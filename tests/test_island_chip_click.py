"""
@file test_island_chip_click.py
@brief Tests unitaires de la resolution de position d'un composant dans une
figure d'ilot (`gui.circuit_viewer._position_composant`), brique utilisee par
le clic sur une puce "Composants : ..." de la fenetre Schema ilot pour
centrer la vue et poser un anneau de surbrillance (cf. rapport
chips-export). Le test Tk d'integration (clic reel, scroll, disparition de
l'anneau) vit dans tests/test_island_viewport.py, meme idiome.
"""
import matplotlib

matplotlib.use("Agg")
from matplotlib.figure import Figure

from gui.circuit_viewer import _fraction_centree, _position_composant


def _fig_vide():
    fig = Figure(figsize=(4, 3))
    fig.add_subplot(111)
    fig._z_hitboxes = []
    return fig


def test_position_via_hitbox_z():
    fig = _fig_vide()
    fig._z_hitboxes = [(1.0, 3.0, 2.0, 4.0, ["R1", "R2"], "R1+R2")]
    assert _position_composant(fig, "R1") == (2.0, 3.0)
    assert _position_composant(fig, "R2") == (2.0, 3.0)


def test_position_via_label_texte_simple():
    fig = _fig_vide()
    fig.axes[0].text(5.0, 6.0, "R5")
    assert _position_composant(fig, "R5") == (5.0, 6.0)


def test_position_via_label_texte_avec_valeur_espace():
    fig = _fig_vide()
    fig.axes[0].text(1.0, 1.0, "Rb = 10k")
    assert _position_composant(fig, "Rb") == (1.0, 1.0)


def test_position_via_label_texte_multiligne():
    fig = _fig_vide()
    fig.axes[0].text(2.0, 2.0, "C1\n100nF")
    assert _position_composant(fig, "C1") == (2.0, 2.0)


def test_hitbox_prioritaire_sur_le_texte():
    # Si les deux sources existent, la hitbox Z (cliquable, plus fiable) gagne.
    fig = _fig_vide()
    fig.axes[0].text(9.0, 9.0, "R1")
    fig._z_hitboxes = [(1.0, 3.0, 2.0, 4.0, ["R1"], "R1")]
    assert _position_composant(fig, "R1") == (2.0, 3.0)


def test_frontiere_de_mot_r51_ne_matche_pas_r5():
    fig = _fig_vide()
    fig.axes[0].text(9.0, 9.0, "R51")
    assert _position_composant(fig, "R5") is None


def test_ref_introuvable_retourne_none():
    fig = _fig_vide()
    fig.axes[0].text(1.0, 1.0, "R7")
    assert _position_composant(fig, "R5") is None


def test_fig_sans_hitboxes_attribut_ne_plante_pas():
    fig = Figure(figsize=(4, 3))
    fig.add_subplot(111)
    assert _position_composant(fig, "R5") is None


# ── _fraction_centree ─────────────────────────────────────────────────────────

def test_fraction_centree_point_au_centre_exact():
    # Convention Tk : xview_moveto(f) place le bord gauche visible a
    # f * total. Pour centrer la cible : bord gauche vise = cible - vw/2,
    # donc f = (cible - vw/2) / total. Verite geometrique : le centre
    # visible (f * total + vw/2) retombe sur la cible.
    f = _fraction_centree(500, 1000, 200)
    assert f == (500 - 100) / 1000
    assert f * 1000 + 100 == 500


def test_fraction_centree_bornee_a_zero_pres_du_bord_gauche():
    assert _fraction_centree(0, 1000, 200) == 0.0


def test_fraction_centree_cible_au_bord_droit_laisse_tk_clamper():
    # Cible collee au bord droit : f = (1000-100)/1000 = 0.9 demande un bord
    # gauche a 900 px ; Tk clampe lui-meme a total - viewport (800 px) et
    # montre la fin de la scrollregion. Sur-clamper ici a 1.0 (l'ancienne
    # convention) sur-defilait TOUS les centrages loin du bord gauche.
    assert _fraction_centree(1000, 1000, 200) == 0.9
