"""
@file graph_builder.py
@brief Shim de compatibilité — réexporte construire_graphe() sous l'ancien nom build_graph().
@see circuit_analyzer.composant
"""
from circuit_analyzer.composant import construire_graphe as build_graph  # noqa: F401
