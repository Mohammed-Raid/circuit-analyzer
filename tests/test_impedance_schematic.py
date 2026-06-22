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


def test_dessiner_produit_une_figure_sans_exception():
    from circuit_analyzer.composant import Composant
    comps = {
        "R1": Composant("R1", "R", {"1": "A", "2": "M"}, "1k"),
        "R2": Composant("R2", "R", {"1": "M", "2": "B"}, "2k"),
        "R3": Composant("R3", "R", {"1": "A", "2": "B"}, "3k"),
    }
    arbre = ("parallele", [("serie", [("feuille", "R1"), ("feuille", "R2")]),
                           ("feuille", "R3")])
    fig = sch.dessiner(arbre, "VIN", "VOUT", comps)
    assert fig is not None
    assert len(fig.axes) == 1


def test_dessiner_pont_simple_pas_de_hitbox():
    from circuit_analyzer.composant import Composant
    comps = {r: Composant(r, "R", {"1": "x", "2": "y"}, "1k")
             for r in ("R1", "R2", "R3", "R4", "R5")}
    pont = {
        "haut": "VIN", "bas": "VOUT", "gauche": "N1", "droite": "N2",
        "bras": {role: {"refs": [r], "composition": r} for role, r in (
            ("haut_gauche", "R1"), ("haut_droite", "R2"), ("bas_gauche", "R3"),
            ("bas_droite", "R4"), ("pont", "R5"))},
    }
    fig = sch.dessiner_pont(pont, comps)
    assert fig is not None and len(fig.axes) == 1
    assert getattr(fig, "_z_hitboxes", []) == []   # tous simples -> aucun hitbox


def test_dessiner_pont_composite_a_un_hitbox():
    from circuit_analyzer.composant import Composant
    comps = {r: Composant(r, "R", {"1": "x", "2": "y"}, "1k")
             for r in ("R1", "R6", "R2", "R3", "R4", "R5")}
    pont = {
        "haut": "VIN", "bas": "VOUT", "gauche": "N1", "droite": "N2",
        "bras": {
            "haut_gauche": {"refs": ["R1", "R6"], "composition": "R1+R6"},
            "haut_droite": {"refs": ["R2"], "composition": "R2"},
            "bas_gauche": {"refs": ["R3"], "composition": "R3"},
            "bas_droite": {"refs": ["R4"], "composition": "R4"},
            "pont": {"refs": ["R5"], "composition": "R5"},
        },
    }
    fig = sch.dessiner_pont(pont, comps)
    boites = getattr(fig, "_z_hitboxes", [])
    assert len(boites) == 1
    x0, x1, y0, y1, refs, composition = boites[0]
    assert set(refs) == {"R1", "R6"}


def test_dessiner_pont_deux_bras_composites_hitboxes_disjoints():
    from circuit_analyzer.composant import Composant
    comps = {r: Composant(r, "R", {"1": "x", "2": "y"}, "1k")
             for r in ("R1", "R6", "R2", "R7", "R3", "R4", "R5")}
    pont = {
        "haut": "VIN", "bas": "VOUT", "gauche": "N1", "droite": "N2",
        "bras": {
            "haut_gauche": {"refs": ["R1", "R6"], "composition": "R1+R6"},
            "haut_droite": {"refs": ["R2", "R7"], "composition": "R2+R7"},
            "bas_gauche": {"refs": ["R3"], "composition": "R3"},
            "bas_droite": {"refs": ["R4"], "composition": "R4"},
            "pont": {"refs": ["R5"], "composition": "R5"},
        },
    }
    fig = sch.dessiner_pont(pont, comps)
    boites = fig._z_hitboxes
    assert len(boites) == 2
    (ax0, ax1, ay0, ay1, _, _), (bx0, bx1, by0, by1, _, _) = boites
    # Les deux boites ne se chevauchent pas (clic non ambigu).
    disjoints = ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0
    assert disjoints


def _comps_rlc(*refs):
    from circuit_analyzer.composant import Composant
    t = {"C1": "C", "C2": "C", "L1": "L"}
    return {r: Composant(r, t.get(r, "R"), {"1": "x", "2": "y"}, "1k") for r in refs}


def test_dessiner_groupe_cree_boites_z_cliquables():
    # R1 + ((R2+C1)//(L1+R3)) + (R4//C2) -> R1 (feuille) + Z1 + Z2
    arbre = ("serie", [
        ("feuille", "R1"),
        ("parallele", [("serie", [("feuille", "R2"), ("feuille", "C1")]),
                       ("serie", [("feuille", "L1"), ("feuille", "R3")])]),
        ("parallele", [("feuille", "R4"), ("feuille", "C2")]),
    ])
    comps = _comps_rlc("R1", "R2", "C1", "L1", "R3", "R4", "C2")
    fig = sch.dessiner_groupe(arbre, "VIN", "VOUT", comps)
    hb = fig._z_hitboxes
    assert len(hb) == 2                       # deux sous-blocs -> deux boites Z
    refs_par_boite = sorted((sorted(b[4]) for b in hb), key=len)
    assert refs_par_boite[0] == ["C2", "R4"]                       # Z2 = R4//C2
    assert refs_par_boite[1] == ["C1", "L1", "R2", "R3"]           # Z1 = (R2+C1)//(L1+R3)
    # la composition stockee doit etre reparsable (pour le drill-down)
    from circuit_analyzer import impedance
    for b in hb:
        assert impedance.arbre_expr(b[5]) is not None


def test_dessiner_groupe_tout_simple_aucune_boite():
    arbre = ("serie", [("feuille", "R1"), ("feuille", "R2")])
    fig = sch.dessiner_groupe(arbre, "A", "B", _comps_rlc("R1", "R2"))
    assert fig._z_hitboxes == []
