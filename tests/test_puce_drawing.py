"""@file test_puce_drawing.py
@brief Boîte puce (elm.Ic) : ancres par fonction, nets, contrat puces bandeau,
jamais de grille générique pour un îlot à puce identifiée."""
import matplotlib
matplotlib.use("Agg")
import schemdraw

from circuit_analyzer import catalogue
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser
from circuit_analyzer.xml import lire_xml
import gui.circuit_viewer as cv
from gui import puce_schematic

CI_555 = {"U1": {"type": "U", "value": "NE555",
                 "pins": {"1": "GND", "2": "NTRIG", "3": "NOUT", "4": "VCC",
                          "5": "NCTRL", "6": "NTRIG", "7": "NDIS", "8": "VCC"}}}


def _dessiner(detaille=False):
    entree = catalogue.identifier("U", "NE555")
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = detaille
        res = puce_schematic.dessiner_puce(d, "U1", entree, CI_555)
    return d, res


def test_contrat_ancres_et_nets():
    d, res = _dessiner()
    for cle in ("in", "out", "title", "nets", "absorbed_refs"):
        assert cle in res
    # chaque net câblé de la puce a un point d'ancrage réel
    for net in ("NTRIG", "NOUT", "NDIS", "NCTRL", "GND", "VCC"):
        assert net in res["nets"], net
    assert "U1" in d._comp_positions          # puce bandeau cliquable


def test_puce_ilot_reconnait_le_555():
    comps = lire_xml("circuits_industriels/reel_555_astable.xml")
    g = construire_graphe(comps)
    res = analyser(g)
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    trouve = cv._puce_ilot(ilot, g)
    assert trouve is not None
    ref, entree = trouve
    assert ref == "U1" and entree["categorie"] == "Timer"


def test_puce_ilot_ignore_les_aop_et_inconnus():
    comps = lire_xml("circuits_industriels/reel_741_inverseur.xml")
    g = construire_graphe(comps)
    res = analyser(g)
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    assert cv._puce_ilot(ilot, g) is None     # aliasé AOP -> chemins AOP


def test_make_puce_fig_deux_vues_et_z_cliquables():
    comps = lire_xml("circuits_industriels/reel_555_astable.xml")
    g = construire_graphe(comps)
    res = analyser(g)
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
          for c in comps}
    ref, entree = cv._puce_ilot(ilot, g)
    matches = cv._matches_for_island(ilot, res)
    for detaille in (False, True):
        fig = cv._make_puce_fig(ref, entree, ci, matches, detaille=detaille)
        assert "U1" in fig._comp_positions, f"puce non cliquable ({detaille=})"
        txts = [t.get_text() for ax in fig.axes for t in ax.texts]
        assert any("TRIG" in t for t in txts), "broches étiquetées par fonction"
        assert any("NE555" in t or "Timer" in t for t in txts), "titre puce"


# ── Filtre broches câblées (revue contrôleur) ────────────────────────────
# Convention de lecture : toute broche NON câblée ressort avec son propre net
# singleton "NET<n>" (jamais partagé, jamais NC) -- fidèle aux fichiers
# réels. `_broche_cablee`/`_nets_partages` distinguent ce fantôme d'une
# broche réellement câblée (net partagé, ou net nommé hors convention NET#).

def test_broche_cablee_filtre_les_singletons_net_hash():
    from gui.puce_schematic import _broche_cablee, _nets_partages
    ci = {"U1": {"pins": {"1": "NET1", "2": "NET1", "3": "NET2", "4": "GND"}},
          "R1": {"pins": {"1": ""}}}
    partages = _nets_partages(ci)
    assert _broche_cablee("NET1", partages) is True     # NET# mais partagé -> câblée
    assert _broche_cablee("NET2", partages) is False    # NET# singleton -> fantôme
    assert _broche_cablee("GND", partages) is True       # rail nommé, même seul -> câblée
    assert _broche_cablee("", partages) is False
    assert _broche_cablee("NC", partages) is False


def test_74hc00_ne_dessine_que_les_broches_cablees():
    # 74HC00 : une seule porte câblée (1A/1B/1Y) + alimentations, les 9
    # autres broches logiques sont "en l'air" (nets NET# singleton du
    # fichier réel) -- elles ne doivent jamais apparaître comme ancres.
    ci = {
        "U1": {"type": "U", "value": "74HC00", "pins": {
            "1": "SIGA", "2": "SIGB", "3": "SIGY",
            "4": "NET1", "5": "NET2", "6": "NET3", "8": "NET4", "9": "NET5",
            "10": "NET6", "11": "NET7", "12": "NET8", "13": "NET9",
            "7": "GND", "14": "VCC"}},
        "R1": {"type": "R", "value": "1k", "pins": {"1": "SIGA", "2": "SIGB"}},
    }
    entree = catalogue.identifier("U", "74HC00")
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = False
        res = puce_schematic.dessiner_puce(d, "U1", entree, ci)
    assert set(res["nets"]) == {"SIGA", "SIGB", "SIGY", "GND", "VCC"}
