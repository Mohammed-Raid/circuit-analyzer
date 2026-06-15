"""
@file reduction.py
@brief Réduction des sous-réseaux passifs en dipôles équivalents.

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
    """@brief Vrai si le net est une masse, une alimentation ou une terre de protection.

    @param net Nom du net à tester (chaîne, éventuellement vide/None).
    @return bool True si le net est un rail (GND / alimentation / terre de protection).
    """
    if not net:
        return False
    return is_ground_net(net) or is_power_net(net) or is_protective_earth_net(net)


def _combiner_type(t1: str, t2: str) -> str:
    """@brief Type de l'équivalent : le type commun, ou 'Z' (impédance composite) si mixte.

    @param t1 Type du premier composant ('R', 'C' ou 'L').
    @param t2 Type du second composant.
    @return str Le type commun si t1 == t2, sinon 'Z' (impédance composite).

    Limitation connue : un dipôle mixte (ex. R série C, le cas « (R1+C)R2 » du
    document) devient un type 'Z' qu'AUCUN détecteur actuel ne reconnaît
    (l'inverseur attend 'R', l'intégrateur 'C'). C'est volontaire — mieux vaut
    une non-détection qu'un faux positif —, mais cela signifie que la variante
    composite mixte n'est pas (encore) classifiée comme un montage nommé."""
    return t1 if t1 == t2 else 'Z'


def _noeuds_proteges(graphe) -> set:
    """
    @brief Ensemble des nœuds qu'on ne doit JAMAIS éliminer par réduction série.

    Sont protégés :
      - rails (GND / alim / terre de protection) ;
      - broches d'un composant multi-broches (AOP, transistor, relais…) ;
      - nœuds touchés par une arête non réductible (diode, fusible, SW…).

    @param graphe Le MultiGraph NetworkX d'origine (arêtes passives + dict 'components').
    @return set Ensemble des noms de nœuds protégés.
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
    """@brief Construit le MultiGraph de travail des seules arêtes passives réductibles.

    Chaque arête est annotée pour la fusion (refs constitutives + expression lisible).

    @param graphe Le MultiGraph NetworkX d'origine.
    @return nx.MultiGraph Sous-graphe des arêtes R/C/L, annotées (type, refs, expr, value).
    """
    W = nx.MultiGraph()
    for u, v, data in graphe.edges(data=True):
        if data.get('type') in TYPES_REDUCTIBLES:
            ref = data['ref']
            # 'value' est conservée pour les arêtes NON fusionnées (singletons) :
            # le graphe réduit doit rester strictement identique à l'original
            # tant qu'aucune réduction n'a lieu (valeurs comprises).
            W.add_edge(u, v, type=data['type'], refs=[ref], expr=ref,
                       value=data.get('value', ''))
    return W


def _pins_actives(graphe) -> set:
    """@brief Nœuds reliés à une broche d'un composant actif (multi-broches).

    AOP, transistor, relais… Ce sont les ancres de la directive métier.

    @param graphe Le MultiGraph NetworkX d'origine (dict 'components').
    @return set Ensemble des nets connectés à une broche d'un composant non-2-broches.
    """
    pins = set()
    for comp in graphe.graph.get('components', {}).values():
        if len(comp.pins) != 2:
            pins.update(v for v in comp.pins.values() if v)
    return pins


def _noeuds_ancres(W: nx.MultiGraph, pins_actives: set) -> set:
    """
    @brief Nœuds d'une composante connexe passive touchant au moins une broche active.

    Seuls ces nœuds sont éligibles à la réduction : un réseau passif flottant
    (snubber R//C, pont diviseur, filtre RC) n'est PAS ancré et reste intact pour
    les détecteurs simples.

    @param W Graphe de travail des arêtes passives réductibles.
    @param pins_actives Ensemble des nets reliés à un composant actif (cf. _pins_actives).
    @return set Ensemble des nœuds ancrés (éligibles à la réduction).
    """
    ancres = set()
    for composante in nx.connected_components(W):
        if composante & pins_actives:
            ancres |= composante
    return ancres


def _pass_parallele(W: nx.MultiGraph, ancres: set) -> bool:
    """@brief Fusionne en une seule passe tous les bancs d'arêtes parallèles.

    (Arêtes partageant la même paire de nœuds.) Les bancs parallèles sont
    indépendants entre eux (fusionner (u,v) ne touche aucune autre paire de
    nœuds), on peut donc tous les traiter d'un coup — inutile de relancer un
    balayage complet après chaque fusion.

    Conditions :
      - le banc doit être ancré à un composant actif (sinon un R//C flottant
        est un amortisseur autonome, pas une contre-réaction) ;
      - aucune extrémité ne doit être un rail (composants de prélèvement).

    @param W Graphe de travail (modifié en place).
    @param ancres Ensemble des nœuds ancrés à un composant actif.
    @return bool True si au moins une fusion parallèle a eu lieu.
    """
    paires = set()
    for u, v in W.edges():
        if u == v or _est_rail(u) or _est_rail(v):
            continue
        if u not in ancres and v not in ancres:
            continue
        if W.number_of_edges(u, v) > 1:
            paires.add(frozenset((u, v)))

    for paire in paires:
        u, v = tuple(paire)
        paquet = list(W.get_edge_data(u, v).values())
        type_eq = paquet[0]['type']
        refs, exprs = [], []
        for d in paquet:
            type_eq = _combiner_type(type_eq, d['type'])
            refs.extend(d['refs'])
            exprs.append(d['expr'])
        for _ in range(len(paquet)):
            W.remove_edge(u, v)
        W.add_edge(u, v, type=type_eq, refs=refs,
                   expr="(" + "//".join(exprs) + ")")
    return bool(paires)


def _pass_serie(W: nx.MultiGraph, proteges: set, ancres: set) -> bool:
    """@brief Élimine en une passe tous les nœuds internes de degré 2 éligibles.

    Fusionne chaque paire d'arêtes en série en un dipôle équivalent.

    @param W Graphe de travail (modifié en place).
    @param proteges Nœuds à ne jamais éliminer (cf. _noeuds_proteges).
    @param ancres Nœuds ancrés à un composant actif (cf. _noeuds_ancres).
    @return bool True si au moins une fusion série a eu lieu.

    Sûreté de la mutation pendant l'itération : les arêtes de chaque nœud sont
    relues À FRAIS (`W.edges(n)`) au moment où il est traité, jamais mises en
    cache — il n'y a donc aucune donnée périmée. Seul le nœud-centre est retiré
    (jamais ses voisins), et chaque nœud n'apparaît qu'une fois dans le snapshot,
    si bien qu'un nœud retiré n'est jamais revisité. On peut donc fusionner tous
    les nœuds éligibles d'un coup, y compris des branches qui partagent le même
    couple de voisins (hub) — cas « N dipôles composites entre IN- et OUT »."""
    change = False
    for n in list(W.nodes()):
        if n in proteges or n not in ancres:
            continue
        if W.degree(n) != 2:
            continue
        aretes = list(W.edges(n, keys=True, data=True))
        if len(aretes) != 2:  # garde-fou (multi-arête résiduelle)
            continue
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
        change = True
    return change


def reduire_dipoles(graphe):
    """
    @brief Réduit les sous-réseaux passifs série/parallèle du graphe en dipôles équivalents.

    @param graphe Le MultiGraph NetworkX d'origine.
    @return tuple (graphe_reduit, expansion) où :
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
            # Namespace réservé : un ref réel commence toujours par une lettre
            # (cf. lire_netlist), '#' garantit l'absence de collision avec un
            # composant existant lors de la ré-expansion.
            ref_syn = f"Z#{compteur}"
            expansion[ref_syn] = list(refs)
            # Dipôle composite : 'value' = expression lisible (« R1+R2 »,
            # « (R1//C1) »), volontairement non parseable en ohms/farads.
            reduit.add_edge(u, v, ref=ref_syn, type=data['type'], value=data['expr'])
        else:
            # Singleton non fusionné : on restitue ref ET value d'origine →
            # arête strictement identique à celle du graphe de départ.
            reduit.add_edge(u, v, ref=refs[0], type=data['type'],
                            value=data.get('value', ''))

    return reduit, expansion


def expandre_composites(match: dict, expansion: dict) -> dict:
    """
    @brief Ré-expanse les refs synthétiques d'un match vers leurs composants réels.

    Remplace, dans match['components'], chaque ref synthétique par ses refs
    réelles (en préservant l'ordre — la contre-réaction reste avant l'entrée).

    @param match Dict du circuit détecté (clé 'components' = liste de refs).
    @param expansion Dict {ref_synthetique -> [refs_reelles]} produit par reduire_dipoles.
    @return dict Copie du match aux refs réelles ; le match d'origine n'est pas modifié.
    """
    if not expansion:
        return match
    comps = []
    for ref in match['components']:
        comps.extend(expansion.get(ref, [ref]))
    return {**match, 'components': comps}
