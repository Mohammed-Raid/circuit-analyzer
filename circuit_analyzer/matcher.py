import networkx as nx
from circuit_analyzer.patterns.basic_circuits import ALL_PATTERNS as BASIC_PATTERNS
from circuit_analyzer.patterns.transistor import TRANSISTOR_PATTERNS
from circuit_analyzer.patterns.opamp import OPAMP_PATTERNS

_BUILTIN_PATTERNS = BASIC_PATTERNS + TRANSISTOR_PATTERNS + OPAMP_PATTERNS


def match_patterns(graph: nx.MultiGraph) -> list[dict]:
    try:
        from custom_circuits.loader import get_custom_patterns
        all_patterns = _BUILTIN_PATTERNS + get_custom_patterns()
    except ImportError:
        all_patterns = _BUILTIN_PATTERNS

    results = []
    for pattern in all_patterns:
        for match in pattern.match(graph):
            results.append({
                'circuit_type': pattern.name,
                'components': match['components'],
                'nodes': match['nodes'],
            })
    return results
