"""@file test_reseau_deux_bornes.py
@brief Recognizer + routage du reseau passif compact a 2 bornes (rails/ports).

Remplace la grille generique pour les ilots qui se reduisent a UN reseau entre
deux nets-bornes (GND/VOUT, GND/VCC, AVCC/GND...), nœuds internes NETxx tolere.
"""
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from gui import circuit_viewer as cv
from gui import impedance_schematic


def _ilot(refs):
    return {'composants': sorted(refs), 'circuits': [], 'rail': None,
            'categorie': 'charge', 'label': 'Ilot test'}


def test_reconnait_reseau_parallele_gnd_vout():
    # Charge de sortie : C//R entre GND et VOUT (cf. ce_suiveur_sortie_rlc).
    comps = [
        Component('R9', 'R', {'1': 'VOUT', '2': 'GND'}, '1k'),
        Component('C4', 'C', {'1': 'VOUT', '2': 'GND'}, '100nF'),
    ]
    g = build_graph(comps)
    res = cv._reseau_deux_bornes_ilot(_ilot(['R9', 'C4']), g)
    assert res is not None
    arbre, a, b, comps_out = res
    assert {a, b} == {'GND', 'VOUT'}
    assert set(comps_out) == {'R9', 'C4'}


def test_reconnait_serie_via_noeud_interne():
    # R(NET10-GND) + C(VOUT-NET10) : 2 bornes (GND, VOUT), NET10 interne.
    comps = [
        Component('R14', 'R', {'1': 'NET10', '2': 'GND'}, '1k'),
        Component('C6', 'C', {'1': 'VOUT', '2': 'NET10'}, '1uF'),
    ]
    g = build_graph(comps)
    res = cv._reseau_deux_bornes_ilot(_ilot(['R14', 'C6']), g)
    assert res is not None
    _arbre, a, b, _comps = res
    assert {a, b} == {'GND', 'VOUT'}


def test_rejette_quand_pas_exactement_deux_bornes():
    # Trois rails -> pas un dipole 2-bornes -> None (repli grille generique).
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'GND'}, '1k'),
        Component('R2', 'R', {'1': 'VOUT', '2': 'GND'}, '1k'),
        Component('R3', 'R', {'1': 'VCC', '2': 'VOUT'}, '1k'),
    ]
    g = build_graph(comps)
    assert cv._reseau_deux_bornes_ilot(_ilot(['R1', 'R2', 'R3']), g) is None


def test_rejette_si_composant_actif():
    comps = [
        Component('Q1', 'Q', {'C': 'VOUT', 'B': 'NET1', 'E': 'GND'}, ''),
        Component('R1', 'R', {'1': 'VOUT', '2': 'GND'}, '1k'),
    ]
    g = build_graph(comps)
    assert cv._reseau_deux_bornes_ilot(_ilot(['Q1', 'R1']), g) is None


def test_draw_via_dessiner_bloc_une_boite_cliquable():
    comps = [
        Component('R9', 'R', {'1': 'VOUT', '2': 'GND'}, '1k'),
        Component('C4', 'C', {'1': 'VOUT', '2': 'GND'}, '100nF'),
    ]
    g = build_graph(comps)
    arbre, a, b, comps_out = cv._reseau_deux_bornes_ilot(_ilot(['R9', 'C4']), g)
    fig = impedance_schematic.dessiner_bloc(arbre, a, b, comps_out)
    assert fig is not None
    # reseau multi-composant -> une seule boite Z cliquable.
    assert len(getattr(fig, '_z_hitboxes', [])) == 1
    refs_hit = set(fig._z_hitboxes[0][4])
    assert refs_hit == {'R9', 'C4'}


def test_routage_prefere_deux_bornes_a_la_grille():
    comps = [
        Component('R9', 'R', {'1': 'VOUT', '2': 'GND'}, '1k'),
        Component('C4', 'C', {'1': 'VOUT', '2': 'GND'}, '100nF'),
    ]
    g = build_graph(comps)
    ilot = _ilot(['R9', 'C4'])
    # Tous les recognizers prioritaires renvoient None -> le 2-bornes prend la main.
    assert cv._circuit_principal_ilot(ilot, g, None) is None
    assert cv._arbre_serie_parallele_ilot(ilot, g) is None
    assert cv._pont_ilot(ilot, g) is None
    assert cv._reseau_derive_ilot(ilot, g) is None
    assert cv._reseau_deux_bornes_ilot(ilot, g) is not None
