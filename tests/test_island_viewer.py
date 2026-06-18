from circuit_analyzer.composant import Composant, construire_graphe
from gui.circuit_viewer import (
    _build_island_model,
    _build_island_schematic_plan,
    _make_island_fig,
)


def _comp_info(composants):
    return {
        c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
        for c in composants
    }


def test_build_island_model_keeps_real_components_and_nets():
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "OUT"}, "10k"),
        Composant("C1", "C", {"1": "OUT", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "OUT", "IN-": "REF", "OUT": "AMP_OUT"}),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot 1 - filtrage", "composants": ["R1", "C1"]}

    model = _build_island_model(ilot, graphe, _comp_info(composants))

    assert [c["ref"] for c in model["components"]] == ["C1", "R1"]
    assert model["internal_nets"] == ["IN", "OUT"]
    assert model["rail_nets"] == ["GND"]
    assert ("R1", "IN") in model["links"]
    assert ("R1", "OUT") in model["links"]
    assert ("C1", "OUT") in model["links"]
    assert ("C1", "GND") in model["links"]
    assert all(ref != "U1" for ref, _ in model["links"])


def test_plan_drops_nc_and_classifies_stub_vs_column():
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "MID"}, "10k"),
        Composant("R2", "R", {"1": "MID", "2": "GND"}, "10k"),
        Composant("U1", "U", {"IN+": "MID", "IN-": "FB", "OUT": "NC"}),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot", "composants": ["R1", "R2", "U1"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    plan = _build_island_schematic_plan(model)

    col_nets = {c["net"] for c in plan["columns"]}
    # NC : jamais de colonne
    assert "NC" not in col_nets
    # MID touche 3 broches -> colonne ; IN touche 1 broche -> stub
    assert "MID" in col_nets
    assert "IN" not in col_nets
    r1 = next(r for r in plan["rows"] if r["ref"] == "R1")
    assert ("1", "IN") in r1["stubs"]
    # NC ne doit pas devenir un stub non plus
    u1 = next(r for r in plan["rows"] if r["ref"] == "U1")
    assert all(net != "NC" for _pin, net in u1["stubs"])


def test_columns_ordered_ground_left_power_right_and_trimmed():
    composants = [
        Composant("R1", "R", {"1": "VCC", "2": "AAA"}, "10k"),
        Composant("R2", "R", {"1": "AAA", "2": "OUT"}, "10k"),
        Composant("R3", "R", {"1": "OUT", "2": "GND"}, "10k"),
        Composant("R4", "R", {"1": "GND", "2": "VCC"}, "10k"),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot", "composants": ["R1", "R2", "R3", "R4"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    plan = _build_island_schematic_plan(model)
    by_net = {c["net"]: c for c in plan["columns"]}
    xs = {c["net"]: c["x"] for c in plan["columns"]}

    # masse a gauche, alim a droite, malgre l'ordre alphabetique 'AAA' < 'GND'
    assert xs["GND"] == min(xs.values())
    assert xs["VCC"] == max(xs.values())
    # AAA connecte R1 (y=0) et R2 (y=-1.6) -> extent rogne sur ces deux lignes
    assert by_net["AAA"]["y_top"] == 0.0
    assert by_net["AAA"]["y_bottom"] == -1.6


def test_build_island_schematic_plan_keeps_exact_component_pin_nets():
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "MID"}, "10k"),
        Composant("C1", "C", {"1": "MID", "2": "GND"}, "100n"),
        Composant("D1", "D", {"A": "MID", "K": "OUT"}, "1N4148"),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot 1 - filtrage", "composants": ["R1", "C1", "D1"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    plan = _build_island_schematic_plan(model)

    # MID relie R1,C1,D1 (3) -> colonne ; GND/IN/OUT 1 connexion -> stub
    col_nets = {c["net"] for c in plan["columns"]}
    assert "MID" in col_nets
    by_ref = {r["ref"]: r for r in plan["rows"]}
    assert by_ref["R1"]["pins"] == [("1", "IN"), ("2", "MID")]
    assert by_ref["C1"]["pins"] == [("1", "MID"), ("2", "GND")]
    assert by_ref["D1"]["pins"] == [("A", "MID"), ("K", "OUT")]
    assert by_ref["R1"]["symbol"] == "resistor"
    assert by_ref["C1"]["symbol"] == "capacitor"
    assert by_ref["D1"]["symbol"] == "diode"


def test_opamp_symbol_and_rows_do_not_overlap():
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "MID"}, "10k"),
        Composant("C1", "C", {"1": "MID", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "MID", "IN-": "GND", "OUT": "MID"}),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot 1 - filtrage", "composants": ["R1", "C1", "U1"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    plan = _build_island_schematic_plan(model)

    by_ref = {r["ref"]: r for r in plan["rows"]}
    assert by_ref["U1"]["symbol"] == "opamp"
    assert by_ref["R1"]["symbol"] == "resistor"
    # lignes strictement decroissantes en y, espacees (pas de chevauchement)
    ys = [r["y"] for r in plan["rows"]]
    assert ys == sorted(ys, reverse=True)
    assert all(abs(a - b) >= 1.5 for a, b in zip(ys, ys[1:]))


def test_make_island_fig_draws_schematic_without_graph_bubbles():
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "OUT"}, "10k"),
        Composant("C1", "C", {"1": "OUT", "2": "GND"}, "100n"),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot 1 - filtrage", "composants": ["R1", "C1"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    fig = _make_island_fig(model)

    assert fig.axes
    texts = [text.get_text() for ax in fig.axes for text in ax.texts]
    assert any("R1" in text for text in texts)
    assert any("C1" in text for text in texts)
    assert not any("schema graphe" in text.lower() for text in texts)


def test_make_island_fig_ignores_matches_and_draws_real_netlist():
    composants = [
        Composant("D1", "D", {"A": "AC", "K": "DC"}, "1N4148"),
        Composant("R1", "R", {"1": "DC", "2": "GND"}, "1k"),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot 1 - redressement", "composants": ["D1", "R1"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))
    match = {
        "circuit_type": "Redresseur simple alternance",
        "components": ["D1", "R1"],
        "nodes": ["AC", "DC", "GND"],
    }

    fig = _make_island_fig(model, matches=[match])

    assert all(not ax.get_title() for ax in fig.axes)
    texts = [text.get_text() for ax in fig.axes for text in ax.texts]
    assert any("AC" in text for text in texts)
    assert any("DC" in text for text in texts)
    assert any("GND" in text for text in texts)
    assert any("D1" in text for text in texts)
    assert any("R1" in text for text in texts)
    assert not any("Redresseur simple alternance" in text for text in texts)


def test_make_island_fig_draws_each_real_component_once_even_with_matches():
    composants = [
        Composant("K1", "K", {"A1": "VCC", "A2": "NET1"}, "Relay"),
        Composant("Q1", "Q", {"B": "CMD", "C": "NET1", "E": "GND"}, "2N2222"),
        Composant("R1", "R", {"1": "CMD", "2": "GND"}, "10k"),
    ]
    graphe = construire_graphe(composants)
    ilot = {
        "label": "Ilot 1 - commutation",
        "composants": ["K1", "Q1", "R1"],
    }
    model = _build_island_model(ilot, graphe, _comp_info(composants))
    matches = [
        {
            "circuit_type": "Commande de relais",
            "components": ["K1", "Q1"],
            "nodes": ["VCC", "NET1"],
        },
        {
            "circuit_type": "Impedance Z",
            "components": ["R1"],
            "nodes": ["CMD", "GND"],
            "composition": "R1",
        },
    ]

    fig = _make_island_fig(model, matches=matches)

    assert len(fig.axes) == 1
    assert all(not ax.get_title() for ax in fig.axes)
    texts = [text.get_text() for ax in fig.axes for text in ax.texts]
    assert any("K1" in text for text in texts)
    assert any("Q1" in text for text in texts)
    assert any("R1" in text for text in texts)
    assert not any("Commande de relais" in text for text in texts)
    assert not any("Impedance Z" in text for text in texts)
