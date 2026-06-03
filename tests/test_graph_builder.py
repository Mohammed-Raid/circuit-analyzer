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
