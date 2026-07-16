"""@file test_app_window.py
@brief Contrat de la fenetre principale : 4 onglets, l'editeur remplace Saisie.
"""
import pytest

ctk = pytest.importorskip("customtkinter")

from gui.app_window import AppWindow


def test_quatre_onglets_sans_saisie():
    try:
        app = AppWindow()
    except Exception:
        pytest.skip("pas de display Tk")
    try:
        assert len(app._frames) == 4
        labels = [button._lbl.cget("text") for button in app._nav_btns]
        assert "Saisie" not in labels
    finally:
        app.root.destroy()
