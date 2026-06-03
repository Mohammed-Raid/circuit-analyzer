import argparse
import sys
import io
from pathlib import Path
from circuit_analyzer.parser import parse_file
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.reporter import generate

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(
        description='Analyse un circuit et identifie les sous-circuits de base.'
    )
    parser.add_argument('input', help='Fichier netlist (.txt)')
    parser.add_argument('--output', help='Fichier de sortie (défaut: report.txt)', default='report.txt')
    parser.add_argument('--format', choices=['txt'], default='txt', help='Format de sortie')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Erreur : fichier introuvable : {args.input}", file=sys.stderr)
        sys.exit(1)

    components = parse_file(str(input_path))
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
