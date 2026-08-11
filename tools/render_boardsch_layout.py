"""
@file render_boardsch_layout.py
@brief Rendu minimal (rectangles + labels) d'un schema BoardSCH XML, pour
verification visuelle d'une disposition canonique.

Usage:
  python tools/render_boardsch_layout.py

Genere tools/_renders/disposition_ampli_inverseur.png depuis un cas de test
synthetique (ampli inverseur).

ponytail: rectangles + label + trait d'angle, pas le catalogue de formes
reelles (Puce/AOP/etc.) — suffisant pour verifier gauche/centre/au-dessus a
l'oeil. Upgrade vers les vraies formes si l'inspection visuelle simple ne
suffit plus a juger une disposition.
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "tools" / "_renders"


def render(xml_str: str, out_path: Path, largeur: int = 80, hauteur: int = 40) -> None:
    """@brief Dessine chaque <DataItem> du XML en rectangle labellise.

    @param xml_str Document BoardSCH (sortie de generer_xml/components_to_xml).
    @param out_path Chemin du PNG a ecrire.
    @param largeur, hauteur Taille (px modele) du rectangle par composant.
    """
    root = ET.fromstring(xml_str)
    items = list(root.iter("DataItem"))

    fig, ax = plt.subplots(figsize=(8, 6))
    for item in items:
        ref = item.findtext("reference") or "?"
        cx = float(item.findtext("CtrIem/X") or 0)
        cy = float(item.findtext("CtrIem/Y") or 0)
        angle = float(item.findtext("angle") or 0)
        rect = Rectangle((cx - largeur / 2, cy - hauteur / 2), largeur, hauteur,
                          angle=angle, rotation_point='center',
                          fill=False, edgecolor="black")
        ax.add_patch(rect)
        ax.text(cx, cy, ref, ha="center", va="center", fontsize=9)

    ax.set_aspect("equal")
    ax.autoscale()
    ax.invert_yaxis()  # coordonnees ecran BoardSCH : Y croit vers le bas
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    from circuit_analyzer.graph_builder import build_graph
    from circuit_analyzer.matcher import match_patterns
    from circuit_analyzer.parser import Component
    from circuit_analyzer.xml_generator import components_to_xml

    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    resultats = match_patterns(build_graph(comps))
    xml = components_to_xml(comps, resultats)
    render(xml, OUT / "disposition_ampli_inverseur.png")
    print(f"Rendu ecrit : {OUT / 'disposition_ampli_inverseur.png'}")
