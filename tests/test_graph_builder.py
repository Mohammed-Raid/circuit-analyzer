"""
@file test_graph_builder.py
@brief Tests automatises pour test_graph_builder.
"""

from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph


def test_nodes_are_nets():
    """@brief Verifie nodes are nets.

    @return None
    """
    comps = [Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k')]
    G = build_graph(comps)
    assert 'NET_A' in G.nodes
    assert 'NET_B' in G.nodes


def test_edge_has_component_attributes():
    """@brief Verifie edge has component attributes.

    @return None
    """
    comps = [Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k')]
    G = build_graph(comps)
    edges = list(G.edges(data=True))
    assert len(edges) == 1
    data = edges[0][2]
    assert data['ref'] == 'R1'
    assert data['type'] == 'R'
    assert data['value'] == '10k'


def test_multiple_components_between_same_nodes():
    """@brief Verifie multiple components between same nodes.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_A', '2': 'NET_B'}, '100nF'),
    ]
    G = build_graph(comps)
    assert G.number_of_edges() == 2


def test_shared_node():
    """@brief Verifie shared node.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    G = build_graph(comps)
    assert 'NET_MID' in G.nodes
    assert G.degree('NET_MID') == 2


def test_components_dict_stored_in_graph():
    """@brief Verifie components dict stored in graph.

    @return None
    """
    comps = [Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k')]
    G = build_graph(comps)
    assert 'R1' in G.graph['components']
    assert G.graph['components']['R1'].ref == 'R1'


def test_multipin_component_adds_nodes_not_edges():
    """@brief Verifie multipin component adds nodes not edges.

    @return None
    """
    comps = [Component('Q1', 'Q', {'B': 'NET_B', 'C': 'NET_C', 'E': 'GND'})]
    G = build_graph(comps)
    assert G.number_of_edges() == 0
    assert 'NET_B' in G.nodes
    assert 'NET_C' in G.nodes
    assert 'GND' in G.nodes


def test_mixed_two_and_multipin():
    """@brief Verifie mixed two and multipin.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('Q1', 'Q', {'B': 'NET_B', 'C': 'NET_C', 'E': 'GND'}),
    ]
    G = build_graph(comps)
    assert G.number_of_edges() == 1
    assert 'Q1' in G.graph['components']
    assert 'R1' in G.graph['components']
