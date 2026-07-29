"""@file test_eretro_patch.py
@brief Retour fidele vers ERetroDesign : pont ref->element et ecriture des groupes.
"""
import os
import xml.etree.ElementTree as ET

import pytest

from circuit_analyzer.composant import Composant
from circuit_analyzer.xml import generer_xml, lire_xml

_DOSSIER_REEL = "CARTE POUR TESTER (VRAI TEST)"


def _fichier_synthetique(tmp_path, comps=None):
    """@brief Ecrit un BoardSCH valide via generer_xml et renvoie son chemin.

    On part de notre PROPRE generateur : il produit un document que lire_xml
    sait relire, donc le test n'a pas besoin des cartes reelles (absentes en CI).
    """
    comps = comps or [
        Composant("R1", "R", {"1": "IN", "2": "N1"}, "10k"),
        Composant("C1", "C", {"1": "N1", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "N1", "IN-": "N2", "OUT": "OUT"}, ""),
    ]
    p = os.path.join(str(tmp_path), "synth.xml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(generer_xml(comps))
    return p


def test_source_absente_quand_la_liste_ne_vient_pas_d_un_xml():
    assert getattr([], "source", None) is None


def test_lire_xml_publie_l_arbre_et_le_pont(tmp_path):
    comps = lire_xml(_fichier_synthetique(tmp_path))
    src = comps.source
    assert src is not None
    assert isinstance(src.arbre, ET.ElementTree)
    # Une entree de pont par composant emis, et pas une de plus.
    assert set(src.elements) == {c.ref for c in comps}


def test_le_pont_designe_le_bon_element(tmp_path):
    comps = lire_xml(_fichier_synthetique(tmp_path))
    src = comps.source
    items = src.arbre.getroot().findall(".//CmpntL/DataItem")
    for c in comps:
        assert src.elements[c.ref] in items


def test_le_pont_expose_les_fils_dans_l_ordre_du_fichier(tmp_path):
    comps = lire_xml(_fichier_synthetique(tmp_path))
    src = comps.source
    assert src.lignes == src.arbre.getroot().findall(".//lineL/Line")
    # Chaque fil resolu designe deux refs connues du pont.
    for idx, (ra, rb) in src.lignes_refs.items():
        assert 0 <= idx < len(src.lignes)
        assert ra in src.elements and rb in src.elements


@pytest.mark.skipif(not os.path.isdir(_DOSSIER_REEL), reason="cartes reelles absentes")
def test_un_compose_pointe_sur_son_boitier_pas_sur_ses_entrailles():
    chemin = os.path.join(_DOSSIER_REEL, "PowtranAlim20260809.xml")
    comps = lire_xml(chemin)
    src = comps.source
    boitiers = src.arbre.getroot().findall(".//CCmpntL/CComp")
    internes = [r for r in src.elements if "." in r]
    assert internes, "la carte de reference contient une puce composee"
    for ref in internes:
        assert src.elements[ref] in boitiers
