import pytest
from circuit_analyzer.eretro import decoder_valeur_resistance


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
