import json, os, tempfile
from circuit_analyzer.component_library.base import COMPONENT_TYPES
from circuit_analyzer.component_library.loader import load_library, get_pins


def test_base_library_has_standard_types():
    assert 'R' in COMPONENT_TYPES
    assert 'C' in COMPONENT_TYPES
    assert 'Q' in COMPONENT_TYPES
    assert 'U' in COMPONENT_TYPES
    assert 'M' in COMPONENT_TYPES


def test_bjt_pins():
    assert COMPONENT_TYPES['Q']['pins'] == ['B', 'C', 'E']


def test_mosfet_pins():
    assert COMPONENT_TYPES['M']['pins'] == ['G', 'D', 'S']


def test_opamp_pins():
    assert COMPONENT_TYPES['U']['pins'] == ['IN+', 'IN-', 'OUT', 'V+', 'V-']


def test_load_library_returns_base_without_json():
    lib = load_library('nonexistent_file.json')
    assert 'Q' in lib
    assert lib['Q']['pins'] == ['B', 'C', 'E']


def test_json_override_replaces_entry():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'Q': {'name': 'Transistor custom', 'pins': ['BASE', 'COLL', 'EMIT']}}, f)
        fname = f.name
    lib = load_library(fname)
    os.unlink(fname)
    assert lib['Q']['pins'] == ['BASE', 'COLL', 'EMIT']


def test_json_adds_new_type():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'IC': {'name': 'CI spécifique', 'pins': ['VCC', 'GND', 'IN', 'OUT']}}, f)
        fname = f.name
    lib = load_library(fname)
    os.unlink(fname)
    assert 'IC' in lib
    assert lib['IC']['pins'] == ['VCC', 'GND', 'IN', 'OUT']


def test_get_pins_known_type():
    assert get_pins('Q') == ['B', 'C', 'E']
    assert get_pins('M') == ['G', 'D', 'S']


def test_get_pins_unknown_type_defaults_to_two_pin():
    assert get_pins('XYZ') == ['1', '2']
