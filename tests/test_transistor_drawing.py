"""@file test_transistor_drawing.py
@brief Dessin SIMPLE des montages transistor : symboles classiques + titre du
montage, sans boîtes Z cliquables (cf. spec 2026-06-26-transistors-schemas-simples)."""
import matplotlib
matplotlib.use("Agg")

import schemdraw

import gui.circuit_viewer as cv


def _ci(*entries):
    return {ref: {"type": t, "value": v, "pins": pins} for ref, t, v, pins in entries}


def _render(result, ci):
    fig = cv._make_fig(result, ci, cv._DRAWERS[result["circuit_type"]])
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    return fig, txts


SUIVEUR = (
    {"circuit_type": "Collecteur commun (suiveur d'émetteur)",
     "components": ["Q1", "Re", "R1"], "nodes": ["NB", "VCC", "NOUT"]},
    _ci(("Q1", "Q", "", {"B": "NB", "C": "VCC", "E": "NOUT"}),
        ("Re", "R", "1k", {"1": "NOUT", "2": "GND"}),
        ("R1", "R", "47k", {"1": "NB", "2": "VCC"})),
)
PUSH_PULL = (
    {"circuit_type": "Étage push-pull", "components": ["Q1", "Q2"], "nodes": ["NIN", "NIN", "NOUT"]},
    _ci(("Q1", "Q", "", {"B": "NIN", "C": "VCC", "E": "NOUT"}),
        ("Q2", "Q", "", {"B": "NIN", "C": "GND", "E": "NOUT"})),
)
DARLINGTON = (
    {"circuit_type": "Paire Darlington", "components": ["Q1", "Q2", "Re"], "nodes": ["NB", "VCC", "NOUT"]},
    _ci(("Q1", "Q", "", {"B": "NB", "C": "VCC", "E": "NE1"}),
        ("Q2", "Q", "", {"B": "NE1", "C": "VCC", "E": "NOUT"}),
        ("Re", "R", "1k", {"1": "NOUT", "2": "GND"})),
)
EMETTEUR_COMMUN = (
    {"circuit_type": "Amplificateur émetteur commun",
     "components": ["Q1", "Rc", "Rb"], "nodes": ["NB", "NCOL", "GND"]},
    _ci(("Q1", "Q", "", {"B": "NB", "C": "NCOL", "E": "GND"}),
        ("Rc", "R", "1k", {"1": "VCC", "2": "NCOL"}),
        ("Rb", "R", "10k", {"1": "VCC", "2": "NB"})),
)
BJT_SWITCH = (
    {"circuit_type": "Transistor en commutation",
     "components": ["Q1", "Rb", "L1"], "nodes": ["NB", "NL", "GND"]},
    _ci(("Q1", "Q", "", {"B": "NB", "C": "NL", "E": "GND"}),
        ("Rb", "R", "10k", {"1": "NIN", "2": "NB"}),
        ("L1", "L", "10mH", {"1": "VCC", "2": "NL"})),
)
MOSFET_SWITCH = (
    {"circuit_type": "MOSFET en commutation",
     "components": ["M1", "Rg", "L1"], "nodes": ["NG", "ND", "GND"]},
    _ci(("M1", "M", "", {"G": "NG", "D": "ND", "S": "GND"}),
        ("Rg", "R", "100", {"1": "NIN", "2": "NG"}),
        ("L1", "L", "10mH", {"1": "VCC", "2": "ND"})),
)


def test_nouveaux_drawers_transistor_enregistres():
    for ct in ("Collecteur commun (suiveur d'émetteur)", "Étage push-pull", "Paire Darlington"):
        assert ct in cv._DRAWERS


def test_montages_rendent_sans_erreur():
    for result, ci in (SUIVEUR, PUSH_PULL, DARLINGTON, EMETTEUR_COMMUN, BJT_SWITCH):
        _fig, txts = _render(result, ci)
        assert not any("non disponible" in t for t in txts), result["circuit_type"]


def test_aucune_boite_z_sur_transistors():
    # Schéma simple : pas de boîtes Z cliquables sur les passifs transistor.
    for result, ci in (EMETTEUR_COMMUN, SUIVEUR, DARLINGTON):
        fig, _txts = _render(result, ci)
        assert fig._z_hitboxes == [], result["circuit_type"]


def test_resistances_affichees_en_etiquette():
    # Les résistances apparaissent en symbole classique avec leur nom.
    _fig, txts = _render(*EMETTEUR_COMMUN)
    joined = " ".join(txts)
    assert "Rb" in joined and "Rc" in joined


def test_bjt_commutation_affiche_charge_inductive():
    _fig, txts = _render(*BJT_SWITCH)
    assert any("L1" in t for t in txts)


def test_bjt_commutation_titre_degage_charge_verticale():
    res = _ancres(cv._draw_bjt_switch, *BJT_SWITCH, origin=(0, 0))
    assert res["title"][1] - res["out"][1] >= 2.25


def test_mosfet_commutation_titre_degage_charge_verticale():
    res = _ancres(cv._draw_mosfet_switch, *MOSFET_SWITCH, origin=(0, 0))
    assert res["title"][1] - res["out"][1] >= 2.25


def test_commutation_vcc_ne_chevauche_pas_charge_inductive():
    for result, ci in (BJT_SWITCH, MOSFET_SWITCH):
        fig, _txts = _render(result, ci)
        _assert_texts_do_not_overlap(fig, "L1", "VCC")


def test_commutation_label_charge_degage_du_fil_vertical():
    # Audit visuel : le label de la charge (L1) etait centre SUR le fil vertical
    # VCC -> collecteur. Il doit vivre entierement a droite du fil (VCC est
    # centre sur le fil via loc="top", donc son centre x = x du fil).
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    for result, ci in (BJT_SWITCH, MOSFET_SWITCH):
        fig, _txts = _render(result, ci)
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        renderer = canvas.get_renderer()
        l1 = [t.get_window_extent(renderer)
              for ax in fig.axes for t in ax.texts if "L1" in t.get_text()]
        vcc = [t.get_window_extent(renderer)
               for ax in fig.axes for t in ax.texts if "VCC" in t.get_text()]
        assert l1 and vcc, result["circuit_type"]
        wire_x = (vcc[0].x0 + vcc[0].x1) / 2
        assert l1[0].x0 >= wire_x, result["circuit_type"]


def test_emetteur_commun_couple_dc_sans_rb_fantome():
    # Etage CE couple en DC (base = collecteur amont) : pas de resistance de base,
    # donc aucun symbole/label Rb fantome ne doit etre dessine.
    result = {"circuit_type": "Amplificateur émetteur commun",
              "components": ["Q2", "Rc2"], "nodes": ["N1", "N2", "GND"]}
    ci = _ci(("Q2", "Q", "", {"B": "N1", "C": "N2", "E": "GND"}),
             ("Rc2", "R", "1k", {"1": "VCC", "2": "N2"}))
    _fig, txts = _render(result, ci)
    assert not any(t.strip() == "Rb" for t in txts)


def test_titre_role_transistor_affiche():
    _fig, txts = _render(*EMETTEUR_COMMUN)
    assert any("Émetteur commun" in t for t in txts)


def _ancres(drawer, result, ci, origin):
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        return drawer(d, result, ci, origin=origin, titre=False)


def test_drawer_ce_renvoie_ancres_in_out():
    res = _ancres(cv._draw_common_emitter, *EMETTEUR_COMMUN, origin=(0, 0))
    assert "in" in res and "out" in res
    assert res["out"][0] > res["in"][0]


def test_drawer_ce_origine_decale_le_dessin():
    a = _ancres(cv._draw_common_emitter, *EMETTEUR_COMMUN, origin=(0, 0))
    b = _ancres(cv._draw_common_emitter, *EMETTEUR_COMMUN, origin=(10, 0))
    assert round(b["in"][0] - a["in"][0], 3) == 10.0


def test_push_pull_in_out_bien_separes():
    # Les noeuds IN (gauche) et OUT (droite) doivent etre nettement separes
    # horizontalement : sinon ils paraissent etre le meme noeud (cf. audit ChatGPT).
    res = _ancres(cv._draw_push_pull, *PUSH_PULL, origin=(0, 0))
    assert "in" in res and "out" in res
    assert res["out"][0] - res["in"][0] >= 5.5


def test_drawer_titre_false_pas_de_titre():
    fig = cv.Figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._z_hitboxes = []
        cv._draw_common_emitter(d, *EMETTEUR_COMMUN, origin=(0, 0), titre=False)
    direct = [t.get_text() for t in ax.texts]
    assert not any("Émetteur commun" in t for t in direct)

    standalone = [t.get_text()
                  for ax in cv._make_fig(EMETTEUR_COMMUN[0], EMETTEUR_COMMUN[1],
                                         cv._draw_common_emitter).axes
                  for t in ax.texts]
    assert any("Émetteur commun" in t for t in standalone)


def test_commande_relais_affiche_rb_satellite():
    result = {"circuit_type": "Commande de relais",
              "components": ["K1", "Q1"], "nodes": ["VCC", "NCOIL"]}
    ci = _ci(("Q1", "Q", "", {"B": "NB", "C": "NCOIL", "E": "GND"}),
             ("K1", "K", "", {"A1": "VCC", "A2": "NCOIL"}),
             ("Rb", "R", "10k", {"1": "NIN", "2": "NB"}))
    _fig, txts = _render(result, ci)
    assert any("Rb" in t for t in txts)


def _render_ilot_xml(nom, detaille=False):
    from circuit_analyzer import detecteur
    from circuit_analyzer.composant import construire_graphe
    from circuit_analyzer.xml import lire_xml

    comps = lire_xml(f"circuits_industriels/{nom}")
    g = construire_graphe(comps)
    res = detecteur.analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    matches = cv._matches_for_island(ilot, res)
    ordre = cv._ordonner_montages_flux(matches, ci)
    if ordre:
        fig = cv._make_chain_fig(ordre, ci, matches=matches, detaille=detaille)
    else:
        principal = cv._circuit_principal_ilot(ilot, g, res)
        fig = cv._make_fig(principal, ci, cv._DRAWERS[principal["circuit_type"]],
                           matches=matches, detaille=detaille)
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    return fig, txts


def _hitbox_refsets(fig):
    return [set(hb[4]) for hb in getattr(fig, "_z_hitboxes", [])]


def _assert_texts_do_not_overlap(fig, needle_a, needle_b):
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    boxes_a = [
        t.get_window_extent(renderer)
        for ax in fig.axes for t in ax.texts
        if needle_a in t.get_text()
    ]
    boxes_b = [
        t.get_window_extent(renderer)
        for ax in fig.axes for t in ax.texts
        if needle_b in t.get_text()
    ]
    assert boxes_a and boxes_b
    assert not any(a.overlaps(b) for a in boxes_a for b in boxes_b)


def _assert_label_hors_boites_z(fig, needle):
    """Le label `needle` (texte) ne doit chevaucher aucune boite Z (hitbox)."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.transforms import Bbox
    ax = fig.axes[0]
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    labels = [t.get_window_extent(renderer)
              for t in ax.texts if needle in t.get_text()]
    assert labels, needle
    for hb in getattr(fig, "_z_hitboxes", []):
        # hitbox = boite reelle + pad 0.5 (zone cliquable) ; on teste la boite
        # DESSINEE (depadée) pour ne juger que le chevauchement visuel.
        (px0, py0), (px1, py1) = ax.transData.transform(
            [(hb[0] + 0.5, hb[2] + 0.5), (hb[1] - 0.5, hb[3] - 0.5)])
        box = Bbox.from_extents(px0, py0, px1, py1)
        assert not any(b.overlaps(box) for b in labels), (needle, hb[5])


def test_reel_suiveur_re_label_hors_boite_z_sortie():
    # Audit visuel : le label "Re = ..." de l'emetteur chevauchait la boite Z de
    # sortie (L1//R8) posee sur le noeud OUT. Il doit s'en degager.
    fig, _txts = _render_ilot_xml("ilot_reel_ce_suiveur_sortie_rlc.xml")
    _assert_label_hors_boites_z(fig, "Re")


def test_common_emitter_emetteur_a_droite_malgre_direction_inverse():
    # Un drawer amont (ex. Darlington) peut laisser la direction courante du
    # dessin pointee vers la gauche. Le BjtNpn du CE doit garder une orientation
    # DETERMINISTE (emetteur a droite de la base) sinon il est mirroir et percute
    # l'etiquette Rb (cf. ilot_chaine_darlington_ce).
    import schemdraw
    from schemdraw import elements as elm
    fig = cv.Figure()
    ax = fig.add_subplot(111)
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._z_hitboxes = []
        d.add(elm.Line().at((0, 0)).left(1))   # direction ambiante -> gauche
        res = cv._draw_common_emitter(d, *EMETTEUR_COMMUN, origin=(5, 0),
                                      titre=False)
    emitter = res["nets"]["GND"]   # ancre emetteur (E -> GND)
    assert emitter[0] > 5, "emetteur du CE mirroir a gauche (percute Rb)"


def test_reel_2ce_coupling_sortie_dessine_en_ligne():
    # Audit visuel : le coupling de sortie (collecteur -> VOUT, ici C4) etait
    # dessine en stub VERTICAL descendant, or le collecteur est aligne au-dessus
    # de l'emetteur -> la boite traversait le transistor. Il doit etre EN LIGNE
    # (horizontal) sur le fil de sortie.
    fig, _txts = _render_ilot_xml("ilot_reel_2ce_bias_rlc.xml")
    c4 = [hb for hb in fig._z_hitboxes if hb[5] == "C4"]
    assert c4, "boite C4 absente"
    x0, x1, y0, y1 = c4[0][:4]
    assert (x1 - x0) > (y1 - y0), "le coupling de sortie doit etre horizontal"


def test_reel_suiveur_vout_label_hors_boite_z():
    # La boite Z de sortie du suiveur (L1//R8, ancree sur VOUT) ne doit pas
    # chevaucher le label VOUT : elle reste en stub vertical (rien ne la bloque
    # en dessous), contrairement au collecteur du CE (element aligne dessous).
    fig, _txts = _render_ilot_xml("ilot_reel_ce_suiveur_sortie_rlc.xml")
    _assert_label_hors_boites_z(fig, "VOUT")


def test_reel_suiveur_detaille_rlc_labels_ne_se_chevauchent_pas():
    fig, _txts = _render_ilot_xml("ilot_reel_ce_suiveur_sortie_rlc.xml", detaille=True)
    _assert_texts_do_not_overlap(fig, "Rb", "C1")
    _assert_texts_do_not_overlap(fig, "Re", "R8")
    _assert_texts_do_not_overlap(fig, "Re", "L1")


def test_darlington_xml_absorbe_resistance_emetteur_simple():
    fig, txts = _render_ilot_xml("tr_paire_darlington.xml")
    assert not any("non disponible" in t for t in txts)
    assert {"R1"} not in _hitbox_refsets(fig)


def test_chaine_darlington_ce_absorbe_resistance_emetteur_simple():
    fig, txts = _render_ilot_xml("ilot_chaine_darlington_ce.xml")
    refs = _hitbox_refsets(fig)
    assert not any("non disponible" in t for t in txts)
    assert {"C1"} in refs
    assert {"R1"} not in refs


def test_darlington_reel_absorbe_resistance_entree_simple():
    fig, txts = _render_ilot_xml("ilot_reel_darlington_relais_rlc.xml")
    refs = _hitbox_refsets(fig)
    assert not any("non disponible" in t for t in txts)
    assert {"R1"} not in refs
    assert {"R2", "C1"} in refs
    assert {"L1", "R3", "C2", "R4"} in refs


def test_darlington_reel_detaille_deplie_reseau_2_branches():
    # Audit visuel : la vue detaillee R/L/C de l'ilot vitrine (Darlington +
    # relais) doit au minimum deplier le reseau a 2 branches (R2//C1) en
    # symboles reels, pas seulement garder une boite Z generique.
    fig, txts = _render_ilot_xml("ilot_reel_darlington_relais_rlc.xml", detaille=True)
    assert any(t.strip() == "R2" for t in txts), "R2 non deplie en detaille"
    assert any(t.strip() == "C1" for t in txts), "C1 non deplie en detaille"


def test_bjt_commutation_xml_affiche_charge_inductive():
    fig, txts = _render_ilot_xml("tr_bjt_commutation.xml")
    assert not any("non disponible" in t for t in txts)
    assert any("L1" in t for t in txts)
    assert {"L1"} not in _hitbox_refsets(fig)


def test_mosfet_commutation_xml_affiche_charge_inductive():
    fig, txts = _render_ilot_xml("tr_mosfet_commutation.xml")
    assert not any("non disponible" in t for t in txts)
    assert any("L1" in t for t in txts)
    assert {"L1"} not in _hitbox_refsets(fig)


def test_commutation_bjt_vcc_ne_chevauche_pas_charge():
    fig, _txts = _render_ilot_xml("tr_bjt_commutation.xml")
    _assert_texts_do_not_overlap(fig, "VCC", "L1")


def test_commutation_mosfet_vcc_ne_chevauche_pas_charge():
    fig, _txts = _render_ilot_xml("tr_mosfet_commutation.xml")
    _assert_texts_do_not_overlap(fig, "VCC", "L1")
