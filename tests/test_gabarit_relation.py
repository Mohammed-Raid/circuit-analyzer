"""
@file test_gabarit_relation.py
@brief Tests du moteur de correspondance a DEUX ancres (lot "relations",
chantier "gabarits-xml-montages-canoniques" -- voir docs/superpowers/plans).
Mecanisme ADDITIF, separe du moteur a une seule ancre (gabarit.Gabarit).
"""
import os

from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.gabarit import charger_gabarit_relation
from circuit_analyzer.parser import Component

_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "patterns_reference")
_MIROIR = os.path.join(_DIR, "Miroir de courant BJT.xml")
_PUSHPULL = os.path.join(_DIR, "Etage push-pull.xml")
_DARLINGTON = os.path.join(_DIR, "Paire Darlington.xml")


def test_gabarit_relation_miroir_charge_et_matche():
    gab = charger_gabarit_relation(_MIROIR)
    assert gab is not None
    cible = [
        Component('Q9', 'Q', {'B': 'NET_B', 'C': 'VCC', 'E': 'GND'}),
        Component('Q10', 'Q', {'B': 'NET_B', 'C': 'NET_LOAD', 'E': 'GND'}),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'Q9', 'Q10'}


def test_gabarit_relation_miroir_ne_matche_pas_bases_differentes():
    gab = charger_gabarit_relation(_MIROIR)
    cible = [
        Component('Q9', 'Q', {'B': 'NET_B1', 'C': 'VCC', 'E': 'GND'}),
        Component('Q10', 'Q', {'B': 'NET_B2', 'C': 'NET_LOAD', 'E': 'GND'}),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert matches == []


def test_gabarit_relation_miroir_symetrique_ne_matche_pas_deux_fois():
    """@brief BUG A EVITER (verifie explicitement) : une relation SYMETRIQUE
    (Q1<->Q2 interchangeables) essaie les deux paires ordonnees en interne
    -- doit rapporter la paire UNE SEULE fois, pas deux."""
    gab = charger_gabarit_relation(_MIROIR)
    cible = [
        Component('Q9', 'Q', {'B': 'NET_B', 'C': 'VCC', 'E': 'GND'}),
        Component('Q10', 'Q', {'B': 'NET_B', 'C': 'NET_LOAD', 'E': 'GND'}),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1


def test_gabarit_relation_darlington_directionnel_charge_et_matche():
    gab = charger_gabarit_relation(_DARLINGTON)
    assert gab is not None
    cible = [
        Component('Q9', 'Q', {'B': 'NET_IN', 'C': 'VCC', 'E': 'NET_LIEN'}),
        Component('Q10', 'Q', {'B': 'NET_LIEN', 'C': 'VCC', 'E': 'NET_OUT'}),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'Q9', 'Q10'}


def test_gabarit_relation_darlington_est_bien_directionnel():
    """@brief Le sens compte : E(Q1)->B(Q2), PAS B(Q1)<-E(Q2). Une paire ou
    la relation est inversee (E(Q10)->B(Q9) au lieu de E(Q9)->B(Q10)) est
    en realite juste la MEME structure lue dans l'autre sens -- le moteur
    essaie les deux ordres (Q9,Q10) et (Q10,Q9), donc DEVRAIT matcher
    quand meme (le Darlington n'exige pas de savoir lequel est "Q1" dans
    l'absolu, juste que la relation E->B existe dans un sens ou l'autre).
    Ce test verifie que ca matche -- confirme que l'essai des deux ordres
    fonctionne pour une relation directionnelle."""
    gab = charger_gabarit_relation(_DARLINGTON)
    cible = [
        Component('Q9', 'Q', {'B': 'NET_LIEN', 'C': 'VCC', 'E': 'NET_OUT'}),
        Component('Q10', 'Q', {'B': 'NET_IN', 'C': 'VCC', 'E': 'NET_LIEN'}),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1


def test_gabarit_relation_darlington_ne_matche_pas_sans_lien_base_emetteur():
    """@brief Deux transistors independants (aucun lien E->B) ne doivent
    JAMAIS matcher le gabarit Darlington."""
    gab = charger_gabarit_relation(_DARLINGTON)
    cible = [
        Component('Q9', 'Q', {'B': 'NET_A', 'C': 'VCC', 'E': 'NET_B'}),
        Component('Q10', 'Q', {'B': 'NET_C', 'C': 'VCC', 'E': 'NET_D'}),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert matches == []


def test_gabarit_relation_pushpull_charge_et_matche():
    gab = charger_gabarit_relation(_PUSHPULL)
    assert gab is not None
    cible = [
        Component('Q9', 'Q', {'B': 'NET_B1', 'C': 'VCC', 'E': 'NET_OUT'}),
        Component('Q10', 'Q', {'B': 'NET_B2', 'C': 'GND', 'E': 'NET_OUT'}),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1


def test_gabarit_relation_pushpull_ne_matche_pas_emetteurs_differents():
    gab = charger_gabarit_relation(_PUSHPULL)
    cible = [
        Component('Q9', 'Q', {'B': 'NET_B1', 'C': 'VCC', 'E': 'NET_OUT1'}),
        Component('Q10', 'Q', {'B': 'NET_B2', 'C': 'GND', 'E': 'NET_OUT2'}),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert matches == []


def test_gabarit_relation_fichier_ambigu_1_seule_ancre_rejete(tmp_path):
    from circuit_analyzer.xml import generer_xml
    xml = generer_xml([Component('Q1', 'Q', {'B': 'A', 'C': 'B', 'E': 'GND'})])
    p = tmp_path / "un_seul.xml"
    p.write_text(xml, encoding="utf-8")
    assert charger_gabarit_relation(str(p)) is None


def test_gabarit_relation_fichier_absent_rejete():
    assert charger_gabarit_relation("chemin/inexistant.xml") is None


# ── Lot 9c : positions pour les montages a deux ancres ──

def test_gabarit_relation_positions_canoniques_miroir():
    gab = charger_gabarit_relation(_MIROIR)
    cible = [
        Component('Q9', 'Q', {'B': 'NET_B', 'C': 'VCC', 'E': 'GND'}),
        Component('Q10', 'Q', {'B': 'NET_B', 'C': 'NET_LOAD', 'E': 'GND'}),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1
    positions = gab.positions_canoniques(matches[0], x=500, y=500)
    assert set(positions) == {'Q9', 'Q10'}
    assert positions['Q9'] == (500, 500)
    assert positions['Q10'] != positions['Q9']


def test_gabarit_relation_positions_canoniques_darlington_respecte_le_sens():
    """@brief Meme si la paire cible est fournie dans l'ordre "inverse"
    (Q10 est electriquement le premier etage, Q9 le second), le mapping
    doit rester coherent avec CE QUI A ETE TROUVE par correspondre() (pas
    suppose Q9=ancre[0])."""
    gab = charger_gabarit_relation(_DARLINGTON)
    cible = [
        Component('Q9', 'Q', {'B': 'NET_LIEN', 'C': 'VCC', 'E': 'NET_OUT'}),
        Component('Q10', 'Q', {'B': 'NET_IN', 'C': 'VCC', 'E': 'NET_LIEN'}),
    ]
    matches = gab.correspondre(construire_graphe(cible))
    assert len(matches) == 1
    positions = gab.positions_canoniques(matches[0], x=0, y=0)
    assert set(positions) == {'Q9', 'Q10'}
    assert positions['Q9'] != positions['Q10']


def test_positions_depuis_gabarit_fonctionne_pour_les_3_montages_a_deux_ancres():
    """@brief Bout en bout via l'API generique de disposition (lot 9) :
    les 3 montages a deux ancres, jusque-la ignores silencieusement par
    positions_depuis_gabarit (aucune methode positions_canoniques
    n'existait cote GabaritRelation), obtiennent desormais une disposition."""
    from circuit_analyzer.gabarit import positions_depuis_gabarit

    cas = {
        "Miroir de courant BJT": [
            Component('Q9', 'Q', {'B': 'NET_B', 'C': 'VCC', 'E': 'GND'}),
            Component('Q10', 'Q', {'B': 'NET_B', 'C': 'NET_LOAD', 'E': 'GND'}),
        ],
        "Etage push-pull": [
            Component('Q9', 'Q', {'B': 'NET_B1', 'C': 'VCC', 'E': 'NET_OUT'}),
            Component('Q10', 'Q', {'B': 'NET_B2', 'C': 'GND', 'E': 'NET_OUT'}),
        ],
        "Paire Darlington": [
            Component('Q9', 'Q', {'B': 'NET_IN', 'C': 'VCC', 'E': 'NET_LIEN'}),
            Component('Q10', 'Q', {'B': 'NET_LIEN', 'C': 'VCC', 'E': 'NET_OUT'}),
        ],
    }
    for nom, cible in cas.items():
        positions = positions_depuis_gabarit(nom, cible, 100, 100)
        assert positions is not None, f"{nom} : aucune position derivee"
        assert set(positions) == {'Q9', 'Q10'}, f"{nom} : composants manquants"
        assert positions['Q9'] != positions['Q10'], f"{nom} : positions identiques"
