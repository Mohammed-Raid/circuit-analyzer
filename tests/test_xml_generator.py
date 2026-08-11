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


# ── Positionneur canonique : amplificateur inverseur ────────────────────────────

from circuit_analyzer.xml import _positionner_amplificateur_inverseur, _PAS_X_BLOC, _PAS_Y_BLOC


def test_positionner_amplificateur_inverseur_places_roles_canoniquement():
    """@brief Zin a gauche, AOP au centre, Zf au-dessus avec angle 90 (arc de contre-reaction)."""
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
    assert pos["R2"] == (x_aop, 200, 90)


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


def test_positionner_amplificateur_inverseur_ignore_role_hors_bloc():
    """@brief Un ref present dans `roles` mais absent de `comps` (bloc etranger,
    ex. detecteur/registre corrompu ou pattern personnalise futur reutilisant le
    meme circuit_type) ne doit JAMAIS recevoir de position ici : sinon
    `_positionner_blocs` ecraserait la position d'un composant d'un AUTRE bloc
    via son `pos.update(...)` partage."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    # "R99" appartient a un AUTRE bloc mais figure (a tort) dans ces roles.
    roles = {"aop": ["U1"], "Zin": ["R1"], "Zf": ["R2", "R99"]}
    pos = _positionner_amplificateur_inverseur(comps, roles, 0, 0)
    assert "R99" not in pos, "ref hors du bloc place quand meme : risque de vol de position inter-blocs"
    # les refs legitimes du bloc restent placees normalement
    assert "U1" in pos and "R1" in pos and "R2" in pos


# ── Dispatch du positionneur canonique + angle dans le XML ──────────────────────

import xml.etree.ElementTree as ET

from circuit_analyzer.xml import _Bloc, _positionner_composants_bloc


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
    root = ET.fromstring(xml_str)
    for item in root.iter("DataItem"):
        if item.findtext("reference") == ref:
            return item
    return None


def test_generer_xml_ecrit_angle_canonique_pour_zf():
    """@brief La resistance de contre-reaction (Zf) recoit l'angle canonique 90 dans le XML."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    resultats = match_patterns(build_graph(comps))
    xml = components_to_xml(comps, resultats)
    item_zf, item_zin = _item(xml, "R2"), _item(xml, "R1")
    assert item_zf is not None and item_zin is not None
    assert item_zf.findtext("angle") == "90"
    assert item_zin.findtext("angle") == "0"


# ── Contour et brochage reels (fidelite de forme) ────────────────────────────────

def test_generateur_ecrit_le_contour_reel_dune_instance():
    from circuit_analyzer.xml import _Generateur
    gen = _Generateur()
    cid = gen.ajouter('U', 'NE555', x=100, y=100,
                      primitives=[('polygon', [(-36, -48), (-36, 48), (36, 48), (36, -48)], False)],
                      pinout={'Vin+': ('L', -42), 'GND1': ('L', 42)})
    xml = gen.vers_xml()
    assert '<DataPolygon>' in xml
    assert '<X>-36</X><Y>-48</Y>' in xml  # contour reel present
    assert 'Vin+' in xml and 'GND1' in xml


def test_generateur_sans_contour_reel_comportement_inchange():
    from circuit_analyzer.xml import _Generateur
    gen = _Generateur()
    gen.ajouter('Résistance', '1k', x=100, y=100)
    xml = gen.vers_xml()
    assert '<Name>Résistance</Name>' in xml


def test_generateur_positionne_les_broches_dans_le_contour_reel():
    """Regression : sans w_exact/h_exact, `geometrie_libre` retombe sur son
    heuristique de remplissage et une broche peut se retrouver HORS du
    polygone reel (ecart constate en revue : Vin+ exporte a x=-44 alors que
    le contour reel s'arrete a x=-36). `_xml_composant` doit calculer la
    boite EXACTE via `etendue_primitives` avant d'appeler `geometrie_libre`."""
    import xml.etree.ElementTree as ET

    from circuit_analyzer.xml import _Generateur

    primitives = [('polygon', [(-36, -48), (-36, 48), (36, 48), (36, -48)], False)]
    gen = _Generateur()
    gen.ajouter('U', 'NE555', x=100, y=100, primitives=primitives,
               pinout={'Vin+': ('L', -42), 'GND1': ('L', 42)})
    root = ET.fromstring(gen.vers_xml())

    xs = [x for _, points, *_ in primitives for x, _y in points]
    ys = [y for _, points, *_ in primitives for _x, y in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    broches = root.findall('.//DataItem/datapin/DataPin/Pin')
    assert broches, "aucune broche exportee"
    for pin in broches:
        px, py = int(pin.findtext('X')), int(pin.findtext('Y'))
        assert xmin <= px <= xmax, f"broche hors du contour reel en X : {px} (attendu dans [{xmin};{xmax}])"
        assert ymin <= py <= ymax, f"broche hors du contour reel en Y : {py} (attendu dans [{ymin};{ymax}])"


def test_idx_broche_pinout_reel_route_le_bon_nom_de_broche():
    """`_idx_broche`, quand `comp.pinout` est fourni, doit indexer les
    broches du PINOUT REEL (pas de `_FORME`) -- sinon `.relier()` peut cabler
    un fil sur le mauvais `<DataPin>` sans qu'aucun test ne le remarque.
    Verifie que le NodeL du fil atterrit sur le <Pname> demande, et sur lui
    seul (les broches non reliees ne doivent porter aucune reference)."""
    import xml.etree.ElementTree as ET

    from circuit_analyzer.xml import _Generateur

    gen = _Generateur()
    c1 = gen.ajouter('U1', 'NE555', x=100, y=100,
                     primitives=[('polygon', [(-36, -48), (-36, 48), (36, 48), (36, -48)], False)],
                     pinout={'Vin+': ('L', -42), 'GND1': ('L', 42)})
    c2 = gen.ajouter('U2', 'NE555', x=300, y=100,
                     primitives=[('polygon', [(-36, -48), (-36, 48), (36, 48), (36, -48)], False)],
                     pinout={'A': ('L', -42), 'B': ('L', 42)})
    gen.relier(c1, 'GND1', c2, 'B')
    root = ET.fromstring(gen.vers_xml())
    items = root.findall('.//DataItem')

    def refs_de(item_idx, pname):
        item = items[item_idx]
        for dp in item.findall('./datapin/DataPin'):
            if dp.findtext('Pname') == pname:
                return {s.text for s in dp.findall('NodeL/string')}
        raise AssertionError(f"broche '{pname}' introuvable dans le DataItem {item_idx}")

    assert refs_de(0, 'GND1'), "GND1 (relie) n'a recu aucune reference de noeud"
    assert refs_de(1, 'B'), "B (relie) n'a recu aucune reference de noeud"
    assert not refs_de(0, 'Vin+'), "Vin+ (non relie) ne devrait porter aucune reference"
    assert not refs_de(1, 'A'), "A (non relie) ne devrait porter aucune reference"


def test_generer_xml_transporte_le_contour_dun_composant_analyse():
    """Verifie que generer_xml() accepte et ecrit les primitives/pinout reels
    fournis via Composant.primitives/pinout (Task 1) dans le XML (Task 4)."""
    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml

    comp = Composant(ref='U1', type='U', pins={'Vin+': 'N1', 'GND1': 'GND'},
                     value='',
                     primitives=[('polygon', [(-36, -48), (-36, 48), (36, 48), (36, -48)], False)],
                     pinout={'Vin+': ('L', -42), 'GND1': ('L', 42)})
    xml = generer_xml([comp])
    assert '<DataPolygon>' in xml
    assert 'Vin+' in xml


def test_generer_xml_pinout_reel_cable_le_bon_noeud_au_reimport():
    """Regression Task 7 (boucle visuelle) : le bouclage de cablage de
    generer_xml() calculait l'index de broche via le catalogue
    (`_idx_broche_forme`), qui ignore totalement `comp.pinout` -- alors que
    `_xml_composant` dessine les <DataPin> par NOM reel (ordre
    `sorted(comp.pinout)`, Task 4). Les deux desaccordaient : le `NodeL`
    d'un fil pouvait atterrir sur la mauvaise broche (ou aucune), corrompant
    la connectivite exportee pour tout composant a brochage reel. Round-trip
    complet generer_xml -> lire_xml : la connectivite broche<->net
    reimportee doit correspondre exactement a `comp.pins` d'origine, y
    compris pour le rail GND (bouclage broches d'alimentation)."""
    import os
    import tempfile

    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml, lire_xml

    u1 = Composant(ref='U1', type='U', value='',
                   pins={'Vin+': 'N1', 'Vin-': 'GND', 'GND1': 'GND', 'OUT': 'N2'},
                   primitives=[('polygon', [(-36, -48), (-36, 48), (36, 48), (36, -48)], False)],
                   pinout={'Vin+': ('L', -42), 'Vin-': ('L', -14),
                           'GND1': ('L', 14), 'OUT': ('R', 0)})
    r1 = Composant(ref='R1', type='R', value='10k', pins={'1': 'N1', '2': 'N3'})

    xml_texte = generer_xml([u1, r1])

    with tempfile.NamedTemporaryFile('w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(xml_texte)
        chemin = f.name
    try:
        relus = lire_xml(chemin)
    finally:
        os.unlink(chemin)

    # ref regeneree par compteur de type a la lecture (comportement du lecteur,
    # inchange par ce test) : <Name> porte desormais "U" (comp.type, ne
    # collisionne avec aucune entree catalogue, cf. generer_xml) plutot que
    # l'ancien "PuceN" -- correspondance is None des la 1ere passe -> type 'X'
    # (bucket "inconnu mais forme/brochage reels preserves"), donc "X1" et
    # non plus "U1". Seule la FIDELITE (broches/connectivite) nous interesse ici.
    relu_u1 = next(c for c in relus if c.type == 'X')
    relu_r1 = next(c for c in relus if c.ref == 'R1')

    # Memes noms de broches (plan de reimport passthrough, Puce catalogue).
    assert set(relu_u1.pins) == set(u1.pins), \
        f"noms de broches perdus/renommes au reimport : {relu_u1.pins}"

    # Vin+ (U1) et 1 (R1) partageaient le net N1 -> meme net apres reimport
    # (peu importe le libelle synthetique NETn attribue).
    assert relu_u1.pins['Vin+'] == relu_r1.pins['1'], \
        "Vin+/R1.1 ne partagent plus le meme noeud apres le round-trip"
    # OUT n'etait relie a rien d'autre : net distinct de Vin+.
    assert relu_u1.pins['OUT'] != relu_u1.pins['Vin+']
    # Vin-/GND1 partageaient le rail GND -> les deux doivent rester GND
    # (exerce la branche d'alimentation du bouclage de cablage).
    assert relu_u1.pins['Vin-'] == 'GND'
    assert relu_u1.pins['GND1'] == 'GND'


def test_generer_xml_pinout_reel_survit_a_deux_cycles_export_import():
    """Regression Task 7 finding #2 (boucle visuelle) : un composant catch-all
    a brochage reel (comp.pinout) voit son <Name> neutralise en "PuceN" a
    l'export (volontaire, cf. commentaire generer_xml ~ligne 1017, pour eviter
    toute collision avec un plan catalogue nomme au reimport). Mais ce
    "PuceN" resout lui-meme en ('U', {}) via _NOM_VERS_TYPE des le reimport
    -> la branche catch-all (qui seule declenche _forme_et_brochage_reels())
    etait sautee, et `primitives`/`pinout` disparaissaient des le premier
    aller-retour. Ce test enchaine DEUX cycles complets generer_xml ->
    lire_xml et verifie que la forme reelle et le brochage nomme survivent
    identiques aux deux etapes (pas seulement un aller simple)."""
    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml, lire_xml

    primitives = [('polygon', [(-36.0, -48.0), (-36.0, 48.0), (36.0, 48.0), (36.0, -48.0)], False)]
    pinout = {'Vin+': ('L', -40), 'GND1': ('L', -13), 'OUT': ('R', -13),
              'V+': ('R', 13), 'V-': ('R', 40), 'NC': ('L', 40)}
    u1 = Composant(ref='U1', type='U', value='A788J', boite_ic=True,
                   pins={n: f'N{i}' for i, n in enumerate(pinout)},
                   primitives=primitives, pinout=pinout)

    def _cycle(comp):
        xml_texte = generer_xml([comp])
        with tempfile.NamedTemporaryFile('w', suffix='.xml', delete=False,
                                          encoding='utf-8') as f:
            f.write(xml_texte)
            chemin = f.name
        try:
            relus = lire_xml(chemin)
        finally:
            os.unlink(chemin)
        return next(c for c in relus if c.type == 'U')

    u2 = _cycle(u1)
    assert u2.primitives is not None, "forme perdue des le premier aller-retour"
    assert u2.pinout is not None, "brochage reel perdu des le premier aller-retour"
    assert u2.boite_ic, "boite_ic doit rester vrai apres reimport"
    assert set(u2.pinout) == set(pinout), "noms de broches modifies au reimport"

    u3 = _cycle(u2)
    assert u3.primitives is not None, "forme perdue au second aller-retour"
    assert u3.pinout is not None, "brochage reel perdu au second aller-retour"
    assert u3.boite_ic, "boite_ic doit rester vrai apres le second reimport"
    assert set(u3.pinout) == set(pinout), "noms de broches modifies au second cycle"


def test_generer_xml_puce_generique_catalogue_ne_devient_pas_boite_ic():
    """Non-regression du correctif finding #2 : un composant catalogue
    authentique passe par le fallback DIP generique de generer_xml (spec
    catalogue absente, ligne ~1047-1060 -- ex. un transformateur/connecteur a
    broches numerotees, SANS comp.pinout/comp.primitives). Sa <value> est
    vide (aucun nom de piece connu). Le signal de reclassification (base sur
    le NOM des broches -- purement numeriques "1".."n" pour un catch-all
    catalogue authentique, pas sur elem['value']) ne doit PAS promouvoir ce
    composant en boite_ic -- seuls les vrais catch-all a brochage reel
    (noms de broches non numeriques) le doivent."""
    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml, lire_xml

    t1 = Composant(ref='T1', type='T', value='',
                   pins={str(i): f'N{i}' for i in range(1, 7)})

    xml_texte = generer_xml([t1])
    with tempfile.NamedTemporaryFile('w', suffix='.xml', delete=False,
                                      encoding='utf-8') as f:
        f.write(xml_texte)
        chemin = f.name
    try:
        relus = lire_xml(chemin)
    finally:
        os.unlink(chemin)

    relu_t1 = relus[0]
    assert relu_t1.boite_ic is False, \
        f"composant catalogue generique promu boite_ic a tort : {relu_t1}"
    assert relu_t1.primitives is None
    assert relu_t1.pinout is None


def test_xml_composant_ecrit_le_contour_dessine_sans_pinout_dinstance():
    """Critical 2 (revue finale round 1) : `_xml_composant` mettait toute
    l'emission du contour reel (`comp.primitives`) A L'INTERIEUR de
    `if comp.pinout:`. Un composant TYPE (ex. resistance) avec un contour
    dessine a la main (Task 6, `_entrer_dessin_forme`) mais SANS brochage
    libre d'instance (`comp.pinout is None`, le cas le plus courant du mode
    dessin) voyait son contour disparaitre totalement a l'export -- le XML
    reprenait la forme catalogue generique ("Résistance", coins a X=45/-45/
    80/-80) au lieu du contour reellement dessine."""
    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml

    contour = [('polygon', [(-20, -15), (-20, 15), (20, 15), (20, -15)], False)]
    r1 = Composant(ref='R1', type='R', pins={'1': 'N1', '2': 'N2'}, value='10k',
                   primitives=contour)  # pinout reste None : brochage catalogue
    xml_texte = generer_xml([r1])
    assert '<X>-20</X><Y>-15</Y>' in xml_texte, \
        "contour dessine absent de l'export (Critical 2)"
    assert '<X>45</X><Y>-22</Y>' not in xml_texte, \
        "contour catalogue generique encore ecrit malgre le contour dessine"


def test_xml_composant_sans_pinout_reprojette_les_broches_catalogue_dans_le_contour_dessine():
    """Critical 2 (revue finale round 2, sous-point manque au round 1) :
    `_xml_composant` fait desormais primer `comp.primitives` sur le
    catalogue pour le CONTOUR meme sans `comp.pinout` -- mais les
    `<DataPin>` de cette meme branche `else` continuaient d'utiliser
    `_FORME[nom_forme]["pins"]` (coordonnees CATALOGUE, ex. Resistance
    +-80) SANS AUCUN rapport d'echelle avec `comp.primitives` (coordonnees
    EDITEUR, ex. +-20 dans ce test). Une broche catalogue finissait donc
    hors du polygone reellement dessine, systematiquement (tout composant
    catalogue a des coordonnees ~2x celles de l'editeur)."""
    import re

    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml

    contour = [('polygon', [(-20, -15), (-20, 15), (20, 15), (20, -15)], False)]
    r1 = Composant(ref='R1', type='R', pins={'1': 'N1', '2': 'N2'}, value='10k',
                   primitives=contour)  # pinout reste None : brochage catalogue
    xml_texte = generer_xml([r1])
    broches = re.findall(r'<Pin><X>(-?\d+)</X><Y>(-?\d+)</Y></Pin>', xml_texte)
    assert broches, "aucune broche trouvee dans le XML genere"
    for sx, sy in broches:
        x, y = int(sx), int(sy)
        assert -20 <= x <= 20 and -15 <= y <= 15, \
            f"broche catalogue hors du contour reellement dessine : ({x}, {y})"


def test_xml_composant_sans_pinout_reprojette_le_decalage_longitudinal_aussi():
    """Revue finale round 2 bis (re-revue de 951effb) : la reprojection du
    round 2 ne corrigeait que l'axe PERPENDICULAIRE (+-w2/+-h2 recalcules
    depuis le contour reel) -- le decalage LONGITUDINAL renvoye par
    `aimanter_bord` (calcule dans l'echelle CATALOGUE) etait reinjecte tel
    quel dans le contour reel. Invisible sur la Resistance du test
    precedent (ses deux broches catalogue ont un decalage nul), mais
    systematique des qu'une broche catalogue a un decalage non nul -- ex.
    Transistor 2N2B, broches C/E a Y=+-48 catalogue."""
    import re

    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml

    contour = [('polygon', [(-20, -15), (-20, 15), (20, 15), (20, -15)], False)]
    q1 = Composant(ref='Q1', type='Q', pins={'B': 'N1', 'C': 'N2', 'E': 'N3'},
                   value='2N2222', primitives=contour)  # pinout reste None
    xml_texte = generer_xml([q1])
    broches = re.findall(r'<Pin><X>(-?\d+)</X><Y>(-?\d+)</Y></Pin>', xml_texte)
    assert len(broches) == 3, "les 3 broches du transistor doivent etre exportees"
    for sx, sy in broches:
        x, y = int(sx), int(sy)
        assert -20 <= x <= 20 and -15 <= y <= 15, \
            f"broche catalogue hors du contour reellement dessine : ({x}, {y})"


def test_generer_xml_puce_generique_valeur_non_vide_ne_devient_pas_boite_ic():
    """Important 5 (revue finale round 1) : le garde d'origine (`value` +
    seuil >=6, commit 6f635aa) promouvait a tort en boite_ic un composant
    catalogue AUTHENTIQUE (jamais eu de comp.pinout/comp.primitives) des que
    sa `value` d'origine ne matchait aucun alias catalogue -- cas courant
    d'un transfo/connecteur (ex. '230V-12V'). Le nouveau garde (noms de
    broches, pas `value`) ne doit PLUS promouvoir ce cas : les <Pname>
    ecrits par la branche catalogue de `_xml_composant` sont TOUJOURS les
    chaines numeriques "1".."n" de `_FORME[nom_forme]["pins"]`."""
    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml, lire_xml

    t1 = Composant(ref='T1', type='T', value='230V-12V',
                   pins={str(i): f'N{i}' for i in range(1, 7)})

    xml_texte = generer_xml([t1])
    with tempfile.NamedTemporaryFile('w', suffix='.xml', delete=False,
                                      encoding='utf-8') as f:
        f.write(xml_texte)
        chemin = f.name
    try:
        relus = lire_xml(chemin)
    finally:
        os.unlink(chemin)

    relu_t1 = relus[0]
    assert relu_t1.boite_ic is False, \
        f"composant catalogue generique (value non catalogue) promu boite_ic a tort : {relu_t1}"
    assert relu_t1.primitives is None
    assert relu_t1.pinout is None


def test_generer_xml_connecteur_j_moins_de_6_broches_survit_a_l_aller_retour():
    """Important 6 (revue finale round 1) : le seuil `>=6` (herite du garde
    de PREMIER import, pense pour distinguer IC vs. passif) bloquait a tort
    la reclassification de tout catch-all a MOINS de 6 broches -- notamment
    un connecteur J reel a contour dessine (explicitement dans le perimetre
    du plan). Avec le nouveau garde (noms de broches non-numeriques, pas de
    seuil de compte), ce connecteur 4 broches doit desormais survivre a un
    aller-retour export/import (contour + brochage reels preserves)."""
    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml, lire_xml

    primitives = [('polygon', [(-20.0, -30.0), (-20.0, 30.0),
                               (20.0, 30.0), (20.0, -30.0)], False)]
    pinout = {'A': ('L', -15), 'B': ('L', 15), 'C': ('R', -15), 'D': ('R', 15)}
    j1 = Composant(ref='J1', type='J', value='CONN4', boite_ic=True,
                   pins={n: f'N{i}' for i, n in enumerate(pinout)},
                   primitives=primitives, pinout=pinout)

    xml_texte = generer_xml([j1])
    with tempfile.NamedTemporaryFile('w', suffix='.xml', delete=False,
                                      encoding='utf-8') as f:
        f.write(xml_texte)
        chemin = f.name
    try:
        relus = lire_xml(chemin)
    finally:
        os.unlink(chemin)

    relu_j1 = relus[0]
    assert relu_j1.primitives is not None, \
        "contour reel perdu des le premier aller-retour (< 6 broches)"
    assert relu_j1.pinout is not None, \
        "brochage reel perdu des le premier aller-retour (< 6 broches)"
    assert set(relu_j1.pinout) == set(pinout), "noms de broches modifies au reimport"
    # <Name> porte desormais "J" (comp.type) plutot que l'ancien "PuceN" --
    # correspondance is None des la 1ere passe (aucune heuristique sur les
    # noms de broches necessaire, y compris pour un connecteur A/B/C/D non-
    # numerique) -> type 'X', pas de boite_ic (bucket "inconnu mais forme/
    # brochage reels preserves", coherent avec le traitement d'un composant
    # vraiment etranger). Seule la fidelite de forme/brochage nous interesse.
    assert relu_j1.type == 'X'


def test_generer_xml_pinout_reel_a_noms_numeriques_survit_au_reimport():
    """Regression trouvee en testant un vrai type custom de bibliotheque
    (AMP « Ampoule », component_library.json) : un composant a brochage reel
    (comp.pinout) dont TOUTES les broches portent des noms numeriques ('1',
    '2' -- le cas COURANT d'un type dessine sans renommer ses broches, pas
    un cas marginal) etait renomme "PuceN" a l'export (neutralisation
    volontaire, cf. commentaire generer_xml). Au reimport, "PuceN" resout
    EN PREMIER via _NOM_VERS_TYPE (catalogue) -> le garde de reclassification
    catch-all (`elem['pins'] tous numeriques -> pas reclassifie`, compromis
    documente) rate ce cas precisement PARCE QUE ses broches sont numeriques
    -- fail-closed silencieux, forme et brochage perdus, triangle AOP
    generique au reimport. Le vrai fix : ne PAS neutraliser en "PuceN" du
    tout quand un nom stable et non-catalogue existe (`comp.type`) -- le nom
    d'origine renvoie alors `correspondance is None` des la premiere passe,
    qui capture INCONDITIONNELLEMENT le contour/brochage reels (aucune
    heuristique sur les noms de broches necessaire)."""
    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml, lire_xml

    amp = Composant(ref='AMP1', type='AMP', value='',
                    pins={'1': 'N1', '2': 'N2'},
                    primitives=[('line', [(-80.0, 0.0), (-30.0, 0.0)], 2)],
                    pinout={'1': ('R', 0), '2': ('L', 0)})

    xml_texte = generer_xml([amp])
    with tempfile.NamedTemporaryFile('w', suffix='.xml', delete=False,
                                      encoding='utf-8') as f:
        f.write(xml_texte)
        chemin = f.name
    try:
        relus = lire_xml(chemin)
    finally:
        os.unlink(chemin)

    relu = relus[0]
    assert relu.primitives is not None, \
        "forme reelle perdue au reimport (broches numeriques)"
    assert relu.pinout is not None and set(relu.pinout) == {'1', '2'}, \
        "brochage reel perdu au reimport (broches numeriques)"
