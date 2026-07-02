"""Expansion d'une composition Z en réseau R/L/C entre deux points (vue détaillée)."""
import math
from circuit_analyzer.impedance import arbre_expr
from gui.circuit_viewer import _agencement_entre


def _pres(a, b, tol=1e-6):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def test_serie_horizontale_reste_sur_l_axe():
    arbre = arbre_expr("(R1)+(R2)")
    symboles, fils = _agencement_entre((0.0, 0.0), (6.0, 0.0), arbre)
    assert [s[0] for s in symboles] == ["R1", "R2"]
    for _ref, pa, pb in symboles:          # tout sur l'axe y=0
        assert abs(pa[1]) < 1e-6 and abs(pb[1]) < 1e-6
    assert symboles[0][1][0] < symboles[0][2][0] <= symboles[1][1][0]


def test_parallele_branches_de_part_et_d_autre():
    arbre = arbre_expr("(R1)//(C1)")
    symboles, fils = _agencement_entre((0.0, 0.0), (6.0, 0.0), arbre)
    ys = sorted(s[1][1] for s in symboles)
    assert len(symboles) == 2 and ys[0] < ys[1]      # branches empilées
    assert fils, "rails et connecteurs attendus"


def test_segment_vertical_pivote():
    arbre = arbre_expr("(R1)+(R2)")
    symboles, _ = _agencement_entre((0.0, 0.0), (0.0, -6.0), arbre)
    for _ref, pa, pb in symboles:          # tout sur l'axe x=0, y décroissant
        assert abs(pa[0]) < 1e-6 and abs(pb[0]) < 1e-6
    assert symboles[0][1][1] > symboles[1][1][1]


def test_composition_pont_non_depliable():
    assert arbre_expr("(R1)*(R2)/((R1)+(R2)+(R3))") is None
