"""Rend la vue ILOT (chemin reel show_island -> principal) des montages
multi-actifs, pour inspection visuelle apres le fix."""
import os, sys
import matplotlib
matplotlib.use("Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuit_analyzer.composant import construire_graphe
from circuit_analyzer import detecteur
from circuit_analyzer.xml import lire_xml
from gui import circuit_viewer as cv

CI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "circuits_industriels")
CASES = {
    "ilot_push_pull": "tr_etage_push_pull.xml",
    "ilot_darlington": "tr_paire_darlington.xml",
    "ilot_commande_relais": "tr_commande_relais.xml",
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_renders")
os.makedirs(OUT, exist_ok=True)

for nom, fichier in CASES.items():
    comps = lire_xml(os.path.join(CI, fichier))
    g = construire_graphe(comps)
    res = detecteur.analyser(g)
    comp_info = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    principal = cv._circuit_principal_ilot(ilot, g, res)
    assert principal is not None, nom
    fig = cv._make_fig(principal, comp_info, cv._DRAWERS[principal["circuit_type"]])
    chemin = os.path.join(OUT, nom + ".png")
    fig.savefig(chemin, dpi=110, bbox_inches="tight")
    print(f"{nom}: drawer '{principal['circuit_type']}' -> {chemin}")
