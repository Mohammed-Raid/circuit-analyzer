"""
@file test_palette_et_doublon.py
@brief Tests des composants étendus, de la synchronisation palette éditeur, et du
       contrôle de doublon à la création d'un pattern.
"""
import pytest

from gui.schematic_editor import _auto_def, COMP_DEFS
from circuit_analyzer.composant import lire_netlist


# ── Partie 1 : standards manquants ────────────────────────────────────────────

def test_standards_ajoutes_a_la_palette():
    """F, M, T, SW sont désormais dessinables dans l'éditeur."""
    for t in ("F", "M", "T", "SW"):
        assert t in COMP_DEFS, f"{t} devrait être dans COMP_DEFS"
    # Broches conformes à TYPES_COMPOSANTS
    assert set(COMP_DEFS["M"]["pins"]) == {"G", "D", "S"}
    assert set(COMP_DEFS["T"]["pins"]) == {"P1", "P2", "S1", "S2"}


def test_sw_netlist_roundtrip(tmp_path):
    """Un interrupteur SW1 est relu comme type SW (préfixe 2 lettres)."""
    p = tmp_path / "sw.sp"
    p.write_text("* test\nSW1 NET1 GND\nR1 NET1 GND 1k\n", encoding="utf-8")
    comps = lire_netlist(str(p))
    types = {c.ref: c.type for c in comps}
    assert types["SW1"] == "SW"
    assert types["R1"] == "R"


# ── Partie 2 : géométrie auto des types personnalisés ─────────────────────────

def test_auto_def_deux_broches():
    """2 broches → une à gauche, une à droite."""
    d = _auto_def("Mon type", ["1", "2"])
    assert set(d["pins"]) == {"1", "2"}
    assert d["pins"]["1"][0] < 0 < d["pins"]["2"][0]


def test_auto_def_quatre_broches():
    """4 broches → 2 à gauche, 2 à droite, clés = noms de broches."""
    d = _auto_def("Quad", ["A", "B", "C", "D"])
    assert set(d["pins"]) == {"A", "B", "C", "D"}
    gauche = [p for p, (x, _) in d["pins"].items() if x < 0]
    droite = [p for p, (x, _) in d["pins"].items() if x > 0]
    assert len(gauche) == 2 and len(droite) == 2


# ── Fixtures Tk ───────────────────────────────────────────────────────────────

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


def _bibliotheque_temporaire(monkeypatch, tmp_path):
    """Redirige la bibliothèque de composants vers un fichier temporaire."""
    chemin = tmp_path / "component_library.json"
    chemin.write_text("{}", encoding="utf-8")
    import circuit_analyzer.composant as composant
    import gui.tab_components as tab_components
    monkeypatch.setattr(composant, "chemin_bibliotheque", lambda: chemin)
    monkeypatch.setattr(tab_components, "chemin_bibliotheque", lambda: chemin)
    return chemin


# ── Partie 2 : synchronisation palette éditeur ────────────────────────────────

def test_composant_perso_apparait_et_disparait_de_la_palette(
        ctk_root, monkeypatch, tmp_path):
    """Créer un type l'ajoute à la palette de l'éditeur ; le supprimer le retire,
    et purge du canvas un composant de ce type déjà posé."""
    _bibliotheque_temporaire(monkeypatch, tmp_path)
    from gui.tab_components import TabComponents
    from gui.schematic_editor import SchematicEditor
    from tkinter import messagebox

    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: None)

    editor = SchematicEditor(ctk_root)
    tab_p = TabComponents(ctk_root, on_save=editor.refresh_palette)

    # 1) Créer un type personnalisé 'IC' (2 broches)
    tab_p._prefix_var.set("IC")
    tab_p._name_var.set("Mon IC")
    tab_p._pin_lignes[0][0].set("A")
    tab_p._ajouter_broche("B")
    tab_p._sauvegarder()

    assert "IC" in editor._defs, "le type créé doit être dessinable"
    assert "IC" in editor._palette_btns, "le bouton de palette doit apparaître"

    # 2) Poser un composant de ce type sur le canvas
    editor._start_placing("IC")
    editor._place_comp(100, 100)
    assert any(c.comp_type == "IC" for c in editor._comps.values())

    # 3) Supprimer le type → bouton retiré + composant purgé du canvas
    tab_p._supprimer()
    assert "IC" not in editor._palette_btns
    assert not any(c.comp_type == "IC" for c in editor._comps.values())


# ── Partie 3 : doublon de pattern ─────────────────────────────────────────────

def test_doublon_pattern_refuse(ctk_root, monkeypatch, tmp_path):
    """Sauvegarder un pattern dont le nom existe déjà n'ajoute rien."""
    chemin = tmp_path / "custom_circuits.json"
    import custom_circuits.loader as loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)

    from gui.tab_circuits import TabCircuits
    from tkinter import messagebox

    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: None)

    tab = TabCircuits(ctk_root)

    # 1) Premier enregistrement
    tab._afficher_nouveau()
    tab._name_var.set("Mon montage")
    list(tab._comp_vars.values())[0].set(True)
    tab._sauvegarder()
    assert len(tab._custom) == 1

    # 2) Même nom → refusé, rien d'ajouté
    tab._afficher_nouveau()
    tab._name_var.set("Mon montage")
    list(tab._comp_vars.values())[0].set(True)
    tab._sauvegarder()
    assert len(tab._custom) == 1, "un doublon ne doit pas être ajouté"
