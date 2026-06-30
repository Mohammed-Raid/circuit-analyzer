"""Audit visuel : rend chaque ilot de chaque circuit industriel et detecte
exceptions, « Schema non disponible », et chevauchements de labels.

Usage : python tools/audit_visuel_ilots.py
PNG suspects ecrits dans tools/_renders/audit/<circuit>__ilot<N>.png
"""
import glob
import os
import sys
import traceback

import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuit_analyzer.xml import lire_xml
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer import detecteur
from gui import circuit_viewer as cv

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_renders", "audit")


def _fig_ilot(ilot, g, res, ci):
    """Reproduit EXACTEMENT l'arbre de decision de show_island."""
    model = cv._build_island_model(ilot, g, ci)
    matches = cv._matches_for_island(ilot, res)
    principal = cv._circuit_principal_ilot(ilot, g, res)
    sp = cv._arbre_serie_parallele_ilot(ilot, g) if principal is None else None
    pont = cv._pont_ilot(ilot, g) if (principal is None and sp is None) else None
    chaine = branches = None
    if principal is None and sp is None and pont is None:
        chaine = cv._ordonner_montages_flux(matches, ci)
        if chaine is None:
            branches = cv._layers_montages_flux(matches, ci)

    if principal is not None:
        return cv._make_fig(principal, ci, cv._DRAWERS[principal["circuit_type"]],
                            matches=matches)
    if sp is not None:
        from gui import impedance_schematic
        arbre, comps = sp
        return impedance_schematic.dessiner_bloc(arbre, "VIN", "VOUT", comps)
    if pont is not None:
        from gui import impedance_schematic
        pont_struct, comps = pont
        return impedance_schematic.dessiner_pont(pont_struct, comps)
    if chaine is not None:
        return cv._make_chain_fig(chaine, ci, matches=matches)
    if branches is not None:
        return cv._make_branched_fig(branches, ci, matches=matches)
    return cv._make_island_fig(model, matches=matches)


def _collisions(fig, seuil=0.30):
    """Paires de labels dont les boites se chevauchent (> seuil de la plus petite)."""
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    r = canvas.get_renderer()
    items = [(t.get_text().strip(), t.get_window_extent(r))
             for ax in fig.axes for t in ax.texts if t.get_text().strip()]
    hits = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i][1], items[j][1]
            ix = max(0, min(a.x1, b.x1) - max(a.x0, b.x0))
            iy = max(0, min(a.y1, b.y1) - max(a.y0, b.y0))
            inter = ix * iy
            if inter <= 0:
                continue
            petite = min(a.width * a.height, b.width * b.height) or 1
            if inter / petite > seuil:
                hits.append((items[i][0], items[j][0]))
    return hits


def main():
    os.makedirs(OUT, exist_ok=True)
    fichiers = sorted(glob.glob("circuits_industriels/*.xml"))
    n_ilots = n_susp = 0
    problemes = []
    for f in fichiers:
        nom = os.path.basename(f)
        try:
            comps = lire_xml(f)
            g = construire_graphe(comps)
            res = detecteur.analyser(g)
            ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
                  for c in comps}
        except Exception as e:
            problemes.append((nom, "-", f"ANALYSE: {e}"))
            continue
        for idx, ilot in enumerate(res.ilots):
            n_ilots += 1
            tag = f"{nom}__ilot{idx}"
            try:
                fig = _fig_ilot(ilot, g, res, ci)
                txts = [t.get_text() for ax in fig.axes for t in ax.texts]
                soucis = []
                if any("non disponible" in t for t in txts):
                    soucis.append("NON_DISPONIBLE")
                cols = _collisions(fig)
                if cols:
                    soucis.append(f"COLLISIONS={cols}")
                if soucis:
                    n_susp += 1
                    fig.savefig(os.path.join(OUT, tag + ".png"),
                                dpi=110, bbox_inches="tight")
                    problemes.append((nom, idx, " ; ".join(soucis)))
            except Exception:
                n_susp += 1
                problemes.append((nom, idx, "EXCEPTION:\n" + traceback.format_exc()))

    def p(s):
        print(str(s).encode("ascii", "replace").decode("ascii"))

    p(f"circuits={len(fichiers)} ilots={n_ilots} suspects={n_susp}")
    p("=" * 60)
    for nom, idx, msg in problemes:
        p(f"[{nom} ilot{idx}] {msg}")
    if not problemes:
        p("AUCUN probleme detecte.")


if __name__ == "__main__":
    main()
