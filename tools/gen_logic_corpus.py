# @file gen_logic_corpus.py
# @brief Génère le corpus de portes CMOS (circuits_industriels/logic_*.xml)
# via circuit_analyzer.xml.generer_xml — relançable, déterministe.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuit_analyzer.composant import Composant
from circuit_analyzer.xml import generer_xml

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "circuits_industriels")


def _m(ref, g, d, s):
    return Composant(ref=ref, type="M", pins={"G": g, "D": d, "S": s}, value="")


def _r(ref, a, b, val="10k"):
    return Composant(ref=ref, type="R", pins={"1": a, "2": b}, value=val)


def _inverseur(prefixe, entree, sortie, i0=1):
    # Sources aux rails (critère D/S de la détection).
    return [_m(f"M{i0}", entree, sortie, "VDD"),
            _m(f"M{i0 + 1}", entree, sortie, "GND")]


def _nand2(entree_a, entree_b, sortie, i0=1, interne=None):
    interne = interne or f"X{i0}"
    return [_m(f"M{i0}", entree_a, sortie, "VDD"),
            _m(f"M{i0 + 1}", entree_b, sortie, "VDD"),
            _m(f"M{i0 + 2}", entree_a, sortie, interne),
            _m(f"M{i0 + 3}", entree_b, interne, "GND")]


def _nor2(entree_a, entree_b, sortie, i0=1, interne=None):
    interne = interne or f"P{i0}"
    return [_m(f"M{i0}", entree_a, "VDD", interne),
            _m(f"M{i0 + 1}", entree_b, interne, sortie),
            _m(f"M{i0 + 2}", entree_a, sortie, "GND"),
            _m(f"M{i0 + 3}", entree_b, sortie, "GND")]


CIRCUITS = {
    "logic_cmos_not.xml": _inverseur("", "A", "OUT"),
    "logic_cmos_nand2.xml": _nand2("A", "B", "OUT"),
    "logic_cmos_nand3.xml": [
        _m("M1", "A", "OUT", "VDD"), _m("M2", "B", "OUT", "VDD"),
        _m("M3", "C", "OUT", "VDD"),
        _m("M4", "A", "OUT", "X1"), _m("M5", "B", "X1", "X2"),
        _m("M6", "C", "X2", "GND")],
    "logic_cmos_nor2.xml": _nor2("A", "B", "OUT"),
    # NAND2 → NOT : AND en deux étages chaînés.
    "logic_chaine_and.xml": _nand2("A", "B", "N1") + _inverseur("", "N1", "OUT", i0=5),
    # DAG : deux NOT alimentant un NAND2.
    "logic_dag_2vers1.xml": (_inverseur("", "A", "N1")
                             + _inverseur("", "B", "N2", i0=3)
                             + _nand2("N1", "N2", "OUT", i0=5)),
    # Latch SR : deux NOR2 croisés (rendu de repli figé, spec § 2).
    "logic_latch_sr.xml": (_nor2("S", "NQ", "Q", i0=1, interne="P1")
                           + _nor2("R", "Q", "NQ", i0=5, interne="P2")),
    # Inverseur + R série de grille (satellite dessiné, spec § 2).
    "logic_not_r_grille.xml": [_r("R1", "IN", "A")] + _inverseur("", "A", "OUT"),
    # Suiveur : sources des DEUX transistors sur OUT → aucune porte.
    "logic_suiveur_mos.xml": [_m("M1", "A", "VDD", "OUT"),
                              _m("M2", "A", "GND", "OUT")],
    # Non-dual : pull-down série(A,B), pull-up feuille(A) → aucune porte.
    # (fichier réservé aux tests UNITAIRES, hors globs visuels)
    "logic_non_dual.xml": [_m("M1", "A", "OUT", "VDD"),
                           _m("M2", "A", "OUT", "X"), _m("M3", "B", "X", "GND")],
}


def main():
    for nom, comps in CIRCUITS.items():
        chemin = os.path.join(OUT_DIR, nom)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(generer_xml(comps))
        print(f"{nom}: {len(comps)} composants")


if __name__ == "__main__":
    main()
