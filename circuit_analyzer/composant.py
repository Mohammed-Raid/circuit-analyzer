"""
composant.py — Tout ce qui concerne les composants électroniques.

Ce fichier regroupe :
  1. La classe Composant (description d'un composant)
  2. lire_netlist()     — lit un fichier texte et retourne la liste des composants
  3. construire_graphe() — transforme la liste en graphe NetworkX
  4. TYPES_COMPOSANTS   — dictionnaire des types reconnus (R, C, L, D, Q…)
  5. charger_bibliotheque() — charge la bibliothèque (defaut + personnalisations)
"""

import copy
import json
import networkx as nx
from dataclasses import dataclass
from pathlib import Path


# =============================================================================
# 1. TYPES DE COMPOSANTS RECONNUS
# =============================================================================

TYPES_COMPOSANTS = {
    'R':  {'name': 'Résistance',      'pins': ['1', '2']},
    'C':  {'name': 'Condensateur',    'pins': ['1', '2']},
    'L':  {'name': 'Inductance',      'pins': ['1', '2']},
    'D':  {'name': 'Diode',           'pins': ['A', 'K']},
    'F':  {'name': 'Fusible',         'pins': ['1', '2']},
    'Q':  {'name': 'Transistor BJT',  'pins': ['B', 'C', 'E']},
    'M':  {'name': 'MOSFET',          'pins': ['G', 'D', 'S']},
    'U':  {'name': 'Circuit intégré', 'pins': ['IN+', 'IN-', 'OUT', 'V+', 'V-']},
    'T':  {'name': 'Transformateur',  'pins': ['P1', 'P2', 'S1', 'S2']},
    'K':  {'name': 'Relais',          'pins': ['A1', 'A2', '11', '12', '14']},
    'SW': {'name': 'Interrupteur',    'pins': ['1', '2']},
}

# Alias anglais pour la compatibilité
COMPONENT_TYPES = TYPES_COMPOSANTS


def chemin_bibliotheque() -> Path:
    """Chemin par défaut de component_library.json : à la racine de
    l'application (à côté de l'exe une fois gelée), pas au CWD."""
    from circuit_analyzer.chemins import racine_application
    return racine_application() / 'component_library.json'


def charger_bibliotheque(chemin_json=None) -> dict:
    """
    Charge la bibliothèque de composants.
    Commence par les types par défaut, puis applique les modifications du fichier JSON.
    """
    bibliotheque = copy.deepcopy(TYPES_COMPOSANTS)
    chemin = Path(chemin_json) if chemin_json is not None else chemin_bibliotheque()
    if chemin.exists():
        with open(chemin, encoding='utf-8') as f:
            personnalisations = json.load(f)
        bibliotheque.update(personnalisations)
    return bibliotheque


def get_pins(type_comp: str, chemin_json=None) -> list[str]:
    """Retourne les noms de broches pour un type de composant donné."""
    bib = charger_bibliotheque(chemin_json)
    entree = bib.get(type_comp)
    return entree.get('pins', ['1', '2']) if entree else ['1', '2']


# Alias anglais
load_library = charger_bibliotheque


# =============================================================================
# 2. CLASSE COMPOSANT
# =============================================================================

@dataclass
class Composant:
    """
    Représente un composant électronique avec ses connexions.

    Attributs :
        ref  : référence unique (ex: 'R1', 'C2', 'U1')
        type : type du composant ('R', 'C', 'L', 'D', 'Q', 'M', 'U', 'F', 'K')
        pins : dictionnaire {nom_broche → nœud_électrique}
               ex: {'1': 'NET_IN', '2': 'GND'}
        value: valeur optionnelle (ex: '10k', '100nF')
    """
    ref:   str
    type:  str
    pins:  dict[str, str]
    value: str = ''

    @property
    def net1(self) -> str:
        """Premier nœud du composant."""
        return list(self.pins.values())[0] if self.pins else ''

    @property
    def net2(self) -> str:
        """Deuxième nœud du composant."""
        vals = list(self.pins.values())
        return vals[1] if len(vals) > 1 else ''


# Alias anglais pour la compatibilité
Component = Composant


# =============================================================================
# 3. LECTURE DE LA NETLIST
# =============================================================================

def _trouver_type(ref: str, bibliotheque: dict) -> str:
    """
    Devine le type d'un composant à partir de sa référence.
    Essaie les préfixes de 3 lettres, puis 2, puis 1.
    Exemple : 'SW1' → 'SW', 'R12' → 'R'
    """
    for longueur in range(min(3, len(ref)), 0, -1):
        prefixe = ref[:longueur].upper()
        if prefixe in bibliotheque:
            return prefixe
    return ref[0].upper()


def lire_netlist(chemin: str, bibliotheque: dict = None) -> list[Composant]:
    """
    Lit un fichier netlist et retourne la liste des composants.

    Format d'une ligne :
        REFERENCE  NOEUD1  NOEUD2  [VALEUR]

    Lève ValueError si :
        - Une référence est dupliquée
        - Un composant a trop peu de nœuds
        - Une ligne a un format invalide
    """
    if bibliotheque is None:
        bibliotheque = charger_bibliotheque()

    composants = []
    refs_vus = set()

    with open(chemin, encoding='utf-8') as f:
        for num_ligne, ligne_brute in enumerate(f, 1):
            ligne = ligne_brute.strip()
            if not ligne or ligne.startswith('#'):
                continue

            mots = ligne.split()
            ref = mots[0]

            if not ref[0].isalpha():
                raise ValueError(
                    f"Référence invalide '{ref}' (doit commencer par une lettre) "
                    f"— ligne {num_ligne}: {repr(ligne)}"
                )

            ref_maj = ref.upper()
            if ref_maj in refs_vus:
                raise ValueError(
                    f"Référence dupliquée '{ref}' — ligne {num_ligne}: {repr(ligne)}"
                )
            refs_vus.add(ref_maj)

            type_comp   = _trouver_type(ref, bibliotheque)
            noms_broches = bibliotheque.get(type_comp, {}).get('pins', ['1', '2'])
            nb_broches  = len(noms_broches)

            noeuds_bruts = mots[1:1 + nb_broches]
            if len(noeuds_bruts) < nb_broches:
                raise ValueError(
                    f"Composant '{ref}' ({type_comp}) attend {nb_broches} nœud(s) "
                    f"mais {len(noeuds_bruts)} trouvé(s) — ligne {num_ligne}: {repr(ligne)}"
                )

            noeuds = [n.upper().replace(' ', '') for n in noeuds_bruts]
            valeur = mots[1 + nb_broches] if len(mots) > 1 + nb_broches else ''
            broches = dict(zip(noms_broches, noeuds))
            composants.append(Composant(ref=ref, type=type_comp, pins=broches, value=valeur))

    return composants


# Alias anglais
parse_file = lire_netlist


# =============================================================================
# 4. CONSTRUCTION DU GRAPHE
# =============================================================================

def construire_graphe(composants: list[Composant]) -> nx.MultiGraph:
    """
    Transforme la liste de composants en graphe NetworkX.

    - Chaque NŒUD du graphe = un nœud électrique (NET_IN, GND, VCC…)
    - Chaque ARÊTE          = un composant à 2 broches (R, C, L, D, F)
    - Les composants multi-broches (AOP, transistors) sont dans graphe.graph['components']
      car ils ne peuvent pas être représentés par une simple arête.
    """
    graphe = nx.MultiGraph()
    graphe.graph['components'] = {c.ref: c for c in composants}

    for comp in composants:
        if len(comp.pins) == 2:
            noeud1, noeud2 = list(comp.pins.values())
            graphe.add_edge(noeud1, noeud2, ref=comp.ref, type=comp.type, value=comp.value)
        else:
            for noeud in comp.pins.values():
                graphe.add_node(noeud)

    return graphe


# Alias anglais
build_graph = construire_graphe
