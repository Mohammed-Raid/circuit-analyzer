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
