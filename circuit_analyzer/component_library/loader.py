"""
@file loader.py
@brief Shim de compatibilité — réexporte charger_bibliotheque (load_library) et get_pins.
@see circuit_analyzer.composant
"""
from circuit_analyzer.composant import charger_bibliotheque as load_library, get_pins  # noqa: F401
