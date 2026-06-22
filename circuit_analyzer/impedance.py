"""
@file impedance.py
@brief Réduction des réseaux passifs R/L/C en impédances équivalentes Z.

Pipeline « Z d'abord » : on simplifie les chaînes SÉRIE en un bloc, puis ce qui
est en PARALLÈLE avec ces blocs, itéré jusqu'à point fixe. Le résultat est une
impédance Z — un dipôle qui est aussi un sous-circuit consommé par les grands
montages (inverseur, intégrateur…). But premier : qu'aucun composant passif ne
reste « non classifié » — tout R/L/C devient au minimum une Z singleton.
"""
import ast
import copy
import math
import re

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

    transparents: list = []   # refs des fusibles effacés (pour le rapport)
    for _u, _v, data in graphe.edges(data=True):
        if data.get('type') == 'F':
            unir(_u, _v)
            transparents.append(data.get('ref'))

    if not parent:  # aucun fusible
        return graphe

    g2 = nx.MultiGraph()
    # Recopier les composants en renommant leurs broches. On COPIE chaque
    # Composant : ils sont partagés par référence avec l'appelant, et réécrire
    # comp.pins ci-dessous corromprait les composants d'origine.
    comps = {ref: copy.copy(comp)
             for ref, comp in graphe.graph.get('components', {}).items()}
    g2.graph['components'] = comps
    # Refs des fusibles effacés : remontées au rapport pour qu'ils ne soient pas
    # comptés comme « non classifiés » (le fusible est neutralisé, pas perdu).
    g2.graph['fusibles_transparents'] = [r for r in transparents if r]

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


def _bornes(graphe) -> set:
    """@brief Nœuds jamais éliminés : rails, broches actives, jonctions
    touchées par une arête non réductible.

    Les feuilles (degré 1 dans W) ne peuvent de toute façon pas être éliminées
    par la passe série (qui exige un degré 2), inutile de les lister ici.

    @param graphe Graphe d'origine.
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
        # L'ordre de composition d'une chaîne de 3+ éléments suit l'ordre
        # d'insertion des arêtes (limitation cosmétique connue, sans impact
        # électrique : a+b == b+a).
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


def _trouver_triangle(W: nx.MultiGraph):
    """@brief Cherche un triangle (3 nœuds reliés deux à deux par une arête simple).

    @return tuple|None (p, q, r) ou None s'il n'y en a aucun.
    """
    for p in W.nodes():
        nbrs = [q for q in W.neighbors(p) if q != p and W.number_of_edges(p, q) == 1]
        for i, q in enumerate(nbrs):
            for r in nbrs[i + 1:]:
                if W.number_of_edges(q, r) == 1:
                    return (p, q, r)
    return None


def _passe_delta_y(W: nx.MultiGraph, bornes: set) -> bool:
    """@brief Transforme UN triangle (Δ) en étoile (Y), symboliquement.

    Casse les ponts que série/parallèle ne peuvent réduire. Pour un triangle de
    sommets p,q,r d'impédances Z_pq, Z_qr, Z_rp, l'étoile vers un nœud central N a
    pour bras (somme S = Z_pq+Z_qr+Z_rp) : Z_p = Z_pq·Z_rp/S, etc. (produit des
    deux arêtes touchant le sommet / S).

    @param W Graphe de travail (muté en place).
    @param bornes Inutilisé (un triangle a toujours un sommet non-borne ici).
    @return bool True si une transformation a eu lieu.
    """
    tri = _trouver_triangle(W)
    if tri is None:
        return False
    p, q, r = tri
    d_pq = next(iter(W.get_edge_data(p, q).values()))
    d_qr = next(iter(W.get_edge_data(q, r).values()))
    d_rp = next(iter(W.get_edge_data(r, p).values()))
    e_pq, e_qr, e_rp = d_pq['expr'], d_qr['expr'], d_rp['expr']
    somme = f"({e_pq})+({e_qr})+({e_rp})"

    def _bras(e1, e2):  # produit des deux arêtes touchant le sommet, sur la somme
        return f"({e1})*({e2})/({somme})"

    n = W.graph.get('_yc', 0)
    W.graph['_yc'] = n + 1
    centre = f"_Y{n}"
    W.remove_edge(p, q)
    W.remove_edge(q, r)
    W.remove_edge(r, p)
    # sommet p touche pq+rp ; q touche pq+qr ; r touche qr+rp
    W.add_edge(p, centre, type='Z', refs=d_pq['refs'] + d_rp['refs'],
               expr=_bras(e_pq, e_rp), value='')
    W.add_edge(q, centre, type='Z', refs=d_pq['refs'] + d_qr['refs'],
               expr=_bras(e_pq, e_qr), value='')
    W.add_edge(r, centre, type='Z', refs=d_qr['refs'] + d_rp['refs'],
               expr=_bras(e_qr, e_rp), value='')
    return True


def formater_expr(expr: str) -> str:
    """@brief Version lisible d'une expression de composition (affichage seulement).

    Retire les parenthèses superflues autour d'un terme simple (« (R1) » → « R1 »)
    et utilise « · » pour le produit. Ne change pas le sens, seulement la lisibilité.

    @param expr Expression interne (ex. « (R1)*(R2)/((R1)+(R2)+(R5)) »).
    @return str Expression lisible (ex. « R1·R2/(R1+R2+R5) »).
    """
    if not expr:
        return expr
    prev = None
    out = expr
    while out != prev:                       # « (X) » → « X » tant qu'il en reste
        prev = out
        out = re.sub(r'\(([A-Za-z]\w*)\)', r'\1', out)
    return out.replace('*', '·')


# Préfixes SI usuels en électronique. 'm' = milli, 'M' = méga (casse stricte) ;
# 'k'/'K' tolérés pour kilo, 'µ'/'u' pour micro.
_PREFIXES = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'µ': 1e-6, 'm': 1e-3,
             'k': 1e3, 'K': 1e3, 'M': 1e6, 'G': 1e9}


def _parse_valeur(s: str) -> float:
    """@brief Convertit une valeur ingénieur (« 10k », « 100n », « 470 ») en float SI.

    Une éventuelle unité finale (« 100nF », « 1mH ») est ignorée : seuls le nombre
    et l'éventuel préfixe sont lus.

    @param s Chaîne valeur.
    @return float Valeur en unité SI de base (Ω, F ou H).
    @raises ValueError si s est vide ou non interprétable.
    """
    m = re.match(r'\s*([0-9]*\.?[0-9]+)\s*([pnuµmkKMG])?', s or '')
    if not m:
        raise ValueError(f"valeur non interprétable : {s!r}")
    return float(m.group(1)) * _PREFIXES.get(m.group(2), 1.0)


_UNITES = {"R": "Ω", "L": "H", "C": "F"}


def formater_valeur(value: str, typ: str) -> str:
    """@brief Valeur ingénieur + unité pour étiquette (« 10k »,R → « 10 kΩ »).

    @param value Chaîne valeur ; vide → "".
    @param typ Type composant (R→Ω, L→H, C→F ; autre → sans unité).
    @return str Étiquette formatée, ou la valeur brute si non interprétable.
    """
    if not value:
        return ""
    m = re.match(r'\s*([0-9]*\.?[0-9]+)\s*([pnuµmkKMG]?)', value)
    if not m:
        return value
    return f"{m.group(1)} {m.group(2)}{_UNITES.get(typ, '')}".strip()


def _impedance_complexe(typ: str, valeur: float, omega: float) -> complex:
    """@brief Impédance complexe d'un composant à la pulsation ω.

    R → R ; L → jωL ; C → 1/(jωC) = -j/(ωC).

    @param typ Type ('R', 'L' ou 'C').
    @param valeur Valeur SI (Ω, H ou F).
    @param omega Pulsation 2πf (rad/s).
    @return complex Impédance (Ω).
    @raises ValueError pour un type non évaluable.
    """
    if typ == 'R':
        return complex(valeur, 0.0)
    if typ == 'L':
        return complex(0.0, omega * valeur)
    if typ == 'C':
        if omega == 0 or valeur == 0:
            return complex(math.inf, 0.0)  # condensateur en continu = circuit ouvert
        return complex(0.0, -1.0 / (omega * valeur))
    raise ValueError(f"type non évaluable : {typ}")


def evaluer_impedance(graphe, expr: str, f: float) -> complex:
    """@brief Évalue numériquement une expression d'impédance à la fréquence f.

    L'expression (produite par `impedance_equivalente`) est interprétée via l'AST :
    « + » = série, « // » = parallèle (a·b/(a+b)), « * » et « / » = produit/quotient
    (bras de transformation Y-Δ). Chaque symbole (R1, L1, C1…) est remplacé par son
    impédance complexe à la pulsation 2πf.

    @param graphe Graphe d'origine (dict 'components' : ref → Composant).
    @param expr Expression de composition (ex. « (R1+R2)//C1 »).
    @param f Fréquence en Hz.
    @return complex Impédance équivalente Z (Ω).
    @raises ValueError si une valeur est manquante/illisible ou l'expression invalide.
    """
    omega = 2 * math.pi * f
    imp = {
        ref: _impedance_complexe(c.type, _parse_valeur(c.value), omega)
        for ref, c in graphe.graph.get('components', {}).items()
        if c.type in TYPES_REDUCTIBLES
    }

    def _ev(node):
        if isinstance(node, ast.Expression):
            return _ev(node.body)
        if isinstance(node, ast.BinOp):
            a, b = _ev(node.left), _ev(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                return a / b
            if isinstance(node.op, ast.FloorDiv):  # // = parallèle
                return a * b / (a + b)
            raise ValueError("opérateur non supporté dans l'expression")
        if isinstance(node, ast.Name):
            if node.id not in imp:
                raise ValueError(f"valeur manquante pour {node.id}")
            return imp[node.id]
        raise ValueError("expression d'impédance non évaluable")

    return _ev(ast.parse(expr, mode='eval'))


def _convertir_noeud(node):
    """@brief Convertit un nœud AST en arbre série/parallèle, ou None si * / /."""
    if isinstance(node, ast.Name):
        return ("feuille", node.id)
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            kind = "serie"
        elif isinstance(node.op, ast.FloorDiv):  # // = parallèle
            kind = "parallele"
        else:
            return None  # * ou / => pont (Y-Δ), pas de forme série/parallèle
        gauche = _convertir_noeud(node.left)
        droite = _convertir_noeud(node.right)
        if gauche is None or droite is None:
            return None
        enfants = []
        for sous in (gauche, droite):
            if sous[0] == kind:          # aplatissement associatif (a+b+c)
                enfants.extend(sous[1])
            else:
                enfants.append(sous)
        return (kind, enfants)
    return None


def arbre_expr(expr: str):
    """@brief Parse une expression de composition en arbre série/parallèle.

    @param expr Expression (ex. « (R1+R2)//R3 »).
    @return tuple|None Arbre (« serie »/« parallele »/« feuille »), ou None si
            l'expression n'est pas purement série/parallèle (pont Y-Δ : * ou /)
            ou est invalide.
    """
    try:
        return _convertir_noeud(ast.parse(expr, mode='eval').body)
    except (SyntaxError, ValueError):
        return None


def detecter_pont(graphe, a, b):
    """@brief Reconnaît un motif pont (type Wheatstone) entre les bornes a et b.

    Les bras sont d'abord réduits (série/parallèle) : un bras composite (plusieurs
    R/L/C) devient une seule arête Z. Le motif retenu : 4 nœuds et 5 arêtes ; a et b
    de degré 2, non adjacents ; n1, n2 de degré 3, adjacents.

    @param graphe Graphe d'origine (arêtes R/L/C).
    @param a, b Les deux bornes (sommet haut / bas du losange).
    @return dict|None Structure du pont ; bras[role] = {"refs": [...], "composition": str}.
    """
    W = _graphe_de_travail(graphe)
    if a not in W or b not in W:
        return None
    bornes = {a, b}
    while True:
        if _passe_serie(W, bornes):
            continue
        if _passe_parallele(W, bornes):
            continue
        break
    if W.number_of_nodes() != 4 or W.number_of_edges() != 5:
        return None
    if any(W.number_of_edges(u, v) != 1 for u, v in set(W.edges())):
        return None
    if W.degree(a) != 2 or W.degree(b) != 2 or W.has_edge(a, b):
        return None
    internes = [n for n in W.nodes() if n not in (a, b)]
    if len(internes) != 2:
        return None
    n1, n2 = sorted(internes, key=str)
    if W.degree(n1) != 3 or W.degree(n2) != 3 or not W.has_edge(n1, n2):
        return None
    attendues = [(a, n1), (a, n2), (n1, b), (n2, b), (n1, n2)]
    if not all(W.has_edge(u, v) for u, v in attendues):
        return None

    def _bras(u, v):
        d = next(iter(W.get_edge_data(u, v).values()))
        return {"refs": list(d["refs"]), "composition": d["expr"]}

    return {
        "haut": a, "bas": b, "gauche": n1, "droite": n2,
        "bras": {
            "haut_gauche": _bras(a, n1),
            "haut_droite": _bras(a, n2),
            "bas_gauche": _bras(n1, b),
            "bas_droite": _bras(n2, b),
            "pont": _bras(n1, n2),
        },
    }


def bornes_possibles(graphe) -> list:
    """@brief Nets touchés par au moins une impédance (R/L/C) — bornes candidates.

    @param graphe Graphe d'origine.
    @return list[str] Nets triés, sur lesquels on peut calculer un équivalent.
    """
    nets = set()
    for u, v, data in graphe.edges(data=True):
        if data.get('type') in TYPES_REDUCTIBLES:
            nets.add(u)
            nets.add(v)
    return sorted(nets, key=str)


def impedance_equivalente(graphe, a, b):
    """@brief Impédance équivalente symbolique d'un réseau passif entre deux bornes.

    Réduit le réseau R/L/C par série, parallèle puis étoile↔triangle (Y-Δ) jusqu'à
    une seule arête a-b. Symbolique : pas de valeurs numériques ni de fréquence.

    @param graphe Graphe d'origine (arêtes R/L/C ; les autres sont ignorées).
    @param a, b Les deux bornes entre lesquelles calculer l'équivalent.
    @return str|None L'expression de composition (ex. "(R1+R2)//C1"), ou None si le
            réseau n'est pas entièrement réductible par ces trois transformations.
    """
    W = _graphe_de_travail(graphe)
    bornes = {a, b}
    # ponytail: serie/parallele/Y-D suffisent pour tout reseau planaire 2-bornes ;
    # un reseau non planaire (rare) ressort None. Garde-fou d'iterations par securite.
    for _ in range(10 * (W.number_of_edges() + 1)):
        if _passe_serie(W, bornes) or _passe_parallele(W, bornes) or _passe_delta_y(W, bornes):
            continue
        break
    aretes = list(W.edges(data=True))
    if len(aretes) == 1 and {aretes[0][0], aretes[0][1]} == {a, b}:
        return aretes[0][2]['expr']
    return None


def _replier_blocs_irreductibles(W: nx.MultiGraph, bornes: set) -> None:
    """@brief Replie chaque composante passive non réductible (pont) en une seule
    arête Z entre ses deux bornes de contact.

    Seuls les vrais blocs irréductibles (pas de feuilles internes pendantes) sont
    repliés. Les nœuds internes de degré 1 (branches pendantes) sont d'abord
    détachés itérativement : leurs arêtes restent dans W comme singletons, et
    seul le noyau résiduel — s'il persiste — est replié en Z.

    @param W Graphe de travail (muté en place).
    @param bornes Nœuds-bornes.
    @return None
    """
    for composante in list(nx.connected_components(W)):
        internes = [n for n in composante if n not in bornes]
        if not internes:
            continue  # déjà réduit (au plus des arêtes borne-à-borne)
        contacts = sorted(n for n in composante if n in bornes)
        if len(contacts) != 2:
            # 0 ou 1 borne : pas assez pour replier. Plus de 2 bornes (étoile /
            # multi-port) : on ne replie PAS, sinon on ne garderait que 2 des
            # bornes et on perdrait silencieusement la connectivité vers les
            # autres. On laisse les arêtes du bloc intactes dans W : elles seront
            # réémises en singletons, préservant toute la connectivité. Une vraie
            # réduction multi-port est hors périmètre ici.
            continue
        a, b = contacts[0], contacts[1]
        # Construire le sous-graphe de la composante pour tester l'irréductibilité
        # sans muter W pendant l'analyse.
        sous = W.subgraph(composante).copy()
        # Peler itérativement les feuilles internes (degré 1 dans le sous-graphe,
        # mais ce ne sont pas des bornes). Ces branches pendantes sont des dipôles
        # isolés (ex. Re vers un nœud feuille) : ils restent dans W comme
        # singletons et ne font PAS partie du bloc à replier.
        changed = True
        while changed:
            changed = False
            for n in list(sous.nodes()):
                if n in bornes:
                    continue
                if sous.degree(n) == 1:
                    sous.remove_node(n)
                    changed = True
        # Vérifier s'il reste des nœuds internes dans le noyau après le pelage.
        noyau_internes = [n for n in sous.nodes() if n not in bornes]
        if not noyau_internes:
            # Aucun nœud interne résiduel : le bloc n'est pas irréductible.
            # Les arêtes restent dans W telles quelles (singletons ou composites
            # déjà réduits).
            continue
        # Le noyau est vraiment irréductible (ex. pont de Wheatstone).
        # Ne replier QUE les arêtes du noyau, pas les branches pendantes.
        refs = []
        for u, v, d in list(sous.edges(data=True)):
            refs.extend(d['refs'])
        noyau_noeuds = set(sous.nodes())
        # Identifier et sauvegarder les arêtes pendantes : leur AUTRE extrémité
        # est hors du noyau, mais elles sont incidentes à un nœud interne du
        # noyau. Ces arêtes doivent survivre à la suppression du noyau.
        aretes_pendantes = []
        for n in noyau_internes:
            if n not in W:
                continue
            for u2, v2, k2, d2 in list(W.edges(n, keys=True, data=True)):
                autre = v2 if u2 == n else u2
                if autre not in noyau_noeuds:
                    # Branche pendante : hors noyau, mais accrochée à un interne.
                    aretes_pendantes.append((u2, v2, dict(d2)))
        # Retirer les arêtes internes au noyau (SANS toucher les branches).
        for u, v, k in list(W.edges(noyau_noeuds, keys=True)):
            if u in noyau_noeuds and v in noyau_noeuds:
                W.remove_edge(u, v, k)
        for n in noyau_internes:
            if n in W:
                W.remove_node(n)
        # Un bloc irréductible est toujours de type 'Z' : il ne peut pas être
        # simplifié en un dipôle pur, même s'il est homogène (ex. pont tout-R).
        W.add_edge(a, b, type='Z',
                   refs=refs, expr="pont{" + ",".join(sorted(refs)) + "}",
                   value='')
        # Réinsérer les branches pendantes : elles sont maintenant des singletons
        # connectés à leur extrémité extérieure et… nulle part (le nœud interne
        # a disparu). Pour les émettre en résultats, on les raccroche à la borne
        # la plus proche du noyau (a ou b) — leur topologie importe peu car elles
        # seront de toute façon émises comme singletons par reduire().
        for u2, v2, d2 in aretes_pendantes:
            # Choisir la borne du noyau (a ou b) comme nouvel ancrage interne
            autre = v2 if u2 in noyau_noeuds else u2
            W.add_edge(a, autre, **d2)


def reduire(graphe) -> nx.MultiGraph:
    """@brief Réduit les réseaux passifs R/L/C en impédances équivalentes Z.

    @param graphe MultiGraph d'origine (arêtes 2-broches + dict 'components').
    @return nx.MultiGraph Copie réduite : chaque arête passive porte un dict Z
            (ref, type, refs, composition, value). Les arêtes non réductibles et
            le dict 'components' sont conservés tels quels.
    """
    graphe = _rendre_fusibles_transparents(graphe)
    W = _graphe_de_travail(graphe)
    bornes = _bornes(graphe)

    while True:
        if _passe_serie(W, bornes):
            continue
        if _passe_parallele(W, bornes):
            continue
        break

    _replier_blocs_irreductibles(W, bornes)

    # Reconstruire le graphe réduit : on retire les arêtes passives d'origine et
    # on réémet celles de W (réduites ou non).
    reduit = graphe.copy()
    reduit.graph.setdefault('fusibles_transparents', [])
    for u, v, k, data in list(reduit.edges(keys=True, data=True)):
        if data.get('type') in TYPES_REDUCTIBLES:
            reduit.remove_edge(u, v, k)

    compteur = 0
    for u, v, data in W.edges(data=True):
        refs = data['refs']
        if len(refs) > 1:
            compteur += 1
            # Le numéro Zn est un label interne, NON garanti stable d'un run à
            # l'autre (il dépend de l'ordre d'itération) : les consommateurs ne
            # doivent pas dépendre d'un numéro Z précis.
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


def expansion_depuis_graphe(reduit) -> dict:
    """@brief Table {ref_synthetique -> [refs_reelles]} des arêtes composites du graphe réduit.

    @param reduit Graphe réduit produit par reduire().
    @return dict Mapping des refs synthétiques 'Zn' vers leurs vraies refs.
    """
    expansion = {}
    for _u, _v, data in reduit.edges(data=True):
        ref = data.get('ref', '')
        refs = data.get('refs', [])
        if len(refs) > 1:
            expansion[ref] = list(refs)
    return expansion


def expandre_composites(match: dict, expansion: dict) -> dict:
    """@brief Remplace dans match['components'] chaque ref synthétique par ses vraies refs.

    @param match Dict du circuit détecté (clé 'components').
    @param expansion Table {ref_synthetique -> [refs_reelles]}.
    @return dict Copie du match aux vraies refs ; l'original n'est pas modifié.
    """
    if not expansion:
        return match
    comps = []
    for ref in match['components']:
        comps.extend(expansion.get(ref, [ref]))
    return {**match, 'components': comps}
