"""@file test_impedance_schematic.py
@brief Tests de la mise en page serie/parallele (gui/impedance_schematic.py)."""
from gui import impedance_schematic as sch


def test_agencer_serie_aligne_les_enfants_en_ligne():
    arbre = ("serie", [("feuille", "R1"), ("feuille", "R2")])
    symboles, fils, dims = sch.agencer(arbre)
    assert len(symboles) == 2
    # x croissants (R1 a gauche de R2), meme ligne de bornes (y egaux).
    xs = sorted(s[1] for s in symboles)
    assert xs[0] < xs[1]
    assert symboles[0][3] == symboles[1][3]
    # largeur de la boite = 2 symboles + 1 fil entre eux.
    assert abs(dims.largeur - (2 * sch.W_SYMB + sch.LEAD)) < 1e-9


def test_agencer_parallele_empile_les_enfants():
    arbre = ("parallele", [("feuille", "R1"), ("feuille", "R2")])
    symboles, fils, dims = sch.agencer(arbre)
    assert len(symboles) == 2
    # y distincts (empiles), donc hauteur = 2 symboles + 1 ecart vertical.
    ys = sorted(s[3] for s in symboles)
    assert ys[0] < ys[1]
    assert abs(dims.hauteur - (2 * sch.H_SYMB + sch.GAP_V)) < 1e-9
    # des fils relient les branches aux rails (au moins 2 liaisons + 2 rails).
    assert len(fils) >= 4


def test_agencer_feuille_seule():
    symboles, fils, dims = sch.agencer(("feuille", "R1"))
    assert len(symboles) == 1
    assert symboles[0][0] == "R1"
    assert fils == []
    assert abs(dims.largeur - sch.W_SYMB) < 1e-9
