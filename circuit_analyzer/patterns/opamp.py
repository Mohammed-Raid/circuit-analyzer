"""
Couche de compatibilité — montages AOP.
Toute la logique est dans circuit_analyzer/detecteur.py.
"""

from circuit_analyzer.patterns.base import Pattern
from circuit_analyzer import detecteur


class InvertingAmplifier(Pattern):
    name = "Amplificateur inverseur (AOP)"
    def match(self, graph): return detecteur.detecter_amplificateur_inverseur(graph)


class NonInvertingAmplifier(Pattern):
    name = "Amplificateur non-inverseur (AOP)"
    def match(self, graph): return detecteur.detecter_amplificateur_non_inverseur(graph)


class VoltageFollower(Pattern):
    name = "Suiveur de tension (AOP)"
    def match(self, graph): return detecteur.detecter_suiveur_tension(graph)


class Integrator(Pattern):
    name = "Intégrateur (AOP)"
    def match(self, graph): return detecteur.detecter_integrateur(graph)


class Comparator(Pattern):
    name = "Comparateur (AOP)"
    def match(self, graph): return detecteur.detecter_comparateur(graph)


class Differentiator(Pattern):
    name = "Dérivateur (AOP)"
    def match(self, graph): return detecteur.detecter_derivateur(graph)


class SchmittTrigger(Pattern):
    name = "Bascule de Schmitt (AOP)"
    def match(self, graph): return detecteur.detecter_bascule_schmitt(graph)


class DifferentialAmplifier(Pattern):
    name = "Amplificateur différentiel (AOP)"
    def match(self, graph): return detecteur.detecter_amplificateur_differentiel(graph)


class SummingAmplifier(Pattern):
    name = "Amplificateur sommateur (AOP)"
    def match(self, graph): return detecteur.detecter_amplificateur_sommateur(graph)


OPAMP_PATTERNS = [
    DifferentialAmplifier(),
    SummingAmplifier(),
    Integrator(),
    Differentiator(),
    SchmittTrigger(),
    NonInvertingAmplifier(),
    InvertingAmplifier(),
    VoltageFollower(),
    Comparator(),
]
