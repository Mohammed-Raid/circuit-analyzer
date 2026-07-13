"""@file test_schema_router.py
@brief Contrats du routeur Manhattan (spec 2026-07-13 §4) : orthogonalite,
evitement d'obstacles, non-chevauchement colineaire, repli None, purete.
"""
import subprocess
import sys

from gui.schema_grid import PAS, Rect
from gui.schema_router import router


def _orthogonale(poly):
    return all(a[0] == b[0] or a[1] == b[1] for a, b in zip(poly, poly[1:]))


def _aretes(poly):
    """Arêtes unitaires (pas PAS) d'une polyligne, normalisées."""
    out = set()
    for (xa, ya), (xb, yb) in zip(poly, poly[1:]):
        n = round(max(abs(xb - xa), abs(yb - ya)) / PAS)
        dx, dy = (xb - xa) / n, (yb - ya) / n
        for k in range(n):
            p = (round(xa + k * dx, 6), round(ya + k * dy, 6))
            q = (round(xa + (k + 1) * dx, 6), round(ya + (k + 1) * dy, 6))
            out.add((min(p, q), max(p, q)))
    return out


def test_route_directe_sans_obstacle():
    res = router([("n1", (0.0, 0.0), (4.0, 0.0))], [])
    poly = res["n1"]
    assert poly[0] == (0.0, 0.0) and poly[-1] == (4.0, 0.0)
    assert _orthogonale(poly)
    assert len(poly) == 2  # segments colinéaires fusionnés


def test_contourne_un_obstacle():
    mur = Rect(1.0, -3.0, 3.0, 3.0)
    res = router([("n1", (0.0, 0.0), (4.0, 0.0))], [mur])
    poly = res["n1"]
    assert poly is not None and _orthogonale(poly)
    # Aucun point intermédiaire strictement dans l'obstacle.
    for (xa, ya), (xb, yb) in zip(poly, poly[1:]):
        mx, my = (xa + xb) / 2, (ya + yb) / 2
        assert not mur.contient_strict(mx, my), poly


def test_depart_arrivee_sur_frontiere_obstacle():
    # Cas nominal des ports : le point de départ est SUR le bord d'un slot.
    slot = Rect(0.0, -2.0, 2.0, 2.0)
    res = router([("n1", (2.0, 0.0), (6.0, 0.0))], [slot])
    assert res["n1"] is not None


def test_deux_nets_ne_partagent_pas_d_arete():
    # Deux nets de même départ→même couloir : le 2e doit dévier.
    nets = [("a", (0.0, 0.0), (6.0, 0.0)),
            ("b", (0.0, -0.5), (6.0, -0.5))]
    res = router(nets, [])
    assert res["a"] and res["b"]
    assert not (_aretes(res["a"]) & _aretes(res["b"]))


def test_croisement_perpendiculaire_autorise():
    nets = [("h", (0.0, 0.0), (4.0, 0.0)),
            ("v", (2.0, -2.0), (2.0, 2.0))]
    res = router(nets, [])
    assert res["h"] and res["v"]   # le croisement en (2,0) est légal


def test_grille_saturee_renvoie_none():
    # Départ complètement muré -> pas de chemin -> None (repli appelant).
    dep = (0.0, 0.0)
    murs = [Rect(-1.0, -1.0, 1.0, -0.5), Rect(-1.0, 0.5, 1.0, 1.0),
            Rect(-1.0, -1.0, -0.5, 1.0), Rect(0.5, -1.0, 1.0, 1.0)]
    res = router([("n1", dep, (8.0, 0.0))], murs)
    assert res["n1"] is None


def test_import_sans_backend_graphique():
    code = ("import sys; import gui.schema_router; "
            "sys.exit(1 if any(m in sys.modules for m in "
            "('matplotlib', 'schemdraw', 'tkinter')) else 0)")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert r.returncode == 0, r.stderr
