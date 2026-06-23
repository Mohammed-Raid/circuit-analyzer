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


def test_pont_wheatstone_irreductible_en_bloc():
    # Pont en H : A,B,C,D avec une diagonale R5 entre C et D. Aucun nœud
    # interne de degré 2, aucun banc parallèle → série/parallèle impuissant.
    # On signale le bloc passif comme une Z unique listant tous ses composants.
    g = _graphe(
        Composant('U1', 'U', {'IN+': 'A', 'IN-': 'X', 'OUT': 'B'}),  # ancre A,B
        Composant('R1', 'R', {'1': 'A', '2': 'C'}, '1k'),
        Composant('R2', 'R', {'1': 'A', '2': 'D'}, '1k'),
        Composant('R3', 'R', {'1': 'C', '2': 'B'}, '1k'),
        Composant('R4', 'R', {'1': 'D', '2': 'B'}, '1k'),
        Composant('R5', 'R', {'1': 'C', '2': 'D'}, '1k'),
    )
    reduit = impedance.reduire(g)
    zs = [d for _, _, d in reduit.edges(data=True) if str(d['ref']).startswith('Z')]
    assert len(zs) == 1
    z = zs[0]
    assert sorted(z['refs']) == ['R1', 'R2', 'R3', 'R4', 'R5']
    assert z['type'] == 'Z'
    assert z['composition'].startswith('pont{')
    # Les nœuds internes C et D du pont ont disparu (absorbés dans le bloc).
    assert 'C' not in reduit.nodes() and 'D' not in reduit.nodes()
    # L'arête Z du bloc relie bien les deux bornes A et B.
    u, v = next((u, v) for u, v, d in reduit.edges(data=True)
                if str(d['ref']).startswith('Z'))
    assert {u, v} == {'A', 'B'}


def test_fusible_transparent():
    # VIN ─F1─ N ─R1─ OUT : le fusible est transparent (ses deux nœuds
    # fusionnent). Il ne reste QUE R1, entre VIN et OUT. Aucune arête 'F'.
    g = _graphe(
        Composant('F1', 'F', {'1': 'VIN', '2': 'N'}),
        Composant('R1', 'R', {'1': 'N', '2': 'OUT'}, '1k'),
    )
    reduit = impedance.reduire(g)
    types = sorted(d['type'] for _, _, d in reduit.edges(data=True))
    assert types == ['R']  # plus aucune arête 'F'
    r1 = next(d for _, _, d in reduit.edges(data=True) if d['ref'] == 'R1')
    bornes = {u for u, _, d in reduit.edges(data=True) if d['ref'] == 'R1'}
    bornes |= {v for _, v, d in reduit.edges(data=True) if d['ref'] == 'R1'}
    assert bornes == {'VIN', 'OUT'}  # N a été absorbé dans VIN


def test_milieu_relie_a_aop_non_fusionne():
    # Pont diviseur VCC ─R1─ MID ─R2─ GND, mais MID alimente IN- d'un AOP.
    # MID est une broche active → borne → NON éliminé : R1 et R2 restent
    # deux singletons distincts (l'AOP les verra séparément au sous-projet 2).
    g = _graphe(
        Composant('U1', 'U', {'IN+': 'P', 'IN-': 'MID', 'OUT': 'O'}),
        Composant('R1', 'R', {'1': 'VCC', '2': 'MID'}, '10k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'GND'}, '10k'),
    )
    reduit = impedance.reduire(g)
    refs = sorted(d['ref'] for _, _, d in reduit.edges(data=True))
    assert refs == ['R1', 'R2']  # pas de Z1, MID préservé
    assert 'MID' in reduit.nodes()


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


def test_fusible_ne_mute_pas_les_composants_origine():
    # Le passage des fusibles en transparent ne doit PAS muter les Composant
    # d'origine (partagés par référence avec l'appelant).
    r1 = Composant('R1', 'R', {'1': 'N', '2': 'OUT'}, '1k')
    g = _graphe(
        Composant('F1', 'F', {'1': 'VIN', '2': 'N'}),
        r1,
    )
    impedance.reduire(g)
    # Les broches du R1 d'origine restent inchangées (N non fusionné en VIN).
    assert r1.pins == {'1': 'N', '2': 'OUT'}


def test_pont_trois_bornes_non_replie():
    # Étoile R1(A-X), R2(B-X), R3(C-X) où A, B, C sont des broches d'un composant
    # actif (donc des bornes) et X est interne. Le bloc touche 3 bornes : il ne
    # doit PAS être replié (sinon perte de connectivité). Les trois R restent
    # des singletons, aucune arête Z n'est créée.
    g = _graphe(
        Composant('U1', 'U', {'IN+': 'A', 'IN-': 'B', 'OUT': 'C'}),
        Composant('R1', 'R', {'1': 'A', '2': 'X'}, '1k'),
        Composant('R2', 'R', {'1': 'B', '2': 'X'}, '1k'),
        Composant('R3', 'R', {'1': 'C', '2': 'X'}, '1k'),
    )
    reduit = impedance.reduire(g)
    refs = sorted(d['ref'] for _, _, d in reduit.edges(data=True))
    assert refs == ['R1', 'R2', 'R3']
    assert not any(str(d['ref']).startswith('Z') for _, _, d in reduit.edges(data=True))


# ── impedance_equivalente : reduction complete d'un reseau 2-bornes ───────────

def test_impedance_equivalente_serie_parallele():
    # A ─R1─ M ─R2─ B  avec C1 entre A et B : (R1+R2)//C1.
    g = _graphe(
        Composant('R1', 'R', {'1': 'A', '2': 'M'}, '1k'),
        Composant('R2', 'R', {'1': 'M', '2': 'B'}, '2k'),
        Composant('C1', 'C', {'1': 'A', '2': 'B'}, '1u'),
    )
    assert impedance.impedance_equivalente(g, 'A', 'B') == '((R1+R2)//C1)'


def test_impedance_equivalente_pont_wheatstone_via_etoile_triangle():
    # Pont de Wheatstone pur : serie/parallele seuls echouent -> Y-D le casse
    # et le reduit a UNE impedance equivalente entre A et B.
    g = _graphe(
        Composant('R1', 'R', {'1': 'A', '2': 'C'}, '1k'),
        Composant('R2', 'R', {'1': 'A', '2': 'D'}, '1k'),
        Composant('R3', 'R', {'1': 'C', '2': 'B'}, '1k'),
        Composant('R4', 'R', {'1': 'D', '2': 'B'}, '1k'),
        Composant('R5', 'R', {'1': 'C', '2': 'D'}, '1k'),
    )

    expr = impedance.impedance_equivalente(g, 'A', 'B')

    assert expr is not None                       # entierement reductible
    assert '*' in expr and '/' in expr            # une transformation Y-D a eu lieu
    for r in ['R1', 'R2', 'R3', 'R4', 'R5']:
        assert r in expr                          # les 5 impedances sont presentes


def test_formater_expr_nettoie_parentheses_et_produit():
    assert impedance.formater_expr("(R1)*(R2)/((R1)+(R2)+(R5))") == "R1·R2/(R1+R2+R5)"
    assert impedance.formater_expr("R1+R2") == "R1+R2"
    assert impedance.formater_expr("(R1//C1)") == "(R1//C1)"   # parentheses utiles gardees
    assert impedance.formater_expr("") == ""


def test_bornes_possibles_ignore_les_non_impedances():
    g = _graphe(
        Composant('U1', 'U', {'IN+': 'A', 'IN-': 'X', 'OUT': 'B'}),  # actif : ignore
        Composant('R1', 'R', {'1': 'A', '2': 'M'}, '1k'),
        Composant('R2', 'R', {'1': 'M', '2': 'B'}, '1k'),
    )
    assert impedance.bornes_possibles(g) == ['A', 'B', 'M']  # X (broche AOP) exclu


def test_expansion_depuis_graphe_et_expandre():
    # Chaîne série R1+R2 → Z1 ; l'expansion mappe Z1 -> [R1, R2].
    g = _graphe(
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '1k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'OUT'}, '2k'),
    )
    reduit = impedance.reduire(g)
    exp = impedance.expansion_depuis_graphe(reduit)
    assert exp == {'Z1': ['R1', 'R2']}
    # expandre_composites remplace la ref synthétique par les vraies refs.
    match = {'circuit_type': 'X', 'components': ['Z1'], 'nodes': ['IN', 'OUT']}
    out = impedance.expandre_composites(match, exp)
    assert out['components'] == ['R1', 'R2']
    # match d'origine non muté
    assert match['components'] == ['Z1']
    # sans expansion (singleton), la ref passe telle quelle
    assert impedance.expandre_composites({'components': ['R5']}, {})['components'] == ['R5']


# ── evaluation numerique : valeur ingenieur + Z complexe a une frequence ──────

def test_parse_valeur_prefixes_ingenieur():
    assert impedance._parse_valeur('470') == 470.0
    assert impedance._parse_valeur('10k') == 10_000.0
    assert abs(impedance._parse_valeur('100n') - 100e-9) < 1e-18
    assert abs(impedance._parse_valeur('1m') - 1e-3) < 1e-15
    assert abs(impedance._parse_valeur('2.2u') - 2.2e-6) < 1e-15
    assert impedance._parse_valeur('1M') == 1e6        # mega, pas milli
    assert abs(impedance._parse_valeur('100nF') - 100e-9) < 1e-18  # unite finale ignoree


def test_evaluer_impedance_resistances_serie_reelle():
    # R1+R2 = 1k + 2k = 3000 ohm, purement reel (independant de f).
    g = _graphe(
        Composant('R1', 'R', {'1': 'A', '2': 'M'}, '1k'),
        Composant('R2', 'R', {'1': 'M', '2': 'B'}, '2k'),
    )
    z = impedance.evaluer_impedance(g, 'R1+R2', 1000)
    assert abs(z - complex(3000, 0)) < 1e-6


def test_evaluer_impedance_parallele_resistances():
    # R1//R2 = 1k // 1k = 500 ohm.
    g = _graphe(
        Composant('R1', 'R', {'1': 'A', '2': 'B'}, '1k'),
        Composant('R2', 'R', {'1': 'A', '2': 'B'}, '1k'),
    )
    z = impedance.evaluer_impedance(g, '(R1//R2)', 1000)
    assert abs(z - complex(500, 0)) < 1e-6


def test_evaluer_impedance_condensateur_reactance_negative():
    # C seul : Z = -j/(wC). C=1uF, f=1000Hz -> w=2pi*1000, |Z|~159.15 ohm, reel~0.
    import math
    g = _graphe(Composant('C1', 'C', {'1': 'A', '2': 'B'}, '1u'))
    z = impedance.evaluer_impedance(g, 'C1', 1000)
    attendu = -1.0 / (2 * math.pi * 1000 * 1e-6)
    assert abs(z.real) < 1e-6
    assert abs(z.imag - attendu) < 1e-3


def test_evaluer_impedance_bobine_reactance_positive():
    # L seule : Z = jwL. L=1mH, f=1000Hz -> +j*2pi*1000*1e-3 ~ +6.283j.
    import math
    g = _graphe(Composant('L1', 'L', {'1': 'A', '2': 'B'}, '1m'))
    z = impedance.evaluer_impedance(g, 'L1', 1000)
    assert abs(z.real) < 1e-6
    assert abs(z.imag - 2 * math.pi * 1000 * 1e-3) < 1e-6


def test_evaluer_impedance_valeur_manquante_leve():
    g = _graphe(Composant('R1', 'R', {'1': 'A', '2': 'B'}, ''))
    try:
        impedance.evaluer_impedance(g, 'R1', 1000)
        assert False, "devrait lever ValueError sur valeur vide"
    except ValueError:
        pass


# ── arbre_expr : expression de composition -> arbre serie/parallele ───────────

def test_arbre_expr_serie_simple():
    assert impedance.arbre_expr("R1+R2") == (
        "serie", [("feuille", "R1"), ("feuille", "R2")])


def test_arbre_expr_serie_aplatie():
    # R1+R2+R3 (associatif) -> un seul noeud serie a 3 enfants.
    assert impedance.arbre_expr("R1+R2+R3") == (
        "serie", [("feuille", "R1"), ("feuille", "R2"), ("feuille", "R3")])


def test_arbre_expr_parallele_de_serie():
    assert impedance.arbre_expr("(R1+R2)//R3") == (
        "parallele", [("serie", [("feuille", "R1"), ("feuille", "R2")]),
                      ("feuille", "R3")])


def test_arbre_expr_feuille_seule():
    assert impedance.arbre_expr("R1") == ("feuille", "R1")


def test_arbre_expr_pont_non_serie_parallele():
    # Une expression Y-D contient * et / -> pas de forme serie/parallele.
    assert impedance.arbre_expr("(R1)*(R2)/((R1)+(R2)+(R5))") is None


# ── detecter_pont : motif pont de Wheatstone (4 noeuds / 5 aretes) ────────────

def test_detecter_pont_wheatstone():
    g = _graphe(
        Composant("R1", "R", {"1": "VIN", "2": "NET1"}, "1k"),
        Composant("R2", "R", {"1": "VIN", "2": "NET2"}, "1k"),
        Composant("R3", "R", {"1": "NET1", "2": "VOUT"}, "1k"),
        Composant("R4", "R", {"1": "NET2", "2": "VOUT"}, "1k"),
        Composant("R5", "R", {"1": "NET1", "2": "NET2"}, "1k"),
    )
    pont = impedance.detecter_pont(g, "VIN", "VOUT")
    assert pont is not None
    assert pont["haut"] == "VIN" and pont["bas"] == "VOUT"
    assert pont["gauche"] == "NET1"
    bras = pont["bras"]
    assert bras["haut_gauche"] == {"refs": ["R1"], "composition": "R1"}
    assert bras["haut_droite"] == {"refs": ["R2"], "composition": "R2"}
    assert bras["bas_gauche"] == {"refs": ["R3"], "composition": "R3"}
    assert bras["bas_droite"] == {"refs": ["R4"], "composition": "R4"}
    assert bras["pont"] == {"refs": ["R5"], "composition": "R5"}


def test_detecter_pont_bras_composite():
    # Bras VIN-NET1 = R1+R6 (X interne degre 2 collapse en serie).
    g = _graphe(
        Composant("R1", "R", {"1": "VIN", "2": "X"}, "1k"),
        Composant("R6", "R", {"1": "X", "2": "NET1"}, "1k"),
        Composant("R2", "R", {"1": "VIN", "2": "NET2"}, "1k"),
        Composant("R3", "R", {"1": "NET1", "2": "VOUT"}, "1k"),
        Composant("R4", "R", {"1": "NET2", "2": "VOUT"}, "1k"),
        Composant("R5", "R", {"1": "NET1", "2": "NET2"}, "1k"),
    )
    pont = impedance.detecter_pont(g, "VIN", "VOUT")
    assert pont is not None
    hg = pont["bras"]["haut_gauche"]      # VIN-NET1 = bras composite
    assert set(hg["refs"]) == {"R1", "R6"}
    assert "+" in hg["composition"]


def test_detecter_pont_serie_parallele_renvoie_none():
    g = _graphe(
        Composant("R1", "R", {"1": "VIN", "2": "M"}, "1k"),
        Composant("R2", "R", {"1": "M", "2": "VOUT"}, "1k"),
        Composant("R3", "R", {"1": "VIN", "2": "VOUT"}, "1k"),
    )
    assert impedance.detecter_pont(g, "VIN", "VOUT") is None


def test_detecter_pont_triangle_renvoie_none():
    # 3 noeuds seulement -> pas un pont.
    g = _graphe(
        Composant("R1", "R", {"1": "VIN", "2": "VOUT"}, "1k"),
        Composant("R2", "R", {"1": "VOUT", "2": "N"}, "1k"),
        Composant("R3", "R", {"1": "N", "2": "VIN"}, "1k"),
    )
    assert impedance.detecter_pont(g, "VIN", "VOUT") is None


def test_formater_valeur_avec_unite():
    assert impedance.formater_valeur("10k", "R") == "10 kΩ"
    assert impedance.formater_valeur("100n", "C") == "100 nF"
    assert impedance.formater_valeur("1m", "L") == "1 mH"
    assert impedance.formater_valeur("470", "R") == "470 Ω"
    assert impedance.formater_valeur("", "R") == ""
    assert impedance.formater_valeur("abc", "R") == "abc"  # non interpretable -> tel quel


def test_gain_inverseur_resistif_est_un_reel_negatif():
    g = construire_graphe([
        Composant("Rin", "R", {"1": "A", "2": "B"}, "1k"),
        Composant("R1", "R", {"1": "B", "2": "C"}, "10k"),
        Composant("R2", "R", {"1": "C", "2": "D"}, "10k"),
    ])
    # Zf = R1+R2 = 20k ; Zin = Rin = 1k ; Av = -20
    s = impedance.gain_inverseur(g, "Rin", "R1+R2")
    assert s == "-20"


def test_gain_inverseur_reactif_donne_module_a_la_frequence():
    g = construire_graphe([
        Composant("Rin", "R", {"1": "A", "2": "B"}, "1k"),
        Composant("Rf", "R", {"1": "B", "2": "C"}, "10k"),
        Composant("Cf", "C", {"1": "B", "2": "C"}, "10n"),
    ])
    s = impedance.gain_inverseur(g, "Rin", "Rf//Cf", f=1000.0)
    assert s.startswith("|Av|")
    assert "1000 Hz" in s


def test_gain_inverseur_valeur_manquante_renvoie_none():
    g = construire_graphe([
        Composant("Rin", "R", {"1": "A", "2": "B"}, ""),   # pas de valeur
        Composant("Rf", "R", {"1": "B", "2": "C"}, "10k"),
    ])
    assert impedance.gain_inverseur(g, "Rin", "Rf") is None
