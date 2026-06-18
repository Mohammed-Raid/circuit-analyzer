"""
@file __init__.py
@brief circuit_analyzer — Analyseur de circuits électroniques (package racine).

API principale :
    from circuit_analyzer.composant import lire_netlist, construire_graphe
    from circuit_analyzer.detecteur import analyser
    from circuit_analyzer.rapport   import generer_rapport
    from circuit_analyzer.xml       import lire_xml, generer_xml
"""

# Source unique de vérité pour la version de l'application : lue par le build
# (tools/build_exe.py) et l'interface (gui/app_window.py) pour éviter la dérive.
__version__ = "1.5.0"

