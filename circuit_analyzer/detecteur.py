"""
@file detecteur.py
@brief Détection des circuits électroniques dans un graphe de connexions.

Chaque fonction de ce fichier détecte un type de circuit précis.
Elles prennent toutes le graphe NetworkX en entrée et retournent
une liste de dictionnaires avec les clés :
  - 'circuit_type' : nom du circuit trouvé (ex: "Amplificateur inverseur (AOP)")
  - 'components'   : liste des références des composants (ex: ['R1', 'C2'])
  - 'nodes'        : liste des nœuds électriques impliqués (ex: ['VCC', 'NET1', 'GND'])

Ordre d'appel important (voir la fonction principale `analyser`) :
  Les circuits complexes (AOP, transistors) sont cherchés EN PREMIER.
  Si un composant est déjà utilisé dans un circuit complexe, il ne sera
  pas "volé" par un circuit plus simple.
  Exemple : une résistance dans un montage AOP ne doit pas être aussi
  détectée comme un "pont diviseur de tension".
"""

import networkx as nx
from circuit_analyzer.patterns.base import (
    is_ground_net, is_power_net, is_protective_earth_net, classify_net
)
from circuit_analyzer.value_parser import parse_valeur
from circuit_analyzer.satellites import rattacher_satellites
from circuit_analyzer.ilots import detecter_ilots
from circuit_analyzer import impedance
from circuit_analyzer.impedance import expandre_composites

# Alias français (= les nouvelles fonctions enrichies par le fichier de config)
est_masse        = is_ground_net
est_alimentation = is_power_net
# Alias backward-compat utilisés dans les patterns existants
is_gnd   = is_ground_net
is_power = is_power_net


def _est_rail(noeud) -> bool:
    """@brief Vrai si le nœud est une masse, une alimentation ou une terre de protection.

    @param noeud Nom du nœud à tester.
    @return bool True si le nœud est un rail (GND / alimentation / terre de protection).
    """
    return bool(noeud) and (
        est_masse(noeud) or est_alimentation(noeud) or is_protective_earth_net(noeud)
    )


def _type_correspond(data, type_composant, inclure_z=False):
    """Retourne True si l'arete correspond au type attendu."""
    type_arete = data.get('type')
    if type_arete == type_composant:
        return True
    return inclure_z and type_composant == 'R' and type_arete == 'Z'


def _voisins_de_type(graphe, noeud, type_composant, inclure_z=False):
    """
    @brief Composants d'un type donné connectés à un nœud, avec leur autre extrémité.

    @param graphe Graphe NetworkX du circuit.
    @param noeud Nœud autour duquel chercher.
    @param type_composant Type recherché ('R', 'C', 'L', 'D'…).
    @return list[tuple] Liste de (ref_composant, autre_noeud).

    Exemple : _voisins_de_type(graphe, 'NET1', 'R') retourne toutes les
    résistances connectées au nœud NET1, avec l'autre extrémité de chaque R.
    """
    resultats = []
    for u, v, data in graphe.edges(noeud, data=True):
        if _type_correspond(data, type_composant, inclure_z=inclure_z):
            autre = v if u == noeud else u
            resultats.append((data['ref'], autre))
    return resultats


# =============================================================================
# DÉTECTION DES MONTAGES AOP (Amplificateurs Opérationnels)
# =============================================================================

def detecter_amplificateur_inverseur(graphe):
    """
    @brief Amplificateur inverseur : AOP avec une Z d'entrée sur IN- et une Z de feedback (OUT → IN-).

    @param graphe Graphe NetworkX (réduit) du circuit.
    @return list[dict] Circuits détectés, enrichis de 'impedances' (Zin/Zf) et 'gain'.

    Schéma :
        IN ──[Zin]── IN- ──[Zf]── OUT
                      └──── AOP ──┘

    Comment le reconnaître : 2 impédances sur IN-, l'une vient de l'entrée,
    l'autre relie la sortie à l'entrée négative (= contre-réaction). Le détecteur
    tourne sur le graphe réduit : chaque arête porte 'refs' + 'composition' (un
    composite Zf = R1+R2 est déjà une seule arête Z).
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_aop, comp in composants.items():
        if comp.type != 'U':
            continue

        entree_neg = comp.pins.get('IN-')
        sortie = comp.pins.get('OUT')
        if not entree_neg or not sortie:
            continue

        feedback = None      # {'refs','composition','nodes'}
        entree = None
        for u, v, data in graphe.edges(entree_neg, data=True):
            if not _type_correspond(data, 'R', inclure_z=True):
                continue
            autre = v if u == entree_neg else u
            bloc = {
                'refs': list(data.get('refs', [data['ref']])),
                'composition': data.get('composition', data['ref']),
                'nodes': (entree_neg, autre),
            }
            if autre == sortie:
                feedback = bloc
            elif entree is None:
                entree = bloc

        if feedback and entree:
            resultats.append({
                'circuit_type': 'Amplificateur inverseur (AOP)',
                'components': [ref_aop] + feedback['refs'] + entree['refs'],
                'nodes': [comp.pins.get('IN+', ''), entree_neg, sortie],
                'impedances': {'Zin': entree, 'Zf': feedback},
                'gain': '−Zf/Zin',
            })

    return resultats


def detecter_amplificateur_non_inverseur(graphe):
    """
    @brief Amplificateur non-inverseur : AOP avec R de feedback (OUT → IN-) et R vers GND sur IN-.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).

    Schéma :
        IN ──── IN+
                AOP ──── OUT ──[R_feedback]──┐
                IN- ──[R_gnd]── GND          │
                  └──────────────────────────┘
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_aop, comp in composants.items():
        if comp.type != 'U':
            continue

        entree_neg = comp.pins.get('IN-')
        sortie = comp.pins.get('OUT')
        if not entree_neg or not sortie:
            continue

        resistances_sur_inm = _voisins_de_type(graphe, entree_neg, 'R', inclure_z=True)

        r_feedback = [ref for ref, autre in resistances_sur_inm if autre == sortie]
        r_vers_gnd = [ref for ref, autre in resistances_sur_inm if est_masse(autre)]

        if r_feedback and r_vers_gnd:
            resultats.append({
                'circuit_type': 'Amplificateur non-inverseur (AOP)',
                'components': [ref_aop] + r_feedback + r_vers_gnd,
                'nodes': [comp.pins.get('IN+', ''), entree_neg, sortie],
            })

    return resultats


def detecter_suiveur_tension(graphe):
    """
    @brief Suiveur de tension (buffer) : la sortie est directement reliée à IN-.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Le gain est exactement 1 (pas de composants autour de l'AOP).

    Schéma :
        IN ──── IN+
                AOP ──── OUT
                IN- ──────┘  (court-circuit sortie → entrée négative)
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_aop, comp in composants.items():
        if comp.type != 'U':
            continue

        entree_neg = comp.pins.get('IN-')
        sortie = comp.pins.get('OUT')
        # Le suiveur a IN- directement connecté à OUT (même nœud électrique)
        if entree_neg and sortie and entree_neg == sortie:
            resultats.append({
                'circuit_type': 'Suiveur de tension (AOP)',
                'components': [ref_aop],
                'nodes': [comp.pins.get('IN+', ''), sortie],
            })

    return resultats


def _feedback_capacitif(bloc, composants) -> bool:
    """
    @brief Vrai si le bloc de contre-réaction est capacitif (intégrateur idéal ou réel).

    Deux formes acceptées :
      - condensateur seul (intégrateur idéal) ;
      - Rf // Cf (intégrateur réel « leaky » : une R en parallèle d'une C).
    Un feedback résistif pur, ou résonant (L et C), n'est PAS capacitif → ce n'est
    pas un intégrateur (reste un ampli inverseur / filtre).

    @param bloc Bloc de contre-réaction ({'refs', 'composition'}).
    @param composants Dict {ref → Composant} (pour les types).
    @return bool
    """
    refs = bloc['refs']
    types = [composants[r].type for r in refs if r in composants]
    if not any(t == 'C' for t in types):
        return False
    if len(refs) == 1:
        return types == ['C']                      # condensateur seul (idéal)
    # leaky : la composition doit être un parallèle de feuilles {une R, une C}
    arbre = impedance.arbre_expr(bloc['composition'])
    if arbre and arbre[0] == 'parallele' and all(c[0] == 'feuille' for c in arbre[1]):
        tset = sorted(composants[c[1]].type for c in arbre[1] if c[1] in composants)
        return tset == ['C', 'R']
    return False


def detecter_integrateur(graphe):
    """
    @brief Intégrateur : AOP avec Z d'entrée sur IN- et feedback capacitif (OUT → IN-).

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    La sortie est proportionnelle à l'intégrale du signal d'entrée.

    Schéma (Zf = condensateur seul, ou Rf // Cf pour l'intégrateur réel) :
        IN ──[Zin]── IN- ──[Zf]── OUT
                      └── AOP ────┘
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_aop, comp in composants.items():
        if comp.type != 'U':
            continue

        entree_neg = comp.pins.get('IN-')
        sortie = comp.pins.get('OUT')
        if not entree_neg or not sortie:
            continue

        entree = None
        feedback = None
        for u, v, data in graphe.edges(entree_neg, data=True):
            autre = v if u == entree_neg else u
            bloc = {
                'refs': list(data.get('refs', [data['ref']])),
                'composition': data.get('composition', data['ref']),
                'nodes': (entree_neg, autre),
            }
            if autre == sortie and _feedback_capacitif(bloc, composants):
                feedback = bloc                       # contre-réaction capacitive
            elif _type_correspond(data, 'R', inclure_z=True) and autre != sortie:
                entree = bloc

        if entree and feedback:
            resultats.append({
                'circuit_type': 'Intégrateur (AOP)',
                'components': [ref_aop] + entree['refs'] + feedback['refs'],
                'nodes': [comp.pins.get('IN+', ''), entree_neg, sortie],
                'impedances': {'Zin': entree, 'Zf': feedback},
                'gain': '−Zf/Zin',
            })

    return resultats


def _entree_capacitive(bloc, composants) -> bool:
    """
    @brief Vrai si le bloc d'entrée est capacitif (dérivateur idéal ou réel).

    Dual de _feedback_capacitif. Deux formes acceptées :
      - condensateur seul (dérivateur idéal) ;
      - Rin + Cin (dérivateur réel : une R en série du condensateur, qui borne le
        gain en haute fréquence et stabilise le montage).
    Une entrée résistive pure n'est PAS capacitive → ce n'est pas un dérivateur
    (reste un ampli inverseur).

    @param bloc Bloc d'entrée ({'refs', 'composition'}).
    @param composants Dict {ref → Composant} (pour les types).
    @return bool
    """
    refs = bloc['refs']
    types = [composants[r].type for r in refs if r in composants]
    if not any(t == 'C' for t in types):
        return False
    if len(refs) == 1:
        return types == ['C']                      # condensateur seul (idéal)
    # réel : la composition doit être une série de feuilles {une R, une C}
    arbre = impedance.arbre_expr(bloc['composition'])
    if arbre and arbre[0] == 'serie' and all(c[0] == 'feuille' for c in arbre[1]):
        tset = sorted(composants[c[1]].type for c in arbre[1] if c[1] in composants)
        return tset == ['C', 'R']
    return False


def detecter_derivateur(graphe):
    """
    @brief Dérivateur : AOP avec Z d'entrée capacitive sur IN- et feedback résistif (OUT → IN-).

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    La sortie est proportionnelle à la dérivée du signal d'entrée.

    Schéma (Zin = condensateur seul, ou Rin + Cin pour le dérivateur réel) :
        IN ──[Zin]── IN- ──[Zf]── OUT
                      └── AOP ────┘
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_aop, comp in composants.items():
        if comp.type != 'U':
            continue

        entree_neg = comp.pins.get('IN-')
        sortie = comp.pins.get('OUT')
        if not entree_neg or not sortie:
            continue

        entree = None
        feedback = None
        for u, v, data in graphe.edges(entree_neg, data=True):
            autre = v if u == entree_neg else u
            bloc = {
                'refs': list(data.get('refs', [data['ref']])),
                'composition': data.get('composition', data['ref']),
                'nodes': (entree_neg, autre),
            }
            if autre != sortie and _entree_capacitive(bloc, composants):
                entree = bloc                         # entrée capacitive
            elif _type_correspond(data, 'R', inclure_z=True) and autre == sortie:
                feedback = bloc                       # contre-réaction résistive

        if entree and feedback:
            resultats.append({
                'circuit_type': 'Dérivateur (AOP)',
                'components': [ref_aop] + entree['refs'] + feedback['refs'],
                'nodes': [comp.pins.get('IN+', ''), entree_neg, sortie],
                'impedances': {'Zin': entree, 'Zf': feedback},
                'gain': '−Zf/Zin',
            })

    return resultats


def detecter_bascule_schmitt(graphe):
    """
    @brief Bascule de Schmitt : AOP avec contre-réaction POSITIVE (R de OUT vers IN+).

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Crée une hystérésis qui évite les oscillations sur les seuils.

    Schéma :
        IN ──── IN-
                AOP ──── OUT ──[R]──┐
                IN+ ────────────────┘  (contre-réaction positive)
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_aop, comp in composants.items():
        if comp.type != 'U':
            continue

        entree_pos = comp.pins.get('IN+')
        entree_neg = comp.pins.get('IN-')
        sortie = comp.pins.get('OUT')
        if not all([entree_pos, entree_neg, sortie]):
            continue
        if entree_neg == sortie:
            continue  # C'est un suiveur, pas une bascule

        # Chercher une R qui relie la sortie à IN+ (contre-réaction positive)
        r_positive = [ref for ref, autre in _voisins_de_type(graphe, entree_pos, 'R', inclure_z=True)
                      if autre == sortie]

        if r_positive:
            resultats.append({
                'circuit_type': 'Bascule de Schmitt (AOP)',
                'components': [ref_aop] + r_positive,
                'nodes': [entree_pos, entree_neg, sortie],
            })

    return resultats


def detecter_comparateur(graphe):
    """
    @brief Comparateur : AOP sans aucune contre-réaction.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    La sortie bascule selon quel seuil est le plus grand (IN+ ou IN-).
    C'est le mode le plus basique : l'AOP est utilisé "en boucle ouverte".
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_aop, comp in composants.items():
        if comp.type != 'U':
            continue

        entree_pos = comp.pins.get('IN+')
        entree_neg = comp.pins.get('IN-')
        sortie = comp.pins.get('OUT')
        if not all([entree_pos, entree_neg, sortie]):
            continue
        if entree_neg == sortie:
            continue  # C'est un suiveur

        # Vérifier qu'il n'y a AUCUN composant entre la sortie et les entrées
        feedback_negatif = [
            d for u, v, d in graphe.edges(entree_neg, data=True)
            if d['type'] in ('R', 'C', 'Z') and (v if u == entree_neg else u) == sortie
        ]
        feedback_positif = [
            d for u, v, d in graphe.edges(entree_pos, data=True)
            if d['type'] in ('R', 'Z') and (v if u == entree_pos else u) == sortie
        ]

        if not feedback_negatif and not feedback_positif:
            resultats.append({
                'circuit_type': 'Comparateur (AOP)',
                'components': [ref_aop],
                'nodes': [entree_pos, entree_neg, sortie],
            })

    return resultats


def detecter_amplificateur_differentiel(graphe):
    """
    @brief Amplificateur différentiel : AOP avec 4 résistances formant un pont.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Mesure la DIFFÉRENCE entre deux tensions d'entrée.

    Schéma :
        IN1 ──[R1]── IN- ──[R2]── OUT   (pont résistif sur les deux entrées)
        IN2 ──[R3]── IN+ ──[R4]── GND
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_aop, comp in composants.items():
        if comp.type != 'U':
            continue

        entree_pos = comp.pins.get('IN+')
        entree_neg = comp.pins.get('IN-')
        sortie = comp.pins.get('OUT')
        if not all([entree_pos, entree_neg, sortie]):
            continue
        if entree_neg == sortie:
            continue

        # Résistances sur IN+
        r_inp_vers_gnd   = [ref for ref, autre in _voisins_de_type(graphe, entree_pos, 'R', inclure_z=True) if est_masse(autre)]
        r_inp_depuis_src = [ref for ref, autre in _voisins_de_type(graphe, entree_pos, 'R', inclure_z=True) if not est_masse(autre)]
        # Résistances sur IN-
        r_inm_feedback   = [ref for ref, autre in _voisins_de_type(graphe, entree_neg, 'R', inclure_z=True) if autre == sortie]
        r_inm_depuis_src = [ref for ref, autre in _voisins_de_type(graphe, entree_neg, 'R', inclure_z=True) if autre != sortie]

        if r_inp_vers_gnd and r_inp_depuis_src and r_inm_feedback and r_inm_depuis_src:
            resultats.append({
                'circuit_type': 'Amplificateur différentiel (AOP)',
                'components': [ref_aop] + r_inp_vers_gnd + r_inp_depuis_src + r_inm_feedback + r_inm_depuis_src,
                'nodes': [entree_pos, entree_neg, sortie],
            })

    return resultats


def detecter_amplificateur_sommateur(graphe):
    """
    @brief Amplificateur sommateur : AOP avec plusieurs R d'entrée sur IN-.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Calcule la somme (pondérée) de plusieurs signaux.

    Schéma :
        IN1 ──[R1]──┐
        IN2 ──[R2]──┤── IN- ──[Rf]── OUT
        IN3 ──[R3]──┘      └── AOP ──┘
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_aop, comp in composants.items():
        if comp.type != 'U':
            continue

        entree_neg = comp.pins.get('IN-')
        sortie = comp.pins.get('OUT')
        if not entree_neg or not sortie:
            continue

        resistances_sur_inm = _voisins_de_type(graphe, entree_neg, 'R', inclure_z=True)
        r_feedback = [ref for ref, autre in resistances_sur_inm if autre == sortie]
        r_entrees  = [ref for ref, autre in resistances_sur_inm if autre != sortie]

        # Un sommateur a AU MOINS 2 entrées distinctes
        if r_feedback and len(r_entrees) >= 2:
            resultats.append({
                'circuit_type': 'Amplificateur sommateur (AOP)',
                'components': [ref_aop] + r_feedback + r_entrees,
                'nodes': [comp.pins.get('IN+', ''), entree_neg, sortie],
            })

    return resultats


# =============================================================================
# DÉTECTION DES CIRCUITS À TRANSISTORS
# =============================================================================

def detecter_transistor_commutation(graphe):
    """
    @brief Transistor BJT en commutation : émetteur à la masse, R sur la base.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Le transistor sert d'interrupteur commandé par la base.

    Schéma :
        VCC ── Charge ── Collecteur
                         Transistor BJT
        CMD ──[R]───── Base
                         Emetteur ── GND
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_q, comp in composants.items():
        if comp.type != 'Q':
            continue

        base     = comp.pins.get('B')
        collecteur = comp.pins.get('C')
        emetteur = comp.pins.get('E')
        if not all([base, collecteur, emetteur]):
            continue

        # L'émetteur doit être à la masse pour un montage en commutation classique
        if not est_masse(emetteur):
            continue

        resistances_base = [ref for ref, _ in _voisins_de_type(graphe, base, 'R')]
        if resistances_base:
            resultats.append({
                'circuit_type': 'Transistor en commutation',
                'components': [ref_q] + resistances_base,
                'nodes': [base, collecteur, emetteur],
            })

    return resultats


def detecter_amplificateur_emetteur_commun(graphe):
    """
    @brief Amplificateur émetteur commun : BJT avec R au collecteur ET R à la base.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Configuration d'amplification la plus courante avec les BJT.

    Schéma :
        VCC ──[Rc]── Collecteur
                     Transistor BJT
        IN ──[Rb]─── Base
                     Emetteur ── GND (ou dégenération)
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_q, comp in composants.items():
        if comp.type != 'Q':
            continue

        base       = comp.pins.get('B')
        collecteur = comp.pins.get('C')
        emetteur   = comp.pins.get('E')
        if not all([base, collecteur, emetteur]):
            continue

        r_collecteur = [ref for ref, _ in _voisins_de_type(graphe, collecteur, 'R')]
        r_base       = [ref for ref, _ in _voisins_de_type(graphe, base, 'R')]

        if r_collecteur and r_base:
            resultats.append({
                'circuit_type': 'Amplificateur émetteur commun',
                'components': [ref_q] + r_collecteur + r_base,
                'nodes': [base, collecteur, emetteur],
            })

    return resultats


def detecter_miroir_courant(graphe):
    """
    @brief Miroir de courant BJT : deux transistors avec la base commune et les émetteurs à GND.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Copie un courant de référence vers une charge.

    Schéma :
        VCC ──── C1    C2 ──── Charge
                  Q1    Q2
                  B ────B   (bases communes)
                  E     E
                  │     │
                 GND   GND
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    # Grouper par net de base : le miroir exige une base commune, inutile
    # (et quadratique) de comparer des BJT de bases différentes.
    groupes: dict = {}
    for ref, comp in composants.items():
        if comp.type != 'Q':
            continue
        base     = comp.pins.get('B')
        emetteur = comp.pins.get('E')
        if not base or not emetteur or not est_masse(emetteur):
            continue
        groupes.setdefault(base, []).append((ref, comp))

    for base, bjts in groupes.items():
        for i in range(len(bjts)):
            for j in range(i + 1, len(bjts)):
                ref1, q1 = bjts[i]
                ref2, q2 = bjts[j]
                resultats.append({
                    'circuit_type': 'Miroir de courant BJT',
                    'components': [ref1, ref2],
                    'nodes': [base, q1.pins.get('C', ''), q2.pins.get('C', '')],
                })

    return resultats


def detecter_mosfet_commutation(graphe):
    """
    @brief MOSFET en commutation (côté bas) : source à la masse, R sur la grille.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Fonctionne comme un interrupteur commandé par la tension de grille.
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_m, comp in composants.items():
        if comp.type != 'M':
            continue

        grille = comp.pins.get('G')
        drain  = comp.pins.get('D')
        source = comp.pins.get('S')
        if not all([grille, drain, source]):
            continue

        if not est_masse(source):
            continue

        r_grille = [ref for ref, _ in _voisins_de_type(graphe, grille, 'R')]
        if r_grille:
            resultats.append({
                'circuit_type': 'MOSFET en commutation',
                'components': [ref_m] + r_grille,
                'nodes': [grille, drain, source],
            })

    return resultats


def detecter_mosfet_cote_haut(graphe):
    """
    @brief MOSFET côté haut : drain sur rail d'alimentation, source NON à la masse.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Utilisé pour commuter la puissance vers la charge depuis le haut.
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_m, comp in composants.items():
        if comp.type != 'M':
            continue

        grille = comp.pins.get('G')
        drain  = comp.pins.get('D')
        source = comp.pins.get('S')
        if not all([grille, drain, source]):
            continue

        if est_masse(source):
            continue  # Déjà détecté comme MOSFET commutation (côté bas)
        if not est_alimentation(drain):
            continue  # Le drain doit être sur un rail positif

        r_grille = [ref for ref, _ in _voisins_de_type(graphe, grille, 'R')]
        if r_grille:
            resultats.append({
                'circuit_type': 'MOSFET haute-tension (côté haut)',
                'components': [ref_m] + r_grille,
                'nodes': [grille, drain, source],
            })

    return resultats


def detecter_commande_relais(graphe):
    """
    @brief Commande de relais : bobine de relais K alimentée par un transistor (BJT ou MOSFET).

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Le transistor commute la bobine du relais.

    Schéma :
        VCC ──[bobine K]── Collecteur
                           Transistor
        CMD ──────────── Base
                           Emetteur ── GND
    """
    resultats = []
    composants = graphe.graph.get('components', {})
    deja_vus = set()

    for ref_k, comp_k in composants.items():
        if comp_k.type != 'K':
            continue

        a1 = comp_k.pins.get('A1')
        a2 = comp_k.pins.get('A2')
        if not a1 or not a2:
            continue

        # Trouver le nœud de commutation (celui qui n'est pas l'alimentation)
        if est_alimentation(a1) and not est_alimentation(a2) and not est_masse(a2):
            noeud_commutation = a2
        elif est_masse(a2) and not est_masse(a1) and not est_alimentation(a1):
            noeud_commutation = a1
        else:
            continue

        # Chercher un transistor dont le collecteur/drain est sur le nœud de commutation
        transistors_trouves = []
        for ref2, comp2 in composants.items():
            if comp2.type == 'Q':
                if comp2.pins.get('C') == noeud_commutation and est_masse(comp2.pins.get('E', '')):
                    transistors_trouves.append(ref2)
            elif comp2.type == 'M':
                if comp2.pins.get('D') == noeud_commutation and est_masse(comp2.pins.get('S', '')):
                    transistors_trouves.append(ref2)

        if not transistors_trouves:
            continue

        cle = frozenset([ref_k] + transistors_trouves)
        if cle in deja_vus:
            continue
        deja_vus.add(cle)

        noeuds = [a1, noeud_commutation] if noeud_commutation != a1 else [noeud_commutation, a2]
        resultats.append({
            'circuit_type': 'Commande de relais',
            'components': [ref_k] + transistors_trouves,
            'nodes': noeuds,
        })

    return resultats


# =============================================================================
# DÉTECTION DES CIRCUITS PASSIFS ET DE PROTECTION
# =============================================================================

def detecter_pont_redresseur(graphe):
    """
    @brief Pont redresseur de Graetz : 4 diodes formant un cycle fermé (pont en H).

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Convertit une tension alternative en tension continue.

    Schéma (en forme de losange) :
          AC+ ─── D1 ─── DC+
           │               │
          D4               D2
           │               │
          AC- ─── D3 ─── DC-
    """
    resultats = []

    # Construire une liste d'adjacence : nœud → [(voisin, ref_diode)]
    adj_diodes = {}
    for u, v, data in graphe.edges(data=True):
        if data['type'] != 'D':
            continue
        adj_diodes.setdefault(u, []).append((v, data['ref']))
        adj_diodes.setdefault(v, []).append((u, data['ref']))

    cycles_vus = set()

    # Chercher un cycle de longueur 4 dans le graphe des diodes
    for n1 in adj_diodes:
        for n2, d1 in adj_diodes[n1]:
            if n2 == n1:
                continue
            for n3, d2 in adj_diodes.get(n2, []):
                if n3 in (n1, n2):
                    continue
                for n4, d3 in adj_diodes.get(n3, []):
                    if n4 in (n1, n2, n3):
                        continue
                    # Vérifier si n4 reboucle sur n1 avec une 4e diode différente
                    for retour, d4 in adj_diodes.get(n4, []):
                        if retour == n1 and len({d1, d2, d3, d4}) == 4:
                            noeuds_cycle = {n1, n2, n3, n4}
                            # Exclure les arrays ESD (qui ont à la fois une alim ET une masse)
                            if est_alimentation(n1) and est_masse(n1):
                                continue
                            a_alim = any(est_alimentation(n) for n in noeuds_cycle)
                            a_masse = any(est_masse(n) for n in noeuds_cycle)
                            if a_alim and a_masse:
                                continue  # Array ESD, pas un pont redresseur
                            cle = frozenset([d1, d2, d3, d4])
                            if cle not in cycles_vus:
                                cycles_vus.add(cle)
                                resultats.append({
                                    'circuit_type': 'Pont redresseur (Graetz)',
                                    'components': [d1, d2, d3, d4],
                                    'nodes': [n1, n2, n3, n4],
                                })
    return resultats


def detecter_diode_roue_libre(graphe):
    """
    @brief Diode de roue libre : cathode sur l'alimentation, anode sur le nœud de commutation.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Protège le transistor contre les surtensions des charges inductives (moteurs, relais).

    Schéma :
        VCC ─── K ─── [Diode] ─── A ─── nœud de commutation
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_d, comp in composants.items():
        if comp.type != 'D':
            continue

        cathode = comp.pins.get('K')
        anode   = comp.pins.get('A')
        if not cathode or not anode:
            continue

        # Roue libre : cathode sur alim, anode sur nœud ni alim ni masse
        if est_alimentation(cathode) and not est_masse(anode) and not est_alimentation(anode):
            resultats.append({
                'circuit_type': 'Diode de roue libre',
                'components': [ref_d],
                'nodes': [anode, cathode],
            })

    return resultats


def detecter_diode_protection_esd(graphe):
    """
    @brief Diode de protection ESD / TVS / Zener.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Protège les entrées/sorties contre les décharges électrostatiques.

    Reconnaissance : une broche de la diode est à la masse (anode OU cathode).
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_d, comp in composants.items():
        if comp.type != 'D':
            continue

        anode   = comp.pins.get('A') or comp.pins.get('1', '')
        cathode = comp.pins.get('K') or comp.pins.get('2', '')
        if not anode or not cathode:
            continue

        if est_masse(anode) or est_masse(cathode):
            resultats.append({
                'circuit_type': 'Diode de protection ESD',
                'components': [ref_d],
                'nodes': [anode, cathode],
            })

    return resultats


def detecter_redresseur_simple(graphe):
    """
    @brief Redresseur simple alternance : diode + résistance de charge vers GND.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    La forme la plus simple de redressement.

    Schéma :
        AC ── [Diode] ── nœud ── [R_charge] ── GND
    """
    resultats = []
    deja_vus = set()
    composants = graphe.graph.get('components', {})

    for ref_d, comp in composants.items():
        if comp.type != 'D':
            continue

        anode   = comp.pins.get('A') or comp.pins.get('1', '')
        cathode = comp.pins.get('K') or comp.pins.get('2', '')
        if not anode or not cathode:
            continue

        # Exclure les diodes déjà classées dans d'autres catégories
        if est_alimentation(cathode):  # Roue libre
            continue
        if est_masse(anode):           # Protection ESD
            continue
        if est_alimentation(anode):    # LED indicateur ou autre
            continue

        # Chercher une R de charge sur la cathode vers GND
        for ref_r, autre in _voisins_de_type(graphe, cathode, 'R'):
            if ref_r == ref_d:
                continue
            if est_masse(autre):
                cle = frozenset([ref_d, ref_r])
                if cle not in deja_vus:
                    deja_vus.add(cle)
                    resultats.append({
                        'circuit_type': 'Redresseur simple alternance',
                        'components': [ref_d, ref_r],
                        'nodes': [anode, cathode, autre],
                    })

    return resultats


def detecter_detecteur_crete(graphe):
    """
    @brief Détecteur de crête : diode + condensateur vers GND.

    @param graphe Graphe NetworkX du circuit.
    @return list[dict] Circuits détectés ({'circuit_type', 'components', 'nodes'}).
    Le condensateur se charge au pic du signal et le mémorise.

    Schéma :
        AC ── [Diode] ── nœud ── [C] ── GND
    """
    resultats = []
    deja_vus = set()
    composants = graphe.graph.get('components', {})

    for ref_d, comp in composants.items():
        if comp.type != 'D':
            continue

        anode   = comp.pins.get('A') or comp.pins.get('1', '')
        cathode = comp.pins.get('K') or comp.pins.get('2', '')
        if not anode or not cathode:
            continue

        if est_alimentation(cathode) or est_masse(anode):
            continue

        # Chercher un C vers GND sur la cathode
        for ref_c, autre in _voisins_de_type(graphe, cathode, 'C'):
            if est_masse(autre):
                cle = frozenset([ref_d, ref_c])
                if cle not in deja_vus:
                    deja_vus.add(cle)
                    resultats.append({
                        'circuit_type': 'Détecteur de crête',
                        'components': [ref_d, ref_c],
                        'nodes': [anode, cathode, autre],
                    })

    return resultats


def detecter_impedances(graphe):
    """
    @brief Émet chaque arête Z (passive réduite) comme une « Impédance Z ».

    @param graphe Graphe RÉDUIT (sortie de impedance.reduire()).
    @return list[dict] Un match par arête passive, {'circuit_type', 'components',
            'nodes', 'composition'}.

    Placé en dernier dans la chaîne de détection : l'anti-vol d'analyser() saute
    les Z dont les composants sont déjà pris par un montage actif. Ce qui reste
    devient une impédance nommée — plus aucun passif « non classifié ».
    """
    resultats = []
    for u, v, data in graphe.edges(data=True):
        if data.get('type') not in ('R', 'C', 'L', 'Z'):
            continue  # diodes, etc. : pas des impédances passives
        resultats.append({
            'circuit_type': 'Impédance Z',
            'components': [data['ref']],
            'nodes': [u, v],
            'composition': data.get('composition', data['ref']),
        })
    return resultats


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

# =============================================================================
# RÉSULTAT D'ANALYSE — liste étendue avec métadonnées
# =============================================================================

class ResultatsAnalyse(list):
    """
    @brief Liste de circuits détectés, compatible avec list, enrichie de métadonnées.

    Attributs supplémentaires :
        .supprimes    : matches ignorés car leurs composants étaient déjà pris
        .ilots        : îlots fonctionnels (structure en étages du schéma)
        .transparents : refs des fusibles neutralisés (retirés du graphe réduit)
    """
    def __init__(self, matches=None):
        """@brief Initialise la liste de résultats et ses métadonnées.

        @param matches Matches initiaux à placer dans la liste (optionnel).
        @return None
        """
        super().__init__(matches or [])
        self.supprimes: list[dict] = []
        self.ilots: list[dict] = []
        self.transparents: list[str] = []


# Catégorie fonctionnelle par type de circuit
_CATEGORIES: dict[str, str] = {
    'Amplificateur inverseur (AOP)':       'amplification',
    'Amplificateur non-inverseur (AOP)':   'amplification',
    'Suiveur de tension (AOP)':            'amplification',
    'Intégrateur (AOP)':                   'traitement_signal',
    'Dérivateur (AOP)':                    'traitement_signal',
    'Bascule de Schmitt (AOP)':            'traitement_signal',
    'Comparateur (AOP)':                   'comparaison',
    'Amplificateur différentiel (AOP)':    'amplification',
    'Amplificateur sommateur (AOP)':       'traitement_signal',
    'Transistor en commutation':           'commutation',
    'Amplificateur émetteur commun':       'amplification',
    'Miroir de courant BJT':               'polarisation',
    'MOSFET en commutation':               'commutation',
    'MOSFET haute-tension (côté haut)':    'commutation',
    'Commande de relais':                  'commutation',
    'Pont redresseur (Graetz)':            'alimentation',
    'Diode de roue libre':                 'protection',
    'Diode de protection ESD':             'protection',
    'Redresseur simple alternance':        'alimentation',
    'Détecteur de crête':                  'traitement_signal',
    'Impédance Z':                         'impedance',
}


def _valeur(graphe, ref: str) -> str:
    """@brief Retourne la valeur d'un composant.

    Cherche dans le dict des composants multi-broches puis dans les arêtes.

    @param graphe Graphe NetworkX du circuit.
    @param ref Référence du composant recherché.
    @return str Valeur du composant, ou '' si absente/introuvable.
    """
    if not ref:
        return ''
    comp = graphe.graph.get('components', {}).get(ref)
    if comp:
        return comp.value or ''
    for u, v, data in graphe.edges(data=True):
        if data.get('ref') == ref:
            return data.get('value', '')
    return ''


def _enrichir(match: dict, graphe) -> dict:
    """
    @brief Enrichit un match de détection avec confiance, raisons et avertissements.

    Ajoute confidence, confidence_level, reasons, warnings, functional_category
    et locked_components.

    @param match Match brut ({'circuit_type', 'components', 'nodes'}).
    @param graphe Graphe NetworkX d'origine (pour lire les valeurs des composants).
    @return dict Copie enrichie du match ; le dict original n'est pas modifié.
    """
    ct     = match['circuit_type']
    comps  = match['components']
    nodes  = match.get('nodes', [])

    reasons:  list[str] = []
    warnings: list[str] = []
    confidence = 0.80

    # ── Vérification PE/CHASSIS (ne doit pas être traité comme GND) ──────────
    for n in nodes:
        if n and is_protective_earth_net(n):
            warnings.append(
                f"Nœud PE/CHASSIS '{n}' détecté — ne pas confondre avec GND"
            )

    # ── Logique par type de circuit ───────────────────────────────────────────

    if ct == 'Suiveur de tension (AOP)':
        confidence = 0.95
        reasons.append("IN- directement relié à OUT (même nœud électrique)")

    elif ct in ('Amplificateur inverseur (AOP)', 'Amplificateur non-inverseur (AOP)'):
        confidence = 0.90
        reasons.append("Contre-réaction négative via résistance entre OUT et IN-")

    elif ct in ('Intégrateur (AOP)', 'Dérivateur (AOP)'):
        confidence = 0.90
        reasons.append("Contre-réaction via condensateur/résistance entre OUT et IN-")

    elif ct == 'Bascule de Schmitt (AOP)':
        confidence = 0.90
        reasons.append("Contre-réaction positive via résistance entre OUT et IN+")

    elif ct == 'Comparateur (AOP)':
        confidence = 0.75
        reasons.append("AOP sans contre-réaction (boucle ouverte)")
        warnings.append("Peut être un AOP mal câblé — vérifier l'absence intentionnelle de feedback")

    elif ct in ('Amplificateur différentiel (AOP)', 'Amplificateur sommateur (AOP)'):
        confidence = 0.85
        reasons.append("Pont résistif sur IN+ et IN-" if 'différentiel' in ct
                        else "Plusieurs résistances d'entrée sur IN-")

    elif ct in ('Transistor en commutation', 'MOSFET en commutation'):
        confidence = 0.85
        reasons.append("Émetteur/Source à GND + résistance de commande sur Base/Grille")

    elif ct == 'MOSFET haute-tension (côté haut)':
        confidence = 0.85
        reasons.append("Drain sur alimentation, source non reliée à GND")

    elif ct == 'Amplificateur émetteur commun':
        confidence = 0.85
        reasons.append("Résistance sur collecteur + résistance sur base")

    elif ct == 'Miroir de courant BJT':
        confidence = 0.90
        reasons.append("Deux BJT avec bases communes et émetteurs à GND")

    elif ct == 'Commande de relais':
        confidence = 0.85
        reasons.append("Bobine de relais + transistor (collecteur/drain sur bobine)")

    elif ct == 'Pont redresseur (Graetz)':
        confidence = 0.95
        reasons.append("Cycle fermé de 4 diodes détecté")

    elif ct == 'Diode de roue libre':
        confidence = 0.70
        reasons.append("Cathode sur rail d'alimentation, anode sur nœud de commutation")
        warnings.append("Topologie compatible avec une LED indicateur selon le contexte")

    elif ct == 'Diode de protection ESD':
        confidence = 0.65
        reasons.append("Une broche de la diode reliée à GND")
        warnings.append("Topologie compatible LED / TVS / Zener / redresseur selon le contexte")

    elif ct == 'Redresseur simple alternance':
        confidence = 0.65
        reasons.append("Diode en série + résistance de charge vers GND")
        warnings.append("Topologie compatible LED avec résistance de limitation de courant")

    elif ct == 'Détecteur de crête':
        confidence = 0.75
        reasons.append("Diode en série + condensateur vers GND")

    elif ct == 'Impédance Z':
        confidence = 0.80
        compo = match.get('composition', '')
        if compo:
            reasons.append(f"Impédance équivalente : {compo}")
        else:
            reasons.append("Impédance passive réduite")

    # ── Niveau de confiance ───────────────────────────────────────────────────
    if confidence >= 0.80:
        level = 'high'
    elif confidence >= 0.55:
        level = 'medium'
    else:
        level = 'low'

    result = dict(match)
    result['confidence']          = round(confidence, 2)
    result['confidence_level']    = level
    result['reasons']             = reasons
    result['warnings']            = warnings
    result['functional_category'] = _CATEGORIES.get(ct, 'divers')
    result['locked_components']   = list(comps)
    return result


# Détecteurs prioritaires (circuits complexes — AOP, transistors, diodes)
# Ces détecteurs sont appelés EN PREMIER pour éviter qu'un composant
# d'un circuit complexe soit "volé" par un circuit simple.
_DETECTEURS_COMPLEXES = [
    detecter_amplificateur_differentiel,   # 4 résistances en pont
    detecter_amplificateur_sommateur,      # plusieurs R d'entrée sur IN-
    detecter_integrateur,                  # R entrée + C feedback
    detecter_derivateur,                   # C entrée + R feedback
    detecter_bascule_schmitt,              # R de feedback positif
    detecter_amplificateur_non_inverseur,  # R feedback + R vers GND
    detecter_amplificateur_inverseur,      # R entrée + R feedback
    detecter_suiveur_tension,              # IN- = OUT (court-circuit)
    detecter_comparateur,                  # AOP sans feedback
    detecter_miroir_courant,               # 2 BJT, bases communes
    detecter_commande_relais,              # Relais + transistor
    detecter_amplificateur_emetteur_commun,
    detecter_transistor_commutation,
    detecter_mosfet_commutation,
    detecter_mosfet_cote_haut,
    detecter_pont_redresseur,
    detecter_diode_roue_libre,
    detecter_diode_protection_esd,
    detecter_redresseur_simple,
    detecter_detecteur_crete,
]

# Détecteurs simples (passifs réduits — appelés EN DERNIER)
# Les patterns personnalisés (créés via l'interface) s'insèrent entre les deux.
# Tout passif R/L/C résiduel est émis comme « Impédance Z » par detecter_impedances :
# il n'existe plus de détecteur passif nommé (filtre RC, pont diviseur, etc.).
_DETECTEURS_SIMPLES = [
    detecter_impedances,
]

# Noms de tous les circuits intégrés, dans l'ordre d'affichage de l'interface
NOMS_CIRCUITS = [
    "Amplificateur différentiel (AOP)", "Amplificateur sommateur (AOP)",
    "Intégrateur (AOP)", "Dérivateur (AOP)", "Bascule de Schmitt (AOP)",
    "Amplificateur non-inverseur (AOP)", "Amplificateur inverseur (AOP)",
    "Suiveur de tension (AOP)", "Comparateur (AOP)",
    "Miroir de courant BJT", "Commande de relais",
    "Amplificateur émetteur commun", "Transistor en commutation",
    "MOSFET en commutation", "MOSFET haute-tension (côté haut)",
    "Pont redresseur (Graetz)", "Diode de roue libre",
    "Diode de protection ESD", "Redresseur simple alternance", "Détecteur de crête",
    "Impédance Z",
]

# Alias pour compatibilité
match_patterns = None  # défini après analyser()


def analyser(graphe, patterns_personnalises=None):
    """
    @brief Analyse le graphe et retourne tous les circuits détectés.

    Chaque composant ne peut appartenir qu'à UN SEUL circuit.
    Les circuits complexes sont prioritaires sur les circuits simples.

    @param graphe Le graphe NetworkX construit par graph_builder.py.
    @param patterns_personnalises Liste optionnelle de fonctions de détection supplémentaires.
    @return ResultatsAnalyse Liste enrichie de dicts {'circuit_type', 'components', 'nodes', …},
            avec les attributs .supprimes (matches ignorés) et .ilots (structure en étages).
    """
    # Charger les patterns personnalisés depuis l'interface graphique (si présents)
    # Ils s'insèrent entre les circuits complexes et les circuits simples.
    if patterns_personnalises is None:
        try:
            from custom_circuits.loader import get_custom_patterns
            objets_custom = get_custom_patterns()
            # Les patterns custom retournent {'components': ..., 'nodes': ...} sans 'circuit_type'.
            # On crée une fonction wrapper qui ajoute le nom du circuit.
            def _envelopper(pattern):
                """@brief Adapte un objet Pattern personnalisé en fonction détecteur.

                @param pattern Instance de Pattern personnalisé chargée depuis le JSON.
                @return callable Détecteur qui ajoute la clé 'circuit_type' aux matches.
                """
                def detecter(graphe):
                    """@brief Exécute le pattern personnalisé sur un graphe.

                    @param graphe Graphe NetworkX à analyser.
                    @return generator Matches enrichis avec le nom du circuit personnalisé.
                    """
                    for match in pattern.match(graphe):
                        yield {**match, 'circuit_type': pattern.name}
                return detecter
            patterns_personnalises = [_envelopper(p) for p in objets_custom]
        except Exception:
            patterns_personnalises = []

    # Ordre final : complexes → personnalisés → simples
    tous_les_detecteurs = _DETECTEURS_COMPLEXES + list(patterns_personnalises) + _DETECTEURS_SIMPLES

    # Réduction préalable (directive métier en rouge du document de référence) :
    # les sous-réseaux passifs série/parallèle sont collapsés en dipôles
    # équivalents, pour que les détecteurs reconnaissent un montage dont la
    # contre-réaction (ou l'entrée) est un composite « Rf = R1+R2 ». La détection
    # tourne sur le graphe réduit ; les refs synthétiques (Z#k) sont ré-expansées
    # juste après, pour que enrichissement, satellites et îlots travaillent sur
    # les vraies refs et le graphe original.
    graphe_reduit = impedance.reduire(graphe)
    expansion = impedance.expansion_depuis_graphe(graphe_reduit)

    composants_utilises: set = set()
    circuits_trouves: list  = []
    supprimes: list         = []

    for detecter in tous_les_detecteurs:
        for match in detecter(graphe_reduit):
            match = expandre_composites(match, expansion)
            # Test anti-vol AVANT enrichissement : inutile de calculer la
            # confiance des matches supprimés (ils peuvent être très nombreux).
            if any(c in composants_utilises for c in match['components']):
                supprimes.append(match)
                continue
            composants_utilises.update(match['components'])
            circuits_trouves.append(_enrichir(match, graphe))

    # Passe satellite : absorbe les annexes mono-composant puis rattache
    # les composants restés non classifiés aux circuits détectés.
    rattacher_satellites(circuits_trouves, graphe, composants_utilises)

    resultats = ResultatsAnalyse(circuits_trouves)
    resultats.supprimes = supprimes
    # Fusibles neutralisés par la réduction : remontés pour que le rapport ne les
    # liste pas comme « non classifiés ».
    resultats.transparents = list(graphe_reduit.graph.get('fusibles_transparents', []))
    # Structure en étages : îlots de connexité hors rails
    resultats.ilots = detecter_ilots(graphe, circuits_trouves)
    return resultats


# Alias anglais — pour que l'ancien code qui appelle match_patterns() continue à fonctionner
match_patterns = analyser
