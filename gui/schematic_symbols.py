"""@file schematic_symbols.py
@brief Primitives vectorielles des symboles de l'editeur (spec 2026-07-15
§3). Module PUR (aucun import graphique) : chaque traceur produit des
primitives en coordonnees MONDE centrees sur (0,0), rotation appliquee ici.

Primitive :
  ("line", [(x,y),...], epaisseur)
  ("polygon", [(x,y),...], rempli: bool)
  ("arc", (x0,y0,x1,y1), start_deg, extent_deg)
  ("text", (x,y), texte, taille, ancre)
"""

from gui.theme import SCHEMA_COLORS


def rotate_pin(dx, dy, rotation):
    """@brief Tourne (dx,dy) de `rotation` degres sens horaire (0/90/180/270)."""
    if rotation == 90:
        return (dy, -dx)
    if rotation == 180:
        return (-dx, -dy)
    if rotation == 270:
        return (-dy, dx)
    return (dx, dy)


def _rot_prims(prims, rotation):
    """@brief Applique la rotation a toutes les primitives."""
    if rotation % 360 == 0:
        return prims
    out = []
    for p in prims:
        if p[0] in ("line", "polygon"):
            out.append((p[0], [rotate_pin(x, y, rotation) for x, y in p[1]],
                        p[2]))
        elif p[0] == "arc":
            x0, y0, x1, y1 = p[1]
            (ax, ay) = rotate_pin(x0, y0, rotation)
            (bx, by) = rotate_pin(x1, y1, rotation)
            out.append(("arc", (ax, ay, bx, by),
                        (p[2] + rotation) % 360, p[3]))
        elif p[0] == "text":
            out.append(("text", rotate_pin(*p[1], rotation), p[2], p[3], p[4]))
    return out


def _tr_r(d):
    # Zigzag 6 crêtes entre -24 et 24, amorces jusqu'aux pins.
    a = 8
    pts = [(-40, 0), (-24, 0)]
    xs = [-24 + i * 8 for i in range(1, 6)]
    for i, x in enumerate(xs):
        pts.append((x, -a if i % 2 == 0 else a))
    pts += [(24, 0), (40, 0)]
    return [("line", pts, 2)]


def _tr_c(d):
    return [
        ("line", [(-30, 0), (-4, 0)], 2),
        ("line", [(-4, -12), (-4, 12)], 3),
        ("line", [(4, -12), (4, 12)], 3),
        ("line", [(4, 0), (30, 0)], 2),
    ]


def _tr_l(d):
    prims = [("line", [(-40, 0), (-24, 0)], 2)]
    for i in range(3):
        x0 = -24 + i * 16
        prims.append(("arc", (x0, -8, x0 + 16, 8), 0, 180))
    prims.append(("line", [(24, 0), (40, 0)], 2))
    return prims


def _tr_d(d, value=""):
    prims = [
        ("line", [(-30, 0), (-8, 0)], 2),
        ("polygon", [(-8, -10), (-8, 10), (8, 0)], True),
        ("line", [(8, -10), (8, 10)], 3),
        ("line", [(8, 0), (30, 0)], 2),
    ]
    if (value or "").upper().startswith("LED"):
        prims.append(("line", [(2, -12), (10, -20)], 1))
        prims.append(("line", [(8, -10), (16, -18)], 1))
    return prims


def _tr_f(d):
    return [
        ("line", [(-40, 0), (40, 0)], 2),
        ("polygon", [(-20, -7), (20, -7), (20, 7), (-20, 7)], False),
    ]


def _tr_q(d):
    # NPN : barre de base verticale, cercle, collecteur haut, émetteur bas fléché.
    return [
        ("line", [(-30, 0), (-8, 0)], 2),
        ("line", [(-8, -16), (-8, 16)], 3),
        ("line", [(-8, -8), (30, -30)], 2),
        ("line", [(-8, 8), (30, 30)], 2),
        ("polygon", [(18, 20), (30, 30), (16, 28)], True),   # flèche émetteur
        ("arc", (-24, -24, 24, 24), 0, 360),
    ]


def _tr_m(d):
    # MOSFET canal N simplifié : grille + 3 segments de canal + flèche.
    return [
        ("line", [(-30, 0), (-10, 0)], 2),
        ("line", [(-10, -16), (-10, 16)], 3),
        ("line", [(-4, -18), (-4, -6)], 2),
        ("line", [(-4, -6), (-4, 6)], 2),
        ("line", [(-4, 6), (-4, 18)], 2),
        ("line", [(-4, -12), (30, -30)], 2),
        ("line", [(-4, 12), (30, 30)], 2),
        ("polygon", [(4, 8), (-4, 12), (4, 16)], True),      # flèche substrat
    ]


def _tr_u(d):
    # Triangle AOP : pins IN+ (-40,-20), IN- (-40,20), OUT (40,0).
    return [
        ("polygon", [(-24, -32), (-24, 32), (40, 0)], False),
        ("line", [(-40, -20), (-24, -20)], 2),
        ("line", [(-40, 20), (-24, 20)], 2),
        ("text", (-16, -20), "+", 10, "center"),
        ("text", (-16, 20), "-", 10, "center"),
    ]


def _tr_gnd(d):
    prims = [("line", [(0, -20), (0, 0)], 2)]
    for i, hw in enumerate([16, 10, 5]):
        prims.append(("line", [(-hw, i * 5), (hw, i * 5)], 2))
    return prims


def _tr_vcc(d):
    return [
        ("line", [(0, 20), (0, 2)], 2),
        ("polygon", [(-10, 2), (10, 2), (0, -14)], True),
    ]


def _tr_t(d):
    # Transfo : 2 enroulements verticaux + 2 barres centrales.
    prims = []
    for cote in (-1, 1):
        x = cote * 12
        for i in range(3):
            y0 = -24 + i * 16
            prims.append(("arc", (x - 8, y0, x + 8, y0 + 16),
                          90 if cote < 0 else 270, 180))
        prims.append(("line", [(cote * 40, -20), (x, -20)], 2))
        prims.append(("line", [(cote * 40, 20), (x, 20)], 2))
    prims.append(("line", [(-3, -26), (-3, 26)], 1))
    prims.append(("line", [(3, -26), (3, 26)], 1))
    return prims


def _tr_k(d):
    # Relais : bobine (rectangle) + contact incliné.
    return [
        ("polygon", [(-36, -12), (-4, -12), (-4, 12), (-36, 12)], False),
        ("line", [(-40, -20), (-20, -20), (-20, -12)], 2),
        ("line", [(-40, 20), (-20, 20), (-20, 12)], 2),
        ("line", [(8, -20), (40, -20)], 2),
        ("line", [(8, 20), (40, 20)], 2),
        ("line", [(8, 20), (28, -16)], 2),
    ]


_TRACEURS = {
    "R": _tr_r, "C": _tr_c, "L": _tr_l, "F": _tr_f, "Q": _tr_q,
    "M": _tr_m, "U": _tr_u, "GND": _tr_gnd, "VCC": _tr_vcc,
    "T": _tr_t, "K": _tr_k,
}


def _tr_boite(defn):
    """@brief Boîte générique à encoche (types perso, puces catalogue) :
    rectangle + encoche haut + stub par broche (le trait court qui va du
    corps a la broche, style DIP)."""
    w2, h2 = defn["w"] // 2, defn["h"] // 2
    corps = w2 - 8
    prims = [
        ("polygon", [(-corps, -h2), (corps, -h2), (corps, h2), (-corps, h2)],
         False),
        ("arc", (-8, -h2 - 4, 8, -h2 + 8), 180, 180),
    ]
    for pn, (px, py) in defn["pins"].items():
        bord = corps if px > 0 else -corps
        if abs(px) > corps:
            prims.append(("line", [(bord, py), (px, py)], 2))
        fonction = (defn.get("fonctions") or {}).get(pn, "")
        libelle = f"{pn} {fonction}".strip()
        ancre = "e" if px < 0 else "w"
        tx = bord + (6 if px < 0 else -6)
        prims.append(("text", (tx, py), libelle, 7, ancre))
    return prims


def primitives(comp_type, defn, rotation, value=""):
    """@brief Primitives monde du symbole, rotation appliquee.

    Types traces : table _TRACEURS. Tout autre type (perso, puce catalogue)
    -> boite generique a encoche avec stubs et libelles de broches.
    """
    if comp_type == "D":
        prims = _tr_d(defn, value)
    elif comp_type in _TRACEURS:
        prims = _TRACEURS[comp_type](defn)
    else:
        prims = _tr_boite(defn)
    return _rot_prims(prims, rotation)


def def_puce(value, broches):
    """@brief Def dynamique DIP pour une puce catalogue (spec §5).

    Broches 1..n/2 a GAUCHE de haut en bas, n/2+1..n a DROITE de bas en
    haut (convention DIP). Pas vertical 20, largeur 120, coordonnees sur
    grille 20. Cles compatibles COMP_DEFS + "fonctions".
    """
    nums = sorted(broches, key=int)
    n = len(nums)
    gauche = nums[: (n + 1) // 2]
    droite = nums[(n + 1) // 2:]
    rangees = max(len(gauche), len(droite))
    h2 = ((rangees + 1) * 20) // 2
    h2 = h2 + (20 - h2 % 20) % 20        # multiple de 20
    pins = {}
    for i, pn in enumerate(gauche):
        pins[pn] = (-60, -h2 + 20 * (i + 1))
    for i, pn in enumerate(droite):
        pins[pn] = (60, h2 - 20 * (i + 1))
    return {
        "label": value, "color": SCHEMA_COLORS["COMP"]["U"], "w": 120, "h": h2 * 2,
        "pins": pins, "default_value": value,
        "fonctions": dict(broches),
    }
