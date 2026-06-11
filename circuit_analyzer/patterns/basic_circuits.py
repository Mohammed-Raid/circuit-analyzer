"""
Couche de compatibilité — enveloppe les fonctions de detecteur.py comme objets Pattern.

Toute la logique de détection se trouve dans circuit_analyzer/detecteur.py.
Ce fichier existe uniquement pour que les anciens tests et l'interface graphique
continuent de fonctionner sans modification.
"""

from circuit_analyzer.patterns.base import Pattern, is_gnd, is_power
from circuit_analyzer import detecteur


class ESDProtectionDiode(Pattern):
    name = "Diode de protection ESD"
    def match(self, graph): return detecteur.detecter_diode_protection_esd(graph)


class FlybackDiode(Pattern):
    name = "Diode de roue libre"
    def match(self, graph): return detecteur.detecter_diode_roue_libre(graph)


class RCLowPassFilter(Pattern):
    name = "Filtre RC passe-bas"
    def match(self, graph): return detecteur.detecter_filtre_rc_passe_bas(graph)


class RCHighPassFilter(Pattern):
    name = "Filtre RC passe-haut"
    def match(self, graph): return detecteur.detecter_filtre_rc_passe_haut(graph)


class LCFilter(Pattern):
    name = "Filtre LC"
    def match(self, graph): return detecteur.detecter_filtre_lc(graph)


class VoltageDivider(Pattern):
    name = "Pont diviseur de tension"
    def match(self, graph): return detecteur.detecter_pont_diviseur(graph)


class DecouplingCapacitor(Pattern):
    name = "Condensateur de découplage"
    def match(self, graph): return detecteur.detecter_condensateur_decouplage(graph)


class BridgeRectifier(Pattern):
    name = "Pont redresseur (Graetz)"
    def match(self, graph): return detecteur.detecter_pont_redresseur(graph)


class FuseProtection(Pattern):
    name = "Protection par fusible"
    def match(self, graph): return detecteur.detecter_fusible(graph)


class RCSnubber(Pattern):
    name = "Absorbeur RC"
    def match(self, graph): return detecteur.detecter_absorbeur_rc(graph)


class HalfWaveRectifier(Pattern):
    name = "Redresseur simple alternance"
    def match(self, graph): return detecteur.detecter_redresseur_simple(graph)


class PeakDetector(Pattern):
    name = "Détecteur de crête"
    def match(self, graph): return detecteur.detecter_detecteur_crete(graph)


# Liste dans le bon ordre (DecouplingCapacitor en premier — voir detecteur.py)
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
