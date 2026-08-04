"""
@file test_gui_sync.py
@brief Tests automatises pour test_gui_sync.
"""

"""
test_gui_sync.py — Résumé exécutif et aperçu de groupes de l'onglet Analyser.
"""
from gui.tab_analyze import (
    _build_executive_summary,
    _build_group_preview,
    _find_demo_file,
)


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
