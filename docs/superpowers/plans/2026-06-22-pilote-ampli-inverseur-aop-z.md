# Pilote Ampli inverseur (AOP + Zin/Zf cliquables + gain) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afficher un ampli inverseur détecté comme « AOP + boîtes Z (Zin/Zf) cliquables → détail R/L/C » avec le gain `Av = −Zf/Zin`.

**Architecture:** Le détecteur (qui tourne déjà sur le graphe réduit, composite-aware) enrichit son match avec des impédances structurées + le gain. Le drawer de l'inverseur dessine Zin/Zf en boîtes Z à coordonnées explicites et enregistre des zones cliquables ; `show_circuit` câble le clic vers le drill-down série/parallèle existant et affiche le gain.

**Tech Stack:** Python ; networkx ; schemdraw + matplotlib + customtkinter (existants).

## Global Constraints

- Aucun commit ne porte `Co-Authored-By Claude` (directive utilisateur).
- Aucune nouvelle dépendance.
- Branche : `rewrite-simple`.
- Périmètre = **ampli inverseur uniquement**. Repli sûr : un match sans `impedances` garde l'ancien dessin (résistances). Aucune régression sur les autres drawers/montages.
- Suite complète verte.

## File Structure

- `circuit_analyzer/detecteur.py` (modifier) : `detecter_amplificateur_inverseur` ajoute `impedances` + `gain`.
- `gui/circuit_viewer.py` (modifier) : `_make_fig` (passe-plat hitboxes), `show_circuit` (param `graph` + clic + gain), `_draw_inverting_amp` (boîtes Z).
- `gui/tab_analyze.py` (modifier) : passer `graph=self._graph` à `show_circuit`.
- `tests/test_detecteur_aop.py` (créer) ; `tests/test_circuit_viewer.py` (créer).

---

### Task 1 : enrichir la détection de l'ampli inverseur

**Files:**
- Modify: `circuit_analyzer/detecteur.py` (fonction `detecter_amplificateur_inverseur`)
- Test: `tests/test_detecteur_aop.py` (créer)

**Interfaces:**
- Consumes : graphe réduit (arêtes IN-↔OUT et IN-↔entrée portent `refs` + `composition`).
- Produces : le match de l'inverseur gagne
  `match['impedances'] = {'Zin': {'refs':[...],'composition':str,'nodes':(n1,n2)}, 'Zf': {...}}`
  et `match['gain'] = '−Zf/Zin'`.

- [ ] **Step 1 : Écrire le test qui échoue** — créer `tests/test_detecteur_aop.py` :

```python
"""@file test_detecteur_aop.py
@brief Tests d'enrichissement des montages AOP (impedances structurees + gain)."""
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer import detecteur


def _ampli_inverseur_zf_composite():
    # AOP U1 ; entree IN -Rin- INM ; contre-reaction INM -R1- X -R2- OUT (Zf=R1+R2).
    return construire_graphe([
        Composant("U1", "U", {"IN+": "GND", "IN-": "INM", "OUT": "OUT"}),
        Composant("Rin", "R", {"1": "IN", "2": "INM"}, "1k"),
        Composant("R1", "R", {"1": "INM", "2": "X"}, "2k"),
        Composant("R2", "R", {"1": "X", "2": "OUT"}, "3k"),
    ])


def test_inverseur_expose_impedances_et_gain():
    res = detecteur.analyser(_ampli_inverseur_zf_composite())
    inv = [r for r in res if r["circuit_type"] == "Amplificateur inverseur (AOP)"]
    assert len(inv) == 1
    m = inv[0]
    assert m["gain"] == "−Zf/Zin"
    assert set(m["impedances"]["Zf"]["refs"]) == {"R1", "R2"}
    assert "+" in m["impedances"]["Zf"]["composition"]      # Zf composite
    assert m["impedances"]["Zin"]["refs"] == ["Rin"]
    assert m["impedances"]["Zf"]["nodes"] == ("INM", "OUT")
```

- [ ] **Step 2 : Vérifier l'échec** — `python -m pytest tests/test_detecteur_aop.py -q`
  Expected : FAIL (`KeyError: 'gain'` ou `'impedances'`).

- [ ] **Step 3 : Implémenter** — dans `circuit_analyzer/detecteur.py`, REMPLACER le corps de `detecter_amplificateur_inverseur` par :

```python
def detecter_amplificateur_inverseur(graphe):
    """
    @brief Amplificateur inverseur : AOP avec une Z d'entrée sur IN- et une Z de feedback (OUT → IN-).

    @param graphe Graphe NetworkX (réduit) du circuit.
    @return list[dict] Circuits détectés, enrichis de 'impedances' (Zin/Zf) et 'gain'.
    """
    resultats = []
    composants = graphe.graph.get('components', {})

    for ref_aop, comp in composants.items():
        if comp.type != 'U':
            continue

        entree_neg = comp.pins.get('IN-')
        sortie = comp.pins.get('OUT')
        if not entree_neg or not sortie:
            continue

        feedback = None      # {'refs','composition','nodes'}
        entree = None
        for u, v, data in graphe.edges(entree_neg, data=True):
            if not _type_correspond(data, 'R', inclure_z=True):
                continue
            autre = v if u == entree_neg else u
            bloc = {
                'refs': list(data.get('refs', [data['ref']])),
                'composition': data.get('composition', data['ref']),
                'nodes': (entree_neg, autre),
            }
            if autre == sortie:
                feedback = bloc
            elif entree is None:
                entree = bloc

        if feedback and entree:
            resultats.append({
                'circuit_type': 'Amplificateur inverseur (AOP)',
                'components': [ref_aop] + feedback['refs'] + entree['refs'],
                'nodes': [comp.pins.get('IN+', ''), entree_neg, sortie],
                'impedances': {'Zin': entree, 'Zf': feedback},
                'gain': '−Zf/Zin',
            })

    return resultats
```

- [ ] **Step 4 : Vérifier le succès** — `python -m pytest tests/test_detecteur_aop.py -q` → PASS. Puis `python -m pytest -q` → pas de régression (la détection de l'inverseur reste fonctionnelle ; `components` toujours présent).

- [ ] **Step 5 : Commit**
```bash
git add circuit_analyzer/detecteur.py tests/test_detecteur_aop.py
git commit -m "feat(detecteur): ampli inverseur expose Zin/Zf (refs+composition) et le gain"
```

---

### Task 2 : plumbing — hitboxes dans _make_fig + clic & gain dans show_circuit

**Files:**
- Modify: `gui/circuit_viewer.py` (`_make_fig`, `show_circuit`)
- Modify: `gui/tab_analyze.py` (appel `show_circuit`)
- Test: `tests/test_circuit_viewer.py` (créer)

**Interfaces:**
- Produces : `_make_fig` expose `fig._z_hitboxes` (liste alimentée par le drawer via `d._z_hitboxes`). `show_circuit(result, comp_info, parent=None, graph=None)`.
- Consumes : `show_dipole_detail(refs, composition, graph, comp_info, parent)` (déjà en place).

- [ ] **Step 1 : Écrire le test qui échoue** — créer `tests/test_circuit_viewer.py` :

```python
"""@file test_circuit_viewer.py
@brief Tests du builder de figure (passe-plat des zones cliquables Z)."""
from gui import circuit_viewer as cv


def test_make_fig_remonte_les_hitboxes_du_drawer():
    def _faux_drawer(d, result, ci):
        d._z_hitboxes.append((0.0, 1.0, 0.0, 1.0, ["R1"], "R1"))
    fig = cv._make_fig({"circuit_type": "X", "components": []}, {}, _faux_drawer)
    assert getattr(fig, "_z_hitboxes", None) == [(0.0, 1.0, 0.0, 1.0, ["R1"], "R1")]


def test_make_fig_sans_hitbox_liste_vide():
    fig = cv._make_fig({"circuit_type": "X", "components": []}, {}, None)
    assert fig._z_hitboxes == []
```

- [ ] **Step 2 : Vérifier l'échec** — `python -m pytest tests/test_circuit_viewer.py -q`
  Expected : FAIL (`fig` n'a pas `_z_hitboxes`).

- [ ] **Step 3 : Implémenter le passe-plat dans `_make_fig`** — dans `gui/circuit_viewer.py`, fonction `_make_fig`, remplacer le bloc `if drawer_fn:` … (le `with schemdraw.Drawing...`) ET garantir `fig._z_hitboxes`. Précisément, remplacer :

```python
    if drawer_fn:
        try:
            with schemdraw.Drawing(canvas=ax, show=False) as d:
                d.config(fontsize=11, inches_per_unit=0.5)
                drawer_fn(d, result, comp_info)
        except Exception as e:
            ax.text(0.5, 0.5, f"Schéma non disponible\n{e}",
                    ha="center", va="center",
                    transform=ax.transAxes,
                    fontsize=12, color="#64748b")
```

par :

```python
    fig._z_hitboxes = []   # zones cliquables des Z (renseignées par le drawer)
    if drawer_fn:
        try:
            with schemdraw.Drawing(canvas=ax, show=False) as d:
                d.config(fontsize=11, inches_per_unit=0.5)
                d._z_hitboxes = []
                drawer_fn(d, result, comp_info)
                fig._z_hitboxes = list(d._z_hitboxes)
        except Exception as e:
            ax.text(0.5, 0.5, f"Schéma non disponible\n{e}",
                    ha="center", va="center",
                    transform=ax.transAxes,
                    fontsize=12, color="#64748b")
```

- [ ] **Step 4 : Vérifier le test** — `python -m pytest tests/test_circuit_viewer.py -q` → PASS (2).

- [ ] **Step 5 : Câbler le clic + le gain dans `show_circuit`** — dans `gui/circuit_viewer.py`, modifier la signature et le corps de `show_circuit`.

Signature :
```python
def show_circuit(result: dict, comp_info: dict, parent=None, graph=None):
```

Juste après le header (après le `ctk.CTkLabel(hdr, ...)` qui affiche le nom), AJOUTER l'affichage du gain :
```python
    if result.get("gain"):
        ctk.CTkLabel(hdr, text=f"Av = {result['gain']}",
                     font=ctk.CTkFont("Consolas", 12, "bold"),
                     text_color="#34d399").pack(side="right", padx=18)
```

Après le bloc qui crée `canvas` et fait `canvas.get_tk_widget().pack(...)`, AJOUTER le handler de clic :
```python
    def _on_click(event):
        if graph is None or event.xdata is None or event.ydata is None:
            return
        for x0, x1, y0, y1, refs, composition in getattr(fig, "_z_hitboxes", []):
            if x0 <= event.xdata <= x1 and y0 <= event.ydata <= y1:
                show_dipole_detail(refs, composition, graph, comp_info, popup)
                return
    canvas.mpl_connect("button_press_event", _on_click)
```

- [ ] **Step 6 : Mettre à jour le site d'appel** — dans `gui/tab_analyze.py`, remplacer :
```python
        show_circuit(self._result, self._comp_info)
```
par :
```python
        show_circuit(self._result, self._comp_info, graph=self._graph)
```

- [ ] **Step 7 : Vérifier import + suite** —
  `python -c "import gui.circuit_viewer, gui.tab_analyze; print('import ok')"`
  `python -m pytest -q` → vert.

- [ ] **Step 8 : Commit**
```bash
git add gui/circuit_viewer.py gui/tab_analyze.py tests/test_circuit_viewer.py
git commit -m "feat(viewer): show_circuit cable le clic Z (drill-down) et affiche le gain"
```

---

### Task 3 : dessiner l'inverseur en AOP + boîtes Z (Zin/Zf) cliquables

**Files:**
- Modify: `gui/circuit_viewer.py` (`_draw_inverting_amp`)
- Test: `tests/test_circuit_viewer.py` (ajout)

**Interfaces:**
- Consumes : `result['impedances']` (Task 1) ; `d._z_hitboxes` (Task 2) ; `impedance.formater_expr`.
- Produces : un dessin AOP + 2 boîtes Z, et 2 hitboxes dans `d._z_hitboxes`.

- [ ] **Step 1 : Écrire le test qui échoue** — ajouter à `tests/test_circuit_viewer.py` :

```python
def test_draw_inverting_amp_deux_boites_z():
    from gui import circuit_viewer as cv
    result = {
        "circuit_type": "Amplificateur inverseur (AOP)",
        "components": ["U1", "R1", "R2", "Rin"],
        "nodes": ["GND", "INM", "OUT"],
        "impedances": {
            "Zin": {"refs": ["Rin"], "composition": "Rin", "nodes": ("INM", "IN")},
            "Zf": {"refs": ["R1", "R2"], "composition": "R1+R2", "nodes": ("INM", "OUT")},
        },
        "gain": "−Zf/Zin",
    }
    fig = cv._make_fig(result, {}, cv._DRAWERS["Amplificateur inverseur (AOP)"])
    hb = fig._z_hitboxes
    assert len(hb) == 2
    refs = sorted((sorted(b[4]) for b in hb), key=len)
    assert refs[0] == ["Rin"]
    assert refs[1] == ["R1", "R2"]
```

- [ ] **Step 2 : Vérifier l'échec** — `python -m pytest tests/test_circuit_viewer.py -q -k inverting`
  Expected : FAIL (0 hitbox : l'ancien drawer dessine des résistances sans hitbox).

- [ ] **Step 3 : Implémenter** — dans `gui/circuit_viewer.py`, REMPLACER `_draw_inverting_amp` par :

```python
def _draw_inverting_amp(d, result, ci):
    """@brief Dessine « Amplificateur inverseur (AOP) » : AOP + Zin/Zf en blocs Z cliquables.

    Repli : si le match ne porte pas d'impédances structurées, dessin résistances.
    """
    from circuit_analyzer.impedance import formater_expr
    imp = result.get("impedances")
    if not imp:
        rs = _refs(result, ci, "R")
        rf = rs[0] if rs else "Rf"
        rin = rs[1] if len(rs) > 1 else "Rin"
        op = d.add(elm.Opamp().anchor("in1").at((4.5, 0)))
        d.add(elm.Resistor().at(op.in1).left().label(_lbl(rin, ci), loc="top"))
        d.add(elm.Dot().label("IN", loc="left"))
        d.add(elm.Line().at(op.in2).left(1))
        d.add(elm.Ground())
        above = (op.in1[0], op.in1[1] + 1.5)
        d.add(elm.Line().at(op.in1).up(1.5))
        d.add(elm.Resistor().at(above).right().tox(op.out[0]).label(_lbl(rf, ci), loc="top"))
        d.add(elm.Line().toy(op.out[1]))
        d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))
        return

    zin, zf = imp["Zin"], imp["Zf"]
    op = d.add(elm.Opamp().anchor("in1").at((4.5, 0)))
    in1, out = op.in1, op.out

    # Zin : entrée -> IN- (boîte Z horizontale)
    zin_p1 = (in1[0] - 3.0, in1[1])
    d.add(elm.ResistorIEC().at(zin_p1).to(in1).label(
        "Zin\n" + formater_expr(zin["composition"]), loc="top"))
    d.add(elm.Line().at(zin_p1).left(0.7))
    d.add(elm.Dot().label("IN", loc="left"))
    # IN+ à la masse
    d.add(elm.Line().at(op.in2).left(1.0))
    d.add(elm.Ground())
    # Zf : contre-réaction IN- -> OUT (boîte Z horizontale, par le haut)
    above_y = in1[1] + 2.0
    d.add(elm.Line().at(in1).up(2.0))
    zf_p1, zf_p2 = (in1[0], above_y), (out[0], above_y)
    d.add(elm.ResistorIEC().at(zf_p1).to(zf_p2).label(
        "Zf\n" + formater_expr(zf["composition"]), loc="top"))
    d.add(elm.Line().at(zf_p2).toy(out[1]))
    d.add(elm.Line().at(out).right(1.0).label("OUT", loc="right"))

    # Zones cliquables (centrées sur chaque boîte) -> drill-down R/L/C
    hb = getattr(d, "_z_hitboxes", None)
    if hb is not None:
        pad = 0.5
        hb.append((min(zin_p1[0], in1[0]) - pad, max(zin_p1[0], in1[0]) + pad,
                   in1[1] - pad, in1[1] + pad, list(zin["refs"]), zin["composition"]))
        hb.append((min(zf_p1[0], zf_p2[0]) - pad, max(zf_p1[0], zf_p2[0]) + pad,
                   above_y - pad, above_y + pad, list(zf["refs"]), zf["composition"]))
```

- [ ] **Step 4 : Vérifier le test** — `python -m pytest tests/test_circuit_viewer.py -q` → PASS. Puis `python -m pytest -q` → vert.

- [ ] **Step 5 : Commit**
```bash
git add gui/circuit_viewer.py tests/test_circuit_viewer.py
git commit -m "feat(viewer): ampli inverseur dessine en AOP + Zin/Zf (boites Z cliquables)"
```

---

### Task 4 : circuit de démo + vérification visuelle bout-en-bout

**Files:**
- Create: `circuits_industriels/aop_inverseur_zf_composite.xml` (généré)

**Interfaces:** Consomme `generer_xml`, `analyser`, `_make_fig`.

- [ ] **Step 1 : Générer le circuit de démo** — exécuter ce script (puis le supprimer) :

```python
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.xml import generer_xml, lire_xml
from circuit_analyzer import detecteur

comps = [
    Composant("U1", "U", {"IN+": "GND", "IN-": "INM", "OUT": "VOUT"}),
    Composant("Rin", "R", {"1": "VIN", "2": "INM"}, "1k"),
    Composant("R1", "R", {"1": "INM", "2": "XF"}, "4.7k"),   # Zf = R1+R2
    Composant("R2", "R", {"1": "XF", "2": "VOUT"}, "5.3k"),
]
open("circuits_industriels/aop_inverseur_zf_composite.xml", "w", encoding="utf-8").write(
    generer_xml(comps))

# Verif round-trip : detection + impedances
g = construire_graphe(lire_xml("circuits_industriels/aop_inverseur_zf_composite.xml"))
res = detecteur.analyser(g)
inv = [r for r in res if r["circuit_type"] == "Amplificateur inverseur (AOP)"]
assert inv, "inverseur non detecte apres round-trip"
assert "impedances" in inv[0] and inv[0]["gain"] == "−Zf/Zin"
print("OK: inverseur detecte, Zf =", inv[0]["impedances"]["Zf"]["composition"])
```
Expected : `OK: inverseur detecte, Zf = ...` (composition contenant « + »).

- [ ] **Step 2 : Vérification visuelle manuelle** — lancer l'app, ouvrir
  `circuits_industriels/aop_inverseur_zf_composite.xml`, analyser, ouvrir le schéma de
  « Amplificateur inverseur (AOP) ». Vérifier : AOP + boîte **Zin** + boîte **Zf** (composition
  affichée), **Av = −Zf/Zin** dans l'entête, et **clic sur Zf** → détail R1+R2 en série.

- [ ] **Step 3 : Commit**
```bash
git add circuits_industriels/aop_inverseur_zf_composite.xml
git commit -m "feat(demo): ampli inverseur a Zf composite (R1+R2) pour la vue AOP + Z"
```

---

## Vérification finale

- `python -m pytest -q` vert (dont `test_detecteur_aop.py` et `test_circuit_viewer.py`).
- App : `aop_inverseur_zf_composite.xml` → vue « AOP + Zin/Zf » ; clic sur une boîte Z → détail série/parallèle ; gain `Av = −Zf/Zin` affiché.
- Aucune régression sur les autres montages (repli résistances si pas d'`impedances`).
- Aucun commit avec `Co-Authored-By Claude`.
