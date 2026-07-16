"""@file test_schematic_editor.py
@brief Editeur de schema (spec 2026-07-15) : rendu par primitives,
raccourcis, palette catalogue. Tk -> skip sans display.
"""
import pytest

ctk = pytest.importorskip("customtkinter")
import tkinter as tk                                    # noqa: E402

from gui.schematic_editor import SchematicEditor        # noqa: E402


@pytest.fixture
def editeur():
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("pas de display Tk")
    root.withdraw()
    ed = SchematicEditor(root)
    ed.pack()
    root.update_idletasks()
    yield ed
    root.destroy()


def _place(ed, t, cx, cy, value=""):
    """Place un composant par l'API interne (comme un clic en mode placement)."""
    ed._place_type = t
    ed._state = "placing"
    comp = ed._place_at(cx, cy) if hasattr(ed, "_place_at") else None
    # NOTE implémenteur : si aucune API interne directe n'existe, extraire
    # du handler de clic la pose effective dans une méthode _place_at(cx, cy)
    # -> CompInst (refactor minime, testable).
    return comp


def test_resistance_rendue_en_zigzag_pas_en_rectangle(editeur):
    c = _place(editeur, "R", 200, 200)
    items = editeur._canvas.find_withtag(f"comp_{c.id}")
    types = {editeur._canvas.type(i) for i in items}
    # Un zigzag = au moins une "line" à >= 8 points ; plus AUCUN rectangle.
    assert "rectangle" not in types
    lignes = [i for i in items if editeur._canvas.type(i) == "line"]
    assert any(len(editeur._canvas.coords(i)) >= 16 for i in lignes)


def test_gnd_rendu_par_primitives(editeur):
    c = _place(editeur, "GND", 300, 300)
    assert editeur._canvas.find_withtag(f"comp_{c.id}")


def test_jonction_dessinee_pour_trois_fils(editeur):
    a = _place(editeur, "R", 160, 100)
    b = _place(editeur, "R", 240, 100)
    c = _place(editeur, "R", 240, 180)
    for src, dst in [((a.id, "2"), (b.id, "1")),
                     ((a.id, "2"), (c.id, "1")),
                     ((b.id, "1"), (c.id, "1"))]:
        editeur._add_wire(src[0], src[1], dst[0], dst[1])
    editeur._redraw_all()
    assert editeur._canvas.find_withtag("jonction")


def test_deux_fils_convergents_meme_broche_pas_de_jonction(editeur):
    """Revue Task 2 : 2 fils distincts convergeant sur UNE broche ne suffisent
    pas — seuil >= 3 extrémités de FILS (spec §4), pas >= 2 fils."""
    a = _place(editeur, "R", 100, 100)
    b = _place(editeur, "R", 300, 100)
    c = _place(editeur, "R", 100, 300)
    editeur._add_wire(a.id, "2", b.id, "1")
    editeur._add_wire(c.id, "2", b.id, "1")
    editeur._redraw_all()
    assert not editeur._canvas.find_withtag("jonction")


def test_apercu_cablage_orthogonal(editeur):
    a = _place(editeur, "R", 160, 100)
    editeur._start_wiring(a.id, "2")
    editeur._update_wire_preview(300, 220)   # point monde courant
    coords = editeur._canvas.coords(editeur._rubber_band)
    # L : 6 coordonnées (3 points), segments H puis V
    assert len(coords) == 6
    assert coords[1] == coords[3] or coords[0] == coords[2]
