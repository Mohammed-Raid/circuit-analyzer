"""
@file test_tab_draw_pattern.py
@brief Valide le pont « éditeur → graphe → suggestion de conditions » utilisé par
       le bouton « Enregistrer comme pattern » (gui/tab_draw._save_as_pattern)
       et le chemin d'export réel « Analyser ce circuit » (_export_netlist_file).

Depuis le fix Task 5, le chemin réel de TabDraw est :
`SchematicEditor.exporter_composants()` -> `generer_xml()` -> fichier .xml
temporaire -> `lire_xml()` (TabAnalyze) — broches nommées, puces catalogue
préservées. L'ancien export SPICE (`to_netlist`) tronquait les U catalogue à
3 broches à la relecture (`lire_spice` : _SPICE_PINS["U"] fixe).

Les tests headless valident le pont de données ; les tests Tk (skip sans
display) valident le chemin complet depuis un éditeur réel.
"""
import os
import tempfile

import pytest

from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.xml import generer_xml, lire_xml
from custom_circuits.loader import suggest_conditions


def _composants_rc():
    """Composants tels que produits par SchematicEditor.exporter_composants() :
    une résistance et un condensateur partageant un nœud signal (NET1), tous
    deux reliés à la masse."""
    return [
        Composant(ref="R1", type="R", pins={"1": "NET1", "2": "GND"}, value="1k"),
        Composant(ref="C1", type="C", pins={"1": "NET1", "2": "GND"}, value="100n"),
    ]


def test_pont_editeur_vers_suggestions():
    """Le graphe construit depuis l'export de l'éditeur détecte les conditions."""
    composants = _composants_rc()
    graph = construire_graphe(composants)

    refs = [c.ref for c in composants]
    assert set(refs) == {"R1", "C1"}

    suggestions = suggest_conditions(graph, refs)

    # Le condensateur touche la masse → condition détectée automatiquement.
    assert "C connecté à GND" in suggestions
    # R et C partagent NET1 (nœud signal) → condition topologique détectée.
    assert "R et C connectés au même nœud signal" in suggestions


def test_comp_info_construit_depuis_composants():
    """comp_info (ref → type/value/pins) tel que construit par _save_as_pattern."""
    composants = _composants_rc()

    comp_info = {
        c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
        for c in composants
    }
    assert comp_info["R1"]["type"] == "R"
    assert comp_info["C1"]["type"] == "C"
    # Chaque composant a bien des broches nommées (clé pin → net).
    assert comp_info["R1"]["pins"]


def test_export_xml_preserve_puce_catalogue_headless():
    """Pont de données seul : Composant NE555 8 broches -> generer_xml ->
    lire_xml ne perd ni le type, ni la value, ni les 8 broches."""
    comps = [
        Composant(ref="U1", type="U", value="NE555",
                  pins={str(i): f"NET{i}" for i in range(1, 9)}),
    ]
    tmp = tempfile.NamedTemporaryFile(suffix=".xml", mode="w",
                                      encoding="utf-8", delete=False)
    tmp.write(generer_xml(comps))
    tmp.close()
    try:
        relus = lire_xml(tmp.name)
    finally:
        os.unlink(tmp.name)

    u = next(c for c in relus if c.type == "U")
    assert u.value == "NE555"
    assert len(u.pins) == 8

    from circuit_analyzer.catalogue import identifier
    assert identifier(u.type, u.value)["nom"] == "NE555"


# ── Chemin réel complet (Tk requis, skip sans display) ──────────────────────

ctk = pytest.importorskip("customtkinter")


@pytest.fixture
def tab_draw():
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("pas de display Tk")
    root.withdraw()
    from gui.tab_draw import TabDraw
    tab = TabDraw(root)
    root.update_idletasks()
    yield tab
    root.destroy()


def test_export_analyse_puce_catalogue_reconnue(tab_draw):
    """Test 10 spec §8, chemin réel : NE555 catalogue placé + R câblée ->
    _export_netlist_file() -> lire_xml(path) -> U/NE555 reconnu par
    identifier. C'est le fichier exact que reçoit TabAnalyze via on_analyze."""
    ed = tab_draw._editor
    ed._activer_catalogue("U", "NE555")
    u = ed._place_at(300, 200)
    ed._place_type = "R"
    r = ed._place_at(600, 200)
    ed._add_wire(u.id, "3", r.id, "1")     # OUT du 555 -> R

    path = tab_draw._export_netlist_file()
    try:
        assert path is not None and path.lower().endswith(".xml")
        comps = lire_xml(path)
    finally:
        if path:
            os.unlink(path)

    u_lu = next(c for c in comps if c.type == "U")
    assert u_lu.value == "NE555"
    assert len(u_lu.pins) == 8             # jamais tronqué à 3 (ex-lire_spice)

    from circuit_analyzer.catalogue import identifier
    assert identifier(u_lu.type, u_lu.value)["nom"] == "NE555"

    # La R câblée sur OUT partage bien un net avec la broche 3 du 555.
    r_lu = next(c for c in comps if c.type == "R")
    assert u_lu.pins["3"] in r_lu.pins.values()


def test_export_circuit_simple_reste_analysable(tab_draw):
    """Non-régression : un schéma sans puce catalogue (R + GND) passe toujours
    par le même export XML et reste analysable."""
    ed = tab_draw._editor
    ed._place_type = "R"
    r = ed._place_at(200, 200)
    ed._place_type = "GND"
    g = ed._place_at(200, 320)
    ed._add_wire(r.id, "2", g.id, "1")

    path = tab_draw._export_netlist_file()
    try:
        assert path is not None and path.lower().endswith(".xml")
        comps = lire_xml(path)
    finally:
        if path:
            os.unlink(path)

    r_lu = next(c for c in comps if c.type == "R")
    assert r_lu.value == "10k"
    assert "GND" in {n.upper() for n in r_lu.pins.values()}
    # Le graphe se construit sans erreur (entrée du pipeline d'analyse).
    assert construire_graphe(comps) is not None
