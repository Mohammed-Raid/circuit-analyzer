"""@file test_reel_integration.py
@brief Corpus reel_* : identification + aliasing + non-régression détection."""
import glob
import os
import tempfile

import pytest

from circuit_analyzer import catalogue
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.detecteur import analyser
from circuit_analyzer.xml import generer_xml, lire_xml

FICHIERS = sorted(glob.glob("circuits_industriels/reel_*.xml"))


def test_round_trip_u_broches_numerotees():
    # Un U à broches NUMÉROTÉES doit round-tripper type/broches/connectivité
    # (forme d'écriture "Puce", plan identité ; lecture passthrough).
    comps = [
        Composant(ref="U1", type="U", value="NE555",
                  pins={"1": "GND", "2": "NT", "3": "NO", "8": "VCC"}),
        Composant(ref="R1", type="R", pins={"1": "VCC", "2": "NT"}, value="10k"),
    ]
    chemin = os.path.join(tempfile.gettempdir(), "rt_puce.xml")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(generer_xml(comps))
    relus = {c.ref: c for c in lire_xml(chemin)}
    u = relus["U1"]
    assert u.type == "U" and u.value == "NE555"
    # Convention app (identique aux vrais fichiers) : une broche physique non
    # câblée ressort sur son propre net singleton NET# — jamais de clé nommée
    # injectée (le setdefault IN+/IN-... est réservé aux formes à plan nommé).
    assert {"1", "2", "3", "8"} <= set(u.pins)
    assert all(k.isdigit() for k in u.pins), "aucun mix numerote/nomme"
    # connectivité : la broche 2 du U partage son net avec R1.2, les rails survivent
    assert u.pins["2"] == relus["R1"].pins["2"]
    assert u.pins["1"] == "GND" and u.pins["8"] == "VCC"
    # isolation : la broche 5 (en l'air) ne partage son net avec AUCUNE autre
    autres = [n for k, n in u.pins.items() if k != "5"] + list(relus["R1"].pins.values())
    assert u.pins["5"] not in autres


def test_corpus_present():
    assert len(FICHIERS) == 8


@pytest.mark.parametrize("fichier", FICHIERS)
def test_lecture_et_analyse_sans_exception(fichier):
    comps = lire_xml(fichier)
    res = analyser(construire_graphe(comps))
    assert res is not None


def test_741_du_corpus_detecte_inverseur():
    comps = lire_xml("circuits_industriels/reel_741_inverseur.xml")
    # l'aliasing a eu lieu DANS lire_xml :
    u = next(c for c in comps if c.type == "U")
    assert "IN-" in u.pins and "OUT" in u.pins
    res = analyser(construire_graphe(comps))
    assert any(m["circuit_type"] == "Amplificateur inverseur (AOP)" for m in res)


def test_555_du_corpus_identifie_et_pas_daop():
    comps = lire_xml("circuits_industriels/reel_555_astable.xml")
    u = next(c for c in comps if c.type == "U")
    assert catalogue.identifier(u.type, u.value)["categorie"] == "Timer"
    assert "2" in u.pins                      # multi-unité/non-alias : intact
    res = analyser(construire_graphe(comps))
    assert not any("(AOP)" in m["circuit_type"] for m in res)


@pytest.mark.parametrize("fichier", FICHIERS)
def test_aucun_faux_warning_broches_critiques(fichier):
    # Critical revue Task 4 : le check IN+/IN-/OUT tournait AVANT l'aliasing,
    # sur les cles NUMERIQUES des formes Puce -> "broches critiques non
    # connectees" a tort sur 7/8 fichiers. Le check ne s'applique qu'aux
    # formes a plan nomme (AOP historique).
    warnings = lire_xml(fichier).warnings
    assert not any("broches critiques" in w for w in warnings), warnings
