"""@file test_export_lisible.py
@brief Ce que SON editeur doit pouvoir afficher d'un schema que NOUS generons.

Defauts mesures en desserialisant nos sorties avec son XmlSerializer (harnais
net472). Ne PAS ajouter d'assertion sur <TL>/<BR> : (50,25)/(210,121) est une
constante de son format, portee par les 209 composants poses de ses 4 cartes.
"""
import xml.etree.ElementTree as ET

from circuit_analyzer.composant import Composant
from circuit_analyzer.xml import generer_xml


def test_chaque_composant_porte_sa_reference():
    comps = [Composant("R1", "R", {"1": "IN", "2": "N1"}, "10k"),
             Composant("C1", "C", {"1": "N1", "2": "GND"}, "100n")]
    racine = ET.fromstring(generer_xml(comps))
    refs = [(d.findtext("reference") or "").strip()
            for d in racine.findall("./CmpntL/DataItem")]
    assert "R1" in refs and "C1" in refs


def test_la_reference_ne_pollue_pas_la_valeur():
    """`value` porte 10k, PAS R1 : son editeur affiche les deux separement."""
    racine = ET.fromstring(generer_xml(
        [Composant("R1", "R", {"1": "IN", "2": "N1"}, "10k")]))
    d = racine.find("./CmpntL/DataItem")
    assert (d.findtext("reference") or "").strip() == "R1"
    assert (d.findtext("value") or "").strip() == "10k"


def test_les_rails_ajoutes_n_usurpent_pas_une_reference():
    """Les symboles de masse/alim naissent d'un NET, pas d'un composant :
    leur donner la reference d'un voisin creerait un doublon chez lui."""
    racine = ET.fromstring(generer_xml(
        [Composant("R1", "R", {"1": "IN", "2": "GND"}, "10k")]))
    refs = [(d.findtext("reference") or "").strip()
            for d in racine.findall("./CmpntL/DataItem")]
    assert refs.count("R1") == 1


def test_une_masse_ne_devient_pas_un_boitier_dip():
    """`_TYPE_VERS_FORME` sans entree GND -> la broche numerotee "1" faisait
    tomber le composant dans la branche PuceN (xml.py:829)."""
    racine = ET.fromstring(generer_xml(
        [Composant("R1", "R", {"1": "IN", "2": "GND"}, "10k"),
         Composant("GND1", "GND", {"1": "GND"}, "")]))
    noms = [d.findtext("Name") for d in racine.findall("./CmpntL/DataItem")]
    assert not any((n or "").startswith("Puce") for n in noms), \
        f"boitier fantome : {noms}"


def test_l_alimentation_non_plus():
    racine = ET.fromstring(generer_xml(
        [Composant("R1", "R", {"1": "VCC", "2": "N1"}, "10k"),
         Composant("VCC1", "VCC", {"1": "VCC"}, "")]))
    noms = [d.findtext("Name") for d in racine.findall("./CmpntL/DataItem")]
    assert not any((n or "").startswith("Puce") for n in noms), \
        f"boitier fantome : {noms}"


def test_les_composants_declares_sont_tous_emis():
    """Corollaire mesurable : 2 composants en entree, 2 formes en sortie
    (plus les rails nes des nets, qui ne portent pas de reference)."""
    racine = ET.fromstring(generer_xml(
        [Composant("R1", "R", {"1": "IN", "2": "GND"}, "10k"),
         Composant("GND1", "GND", {"1": "GND"}, "")]))
    refs = [(d.findtext("reference") or "").strip()
            for d in racine.findall("./CmpntL/DataItem")]
    assert "R1" in refs and "GND1" in refs
