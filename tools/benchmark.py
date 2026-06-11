"""
benchmark.py — Mesure le temps d'analyse sur des netlists synthétiques.

Usage : python tools/benchmark.py [tailles...]
        python tools/benchmark.py            # 100 500 1000 2000 5000
        python tools/benchmark.py 100 500    # tailles personnalisées

Chaque bloc (8 composants) réplique un étage de commande de relais :
transistor + diviseur de base, relais + roue libre, pont diviseur, découplage.
Les nets sont uniques par bloc (préfixe B{i}_), seuls VCC et GND sont partagés
— comme dans un vrai schéma multi-étages.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.detecteur import analyser


def bloc(i: int) -> list:
    """Un étage de commande de relais (8 composants, nets propres au bloc)."""
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


def netlist_synthetique(nb_composants: int) -> list:
    composants = []
    i = 0
    while len(composants) < nb_composants:
        composants.extend(bloc(i))
        i += 1
    return composants[:nb_composants]


def mesurer(nb_composants: int) -> None:
    composants = netlist_synthetique(nb_composants)

    debut = time.perf_counter()
    graphe = build_graph(composants)
    t_graphe = time.perf_counter() - debut

    debut = time.perf_counter()
    resultats = analyser(graphe)
    t_analyse = time.perf_counter() - debut

    print(f'{len(composants):5d} comps | graphe {t_graphe:6.2f}s | '
          f'analyse {t_analyse:8.2f}s | {len(resultats)} circuits, '
          f'{len(resultats.supprimes)} supprimes, {len(resultats.ilots)} ilots',
          flush=True)


if __name__ == '__main__':
    tailles = [int(a) for a in sys.argv[1:]] or [100, 500, 1000, 2000, 5000]
    for taille in tailles:
        mesurer(taille)
