"""
@file test_descriptions.py
@brief Tests automatises pour test_descriptions.
"""

"""Chaque circuit intégré doit avoir sa description (fiche lecture seule GUI)."""
from circuit_analyzer.detecteur import NOMS_CIRCUITS
from gui.descriptions import DESCRIPTIONS_CIRCUITS


def test_chaque_circuit_a_une_description():
    """@brief Verifie chaque circuit a une description.

    @return None
    """
    manquants = [n for n in NOMS_CIRCUITS if n not in DESCRIPTIONS_CIRCUITS]
    assert not manquants, f'Descriptions manquantes : {manquants}'


def test_pas_de_description_orpheline():
    """@brief Verifie pas de description orpheline.

    @return None
    """
    orphelines = [n for n in DESCRIPTIONS_CIRCUITS if n not in NOMS_CIRCUITS]
    assert not orphelines, f'Descriptions sans circuit : {orphelines}'


def test_chaque_drawer_est_un_circuit_declare():
    """@brief Tout circuit dessinable (_DRAWERS) doit figurer dans NOMS_CIRCUITS.

    NOMS_CIRCUITS alimente la liste de l'onglet Circuits : un détecteur avec
    drawer mais absent de la liste serait détecté/dessiné mais invisible GUI.

    @return None
    """
    from gui.circuit_viewer import _DRAWERS
    inconnus = [n for n in _DRAWERS if n not in NOMS_CIRCUITS]
    assert not inconnus, f'Drawers sans circuit déclaré : {inconnus}'


def test_descriptions_non_vides():
    """@brief Verifie descriptions non vides.

    @return None
    """
    for nom, desc in DESCRIPTIONS_CIRCUITS.items():
        assert desc.strip(), f'Description vide pour {nom}'
