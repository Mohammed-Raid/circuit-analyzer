"""
@file base.py
@brief Classification des nets (masse / alimentation / terre de protection) et
       classe de base des patterns personnalisés.

Les alias de nets sont chargés une fois à l'import depuis
config/net_aliases.json, puis figés : la classification d'un net est donc
mémoïsable (lru_cache), ce qui évite des milliers de reclassements sur une
grosse netlist.
"""
from abc import ABC, abstractmethod
from functools import lru_cache
import json
import re
from pathlib import Path
import networkx as nx


# =============================================================================
# CHARGEMENT DES ALIAS DE NETS
# =============================================================================

def _charger_alias() -> dict:
    """@brief Charge config/net_aliases.json depuis la racine du projet.

    @return dict Alias fusionnés avec les défauts ; les défauts seuls si le fichier est absent/illisible.
    """
    # VSS / V- / VEE sont volontairement dans "power" : ce sont des rails
    # d'alimentation NÉGATIFS, pas des masses. Le format BoardSCH distingue
    # lui-même typ 'G' (masse), 'V' (alim +) et 'N' (alim −) -> 'VSS', et la
    # bibliothèque ERetroDesign a GND et Vss en symboles SÉPARÉS.
    _defaut = {
        "ground": ["GND", "AGND", "DGND", "PGND", "0", "0V", "COM"],
        "power":  ["VCC", "VDD", "VIN", "VBAT", "VBUS", "VMOT", "+5V", "+3V3",
                   "AVCC", "AVDD", "DVCC", "PWR", "V+", "VREG", "VSUPPLY", "VPWR", "VSYS",
                   "VSS", "V-", "VEE", "VOUT"],
        "protective_earth": ["PE", "EARTH", "CHASSIS"]
    }
    # Racine de l'application : projet en mode normal, dossier de l'exe
    # une fois gelée par PyInstaller (fichier éditable par l'utilisateur).
    from circuit_analyzer.chemins import racine_application
    chemin = racine_application() / 'config' / 'net_aliases.json'
    if chemin.exists():
        try:
            with open(chemin, encoding='utf-8') as f:
                data = json.load(f)
            # Une catégorie PRÉSENTE dans le fichier REMPLACE le défaut ; une
            # catégorie absente garde le défaut. L'ancienne fusion était une
            # UNION : on pouvait ajouter un alias mais JAMAIS en retirer un,
            # sans le moindre message — un fichier utilisateur doit pouvoir
            # corriger la classification, pas seulement l'étendre.
            # (Les clés "_note*" sont des commentaires, pas des catégories.)
            return {**_defaut,
                    **{k: list(v) for k, v in data.items()
                       if not k.startswith('_') and isinstance(v, list)}}
        except Exception:
            pass
    return _defaut


_ALIASES = _charger_alias()

# Ensembles de noms en majuscules pour la comparaison rapide
_GND_EXACTS  = {a.upper() for a in _ALIASES.get('ground', [])}
_PWR_EXACTS  = {a.upper() for a in _ALIASES.get('power', [])}
_PE_EXACTS   = {a.upper() for a in _ALIASES.get('protective_earth', [])}


def _compiler_prefixes(exacts: set):
    """@brief Compile UNE regex pour les préfixes composés (GND_AOP, VDD1…) d'une catégorie.

    @param exacts Ensemble des noms exacts (en majuscules) de la catégorie.
    @return re.Pattern|None Regex de préfixe, ou None si aucun alias d'au moins 2 caractères.
    """
    alternatives = sorted(re.escape(a) for a in exacts if len(a) >= 2)
    if not alternatives:
        return None
    return re.compile(r'^(?:' + '|'.join(alternatives) + r')[\d_]')


_GND_PREFIXES = _compiler_prefixes(_GND_EXACTS)
_PWR_PREFIXES = _compiler_prefixes(_PWR_EXACTS)
_PE_PREFIXES  = _compiler_prefixes(_PE_EXACTS)


# =============================================================================
# HELPERS DE CLASSIFICATION DE NETS
# =============================================================================
# Les alias sont figés au chargement du module : la classification d'un net
# est donc mémoïsable (les détecteurs reclassent les mêmes nets des milliers
# de fois sur une grosse netlist).

@lru_cache(maxsize=None)
def is_ground_net(net: str) -> bool:
    """@brief Indique si le net est une masse (GND, AGND, 0V, VSS…).

    @param net Nom du net à classer.
    @return bool True si le net est une masse.
    """
    if not net:
        return False
    n = net.lstrip('/').upper().replace(' ', '')
    if n in _GND_EXACTS:
        return True
    # Préfixes composés : GND_AOP, PGND1, etc.
    return _GND_PREFIXES is not None and _GND_PREFIXES.match(n) is not None


@lru_cache(maxsize=None)
def is_power_net(net: str) -> bool:
    """@brief Indique si le net est un rail d'alimentation (VCC, VDD, +5V…).

    @param net Nom du net à classer.
    @return bool True si le net est une alimentation.
    """
    if not net:
        return False
    n = net.lstrip('/').upper().replace(' ', '')
    if n in _PWR_EXACTS:
        return True
    # Préfixes composés : VCC_AOP, VDD1, etc.
    return _PWR_PREFIXES is not None and _PWR_PREFIXES.match(n) is not None


@lru_cache(maxsize=None)
def is_protective_earth_net(net: str) -> bool:
    """@brief Indique si le net est une terre de protection (PE, EARTH, CHASSIS…).

    Ne doit PAS être traité comme GND dans les détecteurs de circuits.

    @param net Nom du net à classer.
    @return bool True si le net est une terre de protection.
    """
    if not net:
        return False
    n = net.lstrip('/').upper().replace(' ', '')
    if n in _PE_EXACTS:
        return True
    return _PE_PREFIXES is not None and _PE_PREFIXES.match(n) is not None


def classify_net(net: str) -> str:
    """@brief Classifie un net en une catégorie unique.

    @param net Nom du net à classer.
    @return str 'ground', 'power', 'pe' (terre de protection) ou 'signal'.
    """
    if is_ground_net(net):
        return 'ground'
    if is_power_net(net):
        return 'power'
    if is_protective_earth_net(net):
        return 'pe'
    return 'signal'


# Alias backward-compat (utilisés dans tout le reste du projet)
is_gnd   = is_ground_net
is_power = is_power_net


def nodes_aplatis(nodes) -> list:
    """@brief Liste plate de noms de nets depuis match['nodes'].

    Les familles historiques stockent 'nodes' en LISTE de noms de nets. Les
    portes CMOS (cf. circuit_analyzer.logique) le stockent en DICT
    ({'entrees': [...], 'sortie', 'vdd', 'gnd'}) -- itérer un dict directement
    (`for n in nodes`) parcourt ses CLÉS ('entrees', 'sortie'...), pas les noms
    de nets : un no-op silencieux pour tout consommateur générique (avertissement
    PE/CHASSIS, rattachement de satellites...). Cette fonction aplatit les deux
    formes en une liste homogène de noms de nets.

    @param nodes list[str] ou dict (forme porte CMOS), ou None.
    @return list[str] Noms de nets (valeurs de dict aplaties si besoin).
    """
    if isinstance(nodes, dict):
        plats = []
        for v in nodes.values():
            if isinstance(v, (list, tuple, set)):
                plats.extend(v)
            elif v:
                plats.append(v)
        return plats
    return list(nodes or [])


# =============================================================================
# CLASSE DE BASE POUR LES PATTERNS PERSONNALISÉS
# =============================================================================

class Pattern(ABC):
    """@brief Interface de base des patterns de circuits personnalisés."""

    @property
    @abstractmethod
    def name(self) -> str:
        """@brief Nom affiché du pattern.

        @return str Nom du circuit détecté.
        """
        pass

    @abstractmethod
    def match(self, graph: nx.MultiGraph) -> list[dict]:
        """
        @brief Recherche les occurrences du pattern dans le graphe.

        @param graph Le MultiGraph NetworkX du circuit.
        @return list[dict] Liste de matches, chacun de la forme
                {'components': [ref, ...], 'nodes': [net, ...]}.
        """
        pass
