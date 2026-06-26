"""@file test_transistor_drawing.py
@brief Dessin SIMPLE des montages transistor : symboles classiques + titre du
montage, sans boîtes Z cliquables (cf. spec 2026-06-26-transistors-schemas-simples)."""
import matplotlib
matplotlib.use("Agg")

import schemdraw

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
BJT_SWITCH = (
    {"circuit_type": "Transistor en commutation",
     "components": ["Q1", "Rb", "L1"], "nodes": ["NB", "NL", "GND"]},
    _ci(("Q1", "Q", "", {"B": "NB", "C": "NL", "E": "GND"}),
        ("Rb", "R", "10k", {"1": "NIN", "2": "NB"}),
        ("L1", "L", "10mH", {"1": "VCC", "2": "NL"})),
)


def test_nouveaux_drawers_transistor_enregistres():
    for ct in ("Collecteur commun (suiveur d'émetteur)", "Étage push-pull", "Paire Darlington"):
        assert ct in cv._DRAWERS


def test_montages_rendent_sans_erreur():
    for result, ci in (SUIVEUR, PUSH_PULL, DARLINGTON, EMETTEUR_COMMUN, BJT_SWITCH):
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


def test_bjt_commutation_affiche_charge_inductive():
    _fig, txts = _render(*BJT_SWITCH)
    assert any("L1" in t for t in txts)


def test_titre_role_transistor_affiche():
    _fig, txts = _render(*EMETTEUR_COMMUN)
    assert any("Émetteur commun" in t for t in txts)


def _ancres(drawer, result, ci, origin):
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        return drawer(d, result, ci, origin=origin, titre=False)


def test_drawer_ce_renvoie_ancres_in_out():
    res = _ancres(cv._draw_common_emitter, *EMETTEUR_COMMUN, origin=(0, 0))
    assert "in" in res and "out" in res
    assert res["out"][0] > res["in"][0]


def test_drawer_ce_origine_decale_le_dessin():
    a = _ancres(cv._draw_common_emitter, *EMETTEUR_COMMUN, origin=(0, 0))
    b = _ancres(cv._draw_common_emitter, *EMETTEUR_COMMUN, origin=(10, 0))
    assert round(b["in"][0] - a["in"][0], 3) == 10.0


def test_drawer_titre_false_pas_de_titre():
    fig = cv.Figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._z_hitboxes = []
        cv._draw_common_emitter(d, *EMETTEUR_COMMUN, origin=(0, 0), titre=False)
    direct = [t.get_text() for t in ax.texts]
    assert not any("Émetteur commun" in t for t in direct)

    standalone = [t.get_text()
                  for ax in cv._make_fig(EMETTEUR_COMMUN[0], EMETTEUR_COMMUN[1],
                                         cv._draw_common_emitter).axes
                  for t in ax.texts]
    assert any("Émetteur commun" in t for t in standalone)


def test_commande_relais_affiche_rb_satellite():
    result = {"circuit_type": "Commande de relais",
              "components": ["K1", "Q1"], "nodes": ["VCC", "NCOIL"]}
    ci = _ci(("Q1", "Q", "", {"B": "NB", "C": "NCOIL", "E": "GND"}),
             ("K1", "K", "", {"A1": "VCC", "A2": "NCOIL"}),
             ("Rb", "R", "10k", {"1": "NIN", "2": "NB"}))
    _fig, txts = _render(result, ci)
    assert any("Rb" in t for t in txts)
