"""
@file matcher.py
@brief Shim de compatibilité — réexporte analyser() sous l'ancien nom match_patterns().
@see circuit_analyzer.detecteur
"""
from circuit_analyzer.detecteur import analyser as match_patterns
