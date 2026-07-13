"""@file test_schema_grid.py
@brief Contrats de la grille absolue (spec 2026-07-13 §3) : snap, formules
x(c)/y(b), obstacles = slots, déterminisme strict, pureté d'import.
"""
import subprocess
import sys

from gui.schema_grid import (PAS, MARGE, CANAL_H, CANAL_V, X0,
                             EtageMesure, PlanGrille, Rect, poser,
                             snap, snap_ceil)


def _etages_2x1():
    # Chaîne de 2 étages, une bande : largeurs 7.3 et 4.1, hauteurs 5.0/3.0.
    return [
        EtageMesure("A", colonne=0, bande=0, largeur=7.3, hauteur=5.0,
                    ancrage_x=1.2, ancrage_y=0.625),
        EtageMesure("B", colonne=1, bande=0, largeur=4.1, hauteur=3.0,
                    ancrage_x=0.4, ancrage_y=-0.625),
    ]


def test_snap_et_snap_ceil():
    assert snap(1.24) == 1.0
    assert snap(1.26) == 1.5
    assert snap_ceil(7.3 + 2 * MARGE) == 9.5   # ceil(9.3/0.5)*0.5
    assert snap_ceil(4.0) == 4.0               # déjà multiple


def test_formules_x_colonne():
    plan = poser(_etages_2x1())
    # L(0) = snap_ceil(7.3 + 2*MARGE) = 9.5 ; x(0)=X0 ; x(1)=X0+9.5+CANAL_H
    assert plan.slots["A"].x0 == X0
    assert plan.slots["B"].x0 == X0 + 9.5 + CANAL_H
    # origine = (x(c) + MARGE + ancrage_x, y(b) + ancrage_y), snappée
    ox, oy = plan.origines["A"]
    assert ox == snap(X0 + MARGE + 1.2)
    assert oy == snap(0.0 + 0.625)


def test_formules_y_bande():
    etages = [
        EtageMesure("H", 0, 0, largeur=4.0, hauteur=6.0, ancrage_x=0, ancrage_y=0),
        EtageMesure("B", 0, 1, largeur=4.0, hauteur=3.0, ancrage_x=0, ancrage_y=0),
    ]
    plan = poser(etages)
    # H(0)=6.0 ; y(1) = y(0) - H(0) - CANAL_V = -8.0
    assert plan.origines["B"][1] == snap(-6.0 - CANAL_V)


def test_tout_est_sur_la_grille():
    plan = poser(_etages_2x1())
    pts = list(plan.origines.values())
    for r in plan.obstacles:
        pts += [(r.x0, r.y0), (r.x1, r.y1)]
    for x, y in pts:
        assert abs(x / PAS - round(x / PAS)) < 1e-9, (x, y)
        assert abs(y / PAS - round(y / PAS)) < 1e-9, (x, y)


def test_un_obstacle_par_etage_couvre_le_slot():
    plan = poser(_etages_2x1())
    assert len(plan.obstacles) == 2
    assert plan.slots["A"] in plan.obstacles


def test_deterministe_meme_en_ordre_inverse():
    a = poser(_etages_2x1())
    b = poser(list(reversed(_etages_2x1())))
    assert a == b


def test_import_sans_backend_graphique():
    # Le module doit s'importer sans tirer matplotlib/schemdraw/tkinter.
    code = ("import sys; import gui.schema_grid; "
            "interdits = [m for m in ('matplotlib', 'schemdraw', 'tkinter') "
            "if m in sys.modules]; "
            "sys.exit(1 if interdits else 0)")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert r.returncode == 0, r.stderr
