"""
@file eretro.py
@brief Import des fichiers réels ERetroDesign (éditeur C# maison de l'entreprise).

Spécificités des vrais fichiers BoardSCH par rapport au dialecte natif produit
par generer_xml : refs de connexion historiques concaténées sans underscore,
puces composées (CCmpntL), noms de bibliothèque français, broches identifiées
par Pnumber (Pname souvent vide, parfois les deux absents), champ <typ> = code
ASCII du char C#.

Règle d'or (spec 2026-07-17 §3) : la connexité se résout par ÉGALITÉ DE
CHAÎNES entre datapin/NodeL et Line.CFirst/CLast — on ne parse JAMAIS le
format packé des refs (ambigu dans les vieux fichiers : '14001' est
indécodable sans les largeurs de champs).
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
