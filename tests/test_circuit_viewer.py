"""@file test_circuit_viewer.py
@brief Tests du builder de figure (passe-plat des zones cliquables Z)."""
from gui import circuit_viewer as cv


def test_make_fig_remonte_les_hitboxes_du_drawer():
    def _faux_drawer(d, result, ci):
        d._z_hitboxes.append((0.0, 1.0, 0.0, 1.0, ["R1"], "R1"))
    fig = cv._make_fig({"circuit_type": "X", "components": []}, {}, _faux_drawer)
    assert getattr(fig, "_z_hitboxes", None) == [(0.0, 1.0, 0.0, 1.0, ["R1"], "R1")]


def test_make_fig_sans_hitbox_liste_vide():
    fig = cv._make_fig({"circuit_type": "X", "components": []}, {}, None)
    assert fig._z_hitboxes == []


def test_z_label_composant_unique_montre_la_valeur():
    z = {"refs": ["R4"], "composition": "R4"}
    ci = {"R4": {"type": "R", "value": "22k"}}
    assert cv._z_label("Zf", z, ci) == "Zf\nR4 = 22 kΩ"


def test_z_label_composite_reste_symbolique():
    z = {"refs": ["R1", "C1", "R2"], "composition": "R1+(C1//R2)"}
    out = cv._z_label("Zin", z, {})
    assert out == "Zin\nR1+(C1//R2)"


def test_texte_gain_resistif_affiche_le_nombre():
    from circuit_analyzer.composant import Composant, construire_graphe
    g = construire_graphe([
        Composant("Rin", "R", {"1": "A", "2": "B"}, "1k"),
        Composant("Rf", "R", {"1": "B", "2": "C"}, "10k"),
    ])
    result = {"gain": "−Zf/Zin",
              "impedances": {"Zin": {"composition": "Rin"},
                             "Zf": {"composition": "Rf"}}}
    assert cv._texte_gain(result, g) == "Av = −Zf/Zin = -10"


def test_texte_gain_sans_graph_reste_symbolique():
    result = {"gain": "−Zf/Zin",
              "impedances": {"Zin": {"composition": "Rin"},
                             "Zf": {"composition": "Rf"}}}
    assert cv._texte_gain(result, None) == "Av = −Zf/Zin"


def test_make_fig_affiche_astuce_clic_si_hitbox():
    def _faux_drawer(d, result, ci):
        d._z_hitboxes.append((0.0, 1.0, 0.0, 1.0, ["R1"], "R1"))
    fig = cv._make_fig({"circuit_type": "X", "components": []}, {}, _faux_drawer)
    textes = " ".join(t.get_text() for t in fig.axes[0].texts)
    assert "cliquez" in textes.lower()


def test_draw_inverting_amp_deux_boites_z():
    result = {
        "circuit_type": "Amplificateur inverseur (AOP)",
        "components": ["U1", "R1", "R2", "Rin"],
        "nodes": ["GND", "INM", "OUT"],
        "impedances": {
            "Zin": {"refs": ["Rin"], "composition": "Rin", "nodes": ("INM", "IN")},
            "Zf": {"refs": ["R1", "R2"], "composition": "R1+R2", "nodes": ("INM", "OUT")},
        },
        "gain": "−Zf/Zin",
    }
    fig = cv._make_fig(result, {}, cv._DRAWERS["Amplificateur inverseur (AOP)"])
    hb = fig._z_hitboxes
    assert len(hb) == 2
    refs = sorted((sorted(b[4]) for b in hb), key=len)
    assert refs[0] == ["Rin"]
    assert refs[1] == ["R1", "R2"]
