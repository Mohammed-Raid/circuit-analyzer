"""@file test_retour_fidele_cartes.py
@brief Le fichier d'un collegue revient intact, aux groupes pres (4 vraies cartes).

Filet de securite du chantier « retour fidele ERetroDesign ». Deux niveaux :

1. Niveau ARBRE (`ET`) — structure, textes, attributs hors champs de groupe.
2. Niveau OCTET (`rb`) — prologue, declarations `xmlns:*`, fins de ligne.

Le niveau 2 n'est PAS un doublon du 1 : un `ElementTree` ne contient ni le
prologue `<?xml ...?>`, ni les `xmlns:*` qui ne qualifient aucun tag, ni la
convention de fin de ligne. Ce sont exactement les trois defauts qui ont coute
trois rondes de correction a la Task 2 sans qu'aucun test d'arbre ne vire au
rouge. On lit donc aussi le fichier REELLEMENT ECRIT sur disque, en binaire,
par le meme `open(..., "w", encoding="utf-8")` que `gui/tab_analyze.py`.
"""
import os
import xml.etree.ElementTree as ET

import pytest

from circuit_analyzer.xml import lire_xml
from circuit_analyzer.eretro_patch import ecrire_groupes
from tests.test_eretro_patch import (
    _comparer_sauf_groupes, _convention_fin_de_ligne, _lire_octets)

_DOSSIER = "CARTE POUR TESTER (VRAI TEST)"
_FICHIERS = ["PG 2.xml", "PG 3.xml", "PowtranAlim20260809.xml", "pg carte.xml"]

#: Balises dont la VALEUR a le droit de changer : c'est tout l'apport du patch.
_LIGNES_DE_GROUPE = ("GpId", "Begrp", "BeIngrp")

pytestmark = pytest.mark.skipif(
    not os.path.isdir(_DOSSIER), reason="cartes reelles absentes")


def _patcher(fichier):
    """@brief Chaine complete : lecture -> analyse -> patch, sur une vraie carte."""
    from circuit_analyzer.graph_builder import build_graph
    from circuit_analyzer.matcher import match_patterns
    chemin = os.path.join(_DOSSIER, fichier)
    comps = lire_xml(chemin)
    res = match_patterns(build_graph(comps))
    return chemin, comps, ecrire_groupes(comps.source, comps, res)


def _ecrire_comme_l_appli(texte, cible):
    """@brief Reproduit a l'identique l'ecriture de `gui/tab_analyze.py`.

    Mode TEXTE, sans `newline=""` : c'est ce mode qui retraduit les '\\n' de
    `ecrire_groupes` en '\\r\\n' sur Windows et restitue le CRLF de la source.
    Toute la classe de defauts « fin de ligne » ne se voit que par ce chemin ;
    ecrire en binaire dans le test la rendrait invisible.
    """
    with open(cible, "w", encoding="utf-8") as f:
        f.write(texte)
    return cible


def _premiere_ligne(brut):
    """@brief Prologue XML : tout ce qui precede la premiere fin de ligne."""
    return brut.split(b"\n", 1)[0].rstrip(b"\r")


def _balise_racine_ouvrante(brut):
    """@brief `<BoardSCH ...>` complet, jusqu'au '>' inclus — porte les xmlns:*."""
    debut = brut.index(b"<BoardSCH")
    return brut[debut:brut.index(b">", debut) + 1]


def _lignes_physiques(brut):
    """@brief Lignes du fichier, fins de ligne otees (CRLF comme LF)."""
    return brut.replace(b"\r\n", b"\n").split(b"\n")


def _est_une_ligne_de_groupe(ligne):
    """@brief Vrai si la ligne ne porte qu'une balise GpId/Begrp/BeIngrp."""
    nue = ligne.strip()
    return any(nue.startswith(b"<%s>" % b.encode()) for b in _LIGNES_DE_GROUPE)


# --------------------------------------------------------------------------
# Niveau ARBRE
# --------------------------------------------------------------------------

@pytest.mark.parametrize("fichier", _FICHIERS)
def test_invariance_hors_groupes(fichier):
    chemin, _comps, xml = _patcher(fichier)
    _comparer_sauf_groupes(ET.parse(chemin).getroot(), ET.fromstring(xml))


def test_le_corpus_contient_bien_une_puce_composee():
    """Garde-fou anti-test-creux du test suivant : une seule des 4 cartes porte
    un `<CComp>` (PowtranAlim). Si ce cas venait a disparaitre du corpus, la
    boucle `CComp` de `test_positions_angles_et_zooms_mot_pour_mot` tournerait
    a vide sur les 4 cartes sans que personne ne le remarque."""
    total = sum(len(ET.parse(os.path.join(_DOSSIER, f)).getroot().findall(".//CComp"))
                for f in _FICHIERS)
    assert total, "aucune carte du corpus ne porte de puce composee"


@pytest.mark.parametrize("fichier", _FICHIERS)
def test_positions_angles_et_zooms_mot_pour_mot(fichier):
    """Garde-fou EXPLICITE sur les champs que l'ancien export detruisait.

    Trois durcissements par rapport au plan, chacun bouchant un trou par lequel
    ce test resterait vert en presence d'un vrai defaut :
    - les LONGUEURS sont assertees (un `zip` nu s'arrete au plus court : perdre
      la moitie des `DataItem` passerait inapercu) ;
    - la PRESENCE de chaque champ est assertee (`findtext` renvoyant None des
      deux cotes rend l'assertion vacue — un tag mal orthographie ne testerait
      plus rien) ;
    - une boite absente d'un cote et presente de l'autre est une erreur, la ou
      le `if ea is not None:` du plan sautait silencieusement le cas.
    """
    chemin, _comps, xml = _patcher(fichier)
    avant, apres = ET.parse(chemin).getroot(), ET.fromstring(xml)
    for tag in ("DataItem", "CComp"):
        ea, eb = list(avant.iter(tag)), list(apres.iter(tag))
        assert len(ea) == len(eb), \
            f"{fichier} : {len(ea)} <{tag}> avant, {len(eb)} apres"
        for a, b in zip(ea, eb):
            for champ in ("angle", "zmH", "zmV", "Flip", "typ", "Name", "value"):
                assert a.find(champ) is not None, \
                    f"{fichier} : <{tag}> sans <{champ}> — assertion vacue"
                assert (a.findtext(champ) or "") == (b.findtext(champ) or ""), \
                    f"{fichier} : {tag}/{champ} modifie"
            for boite in ("CtrIem", "TL", "BR"):
                ba, bb = a.find(boite), b.find(boite)
                assert ba is not None, \
                    f"{fichier} : <{tag}> sans <{boite}> — assertion vacue"
                assert bb is not None, f"{fichier} : {tag}/{boite} disparu"
                coins = [(c.tag, c.text) for c in ba]
                assert coins, f"{fichier} : {tag}/{boite} vide — assertion vacue"
                assert coins == [(c.tag, c.text) for c in bb], \
                    f"{fichier} : {tag}/{boite} modifie"


@pytest.mark.parametrize("fichier", _FICHIERS)
def test_netlist_stable_apres_patch(fichier, tmp_path):
    """Un NodeL casse changerait la connexite : ce test le verrait."""
    chemin, comps, xml = _patcher(fichier)
    p = _ecrire_comme_l_appli(xml, os.path.join(str(tmp_path), "patche.xml"))
    relu = lire_xml(p)
    assert comps, "garde-fou : la carte doit porter des composants"
    assert [(c.ref, c.type, c.value) for c in relu] == \
           [(c.ref, c.type, c.value) for c in comps]
    assert [c.pins for c in relu] == [c.pins for c in comps]


@pytest.mark.parametrize("fichier", _FICHIERS)
def test_le_patch_est_idempotent(fichier, tmp_path):
    """Deux passes donnent le meme fichier : pas de groupe fantome accumule."""
    from circuit_analyzer.graph_builder import build_graph
    from circuit_analyzer.matcher import match_patterns
    _chemin, _comps, xml1 = _patcher(fichier)
    p = _ecrire_comme_l_appli(xml1, os.path.join(str(tmp_path), "p1.xml"))
    c2 = lire_xml(p)
    xml2 = ecrire_groupes(c2.source, c2, match_patterns(build_graph(c2)))

    # Chaque document n'est parse QU'UNE fois : le plan appelait `fromstring`
    # trois fois de suite, ce qui rendait difficile de voir que la boucle des
    # GpId comparait bien les memes documents que la comparaison d'arbres.
    racine1, racine2 = ET.fromstring(xml1), ET.fromstring(xml2)
    _comparer_sauf_groupes(racine1, racine2)

    g1 = [(e.text or "") for e in racine1.iter("GpId")]
    g2 = [(e.text or "") for e in racine2.iter("GpId")]
    assert len(g1) == len(g2), \
        f"{fichier} : {len(g1)} <GpId> a la passe 1, {len(g2)} a la passe 2"
    # Sans ce garde-fou, deux listes de GpId toutes a "0" satisferaient
    # l'egalite ci-dessous : l'idempotence serait alors celle du neant.
    assert any(g not in ("", "0") for g in g1), \
        f"{fichier} : aucun groupe ecrit, l'idempotence ne prouverait rien"
    assert g1 == g2


# --------------------------------------------------------------------------
# Niveau OCTET — ce dont les arbres sont aveugles
# --------------------------------------------------------------------------

@pytest.mark.parametrize("fichier", _FICHIERS)
def test_entete_et_fins_de_ligne_a_l_octet_pres(fichier, tmp_path):
    """Prologue, `xmlns:*` et convention de fin de ligne, sur le fichier ECRIT.

    Aucun de ces trois points n'existe dans un `ElementTree` : les quatre tests
    ci-dessus resteraient tous verts avec un prologue perdu, des `xmlns:*`
    evapores ou des '\\r\\r\\n' plein le fichier. On compare donc les octets.
    """
    chemin, _comps, xml = _patcher(fichier)
    recu = _lire_octets(
        _ecrire_comme_l_appli(xml, os.path.join(str(tmp_path), "recu.xml")))
    source = _lire_octets(chemin)

    assert _premiere_ligne(recu) == _premiere_ligne(source), \
        f"{fichier} : prologue <?xml ...?> altere"
    assert b"xmlns:" in _balise_racine_ouvrante(source), \
        f"{fichier} : la source n'a pas de xmlns — assertion suivante vacue"
    assert _balise_racine_ouvrante(recu) == _balise_racine_ouvrante(source), \
        f"{fichier} : declarations xmlns de <BoardSCH> alterees"

    assert b"\r\r\n" not in recu, f"{fichier} : fin de ligne CRLF doublee"
    assert _convention_fin_de_ligne(recu) == _convention_fin_de_ligne(source), \
        f"{fichier} : convention de fin de ligne changee"
    # Les 4 cartes sont a 100 % CRLF : on exige le MEME compte, et zero LF nu.
    # Un simple `in` ne verrait pas un fichier a moitie converti.
    crlf_source, crlf_recu = source.count(b"\r\n"), recu.count(b"\r\n")
    assert crlf_recu == crlf_source, \
        f"{fichier} : {crlf_source} CRLF en entree, {crlf_recu} en sortie"
    assert recu.count(b"\n") - recu.count(b"\r\n") == \
        source.count(b"\n") - source.count(b"\r\n"), \
        f"{fichier} : des fins de ligne LF nues sont apparues"


@pytest.mark.parametrize("fichier", _FICHIERS)
def test_seules_les_lignes_de_groupe_different_a_l_octet_pres(fichier, tmp_path):
    """LA preuve de la promesse faite au collegue, sans intermediaire.

    Les comparaisons d'arbres tolerent par construction toute difference que le
    parseur absorbe (balises auto-fermantes, indentation, guillemets, entites).
    Ici on compare le fichier RENDU au fichier RECU, ligne physique par ligne
    physique : la seule difference autorisee est la valeur d'une balise
    GpId/Begrp/BeIngrp. Tout le reste — a la virgule — doit etre identique.
    """
    chemin, _comps, xml = _patcher(fichier)
    recu = _lignes_physiques(_lire_octets(
        _ecrire_comme_l_appli(xml, os.path.join(str(tmp_path), "recu.xml"))))
    source = _lignes_physiques(_lire_octets(chemin))

    assert len(recu) == len(source), \
        f"{fichier} : {len(source)} lignes recues, {len(recu)} rendues"
    differentes = [(n, a, b) for n, (a, b) in enumerate(zip(source, recu), 1) if a != b]
    hors_groupe = [t for t in differentes if not _est_une_ligne_de_groupe(t[1])]
    assert not hors_groupe, \
        f"{fichier} : le patch a modifie des lignes hors groupe, " \
        f"ex. ligne {hors_groupe[0][0]} : {hors_groupe[0][1]!r} -> {hors_groupe[0][2]!r}"
    assert differentes, f"{fichier} : aucun groupe ecrit — le test ne prouve rien"


@pytest.mark.parametrize("fichier", _FICHIERS)
def test_le_patch_est_idempotent_a_l_octet_pres(fichier, tmp_path):
    """Complement octet de `test_le_patch_est_idempotent`.

    L'egalite des arbres et des GpId ne dirait rien d'un prologue qui se
    dupliquerait ou de `xmlns:*` qui s'accumuleraient a chaque passe — or c'est
    precisement ce que `_serialiser_avec_entete` repose a la main sur l'arbre
    partage a chaque appel. Deux passes doivent rendre les MEMES octets.
    """
    from circuit_analyzer.graph_builder import build_graph
    from circuit_analyzer.matcher import match_patterns
    _chemin, _comps, xml1 = _patcher(fichier)
    p1 = _ecrire_comme_l_appli(xml1, os.path.join(str(tmp_path), "p1.xml"))
    c2 = lire_xml(p1)
    xml2 = ecrire_groupes(c2.source, c2, match_patterns(build_graph(c2)))
    p2 = _ecrire_comme_l_appli(xml2, os.path.join(str(tmp_path), "p2.xml"))
    assert _lire_octets(p2) == _lire_octets(p1), \
        f"{fichier} : la seconde passe ne rend pas les memes octets"
