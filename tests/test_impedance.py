"""
@file test_impedance.py
@brief Tests du moteur de réduction Z (circuit_analyzer/impedance.py).
"""
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer import impedance


def _graphe(*composants):
    """@brief Construit un graphe de test à partir de composants."""
    return construire_graphe(list(composants))


def _aretes(graphe):
    """@brief (frozenset(nœuds), type, ref) triées, pour comparaison stable."""
    return sorted(
        (tuple(sorted((u, v))), d['type'], d['ref'])
        for u, v, d in graphe.edges(data=True)
    )


def test_combiner_type_homogene_et_mixte():
    assert impedance._combiner_type('R', 'R') == 'R'
    assert impedance._combiner_type('C', 'C') == 'C'
    assert impedance._combiner_type('R', 'C') == 'Z'
    assert impedance._combiner_type('Z', 'R') == 'Z'


def test_aucune_reduction_graphe_inchange():
    # Deux R indépendantes (aucun nœud interne fusionnable) → graphe identique.
    g = _graphe(
        Composant('R1', 'R', {'1': 'IN', '2': 'OUT'}, '10k'),
        Composant('R2', 'R', {'1': 'VCC', '2': 'GND'}, '1k'),
    )
    reduit = impedance.reduire(g)
    assert _aretes(reduit) == _aretes(g)
    # Les valeurs réelles sont préservées sur les singletons.
    vals = {d['ref']: d['value'] for _, _, d in reduit.edges(data=True)}
    assert vals == {'R1': '10k', 'R2': '1k'}
    # Chaque singleton porte refs/composition cohérents.
    r1 = next(d for _, _, d in reduit.edges(data=True) if d['ref'] == 'R1')
    assert r1['refs'] == ['R1'] and r1['composition'] == 'R1'


def test_serie_deux_resistances_entre_bornes():
    # IN ─R1─ MID ─R2─ OUT : MID interne degré 2 → fusion en Z1 = R1+R2.
    # IN et OUT sont des feuilles (degré 1) → bornes, jamais éliminées.
    g = _graphe(
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '1k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'OUT'}, '2k'),
    )
    reduit = impedance.reduire(g)
    aretes = [d for _, _, d in reduit.edges(data=True)]
    assert len(aretes) == 1
    z = aretes[0]
    assert z['type'] == 'R'
    assert sorted(z['refs']) == ['R1', 'R2']
    assert z['composition'] == 'R1+R2'
    assert z['ref'] == 'Z1'
    assert 'MID' not in reduit.nodes()


def test_filtre_rc_isole_devient_z_vers_gnd():
    # IN ─R1─ MID ─C1─ GND : MID interne degré 2 (non-borne), GND est un rail
    # mais on AUTORISE la fusion vers le rail → Z1 = R1+C1 entre IN et GND.
    g = _graphe(
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '10k'),
        Composant('C1', 'C', {'1': 'MID', '2': 'GND'}, '100n'),
    )
    reduit = impedance.reduire(g)
    aretes = [d for _, _, d in reduit.edges(data=True)]
    assert len(aretes) == 1
    z = aretes[0]
    assert z['type'] == 'Z'
    assert sorted(z['refs']) == ['C1', 'R1']
    assert z['composition'] == 'R1+C1'
    assert 'MID' not in reduit.nodes()
    assert set(reduit.nodes()) == {'IN', 'GND'}


def test_parallele_r_et_c_meme_paire():
    # R1 // C1 entre A et B (deux feuilles) → Z mixte, composition (R1//C1).
    g = _graphe(
        Composant('R1', 'R', {'1': 'A', '2': 'B'}, '1k'),
        Composant('C1', 'C', {'1': 'A', '2': 'B'}, '1u'),
    )
    reduit = impedance.reduire(g)
    aretes = [d for _, _, d in reduit.edges(data=True)]
    assert len(aretes) == 1
    z = aretes[0]
    assert z['type'] == 'Z'  # mixte R+C
    assert sorted(z['refs']) == ['C1', 'R1']
    assert z['composition'] == '(R1//C1)'


def test_serie_puis_parallele_imbrique():
    # A ─R1─ MID ─R2─ B  avec  C1 directement entre A et B.
    # Série d'abord : R1+R2 entre A et B ; puis // C1.
    g = _graphe(
        Composant('R1', 'R', {'1': 'A', '2': 'MID'}, '1k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'B'}, '2k'),
        Composant('C1', 'C', {'1': 'A', '2': 'B'}, '1u'),
    )
    reduit = impedance.reduire(g)
    aretes = [d for _, _, d in reduit.edges(data=True)]
    assert len(aretes) == 1
    z = aretes[0]
    assert z['type'] == 'Z'
    assert sorted(z['refs']) == ['C1', 'R1', 'R2']
    assert z['composition'] == '((R1+R2)//C1)'
    assert 'MID' not in reduit.nodes()
