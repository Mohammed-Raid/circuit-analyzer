"""
Tests for the 4 refactoring points:
  1. Lexical normalization (upper + strip spaces)
  2. Dimensional validation with exceptions
  3. Duplicate reference detection with exceptions
  4. Hierarchical resolution + component locking (mutex)
"""
import os, tempfile, pytest
from circuit_analyzer.parser import parse_file, Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns


def _write_tmp(content):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
    f.write(content)
    f.close()
    return f.name


# ── Point 1: Lexical normalization ────────────────────────────────────────────

def test_lowercase_node_names_normalized():
    path = _write_tmp("R1 vcc gnd 10k\n")
    comps = parse_file(path)
    os.unlink(path)
    assert comps[0].net1 == 'VCC'
    assert comps[0].net2 == 'GND'


def test_mixed_case_node_names_normalized():
    path = _write_tmp("C1 Net_Mid Gnd 100nF\n")
    comps = parse_file(path)
    os.unlink(path)
    assert comps[0].net1 == 'NET_MID'
    assert comps[0].net2 == 'GND'


def test_normalization_makes_nets_comparable():
    # vcc and VCC should resolve to the same net in the graph
    path = _write_tmp("R1 vcc net_a 10k\nC1 NET_A GND 10nF\n")
    comps = parse_file(path)
    os.unlink(path)
    graph = build_graph(comps)
    # Both R1 and C1 share NET_A after normalization
    assert 'NET_A' in graph.nodes()
    results = match_patterns(graph)
    types = [r['circuit_type'] for r in results]
    assert 'Filtre RC passe-bas' in types


# ── Point 2: Dimensional validation ───────────────────────────────────────────

def test_truncated_2pin_component_raises():
    path = _write_tmp("R1 NET_A\n")
    with pytest.raises(ValueError, match="attend 2"):
        parse_file(path)
    os.unlink(path)


def test_truncated_transistor_raises():
    path = _write_tmp("Q1 NET_BASE NET_COLL\n")
    with pytest.raises(ValueError, match="attend 3"):
        parse_file(path)
    os.unlink(path)


def test_truncated_opamp_raises():
    path = _write_tmp("U1 NET_INP NET_INM NET_OUT VCC\n")
    with pytest.raises(ValueError, match="attend 5"):
        parse_file(path)
    os.unlink(path)


def test_error_message_contains_line_number():
    path = _write_tmp("R1 NET_A NET_B 10k\nC1 NET_B\n")
    with pytest.raises(ValueError, match="ligne 2"):
        parse_file(path)
    os.unlink(path)


# ── Point 3: Duplicate reference detection ────────────────────────────────────

def test_duplicate_ref_raises():
    path = _write_tmp("R1 NET_A NET_B 10k\nR1 NET_C NET_D 4.7k\n")
    with pytest.raises(ValueError, match="R1"):
        parse_file(path)
    os.unlink(path)


def test_duplicate_ref_error_contains_line_number():
    path = _write_tmp("C1 NET_A NET_B\nR1 A B\nC1 NET_C NET_D\n")
    with pytest.raises(ValueError, match="ligne 3"):
        parse_file(path)
    os.unlink(path)


def test_unique_refs_accepted():
    path = _write_tmp("R1 A B 10k\nR2 B C 4.7k\nC1 C GND 10nF\n")
    comps = parse_file(path)
    os.unlink(path)
    assert len(comps) == 3


# ── Point 4: Hierarchical resolution + component locking ──────────────────────

def test_non_inverting_amp_locks_resistors_from_voltage_divider():
    # R1 (IN-→OUT) and R2 (IN-→GND) form both a NonInvertingAmp feedback network
    # AND a voltage divider. AOP must win; VoltageDivider must not fire.
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '100k'),
        Component('R2', 'R', {'1': 'NET_INM', '2': 'GND'}, '10k'),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Amplificateur non-inverseur (AOP)' in types
    assert 'Pont diviseur de tension' not in types


def test_summing_amp_takes_priority_over_inverting():
    # U1 with 2 input R and 1 feedback R matches SummingAmplifier (more specific).
    # InvertingAmplifier must NOT also fire on the same U1.
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND2'}),
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_INM'}, '10k'),
        Component('R2', 'R', {'1': 'NET_B', '2': 'NET_INM'}, '10k'),
        Component('R3', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '20k'),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Amplificateur sommateur (AOP)' in types
    assert 'Amplificateur inverseur (AOP)' not in types


def test_decoupling_cap_locks_before_rc_lowpass():
    # C1 (VCC→GND) is a decoupling cap. Without locking it could also be claimed
    # by RCLowPassFilter alongside R1. DecouplingCapacitor must win.
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_SIG'}, '100'),
        Component('C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Condensateur de découplage' in types
    assert 'Filtre RC passe-bas' not in types


def test_transistor_switch_locks_base_resistor():
    # R1 is the base resistor of the transistor switch.
    # It must not also appear as part of a VoltageDivider or RC filter.
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_DRIVE', '2': 'NET_BASE'}, '10k'),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Transistor en commutation' in types
    # R1 consumed by transistor switch — must not appear in any other pattern
    for r in results:
        if r['circuit_type'] != 'Transistor en commutation':
            assert 'R1' not in r['components']


def test_each_component_appears_in_at_most_one_result():
    # Global invariant: component locking guarantees no component is
    # reported in two different circuit results.
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_INM', '2': 'NET_OUT'}, '100k'),
        Component('R2', 'R', {'1': 'NET_INM', '2': 'GND'}, '10k'),
        Component('R3', 'R', {'1': 'NET_IN', '2': 'VCC'}, '10k'),
        Component('C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF'),
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R4', 'R', {'1': 'NET_CMD', '2': 'NET_BASE'}, '1k'),
    ]
    results = match_patterns(build_graph(comps))
    seen = {}
    for r in results:
        for comp_ref in r['components']:
            assert comp_ref not in seen, (
                f"'{comp_ref}' apparaît dans '{seen[comp_ref]}' ET '{r['circuit_type']}'"
            )
            seen[comp_ref] = r['circuit_type']
