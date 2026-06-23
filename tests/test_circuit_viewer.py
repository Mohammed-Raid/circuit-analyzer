"""@file test_circuit_viewer.py
@brief Tests du builder de figure (passe-plat des zones cliquables Z)."""
from gui import circuit_viewer as cv


def test_make_fig_remonte_les_hitboxes_du_drawer():
    def _faux_drawer(d, result, ci):
        d._z_hitboxes.append((0.0, 1.0, 0.0, 1.0, ["R1"], "R1"))
    fig = cv._make_fig({"circuit_type": "X", "components": []}, {}, _faux_drawer)
    assert getattr(fig, "_z_hitboxes", None) == [(0.0, 1.0, 0.0, 1.0, ["R1"], "R1")]


def test_make_fig_sans_hitbox_liste_vide():
    fig = cv._make_fig({"circuit_type": "X", "components": []}, {}, None)
    assert fig._z_hitboxes == []
