"""@file test_catalogue.py
@brief Identification des références constructeur (catalogue déclaratif)."""
import pytest

from circuit_analyzer import catalogue


@pytest.mark.parametrize("valeur,categorie", [
    ("NE555", "Timer"), ("ne 555", "Timer"),           # normalisation
    ("LM393", "Comparateur double"), ("LM339", "Comparateur quadruple"),
    ("PC817", "Optocoupleur"),
    ("74HC00", "Porte NAND x4"), ("74HCT00", "Porte NAND x4"),   # famille
    ("74HC04N", "Inverseur x6"),                        # suffixe boîtier
    ("74HC08", "Porte AND x4"), ("74HC32", "Porte OR x4"),
    ("74HC74", "Bascule D x2"), ("74HC157", "Multiplexeur 2:1 x4"),
    ("74HC138", "Demultiplexeur 3:8"),
    ("LM741", "AOP"), ("UA741", "AOP"),                 # suffixe libre
    ("MC1458", "AOP double"), ("LM1458", "AOP double"),
    ("7805", "Regulateur +5 V"), ("LM7805", "Regulateur +5 V"),
    ("7812", "Regulateur +12 V"), ("LM317", "Regulateur ajustable"),
    ("74HC125", "Logique 74HC"),                        # repli famille
])
def test_identifier_u(valeur, categorie):
    e = catalogue.identifier("U", valeur)
    assert e is not None and e["categorie"] == categorie


@pytest.mark.parametrize("valeur,categorie", [
    ("2N2222", "Transistor NPN"), ("BC547", "Transistor NPN"),
    ("2N3904", "Transistor NPN"),
])
def test_identifier_q(valeur, categorie):
    assert catalogue.identifier("Q", valeur)["categorie"] == categorie


@pytest.mark.parametrize("valeur", ["IRFZ44N", "BS170", "IRLZ44N"])
def test_identifier_m(valeur):
    assert catalogue.identifier("M", valeur)["categorie"] == "MOSFET canal N"


@pytest.mark.parametrize("valeur,couleur", [
    ("LED rouge", "red"), ("rouge", "red"),
    ("LED verte", "green"), ("LED bleue", "blue"),
])
def test_identifier_led(valeur, couleur):
    e = catalogue.identifier("D", valeur)
    assert e["categorie"] == "LED" and e["couleur"] == couleur


def test_identifier_inconnu_et_type_non_concerne():
    assert catalogue.identifier("U", "") is None
    assert catalogue.identifier("U", "XYZ999") is None
    assert catalogue.identifier("R", "10k") is None
    # une LED n'est identifiée QUE sur le type D :
    assert catalogue.identifier("U", "rouge") is None


def test_broches_et_alias():
    e555 = catalogue.identifier("U", "NE555")
    assert e555["broches"]["2"] == "TRIG" and e555["broches"]["8"] == "VCC"
    assert e555["alias"] is False
    e741 = catalogue.identifier("U", "LM741")
    assert e741["broches"]["2"] == "IN-" and e741["broches"]["6"] == "OUT"
    assert e741["alias"] is True                       # mono-unité -> AOP existant
    e7805 = catalogue.identifier("U", "7805")
    assert e7805["broches"] == {"1": "IN", "2": "GND", "3": "OUT"}
    assert e7805["alias"] is True
    e458 = catalogue.identifier("U", "MC1458")
    assert e458["alias"] is False                      # multi-unité : jamais aliasé
    assert catalogue.identifier("Q", "2N2222")["broches"] is None
