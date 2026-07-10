"""
@file composant.py
@brief Tout ce qui concerne les composants électroniques.

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
    """@brief Chemin par défaut de component_library.json.

    À la racine de l'application (à côté de l'exe une fois gelée), pas au CWD.

    @return Path Chemin du fichier de bibliothèque de composants.
    """
    from circuit_analyzer.chemins import racine_application
    return racine_application() / 'component_library.json'


def charger_bibliotheque(chemin_json=None) -> dict:
    """
    @brief Charge la bibliothèque de composants.

    Commence par les types par défaut, puis applique les modifications du fichier JSON.

    @param chemin_json Chemin du JSON de personnalisation (défaut : chemin_bibliotheque()).
    @return dict Bibliothèque {type -> {'name', 'pins'}} fusionnée.
    """
    bibliotheque = copy.deepcopy(TYPES_COMPOSANTS)
    chemin = Path(chemin_json) if chemin_json is not None else chemin_bibliotheque()
    if chemin.exists():
        with open(chemin, encoding='utf-8') as f:
            personnalisations = json.load(f)
        bibliotheque.update(personnalisations)
    return bibliotheque


def get_pins(type_comp: str, chemin_json=None) -> list[str]:
    """@brief Retourne les noms de broches pour un type de composant donné.

    @param type_comp Type du composant (ex. 'R', 'U', 'Q').
    @param chemin_json Chemin du JSON de personnalisation (optionnel).
    @return list[str] Noms de broches ; ['1', '2'] par défaut si type inconnu.
    """
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
    @brief Représente un composant électronique avec ses connexions.

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
        """@brief Premier nœud du composant.
        @return str Net de la première broche, ou '' si aucune broche.
        """
        return list(self.pins.values())[0] if self.pins else ''

    @property
    def net2(self) -> str:
        """@brief Deuxième nœud du composant.
        @return str Net de la seconde broche, ou '' s'il y en a moins de deux.
        """
        vals = list(self.pins.values())
        return vals[1] if len(vals) > 1 else ''


# Alias anglais pour la compatibilité
Component = Composant


# =============================================================================
# 3. LECTURE DE LA NETLIST
# =============================================================================

def _trouver_type(ref: str, bibliotheque: dict) -> str:
    """
    @brief Devine le type d'un composant à partir de sa référence.

    Essaie les préfixes de 3 lettres, puis 2, puis 1.
    Exemple : 'SW1' → 'SW', 'R12' → 'R'

    @param ref Référence du composant (ex. 'R12', 'SW1').
    @param bibliotheque Bibliothèque des types reconnus.
    @return str Type deviné (préfixe connu), sinon la première lettre en majuscule.
    """
    for longueur in range(min(3, len(ref)), 0, -1):
        prefixe = ref[:longueur].upper()
        if prefixe in bibliotheque:
            return prefixe
    return ref[0].upper()


def _detect_format(chemin: str) -> str:
    """@brief Détecte le format d'un fichier netlist à partir de son contenu.

    @param chemin Chemin du fichier.
    @return str 'spice' | 'kicad' | 'texte'
    """
    try:
        with open(chemin, encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('*'):
                    return 'spice'
                if line.startswith('('):
                    return 'kicad'
                break
    except OSError:
        pass
    ext = Path(chemin).suffix.lower()
    if ext in ('.cir', '.sp'):
        return 'spice'
    return 'texte'


# Ordre des broches pour les netlists SPICE (différent de notre bibliothèque interne)
_SPICE_PINS: dict[str, list[str]] = {
    'Q': ['C', 'B', 'E'],      # SPICE BJT : collecteur base émetteur
    'M': ['D', 'G', 'S'],      # SPICE MOSFET : drain grille source (bulk ignoré)
    'D': ['A', 'K'],            # SPICE diode : anode cathode
    'U': ['IN+', 'IN-', 'OUT'], # op-amp simplifié
}

# Lettres à ignorer dans les netlists SPICE (sources, directives, couplages inductifs)
_SPICE_IGNORER = frozenset('VIFBEGHIJOPWYZ')


def lire_spice(chemin: str, bibliotheque: dict = None) -> list:
    """@brief Lit une netlist au format SPICE/LTspice.

    Accepte les fichiers .cir / .sp / .net commençant par une ligne '*'.
    Ordre des broches SPICE : Q → C B E, M → D G S, D → A K.

    @param chemin  Chemin du fichier SPICE.
    @param bibliotheque Bibliothèque (ignorée — SPICE a ses propres ordres de pins).
    @return list[Composant] Composants extraits.
    """
    composants = []
    refs_vus: set[str] = set()

    with open(chemin, encoding='utf-8', errors='replace') as f:
        for num, ligne_brute in enumerate(f, 1):
            ligne = ligne_brute.strip()
            # Commentaires et directives SPICE
            if not ligne or ligne.startswith('*') or ligne.startswith('.'):
                continue

            mots = ligne.split()
            ref = mots[0]
            if not ref or not ref[0].isalpha():
                continue

            type_comp = _trouver_type(ref, TYPES_COMPOSANTS)
            # Ignorer sources de tension/courant, éléments non supportés
            if type_comp in _SPICE_IGNORER:
                continue

            ref_maj = ref.upper()
            if ref_maj in refs_vus:
                continue  # doublons silencieux dans SPICE (sous-circuits, etc.)
            refs_vus.add(ref_maj)

            # Pins selon convention SPICE ou bibliothèque par défaut
            noms_broches = _SPICE_PINS.get(type_comp,
                           TYPES_COMPOSANTS.get(type_comp, {}).get('pins', ['1', '2']))
            nb = len(noms_broches)

            noeuds_bruts = mots[1:1 + nb]
            if len(noeuds_bruts) < nb:
                continue  # ligne incomplète → ignorer

            noeuds = [n.upper() for n in noeuds_bruts]
            # La valeur est le token après les noeuds, s'il n'est pas un noeud (commence par chiffre ou unité)
            valeur = ''
            if len(mots) > 1 + nb:
                candidate = mots[1 + nb]
                if candidate[0].isdigit() or candidate[0] in '+-':
                    valeur = candidate
                # sinon c'est un nom de modèle SPICE → on l'ignore comme valeur

            broches = dict(zip(noms_broches, noeuds))
            composants.append(Composant(ref=ref, type=type_comp, pins=broches, value=valeur))

    return composants


def lire_kicad_net(chemin: str, bibliotheque: dict = None) -> list:
    """@brief Lit une netlist KiCad au format S-expression (.net).

    Compatible avec KiCad 5 (net-list) et KiCad 6+ (export).
    Le nom des broches dans KiCad est mappé vers nos pins internes via la bibliothèque.

    @param chemin  Chemin du fichier .net KiCad.
    @param bibliotheque Bibliothèque des types (défaut : charger_bibliotheque()).
    @return list[Composant] Composants extraits.
    """
    import re

    if bibliotheque is None:
        bibliotheque = charger_bibliotheque()

    with open(chemin, encoding='utf-8', errors='replace') as f:
        content = f.read()

    # --- Étape 1 : extraire valeurs des composants {ref → value} ---
    comp_values: dict[str, str] = {}
    for m in re.finditer(
        r'\(comp\s+\(ref\s+"?([^"\s)]+)"?\).*?\(value\s+"?([^"\s)]+)"?\)',
        content, re.DOTALL | re.IGNORECASE
    ):
        comp_values[m.group(1)] = m.group(2)

    # --- Étape 2 : construire la map {(ref, pin) → net_name} ---
    pin_to_net: dict[tuple, str] = {}
    for block in _sexpr_blocks(content, 'net'):
        name_m = re.search(r'\(name\s+"?([^")\s]*)"?\)', block, re.IGNORECASE)
        if not name_m:
            continue
        raw_name = name_m.group(1).lstrip('/').strip() or 'NC'
        net_name = raw_name.upper()
        for node_m in re.finditer(
            r'\(node\s+\(ref\s+"?([^"\s)]+)"?\)\s*\(pin\s+"?([^"\s)]+)"?\)',
            block,
            re.IGNORECASE,
        ):
            pin_to_net[(node_m.group(1), node_m.group(2))] = net_name

    # --- Étape 3 : reconstruire les composants ---
    composants = []
    refs_vus: set[str] = set()

    # Regrouper les pins par ref
    ref_pins: dict[str, dict[str, str]] = {}
    for (ref, pin), net in pin_to_net.items():
        ref_pins.setdefault(ref, {})[pin] = net

    for ref, pin_map in ref_pins.items():
        ref_maj = ref.upper()
        if ref_maj in refs_vus:
            continue
        refs_vus.add(ref_maj)

        type_comp = _trouver_type(ref, bibliotheque)
        noms_internes = bibliotheque.get(type_comp, {}).get('pins', ['1', '2'])

        # Mapper les pins KiCad → nos noms internes (tentative directe d'abord)
        broches: dict[str, str] = {}
        for nom_interne in noms_internes:
            if nom_interne in pin_map:
                broches[nom_interne] = pin_map[nom_interne]
        # Pins non reconnues → ajout dans l'ordre de pin_map
        for kpin, net in pin_map.items():
            if kpin not in broches and len(broches) < len(noms_internes):
                nom = noms_internes[len(broches)]
                broches[nom] = net

        if not broches:
            continue

        valeur = comp_values.get(ref, '')
        composants.append(Composant(ref=ref, type=type_comp, pins=broches, value=valeur))

    return composants


def _sexpr_blocks(content: str, head: str) -> list[str]:
    """@brief Extrait les blocs S-expression complets dont la tête vaut `head`.

    @param content Contenu KiCad.
    @param head Nom de la forme recherchée, par exemple 'net'.
    @return list[str] Blocs parenthésés complets.
    """
    import re

    blocks = []
    starts = [m.start() for m in re.finditer(r'\(' + re.escape(head) + r'(?=\s|\))', content)]
    for start in starts:
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(content)):
            ch = content[idx]
            if in_string:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    blocks.append(content[start:idx + 1])
                    break
        else:
            return blocks
    return blocks


def lire_netlist(chemin: str, bibliotheque: dict = None) -> list:
    """@brief Lit un fichier netlist — détecte automatiquement le format.

    Formats supportés :
      - Texte tabulaire (notre format natif : REF  NET1  NET2  [VALEUR])
      - SPICE/LTspice (.cir, .sp, .net commençant par '*')
      - KiCad S-expression (.net commençant par '(')

    @param chemin Chemin du fichier netlist à lire.
    @param bibliotheque Bibliothèque des types (défaut : charger_bibliotheque()).
    @return list[Composant] Composants lus dans l'ordre du fichier.
    @throws ValueError Si le format texte contient des erreurs de syntaxe.
    """
    fmt = _detect_format(chemin)
    if fmt == 'spice':
        composants = lire_spice(chemin, bibliotheque)
    elif fmt == 'kicad':
        composants = lire_kicad_net(chemin, bibliotheque)
    else:
        composants = _lire_netlist_texte(chemin, bibliotheque)

    from circuit_analyzer.catalogue import appliquer_catalogue
    appliquer_catalogue(composants)

    return composants


def _lire_netlist_texte(chemin: str, bibliotheque: dict = None) -> list:
    """@brief Lit une netlist au format texte tabulaire natif.

    Format d'une ligne :
        REFERENCE  NOEUD1  NOEUD2  [VALEUR]

    @param chemin Chemin du fichier netlist à lire.
    @param bibliotheque Bibliothèque des types (défaut : charger_bibliotheque()).
    @return list[Composant] Composants lus dans l'ordre du fichier.
    @throws ValueError Si une référence est dupliquée, invalide, ou a trop peu de nœuds.
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
lire_spice = lire_spice  # déjà défini, alias pour export
parse_spice = lire_spice
parse_kicad_net = lire_kicad_net


# =============================================================================
# 4. CONSTRUCTION DU GRAPHE
# =============================================================================

def construire_graphe(composants: list[Composant]) -> nx.MultiGraph:
    """
    @brief Transforme la liste de composants en graphe NetworkX.

    - Chaque NŒUD du graphe = un nœud électrique (NET_IN, GND, VCC…)
    - Chaque ARÊTE          = un composant à 2 broches (R, C, L, D, F)
    - Les composants multi-broches (AOP, transistors) sont dans graphe.graph['components']
      car ils ne peuvent pas être représentés par une simple arête.

    @param composants Liste des composants à représenter.
    @return nx.MultiGraph Graphe (arêtes 2-broches + dict annexe 'components').
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
