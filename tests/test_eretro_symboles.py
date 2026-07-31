"""@file test_eretro_symboles.py
@brief Chargement de la bibliotheque VIVANTE d'ERetroDesign (LibItem/Lib).

Sa bibliotheque est un <DataItem> complet par composant depuis son
[MODIF 2026-07-24] (Form1.cs:6104). Ne pas confondre avec bin/Debug/Lib/,
fonds MORT dont les symboles font ~997x201 et n'ont ni Name ni typ.
"""
import os
import xml.etree.ElementTree as ET

import pytest

from circuit_analyzer import eretro_symboles

_DOSSIER_REEL = os.path.join("ERetroDesign", "ERetroDesign", "bin", "Debug",
                             "LibItem", "Lib")


def _symbole(tmp_path, nom, pins, typ="0", segments=1):
    """@brief Ecrit un symbole minimal au format LibItem/Lib."""
    dp = "".join(
        f"<DataPin><Pname>{n}</Pname><Pnumber>{n}</Pnumber>"
        f"<Pin><X>{x}</X><Y>{y}</Y></Pin></DataPin>"
        for n, (x, y) in pins.items())
    seg = "".join(
        "<DataSegment><Spoint><X>-10</X><Y>0</Y></Spoint>"
        "<Epoint><X>10</X><Y>0</Y></Epoint></DataSegment>"
        for _ in range(segments))
    chemin = os.path.join(str(tmp_path), nom + ".xml")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(f'<?xml version="1.0" encoding="utf-8"?>'
                f"<DataItem><Name>{nom}</Name>"
                f"<datapolygon /><datasegment>{seg}</datasegment><dataarc />"
                f"<datapin>{dp}</datapin><typ>{typ}</typ></DataItem>")
    return chemin


def test_un_symbole_donne_ses_broches_avec_leur_rang(tmp_path):
    """Le 3e membre du tuple est le RANG dans <datapin> : c'est lui que
    `_xml_composant` emet comme index de broche, et sur lequel les refs de
    connexion `cid_pidx_..._wid` sont construites."""
    _symbole(tmp_path, "Truc", {"2": (-80, 0), "1": (80, 0)})
    formes = eretro_symboles.charger(str(tmp_path))
    assert formes["Truc"]["pins"] == {"2": (-80, 0, 0), "1": (80, 0, 1)}


def test_la_geometrie_ressort_en_fragments_xml(tmp_path):
    """`_FORME` stocke polygon/segment/arc en CHAINE XML, prete a etre
    concatenee par `_xml_composant`. On rend donc la meme chose."""
    _symbole(tmp_path, "Truc", {"1": (0, 0)}, segments=2)
    f = eretro_symboles.charger(str(tmp_path))["Truc"]
    assert f["segment"].count("<DataSegment>") == 2
    assert f["polygon"] == "" and f["arc"] == ""
    ET.fromstring("<r>" + f["segment"] + "</r>")   # fragment bien forme


def test_le_typ_du_symbole_est_rendu(tmp_path):
    _symbole(tmp_path, "Truc", {"1": (0, 0)}, typ="76")
    assert eretro_symboles.charger(str(tmp_path))["Truc"]["typ"] == 76


def test_un_symbole_sans_broche_est_ecarte(tmp_path):
    """Un symbole sans broche ne se cable pas : le garder ferait disparaitre
    en silence toutes les liaisons du composant qui l'utiliserait."""
    _symbole(tmp_path, "Muet", {})
    assert "Muet" not in eretro_symboles.charger(str(tmp_path))


def test_un_symbole_corrompu_n_empeche_pas_les_autres(tmp_path):
    """Robustesse exigee par la spec : on lit le dossier d'un TIERS, qui
    bouge sans nous prevenir."""
    _symbole(tmp_path, "Bon", {"1": (0, 0)})
    with open(os.path.join(str(tmp_path), "Casse.xml"), "w", encoding="utf-8") as f:
        f.write("<DataItem><Name>Casse</Name><datapin>")   # jamais referme
    formes = eretro_symboles.charger(str(tmp_path))
    assert "Bon" in formes and "Casse" not in formes


def test_un_dossier_absent_ne_leve_pas(tmp_path):
    """La CI n'a pas son dossier, et le .exe livre non plus."""
    assert eretro_symboles.charger(os.path.join(str(tmp_path), "nexiste_pas")) == {}


def test_le_chemin_vient_de_la_variable_d_environnement(tmp_path, monkeypatch):
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    assert eretro_symboles.chemin_par_defaut() == str(tmp_path)


@pytest.mark.skipif(not os.path.isdir(_DOSSIER_REEL), reason="ERetroDesign absent")
def test_sa_vraie_bibliotheque_se_charge():
    """Garde-fou anti-test-creux : les tests ci-dessus tournent sur des
    symboles que NOUS fabriquons. Celui-ci lit les siens."""
    formes = eretro_symboles.charger(_DOSSIER_REEL)
    assert {"Résistance", "Capa", "AOP", "Diode", "GND", "Self", "2N2B"} <= set(formes)
    r = formes["Résistance"]
    assert set(r["pins"]) == {"1", "2"}
    assert r["pins"]["1"][:2] == (80, 0)
    assert r["pins"]["2"][:2] == (-80, 0)
    aop = formes["AOP"]
    assert set(aop["pins"]) == {"+", "-", "s"}, \
        "ses noms de broches sont ceux de nos plans _TYPE_VERS_FORME"


def test_ses_formes_ecrasent_les_notres_a_nom_egal(tmp_path, monkeypatch):
    """Decision du boss : SA geometrie fait foi sur les noms communs."""
    _symbole(tmp_path, "Résistance", {"1": (80, 0), "2": (-80, 0)}, segments=3)
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    import importlib

    from circuit_analyzer import xml as cx
    importlib.reload(cx)
    try:
        assert cx._FORME["Résistance"]["segment"].count("<DataSegment>") == 3
        assert cx._FORME_MAISON["Résistance"]["segment"].count("<DataSegment>") != 3
    finally:
        monkeypatch.delenv("ERETRO_LIB")
        importlib.reload(cx)


def test_nos_orphelines_survivent_a_la_fusion(tmp_path, monkeypatch):
    """Il n'a ni MOSFET ni Fusible ni PuceN : les ecraser par un dict vide
    supprimerait des formes dont l'export depend."""
    _symbole(tmp_path, "Résistance", {"1": (80, 0), "2": (-80, 0)})
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    import importlib

    from circuit_analyzer import xml as cx
    importlib.reload(cx)
    try:
        assert {"MOSFET", "Fusible", "Puce4", "Puce8"} <= set(cx._FORME)
    finally:
        monkeypatch.delenv("ERETRO_LIB")
        importlib.reload(cx)


def test_le_typ_reste_le_notre(tmp_path, monkeypatch):
    """MESURE : son GND.xml porte typ=0 alors que le notre vaut 71 ('G'),
    valeur dont `eretro.classer_rail` se sert pour reconnaitre une masse.
    Adopter son typ ferait perdre la classification des rails."""
    _symbole(tmp_path, "GND", {"1": (0, -47)}, typ="0")
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    import importlib

    from circuit_analyzer import xml as cx
    importlib.reload(cx)
    try:
        assert cx._TYP_COMPOSANT["GND"] == 71
    finally:
        monkeypatch.delenv("ERETRO_LIB")
        importlib.reload(cx)
