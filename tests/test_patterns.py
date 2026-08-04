"""
@file test_patterns.py
@brief Tests des patterns à diodes (les passifs sont devenus des « Impédance Z »).
"""

from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.parser import Component
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


def test_bridge_rectifier_avec_sortie_vcc_gnd_est_detecte():
    """@brief Bug reel (schema_test/5_pont_redresseur.xml) : un pont dont la
    sortie DC est nommee VCC/GND (le cas le plus courant en pratique — c'est
    exactement ce qu'un pont PRODUIT) doit etre detecte. VCC et GND sont sur
    des coins OPPOSES du cycle (jamais relies directement par une seule
    diode) — la signature topologique d'un vrai pont, pas d'un array ESD.
    """
    comps = [
        Component('D1', 'D', {'A': 'AC1', 'K': 'VCC'}),
        Component('D2', 'D', {'A': 'AC2', 'K': 'VCC'}),
        Component('D3', 'D', {'A': 'GND', 'K': 'AC1'}),
        Component('D4', 'D', {'A': 'GND', 'K': 'AC2'}),
    ]
    matches = BridgeRectifier().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'D1', 'D2', 'D3', 'D4'}


def test_diode_directe_entre_vcc_et_gnd_est_flaggee_ambigue():
    """@brief Une diode reliant VCC et GND DIRECTEMENT (coin adjacent du
    cycle) est topologiquement aussi peu credible qu'un vrai pont — mais tout
    aussi indissociable par la seule topologie d'un array ESD. Signalee
    (rails_sur_cycle=True), jamais exclue en silence : voir
    detecter_pont_redresseur et test_industrial_patterns.py pour la
    confiance reduite + l'avertissement assignes en aval par _enrichir."""
    comps = [
        Component('D1', 'D', {'A': 'VCC', 'K': 'GND'}),   # relie les 2 rails directement
        Component('D2', 'D', {'A': 'SIG1', 'K': 'VCC'}),
        Component('D3', 'D', {'A': 'GND', 'K': 'SIG2'}),
        Component('D4', 'D', {'A': 'SIG2', 'K': 'SIG1'}),
    ]
    matches = BridgeRectifier().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['rails_sur_cycle'] is True
