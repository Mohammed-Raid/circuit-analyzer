"""
Détection des circuits électroniques dans un graphe de connexions.

Chaque fonction de ce fichier détecte un type de circuit précis.
Elles prennent toutes le graphe NetworkX en entrée et retournent
une liste de dictionnaires avec les clés :
  - 'circuit_type' : nom du circuit trouvé (ex: "Filtre RC passe-bas")
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

# Alias français (= les nouvelles fonctions enrichies par le fichier de config)
est_masse        = is_ground_net
est_alimentation = is_power_net
# Alias backward-compat utilisés dans les patterns existants
is_gnd   = is_ground_net
is_power = is_power_net


def _est_rail(noeud) -> bool:
    """Vrai si le nœud est une masse, une alimentation ou une terre de protection."""
    return bool(noeud) and (
        est_masse(noeud) or est_alimentation(noeud) or is_protective_earth_net(noeud)
    )


def _voisins_de_type(graphe, noeud, type_composant):
    """
    Retourne la liste de (ref_composant, autre_noeud) pour tous les composants
    d'un type donné connectés au nœud indiqué.

    Exemple : _voisins_de_type(graphe, 'NET1', 'R') retourne toutes les
    résistances connectées au nœud NET1, avec l'autre extrémité de chaque R.
    """
    resultats = []
    for u, v, data in graphe.edges(noeud, data=True):
        if data['type'] == type_composant:
            autre = v if u == noeud else u
            resultats.append((data['ref'], autre))
    return resultats


# =============================================================================
# DÉTECTION DES MONTAGES AOP (Amplificateurs Opérationnels)
# =============================================================================

def detecter_amplificateur_inverseur(graphe):
    """
    Amplificateur inverseur : AOP avec une R d'entrée sur IN- et une R de feedback (OUT → IN-).

    Schéma :
        IN ──[R_entree]── IN- ──[R_feedback]── OUT
                           └────── AOP ──────┘

    Comment le reconnaître : 2 résistances sur IN-, l'une vient de l'entrée,
    l'autre relie la sortie à l'entrée négative (= contre-réaction).
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

        resistances_sur_inm = _voisins_de_type(graphe, entree_neg, 'R')

        # La R de feedback relie la sortie à IN- (contre-réaction négative)
        r_feedback = [ref for ref, autre in resistances_sur_inm if autre == sortie]
        # Les autres R sur IN- sont les résistances d'entrée
        r_entree   = [ref for ref, autre in resistances_sur_inm if autre != sortie]

        if r_feedback and r_entree:
            resultats.append({
                'circuit_type': 'Amplificateur inverseur (AOP)',
                'components': [ref_aop] + r_feedback + r_entree,
                'nodes': [comp.pins.get('IN+', ''), entree_neg, sortie],
            })

    return resultats


def detecter_amplificateur_non_inverseur(graphe):
    """
    Amplificateur non-inverseur : AOP avec R de feedback (OUT → IN-) et R vers GND sur IN-.

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

        resistances_sur_inm = _voisins_de_type(graphe, entree_neg, 'R')

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
    Suiveur de tension (buffer) : la sortie est directement reliée à IN-.
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


def detecter_integrateur(graphe):
    """
    Intégrateur : AOP avec R d'entrée sur IN- et condensateur de feedback (OUT → IN-).
    La sortie est proportionnelle à l'intégrale du signal d'entrée.

    Schéma :
        IN ──[R]── IN- ──[C]── OUT
                    └── AOP ───┘
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

        r_entree = []
        c_feedback = []
        for u, v, data in graphe.edges(entree_neg, data=True):
            autre = v if u == entree_neg else u
            if data['type'] == 'R' and autre != sortie:
                r_entree.append(data['ref'])
            elif data['type'] == 'C' and autre == sortie:
                c_feedback.append(data['ref'])

        if r_entree and c_feedback:
            resultats.append({
                'circuit_type': 'Intégrateur (AOP)',
                'components': [ref_aop] + r_entree + c_feedback,
                'nodes': [comp.pins.get('IN+', ''), entree_neg, sortie],
            })

    return resultats


def detecter_derivateur(graphe):
    """
    Dérivateur : AOP avec condensateur d'entrée sur IN- et R de feedback (OUT → IN-).
    La sortie est proportionnelle à la dérivée du signal d'entrée.

    Schéma :
        IN ──[C]── IN- ──[R]── OUT
                    └── AOP ───┘
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

        c_entree = []
        r_feedback = []
        for u, v, data in graphe.edges(entree_neg, data=True):
            autre = v if u == entree_neg else u
            if data['type'] == 'C' and autre != sortie:
                c_entree.append(data['ref'])
            elif data['type'] == 'R' and autre == sortie:
                r_feedback.append(data['ref'])

        if c_entree and r_feedback:
            resultats.append({
                'circuit_type': 'Dérivateur (AOP)',
                'components': [ref_aop] + c_entree + r_feedback,
                'nodes': [comp.pins.get('IN+', ''), entree_neg, sortie],
            })

    return resultats


def detecter_bascule_schmitt(graphe):
    """
    Bascule de Schmitt : AOP avec contre-réaction POSITIVE (R de OUT vers IN+).
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
        r_positive = [ref for ref, autre in _voisins_de_type(graphe, entree_pos, 'R')
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
    Comparateur : AOP sans aucune contre-réaction.
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
            if d['type'] in ('R', 'C') and (v if u == entree_neg else u) == sortie
        ]
        feedback_positif = [
            d for u, v, d in graphe.edges(entree_pos, data=True)
            if d['type'] == 'R' and (v if u == entree_pos else u) == sortie
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
    Amplificateur différentiel : AOP avec 4 résistances formant un pont.
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
        r_inp_vers_gnd   = [ref for ref, autre in _voisins_de_type(graphe, entree_pos, 'R') if est_masse(autre)]
        r_inp_depuis_src = [ref for ref, autre in _voisins_de_type(graphe, entree_pos, 'R') if not est_masse(autre)]
        # Résistances sur IN-
        r_inm_feedback   = [ref for ref, autre in _voisins_de_type(graphe, entree_neg, 'R') if autre == sortie]
        r_inm_depuis_src = [ref for ref, autre in _voisins_de_type(graphe, entree_neg, 'R') if autre != sortie]

        if r_inp_vers_gnd and r_inp_depuis_src and r_inm_feedback and r_inm_depuis_src:
            resultats.append({
                'circuit_type': 'Amplificateur différentiel (AOP)',
                'components': [ref_aop] + r_inp_vers_gnd + r_inp_depuis_src + r_inm_feedback + r_inm_depuis_src,
                'nodes': [entree_pos, entree_neg, sortie],
            })

    return resultats


def detecter_amplificateur_sommateur(graphe):
    """
    Amplificateur sommateur : AOP avec plusieurs R d'entrée sur IN-.
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

        resistances_sur_inm = _voisins_de_type(graphe, entree_neg, 'R')
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
    Transistor BJT en commutation : émetteur à la masse, R sur la base.
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
    Amplificateur émetteur commun : BJT avec R au collecteur ET R à la base.
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
    Miroir de courant BJT : deux transistors avec la base commune et les émetteurs à GND.
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
    bjts = [(ref, comp) for ref, comp in composants.items() if comp.type == 'Q']
    deja_vus = set()

    # Comparer chaque paire de BJT
    for i in range(len(bjts)):
        for j in range(i + 1, len(bjts)):
            ref1, q1 = bjts[i]
            ref2, q2 = bjts[j]

            base1    = q1.pins.get('B')
            base2    = q2.pins.get('B')
            emetteur1 = q1.pins.get('E')
            emetteur2 = q2.pins.get('E')

            if not all([base1, base2, emetteur1, emetteur2]):
                continue

            # Condition miroir : mêmes bases, deux émetteurs à GND
            if base1 == base2 and est_masse(emetteur1) and est_masse(emetteur2):
                cle = frozenset([ref1, ref2])
                if cle not in deja_vus:
                    deja_vus.add(cle)
                    resultats.append({
                        'circuit_type': 'Miroir de courant BJT',
                        'components': [ref1, ref2],
                        'nodes': [base1, q1.pins.get('C', ''), q2.pins.get('C', '')],
                    })

    return resultats


def detecter_mosfet_commutation(graphe):
    """
    MOSFET en commutation (côté bas) : source à la masse, R sur la grille.
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
    MOSFET côté haut : drain sur rail d'alimentation, source NON à la masse.
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
    Commande de relais : bobine de relais K alimentée par un transistor (BJT ou MOSFET).
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
    Pont redresseur de Graetz : 4 diodes formant un cycle fermé (pont en H).
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
    Diode de roue libre : cathode sur l'alimentation, anode sur le nœud de commutation.
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
    Diode de protection ESD / TVS / Zener.
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
    Redresseur simple alternance : diode + résistance de charge vers GND.
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
    Détecteur de crête : diode + condensateur vers GND.
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


def detecter_condensateur_decouplage(graphe):
    """
    Condensateur de découplage : C directement entre une alimentation et la masse.
    Filtre les parasites haute fréquence sur les rails d'alimentation.
    Placé juste à côté des circuits intégrés.

    Schéma :
        VCC ──[C]── GND
    """
    resultats = []

    for u, v, data in graphe.edges(data=True):
        if data['type'] != 'C':
            continue

        # Le C doit être directement entre alim et masse (pas de R en parallèle)
        if not ((est_alimentation(u) and est_masse(v)) or (est_masse(u) and est_alimentation(v))):
            continue

        # Vérifier qu'il n'y a pas une R en parallèle (sinon c'est un absorbeur RC)
        edges_paralleles = graphe[u][v]
        a_r_en_parallele = any(
            d['type'] == 'R'
            for k, d in edges_paralleles.items()
            if d['ref'] != data['ref']
        )
        if not a_r_en_parallele:
            resultats.append({
                'circuit_type': 'Condensateur de découplage',
                'components': [data['ref']],
                'nodes': [u, v],
            })

    return resultats


def detecter_filtre_rc_passe_bas(graphe):
    """
    Filtre RC passe-bas : R en série + C vers GND.
    Laisse passer les basses fréquences, atténue les hautes.

    Schéma :
        IN ──[R]── MID ──[C]── GND
    """
    resultats = []
    deja_vus = set()

    for noeud in graphe.nodes():
        resistances   = _voisins_de_type(graphe, noeud, 'R')
        condensateurs = _voisins_de_type(graphe, noeud, 'C')

        for ref_r, autre_r in resistances:
            if est_masse(autre_r):
                continue  # La R va à la masse → pas une R série

            for ref_c, autre_c in condensateurs:
                if est_masse(autre_c):
                    cle = frozenset([ref_r, ref_c])
                    if cle not in deja_vus:
                        deja_vus.add(cle)
                        resultats.append({
                            'circuit_type': 'Filtre RC passe-bas',
                            'components': [ref_r, ref_c],
                            'nodes': [autre_r, noeud, autre_c],
                        })

    return resultats


def detecter_filtre_rc_passe_haut(graphe):
    """
    Filtre RC passe-haut : C en série + R vers GND.
    Laisse passer les hautes fréquences, atténue les basses.

    Schéma :
        IN ──[C]── MID ──[R]── GND
    """
    resultats = []
    deja_vus = set()

    for noeud in graphe.nodes():
        resistances   = _voisins_de_type(graphe, noeud, 'R')
        condensateurs = _voisins_de_type(graphe, noeud, 'C')

        for ref_r, autre_r in resistances:
            if not est_masse(autre_r):
                continue  # La R doit aller à la masse pour le passe-haut

            for ref_c, autre_c in condensateurs:
                if est_masse(autre_c):
                    continue  # Le C ne doit pas aller à la masse (ce serait un passe-bas)

                cle = frozenset([ref_r, ref_c])
                if cle not in deja_vus:
                    deja_vus.add(cle)
                    resultats.append({
                        'circuit_type': 'Filtre RC passe-haut',
                        'components': [ref_r, ref_c],
                        'nodes': [autre_c, noeud, autre_r],
                    })

    return resultats


def detecter_filtre_lc(graphe):
    """
    Filtre LC : inductance en série + condensateur vers GND.
    Utilisé dans les alimentations à découpage pour filtrer le courant.

    Schéma :
        IN ──[L]── MID ──[C]── GND
    """
    resultats = []
    deja_vus = set()

    for noeud in graphe.nodes():
        inductances    = _voisins_de_type(graphe, noeud, 'L')
        condensateurs  = _voisins_de_type(graphe, noeud, 'C')

        for ref_l, autre_l in inductances:
            for ref_c, autre_c in condensateurs:
                if est_masse(autre_c):
                    cle = frozenset([ref_l, ref_c])
                    if cle not in deja_vus:
                        deja_vus.add(cle)
                        resultats.append({
                            'circuit_type': 'Filtre LC',
                            'components': [ref_l, ref_c],
                            'nodes': [autre_l, noeud, autre_c],
                        })

    return resultats


def detecter_pont_diviseur(graphe):
    """
    Pont diviseur de tension : deux résistances en série entre deux points.
    Crée une tension intermédiaire à partir d'une tension plus élevée.

    Schéma :
        VCC ──[R1]── MID ──[R2]── GND
    """
    resultats = []
    deja_vus = set()

    for noeud in graphe.nodes():
        # Le nœud milieu d'un diviseur est toujours un nœud signal — énumérer
        # les paires de R sur GND/VCC serait à la fois faux et quadratique.
        if _est_rail(noeud):
            continue
        resistances = _voisins_de_type(graphe, noeud, 'R')

        # Chercher deux R connectées au même nœud mais vers des points différents
        for i in range(len(resistances)):
            for j in range(i + 1, len(resistances)):
                ref1, autre1 = resistances[i]
                ref2, autre2 = resistances[j]

                if autre1 == autre2:
                    continue  # Les deux R vont au même endroit → pas un diviseur

                cle = frozenset([ref1, ref2])
                if cle not in deja_vus:
                    deja_vus.add(cle)
                    resultats.append({
                        'circuit_type': 'Pont diviseur de tension',
                        'components': [ref1, ref2],
                        'nodes': [autre1, noeud, autre2],
                    })

    return resultats


def detecter_absorbeur_rc(graphe):
    """
    Absorbeur RC (snubber) : résistance et condensateur en PARALLÈLE.
    Absorbe les surtensions transitoires, protège les interrupteurs.

    Schéma :
        A ──[R]── B    (R et C entre les mêmes nœuds A et B)
        A ──[C]── B
    """
    resultats = []
    deja_vus = set()

    for noeud in graphe.nodes():
        for voisin in graphe.neighbors(noeud):
            # R parallèle C entre deux rails = bleeder + découplage, pas un snubber.
            if _est_rail(noeud) and _est_rail(voisin):
                continue
            paire = tuple(sorted([noeud, voisin]))
            if paire in deja_vus:
                continue
            deja_vus.add(paire)

            # Récupérer tous les composants entre ces deux nœuds
            composants_entre = list(graphe[noeud][voisin].values())
            refs_r = [d['ref'] for d in composants_entre if d['type'] == 'R']
            refs_c = [d['ref'] for d in composants_entre if d['type'] == 'C']

            if refs_r and refs_c:
                resultats.append({
                    'circuit_type': 'Absorbeur RC',
                    'components': refs_r + refs_c,
                    'nodes': list(paire),
                })

    return resultats


def detecter_fusible(graphe):
    """
    Protection par fusible : composant F seul dans le circuit.
    Se coupe en cas de surintensité pour protéger le reste du circuit.
    """
    resultats = []

    for u, v, data in graphe.edges(data=True):
        if data['type'] == 'F':
            resultats.append({
                'circuit_type': 'Protection par fusible',
                'components': [data['ref']],
                'nodes': [u, v],
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
    Liste de circuits détectés. Entièrement compatible avec list.
    Attributs supplémentaires :
        .supprimes : matches ignorés car leurs composants étaient déjà pris
        .ilots     : îlots fonctionnels (structure en étages du schéma)
    """
    def __init__(self, matches=None):
        super().__init__(matches or [])
        self.supprimes: list[dict] = []
        self.ilots: list[dict] = []


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
    'Condensateur de découplage':          'alimentation',
    'Filtre RC passe-bas':                 'filtrage',
    'Filtre RC passe-haut':                'filtrage',
    'Filtre LC':                           'filtrage',
    'Absorbeur RC':                        'protection',
    'Pont diviseur de tension':            'polarisation',
    'Protection par fusible':              'protection',
}


def _valeur(graphe, ref: str) -> str:
    """Retourne la valeur d'un composant (cherche dans le dict multi-broches et dans les arêtes)."""
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
    Ajoute confidence, confidence_level, reasons, warnings, functional_category
    et locked_components à un match de détection.

    Ne modifie pas le dict original (retourne une copie enrichie).
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

    elif ct == 'Condensateur de découplage':
        n0 = nodes[0] if len(nodes) > 0 else ''
        n1 = nodes[1] if len(nodes) > 1 else ''
        val = _valeur(graphe, comps[0]) if comps else ''
        vraiment_entre_rails = (
            (is_ground_net(n0) or is_power_net(n0)) and
            (is_ground_net(n1) or is_power_net(n1))
        )
        if vraiment_entre_rails:
            confidence = 0.90
            reasons.append("Condensateur directement entre alimentation et GND")
        else:
            confidence = 0.50
            warnings.append(
                "Condensateur entre nœuds non identifiés comme alimentation/GND — "
                "vérifier les alias de nets"
            )
        if val:
            v = parse_valeur(val)
            if v is not None and v > 1e-6:
                reasons.append(f"Valeur {val} — filtrage bulk (> 1µF), pas du découplage HF")
            elif v is not None:
                reasons.append(f"Valeur {val} — découplage HF typique")
        else:
            warnings.append("Valeur absente — type de découplage (HF vs bulk) non confirmé")

    elif ct in ('Filtre RC passe-bas', 'Filtre RC passe-haut'):
        r_ref = next((c for c in comps if c.upper().startswith('R')), None)
        c_ref = next((c for c in comps if c.upper().startswith('C')), None)
        r_val = _valeur(graphe, r_ref) if r_ref else ''
        c_val = _valeur(graphe, c_ref) if c_ref else ''
        direction = "série + condensateur vers GND" if 'bas' in ct else "en série + résistance vers GND"
        reasons.append(f"Résistance {direction}")
        if r_val and c_val:
            rv, cv = parse_valeur(r_val), parse_valeur(c_val)
            if rv is not None and cv is not None and rv > 0 and cv > 0:
                import math
                fc = 1.0 / (2.0 * math.pi * rv * cv)
                reasons.append(f"Fréquence de coupure ~ {fc:.1f} Hz (R={r_val}, C={c_val})")
                confidence = 0.90
                if rv == 0.0:
                    warnings.append(f"{r_ref} = 0Ω (jumper) — pas vraiment un filtre RC")
                    confidence = 0.30
            else:
                confidence = 0.70
                warnings.append("Valeurs invalides — fréquence de coupure non calculable")
        else:
            confidence = 0.65
            warnings.append("Valeurs absentes — fréquence de coupure non vérifiable")

    elif ct == 'Filtre LC':
        l_ref = next((c for c in comps if c.upper().startswith('L')), None)
        c_ref = next((c for c in comps if c.upper().startswith('C')), None)
        reasons.append("Inductance en série + condensateur vers GND")
        l_val = _valeur(graphe, l_ref) if l_ref else ''
        c_val = _valeur(graphe, c_ref) if c_ref else ''
        if l_val and c_val:
            lv, cv = parse_valeur(l_val), parse_valeur(c_val)
            if lv is not None and cv is not None and lv > 0 and cv > 0:
                import math
                f0 = 1.0 / (2.0 * math.pi * math.sqrt(lv * cv))
                reasons.append(f"Fréquence de résonance ~ {f0:.1f} Hz")
                confidence = 0.90
            else:
                confidence = 0.70
        else:
            confidence = 0.65
            warnings.append("Valeurs absentes — fréquence de résonance non vérifiable")

    elif ct == 'Absorbeur RC':
        reasons.append("Résistance et condensateur en parallèle entre les mêmes nœuds")
        warnings.append(
            "Topologie compatible avec un filtre ou une compensation de stabilité selon le contexte"
        )
        confidence = 0.70

    elif ct == 'Pont diviseur de tension':
        has_power = any(is_power_net(n) for n in nodes if n)
        has_gnd   = any(is_ground_net(n) for n in nodes if n)
        reasons.append("Deux résistances sur un nœud commun, chacune vers un point différent")
        if has_power and has_gnd:
            confidence = 0.90
            reasons.append("Entre alimentation et GND — pont de polarisation confirmé")
        else:
            confidence = 0.60
            warnings.append(
                "Nœuds d'alimentation et masse non clairement identifiés — "
                "peut être un pont résistif quelconque"
            )
        # Vérifier si une R est un jumper (0Ω)
        for ref in comps:
            val = _valeur(graphe, ref)
            if val and parse_valeur(val) == 0.0:
                warnings.append(
                    f"{ref} = 0Ω (jumper) — le rapport de division peut être court-circuité"
                )
                confidence = min(confidence, 0.50)

    elif ct == 'Protection par fusible':
        confidence = 0.95
        reasons.append("Composant de type F (fusible) en série dans le circuit")

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

# Détecteurs simples (circuits passifs — appelés EN DERNIER)
# Les patterns personnalisés (créés via l'interface) s'insèrent entre les deux.
_DETECTEURS_SIMPLES = [
    detecter_condensateur_decouplage,     # C direct alim/GND (avant filtres RC !)
    detecter_filtre_rc_passe_bas,
    detecter_filtre_rc_passe_haut,
    detecter_filtre_lc,
    detecter_absorbeur_rc,
    detecter_pont_diviseur,
    detecter_fusible,
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
    "Condensateur de découplage", "Filtre RC passe-bas", "Filtre RC passe-haut",
    "Filtre LC", "Absorbeur RC", "Pont diviseur de tension", "Protection par fusible",
]

# Alias pour compatibilité
match_patterns = None  # défini après analyser()


def analyser(graphe, patterns_personnalises=None):
    """
    Analyse le graphe et retourne tous les circuits détectés.

    Chaque composant ne peut appartenir qu'à UN SEUL circuit.
    Les circuits complexes sont prioritaires sur les circuits simples.

    Arguments :
        graphe               : le graphe NetworkX construit par graph_builder.py
        patterns_personnalises : liste optionnelle de fonctions de détection supplémentaires

    Retourne :
        liste de dicts {'circuit_type': str, 'components': list, 'nodes': list}
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
                def detecter(graphe):
                    for match in pattern.match(graphe):
                        yield {**match, 'circuit_type': pattern.name}
                return detecter
            patterns_personnalises = [_envelopper(p) for p in objets_custom]
        except Exception:
            patterns_personnalises = []

    # Ordre final : complexes → personnalisés → simples
    tous_les_detecteurs = _DETECTEURS_COMPLEXES + list(patterns_personnalises) + _DETECTEURS_SIMPLES

    composants_utilises: set = set()
    circuits_trouves: list  = []
    supprimes: list         = []

    for detecter in tous_les_detecteurs:
        for match in detecter(graphe):
            match_enrichi = _enrichir(match, graphe)
            if any(c in composants_utilises for c in match['components']):
                supprimes.append(match_enrichi)
                continue
            composants_utilises.update(match['components'])
            circuits_trouves.append(match_enrichi)

    # Passe satellite : absorbe les annexes mono-composant puis rattache
    # les composants restés non classifiés aux circuits détectés.
    rattacher_satellites(circuits_trouves, graphe, composants_utilises)

    resultats = ResultatsAnalyse(circuits_trouves)
    resultats.supprimes = supprimes
    # Structure en étages : îlots de connexité hors rails
    resultats.ilots = detecter_ilots(graphe, circuits_trouves)
    return resultats


# Alias anglais — pour que l'ancien code qui appelle match_patterns() continue à fonctionner
match_patterns = analyser
