"""
@file test_patterns.py
@brief Tests des patterns à diodes (les passifs sont devenus des « Impédance Z »).
"""

from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.patterns.basic_circuits import BridgeRectifier


def test_bridge_rectifier_found():
    """@brief Vérifie la détection d'un pont redresseur de Graetz.

    @return None
    """
    comps = [
        Component('D1', 'D', {'A': 'AC_POS', 'K': 'DC_POS'}),
        Component('D2', 'D', {'A': 'AC_NEG', 'K': 'DC_POS'}),
        Component('D3', 'D', {'A': 'DC_NEG', 'K': 'AC_POS'}),
        Component('D4', 'D', {'A': 'DC_NEG', 'K': 'AC_NEG'}),
    ]
    matches = BridgeRectifier().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'D1', 'D2', 'D3', 'D4'}
