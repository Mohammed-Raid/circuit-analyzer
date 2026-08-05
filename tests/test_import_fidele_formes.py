"""@file test_import_fidele_formes.py
@brief Import fidele des formes de bibliotheque ERetroDesign (spec 2026-08-05) :
_auto_def fait suivre les primitives reelles jusqu'a l'editeur. Tk -> skip
sans display.
"""
import pytest

ctk = pytest.importorskip("customtkinter")

from gui.schematic_editor import SchematicEditor, _auto_def


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
    ed._place_type, ed._state = t, "placing"
    return ed._place_at(cx, cy)


def test_auto_def_copie_les_primitives_de_forme_si_presentes():
    d = _auto_def("Test", ["1", "2"], {"1": ["L", 0], "2": ["R", 0]},
                  forme_primitives=[("polygon", [(0, -10), (10, 10), (-10, 10)], False)])
    assert d["primitives"] == [("polygon", [(0, -10), (10, 10), (-10, 10)], False)]
    assert set(d["pins"]) == {"1", "2"}      # le brochage reste inchange


def test_auto_def_sans_primitives_ne_pose_pas_la_cle():
    d = _auto_def("Test", ["1", "2"], {"1": ["L", 0], "2": ["R", 0]})
    assert "primitives" not in d


def test_composant_avec_forme_se_dessine_sans_la_boite_generique(editeur):
    editeur._defs["FORME"] = {
        "label": "Test", "color": "#94a3b8", "w": 80, "h": 60,
        "pins": {"1": (-40, 0)}, "cotes": {"1": "L"}, "default_value": "",
        "primitives": [("polygon", [(0, -20), (20, 20), (-20, 20)], False)],
    }
    c = _place(editeur, "FORME", 200, 200)
    items = editeur._canvas.find_withtag(f"comp_{c.id}")
    polygones = [i for i in items if editeur._canvas.type(i) == "polygon"]
    assert polygones
    # Le triangle importe a 3 sommets (6 coordonnees) ; la boite generique
    # (test suivant) en a 4 (8 coordonnees) : ce nombre distingue les deux.
    assert len(editeur._canvas.coords(polygones[0])) == 6


def test_composant_avec_forme_garde_ses_libelles_de_broches(editeur):
    editeur._defs["FORME"] = {
        "label": "Test", "color": "#94a3b8", "w": 80, "h": 60,
        "pins": {"1": (-40, 0)}, "cotes": {"1": "L"}, "default_value": "",
        "primitives": [("line", [(-10, 0), (10, 0)], 2)],
    }
    c = _place(editeur, "FORME", 200, 200)
    items = editeur._canvas.find_withtag(f"comp_{c.id}")
    textes = [i for i in items if editeur._canvas.type(i) == "text"
             and editeur._canvas.itemcget(i, "text").strip() == "1"]
    assert textes    # le libelle "1" est bien dessine malgre la vraie forme


def test_composant_sans_forme_garde_la_boite_generique_actuelle(editeur):
    editeur._defs["SANSFORME"] = {
        "label": "Test", "color": "#94a3b8", "w": 80, "h": 60,
        "pins": {"1": (-40, 0)}, "cotes": {"1": "L"}, "default_value": "",
    }
    c = _place(editeur, "SANSFORME", 200, 200)
    items = editeur._canvas.find_withtag(f"comp_{c.id}")
    polygones = [i for i in items if editeur._canvas.type(i) == "polygon"]
    assert polygones
    assert len(editeur._canvas.coords(polygones[0])) == 8   # rectangle 4 sommets
