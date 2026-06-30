"""
@file test_conditions_display.py
@brief Couche d'affichage des conditions : libellés clairs, regroupement, et
       rétro-compatibilité du doublon retiré.
"""
from custom_circuits.loader import (
    CONDITION_LABELS, CONDITION_DISPLAY, CONDITION_GROUPS,
    condition_display, CustomCircuitPattern,
)
from circuit_analyzer.composant import Composant, construire_graphe


def test_display_couvre_toutes_les_conditions():
    """Chaque clé stable a un libellé clair."""
    manquants = [k for k in CONDITION_LABELS if k not in CONDITION_DISPLAY]
    assert manquants == [], f"Sans libellé clair : {manquants}"


def test_groupes_couvrent_exactement_les_conditions():
    """Les 3 familles couvrent toutes les conditions, sans doublon."""
    dans_groupes = [cle for _titre, cles in CONDITION_GROUPS for cle in cles]
    assert sorted(dans_groupes) == sorted(CONDITION_LABELS)
    assert len(dans_groupes) == len(set(dans_groupes))


def test_condition_display_fallback():
    """Une clé inconnue retombe sur elle-même (jamais de libellé vide)."""
    assert condition_display("clé inexistante") == "clé inexistante"
    assert condition_display("Feedback OUT→IN-").startswith("Contre-réaction")


def test_doublon_retire_mais_alias_toujours_actif():
    """« Transistor émetteur à GND » n'est plus proposé mais matche encore
    (patterns déjà enregistrés)."""
    assert "Transistor émetteur à GND" not in CONDITION_LABELS

    q = Composant("Q1", "Q", {"B": "NB", "C": "NC", "E": "GND"})
    graph = construire_graphe([q])
    pattern = CustomCircuitPattern({
        "name": "ancien",
        "components": ["Q"],
        "conditions": ["Transistor émetteur à GND"],
    })
    assert pattern.match(graph), "l'alias doit rester reconnu"
