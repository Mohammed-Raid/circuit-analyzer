"""@file test_audit_ilots_visuel.py
@brief Contrats cibles de l'audit visuel ilots 2026-07-13.

Chaque test fige la geometrie corrigee d'un defaut constate sur les rendus
(sweep complet de circuits_industriels, modes Z et detaille) :
  - V1 : reseau parallele NON compact deplie (Zf = R//C) -> ref et valeur d'une
    branche cote a cote le long de la branche, pas empilees en profondeur vers
    l'axe (la colonne fusionnee "R2 / 10 kΩ / 10 nF / C1" etait illisible).
  - V2 : Zf composite deplie de la topologie inverseuse releve au-dessus du
    corps de l'AOP (la branche basse du parallele frolait le triangle).
  - V3 : pont diviseur du suiveur (buffer de reference) -> labels Z LATERAUX
    (le label de Z1 ecrasait le label VCC au bout de la boite).
  - V4 : Z locale vers VCC -> label VCC au-dessus du stub (loc="top" schemdraw
    sur un fil vertical tombait a GAUCHE, sous la boite Z voisine).
  - V5 : chemin single-ref de _z_box en vue detaillee -> label_loc du caller
    honore (le Zg du differentiel demandait "right" et recevait le defaut
    schemdraw, d'ou 'R14' sous la valeur de R12 sur pid_controller).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

from circuit_analyzer import detecteur
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.xml import lire_xml
from tools.render_ilots_v2 import _fig_for_ilot

ROOT = Path(__file__).resolve().parent.parent


def _fig(nom, idx=0, detaille=False):
    comps = lire_xml(str(ROOT / "circuits_industriels" / f"{nom}.xml"))
    graph = construire_graphe(comps)
    results = detecteur.analyser(graph)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
          for c in comps}
    return _fig_for_ilot(results.ilots[idx], graph, ci, results,
                         detaille=detaille)


def _texte(fig, contenu):
    for ax in fig.axes:
        for t in ax.texts:
            if t.get_text() == contenu:
                return t
    raise AssertionError(f"texte {contenu!r} introuvable")


def test_parallele_non_compact_ref_et_valeur_cote_a_cote():
    # V1 : Zf = R2//C1 deplie (aop_inverseurs_multiples, 1er inverseur).
    fig = _fig("aop_inverseurs_multiples", 0, detaille=True)
    for ref_txt, val_txt in (("R2", "10 kΩ"), ("C1", "10 nF")):
        t_ref, t_val = _texte(fig, ref_txt), _texte(fig, val_txt)
        dy = abs(t_ref.get_position()[1] - t_val.get_position()[1])
        dx = abs(t_ref.get_position()[0] - t_val.get_position()[0])
        assert dy < 0.2, (
            f"{ref_txt}/{val_txt} : empiles en profondeur (dy={dy:.2f}), "
            "attendus cote a cote sur la meme rangee")
        assert dx > 0.5, f"{ref_txt}/{val_txt} : superposes (dx={dx:.2f})"


def test_zf_composite_deplie_degage_le_corps_de_l_aop():
    # V2 : la branche basse du R2//C1 deplie ne descend plus sur le triangle
    # (points des Line2D couleur condensateur dans la plage x du Zf).
    from gui.circuit_viewer import _COMP_COLORS
    import matplotlib.colors as mcolors
    cyan = mcolors.to_rgba(_COMP_COLORS["C"])
    fig = _fig("aop_inverseurs_multiples", 0, detaille=True)
    ax = fig.axes[0]
    pts_bas = []
    for line in ax.lines:
        if mcolors.to_rgba(line.get_color()) != cyan:
            continue
        for x, y in line.get_xydata():
            # plage x du reseau Zf (entre le noeud de sommation et OUT)
            if 3.0 <= x <= 8.5:
                pts_bas.append(y)
    assert pts_bas, "aucun trace de condensateur trouve dans la plage du Zf"
    assert min(pts_bas) > 1.0, (
        f"branche C du Zf a y={min(pts_bas):.2f} : frole le corps de l'AOP "
        "(sommet du triangle vers y=0.6)")


def test_pont_diviseur_suiveur_labels_lateraux():
    # V3 : buffer_reference mode Z -- les labels Z1/Z2 du pont sont LATERAUX
    # (va=center), plus jamais au bout de la boite (va=bottom/top) ou ils
    # percutaient le label du rail.
    fig = _fig("buffer_reference", 0, detaille=False)
    labels = [t for ax in fig.axes for t in ax.texts
              if t.get_text().startswith(("Z1", "Z2"))]
    assert len(labels) == 2, [t.get_text() for t in labels]
    for t in labels:
        assert t.get_verticalalignment() == "center", (
            f"{t.get_text()!r} : va={t.get_verticalalignment()} "
            "(attendu 'center' = label lateral)")


def test_z_locale_vers_vcc_label_au_dessus_du_stub():
    # V4 : darlington relais mode Z -- le VCC de la charge collecteur est
    # au-dessus du stub (ha=center, va=bottom), plus a gauche sous la boite.
    fig = _fig("ilot_reel_darlington_relais_rlc", 0, detaille=False)
    vccs = [t for ax in fig.axes for t in ax.texts if t.get_text() == "VCC"]
    assert any(
        t.get_horizontalalignment() == "center"
        and t.get_verticalalignment() == "bottom"
        for t in vccs
    ), [(t.get_horizontalalignment(), t.get_verticalalignment()) for t in vccs]


def test_z_box_single_ref_detaille_honore_label_loc():
    # V5 : pid_controller, differentiel deplie -- le Zg (R14, boite verticale,
    # label_loc="right" choisi a l'audit fenetre) porte son label A DROITE
    # (ha=left) au lieu du defaut schemdraw (gauche sur une verticale).
    fig = _fig("pid_controller", 0, detaille=True)
    t = _texte(fig, "R14\n10 kΩ")
    assert t.get_horizontalalignment() == "left", (
        f"label R14 : ha={t.get_horizontalalignment()} (attendu 'left' = "
        "a droite de la boite verticale, cote demande par le drawer)")
