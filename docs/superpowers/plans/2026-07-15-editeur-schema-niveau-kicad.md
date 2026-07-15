# Éditeur de schéma niveau KiCad — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Symboles schématiques réels, câblage à jonctions, puces réelles dans la palette et raccourcis KiCad dans l'onglet Dessiner ; retrait de l'onglet Saisie.

**Architecture:** Nouveau module pur `gui/schematic_symbols.py` (primitives vectorielles par type, testable sans Tk) rendu par `_draw_comp` ; logique de jonctions et split `U::REF` dans `gui/schematic_io.py` (pur) ; interactions (molette, pan, sélection rectangle) dans `gui/schematic_editor.py`. Format `.circ` et export inchangés (sauf convention `type="U::REF"`, rétro-compatible).

**Tech Stack:** Python 3.14 local (`python`), tk.Canvas/customtkinter existants, pytest.

**Spec:** `docs/superpowers/specs/2026-07-15-editeur-schema-niveau-kicad-design.md`

## Global Constraints

- `PYTHONUTF8=1` devant chaque commande python/pytest (shell cp1252).
- `gui/schematic_symbols.py` : AUCUN import tkinter/customtkinter/matplotlib (test subprocess, pattern schema_grid).
- Les POSITIONS DE BROCHES de `COMP_DEFS`/`_defs` ne changent PAS (les `.circ` existants se rouvrent à l'identique) ; grille monde = 20.
- Primitive = tuple : `("line", [(x,y),...], epaisseur)` | `("polygon", [(x,y),...], rempli: bool)` | `("arc", (x0,y0,x1,y1), start, extent)` | `("text", (x,y), s, taille, ancre)`.
- `.circ` ancien (types sans `::`) : lecture/écriture STRICTEMENT inchangées.
- Boucle visuelle OBLIGATOIRE sur toute tâche de rendu : capture PNG du canvas réel + inspection (Read tool) AVANT commit.
- Suite complète verte à chaque tâche (~1657 passed / 14 skipped ; flake connu test_500_portes_sous_budget sous charge → relancer isolément).
- Commits FRANÇAIS, JAMAIS de footer Co-Authored-By/Generated. `git add` fichier par fichier, JAMAIS -A (docs.rar non suivi = fichier du boss, intouchable). Rien n'est poussé.

---

### Task 1: gui/schematic_symbols.py — primitives vectorielles par type

**Files:**
- Create: `gui/schematic_symbols.py`
- Test: `tests/test_schematic_symbols.py`

**Interfaces:**
- Consomme : rien (module pur ; `_rotate_pin` est DÉPLACÉ ici depuis `gui/schematic_editor.py` qui l'importera désormais d'ici — adapter l'import dans schematic_editor.py fait partie de cette tâche, sans autre changement de ce fichier).
- Produit (Tasks 3, 5) :
  - `rotate_pin(dx, dy, rotation) -> (dx, dy)` (renommage public de `_rotate_pin`, même corps)
  - `primitives(comp_type: str, defn: dict, rotation: int, value: str = "") -> list[tuple]` — primitives en coordonnées monde CENTRÉES sur (0,0), rotation déjà appliquée
  - `def_puce(value: str, broches: dict[str, str]) -> dict` — def dynamique DIP compatible `COMP_DEFS` (clés `label`, `color`, `w`, `h`, `pins`, `default_value`, + `fonctions`)

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_schematic_symbols.py
"""@file test_schematic_symbols.py
@brief Primitives vectorielles des symboles (spec 2026-07-15 §3) : chaque
type trace, rotation coherente, DIP catalogue, purete d'import.
"""
import subprocess
import sys

from gui.schematic_symbols import def_puce, primitives, rotate_pin

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


def test_purete_import():
    code = ("import sys; import gui.schematic_symbols; "
            "sys.exit(1 if any(m in sys.modules for m in "
            "('tkinter', 'customtkinter', 'matplotlib')) else 0)")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert r.returncode == 0, r.stderr
```

- [ ] **Step 2: RED**

Run: `PYTHONUTF8=1 python -m pytest tests/test_schematic_symbols.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gui.schematic_symbols'`

- [ ] **Step 3: Implémenter le module**

```python
# gui/schematic_symbols.py
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
            out.append(("arc", (min(ax, bx), min(ay, by),
                                max(ax, bx), max(ay, by)),
                        (p[2] - rotation) % 360, p[3]))
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
        "label": value, "color": "#b45309", "w": 120, "h": h2 * 2,
        "pins": pins, "default_value": value,
        "fonctions": dict(broches),
    }
```

NOTE : le `#b45309` de `def_puce` est la couleur U de `COMP_DEFS`-analyse
(SCHEMA_COLORS["COMP"]["U"]) — l'importer depuis `gui.theme`
(`SCHEMA_COLORS["COMP"]["U"]`) au lieu du littéral (contrainte anti-hex du
projet ; theme.py n'importe rien de graphique, la pureté tient).

Déplacer aussi `_rotate_pin` : dans `gui/schematic_editor.py`, remplacer la
définition locale (lignes ~123-128) par
`from gui.schematic_symbols import rotate_pin as _rotate_pin` (aucun autre
changement dans ce fichier pour cette tâche).

- [ ] **Step 4: GREEN + non-régression éditeur**

Run: `PYTHONUTF8=1 python -m pytest tests/test_schematic_symbols.py -q`
Expected: 7 passed.
Run: `PYTHONUTF8=1 python -m pytest -q -k "schematic or editor or draw"`
Expected: aucun échec (l'import déplacé n'a rien cassé).

- [ ] **Step 5: Commit**

```bash
git add gui/schematic_symbols.py gui/schematic_editor.py tests/test_schematic_symbols.py
git commit -m "feat(editeur): schematic_symbols - primitives vectorielles par type + def_puce DIP (module pur)"
```

---

### Task 2: schematic_io — jonctions + convention U::REF

**Files:**
- Modify: `gui/schematic_io.py`
- Test: `tests/test_schematic_io.py` (créer si absent — vérifier d'abord ; si des tests IO existent ailleurs (`grep -rl editor_to_dict tests/`), étendre le fichier existant)

**Interfaces:**
- Produit (Tasks 4, 5) :
  - `points_jonction(comps: dict, wires: list, defs: dict) -> list[tuple[int, int]]` — points monde où ≥ 3 extrémités de fils coïncident
  - `type_reel(comp_type: str) -> tuple[str, str]` — `"U::NE555"` → `("U", "NE555")` ; `"R"` → `("R", "")`
  - `editor_to_dict` inchangé (le `.circ` stocke le comp_type tel quel, `U::...` compris) ; la fonction d'EXPORT netlist/Composant du module applique `type_reel` (type exporté = partie avant `::`, value = partie après si non vide, sinon value existante).

- [ ] **Step 1: Localiser l'export**

`grep -n "def " gui/schematic_io.py` et lire la fonction qui convertit
l'état éditeur en netlist/Composant pour l'analyse (utilisée par TabDraw
« Analyser »). C'est ELLE qui applique `type_reel`. Noter son nom exact
pour le test.

- [ ] **Step 2: Tests RED**

```python
# à ajouter au fichier de tests IO identifié
from gui.schematic_io import points_jonction, type_reel


def _mk_comp(id_, t, cx, cy):
    from gui.schematic_editor import CompInst
    return CompInst(id=id_, ref=f"{t}{id_}", comp_type=t, value="",
                    cx=cx, cy=cy)


def _mk_wire(i, a, pa, b, pb):
    from gui.schematic_editor import WireInst
    return WireInst(id=i, from_comp_id=a, from_pin=pa,
                    to_comp_id=b, to_pin=pb)


DEFS = {"R": {"w": 80, "h": 40, "pins": {"1": (-40, 0), "2": (40, 0)}}}


def test_type_reel():
    assert type_reel("U::NE555") == ("U", "NE555")
    assert type_reel("R") == ("R", "")


def test_points_jonction_trois_fils():
    # R1.2, R2.1, R3.1 au même point monde (200,100) -> 1 jonction.
    comps = {1: _mk_comp(1, "R", 160, 100), 2: _mk_comp(2, "R", 240, 100),
             3: _mk_comp(3, "R", 240, 180)}
    # NB : R3 tourné 90° mettrait sa broche ailleurs ; on garde rotation 0
    # et on fait CONVERGER les fils sur la broche 2 de R1 (200,100).
    wires = [_mk_wire(1, 1, "2", 2, "1"),
             _mk_wire(2, 1, "2", 3, "1"),
             _mk_wire(3, 2, "1", 3, "1")]
    pts = points_jonction(comps, wires, DEFS)
    assert (200, 100) in pts    # 2 extrémités de fils + ... >= 3
    # 2 fils seulement sur un point -> pas de jonction
    assert all(p != (280, 180) or False for p in pts)


def test_points_jonction_deux_fils_aucune():
    comps = {1: _mk_comp(1, "R", 160, 100), 2: _mk_comp(2, "R", 240, 100)}
    wires = [_mk_wire(1, 1, "2", 2, "1")]
    assert points_jonction(comps, wires, DEFS) == []
```

Run: `PYTHONUTF8=1 python -m pytest <fichier_io> -q -k "jonction or type_reel"`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implémenter**

Dans `gui/schematic_io.py` :

```python
def type_reel(comp_type: str) -> tuple:
    """@brief Sépare la convention "U::NE555" -> ("U", "NE555").

    Les puces catalogue de la palette portent leur référence dans le
    comp_type (spec 2026-07-15 §5) : le .circ les stocke tels quels, tout
    EXPORT (netlist/Composant) doit re-séparer. Type simple -> value "".
    """
    if "::" in comp_type:
        t, _, v = comp_type.partition("::")
        return t, v
    return comp_type, ""


def _pin_monde(comp, pin, defs):
    from gui.schematic_symbols import rotate_pin
    dx, dy = defs[comp.comp_type]["pins"][pin]
    rdx, rdy = rotate_pin(dx, dy, comp.rotation)
    return (comp.cx + rdx, comp.cy + rdy)


def points_jonction(comps, wires, defs) -> list:
    """@brief Points monde où >= 3 extrémités de fils coïncident (spec §4).

    Une extrémité = la broche (monde, rotation appliquée) d'un bout de fil.
    Deux fils qui se REJOIGNENT sur une même broche = 3 extrémités au même
    point (2 bouts de fils + implicitement la broche partagée compte via
    ses fils) — le seuil >= 3 évite le point sur une simple liaison à 2.
    """
    from collections import Counter
    compte = Counter()
    for w in wires:
        ca, cb = comps.get(w.from_comp_id), comps.get(w.to_comp_id)
        if not ca or not cb:
            continue
        compte[_pin_monde(ca, w.from_pin, defs)] += 1
        compte[_pin_monde(cb, w.to_pin, defs)] += 1
    return sorted(p for p, n in compte.items() if n >= 3)
```

Puis dans la fonction d'export identifiée au Step 1 : partout où
`comp.comp_type` devient le type exporté, appliquer :

```python
        t, v = type_reel(comp.comp_type)
        type_exporte = t
        value_exportee = v or comp.value
```

(et vérifier que `build_from_components`/l'import ne reçoit jamais de
`::` — les XML n'en contiennent pas ; aucun changement là).

- [ ] **Step 4: GREEN + non-régression**

Run: `PYTHONUTF8=1 python -m pytest <fichier_io> tests/test_schematic_symbols.py -q`
Expected: PASS + tests IO existants inchangés verts.

- [ ] **Step 5: Commit**

```bash
git add gui/schematic_io.py <fichier_io_tests>
git commit -m "feat(editeur): jonctions calculees (points_jonction) + convention U::REF a l'export"
```

---

### Task 3: Rendu des symboles dans l'éditeur (boucle visuelle)

**Files:**
- Modify: `gui/schematic_editor.py` — `_draw_comp` (~ligne 509)
- Test: `tests/test_schematic_editor.py` (créer, style test_island_viewport : fixture racine ctk, skip sans display)

**Interfaces:**
- Consomme : `primitives(comp_type, defn, rotation, value)` (Task 1).
- Produit : `_draw_comp` rend via primitives ; GND/VCC passent aussi par `primitives` (leurs traceurs sont dans schematic_symbols depuis Task 1 — SUPPRIMER les deux branches `if comp.comp_type == "GND"/"VCC"` locales).

- [ ] **Step 1: Test RED**

```python
# tests/test_schematic_editor.py
"""@file test_schematic_editor.py
@brief Editeur de schema (spec 2026-07-15) : rendu par primitives,
raccourcis, palette catalogue. Tk -> skip sans display.
"""
import pytest

ctk = pytest.importorskip("customtkinter")
import tkinter as tk                                    # noqa: E402

from gui.schematic_editor import SchematicEditor        # noqa: E402


@pytest.fixture
def editeur():
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("pas de display Tk")
    root.withdraw()
    ed = SchematicEditor(root)
    ed.pack()
    root.update_idletasks()
    yield ed
    root.destroy()


def _place(ed, t, cx, cy, value=""):
    """Place un composant par l'API interne (comme un clic en mode placement)."""
    ed._place_type = t
    ed._state = "placing"
    comp = ed._place_at(cx, cy) if hasattr(ed, "_place_at") else None
    # NOTE implémenteur : si aucune API interne directe n'existe, extraire
    # du handler de clic la pose effective dans une méthode _place_at(cx, cy)
    # -> CompInst (refactor minime, testable).
    return comp


def test_resistance_rendue_en_zigzag_pas_en_rectangle(editeur):
    c = _place(editeur, "R", 200, 200)
    items = editeur._canvas.find_withtag(f"comp_{c.id}")
    types = {editeur._canvas.type(i) for i in items}
    # Un zigzag = au moins une "line" à >= 8 points ; plus AUCUN rectangle.
    assert "rectangle" not in types
    lignes = [i for i in items if editeur._canvas.type(i) == "line"]
    assert any(len(editeur._canvas.coords(i)) >= 16 for i in lignes)


def test_gnd_rendu_par_primitives(editeur):
    c = _place(editeur, "GND", 300, 300)
    assert editeur._canvas.find_withtag(f"comp_{c.id}")
```

Run: `PYTHONUTF8=1 python -m pytest tests/test_schematic_editor.py -q`
Expected: FAIL (rectangle présent aujourd'hui / _place_at absent).

- [ ] **Step 2: Implémenter le rendu**

Dans `_draw_comp` :
1. Extraire si besoin `_place_at(cx, cy) -> CompInst` du handler de clic
   (pose + ref auto + redraw ; le handler l'appelle).
2. Remplacer les branches GND/VCC et le rectangle par :

```python
        prims = primitives(comp.comp_type, defn, rot, comp.value)
        for p in prims:
            if p[0] == "line":
                flat = [c for x, y in p[1] for c in self._w2s(comp.cx + x, comp.cy + y)]
                self._canvas.create_line(*flat, fill=color,
                                         width=max(1, int(p[2] * z)),
                                         joinstyle="round", tags=tag)
            elif p[0] == "polygon":
                flat = [c for x, y in p[1] for c in self._w2s(comp.cx + x, comp.cy + y)]
                self._canvas.create_polygon(
                    *flat, fill=color if p[2] else "",
                    outline=color, width=max(1, int(2 * z)), tags=tag)
            elif p[0] == "arc":
                x0, y0, x1, y1 = p[1]
                sx0, sy0 = self._w2s(comp.cx + x0, comp.cy + y0)
                sx1, sy1 = self._w2s(comp.cx + x1, comp.cy + y1)
                self._canvas.create_arc(sx0, sy0, sx1, sy1, start=p[2],
                                        extent=p[3], style="arc",
                                        outline=color,
                                        width=max(1, int(2 * z)), tags=tag)
            elif p[0] == "text":
                sx, sy = self._w2s(comp.cx + p[1][0], comp.cy + p[1][1])
                self._canvas.create_text(sx, sy, text=p[2], fill=color,
                                         font=("Consolas", max(5, int(p[3] * z))),
                                         anchor={"e": "e", "w": "w"}.get(p[4], "center"),
                                         tags=tag)
```

3. Ref au-dessus (`(0, -h2-10)` tourné), valeur en dessous (`(0, h2+10)`
   tourné), textes HORIZONTAUX (positions tournées, texte pas tourné,
   comme KiCad). Le nom de type n'est plus dessiné. Pastilles de broches
   et labels de broches (>2 pins) : conservés tels quels.
4. GND/VCC : leurs textes ("GND"/"VCC") restent (le traceur ne les émet
   pas — les garder côté _draw_comp comme les refs).

- [ ] **Step 3: GREEN + suite ciblée**

Run: `PYTHONUTF8=1 python -m pytest tests/test_schematic_editor.py tests/test_schematic_symbols.py -q`
Expected: PASS.

- [ ] **Step 4: BOUCLE VISUELLE (OBLIGATOIRE avant commit)**

Script scratchpad : monte l'éditeur, place R/C/L/D(LED rouge)/F/Q/M/U/
GND/VCC en grille, un R aux 4 rotations, zooms 0.5/1/2, capture PNG
(ImageGrab sur le canvas), REGARDE chaque PNG. Critères : symboles
reconnaissables, traits nets aux 3 zooms, rotations correctes, broches
alignées sur les symboles, refs/valeurs lisibles sans chevauchement.
Corriger les traceurs moches AVANT commit (retoucher schematic_symbols
est attendu ici — c'est la boucle de design).

- [ ] **Step 5: Suite complète + commit**

Run: `PYTHONUTF8=1 python -m pytest -q` → verte.

```bash
git add gui/schematic_editor.py gui/schematic_symbols.py tests/test_schematic_editor.py
git commit -m "feat(editeur): rendu vectoriel des symboles (zigzag, plaques, triangle AOP...) via schematic_symbols"
```

---

### Task 4: Câblage pro — jonctions, aperçu orthogonal, aimantation

**Files:**
- Modify: `gui/schematic_editor.py` — `_redraw_all` (~464), aperçu de câblage (~765), fin de câblage
- Test: `tests/test_schematic_editor.py` (étendre)

**Interfaces:**
- Consomme : `points_jonction` (Task 2).

- [ ] **Step 1: Tests RED**

```python
def test_jonction_dessinee_pour_trois_fils(editeur):
    a = _place(editeur, "R", 160, 100)
    b = _place(editeur, "R", 240, 100)
    c = _place(editeur, "R", 240, 180)
    for src, dst in [((a.id, "2"), (b.id, "1")),
                     ((a.id, "2"), (c.id, "1")),
                     ((b.id, "1"), (c.id, "1"))]:
        editeur._add_wire(src[0], src[1], dst[0], dst[1])
    # NOTE implémenteur : si _add_wire n'existe pas, extraire la création
    # de WireInst du handler de câblage (même approche que _place_at).
    editeur._redraw_all()
    assert editeur._canvas.find_withtag("jonction")


def test_apercu_cablage_orthogonal(editeur):
    a = _place(editeur, "R", 160, 100)
    editeur._start_wiring(a.id, "2")
    editeur._update_wire_preview(300, 220)   # point monde courant
    coords = editeur._canvas.coords(editeur._rubber_band)
    # L : 6 coordonnées (3 points), segments H puis V
    assert len(coords) == 6
    assert coords[1] == coords[3] or coords[0] == coords[2]
```

Run: RED (tags/méthodes absents).

- [ ] **Step 2: Implémenter**

1. `_redraw_all` : après les fils, `self._canvas.delete("jonction")` puis
   pour chaque `(wx, wy)` de `points_jonction(self._comps, self._wires,
   self._defs)` : disque plein rayon `4*z`, couleur du fil (`#475569`
   actuel — le remplacer par `theme.SCHEMA_COLORS["BUS"]`-équivalent SI la
   valeur est identique, sinon garder), tags `("jonction",)`. Idem après
   chaque `_redraw_wires_of`.
2. Aperçu : la ligne fantôme (~765) devient 3 points
   `(x0, y0, xm, y0, xm, ym)` — extraire `_update_wire_preview(wx, wy)`
   et `_start_wiring(comp_id, pin)` si le code est inline dans les
   handlers (refactor minimal, handlers deviennent des délégués).
3. Aimantation : dans `_update_wire_preview`, chercher la broche la plus
   proche (`_pin_at` existant ou équivalent — lire le fichier) à ≤ 12 px
   écran ; si trouvée, l'aperçu se termine sur ELLE et la broche reçoit un
   halo (`create_oval` outline BLUE, tags aperçu).

- [ ] **Step 3: GREEN + boucle visuelle**

Tests verts ; capture PNG d'un montage à jonction (3 fils sur une broche) —
le point de jonction doit être NET et sur la broche. Inspection avant commit.

- [ ] **Step 4: Suite complète + commit**

```bash
git add gui/schematic_editor.py tests/test_schematic_editor.py
git commit -m "feat(editeur): jonctions automatiques, apercu de fil orthogonal, aimantation aux broches"
```

---

### Task 5: Palette catalogue (« Puces réelles »)

**Files:**
- Modify: `gui/schematic_editor.py` — `_build_palette` (~322), `_compute_defs`, export/placement
- Test: `tests/test_schematic_editor.py` (étendre)

**Interfaces:**
- Consomme : `entrees_catalogue()` (existant), `def_puce` (Task 1), `type_reel` (Task 2).

- [ ] **Step 1: Tests RED**

```python
def test_placement_puce_catalogue(editeur):
    editeur._activer_catalogue("U", "NE555")   # à créer : prépare le placement
    c = editeur._place_at(400, 300)
    assert c.comp_type == "U::NE555"
    defn = editeur._defs["U::NE555"]
    assert len(defn["pins"]) == 8 and defn["fonctions"]["2"] == "TRIG"


def test_export_puce_catalogue_analysable(editeur, tmp_path):
    editeur._activer_catalogue("U", "NE555")
    editeur._place_at(400, 300)
    # Export via le chemin réel de TabDraw (identifier la fonction au
    # Step 2 : celle qui produit la netlist/le fichier d'analyse).
    comps = editeur.exporter_composants()   # nom à adapter au code réel
    u = next(c for c in comps if c.type == "U")
    assert u.value == "NE555"
    from circuit_analyzer.catalogue import identifier
    assert identifier(u.type, u.value)["nom"] == "NE555"
```

Run: RED.

- [ ] **Step 2: Implémenter**

1. `_activer_catalogue(type_, value)` : si `type_ == "U"` avec broches
   catalogue (`identifier(type_, value)["broches"]`), enregistrer
   `self._defs[f"U::{value}"] = def_puce(value, broches)` (idempotent) et
   passer en mode placement avec `_place_type = f"U::{value}"` ; sinon
   (Q/M/D/LED) : `_place_type = type_` et la value par défaut du placement
   devient la référence (adapter `_place_at` pour accepter une value
   imposée — les LED posent `value="LED rouge"...`).
2. Palette : sous les types intégrés, section « Puces réelles » —
   liste déroulante (tk.Listbox scrollable dans le cadre palette, style
   tokens) alimentée par `sorted(entrees_catalogue(), key=lambda e: e[1])`,
   simple clic → `_activer_catalogue`. (PAS un bouton par entrée : ~30
   entrées, la palette doit rester compacte.)
3. Export : appliquer `type_reel` (Task 2) dans le chemin d'export réel —
   si Task 2 l'a déjà fait dans schematic_io, vérifier que le chemin
   TabDraw y passe ; sinon l'y brancher.
4. `.circ` : `editor_to_dict` stocke déjà comp_type tel quel ; à la
   RELECTURE d'un `.circ` contenant `U::NE555`, `_compute_defs` doit
   régénérer la def dynamique (au chargement : pour chaque type `::`
   inconnu, `def_puce` depuis `identifier`) — sinon KeyError. Test rapide
   à ajouter : save/load d'un état avec puce.

- [ ] **Step 3: GREEN + boucle visuelle**

Capture PNG : NE555 posé (boîtier à encoche, 8 broches libellées
`n FONCTION`), 74HC00 (14 broches), LED rouge (symbole diode + flèches).
Inspection avant commit.

- [ ] **Step 4: Suite complète + commit**

```bash
git add gui/schematic_editor.py tests/test_schematic_editor.py
git commit -m "feat(editeur): puces reelles du catalogue placables depuis la palette (defs DIP dynamiques)"
```

---

### Task 6: Raccourcis éditeur (molette, pan, sélection rectangle, R, Échap)

**Files:**
- Modify: `gui/schematic_editor.py` — bindings, machine à états, `_selected_id` → `_selected_ids`
- Test: `tests/test_schematic_editor.py` (étendre)

- [ ] **Step 1: Tests RED**

```python
def test_zoom_molette_centre_sur_le_curseur(editeur):
    editeur._zoom_wheel(1.25, sx=400, sy=300)   # API interne à créer
    wx0, wy0 = editeur._s2w(400, 300)
    editeur._zoom_wheel(1.25, sx=400, sy=300)
    wx1, wy1 = editeur._s2w(400, 300)
    assert abs(wx0 - wx1) < 1e-6 and abs(wy0 - wy1) < 1e-6


def test_selection_rectangle_et_suppression_groupee(editeur):
    a = _place(editeur, "R", 100, 100)
    b = _place(editeur, "C", 200, 100)
    editeur._select_in_rect(60, 60, 260, 140)   # API interne à créer
    assert editeur._selected_ids == {a.id, b.id}
    editeur._delete_selection()
    assert not editeur._comps


def test_escape_annule_le_mode(editeur):
    editeur._place_type = "R"; editeur._state = "placing"
    editeur._on_escape()
    assert editeur._state == "idle" and editeur._place_type is None


def test_r_tourne_la_selection(editeur):
    a = _place(editeur, "R", 100, 100)
    editeur._selected_ids = {a.id}
    editeur._rotate_selection()
    assert editeur._comps[a.id].rotation == 90
```

Run: RED.

- [ ] **Step 2: Implémenter**

1. **Molette** : `_zoom_wheel(facteur, sx, sy)` — le point monde sous
   (sx, sy) doit rester sous (sx, sy). L'éditeur actuel n'a pas d'offset
   de vue (`_w2s = w*zoom`) : introduire `self._ox, self._oy` (offset
   écran) dans `_w2s`/`_s2w` (`sx = wx*z + ox`), initialisés à 0 — TOUS
   les usages passent déjà par ces deux fonctions (vérifier par grep
   qu'aucun calcul n'inline le zoom). Formule :
   `ox' = sx - (sx - ox) * (z'/z)` (idem oy). Bind `<MouseWheel>`
   (Windows : `event.delta/120` → facteur 1.1^n). Boutons zoom existants :
   passer par `_zoom_wheel` centré sur le centre du canvas.
2. **Pan** : `<Button-2>` press/motion/release → décalage de `_ox/_oy`,
   curseur "fleur" pendant le pan.
3. **Sélection multiple** : `_selected_id` devient `_selected_ids: set`
   (adapter TOUS les usages — grep `_selected_id` ; le clic simple
   sélectionne {id}, le clic sur vide vide le set). Glisser sur fond vide
   en idle → rectangle (`create_rectangle` pointillé, tags "selrect") ;
   au relâchement `_select_in_rect(x0, y0, x1, y1)` (coords monde,
   composants dont le centre est dans le rect). `_delete_selection()`
   supprime composants + leurs fils (undo pushé une fois). Drag d'un
   composant sélectionné → déplace tout le set (offsets relatifs).
4. **R** : `_rotate_selection()` (+90° chaque composant du set) ; en mode
   placing, R tourne la rotation de pose (existant à normaliser).
5. **Échap** : `_on_escape()` — placing→idle, wiring→cancel, sélection
   vidée, aperçus effacés. Bind `<Escape>`.
6. Légende raccourcis de la palette mise à jour (R, molette, clic-milieu,
   Échap, Suppr).

- [ ] **Step 3: GREEN + suite complète + boucle visuelle**

Tests verts ; suite complète verte ; capture PNG après zoom molette x2 et
pan (le montage reste net et positionné où attendu). Inspection.

- [ ] **Step 4: Commit**

```bash
git add gui/schematic_editor.py tests/test_schematic_editor.py
git commit -m "feat(editeur): zoom curseur, pan clic-milieu, selection rectangle multi, R/Echap unifies"
```

---

### Task 7: Retrait onglet Saisie + clôture

**Files:**
- Modify: `gui/app_window.py` (retrait onglet)
- Delete: `gui/tab_quick_entry.py`, `tests/test_tab_quick_entry.py`
- Modify: `.superpowers/sdd/progress.md` (append)

- [ ] **Step 1: Test RED (adapter, pas supprimer aveuglément)**

Le test d'intégration `test_app_window_a_l_onglet_saisie` vit dans
`tests/test_tab_quick_entry.py` (qui sera supprimé). AVANT suppression,
créer `tests/test_app_window.py` avec le contrat inverse :

```python
# tests/test_app_window.py
"""@file test_app_window.py
@brief Contrat de la fenetre principale : 4 onglets (l'onglet Saisie a ete
retire au profit de l'editeur niveau KiCad, spec 2026-07-15 §7)."""
import pytest

ctk = pytest.importorskip("customtkinter")

from gui.app_window import AppWindow


def test_quatre_onglets_sans_saisie():
    try:
        app = AppWindow()
    except Exception:
        pytest.skip("pas de display Tk")
    try:
        assert len(app._frames) == 4
        libelles = [b._lbl.cget("text") for b in app._nav_btns]
        assert "Saisie" not in libelles
    finally:
        app.root.destroy()
```

Run: RED (5 onglets aujourd'hui).

- [ ] **Step 2: Retirer**

`git rm gui/tab_quick_entry.py tests/test_tab_quick_entry.py` ; dans
`gui/app_window.py` retirer l'import TabQuickEntry, l'entrée nav
« Saisie », `tab_s`/`self._tab_s`, la 5e frame ; docstrings 5→4 onglets.
NE PAS toucher : `circuit_analyzer/saisie.py`, `tests/test_saisie.py`,
`tests/test_saisie_fondations.py`, `default_value`, `entrees_catalogue`,
`lire_xml(alias_catalogue=...)`.

- [ ] **Step 3: GREEN + suite complète**

Run: `PYTHONUTF8=1 python -m pytest tests/test_app_window.py -q` → PASS.
Run: `PYTHONUTF8=1 python -m pytest -q` → verte intégrale.

- [ ] **Step 4: Boucle visuelle finale (exigence boss)**

Script scratchpad : AppWindow réelle → onglet Dessiner → placer un montage
complet (R + C + Q + AOP + NE555 catalogue + GND/VCC + fils avec une
jonction) → captures PNG de l'éditeur + des 4 onglets. INSPECter : symboles
réels partout, jonction visible, palette avec section Puces réelles, nav à
4 onglets, aucun onglet cassé. Tout défaut = fix TDD avant commit final.

- [ ] **Step 5: Ledger + commit**

Append `.superpowers/sdd/progress.md` : section chantier éditeur KiCad
(commits, suite, PNG inspectés).

```bash
git add gui/app_window.py .superpowers/sdd/progress.md tests/test_app_window.py
git commit -m "feat(editeur): retrait de l'onglet Saisie (remplace par l'editeur niveau KiCad) - retour a 4 onglets"
```

---

## Self-review (fait à l'écriture du plan)

- Spec §3→T1+T3, §4→T2+T4, §5→T1(def_puce)+T2(U::)+T5, §6→T6, §7→T7,
  §8 tests 1-4→T1, 5-6→T2, 7→T5, 8-9→T6, 10→T5/T7, 11→T7 ; boucle
  visuelle dans T3/T4/T5/T6/T7.
- Les APIs internes `_place_at`/`_add_wire`/`_start_wiring`/
  `_update_wire_preview`/`_zoom_wheel`/`_select_in_rect` sont des
  EXTRACTIONS de handlers existants (testabilité) — chaque tâche le dit
  explicitement, l'implémenteur lit le handler réel avant d'extraire.
- Les coordonnées des traceurs (T1) sont un point de départ : la boucle
  visuelle de T3 est LE juge, retoucher schematic_symbols y est prévu.
- `test_points_jonction_trois_fils` : le point (200,100) reçoit 4
  extrémités (2 fils × 2 bouts convergents + ...) — le seuil ≥3 est bien
  franchi ; l'assertion secondaire redondante a été laissée simple.
