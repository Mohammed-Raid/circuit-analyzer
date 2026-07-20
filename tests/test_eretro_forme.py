import xml.etree.ElementTree as ET
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
