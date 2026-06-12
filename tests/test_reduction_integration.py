"""
Tests d'intégration : la réduction en dipôles équivalents permet de détecter
des montages dont la contre-réaction / l'entrée est un réseau composite.
Couvre la directive rouge du document : « créer le dipôle Rf complexe ».
"""
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.detecteur import analyser


def _types(resultats):
    return {c['circuit_type'] for c in resultats}


def test_inverseur_avec_feedback_compose_serie():
    # Feedback Rf = R1 + R2 (série) entre OUT et IN- ; sans réduction, le nœud
    # MID intermédiaire empêche la détection.
    composants = [
        Composant('U1', 'U', {'IN+': 'GND', 'IN-': 'INM', 'OUT': 'OUT'}),
        Composant('Rin', 'R', {'1': 'IN', '2': 'INM'}, '1k'),
        Composant('R1', 'R', {'1': 'INM', '2': 'MID'}, '5k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'OUT'}, '5k'),
    ]
    res = analyser(construire_graphe(composants))
    assert 'Amplificateur inverseur (AOP)' in _types(res)
    # Le circuit détecté doit contenir les VRAIES résistances du feedback composite
    inv = next(c for c in res if c['circuit_type'] == 'Amplificateur inverseur (AOP)')
    assert 'R1' in inv['components'] and 'R2' in inv['components']
    assert 'Rin' in inv['components']


def test_inverseur_simple_toujours_detecte():
    # Non-régression : un feedback mono-résistance reste détecté à l'identique.
    composants = [
        Composant('U1', 'U', {'IN+': 'GND', 'IN-': 'INM', 'OUT': 'OUT'}),
        Composant('Rin', 'R', {'1': 'IN', '2': 'INM'}, '1k'),
        Composant('Rf', 'R', {'1': 'INM', '2': 'OUT'}, '10k'),
    ]
    res = analyser(construire_graphe(composants))
    inv = next(c for c in res if c['circuit_type'] == 'Amplificateur inverseur (AOP)')
    assert sorted(inv['components']) == ['Rf', 'Rin', 'U1']


def test_feedback_mixte_R_serie_C_non_classifie():
    # Limitation connue : un feedback R série C devient un dipôle de type 'Z'
    # qu'aucun détecteur ne reconnaît. On épingle ce comportement (non-détection
    # volontaire plutôt que faux positif) pour qu'il ne soit pas pris pour un bug.
    composants = [
        Composant('U1', 'U', {'IN+': 'GND', 'IN-': 'INM', 'OUT': 'OUT'}),
        Composant('Rin', 'R', {'1': 'IN', '2': 'INM'}, '1k'),
        Composant('Rf', 'R', {'1': 'INM', '2': 'MID'}, '10k'),
        Composant('Cf', 'C', {'1': 'MID', '2': 'OUT'}, '100n'),
    ]
    res = analyser(construire_graphe(composants))
    assert 'Amplificateur inverseur (AOP)' not in _types(res)
    assert 'Intégrateur (AOP)' not in _types(res)
