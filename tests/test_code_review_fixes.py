"""
Regression tests for the 8 bugs found by code review.
"""
import json, os, tempfile, pytest
from pathlib import Path
from circuit_analyzer.parser import parse_file, Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.patterns.basic_circuits import HalfWaveRectifier, PeakDetector


def _write_tmp(content):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
    f.write(content)
    f.close()
    return f.name


# ── Fix 1: matcher.py except broadened to Exception ──────────────────────────

def test_malformed_custom_circuits_json_does_not_crash(tmp_path, monkeypatch):
    # A malformed custom_circuits.json must not crash match_patterns()
    (tmp_path / 'custom_circuits.json').write_text('{ not valid json }', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Filtre RC passe-bas' in types


# ── Fix 2: HalfWaveRectifier uses cathode only ────────────────────────────────

def test_half_wave_rectifier_not_found_on_anode_load():
    # R1 is on the ANODE (input) side — must NOT be reported as a rectifier
    comps = [
        Component('D1', 'D', {'A': 'NET_AC', 'K': 'NET_DC'}),
        Component('R1', 'R', {'1': 'NET_AC', '2': 'GND'}, '1k'),  # anode-side load
    ]
    assert HalfWaveRectifier().match(build_graph(comps)) == []


def test_half_wave_rectifier_found_on_cathode_load():
    # R1 is on the CATHODE (output) side — must be reported as a rectifier
    comps = [
        Component('D1', 'D', {'A': 'NET_AC', 'K': 'NET_DC'}),
        Component('R1', 'R', {'1': 'NET_DC', '2': 'GND'}, '1k'),  # cathode-side load
    ]
    matches = HalfWaveRectifier().match(build_graph(comps))
    assert len(matches) == 1
    assert 'D1' in matches[0]['components']
    assert 'R1' in matches[0]['components']


def test_peak_detector_not_found_on_anode_cap():
    # C1 is on the ANODE (input) side — must NOT be reported as a peak detector
    comps = [
        Component('D1', 'D', {'A': 'NET_IN', 'K': 'NET_PEAK'}),
        Component('C1', 'C', {'1': 'NET_IN', '2': 'GND'}, '10uF'),  # anode-side cap
    ]
    assert PeakDetector().match(build_graph(comps)) == []


# ── Fix 3: main.py ValueError handled ────────────────────────────────────────

def test_main_exits_cleanly_on_duplicate_ref(tmp_path):
    import subprocess, sys
    netlist = tmp_path / 'bad.txt'
    netlist.write_text('R1 VCC GND 10k\nR1 NET_A NET_B 4k7\n', encoding='utf-8')
    result = subprocess.run(
        [sys.executable, 'main.py', str(netlist)],
        capture_output=True, text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 1
    assert 'Erreur netlist' in result.stderr
    assert 'Traceback' not in result.stderr


# ── Fix 4: _check_condition unknown label returns False ───────────────────────

def test_unknown_condition_label_does_not_pass():
    from custom_circuits.loader import CustomCircuitPattern
    defn = {'name': 'Test', 'components': ['R'], 'conditions': ['Condition inconnue']}
    pattern = CustomCircuitPattern(defn)
    comps = [Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k')]
    matches = pattern.match(build_graph(comps))
    assert matches == []


# ── Fix 5: case-insensitive duplicate ref detection ───────────────────────────

def test_lowercase_duplicate_ref_raises():
    path = _write_tmp("R1 NET_A NET_B 10k\nr1 NET_C NET_D 4k7\n")
    with pytest.raises(ValueError, match="[Rr]1"):
        parse_file(path)
    os.unlink(path)


# ── Fix 6: unvalidated ref token raises ──────────────────────────────────────

def test_numeric_ref_raises():
    path = _write_tmp("10k VCC GND\n")
    with pytest.raises(ValueError, match="invalide"):
        parse_file(path)
    os.unlink(path)


def test_value_shifted_left_raises():
    path = _write_tmp("100nF NET_A NET_B\n")
    with pytest.raises(ValueError, match="invalide"):
        parse_file(path)
    os.unlink(path)


# ── Fix 7+8: OPAMP_PATTERNS complete, ALL_PATTERNS correct order ─────────────

def test_opamp_patterns_includes_all_new_patterns():
    from circuit_analyzer.patterns.opamp import OPAMP_PATTERNS
    names = [p.name for p in OPAMP_PATTERNS]
    assert 'Dérivateur (AOP)' in names
    assert 'Trigger de Schmitt (AOP)' in names
    assert 'Amplificateur différentiel (AOP)' in names
    assert 'Amplificateur sommateur (AOP)' in names


def test_all_patterns_decoupling_before_rc_lowpass():
    from circuit_analyzer.patterns.basic_circuits import ALL_PATTERNS
    names = [p.name for p in ALL_PATTERNS]
    assert names.index('Condensateur de découplage') < names.index('Filtre RC passe-bas')
