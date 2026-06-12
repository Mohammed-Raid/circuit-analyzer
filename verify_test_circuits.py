"""
Vérifie que chaque fichier XML généré est correctement reconnu par l'analyseur.
Compare le pattern détecté au pattern attendu (déduit du nom de fichier).

Usage: python verify_test_circuits.py
"""
import os
import sys
import io
sys.path.insert(0, os.path.dirname(__file__))
from circuit_analyzer.xml_parser import parse_xml
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = "circuits_test"

# Fichier → pattern(s) attendu(s) (sous-chaîne suffisante)
EXPECTED = {
    "filtre_rc_passe_bas.xml":           ["Filtre RC passe-bas"],
    "filtre_rc_passe_haut.xml":          ["Filtre RC passe-haut"],
    "condensateur_decouplage.xml":       ["Condensateur de découplage"],
    "pont_diviseur.xml":                 ["Pont diviseur de tension"],
    "absorbeur_rc.xml":                  ["Absorbeur RC"],
    "amplificateur_inverseur.xml":       ["Amplificateur inverseur (AOP)"],
    "amplificateur_non_inverseur.xml":   ["Amplificateur non-inverseur (AOP)"],
    "suiveur_tension.xml":               ["Suiveur de tension (AOP)"],
    "integrateur.xml":                   ["Intégrateur (AOP)"],
    "derivateur.xml":                    ["Dérivateur (AOP)"],
    "comparateur.xml":                   ["Comparateur (AOP)"],
    "bascule_schmitt.xml":               ["Bascule de Schmitt (AOP)"],
    "amplificateur_differentiel.xml":    ["Amplificateur différentiel (AOP)"],
    "amplificateur_sommateur.xml":       ["Amplificateur sommateur (AOP)"],
    "transistor_commutation.xml":        ["Transistor en commutation"],
    "amplificateur_emetteur_commun.xml": ["Amplificateur émetteur commun"],
    "miroir_courant_bjt.xml":            ["Miroir de courant BJT"],
    "mosfet_commutation.xml":            ["MOSFET en commutation"],
    "pont_redresseur_graetz.xml":        ["Pont redresseur (Graetz)"],
    "protection_fusible.xml":            ["Protection par fusible"],
    "circuit_combine.xml":               ["Filtre RC passe-bas", "Condensateur de découplage",
                                          "Amplificateur inverseur (AOP)", "Transistor en commutation",
                                          "Protection par fusible"],
}


def analyze(path):
    comps   = parse_xml(path)
    graph   = build_graph(comps)
    results = match_patterns(graph)
    return comps, results


def main():
    passed = 0
    failed = 0
    for fname, expected in EXPECTED.items():
        path = os.path.join(OUT, fname)
        if not os.path.exists(path):
            print(f"  [MANQUE]  {fname}")
            failed += 1
            continue
        try:
            comps, results = analyze(path)
            detected = [r["circuit_type"] for r in results]
            missing  = [e for e in expected if e not in detected]
            if not missing:
                print(f"  [OK]   {fname:38s} → {', '.join(detected) or '(rien)'}")
                passed += 1
            else:
                print(f"  [FAIL] {fname:38s}")
                print(f"         attendu  : {expected}")
                print(f"         détecté  : {detected}")
                print(f"         manquant : {missing}")
                failed += 1
        except Exception as e:
            print(f"  [ERREUR] {fname}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  {passed} réussis  |  {failed} échoués  sur {len(EXPECTED)} fichiers")


if __name__ == "__main__":
    main()
