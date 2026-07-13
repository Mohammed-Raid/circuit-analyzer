"""@file test_assemblage_manhattan.py
@brief Contrats corpus de l'assemblage grille+Manhattan (spec §8.3-8.6) :
fils inter-etages orthogonaux, aucun segment a travers un slot d'etage,
repli _fil_en_z journalise. Etendu au DAG branche en Task 5.
"""
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import pytest

from circuit_analyzer import detecteur
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.xml import lire_xml
from gui import theme
from gui.circuit_viewer import _mesurer_montage  # noqa: F401 -- Step 2 du brief :
# contrats "corpus" (orthogonalite, determinisme) deja verts sur l'ancien
# chemin _fil_en_z -> le RED cible impose par le brief est l'ABSENCE de
# l'assemblage grille+routeur (Task 4), verifiee ici par cet import.
from tools.render_ilots_v2 import _fig_for_ilot

ROOT = Path(__file__).resolve().parent.parent
_WIRE_COLORS = {theme.SCHEMA_COLORS["WIRE"], theme.SCHEMA_COLORS["BUS"]}

# Îlots multi-montages en CHAÎNE (assemblage linéaire).
CHAINES = ["chaine_5_aop.xml", "chaine_conditionnement.xml",
           "ilot_chaine_2ce.xml", "ilot_chaine_3ce.xml",
           "ilot_chaine_ce_suiveur.xml", "ilot_chaine_darlington_ce.xml",
           "ilot_reel_ampli_audio_3etages.xml",
           "ilot_reel_ce_suiveur_sortie_rlc.xml"]


def _fig(nom, detaille):
    comps = lire_xml(str(ROOT / "circuits_industriels" / nom))
    graph = construire_graphe(comps)
    results = detecteur.analyser(graph)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
          for c in comps}
    return _fig_for_ilot(results.ilots[0], graph, ci, results,
                         detaille=detaille)


@pytest.mark.parametrize("nom", CHAINES)
@pytest.mark.parametrize("detaille", [False, True], ids=["z", "det"])
def test_fils_interetages_orthogonaux(nom, detaille):
    # Le RED reel (avant impl. Task 4) revele des Line2D obliques qui ne sont
    # PAS des fils de cablage mais des FORMES DE SYMBOLES schemdraw tracees en
    # un seul element : triangle AOP (7 points, 2 sous-chemins separes par un
    # NaN, colore _WIRE -- un filtre par COULEUR seul est donc insuffisant),
    # fleche de jonction BjtNpn (segment isole a 2 points, NOIR, ni _WIRE ni
    # _BUS), zigzag de Resistor / spirale d'Inductor2 (10 points, noir). Tous
    # les fils reellement caibles par ce module (_fil_en_z, _raccord,
    # _tracer_polyligne, _fil_avec_couplage...) posent UN SEUL segment par
    # `elm.Line().at(p).to(q)` colore explicitement _WIRE/_BUS (aucun
    # chaînage `.to().to()` dans le fichier) -> une Line2D de fil de cablage
    # a TOUJOURS exactement 2 points ET une couleur _WIRE/_BUS. On ne
    # verifie donc l'orthogonalite que sur CES Line2D-la ; les formes de
    # symboles (couleur par defaut noire, ou >2 points) sont hors perimetre
    # de ce contrat, qui porte sur le CABLAGE inter-etages, pas les symboles.
    fig = _fig(nom, detaille)
    for ax in fig.axes:
        for line in ax.lines:
            xy = line.get_xydata()
            if len(xy) != 2 or line.get_color() not in _WIRE_COLORS:
                continue
            for (xa, ya), (xb, yb) in zip(xy[:-1], xy[1:]):
                assert abs(xa - xb) < 1e-6 or abs(ya - yb) < 1e-6, (
                    f"{nom}: segment oblique ({xa},{ya})->({xb},{yb})")


def _xy_eq_nan(a, b):
    """@brief Egalite point-a-point tolerante au NaN.

    Le triangle AOP (et d'autres symboles multi-sous-chemins) est trace en un
    seul `elm.Line`/path schemdraw dont les sous-chemins sont separes par un
    point (NaN, NaN) — technique standard matplotlib. Une comparaison `==`
    nue echoue TOUJOURS sur ce point (NaN != NaN en IEEE 754) meme entre deux
    rendus rigoureusement identiques : ce n'est pas un signe de
    non-determinisme du routage, juste un artefact de la comparaison. On
    traite donc (NaN, NaN) == (NaN, NaN) comme vrai.
    """
    if len(a) != len(b):
        return False
    for (xa, ya), (xb, yb) in zip(a, b):
        if math.isnan(xa) and math.isnan(xb) and math.isnan(ya) and math.isnan(yb):
            continue
        if (xa, ya) != (xb, yb):
            return False
    return True


def test_routage_deterministe():
    a = _fig("chaine_5_aop.xml", True)
    b = _fig("chaine_5_aop.xml", True)
    la = [tuple(map(tuple, l.get_xydata())) for ax in a.axes for l in ax.lines]
    lb = [tuple(map(tuple, l.get_xydata())) for ax in b.axes for l in ax.lines]
    assert len(la) == len(lb)
    for xa, xb in zip(la, lb):
        assert _xy_eq_nan(xa, xb), (xa, xb)


def test_aucun_repli_fil_en_z_sur_le_corpus_chaines(caplog):
    """Contrat spec section 4.3/8.6 : le repli _fil_en_z est LEGAL mais doit
    rester inatteignable sur le corpus de demo -- un port pose a l'INTERIEUR
    d'un slot-obstacle (au lieu de sa frontiere) faisait echouer l'A* des le
    premier pas (24 replis constates au premier render Task 4)."""
    import logging
    with caplog.at_level(logging.WARNING, logger="gui.circuit_viewer"):
        for nom in CHAINES:
            for det in (False, True):
                _fig(nom, det)
    replis = [r for r in caplog.records if "repli _fil_en_z" in r.getMessage()]
    assert not replis, [r.getMessage() for r in replis[:5]]
