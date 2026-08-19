"""
@file test_gabarit.py
@brief Tests du moteur de correspondance par gabarit XML (Phase 1, chantier
"gabarits-xml-montages-canoniques" -- voir docs/superpowers/plans).
"""
import os

import pytest

from circuit_analyzer.gabarit import charger_gabarit
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.parser import Component

_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "patterns_reference")
_SUIVEUR = os.path.join(_DIR, "Suiveur de tension.xml")
_INVERSEUR = os.path.join(_DIR, "Amplificateur inverseur.xml")
_SOMMATEUR = os.path.join(_DIR, "Amplificateur sommateur.xml")


def test_gabarit_charge_suiveur_et_matche_un_suiveur_reel():
    gab = charger_gabarit(_SUIVEUR)
    assert gab is not None
    cible = [Component('U9', 'U', {'IN+': 'IN_A', 'IN-': 'OUT_A', 'OUT': 'OUT_A',
                                   'V+': 'VCC', 'V-': 'GND'})]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1
    assert matches[0]['circuit_type'] == 'Suiveur de tension'
    assert matches[0]['components'] == ['U9']


def test_gabarit_suiveur_ne_matche_pas_un_inverseur():
    gab = charger_gabarit(_SUIVEUR)
    assert gab is not None
    cible = [
        Component('U9', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert matches == []


def test_gabarit_charge_inverseur_et_matche():
    gab = charger_gabarit(_INVERSEUR)
    assert gab is not None
    cible = [
        Component('U9', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R7', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('R8', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '22k'),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1
    assert matches[0]['circuit_type'] == 'Amplificateur inverseur'
    assert set(matches[0]['components']) == {'U9', 'R7', 'R8'}


def test_gabarit_inverseur_ne_matche_pas_un_suiveur():
    gab = charger_gabarit(_INVERSEUR)
    assert gab is not None
    cible = [Component('U1', 'U', {'IN+': 'IN', 'IN-': 'OUT', 'OUT': 'OUT',
                                   'V+': 'VCC', 'V-': 'GND'})]
    matches = gab.correspondre(construire_graphe(cible))
    assert matches == []


def test_gabarit_fichier_vide_rejete(tmp_path):
    """@brief Aucun composant du tout -> aucune ancre possible, quel que soit
    le seuil de broches."""
    from circuit_analyzer.xml import generer_xml
    xml = generer_xml([])
    p = tmp_path / "vide.xml"
    p.write_text(xml, encoding="utf-8")
    assert charger_gabarit(str(p)) is None


def test_gabarit_ambigu_deux_ancres_meme_nombre_de_broches_rejete(tmp_path):
    """@brief BUG TROUVE EN TESTANT (lot 4, montages diode) : l'ancre est
    choisie par le NOMBRE MAXIMAL de broches du fichier (pas un seuil fixe,
    voir charger_gabarit) -- deux composants DIFFERENTS de types mais a
    EGALITE sur ce max (ici 2 AOP a 5 broches chacun, comme avant ; mais le
    meme principe s'applique a 2 composants a 2 broches chacun, ex. une
    diode ET une resistance dans le meme fichier -- voir
    test_gabarit_diode_plus_resistance_reste_ambigu) doit rester rejete,
    jamais devine."""
    from circuit_analyzer.xml import generer_xml
    xml = generer_xml([
        Component('U1', 'U', {'IN+': 'A', 'IN-': 'B', 'OUT': 'C', 'V+': 'VCC', 'V-': 'GND'}),
        Component('U2', 'U', {'IN+': 'D', 'IN-': 'E', 'OUT': 'F', 'V+': 'VCC', 'V-': 'GND'}),
    ])
    p = tmp_path / "deux_ancres.xml"
    p.write_text(xml, encoding="utf-8")
    assert charger_gabarit(str(p)) is None


def test_gabarit_diode_seule_devient_une_ancre_valide(tmp_path):
    """@brief BUG CORRIGE (lot 4) : un composant a SEULEMENT 2 broches
    (une diode) doit pouvoir devenir une ancre valide s'il est le SEUL
    composant du fichier (max de broches = 2, aucune egalite) -- l'ancien
    seuil fixe ">= 3 broches" l'excluait par construction, rendant tout
    montage ancre sur une diode seule impossible a migrer."""
    from circuit_analyzer.xml import generer_xml
    xml = generer_xml([Component('D1', 'D', {'A': 'NET_A', 'K': 'NET_K'}, '1N4148')])
    p = tmp_path / "diode_seule.xml"
    p.write_text(xml, encoding="utf-8")
    gab = charger_gabarit(str(p))
    assert gab is not None
    assert gab.ancre.type == 'D'


def test_gabarit_diode_plus_resistance_choisit_la_diode_comme_ancre(tmp_path):
    """@brief [MODIF 2026-08-17] Lot 9c : une diode ET une resistance a
    EGALITE (2 broches chacune) choisit desormais la diode comme ancre --
    bris d'egalite NARROW (voir docstring de charger_gabarit), motive par
    le fait que TOUS les montages diode+1-passif (roue libre, ESD deja
    migres avec une diode SEULE ; redresseur simple/detecteur de crete,
    diode+R ou diode+C) sont electriquement centres sur la diode. Ancien
    comportement (rejet ambigu) documente comme regression VOULUE dans
    test_gabarit_deux_diodes_a_egalite_reste_ambigu ci-dessous : le bris
    d'egalite ne s'applique QUE si un seul des deux candidats est 'D'."""
    from circuit_analyzer.xml import generer_xml
    xml = generer_xml([
        Component('D1', 'D', {'A': 'NET_A', 'K': 'NET_K'}, '1N4148'),
        Component('R1', 'R', {'1': 'NET_K', '2': 'GND'}, '10k'),
    ])
    p = tmp_path / "diode_plus_r.xml"
    p.write_text(xml, encoding="utf-8")
    gab = charger_gabarit(str(p))
    assert gab is not None
    assert gab.ancre.type == 'D'
    assert gab.ancre.ref == 'D1'


def test_gabarit_deux_diodes_a_egalite_reste_ambigu(tmp_path):
    """@brief DEUX diodes a egalite (un vrai montage a 2 diodes, ex. un
    doubleur de tension) reste rejete comme ambigu -- le bris d'egalite ne
    doit jamais deviner LAQUELLE des deux diodes est l'ancre."""
    from circuit_analyzer.xml import generer_xml
    xml = generer_xml([
        Component('D1', 'D', {'A': 'NET_A', 'K': 'NET_K'}, '1N4148'),
        Component('D2', 'D', {'A': 'NET_K', 'K': 'NET_B'}, '1N4148'),
    ])
    p = tmp_path / "deux_diodes.xml"
    p.write_text(xml, encoding="utf-8")
    assert charger_gabarit(str(p)) is None


def test_gabarit_fichier_absent_rejete():
    assert charger_gabarit("chemin/qui/nexiste/pas.xml") is None


def test_gabarit_ignore_les_valeurs():
    """@brief Les valeurs (10k vs 47k) ne doivent JAMAIS empecher un match --
    seule la structure (types + roles) compte, comme les detecteurs Python
    existants."""
    gab = charger_gabarit(_INVERSEUR)
    cible = [
        Component('U9', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R7', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '47k'),   # valeur differente du gabarit
        Component('R8', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '999R'),  # valeur differente du gabarit
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1


def test_gabarit_positions_canoniques_translate_depuis_lancre():
    gab = charger_gabarit(_INVERSEUR)
    cible = [
        Component('U9', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R7', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('R8', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '22k'),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1
    positions = gab.positions_canoniques(matches[0], x=5000, y=5000)
    assert set(positions) == {'U9', 'R7', 'R8'}
    # L'ancre (U9) doit atterrir exactement a l'origine demandee.
    assert positions['U9'] == (5000, 5000)
    # Les positions des voisins restent DISTINCTES de celle de l'ancre
    # (translation reelle, pas tout au meme point).
    assert positions['R7'] != positions['U9']
    assert positions['R8'] != positions['U9']


# ── Phase 2 : inference de repetition (gabarit "Amplificateur sommateur") ──

def test_gabarit_sommateur_matche_avec_2_entrees():
    """Le gabarit dessine 3 entrees (illustratif) -- une cible a 2 entrees
    SEULEMENT doit deja matcher : la regle se generalise en "2 ou plus" des
    qu'une repetition (2+) apparait dans le gabarit, reproduit fidelement
    `detecter_amplificateur_sommateur` (`len(zin) >= 2`)."""
    gab = charger_gabarit(_SOMMATEUR)
    assert gab is not None
    cible = [
        Component('U9', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_INV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_B', '2': 'NET_INV'}, '10k'),
        Component('RF', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'U9', 'R1', 'R2', 'RF'}


def test_gabarit_sommateur_matche_avec_5_entrees():
    """Une cible a PLUS d'entrees que l'exemple du gabarit (3) doit aussi
    matcher -- la repetition n'est jamais bornee par le compte exact dessine."""
    gab = charger_gabarit(_SOMMATEUR)
    cible = [
        Component('U9', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        *[Component(f'R{i}', 'R', {'1': f'NET_IN{i}', '2': 'NET_INV'}, '10k')
          for i in range(5)],
        Component('RF', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1
    assert len(matches[0]['components']) == 1 + 5 + 1


def test_gabarit_sommateur_ne_matche_pas_avec_1_seule_entree():
    """BUG EVITE EN CONCEVANT (pas seulement trouve en testant) : avec 1 seule
    resistance d'entree, la cible est un Amplificateur INVERSEUR, pas un
    sommateur -- le seuil de repetition doit etre 2, jamais 1, sinon le
    gabarit sommateur avalerait aussi tous les inverseurs (faux positif entre
    deux montages deja distincts cote detecteurs Python)."""
    gab = charger_gabarit(_SOMMATEUR)
    cible = [
        Component('U9', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('RF', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert matches == []


def test_gabarit_rail_partage_ailleurs_sur_la_carte_ne_casse_pas_le_match():
    """@brief BUG TROUVE EN TESTANT (reproduit AVANT correction avec un cas
    minimal) : une broche directement sur GND (ex. IN+ d'un inverseur) ne
    doit JAMAIS dependre de ce qui est connecte AILLEURS sur ce meme rail
    partage -- sur une vraie carte scannee, GND porte presque toujours des
    dizaines de composants sans rapport. Avant correction, un decouplage
    C99 (VCC-GND) SANS AUCUN LIEN avec l'ampli suffisait a faire echouer le
    match d'un inverseur pourtant parfaitement valide."""
    gab = charger_gabarit(_INVERSEUR)
    cible = [
        Component('U9', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R7', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('R8', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '22k'),
        Component('C99', 'C', {'1': 'VCC', '2': 'GND'}, '100nF'),   # sans rapport, meme rail GND
        Component('R99', 'R', {'1': 'NET_AUTRE', '2': 'GND'}, '4k7'),  # idem
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'U9', 'R7', 'R8'}


def test_gabarit_broche_vide_rejette_tout_voisin_supplementaire(tmp_path):
    """@brief Un gabarit dont une broche ne montre AUCUN voisin dessine (ex.
    OUT d'un futur "Comparateur", libre de toute contre-reaction) doit
    rejeter une cible qui a QUAND MEME quelque chose branche dessus --
    sinon un montage avec contre-reaction matcherait a tort un gabarit
    "sans contre-reaction"."""
    from circuit_analyzer.xml import generer_xml
    bare = generer_xml([Component('U1', 'U', {'IN+': 'NET1', 'IN-': 'NET2', 'OUT': 'NET3',
                                              'V+': 'VCC', 'V-': 'GND'})])
    p = tmp_path / "bare_aop.xml"
    p.write_text(bare, encoding="utf-8")
    gab = charger_gabarit(str(p))
    assert gab is not None

    # Cible IDENTIQUE en structure (rien branche nulle part) -> doit matcher.
    cible_nue = [Component('U9', 'U', {'IN+': 'NET_A', 'IN-': 'NET_B', 'OUT': 'NET_C',
                                       'V+': 'VCC', 'V-': 'GND'})]
    assert len(gab.correspondre(construire_graphe(cible_nue))) == 1

    # Cible avec une R EN TROP entre OUT et IN- (contre-reaction) -> ne doit
    # PLUS matcher : le gabarit "bare" n'a RIEN dessine sur ces broches.
    cible_avec_feedback = [
        Component('U9', 'U', {'IN+': 'NET_A', 'IN-': 'NET_B', 'OUT': 'NET_C',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('RF', 'R', {'1': 'NET_C', '2': 'NET_B'}, '10k'),
    ]
    assert gab.correspondre(construire_graphe(cible_avec_feedback)) == []


def test_gabarit_sommateur_positions_empilent_les_entrees_sans_les_superposer():
    gab = charger_gabarit(_SOMMATEUR)
    cible = [
        Component('U9', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        *[Component(f'R{i}', 'R', {'1': f'NET_IN{i}', '2': 'NET_INV'}, '10k')
          for i in range(4)],
        Component('RF', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    positions = gab.positions_canoniques(matches[0], x=0, y=0)
    entrees = [positions[f'R{i}'] for i in range(4)]
    assert len(set(entrees)) == 4, f"les 4 entrees ne devraient jamais se superposer : {entrees}"
