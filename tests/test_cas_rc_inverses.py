"""@file test_cas_rc_inverses.py
@brief Tests des cas RC inverses autour de l'ampli inverseur AOP."""
import matplotlib
matplotlib.use("Agg")

from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer import detecteur


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
