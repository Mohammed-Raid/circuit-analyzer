"""@file test_saisie_fondations.py
@brief Fondations de l'onglet Saisie (spec 2026-07-15 §2.3/§3.3) :
itérateur public du catalogue et lecture XML sans aliasing.
"""
from pathlib import Path

from circuit_analyzer.catalogue import entrees_catalogue, identifier
from circuit_analyzer.xml import lire_xml

ROOT = Path(__file__).resolve().parent.parent


def test_entrees_catalogue_couvre_les_familles():
    entrees = list(entrees_catalogue())
    valeurs = {(t, v) for t, v, _e in entrees}
    for attendu in [("U", "NE555"), ("U", "74HC00"), ("U", "LM317"),
                    ("U", "7805"), ("Q", "2N2222"), ("M", "IRFZ44N"),
                    ("D", "1N4148"), ("D", "LED rouge")]:
        assert attendu in valeurs, attendu


def test_entrees_catalogue_coherentes_avec_identifier():
    # Chaque entrée listée doit être re-identifiée par identifier()
    # (même nom de catalogue) : l'itérateur ne peut pas dériver des tables.
    for type_, value, entree in entrees_catalogue():
        vu = identifier(type_, value)
        assert vu is not None, (type_, value)
        assert vu["nom"] == entree["nom"], (type_, value)


def test_lire_xml_sans_aliasing_garde_les_broches_numerotees():
    chemin = str(ROOT / "circuits_industriels" / "reel_741_inverseur.xml")
    brut = lire_xml(chemin, alias_catalogue=False)
    u1 = next(c for c in brut if c.ref == "U1")
    assert set(u1.pins) == {"1", "2", "3", "4", "5", "6", "7", "8"}


def test_lire_xml_defaut_inchange_broches_aliassees():
    chemin = str(ROOT / "circuits_industriels" / "reel_741_inverseur.xml")
    alias = lire_xml(chemin)
    u1 = next(c for c in alias if c.ref == "U1")
    assert {"IN-", "IN+", "OUT"} <= set(u1.pins)
