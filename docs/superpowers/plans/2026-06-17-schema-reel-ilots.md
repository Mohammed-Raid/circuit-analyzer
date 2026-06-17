# Schema Reel Des Ilots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un bouton permettant d'afficher chaque ilot fonctionnel comme un schema electronique reel.

**Architecture:** `gui.circuit_viewer` expose un modele pur `_build_island_model()` et un visualiseur `show_island()`. `gui.tab_analyze` passe le graphe aux sections d'ilots et ajoute un bouton d'ouverture. Les tests couvrent le modele de schema.

**Tech Stack:** Python 3, CustomTkinter, matplotlib TkAgg, schemdraw, pytest.

## Global Constraints

- Pas de nouvelle dependance.
- Les rails restent visibles comme labels mais ne fusionnent pas les ilots.
- Le rendu doit avoir un fallback lisible.
- Le build PyInstaller doit passer.

---

### Task 1: Modele de schema d'ilot

**Files:**
- Modify: `gui/circuit_viewer.py`
- Test: `tests/test_island_viewer.py`

**Interfaces:**
- Produces: `_build_island_model(ilot: dict, graph, comp_info: dict) -> dict`

- [ ] **Step 1: Write failing test**

Create `tests/test_island_viewer.py` with a graph containing `R1`, `C1`, `U1` and an ilot `{'composants': ['R1', 'C1']}`. Assert the model contains exactly `R1`, `C1`, internal net `OUT`, rail `GND`, and component-net links.

- [ ] **Step 2: Run red test**

Run `pytest tests/test_island_viewer.py -q`. Expected failure: cannot import `_build_island_model`.

- [ ] **Step 3: Implement model**

Add `_build_island_model` to `gui/circuit_viewer.py`. It filters refs to the ilot, reads pins from `comp_info` or `graph.graph['components']`, separates rails using `is_ground_net`, `is_power_net`, `is_protective_earth_net`, and returns sorted components/nets/links.

- [ ] **Step 4: Run green test**

Run `pytest tests/test_island_viewer.py -q`. Expected: pass.

### Task 2: Fenetre de schema d'ilot

**Files:**
- Modify: `gui/circuit_viewer.py`

**Interfaces:**
- Consumes: `_build_island_model(...)`
- Produces: `show_island(ilot: dict, graph, comp_info: dict, parent=None) -> None`

- [ ] **Step 1: Add drawer**

Implement `show_island` and `_make_island_fig`. Use a CTkToplevel like `show_circuit`, draw components as schemdraw elements between net labels, and show text fallback on exception.

- [ ] **Step 2: Smoke import**

Run `python -c "from gui.circuit_viewer import show_island, _build_island_model; print('ok')"`. Expected: `ok`.

### Task 3: Brancher l'onglet Analyse

**Files:**
- Modify: `gui/tab_analyze.py`

**Interfaces:**
- Consumes: `show_island(ilot, graph, comp_info, parent=None)`

- [ ] **Step 1: Pass graph to sections**

Change `_render_islands` to call `_IslandSection(self._results_view, ilot, results, self._graph, self._comp_info, self.frame)`.

- [ ] **Step 2: Add button**

Update `_IslandSection.__init__` to store ilot/graph/comp_info/parent and add a "Schema ilot" button. Its command calls `show_island`.

- [ ] **Step 3: Run targeted tests**

Run `pytest tests/test_island_viewer.py tests/test_ilots.py -q`. Expected: pass.

### Task 4: Verification, commit, build

**Files:**
- Modify: tracked changes from Tasks 1-3

- [ ] **Step 1: Run all tests**

Run `pytest -q`. Expected: all pass.

- [ ] **Step 2: Commit**

Commit with `feat(gui): show functional islands as schematics`.

- [ ] **Step 3: Rebuild**

Run `python tools/build_exe.py`. If `dist/AnalyseurCircuits` is locked by a running app, close that process and rerun.
