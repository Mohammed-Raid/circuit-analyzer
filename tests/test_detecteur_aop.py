"""@file test_detecteur_aop.py
@brief Tests d'enrichissement des montages AOP (impedances structurees + gain)."""
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer import detecteur


def _ampli_inverseur_zf_composite():
    # AOP U1 ; entree IN -Rin- INM ; contre-reaction INM -R1- X -R2- OUT (Zf=R1+R2).
    return construire_graphe([
        Composant("U1", "U", {"IN+": "GND", "IN-": "INM", "OUT": "OUT"}),
        Composant("Rin", "R", {"1": "IN", "2": "INM"}, "1k"),
        Composant("R1", "R", {"1": "INM", "2": "X"}, "2k"),
        Composant("R2", "R", {"1": "X", "2": "OUT"}, "3k"),
    ])


def test_inverseur_expose_impedances_et_gain():
    res = detecteur.analyser(_ampli_inverseur_zf_composite())
    inv = [r for r in res if r["circuit_type"] == "Amplificateur inverseur (AOP)"]
    assert len(inv) == 1
    m = inv[0]
    assert m["gain"] == "−Zf/Zin"
    assert set(m["impedances"]["Zf"]["refs"]) == {"R1", "R2"}
    assert "+" in m["impedances"]["Zf"]["composition"]      # Zf composite
    assert m["impedances"]["Zin"]["refs"] == ["Rin"]
    assert m["impedances"]["Zf"]["nodes"] == ("INM", "OUT")
