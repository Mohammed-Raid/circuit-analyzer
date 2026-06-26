"""Rend la vue ilot (chemin reel show_island) de chaque demo ilot_*.xml en PNG."""
import os, sys, glob
import matplotlib
matplotlib.use("Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuit_analyzer.composant import construire_graphe
from circuit_analyzer import detecteur
from circuit_analyzer.xml import lire_xml
from gui import circuit_viewer as cv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CI = os.path.join(ROOT, "circuits_industriels")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_renders")
os.makedirs(OUT, exist_ok=True)


def fig_for(ilot, g, res, comp_info):
    """Reproduit le dispatch de show_island."""
    principal = cv._circuit_principal_ilot(ilot, g, res)
    matches = cv._matches_for_island(ilot, res)
    if principal is not None:
        return cv._make_fig(principal, comp_info, cv._DRAWERS[principal["circuit_type"]]), "principal"
    chaine = cv._ordonner_montages_flux(matches, comp_info)
    if chaine is not None:
        return cv._make_chain_fig(chaine, comp_info, matches=matches), "chaine"
    branches = cv._layers_montages_flux(matches, comp_info)
    if branches is not None:
        return cv._make_branched_fig(branches, comp_info), "branchee"
    model = cv._build_island_model(ilot, g, comp_info)
    return cv._make_island_fig(model, matches=matches), "GRILLE"


for path in sorted(glob.glob(os.path.join(CI, "ilot_*.xml"))):
    nom = os.path.splitext(os.path.basename(path))[0]
    comps = lire_xml(path)
    g = construire_graphe(comps)
    res = detecteur.analyser(g)
    comp_info = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    if not res.ilots:
        print(f"{nom:38s} -> AUCUN ilot")
        continue
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    try:
        fig, voie = fig_for(ilot, g, res, comp_info)
        dest = os.path.join(OUT, nom + ".png")
        fig.savefig(dest, dpi=110, bbox_inches="tight")
        types = [m["circuit_type"] for m in cv._matches_for_island(ilot, res)]
        print(f"{nom:38s} -> {voie:9s} | {types}")
    except Exception as e:
        print(f"{nom:38s} -> ERREUR {type(e).__name__}: {e}")
