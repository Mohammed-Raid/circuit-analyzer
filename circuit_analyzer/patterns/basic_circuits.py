"""
@file basic_circuits.py
@brief Couche de compatibilité — enveloppe les détecteurs de circuits passifs/alim comme objets Pattern.

Toute la logique de détection se trouve dans circuit_analyzer/detecteur.py.
Ce fichier existe uniquement pour que les anciens tests et l'interface graphique
continuent de fonctionner sans modification.
"""

from circuit_analyzer.patterns.base import Pattern, is_gnd, is_power
from circuit_analyzer import detecteur


class ESDProtectionDiode(Pattern):
    """@brief Pattern « Diode de protection ESD » (délègue à detecteur)."""
    name = "Diode de protection ESD"
    def match(self, graph): return detecteur.detecter_diode_protection_esd(graph)


class FlybackDiode(Pattern):
    """@brief Pattern « Diode de roue libre » (délègue à detecteur)."""
    name = "Diode de roue libre"
    def match(self, graph): return detecteur.detecter_diode_roue_libre(graph)


class RCLowPassFilter(Pattern):
    """@brief Pattern « Filtre RC passe-bas » (délègue à detecteur)."""
    name = "Filtre RC passe-bas"
    def match(self, graph): return detecteur.detecter_filtre_rc_passe_bas(graph)


class RCHighPassFilter(Pattern):
    """@brief Pattern « Filtre RC passe-haut » (délègue à detecteur)."""
    name = "Filtre RC passe-haut"
    def match(self, graph): return detecteur.detecter_filtre_rc_passe_haut(graph)


class LCFilter(Pattern):
    """@brief Pattern « Filtre LC » (délègue à detecteur)."""
    name = "Filtre LC"
    def match(self, graph): return detecteur.detecter_filtre_lc(graph)


class VoltageDivider(Pattern):
    """@brief Pattern « Pont diviseur de tension » (délègue à detecteur)."""
    name = "Pont diviseur de tension"
    def match(self, graph): return detecteur.detecter_pont_diviseur(graph)


class DecouplingCapacitor(Pattern):
    """@brief Pattern « Condensateur de découplage » (délègue à detecteur)."""
    name = "Condensateur de découplage"
    def match(self, graph): return detecteur.detecter_condensateur_decouplage(graph)


class BridgeRectifier(Pattern):
    """@brief Pattern « Pont redresseur (Graetz) » (délègue à detecteur)."""
    name = "Pont redresseur (Graetz)"
    def match(self, graph): return detecteur.detecter_pont_redresseur(graph)


class FuseProtection(Pattern):
    """@brief Pattern « Protection par fusible » (délègue à detecteur)."""
    name = "Protection par fusible"
    def match(self, graph): return detecteur.detecter_fusible(graph)


class RCSnubber(Pattern):
    """@brief Pattern « Absorbeur RC » (délègue à detecteur)."""
    name = "Absorbeur RC"
    def match(self, graph): return detecteur.detecter_absorbeur_rc(graph)


class HalfWaveRectifier(Pattern):
    """@brief Pattern « Redresseur simple alternance » (délègue à detecteur)."""
    name = "Redresseur simple alternance"
    def match(self, graph): return detecteur.detecter_redresseur_simple(graph)


class PeakDetector(Pattern):
    """@brief Pattern « Détecteur de crête » (délègue à detecteur)."""
    name = "Détecteur de crête"
    def match(self, graph): return detecteur.detecter_detecteur_crete(graph)


## @brief Liste des patterns passifs dans le bon ordre (DecouplingCapacitor en premier — voir detecteur.py).
ALL_PATTERNS = [
    DecouplingCapacitor(),
    RCLowPassFilter(),
    RCHighPassFilter(),
    LCFilter(),
    RCSnubber(),
    VoltageDivider(),
    FuseProtection(),
    BridgeRectifier(),
    FlybackDiode(),
    ESDProtectionDiode(),
    HalfWaveRectifier(),
    PeakDetector(),
]
