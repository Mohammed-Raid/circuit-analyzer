"""
Tests d'integration : la reduction en dipoles equivalents permet de detecter
des montages dont la contre-reaction / l'entree est un reseau composite.
"""
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.detecteur import analyser


def _types(resultats):
    """@brief Helper de test pour types."""
    return {c['circuit_type'] for c in resultats}


def test_inverseur_avec_feedback_compose_serie():
    """@brief Verifie inverseur avec feedback compose serie."""
    # Feedback Rf = R1 + R2 en serie entre OUT et IN-. Sans reduction, le noeud
    # MID intermediaire empeche la detection.
    composants = [
        Composant('U1', 'U', {'IN+': 'GND', 'IN-': 'INM', 'OUT': 'OUT'}),
        Composant('Rin', 'R', {'1': 'IN', '2': 'INM'}, '1k'),
        Composant('R1', 'R', {'1': 'INM', '2': 'MID'}, '5k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'OUT'}, '5k'),
    ]
    res = analyser(construire_graphe(composants))
    assert 'Amplificateur inverseur (AOP)' in _types(res)
    inv = next(c for c in res if c['circuit_type'] == 'Amplificateur inverseur (AOP)')
    assert 'R1' in inv['components'] and 'R2' in inv['components']
    assert 'Rin' in inv['components']


def test_inverseur_simple_toujours_detecte():
    """@brief Verifie inverseur simple toujours detecte."""
    composants = [
        Composant('U1', 'U', {'IN+': 'GND', 'IN-': 'INM', 'OUT': 'OUT'}),
        Composant('Rin', 'R', {'1': 'IN', '2': 'INM'}, '1k'),
        Composant('Rf', 'R', {'1': 'INM', '2': 'OUT'}, '10k'),
    ]
    res = analyser(construire_graphe(composants))
    inv = next(c for c in res if c['circuit_type'] == 'Amplificateur inverseur (AOP)')
    assert sorted(inv['components']) == ['Rf', 'Rin', 'U1']


def test_action_integrale_avec_feedback_mixte_R_serie_C_detecte():
    """@brief Verifie action integrale avec feedback mixte R serie C."""
    # Un feedback mixte R+C devient un dipole de type 'Z'. Les detecteurs AOP
    # doivent pouvoir l'utiliser comme impedance de contre-reaction, puis
    # l'expansion doit restituer les vraies refs Rf et Cf.
    composants = [
        Composant('U1', 'U', {'IN+': 'GND', 'IN-': 'INM', 'OUT': 'OUT'}),
        Composant('Rin', 'R', {'1': 'IN', '2': 'INM'}, '1k'),
        Composant('Rf', 'R', {'1': 'INM', '2': 'MID'}, '10k'),
        Composant('Cf', 'C', {'1': 'MID', '2': 'OUT'}, '100n'),
    ]
    res = analyser(construire_graphe(composants))
    inv = next((c for c in res
                if c['circuit_type'] == 'Ampli inverseur + action intégrale (AOP)'), None)
    assert inv is not None
    assert {'U1', 'Rin', 'Rf', 'Cf'} <= set(inv['components'])
    assert 'Int\u00e9grateur (AOP)' not in _types(res)
    assert not any(
        c['circuit_type'] == 'Imp\u00e9dance Z' and {'Rf', 'Cf'} <= set(c['components'])
        for c in res
    )
