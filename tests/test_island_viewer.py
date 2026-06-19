from circuit_analyzer.composant import Composant, construire_graphe
from gui.circuit_viewer import (
    _build_island_model,
    _build_dipole_model,
    _build_island_schematic_plan,
    _make_island_fig,
)


def _comp_info(composants):
    return {
        c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
        for c in composants
    }


def _unit(ref, typ, pins, value="", symbol=None, refs=None, composition=None):
    """Fabrique une unite de modele (bypass la reduction) pour tester le layout pur."""
    return {
        "ref": ref, "type": typ, "value": value, "pins": pins,
        "symbol": symbol, "refs": refs or [ref], "composition": composition or ref,
    }


# ── Modele d'ilot au niveau Z (graphe reduit) ─────────────────────────────────

def test_island_model_reduces_passives_to_z_and_keeps_devices():
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "MID"}, "10k"),
        Composant("C1", "C", {"1": "MID", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "MID", "IN-": "GND", "OUT": "OUT"}),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot 1", "composants": ["R1", "C1", "U1"]}

    model = _build_island_model(ilot, graphe, _comp_info(composants))

    zs = [u for u in model["components"] if u["type"] == "Z"]
    assert len(zs) == 2                                  # R1 et C1 -> deux Z
    assert all(u["symbol"] == "impedance" for u in zs)
    # chaque Z porte ses composants bruts (drill-down)
    all_refs = {r for u in zs for r in u["refs"]}
    assert all_refs == {"R1", "C1"}
    # U1 reste un composant multi-broches
    devices = [u for u in model["components"] if u["type"] == "U"]
    assert len(devices) == 1 and len(devices[0]["pins"]) >= 3


def test_island_model_combines_series_passives_into_one_z():
    # C3 -- N -- R8 : N de degre 2 -> serie fusionnee en un seul Z
    composants = [
        Composant("C3", "C", {"1": "GND", "2": "N"}, "1u"),
        Composant("R8", "R", {"1": "N", "2": "OUT"}, "1k"),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "I", "composants": ["C3", "R8"]}

    model = _build_island_model(ilot, graphe, _comp_info(composants))

    zs = [u for u in model["components"] if u["type"] == "Z"]
    assert len(zs) == 1
    assert set(zs[0]["refs"]) == {"C3", "R8"}


def test_dipole_model_exposes_raw_components_with_real_symbols():
    composants = [
        Composant("C3", "C", {"1": "GND", "2": "N"}, "1u"),
        Composant("R8", "R", {"1": "N", "2": "OUT"}, "1k"),
    ]
    graphe = construire_graphe(composants)

    model = _build_dipole_model(["C3", "R8"], graphe, _comp_info(composants))

    refs = [u["ref"] for u in model["components"]]
    assert refs == ["C3", "R8"]
    syms = {u["ref"]: u["symbol"] for u in model["components"]}
    assert syms["C3"] == "capacitor"
    assert syms["R8"] == "resistor"


# ── Plan / layout pur (unites construites directement) ────────────────────────

def test_plan_drops_nc_and_classifies_stub_vs_column():
    model = {"label": "I", "components": [
        _unit("Z1", "Z", {"1": "IN", "2": "MID"}),
        _unit("Z2", "Z", {"1": "MID", "2": "GND"}),
        _unit("U1", "U", {"IN+": "MID", "IN-": "FB", "OUT": "NC"}),
    ]}

    plan = _build_island_schematic_plan(model)

    col_nets = {c["net"] for c in plan["columns"]}
    assert "NC" not in col_nets
    assert "MID" in col_nets                 # MID touche Z1, Z2, U1 -> colonne
    assert "IN" not in col_nets              # 1 connexion -> stub
    z1 = next(r for r in plan["rows"] if r["ref"] == "Z1")
    assert ("1", "IN") in z1["stubs"]
    u1 = next(r for r in plan["rows"] if r["ref"] == "U1")
    assert all(net != "NC" for _pin, net in u1["stubs"])


def test_columns_ordered_ground_left_power_right_and_trimmed():
    model = {"label": "I", "components": [
        _unit("Z1", "Z", {"1": "VCC", "2": "AAA"}),
        _unit("Z2", "Z", {"1": "AAA", "2": "OUT"}),
        _unit("Z3", "Z", {"1": "OUT", "2": "GND"}),
        _unit("Z4", "Z", {"1": "GND", "2": "VCC"}),
    ]}

    plan = _build_island_schematic_plan(model)
    xs = {c["net"]: c["x"] for c in plan["columns"]}
    by_net = {c["net"]: c for c in plan["columns"]}

    assert xs["GND"] == min(xs.values())     # masse a gauche
    assert xs["VCC"] == max(xs.values())     # alim a droite
    assert by_net["AAA"]["y_top"] == 0.0     # extent rogne sur Z1 (y=0) et Z2 (y=-2.0)
    assert by_net["AAA"]["y_bottom"] == -2.0


def test_opamp_symbol_and_rows_do_not_overlap():
    model = {"label": "I", "components": [
        _unit("Z1", "Z", {"1": "IN", "2": "MID"}),
        _unit("Z2", "Z", {"1": "MID", "2": "GND"}),
        _unit("U1", "U", {"IN+": "MID", "IN-": "GND", "OUT": "MID"}),
    ]}

    plan = _build_island_schematic_plan(model)

    by_ref = {r["ref"]: r for r in plan["rows"]}
    assert by_ref["U1"]["symbol"] == "opamp"
    assert by_ref["Z1"]["symbol"] == "impedance"
    ys = [r["y"] for r in plan["rows"]]
    assert ys == sorted(ys, reverse=True)
    assert all(abs(a - b) >= 2.0 for a, b in zip(ys, ys[1:]))   # pas mini = ROW_PITCH


def test_row_gap_widens_for_rows_carrying_a_value():
    # Deux dipoles SANS valeur -> pas = ROW_PITCH (2.0).
    # Deux dipoles AVEC valeur -> pas = ROW_PITCH + LABEL_LINE (2.5).
    sans = {"label": "I", "components": [
        _unit("Z1", "Z", {"1": "A", "2": "B"}),
        _unit("Z2", "Z", {"1": "A", "2": "B"}),
    ]}
    avec = {"label": "I", "components": [
        _unit("Z1", "Z", {"1": "A", "2": "B"}, value="10k"),
        _unit("Z2", "Z", {"1": "A", "2": "B"}, value="1k"),
    ]}

    ys_sans = [r["y"] for r in _build_island_schematic_plan(sans)["rows"]]
    ys_avec = [r["y"] for r in _build_island_schematic_plan(avec)["rows"]]

    assert abs(ys_sans[0] - ys_sans[1]) == 2.0   # ROW_PITCH
    assert abs(ys_avec[0] - ys_avec[1]) == 2.5   # ROW_PITCH + LABEL_LINE


# ── Rendu figure ──────────────────────────────────────────────────────────────

def test_make_island_fig_draws_z_dipoles_and_caption():
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "OUT"}, "10k"),
        Composant("C1", "C", {"1": "OUT", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "OUT", "IN-": "GND", "OUT": "AMP"}),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot 1", "composants": ["R1", "C1", "U1"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    fig = _make_island_fig(model)

    assert fig.axes
    texts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any(t.startswith("Z") for t in texts)        # dipoles Z affiches
    assert any("U1" in t for t in texts)                # AOP affiche
    assert any("connexion" in t for t in texts)         # legende


def test_make_island_fig_keeps_diode_and_does_not_show_match_type():
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
    texts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("D1" in t for t in texts)                # diode conservee
    assert any(t.startswith("Z") for t in texts)        # R1 -> Z
    assert not any("Redresseur simple alternance" in t for t in texts)


def test_make_island_fig_records_clickable_z_hitboxes():
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "MID"}, "10k"),
        Composant("C1", "C", {"1": "MID", "2": "GND"}, "100n"),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "I", "composants": ["R1", "C1"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    fig = _make_island_fig(model)

    hits = getattr(fig, "_z_hitboxes", [])
    assert hits                                          # au moins un Z cliquable
    # chaque zone porte (x0,x1,y0,y1, refs, composition) et couvre R1 et C1
    all_refs = {r for *_box, refs, _compo in hits for r in refs}
    assert {"R1", "C1"} <= all_refs
    for x0, x1, y0, y1, _refs, _compo in hits:
        assert x0 < x1 and y0 < y1                       # zone non vide


def test_make_island_fig_single_axis_with_devices_and_z():
    composants = [
        Composant("K1", "K", {"A1": "VCC", "A2": "NET1"}, "Relay"),
        Composant("Q1", "Q", {"B": "CMD", "C": "NET1", "E": "GND"}, "2N2222"),
        Composant("R1", "R", {"1": "CMD", "2": "GND"}, "10k"),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot 1 - commutation", "composants": ["K1", "Q1", "R1"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    fig = _make_island_fig(model)

    assert len(fig.axes) == 1
    texts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("Q1" in t for t in texts)                # transistor
    assert any(t.startswith("Z") for t in texts)        # R1 -> Z


def test_dipoles_sharing_a_column_pair_are_contiguous():
    # Za et Zc relient la meme paire {A,B} ; Zb relie {B,C2}. Entrelaces dans
    # l'ordre du modele -> doivent etre regroupes (anti-escalier).
    model = {"label": "I", "components": [
        _unit("Za", "Z", {"1": "A", "2": "B"}),
        _unit("Zb", "Z", {"1": "B", "2": "C2"}),
        _unit("Zc", "Z", {"1": "A", "2": "B"}),
        _unit("Zd", "Z", {"1": "C2", "2": "A"}),  # rend C2 colonne (2 connexions)
    ]}

    plan = _build_island_schematic_plan(model)

    order = [r["ref"] for r in plan["rows"]]
    assert abs(order.index("Za") - order.index("Zc")) == 1   # meme paire -> adjacents


def test_multi_pin_devices_are_ordered_after_dipoles():
    model = {"label": "I", "components": [
        _unit("U1", "U", {"IN+": "A", "IN-": "B", "OUT": "C2"}),
        _unit("Za", "Z", {"1": "A", "2": "B"}),
    ]}

    plan = _build_island_schematic_plan(model)

    order = [r["ref"] for r in plan["rows"]]
    assert order.index("Za") < order.index("U1")


def test_net_labels_are_offset_from_symbols():
    # Garde-fou de non-regression : un rendu avec moignons E/S et AOP ne doit pas
    # lever, et tous les noms de net attendus doivent etre presents (decales).
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "MID"}, "10k"),
        Composant("C1", "C", {"1": "MID", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "MID", "IN-": "GND", "OUT": "OUT"}),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "I", "composants": ["R1", "C1", "U1"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    fig = _make_island_fig(model)

    texts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("IN" in t for t in texts)     # net moignon affiche
    assert any("OUT" in t for t in texts)    # net moignon de l'AOP affiche
