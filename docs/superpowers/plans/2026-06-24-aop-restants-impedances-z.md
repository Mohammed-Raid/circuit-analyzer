# Montages AOP restants — impédances Z cliquables — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner aux montages AOP différentiel, sommateur et bascule de Schmitt le drill-down « 1 AOP + Z au clic » (impédances cliquables), et polir le dessin du comparateur (sans Z).

**Architecture:** Le détecteur (`circuit_analyzer/detecteur.py`) possède la topologie et émet des *blocs* d'impédance `{'refs','composition','nodes'}`. Le drawer (`gui/circuit_viewer.py`) est du rendu pur : il dessine chaque bloc en boîte Z cliquable et enregistre sa hitbox. Un helper partagé `_z_box()` factorise le dessin+hitbox aujourd'hui dupliqué.

**Tech Stack:** Python, schemdraw (dessin), networkx (graphe), pytest.

## Global Constraints

- Pas de nouvelle dépendance (matplotlib/schemdraw/networkx déjà en place).
- Commits sans `Co-Authored-By: Claude` (règle utilisateur permanente).
- Repli gracieux : chaque drawer modifié garde son dessin fixe R/C actuel quand `result["impedances"]` est absent (motif déjà en place dans `_draw_integrator`).
- Bloc d'impédance = `{'refs': list[str], 'composition': str, 'nodes': (a, b)}`.
- Hitbox = tuple `(x_min, x_max, y_min, y_max, refs_list, composition)` appendé à `d._z_hitboxes`.
- Couleurs : `_WIRE`, `_Z_EDGE`, `_Z_FILL`, `_OPAMP_FILL` (déjà définies dans `circuit_viewer.py`).
- Lancer les tests avec `python -m pytest <chemin> -q`.

---

### Task 1: Helper partagé `_z_box()` + helper détecteur `_bloc_impedance()`

Factorise le dessin d'une boîte Z cliquable (drawer) et la construction d'un bloc d'impédance (détecteur). Aucun changement de comportement visuel : on réécrit les 2 drawers Z existants pour utiliser `_z_box`, et on vérifie que les tests de hitbox existants passent toujours.

**Files:**
- Modify: `gui/circuit_viewer.py` (ajout `_z_box`, réécriture interne de `_draw_aop_inverseur_zin_zf` et `_draw_aop_non_inverseur_zf_zg`)
- Modify: `circuit_analyzer/detecteur.py` (ajout `_bloc_impedance` après `_voisins_de_type`, ligne ~74)
- Test: `tests/test_circuit_viewer.py` (réutilise le test existant `test_draw_inverting_amp_deux_boites_z`)

**Interfaces:**
- Produces: `_z_box(d, p1, p2, name, bloc, ci, label_loc="top") -> None` — dessine une `ResistorIEC` bleue de `p1` à `p2`, étiquetée `_z_label(name, bloc, ci)`, et append la hitbox à `d._z_hitboxes` si présent.
- Produces: `_bloc_impedance(noeud, data, autre) -> dict` — `{'refs': list(data.get('refs',[data['ref']])), 'composition': data.get('composition', data['ref']), 'nodes': (noeud, autre)}`.

- [ ] **Step 1: Ajouter `_z_box` dans `gui/circuit_viewer.py`**

Insérer juste avant `_draw_aop_inverseur_zin_zf` (ligne ~1419) :

```python
def _z_box(d, p1, p2, name, bloc, ci, label_loc="top"):
    """@brief Dessine une boîte Z cliquable (ResistorIEC bleue) de p1 à p2 et
    enregistre sa hitbox sur d._z_hitboxes.

    @param d Dessin schemdraw.
    @param p1/p2 Extrémités de la boîte (x, y).
    @param name Préfixe d'étiquette (« Zin », « Zf »…).
    @param bloc Bloc d'impédance {'refs','composition','nodes'}.
    @param ci Dict {ref → {type, value}} pour l'étiquette.
    @param label_loc Position de l'étiquette schemdraw.
    @return None
    """
    d.add(elm.ResistorIEC().at(p1).to(p2).color(_Z_EDGE).fill(_Z_FILL).label(
        _z_label(name, bloc, ci), loc=label_loc, color=_Z_EDGE))
    hb = getattr(d, "_z_hitboxes", None)
    if hb is not None:
        pad = 0.5
        hb.append((min(p1[0], p2[0]) - pad, max(p1[0], p2[0]) + pad,
                   min(p1[1], p2[1]) - pad, max(p1[1], p2[1]) + pad,
                   list(bloc["refs"]), bloc["composition"]))
```

- [ ] **Step 2: Réécrire `_draw_aop_inverseur_zin_zf` pour utiliser `_z_box`**

Dans `_draw_aop_inverseur_zin_zf`, remplacer le dessin de Zin (lignes ~1443-1444) par :

```python
    _z_box(d, zin_p1, noeud, "Zin", zin, ci)
```

remplacer le dessin de Zf (lignes ~1455-1456) par :

```python
    _z_box(d, zf_p1, zf_p2, "Zf", zf, ci)
```

et supprimer le bloc `hb = getattr(d, "_z_hitboxes", None) ... hb.append(...)` (lignes ~1462-1468) — les hitboxes sont désormais posées par `_z_box`. Garder le `return {"in": in_pt, "out": out_pt}`.

- [ ] **Step 3: Réécrire `_draw_aop_non_inverseur_zf_zg` pour utiliser `_z_box`**

Idem : remplacer le dessin de Zf (lignes ~1502-1503) par `_z_box(d, zf_p1, zf_p2, "Zf", zf, ci)`, le dessin de Zg (lignes ~1510-1511) par `_z_box(d, zg_p1, noeud, "Zg", zg, ci)`, et supprimer le bloc `hb.append(...)` (lignes ~1516-1522). Garder le `return`.

- [ ] **Step 4: Ajouter `_bloc_impedance` dans `circuit_analyzer/detecteur.py`**

Insérer juste après `_voisins_de_type` (ligne ~74) :

```python
def _bloc_impedance(noeud, data, autre):
    """@brief Construit un bloc d'impédance à partir d'une arête du graphe.

    @param noeud Nœud de référence (une extrémité de l'arête).
    @param data Attributs de l'arête (ref/refs/composition).
    @param autre Autre extrémité de l'arête.
    @return dict {'refs','composition','nodes'}.
    """
    return {
        'refs': list(data.get('refs', [data['ref']])),
        'composition': data.get('composition', data['ref']),
        'nodes': (noeud, autre),
    }
```

- [ ] **Step 5: Lancer les tests de non-régression**

Run: `python -m pytest tests/test_circuit_viewer.py tests/test_detecteur_aop.py -q`
Expected: PASS (le comportement des drawers inverseur/non-inverseur est inchangé ; `test_draw_inverting_amp_deux_boites_z` passe toujours).

- [ ] **Step 6: Commit**

```bash
git add gui/circuit_viewer.py circuit_analyzer/detecteur.py
git commit -m "refactor(viewer): helper _z_box (boite Z cliquable) + _bloc_impedance partage"
```

---

### Task 2: Différentiel — impédances Z1/Zf/Z3/Zg cliquables

**Files:**
- Modify: `circuit_analyzer/detecteur.py:467-508` (`detecter_amplificateur_differentiel`)
- Modify: `gui/circuit_viewer.py` (nouveau `_draw_aop_differentiel`, branche dans `_draw_differential_amp:1730`)
- Test: `tests/test_detecteur_aop.py`, `tests/test_circuit_viewer.py`
- Create demo: `simulations/differential_aop.txt`

**Interfaces:**
- Consumes: `_bloc_impedance`, `_z_box` (Task 1).
- Produces (détecteur): match enrichi de `'impedances': {'Z1','Zf','Z3','Zg'}` et `'gain': 'Zf/Z1 · (V2−V1)'`.
- Produces (drawer): `_draw_aop_differentiel(d, imp, ci, origin=(6.0, 0), in1_label="IN1", in2_label="IN2", out_label="OUT") -> {"in":(x,y),"out":(x,y)}`.

- [ ] **Step 1: Test détecteur (échec attendu)**

Ajouter dans `tests/test_detecteur_aop.py` :

```python
def _differentiel():
    # IN1 -R1- INM -Rf- OUT ; IN2 -R3- INP -Rg- GND
    return construire_graphe([
        Composant("U1", "U", {"IN+": "INP", "IN-": "INM", "OUT": "OUT"}),
        Composant("R1", "R", {"1": "IN1", "2": "INM"}, "10k"),
        Composant("Rf", "R", {"1": "INM", "2": "OUT"}, "100k"),
        Composant("R3", "R", {"1": "IN2", "2": "INP"}, "10k"),
        Composant("Rg", "R", {"1": "INP", "2": "GND"}, "100k"),
    ])


def test_differentiel_expose_quatre_impedances():
    res = detecteur.analyser(_differentiel())
    m = [r for r in res if r["circuit_type"] == "Amplificateur différentiel (AOP)"]
    assert len(m) == 1
    imp = m[0]["impedances"]
    assert imp["Z1"]["refs"] == ["R1"]
    assert imp["Zf"]["refs"] == ["Rf"]
    assert imp["Z3"]["refs"] == ["R3"]
    assert imp["Zg"]["refs"] == ["Rg"]
    assert m[0]["gain"] == "Zf/Z1 · (V2−V1)"
```

- [ ] **Step 2: Lancer → échec**

Run: `python -m pytest tests/test_detecteur_aop.py::test_differentiel_expose_quatre_impedances -q`
Expected: FAIL (`KeyError: 'impedances'`).

- [ ] **Step 3: Implémenter l'émission des blocs**

Remplacer le corps de la boucle dans `detecter_amplificateur_differentiel` (lignes ~494-506) par :

```python
        z1 = zf = z3 = zg = None
        for u, v, data in graphe.edges(entree_neg, data=True):
            if not _type_correspond(data, 'R', inclure_z=True):
                continue
            autre = v if u == entree_neg else u
            if autre == sortie:
                zf = _bloc_impedance(entree_neg, data, autre)
            elif z1 is None:
                z1 = _bloc_impedance(entree_neg, data, autre)
        for u, v, data in graphe.edges(entree_pos, data=True):
            if not _type_correspond(data, 'R', inclure_z=True):
                continue
            autre = v if u == entree_pos else u
            if est_masse(autre):
                zg = _bloc_impedance(entree_pos, data, autre)
            elif z3 is None:
                z3 = _bloc_impedance(entree_pos, data, autre)

        if z1 and zf and z3 and zg:
            resultats.append({
                'circuit_type': 'Amplificateur différentiel (AOP)',
                'components': [ref_aop] + z1['refs'] + zf['refs'] + z3['refs'] + zg['refs'],
                'nodes': [entree_pos, entree_neg, sortie],
                'impedances': {'Z1': z1, 'Zf': zf, 'Z3': z3, 'Zg': zg},
                'gain': 'Zf/Z1 · (V2−V1)',
            })
```

- [ ] **Step 4: Lancer → succès**

Run: `python -m pytest tests/test_detecteur_aop.py::test_differentiel_expose_quatre_impedances -q`
Expected: PASS.

- [ ] **Step 5: Test drawer (échec attendu)**

Ajouter dans `tests/test_circuit_viewer.py` :

```python
def test_draw_differentiel_quatre_boites_z():
    result = {
        "circuit_type": "Amplificateur différentiel (AOP)",
        "components": ["U1", "R1", "Rf", "R3", "Rg"],
        "nodes": ["INP", "INM", "OUT"],
        "impedances": {
            "Z1": {"refs": ["R1"], "composition": "R1", "nodes": ("INM", "IN1")},
            "Zf": {"refs": ["Rf"], "composition": "Rf", "nodes": ("INM", "OUT")},
            "Z3": {"refs": ["R3"], "composition": "R3", "nodes": ("INP", "IN2")},
            "Zg": {"refs": ["Rg"], "composition": "Rg", "nodes": ("INP", "GND")},
        },
        "gain": "Zf/Z1 · (V2−V1)",
    }
    fig = cv._make_fig(result, {}, cv._DRAWERS["Amplificateur différentiel (AOP)"])
    assert len(fig._z_hitboxes) == 4
    refs = sorted(b[4][0] for b in fig._z_hitboxes)
    assert refs == ["R1", "R3", "Rf", "Rg"]
```

- [ ] **Step 6: Lancer → échec**

Run: `python -m pytest tests/test_circuit_viewer.py::test_draw_differentiel_quatre_boites_z -q`
Expected: FAIL (0 hitbox — `_draw_differential_amp` ne lit pas encore `impedances`).

- [ ] **Step 7: Implémenter le drawer**

Ajouter `_draw_aop_differentiel` près de `_draw_differential_amp` dans `gui/circuit_viewer.py` :

```python
def _draw_aop_differentiel(d, imp, ci, origin=(6.0, 0),
                           in1_label="IN1", in2_label="IN2", out_label="OUT"):
    """@brief Dessine le différentiel : AOP + pont Z1/Zf/Z3/Zg cliquable.

    @param imp Dict {'Z1','Zf','Z3','Zg'} (cf. détecteur).
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    z1, zf, z3, zg = imp["Z1"], imp["Zf"], imp["Z3"], imp["Zg"]
    op = d.add(elm.Opamp().right().anchor("center").at(origin).color(_WIRE).fill(_OPAMP_FILL))
    inm, inp, out = op.in1, op.in2, op.out

    # IN- (haut) : Z1 depuis la source, Zf en contre-réaction par le haut
    nm = (inm[0] - 1.3, inm[1])
    d.add(elm.Line().at(nm).to(inm).color(_WIRE))
    d.add(elm.Dot().at(nm).color(_WIRE))
    z1_p1 = (nm[0] - 3.0, nm[1])
    _z_box(d, z1_p1, nm, "Z1", z1, ci)
    d.add(elm.Line().at(z1_p1).left(0.6).color(_WIRE))
    in1_pt = (z1_p1[0] - 0.6, z1_p1[1])
    d.add(elm.Dot().at(in1_pt).color(_WIRE).label(in1_label, loc="left", color=_WIRE))
    above_y = inm[1] + 2.2
    d.add(elm.Line().at(nm).up(above_y - nm[1]).color(_WIRE))
    _z_box(d, (nm[0], above_y), (out[0], above_y), "Zf", zf, ci)
    d.add(elm.Line().at((out[0], above_y)).toy(out[1]).color(_WIRE))

    # IN+ (bas) : Z3 depuis la source, Zg vers la masse (verticale)
    npn = (inp[0] - 1.3, inp[1])
    d.add(elm.Line().at(npn).to(inp).color(_WIRE))
    d.add(elm.Dot().at(npn).color(_WIRE))
    z3_p1 = (npn[0] - 3.0, npn[1])
    _z_box(d, z3_p1, npn, "Z3", z3, ci)
    d.add(elm.Line().at(z3_p1).left(0.6).color(_WIRE))
    in2_pt = (z3_p1[0] - 0.6, z3_p1[1])
    d.add(elm.Dot().at(in2_pt).color(_WIRE).label(in2_label, loc="left", color=_WIRE))
    zg_p2 = (npn[0], npn[1] - 1.6)
    _z_box(d, npn, zg_p2, "Zg", zg, ci, label_loc="bottom")
    d.add(elm.Line().at(zg_p2).down(0.4).color(_WIRE))
    d.add(elm.Ground().color(_WIRE))

    out_pt = (out[0] + 1.0, out[1])
    d.add(elm.Line().at(out).to(out_pt).color(_WIRE).label(out_label, loc="right", color=_WIRE))
    return {"in": in1_pt, "out": out_pt}
```

Puis ajouter le repli en tête de `_draw_differential_amp` (juste après le docstring, avant `rs = _refs(...)`) :

```python
    imp = result.get("impedances")
    if imp:
        _draw_aop_differentiel(d, imp, ci)
        return
```

- [ ] **Step 8: Lancer → succès**

Run: `python -m pytest tests/test_circuit_viewer.py::test_draw_differentiel_quatre_boites_z -q`
Expected: PASS.

- [ ] **Step 9: Démo XML + vérification round-trip**

Créer `simulations/differential_aop.txt` :

```
# Amplificateur differentiel AOP : Vout = Rf/R1 (V2 - V1)
U1  /INP   /INM   /OUT   /VCC   /GND
R1  /IN1   /INM   10k
Rf  /INM   /OUT   100k
R3  /IN2   /INP   10k
Rg  /INP   /GND   100k
```

Run: `python netlist_to_xml.py simulations/differential_aop.txt`
Expected: imprime `· Amplificateur différentiel (AOP)` et écrit `circuits_industriels/differential_aop.xml`.

- [ ] **Step 10: Commit**

```bash
git add circuit_analyzer/detecteur.py gui/circuit_viewer.py tests/test_detecteur_aop.py tests/test_circuit_viewer.py simulations/differential_aop.txt circuits_industriels/differential_aop.xml
git commit -m "feat(differentiel): impedances Z1/Zf/Z3/Zg cliquables + vue AOP + demo"
```

---

### Task 3: Sommateur — Zf + N entrées cliquables

**Files:**
- Modify: `circuit_analyzer/detecteur.py:511-548` (`detecter_amplificateur_sommateur`)
- Modify: `gui/circuit_viewer.py` (nouveau `_draw_aop_sommateur`, branche dans `_draw_summing_amp:1760`)
- Test: `tests/test_detecteur_aop.py`, `tests/test_circuit_viewer.py`
- Create demo: `simulations/summing_aop.txt`

**Interfaces:**
- Consumes: `_bloc_impedance`, `_z_box` (Task 1).
- Produces (détecteur): `'impedances': {'Zf': bloc, 'Zin': [bloc, ...]}`, `'gain': '−Σ Zf/Zk'`.
- Produces (drawer): `_draw_aop_sommateur(d, imp, ci, origin=(5.0, 0), out_label="OUT") -> {"in":(x,y),"out":(x,y)}`.

- [ ] **Step 1: Test détecteur (échec attendu)**

Ajouter dans `tests/test_detecteur_aop.py` :

```python
def _sommateur():
    # IN1 -R1-, IN2 -R2-, IN3 -R3- vers INM ; Rf INM -> OUT
    return construire_graphe([
        Composant("U1", "U", {"IN+": "GND", "IN-": "INM", "OUT": "OUT"}),
        Composant("R1", "R", {"1": "IN1", "2": "INM"}, "10k"),
        Composant("R2", "R", {"1": "IN2", "2": "INM"}, "10k"),
        Composant("R3", "R", {"1": "IN3", "2": "INM"}, "10k"),
        Composant("Rf", "R", {"1": "INM", "2": "OUT"}, "10k"),
    ])


def test_sommateur_expose_zf_et_entrees():
    res = detecteur.analyser(_sommateur())
    m = [r for r in res if r["circuit_type"] == "Amplificateur sommateur (AOP)"]
    assert len(m) == 1
    imp = m[0]["impedances"]
    assert imp["Zf"]["refs"] == ["Rf"]
    assert sorted(b["refs"][0] for b in imp["Zin"]) == ["R1", "R2", "R3"]
    assert m[0]["gain"] == "−Σ Zf/Zk"
```

- [ ] **Step 2: Lancer → échec**

Run: `python -m pytest tests/test_detecteur_aop.py::test_sommateur_expose_zf_et_entrees -q`
Expected: FAIL (`KeyError: 'impedances'`).

- [ ] **Step 3: Implémenter l'émission des blocs**

Remplacer le corps de la boucle dans `detecter_amplificateur_sommateur` (lignes ~536-546) par :

```python
        zf = None
        zin = []
        for u, v, data in graphe.edges(entree_neg, data=True):
            if not _type_correspond(data, 'R', inclure_z=True):
                continue
            autre = v if u == entree_neg else u
            bloc = _bloc_impedance(entree_neg, data, autre)
            if autre == sortie:
                zf = bloc
            else:
                zin.append(bloc)

        if zf and len(zin) >= 2:
            refs_entrees = [r for b in zin for r in b['refs']]
            resultats.append({
                'circuit_type': 'Amplificateur sommateur (AOP)',
                'components': [ref_aop] + zf['refs'] + refs_entrees,
                'nodes': [comp.pins.get('IN+', ''), entree_neg, sortie],
                'impedances': {'Zf': zf, 'Zin': zin},
                'gain': '−Σ Zf/Zk',
            })
```

- [ ] **Step 4: Lancer → succès**

Run: `python -m pytest tests/test_detecteur_aop.py::test_sommateur_expose_zf_et_entrees -q`
Expected: PASS.

- [ ] **Step 5: Test drawer (échec attendu)**

Ajouter dans `tests/test_circuit_viewer.py` :

```python
def test_draw_sommateur_n_plus_un_boites_z():
    result = {
        "circuit_type": "Amplificateur sommateur (AOP)",
        "components": ["U1", "Rf", "R1", "R2", "R3"],
        "nodes": ["GND", "INM", "OUT"],
        "impedances": {
            "Zf": {"refs": ["Rf"], "composition": "Rf", "nodes": ("INM", "OUT")},
            "Zin": [
                {"refs": ["R1"], "composition": "R1", "nodes": ("INM", "IN1")},
                {"refs": ["R2"], "composition": "R2", "nodes": ("INM", "IN2")},
                {"refs": ["R3"], "composition": "R3", "nodes": ("INM", "IN3")},
            ],
        },
        "gain": "−Σ Zf/Zk",
    }
    fig = cv._make_fig(result, {}, cv._DRAWERS["Amplificateur sommateur (AOP)"])
    assert len(fig._z_hitboxes) == 4   # Zf + 3 entrées
    refs = sorted(b[4][0] for b in fig._z_hitboxes)
    assert refs == ["R1", "R2", "R3", "Rf"]
```

- [ ] **Step 6: Lancer → échec**

Run: `python -m pytest tests/test_circuit_viewer.py::test_draw_sommateur_n_plus_un_boites_z -q`
Expected: FAIL (0 hitbox).

- [ ] **Step 7: Implémenter le drawer**

Ajouter `_draw_aop_sommateur` près de `_draw_summing_amp` dans `gui/circuit_viewer.py` :

```python
def _draw_aop_sommateur(d, imp, ci, origin=(5.0, 0), out_label="OUT"):
    """@brief Dessine le sommateur : bus d'entrées Zin + Zf cliquables sur IN-.

    @param imp Dict {'Zf': bloc, 'Zin': [bloc, ...]} (cf. détecteur).
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    zf, zin = imp["Zf"], imp["Zin"]
    op = d.add(elm.Opamp().right().anchor("in1").at(origin).color(_WIRE).fill(_OPAMP_FILL))
    inm, out = op.in1, op.out

    # IN+ à la masse
    d.add(elm.Line().at(op.in2).left(0.8).color(_WIRE))
    d.add(elm.Ground().color(_WIRE))

    node_x = inm[0] - 1.3
    d.add(elm.Line().at((node_x, inm[1])).to(inm).color(_WIRE))
    n = len(zin)
    spacing = 1.4
    top_y = inm[1] + (n - 1) * spacing
    d.add(elm.Line().at((node_x, inm[1])).toy(top_y).color(_WIRE))   # bus vertical
    d.add(elm.Dot().at((node_x, inm[1])).color(_WIRE))

    for i, bloc in enumerate(zin):
        y = inm[1] + i * spacing
        p1 = (node_x - 3.0, y)
        _z_box(d, p1, (node_x, y), f"Z{i+1}", bloc, ci)
        d.add(elm.Line().at(p1).left(0.5).color(_WIRE))
        d.add(elm.Dot().at((p1[0] - 0.5, y)).color(_WIRE).label(f"IN{i+1}", loc="left", color=_WIRE))

    # Zf : du nœud de sommation vers le haut puis OUT
    above_y = top_y + 1.2
    d.add(elm.Line().at((node_x, inm[1])).up(above_y - inm[1]).color(_WIRE))
    _z_box(d, (node_x, above_y), (out[0], above_y), "Zf", zf, ci)
    d.add(elm.Line().at((out[0], above_y)).toy(out[1]).color(_WIRE))

    out_pt = (out[0] + 1.0, out[1])
    d.add(elm.Line().at(out).to(out_pt).color(_WIRE).label(out_label, loc="right", color=_WIRE))
    return {"in": (node_x - 3.5, inm[1]), "out": out_pt}
```

Puis ajouter le repli en tête de `_draw_summing_amp` (juste après le docstring) :

```python
    imp = result.get("impedances")
    if imp:
        _draw_aop_sommateur(d, imp, ci)
        return
```

- [ ] **Step 8: Lancer → succès**

Run: `python -m pytest tests/test_circuit_viewer.py::test_draw_sommateur_n_plus_un_boites_z -q`
Expected: PASS.

- [ ] **Step 9: Démo XML + vérification round-trip**

Créer `simulations/summing_aop.txt` :

```
# Amplificateur sommateur AOP : Vout = -(Rf/R1 V1 + Rf/R2 V2 + Rf/R3 V3)
U1  /GND   /INM   /OUT   /VCC   /GND
R1  /IN1   /INM   10k
R2  /IN2   /INM   10k
R3  /IN3   /INM   10k
Rf  /INM   /OUT   10k
```

Run: `python netlist_to_xml.py simulations/summing_aop.txt`
Expected: imprime `· Amplificateur sommateur (AOP)` et écrit `circuits_industriels/summing_aop.xml`.

- [ ] **Step 10: Commit**

```bash
git add circuit_analyzer/detecteur.py gui/circuit_viewer.py tests/test_detecteur_aop.py tests/test_circuit_viewer.py simulations/summing_aop.txt circuits_industriels/summing_aop.xml
git commit -m "feat(sommateur): Zf + N entrees Z cliquables + vue AOP + demo"
```

---

### Task 4: Bascule de Schmitt — réseau d'hystérésis Zf + Zin cliquable

**Files:**
- Modify: `circuit_analyzer/detecteur.py:381-420` (`detecter_bascule_schmitt`)
- Modify: `gui/circuit_viewer.py` (nouveau `_draw_aop_schmitt`, branche dans `_draw_schmitt:1706`)
- Test: `tests/test_detecteur_aop.py`, `tests/test_circuit_viewer.py`
- Create demo: `simulations/schmitt_aop.txt`

**Interfaces:**
- Consumes: `_bloc_impedance`, `_z_box` (Task 1).
- Produces (détecteur): `'impedances': {'Zf': bloc}` (toujours) plus `'Zin': bloc` si la 2e patte de IN+ existe ; `'gain': 'hystérésis ±Vsat·Zin/(Zin+Zf)'`.
- Produces (drawer): `_draw_aop_schmitt(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT") -> {"in":(x,y),"out":(x,y)}`.

- [ ] **Step 1: Test détecteur (échec attendu)**

Ajouter dans `tests/test_detecteur_aop.py` :

```python
def _schmitt():
    # IN -Rin- INP ; Rf OUT -> INP (contre-reaction positive) ; REF sur IN-
    return construire_graphe([
        Composant("U1", "U", {"IN+": "INP", "IN-": "REF", "OUT": "OUT"}),
        Composant("Rin", "R", {"1": "IN", "2": "INP"}, "10k"),
        Composant("Rf", "R", {"1": "OUT", "2": "INP"}, "100k"),
    ])


def test_schmitt_expose_zf_et_zin():
    res = detecteur.analyser(_schmitt())
    m = [r for r in res if r["circuit_type"] == "Bascule de Schmitt (AOP)"]
    assert len(m) == 1
    imp = m[0]["impedances"]
    assert imp["Zf"]["refs"] == ["Rf"]
    assert imp["Zin"]["refs"] == ["Rin"]
    assert "hystérésis" in m[0]["gain"]
```

- [ ] **Step 2: Lancer → échec**

Run: `python -m pytest tests/test_detecteur_aop.py::test_schmitt_expose_zf_et_zin -q`
Expected: FAIL (`KeyError: 'impedances'`).

- [ ] **Step 3: Implémenter l'émission des blocs**

Remplacer le corps de la boucle dans `detecter_bascule_schmitt` (lignes ~409-418) par :

```python
        zf = None
        zin = None
        for u, v, data in graphe.edges(entree_pos, data=True):
            if not _type_correspond(data, 'R', inclure_z=True):
                continue
            autre = v if u == entree_pos else u
            bloc = _bloc_impedance(entree_pos, data, autre)
            if autre == sortie:
                zf = bloc
            elif zin is None:
                zin = bloc

        if zf:
            imp = {'Zf': zf}
            comps = [ref_aop] + zf['refs']
            if zin:
                imp['Zin'] = zin
                comps += zin['refs']
            resultats.append({
                'circuit_type': 'Bascule de Schmitt (AOP)',
                'components': comps,
                'nodes': [entree_pos, entree_neg, sortie],
                'impedances': imp,
                'gain': 'hystérésis ±Vsat·Zin/(Zin+Zf)',
            })
```

- [ ] **Step 4: Lancer → succès**

Run: `python -m pytest tests/test_detecteur_aop.py::test_schmitt_expose_zf_et_zin -q`
Expected: PASS.

- [ ] **Step 5: Test drawer (échec attendu)**

Ajouter dans `tests/test_circuit_viewer.py` :

```python
def test_draw_schmitt_deux_boites_z():
    result = {
        "circuit_type": "Bascule de Schmitt (AOP)",
        "components": ["U1", "Rf", "Rin"],
        "nodes": ["INP", "REF", "OUT"],
        "impedances": {
            "Zf": {"refs": ["Rf"], "composition": "Rf", "nodes": ("INP", "OUT")},
            "Zin": {"refs": ["Rin"], "composition": "Rin", "nodes": ("INP", "IN")},
        },
        "gain": "hystérésis ±Vsat·Zin/(Zin+Zf)",
    }
    fig = cv._make_fig(result, {}, cv._DRAWERS["Bascule de Schmitt (AOP)"])
    assert len(fig._z_hitboxes) == 2
    refs = sorted(b[4][0] for b in fig._z_hitboxes)
    assert refs == ["Rf", "Rin"]
```

- [ ] **Step 6: Lancer → échec**

Run: `python -m pytest tests/test_circuit_viewer.py::test_draw_schmitt_deux_boites_z -q`
Expected: FAIL (0 hitbox — `_draw_schmitt` ne lit pas encore `impedances`).

- [ ] **Step 7: Implémenter le drawer**

Ajouter `_draw_aop_schmitt` près de `_draw_schmitt` dans `gui/circuit_viewer.py` :

```python
def _draw_aop_schmitt(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT"):
    """@brief Dessine la bascule de Schmitt : contre-réaction positive Zf
    (OUT → IN+) + patte d'entrée Zin sur IN+, toutes deux cliquables.

    @param imp Dict {'Zf': bloc, 'Zin': bloc?} (cf. détecteur).
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    zf = imp["Zf"]
    zin = imp.get("Zin")
    op = d.add(elm.Opamp().right().anchor("center").at(origin).color(_WIRE).fill(_OPAMP_FILL))
    inm, inp, out = op.in1, op.in2, op.out

    # IN- = référence
    d.add(elm.Line().at(inm).left(1.2).color(_WIRE))
    d.add(elm.Dot().at((inm[0] - 1.2, inm[1])).color(_WIRE).label("REF", loc="left", color=_WIRE))

    # Nœud IN+
    np_node = (inp[0] - 1.0, inp[1])
    d.add(elm.Line().at(np_node).to(inp).color(_WIRE))
    d.add(elm.Dot().at(np_node).color(_WIRE))
    in_pt = np_node

    # Zin : entrée -> IN+ (horizontale vers la gauche)
    if zin:
        zin_p1 = (np_node[0] - 3.0, np_node[1])
        _z_box(d, zin_p1, np_node, "Zin", zin, ci)
        d.add(elm.Line().at(zin_p1).left(0.5).color(_WIRE))
        in_pt = (zin_p1[0] - 0.5, zin_p1[1])
        d.add(elm.Dot().at(in_pt).color(_WIRE).label(in_label, loc="left", color=_WIRE))

    # Zf : contre-réaction positive OUT -> IN+ (par le bas pour éviter le corps)
    below_y = inp[1] - 1.8
    d.add(elm.Line().at(np_node).down(np_node[1] - below_y).color(_WIRE))
    _z_box(d, (np_node[0], below_y), (out[0], below_y), "Zf", zf, ci, label_loc="bottom")
    d.add(elm.Line().at((out[0], below_y)).toy(out[1]).color(_WIRE))

    out_pt = (out[0] + 1.2, out[1])
    d.add(elm.Line().at(out).to(out_pt).color(_WIRE).label(out_label, loc="right", color=_WIRE))
    return {"in": in_pt, "out": out_pt}
```

Puis ajouter le repli en tête de `_draw_schmitt` (juste après le docstring, avant `rs = _refs(...)`) :

```python
    imp = result.get("impedances")
    if imp:
        _draw_aop_schmitt(d, imp, ci)
        return
```

- [ ] **Step 8: Lancer → succès**

Run: `python -m pytest tests/test_circuit_viewer.py::test_draw_schmitt_deux_boites_z -q`
Expected: PASS.

- [ ] **Step 9: Démo XML + vérification round-trip**

Créer `simulations/schmitt_aop.txt` :

```
# Bascule de Schmitt AOP (non-inverseuse) : hysteresis par Rf/Rin
U1  /INP   /REF   /OUT   /VCC   /GND
Rin /IN    /INP   10k
Rf  /OUT   /INP   100k
```

Run: `python netlist_to_xml.py simulations/schmitt_aop.txt`
Expected: imprime `· Bascule de Schmitt (AOP)` et écrit `circuits_industriels/schmitt_aop.xml`.

- [ ] **Step 10: Commit**

```bash
git add circuit_analyzer/detecteur.py gui/circuit_viewer.py tests/test_detecteur_aop.py tests/test_circuit_viewer.py simulations/schmitt_aop.txt circuits_industriels/schmitt_aop.xml
git commit -m "feat(schmitt): reseau hysteresis Zf+Zin cliquable + vue AOP + demo"
```

---

### Task 5: Comparateur — dessin propre (sans Z)

Le comparateur n'a aucune impédance (boucle ouverte). On polit seulement son dessin pour l'homogénéité visuelle (couleurs `_WIRE`/`_OPAMP_FILL`, libellés IN+/REF/OUT). Aucune hitbox.

**Files:**
- Modify: `gui/circuit_viewer.py:1698-1703` (`_draw_comparator`)
- Test: `tests/test_circuit_viewer.py`
- Create demo: `simulations/comparator_aop.txt`

**Interfaces:**
- Consumes: rien de neuf.
- Produces (drawer): `_draw_comparator(d, result, ci)` redessiné, 0 hitbox.

- [ ] **Step 1: Test drawer (échec attendu)**

Ajouter dans `tests/test_circuit_viewer.py` :

```python
def test_draw_comparateur_sans_hitbox():
    result = {
        "circuit_type": "Comparateur (AOP)",
        "components": ["U1"],
        "nodes": ["INP", "INM", "OUT"],
    }
    fig = cv._make_fig(result, {}, cv._DRAWERS["Comparateur (AOP)"])
    assert fig._z_hitboxes == []   # aucune impédance à driller
```

- [ ] **Step 2: Lancer → vérifier l'état**

Run: `python -m pytest tests/test_circuit_viewer.py::test_draw_comparateur_sans_hitbox -q`
Expected: PASS déjà (le comparateur n'a jamais posé de hitbox). Ce test verrouille l'invariant « 0 hitbox » avant de retoucher le dessin.

- [ ] **Step 3: Polir le dessin**

Remplacer le corps de `_draw_comparator` (lignes ~1700-1703) par :

```python
    op = d.add(elm.Opamp().right().anchor("center").at((4.5, 0)).color(_WIRE).fill(_OPAMP_FILL))
    d.add(elm.Line().at(op.in2).left(1.3).color(_WIRE))
    d.add(elm.Dot().at((op.in2[0] - 1.3, op.in2[1])).color(_WIRE).label("IN+", loc="left", color=_WIRE))
    d.add(elm.Line().at(op.in1).left(1.3).color(_WIRE))
    d.add(elm.Dot().at((op.in1[0] - 1.3, op.in1[1])).color(_WIRE).label("REF", loc="left", color=_WIRE))
    d.add(elm.Line().at(op.out).right(1.3).color(_WIRE).label("OUT", loc="right", color=_WIRE))
```

- [ ] **Step 4: Lancer → succès**

Run: `python -m pytest tests/test_circuit_viewer.py::test_draw_comparateur_sans_hitbox -q`
Expected: PASS.

- [ ] **Step 5: Démo XML + vérification round-trip**

Créer `simulations/comparator_aop.txt` :

```
# Comparateur AOP en boucle ouverte : OUT bascule selon IN+ vs REF
U1  /IN   /REF   /OUT   /VCC   /GND
```

Run: `python netlist_to_xml.py simulations/comparator_aop.txt`
Expected: imprime `· Comparateur (AOP)` et écrit `circuits_industriels/comparator_aop.xml`.

- [ ] **Step 6: Commit**

```bash
git add gui/circuit_viewer.py tests/test_circuit_viewer.py simulations/comparator_aop.txt circuits_industriels/comparator_aop.xml
git commit -m "feat(comparateur): dessin propre IN+/REF/OUT + demo"
```

---

### Task 6: Vérification globale

**Files:** tous les fichiers modifiés.

- [ ] **Step 1: Suite complète**

Run: `python -m pytest -q`
Expected: tout passe (aucune régression sur les 5 montages déjà faits ni sur le reste).

- [ ] **Step 2: État git propre**

Run: `git status --short`
Expected: aucune modification source non commitée ; seuls restent les fichiers `debug_*.py` non suivis préexistants.
