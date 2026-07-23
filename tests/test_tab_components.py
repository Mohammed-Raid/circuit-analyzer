"""@file test_tab_components.py
@brief Onglet Composants : brochage positionné (spec 2026-07-23).

Tk -> skip sans display. La bibliothèque est isolée dans tmp_path : le VRAI
`component_library.json` (règle perso du boss) ne doit JAMAIS être touché.
"""
import json

import pytest

ctk = pytest.importorskip("customtkinter")


class _Boites:
    """Remplace `messagebox` : une modale non neutralisée GÈLE la suite."""

    def __init__(self):
        self.infos, self.erreurs = [], []

    def showinfo(self, _titre, message=""):
        self.infos.append(message)

    def showerror(self, _titre, message=""):
        self.erreurs.append(message)

    def showwarning(self, _titre, message=""):
        self.erreurs.append(message)

    def askyesno(self, _titre, _message=""):
        return True          # abandon de saisie toujours autorisé en test


@pytest.fixture
def onglet(tmp_path, monkeypatch):
    chemin = tmp_path / "component_library.json"
    monkeypatch.setattr("gui.tab_components.chemin_bibliotheque",
                        lambda: chemin)
    boites = _Boites()
    monkeypatch.setattr("gui.tab_components.messagebox", boites)
    from gui.tab_components import TabComponents
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("pas de display Tk")
    root.withdraw()
    t = TabComponents(root)
    root.update_idletasks()
    t._boites = boites
    yield t, chemin
    root.destroy()


def test_sauvegarde_ecrit_pins_dans_l_ordre_et_le_brochage(onglet):
    t, chemin = onglet
    t._prefix_var.set("IC")
    t._name_var.set("Ampli")
    t._brochage = [("VCC", "T", 0), ("IN", "L", -20), ("GND", "B", 0)]
    t._sauvegarder()
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert data["IC"]["pins"] == ["VCC", "IN", "GND"]
    assert data["IC"]["brochage"]["VCC"] == ["T", 0]


def test_relecture_d_un_type_sans_brochage_amorce_les_broches(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps(
        {"ZZ": {"name": "Ancien", "pins": ["A", "B", "C"]}}),
        encoding="utf-8")
    t._load()
    t._afficher_perso("ZZ")
    noms = [n for n, _, _ in t._brochage]
    assert noms == ["A", "B", "C"]                  # aucune broche perdue
    assert all(c in ("L", "R", "T", "B") for _n, c, _d in t._brochage)


def test_relecture_d_un_type_avec_brochage_est_fidele(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({"IC": {
        "name": "Ampli", "pins": ["VCC", "IN", "GND"],
        "brochage": {"VCC": ["T", 0], "IN": ["L", -20], "GND": ["B", 0]}}}),
        encoding="utf-8")
    t._load()
    t._afficher_perso("IC")
    assert t._brochage == [("VCC", "T", 0), ("IN", "L", -20), ("GND", "B", 0)]


def test_type_integre_est_en_lecture_seule(onglet):
    t, _ = onglet
    t._afficher_integre("R")
    assert t._canvas_broches._lecture_seule is True


def test_deplacer_une_broche_rend_le_formulaire_sale(onglet):
    t, _ = onglet
    t._prefix_var.set("IC")
    t._brochage = [("1", "L", 0)]
    t._prendre_snapshot()
    t._brochage = [("1", "R", 0)]
    assert t._etat_courant() != t._etat_initial


def test_duplication_clone_le_brochage(onglet):
    t, _ = onglet
    t._brochage = [("VCC", "T", 0)]
    t._dupliquer()
    t._brochage[0] = ("GND", "B", 0)
    assert t._etat_initial[2][0][0] == "VCC"        # snapshot non altéré


def test_sauvegarde_refuse_un_type_sans_broche(onglet):
    t, chemin = onglet
    erreurs = t._boites.erreurs
    t._prefix_var.set("IC")
    t._name_var.set("Vide")
    t._brochage = []
    t._sauvegarder()
    assert erreurs and "broche" in erreurs[0].lower()
    assert not chemin.exists() or "IC" not in json.loads(
        chemin.read_text(encoding="utf-8"))


def test_saisie_rapide_voit_les_broches_dans_l_ordre(onglet, monkeypatch):
    """L'ordre du canevas doit ressortir tel quel côté saisie rapide."""
    t, chemin = onglet
    t._prefix_var.set("IC")
    t._name_var.set("Ampli")
    t._brochage = [("GND", "B", 0), ("VCC", "T", 0), ("IN", "L", 0)]
    t._sauvegarder()
    monkeypatch.setattr("circuit_analyzer.composant.chemin_bibliotheque",
                        lambda: chemin)
    from circuit_analyzer.saisie import ModeleSaisie
    assert ModeleSaisie()._broches_du_type("IC") == ["GND", "VCC", "IN"]
