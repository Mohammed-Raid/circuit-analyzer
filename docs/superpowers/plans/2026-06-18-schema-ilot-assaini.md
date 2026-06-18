# Schéma d'îlot assaini — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre lisible le schéma à plat (bus-colonnes) d'un îlot, y compris sur les gros îlots hétérogènes (24 comp / 18 nets), en isolant toute la logique de layout dans une fonction pure testable.

**Architecture:** `_build_island_schematic_plan(model)` devient la fonction pure unique qui filtre les nets (NC supprimés, E/S→moignons, ≥2 connexions→colonnes), ordonne les colonnes, rogne leur extent vertical, assigne les lignes et choisit les symboles. `_draw_island_schematic(d, plan)` ne fait que consommer ce plan.

**Tech Stack:** Python, schemdraw 0.22 (`elm.Opamp`, `elm.Resistor`, …), matplotlib `Figure`, pytest.

## Global Constraints

- Branche : `rewrite-simple`.
- Commits **sans** `Co-Authored-By Claude` (directive utilisateur).
- Symboles réels + **valeurs réelles** (`10k`, `100pF`) dans la vue d'îlot — pas « Z ».
- Net classifiers : `is_ground_net`, `is_power_net`, `is_protective_earth_net` depuis `circuit_analyzer.patterns.base` (déjà importés dans `circuit_viewer.py`).
- Convention de jonction : point = connexion ; croisement nu = pas de liaison (caption d'une ligne).
- Hors périmètre : découpage par sous-circuit, layout hybride, arcs de saut, routage optimal.

---

### Task 1: Plan pur — classification des nets (NC, stub, colonne)

**Files:**
- Modify: `gui/circuit_viewer.py` (`_build_island_schematic_plan`)
- Test: `tests/test_island_viewer.py`

**Interfaces:**
- Consumes: `_build_island_model(ilot, graph, comp_info)` → `model` dict avec `components`, `links`.
- Produces: `_build_island_schematic_plan(model)` → dict avec clés `label`, `columns` (liste de `{"net","x","kind","y_top","y_bottom"}`), `rows` (liste de `{"ref","type","value","symbol","y","pins":[(pin,net)],"stubs":[(pin,net)]}`), `caption`.

- [ ] **Step 1: Write the failing test**

```python
def test_plan_drops_nc_and_classifies_stub_vs_column():
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "MID"}, "10k"),
        Composant("R2", "R", {"1": "MID", "2": "GND"}, "10k"),
        Composant("U1", "U", {"IN+": "MID", "IN-": "FB", "OUT": "NC"}),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot", "composants": ["R1", "R2", "U1"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    plan = _build_island_schematic_plan(model)

    col_nets = {c["net"] for c in plan["columns"]}
    # NC : jamais de colonne
    assert "NC" not in col_nets
    # MID touche 3 broches -> colonne ; GND/IN -> >=2 ? IN touche 1 broche -> stub
    assert "MID" in col_nets
    assert "IN" not in col_nets            # 1 seule connexion => E/S (stub)
    # IN doit apparaitre comme stub de R1
    r1 = next(r for r in plan["rows"] if r["ref"] == "R1")
    assert ("1", "IN") in r1["stubs"]
    # NC ne doit pas devenir un stub non plus
    u1 = next(r for r in plan["rows"] if r["ref"] == "U1")
    assert all(net != "NC" for _pin, net in u1["stubs"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_island_viewer.py::test_plan_drops_nc_and_classifies_stub_vs_column -v`
Expected: FAIL (KeyError `columns` / `stubs` absent — l'ancien plan a `nets`/`components`).

- [ ] **Step 3: Write minimal implementation**

Réécrire `_build_island_schematic_plan` (et adapter `_planned_component` / supprimer si fusionné) :

```python
_NC_NAMES = {"NC", "N/C", "NReliee", ""}


def _net_kind(net):
    if is_ground_net(net) or is_protective_earth_net(net):
        return "ground"
    if is_power_net(net):
        return "power"
    return "signal"


def _schematic_symbol(ctype):
    return {
        "R": "resistor", "C": "capacitor", "L": "inductor",
        "D": "diode", "F": "fuse", "SW": "switch",
        "U": "opamp", "Q": "bjt", "M": "mosfet",
        "K": "relay", "X": "connector",
    }.get(ctype, "block")


ROW_PITCH = 1.6
COL_PITCH = 2.4


def _build_island_schematic_plan(model):
    """Plan netlist-fidele assaini : colonnes (nets >=2 connexions), lignes, stubs."""
    components = list(model.get("components", []))

    # Connexions par net (dans l'ilot), en ignorant NC / vides.
    net_pins = {}
    for comp in components:
        for pin, net in (comp.get("pins", {}) or {}).items():
            if not net or net.upper() in {n.upper() for n in _NC_NAMES}:
                continue
            net_pins.setdefault(net, []).append((comp["ref"], pin))

    col_nets = {net for net, pins in net_pins.items() if len(pins) >= 2}

    # Lignes (une par composant) + stubs (broches vers nets a 1 connexion).
    rows = []
    for idx, comp in enumerate(components):
        y = -idx * ROW_PITCH
        pins = [(pin, net) for pin, net in (comp.get("pins", {}) or {}).items()]
        stubs = [
            (pin, net) for pin, net in pins
            if net and net in net_pins and net not in col_nets
        ]
        rows.append({
            "ref": comp.get("ref", "?"),
            "type": comp.get("type", "?"),
            "value": comp.get("value", ""),
            "symbol": _schematic_symbol(comp.get("type", "?")),
            "y": y,
            "pins": pins,
            "stubs": stubs,
        })

    columns = _layout_columns(col_nets, net_pins, rows)

    return {
        "label": model.get("label", "Ilot"),
        "columns": columns,
        "rows": rows,
        "caption": "● connexion — un croisement sans point n'est pas une liaison",
    }
```

`_layout_columns` est défini en Task 2 ; pour faire passer ce test, ajouter d'abord une version minimale :

```python
def _layout_columns(col_nets, net_pins, rows):
    y_by_ref = {r["ref"]: r["y"] for r in rows}
    cols = []
    for i, net in enumerate(sorted(col_nets)):
        ys = [y_by_ref[ref] for ref, _pin in net_pins[net]]
        cols.append({"net": net, "x": float(i * COL_PITCH),
                     "kind": _net_kind(net),
                     "y_top": max(ys), "y_bottom": min(ys)})
    return cols
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_island_viewer.py::test_plan_drops_nc_and_classifies_stub_vs_column -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gui/circuit_viewer.py tests/test_island_viewer.py
git commit -m "feat(viewer): plan d'ilot pur - NC supprimes, E/S en moignons"
```

---

### Task 2: Ordre des colonnes (masse à gauche, alim à droite) + extent rogné

**Files:**
- Modify: `gui/circuit_viewer.py` (`_layout_columns`)
- Test: `tests/test_island_viewer.py`

**Interfaces:**
- Produces: `_layout_columns(col_nets, net_pins, rows)` ordonne : `ground` (x min) → `signal` (trié par y moyen) → `power` (x max) ; `y_top`/`y_bottom` = bornes des lignes connectées.

- [ ] **Step 1: Write the failing test**

```python
def test_columns_ordered_ground_left_power_right_and_trimmed():
    composants = [
        Composant("R1", "R", {"1": "VCC", "2": "MID"}, "10k"),
        Composant("R2", "R", {"1": "MID", "2": "OUT"}, "10k"),
        Composant("R3", "R", {"1": "OUT", "2": "GND"}, "10k"),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot", "composants": ["R1", "R2", "R3"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    plan = _build_island_schematic_plan(model)
    by_net = {c["net"]: c for c in plan["columns"]}

    # GND (ground) a le plus petit x, VCC (power) le plus grand
    xs = {c["net"]: c["x"] for c in plan["columns"]}
    assert xs["GND"] == min(xs.values())
    assert xs["VCC"] == max(xs.values())
    # MID connecte R1 (y=0) et R2 (y=-1.6) -> extent rogne sur ces deux lignes
    assert by_net["MID"]["y_top"] == 0.0
    assert by_net["MID"]["y_bottom"] == -1.6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_island_viewer.py::test_columns_ordered_ground_left_power_right_and_trimmed -v`
Expected: FAIL (ordre alphabétique : GND/MID/OUT/VCC, donc VCC pas forcément au max après tri alpha — en fait GND<MID<OUT<VCC donne déjà VCC au max et GND au min ; le test peut passer par accident sur l'ordre mais PAS sur le tri par kind. Pour rendre l'échec net, ajouter un net signal « AAA » : voir ci-dessous.)

Ajuster le test pour forcer l'échec sur le tri par `kind` (un signal alphabétiquement avant GND) :

```python
    composants = [
        Composant("R1", "R", {"1": "VCC", "2": "AAA"}, "10k"),
        Composant("R2", "R", {"1": "AAA", "2": "OUT"}, "10k"),
        Composant("R3", "R", {"1": "OUT", "2": "GND"}, "10k"),
    ]
    ...
    assert xs["GND"] == min(xs.values())   # ground a gauche malgré 'AAA' < 'GND' alpha
    assert xs["VCC"] == max(xs.values())   # power a droite
    assert by_net["AAA"]["y_top"] == 0.0
    assert by_net["AAA"]["y_bottom"] == -1.6
```

- [ ] **Step 3: Write minimal implementation**

```python
def _layout_columns(col_nets, net_pins, rows):
    y_by_ref = {r["ref"]: r["y"] for r in rows}
    order = {"ground": 0, "signal": 1, "power": 2}

    def avg_y(net):
        ys = [y_by_ref[ref] for ref, _pin in net_pins[net]]
        return sum(ys) / len(ys)

    ordered = sorted(
        col_nets,
        key=lambda net: (order[_net_kind(net)], -avg_y(net), net),
    )
    cols = []
    for i, net in enumerate(ordered):
        ys = [y_by_ref[ref] for ref, _pin in net_pins[net]]
        cols.append({"net": net, "x": float(i * COL_PITCH),
                     "kind": _net_kind(net),
                     "y_top": max(ys), "y_bottom": min(ys)})
    return cols
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_island_viewer.py::test_columns_ordered_ground_left_power_right_and_trimmed -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gui/circuit_viewer.py tests/test_island_viewer.py
git commit -m "feat(viewer): colonnes ordonnees masse/signal/alim + extent rogne"
```

---

### Task 3: Symbole AOP réel + adaptation des tests existants

**Files:**
- Modify: `gui/circuit_viewer.py` (vérifie le mapping symbol ; supprime `_planned_component` mort, `_schematic_net_sort_key` mort si plus utilisés)
- Test: `tests/test_island_viewer.py` (adapter les tests qui lisaient l'ancienne structure `plan["nets"]`)

**Interfaces:**
- Produces: `row["symbol"] == "opamp"` pour un composant de type `U`.

- [ ] **Step 1: Write the failing test**

```python
def test_opamp_symbol_and_plan_structure():
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "MID"}, "10k"),
        Composant("C1", "C", {"1": "MID", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "MID", "IN-": "GND", "OUT": "MID"}),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot 1 - filtrage", "composants": ["R1", "C1", "U1"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    plan = _build_island_schematic_plan(model)

    by_ref = {r["ref"]: r for r in plan["rows"]}
    assert by_ref["U1"]["symbol"] == "opamp"
    assert by_ref["R1"]["symbol"] == "resistor"
    # lignes strictement decroissantes en y (pas de chevauchement vertical)
    ys = [r["y"] for r in plan["rows"]]
    assert ys == sorted(ys, reverse=True)
    assert all(abs(a - b) >= 1.5 for a, b in zip(ys, ys[1:]))
```

- [ ] **Step 2: Run test to verify it fails / adapter les anciens**

Le test précédent `test_build_island_schematic_plan_keeps_exact_component_pin_nets` lit `plan["nets"]` et `plan["rails"]` (n'existent plus). Le mettre à jour pour la nouvelle structure :

```python
def test_build_island_schematic_plan_keeps_exact_component_pin_nets():
    composants = [
        Composant("R1", "R", {"1": "IN", "2": "MID"}, "10k"),
        Composant("C1", "C", {"1": "MID", "2": "GND"}, "100n"),
        Composant("D1", "D", {"A": "MID", "K": "OUT"}, "1N4148"),
    ]
    graphe = construire_graphe(composants)
    ilot = {"label": "Ilot 1 - filtrage", "composants": ["R1", "C1", "D1"]}
    model = _build_island_model(ilot, graphe, _comp_info(composants))

    plan = _build_island_schematic_plan(model)

    # MID relie R1,C1,D1 (3) -> colonne ; GND relie C1 (1) -> stub ; IN/OUT 1 -> stub
    col_nets = {c["net"] for c in plan["columns"]}
    assert "MID" in col_nets
    by_ref = {r["ref"]: r for r in plan["rows"]}
    assert by_ref["R1"]["pins"] == [("1", "IN"), ("2", "MID")]
    assert by_ref["C1"]["pins"] == [("1", "MID"), ("2", "GND")]
    assert by_ref["D1"]["pins"] == [("A", "MID"), ("K", "OUT")]
    assert by_ref["R1"]["symbol"] == "resistor"
    assert by_ref["C1"]["symbol"] == "capacitor"
    assert by_ref["D1"]["symbol"] == "diode"
```

Run: `python -m pytest tests/test_island_viewer.py -v`
Expected: les nouveaux tests échouent d'abord si le mapping `U→opamp` n'est pas en place (il l'est après Task 1) — sinon ils passent ; l'objectif est surtout que la suite du fichier soit verte avec la nouvelle structure.

- [ ] **Step 3: Write minimal implementation**

Mapping déjà posé en Task 1 (`"U": "opamp"`). Supprimer les fonctions mortes `_planned_component` et `_schematic_net_sort_key` si elles ne sont plus référencées (`grep -n "_planned_component\|_schematic_net_sort_key" gui/circuit_viewer.py`).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_island_viewer.py -v`
Expected: PASS (tous)

- [ ] **Step 5: Commit**

```bash
git add gui/circuit_viewer.py tests/test_island_viewer.py
git commit -m "feat(viewer): symbole AOP reel + plan adapte, code mort retire"
```

---

### Task 4: Drawer consommant le plan (colonnes rognées, AOP, stubs, caption)

**Files:**
- Modify: `gui/circuit_viewer.py` (`_draw_island_schematic`, `_make_island_fig`, drawers 2-broches / opamp / bloc / stub)
- Test: `tests/test_island_viewer.py` (fumée : gros îlot sans exception)

**Interfaces:**
- Consumes: `plan` de Task 1-3.
- Produces: `_make_island_fig(model, matches=None)` → `Figure` non vide, sans exception, pour le gros îlot.

- [ ] **Step 1: Write the failing test**

```python
def test_make_island_fig_renders_large_heterogeneous_island():
    import matplotlib
    matplotlib.use("Agg")
    from circuit_analyzer.xml import lire_xml
    comps = lire_xml("circuits_industriels/signal_conditioning.xml")
    graphe = construire_graphe(comps)
    from circuit_analyzer.detecteur import analyser
    res = analyser(graphe)
    big = max(res.ilots, key=lambda il: len(il.get("composants", [])))
    comp_info = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
                 for c in comps}
    model = _build_island_model(big, graphe, comp_info)

    fig = _make_island_fig(model)

    assert fig.axes
    texts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert any("U1" in t for t in texts)         # AOP present
    assert any("connexion" in t for t in texts)  # caption presente
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_island_viewer.py::test_make_island_fig_renders_large_heterogeneous_island -v`
Expected: FAIL (caption absente / ancien drawer référence `plan["nets"]`).

- [ ] **Step 3: Write minimal implementation**

Réécrire `_draw_island_schematic` et ses helpers pour consommer `columns`/`rows`/`stubs`. Code de référence (à affiner visuellement) :

```python
def _draw_island_schematic(d, plan):
    columns = plan["columns"]
    rows = plan["rows"]
    if not columns:
        return
    x_by_net = {c["net"]: c["x"] for c in columns}

    # Colonnes-bus rognées + etiquette + masse.
    for c in columns:
        d += elm.Line().at((c["x"], c["y_top"] + 0.4)).to((c["x"], c["y_bottom"] - 0.4))
        d += elm.Dot().at((c["x"], c["y_top"] + 0.4)).label(c["net"], loc="top")
        if c["kind"] == "ground":
            d += elm.Ground().at((c["x"], c["y_bottom"] - 0.4))

    for row in rows:
        cols_pins = [(p, n) for p, n in row["pins"] if n in x_by_net]
        if row["symbol"] == "opamp":
            _draw_opamp_row(d, row, cols_pins, x_by_net)
        elif len(cols_pins) == 2 and cols_pins[0][1] != cols_pins[1][1]:
            _draw_two_pin_row(d, row, cols_pins, x_by_net)
        else:
            _draw_block_row(d, row, cols_pins, x_by_net)
        _draw_stubs(d, row, x_by_net)


def _draw_two_pin_row(d, row, cols_pins, x_by_net):
    (_p1, n1), (_p2, n2) = cols_pins
    x1, x2 = x_by_net[n1], x_by_net[n2]
    y = row["y"]
    left, right = sorted((x1, x2))
    direction = "right"
    element = _SYMBOL_ELM.get(row["symbol"], elm.Resistor)
    d += elm.Dot().at((left, y))
    d += elm.Line().at((left, y)).tox(left + 0.25)
    part = element().at((left + 0.25, y)).right(max(0.8, right - left - 0.5))
    d += part.label(_component_label(row), loc="top")
    d += elm.Line().tox(right)
    d += elm.Dot().at((right, y))


def _draw_opamp_row(d, row, cols_pins, x_by_net):
    xs = [x_by_net[n] for _p, n in cols_pins] or [0.0]
    cx = sum(xs) / len(xs)
    y = row["y"]
    op = elm.Opamp(leads=True).at((cx, y)).right().label(row["ref"], loc="center")
    d += op
    for pin, net in cols_pins:
        x = x_by_net[net]
        d += elm.Line().at((cx, y)).to((x, y))
        d += elm.Dot().at((x, y)).label(pin, loc="bottom")


def _draw_block_row(d, row, cols_pins, x_by_net):
    if not cols_pins:
        return
    xs = [x_by_net[n] for _p, n in cols_pins]
    cx = (min(xs) + max(xs)) / 2
    y = row["y"]
    d += elm.Rect(w=1.6, h=0.7).at((cx, y)).label(row["ref"], loc="center")
    for pin, net in cols_pins:
        x = x_by_net[net]
        d += elm.Line().at((cx, y)).to((x, y))
        d += elm.Dot().at((x, y)).label(pin, loc="bottom")


def _draw_stubs(d, row, x_by_net):
    for pin, net in row["stubs"]:
        # moignon court a droite de la ligne, etiquette du net (E/S)
        x = max([x_by_net[n] for _p, n in row["pins"] if n in x_by_net] or [0.0])
        y = row["y"]
        d += elm.Line().at((x + 0.3, y)).right(0.5).label(net, loc="right")
```

Ajouter la table `_SYMBOL_ELM` près des imports :

```python
_SYMBOL_ELM = {
    "resistor": elm.Resistor, "capacitor": elm.Capacitor,
    "inductor": elm.Inductor2, "diode": elm.Diode,
    "fuse": elm.Fuse, "switch": elm.Switch,
}
```

Dans `_make_island_fig`, après le `with schemdraw.Drawing(... ) as d: _draw_island_schematic(d, plan)`, ajouter la caption :

```python
    ax.text(0.01, 0.01, plan["caption"], transform=ax.transAxes,
            fontsize=8, color="#64748b", va="bottom", ha="left")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_island_viewer.py -v`
Expected: PASS (tous)

- [ ] **Step 5: Commit**

```bash
git add gui/circuit_viewer.py tests/test_island_viewer.py
git commit -m "feat(viewer): drawer d'ilot assaini (colonnes rognees, AOP, stubs, legende)"
```

---

### Task 5: Vérification visuelle + suite complète

**Files:**
- Use: `debug_render_ilots.py` (déjà présent)

- [ ] **Step 1: Rendu headless du gros îlot**

Run: `python debug_render_ilots.py circuits_industriels/signal_conditioning.xml`
Expected: 4 PNG dans `build_rebuild/ilots_render/` sans exception.

- [ ] **Step 2: Inspection visuelle**

Ouvrir `00_*.png` (gros îlot) : vérifier — pas de colonne `NC`, lignes de bus rognées (pas pleine hauteur), AOP en triangles non chevauchants, étiquettes ref/valeur lisibles, caption présente.

- [ ] **Step 3: Suite complète**

Run: `python -m pytest -q`
Expected: vert (ajustement attendu du compte par rapport à la référence).

- [ ] **Step 4: Commit éventuel** (si retouches visuelles)

```bash
git add gui/circuit_viewer.py
git commit -m "fix(viewer): retouches lisibilite schema d'ilot"
```

---

## Self-Review

- **Spec coverage :** §1 filtrage→Task 1 ; §2 extent+ordre+convention→Task 2+caption Task 4 ; §3 lignes sans collision→Task 3 (espacement) ; §4 AOP/blocs→Task 4 ; §5 refactor pur→Task 1-3. Tests spec 1-7 couverts (NC, stub/col, extent, ordre, AOP, non-régression, fumée gros îlot).
- **Placeholders :** aucun — code complet par étape.
- **Type consistency :** `plan` = `{label, columns:[{net,x,kind,y_top,y_bottom}], rows:[{ref,type,value,symbol,y,pins,stubs}], caption}` cohérent Task 1→4 ; `_layout_columns`, `_net_kind`, `_schematic_symbol`, `_SYMBOL_ELM`, `_draw_*` noms cohérents.
