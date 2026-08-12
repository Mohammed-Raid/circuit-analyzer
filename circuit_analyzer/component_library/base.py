"""
@file base.py
@brief Shim de compatibilité — réexporte TYPES_COMPOSANTS sous l'ancien nom COMPONENT_TYPES.
@see circuit_analyzer.composant
"""
from circuit_analyzer.composant import TYPES_COMPOSANTS as COMPONENT_TYPES  # noqa: F401
