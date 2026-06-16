"""
@file test_gui_sync.py
@brief Tests automatises pour test_gui_sync.
"""

"""
test_gui_sync.py — Synchronisation entre les onglets Composants et Circuits.

Les deux onglets partagent la bibliothèque component_library.json. Quand on
crée, modifie ou supprime un composant dans l'onglet Composants, l'onglet
Circuits (qui propose ces composants dans « Composants requis ») doit se mettre
à jour. Test d'intégration léger sur un vrai root Tk (sauté sans affichage).
"""
import pytest

from gui.tab_analyze import (
    _build_executive_summary,
    _build_group_preview,
    _find_demo_file,
)


@pytest.fixture
def ctk_root():
    """@brief Helper de test pour ctk root."""
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
    """@brief Helper de test pour bibliotheque temporaire."""
    """Redirige la bibliothèque vers un fichier temporaire pour les deux onglets."""
    chemin = tmp_path / "component_library.json"
    chemin.write_text("{}", encoding="utf-8")
    import circuit_analyzer.composant as composant
    import gui.tab_components as tab_components
    monkeypatch.setattr(composant, "chemin_bibliotheque", lambda: chemin)
    monkeypatch.setattr(tab_components, "chemin_bibliotheque", lambda: chemin)
    return chemin


def test_executive_summary_highlights_detected_circuits():
    """@brief Vérifie le résumé exécutif pour une analyse avec circuits détectés.

    @return None
    """
    results = [
        {
            "circuit_type": "Commande de relais",
            "components": ["K1", "Q1"],
            "satellites": [{"ref": "D1", "status": "possible"}],
            "warnings": ["validation ingénieur nécessaire"],
        },
        {
            "circuit_type": "Protection par fusible",
            "components": ["F1"],
            "satellites": [],
        },
    ]

    summary = _build_executive_summary(
        results,
        total=5,
        classified_count=3,
        unclassified=["R1"],
    )

    assert summary["headline"] == "Analyse terminée : 5 composants analysés, 2 circuits reconnus."
    assert summary["classification"] == "3 composants classés (60%)."
    assert "commutation" in summary["reading"].lower()
    assert "protection" in summary["reading"].lower()
    assert summary["review"] == "3 points nécessitent une vérification ingénieur."


def test_executive_summary_handles_no_detection():
    """@brief Vérifie le résumé exécutif quand aucun circuit n'est reconnu.

    @return None
    """
    summary = _build_executive_summary(
        [],
        total=4,
        classified_count=0,
        unclassified=["R1", "C1", "D1", "X1"],
    )

    assert summary["headline"] == "Analyse terminée : 4 composants analysés, aucun circuit reconnu."
    assert summary["classification"] == "0 composant classé (0%)."
    assert summary["reading"] == "Le schéma ne correspond pas encore aux patterns intégrés."
    assert summary["review"] == "4 composants restent non classifiés."


def test_find_demo_file_picks_random_xml(tmp_path):
    """@brief Vérifie que _find_demo_file retourne un XML du dossier circuits_industriels.

    @return None
    """
    ci = tmp_path / "circuits_industriels"
    ci.mkdir()
    fichiers = ["relay_driver.xml", "pid_controller.xml", "buck_converter.xml"]
    for nom in fichiers:
        (ci / nom).write_text("<BoardSCH />", encoding="utf-8")

    result = _find_demo_file(tmp_path)
    assert result in [str(ci / nom) for nom in fichiers]


def test_build_group_preview_keeps_circuit_and_satellite_refs():
    """@brief Vérifie les données de l'aperçu des groupes.

    @return None
    """
    preview = _build_group_preview([
        {
            "circuit_type": "Commande de relais",
            "components": ["K1", "Q1"],
            "satellites": [{"ref": "D1", "status": "sure"}],
            "confidence": 0.92,
        },
        {
            "circuit_type": "Pont diviseur de tension",
            "components": ["R1", "R2"],
            "confidence": 0.75,
        },
    ])

    assert preview[0]["title"] == "Commande de relais"
    assert preview[0]["refs"] == ["K1", "Q1", "D1"]
    assert preview[0]["category"] == "TRANSISTORS & COMMUTATION"
    assert preview[0]["confidence"] == "92%"
    assert preview[1]["confidence"] == "75%"


def test_suppression_composant_retiree_de_l_onglet_circuits(
        ctk_root, monkeypatch, tmp_path):
    """@brief Verifie suppression composant retiree de l onglet circuits.

    @return None
    """
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
