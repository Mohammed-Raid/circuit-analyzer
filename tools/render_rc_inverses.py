"""Rend les 2 montages RC reclasses en PNG pour inspection."""
import os
import sys

import matplotlib
matplotlib.use("Agg")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer import detecteur
from gui import circuit_viewer as cv


CASES = {
    "boost_hf": [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Cin", "C", {"1": "VIN", "2": "M"}, "100n"),
        Composant("Rf", "R", {"1": "M", "2": "VOUT"}, "100k"),
    ],
    "action_integrale": [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Rf", "R", {"1": "M", "2": "X"}, "10k"),
        Composant("Cf", "C", {"1": "X", "2": "VOUT"}, "100n"),
    ],
}


def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_renders")
    os.makedirs(out, exist_ok=True)
    for nom, comps in CASES.items():
        g = construire_graphe(comps)
        res = detecteur.analyser(g)
        ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
              for c in comps}
        ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
        p = cv._circuit_principal_ilot(ilot, g, res)
        fig = cv._make_fig(p, ci, cv._DRAWERS[p["circuit_type"]],
                           matches=cv._matches_for_island(ilot, res))
        fig.savefig(os.path.join(out, nom + ".png"), dpi=110, bbox_inches="tight")
        print(nom, "->", p["circuit_type"])


if __name__ == "__main__":
    main()
