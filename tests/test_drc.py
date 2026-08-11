"""
@file test_drc.py
@brief Tests de circuit_analyzer.drc.verifier_drc (aucune couverture avant ce fichier).

Construit directement des paires (resultats, graphe) plutôt que de passer par
analyser() : drc.py ne dépend que de cette interface (liste de matches avec
'circuit_type'/'components'/'satellites', graphe.graph['components']).
"""
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.drc import verifier_drc


def _resultat(circuit_type, components, satellites=None):
    return {'circuit_type': circuit_type, 'components': components,
            'satellites': satellites or []}


def test_regle1_aop_sans_decouplage_est_signalee():
    comps = [
        Composant('U1', 'U', {'IN+': 'IN', 'IN-': 'OUT', 'OUT': 'OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
    ]
    g = construire_graphe(comps)
    resultats = [_resultat('Suiveur de tension (AOP)', ['U1'])]
    violations = verifier_drc(resultats, g)
    assert any(v['rule'] == 'AOP sans découplage' for v in violations)


def test_regle1_aop_avec_decouplage_nest_pas_signalee():
    comps = [
        Composant('U1', 'U', {'IN+': 'IN', 'IN-': 'OUT', 'OUT': 'OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
    ]
    g = construire_graphe(comps)
    satellites = [{'ref': 'C1', 'role': 'decoupling', 'score': 0.9,
                   'status': 'sure', 'reason': 'C entre VCC et GND'}]
    resultats = [_resultat('Suiveur de tension (AOP)', ['U1'], satellites)]
    violations = verifier_drc(resultats, g)
    assert not any(v['rule'] == 'AOP sans découplage' for v in violations)


def test_regle2_transistor_commutation_avec_inductance_sans_roue_libre():
    comps = [
        Composant('Q1', 'Q', {'B': 'BASE', 'C': 'COLL', 'E': 'GND'}),
        Composant('R1', 'R', {'1': 'CMD', '2': 'BASE'}, '1k'),
        Composant('L1', 'L', {'1': 'COLL', '2': 'VCC'}, '10mH'),
    ]
    g = construire_graphe(comps)
    resultats = [_resultat('Transistor en commutation', ['Q1', 'R1'])]
    violations = verifier_drc(resultats, g)
    assert any(v['rule'] == 'Diode de roue libre manquante' for v in violations)


def test_regle2_transistor_commutation_avec_roue_libre_nest_pas_signalee():
    comps = [
        Composant('Q1', 'Q', {'B': 'BASE', 'C': 'COLL', 'E': 'GND'}),
        Composant('R1', 'R', {'1': 'CMD', '2': 'BASE'}, '1k'),
        Composant('L1', 'L', {'1': 'COLL', '2': 'VCC'}, '10mH'),
    ]
    g = construire_graphe(comps)
    satellites = [{'ref': 'D1', 'role': 'flyback', 'score': 0.85,
                   'status': 'sure', 'reason': 'D anode sur COLL, cathode sur VCC'}]
    resultats = [_resultat('Transistor en commutation', ['Q1', 'R1'], satellites)]
    violations = verifier_drc(resultats, g)
    assert not any(v['rule'] == 'Diode de roue libre manquante' for v in violations)


def test_regle3_resistance_base_surdimensionnee():
    comps = [
        Composant('Q1', 'Q', {'B': 'BASE', 'C': 'COLL', 'E': 'GND'}),
        Composant('R1', 'R', {'1': 'CMD', '2': 'BASE'}, '470k'),
    ]
    g = construire_graphe(comps)
    resultats = [_resultat('Transistor en commutation', ['Q1', 'R1'])]
    violations = verifier_drc(resultats, g)
    assert any(v['rule'] == 'Résistance de base surdimensionnée' for v in violations)


def test_regle3_resistance_base_normale_nest_pas_signalee():
    comps = [
        Composant('Q1', 'Q', {'B': 'BASE', 'C': 'COLL', 'E': 'GND'}),
        Composant('R1', 'R', {'1': 'CMD', '2': 'BASE'}, '1k'),
    ]
    g = construire_graphe(comps)
    resultats = [_resultat('Transistor en commutation', ['Q1', 'R1'])]
    violations = verifier_drc(resultats, g)
    assert not any(v['rule'] == 'Résistance de base surdimensionnée' for v in violations)


def test_regle6_fusible_manquant_si_assez_de_composants():
    # >= 8 composants "reels" (hors GND/VCC/PWR) + rail VCC + aucun fusible.
    comps = [Composant(f'R{i}', 'R', {'1': f'N{i}', '2': 'VCC'}, '1k')
             for i in range(8)]
    g = construire_graphe(comps)
    violations = verifier_drc([], g)
    assert any(v['rule'] == 'Fusible manquant' for v in violations)


def test_regle6_pas_de_signalement_sous_le_seuil_de_composants():
    comps = [Composant(f'R{i}', 'R', {'1': f'N{i}', '2': 'VCC'}, '1k')
             for i in range(3)]
    g = construire_graphe(comps)
    violations = verifier_drc([], g)
    assert not any(v['rule'] == 'Fusible manquant' for v in violations)


def test_regle6_pas_de_signalement_si_fusible_present():
    comps = [Composant(f'R{i}', 'R', {'1': f'N{i}', '2': 'VCC'}, '1k')
             for i in range(8)]
    comps.append(Composant('F1', 'F', {'1': 'VCC', '2': 'RAIL'}))
    g = construire_graphe(comps)
    violations = verifier_drc([], g)
    assert not any(v['rule'] == 'Fusible manquant' for v in violations)


def test_les_regles_4_et_5_ne_sont_plus_jamais_emises():
    """Retrait délibéré et documenté (voir docstring de drc.py, commits
    76535a2 et 8fa4e91) : garde-fou anti-régression si quelqu'un réutilise
    ces noms de règle par erreur en réintroduisant du code mort."""
    comps = [
        Composant('U1', 'U', {'IN+': 'IN', 'IN-': 'OUT', 'OUT': 'OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '10k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'GND'}, '4.7k'),
    ]
    g = construire_graphe(comps)
    resultats = [
        _resultat('Suiveur de tension (AOP)', ['U1']),
        _resultat('Pont diviseur de tension', ['R1', 'R2']),
        _resultat('Filtre RC passe-bas', ['R1', 'R2']),
    ]
    violations = verifier_drc(resultats, g)
    noms = {v['rule'] for v in violations}
    assert 'Pont diviseur déséquilibré' not in noms
    assert 'Filtre RC sans découplage' not in noms
