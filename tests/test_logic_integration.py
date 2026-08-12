"""@file test_logic_integration.py
@brief Intégration des portes CMOS dans le pipeline complet (matcher,
anti-vol, anti-faux-positifs sur le corpus analogique existant)."""
import glob

import pytest

from circuit_analyzer import detecteur, logique
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.detecteur import analyser
from circuit_analyzer.xml import lire_xml


def _m(ref, g, d, s):
    return Composant(ref=ref, type="M", pins={"G": g, "D": d, "S": s}, value="")


def test_analyser_detecte_l_inverseur_en_priorite():
    graphe = construire_graphe([_m("M1", "A", "OUT", "VDD"),
                                _m("M2", "A", "OUT", "GND")])
    res = detecteur.analyser(graphe)
    types = [c["circuit_type"] for c in res]
    assert "Inverseur (CMOS)" in types
    # Anti-vol : les M de la porte ne sont pas repris par un détecteur MOSFET.
    assert "MOSFET en commutation" not in types


def test_noms_circuits_contiennent_les_portes():
    for nom in ("Inverseur (CMOS)", "Porte NAND (CMOS)", "Porte NOR (CMOS)"):
        assert nom in detecteur.NOMS_CIRCUITS


# LE filet anti-régression de la démo : le détecteur de portes ne matche
# RIEN sur tout le corpus analogique existant.
@pytest.mark.parametrize("fichier", sorted(
    glob.glob("circuits_industriels/ilot_*.xml")
    + glob.glob("circuits_industriels/tr_*.xml")
    + glob.glob("circuits_industriels/aop_*.xml")))
def test_zero_faux_positif_sur_corpus_analogique(fichier):
    graphe = construire_graphe(lire_xml(fichier))
    assert logique.detecter_portes_cmos(graphe) == []


@pytest.mark.parametrize("fichier", sorted(
    glob.glob("circuits_industriels/ilot_*.xml")
    + glob.glob("circuits_industriels/tr_*.xml")
    + glob.glob("circuits_industriels/aop_*.xml")))
def test_non_regression_types_detectes_corpus(fichier):
    # L'insertion en tête ne change la détection d'AUCUN fichier existant :
    # aucun type porte ne doit apparaître dans leurs résultats.
    res = detecteur.analyser(construire_graphe(lire_xml(fichier)))
    for c in res:
        assert "(CMOS)" not in c["circuit_type"]


# ── Détection sur le corpus logic_* (fichiers réels, round-trip XML) ─────────
#
# ATTENTION round-trip (vérifié à la main, cf. tools/gen_logic_corpus.py) :
# le format BoardSCH (generer_xml/lire_xml) n'a AUCUN champ pour stocker le
# nom d'un net SIGNAL — seuls les rails VDD/GND survivent verbatim (portés
# par un symbole dédié, cf. xml.py::nom_net). Les nets d'entrée/sortie
# "A", "B", "OUT", "N1"... sont donc renommés en NET1, NET2... par lire_xml,
# de façon DÉTERMINISTE (ordre d'insertion des composants/broches — la
# régénération du corpus produit des fichiers strictement identiques).
# Confirmé pré-existant et non spécifique à ce corpus : le même renommage
# s'observe sur circuits_industriels/tr_mosfet_commutation.xml (fixture
# antérieure, sans rapport avec cette tâche) — ce n'est donc pas un bug du
# générateur mais une propriété structurelle du format XML lui-même.
# Les valeurs ci-dessous sont les NET# réels observés après round-trip.
_ATTENDUS = [
    ("logic_cmos_not.xml", ["Inverseur (CMOS)"], [("NOT", ["NET1"])]),
    ("logic_cmos_nand2.xml", ["Porte NAND (CMOS)"], [("NAND", ["NET1", "NET3"])]),
    ("logic_cmos_nand3.xml", ["Porte NAND (CMOS)"], [("NAND", ["NET1", "NET3", "NET4"])]),
    ("logic_cmos_nor2.xml", ["Porte NOR (CMOS)"], [("NOR", ["NET1", "NET3"])]),
    ("logic_chaine_and.xml",
     ["Porte NAND (CMOS)", "Inverseur (CMOS)"],
     [("NAND", ["NET1", "NET3"]), ("NOT", ["NET2"])]),
    ("logic_dag_2vers1.xml",
     ["Inverseur (CMOS)", "Inverseur (CMOS)", "Porte NAND (CMOS)"],
     [("NOT", ["NET1"]), ("NOT", ["NET3"]), ("NAND", ["NET2", "NET4"])]),
    ("logic_latch_sr.xml",
     ["Porte NOR (CMOS)", "Porte NOR (CMOS)"],
     [("NOR", ["NET4", "NET5"]), ("NOR", ["NET1", "NET3"])]),
    ("logic_not_r_grille.xml", ["Inverseur (CMOS)"], [("NOT", ["NET1"])]),
    ("logic_suiveur_mos.xml", [], []),
    ("logic_non_dual.xml", [], []),
]


@pytest.mark.parametrize("fichier,types,fonctions", _ATTENDUS)
def test_detection_corpus_logic(fichier, types, fonctions):
    graphe = construire_graphe(lire_xml(f"circuits_industriels/{fichier}"))
    matches = logique.detecter_portes_cmos(graphe)
    assert sorted(m["circuit_type"] for m in matches) == sorted(types)
    assert sorted(m["fonction"] for m in matches) == sorted(fonctions)


# ── Routage io : chaîne et DAG de portes ─────────────────────────────────────

def _matches_fichier(fichier):
    res = analyser(construire_graphe(lire_xml(f"circuits_industriels/{fichier}")))
    return [c for c in res if "(CMOS)" in c["circuit_type"]], res


def test_io_montage_lit_le_champ_io_en_priorite():
    import gui.circuit_viewer as cv
    match = {"circuit_type": "Porte NAND (CMOS)",
             "io": {"ins": ["A", "B"], "out": "OUT"}, "nodes": {}}
    assert cv._io_montage(match, {}) == (["A", "B"], "OUT")


def test_chaine_nand_not_ordonnee():
    import gui.circuit_viewer as cv
    matches, _res = _matches_fichier("logic_chaine_and.xml")
    ordre = cv._ordonner_montages_flux(matches, {})
    assert ordre is not None
    assert [m["circuit_type"] for m in ordre] == \
        ["Porte NAND (CMOS)", "Inverseur (CMOS)"]


def test_dag_deux_not_vers_nand_en_couches():
    import gui.circuit_viewer as cv
    matches, _res = _matches_fichier("logic_dag_2vers1.xml")
    couches = cv._layers_montages_flux(matches, {})
    assert couches is not None
    assert [sorted(m["circuit_type"] for m in c) for c in couches] == \
        [["Inverseur (CMOS)", "Inverseur (CMOS)"], ["Porte NAND (CMOS)"]]


# ── Rapport et onglet (la forme nouvelle du match ne casse aucun consommateur) ─
#
# Point d'entree reellement appele par gui/tab_analyze.py (cf. _coeur_analyse) :
# `circuit_analyzer.rapport.generate(results, input_file, total_components,
# all_refs=...)`, alias anglais de `generer_rapport` -- pas la signature
# esquissee dans le brief.

@pytest.mark.parametrize("fichier", ["logic_cmos_nand2.xml", "logic_latch_sr.xml"])
def test_rapport_se_genere_avec_des_portes(fichier):
    from circuit_analyzer.rapport import generate
    comps = lire_xml(f"circuits_industriels/{fichier}")
    graphe = construire_graphe(comps)
    res = analyser(graphe)
    texte = generate(res, fichier, len(comps), all_refs=[c.ref for c in comps])
    assert "CMOS" in texte


def test_rapport_noeuds_montre_les_vrais_nets_pas_les_cles_du_dict():
    # Bug integration (revue finale) : match['nodes'] est un DICT pour les portes
    # CMOS ({entrees, sortie, vdd, gnd}). Itere directement, il rend ses CLES au
    # lieu des noms de nets -> "Noeuds : entrees -> sortie -> vdd -> gnd" (vue
    # generique interdite par le boss). nodes_aplatis doit rendre les vrais nets.
    from circuit_analyzer.rapport import generate
    comps = lire_xml("circuits_industriels/logic_cmos_nand2.xml")
    graphe = construire_graphe(comps)
    res = analyser(graphe)
    texte = generate(res, "logic_cmos_nand2.xml", len(comps),
                     all_refs=[c.ref for c in comps])
    ligne = next(l for l in texte.splitlines() if "Nœuds" in l)
    assert "entrees" not in ligne and "sortie" not in ligne, \
        f"le rapport affiche les cles du dict au lieu des nets : {ligne!r}"
    assert "VDD" in ligne and "GND" in ligne, f"nets manquants : {ligne!r}"
