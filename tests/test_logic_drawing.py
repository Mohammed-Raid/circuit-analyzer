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


def test_detaille_chaque_m_a_sa_position():
    d, res = _dessiner(NAND2, detaille=True)
    positions = [d._comp_positions[r] for r in NAND2["components"]]
    assert len(set(positions)) == 4, "en vue détaillée chaque M a SA position"
    for cle in ("in", "out", "title", "nets", "absorbed_refs"):
        assert cle in res


NOR2 = {
    "circuit_type": "Porte NOR (CMOS)",
    "components": ["M1", "M2", "M3", "M4"],
    "nodes": {"entrees": ["A", "B"], "sortie": "OUT", "vdd": "VDD", "gnd": "GND"},
    "io": {"ins": ["A", "B"], "out": "OUT"},
    "polarites": {"M1": "P", "M2": "P", "M3": "N", "M4": "N"},
    "arbres": {"pull_up": ("serie", [("feuille", "M1"), ("feuille", "M2")]),
               "pull_down": ("parallele", [("feuille", "M3"), ("feuille", "M4")])},
    "fonction": ("NOR", ["A", "B"]),
    "expression": "OUT = NOR(A, B)",
}


def _n_verticals_touchant_oy(d, ox, oy, cote):
    """Compte les fils VERTICAUX à x=ox qui touchent le niveau OUT (oy)
    depuis le bas (pull-down) ou le haut (pull-up). Sur une pile SÉRIE,
    un SEUL transistor (le bout) doit toucher oy ; >1 = nœud interne shunté
    vers OUT (court-circuit invisible car les fils fusionnent à x=ox)."""
    import schemdraw.elements as elm
    n = 0
    for e in d.elements:
        if not isinstance(e, elm.Line):
            continue
        (x1, y1), (x2, y2) = tuple(e.start), tuple(e.end)
        if round(x1, 2) != round(ox, 2) or round(x2, 2) != round(ox, 2):
            continue
        lo, hi = sorted((round(y1, 2), round(y2, 2)))
        if cote == "bas" and hi == round(oy, 2) and lo < round(oy, 2):
            n += 1
        if cote == "haut" and lo == round(oy, 2) and hi > round(oy, 2):
            n += 1
    return n


def test_detaille_pile_serie_pas_de_court_circuit_out_rail():
    # Bug électrique Critical : sur une pile série, chaque nœud interne était
    # câblé vers OUT ET vers le rail → OUT court-circuité au rail. Invisible à
    # l'œil (fils colinéaires à x=ox). Invariant : UN SEUL transistor de la
    # pile touche le niveau OUT.
    ox, oy = 3, 0
    d_nand, _ = _dessiner(NAND2, detaille=True)    # pull-down NMOS série
    assert _n_verticals_touchant_oy(d_nand, ox, oy, "bas") == 1
    d_nor, _ = _dessiner(NOR2, detaille=True)       # pull-up PMOS série
    assert _n_verticals_touchant_oy(d_nor, ox, oy, "haut") == 1


def test_dessin_invariant_a_la_direction_du_stylo():
    # Bug D4 (audit visuel) : schemdraw fait heriter la direction COURANTE du
    # dessin a tout element sans orientation explicite. En chaine/DAG le routeur
    # laisse le stylo vertical -> FET/porte pivotes de 90 degres (VDD flottant,
    # fils a travers les transistors). Invariant : apres un fil .up(), le dessin
    # d'une porte est IDENTIQUE (a translation pres) au dessin sur toile vierge.
    import schemdraw.elements as elm

    def _fets(d):
        return [e for e in d.elements if hasattr(e, "gate") and hasattr(e, "drain")]

    for detaille in (False, True):
        with schemdraw.Drawing(show=False) as d:
            d._comp_positions = {}
            d._z_hitboxes = []
            d._mode_detaille = detaille
            d.add(elm.Line().at((0, 0)).up(2))     # stylo laisse VERTICAL
            logic_schematic.dessiner_porte(d, NAND2, CI)
        if detaille:
            for f in _fets(d):
                assert f.gate[0] < f.drain[0] and f.gate[0] < f.source[0], \
                    "FET pivote par la direction heritee du stylo"
        else:
            porte = next(e for e in d.elements if hasattr(e, "anchors")
                         and "out" in getattr(e, "anchors", {}))
            assert porte.out[0] > porte.in1[0], \
                "symbole de porte pivote par la direction heritee du stylo"


def test_detaille_fets_grille_a_gauche():
    # Piège NFet/PFet schemdraw 0.22 : grille à DROITE par défaut → .reverse().
    # Garde : les x des grilles sont STRICTEMENT à gauche des x drain/source.
    import schemdraw
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = True
        from gui import logic_schematic
        elems_avant = len(d.elements)
        logic_schematic.dessiner_porte(d, NAND2, CI)
        fets = [e for e in d.elements[elems_avant:]
                if hasattr(e, "gate") and hasattr(e, "drain")]
    assert len(fets) == 4
    for f in fets:
        assert f.gate[0] < f.drain[0] and f.gate[0] < f.source[0]
