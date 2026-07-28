"""@file test_puce_drawing.py
@brief Boîte puce (elm.Ic) : ancres par fonction, nets, contrat puces bandeau,
jamais de grille générique pour un îlot à puce identifiée."""
import matplotlib
matplotlib.use("Agg")
import pytest
import schemdraw

from circuit_analyzer import catalogue
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser
from circuit_analyzer.xml import lire_xml
import gui.circuit_viewer as cv
from gui import puce_schematic

CI_555 = {"U1": {"type": "U", "value": "NE555",
                 "pins": {"1": "GND", "2": "NTRIG", "3": "NOUT", "4": "VCC",
                          "5": "NCTRL", "6": "NTRIG", "7": "NDIS", "8": "VCC"}}}


def _dessiner(detaille=False):
    entree = catalogue.identifier("U", "NE555")
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = detaille
        res = puce_schematic.dessiner_puce(d, "U1", entree, CI_555)
    return d, res


def test_contrat_ancres_et_nets():
    d, res = _dessiner()
    for cle in ("in", "out", "title", "nets", "absorbed_refs"):
        assert cle in res
    # chaque net câblé de la puce a un point d'ancrage réel
    for net in ("NTRIG", "NOUT", "NDIS", "NCTRL", "GND", "VCC"):
        assert net in res["nets"], net
    assert "U1" in d._comp_positions          # puce bandeau cliquable


def test_puce_ilot_reconnait_le_555():
    comps = lire_xml("circuits_industriels/reel_555_astable.xml")
    g = construire_graphe(comps)
    res = analyser(g)
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    trouve = cv._puce_ilot(ilot, g)
    assert trouve is not None
    ref, entree = trouve
    assert ref == "U1" and entree["categorie"] == "Timer"


def test_puce_ilot_ignore_les_aop_et_inconnus():
    comps = lire_xml("circuits_industriels/reel_741_inverseur.xml")
    g = construire_graphe(comps)
    res = analyser(g)
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    assert cv._puce_ilot(ilot, g) is None     # aliasé AOP -> chemins AOP


def test_puce_ilot_gate_par_forme_donne_boite_ic_neutre():
    from circuit_analyzer.composant import Composant, construire_graphe
    comp = Composant(ref="U1", type="U", pins={"1": "A", "2": "B", "3": "Y"},
                     value="4000", par_forme=True)
    g = construire_graphe([comp])
    trouve = cv._puce_ilot({"composants": ["U1"]}, g)
    assert trouve is not None                       # plus jamais None → opamp
    ref, entree = trouve
    assert ref == "U1"
    assert entree["categorie"] != "AOP"             # boîte neutre, pas un AOP
    # l'entrée neutre est bien dessinable par le drawer boîte IC existant
    import schemdraw, schemdraw.elements as elm
    from gui import puce_schematic
    ci = {"U1": {"type": "U", "value": "4000", "pins": comp.pins}}
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}; d._z_hitboxes = []; d._mode_detaille = False
        res = puce_schematic.dessiner_puce(d, ref, entree, ci)
    assert set(res["nets"]) == {"A", "B", "Y"}      # 3 broches câblées, boîte IC
    assert "U1" in d._comp_positions                # cliquable


def test_puce_ilot_u_inconnu_sans_forme_reste_none():
    # Contraste : sans le marqueur, comportement inchangé (retombe en vue générique).
    from circuit_analyzer.composant import Composant, construire_graphe
    comp = Composant(ref="U1", type="U", pins={"1": "A", "2": "B", "3": "Y"},
                     value="4000", par_forme=False)
    g = construire_graphe([comp])
    assert cv._puce_ilot({"composants": ["U1"]}, g) is None


def test_make_puce_fig_deux_vues_et_z_cliquables():
    comps = lire_xml("circuits_industriels/reel_555_astable.xml")
    g = construire_graphe(comps)
    res = analyser(g)
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
          for c in comps}
    ref, entree = cv._puce_ilot(ilot, g)
    matches = cv._matches_for_island(ilot, res)
    figs = {}
    for detaille in (False, True):
        fig = cv._make_puce_fig(ref, entree, ci, matches, detaille=detaille)
        assert "U1" in fig._comp_positions, f"puce non cliquable ({detaille=})"
        txts = [t.get_text() for ax in fig.axes for t in ax.texts]
        assert any("TRIG" in t for t in txts), "broches étiquetées par fonction"
        assert any("NE555" in t or "Timer" in t for t in txts), "titre puce"
        figs[detaille] = fig
    # Vue simplifiee : le reseau de temporisation R/C du 555 est cable en
    # couplages locaux (_dessiner_z_locales) -> boites Z cliquables
    # (drill-down). Hitbox = (x0, x1, y0, y1, refs, composition), cf.
    # `_enregistrer_hitbox`/`_z_box` -- refs (5e element) porte les refs
    # composant reelles du bloc.
    hb_simple = figs[False]._z_hitboxes
    assert len(hb_simple) >= 1, "aucune boite Z cliquable en vue simplifiee"
    for hb in hb_simple:
        assert len(hb) == 6
        refs = hb[4]
        assert refs, "hitbox sans ref de composant (5e element vide)"
    # Vue detaillee : `_enregistrer_hitbox` est un no-op explicite quand
    # `d._mode_detaille` (cf. gui/circuit_viewer.py) -- les reseaux R/C sont
    # deja depliés en symboles reels, donc rien a "drill-down" en plus.
    assert figs[True]._z_hitboxes == []


# ── Filtre broches câblées (revue contrôleur) ────────────────────────────
# Convention de lecture : toute broche NON câblée ressort avec son propre net
# singleton "NET<n>" (jamais partagé, jamais NC) -- fidèle aux fichiers
# réels. `_broche_cablee`/`_nets_partages` distinguent ce fantôme d'une
# broche réellement câblée (net partagé, ou net nommé hors convention NET#).

def test_broche_cablee_filtre_les_singletons_net_hash():
    from gui.puce_schematic import _broche_cablee, _nets_partages
    ci = {"U1": {"pins": {"1": "NET1", "2": "NET1", "3": "NET2", "4": "GND"}},
          "R1": {"pins": {"1": ""}}}
    partages = _nets_partages(ci)
    assert _broche_cablee("NET1", partages) is True     # NET# mais partagé -> câblée
    assert _broche_cablee("NET2", partages) is False    # NET# singleton -> fantôme
    assert _broche_cablee("GND", partages) is True       # rail nommé, même seul -> câblée
    assert _broche_cablee("", partages) is False
    assert _broche_cablee("NC", partages) is False


def test_74hc00_ne_dessine_que_les_broches_cablees():
    # 74HC00 : une seule porte câblée (1A/1B/1Y) + alimentations, les 9
    # autres broches logiques sont "en l'air" (nets NET# singleton du
    # fichier réel) -- elles ne doivent jamais apparaître comme ancres.
    ci = {
        "U1": {"type": "U", "value": "74HC00", "pins": {
            "1": "SIGA", "2": "SIGB", "3": "SIGY",
            "4": "NET1", "5": "NET2", "6": "NET3", "8": "NET4", "9": "NET5",
            "10": "NET6", "11": "NET7", "12": "NET8", "13": "NET9",
            "7": "GND", "14": "VCC"}},
        "R1": {"type": "R", "value": "1k", "pins": {"1": "SIGA", "2": "SIGB"}},
    }
    entree = catalogue.identifier("U", "74HC00")
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = False
        res = puce_schematic.dessiner_puce(d, "U1", entree, ci)
    assert set(res["nets"]) == {"SIGA", "SIGB", "SIGY", "GND", "VCC"}


# ── Regulateurs alias -> boite puce (revue Task 5, CRITIQUE) ─────────────

@pytest.mark.parametrize("fichier,attendu", [
    ("reel_7805_alim.xml", "7805"), ("reel_lm317_variable.xml", "LM317")])
def test_regulateurs_ont_la_boite_puce_jamais_generique(fichier, attendu):
    # CRITICAL revue Task 5 : alias=True excluait les regulateurs de la boite
    # puce ALORS QU'aucun detecteur ne matche IN/GND/OUT -> grille generique
    # (regle dure violee). Seule la categorie AOP est exclue.
    comps = lire_xml(f"circuits_industriels/{fichier}")
    g = construire_graphe(comps)
    res = analyser(g)
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    trouve = cv._puce_ilot(ilot, g)
    assert trouve is not None, "regulateur identifie -> boite puce obligatoire"
    ref, entree = trouve
    assert attendu in entree["nom"]
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    fig = cv._make_puce_fig(ref, entree, ci, cv._matches_for_island(ilot, res))
    assert ref in fig._comp_positions


# ── LED coloree (Task 6) ──────────────────────────────────────────────────

def test_led_dessinee_en_led_coloree():
    comps = lire_xml("circuits_industriels/reel_led_r.xml")
    g = construire_graphe(comps)
    res = analyser(g)
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    from tools.render_ilots_v2 import _fig_for_ilot   # via sys.path tools/
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
          for c in comps}
    fig = _fig_for_ilot(ilot, g, ci, res, detaille=True)
    # au moins un élément LED (schemdraw pose des flèches de rayonnement :
    # on vérifie par la couleur rouge d'un patch/ligne de l'axe)
    import matplotlib.colors as mcolors
    rouge = mcolors.to_rgba("red")
    ax = fig.axes[0]
    couleurs = ([l.get_color() for l in ax.lines]
                + [p.get_edgecolor() for p in ax.patches])
    assert any(mcolors.to_rgba(c) == rouge for c in couleurs), \
        "aucun trait rouge : la LED n'est pas dessinée en LED colorée"


def _dots_et_lignes(fichier):
    import schemdraw
    comps = lire_xml(f"circuits_industriels/{fichier}")
    g = construire_graphe(comps)
    res = analyser(g)
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ref, entree = cv._puce_ilot(ilot, g)
    from gui import puce_schematic
    import schemdraw.elements as elm
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = False
        r = puce_schematic.dessiner_puce(d, ref, entree, ci)
        matches = cv._matches_for_island(ilot, res)
        puce_schematic.dessiner_z_locales(d, r, matches, ci)
        dots = [tuple(e.absanchors["center"]) for e in d.elements
                if isinstance(e, elm.Dot) and not e._userparams.get("open")]
        lignes = [(tuple(e.start), tuple(e.end)) for e in d.elements
                  if isinstance(e, elm.Line)]
    return dots, lignes


def _dot_strictement_dans(dot, seg):
    (x1, y1), (x2, y2) = seg
    dx, dy = round(x2 - x1, 3), round(y2 - y1, 3)
    px, py = round(dot[0] - x1, 3), round(dot[1] - y1, 3)
    if dx == 0 and dy == 0:
        return False
    # colinéaire ?
    if abs(px * dy - py * dx) > 1e-2:
        return False
    t = (px * dx + py * dy) / (dx * dx + dy * dy)
    return 0.05 < t < 0.95      # strictement interne (pas une extrémité)


@pytest.mark.parametrize("fichier", ["reel_lm317_variable.xml",
                                     "reel_555_astable.xml",
                                     "reel_lm393_seuil.xml"])
def test_aucun_fil_ne_traverse_le_dot_d_une_autre_broche(fichier):
    # Audit A1 : le riser d'étalement des Z passait PAR le dot d'une autre
    # broche du même côté (LM317 : lecture court-circuit ADJ-IN, un dot est
    # une JONCTION). Invariant : aucun dot plein n'est strictement interne
    # à un segment de fil.
    dots, lignes = _dots_et_lignes(fichier)
    for dot in dots:
        for seg in lignes:
            assert not _dot_strictement_dans(dot, seg), \
                f"fil {seg} traverse le dot {dot}"


def test_puce_ilot_connecteur_multibroches_donne_boite():
    from circuit_analyzer.composant import Composant, construire_graphe
    comp = Composant(ref="J1", type="J",
                     pins={"1": "A", "2": "B", "3": "C"}, value="Borne", boite_ic=True)
    g = construire_graphe([comp])
    trouve = cv._puce_ilot({"composants": ["J1"]}, g)
    assert trouve is not None
    ref, entree = trouve
    assert entree["categorie"] == "Connecteur" and entree["nom"] == "Borne"


def test_puce_ilot_ic_nommee_donne_boite_ci():
    from circuit_analyzer.composant import Composant, construire_graphe
    comp = Composant(ref="U1", type="U",
                     pins={str(i): f"n{i}" for i in range(1, 9)},
                     value="SI844AB", boite_ic=True)
    g = construire_graphe([comp])
    ref, entree = cv._puce_ilot({"composants": ["U1"]}, g)
    assert entree["categorie"] != "AOP" and entree["nom"] == "SI844AB"


def test_symbole_jumper_2_broches():
    import schemdraw.elements as elm
    # elm.Jumper n'est pas un element 2 bornes (pas de .to()) -> plante au rendu.
    # elm.Switch est l'element 2 bornes honnete pour un cavalier.
    assert cv._SYMBOL_ELM.get(cv._schematic_symbol("J")) is elm.Switch


def test_titre_bloc_connecteur_ic_et_aop():
    from gui.circuit_viewer import _titre_bloc
    assert _titre_bloc({"type": "J", "value": "Borne"}).startswith("Connecteur")
    assert "SI844AB" in _titre_bloc({"type": "U", "value": "SI844AB", "boite_ic": True})
    reg = _titre_bloc({"type": "U", "value": "78L05CP", "boite_ic": False})
    assert reg is not None and "Regulateur" in reg
    # vrai AOP -> None (garde le triangle d'AOP)
    assert _titre_bloc({"type": "U", "value": "741", "boite_ic": False}) is None
    # U inconnu sans marqueur -> None (non-régression, garde le comportement actuel)
    assert _titre_bloc({"type": "U", "value": "", "boite_ic": False}) is None


def test_titre_bloc_ne_repete_pas_la_categorie_deja_dans_le_nom():
    """Le dialecte reel nomme parfois le composant PAR sa categorie : la carte
    « pg carte » porte un J value='connecteur traversant', rendu
    « Connecteur / connecteur traversant ». Repeter le mot n'apporte rien et
    allonge une etiquette qui doit ensuite trouver sa place."""
    from gui.circuit_viewer import _titre_bloc
    assert _titre_bloc({"type": "J", "value": "connecteur traversant"}) \
        == "connecteur traversant"
    # casse differente : meme traitement
    assert _titre_bloc({"type": "J", "value": "CONNECTEUR J5"}) == "CONNECTEUR J5"
    # nom qui n'a rien a voir -> les deux lignes sont conservees
    assert _titre_bloc({"type": "J", "value": "Borne"}) == "Connecteur\nBorne"


def test_draw_block_row_ic_multiactive_rend_une_boite_pas_un_faux_aop():
    # IC catch-all (boite_ic) multi-broches : le rendu generique la typait "opamp"
    # -> faux triangle d'AOP. Doit desormais etre une boite etiquetee.
    row = {"type": "U", "value": "SI844AB", "boite_ic": True, "ref": "U1",
           "symbol": "opamp", "y": 0.0,
           "pins": [("1", "A"), ("2", "B"), ("3", "C")], "stubs": []}
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = False
        cv._draw_block_row(d, row, [], {}, 4.0)
        noms = [type(e).__name__ for e in d.elements]
    assert "Opamp" not in noms and "Rect" in noms


def test_draw_block_row_connecteur_rend_une_boite_pas_un_aop():
    row = {"type": "J", "value": "Borne", "boite_ic": True, "ref": "J1",
           "symbol": "jumper", "y": 0.0,
           "pins": [("1", "A"), ("2", "B"), ("3", "C")], "stubs": []}
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = False
        cv._draw_block_row(d, row, [], {}, 4.0)
        noms = [type(e).__name__ for e in d.elements]
    assert "Opamp" not in noms and "Rect" in noms


def _dessiner_bloc(row, cols_pins=(), x_by_net=None):
    """@brief Joue `_draw_block_row` isolement, renvoie (elements, drawing)."""
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = False
        cv._draw_block_row(d, row, list(cols_pins), dict(x_by_net or {}), 4.0)
        return list(d.elements), d


def test_boite_multibroches_assez_haute_pour_ses_moignons():
    """DEFAUT D1 (audit visuel 2026-07-28) : la boite etait a hauteur FIXE (1.0)
    alors que les moignons s'eventent de 1.0 par broche. Sur SI844AB (13
    broches), 12 moignons flottaient dans le vide, detaches de la boite."""
    stubs = [(str(i), f"NET{i}") for i in range(1, 14)]
    row = {"type": "U", "value": "SI844AB", "boite_ic": True, "ref": "U1",
           "symbol": "opamp", "y": 0.0,
           "pins": stubs, "stubs": stubs}
    elements, _d = _dessiner_bloc(row)
    rect = next(e for e in elements if type(e).__name__ == "Rect")
    haut = rect.get_bbox(transform=True)
    assert haut.ymax - haut.ymin >= len(stubs), (
        f"boite de {haut.ymax - haut.ymin} pour {len(stubs)} broches")
    # ... et CHAQUE moignon part de l'interieur de la boite.
    lignes = [e for e in elements if type(e).__name__ == "Line"]
    ys = {round(e.get_bbox(transform=True).ymin, 3) for e in lignes}
    dehors = [y for y in ys if not (haut.ymin - 1e-6 <= y <= haut.ymax + 1e-6)]
    assert not dehors, f"moignons hors de la boite : {sorted(dehors)}"


def test_bloc_multibroches_nomme_ses_broches():
    """DEFAUT D2 : les transistors sortaient en CARRE VIDE -- aucune broche
    nommee, un seul fil arrivant sur un coin. B/C/E existent pourtant dans les
    donnees des vraies cartes."""
    row = {"type": "Q", "value": "", "boite_ic": False, "ref": "Q1",
           "symbol": "bjt", "y": 0.0,
           "pins": [("B", "NET1"), ("C", "NET2"), ("E", "NET3")],
           "stubs": [("E", "NET3")]}
    elements, _d = _dessiner_bloc(row, cols_pins=[("B", "NET1"), ("C", "NET2")],
                                  x_by_net={"NET1": 0.0, "NET2": 2.0})
    textes = set()
    for e in elements:
        for lab in getattr(e, "_userlabels", []) or []:
            textes.add(getattr(lab, "label", None))
    assert {"B", "C", "E"} <= textes, f"broches non nommees : {textes}"


def test_broches_de_colonne_ne_se_superposent_pas():
    """DEFAUT D2 (suite) : toutes les broches cablees arrivaient a la MEME
    ordonnee -> trois fils exactement superposes, illisibles (Q1 : C et E sur
    le meme net donnaient deux traits identiques)."""
    row = {"type": "Q", "value": "", "boite_ic": False, "ref": "Q1",
           "symbol": "bjt", "y": 0.0,
           "pins": [("B", "NET1"), ("C", "NET2"), ("E", "NET2")], "stubs": []}
    cols = [("B", "NET1"), ("C", "NET2"), ("E", "NET2")]
    elements, _d = _dessiner_bloc(row, cols_pins=cols,
                                  x_by_net={"NET1": 0.0, "NET2": 2.0})
    lignes = [e for e in elements if type(e).__name__ == "Line"]
    ys = [round(e.get_bbox(transform=True).ymin, 3) for e in lignes]
    assert len(set(ys)) == len(cols), f"fils superposes : {ys}"


def test_reserve_verticale_est_le_miroir_de_la_boite_dessinee():
    """La place reservee au plan doit valoir la HAUTEUR REELLE de la boite.

    Majorer a `len(pins)` sur une puce cablee moitie-moitie reservait le double,
    ecartait les blocs a l'exces et alignait tous les hauts de bus a la meme
    ordonnee : 17 chevauchements d'etiquettes sur « pg carte »."""
    pins = [(str(i), f"NET{i}") for i in range(1, 17)]
    row = {"type": "U", "value": "SI844AB", "boite_ic": True, "ref": "U1",
           "symbol": "opamp", "y": 0.0, "pins": pins,
           "cols": pins[:8], "stubs": pins[8:]}
    elements, _d = _dessiner_bloc(row, cols_pins=row["cols"],
                                  x_by_net={n: 0.0 for _p, n in row["cols"]})
    rect = next(e for e in elements if type(e).__name__ == "Rect")
    # Le CADRE seul (get_bbox engloberait aussi le titre pose au-dessus).
    ys = [p[1] for seg in rect.segments
          for p in getattr(seg, "path", ()) or ()]
    assert cv._demi_hauteur_bloc(row) == pytest.approx((max(ys) - min(ys)) / 2.0)


def test_voie_des_devices_degage_les_moignons_de_la_derniere_colonne():
    """La diode D4 de « pg carte » etait dessinee A TRAVERS l'isolateur : un
    dipole « bus a gauche, E/S a droite » atteint col_x + STUB_REACH."""
    columns = [{"x": 0.0}, {"x": cv.COL_PITCH}]
    bord_gauche = cv._voie_devices(columns) - cv._W_BLOC / 2.0
    assert bord_gauche >= columns[-1]["x"] + cv.STUB_REACH


def test_compactage_reserve_la_largeur_de_l_etiquette():
    """Deux impedances tenaient dans la meme bande parce que leurs SYMBOLES ne se
    touchaient pas, pendant que leurs titres se marchaient dessus."""
    court = cv._span_avec_etiquette((0.0, 1.6), "Z9\nC12")
    long_ = cv._span_avec_etiquette((0.0, 1.6), "Z6\nR15+C8+C9")
    assert long_[1] - long_[0] > court[1] - court[0]
    # ... et l'elargissement est CENTRE sur le symbole (le label l'est aussi).
    assert (long_[0] + long_[1]) / 2 == pytest.approx(0.8)


def test_jumper_2_broches_se_dessine_sans_crash():
    import schemdraw
    from gui import circuit_viewer as cv
    row = {"type": "J", "value": "JMP", "boite_ic": False, "ref": "JP1",
           "symbol": "jumper", "y": 0.0, "pins": [("1", "A"), ("2", "B")], "stubs": []}
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}; d._z_hitboxes = []; d._mode_detaille = False
        cv._draw_two_pin_row(d, row, {"A": 0.0, "B": 2.0}, "top", None)  # ne doit PAS lever
