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
# Broches G reelles (NAND2 et NOR2 partagent le mapping M1/M3->A, M2/M4->B) :
# sans elles grille_de est vide et la fan-in n'est jamais dessinee (tests vides).
CI = {f"M{i}": {"type": "M", "value": "", "pins": {"G": g}}
      for i, g in [(1, "A"), (2, "B"), (3, "A"), (4, "B")]}


def _dessiner(match, detaille=False, ci=None):
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = detaille
        res = logic_schematic.dessiner_porte(d, match, ci or CI)
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


NAND3 = {
    "circuit_type": "Porte NAND (CMOS)",
    "components": ["M1", "M2", "M3", "M4", "M5", "M6"],
    "nodes": {"entrees": ["A", "B", "C"], "sortie": "OUT",
              "vdd": "VDD", "gnd": "GND"},
    "io": {"ins": ["A", "B", "C"], "out": "OUT"},
    "polarites": {"M1": "P", "M2": "P", "M3": "P",
                  "M4": "N", "M5": "N", "M6": "N"},
    "arbres": {"pull_down": ("serie", [("feuille", "M4"), ("feuille", "M5"),
                                       ("feuille", "M6")]),
               "pull_up": ("parallele", [("feuille", "M1"), ("feuille", "M2"),
                                         ("feuille", "M3")])},
    "fonction": ("NAND", ["A", "B", "C"]),
    "expression": "OUT = NAND(A, B, C)",
}
CI3 = {f"M{i}": {"type": "M", "value": "",
                 "pins": {"G": g}} for i, g in
       [(1, "A"), (2, "B"), (3, "C"), (4, "A"), (5, "B"), (6, "C")]}


def _segments_horizontaux(d):
    import schemdraw.elements as elm
    segs = []
    for e in d.elements:
        if not isinstance(e, elm.Line):
            continue
        (x1, y1), (x2, y2) = tuple(e.start), tuple(e.end)
        if abs(y1 - y2) < 1e-6 and abs(x1 - x2) > 1e-6:
            segs.append((min(x1, x2), max(x1, x2), y1))
    return segs


def _corps_fets(d):
    """Boites englobantes (approx) des CORPS de transistors poses."""
    corps = []
    for e in d.elements:
        if hasattr(e, "gate") and hasattr(e, "drain"):
            cx = (e.drain[0] + e.source[0]) / 2.0
            cy = (e.drain[1] + e.source[1]) / 2.0
            corps.append((cx - 0.55, cx + 0.55, cy - 0.65, cy + 0.65))
    return corps


@pytest.mark.parametrize("match,ci", [(NAND2, CI), (NOR2, CI), (NAND3, CI3)],
                         ids=["nand2", "nor2", "nand3"])
def test_detaille_fan_in_ne_traverse_aucun_corps(match, ci):
    # Bug D5 (audit visuel) : les taps de grille multi-entrees couraient a
    # gy +/- 0.13 -> EN PLEIN dans les corps des transistors a gauche de leur
    # cible. Invariant : aucun fil horizontal ne traverse l'interieur d'un corps.
    d, _ = _dessiner(match, detaille=True, ci=ci)
    for x1, x2, y in _segments_horizontaux(d):
        for bx1, bx2, by1, by2 in _corps_fets(d):
            traverse = x1 < bx1 and x2 > bx2 and by1 < y < by2
            assert not traverse, \
                f"fil horizontal y={y:.2f} [{x1:.2f},{x2:.2f}] traverse un corps " \
                f"[{bx1:.2f},{bx2:.2f}]x[{by1:.2f},{by2:.2f}]"


@pytest.mark.parametrize("match,ci", [(NAND2, CI), (NOR2, CI), (NAND3, CI3)],
                         ids=["nand2", "nor2", "nand3"])
def test_detaille_fan_in_jamais_quasi_colineaire(match, ci):
    # Bug D5 (suite) : deux taps d'entrees differentes a 0.26 l'un de l'autre
    # avec recouvrement en x = illisible (quelle entree pilote quelle grille ?).
    # Invariant : deux segments horizontaux qui se recouvrent en x sont soit
    # confondus (meme fil), soit separes d'au moins 0.3 en y.
    d, _ = _dessiner(match, detaille=True, ci=ci)
    segs = _segments_horizontaux(d)
    for i, (a1, a2, ya) in enumerate(segs):
        for b1, b2, yb in segs[i + 1:]:
            recouvre = min(a2, b2) - max(a1, b1) > 0.15
            if recouvre and abs(ya - yb) > 1e-6:
                assert abs(ya - yb) >= 0.3, \
                    f"taps quasi-colineaires : y={ya:.2f} et y={yb:.2f} " \
                    f"se recouvrent sur x [{max(a1, b1):.2f},{min(a2, b2):.2f}]"


def _textes_rendus(match, ci, detaille, in_label, out_label):
    from matplotlib.figure import Figure
    fig = Figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.axis("off")
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = detaille
        logic_schematic.dessiner_porte(d, match, ci, titre=False,
                                       in_label=in_label, out_label=out_label)
    return [t.get_text() for t in ax.texts]


@pytest.mark.parametrize("detaille", [False, True], ids=["z", "detaille"])
def test_chaine_multi_entrees_jamais_le_meme_label_partout(detaille):
    # Bug D2 (audit visuel) : la chaine passe in_label='VIN' au 1er montage et
    # le drawer l'appliquait a CHAQUE entree -> 'VIN' sur les 2 entrees de la
    # NAND (nets distincts !). Multi-entrees = toujours les vrais noms de nets.
    textes = _textes_rendus(NAND2, CI, detaille, in_label="VIN", out_label="")
    assert textes.count("VIN") == 0, f"in_label applique en masse : {textes}"
    assert "A" in textes and "B" in textes


@pytest.mark.parametrize("detaille", [False, True], ids=["z", "detaille"])
def test_chaine_label_vide_masque_vraiment(detaille):
    # Bug D3 (audit visuel) : in/out_label='' (= masquer, convention des fils
    # internes de chaine) etait ressuscite par `or net` -> 'NET2' aux DEUX
    # bouts du meme fil. '' explicite = aucun texte pour ce net.
    nand = _textes_rendus(NAND2, CI, detaille, in_label=None, out_label="")
    assert "OUT" not in nand, f"out_label='' doit masquer la sortie : {nand}"
    not_ = _textes_rendus(NOT1, CI_NOT, detaille, in_label="", out_label="")
    assert "A" not in not_ and "OUT" not in not_, \
        f"labels '' doivent masquer entree et sortie : {not_}"


NOT1 = {
    "circuit_type": "Inverseur (CMOS)",
    "components": ["M1", "M2"],
    "nodes": {"entrees": ["A"], "sortie": "OUT", "vdd": "VDD", "gnd": "GND"},
    "io": {"ins": ["A"], "out": "OUT"},
    "polarites": {"M1": "P", "M2": "N"},
    "arbres": {"pull_up": ("feuille", "M1"), "pull_down": ("feuille", "M2")},
    "fonction": ("NOT", ["A"]),
    "expression": "OUT = NOT(A)",
}
CI_NOT = {"M1": {"type": "M", "value": "", "pins": {"G": "A"}},
          "M2": {"type": "M", "value": "", "pins": {"G": "A"}}}


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
