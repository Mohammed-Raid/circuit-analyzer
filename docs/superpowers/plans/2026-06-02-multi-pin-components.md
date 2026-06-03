# Multi-Pin Components Extension — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the circuit analyzer to support multi-pin components (transistors BJT/MOSFET, AOPs) with a component library system and 9 new circuit patterns, while keeping all 32 existing tests passing.

**Architecture:** `Component` gains a `pins: dict[str, str]` field replacing positional `net1`/`net2` (kept as backward-compat properties). `build_graph()` stores all components in `graph.graph['components']` so new patterns can look up multi-pin topology directly. Patterns receive only the graph — they access the components dict via `graph.graph.get('components', {})`.

**Tech Stack:** Python 3.10+, networkx, pytest (already installed)

---

## File Map

| File | Change |
|---|---|
| `circuit_analyzer/parser.py` | `Component` gets `pins` field; `net1`/`net2` become properties; parser updated |
| `circuit_analyzer/graph_builder.py` | Store `graph.graph['components']`; multi-pin adds nodes only |
| `circuit_analyzer/component_library/__init__.py` | New (empty) |
| `circuit_analyzer/component_library/base.py` | New — COMPONENT_TYPES dict |
| `circuit_analyzer/component_library/loader.py` | New — load base + merge JSON override |
| `circuit_analyzer/patterns/transistor.py` | New — 4 BJT/MOSFET patterns |
| `circuit_analyzer/patterns/opamp.py` | New — 5 AOP patterns |
| `circuit_analyzer/matcher.py` | Import all three pattern sets |
| `tests/test_graph_builder.py` | Update Component constructors |
| `tests/test_patterns.py` | Update Component constructors |
| `tests/test_matcher.py` | Update Component constructors |
| `tests/test_component_library.py` | New |
| `tests/test_transistor_patterns.py` | New |
| `tests/test_opamp_patterns.py` | New |

---

## Task 1: Migrate Component to pins dict

**Files:**
- Modify: `circuit_analyzer/parser.py`
- Modify: `tests/test_graph_builder.py`
- Modify: `tests/test_patterns.py`
- Modify: `tests/test_matcher.py`

- [ ] **Step 1: Update `circuit_analyzer/parser.py`**

Replace the entire file with:

```python
from dataclasses import dataclass


@dataclass
class Component:
    ref: str
    type: str
    pins: dict[str, str]
    value: str = ''

    @property
    def net1(self) -> str:
        return list(self.pins.values())[0] if self.pins else ''

    @property
    def net2(self) -> str:
        vals = list(self.pins.values())
        return vals[1] if len(vals) > 1 else ''


def parse_file(path: str) -> list[Component]:
    components = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            ref = parts[0]
            net1 = parts[1]
            net2 = parts[2]
            value = parts[3] if len(parts) > 3 else ''
            comp_type = ref[0].upper()
            components.append(Component(
                ref=ref, type=comp_type,
                pins={'1': net1, '2': net2},
                value=value
            ))
    return components
```

- [ ] **Step 2: Verify test_parser.py still passes (no changes needed)**

```bash
pytest tests/test_parser.py -v
```

Expected: 5 PASS — `net1`/`net2` properties preserve existing behavior.

- [ ] **Step 3: Update `tests/test_graph_builder.py`**

Replace the entire file with:

```python
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph


def test_nodes_are_nets():
    comps = [Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k')]
    G = build_graph(comps)
    assert 'NET_A' in G.nodes
    assert 'NET_B' in G.nodes


def test_edge_has_component_attributes():
    comps = [Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k')]
    G = build_graph(comps)
    edges = list(G.edges(data=True))
    assert len(edges) == 1
    data = edges[0][2]
    assert data['ref'] == 'R1'
    assert data['type'] == 'R'
    assert data['value'] == '10k'


def test_multiple_components_between_same_nodes():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_A', '2': 'NET_B'}, '100nF'),
    ]
    G = build_graph(comps)
    assert G.number_of_edges() == 2


def test_shared_node():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    G = build_graph(comps)
    assert 'NET_MID' in G.nodes
    assert G.degree('NET_MID') == 2
```

- [ ] **Step 4: Update `tests/test_patterns.py`**

Replace the entire file with:

```python
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.patterns.basic_circuits import (
    RCLowPassFilter, RCHighPassFilter, LCFilter,
    VoltageDivider, DecouplingCapacitor, BridgeRectifier,
    FuseProtection, RCSnubber
)


def test_rc_lowpass_found():
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    matches = RCLowPassFilter().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'C1'}


def test_rc_lowpass_not_found_when_c_not_to_gnd():
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'NET_OUT'}, '100nF'),
    ]
    assert RCLowPassFilter().match(build_graph(comps)) == []


def test_rc_highpass_found():
    comps = [
        Component('C1', 'C', {'1': 'NET_IN', '2': 'NET_MID'}, '100nF'),
        Component('R1', 'R', {'1': 'NET_MID', '2': 'GND'}, '10k'),
    ]
    matches = RCHighPassFilter().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'C1'}


def test_rc_highpass_not_found_when_r_not_to_gnd():
    comps = [
        Component('C1', 'C', {'1': 'NET_IN', '2': 'NET_MID'}, '100nF'),
        Component('R1', 'R', {'1': 'NET_MID', '2': 'NET_OUT'}, '10k'),
    ]
    assert RCHighPassFilter().match(build_graph(comps)) == []


def test_lc_filter_found():
    comps = [
        Component('L1', 'L', {'1': 'NET_IN', '2': 'NET_MID'}, '10uH'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    matches = LCFilter().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'L1', 'C1'}


def test_voltage_divider_found():
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_DIV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_DIV', '2': 'GND'}, '4.7k'),
    ]
    matches = VoltageDivider().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'R2'}


def test_voltage_divider_not_found_for_single_resistor():
    comps = [Component('R1', 'R', {'1': 'VCC', '2': 'GND'}, '10k')]
    assert VoltageDivider().match(build_graph(comps)) == []


def test_decoupling_cap_found():
    comps = [Component('C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF')]
    matches = DecouplingCapacitor().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['C1']


def test_decoupling_cap_not_found_between_two_signal_nets():
    comps = [Component('C1', 'C', {'1': 'NET_A', '2': 'NET_B'}, '100nF')]
    assert DecouplingCapacitor().match(build_graph(comps)) == []


def test_fuse_found():
    comps = [Component('F1', 'F', {'1': 'LINE_IN', '2': 'NET_FUSE'})]
    matches = FuseProtection().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['F1']


def test_rc_snubber_found():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '100'),
        Component('C1', 'C', {'1': 'NET_A', '2': 'NET_B'}, '10nF'),
    ]
    matches = RCSnubber().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'C1'}


def test_rc_snubber_not_found_when_not_parallel():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '100'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'NET_C'}, '10nF'),
    ]
    assert RCSnubber().match(build_graph(comps)) == []


def test_bridge_rectifier_found():
    comps = [
        Component('D1', 'D', {'A': 'AC_POS', 'K': 'DC_POS'}),
        Component('D2', 'D', {'A': 'AC_NEG', 'K': 'DC_POS'}),
        Component('D3', 'D', {'A': 'DC_NEG', 'K': 'AC_POS'}),
        Component('D4', 'D', {'A': 'DC_NEG', 'K': 'AC_NEG'}),
    ]
    matches = BridgeRectifier().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'D1', 'D2', 'D3', 'D4'}
```

- [ ] **Step 5: Update `tests/test_matcher.py`**

Replace the entire file with:

```python
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns


def test_matcher_finds_rc_lowpass():
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Filtre RC passe-bas' in types


def test_matcher_returns_circuit_type_field():
    comps = [Component('F1', 'F', {'1': 'LINE_IN', '2': 'NET_FUSE'})]
    results = match_patterns(build_graph(comps))
    assert all('circuit_type' in r for r in results)
    assert all('components' in r for r in results)
    assert all('nodes' in r for r in results)


def test_matcher_empty_circuit_returns_empty():
    import networkx as nx
    assert match_patterns(nx.MultiGraph()) == []
```

- [ ] **Step 6: Run all existing tests**

```bash
pytest tests/ -v -q
```

Expected: 32 passed

- [ ] **Step 7: Commit**

```bash
git add circuit_analyzer/parser.py tests/test_graph_builder.py tests/test_patterns.py tests/test_matcher.py
git commit -m "refactor: migrate Component to pins dict with net1/net2 compat properties"
```

---

## Task 2: Update graph_builder

**Files:**
- Modify: `circuit_analyzer/graph_builder.py`
- Modify: `tests/test_graph_builder.py`

- [ ] **Step 1: Write new failing tests** (append to `tests/test_graph_builder.py`)

Add these tests at the end of the file:

```python
def test_components_dict_stored_in_graph():
    comps = [Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k')]
    G = build_graph(comps)
    assert 'R1' in G.graph['components']
    assert G.graph['components']['R1'].ref == 'R1'


def test_multipin_component_adds_nodes_not_edges():
    comps = [Component('Q1', 'Q', {'B': 'NET_B', 'C': 'NET_C', 'E': 'GND'})]
    G = build_graph(comps)
    assert G.number_of_edges() == 0
    assert 'NET_B' in G.nodes
    assert 'NET_C' in G.nodes
    assert 'GND' in G.nodes


def test_mixed_two_and_multipin():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('Q1', 'Q', {'B': 'NET_B', 'C': 'NET_C', 'E': 'GND'}),
    ]
    G = build_graph(comps)
    assert G.number_of_edges() == 1
    assert 'Q1' in G.graph['components']
    assert 'R1' in G.graph['components']
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_graph_builder.py::test_components_dict_stored_in_graph -v
```

Expected: FAIL — `'components' not in G.graph`

- [ ] **Step 3: Update `circuit_analyzer/graph_builder.py`**

Replace the entire file with:

```python
import networkx as nx
from circuit_analyzer.parser import Component


def build_graph(components: list[Component]) -> nx.MultiGraph:
    G = nx.MultiGraph()
    G.graph['components'] = {c.ref: c for c in components}
    for comp in components:
        if len(comp.pins) == 2:
            net1, net2 = list(comp.pins.values())
            G.add_edge(net1, net2, ref=comp.ref, type=comp.type, value=comp.value)
        else:
            for net in comp.pins.values():
                G.add_node(net)
    return G
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/ -q
```

Expected: 35 passed

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/graph_builder.py tests/test_graph_builder.py
git commit -m "feat: store components dict in graph and support multi-pin components"
```

---

## Task 3: Component Library

**Files:**
- Create: `circuit_analyzer/component_library/__init__.py`
- Create: `circuit_analyzer/component_library/base.py`
- Create: `circuit_analyzer/component_library/loader.py`
- Create: `tests/test_component_library.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_component_library.py`:

```python
import json, os, tempfile
from circuit_analyzer.component_library.base import COMPONENT_TYPES
from circuit_analyzer.component_library.loader import load_library, get_pins


def test_base_library_has_standard_types():
    assert 'R' in COMPONENT_TYPES
    assert 'C' in COMPONENT_TYPES
    assert 'Q' in COMPONENT_TYPES
    assert 'U' in COMPONENT_TYPES
    assert 'M' in COMPONENT_TYPES


def test_bjt_pins():
    assert COMPONENT_TYPES['Q']['pins'] == ['B', 'C', 'E']


def test_mosfet_pins():
    assert COMPONENT_TYPES['M']['pins'] == ['G', 'D', 'S']


def test_opamp_pins():
    assert COMPONENT_TYPES['U']['pins'] == ['IN+', 'IN-', 'OUT', 'V+', 'V-']


def test_load_library_returns_base_without_json():
    lib = load_library('nonexistent_file.json')
    assert 'Q' in lib
    assert lib['Q']['pins'] == ['B', 'C', 'E']


def test_json_override_replaces_entry():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'Q': {'name': 'Transistor custom', 'pins': ['BASE', 'COLL', 'EMIT']}}, f)
        fname = f.name
    lib = load_library(fname)
    os.unlink(fname)
    assert lib['Q']['pins'] == ['BASE', 'COLL', 'EMIT']


def test_json_adds_new_type():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'IC': {'name': 'CI spécifique', 'pins': ['VCC', 'GND', 'IN', 'OUT']}}, f)
        fname = f.name
    lib = load_library(fname)
    os.unlink(fname)
    assert 'IC' in lib
    assert lib['IC']['pins'] == ['VCC', 'GND', 'IN', 'OUT']


def test_get_pins_known_type():
    assert get_pins('Q') == ['B', 'C', 'E']
    assert get_pins('M') == ['G', 'D', 'S']


def test_get_pins_unknown_type_defaults_to_two_pin():
    assert get_pins('XYZ') == ['1', '2']
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_component_library.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `circuit_analyzer/component_library/__init__.py`**

Empty file.

- [ ] **Step 4: Create `circuit_analyzer/component_library/base.py`**

```python
COMPONENT_TYPES = {
    'R':  {'name': 'Résistance',       'pins': ['1', '2']},
    'C':  {'name': 'Condensateur',     'pins': ['1', '2']},
    'L':  {'name': 'Inductance',       'pins': ['1', '2']},
    'D':  {'name': 'Diode',            'pins': ['A', 'K']},
    'F':  {'name': 'Fusible',          'pins': ['1', '2']},
    'Q':  {'name': 'Transistor BJT',   'pins': ['B', 'C', 'E']},
    'M':  {'name': 'MOSFET',           'pins': ['G', 'D', 'S']},
    'U':  {'name': 'Circuit intégré',  'pins': ['IN+', 'IN-', 'OUT', 'V+', 'V-']},
    'T':  {'name': 'Transformateur',   'pins': ['P1', 'P2', 'S1', 'S2']},
    'K':  {'name': 'Relais',           'pins': ['A1', 'A2', '11', '12', '14']},
    'SW': {'name': 'Interrupteur',     'pins': ['1', '2']},
}
```

- [ ] **Step 5: Create `circuit_analyzer/component_library/loader.py`**

```python
import json
from pathlib import Path
from circuit_analyzer.component_library.base import COMPONENT_TYPES


def load_library(json_path: str = 'component_library.json') -> dict:
    library = dict(COMPONENT_TYPES)
    path = Path(json_path)
    if path.exists():
        with open(path, encoding='utf-8') as f:
            overrides = json.load(f)
        library.update(overrides)
    return library


def get_pins(comp_type: str, json_path: str = 'component_library.json') -> list[str]:
    library = load_library(json_path)
    entry = library.get(comp_type)
    return entry['pins'] if entry else ['1', '2']
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_component_library.py -v
```

Expected: 8 passed

- [ ] **Step 7: Run all tests**

```bash
pytest tests/ -q
```

Expected: 43 passed

- [ ] **Step 8: Commit**

```bash
git add circuit_analyzer/component_library/ tests/test_component_library.py
git commit -m "feat: add component library with base types and JSON override support"
```

---

## Task 4: Transistor Patterns

**Files:**
- Create: `circuit_analyzer/patterns/transistor.py`
- Create: `tests/test_transistor_patterns.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_transistor_patterns.py`:

```python
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.patterns.transistor import (
    TransistorSwitch, CommonEmitterAmp, CurrentMirror, MosfetSwitch
)


# --- Transistor en commutation ---

def test_transistor_switch_found():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_DRIVE', '2': 'NET_BASE'}, '10k'),
    ]
    matches = TransistorSwitch().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'Q1', 'R1'}


def test_transistor_switch_not_found_without_base_resistor():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
    ]
    assert TransistorSwitch().match(build_graph(comps)) == []


def test_transistor_switch_not_found_when_emitter_not_gnd():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'NET_EMIT'}),
        Component('R1', 'R', {'1': 'NET_DRIVE', '2': 'NET_BASE'}, '10k'),
    ]
    assert TransistorSwitch().match(build_graph(comps)) == []


# --- Amplificateur émetteur commun ---

def test_common_emitter_found():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_COLL'}, '1k'),
        Component('R2', 'R', {'1': 'VCC', '2': 'NET_BASE'}, '10k'),
    ]
    matches = CommonEmitterAmp().match(build_graph(comps))
    assert len(matches) == 1
    assert 'Q1' in matches[0]['components']
    assert 'R1' in matches[0]['components']
    assert 'R2' in matches[0]['components']


def test_common_emitter_not_found_without_collector_resistor():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R2', 'R', {'1': 'VCC', '2': 'NET_BASE'}, '10k'),
    ]
    assert CommonEmitterAmp().match(build_graph(comps)) == []


# --- Miroir de courant BJT ---

def test_current_mirror_found():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL1', 'E': 'GND'}),
        Component('Q2', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL2', 'E': 'GND'}),
    ]
    matches = CurrentMirror().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'Q1', 'Q2'}


def test_current_mirror_not_found_when_bases_differ():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE1', 'C': 'NET_COLL1', 'E': 'GND'}),
        Component('Q2', 'Q', {'B': 'NET_BASE2', 'C': 'NET_COLL2', 'E': 'GND'}),
    ]
    assert CurrentMirror().match(build_graph(comps)) == []


# --- MOSFET en commutation ---

def test_mosfet_switch_found():
    comps = [
        Component('M1', 'M', {'G': 'NET_GATE', 'D': 'NET_DRAIN', 'S': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CTRL', '2': 'NET_GATE'}, '100'),
    ]
    matches = MosfetSwitch().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'M1', 'R1'}


def test_mosfet_switch_not_found_when_source_not_gnd():
    comps = [
        Component('M1', 'M', {'G': 'NET_GATE', 'D': 'NET_DRAIN', 'S': 'NET_SOURCE'}),
        Component('R1', 'R', {'1': 'NET_CTRL', '2': 'NET_GATE'}, '100'),
    ]
    assert MosfetSwitch().match(build_graph(comps)) == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_transistor_patterns.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `circuit_analyzer/patterns/transistor.py`**

```python
from circuit_analyzer.patterns.base import Pattern, is_gnd


class TransistorSwitch(Pattern):
    name = "Transistor en commutation"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for q_ref, comp in components.items():
            if comp.type != 'Q':
                continue
            base = comp.pins.get('B')
            collector = comp.pins.get('C')
            emitter = comp.pins.get('E')
            if not all([base, collector, emitter]):
                continue
            if not is_gnd(emitter):
                continue
            r_at_base = [d['ref'] for u, v, d in graph.edges(base, data=True) if d['type'] == 'R']
            if r_at_base:
                matches.append({
                    'components': [q_ref] + r_at_base,
                    'nodes': [base, collector, emitter],
                })
        return matches


class CommonEmitterAmp(Pattern):
    name = "Amplificateur émetteur commun"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for q_ref, comp in components.items():
            if comp.type != 'Q':
                continue
            base = comp.pins.get('B')
            collector = comp.pins.get('C')
            emitter = comp.pins.get('E')
            if not all([base, collector, emitter]):
                continue
            r_at_collector = [d['ref'] for u, v, d in graph.edges(collector, data=True) if d['type'] == 'R']
            r_at_base = [d['ref'] for u, v, d in graph.edges(base, data=True) if d['type'] == 'R']
            if r_at_collector and r_at_base:
                matches.append({
                    'components': [q_ref] + r_at_collector + r_at_base,
                    'nodes': [base, collector, emitter],
                })
        return matches


class CurrentMirror(Pattern):
    name = "Miroir de courant BJT"

    def match(self, graph):
        components = graph.graph.get('components', {})
        bjts = [(ref, comp) for ref, comp in components.items() if comp.type == 'Q']
        matches = []
        seen = set()
        for i in range(len(bjts)):
            for j in range(i + 1, len(bjts)):
                ref1, q1 = bjts[i]
                ref2, q2 = bjts[j]
                base1 = q1.pins.get('B')
                base2 = q2.pins.get('B')
                emitter1 = q1.pins.get('E')
                emitter2 = q2.pins.get('E')
                if not all([base1, base2, emitter1, emitter2]):
                    continue
                if base1 == base2 and is_gnd(emitter1) and is_gnd(emitter2):
                    key = frozenset([ref1, ref2])
                    if key not in seen:
                        seen.add(key)
                        matches.append({
                            'components': [ref1, ref2],
                            'nodes': [base1, q1.pins.get('C', ''), q2.pins.get('C', '')],
                        })
        return matches


class MosfetSwitch(Pattern):
    name = "MOSFET en commutation"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for m_ref, comp in components.items():
            if comp.type != 'M':
                continue
            gate = comp.pins.get('G')
            drain = comp.pins.get('D')
            source = comp.pins.get('S')
            if not all([gate, drain, source]):
                continue
            if not is_gnd(source):
                continue
            r_at_gate = [d['ref'] for u, v, d in graph.edges(gate, data=True) if d['type'] == 'R']
            if r_at_gate:
                matches.append({
                    'components': [m_ref] + r_at_gate,
                    'nodes': [gate, drain, source],
                })
        return matches


TRANSISTOR_PATTERNS = [
    TransistorSwitch(),
    CommonEmitterAmp(),
    CurrentMirror(),
    MosfetSwitch(),
]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_transistor_patterns.py -v
```

Expected: 8 passed

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -q
```

Expected: 51 passed

- [ ] **Step 6: Commit**

```bash
git add circuit_analyzer/patterns/transistor.py tests/test_transistor_patterns.py
git commit -m "feat: add BJT and MOSFET circuit patterns"
```

---

## Task 5: AOP Patterns

**Files:**
- Create: `circuit_analyzer/patterns/opamp.py`
- Create: `tests/test_opamp_patterns.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_opamp_patterns.py`:

```python
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.patterns.opamp import (
    InvertingAmplifier, NonInvertingAmplifier, VoltageFollower,
    Integrator, Comparator
)


# --- Amplificateur inverseur ---

def test_inverting_amp_found():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INM'}, '10k'),
        Component('R2', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '100k'),
    ]
    matches = InvertingAmplifier().match(build_graph(comps))
    assert len(matches) == 1
    assert 'U1' in matches[0]['components']
    assert 'R1' in matches[0]['components']
    assert 'R2' in matches[0]['components']


def test_inverting_amp_not_found_without_feedback():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INM'}, '10k'),
    ]
    assert InvertingAmplifier().match(build_graph(comps)) == []


# --- Amplificateur non-inverseur ---

def test_non_inverting_amp_found():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '100k'),
        Component('R2', 'R', {'1': 'NET_INM', '2': 'GND'}, '10k'),
    ]
    matches = NonInvertingAmplifier().match(build_graph(comps))
    assert len(matches) == 1
    assert 'U1' in matches[0]['components']
    assert 'R1' in matches[0]['components']
    assert 'R2' in matches[0]['components']


def test_non_inverting_amp_not_found_without_gnd_resistor():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '100k'),
    ]
    assert NonInvertingAmplifier().match(build_graph(comps)) == []


# --- Suiveur de tension ---

def test_voltage_follower_found():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_OUT', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
    ]
    matches = VoltageFollower().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['U1']


def test_voltage_follower_not_found_when_no_direct_feedback():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
    ]
    assert VoltageFollower().match(build_graph(comps)) == []


# --- Intégrateur ---

def test_integrator_found():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INM'}, '10k'),
        Component('C1', 'C', {'1': 'NET_INM', '2': 'NET_OUT'}, '10nF'),
    ]
    matches = Integrator().match(build_graph(comps))
    assert len(matches) == 1
    assert 'U1' in matches[0]['components']
    assert 'R1' in matches[0]['components']
    assert 'C1' in matches[0]['components']


def test_integrator_not_found_without_feedback_cap():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INM'}, '10k'),
    ]
    assert Integrator().match(build_graph(comps)) == []


# --- Comparateur ---

def test_comparator_found():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_REF', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
    ]
    matches = Comparator().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['U1']


def test_comparator_not_found_when_follower():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_OUT', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
    ]
    assert Comparator().match(build_graph(comps)) == []


def test_comparator_not_found_when_feedback_resistor_present():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '100k'),
    ]
    assert Comparator().match(build_graph(comps)) == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_opamp_patterns.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `circuit_analyzer/patterns/opamp.py`**

```python
from circuit_analyzer.patterns.base import Pattern, is_gnd


class InvertingAmplifier(Pattern):
    name = "Amplificateur inverseur (AOP)"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for u_ref, comp in components.items():
            if comp.type != 'U':
                continue
            inm = comp.pins.get('IN-')
            out = comp.pins.get('OUT')
            if not all([inm, out]):
                continue
            r_at_inm = [
                (d['ref'], v if u == inm else u)
                for u, v, d in graph.edges(inm, data=True)
                if d['type'] == 'R'
            ]
            feedback_r = [r for r, other in r_at_inm if other == out]
            input_r = [r for r, other in r_at_inm if other != out]
            if feedback_r and input_r:
                matches.append({
                    'components': [u_ref] + feedback_r + input_r,
                    'nodes': [comp.pins.get('IN+', ''), inm, out],
                })
        return matches


class NonInvertingAmplifier(Pattern):
    name = "Amplificateur non-inverseur (AOP)"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for u_ref, comp in components.items():
            if comp.type != 'U':
                continue
            inm = comp.pins.get('IN-')
            out = comp.pins.get('OUT')
            if not all([inm, out]):
                continue
            r_at_inm = [
                (d['ref'], v if u == inm else u)
                for u, v, d in graph.edges(inm, data=True)
                if d['type'] == 'R'
            ]
            feedback_r = [r for r, other in r_at_inm if other == out]
            gnd_r = [r for r, other in r_at_inm if is_gnd(other)]
            if feedback_r and gnd_r:
                matches.append({
                    'components': [u_ref] + feedback_r + gnd_r,
                    'nodes': [comp.pins.get('IN+', ''), inm, out],
                })
        return matches


class VoltageFollower(Pattern):
    name = "Suiveur de tension (AOP)"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for u_ref, comp in components.items():
            if comp.type != 'U':
                continue
            inm = comp.pins.get('IN-')
            out = comp.pins.get('OUT')
            if inm and out and inm == out:
                matches.append({
                    'components': [u_ref],
                    'nodes': [comp.pins.get('IN+', ''), out],
                })
        return matches


class Integrator(Pattern):
    name = "Intégrateur (AOP)"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for u_ref, comp in components.items():
            if comp.type != 'U':
                continue
            inm = comp.pins.get('IN-')
            out = comp.pins.get('OUT')
            if not all([inm, out]):
                continue
            r_at_inm = [d['ref'] for u, v, d in graph.edges(inm, data=True) if d['type'] == 'R']
            c_feedback = [
                d['ref'] for u, v, d in graph.edges(inm, data=True)
                if d['type'] == 'C' and (v if u == inm else u) == out
            ]
            if r_at_inm and c_feedback:
                matches.append({
                    'components': [u_ref] + r_at_inm + c_feedback,
                    'nodes': [comp.pins.get('IN+', ''), inm, out],
                })
        return matches


class Comparator(Pattern):
    name = "Comparateur (AOP)"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for u_ref, comp in components.items():
            if comp.type != 'U':
                continue
            inm = comp.pins.get('IN-')
            inp = comp.pins.get('IN+')
            out = comp.pins.get('OUT')
            if not all([inm, inp, out]):
                continue
            if inm == out:
                continue
            feedback = [
                d for u, v, d in graph.edges(inm, data=True)
                if d['type'] in ('R', 'C') and (v if u == inm else u) == out
            ]
            if not feedback:
                matches.append({
                    'components': [u_ref],
                    'nodes': [inp, inm, out],
                })
        return matches


OPAMP_PATTERNS = [
    InvertingAmplifier(),
    NonInvertingAmplifier(),
    VoltageFollower(),
    Integrator(),
    Comparator(),
]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_opamp_patterns.py -v
```

Expected: 11 passed

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -q
```

Expected: 62 passed

- [ ] **Step 6: Commit**

```bash
git add circuit_analyzer/patterns/opamp.py tests/test_opamp_patterns.py
git commit -m "feat: add AOP circuit patterns (inverseur, non-inverseur, suiveur, intégrateur, comparateur)"
```

---

## Task 6: Update Matcher

**Files:**
- Modify: `circuit_analyzer/matcher.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_matcher.py`)

Add this test at the end of `tests/test_matcher.py`:

```python
def test_matcher_finds_transistor_switch():
    from circuit_analyzer.parser import Component
    from circuit_analyzer.graph_builder import build_graph
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_DRIVE', '2': 'NET_BASE'}, '10k'),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Transistor en commutation' in types


def test_matcher_finds_voltage_follower():
    from circuit_analyzer.parser import Component
    from circuit_analyzer.graph_builder import build_graph
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_OUT', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Suiveur de tension (AOP)' in types
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_matcher.py::test_matcher_finds_transistor_switch -v
```

Expected: FAIL — `'Transistor en commutation' not in types`

- [ ] **Step 3: Update `circuit_analyzer/matcher.py`**

Replace the entire file with:

```python
import networkx as nx
from circuit_analyzer.patterns.basic_circuits import ALL_PATTERNS as BASIC_PATTERNS
from circuit_analyzer.patterns.transistor import TRANSISTOR_PATTERNS
from circuit_analyzer.patterns.opamp import OPAMP_PATTERNS

_ALL_PATTERNS = BASIC_PATTERNS + TRANSISTOR_PATTERNS + OPAMP_PATTERNS


def match_patterns(graph: nx.MultiGraph) -> list[dict]:
    results = []
    for pattern in _ALL_PATTERNS:
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

Expected: 64 passed

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/matcher.py tests/test_matcher.py
git commit -m "feat: extend matcher with transistor and AOP patterns"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ Component pins dict + net1/net2 compat → Task 1
- ✅ graph.graph['components'] → Task 2
- ✅ Component library (base.py + loader.py + JSON override) → Task 3
- ✅ Transistor patterns (switch, émetteur commun, miroir, MOSFET) → Task 4
- ✅ AOP patterns (inverseur, non-inverseur, suiveur, intégrateur, comparateur) → Task 5
- ✅ Matcher updated → Task 6
- ✅ Parser "inchangé pour l'instant" — intentional, documented in spec

**2. Placeholder scan:** None found.

**3. Type consistency:**
- `Component(ref, type, pins: dict, value='')` defined in Task 1, used consistently in Tasks 2–6
- `graph.graph['components']` set in Task 2, accessed in Tasks 4–5 via `graph.graph.get('components', {})`
- `TRANSISTOR_PATTERNS` defined in Task 4 and imported in Task 6
- `OPAMP_PATTERNS` defined in Task 5 and imported in Task 6
- All `match()` return `list[dict]` with `components` and `nodes` keys — consistent throughout
