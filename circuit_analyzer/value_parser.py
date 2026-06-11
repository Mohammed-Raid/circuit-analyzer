"""
value_parser.py — Parse les valeurs électriques des composants.

Comprend :
  Résistances : 0R, 10R, 10Ω, 1k, 4.7k, 1M, 0.01R, 4K7 (notation EIA)
  Condensateurs : 100n, 100nF, 1uF, 10µF, 470u, 1mF
  Inductances : 10uH, 1mH

Ne crash jamais sur une valeur absente ou invalide (retourne None).
"""
import re

# Multiplicateurs SI
_MULT: dict[str, float] = {
    'p': 1e-12, 'n': 1e-9,
    'u': 1e-6,  'µ': 1e-6,  'μ': 1e-6,
    'm': 1e-3,
    'k': 1e3,   'K': 1e3,
    'M': 1e6,
    'G': 1e9,
}


def parse_valeur(valeur: str) -> float | None:
    """
    Parse une valeur électrique et retourne un float en unité SI de base.
    Retourne None si la valeur est absente, vide ou invalide.

    Exemples :
        '10k'    → 10000.0
        '100nF'  → 1e-7
        '4.7k'   → 4700.0
        '0R'     → 0.0       (jumper)
        '4K7'    → 4700.0    (notation EIA)
        '2M2'    → 2200000.0 (notation EIA)
    """
    if not valeur or not str(valeur).strip():
        return None

    v = str(valeur).strip()

    # Enlever les unités de fin : F (farad), H (henry), ohm, Ω
    v = re.sub(r'(?i)(ohm|[FH])$', '', v).strip()
    v = v.replace('Ω', 'R').replace('Ω', 'R')

    # Notation EIA : "4R7" → 4.7, "4K7" → 4700, "2M2" → 2200000
    for separateur, mult in [('R', 1.0), ('K', 1e3), ('M', 1e6), ('N', 1e-9), ('U', 1e-6)]:
        m = re.match(r'^(\d+)' + separateur + r'(\d+)$', v, re.IGNORECASE)
        if m:
            return float(f'{m.group(1)}.{m.group(2)}') * mult

    # Enlever le suffixe R/Ω (unité résistance sans multiplicateur)
    v_clean = re.sub(r'[Rr]$', '', v).strip()

    # Format standard : "10k", "4.7k", "100n", "1M", "10", "0.01"
    m = re.match(r'^([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)\s*([pnuµμmkKMG]?)$', v_clean)
    if m:
        try:
            nombre = float(m.group(1))
            mult = _MULT.get(m.group(2), 1.0)
            return nombre * mult
        except (ValueError, OverflowError):
            return None

    # Dernier recours : essai direct
    try:
        return float(v_clean)
    except (ValueError, TypeError):
        return None


def classifier_resistance(valeur: str) -> str:
    """
    Classifie une résistance selon sa valeur.

    Retours :
        'jumper'   — 0Ω, pont direct
        'shunt'    — < 1Ω, mesure de courant
        'standard' — valeur normale
        'pull'     — ≥ 10kΩ, pull-up/pull-down typique
        'unknown'  — valeur absente ou invalide
    """
    v = parse_valeur(valeur)
    if v is None:
        return 'unknown'
    if v == 0.0:
        return 'jumper'
    if v < 1.0:
        return 'shunt'
    if v >= 10_000:
        return 'pull'
    return 'standard'


def classifier_condensateur(valeur: str, entre_power_gnd: bool = False) -> str:
    """
    Classifie un condensateur selon sa valeur et son emplacement.

    Retours :
        'decoupling'   — ≤ 1µF entre alim/GND (découplage HF)
        'bulk_filter'  — > 1µF entre alim/GND (filtrage alimentation)
        'standard'     — emplacement non significatif
        'unknown'      — valeur absente ou invalide
    """
    v = parse_valeur(valeur)
    if v is None:
        return 'unknown'
    if entre_power_gnd:
        if v <= 1e-6:
            return 'decoupling'
        return 'bulk_filter'
    return 'standard'
