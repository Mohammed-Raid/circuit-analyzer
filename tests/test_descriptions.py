"""Chaque circuit intégré doit avoir sa description (fiche lecture seule GUI)."""
from circuit_analyzer.detecteur import NOMS_CIRCUITS
from gui.descriptions import DESCRIPTIONS_CIRCUITS


def test_chaque_circuit_a_une_description():
    manquants = [n for n in NOMS_CIRCUITS if n not in DESCRIPTIONS_CIRCUITS]
    assert not manquants, f'Descriptions manquantes : {manquants}'


def test_pas_de_description_orpheline():
    orphelines = [n for n in DESCRIPTIONS_CIRCUITS if n not in NOMS_CIRCUITS]
    assert not orphelines, f'Descriptions sans circuit : {orphelines}'


def test_descriptions_non_vides():
    for nom, desc in DESCRIPTIONS_CIRCUITS.items():
        assert desc.strip(), f'Description vide pour {nom}'
