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
