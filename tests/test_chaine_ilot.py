"""@file test_chaine_ilot.py
@brief Vue îlot multi-AOP : ordonnancement par flux + chaîne de schémas connectés."""
from circuit_analyzer.xml import lire_xml
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser
from gui import circuit_viewer as cv


def _matches_chaine():
    comps = lire_xml("circuits_industriels/chaine_5_aop.xml")
    res = analyser(construire_graphe(comps))
    return [r for r in res if "(AOP)" in r["circuit_type"]]


def test_ordonner_montages_flux_chaine_5():
    ordre = cv._ordonner_montages_flux(_matches_chaine())
    assert ordre is not None
    types = [m["circuit_type"] for m in ordre]
    assert types == [
        "Amplificateur non-inverseur (AOP)",
        "Amplificateur inverseur (AOP)",
        "Intégrateur (AOP)",
        "Dérivateur (AOP)",
        "Suiveur de tension (AOP)",
    ]


def test_ordonner_montages_flux_non_chaine_renvoie_none():
    # Deux montages sans lien OUT->IN entre eux : pas une chaîne.
    from circuit_analyzer.composant import Composant
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M1", "OUT": "O1"}),
        Composant("R1", "R", {"1": "VIN", "2": "M1"}, "1k"),
        Composant("R2", "R", {"1": "M1", "2": "O1"}, "10k"),
        Composant("U2", "U", {"IN+": "GND", "IN-": "M2", "OUT": "O2"}),
        Composant("R3", "R", {"1": "AUTRE", "2": "M2"}, "1k"),
        Composant("R4", "R", {"1": "M2", "2": "O2"}, "10k"),
    ]
    res = analyser(construire_graphe(comps))
    aops = [r for r in res if "(AOP)" in r["circuit_type"]]
    assert cv._ordonner_montages_flux(aops) is None
