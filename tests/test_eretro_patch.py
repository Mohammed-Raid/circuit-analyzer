"""@file test_eretro_patch.py
@brief Retour fidele vers ERetroDesign : pont ref->element et ecriture des groupes.
"""
import os
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest

from circuit_analyzer.composant import Composant
from circuit_analyzer.xml import generer_xml, lire_xml

_DOSSIER_REEL = "CARTE POUR TESTER (VRAI TEST)"


def test_deltas_disposition_canonique_ancre_sur_le_centroide_reel(tmp_path):
    """@brief Les refs de role (aop/Zin/Zf) d'un ampli inverseur recoivent un
    delta qui les ramene vers la disposition canonique, centree sur leur
    centroide REEL actuel — pas une origine arbitraire."""
    from circuit_analyzer.eretro_patch import _deltas_disposition_canonique
    from circuit_analyzer.xml import _grouper_par_circuit

    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Composant("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Composant("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, res = _analyser(chemin)
    source = lus.source
    blocs = _grouper_par_circuit(lus, res)
    assert len(blocs) == 1 and blocs[0].roles, "l'ampli inverseur doit etre reconnu avec ses roles"

    deltas = _deltas_disposition_canonique(source, lus, blocs)
    assert set(deltas) == {"U1", "R1", "R2"}
    for ref, (dx, dy) in deltas.items():
        assert isinstance(dx, (int, float)) and isinstance(dy, (int, float))


def test_deltas_disposition_canonique_vide_sans_roles(tmp_path):
    """@brief Un montage non migre (pas de roles) ne produit aucun delta."""
    from circuit_analyzer.eretro_patch import _deltas_disposition_canonique
    from circuit_analyzer.xml import _Bloc

    comps = [Composant("R1", "R", {"1": "A", "2": "B"})]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, _ = _analyser(chemin)
    bloc_sans_roles = _Bloc("Divers", list(lus))
    deltas = _deltas_disposition_canonique(lus.source, lus, [bloc_sans_roles])
    assert deltas == {}


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
    """Revue de branche : la version precedente assertait sur une `list` NUE,
    c'est-a-dire un fait du langage CPython, sans exercer une seule ligne du
    projet. C'est `ListeComposantsXML.__init__` qui pose `self.source = None`
    (xml.py) — c'est donc lui qu'il faut interroger."""
    from circuit_analyzer.xml import ListeComposantsXML
    assert ListeComposantsXML([]).source is None


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


def test_aucun_gpid_ecrit_ne_peut_egaler_un_gid_cote_csharp(tmp_path):
    """Revue de branche, constat 1 : nos groupes etaient numerotes 1, 2, 3...
    et les SIENS aussi (`_grps.Gid = GrpL.Count() + 1`, Form1.cs:8945). Des
    qu'il creait son premier groupe, son `UpdateGrp()` (Form1.cs:9216, 9238)
    absorbait dans SON groupe tous nos elements marques GpId=1 — mesure sur
    `pg carte.xml` : 3 composants et 5 fils. Tirer son groupe de 3 en aurait
    traine huit.

    Ses QUATRE lectures de GpId (Form1.cs:8963, 9216, 9238, 9328) sont des
    egalites contre un Gid, et tout Gid vaut >= 1 (creation `Count + 1`,
    renumerotation `i + 1` en :9339) donc PETIT et contigu. Depuis l'option A
    (2026-07-31) nos GpId ne sont plus negatifs — ils designent un `<GRPS>` que
    nous ecrivons vraiment — mais ils restent hors de son domaine, au-dessus de
    _BASE_ANALYSE, pour que les deux jeux de groupes coexistent."""
    from circuit_analyzer.eretro_patch import _BASE_ANALYSE, ecrire_groupes
    comps, res = _analyser(_fichier_synthetique(tmp_path))
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    ecrits = [int(e.findtext("GpId") or 0)
              for e in racine.iter() if e.find("GpId") is not None]
    assert any(g for g in ecrits), "garde-fou : au moins un element doit etre groupe"
    for g in ecrits:
        assert g == 0 or g > _BASE_ANALYSE, \
            f"GpId {g} dans le domaine de ses Gid : collision possible"


def test_un_composant_hors_montage_garde_son_drapeau(tmp_path):
    """Contrepoint de l'option A : on leve `Begrp` sur les MEMBRES, et sur eux
    seuls. Un composant qu'aucun montage ne reclame doit ressortir tel quel —
    le rabaisser d'office ecraserait un groupe fait a la main par le collegue
    (Form1.cs:8954 est le seul endroit ou LUI le leve)."""
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    avant = {d.findtext("ID"): (d.findtext("Begrp") or "").strip()
             for d in ET.parse(chemin).getroot().findall(".//CmpntL/DataItem")}
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    items = racine.findall(".//CmpntL/DataItem")
    assert any(int(d.findtext("GpId") or 0) for d in items), \
        "garde-fou : au moins un composant doit etre groupe, sinon on ne prouve rien"
    libres = [d for d in items if not int(d.findtext("GpId") or 0)]
    assert libres, "garde-fou : la fixture doit contenir un composant non groupe"
    for d in libres:
        assert (d.findtext("Begrp") or "").strip() == avant[d.findtext("ID")], \
            "le drapeau d'un composant hors montage a ete modifie"


def test_patch_sans_resultats_ne_groupe_rien(tmp_path):
    from circuit_analyzer.eretro_patch import ecrire_groupes
    comps = lire_xml(_fichier_synthetique(tmp_path))
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, None))
    assert {int(d.findtext("GpId") or 0)
            for d in racine.findall(".//CmpntL/DataItem")} == {0}


def test_un_fil_intra_groupe_prend_le_groupe(tmp_path):
    from circuit_analyzer.eretro_patch import ecrire_groupes
    comps, res = _analyser(_fichier_synthetique(tmp_path))
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    items = racine.findall(".//CmpntL/DataItem")
    lignes = racine.findall(".//lineL/Line")
    assert items and lignes  # garde-fou : le fichier synthetique est non vide
    # Revue de branche : l'assertion etait sous un `if`, donc le test passait
    # vert sans rien verifier si plus aucun groupe n'etait ecrit. La condition
    # est desormais ASSERTEE, pas supposee.
    assert {int(d.findtext("GpId") or 0) for d in items} != {0}, \
        "garde-fou : au moins un composant doit etre groupe, sinon on ne prouve rien"
    assert any(int(l.findtext("GpId") or 0) for l in lignes), \
        "un montage groupe doit avoir au moins un fil interne qui porte son groupe"


def test_un_fil_entre_deux_groupes_reste_a_zero(tmp_path):
    """Un fil dont les deux bouts n'ont pas le meme groupe n'est jamais groupe."""
    from circuit_analyzer.eretro_patch import _gid_analyse, ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    src = comps.source
    from circuit_analyzer.xml import _grouper_par_circuit, _ids_groupes_par_ref
    gid = _ids_groupes_par_ref(_grouper_par_circuit(comps, res)) if res else {}
    racine = ET.fromstring(ecrire_groupes(src, comps, res))
    lignes = racine.findall(".//lineL/Line")
    # Revue de branche : rien n'exigeait que le cas NOMME par le test (deux
    # bouts dans des groupes DIFFERENTS) se produise. La fixture en contient un
    # aujourd'hui, par chance ; on l'assert desormais, sinon le test ne verifie
    # que des fils intra-groupe sous un nom qui promet le contraire.
    bouts = [(gid.get(ra, 0), gid.get(rb, 0)) for ra, rb in src.lignes_refs.values()]
    assert any(ga and gb and ga != gb for ga, gb in bouts), \
        "garde-fou : la fixture doit contenir un fil ENTRE deux groupes"
    for idx, (ra, rb) in src.lignes_refs.items():
        ga, gb = gid.get(ra, 0), gid.get(rb, 0)
        # On n'est pas cense reimplementer la regle de production ici, mais
        # l'enoncer : un fil ne porte un groupe QUE si ses deux bouts sont
        # dans le meme, sinon zero.
        if ga and ga == gb:
            assert int(lignes[idx].findtext("GpId") or 0) == _gid_analyse(ga)
        else:
            assert int(lignes[idx].findtext("GpId") or 0) == 0


def test_un_fil_hors_montage_garde_son_drapeau(tmp_path):
    """Pendant fil de `test_un_composant_hors_montage_garde_son_drapeau`."""
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    avant = [(l.findtext("BeIngrp") or "").strip()
             for l in ET.parse(chemin).getroot().findall(".//lineL/Line")]
    lignes = ET.fromstring(ecrire_groupes(comps.source, comps, res)) \
        .findall(".//lineL/Line")
    assert any(int(l.findtext("GpId") or 0) for l in lignes), \
        "garde-fou : au moins un fil doit etre groupe, sinon on ne prouve rien"
    libres = [n for n, l in enumerate(lignes) if not int(l.findtext("GpId") or 0)]
    assert libres, "garde-fou : la fixture doit contenir un fil non groupe"
    for n in libres:
        assert (lignes[n].findtext("BeIngrp") or "").strip() == avant[n], \
            "le drapeau d'un fil hors montage a ete modifie"


def test_fil_manquant_declenche_un_warning_distinct(caplog):
    """Correction ronde 1, constat 1 : un <Line> hors dialecte (sans balise
    GpId) doit remonter en warning, au meme titre qu'un composant hors dialecte
    (`test_manquants_declenche_un_warning`) — mais le message doit designer un
    FIL, pas un composant, sinon le diagnostic ne dit pas lequel des deux est
    en cause. (BeIngrp n'entre plus en jeu : depuis l'arbitrage du 2026-07-30
    on ne lit ni n'ecrit plus les drapeaux.)"""
    from circuit_analyzer.eretro import SourceXML
    from circuit_analyzer.eretro_patch import ecrire_groupes
    racine = ET.Element("BoardSCH")
    liste = ET.SubElement(racine, "lineL")

    sain = ET.SubElement(liste, "Line")          # dans le dialecte : deux balises
    ET.SubElement(sain, "GpId").text = "0"
    ET.SubElement(sain, "BeIngrp").text = "false"

    hors = ET.SubElement(liste, "Line")
    ET.SubElement(hors, "CFirst").text = "x"     # pas de GpId : hors dialecte connu

    src = SourceXML(arbre=ET.ElementTree(racine), elements={},
                     lignes=[sain, hors], lignes_refs={})
    with caplog.at_level("WARNING", logger="circuit_analyzer.eretro_patch"):
        ecrire_groupes(src, [], None)
    messages = [rec.getMessage() for rec in caplog.records]
    # Le COMPTE est asserte, pas seulement la presence du message. D'ou les
    # DEUX fils du montage, dont un seul est hors dialecte : un
    # `manquants_fils += 1` inconditionnel dirait « 2 fil(s) » et virerait au
    # rouge, la ou un simple `any("fil" in m)` l'aurait laisse passer.
    assert any("1 fil" in m for m in messages), \
        "le message doit designer UN fil (compte juste), pas un composant"
    assert not any("2 fil" in m for m in messages), \
        "le fil dans le dialecte ne doit pas etre compte comme manquant"


def test_repatcher_sans_resultats_degroupe_aussi_les_fils(tmp_path):
    """Correction ronde 1, constat 2 : le brief justifie l'ecriture
    inconditionnelle de GpId=0 par le risque de "groupes fantomes" d'une
    analyse precedente — ce test protege cette propriete CONTRE UNE
    REGRESSION (ex. quelqu'un conditionnant un jour la boucle des fils par
    `if resultats:`). On patche d'abord AVEC des resultats (au moins un fil
    doit se grouper, garde-fou anti-test-creux), puis on repatche SANS, et on
    verifie que les fils precedemment groupes reviennent a GpId=0."""
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)

    avec = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    lignes_avec = avec.findall(".//lineL/Line")
    assert any(int(l.findtext("GpId") or 0) for l in lignes_avec), \
        "garde-fou : au moins un fil doit etre groupe a la premiere passe"

    sans = ET.fromstring(ecrire_groupes(comps.source, comps, None))
    lignes_sans = sans.findall(".//lineL/Line")
    assert {int(l.findtext("GpId") or 0) for l in lignes_sans} == {0}
    # BeIngrp n'est PLUS assert ici : on ne l'ecrit plus, donc l'exiger a
    # "false" ne prouverait que la valeur d'origine du fichier synthetique.
    # C'est `test_beingrp_n_est_jamais_touche` qui garde ce champ desormais.


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
    """Invariant central : hors GpId, l'arbre est identique — drapeaux compris."""
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


def test_un_xmlns_par_defaut_ne_produit_pas_de_xml_malforme(tmp_path):
    """Revue de branche, constat 2 : `xmlns="..."` (prefixe VIDE) devenait
    `racine.set("xmlns:", uri)`, soit un attribut litteral `xmlns:=` — du XML
    MALFORME, ecrit sur disque avec un « Succes » a l'ecran, et que plus
    personne (ni nous, ni son C#) ne pouvait relire.

    Aucune carte connue ne porte de namespace par defaut ; c'est un garde, pas
    une regression observee. Le fichier rendu doit rester RELISIBLE."""
    from circuit_analyzer.eretro_patch import ecrire_groupes
    contenu = generer_xml([Composant("R1", "R", {"1": "IN", "2": "GND"}, "10k")])
    avec_defaut = contenu.replace(
        '<BoardSCH xmlns:xsi', '<BoardSCH xmlns="urn:eretro" xmlns:xsi', 1)
    assert 'xmlns="urn:eretro"' in avec_defaut, "le montage du test a echoue"
    p = os.path.join(str(tmp_path), "ns_defaut.xml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(avec_defaut)

    comps = lire_xml(p)
    patche = ecrire_groupes(comps.source, comps, None)
    assert "xmlns:=" not in patche, "attribut xmlns: sans prefixe = XML malforme"
    ET.fromstring(patche)   # doit se reparser : c'est LA garantie qui compte


def test_un_xmlns_imbrique_ne_remonte_pas_sur_la_racine(tmp_path):
    """Revue de branche, constat 3 : la capture etait a portee DOCUMENT
    (iterparse voit tous les start-ns, a toute profondeur) mais la restitution
    a portee RACINE — un xmlns declare sur un enfant atterrissait sur
    <BoardSCH>, c'est-a-dire une ligne modifiee HORS GpId, exactement ce que le
    chantier promet de ne jamais faire."""
    from circuit_analyzer.eretro_patch import ecrire_groupes
    contenu = generer_xml([Composant("R1", "R", {"1": "IN", "2": "GND"}, "10k")])
    avec_imbrique = contenu.replace("<CmpntL>", '<CmpntL xmlns:prof="urn:profond">', 1)
    assert 'xmlns:prof' in avec_imbrique, "le montage du test a echoue"
    p = os.path.join(str(tmp_path), "ns_imbrique.xml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(avec_imbrique)

    comps = lire_xml(p)
    assert [pre for pre, _ in comps.source.namespaces] == ["xsi", "xsd"], \
        "seuls les xmlns de la BALISE RACINE doivent etre captures"
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, None))
    assert "urn:profond" not in str(racine.attrib), \
        "un xmlns d'enfant a ete remonte sur la racine"


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


def test_groupe_majoritaire_tranche_et_s_abstient_a_egalite():
    from circuit_analyzer.eretro_patch import _groupe_majoritaire
    assert _groupe_majoritaire([2, 2, 5]) == 2
    assert _groupe_majoritaire([2, 5]) == 0          # egalite -> abstention
    assert _groupe_majoritaire([0, 0, 3]) == 3       # les non-groupes ne votent pas
    assert _groupe_majoritaire([0, 0]) == 0
    assert _groupe_majoritaire([]) == 0


@pytest.mark.skipif(not os.path.isdir(_DOSSIER_REEL), reason="cartes reelles absentes")
def test_le_compose_est_groupe_sur_son_boitier_ses_entrailles_intactes():
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = os.path.join(_DOSSIER_REEL, "PowtranAlim20260809.xml")
    comps, res = _analyser(chemin)
    avant = ET.parse(chemin).getroot()
    apres = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    for cc_av, cc_ap in zip(avant.findall(".//CCmpntL/CComp"),
                            apres.findall(".//CCmpntL/CComp")):
        # Les items INTERNES ne bougent pas d'un iota, GpId compris.
        for di_av, di_ap in zip(cc_av.findall("DItemL/DataItem"),
                                cc_ap.findall("DItemL/DataItem")):
            assert (di_av.findtext("GpId") or "") == (di_ap.findtext("GpId") or "")
            assert (di_av.findtext("Begrp") or "") == (di_ap.findtext("Begrp") or "")


def test_ecrire_groupes_agrege_les_votes_d_un_compose_avant_d_ecrire(monkeypatch):
    """Renforcement (auto-revue) : sur PowtranAlim20260809.xml, les deux refs
    internes du seul compose de la carte votent pour le MEME groupe (7, 7) —
    ce cas reel ne peut donc pas distinguer la nouvelle arbitration d'un bug
    "dernier ecrit dans l'ordre du dict gagne", puisque les deux issues
    coincident. Ce test construit un compose dont les refs internes votent
    pour des groupes DIFFERENTS (2, 2, 5) : seule une vraie agregation avant
    ecriture peut produire 2, jamais 5 ni un ordre dependant du dictionnaire.
    """
    from circuit_analyzer import eretro_patch
    from circuit_analyzer.eretro import SourceXML
    from circuit_analyzer.eretro_patch import ecrire_groupes

    racine = ET.Element("BoardSCH")
    ccomp = ET.SubElement(ET.SubElement(racine, "CCmpntL"), "CComp")
    ET.SubElement(ccomp, "GpId").text = "0"
    ET.SubElement(ccomp, "Begrp").text = "false"

    # Trois refs internes du MEME compose, deux votant 2 et une votant 5.
    elements = {"U7.1": ccomp, "U7.2": ccomp, "U7.3": ccomp}
    src = SourceXML(arbre=ET.ElementTree(racine), elements=elements,
                     lignes=[], lignes_refs={})

    monkeypatch.setattr(eretro_patch, "_grouper_par_circuit", lambda comps, res: ["bloc"])
    monkeypatch.setattr(eretro_patch, "_ids_groupes_par_ref",
                         lambda blocs: {"U7.1": 2, "U7.2": 2, "U7.3": 5})

    racine_patchee = ET.fromstring(ecrire_groupes(src, [], resultats=["dummy"]))
    cc = racine_patchee.find(".//CCmpntL/CComp")
    from circuit_analyzer.eretro_patch import _gid_analyse
    assert cc.findtext("GpId") == str(_gid_analyse(2)), \
        "la majorite (2) doit l'emporter, pas le dernier ecrit (5)"
    assert cc.findtext("GpId") != str(_gid_analyse(5)), "le vote minoritaire a gagne"
    # Option A : le boitier devenant membre d'un groupe, son drapeau se leve —
    # c'est l'etat que produit son propre editeur (Form1.cs:8954).
    assert cc.findtext("Begrp") == "true", "le boitier groupe doit porter Begrp"


def test_un_element_sans_gpid_ne_recoit_rien():
    """Hors dialecte : pas de balise GpId => on n'ecrit rien, on ne cree rien.

    (Remplace `test_poser_groupe_incomplet…` : `_poser_groupe` n'existe plus,
    l'arbitrage du boss du 2026-07-30 ayant reduit l'ecriture a la seule
    balise `GpId`. Il n'y a donc plus de demi-ecriture possible.)
    """
    from circuit_analyzer.eretro_patch import _ecrire
    elem = ET.Element("DataItem")
    ET.SubElement(elem, "Begrp").text = "false"   # dialecte voisin : pas de GpId
    assert _ecrire(elem, "GpId", 3) is False
    assert elem.find("GpId") is None, "la balise ne doit jamais etre creee"
    assert elem.findtext("Begrp") == "false", "et rien d'autre ne bouge"


def test_export_analyse_est_fidele_quand_la_source_existe(tmp_path):
    """L'onglet Analyse renvoie la carte RECUE, enrichie des seuls groupes."""
    from gui.tab_analyze import _texte_export_analyse
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    xml, fidele = _texte_export_analyse(comps, res)
    assert fidele is True
    racine = ET.fromstring(xml)
    # Assertion qui DISCRIMINE reellement patch et regeneration : le
    # `findall(".//CmpntL/DataItem")` du plan serait vrai d'un XML regenere
    # aussi. Ici on exige que l'arbre rendu soit celui du FICHIER SOURCE, a
    # l'identique hors champs de groupe.
    _comparer_sauf_groupes(ET.parse(chemin).getroot(), racine)
    # ... et que les groupes aient bien ete poses, sinon « fidele » ne serait
    # qu'une copie inutile du fichier d'entree.
    assert {int(d.findtext("GpId") or 0)
            for d in racine.findall(".//CmpntL/DataItem")} != {0}


def test_export_analyse_replie_sur_le_generateur_sans_source():
    """Une liste nue (analyse partie d'un .net) n'a pas de source : on regenere."""
    from gui.tab_analyze import _texte_export_analyse
    comps = [Composant("R1", "R", {"1": "IN", "2": "GND"}, "1k")]
    xml, fidele = _texte_export_analyse(comps, None)
    assert fidele is False
    items = ET.fromstring(xml).findall(".//CmpntL/DataItem")
    # Le `findall` nu du plan serait vrai de n'importe quel BoardSCH : on
    # exige que le document REGENERE porte bien le composant qu'on a passe.
    assert "1k" in {(d.findtext("value") or "").strip() for d in items}


def _convention_fin_de_ligne(brut: bytes) -> str:
    """@brief 'CRLF' ou 'LF' d'un contenu binaire — comparable d'un OS a l'autre.

    PORTEE : compare la sortie a la SOURCE plutot que d'exiger CRLF en dur,
    donc jamais de flake hors Windows. Contrepartie a savoir — la protection
    contre un `newline=''` ajoute a l'ouverture n'est EFFECTIVE que sur
    Windows : ailleurs les deux cotes valent 'LF' avec ou sans le bug, parce
    que le bug lui-meme n'existe pas la-bas. Un CI Linux ne rattraperait donc
    pas cette regression ; c'est le poste Windows du boss qui la voit.
    """
    return "CRLF" if b"\r\n" in brut else "LF"


def _lire_octets(chemin):
    """@brief Contenu binaire d'un fichier (aucun handle laisse ouvert)."""
    with open(chemin, "rb") as f:
        return f.read()


def _piloter_export_xml(monkeypatch, comps, resultats, chemin_courant, cible):
    """@brief Joue `TabAnalyze._export_xml` sans ouvrir la moindre fenetre.

    Le selecteur de fichier et les trois boites de dialogue sont remplaces par
    des mouchards, et `self` par un objet minimal portant les seuls attributs
    que la methode lit. On exerce ainsi le VRAI chemin de l'appli — y compris
    le `open(..., "w")` en mode texte, responsable de la convention de fin de
    ligne — sans dependre d'un affichage Tk.

    @return list des (genre, message) affiches, dans l'ordre.
    """
    import gui.tab_analyze as ta
    monkeypatch.setattr(ta.filedialog, "asksaveasfilename", lambda **kw: cible)
    vus = []
    for genre in ("info", "warning", "error"):
        monkeypatch.setattr(ta.messagebox, f"show{genre}",
                            lambda titre, msg, _g=genre: vus.append((_g, msg)))
    ta.TabAnalyze._export_xml(SimpleNamespace(
        _comps=comps, _results=resultats,
        _file_path=SimpleNamespace(get=lambda: chemin_courant)))
    return vus


def test_le_repli_est_annonce_a_l_utilisateur(tmp_path, monkeypatch):
    """Le repli ne doit JAMAIS etre silencieux : c'est le defaut qu'on corrige.

    Un utilisateur a qui l'on rend un schema REDESSINE (positions, symboles et
    zooms inventes) sans le lui dire croira tenir sa carte d'origine. On verifie
    donc que ce chemin passe par showwarning, pas par le showinfo du succes.
    """
    cible = os.path.join(str(tmp_path), "sortie.xml")
    vus = _piloter_export_xml(
        monkeypatch, [Composant("R1", "R", {"1": "IN", "2": "GND"}, "1k")],
        None, "", cible)
    assert [genre for genre, _ in vus] == ["warning"], \
        "le repli sur le generateur doit alerter, jamais annoncer un simple succes"
    assert "REDESSIN" in vus[0][1].upper(), "l'alerte doit dire que le schema a ete redessine"
    assert os.path.isfile(cible), "le fichier doit tout de meme etre ecrit"


def test_export_fidele_annonce_la_carte_conservee(tmp_path, monkeypatch):
    """Pendant fidele du test precedent : succes annonce, aucune alerte."""
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    cible = os.path.join(str(tmp_path), "sortie.xml")
    vus = _piloter_export_xml(monkeypatch, comps, res, chemin, cible)
    assert [genre for genre, _ in vus] == ["info"]
    # Le CONTENU, pas seulement le genre : la garde « Analysez d'abord un
    # circuit » de _export_xml affiche elle aussi un showinfo, et satisferait
    # un `== ["info"]` nu. Symetrique de l'assertion "REDESSIN" du jumeau.
    assert "origine" in vus[0][1].lower(), \
        "le succes doit annoncer que la carte d'origine est conservee"

    brut = _lire_octets(cible)
    # Le fichier ecrit par le VRAI chemin de l'appli doit rester fidele : c'est
    # le mode texte de `open(..., "w")` qui retraduit les LF de `ecrire_groupes`
    # en CRLF. Un `newline=""` ajoute la-bas le sortirait en LF nu.
    assert b"\r\r\n" not in brut, "fin de ligne doublee : fichier malforme"
    assert _convention_fin_de_ligne(brut) == _convention_fin_de_ligne(_lire_octets(chemin)), \
        "la carte rendue doit garder la convention de fin de ligne de la source " \
        "(un newline='' a l'ouverture la sortirait en LF nu)"
    _comparer_sauf_groupes(ET.parse(chemin).getroot(), ET.fromstring(brut.decode("utf-8")))


# Option A du boss (2026-07-31) : on ecrit de VRAIS groupes, donc les drapeaux
# d'appartenance rejoignent GpId. L'ensemble reste volontairement ETROIT — tout
# autre champ modifie doit faire rougir l'invariance sur les 4 vraies cartes.
_CHAMPS_GROUPE = {"GpId", "Begrp", "BeIngrp"}

#: Seule BRANCHE que le patch a le droit d'ajouter (elle n'existe dans aucune
#: des 4 cartes reelles). Elle est verifiee par test_eretro_groupes_reels.py ;
#: ici on l'ecarte pour que la comparaison prouve que RIEN d'autre ne bouge.
_BRANCHE_AJOUTEE = "GrpL"


def test_appliquer_deltas_translate_ctriem_et_lextremite_du_fil_touchee(tmp_path):
    """@brief Un ref avec un delta voit son CtrIem ET l'extremite de fil qui le
    touche decales du meme montant. L'AUTRE extremite (composant non deplace)
    reste intacte."""
    from circuit_analyzer.eretro_patch import _appliquer_deltas

    comps = [
        Composant("R1", "R", {"1": "N1", "2": "N2"}),
        Composant("R2", "R", {"1": "N2", "2": "N3"}),
    ]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, _ = _analyser(chemin)
    source = lus.source

    x_avant = float(source.elements["R1"].find("CtrIem/X").text)
    y_avant = float(source.elements["R1"].find("CtrIem/Y").text)
    x2_avant = float(source.elements["R2"].find("CtrIem/X").text)

    # Le fil entre R1 et R2 (les deux refs connues du pont) : capte SES
    # PointF AVANT translation pour comparer apres.
    idx_fil = next(i for i, (ra, rb) in source.lignes_refs.items()
                   if {ra, rb} == {"R1", "R2"})
    points_avant = [(float(p.findtext("X")), float(p.findtext("Y")))
                    for p in source.lignes[idx_fil].findall("LP/PointF")]

    _appliquer_deltas(source, {"R1": (50.0, -30.0)})

    assert float(source.elements["R1"].find("CtrIem/X").text) == x_avant + 50.0
    assert float(source.elements["R1"].find("CtrIem/Y").text) == y_avant - 30.0
    # R2 n'a pas de delta : son CtrIem est intact.
    assert float(source.elements["R2"].find("CtrIem/X").text) == x2_avant

    points_apres = [(float(p.findtext("X")), float(p.findtext("Y")))
                    for p in source.lignes[idx_fil].findall("LP/PointF")]
    # Exactement UNE extremite a bouge de (50, -30), l'autre est intacte.
    deltas_observes = sorted(
        (round(ax - bx, 6), round(ay - by, 6))
        for (ax, ay), (bx, by) in zip(points_apres, points_avant))
    assert deltas_observes == sorted([(0.0, 0.0), (50.0, -30.0)])


def test_appliquer_deltas_avec_deltas_differents_aux_deux_extremites(tmp_path):
    """@brief Finding 1 : un fil dont les DEUX extremites sont dans deltas avec
    des valeurs DIFFERENTES voit chaque bout se decaler PAR SON PROPRE delta,
    independemment. Teste le cas du fil interne au groupe."""
    from circuit_analyzer.eretro_patch import _appliquer_deltas

    comps = [
        Composant("R1", "R", {"1": "N1", "2": "N2"}),
        Composant("R2", "R", {"1": "N2", "2": "N3"}),
        Composant("R3", "R", {"1": "N3", "2": "GND"}),
    ]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, _ = _analyser(chemin)
    source = lus.source

    # Capture l'etat AVANT pour comparer apres.
    r1_x_avant = float(source.elements["R1"].find("CtrIem/X").text)
    r1_y_avant = float(source.elements["R1"].find("CtrIem/Y").text)
    r2_x_avant = float(source.elements["R2"].find("CtrIem/X").text)
    r2_y_avant = float(source.elements["R2"].find("CtrIem/Y").text)

    # Le fil entre R1 et R2 : capte SES PointF AVANT translation.
    idx_fil_r1_r2 = next(i for i, (ra, rb) in source.lignes_refs.items()
                         if {ra, rb} == {"R1", "R2"})
    points_r1_r2_avant = [(float(p.findtext("X")), float(p.findtext("Y")))
                          for p in source.lignes[idx_fil_r1_r2].findall("LP/PointF")]

    # Le fil entre R2 et R3 : capte SES PointF AVANT translation.
    idx_fil_r2_r3 = next(i for i, (ra, rb) in source.lignes_refs.items()
                         if {ra, rb} == {"R2", "R3"})
    points_r2_r3_avant = [(float(p.findtext("X")), float(p.findtext("Y")))
                          for p in source.lignes[idx_fil_r2_r3].findall("LP/PointF")]

    # Appliquer deux deltas DIFFERENTS : R1 et R2 ne bougent PAS du meme montant.
    deltas = {"R1": (10.0, 20.0), "R2": (30.0, 40.0)}
    _appliquer_deltas(source, deltas)

    # Verifie que R1 et R2 ont chacun bouge de son propre delta.
    assert float(source.elements["R1"].find("CtrIem/X").text) == r1_x_avant + 10.0
    assert float(source.elements["R1"].find("CtrIem/Y").text) == r1_y_avant + 20.0
    assert float(source.elements["R2"].find("CtrIem/X").text) == r2_x_avant + 30.0
    assert float(source.elements["R2"].find("CtrIem/Y").text) == r2_y_avant + 40.0

    # Le fil R1-R2 : son premier PointF (R1 side) doit avoir bouge de (10, 20),
    # son dernier (R2 side) doit avoir bouge de (30, 40) — des MONTANTS
    # DIFFERENTS, exactement ce qu'on teste ici.
    points_r1_r2_apres = [(float(p.findtext("X")), float(p.findtext("Y")))
                          for p in source.lignes[idx_fil_r1_r2].findall("LP/PointF")]
    delta_r1_side = (
        round(points_r1_r2_apres[0][0] - points_r1_r2_avant[0][0], 6),
        round(points_r1_r2_apres[0][1] - points_r1_r2_avant[0][1], 6)
    )
    delta_r2_side = (
        round(points_r1_r2_apres[-1][0] - points_r1_r2_avant[-1][0], 6),
        round(points_r1_r2_apres[-1][1] - points_r1_r2_avant[-1][1], 6)
    )
    assert delta_r1_side == (10.0, 20.0), \
        f"extremite R1 du fil R1-R2 doit bouger de (10, 20), pas {delta_r1_side}"
    assert delta_r2_side == (30.0, 40.0), \
        f"extremite R2 du fil R1-R2 doit bouger de (30, 40), pas {delta_r2_side}"

    # Le fil R2-R3 : son premier PointF (R2 side) doit avoir bouge de (30, 40),
    # son dernier (R3 side) reste inchange (R3 n'a pas de delta).
    points_r2_r3_apres = [(float(p.findtext("X")), float(p.findtext("Y")))
                          for p in source.lignes[idx_fil_r2_r3].findall("LP/PointF")]
    delta_r2_r3_side = (
        round(points_r2_r3_apres[0][0] - points_r2_r3_avant[0][0], 6),
        round(points_r2_r3_apres[0][1] - points_r2_r3_avant[0][1], 6)
    )
    delta_r3_r2_side = (
        round(points_r2_r3_apres[-1][0] - points_r2_r3_avant[-1][0], 6),
        round(points_r2_r3_apres[-1][1] - points_r2_r3_avant[-1][1], 6)
    )
    assert delta_r2_r3_side == (30.0, 40.0), \
        f"extremite R2 du fil R2-R3 doit bouger de (30, 40), pas {delta_r2_r3_side}"
    assert delta_r3_r2_side == (0.0, 0.0), \
        f"extremite R3 du fil R2-R3 ne doit pas bouger, pas {delta_r3_r2_side}"


def test_decaler_point_ecrit_des_entiers_pas_des_floats():
    """@brief Finding 2 : _decaler_point doit ecrire des entiers, pas des floats,
    car l'XmlSerializer C# les deserialize en int et rejette "1250.0"."""
    from circuit_analyzer.eretro_patch import _decaler_point
    point = ET.Element("PointF")
    ET.SubElement(point, "X").text = "1200"
    ET.SubElement(point, "Y").text = "800"

    _decaler_point(point, (50.0, -30.0))

    x_texte = point.find("X").text
    y_texte = point.find("Y").text
    # Les TEXTES doivent etre des entiers, pas des floats.
    assert x_texte == "1250", f"X doit etre '1250', pas '{x_texte}'"
    assert y_texte == "770", f"Y doit etre '770', pas '{y_texte}'"
    # Verifie que ce ne sont PAS des floats (pas de point decimal).
    assert "." not in x_texte, f"X ne doit pas avoir de point decimal : '{x_texte}'"
    assert "." not in y_texte, f"Y ne doit pas avoir de point decimal : '{y_texte}'"


def test_decaler_point_arrondit_les_deltas_non_entiers():
    """@brief Finding 2 (extension) : si le delta est non-entier, on arrondit."""
    from circuit_analyzer.eretro_patch import _decaler_point
    point = ET.Element("PointF")
    ET.SubElement(point, "X").text = "1200"
    ET.SubElement(point, "Y").text = "800"

    _decaler_point(point, (50.7, -30.3))

    x_texte = point.find("X").text
    y_texte = point.find("Y").text
    # Arrondir 1200 + 50.7 = 1250.7 donne 1251 (round vers pair)
    # Arrondir 800 - 30.3 = 769.7 donne 770
    assert x_texte == "1251", f"X doit etre arrondi a '1251', pas '{x_texte}'"
    assert y_texte == "770", f"Y doit etre arrondi a '770', pas '{y_texte}'"


def test_decaler_point_failsoft_avec_pointf_malformee():
    """@brief Finding 3 : _decaler_point ne leve JAMAIS si la structure est
    malforme (X ou Y manquants, ou contenu non-numerique). C'est un no-op."""
    from circuit_analyzer.eretro_patch import _decaler_point

    # Cas 1 : X manquant
    point_sans_x = ET.Element("PointF")
    ET.SubElement(point_sans_x, "Y").text = "100"
    _decaler_point(point_sans_x, (10.0, 20.0))  # ne doit pas lever
    assert point_sans_x.findtext("Y") == "100", "Y ne doit pas changer si X est absent"

    # Cas 2 : Y manquant
    point_sans_y = ET.Element("PointF")
    ET.SubElement(point_sans_y, "X").text = "100"
    _decaler_point(point_sans_y, (10.0, 20.0))  # ne doit pas lever
    assert point_sans_y.findtext("X") == "100", "X ne doit pas changer si Y est absent"

    # Cas 3 : X non-numerique
    point_nan_x = ET.Element("PointF")
    ET.SubElement(point_nan_x, "X").text = "abc"
    ET.SubElement(point_nan_x, "Y").text = "100"
    _decaler_point(point_nan_x, (10.0, 20.0))  # ne doit pas lever
    assert point_nan_x.findtext("X") == "abc", "X ne doit pas changer si non-numerique"
    assert point_nan_x.findtext("Y") == "100", "Y ne doit pas changer si X est mauvais"

    # Cas 4 : Y non-numerique
    point_nan_y = ET.Element("PointF")
    ET.SubElement(point_nan_y, "X").text = "100"
    ET.SubElement(point_nan_y, "Y").text = "xyz"
    _decaler_point(point_nan_y, (10.0, 20.0))  # ne doit pas lever
    assert point_nan_y.findtext("X") == "100", "X ne doit pas changer si Y est mauvais"
    assert point_nan_y.findtext("Y") == "xyz", "Y ne doit pas changer si non-numerique"

    # Cas 5 : PointF completement vide
    point_vide = ET.Element("PointF")
    _decaler_point(point_vide, (10.0, 20.0))  # ne doit pas lever
    assert len(list(point_vide)) == 0, "un PointF vide doit rester vide"


def test_ecrire_groupes_deplace_lampli_inverseur_vers_sa_disposition_canonique(tmp_path):
    """@brief Bout en bout : un ampli inverseur reconnu sur une carte "scannee"
    (chemin ecrire_groupes) est translate vers sa disposition canonique."""
    from circuit_analyzer.eretro_patch import ecrire_groupes

    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Composant("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Composant("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, res = _analyser(chemin)
    positions_avant = {
        ref: (float(el.find("CtrIem/X").text), float(el.find("CtrIem/Y").text))
        for ref, el in lus.source.elements.items()
    }

    xml_patche = ecrire_groupes(lus.source, lus, res)
    racine = ET.fromstring(xml_patche)
    positions_apres = {
        item.findtext("reference"):
            (float(item.find("CtrIem/X").text), float(item.find("CtrIem/Y").text))
        for item in racine.findall(".//CmpntL/DataItem")
    }

    # Les 3 composants de l'ampli inverseur ont bouge (ou sont deja canoniques,
    # peu probable ici mais pas garanti faux) — au moins un a bouge.
    assert any(positions_avant[ref] != positions_apres[ref] for ref in ("U1", "R1", "R2"))


def test_ecrire_groupes_ne_deplace_jamais_un_montage_non_migre(tmp_path):
    """@brief Garde-fou : un montage SANS positionneur canonique (ex. suiveur
    de tension) garde ses positions reelles intactes, seul le groupage s'applique."""
    from circuit_analyzer.eretro_patch import ecrire_groupes

    comps = [
        Composant("U1", "U", {"IN+": "N1", "IN-": "N2", "OUT": "N2"}),
    ]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, res = _analyser(chemin)
    x_avant = float(lus.source.elements["U1"].find("CtrIem/X").text)
    y_avant = float(lus.source.elements["U1"].find("CtrIem/Y").text)

    xml_patche = ecrire_groupes(lus.source, lus, res)
    racine = ET.fromstring(xml_patche)
    item = next(i for i in racine.findall(".//CmpntL/DataItem")
                if i.findtext("reference") == "U1")
    assert float(item.find("CtrIem/X").text) == x_avant
    assert float(item.find("CtrIem/Y").text) == y_avant


def test_ecrire_groupes_preserve_la_connectivite_apres_translation(tmp_path):
    """@brief Contrainte dure : la translation ne change AUCUNE connexion —
    reparse le resultat et confirme que l'ampli inverseur est toujours detecte
    avec les memes composants."""
    from circuit_analyzer.xml import lire_xml
    from circuit_analyzer.eretro_patch import ecrire_groupes

    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Composant("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Composant("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, res = _analyser(chemin)
    xml_patche = ecrire_groupes(lus.source, lus, res)

    chemin_patche = os.path.join(str(tmp_path), "patche.xml")
    with open(chemin_patche, "w", encoding="utf-8") as f:
        f.write(xml_patche)
    relu, res_relu = _analyser(chemin_patche)
    types_relu = sorted(r["circuit_type"] for r in res_relu)
    assert "Amplificateur inverseur (AOP)" in types_relu
    assert {c.ref for c in relu} == {"U1", "R1", "R2"}


def _comparer_sauf_groupes(a, b, chemin="/"):
    """@brief Egalite RECURSIVE de deux arbres, hors champs de groupe.

    Compare la structure (tag, ordre, nombre d'enfants), le texte et les
    attributs. On compare arbre a arbre et NON octet a octet : ElementTree
    re-serialise tout le document (balises auto-fermantes, espaces), un diff
    textuel serait rouge en permanence et donc jamais relu.
    """
    assert a.tag == b.tag, f"{chemin} : {a.tag} != {b.tag}"
    assert a.attrib == b.attrib, f"{chemin}{a.tag} : attributs modifies"
    ea = [x for x in a if x.tag != _BRANCHE_AJOUTEE]
    eb = [x for x in b if x.tag != _BRANCHE_AJOUTEE]
    assert [x.tag for x in ea] == [x.tag for x in eb], \
        f"{chemin}{a.tag} : enfants ajoutes, retires ou reordonnes"
    if a.tag not in _CHAMPS_GROUPE:
        assert (a.text or "").strip() == (b.text or "").strip(), \
            f"{chemin}{a.tag} : texte modifie"
    for i, (x, y) in enumerate(zip(ea, eb)):
        _comparer_sauf_groupes(x, y, f"{chemin}{a.tag}[{i}]/")
