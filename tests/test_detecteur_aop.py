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


def _integrateur():
    # AOP U1 ; entree VIN -Re- M(IN-) ; contre-reaction M -Cf- O(OUT).
    return construire_graphe([
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "O"}),
        Composant("Re", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Cf", "C", {"1": "M", "2": "O"}, "100n"),
    ])


def test_integrateur_expose_impedances_et_gain():
    res = detecteur.analyser(_integrateur())
    integ = [r for r in res if r["circuit_type"] == "Intégrateur (AOP)"]
    assert len(integ) == 1
    m = integ[0]
    assert m["gain"] == "−Zf/Zin"
    assert m["impedances"]["Zf"]["refs"] == ["Cf"]          # condensateur de contre-réaction
    assert m["impedances"]["Zin"]["refs"] == ["Re"]
    assert m["impedances"]["Zf"]["nodes"] == ("M", "O")


def test_integrateur_reel_leaky_rf_parallele_cf():
    # Intégrateur réel : Zf = Rf // Cf (résistance en parallèle du condensateur).
    g = construire_graphe([
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "O"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Rf", "R", {"1": "M", "2": "O"}, "1M"),
        Composant("Cf", "C", {"1": "M", "2": "O"}, "10n"),
    ])
    res = detecteur.analyser(g)
    integ = [r for r in res if r["circuit_type"] == "Intégrateur (AOP)"]
    assert len(integ) == 1, [r["circuit_type"] for r in res]
    assert set(integ[0]["impedances"]["Zf"]["refs"]) == {"Rf", "Cf"}


def test_feedback_resonant_lc_reste_inverseur():
    # Zf = (L+C)//R : feedback résonant, PAS un intégrateur -> ampli inverseur.
    g = construire_graphe([
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "O"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Lf", "L", {"1": "M", "2": "X"}, "1m"),
        Composant("Cf", "C", {"1": "X", "2": "O"}, "10n"),
        Composant("Rf", "R", {"1": "M", "2": "O"}, "100k"),
    ])
    res = detecteur.analyser(g)
    types = [r["circuit_type"] for r in res]
    assert "Intégrateur (AOP)" not in types
    assert "Amplificateur inverseur (AOP)" in types


def _derivateur():
    # AOP U1 ; entree VIN -Ce- M(IN-) ; contre-reaction M -Rf- O(OUT).
    return construire_graphe([
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "O"}),
        Composant("Ce", "C", {"1": "VIN", "2": "M"}, "100n"),
        Composant("Rf", "R", {"1": "M", "2": "O"}, "10k"),
    ])


def test_derivateur_expose_impedances_et_gain():
    res = detecteur.analyser(_derivateur())
    deriv = [r for r in res if r["circuit_type"] == "Dérivateur (AOP)"]
    assert len(deriv) == 1
    m = deriv[0]
    assert m["gain"] == "−Zf/Zin"
    assert m["impedances"]["Zin"]["refs"] == ["Ce"]          # condensateur d'entrée
    assert m["impedances"]["Zf"]["refs"] == ["Rf"]
    assert m["impedances"]["Zin"]["nodes"] == ("M", "VIN")


def test_derivateur_reel_rin_serie_cin():
    # Dérivateur réel : Zin = Rin + Cin (résistance en série du condensateur d'entrée).
    g = construire_graphe([
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "O"}),
        Composant("Rin", "R", {"1": "VIN", "2": "X"}, "1k"),
        Composant("Cin", "C", {"1": "X", "2": "M"}, "100n"),
        Composant("Rf", "R", {"1": "M", "2": "O"}, "10k"),
    ])
    res = detecteur.analyser(g)
    deriv = [r for r in res if r["circuit_type"] == "Dérivateur (AOP)"]
    assert len(deriv) == 1, [r["circuit_type"] for r in res]
    assert set(deriv[0]["impedances"]["Zin"]["refs"]) == {"Rin", "Cin"}
    assert "+" in deriv[0]["impedances"]["Zin"]["composition"]   # Zin série composite


def _non_inverseur():
    # AOP U1 ; signal sur IN+ ; pont Zf/Zg sur IN- : Rf (IN-→OUT), Rg (IN-→GND).
    return construire_graphe([
        Composant("U1", "U", {"IN+": "VIN", "IN-": "M", "OUT": "O"}),
        Composant("Rf", "R", {"1": "M", "2": "O"}, "10k"),
        Composant("Rg", "R", {"1": "M", "2": "GND"}, "1k"),
    ])


def test_non_inverseur_expose_impedances_et_gain():
    res = detecteur.analyser(_non_inverseur())
    ni = [r for r in res if r["circuit_type"] == "Amplificateur non-inverseur (AOP)"]
    assert len(ni) == 1
    m = ni[0]
    assert m["gain"] == "1 + Zf/Zg"
    assert m["impedances"]["Zf"]["refs"] == ["Rf"]          # contre-réaction
    assert m["impedances"]["Zg"]["refs"] == ["Rg"]          # vers la masse
    assert m["impedances"]["Zf"]["nodes"] == ("M", "O")


def test_non_inverseur_zf_composite():
    # Zf = R1 + R2 (série) dans la contre-réaction.
    g = construire_graphe([
        Composant("U1", "U", {"IN+": "VIN", "IN-": "M", "OUT": "O"}),
        Composant("R1", "R", {"1": "M", "2": "X"}, "4k"),
        Composant("R2", "R", {"1": "X", "2": "O"}, "6k"),
        Composant("Rg", "R", {"1": "M", "2": "GND"}, "1k"),
    ])
    res = detecteur.analyser(g)
    ni = [r for r in res if r["circuit_type"] == "Amplificateur non-inverseur (AOP)"]
    assert len(ni) == 1, [r["circuit_type"] for r in res]
    assert set(ni[0]["impedances"]["Zf"]["refs"]) == {"R1", "R2"}
    assert "+" in ni[0]["impedances"]["Zf"]["composition"]


def test_gain_non_inverseur_resistif():
    from circuit_analyzer import impedance
    g = _non_inverseur()
    # Av = 1 + Zf/Zg = 1 + 10k/1k = 11
    assert impedance.gain_non_inverseur(g, "Rf", "Rg") == "11"


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


def _differentiel():
    # IN1 -R1- INM -Rf- OUT ; IN2 -R3- INP -Rg- GND
    return construire_graphe([
        Composant("U1", "U", {"IN+": "INP", "IN-": "INM", "OUT": "OUT"}),
        Composant("R1", "R", {"1": "IN1", "2": "INM"}, "10k"),
        Composant("Rf", "R", {"1": "INM", "2": "OUT"}, "100k"),
        Composant("R3", "R", {"1": "IN2", "2": "INP"}, "10k"),
        Composant("Rg", "R", {"1": "INP", "2": "GND"}, "100k"),
    ])


def test_differentiel_expose_quatre_impedances():
    res = detecteur.analyser(_differentiel())
    m = [r for r in res if r["circuit_type"] == "Amplificateur différentiel (AOP)"]
    assert len(m) == 1
    imp = m[0]["impedances"]
    assert imp["Z1"]["refs"] == ["R1"]
    assert imp["Zf"]["refs"] == ["Rf"]
    assert imp["Z3"]["refs"] == ["R3"]
    assert imp["Zg"]["refs"] == ["Rg"]
    assert m[0]["gain"] == "Zf/Z1 · (V2−V1)"
