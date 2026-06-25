"""
@file test_transistor_patterns.py
@brief Tests automatises pour test_transistor_patterns.
"""

from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.patterns.transistor import (
    TransistorSwitch, CommonEmitterAmp, CurrentMirror, MosfetSwitch, SuiveurEmetteur,
    PushPull, Darlington
)


def test_push_pull_found():
    # NPN (C=VCC) + PNP (C=GND), émetteurs communs (sortie), bases communes (entrée).
    comps = [
        Component('Q1', 'Q', {'B': 'NIN', 'C': 'VCC', 'E': 'NOUT'}),
        Component('Q2', 'Q', {'B': 'NIN', 'C': 'GND', 'E': 'NOUT'}),
    ]
    matches = PushPull().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'Q1', 'Q2'}


def test_push_pull_not_found_when_emitters_differ():
    comps = [
        Component('Q1', 'Q', {'B': 'NIN', 'C': 'VCC', 'E': 'O1'}),
        Component('Q2', 'Q', {'B': 'NIN', 'C': 'GND', 'E': 'O2'}),
    ]
    assert PushPull().match(build_graph(comps)) == []


def test_darlington_found():
    # Émetteur de Q1 relié à la base de Q2, collecteurs communs.
    comps = [
        Component('Q1', 'Q', {'B': 'NB', 'C': 'VCC', 'E': 'NE1'}),
        Component('Q2', 'Q', {'B': 'NE1', 'C': 'VCC', 'E': 'NOUT'}),
    ]
    matches = Darlington().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'Q1', 'Q2'}


def test_darlington_not_found_when_emitter_not_to_base():
    comps = [
        Component('Q1', 'Q', {'B': 'NB', 'C': 'VCC', 'E': 'NE1'}),
        Component('Q2', 'Q', {'B': 'NB2', 'C': 'VCC', 'E': 'NOUT'}),
    ]
    assert Darlington().match(build_graph(comps)) == []


def _follower_comps():
    # Collecteur commun : collecteur sur VCC, sortie sur l'émetteur via Re vers GND,
    # base polarisée vers VCC.
    return [
        Component('Q1', 'Q', {'B': 'NB', 'C': 'VCC', 'E': 'NOUT'}),
        Component('R1', 'R', {'1': 'NB', '2': 'VCC'}, '47k'),
        Component('Re', 'R', {'1': 'NOUT', '2': 'GND'}, '1k'),
    ]


def test_suiveur_emetteur_found():
    matches = SuiveurEmetteur().match(build_graph(_follower_comps()))
    assert len(matches) == 1
    assert 'Q1' in matches[0]['components']
    assert 'Re' in matches[0]['components']


def test_suiveur_emetteur_pas_classe_en_emetteur_commun():
    # Le faux positif corrigé : un suiveur ne doit plus matcher l'émetteur commun.
    assert CommonEmitterAmp().match(build_graph(_follower_comps())) == []


def test_suiveur_emetteur_not_found_without_re():
    comps = [
        Component('Q1', 'Q', {'B': 'NB', 'C': 'VCC', 'E': 'NOUT'}),
        Component('R1', 'R', {'1': 'NB', '2': 'VCC'}, '47k'),
    ]
    assert SuiveurEmetteur().match(build_graph(comps)) == []


def test_transistor_switch_found():
    """@brief Verifie transistor switch found.

    @return None
    """
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_DRIVE', '2': 'NET_BASE'}, '10k'),
    ]
    matches = TransistorSwitch().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'Q1', 'R1'}


def test_transistor_switch_not_found_without_base_resistor():
    """@brief Verifie transistor switch not found without base resistor.

    @return None
    """
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
    ]
    assert TransistorSwitch().match(build_graph(comps)) == []


def test_transistor_switch_not_found_when_emitter_not_gnd():
    """@brief Verifie transistor switch not found when emitter not gnd.

    @return None
    """
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'NET_EMIT'}),
        Component('R1', 'R', {'1': 'NET_DRIVE', '2': 'NET_BASE'}, '10k'),
    ]
    assert TransistorSwitch().match(build_graph(comps)) == []


def test_common_emitter_found():
    """@brief Verifie common emitter found.

    @return None
    """
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_COLL'}, '1k'),
        Component('R2', 'R', {'1': 'VCC', '2': 'NET_BASE'}, '10k'),
    ]
    matches = CommonEmitterAmp().match(build_graph(comps))
    assert len(matches) == 1
    assert 'Q1' in matches[0]['components']
    assert 'R1' in matches[0]['components']
    assert 'R2' in matches[0]['components']


def test_common_emitter_not_found_without_collector_resistor():
    """@brief Verifie common emitter not found without collector resistor.

    @return None
    """
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R2', 'R', {'1': 'VCC', '2': 'NET_BASE'}, '10k'),
    ]
    assert CommonEmitterAmp().match(build_graph(comps)) == []


def test_current_mirror_found():
    """@brief Verifie current mirror found.

    @return None
    """
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL1', 'E': 'GND'}),
        Component('Q2', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL2', 'E': 'GND'}),
    ]
    matches = CurrentMirror().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'Q1', 'Q2'}


def test_current_mirror_not_found_when_bases_differ():
    """@brief Verifie current mirror not found when bases differ.

    @return None
    """
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE1', 'C': 'NET_COLL1', 'E': 'GND'}),
        Component('Q2', 'Q', {'B': 'NET_BASE2', 'C': 'NET_COLL2', 'E': 'GND'}),
    ]
    assert CurrentMirror().match(build_graph(comps)) == []


def test_mosfet_switch_found():
    """@brief Verifie mosfet switch found.

    @return None
    """
    comps = [
        Component('M1', 'M', {'G': 'NET_GATE', 'D': 'NET_DRAIN', 'S': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CTRL', '2': 'NET_GATE'}, '100'),
    ]
    matches = MosfetSwitch().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'M1', 'R1'}


def test_mosfet_switch_not_found_when_source_not_gnd():
    """@brief Verifie mosfet switch not found when source not gnd.

    @return None
    """
    comps = [
        Component('M1', 'M', {'G': 'NET_GATE', 'D': 'NET_DRAIN', 'S': 'NET_SOURCE'}),
        Component('R1', 'R', {'1': 'NET_CTRL', '2': 'NET_GATE'}, '100'),
    ]
    assert MosfetSwitch().match(build_graph(comps)) == []
