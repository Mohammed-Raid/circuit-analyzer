"""
@file test_xml_generator.py
@brief Tests automatises pour test_xml_generator.
"""

"""Tests for the BoardSCH XML generator and the components→XML→components round-trip."""
import os
import tempfile

import pytest

from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.parser import Component
from circuit_analyzer.xml import (
    _positionner_amplificateur_inverseur,
    _positionner_composants_bloc,
    _Bloc,
    _PAS_X_BLOC,
    _PAS_Y_BLOC,
)
from circuit_analyzer.xml_generator import BoardSCHGenerator, components_to_xml
from circuit_analyzer.xml_parser import parse_xml


def _xml_to_components(xml: str):
    """@brief Helper de test pour xml to components."""
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as f:
        f.write(xml)
        path = f.name
    try:
        return parse_xml(path)
    finally:
        os.unlink(path)


# ── Generator basics ──────────────────────────────────────────────────────────

def test_generator_produces_valid_xml():
    """@brief Verifie generator produces valid xml.

    @return None
    """
    g = BoardSCHGenerator()
    r1 = g.add("Résistance", "10k", x=200, y=400)
    c1 = g.add("Capa", "100n", x=400, y=400)
    g.connect(r1, "1", c1, "+")
    xml = g.to_xml()
    assert xml.startswith("<?xml")
    assert "<BoardSCH" in xml
    assert "</BoardSCH>" in xml
    assert "Résistance" in xml
    assert "Capa" in xml


def test_generator_connection_format():
    """@brief Verifie generator connection format.

    @return None
    """
    # CFirst/CLast must follow compId_pinIdx_end_wireIdx so xml_parser can read it
    g = BoardSCHGenerator()
    r1 = g.add("Résistance", "10k")
    r2 = g.add("Résistance", "20k")
    g.connect(r1, "1", r2, "2")
    xml = g.to_xml()
    assert "<CFirst>0_1_0_0</CFirst>" in xml
    assert "<CLast>1_0_1_0</CLast>" in xml


def test_generator_unknown_pin_raises():
    """@brief Verifie generator unknown pin raises.

    @return None
    """
    g = BoardSCHGenerator()
    r1 = g.add("Résistance", "10k")
    c1 = g.add("Capa", "100n")
    with pytest.raises(ValueError):
        g.connect(r1, "BOGUS", c1, "+")


# ── Round-trip: Component → XML → Component preserves topology ────────────────

def test_roundtrip_rc_lowpass():
    """@brief Verifie roundtrip rc lowpass.

    Depuis le modèle Impédance Z, le passif isolé est émis comme « Impédance Z ».
    @return None
    """
    comps = [
        Component("R1", "R", {"1": "NET_MID", "2": "NET_IN"}, "10k"),
        Component("C1", "C", {"1": "NET_MID", "2": "GND"}, "100n"),
    ]
    xml = components_to_xml(comps)
    back = _xml_to_components(xml)
    types = sorted(r["circuit_type"] for r in match_patterns(build_graph(back)))
    assert "Impédance Z" in types


def test_roundtrip_inverting_amp():
    """@brief Verifie roundtrip inverting amp.

    @return None
    """
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    xml = components_to_xml(comps)
    back = _xml_to_components(xml)
    types = [r["circuit_type"] for r in match_patterns(build_graph(back))]
    assert "Amplificateur inverseur (AOP)" in types


def test_disposition_canonique_preserve_la_connectivite():
    """@brief Contrainte dure : la regeneration avec disposition canonique
    ne change AUCUNE connexion — verifie en re-detectant sur le resultat.
    """
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    resultats = match_patterns(build_graph(comps))
    orig = sorted(r["circuit_type"] for r in resultats)
    xml = components_to_xml(comps, resultats)
    item_zf, item_aop = _item(xml, "R2"), _item(xml, "U1")
    assert item_zf is not None and item_aop is not None
    assert float(item_zf.findtext("CtrIem/Y")) < float(item_aop.findtext("CtrIem/Y"))
    back = _xml_to_components(xml)
    roundtrip = sorted(r["circuit_type"] for r in match_patterns(build_graph(back)))
    assert orig == roundtrip


def test_roundtrip_transistor_switch():
    """@brief Verifie roundtrip transistor switch.

    @return None
    """
    comps = [
        Component("Q1", "Q", {"B": "NET_BASE", "C": "NET_COLL", "E": "GND"}),
        Component("R1", "R", {"1": "NET_BASE", "2": "NET_DRV"}, "1k"),
    ]
    xml = components_to_xml(comps)
    back = _xml_to_components(xml)
    types = [r["circuit_type"] for r in match_patterns(build_graph(back))]
    assert "Transistor en commutation" in types


def test_roundtrip_preserves_component_count():
    """@brief Verifie roundtrip preserves component count.

    @return None
    """
    comps = [
        Component("R1", "R", {"1": "A", "2": "B"}),
        Component("R2", "R", {"1": "B", "2": "GND"}),
        Component("C1", "C", {"1": "A", "2": "GND"}),
        Component("Q1", "Q", {"B": "B", "C": "A", "E": "GND"}),
    ]
    xml = components_to_xml(comps)
    back = _xml_to_components(xml)
    # Every drawable component survives the round-trip (power symbols are extra)
    assert len(back) == len(comps)


def test_roundtrip_combined_multi_pattern():
    """@brief Verifie roundtrip combined multi pattern.

    @return None
    """
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
        Component("R3", "R", {"1": "NET_B", "2": "NET_A"}),
        Component("C1", "C", {"1": "NET_B", "2": "GND"}),
        Component("F1", "F", {"1": "LINE", "2": "NET_A"}),
    ]
    orig = sorted(r["circuit_type"] for r in match_patterns(build_graph(comps)))
    xml = components_to_xml(comps)
    back = _xml_to_components(xml)
    roundtrip = sorted(r["circuit_type"] for r in match_patterns(build_graph(back)))
    assert orig == roundtrip


def test_power_net_creates_symbol():
    """@brief Verifie power net creates symbol.

    @return None
    """
    # A GND net must produce a GND symbol so the design app shows it
    comps = [Component("C1", "C", {"1": "VCC", "2": "GND"}, "100n")]
    xml = components_to_xml(comps)
    assert "<Name>GND</Name>" in xml
    assert "<Name>VCC+</Name>" in xml


def test_distinct_power_rails_not_merged():
    """@brief Verifie distinct power rails not merged.

    @return None
    """
    # Two distinct supply rails must stay distinct after round-trip, otherwise
    # decoupling caps on different rails would falsely collapse together.
    comps = [
        Component("C1", "C", {"1": "VMOT_48V", "2": "PGND"}, "100n"),
        Component("C2", "C", {"1": "VCC_5V",   "2": "AGND"}, "100n"),
    ]
    back = _xml_to_components(components_to_xml(comps))
    rails = set()
    for c in back:
        rails.update(c.pins.values())
    # The two positive rails remain separate names
    assert "VMOT_48V" in rails
    assert "VCC_5V" in rails
    # Les deux caps passent désormais comme « Impédance Z » (modèle Z)
    types = [r["circuit_type"] for r in match_patterns(build_graph(back))]
    assert types.count("Impédance Z") == 2


def test_relay_survives_roundtrip():
    """@brief Verifie relay survives roundtrip.

    @return None
    """
    # A relay coil (type K) must be drawable and survive the round-trip
    comps = [
        Component("K1", "K", {"A1": "VCC", "A2": "NET_SW",
                              "11": "COM", "12": "NC", "14": "NO"}),
        Component("Q1", "Q", {"B": "NET_BASE", "C": "NET_SW", "E": "GND"}),
        Component("R1", "R", {"1": "NET_BASE", "2": "NET_DRV"}, "1k"),
        Component("D1", "D", {"A": "NET_SW", "K": "VCC"}),
    ]
    xml = components_to_xml(comps)
    assert "<Name>Relais_1FormC</Name>" in xml
    back = _xml_to_components(xml)
    assert any(c.type == "K" for c in back)


def test_industrial_netlist_roundtrip_no_loss():
    """@brief Verifie industrial netlist roundtrip no loss.

    @return None
    """
    # A multi-rail industrial-style circuit must not LOSE any pattern through XML
    # (the greedy matcher may add an equivalent one, but never drop structure).
    import os

    from circuit_analyzer.parser import parse_file
    sim = os.path.join("simulations", "ldo_regulator.txt")
    if not os.path.exists(sim):
        return  # simulations folder optional
    comps = parse_file(sim)
    orig = sorted(r["circuit_type"] for r in match_patterns(build_graph(comps)))
    back = _xml_to_components(components_to_xml(comps))
    roundtrip = sorted(r["circuit_type"] for r in match_patterns(build_graph(back)))
    # Every original pattern type is still present after the round-trip
    for pattern in set(orig):
        assert orig.count(pattern) <= roundtrip.count(pattern) or pattern in roundtrip


# ── _Block / _layout_groups ───────────────────────────────────────────────────

from circuit_analyzer.xml_generator import _Block, _layout_groups, _place_blocks


def test_layout_groups_one_block_per_pattern():
    """@brief Verifie layout groups one block per pattern.

    @return None
    """
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    results = [{"circuit_type": "Amplificateur inverseur (AOP)",
                "components": ["U1", "R1", "R2"], "nodes": []}]
    blocks = _layout_groups(comps, results)
    assert len(blocks) == 1
    assert blocks[0].label == "Amplificateur inverseur (AOP)"
    assert {c.ref for c in blocks[0].comps} == {"U1", "R1", "R2"}


def test_layout_groups_unclassified_go_to_divers():
    """@brief Verifie layout groups unclassified go to divers.

    @return None
    """
    comps = [
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("L1", "L", {"1": "A", "2": "B"}),   # not in any pattern
    ]
    results = [{"circuit_type": "Amplificateur inverseur (AOP)",
                "components": ["U1", "R1", "R2"], "nodes": []}]
    blocks = _layout_groups(comps, results)
    labels = [b.label for b in blocks]
    assert "Divers" in labels
    divers = next(b for b in blocks if b.label == "Divers")
    assert {c.ref for c in divers.comps} == {"L1"}
    # Divers is always last
    assert blocks[-1].label == "Divers"


def test_place_blocks_groups_are_spatially_separated():
    """@brief Verifie place blocks groups are spatially separated.

    @return None
    """
    # Two blocks: components within a block are closer to each other than to
    # the other block's components.
    a = [Component("R1", "R", {"1": "X", "2": "Y"}),
         Component("R2", "R", {"1": "Y", "2": "Z"})]
    b = [Component("R3", "R", {"1": "P", "2": "Q"})]
    blocks = [_Block("Filtre", a), _Block("Divers", b)]
    pos = _place_blocks(blocks)
    # every ref placed
    assert set(pos) == {"R1", "R2", "R3"}
    # R1 and R2 (same block) share the same y row
    assert pos["R1"][1] == pos["R2"][1]
    # inter-block gap must be strictly larger than intra-block spacing
    intra = pos["R2"][0] - pos["R1"][0]   # gap within block A
    inter = pos["R3"][0] - pos["R2"][0]   # gap from block A to block B
    assert inter > intra, f"inter-block gap ({inter}) must exceed intra-block spacing ({intra})"


def test_place_blocks_relay_driver_uses_two_dimensional_layout():
    """@brief Verifie que la commande de relais n'est pas aplatie sur une ligne.

    @return None
    """
    comps = [
        Component("K1", "K", {"A1": "VCC", "A2": "SW"}),
        Component("Q1", "Q", {"B": "BASE", "C": "SW", "E": "GND"}),
        Component("D1", "D", {"A": "SW", "K": "VCC"}),
    ]
    pos = _place_blocks([_Block("Commande de relais", comps)])

    assert pos["K1"][1] == pos["D1"][1]
    assert pos["Q1"][1] > pos["K1"][1]
    assert pos["K1"][0] < pos["Q1"][0] < pos["D1"][0]


def test_place_blocks_generic_groups_wrap_to_compact_grid():
    """@brief Verifie qu'un groupe generique de 3 composants forme une grille compacte.

    @return None
    """
    comps = [
        Component("R1", "R", {"1": "A", "2": "B"}),
        Component("R2", "R", {"1": "B", "2": "C"}),
        Component("C1", "C", {"1": "C", "2": "GND"}),
    ]
    pos = _place_blocks([_Block("Filtre quelconque", comps)])

    assert len({y for _, y in pos.values()}) > 1
    assert max(x for x, _ in pos.values()) - min(x for x, _ in pos.values()) < 3 * 320


def test_layout_groups_extracts_roles_from_impedances():
    """@brief Un match avec 'impedances' peuple bloc.roles (aop/Zin/Zf)."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    results = [{
        "circuit_type": "Amplificateur inverseur (AOP)",
        "components": ["U1", "R2", "R1"],
        "nodes": [],
        "impedances": {
            "Zin": {"refs": ["R1"], "composition": "R1", "nodes": ("NET_INV", "NET_IN")},
            "Zf":  {"refs": ["R2"], "composition": "R2", "nodes": ("NET_INV", "NET_OUT")},
        },
    }]
    blocks = _layout_groups(comps, results)
    assert len(blocks) == 1
    assert blocks[0].roles == {"Zin": ["R1"], "Zf": ["R2"], "aop": ["U1"]}


def test_layout_groups_roles_empty_without_impedances():
    """@brief Sans 'impedances' (montage pas migre, ou Divers), roles reste vide."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    results = [{"circuit_type": "Amplificateur inverseur (AOP)",
                "components": ["U1", "R1", "R2"], "nodes": []}]
    blocks = _layout_groups(comps, results)
    assert blocks[0].roles == {}


def test_grouper_par_circuit_sommateur_zin_liste_ne_plante_pas():
    """@brief Le Sommateur a Zin en LISTE de blocs (pas un dict) — regression
    du bug documente en memoire projet (detecteur.py:701/718)."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_IN1", "2": "NET_INV"}),
        Component("R2", "R", {"1": "NET_IN2", "2": "NET_INV"}),
        Component("Rf", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    resultats = match_patterns(build_graph(comps))
    assert any(r["circuit_type"] == "Amplificateur sommateur (AOP)" for r in resultats)
    xml = components_to_xml(comps, resultats)  # ne doit pas lever AttributeError
    assert "R1" in xml and "Rf" in xml


def test_export_corpus_industriel_ne_plante_jamais():
    """@brief Balaie circuits_industriels/*.xml : detection + regeneration
    sans exception. Garde-fou pour les montages non migres par ce plan."""
    import glob

    from circuit_analyzer.xml import lire_xml

    fichiers = glob.glob(os.path.join("circuits_industriels", "*.xml"))
    assert fichiers, "corpus circuits_industriels/ introuvable depuis le cwd de pytest"
    for chemin in fichiers:
        comps = lire_xml(chemin)
        resultats = match_patterns(build_graph(comps))
        components_to_xml(comps, resultats)  # ne doit jamais lever


def test_components_to_xml_backward_compatible_without_results():
    """@brief Verifie components to xml backward compatible without results.

    @return None
    """
    # No results → must produce identical output to the legacy grid path.
    comps = [
        Component("R1", "R", {"1": "A", "2": "B"}),
        Component("C1", "C", {"1": "B", "2": "GND"}),
    ]
    xml_a = components_to_xml(comps)
    xml_b = components_to_xml(comps, results=None)
    assert xml_a == xml_b


def test_components_to_xml_grouped_roundtrip_preserved():
    """@brief Verifie components to xml grouped roundtrip preserved.

    @return None
    """
    # With results, the round-trip must still detect the same patterns:
    # grouping changes only coordinates, never connectivity.
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
        Component("R3", "R", {"1": "NET_B", "2": "NET_A"}),
        Component("C1", "C", {"1": "NET_B", "2": "GND"}),
        Component("F1", "F", {"1": "LINE", "2": "NET_A"}),
    ]
    results = match_patterns(build_graph(comps))
    xml = components_to_xml(comps, results=results)
    back = _xml_to_components(xml)
    roundtrip = sorted(r["circuit_type"] for r in match_patterns(build_graph(back)))
    orig = sorted(r["circuit_type"] for r in match_patterns(build_graph(comps)))
    assert orig == roundtrip


def test_components_to_xml_grouped_positions_differ_from_grid():
    """@brief Verifie components to xml grouped positions differ from grid.

    @return None
    """
    # When results are given, at least one component must land at a different
    # position than the naive grid, proving the grouped path is active.
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
        Component("R3", "R", {"1": "NET_B", "2": "NET_A"}),
        Component("C1", "C", {"1": "NET_B", "2": "GND"}),
    ]
    results = match_patterns(build_graph(comps))
    xml_grid = components_to_xml(comps)                    # legacy grid
    xml_grouped = components_to_xml(comps, results=results)  # grouped layout
    # The two XMLs must differ (different CtrIem positions) when results exist
    assert xml_grid != xml_grouped, (
        "Grouped layout must produce different coordinates from the legacy grid"
    )


def test_components_to_xml_grouped_writes_native_boardsch_groups():
    """@brief Verifie que le layout groupe ecrit aussi des groupes BoardSCH natifs.

    @return None
    """
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    results = [{"circuit_type": "Amplificateur inverseur (AOP)",
                "components": ["U1", "R1", "R2"], "nodes": []}]

    xml = components_to_xml(comps, results=results)

    assert "<GrpL>" in xml
    assert "<Gid>1</Gid>" in xml
    assert "<Begrp>true</Begrp>" in xml
    assert "<BeIngrp>true</BeIngrp>" in xml


def test_components_to_xml_places_power_symbols_inside_related_group():
    """@brief Verifie que les alimentations d'un circuit groupe restent proches du groupe.

    @return None
    """
    import xml.etree.ElementTree as ET

    comps = [
        Component("K1", "K", {"A1": "VCC", "A2": "SW"}),
        Component("Q1", "Q", {"B": "BASE", "C": "SW", "E": "GND"}),
        Component("D1", "D", {"A": "SW", "K": "VCC"}),
    ]
    results = [{"circuit_type": "Commande de relais",
                "components": ["K1", "Q1", "D1"], "nodes": ["VCC", "SW", "GND"]}]

    root = ET.fromstring(components_to_xml(comps, results=results))
    power_items = [
        item for item in root.find("CmpntL").findall("DataItem")
        if item.findtext("Name") in {"VCC+", "GND"}
    ]

    assert {item.findtext("Name") for item in power_items} == {"VCC+", "GND"}
    assert all(item.findtext("GpId") == "1" for item in power_items)
    for item in power_items:
        y = int(float(item.find("CtrIem").findtext("Y")))
        assert 120 <= y <= 570


# ── Régression : symbole inductance = Self (pas Bobine) ───────────────────────

def test_inductance_genere_self_pas_bobine():
    """@brief Régression : le générateur doit écrire <Name>Self</Name> pour une inductance.

    Si ce test casse, c'est qu'un commit a réintroduit 'Bobine' à la place de 'Self'
    dans _TYPE_VERS_FORME ou _FORME — réouvrir circuit_analyzer/xml.py et corriger.

    @return None
    """
    import re
    comps = [Component("L1", "L", {"1": "NET_A", "2": "NET_B"}, "10uH")]
    xml = components_to_xml(comps)
    noms = re.findall(r"<Name>(.*?)</Name>", xml)
    assert "Self" in noms, f"Attendu 'Self' dans les noms XML, obtenu : {noms}"
    assert "Bobine" not in noms, (
        "Régression détectée : 'Bobine' ne doit pas apparaître dans le XML généré. "
        "ERetroDesign afficherait le mauvais symbole (cercles verts)."
    )


def test_alias_bobine_pointe_vers_self():
    """@brief Régression : _ALIAS['Bobine'] et _ALIAS['Self'] doivent pointer sur 'Self'.

    Garantit que les anciens fichiers XML lus avec <Name>Bobine</Name> utilisent
    le bon template interne 'Self' (arcs rouges) et non l'ancien 'Bobine' (cercles verts).

    @return None
    """
    from circuit_analyzer.xml import _ALIAS, _FORME
    assert _ALIAS.get("Self") == "Self", "_ALIAS['Self'] doit être 'Self'"
    assert _ALIAS.get("Bobine") == "Self", "_ALIAS['Bobine'] doit pointer sur 'Self'"
    assert "Self" in _FORME, "Le template 'Self' doit exister dans _FORME"
    assert "Bobine" not in _FORME, (
        "'Bobine' ne doit plus être une clé dans _FORME — renommer en 'Self'"
    )


def test_circuits_industriels_sans_bobine():
    """@brief Régression : aucun fichier XML de circuits_industriels ne doit avoir <Name>Bobine</Name>.

    @return None
    """
    import re
    from pathlib import Path
    dossier = Path(__file__).resolve().parent.parent / "circuits_industriels"
    fichiers_avec_bobine = []
    for f in sorted(dossier.glob("*.xml")):
        contenu = f.read_text(encoding="utf-8", errors="replace")
        if re.search(r"<Name>Bobine</Name>", contenu):
            fichiers_avec_bobine.append(f.name)
    assert not fichiers_avec_bobine, (
        f"Fichiers XML avec <Name>Bobine</Name> (doit être <Name>Self</Name>) : "
        f"{fichiers_avec_bobine}"
    )


def test_connecteur_J_n_est_pas_perdu_a_l_export():
    """Un connecteur (type J) n'avait AUCUNE forme dans _TYPE_VERS_FORME :
    `if spec is None: continue` le supprimait EN SILENCE. Sur PG 2, 9 des 23
    composants disparaissaient a l'export."""
    import xml.etree.ElementTree as ET

    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml

    comps = [
        Composant(ref="J1", type="J", value="connecteur traversant",
                  pins={str(i): f"N{i}" for i in range(1, 14)}),
        Composant(ref="J2", type="J", value="JUMPER", pins={"1": "N1", "2": "N2"}),
        Composant(ref="R1", type="R", value="10k", pins={"1": "N1", "2": "N2"}),
    ]
    r = ET.fromstring(generer_xml(comps))
    items = r.findall(".//CmpntL/DataItem")
    # 3 composants + les symboles de rail eventuels : les 3 doivent etre la
    valeurs = [(i.findtext("value") or "") for i in items]
    assert "connecteur traversant" in valeurs, "connecteur 13 broches PERDU"
    assert "JUMPER" in valeurs, "jumper PERDU"
    # et ses broches portent bien des refs de connexion
    nodel = {s.text for i in items for dp in i.findall("./datapin/DataPin")
             for s in dp.findall("NodeL/string") if s.text}
    assert nodel, "aucune connexion emise"


def test_aucun_type_n_est_supprime_en_silence():
    """Contrat general : tout composant a broches ressort a l'export, quel que
    soit son type — sinon la carte du collegue revient amputee."""
    import xml.etree.ElementTree as ET

    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml

    comps = [Composant(ref=f"{t}1", type=t, value=t,
                       pins={"1": "A", "2": "B"})
             for t in ("R", "C", "J", "SW", "T", "ZZ")]
    r = ET.fromstring(generer_xml(comps))
    valeurs = {(i.findtext("value") or "") for i in r.findall(".//CmpntL/DataItem")}
    for t in ("R", "C", "J", "SW", "T", "ZZ"):
        assert t in valeurs, f"type {t} supprime en silence"


def test_broche_au_nom_inattendu_n_est_pas_perdue():
    """2e chemin de suppression silencieuse : une broche dont le NOM n'est pas
    dans le plan de la forme etait ignoree (`broche_forme is None -> continue`).
    Vu sur PowtranAlim : D1 a des broches '-'/'+' et U2.1 des 'C'/'E', absentes
    du plan Diode {A,K,1,2} -> toutes leurs liaisons disparaissaient."""
    import xml.etree.ElementTree as ET

    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml

    comps = [
        Composant(ref="D1", type="D", value="pont", pins={"-": "NA", "+": "NB"}),
        Composant(ref="R5", type="R", value="1k", pins={"1": "NA", "2": "NB"}),
    ]
    r = ET.fromstring(generer_xml(comps))
    # les deux nets doivent relier D1 ET R5 : donc au moins 2 refs par net
    nodel = [s.text for i in r.findall(".//CmpntL/DataItem")
             for dp in i.findall("./datapin/DataPin")
             for s in dp.findall("NodeL/string") if s.text]
    assert len(nodel) >= 4, f"broches perdues : seulement {len(nodel)} connexions"
    lignes = r.findall(".//lineL/Line")
    assert len(lignes) >= 2, "les liaisons de D1 n'ont pas ete emises"


def test_le_plan_de_forme_partage_n_est_jamais_mute():
    """Les plans de _TYPE_VERS_FORME sont des dicts PARTAGES au niveau module :
    les completer en place empoisonnerait tous les exports suivants."""
    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import _TYPE_VERS_FORME, generer_xml

    avant = dict(_TYPE_VERS_FORME["D"][1])
    generer_xml([Composant(ref="D1", type="D", value="x",
                           pins={"-": "NA", "+": "NB"})])
    assert _TYPE_VERS_FORME["D"][1] == avant, "plan de forme MUTE"


# ── Positioner canonical inverting amplifier ──────────────────────────────────

def test_positionner_amplificateur_inverseur_places_roles_canoniquement():
    """@brief Zin a gauche, AOP au centre, Zf strictement au-dessus (angle 0)."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    roles = {"aop": ["U1"], "Zin": ["R1"], "Zf": ["R2"]}
    pos = _positionner_amplificateur_inverseur(comps, roles, 100, 200)
    x_aop, y_aop = 100 + 2 * _PAS_X_BLOC, 200 + _PAS_Y_BLOC
    assert pos["U1"] == (x_aop, y_aop, 0)
    assert pos["R1"] == (100, y_aop, 0)
    assert pos["R2"] == (x_aop, 200, 0)
    assert pos["R2"][1] < pos["U1"][1]  # Zf strictement au-dessus de l'AOP


def test_positionner_amplificateur_inverseur_garde_les_satellites():
    """@brief Un composant du bloc absent des roles (satellite) est place, pas perdu."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
        Component("C3", "C", {"1": "NET_IN", "2": "GND"}),
    ]
    roles = {"aop": ["U1"], "Zin": ["R1"], "Zf": ["R2"]}
    pos = _positionner_amplificateur_inverseur(comps, roles, 0, 0)
    assert "C3" in pos
    assert len(pos["C3"]) == 2


def test_positionner_amplificateur_inverseur_zin_composite_en_chaine():
    """@brief Un Zin composite (2 refs) se place en chaine horizontale, pas superpose."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_MID"}),
        Component("C1", "C", {"1": "NET_MID", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    roles = {"aop": ["U1"], "Zin": ["R1", "C1"], "Zf": ["R2"]}
    pos = _positionner_amplificateur_inverseur(comps, roles, 0, 0)
    assert pos["R1"][0] != pos["C1"][0]
    assert pos["R1"][1] == pos["C1"][1]


# ── Dispatch registry (Task 3) ────────────────────────────────────────────────

def test_positionner_composants_bloc_utilise_le_canonique_si_roles():
    """@brief Bloc reconnu + roles peuples -> positionneur canonique (pas le gabarit famille)."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    roles = {"aop": ["U1"], "Zin": ["R1"], "Zf": ["R2"]}
    bloc = _Bloc("Amplificateur inverseur (AOP)", comps, roles=roles)
    attendu = _positionner_amplificateur_inverseur(comps, roles, 50, 60)
    assert _positionner_composants_bloc(bloc, 50, 60) == attendu


def test_positionner_composants_bloc_repli_si_pas_de_roles():
    """@brief Meme circuit_type SANS roles (montage pas migre) garde l'ancien gabarit famille."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    bloc = _Bloc("Amplificateur inverseur (AOP)", comps)  # roles={} par defaut
    resultat = _positionner_composants_bloc(bloc, 50, 60)
    # L'ancien gabarit famille place l'AOP a (x + _PAS_X_BLOC, y) — pas x+2*_PAS_X_BLOC.
    assert resultat["U1"][:2] == (50 + _PAS_X_BLOC, 60)


def _item(xml_str, ref):
    """@brief Helper de test : le <DataItem> dont <reference> vaut `ref`."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_str)
    for item in root.iter("DataItem"):
        if item.findtext("reference") == ref:
            return item
    return None


def test_generer_xml_positionne_zf_au_dessus_de_laop():
    """@brief Signature du gabarit canonique dans le XML : Zf strictement au-dessus de l'AOP."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    resultats = match_patterns(build_graph(comps))
    xml = components_to_xml(comps, resultats)
    item_zf, item_aop = _item(xml, "R2"), _item(xml, "U1")
    assert item_zf is not None and item_aop is not None
    y_zf = float(item_zf.findtext("CtrIem/Y"))
    y_aop = float(item_aop.findtext("CtrIem/Y"))
    assert y_zf < y_aop
