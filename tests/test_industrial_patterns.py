"""
@file test_industrial_patterns.py
@brief Tests automatises pour test_industrial_patterns.
"""

"""Tests for new industrial patterns: FlybackDiode, ESDProtectionDiode,
HighSideMosfet, RelayDriver, and BridgeRectifier ESD-exclusion fix."""
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.patterns.basic_circuits import (
    FlybackDiode, ESDProtectionDiode, HalfWaveRectifier, PeakDetector,
    BridgeRectifier,
)
from circuit_analyzer.patterns.transistor import HighSideMosfet, RelayDriver


# ---------------------------------------------------------------------------
# FlybackDiode
# ---------------------------------------------------------------------------

def test_flyback_diode_found():
    """@brief Verifie flyback diode found.

    @return None
    """
    comps = [
        Component('D1', 'D', {'A': '/COL_Q1', 'K': '/VCC_12V'}),
    ]
    matches = FlybackDiode().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['D1']


def test_flyback_diode_not_found_when_cathode_not_power():
    """@brief Verifie flyback diode not found when cathode not power.

    @return None
    """
    comps = [
        Component('D1', 'D', {'A': '/COL_Q1', 'K': '/SW_NODE'}),
    ]
    assert FlybackDiode().match(build_graph(comps)) == []


def test_flyback_diode_not_found_when_anode_at_gnd():
    """@brief Verifie flyback diode not found when anode at gnd.

    @return None
    """
    # Anode at GND = ESD clamp, not flyback
    comps = [
        Component('D1', 'D', {'A': '/PGND', 'K': '/VCC_12V'}),
    ]
    assert FlybackDiode().match(build_graph(comps)) == []


# ---------------------------------------------------------------------------
# ESDProtectionDiode
# ---------------------------------------------------------------------------

def test_esd_low_side_clamp_found():
    """@brief Verifie esd low side clamp found.

    @return None
    """
    # Anode at GND, cathode at signal
    comps = [Component('D1', 'D', {'A': '/AGND', 'K': '/SIG_P'})]
    matches = ESDProtectionDiode().match(build_graph(comps))
    assert len(matches) == 1
    assert matches[0]['components'] == ['D1']


def test_esd_cathode_to_gnd_found():
    """@brief Verifie esd cathode to gnd found.

    @return None
    """
    # Anode at signal, cathode at GND (Zener shunt)
    comps = [Component('D1', 'D', {'A': '/SIG', 'K': '/GND'})]
    matches = ESDProtectionDiode().match(build_graph(comps))
    assert len(matches) == 1


def test_esd_power_to_gnd_zener():
    """@brief Verifie esd power to gnd zener.

    @return None
    """
    # Anode at power rail, cathode at GND (reverse TVS)
    comps = [Component('D1', 'D', {'A': '/VCC', 'K': '/GND'})]
    matches = ESDProtectionDiode().match(build_graph(comps))
    assert len(matches) == 1


def test_esd_not_found_for_signal_to_signal():
    """@brief Verifie esd not found for signal to signal.

    @return None
    """
    # Neither pin at GND or power
    comps = [Component('D1', 'D', {'A': '/SIG_A', 'K': '/SIG_B'})]
    assert ESDProtectionDiode().match(build_graph(comps)) == []


# ---------------------------------------------------------------------------
# HalfWaveRectifier — exclusion tests
# ---------------------------------------------------------------------------

def test_half_wave_not_found_for_flyback_diode():
    """@brief Verifie half wave not found for flyback diode.

    @return None
    """
    # Cathode at power rail = flyback, not rectifier
    comps = [
        Component('D1', 'D', {'A': '/COL_Q1', 'K': '/VCC_12V'}),
        Component('R1', 'R', {'1': '/VCC_12V', '2': '/GND'}, '1k'),
    ]
    assert HalfWaveRectifier().match(build_graph(comps)) == []


def test_half_wave_not_found_when_anode_at_gnd():
    """@brief Verifie half wave not found when anode at gnd.

    @return None
    """
    # Anode at GND = ESD clamp, not rectifier
    comps = [
        Component('D1', 'D', {'A': '/GND', 'K': '/SIG_NODE'}),
        Component('R1', 'R', {'1': '/SIG_NODE', '2': '/GND'}, '1k'),
    ]
    assert HalfWaveRectifier().match(build_graph(comps)) == []


def test_half_wave_not_found_when_anode_at_power():
    """@brief Verifie half wave not found when anode at power.

    @return None
    """
    # Anode at power = forward-biased indicator (LED), not rectifier
    comps = [
        Component('D1', 'D', {'A': '/VCC', 'K': '/LED_A'}),
        Component('R1', 'R', {'1': '/LED_A', '2': '/GND'}, '1k'),
    ]
    assert HalfWaveRectifier().match(build_graph(comps)) == []


def test_half_wave_found_for_valid_rectifier():
    """@brief Verifie half wave found for valid rectifier.

    @return None
    """
    comps = [
        Component('D1', 'D', {'A': '/AC_IN', 'K': '/DC_OUT'}),
        Component('R1', 'R', {'1': '/DC_OUT', '2': '/GND'}, '100'),
    ]
    matches = HalfWaveRectifier().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'D1', 'R1'}


# ---------------------------------------------------------------------------
# PeakDetector — exclusion tests
# ---------------------------------------------------------------------------

def test_peak_detector_not_found_for_flyback_diode():
    """@brief Verifie peak detector not found for flyback diode.

    @return None
    """
    comps = [
        Component('D1', 'D', {'A': '/COL_Q1', 'K': '/VCC_12V'}),
        Component('C1', 'C', {'1': '/VCC_12V', '2': '/GND'}, '100nF'),
    ]
    assert PeakDetector().match(build_graph(comps)) == []


def test_peak_detector_not_found_when_anode_at_gnd():
    """@brief Verifie peak detector not found when anode at gnd.

    @return None
    """
    comps = [
        Component('D1', 'D', {'A': '/GND', 'K': '/SIG_NODE'}),
        Component('C1', 'C', {'1': '/SIG_NODE', '2': '/GND'}, '100nF'),
    ]
    assert PeakDetector().match(build_graph(comps)) == []


def test_peak_detector_found_for_valid_topology():
    """@brief Verifie peak detector found for valid topology.

    @return None
    """
    comps = [
        Component('D1', 'D', {'A': '/SIG_IN', 'K': '/PEAK_HOLD'}),
        Component('C1', 'C', {'1': '/PEAK_HOLD', '2': '/GND'}, '10nF'),
    ]
    matches = PeakDetector().match(build_graph(comps))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'D1', 'C1'}


# ---------------------------------------------------------------------------
# BridgeRectifier — ESD exclusion test
# ---------------------------------------------------------------------------

def test_bridge_rectifier_not_found_for_esd_clamp_array():
    """@brief Verifie bridge rectifier not found for esd clamp array.

    @return None
    """
    # 4 ESD diodes: two clamp to AVCC, two from AGND — same 4-node cycle
    comps = [
        Component('D1', 'D', {'A': '/SIG_P', 'K': '/AVCC'}),
        Component('D2', 'D', {'A': '/AGND', 'K': '/SIG_P'}),
        Component('D3', 'D', {'A': '/SIG_N', 'K': '/AVCC'}),
        Component('D4', 'D', {'A': '/AGND', 'K': '/SIG_N'}),
    ]
    matches = BridgeRectifier().match(build_graph(comps))
    assert matches == [], f"Expected no match but got: {matches}"


def test_bridge_rectifier_found_for_valid_graetz():
    """@brief Verifie bridge rectifier found for valid graetz.

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


# ---------------------------------------------------------------------------
# HighSideMosfet
# ---------------------------------------------------------------------------

def test_high_side_mosfet_found():
    """@brief Verifie high side mosfet found.

    @return None
    """
    comps = [
        Component('M1', 'M', {'G': '/GATE_H', 'D': '/VIN_24V', 'S': '/SW_NODE'}),
        Component('R1', 'R', {'1': '/GATE_DRV', '2': '/GATE_H'}, '10'),
    ]
    matches = HighSideMosfet().match(build_graph(comps))
    assert len(matches) == 1
    assert 'M1' in matches[0]['components']
    assert 'R1' in matches[0]['components']


def test_high_side_mosfet_not_found_when_source_at_gnd():
    """@brief Verifie high side mosfet not found when source at gnd.

    @return None
    """
    # Source at GND = low-side, handled by MosfetSwitch
    comps = [
        Component('M1', 'M', {'G': '/GATE_L', 'D': '/DRAIN', 'S': '/GND'}),
        Component('R1', 'R', {'1': '/GATE_DRV', '2': '/GATE_L'}, '10'),
    ]
    assert HighSideMosfet().match(build_graph(comps)) == []


def test_high_side_mosfet_not_found_without_gate_resistor():
    """@brief Verifie high side mosfet not found without gate resistor.

    @return None
    """
    comps = [
        Component('M1', 'M', {'G': '/GATE_H', 'D': '/VIN_24V', 'S': '/SW_NODE'}),
    ]
    assert HighSideMosfet().match(build_graph(comps)) == []


def test_high_side_mosfet_not_found_when_drain_not_power():
    """@brief Verifie high side mosfet not found when drain not power.

    @return None
    """
    # Drain not at power rail — this is not a high-side switch
    comps = [
        Component('M1', 'M', {'G': '/GATE_H', 'D': '/SW_NODE', 'S': '/MID_HB'}),
        Component('R1', 'R', {'1': '/GATE_DRV', '2': '/GATE_H'}, '10'),
    ]
    assert HighSideMosfet().match(build_graph(comps)) == []


# ---------------------------------------------------------------------------
# RelayDriver
# ---------------------------------------------------------------------------

def test_relay_driver_bjt_found():
    """@brief Verifie relay driver bjt found.

    @return None
    """
    comps = [
        Component('K1', 'K', {'A1': '/VCC_12V', 'A2': '/COL_Q1',
                               '11': '/COM', '12': '/NC', '14': '/NO'}),
        Component('Q1', 'Q', {'B': '/BASE_Q1', 'C': '/COL_Q1', 'E': '/GND'}),
        Component('R1', 'R', {'1': '/CTRL', '2': '/BASE_Q1'}, '4.7k'),
    ]
    matches = RelayDriver().match(build_graph(comps))
    assert len(matches) == 1
    assert 'K1' in matches[0]['components']
    assert 'Q1' in matches[0]['components']


def test_relay_driver_mosfet_found():
    """@brief Verifie relay driver mosfet found.

    @return None
    """
    comps = [
        Component('K1', 'K', {'A1': '/VCC_12V', 'A2': '/DRAIN_M1',
                               '11': '/COM', '12': '/NC', '14': '/NO'}),
        Component('M1', 'M', {'G': '/GATE_M1', 'D': '/DRAIN_M1', 'S': '/GND'}),
    ]
    matches = RelayDriver().match(build_graph(comps))
    assert len(matches) == 1
    assert 'K1' in matches[0]['components']
    assert 'M1' in matches[0]['components']


def test_relay_driver_not_found_without_transistor():
    """@brief Verifie relay driver not found without transistor.

    @return None
    """
    comps = [
        Component('K1', 'K', {'A1': '/VCC_12V', 'A2': '/COL_Q1',
                               '11': '/COM', '12': '/NC', '14': '/NO'}),
    ]
    assert RelayDriver().match(build_graph(comps)) == []


def test_relay_driver_not_found_when_coil_directly_to_gnd():
    """@brief Verifie relay driver not found when coil directly to gnd.

    @return None
    """
    # A1=power, A2=GND: no transistor in series with coil
    comps = [
        Component('K1', 'K', {'A1': '/VCC_12V', 'A2': '/GND',
                               '11': '/COM', '12': '/NC', '14': '/NO'}),
        Component('Q1', 'Q', {'B': '/BASE', 'C': '/COLLECTOR', 'E': '/GND'}),
    ]
    assert RelayDriver().match(build_graph(comps)) == []
