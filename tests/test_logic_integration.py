"""@file test_logic_integration.py
@brief Intégration des portes CMOS dans le pipeline complet (matcher,
anti-vol, anti-faux-positifs sur le corpus analogique existant)."""
import glob

import pytest

from circuit_analyzer import detecteur, logique
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.xml import lire_xml


def _m(ref, g, d, s):
    return Composant(ref=ref, type="M", pins={"G": g, "D": d, "S": s}, value="")


def test_analyser_detecte_l_inverseur_en_priorite():
    graphe = construire_graphe([_m("M1", "A", "OUT", "VDD"),
                                _m("M2", "A", "OUT", "GND")])
    res = detecteur.analyser(graphe)
    types = [c["circuit_type"] for c in res]
    assert "Inverseur (CMOS)" in types
    # Anti-vol : les M de la porte ne sont pas repris par un détecteur MOSFET.
    assert "MOSFET en commutation" not in types


def test_noms_circuits_contiennent_les_portes():
    for nom in ("Inverseur (CMOS)", "Porte NAND (CMOS)", "Porte NOR (CMOS)"):
        assert nom in detecteur.NOMS_CIRCUITS


# LE filet anti-régression de la démo : le détecteur de portes ne matche
# RIEN sur tout le corpus analogique existant.
@pytest.mark.parametrize("fichier", sorted(
    glob.glob("circuits_industriels/ilot_*.xml")
    + glob.glob("circuits_industriels/tr_*.xml")
    + glob.glob("circuits_industriels/aop_*.xml")))
def test_zero_faux_positif_sur_corpus_analogique(fichier):
    graphe = construire_graphe(lire_xml(fichier))
    assert logique.detecter_portes_cmos(graphe) == []


@pytest.mark.parametrize("fichier", sorted(
    glob.glob("circuits_industriels/ilot_*.xml")
    + glob.glob("circuits_industriels/tr_*.xml")
    + glob.glob("circuits_industriels/aop_*.xml")))
def test_non_regression_types_detectes_corpus(fichier):
    # L'insertion en tête ne change la détection d'AUCUN fichier existant :
    # aucun type porte ne doit apparaître dans leurs résultats.
    res = detecteur.analyser(construire_graphe(lire_xml(fichier)))
    for c in res:
        assert "(CMOS)" not in c["circuit_type"]
