"""
@file test_island_viewport.py
@brief Viewport zoom exact (persistance croisee mode/zoom, centrage < 1.0x,
scrollregion > 1.0x) et demontage deterministe (zero fuite) de la fenetre
ilot (`gui.circuit_viewer.show_island`).

Design : docs/superpowers/specs/2026-07-06-ilots-rendu-rigoureux-design.md
sections 2 et 3. Tests d'integration legers sur un vrai root Tk (sautes sans
affichage), meme idiome que tests/test_gui_sync.py::ctk_root.
"""
import gc
import time
import weakref

import pytest

from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser
from circuit_analyzer.xml import lire_xml
import gui.circuit_viewer as cv


@pytest.fixture
def ctk_root():
    ctk = pytest.importorskip("customtkinter")
    import tkinter as tk
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("pas d'affichage Tk disponible")
    root.withdraw()
    yield root
    root.destroy()


def _premier_ilot(fichier):
    """@brief Charge un ilot reel (graphe + comp_info + results) depuis un XML
    de circuits_industriels/, pour ouvrir une vraie fenetre show_island."""
    comps = lire_xml(f"circuits_industriels/{fichier}")
    graph = construire_graphe(comps)
    res = analyser(graph)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    return res.ilots[0], graph, ci, res


def _ouvrir(ctk_root, fichier):
    ilot, graph, ci, res = _premier_ilot(fichier)
    popup = cv.show_island(ilot, graph, ci, parent=ctk_root, results=res)
    ctk_root.update()
    return popup


# ── Section 2 : persistance croisee mode/zoom ─────────────────────────────────

def test_toggle_ne_modifie_pas_le_zoom_et_zoom_ne_modifie_pas_le_mode(ctk_root):
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test
    mode, zoom = t["mode"], t["zoom"]

    # Vue depliee par defaut (Task 6) -> mode["detaille"] demarre a True.
    assert mode["detaille"] is True
    assert zoom["facteur"] == 1.0

    t["zoom_in"]()
    ctk_root.update()
    assert zoom["facteur"] == pytest.approx(1.25)
    assert mode["detaille"] is True, "le zoom ne doit pas toucher le mode"

    t["toggle"]()
    ctk_root.update()
    assert mode["detaille"] is False
    assert zoom["facteur"] == pytest.approx(1.25), "le toggle ne doit pas toucher le zoom"

    t["zoom_out"]()
    ctk_root.update()
    assert zoom["facteur"] == pytest.approx(1.0)
    assert mode["detaille"] is False, "le zoom ne doit pas toucher le mode"

    t["toggle"]()
    ctk_root.update()
    assert mode["detaille"] is True
    assert zoom["facteur"] == pytest.approx(1.0)

    popup.destroy()


# ── Section 2 : centrage explicite < 1.0x (pas d'etirement) ───────────────────

def test_zoom_reduit_centre_le_widget_sans_l_etirer(ctk_root):
    # Choisi pour son chemin non-defilant (pas un montage en chaine/branches,
    # figure de base sous le seuil _ISLAND_DEFILE_WIDTH_IN) : c'est justement
    # le chemin "< 1.0x" vise par la section 2 du design. L'autre ilot du meme
    # fichier (index 1) qualifie aussi ; l'ilot 0 de ce_suiveur_sortie_rlc, lui,
    # est un montage en chaine -> toujours defilant, meme sous 1.0x (verifie).
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test

    t["zoom_out"]()
    ctk_root.update()
    assert t["zoom"]["facteur"] < 1.0

    canvas = t["etat"]["canvas"]
    widget = canvas.get_tk_widget()
    info = widget.pack_info()
    assert info.get("fill") in ("none", None), (
        "a facteur < 1.0, le widget ne doit pas etre etire (fill both) : "
        "l'etirement declenche le resize() de FigureCanvasTkAgg qui annule "
        "le zoom reduit en re-agrandissant la figure au cadre disponible"
    )
    assert info.get("expand") in ("1", True, 1), "doit rester centre (expand=True)"

    # La figure montee reflete bien le facteur applique (pas re-agrandie par
    # un resize() Tk qui l'aurait forcee a remplir le cadre disponible).
    fig = t["etat"]["fig"]
    fw, fh = fig.get_size_inches()
    reqw = widget.winfo_reqwidth()
    assert reqw == pytest.approx(fw * fig.dpi, abs=2), (
        "le widget doit demander la taille NATIVE de la figure reduite, "
        "pas la taille du cadre"
    )

    popup.destroy()


# ── Section 2 : scrollregion exacte > 1.0x ────────────────────────────────────

def test_scrollregion_couvre_exactement_la_figure_zoomee(ctk_root):
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test

    t["zoom_in"]()
    t["zoom_in"]()
    ctk_root.update()
    assert t["zoom"]["facteur"] > 1.0

    canvas = t["etat"]["canvas"]
    view = getattr(canvas, "_scroll_view", None)
    assert view is not None, "chemin defilant attendu au-dessus de 1.0x"

    fig = t["etat"]["fig"]
    attendu_w, attendu_h = cv._figure_pixel_size(fig)
    region = [float(v) for v in view.cget("scrollregion").split()]
    assert region == pytest.approx([0.0, 0.0, float(attendu_w), float(attendu_h)], abs=1.0)

    # Le bord du schema est atteignable pile a la fraction 1.0, rien au-dela.
    view.xview_moveto(1.0)
    view.yview_moveto(1.0)
    ctk_root.update()
    x0, x1 = view.xview()
    y0, y1 = view.yview()
    assert x1 == pytest.approx(1.0, abs=1e-6)
    assert y1 == pytest.approx(1.0, abs=1e-6)

    popup.destroy()


# ── Section 3 : demontage deterministe (zero fuite) ──────────────────────────

def test_aucune_fuite_de_figure_sur_cycles_toggle_zoom(ctk_root):
    """Depuis le cache bimode (Task 6), les figures des DEUX modes restent
    volontairement vivantes pendant toute la vie du popup (evite de
    reconstruire a chaque toggle -- `etat["figs"]`) : il n'y a donc plus
    « une figure remplacee = collectee immediatement » pour chaque action,
    mais deux invariants plus forts : jamais plus de 2 figures distinctes
    vues sur tout le cycle toggle/zoom, et la fermeture du popup (`_fermer`)
    les libere TOUTES LES DEUX (cf. `test_fermeture_popup_demonte_le_dernier_contexte`
    pour la derniere affichee seule)."""
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test

    actions = [
        t["zoom_in"], t["toggle"], t["zoom_in"], t["toggle"],
        t["zoom_out"], t["toggle"], t["zoom_reset"], t["toggle"],
    ]
    assert len(actions) >= 8

    vues_par_id = {}
    for action in actions:
        action()
        ctk_root.update()
        vues_par_id[id(t["etat"]["fig"])] = t["etat"]["fig"]

    assert len(vues_par_id) == 2, (
        "le cache bimode ne doit jamais depasser 2 figures distinctes "
        f"(trouve {len(vues_par_id)})")

    refs = [weakref.ref(f) for f in vues_par_id.values()]
    vues_par_id.clear()
    del action
    gc.collect()
    assert all(r() is not None for r in refs), (
        "les 2 figures du cache doivent rester vivantes tant que le popup vit")

    t["fermer"]()
    ctk_root.update()
    gc.collect()

    assert all(r() is None for r in refs), (
        "les figures du cache doivent etre liberees a la fermeture du popup")


# ── Task 6 : vue depliee par defaut + cache bimode des figures ───────────────

def test_ouverture_en_vue_depliee(ctk_root):
    # show_island doit demarrer en mode detaille (spec Task 6).
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test

    assert t["mode"]["detaille"] is True
    assert "Vue simplifiée Z" in t["toggle_btn"].cget("text")

    popup.destroy()


def test_toggle_aller_retour_ne_reconstruit_pas_deux_fois(ctk_root):
    """Un toggle -> toggle (retour a la vue depliee de depart) ne doit
    reconstruire chaque figure qu'UNE SEULE fois (une par mode) : le retour
    a un mode deja vu reutilise la figure du cache, pas une reconstruction."""
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test

    assert t["etat"]["nb_constructions"] == 1, "construction initiale (vue depliee)"

    t["toggle"]()
    ctk_root.update()
    assert t["etat"]["nb_constructions"] == 2, "construction de la vue Z (premier passage)"

    t["toggle"]()
    ctk_root.update()
    assert t["etat"]["nb_constructions"] == 2, (
        "retour a la vue depliee : figure du cache reutilisee, pas de reconstruction")

    popup.destroy()


def test_zoom_apres_toggle_ne_compose_pas_le_facteur(ctk_root):
    """Piege zoom (Task 6) : `set_size_inches` mute la figure cachee. Si
    `_rendre` relisait la taille COURANTE d'une figure reutilisee du cache
    pour deriver le facteur suivant, deux zooms successifs sur un
    aller-retour de mode se composeraient. La taille native doit rester
    figee (`etat["base"]`) et le facteur s'appliquer dessus, jamais sur une
    taille deja zoomee."""
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test

    fig_native = t["etat"]["fig"]
    # Reference NATIVE via `etat["base"]` (Task 6), pas `get_size_inches()`
    # de la figure affichee : celle-ci peut deja etre TASSEE au facteur 1.0
    # (depassement marginal du viewport, cf. `_rendre`), auquel cas mesurer
    # sa taille courante donnerait une reference plus petite que la vraie
    # taille native memorisee -- faussant le calcul attendu ci-dessous.
    base_w, base_h = t["etat"]["base"][True]

    t["zoom_in"]()
    ctk_root.update()
    facteur = t["zoom"]["facteur"]
    assert facteur != 1.0

    t["toggle"]()          # -> vue Z (construction + zoom au meme facteur)
    ctk_root.update()
    t["toggle"]()           # -> retour vue depliee : figure REUTILISEE du cache
    ctk_root.update()

    fig = t["etat"]["fig"]
    assert fig is fig_native, "figure du cache reutilisee (meme objet)"
    w, h = fig.get_size_inches()
    assert w == pytest.approx(base_w * facteur, rel=0.02), (
        "le zoom compose : taille recalculee a partir de la figure DEJA zoomee")
    assert h == pytest.approx(base_h * facteur, rel=0.02)

    popup.destroy()


# ── Task 1 : bouton « Ajuster à la fenêtre » ──────────────────────────────────

def test_ajuster_reduit_une_chaine_large_pour_tenir_dans_le_viewport(ctk_root):
    """Chaine de 7 AOP (ilot_tous_aop) : sans Ajuster, la figure deborde tres
    largement le viewport (defilement enorme). Apres Ajuster, elle doit tenir
    entierement dans le cadre visible (wpx <= vw et hpx <= vh) avec un
    facteur < 1.0."""
    popup = _ouvrir(ctk_root, "ilot_tous_aop.xml")
    t = popup._etat_test

    t["ajuster"]()
    ctk_root.update()

    assert t["zoom"]["facteur"] < 1.0

    vw = t["canvas_frame"].winfo_width()
    vh = t["canvas_frame"].winfo_height()
    wpx, hpx = cv._figure_pixel_size(t["etat"]["fig"])
    assert wpx <= vw
    assert hpx <= vh

    popup.destroy()


def test_ajuster_reste_dans_les_bornes_larges_sur_ilot_compact(ctk_root):
    """Sur un ilot compact (darlington/relais/RLC), Ajuster ne doit jamais
    depasser la borne large 3.0 (distincte des bornes manuelles 0.5-3.0 des
    boutons -/+), et le resultat tient dans le viewport."""
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test

    t["ajuster"]()
    ctk_root.update()

    assert t["zoom"]["facteur"] <= 3.0

    vw = t["canvas_frame"].winfo_width()
    vh = t["canvas_frame"].winfo_height()
    wpx, hpx = cv._figure_pixel_size(t["etat"]["fig"])
    assert wpx <= vw
    assert hpx <= vh

    popup.destroy()


def test_ajuster_repart_du_facteur_pose_pour_les_boutons_manuels(ctk_root):
    """Les boutons -/+ manuels doivent repartir du facteur pose par Ajuster
    (`_island_zoom_next` le re-clampe vers ses propres bornes 0.5-3.0 si
    Ajuster est alle plus loin — comportement documente, pas un bug)."""
    popup = _ouvrir(ctk_root, "ilot_tous_aop.xml")
    t = popup._etat_test

    t["ajuster"]()
    ctk_root.update()
    facteur_ajuste = t["zoom"]["facteur"]

    t["zoom_in"]()
    ctk_root.update()

    attendu = cv._island_zoom_next(facteur_ajuste, "in")
    assert t["zoom"]["facteur"] == pytest.approx(attendu)
    assert 0.5 <= t["zoom"]["facteur"] <= 3.0

    popup.destroy()


def test_ajuster_preserve_le_mode_detaille(ctk_root):
    """Ajuster ne doit pas toucher au mode vue detaillee/Z (meme contrat que
    le zoom manuel, cf. test_toggle_ne_modifie_pas_le_zoom_et_zoom_ne_modifie_pas_le_mode)."""
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test

    # Depart deplie par defaut (Task 6) : on bascule d'abord vers la vue Z
    # (mode non-defaut) pour verifier qu'Ajuster preserve bien la valeur
    # COURANTE du mode, pas seulement le defaut.
    t["toggle"]()
    ctk_root.update()
    assert t["mode"]["detaille"] is False

    t["ajuster"]()
    ctk_root.update()
    assert t["mode"]["detaille"] is False, "Ajuster ne doit pas toucher le mode"

    popup.destroy()


def test_fermeture_popup_demonte_le_dernier_contexte(ctk_root):
    """`_fermer` (partagee par le bouton Fermer ET le protocole
    WM_DELETE_WINDOW, cf. `popup.protocol("WM_DELETE_WINDOW", _fermer)` dans
    show_island) doit liberer la derniere figure affichee avant de detruire
    le popup — pas seulement les figures intermediaires des toggles/zoom."""
    popup = _ouvrir(ctk_root, "ilot_reel_ce_suiveur_sortie_rlc.xml")
    t = popup._etat_test

    # Verifie le wiring WM_DELETE_WINDOW -> meme fonction que le hook "fermer".
    assert popup.protocol("WM_DELETE_WINDOW"), "protocole de fermeture non enregistre"

    derniere_fig = t["etat"]["fig"]
    ref = weakref.ref(derniere_fig)
    del derniere_fig

    t["fermer"]()  # meme chemin que le bouton Fermer / WM_DELETE_WINDOW
    ctk_root.update()

    gc.collect()
    assert ref() is None, "la derniere figure affichee doit etre liberee a la fermeture"


# ── Task chips-export section A : clic sur une puce composant ────────────────

def test_clic_puce_focus_zoome_centre_et_affiche_puis_efface_l_anneau(ctk_root):
    """Clic = FOCUS (retour utilisateur 2026-07-07) : sous _CHIP_FOCUS_FACTEUR
    le clic monte d'abord le zoom a ce facteur (la figure est re-rendue), puis
    centre le viewport defilant sur le composant et pose l'anneau. Les
    attentes se calculent sur la figure COURANTE (post-focus), pas sur celle
    d'avant le clic."""
    popup = _ouvrir(ctk_root, "ilot_tous_aop.xml")
    t = popup._etat_test
    fig_avant = t["etat"]["fig"]

    ilot, _graph, _ci, _res = _premier_ilot("ilot_tous_aop.xml")
    ref = next(r for r in ilot["composants"]
               if cv._position_composant(fig_avant, r) is not None)

    assert t["zoom"]["facteur"] == 1.0
    t["cliquer_composant"](ref)
    ctk_root.update()

    # Focus : zoom monte au facteur cible, figure re-rendue. Depuis le cache
    # bimode (Task 6), le mode ne change pas ici -> meme objet Figure que
    # `fig_avant`, simplement redimensionne et remonte (nouveau canvas
    # defilant) plutot que reconstruit de zero.
    assert t["zoom"]["facteur"] == pytest.approx(cv._CHIP_FOCUS_FACTEUR)
    fig = t["etat"]["fig"]
    assert fig is fig_avant, "meme mode -> figure du cache reutilisee (redimensionnee)"
    canvas = t["etat"]["canvas"]
    view = getattr(canvas, "_scroll_view", None)
    assert view is not None, "au facteur focus la vue doit etre defilante"

    pos = cv._position_composant(fig, ref)
    assert pos is not None
    ax0 = fig.axes[0]
    dispx, dispy = ax0.transData.transform(pos)
    _fig_w_px, fig_h_px = cv._figure_pixel_size(fig)
    vw = max(1, view.winfo_width())
    vh = max(1, view.winfo_height())
    # Invariant GEOMETRIQUE (pas la fraction demandee, qui serait un test
    # auto-referentiel) : le CENTRE VISIBLE du viewport doit tomber sur le
    # pixel du composant, clampe aux bords de la scrollregion quand le
    # centrage parfait n'est pas atteignable (composant trop pres d'un bord).
    sr = [float(v) for v in str(view.cget("scrollregion")).split()]
    sr_w, sr_h = sr[2] - sr[0], sr[3] - sr[1]
    cible_x, cible_y = dispx, fig_h_px - dispy
    attendu_cx = min(max(cible_x, vw / 2.0), max(vw / 2.0, sr_w - vw / 2.0))
    attendu_cy = min(max(cible_y, vh / 2.0), max(vh / 2.0, sr_h - vh / 2.0))
    centre_x = view.canvasx(vw / 2.0)
    centre_y = view.canvasy(vh / 2.0)
    # Tolerance 2 px : Tk quantifie le defilement au pixel entier.
    assert centre_x == pytest.approx(attendu_cx, abs=2.0)
    assert centre_y == pytest.approx(attendu_cy, abs=2.0)

    anneaux = [p for p in ax0.patches if getattr(p, "_surbrillance_puce", False)]
    assert len(anneaux) == 1, "un anneau de surbrillance doit etre pose au clic"
    assert anneaux[0].center == pytest.approx(pos)

    time.sleep((cv._CHIP_HIGHLIGHT_DELAY_MS / 1000.0) + 0.3)
    ctk_root.update()

    anneaux_apres = [p for p in ax0.patches if getattr(p, "_surbrillance_puce", False)]
    assert not anneaux_apres, "l'anneau doit disparaitre apres le delai"

    popup.destroy()


def test_bandeau_puces_refs_reelles_en_vue_detaillee(ctk_root):
    """Le bandeau suit la vue (retour utilisateur 2026-07-08) : vue Z = refs
    de modele (Z1, Z2...), vue detaillee = une puce par composant REEL
    (R/L/C), coherent avec le schema qui ne montre plus de boites Z."""
    popup = _ouvrir(ctk_root, "ilot_reel_fanout_filtres_rlc.xml")
    t = popup._etat_test
    ilot, _graph, ci, _res = _premier_ilot("ilot_reel_fanout_filtres_rlc.xml")

    # Vue depliee par defaut (Task 6) : le bandeau initial est deja detaille.
    textes_det = [p["texte"] for p in t["etat"]["puces"]]
    assert textes_det, "bandeau construit a l'ouverture"
    assert not any(x.startswith("Z") for x in textes_det), (
        "vue detaillee : plus de puce Z")
    reels = {r for r in ilot["composants"]
             if (ci.get(r, {}) or {}).get("type") in ("R", "L", "C")}
    assert reels & set(textes_det), (
        f"les refs reelles doivent apparaitre : {reels} vs {textes_det}")

    t["toggle"]()
    ctk_root.update()
    textes_z = [p["texte"] for p in t["etat"]["puces"]]
    assert any(x.startswith("Z") for x in textes_z), "vue Z : puces de modele"

    t["toggle"]()
    ctk_root.update()
    assert [p["texte"] for p in t["etat"]["puces"]] == textes_det, (
        "retour vue detaillee : bandeau d'origine")

    popup.destroy()


def test_puce_indisponible_grisee_et_message_au_clic(ctk_root):
    """Plus de clic muet (retour utilisateur 2026-07-08) : une puce dont
    aucun candidat ne resout de position sur la figure courante est marquee
    indisponible, et son clic affiche un message transitoire au lieu de ne
    rien faire. Cas stable : D1, diode de roue libre du darlington, jamais
    dessinee (cf. exclusions de test_puces_resolution)."""
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test

    puces = {p["texte"]: p for p in t["etat"]["puces"]}
    p_d1 = next(v for k, v in puces.items() if k.startswith("D1"))
    assert p_d1["dispo"] is False, "D1 jamais dessinee -> puce indisponible"
    assert any(v["dispo"] for v in puces.values()), (
        "les autres puces restent disponibles")

    lbl = t["etat"]["msg_puce"]
    assert lbl.cget("text") == ""
    t["cliquer_puce_indisponible"](p_d1["texte"])
    ctk_root.update()
    assert "D1" in lbl.cget("text") and "dessin" in lbl.cget("text")
    # zoom inchange : pas de focus sur une puce indisponible
    assert t["zoom"]["facteur"] == 1.0

    popup.destroy()


def test_clic_puce_conserve_un_zoom_manuel_superieur(ctk_root):
    """Un zoom manuel deja au-dela du facteur focus n'est PAS ecrase par le
    clic : la figure courante est conservee, seul le centrage s'applique."""
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test
    while t["zoom"]["facteur"] < cv._CHIP_FOCUS_FACTEUR:
        t["zoom_in"]()
    ctk_root.update()
    facteur_manuel = t["zoom"]["facteur"]
    assert facteur_manuel >= cv._CHIP_FOCUS_FACTEUR
    fig_avant = t["etat"]["fig"]

    ilot, _graph, _ci, _res = _premier_ilot("ilot_reel_darlington_relais_rlc.xml")
    ref = next((r for r in ilot["composants"]
                if cv._position_composant(fig_avant, r) is not None), None)
    assert ref is not None

    t["cliquer_composant"](ref)
    ctk_root.update()

    assert t["zoom"]["facteur"] == pytest.approx(facteur_manuel)
    assert t["etat"]["fig"] is fig_avant, "pas de re-rendu si deja au-dela du focus"

    popup.destroy()


def test_clic_puce_ref_introuvable_est_silencieux(ctk_root):
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test

    t["cliquer_composant"]("REF_INEXISTANTE_XYZ")
    ctk_root.update()

    popup.destroy()


def test_clic_puce_apres_toggle_survit_au_remontage_de_figure(ctk_root):
    """La figure est remontee au toggle vue detaillee : le clic doit lire
    l'etat COURANT (liaison tardive), pas une figure capturee a la creation
    des puces."""
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test

    # Depart deplie par defaut (Task 6) : un aller-retour (toggle x2) exerce
    # bien un remontage de figure (cache bimode -> figure REUTILISEE, pas
    # neuve) tout en revenant en vue detaillee, comme le titre du test l'exige.
    t["toggle"]()
    ctk_root.update()
    t["toggle"]()
    ctk_root.update()
    fig_apres_toggle = t["etat"]["fig"]

    ilot, _graph, _ci, _res = _premier_ilot("ilot_reel_darlington_relais_rlc.xml")
    ref = next((r for r in ilot["composants"]
                if cv._position_composant(fig_apres_toggle, r) is not None), None)
    assert ref is not None, "au moins un composant doit rester localisable en vue detaillee"

    t["cliquer_composant"](ref)
    ctk_root.update()

    # Le clic-focus a re-rendu (facteur 1.0 -> focus) : l'anneau vit sur la
    # figure COURANTE, et le mode detaille survit au focus.
    assert t["mode"]["detaille"] is True
    fig_courante = t["etat"]["fig"]
    anneaux = [p for p in fig_courante.axes[0].patches
               if getattr(p, "_surbrillance_puce", False)]
    assert len(anneaux) == 1

    popup.destroy()


# ── Portes CMOS : mêmes contrats de fenêtre que le reste du corpus ───────────

def test_fenetre_ilot_porte_nand_toggle_et_expression(ctk_root):
    """La fenêtre îlot d'une porte : expression en en-tête (comme le gain),
    toggle simplifié/détaillé sans exception, puces M cliquables."""
    popup = _ouvrir(ctk_root, "logic_cmos_nand2.xml")
    t = popup._etat_test
    # Vue depliee par defaut (Task 6) : deja "détaillé" ici.
    assert t["etat"]["fig"] is not None
    assert t["mode"]["detaille"] is True
    refs = [p["texte"] for p in t["etat"]["puces"]]
    assert any(r.startswith("M") for r in refs)
    assert all(p["dispo"] for p in t["etat"]["puces"]), "détaillé : chaque M dessiné"
    t["toggle"]()
    ctk_root.update()
    assert t["mode"]["detaille"] is False
    assert all(p["dispo"] for p in t["etat"]["puces"]), "simplifié : aucune puce grisée"
    popup.destroy()


def test_fenetre_ilot_latch_sr_ouvre_sans_exception(ctk_root):
    """Rendu de repli des topologies bouclées (spec § 2) : FIGÉ — la fenêtre
    s'ouvre, une figure existe, le toggle ne lève pas."""
    popup = _ouvrir(ctk_root, "logic_latch_sr.xml")
    t = popup._etat_test
    assert t["etat"]["fig"] is not None
    t["toggle"]()
    ctk_root.update()
    assert t["etat"]["fig"] is not None
    popup.destroy()
