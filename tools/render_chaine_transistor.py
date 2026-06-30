"""Rend la vue ilot d'une cascade 2-CE en PNG pour inspection."""
import os
import sys

import matplotlib
matplotlib.use("Agg")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer import detecteur
from gui import circuit_viewer as cv


comps = [
    Composant("Q1", "Q", {"B": "NB1", "C": "NC1", "E": "GND"}),
    Composant("Rb1", "R", {"1": "VCC", "2": "NB1"}, "100k"),
    Composant("Rc1", "R", {"1": "VCC", "2": "NC1"}, "4.7k"),
    Composant("Cc", "C", {"1": "NC1", "2": "NB2"}, "1u"),
    Composant("Q2", "Q", {"B": "NB2", "C": "NC2", "E": "GND"}),
    Composant("Rb2", "R", {"1": "VCC", "2": "NB2"}, "100k"),
    Composant("Rc2", "R", {"1": "VCC", "2": "NC2"}, "1k"),
]
g = construire_graphe(comps)
res = detecteur.analyser(g)
ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
matches = cv._matches_for_island(ilot, res)
ordre = cv._ordonner_montages_flux(matches, ci)
fig = cv._make_chain_fig(ordre, ci, matches=matches)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_renders")
os.makedirs(out, exist_ok=True)
p = os.path.join(out, "chaine_2ce.png")
fig.savefig(p, dpi=110, bbox_inches="tight")
print(p)
