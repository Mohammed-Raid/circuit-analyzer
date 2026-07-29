"""@file test_eretro_patch.py
@brief Retour fidele vers ERetroDesign : pont ref->element et ecriture des groupes.
"""
import os
import xml.etree.ElementTree as ET

import pytest

from circuit_analyzer.composant import Composant
from circuit_analyzer.xml import generer_xml, lire_xml

_DOSSIER_REEL = "CARTE POUR TESTER (VRAI TEST)"


def _fichier_synthetique(tmp_path, comps=None):
    """@brief Ecrit un BoardSCH valide via generer_xml et renvoie son chemin.

    On part de notre PROPRE generateur : il produit un document que lire_xml
    sait relire, donc le test n'a pas besoin des cartes reelles (absentes en CI).
    """
    comps = comps or [
        Composant("R1", "R", {"1": "IN", "2": "N1"}, "10k"),
        Composant("C1", "C", {"1": "N1", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "N1", "IN-": "N2", "OUT": "OUT"}, ""),
    ]
    p = os.path.join(str(tmp_path), "synth.xml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(generer_xml(comps))
    return p


def test_source_absente_quand_la_liste_ne_vient_pas_d_un_xml():
    assert getattr([], "source", None) is None


def test_lire_xml_publie_l_arbre_et_le_pont(tmp_path):
    comps = lire_xml(_fichier_synthetique(tmp_path))
    src = comps.source
    assert src is not None
    assert isinstance(src.arbre, ET.ElementTree)
    # Une entree de pont par composant emis, et pas une de plus.
    assert set(src.elements) == {c.ref for c in comps}


def test_le_pont_designe_le_bon_element(tmp_path):
    comps = lire_xml(_fichier_synthetique(tmp_path))
    src = comps.source
    items = src.arbre.getroot().findall(".//CmpntL/DataItem")
    for c in comps:
        assert src.elements[c.ref] in items


def test_le_pont_expose_les_fils_dans_l_ordre_du_fichier(tmp_path):
    comps = lire_xml(_fichier_synthetique(tmp_path))
    src = comps.source
    assert src.lignes == src.arbre.getroot().findall(".//lineL/Line")
    # Chaque fil resolu designe deux refs connues du pont.
    for idx, (ra, rb) in src.lignes_refs.items():
        assert 0 <= idx < len(src.lignes)
        assert ra in src.elements and rb in src.elements


@pytest.mark.skipif(not os.path.isdir(_DOSSIER_REEL), reason="cartes reelles absentes")
def test_un_compose_pointe_sur_son_boitier_pas_sur_ses_entrailles():
    chemin = os.path.join(_DOSSIER_REEL, "PowtranAlim20260809.xml")
    comps = lire_xml(chemin)
    src = comps.source
    boitiers = src.arbre.getroot().findall(".//CCmpntL/CComp")
    internes = [r for r in src.elements if "." in r]
    assert internes, "la carte de reference contient une puce composee"
    for ref in internes:
        assert src.elements[ref] in boitiers


def _analyser(chemin):
    """@brief Chaine d'analyse minimale : composants + resultats du detecteur."""
    from circuit_analyzer.graph_builder import build_graph
    from circuit_analyzer.matcher import match_patterns
    comps = lire_xml(chemin)
    return comps, match_patterns(build_graph(comps))


def test_patch_ecrit_un_gpid_non_nul_sur_les_composants_groupes(tmp_path):
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    gpids = {int(d.findtext("GpId") or 0) for d in racine.findall(".//CmpntL/DataItem")}
    assert gpids != {0}, "aucun groupe ecrit"


def test_begrp_suit_toujours_gpid(tmp_path):
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    for d in racine.findall(".//CmpntL/DataItem"):
        attendu = "true" if int(d.findtext("GpId") or 0) else "false"
        assert (d.findtext("Begrp") or "").strip() == attendu


def test_patch_sans_resultats_ne_groupe_rien(tmp_path):
    from circuit_analyzer.eretro_patch import ecrire_groupes
    comps = lire_xml(_fichier_synthetique(tmp_path))
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, None))
    assert {int(d.findtext("GpId") or 0)
            for d in racine.findall(".//CmpntL/DataItem")} == {0}


def test_un_composant_absent_de_la_source_ne_cree_rien(tmp_path):
    """Cas limite spec §4 : un composant inconnu du fichier n'ajoute aucun element."""
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    n_avant = len(ET.parse(chemin).getroot().findall(".//CmpntL/DataItem"))
    comps.append(Composant("R99", "R", {"1": "IN", "2": "GND"}, "1k"))
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    assert len(racine.findall(".//CmpntL/DataItem")) == n_avant


def test_patch_ne_touche_a_rien_d_autre(tmp_path):
    """Invariant central : hors GpId/Begrp/BeIngrp, l'arbre est identique."""
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    avant = ET.parse(chemin).getroot()
    apres = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    _comparer_sauf_groupes(avant, apres)


def test_ecrire_refuse_de_creer_une_balise_manquante():
    """Revue #2 : le chemin de refus de _ecrire n'etait exerce par aucun test.

    C'est la propriete de securite centrale du module (l'ordre attendu par
    l'XmlSerializer C# nous est inconnu, donc on ne cree jamais une balise).
    """
    from circuit_analyzer.eretro_patch import _ecrire
    elem = ET.Element("DataItem")
    assert _ecrire(elem, "GpId", 1) is False
    assert list(elem) == [], "aucune balise ne doit etre creee"


def test_manquants_declenche_un_warning(caplog):
    """Revue #2 : le compteur `manquants` doit remonter en warning."""
    from circuit_analyzer.eretro import SourceXML
    from circuit_analyzer.eretro_patch import ecrire_groupes
    racine = ET.Element("BoardSCH")
    di = ET.SubElement(ET.SubElement(racine, "CmpntL"), "DataItem")
    ET.SubElement(di, "Name").text = "R1"   # pas de GpId : hors dialecte connu
    src = SourceXML(arbre=ET.ElementTree(racine), elements={"R1": di},
                     lignes=[], lignes_refs={})
    with caplog.at_level("WARNING", logger="circuit_analyzer.eretro_patch"):
        ecrire_groupes(src, [], None)
    assert any("GpId" in rec.message for rec in caplog.records)


def _entete(texte_xml, tag_racine="BoardSCH"):
    """@brief Prologue + balise racine ouvrante COMPLETE (jusqu'au '>' inclus)."""
    fin = texte_xml.index(">", texte_xml.index(f"<{tag_racine}")) + 1
    return texte_xml[:fin]


def _sans_fins_de_ligne(texte):
    """@brief Normalise CRLF/CR en LF pour COMPARER du contenu, pas des octets.

    `ecrire_groupes` renvoie desormais une chaine en LF pur (ronde de
    correction 3 : voir `_normaliser_fins_de_ligne` dans eretro_patch.py) ;
    la source disque, elle, reste en CRLF. Normaliser les DEUX cotes ici
    compare donc bien le contenu (prologue, xmlns) sans etre sensible a la
    convention de fin de ligne, qui est desormais la responsabilite de
    l'appelant qui ecrit le fichier — ca n'affaiblit pas l'assertion de
    contenu, ca la rend juste insensible a un detail qui ne lui appartient
    plus.
    """
    return texte.replace("\r\n", "\n").replace("\r", "\n")


@pytest.mark.skipif(not os.path.isdir(_DOSSIER_REEL), reason="cartes reelles absentes")
def test_entete_restituee_a_l_identique_sur_une_carte_reelle():
    """Constat #1 (ronde de correction) : prologue + xmlns:* ne doivent pas se perdre.

    ET.parse() ne conserve pas les xmlns:* qui ne qualifient aucun tag ; lire_xml
    doit les avoir captes a part pour qu'ecrire_groupes les restitue tels quels.
    """
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = os.path.join(_DOSSIER_REEL, "pg carte.xml")
    with open(chemin, "rb") as f:
        brut_source = f.read().decode("utf-8")
    comps, res = _analyser(chemin)
    patche = ecrire_groupes(comps.source, comps, res)
    assert _sans_fins_de_ligne(_entete(patche)) == _sans_fins_de_ligne(_entete(brut_source))


def test_les_namespaces_absents_de_la_source_ne_sont_pas_fabriques(tmp_path):
    """On ne devine jamais le format : un document sans xmlns:* en ressort sans."""
    from circuit_analyzer.eretro_patch import ecrire_groupes
    contenu = generer_xml([Composant("R1", "R", {"1": "IN", "2": "GND"}, "10k")])
    contenu_sans_ns = contenu.replace(
        '<BoardSCH xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema">',
        "<BoardSCH>",
    )
    assert "xmlns" not in contenu_sans_ns, "le remplacement du test n'a rien trouve"
    p = os.path.join(str(tmp_path), "sans_ns.xml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(contenu_sans_ns)

    comps = lire_xml(p)
    assert comps.source.namespaces == []

    patche = ecrire_groupes(comps.source, comps, None)
    assert "xmlns" not in patche


def test_entete_idempotente_sur_deux_ecritures_successives(tmp_path):
    """Poser les xmlns:* mute l'arbre partage (source.arbre) : ca ne doit pas
    s'accumuler ni se deformer si on rappelle ecrire_groupes plusieurs fois
    sur la meme SourceXML (ex. reecriture apres une nouvelle analyse)."""
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    premiere = ecrire_groupes(comps.source, comps, res)
    seconde = ecrire_groupes(comps.source, comps, res)
    assert premiere == seconde
    assert _entete(premiere) == _entete(seconde)


def test_ecrire_groupes_ne_melange_pas_crlf_et_lf(tmp_path):
    """Ronde de correction 3 : la re-revue a trouve un '\\r\\r\\n' en tete du
    fichier ecrit reellement par l'appli. `ecrire_groupes` renvoie une
    CHAINE, pas des octets : melanger le '\\r\\n' brut de `avant_racine`
    (capture depuis le disque, donc deja CRLF sur une carte reelle) avec le
    corps '\\n' pur d'ET.tostring() est la cause. La chaine renvoyee doit
    donc etre uniformement LF : aucun '\\r' nulle part, quelle que soit la
    convention de la source.
    """
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    patche = ecrire_groupes(comps.source, comps, res)
    assert "\r" not in patche, "la chaine renvoyee melange CRLF (source) et LF (ET.tostring)"


def test_ecriture_sur_disque_ne_produit_pas_de_crlf_double(tmp_path):
    """Le test de bout en bout qui manquait (ronde de correction 3) : les
    autres tests de ce fichier travaillent tous sur la chaine en memoire.
    Ici on reproduit le CHEMIN REEL de l'appelant (gui/tab_analyze.py :
    `open(p, 'w', encoding='utf-8')` puis `f.write(...)`) : c'est CE mode
    texte qui retraduit '\\n' -> '\\r\\n' sur Windows, et qui transformait un
    '\\r\\n' deja present dans la chaine en '\\r\\r\\n' corrompu — invisible
    tant qu'on ne relit pas le fichier en binaire.
    """
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    patche = ecrire_groupes(comps.source, comps, res)

    cible = os.path.join(str(tmp_path), "recu.xml")
    with open(cible, "w", encoding="utf-8") as f:   # meme mode que l'appelant reel
        f.write(patche)

    with open(cible, "rb") as f:
        brut = f.read()
    assert b"\r\r\n" not in brut, "fin de ligne CRLF doublee : fichier malforme"


def test_poser_groupe_incomplet_si_le_drapeau_compagnon_manque():
    """Revue #3 : _poser_groupe ne comptait que l'ecriture de GpId.

    Un element qui porte GpId mais pas son drapeau (ou l'inverse) est
    partiellement hors dialecte : ce n'est pas un succes.
    """
    from circuit_analyzer.eretro_patch import _poser_groupe
    elem = ET.Element("DataItem")
    ET.SubElement(elem, "GpId").text = "0"
    # Pas de Begrp : le drapeau compagnon est absent.
    assert _poser_groupe(elem, 3, "Begrp") is False


_CHAMPS_GROUPE = {"GpId", "Begrp", "BeIngrp"}


def _comparer_sauf_groupes(a, b, chemin="/"):
    """@brief Egalite RECURSIVE de deux arbres, hors champs de groupe.

    Compare la structure (tag, ordre, nombre d'enfants), le texte et les
    attributs. On compare arbre a arbre et NON octet a octet : ElementTree
    re-serialise tout le document (balises auto-fermantes, espaces), un diff
    textuel serait rouge en permanence et donc jamais relu.
    """
    assert a.tag == b.tag, f"{chemin} : {a.tag} != {b.tag}"
    assert a.attrib == b.attrib, f"{chemin}{a.tag} : attributs modifies"
    ea, eb = list(a), list(b)
    assert [x.tag for x in ea] == [x.tag for x in eb], \
        f"{chemin}{a.tag} : enfants ajoutes, retires ou reordonnes"
    if a.tag not in _CHAMPS_GROUPE:
        assert (a.text or "").strip() == (b.text or "").strip(), \
            f"{chemin}{a.tag} : texte modifie"
    for i, (x, y) in enumerate(zip(ea, eb)):
        _comparer_sauf_groupes(x, y, f"{chemin}{a.tag}[{i}]/")
