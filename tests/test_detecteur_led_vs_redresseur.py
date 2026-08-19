"""
@file test_detecteur_led_vs_redresseur.py
@brief Verifie que `detecteur.detecter_redresseur_simple` ne confond plus un
indicateur LED (diode+R vers GND, montage "sink") avec un vrai redresseur
simple alternance -- les deux montages sont topologiquement identiques,
seule la nature reelle de la diode (categorie/value) permet de trancher.

Bug trouve en testant une chaine complete capteur->seuil->indicateur : une
LED alimentee via une resistance de tirage vers un noeud intermediaire NON
nomme comme un rail connu (ex. "LEDA", au lieu de "VCC") passait le filtre
`est_alimentation(anode)` existant et ressortait a tort en
« Redresseur simple alternance ». Cf. `detecteur._est_led`.
"""
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.detecteur import detecter_redresseur_simple


def _c(ref, type_, pins, value='', categorie=''):
    return Composant(ref=ref, type=type_, pins=pins, value=value, categorie=categorie)


def test_led_indicateur_alimente_par_tirage_nest_pas_un_redresseur():
    """@brief LED (value porte 'LED') + R vers GND, anode sur noeud non-rail."""
    comps = [
        _c('R2', 'R', {'1': 'VCC', '2': 'LEDA'}, '1k'),
        _c('D5', 'D', {'A': 'LEDA', 'K': 'LEDN'}, 'LED_rouge'),
        _c('R1', 'R', {'1': 'LEDN', '2': 'GND'}, '330'),
    ]
    assert detecter_redresseur_simple(construire_graphe(comps)) == []


def test_led_identifiee_par_categorie_seule_nest_pas_un_redresseur():
    """@brief `value` ne mentionne pas 'LED' -- seule `categorie` (bibliotheque
    reelle) porte le signal."""
    comps = [
        _c('R4', 'R', {'1': 'VCC', '2': 'LEDB'}, '1k'),
        _c('D7', 'D', {'A': 'LEDB', 'K': 'LEDC'}, 'K1N', categorie='LED verte 5mm'),
        _c('R5', 'R', {'1': 'LEDC', '2': 'GND'}, '220'),
    ]
    assert detecter_redresseur_simple(construire_graphe(comps)) == []


def test_diode_signal_generique_meme_topologie_reste_un_redresseur():
    """@brief Non-regression : une diode de redressement reelle (1N4007), MEME
    topologie (serie + R vers GND), doit toujours matcher."""
    comps = [
        _c('D6', 'D', {'A': 'AC_IN', 'K': 'RECT_OUT'}, '1N4007'),
        _c('R3', 'R', {'1': 'RECT_OUT', '2': 'GND'}, '1k'),
    ]
    matches = detecter_redresseur_simple(construire_graphe(comps))
    assert len(matches) == 1
    assert matches[0]['circuit_type'] == 'Redresseur simple alternance'
    assert set(matches[0]['components']) == {'D6', 'R3'}


def test_diode_sans_categorie_ni_led_dans_value_reste_un_redresseur():
    """@brief Non-regression : diode sans info catalogue (categorie/value vides
    hors 'D1') doit toujours matcher -- comportement historique inchange."""
    comps = [
        _c('D1', 'D', {'A': 'NET_AC', 'K': 'NET_DC'}),
        _c('R1', 'R', {'1': 'NET_DC', '2': 'GND'}, '1k'),
    ]
    matches = detecter_redresseur_simple(construire_graphe(comps))
    assert len(matches) == 1
