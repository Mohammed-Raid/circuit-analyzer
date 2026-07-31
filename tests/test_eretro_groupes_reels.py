"""@file test_eretro_groupes_reels.py
@brief Ecriture de VRAIS groupes <GrpL> dans le BoardSCH du collegue.

Contrat arbitre par le boss le 2026-07-31 (option A), apres le diagnostic qui a
montre que l'ecriture de `GpId` seul etait un no-op VISUEL : `<GrpL>` est la
seule source d'affichage de groupe de son editeur (Form1.cs:12096-12108 dessine
`GrpL[i].GRect`, Form1.cs:9095 y fait le test de clic). Ne pas l'ecrire, c'est
n'ecrire rien de visible.

La forme XML attendue n'est pas devinee : elle a ete produite par SON PROPRE
XmlSerializer (harnais net472 du scratchpad), d'ou l'ordre CtrG, Gid, Name,
NameOffset, GRect, Selected, IidL, LidL — un XmlSerializer .NET est sensible a
l'ordre des elements d'une sequence.
"""
import os
import xml.etree.ElementTree as ET

import pytest

from circuit_analyzer.composant import Composant
from circuit_analyzer.eretro_patch import _BASE_ANALYSE, ecrire_groupes
from circuit_analyzer.xml import generer_xml, lire_xml

_DOSSIER_REEL = "CARTE POUR TESTER (VRAI TEST)"


def _carte(tmp_path, nom="synth.xml"):
    """@brief BoardSCH synthetique relisible par lire_xml."""
    comps = [
        Composant("R1", "R", {"1": "IN", "2": "N1"}, "10k"),
        Composant("R2", "R", {"1": "N1", "2": "OUT"}, "100k"),
        Composant("C1", "C", {"1": "N1", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "GND", "IN-": "N1", "OUT": "OUT"}, ""),
    ]
    p = os.path.join(str(tmp_path), nom)
    with open(p, "w", encoding="utf-8") as f:
        f.write(generer_xml(comps))
    return p


def _analyser(chemin):
    from circuit_analyzer.graph_builder import build_graph
    from circuit_analyzer.matcher import match_patterns
    comps = lire_xml(chemin)
    return comps, match_patterns(build_graph(comps))


def _patcher(chemin):
    comps, res = _analyser(chemin)
    return ET.fromstring(ecrire_groupes(comps.source, comps, res))


# ─────────────────────── la balise existe et est bien placee ───────────────

def test_grpl_est_creee_meme_absente_de_la_source(tmp_path):
    """Les 4 cartes reelles n'ont AUCUNE balise <GrpL> : il faut la creer."""
    racine = _patcher(_carte(tmp_path))
    assert racine.find("GrpL") is not None
    assert racine.findall("./GrpL/GRPS"), "aucun groupe ecrit"


def test_grpl_se_place_entre_ccmpntl_et_zoom(tmp_path):
    """L'XmlSerializer .NET lit une SEQUENCE : un <GrpL> mal place casse la
    deserialisation de tout ce qui suit. Ordre impose par BoardSCH.cs."""
    racine = _patcher(_carte(tmp_path))
    tags = [e.tag for e in racine]
    assert tags.index("CCmpntL") < tags.index("GrpL") < tags.index("zoom")


def test_le_grps_porte_ses_champs_dans_l_ordre_du_csharp(tmp_path):
    """Ordre releve sur la sortie de SON XmlSerializer, pas suppose."""
    racine = _patcher(_carte(tmp_path))
    grps = racine.find("./GrpL/GRPS")
    assert [e.tag for e in grps] == ["CtrG", "Gid", "Name", "NameOffset",
                                     "GRect", "Selected", "IidL", "LidL"]


def test_le_grect_porte_location_size_ET_les_scalaires(tmp_path):
    """System.Drawing.Rectangle expose Location/Size ET X/Y/Width/Height :
    son serialiseur emet LES DEUX. Omettre un couple donne un rectangle nul."""
    racine = _patcher(_carte(tmp_path))
    grect = racine.find("./GrpL/GRPS/GRect")
    assert [e.tag for e in grect] == ["Location", "Size", "X", "Y", "Width", "Height"]
    assert [e.tag for e in grect.find("Location")] == ["X", "Y"]
    assert [e.tag for e in grect.find("Size")] == ["Width", "Height"]


# ─────────────────────── le contenu designe les bons elements ──────────────

def test_iidl_indexe_les_positions_de_cmpntl(tmp_path):
    """Son UpdateGrp fait `GrpL[j].IidL.Add(i)` ou i est l'INDICE dans CmpntL
    (Form1.cs:9221) — pas un <id>, que les vraies cartes ont duplique a 0."""
    racine = _patcher(_carte(tmp_path))
    nb = len(racine.findall("./CmpntL/DataItem"))
    for grps in racine.findall("./GrpL/GRPS"):
        indices = [int(i.text) for i in grps.findall("./IidL/int")]
        assert indices, "un groupe sans aucun composant n'a pas de sens"
        assert all(0 <= i < nb for i in indices)
        assert len(set(indices)) == len(indices)


def test_iidl_et_gpid_designent_les_MEMES_elements(tmp_path):
    """C'est l'invariant que son UpdateGrp reconstruit (`GpId == Gid`). Si les
    deux divergent, la premiere action de l'utilisateur redistribue les
    membres et notre annotation part en morceaux."""
    racine = _patcher(_carte(tmp_path))
    items = racine.findall("./CmpntL/DataItem")
    for grps in racine.findall("./GrpL/GRPS"):
        gid = int(grps.findtext("Gid"))
        par_iidl = {int(i.text) for i in grps.findall("./IidL/int")}
        par_gpid = {n for n, d in enumerate(items)
                    if int(d.findtext("GpId") or 0) == gid}
        assert par_iidl == par_gpid


def test_lidl_et_gpid_des_fils_designent_les_memes_fils(tmp_path):
    racine = _patcher(_carte(tmp_path))
    fils = racine.findall("./lineL/Line")
    for grps in racine.findall("./GrpL/GRPS"):
        gid = int(grps.findtext("Gid"))
        par_lidl = {int(i.text) for i in grps.findall("./LidL/int")}
        par_gpid = {n for n, l in enumerate(fils)
                    if int(l.findtext("GpId") or 0) == gid}
        assert par_lidl == par_gpid


def test_le_nom_du_montage_voyage_dans_le_groupe(tmp_path):
    """Interet principal pour le boss : LIRE « Amplificateur inverseur » sur le
    cadre, dans SON editeur (Form1.cs:12108 dessine GrpL[i].Name)."""
    racine = _patcher(_carte(tmp_path))
    noms = [g.findtext("Name") for g in racine.findall("./GrpL/GRPS")]
    assert all(n and n.strip() for n in noms)


# ─────────────────────── les drapeaux, cette fois, sont CORRECTS ───────────

def test_les_membres_portent_begrp_vrai(tmp_path):
    """Le 2026-07-30 poser Begrp SANS <GrpL> rendait les composants inertes.
    Avec un <GrpL> qui les reference, c'est au contraire l'etat attendu par
    son editeur — c'est exactement ce que fait son CreateGrpFun:8954."""
    racine = _patcher(_carte(tmp_path))
    for d in racine.findall("./CmpntL/DataItem"):
        groupe = int(d.findtext("GpId") or 0) != 0
        assert (d.findtext("Begrp") or "").strip().lower() == str(groupe).lower()


def test_les_fils_membres_portent_beingrp_vrai(tmp_path):
    racine = _patcher(_carte(tmp_path))
    for l in racine.findall("./lineL/Line"):
        groupe = int(l.findtext("GpId") or 0) != 0
        assert (l.findtext("BeIngrp") or "").strip().lower() == str(groupe).lower()


def test_le_rectangle_de_groupe_n_est_pas_nul(tmp_path):
    """GRect=0,0,0,0 (ce que son CreateGrpFun ecrit) n'est rattrape que par
    UpdateGrp, que RestoreBoard n'appelle PAS au chargement : le cadre serait
    invisible a l'ouverture. C'est precisement le no-op qu'on vient de fuir."""
    racine = _patcher(_carte(tmp_path))
    for grps in racine.findall("./GrpL/GRPS"):
        assert int(grps.findtext("./GRect/Width")) > 0
        assert int(grps.findtext("./GRect/Height")) > 0


# ─────────────────────── on ne vole pas SES groupes a lui ──────────────────

def _ajouter_son_groupe(chemin, gid=1):
    """@brief Simule une carte deja groupee A LA MAIN par le collegue."""
    arbre = ET.parse(chemin)
    racine = arbre.getroot()
    grpl = racine.find("GrpL")
    if grpl is None:
        grpl = ET.SubElement(racine, "GrpL")
    grps = ET.SubElement(grpl, "GRPS")
    ET.SubElement(grps, "Gid").text = str(gid)
    ET.SubElement(grps, "Name").text = "SON groupe a lui"
    iidl = ET.SubElement(grps, "IidL")
    ET.SubElement(iidl, "int").text = "0"
    premier = racine.find("./CmpntL/DataItem")
    premier.find("GpId").text = str(gid)
    premier.find("Begrp").text = "true"
    arbre.write(chemin, encoding="utf-8", xml_declaration=True)


def test_les_groupes_du_collegue_survivent_au_patch(tmp_path):
    chemin = _carte(tmp_path)
    _ajouter_son_groupe(chemin)
    racine = _patcher(chemin)
    siens = [g for g in racine.findall("./GrpL/GRPS")
             if int(g.findtext("Gid")) < _BASE_ANALYSE]
    assert len(siens) == 1
    assert siens[0].findtext("Name") == "SON groupe a lui"


def test_un_composant_deja_dans_son_groupe_n_est_pas_vole(tmp_path):
    """Risque latent acte le 2026-07-30 et jamais traite : ecraser SON GpId."""
    chemin = _carte(tmp_path)
    _ajouter_son_groupe(chemin, gid=1)
    racine = _patcher(chemin)
    premier = racine.find("./CmpntL/DataItem")
    assert int(premier.findtext("GpId")) == 1, "son groupe a ete ecrase"


def test_nos_gid_ne_peuvent_pas_entrer_en_collision_avec_les_siens(tmp_path):
    """Ses Gid valent GrpL.Count()+1, puis i+1 : toujours petits. Les notres
    vivent au-dessus de _BASE_ANALYSE pour que les deux jeux coexistent."""
    racine = _patcher(_carte(tmp_path))
    for grps in racine.findall("./GrpL/GRPS"):
        assert int(grps.findtext("Gid")) > _BASE_ANALYSE


# ─────────────────────── rejouer le patch ne s'accumule pas ────────────────

def test_repatcher_ne_duplique_pas_les_groupes(tmp_path):
    chemin = _carte(tmp_path)
    comps, res = _analyser(chemin)
    un = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    deux = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    assert len(un.findall("./GrpL/GRPS")) == len(deux.findall("./GrpL/GRPS"))


def test_repatcher_sans_resultats_degroupe_tout(tmp_path):
    """Les membres doivent redevenir libres : GpId remis a 0 ET drapeau baisse,
    sinon on laisse des composants insélectionnables dans son editeur."""
    chemin = _carte(tmp_path)
    comps, res = _analyser(chemin)
    ecrire_groupes(comps.source, comps, res)
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, None))
    assert racine.findall("./GrpL/GRPS") == []
    for d in racine.findall("./CmpntL/DataItem"):
        assert int(d.findtext("GpId") or 0) == 0
        assert (d.findtext("Begrp") or "").strip().lower() == "false"
    for l in racine.findall("./lineL/Line"):
        assert (l.findtext("BeIngrp") or "").strip().lower() == "false"


# ─────────────────────── sur les vraies cartes ─────────────────────────────

@pytest.mark.skipif(not os.path.isdir(_DOSSIER_REEL), reason="cartes reelles absentes")
@pytest.mark.parametrize("nom", ["pg carte.xml", "PG 2.xml", "PG 3.xml",
                                 "PowtranAlim20260809.xml"])
def test_les_cartes_reelles_recoivent_des_groupes_coherents(nom):
    racine = _patcher(os.path.join(_DOSSIER_REEL, nom))
    groupes = racine.findall("./GrpL/GRPS")
    assert groupes, f"{nom} : aucun montage groupe"
    items = racine.findall("./CmpntL/DataItem")
    vus = set()
    for grps in groupes:
        indices = {int(i.text) for i in grps.findall("./IidL/int")}
        assert indices, "groupe vide"
        assert not (indices & vus), "un composant appartient a deux groupes"
        vus |= indices
        assert all(0 <= i < len(items) for i in indices)
        assert int(grps.findtext("./GRect/Width")) > 0
