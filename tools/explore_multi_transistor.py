"""Explore : que donne la vue ilot quand PLUSIEURS montages transistor sont dans
le meme ilot (cascade) ? Rend le PNG via le vrai chemin show_island."""
import os, sys
import matplotlib
matplotlib.use("Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer import detecteur
from gui import circuit_viewer as cv

# Deux etages emetteur-commun cascades : collecteur Q1 (NC1) -> base Q2.
COMPS = [
    Composant("Q1", "Q", {"B": "NB1", "C": "NC1", "E": "GND"}),
    Composant("Rb1", "R", {"1": "VCC", "2": "NB1"}, "100k"),
    Composant("Rc1", "R", {"1": "VCC", "2": "NC1"}, "4.7k"),
    Composant("Q2", "Q", {"B": "NC1", "C": "NC2", "E": "GND"}),
    Composant("Rc2", "R", {"1": "VCC", "2": "NC2"}, "1k"),
]

g = construire_graphe(COMPS)
res = detecteur.analyser(g)
comp_info = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in COMPS}

print("detecte :", [m["circuit_type"] for m in res])
print("ilots   :", [(i.get("composants")) for i in res.ilots])

ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
principal = cv._circuit_principal_ilot(ilot, g, res)
matches = cv._matches_for_island(ilot, res)
print("matches ilot :", [m.get("circuit_type") for m in matches])
print("principal    :", None if principal is None else principal["circuit_type"])

chaine = cv._ordonner_montages_flux(matches)
branches = cv._layers_montages_flux(matches) if chaine is None else None
if principal is not None:
    branche = "PRINCIPAL drawer"
elif chaine is not None:
    branche = "CHAINE (symboles AOP)"
elif branches is not None:
    branche = "BRANCHED (symboles AOP)"
else:
    branche = "GRILLE GENERIQUE (carres)"
print("-> rendu :", branche)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_renders")
os.makedirs(OUT, exist_ok=True)
# Reproduit le dispatch de show_island pour produire la figure reellement affichee.
if principal is not None:
    fig = cv._make_fig(principal, comp_info, cv._DRAWERS[principal["circuit_type"]])
elif chaine is not None:
    fig = cv._make_chain_fig(chaine, comp_info)
elif branches is not None:
    fig = cv._make_branched_fig(branches, comp_info)
else:
    model = cv._build_island_model(ilot, g, comp_info)
    fig = cv._make_island_fig(model, matches=matches)
chemin = os.path.join(OUT, "multi_transistor.png")
fig.savefig(chemin, dpi=110, bbox_inches="tight")
print("PNG :", chemin)
