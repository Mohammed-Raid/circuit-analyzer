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


def _rendre_fusibles_transparents(graphe) -> nx.MultiGraph:
    """@brief Fusionne les deux nœuds de chaque fusible (≈ fil ~0 Ω) et retire
    l'arête F. Le fusible disparaît du graphe.

    @param graphe Graphe d'origine.
    @return nx.MultiGraph Copie sans fusible, nets fusionnés.
    """
    # Union-Find des nets reliés par un fusible.
    parent: dict = {}

    def trouver(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def unir(a, b):
        ra, rb = trouver(a), trouver(b)
        if ra != rb:
            parent[rb] = ra

    for _u, _v, data in graphe.edges(data=True):
        if data.get('type') == 'F':
            unir(_u, _v)

    if not parent:  # aucun fusible
        return graphe

    g2 = nx.MultiGraph()
    # Recopier les composants en renommant leurs broches.
    comps = {}
    for ref, comp in graphe.graph.get('components', {}).items():
        comps[ref] = comp
    g2.graph['components'] = comps

    for u, v, data in graphe.edges(data=True):
        if data.get('type') == 'F':
            continue  # le fusible disparaît
        g2.add_edge(trouver(u), trouver(v), **data)
    for n in graphe.nodes():
        g2.add_node(trouver(n))
    # Renommer aussi les broches des composants multi-broches (cohérence des nets).
    for comp in comps.values():
        comp.pins = {p: trouver(net) for p, net in comp.pins.items()}
    return g2


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
    # Trier pour traiter en priorité les nœuds qui fusionnent des composants
    # de même type (R+R, C+C…) avant les nœuds hétérogènes (R+C) : cela assure
    # un résultat déterministe et cohérent (ex. R1+R2//C1 et non R2//R1+C1).
    def _priorite_serie(n):
        if n in bornes or W.degree(n) != 2:
            return 1  # sera ignoré de toute façon
        aretes = list(W.edges(n, keys=True, data=True))
        if len(aretes) != 2:
            return 1
        (u1, v1, _k1, d1), (u2, v2, _k2, d2) = aretes
        return 0 if d1['type'] == d2['type'] else 1

    change = False
    for n in sorted(list(W.nodes()), key=_priorite_serie):
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


def _par_operande(expr: str) -> str:
    """@brief Parenthèse une expression série avant de l'insérer dans un parallèle.

    @param expr Expression de composition.
    @return str expr entre parenthèses si elle contient un '+' de haut niveau.
    """
    return f"({expr})" if '+' in expr else expr


def _passe_parallele(W: nx.MultiGraph, bornes: set) -> bool:
    """@brief Fusionne en une passe tous les bancs d'arêtes parallèles.

    (Arêtes multiples entre la même paire de nœuds.)

    @param W Graphe de travail (muté en place).
    @param bornes Inutilisé pour l'instant (le parallèle ne supprime pas de nœud) ;
           présent pour symétrie de signature.
    @return bool True si au moins une fusion a eu lieu.
    """
    paires = set()
    for u, v in W.edges():
        if u != v and W.number_of_edges(u, v) > 1:
            paires.add(frozenset((u, v)))

    for paire in paires:
        u, v = tuple(paire)
        # Trier : composites (contenant '+') en premier ; à égalité, conserver
        # l'ordre d'insertion original (clé entière dans le MultiGraph).
        paquet = sorted(
            W.get_edge_data(u, v).items(),
            key=lambda kd: (0 if '+' in kd[1]['expr'] else 1, kd[0]),
        )
        paquet = [d for _k, d in paquet]
        type_eq = paquet[0]['type']
        refs, exprs = [], []
        for d in paquet:
            type_eq = _combiner_type(type_eq, d['type'])
            refs.extend(d['refs'])
            exprs.append(_par_operande(d['expr']))
        for _ in range(len(paquet)):
            W.remove_edge(u, v)
        W.add_edge(u, v, type=type_eq, refs=refs,
                   expr="(" + "//".join(exprs) + ")", value='')
    return bool(paires)


def reduire(graphe) -> nx.MultiGraph:
    """@brief Réduit les réseaux passifs R/L/C en impédances équivalentes Z.

    @param graphe MultiGraph d'origine (arêtes 2-broches + dict 'components').
    @return nx.MultiGraph Copie réduite : chaque arête passive porte un dict Z
            (ref, type, refs, composition, value). Les arêtes non réductibles et
            le dict 'components' sont conservés tels quels.
    """
    graphe = _rendre_fusibles_transparents(graphe)
    W = _graphe_de_travail(graphe)
    bornes = _bornes(graphe, W)

    while True:
        if _passe_serie(W, bornes):
            continue
        if _passe_parallele(W, bornes):
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
