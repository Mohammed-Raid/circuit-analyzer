"""@file test_logique.py
@brief Détection des portes CMOS (circuit_analyzer/logique.py) : algèbre
d'arbres série/parallèle, réseaux pull-up/pull-down, classification et rejets."""
import pytest

from circuit_analyzer import logique


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
