"""
@file test_performance_fixes.py
@brief Tests automatises pour test_performance_fixes.
"""

"""Tests des correctifs de performance (sous-projet 3) :
détecteurs corrigés électriquement + enrichissement différé."""
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.parser import Component


def test_pas_de_diviseur_avec_rail_en_noeud_milieu():
    """@brief Verifie pas de diviseur avec rail en noeud milieu.

    @return None
    """
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
    """@brief Verifie diviseur legitime toujours detecte.

    Depuis le modèle Impédance Z, le pont diviseur isolé est émis comme « Impédance Z ».
    @return None
    """
    # VCC -> NET_DIV -> GND : réduit en une seule Impédance Z entre VCC et GND.
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_DIV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_DIV', '2': 'GND'}, '4.7k'),
    ]
    results = match_patterns(build_graph(comps))
    z = next((m for m in results if m['circuit_type'] == 'Impédance Z'), None)
    assert z is not None
    assert sorted(z['components']) == ['R1', 'R2']


def test_pas_de_snubber_entre_rails():
    """@brief Verifie pas de snubber entre rails.

    @return None
    """
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
    """@brief Verifie snubber legitime toujours detecte.

    Depuis le modèle Impédance Z, l'absorbeur RC isolé est émis comme « Impédance Z ».
    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '100'),
        Component('C1', 'C', {'1': 'NET_A', '2': 'NET_B'}, '10nF'),
    ]
    results = match_patterns(build_graph(comps))
    z = next((m for m in results if m['circuit_type'] == 'Impédance Z'), None)
    assert z is not None
    assert sorted(z['components']) == ['C1', 'R1']


def test_miroir_apparie_uniquement_par_base_commune():
    """@brief Verifie miroir apparie uniquement par base commune.

    @return None
    """
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
    """@brief Verifie supprimes non enrichis.

    Depuis le modèle Impédance Z, VCC→NET_MID→GND est réduit en une seule
    Impédance Z (R1+R2//C1) — il n'y a plus de chevauchement. On vérifie que
    les matches enrichis contiennent bien les clés de confiance.
    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_MID'}, '10k'),
        Component('R2', 'R', {'1': 'NET_MID', '2': 'GND'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    # Tous les passifs sont désormais couverts par une seule Impédance Z.
    assert any(m['circuit_type'] == 'Impédance Z' for m in results)
    for m in results:
        assert 'circuit_type' in m and 'components' in m
        assert 'confidence' in m


def test_pas_de_filtre_rc_avec_rail_en_jonction():
    """@brief Verifie pas de filtre rc avec rail en jonction.

    @return None
    """
    # R3 (VCC -> DIV) et C1 (VCC -> GND) se croisent sur VCC : la jonction
    # d'un filtre RC est un nœud signal, jamais un rail.
    comps = [
        Component('R3', 'R', {'1': 'VCC', '2': 'NET_DIV'}, '10k'),
        Component('C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    tous = [m['circuit_type'] for m in results] + \
           [m['circuit_type'] for m in results.supprimes]
    assert 'Filtre RC passe-bas' not in tous
    assert 'Filtre RC passe-haut' not in tous


def test_filtre_rc_legitime_toujours_detecte():
    """@brief Verifie filtre rc legitime toujours detecte.

    Depuis le modèle Impédance Z, le filtre RC isolé est émis comme « Impédance Z ».
    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    z = next((m for m in results if m['circuit_type'] == 'Impédance Z'), None)
    assert z is not None
    assert sorted(z['components']) == ['C1', 'R1']


def test_rapport_plafonne_les_supprimes_a_50():
    """@brief Verifie rapport plafonne les supprimes a 50.

    @return None
    """
    from circuit_analyzer.rapport import generer_rapport

    class FauxResultats(list):
        """@brief Classe utilitaire de test FauxResultats."""

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
