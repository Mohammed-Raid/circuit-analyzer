"""
rapport.py — Génération du rapport texte après analyse.
"""
from collections import Counter


# NB : sortie limitée aux caractères cp1252 (console Windows) — pas de
# symboles Unicode (fleches, triangles d'avertissement, traits pleins).
_NIVEAUX = {'high': 'élevée', 'medium': 'moyenne', 'low': 'faible'}
_SEP     = '-' * 64
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
    a_verifier: list = []   # satellites « possibles » : (ref, circuit hôte, raison)
    for i, match in enumerate(resultats, 1):
        ct       = match['circuit_type']
        niveau   = _NIVEAUX.get(match.get('confidence_level', ''), '?')
        conf_pct = int(match.get('confidence', 0) * 100)
        reasons  = match.get('reasons', [])
        warns    = match.get('warnings', [])
        cat      = match.get('functional_category', 'divers')
        sats     = match.get('satellites', [])
        surs     = [s for s in sats if s.get('status') == 'sure']
        possibles = [s for s in sats if s.get('status') == 'possible']

        lignes.append(f'[{i}] {ct}')
        lignes.append(f'    Confiance    : {niveau} ({conf_pct}%) — {cat}')
        lignes.append(f'    Composants   : {", ".join(match["components"])}')
        lignes.append(f'    Nœuds        : {" -> ".join(n for n in match["nodes"] if n)}')
        if surs:
            lignes.append('    Satellites sûrs     : ' + ' ; '.join(
                f"{s['ref']} ({s['role']} - {s['reason']})" for s in surs))
        if possibles:
            lignes.append('    Satellites possibles: ' + ' ; '.join(
                f"{s['ref']} ? ({s['reason']})" for s in possibles))
        if reasons:
            lignes.append(f'    Raisons      : {" ; ".join(reasons)}')
        for w in warns:
            lignes.append(f'    ATTENTION : {w}')
        lignes.append('')
        classifies.update(match['components'])
        # Seuls les satellites SÛRS quittent les « non classifiés » ;
        # les possibles vont dans la section « À vérifier ».
        classifies.update(s['ref'] for s in surs)
        a_verifier.extend((s['ref'], ct, s['reason']) for s in possibles)

    lignes.append(_SEP)

    # Composants non classifiés
    refs_a_verifier = {ref for ref, _, _ in a_verifier}
    if tous_refs:
        non_classifies = [r for r in tous_refs
                          if r not in classifies and r not in refs_a_verifier]
        if non_classifies:
            lignes.append(
                f'\nComposants non classifiés ({len(non_classifies)}) :'
            )
            lignes.append('    ' + ', '.join(non_classifies))

    # Satellites possibles — rattachement à confirmer par un ingénieur
    if a_verifier:
        lignes.append(f'\nÀ vérifier (rattachement possible) ({len(a_verifier)}) :')
        for ref, ct_hote, raison in a_verifier:
            lignes.append(f'    - {ref} -> {ct_hote} ({raison})')

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
        '  ATTENTION : Cet outil est une aide à l\'analyse — il ne remplace pas',
        '  une validation par un ingénieur électronique qualifié.',
        _SEP_FIN,
    ]

    return '\n'.join(lignes)


# Alias anglais pour la compatibilité
def generate(results, input_file, total_components, all_refs=None, format='txt'):
    if format == 'txt':
        return generer_rapport(results, input_file, total_components, all_refs)
    raise ValueError(f"Format non supporté : {format}")
