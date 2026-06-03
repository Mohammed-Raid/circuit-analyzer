def generate(results: list[dict], input_file: str, total_components: int,
             all_refs: list[str] = None, format: str = 'txt') -> str:
    if format == 'txt':
        return _format_txt(results, input_file, total_components, all_refs)
    raise ValueError(f"Format non supporté : {format}")


def _format_txt(results, input_file, total_components, all_refs):
    sep = '-' * 60
    lines = [
        '=== ANALYSE DU CIRCUIT ===',
        f'Fichier           : {input_file}',
        f'Composants totaux : {total_components}',
        f'Groupes identifiés : {len(results)}',
        '',
        sep,
    ]

    classified = set()
    for i, match in enumerate(results, 1):
        lines.append(f'[{i}] {match["circuit_type"]}')
        lines.append(f'    Composants : {", ".join(match["components"])}')
        lines.append(f'    Nœuds     : {" → ".join(match["nodes"])}')
        lines.append('')
        classified.update(match['components'])

    lines.append(sep)

    if all_refs:
        unclassified = [r for r in all_refs if r not in classified]
        if unclassified:
            lines.append(f'\nComposants non classifiés ({len(unclassified)}) :')
            lines.append('    ' + ', '.join(unclassified))

    return '\n'.join(lines)
