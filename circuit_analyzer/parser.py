"""
@file parser.py
@brief Shim de compatibilité — réexporte Composant (Component), lire_netlist (parse_file)
       et charger_bibliotheque (load_library).
@see circuit_analyzer.composant
"""
from circuit_analyzer.composant import (  # noqa: F401
    Composant as Component,
    lire_netlist as parse_file,
    lire_spice as parse_spice,
    lire_kicad_net as parse_kicad_net,
    charger_bibliotheque as load_library,
)
