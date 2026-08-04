"""
@file generate_test_circuits.py
@brief Génère les fichiers XML de test pour tous les patterns du détecteur.

Usage : python tools/generate_test_circuits.py

Chaque circuit est :
  - Construit avec les vrais types ERetroDesign (Résistance, Capa, AOP, 2N2B, Diode, Self, Relais_1FormC)
  - Vérifié automatiquement : le pattern attendu doit être détecté
  - Exporté en XML dans circuits_industriels/

Patterns couverts par ce script (manquants dans les fichiers existants) :
  1. Intégrateur (AOP)
  2. Bascule de Schmitt (AOP)
  3. Transistor en commutation  (BJT seul, sans relais ni Rc)
  4. Miroir de courant BJT
  5. Diode de roue libre
  6. Redresseur simple alternance
  7. Détecteur de crête
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from circuit_analyzer.composant import Composant
from circuit_analyzer.detecteur import match_patterns
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.xml import generer_xml

OUT_DIR = RACINE / "circuits_industriels"


def _comp(ref, type_, pins, value=""):
    return Composant(ref=ref, type=type_, pins=pins, value=value)


def _save_and_verify(nom_fichier, comps, expected_pattern):
    """Génère le XML, le sauvegarde et vérifie que le pattern est bien détecté."""
    graph = build_graph(comps)
    results = match_patterns(graph)
    detected = [r["circuit_type"] for r in results]

    xml = generer_xml(comps, resultats=results)
    path = OUT_DIR / nom_fichier
    path.write_text(xml, encoding="utf-8")

    ok = expected_pattern in detected
    status = "OK" if ok else "ECHEC"
    print(f"  [{status}] {nom_fichier:40s} -> {detected[:4]}")
    if not ok:
        print(f"         !! attendu: '{expected_pattern}' — non trouvé dans {detected}")
    return ok


# ── 1. Intégrateur AOP ────────────────────────────────────────────────────────
# Schéma : NET_IN -[R1]- NET_INM -[AOP U1]- NET_OUT
#                          └────────[C1]──────┘  (feedback C de IN- vers OUT)
#          IN+ → GND (référence)
def build_integrator():
    return [
        _comp("U1",  "U", {"IN+": "GND",     "IN-": "NET_INM", "OUT": "NET_OUT"}, "LM741"),
        _comp("R1",  "R", {"1":   "NET_IN",  "2":   "NET_INM"},                   "10k"),
        _comp("C1",  "C", {"1":   "NET_INM", "2":   "NET_OUT"},                   "100n"),
        _comp("C2",  "C", {"1":   "VCC",     "2":   "GND"},                       "100n"),
        _comp("C3",  "C", {"1":   "VCC",     "2":   "GND"},                       "10u"),
        _comp("R2",  "R", {"1":   "NET_IN",  "2":   "GND"},                       "100k"),
    ]


# ── 2. Bascule de Schmitt AOP ────────────────────────────────────────────────
# Schéma : IN -[R1]- IN+
#                     AOP -[OUT]
#          OUT -[R2]- IN+         (contre-réaction POSITIVE)
#          IN- → diviseur de tension (référence)
def build_schmitt():
    return [
        _comp("U1",  "U", {"IN+": "NET_INP", "IN-": "NET_INM", "OUT": "NET_OUT"}, "LM393"),
        _comp("R1",  "R", {"1":   "NET_IN",  "2":   "NET_INP"},                   "10k"),
        _comp("R2",  "R", {"1":   "NET_OUT", "2":   "NET_INP"},                   "100k"),
        _comp("R3",  "R", {"1":   "VCC",     "2":   "NET_INM"},                   "47k"),
        _comp("R4",  "R", {"1":   "NET_INM", "2":   "GND"},                       "47k"),
        _comp("C1",  "C", {"1":   "VCC",     "2":   "GND"},                       "100n"),
        _comp("C2",  "C", {"1":   "VCC",     "2":   "GND"},                       "10u"),
    ]


# ── 3. Transistor en commutation (BJT, sans R au collecteur) ─────────────────
# Schéma : CMD -[R1]- BASE
#                      2N2B (BJT NPN)
#          COLL -[L1]- VCC   (charge inductrive — pas de R au collecteur)
#          EMIT → GND
def build_bjt_switch():
    return [
        _comp("Q1",  "Q", {"B":   "NET_BASE", "C":   "NET_COLL", "E":   "GND"},  "BC337"),
        _comp("R1",  "R", {"1":   "NET_CMD",  "2":   "NET_BASE"},                 "4.7k"),
        _comp("L1",  "L", {"1":   "VCC",      "2":   "NET_COLL"},                 "100u"),
        _comp("C1",  "C", {"1":   "VCC",      "2":   "GND"},                      "100n"),
        _comp("C2",  "C", {"1":   "VCC",      "2":   "GND"},                      "10u"),
        _comp("R2",  "R", {"1":   "VCC",      "2":   "NET_CMD"},                  "10k"),
    ]


# ── 4. Miroir de courant BJT ─────────────────────────────────────────────────
# Schéma : VCC -[R1]- NET_C1 - Q1(C), Q1(B)=Q2(B)=NET_BASE, Q1(E)=Q2(E)=GND
#                               Q2(C) - NET_C2 (sortie miroir)
def build_current_mirror():
    return [
        _comp("Q1",  "Q", {"B":   "NET_BASE", "C":   "NET_C1",  "E":   "GND"},   "BC337"),
        _comp("Q2",  "Q", {"B":   "NET_BASE", "C":   "NET_C2",  "E":   "GND"},   "BC337"),
        _comp("R1",  "R", {"1":   "VCC",      "2":   "NET_C1"},                   "10k"),
        _comp("C1",  "C", {"1":   "VCC",      "2":   "GND"},                      "100n"),
        _comp("C2",  "C", {"1":   "VCC",      "2":   "GND"},                      "10u"),
    ]


# ── 5. Diode de roue libre ───────────────────────────────────────────────────
# Schéma minimal : VCC -[L1]- NET_MOT -[D1 A→K]- VCC
# Pas de transistor (sinon D1 est absorbé en satellite du transistor par _absorber_annexes).
# Cathode sur VCC, anode sur NET_MOT (nœud ni masse ni alimentation).
def build_flyback():
    return [
        _comp("D1",  "D", {"A":   "NET_MOT",  "K":  "VCC"},                      "1N4007"),
        _comp("L1",  "L", {"1":   "VCC",      "2":  "NET_MOT"},                  "10m"),
        _comp("D2",  "D", {"A":   "GND",      "K":  "NET_MOT"},                  "1N4007"),
        _comp("C1",  "C", {"1":   "VCC",      "2":  "GND"},                      "100n"),
    ]


# ── 6. Redresseur simple alternance ─────────────────────────────────────────
# Schéma : NET_AC -[D1 A→K]- NET_DC -[R1]- GND
#          (NET_AC = signal AC, ni alim ni masse)
def build_half_wave():
    return [
        _comp("D1",  "D", {"A":   "NET_AC",  "K":   "NET_DC"},                    "1N4007"),
        _comp("R1",  "R", {"1":   "NET_DC",  "2":   "GND"},                       "1k"),
        _comp("R2",  "R", {"1":   "NET_DC",  "2":   "GND"},                       "100"),
        _comp("C1",  "C", {"1":   "VCC",     "2":   "GND"},                       "100n"),
    ]


# ── 7. Détecteur de crête ─────────────────────────────────────────────────────
# Schéma : NET_AC -[D1 A→K]- NET_PEAK -[C1]- GND
# Pas de R sur NET_PEAK (sinon detecter_redresseur_simple réclame D1 en premier).
def build_peak_detector():
    return [
        _comp("D1",  "D", {"A":   "NET_AC",   "K":   "NET_PEAK"},                 "1N4148"),
        _comp("C1",  "C", {"1":   "NET_PEAK", "2":   "GND"},                      "10u"),
        _comp("C2",  "C", {"1":   "VCC",      "2":   "GND"},                      "100n"),
    ]


# ── Exécution ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nGénération des circuits de test ERetroDesign :")
    print("=" * 60)

    tests = [
        ("integrator_aop.xml",       build_integrator(),   "Intégrateur (AOP)"),
        ("schmitt_trigger.xml",      build_schmitt(),      "Bascule de Schmitt (AOP)"),
        ("bjt_switch.xml",           build_bjt_switch(),   "Transistor en commutation"),
        ("current_mirror.xml",       build_current_mirror(),"Miroir de courant BJT"),
        ("flyback_protection.xml",   build_flyback(),      "Diode de roue libre"),
        ("half_wave_rectifier.xml",  build_half_wave(),    "Redresseur simple alternance"),
        ("peak_detector.xml",        build_peak_detector(),"Détecteur de crête"),
    ]

    echecs = 0
    for fname, comps, expected in tests:
        ok = _save_and_verify(fname, comps, expected)
        if not ok:
            echecs += 1

    print("=" * 60)
    if echecs == 0:
        print(f"  Tous les {len(tests)} circuits OK — fichiers dans circuits_industriels/")
    else:
        print(f"  {echecs} circuit(s) en ECHEC sur {len(tests)}")
    sys.exit(echecs)
