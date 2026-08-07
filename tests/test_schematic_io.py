"""
@file test_schematic_io.py
@brief Tests de la sérialisation .circ et de l'import netlist/XML dans l'éditeur.
"""
from dataclasses import dataclass

import pytest

from gui.schematic_editor import COMP_DEFS
from gui.schematic_io import (
    build_from_components,
    editor_to_dict,
    points_jonction,
    type_reel,
)

# ── Doubles légers pour Composant (ref, type, pins, value) ────────────────────

@dataclass
class _Comp:
    ref: str
    type: str
    pins: dict
    value: str = ""
    primitives: list | None = None
    pinout: dict | None = None


# ── build_from_components ─────────────────────────────────────────────────────

def test_import_noeud_signal_relie_les_broches():
    """Deux composants sur le même nœud signal → un fil de chaîne."""
    composants = [
        _Comp("R1", "R", {"1": "N1", "2": "GND"}, "10k"),
        _Comp("C1", "C", {"1": "N1", "2": "GND"}, "100n"),
    ]
    doc = build_from_components(composants, COMP_DEFS)

    # 2 composants réels + 2 symboles GND (un par broche sur la masse)
    gnd = [c for c in doc["components"] if c["type"] == "GND"]
    assert len(gnd) == 2
    assert doc["_report"]["dropped_pins"] == 0
    assert doc["_report"]["ignored_components"] == []

    # Le nœud N1 relie R1.1 et C1.1 (un fil entre deux composants non-rail).
    ids_reels = {c["id"] for c in doc["components"] if c["type"] != "GND"}
    fils_signal = [w for w in doc["wires"]
                   if w["from_comp_id"] in ids_reels and w["to_comp_id"] in ids_reels]
    assert len(fils_signal) == 1


def test_import_broche_inconnue_est_comptee():
    """Les broches V+/V- d'un AOP (absentes de l'éditeur) sont ignorées."""
    composants = [
        _Comp("U1", "U",
              {"IN+": "A", "IN-": "B", "OUT": "O", "V+": "VCC", "V-": "GND"}),
    ]
    doc = build_from_components(composants, COMP_DEFS)
    assert doc["_report"]["dropped_pins"] == 2          # V+ et V-


def test_build_garde_le_brochage_reel_dune_puce_catch_all():
    """Meme scenario que test_import_broche_inconnue_est_comptee, mais avec
    un brochage reel : les broches ne doivent plus etre droppees."""
    comp = _Comp("U1", "U",
                 {"Vin+": "N1", "Vin-": "N2", "GND1": "GND"}, "",
                 primitives=[("polygon", [(-36, -48), (-36, 48), (36, 48), (36, -48)], False)],
                 pinout={"Vin+": ("L", -42), "Vin-": ("L", -6), "GND1": ("L", 42)})
    doc = build_from_components([comp], COMP_DEFS)
    c = doc["components"][0]
    assert c["type"] == "U"
    assert c["forme_primitives"] == comp.primitives
    assert c["pinout"] == {"Vin+": ["L", -42], "Vin-": ["L", -6], "GND1": ["L", 42]}
    assert doc["_report"]["dropped_pins"] == 0


def test_build_sans_brochage_reel_comportement_inchange():
    """Non-regression explicite : test_import_broche_inconnue_est_comptee
    doit encore dropper V+/V- quand AUCUN brochage reel n'est fourni."""
    comp = _Comp("U1", "U",
                 {"IN+": "A", "IN-": "B", "OUT": "O", "V+": "VCC", "V-": "GND"})
    doc = build_from_components([comp], COMP_DEFS)
    assert doc["_report"]["dropped_pins"] == 2
    assert "forme_primitives" not in doc["components"][0]
    assert "pinout" not in doc["components"][0]


def test_import_type_inconnu_est_ignore():
    """Un composant d'un type absent de l'éditeur est ignoré et signalé."""
    composants = [_Comp("Z1", "Z", {"1": "A", "2": "B"})]
    doc = build_from_components(composants, COMP_DEFS)
    assert doc["_report"]["ignored_components"] == ["Z1"]
    assert doc["components"] == []


def test_editor_to_dict_forme():
    """editor_to_dict produit la structure .circ attendue."""
    @dataclass
    class _CI:
        id: int
        ref: str
        comp_type: str
        value: str
        cx: int
        cy: int
        rotation: int = 0

    @dataclass
    class _WI:
        id: int
        from_comp_id: int
        from_pin: str
        to_comp_id: int
        to_pin: str

    comps = {1: _CI(1, "R1", "R", "10k", 100, 100)}
    wires = [_WI(2, 1, "2", 1, "1")]
    d = editor_to_dict(comps, wires, {"R": 1}, 3)
    assert d["format"] == "circ" and d["version"] == 1
    assert d["components"][0]["ref"] == "R1"
    assert d["wires"][0]["from_pin"] == "2"
    assert d["next_id"] == 3


# ── type_reel / points_jonction (Task 2) ──────────────────────────────────────

def _mk_comp(id_, t, cx, cy):
    from gui.schematic_editor import CompInst
    return CompInst(id=id_, ref=f"{t}{id_}", comp_type=t, value="",
                    cx=cx, cy=cy)


def _mk_wire(i, a, pa, b, pb):
    from gui.schematic_editor import WireInst
    return WireInst(id=i, from_comp_id=a, from_pin=pa,
                    to_comp_id=b, to_pin=pb)


DEFS = {"R": {"w": 80, "h": 40, "pins": {"1": (-40, 0), "2": (40, 0)}}}


def _geom(comp):
    """Résolveur de géométrie attendu par `points_jonction` (spec 2026-07-23) :
    une fonction, pas un dict — deux instances d'un même type peuvent avoir des
    brochages différents."""
    return DEFS[comp.comp_type]


def test_type_reel():
    assert type_reel("U::NE555") == ("U", "NE555")
    assert type_reel("R") == ("R", "")


def test_points_jonction_trois_fils():
    # R1.2, R2.1, R3.1 au même point monde (200,100) -> 1 jonction.
    comps = {1: _mk_comp(1, "R", 160, 100), 2: _mk_comp(2, "R", 240, 100),
             3: _mk_comp(3, "R", 240, 180)}
    # NB : rotation 0 partout ; on fait CONVERGER les fils sur la broche 2
    # de R1 (200,100).
    wires = [_mk_wire(1, 1, "2", 2, "1"),
             _mk_wire(2, 1, "2", 3, "1"),
             _mk_wire(3, 2, "1", 3, "1")]
    pts = points_jonction(comps, wires, _geom)
    assert (200, 100) in pts    # >= 3 extrémités de fils y coïncident


def test_points_jonction_deux_fils_aucune():
    comps = {1: _mk_comp(1, "R", 160, 100), 2: _mk_comp(2, "R", 240, 100)}
    wires = [_mk_wire(1, 1, "2", 2, "1")]
    assert points_jonction(comps, wires, _geom) == []


# ── load_dict / to_netlist (nécessitent un root Tk) ───────────────────────────

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


def test_roundtrip_to_dict_load_dict(ctk_root):
    """Dessiner → to_dict → load_dict dans un nouvel éditeur reconstruit tout."""
    from gui.schematic_editor import SchematicEditor

    ed = SchematicEditor(ctk_root)
    ed._start_placing("R")
    ed._place_comp(100, 100)
    ed._start_placing("C")
    ed._place_comp(300, 100)
    ids = list(ed._comps.keys())
    ed._wire_src = (ids[0], "2")
    ed._complete_wire((ids[1], "1"))

    d = ed.to_dict()

    ed2 = SchematicEditor(ctk_root)
    ed2.load_dict(d)
    assert ed2.comp_count() == ed.comp_count() == 2
    assert len(ed2._wires) == len(ed._wires) == 1


def test_to_netlist_separe_type_reel_u_ref(ctk_root):
    """Un comp_type "U::NE555" exporte sa référence catalogue comme value."""
    from gui.schematic_editor import CompInst, SchematicEditor

    ed = SchematicEditor(ctk_root)
    # Enregistre une def catalogue "U::NE555" (comme le fera la palette Task 5)
    # et injecte l'instance directement — pas de dépendance au placement.
    ed._defs["U::NE555"] = {"label": "NE555", "color": "#888888",
                            "w": 80, "h": 40, "pins": {"1": (-40, 0)},
                            "default_value": ""}
    ed._comps[1] = CompInst(id=1, ref="U1", comp_type="U::NE555", value="",
                            cx=100, cy=100)
    lignes = [l for l in ed.to_netlist().splitlines() if l.startswith("U1 ")]
    assert len(lignes) == 1
    assert lignes[0].endswith(" NE555")     # value exportée = partie après ::


def test_load_dict_rejette_format_inconnu(ctk_root):
    """Un dict sans le bon format lève ValueError sans toucher au dessin."""
    from gui.schematic_editor import SchematicEditor

    ed = SchematicEditor(ctk_root)
    with pytest.raises(ValueError):
        ed.load_dict({"foo": "bar"})
    with pytest.raises(ValueError):
        ed.load_dict({"format": "circ", "version": 99})
