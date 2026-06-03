# Interface Tkinter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter une interface graphique Tkinter permettant à un technicien d'analyser des circuits, gérer les types de composants et définir des circuits personnalisés — sans toucher au code Python.

**Architecture:** Fenêtre unique avec 3 onglets (Analyser, Circuits, Composants). Les onglets appellent les modules existants. Les circuits personnalisés sont définis via un formulaire et sauvegardés dans `custom_circuits.json`, interprétés par `CustomCircuitPattern`. Le matcher charge les patterns personnalisés dynamiquement à chaque appel.

**Tech Stack:** Python 3.10+, tkinter (stdlib), json (stdlib), modules existants du projet

---

## File Map

| Fichier | Rôle |
|---|---|
| `app.py` | Point d'entrée : `python app.py` |
| `gui/__init__.py` | Package GUI |
| `gui/app_window.py` | Fenêtre principale + ttk.Notebook |
| `gui/tab_analyze.py` | Onglet Analyser |
| `gui/tab_circuits.py` | Onglet Circuits |
| `gui/tab_components.py` | Onglet Composants |
| `custom_circuits/__init__.py` | Package |
| `custom_circuits/loader.py` | load/save custom_circuits.json + CustomCircuitPattern |
| `circuit_analyzer/matcher.py` | Modifié : charge les patterns personnalisés |
| `tests/test_custom_circuits.py` | Tests unitaires pour CustomCircuitPattern |

---

## Task 1: Custom Circuits Package

**Files:**
- Create: `custom_circuits/__init__.py`
- Create: `custom_circuits/loader.py`
- Create: `tests/test_custom_circuits.py`

- [ ] **Step 1: Write failing tests** — créer `tests/test_custom_circuits.py`

```python
import json, os, tempfile, pytest
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from custom_circuits.loader import (
    load_custom_circuits, save_custom_circuits,
    CustomCircuitPattern, get_custom_patterns, CONDITION_LABELS
)


def _tmp_json(data):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(data, f)
    f.close()
    return f.name


def test_load_empty_when_file_missing():
    assert load_custom_circuits('nonexistent_file.json') == []


def test_save_and_load_roundtrip():
    circuits = [{'name': 'Test', 'components': ['R', 'C'], 'conditions': []}]
    path = tempfile.mktemp(suffix='.json')
    save_custom_circuits(circuits, path)
    loaded = load_custom_circuits(path)
    os.unlink(path)
    assert loaded == circuits


def test_custom_pattern_name():
    p = CustomCircuitPattern({'name': 'Mon circuit', 'components': ['R'], 'conditions': []})
    assert p.name == 'Mon circuit'


def test_custom_pattern_matches_required_types():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'GND'}, '100nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({'name': 'RC', 'components': ['R', 'C'], 'conditions': []})
    matches = p.match(G)
    assert len(matches) == 1
    assert 'R1' in matches[0]['components']
    assert 'C1' in matches[0]['components']


def test_custom_pattern_no_match_when_type_missing():
    comps = [Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k')]
    G = build_graph(comps)
    p = CustomCircuitPattern({'name': 'RC', 'components': ['R', 'C'], 'conditions': []})
    assert p.match(G) == []


def test_condition_c_connected_to_gnd():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'GND'}, '100nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Filtre', 'components': ['R', 'C'],
        'conditions': ['C connecté à GND']
    })
    assert len(p.match(G)) == 1


def test_condition_c_connected_to_gnd_fails_when_not():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'NET_C'}, '100nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Filtre', 'components': ['R', 'C'],
        'conditions': ['C connecté à GND']
    })
    assert p.match(G) == []


def test_condition_emitter_to_gnd():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_BASE'}, '1k'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Switch', 'components': ['Q', 'R'],
        'conditions': ['Émetteur/Source à GND']
    })
    assert len(p.match(G)) == 1


def test_condition_labels_list():
    assert 'C connecté à GND' in CONDITION_LABELS
    assert 'Émetteur/Source à GND' in CONDITION_LABELS
    assert len(CONDITION_LABELS) >= 5


def test_get_custom_patterns_returns_empty_when_no_file():
    patterns = get_custom_patterns('nonexistent.json')
    assert patterns == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_custom_circuits.py -v
```

Expected: `ImportError` — module not found

- [ ] **Step 3: Create `custom_circuits/__init__.py`** — fichier vide

- [ ] **Step 4: Create `custom_circuits/loader.py`**

```python
import json
from pathlib import Path
from circuit_analyzer.patterns.base import Pattern, is_gnd, is_power

CUSTOM_CIRCUITS_FILE = 'custom_circuits.json'

CONDITION_LABELS = [
    "C connecté à GND",
    "R en série",
    "R vers alimentation",
    "Émetteur/Source à GND",
    "Feedback OUT→IN-",
]


def load_custom_circuits(path: str = CUSTOM_CIRCUITS_FILE) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def save_custom_circuits(circuits: list[dict], path: str = CUSTOM_CIRCUITS_FILE) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(circuits, f, ensure_ascii=False, indent=2)


def get_custom_patterns(path: str = CUSTOM_CIRCUITS_FILE) -> list['CustomCircuitPattern']:
    return [CustomCircuitPattern(d) for d in load_custom_circuits(path)]


class CustomCircuitPattern(Pattern):
    def __init__(self, definition: dict):
        self._name = definition['name']
        self._required_types = set(definition.get('components', []))
        self._conditions = list(definition.get('conditions', []))

    @property
    def name(self) -> str:
        return self._name

    def match(self, graph) -> list[dict]:
        all_comps = graph.graph.get('components', {})
        found = {ref: comp for ref, comp in all_comps.items()
                 if comp.type in self._required_types}

        if not found:
            return []

        found_types = {comp.type for comp in found.values()}
        if not self._required_types.issubset(found_types):
            return []

        for condition in self._conditions:
            if not self._check_condition(condition, graph, found):
                return []

        return [{'components': list(found.keys()), 'nodes': []}]

    def _check_condition(self, condition: str, graph, found: dict) -> bool:
        if condition == "C connecté à GND":
            for u, v, d in graph.edges(data=True):
                if d['type'] == 'C' and d['ref'] in found:
                    if is_gnd(u) or is_gnd(v):
                        return True
            return False

        if condition == "R vers alimentation":
            for u, v, d in graph.edges(data=True):
                if d['type'] == 'R' and d['ref'] in found:
                    if is_power(u) or is_power(v):
                        return True
            return False

        if condition == "Émetteur/Source à GND":
            for ref, comp in found.items():
                if comp.type == 'Q':
                    e = comp.pins.get('E', '')
                    if e and is_gnd(e):
                        return True
                elif comp.type == 'M':
                    s = comp.pins.get('S', '')
                    if s and is_gnd(s):
                        return True
            return False

        if condition == "Feedback OUT→IN-":
            for ref, comp in found.items():
                if comp.type == 'U':
                    inm = comp.pins.get('IN-')
                    out = comp.pins.get('OUT')
                    if inm and out:
                        for u, v, d in graph.edges(inm, data=True):
                            other = v if u == inm else u
                            if other == out:
                                return True
            return False

        if condition == "R en série":
            r_refs = {ref for ref, comp in found.items() if comp.type == 'R'}
            other_comps = {ref: comp for ref, comp in found.items() if comp.type != 'R'}
            for r_ref in r_refs:
                r_nets = set(found[r_ref].pins.values())
                for o_comp in other_comps.values():
                    if r_nets & set(o_comp.pins.values()):
                        return True
            return False

        return True
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_custom_circuits.py -v
```

Expected: 10 passed

- [ ] **Step 6: Run all tests**

```bash
pytest tests/ -q
```

Expected: 79 passed (69 + 10)

- [ ] **Step 7: Commit**

```bash
git add custom_circuits/ tests/test_custom_circuits.py
git commit -m "feat: add custom circuits package with JSON persistence and pattern matching"
```

---

## Task 2: Update Matcher

**Files:**
- Modify: `circuit_analyzer/matcher.py`
- Modify: `tests/test_matcher.py`

- [ ] **Step 1: Add failing test** (append à `tests/test_matcher.py`)

```python
def test_matcher_loads_custom_patterns(tmp_path):
    import json
    custom = [{'name': 'Circuit test', 'components': ['R', 'C'], 'conditions': []}]
    (tmp_path / 'custom_circuits.json').write_text(json.dumps(custom), encoding='utf-8')

    import os
    orig = os.getcwd()
    os.chdir(tmp_path)
    try:
        comps = [
            Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
            Component('C1', 'C', {'1': 'NET_B', '2': 'GND'}, '100nF'),
        ]
        results = match_patterns(build_graph(comps))
        types = [r['circuit_type'] for r in results]
        assert 'Circuit test' in types
    finally:
        os.chdir(orig)
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_matcher.py::test_matcher_loads_custom_patterns -v
```

Expected: FAIL — 'Circuit test' not in types

- [ ] **Step 3: Update `circuit_analyzer/matcher.py`**

```python
import networkx as nx
from circuit_analyzer.patterns.basic_circuits import ALL_PATTERNS as BASIC_PATTERNS
from circuit_analyzer.patterns.transistor import TRANSISTOR_PATTERNS
from circuit_analyzer.patterns.opamp import OPAMP_PATTERNS

_BUILTIN_PATTERNS = BASIC_PATTERNS + TRANSISTOR_PATTERNS + OPAMP_PATTERNS


def match_patterns(graph: nx.MultiGraph) -> list[dict]:
    try:
        from custom_circuits.loader import get_custom_patterns
        all_patterns = _BUILTIN_PATTERNS + get_custom_patterns()
    except ImportError:
        all_patterns = _BUILTIN_PATTERNS

    results = []
    for pattern in all_patterns:
        for match in pattern.match(graph):
            results.append({
                'circuit_type': pattern.name,
                'components': match['components'],
                'nodes': match['nodes'],
            })
    return results
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/ -q
```

Expected: 80 passed

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/matcher.py tests/test_matcher.py
git commit -m "feat: matcher loads custom circuit patterns from custom_circuits.json"
```

---

## Task 3: GUI Package + App Window

**Files:**
- Create: `gui/__init__.py`
- Create: `gui/app_window.py`

- [ ] **Step 1: Create `gui/__init__.py`** — fichier vide

- [ ] **Step 2: Create `gui/app_window.py`**

```python
import tkinter as tk
from tkinter import ttk
from gui.tab_analyze import TabAnalyze
from gui.tab_circuits import TabCircuits
from gui.tab_components import TabComponents


class AppWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Circuit Analyzer")
        self.root.geometry("850x620")
        self.root.minsize(700, 500)
        self._build()

    def _build(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)

        tab_analyze = TabAnalyze(notebook)
        tab_circuits = TabCircuits(notebook)
        tab_components = TabComponents(notebook, on_save=tab_circuits.refresh_component_list)

        notebook.add(tab_analyze.frame, text='  Analyser  ')
        notebook.add(tab_circuits.frame, text='  Circuits  ')
        notebook.add(tab_components.frame, text='  Composants  ')

    def run(self):
        self.root.mainloop()
```

- [ ] **Step 3: Verify imports don't crash** (les onglets n'existent pas encore — l'erreur doit être ImportError, pas autre chose)

```bash
python -c "import gui.app_window" 2>&1 | head -5
```

Expected: `ModuleNotFoundError: No module named 'gui.tab_analyze'`

- [ ] **Step 4: Commit**

```bash
git add gui/__init__.py gui/app_window.py
git commit -m "feat: add GUI package and main app window with notebook"
```

---

## Task 4: Onglet Analyser

**Files:**
- Create: `gui/tab_analyze.py`

- [ ] **Step 1: Create `gui/tab_analyze.py`**

```python
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from circuit_analyzer.parser import parse_file
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.reporter import generate


class TabAnalyze:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self._file_path = tk.StringVar()
        self._report_content = ''
        self._build()

    def _build(self):
        file_frame = ttk.Frame(self.frame)
        file_frame.pack(fill='x', padx=10, pady=(10, 5))
        ttk.Label(file_frame, text="Fichier :").pack(side='left')
        ttk.Entry(file_frame, textvariable=self._file_path, width=50).pack(side='left', padx=5)
        ttk.Button(file_frame, text="Parcourir", command=self._browse).pack(side='left')

        ttk.Button(self.frame, text="  Analyser  ", command=self._analyze).pack(pady=5)

        report_frame = ttk.Frame(self.frame)
        report_frame.pack(fill='both', expand=True, padx=10)
        self._text = tk.Text(report_frame, state='disabled', wrap='word',
                              font=('Courier', 10))
        sb = ttk.Scrollbar(report_frame, command=self._text.yview)
        self._text.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._text.pack(side='left', fill='both', expand=True)

        ttk.Button(self.frame, text="Sauvegarder le rapport",
                   command=self._save).pack(pady=(5, 10))

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Choisir un fichier circuit",
            filetypes=[("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")]
        )
        if path:
            self._file_path.set(path)

    def _analyze(self):
        path = self._file_path.get().strip()
        if not path:
            self._show("Veuillez sélectionner un fichier circuit.")
            return
        try:
            comps = parse_file(path)
            graph = build_graph(comps)
            results = match_patterns(graph)
            all_refs = [c.ref for c in comps]
            report = generate(results, path, len(comps), all_refs=all_refs)
            self._report_content = report
            self._show(report)
        except FileNotFoundError:
            self._show(f"Erreur : fichier introuvable :\n{path}")
        except Exception as e:
            self._show(f"Erreur lors de l'analyse :\n{e}")

    def _save(self):
        if not self._report_content:
            messagebox.showinfo("Information", "Aucun rapport à sauvegarder.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Fichiers texte", "*.txt")],
            title="Sauvegarder le rapport"
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._report_content)
            messagebox.showinfo("Succès", f"Rapport sauvegardé dans :\n{path}")

    def _show(self, text: str):
        self._text.configure(state='normal')
        self._text.delete('1.0', 'end')
        self._text.insert('1.0', text)
        self._text.configure(state='disabled')
```

- [ ] **Step 2: Verify tab_analyze imports correctly**

```bash
python -c "from gui.tab_analyze import TabAnalyze; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add gui/tab_analyze.py
git commit -m "feat: add Analyser tab with file picker, analysis, and report save"
```

---

## Task 5: Onglet Composants

**Files:**
- Create: `gui/tab_components.py`

- [ ] **Step 1: Create `gui/tab_components.py`**

```python
import json
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from circuit_analyzer.component_library.base import COMPONENT_TYPES

LIBRARY_FILE = 'component_library.json'


class TabComponents:
    def __init__(self, parent, on_save=None):
        self.frame = ttk.Frame(parent)
        self._on_save = on_save
        self._custom = {}
        self._current_key = None
        self._pin_vars = []
        self._build()
        self._load()

    def _build(self):
        left = ttk.Frame(self.frame)
        left.pack(side='left', fill='y', padx=(10, 5), pady=10)

        ttk.Label(left, text="Bibliothèque de composants").pack()
        self._listbox = tk.Listbox(left, width=28, height=20)
        self._listbox.pack(fill='y', expand=True)
        self._listbox.bind('<<ListboxSelect>>', self._on_select)

        btn_f = ttk.Frame(left)
        btn_f.pack(fill='x', pady=(5, 0))
        ttk.Button(btn_f, text="+ Nouveau", command=self._new).pack(side='left')
        ttk.Button(btn_f, text="Supprimer", command=self._delete).pack(side='left', padx=5)

        right = ttk.Frame(self.frame)
        right.pack(side='left', fill='both', expand=True, padx=5, pady=10)

        ttk.Label(right, text="Préfixe :").grid(row=0, column=0, sticky='w', pady=4)
        self._prefix_var = tk.StringVar()
        ttk.Entry(right, textvariable=self._prefix_var, width=10).grid(row=0, column=1, sticky='w')

        ttk.Label(right, text="Nom :").grid(row=1, column=0, sticky='w', pady=4)
        self._name_var = tk.StringVar()
        ttk.Entry(right, textvariable=self._name_var, width=30).grid(row=1, column=1, sticky='w')

        ttk.Label(right, text="Broches :").grid(row=2, column=0, sticky='nw', pady=4)
        self._pins_frame = ttk.Frame(right)
        self._pins_frame.grid(row=2, column=1, sticky='w')

        pin_btns = ttk.Frame(right)
        pin_btns.grid(row=3, column=1, sticky='w', pady=4)
        ttk.Button(pin_btns, text="+ Broche", command=self._add_pin).pack(side='left')
        ttk.Button(pin_btns, text="- Broche", command=self._remove_pin).pack(side='left', padx=5)

        ttk.Button(right, text="  Sauvegarder  ", command=self._save).grid(
            row=4, column=0, columnspan=2, pady=10)

    def _load(self):
        self._listbox.delete(0, 'end')
        for key, val in COMPONENT_TYPES.items():
            self._listbox.insert('end', f"{key}  —  {val['name']}")
        for i in range(len(COMPONENT_TYPES)):
            self._listbox.itemconfig(i, foreground='gray')

        self._custom = {}
        p = Path(LIBRARY_FILE)
        if p.exists():
            with open(p, encoding='utf-8') as f:
                data = json.load(f)
            for key, val in data.items():
                if key not in COMPONENT_TYPES:
                    self._custom[key] = val
                    self._listbox.insert('end', f"{key}  —  {val.get('name', '')}")

    def _on_select(self, _=None):
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(COMPONENT_TYPES):
            return
        keys = list(self._custom.keys())
        key = keys[idx - len(COMPONENT_TYPES)]
        self._current_key = key
        val = self._custom[key]
        self._prefix_var.set(key)
        self._name_var.set(val.get('name', ''))
        self._set_pins(val.get('pins', []))

    def _set_pins(self, pins: list):
        for w in self._pins_frame.winfo_children():
            w.destroy()
        self._pin_vars = []
        for pin in pins:
            v = tk.StringVar(value=pin)
            self._pin_vars.append(v)
            ttk.Entry(self._pins_frame, textvariable=v, width=15).pack(anchor='w', pady=1)

    def _add_pin(self):
        v = tk.StringVar()
        self._pin_vars.append(v)
        ttk.Entry(self._pins_frame, textvariable=v, width=15).pack(anchor='w', pady=1)

    def _remove_pin(self):
        if self._pin_vars:
            self._pin_vars.pop()
            children = self._pins_frame.winfo_children()
            if children:
                children[-1].destroy()

    def _new(self):
        self._current_key = None
        self._prefix_var.set('')
        self._name_var.set('')
        self._set_pins([])

    def _delete(self):
        if not self._current_key:
            messagebox.showinfo("Info", "Sélectionnez un composant personnalisé à supprimer.")
            return
        if messagebox.askyesno("Confirmer", f"Supprimer '{self._current_key}' ?"):
            self._custom.pop(self._current_key, None)
            self._current_key = None
            self._write_file()
            self._load()

    def _save(self):
        prefix = self._prefix_var.get().strip().upper()
        name = self._name_var.get().strip()
        pins = [v.get().strip() for v in self._pin_vars if v.get().strip()]

        if not prefix:
            messagebox.showerror("Erreur", "Le préfixe est obligatoire.")
            return
        if prefix in COMPONENT_TYPES:
            messagebox.showerror("Erreur",
                f"Le préfixe '{prefix}' est réservé aux types de base.")
            return
        if not pins:
            messagebox.showerror("Erreur", "Au moins une broche est requise.")
            return

        if self._current_key and self._current_key != prefix:
            self._custom.pop(self._current_key, None)

        self._custom[prefix] = {'name': name, 'pins': pins}
        self._current_key = prefix
        self._write_file()
        self._load()
        if self._on_save:
            self._on_save()
        messagebox.showinfo("Succès", f"Composant '{prefix}' sauvegardé.")

    def _write_file(self):
        with open(LIBRARY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._custom, f, ensure_ascii=False, indent=2)

    def refresh_component_list(self):
        pass
```

- [ ] **Step 2: Verify import**

```bash
python -c "from gui.tab_components import TabComponents; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add gui/tab_components.py
git commit -m "feat: add Composants tab for managing custom component types"
```

---

## Task 6: Onglet Circuits

**Files:**
- Create: `gui/tab_circuits.py`

- [ ] **Step 1: Create `gui/tab_circuits.py`**

```python
import tkinter as tk
from tkinter import ttk, messagebox
from circuit_analyzer.component_library.loader import load_library
from circuit_analyzer.patterns.basic_circuits import ALL_PATTERNS as BASIC_PATTERNS
from circuit_analyzer.patterns.transistor import TRANSISTOR_PATTERNS
from circuit_analyzer.patterns.opamp import OPAMP_PATTERNS
from custom_circuits.loader import (
    load_custom_circuits, save_custom_circuits, CONDITION_LABELS
)

_BASE_PATTERN_NAMES = [p.name for p in BASIC_PATTERNS + TRANSISTOR_PATTERNS + OPAMP_PATTERNS]


class TabCircuits:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self._custom = []
        self._current_idx = None
        self._comp_vars = {}
        self._cond_vars = {}
        self._build()
        self._load()

    def _build(self):
        left = ttk.Frame(self.frame)
        left.pack(side='left', fill='y', padx=(10, 5), pady=10)

        ttk.Label(left, text="Circuits").pack()
        self._listbox = tk.Listbox(left, width=30, height=20)
        self._listbox.pack(fill='y', expand=True)
        self._listbox.bind('<<ListboxSelect>>', self._on_select)

        btn_f = ttk.Frame(left)
        btn_f.pack(fill='x', pady=(5, 0))
        ttk.Button(btn_f, text="+ Nouveau", command=self._new).pack(side='left')
        ttk.Button(btn_f, text="Supprimer", command=self._delete).pack(side='left', padx=5)

        right = ttk.Frame(self.frame)
        right.pack(side='left', fill='both', expand=True, padx=5, pady=10)

        ttk.Label(right, text="Nom du circuit :").grid(row=0, column=0, sticky='w', pady=4)
        self._name_var = tk.StringVar()
        ttk.Entry(right, textvariable=self._name_var, width=35).grid(row=0, column=1, sticky='w')

        ttk.Label(right, text="Composants requis :").grid(row=1, column=0, sticky='nw', pady=4)
        comp_outer = ttk.Frame(right)
        comp_outer.grid(row=1, column=1, sticky='w')
        comp_canvas = tk.Canvas(comp_outer, width=280, height=180)
        comp_sb = ttk.Scrollbar(comp_outer, orient='vertical', command=comp_canvas.yview)
        self._comp_frame = ttk.Frame(comp_canvas)
        self._comp_frame.bind('<Configure>',
            lambda e: comp_canvas.configure(scrollregion=comp_canvas.bbox('all')))
        comp_canvas.create_window((0, 0), window=self._comp_frame, anchor='nw')
        comp_canvas.configure(yscrollcommand=comp_sb.set)
        comp_sb.pack(side='right', fill='y')
        comp_canvas.pack(side='left', fill='both', expand=True)

        ttk.Label(right, text="Conditions :").grid(row=2, column=0, sticky='nw', pady=4)
        self._cond_frame = ttk.Frame(right)
        self._cond_frame.grid(row=2, column=1, sticky='w')
        for label in CONDITION_LABELS:
            var = tk.BooleanVar()
            self._cond_vars[label] = var
            ttk.Checkbutton(self._cond_frame, text=label, variable=var).pack(anchor='w')

        ttk.Button(right, text="  Sauvegarder  ", command=self._save).grid(
            row=3, column=0, columnspan=2, pady=10)

    def _build_comp_checkboxes(self):
        for w in self._comp_frame.winfo_children():
            w.destroy()
        self._comp_vars = {}
        library = load_library()
        for key, val in library.items():
            var = tk.BooleanVar()
            self._comp_vars[key] = var
            ttk.Checkbutton(
                self._comp_frame,
                text=f"{key}  —  {val['name']}",
                variable=var
            ).pack(anchor='w')

    def refresh_component_list(self):
        self._build_comp_checkboxes()

    def _load(self):
        self._build_comp_checkboxes()
        self._listbox.delete(0, 'end')
        for name in _BASE_PATTERN_NAMES:
            self._listbox.insert('end', name)
        for i in range(len(_BASE_PATTERN_NAMES)):
            self._listbox.itemconfig(i, foreground='gray')
        self._custom = load_custom_circuits()
        for c in self._custom:
            self._listbox.insert('end', c['name'])

    def _on_select(self, _=None):
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        base_count = len(_BASE_PATTERN_NAMES)
        if idx < base_count:
            return
        self._current_idx = idx - base_count
        circuit = self._custom[self._current_idx]
        self._name_var.set(circuit['name'])
        selected = set(circuit.get('components', []))
        for key, var in self._comp_vars.items():
            var.set(key in selected)
        selected_conds = set(circuit.get('conditions', []))
        for label, var in self._cond_vars.items():
            var.set(label in selected_conds)

    def _new(self):
        self._current_idx = None
        self._name_var.set('')
        for var in self._comp_vars.values():
            var.set(False)
        for var in self._cond_vars.values():
            var.set(False)

    def _delete(self):
        if self._current_idx is None:
            messagebox.showinfo("Info", "Sélectionnez un circuit personnalisé à supprimer.")
            return
        name = self._custom[self._current_idx]['name']
        if messagebox.askyesno("Confirmer", f"Supprimer le circuit '{name}' ?"):
            self._custom.pop(self._current_idx)
            save_custom_circuits(self._custom)
            self._current_idx = None
            self._load()

    def _save(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showerror("Erreur", "Le nom du circuit est obligatoire.")
            return
        components = [k for k, v in self._comp_vars.items() if v.get()]
        if not components:
            messagebox.showerror("Erreur", "Sélectionnez au moins un type de composant.")
            return
        conditions = [k for k, v in self._cond_vars.items() if v.get()]

        circuit = {'name': name, 'components': components, 'conditions': conditions}
        if self._current_idx is not None:
            self._custom[self._current_idx] = circuit
        else:
            self._custom.append(circuit)
            self._current_idx = len(self._custom) - 1

        save_custom_circuits(self._custom)
        self._load()
        messagebox.showinfo("Succès", f"Circuit '{name}' sauvegardé.")
```

- [ ] **Step 2: Verify import**

```bash
python -c "from gui.tab_circuits import TabCircuits; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add gui/tab_circuits.py
git commit -m "feat: add Circuits tab for managing custom circuit patterns"
```

---

## Task 7: Point d'entrée + test manuel

**Files:**
- Create: `app.py`

- [ ] **Step 1: Create `app.py`**

```python
from gui.app_window import AppWindow

if __name__ == '__main__':
    AppWindow().run()
```

- [ ] **Step 2: Run all automated tests**

```bash
pytest tests/ -q
```

Expected: 80 passed

- [ ] **Step 3: Test manuel — Onglet Analyser**

```bash
python app.py
```

- Cliquer "Parcourir" → sélectionner `sample_circuit.txt`
- Cliquer "Analyser" → le rapport s'affiche dans la zone de texte
- Vérifier que les groupes attendus apparaissent : "Filtre RC passe-bas", "Pont diviseur de tension", "Transistor en commutation", "Suiveur de tension (AOP)"
- Cliquer "Sauvegarder le rapport" → choisir un emplacement → vérifier que le fichier est créé

- [ ] **Step 4: Test manuel — Onglet Composants**

- Aller dans l'onglet "Composants"
- Cliquer "+ Nouveau" → saisir préfixe "IC", nom "Mon CI", ajouter broches "VCC", "GND", "OUT"
- Cliquer "Sauvegarder" → vérifier que "IC" apparaît dans la liste
- Aller dans l'onglet "Circuits" → vérifier que "IC — Mon CI" apparaît dans la liste des composants

- [ ] **Step 5: Test manuel — Onglet Circuits**

- Aller dans l'onglet "Circuits"
- Cliquer "+ Nouveau" → saisir nom "Mon filtre RC"
- Cocher "R — Résistance" et "C — Condensateur"
- Cocher la condition "C connecté à GND"
- Cliquer "Sauvegarder"
- Aller dans l'onglet "Analyser" → relancer l'analyse sur `sample_circuit.txt`
- Vérifier que "Mon filtre RC" apparaît dans le rapport

- [ ] **Step 6: Commit final**

```bash
git add app.py
git commit -m "feat: add app.py entry point for Tkinter UI"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ Fenêtre unique + 3 onglets → Tasks 3-7
- ✅ Onglet Analyser (parcourir, analyser, sauvegarder) → Task 4
- ✅ Onglet Circuits (liste, formulaire, conditions, save/delete) → Task 6
- ✅ Onglet Composants (préfixe, nom, broches dynamiques, save/delete) → Task 5
- ✅ Circuits personnalisés en JSON (custom_circuits.json) → Task 1
- ✅ CustomCircuitPattern interprète les conditions → Task 1
- ✅ Matcher charge les patterns personnalisés → Task 2
- ✅ Liste composants générée depuis load_library() → Tab Circuits Task 6
- ✅ Types de base non modifiables (gris) → Tasks 5+6
- ✅ Interface en français → tout le code UI

**2. Placeholder scan:** Aucun TBD ou placeholder.

**3. Type consistency:**
- `CustomCircuitPattern` défini Task 1, utilisé Task 2
- `CONDITION_LABELS` défini Task 1, importé Tasks 5+6
- `on_save` callback défini Task 3 (`AppWindow`), implémenté Task 5 (`TabComponents`), appelé Task 6 (`TabCircuits.refresh_component_list`)
- `load_custom_circuits` / `save_custom_circuits` définis Task 1, utilisés Task 6
