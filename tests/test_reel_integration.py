"""@file test_reel_integration.py
@brief Corpus reel_* : identification + aliasing + non-régression détection."""
import os
import tempfile

from circuit_analyzer.composant import Composant
from circuit_analyzer.xml import generer_xml, lire_xml


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
