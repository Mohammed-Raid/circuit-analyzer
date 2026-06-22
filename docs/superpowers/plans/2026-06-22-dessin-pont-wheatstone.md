# Dessin du pont de Wheatstone (losange) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Détecter le motif pont (4 nœuds / 5 arêtes entre 2 bornes) et le dessiner en losange dans la vue d'îlot ; tout autre réseau non-série/parallèle garde l'ancien dessin.

**Architecture:** `detecter_pont` (pur, `impedance.py`) reconnaît la topologie et mappe rôle→ref. `dessiner_pont` (`impedance_schematic.py`) trace le losange via schemdraw. `_pont_ilot` + hook `show_island` branchent ça après l'essai série/parallèle, avant le repli.

**Tech Stack:** Python ; networkx ; schemdraw + matplotlib (existants).

## Global Constraints

- Aucun commit ne porte `Co-Authored-By Claude` (directive utilisateur).
- Aucune nouvelle dépendance.
- Branche : `rewrite-simple`.
- NE PAS modifier `_make_island_fig`, `_build_island_model`, `_draw_island_schematic`, `gui/impedance_view.py`, ni la fonction `dessiner`/`agencer` existantes (on AJOUTE `dessiner_pont`).
- Les 21 tests d'îlot existants et toute la suite doivent rester verts.

## File Structure

- `circuit_analyzer/impedance.py` (modifier) : ajouter `detecter_pont(graphe, a, b)`.
- `gui/impedance_schematic.py` (modifier) : ajouter `dessiner_pont(pont, comps)`.
- `gui/circuit_viewer.py` (modifier) : ajouter `_pont_ilot(ilot, graph)` ; étendre le hook de `show_island`.
- `tests/test_impedance.py`, `tests/test_impedance_schematic.py`, `tests/test_island_viewer.py` (modifier).

---

### Task 1 : `detecter_pont` — reconnaître le motif pont (pur)

**Files:**
- Modify: `circuit_analyzer/impedance.py` (ajouter après `arbre_expr`)
- Test: `tests/test_impedance.py`

**Interfaces:**
- Consumes : `nx` (déjà importé), `TYPES_REDUCTIBLES`, `_graphe_de_travail` (déjà présents dans `impedance.py`).
- Produces : `detecter_pont(graphe, a, b) -> dict | None`. Le dict :
  `{"haut": a, "bas": b, "gauche": n1, "droite": n2, "bras": {"haut_gauche", "haut_droite", "bas_gauche", "bas_droite", "pont"} → ref}`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_impedance.py` :

```python
# ── detecter_pont : motif pont de Wheatstone (4 noeuds / 5 aretes) ────────────

def test_detecter_pont_wheatstone():
    # VIN/VOUT bornes ; NET1/NET2 internes ; R5 = diagonale.
    g = _graphe(
        Composant("R1", "R", {"1": "VIN", "2": "NET1"}, "1k"),
        Composant("R2", "R", {"1": "VIN", "2": "NET2"}, "1k"),
        Composant("R3", "R", {"1": "NET1", "2": "VOUT"}, "1k"),
        Composant("R4", "R", {"1": "NET2", "2": "VOUT"}, "1k"),
        Composant("R5", "R", {"1": "NET1", "2": "NET2"}, "1k"),
    )
    pont = impedance.detecter_pont(g, "VIN", "VOUT")
    assert pont is not None
    assert pont["haut"] == "VIN" and pont["bas"] == "VOUT"
    assert {pont["gauche"], pont["droite"]} == {"NET1", "NET2"}
    # gauche = min des internes -> NET1 ; donc R1 (VIN-NET1) en haut-gauche.
    assert pont["gauche"] == "NET1"
    bras = pont["bras"]
    assert bras["haut_gauche"] == "R1"
    assert bras["haut_droite"] == "R2"
    assert bras["bas_gauche"] == "R3"
    assert bras["bas_droite"] == "R4"
    assert bras["pont"] == "R5"


def test_detecter_pont_serie_parallele_renvoie_none():
    g = _graphe(
        Composant("R1", "R", {"1": "VIN", "2": "M"}, "1k"),
        Composant("R2", "R", {"1": "M", "2": "VOUT"}, "1k"),
        Composant("R3", "R", {"1": "VIN", "2": "VOUT"}, "1k"),
    )
    assert impedance.detecter_pont(g, "VIN", "VOUT") is None


def test_detecter_pont_triangle_renvoie_none():
    # 3 noeuds seulement -> pas un pont.
    g = _graphe(
        Composant("R1", "R", {"1": "VIN", "2": "VOUT"}, "1k"),
        Composant("R2", "R", {"1": "VOUT", "2": "N"}, "1k"),
        Composant("R3", "R", {"1": "N", "2": "VIN"}, "1k"),
    )
    assert impedance.detecter_pont(g, "VIN", "VOUT") is None
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run : `python -m pytest tests/test_impedance.py -q -k detecter_pont`
Expected : FAIL — `AttributeError: ... has no attribute 'detecter_pont'`.

- [ ] **Step 3 : Implémenter**

Ajouter dans `circuit_analyzer/impedance.py`, après `arbre_expr` :

```python
def detecter_pont(graphe, a, b):
    """@brief Reconnaît un motif pont (type Wheatstone) entre les bornes a et b.

    Motif : exactement 4 nœuds et 5 arêtes R/L/C simples ; a et b de degré 2, non
    adjacents ; les 2 autres nœuds (n1, n2) de degré 3, adjacents entre eux ; arêtes
    a-n1, a-n2, n1-b, n2-b, n1-n2.

    @param graphe Graphe d'origine (arêtes R/L/C).
    @param a, b Les deux bornes (sommet haut / bas du losange).
    @return dict|None Structure du pont (nœuds + mapping rôle→ref), ou None.
    """
    W = _graphe_de_travail(graphe)
    if a not in W or b not in W:
        return None
    if W.number_of_nodes() != 4 or W.number_of_edges() != 5:
        return None
    # arêtes simples uniquement (pas de banc parallèle)
    if any(W.number_of_edges(u, v) != 1 for u, v in set(W.edges())):
        return None
    if W.degree(a) != 2 or W.degree(b) != 2 or W.has_edge(a, b):
        return None
    internes = [n for n in W.nodes() if n not in (a, b)]
    if len(internes) != 2:
        return None
    n1, n2 = sorted(internes, key=str)
    if W.degree(n1) != 3 or W.degree(n2) != 3 or not W.has_edge(n1, n2):
        return None
    # les 5 arêtes attendues doivent toutes exister
    attendues = [(a, n1), (a, n2), (n1, b), (n2, b), (n1, n2)]
    if not all(W.has_edge(u, v) for u, v in attendues):
        return None

    def _ref(u, v):
        return next(iter(W.get_edge_data(u, v).values()))["refs"][0]

    return {
        "haut": a, "bas": b, "gauche": n1, "droite": n2,
        "bras": {
            "haut_gauche": _ref(a, n1),
            "haut_droite": _ref(a, n2),
            "bas_gauche": _ref(n1, b),
            "bas_droite": _ref(n2, b),
            "pont": _ref(n1, n2),
        },
    }
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

Run : `python -m pytest tests/test_impedance.py -q -k detecter_pont`
Expected : PASS (3 tests). Puis `python -m pytest tests/test_impedance.py -q` (pas de régression).

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/impedance.py tests/test_impedance.py
git commit -m "feat(impedance): detecter_pont reconnait le motif pont de Wheatstone"
```

---

### Task 2 : `dessiner_pont` — losange schemdraw

**Files:**
- Modify: `gui/impedance_schematic.py` (ajouter `dessiner_pont` ; le module a déjà `schemdraw`, `elm`, `Figure`, `_SYMB`, `SCH_BG`, `_WIRE`, `_BUS`)
- Test: `tests/test_impedance_schematic.py`

**Interfaces:**
- Consumes : structure de `impedance.detecter_pont` ; `comps` {ref → Composant} ; `_SYMB`, `SCH_BG` du module.
- Produces : `dessiner_pont(pont, comps) -> matplotlib.figure.Figure`.

- [ ] **Step 1 : Écrire le smoke test qui échoue**

Ajouter à `tests/test_impedance_schematic.py` :

```python
def test_dessiner_pont_produit_une_figure():
    from circuit_analyzer.composant import Composant
    comps = {r: Composant(r, "R", {"1": "x", "2": "y"}, "1k")
             for r in ("R1", "R2", "R3", "R4", "R5")}
    pont = {
        "haut": "VIN", "bas": "VOUT", "gauche": "N1", "droite": "N2",
        "bras": {"haut_gauche": "R1", "haut_droite": "R2",
                 "bas_gauche": "R3", "bas_droite": "R4", "pont": "R5"},
    }
    fig = sch.dessiner_pont(pont, comps)
    assert fig is not None
    assert len(fig.axes) == 1
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run : `python -m pytest tests/test_impedance_schematic.py::test_dessiner_pont_produit_une_figure -q`
Expected : FAIL — `AttributeError: ... has no attribute 'dessiner_pont'`.

- [ ] **Step 3 : Implémenter**

Ajouter à la fin de `gui/impedance_schematic.py` :

```python
def _elem_arete(ref, comps, p1, p2):
    """@brief Élément schemdraw d'une arête (symbole selon type) entre deux points."""
    comp = comps.get(ref)
    cls = _SYMB.get(getattr(comp, "type", ""), elm.ResistorIEC)
    valeur = getattr(comp, "value", "")
    etiquette = f"{ref}\n{valeur}" if valeur else ref
    return cls().at(p1).to(p2).label(etiquette, loc="bottom", fontsize=9)


def dessiner_pont(pont, comps):
    """@brief Figure matplotlib d'un pont (type Wheatstone) en losange.

    @param pont Structure renvoyée par impedance.detecter_pont.
    @param comps Dict {ref → Composant} (type pour le symbole, value pour l'étiquette).
    @return matplotlib.figure.Figure (losange).
    """
    haut, gauche, droite, bas = (0.0, 4.0), (-2.0, 2.0), (2.0, 2.0), (0.0, 0.0)
    bras = pont["bras"]
    fig = Figure(figsize=(5.0, 5.5))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")

    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d.config(fontsize=10, inches_per_unit=0.5)
        d += _elem_arete(bras["haut_gauche"], comps, haut, gauche)
        d += _elem_arete(bras["haut_droite"], comps, haut, droite)
        d += _elem_arete(bras["bas_gauche"], comps, gauche, bas)
        d += _elem_arete(bras["bas_droite"], comps, droite, bas)
        d += _elem_arete(bras["pont"], comps, gauche, droite)
        d += elm.Dot().at(haut).label(pont["haut"], loc="top", color=_BUS)
        d += elm.Dot().at(bas).label(pont["bas"], loc="bottom", color=_BUS)

    ax.margins(0.2)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        pass
    return fig
```

- [ ] **Step 4 : Lancer le test pour vérifier qu'il passe**

Run : `python -m pytest tests/test_impedance_schematic.py -q`
Expected : PASS (tous les tests du fichier).

- [ ] **Step 5 : Commit**

```bash
git add gui/impedance_schematic.py tests/test_impedance_schematic.py
git commit -m "feat(impedance): dessiner_pont - schema en losange du pont de Wheatstone"
```

---

### Task 3 : `_pont_ilot` + hook `show_island`

**Files:**
- Modify: `gui/circuit_viewer.py` (ajouter `_pont_ilot` ; étendre le hook dans `show_island`)
- Test: `tests/test_island_viewer.py`

**Interfaces:**
- Consumes : `impedance.detecter_pont`, `circuit_analyzer.composant.construire_graphe`, `gui.impedance_schematic.dessiner_pont`, et l'existant `_arbre_serie_parallele_ilot`.
- Produces : `_pont_ilot(ilot, graph) -> (pont, comps) | None`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_island_viewer.py` :

```python
def test_pont_ilot_detecte_le_pont():
    from circuit_analyzer.composant import Composant, construire_graphe
    from gui import circuit_viewer
    g = construire_graphe([
        Composant("R1", "R", {"1": "VIN", "2": "NET1"}, "1k"),
        Composant("R2", "R", {"1": "VIN", "2": "NET2"}, "1k"),
        Composant("R3", "R", {"1": "NET1", "2": "VOUT"}, "1k"),
        Composant("R4", "R", {"1": "NET2", "2": "VOUT"}, "1k"),
        Composant("R5", "R", {"1": "NET1", "2": "NET2"}, "1k"),
    ])
    ilot = {"label": "Ilot", "composants": ["R1", "R2", "R3", "R4", "R5"]}
    res = circuit_viewer._pont_ilot(ilot, g)
    assert res is not None
    pont, comps = res
    assert pont["bras"]["pont"] == "R5"
    assert set(comps) == {"R1", "R2", "R3", "R4", "R5"}


def test_pont_ilot_serie_parallele_renvoie_none():
    from circuit_analyzer.composant import Composant, construire_graphe
    from gui import circuit_viewer
    g = construire_graphe([
        Composant("R1", "R", {"1": "VIN", "2": "M"}, "1k"),
        Composant("R2", "R", {"1": "M", "2": "VOUT"}, "1k"),
    ])
    ilot = {"label": "Ilot", "composants": ["R1", "R2"]}
    assert circuit_viewer._pont_ilot(ilot, g) is None
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run : `python -m pytest tests/test_island_viewer.py -q -k pont_ilot`
Expected : FAIL — `AttributeError: ... has no attribute '_pont_ilot'`.

- [ ] **Step 3 : Implémenter le helper**

Ajouter dans `gui/circuit_viewer.py`, juste après `_arbre_serie_parallele_ilot` :

```python
def _pont_ilot(ilot, graph):
    """@brief Structure pont (Wheatstone) d'un îlot entre VIN et VOUT, ou None.

    @param ilot Îlot détecté (clé "composants" = refs brutes).
    @param graph Graphe original (porte graph["components"]).
    @return (pont, comps) | None : structure de impedance.detecter_pont et dict
            {ref → Composant} du sous-graphe, ou None si ce n'est pas un pont.
    """
    from circuit_analyzer import impedance
    from circuit_analyzer.composant import construire_graphe

    raw = getattr(graph, "graph", {}).get("components", {}) or {}
    refs = [r for r in ilot.get("composants", []) if r in raw]
    if not refs:
        return None
    sous = construire_graphe([raw[r] for r in refs])
    bornes = impedance.bornes_possibles(sous)
    if "VIN" not in bornes or "VOUT" not in bornes:
        return None
    pont = impedance.detecter_pont(sous, "VIN", "VOUT")
    if pont is None:
        return None
    return pont, sous.graph["components"]
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

Run : `python -m pytest tests/test_island_viewer.py -q -k pont_ilot`
Expected : PASS (2 tests).

- [ ] **Step 5 : Étendre le hook dans `show_island`**

Repérer le bloc ajouté précédemment dans `show_island` :

```python
    _sp = _arbre_serie_parallele_ilot(ilot, graph)
    if _sp is not None:
        from gui import impedance_schematic
        _arbre, _comps = _sp
        fig = impedance_schematic.dessiner(_arbre, "VIN", "VOUT", _comps)
    else:
        matches = _matches_for_island(ilot, results)
        fig = _make_island_fig(model, matches=matches)
```

Le remplacer par :

```python
    _sp = _arbre_serie_parallele_ilot(ilot, graph)
    _pont = _pont_ilot(ilot, graph) if _sp is None else None
    if _sp is not None:
        from gui import impedance_schematic
        _arbre, _comps = _sp
        fig = impedance_schematic.dessiner(_arbre, "VIN", "VOUT", _comps)
    elif _pont is not None:
        from gui import impedance_schematic
        _pont_struct, _comps = _pont
        fig = impedance_schematic.dessiner_pont(_pont_struct, _comps)
    else:
        matches = _matches_for_island(ilot, results)
        fig = _make_island_fig(model, matches=matches)
```

- [ ] **Step 6 : Vérifier la suite complète + import**

Run : `python -c "import gui.circuit_viewer; print('import ok')"`
Run : `python -m pytest -q`
Expected : suite complète verte (21 tests d'îlot + nouveaux + reste).

- [ ] **Step 7 : Commit**

```bash
git add gui/circuit_viewer.py tests/test_island_viewer.py
git commit -m "feat(viewer): vue d'ilot dessine le pont de Wheatstone en losange"
```

---

## Vérification finale

- `python -m pytest -q` vert.
- Lancer l'app, ouvrir `circuits_industriels/impedance_pont_wheatstone.xml`, analyser,
  ouvrir le schéma d'îlot : il doit s'afficher en **losange** (4 bras + diagonale R5,
  VIN en haut, VOUT en bas), plus en colonnes-bus.
- Vérifier la non-régression : `impedance_serie_parallele.xml` toujours en
  série/parallèle ; un circuit non-impédance quelconque toujours en ancien dessin.
- Aucun commit avec `Co-Authored-By Claude`.
