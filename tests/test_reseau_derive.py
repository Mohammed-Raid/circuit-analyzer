"""@file test_reseau_derive.py
@brief Recognizer + drawer du reseau derive sur prise (diviseurs / filtrage rail)."""
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from gui import circuit_viewer as cv


def _ilot(refs):
    return {'composants': sorted(refs), 'circuits': [], 'rail': None,
            'categorie': 'alimentation', 'label': 'Ilot test'}


def test_reseau_derive_reconnait_diviseur():
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'VREF'}, '10k'),
        Component('R2', 'R', {'1': 'VREF', '2': 'GND'}, '4.7k'),
    ]
    g = build_graph(comps)
    info = cv._reseau_derive_ilot(_ilot(['R1', 'R2']), g)
    assert info is not None
    assert info['top'] == 'VCC'
    assert info['prise'] == 'VREF'
    assert info['serie']['refs'] == ['R1']
    assert set(info['shunt']['refs']) == {'R2'}


def test_reseau_derive_filtrage_rail_shunt_caps():
    comps = [
        Component('R4', 'R', {'1': 'VCC_5V', '2': 'AVCC'}, '10R'),
        Component('C4', 'C', {'1': 'AVCC', '2': 'GND'}, '100nF'),
        Component('C5', 'C', {'1': 'AVCC', '2': 'GND'}, '10uF'),
    ]
    g = build_graph(comps)
    info = cv._reseau_derive_ilot(_ilot(['R4', 'C4', 'C5']), g)
    assert info is not None
    assert info['prise'] == 'AVCC'
    assert info['serie']['refs'] == ['R4']
    assert set(info['shunt']['refs']) == {'C4', 'C5'}


def test_reseau_derive_non_reconnu_renvoie_none():
    # Filtre RC signal classique : pas de prise derivee.
    comps = [
        Component('R1', 'R', {'1': 'SIG_IN', '2': 'SIG_OUT'}, '10k'),
        Component('C1', 'C', {'1': 'SIG_OUT', '2': 'GND'}, '100nF'),
    ]
    g = build_graph(comps)
    assert cv._reseau_derive_ilot(_ilot(['R1', 'C1']), g) is None
