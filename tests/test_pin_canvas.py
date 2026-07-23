"""@file test_pin_canvas.py
@brief Canevas de brochage de l'onglet Composants (spec 2026-07-23).
Tk -> skip sans display.
"""
import pytest

ctk = pytest.importorskip("customtkinter")

from gui.pin_canvas import PinCanvas          # noqa: E402


@pytest.fixture
def canevas():
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("pas de display Tk")
    root.withdraw()
    pc = PinCanvas(root)
    pc.pack()
    root.update_idletasks()
    yield pc
    root.destroy()


# ── Task 1 : dessin et pose de broche ────────────────────────────────────────

def test_canevas_vierge(canevas):
    assert canevas.brochage() == []


def test_clic_bord_gauche_ajoute_une_broche(canevas):
    assert canevas._ajouter(-40, 0) == "1"
    (nom, cote, dec), = canevas.brochage()
    assert (nom, cote) == ("1", "L")
    assert dec % 20 == 0


def test_broches_ajoutees_en_fin_et_numerotees(canevas):
    canevas._ajouter(-40, -20)
    canevas._ajouter(-40, 20)
    canevas._ajouter(0, -30)
    assert [n for n, _, _ in canevas.brochage()] == ["1", "2", "3"]


def test_charger_puis_brochage_est_fidele(canevas):
    src = [("VCC", "T", 0), ("IN", "L", -20), ("GND", "B", 0)]
    canevas.charger(src)
    assert canevas.brochage() == src


def test_lecture_seule_ne_mute_pas(canevas):
    canevas.charger([("VCC", "T", 0)], lecture_seule=True)
    canevas._ajouter(-40, 0)
    assert canevas.brochage() == [("VCC", "T", 0)]


# ── Task 2 : glisser, renommer, supprimer ────────────────────────────────────

def test_glisser_conserve_l_ordre_et_aimante(canevas):
    canevas._ajouter(-40, -20)
    canevas._ajouter(-40, 20)
    canevas._deplacer("1", -40, 27)
    noms = [n for n, _, _ in canevas.brochage()]
    assert noms == ["1", "2"]                    # ordre INCHANGE
    cote, dec = next((c, d) for n, c, d in canevas.brochage() if n == "1")
    assert cote == "L" and dec % 20 == 0


def test_glisser_au_dela_du_coin_agrandit_la_boite(canevas):
    canevas._ajouter(-40, 0)
    h_avant = canevas._defn()["h"]
    canevas._deplacer("1", -40, 200)
    assert canevas._defn()["h"] > h_avant


def test_renommage_refuse_vide_et_doublon(canevas):
    canevas._ajouter(-40, -20)
    canevas._ajouter(-40, 20)
    assert canevas._renommer("1", "VCC") is True
    assert [n for n, _, _ in canevas.brochage()] == ["VCC", "2"]
    assert canevas._renommer("2", "VCC") is False
    assert canevas._renommer("2", "  ") is False
    assert [n for n, _, _ in canevas.brochage()] == ["VCC", "2"]


def test_suppression_puis_ajout_recycle_le_nom_en_fin(canevas):
    for dy in (-20, 0, 20):
        canevas._ajouter(-40, dy)
    canevas._supprimer("2")
    assert [n for n, _, _ in canevas.brochage()] == ["1", "3"]
    canevas._ajouter(40, 0)
    assert [n for n, _, _ in canevas.brochage()] == ["1", "3", "2"]


def test_hit_test_trouve_la_broche(canevas):
    canevas._ajouter(-40, 0)
    px, py = canevas._defn()["pins"]["1"]
    assert canevas._broche_a(px, py) == "1"
    assert canevas._broche_a(px + 200, py) is None


# ── Task 3 : bandeau d'ordre ─────────────────────────────────────────────────

def test_reordonner_permute_sans_bouger_les_positions(canevas):
    canevas.charger([("A", "L", -20), ("B", "L", 20), ("C", "R", 0)])
    positions = dict(canevas._defn()["pins"])
    canevas._reordonner(2, 0)
    assert [n for n, _, _ in canevas.brochage()] == ["C", "A", "B"]
    assert dict(canevas._defn()["pins"]) == positions   # dessin inchangé


def test_reordonner_index_hors_bornes_est_sans_effet(canevas):
    canevas.charger([("A", "L", 0), ("B", "R", 0)])
    canevas._reordonner(5, 0)
    canevas._reordonner(0, 9)
    assert [n for n, _, _ in canevas.brochage()] == ["A", "B"]


def test_bandeau_suit_l_ordre_du_brochage(canevas):
    canevas.charger([("A", "L", -20), ("B", "L", 20)])
    assert [p.cget("text") for p in canevas._pastilles] == ["A", "B"]
    canevas._reordonner(1, 0)
    assert [p.cget("text") for p in canevas._pastilles] == ["B", "A"]
