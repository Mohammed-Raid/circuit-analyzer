# Éditeur de schéma niveau KiCad (onglet Dessiner)

Date : 2026-07-15
Statut : validé (design approuvé : 4 axes — vrais symboles, câblage pro,
catalogue dans la palette, raccourcis éditeur — + retrait de l'onglet Saisie)

## 1. Objectif et périmètre

Amener l'onglet Dessiner au niveau d'un éditeur de schéma type KiCad :
symboles schématiques réels, câblage orthogonal à jonctions, puces réelles
plaçables depuis la palette, raccourcis clavier/souris standard. ÉVOLUTION
de `gui/schematic_editor.py` (1079 lignes : undo/redo, clipboard, drag,
zoom, machine à états idle/placing/wiring déjà en place) — PAS de
réécriture.

Inclus : retrait de l'onglet Saisie (l'app revient à 4 onglets).
`gui/tab_quick_entry.py` et `tests/test_tab_quick_entry.py` sont SUPPRIMÉS ;
`circuit_analyzer/saisie.py`, `catalogue.entrees_catalogue()` et
`lire_xml(alias_catalogue=...)` sont CONSERVÉS avec leurs tests (la palette
catalogue s'appuie sur `entrees_catalogue()`).

HORS périmètre : le format `.circ` (CompInst/WireInst inchangés), l'export
XML/netlist, l'analyseur, le rendu des îlots, l'onglet Composants.

## 2. État des lieux (constaté dans le code)

- `_draw_comp` : GND/VCC ont déjà un dessin vectoriel ; TOUS les autres
  types = rectangle + labels + pastilles de broches (COMP_DEFS : couleur,
  w/h, positions de broches sur grille 20).
- `_draw_wire` : fils DÉJÀ topologiques (pin→pin) et DÉJÀ en L
  (`sx1,sy1 → sx2,sy1 → sx2,sy2`) ; pas de jonctions, pas d'évitement.
- Aperçu de fil pendant le câblage : existe (`_rubber_band`, ligne droite).
- Rotation 0/90/180/270 par `_rotate_pin` ; zoom par facteur `_zoom`.
- `schematic_io.py` : sérialisation pure `.circ` + import Composant.

## 3. Axe 1 — Vrais symboles schématiques

### 3.1 Nouveau module `gui/schematic_symbols.py` (logique pure)

Fonctions qui produisent des PRIMITIVES en coordonnées monde (sans canvas,
testables headless) :

```python
# primitive = ("line", [(x,y),...], epaisseur) | ("polygon", [...], rempli)
#           | ("arc", (x0,y0,x1,y1), start, extent) | ("text", (x,y), s, taille, ancre)
def primitives(comp_type: str, defn: dict, rotation: int) -> list[tuple]
```

- Un traceur par type intégré : R (zigzag 6 crêtes), C (2 plaques + fils),
  L (3 arcs), D (triangle plein + barre ; valeur commençant par « LED » →
  + 2 flèches sortantes), F (rectangle fin traversé), Q (cercle + barre de
  base + émetteur fléché ; NPN), M (grille + canal 3 segments + flèche),
  U/AOP (triangle + « + »/« − » aux entrées), T (2 enroulements + barres),
  K (bobine + contact), GND/VCC (reprendre les tracés actuels de
  `_draw_comp`, déplacés ici).
- Types personnalisés et boîtiers catalogue (`__PUCE__`, §5) : boîte à
  encoche + broches en traits courts (stub 8 px) + noms.
- La rotation est appliquée par `primitives()` via `_rotate_pin` (déplacé
  ou importé) — le canvas ne tourne rien lui-même.
- Les POSITIONS DE BROCHES restent celles de `COMP_DEFS`/`_defs` (aucun
  changement de géométrie électrique : les `.circ` existants se rouvrent
  à l'identique).

### 3.2 Rendu dans l'éditeur

`_draw_comp` devient : primitives → items canvas (avec zoom appliqué),
+ pastilles de broches et labels ref/valeur comme aujourd'hui (ref au-dessus,
valeur en dessous du symbole, plus DANS un rectangle). Le nom de type
n'est plus affiché (le symbole parle). Les couleurs par type sont
conservées (COMP_DEFS["color"]) ; tout hex TOUCHÉ par le chantier migre
vers un token theme si équivalent exact, sinon reste (le fichier n'est pas
dans le périmètre du test anti-hex — pas de tokenisation massive hors
sujet).

## 4. Axe 2 — Câblage pro

- **Jonctions automatiques** : après chaque `_redraw_all`/mutation de fils,
  calcul des points monde où ≥ 3 EXTRÉMITÉS de fils coïncident → un disque
  plein (couleur fil) y est dessiné. Logique pure dans
  `schematic_io.py` : `points_jonction(comps, wires, defs) -> list[(x,y)]`.
- **Aperçu orthogonal** : le fil fantôme pendant le câblage devient un L
  (H puis V) identique au tracé final — plus de diagonale.
- **Aimantation broche** : pendant le câblage, si le curseur est à
  ≤ 12 px écran d'une broche, l'aperçu s'y accroche (halo sur la broche
  cible). La validation reste le clic sur broche (comportement actuel).
- Le drag d'un composant redessine ses fils (existant, conservé).

## 5. Axe 3 — Catalogue dans la palette

- La palette gagne une section « Puces réelles » : liste déroulante/boutons
  construits depuis `catalogue.entrees_catalogue()` (NE555, LM393, LM339,
  PC817, LM317, 74HC00/08/32/04/74/157/138, 741/1458/x458, 7805/7812,
  2N2222/BC547/2N3904, IRFZ44N/BS170/IRLZ44N, 1N4148/1N4007, LED r/v/b).
- Sélection → mode placement d'un composant :
  - transistors/MOSFET/diodes/LED : type Q/M/D existant, `value` =
    référence (symbole de l'axe 1, LED reconnaît « LED … ») ;
  - puces U à broches numérotées : def DYNAMIQUE générée par
    `def_puce(entree) -> dict` (dans `schematic_symbols.py`) — boîtier
    DIP : broches 1..n/2 à GAUCHE de haut en bas, n/2+1..n à DROITE de bas
    en haut (convention DIP), pas vertical 20, hauteur = (n/2+1)·20,
    libellé `n FONCTION` à côté de chaque broche ; `comp_type` stocké =
    `"U"`, la def dynamique est enregistrée dans `self._defs` sous une clé
    dédiée `f"U::{value}"` avec `comp_type` réel U à l'export (le `.circ`
    stocke `type="U::NE555"` → adaptation de `editor_to_dict`/export
    netlist : `type` exporté = partie avant `::`, `value` = après).
    Un `.circ` existant (sans `::`) reste valide.
- À l'analyse, les broches numérotées suivent le flux réel existant
  (identification + aliasing) — aucun changement analyseur.

## 6. Axe 4 — Raccourcis éditeur

- `R` : rotation +90° du composant en cours de placement OU de la
  sélection (déjà partiellement présent — normaliser le binding, marche
  dans les deux états).
- Molette : zoom CENTRÉ SUR LE CURSEUR (le point monde sous la souris
  reste sous la souris). Boutons de zoom existants conservés.
- Clic-milieu maintenu : pan (curseur « fleur »/main), relâchement stoppe.
- **Sélection rectangle** : glisser sur fond vide en état idle → rectangle
  de sélection ; `self._selected_id` devient `self._selected_ids: set[int]`
  (l'existant mono-sélection est un cas particulier) ; Suppr supprime la
  sélection ET ses fils ; drag d'un élément sélectionné déplace TOUTE la
  sélection ; clic sur fond vide désélectionne.
- `Échap` : annule le mode courant (placement, câblage, sélection) —
  unifier ce qui existe.
- Ctrl+Z/Y/C/V/D existants : inchangés (le clipboard multi n'est PAS
  requis — YAGNI ; coller ne concerne que le dernier composant copié).
- La légende des raccourcis de la palette est mise à jour.

## 7. Retrait de l'onglet Saisie

- `gui/app_window.py` : suppression de l'onglet « Saisie » (nav + frame +
  câblages) — retour à 4 onglets.
- Suppression : `gui/tab_quick_entry.py`, `tests/test_tab_quick_entry.py`.
- Conservés (avec tests) : `circuit_analyzer/saisie.py` (+
  `tests/test_saisie.py`), `entrees_catalogue()` et
  `lire_xml(alias_catalogue=...)` (+ `tests/test_saisie_fondations.py`),
  `default_value` dans `TYPES_COMPOSANTS`.

## 8. Tests (TDD)

`tests/test_schematic_symbols.py` (pur, sans display) :
1. chaque type intégré a des primitives non vides ; les 4 rotations
   produisent des géométries distinctes cohérentes (rotation de 90° d'un
   point de primitive = `_rotate_pin` du point d'origine) ;
2. R : nombre de segments du zigzag attendu ; D avec value « LED rouge » :
   2 primitives de plus (flèches) que D nue ;
3. `def_puce(NE555)` : 8 broches, 1..4 à gauche (x<0) de haut en bas,
   5..8 à droite de bas en haut, positions multiples de 20 ;
4. pureté d'import (subprocess sans tkinter).

`tests/test_schematic_io.py` (étendre) :
5. `points_jonction` : 3 fils arrivant sur la même broche → 1 jonction au
   point de la broche ; 2 fils → aucune ;
6. export d'un `comp_type` `U::NE555` → netlist/dict avec type U et
   value NE555 ; `.circ` ancien sans `::` inchangé (non-régression sur les
   tests existants du fichier).

`tests/test_schematic_editor.py` (Tk, skip sans display — créer s'il
n'existe pas, style test_island_viewport) :
7. placement d'une puce catalogue depuis la palette → CompInst créé avec
   def dynamique, broches numérotées ;
8. molette : le point monde sous le curseur est invariant au zoom ;
9. sélection rectangle : 2 composants dans la zone → `_selected_ids` à 2 ;
   Suppr les retire avec leurs fils ; Échap vide la sélection ;
10. e2e : petit montage placé programmatique (R + LED + VCC + GND câblés)
    → export netlist → `analyser` détecte au moins l'îlot, ET puce NE555
    placée → export → `identifier` la reconnaît.
11. app_window : retour à 4 onglets (adapter le test d'intégration
    existant au lieu de le supprimer aveuglément).

Boucle visuelle OBLIGATOIRE (règle boss) : script scratchpad qui monte
l'éditeur, place un montage représentatif (R, C, Q, AOP, NE555 catalogue,
GND/VCC, fils avec jonction), capture PNG aux 4 rotations d'un R et en
zoom 0.5/1/2 — PNG INSPECTÉS avant tout commit de rendu.

## 9. Risques et décisions

- Les hex en dur préexistants de schematic_editor.py restent hors
  périmètre anti-hex (dette connue) ; seuls les hex des lignes touchées
  migrent si un token exact existe.
- `type="U::REF"` dans `.circ` : choix le moins invasif pour porter les
  defs dynamiques ; l'export re-sépare — documenté dans schematic_io.
- Sélection multiple : le clipboard reste mono-composant (YAGNI).
- Pas de routage à évitement d'obstacles sur le canvas (les L suffisent au
  geste de dessin ; l'utilisateur place ses composants) — YAGNI, réévalué
  si le boss le demande à l'usage.
- Textes non tournés avec le symbole (ref/valeur restent horizontaux,
  comme KiCad).
