"""@file gen_schemas_impedances_complexes.py
@brief Genere des schemas transistor realistes avec impedances RLC complexes.

Ces fixtures servent a tester la detection d'ilots transistor quand les etages
ne sont plus des cas minimaux : polarisation par pont, degeneration d'emetteur,
decouplages, couplages AC et charges composees.

Lancer : python tools/gen_schemas_impedances_complexes.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.detecteur import analyser
from circuit_analyzer.xml import generer_xml

DEST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "circuits_industriels")


def C(ref, typ, pins, value=""):
    """@brief Raccourci de creation d'un composant."""
    return Composant(ref=ref, type=typ, pins=pins, value=value)


SCHEMAS = [
    (
        "ilot_reel_2ce_bias_rlc",
        {"Amplificateur émetteur commun": 2, "Impédance Z": 5},
        [
            C("Q1", "Q", {"B": "NB1", "C": "NC1", "E": "NE1"}),
            C("Rb1H", "R", {"1": "VCC", "2": "NB1"}, "220k"),
            C("Rb1L", "R", {"1": "NB1", "2": "GND"}, "47k"),
            C("Rc1", "R", {"1": "VCC", "2": "NC1"}, "4.7k"),
            C("Re1", "R", {"1": "NE1", "2": "GND"}, "1k"),
            C("Ce1", "C", {"1": "NE1", "2": "GND"}, "47u"),
            C("C12", "C", {"1": "NC1", "2": "N12"}, "470n"),
            C("R12", "R", {"1": "N12", "2": "NB2"}, "100"),
            C("L12", "L", {"1": "N12", "2": "NB2"}, "2.2u"),
            C("Q2", "Q", {"B": "NB2", "C": "NC2", "E": "NE2"}),
            C("Rb2H", "R", {"1": "VCC", "2": "NB2"}, "150k"),
            C("Rb2L", "R", {"1": "NB2", "2": "GND"}, "33k"),
            C("Rc2", "R", {"1": "VCC", "2": "NC2"}, "2.2k"),
            C("Re2", "R", {"1": "NE2", "2": "GND"}, "680"),
            C("Ce2", "C", {"1": "NE2", "2": "GND"}, "100u"),
            C("Cout", "C", {"1": "NC2", "2": "VOUT"}, "1u"),
            C("Rload", "R", {"1": "VOUT", "2": "GND"}, "10k"),
            C("Cload", "C", {"1": "VOUT", "2": "GND"}, "4.7n"),
        ],
    ),
    (
        "ilot_reel_ce_suiveur_sortie_rlc",
        {"Amplificateur émetteur commun": 1,
         "Collecteur commun": 1,
         "Impédance Z": 5},
        [
            C("Q1", "Q", {"B": "NB1", "C": "NC1", "E": "NE1"}),
            C("Rin", "R", {"1": "VIN", "2": "NIN"}, "1k"),
            C("Cin", "C", {"1": "NIN", "2": "NB1"}, "220n"),
            C("Rb1H", "R", {"1": "VCC", "2": "NB1"}, "180k"),
            C("Rb1L", "R", {"1": "NB1", "2": "GND"}, "39k"),
            C("Rc1", "R", {"1": "VCC", "2": "NC1"}, "3.3k"),
            C("Re1", "R", {"1": "NE1", "2": "GND"}, "820"),
            C("Ce1", "C", {"1": "NE1", "2": "GND"}, "22u"),
            C("C12", "C", {"1": "NC1", "2": "NB2"}, "1u"),
            C("Rbleed", "R", {"1": "NB2", "2": "GND"}, "220k"),
            C("Q2", "Q", {"B": "NB2", "C": "VCC", "E": "NBUF"}),
            C("Re2", "R", {"1": "NBUF", "2": "GND"}, "1.2k"),
            C("Lout", "L", {"1": "NBUF", "2": "VOUT"}, "10u"),
            C("Riso", "R", {"1": "NBUF", "2": "VOUT"}, "10"),
            C("Csnub", "C", {"1": "VOUT", "2": "GND"}, "100n"),
            C("Rload", "R", {"1": "VOUT", "2": "GND"}, "8"),
        ],
    ),
    (
        "ilot_reel_fanout_filtres_rlc",
        {"Amplificateur émetteur commun": 3, "Impédance Z": 3},
        [
            C("Q0", "Q", {"B": "NIN", "C": "NC0", "E": "NE0"}),
            C("Rb0H", "R", {"1": "VCC", "2": "NIN"}, "220k"),
            C("Rb0L", "R", {"1": "NIN", "2": "GND"}, "47k"),
            C("Rc0", "R", {"1": "VCC", "2": "NC0"}, "4.7k"),
            C("Re0", "R", {"1": "NE0", "2": "GND"}, "1k"),
            C("Ce0", "C", {"1": "NE0", "2": "GND"}, "47u"),
            C("Ca", "C", {"1": "NC0", "2": "NA1"}, "330n"),
            C("Ra", "R", {"1": "NA1", "2": "NBA"}, "220"),
            C("La", "L", {"1": "NA1", "2": "NBA"}, "4.7u"),
            C("Q1", "Q", {"B": "NBA", "C": "NCA", "E": "GND"}),
            C("Rba", "R", {"1": "VCC", "2": "NBA"}, "100k"),
            C("Rca", "R", {"1": "VCC", "2": "NCA"}, "2.2k"),
            C("Cb", "C", {"1": "NC0", "2": "NBB"}, "47n"),
            C("Rbshape", "R", {"1": "NC0", "2": "NBB"}, "4.7k"),
            C("Q2", "Q", {"B": "NBB", "C": "NCB", "E": "GND"}),
            C("Rbb", "R", {"1": "VCC", "2": "NBB"}, "100k"),
            C("Rcb", "R", {"1": "VCC", "2": "NCB"}, "3.3k"),
        ],
    ),
    (
        "ilot_reel_darlington_relais_rlc",
        {"Paire Darlington": 1, "Impédance Z": 4},
        [
            C("Q1", "Q", {"B": "NB", "C": "VCC", "E": "NE1"}),
            C("Q2", "Q", {"B": "NE1", "C": "NCOIL", "E": "GND"}),
            C("Rb", "R", {"1": "VIN", "2": "NB"}, "4.7k"),
            C("Rpd", "R", {"1": "NB", "2": "GND"}, "100k"),
            C("Cb", "C", {"1": "NB", "2": "GND"}, "10n"),
            C("Lcoil", "L", {"1": "VCC", "2": "NCOIL"}, "80mH"),
            C("Rcoil", "R", {"1": "VCC", "2": "NCOIL"}, "320"),
            C("Dfly", "D", {"A": "NCOIL", "K": "VCC"}),
            C("Csnub", "C", {"1": "NCOIL", "2": "VCC"}, "47n"),
            C("Rsnub", "R", {"1": "NCOIL", "2": "VCC"}, "100"),
            C("Cdec", "C", {"1": "VCC", "2": "GND"}, "100n"),
            C("Lfeed", "L", {"1": "VIN_SUP", "2": "VCC"}, "2.2u"),
        ],
    ),
    (
        "ilot_reel_ampli_audio_3etages",
        {"Amplificateur émetteur commun": 2,
         "Collecteur commun": 1,
         "Impédance Z": 6},
        [
            C("Q1", "Q", {"B": "NB1", "C": "NC1", "E": "NE1"}),
            C("Cin", "C", {"1": "VIN", "2": "NB1"}, "220n"),
            C("RinLeak", "R", {"1": "NB1", "2": "GND"}, "470k"),
            C("Rb1H", "R", {"1": "VCC", "2": "NB1"}, "220k"),
            C("Rb1L", "R", {"1": "NB1", "2": "GND"}, "47k"),
            C("Rc1", "R", {"1": "VCC", "2": "NC1"}, "6.8k"),
            C("Re1", "R", {"1": "NE1", "2": "GND"}, "1.2k"),
            C("Ce1", "C", {"1": "NE1", "2": "GND"}, "22u"),
            C("C12", "C", {"1": "NC1", "2": "N12"}, "470n"),
            C("R12", "R", {"1": "N12", "2": "NB2"}, "150"),
            C("L12", "L", {"1": "N12", "2": "NB2"}, "1u"),
            C("Q2", "Q", {"B": "NB2", "C": "NC2", "E": "NE2"}),
            C("Rb2H", "R", {"1": "VCC", "2": "NB2"}, "180k"),
            C("Rb2L", "R", {"1": "NB2", "2": "GND"}, "39k"),
            C("Rc2", "R", {"1": "VCC", "2": "NC2"}, "3.3k"),
            C("Re2", "R", {"1": "NE2", "2": "GND"}, "680"),
            C("Ce2", "C", {"1": "NE2", "2": "GND"}, "47u"),
            C("C23", "C", {"1": "NC2", "2": "NB3"}, "1u"),
            C("Rbleed3", "R", {"1": "NB3", "2": "GND"}, "220k"),
            C("Q3", "Q", {"B": "NB3", "C": "VCC", "E": "NOUT"}),
            C("Re3", "R", {"1": "NOUT", "2": "GND"}, "1k"),
            C("Lout", "L", {"1": "NOUT", "2": "VOUT"}, "15u"),
            C("Riso", "R", {"1": "NOUT", "2": "VOUT"}, "4.7"),
            C("Czobel", "C", {"1": "VOUT", "2": "NZ"}, "100n"),
            C("Rzobel", "R", {"1": "NZ", "2": "GND"}, "10"),
            C("Rload", "R", {"1": "VOUT", "2": "GND"}, "32"),
        ],
    ),
]


def _nb_types(resultats, fragment):
    """@brief Compte les matches dont le type contient `fragment`."""
    return sum(fragment in r.get("circuit_type", "") for r in resultats)


def main():
    os.makedirs(DEST, exist_ok=True)
    ok = True
    for nom, attendus, comps in SCHEMAS:
        resultats = analyser(construire_graphe(comps))
        xml = generer_xml(comps, resultats=resultats)
        chemin = os.path.join(DEST, nom + ".xml")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(xml)

        types = [r["circuit_type"] for r in resultats]
        checks = []
        for fragment, minimum in attendus.items():
            n = _nb_types(resultats, fragment)
            checks.append(f"{fragment}: {n}/{minimum}")
            ok = ok and n >= minimum
        etat = "OK " if all(_nb_types(resultats, f) >= n
                            for f, n in attendus.items()) else "!! "
        print(f"{etat}{nom}.xml -> {', '.join(checks)}")
        print("   detecte:", ", ".join(types))
    print("\nTOUT OK" if ok else "\nDES ECARTS DE DETECTION")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
