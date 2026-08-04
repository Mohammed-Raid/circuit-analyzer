"""
@file test_pattern_refresh.py
@brief Régression : un pattern créé depuis l'éditeur apparaît aussitôt dans
       l'onglet Circuits (et n'attend pas un redémarrage).
"""
import pytest


@pytest.fixture
def ctk_root():
    ctk = pytest.importorskip("customtkinter")
    import tkinter as tk
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("pas d'affichage Tk disponible")
    root.withdraw()
    yield root
    root.destroy()


def test_pattern_cree_apparait_dans_circuits(ctk_root, monkeypatch, tmp_path):
    """Sauvegarder un pattern via le loader puis refresh_circuits le fait apparaître."""
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)

    from custom_circuits.loader import save_custom_circuits
    from gui.tab_circuits import TabCircuits

    tab_c = TabCircuits(ctk_root)
    # Aucun personnalisé au départ
    assert tab_c._custom == []

    # Un autre onglet crée un pattern (écrit le fichier) sans passer par tab_c
    save_custom_circuits([{"name": "Mon test", "components": ["R"], "conditions": []}])

    # Sans refresh, la liste en mémoire est encore vide (le bug)
    assert tab_c._custom == []

    # Le callback de création déclenche le rechargement
    tab_c.refresh_circuits()
    assert [c["name"] for c in tab_c._custom] == ["Mon test"]
