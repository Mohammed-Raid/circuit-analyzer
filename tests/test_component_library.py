"""
@file test_component_library.py
@brief Tests automatises pour test_component_library.
"""

import json
import os
import tempfile

from circuit_analyzer.component_library.base import COMPONENT_TYPES
from circuit_analyzer.component_library.loader import get_pins, load_library


def test_base_library_has_standard_types():
    """@brief Verifie base library has standard types.

    @return None
    """
    assert 'R' in COMPONENT_TYPES
    assert 'C' in COMPONENT_TYPES
    assert 'Q' in COMPONENT_TYPES
    assert 'U' in COMPONENT_TYPES
    assert 'M' in COMPONENT_TYPES


def test_bjt_pins():
    """@brief Verifie bjt pins.

    @return None
    """
    assert COMPONENT_TYPES['Q']['pins'] == ['B', 'C', 'E']


def test_mosfet_pins():
    """@brief Verifie mosfet pins.

    @return None
    """
    assert COMPONENT_TYPES['M']['pins'] == ['G', 'D', 'S']


def test_opamp_pins():
    """@brief Verifie opamp pins.

    @return None
    """
    assert COMPONENT_TYPES['U']['pins'] == ['IN+', 'IN-', 'OUT', 'V+', 'V-']


def test_load_library_returns_base_without_json():
    """@brief Verifie load library returns base without json.

    @return None
    """
    lib = load_library('nonexistent_file.json')
    assert 'Q' in lib
    assert lib['Q']['pins'] == ['B', 'C', 'E']


def test_json_override_replaces_entry():
    """@brief Verifie json override replaces entry.

    @return None
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'Q': {'name': 'Transistor custom', 'pins': ['BASE', 'COLL', 'EMIT']}}, f)
        fname = f.name
    lib = load_library(fname)
    os.unlink(fname)
    assert lib['Q']['pins'] == ['BASE', 'COLL', 'EMIT']


def test_json_adds_new_type():
    """@brief Verifie json adds new type.

    @return None
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'IC': {'name': 'CI spécifique', 'pins': ['VCC', 'GND', 'IN', 'OUT']}}, f)
        fname = f.name
    lib = load_library(fname)
    os.unlink(fname)
    assert 'IC' in lib
    assert lib['IC']['pins'] == ['VCC', 'GND', 'IN', 'OUT']


def test_get_pins_known_type():
    """@brief Verifie get pins known type.

    @return None
    """
    assert get_pins('Q') == ['B', 'C', 'E']
    assert get_pins('M') == ['G', 'D', 'S']


def test_get_pins_unknown_type_defaults_to_two_pin():
    """@brief Verifie get pins unknown type defaults to two pin.

    @return None
    """
    assert get_pins('XYZ') == ['1', '2']
