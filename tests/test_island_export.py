"""
@file test_island_export.py
@brief Export PNG cadre sur le CONTENU reel du schema d'ilot
(`gui.circuit_viewer._exporter_figure`), pas sur les limites d'axe affichees
a l'ecran (volontairement asymetriques : marges de cadrage + extensions
unilaterales du moteur anti-collision de labels, cf. gui/schema_labels.py).

Meme idiome que tests/test_island_viewport.py (vrai root Tk, saute sans
affichage) : on ouvre une vraie fenetre `show_island` pour recuperer une
figure d'ilot REELLE (pas une figure jouet construite a la main -- c'est
justement l'asymetrie du VRAI moteur de rendu qu'on veut verifier corrigee).
"""
import pytest

PIL = pytest.importorskip("PIL.Image")
from PIL import Image

from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser
from circuit_analyzer.xml import lire_xml
import gui.circuit_viewer as cv

_MARGE_TOLERANCE_PX = 8
_FOND = (0xFA, 0xFA, 0xFA)   # SCH_BG "#fafafa"
_TOL_FOND = 6                # tolerance anti-crenelage (antialiasing des traits)


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


def _ouvrir(ctk_root, fichier, index=0):
    comps = lire_xml(f"circuits_industriels/{fichier}")
    graph = construire_graphe(comps)
    res = analyser(graph)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    popup = cv.show_island(res.ilots[index], graph, ci, parent=ctk_root, results=res)
    ctk_root.update()
    return popup


def _bbox_non_fond(png_path):
    """@brief Bbox pixel (gauche, haut, droite, bas) des pixels NON-fond du
    PNG (tolerance `_TOL_FOND` autour de `_FOND`, pour ignorer l'antialiasing
    des traits sur le fond)."""
    img = Image.open(png_path).convert("RGB")
    w, h = img.size
    pixels = img.load()
    gauche, haut, droite, bas = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            if (abs(r - _FOND[0]) > _TOL_FOND or abs(g - _FOND[1]) > _TOL_FOND
                    or abs(b - _FOND[2]) > _TOL_FOND):
                gauche, haut = min(gauche, x), min(haut, y)
                droite, bas = max(droite, x), max(bas, y)
    assert droite >= 0, "aucun pixel non-fond trouve (export vide ?)"
    return gauche, haut, droite, bas, w, h


def test_export_png_est_cadre_centre_sur_un_ilot_reel_asymetrique(ctk_root, tmp_path):
    # ilot_reel_ce_suiveur_sortie_rlc : montage en chaine (suiveur + charge
    # RLC) dont le cadrage d'axe est un cas connu d'asymetrie (marges de
    # cadrage + extensions unilaterales de l'anti-collision, cf. rapport
    # chips-export section B) -- avant le fix, le contenu y est decentre
    # dans le PNG exporte.
    popup = _ouvrir(ctk_root, "ilot_reel_ce_suiveur_sortie_rlc.xml")
    t = popup._etat_test
    fig = t["etat"]["fig"]

    png = tmp_path / "export.png"
    cv._exporter_figure(fig, str(png))

    gauche, haut, droite, bas, w, h = _bbox_non_fond(png)
    marge_g, marge_d = gauche, (w - 1 - droite)
    marge_h, marge_b = haut, (h - 1 - bas)

    assert marge_g == pytest.approx(marge_d, abs=_MARGE_TOLERANCE_PX), (
        f"marges gauche/droite non symetriques : {marge_g} vs {marge_d}")
    assert marge_h == pytest.approx(marge_b, abs=_MARGE_TOLERANCE_PX), (
        f"marges haut/bas non symetriques : {marge_h} vs {marge_b}")

    popup.destroy()


def test_export_ne_modifie_pas_les_limites_d_axe_affichees(ctk_root, tmp_path):
    """L'affichage a l'ecran ne doit pas bouger : xlim/ylim restaures apres
    l'export (contrainte explicite du rapport chips-export section B)."""
    popup = _ouvrir(ctk_root, "ilot_reel_ce_suiveur_sortie_rlc.xml")
    t = popup._etat_test
    fig = t["etat"]["fig"]
    ax = fig.axes[0]

    xlim_avant, ylim_avant = ax.get_xlim(), ax.get_ylim()
    cv._exporter_figure(fig, str(tmp_path / "export.png"))

    assert ax.get_xlim() == pytest.approx(xlim_avant)
    assert ax.get_ylim() == pytest.approx(ylim_avant)

    popup.destroy()


def test_export_restaure_la_visibilite_des_textes_de_figure(ctk_root, tmp_path):
    """L'astuce "cliquez une boite Z..." (fig.text) est masquee PENDANT
    l'export (cf. docstring `_exporter_figure`) mais doit redevenir visible
    juste apres."""
    popup = _ouvrir(ctk_root, "ilot_reel_ce_suiveur_sortie_rlc.xml")
    t = popup._etat_test
    fig = t["etat"]["fig"]

    visibles_avant = [tx.get_visible() for tx in fig.texts]
    cv._exporter_figure(fig, str(tmp_path / "export.png"))
    visibles_apres = [tx.get_visible() for tx in fig.texts]

    assert visibles_apres == visibles_avant

    popup.destroy()
