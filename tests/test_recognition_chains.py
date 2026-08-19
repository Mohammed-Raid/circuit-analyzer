"""
@file test_recognition_chains.py
@brief Couverture volumique du moteur de patterns personnalises (custom_circuits.loader)
sur des CHAINES multi-etages realistes (alim, minuterie 555, ampli, capteur+seuil,
driver relais, pont, etc.), pas des mini-fixtures isolees.

Chaque circuit_* ci-dessous est une petite chaine reelle (types/valeurs/pins
plausibles). Chaque CAS associe un circuit a une condition generique parametree
(cf. custom_circuits.loader._evaluer_condition_generique, les 12 CONDITION_KINDS)
et le resultat attendu -- positif ET negatif pour chaque "kind", verifie via
CustomCircuitPattern.match() reel, jamais une approximation.

Objectif de la demande utilisateur (2026-08-19) : « do at least 500 tests of new
schema canonique complicated ... see if it reconizing perfectly ». Ce fichier
fournit la partie volumique en memoire (rapide, durable, s'execute a chaque run) ;
les fixtures XML complexes deposees dans bin/Debug/schema_test (generees via
circuit_analyzer.xml.generer_xml, cf. test_reel_chains_xml_fixtures.py) couvrent
le "full chain via ERetroDesign" demande en plus.
"""
import pytest

from circuit_analyzer.composant import Composant, construire_graphe
from custom_circuits.loader import CustomCircuitPattern


def _c(ref, type_, pins, value='', categorie=''):
    return Composant(ref=ref, type=type_, pins=pins, value=value, categorie=categorie)


# =============================================================================
# Bibliotheque de chaines realistes (chacune = une petite fonction -> list[Composant])
# =============================================================================

def circuit_555_astable():
    """Minuterie NE555 astable : R1/R2/C1 timing, C2 decouplage CTRL."""
    return [
        _c('U1', 'U', {'1': 'GND', '2': 'TT', '3': 'OUT', '4': 'VCC',
                       '5': 'CTRL', '6': 'TT', '7': 'DISCH', '8': 'VCC'}, 'NE555'),
        _c('R1', 'R', {'1': 'VCC', '2': 'DISCH'}, '4.7k'),
        _c('R2', 'R', {'1': 'DISCH', '2': 'TT'}, '10k'),
        _c('C1', 'C', {'1': 'TT', '2': 'GND'}, '10u'),
        _c('C2', 'C', {'1': 'CTRL', '2': 'GND'}, '10n'),
    ]


def circuit_alim_redressee_regulee():
    """Chaine alim : pont redresseur -> lissage -> regulateur lineaire -> sortie."""
    return [
        _c('D1', 'D', {'A': 'AC1', 'K': 'RECT+'}, '1N4007'),
        _c('D2', 'D', {'A': 'AC2', 'K': 'RECT+'}, '1N4007'),
        _c('D3', 'D', {'A': 'RECT-', 'K': 'AC1'}, '1N4007'),
        _c('D4', 'D', {'A': 'RECT-', 'K': 'AC2'}, '1N4007'),
        _c('C1', 'C', {'1': 'RECT+', '2': 'GND'}, '470u'),
        _c('U1', 'U', {'IN': 'RECT+', 'GND': 'GND', 'OUT': 'VOUT'}, '7805'),
        _c('C2', 'C', {'1': 'VOUT', '2': 'GND'}, '100n'),
        _c('D5', 'D', {'A': 'VOUT', 'K': 'LEDN'}, 'LED_rouge'),
        _c('R1', 'R', {'1': 'LEDN', '2': 'GND'}, '330'),
    ]


def circuit_capteur_seuil_aop():
    """Photoresistance + pont diviseur -> comparateur AOP -> sortie relais."""
    return [
        _c('R1', 'X', {'1': 'VCC', '2': 'SIG'}, '10k', categorie='Photoresistance'),
        _c('R2', 'R', {'1': 'SIG', '2': 'GND'}, '10k'),
        _c('R3', 'R', {'1': 'VCC', '2': 'REF'}, '10k'),
        _c('R4', 'R', {'1': 'REF', '2': 'GND'}, '10k'),
        _c('U1', 'U', {'IN+': 'SIG', 'IN-': 'REF', 'OUT': 'CMPOUT', 'V+': 'VCC', 'V-': 'GND'}, 'LM393'),
        _c('R5', 'R', {'1': 'VCC', '2': 'CMPOUT'}, '4.7k'),
    ]


def circuit_ampli_emetteur_commun():
    """Ampli BJT emetteur commun : pont de base, Rc/Re, Cin/Cout/Cbypass."""
    return [
        _c('Q1', 'Q', {'B': 'BASE', 'C': 'COL', 'E': 'EMET'}, '2N2222'),
        _c('R1', 'R', {'1': 'VCC', '2': 'BASE'}, '47k'),
        _c('R2', 'R', {'1': 'BASE', '2': 'GND'}, '10k'),
        _c('R3', 'R', {'1': 'VCC', '2': 'COL'}, '2.2k'),
        _c('R4', 'R', {'1': 'EMET', '2': 'GND'}, '1k'),
        _c('C1', 'C', {'1': 'VIN', '2': 'BASE'}, '1u'),
        _c('C2', 'C', {'1': 'COL', '2': 'VOUT'}, '1u'),
        _c('C3', 'C', {'1': 'EMET', '2': 'GND'}, '100u'),
    ]


def circuit_darlington_relais():
    """Driver relais darlington + diode de roue libre."""
    return [
        _c('Q1', 'Q', {'B': 'CMD', 'C': 'N1', 'E': 'GND'}, 'BC547'),
        _c('Q2', 'Q', {'B': 'N1', 'C': 'COIL', 'E': 'GND'}, 'BC547'),
        _c('R1', 'R', {'1': 'CMD', '2': 'GND'}, '10k'),
        _c('K1', 'K', {'1': 'VCC', '2': 'COIL', '3': 'COM', '4': 'NO'}, 'Relais_5V'),
        _c('D1', 'D', {'A': 'COIL', 'K': 'VCC'}, '1N4148'),
    ]


def circuit_optocoupleur():
    """Isolation galvanique : LED d'entree -> phototransistor -> pull-up sortie."""
    return [
        _c('R1', 'R', {'1': 'VIN', '2': 'A'}, '330'),
        _c('U1', 'U', {'A': 'A', 'K': 'GND1', 'C': 'VCC2', 'E': 'OUT'}, 'PC817'),
        _c('R2', 'R', {'1': 'VCC2', '2': 'OUT'}, '4.7k'),
    ]


def circuit_pont_wheatstone():
    """Pont de Wheatstone equilibre : 2 branches R1/R2 et R3/R4.

    [MODIF 2026-08-19] BUG TROUVE EN TESTANT : "VIN"/"VOUT" sont des ALIAS DE
    RAIL D'ALIMENTATION (cf. circuit_analyzer.patterns.base._ALIASES['power']),
    donc exclus de la connexite d'ilot -- un noeud SIGNAL de test doit utiliser
    un nom qui n'est PAS dans cette liste (ici "SIGIN"), sinon le pont se
    scindait en 2 ilots (R1+R2 / R3+R4) au lieu d'un seul.
    """
    return [
        _c('R1', 'R', {'1': 'SIGIN', '2': 'A'}, '1k'),
        _c('R2', 'R', {'1': 'A', '2': 'GND'}, '1k'),
        _c('R3', 'R', {'1': 'SIGIN', '2': 'B'}, '1k'),
        _c('R4', 'R', {'1': 'B', '2': 'GND'}, '1k'),
    ]


def circuit_filtre_rc_2_etages():
    """Filtre passe-bas RC en cascade (2 cellules).

    [MODIF 2026-08-19] "VIN"/"VOUT" -> "SIGIN"/"SIGOUT" (cf. commentaire de
    circuit_pont_wheatstone : ce sont des alias de rail, pas des noeuds signal)."""
    return [
        _c('R1', 'R', {'1': 'SIGIN', '2': 'N1'}, '1k'),
        _c('C1', 'C', {'1': 'N1', '2': 'GND'}, '100n'),
        _c('R2', 'R', {'1': 'N1', '2': 'SIGOUT'}, '1k'),
        _c('C2', 'C', {'1': 'SIGOUT', '2': 'GND'}, '100n'),
    ]


def circuit_regulateur_zener():
    """Regulateur shunt zener : Rserie + zener + charge.

    [MODIF 2026-08-19] "VOUT" -> "REGOUT" : le noeud regule doit rester un
    noeud SIGNAL normal pour que R1/D1/R2 soient bien dans le meme ilot (cf.
    commentaire de circuit_pont_wheatstone)."""
    return [
        _c('R1', 'R', {'1': 'VIN', '2': 'REGOUT'}, '220'),
        _c('D1', 'D', {'A': 'GND', 'K': 'REGOUT'}, 'Zener_5V1'),
        _c('R2', 'R', {'1': 'REGOUT', '2': 'GND'}, '1k'),
    ]


def circuit_indicateur_led():
    """LED + resistance de limitation, simple."""
    return [
        _c('D1', 'D', {'A': 'VCC', 'K': 'LEDN'}, 'LED_verte'),
        _c('R1', 'R', {'1': 'LEDN', '2': 'GND'}, '470'),
    ]


def circuit_decouplage_multi_c():
    """Reseau de decouplage : plusieurs C en //  sur VCC d'un CI."""
    return [
        _c('U1', 'U', {'VCC': 'VCC', 'GND': 'GND', 'A': 'NA', 'B': 'NB', 'Y': 'NY'}, '74HC08'),
        _c('C1', 'C', {'1': 'VCC', '2': 'GND'}, '100n'),
        _c('C2', 'C', {'1': 'VCC', '2': 'GND'}, '10u'),
    ]


def circuit_logique_cascade():
    """Deux portes logiques en cascade OUT(U1) -> IN(U2)."""
    return [
        _c('U1', 'U', {'A': 'IN1', 'B': 'IN2', 'Y': 'MID', 'VCC': 'VCC', 'GND': 'GND'}, '74HC00'),
        _c('U2', 'U', {'A': 'MID', 'B': 'MID', 'Y': 'OUT', 'VCC': 'VCC', 'GND': 'GND'}, '74HC00'),
    ]


def circuit_diviseur_parallele_double():
    """Deux paires de resistances vraiment en parallele (R1//R2 et R3//R4 distincts)."""
    return [
        _c('R1', 'R', {'1': 'A', '2': 'B'}, '10k'),
        _c('R2', 'R', {'1': 'A', '2': 'B'}, '10k'),
        _c('R3', 'R', {'1': 'C', '2': 'D'}, '4.7k'),
        _c('R4', 'R', {'1': 'C', '2': 'D'}, '4.7k'),
    ]


def circuit_aop_v_moins_flottant():
    """AOP alimentation simple : V- JAMAIS cablee (net dedie, personne d'autre)."""
    return [
        _c('U1', 'U', {'IN+': 'SIG', 'IN-': 'REF', 'OUT': 'OUT1', 'V+': 'VCC', 'V-': 'VMOINS_NC'}, 'LM358'),
        _c('R1', 'R', {'1': 'VCC', '2': 'SIG'}, '10k'),
        _c('R2', 'R', {'1': 'SIG', '2': 'GND'}, '10k'),
    ]


def circuit_aop_v_moins_cablee():
    """Variante : V- correctement cablee a la masse (double alimentation)."""
    return [
        _c('U1', 'U', {'IN+': 'SIG', 'IN-': 'REF', 'OUT': 'OUT1', 'V+': 'VCC', 'V-': 'GND'}, 'LM358'),
        _c('R1', 'R', {'1': 'VCC', '2': 'SIG'}, '10k'),
        _c('R2', 'R', {'1': 'SIG', '2': 'GND'}, '10k'),
        _c('R3', 'R', {'1': 'REF', '2': 'GND'}, '10k'),
    ]


def circuit_pont_appaire():
    """Pont resistif APPAIRE : R1 et R3 memes valeurs (10k), R2/R4 autres valeurs."""
    return [
        _c('R1', 'R', {'1': 'SIGIN', '2': 'A'}, '10k'),
        _c('R2', 'R', {'1': 'A', '2': 'GND'}, '2.2k'),
        _c('R3', 'R', {'1': 'SIGIN', '2': 'B'}, '10k'),
        _c('R4', 'R', {'1': 'B', '2': 'GND'}, '3.3k'),
    ]


def circuit_pont_desequilibre():
    """Meme topologie, valeurs toutes distinctes (aucune paire egale)."""
    return [
        _c('R1', 'R', {'1': 'SIGIN', '2': 'A'}, '10k'),
        _c('R2', 'R', {'1': 'A', '2': 'GND'}, '2.2k'),
        _c('R3', 'R', {'1': 'SIGIN', '2': 'B'}, '15k'),
        _c('R4', 'R', {'1': 'B', '2': 'GND'}, '3.3k'),
    ]


def circuit_pullup_et_gain():
    """R1 = pull-up haute valeur (100k), R2 = resistance de gain basse (1k)."""
    return [
        _c('R1', 'R', {'1': 'VCC', '2': 'SIG'}, '100k'),
        _c('R2', 'R', {'1': 'SIG', '2': 'GND'}, '1k'),
    ]


def circuit_boitier_8_broches():
    """CI a exactement 8 broches (NE555) + CI a 3 broches (regulateur) dans le meme ilot."""
    return [
        _c('U1', 'U', {'1': 'GND', '2': 'TT', '3': 'OUT', '4': 'VCC',
                       '5': 'CTRL', '6': 'TT', '7': 'DISCH', '8': 'VCC'}, 'NE555'),
        _c('U2', 'U', {'IN': 'VCC', 'GND': 'GND', 'OUT': 'TT'}, '7805'),
    ]


def circuit_cavalier_court_circuite():
    """Connecteur 3 broches : broches 1 et 2 court-circuitees (meme net), 3 isolee."""
    return [
        _c('J1', 'J', {'1': 'SHORT', '2': 'SHORT', '3': 'AUTRE'}, 'Cavalier'),
        _c('R1', 'R', {'1': 'AUTRE', '2': 'GND'}, '1k'),
    ]


def circuit_cavalier_ouvert():
    """Meme connecteur mais SANS court-circuit (3 broches sur 3 nets distincts)."""
    return [
        _c('J1', 'J', {'1': 'P1', '2': 'P2', '3': 'P3'}, 'Cavalier'),
        _c('R1', 'R', {'1': 'P3', '2': 'GND'}, '1k'),
    ]


def circuit_aop_in_moins_vers_vcc():
    """Montage FAUTIF : IN- de l'AOP directement relie a VCC (jamais un vrai comparateur)."""
    return [
        _c('U1', 'U', {'IN+': 'SIG', 'IN-': 'VCC', 'OUT': 'OUT1', 'V+': 'VCC', 'V-': 'GND'}, 'LM358'),
        _c('R1', 'R', {'1': 'VCC', '2': 'SIG'}, '10k'),
        _c('R2', 'R', {'1': 'SIG', '2': 'GND'}, '10k'),
    ]


def circuit_contre_reaction_aop():
    """AOP en ampli non-inverseur : Rf relie OUT a IN- (vraie contre-reaction)."""
    return [
        _c('U1', 'U', {'IN+': 'SIG', 'IN-': 'FB', 'OUT': 'OUT1', 'V+': 'VCC', 'V-': 'GND'}, 'LM358'),
        _c('RF', 'R', {'1': 'OUT1', '2': 'FB'}, '100k'),
        _c('RG', 'R', {'1': 'FB', '2': 'GND'}, '10k'),
    ]


def circuit_sans_contre_reaction():
    """AOP en comparateur simple : boucle ouverte, PAS de Rf entre OUT et IN-."""
    return [
        _c('U1', 'U', {'IN+': 'SIG', 'IN-': 'REF', 'OUT': 'OUT1', 'V+': 'VCC', 'V-': 'GND'}, 'LM358'),
        _c('R1', 'R', {'1': 'VCC', '2': 'REF'}, '10k'),
        _c('R2', 'R', {'1': 'REF', '2': 'GND'}, '10k'),
    ]


def circuit_mosfet_commutation():
    """Commutateur MOSFET cote bas + gate resistor + pull-down."""
    return [
        _c('M1', 'M', {'G': 'GATE', 'D': 'DRAIN', 'S': 'GND'}, 'IRLZ44N'),
        _c('R1', 'R', {'1': 'CMD', '2': 'GATE'}, '100'),
        _c('R2', 'R', {'1': 'GATE', '2': 'GND'}, '10k'),
    ]


def circuit_bobine_filtre_lc():
    """Filtre LC de sortie d'alim a decoupage."""
    return [
        _c('L1', 'L', {'1': 'SW', '2': 'VOUT'}, '100u'),
        _c('C1', 'C', {'1': 'VOUT', '2': 'GND'}, '220u'),
    ]


_TOUS_LES_CIRCUITS = [
    circuit_555_astable, circuit_alim_redressee_regulee, circuit_capteur_seuil_aop,
    circuit_ampli_emetteur_commun, circuit_darlington_relais, circuit_optocoupleur,
    circuit_pont_wheatstone, circuit_filtre_rc_2_etages, circuit_regulateur_zener,
    circuit_indicateur_led, circuit_decouplage_multi_c, circuit_logique_cascade,
    circuit_diviseur_parallele_double, circuit_aop_v_moins_flottant,
    circuit_aop_v_moins_cablee, circuit_pont_appaire, circuit_pont_desequilibre,
    circuit_pullup_et_gain, circuit_boitier_8_broches, circuit_cavalier_court_circuite,
    circuit_cavalier_ouvert, circuit_aop_in_moins_vers_vcc, circuit_contre_reaction_aop,
    circuit_sans_contre_reaction, circuit_mosfet_commutation, circuit_bobine_filtre_lc,
]


def _graphe(circuit_fn):
    return construire_graphe(circuit_fn())


def _matche(circuit_fn, definition: dict) -> bool:
    g = _graphe(circuit_fn)
    p = CustomCircuitPattern(definition)
    return len(p.match(g)) > 0


# =============================================================================
# Matrice de cas : (id, circuit, components requis, condition, attendu)
# =============================================================================

CAS_AU_MOINS_N = [
    ("555_au_moins_2R_vrai", circuit_555_astable, ["R"],
     {"kind": "au_moins_n", "type": "R", "n": 2, "comparateur": ">="}, True),
    ("555_au_moins_3R_faux", circuit_555_astable, ["R"],
     {"kind": "au_moins_n", "type": "R", "n": 3, "comparateur": ">="}, False),
    ("ampli_exactement_4R_vrai", circuit_ampli_emetteur_commun, ["R"],
     {"kind": "au_moins_n", "type": "R", "n": 4, "comparateur": "=="}, True),
    ("ampli_exactement_3R_faux", circuit_ampli_emetteur_commun, ["R"],
     {"kind": "au_moins_n", "type": "R", "n": 3, "comparateur": "=="}, False),
    ("filtre_au_plus_2C_vrai", circuit_filtre_rc_2_etages, ["C"],
     {"kind": "au_moins_n", "type": "C", "n": 2, "comparateur": "<="}, True),
    ("filtre_au_plus_1C_faux", circuit_filtre_rc_2_etages, ["C"],
     {"kind": "au_moins_n", "type": "C", "n": 1, "comparateur": "<="}, False),
    ("indicateur_plus_de_0D_vrai", circuit_indicateur_led, ["D"],
     {"kind": "au_moins_n", "type": "D", "n": 0, "comparateur": ">"}, True),
    ("indicateur_moins_de_1D_faux", circuit_indicateur_led, ["D"],
     {"kind": "au_moins_n", "type": "D", "n": 1, "comparateur": "<"}, False),
    ("capteur_photoR_categorie_vrai", circuit_capteur_seuil_aop, [{"type": "X", "categorie": "Photoresistance"}],
     {"kind": "au_moins_n", "type": "X", "categorie": "Photoresistance", "n": 1, "comparateur": "=="}, True),
    ("pont_4R_exactement_vrai", circuit_pont_wheatstone, ["R"],
     {"kind": "au_moins_n", "type": "R", "n": 4, "comparateur": "=="}, True),
]

CAS_EN_PARALLELE = [
    ("double_diviseur_R1R2_paralleles_vrai", circuit_diviseur_parallele_double, ["R"],
     {"kind": "en_parallele", "types": ["R", "R"]}, True),
    ("pont_wheatstone_pas_parallele_faux", circuit_pont_wheatstone, ["R"],
     {"kind": "en_parallele", "types": ["R", "R"]}, False),
    ("filtre_rc_pas_parallele_faux", circuit_filtre_rc_2_etages, ["R", "C"],
     {"kind": "en_parallele", "types": ["R", "C"]}, False),
    ("ampli_Rc_Re_pas_paralleles_faux", circuit_ampli_emetteur_commun, ["R"],
     {"kind": "en_parallele", "types": ["R", "R"]}, False),
    ("decouplage_C1C2_pas_paralleles_faux", circuit_decouplage_multi_c, ["C"],
     {"kind": "en_parallele", "types": ["C", "C"]}, False),
]

CAS_MEME_NOEUD = [
    ("capteur_photoR_et_R2_meme_noeud_vrai", circuit_capteur_seuil_aop, [{"type": "X", "categorie": "Photoresistance"}, "R"],
     {"kind": "meme_noeud", "types": ["X", "R"], "categories": ["Photoresistance", None]}, True),
    ("pont_R_partage_un_noeud_vrai", circuit_pont_wheatstone, ["R"],
     {"kind": "meme_noeud", "types": ["R", "R"]}, True),
    ("optocoupleur_R_U_meme_noeud_vrai", circuit_optocoupleur, ["R", "U"],
     {"kind": "meme_noeud", "types": ["R", "U"]}, True),
    ("indicateur_D_R_meme_noeud_vrai", circuit_indicateur_led, ["D", "R"],
     {"kind": "meme_noeud", "types": ["D", "R"]}, True),
    ("zener_R1_D1_meme_noeud_vrai", circuit_regulateur_zener, ["R", "D"],
     {"kind": "meme_noeud", "types": ["R", "D"]}, True),
]

CAS_EN_SERIE = [
    ("filtre_R1_en_serie_C1_vrai", circuit_filtre_rc_2_etages, ["R", "C"],
     {"kind": "en_serie", "type": "R"}, True),
    ("indicateur_R1_en_serie_D1_vrai", circuit_indicateur_led, ["R", "D"],
     {"kind": "en_serie", "type": "R"}, True),
    ("zener_R1_en_serie_vrai", circuit_regulateur_zener, ["R", "D"],
     {"kind": "en_serie", "type": "R"}, True),
    ("boitier_8broches_R_absente_faux", circuit_boitier_8_broches, ["U"],
     {"kind": "en_serie", "type": "R"}, False),
]

CAS_TYPE_ABSENT = [
    ("filtre_pas_de_transistor_vrai", circuit_filtre_rc_2_etages, ["R", "C"],
     {"kind": "type_absent", "types": ["Q", "M"]}, True),
    ("ampli_transistor_present_faux", circuit_ampli_emetteur_commun, ["Q"],
     {"kind": "type_absent", "types": ["Q"]}, False),
    ("darlington_transistor_present_faux", circuit_darlington_relais, ["Q"],
     {"kind": "type_absent", "types": ["Q", "M"]}, False),
    ("mosfet_M_present_faux", circuit_mosfet_commutation, ["M"],
     {"kind": "type_absent", "types": ["M"]}, False),
    ("pont_pas_de_diode_vrai", circuit_pont_wheatstone, ["R"],
     {"kind": "type_absent", "types": ["D"]}, True),
    ("indicateur_diode_presente_faux", circuit_indicateur_led, ["D"],
     {"kind": "type_absent", "types": ["D"]}, False),
]

CAS_CONTRE_REACTION = [
    ("aop_contre_reaction_vrai", circuit_contre_reaction_aop, ["U"],
     {"kind": "contre_reaction", "type": "U", "broche_source": "OUT", "broche_cible": "IN-"}, True),
    ("aop_sans_contre_reaction_faux", circuit_sans_contre_reaction, ["U"],
     {"kind": "contre_reaction", "type": "U", "broche_source": "OUT", "broche_cible": "IN-"}, False),
    ("aop_capteur_pas_de_Rf_faux", circuit_capteur_seuil_aop, ["U"],
     {"kind": "contre_reaction", "type": "U", "broche_source": "OUT", "broche_cible": "IN-"}, False),
]

CAS_BROCHE_NON_CONNECTEE = [
    ("aop_v_moins_flottante_vrai", circuit_aop_v_moins_flottant, ["U"],
     {"kind": "broche_non_connectee", "type": "U", "broche": "V-"}, True),
    ("aop_v_moins_cablee_faux", circuit_aop_v_moins_cablee, ["U"],
     {"kind": "broche_non_connectee", "type": "U", "broche": "V-"}, False),
    ("aop_capteur_v_moins_cablee_gnd_faux", circuit_capteur_seuil_aop, ["U"],
     {"kind": "broche_non_connectee", "type": "U", "broche": "V-"}, False),
]

CAS_VALEUR_COMPARE = [
    ("pullup_R1_gt_50k_vrai", circuit_pullup_et_gain, ["R"],
     {"kind": "valeur_compare", "type": "R", "seuil": 50000, "comparateur": ">"}, True),
    ("pullup_R2_gt_50k_faux_car_R1_matche_dabord", circuit_pullup_et_gain, ["R"],
     {"kind": "valeur_compare", "type": "R", "seuil": 500000, "comparateur": ">"}, False),
    ("zener_R1_220_lt_1k_vrai", circuit_regulateur_zener, ["R"],
     {"kind": "valeur_compare", "type": "R", "seuil": 1000, "comparateur": "<"}, True),
    ("zener_R2_egal_1k_vrai", circuit_regulateur_zener, ["R"],
     {"kind": "valeur_compare", "type": "R", "seuil": 1000, "comparateur": "=="}, True),
    ("555_C1_gt_1u_vrai", circuit_555_astable, ["C"],
     {"kind": "valeur_compare", "type": "C", "seuil": 0.000001, "comparateur": ">"}, True),
    ("555_C2_lt_1n_faux", circuit_555_astable, ["C"],
     {"kind": "valeur_compare", "type": "C", "seuil": 0.000000001, "comparateur": "<"}, False),
]

CAS_MEME_VALEUR = [
    ("pont_appaire_R1_R3_egaux_vrai", circuit_pont_appaire, ["R"],
     {"kind": "meme_valeur", "types": ["R", "R"]}, True),
    ("pont_desequilibre_aucune_paire_faux", circuit_pont_desequilibre, ["R"],
     {"kind": "meme_valeur", "types": ["R", "R"]}, False),
    ("double_diviseur_R1_R2_egaux_vrai", circuit_diviseur_parallele_double, ["R"],
     {"kind": "meme_valeur", "types": ["R", "R"]}, True),
    ("pont_wheatstone_toutes_1k_vrai", circuit_pont_wheatstone, ["R"],
     {"kind": "meme_valeur", "types": ["R", "R"]}, True),
]

CAS_NOMBRE_BROCHES = [
    ("boitier_555_8broches_vrai", circuit_boitier_8_broches, ["U"],
     {"kind": "nombre_broches", "type": "U", "n": 8, "comparateur": "=="}, True),
    ("boitier_555_pas_3broches_faux_car_555_matche", circuit_boitier_8_broches, ["U"],
     {"kind": "nombre_broches", "type": "U", "n": 8, "comparateur": ">="}, True),
    ("capteur_aop_5broches_vrai", circuit_capteur_seuil_aop, ["U"],
     {"kind": "nombre_broches", "type": "U", "n": 5, "comparateur": "=="}, True),
    ("capteur_aop_pas_8broches_faux", circuit_capteur_seuil_aop, ["U"],
     {"kind": "nombre_broches", "type": "U", "n": 8, "comparateur": "=="}, False),
    ("logique_cascade_moins_de_10broches_vrai", circuit_logique_cascade, ["U"],
     {"kind": "nombre_broches", "type": "U", "n": 10, "comparateur": "<"}, True),
]

CAS_CONNEXION_BROCHES_BASE = [
    ("optocoupleur_A_relie_R1_vrai", circuit_optocoupleur, ["U", "R"],
     {"kind": "connexion_broches",
      "cote_a": {"type": "U", "broches": ["A"]},
      "cote_b": {"type": "R", "broches": []}}, True),
    ("capteur_R1_relie_U1_INplus_vrai", circuit_capteur_seuil_aop, [{"type": "X", "categorie": "Photoresistance"}, "U"],
     {"kind": "connexion_broches",
      "cote_a": {"type": "X", "categorie": "Photoresistance", "broches": ["2"]},
      "cote_b": {"type": "U", "broches": ["IN+"]}}, True),
    ("capteur_R1_pas_relie_U1_INmoins_faux", circuit_capteur_seuil_aop, [{"type": "X", "categorie": "Photoresistance"}, "U"],
     {"kind": "connexion_broches",
      "cote_a": {"type": "X", "categorie": "Photoresistance", "broches": ["2"]},
      "cote_b": {"type": "U", "broches": ["IN-"]}}, False),
]

CAS_CONNEXION_BROCHES_SENS_MODE = [
    ("aop_in_moins_jamais_vers_vcc_vrai_cas_normal", circuit_capteur_seuil_aop, ["U"],
     {"kind": "connexion_broches", "sens": "jamais_connectee",
      "cote_a": {"type": "U", "broches": ["IN-"]},
      "cote_b": {"type": "U", "broches": ["V+"], "meme_composant": True}}, True),
    ("aop_in_moins_jamais_vers_vcc_faux_cas_fautif", circuit_aop_in_moins_vers_vcc, ["U"],
     {"kind": "connexion_broches", "sens": "jamais_connectee",
      "cote_a": {"type": "U", "broches": ["IN-"]},
      "cote_b": {"type": "U", "broches": ["V+"], "meme_composant": True}}, False),
    ("cavalier_mode_toutes_court_circuit_vrai", circuit_cavalier_court_circuite, ["J"],
     {"kind": "connexion_broches",
      "cote_a": {"type": "J", "broches": ["1", "2"], "mode": "toutes"},
      "cote_b": {"type": "J", "broches": [], "meme_composant": True}}, True),
    ("cavalier_mode_toutes_ouvert_faux", circuit_cavalier_ouvert, ["J"],
     {"kind": "connexion_broches",
      "cote_a": {"type": "J", "broches": ["1", "2"], "mode": "toutes"},
      "cote_b": {"type": "J", "broches": [], "meme_composant": True}}, False),
    ("cavalier_mode_au_moins_une_ouvert_faux_aussi", circuit_cavalier_ouvert, ["J"],
     {"kind": "connexion_broches",
      "cote_a": {"type": "J", "broches": ["1", "2"], "mode": "au_moins_une"},
      "cote_b": {"type": "J", "broches": [], "meme_composant": True}}, False),
    ("cavalier_jamais_court_circuite_vrai_car_ouvert", circuit_cavalier_ouvert, ["J"],
     {"kind": "connexion_broches", "sens": "jamais_connectee",
      "cote_a": {"type": "J", "broches": ["1", "2"], "mode": "toutes"},
      "cote_b": {"type": "J", "broches": [], "meme_composant": True}}, True),
    ("cavalier_jamais_court_circuite_faux_car_court_circuite", circuit_cavalier_court_circuite, ["J"],
     {"kind": "connexion_broches", "sens": "jamais_connectee",
      "cote_a": {"type": "J", "broches": ["1", "2"], "mode": "toutes"},
      "cote_b": {"type": "J", "broches": [], "meme_composant": True}}, False),
    ("darlington_B_jamais_court_circuitee_sur_C_vrai", circuit_darlington_relais, ["Q"],
     {"kind": "connexion_broches", "sens": "jamais_connectee",
      "cote_a": {"type": "Q", "broches": ["B"]},
      "cote_b": {"type": "Q", "broches": ["C"], "meme_composant": True}}, True),
]


# =============================================================================
# Generation automatique (correcte par construction) : les 5 comparateurs de
# au_moins_n/nombre_broches/valeur_compare a la frontiere exacte (n-1, n, n+1),
# derives des VRAIS comptages/valeurs de chaque chaine -- volume important sans
# risque d'erreur de calcul manuel (le comptage est fait par le test lui-meme,
# pas recopie a la main).
# =============================================================================
from circuit_analyzer.value_parser import parse_valeur  # noqa: E402

_COMPARATEURS_TEST = {
    ">=": lambda a, b: a >= b, "==": lambda a, b: a == b, "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b, "<": lambda a, b: a < b,
}


def _slug(comparateur):
    return comparateur.replace('=', 'eq').replace('<', 'lt').replace('>', 'gt')


def _requis_entry(t, cat):
    return {"type": t, "categorie": cat} if cat else t


def _profil_par_ilot(fn):
    """@brief {(type, categorie|None) -> [compte par ilot contenant ce couple]}.

    [MODIF 2026-08-19] BUG TROUVE EN TESTANT (generateur automatique) : deux
    ecueils decouverts en generant des cas au_moins_n a partir de comptages
    "evidents" :
      1. au_moins_n ne voit que les composants d'un MEME ilot (match() boucle
         sur detecter_ilots) -- un compte GLOBAL (toute la chaine) surestime
         quand la chaine se scinde en plusieurs ilots (ex.
         circuit_alim_redressee_regulee : "VOUT" est un alias de rail -> pont
         redresseur et indicateur LED sont deux ilots distincts). Il faut le
         DECOUPAGE REEL, pas un total.
      2. un type 'X' (photoresistance, etc.) SANS categorie declenche le garde
         anti-"inconnu generique" de CustomCircuitPattern.match() (retourne
         toujours [] cf. commentaire 2026-08-18 dans loader.py) -- regrouper
         par (type, categorie) et non par type seul evite de generer un cas
         que le moteur rejette structurellement avant meme d'evaluer la
         condition.
    """
    from circuit_analyzer.ilots import detecter_ilots
    comps = fn()
    g = construire_graphe(comps)
    par_ref = {c.ref: c for c in comps}
    profil: dict = {}
    for ilot in detecter_ilots(g, []):
        comptes_ilot: dict = {}
        for ref in ilot.get("composants", []):
            c = par_ref.get(ref)
            if c is None:
                continue
            cle = (c.type, c.categorie or None)
            comptes_ilot[cle] = comptes_ilot.get(cle, 0) + 1
        for cle, n in comptes_ilot.items():
            profil.setdefault(cle, []).append(n)
    return profil


def _generer_cas_au_moins_n():
    cas = []
    for fn in _TOUS_LES_CIRCUITS:
        for (t, cat), comptes_par_ilot in _profil_par_ilot(fn).items():
            n_max = max(comptes_par_ilot)
            for seuil in (n_max - 1, n_max, n_max + 1):
                if seuil < 0:
                    continue
                for comparateur, f in _COMPARATEURS_TEST.items():
                    # "any ilot" : au_moins_n matche des qu'AU MOINS UN ilot
                    # satisfait -- jamais seulement celui du compte max (un
                    # petit ilot separe peut, lui, satisfaire un "<").
                    attendu = any(f(n, seuil) for n in comptes_par_ilot)
                    cond = {"kind": "au_moins_n", "type": t, "n": seuil, "comparateur": comparateur}
                    if cat:
                        cond["categorie"] = cat
                    cid = f"auto_au_moins_n_{fn.__name__}_{t}{'_' + cat if cat else ''}_{_slug(comparateur)}_{seuil}"
                    cas.append((cid, fn, [_requis_entry(t, cat)], cond, attendu))
    return cas


def _generer_cas_nombre_broches():
    cas = []
    for fn in _TOUS_LES_CIRCUITS:
        comps = fn()
        valeurs_par_type: dict = {}
        for c in comps:
            valeurs_par_type.setdefault((c.type, c.categorie or None), []).append(len(c.pins))
        for (t, cat), valeurs in valeurs_par_type.items():
            n_max = max(valeurs)
            for seuil in (n_max - 1, n_max, n_max + 1):
                if seuil < 0:
                    continue
                for comparateur, f in _COMPARATEURS_TEST.items():
                    # nombre_broches teste CHAQUE composant du type -- "any"
                    # sur toutes les instances (memes types de valeurs de pins
                    # differentes dans un meme ilot, cf. circuit_boitier_8_broches).
                    attendu = any(f(v, seuil) for v in valeurs)
                    cond = {"kind": "nombre_broches", "type": t, "n": seuil, "comparateur": comparateur}
                    if cat:
                        cond["categorie"] = cat
                    cid = f"auto_nb_broches_{fn.__name__}_{t}{'_' + cat if cat else ''}_{_slug(comparateur)}_{seuil}"
                    cas.append((cid, fn, [_requis_entry(t, cat)], cond, attendu))
    return cas


def _generer_cas_valeur_compare():
    cas = []
    for fn in _TOUS_LES_CIRCUITS:
        comps = fn()
        valeurs_par_type: dict = {}
        for c in comps:
            if c.type not in ("R", "C", "L"):
                continue
            v = parse_valeur(c.value)
            if v is None:
                continue
            valeurs_par_type.setdefault((c.type, c.categorie or None), []).append(v)
        for (t, cat), valeurs in valeurs_par_type.items():
            v_min, v_max = min(valeurs), max(valeurs)
            for facteur, comparateur in (
                (0.5, ">"), (2.0, ">"), (0.5, "<"), (2.0, "<"), (1.0, "=="),
            ):
                # seuil derive du min/max REEL du groupe (pas d'une instance
                # isolee) : plusieurs R du meme type dans le meme ilot
                # partagent le meme `found` cote moteur (cf. _profil_par_ilot).
                base = v_min if facteur >= 1.0 else v_max
                seuil = base * facteur
                attendu = any(_COMPARATEURS_TEST[comparateur](v, seuil) for v in valeurs)
                cond = {"kind": "valeur_compare", "type": t, "seuil": seuil, "comparateur": comparateur}
                if cat:
                    cond["categorie"] = cat
                cid = f"auto_valeur_{fn.__name__}_{t}{'_' + cat if cat else ''}_{_slug(comparateur)}_{facteur}"
                cas.append((cid, fn, [_requis_entry(t, cat)], cond, attendu))
    return cas


def _generer_cas_type_absent():
    cas = []
    tous_types = set("RCLDQMUKFXJ")
    for fn in _TOUS_LES_CIRCUITS:
        comps = fn()
        # Type de "remplissage" (pour passer le filtre found_partout non-vide) :
        # jamais un 'X' NU -- meme garde anti-"inconnu generique" que ci-dessus.
        non_x = [c for c in comps if c.type != 'X']
        remplissage = _requis_entry(non_x[0].type, non_x[0].categorie or None) if non_x else (
            _requis_entry(comps[0].type, comps[0].categorie or None) if comps else None)
        if remplissage is None:
            continue
        presents = {c.type for c in comps}
        absents = sorted(tous_types - presents)
        for t in [tt for tt in presents if tt != 'X'][:2]:
            cid = f"auto_type_absent_{fn.__name__}_{t}_present_faux"
            cas.append((cid, fn, [t], {"kind": "type_absent", "types": [t]}, False))
        for t in absents[:2]:
            cid = f"auto_type_absent_{fn.__name__}_{t}_absent_vrai"
            cas.append((cid, fn, [remplissage], {"kind": "type_absent", "types": [t]}, True))
    return cas


CAS_AUTO_AU_MOINS_N = _generer_cas_au_moins_n()
CAS_AUTO_NOMBRE_BROCHES = _generer_cas_nombre_broches()
CAS_AUTO_VALEUR_COMPARE = _generer_cas_valeur_compare()
CAS_AUTO_TYPE_ABSENT = _generer_cas_type_absent()


def _flatten(groupes):
    out = []
    for groupe in groupes:
        for (case_id, circuit_fn, requis, cond, attendu) in groupe:
            out.append(pytest.param(circuit_fn, requis, cond, attendu, id=case_id))
    return out


_TOUTES_LES_CONDITIONS = _flatten([
    CAS_AU_MOINS_N, CAS_EN_PARALLELE, CAS_MEME_NOEUD, CAS_EN_SERIE, CAS_TYPE_ABSENT,
    CAS_CONTRE_REACTION, CAS_BROCHE_NON_CONNECTEE, CAS_VALEUR_COMPARE, CAS_MEME_VALEUR,
    CAS_NOMBRE_BROCHES, CAS_CONNEXION_BROCHES_BASE, CAS_CONNEXION_BROCHES_SENS_MODE,
    CAS_AUTO_AU_MOINS_N, CAS_AUTO_NOMBRE_BROCHES, CAS_AUTO_VALEUR_COMPARE, CAS_AUTO_TYPE_ABSENT,
])


@pytest.mark.parametrize("circuit_fn,requis,condition,attendu", _TOUTES_LES_CONDITIONS)
def test_condition_generique_sur_chaine_reelle(circuit_fn, requis, condition, attendu):
    """Chaque condition generique parametree, evaluee sur une CHAINE reelle
    multi-etages (pas une fixture jouet isolee) via CustomCircuitPattern.match()."""
    definition = {"name": "test-volumique", "components": requis, "conditions": [condition]}
    assert _matche(circuit_fn, definition) == attendu, (
        f"condition={condition!r} sur {circuit_fn.__name__} : attendu {attendu}"
    )


# =============================================================================
# Filet de securite corpus : chaque chaine, quel que soit le kind, doit rester
# ANALYSABLE (aucune exception, ilots non vides) -- regression directe du bug
# "test impedances" corrige dans custom_circuits.json (un pattern residuel trop
# generique avalait silencieusement des composants reels de N'IMPORTE QUEL
# schema, cf. reel_555_astable.xml -- 10/11 echecs de baseline de ce depot).
# =============================================================================

@pytest.mark.parametrize("circuit_fn", _TOUS_LES_CIRCUITS, ids=lambda f: f.__name__)
def test_chaine_analysable_sans_perte_de_composant(circuit_fn):
    from circuit_analyzer.detecteur import analyser

    comps = circuit_fn()
    g = construire_graphe(comps)
    res = analyser(g)
    tous_les_refs = {c.ref for c in comps}
    refs_dans_ilots = set()
    for ilot in res.ilots:
        refs_dans_ilots.update(ilot.get("composants", []))
    manquants = tous_les_refs - refs_dans_ilots
    assert not manquants, (
        f"{circuit_fn.__name__} : composants absents de tout ilot -> {sorted(manquants)}"
    )
