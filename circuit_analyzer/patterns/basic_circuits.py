"""
@file basic_circuits.py
@brief Couche de compatibilité — enveloppe les détecteurs de circuits à diodes comme objets Pattern.

Toute la logique de détection se trouve dans circuit_analyzer/detecteur.py.
Ce fichier existe uniquement pour que les anciens tests et l'interface graphique
continuent de fonctionner sans modification.

Les circuits passifs nommés (filtre RC, pont diviseur, découplage, snubber, fusible)
n'existent plus : tout passif R/L/C est désormais réduit en « Impédance Z ». Seuls
les circuits à diodes conservent un Pattern dédié.
"""

from circuit_analyzer import detecteur
from circuit_analyzer.patterns.base import Pattern


class ESDProtectionDiode(Pattern):
    """@brief Pattern « Diode de protection ESD » (délègue à detecteur)."""
    name = "Diode de protection ESD"
    def match(self, graph): return detecteur.detecter_diode_protection_esd(graph)


class FlybackDiode(Pattern):
    """@brief Pattern « Diode de roue libre » (délègue à detecteur)."""
    name = "Diode de roue libre"
    def match(self, graph): return detecteur.detecter_diode_roue_libre(graph)


class BridgeRectifier(Pattern):
    """@brief Pattern « Pont redresseur (Graetz) » (délègue à detecteur)."""
    name = "Pont redresseur (Graetz)"
    def match(self, graph): return detecteur.detecter_pont_redresseur(graph)


class HalfWaveRectifier(Pattern):
    """@brief Pattern « Redresseur simple alternance » (délègue à detecteur)."""
    name = "Redresseur simple alternance"
    def match(self, graph): return detecteur.detecter_redresseur_simple(graph)


class PeakDetector(Pattern):
    """@brief Pattern « Détecteur de crête » (délègue à detecteur)."""
    name = "Détecteur de crête"
    def match(self, graph): return detecteur.detecter_detecteur_crete(graph)


## @brief Liste des patterns à diodes dans leur ordre de détection.
ALL_PATTERNS = [
    BridgeRectifier(),
    FlybackDiode(),
    ESDProtectionDiode(),
    HalfWaveRectifier(),
    PeakDetector(),
]
