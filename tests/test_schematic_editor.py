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


# ── Task 5 : palette catalogue (« Puces réelles ») ──────────────────────────

def test_placement_puce_catalogue(editeur):
    editeur._activer_catalogue("U", "NE555")   # prépare le placement
    c = editeur._place_at(400, 300)
    assert c.comp_type == "U::NE555"
    assert c.ref == "U1"          # revue Task 2 : jamais "U::NE5551"
    defn = editeur._defs["U::NE555"]
    assert len(defn["pins"]) == 8 and defn["fonctions"]["2"] == "TRIG"


def test_placement_puce_74hc00_14_broches(editeur):
    editeur._activer_catalogue("U", "74HC00")
    c = editeur._place_at(200, 200)
    assert c.comp_type == "U::74HC00"
    assert c.ref == "U1"
    assert len(editeur._defs["U::74HC00"]["pins"]) == 14


def test_refs_uniques_types_catalogue_partagent_compteur_type_reel(editeur):
    """Deux puces catalogue différentes (même lettre "U") ne doivent jamais
    collisionner sur la même réf — le compteur est partagé par type réel."""
    editeur._activer_catalogue("U", "NE555")
    c1 = editeur._place_at(100, 100)
    editeur._activer_catalogue("U", "74HC00")
    c2 = editeur._place_at(300, 100)
    assert {c1.ref, c2.ref} == {"U1", "U2"}


def test_placement_led_rouge_value_imposee(editeur):
    editeur._activer_catalogue("D", "LED rouge")
    c = editeur._place_at(150, 150)
    assert c.comp_type == "D"     # type intégré, pas de def dynamique
    assert c.value == "LED rouge"
    assert c.ref == "D1"


def test_export_puce_catalogue_analysable(editeur):
    editeur._activer_catalogue("U", "NE555")
    editeur._place_at(400, 300)
    comps = editeur.exporter_composants()
    u = next(c for c in comps if c.type == "U")
    assert u.value == "NE555"
    from circuit_analyzer.catalogue import identifier
    assert identifier(u.type, u.value)["nom"] == "NE555"


def test_relecture_circ_regenere_def_puce_catalogue(editeur):
    """Spec §4 : la def dynamique doit être régénérée AVANT tout redraw à la
    relecture d'un .circ contenant une puce catalogue, sinon KeyError."""
    editeur._activer_catalogue("U", "NE555")
    editeur._place_at(200, 200)
    doc = editeur.to_dict()
    del editeur._defs["U::NE555"]   # simule un éditeur frais sans la def
    editeur.load_dict(doc)          # ne doit pas lever KeyError
    assert "U::NE555" in editeur._defs
    comp = next(c for c in editeur._comps.values() if c.comp_type == "U::NE555")
    assert editeur._canvas.find_withtag(f"comp_{comp.id}")


def test_refresh_palette_conserve_def_puce_catalogue(editeur):
    """Un refresh_palette() (édition de bibliothèque perso) ne doit pas purger
    à tort une puce catalogue posée comme composant devenu 'inconnu'."""
    editeur._activer_catalogue("U", "NE555")
    c = editeur._place_at(200, 200)
    editeur.refresh_palette()
    assert "U::NE555" in editeur._defs
    assert c.id in editeur._comps


def test_palette_liste_puces_reelles_compacte(editeur):
    assert hasattr(editeur, "_catalogue_listbox")
    # ~30 entrées catalogue (5 U exacts + 6*74HC + 4 suffixes + 3 Q + 3 M + 2 D + 3 LED)
    assert editeur._catalogue_listbox.size() >= 20
