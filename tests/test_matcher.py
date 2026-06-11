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


def test_matcher_finds_transistor_switch():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_DRIVE', '2': 'NET_BASE'}, '10k'),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Transistor en commutation' in types


def test_matcher_finds_voltage_follower():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_OUT', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Suiveur de tension (AOP)' in types


def test_matcher_loads_custom_patterns(tmp_path, monkeypatch):
    # custom_circuits.json est cherché à la racine de l'application (à côté
    # de l'exe une fois gelée), plus au répertoire courant.
    import json, sys
    custom = [{'name': 'Circuit test', 'components': ['R', 'C'], 'conditions': []}]
    (tmp_path / 'custom_circuits.json').write_text(json.dumps(custom), encoding='utf-8')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'AnalyseurCircuits.exe'))
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Circuit test' in types
