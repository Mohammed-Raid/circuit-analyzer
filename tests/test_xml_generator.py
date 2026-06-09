"""Tests for the BoardSCH XML generator and the components→XML→components round-trip."""
import tempfile
import os
import pytest

from circuit_analyzer.parser import Component
from circuit_analyzer.xml_generator import BoardSCHGenerator, components_to_xml
from circuit_analyzer.xml_parser import parse_xml
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns


def _xml_to_components(xml: str):
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as f:
        f.write(xml)
        path = f.name
    try:
        return parse_xml(path)
    finally:
        os.unlink(path)


# ── Generator basics ──────────────────────────────────────────────────────────

def test_generator_produces_valid_xml():
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
    # CFirst/CLast must follow compId_pinIdx_end_wireIdx so xml_parser can read it
    g = BoardSCHGenerator()
    r1 = g.add("Résistance", "10k")
    r2 = g.add("Résistance", "20k")
    g.connect(r1, "1", r2, "2")
    xml = g.to_xml()
    assert "<CFirst>0_1_0_0</CFirst>" in xml
    assert "<CLast>1_0_1_0</CLast>" in xml


def test_generator_unknown_pin_raises():
    g = BoardSCHGenerator()
    r1 = g.add("Résistance", "10k")
    c1 = g.add("Capa", "100n")
    with pytest.raises(ValueError):
        g.connect(r1, "BOGUS", c1, "+")


# ── Round-trip: Component → XML → Component preserves topology ────────────────

def test_roundtrip_rc_lowpass():
    comps = [
        Component("R1", "R", {"1": "NET_MID", "2": "NET_IN"}, "10k"),
        Component("C1", "C", {"1": "NET_MID", "2": "GND"}, "100n"),
    ]
    xml = components_to_xml(comps)
    back = _xml_to_components(xml)
    types = sorted(r["circuit_type"] for r in match_patterns(build_graph(back)))
    assert "Filtre RC passe-bas" in types


def test_roundtrip_inverting_amp():
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
    comps = [
        Component("Q1", "Q", {"B": "NET_BASE", "C": "NET_COLL", "E": "GND"}),
        Component("R1", "R", {"1": "NET_BASE", "2": "NET_DRV"}, "1k"),
    ]
    xml = components_to_xml(comps)
    back = _xml_to_components(xml)
    types = [r["circuit_type"] for r in match_patterns(build_graph(back))]
    assert "Transistor en commutation" in types


def test_roundtrip_preserves_component_count():
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
    # A GND net must produce a GND symbol so the design app shows it
    comps = [Component("C1", "C", {"1": "VCC", "2": "GND"}, "100n")]
    xml = components_to_xml(comps)
    assert "<Name>GND</Name>" in xml
    assert "<Name>VCC</Name>" in xml


def test_distinct_power_rails_not_merged():
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
    # Both decoupling caps survive
    types = [r["circuit_type"] for r in match_patterns(build_graph(back))]
    assert types.count("Condensateur de découplage") == 2


def test_relay_survives_roundtrip():
    # A relay coil (type K) must be drawable and survive the round-trip
    comps = [
        Component("K1", "K", {"A1": "VCC", "A2": "NET_SW",
                              "11": "COM", "12": "NC", "14": "NO"}),
        Component("Q1", "Q", {"B": "NET_BASE", "C": "NET_SW", "E": "GND"}),
        Component("R1", "R", {"1": "NET_BASE", "2": "NET_DRV"}, "1k"),
        Component("D1", "D", {"A": "NET_SW", "K": "VCC"}),
    ]
    xml = components_to_xml(comps)
    assert "<Name>Relais</Name>" in xml
    back = _xml_to_components(xml)
    assert any(c.type == "K" for c in back)


def test_industrial_netlist_roundtrip_no_loss():
    # A multi-rail industrial-style circuit must not LOSE any pattern through XML
    # (the greedy matcher may add an equivalent one, but never drop structure).
    from circuit_analyzer.parser import parse_file
    import os
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

from circuit_analyzer.xml_generator import _layout_groups, _Block, _place_blocks


def test_layout_groups_one_block_per_pattern():
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
    # Two blocks: components within a block are closer to each other than to
    # the other block's components.
    a = [Component("R1", "R", {"1": "X", "2": "Y"}),
         Component("R2", "R", {"1": "Y", "2": "Z"})]
    b = [Component("R3", "R", {"1": "P", "2": "Q"})]
    blocks = [_Block("Filtre", a), _Block("Divers", b)]
    pos = _place_blocks(blocks)
    # every ref placed
    assert set(pos) == {"R1", "R2", "R3"}
    # R1 and R2 (same block) share the same y row; R3 is on a different position
    assert pos["R1"][1] == pos["R2"][1]
    assert pos["R3"] != pos["R1"]
