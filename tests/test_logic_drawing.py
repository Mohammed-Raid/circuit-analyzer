"""@file test_logic_drawing.py
@brief Drawers des portes CMOS (gui/logic_schematic.py) : ancres, registre
de positions (contrat puces), expression en en-tête."""
import matplotlib
matplotlib.use("Agg")
import pytest
import schemdraw

import gui.circuit_viewer as cv
from gui import logic_schematic

NAND2 = {
    "circuit_type": "Porte NAND (CMOS)",
    "components": ["M1", "M2", "M3", "M4"],
    "nodes": {"entrees": ["A", "B"], "sortie": "OUT", "vdd": "VDD", "gnd": "GND"},
    "io": {"ins": ["A", "B"], "out": "OUT"},
    "polarites": {"M1": "P", "M2": "P", "M3": "N", "M4": "N"},
    "arbres": {"pull_down": ("serie", [("feuille", "M3"), ("feuille", "M4")]),
               "pull_up": ("parallele", [("feuille", "M1"), ("feuille", "M2")])},
    "fonction": ("NAND", ["A", "B"]),
    "expression": "OUT = NAND(A, B)",
}
CI = {f"M{i}": {"type": "M", "value": "", "pins": {}} for i in range(1, 5)}


def _dessiner(match, detaille=False):
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = detaille
        res = logic_schematic.dessiner_porte(d, match, CI)
    return d, res


def test_symbole_ancres_contrat():
    _d, res = _dessiner(NAND2)
    for cle in ("in", "out", "title", "nets", "absorbed_refs"):
        assert cle in res
    # nets : chaque entrée et la sortie ont un point d'ancrage.
    for net in ("A", "B", "OUT"):
        assert net in res["nets"]


def test_symbole_enregistre_toutes_les_refs_m():
    # Contrat puces (vue simplifiée) : TOUTES les refs M pointent le symbole.
    d, _res = _dessiner(NAND2)
    for ref in NAND2["components"]:
        assert ref in d._comp_positions
    positions = {d._comp_positions[r] for r in NAND2["components"]}
    assert len(positions) == 1, "toutes les refs sur le CENTRE du symbole"


def test_drawers_enregistres_pour_les_trois_types():
    for ct in ("Inverseur (CMOS)", "Porte NAND (CMOS)", "Porte NOR (CMOS)"):
        assert ct in cv._DRAWERS


def test_expression_affichee_en_en_tete():
    # Généralisation _texte_gain : un montage porteur d'expression l'affiche.
    assert cv._texte_gain(NAND2, None) == "OUT = NAND(A, B)"
