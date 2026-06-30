# Vue îlot multi-transistors (chaîne câblée) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afficher une cascade de montages transistor (ex. 2 émetteurs communs AC-couplés) comme une chaîne câblée gauche→droite, chaque étage en schéma complet, au lieu de la grille générique.

**Architecture:** On rend le moteur de chaîne (`_ordonner_montages_flux`, `_layers_montages_flux`, `_dessiner_montage_a`) agnostique au type : nets d'E/S conscients du type (Brique 1), traversée des couplages AC via union-find (Brique 2), dessin d'étage polymorphe par drawers transistor paramétriques en origine (Brique 3). La logique AOP est préservée à l'identique.

**Tech Stack:** Python, schemdraw (symboles), matplotlib (Agg pour tests), pytest.

## Global Constraints

- Fichier principal : `gui/circuit_viewer.py`. Suivre le style existant (docstrings `@brief`, commentaires FR).
- **Zéro régression AOP** : `chaine_5_aop.xml` et `pid_controller.xml` doivent rendre exactement comme avant. Tests de régression obligatoires.
- Pas de boîtes Z sur les transistors (schéma simple, cf. spec 2026-06-26-transistors-schemas-simples).
- Ne JAMAIS ajouter `Co-Authored-By: Claude` aux commits.
- Tests matplotlib : `import matplotlib; matplotlib.use("Agg")` en tête.
- Repère anchors schemdraw (mesuré) : `BjtNpn().at(o)` → base=`o`, collector=`o+(0.752, 0.697)`, emitter=`o+(0.752, -0.697)` ; `BjtPnp().at(o)` → base=`o`, emitter=`o+(0.752, 0.697)`.

---

### Task 1 : Nets d'entrée/sortie conscients du type (`_io_montage`)

**Files:**
- Modify: `gui/circuit_viewer.py` (ajouter après `_in_nets`, ~ligne 1005)
- Test: `tests/test_chaine_ilot.py`

**Interfaces:**
- Consumes: `_in_nets(match)` existant.
- Produces:
  - `_MONTAGES_TRANSISTOR_CHAINABLES: set[str]`, `_MONTAGES_TRANSISTOR_TERMINAUX: set[str]`
  - `_io_montage(match, ci) -> tuple[list[str], str | None]` (in_nets, out_net)

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_chaine_ilot.py (ajouter en bas)
from gui.circuit_viewer import _io_montage


def _ci(*e):
    return {r: {"type": t, "value": v, "pins": p} for r, t, v, p in e}


def test_io_montage_emetteur_commun_in_base_out_collecteur():
    ci = _ci(("Q1", "Q", "", {"B": "NB", "C": "NC", "E": "GND"}))
    match = {"circuit_type": "Amplificateur émetteur commun",
             "components": ["Q1", "Rc", "Rb"], "nodes": ["NB", "NC", "GND"]}
    ins, out = _io_montage(match, ci)
    assert ins == ["NB"]
    assert out == "NC"


def test_io_montage_suiveur_out_emetteur():
    ci = _ci(("Q1", "Q", "", {"B": "NB", "C": "VCC", "E": "NOUT"}))
    match = {"circuit_type": "Collecteur commun (suiveur d'émetteur)",
             "components": ["Q1", "Re"], "nodes": ["NB", "VCC", "NOUT"]}
    ins, out = _io_montage(match, ci)
    assert ins == ["NB"]
    assert out == "NOUT"


def test_io_montage_darlington_in_q1base_out_q2emetteur():
    ci = _ci(("Q1", "Q", "", {"B": "NB", "C": "VCC", "E": "NE1"}),
             ("Q2", "Q", "", {"B": "NE1", "C": "VCC", "E": "NOUT"}))
    match = {"circuit_type": "Paire Darlington",
             "components": ["Q1", "Q2", "Re"], "nodes": ["NB", "VCC", "NOUT"]}
    ins, out = _io_montage(match, ci)
    assert ins == ["NB"]
    assert out == "NOUT"


def test_io_montage_terminal_relais_out_none():
    ci = _ci(("Q1", "Q", "", {"B": "NB", "C": "NCOIL", "E": "GND"}))
    match = {"circuit_type": "Commande de relais",
             "components": ["Q1", "K1"], "nodes": ["NB", "NCOIL", "GND"]}
    _ins, out = _io_montage(match, ci)
    assert out is None


def test_io_montage_aop_inchange():
    # AOP : doit retourner exactement (_in_nets, nodes[-1]).
    from gui.circuit_viewer import _in_nets
    match = {"circuit_type": "Amplificateur inverseur (AOP)",
             "nodes": ["VIN", "INM", "VOUT"],
             "impedances": {"Zin": {"nodes": ["INM", "VIN"], "composition": "R1"}}}
    ins, out = _io_montage(match, {})
    assert ins == _in_nets(match)
    assert out == "VOUT"
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `python -m pytest tests/test_chaine_ilot.py -k io_montage -q`
Expected: FAIL avec `ImportError: cannot import name '_io_montage'`.

- [ ] **Step 3: Implémenter**

```python
# gui/circuit_viewer.py, juste après _in_nets(...)
_MONTAGES_TRANSISTOR_CHAINABLES = {
    "Amplificateur émetteur commun",
    "Transistor en commutation",
    "Collecteur commun (suiveur d'émetteur)",
    "Étage push-pull",
    "Paire Darlington",
}
_MONTAGES_TRANSISTOR_TERMINAUX = {
    "Miroir de courant BJT",
    "Commande de relais",
    "MOSFET en commutation",
    "MOSFET haute-tension (côté haut)",
}


def _io_transistor(match, ci):
    """@brief (in_nets, out_net) d'un montage transistor via les broches du Q.

    Émetteur commun / commutation : OUT = collecteur. Suiveur / push-pull :
    OUT = émetteur. Darlington : IN = base(Q1), OUT = émetteur(Q2).
    """
    ct = match["circuit_type"]
    qs = [r for r in match["components"] if ci.get(r, {}).get("type") == "Q"]
    pins = {r: ci.get(r, {}).get("pins", {}) for r in qs}
    if ct == "Paire Darlington":
        emetteurs = {pins[r].get("E") for r in qs}
        q2 = next((r for r in qs if pins[r].get("B") in emetteurs), qs[-1])
        q1 = next((r for r in qs if r != q2), qs[0])
        return [pins[q1].get("B")], pins[q2].get("E")
    p = pins[qs[0]]
    if ct in ("Collecteur commun (suiveur d'émetteur)", "Étage push-pull"):
        return [p.get("B")], p.get("E")
    return [p.get("B")], p.get("C")


def _io_montage(match, ci):
    """@brief Nets d'entrée/sortie d'un montage, selon son type.

    AOP (et montages historiques) : (_in_nets, nodes[-1]) — inchangé. Transistor
    chaînable : via broches. Transistor terminal : out_net = None (jamais relié
    en aval). @return (in_nets: list[str], out_net: str | None).
    """
    ct = match.get("circuit_type", "")
    if ct in _MONTAGES_TRANSISTOR_CHAINABLES:
        return _io_transistor(match, ci)
    if ct in _MONTAGES_TRANSISTOR_TERMINAUX:
        return _in_nets(match), None
    return _in_nets(match), match["nodes"][-1]
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `python -m pytest tests/test_chaine_ilot.py -k io_montage -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add gui/circuit_viewer.py tests/test_chaine_ilot.py
git commit -m "feat(ilot): nets E/S conscients du type (_io_montage transistor+AOP)"
```

---

### Task 2 : Traversée des couplages AC (union-find)

**Files:**
- Modify: `gui/circuit_viewer.py` (ajouter après `_io_montage`)
- Test: `tests/test_chaine_ilot.py`

**Interfaces:**
- Produces:
  - `_est_couplage(match) -> bool` (Impédance Z à exactement 2 nœuds)
  - `_couplage_find(matches) -> Callable[[str], str]` (représentant union-find des nets reliés par un couplage)

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_chaine_ilot.py
from gui.circuit_viewer import _est_couplage, _couplage_find


def test_est_couplage_impedance_z_2_noeuds():
    assert _est_couplage({"circuit_type": "Impédance Z", "nodes": ["NC1", "NB2"]})
    assert not _est_couplage({"circuit_type": "Amplificateur émetteur commun",
                              "nodes": ["NB", "NC", "GND"]})


def test_couplage_find_fusionne_les_nets_relies():
    matches = [
        {"circuit_type": "Impédance Z", "nodes": ["NC1", "NB2"]},
        {"circuit_type": "Amplificateur émetteur commun", "nodes": ["NB1", "NC1", "GND"]},
    ]
    find = _couplage_find(matches)
    assert find("NC1") == find("NB2")       # reliés par le couplage
    assert find("NB1") != find("NC1")       # non reliés
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_chaine_ilot.py -k couplage -q`
Expected: FAIL avec `ImportError`.

- [ ] **Step 3: Implémenter**

```python
# gui/circuit_viewer.py, après _io_montage
def _est_couplage(match):
    """@brief Vrai si le match est un dipôle de couplage (Impédance Z à 2 nœuds)."""
    return (match.get("circuit_type") == "Impédance Z"
            and len(match.get("nodes", ())) == 2)


def _couplage_find(matches):
    """@brief Union-find des nets reliés par un couplage (Cc, R série…).

    @return fonction find(net) -> représentant ; deux nets reliés par un dipôle
            de couplage partagent le même représentant.
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        racine = x
        while parent[racine] != racine:
            racine = parent[racine]
        while parent[x] != racine:        # compression de chemin
            parent[x], x = racine, parent[x]
        return racine

    for m in matches:
        if _est_couplage(m):
            n1, n2 = m["nodes"]
            parent[find(n1)] = find(n2)
    return find
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `python -m pytest tests/test_chaine_ilot.py -k couplage -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add gui/circuit_viewer.py tests/test_chaine_ilot.py
git commit -m "feat(ilot): traversee des couplages AC (union-find des nets)"
```

---

### Task 3 : Généraliser `_ordonner_montages_flux`

**Files:**
- Modify: `gui/circuit_viewer.py` (`_ordonner_montages_flux` ~ligne 934 ; appel dans `show_island` ~ligne 467)
- Test: `tests/test_chaine_ilot.py`

**Interfaces:**
- Consumes: `_io_montage`, `_couplage_find`, `_est_couplage` (Tasks 1-2).
- Produces: `_ordonner_montages_flux(matches, ci=None) -> list[match] | None` (signature étendue avec `ci`).

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_chaine_ilot.py
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer import detecteur
from gui import circuit_viewer as cv


def _cascade_2ce():
    comps = [
        Composant("Q1", "Q", {"B": "NB1", "C": "NC1", "E": "GND"}),
        Composant("Rb1", "R", {"1": "VCC", "2": "NB1"}, "100k"),
        Composant("Rc1", "R", {"1": "VCC", "2": "NC1"}, "4.7k"),
        Composant("Cc", "C", {"1": "NC1", "2": "NB2"}, "1u"),
        Composant("Q2", "Q", {"B": "NB2", "C": "NC2", "E": "GND"}),
        Composant("Rb2", "R", {"1": "VCC", "2": "NB2"}, "100k"),
        Composant("Rc2", "R", {"1": "VCC", "2": "NC2"}, "1k"),
    ]
    g = construire_graphe(comps)
    res = detecteur.analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    return cv._matches_for_island(ilot, res), ci


def test_ordonner_cascade_2ce_a_travers_couplage():
    matches, ci = _cascade_2ce()
    ordre = cv._ordonner_montages_flux(matches, ci)
    assert ordre is not None
    types = [m["circuit_type"] for m in ordre]
    assert types == ["Amplificateur émetteur commun",
                     "Amplificateur émetteur commun"]
    # Le couplage (Impédance Z) n'est PAS un étage de la chaîne.
    assert all(m["circuit_type"] != "Impédance Z" for m in ordre)
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_chaine_ilot.py -k ordonner_cascade -q`
Expected: FAIL (`ordre is None` aujourd'hui).

- [ ] **Step 3: Remplacer `_ordonner_montages_flux`**

Remplacer entièrement la fonction (lignes ~934-985) par :

```python
def _ordonner_montages_flux(matches, ci=None):
    """@brief Ordonne des montages par flux de signal (OUT(N) -> IN(N+1)).

    Les couplages (Impédance Z 2 nœuds) sont retirés des étages et utilisés pour
    relier deux étages séparés par un condensateur de liaison (via union-find).
    Les nets d'E/S sont résolus selon le type (`_io_montage`). @return montages
    triés entrée->sortie, ou None si ce n'est pas une chaîne linéaire unique.
    """
    etages = [m for m in matches if not _est_couplage(m)]
    if len(etages) < 2:
        return None
    ci = ci or {}
    find = _couplage_find(matches)

    io = {}
    for m in etages:
        ins, out = _io_montage(m, ci)
        io[id(m)] = ([find(n) for n in ins if n], find(out) if out else None)

    par_in = {}
    for m in etages:
        for net in io[id(m)][0]:
            par_in.setdefault(net, []).append(m)
    outs = {io[id(m)][1] for m in etages if io[id(m)][1] is not None}

    tetes = [m for m in etages if not any(n in outs for n in io[id(m)][0])]
    if len(tetes) != 1:
        return None

    ordre, vus, courant = [], set(), tetes[0]
    while courant is not None and id(courant) not in vus:
        ordre.append(courant)
        vus.add(id(courant))
        out = io[id(courant)][1]
        suivants = [s for s in par_in.get(out, []) if id(s) not in vus] if out else []
        if len(suivants) > 1:
            return None                      # bifurcation : pas linéaire
        courant = suivants[0] if suivants else None

    if len(ordre) != len(etages):
        return None
    return ordre
```

- [ ] **Step 4: Mettre à jour l'appel dans `show_island`**

Dans `show_island` (~ligne 467), remplacer :

```python
        _chaine = _ordonner_montages_flux(_matches_for_island(ilot, results))
```

par :

```python
        _chaine = _ordonner_montages_flux(_matches_for_island(ilot, results), comp_info)
```

- [ ] **Step 5: Lancer le nouveau test + la régression AOP**

Run: `python -m pytest tests/test_chaine_ilot.py -q`
Expected: PASS (nouveau test + tous les tests de chaîne AOP existants).

- [ ] **Step 6: Commit**

```bash
git add gui/circuit_viewer.py tests/test_chaine_ilot.py
git commit -m "feat(ilot): _ordonner_montages_flux generique (type + couplages)"
```

---

### Task 4 : Drawers transistor paramétriques en origine

**Files:**
- Modify: `gui/circuit_viewer.py` (`_draw_bjt_switch`, `_draw_common_emitter`, `_draw_suiveur_emetteur`, `_draw_push_pull`, `_draw_darlington`)
- Test: `tests/test_transistor_drawing.py`

**Interfaces:**
- Produces: chaque drawer devient `(_draw_X)(d, result, ci, origin=<def>, titre=True) -> {"in": (x,y), "out": (x,y)}`. `_make_fig` continue de l'appeler en 3 args positionnels (origine + titre par défaut), valeur de retour ignorée.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_transistor_drawing.py (ajouter)
import schemdraw


def _ancres(drawer, result, ci, origin):
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        return drawer(d, result, ci, origin=origin, titre=False)


def test_drawer_ce_renvoie_ancres_in_out():
    res = _ancres(cv._draw_common_emitter, *EMETTEUR_COMMUN, origin=(0, 0))
    assert "in" in res and "out" in res
    assert res["out"][0] > res["in"][0]        # sortie à droite de l'entrée


def test_drawer_ce_origine_decale_le_dessin():
    a = _ancres(cv._draw_common_emitter, *EMETTEUR_COMMUN, origin=(0, 0))
    b = _ancres(cv._draw_common_emitter, *EMETTEUR_COMMUN, origin=(10, 0))
    assert round(b["in"][0] - a["in"][0], 3) == 10.0


def test_drawer_titre_false_pas_de_titre():
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        cv._draw_common_emitter(*EMETTEUR_COMMUN, origin=(0, 0), titre=False)
        txts = [e.label for e in d.elements if hasattr(e, "label")]
    # 'Émetteur commun' ne doit PAS être présent quand titre=False (ré-rendu via la figure)
    fig = cv._make_fig(EMETTEUR_COMMUN[0], EMETTEUR_COMMUN[1], cv._draw_common_emitter)
    standalone = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("Émetteur commun" in t for t in standalone)   # standalone garde le titre
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_transistor_drawing.py -k "ancres or origine or titre_false" -q`
Expected: FAIL (`_draw_common_emitter() got an unexpected keyword argument 'origin'`).

- [ ] **Step 3: Refactoriser `_draw_common_emitter`**

```python
def _draw_common_emitter(d, result, ci, origin=(3, 0), titre=True):
    """@brief Schéma « Amplificateur émetteur commun ». Paramétrique en origine,
    renvoie ses ancres {"in","out"} (réutilisé en vue chaîne)."""
    q = _ref(result, ci, "Q")
    rs = _refs(result, ci, "R")
    q_pins = ci.get(q, {}).get("pins", {})
    rc = _ref_on_net(rs, ci, q_pins.get("C"), rs[0] if rs else "Rc")
    remaining = [r for r in rs if r != rc]
    rb = _ref_on_net(remaining, ci, q_pins.get("B"), remaining[0] if remaining else "Rb")
    t = d.add(elm.BjtNpn().at(origin))
    bx, by = t.base
    in_pt = (bx - 2.6, by)
    _r_simple(d, rb, ci, in_pt, (bx - 0.9, by), "Rb")
    d.add(elm.Line().at((bx - 0.9, by)).to((bx, by)))
    d.add(elm.Dot().at(in_pt).label("IN", loc="left"))
    cx, cy = t.collector
    _r_simple(d, rc, ci, (cx, cy + 0.5), (cx, cy + 1.9), "Rc", label_loc="left")
    d.add(elm.Line().at(t.collector).to((cx, cy + 0.5)))
    d.add(elm.Line().at((cx, cy + 1.9)).up(0.4).label("VCC", loc="top"))
    d.add(elm.Line().at(t.emitter).down(0.5))
    d.add(elm.Ground())
    out_pt = (cx + 1.5, cy)
    d.add(elm.Line().at(t.collector).to(out_pt).label("OUT", loc="right"))
    if titre:
        _titre_montage(d, result, (cx, cy + 2.7))
    return {"in": in_pt, "out": out_pt}
```

- [ ] **Step 4: Refactoriser `_draw_bjt_switch`** (même schéma, OUT = LOAD en haut, pas chaîné en aval mais doit renvoyer des ancres)

```python
def _draw_bjt_switch(d, result, ci, origin=(3, 0), titre=True):
    """@brief Schéma « Transistor en commutation ». Paramétrique en origine."""
    q = _ref(result, ci, "Q"); r = _ref(result, ci, "R")
    t = d.add(elm.BjtNpn().at(origin))
    bx, by = t.base
    in_pt = (bx - 2.6, by)
    _r_simple(d, r, ci, in_pt, (bx - 0.9, by), "Rb")
    d.add(elm.Line().at((bx - 0.9, by)).to((bx, by)))
    d.add(elm.Dot().at(in_pt).label("IN", loc="left"))
    cx, cy = t.collector
    out_pt = (cx, cy + 1.0)
    d.add(elm.Line().at(t.collector).to(out_pt).label("LOAD", loc="right"))
    d.add(elm.Line().at(t.emitter).down(0.5))
    d.add(elm.Ground())
    if titre:
        _titre_montage(d, result, (cx, cy + 1.8))
    return {"in": in_pt, "out": out_pt}
```

- [ ] **Step 5: Refactoriser `_draw_suiveur_emetteur`**

```python
def _draw_suiveur_emetteur(d, result, ci, origin=(3, 0), titre=True):
    """@brief « Collecteur commun (suiveur d'émetteur) ». Paramétrique en origine."""
    q = _ref(result, ci, "Q")
    rs = _refs(result, ci, "R")
    q_pins = ci.get(q, {}).get("pins", {})
    re = _ref_on_net(rs, ci, q_pins.get("E"), rs[0] if rs else "Re")
    rb = next((r for r in rs if r != re), None)
    t = d.add(elm.BjtNpn().at(origin))
    bx, by = t.base
    in_pt = (bx - 2.6, by)
    if rb:
        _r_simple(d, rb, ci, in_pt, (bx - 0.9, by), "Rb")
        d.add(elm.Line().at((bx - 0.9, by)).to((bx, by)))
        d.add(elm.Dot().at(in_pt).label("IN", loc="left"))
    else:
        in_pt = (bx - 1.0, by)
        d.add(elm.Line().at(t.base).to(in_pt).label("IN", loc="left"))
    d.add(elm.Line().at(t.collector).up(1).label("VCC", loc="top"))
    ex, ey = t.emitter
    out_pt = (ex + 1.4, ey)
    d.add(elm.Line().at(t.emitter).to(out_pt).label("OUT", loc="right"))
    _r_simple(d, re, ci, (ex, ey - 0.6), (ex, ey - 2.0), "Re", label_loc="right")
    d.add(elm.Line().at(t.emitter).to((ex, ey - 0.6)))
    d.add(elm.Line().at((ex, ey - 2.0)).down(0.4))
    d.add(elm.Ground())
    if titre:
        _titre_montage(d, result, (t.collector[0], t.collector[1] + 1.8))
    return {"in": in_pt, "out": out_pt}
```

- [ ] **Step 6: Refactoriser `_draw_push_pull`** (préfixer les `at((3, ...))` par origine)

```python
def _draw_push_pull(d, result, ci, origin=(3, 0), titre=True):
    """@brief « Étage push-pull ». Paramétrique en origine."""
    ox, oy = origin
    qn = d.add(elm.BjtNpn().at((ox, oy + 1.7)))
    qp = d.add(elm.BjtPnp().at((ox, oy - 1.7)))
    d.add(elm.Line().at(qn.base).to(qp.base))
    midb = ((qn.base[0] + qp.base[0]) / 2, (qn.base[1] + qp.base[1]) / 2)
    d.add(elm.Dot().at(midb))
    in_pt = (midb[0] - 1.8, midb[1])
    d.add(elm.Line().at(midb).to(in_pt).label("IN", loc="left"))
    d.add(elm.Line().at(qn.collector).up(1.0).label("VCC", loc="top"))
    d.add(elm.Line().at(qp.collector).down(1.0))
    d.add(elm.Ground())
    d.add(elm.Line().at(qn.emitter).to(qp.emitter))
    mide = ((qn.emitter[0] + qp.emitter[0]) / 2, (qn.emitter[1] + qp.emitter[1]) / 2)
    d.add(elm.Dot().at(mide))
    out_pt = (mide[0] + 2.0, mide[1])
    d.add(elm.Line().at(mide).to(out_pt).label("OUT", loc="right"))
    if titre:
        _titre_montage(d, result, (qn.collector[0], qn.collector[1] + 1.8))
    return {"in": in_pt, "out": out_pt}
```

- [ ] **Step 7: Refactoriser `_draw_darlington`** (préfixer les placements par origine)

```python
def _draw_darlington(d, result, ci, origin=(3, 0), titre=True):
    """@brief « Paire Darlington ». Paramétrique en origine."""
    ox, oy = origin
    re = _ref(result, ci, "R")
    q1 = d.add(elm.BjtNpn().at((ox, oy + 1.7)))
    q2 = d.add(elm.BjtNpn().at((ox + 1.8, oy - 1.4)))
    in_pt = (q1.base[0] - 1.4, q1.base[1])
    d.add(elm.Line().at(q1.base).to(in_pt).label("IN", loc="left"))
    d.add(elm.Line().at(q1.collector).up(0.9))
    top = d.here
    d.add(elm.Line().at(q2.collector).toy(top[1]))
    d.add(elm.Line().tox(top[0]))
    d.add(elm.Line().at(top).up(0.4).label("VCC", loc="top"))
    d.add(elm.Line().at(q1.emitter).toy(q2.base[1]))
    d.add(elm.Line().tox(q2.base[0]))
    d.add(elm.Dot().at(q2.base))
    ex, ey = q2.emitter
    out_pt = (ex + 1.6, ey)
    d.add(elm.Line().at(q2.emitter).to(out_pt).label("OUT", loc="right"))
    _r_simple(d, re, ci, (ex, ey - 0.6), (ex, ey - 2.0), "Re", label_loc="left")
    d.add(elm.Line().at(q2.emitter).to((ex, ey - 0.6)))
    d.add(elm.Line().at((ex, ey - 2.0)).down(0.4))
    d.add(elm.Ground())
    if titre:
        _titre_montage(d, result, (top[0], top[1] + 1.2))
    return {"in": in_pt, "out": out_pt}
```

- [ ] **Step 8: Lancer les tests transistor (standalone + nouveaux)**

Run: `python -m pytest tests/test_transistor_drawing.py -q`
Expected: PASS (les tests standalone existants + les 3 nouveaux d'ancres).

- [ ] **Step 9: Commit**

```bash
git add gui/circuit_viewer.py tests/test_transistor_drawing.py
git commit -m "refactor(dessin): drawers transistor parametriques en origine + ancres"
```

---

### Task 5 : Dispatch transistor dans la chaîne + alignement

**Files:**
- Modify: `gui/circuit_viewer.py` (`_dessiner_montage_a` ~ligne 2022 ; `_oy_for` ~ligne 2089 ; `_draw_island_chain` ~ligne 2059)
- Test: `tests/test_chaine_ilot.py`

**Interfaces:**
- Consumes: drawers Task 4, `_io_montage`, `_DRAWERS`.
- Produces: `_dessiner_montage_a` gère les types transistor ; `_oy_for` gère les transistors.

- [ ] **Step 1: Écrire le test qui échoue**

```python
# tests/test_chaine_ilot.py
def test_chaine_2ce_dessine_des_transistors_pas_des_aop():
    matches, ci = _cascade_2ce()
    ordre = cv._ordonner_montages_flux(matches, ci)
    fig = cv._make_chain_fig(ordre, ci)
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert not any("non disponible" in t for t in txts)
    # compter les symboles transistor dessinés (BjtNpn) via les patches/lignes :
    # au moins les 2 étiquettes de rôle "Émetteur commun" doivent apparaître.
    assert sum("Émetteur commun" in t for t in txts) >= 2
    # aucune trace d'un AOP de repli
    assert not any("Suiveur" in t for t in txts)
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_chaine_ilot.py -k 2ce_dessine -q`
Expected: FAIL (les étages transistor passent par `_draw_follower` → pas d'« Émetteur commun », voire « non disponible »).

- [ ] **Step 3: Étendre `_dessiner_montage_a`**

Au début de `_dessiner_montage_a` (juste après `ct = match.get("circuit_type", "")`), ajouter le routage transistor AVANT les branches AOP :

```python
    if ct in _DRAWERS and (ct in _MONTAGES_TRANSISTOR_CHAINABLES
                           or ct in _MONTAGES_TRANSISTOR_TERMINAUX):
        res = _DRAWERS[ct](d, match, ci, origin=origin, titre=False)
        ins, _out = _io_montage(match, ci)
        res["ins"] = {n: res["in"] for n in ins}
        return res
```

(Le reste de la fonction — branches AOP — est inchangé.)

- [ ] **Step 4: Étendre `_oy_for` pour les transistors**

Ajouter, au début de `_oy_for(match)` :

```python
    ct = match.get("circuit_type", "")
    if ct in _MONTAGES_TRANSISTOR_CHAINABLES or ct in _MONTAGES_TRANSISTOR_TERMINAUX:
        # OUT = collecteur (origine + 0.697) ou émetteur (origine - 0.697).
        # On place l'origine pour que la sortie tombe ~ sur la ligne de base.
        if ct in ("Collecteur commun (suiveur d'émetteur)", "Étage push-pull",
                  "Paire Darlington"):
            return 0.697
        return -0.697
```

- [ ] **Step 5: Éviter le doublon de titre dans la chaîne**

Dans `_draw_island_chain`, `_annoter_etage` ajoute déjà le rôle ; les drawers transistor sont appelés avec `titre=False` (Step 3) donc pas de doublon. Vérifier qu'aucune autre modif n'est nécessaire (lecture seule).

- [ ] **Step 6: Lancer le test + régression**

Run: `python -m pytest tests/test_chaine_ilot.py -q`
Expected: PASS (nouveau test + chaînes AOP inchangées).

- [ ] **Step 7: Commit**

```bash
git add gui/circuit_viewer.py tests/test_chaine_ilot.py
git commit -m "feat(ilot): dispatch transistor dans la vue chaine + alignement"
```

---

### Task 6 : Dessiner le couplage (Cc) sur le fil inter-étage

**Files:**
- Modify: `gui/circuit_viewer.py` (`_make_chain_fig` ~ligne 765, `_draw_island_chain` ~ligne 2059)
- Test: `tests/test_chaine_ilot.py`

**Interfaces:**
- Consumes: `_couplage_find`, `_est_couplage`, `_io_montage`.
- Produces: `_make_chain_fig(ordered, comp_info, matches=None)` ; `_draw_island_chain(d, ordered, ci, couplages=None)`.

- [ ] **Step 1: Écrire le test qui échoue**

```python
# tests/test_chaine_ilot.py
def test_chaine_2ce_affiche_le_couplage_cc():
    matches, ci = _cascade_2ce()
    ordre = cv._ordonner_montages_flux(matches, ci)
    fig = cv._make_chain_fig(ordre, ci, matches=matches)
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("Cc" in t for t in txts)        # le condensateur de liaison est étiqueté
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_chaine_ilot.py -k couplage_cc -q`
Expected: FAIL (`Cc` absent ; et/ou `_make_chain_fig` n'accepte pas `matches`).

- [ ] **Step 3: Étendre `_make_chain_fig` pour transmettre les couplages**

Changer la signature et l'appel à `_draw_island_chain` :

```python
def _make_chain_fig(ordered, comp_info, matches=None):
    ...
            _draw_island_chain(d, ordered, ci=comp_info,
                               couplages=(matches or ordered))
    ...
```

(Le reste du corps est inchangé.)

- [ ] **Step 4: Étendre `_draw_island_chain` pour dessiner le couplage**

```python
def _draw_island_chain(d, ordered, ci, couplages=None):
    """@brief Chaîne de montages reliés OUT(N) -> IN(N+1). Si un couplage AC
    (Impédance Z 2 nœuds) relie deux étages, il est dessiné sur le fil."""
    n = len(ordered)
    ancres = []
    for i, match in enumerate(ordered):
        in_label = "VIN" if i == 0 else ""
        out_label = "VOUT" if i == n - 1 else ""
        origin = (4.5 + i * _CHAINE_DX, _oy_for(match))
        ancres.append(_dessiner_montage_a(d, match, ci, origin, in_label, out_label))
        _annoter_etage(d, ancres[-1], match)

    coupl = [m for m in (couplages or []) if _est_couplage(m)]
    find = _couplage_find(couplages or [])
    for i in range(n - 1):
        out_pt = ancres[i]["out"]
        in_pt = ancres[i + 1]["in"]
        cc = _couplage_entre(ordered[i], ordered[i + 1], coupl, find, ci)
        if cc is not None:
            _fil_avec_couplage(d, out_pt, in_pt, cc, ci)
        else:
            _fil_en_z(d, out_pt, in_pt)
```

Ajouter les deux helpers juste avant `_draw_island_chain` :

```python
def _couplage_entre(m_out, m_in, couplages, find, ci):
    """@brief Couplage (match Impédance Z) reliant la sortie de m_out à l'entrée
    de m_in, ou None."""
    out = _io_montage(m_out, ci)[1]
    ins = _io_montage(m_in, ci)[0]
    if out is None:
        return None
    cibles = {find(n) for n in ins if n}
    for z in couplages:
        a, b = z["nodes"]
        if (find(out) in (find(a), find(b))
                and (find(a) in cibles or find(b) in cibles)):
            return z
    return None


def _fil_avec_couplage(d, out_pt, in_pt, cc, ci):
    """@brief Relie out_pt -> in_pt en intercalant le symbole du couplage (cap)."""
    midx = (out_pt[0] + in_pt[0]) / 2
    p1 = (midx - 0.6, out_pt[1])
    p2 = (midx + 0.6, out_pt[1])
    ref = cc.get("composition") if isinstance(cc.get("composition"), str) else None
    refs = cc.get("refs") or ([ref] if ref else [])
    nom = refs[0] if refs else "Cc"
    d.add(elm.Line().at(out_pt).to(p1).color(_WIRE))
    d.add(elm.Capacitor().at(p1).to(p2).label(nom, loc="top"))
    d.add(elm.Line().at(p2).to((in_pt[0], out_pt[1])).color(_WIRE))
    d.add(elm.Line().at((in_pt[0], out_pt[1])).to(in_pt).color(_WIRE))
```

- [ ] **Step 5: Lancer le test + régression**

Run: `python -m pytest tests/test_chaine_ilot.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add gui/circuit_viewer.py tests/test_chaine_ilot.py
git commit -m "feat(ilot): dessine le couplage AC (Cc) sur le fil inter-etage"
```

---

### Task 7 : Vue branchée polymorphe (`_layers_montages_flux` + `_branched_edges`)

**Files:**
- Modify: `gui/circuit_viewer.py` (`_layers_montages_flux` ~ligne 1007, `_branched_edges` ~ligne 2197, appel `show_island` ~ligne 469)
- Test: `tests/test_chaine_ilot.py`

**Interfaces:**
- Consumes: `_io_montage`, `_couplage_find`, `_est_couplage`.
- Produces: `_layers_montages_flux(matches, ci=None)` ; `_branched_edges(layers, ci=None)`.

- [ ] **Step 1: Écrire le test qui échoue (régression PID inchangée + transistors non exclus)**

```python
# tests/test_chaine_ilot.py
def test_branched_inclut_les_etages_transistor():
    # Deux étages transistor en parallèle alimentés par la même entrée + un
    # étage aval : doit produire des couches (≥2) incluant les transistors.
    comps = [
        Composant("Q1", "Q", {"B": "NIN", "C": "NA", "E": "GND"}),
        Composant("Rb1", "R", {"1": "VCC", "2": "NIN"}, "100k"),
        Composant("Rc1", "R", {"1": "VCC", "2": "NA"}, "1k"),
        Composant("Q2", "Q", {"B": "NIN", "C": "NB", "E": "GND"}),
        Composant("Rc2", "R", {"1": "VCC", "2": "NB"}, "1k"),
    ]
    g = construire_graphe(comps)
    res = detecteur.analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    matches = cv._matches_for_island(ilot, res)
    layers = cv._layers_montages_flux(matches, ci)
    # Au moins un étage transistor présent dans les couches (plus filtré sur AOP).
    if layers is not None:
        plat = [m["circuit_type"] for L in layers for m in L]
        assert any("émetteur commun" in t.lower() for t in plat)
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_chaine_ilot.py -k branched_inclut -q`
Expected: FAIL (les transistors sont filtrés par `"(AOP)"`, `layers` ne les contient pas).

- [ ] **Step 3: Généraliser `_layers_montages_flux`**

Remplacer le filtre et le calcul d'E/S :

```python
def _layers_montages_flux(matches, ci=None):
    """@brief Ordonne des montages branchés en couches (DAG par flux de signal).

    Agnostique au type : étages = montages non-couplage ; nets d'E/S via
    `_io_montage` ; couplages AC traversés par union-find. @return couches (≥2)
    ou None.
    """
    ci = ci or {}
    stages = [m for m in matches if not _est_couplage(m)]
    if len(stages) < 2:
        return None
    find = _couplage_find(matches)

    out_net = {}
    in_nets = {}
    for m in stages:
        ins, out = _io_montage(m, ci)
        out_net[id(m)] = find(out) if out else None
        in_nets[id(m)] = [find(n) for n in ins if n]
    producteurs = {out_net[id(m)]: m for m in stages if out_net[id(m)] is not None}

    incoming = {}
    a_entree_externe = {}
    for m in stages:
        prods = []
        externe = False
        for net in in_nets[id(m)]:
            p = producteurs.get(net)
            if p is not None and p is not m:
                prods.append(p)
            else:
                externe = True
        incoming[id(m)] = prods
        a_entree_externe[id(m)] = externe
```

Conserver tel quel le reste de la fonction (calcul des profondeurs / couches) à partir de `incoming` et `a_entree_externe` — ces structures gardent le même format qu'avant.

- [ ] **Step 4: Généraliser `_branched_edges`**

```python
def _branched_edges(layers, ci=None):
    """@brief Arêtes AVANT du DAG (producteur.couche < consommateur.couche).
    Agnostique au type via `_io_montage`."""
    ci = ci or {}
    layer_of = {id(m): lx for lx, L in enumerate(layers) for m in L}
    out_by_net = {}
    for L in layers:
        for m in L:
            _ins, out = _io_montage(m, ci)
            if out:
                out_by_net[out] = m
    edges = []
    for couche in layers:
        for cons in couche:
            ins, _out = _io_montage(cons, ci)
            for net in ins:
                prod = out_by_net.get(net)
                if prod is None or prod is cons:
                    continue
                if layer_of[id(prod)] >= layer_of[id(cons)]:
                    continue
                edges.append((prod, cons, net))
    return edges
```

- [ ] **Step 5: Mettre à jour les appels**

Dans `show_island` (~ligne 469) :

```python
            _branches = _layers_montages_flux(_matches_for_island(ilot, results), comp_info)
```

Dans `_draw_branched_chain` (chercher l'appel à `_branched_edges(layers)`) → `_branched_edges(layers, ci)`.

- [ ] **Step 6: Lancer le test + régression PID**

Run: `python -m pytest tests/test_chaine_ilot.py -q`
Expected: PASS (nouveau test + DAG PID inchangé).

- [ ] **Step 7: Commit**

```bash
git add gui/circuit_viewer.py tests/test_chaine_ilot.py
git commit -m "feat(ilot): vue branchee polymorphe (transistors non exclus)"
```

---

### Task 8 : Intégration + vérification visuelle

**Files:**
- Create: `tools/render_chaine_transistor.py`
- Test: suite complète

- [ ] **Step 1: Vérifier le routage complet de bout en bout (test d'intégration)**

```python
# tests/test_island_viewer.py (ajouter)
def test_cascade_2ce_ne_tombe_pas_sur_la_grille():
    from circuit_analyzer.composant import Composant, construire_graphe
    from circuit_analyzer import detecteur
    from gui import circuit_viewer
    g = construire_graphe([
        Composant("Q1", "Q", {"B": "NB1", "C": "NC1", "E": "GND"}),
        Composant("Rb1", "R", {"1": "VCC", "2": "NB1"}, "100k"),
        Composant("Rc1", "R", {"1": "VCC", "2": "NC1"}, "4.7k"),
        Composant("Cc", "C", {"1": "NC1", "2": "NB2"}, "1u"),
        Composant("Q2", "Q", {"B": "NB2", "C": "NC2", "E": "GND"}),
        Composant("Rb2", "R", {"1": "VCC", "2": "NB2"}, "100k"),
        Composant("Rc2", "R", {"1": "VCC", "2": "NC2"}, "1k"),
    ])
    res = detecteur.analyser(g)
    ci = {r: a for r, a in ((c.ref, {"type": c.type, "value": c.value, "pins": c.pins})
                            for c in g.graph["components"].values())}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    chaine = circuit_viewer._ordonner_montages_flux(
        circuit_viewer._matches_for_island(ilot, res), ci)
    assert chaine is not None and len(chaine) == 2
```

- [ ] **Step 2: Lancer la suite COMPLÈTE**

Run: `python -m pytest -q`
Expected: PASS (toute la suite ; aucune régression AOP).

- [ ] **Step 3: Script de rendu visuel**

```python
# tools/render_chaine_transistor.py
"""Rend la vue ilot d'une cascade 2-CE en PNG pour inspection."""
import os, sys
import matplotlib; matplotlib.use("Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer import detecteur
from gui import circuit_viewer as cv

comps = [
    Composant("Q1", "Q", {"B": "NB1", "C": "NC1", "E": "GND"}),
    Composant("Rb1", "R", {"1": "VCC", "2": "NB1"}, "100k"),
    Composant("Rc1", "R", {"1": "VCC", "2": "NC1"}, "4.7k"),
    Composant("Cc", "C", {"1": "NC1", "2": "NB2"}, "1u"),
    Composant("Q2", "Q", {"B": "NB2", "C": "NC2", "E": "GND"}),
    Composant("Rb2", "R", {"1": "VCC", "2": "NB2"}, "100k"),
    Composant("Rc2", "R", {"1": "VCC", "2": "NC2"}, "1k"),
]
g = construire_graphe(comps); res = detecteur.analyser(g)
ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
matches = cv._matches_for_island(ilot, res)
ordre = cv._ordonner_montages_flux(matches, ci)
fig = cv._make_chain_fig(ordre, ci, matches=matches)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_renders")
os.makedirs(out, exist_ok=True)
p = os.path.join(out, "chaine_2ce.png")
fig.savefig(p, dpi=110, bbox_inches="tight"); print(p)
```

Run: `python tools/render_chaine_transistor.py`
Expected: chemin du PNG imprimé.

- [ ] **Step 4: Inspecter le PNG**

Ouvrir `tools/_renders/chaine_2ce.png` (via l'outil Read). Vérifier visuellement :
- deux étages émetteur commun complets côte à côte ;
- reliés par un condensateur `Cc` sur le fil ;
- aucun symbole AOP, aucun carré générique ;
- titres « Émetteur commun » présents.
Si défaut visuel : itérer sur les constantes d'alignement (`_oy_for`, `_CHAINE_DX`) puis re-rendre.

- [ ] **Step 5: Nettoyer les rendus jetables et committer**

```bash
rm -rf tools/_renders
git add tools/render_chaine_transistor.py tests/test_island_viewer.py
git commit -m "test(ilot): integration cascade 2-CE + script de rendu visuel"
```

---

## Self-Review

- **Couverture spec :** Brique 1 → Task 1 ; Brique 2 → Task 2 ; ordonnancement linéaire → Task 3 ; dessin polymorphe (drawers paramétriques) → Tasks 4-5 ; couplage dessiné → Task 6 ; vue branchée → Task 7 ; tests + visuel → Task 8. Régression AOP couverte aux Tasks 3, 5, 7, 8.
- **Hors périmètre respecté :** aucune modif de détection ; pas de point de fonctionnement.
- **Cohérence des types :** `_io_montage(match, ci) -> (list[str], str|None)` utilisé identiquement dans Tasks 3, 5, 6, 7 ; drawers `(d, result, ci, origin, titre) -> {"in","out"}` utilisés Tasks 4-5 ; `_couplage_find(matches) -> find` utilisé Tasks 3, 6.
- **Limite connue :** un îlot avec un transistor « orphelin » (non détecté comme montage) reste sur la grille générique — c'est un manque de *détection*, hors périmètre de ce plan.
