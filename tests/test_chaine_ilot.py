"""@file test_chaine_ilot.py
@brief Vue îlot multi-AOP : ordonnancement par flux + chaîne de schémas connectés."""
from circuit_analyzer.xml import lire_xml
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser
from gui import circuit_viewer as cv


def _matches_chaine():
    comps = lire_xml("circuits_industriels/chaine_5_aop.xml")
    res = analyser(construire_graphe(comps))
    return [r for r in res if "(AOP)" in r["circuit_type"]]


def test_ordonner_montages_flux_chaine_5():
    ordre = cv._ordonner_montages_flux(_matches_chaine())
    assert ordre is not None
    types = [m["circuit_type"] for m in ordre]
    assert types == [
        "Amplificateur non-inverseur (AOP)",
        "Amplificateur inverseur (AOP)",
        "Intégrateur (AOP)",
        "Dérivateur (AOP)",
        "Suiveur de tension (AOP)",
    ]


def test_ordonner_montages_flux_non_chaine_renvoie_none():
    # Deux montages sans lien OUT->IN entre eux : pas une chaîne.
    from circuit_analyzer.composant import Composant
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M1", "OUT": "O1"}),
        Composant("R1", "R", {"1": "VIN", "2": "M1"}, "1k"),
        Composant("R2", "R", {"1": "M1", "2": "O1"}, "10k"),
        Composant("U2", "U", {"IN+": "GND", "IN-": "M2", "OUT": "O2"}),
        Composant("R3", "R", {"1": "AUTRE", "2": "M2"}, "1k"),
        Composant("R4", "R", {"1": "M2", "2": "O2"}, "10k"),
    ]
    res = analyser(construire_graphe(comps))
    aops = [r for r in res if "(AOP)" in r["circuit_type"]]
    assert cv._ordonner_montages_flux(aops) is None


def test_ordonner_ne_crashe_pas_avec_un_sommateur():
    # Sommateur (Zin = LISTE de blocs) dans un ilot multi-AOP : ne doit pas
    # planter (regression : in_net indexait Zin comme un bloc unique).
    from circuit_analyzer.composant import Composant
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "S", "OUT": "SUM"}),
        Composant("Ra", "R", {"1": "IN1", "2": "S"}, "10k"),
        Composant("Rb", "R", {"1": "IN2", "2": "S"}, "10k"),
        Composant("Rf1", "R", {"1": "S", "2": "SUM"}, "10k"),
        Composant("U2", "U", {"IN+": "GND", "IN-": "M", "OUT": "O"}),
        Composant("Rin", "R", {"1": "SUM", "2": "M"}, "10k"),
        Composant("Rf2", "R", {"1": "M", "2": "O"}, "100k"),
    ]
    res = analyser(construire_graphe(comps))
    aops = [r for r in res if "(AOP)" in r["circuit_type"]]
    ordre = cv._ordonner_montages_flux(aops)   # ne doit pas lever
    # sommateur en tete (entree externe IN1/IN2) puis inverseur en aval
    assert ordre is not None
    assert ordre[0]["circuit_type"] == "Amplificateur sommateur (AOP)"


import schemdraw
from matplotlib.figure import Figure


def _imp_inv():
    return {"Zin": {"refs": ["R3"], "composition": "R3", "nodes": ("M", "A")},
            "Zf": {"refs": ["R4"], "composition": "R4", "nodes": ("M", "B")}}


def test_drawer_inverseur_renvoie_ancres_et_suit_origin():
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        a0 = cv._draw_aop_inverseur_zin_zf(d, _imp_inv(), {}, origin=(0, 0))
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        a10 = cv._draw_aop_inverseur_zin_zf(d, _imp_inv(), {}, origin=(10, 0))
    assert set(a0) == {"in", "out"}
    assert a0["out"][0] > a0["in"][0]                 # OUT à droite de IN
    assert abs(a10["in"][0] - a0["in"][0] - 10) < 1e-6  # l'origine décale tout de +10


def test_chaine_garde_les_aop_orientes_a_droite_apres_une_masse():
    comps = lire_xml("circuits_industriels/chaine_5_aop.xml")
    res = analyser(construire_graphe(comps))
    ci = {c.ref: {"type": c.type, "value": c.value} for c in comps}
    ordre = cv._ordonner_montages_flux([r for r in res if "(AOP)" in r["circuit_type"]])
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        ancres = []
        for i, match in enumerate(ordre):
            imp = match.get("impedances") or {}
            oy = cv._AOP_OUT_DY if "Zin" in imp else -cv._AOP_OUT_DY
            origin = (4.5 + i * cv._CHAINE_DX, oy)
            ancres.append(cv._dessiner_montage_a(d, match, ci, origin, "", ""))

    for a in ancres:
        assert a["out"][0] > a["in"][0]
        assert abs(a["out"][1]) < 1e-6


def test_chaine_comparateur_nest_pas_dessine_en_suiveur():
    # Dans la chaine, un comparateur doit utiliser SON dessin (label REF),
    # pas le repli suiveur (_draw_follower) faute de dispatch dedie.
    match = {"circuit_type": "Comparateur (AOP)", "components": ["U1"],
             "nodes": ["A", "GND", "B"]}
    fig = Figure(figsize=(7, 4)); ax = fig.add_subplot(111)
    ax.axis("off"); ax.set_aspect("equal")
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._z_hitboxes = []
        cv._dessiner_montage_a(d, match, {}, (4.5, 0), "", "VOUT")
    assert "REF" in [t.get_text() for t in ax.texts]


def test_chaine_schmitt_dessine_avec_contre_reaction_positive():
    # Schmitt en chaine : boite Zf cliquable SOUS la ligne (contre-reaction
    # positive), pas au-dessus comme le ferait le dessin inverseur (branche Zin).
    match = {"circuit_type": "Bascule de Schmitt (AOP)",
             "components": ["U1", "Rf", "Rin"], "nodes": ["P", "GND", "O"],
             "impedances": {"Zf": {"refs": ["Rf"], "composition": "Rf", "nodes": ("P", "O")},
                            "Zin": {"refs": ["Rin"], "composition": "Rin", "nodes": ("P", "IN")}}}
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        cv._dessiner_montage_a(d, match, {}, (4.5, 0), "", "")
        hb = list(d._z_hitboxes)
    assert len(hb) == 2
    ys = [(y0 + y1) / 2 for _x0, _x1, y0, y1, *_ in hb]
    assert min(ys) < 0   # Zf routee sous la ligne -> specifique au Schmitt


def test_suiveur_ne_superpose_pas_le_fil_vout_et_le_retour():
    fig = Figure(figsize=(7, 4))
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.set_aspect("equal")
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._z_hitboxes = []
        cv._draw_follower(d, {}, {}, origin=(4.5, -cv._AOP_OUT_DY), in_label="", out_label="VOUT")

    horizontaux_sortie = []
    for line in ax.lines:
        xs = [float(x) for x in line.get_xdata()]
        ys = [float(y) for y in line.get_ydata()]
        if len(xs) >= 2 and all(abs(y) < 1e-9 for y in ys):
            horizontaux_sortie.append((min(xs), max(xs)))

    for i, (a0, a1) in enumerate(horizontaux_sortie):
        for b0, b1 in horizontaux_sortie[i + 1:]:
            assert min(a1, b1) - max(a0, b0) <= 1e-9


def test_suiveur_decale_le_retour_du_bord_de_l_aop():
    fig = Figure(figsize=(7, 4))
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.set_aspect("equal")
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._z_hitboxes = []
        cv._draw_follower(d, {}, {}, origin=(4.5, -cv._AOP_OUT_DY), in_label="", out_label="VOUT")

    bord_aop_x = 4.5
    pin_in_moins_y = 0.625
    for line in ax.lines:
        xs = [float(x) for x in line.get_xdata()]
        ys = [float(y) for y in line.get_ydata()]
        if len(xs) >= 2 and all(abs(x - bord_aop_x) < 1e-9 for x in xs):
            assert max(ys) <= pin_in_moins_y + 1e-9


def test_draw_island_chain_hitboxes_et_ordre():
    comps = lire_xml("circuits_industriels/chaine_5_aop.xml")
    res = analyser(construire_graphe(comps))
    ci = {c.ref: {"type": c.type, "value": c.value} for c in comps}
    ordre = cv._ordonner_montages_flux([r for r in res if "(AOP)" in r["circuit_type"]])
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        cv._draw_island_chain(d, ordre, ci)
        hb = list(d._z_hitboxes)
    # non-inv(2) + inverseur(2) + intégrateur(2) + dérivateur(2) + suiveur(0) = 8
    assert len(hb) == 8
    xs = [(x0 + x1) / 2 for x0, x1, *_ in hb]
    assert max(xs) - min(xs) > 10


def test_make_chain_fig_porte_les_hitboxes():
    comps = lire_xml("circuits_industriels/chaine_5_aop.xml")
    res = analyser(construire_graphe(comps))
    ci = {c.ref: {"type": c.type, "value": c.value} for c in comps}
    ordre = cv._ordonner_montages_flux([r for r in res if "(AOP)" in r["circuit_type"]])
    fig = cv._make_chain_fig(ordre, ci)
    assert len(getattr(fig, "_z_hitboxes", [])) == 8
    w, h = fig.get_size_inches()
    assert h <= 4.2 + 1e-6        # hauteur bornée (tient dans la fenêtre)
    assert w > h                  # figure large (chaîne) -> défilement horizontal
