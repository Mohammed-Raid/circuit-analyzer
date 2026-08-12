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

from circuit_analyzer.xml import (
    _grouper_par_circuit,
    _ids_groupes_par_ref,
    _POSITIONNEURS_PAR_MOTIF,
    _positionner_amplificateur_inverseur,
)

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


_BASE_ANALYSE = 1000
_MARGE_GROUPE = 24


def _gid_analyse(gid: int) -> int:
    """@brief Numero de montage -> Gid du groupe ecrit dans SON fichier.

    Ses Gid a lui valent `GrpL.Count() + 1` a la creation (Form1.cs:8945, 9404)
    puis `i + 1` a la renumerotation (Form1.cs:9339) : toujours petits et
    contigus depuis 1. Nos montages sont numerotes 1, 2, 3... eux aussi, donc
    les ecrire tels quels ferait entrer les deux jeux en COLLISION — son
    `UpdateGrp()` reconstruit la composition en comparant `GpId == Gid`
    (Form1.cs:9216, 9238) et absorberait nos elements dans son groupe.

    On decale donc au-dessus de _BASE_ANALYSE. Contrairement au choix du
    2026-07-30 (GpId NEGATIF, inerte par construction), la valeur est ici
    POSITIVE et volontairement vivante : elle designe un `<GRPS>` que nous
    ecrivons vraiment, et que son editeur doit afficher.
    """
    return _BASE_ANALYSE + gid


def _est_a_lui(gpid: int) -> bool:
    """@brief Ce GpId designe-t-il un groupe cree A LA MAIN par le collegue ?

    0 = jamais groupe, -1 = SA sentinelle « degroupe » (Form1.cs:3566, 9515),
    >= _BASE_ANALYSE = un des notres. Entre les deux, c'est son travail : on
    n'y touche pas (risque acte le 2026-07-30, jamais traite jusqu'ici).
    """
    return 0 < gpid < _BASE_ANALYSE


def _entier(element, balise: str, defaut: int = 0) -> int:
    """@brief Lit une balise entiere, tolerante au vide et au non-numerique."""
    try:
        return int((element.findtext(balise) or "").strip())
    except ValueError:
        return defaut


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


def _deltas_disposition_canonique(source, composants, blocs) -> dict:
    """@brief Deplacements (dx, dy) des composants de role d'un montage migre.

    @param source SourceXML (pont ref -> ET.Element).
    @param composants Composants analyses (Composant, avec .ref).
    @param blocs Sortie de _grouper_par_circuit (porte .label et .roles).
    @return dict {ref: (dx, dy)} ; {} si rien a deplacer.

    N'agit QUE sur les refs de role (aop/Zin/Zf) d'un montage dont le label
    est dans _POSITIONNEURS_PAR_MOTIF ET dont roles est peuple — meme garde
    que le chemin generer_xml, aucune regression possible sur un montage non
    migre. Les satellites et tout le reste de la carte ne sont jamais
    consideres ici.

    La disposition canonique est ANCREE sur le centroide REEL actuel du
    groupe (pas une origine arbitraire) : minimise le risque de chevaucher
    un composant reel voisin non deplace.
    """
    comp_par_ref = {c.ref: c for c in composants}
    deltas = {}
    for bloc in blocs:
        if bloc.label not in _POSITIONNEURS_PAR_MOTIF or not bloc.roles:
            continue
        # Scope strict au bloc COURANT : le chemin netlist appelle toujours
        # le positionneur avec exactement bloc.comps, jamais un ensemble plus
        # large — aligner ce chemin dessus interdit par construction de
        # deplacer une ref qui n'appartiendrait pas a CE bloc precis (revue
        # de branche, Minor #5).
        refs_du_bloc = {c.ref for c in bloc.comps}
        refs_role = [ref for refs in bloc.roles.values() for ref in refs
                     if ref in refs_du_bloc]
        positions_reelles = {}
        for ref in refs_role:
            element = source.elements.get(ref)
            if element is None:
                continue
            x_elem, y_elem = element.find("CtrIem/X"), element.find("CtrIem/Y")
            if x_elem is None or y_elem is None:
                continue
            try:
                positions_reelles[ref] = (float(x_elem.text), float(y_elem.text))
            except (TypeError, ValueError):
                continue
        if not positions_reelles:
            continue

        cx = sum(p[0] for p in positions_reelles.values()) / len(positions_reelles)
        cy = sum(p[1] for p in positions_reelles.values()) / len(positions_reelles)

        comps_role = [comp_par_ref[ref] for ref in positions_reelles
                      if ref in comp_par_ref and ref in refs_du_bloc]
        # Placer provisoirement a une origine arbitraire (0,0) juste pour
        # connaitre le CENTROIDE de la disposition canonique elle-meme, puis
        # ne garder que le DECALAGE necessaire pour amener CE centroide sur
        # le centroide reel. Immunise contre le nombre de composants par role
        # et contre tout changement futur de la geometrie interne du
        # positionneur (contrairement a des coefficients devines a la main,
        # qui avaient produit une derive de (-43, -63) a chaque export —
        # revue de branche, jamais convergente).
        provisoire = _positionner_amplificateur_inverseur(comps_role, bloc.roles, 0, 0)
        provisoire_role = {ref: pos for ref, pos in provisoire.items() if ref in positions_reelles}
        if not provisoire_role:
            continue
        cx_canon = sum(p[0] for p in provisoire_role.values()) / len(provisoire_role)
        cy_canon = sum(p[1] for p in provisoire_role.values()) / len(provisoire_role)
        decalage_x, decalage_y = cx - cx_canon, cy - cy_canon

        for ref, position in provisoire_role.items():
            nx, ny = position[0] + decalage_x, position[1] + decalage_y
            ox, oy = positions_reelles[ref]
            dx, dy = nx - ox, ny - oy
            # Tolerance flottante, pas `if dx or dy` : deux moyennes ("/3")
            # calculees a des passes differentes peuvent differer de ~1e-14
            # sans qu'aucun deplacement REEL n'ait eu lieu (idempotence
            # verifiee analytiquement, cf. test associe) — sous ce seuil, le
            # bruit d'arrondi flottant ne doit jamais se traduire par un
            # delta ecrit (a fortiori _decaler_point arrondit de toute facon
            # a l'entier le plus proche).
            if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                deltas[ref] = (dx, dy)
    return deltas


def _decaler_point(point, delta) -> None:
    """@brief Translate un <PointF> (X, Y) du delta donne. No-op si malforme."""
    dx, dy = delta
    x_elem, y_elem = point.find("X"), point.find("Y")
    if x_elem is None or y_elem is None:
        return
    try:
        # Valide les DEUX avant de modifier L'UNE SEULE : sinon, si Y est
        # mauvais, X a deja change et c'est un no-op partiel (regression).
        new_x = str(int(round(float(x_elem.text) + dx)))
        new_y = str(int(round(float(y_elem.text) + dy)))
        x_elem.text = new_x
        y_elem.text = new_y
    except (TypeError, ValueError):
        return


def _segment_croise_rectangle(p, q, rect) -> bool:
    """@brief Un segment axis-aligned (horizontal OU vertical) traverse-t-il
    l'INTERIEUR d'un rectangle ?

    @param p, q Extremites du segment (x, y) — partagent x (segment
           vertical) OU y (segment horizontal).
    @param rect Rectangle (x0, y0, x1, y1), x0<=x1, y0<=y1.
    @return True si le segment coupe l'interieur STRICT de rect — la
            frontiere reste praticable (meme convention que
            gui/schema_grid.py:Rect.contient_strict, reimplementee ici
            sans nouvelle dependance vers gui/).
    """
    x0, y0, x1, y1 = rect
    (px, py), (qx, qy) = p, q
    if px == qx:
        x = px
        if not (x0 < x < x1):
            return False
        ylo, yhi = min(py, qy), max(py, qy)
        return ylo < y1 and yhi > y0
    y = py
    if not (y0 < y < y1):
        return False
    xlo, xhi = min(px, qx), max(px, qx)
    return xlo < x1 and xhi > x0


def _appliquer_deltas(source, deltas) -> None:
    """@brief Translate <CtrIem> et les extremites de fil des refs deplacees.

    @param source SourceXML (pont ref -> ET.Element, fils, refs de fils).
    @param deltas {ref: (dx, dy)} — sortie de _deltas_disposition_canonique.

    Ne touche jamais <angle> (translation pure). Un fil dont une SEULE
    extremite est dans `deltas` ne voit QUE cette extremite bouger — l'autre
    (composant non deplace) reste a sa position reelle scannee. Un fil dont
    les DEUX extremites sont dans `deltas` (fil interne au groupe) voit
    chacune bouger de SON propre delta.
    """
    for ref, delta in deltas.items():
        element = source.elements.get(ref)
        if element is None:
            continue
        ctr = element.find("CtrIem")
        if ctr is None:
            continue
        _decaler_point(ctr, delta)

    for idx, ligne in enumerate(source.lignes):
        ra, rb = source.lignes_refs.get(idx, (None, None))
        points = ligne.findall("LP/PointF")
        if len(points) < 2:
            continue
        delta_a, delta_b = deltas.get(ra), deltas.get(rb)
        if delta_a is not None and delta_a == delta_b:
            # Meme delta aux deux bouts : le fil entier translate en bloc,
            # coudes compris — deplacement rigide, la forme reste valide.
            for point in points:
                _decaler_point(point, delta_a)
            continue
        if delta_a is not None and delta_b is not None:
            # Fil INTERNE a un groupe deplace, deltas DIFFERENTS aux deux
            # bouts : un coude intermediaire fige a son ancienne position
            # produit un croisement chaotique, visible a l'oeil dans
            # ERetroDesign (constat du 2026-08-12, capture reelle a l'appui,
            # sur un cas aussi simple que 3 composants). On retrace donc une
            # ligne DROITE entre les nouvelles positions plutot que de
            # garder un coude devenu faux — seuls les fils dont un SEUL bout
            # est dans le groupe (vers un composant non deplace, hors
            # perimetre du chantier) gardent leurs coudes intacts ci-dessous.
            _decaler_point(points[0], delta_a)
            _decaler_point(points[-1], delta_b)
            if len(points) > 2:
                lp = ligne.find("LP")
                for point in points[1:-1]:
                    lp.remove(point)
            continue
        if delta_a is not None:
            _decaler_point(points[0], delta_a)
        if delta_b is not None:
            _decaler_point(points[-1], delta_b)


def ecrire_groupes(source, composants, resultats=None) -> str:
    """@brief Renvoie le XML d'origine, enrichi des groupes d'analyse.

    @param source SourceXML publiee par lire_xml (arbre + pont ref->element).
    @param composants Composants analyses (le retour de lire_xml).
    @param resultats Sortie de detecteur.match_patterns, ou None (aucun groupe).
    @return str Document BoardSCH patche.

    ON ECRIT DE VRAIS GROUPES (arbitrage du boss, 2026-07-31, option A), apres
    le diagnostic qui a montre que `GpId` seul etait un NO-OP VISUEL : `<GrpL>`
    est la SEULE source d'affichage de groupe de son editeur — il dessine
    `GrpL[i].GRect` et `GrpL[i].Name` (Form1.cs:12096-12108) et y fait le test
    de clic (Form1.cs:9095). Un `GpId` que ne reference aucun `<GRPS>` n'est
    lu par rien : l'information voyageait dans le fichier sans jamais devenir
    visible.

    Les drapeaux `Begrp`/`BeIngrp` sont donc ecrits, cette fois a JUSTE TITRE :
    poses SANS `<GrpL>` ils rendaient les composants inertes (ni selectionnables
    un par un, ni en groupe), poses AVEC ils sont exactement l'etat que produit
    son propre `CreateGrpFun` (Form1.cs:8954, 8967).

    CONSEQUENCE VISIBLE ASSUMEE : un composant groupe n'est plus selectionnable
    individuellement dans son editeur (Form1.cs:2192, 2269, 2337, 2697, 3767,
    5510) — c'est le sens meme d'un groupe chez lui, et son menu de degroupage
    le rend a l'unite (Form1.cs:9515).
    """
    blocs = _grouper_par_circuit(composants, resultats) if resultats else []
    if blocs:
        _appliquer_deltas(source, _deltas_disposition_canonique(source, composants, blocs))
    gid_par_ref = _ids_groupes_par_ref(blocs) if blocs else {}
    # `getattr` et non `.label` : le nom est DECORATIF (il s'affiche sur le
    # cadre du groupe), il ne doit jamais faire echouer l'ecriture d'un groupe.
    noms = {i: getattr(b, "label", "") or "Montage"
            for i, b in enumerate(blocs, start=1)}

    racine = source.arbre.getroot()
    zoom = _zoom(racine)
    # `or []` serait un piege : un <CmpntL> vide est faux au sens booleen mais
    # n'est pas None, et ET deprecie ce test. On teste l'absence explicitement.
    cmpntl = racine.find("CmpntL")
    position = {e: i for i, e in enumerate(cmpntl if cmpntl is not None else [])}

    votes_par_element = {}
    for ref, element in source.elements.items():
        # `element` EST la cle : ET.Element se hache par identite, donc deux
        # refs internes d'un meme composé (U7.1, U7.2) tombent dans la meme
        # entree. Surtout pas `id()` : le depot proscrit ce motif, et il est
        # ici inutile puisque le dict garde l'objet en vie.
        votes_par_element.setdefault(element, []).append(gid_par_ref.get(ref, 0))

    membres, fils_membres = {}, {}
    manquants = 0
    for element, gids in votes_par_element.items():
        gid = gids[0] if len(gids) == 1 else _groupe_majoritaire(gids)
        retenu = _appliquer(element, "Begrp", gid)
        if retenu is None:
            manquants += 1
        elif retenu and element in position:
            # Un composé (CComp) n'a pas de place dans IidL, qui indexe CmpntL
            # (Form1.cs:9221) : il porte son GpId, mais ne peut pas etre liste.
            membres.setdefault(retenu, []).append(element)
    if manquants:
        _log.warning("%d element(s) sans balise GpId : groupe non ecrit "
                     "(fichier hors dialecte BoardSCH connu)", manquants)

    manquants_fils = 0
    for idx, ligne in enumerate(source.lignes):
        ra, rb = source.lignes_refs.get(idx, (None, None))
        ga, gb = gid_par_ref.get(ra, 0), gid_par_ref.get(rb, 0)
        # Un fil qui traverse deux montages n'appartient a aucun des deux.
        retenu = _appliquer(ligne, "BeIngrp", ga if (ga and ga == gb) else 0)
        if retenu is None:
            manquants_fils += 1
        elif retenu:
            fils_membres.setdefault(retenu, []).append((idx, ligne))
    if manquants_fils:
        # Compteur separe de celui des composants : le message doit dire
        # lequel des deux est en cause (correction ronde 1, constat 1),
        # sinon le diagnostic ne dit rien d'utile a qui le lit.
        _log.warning("%d fil(s) sans balise GpId : groupe non ecrit "
                     "(fichier hors dialecte BoardSCH connu)", manquants_fils)

    _ecrire_grpl(racine, membres, fils_membres, position, noms, zoom)
    return _serialiser_avec_entete(source)


def _appliquer(element, drapeau: str, gid: int):
    """@brief Pose (ou retire) l'appartenance d'un element a un groupe d'analyse.

    @return Le Gid ecrit, 0 si l'element est laisse libre, None si le dialecte
            ne porte pas `GpId` (rien n'a ete ecrit).

    Trois cas, dans cet ordre :
    - le groupe est A LUI -> on ne touche a RIEN, ni GpId ni drapeau ;
    - le montage est detecte -> GpId + drapeau leve ;
    - sinon -> on ne rabaisse que ce que NOUS avions pose, pour ne pas
      transformer gratuitement un `-1` (sa sentinelle) en `0`, ce qui ferait
      diverger le fichier hors de tout groupe.
    """
    if element.find("GpId") is None:
        return None
    ancien = _entier(element, "GpId")
    if _est_a_lui(ancien):
        return 0
    if gid:
        _ecrire(element, "GpId", _gid_analyse(gid))
        _ecrire(element, drapeau, "true")
        return _gid_analyse(gid)
    if ancien >= _BASE_ANALYSE:
        _ecrire(element, "GpId", 0)
        _ecrire(element, drapeau, "false")
    return 0


def _zoom(racine) -> float:
    """@brief Zoom du document — `GRect` vit en pixels ECRAN, pas en modele.

    Son transform d'affichage est `ecran = imgL + modele * zm` (Form1.cs:3268,
    5001) et `UpdateGrp` construit GRect depuis `DitList[].rect`, donc de
    l'ecran (Form1.cs:9276-9306). A l'ouverture `imgL` vaut (0,0) — jamais
    recalcule par RestoreBoard — d'ou `ecran = modele * zoom`.
    """
    try:
        return float((racine.findtext("zoom") or "1").strip()) or 1.0
    except ValueError:
        return 1.0


def _rectangle(elements, zoom: float):
    """@brief Rectangle ecran englobant des elements, marge comprise.

    Son `CreateGrpFun` ecrit `Rectangle(0,0,0,0)` et compte sur `UpdateGrp()`
    pour le calculer — mais `RestoreBoard` n'appelle JAMAIS `UpdateGrp` au
    chargement : un rectangle nul resterait invisible tant que l'utilisateur
    n'a pas touche a un groupe. On le calcule donc nous-memes.
    """
    pts = []
    for e in elements:
        centre = e.find("CtrIem")
        if centre is not None:
            pts.append((_entier(centre, "X"), _entier(centre, "Y")))
        for p in e.findall("./LP/PointF"):
            pts.append((_entier(p, "X"), _entier(p, "Y")))
    if not pts:
        return (0, 0, 0, 0)
    xs = [int(x * zoom) for x, _ in pts]
    ys = [int(y * zoom) for _, y in pts]
    x, y = min(xs) - _MARGE_GROUPE, min(ys) - _MARGE_GROUPE
    return (x, y, max(xs) + _MARGE_GROUPE - x, max(ys) + _MARGE_GROUPE - y)


def _sous(parent, balise, texte=None):
    """@brief Sous-element, avec son texte eventuel (raccourci de lisibilite)."""
    e = ET.SubElement(parent, balise)
    if texte is not None:
        e.text = str(texte)
    return e


def _bloc_grps(gid: int, nom: str, iidl, lidl, rect):
    """@brief Un `<GRPS>` conforme a SON XmlSerializer.

    L'ordre des champs (CtrG, Gid, Name, NameOffset, GRect, Selected, IidL,
    LidL) n'est pas devine : il a ete produit en serialisant un `GRPS` avec le
    serialiseur de son propre binaire. Un XmlSerializer .NET lit une SEQUENCE —
    un champ hors rang et tout ce qui suit est perdu.
    """
    x, y, w, h = rect
    grps = ET.Element("GRPS")
    ctr = _sous(grps, "CtrG")
    _sous(ctr, "X", w // 2)
    _sous(ctr, "Y", h // 2)
    _sous(grps, "Gid", gid)
    _sous(grps, "Name", nom)
    offset = _sous(grps, "NameOffset")
    _sous(offset, "X", 0)
    _sous(offset, "Y", 0)
    grect = _sous(grps, "GRect")
    # System.Drawing.Rectangle expose Location/Size ET X/Y/Width/Height : son
    # serialiseur emet LES DEUX jeux. N'en ecrire qu'un donne un rectangle nul.
    loc = _sous(grect, "Location")
    _sous(loc, "X", x)
    _sous(loc, "Y", y)
    taille = _sous(grect, "Size")
    _sous(taille, "Width", w)
    _sous(taille, "Height", h)
    for balise, valeur in (("X", x), ("Y", y), ("Width", w), ("Height", h)):
        _sous(grect, balise, valeur)
    _sous(grps, "Selected", "false")
    for balise, valeurs in (("IidL", iidl), ("LidL", lidl)):
        liste = _sous(grps, balise)
        for v in valeurs:
            _sous(liste, "int", v)
    return grps


def _grpl(racine):
    """@brief `<GrpL>` du document, creee AU BON RANG si elle manque.

    Les 4 cartes reelles n'en portent aucune. L'ordre des champs de BoardSCH
    est une sequence (CmpntL, lineL, CCmpntL, GrpL, zoom, ...) : inserer
    `<GrpL>` ailleurs qu'apres `CCmpntL` casserait tout ce qui suit.
    """
    grpl = racine.find("GrpL")
    if grpl is not None:
        return grpl
    grpl = ET.Element("GrpL")
    rang = 0
    for i, e in enumerate(racine):
        if e.tag in ("CmpntL", "lineL", "CCmpntL"):
            rang = i + 1
    racine.insert(rang, grpl)
    grpl.tail = "\n  "
    return grpl


def _ecrire_grpl(racine, membres, fils_membres, position, noms, zoom):
    """@brief Reconstruit la liste des groupes d'analyse, en gardant les siens.

    Idempotent : on retire d'abord les `<GRPS>` que NOUS avions poses (Gid
    au-dessus de _BASE_ANALYSE), jamais les siens, puis on reecrit. Rejouer le
    patch ne peut donc ni empiler ni effacer son travail.
    """
    grpl = _grpl(racine)
    for ancien in [g for g in grpl.findall("GRPS")
                   if _entier(g, "Gid") >= _BASE_ANALYSE]:
        grpl.remove(ancien)

    for gid in sorted(membres):
        elements = membres[gid]
        fils = fils_membres.get(gid, [])
        rect = _rectangle(elements + [l for _, l in fils], zoom)
        grpl.append(_bloc_grps(
            gid, noms.get(gid - _BASE_ANALYSE, "Montage"),
            sorted(position[e] for e in elements),
            sorted(idx for idx, _ in fils), rect))

    ET.indent(grpl, space="  ", level=1)


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
