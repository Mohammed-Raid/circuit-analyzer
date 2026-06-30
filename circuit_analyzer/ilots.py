"""
@file ilots.py
@brief Détection d'îlots fonctionnels (structure en étages du schéma).

Principe : deux composants appartiennent au même îlot s'ils partagent un net
signal (non-rail). GND/VCC/PE connectent électriquement tout le schéma mais ne
portent aucune information fonctionnelle : on les exclut de la connexité, et la
structure en étages émerge naturellement.

Cas particuliers :
  - composants rail-to-rail (découplages) : un îlot par rail d'alimentation ;
  - composants ne touchant que GND/PE : îlot « non identifié ».

Format d'un îlot :
    {'label': 'Îlot 1 - commutation', 'categorie': 'commutation',
     'composants': ['D1', 'K1', 'Q1'],   # triés
     'circuits': [0, 1],                  # indices dans les résultats d'analyse
     'rail': None}                        # ou 'VCC_12V' pour un îlot d'alim
"""
from collections import Counter

from circuit_analyzer.patterns.base import is_power_net
from circuit_analyzer.satellites import _est_rail

# Nets « non connectés » : ne relient électriquement aucun composant. L'export
# XML force les broches d'alim d'AOP à 'NC' ; les compter comme un net signal
# fusionnerait à tort tous ces composants dans un même îlot.
_NETS_NON_CONNECTES = {"NC", "N/C", "NRELIEE", ""}


def _net_signal(net) -> bool:
    """@brief Vrai si le net relie réellement des composants (ni rail, ni non-connecté)."""
    return bool(net) and net.upper() not in _NETS_NON_CONNECTES and not _est_rail(net)


def _est_degenere(comp) -> bool:
    """@brief Vrai si toutes les broches connectées pointent vers un seul net.

    Un tel composant est en court-circuit sur lui-même (ex. R14/C9 câblés GND-GND
    dans la netlist) : aucun courant ne le traverse, il est électriquement inerte.
    On l'exclut des îlots pour ne pas produire de boîte Z absurde.

    @param comp Composant (a un dict .pins).
    @return bool Vrai si dégénéré (≥2 broches connectées, toutes sur le même net).
    """
    connectees = [n for n in comp.pins.values()
                  if n and n.upper() not in _NETS_NON_CONNECTES]
    return len(connectees) >= 2 and len(set(connectees)) == 1


def _find(parent: dict, x: str) -> str:
    """@brief Racine Union-Find avec compression de chemin.

    @param parent Dict parent de l'Union-Find.
    @param x Élément dont on cherche la racine.
    @return str Racine de la classe d'équivalence de x.
    """
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent: dict, a: str, b: str) -> None:
    """@brief Fusionne les classes d'équivalence de a et b.

    @param parent Dict parent de l'Union-Find (muté en place).
    @param a Premier élément.
    @param b Second élément.
    @return None
    """
    ra, rb = _find(parent, a), _find(parent, b)
    if ra != rb:
        parent[rb] = ra


def _categorie_dominante(circuits: list, indices: list) -> str:
    """@brief Catégorie fonctionnelle majoritaire des circuits d'un îlot.

    @param circuits Liste de tous les circuits détectés.
    @param indices Indices (dans circuits) des circuits de l'îlot.
    @return str Catégorie dominante (ou catégories à égalité, jointes par ' + ').
    """
    compteur = Counter(
        circuits[i].get('functional_category', 'divers') for i in indices
    )
    if not compteur:
        return 'non identifié'
    # Les « Impédance Z » sont des briques passives, pas la fonction d'un étage :
    # depuis la refonte Z elles sont nombreuses et noieraient les montages actifs
    # dans le vote. On ne les retient que si l'îlot est purement passif.
    if len(compteur) > 1:
        compteur.pop('impedance', None)
    maxi = max(compteur.values())
    gagnantes = sorted(cat for cat, nb in compteur.items() if nb == maxi)
    return ' + '.join(gagnantes)


def detecter_ilots(graphe, circuits: list) -> list[dict]:
    """
    @brief Découpe le circuit en îlots fonctionnels (connexité hors rails).

    @param graphe Graphe NetworkX construit par construire_graphe().
    @param circuits Liste des matches d'analyser() (peut être vide).
    @return list[dict] Îlots triés par taille décroissante (label, categorie, composants, circuits, rail).
    """
    comps = graphe.graph.get('components', {})
    # Écarter les composants dégénérés (toutes broches sur un même net) : inertes,
    # ils n'appartiennent à aucun étage fonctionnel.
    comps = {ref: c for ref, c in comps.items() if not _est_degenere(c)}
    if not comps:
        return []

    # ── 1. Union-Find sur les refs via les nets signal ────────────────────────
    parent = {ref: ref for ref in comps}
    net_vers_refs: dict = {}
    for ref, comp in comps.items():
        for net in comp.pins.values():
            if _net_signal(net):
                net_vers_refs.setdefault(net, []).append(ref)
    for refs in net_vers_refs.values():
        for autre in refs[1:]:
            _union(parent, refs[0], autre)

    refs_signal = {r for refs in net_vers_refs.values() for r in refs}
    groupes: dict = {}
    for ref in refs_signal:
        groupes.setdefault(_find(parent, ref), []).append(ref)

    # ── 2. Composants rail-only : un groupe par rail d'alimentation ──────────
    par_rail: dict = {}
    sans_rien: list = []
    for ref, comp in comps.items():
        if ref in refs_signal:
            continue
        rails = sorted({n for n in comp.pins.values() if n and is_power_net(n)})
        if rails:
            par_rail.setdefault(rails[0], []).append(ref)
        else:
            sans_rien.append(ref)

    # ── 3. Construire les îlots bruts ─────────────────────────────────────────
    bruts = [{'composants': sorted(refs), 'rail': None}
             for refs in groupes.values()]
    bruts += [{'composants': sorted(refs), 'rail': rail}
              for rail, refs in sorted(par_rail.items())]
    if sans_rien:
        bruts.append({'composants': sorted(sans_rien), 'rail': None,
                      'force_non_identifie': True})

    # ── 4. Rattacher les circuits détectés (par leur premier composant) ──────
    ref_vers_ilot = {}
    for ilot in bruts:
        for ref in ilot['composants']:
            ref_vers_ilot[ref] = id(ilot)
    for ilot in bruts:
        ilot['circuits'] = []
    par_id = {id(i): i for i in bruts}
    for idx, match in enumerate(circuits or []):
        for ref in match.get('components', []):
            ilot_id = ref_vers_ilot.get(ref)
            if ilot_id is not None:
                par_id[ilot_id]['circuits'].append(idx)
                break

    # ── 5. Tri, nommage, numérotation ─────────────────────────────────────────
    bruts.sort(key=lambda i: (-len(i['composants']), i['composants'][0]))
    ilots = []
    for n, ilot in enumerate(bruts, 1):
        if ilot.get('force_non_identifie'):
            categorie = 'non identifié'
        elif ilot['rail']:
            categorie = 'alimentation'
        else:
            categorie = _categorie_dominante(circuits or [], ilot['circuits'])
        if ilot['rail']:
            label = f"Îlot {n} - alimentation {ilot['rail']}"
        else:
            label = f"Îlot {n} - {categorie}"
        ilots.append({
            'label':      label,
            'categorie':  categorie,
            'composants': ilot['composants'],
            'circuits':   ilot['circuits'],
            'rail':       ilot['rail'],
        })
    return ilots
