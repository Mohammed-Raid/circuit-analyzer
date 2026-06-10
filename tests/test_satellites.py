"""
test_satellites.py — Tests du rattachement des composants satellites.
"""
import pytest
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.satellites import (
    SEUIL_SUR, SEUIL_POSSIBLE,
    _est_rail, _noeuds_internes, _rails_alim,
)


# =============================================================================
# Helpers de topologie
# =============================================================================

def test_est_rail():
    assert _est_rail('GND')
    assert _est_rail('VCC')
    assert _est_rail('PE')
    assert not _est_rail('NET_BASE')
    assert not _est_rail('')
    assert not _est_rail(None)

def test_noeuds_internes_exclut_les_rails():
    match = {'nodes': ['NET_IN', 'NET_MID', 'GND', 'VCC', '', None]}
    assert _noeuds_internes(match) == {'NET_IN', 'NET_MID'}

def test_rails_alim():
    match = {'nodes': ['NET_IN', 'GND', 'VCC', '+5V']}
    assert _rails_alim(match) == {'VCC', '+5V'}

def test_seuils():
    assert SEUIL_POSSIBLE < SEUIL_SUR
    assert SEUIL_SUR == 0.6
    assert SEUIL_POSSIBLE == 0.3
