"""
@file test_impedance.py
@brief Tests du moteur de réduction Z (circuit_analyzer/impedance.py).
"""
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer import impedance


def _graphe(*composants):
    """@brief Construit un graphe de test à partir de composants."""
    return construire_graphe(list(composants))


def _aretes(graphe):
    """@brief (frozenset(nœuds), type, ref) triées, pour comparaison stable."""
    return sorted(
        (tuple(sorted((u, v))), d['type'], d['ref'])
        for u, v, d in graphe.edges(data=True)
    )


def test_combiner_type_homogene_et_mixte():
    assert impedance._combiner_type('R', 'R') == 'R'
    assert impedance._combiner_type('C', 'C') == 'C'
    assert impedance._combiner_type('R', 'C') == 'Z'
    assert impedance._combiner_type('Z', 'R') == 'Z'


def test_aucune_reduction_graphe_inchange():
    # Deux R indépendantes (aucun nœud interne fusionnable) → graphe identique.
    g = _graphe(
        Composant('R1', 'R', {'1': 'IN', '2': 'OUT'}, '10k'),
        Composant('R2', 'R', {'1': 'VCC', '2': 'GND'}, '1k'),
    )
    reduit = impedance.reduire(g)
    assert _aretes(reduit) == _aretes(g)
    # Les valeurs réelles sont préservées sur les singletons.
    vals = {d['ref']: d['value'] for _, _, d in reduit.edges(data=True)}
    assert vals == {'R1': '10k', 'R2': '1k'}
    # Chaque singleton porte refs/composition cohérents.
    r1 = next(d for _, _, d in reduit.edges(data=True) if d['ref'] == 'R1')
    assert r1['refs'] == ['R1'] and r1['composition'] == 'R1'
