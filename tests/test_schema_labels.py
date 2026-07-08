"""@file test_schema_labels.py
@brief Tests unitaires du moteur anti-collision de labels
(gui/schema_labels.py) : no-op sur figure propre (stabilité visuelle,
condition explicite du design), résolution effective sur collision réelle,
et non-régression des symboles (seuls les Text bougent)."""
import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from gui.schema_labels import ajuster_labels


def _positions(fig):
    return [(t.get_text(), t.get_position()) for ax in fig.axes for t in ax.texts]


def test_no_op_sans_collision():
    # Deux textes largement séparés, aucune ligne à proximité : aucune
    # collision -> aucun déplacement, aucune modification de position.
    fig = Figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 0])
    ax.text(0.2, 0.6, "R1")
    ax.text(5.0, 5.0, "VOUT")
    ax.set_xlim(-1, 6)
    ax.set_ylim(-1, 6)

    before = _positions(fig)
    ajuster_labels(fig)
    after = _positions(fig)

    assert before == after


def test_no_op_titre_et_labels_axe_ignores():
    fig = Figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.set_title("Z = R1+R2")
    ax.text(0.5, 0.5, "R1")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    titre_avant = ax.title.get_position()
    ajuster_labels(fig)
    assert ax.title.get_position() == titre_avant


def test_titre_d_axe_n_etend_pas_les_limites():
    # Le titre (ax.set_title) est ancre au-dessus de la BOITE des axes
    # (transform mixte axes/pixels), PAS en coordonnees donnees : l'inclure
    # dans la re-extension cree un point fixe divergent -- chaque extension
    # de ylim le repousse plus haut en donnees, et ainsi de suite jusqu'a la
    # borne d'iterations (observe sur le drill-down pont : ylim 4.9 -> 13.9,
    # deux tiers de la figure vides).
    fig = Figure(figsize=(5, 5))
    ax = fig.add_subplot(111)
    ax.set_aspect("equal")
    ax.set_title("Z = pont{...}")
    ax.plot([-2, 2], [0, 0])
    ax.text(0.0, 2.0, "R1")
    ax.set_xlim(-2, 2)
    ax.set_ylim(0, 4)

    ajuster_labels(fig)

    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    assert y1 <= 4.5, f"ylim divergee : {y1}"
    assert y0 >= -0.5 and x0 >= -2.5 and x1 <= 2.5


def test_resout_un_chevauchement_reel_entre_deux_textes():
    fig = Figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.axis("off")
    # Deux textes placés EXACTEMENT au même endroit : chevauchement total.
    ax.text(0.5, 0.5, "R1", fontsize=14)
    ax.text(0.5, 0.5, "R2", fontsize=14)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    b0 = [t.get_window_extent(renderer) for t in ax.texts]
    assert b0[0].overlaps(b0[1])

    ajuster_labels(fig)

    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    b1 = [t.get_window_extent(renderer) for t in ax.texts]
    assert not b1[0].overlaps(b1[1])


def test_symboles_lignes_non_deplaces_par_la_resolution():
    # Seuls les Text bougent : les Line2D (symboles/fils) restent intacts.
    fig = Figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.axis("off")
    line, = ax.plot([0.0, 1.0], [0.5, 0.5])
    ax.text(0.5, 0.5, "R1", fontsize=16)
    ax.text(0.5, 0.5, "R2", fontsize=16)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    xdata_avant = list(line.get_xdata())
    ydata_avant = list(line.get_ydata())
    ajuster_labels(fig)
    assert list(line.get_xdata()) == xdata_avant
    assert list(line.get_ydata()) == ydata_avant


def test_aucun_texte_ne_deborde_apres_resolution():
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FCA

    fig = Figure(figsize=(3, 2))
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.text(0.5, 0.5, "R1", fontsize=18)
    ax.text(0.5, 0.5, "R2", fontsize=18)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    ajuster_labels(fig)

    canvas = FCA(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    inv = ax.transData.inverted()
    for t in ax.texts:
        bb = t.get_window_extent(renderer)
        (dx0, dy0), (dx1, dy1) = inv.transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
        assert min(dx0, dx1) >= x0 - 1e-6 and max(dx0, dx1) <= x1 + 1e-6
        assert min(dy0, dy1) >= y0 - 1e-6 and max(dy0, dy1) <= y1 + 1e-6
