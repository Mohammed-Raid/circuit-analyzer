"""
test_gui_sync.py — Synchronisation entre les onglets Composants et Circuits.

Les deux onglets partagent la bibliothèque component_library.json. Quand on
crée, modifie ou supprime un composant dans l'onglet Composants, l'onglet
Circuits (qui propose ces composants dans « Composants requis ») doit se mettre
à jour. Test d'intégration léger sur un vrai root Tk (sauté sans affichage).
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


def _bibliotheque_temporaire(monkeypatch, tmp_path):
    """Redirige la bibliothèque vers un fichier temporaire pour les deux onglets."""
    chemin = tmp_path / "component_library.json"
    chemin.write_text("{}", encoding="utf-8")
    import circuit_analyzer.composant as composant
    import gui.tab_components as tab_components
    monkeypatch.setattr(composant, "chemin_bibliotheque", lambda: chemin)
    monkeypatch.setattr(tab_components, "chemin_bibliotheque", lambda: chemin)
    return chemin


def test_suppression_composant_retiree_de_l_onglet_circuits(
        ctk_root, monkeypatch, tmp_path):
    _bibliotheque_temporaire(monkeypatch, tmp_path)
    from gui.tab_components import TabComponents
    from gui.tab_circuits import TabCircuits
    from tkinter import messagebox

    # Pas de boîtes de dialogue bloquantes pendant le test
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: None)

    tab_c = TabCircuits(ctk_root)
    tab_p = TabComponents(ctk_root, on_save=tab_c.refresh_component_list)

    # 1) Créer un composant personnalisé 'X'
    tab_p._prefix_var.set("X")
    tab_p._name_var.set("Test")
    tab_p._pin_lignes[0][0].set("1")
    tab_p._sauvegarder()
    assert "X" in tab_c._comp_vars, \
        "le composant créé devrait apparaître dans l'onglet Circuits"

    # 2) Le supprimer (il est en mode édition juste après la sauvegarde)
    tab_p._supprimer()

    # 3) Il ne doit plus être proposé dans l'onglet Circuits
    assert "X" not in tab_c._comp_vars, \
        "le composant supprimé ne doit plus apparaître dans l'onglet Circuits"
