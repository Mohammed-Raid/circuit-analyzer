from abc import ABC, abstractmethod
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


# =============================================================================
# HELPERS DE CLASSIFICATION DE NETS
# =============================================================================

def is_ground_net(net: str) -> bool:
    """Retourne True si le net est une masse (GND, AGND, 0V, VSS…)."""
    if not net:
        return False
    n = net.lstrip('/').upper().replace(' ', '')
    if n in _GND_EXACTS:
        return True
    # Préfixes composés : GND_AOP, PGND1, etc.
    for alias in _GND_EXACTS:
        if len(alias) >= 2 and re.match(r'^' + re.escape(alias) + r'[\d_]', n):
            return True
    return False


def is_power_net(net: str) -> bool:
    """Retourne True si le net est un rail d'alimentation (VCC, VDD, +5V…)."""
    if not net:
        return False
    n = net.lstrip('/').upper().replace(' ', '')
    if n in _PWR_EXACTS:
        return True
    # Préfixes composés : VCC_AOP, VDD1, etc.
    for alias in _PWR_EXACTS:
        if len(alias) >= 2 and re.match(r'^' + re.escape(alias) + r'[\d_]', n):
            return True
    return False


def is_protective_earth_net(net: str) -> bool:
    """Retourne True si le net est une terre de protection (PE, EARTH, CHASSIS…).
    Ne doit PAS être traité comme GND dans les détecteurs de circuits."""
    if not net:
        return False
    n = net.lstrip('/').upper().replace(' ', '')
    if n in _PE_EXACTS:
        return True
    for alias in _PE_EXACTS:
        if len(alias) >= 2 and re.match(r'^' + re.escape(alias) + r'[\d_]', n):
            return True
    return False


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
