"""@file test_eretro_lib.py
@brief Partage de composants avec la bibliotheque ERetroDesign (aller-retour).

On ne peut pas valider le RENDU dans l'app C# du collegue depuis ici ; on
verrouille en revanche l'aller-retour par notre propre lecteur : un composant
exporte puis relu redonne le meme brochage et la meme boite.
"""
import xml.etree.ElementTree as ET

import pytest

from circuit_analyzer.eretro_lib import (
    composant_vers_symbole_xml, composants_depuis_xml, symbole_vers_composant)


def test_export_est_un_dataitem_importable():
    """Racine = <DataItem> NU. `ImportComponent` (bouton « Importer composant »)
    aiguille sur le NOM DE LA RACINE : ArrayOfDataItem / ArrayOfCComp / CComp,
    et TOUT LE RESTE part en `LoadOneItemQuiet` (deserialisation DataItem) — un
    <LibraryBundle> y echoue donc. Un DataItem nu passe AUSSI par « Importer
    bibliotheque » (branche root == "DataItem"), d'ou ce choix : un seul
    fichier pour les deux boutons."""
    entree = {"name": "Mon IC", "pins": ["1", "2"],
              "brochage": {"1": ["L", -20], "2": ["R", 20]},
              "boite": {"w": 80, "h": 60}, "default_value": "LM358"}
    xml = composant_vers_symbole_xml("IC", entree)
    r = ET.fromstring(xml)                       # bien forme
    assert r.tag == "DataItem"                   # racine attendue par ImportComponent
    assert r.findtext("Name") == "Mon IC"
    assert r.findtext("Group") == "IC"           # prefixe conserve
    assert r.findtext("value") == "LM358"
    assert len(r.findall("./datapin/DataPin")) == 2
    assert len(r.findall("./datasegment/DataSegment")) == 4     # boite
    # TL/BR = BOITE CLIQUABLE de la vignette, PAS la geometrie du symbole. Le
    # clic palette teste `e.X > TL.X && e.X < BR.X && ...` (Form1.cs) : a zero,
    # la condition est TOUJOURS fausse -> composant visible mais IMPOSSIBLE a
    # poser. Les 12 symboles de Lib.xml portent tous exactement ces valeurs.
    assert (r.find("TL").findtext("X"), r.find("TL").findtext("Y")) == ("50", "25")
    assert (r.find("BR").findtext("X"), r.find("BR").findtext("Y")) == ("210", "121")
    # CtrIem reste nul : recalcule a chaque rendu de palette (pictureBox2_Paint).
    assert (r.find("CtrIem").findtext("X"), r.find("CtrIem").findtext("Y")) == ("0", "0")
    xs, ys = [], []
    for dp in r.findall(".//datapin/DataPin"):
        p = dp.find("Pin")
        xs.append(int(p.findtext("X"))); ys.append(int(p.findtext("Y")))
    assert all(v % 10 == 0 for v in xs + ys)           # aligne grille
    assert min(xs) < 0 < max(xs) or min(ys) < 0 < max(ys)   # centre autour de 0
    # La vignette de la palette dessine `centre_cellule + coord` dans une cellule
    # de 146 px : une echelle trop grande sort de la cellule -> vignette VIDE.
    # On borne donc l'amplitude (verifie via le vrai code C# : rendu visible).
    assert max(abs(v) for v in xs + ys) <= 73          # tient dans la demi-cellule


@pytest.mark.parametrize("brochage", [
    {"1": ["L", -20], "2": ["R", 20]},
    {"1": ["L", -20], "2": ["L", 20], "3": ["R", 0], "V": ["T", 0], "G": ["B", 0]},
    {"A": ["T", -20], "B": ["T", 20], "Y": ["B", 0]},
])
def test_aller_retour_conserve_brochage_et_boite(brochage):
    entree = {"name": "Test", "pins": list(brochage),
              "brochage": brochage, "boite": {"w": 100, "h": 80}}
    prefix, relu = symbole_vers_composant(
        composant_vers_symbole_xml("IC", entree))
    assert prefix == "IC"
    # Le brochage (cote + decalage de CHAQUE broche) est preserve exactement.
    assert relu["brochage"] == {n: v for n, v in brochage.items()}
    assert set(relu["pins"]) == set(brochage)
    # La boite peut etre ajustee par geometrie_libre (marge pour tenir les
    # broches) mais l'aller-retour est STABLE : re-exporter puis relire ne
    # bouge plus rien.
    _p2, relu2 = symbole_vers_composant(
        composant_vers_symbole_xml(prefix, relu))
    assert relu2["boite"] == relu["boite"]
    assert relu2["brochage"] == relu["brochage"]


def test_import_derive_un_prefixe_si_group_absent():
    """Un symbole du collegue sans <Group> : prefixe deduit du nom, jamais vide."""
    xml = ('<DataItem><Name>BUFFER</Name>'
           '<datasegment><DataSegment>'
           '<Spoint><X>100</X><Y>100</Y></Spoint>'
           '<Epoint><X>900</X><Y>700</Y></Epoint></DataSegment></datasegment>'
           '<datapin><DataPin><Pname>1</Pname>'
           '<Pin><X>100</X><Y>400</Y></Pin></DataPin></datapin></DataItem>')
    prefix, entree = symbole_vers_composant(xml)
    assert prefix                                # non vide
    assert entree["name"] == "BUFFER"
    assert entree["pins"] == ["1"]


def test_export_circuit_est_lisible_par_le_nouveau_format():
    """Un circuit exporte (generer_xml) doit etre importable dans l'app C# du
    collegue : la connexite s'y resout par EGALITE de chaines NodeL <-> CFirst/
    CLast (Form1.cs). On verrouille donc que chaque ref de fil est une ref
    ConnRef a 4 champs ET presente dans le NodeL d'une broche."""
    import xml.etree.ElementTree as ET

    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml

    comps = [Composant(ref="R1", type="R", pins={"1": "VCC", "2": "OUT"}, value="10k"),
             Composant(ref="R2", type="R", pins={"1": "OUT", "2": "GND"}, value="22k")]
    r = ET.fromstring(generer_xml(comps))
    nodel = {(s.text or "").strip()
             for dp in r.findall(".//datapin/DataPin")
             for s in dp.findall("NodeL/string") if s.text}
    refs = [(ln.findtext(tag) or "").strip()
            for ln in r.findall(".//lineL/Line") for tag in ("CFirst", "CLast")]
    assert refs, "aucun fil exporte"
    for ref in refs:
        assert len(ref.split("_")) == 4, f"{ref} n'est pas une ref ConnRef (4 champs)"
        assert ref in nodel, f"{ref} absent des NodeL -> l'app C# ne relierait pas"


def test_export_circuit_conserve_la_connexite():
    """Aller-retour : exporte puis relu, le point milieu reste partage."""
    import tempfile
    import os

    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml, lire_xml

    comps = [Composant(ref="R1", type="R", pins={"1": "VCC", "2": "OUT"}, value="10k"),
             Composant(ref="R2", type="R", pins={"1": "OUT", "2": "GND"}, value="22k")]
    f = tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8")
    f.write(generer_xml(comps))
    f.close()
    try:
        relu = {c.ref: c.pins for c in lire_xml(f.name)}
    finally:
        os.unlink(f.name)
    assert relu["R1"]["2"] == relu["R2"]["1"]        # noeud milieu partage


def test_lit_un_bundle_multi_composants():
    """Un paquet « Exporter la bibliotheque » du collegue contient PLUSIEURS
    composants : on les recupere tous (composants_depuis_xml)."""
    e1 = {"name": "A", "pins": ["1", "2"],
          "brochage": {"1": ["L", 0], "2": ["R", 0]}, "boite": {"w": 80, "h": 60}}
    e2 = {"name": "B", "pins": ["1", "2", "3"],
          "brochage": {"1": ["L", 0], "2": ["R", 0], "3": ["T", 0]},
          "boite": {"w": 80, "h": 60}}
    # Notre export est un DataItem NU ; un paquet du collegue les enrobe.
    di1 = ET.fromstring(composant_vers_symbole_xml("AA", e1))
    di2 = ET.fromstring(composant_vers_symbole_xml("BB", e2))
    bundle = ('<LibraryBundle><Items>'
              + ET.tostring(di1, encoding="unicode")
              + ET.tostring(di2, encoding="unicode")
              + '</Items><CComps /></LibraryBundle>')
    comps = composants_depuis_xml(bundle)
    assert {p for p, _e in comps} == {"AA", "BB"}
    assert {e["name"] for _p, e in comps} == {"A", "B"}


def test_lit_une_liste_arrayofdataitem():
    """Le VIEUX fichier agrege du collegue (LibItem/Lib.xml) a pour racine
    <ArrayOfDataItem>. Sans cette branche, `composants_depuis_xml` renvoyait 0
    composant SANS erreur : la bibliotheque semblait vide."""
    e = {"name": "A", "pins": ["1", "2"],
         "brochage": {"1": ["L", 0], "2": ["R", 0]}, "boite": {"w": 80, "h": 60}}
    di = composant_vers_symbole_xml("AA", e).split("?>", 1)[1].strip()
    liste = f"<ArrayOfDataItem>{di}{di.replace('>A<', '>B<', 1)}</ArrayOfDataItem>"
    comps = composants_depuis_xml(liste)
    assert [x[1]["name"] for x in comps] == ["A", "B"]


def test_lit_la_vraie_bibliotheque_du_collegue():
    """Bout en bout sur les VRAIS fichiers : le dossier par-composant
    (LibItem/Lib, format courant depuis 2026-07-24) ET l'agregat historique
    (LibItem/Lib.xml) doivent tous deux se lire."""
    import pathlib
    racine = pathlib.Path(__file__).resolve().parents[1]
    dossier = next(iter(racine.glob("*/**/LibItem/Lib")), None)
    agregat = next(iter(racine.glob("*/**/LibItem/Lib.xml")), None)
    if dossier is None or agregat is None:
        pytest.skip("bibliotheque ERetroDesign absente (lecture seule)")
    depuis_dossier = composants_depuis_xml(str(dossier))
    assert len(depuis_dossier) >= 10          # 16 symboles au moment de l'ecriture
    assert all(e["pins"] for _p, e in depuis_dossier)
    assert composants_depuis_xml(str(agregat))     # agregat non vide


def test_symbole_reel_du_collegue_se_lit(tmp_path):
    """Un vrai symbole Lib d'ERetroDesign (BUFFER.xml) se relit sans erreur."""
    import pathlib
    biblio = (pathlib.Path(__file__).resolve().parents[1]
              / "ERetroDesign/ERetroDesign/bin/Debug/Lib/BUFFER.xml")
    if not biblio.exists():
        pytest.skip("bibliotheque ERetroDesign absente (lecture seule)")
    prefix, entree = symbole_vers_composant(str(biblio))
    assert prefix and entree["pins"]             # broches recuperees
    assert entree["boite"]["w"] > 0 and entree["boite"]["h"] > 0
