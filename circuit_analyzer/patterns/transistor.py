"""
@file transistor.py
@brief Couche de compatibilité — circuits à transistors exposés comme objets Pattern.

Toute la logique de détection est dans circuit_analyzer/detecteur.py.
"""

from circuit_analyzer.patterns.base import Pattern
from circuit_analyzer import detecteur


class TransistorSwitch(Pattern):
    """@brief Pattern « Transistor en commutation » (délègue à detecteur)."""
    name = "Transistor en commutation"
    def match(self, graph): return detecteur.detecter_transistor_commutation(graph)


class CommonEmitterAmp(Pattern):
    """@brief Pattern « Amplificateur émetteur commun » (délègue à detecteur)."""
    name = "Amplificateur émetteur commun"
    def match(self, graph): return detecteur.detecter_amplificateur_emetteur_commun(graph)


class SuiveurEmetteur(Pattern):
    """@brief Pattern « Collecteur commun (suiveur d'émetteur) » (délègue à detecteur)."""
    name = "Collecteur commun (suiveur d'émetteur)"
    def match(self, graph): return detecteur.detecter_suiveur_emetteur(graph)


class PushPull(Pattern):
    """@brief Pattern « Étage push-pull » (délègue à detecteur)."""
    name = "Étage push-pull"
    def match(self, graph): return detecteur.detecter_push_pull(graph)


class Darlington(Pattern):
    """@brief Pattern « Paire Darlington » (délègue à detecteur)."""
    name = "Paire Darlington"
    def match(self, graph): return detecteur.detecter_darlington(graph)


class CurrentMirror(Pattern):
    """@brief Pattern « Miroir de courant BJT » (délègue à detecteur)."""
    name = "Miroir de courant BJT"
    def match(self, graph): return detecteur.detecter_miroir_courant(graph)


class MosfetSwitch(Pattern):
    """@brief Pattern « MOSFET en commutation » (délègue à detecteur)."""
    name = "MOSFET en commutation"
    def match(self, graph): return detecteur.detecter_mosfet_commutation(graph)


class HighSideMosfet(Pattern):
    """@brief Pattern « MOSFET haute-tension (côté haut) » (délègue à detecteur)."""
    name = "MOSFET haute-tension (côté haut)"
    def match(self, graph): return detecteur.detecter_mosfet_cote_haut(graph)


class RelayDriver(Pattern):
    """@brief Pattern « Commande de relais » (délègue à detecteur)."""
    name = "Commande de relais"
    def match(self, graph): return detecteur.detecter_commande_relais(graph)


## @brief Liste ordonnée des patterns à transistors (miroir/relais avant les commutations simples).
TRANSISTOR_PATTERNS = [
    PushPull(),
    Darlington(),
    CurrentMirror(),
    RelayDriver(),
    SuiveurEmetteur(),
    CommonEmitterAmp(),
    TransistorSwitch(),
    MosfetSwitch(),
    HighSideMosfet(),
]
