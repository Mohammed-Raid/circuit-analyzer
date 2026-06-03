from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.patterns.opamp import (
    InvertingAmplifier, NonInvertingAmplifier, VoltageFollower,
    Integrator, Comparator
)


def test_inverting_amp_found():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INM'}, '10k'),
        Component('R2', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '100k'),
    ]
    matches = InvertingAmplifier().match(build_graph(comps))
    assert len(matches) == 1
    assert 'U1' in matches[0]['components']
    assert 'R1' in matches[0]['components']
    assert 'R2' in matches[0]['components']


def test_inverting_amp_not_found_without_feedback():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INM'}, '10k'),
    ]
    assert InvertingAmplifier().match(build_graph(comps)) == []


def test_non_inverting_amp_found():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '100k'),
        Component('R2', 'R', {'1': 'NET_INM', '2': 'GND'}, '10k'),
    ]
    matches = NonInvertingAmplifier().match(build_graph(comps))
    assert len(matches) == 1
    assert 'U1' in matches[0]['components']
    assert 'R1' in matches[0]['components']
    assert 'R2' in matches[0]['components']


def test_non_inverting_amp_not_found_without_gnd_resistor():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '100k'),
    ]
    assert NonInvertingAmplifier().match(build_graph(comps)) == []


def test_voltage_follower_found():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_OUT', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
    ]
    matches = VoltageFollower().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['U1']


def test_voltage_follower_not_found_when_no_direct_feedback():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
    ]
    assert VoltageFollower().match(build_graph(comps)) == []


def test_integrator_found():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INM'}, '10k'),
        Component('C1', 'C', {'1': 'NET_INM', '2': 'NET_OUT'}, '10nF'),
    ]
    matches = Integrator().match(build_graph(comps))
    assert len(matches) == 1
    assert 'U1' in matches[0]['components']
    assert 'R1' in matches[0]['components']
    assert 'C1' in matches[0]['components']


def test_integrator_not_found_without_feedback_cap():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INM'}, '10k'),
    ]
    assert Integrator().match(build_graph(comps)) == []


def test_comparator_found():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_REF', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
    ]
    matches = Comparator().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['U1']


def test_comparator_not_found_when_follower():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_OUT', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
    ]
    assert Comparator().match(build_graph(comps)) == []


def test_comparator_not_found_when_feedback_resistor_present():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '100k'),
    ]
    assert Comparator().match(build_graph(comps)) == []
