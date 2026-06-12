"""
reduction.py — Réduction des sous-réseaux passifs en dipôles équivalents.

Directive métier (annotation manuscrite en ROUGE du document de référence
« montages Electroniques de base.doc », section 4 — Montage sommateur) :

    « Rf = R1+R2 ou (R1+C)R2. Dans tous les cas, il faut "créer" le dipôle
      "Rf" qui est en réalité peut-être complexe. C'est la raison : il sera
      préférable de chercher à réaliser tous les sous-composants complexes
      entre : le point – et Vs, le point – et Vi, le point + et Vs.
      Idem pour toute la carte. »

Conséquence : avant le pattern matching, on collapse les chaînes SÉRIE et les
bancs PARALLÈLES de composants passifs (R, C, L) en UN dipôle équivalent. Les
détecteurs cherchent un composant unique entre deux nœuds ; sans cette étape, un
montage dont la contre-réaction (ou l'entrée) est un réseau composite — par
exemple deux résistances en série — n'est pas reconnu, car il existe un nœud
intermédiaire entre IN- et OUT.

Garantie de non-régression : un dipôle synthétique n'est créé QUE lorsqu'un vrai
sous-réseau série/parallèle existe. Pour un circuit sans composite, le graphe
réduit est identique à l'original (mêmes refs, types, valeurs).
"""
import networkx as nx

from circuit_analyzer.patterns.base import (
    is_ground_net, is_power_net, is_protective_earth_net,
)

# Seuls les composants passifs « impédants » fusionnent en dipôle équivalent.
# Les diodes (polarisées), fusibles, interrupteurs… ne sont pas des impédances
# et protègent leurs nœuds contre toute fusion.
TYPES_REDUCTIBLES = {'R', 'C', 'L'}


def _est_rail(net) -> bool:
    """Vrai si le net est une masse, une alimentation ou une terre de protection."""
    if not net:
        return False
    return is_ground_net(net) or is_power_net(net) or is_protective_earth_net(net)


def _combiner_type(t1: str, t2: str) -> str:
    """Type de l'équivalent : le type commun, ou 'Z' (impédance composite) si mixte."""
    return t1 if t1 == t2 else 'Z'


def _noeuds_proteges(graphe) -> set:
    """
    Nœuds qu'on ne doit JAMAIS éliminer par réduction série :
      - rails (GND / alim / terre de protection) ;
      - broches d'un composant multi-broches (AOP, transistor, relais…) ;
      - nœuds touchés par une arête non réductible (diode, fusible, SW…).
    """
    proteges = set()
    for n in graphe.nodes():
        if _est_rail(n):
            proteges.add(n)
    for comp in graphe.graph.get('components', {}).values():
        if len(comp.pins) != 2:
            proteges.update(v for v in comp.pins.values() if v)
    for u, v, data in graphe.edges(data=True):
        if data.get('type') not in TYPES_REDUCTIBLES:
            proteges.add(u)
            proteges.add(v)
    return proteges


def _graphe_de_travail(graphe) -> nx.MultiGraph:
    """MultiGraph ne contenant que les arêtes passives réductibles, annotées
    pour la fusion (refs constitutives + expression lisible)."""
    W = nx.MultiGraph()
    for u, v, data in graphe.edges(data=True):
        if data.get('type') in TYPES_REDUCTIBLES:
            ref = data['ref']
            W.add_edge(u, v, type=data['type'], refs=[ref], expr=ref)
    return W


def _pins_actives(graphe) -> set:
    """Nœuds reliés à une broche d'un composant actif (multi-broches : AOP,
    transistor, relais…). Ce sont les ancres de la directive métier."""
    pins = set()
    for comp in graphe.graph.get('components', {}).values():
        if len(comp.pins) != 2:
            pins.update(v for v in comp.pins.values() if v)
    return pins


def _noeuds_ancres(W: nx.MultiGraph, pins_actives: set) -> set:
    """
    Nœuds appartenant à une composante connexe passive qui touche au moins une
    broche active. Seuls ces nœuds sont éligibles à la réduction : un réseau
    passif flottant (snubber R//C, pont diviseur, filtre RC) n'est PAS ancré et
    reste intact pour les détecteurs simples.
    """
    ancres = set()
    for composante in nx.connected_components(W):
        if composante & pins_actives:
            ancres |= composante
    return ancres


def _pass_parallele(W: nx.MultiGraph, ancres: set) -> bool:
    """Fusionne UN banc d'arêtes parallèles (même paire de nœuds). Retourne True
    si une fusion a eu lieu (l'appelant relance jusqu'au point fixe).

    Conditions :
      - le banc doit être ancré à un composant actif (sinon un R//C flottant
        est un amortisseur autonome, pas une contre-réaction) ;
      - aucune extrémité ne doit être un rail (composants de prélèvement)."""
    for u, v in [(a, b) for a, b in W.edges()]:
        if u == v or _est_rail(u) or _est_rail(v):
            continue
        if u not in ancres and v not in ancres:
            continue
        if W.number_of_edges(u, v) > 1:
            paquet = list(W.get_edge_data(u, v).values())
            type_eq = paquet[0]['type']
            refs, exprs = [], []
            for d in paquet:
                type_eq = _combiner_type(type_eq, d['type'])
                refs.extend(d['refs'])
                exprs.append(d['expr'])
            # Retirer toutes les arêtes parallèles puis poser l'équivalent
            for _ in range(len(paquet)):
                W.remove_edge(u, v)
            W.add_edge(u, v, type=type_eq, refs=refs,
                       expr="(" + "//".join(exprs) + ")")
            return True
    return False


def _pass_serie(W: nx.MultiGraph, proteges: set, ancres: set) -> bool:
    """Élimine UN nœud interne de degré 2 en fusionnant ses deux arêtes en série.
    Retourne True si une fusion a eu lieu."""
    for n in list(W.nodes()):
        if n in proteges or n not in ancres:
            continue
        if W.degree(n) != 2:
            continue
        aretes = list(W.edges(n, keys=True, data=True))
        (u1, v1, k1, d1), (u2, v2, k2, d2) = aretes
        a = v1 if u1 == n else u1
        b = v2 if u2 == n else u2
        if a == b:
            # Deux arêtes vers le même voisin = banc parallèle : laisser
            # _pass_parallele s'en charger.
            continue
        if _est_rail(a) or _est_rail(b):
            # N est un point de prélèvement vers un rail (sortie de filtre RC,
            # milieu de pont diviseur, amortisseur…). Le fusionner détruirait
            # la topologie que les détecteurs simples reconnaissent.
            continue
        type_eq = _combiner_type(d1['type'], d2['type'])
        refs = d1['refs'] + d2['refs']
        expr = f"{d1['expr']}+{d2['expr']}"
        W.remove_node(n)  # retire le nœud interne et ses deux arêtes
        W.add_edge(a, b, type=type_eq, refs=refs, expr=expr)
        return True
    return False


def reduire_dipoles(graphe):
    """
    Réduit les sous-réseaux passifs série/parallèle du graphe en dipôles
    équivalents.

    Retourne (graphe_reduit, expansion) :
      - graphe_reduit : copie du graphe où chaque sous-réseau composite est
        remplacé par une arête unique (ref synthétique 'Z#k', type équivalent,
        value = expression lisible « R1+R2 », « (R1//C1) »…) ;
      - expansion : dict {ref_synthetique -> [refs_reelles]} pour ré-expanser
        les composites après détection.

    Les arêtes passives non fusionnées conservent leur ref/type/value d'origine :
    un graphe sans composite donne donc un graphe réduit identique à l'original.
    """
    proteges = _noeuds_proteges(graphe)
    W = _graphe_de_travail(graphe)
    ancres = _noeuds_ancres(W, _pins_actives(graphe))

    while True:
        if _pass_parallele(W, ancres):
            continue
        if _pass_serie(W, proteges, ancres):
            continue
        break

    reduit = graphe.copy()
    for u, v, k, data in list(reduit.edges(keys=True, data=True)):
        if data.get('type') in TYPES_REDUCTIBLES:
            reduit.remove_edge(u, v, k)

    expansion: dict[str, list] = {}
    compteur = 0
    for u, v, data in W.edges(data=True):
        refs = data['refs']
        if len(refs) > 1:
            compteur += 1
            ref_syn = f"Z#{compteur}"
            expansion[ref_syn] = list(refs)
            reduit.add_edge(u, v, ref=ref_syn, type=data['type'], value=data['expr'])
        else:
            reduit.add_edge(u, v, ref=refs[0], type=data['type'], value=data['expr'])

    return reduit, expansion


def expandre_composites(match: dict, expansion: dict) -> dict:
    """
    Remplace, dans match['components'], chaque ref synthétique par ses refs
    réelles (en préservant l'ordre — la contre-réaction reste avant l'entrée).
    Retourne une copie ; ne modifie pas le match d'origine.
    """
    if not expansion:
        return match
    comps = []
    for ref in match['components']:
        comps.extend(expansion.get(ref, [ref]))
    return {**match, 'components': comps}
