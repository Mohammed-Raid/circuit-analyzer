# Dessins : ponts composites + drill-down + étiquettes — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) dessiner les ponts à bras composites (boîte Z + composition), (2) clic-pour-déplier les Z composites dans la vue d'îlot ET la fenêtre Impédance, (3) étiquettes de valeurs formatées avec unité.

**Architecture:** `formater_valeur` (pur) formate les valeurs. `detecter_pont` réduit les bras (série/parallèle) avant de reconnaître le motif, et expose par bras `{refs, composition}`. `dessiner`/`dessiner_pont` utilisent ces infos pour labels + hitboxes. La fenêtre Impédance dessine le pont et branche le clic.

**Tech Stack:** Python ; networkx ; schemdraw + matplotlib (existants).

## Global Constraints

- Aucun commit ne porte `Co-Authored-By Claude` (directive utilisateur).
- Aucune nouvelle dépendance.
- Branche : `rewrite-simple`.
- NE PAS modifier `_make_island_fig`, `_build_island_model`, `_draw_island_schematic`, ni `_arbre_serie_parallele_ilot`/`agencer`. La vue d'îlot (`show_island`) n'a AUCUN changement (son `_on_click` lit déjà `fig._z_hitboxes`).
- Suite complète verte (21 tests d'îlot inclus).

## File Structure

- `circuit_analyzer/impedance.py` : ajouter `formater_valeur` ; généraliser `detecter_pont` (bras composites + nouveau contrat `bras[role] = {"refs","composition"}`).
- `gui/impedance_schematic.py` : labels formatés dans `dessiner` ; `dessiner_pont` gère simple/composite + `_z_hitboxes`.
- `gui/impedance_view.py` : dessiner le pont quand `arbre is None` + handler de clic.
- Tests : `tests/test_impedance.py`, `tests/test_impedance_schematic.py`.

---

### Task 1 : `formater_valeur` (étiquettes pro)

**Files:** Modify `circuit_analyzer/impedance.py` (après `_parse_valeur`) ; Test `tests/test_impedance.py`.

**Interfaces:** Produces `formater_valeur(value: str, typ: str) -> str`.

- [ ] **Step 1 : Test qui échoue** — ajouter à la fin de `tests/test_impedance.py` :

```python
def test_formater_valeur_avec_unite():
    assert impedance.formater_valeur("10k", "R") == "10 kΩ"
    assert impedance.formater_valeur("100n", "C") == "100 nF"
    assert impedance.formater_valeur("1m", "L") == "1 mH"
    assert impedance.formater_valeur("470", "R") == "470 Ω"
    assert impedance.formater_valeur("", "R") == ""
    assert impedance.formater_valeur("abc", "R") == "abc"  # non interpretable -> tel quel
```

- [ ] **Step 2 : Vérifier l'échec** — `python -m pytest tests/test_impedance.py -q -k formater_valeur` → FAIL (AttributeError).

- [ ] **Step 3 : Implémenter** — ajouter dans `circuit_analyzer/impedance.py` après `_parse_valeur` :

```python
_UNITES = {"R": "Ω", "L": "H", "C": "F"}


def formater_valeur(value: str, typ: str) -> str:
    """@brief Valeur ingénieur + unité pour étiquette (« 10k »,R → « 10 kΩ »).

    @param value Chaîne valeur ; vide → "".
    @param typ Type composant (R→Ω, L→H, C→F ; autre → sans unité).
    @return str Étiquette formatée, ou la valeur brute si non interprétable.
    """
    if not value:
        return ""
    m = re.match(r'\s*([0-9]*\.?[0-9]+)\s*([pnuµmkKMG]?)', value)
    if not m:
        return value
    return f"{m.group(1)} {m.group(2)}{_UNITES.get(typ, '')}".strip()
```

- [ ] **Step 4 : Vérifier le succès** — `python -m pytest tests/test_impedance.py -q -k formater_valeur` → PASS (1). Puis suite du fichier verte.

- [ ] **Step 5 : Commit**
```bash
git add circuit_analyzer/impedance.py tests/test_impedance.py
git commit -m "feat(impedance): formater_valeur - valeur ingenieur + unite pour les etiquettes"
```

---

### Task 2 : `detecter_pont` — bras composites + contrat `{refs, composition}`

**Files:** Modify `circuit_analyzer/impedance.py` (remplacer le corps de `detecter_pont`) ; Test `tests/test_impedance.py` (mettre à jour les tests existants + 1 nouveau).

**Interfaces:** `detecter_pont(graphe, a, b) -> dict | None` où `bras[role] = {"refs": [...], "composition": str}`. Consomme `_graphe_de_travail`, `_passe_serie`, `_passe_parallele` (déjà présents).

- [ ] **Step 1 : Tests** — dans `tests/test_impedance.py`, REMPLACER le corps de `test_detecter_pont_wheatstone` (les assertions sur `bras[...]`) par la version « contrat dict », et AJOUTER un test bras composite. La fonction `test_detecter_pont_wheatstone` devient :

```python
def test_detecter_pont_wheatstone():
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
    assert pont["gauche"] == "NET1"
    bras = pont["bras"]
    assert bras["haut_gauche"] == {"refs": ["R1"], "composition": "R1"}
    assert bras["haut_droite"] == {"refs": ["R2"], "composition": "R2"}
    assert bras["bas_gauche"] == {"refs": ["R3"], "composition": "R3"}
    assert bras["bas_droite"] == {"refs": ["R4"], "composition": "R4"}
    assert bras["pont"] == {"refs": ["R5"], "composition": "R5"}
```

Et AJOUTER :

```python
def test_detecter_pont_bras_composite():
    # Bras VIN-NET1 = R1+R6 (X interne degre 2 collapse en serie).
    g = _graphe(
        Composant("R1", "R", {"1": "VIN", "2": "X"}, "1k"),
        Composant("R6", "R", {"1": "X", "2": "NET1"}, "1k"),
        Composant("R2", "R", {"1": "VIN", "2": "NET2"}, "1k"),
        Composant("R3", "R", {"1": "NET1", "2": "VOUT"}, "1k"),
        Composant("R4", "R", {"1": "NET2", "2": "VOUT"}, "1k"),
        Composant("R5", "R", {"1": "NET1", "2": "NET2"}, "1k"),
    )
    pont = impedance.detecter_pont(g, "VIN", "VOUT")
    assert pont is not None
    hg = pont["bras"]["haut_gauche"]      # VIN-NET1 = bras composite
    assert set(hg["refs"]) == {"R1", "R6"}
    assert "+" in hg["composition"]
```

(`test_detecter_pont_serie_parallele_renvoie_none` et `test_detecter_pont_triangle_renvoie_none` restent inchangés.)

- [ ] **Step 2 : Vérifier l'échec** — `python -m pytest tests/test_impedance.py -q -k detecter_pont` → FAIL (les nouveaux asserts dict + bras composite ne passent pas avec l'ancien code).

- [ ] **Step 3 : Implémenter** — REMPLACER entièrement la fonction `detecter_pont` dans `circuit_analyzer/impedance.py` par :

```python
def detecter_pont(graphe, a, b):
    """@brief Reconnaît un motif pont (type Wheatstone) entre les bornes a et b.

    Les bras sont d'abord réduits (série/parallèle) : un bras composite (plusieurs
    R/L/C) devient une seule arête Z. Le motif retenu : 4 nœuds et 5 arêtes ; a et b
    de degré 2, non adjacents ; n1, n2 de degré 3, adjacents.

    @param graphe Graphe d'origine (arêtes R/L/C).
    @param a, b Les deux bornes (sommet haut / bas du losange).
    @return dict|None Structure du pont ; bras[role] = {"refs": [...], "composition": str}.
    """
    W = _graphe_de_travail(graphe)
    if a not in W or b not in W:
        return None
    bornes = {a, b}
    while True:
        if _passe_serie(W, bornes):
            continue
        if _passe_parallele(W, bornes):
            continue
        break
    if W.number_of_nodes() != 4 or W.number_of_edges() != 5:
        return None
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
    attendues = [(a, n1), (a, n2), (n1, b), (n2, b), (n1, n2)]
    if not all(W.has_edge(u, v) for u, v in attendues):
        return None

    def _bras(u, v):
        d = next(iter(W.get_edge_data(u, v).values()))
        return {"refs": list(d["refs"]), "composition": d["expr"]}

    return {
        "haut": a, "bas": b, "gauche": n1, "droite": n2,
        "bras": {
            "haut_gauche": _bras(a, n1),
            "haut_droite": _bras(a, n2),
            "bas_gauche": _bras(n1, b),
            "bas_droite": _bras(n2, b),
            "pont": _bras(n1, n2),
        },
    }
```

- [ ] **Step 4 : Vérifier le succès** — `python -m pytest tests/test_impedance.py -q -k detecter_pont` → PASS (4). Puis `python -m pytest tests/test_impedance.py -q` (pas de régression).

- [ ] **Step 5 : Commit**
```bash
git add circuit_analyzer/impedance.py tests/test_impedance.py
git commit -m "feat(impedance): detecter_pont gere les bras composites (refs+composition par bras)"
```

---

### Task 3 : labels formatés + `dessiner_pont` simple/composite + hitboxes

**Files:** Modify `gui/impedance_schematic.py` ; Test `tests/test_impedance_schematic.py`.

**Interfaces:** `dessiner_pont(pont, comps) -> Figure` (avec `fig._z_hitboxes`). Consomme `impedance.formater_valeur`, `impedance.formater_expr`, le nouveau contrat `bras[role] = {refs, composition}`.

- [ ] **Step 1 : Tests** — REMPLACER `test_dessiner_pont_produit_une_figure` dans `tests/test_impedance_schematic.py` par la version « contrat dict » + un test hitbox :

```python
def test_dessiner_pont_simple_pas_de_hitbox():
    from circuit_analyzer.composant import Composant
    comps = {r: Composant(r, "R", {"1": "x", "2": "y"}, "1k")
             for r in ("R1", "R2", "R3", "R4", "R5")}
    pont = {
        "haut": "VIN", "bas": "VOUT", "gauche": "N1", "droite": "N2",
        "bras": {role: {"refs": [r], "composition": r} for role, r in (
            ("haut_gauche", "R1"), ("haut_droite", "R2"), ("bas_gauche", "R3"),
            ("bas_droite", "R4"), ("pont", "R5"))},
    }
    fig = sch.dessiner_pont(pont, comps)
    assert fig is not None and len(fig.axes) == 1
    assert getattr(fig, "_z_hitboxes", []) == []   # tous simples -> aucun hitbox


def test_dessiner_pont_composite_a_un_hitbox():
    from circuit_analyzer.composant import Composant
    comps = {r: Composant(r, "R", {"1": "x", "2": "y"}, "1k")
             for r in ("R1", "R6", "R2", "R3", "R4", "R5")}
    pont = {
        "haut": "VIN", "bas": "VOUT", "gauche": "N1", "droite": "N2",
        "bras": {
            "haut_gauche": {"refs": ["R1", "R6"], "composition": "R1+R6"},
            "haut_droite": {"refs": ["R2"], "composition": "R2"},
            "bas_gauche": {"refs": ["R3"], "composition": "R3"},
            "bas_droite": {"refs": ["R4"], "composition": "R4"},
            "pont": {"refs": ["R5"], "composition": "R5"},
        },
    }
    fig = sch.dessiner_pont(pont, comps)
    boites = getattr(fig, "_z_hitboxes", [])
    assert len(boites) == 1
    x0, x1, y0, y1, refs, composition = boites[0]
    assert set(refs) == {"R1", "R6"}
```

- [ ] **Step 2 : Vérifier l'échec** — `python -m pytest tests/test_impedance_schematic.py -q -k dessiner_pont` → FAIL (l'ancien `_elem_arete`/`dessiner_pont` attend une ref string, pas un dict ; pas de `_z_hitboxes`).

- [ ] **Step 3 : Implémenter** — dans `gui/impedance_schematic.py` :

(a) Mettre à jour le label de feuille de `dessiner`. Repérer dans `dessiner` la ligne :
```python
            etiquette = f"{ref}\n{valeur}" if valeur else ref
```
La remplacer par :
```python
            from circuit_analyzer import impedance
            vfmt = impedance.formater_valeur(valeur, getattr(comp, "type", ""))
            etiquette = f"{ref}\n{vfmt}" if vfmt else ref
```

(b) REMPLACER `_elem_arete` et `dessiner_pont` par :

```python
def _elem_bras(bras, comps, p1, p2):
    """@brief (élément schemdraw, hitbox|None) pour un bras du pont.

    Bras simple (1 réf) : symbole du type + « ref\nvaleur ». Bras composite : boîte Z
    + composition lisible, et un hitbox (x0,x1,y0,y1,refs,composition).
    """
    from circuit_analyzer import impedance
    refs = bras["refs"]
    if len(refs) == 1:
        ref = refs[0]
        comp = comps.get(ref)
        cls = _SYMB.get(getattr(comp, "type", ""), elm.ResistorIEC)
        vfmt = impedance.formater_valeur(getattr(comp, "value", ""),
                                         getattr(comp, "type", ""))
        label = f"{ref}\n{vfmt}" if vfmt else ref
        return cls().at(p1).to(p2).label(label, loc="bottom", fontsize=9), None
    label = impedance.formater_expr(bras["composition"])
    el = elm.ResistorIEC().at(p1).to(p2).label(label, loc="bottom", fontsize=9)
    pad = 0.5
    hit = (min(p1[0], p2[0]) - pad, max(p1[0], p2[0]) + pad,
           min(p1[1], p2[1]) - pad, max(p1[1], p2[1]) + pad,
           list(refs), bras["composition"])
    return el, hit


def dessiner_pont(pont, comps):
    """@brief Figure matplotlib d'un pont (type Wheatstone) en losange.

    @param pont Structure de impedance.detecter_pont (bras = {refs, composition}).
    @param comps Dict {ref → Composant}.
    @return matplotlib.figure.Figure ; fig._z_hitboxes liste les boîtes Z composites.
    """
    haut, gauche, droite, bas = (0.0, 4.0), (-2.0, 2.0), (2.0, 2.0), (0.0, 0.0)
    bras = pont["bras"]
    segments = [
        (bras["haut_gauche"], haut, gauche),
        (bras["haut_droite"], haut, droite),
        (bras["bas_gauche"], gauche, bas),
        (bras["bas_droite"], droite, bas),
        (bras["pont"], gauche, droite),
    ]
    fig = Figure(figsize=(5.0, 5.5))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")

    hitboxes = []
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d.config(fontsize=10, inches_per_unit=0.5)
        for b, p1, p2 in segments:
            el, hit = _elem_bras(b, comps, p1, p2)
            d += el
            if hit is not None:
                hitboxes.append(hit)
        d += elm.Dot().at(haut).label(pont["haut"], loc="top", color=_BUS)
        d += elm.Dot().at(bas).label(pont["bas"], loc="bottom", color=_BUS)

    fig._z_hitboxes = hitboxes
    ax.margins(0.2)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        pass
    return fig
```

- [ ] **Step 4 : Vérifier le succès** — `python -m pytest tests/test_impedance_schematic.py -q` → tous PASS.

- [ ] **Step 5 : Commit**
```bash
git add gui/impedance_schematic.py tests/test_impedance_schematic.py
git commit -m "feat(impedance): pont a bras composites (boite Z + hitbox) + etiquettes formatees"
```

---

### Task 4 : fenêtre Impédance dessine le pont + clic-pour-déplier

**Files:** Modify `gui/impedance_view.py`. (Pas de test unitaire : glue tkinter — couverte par les tests des unités + import + run manuel.)

**Interfaces:** Consomme `impedance.detecter_pont`, `impedance_schematic.dessiner_pont`, `circuit_viewer.show_dipole_detail`.

- [ ] **Step 1 : Implémenter** — dans `gui/impedance_view.py`, fonction `_calculer`, REMPLACER le bloc actuel :

```python
        arbre = impedance.arbre_expr(expr)
        if arbre is None:
            lignes.append("Réseau en pont (Y-Δ) — pas de forme série/parallèle à dessiner.")
        else:
            fig = impedance_schematic.dessiner(arbre, a, b, graph.graph["components"])
            canvas = FigureCanvasTkAgg(fig, master=schema_holder)
            canvas.draw()
            canvas.get_tk_widget().configure(bg=SCH_BG, highlightthickness=0)
            canvas.get_tk_widget().pack(fill="both", expand=True)
        resultat.configure(text="\n".join(lignes), text_color="#34d399")
```

par :

```python
        arbre = impedance.arbre_expr(expr)
        pont = impedance.detecter_pont(graph, a, b) if arbre is None else None
        fig = None
        if arbre is not None:
            fig = impedance_schematic.dessiner(arbre, a, b, graph.graph["components"])
        elif pont is not None:
            fig = impedance_schematic.dessiner_pont(pont, graph.graph["components"])
            lignes.append("Réseau en pont — cliquez une boîte Z pour le détail.")
        else:
            lignes.append("Réseau en pont (Y-Δ) — pas de forme série/parallèle à dessiner.")
        if fig is not None:
            canvas = FigureCanvasTkAgg(fig, master=schema_holder)
            canvas.draw()
            canvas.get_tk_widget().configure(bg=SCH_BG, highlightthickness=0)
            canvas.get_tk_widget().pack(fill="both", expand=True)

            def _on_click(event, _fig=fig):
                if event.xdata is None or event.ydata is None:
                    return
                from gui import circuit_viewer
                for x0, x1, y0, y1, refs, composition in getattr(_fig, "_z_hitboxes", []):
                    if x0 <= event.xdata <= x1 and y0 <= event.ydata <= y1:
                        circuit_viewer.show_dipole_detail(refs, composition, graph, {}, win)
                        return

            canvas.mpl_connect("button_press_event", _on_click)
        resultat.configure(text="\n".join(lignes), text_color="#34d399")
```

- [ ] **Step 2 : Vérifier** —
  - `python -c "import gui.impedance_view; print('import ok')"`
  - `python -m pytest -q` (suite complète verte)

- [ ] **Step 3 : Commit**
```bash
git add gui/impedance_view.py
git commit -m "feat(viewer): fenetre Impedance dessine le pont + clic-pour-deplier les Z"
```

---

## Vérification finale

- `python -m pytest -q` vert.
- App : `impedance_pont_wheatstone.xml` → vue d'îlot ET fenêtre Impédance affichent le losange ; étiquettes formatées (« 1 kΩ »). Un pont à bras composite (R+C dans un bras) affiche une boîte Z ; clic dessus → détail des R/L/C.
- `impedance_serie_parallele.xml` → série/parallèle inchangé, mais étiquettes formatées.
- Aucun commit avec `Co-Authored-By Claude`.
