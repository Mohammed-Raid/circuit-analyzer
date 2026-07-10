# @file gen_reel_corpus.py
# @brief Corpus des composants réels (circuits_industriels/reel_*.xml) —
# relançable, déterministe (même style que gen_logic_corpus.py).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuit_analyzer.composant import Composant
from circuit_analyzer.xml import generer_xml

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "circuits_industriels")


def _r(ref, a, b, val="10k"):
    return Composant(ref=ref, type="R", pins={"1": a, "2": b}, value=val)


def _c(ref, a, b, val="100n"):
    return Composant(ref=ref, type="C", pins={"1": a, "2": b}, value=val)


def _u(ref, val, **pins):
    # pins par numéro de boîtier : _u("U1", "NE555", p1="GND", p2="TRIG_NET"…)
    return Composant(ref=ref, type="U", value=val,
                     pins={k[1:]: v for k, v in pins.items()})


CIRCUITS = {
    # Preuve d'aliasing : broches numérotées 741 -> détecté inverseur AOP.
    "reel_741_inverseur.xml": [
        _u("U1", "LM741", p2="NIN", p3="GND", p6="NOUT", p7="VCC", p4="VEE"),
        _r("R1", "VIN", "NIN"), _r("R2", "NIN", "NOUT", "100k")],
    # RL charge la sortie : sans elle NOUT est un net singleton -> broche 3
    # filtrée, un astable SANS sa sortie en démo (audit A2).
    "reel_555_astable.xml": [
        _u("U1", "NE555", p1="GND", p2="NTRIG", p3="NOUT", p4="VCC",
           p5="NCTRL", p6="NTRIG", p7="NDIS", p8="VCC"),
        _r("RA", "VCC", "NDIS", "4.7k"), _r("RB", "NDIS", "NTRIG", "10k"),
        _c("C1", "NTRIG", "GND", "10u"), _c("C2", "NCTRL", "GND", "10n"),
        _r("RL", "NOUT", "GND", "1k")],
    "reel_7805_alim.xml": [
        _u("U1", "7805", p1="VIN", p2="GND", p3="V5"),
        _c("C1", "VIN", "GND", "330n"), _c("C2", "V5", "GND", "100n")],
    "reel_lm317_variable.xml": [
        _u("U1", "LM317", p1="NADJ", p2="VOUT", p3="VIN"),
        _r("R1", "VOUT", "NADJ", "240"), _r("R2", "NADJ", "GND", "1.2k")],
    "reel_pc817_entree.xml": [
        _u("U1", "PC817", p1="NA", p2="GND", p3="GND", p4="NC1"),
        _r("R1", "VIN", "NA", "1k"), _r("R2", "VCC", "NC1", "10k")],
    # Porte 1 réellement câblée (pull-ups + charge) : des nets singletons
    # seraient filtrés -> boîte vide VCC/GND en démo (audit A2).
    "reel_74hc00_seul.xml": [
        _u("U1", "74HC00", p1="NA1", p2="NB1", p3="NY1", p7="GND",
           p14="VCC"),
        _r("R1", "VCC", "NA1", "10k"), _r("R2", "VCC", "NB1", "10k"),
        _r("R3", "NY1", "GND", "1k")],
    # R4 amène le signal mesuré sur IN1+ : sinon NMES est un singleton ->
    # comparateur affiché SANS son entrée + (audit A2).
    "reel_lm393_seuil.xml": [
        _u("U1", "LM393", p2="NREF", p3="NMES", p1="NOUT", p4="GND",
           p8="VCC"),
        _r("R1", "VCC", "NREF", "10k"), _r("R2", "NREF", "GND", "10k"),
        _r("R3", "VCC", "NOUT", "4.7k"), _r("R4", "VIN", "NMES", "1k")],
    "reel_led_r.xml": [
        Composant(ref="D1", type="D", value="LED rouge",
                  pins={"A": "NLED", "K": "GND"}),
        _r("R1", "VCC", "NLED", "330")],
}


def main():
    for nom, comps in CIRCUITS.items():
        chemin = os.path.join(OUT_DIR, nom)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(generer_xml(comps))
        print("->", chemin)


if __name__ == "__main__":
    main()
