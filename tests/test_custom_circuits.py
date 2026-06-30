"""
@file test_custom_circuits.py
@brief Tests automatises pour test_custom_circuits.
"""

import json, os, tempfile, pytest
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from custom_circuits.loader import (
    load_custom_circuits, save_custom_circuits,
    CustomCircuitPattern, get_custom_patterns,
    CONDITION_LABELS, CONDITION_DESCRIPTIONS,
)


def _tmp_json(data):
    """@brief Helper de test pour tmp json."""
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(data, f)
    f.close()
    return f.name


def test_load_empty_when_file_missing():
    """@brief Verifie load empty when file missing.

    @return None
    """
    assert load_custom_circuits('nonexistent_file.json') == []


def test_save_and_load_roundtrip():
    """@brief Verifie save and load roundtrip.

    @return None
    """
    circuits = [{'name': 'Test', 'components': ['R', 'C'], 'conditions': []}]
    path = tempfile.mktemp(suffix='.json')
    save_custom_circuits(circuits, path)
    loaded = load_custom_circuits(path)
    os.unlink(path)
    assert loaded == circuits


def test_custom_pattern_name():
    """@brief Verifie custom pattern name.

    @return None
    """
    p = CustomCircuitPattern({'name': 'Mon circuit', 'components': ['R'], 'conditions': []})
    assert p.name == 'Mon circuit'


def test_custom_pattern_matches_required_types():
    """@brief Verifie custom pattern matches required types.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'GND'}, '100nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({'name': 'RC', 'components': ['R', 'C'], 'conditions': []})
    matches = p.match(G)
    assert len(matches) == 1
    assert 'R1' in matches[0]['components']
    assert 'C1' in matches[0]['components']


def test_custom_pattern_no_match_when_type_missing():
    """@brief Verifie custom pattern no match when type missing.

    @return None
    """
    comps = [Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k')]
    G = build_graph(comps)
    p = CustomCircuitPattern({'name': 'RC', 'components': ['R', 'C'], 'conditions': []})
    assert p.match(G) == []


def test_condition_c_connected_to_gnd():
    """@brief Verifie condition c connected to gnd.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'GND'}, '100nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Filtre', 'components': ['R', 'C'],
        'conditions': ['C connecté à GND']
    })
    assert len(p.match(G)) == 1


def test_condition_c_connected_to_gnd_fails_when_not():
    """@brief Verifie condition c connected to gnd fails when not.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'NET_C'}, '100nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Filtre', 'components': ['R', 'C'],
        'conditions': ['C connecté à GND']
    })
    assert p.match(G) == []


def test_condition_emitter_to_gnd():
    """@brief Verifie condition emitter to gnd.

    @return None
    """
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_BASE'}, '1k'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Switch', 'components': ['Q', 'R'],
        'conditions': ['Émetteur/Source à GND']
    })
    assert len(p.match(G)) == 1


def test_condition_labels_list():
    """@brief Verifie condition labels list.

    @return None
    """
    assert 'C connecté à GND' in CONDITION_LABELS
    assert 'Émetteur/Source à GND' in CONDITION_LABELS
    assert len(CONDITION_LABELS) >= 5


def test_every_condition_has_a_description():
    """@brief Verifie every condition has a description.

    @return None
    """
    # L'onglet Circuits affiche une description sous chaque case : aucune
    # condition ne doit rester sans explication (sinon case cryptique).
    manquantes = [l for l in CONDITION_LABELS if not CONDITION_DESCRIPTIONS.get(l)]
    assert manquantes == [], f"Conditions sans description : {manquantes}"


def test_get_custom_patterns_returns_empty_when_no_file():
    """@brief Verifie get custom patterns returns empty when no file.

    @return None
    """
    patterns = get_custom_patterns('nonexistent.json')
    assert patterns == []
