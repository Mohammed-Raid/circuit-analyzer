"""@file test_tab_quick_entry.py
@brief Onglet Saisie (spec 2026-07-15 §2) : construction, broches par type,
insertion catalogue, enregistrer/analyser, validation UI.
"""
import tempfile
from pathlib import Path

import pytest

ctk = pytest.importorskip("customtkinter")

from circuit_analyzer.xml import lire_xml           # noqa: E402
from gui.tab_quick_entry import TabQuickEntry       # noqa: E402


@pytest.fixture
def racine():
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("pas de display Tk")
    root.withdraw()
    yield root
    root.destroy()


def test_ajout_r_puis_type_q_reconstruit_les_broches(racine):
    tab = TabQuickEntry(racine)
    tab._ajouter_type("R")
    assert list(tab._lignes_widgets[0]["pins"]) == ["1", "2"]
    tab._changer_type(0, "Q")
    assert list(tab._lignes_widgets[0]["pins"]) == ["B", "C", "E"]
    assert tab._modele.lignes[0].type == "Q"


def test_insertion_catalogue_ne555_libelle_les_broches(racine):
    tab = TabQuickEntry(racine)
    tab._inserer_catalogue("U", "NE555")
    ligne = tab._modele.lignes[0]
    assert ligne.value == "NE555" and len(ligne.pins) == 8
    libelles = tab._libelles_broches(0)
    assert "2 (TRIG)" in libelles and "3 (OUT)" in libelles


def test_enregistrer_produit_un_xml_relisible(racine, tmp_path):
    tab = TabQuickEntry(racine)
    tab._ajouter_type("R")
    tab._modele.lignes[0].pins.update({"1": "VIN", "2": "GND"})
    chemin = str(tmp_path / "essai.xml")
    tab._enregistrer(chemin)
    assert len(lire_xml(chemin)) == 1


def test_analyser_appelle_le_callback(racine, tmp_path, monkeypatch):
    appels = []
    tab = TabQuickEntry(racine, on_analyze=appels.append)
    tab._ajouter_type("R")
    tab._modele.lignes[0].pins.update({"1": "VIN", "2": "GND"})
    monkeypatch.setattr(tab, "_chemin_analyse",
                        lambda: str(tmp_path / "tmp.xml"))
    tab._analyser()
    assert len(appels) == 1 and appels[0].endswith(".xml")


def test_ref_dupliquee_grise_analyser(racine):
    tab = TabQuickEntry(racine)
    tab._ajouter_type("R"); tab._ajouter_type("R")
    tab._modele.lignes[1].ref = "R1"
    tab._rafraichir_validation()
    assert tab._btn_analyser.cget("state") == "disabled"


def test_analyser_sans_nom_ne_contamine_pas_le_chemin_courant(racine, tmp_path, monkeypatch):
    tab = TabQuickEntry(racine, on_analyze=lambda p: None)
    tab._ajouter_type("R")
    tab._modele.lignes[0].pins.update({"1": "VIN", "2": "GND"})
    monkeypatch.setattr(tab, "_chemin_analyse",
                        lambda: str(tmp_path / "tmp.xml"))
    tab._analyser()
    assert tab._chemin_courant is None   # le temp n'est pas devenu le fichier courant
