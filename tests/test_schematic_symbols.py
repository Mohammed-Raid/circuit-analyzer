"""@file test_schematic_symbols.py
@brief Primitives vectorielles des symboles (spec 2026-07-15 §3) : chaque
type trace, rotation coherente, DIP catalogue, purete d'import.
"""
import subprocess
import sys

from gui.schematic_symbols import (aimanter_bord, def_puce,
                                    est_boite_generique, geometrie_libre,
                                    primitives, rotate_pin)

# Géométries minimales suffisantes pour tracer (pins réels de COMP_DEFS).
DEFS = {
    "R": {"w": 80, "h": 40, "pins": {"1": (-40, 0), "2": (40, 0)}},
    "C": {"w": 60, "h": 40, "pins": {"1": (-30, 0), "2": (30, 0)}},
    "L": {"w": 80, "h": 40, "pins": {"1": (-40, 0), "2": (40, 0)}},
    "D": {"w": 60, "h": 40, "pins": {"A": (-30, 0), "K": (30, 0)}},
    "F": {"w": 80, "h": 40, "pins": {"1": (-40, 0), "2": (40, 0)}},
    "Q": {"w": 60, "h": 80, "pins": {"B": (-30, 0), "C": (30, -30), "E": (30, 30)}},
    "M": {"w": 60, "h": 80, "pins": {"G": (-30, 0), "D": (30, -30), "S": (30, 30)}},
    "U": {"w": 80, "h": 80, "pins": {"IN+": (-40, -20), "IN-": (-40, 20), "OUT": (40, 0)}},
    "GND": {"w": 40, "h": 40, "pins": {"1": (0, -20)}},
    "VCC": {"w": 40, "h": 40, "pins": {"1": (0, 20)}},
}
TYPES_TRACES = list(DEFS)


def _points(prims):
    pts = []
    for p in prims:
        if p[0] in ("line", "polygon"):
            pts += list(p[1])
        elif p[0] == "arc":
            x0, y0, x1, y1 = p[1]
            pts += [(x0, y0), (x1, y1)]
        elif p[0] == "text":
            pts.append(p[1])
    return pts


def test_chaque_type_produit_des_primitives():
    for t in TYPES_TRACES:
        prims = primitives(t, DEFS[t], 0)
        assert prims, t
        # ... et atteint chacune de ses broches (le symbole touche ses pins)
        for pn, (px, py) in DEFS[t]["pins"].items():
            assert any(abs(x - px) < 1e-6 and abs(y - py) < 1e-6
                       for x, y in _points(prims)), (t, pn)


def test_rotation_appliquee_aux_primitives():
    for t in ("R", "Q", "U"):
        p0 = _points(primitives(t, DEFS[t], 0))
        p90 = _points(primitives(t, DEFS[t], 90))
        attendus = [rotate_pin(x, y, 90) for x, y in p0]
        assert sorted(p90) == sorted(attendus), t


def test_led_ajoute_des_fleches():
    nue = primitives("D", DEFS["D"], 0)
    led = primitives("D", DEFS["D"], 0, value="LED rouge")
    assert len(led) == len(nue) + 2   # 2 flèches sortantes


def test_resistance_zigzag():
    lignes = [p for p in primitives("R", DEFS["R"], 0) if p[0] == "line"]
    # Le zigzag : au moins une polyligne de >= 8 points (6 crêtes + amorces)
    assert any(len(l[1]) >= 8 for l in lignes)


def test_def_puce_ne555_dip():
    broches = {str(i): f for i, f in enumerate(
        ["GND", "TRIG", "OUT", "RESET", "CTRL", "THR", "DIS", "VCC"], 1)}
    d = def_puce("NE555", broches)
    pins = d["pins"]
    assert set(pins) == set(broches)
    # DIP : 1..4 à gauche de HAUT en BAS, 5..8 à droite de BAS en HAUT
    assert all(pins[str(i)][0] < 0 for i in range(1, 5))
    assert all(pins[str(i)][0] > 0 for i in range(5, 9))
    ys_gauche = [pins[str(i)][1] for i in range(1, 5)]
    assert ys_gauche == sorted(ys_gauche)
    ys_droite = [pins[str(i)][1] for i in range(5, 9)]
    assert ys_droite == sorted(ys_droite, reverse=True)
    # Grille : toutes coordonnées multiples de 20
    assert all(px % 20 == 0 and py % 20 == 0 for px, py in pins.values())
    assert d["fonctions"]["2"] == "TRIG"
    assert d["default_value"] == "NE555"


def test_est_boite_generique():
    # Puce catalogue ("U::NE555") : pas dans _TRACEURS -> boîte générique.
    assert est_boite_generique("U::NE555") is True
    # Type perso (absent de _TRACEURS) -> boîte générique aussi.
    assert est_boite_generique("MODULE_XYZ") is True
    # Types tracés par une primitive dédiée -> pas une boîte.
    assert est_boite_generique("R") is False
    assert est_boite_generique("GND") is False


def test_purete_import():
    code = ("import sys; import gui.schematic_symbols; "
            "sys.exit(1 if any(m in sys.modules for m in "
            "('tkinter', 'customtkinter', 'matplotlib')) else 0)")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert r.returncode == 0, r.stderr


# ── Brochage libre (spec 2026-07-23) ─────────────────────────────────────────

def test_boite_vide_a_la_taille_minimale():
    d = geometrie_libre({})
    assert d["pins"] == {}
    assert (d["w"], d["h"]) == (80, 60)


def test_cotes_vers_offsets_absolus():
    d = geometrie_libre({"1": ("L", -20), "2": ("R", 20), "3": ("T", 0)})
    w2, h2 = d["w"] // 2, d["h"] // 2
    assert d["pins"]["1"] == (-w2, -20)     # bord gauche : le décalage est un y
    assert d["pins"]["2"] == (w2, 20)
    assert d["pins"]["3"] == (0, -h2)       # bord haut : le décalage est un x
    assert d["cotes"]["3"] == "T"


def test_boite_s_agrandit_pour_contenir_les_broches():
    d = geometrie_libre({"1": ("L", -100)})
    assert d["h"] >= 220                    # 2*100 + marge
    assert d["pins"]["1"] == (-d["w"] // 2, -100)


def test_aimantation_choisit_le_bord_le_plus_proche():
    assert aimanter_bord(-38, 7, 80, 60, 20) == ("L", 0)
    assert aimanter_bord(38, -13, 80, 60, 20) == ("R", -20)
    assert aimanter_bord(11, -29, 80, 60, 20) == ("T", 20)


def test_aimantation_au_coin_les_bords_horizontaux_gagnent():
    # coin haut-gauche exact : distance nulle aux deux bords -> T
    assert aimanter_bord(-40, -30, 80, 60, 20)[0] == "T"


def test_boite_s_elargit_pour_loger_les_libelles():
    court = geometrie_libre({"A": ("L", 0), "B": ("R", 0)})
    long_ = geometrie_libre({"ENABLE": ("L", 0), "FEEDBACK": ("R", 0)})
    assert long_["w"] > court["w"]


def test_libelles_opposes_ne_se_chevauchent_pas():
    """Défaut trouvé en boucle visuelle : 'IN1 VCCOUT1' télescopés."""
    from gui.schematic_symbols import CHAR_W, _tr_boite_libre
    d = geometrie_libre({"IN1": ("L", 0), "OUT1": ("R", 0)})
    spans = []
    for _t, (x, _y), texte, _taille, ancre in [p for p in _tr_boite_libre(d)
                                               if p[0] == "text"]:
        larg = len(texte) * CHAR_W
        spans.append((x, x + larg) if ancre == "w" else (x - larg, x))
    (a0, a1), (b0, b1) = sorted(spans)
    assert a1 <= b0, f"libellés qui se chevauchent : {spans}"


def test_broches_haut_bas_laissent_de_la_hauteur():
    sans = geometrie_libre({"A": ("L", 0)})
    avec = geometrie_libre({"A": ("L", 0), "VCC": ("T", 0), "GND": ("B", 0)})
    assert avec["h"] > sans["h"]
