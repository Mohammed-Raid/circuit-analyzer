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


def test_miroir_apparie_uniquement_par_base_commune():
    comps = [
        Component('Q1', 'Q', {'B': 'NB1', 'C': 'NC1', 'E': 'GND'}),
        Component('Q2', 'Q', {'B': 'NB1', 'C': 'NC2', 'E': 'GND'}),
        Component('Q3', 'Q', {'B': 'NB2', 'C': 'NC3', 'E': 'GND'}),
        Component('Q4', 'Q', {'B': 'NB2', 'C': 'NC4', 'E': 'GND'}),
    ]
    from circuit_analyzer.detecteur import detecter_miroir_courant
    matches = detecter_miroir_courant(build_graph(comps))
    paires = {frozenset(m['components']) for m in matches}
    assert paires == {frozenset({'Q1', 'Q2'}), frozenset({'Q3', 'Q4'})}


def test_supprimes_non_enrichis():
    # L'enrichissement (confiance) ne doit plus être calculé pour les
    # matches supprimés — seuls circuit_type/components/nodes sont garantis.
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_MID'}, '10k'),
        Component('R2', 'R', {'1': 'NET_MID', '2': 'GND'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    assert results.supprimes   # chevauchement filtre RC / pont diviseur
    for s in results.supprimes:
        assert 'circuit_type' in s and 'components' in s
        assert 'confidence' not in s


def test_rapport_plafonne_les_supprimes_a_50():
    from circuit_analyzer.rapport import generer_rapport

    class FauxResultats(list):
        pass

    resultats = FauxResultats([])
    resultats.ilots = []
    resultats.supprimes = [
        {'circuit_type': 'Pont diviseur de tension',
         'components': [f'R{2*i}', f'R{2*i+1}'], 'nodes': ['N1', 'N2', 'N3']}
        for i in range(80)
    ]
    rapport = generer_rapport(resultats, 'test.txt', 0, [])
    assert 'Matches supprimés (80)' in rapport
    assert '... et 30 autres matches supprimés' in rapport
    assert rapport.count('déjà dans un autre circuit') == 50
