# Brochage libre par instance (éditeur de schéma) — Design

**Date :** 2026-07-23
**Statut :** design présenté, en attente de relecture spec avant plan.

## Context (pourquoi)

Aujourd'hui, poser un composant dans `gui/schematic_editor.py` n'offre **aucune
liberté sur les broches**. Deux cas seulement :

- **Types intégrés** (`COMP_DEFS`) : géométrie figée, écrite en dur.
- **Types personnalisés** (bibliothèque) : `_auto_def` (l. 68) répartit
  mécaniquement les broches **moitié à gauche / moitié à droite**, pas de 30 px,
  boîte 80 px de large. Aucun contrôle.

Les seuls choix à la pose sont la **position** et la **rotation**. Or les vraies
cartes (voir `cartes_reelles_dialecte`) sont pleines de connecteurs et d'ICs dont
le brochage physique ne ressemble pas à un partage gauche/droite : on veut poser
une boîte et **dire où sont les broches**.

**But :** chaque composant **posé** peut avoir son propre brochage, défini à la
souris sur le canevas.

## Décisions verrouillées (arbitrage boss, 2026-07-23)

| Question | Décision |
|---|---|
| Niveau de liberté | **Broches libres sur le canevas, par instance** |
| Point de départ | **Les deux** : « Boîte vierge » en palette **et** « Éditer broches » sur tout composant posé |
| Placement | **Sur le bord, aligné grille** ; le côté donne le sens du fil |
| Nommage | **Numéroté auto** (1, 2, 3…), **renommable** (double-clic) |
| Réutilisation | **Par instance seulement (v1)** |
| Taille de boîte | **Auto-ajustée** aux broches (pas de poignée — voir §Architecture) |

## Non-goals (v1)

- Pas de « sauver comme type » : aucune écriture dans `component_library.json`,
  aucun nommage de type, aucune déduplication. (YAGNI assumé.)
- Pas de poignée de redimensionnement manuelle : la boîte s'ajuste seule.
- Pas de broche **à l'intérieur** de la boîte ni en diagonale : bord uniquement.
- Pas de modification du format d'échange avec l'analyseur : l'export reste
  `Composant(ref, type, pins={nom: net}, value)` — les **positions** de broches
  ne sortent pas de l'éditeur, seuls les **noms** et la connectique comptent.
- Pas de touche à l'éditeur C# ERetroDesign.

## Architecture

### 1. Modèle de données : le brochage vit sur `CompInst`

```python
@dataclass
class CompInst:
    ...
    rotation: int = 0
    pinout: Optional[dict[str, tuple[str, int]]] = None   # nom -> (côté, décalage)
```

- `côté` ∈ `{"L", "R", "T", "B"}` (gauche / droite / haut / bas) ;
- `décalage` = distance **signée**, multiple du pas de grille, depuis le milieu
  de ce bord ;
- `None` = comportement actuel **strictement inchangé** (le type fait foi) ;
- `{}` (dict vide) = boîte vierge sans broche.

**Pourquoi `(côté, décalage)` et pas `(x, y)` :**
1. le côté **est** le sens du fil, on n'a pas à le redéduire ;
2. la taille de boîte peut changer sans déplacer les broches — d'où
   l'auto-ajustement, qui rend la poignée de redimensionnement inutile ;
3. la rotation se réduit à une permutation de côtés.

**Pourquoi sur `CompInst` et pas dans `self._defs` :** `_snapshot` (l. 210)
deep-copie déjà `_comps` — l'**annulation des éditions de broches est donc
gratuite**. Un dict parallèle ou une entrée `_defs` obligerait à étendre
`_snapshot`/`_restore`, avec le risque classique d'un undo qui restaure les
composants mais pas leur géométrie.

**Alternative écartée — un comp_type synthétique par instance** (dans la lignée
de `_ensure_dyn_def`, l. 573, qui synthétise déjà `"U::NE555"` à l'exécution) :
séduisant car **zéro** site d'appel à toucher, mais `type_reel` (schematic_io
l. 52) coupe sur `"::"` et `exporter_composants` (l. 1506) réinjecte la partie
droite comme **valeur du composant**. Tout suffixe d'unicité corromprait la
valeur envoyée à l'analyseur. Rejeté.

### 2. Le résolveur `_geom(comp)` — le vrai coût du chantier

`self._defs[comp.comp_type]["pins"]` est lu à **15 endroits**. On introduit un
accesseur unique :

```python
def _geom(self, comp: CompInst) -> dict:
    """Géométrie effective : brochage d'instance s'il existe, sinon le type."""
```

Il renvoie un dict de même forme que les defs actuelles (`label`, `color`, `w`,
`h`, `pins` en offsets **absolus** `(dx, dy)`), pour que tous les consommateurs
existants marchent sans changer de contrat.

Sites à basculer sur `_geom` :

| Fichier / ligne | Rôle |
|---|---|
| `schematic_editor.py:659` | `_draw_comp` — rendu |
| `:719-724` | pastilles + libellés de broches |
| `:746, :748` | `_draw_wire` |
| `:777` | `_redraw_jonctions` → `points_jonction` |
| `:802` | `_find_pin_at` (hit-test + aimantation) |
| `:811` | `_find_comp_at` (boîte englobante) |
| `:827, :829` | `_find_wire_at` |
| `:1077` | boîte englobante de sélection |
| `:1119, :1128` | câblage en cours (`_start_wiring` / prévisualisation) |
| `:1195` | redessin |
| `:1399, :1401` | `load_dict` — validation des broches de fil |
| `:1476` | `to_netlist` |
| `:1505` | `exporter_composants` |
| `:1528` | `unconnected_pins` |
| `schematic_io.py:65` | `_pin_monde(comp, pin, defs)` |
| `schematic_io.py:72` | `points_jonction(comps, wires, defs)` |

Les deux helpers de `schematic_io.py` prennent un `defs` **indexé par type** :
un type seul ne peut pas distinguer deux instances, donc leur signature doit
accepter un **résolveur** `geom(comp) -> dict` au lieu du dict. Changement
mécanique, mais c'est une signature publique du module → à traiter comme tel.

`build_from_components(composants, defs)` (schematic_io l. 96), appelé par
`tab_draw.py:154`, est **hors périmètre** : il part de `Composant` issus de
l'analyse et les place à neuf, sans instance d'éditeur — il garde son `defs`
indexé par type, inchangé.

**Cache.** `_find_pin_at` boucle sur tous les composants × broches à chaque
mouvement de souris ; recalculer un dict à chaque appel est gaspilleur à
l'échelle des cartes réelles. `_geom` mémoïse dans `self._geom_cache: dict[int,
dict]`, invalidé par : édition de broche, rotation, `_restore` (undo/redo),
`load_dict`, suppression. **Invalidation globale par défaut** — un cache de
géométrie périmé produit des fils qui pointent à côté, symptôme pénible à
diagnostiquer.

### 3. Auto-ajustement de la boîte

Après toute mutation de broche :

```
h = max(_BOX_MIN_H, 2 * max(|décalage| des broches L/R) + marge)
w = max(_BOX_MIN_W, 2 * max(|décalage| des broches T/B) + marge)
```

Une broche glissée au-delà du coin **allonge le bord** au lieu d'être écrêtée :
on ne peut jamais « manquer de bord », donc jamais besoin d'une poignée.

### 4. Rendu : un composant broché librement devient une BOÎTE

Le symbole vient de `primitives(comp.comp_type, defn, rot, value)` — le zigzag
d'une résistance est **dessiné pour ses deux broches d'origine**. Si on déplace
les broches, le symbole ne suit pas et le dessin ment.

**Règle v1 :** `comp.pinout is not None` ⇒ rendu en **boîte générique
étiquetée** (le chemin `est_boite_generique` existant), quel que soit le type.
C'est honnête : tu as rebroché, tu obtiens une boîte. Le `comp_type` (donc
l'export et l'analyse) est **inchangé** — une résistance rebrochée reste un `R`.

> Conséquence à valider : « éditer les broches » d'une résistance lui fait
> perdre son zigzag. Acceptable pour connecteurs/ICs (la cible), moins pour les
> passifs 2 broches. Point n°1 de la relecture.

### 5. Boîte vierge

Nouveau type intégré `"X"` dans `COMP_DEFS` (`schematic_editor.py:29` ; la clé
`"X"` est libre — les 13 types actuels sont C, D, F, GND, K, L, M, Q, R, SW, T,
U, VCC) — label « Boîte », **0 broche**,
`default_value` vide. `X` est déjà la convention maison pour la boîte noire
(voir import ERetroDesign), donc les réfs se numérotent `X1`, `X2`… et l'export
donne `Composant(type="X")`, que l'analyseur sait déjà traiter.

Le bouton de palette apparaît **automatiquement** : `_build_palette` (l. 345)
itère `self._defs.items()`. À la pose, `_place_at` met `pinout={}` si le type
est `"X"`.

## Interactions

Nouvel état d'éditeur : `"pinedit"` (à côté de `idle | placing | wiring`), avec
`self._pinedit_id`.

**Entrée.** Clic droit sur un composant → nouvelle entrée de menu
« ⊹ Éditer broches » (`_on_right_click`, l. 947, après « Rotation »).

**Amorçage paresseux.** Si `comp.pinout is None`, l'amorçage — projection de
chaque broche du type sur le bord le plus proche → `(côté, décalage)` — n'a lieu
qu'à la **première mutation réelle**, pas à l'entrée dans le mode. Sinon, comme
`pinout is not None` déclenche le rendu en boîte (§4), ouvrir l'éditeur puis
faire `Échap` transformerait le symbole sans qu'on ait rien touché. Avec
l'amorçage paresseux : entrer et sortir ne change **rien**.

**En mode `pinedit`** (seul le composant édité réagit ; les autres sont inertes) :

| Geste | Effet |
|---|---|
| Clic sur le bord, à vide | Ajoute une broche, nommée du **plus petit entier ≥ 1 non utilisé** |
| Glisser une broche | La fait coulisser ; au relâché, aimantation `(bord le plus proche, pas de grille)` |
| Double-clic sur une broche | Renomme (`simpledialog`) ; refuse vide et doublon, message de statut |
| Broche sélectionnée + `Suppr` | Supprime la broche **et les fils qui y étaient rattachés** |
| `Échap` | Sort du mode |

Aimantation en coin : le bord dont la distance perpendiculaire est la plus
faible ; en cas d'égalité, les bords **horizontaux** gagnent (arbitraire mais
déterministe — testable).

**Repères visuels :** contour en pointillés sur la boîte éditée, pastilles
agrandies, nom affiché à côté de chaque broche, statut rappelant les gestes.

**Annulation :** chaque mutation (ajout / déplacement / renommage / suppression)
appelle `_push_undo()` avant de muter — donc une action = une étape annulable.

## Duplication (copier / coller / dupliquer)

« Par instance » impose que le brochage soit **cloné, pas partagé** :
`_add_comp` / le collage doivent deep-copier `pinout`. Sans ça, deux instances
partageraient le même dict et éditer l'une modifierait l'autre — exactement ce
que la décision « par instance » exclut.

## Persistance (`.circ`)

L'entrée composant gagne un champ **optionnel** :

```json
{ "id": 4, "ref": "X1", "type": "X", "cx": 200, "cy": 160, "rotation": 0,
  "pinout": { "1": ["L", -20], "2": ["L", 20], "VCC": ["T", 0] } }
```

- **Version inchangée (1)**, champ additif : `load_dict` (l. 1371) rejette tout
  ce qui n'est pas version 1, donc bumper à 2 rendrait illisibles les schémas
  existants. Absent ⇒ `pinout=None` ⇒ comportement actuel.
- Un lecteur d'une version antérieure ignore le champ : dégradation douce (la
  boîte reprend la géométrie du type), pas de corruption.
- `load_dict` doit valider les broches de fil contre le **brochage résolu**
  (`_geom`), pas contre `self._defs[type]` (l. 1399-1401) — sinon tout fil
  branché sur une broche libre est jeté au rechargement.

## Tests

Fixture Tk existante de `tests/test_schematic_editor.py` (`ctk.CTk()` +
`pytest.skip` sans display), API interne appelée directement comme le fait déjà
`_place(ed, t, cx, cy)`.

**Non-régression (le plus important) :**
- Un composant à `pinout=None` rend, se câble, s'exporte, se sauve et se relit
  **à l'identique** — la suite existante (`test_schematic_editor.py`,
  `test_editor_edition.py`, `test_schematic_io.py`) doit rester verte sans
  modification.
- Une résistance rend toujours son zigzag (`test_resistance_rendue_en_zigzag…`).

**Nouveaux :**
1. Boîte vierge posée → 0 broche, boîte de taille minimale, réf `X1`.
2. Ajout de broche sur un bord → nommée `"1"`, puis `"2"`, `"3"`.
3. Suppression de `"2"` puis ajout → réutilise `"2"` (plus petit libre).
4. Aimantation : un clic à une position quelconque donne un décalage **multiple
   du pas de grille** et un côté attendu ; cas du coin (règle horizontale).
5. Auto-ajustement : broche glissée au-delà du coin → `h` (ou `w`) augmente.
6. Renommage : `"3"` → `"VCC"` ; refus du doublon ; refus du vide.
7. Suppression d'une broche câblée → le fil disparaît, aucun fil orphelin.
8. Câblage sur une broche libre : `_find_pin_at` la trouve, `_draw_wire` la
   place au bon endroit monde.
9. Amorçage paresseux : entrer en `pinedit` sur un `R` puis `Échap` sans rien
   toucher → `pinout` reste `None`, le zigzag est intact. Après la **première**
   mutation, les 2 broches d'origine sont projetées à des positions monde
   **inchangées**.
10. Rendu : `pinout is not None` ⇒ boîte, pas le symbole d'origine.
11. Export : `exporter_composants` d'une boîte libre → `Composant` avec les noms
    de broches libres, `type` inchangé, `value` **non polluée**.
12. Annulation : ajout de broche puis `Ctrl+Z` → brochage d'avant restauré (et
    cache de géométrie invalidé — le redessin doit être correct).
13. Round-trip `.circ` : sauvegarde/relecture conserve `pinout` et les fils.
14. Duplication : copier-coller une boîte libre puis éditer la copie → **l'orig-
    inal n'est pas modifié**.
15. Rétrocompatibilité : un `.circ` **sans** `pinout` se relit sans erreur.

## Risques

| Risque | Parade |
|---|---|
| Refactor `_geom` sur 15 sites : un oubli = fil qui pointe à côté | Basculer **tous** les sites en une tâche, puis grep `_defs\[.*comp_type\]` doit ne rien laisser sur un chemin d'instance |
| Cache de géométrie périmé | Invalidation globale par défaut ; test d'annulation dédié (n°12) |
| Signature publique de `schematic_io` modifiée | Traiter comme un changement d'API : vérifier `tab_draw.py:154` et `test_schematic_io.py` |
| Perte du symbole à l'édition d'un passif | Décision assumée §4 — à confirmer en relecture |

## Preuve visuelle (exigence permanente)

Conformément à la directive « toujours produire le schéma » : à la fin, PNG
rendus **et inspectés** — une boîte vierge brochée à la main, un connecteur
multi-broches, et un schéma existant non modifié (non-régression) — puis
supprimés (jamais committés).
