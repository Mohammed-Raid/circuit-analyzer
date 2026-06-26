"""@file test_transistor_drawing.py
@brief Dessin SIMPLE des montages transistor : symboles classiques + titre du
montage, sans boîtes Z cliquables (cf. spec 2026-06-26-transistors-schemas-simples)."""
import matplotlib
matplotlib.use("Agg")

import gui.circuit_viewer as cv


def _ci(*entries):
    return {ref: {"type": t, "value": v, "pins": pins} for ref, t, v, pins in entries}


def _render(result, ci):
    fig = cv._make_fig(result, ci, cv._DRAWERS[result["circuit_type"]])
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    return fig, txts


SUIVEUR = (
    {"circuit_type": "Collecteur commun (suiveur d'émetteur)",
     "components": ["Q1", "Re", "R1"], "nodes": ["NB", "VCC", "NOUT"]},
    _ci(("Q1", "Q", "", {"B": "NB", "C": "VCC", "E": "NOUT"}),
        ("Re", "R", "1k", {"1": "NOUT", "2": "GND"}),
        ("R1", "R", "47k", {"1": "NB", "2": "VCC"})),
)
PUSH_PULL = (
    {"circuit_type": "Étage push-pull", "components": ["Q1", "Q2"], "nodes": ["NIN", "NIN", "NOUT"]},
    _ci(("Q1", "Q", "", {"B": "NIN", "C": "VCC", "E": "NOUT"}),
        ("Q2", "Q", "", {"B": "NIN", "C": "GND", "E": "NOUT"})),
)
DARLINGTON = (
    {"circuit_type": "Paire Darlington", "components": ["Q1", "Q2", "Re"], "nodes": ["NB", "VCC", "NOUT"]},
    _ci(("Q1", "Q", "", {"B": "NB", "C": "VCC", "E": "NE1"}),
        ("Q2", "Q", "", {"B": "NE1", "C": "VCC", "E": "NOUT"}),
        ("Re", "R", "1k", {"1": "NOUT", "2": "GND"})),
)
EMETTEUR_COMMUN = (
    {"circuit_type": "Amplificateur émetteur commun",
     "components": ["Q1", "Rc", "Rb"], "nodes": ["NB", "NCOL", "GND"]},
    _ci(("Q1", "Q", "", {"B": "NB", "C": "NCOL", "E": "GND"}),
        ("Rc", "R", "1k", {"1": "VCC", "2": "NCOL"}),
        ("Rb", "R", "10k", {"1": "VCC", "2": "NB"})),
)


def test_nouveaux_drawers_transistor_enregistres():
    for ct in ("Collecteur commun (suiveur d'émetteur)", "Étage push-pull", "Paire Darlington"):
        assert ct in cv._DRAWERS


def test_montages_rendent_sans_erreur():
    for result, ci in (SUIVEUR, PUSH_PULL, DARLINGTON, EMETTEUR_COMMUN):
        _fig, txts = _render(result, ci)
        assert not any("non disponible" in t for t in txts), result["circuit_type"]


def test_aucune_boite_z_sur_transistors():
    # Schéma simple : pas de boîtes Z cliquables sur les passifs transistor.
    for result, ci in (EMETTEUR_COMMUN, SUIVEUR, DARLINGTON):
        fig, _txts = _render(result, ci)
        assert fig._z_hitboxes == [], result["circuit_type"]


def test_resistances_affichees_en_etiquette():
    # Les résistances apparaissent en symbole classique avec leur nom.
    _fig, txts = _render(*EMETTEUR_COMMUN)
    joined = " ".join(txts)
    assert "Rb" in joined and "Rc" in joined


def test_titre_role_transistor_affiche():
    _fig, txts = _render(*EMETTEUR_COMMUN)
    assert any("Émetteur commun" in t for t in txts)
