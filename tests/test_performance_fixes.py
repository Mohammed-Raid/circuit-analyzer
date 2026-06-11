"""Tests des correctifs de performance (sous-projet 3) :
détecteurs corrigés électriquement + enrichissement différé."""
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns


def test_pas_de_diviseur_avec_rail_en_noeud_milieu():
    # Deux R qui se rejoignent sur GND : pas un diviseur (le nœud milieu
    # d'un diviseur est toujours un nœud signal).
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'GND'}, '10k'),
        Component('R2', 'R', {'1': 'NET_B', '2': 'GND'}, '4.7k'),
    ]
    results = match_patterns(build_graph(comps))
    tous = [m['circuit_type'] for m in results] + \
           [m['circuit_type'] for m in results.supprimes]
    assert 'Pont diviseur de tension' not in tous


def test_diviseur_legitime_toujours_detecte():
    # VCC -> NET_DIV -> GND : nœud milieu signal, diviseur réel.
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_DIV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_DIV', '2': 'GND'}, '4.7k'),
    ]
    results = match_patterns(build_graph(comps))
    assert any(m['circuit_type'] == 'Pont diviseur de tension' for m in results)


def test_pas_de_snubber_entre_rails():
    # R et C en parallèle entre VCC et GND : bleeder + découplage,
    # pas un absorbeur RC.
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'GND'}, '10k'),
        Component('C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    tous = [m['circuit_type'] for m in results] + \
           [m['circuit_type'] for m in results.supprimes]
    assert 'Absorbeur RC' not in tous


def test_snubber_legitime_toujours_detecte():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '100'),
        Component('C1', 'C', {'1': 'NET_A', '2': 'NET_B'}, '10nF'),
    ]
    results = match_patterns(build_graph(comps))
    assert any(m['circuit_type'] == 'Absorbeur RC' for m in results)
