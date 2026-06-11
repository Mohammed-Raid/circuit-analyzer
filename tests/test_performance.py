"""Garde-fou performance : échoue si un comportement quadratique revient.

Seuil volontairement large (5 s pour 1000 composants, ~0.2 s attendu) pour
rester stable sur une machine chargée tout en détectant une régression
d'ordre de grandeur.
"""
import time

from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns


def _bloc(i: int) -> list:
    """Même étage de relais que tools/benchmark.py (8 composants)."""
    p = f'B{i}_'
    return [
        Component(p + 'Q1', 'Q', {'B': p + 'NB', 'C': p + 'NC', 'E': 'GND'}),
        Component(p + 'R1', 'R', {'1': p + 'CMD', '2': p + 'NB'}, '1k'),
        Component(p + 'R2', 'R', {'1': p + 'NB', '2': 'GND'}, '10k'),
        Component(p + 'K1', 'K', {'A1': p + 'NC', 'A2': 'VCC',
                                  'C': p + 'KC', 'NC': p + 'KN'}),
        Component(p + 'D1', 'D', {'A': p + 'NC', 'K': 'VCC'}),
        Component(p + 'R3', 'R', {'1': 'VCC', '2': p + 'DIV'}, '10k'),
        Component(p + 'R4', 'R', {'1': p + 'DIV', '2': 'GND'}, '4.7k'),
        Component(p + 'C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF'),
    ]


def test_1000_composants_en_moins_de_5_secondes():
    composants = []
    for i in range(125):           # 125 blocs x 8 = 1000 composants
        composants.extend(_bloc(i))
    graphe = build_graph(composants)

    debut = time.perf_counter()
    resultats = match_patterns(graphe)
    duree = time.perf_counter() - debut

    assert duree < 5.0, f'Analyse de 1000 composants en {duree:.1f}s (limite 5s)'
    assert len(resultats) > 0
