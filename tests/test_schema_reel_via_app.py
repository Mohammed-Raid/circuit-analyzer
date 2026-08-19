"""
@file test_schema_reel_via_app.py
@brief Reconnaissance sur un schéma sauvé par le VRAI chemin ERetroDesign
(Form1 par réflexion : InsertItem/AddDItem, CreateFlattenLinkWire,
SaveBoardToPath -- PAS generer_xml()).

[MODIF 2026-08-19] BUG TROUVÉ EN TESTANT : les 1890+ cas construits plus tôt
cette session passaient tous par `Composant` -> `generer_xml()`, qui écrit
TOUJOURS `Pnumber = Pname`. La vraie bibliothèque hand-authored (AOP.xml,
Transistor NPN.xml) porte Pname ET Pnumber renseignés avec des valeurs
DIFFÉRENTES ('+'/'-'/'s' vs '1'/'2'/'3' pour l'AOP) -- un cas structurellement
impossible à produire via le générateur Python. `lire_xml` préfère Pnumber
(vrai pour les passifs dont Pname est vide), donc les broches d'un AOP/
Transistor réel se retrouvaient nommées '1'/'2'/'3' au lieu de IN+/IN-/OUT ou
B/C/E -- invisible à toute la suite de tests jusqu'à ce qu'un schéma soit
réellement construit via le code app (voir docs de session, fork "Validate
schemas via real ERetroDesign GUI path"). Corrigé dans `_NOM_VERS_TYPE['AOP']`
(circuit_analyzer/xml.py) et `_PLAN_Q` (circuit_analyzer/eretro.py) : repli
numérique '1'/'2'/'3' ajouté, même remède déjà en place pour Diode/LED.

Ce fichier fixe cette régression : il lit un fixture réel (pas régénéré par
ce test) et vérifie noms de broches + reconnaissance, pour qu'un futur repli
de ce genre soit détecté immédiatement au lieu d'attendre un aller-retour
par l'app réelle.
"""
from pathlib import Path

import pytest

from circuit_analyzer.detecteur import analyser
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.xml import lire_xml

_DOSSIER = Path(__file__).resolve().parents[2] / "ERetroDesign" / "bin" / "Debug" / "schema_test"
_FICHIER = _DOSSIER / "harness_capteur_seuil_relais_led.xml"

pytestmark = pytest.mark.skipif(
    not _FICHIER.is_file(), reason="fixture réelle (harness ERetroDesign) absente")


def _lire():
    return lire_xml(str(_FICHIER))


def test_aop_reel_a_broches_nommees_pas_1_2_3():
    """L'AOP réel (Pname +/-/s ET Pnumber 1/2/3) doit résoudre IN+/IN-/OUT,
    pas retomber sur des clés numériques ni sur des 'NC' fantômes."""
    comps = _lire()
    aop = next(c for c in comps if c.type == "U")
    assert set(aop.pins) >= {"IN+", "IN-", "OUT"}
    assert aop.pins["IN+"] != "NC"
    assert aop.pins["IN-"] != "NC"
    assert aop.pins["OUT"] != "NC"
    # Les deux entrées ne doivent PAS partager le même net (ce qui produisait
    # le faux positif "Suiveur de tension" avant correction).
    assert aop.pins["IN-"] != aop.pins["OUT"]


def test_transistor_reel_a_broches_nommees_pas_1_2_3():
    """Le transistor réel (Pname B/C/E ET Pnumber 1/2/3) doit résoudre
    B/C/E, pas retomber sur des clés numériques."""
    comps = _lire()
    q = next(c for c in comps if c.type == "Q")
    assert set(q.pins) >= {"B", "C", "E"}


def test_aop_reel_reconnu_comparateur_pas_suiveur():
    """Bug réel corrigé : ce comparateur (diviseurs -> AOP en boucle ouverte)
    était mislabelisé "Suiveur de tension (AOP)" -- broches IN-/OUT toutes
    deux à 'NC' avant correction du repli Pnumber/Pname."""
    comps = _lire()
    graphe = build_graph(comps)
    resultats = list(analyser(graphe))
    types = {r.get("circuit_type") for r in resultats}
    assert "Comparateur (AOP)" in types
    assert "Suiveur de tension (AOP)" not in types


def test_transistor_reel_reconnu_amplificateur():
    """Le transistor du même schéma (base pilotée par R6 depuis l'AOP,
    collecteur -> R5 -> relais) doit être reconnu, pas perdu en 'X'."""
    comps = _lire()
    graphe = build_graph(comps)
    resultats = list(analyser(graphe))
    q_reconnu = [r for r in resultats if "Q1" in r.get("components", [])]
    assert q_reconnu, "Q1 absent de toute reconnaissance"
