"""
Couche de compatibilité — circuits à transistors.
Toute la logique est dans circuit_analyzer/detecteur.py.
"""

from circuit_analyzer.patterns.base import Pattern
from circuit_analyzer import detecteur


class TransistorSwitch(Pattern):
    name = "Transistor en commutation"
    def match(self, graph): return detecteur.detecter_transistor_commutation(graph)


class CommonEmitterAmp(Pattern):
    name = "Amplificateur émetteur commun"
    def match(self, graph): return detecteur.detecter_amplificateur_emetteur_commun(graph)


class CurrentMirror(Pattern):
    name = "Miroir de courant BJT"
    def match(self, graph): return detecteur.detecter_miroir_courant(graph)


class MosfetSwitch(Pattern):
    name = "MOSFET en commutation"
    def match(self, graph): return detecteur.detecter_mosfet_commutation(graph)


class HighSideMosfet(Pattern):
    name = "MOSFET haute-tension (côté haut)"
    def match(self, graph): return detecteur.detecter_mosfet_cote_haut(graph)


class RelayDriver(Pattern):
    name = "Commande de relais"
    def match(self, graph): return detecteur.detecter_commande_relais(graph)


TRANSISTOR_PATTERNS = [
    CurrentMirror(),
    RelayDriver(),
    CommonEmitterAmp(),
    TransistorSwitch(),
    MosfetSwitch(),
    HighSideMosfet(),
]
