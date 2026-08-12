"""
@file test_matcher.py
@brief Tests automatises pour test_matcher.
"""

from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.parser import Component


def test_matcher_finds_rc_lowpass():
    """@brief Verifie matcher finds rc lowpass.

    Les passifs isolés sont désormais classifiés comme « Impédance Z » par le
    moteur Z — le nom « Filtre RC passe-bas » n'est plus émis par analyser().
    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Impédance Z' in types
    assert 'Filtre RC passe-bas' not in types


def test_diode_isolee_hors_rail_devient_non_classifiee():
    """@brief Une diode entre deux nœuds signal (ni rail ni bord d'un pont)
    ne correspond a AUCUN des 5 patterns diode (tous exigent un rail/GND ou
    un cycle a 4). Contrairement a R/L/C (-> Impedance Z), elle disparaissait
    en silence, sans meme un statut "non classifie" — bug reel trouve sur
    de vraies cartes (D1-D4 de PG 3.xml). Meme philosophie que les
    impedances : jamais de diode non representee du tout."""
    comps = [
        Component('D1', 'D', {'A': 'NET_A', 'K': 'NET_B'}),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Diode non classifiée' in types
    d1 = next(r for r in results if r['circuit_type'] == 'Diode non classifiée')
    assert d1['components'] == ['D1']


def test_matcher_returns_circuit_type_field():
    """@brief Verifie matcher returns circuit type field.

    @return None
    """
    comps = [Component('F1', 'F', {'1': 'LINE_IN', '2': 'NET_FUSE'})]
    results = match_patterns(build_graph(comps))
    assert all('circuit_type' in r for r in results)
    assert all('components' in r for r in results)
    assert all('nodes' in r for r in results)


def test_matcher_empty_circuit_returns_empty():
    """@brief Verifie matcher empty circuit returns empty.

    @return None
    """
    import networkx as nx
    assert match_patterns(nx.MultiGraph()) == []


def test_matcher_finds_transistor_switch():
    """@brief Verifie matcher finds transistor switch.

    @return None
    """
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_DRIVE', '2': 'NET_BASE'}, '10k'),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Transistor en commutation' in types


def test_matcher_finds_voltage_follower():
    """@brief Verifie matcher finds voltage follower.

    @return None
    """
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_OUT', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Suiveur de tension (AOP)' in types


def test_matcher_loads_custom_patterns(tmp_path, monkeypatch):
    """@brief Verifie matcher loads custom patterns.

    @return None
    """
    # custom_circuits.json est cherché à la racine de l'application (à côté
    # de l'exe une fois gelée), plus au répertoire courant.
    import json
    import sys
    custom = [{'name': 'Circuit test', 'components': ['R', 'C'], 'conditions': []}]
    (tmp_path / 'custom_circuits.json').write_text(json.dumps(custom), encoding='utf-8')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'AnalyseurCircuits.exe'))
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Circuit test' in types
