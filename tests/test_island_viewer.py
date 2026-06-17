from circuit_analyzer.composant import Composant, construire_graphe
from gui.circuit_viewer import _build_island_model


def test_build_island_model_keeps_real_components_and_nets():
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "OUT"}, "10k"),
        Composant("C1", "C", {"1": "OUT", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "OUT", "IN-": "REF", "OUT": "AMP_OUT"}),
    ]
    graphe = construire_graphe(composants)
    comp_info = {
        c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
        for c in composants
    }
    ilot = {"label": "Ilot 1 - filtrage", "composants": ["R1", "C1"]}

    model = _build_island_model(ilot, graphe, comp_info)

    assert [c["ref"] for c in model["components"]] == ["C1", "R1"]
    assert model["internal_nets"] == ["IN", "OUT"]
    assert model["rail_nets"] == ["GND"]
    assert ("R1", "IN") in model["links"]
    assert ("R1", "OUT") in model["links"]
    assert ("C1", "OUT") in model["links"]
    assert ("C1", "GND") in model["links"]
    assert all(ref != "U1" for ref, _ in model["links"])
