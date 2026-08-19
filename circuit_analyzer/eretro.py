"""
@file eretro.py
@brief Import des fichiers réels ERetroDesign (éditeur C# maison de l'entreprise).

Spécificités des vrais fichiers BoardSCH par rapport au dialecte natif produit
par generer_xml : refs de connexion historiques concaténées sans underscore,
puces composées (CCmpntL), noms de bibliothèque français, broches identifiées
par Pnumber (Pname souvent vide, parfois les deux absents), champ <typ> = code
ASCII du char C#.

Règle d'or (spec 2026-07-17 §3) : la connexité se résout par ÉGALITÉ DE
CHAÎNES entre datapin/NodeL et Line.CFirst/CLast — on ne parse pas le
format packé des refs (ambigu dans les vieux fichiers : '14001' est
indécodable sans les largeurs de champs).

Exception bornée (arbitrage patron 2026-07-20) : les refs d'EXACTEMENT
4 chiffres portées par les fils du schéma principal (lineL/Line) d'un
dialecte encore plus ancien, sans aucun NodeL (ex. SaveDiag.xml), sont
décodées par `_analyser_ref_packee` (xml.py, milliers = index composant,
centaines = index broche), avec garde d'existence sur le composant/la
broche résultante. Les refs à 5 chiffres ou plus (type '14001') restent
rejetées — ambiguës sans largeurs de champs connues. Les fils internes de
puce composée (CCLine) ne sont JAMAIS décodés ainsi, même sur une plage à
4 chiffres identique : c'est un autre référentiel (adresses locales au
boîtier), vérifié empiriquement sur Diag2.xml.
"""
import math
import re
import unicodedata
from dataclasses import dataclass, field


def normaliser_nom(nom: str) -> str:
    """@brief Nom de bibliothèque canonique : minuscules, sans accents,
    espaces repliés — « Résistance  Trad » == « resistance trad ».

    @param nom Nom brut lu dans le fichier.
    @return str Clé normalisée pour _MAPPING_ERETRO.
    """
    sans_accents = ''.join(c for c in unicodedata.normalize('NFD', nom)
                           if unicodedata.category(c) != 'Mn')
    return ' '.join(sans_accents.replace('_', ' ').lower().split())


_PLAN_D = {'A': 'A', 'K': 'K', '1': 'A', '2': 'K',
           'ANODE': 'A', 'CATHODE': 'K', '+': 'A', '-': 'K'}
_PLAN_Q = {'B': 'B', 'C': 'C', 'E': 'E', '1': 'B', '2': 'C', '3': 'E'}
# [MODIF 2026-08-19] BUG TROUVÉ EN TESTANT (schéma bâti via le VRAI chemin
# ERetroDesign, pas generer_xml) : « Transistor NPN.xml » réel porte Pname
# ('B'/'C'/'E') ET Pnumber ('1'/'2'/'3') tous deux renseignés — lire_xml
# préfère Pnumber (xml.py l.2092, vrai pour les passifs dont Pname est vide),
# donc pnom lu vaut '1'/'2'/'3', absent de ce plan -> repli identité -> les
# broches du schéma se retrouvent nommées '1'/'2'/'3' au lieu de B/C/E, comme
# _PLAN_D le gérait déjà pour Diode/LED (repli numérique déjà présent
# ci-dessus). Sans repli ici, aucune connexion réelle sur un transistor
# n'était perdue au sens des NETS, mais les détecteurs qui lisent
# comp.pins.get('B')/('C')/('E') par nom littéral ratent silencieusement le
# composant.
_PLAN_M = {'G': 'G', 'D': 'D', 'S': 'S'}

# Table des noms de bibliothèque ERetroDesign → (type, plan de broches).
# plan None = broches numérotées par POSITION ('1', '2', …) : les libs des
# passifs ERetroDesign n'ont ni Pname ni Pnumber sur leurs broches.
# NPN et PNP mappent tous deux vers Q : les détecteurs déduisent la polarité
# de la topologie (collecteur au rail vs masse), pas d'un champ.
_MAPPING_ERETRO = {
    'resistance trad': ('R', None), 'resistance cms': ('R', None),
    'pot': ('R', None), 'thermistance': ('R', None), 'varistance': ('R', None),
    'condo': ('C', None), 'condo cms': ('C', None),
    'inductance': ('L', None),
    'diode': ('D', _PLAN_D), 'zener': ('D', _PLAN_D), 'led': ('D', _PLAN_D),
    'npn': ('Q', _PLAN_Q), 'transistor npn': ('Q', _PLAN_Q),
    'transistor pnp': ('Q', _PLAN_Q),
    'mosfet': ('M', _PLAN_M), 'mosfet p': ('M', _PLAN_M),
    'mosfet p1': ('M', _PLAN_M),
    'fusible': ('F', None),
    'relais 2rt': ('K', {}),
    'condensateur polarise': ('C', None),
    'photodiode': ('D', _PLAN_D),

    # ── Bibliothèque livrée avec l'éditeur du collègue (2026-07-23) ──────────
    # Diagnostic : 4 noms sur 52 seulement étaient reconnus (18 % des
    # occurrences) ; « Résistance », « Capa », « Self » ou « Gate2 » (33×)
    # tombaient en boîte noire X. Ce dialecte-ci est celui de la BIBLIOTHÈQUE,
    # distinct de celui des vraies cartes ('R 810', 'Transistor_NPN'…).
    'resistance': ('R', None),
    'capa': ('C', None),
    'self': ('L', None),
    'transistor': ('Q', _PLAN_Q),
    'mosfet controle': ('M', _PLAN_M),
    'aop': ('U', {}),
    'regulateur': ('U', {}),
    'optocoupleur simple': ('U', {}),
    'relais 1formc': ('K', {}),
    'contact no': ('SW', None),
    'contact form c': ('SW', None),
    'bouton poussoir double': ('SW', None),
    # Portes logiques : rendues en boîte CI honnête, jamais en symbole deviné.
    'gate2': ('U', {}), 'gate2ic': ('U', {}), 'gates4g': ('U', {}),
    'inverter': ('U', {}), 'nand gate': ('U', {}), 'buffer': ('U', {}),
    'hc165': ('U', {}), 'mc4094': ('U', {}), '8 etage registre': ('U', {}),
    # Portes NOMMÉES par leur fonction : la bibliothèque livre NOT.xml et
    # OR.xml, qui tombaient en boîte noire X faute d'entrée ici.
    'not': ('U', {}), 'or': ('U', {}), 'and': ('U', {}), 'nand': ('U', {}),
    'nor': ('U', {}), 'xor': ('U', {}), 'xnor': ('U', {}),
}

# Noms de symboles d'alimentation de la bibliothèque, par rail produit.
# La bibliothèque du collègue écrit `typ=0` au lieu de 'G'/'V'/'N' : sans ce
# repli par le NOM, aucun rail n'est détecté et plus AUCUN montage n'est
# reconnaissable (tous les détecteurs s'appuient sur la masse et l'alim).
_RAILS_PAR_NOM = {
    'gnd': 'GND', 'masse': 'GND', 'agnd': 'GND', 'dgnd': 'GND',
    'vcc': 'VCC', 'vcc+': 'VCC', 'v+': 'VCC', 'vdd': 'VCC',
    'vss': 'VSS', 'vcc-': 'VSS', 'v-': 'VSS', 'vee': 'VSS',
}


def mapper_nom(nom: str):
    """@brief (type, plan) pour un nom de bibliothèque ERetroDesign, ou None.

    Priorité : table exacte normalisée > catalogue de puces (identifier).
    Une puce du catalogue retourne ('U', {}) : plan vide = passthrough des
    numéros de broches, l'aliasing catalogue (appliquer_catalogue) tourne
    après la lecture comme pour les formes PuceN natives.

    @param nom Nom brut lu dans <Name>.
    @return tuple|None (type, plan) ou None si vraiment inconnu.
    """
    if not nom:
        return None
    cle = normaliser_nom(nom)
    if cle in _MAPPING_ERETRO:
        return _MAPPING_ERETRO[cle]
    # Connecteurs/jumpers/bornes -> type dédié 'J' (dialecte réel).
    if any(mot in cle for mot in ('connect', 'jumper', 'borne')):
        return ('J', None)
    # Résistance 'R <code>' : R suivi d'un chiffre, ou 'RINF'. 'RELAIS' (lettre
    # après R) ne matche pas ; l'exact 'relais 2rt' est déjà intercepté au-dessus.
    if re.match(r'r\s*(\d|inf)', cle):
        return ('R', None)
    from circuit_analyzer.catalogue import identifier
    if identifier('U', nom) is not None:
        return ('U', {})
    return None


def _lire_broches(item_et):
    """@brief Broches d'un DataItem/CComp ElementTree, même forme que lire_xml.

    ATTENTION : chemins DIRECTS ('datapin/DataPin', pas './/') — un CComp
    contient des DataItem internes dont les broches ne doivent pas fuir dans
    celles du boîtier.

    @param item_et Élément <DataItem> ou <CComp>.
    @return list[dict] [{'pname': str, 'refs': list[str]}].
    """
    broches = []
    for pidx, dp in enumerate(item_et.findall('datapin/DataPin')):
        pnum = (dp.findtext('Pnumber') or '').strip()
        pnom = (dp.findtext('Pname') or '').strip()
        refs = [(s.text or '').strip() for s in dp.findall('NodeL/string')]
        broches.append({'pname': pnum or pnom or str(pidx + 1),
                        'refs': [r for r in refs if r]})
    return broches


def extraire_geometrie(item_et):
    """@brief Géométrie brute d'un DataItem (segments/arcs/broches).

    Chemins DIRECTS : la géométrie interne d'une puce composée (DItemL/DataItem)
    ne doit pas fuir dans celle du boîtier.

    @param item_et Élément <DataItem>.
    @return dict {'segments': list[(sx,sy,ex,ey)], 'nb_arcs': int, 'nb_broches': int}.
    """
    segments = []
    for s in item_et.findall('datasegment/DataSegment'):
        sx = float(s.findtext('Spoint/X') or 0.0)
        sy = float(s.findtext('Spoint/Y') or 0.0)
        ex = float(s.findtext('Epoint/X') or 0.0)
        ey = float(s.findtext('Epoint/Y') or 0.0)
        segments.append((sx, sy, ex, ey))
    return {'segments': segments,
            'nb_arcs': len(item_et.findall('dataarc/DataArc')),
            'nb_broches': len(item_et.findall('datapin/DataPin'))}


def _ohms_vers_str(ohms: float) -> str:
    """@brief Ohms -> chaîne d'ingénierie ('81', '3.3k', '390k')."""
    if ohms >= 1_000_000:
        s, suf = ohms / 1_000_000, 'M'
    elif ohms >= 1_000:
        s, suf = ohms / 1_000, 'k'
    else:
        s, suf = ohms, ''
    return f"{s:g}{suf}"


def decoder_valeur_resistance(nom: str) -> str:
    """@brief Valeur d'une résistance depuis son NOM ERetroDesign 'R <code>'.

    Notation résistance standard : EIA (dernier chiffre = multiplicateur),
    'R'-décimal (R = virgule), 'RINF' = non peuplée. Repli gracieux : un code
    indécodable ou aberrant (>100 MΩ) est rendu BRUT — jamais une valeur inventée.

    @param nom Nom brut ('R 810', 'R810', 'R 3R90', 'RINF').
    @return str Valeur pour Composant.value ('81', '1k', '3.9', 'open'), ou '' si pas une résistance.
    """
    code = re.sub(r'(?i)^r\s*', '', (nom or '').strip())
    if not code:
        return ''
    if code.upper() == 'INF':
        return 'open'
    m = re.fullmatch(r'(?i)(\d+)R(\d+)', code)      # 3R90 -> 3.9
    if m:
        return f"{m.group(1)}.{m.group(2)}".rstrip('0').rstrip('.')
    if code.isdigit() and len(code) >= 2:
        ohms = int(code[:-1]) * (10 ** int(code[-1]))
        if ohms <= 100_000_000:
            return _ohms_vers_str(ohms)
    # Repli : un code plausible (contient un chiffre) est rendu BRUT ; un nom
    # GÉNÉRIQUE sans chiffre (« Résistance » -> « ésistance » après strip du R)
    # n'est pas une valeur -> rien, plutôt qu'un libellé abîmé.
    return code if any(ch.isdigit() for ch in code) else ''


def _bbox(segs):
    xs = [c for s in segs for c in (s[0], s[2])]
    ys = [c for s in segs for c in (s[1], s[3])]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 0.0, 0.0)


def _diag(segs):
    x0, y0, x1, y1 = _bbox(segs)
    return math.hypot(x1 - x0, y1 - y0) or 1.0


def _long(s):
    return math.hypot(s[2] - s[0], s[3] - s[1])


def _diagonal(s, ref):
    """Segment ni horizontal ni vertical (|dx| et |dy| tous deux significatifs)."""
    dx, dy = abs(s[2] - s[0]), abs(s[3] - s[1])
    seuil = 0.06 * ref
    return dx > seuil and dy > seuil


def _forme_zigzag(segs):
    """Corps de résistance : ≥4 segments diagonaux (le zigzag)."""
    ref = _diag(segs)
    return sum(1 for s in segs if _diagonal(s, ref)) >= 4


def _plaques_fermees_en_boite(segs, a, b, a_horiz, ref):
    """True si un autre segment referme l'écart entre a et b (boîte/rectangle
    fermé, ex. boîtier de fusible/thermistance/varistance) : les pattes d'un
    VRAI condensateur repartent vers l'EXTÉRIEUR de l'écart, elles ne le
    referment jamais côté gauche ET droit (ou haut ET bas)."""
    tol = 0.06 * ref
    if a_horiz:
        gap_lo, gap_hi = sorted(((a[1] + a[3]) / 2, (b[1] + b[3]) / 2))
        bornes_x = [a[0], a[2], b[0], b[2]]
    else:
        gap_lo, gap_hi = sorted(((a[0] + a[2]) / 2, (b[0] + b[2]) / 2))
        bornes_x = [a[1], a[3], b[1], b[3]]
    for c in segs:
        if c is a or c is b:
            continue
        if a_horiz:
            quasi_vert = abs(c[2] - c[0]) < 0.15 * (_long(c) or 1.0)
            c_lo, c_hi = sorted((c[1], c[3]))
            centre_c = (c[0] + c[2]) / 2
        else:
            quasi_vert = abs(c[3] - c[1]) < 0.15 * (_long(c) or 1.0)
            c_lo, c_hi = sorted((c[0], c[2]))
            centre_c = (c[1] + c[3]) / 2
        if not quasi_vert:
            continue
        couvre_ecart = c_lo <= gap_lo + tol and c_hi >= gap_hi - tol
        pres_dun_bord = any(abs(centre_c - b_) < tol for b_ in bornes_x)
        if couvre_ecart and pres_dun_bord:
            return True
    return False


def _segments_convergent(a, b, prox):
    """@brief Vrai si deux segments ont une extrémité quasi commune (un sommet).

    Sert à distinguer des ARMATURES (deux traits parallèles disjoints) des deux
    arêtes d'un TRIANGLE, qui se rejoignent en pointe.
    """
    for pa in ((a[0], a[1]), (a[2], a[3])):
        for pb in ((b[0], b[1]), (b[2], b[3])):
            if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) < prox:
                return True
    return False


def _forme_paire_plaques(segs):
    """Condensateur : 2 longs segments parallèles séparés par un vrai écart
    (exclut 2 pattes colinéaires, écart ≈ 0, ET exclut un rectangle fermé
    type boîtier de fusible/thermistance/varistance — cf. oracle Lib).

    Exclut aussi les segments qui CONVERGENT en un sommet : les deux arêtes
    obliques d'un triangle (BUFFER, INVERTER) passaient toutes les gardes et
    étaient classées « condensateur » — contresens trouvé par l'oracle Lib le
    2026-07-23, une fois ces symboles enfin typés par leur nom.
    """
    ref = _diag(segs)
    longs = [s for s in segs if _long(s) > 0.35 * ref]
    for i in range(len(longs)):
        for j in range(i + 1, len(longs)):
            a, b = longs[i], longs[j]
            a_horiz = abs(a[3] - a[1]) < 0.15 * _long(a)
            b_horiz = abs(b[3] - b[1]) < 0.15 * _long(b)
            if a_horiz != b_horiz:
                continue  # orientations différentes
            if a_horiz:
                ecart = abs((a[1] + a[3]) / 2 - (b[1] + b[3]) / 2)
            else:
                ecart = abs((a[0] + a[2]) / 2 - (b[0] + b[2]) / 2)
            if 0.1 * ref < ecart < 0.45 * ref:
                if _plaques_fermees_en_boite(segs, a, b, a_horiz, ref):
                    continue  # boîte fermée (fusible/thermistance/varistance), pas un condo
                if _segments_convergent(a, b, 0.12 * ref):
                    continue  # sommet de triangle (buffer/inverseur), pas des armatures
                return True
    return False


def _forme_triangle_barre(segs):
    """Diode : deux segments convergeant en un sommet + une barre transverse
    près de ce sommet."""
    ref = _diag(segs)
    prox = 0.12 * ref
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            a, b = segs[i], segs[j]
            # sommet = extrémités quasi confondues des deux segments
            for pa in ((a[0], a[1]), (a[2], a[3])):
                for pb in ((b[0], b[1]), (b[2], b[3])):
                    if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) < prox:
                        apex_x = (pa[0] + pb[0]) / 2
                        # barre = segment ~vertical proche de l'abscisse du sommet
                        for c in segs:
                            if c in (a, b):
                                continue
                            vertical = abs(c[2] - c[0]) < 0.15 * (_long(c) or 1.0)
                            near = abs((c[0] + c[2]) / 2 - apex_x) < prox
                            if vertical and near and _long(c) > 0.25 * ref:
                                return True
    return False


def classer_par_forme(geo):
    """@brief Type déduit de la forme du symbole, ou None (abstention).

    Conservateur : ne classe que sur une forme franche, le nombre de broches
    désambiguïse (14 broches d'AOP ≠ 2 d'une diode). Ambigu → None → boîte noire.
    Ne classe que vers des types déjà pourvus d'un drawer (U/R/C/D).

    @param geo dict de extraire_geometrie.
    @return tuple(type, plan) ou None.
    """
    segs, arcs, nb = geo['segments'], geo['nb_arcs'], geo['nb_broches']
    # Porte logique : arc + dos + exactement 3 broches (transistor = 0 arc → exclu).
    if arcs >= 1 and nb == 3:
        return ('U', {})
    if nb == 2 and segs:
        if _forme_triangle_barre(segs):
            return ('D', _PLAN_D)
        if _forme_zigzag(segs):
            return ('R', None)
        if _forme_paire_plaques(segs):
            return ('C', None)
    return None


def classer_rail(typc, valeur, nb_broches, nom=''):
    """@brief Nom de net rail pour un symbole d'alimentation ERetroDesign, ou None.

    Le C# marque les alims par le char typ : 'G' (masse), 'V' (alim
    positive), 'N' (alim négative). Garde : un seul point de connexion —
    un composant 2 broches n'est jamais un symbole de rail (le typ natif
    est parfois ord(nom[0]), donc 'V' peut apparaître par accident).

    Repli par le NOM (2026-07-23) : la bibliothèque livrée avec l'éditeur du
    collègue écrit `typ=0` sur GND / Vss / VCC+ / VCC-. Sans ce repli, aucun
    rail n'est détecté et plus aucun montage n'est reconnaissable. La garde
    « une seule broche » s'applique de la même façon.

    @param typc Char typ décodé ('' si absent).
    @param valeur Champ <value> (peut nommer le rail : '+12V', 'VMOT'…).
    @param nb_broches Nombre de broches du composant.
    @param nom Champ <Name> du symbole (repli quand `typ` ne classe rien).
    @return str|None Nom de net ('GND', 'VCC', 'VSS', ou rail nommé), ou None.
    """
    if nb_broches != 1:
        return None
    if typc not in ('G', 'V', 'N'):
        return _RAILS_PAR_NOM.get(normaliser_nom(nom).replace(' ', ''))
    if typc == 'G':
        return 'GND'
    from circuit_analyzer.patterns.base import is_gnd, is_power
    val = (valeur or '').lstrip('/').upper()
    if val and (is_power(val) or is_gnd(val)):
        return val
    return 'VCC' if typc == 'V' else 'VSS'


def extraire_composes(racine, prochain_idx):
    """@brief Aplatit les puces composées (CCmpntL) d'un BoardSCH réel.

    Décision spec §4 : DÉPLIER — les items internes deviennent des composants
    à part entière ; le boîtier reste un pseudo-composant NON émis dont les
    broches externes participent à l'Union-Find (les refs X partagées entre
    NodeL externe et fils internes fusionnent les nets à travers le boîtier).
    Un composé sans intérieur lisible dégrade en boîte noire émise (jamais
    d'exception).

    @param racine Élément racine <BoardSCH> parsé.
    @param prochain_idx Premier index libre après les composants de CmpntL.
    @return tuple (elements_sup, fils_sup, avertissements) :
        elements_sup dict[int, dict] — entrées au format de lire_xml Étape 1,
        enrichies de 'emettre' (bool) et 'puce' ((num, nom) ou None) ;
        fils_sup list[(CFirst, CLast)] — fils internes CCLine ;
        avertissements list[str].
    """
    elements_sup, fils_sup, avertissements = {}, [], []
    idx = prochain_idx
    for num, cc in enumerate(racine.findall('.//CCmpntL/CComp')):
        nom_puce = (cc.findtext('Name') or '').strip() or f'Compose{num + 1}'
        valeur   = (cc.findtext('value') or '').strip()
        items_internes = cc.findall('DItemL/DataItem')
        if not items_internes:
            # Boîte noire : émise telle quelle avec ses broches externes.
            elements_sup[idx] = {'id': idx, 'name': nom_puce, 'value': valeur,
                                 'pins': _lire_broches(cc),
                                 'emettre': True, 'puce': None, 'xml': cc}   # boite noire
            idx += 1
            avertissements.append(
                f"Puce composée '{nom_puce}' sans intérieur lisible → boîte noire"
            )
            continue
        # Boîtier pass-through : broches dans l'Union-Find, composant non émis.
        elements_sup[idx] = {'id': idx, 'name': nom_puce, 'value': valeur,
                             'pins': _lire_broches(cc),
                             'emettre': False, 'puce': None, 'xml': cc}      # boitier
        idx += 1
        for item in items_internes:
            nom_int = (item.findtext('Name') or '').strip()
            val_int = (item.findtext('value') or '').strip()
            elements_sup[idx] = {'id': idx, 'name': nom_int, 'value': val_int,
                                 'pins': _lire_broches(item),
                                 'emettre': True, 'puce': (num, nom_puce),
                                 'xml': cc}   # DELIBERE : le boitier, pas `item`.
            idx += 1
        for fil in cc.findall('CCLine/Line'):
            cf = (fil.findtext('CFirst') or '').strip()
            cl = (fil.findtext('CLast') or '').strip()
            if cf or cl:
                fils_sup.append((cf, cl))
    return elements_sup, fils_sup, avertissements


@dataclass
class SourceXML:
    """@brief Fichier BoardSCH d'ORIGINE, conserve pour etre patche tel quel.

    On garde l'arbre parse plutot que le chemin : le patch doit ecrire dans les
    MEMES elements que ceux qui ont servi a la lecture, sinon rien ne garantit
    que l'indexation par position (cle de tout le decodage) reste la meme.
    """
    arbre: object                    # ET.ElementTree
    elements: dict                   # ref -> ET.Element (<DataItem> ou <CComp>)
    lignes: list                     # <Line> de lineL, dans l'ordre du fichier
    lignes_refs: dict                # indice de fil -> (ref_a, ref_b)
    # Ce que ET.parse() detruit silencieusement et que le patch doit restituer
    # tel quel (jamais fabrique) : xml.etree.ElementTree ne conserve PAS les
    # declarations xmlns:* non utilisees pour qualifier un tag/attribut — un
    # fichier sans namespace donne `namespaces=[]`, jamais une valeur devinee.
    namespaces: list = field(default_factory=list)   # [(prefixe, uri), ...] dans l'ordre du fichier
    avant_racine: str = ""           # texte brut avant la balise racine ouvrante (prologue inclus)
