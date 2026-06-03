import networkx as nx
from circuit_analyzer.parser import Component


def build_graph(components: list[Component]) -> nx.MultiGraph:
    G = nx.MultiGraph()
    for comp in components:
        G.add_edge(comp.net1, comp.net2, ref=comp.ref, type=comp.type, value=comp.value)
    return G
