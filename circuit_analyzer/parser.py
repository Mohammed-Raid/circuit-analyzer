"""
@file parser.py
@brief Shim de compatibilité — réexporte Composant (Component), lire_netlist (parse_file)
       et charger_bibliotheque (load_library).
@see circuit_analyzer.composant
"""
from circuit_analyzer.composant import (
    Composant as Component, lire_netlist as parse_file,
    charger_bibliotheque as load_library,
)
