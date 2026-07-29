"""@file eretro_patch.py
@brief Ecrit les groupes d'analyse DANS le fichier BoardSCH d'origine.

Contrat unique et non negociable : on MODIFIE des balises existantes, on n'en
cree, ne deplace ni ne supprime aucune. Tout ce qu'on ne comprend pas du format
(et il en reste) ressort donc intact, par construction.

Ne pas confondre avec `generer_xml`, qui FABRIQUE un document depuis une
netlist : lui reinvente positions, formes et zooms, ce qui est correct pour un
schema cree chez nous et destructeur pour une carte recue.
"""
import logging
import xml.etree.ElementTree as ET

from circuit_analyzer.xml import _grouper_par_circuit, _ids_groupes_par_ref

_log = logging.getLogger(__name__)


def _ecrire(element, balise, valeur):
    """@brief Ecrit une balise SI elle existe deja. Renvoie False sinon.

    Refus delibere de creer la balise manquante : l'XmlSerializer C# est
    sensible a l'ORDRE des elements d'une sequence, et on ne connait pas
    l'ordre attendu. Les 4 cartes reelles portent GpId/Begrp/BeIngrp sur 100 %
    de leurs elements — un manque signale un fichier hors dialecte, pas un cas
    a rattraper en devinant.
    """
    cible = element.find(balise)
    if cible is None:
        return False
    cible.text = str(valeur)
    return True


def _poser_groupe(element, gid, balise_drapeau):
    """@brief Pose GpId + son drapeau compagnon sur un element du fichier.

    Le retour depend des DEUX ecritures : un element qui porte GpId mais pas
    son drapeau (ou l'inverse) est un element partiellement hors dialecte, pas
    un succes a moitie silencieux — sinon `manquants` sous-compte et le
    drapeau peut rester incoherent avec un GpId pourtant mis a jour.
    """
    ok_gid = _ecrire(element, "GpId", gid)
    ok_drapeau = _ecrire(element, balise_drapeau, "true" if gid else "false")
    return ok_gid and ok_drapeau


def ecrire_groupes(source, composants, resultats=None) -> str:
    """@brief Renvoie le XML d'origine, enrichi des groupes d'analyse.

    @param source SourceXML publiee par lire_xml (arbre + pont ref->element).
    @param composants Composants analyses (le retour de lire_xml).
    @param resultats Sortie de detecteur.match_patterns, ou None (aucun groupe).
    @return str Document BoardSCH patche.
    """
    blocs = _grouper_par_circuit(composants, resultats) if resultats else []
    gid_par_ref = _ids_groupes_par_ref(blocs) if blocs else {}

    manquants = 0
    for ref, element in source.elements.items():
        if not _poser_groupe(element, gid_par_ref.get(ref, 0), "Begrp"):
            manquants += 1
    if manquants:
        _log.warning("%d element(s) sans balise GpId : groupe non ecrit "
                     "(fichier hors dialecte BoardSCH connu)", manquants)

    return _serialiser_avec_entete(source)


def _serialiser_avec_entete(source) -> str:
    """@brief Serialise l'arbre en restituant le prologue et les xmlns d'origine.

    ET.parse() ne conserve ni le prologue `<?xml ...?>` ni les declarations
    `xmlns:*` qui ne qualifient aucun tag (comportement documente de
    xml.etree.ElementTree, contrairement a lxml) : lire_xml les a donc captes
    a part, en texte brut, dans SourceXML.avant_racine/.namespaces. On les
    repose ici plutot que de laisser ET.tostring() fabriquer un prologue
    generique (guillemets simples, xmlns disparus) qui ne serait plus le
    fichier du collegue.

    Un fichier sans namespace ni prologue (namespaces=[], avant_racine="",
    ex. arbre construit a la main dans les tests) ne fabrique rien : on
    retombe alors sur le tostring() nu, comportement inchange.
    """
    racine = source.arbre.getroot()
    # Mutation DELIBEREE de l'arbre partage : on repose les xmlns:* comme de
    # simples attributs litteraux pour qu'ET.tostring() les fasse ressortir
    # dans la balise racine. C'est une AFFECTATION (racine.set), pas un ajout
    # cumulatif : appeler ecrire_groupes plusieurs fois de suite reecrit les
    # memes cles avec les memes valeurs, donc idempotent par construction.
    for prefixe, uri in source.namespaces:
        racine.set(f"xmlns:{prefixe}", uri)

    corps = ET.tostring(racine, encoding="unicode")
    return source.avant_racine + corps if source.avant_racine else corps
