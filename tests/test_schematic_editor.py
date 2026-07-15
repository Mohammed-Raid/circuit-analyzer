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
