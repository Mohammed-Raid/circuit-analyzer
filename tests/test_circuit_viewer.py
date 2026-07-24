"""@file test_circuit_viewer.py
@brief Tests du builder de figure (passe-plat des zones cliquables Z)."""
import schemdraw
from schemdraw.segments import SegmentText

from gui import circuit_viewer as cv


def _textes_du_dessin(d):
    """@brief Tous les libellés texte présents dans un schemdraw.Drawing."""
    return [str(seg.text) for el in d.elements
            for seg in getattr(el, "segments", [])
            if isinstance(seg, SegmentText)]


def test_masse_dessinee_en_borne_nommee():
    """Choix patron (test14) : les masses ne sont PAS dessinées avec le symbole
    de terre ⏚ mais en bornes NOMMÉES, pour lire le nom de chaque rail et ne
    jamais confondre deux masses distinctes (VSS vs GND)."""
    for net in ("VSS", "GND", "AGND"):
        d = schemdraw.Drawing()
        cv._draw_net_end(d, net, at=(0, 0))
        assert net in _textes_du_dessin(d), f"{net} sans libellé"


def test_pas_de_symbole_de_terre_pour_une_masse():
    """Aucun élément schemdraw.Ground n'est émis pour une masse."""
    import schemdraw.elements as elm
    d = schemdraw.Drawing()
    cv._draw_net_end(d, "GND", at=(0, 0))
    assert not any(isinstance(el, elm.Ground) for el in d.elements)


def test_chaine_lineaire_rendue_en_ligne_horizontale():
    """Un diviseur VSS-R1-vout-R2-GND se dessine en LIGNE : trois bornes
    nommées alignées (même y), vout au milieu — pas un empilement en colonne."""
    model = {"label": "x", "components": [
        {"ref": "R1", "type": "R", "pins": {"1": "VSS", "2": "vout"}},
        {"ref": "R2", "type": "R", "pins": {"1": "vout", "2": "GND"}},
    ]}
    plan = cv._build_island_schematic_plan(model)
    assert {c["net"] for c in plan["columns"]} == {"VSS", "vout", "GND"}
    assert all(c.get("chaine") for c in plan["columns"])
    assert all(r["y"] == 0.0 for r in plan["rows"])        # une seule bande
    xs = {c["net"]: c["x"] for c in plan["columns"]}
    assert xs["vout"] == sorted(xs.values())[1]            # vout au milieu


def test_reseau_branche_n_est_pas_une_chaine():
    """Trois dipôles sur un nœud commun = branche, pas une chaîne linéaire :
    on retombe sur la disposition en colonnes classique."""
    model = {"label": "x", "components": [
        {"ref": "R1", "type": "R", "pins": {"1": "A", "2": "N"}},
        {"ref": "R2", "type": "R", "pins": {"1": "N", "2": "B"}},
        {"ref": "R3", "type": "R", "pins": {"1": "N", "2": "C"}},
    ]}
    plan = cv._build_island_schematic_plan(model)
    assert not any(c.get("chaine") for c in plan["columns"])


def test_draw_sommateur_n_plus_un_boites_z():
    result = {
        "circuit_type": "Amplificateur sommateur (AOP)",
        "components": ["U1", "Rf", "R1", "R2", "R3"],
        "nodes": ["GND", "INM", "OUT"],
        "impedances": {
            "Zf": {"refs": ["Rf"], "composition": "Rf", "nodes": ("INM", "OUT")},
            "Zin": [
                {"refs": ["R1"], "composition": "R1", "nodes": ("INM", "IN1")},
                {"refs": ["R2"], "composition": "R2", "nodes": ("INM", "IN2")},
                {"refs": ["R3"], "composition": "R3", "nodes": ("INM", "IN3")},
            ],
        },
        "gain": "−Σ Zf/Zk",
    }
    fig = cv._make_fig(result, {}, cv._DRAWERS["Amplificateur sommateur (AOP)"])
    assert len(fig._z_hitboxes) == 4   # Zf + 3 entrées
    refs = sorted(b[4][0] for b in fig._z_hitboxes)
    assert refs == ["R1", "R2", "R3", "Rf"]


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
    # L'astuce est posee en coords figure (sous le trace) pour ne pas chevaucher
    # un label bas du dessin -> elle vit dans fig.texts, pas dans l'axe.
    textes = " ".join(t.get_text() for t in (*fig.texts, *fig.axes[0].texts))
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


def test_draw_differentiel_quatre_boites_z():
    result = {
        "circuit_type": "Amplificateur différentiel (AOP)",
        "components": ["U1", "R1", "Rf", "R3", "Rg"],
        "nodes": ["INP", "INM", "OUT"],
        "impedances": {
            "Z1": {"refs": ["R1"], "composition": "R1", "nodes": ("INM", "IN1")},
            "Zf": {"refs": ["Rf"], "composition": "Rf", "nodes": ("INM", "OUT")},
            "Z3": {"refs": ["R3"], "composition": "R3", "nodes": ("INP", "IN2")},
            "Zg": {"refs": ["Rg"], "composition": "Rg", "nodes": ("INP", "GND")},
        },
        "gain": "Zf/Z1 · (V2−V1)",
    }
    fig = cv._make_fig(result, {}, cv._DRAWERS["Amplificateur différentiel (AOP)"])
    assert len(fig._z_hitboxes) == 4
    refs = sorted(b[4][0] for b in fig._z_hitboxes)
    assert refs == ["R1", "R3", "Rf", "Rg"]


def test_draw_schmitt_deux_boites_z():
    result = {
        "circuit_type": "Bascule de Schmitt (AOP)",
        "components": ["U1", "Rf", "Rin"],
        "nodes": ["INP", "REF", "OUT"],
        "impedances": {
            "Zf": {"refs": ["Rf"], "composition": "Rf", "nodes": ("INP", "OUT")},
            "Zin": {"refs": ["Rin"], "composition": "Rin", "nodes": ("INP", "IN")},
        },
        "gain": "hystérésis ±Vsat·Zin/(Zin+Zf)",
    }
    fig = cv._make_fig(result, {}, cv._DRAWERS["Bascule de Schmitt (AOP)"])
    assert len(fig._z_hitboxes) == 2
    refs = sorted(b[4][0] for b in fig._z_hitboxes)
    assert refs == ["Rf", "Rin"]


def test_draw_comparateur_sans_hitbox():
    result = {
        "circuit_type": "Comparateur (AOP)",
        "components": ["U1"],
        "nodes": ["INP", "INM", "OUT"],
    }
    fig = cv._make_fig(result, {}, cv._DRAWERS["Comparateur (AOP)"])
    assert fig._z_hitboxes == []   # aucune impédance à driller
