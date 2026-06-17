"""
@file test_schematic_io.py
@brief Tests de la sérialisation .circ et de l'import netlist/XML dans l'éditeur.
"""
import pytest

from dataclasses import dataclass

from gui.schematic_io import editor_to_dict, build_from_components
from gui.schematic_editor import COMP_DEFS


# ── Doubles légers pour Composant (ref, type, pins, value) ────────────────────

@dataclass
class _Comp:
    ref: str
    type: str
    pins: dict
    value: str = ""


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


# ── load_dict (nécessite un root Tk) ──────────────────────────────────────────

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


def test_load_dict_rejette_format_inconnu(ctk_root):
    """Un dict sans le bon format lève ValueError sans toucher au dessin."""
    from gui.schematic_editor import SchematicEditor

    ed = SchematicEditor(ctk_root)
    with pytest.raises(ValueError):
        ed.load_dict({"foo": "bar"})
    with pytest.raises(ValueError):
        ed.load_dict({"format": "circ", "version": 99})
