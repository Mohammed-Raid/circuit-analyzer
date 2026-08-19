"""
@file gabarit.py
@brief Moteur de correspondance structurelle piloté par un schéma de référence
(un fichier BoardSCH XML dessiné normalement) plutôt que par du code Python.

Phase 1 : preuve du mécanisme sur des montages SANS répétition (Suiveur de
tension, Amplificateur inverseur). Phase 2 (celle-ci) : inférence de
répétition (ex. Amplificateur sommateur, N résistances d'entrée). Ce module
reste autonome -- il n'est PAS encore branché dans `detecteur.analyser()` ;
les détecteurs Python existants restent seuls actifs. Voir le plan pour la
phase 3 (bascule réelle + les 21 montages restants).

Principe (repris du design) : le gabarit est ancré sur l'UNIQUE composant à
3+ broches qu'il contient (l'AOP, le transistor...). Pour chaque broche
NOMMÉE de l'ancre, on classe les voisins directs (composants à 2 broches) en
trois familles : vers une AUTRE broche nommée de la même ancre (contre-
réaction), vers un rail masse/alimentation (par FONCTION, jamais par nom de
net), ou externe. Les valeurs de composants (10k, 100nF...) ne sont JAMAIS
comparées -- seuls types et rôles comptent, comme les 24 détecteurs actuels.

Répétition (Phase 2) : si le gabarit montre AU MOINS 2 composants du même
type jouant le même rôle structurel sur une broche (ex. 3 résistances
d'entrée toutes "externes" sur IN-), le moteur généralise cette case en
« 2 ou plus » côté cible -- reproduit fidèlement le seuil du détecteur
Python de référence (`detecter_amplificateur_sommateur` : `len(zin) >= 2`).
Une case qui montre EXACTEMENT 1 occurrence dans le gabarit reste une
exigence stricte (exactement 1) : le seuil est 2, pas 1 -- sinon un simple
amplificateur inverseur (1 seule résistance d'entrée) matcherait AUSSI le
gabarit sommateur, une collision fausse-positive entre deux montages
pourtant déjà distingués par les détecteurs Python actuels.
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from circuit_analyzer.patterns.base import is_gnd, is_power
from circuit_analyzer.xml import lire_xml
from circuit_analyzer.composant import construire_graphe


def _voisins_2broches(graphe, net, exclure_ref):
    """@brief Composants à 2 broches directement connectés à `net`.

    @param graphe Graphe NetworkX (brut, `construire_graphe`).
    @param net Nœud électrique à inspecter.
    @param exclure_ref Référence à ignorer (l'ancre elle-même n'est jamais
    une arête, mais reste défensif si un jour elle en devient une).
    @return list[tuple] (ref, type, autre_net) pour chaque voisin.
    """
    out = []
    for u, v, data in graphe.edges(net, data=True):
        if data.get('ref') == exclure_ref:
            continue
        autre = v if u == net else u
        out.append((data.get('ref'), data.get('type'), autre))
    return out


def _classer(autre_net, pins_ancre, broche_courante):
    """@brief Classe l'autre bout d'un voisin 2-broches par rapport à l'ancre.

    @param autre_net Nœud de l'autre bout du voisin.
    @param pins_ancre {nom_broche: net} de l'ancre.
    @param broche_courante Nom de la broche de l'ancre d'où l'on part (exclue
    de la recherche d'une autre broche du même nom).
    @return tuple Catégorie stable et comparable : ('rail', 'gnd'|'power'),
    ('ancre', nom_autre_broche), ou ('externe',).
    """
    if is_gnd(autre_net):
        return ('rail', 'gnd')
    if is_power(autre_net):
        return ('rail', 'power')
    autre_broche = next((n for n, net in pins_ancre.items()
                         if net == autre_net and n != broche_courante), None)
    if autre_broche is not None:
        return ('ancre', autre_broche)
    return ('externe',)


# Broches d'ALIMENTATION connues (convention catalogue, TYPES_COMPOSANTS['U']) --
# jamais comparées structurellement. Deux raisons : (1) un symbole generique
# (ex. "AOP" a 3 emplacements) peut ne pas avoir de place pour les dessiner,
# elles retombent alors toutes sur le meme "NC" -> faux court-circuit V+/V-
# fabrique par une LIMITE DE DESSIN, pas une vraie structure electrique
# (BUG TROUVE EN TESTANT en generant les 2 premiers gabarits) ; (2) le
# branchement d'alimentation d'un CI ne differencie de toute facon jamais un
# motif d'un autre (chaque AOP en a, quel que soit le montage autour).
_BROCHES_ALIM = {'V+', 'V-'}


def _empreinte(graphe, ancre):
    """@brief Empreinte structurelle d'une ancre : courts-circuits entre ses
    broches +, par broche, soit un marqueur de rail DIRECT, soit les voisins
    2-broches groupés par (type, catégorie).

    [MODIF 2026-08-17] BUG TROUVE EN TESTANT (pas hypothétique -- reproduit
    avec un cas minimal avant correction) : quand une broche nommée de
    l'ancre est reliée DIRECTEMENT à un rail (GND/VCC, ex. IN+ à GND sur un
    inverseur), l'ancien code scannait quand même les "voisins 2-broches" de
    ce net -- or un rail est un net PARTAGÉ par tout le schéma. Sur une
    vraie carte scannée, GND porte presque toujours des dizaines de
    composants SANS AUCUN RAPPORT (découplage ailleurs, autres étages...).
    Résultat : le gabarit exigeait alors la MÊME liste exacte de voisins
    fortuits que dans le petit fichier de référence -- un inverseur
    parfaitement valide cessait de matcher dès qu'un SEUL composant
    supplémentaire, n'importe où sur la carte, touchait GND. Corrigé : une
    broche dont le NET LUI-MÊME est un rail ne scanne plus ses voisins du
    tout -- elle est marquée ('rail', 'gnd'|'power') directement, sans
    dépendre de ce qui est connecté ailleurs sur ce rail. Sert aussi de
    vérification "broche directement au rail, zéro composant intermédiaire"
    (utile pour les montages transistor/MOSFET dont l'émetteur/source doit
    être à la masse SANS détour).

    Les broches d'alimentation (_BROCHES_ALIM) sont exclues -- voir sa
    docstring.

    @param graphe Graphe NetworkX du circuit (référence ou cible).
    @param ancre Composant ancre (3+ broches).
    @return dict {'courts': set[frozenset[str]],
                  'par_broche': {nom: ('rail','gnd'|'power') | {(type, categorie): [refs...]}}}.
    """
    pins = {n: net for n, net in ancre.pins.items() if n not in _BROCHES_ALIM}
    noms = list(pins)
    courts = {frozenset((noms[i], noms[j]))
              for i in range(len(noms)) for j in range(i + 1, len(noms))
              if pins[noms[i]] == pins[noms[j]]}
    par_broche = {}
    for nom, net in pins.items():
        if is_gnd(net):
            par_broche[nom] = ('rail', 'gnd')
            continue
        if is_power(net):
            par_broche[nom] = ('rail', 'power')
            continue
        groupes: dict = {}
        for ref, typ, autre in _voisins_2broches(graphe, net, ancre.ref):
            groupes.setdefault((typ, _classer(autre, pins, nom)), []).append(ref)
        par_broche[nom] = groupes
    return {'courts': courts, 'par_broche': par_broche}


# Seuil de généralisation "répétition" -- voir docstring du module pour le
# raisonnement (reproduit `len(zin) >= 2` du détecteur Sommateur réel).
_SEUIL_REPETITION = 2


def _empreintes_correspondent(ref_emp: dict, cible_emp: dict) -> bool:
    """@brief Vrai si `cible_emp` reproduit la structure de `ref_emp`, avec
    généralisation "2 ou plus" pour toute case qui montrait déjà 2+
    occurrences dans le gabarit de référence (voir _SEUIL_REPETITION).

    [MODIF 2026-08-17] BUG TROUVE EN TESTANT : une broche du gabarit dont le
    groupe de voisins est VIDE (rien dessiné dessus, ex. OUT d'un
    Comparateur qui doit rester libre de toute contre-réaction) ne
    contraignait RIEN côté cible -- la boucle `for cle, refs_ref in
    groupes_ref.items()` ne s'exécute jamais sur un dict vide, donc une
    cible avec des composants EN TROP sur cette broche passait quand même.
    Corrigé : `set(groupes_ref) != set(groupes_cible)` (déjà présent)
    suffit maintenant à le détecter, à condition que `set({})` (vide) soit
    bien comparé à `set(groupes_cible)` -- ce qui échoue déjà correctement
    dès que `groupes_cible` contient ne serait-ce qu'UNE clé de plus. Cette
    ligne existait déjà mais son effet réel n'avait jamais été vérifié par
    un test dédié tant qu'aucun gabarit "broche vide" n'existait -- voir
    test_gabarit_broche_vide_rejette_tout_voisin_supplementaire.

    @param ref_emp Empreinte du gabarit (sortie de `_empreinte`).
    @param cible_emp Empreinte du candidat cible.
    @return bool True si la cible satisfait la structure du gabarit.
    """
    if ref_emp['courts'] != cible_emp['courts']:
        return False
    if set(ref_emp['par_broche']) != set(cible_emp['par_broche']):
        return False
    for nom, val_ref in ref_emp['par_broche'].items():
        val_cible = cible_emp['par_broche'][nom]
        # Broche directement sur un rail (('rail', 'gnd'|'power')) : exige
        # exactement le même rail côté cible, comparaison directe -- jamais
        # de scan de voisins pour un rail (voir _empreinte).
        if isinstance(val_ref, tuple):
            if val_ref != val_cible:
                return False
            continue
        if isinstance(val_cible, tuple):
            return False   # gabarit exige un signal local, cible a un rail direct
        groupes_ref, groupes_cible = val_ref, val_cible
        if set(groupes_ref) != set(groupes_cible):
            return False
        for cle, refs_ref in groupes_ref.items():
            n_ref = len(refs_ref)
            n_cible = len(groupes_cible[cle])
            if n_ref >= _SEUIL_REPETITION:
                if n_cible < _SEUIL_REPETITION:
                    return False
            elif n_cible != n_ref:
                return False
    return True


@dataclass
class Gabarit:
    """@brief Montage de référence chargé depuis un schéma dessiné normalement."""
    nom: str
    ancre: 'object'
    empreinte: dict
    positions: dict = field(default_factory=dict)   # {ref: (x, y)}

    def correspondre(self, graphe_cible) -> list:
        """@brief Cherche, dans un graphe cible, chaque composant qui reproduit
        la structure de l'ancre -- avec généralisation "2 ou plus" pour les
        cases qui montraient déjà une répétition dans le gabarit (Phase 2,
        voir `_empreintes_correspondent`).

        @param graphe_cible Graphe NetworkX (brut) du circuit à analyser.
        @return list[dict] Matches au format des détecteurs existants
        (`circuit_type`, `components`, `nodes`, `confidence`,
        `functional_category`, `reasons`, `warnings`, `satellites`), enrichis
        d'une clé interne `_placement` (liste de {ref, ref_gabarit, index,
        repete}) consommée par `positions_canoniques`.
        """
        resultats = []
        for ref, comp in graphe_cible.graph.get('components', {}).items():
            if comp.type != self.ancre.type or len(comp.pins) != len(self.ancre.pins):
                continue
            empreinte_candidate = _empreinte(graphe_cible, comp)
            if not _empreintes_correspondent(self.empreinte, empreinte_candidate):
                continue
            composants = [ref]
            placement = [{'ref': ref, 'ref_gabarit': self.ancre.ref, 'index': 0, 'repete': False}]
            # [MODIF 2026-08-17] BUG TROUVE EN TESTANT (Phase 2, sommateur a 5
            # entrees) : un voisin qui relie DEUX broches nommees de l'ancre
            # (ex. Rf entre IN- et OUT) apparait comme voisin depuis LES DEUX
            # broches -- une fois classe ('ancre','OUT') en scannant IN-, une
            # fois ('ancre','IN-') en scannant OUT. Sans garde, il finissait
            # deux fois dans `composants`/`placement`. Un `set` de refs deja
            # vus absorbait le doublon en silence dans les comparaisons par
            # `set(...)` des tests Phase 1 -- jamais remarque avant qu'un test
            # Phase 2 compte `len(...)` au lieu de `set(...)`.
            deja_vus = {ref}
            for nom, groupes_cible in empreinte_candidate['par_broche'].items():
                if isinstance(groupes_cible, tuple):
                    continue   # broche directement sur un rail -- aucun composant à collecter
                groupes_gabarit = self.empreinte['par_broche'][nom]
                for cle, refs_cible in groupes_cible.items():
                    refs_gabarit = groupes_gabarit[cle]
                    repete = len(refs_gabarit) >= _SEUIL_REPETITION
                    # Exemplaire du gabarit servant de base de translation :
                    # le premier de son groupe -- suffisant en Phase 2 (pas
                    # de disposition individuelle par occurrence, un seul
                    # empilement par groupe répété, voir positions_canoniques).
                    ref_exemplaire = refs_gabarit[0]
                    for i, ref_c in enumerate(refs_cible):
                        if ref_c in deja_vus:
                            continue
                        deja_vus.add(ref_c)
                        composants.append(ref_c)
                        placement.append({'ref': ref_c, 'ref_gabarit': ref_exemplaire,
                                          'index': i, 'repete': repete})
            resultats.append({
                'circuit_type': self.nom,
                'components': composants,
                'nodes': [comp.pins.get(n, '') for n in self.ancre.pins],
                'confidence': 0.8,
                'confidence_level': 'high',
                'reasons': [f'Correspond au gabarit "{self.nom}" (patterns_reference/).'],
                'warnings': [],
                'functional_category': 'gabarit',
                'satellites': [],
                '_placement': placement,
            })
        return resultats

    def positions_canoniques(self, match: dict, x: int, y: int, pas_empilement: int = 100) -> dict:
        """@brief Positions à écrire pour un match, dérivées du dessin du
        gabarit (translation relative à l'ancre), placées à l'origine (x, y).

        Une occurrence RÉPÉTÉE (Phase 2, ex. 4 résistances d'entrée d'un
        sommateur alors que le gabarit n'en dessinait que 3) est empilée
        verticalement à partir de la position de l'exemplaire du gabarit, un
        pas fixe par occurrence -- simple et honnête (Phase 2 ne prétend pas
        reproduire une disposition individuelle par entrée, juste éviter que
        les occurrences supplémentaires se superposent exactement).

        @param match Un des dicts renvoyés par `correspondre` (porte `_placement`).
        @param x, y Origine (position de l'ancre dans la disposition finale).
        @param pas_empilement Décalage vertical entre occurrences empilées.
        @return dict {ref_cible: (x, y)}.
        """
        ancre_pos = self.positions.get(self.ancre.ref, (0, 0))
        out = {}
        for item in match.get('_placement', []):
            pos = self.positions.get(item['ref_gabarit'])
            if pos is None:
                continue
            dx = pos[0] - ancre_pos[0]
            dy = pos[1] - ancre_pos[1]
            if item['repete']:
                dy += item['index'] * pas_empilement
            out[item['ref']] = (x + dx, y + dy)
        return out


# =============================================================================
# GabaritRelation -- lot "relations à DEUX ancres" (Push-pull, Darlington,
# Miroir de courant BJT). Mécanisme ADDITIF, séparé de Gabarit ci-dessus :
# ces 3 montages recherchent une RELATION entre deux composants à 3+ broches
# (ex. l'émetteur de Q1 attaque la base de Q2), pas "un composant + ses
# voisins 2-broches". Construit en réutilisant `_empreintes_correspondent`
# tel quel (il ne connaît pas la forme des clés de broche, seulement leur
# égalité) -- seule la CONSTRUCTION de l'empreinte change : les broches sont
# labellisées (index_ancre, nom_broche) au lieu de juste nom_broche, ce qui
# fait naturellement apparaître les courts-circuits ENTRE les deux ancres
# (ex. E(Q1) == B(Q2)) dans le même mécanisme `courts` qu'un court-circuit
# interne à une seule ancre.
# =============================================================================

def _voisins_2broches_excl(graphe, net, exclure_refs) -> list:
    """@brief Comme `_voisins_2broches`, mais exclut un ENSEMBLE de
    références (les deux ancres d'une relation, pas une seule).

    @param graphe Graphe NetworkX (brut).
    @param net Nœud électrique à inspecter.
    @param exclure_refs Ensemble de références à ignorer.
    @return list[tuple] (ref, type, autre_net).
    """
    out = []
    for u, v, data in graphe.edges(net, data=True):
        if data.get('ref') in exclure_refs:
            continue
        autre = v if u == net else u
        out.append((data.get('ref'), data.get('type'), autre))
    return out


def _classer_multi(autre_net, pins_multi: dict, cle_courante):
    """@brief Comme `_classer`, généralisé à plusieurs ancres labellisées.

    @param autre_net Nœud de l'autre bout du voisin.
    @param pins_multi {(index_ancre, nom_broche): net} de TOUTES les ancres.
    @param cle_courante Clé (index_ancre, nom_broche) d'où l'on part.
    @return tuple ('rail', ...), ('ancre', autre_cle), ou ('externe',).
    """
    if is_gnd(autre_net):
        return ('rail', 'gnd')
    if is_power(autre_net):
        return ('rail', 'power')
    autre_cle = next((cle for cle, net in pins_multi.items()
                      if net == autre_net and cle != cle_courante), None)
    if autre_cle is not None:
        return ('ancre', autre_cle)
    return ('externe',)


def _empreinte_multi(graphe, ancres: list) -> dict:
    """@brief Empreinte structurelle d'un GROUPE d'ancres (généralisation de
    `_empreinte` à N ancres) : broches labellisées (index, nom), courts-
    circuits INTER et INTRA-ancre confondus dans le même mécanisme.

    @param graphe Graphe NetworkX du circuit (référence ou cible).
    @param ancres Liste de Composant (chacun 3+ broches).
    @return dict Même forme que `_empreinte` -- consommable tel quel par
    `_empreintes_correspondent`.
    """
    pins: dict = {}
    for i, a in enumerate(ancres):
        for nom, net in a.pins.items():
            if nom in _BROCHES_ALIM:
                continue
            pins[(i, nom)] = net
    cles = list(pins)
    courts = {frozenset((cles[i], cles[j]))
              for i in range(len(cles)) for j in range(i + 1, len(cles))
              if pins[cles[i]] == pins[cles[j]]}
    refs_ancres = {a.ref for a in ancres}
    par_broche = {}
    for cle, net in pins.items():
        if is_gnd(net):
            par_broche[cle] = ('rail', 'gnd')
            continue
        if is_power(net):
            par_broche[cle] = ('rail', 'power')
            continue
        groupes: dict = {}
        for ref, typ, autre in _voisins_2broches_excl(graphe, net, refs_ancres):
            groupes.setdefault((typ, _classer_multi(autre, pins, cle)), []).append(ref)
        par_broche[cle] = groupes
    return {'courts': courts, 'par_broche': par_broche}


@dataclass
class GabaritRelation:
    """@brief Montage de référence à DEUX ancres (relation entre deux
    composants à 3+ broches), chargé depuis un schéma dessiné normalement."""
    nom: str
    ancres: list          # [Composant, Composant], ordre = ordre du fichier
    empreinte: dict
    positions: dict = field(default_factory=dict)   # {ref: (x, y)}

    def correspondre(self, graphe_cible) -> list:
        """@brief Cherche, dans un graphe cible, chaque PAIRE ORDONNÉE de
        composants du même type que les ancres qui reproduit la relation du
        gabarit. Essaie toutes les paires ordonnées distinctes -- couvre
        aussi bien une relation SYMÉTRIQUE (ex. Push-pull) qu'une relation
        DIRECTIONNELLE (ex. Darlington, E(Q1)->B(Q2) ≠ E(Q2)->B(Q1)) sans
        logique séparée. Dédoublonne par paire NON ordonnée de références
        pour ne jamais rapporter deux fois la même paire symétrique.

        @param graphe_cible Graphe NetworkX (brut) du circuit à analyser.
        @return list[dict] Matches au format des détecteurs existants.
        """
        type_a, type_b = self.ancres[0].type, self.ancres[1].type
        candidats = [c for c in graphe_cible.graph.get('components', {}).values()
                    if len(c.pins) == len(self.ancres[0].pins) or len(c.pins) == len(self.ancres[1].pins)]
        resultats = []
        vus = set()
        for a in candidats:
            if a.type != type_a:
                continue
            for b in candidats:
                if b is a or b.type != type_b:
                    continue
                if len(b.pins) != len(self.ancres[1].pins):
                    continue
                if len(a.pins) != len(self.ancres[0].pins):
                    continue
                cle_paire = frozenset((a.ref, b.ref))
                if cle_paire in vus:
                    continue
                empreinte_candidate = _empreinte_multi(graphe_cible, [a, b])
                if not _empreintes_correspondent(self.empreinte, empreinte_candidate):
                    continue
                vus.add(cle_paire)
                resultats.append({
                    'circuit_type': self.nom,
                    'components': [a.ref, b.ref],
                    'nodes': [a.pins.get(n, '') for n in self.ancres[0].pins]
                             + [b.pins.get(n, '') for n in self.ancres[1].pins],
                    'confidence': 0.8,
                    'confidence_level': 'high',
                    'reasons': [f'Correspond au gabarit "{self.nom}" (patterns_reference/).'],
                    'warnings': [],
                    'functional_category': 'gabarit',
                    'satellites': [],
                    # 'components'[0] correspond TOUJOURS à ancres[0], [1] à
                    # ancres[1] -- garanti par construction ci-dessus (`a`
                    # testé contre type_a=ancres[0].type, `b` contre
                    # ancres[1].type) -- consommé par positions_canoniques.
                    '_ref_map': {self.ancres[0].ref: a.ref, self.ancres[1].ref: b.ref},
                })
        return resultats

    def positions_canoniques(self, match: dict, x: int, y: int) -> dict:
        """@brief Positions à écrire pour un match à deux ancres, dérivées
        du dessin du gabarit (translation relative à la première ancre).

        [MODIF 2026-08-17] Lot 9c : capacité manquante identifiée en
        vérifiant le lot 9 de bout en bout (demande du boss : « cover all
        of them ») -- les 3 montages à deux ancres (Miroir de courant,
        Push-pull, Darlington) chargeaient bien leur gabarit pour la
        DÉTECTION (mécanisme prouvé au lot 5), mais aucune méthode
        n'existait pour en dériver une DISPOSITION -- `positions_depuis_gabarit`
        (lot 9) les ignorait donc silencieusement (repli générique).

        @param match Un des dicts renvoyés par `correspondre` (porte `_ref_map`).
        @param x, y Origine (position de la première ancre dans la disposition finale).
        @return dict {ref_cible: (x, y)}.
        """
        ancre_pos = self.positions.get(self.ancres[0].ref, (0, 0))
        out = {}
        for ref_gabarit, ref_cible in match.get('_ref_map', {}).items():
            pos = self.positions.get(ref_gabarit)
            if pos is None:
                continue
            out[ref_cible] = (x + (pos[0] - ancre_pos[0]), y + (pos[1] - ancre_pos[1]))
        return out


def charger_gabarit_relation(chemin) -> 'GabaritRelation | None':
    """@brief Charge un gabarit à DEUX ancres depuis un schéma normal.

    Fail-closed : exige exactement 2 composants au nombre de broches
    maximal du fichier (même principe que `charger_gabarit`, généralisé à
    2 ancres au lieu d'1) -- rejeté si 0, 1, ou 3+.

    @param chemin Chemin du fichier .xml.
    @return GabaritRelation ou None si illisible/ambigu.
    """
    try:
        composants = lire_xml(str(chemin))
    except (ValueError, OSError):
        return None
    if not composants:
        return None
    max_broches = max(len(c.pins) for c in composants)
    if max_broches < 3:
        return None
    ancres = [c for c in composants if len(c.pins) == max_broches]
    if len(ancres) != 2:
        return None
    graphe = construire_graphe(list(composants))
    empreinte = _empreinte_multi(graphe, ancres)

    # Voir la note équivalente dans `charger_gabarit` : positions lues via
    # `composants.source.elements`, jamais un re-parse XML séparé indexé par
    # le texte littéral de <reference> (qui diverge des refs RENUMÉROTÉS par
    # `lire_xml`).
    positions = {}
    source = getattr(composants, 'source', None)
    if source is not None:
        for c in composants:
            element = source.elements.get(c.ref)
            if element is None:
                continue
            x = element.findtext('CtrIem/X')
            y = element.findtext('CtrIem/Y')
            if x is None or y is None:
                continue
            try:
                positions[c.ref] = (float(x), float(y))
            except (TypeError, ValueError):
                continue

    import os
    nom = os.path.splitext(os.path.basename(str(chemin)))[0]
    return GabaritRelation(nom=nom, ancres=ancres, empreinte=empreinte, positions=positions)


def charger_gabarit(chemin) -> 'Gabarit | None':
    """@brief Charge un gabarit depuis un fichier BoardSCH XML dessiné normalement.

    Fail-closed (design 2026-08-10) : un gabarit dont l'ancre n'est pas
    identifiable sans ambiguïté est rejeté plutôt que deviné -- jamais de
    faux positif fabriqué à partir d'un fichier incomplet ou mal formé.

    [MODIF 2026-08-17] BUG TROUVE EN TESTANT (lot 4, montages diode --
    roue libre, ESD) : l'ancre était choisie par un seuil FIXE ">= 3
    broches", qui excluait par construction tout montage ancré sur un
    composant à 2 broches (une diode seule). Généraliser naïvement en
    ">= 2 broches" aurait cassé les 12 gabarits DÉJÀ migrés : dans un
    fichier AOP+résistances, chaque résistance a AUSSI 2 broches et
    deviendrait un second "candidat ancre" à égalité -> ambiguïté
    fabriquée là où il n'y en avait pas avant. Corrigé par LE MAXIMUM DE
    BROCHES du fichier (pas un seuil fixe) : l'ancre est le(s) composant(s)
    dont le nombre de broches est le PLUS ÉLEVÉ du fichier (>= 2). Un
    fichier AOP+R garde le même unique candidat qu'avant (5 > 2). Un
    fichier diode SEULE (aucun autre composant) accepte enfin la diode (2
    == 2, seule candidate). Un fichier diode+résistance (ex. "Redresseur
    simple", 2 types de composants à 2 broches chacun) était CORRECTEMENT
    rejeté comme ambigu (2 candidats à égalité) -- fidèle au principe
    fail-closed, pas une régression : ce montage-là avait besoin d'une
    autre façon de désigner l'ancre.

    [MODIF 2026-08-17] Lot 9c : la famille "diode + UN SEUL passif" (roue
    libre/ESD DÉJÀ migrés avec une diode SEULE dans le fichier ; redresseur
    simple/détecteur de crête, diode+R ou diode+C, encore ambigus jusqu'ici)
    a une raison ÉLECTRIQUE de préférer la diode comme ancre plutôt que de
    laisser l'ambiguïté fail-closed : ces 4 montages sont TOUS centrés sur
    UNE diode, jamais sur le passif qui l'accompagne (déjà le cas des 2
    autres, migrés avec succès). Bris d'égalité NARROW : ne s'applique QUE
    quand exactement 2 composants sont à égalité au max de broches ET
    qu'EXACTEMENT UN des deux est de type 'D' -- deux diodes à égalité (un
    vrai montage à 2 diodes) reste rejeté comme ambigu, jamais deviné.

    @param chemin Chemin du fichier .xml (patterns_reference/*.xml).
    @return Gabarit ou None si le fichier est illisible ou ambigu.
    """
    try:
        composants = lire_xml(str(chemin))
    except (ValueError, OSError):
        return None
    if not composants:
        return None
    max_broches = max(len(c.pins) for c in composants)
    if max_broches < 2:
        return None
    ancres = [c for c in composants if len(c.pins) == max_broches]
    if len(ancres) == 2 and max_broches == 2:
        diodes = [c for c in ancres if c.type == 'D']
        if len(diodes) == 1:
            ancres = diodes
    if len(ancres) != 1:
        return None
    ancre = ancres[0]
    graphe = construire_graphe(list(composants))
    empreinte = _empreinte(graphe, ancre)

    # [MODIF 2026-08-17] BUG TROUVÉ EN TESTANT (lot 9b, montage différentiel) :
    # cette fonction relisait le XML brut EN PARALLÈLE de `lire_xml` ci-dessus
    # et indexait les positions par le texte LITTÉRAL de <reference> -- or
    # `lire_xml` RENUMÉROTE TOUJOURS les refs par type+position
    # (`generer_ref`), en ignorant ce même texte (comportement documenté,
    # voir tests/test_eretro_patch.py). Dès qu'un gabarit était dessiné avec
    # un nom de broche descriptif (ex. "RF"/"RG" pour le non-inverseur/
    # différentiel, plutôt que "R1"/"R2"), la position finissait sous une clé
    # ("RF") que plus RIEN ne consultait jamais (l'ancre/l'empreinte, elles,
    # utilisent le ref RENUMÉROTÉ "R2") -- `positions_canoniques` sautait
    # alors silencieusement ce composant (voir sa garde `if pos is None`).
    # Corrigé : les positions viennent de `composants.source.elements`, le
    # PONT ref-renuméroté -> élément XML que `lire_xml` construit déjà pour
    # ses propres besoins (voir `SourceXML` dans xml.py) -- structurellement
    # impossible de diverger des refs utilisés par l'empreinte, puisque
    # c'est le MÊME `lire_xml` qui produit les deux.
    positions = {}
    source = getattr(composants, 'source', None)
    if source is not None:
        for c in composants:
            element = source.elements.get(c.ref)
            if element is None:
                continue
            x = element.findtext('CtrIem/X')
            y = element.findtext('CtrIem/Y')
            if x is None or y is None:
                continue
            try:
                positions[c.ref] = (float(x), float(y))
            except (TypeError, ValueError):
                continue

    import os
    nom = os.path.splitext(os.path.basename(str(chemin)))[0]
    return Gabarit(nom=nom, ancre=ancre, empreinte=empreinte, positions=positions)


# =============================================================================
# BASCULE RÉELLE (lot 8, 2026-08-17) -- branche les gabarits prouvés dans le
# pipeline de détection RÉEL (`detecteur.analyser`), remplaçant le détecteur
# Python d'origine SEULEMENT pour les montages dont la parité a été prouvée
# lot par lot (voir docs/superpowers/plans/2026-08-17-gabarits-xml-montages-canoniques.md).
#
# Contrat de repli (jamais de perte silencieuse de détection) : si le fichier
# de référence est absent, illisible, ou redevient ambigu (modifié à la main
# par le boss de façon à casser sa propre structure), `charger_pour_wiring`
# retombe SANS EXCEPTION sur le détecteur Python D'ORIGINE -- jamais une
# liste de détecteurs amputée. Le détecteur Python original n'est jamais
# supprimé du fichier, seulement retiré de la liste ACTIVE quand son gabarit
# charge correctement.
# =============================================================================

def racine_patterns_reference():
    """@brief Dossier `patterns_reference/`, résolu comme le reste de l'appli
    (à côté de l'exe une fois gelée, à la racine du projet sinon).

    @return Path Chemin du dossier des gabarits.
    """
    from circuit_analyzer.chemins import racine_application
    return racine_application() / 'patterns_reference'


def _envelopper_gabarit(gabarit, circuit_type_exact: str):
    """@brief Adapte un `Gabarit` en fonction détecteur compatible
    `_DETECTEURS_COMPLEXES`/`_DETECTEURS_SIMPLES` (signature `f(graphe) ->
    iterable[dict]`).

    Ne renvoie QUE les clés que `detecteur._enrichir` ne recalcule pas déjà
    lui-même à partir de `circuit_type` (confidence/reasons/warnings/
    functional_category sont TOUJOURS regénérés par `_enrichir`, quelle que
    soit la valeur ici -- inutile de les dupliquer). `circuit_type` est
    FORCÉ à la chaîne EXACTE du détecteur Python d'origine (jamais le nom du
    fichier gabarit) : `_CATEGORIES`, `_POSITIONNEURS_PAR_MOTIF`, `_DRAWERS`
    et tout code aval sont indexés par cette chaîne littérale -- une
    divergence, même d'un accent, les rendrait invisibles à ces mécanismes.

    @param gabarit Gabarit ou GabaritRelation déjà chargé.
    @param circuit_type_exact Chaîne IDENTIQUE à celle du détecteur Python remplacé.
    @return callable f(graphe) -> list[dict].
    """
    def detecter(graphe):
        matches = []
        for m in gabarit.correspondre(graphe):
            matches.append({
                'circuit_type': circuit_type_exact,
                'components': m['components'],
                'nodes': m['nodes'],
            })
        return matches
    return detecter


# {nom_fichier_gabarit (sans .xml): circuit_type EXACT du détecteur Python
# remplacé} -- construit à la main à partir des chaînes littérales trouvées
# dans detecteur.py (grep 'circuit_type':), PAS depuis le nom de fichier
# (qui a parfois dérivé sans accent, ex. "Etage push-pull" vs "Étage
# push-pull" réel -- BUG TROUVE EN VÉRIFIANT, avant toute bascule).
_CIRCUIT_TYPE_EXACT = {
    'Suiveur de tension':                    'Suiveur de tension (AOP)',
    'Amplificateur inverseur':               'Amplificateur inverseur (AOP)',
    'Amplificateur sommateur':               'Amplificateur sommateur (AOP)',
    'Amplificateur non-inverseur':           'Amplificateur non-inverseur (AOP)',
    'Integrateur':                           'Intégrateur (AOP)',
    'Derivateur':                            'Dérivateur (AOP)',
    'Amplificateur differentiel':            'Amplificateur différentiel (AOP)',
    'Comparateur':                           'Comparateur (AOP)',
    'Bascule de Schmitt':                    'Bascule de Schmitt (AOP)',
    'Transistor en commutation':             'Transistor en commutation',
    "Collecteur commun (suiveur d'emetteur)": "Collecteur commun (suiveur d'émetteur)",
    'MOSFET en commutation':                 'MOSFET en commutation',
    'MOSFET haute-tension (cote haut)':      'MOSFET haute-tension (côté haut)',
    'Diode de roue libre':                   'Diode de roue libre',
    'Diode de protection ESD':               'Diode de protection ESD',
    'Miroir de courant BJT':                 'Miroir de courant BJT',
    'Etage push-pull':                       'Étage push-pull',
    'Paire Darlington':                      'Paire Darlington',
    'Amplificateur emetteur commun':         'Amplificateur émetteur commun',
}

# Fichiers dont le gabarit utilise le mécanisme à DEUX ancres (lot 5) --
# les autres utilisent le mécanisme à une ancre.
_FICHIERS_RELATION = {'Miroir de courant BJT', 'Etage push-pull', 'Paire Darlington'}


def detecteurs_gabarit_pour_bascule(logger=None) -> dict:
    """@brief Charge tous les gabarits prouvés et construit
    {détecteur_python_original: fonction_gabarit_ou_None}.

    Ne lève JAMAIS : un fichier absent/illisible/ambigu est simplement
    absent du dict retourné (le détecteur Python original reste alors actif
    tel quel côté appelant -- voir contrat de repli en tête de section).

    @param logger Callable(str) optionnel pour tracer les gabarits chargés/
    ignorés (ex. `print`, ou un vrai logger) -- silencieux par défaut.
    @return dict {nom_fichier: callable} -- SEULEMENT les gabarits chargés
    avec succès ; l'appelant compare aux noms de fichiers attendus pour
    savoir lesquels retomber sur l'original.
    """
    dossier = racine_patterns_reference()
    out = {}
    for nom_fichier, ct_exact in _CIRCUIT_TYPE_EXACT.items():
        chemin = dossier / f"{nom_fichier}.xml"
        if nom_fichier in _FICHIERS_RELATION:
            gab = charger_gabarit_relation(str(chemin))
        else:
            gab = charger_gabarit(str(chemin))
        if gab is None:
            if logger:
                logger(f"Gabarit '{nom_fichier}' introuvable/invalide -- "
                       f"détecteur Python d'origine conservé pour '{ct_exact}'.")
            continue
        out[nom_fichier] = _envelopper_gabarit(gab, ct_exact)
        if logger:
            logger(f"Gabarit '{nom_fichier}' chargé -- remplace le détecteur "
                   f"Python de '{ct_exact}'.")
    return out


# =============================================================================
# DISPOSITION (lot 9, 2026-08-17) -- demande explicite du boss : « add
# another canonique one without hard coding it and still having the
# placement when exporting to the other app ». Contrairement au lot 8 (qui
# touchait la DÉTECTION -- quels composants forment quel montage -- reverté
# après avoir trouvé une régression réelle), ceci ne touche QUE la
# DISPOSITION d'un montage DÉJÀ détecté par le détecteur Python (inchangé,
# fiable). Le risque qui a fait échouer le lot 8 (une carte réelle a
# souvent des composants supplémentaires légitimes sur une broche libre)
# NE S'APPLIQUE PAS ici : on ne fait correspondre le gabarit qu'à
# l'intérieur du sous-graphe des composants DÉJÀ confirmés appartenir à ce
# montage précis (`bloc.comps`, la sortie du détecteur Python) -- jamais au
# graphe entier de la carte, donc jamais exposé au bruit d'un rail partagé
# ou d'un voisin d'un autre étage.
#
# Zéro code Python à ajouter pour un NOUVEAU montage : le fichier doit
# juste s'appeler EXACTEMENT comme le `circuit_type` déjà affiché par
# l'analyseur (ex. "Filtre RC passe-bas.xml") -- la recherche ci-dessous
# est un simple essai de chemin par ce nom, jamais une table à maintenir.
# =============================================================================

_cache_gabarits_disposition: dict = {}   # {nom_fichier: Gabarit | None}, mis en cache


def _gabarit_pour_disposition(circuit_type: str) -> 'Gabarit | GabaritRelation | None':
    """@brief Charge (et met en cache) le gabarit de DISPOSITION pour un
    `circuit_type`, par simple correspondance de NOM DE FICHIER -- aucune
    table à tenir à jour, aucun code à écrire pour un montage nouvellement
    ajouté par le boss.

    [MODIF 2026-08-17] Lot 9c : essaie le mécanisme à UNE ancre
    (`charger_gabarit`) PUIS, s'il échoue, celui à DEUX ancres
    (`charger_gabarit_relation`) -- GÉNÉRIQUEMENT, sans savoir à l'avance
    lequel des deux le fichier utilise. Un montage à deux ancres
    fraîchement ajouté par le boss (ex. une future paire de transistors)
    n'a besoin d'AUCUNE entrée dans une table -- les deux chargeurs sont
    juste essayés dans l'ordre, celui qui réussit gagne. `Gabarit` et
    `GabaritRelation` exposent la même interface (`correspondre`,
    `positions_canoniques`) : le reste du code (positions_depuis_gabarit)
    n'a pas besoin de savoir lequel des deux il tient.

    @param circuit_type Nom exact du montage (ex. "Amplificateur inverseur (AOP)").
    @return Gabarit, GabaritRelation, ou None (fichier absent -- silencieux).
    """
    if circuit_type in _cache_gabarits_disposition:
        return _cache_gabarits_disposition[circuit_type]

    def _essayer(chemin) -> 'Gabarit | GabaritRelation | None':
        return charger_gabarit(str(chemin)) or charger_gabarit_relation(str(chemin))

    chemin = racine_patterns_reference() / f"{circuit_type}.xml"
    gab = _essayer(chemin)
    if gab is None:
        # Repli : nom de fichier historique abrégé (les 19 premiers gabarits
        # migrés, écrits avant que cette convention par nom exact existe).
        # Un montage FUTUR, ajouté par le boss, n'a pas besoin de cette
        # entrée -- seulement les fichiers déjà en place avant ce lot.
        nom_legacy = _CIRCUIT_TYPE_EXACT_VERS_FICHIER.get(circuit_type)
        if nom_legacy:
            gab = _essayer(racine_patterns_reference() / f"{nom_legacy}.xml")
    _cache_gabarits_disposition[circuit_type] = gab
    return gab


_CIRCUIT_TYPE_EXACT_VERS_FICHIER = {v: k for k, v in _CIRCUIT_TYPE_EXACT.items()}


def positions_depuis_gabarit(circuit_type: str, comps_du_bloc: list, x: int, y: int) -> 'dict | None':
    """@brief Dérive les positions d'un bloc DÉJÀ DÉTECTÉ depuis son gabarit
    de référence, s'il existe -- None si aucun gabarit, ou si la
    correspondance de rôle échoue (repli SILENCIEUX vers le positionneur
    générique existant, jamais bloquant).

    Ne fait JAMAIS correspondre le gabarit à autre chose qu'au sous-graphe
    de `comps_du_bloc` lui-même (voir note de sécurité en tête de section) :
    la question posée n'est PAS « ce montage existe-t-il ? » (déjà tranché
    par le détecteur Python), seulement « quel composant de la référence
    correspond à quel composant réel, pour recopier sa position ? ».

    @param circuit_type Nom exact du montage détecté.
    @param comps_du_bloc Liste de Composant DÉJÀ confirmée comme ce montage
    (`bloc.comps`, sortie de `_grouper_par_circuit`).
    @param x, y Origine où placer l'ancre dans la disposition finale.
    @return dict {ref: (x, y)} -- SEULEMENT les refs que le gabarit couvre ;
    None si pas de gabarit ou pas de correspondance de rôle propre.
    """
    gabarit = _gabarit_pour_disposition(circuit_type)
    if gabarit is None:
        return None
    sous_graphe = construire_graphe(list(comps_du_bloc))
    matches = gabarit.correspondre(sous_graphe)
    if len(matches) != 1:
        return None   # 0 = pas de correspondance de role ; 2+ = ambigu, jamais deviner
    match = matches[0]
    if set(match['components']) != {c.ref for c in comps_du_bloc}:
        return None   # correspondance PARTIELLE -- ne jamais placer que la moitie d'un bloc
    return gabarit.positions_canoniques(match, x, y)
