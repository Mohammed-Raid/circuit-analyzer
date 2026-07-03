"""Expansion d'une composition Z en réseau R/L/C entre deux points (vue détaillée)."""
from circuit_analyzer.impedance import arbre_expr
from gui.circuit_viewer import _agencement_entre


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


def test_make_fig_detaille_sans_hitboxes():
    import gui.circuit_viewer as cv
    match = {"circuit_type": "Impédance Z", "components": ["R1", "R2"],
             "nodes": ["A", "B"], "composition": "(R1)+(R2)"}
    ci = {"R1": {"type": "R", "value": "10k"}, "R2": {"type": "R", "value": "4.7k"}}
    fig_z = cv._make_fig(match, ci, cv._DRAWERS["Impédance Z"])
    fig_d = cv._make_fig(match, ci, cv._DRAWERS["Impédance Z"], detaille=True)
    assert fig_z._z_hitboxes, "vue Z : la boîte reste cliquable"
    assert fig_d._z_hitboxes == [], "vue détaillée : aucune hitbox"


def test_dessiner_bloc_detaille_tout():
    """dessiner_bloc(detaille=True) rend tout le réseau réel : plus de boîte Z,
    donc plus de hitbox — contrairement à la vue Z par défaut."""
    from circuit_analyzer.composant import Composant
    from gui import impedance_schematic as isch

    # Signature réelle : Composant(ref, type, pins, value) — le pseudo-code du
    # brief l'omettait ; pins est un dict {broche: nœud}, non utilisé ici.
    comps = {"R1": Composant("R1", "R", {"1": "A", "2": "M"}, "10k"),
             "R2": Composant("R2", "R", {"1": "M", "2": "B"}, "4.7k")}
    arbre = arbre_expr("(R1)+(R2)")
    fig_z = isch.dessiner_bloc(arbre, "A", "B", comps)
    fig_d = isch.dessiner_bloc(arbre, "A", "B", comps, detaille=True)
    assert fig_z._z_hitboxes and fig_d._z_hitboxes == []


def test_island_zoom_next_est_borne_et_reversible():
    import gui.circuit_viewer as cv

    assert cv._island_zoom_next(1.0, "in") == 1.25
    assert cv._island_zoom_next(1.25, "out") == 1.0
    assert cv._island_zoom_next(2.9, "in") == 3.0        # borne haute
    assert cv._island_zoom_next(0.51, "out") == 0.5      # borne basse
    assert cv._island_zoom_next(2.4, "reset") == 1.0
    assert cv._island_zoom_next(0.6, "reset") == 1.0


def test_dessiner_pont_detaille_deplie_bras_composite():
    """dessiner_pont(detaille=True) déplie chaque bras série/parallèle en
    composants réels ; plus aucune boîte Z, donc plus de hitbox."""
    from circuit_analyzer.composant import Composant
    from gui import impedance_schematic as isch

    comps = {
        "R1": Composant("R1", "R", {"1": "H", "2": "G"}, "1k"),
        "R2": Composant("R2", "R", {"1": "H", "2": "D"}, "2k"),
        "R3": Composant("R3", "R", {"1": "D", "2": "B"}, "3k"),
        "R4": Composant("R4", "R", {"1": "G", "2": "M"}, "1k"),
        "R5": Composant("R5", "R", {"1": "M", "2": "B"}, "1k"),
        "R6": Composant("R6", "R", {"1": "G", "2": "D"}, "5k"),
    }
    pont = {
        "haut": "H", "bas": "B",
        "bras": {
            "haut_gauche": {"refs": ["R1"], "composition": "R1"},
            "haut_droite": {"refs": ["R2"], "composition": "R2"},
            "bas_gauche": {"refs": ["R4", "R5"], "composition": "(R4)+(R5)"},
            "bas_droite": {"refs": ["R3"], "composition": "R3"},
            "pont": {"refs": ["R6"], "composition": "R6"},
        },
    }
    fig_z = isch.dessiner_pont(pont, comps)
    fig_d = isch.dessiner_pont(pont, comps, detaille=True)
    assert fig_z._z_hitboxes, "bras composite bas_gauche cliquable en vue Z"
    assert fig_d._z_hitboxes == [], "vue détaillée : aucune hitbox"


def test_make_fig_labels_dans_le_cadre():
    """Garde-fou anti-régression : toute étiquette (ex. « Z\n(R1)+(R2) ») doit
    tomber dans les xlim/ylim finaux de l'axe, en vue Z comme en vue détaillée.
    Régression du bug où _z_label_anchor plaçait le label hors cadre (matplotlib
    n'autoscale pas sur les Text) et rendait la boîte Z autonome muette."""
    import gui.circuit_viewer as cv
    match = {"circuit_type": "Impédance Z", "components": ["R1", "R2"],
             "nodes": ["A", "B"], "composition": "(R1)+(R2)"}
    ci = {"R1": {"type": "R", "value": "10k"}, "R2": {"type": "R", "value": "4.7k"}}
    for detaille in (False, True):
        fig = cv._make_fig(match, ci, cv._DRAWERS["Impédance Z"], detaille=detaille)
        ax = fig.axes[0]
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        for txt in ax.texts:
            x, y = txt.get_position()
            assert x0 <= x <= x1 and y0 <= y <= y1, (
                f"label {txt.get_text()!r} en ({x}, {y}) hors cadre "
                f"xlim={ax.get_xlim()} ylim={ax.get_ylim()} (detaille={detaille})"
            )


def test_make_island_fig_detaille_deplie_z_generique_sans_hitbox():
    import gui.circuit_viewer as cv

    model = {
        "label": "Ilot generique",
        "components": [{
            "ref": "Z1", "type": "Z", "value": "",
            "pins": {"1": "A", "2": "B"},
            "symbol": "impedance",
            "refs": ["R1", "R2"],
            "composition": "(R1)+(R2)",
            "detail_info": {
                "R1": {"type": "R", "value": "10k"},
                "R2": {"type": "R", "value": "4.7k"},
            },
        }],
    }
    fig_z = cv._make_island_fig(model)
    fig_d = cv._make_island_fig(model, detaille=True)
    assert fig_z._z_hitboxes, "fallback generique Z : la boite reste cliquable"
    assert fig_d._z_hitboxes == [], "fallback detaille : aucune hitbox"
    textes = [t.get_text() for ax in fig_d.axes for t in ax.texts]
    assert "Z1\n(R1)+(R2)" not in textes
    assert any("R1" in t for t in textes)
    assert any("R2" in t for t in textes)


def test_z_reseau_compact_trop_dense_dessine_des_symboles_reels():
    """Un reseau composite trop compresse dans un montage principal reste en
    vue detaillee R/L/C : il est decale, mais avec les vrais symboles, pas une
    simple ligne annotee."""
    from matplotlib.figure import Figure
    from schemdraw.elements.lines import Label
    import schemdraw
    import gui.circuit_viewer as cv

    fig = Figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.axis("off")
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d.config(fontsize=10, inches_per_unit=0.5)
        d._z_hitboxes = []
        d._mode_detaille = True
        bloc = {"refs": ["C1", "L1", "R2", "R3"], "composition": "(C1)//(L1)//(R2)//(R3)"}
        ci = {
            "C1": {"type": "C", "value": "10n"},
            "L1": {"type": "L", "value": "80m"},
            "R2": {"type": "R", "value": "100k"},
            "R3": {"type": "R", "value": "47k"},
        }
        dessine = cv._z_reseau(d, (0.0, 0.0), (1.4, 0.0), bloc, ci)
        elements_non_label = [e for e in d.elements if not isinstance(e, Label)]

    textes = {t.get_text() for t in ax.texts}
    assert dessine is True
    assert {"C1", "L1", "R2", "R3"} <= textes
    assert not any(t.startswith("Z") for t in textes)
    assert len(elements_non_label) >= 4
