"""@file test_show_circuit_popup.py
@brief Bouton de suppression d'un circuit personnalise dans la popup de
schema (spec 2026-08-04). Tk -> skip sans display.
"""
import pytest

ctk = pytest.importorskip("customtkinter")


@pytest.fixture
def ctk_root():
    import tkinter as tk
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("pas d'affichage Tk disponible")
    root.withdraw()
    yield root
    root.destroy()


def _custom_circuits(monkeypatch, tmp_path, circuits):
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)
    loader.save_custom_circuits(circuits)
    return chemin


def _boutons_de_la_barre_du_bas(popup):
    """@brief Widgets-boutons de la barre du bas de la popup show_circuit.

    La barre du bas est un CTkFrame direct enfant de `popup`, contenant les
    boutons en enfants directs (pas de nesting supplementaire, cf.
    `show_circuit`) : une recherche a 2 niveaux suffit, plus robuste qu'une
    recursion non bornee sur tout l'arbre de widgets.
    """
    boutons = []
    for cadre in popup.winfo_children():
        for w in cadre.winfo_children():
            if hasattr(w, "cget"):
                try:
                    w.cget("text")
                except Exception:
                    continue
                boutons.append(w)
    return boutons


def _textes_des_boutons_de_la_barre_du_bas(popup):
    return [w.cget("text") for w in _boutons_de_la_barre_du_bas(popup)]


def _bouton_supprimer(popup):
    """@brief Le widget bouton "Supprimer" de la barre du bas, ou None."""
    for w in _boutons_de_la_barre_du_bas(popup):
        if "Supprimer" in w.cget("text"):
            return w
    return None


def test_bouton_supprimer_visible_pour_un_circuit_personnalise(
        ctk_root, monkeypatch, tmp_path):
    _custom_circuits(monkeypatch, tmp_path,
                     [{"name": "Mon montage", "components": ["R"],
                       "conditions": []}])
    from gui import circuit_viewer as cv
    result = {"circuit_type": "Mon montage", "components": ["R1"],
              "nodes": ["A", "B"]}
    cv.show_circuit(result, {"R1": {"type": "R", "value": "10k"}},
                    parent=ctk_root)
    popup = ctk_root.winfo_children()[-1]
    assert any("Supprimer" in t
              for t in _textes_des_boutons_de_la_barre_du_bas(popup))


def test_bouton_supprimer_absent_pour_un_circuit_integre(
        ctk_root, monkeypatch, tmp_path):
    _custom_circuits(monkeypatch, tmp_path, [])
    from gui import circuit_viewer as cv
    result = {"circuit_type": "Suiveur de tension (AOP)",
              "components": ["U1"], "nodes": ["A", "B"]}
    cv.show_circuit(result, {"U1": {"type": "U", "value": ""}},
                    parent=ctk_root)
    popup = ctk_root.winfo_children()[-1]
    assert not any("Supprimer" in t
                  for t in _textes_des_boutons_de_la_barre_du_bas(popup))


def test_supprimer_retire_le_circuit_du_fichier(
        ctk_root, monkeypatch, tmp_path):
    from tkinter import messagebox
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    _custom_circuits(monkeypatch, tmp_path,
                     [{"name": "Mon montage", "components": ["R"],
                       "conditions": []},
                      {"name": "Autre", "components": ["C"],
                       "conditions": []}])
    from gui import circuit_viewer as cv
    result = {"circuit_type": "Mon montage", "components": ["R1"],
              "nodes": ["A", "B"]}
    cv.show_circuit(result, {"R1": {"type": "R", "value": "10k"}},
                    parent=ctk_root)

    from custom_circuits.loader import load_custom_circuits
    cv._supprimer_circuit_personnalise("Mon montage")
    noms = [c["name"] for c in load_custom_circuits()]
    assert noms == ["Autre"]


def test_invoquer_le_bouton_supprimer_avec_confirmation_oui_supprime(
        ctk_root, monkeypatch, tmp_path):
    """Contrairement a test_supprimer_retire_le_circuit_du_fichier, ce test
    passe par le VRAI widget bouton (.invoke()) au lieu d'appeler
    _supprimer_circuit_personnalise directement : un bouton mal cable (ou pas
    cable du tout) passerait quand meme les tests qui appellent la fonction
    a la main."""
    from tkinter import messagebox
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    _custom_circuits(monkeypatch, tmp_path,
                     [{"name": "Mon montage", "components": ["R"],
                       "conditions": []},
                      {"name": "Autre", "components": ["C"],
                       "conditions": []}])
    from gui import circuit_viewer as cv
    result = {"circuit_type": "Mon montage", "components": ["R1"],
              "nodes": ["A", "B"]}
    cv.show_circuit(result, {"R1": {"type": "R", "value": "10k"}},
                    parent=ctk_root)
    popup = ctk_root.winfo_children()[-1]

    bouton = _bouton_supprimer(popup)
    assert bouton is not None, "bouton Supprimer introuvable dans la barre du bas"
    bouton.invoke()

    from custom_circuits.loader import load_custom_circuits
    noms = [c["name"] for c in load_custom_circuits()]
    assert noms == ["Autre"]


def test_invoquer_le_bouton_supprimer_avec_confirmation_non_ne_supprime_pas(
        ctk_root, monkeypatch, tmp_path):
    """Chemin "Non" de la confirmation (jusqu'ici non couvert) : le clic sur
    Supprimer ouvre bien la confirmation, mais un refus ne doit rien retirer
    de custom_circuits.json."""
    from tkinter import messagebox
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
    _custom_circuits(monkeypatch, tmp_path,
                     [{"name": "Mon montage", "components": ["R"],
                       "conditions": []},
                      {"name": "Autre", "components": ["C"],
                       "conditions": []}])
    from gui import circuit_viewer as cv
    result = {"circuit_type": "Mon montage", "components": ["R1"],
              "nodes": ["A", "B"]}
    cv.show_circuit(result, {"R1": {"type": "R", "value": "10k"}},
                    parent=ctk_root)
    popup = ctk_root.winfo_children()[-1]

    bouton = _bouton_supprimer(popup)
    assert bouton is not None, "bouton Supprimer introuvable dans la barre du bas"
    bouton.invoke()

    from custom_circuits.loader import load_custom_circuits
    noms = [c["name"] for c in load_custom_circuits()]
    assert noms == ["Mon montage", "Autre"]
