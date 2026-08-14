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


def render(xml_str: str, out_path: Path, largeur: int = 180, hauteur: int = 100) -> None:
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

    for line in root.iter("Line"):
        points = line.findall("LP/PointF")
        if len(points) < 2:
            continue
        # Trace TOUS les points, pas seulement le premier/dernier : un fil
        # route en L a un coude intermediaire qui doit rester visible pour
        # la verification visuelle (sinon impossible de distinguer une
        # diagonale d'un chemin en angle droit sur le rendu).
        xs = [float(p.findtext("X")) for p in points]
        ys = [float(p.findtext("Y")) for p in points]
        ax.plot(xs, ys, color="black", linewidth=1)

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

    # Amplificateur différentiel (nouvellement migré) : vérifie les 4
    # lignes empilées (Zf haut / AOP+Z1 / Z3 / Zg bas).
    comps_diff = [
        Component("U1", "U", {"IN+": "NET_INPLUS", "IN-": "NET_INMOINS",
                              "OUT": "NET_OUT", "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INMOINS", "2": "NET_IN1"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INMOINS"}),
        Component("R3", "R", {"1": "NET_INPLUS", "2": "NET_IN2"}),
        Component("R4", "R", {"1": "NET_INPLUS", "2": "GND"}),
    ]
    resultats_diff = match_patterns(build_graph(comps_diff))
    xml_diff = components_to_xml(comps_diff, resultats_diff)
    render(xml_diff, OUT / "disposition_ampli_differentiel.png")
    print(f"Rendu ecrit : {OUT / 'disposition_ampli_differentiel.png'}")

    # Integrateur avec Zf reellement parallele (C1//R6) : verifie
    # l'empilement vertical au lieu de la rangee -- le cas reel trouve sur
    # test_pid_3.xml, qui produisait un fil en diagonale avant ce chantier.
    comps_zf_parallele = [
        Component("U2", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R5", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("C1", "C", {"1": "NET_INV", "2": "NET_OUT"}),
        Component("R6", "R", {"1": "NET_INV", "2": "NET_OUT"}),
    ]
    resultats_zf_par = match_patterns(build_graph(comps_zf_parallele))
    xml_zf_par = components_to_xml(comps_zf_parallele, resultats_zf_par)
    render(xml_zf_par, OUT / "disposition_zf_parallele.png")
    print(f"Rendu ecrit : {OUT / 'disposition_zf_parallele.png'}")

    # Chemin carte scannee (ecrire_groupes) : avant/apres translation.
    # "avant" doit etre GENUINEMENT non-canonique pour que la comparaison
    # montre quelque chose : components_to_xml canonise deja l'ampli
    # inverseur (chantier precedent), donc on disperse les positions REELLES
    # a la main apres lecture, avant de patcher — sinon les deux rendus sont
    # visuellement identiques et le controle visuel ne prouve rien (constat
    # de revue de branche).
    import tempfile

    from circuit_analyzer.eretro_patch import _decaler_point, ecrire_groupes
    from circuit_analyzer.xml import lire_xml

    with tempfile.TemporaryDirectory() as tmp:
        chemin = str(Path(tmp) / "carte.xml")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(xml)

        relus = lire_xml(chemin)
        dispersion = {"U1": (0, 0), "R1": (-400, 300), "R2": (350, -250)}
        for ref, (dx, dy) in dispersion.items():
            element = relus.source.elements.get(ref)
            if element is None:
                continue
            x_elem, y_elem = element.find("CtrIem/X"), element.find("CtrIem/Y")
            x_elem.text = str(int(float(x_elem.text) + dx))
            y_elem.text = str(int(float(y_elem.text) + dy))
        # Le composant bouge, mais un fil qui s'y raccroche doit bouger AVEC
        # lui (meme rapport broche/centre que le reste de cette feature) --
        # sinon le fil reste a sa position canonique pendant que le corps du
        # composant se disperse, et l'extremite se retrouve loin du
        # composant qu'elle est censee relier (constat de revue de branche :
        # ~370 unites d'ecart sur carte_scannee_apres.png). Meme lookup
        # CFirst/CLast -> ref que _appliquer_deltas (source.lignes_refs).
        for idx, ligne in enumerate(relus.source.lignes):
            ra, rb = relus.source.lignes_refs.get(idx, (None, None))
            points = ligne.findall("LP/PointF")
            if not points:
                continue
            if ra in dispersion:
                _decaler_point(points[0], dispersion[ra])
            if rb in dispersion:
                _decaler_point(points[-1], dispersion[rb])
        xml_disperse = ET.tostring(relus.source.arbre.getroot(), encoding="unicode")

        render(xml_disperse, OUT / "carte_scannee_avant.png")
        print(f"Rendu ecrit : {OUT / 'carte_scannee_avant.png'}")

        res_relus = match_patterns(build_graph(relus))
        xml_patche = ecrire_groupes(relus.source, relus, res_relus)
        render(xml_patche, OUT / "carte_scannee_apres.png")
        print(f"Rendu ecrit : {OUT / 'carte_scannee_apres.png'}")
