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
import unicodedata


def normaliser_nom(nom: str) -> str:
    """@brief Nom de bibliothèque canonique : minuscules, sans accents,
    espaces repliés — « Résistance  Trad » == « resistance trad ».

    @param nom Nom brut lu dans le fichier.
    @return str Clé normalisée pour _MAPPING_ERETRO.
    """
    sans_accents = ''.join(c for c in unicodedata.normalize('NFD', nom)
                           if unicodedata.category(c) != 'Mn')
    return ' '.join(sans_accents.lower().split())


_PLAN_D = {'A': 'A', 'K': 'K', '1': 'A', '2': 'K',
           'ANODE': 'A', 'CATHODE': 'K'}
_PLAN_Q = {'B': 'B', 'C': 'C', 'E': 'E'}
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


def classer_rail(typc, valeur, nb_broches):
    """@brief Nom de net rail pour un symbole d'alimentation ERetroDesign, ou None.

    Le C# marque les alims par le char typ : 'G' (masse), 'V' (alim
    positive), 'N' (alim négative). Garde : un seul point de connexion —
    un composant 2 broches n'est jamais un symbole de rail (le typ natif
    est parfois ord(nom[0]), donc 'V' peut apparaître par accident).

    @param typc Char typ décodé ('' si absent).
    @param valeur Champ <value> (peut nommer le rail : '+12V', 'VMOT'…).
    @param nb_broches Nombre de broches du composant.
    @return str|None Nom de net ('GND', 'VCC', 'VSS', ou rail nommé), ou None.
    """
    if nb_broches != 1 or typc not in ('G', 'V', 'N'):
        return None
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
                                 'emettre': True, 'puce': None}
            idx += 1
            avertissements.append(
                f"Puce composée '{nom_puce}' sans intérieur lisible → boîte noire"
            )
            continue
        # Boîtier pass-through : broches dans l'Union-Find, composant non émis.
        elements_sup[idx] = {'id': idx, 'name': nom_puce, 'value': valeur,
                             'pins': _lire_broches(cc),
                             'emettre': False, 'puce': None}
        idx += 1
        for item in items_internes:
            nom_int = (item.findtext('Name') or '').strip()
            val_int = (item.findtext('value') or '').strip()
            elements_sup[idx] = {'id': idx, 'name': nom_int, 'value': val_int,
                                 'pins': _lire_broches(item),
                                 'emettre': True, 'puce': (num, nom_puce)}
            idx += 1
        for fil in cc.findall('CCLine/Line'):
            cf = (fil.findtext('CFirst') or '').strip()
            cl = (fil.findtext('CLast') or '').strip()
            if cf or cl:
                fils_sup.append((cf, cl))
    return elements_sup, fils_sup, avertissements
