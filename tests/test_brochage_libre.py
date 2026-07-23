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


# ── Task 4 : boite vierge en palette ─────────────────────────────────────────

def test_boite_vierge_posee_sans_broche(editeur):
    c = _place(editeur, "X", 200, 200)
    assert c.ref == "X1"
    assert c.pinout == {}
    assert editeur._geom(c)["pins"] == {}


def test_boite_vierge_a_un_bouton_de_palette(editeur):
    assert "X" in editeur._palette_btns


# ── Task 5 : mode pinedit, amorcage paresseux, ajout de broche ───────────────

def test_entrer_et_sortir_sans_toucher_ne_change_rien(editeur):
    c = _place(editeur, "R", 200, 200)
    editeur._entrer_pinedit(c.id)
    editeur._quitter_pinedit()
    assert c.pinout is None            # amorcage PARESSEUX
    assert editeur._state == "idle"


def test_premiere_mutation_amorce_sans_bouger_les_broches(editeur):
    c = _place(editeur, "R", 200, 200)
    avant = dict(editeur._geom(c)["pins"])
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200, 200 - 40)
    assert c.pinout is not None
    for pn, xy in avant.items():
        assert editeur._geom(c)["pins"][pn] == xy


def test_broches_numerotees_automatiquement(editeur):
    c = _place(editeur, "X", 200, 200)
    editeur._entrer_pinedit(c.id)
    assert editeur._ajouter_broche(c, 200 - 40, 200) == "1"
    assert editeur._ajouter_broche(c, 200 - 40, 200 + 20) == "2"


def test_nom_reutilise_le_plus_petit_entier_libre(editeur):
    c = _place(editeur, "X", 200, 200)
    editeur._entrer_pinedit(c.id)
    for dy in (-20, 0, 20):
        editeur._ajouter_broche(c, 200 - 40, 200 + dy)
    del c.pinout["2"]
    editeur._invalider_geom(c.id)
    assert editeur._ajouter_broche(c, 200 - 40, 200) == "2"


def test_ajout_de_broche_est_annulable(editeur):
    c = _place(editeur, "X", 200, 200)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    editeur._undo()
    assert editeur._comps[c.id].pinout == {}


# ── Task 6 : glisser, renommer, supprimer ────────────────────────────────────

def test_glisser_une_broche_l_aimante_a_la_grille(editeur):
    c = _place(editeur, "X", 200, 200)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    editeur._deplacer_broche(c, "1", 200 - 40, 200 + 27)
    cote, dec = c.pinout["1"]
    assert cote == "L" and dec % 20 == 0


def test_glisser_au_dela_du_coin_agrandit_la_boite(editeur):
    c = _place(editeur, "X", 200, 200)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    h_avant = editeur._geom(c)["h"]
    editeur._deplacer_broche(c, "1", 200 - 40, 200 + 200)
    assert editeur._geom(c)["h"] > h_avant


def test_renommage_refuse_vide_et_doublon(editeur):
    c = _place(editeur, "X", 200, 200)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    editeur._ajouter_broche(c, 200 + 40, 200)
    assert editeur._renommer_broche(c, "1", "VCC") is True
    assert "VCC" in c.pinout and "1" not in c.pinout
    assert editeur._renommer_broche(c, "2", "VCC") is False
    assert editeur._renommer_broche(c, "2", "") is False
    assert "2" in c.pinout


def test_renommage_suit_les_fils(editeur):
    c = _place(editeur, "X", 200, 200)
    g = _place(editeur, "GND", 300, 300)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    editeur._quitter_pinedit()
    editeur._add_wire(c.id, "1", g.id, next(iter(editeur._geom(g)["pins"])))
    editeur._renommer_broche(c, "1", "OUT")
    assert editeur._wires[0].from_pin == "OUT"


def test_supprimer_une_broche_supprime_ses_fils(editeur):
    c = _place(editeur, "X", 200, 200)
    g = _place(editeur, "GND", 300, 300)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    editeur._quitter_pinedit()
    editeur._add_wire(c.id, "1", g.id, next(iter(editeur._geom(g)["pins"])))
    editeur._supprimer_broche(c, "1")
    assert "1" not in c.pinout
    assert editeur._wires == []          # aucun fil orphelin
