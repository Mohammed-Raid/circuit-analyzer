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


def test_layers_montages_flux_pid_trois_couches():
    # pid = DAG branche : entree -> {P, I, D paralleles} -> sommateur -> buffer.
    # _ordonner_montages_flux echoue (bifurcation) ; _layers_montages_flux doit
    # produire 3 couches malgre le back-edge du a la mauvaise detection de l'etage P.
    comps = lire_xml("circuits_industriels/pid_controller.xml")
    res = analyser(construire_graphe(comps))
    ilot = max(res.ilots, key=lambda i: len(i["composants"]))
    matches = cv._matches_for_island(ilot, res)
    layers = cv._layers_montages_flux(matches)
    assert layers is not None
    assert len(layers) == 3
    assert len(layers[0]) == 3                                  # P, I, D en parallele
    assert layers[1][0]["circuit_type"] == "Amplificateur sommateur (AOP)"
    assert layers[2][0]["circuit_type"] == "Suiveur de tension (AOP)"


def test_make_branched_fig_pid_rend_sans_erreur():
    # La vue branchee de pid se rend en schema connecte (pas de repli grille).
    comps = lire_xml("circuits_industriels/pid_controller.xml")
    res = analyser(construire_graphe(comps))
    ilot = max(res.ilots, key=lambda i: len(i["composants"]))
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    layers = cv._layers_montages_flux(cv._matches_for_island(ilot, res))
    fig = cv._make_branched_fig(layers, ci)
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert not any("non disponible" in t for t in txts)
    assert len(getattr(fig, "_z_hitboxes", [])) >= 6   # boites Z des etages preservees


def test_titre_etage_roles():
    assert cv._titre_etage({"circuit_type": "Intégrateur (AOP)"}) == "Intégrateur"
    assert cv._titre_etage({"circuit_type": "Amplificateur sommateur (AOP)"}) == "Sommateur"
    assert cv._titre_etage({"circuit_type": "Amplificateur non-inverseur (AOP)"}) == "Non-inverseur"
    assert cv._titre_etage({"circuit_type": "Suiveur de tension (AOP)"}) == "Suiveur"


def test_branched_view_annote_roles_et_gains():
    # Chaque étage porte son rôle (titre) ; les étages à gain affichent "Av = …".
    comps = lire_xml("circuits_industriels/pid_controller.xml")
    res = analyser(construire_graphe(comps))
    ilot = max(res.ilots, key=lambda i: len(i["composants"]))
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    layers = cv._layers_montages_flux(cv._matches_for_island(ilot, res))
    fig = cv._make_branched_fig(layers, ci)
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    blob = " | ".join(txts)
    for role in ("Intégrateur", "Dérivateur", "Sommateur", "Suiveur"):
        assert role in blob, f"rôle manquant: {role}"
    assert sum(1 for t in txts if t.startswith("Av")) >= 3   # gains par étage


def test_branched_edges_pid_forward_only():
    # Le câblage branché ne doit garder que les arêtes AVANT : pas de fil de retour
    # buffer -> étage P (back-edge dû à la mauvaise détection) qui traverse tout.
    comps = lire_xml("circuits_industriels/pid_controller.xml")
    res = analyser(construire_graphe(comps))
    ilot = max(res.ilots, key=lambda i: len(i["composants"]))
    layers = cv._layers_montages_flux(cv._matches_for_island(ilot, res))
    edges = cv._branched_edges(layers)
    layer_of = {id(m): lx for lx, L in enumerate(layers) for m in L}
    assert edges, "au moins une arête attendue"
    assert all(layer_of[id(p)] < layer_of[id(c)] for p, c, _ in edges)
    assert len(edges) == 4          # D, I, P -> sommateur ; sommateur -> buffer


def test_branched_fanin_channels_follow_input_order(monkeypatch):
    # Dans un fan-in ordonne bas -> haut, les entrees basses doivent prendre les
    # canaux les plus a droite. Sinon le long fil de la branche basse traverse
    # la zone des autres sorties avant d'entrer dans le sommateur.
    import schemdraw

    comps = lire_xml("circuits_industriels/pid_controller.xml")
    res = analyser(construire_graphe(comps))
    ilot = max(res.ilots, key=lambda i: len(i["composants"]))
    layers = cv._layers_montages_flux(cv._matches_for_island(ilot, res))
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}

    routes = []

    def capture_route(_d, out_pt, in_pt, channel_x):
        routes.append((out_pt, in_pt, channel_x))

    monkeypatch.setattr(cv, "_fil_canal", capture_route)
    d = schemdraw.Drawing(show=False)
    d._z_hitboxes = []
    cv._draw_branched_chain(d, layers, ci)

    fanin = [r for r in routes if abs(r[1][0] - 12.7) < 1e-6]
    assert len(fanin) == 3
    fanin.sort(key=lambda r: r[1][1])       # entree basse -> entree haute
    xs = [r[2] for r in fanin]
    assert xs == sorted(xs, reverse=True)


def test_z_label_anchor_is_clear_of_component_body():
    # Les labels Z sont sur deux lignes ; a 0.35 unite ils chevauchent le symbole
    # et les pistes. On garde au moins 0.9 unite de degagement vertical.
    top = cv._z_label_anchor((1.0, 2.0), (4.0, 2.0), "top")
    bottom = cv._z_label_anchor((1.0, 2.0), (4.0, 2.0), "bottom")

    assert top["pos"] == (2.5, 2.95)
    assert top["ha"] == "center"
    assert top["va"] == "bottom"
    assert bottom["pos"] == (2.5, 1.05)
    assert bottom["ha"] == "center"
    assert bottom["va"] == "top"


def test_sommateur_input_rows_leave_room_for_two_line_labels():
    import schemdraw

    match = {
        "circuit_type": "Amplificateur sommateur (AOP)",
        "components": ["U1", "Rf", "Ra", "Rb", "Rc"],
        "nodes": ["A", "S", "OUT"],
        "impedances": {
            "Zf": {"refs": ["Rf"], "composition": "Rf", "nodes": ("S", "OUT")},
            "Zin": [
                {"refs": ["Ra"], "composition": "Ra", "nodes": ("S", "A")},
                {"refs": ["Rb"], "composition": "Rb", "nodes": ("S", "B")},
                {"refs": ["Rc"], "composition": "Rc", "nodes": ("S", "C")},
            ],
        },
    }
    d = schemdraw.Drawing(show=False)
    d._z_hitboxes = []
    anchors = cv._dessiner_montage_a(d, match, {}, (5.0, cv._AOP_OUT_DY), "", "")
    ys = [pt[1] for pt in anchors["in_pts"]]

    assert min(b - a for a, b in zip(ys, ys[1:])) >= 2.2


def test_sommateur_input_label_anchor_stays_above_track():
    label = cv._sum_input_label_anchor((10.0, 4.0))

    assert label["pos"] == (9.75, 4.45)
    assert label["ha"] == "right"
    assert label["va"] == "bottom"


def test_figure_pixel_size_uses_native_matplotlib_dimensions():
    from matplotlib.figure import Figure

    fig = Figure(figsize=(12.5, 7.25), dpi=120)

    assert cv._figure_pixel_size(fig) == (1500, 870)


def test_zoom_scale_is_clamped():
    assert cv._zoom_next_scale(1.0, 120) == 1.15
    assert cv._zoom_next_scale(1.0, -120) == 1 / 1.15
    assert cv._zoom_next_scale(2.95, 120) == 3.0
    assert cv._zoom_next_scale(0.31, -120) == 0.3


def test_zoom_scroll_fraction_keeps_mouse_world_point_stable():
    fx, fy = cv._zoom_scroll_fractions(
        old_size=(1000, 800),
        new_size=(1500, 1200),
        viewport=(500, 400),
        pointer=(250, 200),
        canvas_origin=(100, 80),
    )

    assert round(fx, 4) == 0.275
    assert round(fy, 4) == 0.275


def test_scrollable_mpl_bindings_preserve_matplotlib_handlers():
    class _Widget:
        def __init__(self):
            self.calls = []

        def bind(self, sequence, callback, add=None):
            self.calls.append((sequence, callback, add))

    widget = _Widget()
    cv._bind_scrollable_mpl_events(widget, object(), object(), object())

    assert {seq for seq, _cb, _add in widget.calls} == {
        "<MouseWheel>", "<ButtonPress-1>", "<B1-Motion>"}
    assert all(add == "+" for _seq, _cb, add in widget.calls)


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


def test_ilot_tous_aop_est_une_chaine_rendue_sans_erreur():
    comps = lire_xml("circuits_industriels/ilot_tous_aop.xml")
    res = analyser(construire_graphe(comps))
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i["composants"]))
    ordre = cv._ordonner_montages_flux(cv._matches_for_island(ilot, res))
    assert [m["circuit_type"] for m in ordre] == [
        "Amplificateur différentiel (AOP)",
        "Amplificateur sommateur (AOP)",
        "Amplificateur non-inverseur (AOP)",
        "Amplificateur inverseur (AOP)",
        "Intégrateur (AOP)",
        "Dérivateur (AOP)",
        "Suiveur de tension (AOP)",
        "Bascule de Schmitt (AOP)",
        "Comparateur (AOP)",
    ]

    fig = cv._make_chain_fig(ordre, ci)
    textes = [t.get_text() for t in fig.axes[0].texts]
    assert not any("Schéma non disponible" in t for t in textes)
    assert len(getattr(fig, "_z_hitboxes", [])) >= 14


import schemdraw
from matplotlib.figure import Figure


def _imp_inv():
    return {"Zin": {"refs": ["R3"], "composition": "R3", "nodes": ("M", "A")},
            "Zf": {"refs": ["R4"], "composition": "R4", "nodes": ("M", "B")}}


def test_drawer_inverseur_renvoie_ancres_et_suit_origin():
    d = schemdraw.Drawing(show=False)
    d._z_hitboxes = []
    a0 = cv._draw_aop_inverseur_zin_zf(d, _imp_inv(), {}, origin=(0, 0))
    d = schemdraw.Drawing(show=False)
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
    d = schemdraw.Drawing(show=False)
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
    d = schemdraw.Drawing(show=False)
    d._z_hitboxes = []
    cv._dessiner_montage_a(d, match, {}, (4.5, 0), "", "")
    hb = list(d._z_hitboxes)
    assert len(hb) == 2
    ys = [(y0 + y1) / 2 for _x0, _x1, y0, y1, *_ in hb]
    assert min(ys) < 0   # Zf routee sous la ligne -> specifique au Schmitt


def test_sommateur_chaine_masque_l_entree_interne_in1():
    match = {
        "circuit_type": "Amplificateur sommateur (AOP)",
        "components": ["U1", "Rf", "Ra", "Rb"],
        "nodes": ["PREV", "S", "OUT"],
        "impedances": {
            "Zf": {"refs": ["Rf"], "composition": "Rf", "nodes": ("S", "OUT")},
            "Zin": [
                {"refs": ["Ra"], "composition": "Ra", "nodes": ("S", "PREV")},
                {"refs": ["Rb"], "composition": "Rb", "nodes": ("S", "AUX")},
            ],
        },
    }
    fig = Figure(figsize=(7, 4))
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.set_aspect("equal")
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._z_hitboxes = []
        cv._dessiner_montage_a(d, match, {}, (5.0, cv._AOP_OUT_DY), "", "")

    textes = [t.get_text() for t in ax.texts]
    assert "IN1" not in textes
    assert "IN2" in textes


def test_texte_gain_sommateur_ne_plante_pas():
    # Sommateur : imp['Zin'] est une LISTE (entrees multiples). _texte_gain ne doit
    # pas la traiter comme un dict -> sinon show_island plante avant d'afficher l'ilot.
    comps = lire_xml("circuits_industriels/summing_aop.xml")
    graph = construire_graphe(comps)
    res = analyser(graph)
    somm = next(r for r in res if r["circuit_type"] == "Amplificateur sommateur (AOP)")
    assert isinstance(somm["impedances"]["Zin"], list)   # garde-fou du scenario
    txt = cv._texte_gain(somm, graph)
    assert txt is None or txt.startswith("Av")


def test_differentiel_tete_de_chaine_libelle_vin_moins_plus():
    match = {
        "circuit_type": "Amplificateur différentiel (AOP)",
        "components": ["U1", "R1", "Rf", "R3", "Rg"],
        "nodes": ["P", "N", "OUT"],
        "impedances": {
            "Z1": {"refs": ["R1"], "composition": "R1", "nodes": ("N", "VINM")},
            "Zf": {"refs": ["Rf"], "composition": "Rf", "nodes": ("N", "OUT")},
            "Z3": {"refs": ["R3"], "composition": "R3", "nodes": ("P", "VINP")},
            "Zg": {"refs": ["Rg"], "composition": "Rg", "nodes": ("P", "GND")},
        },
    }
    fig = Figure(figsize=(7, 4))
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.set_aspect("equal")
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._z_hitboxes = []
        cv._dessiner_montage_a(d, match, {}, (6.0, 0), "VIN", "")

    textes = [t.get_text() for t in ax.texts]
    assert "VIN-" in textes
    assert "VIN+" in textes


def test_differentiel_labels_z1_z3_ne_se_chevauchent_pas():
    # Z1 (sur IN-) et Z3 (sur IN+) partagent la meme plage x et des branches
    # d'entree tres proches : leurs libelles doivent rester separes verticalement.
    imp = {
        "Z1": {"refs": ["R1"], "composition": "R1", "nodes": ("INM", "IN1")},
        "Zf": {"refs": ["R2"], "composition": "R2", "nodes": ("INM", "OUT")},
        "Z3": {"refs": ["R3"], "composition": "R3", "nodes": ("INP", "IN2")},
        "Zg": {"refs": ["R4"], "composition": "R4", "nodes": ("INP", "GND")},
    }
    ci = {r: {"type": "R", "value": "10k"} for r in ("R1", "R2", "R3", "R4")}
    fig = Figure(figsize=(7, 5))
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.set_aspect("equal")
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._z_hitboxes = []
        cv._draw_aop_differentiel(d, imp, ci, (6.0, 0))
        hbs = list(d._z_hitboxes)

    ys = {t.get_text().split("\n")[0]: t.get_position()[1] for t in ax.texts}
    z3_box = next(h for h in hbs if h[4] == ["R3"])
    z3_centre_y = (z3_box[2] + z3_box[3]) / 2
    # Le libelle Z3 doit etre ancre SOUS sa boite (cote oppose a Z1, qui est
    # au-dessus) : sinon son texte 2 lignes remonte dans la boite Z1.
    assert ys["Z3"] < z3_centre_y, f"label Z3 du mauvais cote: {ys['Z3']} >= {z3_centre_y}"
    # ... et les deux libelles divergent nettement.
    assert ys["Z1"] - ys["Z3"] >= 1.8, f"labels trop proches: Z1={ys['Z1']}, Z3={ys['Z3']}"


def test_dessiner_montage_a_sommateur_expose_ins_par_net():
    # Pour le cablage branche, le sommateur doit exposer une ancre par net d'entree.
    match = {
        "circuit_type": "Amplificateur sommateur (AOP)",
        "components": ["U1", "Rf", "Ra", "Rb"], "nodes": ["GND", "S", "OUT"],
        "impedances": {
            "Zf": {"refs": ["Rf"], "composition": "Rf", "nodes": ("S", "OUT")},
            "Zin": [{"refs": ["Ra"], "composition": "Ra", "nodes": ("S", "A")},
                    {"refs": ["Rb"], "composition": "Rb", "nodes": ("S", "B")}],
        },
    }
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        res = cv._dessiner_montage_a(d, match, {}, (5.0, cv._AOP_OUT_DY), "", "")
    assert set(res["ins"]) == {"A", "B"}
    for pt in res["ins"].values():
        assert len(pt) == 2


def test_dessiner_montage_a_differentiel_expose_deux_ins():
    match = {
        "circuit_type": "Amplificateur différentiel (AOP)",
        "components": ["U1", "R1", "Rf", "R3", "Rg"], "nodes": ["P", "N", "OUT"],
        "impedances": {
            "Z1": {"refs": ["R1"], "composition": "R1", "nodes": ("N", "E1")},
            "Zf": {"refs": ["Rf"], "composition": "Rf", "nodes": ("N", "OUT")},
            "Z3": {"refs": ["R3"], "composition": "R3", "nodes": ("P", "E2")},
            "Zg": {"refs": ["Rg"], "composition": "Rg", "nodes": ("P", "GND")},
        },
    }
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        res = cv._dessiner_montage_a(d, match, {}, (6.0, 0), "", "")
    assert set(res["ins"]) == {"E1", "E2"}


def test_suiveur_dessine_le_pont_diviseur_sur_in_plus():
    # IN+ alimente par un pont VCC-VREF_IN-GND : le suiveur dessine les 2 Z + VCC.
    result = {"circuit_type": "Suiveur de tension (AOP)",
              "nodes": ["VREF_IN", "VOUT"], "components": ["U1"]}
    ci = {
        "U1": {"type": "U", "value": "", "pins": {"IN+": "VREF_IN", "IN-": "VOUT", "OUT": "VOUT"}},
        "R1": {"type": "R", "value": "100k", "pins": {"1": "VCC", "2": "VREF_IN"}},
        "R2": {"type": "R", "value": "100k", "pins": {"1": "VREF_IN", "2": "GND"}},
    }
    fig = Figure(figsize=(7, 5))
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.set_aspect("equal")
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._z_hitboxes = []
        cv._draw_follower(d, result, ci, (4.5, 0), "IN", "OUT")
        hb = list(d._z_hitboxes)

    assert len(hb) == 2, f"attendu 2 boites Z (pont diviseur), obtenu {len(hb)}"
    textes = [t.get_text() for t in ax.texts]
    assert any("VCC" in t for t in textes), f"pas de rail VCC dessine: {textes}"


def test_suiveur_sans_pont_ne_dessine_aucune_boite_z():
    # En chaine (result vide / IN+ pilote par l'etage precedent) : aucun pont.
    fig = Figure(figsize=(7, 4))
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.set_aspect("equal")
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._z_hitboxes = []
        cv._draw_follower(d, {}, {}, (4.5, 0), "IN", "OUT")
        hb = list(d._z_hitboxes)
    assert hb == []


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
    d = schemdraw.Drawing(show=False)
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


def _ci(*e):
    return {r: {"type": t, "value": v, "pins": p} for r, t, v, p in e}


def test_io_montage_emetteur_commun_in_base_out_collecteur():
    ci = _ci(("Q1", "Q", "", {"B": "NB", "C": "NC", "E": "GND"}))
    match = {"circuit_type": "Amplificateur émetteur commun",
             "components": ["Q1", "Rc", "Rb"], "nodes": ["NB", "NC", "GND"]}
    ins, out = cv._io_montage(match, ci)
    assert ins == ["NB"]
    assert out == "NC"


def test_io_montage_suiveur_out_emetteur():
    ci = _ci(("Q1", "Q", "", {"B": "NB", "C": "VCC", "E": "NOUT"}))
    match = {"circuit_type": "Collecteur commun (suiveur d'émetteur)",
             "components": ["Q1", "Re"], "nodes": ["NB", "VCC", "NOUT"]}
    ins, out = cv._io_montage(match, ci)
    assert ins == ["NB"]
    assert out == "NOUT"


def test_io_montage_darlington_in_q1base_out_q2emetteur():
    ci = _ci(("Q1", "Q", "", {"B": "NB", "C": "VCC", "E": "NE1"}),
             ("Q2", "Q", "", {"B": "NE1", "C": "VCC", "E": "NOUT"}))
    match = {"circuit_type": "Paire Darlington",
             "components": ["Q1", "Q2", "Re"], "nodes": ["NB", "VCC", "NOUT"]}
    ins, out = cv._io_montage(match, ci)
    assert ins == ["NB"]
    assert out == "NOUT"


def test_io_montage_terminal_relais_out_none():
    ci = _ci(("Q1", "Q", "", {"B": "NB", "C": "NCOIL", "E": "GND"}))
    match = {"circuit_type": "Commande de relais",
             "components": ["Q1", "K1"], "nodes": ["NB", "NCOIL", "GND"]}
    _ins, out = cv._io_montage(match, ci)
    assert out is None


def test_io_montage_aop_inchange():
    # AOP : doit retourner exactement (_in_nets, nodes[-1]).
    match = {"circuit_type": "Amplificateur inverseur (AOP)",
             "nodes": ["VIN", "INM", "VOUT"],
             "impedances": {"Zin": {"nodes": ["INM", "VIN"], "composition": "R1"}}}
    ins, out = cv._io_montage(match, {})
    assert ins == cv._in_nets(match)
    assert out == "VOUT"


def test_io_montage_transistor_sans_Q_ne_plante_pas():
    # Match classé chaînable mais ci sans transistor : ne doit pas lever IndexError.
    match = {"circuit_type": "Amplificateur émetteur commun",
             "components": ["Rx"], "nodes": ["NB", "NC", "GND"]}
    ins, out = cv._io_montage(match, {"Rx": {"type": "R", "pins": {}}})
    assert out is None


def test_est_couplage_impedance_z_2_noeuds():
    assert cv._est_couplage({"circuit_type": "Impédance Z", "nodes": ["NC1", "NB2"]})
    assert not cv._est_couplage({"circuit_type": "Amplificateur émetteur commun",
                                  "nodes": ["NB", "NC", "GND"]})


def test_couplage_find_fusionne_les_nets_relies():
    matches = [
        {"circuit_type": "Impédance Z", "nodes": ["NC1", "NB2"]},
        {"circuit_type": "Amplificateur émetteur commun", "nodes": ["NB1", "NC1", "GND"]},
    ]
    find = cv._couplage_find(matches)
    assert find("NC1") == find("NB2")       # reliés par le couplage
    assert find("NB1") != find("NC1")       # non reliés


def _cascade_2ce():
    from circuit_analyzer.composant import Composant
    comps = [
        Composant("Q1", "Q", {"B": "NB1", "C": "NC1", "E": "GND"}),
        Composant("Rb1", "R", {"1": "VCC", "2": "NB1"}, "100k"),
        Composant("Rc1", "R", {"1": "VCC", "2": "NC1"}, "4.7k"),
        Composant("Cc", "C", {"1": "NC1", "2": "NB2"}, "1u"),
        Composant("Q2", "Q", {"B": "NB2", "C": "NC2", "E": "GND"}),
        Composant("Rb2", "R", {"1": "VCC", "2": "NB2"}, "100k"),
        Composant("Rc2", "R", {"1": "VCC", "2": "NC2"}, "1k"),
    ]
    g = construire_graphe(comps)
    res = analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    return cv._matches_for_island(ilot, res), ci


def test_ordonner_cascade_2ce_a_travers_couplage():
    matches, ci = _cascade_2ce()
    ordre = cv._ordonner_montages_flux(matches, ci)
    assert ordre is not None
    types = [m["circuit_type"] for m in ordre]
    assert types == ["Amplificateur émetteur commun",
                     "Amplificateur émetteur commun"]
    # Le couplage (Impédance Z) n'est PAS un étage de la chaîne.
    assert all(m["circuit_type"] != "Impédance Z" for m in ordre)


def test_chaine_2ce_dessine_des_transistors_pas_des_aop():
    matches, ci = _cascade_2ce()
    ordre = cv._ordonner_montages_flux(matches, ci)
    fig = cv._make_chain_fig(ordre, ci)
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert not any("non disponible" in t for t in txts)
    assert sum("Émetteur commun" in t for t in txts) >= 2
    assert not any("Suiveur" in t for t in txts)


def test_chaine_2ce_affiche_le_couplage_cc():
    matches, ci = _cascade_2ce()
    ordre = cv._ordonner_montages_flux(matches, ci)
    fig = cv._make_chain_fig(ordre, ci, matches=matches)
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("Cc" in t for t in txts)


def test_couplage_cap_simple_est_cliquable():
    # Un condensateur de liaison unique doit etre cliquable (hitbox enregistree),
    # comme les boites Z composites — pas un symbole muet.
    matches, ci = _cascade_2ce()
    ordre = cv._ordonner_montages_flux(matches, ci)
    fig = cv._make_chain_fig(ordre, ci, matches=matches)
    assert len(fig._z_hitboxes) >= 1
    refs = {r for hb in fig._z_hitboxes for r in hb[4]}
    assert "Cc" in refs


def test_z_locale_ne_double_pas_le_label_de_port():
    # Une Z locale vers un net non-rail ne doit PAS re-etiqueter ce net : le port
    # (VIN/VOUT) est deja nomme par le drawer -> evite les doublons. Reste cliquable.
    import schemdraw
    fig = cv.Figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._z_hitboxes = []
        cv._dessiner_z_locale(
            d, (0, 0), "VIN",
            {"refs": ["C1"], "composition": "C1", "nodes": ("NB", "VIN")},
            {"C1": {"type": "C", "value": "1u"}})
        hits = len(d._z_hitboxes)
    texts = [t.get_text() for t in ax.texts]
    assert "VIN" not in texts          # pas de re-etiquetage du port
    assert hits >= 1                   # mais la Z locale reste cliquable


def test_chaine_couplage_complexe_affiche_boite_z():
    from circuit_analyzer.composant import Composant
    comps = [
        Composant("Q1", "Q", {"B": "NB1", "C": "NC1", "E": "GND"}),
        Composant("Rb1", "R", {"1": "VCC", "2": "NB1"}, "100k"),
        Composant("Rc1", "R", {"1": "VCC", "2": "NC1"}, "4.7k"),
        Composant("C12", "C", {"1": "NC1", "2": "N12"}, "470n"),
        Composant("R12", "R", {"1": "N12", "2": "NB2"}, "100"),
        Composant("L12", "L", {"1": "N12", "2": "NB2"}, "2.2u"),
        Composant("Q2", "Q", {"B": "NB2", "C": "NC2", "E": "GND"}),
        Composant("Rb2", "R", {"1": "VCC", "2": "NB2"}, "100k"),
        Composant("Rc2", "R", {"1": "VCC", "2": "NC2"}, "1k"),
    ]
    g = construire_graphe(comps)
    res = analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    matches = cv._matches_for_island(ilot, res)
    ordre = cv._ordonner_montages_flux(matches, ci)
    fig = cv._make_chain_fig(ordre, ci, matches=matches)
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("C12+(R12//L12)" in t for t in txts)
    assert any(set(hb[4]) == {"C12", "R12", "L12"}
               for hb in getattr(fig, "_z_hitboxes", []))


def test_chaine_affiche_impedance_emetteur_locale():
    from circuit_analyzer.composant import Composant
    comps = [
        Composant("Q1", "Q", {"B": "NB1", "C": "NC1", "E": "NE1"}),
        Composant("Rb1", "R", {"1": "VCC", "2": "NB1"}, "100k"),
        Composant("Rc1", "R", {"1": "VCC", "2": "NC1"}, "4.7k"),
        Composant("Re1", "R", {"1": "NE1", "2": "GND"}, "1k"),
        Composant("Ce1", "C", {"1": "NE1", "2": "GND"}, "47u"),
        Composant("C12", "C", {"1": "NC1", "2": "NB2"}, "470n"),
        Composant("Q2", "Q", {"B": "NB2", "C": "NC2", "E": "GND"}),
        Composant("Rb2", "R", {"1": "VCC", "2": "NB2"}, "100k"),
        Composant("Rc2", "R", {"1": "VCC", "2": "NC2"}, "1k"),
    ]
    g = construire_graphe(comps)
    res = analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    matches = cv._matches_for_island(ilot, res)
    ordre = cv._ordonner_montages_flux(matches, ci)
    fig = cv._make_chain_fig(ordre, ci, matches=matches)
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("(Re1//Ce1)" in t or "(Ce1//Re1)" in t for t in txts)
    assert any(set(hb[4]) == {"Re1", "Ce1"}
               for hb in getattr(fig, "_z_hitboxes", []))


def test_chaine_2ce_libelles_externes_seulement():
    matches, ci = _cascade_2ce()
    ordre = cv._ordonner_montages_flux(matches, ci)
    fig = cv._make_chain_fig(ordre, ci, matches=matches)
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert "VIN" in txts
    assert "VOUT" in txts
    assert "IN" not in txts
    assert "OUT" not in txts


def test_branched_inclut_les_etages_transistor():
    from circuit_analyzer.composant import Composant
    comps = [
        Composant("Q1", "Q", {"B": "NIN", "C": "NA", "E": "GND"}),
        Composant("Rb1", "R", {"1": "VCC", "2": "NIN"}, "100k"),
        Composant("Rc1", "R", {"1": "VCC", "2": "NA"}, "1k"),
        Composant("Q2", "Q", {"B": "NIN", "C": "NB", "E": "GND"}),
        Composant("Rc2", "R", {"1": "VCC", "2": "NB"}, "1k"),
    ]
    g = construire_graphe(comps)
    res = analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    matches = cv._matches_for_island(ilot, res)
    layers = cv._layers_montages_flux(matches, ci)
    if layers is not None:
        plat = [m["circuit_type"] for L in layers for m in L]
        assert any("émetteur commun" in t.lower() for t in plat)


def test_branched_edges_traversent_les_couplages_ac():
    from circuit_analyzer.composant import Composant
    comps = [
        Composant("Q0", "Q", {"B": "NB0", "C": "NC0", "E": "GND"}),
        Composant("Rb0", "R", {"1": "VCC", "2": "NB0"}, "100k"),
        Composant("Rc0", "R", {"1": "VCC", "2": "NC0"}, "4.7k"),
        Composant("C01", "C", {"1": "NC0", "2": "NB1"}, "470n"),
        Composant("Q1", "Q", {"B": "NB1", "C": "NC1", "E": "GND"}),
        Composant("Rb1", "R", {"1": "VCC", "2": "NB1"}, "100k"),
        Composant("Rc1", "R", {"1": "VCC", "2": "NC1"}, "2.2k"),
        Composant("C02", "C", {"1": "NC0", "2": "NB2"}, "470n"),
        Composant("Q2", "Q", {"B": "NB2", "C": "NC2", "E": "GND"}),
        Composant("Rb2", "R", {"1": "VCC", "2": "NB2"}, "100k"),
        Composant("Rc2", "R", {"1": "VCC", "2": "NC2"}, "1k"),
    ]
    g = construire_graphe(comps)
    res = analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    matches = cv._matches_for_island(ilot, res)
    layers = cv._layers_montages_flux(matches, ci)
    edges = cv._branched_edges(layers, ci, matches=matches)
    assert len(edges) == 2


def test_branched_couplage_complexe_affiche_boite_z():
    from circuit_analyzer.composant import Composant
    comps = [
        Composant("Q0", "Q", {"B": "NB0", "C": "NC0", "E": "GND"}),
        Composant("Rb0", "R", {"1": "VCC", "2": "NB0"}, "100k"),
        Composant("Rc0", "R", {"1": "VCC", "2": "NC0"}, "4.7k"),
        Composant("C01", "C", {"1": "NC0", "2": "N01"}, "470n"),
        Composant("R01", "R", {"1": "N01", "2": "NB1"}, "100"),
        Composant("L01", "L", {"1": "N01", "2": "NB1"}, "2.2u"),
        Composant("Q1", "Q", {"B": "NB1", "C": "NC1", "E": "GND"}),
        Composant("Rb1", "R", {"1": "VCC", "2": "NB1"}, "100k"),
        Composant("Rc1", "R", {"1": "VCC", "2": "NC1"}, "2.2k"),
        Composant("C02", "C", {"1": "NC0", "2": "NB2"}, "47n"),
        Composant("Q2", "Q", {"B": "NB2", "C": "NC2", "E": "GND"}),
        Composant("Rb2", "R", {"1": "VCC", "2": "NB2"}, "100k"),
        Composant("Rc2", "R", {"1": "VCC", "2": "NC2"}, "1k"),
    ]
    g = construire_graphe(comps)
    res = analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    matches = cv._matches_for_island(ilot, res)
    layers = cv._layers_montages_flux(matches, ci)
    fig = cv._make_branched_fig(layers, ci, matches=matches)
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("C01+(R01//L01)" in t for t in txts)
    assert any(set(hb[4]) == {"C01", "R01", "L01"}
               for hb in getattr(fig, "_z_hitboxes", []))
