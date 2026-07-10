"""@file test_labels_property.py
@brief Test propriété (le contrat, cf. design docs/superpowers/specs/
2026-07-06-ilots-rendu-rigoureux-design.md section 1) : pour chaque circuit
du sweep (ilot_*, tr_*, aop_*) construit exactement comme
tools/render_ilots_v2.py (`_fig_for_ilot`), dans les DEUX modes (Z et
détaillé) :
  (a) aucun couple de `Text` visibles dont les bboxes RENDERER se recouvrent
      de plus de 1 px² ;
  (b) chaque `Text` visible tombe entièrement dans les limites d'axe finales
      de son axe.

Ce test doit capturer l'état imparfait AVANT branchement de
`gui.schema_labels.ajuster_labels` (cf. rapport de chantier) ; il devient
vert une fois le moteur branché en fin des fabriques de figures.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg
import pytest

from circuit_analyzer import detecteur
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.xml import lire_xml
from tools.render_ilots_v2 import _fig_for_ilot

ROOT = Path(__file__).resolve().parent.parent
TOLERANCE_PX2 = 1.0


def _circuit_files():
    ci = ROOT / "circuits_industriels"
    return (sorted(ci.glob("ilot_*.xml"))
            + sorted(ci.glob("tr_*.xml"))
            + sorted(ci.glob("aop_*.xml"))
            # Portes CMOS -- logic_non_dual est EXCLU des contrats visuels
            # (fichier de rejet : ilot de MOSFET non matches, reserve aux
            # tests unitaires).
            + sorted(f for f in ci.glob("logic_*.xml")
                     if "non_dual" not in f.name)
            + sorted(ci.glob("reel_*.xml")))


def _figs_for_file(path, detaille):
    comps = lire_xml(str(path))
    graph = construire_graphe(comps)
    results = detecteur.analyser(graph)
    comp_info = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
                 for c in comps}
    figs = []
    for idx, ilot in enumerate(results.ilots):
        label = ilot.get("label") or f"ilot{idx}"
        fig = _fig_for_ilot(ilot, graph, comp_info, results, detaille=detaille)
        figs.append((f"{path.name}::{label}", fig))
    return figs


def _textes_visibles(fig):
    out = []
    for ax in fig.axes:
        for t in ax.texts:
            if t.get_visible() and t.get_text().strip():
                out.append((t, ax))
        if ax.title.get_visible() and ax.title.get_text().strip():
            out.append((ax.title, ax))
    for t in fig.texts:
        if t.get_visible() and t.get_text().strip():
            out.append((t, None))
    return out


def _chevauchements(fig):
    """@brief Paires de textes dont les bboxes renderer se recouvrent de plus
    de TOLERANCE_PX2 (aire, en pixels²)."""
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    textes = _textes_visibles(fig)
    violations = []
    for i in range(len(textes)):
        ti, _axi = textes[i]
        bi = ti.get_window_extent(renderer)
        for j in range(i + 1, len(textes)):
            tj, _axj = textes[j]
            bj = tj.get_window_extent(renderer)
            ox = min(bi.x1, bj.x1) - max(bi.x0, bj.x0)
            oy = min(bi.y1, bj.y1) - max(bi.y0, bj.y0)
            if ox > 0 and oy > 0 and ox * oy > TOLERANCE_PX2:
                violations.append((ti.get_text(), tj.get_text(), round(ox * oy, 2)))
    return violations


def _hors_cadre(fig):
    """@brief Textes ancrés sur un axe dont la bbox déborde des xlim/ylim
    finaux de cet axe (converti en coordonnées données via transData)."""
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    violations = []
    for ax in fig.axes:
        x0, x1 = sorted(ax.get_xlim())
        y0, y1 = sorted(ax.get_ylim())
        largeur, hauteur = (x1 - x0) or 1.0, (y1 - y0) or 1.0
        eps_x, eps_y = 1e-6 * largeur, 1e-6 * hauteur
        for t in list(ax.texts) + [ax.title]:
            if not (t.get_visible() and t.get_text().strip()):
                continue
            bbox = t.get_window_extent(renderer)
            inv = ax.transData.inverted()
            (dx0, dy0), (dx1, dy1) = inv.transform([(bbox.x0, bbox.y0), (bbox.x1, bbox.y1)])
            tx0, tx1 = sorted((dx0, dx1))
            ty0, ty1 = sorted((dy0, dy1))
            if tx0 < x0 - eps_x or tx1 > x1 + eps_x or ty0 < y0 - eps_y or ty1 > y1 + eps_y:
                violations.append((t.get_text(), (tx0, tx1, ty0, ty1), (x0, x1, y0, y1)))
    return violations


_CAS = [(path, detaille) for path in _circuit_files() for detaille in (False, True)]


@pytest.mark.parametrize(
    "path,detaille", _CAS,
    ids=[f"{p.name}-{'detaille' if d else 'z'}" for p, d in _CAS])
def test_aucun_chevauchement_de_labels(path, detaille):
    for label, fig in _figs_for_file(path, detaille):
        violations = _chevauchements(fig)
        assert not violations, f"{label}: {violations[:5]}"


@pytest.mark.parametrize(
    "path,detaille", _CAS,
    ids=[f"{p.name}-{'detaille' if d else 'z'}" for p, d in _CAS])
def test_aucun_label_hors_cadre(path, detaille):
    for label, fig in _figs_for_file(path, detaille):
        violations = _hors_cadre(fig)
        assert not violations, f"{label}: {violations[:5]}"
