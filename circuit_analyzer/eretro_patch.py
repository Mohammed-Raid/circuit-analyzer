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
from collections import Counter

from circuit_analyzer.xml import _grouper_par_circuit, _ids_groupes_par_ref

_log = logging.getLogger(__name__)


def _groupe_majoritaire(gids) -> int:
    """@brief Groupe d'une puce composee, a la majorite de ses composants internes.

    Les gids nuls (composants non classes) ne votent pas. A EGALITE, on
    s'abstient : mieux vaut une puce non groupee qu'une puce rattachee au
    hasard de l'ordre d'un dictionnaire.
    """
    votes = Counter(g for g in gids if g)
    if not votes:
        return 0
    (gagnant, n), *reste = votes.most_common()
    if reste and reste[0][1] == n:
        return 0
    return gagnant


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

    votes_par_element = {}
    for ref, element in source.elements.items():
        # `element` EST la cle : ET.Element se hache par identite, donc deux
        # refs internes d'un meme composé (U7.1, U7.2) tombent dans la meme
        # entree. Surtout pas `id()` : le depot proscrit ce motif, et il est
        # ici inutile puisque le dict garde l'objet en vie.
        votes_par_element.setdefault(element, []).append(gid_par_ref.get(ref, 0))

    manquants = 0
    for element, gids in votes_par_element.items():
        gid = gids[0] if len(gids) == 1 else _groupe_majoritaire(gids)
        if not _poser_groupe(element, gid, "Begrp"):
            manquants += 1
    if manquants:
        _log.warning("%d element(s) sans balise GpId : groupe non ecrit "
                     "(fichier hors dialecte BoardSCH connu)", manquants)

    for idx, ligne in enumerate(source.lignes):
        ra, rb = source.lignes_refs.get(idx, (None, None))
        ga, gb = gid_par_ref.get(ra, 0), gid_par_ref.get(rb, 0)
        # Un fil qui traverse deux montages n'appartient a aucun des deux.
        _poser_groupe(ligne, ga if (ga and ga == gb) else 0, "BeIngrp")

    return _serialiser_avec_entete(source)


def _normaliser_fins_de_ligne(texte: str) -> str:
    """@brief Ramene toute fin de ligne a LF ('\\n') pur.

    `ecrire_groupes` renvoie une CHAINE, pas des octets : la convention de fin
    de ligne du fichier final appartient a l'APPELANT qui l'ecrit sur disque
    (gui/tab_analyze.py fait `open(p, 'w', encoding='utf-8')`, qui retraduit
    tout '\\n' en '\\r\\n' sur Windows). `source.avant_racine` est capture BRUT
    depuis l'octet du fichier (donc deja en '\\r\\n' sur les cartes reelles,
    100% CRLF) — le laisser tel quel a cote d'un corps ET.tostring() qui, lui,
    ne contient QUE des '\\n' (la norme XML impose au parseur de normaliser
    CRLF/CR en LF a la lecture) produirait un '\\r\\r\\n' corrompu a l'ecriture
    texte. On normalise donc tout en LF ICI, une fois, et on laisse l'appelant
    retraduire uniformement — ce qui redonne exactement le CRLF de la source.
    """
    return texte.replace('\r\n', '\n').replace('\r', '\n')


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
    # NB (revue) : si la racine portait un jour un attribut REEL en plus des
    # xmlns (aucune des 4 cartes reelles n'en a), cette boucle le laisserait
    # avant les xmlns dans l'ordre du dict `attrib`, alors que la source
    # pouvait les avoir dans un ordre different — latent, non corrige ici.
    for prefixe, uri in source.namespaces:
        racine.set(f"xmlns:{prefixe}", uri)

    corps = ET.tostring(racine, encoding="unicode")
    if not source.avant_racine:
        return corps
    return _normaliser_fins_de_ligne(source.avant_racine) + corps
