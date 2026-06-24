"""@file test_chaine_ilot.py
@brief Vue îlot multi-AOP : ordonnancement par flux + chaîne de schémas connectés."""
from circuit_analyzer.xml import lire_xml
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser
from gui import circuit_viewer as cv


def _matches_chaine():
    comps = lire_xml("circuits_industriels/chaine_5_aop.xml")
    res = analyser(construire_graphe(comps))
    return [r for r in res if "(AOP)" in r["circuit_type"]]


def test_ordonner_montages_flux_chaine_5():
    ordre = cv._ordonner_montages_flux(_matches_chaine())
    assert ordre is not None
    types = [m["circuit_type"] for m in ordre]
    assert types == [
        "Amplificateur non-inverseur (AOP)",
        "Amplificateur inverseur (AOP)",
        "Intégrateur (AOP)",
        "Dérivateur (AOP)",
        "Suiveur de tension (AOP)",
    ]


def test_ordonner_montages_flux_non_chaine_renvoie_none():
    # Deux montages sans lien OUT->IN entre eux : pas une chaîne.
    from circuit_analyzer.composant import Composant
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M1", "OUT": "O1"}),
        Composant("R1", "R", {"1": "VIN", "2": "M1"}, "1k"),
        Composant("R2", "R", {"1": "M1", "2": "O1"}, "10k"),
        Composant("U2", "U", {"IN+": "GND", "IN-": "M2", "OUT": "O2"}),
        Composant("R3", "R", {"1": "AUTRE", "2": "M2"}, "1k"),
        Composant("R4", "R", {"1": "M2", "2": "O2"}, "10k"),
    ]
    res = analyser(construire_graphe(comps))
    aops = [r for r in res if "(AOP)" in r["circuit_type"]]
    assert cv._ordonner_montages_flux(aops) is None


import schemdraw


def _imp_inv():
    return {"Zin": {"refs": ["R3"], "composition": "R3", "nodes": ("M", "A")},
            "Zf": {"refs": ["R4"], "composition": "R4", "nodes": ("M", "B")}}


def test_drawer_inverseur_renvoie_ancres_et_suit_origin():
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        a0 = cv._draw_aop_inverseur_zin_zf(d, _imp_inv(), {}, origin=(0, 0))
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        a10 = cv._draw_aop_inverseur_zin_zf(d, _imp_inv(), {}, origin=(10, 0))
    assert set(a0) == {"in", "out"}
    assert a0["out"][0] > a0["in"][0]                 # OUT à droite de IN
    assert abs(a10["in"][0] - a0["in"][0] - 10) < 1e-6  # l'origine décale tout de +10


def test_draw_island_chain_hitboxes_et_ordre():
    comps = lire_xml("circuits_industriels/chaine_5_aop.xml")
    res = analyser(construire_graphe(comps))
    ci = {c.ref: {"type": c.type, "value": c.value} for c in comps}
    ordre = cv._ordonner_montages_flux([r for r in res if "(AOP)" in r["circuit_type"]])
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        cv._draw_island_chain(d, ordre, ci)
        hb = list(d._z_hitboxes)
    # non-inv(2) + inverseur(2) + intégrateur(2) + dérivateur(2) + suiveur(0) = 8
    assert len(hb) == 8
    xs = [(x0 + x1) / 2 for x0, x1, *_ in hb]
    assert max(xs) - min(xs) > 10
