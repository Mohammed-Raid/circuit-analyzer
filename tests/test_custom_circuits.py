"""
@file test_custom_circuits.py
@brief Tests automatises pour test_custom_circuits.
"""

import json
import os
import tempfile

from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.parser import Component
from custom_circuits.loader import (
    CONDITION_DESCRIPTIONS,
    CONDITION_KIND_DESCRIPTIONS,
    CONDITION_KIND_LABELS,
    CONDITION_KINDS,
    CONDITION_LABELS,
    CustomCircuitPattern,
    condition_display,
    get_custom_patterns,
    load_custom_circuits,
    save_custom_circuits,
)


def _tmp_json(data):
    """@brief Helper de test pour tmp json."""
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(data, f)
    f.close()
    return f.name


def test_load_empty_when_file_missing():
    """@brief Verifie load empty when file missing.

    @return None
    """
    assert load_custom_circuits('nonexistent_file.json') == []


def test_save_and_load_roundtrip():
    """@brief Verifie save and load roundtrip.

    @return None
    """
    circuits = [{'name': 'Test', 'components': ['R', 'C'], 'conditions': []}]
    path = tempfile.mktemp(suffix='.json')
    save_custom_circuits(circuits, path)
    loaded = load_custom_circuits(path)
    os.unlink(path)
    assert loaded == circuits


def test_custom_pattern_name():
    """@brief Verifie custom pattern name.

    @return None
    """
    p = CustomCircuitPattern({'name': 'Mon circuit', 'components': ['R'], 'conditions': []})
    assert p.name == 'Mon circuit'


def test_custom_pattern_matches_required_types():
    """@brief Verifie custom pattern matches required types.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'GND'}, '100nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({'name': 'RC', 'components': ['R', 'C'], 'conditions': []})
    matches = p.match(G)
    assert len(matches) == 1
    assert 'R1' in matches[0]['components']
    assert 'C1' in matches[0]['components']


def test_custom_pattern_no_match_when_type_missing():
    """@brief Verifie custom pattern no match when type missing.

    @return None
    """
    comps = [Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k')]
    G = build_graph(comps)
    p = CustomCircuitPattern({'name': 'RC', 'components': ['R', 'C'], 'conditions': []})
    assert p.match(G) == []


def test_condition_c_connected_to_gnd():
    """@brief Verifie condition c connected to gnd.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'GND'}, '100nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Filtre', 'components': ['R', 'C'],
        'conditions': ['C connecté à GND']
    })
    assert len(p.match(G)) == 1


def test_condition_c_connected_to_gnd_fails_when_not():
    """@brief Verifie condition c connected to gnd fails when not.

    @return None
    """
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'NET_C'}, '100nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Filtre', 'components': ['R', 'C'],
        'conditions': ['C connecté à GND']
    })
    assert p.match(G) == []


def test_condition_emitter_to_gnd():
    """@brief Verifie condition emitter to gnd.

    @return None
    """
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_BASE'}, '1k'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Switch', 'components': ['Q', 'R'],
        'conditions': ['Émetteur/Source à GND']
    })
    assert len(p.match(G)) == 1


def test_condition_labels_list():
    """@brief Verifie condition labels list.

    @return None
    """
    assert 'C connecté à GND' in CONDITION_LABELS
    assert 'Émetteur/Source à GND' in CONDITION_LABELS
    assert len(CONDITION_LABELS) >= 5


def test_every_condition_has_a_description():
    """@brief Verifie every condition has a description.

    @return None
    """
    # L'onglet Circuits affiche une description sous chaque case : aucune
    # condition ne doit rester sans explication (sinon case cryptique).
    manquantes = [l for l in CONDITION_LABELS if not CONDITION_DESCRIPTIONS.get(l)]
    assert manquantes == [], f"Conditions sans description : {manquantes}"


def test_deux_occurrences_sans_rapport_donnent_deux_matches_separes():
    """BUG TROUVÉ EN TESTANT (« les conditions de reconnaissance sont mauvaises
    quand on ajoute un nouveau schéma simple ») : deux occurrences du même petit
    montage (R en série avec C, C à GND), sans AUCUN net partagé entre elles,
    doivent donner DEUX matches locaux distincts -- pas un seul blob fusionnant
    toute la carte. Mesuré avant correctif : 1 match ['R1','C1','R2','C2']."""
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'GND'}, '100nF'),
        Component('R2', 'R', {'1': 'NET_X', '2': 'NET_Y'}, '4k7'),
        Component('C2', 'C', {'1': 'NET_Y', '2': 'GND'}, '10nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Snubber', 'components': ['R', 'C'],
        'conditions': ['R en série', 'C connecté à GND'],
    })
    matches = p.match(G)
    assert len(matches) == 2, f"attendu 2 matches locaux, obtenu : {matches}"
    groupes = {frozenset(m['components']) for m in matches}
    assert groupes == {frozenset({'R1', 'C1'}), frozenset({'R2', 'C2'})}


def test_composants_non_qualifiants_dans_l_ilot_n_empechent_pas_le_match():
    """Un composant supplémentaire (non requis par le pattern) dans le MÊME
    îlot physique ne doit ni bloquer ni polluer le match -- seuls les
    composants des types requis apparaissent dans `components`."""
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k'),
        Component('C1', 'C', {'1': 'NET_B', '2': 'GND'}, '100nF'),
        Component('D1', 'D', {'A': 'NET_A', 'K': 'NET_B'}, '1N4148'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Snubber', 'components': ['R', 'C'],
        'conditions': ['C connecté à GND'],
    })
    matches = p.match(G)
    assert len(matches) == 1
    assert set(matches[0]['components']) == {'R1', 'C1'}


def test_condition_generique_broche_vers_rail():
    """BUG TROUVÉ EN TESTANT (« les conditions sont vieilles, pas de possibilité
    d'en ajouter ») : une condition générique paramétrée (dict) doit fonctionner
    exactement comme une condition nommée -- ici l'équivalent de "Diode cathode
    sur alimentation", mais composable sans toucher au code."""
    comps = [
        Component('D1', 'D', {'A': 'NET_A', 'K': 'VCC'}, '1N4148'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Diode custom', 'components': ['D'],
        'conditions': [{'kind': 'broche_vers_rail', 'type': 'D',
                        'broche': 'K', 'rail': 'alimentation'}],
    })
    assert len(p.match(G)) == 1


def test_condition_generique_broche_vers_rail_echoue_si_mauvaise_broche():
    comps = [
        Component('D1', 'D', {'A': 'VCC', 'K': 'NET_A'}, '1N4148'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Diode custom', 'components': ['D'],
        'conditions': [{'kind': 'broche_vers_rail', 'type': 'D',
                        'broche': 'K', 'rail': 'alimentation'}],
    })
    assert p.match(G) == []


def test_condition_generique_broche_vers_rail_sans_broche_precise_teste_toutes():
    """`broche=None` = n'importe quelle broche du composant touche le rail."""
    comps = [Component('C1', 'C', {'1': 'NET_A', '2': 'GND'}, '100nF')]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'C a la masse', 'components': ['C'],
        'conditions': [{'kind': 'broche_vers_rail', 'type': 'C',
                        'broche': None, 'rail': 'masse'}],
    })
    assert len(p.match(G)) == 1


def test_condition_generique_au_moins_n():
    comps = [
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '1k'),
        Component('R2', 'R', {'1': 'N2', '2': 'N3'}, '2k'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Diviseur', 'components': ['R'],
        'conditions': [{'kind': 'au_moins_n', 'type': 'R', 'n': 2}],
    })
    assert len(p.match(G)) == 1
    p_trois = CustomCircuitPattern({
        'name': 'Diviseur3', 'components': ['R'],
        'conditions': [{'kind': 'au_moins_n', 'type': 'R', 'n': 3}],
    })
    assert p_trois.match(G) == []


def test_condition_generique_meme_noeud():
    comps = [
        Component('R1', 'R', {'1': 'NET_SIG', '2': 'N2'}, '1k'),
        Component('C1', 'C', {'1': 'NET_SIG', '2': 'GND'}, '100nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'RC noeud', 'components': ['R', 'C'],
        'conditions': [{'kind': 'meme_noeud', 'types': ['R', 'C']}],
    })
    assert len(p.match(G)) == 1


def test_condition_generique_en_serie():
    comps = [
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '1k'),
        Component('C1', 'C', {'1': 'N2', '2': 'GND'}, '100nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'R serie', 'components': ['R', 'C'],
        'conditions': [{'kind': 'en_serie', 'type': 'R'}],
    })
    assert len(p.match(G)) == 1


def test_condition_generique_type_absent():
    comps = [
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '1k'),
        Component('C1', 'C', {'1': 'N2', '2': 'GND'}, '100nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Passif pur', 'components': ['R', 'C'],
        'conditions': [{'kind': 'type_absent', 'types': ['Q', 'M']}],
    })
    assert len(p.match(G)) == 1


def test_condition_generique_contre_reaction():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT'}),
        Component('Rf', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'AOP feedback', 'components': ['U', 'R'],
        'conditions': [{'kind': 'contre_reaction', 'type': 'U',
                        'broche_source': 'OUT', 'broche_cible': 'IN-'}],
    })
    assert len(p.match(G)) == 1


def test_condition_generique_inconnue_echoue_fail_safe():
    comps = [Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '1k')]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Inconnu', 'components': ['R'],
        'conditions': [{'kind': 'ceci_n_existe_pas'}],
    })
    assert p.match(G) == []


def test_conditions_nommees_et_generiques_melangees():
    """Une définition peut mélanger conditions nommées (str) et génériques
    (dict) dans la même liste -- round-trip JSON transparent (mêmes deux
    formes dans une liste Python : le format natif)."""
    comps = [
        Component('R1', 'R', {'1': 'NET_SIG', '2': 'N2'}, '1k'),
        Component('C1', 'C', {'1': 'NET_SIG', '2': 'GND'}, '100nF'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Mix', 'components': ['R', 'C'],
        'conditions': [
            'C connecté à GND',
            {'kind': 'au_moins_n', 'type': 'R', 'n': 1},
        ],
    })
    assert len(p.match(G)) == 1


def test_condition_generique_json_roundtrip(tmp_path):
    """Une condition générique (dict) survit à un aller-retour JSON, comme
    n'importe quelle autre donnée -- pas de format spécial requis."""
    path = tmp_path / "custom.json"
    circuits = [{
        'name': 'Mix', 'components': ['D'],
        'conditions': [{'kind': 'broche_vers_rail', 'type': 'D',
                        'broche': 'K', 'rail': 'alimentation'}],
    }]
    save_custom_circuits(circuits, path)
    relu = load_custom_circuits(path)
    assert relu == circuits
    p = get_custom_patterns(path)[0]
    comps = [Component('D1', 'D', {'A': 'NET_A', 'K': 'VCC'}, '1N4148')]
    G = build_graph(comps)
    assert len(p.match(G)) == 1


def test_condition_display_gere_les_deux_formats():
    assert condition_display("C connecté à GND") == "Un condensateur relié à la masse"
    assert condition_display({'kind': 'au_moins_n', 'type': 'R', 'n': 2}) == \
        "Au moins 2 composant(s) de type R"


def test_kinds_generiques_ont_tous_un_libelle_et_une_description():
    manquants_label = [k for k in CONDITION_KINDS if not CONDITION_KIND_LABELS.get(k)]
    manquants_desc = [k for k in CONDITION_KINDS if not CONDITION_KIND_DESCRIPTIONS.get(k)]
    assert manquants_label == []
    assert manquants_desc == []


def test_categorie_distingue_photoresistance_d_une_resistance_ordinaire():
    """BUG TROUVÉ EN TESTANT (« AOP + photorésistance -> U + R, indiscernable
    de n'importe quel autre montage U+R ») : un pattern exigeant spécifiquement
    "R (Photorésistance)" ne doit PAS matcher un îlot avec une résistance
    ordinaire du même type électrique -- et DOIT matcher un îlot avec la vraie
    photorésistance."""
    comps_ordinaire = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2'}),
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
    ]
    comps_ordinaire[1].categorie = 'Résistance'
    G_ordinaire = build_graph(comps_ordinaire)

    comps_photo = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2'}),
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, ''),
    ]
    comps_photo[1].categorie = 'Photorésistance'
    G_photo = build_graph(comps_photo)

    p = CustomCircuitPattern({
        'name': 'Capteur lumière',
        'components': ['U', {'type': 'R', 'categorie': 'Photorésistance'}],
        'conditions': [],
    })
    assert p.match(G_ordinaire) == [], \
        "une résistance ordinaire ne doit pas satisfaire l'exigence 'Photorésistance'"
    assert len(p.match(G_photo)) == 1


def test_categorie_absente_matche_comme_avant_type_seul():
    """Une entrée `components` sans dict (juste "R") continue de matcher
    N'IMPORTE QUEL R, categorie ou pas -- comportement d'origine inchangé."""
    comps = [Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '10k')]
    comps[0].categorie = 'Photorésistance'
    G = build_graph(comps)
    p = CustomCircuitPattern({'name': 'R generique', 'components': ['R'], 'conditions': []})
    assert len(p.match(G)) == 1


def test_condition_generique_categorie_broche_vers_rail():
    """La condition générique elle-même peut aussi filtrer par categorie, pas
    seulement l'exigence de haut niveau -- ex. « la photorésistance touche
    l'alimentation », distinct de « une résistance quelconque »."""
    comps = [Component('R1', 'R', {'1': 'N1', '2': 'VCC'}, '')]
    comps[0].categorie = 'Photorésistance'
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Photo vers alim', 'components': ['R'],
        'conditions': [{'kind': 'broche_vers_rail', 'type': 'R',
                        'categorie': 'Photorésistance', 'broche': None,
                        'rail': 'alimentation'}],
    })
    assert len(p.match(G)) == 1

    comps_autre = [Component('R1', 'R', {'1': 'N1', '2': 'VCC'}, '10k')]
    comps_autre[0].categorie = 'Résistance'
    G_autre = build_graph(comps_autre)
    assert p.match(G_autre) == [], \
        "une resistance NON photoresistance ne doit pas satisfaire la condition"


def test_condition_display_affiche_la_categorie():
    from custom_circuits.loader import condition_display
    txt = condition_display({'kind': 'au_moins_n', 'type': 'R',
                             'categorie': 'Photorésistance', 'n': 1})
    assert 'Photorésistance' in txt
    assert 'R' in txt


# ── connexion_broches ────────────────────────────────────────────────────────
# BUG TROUVÉ EN TESTANT (demande utilisateur : « select the pins of componant
# and choose the connection between them, u can choose 2 or 1 also »).

def test_connexion_broches_entre_deux_composants_differents():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2'}),
        Component('R1', 'R', {'1': 'N1', '2': 'N3'}, '10k'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Connexion', 'components': ['U', 'R'],
        'conditions': [{'kind': 'connexion_broches',
                        'cote_a': {'type': 'R', 'broches': ['1']},
                        'cote_b': {'type': 'U', 'broches': ['IN-']}}],
    })
    assert len(p.match(G)) == 1


def test_connexion_broches_echoue_si_pas_connectees():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2'}),
        Component('R1', 'R', {'1': 'N9', '2': 'N3'}, '10k'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Connexion', 'components': ['U', 'R'],
        'conditions': [{'kind': 'connexion_broches',
                        'cote_a': {'type': 'R', 'broches': ['1']},
                        'cote_b': {'type': 'U', 'broches': ['IN-']}}],
    })
    assert p.match(G) == []


def test_connexion_broches_ensemble_de_broches_ou():
    """"broches": ['1', '2'] = pin 1 OU pin 2 -- ici seule la broche 2 est
    reliée à IN-, le match doit quand meme reussir."""
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2'}),
        Component('R1', 'R', {'1': 'N9', '2': 'N1'}, '10k'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Connexion', 'components': ['U', 'R'],
        'conditions': [{'kind': 'connexion_broches',
                        'cote_a': {'type': 'R', 'broches': ['1', '2']},
                        'cote_b': {'type': 'U', 'broches': ['IN-']}}],
    })
    assert len(p.match(G)) == 1


# ── Lot "we are very limited, add all the possible pattern of a schema"
# (demande utilisateur 2026-08-18) : comparateur sur au_moins_n, en_parallele,
# broche_non_connectee, valeur_compare, meme_valeur, nombre_broches.

def test_au_moins_n_comparateur_exactement():
    comps = [Component('R1', 'R', {'1': 'N1', '2': 'GND'}, '10k'),
             Component('R2', 'R', {'1': 'N1', '2': 'N2'}, '10k')]
    G = build_graph(comps)
    p_egal = CustomCircuitPattern({
        'name': 'Test', 'components': ['R'],
        'conditions': [{'kind': 'au_moins_n', 'type': 'R', 'n': 2, 'comparateur': '=='}]})
    assert len(p_egal.match(G)) == 1
    p_egal3 = CustomCircuitPattern({
        'name': 'Test3', 'components': ['R'],
        'conditions': [{'kind': 'au_moins_n', 'type': 'R', 'n': 3, 'comparateur': '=='}]})
    assert p_egal3.match(G) == []


def test_au_moins_n_comparateur_au_plus():
    comps = [Component('R1', 'R', {'1': 'N1', '2': 'GND'}, '10k')]
    G = build_graph(comps)
    p_ok = CustomCircuitPattern({
        'name': 'Test', 'components': ['R'],
        'conditions': [{'kind': 'au_moins_n', 'type': 'R', 'n': 1, 'comparateur': '<='}]})
    assert len(p_ok.match(G)) == 1
    p_trop_strict = CustomCircuitPattern({
        'name': 'Test2', 'components': ['R'],
        'conditions': [{'kind': 'au_moins_n', 'type': 'R', 'n': 0, 'comparateur': '<='}]})
    assert p_trop_strict.match(G) == []


def test_au_moins_n_sans_comparateur_reste_au_moins():
    """Non-regression : une condition sauvegardee AVANT l'ajout du comparateur
    (pas de cle "comparateur") continue de se comporter comme ">="."""
    comps = [Component('R1', 'R', {'1': 'N1', '2': 'GND'}, '10k'),
             Component('R2', 'R', {'1': 'N1', '2': 'N2'}, '10k')]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Test', 'components': ['R'],
        'conditions': [{'kind': 'au_moins_n', 'type': 'R', 'n': 2}]})
    assert len(p.match(G)) == 1


def test_en_parallele_deux_broches_partagees():
    comps = [Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
             Component('R2', 'R', {'1': 'N1', '2': 'N2'}, '4.7k')]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Parallele', 'components': ['R'],
        'conditions': [{'kind': 'en_parallele', 'types': ['R', 'R']}]})
    assert len(p.match(G)) == 1


def test_en_parallele_echoue_si_un_seul_noeud_partage():
    """Un seul noeud commun (pas les deux) = 'meme_noeud', pas 'en_parallele'."""
    comps = [Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
             Component('R2', 'R', {'1': 'N1', '2': 'N3'}, '4.7k')]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Parallele', 'components': ['R'],
        'conditions': [{'kind': 'en_parallele', 'types': ['R', 'R']}]})
    assert p.match(G) == []


def test_broche_non_connectee_detecte_nc():
    comps = [Component('U1', 'U', {'IN+': 'N1', 'IN-': 'N2', 'OUT': 'N3', 'V+': 'NC'})]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Flottant', 'components': ['U'],
        'conditions': [{'kind': 'broche_non_connectee', 'type': 'U', 'broche': 'V+'}]})
    assert len(p.match(G)) == 1


def test_broche_non_connectee_echoue_si_cablee():
    comps = [Component('U1', 'U', {'IN+': 'N1', 'IN-': 'N2', 'OUT': 'N3'}),
             Component('R1', 'R', {'1': 'N2', '2': 'GND'}, '10k')]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Flottant', 'components': ['U'],
        'conditions': [{'kind': 'broche_non_connectee', 'type': 'U', 'broche': 'IN-'}]})
    assert p.match(G) == []


def test_valeur_compare_superieur():
    comps = [Component('R1', 'R', {'1': 'N1', '2': 'GND'}, '100k')]
    G = build_graph(comps)
    p_ok = CustomCircuitPattern({
        'name': 'Pullup', 'components': ['R'],
        'conditions': [{'kind': 'valeur_compare', 'type': 'R',
                        'comparateur': '>', 'seuil': 10000}]})
    assert len(p_ok.match(G)) == 1
    p_trop_haut = CustomCircuitPattern({
        'name': 'Pullup2', 'components': ['R'],
        'conditions': [{'kind': 'valeur_compare', 'type': 'R',
                        'comparateur': '>', 'seuil': 1_000_000}]})
    assert p_trop_haut.match(G) == []


def test_valeur_compare_ignore_valeur_illisible_sans_planter():
    comps = [Component('R1', 'R', {'1': 'N1', '2': 'GND'}, '')]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Test', 'components': ['R'],
        'conditions': [{'kind': 'valeur_compare', 'type': 'R',
                        'comparateur': '>', 'seuil': 1}]})
    assert p.match(G) == []


def test_meme_valeur_paire_appairee():
    comps = [Component('R1', 'R', {'1': 'N1', '2': 'GND'}, '10k'),
             Component('R2', 'R', {'1': 'N1', '2': 'N2'}, '10k')]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Appairee', 'components': ['R'],
        'conditions': [{'kind': 'meme_valeur', 'types': ['R', 'R']}]})
    assert len(p.match(G)) == 1


def test_meme_valeur_echoue_si_differentes():
    comps = [Component('R1', 'R', {'1': 'N1', '2': 'GND'}, '10k'),
             Component('R2', 'R', {'1': 'N1', '2': 'N2'}, '4.7k')]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Appairee', 'components': ['R'],
        'conditions': [{'kind': 'meme_valeur', 'types': ['R', 'R']}]})
    assert p.match(G) == []


def test_nombre_broches_boitier_8_pins():
    comps = [Component('U1', 'U', {str(i): f'N{i}' for i in range(1, 9)})]
    G = build_graph(comps)
    p_ok = CustomCircuitPattern({
        'name': 'DIP8', 'components': ['U'],
        'conditions': [{'kind': 'nombre_broches', 'type': 'U',
                        'comparateur': '==', 'n': 8}]})
    assert len(p_ok.match(G)) == 1
    p_faux = CustomCircuitPattern({
        'name': 'DIP3', 'components': ['U'],
        'conditions': [{'kind': 'nombre_broches', 'type': 'U',
                        'comparateur': '==', 'n': 3}]})
    assert p_faux.match(G) == []


def test_nouveaux_kinds_dans_la_registry():
    for k in ('en_parallele', 'broche_non_connectee', 'valeur_compare',
             'meme_valeur', 'nombre_broches'):
        assert k in CONDITION_KINDS
        assert k in CONDITION_KIND_LABELS
        assert k in CONDITION_KIND_DESCRIPTIONS


def test_condition_display_nouveaux_kinds_ne_retombe_pas_sur_le_dict_brut():
    exemples = [
        {'kind': 'en_parallele', 'types': ['R', 'R']},
        {'kind': 'broche_non_connectee', 'type': 'U', 'broche': 'V+'},
        {'kind': 'valeur_compare', 'type': 'R', 'comparateur': '>', 'seuil': 1000},
        {'kind': 'meme_valeur', 'types': ['R', 'R']},
        {'kind': 'nombre_broches', 'type': 'U', 'comparateur': '==', 'n': 8},
    ]
    for cond in exemples:
        texte = condition_display(cond)
        assert "'kind'" not in texte, f"retombe sur repr(dict) brut : {texte}"


def test_connexion_broches_n_importe_laquelle_des_deux_cotes():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2'}),
        Component('R1', 'R', {'1': 'N9', '2': 'N1'}, '10k'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Connexion', 'components': ['U', 'R'],
        'conditions': [{'kind': 'connexion_broches',
                        'cote_a': {'type': 'R', 'broches': []},
                        'cote_b': {'type': 'U', 'broches': []}}],
    })
    assert len(p.match(G)) == 1


def test_connexion_broches_meme_composant():
    """cote_b.meme_composant=True : cherche une connexion entre deux broches
    du MÊME composant (ex. deux broches d'un IC court-circuitées entre elles
    par le montage, ou par une broche partagée)."""
    comps = [
        Component('U1', 'U', {'IN+': 'N1', 'IN-': 'N1', 'OUT': 'N2'}),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Court-circuit', 'components': ['U'],
        'conditions': [{'kind': 'connexion_broches',
                        'cote_a': {'type': 'U', 'broches': ['IN+']},
                        'cote_b': {'meme_composant': True, 'broches': ['IN-']}}],
    })
    assert len(p.match(G)) == 1


def test_connexion_broches_meme_composant_echoue_si_pas_relie():
    comps = [
        Component('U1', 'U', {'IN+': 'N1', 'IN-': 'N4', 'OUT': 'N2'}),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Court-circuit', 'components': ['U'],
        'conditions': [{'kind': 'connexion_broches',
                        'cote_a': {'type': 'U', 'broches': ['IN+']},
                        'cote_b': {'meme_composant': True, 'broches': ['IN-']}}],
    })
    assert p.match(G) == []


def test_connexion_broches_avec_categorie():
    """Le filtre par nom précis (categorie) s'applique aussi à chaque côté."""
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2'}),
        Component('R1', 'R', {'1': 'N1', '2': 'N3'}, ''),
    ]
    comps[1].categorie = 'Photorésistance'
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Connexion', 'components': ['U', 'R'],
        'conditions': [{'kind': 'connexion_broches',
                        'cote_a': {'type': 'R', 'categorie': 'Photorésistance', 'broches': ['1']},
                        'cote_b': {'type': 'U', 'broches': ['IN-']}}],
    })
    assert len(p.match(G)) == 1

    comps_autre = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2'}),
        Component('R1', 'R', {'1': 'N1', '2': 'N3'}, '10k'),
    ]
    comps_autre[1].categorie = 'Résistance'
    assert p.match(build_graph(comps_autre)) == [], \
        "une resistance ordinaire ne doit pas satisfaire le filtre categorie"


def test_connexion_broches_display():
    from custom_circuits.loader import condition_display
    txt_autre = condition_display({
        'kind': 'connexion_broches',
        'cote_a': {'type': 'R', 'broches': ['1', '2']},
        'cote_b': {'type': 'U', 'broches': ['IN-']},
    })
    assert '1 ou 2' in txt_autre
    assert 'R' in txt_autre and 'U' in txt_autre

    txt_meme = condition_display({
        'kind': 'connexion_broches',
        'cote_a': {'type': 'U', 'broches': ['IN+']},
        'cote_b': {'meme_composant': True, 'broches': ['IN-']},
    })
    assert 'même composant' in txt_meme


# ── connexion_broches : "sens" (jamais connectée) et "mode" (toutes les
# broches, pas juste une) -- demande utilisateur 2026-08-18 : « add more
# costomation ... choose like 1 to a lot of pins or this one should never be
# connected to this ».

def test_connexion_broches_sens_jamais_connectee_echoue_si_connectees():
    """R relié à IN- : la condition "jamais connectée" doit donc echouer."""
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2'}),
        Component('R1', 'R', {'1': 'N1', '2': 'N3'}, '10k'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Jamais', 'components': ['U', 'R'],
        'conditions': [{'kind': 'connexion_broches', 'sens': 'jamais_connectee',
                        'cote_a': {'type': 'R', 'broches': ['1']},
                        'cote_b': {'type': 'U', 'broches': ['IN-']}}],
    })
    assert p.match(G) == []


def test_connexion_broches_sens_jamais_connectee_reussit_si_pas_connectees():
    # R1.2 partage OUT (N2) avec U1 -- meme ilot -- mais R1.1 (N9) et IN- (N1)
    # restent des nets distincts : c'est bien EUX qu'on verifie.
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2'}),
        Component('R1', 'R', {'1': 'N9', '2': 'N2'}, '10k'),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Jamais', 'components': ['U', 'R'],
        'conditions': [{'kind': 'connexion_broches', 'sens': 'jamais_connectee',
                        'cote_a': {'type': 'R', 'broches': ['1']},
                        'cote_b': {'type': 'U', 'broches': ['IN-']}}],
    })
    assert len(p.match(G)) == 1


def test_connexion_broches_jamais_connectee_vrai_si_composant_absent():
    """Le type reference par cote_a n'existe meme pas dans l'ilot : rien a
    exclure, la condition "jamais" est satisfaite par defaut (comme
    type_absent)."""
    comps = [Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2'})]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Jamais', 'components': ['U'],
        'conditions': [{'kind': 'connexion_broches', 'sens': 'jamais_connectee',
                        'cote_a': {'type': 'R', 'broches': ['1']},
                        'cote_b': {'type': 'U', 'broches': ['IN-']}}],
    })
    assert len(p.match(G)) == 1


def test_connexion_broches_mode_toutes_deux_broches_du_meme_composant_court_circuitees():
    """mode="toutes" cote_a + meme_composant : les DEUX broches choisies cote_a
    doivent chacune retrouver leur net sur C -- un jumper A/B/C court-circuite
    matche (D sur un net distinct : evite le filtre "composant degenere" de
    detecter_ilots, qui ecarte un composant dont TOUTES les broches sont sur
    le meme net -- mesure via check_graph_model, cf. test similaire plus haut)."""
    comps_ok = [Component('J1', 'J', {'A': 'N1', 'B': 'N1', 'C': 'N1', 'D': 'N2'})]
    G_ok = build_graph(comps_ok)
    p = CustomCircuitPattern({
        'name': 'Pont', 'components': ['J'],
        'conditions': [{'kind': 'connexion_broches',
                        'cote_a': {'type': 'J', 'broches': ['A', 'B'], 'mode': 'toutes'},
                        'cote_b': {'meme_composant': True, 'broches': ['C']}}],
    })
    assert len(p.match(G_ok)) == 1


def test_connexion_broches_mode_toutes_echoue_si_une_seule_broche_relie():
    """Même condition mais SEULE A (pas B) est reliée à C : mode="toutes" doit
    échouer -- démontre que c'est bien plus strict que le défaut "au_moins_une"
    (qui aurait matché grâce à A seule)."""
    comps_partiel = [Component('J1', 'J', {'A': 'N1', 'B': 'N2', 'C': 'N1'})]
    G_partiel = build_graph(comps_partiel)
    p_toutes = CustomCircuitPattern({
        'name': 'Pont', 'components': ['J'],
        'conditions': [{'kind': 'connexion_broches',
                        'cote_a': {'type': 'J', 'broches': ['A', 'B'], 'mode': 'toutes'},
                        'cote_b': {'meme_composant': True, 'broches': ['C']}}],
    })
    assert p_toutes.match(G_partiel) == []

    p_au_moins_une = CustomCircuitPattern({
        'name': 'Pont2', 'components': ['J'],
        'conditions': [{'kind': 'connexion_broches',
                        'cote_a': {'type': 'J', 'broches': ['A', 'B']},
                        'cote_b': {'meme_composant': True, 'broches': ['C']}}],
    })
    assert len(p_au_moins_une.match(G_partiel)) == 1


def test_connexion_broches_mode_au_moins_une_reste_le_defaut():
    """Sans "mode" precise, comportement inchange (une seule broche suffit)."""
    comps = [
        Component('U1', 'U', {'IN+': 'N1', 'IN-': 'N2', 'OUT': 'N3',
                              'V+': 'GND', 'V-': 'N4'}),
    ]
    G = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'Alim', 'components': ['U'],
        'conditions': [{'kind': 'connexion_broches',
                        'cote_a': {'type': 'U', 'broches': ['V+', 'V-']},
                        'cote_b': {'meme_composant': True, 'broches': ['IN+']}}],
    })
    assert p.match(G) == []


def test_connexion_broches_display_sens_et_mode():
    from custom_circuits.loader import condition_display
    txt = condition_display({
        'kind': 'connexion_broches', 'sens': 'jamais_connectee',
        'cote_a': {'type': 'R', 'broches': ['1'], 'mode': 'toutes'},
        'cote_b': {'type': 'U', 'broches': ['IN-']},
    })
    assert 'JAMAIS' in txt


# [MODIF 2026-08-19] BUG TROUVÉ EN TESTANT (demande utilisateur, repro exacte
# via son fichier réel `test4.xml` : pattern « 1 AOP + 1 photorésistance »
# matche quand même un îlot contenant EN PLUS 2 ampoules -- « i did specify
# there is no other more composant then this there is no this option »).
# `_requis_satisfaits` ne vérifie que la PRÉSENCE des types requis ; les
# ampoules (type X, comme la photorésistance, mais categorie "Ampoule") ne sont
# vues par AUCUNE condition existante (toutes filtrées par categorie) --
# reproduit ici avec les mêmes composants que le fichier réel de l'utilisateur.
def _pattern_aop_photoresistance(composition_exacte: bool = False) -> dict:
    return {
        'name': 'test',
        'components': [
            {'type': 'X', 'categorie': 'Photoresistance'},
            {'type': 'U', 'categorie': 'AOP'},
        ],
        'composition_exacte': composition_exacte,
        'conditions': [
            {'kind': 'au_moins_n', 'type': 'U', 'categorie': 'AOP',
             'n': 1, 'comparateur': '=='},
            {'kind': 'au_moins_n', 'type': 'X', 'categorie': 'Photoresistance',
             'n': 1, 'comparateur': '=='},
        ],
    }


def test_composition_exacte_defaut_desactivee_matche_avec_composants_en_trop():
    """Comportement HISTORIQUE (option absente/False) : inchangé -- des ampoules
    en plus dans l'îlot ne bloquent pas le match (regression guard)."""
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2',
                              'V+': 'NC', 'V-': 'NC'}, categorie='AOP'),
        Component('X1', 'X', {'1': 'N1', '2': 'N2'}, categorie='Photoresistance'),
        Component('X2', 'X', {'1': 'N3', '2': 'N1'}, categorie='Ampoule'),
        Component('X3', 'X', {'1': 'N3', '2': 'N1'}, categorie='Ampoule'),
    ]
    graph = build_graph(comps)
    p = CustomCircuitPattern(_pattern_aop_photoresistance(composition_exacte=False))
    assert len(p.match(graph)) == 1


def test_composition_exacte_activee_rejette_les_composants_en_trop():
    """Reproduction exacte du signalement utilisateur : mêmes composants que
    ci-dessus, mais `composition_exacte: True` -- ne doit PLUS matcher."""
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2',
                              'V+': 'NC', 'V-': 'NC'}, categorie='AOP'),
        Component('X1', 'X', {'1': 'N1', '2': 'N2'}, categorie='Photoresistance'),
        Component('X2', 'X', {'1': 'N3', '2': 'N1'}, categorie='Ampoule'),
        Component('X3', 'X', {'1': 'N3', '2': 'N1'}, categorie='Ampoule'),
    ]
    graph = build_graph(comps)
    p = CustomCircuitPattern(_pattern_aop_photoresistance(composition_exacte=True))
    assert p.match(graph) == []


def test_composition_exacte_activee_matche_toujours_sans_composant_en_trop():
    """`composition_exacte: True` ne doit PAS empêcher le match légitime --
    seulement rejeter les composants HORS de la liste requise."""
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2',
                              'V+': 'NC', 'V-': 'NC'}, categorie='AOP'),
        Component('X1', 'X', {'1': 'N1', '2': 'N2'}, categorie='Photoresistance'),
    ]
    graph = build_graph(comps)
    p = CustomCircuitPattern(_pattern_aop_photoresistance(composition_exacte=True))
    assert len(p.match(graph)) == 1


def test_composition_exacte_ignore_categorie_non_verrouillee():
    """Une exigence sans categorie verrouillée (ex. juste "R") accepte N'IMPORTE
    QUEL composant de ce type, même avec composition_exacte activée -- seule une
    categorie DIFFÉRENTE de celle exigée, ou un type non listé du tout, est rejetée."""
    comps = [
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, categorie='Résistance A'),
        Component('R2', 'R', {'1': 'N1', '2': 'N2'}, categorie='Résistance B'),
    ]
    graph = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'DeuxR', 'components': ['R'],
        'composition_exacte': True,
        'conditions': [],
    })
    assert len(p.match(graph)) == 1


def test_composition_exacte_rejette_type_non_liste_du_tout():
    """Un composant d'un type qui n'apparaît PAS du tout dans "components"
    (pas seulement une categorie différente) doit aussi être rejeté."""
    comps = [
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}),
        Component('C1', 'C', {'1': 'N1', '2': 'N2'}),
    ]
    graph = build_graph(comps)
    p = CustomCircuitPattern({
        'name': 'JusteR', 'components': ['R'],
        'composition_exacte': True,
        'conditions': [],
    })
    assert p.match(graph) == []


def test_connexion_broches_display_mode_toutes_sans_broches_precisees():
    """[MODIF 2026-08-19] BUG TROUVÉ EN TESTANT (demande utilisateur : « the
    verification etape ... need to be exactly precise on what condition u did »)
    : mode="toutes" + "broches" absente/vide veut dire "TOUTES les broches DU
    COMPOSANT" côté évaluation (cf. `_evaluer_condition_generique`, "toutes"
    sans liste explicite -> `pins_a_cfg = list(comp_a.pins.keys())`) -- avant
    ce correctif, l'affichage retombait sur "n'importe laquelle", RIGOUREUSEMENT
    IDENTIQUE au texte d'un mode "au_moins_une" sur les mêmes broches, alors que
    ce sont deux conditions électriquement différentes. Le texte doit
    maintenant les distinguer sans ambiguïté."""
    from custom_circuits.loader import condition_display
    txt_toutes = condition_display({
        'kind': 'connexion_broches',
        'cote_a': {'type': 'U', 'mode': 'toutes'},
        'cote_b': {'type': 'R'},
    })
    txt_au_moins_une = condition_display({
        'kind': 'connexion_broches',
        'cote_a': {'type': 'U'},
        'cote_b': {'type': 'R'},
    })
    assert txt_toutes != txt_au_moins_une
    assert 'TOUTES' in txt_toutes
    assert 'TOUTES' not in txt_au_moins_une


def test_get_custom_patterns_returns_empty_when_no_file():
    """@brief Verifie get custom patterns returns empty when no file.

    @return None
    """
    patterns = get_custom_patterns('nonexistent.json')
    assert patterns == []
