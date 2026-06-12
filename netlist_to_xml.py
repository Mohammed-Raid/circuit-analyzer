"""
Convertit des netlists .txt en schémas BoardSCH .xml ouvrables dans le logiciel
de design. Convertit tout le dossier simulations/ (circuits industriels réels) en
un coup, puis vérifie que chaque XML est correctement analysé.

Usage:
    python netlist_to_xml.py                  # convertit tout simulations/
    python netlist_to_xml.py mon_circuit.txt  # convertit un seul fichier
"""
import os
import sys
import io

sys.path.insert(0, os.path.dirname(__file__))
from circuit_analyzer.composant import lire_netlist as parse_file, construire_graphe as build_graph
from circuit_analyzer.xml import generer_xml as components_to_xml, lire_xml as parse_xml
from circuit_analyzer.detecteur import analyser as match_patterns

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = "simulations"
OUT = "circuits_industriels"


def convert(txt_path: str, xml_path: str) -> tuple[int, list[str]]:
    """Read a netlist, write a BoardSCH XML, return (component count, detected patterns)."""
    comps = parse_file(txt_path)
    xml = components_to_xml(comps, results=match_patterns(build_graph(comps)))
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)

    # Verify: re-parse the XML we just wrote and analyze it
    re_comps = parse_xml(xml_path)
    results = match_patterns(build_graph(re_comps))
    patterns = sorted({r["circuit_type"] for r in results})
    return len(re_comps), patterns


def convert_all():
    os.makedirs(OUT, exist_ok=True)
    if not os.path.isdir(SRC):
        print(f"Dossier {SRC}/ introuvable.")
        return

    # Only source netlists, not the result_*.txt report files
    files = sorted(
        f for f in os.listdir(SRC)
        if f.endswith(".txt") and not f.startswith("result_")
    )

    total_ok = 0
    for fname in files:
        txt_path = os.path.join(SRC, fname)
        xml_name = os.path.splitext(fname)[0] + ".xml"
        xml_path = os.path.join(OUT, xml_name)
        try:
            n, patterns = convert(txt_path, xml_path)
            print(f"  [OK]  {xml_name:28s}  {n:3d} composants  →  {len(patterns)} patterns")
            for p in patterns:
                print(f"          · {p}")
            total_ok += 1
        except Exception as e:
            print(f"  [ERREUR]  {fname}: {e}")

    print(f"\n{'='*64}")
    print(f"  {total_ok}/{len(files)} circuits industriels convertis dans {OUT}/")


def convert_one(txt_path: str):
    os.makedirs(OUT, exist_ok=True)
    base = os.path.splitext(os.path.basename(txt_path))[0]
    xml_path = os.path.join(OUT, base + ".xml")
    n, patterns = convert(txt_path, xml_path)
    print(f"  [OK]  {xml_path}  ({n} composants)")
    for p in patterns:
        print(f"          · {p}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        convert_one(sys.argv[1])
    else:
        print("Conversion des circuits industriels en XML...\n")
        convert_all()
