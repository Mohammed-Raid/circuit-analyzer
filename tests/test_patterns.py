from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.patterns.basic_circuits import (
    RCLowPassFilter, RCHighPassFilter, LCFilter,
    VoltageDivider, DecouplingCapacitor, BridgeRectifier,
    FuseProtection, RCSnubber
)


def test_rc_lowpass_found():
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    matches = RCLowPassFilter().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'C1'}


def test_rc_lowpass_not_found_when_c_not_to_gnd():
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'NET_OUT'}, '100nF'),
    ]
    assert RCLowPassFilter().match(build_graph(comps)) == []


def test_rc_highpass_found():
    comps = [
        Component('C1', 'C', {'1': 'NET_IN', '2': 'NET_MID'}, '100nF'),
        Component('R1', 'R', {'1': 'NET_MID', '2': 'GND'}, '10k'),
    ]
    matches = RCHighPassFilter().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'C1'}


def test_rc_highpass_not_found_when_r_not_to_gnd():
    comps = [
        Component('C1', 'C', {'1': 'NET_IN', '2': 'NET_MID'}, '100nF'),
        Component('R1', 'R', {'1': 'NET_MID', '2': 'NET_OUT'}, '10k'),
    ]
    assert RCHighPassFilter().match(build_graph(comps)) == []


def test_lc_filter_found():
    comps = [
        Component('L1', 'L', {'1': 'NET_IN', '2': 'NET_MID'}, '10uH'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    matches = LCFilter().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'L1', 'C1'}


def test_voltage_divider_found():
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_DIV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_DIV', '2': 'GND'}, '4.7k'),
    ]
    matches = VoltageDivider().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'R2'}


def test_voltage_divider_not_found_for_single_resistor():
    comps = [Component('R1', 'R', {'1': 'VCC', '2': 'GND'}, '10k')]
    assert VoltageDivider().match(build_graph(comps)) == []


def test_decoupling_cap_found():
    comps = [Component('C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF')]
    matches = DecouplingCapacitor().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['C1']


def test_decoupling_cap_not_found_between_two_signal_nets():
    comps = [Component('C1', 'C', {'1': 'NET_A', '2': 'NET_B'}, '100nF')]
    assert DecouplingCapacitor().match(build_graph(comps)) == []


def test_fuse_found():
    comps = [Component('F1', 'F', {'1': 'LINE_IN', '2': 'NET_FUSE'})]
    matches = FuseProtection().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['F1']


def test_rc_snubber_found():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '100'),
        Component('C1', 'C', {'1': 'NET_A', '2': 'NET_B'}, '10nF'),
    ]
    matches = RCSnubber().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'C1'}


def test_rc_snubber_not_found_when_not_parallel():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '100'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'NET_C'}, '10nF'),
    ]
    assert RCSnubber().match(build_graph(comps)) == []


def test_bridge_rectifier_found():
    comps = [
        Component('D1', 'D', {'A': 'AC_POS', 'K': 'DC_POS'}),
        Component('D2', 'D', {'A': 'AC_NEG', 'K': 'DC_POS'}),
        Component('D3', 'D', {'A': 'DC_NEG', 'K': 'AC_POS'}),
        Component('D4', 'D', {'A': 'DC_NEG', 'K': 'AC_NEG'}),
    ]
    matches = BridgeRectifier().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'D1', 'D2', 'D3', 'D4'}
