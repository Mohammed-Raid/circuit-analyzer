# Lisibilité des gros îlots — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre lisible la vue d'îlot au niveau Impédance Z pour les gros îlots (regrouper les dipôles, espacer le texte, décoller les labels de net), sans casser le drill-down.

**Architecture:** Trois changements confinés à `gui/circuit_viewer.py`. (1) Réordonner les lignes dans `_build_island_schematic_plan` pour grouper les dipôles partageant une paire de colonnes → fin de la diagonale. (2) Pas vertical adaptatif au lieu d'un décrément fixe → fin des chevauchements de texte. (3) Marges (`ofst`) sur les labels de net dans les drawers. Le moteur de dessin et les hitboxes de drill-down restent intacts.

**Tech Stack:** Python, schemdraw 0.22 (`elm.*`), matplotlib `Figure`, pytest.

## Global Constraints

- Aucun commit ni PR ne doit porter `Co-Authored-By Claude` (directive utilisateur, mémoire `feedback_no_claude_coauthor.md`).
- Tous les passifs R/L/C restent réduits en « Impédance Z » ; ne pas réintroduire de détecteur passif nommé.
- Branche de travail : `rewrite-simple`.
- La suite `python -m pytest -q` doit rester verte.

---

### Task 1 : Regrouper les dipôles par paire de colonnes (anti-escalier)

**Files:**
- Modify: `gui/circuit_viewer.py` (`_build_island_schematic_plan` ~l.489-543 ; ajout helper `_pair_key` près des constantes ~l.448)
- Test: `tests/test_island_viewer.py`

**Interfaces:**
- Consumes: `_build_island_schematic_plan(model) -> dict {label, columns, rows, caption}` (existant) ; `_is_multi_pin(comp) -> bool` (existant, l.451).
- Produces: `_pair_key(comp, col_nets) -> tuple[str, ...]` (nets de `comp` présents dans `col_nets`, triés). Contrat enrichi de `_build_island_schematic_plan` : `plan["rows"]` ordonne les dipôles partageant la même paire de colonnes de façon contiguë, puis place les composants multi-broches en fin.

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter dans `tests/test_island_viewer.py` (section « Plan / layout pur ») :

```python
def test_dipoles_sharing_a_column_pair_are_contiguous():
    # Za et Zc relient la meme paire {A,B} ; Zb relie {B,C}. Entrelaces dans
    # l'ordre du modele -> doivent etre regroupes (anti-escalier).
    model = {"label": "I", "components": [
        _unit("Za", "Z", {"1": "A", "2": "B"}),
        _unit("Zb", "Z", {"1": "B", "2": "C2"}),
        _unit("Zc", "Z", {"1": "A", "2": "B"}),
        _unit("Zd", "Z", {"1": "C2", "2": "A"}),  # rend C2 colonne (2 connexions)
    ]}

    plan = _build_island_schematic_plan(model)

    order = [r["ref"] for r in plan["rows"]]
    assert abs(order.index("Za") - order.index("Zc")) == 1   # meme paire -> adjacents


def test_multi_pin_devices_are_ordered_after_dipoles():
    model = {"label": "I", "components": [
        _unit("U1", "U", {"IN+": "A", "IN-": "B", "OUT": "C2"}),
        _unit("Za", "Z", {"1": "A", "2": "B"}),
    ]}

    plan = _build_island_schematic_plan(model)

    order = [r["ref"] for r in plan["rows"]]
    assert order.index("Za") < order.index("U1")
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `python -m pytest tests/test_island_viewer.py::test_dipoles_sharing_a_column_pair_are_contiguous tests/test_island_viewer.py::test_multi_pin_devices_are_ordered_after_dipoles -q`
Expected: FAIL (l'ordre actuel suit le modèle, Za/Zc ne sont pas adjacents ; U1 reste en tête).

- [ ] **Step 3 : Ajouter le helper `_pair_key`**

Juste après les constantes de pas (après `COL_PITCH = 2.4`, ~l.448) :

```python
def _pair_key(comp, col_nets):
    """@brief Cle de regroupement d'un dipole : ses nets qui sont des colonnes, tries.

    Deux dipoles reliant la meme paire de colonnes partagent la meme cle, donc
    seront contigus apres tri -> ils s'empilent verticalement au lieu de deriver.
    """
    cols = sorted(
        net for net in (comp.get("pins", {}) or {}).values() if net in col_nets
    )
    return tuple(cols)
```

- [ ] **Step 4 : Réordonner les composants avant l'assignation des `y`**

Dans `_build_island_schematic_plan`, après le calcul de `col_nets` (l.509) et **avant** la boucle `for idx, comp in enumerate(components)`, insérer :

```python
    # Anti-escalier : grouper les dipoles par paire de colonnes ; les composants
    # multi-broches (AOP/blocs) partent en fin (voie dediee a droite).
    dipoles = [c for c in components if not _is_multi_pin(c)]
    devices = [c for c in components if _is_multi_pin(c)]
    dipoles.sort(key=lambda c: (_pair_key(c, col_nets), c.get("ref", "")))
    components = dipoles + devices
```

(La boucle existante itère ensuite `components` — désormais réordonné. Aucun autre changement dans cette étape.)

- [ ] **Step 5 : Lancer les tests pour vérifier qu'ils passent**

Run: `python -m pytest tests/test_island_viewer.py -q`
Expected: PASS (les 2 nouveaux + les 10 existants).

- [ ] **Step 6 : Commit**

```bash
git add gui/circuit_viewer.py tests/test_island_viewer.py
git commit -m "feat(viewer): regroupe les dipoles par paire de colonnes (anti-escalier)"
```

---

### Task 2 : Pas vertical adaptatif + labels cohérents en haut

**Files:**
- Modify: `gui/circuit_viewer.py` (constantes ~l.446-448 ; `_row_gap` nouveau ~l.449 ; boucle d'assignation `y` dans `_build_island_schematic_plan` ~l.511-518 ; `_draw_island_schematic` ~l.618-627 ; `_make_island_fig` height ~l.395)
- Test: `tests/test_island_viewer.py`

**Interfaces:**
- Consumes: `_is_multi_pin(comp)` (l.451).
- Produces: `_row_gap(prev, cur) -> float` (pas vertical entre deux lignes voisines). Constante `LABEL_LINE`. `ROW_PITCH` passe de `1.6` à `2.0`.

- [ ] **Step 1 : Mettre à jour le test d'espacement existant**

Dans `tests/test_island_viewer.py`, dans `test_opamp_symbol_and_rows_do_not_overlap`, remplacer la dernière assertion :

```python
    assert all(abs(a - b) >= 1.5 for a, b in zip(ys, ys[1:]))
```

par :

```python
    assert all(abs(a - b) >= 2.0 for a, b in zip(ys, ys[1:]))   # pas mini = ROW_PITCH
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `python -m pytest tests/test_island_viewer.py::test_opamp_symbol_and_rows_do_not_overlap -q`
Expected: FAIL (le pas actuel est 1.6 < 2.0 entre deux dipôles).

- [ ] **Step 3 : Bumper les constantes et ajouter `_row_gap`**

Remplacer le bloc de constantes (l.446-448) :

```python
ROW_PITCH = 1.6        # pas vertical entre deux composants 2 broches
MULTI_PITCH = 3.4      # pas elargi autour d'un composant multi-broches (AOP, bloc)
COL_PITCH = 2.4
```

par :

```python
ROW_PITCH = 2.0        # pas vertical entre deux composants 2 broches (symbole + label + marge)
MULTI_PITCH = 3.4      # pas elargi autour d'un composant multi-broches (AOP, bloc)
COL_PITCH = 2.4
LABEL_LINE = 0.5       # rallonge le pas quand une etiquette porte une valeur (2 lignes)


def _row_gap(prev, cur):
    """@brief Pas vertical adaptatif entre deux lignes voisines (anti-collision texte)."""
    if _is_multi_pin(prev) or _is_multi_pin(cur):
        return MULTI_PITCH
    gap = ROW_PITCH
    if (prev.get("value") or "") or (cur.get("value") or ""):
        gap += LABEL_LINE
    return gap
```

(`_is_multi_pin` est défini plus bas dans le fichier ; `_row_gap` n'est appelé qu'à l'exécution, donc l'ordre de définition au niveau module est sans incidence.)

- [ ] **Step 4 : Utiliser `_row_gap` dans la boucle d'assignation des `y`**

Dans `_build_island_schematic_plan`, remplacer la boucle (l.511-518) :

```python
    rows = []
    y = 0.0
    prev_multi = False
    for idx, comp in enumerate(components):
        is_multi = _is_multi_pin(comp)
        if idx > 0:
            y -= MULTI_PITCH if (is_multi or prev_multi) else ROW_PITCH
        prev_multi = is_multi
        pins = list((comp.get("pins", {}) or {}).items())
```

par :

```python
    rows = []
    y = 0.0
    prev = None
    for comp in components:
        if prev is not None:
            y -= _row_gap(prev, comp)
        prev = comp
        pins = list((comp.get("pins", {}) or {}).items())
```

(Le reste du corps de boucle — calcul de `stubs`, `rows.append(...)` — est inchangé.)

- [ ] **Step 5 : Labels de dipôles cohérents en haut (fin de l'alternance)**

Dans `_draw_island_schematic`, remplacer le bloc (l.618-627) :

```python
    passive_i = 0
    for row in rows:
        cols_pins = [(p, n) for p, n in row["pins"] if n in x_by_net]
        if row["symbol"] != "opamp" and len(row["pins"]) == 2:
            # etiquettes alternees haut/bas : evite les collisions sur lignes voisines.
            label_loc = "top" if passive_i % 2 == 0 else "bottom"
            passive_i += 1
            _draw_two_pin_row(d, row, x_by_net, label_loc, hitboxes)
        else:
            _draw_block_row(d, row, cols_pins, x_by_net, device_x)
```

par :

```python
    for row in rows:
        cols_pins = [(p, n) for p, n in row["pins"] if n in x_by_net]
        if row["symbol"] != "opamp" and len(row["pins"]) == 2:
            # label toujours en haut : le pas adaptatif garantit l'air necessaire.
            _draw_two_pin_row(d, row, x_by_net, "top", hitboxes)
        else:
            _draw_block_row(d, row, cols_pins, x_by_net, device_x)
```

- [ ] **Step 6 : Ajuster la hauteur de figure au nouveau pas**

Dans `_make_island_fig`, remplacer (l.395) :

```python
    height = max(4.8, 0.9 * max(2, len(plan["rows"])) + 2.0)
```

par :

```python
    height = max(4.8, 1.15 * max(2, len(plan["rows"])) + 2.0)
```

- [ ] **Step 7 : Lancer toute la suite du viewer**

Run: `python -m pytest tests/test_island_viewer.py -q`
Expected: PASS (12 tests).

- [ ] **Step 8 : Commit**

```bash
git add gui/circuit_viewer.py tests/test_island_viewer.py
git commit -m "feat(viewer): pas vertical adaptatif + labels coherents en haut (anti-collision)"
```

---

### Task 3 : Marges sur les labels de net (décollage des symboles/AOP)

**Files:**
- Modify: `gui/circuit_viewer.py` (`_draw_island_schematic` label de colonne ~l.614 ; `_draw_two_pin_row` labels moignon/isolé ~l.667-676 ; `_draw_block_row` labels de stub ~l.692,698)
- Test: `tests/test_island_viewer.py`

**Interfaces:**
- Consumes: drawers existants. Aucun changement de signature.
- Produces: tous les labels de net (`loc` top/left/right) dessinés avec un `ofst` de séparation. Le contenu texte (donc les assertions sur `ax.texts`) est inchangé.

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter dans `tests/test_island_viewer.py` (section « Rendu figure ») :

```python
def test_net_labels_are_offset_from_symbols():
    # Garde-fou de non-regression : un rendu avec moignons E/S et AOP ne doit pas
    # lever, et tous les noms de net attendus doivent etre presents (decales).
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "MID"}, "10k"),
        Composant("C1", "C", {"1": "MID", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "MID", "IN-": "GND", "OUT": "OUT"}),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "I", "composants": ["R1", "C1", "U1"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    fig = _make_island_fig(model)

    texts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("IN" in t for t in texts)     # net moignon affiche
    assert any("OUT" in t for t in texts)    # net moignon de l'AOP affiche
```

- [ ] **Step 2 : Lancer le test pour vérifier l'état courant**

Run: `python -m pytest tests/test_island_viewer.py::test_net_labels_are_offset_from_symbols -q`
Expected: PASS déjà (le test verrouille le comportement avant le refactor des marges ; il doit rester vert après).

- [ ] **Step 3 : Ajouter une constante d'offset et l'appliquer au label de colonne**

Après `_WIRE = "#1e293b"` (l.590), ajouter :

```python
_LBL_OFST = 0.18   # decalage des labels de net pour les decoller des symboles
```

Dans `_draw_island_schematic`, remplacer (l.614) :

```python
        d += elm.Dot().at((c["x"], top)).label(c["net"], loc="top", color=_BUS)
```

par :

```python
        d += elm.Dot().at((c["x"], top)).label(
            c["net"], loc="top", color=_BUS, ofst=_LBL_OFST)
```

- [ ] **Step 4 : Décaler les labels de moignon et isolés dans `_draw_two_pin_row`**

Dans `_draw_two_pin_row`, branche moignon, remplacer (l.667) :

```python
        if not _is_not_connected(stub_net):
            d += elm.Dot().label(stub_net, loc="right", color=_BUS)
```

par :

```python
        if not _is_not_connected(stub_net):
            d += elm.Dot().label(stub_net, loc="right", color=_BUS, ofst=_LBL_OFST)
```

Branche composant isolé, remplacer (l.673-676) :

```python
    if not _is_not_connected(n1):
        d += elm.Dot().at((0.0, y)).label(n1, loc="left", color=_BUS)
    if not _is_not_connected(n2):
        d += elm.Dot().at((1.4, y)).label(n2, loc="right", color=_BUS)
```

par :

```python
    if not _is_not_connected(n1):
        d += elm.Dot().at((0.0, y)).label(n1, loc="left", color=_BUS, ofst=_LBL_OFST)
    if not _is_not_connected(n2):
        d += elm.Dot().at((1.4, y)).label(n2, loc="right", color=_BUS, ofst=_LBL_OFST)
```

- [ ] **Step 5 : Décaler les labels de broche/stub dans `_draw_block_row`**

Dans `_draw_block_row`, remplacer (l.692) :

```python
        d += elm.Dot().at((x, y)).label(pin, loc="bottom", color=_BUS)
```

par :

```python
        d += elm.Dot().at((x, y)).label(pin, loc="bottom", color=_BUS, ofst=_LBL_OFST)
```

et remplacer (l.698) :

```python
        d += elm.Dot().label(net, loc="right", color=_BUS)
```

par :

```python
        d += elm.Dot().label(net, loc="right", color=_BUS, ofst=_LBL_OFST)
```

- [ ] **Step 6 : Lancer la suite du viewer**

Run: `python -m pytest tests/test_island_viewer.py -q`
Expected: PASS (13 tests).

- [ ] **Step 7 : Commit**

```bash
git add gui/circuit_viewer.py tests/test_island_viewer.py
git commit -m "feat(viewer): marges sur les labels de net (decolle des symboles et AOP)"
```

---

### Task 4 : Vérification visuelle + suite complète

**Files:**
- Utilise: `debug_render_ilots.py` (existant), aucun fichier modifié.

**Interfaces:**
- Consumes: `_build_island_model`, `_make_island_fig` (modifiés par les tâches 1-3).
- Produces: aucun code ; PNG de contrôle dans `build_rebuild/ilots_render/` + confirmation suite verte.

- [ ] **Step 1 : Lancer la suite complète**

Run: `python -m pytest -q`
Expected: PASS (tous les tests, dont les 13 du viewer).

- [ ] **Step 2 : Re-rendre l'îlot dense**

Run: `python debug_render_ilots.py circuits_industriels/signal_conditioning.xml`
Expected: « 4 ilots » imprimés ; PNG régénérés.

- [ ] **Step 3 : Inspecter le rendu**

Ouvrir `build_rebuild/ilots_render/00_Îlot_1_-_comparaison.png` et vérifier visuellement :
- aucun texte ne chevauche un autre texte ni un symbole (`Z2`/`Z3`, `D4`/`Z4`, `Z10`/`Z11` séparés) ;
- les Z reliant la même paire de colonnes sont empilés verticalement et alignés (plus de diagonale continue) ;
- les noms de net (`NET12`, `NET13`…) ne mordent plus sur les symboles ni sur les triangles AOP.

Comparer avec le petit îlot `01_Îlot_2_-_alimentation_AVCC.png` (doit rester aussi propre qu'avant — non-régression).

- [ ] **Step 4 : Commit éventuel des PNG de contrôle**

Si l'inspection est concluante et que l'on souhaite garder une trace :

```bash
git add build_rebuild/ilots_render
git commit -m "chore(viewer): rendus de controle des ilots assainis"
```

(Sinon, ne rien committer — `build_rebuild/` est un dossier de travail.)
