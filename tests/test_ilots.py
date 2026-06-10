"""
test_ilots.py — Tests de la détection d'îlots fonctionnels.
"""
import pytest
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.ilots import detecter_ilots


def _match(circuit_type, components, nodes, categorie='divers', confidence=0.8):
    return {'circuit_type': circuit_type, 'components': list(components),
            'nodes': list(nodes), 'functional_category': categorie,
            'confidence': confidence, 'satellites': []}


# =============================================================================
# Connexité (Union-Find sur les nets non-rail)
# =============================================================================

def test_deux_ilots_disjoints():
    comps = [
        # Îlot A : filtre RC
        Component('R1', 'R', {'1': 'NET_A1', '2': 'NET_A2'}, '10k'),
        Component('C1', 'C', {'1': 'NET_A2', '2': 'GND'}, '100nF'),
        # Îlot B : autre filtre, aucun net signal commun
        Component('R2', 'R', {'1': 'NET_B1', '2': 'NET_B2'}, '10k'),
        Component('C2', 'C', {'1': 'NET_B2', '2': 'GND'}, '100nF'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert len(ilots) == 2
    groupes = [set(i['composants']) for i in ilots]
    assert {'R1', 'C1'} in groupes
    assert {'R2', 'C2'} in groupes

def test_gnd_ne_fusionne_pas_les_ilots():
    # Les deux îlots partagent GND : ils doivent rester séparés
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'GND'}, '10k'),
        Component('R2', 'R', {'1': 'NET_B', '2': 'GND'}, '10k'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert len(ilots) == 2

def test_net_signal_fusionne():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_MID'}, '10k'),
        Component('R2', 'R', {'1': 'NET_MID', '2': 'NET_B'}, '10k'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert len(ilots) == 1
    assert set(ilots[0]['composants']) == {'R1', 'R2'}

def test_aop_multibroches_unionne_ses_nets():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_P', 'IN-': 'NET_M',
                              'OUT': 'NET_O', 'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_P', '2': 'NET_X'}, '10k'),
        Component('R2', 'R', {'1': 'NET_O', '2': 'NET_Y'}, '10k'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert len(ilots) == 1
    assert set(ilots[0]['composants']) == {'U1', 'R1', 'R2'}


# =============================================================================
# Composants rail-only
# =============================================================================

def test_rail_only_groupes_par_rail():
    comps = [
        Component('C1', 'C', {'1': 'VCC_12V', '2': 'GND'}, '100nF'),
        Component('C2', 'C', {'1': 'VCC_12V', '2': 'GND'}, '10uF'),
        Component('C3', 'C', {'1': 'VCC_5V', '2': 'GND'}, '100nF'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert len(ilots) == 2
    par_rail = {i['rail']: set(i['composants']) for i in ilots}
    assert par_rail['VCC_12V'] == {'C1', 'C2'}
    assert par_rail['VCC_5V'] == {'C3'}
    for i in ilots:
        assert 'alimentation' in i['label']
        assert i['rail'] in i['label']

def test_gnd_only_va_en_non_identifie():
    comps = [
        Component('R1', 'R', {'1': 'GND', '2': 'GND'}, '0R'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert len(ilots) == 1
    assert ilots[0]['rail'] is None
    assert 'non identifié' in ilots[0]['label']


# =============================================================================
# Nommage et mapping circuits
# =============================================================================

def test_categorie_majoritaire():
    comps = [
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
        Component('R2', 'R', {'1': 'N2', '2': 'N3'}, '10k'),
        Component('R3', 'R', {'1': 'N3', '2': 'N4'}, '10k'),
    ]
    g = build_graph(comps)
    circuits = [
        _match('A', ['R1'], ['N1', 'N2'], categorie='commutation'),
        _match('B', ['R2'], ['N2', 'N3'], categorie='commutation'),
        _match('C', ['R3'], ['N3', 'N4'], categorie='filtrage'),
    ]
    ilots = detecter_ilots(g, circuits)
    assert len(ilots) == 1
    assert ilots[0]['categorie'] == 'commutation'
    assert 'commutation' in ilots[0]['label']
    assert ilots[0]['circuits'] == [0, 1, 2]

def test_egalite_liste_les_categories():
    comps = [
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
        Component('R2', 'R', {'1': 'N2', '2': 'N3'}, '10k'),
    ]
    g = build_graph(comps)
    circuits = [
        _match('A', ['R1'], ['N1', 'N2'], categorie='commutation'),
        _match('B', ['R2'], ['N2', 'N3'], categorie='filtrage'),
    ]
    ilots = detecter_ilots(g, circuits)
    assert ilots[0]['categorie'] == 'commutation + filtrage'

def test_sans_circuit_non_identifie():
    comps = [
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert ilots[0]['categorie'] == 'non identifié'

def test_tri_par_taille_decroissante_et_numerotation():
    comps = [
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
        Component('R2', 'R', {'1': 'M1', '2': 'M2'}, '10k'),
        Component('R3', 'R', {'1': 'M2', '2': 'M3'}, '10k'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert len(ilots[0]['composants']) >= len(ilots[1]['composants'])
    assert ilots[0]['label'].startswith('Îlot 1')
    assert ilots[1]['label'].startswith('Îlot 2')

def test_composants_tries():
    comps = [
        Component('R9', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
        Component('C1', 'C', {'1': 'N2', '2': 'N3'}, '1nF'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert ilots[0]['composants'] == sorted(ilots[0]['composants'])

def test_labels_cp1252():
    comps = [
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
        Component('C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF'),
    ]
    g = build_graph(comps)
    for i in detecter_ilots(g, []):
        i['label'].encode('cp1252')


# =============================================================================
# Intégration bout-en-bout via analyser()
# =============================================================================

def _circuit_deux_etages():
    return [
        # Étage 1 : filtre RC
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
        # Étage 2 : pont diviseur, aucun net signal commun avec l'étage 1
        Component('R2', 'R', {'1': 'VCC', '2': 'NET_DIV'}, '10k'),
        Component('R3', 'R', {'1': 'NET_DIV', '2': 'GND'}, '4.7k'),
        # Découplage rail-to-rail
        Component('C2', 'C', {'1': 'VCC', '2': 'GND'}, '100nF'),
    ]

def test_e2e_ilots_attache_aux_resultats():
    results = match_patterns(build_graph(_circuit_deux_etages()))
    assert hasattr(results, 'ilots')
    assert isinstance(results.ilots, list)
    assert len(results.ilots) >= 2

def test_e2e_indices_circuits_coherents():
    results = match_patterns(build_graph(_circuit_deux_etages()))
    for ilot in results.ilots:
        for idx in ilot['circuits']:
            match = results[idx]
            # au moins un composant du match est dans l'îlot
            assert any(ref in ilot['composants']
                       for ref in match['components'])

def test_e2e_etages_separes():
    results = match_patterns(build_graph(_circuit_deux_etages()))
    groupes = [set(i['composants']) for i in results.ilots]
    assert any({'R1', 'C1'} <= g for g in groupes)
    assert any({'R2', 'R3'} <= g for g in groupes)
    # le filtre et le diviseur ne sont pas dans le même îlot
    assert not any({'R1', 'R2'} <= g for g in groupes)

def test_resultats_analyse_ilots_par_defaut():
    from circuit_analyzer.detecteur import ResultatsAnalyse
    r = ResultatsAnalyse()
    assert r.ilots == []


# =============================================================================
# Rapport — section STRUCTURE EN ETAGES
# =============================================================================

from circuit_analyzer.rapport import generer_rapport


def test_rapport_section_etages():
    comps = _circuit_deux_etages()
    refs = [c.ref for c in comps]
    results = match_patterns(build_graph(comps))
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    assert '=== STRUCTURE EN ETAGES ===' in rapport
    assert 'Îlot 1' in rapport

def test_rapport_etages_numeros_circuits_coherents():
    comps = _circuit_deux_etages()
    refs = [c.ref for c in comps]
    results = match_patterns(build_graph(comps))
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    # le circuit [1] du listing principal doit apparaître avec le même
    # numéro dans la section étages
    section = rapport.split('=== STRUCTURE EN ETAGES ===')[1]
    assert '[1]' in section

def test_rapport_etages_absente_si_list_simple():
    # compat : un appel avec une simple list (sans .ilots) ne plante pas
    comps = _circuit_deux_etages()
    refs = [c.ref for c in comps]
    results = match_patterns(build_graph(comps))
    rapport = generer_rapport(list(results), 'test.txt', len(refs), refs)
    assert '=== STRUCTURE EN ETAGES ===' not in rapport

def test_rapport_etages_ilot_sans_circuit_liste_composants():
    comps = [
        Component('X1', 'R', {'1': 'NET_Z1', '2': 'NET_Z2'}),
    ]
    refs = [c.ref for c in comps]
    results = match_patterns(build_graph(comps))
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    section = rapport.split('=== STRUCTURE EN ETAGES ===')[1]
    assert 'X1' in section

def test_rapport_etages_cp1252():
    comps = _circuit_deux_etages()
    refs = [c.ref for c in comps]
    results = match_patterns(build_graph(comps))
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    section = rapport.split('=== STRUCTURE EN ETAGES ===')[1].split('===')[0]
    section.encode('cp1252')
