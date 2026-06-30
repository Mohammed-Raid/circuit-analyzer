# Chaîne de schémas connectés (vue îlot multi-AOP) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afficher un îlot à plusieurs AOP comme une chaîne de schémas dédiés reliés OUT→IN, lisible de gauche à droite, avec défilement horizontal et boîtes Z cliquables.

**Architecture:** Tout est dans `gui/circuit_viewer.py`. Un helper ordonne les montages par flux de signal ; les 3 drawers partagés gagnent un `origin` + libellés paramétrables et renvoient leurs points IN/OUT ; un orchestrateur pose les blocs côte à côte et tire les fils ; `show_island` route les îlots multi-AOP vers un nouveau builder de figure dans un conteneur scrollable.

**Tech Stack:** Python, schemdraw 0.22, matplotlib, customtkinter (CTk), pytest.

## Global Constraints

- Aucun commit ne porte `Co-Authored-By Claude` (directive utilisateur).
- Repli obligatoire : tout îlot non résoluble (mono-actif, passif, branche, montage sans drawer) garde EXACTEMENT le comportement actuel.
- Hauteur de figure bornée comme l'existant (`haut = 4.2`) ; la largeur, elle, peut croître (défilement horizontal).
- Drawers rétro-compatibles : appelés sans `origin`, ils se comportent comme aujourd'hui.
- Tests lancés avec `$env:PYTHONUTF8=1` sous PowerShell (accents).

---

### Task 1 : Ordonnancement des montages par flux

**Files:**
- Modify: `gui/circuit_viewer.py` (ajouter `_ordonner_montages_flux` près de `_matches_for_island`, ~ligne 664)
- Test: `tests/test_chaine_ilot.py` (créer)

**Interfaces:**
- Consumes: les matches de `detecteur.analyser` (clés `nodes`, `impedances`).
- Produces: `_ordonner_montages_flux(matches: list[dict]) -> list[dict] | None`
  — liste des montages triés entrée→sortie, ou `None` si ce n'est pas une chaîne linéaire unique.

- [ ] **Step 1 : Écrire le test qui échoue**

```python
# tests/test_chaine_ilot.py
"""@file test_chaine_ilot.py
@brief Vue îlot multi-AOP : ordonnancement par flux + chaîne de schémas connectés."""
from circuit_analyzer.xml import lire_xml
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser
from gui import circuit_viewer as cv


def _matches_chaine():
    comps = lire_xml("circuits_industriels/chaine_5_aop.xml")
    res = analyser(construire_graphe(comps))
    return [r for r in res if "(AOP)" in r["circuit_type"]]


def test_ordonner_montages_flux_chaine_5():
    ordre = cv._ordonner_montages_flux(_matches_chaine())
    assert ordre is not None
    types = [m["circuit_type"] for m in ordre]
    assert types == [
        "Amplificateur non-inverseur (AOP)",
        "Amplificateur inverseur (AOP)",
        "Intégrateur (AOP)",
        "Dérivateur (AOP)",
        "Suiveur de tension (AOP)",
    ]


def test_ordonner_montages_flux_non_chaine_renvoie_none():
    # Deux montages sans lien OUT->IN entre eux : pas une chaîne.
    from circuit_analyzer.composant import Composant
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M1", "OUT": "O1"}),
        Composant("R1", "R", {"1": "VIN", "2": "M1"}, "1k"),
        Composant("R2", "R", {"1": "M1", "2": "O1"}, "10k"),
        Composant("U2", "U", {"IN+": "GND", "IN-": "M2", "OUT": "O2"}),
        Composant("R3", "R", {"1": "AUTRE", "2": "M2"}, "1k"),
        Composant("R4", "R", {"1": "M2", "2": "O2"}, "10k"),
    ]
    res = analyser(construire_graphe(comps))
    aops = [r for r in res if "(AOP)" in r["circuit_type"]]
    assert cv._ordonner_montages_flux(aops) is None
```

- [ ] **Step 2 : Lancer le test → échec**

Run: `$env:PYTHONUTF8=1; python -m pytest tests/test_chaine_ilot.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute '_ordonner_montages_flux'`

- [ ] **Step 3 : Implémenter le helper**

Insérer après `_matches_for_island` (~ligne 664) dans `gui/circuit_viewer.py` :

```python
def _ordonner_montages_flux(matches):
    """@brief Ordonne des montages AOP par flux de signal (OUT(N) -> IN(N+1)).

    Pour chaque montage : out_net = net de la broche OUT (= nodes[-1]) ; in_net =
    nœud extérieur de Zin si présent (inverseur/intégrateur/dérivateur), sinon le
    net IN+ (= nodes[0], non-inverseur/suiveur). On relie i->j quand
    out_net(i) == in_net(j), puis on suit la chaîne depuis l'unique étage dont
    l'entrée n'est alimentée par aucun autre.

    @param matches Liste des matches de montages d'un même îlot.
    @return list[dict] | None Montages triés entrée->sortie, ou None si ce n'est
            pas une chaîne linéaire unique couvrant tous les montages.
    """
    if len(matches) < 2:
        return None

    def out_net(m):
        return m["nodes"][-1]

    def in_net(m):
        imp = m.get("impedances") or {}
        if "Zin" in imp:
            return imp["Zin"]["nodes"][1]
        return m["nodes"][0]

    par_in = {}
    for m in matches:
        par_in.setdefault(in_net(m), []).append(m)
    outs = {out_net(m) for m in matches}

    # Tête de chaîne : un montage dont l'entrée n'est la sortie d'aucun autre.
    tetes = [m for m in matches if in_net(m) not in outs]
    if len(tetes) != 1:
        return None

    ordre = []
    vus = set()
    courant = tetes[0]
    while courant is not None and id(courant) not in vus:
        ordre.append(courant)
        vus.add(id(courant))
        suivants = par_in.get(out_net(courant), [])
        if len(suivants) > 1:
            return None                      # bifurcation : pas une chaîne linéaire
        courant = suivants[0] if suivants else None

    if len(ordre) != len(matches):
        return None                          # tous les montages ne sont pas chaînés
    return ordre
```

- [ ] **Step 4 : Lancer le test → succès**

Run: `$env:PYTHONUTF8=1; python -m pytest tests/test_chaine_ilot.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5 : Commit**

```bash
git add tests/test_chaine_ilot.py gui/circuit_viewer.py
git commit -m "feat(ilot): ordonnancement des montages AOP par flux de signal"
```

---

### Task 2 : Drawers paramétrables (origin + libellés + ancres IN/OUT)

**Files:**
- Modify: `gui/circuit_viewer.py` — `_draw_aop_inverseur_zin_zf` (~1296), `_draw_aop_non_inverseur_zf_zg` (~1345), `_draw_follower` (~1428)
- Test: `tests/test_chaine_ilot.py`

**Interfaces:**
- Produces (signatures rétro-compatibles, valeur de retour ignorable) :
  - `_draw_aop_inverseur_zin_zf(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT") -> {"in": (x,y), "out": (x,y)}`
  - `_draw_aop_non_inverseur_zf_zg(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT") -> {"in": (x,y), "out": (x,y)}`
  - `_draw_follower(d, result, ci, origin=(4.5, 0), in_label="IN", out_label="OUT") -> {"in": (x,y), "out": (x,y)}`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `tests/test_chaine_ilot.py` :

```python
import schemdraw


def _imp_inv():
    return {"Zin": {"refs": ["R3"], "composition": "R3", "nodes": ("M", "A")},
            "Zf": {"refs": ["R4"], "composition": "R4", "nodes": ("M", "B")}}


def test_drawer_inverseur_renvoie_ancres_et_suit_origin():
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        a0 = cv._draw_aop_inverseur_zin_zf(d, _imp_inv(), {}, origin=(0, 0))
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        a10 = cv._draw_aop_inverseur_zin_zf(d, _imp_inv(), {}, origin=(10, 0))
    assert set(a0) == {"in", "out"}
    assert a0["out"][0] > a0["in"][0]                 # OUT à droite de IN
    assert abs(a10["in"][0] - a0["in"][0] - 10) < 1e-6  # l'origine décale tout de +10
```

- [ ] **Step 2 : Lancer le test → échec**

Run: `$env:PYTHONUTF8=1; python -m pytest tests/test_chaine_ilot.py::test_drawer_inverseur_renvoie_ancres_et_suit_origin -q`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'origin'`

- [ ] **Step 3 : Modifier `_draw_aop_inverseur_zin_zf`**

Remplacer la signature et le corps (la partie placement + le `return`). Nouvelle version complète :

```python
def _draw_aop_inverseur_zin_zf(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT"):
    """@brief Dessin commun des montages à topologie inverseuse : AOP + Zin/Zf cliquables.

    Partagé par l'ampli inverseur, l'intégrateur, le dérivateur (même structure :
    Zin sur IN-, Zf de IN- vers OUT, IN+ à la masse).

    @param origin Position de l'AOP (pour chaîner plusieurs montages).
    @param in_label/out_label Libellés d'entrée/sortie ("" pour les masquer).
    @return dict {"in": (x,y), "out": (x,y)} : points de connexion du bloc.
    """
    zin, zf = imp["Zin"], imp["Zf"]
    op = d.add(elm.Opamp().anchor("in1").at(origin).color(_WIRE).fill(_OPAMP_FILL))
    in1, out = op.in1, op.out

    noeud = (in1[0] - 1.3, in1[1])
    d.add(elm.Line().at(noeud).to(in1).color(_WIRE))
    d.add(elm.Dot().at(noeud).color(_WIRE))

    zin_p1 = (noeud[0] - 3.0, noeud[1])
    d.add(elm.ResistorIEC().at(zin_p1).to(noeud).color(_Z_EDGE).fill(_Z_FILL).label(
        _z_label("Zin", zin, ci), loc="top", color=_Z_EDGE))
    d.add(elm.Line().at(zin_p1).left(0.7).color(_WIRE))
    in_pt = (zin_p1[0] - 0.7, zin_p1[1])
    d.add(elm.Dot().at(in_pt).color(_WIRE).label(in_label, loc="left", color=_WIRE))
    # IN+ à la masse
    d.add(elm.Line().at(op.in2).left(1.0).color(_WIRE))
    d.add(elm.Ground().color(_WIRE))
    # Zf : contre-réaction nœud -> OUT
    above_y = in1[1] + 2.0
    d.add(elm.Line().at(noeud).up(above_y - noeud[1]).color(_WIRE))
    zf_p1, zf_p2 = (noeud[0], above_y), (out[0], above_y)
    d.add(elm.ResistorIEC().at(zf_p1).to(zf_p2).color(_Z_EDGE).fill(_Z_FILL).label(
        _z_label("Zf", zf, ci), loc="top", color=_Z_EDGE))
    d.add(elm.Line().at(zf_p2).toy(out[1]).color(_WIRE))
    out_pt = (out[0] + 1.0, out[1])
    d.add(elm.Line().at(out).to(out_pt).color(_WIRE).label(out_label, loc="right", color=_WIRE))

    hb = getattr(d, "_z_hitboxes", None)
    if hb is not None:
        pad = 0.5
        hb.append((min(zin_p1[0], noeud[0]) - pad, max(zin_p1[0], noeud[0]) + pad,
                   noeud[1] - pad, noeud[1] + pad, list(zin["refs"]), zin["composition"]))
        hb.append((min(zf_p1[0], zf_p2[0]) - pad, max(zf_p1[0], zf_p2[0]) + pad,
                   above_y - pad, above_y + pad, list(zf["refs"]), zf["composition"]))
    return {"in": in_pt, "out": out_pt}
```

- [ ] **Step 4 : Modifier `_draw_aop_non_inverseur_zf_zg`**

```python
def _draw_aop_non_inverseur_zf_zg(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT"):
    """@brief Dessin du non-inverseur : signal sur IN+, pont Zf/Zg cliquable sur IN-.

    @param origin/in_label/out_label cf. _draw_aop_inverseur_zin_zf.
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    zf, zg = imp["Zf"], imp["Zg"]
    op = d.add(elm.Opamp().anchor("in2").at(origin).color(_WIRE).fill(_OPAMP_FILL))
    in1, out = op.in1, op.out

    d.add(elm.Line().at(op.in2).left(1.2).color(_WIRE))
    in_pt = (op.in2[0] - 1.2, op.in2[1])
    d.add(elm.Dot().at(in_pt).color(_WIRE).label(in_label, loc="left", color=_WIRE))

    noeud = (in1[0] - 1.3, in1[1])
    d.add(elm.Line().at(noeud).to(in1).color(_WIRE))
    d.add(elm.Dot().at(noeud).color(_WIRE))

    above_y = in1[1] + 2.0
    d.add(elm.Line().at(noeud).up(above_y - noeud[1]).color(_WIRE))
    zf_p1, zf_p2 = (noeud[0], above_y), (out[0], above_y)
    d.add(elm.ResistorIEC().at(zf_p1).to(zf_p2).color(_Z_EDGE).fill(_Z_FILL).label(
        _z_label("Zf", zf, ci), loc="top", color=_Z_EDGE))
    d.add(elm.Line().at(zf_p2).toy(out[1]).color(_WIRE))
    out_pt = (out[0] + 1.0, out[1])
    d.add(elm.Line().at(out).to(out_pt).color(_WIRE).label(out_label, loc="right", color=_WIRE))

    zg_p1 = (noeud[0] - 3.0, noeud[1])
    d.add(elm.ResistorIEC().at(zg_p1).to(noeud).color(_Z_EDGE).fill(_Z_FILL).label(
        _z_label("Zg", zg, ci), loc="top", color=_Z_EDGE))
    d.add(elm.Line().at(zg_p1).left(0.5).color(_WIRE))
    d.add(elm.Ground().color(_WIRE))

    hb = getattr(d, "_z_hitboxes", None)
    if hb is not None:
        pad = 0.5
        hb.append((min(zf_p1[0], zf_p2[0]) - pad, max(zf_p1[0], zf_p2[0]) + pad,
                   above_y - pad, above_y + pad, list(zf["refs"]), zf["composition"]))
        hb.append((min(zg_p1[0], noeud[0]) - pad, max(zg_p1[0], noeud[0]) + pad,
                   noeud[1] - pad, noeud[1] + pad, list(zg["refs"]), zg["composition"]))
    return {"in": in_pt, "out": out_pt}
```

- [ ] **Step 5 : Modifier `_draw_follower`**

```python
def _draw_follower(d, result, ci, origin=(4.5, 0), in_label="IN", out_label="OUT"):
    """@brief Dessine le schéma « Suiveur de tension (AOP) ».

    @param origin/in_label/out_label cf. _draw_aop_inverseur_zin_zf.
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    op = d.add(elm.Opamp().anchor("in2").at(origin))
    d.add(elm.Line().at(op.in2).left(1.2))
    in_pt = (op.in2[0] - 1.2, op.in2[1])
    d.add(elm.Dot().at(in_pt).label(in_label, loc="left"))

    out_pt0 = op.out
    in1_pt = op.in1
    top_y = in1_pt[1] + 1.2
    d.add(elm.Line().at(out_pt0).right(0.6))
    d.add(elm.Line().toy(top_y))
    d.add(elm.Line().tox(in1_pt[0]))
    d.add(elm.Line().toy(in1_pt[1]))
    d.add(elm.Dot().at(out_pt0))
    out_pt = (out_pt0[0] + 1.0, out_pt0[1])
    d.add(elm.Line().at(out_pt0).to(out_pt).label(out_label, loc="right"))
    return {"in": in_pt, "out": out_pt}
```

- [ ] **Step 6 : Lancer les tests + non-régression rendu → succès**

Run: `$env:PYTHONUTF8=1; python -m pytest tests/test_chaine_ilot.py -q`
Expected: PASS

Vérifier que les vues mono-montage rendent encore (les appelants n'utilisent pas `origin`) :
Run: `$env:PYTHONUTF8=1; python -m pytest -q`
Expected: tout vert (aucune régression).

- [ ] **Step 7 : Commit**

```bash
git add tests/test_chaine_ilot.py gui/circuit_viewer.py
git commit -m "feat(viewer): drawers AOP parametrables (origin, libelles) renvoyant leurs ancres IN/OUT"
```

---

### Task 3 : Dispatcher + orchestrateur de chaîne

**Files:**
- Modify: `gui/circuit_viewer.py` (ajouter `_dessiner_montage_a` et `_draw_island_chain` après `_draw_follower`)
- Test: `tests/test_chaine_ilot.py`

**Interfaces:**
- Consumes: `_ordonner_montages_flux` (Task 1), les 3 drawers (Task 2).
- Produces:
  - `_dessiner_montage_a(d, match, ci, origin, in_label, out_label) -> {"in", "out"}`
  - `_draw_island_chain(d, ordered, ci)` — dessine tous les blocs + fils ; renseigne `d._z_hitboxes`.

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `tests/test_chaine_ilot.py` :

```python
def test_draw_island_chain_hitboxes_et_ordre():
    comps = lire_xml("circuits_industriels/chaine_5_aop.xml")
    res = analyser(construire_graphe(comps))
    ci = {c.ref: {"type": c.type, "value": c.value} for c in comps}
    ordre = cv._ordonner_montages_flux([r for r in res if "(AOP)" in r["circuit_type"]])
    with schemdraw.Drawing(show=False) as d:
        d._z_hitboxes = []
        cv._draw_island_chain(d, ordre, ci)
        hb = list(d._z_hitboxes)
    # non-inv(2) + inverseur(2) + intégrateur(2) + dérivateur(2) + suiveur(0) = 8
    assert len(hb) == 8
    # les boîtes Z se décalent vers la droite d'un étage à l'autre (centres x croissants
    # globalement) : le x max d'une hitbox dépasse largement le x min de la première.
    xs = [(x0 + x1) / 2 for x0, x1, *_ in hb]
    assert max(xs) - min(xs) > 10
```

- [ ] **Step 2 : Lancer le test → échec**

Run: `$env:PYTHONUTF8=1; python -m pytest tests/test_chaine_ilot.py::test_draw_island_chain_hitboxes_et_ordre -q`
Expected: FAIL — `AttributeError: ... '_draw_island_chain'`

- [ ] **Step 3 : Implémenter dispatcher + orchestrateur**

Insérer après `_draw_follower` :

```python
_CHAINE_DX = 10.0     # pas horizontal entre deux blocs de montage (largeur bloc + marge)


def _dessiner_montage_a(d, match, ci, origin, in_label, out_label):
    """@brief Dessine un montage à `origin` via son drawer partagé ; renvoie ses ancres.

    @return dict {"in": (x,y), "out": (x,y)}.
    """
    imp = match.get("impedances") or {}
    if "Zg" in imp:
        return _draw_aop_non_inverseur_zf_zg(d, imp, ci, origin, in_label, out_label)
    if "Zin" in imp:
        return _draw_aop_inverseur_zin_zf(d, imp, ci, origin, in_label, out_label)
    return _draw_follower(d, match, ci, origin, in_label, out_label)


def _draw_island_chain(d, ordered, ci):
    """@brief Dessine une chaîne de montages reliés OUT(N) -> IN(N+1).

    Chaque montage est posé à un x croissant ; un fil en Z relie la sortie d'un
    bloc à l'entrée du suivant. Premier bloc étiqueté VIN, dernier VOUT, internes
    sans libellé. Les boîtes Z poussent leurs hitboxes (coords absolues) -> le
    drill-down R/L/C reste cliquable.
    """
    n = len(ordered)
    ancres = []
    for i, match in enumerate(ordered):
        in_label = "VIN" if i == 0 else ""
        out_label = "VOUT" if i == n - 1 else ""
        origin = (4.5 + i * _CHAINE_DX, 0)
        ancres.append(_dessiner_montage_a(d, match, ci, origin, in_label, out_label))

    for i in range(n - 1):
        out_pt = ancres[i]["out"]
        in_pt = ancres[i + 1]["in"]
        mx = (out_pt[0] + in_pt[0]) / 2          # fil en Z : horizontal, vertical, horizontal
        d.add(elm.Line().at(out_pt).to((mx, out_pt[1])).color(_WIRE))
        d.add(elm.Line().at((mx, out_pt[1])).to((mx, in_pt[1])).color(_WIRE))
        d.add(elm.Line().at((mx, in_pt[1])).to(in_pt).color(_WIRE))
```

- [ ] **Step 4 : Lancer le test → succès**

Run: `$env:PYTHONUTF8=1; python -m pytest tests/test_chaine_ilot.py::test_draw_island_chain_hitboxes_et_ordre -q`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add tests/test_chaine_ilot.py gui/circuit_viewer.py
git commit -m "feat(ilot): orchestrateur de chaine de montages relies OUT->IN"
```

---

### Task 4 : Figure de chaîne + branchement scrollable dans `show_island`

**Files:**
- Modify: `gui/circuit_viewer.py` — ajouter `_make_chain_fig` (après `_make_fig`, ~593) ; brancher dans `show_island` (~415-432)
- Test: `tests/test_chaine_ilot.py`

**Interfaces:**
- Consumes: `_ordonner_montages_flux`, `_draw_island_chain`.
- Produces: `_make_chain_fig(ordered, comp_info) -> matplotlib.figure.Figure`
  (porte `fig._z_hitboxes`).

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `tests/test_chaine_ilot.py` :

```python
def test_make_chain_fig_porte_les_hitboxes():
    comps = lire_xml("circuits_industriels/chaine_5_aop.xml")
    res = analyser(construire_graphe(comps))
    ci = {c.ref: {"type": c.type, "value": c.value} for c in comps}
    ordre = cv._ordonner_montages_flux([r for r in res if "(AOP)" in r["circuit_type"]])
    fig = cv._make_chain_fig(ordre, ci)
    assert len(getattr(fig, "_z_hitboxes", [])) == 8
    w, h = fig.get_size_inches()
    assert h <= 4.2 + 1e-6        # hauteur bornée (tient dans la fenêtre)
    assert w > h                  # figure large (chaîne) -> défilement horizontal
```

- [ ] **Step 2 : Lancer le test → échec**

Run: `$env:PYTHONUTF8=1; python -m pytest tests/test_chaine_ilot.py::test_make_chain_fig_porte_les_hitboxes -q`
Expected: FAIL — `AttributeError: ... '_make_chain_fig'`

- [ ] **Step 3 : Implémenter `_make_chain_fig`**

Insérer après `_make_fig` (~ligne 593). Calque sur `_make_fig` mais sans plafond d'aspect (la largeur peut être grande) :

```python
def _make_chain_fig(ordered, comp_info):
    """@brief Figure d'une chaîne de montages connectés (vue îlot multi-AOP).

    Large par construction (un bloc par étage) : destinée à un conteneur à
    défilement horizontal. Hauteur bornée à 4.2" pour tenir dans la fenêtre.

    @param ordered Montages triés par flux (cf. _ordonner_montages_flux).
    @param comp_info Dict {ref -> {type, value}}.
    @return matplotlib.figure.Figure (porte fig._z_hitboxes).
    """
    fig = Figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")
    fig._z_hitboxes = []
    try:
        with schemdraw.Drawing(canvas=ax, show=False) as d:
            d.config(fontsize=12, inches_per_unit=0.5)
            d._z_hitboxes = []
            _draw_island_chain(d, ordered, ci=comp_info)
            fig._z_hitboxes = list(d._z_hitboxes)
            try:
                bb = d.get_bbox()
                w, h = (bb.xmax - bb.xmin), (bb.ymax - bb.ymin)
                if w > 0 and h > 0:
                    haut = 4.2
                    fig.set_size_inches(haut * (w / h), haut)   # PAS de plafond : large -> scroll
            except Exception:
                pass
    except Exception as e:
        ax.text(0.5, 0.5, f"Schéma non disponible\n{e}", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color="#64748b")
    if fig._z_hitboxes:
        ax.text(0.005, 0.01, "Astuce : cliquez une boîte Z pour voir le détail R/L/C",
                transform=ax.transAxes, fontsize=9, color="#64748b", va="bottom", ha="left")
    ax.margins(0.04)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        pass
    return fig
```

Note : `_draw_island_chain` prend `ci=` en mot-clé ; l'appel ci-dessus passe `ci=comp_info`.

- [ ] **Step 4 : Lancer le test → succès**

Run: `$env:PYTHONUTF8=1; python -m pytest tests/test_chaine_ilot.py::test_make_chain_fig_porte_les_hitboxes -q`
Expected: PASS

- [ ] **Step 5 : Brancher dans `show_island` (conteneur scrollable horizontal)**

Dans `show_island`, repérer le bloc (~415-432) :

```python
    principal = _circuit_principal_ilot(ilot, graph, results)
    _sp = _arbre_serie_parallele_ilot(ilot, graph) if principal is None else None
    _pont = _pont_ilot(ilot, graph) if (principal is None and _sp is None) else None
    if principal is not None:
        fig = _make_fig(principal, comp_info, _DRAWERS[principal["circuit_type"]])
    elif _sp is not None:
        from gui import impedance_schematic
        _arbre, _comps = _sp
        fig = impedance_schematic.dessiner_bloc(_arbre, "VIN", "VOUT", _comps)
    elif _pont is not None:
        from gui import impedance_schematic
        _pont_struct, _comps = _pont
        fig = impedance_schematic.dessiner_pont(_pont_struct, _comps)
    else:
        matches = _matches_for_island(ilot, results)
        fig = _make_island_fig(model, matches=matches)
    canvas_frame = ctk.CTkFrame(popup, fg_color=SCH_BG, corner_radius=10)
    canvas_frame.pack(fill="both", expand=True, padx=14, pady=(4, 0))

    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().configure(bg=SCH_BG, highlightthickness=0)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
```

Le remplacer par (ajoute la branche chaîne + un conteneur scrollable quand la
figure est plus large que la fenêtre) :

```python
    principal = _circuit_principal_ilot(ilot, graph, results)
    _sp = _arbre_serie_parallele_ilot(ilot, graph) if principal is None else None
    _pont = _pont_ilot(ilot, graph) if (principal is None and _sp is None) else None
    _chaine = None
    if principal is None and _sp is None and _pont is None:
        _chaine = _ordonner_montages_flux(_matches_for_island(ilot, results))
    if principal is not None:
        fig = _make_fig(principal, comp_info, _DRAWERS[principal["circuit_type"]])
    elif _sp is not None:
        from gui import impedance_schematic
        _arbre, _comps = _sp
        fig = impedance_schematic.dessiner_bloc(_arbre, "VIN", "VOUT", _comps)
    elif _pont is not None:
        from gui import impedance_schematic
        _pont_struct, _comps = _pont
        fig = impedance_schematic.dessiner_pont(_pont_struct, _comps)
    elif _chaine is not None:
        fig = _make_chain_fig(_chaine, comp_info)
    else:
        matches = _matches_for_island(ilot, results)
        fig = _make_island_fig(model, matches=matches)
    canvas_frame = ctk.CTkFrame(popup, fg_color=SCH_BG, corner_radius=10)
    canvas_frame.pack(fill="both", expand=True, padx=14, pady=(4, 0))

    # La chaîne est large : on la met dans un cadre à défilement horizontal pour
    # lire le signal de gauche à droite sans rogner. Les autres vues remplissent.
    if _chaine is not None:
        scroll = ctk.CTkScrollableFrame(canvas_frame, orientation="horizontal",
                                        fg_color=SCH_BG)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        master = scroll
    else:
        master = canvas_frame

    canvas = FigureCanvasTkAgg(fig, master=master)
    canvas.draw()
    canvas.get_tk_widget().configure(bg=SCH_BG, highlightthickness=0)
    if _chaine is not None:
        canvas.get_tk_widget().pack(padx=4, pady=4)        # taille native -> scroll
    else:
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
```

- [ ] **Step 6 : Vérifier la suite complète + rendu de preuve**

Run: `$env:PYTHONUTF8=1; python -m pytest -q`
Expected: tout vert.

Rendu de preuve (figure de chaîne) dans le dossier temp :

```bash
$env:PYTHONUTF8=1; python -c "import tempfile,os; from circuit_analyzer.xml import lire_xml; from circuit_analyzer.composant import construire_graphe; from circuit_analyzer.detecteur import analyser; from gui import circuit_viewer as cv; comps=lire_xml('circuits_industriels/chaine_5_aop.xml'); res=analyser(construire_graphe(comps)); ci={c.ref:{'type':c.type,'value':c.value} for c in comps}; ordre=cv._ordonner_montages_flux([r for r in res if '(AOP)' in r['circuit_type']]); fig=cv._make_chain_fig(ordre,ci); out=os.path.join(tempfile.gettempdir(),'chaine_connectee_proof.png'); fig.savefig(out,dpi=100,bbox_inches='tight'); print(out)"
```

Inspecter le PNG : 5 blocs alignés gauche→droite, fils OUT→IN entre eux, VIN à gauche / VOUT à droite, boîtes Z présentes.

- [ ] **Step 7 : Commit**

```bash
git add tests/test_chaine_ilot.py gui/circuit_viewer.py
git commit -m "feat(ilot): vue chaine de schemas connectes (defilement horizontal) pour les ilots multi-AOP"
```

---

## Self-Review

- **Couverture spec :** ordonnancement (T1), drawers paramétrables + ancres (T2), dispatcher + orchestrateur + fils (T3), figure + scroll + branchement + repli (T4), tests (chaque tâche). ✓
- **Repli :** `show_island` ne prend la branche chaîne que si `principal`, `_sp`, `_pont` sont tous None ET `_ordonner_montages_flux` renvoie une liste — sinon `_make_island_fig`. Les îlots mono-actif/passifs sont court-circuités avant. ✓
- **Types cohérents :** les drawers renvoient `{"in","out"}` (tuples) ; `_draw_island_chain` lit `ancres[i]["out"]` / `["in"]` ; `_make_chain_fig` appelle `_draw_island_chain(d, ordered, ci=comp_info)`. ✓
- **Pas de placeholder :** tout le code est fourni. ✓
- **Risque connu :** `CTkScrollableFrame(orientation="horizontal")` — vérifié au Step 6 (rendu) + test manuel app ; si la version de CTk ne gère pas l'orientation, repli simple : `canvas_frame` direct (la figure restera large mais le reste fonctionne).
