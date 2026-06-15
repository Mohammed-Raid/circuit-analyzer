"""
@file xml_parser.py
@brief Shim de compatibilité — réexporte lire_xml() sous l'ancien nom parse_xml().
@see circuit_analyzer.xml
"""
from circuit_analyzer.xml import lire_xml as parse_xml
