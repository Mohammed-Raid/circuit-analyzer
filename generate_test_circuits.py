"""
Génère les fichiers XML de test BoardSCH pour tous les types de circuits reconnus.
Chaque fichier peut être ouvert dans l'app de design ET analysé par Circuit Analyzer.

Usage: python generate_test_circuits.py
"""
import os
import sys
import io
sys.path.insert(0, os.path.dirname(__file__))
from circuit_analyzer.xml_generator import BoardSCHGenerator

# Force UTF-8 console output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = "circuits_test"
os.makedirs(OUT, exist_ok=True)


def save(name: str, gen: BoardSCHGenerator):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(gen.to_xml())
    print(f"  [OK]  {path}")


# ──────────────────────────────────────────────────────────────────────────────
# 1. Filtre RC passe-bas
# ──────────────────────────────────────────────────────────────────────────────
def make_rc_lowpass():
    g = BoardSCHGenerator()
    r1  = g.add("Résistance", "10k",  x=300,  y=400)
    c1  = g.add("Capa",       "100n", x=500,  y=400)
    gnd = g.add("GND",        "",     x=500,  y=580)
    g.connect(r1, "1",   c1,  "+")      # R1 → C1 node
    g.connect(c1, "-",   gnd, "GND")    # C1 → GND
    save("filtre_rc_passe_bas.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 2. Filtre RC passe-haut
# ──────────────────────────────────────────────────────────────────────────────
def make_rc_highpass():
    g = BoardSCHGenerator()
    c1  = g.add("Capa",       "100n", x=300,  y=400)
    r1  = g.add("Résistance", "10k",  x=500,  y=400)
    gnd = g.add("GND",        "",     x=500,  y=580)
    g.connect(c1, "+",   r1,  "2")      # C1 → R1 node
    g.connect(r1, "1",   gnd, "GND")    # R1 → GND
    save("filtre_rc_passe_haut.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 3. Condensateur de découplage
# ──────────────────────────────────────────────────────────────────────────────
def make_decoupling():
    g = BoardSCHGenerator()
    vcc = g.add("VCC",  "",      x=300,  y=260)
    c1  = g.add("Capa", "100n", x=300,  y=400)
    gnd = g.add("GND",  "",     x=300,  y=580)
    g.connect(vcc, "VCC", c1,  "+")     # VCC → C1
    g.connect(c1,  "-",   gnd, "GND")   # C1 → GND
    save("condensateur_decouplage.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 4. Pont diviseur de tension
# ──────────────────────────────────────────────────────────────────────────────
def make_voltage_divider():
    g = BoardSCHGenerator()
    vcc = g.add("VCC",        "",     x=300,  y=260)
    r1  = g.add("Résistance", "10k",  x=300,  y=400, angle=90)
    r2  = g.add("Résistance", "4k7",  x=300,  y=560, angle=90)
    gnd = g.add("GND",        "",     x=300,  y=700)
    g.connect(vcc, "VCC", r1,  "1")    # VCC → R1
    g.connect(r1,  "2",   r2,  "1")    # R1 mid → R2
    g.connect(r2,  "2",   gnd, "GND")  # R2 → GND
    save("pont_diviseur.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 5. Absorbeur RC (Snubber)
# ──────────────────────────────────────────────────────────────────────────────
def make_snubber():
    g = BoardSCHGenerator()
    r1 = g.add("Résistance", "100",  x=300,  y=360)
    c1 = g.add("Capa",       "10n",  x=300,  y=480)
    # Both in parallel between the same two nodes
    # Node A (left side): R1 pin2, C1 minus
    # Node B (right side): R1 pin1, C1 plus
    g.connect(r1, "1",   c1, "+")   # right node shared
    g.connect(r1, "2",   c1, "-")   # left node shared
    save("absorbeur_rc.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 6. Amplificateur inverseur (AOP)
# ──────────────────────────────────────────────────────────────────────────────
def make_inv_amp():
    g = BoardSCHGenerator()
    u1   = g.add("AOP",        "LM741", x=600,  y=500)
    rin  = g.add("Résistance", "10k",   x=380,  y=476)   # input R at IN-
    rf   = g.add("Résistance", "100k",  x=520,  y=330)   # feedback R
    gnd  = g.add("GND",        "",      x=440,  y=660)   # IN+ to GND
    g.connect(u1, "-",  rin, "1")     # IN- → R_in right
    g.connect(u1, "-",  rf,  "2")     # IN- → Rf left
    g.connect(u1, "s",  rf,  "1")     # OUT → Rf right
    g.connect(u1, "+",  gnd, "GND")   # IN+ → GND
    save("amplificateur_inverseur.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 7. Amplificateur non-inverseur (AOP)
# ──────────────────────────────────────────────────────────────────────────────
def make_noninv_amp():
    g = BoardSCHGenerator()
    u1  = g.add("AOP",        "LM741", x=600,  y=500)
    rf  = g.add("Résistance", "100k",  x=520,  y=330)    # feedback
    rg  = g.add("Résistance", "10k",   x=380,  y=580, angle=90)  # to GND
    gnd = g.add("GND",        "",      x=300,  y=660)
    g.connect(u1, "-",  rf,  "2")     # IN- → Rf left
    g.connect(u1, "s",  rf,  "1")     # OUT → Rf right
    g.connect(u1, "-",  rg,  "1")     # IN- → Rg top
    g.connect(rg, "2",  gnd, "GND")   # Rg bottom → GND
    save("amplificateur_non_inverseur.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 8. Suiveur de tension (AOP)
# ──────────────────────────────────────────────────────────────────────────────
def make_follower():
    g = BoardSCHGenerator()
    u1 = g.add("AOP", "LM741", x=500, y=500)
    # IN- directly wired to OUT (same net)
    g.connect(u1, "-", u1, "s")    # feedback: IN- = OUT
    save("suiveur_tension.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 9. Intégrateur (AOP)
# ──────────────────────────────────────────────────────────────────────────────
def make_integrator():
    g = BoardSCHGenerator()
    u1  = g.add("AOP",   "LM741", x=600,  y=500)
    r1  = g.add("Résistance", "10k",  x=380,  y=476)
    c1  = g.add("Capa",  "100n", x=520,  y=330)
    gnd = g.add("GND",   "",     x=440,  y=660)
    g.connect(u1, "-",  r1, "1")   # IN- → R1 right
    g.connect(u1, "-",  c1, "-")   # IN- → C1 left
    g.connect(u1, "s",  c1, "+")   # OUT → C1 right (feedback)
    g.connect(u1, "+",  gnd, "GND")
    save("integrateur.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 10. Dérivateur (AOP)
# ──────────────────────────────────────────────────────────────────────────────
def make_differentiator():
    g = BoardSCHGenerator()
    u1  = g.add("AOP",        "LM741", x=600,  y=500)
    c1  = g.add("Capa",       "100n",  x=380,  y=476)
    r1  = g.add("Résistance", "10k",   x=520,  y=330)
    gnd = g.add("GND",        "",      x=440,  y=660)
    g.connect(u1, "-",  c1, "+")   # IN- → C1 right
    g.connect(u1, "-",  r1, "2")   # IN- → R1 left  (feedback)
    g.connect(u1, "s",  r1, "1")   # OUT → R1 right
    g.connect(u1, "+",  gnd, "GND")
    save("derivateur.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 11. Comparateur (AOP) — pas de rétroaction
# ──────────────────────────────────────────────────────────────────────────────
def make_comparator():
    g = BoardSCHGenerator()
    u1 = g.add("AOP", "LM339", x=500, y=500)
    # No feedback — just two inputs and output
    # Nothing to connect (pins are on separate nets)
    save("comparateur.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 12. Bascule de Schmitt (AOP) — rétroaction positive
# ──────────────────────────────────────────────────────────────────────────────
def make_schmitt():
    g = BoardSCHGenerator()
    u1 = g.add("AOP",        "LM741", x=500,  y=500)
    rf = g.add("Résistance", "100k",  x=420,  y=350)
    g.connect(u1, "+", rf, "2")   # IN+ → Rf left
    g.connect(u1, "s", rf, "1")   # OUT → Rf right (positive feedback)
    save("bascule_schmitt.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 13. Amplificateur différentiel (AOP)
# ──────────────────────────────────────────────────────────────────────────────
def make_diff_amp():
    g = BoardSCHGenerator()
    u1  = g.add("AOP",        "LM741", x=700,  y=500)
    r1  = g.add("Résistance", "10k",   x=480,  y=452)   # IN+ input R
    rg  = g.add("Résistance", "10k",   x=340,  y=560, angle=90)  # IN+ to GND
    r2  = g.add("Résistance", "100k",  x=480,  y=548)   # IN- input R
    rf  = g.add("Résistance", "100k",  x=620,  y=330)   # feedback
    gnd = g.add("GND",        "",      x=260,  y=680)
    g.connect(u1, "+",  r1, "1")    # IN+ → R1 right
    g.connect(u1, "+",  rg, "1")    # IN+ → Rg top
    g.connect(rg, "2",  gnd, "GND") # Rg → GND
    g.connect(u1, "-",  r2, "1")    # IN- → R2 right
    g.connect(u1, "-",  rf, "2")    # IN- → Rf left
    g.connect(u1, "s",  rf, "1")    # OUT → Rf right
    save("amplificateur_differentiel.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 14. Amplificateur sommateur (AOP)
# ──────────────────────────────────────────────────────────────────────────────
def make_summing_amp():
    g = BoardSCHGenerator()
    u1  = g.add("AOP",        "LM741", x=700,  y=500)
    rf  = g.add("Résistance", "100k",  x=620,  y=330)
    ra  = g.add("Résistance", "10k",   x=480,  y=430)
    rb  = g.add("Résistance", "10k",   x=480,  y=500)
    rc  = g.add("Résistance", "10k",   x=480,  y=570)
    gnd = g.add("GND",        "",      x=560,  y=680)
    g.connect(u1, "-",  rf, "2")    # IN- → Rf left
    g.connect(u1, "s",  rf, "1")    # OUT → Rf right
    g.connect(u1, "-",  ra, "1")    # IN- → Ra right
    g.connect(u1, "-",  rb, "1")    # IN- → Rb right
    g.connect(u1, "-",  rc, "1")    # IN- → Rc right
    g.connect(u1, "+",  gnd, "GND") # IN+ → GND
    save("amplificateur_sommateur.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 15. Transistor en commutation (BJT NPN)
# ──────────────────────────────────────────────────────────────────────────────
def make_bjt_switch():
    g = BoardSCHGenerator()
    q1  = g.add("Transistor", "BC547", x=500,  y=500)
    r1  = g.add("Résistance", "1k",    x=280,  y=500)   # base R
    gnd = g.add("GND",        "",      x=540,  y=720)   # emitter
    g.connect(q1, "B",  r1,  "1")     # Base ← R1
    g.connect(q1, "E",  gnd, "GND")   # Emitter → GND
    save("transistor_commutation.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 16. Amplificateur émetteur commun (BJT)
# ──────────────────────────────────────────────────────────────────────────────
def make_ce_amp():
    g = BoardSCHGenerator()
    q1  = g.add("Transistor", "BC547", x=500,  y=500)
    rb  = g.add("Résistance", "100k",  x=280,  y=500)   # base bias
    rc  = g.add("Résistance", "2k2",   x=500,  y=280, angle=90)  # collector load
    vcc = g.add("VCC",        "",      x=500,  y=160)
    gnd = g.add("GND",        "",      x=540,  y=720)
    g.connect(q1, "B",  rb,  "1")     # Base ← Rb
    g.connect(q1, "C",  rc,  "2")     # Collector → Rc bottom
    g.connect(rc, "1",  vcc, "VCC")   # Rc top → VCC
    g.connect(q1, "E",  gnd, "GND")   # Emitter → GND
    save("amplificateur_emetteur_commun.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 17. Miroir de courant BJT
# ──────────────────────────────────────────────────────────────────────────────
def make_current_mirror():
    g = BoardSCHGenerator()
    q1   = g.add("Transistor", "BC547", x=400,  y=500)   # reference
    q2   = g.add("Transistor", "BC547", x=600,  y=500)   # output
    gnd1 = g.add("GND",        "",      x=440,  y=720)
    gnd2 = g.add("GND",        "",      x=640,  y=720)
    # Shared base + Q1 diode-connected (collector = base)
    g.connect(q1, "B",  q2,   "B")     # bases shared
    g.connect(q1, "C",  q1,   "B")     # Q1 diode-connect (C=B)
    g.connect(q1, "E",  gnd1, "GND")
    g.connect(q2, "E",  gnd2, "GND")
    save("miroir_courant_bjt.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 18. MOSFET en commutation
# ──────────────────────────────────────────────────────────────────────────────
def make_mosfet_switch():
    g = BoardSCHGenerator()
    m1  = g.add("MOSFET",     "IRF540", x=500,  y=500)
    rg  = g.add("Résistance", "100",    x=280,  y=500)   # gate R
    gnd = g.add("GND",        "",       x=500,  y=720)   # source
    g.connect(m1, "G",  rg,  "1")     # Gate ← Rg
    g.connect(m1, "S",  gnd, "GND")   # Source → GND
    save("mosfet_commutation.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 19. Pont redresseur (Graetz)
# ──────────────────────────────────────────────────────────────────────────────
def make_bridge_rectifier():
    g = BoardSCHGenerator()
    d1 = g.add("Diode", "1N4007", x=400, y=300)
    d2 = g.add("Diode", "1N4007", x=600, y=300)
    d3 = g.add("Diode", "1N4007", x=400, y=500)
    d4 = g.add("Diode", "1N4007", x=600, y=500)
    # AC1 node: D1 anode, D3 cathode
    g.connect(d1, "A",  d3, "K")   # AC1
    # AC2 node: D2 anode, D4 cathode
    g.connect(d2, "A",  d4, "K")   # AC2
    # DC+ node: D1 cathode, D2 cathode
    g.connect(d1, "K",  d2, "K")   # DC+
    # DC- node: D3 anode, D4 anode
    g.connect(d3, "A",  d4, "A")   # DC-
    save("pont_redresseur_graetz.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 20. Protection par fusible
# ──────────────────────────────────────────────────────────────────────────────
def make_fuse():
    g = BoardSCHGenerator()
    f1 = g.add("Fusible", "500mA", x=400, y=400)
    save("protection_fusible.xml", g)


# ──────────────────────────────────────────────────────────────────────────────
# 21. Circuit combiné (plusieurs patterns sur une carte)
# ──────────────────────────────────────────────────────────────────────────────
def make_combined():
    """Une carte complète avec filtre RC + AOP inverseur + transistor + fusible."""
    g = BoardSCHGenerator()
    # Fusible en entrée
    f1   = g.add("Fusible",    "500mA", x=100,  y=300)
    # Filtre RC passe-bas
    r1   = g.add("Résistance", "10k",   x=280,  y=300)
    c1   = g.add("Capa",       "100n",  x=460,  y=300)
    gnd1 = g.add("GND",        "",      x=460,  y=460)
    # Condensateur de découplage VCC
    vcc1 = g.add("VCC",        "",      x=640,  y=200)
    c2   = g.add("Capa",       "10uF",  x=640,  y=320)
    gnd2 = g.add("GND",        "",      x=640,  y=460)
    # AOP inverseur
    u1   = g.add("AOP",        "LM741", x=720,  y=500)
    rin  = g.add("Résistance", "10k",   x=530,  y=476)
    rf   = g.add("Résistance", "100k",  x=640,  y=360)
    gnd3 = g.add("GND",        "",      x=640,  y=660)
    # Transistor commutation en sortie
    q1   = g.add("Transistor", "BC547", x=980,  y=500)
    rb   = g.add("Résistance", "1k",    x=820,  y=500)
    gnd4 = g.add("GND",        "",      x=1020, y=720)

    # Fusible → R1
    g.connect(f1,  "2",   r1,   "2")
    # Filtre RC
    g.connect(r1,  "1",   c1,   "+")
    g.connect(c1,  "-",   gnd1, "GND")
    # Condensateur de découplage
    g.connect(vcc1,"VCC", c2,   "+")
    g.connect(c2,  "-",   gnd2, "GND")
    # AOP inverseur : sortie filtre → entrée AOP
    g.connect(c1,  "+",   rin,  "2")    # signal node
    g.connect(u1,  "-",   rin,  "1")
    g.connect(u1,  "-",   rf,   "2")
    g.connect(u1,  "s",   rf,   "1")
    g.connect(u1,  "+",   gnd3, "GND")
    # Transistor : sortie AOP → base via Rb
    g.connect(u1,  "s",   rb,   "2")
    g.connect(rb,  "1",   q1,   "B")
    g.connect(q1,  "E",   gnd4, "GND")

    save("circuit_combine.xml", g)


if __name__ == "__main__":
    print("Génération des fichiers XML de test...\n")
    make_rc_lowpass()
    make_rc_highpass()
    make_decoupling()
    make_voltage_divider()
    make_snubber()
    make_inv_amp()
    make_noninv_amp()
    make_follower()
    make_integrator()
    make_differentiator()
    make_comparator()
    make_schmitt()
    make_diff_amp()
    make_summing_amp()
    make_bjt_switch()
    make_ce_amp()
    make_current_mirror()
    make_mosfet_switch()
    make_bridge_rectifier()
    make_fuse()
    make_combined()
    print(f"\n{21} fichiers générés dans {OUT}/")
