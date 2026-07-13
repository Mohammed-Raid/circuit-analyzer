# Grille déterministe + routage Manhattan — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Réécrire l'assemblage des îlots (placement + fils inter-étages) sur une grille absolue déterministe avec routage Manhattan sans collision, Vue dépliée par défaut, thème centralisé et cache de figures.

**Architecture:** Deux nouveaux modules purs (`gui/schema_grid.py` calcule les positions/obstacles, `gui/schema_router.py` route en A* orthogonal) consommés uniquement par `gui/circuit_viewer.py`, seul module autorisé à toucher schemdraw/matplotlib/TkAgg. L'intérieur des drawers de montage (audités A1-A5/V1-V5) ne change pas.

**Tech Stack:** Python 3.14 local (`python`), schemdraw==0.22 (pin `<0.23`), matplotlib/TkAgg, pytest.

**Spec:** `docs/superpowers/specs/2026-07-13-grille-deterministe-routage-manhattan-design.md`

## Global Constraints

- `PYTHONUTF8=1` obligatoire devant chaque commande pytest/python (shell cp1252).
- schemdraw pinné `>=0.18,<0.23` — ne pas toucher requirements.
- Canvas des schémas reste CLAIR : `SCH_BG = "#fafafa"` (directive boss, invariant).
- `gui/schema_grid.py` et `gui/schema_router.py` : AUCUN import schemdraw/matplotlib/tkinter (test dédié).
- Constantes de grille (spec §3.1) : `PAS=0.5`, `MARGE=1.0`, `CANAL_H=2.0`, `CANAL_V=2.0`, `X0=4.5`, `PENALITE_COUDE=1.5` (=3·PAS).
- L'intérieur des drawers de montage ne bouge pas ; seules leurs ORIGINES changent.
- Les tests existants (1583, dont 244 contrats labels, audits A1-A5/V1-V5) doivent rester verts à CHAQUE tâche.
- Commits en FRANÇAIS, JAMAIS de footer "Co-Authored-By"/"Generated with". `git add` UNIQUEMENT tes fichiers (jamais `-A` — `docs.rar` est un fichier du boss, intouchable).
- Rien n'est poussé (le boss pousse lui-même).

---

### Task 1: gui/schema_grid.py — grille absolue déterministe

**Files:**
- Create: `gui/schema_grid.py`
- Test: `tests/test_schema_grid.py`

**Interfaces:**
- Consomme : rien (module pur ; les constantes viennent de `gui.theme.SCHEMA_DIMS`, créé en Task 3 — d'ici là, définies localement avec un commentaire `# déplacées vers theme.SCHEMA_DIMS en Task 3`).
- Produit (utilisé par Tasks 2, 4, 5) :
  - `Rect(x0, y0, x1, y1)` dataclass frozen, méthodes `contient_strict(x, y) -> bool`, `dilate(m) -> Rect`
  - `EtageMesure(cle: str, colonne: int, bande: int, largeur: float, hauteur: float, ancrage_x: float, ancrage_y: float)` dataclass frozen
  - `PlanGrille(origines: dict[str, tuple], obstacles: list[Rect], slots: dict[str, Rect])` dataclass
  - `snap(v) -> float`, `snap_ceil(v) -> float`
  - `poser(etages: list[EtageMesure]) -> PlanGrille`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_schema_grid.py
"""@file test_schema_grid.py
@brief Contrats de la grille absolue (spec 2026-07-13 §3) : snap, formules
x(c)/y(b), obstacles = slots, déterminisme strict, pureté d'import.
"""
import subprocess
import sys

from gui.schema_grid import (PAS, MARGE, CANAL_H, CANAL_V, X0,
                             EtageMesure, PlanGrille, Rect, poser,
                             snap, snap_ceil)


def _etages_2x1():
    # Chaîne de 2 étages, une bande : largeurs 7.3 et 4.1, hauteurs 5.0/3.0.
    return [
        EtageMesure("A", colonne=0, bande=0, largeur=7.3, hauteur=5.0,
                    ancrage_x=1.2, ancrage_y=0.625),
        EtageMesure("B", colonne=1, bande=0, largeur=4.1, hauteur=3.0,
                    ancrage_x=0.4, ancrage_y=-0.625),
    ]


def test_snap_et_snap_ceil():
    assert snap(1.24) == 1.0
    assert snap(1.26) == 1.5
    assert snap_ceil(7.3 + 2 * MARGE) == 9.5   # ceil(9.3/0.5)*0.5
    assert snap_ceil(4.0) == 4.0               # déjà multiple


def test_formules_x_colonne():
    plan = poser(_etages_2x1())
    # L(0) = snap_ceil(7.3 + 2*MARGE) = 9.5 ; x(0)=X0 ; x(1)=X0+9.5+CANAL_H
    assert plan.slots["A"].x0 == X0
    assert plan.slots["B"].x0 == X0 + 9.5 + CANAL_H
    # origine = (x(c) + MARGE + ancrage_x, y(b) + ancrage_y), snappée
    ox, oy = plan.origines["A"]
    assert ox == snap(X0 + MARGE + 1.2)
    assert oy == snap(0.0 + 0.625)


def test_formules_y_bande():
    etages = [
        EtageMesure("H", 0, 0, largeur=4.0, hauteur=6.0, ancrage_x=0, ancrage_y=0),
        EtageMesure("B", 0, 1, largeur=4.0, hauteur=3.0, ancrage_x=0, ancrage_y=0),
    ]
    plan = poser(etages)
    # H(0)=6.0 ; y(1) = y(0) - H(0) - CANAL_V = -8.0
    assert plan.origines["B"][1] == snap(-6.0 - CANAL_V)


def test_tout_est_sur_la_grille():
    plan = poser(_etages_2x1())
    pts = list(plan.origines.values())
    for r in plan.obstacles:
        pts += [(r.x0, r.y0), (r.x1, r.y1)]
    for x, y in pts:
        assert abs(x / PAS - round(x / PAS)) < 1e-9, (x, y)
        assert abs(y / PAS - round(y / PAS)) < 1e-9, (x, y)


def test_un_obstacle_par_etage_couvre_le_slot():
    plan = poser(_etages_2x1())
    assert len(plan.obstacles) == 2
    assert plan.slots["A"] in plan.obstacles


def test_deterministe_meme_en_ordre_inverse():
    a = poser(_etages_2x1())
    b = poser(list(reversed(_etages_2x1())))
    assert a == b


def test_import_sans_backend_graphique():
    # Le module doit s'importer sans tirer matplotlib/schemdraw/tkinter.
    code = ("import sys; import gui.schema_grid; "
            "interdits = [m for m in ('matplotlib', 'schemdraw', 'tkinter') "
            "if m in sys.modules]; "
            "sys.exit(1 if interdits else 0)")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert r.returncode == 0, r.stderr
```

- [ ] **Step 2: Vérifier l'échec**

Run: `PYTHONUTF8=1 python -m pytest tests/test_schema_grid.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gui.schema_grid'`

- [ ] **Step 3: Implémenter le module**

```python
# gui/schema_grid.py
"""@file schema_grid.py
@brief Grille absolue deterministe pour l'ASSEMBLAGE des ilots (spec
2026-07-13 §3). Module PUR : aucune dependance schemdraw/matplotlib/tkinter ;
entrees = mesures fournies par l'appelant, sorties = positions/rectangles.
"""
import math
from dataclasses import dataclass, field

# Constantes de grille — déplacées vers theme.SCHEMA_DIMS en Task 3
# (schema_grid les REimportera depuis theme à ce moment-là).
PAS = 0.5
MARGE = 1.0
CANAL_H = 2.0
CANAL_V = 2.0
X0 = 4.5


def snap(v: float) -> float:
    """@brief Arrondit au multiple de PAS le plus proche."""
    return round(v / PAS) * PAS


def snap_ceil(v: float) -> float:
    """@brief Arrondit au multiple de PAS superieur (jamais plus petit)."""
    return math.ceil(v / PAS - 1e-9) * PAS


@dataclass(frozen=True)
class Rect:
    """@brief Rectangle axis-aligned (x0<=x1, y0<=y1) en unites schemdraw."""
    x0: float
    y0: float
    x1: float
    y1: float

    def contient_strict(self, x: float, y: float) -> bool:
        """@brief Interieur STRICT (la frontiere reste praticable, spec §4.1)."""
        return self.x0 < x < self.x1 and self.y0 < y < self.y1

    def dilate(self, m: float) -> "Rect":
        return Rect(self.x0 - m, self.y0 - m, self.x1 + m, self.y1 + m)


@dataclass(frozen=True)
class EtageMesure:
    """@brief Mesures d'un etage (bbox du drawer, dry-run cote appelant).

    @param cle Identifiant stable (ref du montage, ex. "U1").
    @param ancrage_x Decalage origine-drawer -> bord gauche de sa bbox.
    @param ancrage_y Decalage vertical (oy_for du montage).
    """
    cle: str
    colonne: int
    bande: int
    largeur: float
    hauteur: float
    ancrage_x: float
    ancrage_y: float


@dataclass
class PlanGrille:
    """@brief Sortie de poser() : origines snappees + obstacles (slots)."""
    origines: dict = field(default_factory=dict)
    obstacles: list = field(default_factory=list)
    slots: dict = field(default_factory=dict)


def poser(etages) -> PlanGrille:
    """@brief Applique les formules de la spec §3.2.

    L(c)  = snap_ceil(max largeur de la colonne + 2*MARGE)
    x(0)  = X0 ; x(c) = x(c-1) + L(c-1) + CANAL_H
    H(b)  = snap_ceil(max hauteur de la bande)
    y(0)  = 0  ; y(b) = y(b-1) - H(b-1) - CANAL_V
    origine(e) = (snap(x(c) + MARGE + ancrage_x), snap(y(b) + ancrage_y))
    Obstacle(e) = slot complet [x(c), x(c)+L(c)] x [y(b)-H(b), y(b)].

    Deterministe : tri stable des etages par (colonne, bande, cle) ; aucune
    dependance a l'ordre d'entree.
    """
    etages = sorted(etages, key=lambda e: (e.colonne, e.bande, e.cle))
    if not etages:
        return PlanGrille()

    colonnes = sorted({e.colonne for e in etages})
    bandes = sorted({e.bande for e in etages})
    L = {c: snap_ceil(max(e.largeur for e in etages if e.colonne == c)
                      + 2 * MARGE) for c in colonnes}
    H = {b: snap_ceil(max(e.hauteur for e in etages if e.bande == b))
         for b in bandes}

    x = {}
    cour = X0
    for c in colonnes:
        x[c] = cour
        cour += L[c] + CANAL_H
    y = {}
    cour = 0.0
    for b in bandes:
        y[b] = cour
        cour -= H[b] + CANAL_V

    plan = PlanGrille()
    for e in etages:
        plan.origines[e.cle] = (snap(x[e.colonne] + MARGE + e.ancrage_x),
                                snap(y[e.bande] + e.ancrage_y))
        slot = Rect(x[e.colonne], snap(y[e.bande] - H[e.bande]),
                    snap(x[e.colonne] + L[e.colonne]), y[e.bande])
        plan.slots[e.cle] = slot
        plan.obstacles.append(slot)
    return plan
```

- [ ] **Step 4: Vérifier le vert**

Run: `PYTHONUTF8=1 python -m pytest tests/test_schema_grid.py -q`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add gui/schema_grid.py tests/test_schema_grid.py
git commit -m "feat(grille): schema_grid - grille absolue deterministe de l'assemblage"
```

---

### Task 2: gui/schema_router.py — A* Manhattan avec réservation d'arêtes

**Files:**
- Create: `gui/schema_router.py`
- Test: `tests/test_schema_router.py`

**Interfaces:**
- Consomme : `Rect`, `PAS`, `snap` de `gui.schema_grid` (Task 1).
- Produit (utilisé par Tasks 4, 5) :
  - `router(nets: list[tuple[str, tuple, tuple]], obstacles: list[Rect]) -> dict[str, list[tuple] | None]`
    — `nets` = [(nom, (x_dep, y_dep), (x_arr, y_arr)), ...] routés DANS L'ORDRE de la liste (l'appelant trie) ; polyligne = points consécutifs alignés en x ou y, segments colinéaires fusionnés ; `None` = échec (repli appelant).
  - `PENALITE_COUDE = 1.5`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_schema_router.py
"""@file test_schema_router.py
@brief Contrats du routeur Manhattan (spec 2026-07-13 §4) : orthogonalite,
evitement d'obstacles, non-chevauchement colineaire, repli None, purete.
"""
import subprocess
import sys

from gui.schema_grid import PAS, Rect
from gui.schema_router import router


def _orthogonale(poly):
    return all(a[0] == b[0] or a[1] == b[1] for a, b in zip(poly, poly[1:]))


def _aretes(poly):
    """Arêtes unitaires (pas PAS) d'une polyligne, normalisées."""
    out = set()
    for (xa, ya), (xb, yb) in zip(poly, poly[1:]):
        n = round(max(abs(xb - xa), abs(yb - ya)) / PAS)
        dx, dy = (xb - xa) / n, (yb - ya) / n
        for k in range(n):
            p = (round(xa + k * dx, 6), round(ya + k * dy, 6))
            q = (round(xa + (k + 1) * dx, 6), round(ya + (k + 1) * dy, 6))
            out.add((min(p, q), max(p, q)))
    return out


def test_route_directe_sans_obstacle():
    res = router([("n1", (0.0, 0.0), (4.0, 0.0))], [])
    poly = res["n1"]
    assert poly[0] == (0.0, 0.0) and poly[-1] == (4.0, 0.0)
    assert _orthogonale(poly)
    assert len(poly) == 2  # segments colinéaires fusionnés


def test_contourne_un_obstacle():
    mur = Rect(1.0, -3.0, 3.0, 3.0)
    res = router([("n1", (0.0, 0.0), (4.0, 0.0))], [mur])
    poly = res["n1"]
    assert poly is not None and _orthogonale(poly)
    # Aucun point intermédiaire strictement dans l'obstacle.
    for (xa, ya), (xb, yb) in zip(poly, poly[1:]):
        mx, my = (xa + xb) / 2, (ya + yb) / 2
        assert not mur.contient_strict(mx, my), poly


def test_depart_arrivee_sur_frontiere_obstacle():
    # Cas nominal des ports : le point de départ est SUR le bord d'un slot.
    slot = Rect(0.0, -2.0, 2.0, 2.0)
    res = router([("n1", (2.0, 0.0), (6.0, 0.0))], [slot])
    assert res["n1"] is not None


def test_deux_nets_ne_partagent_pas_d_arete():
    # Deux nets de même départ→même couloir : le 2e doit dévier.
    nets = [("a", (0.0, 0.0), (6.0, 0.0)),
            ("b", (0.0, -0.5), (6.0, -0.5))]
    res = router(nets, [])
    assert res["a"] and res["b"]
    assert not (_aretes(res["a"]) & _aretes(res["b"]))


def test_croisement_perpendiculaire_autorise():
    nets = [("h", (0.0, 0.0), (4.0, 0.0)),
            ("v", (2.0, -2.0), (2.0, 2.0))]
    res = router(nets, [])
    assert res["h"] and res["v"]   # le croisement en (2,0) est légal


def test_grille_saturee_renvoie_none():
    # Départ complètement muré -> pas de chemin -> None (repli appelant).
    dep = (0.0, 0.0)
    murs = [Rect(-1.0, -1.0, 1.0, -0.5), Rect(-1.0, 0.5, 1.0, 1.0),
            Rect(-1.0, -1.0, -0.5, 1.0), Rect(0.5, -1.0, 1.0, 1.0)]
    res = router([("n1", dep, (8.0, 0.0))], murs)
    assert res["n1"] is None


def test_import_sans_backend_graphique():
    code = ("import sys; import gui.schema_router; "
            "sys.exit(1 if any(m in sys.modules for m in "
            "('matplotlib', 'schemdraw', 'tkinter')) else 0)")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert r.returncode == 0, r.stderr
```

- [ ] **Step 2: Vérifier l'échec**

Run: `PYTHONUTF8=1 python -m pytest tests/test_schema_router.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gui.schema_router'`

- [ ] **Step 3: Implémenter le routeur**

```python
# gui/schema_router.py
"""@file schema_router.py
@brief Routage Manhattan A* pour les fils inter-etages (spec 2026-07-13 §4).
Module PUR (aucun import graphique). Noeuds = grille au pas PAS ; interdits =
interieur STRICT des obstacles ; cout = PAS par arete + PENALITE_COUDE par
virage ; les aretes des nets deja routes sont reservees (pas de chevauchement
colineaire ; croisement perpendiculaire libre).
"""
import heapq

from gui.schema_grid import PAS, Rect, snap

PENALITE_COUDE = 1.5   # 3 * PAS — favorise les longs segments droits
_MAX_NOEUDS = 20000    # garde-fou : au-dela, on abandonne (repli appelant)
_DIRS = ((PAS, 0.0), (-PAS, 0.0), (0.0, PAS), (0.0, -PAS))


def _cle(p):
    return (round(p[0], 6), round(p[1], 6))


def _arete(p, q):
    a, b = _cle(p), _cle(q)
    return (a, b) if a <= b else (b, a)


def _zone(nets, obstacles):
    """@brief Bbox englobante (ports + obstacles) dilatee de 2 canaux."""
    xs, ys = [], []
    for _n, dep, arr in nets:
        xs += [dep[0], arr[0]]; ys += [dep[1], arr[1]]
    for r in obstacles:
        xs += [r.x0, r.x1]; ys += [r.y0, r.y1]
    m = 4 * PAS
    return Rect(snap(min(xs)) - m, snap(min(ys)) - m,
                snap(max(xs)) + m, snap(max(ys)) + m)


def _fusionner(points):
    """@brief Supprime les points intermediaires colineaires (garde un point
    seulement si la direction change)."""
    if len(points) < 3:
        return points
    res = [points[0]]
    for i in range(1, len(points) - 1):
        dx1 = points[i][0] - points[i - 1][0]
        dy1 = points[i][1] - points[i - 1][1]
        dx2 = points[i + 1][0] - points[i][0]
        dy2 = points[i + 1][1] - points[i][1]
        if (dx1 == 0) != (dx2 == 0) or (dy1 == 0) != (dy2 == 0):
            res.append(points[i])
    res.append(points[-1])
    return res


def _astar(dep, arr, obstacles, zone, reservees):
    """@brief A* 4-directions ; etat = (noeud, direction d'arrivee)."""
    dep, arr = _cle(dep), _cle(arr)

    def h(p):
        return abs(p[0] - arr[0]) + abs(p[1] - arr[1])

    def praticable(p, exempt):
        if not (zone.x0 <= p[0] <= zone.x1 and zone.y0 <= p[1] <= zone.y1):
            return False
        if p in (dep, arr):
            return True
        return not any(r.contient_strict(p[0], p[1]) for r in obstacles)

    ouverts = [(h(dep), 0.0, dep, None, None)]  # f, g, noeud, dir, parent-etat
    vus = {}
    parents = {}
    explores = 0
    while ouverts:
        f, g, p, dirn, parent = heapq.heappop(ouverts)
        etat = (p, dirn)
        if etat in vus and vus[etat] <= g:
            continue
        vus[etat] = g
        parents[etat] = parent
        explores += 1
        if explores > _MAX_NOEUDS:
            return None
        if p == arr:
            chemin = [p]
            while parents[etat] is not None:
                etat = parents[etat]
                chemin.append(etat[0])
            return list(reversed(chemin))
        for dx, dy in _DIRS:
            q = _cle((p[0] + dx, p[1] + dy))
            if not praticable(q, (dep, arr)):
                continue
            # Arete bloquee si son milieu est STRICTEMENT dans un obstacle
            mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
            if any(r.contient_strict(mx, my) for r in obstacles):
                continue
            if _arete(p, q) in reservees:
                continue
            ng = g + PAS + (PENALITE_COUDE if dirn and dirn != (dx, dy) else 0.0)
            netat = (q, (dx, dy))
            if netat in vus and vus[netat] <= ng:
                continue
            heapq.heappush(ouverts, (ng + h(q), ng, q, (dx, dy), (p, dirn)))
    return None


def router(nets, obstacles):
    """@brief Route chaque net dans l'ordre de la liste (spec §4.2).

    @param nets [(nom, depart, arrivee), ...] — depart/arrivee snappes PAS.
    @param obstacles list[Rect] (slots d'etages + stubs Z locales).
    @return dict nom -> polyligne (coudes fusionnes) | None si echec.
    """
    if not nets:
        return {}
    zone = _zone(nets, obstacles)
    reservees = set()
    resultats = {}
    for nom, dep, arr in nets:
        chemin = _astar(dep, arr, obstacles, zone, reservees)
        if chemin is None:
            resultats[nom] = None
            continue
        for p, q in zip(chemin, chemin[1:]):
            reservees.add(_arete(p, q))
        resultats[nom] = _fusionner(chemin)
    return resultats
```

- [ ] **Step 4: Vérifier le vert**

Run: `PYTHONUTF8=1 python -m pytest tests/test_schema_router.py tests/test_schema_grid.py -q`
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add gui/schema_router.py tests/test_schema_router.py
git commit -m "feat(routage): schema_router - A* Manhattan avec reservation d'aretes"
```

---

### Task 3: Thème centralisé — SCHEMA_COLORS / SCHEMA_DIMS + dé-hardcodage

**Files:**
- Modify: `gui/theme.py` (fin de fichier)
- Modify: `gui/fonts.py` (fin de fichier)
- Modify: `gui/circuit_viewer.py:35-60` (bloc couleurs) + tous les littéraux hex du fichier
- Modify: `gui/impedance_schematic.py`, `gui/logic_schematic.py`, `gui/puce_schematic.py` (littéraux hex)
- Modify: `gui/schema_grid.py` (réimporter PAS/MARGE/CANAL_H/CANAL_V/X0 depuis theme)
- Test: `tests/test_theme_schemas.py`

**Interfaces:**
- Produit : `theme.SCHEMA_COLORS` (MappingProxyType), `theme.SCHEMA_DIMS` (MappingProxyType), `fonts.SCHEMA_FONTSIZES` (dict figé).
- RENDU STRICTEMENT IDENTIQUE : pur renommage de constantes, AUCUNE valeur ne change. Les 244 contrats labels le prouvent.

- [ ] **Step 1: Écrire le test grep qui échoue**

```python
# tests/test_theme_schemas.py
"""@file test_theme_schemas.py
@brief Interdit tout litteral couleur hex dans les modules de dessin des
schemas (spec 2026-07-13 §6) : la source unique est gui/theme.py.
Liste d'exclusions VIDE par contrat (meme regle que test_puces_resolution).
"""
import re
from pathlib import Path

import pytest

GUI = Path(__file__).resolve().parent.parent / "gui"
MODULES = ["circuit_viewer.py", "impedance_schematic.py",
           "logic_schematic.py", "puce_schematic.py"]
HEX = re.compile(r'["\']#[0-9a-fA-F]{3,8}["\']')


@pytest.mark.parametrize("nom", MODULES)
def test_aucun_hex_en_dur(nom):
    src = (GUI / nom).read_text(encoding="utf-8")
    lignes = [(i + 1, l) for i, l in enumerate(src.splitlines())
              if HEX.search(l)]
    assert not lignes, f"{nom}: littéraux hex interdits -> {lignes[:10]}"


def test_tokens_schemas_presents_et_figes():
    from types import MappingProxyType
    from gui import theme
    assert isinstance(theme.SCHEMA_COLORS, MappingProxyType)
    assert isinstance(theme.SCHEMA_DIMS, MappingProxyType)
    # Invariant boss : canvas des schemas CLAIR.
    assert theme.SCHEMA_COLORS["SCH_BG"] == "#fafafa"
    assert theme.SCHEMA_DIMS["PAS"] == 0.5
    assert theme.SCHEMA_DIMS["X0"] == 4.5


def test_grid_lit_ses_constantes_dans_theme():
    from gui import schema_grid, theme
    assert schema_grid.PAS is theme.SCHEMA_DIMS["PAS"] or \
        schema_grid.PAS == theme.SCHEMA_DIMS["PAS"]
```

- [ ] **Step 2: Vérifier l'échec**

Run: `PYTHONUTF8=1 python -m pytest tests/test_theme_schemas.py -q`
Expected: FAIL — hex présents dans les 4 modules + `AttributeError: SCHEMA_COLORS`

- [ ] **Step 3: Ajouter les tokens à theme.py et fonts.py**

Ajouter à la fin de `gui/theme.py` :

```python
from types import MappingProxyType

# ── Schémas (canvas CLAIR — invariant boss : ne jamais assombrir) ──────────
SCHEMA_COLORS = MappingProxyType({
    "SCH_BG":     "#fafafa",   # fond canvas schémas (CLAIR, invariant)
    "WIRE":       "#1e293b",   # fils/encre
    "BUS":        "#475569",   # bus/nets satellites
    "Z_FILL":     "#dbeafe",   # remplissage boîte Z
    "Z_EDGE":     BLUE_HOVER,  # bord boîte Z
    "OPAMP_FILL": "#eef2ff",   # triangle AOP
    "TITRE":      OVERLAY,     # rôle de l'étage
    "GAIN":       "#0f766e",   # gain (teal)
    "LEGENDE":    "#64748b",   # légendes/notes discrètes
    "COMP": MappingProxyType({
        "R": "#1d4ed8", "C": "#0891b2", "L": "#059669", "D": "#dc2626",
        "Q": "#7c3aed", "M": "#6d28d9", "U": "#b45309", "F": "#374151",
    }),
})

SCHEMA_DIMS = MappingProxyType({
    "PAS": 0.5, "MARGE": 1.0, "CANAL_H": 2.0, "CANAL_V": 2.0,
    "X0": 4.5, "PENALITE_COUDE": 1.5,
})
```

Ajouter à la fin de `gui/fonts.py` :

```python
# Tailles de police des schémas (valeurs historiques, juste nommées).
SCHEMA_FONTSIZES = {"label": 9, "titre": 11, "gain": 8, "legende": 9}
```

- [ ] **Step 4: Dé-hardcoder les 4 modules de dessin**

Méthode mécanique, valeur par valeur (JAMAIS de changement de valeur) :

1. Dans `gui/circuit_viewer.py`, remplacer le bloc lignes ~35-60 par des
   lectures de tokens :
   `SCH_BG = theme.SCHEMA_COLORS["SCH_BG"]`, `_WIRE = theme.SCHEMA_COLORS["WIRE"]`,
   `_BUS = ...["BUS"]`, `_COMP_COLORS = dict(theme.SCHEMA_COLORS["COMP"])`,
   `_Z_FILL/_Z_EDGE/_OPAMP_FILL/_TITRE_COLOR/_GAIN_COLOR` idem. Les noms
   locaux (`_WIRE`, `_BUS`…) SONT CONSERVÉS — aucun site d'usage ne change.
2. `grep -n '"#' gui/circuit_viewer.py` : pour chaque hex restant (chrome de
   la fenêtre : `#f1f5f9`→`theme.TEXT`, `#64748b`→`theme.TEXT_DIM`,
   `#34d399`→ nouveau token `theme.SUCCESS_SOFT = "#34d399"` à ajouter,
   `#1d4ed8`→`theme.BLUE_PRESS`, `#2563eb`→`theme.BLUE_HOVER`,
   `#374151`/`#4b5563`→ nouveaux tokens `theme.NEUTRAL`/`theme.NEUTRAL_HOVER`,
   `#ffffff`→ nouveau token `theme.WHITE`, `#1e293b`→`theme.OVERLAY`) —
   remplacer par le token. Si un hex n'a pas d'équivalent exact dans theme,
   AJOUTER le token à theme.py avec la même valeur (jamais approximer).
3. Même passe sur `impedance_schematic.py`, `logic_schematic.py`,
   `puce_schematic.py` (couleurs `_BUS`, `_SYMB` colors, etc. — importer
   depuis theme).
4. Dans `gui/schema_grid.py`, remplacer le bloc de constantes locales par :

```python
from gui.theme import SCHEMA_DIMS

PAS = SCHEMA_DIMS["PAS"]
MARGE = SCHEMA_DIMS["MARGE"]
CANAL_H = SCHEMA_DIMS["CANAL_H"]
CANAL_V = SCHEMA_DIMS["CANAL_V"]
X0 = SCHEMA_DIMS["X0"]
```

   (theme.py n'importe aucun module graphique : la pureté d'import du test
   Task 1 reste satisfaite.)
5. Dans `gui/schema_router.py` : `PENALITE_COUDE = SCHEMA_DIMS["PENALITE_COUDE"]`.

- [ ] **Step 5: Vérifier le vert + non-régression pixel**

Run: `PYTHONUTF8=1 python -m pytest tests/test_theme_schemas.py tests/test_labels_property.py tests/test_audit_ilots_visuel.py -q`
Expected: 244 + 5 + 6 tests passed (aucune géométrie modifiée)

- [ ] **Step 6: Commit**

```bash
git add gui/theme.py gui/fonts.py gui/circuit_viewer.py gui/impedance_schematic.py gui/logic_schematic.py gui/puce_schematic.py gui/schema_grid.py gui/schema_router.py tests/test_theme_schemas.py
git commit -m "refactor(theme): SCHEMA_COLORS/SCHEMA_DIMS centralises, zero hex en dur dans les modules de dessin"
```

---

### Task 4: Intégration chaîne — mesures dry-run + grille + routage

**Files:**
- Modify: `gui/circuit_viewer.py` — `_draw_island_chain` (~ligne 4053), nouveau `_mesurer_montage`, nouveau `_tracer_polyligne`, `_fil_en_z` conservé en repli
- Test: `tests/test_assemblage_manhattan.py` (créé ici, étendu Task 5)

**Interfaces:**
- Consomme : `poser`, `EtageMesure`, `Rect`, `snap` (Task 1) ; `router` (Task 2).
- Produit : `_mesurer_montage(match, ci) -> (largeur, hauteur, ancrage_x)` (lru_cache par `(circuit_type, tuple(refs))`) ; `_tracer_polyligne(d, poly, couleur)` — réutilisés par Task 5.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_assemblage_manhattan.py
"""@file test_assemblage_manhattan.py
@brief Contrats corpus de l'assemblage grille+Manhattan (spec §8.3-8.6) :
fils inter-etages orthogonaux, aucun segment a travers un slot d'etage,
repli _fil_en_z journalise. Etendu au DAG branche en Task 5.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import pytest

from circuit_analyzer import detecteur
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.xml import lire_xml
from tools.render_ilots_v2 import _fig_for_ilot

ROOT = Path(__file__).resolve().parent.parent

# Îlots multi-montages en CHAÎNE (assemblage linéaire).
CHAINES = ["chaine_5_aop.xml", "chaine_conditionnement.xml",
           "ilot_chaine_2ce.xml", "ilot_chaine_3ce.xml",
           "ilot_chaine_ce_suiveur.xml", "ilot_chaine_darlington_ce.xml",
           "ilot_reel_ampli_audio_3etages.xml",
           "ilot_reel_ce_suiveur_sortie_rlc.xml"]


def _fig(nom, detaille):
    comps = lire_xml(str(ROOT / "circuits_industriels" / nom))
    graph = construire_graphe(comps)
    results = detecteur.analyser(graph)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
          for c in comps}
    return _fig_for_ilot(results.ilots[0], graph, ci, results,
                         detaille=detaille)


@pytest.mark.parametrize("nom", CHAINES)
@pytest.mark.parametrize("detaille", [False, True], ids=["z", "det"])
def test_fils_interetages_orthogonaux(nom, detaille):
    fig = _fig(nom, detaille)
    for ax in fig.axes:
        for line in ax.lines:
            xy = line.get_xydata()
            for (xa, ya), (xb, yb) in zip(xy[:-1], xy[1:]):
                assert abs(xa - xb) < 1e-6 or abs(ya - yb) < 1e-6, (
                    f"{nom}: segment oblique ({xa},{ya})->({xb},{yb})")


def test_routage_deterministe():
    a = _fig("chaine_5_aop.xml", True)
    b = _fig("chaine_5_aop.xml", True)
    la = [tuple(map(tuple, l.get_xydata())) for ax in a.axes for l in ax.lines]
    lb = [tuple(map(tuple, l.get_xydata())) for ax in b.axes for l in ax.lines]
    assert la == lb
```

Note : le contrat « orthogonal » couvre TOUTES les lignes de la figure. Les
drawers existants tracent déjà orthogonal partout SAUF les diagonales
INTERNES aux symboles schemdraw (transistor BJT : segments base->E/C) — ces
segments appartiennent aux `elm.BjtNpn()` (segments du symbole, pas des
`elm.Line`) et ne produisent pas de Line2D séparées obliques ; si le RED
révèle des exceptions légitimes (symbole custom), les filtrer par couleur
`_WIRE`/`_BUS` UNIQUEMENT et documenter dans le test.

- [ ] **Step 2: Vérifier l'échec**

Run: `PYTHONUTF8=1 python -m pytest tests/test_assemblage_manhattan.py -q`
Expected: FAIL sur `test_fils_interetages_orthogonaux` (les `_fil_en_z` actuels génèrent des positions non alignées à la grille mais orthogonales — l'échec attendu vient de `test_routage_deterministe` si l'ancien chemin passe ; si TOUT passe déjà, l'échec cible est l'ABSENCE des symboles `_mesurer_montage`/import `schema_grid` : ajouter alors une assertion `from gui.circuit_viewer import _mesurer_montage` en tête de test).

- [ ] **Step 3: Implémenter les mesures et la pose**

Dans `gui/circuit_viewer.py`, ajouter au-dessus de `_draw_island_chain` :

```python
# Cache module des mesures de drawers : cle hashable (circuit_type, refs) ;
# un dict simple (pas de lru_cache : `match` est un dict non hashable).
_MESURES = {}


def _mesurer_montage(match, ci):
    """@brief (largeur, hauteur, ancrage_x) de la bbox du drawer de `match`.

    Dry-run : dessine le montage dans un Drawing jetable a l'origine
    (0, _oy_for(match)), sans titre, et mesure d.get_bbox(). Memoise par
    (circuit_type, refs) — un meme montage n'est jamais mesure deux fois.
    ancrage_x = 0 - bbox.xmin (decalage origine -> bord gauche).
    """
    cle = (match.get("circuit_type", ""),
           tuple(sorted(match.get("components") or [])))
    if cle in _MESURES:
        return _MESURES[cle]
    d = schemdraw.Drawing(show=False)
    d._mode_detaille = False
    _dessiner_montage_a(d, match, ci, (0.0, _oy_for(match)), "", "")
    bb = d.get_bbox()
    mesure = (float(bb.xmax - bb.xmin), float(bb.ymax - bb.ymin),
              float(0.0 - bb.xmin))
    _MESURES[cle] = mesure
    return mesure
```

Remplacer le corps de `_draw_island_chain` (placement + câblage) :

```python
def _draw_island_chain(d, ordered, ci, couplages=None):
    """@brief Chaîne de montages posee sur la grille absolue (schema_grid)
    et cablee par le routeur Manhattan (schema_router). Spec 2026-07-13.
    `_fil_en_z` ne subsiste que comme REPLI (router -> None), journalise.
    """
    from gui import schema_grid, schema_router
    n = len(ordered)
    etages = []
    for i, match in enumerate(ordered):
        larg, haut, ancr = _mesurer_montage(match, ci)
        etages.append(schema_grid.EtageMesure(
            cle=f"{i:03d}", colonne=i, bande=0, largeur=larg,
            hauteur=haut, ancrage_x=ancr, ancrage_y=_oy_for(match)))
    plan = schema_grid.poser(etages)

    ancres = []
    for i, match in enumerate(ordered):
        in_label = "VIN" if i == 0 else ""
        out_label = "VOUT" if i == n - 1 else ""
        origin = plan.origines[f"{i:03d}"]
        ancres.append(_dessiner_montage_a(d, match, ci, origin,
                                          in_label, out_label))
        _annoter_etage(d, ancres[-1], match)

    coupl = [m for m in (couplages or []) if _est_couplage(m)]
    find = _couplage_find(couplages or [])
    couplages_utilises = set()
    obstacles = list(plan.obstacles) + _obstacles_stubs(ordered, ancres,
                                                        coupl, ci)
    nets = []
    for i in range(n - 1):
        nets.append((f"lien{i}",
                     schema_grid.snap_point(ancres[i]["out"]),
                     schema_grid.snap_point(ancres[i + 1]["in"])))
    routes = schema_router.router(nets, obstacles)
    for i in range(n - 1):
        out_pt, in_pt = ancres[i]["out"], ancres[i + 1]["in"]
        poly = routes.get(f"lien{i}")
        cc = _couplage_entre(ordered[i], ordered[i + 1], coupl, find, ci)
        if poly is None:
            _log.warning("routage Manhattan impossible pour lien%d ; "
                         "repli _fil_en_z", i)
            if cc is not None:
                couplages_utilises.add(id(cc))
                _fil_avec_couplage(d, out_pt, in_pt, cc, ci)
            else:
                _fil_en_z(d, out_pt, in_pt)
            continue
        # Raccords port reel -> premier/dernier point snappe (droits, courts)
        _raccord(d, out_pt, poly[0])
        _raccord(d, in_pt, poly[-1])
        if cc is not None:
            couplages_utilises.add(id(cc))
            _polyligne_avec_couplage(d, poly, cc, ci)
        else:
            _tracer_polyligne(d, poly)
    _dessiner_impedances_locales(d, ordered, ancres, coupl,
                                 couplages_utilises, ci)
```

Ajouter les helpers (mêmes conventions de style que le fichier) :

```python
def _raccord(d, reel, snappe):
    """@brief Petit fil L entre l'ancre reelle d'un drawer et son point de
    grille (dx, dy < PAS chacun) : horizontal puis vertical."""
    if reel == tuple(snappe):
        return
    coin = (snappe[0], reel[1])
    if coin != tuple(reel):
        d.add(elm.Line().at(reel).to(coin).color(_WIRE))
    if coin != tuple(snappe):
        d.add(elm.Line().at(coin).to(snappe).color(_WIRE))


def _tracer_polyligne(d, poly, couleur=None):
    """@brief Trace une polyligne orthogonale du routeur, segment par segment."""
    c = couleur or _WIRE
    for p, q in zip(poly, poly[1:]):
        d.add(elm.Line().at(p).to(q).color(c))


def _polyligne_avec_couplage(d, poly, cc, ci):
    """@brief Pose le couplage (C serie...) au MILIEU du plus long segment
    horizontal de la polyligne (garanti >= 4*PAS par les couloirs CANAL_H)."""
    segs = [(p, q) for p, q in zip(poly, poly[1:]) if p[1] == q[1]]
    p, q = max(segs, key=lambda s: abs(s[1][0] - s[0][0]))
    milieu = ((p[0] + q[0]) / 2, p[1])
    demi = 0.9
    a, b = (milieu[0] - demi, milieu[1]), (milieu[0] + demi, milieu[1])
    for s, e in zip(poly, poly[1:]):
        if (s, e) == (p, q):
            d.add(elm.Line().at(s).to(a).color(_WIRE))
            _z_box(d, a, b, "Zc", _bloc_couplage(cc), ci)
            d.add(elm.Line().at(b).to(e).color(_WIRE))
        else:
            d.add(elm.Line().at(s).to(e).color(_WIRE))


def _obstacles_stubs(stages, ancres, coupl, ci):
    """@brief Rects previsionnels des stubs Z locales (spec §3.3) — MEME
    geometrie que _dessiner_z_locale (largeur boite 1.2 centree sur l'ancre
    + index*1.8, hauteur 1.65+extra au-dessus (VCC) ou en dessous (autres)).
    Toute evolution de _dessiner_z_locale doit mettre a jour cette fonction
    (test corpus : aucun fil route ne traverse un stub)."""
    from gui.schema_grid import Rect
    rects = []
    for pos, z, other_net, index in _iter_z_locales(stages, ancres, coupl, ci):
        ax, ay = pos
        dx = index * 1.8
        extra = 1.2   # borne haute de _z_locale_extra (previsionnel)
        if other_net == "VCC":
            rects.append(Rect(ax + dx - 0.6, ay, ax + dx + 0.6,
                              ay + 2.0 + extra))
        else:
            rects.append(Rect(ax + dx - 0.6, ay - 2.05 - extra,
                              ax + dx + 0.6, ay))
    return rects
```

`_iter_z_locales` : extraire de `_dessiner_impedances_locales` la boucle qui
détermine (ancre, z, other_net, index) SANS dessiner, la partager entre les
deux usages (un seul point de vérité — pas de duplication de la logique
d'attribution). `snap_point` : ajouter à `schema_grid` :

```python
def snap_point(p):
    """@brief Snappe un point (x, y) sur la grille."""
    return (snap(p[0]), snap(p[1]))
```

- [ ] **Step 4: Vérifier le vert + suite complète**

Run: `PYTHONUTF8=1 python -m pytest tests/test_assemblage_manhattan.py tests/test_labels_property.py -q`
Expected: PASS intégral (contrats labels inchangés : le moteur anti-collision
tourne toujours en fin de fabrique)

Run: `PYTHONUTF8=1 python -m pytest -q`
Expected: suite complète verte

- [ ] **Step 5: Boucle visuelle (exigence boss — OBLIGATOIRE)**

Re-render les chaînes et INSPECTER les PNG :
`PYTHONUTF8=1 python tools/render_ilots_v2.py` puis regarder au minimum
`chaine_5_aop`, `ilot_reel_ampli_audio_3etages`, `chaine_conditionnement`
dans les deux modes. Critères : fils orthogonaux, aucun fil sous un montage
ou un stub, couplages posés sur segments horizontaux.

- [ ] **Step 6: Commit**

```bash
git add gui/circuit_viewer.py gui/schema_grid.py tests/test_assemblage_manhattan.py
git commit -m "feat(assemblage): chaines posees sur la grille et cablees en Manhattan (repli _fil_en_z journalise)"
```

---

### Task 5: Intégration DAG branché (couches multi-bandes)

**Files:**
- Modify: `gui/circuit_viewer.py` — `_make_branched_fig` (~ligne 1680) et son câblage `_branched_edges`
- Test: `tests/test_assemblage_manhattan.py` (étendre)

**Interfaces:**
- Consomme : `poser`/`EtageMesure`/`snap_point` (Task 1), `router` (Task 2), `_mesurer_montage`/`_tracer_polyligne`/`_raccord`/`_polyligne_avec_couplage`/`_obstacles_stubs` (Task 4).
- Produit : rien de nouveau (dernier consommateur).

- [ ] **Step 1: Étendre les tests (RED)**

Ajouter à `tests/test_assemblage_manhattan.py` :

```python
BRANCHES = ["pid_controller.xml", "ilot_branche_ce_fanout.xml",
            "ilot_reel_fanout_filtres_rlc.xml", "logic_dag_2vers1.xml"]


@pytest.mark.parametrize("nom", BRANCHES)
@pytest.mark.parametrize("detaille", [False, True], ids=["z", "det"])
def test_dag_fils_orthogonaux_hors_slots(nom, detaille):
    fig = _fig(nom, detaille)
    for ax in fig.axes:
        for line in ax.lines:
            xy = line.get_xydata()
            for (xa, ya), (xb, yb) in zip(xy[:-1], xy[1:]):
                assert abs(xa - xb) < 1e-6 or abs(ya - yb) < 1e-6, (
                    f"{nom}: segment oblique ({xa},{ya})->({xb},{yb})")
```

Run: `PYTHONUTF8=1 python -m pytest tests/test_assemblage_manhattan.py -q -k dag`
Expected: FAIL (le câblage DAG actuel produit des fils via `_fil_canal` non routés — si tout est déjà orthogonal, l'échec RED se prend sur le déterminisme : dupliquer `test_routage_deterministe` sur `pid_controller.xml`).

- [ ] **Step 2: Porter `_make_branched_fig` sur grille + routeur**

Dans le corps du dessin branché (fonction interne qui place les couches) :
1. construire `EtageMesure(cle=f"{lx:02d}_{i:02d}", colonne=lx, bande=i, ...)`
   pour chaque match `m` de la couche `lx`, position `i` dans la couche,
   avec `_mesurer_montage(m, ci)` et `ancrage_y=_oy_for(m)` ;
2. `plan = schema_grid.poser(etages)` ; dessiner chaque montage à
   `plan.origines[cle]` (remplace le calcul incrémental existant) ;
3. nets à router = les arêtes de `_branched_edges(layers, ci, matches)` :
   nom = `f"{net}_{id(prod)}_{id(cons)}"`, départ = `snap_point(out_pt du
   producteur)`, arrivée = `snap_point(in_pt du consommateur)` ; tri des
   nets par `(couche du producteur, nom)` AVANT routage (spec §4.2) ;
4. obstacles = `plan.obstacles + _obstacles_stubs(...)` ;
5. pour chaque route : `None` -> warning + `_fil_canal` existant (repli) ;
   sinon `_raccord` + `_tracer_polyligne` (ou `_polyligne_avec_couplage` si
   l'arête porte un couplage).
Un net de sortie partagé par PLUSIEURS consommateurs (fanout) : router
chaque arête séparément ; le routeur autorise le PARTAGE d'arêtes du MÊME
net ssi le nom de net passé commence par le même préfixe `net_` — NON :
simplifier — chaque arête garde son nom unique, et l'appelant pose un
`elm.Dot()` au départ commun (`out_pt`) comme le fait déjà le code actuel.
Le non-partage d'arêtes force alors le routeur à écarter les deux branches
d'un fanout dès le départ, ce qui est le comportement VOULU (lisibilité).

- [ ] **Step 3: Vérifier le vert + suite complète**

Run: `PYTHONUTF8=1 python -m pytest tests/test_assemblage_manhattan.py -q`
Expected: PASS

Run: `PYTHONUTF8=1 python -m pytest -q`
Expected: suite complète verte (contrats labels compris)

- [ ] **Step 4: Boucle visuelle (OBLIGATOIRE)**

Re-render + inspecter `pid_controller` (le pire cas : 6 étages, 3 couches),
`ilot_branche_ce_fanout`, `ilot_reel_fanout_filtres_rlc` dans les 2 modes.
Critères : aucune traversée de slot, branches de fanout séparées, couplages
sur segments horizontaux, labels toujours propres (moteur anti-collision).

- [ ] **Step 5: Commit**

```bash
git add gui/circuit_viewer.py tests/test_assemblage_manhattan.py
git commit -m "feat(assemblage): DAG branche pose sur la grille multi-bandes et route en Manhattan"
```

---

### Task 6: Vue dépliée par défaut + cache bimode des figures

**Files:**
- Modify: `gui/circuit_viewer.py` — `show_island` : `mode = {"detaille": False}` (ligne ~885), `_rendre` (ligne ~1197), `_demonter_contexte` (ligne ~891), texte initial du bouton toggle (ligne ~1251)
- Test: `tests/test_island_viewer.py` (étendre)

**Interfaces:**
- Consomme : l'existant uniquement.
- Produit : `etat["figs"] = {False: fig|None, True: fig|None}` (cache bimode).

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `tests/test_island_viewer.py` (suivre le style des tests Tk
existants du fichier — skip si pas de display, fixture popup existante) :

```python
def test_ouverture_en_vue_depliee(tk_root, ilot_simple):
    # show_island doit démarrer en mode détaillé (spec §5).
    etat = _ouvrir_ilot(tk_root, ilot_simple)   # helper existant du fichier
    assert etat["mode"]["detaille"] is True
    assert "Vue simplifiée Z" in etat["toggle_btn"].cget("text")


def test_toggle_ne_reconstruit_pas_deux_fois(tk_root, ilot_simple, monkeypatch):
    compteur = {"n": 0}
    vrai = circuit_viewer._fig_pour_mode_test_hook   # posé par le cache
    # Espionner la fabrique : chaque construction réelle incrémente n.
    ...
```

NOTE à l'implémenteur : lire d'abord `tests/test_island_viewer.py` pour
réutiliser ses fixtures réelles (noms exacts inconnus du plan) ; le contrat
à tester est : (a) `mode["detaille"]` initial True et libellé bouton initial
« Vue simplifiée Z » ; (b) après séquence toggle → toggle (retour dépliée),
`construire_fig` n'a été appelée que DEUX fois au total (une par mode),
espionnée par `monkeypatch` sur la fonction interne via le dict `hooks`
exposé par `show_island` (le fichier expose déjà `"toggle"` dans `hooks`,
ligne ~1330 — y ajouter `"etat"`, `"mode"` et `"nb_constructions"`).

- [ ] **Step 2: RED**

Run: `PYTHONUTF8=1 python -m pytest tests/test_island_viewer.py -q -k "depliee or reconstruit"`
Expected: FAIL (mode initial False ; pas de cache)

- [ ] **Step 3: Implémenter**

Dans `show_island` :

1. `mode = {"detaille": True}` (au lieu de False).
2. Bouton : `toggle_btn = ui_kit.SecondaryButton(bar, text="Vue simplifiée Z", ...)`
   (le libellé initial doit refléter l'action DISPONIBLE, comme le fait déjà
   `_toggle_detaille` après coup).
3. Cache dans `_rendre` :

```python
    etat.setdefault("figs", {False: None, True: None})
    etat.setdefault("nb_constructions", 0)

    def _rendre():
        det = mode["detaille"]
        nouvelle_fig = etat["figs"][det]
        if nouvelle_fig is None:
            nouvelle_fig = construire_fig(det)
            etat["figs"][det] = nouvelle_fig
            etat["nb_constructions"] += 1
        base_w, base_h = ...   # reste du corps INCHANGÉ
```

   (le reste du corps existant — mémorisation base_w/h, zoom, tassage,
   `monter_canvas`, `_maj_bouton_pct`, `_reconstruire_puces` — ne change pas).
4. Dans `_demonter_contexte`, protéger les figures du cache :

```python
        ancienne_fig = etat.get("fig")
        if ancienne_fig is not None and ancienne_fig not in (
                etat.get("figs") or {}).values():
            ancienne_fig.clf()
```

   et au TEARDOWN FINAL du popup (chemin Fermer/WM_DELETE_WINDOW existant,
   qui appelle `_demonter_contexte`), vider aussi le cache :

```python
    def _fermer():          # ou le handler existant équivalent
        for f in (etat.get("figs") or {}).values():
            if f is not None:
                f.clf()
        etat["figs"] = {False: None, True: None}
        _demonter_contexte()
        popup.destroy()
```

   (adapter au handler réel — le principe : `clf()` des DEUX figures au
   moment où la fenêtre meurt, pas avant).
5. Exposer pour les tests : ajouter `"etat": etat, "mode": mode,`
   `"toggle_btn": toggle_btn` au dict `hooks` retourné (ligne ~1330).

ATTENTION zoom : `set_size_inches` mute la figure cachée — comportement
correct (le zoom persiste par mode), mais `_rendre` doit recalculer
base_w/base_h AVANT d'appliquer le facteur : conserver la logique existante
qui les mémorise à partir de la figure SI `etat["figs"][det]` était None,
sinon réutiliser `etat` (stocker `etat["base"] = {False: (w, h), True: (w, h)}`
au premier calcul de chaque mode et relire ensuite).

- [ ] **Step 4: GREEN + suite**

Run: `PYTHONUTF8=1 python -m pytest tests/test_island_viewer.py tests/test_ilots.py -q`
Expected: PASS

Run: `PYTHONUTF8=1 python -m pytest -q`
Expected: suite complète verte

- [ ] **Step 5: Commit**

```bash
git add gui/circuit_viewer.py tests/test_island_viewer.py
git commit -m "feat(ilots): vue depliee par defaut + cache bimode des figures (toggle sans reconstruction)"
```

---

### Task 7: Clôture — sweep visuel complet, suite, ledger

**Files:**
- Modify: `.superpowers/sdd/progress.md` (append)
- Aucun code sauf corrections issues de l'inspection.

- [ ] **Step 1: Suite complète**

Run: `PYTHONUTF8=1 python -m pytest -q`
Expected: verte intégrale (≥ 1583 + nouveaux tests), 0 nouvelle exclusion.

- [ ] **Step 2: Sweep visuel TOTAL (exigence boss)**

`PYTHONUTF8=1 python tools/render_ilots_v2.py` + le script de sweep complet
du scratchpad si disponible. INSPECTER les planches : chaînes, DAG
(pid_controller en priorité), îlots simples (non touchés — sentinelles),
puces, portes. Tout défaut trouvé = fix TDD AVANT de continuer.

- [ ] **Step 3: Vérifier le repli inatteignable**

`PYTHONUTF8=1 python - <<'PY'` : rendre tout le corpus avec un handler
logging capturant les WARNING `routage Manhattan impossible` — attendu :
AUCUN sur le corpus (le repli n'est légal que sur cas pathologique hors
corpus). S'il y en a : les résoudre (agrandir la zone du routeur ou la
borne `_MAX_NOEUDS`) avant clôture.

- [ ] **Step 4: Ledger + commit final**

Append à `.superpowers/sdd/progress.md` : une section « CHANTIER GRILLE +
MANHATTAN (2026-07-13) » avec commits, état suite, PNG inspectés, replis
observés (attendu : 0).

```bash
git add .superpowers/sdd/progress.md
git commit -m "docs(ledger): chantier grille deterministe + routage Manhattan clos"
```

---

## Self-review (fait à l'écriture du plan)

- Spec §3 → Task 1 ; §4 → Task 2 ; §6 → Task 3 ; §4.4+§3.3 → Tasks 4-5 ;
  §5+§7 → Task 6 ; §8 → réparti (tests 1-2 T1, 3-4+6 T2, 7 T3, 5 T4/T5,
  8 T6, 9 T1/T2) + Task 7 (boucle visuelle).
- Ambiguïté assumée : les fixtures exactes de `test_island_viewer.py` sont
  inconnues du plan (Task 6 Step 1 l'explicite et donne le contrat exact).
