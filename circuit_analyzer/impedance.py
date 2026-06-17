"""
@file impedance.py
@brief Réduction des réseaux passifs R/L/C en impédances équivalentes Z.

Pipeline « Z d'abord » : on simplifie les chaînes SÉRIE en un bloc, puis ce qui
est en PARALLÈLE avec ces blocs, itéré jusqu'à point fixe. Le résultat est une
impédance Z — un dipôle qui est aussi un sous-circuit consommé par les grands
montages (inverseur, intégrateur…). But premier : qu'aucun composant passif ne
reste « non classifié » — tout R/L/C devient au minimum une Z singleton.
"""
import networkx as nx

from circuit_analyzer.patterns.base import (
    is_ground_net, is_power_net, is_protective_earth_net,
)

# Seuls ces types fusionnent en impédance.
TYPES_REDUCTIBLES = {'R', 'C', 'L'}


def _combiner_type(t1: str, t2: str) -> str:
    """@brief Type équivalent : le type commun, ou 'Z' (mixte) sinon.

    @param t1 Type du premier composant ('R', 'C', 'L' ou 'Z').
    @param t2 Type du second.
    @return str Type commun si t1 == t2, sinon 'Z'.
    """
    return t1 if t1 == t2 else 'Z'


def _est_rail(net) -> bool:
    """@brief Vrai si le net est masse, alimentation ou terre de protection.

    @param net Nom du net (peut être vide/None).
    @return bool True si rail.
    """
    if not net:
        return False
    return is_ground_net(net) or is_power_net(net) or is_protective_earth_net(net)


def _graphe_de_travail(graphe) -> nx.MultiGraph:
    """@brief Sous-graphe des seules arêtes passives réductibles (R/L/C), annotées.

    @param graphe Graphe d'origine.
    @return nx.MultiGraph Arêtes R/L/C avec (type, refs, expr, value).
    """
    W = nx.MultiGraph()
    for u, v, data in graphe.edges(data=True):
        if data.get('type') in TYPES_REDUCTIBLES:
            ref = data['ref']
            W.add_edge(u, v, type=data['type'], refs=[ref], expr=ref,
                       value=data.get('value', ''))
    return W


def _bornes(graphe, W) -> set:
    """@brief Nœuds jamais éliminés : rails, broches actives, jonctions
    touchées par une arête non réductible.

    Les feuilles (degré 1 dans W) ne peuvent de toute façon pas être éliminées
    par la passe série (qui exige un degré 2), inutile de les lister ici.

    @param graphe Graphe d'origine.
    @param W Graphe de travail des arêtes passives.
    @return set Ensemble des nœuds-bornes.
    """
    bornes = set()
    for n in graphe.nodes():
        if _est_rail(n):
            bornes.add(n)
    for comp in graphe.graph.get('components', {}).values():
        if len(comp.pins) != 2:
            bornes.update(v for v in comp.pins.values() if v)
    for u, v, data in graphe.edges(data=True):
        if data.get('type') not in TYPES_REDUCTIBLES:
            bornes.add(u)
            bornes.add(v)
    return bornes


def _passe_serie(W: nx.MultiGraph, bornes: set) -> bool:
    """@brief Élimine en une passe les nœuds internes de degré 2 non-bornes.

    Chaque tel nœud fusionne ses deux arêtes en un dipôle série a+b.

    @param W Graphe de travail (muté en place).
    @param bornes Nœuds à ne jamais éliminer.
    @return bool True si au moins une fusion a eu lieu.
    """
    change = False
    for n in list(W.nodes()):
        if n in bornes or W.degree(n) != 2:
            continue
        aretes = list(W.edges(n, keys=True, data=True))
        if len(aretes) != 2:  # garde-fou (multi-arête résiduelle = parallèle)
            continue
        (u1, v1, _k1, d1), (u2, v2, _k2, d2) = aretes
        a = v1 if u1 == n else u1
        b = v2 if u2 == n else u2
        if a == b:
            continue  # banc parallèle : laisser la passe parallèle agir
        type_eq = _combiner_type(d1['type'], d2['type'])
        refs = d1['refs'] + d2['refs']
        expr = f"{d1['expr']}+{d2['expr']}"
        W.remove_node(n)
        W.add_edge(a, b, type=type_eq, refs=refs, expr=expr, value='')
        change = True
    return change


def reduire(graphe) -> nx.MultiGraph:
    """@brief Réduit les réseaux passifs R/L/C en impédances équivalentes Z.

    @param graphe MultiGraph d'origine (arêtes 2-broches + dict 'components').
    @return nx.MultiGraph Copie réduite : chaque arête passive porte un dict Z
            (ref, type, refs, composition, value). Les arêtes non réductibles et
            le dict 'components' sont conservés tels quels.
    """
    W = _graphe_de_travail(graphe)
    bornes = _bornes(graphe, W)

    while True:
        if _passe_serie(W, bornes):
            continue
        break

    # Reconstruire le graphe réduit : on retire les arêtes passives d'origine et
    # on réémet celles de W (réduites ou non).
    reduit = graphe.copy()
    for u, v, k, data in list(reduit.edges(keys=True, data=True)):
        if data.get('type') in TYPES_REDUCTIBLES:
            reduit.remove_edge(u, v, k)

    compteur = 0
    for u, v, data in W.edges(data=True):
        refs = data['refs']
        if len(refs) > 1:
            compteur += 1
            reduit.add_edge(u, v, ref=f"Z{compteur}", type=data['type'],
                            refs=list(refs), composition=data['expr'],
                            value=data['expr'])
        else:
            reduit.add_edge(u, v, ref=refs[0], type=data['type'],
                            refs=list(refs), composition=refs[0],
                            value=data.get('value', ''))

    # Élaguer les nœuds devenus isolés par la réduction (ex. le milieu d'une
    # chaîne série) — sauf s'ils sont une broche d'un composant actif.
    actifs = set()
    for comp in reduit.graph.get('components', {}).values():
        if len(comp.pins) != 2:
            actifs.update(n for n in comp.pins.values() if n)
    for n in list(reduit.nodes()):
        if reduit.degree(n) == 0 and n not in actifs:
            reduit.remove_node(n)

    return reduit
