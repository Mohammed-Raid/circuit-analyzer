from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.patterns.opamp import (
    Differentiator, SchmittTrigger, DifferentialAmplifier, SummingAmplifier, Comparator,
)
from circuit_analyzer.patterns.basic_circuits import HalfWaveRectifier, PeakDetector


# --- Dérivateur ---

def test_differentiator_found():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('C1', 'C', {'1': 'NET_IN', '2': 'NET_INM'}, '10nF'),
        Component('R1', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '10k'),
    ]
    matches = Differentiator().match(build_graph(comps))
    assert len(matches) == 1
    assert 'U1' in matches[0]['components']
    assert 'C1' in matches[0]['components']
    assert 'R1' in matches[0]['components']


def test_differentiator_not_found_without_input_cap():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('R1', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '10k'),
    ]
    assert Differentiator().match(build_graph(comps)) == []


def test_differentiator_not_found_without_feedback_r():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('C1', 'C', {'1': 'NET_IN', '2': 'NET_INM'}, '10nF'),
    ]
    assert Differentiator().match(build_graph(comps)) == []


# --- Trigger de Schmitt ---

def test_schmitt_trigger_found():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_INP', 'IN-': 'NET_REF', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_INP', '2': 'NET_OUT'}, '100k'),
    ]
    matches = SchmittTrigger().match(build_graph(comps))
    assert len(matches) == 1
    assert 'U1' in matches[0]['components']
    assert 'R1' in matches[0]['components']


def test_schmitt_trigger_not_found_without_positive_feedback():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_INP', 'IN-': 'NET_REF', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
    ]
    assert SchmittTrigger().match(build_graph(comps)) == []


def test_comparator_not_found_when_schmitt_trigger():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_INP', 'IN-': 'NET_REF', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_INP', '2': 'NET_OUT'}, '100k'),
    ]
    assert Comparator().match(build_graph(comps)) == []


# --- Amplificateur différentiel ---

def test_differential_amp_found():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_INP', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN1', '2': 'NET_INP'}, '10k'),
        Component('R2', 'R', {'1': 'NET_INP', '2': 'GND'}, '10k'),
        Component('R3', 'R', {'1': 'NET_IN2', '2': 'NET_INM'}, '10k'),
        Component('R4', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '100k'),
    ]
    matches = DifferentialAmplifier().match(build_graph(comps))
    assert len(matches) == 1
    assert 'U1' in matches[0]['components']
    assert 'R1' in matches[0]['components']
    assert 'R2' in matches[0]['components']
    assert 'R3' in matches[0]['components']
    assert 'R4' in matches[0]['components']


def test_differential_amp_not_found_without_gnd_resistor_at_inp():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_INP', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN1', '2': 'NET_INP'}, '10k'),
        Component('R3', 'R', {'1': 'NET_IN2', '2': 'NET_INM'}, '10k'),
        Component('R4', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '100k'),
    ]
    assert DifferentialAmplifier().match(build_graph(comps)) == []


# --- Amplificateur sommateur ---

def test_summing_amp_found():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_INM'}, '10k'),
        Component('R2', 'R', {'1': 'NET_B', '2': 'NET_INM'}, '10k'),
        Component('R3', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '20k'),
    ]
    matches = SummingAmplifier().match(build_graph(comps))
    assert len(matches) == 1
    assert 'U1' in matches[0]['components']
    assert 'R1' in matches[0]['components']
    assert 'R2' in matches[0]['components']
    assert 'R3' in matches[0]['components']


def test_summing_amp_not_found_with_single_input():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_INM'}, '10k'),
        Component('R2', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '20k'),
    ]
    assert SummingAmplifier().match(build_graph(comps)) == []


# --- Redresseur simple alternance ---

def test_half_wave_rectifier_found():
    comps = [
        Component('D1', 'D', {'A': 'NET_AC', 'K': 'NET_DC'}),
        Component('R1', 'R', {'1': 'NET_DC', '2': 'GND'}, '1k'),
    ]
    matches = HalfWaveRectifier().match(build_graph(comps))
    assert len(matches) == 1
    assert 'D1' in matches[0]['components']
    assert 'R1' in matches[0]['components']


def test_half_wave_rectifier_not_found_without_load():
    comps = [
        Component('D1', 'D', {'A': 'NET_AC', 'K': 'NET_DC'}),
    ]
    assert HalfWaveRectifier().match(build_graph(comps)) == []


# --- Détecteur de crête ---

def test_peak_detector_found():
    comps = [
        Component('D1', 'D', {'A': 'NET_IN', 'K': 'NET_PEAK'}),
        Component('C1', 'C', {'1': 'NET_PEAK', '2': 'GND'}, '10uF'),
    ]
    matches = PeakDetector().match(build_graph(comps))
    assert len(matches) == 1
    assert 'D1' in matches[0]['components']
    assert 'C1' in matches[0]['components']


def test_peak_detector_not_found_without_cap():
    comps = [
        Component('D1', 'D', {'A': 'NET_IN', 'K': 'NET_PEAK'}),
        Component('R1', 'R', {'1': 'NET_PEAK', '2': 'GND'}, '10k'),
    ]
    assert PeakDetector().match(build_graph(comps)) == []
