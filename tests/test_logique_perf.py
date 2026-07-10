"""@file test_logique_perf.py
@brief Gardes de performance des portes CMOS : le détecteur en TÊTE du
matcher ne doit rien coûter aux corpus analogiques (garde zéro-M) et rester
linéaire sur un circuit de 500 portes (protège l'acquis 5000 comps ≈ 3,3 s)."""
import time

from circuit_analyzer import detecteur, logique
from circuit_analyzer.composant import Composant, construire_graphe


def _m(ref, g, d, s):
    return Composant(ref=ref, type="M", pins={"G": g, "D": d, "S": s}, value="")


def _circuit_500_portes():
    comps = []
    for k in range(500):                     # 500 NAND2 chaînés = 2000 MOSFET
        a = f"N{k}" if k else "A0"
        b = f"B{k}"
        out = f"N{k + 1}"
        x = f"X{k}"
        i0 = 4 * k + 1
        comps += [_m(f"M{i0}", a, out, "VDD"), _m(f"M{i0+1}", b, out, "VDD"),
                  _m(f"M{i0+2}", a, out, x), _m(f"M{i0+3}", b, x, "GND")]
    return comps


def test_garde_zero_m_est_immediate():
    comps = [Composant(ref=f"R{i}", type="R",
                       pins={"1": f"N{i}", "2": f"N{i+1}"}, value="1k")
             for i in range(2000)]
    graphe = construire_graphe(comps)
    debut = time.perf_counter()
    assert logique.detecter_portes_cmos(graphe) == []
    assert time.perf_counter() - debut < 0.2, "zero MOSFET = retour immediat"


def test_500_portes_sous_budget():
    graphe = construire_graphe(_circuit_500_portes())
    debut = time.perf_counter()
    matches = logique.detecter_portes_cmos(graphe)
    duree = time.perf_counter() - debut
    assert len(matches) == 500
    assert duree < 10.0, f"500 portes en {duree:.1f}s (budget 10 s)"
