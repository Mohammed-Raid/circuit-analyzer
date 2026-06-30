"""
@file test_ilots.py
@brief Tests automatises pour test_ilots.
"""

"""
test_ilots.py — Tests de la détection d'îlots fonctionnels.
"""
import pytest
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.ilots import detecter_ilots


def _match(circuit_type, components, nodes, categorie='divers', confidence=0.8):
    """@brief Helper de test pour match."""
    return {'circuit_type': circuit_type, 'components': list(components),
            'nodes': list(nodes), 'functional_category': categorie,
            'confidence': confidence, 'satellites': []}


# =============================================================================
# Connexité (Union-Find sur les nets non-rail)
# =============================================================================

def test_deux_ilots_disjoints():
    """@brief Verifie deux ilots disjoints.

    @return None
    """
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
    """@brief Verifie gnd ne fusionne pas les ilots.

    @return None
    """
    # Les deux îlots partagent GND : ils doivent rester séparés
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'GND'}, '10k'),
        Component('R2', 'R', {'1': 'NET_B', '2': 'GND'}, '10k'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert len(ilots) == 2

def test_nc_ne_fusionne_pas_les_ilots():
    """@brief Un net « NC » (non connecté) ne doit pas relier deux îlots.

    Cas réel : deux AOP dont les broches d'alim sont laissées à 'NC' par l'export
    XML — ils ne partagent aucun net signal et doivent rester deux îlots.
    """
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_A', 'OUT': 'OUTA',
                              'V+': 'NC', 'V-': 'NC'}),
        Component('U2', 'U', {'IN+': 'GND', 'IN-': 'NET_B', 'OUT': 'OUTB',
                              'V+': 'NC', 'V-': 'NC'}),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert len(ilots) == 2

def test_net_signal_fusionne():
    """@brief Verifie net signal fusionne.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_MID'}, '10k'),
        Component('R2', 'R', {'1': 'NET_MID', '2': 'NET_B'}, '10k'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert len(ilots) == 1
    assert set(ilots[0]['composants']) == {'R1', 'R2'}

def test_aop_multibroches_unionne_ses_nets():
    """@brief Verifie aop multibroches unionne ses nets.

    @return None
    """
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
    """@brief Verifie rail only groupes par rail.

    @return None
    """
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

def test_composant_degenere_meme_net_exclu():
    """Un composant dont toutes les broches sont sur le MÊME net (court-circuit
    dégénéré) ne forme pas d'îlot : il est électriquement inerte.

    Cas réel : R14 et C9 du pid_controller câblés GND-GND dans la netlist
    s'affichaient en boîtes Z absurdes (« non identifié »). Ils doivent disparaître.
    """
    comps = [
        Component('R14', 'R', {'1': 'GND', '2': 'GND'}, '10k'),
        Component('C9', 'C', {'1': 'GND', '2': 'GND'}, '100nF'),
        # Même cas sur un net signal (court-circuit) : aussi dégénéré.
        Component('R20', 'R', {'1': 'NET_A', '2': 'NET_A'}, '1k'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert ilots == []


def test_diviseur_reference_un_seul_ilot():
    # R_haut (VCC->VREF) et R_bas (VREF->GND) doivent etre dans le MEME ilot.
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'VREF'}, '10k'),
        Component('R2', 'R', {'1': 'VREF', '2': 'GND'}, '10k'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert len(ilots) == 1
    assert set(ilots[0]['composants']) == {'R1', 'R2'}


def test_filtrage_rail_un_seul_ilot():
    comps = [
        Component('R4', 'R', {'1': 'VCC_5V', '2': 'AVCC'}, '10R'),
        Component('C4', 'C', {'1': 'AVCC', '2': 'GND'}, '100nF'),
        Component('C5', 'C', {'1': 'AVCC', '2': 'GND'}, '10uF'),
    ]
    ilots = detecter_ilots(build_graph(comps), [])
    assert len(ilots) == 1
    assert set(ilots[0]['composants']) == {'R4', 'C4', 'C5'}


# =============================================================================
# Nets dérivés (prises de référence)
# =============================================================================

def test_nets_derives_reconnait_diviseur():
    # VCC -- R1 -- VREF -- R2 -- GND : VREF est une prise, VCC non.
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'VREF'}, '10k'),
        Component('R2', 'R', {'1': 'VREF', '2': 'GND'}, '10k'),
    ]
    from circuit_analyzer.ilots import _nets_derives
    derives = _nets_derives(build_graph(comps))
    assert 'VREF' in derives
    assert 'VCC' not in derives


def test_nets_derives_filtrage_rail_caps_vers_gnd():
    # VCC_5V -- R4 -- AVCC, et C4/C5 de AVCC a GND : AVCC est une prise.
    comps = [
        Component('R4', 'R', {'1': 'VCC_5V', '2': 'AVCC'}, '10R'),
        Component('C4', 'C', {'1': 'AVCC', '2': 'GND'}, '100nF'),
        Component('C5', 'C', {'1': 'AVCC', '2': 'GND'}, '10uF'),
    ]
    from circuit_analyzer.ilots import _nets_derives
    derives = _nets_derives(build_graph(comps))
    assert 'AVCC' in derives
    assert 'VCC_5V' not in derives


def test_nets_derives_decouplage_simple_pas_une_prise():
    # Un simple cap VCC-GND n'a pas de passif vers un AUTRE rail : pas une prise.
    comps = [Component('C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF')]
    from circuit_analyzer.ilots import _nets_derives
    assert _nets_derives(build_graph(comps)) == set()


# =============================================================================
# Nommage et mapping circuits
# =============================================================================

def test_categorie_majoritaire():
    """@brief Verifie categorie majoritaire.

    @return None
    """
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

def test_impedance_ne_noie_pas_la_fonction_active():
    """@brief Les « Impédance Z » (passifs réduits) ne doivent pas dominer le
    libellé d'un îlot dont la fonction réelle est active.

    Régression de la refonte Z : chaque passif devient une Impédance Z, donc
    les Z sont nombreux et noyaient les montages actifs dans le vote.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
        Component('R2', 'R', {'1': 'N2', '2': 'N3'}, '10k'),
        Component('R3', 'R', {'1': 'N3', '2': 'N4'}, '10k'),
        Component('U1', 'U', {'IN+': 'N4', 'IN-': 'N5', 'OUT': 'N5'}, ''),
    ]
    g = build_graph(comps)
    circuits = [
        _match('Impédance Z', ['R1'], ['N1', 'N2'], categorie='impedance'),
        _match('Impédance Z', ['R2'], ['N2', 'N3'], categorie='impedance'),
        _match('Impédance Z', ['R3'], ['N3', 'N4'], categorie='impedance'),
        _match('Comparateur (AOP)', ['U1'], ['N4', 'N5'], categorie='comparaison'),
    ]
    ilots = detecter_ilots(g, circuits)
    assert len(ilots) == 1
    assert ilots[0]['categorie'] == 'comparaison'


def test_ilot_tout_impedance_reste_impedance():
    """@brief Un îlot composé uniquement d'impédances garde la catégorie « impedance ».

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
        Component('R2', 'R', {'1': 'N2', '2': 'N3'}, '10k'),
    ]
    g = build_graph(comps)
    circuits = [
        _match('Impédance Z', ['R1'], ['N1', 'N2'], categorie='impedance'),
        _match('Impédance Z', ['R2'], ['N2', 'N3'], categorie='impedance'),
    ]
    ilots = detecter_ilots(g, circuits)
    assert ilots[0]['categorie'] == 'impedance'


def test_egalite_liste_les_categories():
    """@brief Verifie egalite liste les categories.

    @return None
    """
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
    """@brief Verifie sans circuit non identifie.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert ilots[0]['categorie'] == 'non identifié'

def test_tri_par_taille_decroissante_et_numerotation():
    """@brief Verifie tri par taille decroissante et numerotation.

    @return None
    """
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
    """@brief Verifie composants tries.

    @return None
    """
    comps = [
        Component('R9', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
        Component('C1', 'C', {'1': 'N2', '2': 'N3'}, '1nF'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert ilots[0]['composants'] == sorted(ilots[0]['composants'])

def test_labels_cp1252():
    """@brief Verifie labels cp1252.

    @return None
    """
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
    """@brief Helper de test pour circuit deux etages."""
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
    """@brief Verifie e2e ilots attache aux resultats.

    @return None
    """
    results = match_patterns(build_graph(_circuit_deux_etages()))
    assert hasattr(results, 'ilots')
    assert isinstance(results.ilots, list)
    assert len(results.ilots) >= 2

def test_e2e_indices_circuits_coherents():
    """@brief Verifie e2e indices circuits coherents.

    @return None
    """
    results = match_patterns(build_graph(_circuit_deux_etages()))
    for ilot in results.ilots:
        for idx in ilot['circuits']:
            match = results[idx]
            # au moins un composant du match est dans l'îlot
            assert any(ref in ilot['composants']
                       for ref in match['components'])

def test_e2e_etages_separes():
    """@brief Verifie e2e etages separes.

    @return None
    """
    results = match_patterns(build_graph(_circuit_deux_etages()))
    groupes = [set(i['composants']) for i in results.ilots]
    assert any({'R1', 'C1'} <= g for g in groupes)
    assert any({'R2', 'R3'} <= g for g in groupes)
    # le filtre et le diviseur ne sont pas dans le même îlot
    assert not any({'R1', 'R2'} <= g for g in groupes)

def test_resultats_analyse_ilots_par_defaut():
    """@brief Verifie resultats analyse ilots par defaut.

    @return None
    """
    from circuit_analyzer.detecteur import ResultatsAnalyse
    r = ResultatsAnalyse()
    assert r.ilots == []


# =============================================================================
# Rapport — section STRUCTURE EN ETAGES
# =============================================================================

from circuit_analyzer.rapport import generer_rapport


def test_rapport_section_etages():
    """@brief Verifie rapport section etages.

    @return None
    """
    comps = _circuit_deux_etages()
    refs = [c.ref for c in comps]
    results = match_patterns(build_graph(comps))
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    assert '=== STRUCTURE EN ETAGES ===' in rapport
    assert 'Îlot 1' in rapport

def test_rapport_etages_numeros_circuits_coherents():
    """@brief Verifie rapport etages numeros circuits coherents.

    @return None
    """
    comps = _circuit_deux_etages()
    refs = [c.ref for c in comps]
    results = match_patterns(build_graph(comps))
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    # le circuit [1] du listing principal doit apparaître avec le même
    # numéro dans la section étages
    section = rapport.split('=== STRUCTURE EN ETAGES ===')[1]
    assert '[1]' in section

def test_rapport_etages_absente_si_list_simple():
    """@brief Verifie rapport etages absente si list simple.

    @return None
    """
    # compat : un appel avec une simple list (sans .ilots) ne plante pas
    comps = _circuit_deux_etages()
    refs = [c.ref for c in comps]
    results = match_patterns(build_graph(comps))
    rapport = generer_rapport(list(results), 'test.txt', len(refs), refs)
    assert '=== STRUCTURE EN ETAGES ===' not in rapport

def test_rapport_etages_ilot_sans_circuit_liste_composants():
    """@brief Verifie rapport etages ilot sans circuit liste composants.

    @return None
    """
    comps = [
        Component('X1', 'R', {'1': 'NET_Z1', '2': 'NET_Z2'}),
    ]
    refs = [c.ref for c in comps]
    results = match_patterns(build_graph(comps))
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    section = rapport.split('=== STRUCTURE EN ETAGES ===')[1]
    assert 'X1' in section

def test_rapport_etages_ligne_autres_pour_membres_hors_circuits():
    """@brief Verifie rapport etages ligne autres pour membres hors circuits.

    @return None
    """
    # X9 est dans l'îlot mais n'appartient à aucun circuit listé
    # ni aux satellites sûrs -> il doit apparaître sur la ligne « Autres »
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
        Component('X9', 'X', {'1': 'NET_MID', '2': 'NET_X'}),  # non classifié
    ]
    refs = [c.ref for c in comps]
    results = match_patterns(build_graph(comps))
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    section = rapport.split('=== STRUCTURE EN ETAGES ===')[1].split('===')[0]
    assert 'Autres : X9' in section


def test_rapport_etages_cp1252():
    """@brief Verifie rapport etages cp1252.

    @return None
    """
    comps = _circuit_deux_etages()
    refs = [c.ref for c in comps]
    results = match_patterns(build_graph(comps))
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    section = rapport.split('=== STRUCTURE EN ETAGES ===')[1].split('===')[0]
    section.encode('cp1252')


# =============================================================================
# Export XML — ordre des blocs par îlot
# =============================================================================

from circuit_analyzer.xml import _grouper_par_circuit


def test_xml_blocs_ordonnes_par_ilot():
    """@brief Verifie xml blocs ordonnes par ilot.

    @return None
    """
    comps = _circuit_deux_etages()
    results = match_patterns(build_graph(comps))
    blocs = _grouper_par_circuit(comps, results)
    labels = [b.label for b in blocs if b.label != 'Divers']
    # ordre attendu : les circuits dans l'ordre des îlots
    attendu = [results[idx]['circuit_type']
               for ilot in results.ilots for idx in ilot['circuits']]
    assert labels == attendu

def test_xml_divers_reste_dernier():
    """@brief Verifie xml divers reste dernier.

    @return None
    """
    comps = _circuit_deux_etages() + [
        Component('R9', 'R', {'1': 'NET_SEUL', '2': 'NET_SEUL2'}),
    ]
    results = match_patterns(build_graph(comps))
    blocs = _grouper_par_circuit(comps, results)
    if any(b.label == 'Divers' for b in blocs):
        assert blocs[-1].label == 'Divers'

def test_xml_compat_list_simple():
    """@brief Verifie xml compat list simple.

    @return None
    """
    # une simple list (sans .ilots) doit garder l'ordre de détection historique
    comps = _circuit_deux_etages()
    results = match_patterns(build_graph(comps))
    blocs_simple = _grouper_par_circuit(comps, list(results))
    labels_simple = [b.label for b in blocs_simple if b.label != 'Divers']
    assert labels_simple == [m['circuit_type'] for m in results]
