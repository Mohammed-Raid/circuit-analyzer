# Routage en L des fils internes au groupe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the straight diagonal line used today for wires internal
to a translated group with a single-bend orthogonal (L-shaped) path that
avoids the group's other components, falling back to a straight line only
when no L-shaped path is clear.

**Architecture:** Two new pure geometry helpers in
`circuit_analyzer/eretro_patch.py` (segment-vs-rectangle intersection,
L-path selection between two candidates), plus one small position-lookup
helper, wired into `_appliquer_deltas`'s existing "different deltas at
both ends" branch.

**Tech Stack:** Python, `xml.etree.ElementTree`, `pytest`.

## Global Constraints

- Only wires whose BOTH endpoints belong to moved role components are
  affected — same scope as the existing straight-line fix (commit
  `121786d`). Wires with only one endpoint in the group are untouched.
- Obstacle boxes are approximate and generic: ~160 wide, ~80 tall,
  centered on each OTHER group component's (already-translated) position.
  Never the two components the wire itself connects.
- If neither of the two L-shaped candidates avoids every obstacle, fall
  back to the straight line — never worse than what's already shipped.
- If the chosen path's bend is degenerate (the two points already share
  an X or Y), return a plain 2-point line, not a redundant 3-point path.
- Never touch `<angle>`. Never touch wires outside this scope.

---

### Task 1: `_segment_croise_rectangle` — segment/rectangle intersection

**Files:**
- Modify: `circuit_analyzer/eretro_patch.py` (add after `_decaler_point`, currently ending at line 195, before `_appliquer_deltas` at line 198)
- Test: `tests/test_eretro_patch.py`

**Interfaces:**
- Produces: `_segment_croise_rectangle(p: tuple[float, float], q: tuple[float, float], rect: tuple[float, float, float, float]) -> bool` — `p`/`q` are the two ends of an axis-aligned segment (they share an X or a Y coordinate); `rect` is `(x0, y0, x1, y1)` with `x0<=x1`, `y0<=y1`. Returns `True` only if the segment crosses the STRICT interior of `rect` (the boundary is passable, same convention as `gui/schema_grid.py`'s `Rect.contient_strict` — not reused, no new dependency on `gui/`, just the same rule reimplemented locally).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_eretro_patch.py`:

```python
def test_segment_croise_rectangle_horizontal_dedans():
    """@brief Un segment horizontal qui passe par l'interieur d'un rectangle est detecte."""
    from circuit_analyzer.eretro_patch import _segment_croise_rectangle
    assert _segment_croise_rectangle((0, 50), (100, 50), (40, 40, 60, 60)) is True


def test_segment_croise_rectangle_horizontal_dehors():
    """@brief Un segment horizontal qui ne touche pas le rectangle n'est pas detecte."""
    from circuit_analyzer.eretro_patch import _segment_croise_rectangle
    assert _segment_croise_rectangle((0, 10), (100, 10), (40, 40, 60, 60)) is False


def test_segment_croise_rectangle_vertical_dedans():
    """@brief Un segment vertical qui passe par l'interieur d'un rectangle est detecte."""
    from circuit_analyzer.eretro_patch import _segment_croise_rectangle
    assert _segment_croise_rectangle((50, 0), (50, 100), (40, 40, 60, 60)) is True


def test_segment_croise_rectangle_frontiere_praticable():
    """@brief Un segment exactement SUR le bord du rectangle n'est pas bloque (frontiere praticable)."""
    from circuit_analyzer.eretro_patch import _segment_croise_rectangle
    assert _segment_croise_rectangle((0, 40), (100, 40), (40, 40, 60, 60)) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -k segment_croise_rectangle -v`
Expected: FAIL — `ImportError: cannot import name '_segment_croise_rectangle'`

- [ ] **Step 3: Write the implementation**

Add to `circuit_analyzer/eretro_patch.py`, right after `_decaler_point` (currently ends line 195) and before `def _appliquer_deltas` (currently line 198):

```python
def _segment_croise_rectangle(p, q, rect) -> bool:
    """@brief Un segment axis-aligned (horizontal OU vertical) traverse-t-il
    l'INTERIEUR d'un rectangle ?

    @param p, q Extremites du segment (x, y) — partagent x (segment
           vertical) OU y (segment horizontal).
    @param rect Rectangle (x0, y0, x1, y1), x0<=x1, y0<=y1.
    @return True si le segment coupe l'interieur STRICT de rect — la
            frontiere reste praticable (meme convention que
            gui/schema_grid.py:Rect.contient_strict, reimplementee ici
            sans nouvelle dependance vers gui/).
    """
    x0, y0, x1, y1 = rect
    (px, py), (qx, qy) = p, q
    if px == qx:
        x = px
        if not (x0 < x < x1):
            return False
        ylo, yhi = min(py, qy), max(py, qy)
        return ylo < y1 and yhi > y0
    y = py
    if not (y0 < y < y1):
        return False
    xlo, xhi = min(px, qx), max(px, qx)
    return xlo < x1 and xhi > x0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -k segment_croise_rectangle -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/eretro_patch.py tests/test_eretro_patch.py
git commit -m "feat(disposition): _segment_croise_rectangle pour l'evitement d'obstacles"
```

---

### Task 2: `_router_fil_en_l` — L-shaped path selection

**Files:**
- Modify: `circuit_analyzer/eretro_patch.py` (add right after `_segment_croise_rectangle`, added in Task 1)
- Test: `tests/test_eretro_patch.py`

**Interfaces:**
- Consumes: `_segment_croise_rectangle(p, q, rect) -> bool` (Task 1).
- Produces: `_LARGEUR_OBSTACLE = 160`, `_HAUTEUR_OBSTACLE = 80` (module-level constants). `_boite_obstacle(centre: tuple[float, float]) -> tuple[float, float, float, float]`. `_router_fil_en_l(p1: tuple[float, float], p2: tuple[float, float], obstacles: list[tuple]) -> list[tuple[float, float]]` — returns a 2-point (straight) or 3-point (single bend) path.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_eretro_patch.py`:

```python
def test_router_fil_en_l_prefere_horizontal_puis_vertical_si_libre():
    """@brief Sans obstacle, le premier candidat (horizontal puis vertical) est retenu."""
    from circuit_analyzer.eretro_patch import _router_fil_en_l
    chemin = _router_fil_en_l((0, 0), (100, 100), [])
    assert chemin == [(0, 0), (100, 0), (100, 100)]


def test_router_fil_en_l_bascule_si_horizontal_bloque():
    """@brief Si le segment horizontal du 1er candidat traverse un obstacle,
    le 2e candidat (vertical puis horizontal) est retenu a la place."""
    from circuit_analyzer.eretro_patch import _router_fil_en_l
    obstacle = (40, -10, 60, 10)  # bloque le segment horizontal (0,0)->(100,0)
    chemin = _router_fil_en_l((0, 0), (100, 100), [obstacle])
    assert chemin == [(0, 0), (0, 100), (100, 100)]


def test_router_fil_en_l_repli_ligne_droite_si_tout_bloque():
    """@brief Si les DEUX candidats sont bloques, repli sur la ligne droite."""
    from circuit_analyzer.eretro_patch import _router_fil_en_l
    obstacles = [(40, -10, 60, 10), (-10, 40, 10, 60)]
    chemin = _router_fil_en_l((0, 0), (100, 100), obstacles)
    assert chemin == [(0, 0), (100, 100)]


def test_router_fil_en_l_deja_droit_reste_a_2_points():
    """@brief p1/p2 deja alignes (meme Y) -> pas de coude degenere, 2 points."""
    from circuit_analyzer.eretro_patch import _router_fil_en_l
    chemin = _router_fil_en_l((0, 0), (100, 0), [])
    assert chemin == [(0, 0), (100, 0)]


def test_boite_obstacle_centree_sur_le_composant():
    """@brief La boite generique est centree sur le point donne, taille fixe."""
    from circuit_analyzer.eretro_patch import _boite_obstacle, _LARGEUR_OBSTACLE, _HAUTEUR_OBSTACLE
    x0, y0, x1, y1 = _boite_obstacle((500, 300))
    assert x1 - x0 == _LARGEUR_OBSTACLE
    assert y1 - y0 == _HAUTEUR_OBSTACLE
    assert (x0 + x1) / 2 == 500
    assert (y0 + y1) / 2 == 300
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -k "router_fil_en_l or boite_obstacle" -v`
Expected: FAIL — `ImportError: cannot import name '_router_fil_en_l'`

- [ ] **Step 3: Write the implementation**

Add to `circuit_analyzer/eretro_patch.py`, right after `_segment_croise_rectangle` (added in Task 1):

```python
_LARGEUR_OBSTACLE = 160
_HAUTEUR_OBSTACLE = 80


def _boite_obstacle(centre) -> tuple:
    """@brief Rectangle (x0,y0,x1,y1) approximatif autour d'un centre de composant.

    Taille generique (~resistance/AOP a cette echelle) : Composant ne porte
    pas de forme reelle cote analyse, seulement une position.
    """
    cx, cy = centre
    return (cx - _LARGEUR_OBSTACLE / 2, cy - _HAUTEUR_OBSTACLE / 2,
            cx + _LARGEUR_OBSTACLE / 2, cy + _HAUTEUR_OBSTACLE / 2)


def _router_fil_en_l(p1, p2, obstacles) -> list:
    """@brief Chemin en angle droit (un seul coude) entre p1 et p2, en
    evitant les rectangles `obstacles`.

    @param p1, p2 Nouvelles positions des deux extremites du fil.
    @param obstacles Rectangles (x0,y0,x1,y1) des AUTRES composants du
           groupe (jamais ceux que ce fil relie lui-meme).
    @return [p1, p2] (ligne droite) si le chemin ne necessite pas de coude,
            ou si aucun des deux candidats n'evite tous les obstacles ;
            [p1, coude, p2] sinon.
    """
    candidats = [
        (p2[0], p1[1]),  # horizontal puis vertical
        (p1[0], p2[1]),  # vertical puis horizontal
    ]
    for coude in candidats:
        segments = [(p1, coude), (coude, p2)]
        if any(_segment_croise_rectangle(a, b, r) for a, b in segments for r in obstacles):
            continue
        if coude[0] == p1[0] == p2[0] or coude[1] == p1[1] == p2[1]:
            return [p1, p2]
        return [p1, coude, p2]
    return [p1, p2]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -k "router_fil_en_l or boite_obstacle" -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/eretro_patch.py tests/test_eretro_patch.py
git commit -m "feat(disposition): _router_fil_en_l choisit un chemin en L ou replie en ligne droite"
```

---

### Task 3: wire L-routing into `_appliquer_deltas`

**Files:**
- Modify: `circuit_analyzer/eretro_patch.py:231-241` (the "deltas differents aux deux bouts" branch inside `_appliquer_deltas`)
- Test: `tests/test_eretro_patch.py`

**Interfaces:**
- Consumes: `_router_fil_en_l(p1, p2, obstacles) -> list` (Task 2), `_boite_obstacle(centre) -> tuple` (Task 2).
- Produces: `_point_translate(point, delta) -> tuple[float, float] | None` (new helper — the wire's OWN pin position, translated, WITHOUT mutating; this is what a moved wire endpoint must land on, since a component's pins sit at an offset from its center, not at the center itself). `_position_actuelle(source, ref) -> tuple[float, float] | None` (new helper — a component's CURRENT center position, used only to build obstacle boxes for the OTHER components in the group, never for the wire's own endpoints). `_appliquer_deltas` now writes an L-shaped or straight path (instead of always a straight line) for wires internal to the moved group.

**Important distinction driving this task:** a wire's recorded `<PointF>` is a PIN location (offset from its component's center — e.g. ±80 for a resistor), not the component's center. The L-path's endpoints must be the translated PIN positions (`_point_translate` on the wire's own points), never the component's `<CtrIem>` center (`_position_actuelle`) — using the center for the endpoint would draw the wire into the middle of the component's body instead of at its lead. `_position_actuelle` is only appropriate for OTHER components, where an approximate body-sized obstacle box is what we want to avoid.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_eretro_patch.py` (this REPLACES the assertions of the existing straight-line test — read it first to confirm you're editing the right one, it currently asserts `resultat == [(5.0, 5.0), (109.0, 1.0)]`):

```python
def test_appliquer_deltas_avec_coude_et_deltas_differents_route_en_l():
    """@brief Un fil dont les deux bouts bougent de deltas DIFFERENTS est
    maintenant route en angle droit (pas juste une diagonale) quand aucun
    autre composant du groupe ne bloque les deux chemins possibles."""
    from circuit_analyzer.eretro_patch import _appliquer_deltas
    from circuit_analyzer.eretro import SourceXML

    racine = ET.Element("BoardSCH")
    ligne = ET.SubElement(racine, "Line")
    lp = ET.SubElement(ligne, "LP")
    coords = [(0, 0), (50, 10), (100, 0)]
    for x, y in coords:
        pf = ET.SubElement(lp, "PointF")
        ET.SubElement(pf, "X").text = str(x)
        ET.SubElement(pf, "Y").text = str(y)

    source = SourceXML(arbre=ET.ElementTree(racine), elements={},
                        lignes=[ligne], lignes_refs={0: ("A", "B")})
    _appliquer_deltas(source, {"A": (5.0, 5.0), "B": (9.0, 1.0)})

    resultat = [(float(p.findtext("X")), float(p.findtext("Y")))
                for p in ligne.findall("LP/PointF")]
    # Nouvelles extremites : A -> (5,5), B -> (109,1). Pas d'obstacle
    # (elements={} ici, donc aucune autre ref connue) -> chemin en L
    # horizontal-puis-vertical, 3 points.
    assert resultat == [(5.0, 5.0), (109.0, 5.0), (109.0, 1.0)]


def test_appliquer_deltas_route_en_l_evite_un_autre_composant_du_groupe():
    """@brief Bout en bout : un 3e composant du groupe, positionne pile sur
    le segment horizontal du 1er candidat, fait basculer sur l'autre.

    Coordonnees deliberement larges (0..1000, pas 0..100) : la boite
    d'evitement fait 160x80, comparable a un trajet court — sur un trajet
    de seulement 100x100 elle bloquerait les DEUX candidats a la fois
    (verifie a la main en ecrivant ce test), ce qui ne testerait rien.
    """
    from circuit_analyzer.eretro_patch import _appliquer_deltas
    from circuit_analyzer.eretro import SourceXML

    racine = ET.Element("BoardSCH")

    def _composant(cx, cy):
        item = ET.Element("DataItem")
        ctr = ET.SubElement(item, "CtrIem")
        ET.SubElement(ctr, "X").text = str(cx)
        ET.SubElement(ctr, "Y").text = str(cy)
        return item

    # A -> (0,0) et B -> (1000,1000) apres translation (delta applique au
    # point du FIL lui-meme, pas au CtrIem de A/B — non representes ici).
    # C doit AUSSI etre dans `deltas` (delta nul : il ne bouge pas, mais
    # les obstacles ne sont construits que pour les AUTRES refs de
    # `deltas`, cf. implementation — un composant du groupe absent de
    # `deltas` ne serait jamais considere comme obstacle). C reste donc a
    # (500,0) : pile sur le segment horizontal du 1er candidat
    # (0,0)->(1000,0), loin des deux segments du 2e candidat (vertical
    # x=0, horizontal y=1000).
    elements = {"C": _composant(500, 0)}
    ligne = ET.SubElement(racine, "Line")
    lp = ET.SubElement(ligne, "LP")
    for x, y in [(-5, -5), (990, 999)]:
        pf = ET.SubElement(lp, "PointF")
        ET.SubElement(pf, "X").text = str(x)
        ET.SubElement(pf, "Y").text = str(y)

    source = SourceXML(arbre=ET.ElementTree(racine), elements=elements,
                        lignes=[ligne], lignes_refs={0: ("A", "B")})
    _appliquer_deltas(source, {"A": (5.0, 5.0), "B": (10.0, 1.0), "C": (0.0, 0.0)})

    resultat = [(float(p.findtext("X")), float(p.findtext("Y")))
                for p in ligne.findall("LP/PointF")]
    assert resultat == [(0.0, 0.0), (0.0, 1000.0), (1000.0, 1000.0)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -k "route_en_l" -v`
Expected: FAIL — the old straight-line branch is still active, so the path is `[(5.0, 5.0), (109.0, 1.0)]` (2 points), not the expected L-shaped result.

- [ ] **Step 3: Write the implementation**

First, add two small helpers right after `_decaler_point` (before `_segment_croise_rectangle`, which Task 1 placed there — put these between them, or immediately after `_decaler_point`, either is fine as long as they're defined before `_appliquer_deltas` uses them):

```python
def _point_translate(point, delta):
    """@brief Nouvelle position (x, y) d'un <PointF>/<CtrIem> apres un
    delta, SANS muter l'element. None si absent/malforme.

    Contrairement a _decaler_point (qui ecrit), celle-ci calcule seulement
    -- necessaire pour router un fil AVANT de savoir quel chemin on va
    finalement ecrire.
    """
    x_elem, y_elem = point.find("X"), point.find("Y")
    if x_elem is None or y_elem is None:
        return None
    try:
        return (float(x_elem.text) + delta[0], float(y_elem.text) + delta[1])
    except (TypeError, ValueError):
        return None


def _position_actuelle(source, ref):
    """@brief Position (x, y) ACTUELLE du CtrIem d'une ref (deja translatee
    si elle fait partie des deltas appliques plus haut dans cette meme
    fonction), ou None si la ref/le CtrIem est absent ou malforme.

    Usage : construire une boite d'evitement pour un AUTRE composant du
    groupe -- jamais pour l'extremite du fil lui-meme (cf. _point_translate).
    """
    element = source.elements.get(ref)
    if element is None:
        return None
    x_elem, y_elem = element.find("CtrIem/X"), element.find("CtrIem/Y")
    if x_elem is None or y_elem is None:
        return None
    try:
        return (float(x_elem.text), float(y_elem.text))
    except (TypeError, ValueError):
        return None
```

Then, in `_appliquer_deltas`, replace the existing "deltas differents" branch (currently, right after the `if delta_a is not None and delta_a == delta_b:` block's `continue`):

```python
        if delta_a is not None and delta_b is not None:
            _decaler_point(points[0], delta_a)
            _decaler_point(points[-1], delta_b)
            if len(points) > 2:
                lp = ligne.find("LP")
                for point in points[1:-1]:
                    lp.remove(point)
            continue
```

with:

```python
        if delta_a is not None and delta_b is not None:
            # Fil INTERNE a un groupe deplace, deltas DIFFERENTS aux deux
            # bouts : route en angle droit plutot qu'une diagonale -- constat
            # visuel reel dans ERetroDesign (capture du 2026-08-12) montrant
            # un croisement chaotique de fils, meme sur un groupe a 3
            # composants. Repli sur la ligne droite (comportement precedent,
            # commit 121786d) si les positions sont indisponibles ou si
            # aucun des deux chemins en L n'evite les autres composants.
            p1 = _point_translate(points[0], delta_a)
            p2 = _point_translate(points[-1], delta_b)
            if p1 is None or p2 is None:
                _decaler_point(points[0], delta_a)
                _decaler_point(points[-1], delta_b)
                if len(points) > 2:
                    lp = ligne.find("LP")
                    for point in points[1:-1]:
                        lp.remove(point)
                continue
            obstacles = [
                _boite_obstacle(pos)
                for autre in deltas
                if autre not in (ra, rb)
                for pos in [_position_actuelle(source, autre)]
                if pos is not None
            ]
            chemin = _router_fil_en_l(p1, p2, obstacles)
            lp = ligne.find("LP")
            for point in points:
                lp.remove(point)
            for x, y in chemin:
                pf = ET.SubElement(lp, "PointF")
                ET.SubElement(pf, "X").text = str(int(round(x)))
                ET.SubElement(pf, "Y").text = str(int(round(y)))
            continue
```

Note: `p1`/`p2` come from `_point_translate` on the wire's OWN recorded points — the wire's actual pin position, moved by its component's delta — never from `_position_actuelle` (the component's center), which is reserved for building obstacle boxes for the OTHER components below. `obstacles` DOES use `_position_actuelle`, read for refs already processed by the component-translation loop above (the first `for ref, delta in deltas.items():` loop in `_appliquer_deltas`, which runs before this wire loop) — so those centers are already the new, translated ones.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -k "route_en_l" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full eretro_patch suite to confirm no regressions**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -q`
Expected: all tests pass (the old test this task's Step 1 replaced no longer exists under its old name — confirm no leftover duplicate/orphaned test remains in the file).

- [ ] **Step 6: Visual verification — regenerate and actually look**

Run: `PYTHONUTF8=1 python tools/render_boardsch_layout.py`

Then write a small one-off script (do not commit it, this is a manual check) to render `inver.xml` if it's still present at the repo root (it was used for the previous fix's verification):

```python
from circuit_analyzer.xml import lire_xml
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer import detecteur
from circuit_analyzer.eretro_patch import ecrire_groupes
import sys
sys.path.insert(0, "tools")
from render_boardsch_layout import render
from pathlib import Path

comps = lire_xml("inver.xml")
res = detecteur.analyser(construire_graphe(comps))
xml_apres = ecrire_groupes(comps.source, comps, res)
render(xml_apres, Path("tools/_renders/inver_apres_routage_l.png"))
```

Read `tools/_renders/inver_apres_routage_l.png` and confirm the wires between the group's components now show at least one right-angle bend instead of a plain diagonal, and nothing crosses through a component box. If `inver.xml` isn't present (the user may not have left it in the repo), use the synthetic 3-component fixture from `tools/_renders/carte_scannee_apres.png` instead — same check.

- [ ] **Step 7: Run the full project test suite**

Run: `PYTHONUTF8=1 python -m pytest -q`
Expected: no new failures compared to the pre-existing baseline (note: `tests/test_puces_resolution.py`'s `reel_555_astable.xml` failures are a known PRE-EXISTING issue unrelated to this plan — confirmed by reviewing the same failures with this plan's changes stashed — don't treat them as caused by this work).

- [ ] **Step 8: Commit**

```bash
git add circuit_analyzer/eretro_patch.py tests/test_eretro_patch.py
git commit -m "feat(disposition): route les fils internes au groupe en L au lieu d'une diagonale"
```

---

## After this plan

The obstacle box size (160×80) and the tie-break rule (always prefer
horizontal-then-vertical when both candidates are clear) are both noted as
open points in the design doc — revisit only if real usage shows the
generic box size is systematically wrong for some component type.
