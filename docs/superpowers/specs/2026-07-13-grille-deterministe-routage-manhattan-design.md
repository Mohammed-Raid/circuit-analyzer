# Grille déterministe + routage Manhattan pour l'assemblage des îlots

Date : 2026-07-13
Statut : validé (design approuvé en session ; architecture B « refonte dans
schemdraw », périmètre « assemblage seul », « dépliée par défaut, Z conservé »)

## 1. Objectif et périmètre

Réécrire la couche d'ASSEMBLAGE du rendu des îlots (placement des étages,
fils inter-étages, stubs Z locales, chutes VCC/GND) autour de :

1. une **grille absolue déterministe** (positions calculées, plus d'empilement
   incrémental `_CHAINE_DX` fixe) ;
2. un **routage orthogonal Manhattan sans collision** (remplace `_fil_en_z`
   et le câblage ad hoc du DAG branché) ;
3. la **Vue dépliée par défaut** à l'ouverture d'un îlot (le mode Z boîtes
   cliquables reste disponible au toggle) ;
4. **thème et dimensions centralisés** dans `gui/theme.py` + `gui/fonts.py`
   (zéro hex, zéro dimension en dur dans les modules de dessin) ;
5. **isolation d'état** : les nouveaux modules de calcul ne dépendent que des
   structures `circuit_analyzer` ; seul `circuit_viewer.py` touche
   schemdraw/matplotlib/TkAgg ;
6. **cache des figures** : les deux modes (Z / dépliée) d'un îlot sont
   construits au plus une fois par fenêtre ; le toggle bascule sans
   reconstruire.

HORS périmètre (décision explicite) :

- L'INTÉRIEUR des drawers de montage (`_draw_emitter_follower`,
  `_draw_darlington`, `_draw_aop_*`, portes CMOS, boîte puce,
  `dessiner_bloc`/`dessiner_pont`) ne bouge pas : il est audité (A1-A5,
  V1-V5) et validé par le boss. La grille gouverne leurs ORIGINES et leurs
  BBOXES, pas leurs entrailles.
- Pas de moteur tk.Canvas natif : on reste sur le pipeline
  schemdraw 0.22 → matplotlib → FigureCanvasTkAgg (pin
  `schemdraw>=0.18,<0.23` inchangé). Les directives « appels Canvas » et
  « cache d'identifiants Tkinter » de la demande initiale sont transposées :
  isolation vis-à-vis du BACKEND (section 6) et cache de FIGURES (section 7).
- Le rendu réseau (network_viewer) et l'éditeur de schéma ne sont pas
  concernés.

## 2. Architecture — nouveaux modules

```
gui/schema_grid.py     (NOUVEAU, pur calcul, importe uniquement math +
                        circuit_analyzer ; AUCUN import schemdraw/mpl/tk)
gui/schema_router.py   (NOUVEAU, pur calcul, mêmes contraintes)
gui/theme.py           (ÉTENDU : sections SCHEMA_COLORS / SCHEMA_DIMS)
gui/fonts.py           (ÉTENDU : tailles de police des schémas)
gui/circuit_viewer.py  (MODIFIÉ : consomme grid+router ; seul module backend)
gui/impedance_schematic.py, gui/logic_schematic.py, gui/puce_schematic.py
                       (MODIFIÉS : uniquement dé-hardcodage couleurs/dims)
```

Flux de données :

```
matches/ci (circuit_analyzer)
   └─> schema_grid.poser(stages, mesures)       -> PlanGrille
          └─> schema_router.router(plan, nets)  -> dict net -> polyligne
                 └─> circuit_viewer._make_*fig  -> schemdraw Drawing -> fig
```

`circuit_viewer` fournit à `schema_grid` les MESURES des drawers (bbox par
étage), obtenues par un dry-run schemdraw hors écran (Drawing jamais montré,
`d.get_bbox()`), mémoïsées par `(circuit_type, refs)`.

## 3. schema_grid — grille absolue déterministe

### 3.1 Constantes (toutes dans theme.SCHEMA_DIMS)

| Nom        | Valeur | Rôle |
|------------|--------|------|
| `PAS`      | 0.5    | pas de grille, en unités schemdraw |
| `MARGE`    | 1.0    | marge ajoutée autour de la bbox d'un étage |
| `CANAL_H`  | 2.0    | couloir horizontal réservé entre deux colonnes (= 4·PAS) |
| `CANAL_V`  | 2.0    | couloir vertical réservé entre deux bandes |
| `X0`       | 4.5    | origine x de la première colonne (inchangé vs existant) |

### 3.2 Formules

Arrondi grille : `snap(v) = round(v / PAS) * PAS`.

Largeur de slot d'une colonne `c` (étages `E(c)` de la colonne) :

```
L(c) = snap_ceil( max_{e in E(c)} largeur_bbox(e) + 2*MARGE )
       où snap_ceil(v) = ceil(v / PAS) * PAS
```

Origine x de la colonne `c` :

```
x(0) = X0
x(c) = x(c-1) + L(c-1) + CANAL_H
```

Origine y d'un étage en bande `b` (bande 0 en haut, croissante vers le bas) :

```
H(b)  = snap_ceil( max_{e in bande b} hauteur_bbox(e) )
y(b)  = y(b-1) - H(b-1) - CANAL_V          (y(0) = 0)
origine_etage = ( x(c) + MARGE + ancrage_x(e), y(b) + oy_for(e) )
```

`oy_for` = la fonction existante (alignement des sorties d'AOP sur la ligne
de base de la bande) ; `ancrage_x` = décalage entre l'origine du drawer et le
bord gauche de sa bbox (mesuré au dry-run). Les deux sont snappés à PAS.

Chaînes simples = cas particulier à 1 bande. Le DAG branché
(`_layers_montages_flux`) fournit directement (colonne, bande) par étage.

### 3.3 Sorties (`PlanGrille`, dataclass)

- `origines : dict[id(match) -> (x, y)]` — tous multiples de PAS ;
- `obstacles : list[Rect]` — bbox⊕MARGE de chaque étage, snappée, PLUS un
  Rect par stub Z locale (calculé d'après la géométrie connue de
  `_dessiner_z_locale` : largeur 1.2, hauteur 1.65+extra sous/sur l'ancre) ;
- `ports : dict[(id(match), net) -> (x, y, cote)]` — ancres in/out publiées
  par les drawers, snappées ;
- `canaux : list[Rect]` — les couloirs libres (pour information/debug).

Déterminisme : entrée identique -> sortie identique (aucun état module,
aucun random, tri stable des étages par `(couche, ref du montage)`).

## 4. schema_router — routage Manhattan

### 4.1 Algorithme

A* sur le graphe implicite des nœuds de grille (pas PAS) contenus dans la
bbox globale étendue de `CANAL_H` de chaque côté :

- nœuds INTERDITS : intérieur strict d'un `Rect` d'obstacle ;
- coût d'une arête : `PAS` ; pénalité par changement de direction :
  `PENALITE_COUDE = 3 * PAS` (favorise les longs segments droits) ;
- heuristique : distance de Manhattan (admissible).

### 4.2 Réservation d'arêtes (anti-chevauchement)

Le routage est SÉQUENTIEL, nets triés par `(couche du producteur, net)` :

- chaque polyligne retenue réserve ses arêtes de grille ;
- une arête réservée est INTERDITE aux nets suivants (pas de chevauchement
  colinéaire de deux nets distincts) ;
- le CROISEMENT perpendiculaire d'arêtes réservées reste autorisé (la
  légende existante « un croisement sans point n'est pas une liaison »
  couvre la sémantique) ; un même net qui bifurque pose un Dot de jonction.

### 4.3 Sorties et replis

`router(plan, nets) -> dict[net -> list[(x, y)]]` (polylignes orthogonales,
points consécutifs alignés en x ou y, coudes réduits par fusion des segments
colinéaires).

Repli documenté : si A* échoue (grille saturée, cas pathologique), le net
retombe sur le `_fil_en_z` actuel ET un warning est journalisé — jamais
d'exception à l'écran. Test dédié sur un cas synthétique saturé.

### 4.4 Intégration circuit_viewer

- `_draw_island_chain` et `_make_branched_fig` : les origines viennent de
  `PlanGrille.origines` ; TOUS les fils inter-étages viennent du routeur
  (suppression de `_fil_en_z` du chemin nominal ; conservé comme repli) ;
- `_fil_avec_couplage` : le couplage (C série…) est posé au MILIEU du plus
  long segment horizontal de la polyligne routée (les couloirs CANAL_H le
  garantissent d'au moins 4·PAS) ;
- les stubs Z locales (`_dessiner_z_locale`) sont dessinés APRÈS le calcul
  du plan (ils y figurent comme obstacles) et inchangés visuellement.

## 5. Vue dépliée par défaut

- `show_island` construit et affiche d'abord la figure `detaille=True` ;
  le bouton toggle (libellés inchangés) bascule vers le mode Z ;
- `tools/render_ilots_v2.py` et les tests contractuels continuent de rendre
  LES DEUX modes (aucun contrat supprimé) ;
- le drill-down clic-sur-boîte reste réservé au mode Z (comportement
  existant, `_z_hitboxes` vides en dépliée — convention conservée).

## 6. Thème centralisé (dé-hardcodage)

`gui/theme.py` gagne deux dicts figés (MappingProxyType) :

- `SCHEMA_COLORS` : reprend à l'identique les valeurs actuelles —
  `SCH_BG #fafafa`, `WIRE #1e293b`, `BUS #475569`, `COMP_COLORS` (R/C/L/D/
  Q/M/U/F), `Z_FILL #dbeafe`, `Z_EDGE = BLUE_HOVER`, `OPAMP_FILL #eef2ff`,
  `TITRE = OVERLAY`, `GAIN #0f766e`, gris de légende `#64748b`. La règle
  « canvas schémas CLAIR » est un invariant documenté dans le module.
- `SCHEMA_DIMS` : PAS, MARGE, CANAL_H/V, X0, PENALITE_COUDE, et les
  clearances existantes (`_Z_LABEL_CLEAR`, `_Z_DETAIL_*`,
  `_SATELLITE_LABEL_FONTSIZE`→fonts, etc.).

`gui/fonts.py` : tailles de police schémas (`SCHEMA_LABEL=9`,
`SCHEMA_TITRE=11`, `SCHEMA_GAIN=8`, `SCHEMA_LEGENDE=9`) — mêmes valeurs
qu'aujourd'hui, juste nommées.

Les quatre modules de dessin (`circuit_viewer`, `impedance_schematic`,
`logic_schematic`, `puce_schematic`) importent ces tokens ; un test grep
(`test_theme_schemas.py`) interdit tout littéral `#rrggbb` hors theme.py
dans ces fichiers (liste d'exclusions vide, comme test_puces_resolution).
Rendu attendu STRICTEMENT identique pixel à pixel sur ce lot (pur
renommage) — vérifié par les 244 contrats labels existants.

## 7. Isolation d'état et cache de figures

- `schema_grid`/`schema_router` : fonctions pures, entrées = structures
  `circuit_analyzer` + mesures fournies par l'appelant ; testables sans
  display, sans matplotlib importé (test d'import dédié) ;
- cache par fenêtre d'îlot : `etat["figs"] = {False: fig_z|None,
  True: fig_detaillee|None}` rempli paresseusement ; le toggle réutilise la
  figure existante (swap du canvas TkAgg, technique déjà en place pour le
  teardown `_demonter_contexte`) ; le cache de MESURES de drawers
  (`lru_cache` sur `(circuit_type, tuple(refs))`) évite le double dry-run ;
- invalidation : fermeture de la fenêtre (teardown existant) ; aucune
  invalidation à chaud nécessaire (un îlot est immuable pendant l'affichage).

## 8. Tests (TDD, contrats nouveaux + anciens intacts)

Nouveaux (`tests/test_schema_grid.py`, `tests/test_schema_router.py`,
`tests/test_assemblage_manhattan.py`, `tests/test_theme_schemas.py`) :

1. tout point de `origines`/`ports` est multiple de PAS ;
2. déterminisme : deux appels -> structures égales (==) ;
3. aucun segment routé ne traverse un obstacle (intersection stricte) ;
4. aucune paire de nets ne partage une arête colinéaire ;
5. corpus complet : pour chaque îlot multi-montages, les fils inter-étages
   sont orthogonaux (tous segments axis-aligned) dans les DEUX modes ;
6. repli `_fil_en_z` : cas saturé synthétique -> warning + rendu sans crash ;
7. grep anti-hex sur les 4 modules de dessin ;
8. `show_island` ouvre en dépliée ; toggle -> mode Z sans reconstruction
   (compteur d'appels de fabrique espionné) ;
9. imports : `schema_grid`/`schema_router` importables sans matplotlib.

Anciens : les 244 contrats `test_labels_property`, les audits
`test_audit_ilots_visuel` (V1-V5), `test_puce_drawing` (A1-A5) et toute la
suite (1583) restent verts. Boucle visuelle obligatoire : re-render du sweep
complet + inspection PNG avant de déclarer le chantier fini (exigence boss).

## 9. Risques et décisions

- **Bbox dry-run** : mesurer un drawer exige de le dessiner une fois hors
  écran ; coût accepté (mémoïsé), déjà pratiqué ailleurs
  (`draw_without_rendering`).
- **Stubs Z locales comme obstacles** : leur géométrie est recalculée par
  une fonction partagée (pas de duplication de constantes) — la dette
  « 2 heuristiques de placement Z » notée au chantier catalogue n'est pas
  aggravée.
- **`_fil_en_z` conservé en repli** : le supprimer totalement rendrait le
  rendu fragile aux cas pathologiques ; il devient inatteignable dans le
  chemin nominal (assert de non-emprunt dans les tests corpus).
- **Compat XML/exports** : aucun impact (le format et `rapport.py` ne
  changent pas).
