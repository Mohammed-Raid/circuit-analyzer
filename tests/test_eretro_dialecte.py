import pytest

from circuit_analyzer.eretro import decoder_valeur_resistance, mapper_nom


@pytest.mark.parametrize("nom, attendu", [
    ("R 810", "81"), ("R810", "81"),
    ("R 561", "560"), ("R 332", "3.3k"), ("R332", "3.3k"),
    ("R 1001", "1k"), ("R2001", "2k"), ("R 3903", "390k"),
    ("R5101", "5.1k"), ("R512", "5.1k"),
    ("R300", "30"), ("R2400", "240"), ("R 3300", "330"),
    ("R 3R90", "3.9"), ("R 60R4", "60.4"), ("R 47R0", "47"),
    ("RINF", "open"),
    ("R 308", "308"), ("R 30A", "30A"),   # indécodables/aberrants -> code brut
    # Nom GÉNÉRIQUE (pas un code) : rien, pas un libellé abîmé « ésistance ».
    ("Résistance", ""), ("Resistance", ""), ("R", ""),
])
def test_decoder_valeur_resistance(nom, attendu):
    assert decoder_valeur_resistance(nom) == attendu


@pytest.mark.parametrize("nom, type_attendu", [
    ("Transistor_NPN", "Q"),          # underscore : mappe via 'transistor npn'
    ("Condensateur_polarise", "C"),
    ("Photodiode", "D"),
    ("R 810", "R"), ("R810", "R"), ("RINF", "R"), ("R 30A", "R"),
    ("open connecter", "J"), ("JUMPER", "J"), ("jumper 2 broches", "J"),
    ("connecteur traversant", "J"), ("Borne", "J"),
])
def test_mapper_nom_dialecte_reel(nom, type_attendu):
    corr = mapper_nom(nom)
    assert corr is not None and corr[0] == type_attendu


@pytest.mark.parametrize("nom", ["RELAIS 2RT", "reset", "resistance trad"])
def test_mapper_nom_pas_de_faux_positif_r(nom):
    # 'RELAIS 2RT' -> K (exact), 'reset' -> None, 'resistance trad' -> R (exact) :
    # la règle R-code ne doit JAMAIS transformer ces noms en R via le préfixe.
    corr = mapper_nom(nom)
    if nom == "reset":
        assert corr is None
    elif nom == "RELAIS 2RT":
        assert corr[0] == "K"
    else:
        assert corr[0] == "R"


# ── Task 3 : valeur R-code + catch-all IC + marqueur boîte + 78L05 ───────────

from circuit_analyzer.composant import Composant


def test_composant_boite_ic_defaut_false():
    assert Composant(ref="U1", type="U", pins={}).boite_ic is False


def test_ic_nommee_multibroches_devient_boite_ic():
    # helpers _item/_pin/_boardsch/_lire réutilisés depuis test_eretro.
    from tests.test_eretro import _boardsch, _item, _lire, _pin
    # Reference VOLONTAIREMENT fictive : ce test porte sur le catch-all des
    # puces INCONNUES. Une vraie reference finit tot ou tard au catalogue
    # (c'est arrive a 'SI844AB'), ce qui invaliderait la premisse en silence.
    pins = [_pin(refs=[f'n{i}']) for i in range(8)]
    item = _item('XYZ4321K', pins=pins)         # nom inconnu, 8 broches, pas de forme franche
    comps = _lire(_boardsch([item], []))
    c = comps[0]
    assert c.type == 'U' and c.boite_ic is True and c.value == 'XYZ4321K'


def test_rcode_porte_sa_valeur_decodee():
    from tests.test_eretro import _boardsch, _item, _lire, _pin
    item = _item('R 1001', pins=[_pin(refs=['a']), _pin(refs=['b'])])
    comps = _lire(_boardsch([item], []))
    c = comps[0]
    assert c.type == 'R' and c.value == '1k'


# ── Task 6 : le n° de pièce survit dans value jusqu'au rendu ─────────────────

def test_78L05_garde_son_identite_de_piece():
    from circuit_analyzer.catalogue import identifier
    from tests.test_eretro import _boardsch, _item, _lire, _pin
    pins = [_pin(refs=[f'n{i}']) for i in range(3)]
    item = _item('78L05CP', pins=pins)          # nom = n° de pièce, value XML vide
    comps = _lire(_boardsch([item], []))
    c = comps[0]
    assert c.type == 'U'
    # le n° de pièce survit dans value -> identifiable au rendu comme régulateur
    assert c.value == '78L05CP'
    assert identifier('U', c.value)['categorie'] == 'Regulateur +5 V'


@pytest.mark.parametrize("nom", [
    "NOT", "OR", "AND", "NAND", "NOR", "XOR", "XNOR", "BUFFER",
    "not", "Or",                       # casse indifferente
])
def test_portes_logiques_de_la_bibliotheque_sont_typees(nom):
    """La bibliotheque ERetroDesign livre NOT.xml et OR.xml : ces portes
    tombaient en boite noire X faute d'entree dans le dialecte. Elles doivent
    etre typees 'U' (boite CI honnete), comme Gate2 l'est deja."""
    from circuit_analyzer.eretro import mapper_nom
    resultat = mapper_nom(nom)
    assert resultat is not None, f"« {nom} » non reconnu"
    assert resultat[0] == "U"
