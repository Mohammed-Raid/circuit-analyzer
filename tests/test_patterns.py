from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.patterns.basic_circuits import (
    RCLowPassFilter, RCHighPassFilter, LCFilter,
    VoltageDivider, DecouplingCapacitor, BridgeRectifier,
    FuseProtection, RCSnubber
)


# --- RC Low-Pass Filter ---

def test_rc_lowpass_found():
    comps = [
        Component('R1', 'R', 'NET_IN', 'NET_MID', '10k'),
        Component('C1', 'C', 'NET_MID', 'GND', '100nF'),
    ]
    matches = RCLowPassFilter().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'C1'}


def test_rc_lowpass_not_found_when_c_not_to_gnd():
    comps = [
        Component('R1', 'R', 'NET_IN', 'NET_MID', '10k'),
        Component('C1', 'C', 'NET_MID', 'NET_OUT', '100nF'),
    ]
    assert RCLowPassFilter().match(build_graph(comps)) == []


# --- RC High-Pass Filter ---

def test_rc_highpass_found():
    comps = [
        Component('C1', 'C', 'NET_IN', 'NET_MID', '100nF'),
        Component('R1', 'R', 'NET_MID', 'GND', '10k'),
    ]
    matches = RCHighPassFilter().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'C1'}


# --- LC Filter ---

def test_lc_filter_found():
    comps = [
        Component('L1', 'L', 'NET_IN', 'NET_MID', '10uH'),
        Component('C1', 'C', 'NET_MID', 'GND', '100nF'),
    ]
    matches = LCFilter().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'L1', 'C1'}


# --- Voltage Divider ---

def test_voltage_divider_found():
    comps = [
        Component('R1', 'R', 'VCC', 'NET_DIV', '10k'),
        Component('R2', 'R', 'NET_DIV', 'GND', '4.7k'),
    ]
    matches = VoltageDivider().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'R2'}


def test_voltage_divider_not_found_for_single_resistor():
    comps = [Component('R1', 'R', 'VCC', 'GND', '10k')]
    assert VoltageDivider().match(build_graph(comps)) == []


# --- Decoupling Capacitor ---

def test_decoupling_cap_found():
    comps = [Component('C1', 'C', 'VCC', 'GND', '100nF')]
    matches = DecouplingCapacitor().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['C1']


def test_decoupling_cap_not_found_between_two_signal_nets():
    comps = [Component('C1', 'C', 'NET_A', 'NET_B', '100nF')]
    assert DecouplingCapacitor().match(build_graph(comps)) == []


# --- Fuse Protection ---

def test_fuse_found():
    comps = [Component('F1', 'F', 'LINE_IN', 'NET_FUSE')]
    matches = FuseProtection().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['F1']


# --- RC Snubber ---

def test_rc_snubber_found():
    comps = [
        Component('R1', 'R', 'NET_A', 'NET_B', '100'),
        Component('C1', 'C', 'NET_A', 'NET_B', '10nF'),
    ]
    matches = RCSnubber().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'C1'}


def test_rc_snubber_not_found_when_not_parallel():
    comps = [
        Component('R1', 'R', 'NET_A', 'NET_B', '100'),
        Component('C1', 'C', 'NET_B', 'NET_C', '10nF'),
    ]
    assert RCSnubber().match(build_graph(comps)) == []


# --- Bridge Rectifier ---

def test_bridge_rectifier_found():
    comps = [
        Component('D1', 'D', 'AC_POS', 'DC_POS'),
        Component('D2', 'D', 'AC_NEG', 'DC_POS'),
        Component('D3', 'D', 'DC_NEG', 'AC_POS'),
        Component('D4', 'D', 'DC_NEG', 'AC_NEG'),
    ]
    matches = BridgeRectifier().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'D1', 'D2', 'D3', 'D4'}
