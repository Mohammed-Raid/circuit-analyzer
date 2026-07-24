import os
import glob
import xml.etree.ElementTree as ET
import pytest
from circuit_analyzer import eretro


def _item_geo(segments=(), nb_arcs=0, nb_pins=0):
    """Construit un <DataItem> minimal avec segments/arcs/broches."""
    it = ET.Element('DataItem')
    ds = ET.SubElement(it, 'datasegment')
    for (sx, sy, ex, ey) in segments:
        seg = ET.SubElement(ds, 'DataSegment')
        sp = ET.SubElement(seg, 'Spoint')
        ET.SubElement(sp, 'X').text = str(sx); ET.SubElement(sp, 'Y').text = str(sy)
        ep = ET.SubElement(seg, 'Epoint')
        ET.SubElement(ep, 'X').text = str(ex); ET.SubElement(ep, 'Y').text = str(ey)
    da = ET.SubElement(it, 'dataarc')
    for _ in range(nb_arcs):
        ET.SubElement(da, 'DataArc')
    dp = ET.SubElement(it, 'datapin')
    for _ in range(nb_pins):
        ET.SubElement(dp, 'DataPin')
    return it


def test_extraire_geometrie_compte_segments_arcs_broches():
    it = _item_geo(segments=[(0, 0, 10, 0), (10, 0, 10, 10)], nb_arcs=1, nb_pins=3)
    geo = eretro.extraire_geometrie(it)
    assert geo['segments'] == [(0.0, 0.0, 10.0, 0.0), (10.0, 0.0, 10.0, 10.0)]
    assert geo['nb_arcs'] == 1
    assert geo['nb_broches'] == 3


def test_extraire_geometrie_ignore_geometrie_interne_de_compose():
    # Un DataItem contenant un DItemL interne ne doit pas voir ses segments.
    it = _item_geo(segments=[(0, 0, 1, 1)], nb_pins=2)
    ditem_l = ET.SubElement(it, 'DItemL')
    interne = ET.SubElement(ditem_l, 'DataItem')
    ds = ET.SubElement(interne, 'datasegment')
    seg = ET.SubElement(ds, 'DataSegment')
    for tag, x, y in [('Spoint', 5, 5), ('Epoint', 9, 9)]:
        pt = ET.SubElement(seg, tag)
        ET.SubElement(pt, 'X').text = str(x); ET.SubElement(pt, 'Y').text = str(y)
    geo = eretro.extraire_geometrie(it)
    assert geo['segments'] == [(0.0, 0.0, 1.0, 1.0)]  # pas le (5,5,9,9) interne


# Géométries extraites des vrais symboles Lib/*.xml (vérité terrain).
_SEG_RESISTANCE = [(502, 500, 749, 500), (749, 500, 799, 402), (800, 401, 901, 596),
                   (903, 599, 997, 401), (999, 403, 1099, 601), (1101, 602, 1196, 402),
                   (1198, 401, 1249, 499), (1251, 499, 1499, 499)]
_SEG_CONDO = [(501, 399, 1097, 399), (501, 599, 1097, 598),
              (802, 396, 802, 198), (801, 598, 801, 798)]
_SEG_DIODE = [(600, 299, 600, 700), (1002, 500, 602, 299), (602, 701, 1003, 501),
              (1001, 198, 1001, 799), (299, 499, 600, 499), (1005, 499, 1302, 499)]
_SEG_GATE = [(900, 800, 900, 200), (900, 300, 1200, 300),
             (899, 700, 1200, 700), (400, 500, 600, 500)]
_SEG_NPN = [(800, 352, 800, 650), (803, 400, 1100, 200), (803, 600, 1101, 800),
            (500, 500, 800, 500), (901, 663, 1000, 600), (901, 667, 944, 786)]


def test_forme_resistance():
    geo = {'segments': _SEG_RESISTANCE, 'nb_arcs': 0, 'nb_broches': 2}
    assert eretro.classer_par_forme(geo) == ('R', None)


def test_forme_condensateur():
    geo = {'segments': _SEG_CONDO, 'nb_arcs': 0, 'nb_broches': 2}
    assert eretro.classer_par_forme(geo) == ('C', None)


def test_forme_diode():
    geo = {'segments': _SEG_DIODE, 'nb_arcs': 0, 'nb_broches': 2}
    assert eretro.classer_par_forme(geo) == ('D', eretro._PLAN_D)


def test_forme_porte_arc_trois_broches():
    geo = {'segments': _SEG_GATE, 'nb_arcs': 1, 'nb_broches': 3}
    assert eretro.classer_par_forme(geo) == ('U', {})


def test_forme_transistor_npn_sabstient():
    # 3 broches mais 0 arc : ne doit PAS être classé porte (collision évitée).
    geo = {'segments': _SEG_NPN, 'nb_arcs': 0, 'nb_broches': 3}
    assert eretro.classer_par_forme(geo) is None


def test_forme_ambigue_deux_broches_vide_sabstient():
    assert eretro.classer_par_forme({'segments': [], 'nb_arcs': 0, 'nb_broches': 2}) is None


# --- Oracle sur les vrais Lib (garde anti-contresens) ------------------------
# Le skipif est appliqué UNIQUEMENT aux tests de l'oracle (pas à tout le module :
# les unités de _forme_* ci-dessus doivent rester actives même sans le corpus).

# Corpus LOCALISE par sa presence, pas par un chemin en dur : le dossier de
# la solution C# a change de nom et de profondeur (2026-07-23).
_LIB = next((os.path.dirname(c) for c in
             glob.glob(os.path.join('**', 'Debug', 'Lib', 'CD4011.xml'),
                       recursive=True)), '')

_skip_sans_corpus = pytest.mark.skipif(not os.path.isdir(_LIB), reason="corpus Lib absent")


def _type_attendu(nom_fichier):
    """Vrai type d'un symbole d'après son nom de fichier (via le mapping existant)."""
    nom = os.path.splitext(os.path.basename(nom_fichier))[0]
    corr = eretro.mapper_nom(nom)
    return corr[0] if corr else None


@_skip_sans_corpus
@pytest.mark.parametrize('chemin', sorted(glob.glob(os.path.join(_LIB, '*.xml'))))
def test_oracle_lib_jamais_de_contresens(chemin):
    """Sur CHAQUE symbole Lib : classer_par_forme retourne son vrai type OU None,
    jamais un autre type. (S'abstenir = permis ; se tromper = interdit.)"""
    attendu = _type_attendu(chemin)
    if attendu is None:
        pytest.skip("type de référence inconnu pour ce symbole")
    it = ET.parse(chemin).getroot()
    obtenu = eretro.classer_par_forme(eretro.extraire_geometrie(it))
    if obtenu is not None:
        assert obtenu[0] == attendu, f"contresens {chemin}: {obtenu[0]} != {attendu}"


@_skip_sans_corpus
def test_oracle_lib_couvre_les_familles_ciblees():
    """Les symboles francs des familles v1 sont bien reconnus (pas seulement 'pas faux')."""
    attendus = {'resistance trad.xml': 'R', 'condo.xml': 'C',
                'DIODE.xml': 'D', 'Gate2.xml': 'U'}
    for fichier, typ in attendus.items():
        chemin = os.path.join(_LIB, fichier)
        if not os.path.exists(chemin):
            continue
        obtenu = eretro.classer_par_forme(eretro.extraire_geometrie(ET.parse(chemin).getroot()))
        assert obtenu is not None and obtenu[0] == typ, f"{fichier} → {obtenu}"
