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


_DECALAGE_ANALYSE = 1000


def _gpid_analyse(gid: int) -> int:
    """@brief Numero de montage -> valeur de GpId ecrite dans SON fichier.

    Nos montages sont numerotes 1, 2, 3... et les SIENS aussi : son editeur
    attribue `Gid = GrpL.Count() + 1` a la creation (Form1.cs:8945, 9404) et
    renumerote en `i + 1` (Form1.cs:9339). Ecrire nos numeros tels quels les
    faisait donc entrer en COLLISION : des qu'il creait son premier groupe,
    `UpdateGrp()` (Form1.cs:9216, 9238) reconstruit la composition des groupes
    en comparant `CmpntL[i].GpId == GrpL[j].Gid`, et absorbait dans SON groupe
    tous nos elements marques 1 (mesure sur `pg carte.xml` : 3 composants et
    5 fils). Deplacer son groupe de 3 en aurait traine huit.

    Ses QUATRE lectures de GpId (Form1.cs:8963, 9216, 9238, 9328) sont toutes
    des egalites contre un Gid — jamais de l'arithmetique, jamais un indice.
    Un GpId strictement negatif ne peut donc egaler aucun Gid : l'annotation
    devient inerte PAR CONSTRUCTION, et non plus par circonstance (« tant que
    <GrpL> est vide »), precondition que le premier groupe cree invalidait.

    -1 est evite : c'est SA sentinelle « composant non groupe »
    (Form1.cs:3566, 9515). 0 reste 0, valeur des cartes non groupees.
    """
    return -(_DECALAGE_ANALYSE + gid) if gid else 0


def _ecrire(element, balise, valeur):
    """@brief Ecrit une balise SI elle existe deja. Renvoie False sinon.

    Refus delibere de creer la balise manquante : l'XmlSerializer C# est
    sensible a l'ORDRE des elements d'une sequence, et on ne connait pas
    l'ordre attendu. Les 4 cartes reelles portent GpId sur 100 % de leurs
    elements — un manque signale un fichier hors dialecte, pas un cas a
    rattraper en devinant.
    """
    cible = element.find(balise)
    if cible is None:
        return False
    cible.text = str(valeur)
    return True


def ecrire_groupes(source, composants, resultats=None) -> str:
    """@brief Renvoie le XML d'origine, enrichi des groupes d'analyse.

    @param source SourceXML publiee par lire_xml (arbre + pont ref->element).
    @param composants Composants analyses (le retour de lire_xml).
    @param resultats Sortie de detecteur.match_patterns, ou None (aucun groupe).
    @return str Document BoardSCH patche.

    ON N'ECRIT QUE `GpId` (arbitrage du boss, 2026-07-30, apres la preuve C#
    de la Task 7). Ses drapeaux `Begrp`/`BeIngrp` ne sont PAS des compagnons
    decoratifs de `GpId` : dans son editeur, `Begrp=true` INTERDIT la selection
    individuelle du composant (Form1.cs:2192, 2269, 2337, 2697, 3767, 5510),
    et l'appartenance a un groupe fait autorite dans `<GrpL>`, que nous
    n'ecrivons pas. Poser les drapeaux sans `<GrpL>` rendrait les composants
    groupes INERTES chez lui : ni selectionnables un par un, ni en groupe.
    `GpId` seul est inerte tant que `<GrpL>` est vide — l'information d'analyse
    voyage dans le fichier sans jamais perturber son application.
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
        if not _ecrire(element, "GpId", _gpid_analyse(gid)):
            manquants += 1
    if manquants:
        _log.warning("%d element(s) sans balise GpId : groupe non ecrit "
                     "(fichier hors dialecte BoardSCH connu)", manquants)

    manquants_fils = 0
    for idx, ligne in enumerate(source.lignes):
        ra, rb = source.lignes_refs.get(idx, (None, None))
        ga, gb = gid_par_ref.get(ra, 0), gid_par_ref.get(rb, 0)
        # Un fil qui traverse deux montages n'appartient a aucun des deux.
        if not _ecrire(ligne, "GpId", _gpid_analyse(ga if (ga and ga == gb) else 0)):
            manquants_fils += 1
    if manquants_fils:
        # Compteur separe de celui des composants : le message doit dire
        # lequel des deux est en cause (correction ronde 1, constat 1),
        # sinon le diagnostic ne dit rien d'utile a qui le lit.
        _log.warning("%d fil(s) sans balise GpId : groupe non ecrit "
                     "(fichier hors dialecte BoardSCH connu)", manquants_fils)

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
