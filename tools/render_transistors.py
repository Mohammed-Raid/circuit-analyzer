"""Rend les montages transistor simples en PNG pour inspection visuelle."""
import os
import sys

import matplotlib
matplotlib.use("Agg")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gui.circuit_viewer as cv


def _ci(*e):
    return {ref: {"type": t, "value": v, "pins": p} for ref, t, v, p in e}


CASES = {
    "commutation": (
        {"circuit_type": "Transistor en commutation",
         "components": ["Q1", "Rb"], "nodes": ["NB", "NL", "GND"]},
        _ci(("Q1", "Q", "", {"B": "NB", "C": "NL", "E": "GND"}),
            ("Rb", "R", "10k", {"1": "NIN", "2": "NB"}))),
    "emetteur_commun": (
        {"circuit_type": "Amplificateur émetteur commun",
         "components": ["Q1", "Rc", "Rb"], "nodes": ["NB", "NCOL", "GND"]},
        _ci(("Q1", "Q", "", {"B": "NB", "C": "NCOL", "E": "GND"}),
            ("Rc", "R", "1k", {"1": "VCC", "2": "NCOL"}),
            ("Rb", "R", "10k", {"1": "VCC", "2": "NB"}))),
    "suiveur": (
        {"circuit_type": "Collecteur commun (suiveur d'émetteur)",
         "components": ["Q1", "Re", "R1"], "nodes": ["NB", "VCC", "NOUT"]},
        _ci(("Q1", "Q", "", {"B": "NB", "C": "VCC", "E": "NOUT"}),
            ("Re", "R", "1k", {"1": "NOUT", "2": "GND"}),
            ("R1", "R", "47k", {"1": "NB", "2": "VCC"}))),
}

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_renders")
os.makedirs(OUT, exist_ok=True)

for nom, (result, ci) in CASES.items():
    fig = cv._make_fig(result, ci, cv._DRAWERS[result["circuit_type"]])
    chemin = os.path.join(OUT, nom + ".png")
    fig.savefig(chemin, dpi=110, bbox_inches="tight")
    print(chemin)
