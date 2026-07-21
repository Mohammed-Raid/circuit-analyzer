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
