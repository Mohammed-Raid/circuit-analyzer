"""@file test_app_window.py
@brief Contrat de la fenetre principale : 3 onglets, l'editeur remplace Saisie,
       l'onglet Circuits est retire (redondant avec le wizard de pattern).
"""
import pytest

ctk = pytest.importorskip("customtkinter")

from gui.app_window import AppWindow


def test_trois_onglets_sans_saisie_ni_circuits():
    try:
        app = AppWindow()
    except Exception:
        pytest.skip("pas de display Tk")
    try:
        assert len(app._frames) == 3
        labels = [button._lbl.cget("text") for button in app._nav_btns]
        assert "Saisie" not in labels
        assert "Circuits" not in labels
    finally:
        app.root.destroy()
