"""@file test_detecteur_transistors.py
@brief Tests des detecteurs MOSFET (commutation, cote haut) : confiance aux
broches G/D/S nommees plutot qu'au type declare, et tolerance a une
resistance de sense/decouplage entre la source et la masse."""
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.detecteur import (
    detecter_mosfet_commutation,
    detecter_mosfet_cote_haut,
)


def _m(ref, type_, g, d, s):
    return Composant(ref=ref, type=type_, pins={"G": g, "D": d, "S": s}, value="")


def _r(ref, p1, p2):
    return Composant(ref=ref, type="R", pins={"1": p1, "2": p2}, value="1k")


def test_mosfet_type_x_avec_broches_gds_est_detecte():
    """@brief Cas reel trouve sur flyback.xml (X2) : type generique 'X',
    mais broches G/D/S nommees sans ambiguite -- source reliee a la masse
    via une seule resistance de sense (motif standard cote bas d'un
    convertisseur a decoupage)."""
    comps = [
        _m("X2", "X", "NET13", "NET3", "NET15"),
        _r("R4", "CMD", "NET13"),
        _r("R6", "NET15", "GND"),
    ]
    res = detecter_mosfet_commutation(construire_graphe(comps))
    types = [r["circuit_type"] for r in res]
    assert "MOSFET en commutation" in types
    match = next(r for r in res if r["circuit_type"] == "MOSFET en commutation")
    assert "X2" in match["components"]


def test_mosfet_type_m_source_directe_masse_toujours_detecte():
    """@brief Non-regression : le cas deja couvert (type 'M', source
    directement a la masse) reste identique."""
    comps = [
        _m("M1", "M", "NET1", "NET2", "GND"),
        _r("R1", "CMD", "NET1"),
    ]
    res = detecter_mosfet_commutation(construire_graphe(comps))
    types = [r["circuit_type"] for r in res]
    assert "MOSFET en commutation" in types


def test_mosfet_sans_broches_gds_nommees_ignore():
    """@brief Un composant type 'X' generique SANS broches G/D/S nommees
    (pins numeriques, ex. Q1/Q2 de flyback.xml) n'est pas un candidat --
    rien a matcher sans indice de brochage."""
    comps = [
        Composant(ref="Q1", type="Q", pins={"1": "A", "2": "B", "3": "C"}, value=""),
    ]
    res = detecter_mosfet_commutation(construire_graphe(comps))
    assert res == []


def test_mosfet_source_flottante_non_reliee_masse_ignore():
    """@brief La source n'atteint la masse ni directement ni via une seule
    resistance -- pas un interrupteur cote bas, ne doit rien matcher."""
    comps = [
        _m("X3", "X", "NET13", "NET3", "NET15"),
        _r("R4", "CMD", "NET13"),
        _r("R6", "NET15", "NET_AUTRE"),  # ne mene pas a la masse
    ]
    res = detecter_mosfet_commutation(construire_graphe(comps))
    assert res == []


def test_mosfet_source_masse_via_deux_resistances_en_serie_ignore():
    """@brief Volontairement hors perimetre : une CHAINE de 2+ resistances
    entre la source et la masse n'est pas suivie -- seul un unique saut est
    accepte, pour ne jamais matcher un diviseur resistif quelconque comme
    un interrupteur de puissance."""
    comps = [
        _m("X4", "X", "NET13", "NET3", "NET15"),
        _r("R4", "CMD", "NET13"),
        _r("R6", "NET15", "NET_INTERMEDIAIRE"),
        _r("R7", "NET_INTERMEDIAIRE", "GND"),
    ]
    res = detecter_mosfet_commutation(construire_graphe(comps))
    assert res == []


def test_mosfet_cote_haut_type_x_avec_broches_gds_est_detecte():
    """@brief Meme confiance aux broches nommees pour le detecteur cote
    haut : drain sur rail d'alimentation, source non reliee a la masse."""
    comps = [
        _m("X5", "X", "NET13", "VCC", "NET15"),
        _r("R4", "CMD", "NET13"),
    ]
    res = detecter_mosfet_cote_haut(construire_graphe(comps))
    types = [r["circuit_type"] for r in res]
    assert "MOSFET haute-tension (côté haut)" in types


def test_mosfet_cote_haut_exclut_si_source_masse_via_resistance():
    """@brief Coherence avec le detecteur cote bas : une source qui atteint
    la masse via une seule resistance (motif deja repris par le detecteur
    cote bas) ne doit jamais AUSSI matcher cote haut, meme si le drain est
    sur un rail d'alimentation."""
    comps = [
        _m("X6", "X", "NET13", "VCC", "NET15"),
        _r("R4", "CMD", "NET13"),
        _r("R6", "NET15", "GND"),
    ]
    res = detecter_mosfet_cote_haut(construire_graphe(comps))
    assert res == []
