"""
Tests de circuit_analyzer/reduction.py — réduction des sous-réseaux passifs
en dipôles équivalents (directive rouge du document : « créer le dipôle Rf »).
"""
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.reduction import reduire_dipoles, expandre_composites


def _graphe(*composants):
    return construire_graphe(list(composants))


# Composant actif servant d'ancre : la réduction n'opère que sur les réseaux
# passifs reliés à au moins une broche active (directive métier).
def _aop(in_plus='P', in_moins='M', out='O'):
    return Composant('U1', 'U', {'IN+': in_plus, 'IN-': in_moins, 'OUT': out})


def _aretes(graphe):
    """Liste (frozenset(nœuds), type, ref) des arêtes, pour comparaison stable."""
    return sorted(
        (tuple(sorted((u, v))), d['type'], d['ref'])
        for u, v, d in graphe.edges(data=True)
    )


# ── Préservation de la valeur (non-régression stricte) ─────────────────────────

def test_singleton_conserve_sa_valeur_reelle():
    # Un passif non fusionné (R de feedback unique, ancré par l'AOP) doit garder
    # sa value d'origine dans le graphe réduit — pas son ref comme value.
    g = _graphe(
        _aop(in_moins='INM', out='OUT'),
        Composant('Rf', 'R', {'1': 'INM', '2': 'OUT'}, '10k'),
    )
    reduit, expansion = reduire_dipoles(g)
    assert expansion == {}
    rf = next(d for _, _, d in reduit.edges(data=True) if d['ref'] == 'Rf')
    assert rf['value'] == '10k'   # et surtout PAS 'Rf'


def test_reseau_flottant_conserve_valeurs():
    # Pont diviseur non ancré : intact, valeurs comprises.
    g = _graphe(
        Composant('R1', 'R', {'1': 'VCC', '2': 'DIV'}, '10k'),
        Composant('R2', 'R', {'1': 'DIV', '2': 'GND'}, '4k7'),
    )
    reduit, _ = reduire_dipoles(g)
    vals = {d['ref']: d['value'] for _, _, d in reduit.edges(data=True)}
    assert vals == {'R1': '10k', 'R2': '4k7'}


# ── Non-régression : aucun composite → graphe inchangé ─────────────────────────

def test_aucune_reduction_si_pas_de_composite():
    g = _graphe(
        Composant('R1', 'R', {'1': 'A', '2': 'B'}, '10k'),
        Composant('R2', 'R', {'1': 'B', '2': 'GND'}, '1k'),
    )
    # B est interne degré 2 → SERAIT réductible, mais on veut vérifier qu'une
    # vraie chaîne EST réduite ; ici on teste plutôt deux R indépendantes :
    g2 = _graphe(
        Composant('R1', 'R', {'1': 'IN', '2': 'OUT'}, '10k'),
        Composant('R2', 'R', {'1': 'VCC', '2': 'GND'}, '1k'),
    )
    reduit, expansion = reduire_dipoles(g2)
    assert expansion == {}
    assert _aretes(reduit) == _aretes(g2)


# ── Série : deux résistances en chaîne → une R équivalente ─────────────────────

def test_serie_deux_resistances():
    # INM ─[R1]─ MID ─[R2]─ OUT ; MID interne, ancré par l'AOP (INM, OUT)
    g = _graphe(
        _aop(in_moins='INM', out='OUT'),
        Composant('R1', 'R', {'1': 'INM', '2': 'MID'}, '10k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'OUT'}, '10k'),
    )
    reduit, expansion = reduire_dipoles(g)
    passives = [(u, v, d) for u, v, d in reduit.edges(data=True)
                if d['type'] in ('R', 'C', 'L', 'Z')]
    assert len(passives) == 1
    u, v, d = passives[0]
    assert {u, v} == {'INM', 'OUT'}          # MID éliminé
    assert d['type'] == 'R'                  # R+R = R
    assert d['ref'] in expansion
    assert sorted(expansion[d['ref']]) == ['R1', 'R2']


def test_serie_trois_resistances():
    g = _graphe(
        _aop(in_moins='A', out='D'),
        Composant('R1', 'R', {'1': 'A', '2': 'B'}, '1k'),
        Composant('R2', 'R', {'1': 'B', '2': 'C'}, '1k'),
        Composant('R3', 'R', {'1': 'C', '2': 'D'}, '1k'),
    )
    reduit, expansion = reduire_dipoles(g)
    passives = [(u, v, d) for u, v, d in reduit.edges(data=True)
                if d['type'] in ('R', 'C', 'L', 'Z')]
    assert len(passives) == 1
    u, v, d = passives[0]
    assert {u, v} == {'A', 'D'}
    assert sorted(expansion[d['ref']]) == ['R1', 'R2', 'R3']


def test_reseau_flottant_non_reduit():
    # Réseau passif sans broche active : ne doit PAS être réduit (snubber, etc.)
    g = _graphe(
        Composant('R1', 'R', {'1': 'A', '2': 'MID'}, '10k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'B'}, '10k'),
    )
    reduit, expansion = reduire_dipoles(g)
    assert expansion == {}
    assert len(list(reduit.edges())) == 2


def test_hub_partage_plusieurs_branches_serie():
    # N branches composites (R série R) entre LE MÊME couple IN-/OUT — topologie
    # à « hub » partagé. Chaque branche doit fusionner, puis le banc parallèle
    # résultant fusionne en un seul dipôle. Vérifie l'absence de régression de la
    # passe série groupée (les centres MMi partagent les voisins INM/OUT).
    comps = [_aop(in_moins='INM', out='OUT')]
    attendus = []
    for i in range(5):
        comps.append(Composant(f'Ra{i}', 'R', {'1': 'INM', '2': f'M{i}'}, '5k'))
        comps.append(Composant(f'Rb{i}', 'R', {'1': f'M{i}', '2': 'OUT'}, '5k'))
        attendus += [f'Ra{i}', f'Rb{i}']
    reduit, expansion = reduire_dipoles(_graphe(*comps))
    passives = [(u, v, d) for u, v, d in reduit.edges(data=True)
                if d['type'] in ('R', 'C', 'L', 'Z')]
    assert len(passives) == 1                      # tout collapse en 1 dipôle
    u, v, d = passives[0]
    assert {u, v} == {'INM', 'OUT'}
    assert sorted(expansion[d['ref']]) == sorted(attendus)   # aucun ref perdu


def test_serie_creant_un_banc_parallele():
    # X-Ra-M-Rb-Y et déjà un Rc direct X-Y : après la fusion série (Ra+Rb),
    # un banc parallèle (Ra+Rb)//Rc apparaît et doit fusionner à son tour.
    g = _graphe(
        _aop(in_moins='X', out='Y'),
        Composant('Ra', 'R', {'1': 'X', '2': 'M'}, '5k'),
        Composant('Rb', 'R', {'1': 'M', '2': 'Y'}, '5k'),
        Composant('Rc', 'R', {'1': 'X', '2': 'Y'}, '10k'),
    )
    reduit, expansion = reduire_dipoles(g)
    passives = [d for _, _, d in reduit.edges(data=True)
                if d['type'] in ('R', 'C', 'L', 'Z')]
    assert len(passives) == 1
    assert sorted(expansion[passives[0]['ref']]) == ['Ra', 'Rb', 'Rc']


# ── Parallèle : deux composants entre les mêmes nœuds → un équivalent ──────────

def test_parallele_deux_resistances():
    # R1//R2 entre IN- et OUT (contre-réaction), ancré par l'AOP
    g = _graphe(
        _aop(in_moins='X', out='Y'),
        Composant('R1', 'R', {'1': 'X', '2': 'Y'}, '10k'),
        Composant('R2', 'R', {'1': 'X', '2': 'Y'}, '10k'),
    )
    reduit, expansion = reduire_dipoles(g)
    passives = [d for _, _, d in reduit.edges(data=True)
                if d['type'] in ('R', 'C', 'L', 'Z')]
    assert len(passives) == 1
    d = passives[0]
    assert d['type'] == 'R'
    assert sorted(expansion[d['ref']]) == ['R1', 'R2']


def test_parallele_R_et_C_donne_impedance_composite():
    # R // C en contre-réaction : type équivalent 'Z' (ni résistif ni capacitif pur)
    g = _graphe(
        _aop(in_moins='X', out='Y'),
        Composant('R1', 'R', {'1': 'X', '2': 'Y'}, '10k'),
        Composant('C1', 'C', {'1': 'X', '2': 'Y'}, '100n'),
    )
    reduit, expansion = reduire_dipoles(g)
    passives = [d for _, _, d in reduit.edges(data=True)
                if d['type'] in ('R', 'C', 'L', 'Z')]
    assert len(passives) == 1
    d = passives[0]
    assert d['type'] == 'Z'
    assert sorted(expansion[d['ref']]) == ['C1', 'R1']


# ── Protection : un rail ne doit jamais être éliminé ───────────────────────────

def test_noeud_masse_jamais_elimine():
    # R1 vers GND, R2 depuis GND : GND est un rail, NE DOIT PAS fusionner
    g = _graphe(
        Composant('R1', 'R', {'1': 'A', '2': 'GND'}, '10k'),
        Composant('R2', 'R', {'1': 'GND', '2': 'B'}, '10k'),
    )
    reduit, expansion = reduire_dipoles(g)
    assert expansion == {}
    assert len(list(reduit.edges())) == 2


def test_broche_active_jamais_eliminee():
    # MID est la broche IN- d'un AOP → protégée ; pas de fusion série à travers elle
    g = _graphe(
        Composant('U1', 'U', {'IN+': 'P', 'IN-': 'MID', 'OUT': 'OUT'}),
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '10k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'OUT'}, '10k'),
    )
    reduit, expansion = reduire_dipoles(g)
    assert expansion == {}
    assert len(list(reduit.edges())) == 2


# ── expandre_composites ────────────────────────────────────────────────────────

def test_expandre_preserve_ordre():
    match = {'components': ['U1', 'Z#1', 'Rin'], 'nodes': []}
    expansion = {'Z#1': ['R1', 'R2']}
    out = expandre_composites(match, expansion)
    assert out['components'] == ['U1', 'R1', 'R2', 'Rin']
    # match d'origine non muté
    assert match['components'] == ['U1', 'Z#1', 'Rin']


def test_expandre_sans_expansion_retourne_match():
    match = {'components': ['U1', 'R1'], 'nodes': []}
    assert expandre_composites(match, {}) is match
