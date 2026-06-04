# Circuit Analyzer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CLI tool that reads a plain-text circuit netlist, identifies basic circuit patterns using graph topology, and outputs a text report grouping components by recognized circuit type.

**Architecture:** The input file is parsed into a list of `Component` objects, which are loaded into a NetworkX MultiGraph (nodes = nets, edges = components). Pattern classes each implement a `match(graph)` method to find their topology in the graph. A reporter formats the results.

**Tech Stack:** Python 3.10+, `networkx`, `pytest`, `argparse` (stdlib)

---

## File Map

| File | Responsibility |
|---|---|
| `circuit_analyzer/parser.py` | Parse `.txt` netlist → `list[Component]` |
| `circuit_analyzer/graph_builder.py` | `list[Component]` → `nx.MultiGraph` |
| `circuit_analyzer/patterns/base.py` | Abstract `Pattern` base class |
| `circuit_analyzer/patterns/basic_circuits.py` | 8 pattern implementations + `ALL_PATTERNS` |
| `circuit_analyzer/matcher.py` | Apply all patterns → `list[MatchResult]` |
| `circuit_analyzer/reporter.py` | `list[MatchResult]` → text report string |
| `main.py` | CLI entry point (argparse) |
| `tests/test_parser.py` | Parser unit tests |
| `tests/test_graph_builder.py` | Graph builder unit tests |
| `tests/test_patterns.py` | Pattern unit tests |
| `tests/test_matcher.py` | Matcher unit tests |
| `tests/test_reporter.py` | Reporter unit tests |
| `tests/test_integration.py` | End-to-end test |
| `requirements.txt` | Dependencies |
| `sample_circuit.txt` | Example netlist for manual testing |

---

## Task 1: Project Setup

**Files:**
- Create: `circuit_analyzer/` (directory)
- Create: `circuit_analyzer/__init__.py`
- Create: `circuit_analyzer/patterns/` (directory)
- Create: `circuit_analyzer/patterns/__init__.py`
- Create: `tests/` (directory)
- Create: `tests/__init__.py`
- Create: `requirements.txt`
- Create: `sample_circuit.txt`

- [ ] **Step 1: Create directory structure**

```
mkdir circuit_analyzer
mkdir circuit_analyzer\patterns
mkdir tests
```

- [ ] **Step 2: Create `requirements.txt`**

```
networkx>=3.0
pytest>=7.0
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected output: `Successfully installed networkx-... pytest-...`

- [ ] **Step 4: Create empty `__init__.py` files**

`circuit_analyzer/__init__.py` — empty file
`circuit_analyzer/patterns/__init__.py` — empty file
`tests/__init__.py` — empty file

- [ ] **Step 5: Create `sample_circuit.txt`**

```
# Exemple de circuit de test
# Filtre RC passe-bas
R1  NET_IN   NET_MID  10k
C1  NET_MID  GND      100nF

# Pont diviseur de tension
R2  VCC      NET_DIV  10k
R3  NET_DIV  GND      4.7k

# Condensateur de découplage
C2  VCC      GND      10uF

# Fusible
F1  LINE_IN  NET_FUSE

# Snubber RC
R4  NET_A    NET_B    100
C3  NET_A    NET_B    10nF

# Diodes pont de Graetz
D1  AC_POS   DC_POS
D2  AC_NEG   DC_POS
D3  DC_NEG   AC_POS
D4  DC_NEG   AC_NEG
```

- [ ] **Step 6: Commit**

```bash
git init
git add requirements.txt sample_circuit.txt circuit_analyzer/__init__.py circuit_analyzer/patterns/__init__.py tests/__init__.py
git commit -m "chore: initial project structure for circuit analyzer"
```

---

## Task 2: Parser

**Files:**
- Create: `circuit_analyzer/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_parser.py`:
```python
import os, tempfile, pytest
from circuit_analyzer.parser import parse_file, Component


def _write_tmp(content):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
    f.write(content)
    f.close()
    return f.name


def test_parse_resistor_with_value():
    path = _write_tmp("R1  NET_A  NET_B  10k\n")
    comps = parse_file(path)
    os.unlink(path)
    assert len(comps) == 1
    c = comps[0]
    assert c.ref == 'R1'
    assert c.type == 'R'
    assert c.net1 == 'NET_A'
    assert c.net2 == 'NET_B'
    assert c.value == '10k'


def test_parse_diode_without_value():
    path = _write_tmp("D1  NET_A  NET_B\n")
    comps = parse_file(path)
    os.unlink(path)
    assert len(comps) == 1
    assert comps[0].type == 'D'
    assert comps[0].value == ''


def test_comments_and_blank_lines_ignored():
    path = _write_tmp("# commentaire\n\nR1 A B 10k\n")
    comps = parse_file(path)
    os.unlink(path)
    assert len(comps) == 1


def test_multiple_components():
    path = _write_tmp("R1 A B 10k\nC1 B GND 100nF\n")
    comps = parse_file(path)
    os.unlink(path)
    assert len(comps) == 2


def test_type_deduced_from_prefix():
    cases = [('R1', 'R'), ('C2', 'C'), ('L3', 'L'), ('D4', 'D'), ('F5', 'F')]
    lines = '\n'.join(f'{ref} A B' for ref, _ in cases)
    path = _write_tmp(lines)
    comps = parse_file(path)
    os.unlink(path)
    for comp, (_, expected_type) in zip(comps, cases):
        assert comp.type == expected_type
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_parser.py -v
```

Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement `circuit_analyzer/parser.py`**

```python
from dataclasses import dataclass, field


@dataclass
class Component:
    ref: str
    type: str
    net1: str
    net2: str
    value: str = ''


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
            components.append(Component(ref=ref, type=comp_type, net1=net1, net2=net2, value=value))
    return components
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_parser.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/parser.py tests/test_parser.py
git commit -m "feat: add text netlist parser"
```

---

## Task 3: Graph Builder

**Files:**
- Create: `circuit_analyzer/graph_builder.py`
- Create: `tests/test_graph_builder.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_graph_builder.py`:
```python
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph


def test_nodes_are_nets():
    comps = [Component('R1', 'R', 'NET_A', 'NET_B', '10k')]
    G = build_graph(comps)
    assert 'NET_A' in G.nodes
    assert 'NET_B' in G.nodes


def test_edge_has_component_attributes():
    comps = [Component('R1', 'R', 'NET_A', 'NET_B', '10k')]
    G = build_graph(comps)
    edges = list(G.edges(data=True))
    assert len(edges) == 1
    data = edges[0][2]
    assert data['ref'] == 'R1'
    assert data['type'] == 'R'
    assert data['value'] == '10k'


def test_multiple_components_between_same_nodes():
    comps = [
        Component('R1', 'R', 'NET_A', 'NET_B', '10k'),
        Component('C1', 'C', 'NET_A', 'NET_B', '100nF'),
    ]
    G = build_graph(comps)
    assert G.number_of_edges() == 2


def test_shared_node():
    comps = [
        Component('R1', 'R', 'NET_A', 'NET_MID', '10k'),
        Component('C1', 'C', 'NET_MID', 'GND', '100nF'),
    ]
    G = build_graph(comps)
    assert 'NET_MID' in G.nodes
    assert G.degree('NET_MID') == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_graph_builder.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement `circuit_analyzer/graph_builder.py`**

```python
import networkx as nx
from circuit_analyzer.parser import Component


def build_graph(components: list[Component]) -> nx.MultiGraph:
    G = nx.MultiGraph()
    for comp in components:
        G.add_edge(comp.net1, comp.net2, ref=comp.ref, type=comp.type, value=comp.value)
    return G
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_graph_builder.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/graph_builder.py tests/test_graph_builder.py
git commit -m "feat: add graph builder from component list"
```

---

## Task 4: Pattern Base Class

**Files:**
- Create: `circuit_analyzer/patterns/base.py`

- [ ] **Step 1: Create `circuit_analyzer/patterns/base.py`**

```python
from abc import ABC, abstractmethod
import networkx as nx


GND_NETS = {'GND', 'AGND', 'DGND', '0', 'VSS', 'V-'}
POWER_NETS = {'VCC', 'VDD', 'AVCC', 'AVDD', 'DVCC', 'VIN', 'VBAT', 'PWR', 'V+'}


def is_gnd(net: str) -> bool:
    return net.upper() in GND_NETS or any(g in net.upper() for g in GND_NETS)


def is_power(net: str) -> bool:
    return net.upper() in POWER_NETS or any(p in net.upper() for p in POWER_NETS)


class Pattern(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def match(self, graph: nx.MultiGraph) -> list[dict]:
        """
        Returns list of matches.
        Each match: {'components': [ref, ...], 'nodes': [net, ...]}
        """
        pass
```

- [ ] **Step 2: Commit**

```bash
git add circuit_analyzer/patterns/base.py
git commit -m "feat: add abstract Pattern base class"
```

---

## Task 5: Basic Circuit Patterns

**Files:**
- Create: `circuit_analyzer/patterns/basic_circuits.py`
- Create: `tests/test_patterns.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_patterns.py`:
```python
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.patterns.basic_circuits import (
    RCLowPassFilter, RCHighPassFilter, LCFilter,
    VoltageDivider, DecouplingCapacitor, BridgeRectifier,
    FuseProtection, RCSnubber
)


# --- RC Low-Pass Filter ---

def test_rc_lowpass_found():
    comps = [
        Component('R1', 'R', 'NET_IN', 'NET_MID', '10k'),
        Component('C1', 'C', 'NET_MID', 'GND', '100nF'),
    ]
    matches = RCLowPassFilter().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'C1'}


def test_rc_lowpass_not_found_when_c_not_to_gnd():
    comps = [
        Component('R1', 'R', 'NET_IN', 'NET_MID', '10k'),
        Component('C1', 'C', 'NET_MID', 'NET_OUT', '100nF'),
    ]
    assert RCLowPassFilter().match(build_graph(comps)) == []


# --- RC High-Pass Filter ---

def test_rc_highpass_found():
    comps = [
        Component('C1', 'C', 'NET_IN', 'NET_MID', '100nF'),
        Component('R1', 'R', 'NET_MID', 'GND', '10k'),
    ]
    matches = RCHighPassFilter().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'C1'}


# --- LC Filter ---

def test_lc_filter_found():
    comps = [
        Component('L1', 'L', 'NET_IN', 'NET_MID', '10uH'),
        Component('C1', 'C', 'NET_MID', 'GND', '100nF'),
    ]
    matches = LCFilter().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'L1', 'C1'}


# --- Voltage Divider ---

def test_voltage_divider_found():
    comps = [
        Component('R1', 'R', 'VCC', 'NET_DIV', '10k'),
        Component('R2', 'R', 'NET_DIV', 'GND', '4.7k'),
    ]
    matches = VoltageDivider().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'R2'}


def test_voltage_divider_not_found_for_single_resistor():
    comps = [Component('R1', 'R', 'VCC', 'GND', '10k')]
    assert VoltageDivider().match(build_graph(comps)) == []


# --- Decoupling Capacitor ---

def test_decoupling_cap_found():
    comps = [Component('C1', 'C', 'VCC', 'GND', '100nF')]
    matches = DecouplingCapacitor().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['C1']


def test_decoupling_cap_not_found_between_two_signal_nets():
    comps = [Component('C1', 'C', 'NET_A', 'NET_B', '100nF')]
    assert DecouplingCapacitor().match(build_graph(comps)) == []


# --- Fuse Protection ---

def test_fuse_found():
    comps = [Component('F1', 'F', 'LINE_IN', 'NET_FUSE')]
    matches = FuseProtection().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['F1']


# --- RC Snubber ---

def test_rc_snubber_found():
    comps = [
        Component('R1', 'R', 'NET_A', 'NET_B', '100'),
        Component('C1', 'C', 'NET_A', 'NET_B', '10nF'),
    ]
    matches = RCSnubber().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'C1'}


def test_rc_snubber_not_found_when_not_parallel():
    comps = [
        Component('R1', 'R', 'NET_A', 'NET_B', '100'),
        Component('C1', 'C', 'NET_B', 'NET_C', '10nF'),
    ]
    assert RCSnubber().match(build_graph(comps)) == []


# --- Bridge Rectifier ---

def test_bridge_rectifier_found():
    comps = [
        Component('D1', 'D', 'AC_POS', 'DC_POS'),
        Component('D2', 'D', 'AC_NEG', 'DC_POS'),
        Component('D3', 'D', 'DC_NEG', 'AC_POS'),
        Component('D4', 'D', 'DC_NEG', 'AC_NEG'),
    ]
    matches = BridgeRectifier().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'D1', 'D2', 'D3', 'D4'}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_patterns.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement `circuit_analyzer/patterns/basic_circuits.py`**

```python
from itertools import combinations
import networkx as nx
from circuit_analyzer.patterns.base import Pattern, is_gnd, is_power


class RCLowPassFilter(Pattern):
    name = "Filtre RC passe-bas"

    def match(self, graph):
        matches = []
        for node in graph.nodes():
            r_edges, c_edges = [], []
            for u, v, data in graph.edges(node, data=True):
                other = v if u == node else u
                if data['type'] == 'R':
                    r_edges.append((other, data['ref']))
                elif data['type'] == 'C':
                    c_edges.append((other, data['ref']))
            for _, r_ref in r_edges:
                for c_other, c_ref in c_edges:
                    if is_gnd(c_other):
                        matches.append({'components': [r_ref, c_ref], 'nodes': [_, node, c_other]})
        return matches


class RCHighPassFilter(Pattern):
    name = "Filtre RC passe-haut"

    def match(self, graph):
        matches = []
        for node in graph.nodes():
            r_edges, c_edges = [], []
            for u, v, data in graph.edges(node, data=True):
                other = v if u == node else u
                if data['type'] == 'R':
                    r_edges.append((other, data['ref']))
                elif data['type'] == 'C':
                    c_edges.append((other, data['ref']))
            for r_other, r_ref in r_edges:
                if is_gnd(r_other):
                    for c_other, c_ref in c_edges:
                        matches.append({'components': [r_ref, c_ref], 'nodes': [c_other, node, r_other]})
        return matches


class LCFilter(Pattern):
    name = "Filtre LC"

    def match(self, graph):
        matches = []
        for node in graph.nodes():
            l_edges, c_edges = [], []
            for u, v, data in graph.edges(node, data=True):
                other = v if u == node else u
                if data['type'] == 'L':
                    l_edges.append((other, data['ref']))
                elif data['type'] == 'C':
                    c_edges.append((other, data['ref']))
            for l_other, l_ref in l_edges:
                for c_other, c_ref in c_edges:
                    if is_gnd(c_other):
                        matches.append({'components': [l_ref, c_ref], 'nodes': [l_other, node, c_other]})
        return matches


class VoltageDivider(Pattern):
    name = "Pont diviseur de tension"

    def match(self, graph):
        matches = []
        seen = set()
        for node in graph.nodes():
            r_edges = []
            for u, v, data in graph.edges(node, data=True):
                other = v if u == node else u
                if data['type'] == 'R':
                    r_edges.append((other, data['ref']))
            for i in range(len(r_edges)):
                for j in range(i + 1, len(r_edges)):
                    other1, ref1 = r_edges[i]
                    other2, ref2 = r_edges[j]
                    if other1 == other2:
                        continue
                    key = frozenset([ref1, ref2])
                    if key not in seen:
                        seen.add(key)
                        matches.append({'components': [ref1, ref2], 'nodes': [other1, node, other2]})
        return matches


class DecouplingCapacitor(Pattern):
    name = "Condensateur de découplage"

    def match(self, graph):
        matches = []
        for u, v, data in graph.edges(data=True):
            if data['type'] != 'C':
                continue
            if (is_power(u) and is_gnd(v)) or (is_gnd(u) and is_power(v)):
                matches.append({'components': [data['ref']], 'nodes': [u, v]})
        return matches


class BridgeRectifier(Pattern):
    name = "Pont redresseur (Graetz)"

    def match(self, graph):
        dg = nx.Graph()
        diode_map = {}
        for u, v, data in graph.edges(data=True):
            if data['type'] == 'D' and not dg.has_edge(u, v):
                dg.add_edge(u, v)
                diode_map[tuple(sorted([u, v]))] = data['ref']

        matches = []
        for combo in combinations(dg.nodes(), 4):
            sub = dg.subgraph(combo)
            if sub.number_of_edges() == 4 and all(sub.degree(n) == 2 for n in combo):
                refs = [diode_map[tuple(sorted([u, v]))] for u, v in sub.edges()]
                matches.append({'components': refs, 'nodes': list(combo)})
        return matches


class FuseProtection(Pattern):
    name = "Protection par fusible"

    def match(self, graph):
        matches = []
        for u, v, data in graph.edges(data=True):
            if data['type'] == 'F':
                matches.append({'components': [data['ref']], 'nodes': [u, v]})
        return matches


class RCSnubber(Pattern):
    name = "Snubber RC"

    def match(self, graph):
        matches = []
        seen = set()
        for node in graph.nodes():
            for u, v, data in graph.edges(node, data=True):
                other = v if u == node else u
                pair = tuple(sorted([node, other]))
                if pair in seen:
                    continue
                seen.add(pair)
                between = [(d['ref'], d['type']) for a, b, d in graph.edges(data=True)
                           if {a, b} == {node, other}]
                r_refs = [ref for ref, t in between if t == 'R']
                c_refs = [ref for ref, t in between if t == 'C']
                if r_refs and c_refs:
                    matches.append({'components': r_refs + c_refs, 'nodes': list(pair)})
        return matches


ALL_PATTERNS = [
    RCLowPassFilter(),
    RCHighPassFilter(),
    LCFilter(),
    VoltageDivider(),
    DecouplingCapacitor(),
    BridgeRectifier(),
    FuseProtection(),
    RCSnubber(),
]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_patterns.py -v
```

Expected: all 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/patterns/base.py circuit_analyzer/patterns/basic_circuits.py tests/test_patterns.py
git commit -m "feat: add 8 basic circuit patterns with graph matching"
```

---

## Task 6: Matcher

**Files:**
- Create: `circuit_analyzer/matcher.py`
- Create: `tests/test_matcher.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_matcher.py`:
```python
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns


def test_matcher_finds_rc_lowpass():
    comps = [
        Component('R1', 'R', 'NET_IN', 'NET_MID', '10k'),
        Component('C1', 'C', 'NET_MID', 'GND', '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Filtre RC passe-bas' in types


def test_matcher_returns_circuit_type_field():
    comps = [Component('F1', 'F', 'LINE_IN', 'NET_FUSE')]
    results = match_patterns(build_graph(comps))
    assert all('circuit_type' in r for r in results)
    assert all('components' in r for r in results)
    assert all('nodes' in r for r in results)


def test_matcher_empty_circuit_returns_empty():
    import networkx as nx
    assert match_patterns(nx.MultiGraph()) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_matcher.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement `circuit_analyzer/matcher.py`**

```python
import networkx as nx
from circuit_analyzer.patterns.basic_circuits import ALL_PATTERNS


def match_patterns(graph: nx.MultiGraph) -> list[dict]:
    results = []
    for pattern in ALL_PATTERNS:
        for match in pattern.match(graph):
            results.append({
                'circuit_type': pattern.name,
                'components': match['components'],
                'nodes': match['nodes'],
            })
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_matcher.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/matcher.py tests/test_matcher.py
git commit -m "feat: add pattern matcher"
```

---

## Task 7: Reporter

**Files:**
- Create: `circuit_analyzer/reporter.py`
- Create: `tests/test_reporter.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_reporter.py`:
```python
from circuit_analyzer.reporter import generate


SAMPLE_RESULTS = [
    {'circuit_type': 'Filtre RC passe-bas', 'components': ['R1', 'C1'], 'nodes': ['NET_IN', 'NET_MID', 'GND']},
    {'circuit_type': 'Pont diviseur de tension', 'components': ['R2', 'R3'], 'nodes': ['VCC', 'NET_DIV', 'GND']},
]


def test_report_contains_header():
    report = generate(SAMPLE_RESULTS, 'circuit.txt', 4)
    assert '=== ANALYSE DU CIRCUIT ===' in report


def test_report_contains_circuit_type():
    report = generate(SAMPLE_RESULTS, 'circuit.txt', 4)
    assert 'Filtre RC passe-bas' in report
    assert 'Pont diviseur de tension' in report


def test_report_contains_components():
    report = generate(SAMPLE_RESULTS, 'circuit.txt', 4)
    assert 'R1' in report
    assert 'C1' in report


def test_report_contains_group_count():
    report = generate(SAMPLE_RESULTS, 'circuit.txt', 4)
    assert 'Groupes identifiés : 2' in report


def test_report_contains_total_components():
    report = generate(SAMPLE_RESULTS, 'circuit.txt', 4)
    assert 'Composants totaux : 4' in report


def test_report_lists_unclassified_components():
    results = [{'circuit_type': 'Filtre RC passe-bas', 'components': ['R1', 'C1'], 'nodes': ['A', 'B', 'GND']}]
    all_refs = ['R1', 'C1', 'U1', 'Q1']
    report = generate(results, 'circuit.txt', 4, all_refs=all_refs)
    assert 'U1' in report
    assert 'Q1' in report
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_reporter.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement `circuit_analyzer/reporter.py`**

```python
def generate(results: list[dict], input_file: str, total_components: int,
             all_refs: list[str] = None, format: str = 'txt') -> str:
    if format == 'txt':
        return _format_txt(results, input_file, total_components, all_refs)
    raise ValueError(f"Format non supporté : {format}")


def _format_txt(results, input_file, total_components, all_refs):
    sep = '-' * 60
    lines = [
        '=== ANALYSE DU CIRCUIT ===',
        f'Fichier           : {input_file}',
        f'Composants totaux : {total_components}',
        f'Groupes identifiés : {len(results)}',
        '',
        sep,
    ]

    classified = set()
    for i, match in enumerate(results, 1):
        lines.append(f'[{i}] {match["circuit_type"]}')
        lines.append(f'    Composants : {", ".join(match["components"])}')
        lines.append(f'    Nœuds     : {" → ".join(match["nodes"])}')
        lines.append('')
        classified.update(match['components'])

    lines.append(sep)

    if all_refs:
        unclassified = [r for r in all_refs if r not in classified]
        if unclassified:
            lines.append(f'\nComposants non classifiés ({len(unclassified)}) :')
            lines.append('    ' + ', '.join(unclassified))

    return '\n'.join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_reporter.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/reporter.py tests/test_reporter.py
git commit -m "feat: add text report generator"
```

---

## Task 8: CLI Entry Point

**Files:**
- Create: `main.py`

- [ ] **Step 1: Create `main.py`**

```python
import argparse
import sys
from pathlib import Path
from circuit_analyzer.parser import parse_file
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.reporter import generate


def main():
    parser = argparse.ArgumentParser(
        description='Analyse un circuit et identifie les sous-circuits de base.'
    )
    parser.add_argument('input', help='Fichier netlist (.txt)')
    parser.add_argument('--output', help='Fichier de sortie (défaut: report.txt)', default='report.txt')
    parser.add_argument('--format', choices=['txt'], default='txt', help='Format de sortie')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Erreur : fichier introuvable : {args.input}", file=sys.stderr)
        sys.exit(1)

    components = parse_file(str(input_path))
    all_refs = [c.ref for c in components]
    graph = build_graph(components)
    results = match_patterns(graph)
    report = generate(results, args.input, len(components), all_refs=all_refs, format=args.format)

    output_path = Path(args.output)
    output_path.write_text(report, encoding='utf-8')

    print(report)
    print(f'\nRapport sauvegardé dans : {output_path}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Test manually with sample circuit**

```bash
python main.py sample_circuit.txt --output report.txt
```

Expected: report printed to terminal, `report.txt` created with identified groups.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add CLI entry point"
```

---

## Task 9: Integration Test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write the integration test**

`tests/test_integration.py`:
```python
import subprocess, sys, os, tempfile
from pathlib import Path


SAMPLE_NETLIST = """\
# Filtre RC passe-bas
R1  NET_IN   NET_MID  10k
C1  NET_MID  GND      100nF

# Pont diviseur
R2  VCC      NET_DIV  10k
R3  NET_DIV  GND      4.7k

# Découplage
C2  VCC      GND      10uF

# Fusible
F1  LINE_IN  NET_FUSE

# Snubber
R4  NET_A    NET_B    100
C3  NET_A    NET_B    10nF

# Pont de Graetz
D1  AC_POS   DC_POS
D2  AC_NEG   DC_POS
D3  DC_NEG   AC_POS
D4  DC_NEG   AC_NEG
"""


def test_full_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        netlist_path = Path(tmpdir) / 'circuit.txt'
        report_path = Path(tmpdir) / 'report.txt'
        netlist_path.write_text(SAMPLE_NETLIST, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, 'main.py', str(netlist_path), '--output', str(report_path)],
            capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        report = report_path.read_text(encoding='utf-8')

        assert 'Filtre RC passe-bas' in report
        assert 'Pont diviseur de tension' in report
        assert 'Condensateur de découplage' in report
        assert 'Protection par fusible' in report
        assert 'Snubber RC' in report
        assert 'Pont redresseur (Graetz)' in report
        assert 'R1' in report
        assert 'C1' in report
```

- [ ] **Step 2: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 3: Final commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration test"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Parser ✓, Graph ✓, 8 patterns ✓, Matcher ✓, Reporter ✓, CLI ✓, extensible format ✓
- [x] **No placeholders:** all steps have real code
- [x] **Type consistency:** `Component` dataclass defined in Task 2, used consistently in Tasks 3–8; `match()` always returns `list[dict]` with `components`/`nodes` keys; `generate()` signature in Task 7 matches usage in Task 8
