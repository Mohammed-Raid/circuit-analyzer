"""@file test_cas_rc_inverses.py
@brief Tests des cas RC inverses autour de l'ampli inverseur AOP."""
import matplotlib

matplotlib.use("Agg")

import gui.circuit_viewer as cv
from circuit_analyzer import detecteur
from circuit_analyzer.composant import Composant, construire_graphe


def _rc():
    return {"R1": Composant("R1", "R", {}),
            "C1": Composant("C1", "C", {})}


def test_est_rc_serie_vrai():
    bloc = {"refs": ["R1", "C1"], "composition": "R1+C1"}
    assert detecteur._est_rc_serie(bloc, _rc())


def test_est_rc_serie_faux_si_parallele():
    bloc = {"refs": ["R1", "C1"], "composition": "R1//C1"}
    assert not detecteur._est_rc_serie(bloc, _rc())


def test_est_rc_parallele_vrai():
    bloc = {"refs": ["R1", "C1"], "composition": "R1//C1"}
    assert detecteur._est_rc_parallele(bloc, _rc())


def test_est_rc_parallele_faux_si_deux_r():
    comps = {"R1": Composant("R1", "R", {}),
             "R2": Composant("R2", "R", {})}
    bloc = {"refs": ["R1", "R2"], "composition": "R1//R2"}
    assert not detecteur._est_rc_parallele(bloc, comps)


def _types(comps):
    return [m["circuit_type"] for m in detecteur.analyser(construire_graphe(comps))]


def test_boost_hf_detecte():
    # Zin = Rin // Cin (parallele a l'entree), Zf = Rf -> boost HF.
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Cin", "C", {"1": "VIN", "2": "M"}, "100n"),
        Composant("Rf", "R", {"1": "M", "2": "VOUT"}, "100k"),
    ]
    assert "Ampli inverseur + boost HF (AOP)" in _types(comps)


def test_derivateur_ideal_inchange():
    # C seul a l'entree, Rf feedback -> reste Derivateur (pas boost HF).
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Cin", "C", {"1": "VIN", "2": "M"}, "100n"),
        Composant("Rf", "R", {"1": "M", "2": "VOUT"}, "100k"),
    ]
    t = _types(comps)
    assert "Dérivateur (AOP)" in t
    assert "Ampli inverseur + boost HF (AOP)" not in t


def test_inverseur_pur_inchange():
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Rf", "R", {"1": "M", "2": "VOUT"}, "100k"),
    ]
    t = _types(comps)
    assert "Amplificateur inverseur (AOP)" in t
    assert "boost HF" not in " ".join(t)


def test_action_integrale_detecte():
    # Zin = Rin, Zf = Rf + Cf en serie -> action integrale (PI).
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Rf", "R", {"1": "M", "2": "X"}, "10k"),
        Composant("Cf", "C", {"1": "X", "2": "VOUT"}, "100n"),
    ]
    assert "Ampli inverseur + action intégrale (AOP)" in _types(comps)


def test_integrateur_ideal_inchange():
    # Cf seul en feedback -> reste Integrateur (pas action integrale).
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Cf", "C", {"1": "M", "2": "VOUT"}, "100n"),
    ]
    t = _types(comps)
    assert "Intégrateur (AOP)" in t
    assert "action intégrale" not in " ".join(t)


def _ilot_fig(comps):
    g = construire_graphe(comps)
    res = detecteur.analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    p = cv._circuit_principal_ilot(ilot, g, res)
    return cv._make_fig(p, ci, cv._DRAWERS[p["circuit_type"]],
                        matches=cv._matches_for_island(ilot, res)), p


def test_boost_hf_rendu_cliquable():
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Cin", "C", {"1": "VIN", "2": "M"}, "100n"),
        Composant("Rf", "R", {"1": "M", "2": "VOUT"}, "100k"),
    ]
    fig, p = _ilot_fig(comps)
    assert p["circuit_type"] == "Ampli inverseur + boost HF (AOP)"
    assert len(fig._z_hitboxes) >= 2
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert not any("non disponible" in t for t in txts)


def test_role_etage_nouveaux_types():
    assert cv._ROLE_ETAGE["Ampli inverseur + boost HF (AOP)"]
    assert cv._ROLE_ETAGE["Ampli inverseur + action intégrale (AOP)"]
