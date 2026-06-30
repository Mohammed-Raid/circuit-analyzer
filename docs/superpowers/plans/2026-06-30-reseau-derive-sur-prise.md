# Réseau dérivé sur prise — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Détecter les réseaux passifs dérivés des rails (diviseurs de référence, filtrages d'alim) et les dessiner en schéma propre « rail ─ Z série ─ ●prise ─ Z shunt ─ GND » au lieu de la grille générique.

**Architecture:** Détection structurelle des « nets dérivés » dans `ilots.py` → regroupement des rail-passifs par net-prise (un seul îlot par réseau) → recognizer + drawer dédiés dans `circuit_viewer.py`, routés avant le repli grille générique. Les deux blocs Z réutilisent les boîtes cliquables existantes (`_z_box`) et le drill-down.

**Tech Stack:** Python, NetworkX (graphe), schemdraw + matplotlib (dessin), pytest.

## Global Constraints

- Aucun `Co-Authored-By: Claude` ni footer « Generated with Claude Code » dans les commits.
- L'app traite uniquement des impédances ; ne pas gold-plater (pas de fusion avec l'AOP, pas de prises multiples).
- Passifs = types `{'R', 'L', 'C'}`. GND-family = net `rail` non-`power` (ex. GND, PE).
- Toute modif de rendu → re-rendu PNG inspecté (pas seulement tests verts).
- Encodage : forcer l'ASCII aux `print` de diagnostic (le `Ω` casse cp1252).

---

### Task 1 : `_nets_derives(graphe)` — détection structurelle

**Files:**
- Modify: `circuit_analyzer/ilots.py` (ajout helper après `_est_degenere`)
- Test: `tests/test_ilots.py`

**Interfaces:**
- Consumes: `graphe.graph['components']` ({ref → Composant}), `is_power_net`, `_est_rail` (déjà importés dans ilots.py).
- Produces: `_nets_derives(graphe) -> set[str]` — ensemble des nets-prises.

- [ ] **Step 1 : Écrire les tests qui échouent**

```python
def test_nets_derives_reconnait_diviseur():
    # VCC -- R1 -- VREF -- R2 -- GND : VREF est une prise, VCC non.
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'VREF'}, '10k'),
        Component('R2', 'R', {'1': 'VREF', '2': 'GND'}, '10k'),
    ]
    from circuit_analyzer.ilots import _nets_derives
    derives = _nets_derives(build_graph(comps))
    assert 'VREF' in derives
    assert 'VCC' not in derives


def test_nets_derives_filtrage_rail_caps_vers_gnd():
    # VCC_5V -- R4 -- AVCC, et C4/C5 de AVCC a GND : AVCC est une prise.
    comps = [
        Component('R4', 'R', {'1': 'VCC_5V', '2': 'AVCC'}, '10R'),
        Component('C4', 'C', {'1': 'AVCC', '2': 'GND'}, '100nF'),
        Component('C5', 'C', {'1': 'AVCC', '2': 'GND'}, '10uF'),
    ]
    from circuit_analyzer.ilots import _nets_derives
    derives = _nets_derives(build_graph(comps))
    assert 'AVCC' in derives
    assert 'VCC_5V' not in derives


def test_nets_derives_decouplage_simple_pas_une_prise():
    # Un simple cap VCC-GND n'a pas de passif vers un AUTRE rail : pas une prise.
    comps = [Component('C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF')]
    from circuit_analyzer.ilots import _nets_derives
    assert _nets_derives(build_graph(comps)) == set()
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_ilots.py -k nets_derives -q`
Expected: FAIL — `ImportError: cannot import name '_nets_derives'`.

- [ ] **Step 3 : Implémenter le helper**

Ajouter dans `circuit_analyzer/ilots.py`, juste après `_est_degenere` :

```python
_PASSIFS = {'R', 'L', 'C'}


def _est_gnd(net) -> bool:
    """@brief Vrai pour la masse (rail non-alimentation : GND, PE…)."""
    return bool(net) and _est_rail(net) and not is_power_net(net)


def _nets_derives(graphe) -> set:
    """@brief Nets d'alimentation « dérivés » (prises de référence / rails filtrés).

    Un net N est une prise dérivée s'il est un net d'alimentation ≠ GND qui possède
    À LA FOIS un passif (R/L/C) vers GND ET un passif vers un autre net d'alimentation.
    Discrimine les références (VREF, AVCC) des vrais rails sources (VCC, qui n'a pas
    de passif vers GND dans son réseau).

    @param graphe Graphe NetworkX (porte graphe.graph['components']).
    @return set[str] Nets-prises.
    """
    comps = graphe.graph.get('components', {})
    vers_gnd: set = set()        # nets alim ayant un passif vers GND
    vers_rail: dict = {}         # net alim -> {autres nets alim relies par un passif}
    for comp in comps.values():
        if comp.type not in _PASSIFS:
            continue
        nets = [n for n in comp.pins.values() if n]
        for i, a in enumerate(nets):
            for b in nets[i + 1:]:
                if a == b:
                    continue
                for x, y in ((a, b), (b, a)):
                    if is_power_net(x) and not _est_gnd(x):
                        if _est_gnd(y):
                            vers_gnd.add(x)
                        elif is_power_net(y) and not _est_gnd(y):
                            vers_rail.setdefault(x, set()).add(y)
    return {n for n in vers_gnd if vers_rail.get(n)}
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run: `python -m pytest tests/test_ilots.py -k nets_derives -q`
Expected: PASS (3 tests).

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/ilots.py tests/test_ilots.py
git commit -m "feat(ilot): detection structurelle des nets derives (prises de reference)"
```

---

### Task 2 : Regroupement des rail-passifs par net-prise

**Files:**
- Modify: `circuit_analyzer/ilots.py` (`detecter_ilots`, étape 2 « composants rail-only »)
- Test: `tests/test_ilots.py`

**Interfaces:**
- Consumes: `_nets_derives(graphe)` (Task 1).
- Produces: comportement de `detecter_ilots` — un diviseur `R_haut + R_bas` partageant une prise forme UN seul îlot.

- [ ] **Step 1 : Écrire le test qui échoue**

```python
def test_diviseur_reference_un_seul_ilot():
    # R_haut (VCC->VREF) et R_bas (VREF->GND) doivent etre dans le MEME ilot.
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'VREF'}, '10k'),
        Component('R2', 'R', {'1': 'VREF', '2': 'GND'}, '10k'),
    ]
    g = build_graph(comps)
    ilots = detecter_ilots(g, [])
    assert len(ilots) == 1
    assert set(ilots[0]['composants']) == {'R1', 'R2'}


def test_filtrage_rail_un_seul_ilot():
    comps = [
        Component('R4', 'R', {'1': 'VCC_5V', '2': 'AVCC'}, '10R'),
        Component('C4', 'C', {'1': 'AVCC', '2': 'GND'}, '100nF'),
        Component('C5', 'C', {'1': 'AVCC', '2': 'GND'}, '10uF'),
    ]
    ilots = detecter_ilots(build_graph(comps), [])
    assert len(ilots) == 1
    assert set(ilots[0]['composants']) == {'R4', 'C4', 'C5'}
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_ilots.py -k "diviseur_reference_un_seul or filtrage_rail_un_seul" -q`
Expected: FAIL — `test_diviseur_reference_un_seul_ilot` donne 2 îlots (R1 sous bucket VCC, R2 sous bucket VREF).

- [ ] **Step 3 : Modifier l'étape 2 de `detecter_ilots`**

Remplacer le bloc « ── 2. Composants rail-only ── » par (calcul de la clé de bucket = net-prise partagé si présent) :

```python
    # ── 2. Composants rail-only : un groupe par prise dérivée, sinon par rail ──
    derives = _nets_derives(graphe)
    par_rail: dict = {}
    sans_rien: list = []
    for ref, comp in comps.items():
        if ref in refs_signal:
            continue
        prises = sorted({n for n in comp.pins.values() if n in derives})
        if prises:                       # rattaché à sa prise dérivée (diviseur unifié)
            par_rail.setdefault(prises[0], []).append(ref)
            continue
        rails = sorted({n for n in comp.pins.values() if n and is_power_net(n)})
        if rails:
            par_rail.setdefault(rails[0], []).append(ref)
        else:
            sans_rien.append(ref)
```

Note : `comps` est ici le dict filtré (les dégénérés sont déjà retirés en tête de fonction) ; `_nets_derives` prend `graphe` (non filtré), ce qui est sans incidence — un dégénéré n'a pas deux nets distincts donc ne crée jamais de prise.

- [ ] **Step 4 : Lancer, vérifier le succès**

Run: `python -m pytest tests/test_ilots.py -q`
Expected: PASS (tout le fichier ; le regroupement n'altère pas les autres tests).

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/ilots.py tests/test_ilots.py
git commit -m "feat(ilot): regrouper les rail-passifs par prise derivee (diviseur unifie)"
```

---

### Task 3 : Recognizer `_reseau_derive_ilot(ilot, graph)`

**Files:**
- Modify: `gui/circuit_viewer.py` (ajout après `_pont_ilot`, ~ligne 437)
- Test: `tests/test_reseau_derive.py` (créer)

**Interfaces:**
- Consumes: `_nets_derives` (import depuis `circuit_analyzer.ilots`), `impedance.impedance_equivalente`, `construire_graphe`.
- Produces: `_reseau_derive_ilot(ilot, graph) -> dict | None` où le dict est
  `{"top": str, "prise": str, "serie": {"refs": list, "composition": str}, "shunt": {"refs": list, "composition": str} | None}`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `tests/test_reseau_derive.py` :

```python
"""@file test_reseau_derive.py
@brief Recognizer + drawer du reseau derive sur prise (diviseurs / filtrage rail)."""
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from gui import circuit_viewer as cv


def _ilot(refs):
    return {'composants': sorted(refs), 'circuits': [], 'rail': None,
            'categorie': 'alimentation', 'label': 'Ilot test'}


def test_reseau_derive_reconnait_diviseur():
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'VREF'}, '10k'),
        Component('R2', 'R', {'1': 'VREF', '2': 'GND'}, '4.7k'),
    ]
    g = build_graph(comps)
    info = cv._reseau_derive_ilot(_ilot(['R1', 'R2']), g)
    assert info is not None
    assert info['top'] == 'VCC'
    assert info['prise'] == 'VREF'
    assert info['serie']['refs'] == ['R1']
    assert set(info['shunt']['refs']) == {'R2'}


def test_reseau_derive_filtrage_rail_shunt_caps():
    comps = [
        Component('R4', 'R', {'1': 'VCC_5V', '2': 'AVCC'}, '10R'),
        Component('C4', 'C', {'1': 'AVCC', '2': 'GND'}, '100nF'),
        Component('C5', 'C', {'1': 'AVCC', '2': 'GND'}, '10uF'),
    ]
    g = build_graph(comps)
    info = cv._reseau_derive_ilot(_ilot(['R4', 'C4', 'C5']), g)
    assert info is not None
    assert info['prise'] == 'AVCC'
    assert info['serie']['refs'] == ['R4']
    assert set(info['shunt']['refs']) == {'C4', 'C5'}


def test_reseau_derive_non_reconnu_renvoie_none():
    # Filtre RC signal classique : pas de prise derivee.
    comps = [
        Component('R1', 'R', {'1': 'VIN', '2': 'VOUT'}, '10k'),
        Component('C1', 'C', {'1': 'VOUT', '2': 'GND'}, '100nF'),
    ]
    g = build_graph(comps)
    assert cv._reseau_derive_ilot(_ilot(['R1', 'C1']), g) is None
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_reseau_derive.py -q`
Expected: FAIL — `AttributeError: module 'gui.circuit_viewer' has no attribute '_reseau_derive_ilot'`.

- [ ] **Step 3 : Implémenter le recognizer**

Ajouter dans `gui/circuit_viewer.py` après `_pont_ilot` :

```python
def _compo_2bornes(refs, a, b, raw):
    """@brief Composition symbolique (serie/parallele) des passifs entre a et b.

    @param refs Liste de refs du sous-reseau. @param a/b Nets bornes.
    @param raw Dict {ref -> Composant} original.
    @return str Expression reparsable (ex. 'R7//C7'), ou la ref unique.
    """
    from circuit_analyzer import impedance
    from circuit_analyzer.composant import construire_graphe
    if len(refs) == 1:
        return refs[0]
    sous = construire_graphe([raw[r] for r in refs])
    expr = impedance.impedance_equivalente(sous, a, b)
    return expr if expr else "//".join(refs)


def _reseau_derive_ilot(ilot, graph):
    """@brief Reseau passif derive sur prise (diviseur de reference / filtrage rail).

    Forme : <rail source> -[Z serie]- (prise) -[Z shunt]- GND. Couvre le diviseur
    pur, le diviseur + cap de bypass, et le filtrage de rail.

    @param ilot Ilot detecte (cle 'composants' = refs brutes).
    @param graph Graphe original (porte graph['components']).
    @return dict {top, prise, serie, shunt} ou None si la forme ne s'applique pas.
    """
    from circuit_analyzer.ilots import _nets_derives, _est_gnd, _PASSIFS
    from circuit_analyzer.patterns.base import is_power_net

    raw = getattr(graph, "graph", {}).get("components", {}) or {}
    refs = [r for r in ilot.get("composants", []) if r in raw]
    if not refs or any(raw[r].type not in _PASSIFS for r in refs):
        return None
    prises = _nets_derives(graph) & {
        n for r in refs for n in raw[r].pins.values() if n}
    if len(prises) != 1:
        return None
    prise = next(iter(prises))

    serie_refs, shunt_refs, tops = [], [], set()
    for r in refs:
        nets = {n for n in raw[r].pins.values() if n}
        if prise not in nets:
            return None                       # tout composant doit toucher la prise
        autre = nets - {prise}
        if any(_est_gnd(n) for n in autre):
            shunt_refs.append(r)
        else:
            rails = [n for n in autre if is_power_net(n)]
            if not rails:
                return None
            serie_refs.append(r)
            tops.update(rails)
    if not serie_refs or len(tops) != 1:
        return None
    top = next(iter(tops))
    serie = {"refs": serie_refs,
             "composition": _compo_2bornes(serie_refs, top, prise, raw)}
    shunt = ({"refs": shunt_refs,
              "composition": _compo_2bornes(shunt_refs, prise, "GND", raw)}
             if shunt_refs else None)
    return {"top": top, "prise": prise, "serie": serie, "shunt": shunt}
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run: `python -m pytest tests/test_reseau_derive.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5 : Commit**

```bash
git add gui/circuit_viewer.py tests/test_reseau_derive.py
git commit -m "feat(ilot): recognizer du reseau derive sur prise (top/prise/serie/shunt)"
```

---

### Task 4 : Drawer `_draw_reseau_derive` + routage dans `show_island`

**Files:**
- Modify: `gui/circuit_viewer.py` (drawer près des autres `_draw_*` ; routage dans `show_island` ~ligne 477-508)
- Test: `tests/test_reseau_derive.py`

**Interfaces:**
- Consumes: `_reseau_derive_ilot` (Task 3), `_z_box`, `_make_fig`, `elm`, `_WIRE`.
- Produces: `_draw_reseau_derive(d, info, ci)` (signature drawer : `(d, result, comp_info)`), rendu via `_make_fig`. Figure portant `fig._z_hitboxes` (une par bloc Z).

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter dans `tests/test_reseau_derive.py` :

```python
def test_draw_reseau_derive_figure_et_hitboxes():
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'VREF'}, '10k'),
        Component('R2', 'R', {'1': 'VREF', '2': 'GND'}, '4.7k'),
    ]
    g = build_graph(comps)
    info = cv._reseau_derive_ilot(_ilot(['R1', 'R2']), g)
    ci = {c.ref: {'type': c.type, 'value': c.value, 'pins': c.pins} for c in comps}
    fig = cv._make_fig(info, ci, cv._draw_reseau_derive)
    assert fig is not None
    # une boite Z cliquable pour la serie, une pour le shunt
    assert len(getattr(fig, '_z_hitboxes', [])) == 2
    refs_hit = {tuple(sorted(h[4])) for h in fig._z_hitboxes}
    assert ('R1',) in refs_hit and ('R2',) in refs_hit


def test_show_island_route_vers_reseau_derive(monkeypatch):
    # Le routage de show_island choisit le reseau derive avant la grille generique.
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'VREF'}, '10k'),
        Component('R2', 'R', {'1': 'VREF', '2': 'GND'}, '4.7k'),
    ]
    g = build_graph(comps)
    ilot = _ilot(['R1', 'R2'])
    # le recognizer doit reconnaitre cet ilot (preuve que la branche sera prise)
    assert cv._reseau_derive_ilot(ilot, g) is not None
    # et la grille generique ne doit PAS etre le seul recours
    assert cv._circuit_principal_ilot(ilot, g, None) is None
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_reseau_derive.py -k draw_reseau_derive -q`
Expected: FAIL — `AttributeError: ... no attribute '_draw_reseau_derive'`.

- [ ] **Step 3 : Implémenter le drawer**

Ajouter dans `gui/circuit_viewer.py` (près des autres `_draw_*`) :

```python
def _draw_reseau_derive(d, info, ci):
    """@brief Dessine un reseau derive : rail haut -[Z serie]- prise -[Z shunt]- GND.

    @param d Dessin schemdraw. @param info Dict de _reseau_derive_ilot.
    @param ci Dict {ref -> {type, value, pins}}.
    @return dict (ancres ; vide ici).
    """
    p_top, p_prise, p_gnd = (0, 5), (0, 3), (0, 1)
    d.add(elm.Line().at(p_top).up(0.5).color(_WIRE))
    d.add(elm.Label().at((0, 5.8)).label(info["top"], color=_WIRE))
    _z_box(d, p_top, p_prise, "Z", info["serie"], ci, label_loc="left")
    d.add(elm.Dot().at(p_prise).color(_WIRE))
    d.add(elm.Line().at(p_prise).right(1.8).color(_WIRE))
    d.add(elm.Label().at((1.9, 3)).label(f"{info['prise']}  ->",
                                         halign="left", color=_WIRE))
    if info["shunt"]:
        _z_box(d, p_prise, p_gnd, "Z", info["shunt"], ci, label_loc="left")
        d.add(elm.Ground().at(p_gnd).color(_WIRE))
    else:
        d.add(elm.Ground().at(p_prise).color(_WIRE))
    return {}
```

- [ ] **Step 4 : Router dans `show_island`**

Dans `show_island`, après la ligne calculant `_pont` (~479) et avant le bloc `_chaine = _branches = None`, ajouter le recognizer ; puis ajouter la branche de rendu.

Calcul (après `_pont = ...`) :

```python
    _derive = (_reseau_derive_ilot(ilot, graph)
               if (principal is None and _sp is None and _pont is None) else None)
    _chaine = _branches = None
    if principal is None and _sp is None and _pont is None and _derive is None:
        _chaine = _ordonner_montages_flux(_matches_for_island(ilot, results), comp_info)
        if _chaine is None:
            _branches = _layers_montages_flux(_matches_for_island(ilot, results), comp_info)
```

Rendu : insérer la branche AVANT le `elif _chaine is not None:` :

```python
    elif _derive is not None:
        fig = _make_fig(_derive, comp_info, _draw_reseau_derive)
```

- [ ] **Step 5 : Lancer, vérifier le succès (fichier + suite complète)**

Run: `python -m pytest tests/test_reseau_derive.py -q`
Expected: PASS (5 tests).
Run: `python -m pytest -q`
Expected: PASS (toute la suite).

- [ ] **Step 6 : Vérification visuelle obligatoire**

Régénérer tous les îlots et inspecter les 10 concernés (tous_aop, anti_alias, surtension, schmitt, conditionnement, buffer) :

Run: `python <scratchpad>/gen_ilots.py`
Vérifier dans `tools/_renders/ilots_pour_chatgpt/` que ces îlots montrent désormais le schéma « rail ─ Z ─ prise → ─ Z ─ GND » (et non plus la grille générique). Confirmer le manifeste : `grille_generique` doit avoir nettement diminué.

- [ ] **Step 7 : Commit**

```bash
git add gui/circuit_viewer.py tests/test_reseau_derive.py
git commit -m "feat(ilot): drawer du reseau derive + routage show_island (fin grille generique sur les references)"
```

---

## Self-Review

**Spec coverage :**
- A. Concept (forme unifiée) → Task 4 (drawer) ✓
- B. Détection structurelle `_nets_derives` → Task 1 ✓
- C. Regroupement d'îlots → Task 2 ✓
- D. Recognizer + drawer + routage → Tasks 3 & 4 ✓
- E. Tests + vérif visuelle → Steps de test de chaque task + Task 4 Step 6 ✓
- Tiebreak : garde-fou — `len(prises) != 1` → None (Task 3) et `prises[0]` (Task 2) ; cas multi-prise non gold-platé, conforme au hors-périmètre. ✓

**Placeholder scan :** aucun TBD/TODO ; tout le code est fourni.

**Type consistency :** `_nets_derives -> set` (T1) consommé en `& {...}` (T3) et `_nets_derives(graphe)` (T2) ✓ ; `_reseau_derive_ilot -> dict{top,prise,serie,shunt}` (T3) consommé par `_draw_reseau_derive(d, info, ci)` et `_make_fig` (T4) ✓ ; `_compo_2bornes` produit/consommé en T3 ✓ ; `_est_gnd`/`_PASSIFS` définis T1, importés T3 ✓.
