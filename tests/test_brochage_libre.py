"""@file test_brochage_libre.py
@brief Brochage libre par instance (spec 2026-07-23) : resolveur de geometrie,
rendu en boite, mode d'edition de broches, persistance. Tk -> skip sans display.
"""
import pytest

ctk = pytest.importorskip("customtkinter")

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


def _place(ed, t, cx, cy):
    """Pose un composant par l'API interne (comme un clic en mode placement)."""
    ed._place_type, ed._state = t, "placing"
    return ed._place_at(cx, cy)


# ── Task 2 : le resolveur _geom ──────────────────────────────────────────────

def test_geom_sans_pinout_rend_la_def_du_type(editeur):
    c = _place(editeur, "R", 200, 200)
    assert editeur._geom(c) is editeur._defs["R"]


def test_geom_avec_pinout_ignore_la_def_du_type(editeur):
    c = _place(editeur, "R", 200, 200)
    c.pinout = {"A": ("L", 0), "B": ("R", 0), "C": ("T", 0)}
    editeur._invalider_geom()
    assert set(editeur._geom(c)["pins"]) == {"A", "B", "C"}


def test_hit_test_trouve_une_broche_libre(editeur):
    c = _place(editeur, "R", 200, 200)
    c.pinout = {"VCC": ("T", 0)}
    editeur._invalider_geom()
    editeur._redraw_all()
    dx, dy = editeur._geom(c)["pins"]["VCC"]
    assert editeur._find_pin_at(200 + dx, 200 + dy) == (c.id, "VCC")


def test_export_utilise_les_broches_libres_sans_polluer_la_valeur(editeur):
    c = _place(editeur, "R", 200, 200)
    c.pinout = {"1": ("L", 0), "2": ("R", 0), "3": ("B", 0)}
    editeur._invalider_geom()
    comp = next(x for x in editeur.exporter_composants() if x.ref == c.ref)
    assert set(comp.pins) == {"1", "2", "3"}
    assert comp.type == "R"


# ── Task 3 : rendu en boite honnete ──────────────────────────────────────────

def test_resistance_rebrochee_devient_une_boite(editeur):
    c = _place(editeur, "R", 200, 200)
    c.pinout = {"1": ("L", 0), "2": ("R", 0)}
    editeur._invalider_geom()
    editeur._redraw_all()
    items = editeur._canvas.find_withtag(f"comp_{c.id}")
    lignes = [i for i in items if editeur._canvas.type(i) == "line"]
    # Le zigzag (>= 8 points) a disparu au profit d'un rectangle.
    assert not any(len(editeur._canvas.coords(i)) >= 16 for i in lignes)
    assert any(editeur._canvas.type(i) == "polygon" for i in items)


def test_resistance_intacte_garde_son_zigzag(editeur):
    c = _place(editeur, "R", 200, 200)
    items = editeur._canvas.find_withtag(f"comp_{c.id}")
    lignes = [i for i in items if editeur._canvas.type(i) == "line"]
    assert any(len(editeur._canvas.coords(i)) >= 16 for i in lignes)


def test_broche_du_haut_est_dessinee(editeur):
    c = _place(editeur, "R", 200, 200)
    c.pinout = {"VCC": ("T", 0)}
    editeur._invalider_geom()
    editeur._redraw_all()
    assert editeur._canvas.find_withtag(f"pin_{c.id}_VCC")
