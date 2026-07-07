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

    assert mode["detaille"] is False
    assert zoom["facteur"] == 1.0

    t["zoom_in"]()
    ctk_root.update()
    assert zoom["facteur"] == pytest.approx(1.25)
    assert mode["detaille"] is False, "le zoom ne doit pas toucher le mode"

    t["toggle"]()
    ctk_root.update()
    assert mode["detaille"] is True
    assert zoom["facteur"] == pytest.approx(1.25), "le toggle ne doit pas toucher le zoom"

    t["zoom_out"]()
    ctk_root.update()
    assert zoom["facteur"] == pytest.approx(1.0)
    assert mode["detaille"] is True, "le zoom ne doit pas toucher le mode"

    t["toggle"]()
    ctk_root.update()
    assert mode["detaille"] is False
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
    popup = _ouvrir(ctk_root, "ilot_reel_darlington_relais_rlc.xml")
    t = popup._etat_test

    actions = [
        t["zoom_in"], t["toggle"], t["zoom_in"], t["toggle"],
        t["zoom_out"], t["toggle"], t["zoom_reset"], t["toggle"],
    ]
    assert len(actions) >= 8

    refs = []
    old_fig = None
    for action in actions:
        old_fig = t["etat"]["fig"]
        refs.append(weakref.ref(old_fig))
        action()
        ctk_root.update()

    del old_fig
    gc.collect()

    vivantes = [i for i, r in enumerate(refs) if r() is not None]
    popup.destroy()
    assert not vivantes, (
        f"{len(vivantes)}/{len(refs)} figures remplacees non collectees "
        f"apres gc.collect() (indices {vivantes})"
    )


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

    t["toggle"]()
    ctk_root.update()
    assert t["mode"]["detaille"] is True

    t["ajuster"]()
    ctk_root.update()
    assert t["mode"]["detaille"] is True, "Ajuster ne doit pas toucher le mode"

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

def test_clic_puce_centre_le_scroll_et_affiche_puis_efface_l_anneau(ctk_root):
    """Ilot en chaine (ilot_tous_aop, toujours defilant) : le clic simule sur
    une puce composant (hook `cliquer_composant`, meme idiome que
    `zoom_in`/`toggle` -- pas de dependance fragile aux libelles de bouton ni
    aux widgets Tk) doit centrer le viewport scrollable sur ce composant et
    poser un anneau de surbrillance qui disparait apres le delai."""
    popup = _ouvrir(ctk_root, "ilot_tous_aop.xml")
    t = popup._etat_test
    fig = t["etat"]["fig"]
    canvas = t["etat"]["canvas"]
    view = getattr(canvas, "_scroll_view", None)
    assert view is not None, "ilot_tous_aop (chaine) attendu toujours defilant"

    ilot, _graph, _ci, _res = _premier_ilot("ilot_tous_aop.xml")
    ref = next(r for r in ilot["composants"] if cv._position_composant(fig, r) is not None)

    pos = cv._position_composant(fig, ref)
    ax0 = fig.axes[0]
    dispx, dispy = ax0.transData.transform(pos)
    fig_w_px, fig_h_px = cv._figure_pixel_size(fig)
    vw = max(1, view.winfo_width())
    vh = max(1, view.winfo_height())
    attendu_fx = cv._fraction_centree(dispx, fig_w_px, vw)
    attendu_fy = cv._fraction_centree(fig_h_px - dispy, fig_h_px, vh)

    t["cliquer_composant"](ref)
    ctk_root.update()

    fx0, _fx1 = view.xview()
    fy0, _fy1 = view.yview()
    # Tolerance large (pas 1e-6) : Tk quantifie la fraction reportee par
    # xview()/yview() en pixels internes (scrollregion parsee en chaine),
    # introduisant un ecart negligeable (< 1 px observe) face au calcul flottant.
    assert fx0 == pytest.approx(attendu_fx, abs=2e-3)
    assert fy0 == pytest.approx(attendu_fy, abs=2e-3)

    anneaux = [p for p in ax0.patches if getattr(p, "_surbrillance_puce", False)]
    assert len(anneaux) == 1, "un anneau de surbrillance doit etre pose au clic"
    assert anneaux[0].center == pytest.approx(pos)

    time.sleep((cv._CHIP_HIGHLIGHT_DELAY_MS / 1000.0) + 0.3)
    ctk_root.update()

    anneaux_apres = [p for p in ax0.patches if getattr(p, "_surbrillance_puce", False)]
    assert not anneaux_apres, "l'anneau doit disparaitre apres le delai"

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

    t["toggle"]()
    ctk_root.update()
    fig_apres_toggle = t["etat"]["fig"]

    ilot, _graph, _ci, _res = _premier_ilot("ilot_reel_darlington_relais_rlc.xml")
    ref = next((r for r in ilot["composants"]
                if cv._position_composant(fig_apres_toggle, r) is not None), None)
    assert ref is not None, "au moins un composant doit rester localisable en vue detaillee"

    t["cliquer_composant"](ref)
    ctk_root.update()

    anneaux = [p for p in fig_apres_toggle.axes[0].patches
               if getattr(p, "_surbrillance_puce", False)]
    assert len(anneaux) == 1

    popup.destroy()
