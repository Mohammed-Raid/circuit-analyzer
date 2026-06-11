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
    """Charge config/net_aliases.json depuis la racine du projet. Retourne les défauts si absent."""
    _defaut = {
        "ground": ["GND", "AGND", "DGND", "PGND", "0", "0V", "COM", "VSS", "V-"],
        "power":  ["VCC", "VDD", "VIN", "VBAT", "VBUS", "VMOT", "+5V", "+3V3",
                   "AVCC", "AVDD", "DVCC", "PWR", "V+", "VREG", "VSUPPLY", "VPWR", "VSYS", "VOUT"],
        "protective_earth": ["PE", "EARTH", "CHASSIS"]
    }
    # Chercher depuis la racine du projet (2 niveaux au-dessus de patterns/)
    racine = Path(__file__).parent.parent.parent
    chemin = racine / 'config' / 'net_aliases.json'
    if not chemin.exists():
        chemin = Path('config') / 'net_aliases.json'
    if chemin.exists():
        try:
            with open(chemin, encoding='utf-8') as f:
                data = json.load(f)
            # Fusionner avec les défauts pour ne rien perdre
            merged = {k: list({*_defaut.get(k, []), *data.get(k, [])}) for k in set(_defaut) | set(data)}
            return merged
        except Exception:
            pass
    return _defaut


_ALIASES = _charger_alias()

# Ensembles de noms en majuscules pour la comparaison rapide
_GND_EXACTS  = {a.upper() for a in _ALIASES.get('ground', [])}
_PWR_EXACTS  = {a.upper() for a in _ALIASES.get('power', [])}
_PE_EXACTS   = {a.upper() for a in _ALIASES.get('protective_earth', [])}


def _compiler_prefixes(exacts: set):
    """Compile UNE regex pour les préfixes composés (GND_AOP, VDD1…) d'une catégorie."""
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
    """Retourne True si le net est une masse (GND, AGND, 0V, VSS…)."""
    if not net:
        return False
    n = net.lstrip('/').upper().replace(' ', '')
    if n in _GND_EXACTS:
        return True
    # Préfixes composés : GND_AOP, PGND1, etc.
    return _GND_PREFIXES is not None and _GND_PREFIXES.match(n) is not None


@lru_cache(maxsize=None)
def is_power_net(net: str) -> bool:
    """Retourne True si le net est un rail d'alimentation (VCC, VDD, +5V…)."""
    if not net:
        return False
    n = net.lstrip('/').upper().replace(' ', '')
    if n in _PWR_EXACTS:
        return True
    # Préfixes composés : VCC_AOP, VDD1, etc.
    return _PWR_PREFIXES is not None and _PWR_PREFIXES.match(n) is not None


@lru_cache(maxsize=None)
def is_protective_earth_net(net: str) -> bool:
    """Retourne True si le net est une terre de protection (PE, EARTH, CHASSIS…).
    Ne doit PAS être traité comme GND dans les détecteurs de circuits."""
    if not net:
        return False
    n = net.lstrip('/').upper().replace(' ', '')
    if n in _PE_EXACTS:
        return True
    return _PE_PREFIXES is not None and _PE_PREFIXES.match(n) is not None


def classify_net(net: str) -> str:
    """Classifie un net : 'ground', 'power', 'pe' (terre de protection) ou 'signal'."""
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


# =============================================================================
# CLASSE DE BASE POUR LES PATTERNS PERSONNALISÉS
# =============================================================================

class Pattern(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def match(self, graph: nx.MultiGraph) -> list[dict]:
        """
        Returns list of matches.
        Each match: {'components': [ref, ...], 'nodes': [net, ...]}
        """
        pass
