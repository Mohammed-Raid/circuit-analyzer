# Export XML organisé par circuit détecté — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** L'export XML (`components_to_xml`) regroupe les composants par circuit détecté en blocs visuels organisés, avec des symboles d'alimentation globaux, au lieu d'une grille naïve.

**Architecture:** Une fonction pure `_layout_groups` mappe chaque composant à un bloc (un par pattern détecté, « Divers » pour le reste). `_place_blocks` calcule les coordonnées absolues. `components_to_xml` gagne un paramètre optionnel `results` (rétrocompatible : `None` = ancienne grille). Seules les coordonnées `CtrIem` changent ; la connectivité (nets, symboles d'alim) reste identique, donc le round-trip est préservé par construction.

**Tech Stack:** Python 3, pytest, modules existants `circuit_analyzer.{xml_generator, xml_parser, matcher, graph_builder, parser}`.

---

## File Structure

- **Modify** `circuit_analyzer/xml_generator.py` :
  - Ajouter une dataclass `_Block(label: str, comps: list)`.
  - Ajouter `_layout_groups(components, results) -> list[_Block]` (fonction pure).
  - Ajouter `_place_blocks(blocks) -> dict[str, tuple[int, int]]` (positions par ref).
  - Étendre `components_to_xml(components, results=None)`.
- **Modify** `gui/tab_analyze.py:287` : passer `results=self._results` à `components_to_xml`.
- **Modify** `tests/test_xml_generator.py` : ajouter 5 tests (layout, divers, rétrocompat, round-trip groupé, placement).

Constantes de layout réutilisées : `COL_W = 320`, `ROW_H = 260` (déjà dans `components_to_xml`). Nouvelle : `BLOCKS_PER_ROW = 3`, `BLOCK_GAP = 160`.

---

## Task 1: `_Block` dataclass + `_layout_groups` (fonction pure)

**Files:**
- Modify: `circuit_analyzer/xml_generator.py` (ajouter après la classe `BoardSCHGenerator`, avant `components_to_xml`)
- Test: `tests/test_xml_generator.py`

- [ ] **Step 1: Write the failing test**

Ajouter dans `tests/test_xml_generator.py` :

```python
from circuit_analyzer.xml_generator import _layout_groups, _Block


def test_layout_groups_one_block_per_pattern():
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    results = [{"circuit_type": "Amplificateur inverseur (AOP)",
                "components": ["U1", "R1", "R2"], "nodes": []}]
    blocks = _layout_groups(comps, results)
    assert len(blocks) == 1
    assert blocks[0].label == "Amplificateur inverseur (AOP)"
    assert {c.ref for c in blocks[0].comps} == {"U1", "R1", "R2"}


def test_layout_groups_unclassified_go_to_divers():
    comps = [
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("L1", "L", {"1": "A", "2": "B"}),   # not in any pattern
    ]
    results = [{"circuit_type": "Amplificateur inverseur (AOP)",
                "components": ["U1", "R1", "R2"], "nodes": []}]
    blocks = _layout_groups(comps, results)
    labels = [b.label for b in blocks]
    assert "Divers" in labels
    divers = next(b for b in blocks if b.label == "Divers")
    assert {c.ref for c in divers.comps} == {"L1"}
    # Divers is always last
    assert blocks[-1].label == "Divers"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_xml_generator.py::test_layout_groups_one_block_per_pattern tests/test_xml_generator.py::test_layout_groups_unclassified_go_to_divers -v`
Expected: FAIL with `ImportError: cannot import name '_layout_groups'`

- [ ] **Step 3: Write minimal implementation**

Dans `circuit_analyzer/xml_generator.py`, ajouter après la classe `BoardSCHGenerator` (avant `def components_to_xml`) :

```python
@dataclass
class _Block:
    """A visual group of components sharing a detected circuit pattern."""
    label: str
    comps: list   # list[Component]


def _layout_groups(components, results) -> List["_Block"]:
    """Group drawable components into blocks, one per detected pattern.

    Components not claimed by any pattern go into a final "Divers" block.
    Pure function: no XML, no side effects. Order is deterministic — patterns
    in the order they appear in `results`, then "Divers" last.
    """
    comp_by_ref = {c.ref: c for c in components
                   if BoardSCHGenerator._TYPE_TO_SHAPE.get(c.type) is not None}

    # ref → circuit_type (first pattern that claims it; matcher guarantees
    # exclusivity, so each ref appears in at most one result anyway)
    type_of_ref: dict[str, str] = {}
    for r in results or []:
        for ref in r["components"]:
            type_of_ref.setdefault(ref, r["circuit_type"])

    # Build blocks preserving first-seen pattern order
    blocks: list[_Block] = []
    block_by_label: dict[str, _Block] = {}
    for r in results or []:
        label = r["circuit_type"]
        if label not in block_by_label:
            b = _Block(label, [])
            block_by_label[label] = b
            blocks.append(b)
        for ref in r["components"]:
            if ref in comp_by_ref:
                block_by_label[label].comps.append(comp_by_ref[ref])

    # Unclassified drawable components → "Divers"
    divers = [c for ref, c in comp_by_ref.items() if ref not in type_of_ref]
    if divers:
        blocks.append(_Block("Divers", divers))

    return blocks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_xml_generator.py::test_layout_groups_one_block_per_pattern tests/test_xml_generator.py::test_layout_groups_unclassified_go_to_divers -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/xml_generator.py tests/test_xml_generator.py
git commit -m "feat: add _layout_groups to group components by detected pattern"
```

---

## Task 2: `_place_blocks` — coordonnées absolues par bloc

**Files:**
- Modify: `circuit_analyzer/xml_generator.py` (ajouter après `_layout_groups`)
- Test: `tests/test_xml_generator.py`

- [ ] **Step 1: Write the failing test**

```python
from circuit_analyzer.xml_generator import _place_blocks


def test_place_blocks_groups_are_spatially_separated():
    # Two blocks: components within a block are closer to each other than to
    # the other block's components.
    a = [Component("R1", "R", {"1": "X", "2": "Y"}),
         Component("R2", "R", {"1": "Y", "2": "Z"})]
    b = [Component("R3", "R", {"1": "P", "2": "Q"})]
    blocks = [_Block("Filtre", a), _Block("Divers", b)]
    pos = _place_blocks(blocks)
    # every ref placed
    assert set(pos) == {"R1", "R2", "R3"}
    # R1 and R2 (same block) share the same y row; R3 is on a different position
    assert pos["R1"][1] == pos["R2"][1]
    assert pos["R3"] != pos["R1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_xml_generator.py::test_place_blocks_groups_are_spatially_separated -v`
Expected: FAIL with `ImportError: cannot import name '_place_blocks'`

- [ ] **Step 3: Write minimal implementation**

Ajouter après `_layout_groups` dans `circuit_analyzer/xml_generator.py` :

```python
# Block-grid layout constants
_BLOCKS_PER_ROW = 3
_BLOCK_GAP = 160          # horizontal gap between blocks
_COMP_W = 320             # horizontal spacing of components inside a block
_BLOCK_ROW_H = 260        # vertical spacing between block rows


def _place_blocks(blocks) -> Dict[str, Tuple[int, int]]:
    """Compute the absolute (x, y) of every component, grouped by block.

    Blocks are laid on a grid (_BLOCKS_PER_ROW per row). Inside a block the
    components are aligned horizontally. Returns ref → (x, y).
    """
    pos: Dict[str, Tuple[int, int]] = {}
    x_cursor = 250
    y_cursor = 250
    row_count = 0
    for blk in blocks:
        # place this block's components horizontally from x_cursor
        for j, comp in enumerate(blk.comps):
            pos[comp.ref] = (x_cursor + j * _COMP_W, y_cursor)
        # advance the cursor past this block (its width + a gap)
        block_w = max(len(blk.comps), 1) * _COMP_W
        x_cursor += block_w + _BLOCK_GAP
        row_count += 1
        if row_count >= _BLOCKS_PER_ROW:
            row_count = 0
            x_cursor = 250
            y_cursor += _BLOCK_ROW_H
    return pos
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_xml_generator.py::test_place_blocks_groups_are_spatially_separated -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/xml_generator.py tests/test_xml_generator.py
git commit -m "feat: add _place_blocks to lay grouped blocks on a grid"
```

---

## Task 3: Brancher `results` dans `components_to_xml` (rétrocompatible)

**Files:**
- Modify: `circuit_analyzer/xml_generator.py:416-484` (fonction `components_to_xml`)
- Test: `tests/test_xml_generator.py`

- [ ] **Step 1: Write the failing test**

```python
def test_components_to_xml_backward_compatible_without_results():
    # No results → must produce identical output to the legacy grid path.
    comps = [
        Component("R1", "R", {"1": "A", "2": "B"}),
        Component("C1", "C", {"1": "B", "2": "GND"}),
    ]
    xml_a = components_to_xml(comps)
    xml_b = components_to_xml(comps, results=None)
    assert xml_a == xml_b


def test_components_to_xml_grouped_roundtrip_preserved():
    # With results, the round-trip must still detect the same patterns:
    # grouping changes only coordinates, never connectivity.
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
        Component("R3", "R", {"1": "NET_B", "2": "NET_A"}),
        Component("C1", "C", {"1": "NET_B", "2": "GND"}),
        Component("F1", "F", {"1": "LINE", "2": "NET_A"}),
    ]
    results = match_patterns(build_graph(comps))
    xml = components_to_xml(comps, results=results)
    back = _xml_to_components(xml)
    roundtrip = sorted(r["circuit_type"] for r in match_patterns(build_graph(back)))
    orig = sorted(r["circuit_type"] for r in match_patterns(build_graph(comps)))
    assert orig == roundtrip
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_xml_generator.py::test_components_to_xml_backward_compatible_without_results tests/test_xml_generator.py::test_components_to_xml_grouped_roundtrip_preserved -v`
Expected: FAIL — `test_components_to_xml_grouped_roundtrip_preserved` fails with `TypeError: components_to_xml() got an unexpected keyword argument 'results'`

- [ ] **Step 3: Write minimal implementation**

Modifier la signature et l'étape 1 de `components_to_xml` dans `circuit_analyzer/xml_generator.py`. Remplacer la définition actuelle (ligne 416) :

```python
def components_to_xml(components) -> str:
```

par :

```python
def components_to_xml(components, results=None) -> str:
```

Mettre à jour le docstring en ajoutant cette phrase à la fin :

```python
    When `results` (the output of match_patterns) is given, components are laid
    out grouped by detected circuit pattern instead of on a naive grid; passing
    None keeps the legacy grid layout. Only coordinates change — connectivity is
    unchanged, so the round-trip still detects the same patterns.
```

Puis remplacer le bloc « Step 1: place every component on a grid » (lignes ~426-442) :

```python
    # ── Step 1: place every component on a grid ───────────────────────────────
    COL_W, ROW_H = 320, 260
    PER_ROW = 4
    cid_of_ref: dict[str, int] = {}
    # library_pin → shape_pin map per ref
    pinmap_of_ref: dict[str, dict] = {}

    for i, comp in enumerate(components):
        spec = BoardSCHGenerator._TYPE_TO_SHAPE.get(comp.type)
        if spec is None:
            continue   # unknown type → skip (can't draw a shape for it)
        board_name, pinmap = spec
        x = 250 + (i % PER_ROW) * COL_W
        y = 250 + (i // PER_ROW) * ROW_H
        cid = gen.add(board_name, comp.value, x=x, y=y)
        cid_of_ref[comp.ref] = cid
        pinmap_of_ref[comp.ref] = pinmap
```

par :

```python
    # ── Step 1: choose component positions ────────────────────────────────────
    COL_W, ROW_H = 320, 260
    PER_ROW = 4
    cid_of_ref: dict[str, int] = {}
    # library_pin → shape_pin map per ref
    pinmap_of_ref: dict[str, dict] = {}

    if results:
        # Grouped layout: one block per detected pattern, "Divers" for the rest.
        grouped_pos = _place_blocks(_layout_groups(components, results))
    else:
        grouped_pos = None

    for i, comp in enumerate(components):
        spec = BoardSCHGenerator._TYPE_TO_SHAPE.get(comp.type)
        if spec is None:
            continue   # unknown type → skip (can't draw a shape for it)
        board_name, pinmap = spec
        if grouped_pos is not None and comp.ref in grouped_pos:
            x, y = grouped_pos[comp.ref]
        else:
            x = 250 + (i % PER_ROW) * COL_W
            y = 250 + (i // PER_ROW) * ROW_H
        cid = gen.add(board_name, comp.value, x=x, y=y)
        cid_of_ref[comp.ref] = cid
        pinmap_of_ref[comp.ref] = pinmap
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_xml_generator.py::test_components_to_xml_backward_compatible_without_results tests/test_xml_generator.py::test_components_to_xml_grouped_roundtrip_preserved -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/xml_generator.py tests/test_xml_generator.py
git commit -m "feat: components_to_xml lays out by detected pattern when results given"
```

---

## Task 4: Brancher l'export GUI sur le layout groupé

**Files:**
- Modify: `gui/tab_analyze.py:287`

- [ ] **Step 1: Inspect the current call**

Run: `python -m pytest tests/ -q` (baseline — tout doit passer avant de toucher le GUI)
Expected: PASS (suite complète verte)

- [ ] **Step 2: Modify the export call**

Dans `gui/tab_analyze.py`, remplacer la ligne 287 :

```python
            xml = components_to_xml(self._comps)
```

par :

```python
            xml = components_to_xml(self._comps, results=self._results)
```

(`self._results` est déjà rempli dans `_analyze` à la ligne 219, et vaut `[]` si
aucune analyse — `components_to_xml` retombe alors sur la grille, donc sûr.)

- [ ] **Step 3: Verify nothing broke**

Run: `python -m pytest tests/ -q`
Expected: PASS (même nombre de tests qu'avant, +5 nouveaux)

- [ ] **Step 4: Smoke-test the export end to end**

Run:
```bash
python -c "from circuit_analyzer.parser import parse_file; from circuit_analyzer.graph_builder import build_graph; from circuit_analyzer.matcher import match_patterns; from circuit_analyzer.xml_generator import components_to_xml; c=parse_file('simulations/ldo_regulator.txt'); r=match_patterns(build_graph(c)); xml=components_to_xml(c, results=r); print('OK', len(xml), 'chars,', len(r), 'patterns')"
```
Expected: `OK <n> chars, <m> patterns` sans exception (si `simulations/ldo_regulator.txt` absent, choisir un autre fichier de `simulations/`).

- [ ] **Step 5: Commit**

```bash
git add gui/tab_analyze.py
git commit -m "feat: GUI exports grouped XML layout using analysis results"
```

---

## Task 5: Régression complète + circuits industriels groupés

**Files:**
- Modify: `netlist_to_xml.py:31` (passer `results` pour bénéficier du regroupement)

- [ ] **Step 1: Pass results in the batch converter**

Dans `netlist_to_xml.py`, fonction `convert` (ligne ~30-31), remplacer :

```python
    comps = parse_file(txt_path)
    xml = components_to_xml(comps)
```

par :

```python
    comps = parse_file(txt_path)
    xml = components_to_xml(comps, results=match_patterns(build_graph(comps)))
```

(`match_patterns` et `build_graph` sont déjà importés dans ce fichier.)

- [ ] **Step 2: Re-run the industrial conversion + verify no pattern loss**

Run: `python netlist_to_xml.py`
Expected: `12/12 circuits industriels convertis` (même décompte qu'avant), aucune
exception. Le regroupement ne change que les positions, donc le nombre de
patterns par fichier reste inchangé.

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: PASS — tous les tests verts (les 156 existants + 5 nouveaux).

- [ ] **Step 4: Commit**

```bash
git add netlist_to_xml.py circuits_industriels/
git commit -m "feat: industrial XML batch uses grouped layout"
```

---

## Self-Review

**Spec coverage:**
- Décision 1 (regroupement par circuit détecté) → Tasks 1 (`_layout_groups`) + 2 (`_place_blocks`) + 3 (branchement).
- Décision 2 (symboles d'alim globaux) → inchangé, couvert par la logique existante de `components_to_xml` (étape 3 de la fonction, non modifiée) ; le round-trip Task 3 le valide.
- Bloc « Divers » → Task 1, test `test_layout_groups_unclassified_go_to_divers`.
- Rétrocompatibilité `results=None` → Task 3, test `test_components_to_xml_backward_compatible_without_results`.
- Round-trip préservé → Task 3, test `test_components_to_xml_grouped_roundtrip_preserved`.
- Branchement GUI → Task 4. Batch industriel → Task 5.

**Placeholder scan:** aucun TBD/TODO ; chaque step de code montre le code complet.

**Type consistency:** `_Block(label, comps)` défini en Task 1, utilisé identiquement en Tasks 2/3. `_layout_groups(components, results)` et `_place_blocks(blocks) -> dict[ref,(x,y)]` cohérents entre définition (Tasks 1/2) et usage (Task 3). `components_to_xml(components, results=None)` cohérent entre Tasks 3, 4, 5.
