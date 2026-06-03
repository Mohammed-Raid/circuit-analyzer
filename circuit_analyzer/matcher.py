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
