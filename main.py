import argparse
import sys
import io
from pathlib import Path
from circuit_analyzer.composant import lire_netlist as parse_file, construire_graphe as build_graph
from circuit_analyzer.xml import lire_xml as parse_xml
from circuit_analyzer.detecteur import analyser as match_patterns
from circuit_analyzer.rapport import generate

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(
        description='Analyse un circuit et identifie les sous-circuits de base.'
    )
    parser.add_argument('input', help='Fichier netlist (.txt) ou schéma BoardSCH (.xml)')
    parser.add_argument('--output', help='Fichier de sortie (défaut: report.txt)', default='report.txt')
    parser.add_argument('--format', choices=['txt'], default='txt', help='Format de sortie')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Erreur : fichier introuvable : {args.input}", file=sys.stderr)
        sys.exit(1)

    try:
        if input_path.suffix.lower() == '.xml':
            components = parse_xml(str(input_path))
        else:
            components = parse_file(str(input_path))
    except ValueError as e:
        print(f"Erreur netlist : {e}", file=sys.stderr)
        sys.exit(1)
    all_refs = [c.ref for c in components]
    graph = build_graph(components)
    results = match_patterns(graph)
    report = generate(results, args.input, len(components), all_refs=all_refs, format=args.format)

    output_path = Path(args.output)
    output_path.write_text(report, encoding='utf-8')

    print(report)
    print(f'\nRapport sauvegardé dans : {output_path}')


if __name__ == '__main__':
    main()
