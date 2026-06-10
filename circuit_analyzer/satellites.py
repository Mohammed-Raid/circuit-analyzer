"""
satellites.py — Rattachement des composants satellites aux circuits détectés.

Après la détection des 27 patterns, deux phases :
  Phase 1 : les circuits annexes mono-composant (roue libre, découplage, ESD)
            adjacents à un circuit multi-composants sont absorbés comme satellites.
  Phase 2 : les composants restés non classifiés sont examinés ; ceux qui touchent
            un circuit détecté reçoivent un rôle et un score de rattachement.

Chaque satellite porte un statut calculé une seule fois :
  score >= SEUIL_SUR                  -> status 'sure'     (verrouillé, exporté dans le bloc XML)
  SEUIL_POSSIBLE <= score < SEUIL_SUR -> status 'possible' (affiché à part, jamais exporté)

Format d'un satellite :
    {'ref': 'R2', 'role': 'pull-down', 'score': 0.9, 'status': 'sure',
     'reason': 'R 10k entre NET_BASE et GND'}
"""
from circuit_analyzer.patterns.base import (
    is_ground_net, is_power_net, is_protective_earth_net,
)
from circuit_analyzer.value_parser import (
    parse_valeur, classifier_resistance, classifier_condensateur,
)

SEUIL_SUR      = 0.6
SEUIL_POSSIBLE = 0.3


def _est_rail(net) -> bool:
    """Vrai si le net est une masse, une alimentation ou une terre de protection."""
    if not net:
        return False
    return is_ground_net(net) or is_power_net(net) or is_protective_earth_net(net)


def _noeuds_internes(match: dict) -> set:
    """Nœuds du circuit qui ne sont ni GND, ni alim, ni PE (= nœuds signal)."""
    return {n for n in match.get('nodes', []) if n and not _est_rail(n)}


def _rails_alim(match: dict) -> set:
    """Rails d'alimentation effectivement présents dans les nœuds du circuit."""
    return {n for n in match.get('nodes', []) if n and is_power_net(n)}
