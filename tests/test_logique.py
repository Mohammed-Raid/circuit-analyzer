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


# ── Détection complète ───────────────────────────────────────────────────────

def _detecter(comps):
    return logique.detecter_portes_cmos(construire_graphe(comps))


def test_detecte_inverseur_cmos():
    matches = _detecter([_m("M1", "A", "OUT", "VDD"),
                         _m("M2", "A", "OUT", "GND")])
    assert len(matches) == 1
    m = matches[0]
    assert m["circuit_type"] == "Inverseur (CMOS)"
    assert sorted(m["components"]) == ["M1", "M2"]
    assert m["nodes"] == {"entrees": ["A"], "sortie": "OUT",
                          "vdd": "VDD", "gnd": "GND"}
    assert m["io"] == {"ins": ["A"], "out": "OUT"}
    assert m["polarites"] == {"M1": "P", "M2": "N"}
    assert m["fonction"] == ("NOT", ["A"])
    assert m["expression"] == "OUT = NOT(A)"
    assert m["arbres"]["pull_down"] == ("feuille", "M2")


def _nand2():
    return [_m("M1", "A", "OUT", "VDD"), _m("M2", "B", "OUT", "VDD"),
            _m("M3", "A", "OUT", "X"), _m("M4", "B", "X", "GND")]


def test_detecte_nand2():
    matches = _detecter(_nand2())
    assert len(matches) == 1
    m = matches[0]
    assert m["circuit_type"] == "Porte NAND (CMOS)"
    assert m["nodes"]["entrees"] == ["A", "B"]
    assert m["fonction"] == ("NAND", ["A", "B"])
    assert m["expression"] == "OUT = NAND(A, B)"
    assert m["polarites"] == {"M1": "P", "M2": "P", "M3": "N", "M4": "N"}


def test_detecte_nor3():
    comps = [_m("M1", "A", "VDD", "P1"), _m("M2", "B", "P1", "P2"),
             _m("M3", "C", "P2", "OUT"),
             _m("M4", "A", "OUT", "GND"), _m("M5", "B", "OUT", "GND"),
             _m("M6", "C", "OUT", "GND")]
    matches = _detecter(comps)
    assert len(matches) == 1
    assert matches[0]["circuit_type"] == "Porte NOR (CMOS)"
    assert matches[0]["fonction"] == ("NOR", ["A", "B", "C"])


def test_nets_internes_nand_ne_matchent_pas():
    # Invariant anti-candidats-internes (spec § 1.4) : le net X du NAND2
    # ne doit produire aucun match — seule OUT matche.
    matches = _detecter(_nand2())
    assert [m["nodes"]["sortie"] for m in matches] == ["OUT"]


# ── Rejets (un test nommé chacun, spec § 1.4) ────────────────────────────────

def test_rejet_suiveur_sources_sur_out():
    # Paire complémentaire, grilles communes, mais S des DEUX transistors
    # sur OUT : push-pull suiveur, PAS un inverseur (critère D/S).
    matches = _detecter([_m("M1", "A", "VDD", "OUT"),
                         _m("M2", "A", "GND", "OUT")])
    assert matches == []


def test_rejet_cablage_panache():
    # Un transistor source-au-rail, l'autre source-à-OUT : incohérent.
    matches = _detecter([_m("M1", "A", "OUT", "VDD"),
                         _m("M2", "A", "GND", "OUT")])
    assert matches == []


def test_rejet_grille_sur_rail():
    matches = _detecter([_m("M1", "VDD", "OUT", "VDD"),
                         _m("M2", "VDD", "OUT", "GND")])
    assert matches == []


def test_rejet_sortie_reinjectee():
    matches = _detecter([_m("M1", "OUT", "OUT", "VDD"),
                         _m("M2", "OUT", "OUT", "GND")])
    assert matches == []


def test_rejet_grilles_dupliquees():
    # Deux NMOS en parallèle sur la MÊME grille (drive strength) : rejet v1.
    comps = [_m("M1", "A", "VDD", "P1"), _m("M2", "A", "P1", "OUT"),
             _m("M3", "A", "OUT", "GND"), _m("M4", "A", "OUT", "GND")]
    assert _detecter(comps) == []


def test_rejet_pull_up_bi_rail():
    comps = [_m("M1", "A", "OUT", "VDD"), _m("M2", "B", "OUT", "VCC"),
             _m("M3", "A", "OUT", "X"), _m("M4", "B", "X", "GND")]
    assert _detecter(comps) == []


def test_rejet_non_dual():
    # Pull-down série(A,B), pull-up une seule feuille A : multisets inégaux.
    comps = [_m("M1", "A", "OUT", "VDD"),
             _m("M2", "A", "OUT", "X"), _m("M3", "B", "X", "GND")]
    assert _detecter(comps) == []


def test_rejet_sans_rail_ou_sans_masse():
    assert _detecter([_m("M1", "A", "OUT", "N1"),
                      _m("M2", "A", "OUT", "GND")]) == []


def test_garde_zero_mosfet():
    comps = [Composant(ref="R1", type="R", pins={"1": "A", "2": "B"}, value="1k")]
    assert _detecter(comps) == []
