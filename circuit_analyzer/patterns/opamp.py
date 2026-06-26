"""
@file opamp.py
@brief Couche de compatibilité — montages AOP exposés comme objets Pattern.

Toute la logique de détection est dans circuit_analyzer/detecteur.py.
"""

from circuit_analyzer.patterns.base import Pattern
from circuit_analyzer import detecteur


class InvertingAmplifier(Pattern):
    """@brief Pattern « Amplificateur inverseur (AOP) » (délègue à detecteur)."""
    name = "Amplificateur inverseur (AOP)"
    def match(self, graph): return detecteur.detecter_amplificateur_inverseur(graph)


class PartialDifferentiator(Pattern):
    """@brief Pattern « Ampli inverseur + boost HF (AOP) » (délègue à detecteur)."""
    name = "Ampli inverseur + boost HF (AOP)"
    def match(self, graph): return detecteur.detecter_derivateur_partiel(graph)


class PIController(Pattern):
    """@brief Pattern « Ampli inverseur + action intégrale (AOP) » (délègue à detecteur)."""
    name = "Ampli inverseur + action intégrale (AOP)"
    def match(self, graph): return detecteur.detecter_correcteur_pi(graph)


class NonInvertingAmplifier(Pattern):
    """@brief Pattern « Amplificateur non-inverseur (AOP) » (délègue à detecteur)."""
    name = "Amplificateur non-inverseur (AOP)"
    def match(self, graph): return detecteur.detecter_amplificateur_non_inverseur(graph)


class VoltageFollower(Pattern):
    """@brief Pattern « Suiveur de tension (AOP) » (délègue à detecteur)."""
    name = "Suiveur de tension (AOP)"
    def match(self, graph): return detecteur.detecter_suiveur_tension(graph)


class Integrator(Pattern):
    """@brief Pattern « Intégrateur (AOP) » (délègue à detecteur)."""
    name = "Intégrateur (AOP)"
    def match(self, graph): return detecteur.detecter_integrateur(graph)


class Comparator(Pattern):
    """@brief Pattern « Comparateur (AOP) » (délègue à detecteur)."""
    name = "Comparateur (AOP)"
    def match(self, graph): return detecteur.detecter_comparateur(graph)


class Differentiator(Pattern):
    """@brief Pattern « Dérivateur (AOP) » (délègue à detecteur)."""
    name = "Dérivateur (AOP)"
    def match(self, graph): return detecteur.detecter_derivateur(graph)


class SchmittTrigger(Pattern):
    """@brief Pattern « Bascule de Schmitt (AOP) » (délègue à detecteur)."""
    name = "Bascule de Schmitt (AOP)"
    def match(self, graph): return detecteur.detecter_bascule_schmitt(graph)


class DifferentialAmplifier(Pattern):
    """@brief Pattern « Amplificateur différentiel (AOP) » (délègue à detecteur)."""
    name = "Amplificateur différentiel (AOP)"
    def match(self, graph): return detecteur.detecter_amplificateur_differentiel(graph)


class SummingAmplifier(Pattern):
    """@brief Pattern « Amplificateur sommateur (AOP) » (délègue à detecteur)."""
    name = "Amplificateur sommateur (AOP)"
    def match(self, graph): return detecteur.detecter_amplificateur_sommateur(graph)


## @brief Liste ordonnée des patterns AOP (Comparateur en dernier — pattern par élimination).
OPAMP_PATTERNS = [
    DifferentialAmplifier(),
    SummingAmplifier(),
    Integrator(),
    Differentiator(),
    SchmittTrigger(),
    NonInvertingAmplifier(),
    PartialDifferentiator(),
    PIController(),
    InvertingAmplifier(),
    VoltageFollower(),
    Comparator(),
]
