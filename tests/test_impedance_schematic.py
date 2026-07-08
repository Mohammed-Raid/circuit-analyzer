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


def test_agencer_parallele_dense_reste_lisible_en_fenetre_detail():
    arbre = ("parallele", [
        ("feuille", "L1"), ("feuille", "R3"), ("feuille", "C2"), ("feuille", "R4"),
    ])
    symboles, _fils, dims = sch.agencer(arbre)
    assert len(symboles) == 4
    assert dims.hauteur / dims.largeur <= 2.0


def test_dessiner_parallele_dense_ne_produit_pas_une_popup_trop_verticale():
    arbre = ("parallele", [
        ("feuille", "L1"), ("feuille", "R3"), ("feuille", "C2"), ("feuille", "R4"),
    ])
    fig = sch.dessiner(arbre, "A", "B", _comps_rlc("L1", "R3", "C2", "R4"))
    w, h = fig.get_size_inches()
    assert h / w <= 1.4


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


def _all_texts(fig):
    out = [t.get_text() for t in fig.texts]
    for ax in fig.axes:
        out += [t.get_text() for t in ax.texts]
        if ax.get_title():
            out.append(ax.get_title())
    return out


def test_dessiner_affiche_le_titre_de_composition():
    comps = _comps_rlc("R2", "R3")
    arbre = ("serie", [("feuille", "R2"), ("feuille", "R3")])
    fig = sch.dessiner(arbre, "A", "B", comps, titre="Z = R2+R3")
    assert any("Z = R2+R3" in t for t in _all_texts(fig))


def test_dessiner_sans_titre_inchange():
    comps = _comps_rlc("R2", "R3")
    arbre = ("serie", [("feuille", "R2"), ("feuille", "R3")])
    fig = sch.dessiner(arbre, "A", "B", comps)
    assert not any("Z = " in t for t in _all_texts(fig))


def test_dessiner_pont_affiche_le_titre():
    from circuit_analyzer.composant import Composant
    comps = {r: Composant(r, "R", {"1": "x", "2": "y"}, "1k")
             for r in ("R1", "R2", "R3", "R4", "R5")}
    pont = {
        "haut": "VIN", "bas": "VOUT", "gauche": "N1", "droite": "N2",
        "bras": {role: {"refs": [r], "composition": r} for role, r in (
            ("haut_gauche", "R1"), ("haut_droite", "R2"), ("bas_gauche", "R3"),
            ("bas_droite", "R4"), ("pont", "R5"))},
    }
    fig = sch.dessiner_pont(pont, comps, titre="Z = pont")
    assert any("Z = pont" in t for t in _all_texts(fig))


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


def test_dessiner_pont_bras_simple_labels_ref_et_valeur_separes():
    # Idiome feuille unifie (meme regle que _dessiner_impl / style_symbole) :
    # ref et valeur d'un bras simple = DEUX Texts distincts (ref loc="top",
    # valeur loc="bottom"), jamais un « ref\nvaleur » combine.
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
    txts = _all_texts(fig)
    assert not any("\n" in t for t in txts), (
        "aucun label combine ref\\nvaleur sur un bras simple")
    for r in ("R1", "R2", "R3", "R4", "R5"):
        assert r in txts, f"ref {r} en Text autonome"
    assert txts.count("1 kΩ") == 5, "une valeur autonome par bras"


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


def test_dessiner_bloc_reseau_entier_en_une_boite_z():
    # L1 + (R1//C1) -> UNE seule boite Z contenant tout (L1 inclus), cliquable.
    arbre = ("serie", [
        ("feuille", "L1"),
        ("parallele", [("feuille", "R1"), ("feuille", "C1")]),
    ])
    comps = _comps_rlc("L1", "R1", "C1")
    fig = sch.dessiner_bloc(arbre, "VIN", "VOUT", comps)
    hb = fig._z_hitboxes
    assert len(hb) == 1                       # tout le reseau = une boite Z
    x0, x1, y0, y1, refs, composition = hb[0]
    assert set(refs) == {"L1", "R1", "C1"}    # L1 est dedans, pas laisse nu
    # la composition stockee est reparsable (pour le drill-down vers le detail)
    from circuit_analyzer import impedance
    assert impedance.arbre_expr(composition) is not None


def test_dessiner_bloc_un_seul_composant_pas_de_boite():
    fig = sch.dessiner_bloc(("feuille", "R1"), "A", "B", _comps_rlc("R1"))
    assert fig._z_hitboxes == []              # rien a deplier sur un composant seul
