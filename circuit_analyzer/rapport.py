"""
rapport.py — Génération du rapport texte après analyse.
"""
from collections import Counter


_NIVEAUX = {'high': 'élevée', 'medium': 'moyenne', 'low': 'faible'}
_SEP     = '─' * 64
_SEP_FIN = '=' * 64


def generer_rapport(resultats, fichier: str,
                    total_composants: int, tous_refs: list[str] = None) -> str:
    """
    Génère un rapport texte enrichi à partir des résultats de analyser().

    Arguments :
        resultats        : sortie de detecteur.analyser() (ResultatsAnalyse ou list)
        fichier          : nom du fichier analysé
        total_composants : nombre total de composants dans le circuit
        tous_refs        : liste de toutes les références (pour afficher non-classifiés)
    """
    # Compter par catégorie fonctionnelle
    categories: Counter = Counter()
    for m in resultats:
        cat = m.get('functional_category', 'divers')
        categories[cat] += 1

    lignes = [
        '=== ANALYSE DU CIRCUIT ===',
        f'Fichier           : {fichier}',
        f'Composants totaux : {total_composants}',
        f'Groupes identifiés : {len(resultats)}',
    ]
    if categories:
        lignes.append('Répartition par catégorie :')
        for cat, nb in sorted(categories.items()):
            lignes.append(f'  ├ {cat:<22} : {nb}')
    lignes += ['', _SEP]

    classifies: set = set()
    for i, match in enumerate(resultats, 1):
        ct       = match['circuit_type']
        niveau   = _NIVEAUX.get(match.get('confidence_level', ''), '?')
        conf_pct = int(match.get('confidence', 0) * 100)
        reasons  = match.get('reasons', [])
        warns    = match.get('warnings', [])
        cat      = match.get('functional_category', 'divers')

        lignes.append(f'[{i}] {ct}')
        lignes.append(f'    Confiance    : {niveau} ({conf_pct}%) — {cat}')
        lignes.append(f'    Composants   : {", ".join(match["components"])}')
        lignes.append(f'    Nœuds        : {" → ".join(n for n in match["nodes"] if n)}')
        if reasons:
            lignes.append(f'    Raisons      : {" ; ".join(reasons)}')
        for w in warns:
            lignes.append(f'    ⚠  {w}')
        lignes.append('')
        classifies.update(match['components'])

    lignes.append(_SEP)

    # Composants non classifiés
    if tous_refs:
        non_classifies = [r for r in tous_refs if r not in classifies]
        if non_classifies:
            lignes.append(
                f'\nComposants non classifiés ({len(non_classifies)}) :'
            )
            lignes.append('    ' + ', '.join(non_classifies))

    # Matches supprimés (composants déjà pris)
    supprimes = getattr(resultats, 'supprimes', [])
    if supprimes:
        lignes.append(f'\nMatches supprimés ({len(supprimes)}) — composants déjà utilisés :')
        for s in supprimes:
            ref_conflit = next(
                (c for c in s.get('locked_components', s['components'])
                 if c in classifies), '?'
            )
            lignes.append(
                f'    - {s["circuit_type"]} [{", ".join(s["components"])}]'
                f' — "{ref_conflit}" déjà dans un autre circuit'
            )

    # Avertissement global
    lignes += [
        '',
        _SEP_FIN,
        '  ⚠  Cet outil est une aide à l\'analyse — il ne remplace pas',
        '     une validation par un ingénieur électronique qualifié.',
        _SEP_FIN,
    ]

    return '\n'.join(lignes)


# Alias anglais pour la compatibilité
def generate(results, input_file, total_components, all_refs=None, format='txt'):
    if format == 'txt':
        return generer_rapport(results, input_file, total_components, all_refs)
    raise ValueError(f"Format non supporté : {format}")
