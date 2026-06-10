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
