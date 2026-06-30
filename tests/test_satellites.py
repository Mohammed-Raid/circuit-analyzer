"""
@file test_satellites.py
@brief Tests automatises pour test_satellites.
"""

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
    """@brief Classe utilitaire de test _Comp."""
    """Composant minimal pour tester _evaluer sans construire un graphe."""
    def __init__(self, ref, type_, pins, value=''):
        """@brief Helper de test pour  init  ."""
        self.ref, self.type, self.pins, self.value = ref, type_, pins, value


# =============================================================================
# Helpers de topologie
# =============================================================================

def test_est_rail():
    """@brief Verifie est rail.

    @return None
    """
    assert _est_rail('GND')
    assert _est_rail('VCC')
    assert _est_rail('PE')
    assert not _est_rail('NET_BASE')
    assert not _est_rail('')
    assert not _est_rail(None)

def test_noeuds_internes_exclut_les_rails():
    """@brief Verifie noeuds internes exclut les rails.

    @return None
    """
    match = {'nodes': ['NET_IN', 'NET_MID', 'GND', 'VCC', '', None]}
    assert _noeuds_internes(match) == {'NET_IN', 'NET_MID'}

def test_rails_alim():
    """@brief Verifie rails alim.

    @return None
    """
    match = {'nodes': ['NET_IN', 'GND', 'VCC', '+5V']}
    assert _rails_alim(match) == {'VCC', '+5V'}

def test_seuils():
    """@brief Verifie seuils.

    @return None
    """
    assert SEUIL_POSSIBLE < SEUIL_SUR
    assert SEUIL_SUR == 0.6
    assert SEUIL_POSSIBLE == 0.3


# =============================================================================
# _evaluer — résistances
# =============================================================================

def test_pull_down_avec_valeur():
    """@brief Verifie pull down avec valeur.

    @return None
    """
    r = _Comp('R2', 'R', {'1': 'NET_BASE', '2': 'GND'}, '10k')
    role, score, reason = _evaluer(r, internes={'NET_BASE'}, rails=set())
    assert role == 'pull-down'
    assert score == 0.9
    assert 'NET_BASE' in reason and 'GND' in reason

def test_pull_up_avec_valeur():
    """@brief Verifie pull up avec valeur.

    @return None
    """
    r = _Comp('R3', 'R', {'1': 'VCC', '2': 'NET_BASE'}, '47k')
    role, score, reason = _evaluer(r, internes={'NET_BASE'}, rails=set())
    assert role == 'pull-up'
    assert score == 0.9

def test_pull_sans_valeur_score_reduit():
    """@brief Verifie pull sans valeur score reduit.

    @return None
    """
    r = _Comp('R2', 'R', {'1': 'NET_BASE', '2': 'GND'})
    role, score, reason = _evaluer(r, internes={'NET_BASE'}, rails=set())
    assert role == 'pull-down'
    assert score == 0.7

def test_r_faible_vers_rail_role_incertain():
    """@brief Verifie r faible vers rail role incertain.

    @return None
    """
    # 100 ohms vers GND : trop faible pour un pull -> voisin inconnu
    r = _Comp('R5', 'R', {'1': 'NET_BASE', '2': 'GND'}, '100')
    role, score, reason = _evaluer(r, internes={'NET_BASE'}, rails=set())
    assert role == 'unknown-neighbor'
    assert score == 0.4

def test_r_serie_valeur_coherente():
    """@brief Verifie r serie valeur coherente.

    @return None
    """
    # 100 ohms entre deux nets signal : typique d'une R série de base/grille
    r = _Comp('R4', 'R', {'1': 'NET_IN', '2': 'NET_EXT'}, '100')
    role, score, reason = _evaluer(r, internes={'NET_IN'}, rails=set())
    assert role == 'series-r'
    assert score == 0.7

def test_r_serie_valeur_incoherente_score_reduit():
    """@brief Verifie r serie valeur incoherente score reduit.

    @return None
    """
    # 47k entre deux nets signal : trop forte pour une R série classique
    r = _Comp('R4', 'R', {'1': 'NET_IN', '2': 'NET_EXT'}, '47k')
    role, score, reason = _evaluer(r, internes={'NET_IN'}, rails=set())
    assert role == 'series-r'
    assert score == 0.55

def test_r_serie_sans_valeur_score_reduit():
    """@brief Verifie r serie sans valeur score reduit.

    @return None
    """
    r = _Comp('R4', 'R', {'1': 'NET_IN', '2': 'NET_EXT'})
    role, score, reason = _evaluer(r, internes={'NET_IN'}, rails=set())
    assert role == 'series-r'
    assert score == 0.55

def test_r_sans_contact_retourne_none():
    """@brief Verifie r sans contact retourne none.

    @return None
    """
    r = _Comp('R9', 'R', {'1': 'NET_X', '2': 'NET_Y'}, '10k')
    assert _evaluer(r, internes={'NET_BASE'}, rails=set()) is None

def test_r_uniquement_via_rail_retourne_none():
    """@brief Verifie r uniquement via rail retourne none.

    @return None
    """
    # R entre VCC et GND : ne touche le circuit par aucun nœud interne
    r = _Comp('R9', 'R', {'1': 'VCC', '2': 'GND'}, '10k')
    assert _evaluer(r, internes={'NET_BASE'}, rails=set()) is None


# =============================================================================
# _evaluer — condensateurs, diodes, voisin inconnu
# =============================================================================

def test_decoupling_avec_valeur():
    """@brief Verifie decoupling avec valeur.

    @return None
    """
    c = _Comp('C3', 'C', {'1': 'VCC', '2': 'GND'}, '100nF')
    role, score, reason = _evaluer(c, internes={'NET_X'}, rails={'VCC'})
    assert role == 'decoupling'
    assert score == 0.9

def test_bulk_grosse_valeur():
    """@brief Verifie bulk grosse valeur.

    @return None
    """
    c = _Comp('C4', 'C', {'1': 'VCC', '2': 'GND'}, '47uF')
    role, score, reason = _evaluer(c, internes=set(), rails={'VCC'})
    assert role == 'bulk'
    assert score == 0.8

def test_decoupling_sans_valeur_score_reduit():
    """@brief Verifie decoupling sans valeur score reduit.

    @return None
    """
    c = _Comp('C3', 'C', {'1': 'VCC', '2': 'GND'})
    role, score, reason = _evaluer(c, internes=set(), rails={'VCC'})
    assert role == 'decoupling'
    assert score == 0.7

def test_c_sur_rail_non_utilise_par_le_circuit():
    """@brief Verifie c sur rail non utilise par le circuit.

    @return None
    """
    # Le circuit n'utilise pas VBAT -> ce C n'est pas son découplage
    c = _Comp('C5', 'C', {'1': 'VBAT', '2': 'GND'}, '100nF')
    assert _evaluer(c, internes={'NET_X'}, rails={'VCC'}) is None

def test_flyback():
    """@brief Verifie flyback.

    @return None
    """
    d = _Comp('D1', 'D', {'A': 'NET_SW', 'K': 'VCC'})
    role, score, reason = _evaluer(d, internes={'NET_SW'}, rails={'VCC'})
    assert role == 'flyback'
    assert score == 0.85

def test_diode_sens_inverse_pas_flyback():
    """@brief Verifie diode sens inverse pas flyback.

    @return None
    """
    # Anode sur rail, cathode sur nœud interne : pas une roue libre
    d = _Comp('D2', 'D', {'A': 'VCC', 'K': 'NET_SW'})
    role, score, reason = _evaluer(d, internes={'NET_SW'}, rails={'VCC'})
    assert role == 'unknown-neighbor'
    assert score == 0.4

def test_voisin_inconnu():
    """@brief Verifie voisin inconnu.

    @return None
    """
    c = _Comp('C9', 'C', {'1': 'NET_COLL', '2': 'NET_X'}, '10nF')
    role, score, reason = _evaluer(c, internes={'NET_COLL'}, rails=set())
    assert role == 'unknown-neighbor'
    assert score == 0.4
    assert 'NET_COLL' in reason

def test_reasons_sans_caracteres_hors_cp1252():
    """@brief Verifie reasons sans caracteres hors cp1252.

    @return None
    """
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
    """@brief Helper de test pour match."""
    return {'circuit_type': circuit_type, 'components': list(components),
            'nodes': list(nodes), 'confidence': confidence, 'warnings': []}


def test_leftover_rattache_comme_sur():
    """@brief Verifie leftover rattache comme sur.

    @return None
    """
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
    """@brief Verifie satellite possible non verrouille et warning.

    @return None
    """
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
    """@brief Verifie composant deja classifie jamais reexamine.

    @return None
    """
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
    """@brief Verifie composant isole non rattache.

    @return None
    """
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
    """@brief Verifie satellites toujours present meme vide.

    @return None
    """
    g = build_graph([Component('Q1', 'Q', {'B': 'A', 'C': 'B', 'E': 'GND'})])
    circuits = [_match('Transistor en commutation', ['Q1'], ['A', 'B', 'GND'])]
    rattacher_satellites(circuits, g, {'Q1'})
    assert 'satellites' in circuits[0]

def test_conflit_egalite_va_a_la_meilleure_confiance():
    """@brief Verifie conflit egalite va a la meilleure confiance.

    @return None
    """
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
    """@brief Verifie conflit meilleur score gagne.

    @return None
    """
    import circuit_analyzer.satellites as sat
    def faux_evaluer(comp, internes, rails):
        """@brief Helper de test pour faux evaluer."""
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
    """@brief Verifie roue libre absorbee via noeud signal.

    @return None
    """
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

def test_annexe_sans_circuit_hote_reste_un_circuit():
    """@brief Verifie annexe sans circuit hote reste un circuit.

    @return None
    """
    circuits = [
        _match('Diode de roue libre', ['D1'], ['NET_SW', 'VCC'], confidence=0.75),
    ]
    g = build_graph([])
    rattacher_satellites(circuits, g, {'D1'})
    assert len(circuits) == 1
    assert circuits[0]['circuit_type'] == 'Diode de roue libre'

def test_annexe_non_adjacente_reste_un_circuit():
    """@brief Verifie annexe non adjacente reste un circuit.

    @return None
    """
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
    """@brief Verifie absorption prefere noeud signal au rail.

    @return None
    """
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


# =============================================================================
# Intégration bout-en-bout via analyser()
# =============================================================================

def test_e2e_pull_up_devient_satellite():
    """@brief Verifie e2e pull up devient satellite.

    Depuis le modèle Impédance Z, C1 et R3 (GND–VCC) sont réduits en une seule
    Impédance Z composite. R1 est une Impédance Z singleton. Plus de satellite
    pull-up — tous les passifs sont couverts par « Impédance Z ».
    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
        Component('R3', 'R', {'1': 'NET_MID', '2': 'VCC'}, '47k'),
    ]
    results = match_patterns(build_graph(comps))
    types = [m['circuit_type'] for m in results]
    assert 'Impédance Z' in types
    # R1, C1 et R3 sont tous couverts par des Impédances Z
    couverts = {c for m in results for c in m['components']}
    assert {'R1', 'C1', 'R3'} <= couverts

def test_e2e_tous_les_matches_ont_la_cle_satellites():
    """@brief Verifie e2e tous les matches ont la cle satellites.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    assert results
    for m in results:
        assert isinstance(m['satellites'], list)

def test_e2e_roue_libre_absorbee():
    """@brief Verifie e2e roue libre absorbee.

    @return None
    """
    # Commande de relais + diode de roue libre sur le nœud de commutation
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_SW', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_BASE'}, '1k'),
        Component('K1', 'K', {'A1': 'NET_SW', 'A2': 'VCC', 'C': 'NET_C', 'NC': 'NET_NC'}),
        Component('D1', 'D', {'A': 'NET_SW', 'K': 'VCC'}),
    ]
    results = match_patterns(build_graph(comps))
    types = [m['circuit_type'] for m in results]
    assert 'Diode de roue libre' not in types
    hote = [m for m in results if any(s['ref'] == 'D1' for s in m['satellites'])]
    assert len(hote) == 1

def test_e2e_aucune_regression_sans_satellite():
    """@brief Verifie e2e aucune regression sans satellite.

    @return None
    """
    # Un circuit sans composant orphelin : aucun satellite, comportement inchangé
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_DIV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_DIV', '2': 'GND'}, '4.7k'),
    ]
    results = match_patterns(build_graph(comps))
    assert len(results) == 1
    assert results[0]['satellites'] == []


# =============================================================================
# Rapport
# =============================================================================

from circuit_analyzer.rapport import generer_rapport


def _resultats_filtre_avec_satellites():
    """@brief Helper de test pour resultats filtre avec satellites.

    Depuis le modèle Impédance Z, un circuit purement passif ne produit plus de
    satellites. On utilise un transistor en commutation (circuit actif) avec :
    - Q1, R1 : transistor en commutation (R1 = résistance de base, consommée)
    - D1 (roue libre NET_COLL→VCC) : satellite sûr (flyback)
    - D2 (anode VCC, cathode NET_COLL) : satellite possible (unknown-neighbor)
    """
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_BASE'}, '1k'),
        Component('D1', 'D', {'A': 'NET_COLL', 'K': 'VCC'}),   # roue libre → sûr
        Component('D2', 'D', {'A': 'VCC', 'K': 'NET_COLL'}),   # anode sur rail → possible
    ]
    refs = [c.ref for c in comps]
    return match_patterns(build_graph(comps)), refs

def test_rapport_affiche_satellites_surs():
    """@brief Verifie rapport affiche satellites surs.

    @return None
    """
    results, refs = _resultats_filtre_avec_satellites()
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    assert 'Satellites sûrs' in rapport
    assert 'D1' in rapport
    assert 'flyback' in rapport

def test_rapport_affiche_satellites_possibles_avec_marqueur():
    """@brief Verifie rapport affiche satellites possibles avec marqueur.

    @return None
    """
    results, refs = _resultats_filtre_avec_satellites()
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    assert 'Satellites possibles' in rapport
    assert 'D2 ?' in rapport

def test_rapport_sur_quitte_non_classifies_possible_va_dans_a_verifier():
    """@brief Verifie rapport sur quitte non classifies possible va dans a verifier.

    @return None
    """
    # Correction 2 : seuls les sûrs sortent des non-classifiés ;
    # les possibles vont dans une section « À vérifier »
    results, refs = _resultats_filtre_avec_satellites()
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    assert 'À vérifier (rattachement possible)' in rapport
    section = rapport.split('À vérifier')[1]
    assert 'D2' in section
    if 'non classifiés' in rapport:
        section_nc = rapport.split('non classifiés')[1].split('À vérifier')[0]
        assert 'D1' not in section_nc

def test_rapport_warning_validation_ingenieur():
    """@brief Verifie rapport warning validation ingenieur.

    @return None
    """
    results, refs = _resultats_filtre_avec_satellites()
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    assert 'validation ingénieur nécessaire' in rapport

def test_rapport_pas_de_lignes_satellites_quand_vide():
    """@brief Verifie rapport pas de lignes satellites quand vide.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_DIV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_DIV', '2': 'GND'}, '4.7k'),
    ]
    refs = [c.ref for c in comps]
    results = match_patterns(build_graph(comps))
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    assert 'Satellites' not in rapport
    assert 'À vérifier' not in rapport

def test_rapport_encodable_cp1252():
    """@brief Verifie rapport encodable cp1252.

    @return None
    """
    results, refs = _resultats_filtre_avec_satellites()
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    for ligne in rapport.split('\n'):
        if 'Satellites' in ligne or 'À vérifier' in ligne or 'rattachement' in ligne:
            ligne.encode('cp1252')   # ne doit pas lever UnicodeEncodeError


# =============================================================================
# Export XML
# =============================================================================

from circuit_analyzer.xml import generer_xml, _grouper_par_circuit


def test_xml_satellite_sur_dans_le_bloc_du_circuit():
    """@brief Verifie xml satellite sur dans le bloc du circuit.

    Depuis le modèle Impédance Z, R3 (VCC–GND via le nœud milieu) est réduit
    en une Impédance Z composite avec C1. R3 n'est dans aucun bloc Divers.
    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
        Component('R3', 'R', {'1': 'NET_MID', '2': 'VCC'}, '47k'),
    ]
    results = match_patterns(build_graph(comps))
    blocs = _grouper_par_circuit(comps, results)
    # R3 doit être dans un bloc Impédance Z (composite avec C1), pas en Divers.
    bloc_z = [b for b in blocs if b.label == 'Impédance Z']
    assert any(any(c.ref == 'R3' for c in b.comps) for b in bloc_z)
    for b in blocs:
        if b.label == 'Divers':
            assert all(c.ref != 'R3' for c in b.comps)

def test_xml_satellite_possible_reste_en_divers():
    """@brief Verifie xml satellite possible reste en divers.

    Depuis le modèle Impédance Z, C9 n'est plus un satellite possible : il est
    émis comme une Impédance Z autonome et groupé dans le bloc Impédance Z.
    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
        Component('C9', 'C', {'1': 'NET_MID', '2': 'NET_X'}, '10nF'),
    ]
    results = match_patterns(build_graph(comps))
    blocs = _grouper_par_circuit(comps, results)
    # C9 est maintenant une Impédance Z, pas en Divers
    bloc_z = [b for b in blocs if b.label == 'Impédance Z']
    assert any(any(c.ref == 'C9' for c in b.comps) for b in bloc_z)
    divers = [b for b in blocs if b.label == 'Divers']
    assert not divers or all(c.ref != 'C9' for c in divers[0].comps)

def test_xml_generation_complete_avec_satellites():
    """@brief Verifie xml generation complete avec satellites.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
        Component('R3', 'R', {'1': 'NET_MID', '2': 'VCC'}, '47k'),
    ]
    results = match_patterns(build_graph(comps))
    xml_str = generer_xml(comps, results)
    # le format BoardSCH n'embarque pas les refs : on vérifie la valeur de R3
    assert '47k' in xml_str
