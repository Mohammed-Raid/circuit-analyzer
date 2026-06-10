"""
test_satellites.py — Tests du rattachement des composants satellites.
"""
import pytest
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.satellites import (
    SEUIL_SUR, SEUIL_POSSIBLE,
    _est_rail, _noeuds_internes, _rails_alim,
    _evaluer,
)


class _Comp:
    """Composant minimal pour tester _evaluer sans construire un graphe."""
    def __init__(self, ref, type_, pins, value=''):
        self.ref, self.type, self.pins, self.value = ref, type_, pins, value


# =============================================================================
# Helpers de topologie
# =============================================================================

def test_est_rail():
    assert _est_rail('GND')
    assert _est_rail('VCC')
    assert _est_rail('PE')
    assert not _est_rail('NET_BASE')
    assert not _est_rail('')
    assert not _est_rail(None)

def test_noeuds_internes_exclut_les_rails():
    match = {'nodes': ['NET_IN', 'NET_MID', 'GND', 'VCC', '', None]}
    assert _noeuds_internes(match) == {'NET_IN', 'NET_MID'}

def test_rails_alim():
    match = {'nodes': ['NET_IN', 'GND', 'VCC', '+5V']}
    assert _rails_alim(match) == {'VCC', '+5V'}

def test_seuils():
    assert SEUIL_POSSIBLE < SEUIL_SUR
    assert SEUIL_SUR == 0.6
    assert SEUIL_POSSIBLE == 0.3


# =============================================================================
# _evaluer — résistances
# =============================================================================

def test_pull_down_avec_valeur():
    r = _Comp('R2', 'R', {'1': 'NET_BASE', '2': 'GND'}, '10k')
    role, score, reason = _evaluer(r, internes={'NET_BASE'}, rails=set())
    assert role == 'pull-down'
    assert score == 0.9
    assert 'NET_BASE' in reason and 'GND' in reason

def test_pull_up_avec_valeur():
    r = _Comp('R3', 'R', {'1': 'VCC', '2': 'NET_BASE'}, '47k')
    role, score, reason = _evaluer(r, internes={'NET_BASE'}, rails=set())
    assert role == 'pull-up'
    assert score == 0.9

def test_pull_sans_valeur_score_reduit():
    r = _Comp('R2', 'R', {'1': 'NET_BASE', '2': 'GND'})
    role, score, reason = _evaluer(r, internes={'NET_BASE'}, rails=set())
    assert role == 'pull-down'
    assert score == 0.7

def test_r_faible_vers_rail_role_incertain():
    # 100 ohms vers GND : trop faible pour un pull -> voisin inconnu
    r = _Comp('R5', 'R', {'1': 'NET_BASE', '2': 'GND'}, '100')
    role, score, reason = _evaluer(r, internes={'NET_BASE'}, rails=set())
    assert role == 'unknown-neighbor'
    assert score == 0.4

def test_r_serie_valeur_coherente():
    # 100 ohms entre deux nets signal : typique d'une R série de base/grille
    r = _Comp('R4', 'R', {'1': 'NET_IN', '2': 'NET_EXT'}, '100')
    role, score, reason = _evaluer(r, internes={'NET_IN'}, rails=set())
    assert role == 'series-r'
    assert score == 0.7

def test_r_serie_valeur_incoherente_score_reduit():
    # 47k entre deux nets signal : trop forte pour une R série classique
    r = _Comp('R4', 'R', {'1': 'NET_IN', '2': 'NET_EXT'}, '47k')
    role, score, reason = _evaluer(r, internes={'NET_IN'}, rails=set())
    assert role == 'series-r'
    assert score == 0.55

def test_r_serie_sans_valeur_score_reduit():
    r = _Comp('R4', 'R', {'1': 'NET_IN', '2': 'NET_EXT'})
    role, score, reason = _evaluer(r, internes={'NET_IN'}, rails=set())
    assert role == 'series-r'
    assert score == 0.55

def test_r_sans_contact_retourne_none():
    r = _Comp('R9', 'R', {'1': 'NET_X', '2': 'NET_Y'}, '10k')
    assert _evaluer(r, internes={'NET_BASE'}, rails=set()) is None

def test_r_uniquement_via_rail_retourne_none():
    # R entre VCC et GND : ne touche le circuit par aucun nœud interne
    r = _Comp('R9', 'R', {'1': 'VCC', '2': 'GND'}, '10k')
    assert _evaluer(r, internes={'NET_BASE'}, rails=set()) is None


# =============================================================================
# _evaluer — condensateurs, diodes, voisin inconnu
# =============================================================================

def test_decoupling_avec_valeur():
    c = _Comp('C3', 'C', {'1': 'VCC', '2': 'GND'}, '100nF')
    role, score, reason = _evaluer(c, internes={'NET_X'}, rails={'VCC'})
    assert role == 'decoupling'
    assert score == 0.9

def test_bulk_grosse_valeur():
    c = _Comp('C4', 'C', {'1': 'VCC', '2': 'GND'}, '47uF')
    role, score, reason = _evaluer(c, internes=set(), rails={'VCC'})
    assert role == 'bulk'
    assert score == 0.8

def test_decoupling_sans_valeur_score_reduit():
    c = _Comp('C3', 'C', {'1': 'VCC', '2': 'GND'})
    role, score, reason = _evaluer(c, internes=set(), rails={'VCC'})
    assert role == 'decoupling'
    assert score == 0.7

def test_c_sur_rail_non_utilise_par_le_circuit():
    # Le circuit n'utilise pas VBAT -> ce C n'est pas son découplage
    c = _Comp('C5', 'C', {'1': 'VBAT', '2': 'GND'}, '100nF')
    assert _evaluer(c, internes={'NET_X'}, rails={'VCC'}) is None

def test_flyback():
    d = _Comp('D1', 'D', {'A': 'NET_SW', 'K': 'VCC'})
    role, score, reason = _evaluer(d, internes={'NET_SW'}, rails={'VCC'})
    assert role == 'flyback'
    assert score == 0.85

def test_diode_sens_inverse_pas_flyback():
    # Anode sur rail, cathode sur nœud interne : pas une roue libre
    d = _Comp('D2', 'D', {'A': 'VCC', 'K': 'NET_SW'})
    role, score, reason = _evaluer(d, internes={'NET_SW'}, rails={'VCC'})
    assert role == 'unknown-neighbor'
    assert score == 0.4

def test_voisin_inconnu():
    c = _Comp('C9', 'C', {'1': 'NET_COLL', '2': 'NET_X'}, '10nF')
    role, score, reason = _evaluer(c, internes={'NET_COLL'}, rails=set())
    assert role == 'unknown-neighbor'
    assert score == 0.4
    assert 'NET_COLL' in reason

def test_reasons_sans_caracteres_hors_cp1252():
    # Les chaînes destinées au rapport Windows ne doivent pas contenir
    # de caractères hors cp1252 (pas de fleches/symboles Unicode)
    cas = [
        (_Comp('R2', 'R', {'1': 'N1', '2': 'GND'}, '10k'), {'N1'}, set()),
        (_Comp('C3', 'C', {'1': 'VCC', '2': 'GND'}, '100nF'), set(), {'VCC'}),
        (_Comp('D1', 'D', {'A': 'N1', 'K': 'VCC'}), {'N1'}, {'VCC'}),
        (_Comp('R4', 'R', {'1': 'N1', '2': 'N2'}, '100'), {'N1'}, set()),
        (_Comp('C9', 'C', {'1': 'N1', '2': 'N2'}), {'N1'}, set()),
    ]
    for comp, internes, rails in cas:
        resultat = _evaluer(comp, internes, rails)
        assert resultat is not None
        resultat[2].encode('cp1252')   # ne doit pas lever UnicodeEncodeError


# =============================================================================
# rattacher_satellites — phase leftovers
# =============================================================================

from circuit_analyzer.satellites import rattacher_satellites


def _match(circuit_type, components, nodes, confidence=0.8):
    return {'circuit_type': circuit_type, 'components': list(components),
            'nodes': list(nodes), 'confidence': confidence, 'warnings': []}


def test_leftover_rattache_comme_sur():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R2', 'R', {'1': 'NET_BASE', '2': 'GND'}, '10k'),
    ]
    g = build_graph(comps)
    circuits = [_match('Transistor en commutation', ['Q1'],
                       ['NET_BASE', 'NET_COLL', 'GND'], confidence=0.85)]
    utilises = {'Q1'}
    rattacher_satellites(circuits, g, utilises)
    sats = circuits[0]['satellites']
    assert len(sats) == 1
    assert sats[0]['ref'] == 'R2'
    assert sats[0]['role'] == 'pull-down'
    assert sats[0]['status'] == 'sure'
    # Un satellite sûr est verrouillé
    assert 'R2' in utilises

def test_satellite_possible_non_verrouille_et_warning():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('C9', 'C', {'1': 'NET_COLL', '2': 'NET_X'}, '10nF'),
    ]
    g = build_graph(comps)
    circuits = [_match('Transistor en commutation', ['Q1'],
                       ['NET_BASE', 'NET_COLL', 'GND'])]
    utilises = {'Q1'}
    rattacher_satellites(circuits, g, utilises)
    sats = circuits[0]['satellites']
    assert len(sats) == 1
    assert sats[0]['role'] == 'unknown-neighbor'
    assert sats[0]['status'] == 'possible'
    assert 'C9' not in utilises
    # Correction 7 : warning explicite pour chaque satellite possible
    assert any('C9' in w and 'validation ingénieur' in w
               for w in circuits[0]['warnings'])

def test_composant_deja_classifie_jamais_reexamine():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R2', 'R', {'1': 'NET_BASE', '2': 'GND'}, '10k'),
    ]
    g = build_graph(comps)
    circuits = [_match('Transistor en commutation', ['Q1'],
                       ['NET_BASE', 'NET_COLL', 'GND'])]
    utilises = {'Q1', 'R2'}          # R2 appartient déjà à un circuit
    rattacher_satellites(circuits, g, utilises)
    assert circuits[0]['satellites'] == []

def test_composant_isole_non_rattache():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R8', 'R', {'1': 'NET_LOIN', '2': 'NET_AILLEURS'}, '1k'),
    ]
    g = build_graph(comps)
    circuits = [_match('Transistor en commutation', ['Q1'],
                       ['NET_BASE', 'NET_COLL', 'GND'])]
    utilises = {'Q1'}
    rattacher_satellites(circuits, g, utilises)
    assert circuits[0]['satellites'] == []

def test_satellites_toujours_present_meme_vide():
    g = build_graph([Component('Q1', 'Q', {'B': 'A', 'C': 'B', 'E': 'GND'})])
    circuits = [_match('Transistor en commutation', ['Q1'], ['A', 'B', 'GND'])]
    rattacher_satellites(circuits, g, {'Q1'})
    assert 'satellites' in circuits[0]

def test_conflit_egalite_va_a_la_meilleure_confiance():
    comps = [
        Component('R2', 'R', {'1': 'NET_A', '2': 'GND'}, '10k'),
    ]
    g = build_graph(comps)
    c1 = _match('Circuit faible', ['Q1'], ['NET_A', 'GND'], confidence=0.7)
    c2 = _match('Circuit fort',   ['Q2'], ['NET_A', 'GND'], confidence=0.95)
    utilises = {'Q1', 'Q2'}
    rattacher_satellites([c1, c2], g, utilises)
    assert c1['satellites'] == []
    assert len(c2['satellites']) == 1 and c2['satellites'][0]['ref'] == 'R2'

def test_conflit_meilleur_score_gagne(monkeypatch):
    import circuit_analyzer.satellites as sat
    def faux_evaluer(comp, internes, rails):
        if 'N_FAIBLE' in internes:
            return ('role-faible', 0.5, 'x')
        return ('role-fort', 0.9, 'y')
    monkeypatch.setattr(sat, '_evaluer', faux_evaluer)
    comps = [Component('R2', 'R', {'1': 'N_FAIBLE', '2': 'N_FORT'}, '1k')]
    g = build_graph(comps)
    c1 = _match('A', ['Q1'], ['N_FAIBLE'], confidence=0.99)
    c2 = _match('B', ['Q2'], ['N_FORT'],   confidence=0.70)
    rattacher_satellites([c1, c2], g, {'Q1', 'Q2'})
    assert c1['satellites'] == []
    assert c2['satellites'][0]['role'] == 'role-fort'


# =============================================================================
# Absorption des circuits annexes mono-composant
# =============================================================================

def test_roue_libre_absorbee_via_noeud_signal():
    circuits = [
        _match('Commande de relais', ['Q1', 'K1'],
               ['NET_BASE', 'NET_COLL', 'GND', 'VCC'], confidence=0.9),
        _match('Diode de roue libre', ['D1'],
               ['NET_COLL', 'VCC'], confidence=0.75),
    ]
    g = build_graph([])
    rattacher_satellites(circuits, g, {'Q1', 'K1', 'D1'})
    assert len(circuits) == 1
    assert circuits[0]['circuit_type'] == 'Commande de relais'
    sats = circuits[0]['satellites']
    assert len(sats) == 1
    assert sats[0]['ref'] == 'D1'
    assert sats[0]['role'] == 'flyback'
    assert sats[0]['status'] == 'sure'        # partage un nœud signal
    assert sats[0]['score'] == 0.75
    assert sats[0]['reason'] == 'Diode de roue libre'

def test_decouplage_rail_seul_hote_devient_possible():
    # Correction 3 : absorption par rails uniquement -> jamais « sure »
    circuits = [
        _match('Amplificateur inverseur (AOP)', ['U1', 'R1', 'R2'],
               ['NET_IN', 'NET_INM', 'NET_OUT', 'VCC', 'GND'], confidence=0.9),
        _match('Condensateur de découplage', ['C3'],
               ['VCC', 'GND'], confidence=0.85),
    ]
    g = build_graph([])
    rattacher_satellites(circuits, g, {'U1', 'R1', 'R2', 'C3'})
    assert len(circuits) == 1
    sat = circuits[0]['satellites'][0]
    assert sat['role'] == 'decoupling'
    assert sat['status'] == 'possible'
    assert sat['score'] <= 0.55
    assert any('C3' in w for w in circuits[0]['warnings'])

def test_decouplage_rails_plusieurs_hotes_pas_absorbe():
    # Correction 3 : plusieurs circuits partagent le rail -> ambigu, pas d'absorption
    circuits = [
        _match('Amplificateur inverseur (AOP)', ['U1', 'R1'],
               ['NET_A', 'NET_B', 'VCC', 'GND'], confidence=0.9),
        _match('Transistor en commutation', ['Q1', 'R3'],
               ['NET_C', 'NET_D', 'VCC', 'GND'], confidence=0.85),
        _match('Condensateur de découplage', ['C3'],
               ['VCC', 'GND'], confidence=0.85),
    ]
    g = build_graph([])
    rattacher_satellites(circuits, g, {'U1', 'R1', 'Q1', 'R3', 'C3'})
    assert len(circuits) == 3
    types = [m['circuit_type'] for m in circuits]
    assert 'Condensateur de découplage' in types

def test_annexe_sans_circuit_hote_reste_un_circuit():
    circuits = [
        _match('Diode de roue libre', ['D1'], ['NET_SW', 'VCC'], confidence=0.75),
    ]
    g = build_graph([])
    rattacher_satellites(circuits, g, {'D1'})
    assert len(circuits) == 1
    assert circuits[0]['circuit_type'] == 'Diode de roue libre'

def test_annexe_non_adjacente_reste_un_circuit():
    circuits = [
        _match('Commande de relais', ['Q1', 'K1'],
               ['NET_BASE', 'NET_COLL', 'GND'], confidence=0.9),
        _match('Diode de roue libre', ['D9'],
               ['NET_LOIN', 'VBAT'], confidence=0.75),
    ]
    g = build_graph([])
    rattacher_satellites(circuits, g, {'Q1', 'K1', 'D9'})
    assert len(circuits) == 2

def test_absorption_prefere_noeud_signal_au_rail():
    # D1 partage NET_COLL (signal) avec c1 et seulement VCC (rail) avec c2
    c1 = _match('Commande de relais', ['Q1', 'K1'],
                ['NET_BASE', 'NET_COLL', 'VCC', 'GND'], confidence=0.7)
    c2 = _match('Amplificateur inverseur (AOP)', ['U1', 'R1'],
                ['NET_X', 'NET_Y', 'VCC', 'GND'], confidence=0.99)
    annexe = _match('Diode de roue libre', ['D1'], ['NET_COLL', 'VCC'],
                    confidence=0.75)
    circuits = [c1, c2, annexe]
    g = build_graph([])
    rattacher_satellites(circuits, g, {'Q1', 'K1', 'U1', 'R1', 'D1'})
    assert len(c1['satellites']) == 1      # malgré la confiance plus faible
    assert c2['satellites'] == []
