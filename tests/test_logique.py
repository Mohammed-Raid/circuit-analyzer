"""@file test_logique.py
@brief Détection des portes CMOS (circuit_analyzer/logique.py) : algèbre
d'arbres série/parallèle, réseaux pull-up/pull-down, classification et rejets."""
import pytest

from circuit_analyzer import logique
from circuit_analyzer.composant import Composant, construire_graphe


# ── Algèbre d'arbres ─────────────────────────────────────────────────────────

def test_reduire_arete_unique():
    assert logique.reduire_reseau([("M1", "OUT", "GND")], "OUT", "GND") == \
        ("feuille", "M1")


def test_reduire_deux_en_serie():
    arbre = logique.reduire_reseau(
        [("M1", "OUT", "X"), ("M2", "X", "GND")], "OUT", "GND")
    assert arbre == ("serie", [("feuille", "M1"), ("feuille", "M2")])


def test_reduire_deux_en_parallele():
    arbre = logique.reduire_reseau(
        [("M1", "OUT", "GND"), ("M2", "OUT", "GND")], "OUT", "GND")
    assert arbre == ("parallele", [("feuille", "M1"), ("feuille", "M2")])


def test_reduire_trois_en_serie_aplatis():
    arbre = logique.reduire_reseau(
        [("M1", "OUT", "X"), ("M2", "X", "Y"), ("M3", "Y", "GND")],
        "OUT", "GND")
    assert arbre == ("serie", [("feuille", "M1"), ("feuille", "M2"),
                               ("feuille", "M3")])


def test_reduire_serie_insensible_a_l_orientation_des_tuples():
    # Arêtes NON ORIENTÉES : l'ordre (net1, net2) d'un arc est arbitraire
    # (drain/source d'un MOSFET). Un tuple renversé ne change pas le réseau.
    arbre = logique.reduire_reseau(
        [("M1", "OUT", "X"), ("M2", "GND", "X")], "OUT", "GND")
    assert arbre == ("serie", [("feuille", "M1"), ("feuille", "M2")])
    # Trois maillons avec M2 et M3 renversés.
    arbre = logique.reduire_reseau(
        [("M1", "OUT", "X"), ("M2", "Y", "X"), ("M3", "GND", "Y")],
        "OUT", "GND")
    assert arbre == ("serie", [("feuille", "M1"), ("feuille", "M2"),
                               ("feuille", "M3")])


def test_reduire_reseau_deconnecte_de_a_b_renvoie_none():
    # Arcs qui ne touchent ni a ni b.
    assert logique.reduire_reseau([("M1", "N1", "N2")], "OUT", "GND") is None


def test_reduire_cycle_isole_a_cote_d_un_chemin_valide_renvoie_none():
    # Cycle flottant P-Q (ne touche ni a ni b) à côté d'un chemin valide :
    # le réseau n'est pas série/parallèle propre entre a et b -> None.
    arcs = [("M1", "OUT", "GND"), ("M2", "P", "Q"), ("M3", "Q", "P")]
    assert logique.reduire_reseau(arcs, "OUT", "GND") is None


def test_reduire_pont_non_serie_parallele_renvoie_none():
    # Pont de Wheatstone : irréductible en série/parallèle.
    arcs = [("M1", "A", "X"), ("M2", "A", "Y"), ("M3", "X", "B"),
            ("M4", "Y", "B"), ("M5", "X", "Y")]
    assert logique.reduire_reseau(arcs, "A", "B") is None


def test_reduire_reseau_vide_renvoie_none():
    assert logique.reduire_reseau([], "OUT", "GND") is None


def test_feuilles_ordre_stable():
    arbre = ("serie", [("feuille", "M2"), ("parallele",
             [("feuille", "M3"), ("feuille", "M1")])])
    assert logique.feuilles(arbre) == ["M2", "M3", "M1"]


def test_forme_pure():
    assert logique.forme_pure(("feuille", "M1")) == ("feuille", ["M1"])
    assert logique.forme_pure(
        ("serie", [("feuille", "M1"), ("feuille", "M2")])) == \
        ("serie", ["M1", "M2"])
    assert logique.forme_pure(
        ("parallele", [("feuille", "M1"), ("feuille", "M2")])) == \
        ("parallele", ["M1", "M2"])
    # Mixte (AOI) : pas une forme pure en v1.
    mixte = ("serie", [("feuille", "M1"),
                       ("parallele", [("feuille", "M2"), ("feuille", "M3")])])
    assert logique.forme_pure(mixte) is None


# ── Graphe de conduction et réseaux ──────────────────────────────────────────

def _m(ref, g, d, s):
    return Composant(ref=ref, type="M", pins={"G": g, "D": d, "S": s}, value="")


def _graphe_inverseur():
    # M1 : VDD—OUT (grille A), M2 : OUT—GND (grille A). Sources aux rails.
    comps = [_m("M1", "A", "OUT", "VDD"), _m("M2", "A", "OUT", "GND")]
    return construire_graphe(comps)


def test_graphe_conduction_liste_les_arcs_ds():
    arcs = logique.graphe_conduction(_graphe_inverseur())
    assert sorted(arcs) == [("M1", "OUT", "VDD"), ("M2", "OUT", "GND")]


def test_graphe_conduction_sans_mosfet_vide():
    comps = [Composant(ref="R1", type="R", pins={"1": "A", "2": "B"}, value="1k")]
    assert logique.graphe_conduction(construire_graphe(comps)) == []


def test_reseau_pull_down_nand2():
    # Pull-down : M3 (OUT—X) + M4 (X—GND) ; pull-up : M1, M2 (OUT—VDD).
    arcs = [("M1", "OUT", "VDD"), ("M2", "OUT", "VDD"),
            ("M3", "OUT", "X"), ("M4", "X", "GND")]
    bas = logique._reseau(arcs, "OUT", {"GND"}, {"VDD"})
    assert sorted(r for r, _, _ in bas) == ["M3", "M4"]
    haut = logique._reseau(arcs, "OUT", {"VDD"}, {"GND"})
    assert sorted(r for r, _, _ in haut) == ["M1", "M2"]


def test_reseau_ne_traverse_pas_un_net_interdit():
    # Chemin OUT—VDD—GND : ne doit PAS compter M2 dans le pull-down
    # (il faudrait traverser VDD).
    arcs = [("M1", "OUT", "VDD"), ("M2", "VDD", "GND")]
    bas = logique._reseau(arcs, "OUT", {"GND"}, {"VDD"})
    assert bas == []
