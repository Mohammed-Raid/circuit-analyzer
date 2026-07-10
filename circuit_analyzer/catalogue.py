"""
@file catalogue.py
@brief Catalogue déclaratif des composants réels (références constructeur).

Ajouter un composant = ajouter UNE entrée de données ci-dessous (jamais de
code). Les pinouts (n° boîtier -> fonction) viennent de la spec
docs/superpowers/specs/2026-07-10-catalogue-composants-reels-design.md.

`alias=True` = puce MONO-unité dont les broches sont renommées à la lecture
vers un rôle déjà connu de l'app (x741 -> AOP IN-/IN+/OUT ; régulateurs ->
IN/GND/OUT). Les multi-unités (x458, LM393, 74HC00…) restent en fonctions de
boîtier et passent par la boîte puce.
"""
import functools
import re


def _normaliser(valeur):
    """@brief Majuscules, espaces/tirets/underscores retirés."""
    return re.sub(r"[\s\-_]", "", (valeur or "").upper())


def _e(categorie, nom, broches=None, alias=False, symbole="puce"):
    return {"categorie": categorie, "nom": nom, "broches": broches,
            "alias": alias, "symbole": symbole}


_BROCHES_7400 = {"1": "1A", "2": "1B", "3": "1Y", "4": "2A", "5": "2B",
                 "6": "2Y", "7": "GND", "8": "3Y", "9": "3A", "10": "3B",
                 "11": "4Y", "12": "4A", "13": "4B", "14": "VCC"}

# ── U : correspondance EXACTE (après normalisation) ─────────────────────────
_EXACTS_U = {
    "NE555": _e("Timer", "NE555",
                {"1": "GND", "2": "TRIG", "3": "OUT", "4": "RESET",
                 "5": "CTRL", "6": "THR", "7": "DIS", "8": "VCC"}),
    "LM393": _e("Comparateur double", "LM393",
                {"1": "OUT1", "2": "IN1-", "3": "IN1+", "4": "GND",
                 "5": "IN2+", "6": "IN2-", "7": "OUT2", "8": "VCC"}),
    "LM339": _e("Comparateur quadruple", "LM339",
                {"1": "OUT2", "2": "OUT1", "3": "VCC", "4": "IN1-",
                 "5": "IN1+", "6": "IN2-", "7": "IN2+", "8": "IN3-",
                 "9": "IN3+", "10": "IN4-", "11": "IN4+", "12": "GND",
                 "13": "OUT4", "14": "OUT3"}),
    "PC817": _e("Optocoupleur", "PC817",
                {"1": "ANODE", "2": "CATHODE", "3": "EMETTEUR",
                 "4": "COLLECTEUR"}),
    "LM317": _e("Regulateur ajustable", "LM317",
                {"1": "ADJ", "2": "OUT", "3": "IN"}, alias=True),
}

# ── U : familles 74HC/74HCT (le T et le suffixe boîtier sont tolérés) ───────
_FAMILLES_74HC = {
    "00": _e("Porte NAND x4", "74HC00", dict(_BROCHES_7400)),
    "08": _e("Porte AND x4", "74HC08", dict(_BROCHES_7400)),
    "32": _e("Porte OR x4", "74HC32", dict(_BROCHES_7400)),
    "04": _e("Inverseur x6", "74HC04",
             {"1": "1A", "2": "1Y", "3": "2A", "4": "2Y", "5": "3A",
              "6": "3Y", "7": "GND", "8": "4Y", "9": "4A", "10": "5Y",
              "11": "5A", "12": "6Y", "13": "6A", "14": "VCC"}),
    "74": _e("Bascule D x2", "74HC74",
             {"1": "1CLR", "2": "1D", "3": "1CLK", "4": "1PRE", "5": "1Q",
              "6": "1NQ", "7": "GND", "8": "2NQ", "9": "2Q", "10": "2PRE",
              "11": "2CLK", "12": "2D", "13": "2CLR", "14": "VCC"}),
    "157": _e("Multiplexeur 2:1 x4", "74HC157",
              {"1": "SEL", "2": "1A", "3": "1B", "4": "1Y", "5": "2A",
               "6": "2B", "7": "2Y", "8": "GND", "9": "3Y", "10": "3B",
               "11": "3A", "12": "4Y", "13": "4B", "14": "4A",
               "15": "NEN", "16": "VCC"}),
    "138": _e("Demultiplexeur 3:8", "74HC138",
              {"1": "A0", "2": "A1", "3": "A2", "4": "NE1", "5": "NE2",
               "6": "E3", "7": "Y7", "8": "GND", "9": "Y6", "10": "Y5",
               "11": "Y4", "12": "Y3", "13": "Y2", "14": "Y1",
               "15": "Y0", "16": "VCC"}),
}

# ── U : suffixes libres (tout préfixe constructeur : LM741, UA741, MC1458…) ─
_SUFFIXES_U = {
    "741": _e("AOP", "741",
              {"1": "OFFSET1", "2": "IN-", "3": "IN+", "4": "V-",
               "5": "OFFSET2", "6": "OUT", "7": "V+", "8": "NC"},
              alias=True),
    "1458": _e("AOP double", "1458",
               {"1": "OUT1", "2": "IN1-", "3": "IN1+", "4": "V-",
                "5": "IN2+", "6": "IN2-", "7": "OUT2", "8": "V+"}),
    "458": _e("AOP double", "x458",
              {"1": "OUT1", "2": "IN1-", "3": "IN1+", "4": "V-",
               "5": "IN2+", "6": "IN2-", "7": "OUT2", "8": "V+"}),
    "7805": _e("Regulateur +5 V", "7805",
               {"1": "IN", "2": "GND", "3": "OUT"}, alias=True),
    "7812": _e("Regulateur +12 V", "7812",
               {"1": "IN", "2": "GND", "3": "OUT"}, alias=True),
}

_REPLI_74HC = _e("Logique 74HC", "74HC (famille)", None)

# ── Q / M / D : catégorie seule (les broches nommées existent déjà) ─────────
_EXACTS_Q = {v: _e("Transistor NPN", v, None, symbole=None)
             for v in ("2N2222", "BC547", "2N3904")}
_EXACTS_M = {v: _e("MOSFET canal N", v, None, symbole=None)
             for v in ("IRFZ44N", "BS170", "IRLZ44N")}
_EXACTS_D = {v: _e("Diode signal" if v == "1N4148" else "Diode redressement",
                   v, None, symbole=None)
             for v in ("1N4148", "1N4007")}

_COULEURS_LED = {"ROUGE": "red", "VERT": "green", "BLEU": "blue"}


@functools.lru_cache(maxsize=512)
def identifier(type_, value):
    """@brief Entrée de catalogue d'un composant, ou None si inconnu.

    Mémoïsée (revue Task 3) : appelée 11x par composant U par les détecteurs.
    Les entrées renvoyées sont des dicts PARTAGÉS (déjà le cas pour les tables
    module) — ne jamais les muter côté appelant.

    Priorité : exact > famille 74HC (précise, sinon repli — une valeur 74HCxx n'atteint jamais les suffixes) > suffixe libre.
    None = comportement actuel de l'app inchangé (compat totale).

    @param type_ Lettre de type BoardSCH ("U", "Q", "M", "D"…).
    @param value Champ value du composant (référence constructeur).
    @return dict {categorie, nom, broches, alias, symbole[, couleur]} | None.
    """
    v = _normaliser(value)
    if not v:
        return None
    if type_ == "D":
        for cle, couleur in _COULEURS_LED.items():
            if cle in v:            # "LEDROUGE", "ROUGE", "LEDVERTE"…
                e = dict(_e("LED", f"LED ({couleur})", None, symbole="led"))
                e["couleur"] = couleur
                return e
        return _EXACTS_D.get(v)
    if type_ == "Q":
        return _EXACTS_Q.get(v)
    if type_ == "M":
        return _EXACTS_M.get(v)
    if type_ != "U":
        return None
    if v in _EXACTS_U:
        return _EXACTS_U[v]
    m = re.fullmatch(r"74HCT?(\d+)[A-Z]*", v)
    if m:
        if m.group(1) in _FAMILLES_74HC:
            return _FAMILLES_74HC[m.group(1)]
        return _REPLI_74HC
    for suffixe, entree in sorted(_SUFFIXES_U.items(),
                                  key=lambda kv: -len(kv[0])):
        if re.fullmatch(rf"([A-Z0-9]*[A-Z])?{suffixe}[A-Z]*", v):
            return entree
    return None


def appliquer_catalogue(comps):
    """@brief Passe post-lecture : renomme les broches numérotées des puces
    mono-unité identifiées (alias=True) vers leur rôle connu (741 -> AOP…).

    Idempotente : une broche déjà fonctionnelle (clé absente du pinout
    numéroté) est laissée telle quelle. Mutation en place ; renvoie comps.

    INVARIANT (revue Task 2) : suppose des broches uniformément numérotées OU
    uniformément nommées par composant, jamais mélangées — un mix
    {"2": netA, "IN-": netB} sur un 741 collisionnerait sur "IN-" et perdrait
    silencieusement un net. Aucun chemin de lecture actuel ne produit ce mix
    (les U reconnus par plan de symbole sortent nommés, les inconnus sortent
    en type X) ; à garantir si un plan de symbole 741 dédié est ajouté.
    """
    for c in comps:
        entree = identifier(getattr(c, "type", ""), getattr(c, "value", ""))
        if not entree or not entree.get("alias") or not entree.get("broches"):
            continue
        broches = entree["broches"]
        c.pins = {broches.get(num, num): net for num, net in c.pins.items()}
    return comps
