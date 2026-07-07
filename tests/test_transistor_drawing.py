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


def _render_ilot_branche_xml(nom, detaille=False):
    """Rendu par le chemin DAG en couches (_layers/_make_branched_fig)."""
    from circuit_analyzer import detecteur
    from circuit_analyzer.composant import construire_graphe
    from circuit_analyzer.xml import lire_xml

    comps = lire_xml(f"circuits_industriels/{nom}")
    g = construire_graphe(comps)
    res = detecteur.analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    matches = cv._matches_for_island(ilot, res)
    layers = cv._layers_montages_flux(matches, ci)
    assert layers, f"{nom} devrait passer par le chemin branche (DAG en couches)"
    fig = cv._make_branched_fig(layers, ci, matches=matches, detaille=detaille)
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


def test_reel_suiveur_stub_vin_et_vout_termines_par_le_nom_du_net():
    # Les stubs locaux (C1+R1 sous VIN ; L1+R8 sous VOUT) se terminaient par un
    # Dot plein anonyme. Ils doivent maintenant afficher le nom du net reel de
    # destination (VIN / VOUT) au bout du moignon -> 2 occurrences de chaque
    # texte (le port principal + la terminaison du stub), dans les DEUX vues.
    for detaille in (False, True):
        fig, txts = _render_ilot_xml("ilot_reel_ce_suiveur_sortie_rlc.xml", detaille=detaille)
        assert sum(1 for t in txts if t.strip() == "VIN") == 2, (detaille, txts)
        assert sum(1 for t in txts if t.strip() == "VOUT") == 2, (detaille, txts)


def test_reel_suiveur_fils_stub_en_bus_chemin_principal_en_wire():
    # Task 3 (hierarchie visuelle) : les fils des stubs satellites locaux
    # (C1+R1 sous VIN, R5//C2 en aval du 1er etage, L1//R8 sous VOUT) doivent
    # passer en _BUS (gris net), en retrait par rapport au chemin principal.
    # Le fil du couplage de chaine entre les deux etages (C3, sur le chemin du
    # signal, dessine par _fil_avec_couplage) doit lui rester en _WIRE plein.
    fig, _txts = _render_ilot_xml("ilot_reel_ce_suiveur_sortie_rlc.xml")
    ax = fig.axes[0]
    bus_lines = [l for l in ax.lines if l.get_color() == cv._BUS]
    wire_lines = [l for l in ax.lines if l.get_color() == cv._WIRE]
    assert bus_lines, "aucun fil de stub local en _BUS"
    assert wire_lines, "le fil de couplage de chaine (chemin du signal) doit rester en _WIRE"
    # Position : un stub descend nettement SOUS l'axe principal (y=0) du
    # montage -> il "quitte" le chemin, contrairement au couplage inter-etages
    # qui reste ACCROCHE a cet axe (meme ligne y que les bornes in/out).
    assert any(min(l.get_ydata()) < -0.5 for l in bus_lines), (
        "un fil de stub doit descendre hors de l'axe principal")
    assert any(max(abs(v) for v in l.get_ydata()) < 0.01 for l in wire_lines), (
        "le fil de couplage de chaine doit rester sur l'axe principal (y~0)")


def test_reel_ampli_audio_stub_vin_et_vout_termines_par_le_nom_du_net():
    for detaille in (False, True):
        fig, txts = _render_ilot_xml("ilot_reel_ampli_audio_3etages.xml", detaille=detaille)
        assert sum(1 for t in txts if t.strip() == "VIN") == 2, (detaille, txts)
        assert sum(1 for t in txts if t.strip() == "VOUT") == 2, (detaille, txts)


def test_reel_suiveur_detaille_rlc_labels_ne_se_chevauchent_pas():
    fig, _txts = _render_ilot_xml("ilot_reel_ce_suiveur_sortie_rlc.xml", detaille=True)
    _assert_texts_do_not_overlap(fig, "Rb", "C1")
    _assert_texts_do_not_overlap(fig, "Re", "R8")
    _assert_texts_do_not_overlap(fig, "Re", "L1")


def _assert_texte_hors_symbole_proche(fig, needle_texte, needle_repere, couleur,
                                       rayon_px=60):
    """@brief `needle_texte` ne doit pas chevaucher le SYMBOLE (traits `couleur`,
    pas juste son étiquette texte) le plus proche du repère `needle_repere`
    (ex. "C1"). `_assert_texts_do_not_overlap` ne compare que des textes entre
    eux : un stub dépilé (C1+R1) peut chevaucher une étiquette voisine (Rb) par
    son SYMBOLE (plaques du condensateur) sans que les DEUX textes ne se
    touchent -> ce helper compare texte vs bbox réelle du symbole dessiné."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.transforms import Bbox

    ax = fig.axes[0]
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    label_boxes = [t.get_window_extent(renderer)
                   for t in ax.texts if needle_texte in t.get_text()]
    repere_boxes = [t.get_window_extent(renderer)
                    for t in ax.texts if t.get_text().strip() == needle_repere]
    assert label_boxes, needle_texte
    assert repere_boxes, needle_repere
    rx = (repere_boxes[0].x0 + repere_boxes[0].x1) / 2
    ry = (repere_boxes[0].y0 + repere_boxes[0].y1) / 2
    candidats = []
    for line in ax.lines:
        if line.get_color() != couleur:
            continue
        bb = line.get_window_extent(renderer)
        cx, cy = (bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2
        if ((cx - rx) ** 2 + (cy - ry) ** 2) ** 0.5 < rayon_px:
            candidats.append(bb)
    assert candidats, (needle_repere, couleur)
    symbole_box = Bbox.union(candidats)
    assert not any(symbole_box.overlaps(lb) for lb in label_boxes), (
        needle_texte, needle_repere)


def test_reel_suiveur_detaille_rb_entree_hors_symbole_c1():
    # Audit visuel (D2) : le stub d'entree deplie (C1 serie + R1) descend sous
    # VIN a la meme abscisse que le condensateur C1 -> l'etiquette "Rb = ..."
    # (placee sous le fil Rb pour degager le titre) traversait les PLAQUES de
    # C1 (chevauchement texte/symbole, invisible a un simple texte-vs-texte).
    fig, _txts = _render_ilot_xml("ilot_reel_ce_suiveur_sortie_rlc.xml", detaille=True)
    _assert_texte_hors_symbole_proche(fig, "Rb", "C1", "#0891b2")


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


def _assert_label_hors_lignes_noires(fig, needle):
    """@brief `needle` ne doit chevaucher aucun trait NOIR par défaut (symbole
    du transistor) : seul le fil/label explicitement coloré (_WIRE, Z…) peut
    passer sous une étiquette, jamais le corps du composant actif lui-même."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    ax = fig.axes[0]
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    boxes = [t.get_window_extent(renderer) for t in ax.texts if needle in t.get_text()]
    assert boxes, needle
    for line in ax.lines:
        if line.get_color() != "black":
            continue
        bb = line.get_window_extent(renderer)
        assert not any(bb.overlaps(b) for b in boxes), needle


def test_chaine_darlington_ce_rb_2e_etage_hors_transistor():
    # Audit visuel (D4) : le label "Rb = 100 kOhm" du 2e etage (emetteur
    # commun apres le Darlington) etait recentre sous le fil Rb -> quand le
    # texte est un peu large, son bord droit chevauchait le fil horizontal ET
    # le point de jonction / le corps du transistor. Doit rester degage.
    fig, _txts = _render_ilot_xml("ilot_chaine_darlington_ce.xml")
    _assert_label_hors_lignes_noires(fig, "Rb = 100")


def test_chaine_darlington_ce_rc_2e_etage_hors_vcc():
    # Audit visuel : dans la chaine Darlington -> CE, le label Rc du 2e etage
    # remontait trop pres de l'etiquette VCC.
    for detaille in (False, True):
        fig, _txts = _render_ilot_xml("ilot_chaine_darlington_ce.xml", detaille=detaille)
        _assert_texts_do_not_overlap(fig, "Rc = 2.2", "VCC")


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


def test_fanout_premier_etage_etiquette_vin():
    # Audit visuel (D5) : le chemin branche (_make_branched_fig) laissait le
    # point d'entree du premier etage SANS label, contrairement aux chaines
    # lineaires qui etiquettent VIN. L'entree doit etre nommee.
    _fig, txts = _render_ilot_branche_xml("ilot_branche_ce_fanout.xml")
    assert any(t.strip().startswith("VIN") for t in txts), \
        "le premier etage du fan-out doit porter un label VIN"


def test_mosfet_commutation_entree_a_gauche():
    # Audit visuel (D3) : le NFet schemdraw 0.22 place sa grille a DROITE par
    # defaut -> Rg/IN se retrouvaient a droite du symbole, flux droite->gauche,
    # incoherent avec tous les autres montages (IN toujours a gauche).
    res = _ancres(cv._draw_mosfet_switch, *MOSFET_SWITCH, origin=(0, 0))
    assert res["in"][0] < res["out"][0], "IN doit rester a gauche du montage"


def test_high_side_mosfet_entree_a_gauche():
    # Meme motif que le commutateur MOSFET (D3) : le NFet est ancre a (3, 0) ;
    # sans .reverse() sa grille (donc Rg/IN) tombe a DROITE du drain/source,
    # en miroir par rapport a tous les autres montages. Verifie sur le vrai
    # drawer que le label "IN" reste a gauche du drain (VCC).
    fig = cv.Figure()
    ax = fig.add_subplot(111)
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._z_hitboxes = []
        result = {"circuit_type": "MOSFET haute-tension (côté haut)",
                  "components": ["M1", "Rg"], "nodes": ["NG", "VCC", "NLOAD"]}
        ci = _ci(("M1", "M", "", {"G": "NG", "D": "VCC", "S": "NLOAD"}),
                 ("Rg", "R", "100", {"1": "NIN", "2": "NG"}))
        cv._draw_high_side_mosfet(d, result, ci)
    in_x = next(t.get_position()[0] for t in ax.texts if t.get_text().strip() == "IN")
    vcc_x = next(t.get_position()[0] for t in ax.texts if t.get_text().strip() == "VCC")
    assert in_x < vcc_x, "IN doit rester a gauche du drain/VCC (pas en miroir)"


def test_commutation_mosfet_vcc_ne_chevauche_pas_charge():
    fig, _txts = _render_ilot_xml("tr_mosfet_commutation.xml")
    _assert_texts_do_not_overlap(fig, "VCC", "L1")


# ── Audit fenêtre F1 : labels Rc/Re à côté de leur zigzag, jamais dessus ─────
#
# Reproduction fidèle : le chevauchement n'apparaît qu'à travers le pipeline
# RÉEL (_make_chain_fig fixe la hauteur de figure à 4.2" quelle que soit la
# largeur de la chaîne -> ratio px/unité différent d'un rendu de montage
# isolé). Un rendu synthétique isolé (_draw_common_emitter seul, figure par
# défaut) ne reproduit PAS le bug (vérifié en le rejouant sur l'ancien code).
# D'où l'usage direct des XML îlots réels via `_render_ilot_xml`.

def _assert_texte_ne_touche_aucune_ligne_noire(fig, needle):
    """@brief Le texte `needle` (ex. "Rc") ne doit chevaucher AUCUN trait noir
    du schéma (symboles/fils des montages transistor, dessinés en noir par
    `_r_simple` — contrairement aux réseaux R/L/C détaillés, colorés)."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    ax = fig.axes[0]
    labels = [t.get_window_extent(renderer) for t in ax.texts
              if t.get_text().startswith(needle)]
    assert labels, needle
    for line in ax.lines:
        if line.get_color() not in ("black", "k", "#000000"):
            continue
        xs = line.get_xdata()
        if len(xs) < 2:
            continue
        bb = line.get_window_extent(renderer)
        assert not any(lb.overlaps(bb) for lb in labels), (
            f"{needle} chevauche une ligne noire (symbole) en {bb}")


def test_darlington_chaine_rc_label_hors_zigzag():
    # Audit fenêtre F1 (ilot_chaine_darlington_ce, "Rc = 2.2 kΩ") : "Rc = ..."
    # était centré sur son ancre (halign par défaut) et sa moitié droite
    # traversait le zigzag de Rc.
    fig, _txts = _render_ilot_xml("ilot_chaine_darlington_ce.xml", detaille=True)
    _assert_texte_ne_touche_aucune_ligne_noire(fig, "Rc")


def test_suiveur_re_label_hors_zigzag():
    # Audit fenêtre F1 (ilot_reel_ce_suiveur_sortie_rlc, "Re = 1.2 kΩ") :
    # "Re = ..." (placé à gauche de Re) était centré sur son ancre et sa
    # moitié droite traversait le zigzag de Re.
    fig, _txts = _render_ilot_xml("ilot_reel_ce_suiveur_sortie_rlc.xml", detaille=True)
    _assert_texte_ne_touche_aucune_ligne_noire(fig, "Re")


def test_darlington_chaine_re_label_hors_zigzag():
    # Audit fenêtre F1 (ilot_chaine_darlington_ce, "Re = 1 kΩ") : "Re = ..."
    # (placé à droite de Re) était centré sur son ancre et sa moitié gauche
    # traversait le zigzag de Re.
    fig, _txts = _render_ilot_xml("ilot_chaine_darlington_ce.xml", detaille=True)
    _assert_texte_ne_touche_aucune_ligne_noire(fig, "Re")
