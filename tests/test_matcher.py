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
