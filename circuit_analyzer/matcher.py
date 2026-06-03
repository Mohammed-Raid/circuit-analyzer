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
