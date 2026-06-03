from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.patterns.transistor import (
    TransistorSwitch, CommonEmitterAmp, CurrentMirror, MosfetSwitch
)


def test_transistor_switch_found():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_DRIVE', '2': 'NET_BASE'}, '10k'),
    ]
    matches = TransistorSwitch().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'Q1', 'R1'}


def test_transistor_switch_not_found_without_base_resistor():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
    ]
    assert TransistorSwitch().match(build_graph(comps)) == []


def test_transistor_switch_not_found_when_emitter_not_gnd():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'NET_EMIT'}),
        Component('R1', 'R', {'1': 'NET_DRIVE', '2': 'NET_BASE'}, '10k'),
    ]
    assert TransistorSwitch().match(build_graph(comps)) == []


def test_common_emitter_found():
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
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R2', 'R', {'1': 'VCC', '2': 'NET_BASE'}, '10k'),
    ]
    assert CommonEmitterAmp().match(build_graph(comps)) == []


def test_current_mirror_found():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL1', 'E': 'GND'}),
        Component('Q2', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL2', 'E': 'GND'}),
    ]
    matches = CurrentMirror().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'Q1', 'Q2'}


def test_current_mirror_not_found_when_bases_differ():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE1', 'C': 'NET_COLL1', 'E': 'GND'}),
        Component('Q2', 'Q', {'B': 'NET_BASE2', 'C': 'NET_COLL2', 'E': 'GND'}),
    ]
    assert CurrentMirror().match(build_graph(comps)) == []


def test_mosfet_switch_found():
    comps = [
        Component('M1', 'M', {'G': 'NET_GATE', 'D': 'NET_DRAIN', 'S': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CTRL', '2': 'NET_GATE'}, '100'),
    ]
    matches = MosfetSwitch().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'M1', 'R1'}


def test_mosfet_switch_not_found_when_source_not_gnd():
    comps = [
        Component('M1', 'M', {'G': 'NET_GATE', 'D': 'NET_DRAIN', 'S': 'NET_SOURCE'}),
        Component('R1', 'R', {'1': 'NET_CTRL', '2': 'NET_GATE'}, '100'),
    ]
    assert MosfetSwitch().match(build_graph(comps)) == []
