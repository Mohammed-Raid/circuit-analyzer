"""
@file test_editor_edition.py
@brief Confort d'édition : redo, copier/coller/dupliquer, ajuster à l'écran.
"""
import pytest


@pytest.fixture
def editor():
    ctk = pytest.importorskip("customtkinter")
    import tkinter as tk
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("pas d'affichage Tk disponible")
    root.withdraw()
    from gui.schematic_editor import SchematicEditor
    ed = SchematicEditor(root)
    yield ed
    root.destroy()


def _place(ed, t, x, y):
    ed._start_placing(t)
    ed._place_comp(x, y)


# ── A : Redo ──────────────────────────────────────────────────────────────────

def test_redo_retablit_apres_annulation(editor):
    _place(editor, "R", 100, 100)
    assert editor.comp_count() == 1
    editor._undo()
    assert editor.comp_count() == 0
    editor._redo()
    assert editor.comp_count() == 1


def test_nouvelle_action_invalide_le_redo(editor):
    _place(editor, "R", 100, 100)
    editor._undo()                       # pile redo : 1 élément
    _place(editor, "C", 200, 200)        # nouvelle action → redo vidé
    assert editor._redo_stack == []
    editor._redo()                       # ne doit rien faire
    assert editor.comp_count() == 1


# ── B : Copier / coller / dupliquer ───────────────────────────────────────────

def test_copier_coller(editor):
    _place(editor, "R", 100, 100)
    editor._select(list(editor._comps.keys())[0])
    editor._copy()
    editor._cursor_w = (300, 100)
    editor._paste()
    assert editor.comp_count() == 2
    # Le collé est un composant distinct, même type
    types = [c.comp_type for c in editor._comps.values()]
    assert types.count("R") == 2


def test_dupliquer_decale(editor):
    _place(editor, "C", 100, 100)
    src_id = list(editor._comps.keys())[0]
    editor._select(src_id)
    editor._duplicate()
    assert editor.comp_count() == 2
    src = editor._comps[src_id]
    dup = [c for cid, c in editor._comps.items() if cid != src_id][0]
    assert (dup.cx, dup.cy) != (src.cx, src.cy)   # bien décalé


def test_coller_est_annulable(editor):
    _place(editor, "R", 100, 100)
    editor._select(list(editor._comps.keys())[0])
    editor._copy()
    editor._paste()
    assert editor.comp_count() == 2
    editor._undo()
    assert editor.comp_count() == 1


# ── C : Ajuster à l'écran ─────────────────────────────────────────────────────

def test_fit_to_view_ne_plante_pas(editor):
    _place(editor, "R", 100, 100)
    _place(editor, "C", 800, 600)
    editor.fit_to_view()
    assert 0.2 <= editor._zoom <= 3.0


def test_fit_to_view_canvas_vide_reinitialise_zoom(editor):
    editor._zoom = 2.5
    editor.fit_to_view()
    assert editor._zoom == 1.0
