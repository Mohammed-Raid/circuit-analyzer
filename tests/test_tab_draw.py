"""@file test_tab_draw.py
@brief Groupage automatique a l'export du schema dessine (spec 2026-08-06).

Teste _xml_groupe_par_circuit directement (fonction module-level, aucun Tk) —
meme principe que test_eretro_patch.py pour tab_analyze._texte_export_analyse.
"""
import xml.etree.ElementTree as ET

from circuit_analyzer.composant import Composant
from gui.tab_draw import _xml_groupe_par_circuit


def _montage_reconnu():
    """@brief Diviseur R1/R2 + C1 + AOP U1 — meme montage que
    tests/test_eretro_groupes_reels.py::_carte, deja prouve detecte par
    test_grpl_est_creee_meme_absente_de_la_source."""
    return [
        Composant("R1", "R", {"1": "IN", "2": "N1"}, "10k"),
        Composant("R2", "R", {"1": "N1", "2": "OUT"}, "100k"),
        Composant("C1", "C", {"1": "N1", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "GND", "IN-": "N1", "OUT": "OUT"}, ""),
    ]


def test_montage_reconnu_produit_un_groupe():
    xml = _xml_groupe_par_circuit(_montage_reconnu())
    racine = ET.fromstring(xml)
    assert racine.findall("./GrpL/GRPS"), "aucun groupe ecrit pour un montage reconnu"


def test_aucun_montage_reconnu_grpl_vide():
    """Non-regression : une resistance isolee ne doit RIEN grouper."""
    xml = _xml_groupe_par_circuit([Composant("R1", "R", {"1": "IN", "2": "OUT"}, "1k")])
    racine = ET.fromstring(xml)
    assert racine.findall("./GrpL/GRPS") == []
    assert racine.find("GrpL") is not None


def test_fonction_est_bien_exportee_du_module():
    import gui.tab_draw as td
    assert callable(td._xml_groupe_par_circuit)
