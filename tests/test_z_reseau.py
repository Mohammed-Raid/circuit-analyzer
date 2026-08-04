"""Expansion d'une composition Z en réseau R/L/C entre deux points (vue détaillée)."""
import math

from circuit_analyzer.impedance import arbre_expr
from gui.circuit_viewer import _amorce_centree, _z_locale_extra
from gui.impedance_schematic import agencement_entre


def test_serie_horizontale_reste_sur_l_axe():
    arbre = arbre_expr("(R1)+(R2)")
    symboles, fils = agencement_entre((0.0, 0.0), (6.0, 0.0), arbre)
    assert [s[0] for s in symboles] == ["R1", "R2"]
    for _ref, pa, pb in symboles:          # tout sur l'axe y=0
        assert abs(pa[1]) < 1e-6 and abs(pb[1]) < 1e-6
    assert symboles[0][1][0] < symboles[0][2][0] <= symboles[1][1][0]


def test_parallele_branches_de_part_et_d_autre():
    arbre = arbre_expr("(R1)//(C1)")
    symboles, fils = agencement_entre((0.0, 0.0), (6.0, 0.0), arbre)
    ys = sorted(s[1][1] for s in symboles)
    assert len(symboles) == 2 and ys[0] < ys[1]      # branches empilées
    assert fils, "rails et connecteurs attendus"


def test_segment_vertical_pivote():
    arbre = arbre_expr("(R1)+(R2)")
    symboles, _ = agencement_entre((0.0, 0.0), (0.0, -6.0), arbre)
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
    import schemdraw
    from matplotlib.figure import Figure
    from schemdraw.elements.lines import Label

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


# ── Audit fenêtre F3/F4 : symbole recentré + fils d'amorce ────────────────────

def test_amorce_centree_raccourcit_un_segment_long():
    """Un segment assez long pour laisser de la place recoit deux fils
    d'amorce ; le symbole recentre garde le meme milieu que le segment
    d'origine (les labels perpendiculaires s'appuient dessus)."""
    pa, pb = (0.0, 0.0), (3.0, 0.0)
    sa, sb, amorces = _amorce_centree(pa, pb)
    assert len(amorces) == 2
    assert amorces[0] == (pa, sa)
    assert amorces[1] == (sb, pb)
    assert sa[0] > pa[0] and sb[0] < pb[0]                 # symbole recule des bornes
    milieu_orig = (pa[0] + pb[0]) / 2
    milieu_symb = (sa[0] + sb[0]) / 2
    assert math.isclose(milieu_orig, milieu_symb, abs_tol=1e-9)


def test_amorce_centree_segment_trop_court_reste_inchange():
    """Un segment deja plus court que le minimum absolu ne peut pas degager de
    fil d'amorce sans deborder de ses propres bornes p1/p2 : il reste tel
    quel (comportement de repli, pas de crash ni de symbole hors segment)."""
    pa, pb = (0.0, 0.0), (0.4, 0.0)
    sa, sb, amorces = _amorce_centree(pa, pb, min_len=1.0)
    assert (sa, sb) == (pa, pb)
    assert amorces == []


def test_amorce_centree_verticale_respecte_le_milieu():
    pa, pb = (2.0, 5.0), (2.0, 1.0)
    sa, sb, amorces = _amorce_centree(pa, pb)
    assert amorces
    assert sa[0] == sb[0] == 2.0
    assert min(pa[1], pb[1]) < sb[1] < sa[1] < max(pa[1], pb[1])


# ── Audit fenêtre F4 : moignon Z local élargi pour un couplage composite ─────

def test_z_locale_extra_nulle_hors_vue_detaillee():
    class Faux:
        _mode_detaille = False
    z = {"refs": ["C1", "R1"], "composition": "(C1)+(R1)"}
    assert _z_locale_extra(Faux(), z, 1.2) == 0.0


def test_z_locale_extra_nulle_pour_une_seule_ref():
    class Faux:
        _mode_detaille = True
    z = {"refs": ["C1"], "composition": "C1"}
    assert _z_locale_extra(Faux(), z, 1.2) == 0.0


def test_z_locale_extra_positive_pour_reseau_composite_en_vue_detaillee():
    """C1+R1 en série sur un moignon a longueur fixe (1.2) ecrase chaque
    symbole a une fraction d'unite : schemdraw deborde alors des bornes
    (audit fenetre F4). L'allongement doit etre strictement positif."""
    class Faux:
        _mode_detaille = True
    z = {"refs": ["C1", "R1"], "composition": "(C1)+(R1)"}
    assert _z_locale_extra(Faux(), z, 1.2) > 0.0


# ── Audit fenêtre F2 : labels des réseaux décalés au-dessus/dessous du rail ──

def test_z_reseau_decale_place_les_labels_hors_du_rail():
    """Les 4 branches d'un réseau décalé (> _Z_DETAIL_COMPACT_INLINE_MAX) ne
    doivent jamais poser leur étiquette dans l'entrefer symbole<->rail (trop
    étroit pour un texte lisible) : chaque label tombe au-delà du rail le
    plus proche de sa branche."""
    import schemdraw
    from matplotlib.figure import Figure

    import gui.circuit_viewer as cv

    fig = Figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.axis("off")
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d.config(fontsize=10, inches_per_unit=0.5)
        d._z_hitboxes = []
        d._mode_detaille = True
        bloc = {"refs": ["L1", "R3", "C2", "R4"],
                "composition": "(L1)//(R3)//(C2)//(R4)"}
        ci = {
            "L1": {"type": "L", "value": "10u"},
            "R3": {"type": "R", "value": "1k"},
            "C2": {"type": "C", "value": "10n"},
            "R4": {"type": "R", "value": "2k"},
        }
        dessine = cv._z_reseau(d, (0.0, 0.0), (0.0, 1.2), bloc, ci, label_loc="right")
    assert dessine is True
    textes = {t.get_text(): t.get_position() for t in ax.texts}
    for ref in ("L1", "R3", "C2", "R4"):
        assert ref in textes, f"{ref} absent des labels"
        _lx, ly = textes[ref]
        # Hors de l'intervalle [0, 1.2] du rail (au-dessus ou en-dessous).
        assert ly < 0.0 or ly > 1.2, (
            f"label {ref} en y={ly} tombe dans l'entrefer symbole<->rail"
        )


def test_label_clear_vertical_couvre_amplitude_zigzag():
    """Une branche HORIZONTALE hors-axe (ex. R5 d'un couplage C2+(R5//L1))
    pousse son étiquette verticalement : le dégagement doit couvrir
    l'amplitude du zigzag (~0.25 unité), pas seulement une fraction (audit
    fenêtre F1, ilot_reel_2ce_bias_rlc)."""
    from gui.circuit_viewer import _Z_DETAIL_LABEL_CLEAR_VERT
    assert _Z_DETAIL_LABEL_CLEAR_VERT > 0.3


# ── Régression bug visuel : couplage déplié plus large que le canal alloué ───

def test_fil_canal_avec_couplage_reseau_large_reste_dans_le_segment_alloue():
    """Bug visuel réel (ilot_reel_fanout_filtres_rlc, couplage C2+(R5//L1) de la
    branche du bas vers VOUT1, vue détaillée) : un réseau composite (3 refs)
    a besoin de plus de largeur que l'espace [channel_x, in_pt] alloué par le
    routage du fan-out. Un centrage symétrique naïf sur ce segment déborde
    alors des DEUX côtés à la fois :
      A. le fil d'amorce gauche de C2 traverse le bus vertical du canal et
         dépasse de l'autre côté ;
      B. la borne droite du réseau déplié (rail droit de R5//L1) engloutit le
         point d'entrée de destination, là où le drawer suivant (transistor)
         pose son Dot de prise (Rb) à une position fixe qui suppose une boîte
         Z compacte -- le Dot se retrouve DANS la boucle R5//L1 au lieu d'être
         sur le fil de sortie, après le réseau.
    Reproduit les coordonnées réelles de ce circuit (cf.
    tools/render_ilots_v2.py + circuits_industriels/ilot_reel_fanout_filtres_rlc.xml).
    """
    import schemdraw
    from matplotlib.figure import Figure

    import gui.circuit_viewer as cv

    fig = Figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    ax.axis("off")
    out_pt = (6.751666666666667, -0.0003333333333332966)
    in_pt = (14.9, -5.197)
    channel_x = 12.5
    cc = {"refs": ["C2", "R5", "L1"], "composition": "C2+(R5//L1)"}
    ci = {
        "C2": {"type": "C", "value": "1u"},
        "R5": {"type": "R", "value": "10k"},
        "L1": {"type": "L", "value": "10m"},
    }
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d.config(fontsize=10, inches_per_unit=0.5)
        d._z_hitboxes = []
        d._mode_detaille = True
        cv._fil_canal_avec_couplage(d, out_pt, in_pt, channel_x, cc, ci)

    # Le bus vertical du canal : une ligne à x constant reliant les niveaux y
    # de out_pt et in_pt.
    canal_x = None
    for line in ax.lines:
        xs = [float(x) for x in line.get_xdata()]
        ys = [float(y) for y in line.get_ydata()]
        if (max(xs) - min(xs) < 1e-9
                and min(ys) <= min(out_pt[1], in_pt[1]) + 1e-6
                and max(ys) >= max(out_pt[1], in_pt[1]) - 1e-6):
            canal_x = xs[0]
    assert canal_x is not None, "bus vertical du canal introuvable"

    # Étendue x de tout ce qui est dessiné au niveau du couplage (bande
    # verticale autour de in_pt[1], assez large pour couvrir la boucle R5//L1).
    xs_bande = [
        x for line in ax.lines
        for x, y in zip(line.get_xdata(), line.get_ydata())
        if not (math.isnan(x) or math.isnan(y)) and abs(y - in_pt[1]) <= 1.5
    ]
    x_gauche, x_droit = min(xs_bande), max(xs_bande)

    assert x_gauche >= canal_x - 1e-9, (
        "A: le fil d'amorce gauche du couplage traverse le bus vertical du "
        f"canal (x_gauche={x_gauche}, canal_x={canal_x})"
    )
    assert x_droit <= in_pt[0] + 1e-9, (
        "B: le réseau déplié engloutit le point d'entrée de destination "
        f"(x_droit={x_droit}, in_pt={in_pt[0]}) -- le Dot de prise se "
        "retrouverait à l'intérieur de la boucle"
    )
