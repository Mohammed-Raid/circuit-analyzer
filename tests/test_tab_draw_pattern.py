"""
@file test_tab_draw_pattern.py
@brief Valide le pont « éditeur → graphe → suggestion de conditions » utilisé par
       le bouton « Enregistrer comme pattern » (gui/tab_draw._save_as_pattern).

Teste le chemin de données réel (lire_netlist → construire_graphe →
suggest_conditions) sans ouvrir de fenêtre Tk, donc exécutable headless.
"""
import tempfile
import os

from circuit_analyzer.composant import lire_netlist, construire_graphe
from custom_circuits.loader import suggest_conditions


# Netlist au format SPICE, identique à ce que produit SchematicEditor.to_netlist :
# une résistance et un condensateur partageant un nœud signal (NET1), tous deux
# reliés à la masse.
_NETLIST = """\
* Schéma test — pont éditeur vers pattern

R1 NET1 GND 1k
C1 NET1 GND 100n
"""


def _ecrire_netlist(contenu: str) -> str:
    tmp = tempfile.NamedTemporaryFile(
        suffix=".sp", mode="w", encoding="utf-8", delete=False)
    tmp.write(contenu)
    tmp.close()
    return tmp.name


def test_pont_editeur_vers_suggestions():
    """Le graphe reconstruit depuis la netlist permet de détecter les conditions."""
    path = _ecrire_netlist(_NETLIST)
    try:
        composants = lire_netlist(path)
        graph = construire_graphe(composants)
    finally:
        os.unlink(path)

    refs = [c.ref for c in composants]
    assert set(refs) == {"R1", "C1"}

    suggestions = suggest_conditions(graph, refs)

    # Le condensateur touche la masse → condition détectée automatiquement.
    assert "C connecté à GND" in suggestions
    # R et C partagent NET1 (nœud signal) → condition topologique détectée.
    assert "R et C connectés au même nœud signal" in suggestions


def test_comp_info_construit_depuis_composants():
    """comp_info (ref → type/value/pins) tel que construit par _save_as_pattern."""
    path = _ecrire_netlist(_NETLIST)
    try:
        composants = lire_netlist(path)
    finally:
        os.unlink(path)

    comp_info = {
        c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
        for c in composants
    }
    assert comp_info["R1"]["type"] == "R"
    assert comp_info["C1"]["type"] == "C"
    # Chaque composant a bien des broches nommées (clé pin → net).
    assert comp_info["R1"]["pins"]
