"""@file gen_demos_transistor.py
@brief (Re)génère les circuits de démo à transistors dans circuits_industriels/
et vérifie que chacun est détecté avec le type attendu.

Fixtures jetables pour tester l'app à la main (détection + dessin riche A).
Lancer : python tools/gen_demos_transistor.py
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
    return Composant(ref=ref, type=typ, pins=pins, value=value)


# (nom_fichier, type_attendu, [composants])
DEMOS = [
    ("tr_bjt_commutation", "Transistor en commutation", [
        C("Q1", "Q", {"B": "NB", "C": "NL", "E": "GND"}),
        C("Rb", "R", {"1": "NIN", "2": "NB"}, "10k"),
        C("L1", "L", {"1": "VCC", "2": "NL"}, "10mH"),
    ]),
    ("tr_emetteur_commun", "Amplificateur émetteur commun", [
        C("Q1", "Q", {"B": "NB", "C": "NCOL", "E": "GND"}),
        C("Rc", "R", {"1": "VCC", "2": "NCOL"}, "1k"),
        C("Rb", "R", {"1": "VCC", "2": "NB"}, "47k"),
    ]),
    ("tr_suiveur_emetteur", "Collecteur commun (suiveur d'émetteur)", [
        C("Q1", "Q", {"B": "NB", "C": "VCC", "E": "NOUT"}),
        C("Re", "R", {"1": "NOUT", "2": "GND"}, "1k"),
        C("Rb", "R", {"1": "VCC", "2": "NB"}, "47k"),
    ]),
    ("tr_etage_push_pull", "Étage push-pull", [
        C("Q1", "Q", {"B": "NIN", "C": "VCC", "E": "NOUT"}),
        C("Q2", "Q", {"B": "NIN", "C": "GND", "E": "NOUT"}),
    ]),
    ("tr_paire_darlington", "Paire Darlington", [
        C("Q1", "Q", {"B": "NB", "C": "VCC", "E": "NE1"}),
        C("Q2", "Q", {"B": "NE1", "C": "VCC", "E": "NOUT"}),
        C("Re", "R", {"1": "NOUT", "2": "GND"}, "1k"),
    ]),
    ("tr_mosfet_commutation", "MOSFET en commutation", [
        C("M1", "M", {"G": "NG", "D": "NL", "S": "GND"}),
        C("Rg", "R", {"1": "NIN", "2": "NG"}, "100"),
        C("L1", "L", {"1": "VCC", "2": "NL"}, "10mH"),
    ]),
    ("tr_commande_relais", "Commande de relais", [
        C("Q1", "Q", {"B": "NB", "C": "NCOIL", "E": "GND"}),
        C("Rb", "R", {"1": "NIN", "2": "NB"}, "10k"),
        C("K1", "K", {"A1": "VCC", "A2": "NCOIL"}),
        C("D1", "D", {"A": "NCOIL", "K": "VCC"}),
    ]),
]


def main():
    ok = True
    for nom, attendu, comps in DEMOS:
        resultats = analyser(construire_graphe(comps))
        types = [r["circuit_type"] for r in resultats]
        trouve = attendu in types
        xml = generer_xml(comps, resultats=resultats)
        chemin = os.path.join(DEST, nom + ".xml")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(xml)
        etat = "OK " if trouve else "!! "
        print(f"{etat}{nom}.xml -> attendu '{attendu}' | detecte {types}")
        ok = ok and trouve
    print("\nTOUT OK" if ok else "\nDES ECARTS DE DETECTION")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
