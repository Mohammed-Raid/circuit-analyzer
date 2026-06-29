# Détection cas RC inverses — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reclasser deux topologies d'ampli à AOP aujourd'hui noyées dans « Amplificateur inverseur » : Zin=R∥C → « Ampli inverseur + boost HF », Zf=R+C série → « Ampli inverseur + action intégrale ».

**Architecture:** Deux nouveaux détecteurs dans `detecteur.py`, insérés avant `detecter_amplificateur_inverseur` dans `_DETECTEURS_COMPLEXES` (priorité). Ils émettent une structure `{Zin, Zf}` standard → le drawer inverseur existant les rend (boîtes Z cliquables). Helpers de structure factorisés depuis l'existant.

**Tech Stack:** Python, NetworkX (graphe réduit), pytest, schemdraw/matplotlib (rendu).

## Global Constraints

- Fichiers : `circuit_analyzer/detecteur.py`, `circuit_analyzer/patterns/opamp.py`, `gui/circuit_viewer.py`. Style : docstrings `@brief`, commentaires français.
- **Libellés exacts** (vus dans l'app) : `"Ampli inverseur + boost HF (AOP)"` et `"Ampli inverseur + action intégrale (AOP)"`.
- **Zéro régression** : dérivateur idéal (C seul) reste « Dérivateur (AOP) » ; intégrateur idéal/leaky reste « Intégrateur (AOP) » ; inverseur R/R pur reste « Amplificateur inverseur (AOP) ». La suite existante doit rester verte.
- Ne JAMAIS ajouter `Co-Authored-By: Claude` aux commits.
- Tests rendu : `import matplotlib; matplotlib.use("Agg")` en tête.
- Composition d'impédance : série = `"A+B"`, parallèle = `"A//B"` ; `impedance.arbre_expr` retourne `('serie'|'parallele', [('feuille', ref), ...])`.
- Détecteur : parcours d'arêtes sur `graphe.edges(IN-, data=True)`, chaque arête porte `refs`, `composition` ; filtre `_type_correspond(data, 'R', inclure_z=True)` accepte type `'R'` ou `'Z'`.

---

### Task 1 : Helpers de structure RC + refactor

**Files:**
- Modify: `circuit_analyzer/detecteur.py` (ajouter 2 helpers ; refactor `_entree_capacitive` ~ligne 317, `_feedback_capacitif` ~ligne 239)
- Test: `tests/test_cas_rc_inverses.py` (créer)

**Interfaces:**
- Consumes: `impedance.arbre_expr(composition)`.
- Produces:
  - `_est_rc_serie(bloc, composants) -> bool` (série de 2 feuilles {R, C})
  - `_est_rc_parallele(bloc, composants) -> bool` (parallèle de 2 feuilles {R, C})

- [ ] **Step 1: Écrire les tests des helpers (RED)**

```python
# tests/test_cas_rc_inverses.py
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer import detecteur


def _rc():
    return {"R1": Composant("R1", "R", {}), "C1": Composant("C1", "C", {})}


def test_est_rc_serie_vrai():
    bloc = {"refs": ["R1", "C1"], "composition": "R1+C1"}
    assert detecteur._est_rc_serie(bloc, _rc())


def test_est_rc_serie_faux_si_parallele():
    bloc = {"refs": ["R1", "C1"], "composition": "R1//C1"}
    assert not detecteur._est_rc_serie(bloc, _rc())


def test_est_rc_parallele_vrai():
    bloc = {"refs": ["R1", "C1"], "composition": "R1//C1"}
    assert detecteur._est_rc_parallele(bloc, _rc())


def test_est_rc_parallele_faux_si_deux_r():
    comps = {"R1": Composant("R1", "R", {}), "R2": Composant("R2", "R", {})}
    bloc = {"refs": ["R1", "R2"], "composition": "R1//R2"}
    assert not detecteur._est_rc_parallele(bloc, comps)
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_cas_rc_inverses.py -k "est_rc" -q`
Expected: FAIL (`AttributeError: module ... has no attribute '_est_rc_serie'`).

- [ ] **Step 3: Ajouter les helpers (avant `_feedback_capacitif`, ~ligne 239)**

```python
def _est_rc_serie(bloc, composants) -> bool:
    """@brief Vrai si le bloc est une série de 2 feuilles {une R, une C}."""
    if len(bloc.get("refs", [])) != 2:
        return False
    arbre = impedance.arbre_expr(bloc["composition"])
    if arbre and arbre[0] == "serie" and all(c[0] == "feuille" for c in arbre[1]):
        tset = sorted(composants[c[1]].type for c in arbre[1] if c[1] in composants)
        return tset == ["C", "R"]
    return False


def _est_rc_parallele(bloc, composants) -> bool:
    """@brief Vrai si le bloc est un parallèle de 2 feuilles {une R, une C}."""
    if len(bloc.get("refs", [])) != 2:
        return False
    arbre = impedance.arbre_expr(bloc["composition"])
    if arbre and arbre[0] == "parallele" and all(c[0] == "feuille" for c in arbre[1]):
        tset = sorted(composants[c[1]].type for c in arbre[1] if c[1] in composants)
        return tset == ["C", "R"]
    return False
```

- [ ] **Step 4: Refactoriser `_entree_capacitive` (réutilise `_est_rc_serie`)**

Remplacer le corps après le check « C seul » :

```python
def _entree_capacitive(bloc, composants) -> bool:
    """@brief Vrai si le bloc d'entrée est capacitif (dérivateur idéal ou réel).

    Idéal : condensateur seul. Réel : R + C en série (`_est_rc_serie`).
    """
    refs = bloc['refs']
    types = [composants[r].type for r in refs if r in composants]
    if not any(t == 'C' for t in types):
        return False
    if len(refs) == 1:
        return types == ['C']
    return _est_rc_serie(bloc, composants)
```

- [ ] **Step 5: Refactoriser `_feedback_capacitif` (réutilise `_est_rc_parallele`)**

```python
def _feedback_capacitif(bloc, composants) -> bool:
    """@brief Vrai si le bloc de contre-réaction est capacitif (intégrateur idéal/leaky).

    Idéal : condensateur seul. Leaky : R // C (`_est_rc_parallele`).
    """
    refs = bloc['refs']
    types = [composants[r].type for r in refs if r in composants]
    if not any(t == 'C' for t in types):
        return False
    if len(refs) == 1:
        return types == ['C']
    return _est_rc_parallele(bloc, composants)
```

- [ ] **Step 6: Lancer les tests helpers + la suite détection complète**

Run: `python -m pytest tests/test_cas_rc_inverses.py tests/test_confidence.py -q`
Expected: PASS (helpers verts + détection AOP existante inchangée).

- [ ] **Step 7: Commit**

```bash
git add circuit_analyzer/detecteur.py tests/test_cas_rc_inverses.py
git commit -m "refactor(detection): helpers _est_rc_serie/_est_rc_parallele (RC structure)"
```

---

### Task 2 : Détecteur « boost HF » (Zin = R∥C)

**Files:**
- Modify: `circuit_analyzer/detecteur.py` (ajouter `detecter_derivateur_partiel` ; l'insérer dans `_DETECTEURS_COMPLEXES` ~ligne 1454, juste avant `detecter_amplificateur_inverseur`)
- Modify: `circuit_analyzer/patterns/opamp.py` (wrapper + entrée dans `OPAMP_PATTERNS`)
- Test: `tests/test_cas_rc_inverses.py`

**Interfaces:**
- Consumes: `_est_rc_parallele`, `_feedback_capacitif`, `_type_correspond`.
- Produces: `detecter_derivateur_partiel(graphe) -> list[dict]` (circuit_type `"Ampli inverseur + boost HF (AOP)"`).

- [ ] **Step 1: Écrire le test de détection + non-régression (RED)**

```python
# tests/test_cas_rc_inverses.py
def _types(comps):
    return [m["circuit_type"] for m in detecteur.analyser(construire_graphe(comps))]


def test_boost_hf_detecte():
    # Zin = Rin // Cin (parallele a l'entree), Zf = Rf -> boost HF.
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Cin", "C", {"1": "VIN", "2": "M"}, "100n"),
        Composant("Rf", "R", {"1": "M", "2": "VOUT"}, "100k"),
    ]
    assert "Ampli inverseur + boost HF (AOP)" in _types(comps)


def test_derivateur_ideal_inchange():
    # C seul a l'entree, Rf feedback -> reste Derivateur (pas boost HF).
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Cin", "C", {"1": "VIN", "2": "M"}, "100n"),
        Composant("Rf", "R", {"1": "M", "2": "VOUT"}, "100k"),
    ]
    t = _types(comps)
    assert "Dérivateur (AOP)" in t
    assert "Ampli inverseur + boost HF (AOP)" not in t


def test_inverseur_pur_inchange():
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Rf", "R", {"1": "M", "2": "VOUT"}, "100k"),
    ]
    t = _types(comps)
    assert "Amplificateur inverseur (AOP)" in t
    assert "boost HF" not in " ".join(t)
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_cas_rc_inverses.py -k "boost_hf or derivateur_ideal or inverseur_pur" -q`
Expected: FAIL sur `test_boost_hf_detecte` (le cas est classé « Amplificateur inverseur (AOP) »).

- [ ] **Step 3: Ajouter le détecteur (après `detecter_derivateur`, ~ligne 393)**

```python
def detecter_derivateur_partiel(graphe):
    """@brief Ampli inverseur à entrée R∥C : gain DC fini + boost HF (+20 dB/déc).

    Zin = R // C (parallèle), Zf résistive. Distinct du dérivateur idéal (C série)
    et de l'inverseur pur (R). @return list[dict].
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
        feedback = entree = None
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
        if (feedback and entree
                and _est_rc_parallele(entree, composants)
                and not _feedback_capacitif(feedback, composants)):
            resultats.append({
                'circuit_type': 'Ampli inverseur + boost HF (AOP)',
                'components': [ref_aop] + feedback['refs'] + entree['refs'],
                'nodes': [comp.pins.get('IN+', ''), entree_neg, sortie],
                'impedances': {'Zin': entree, 'Zf': feedback},
                'gain': '−Zf/Zin',
            })
    return resultats
```

- [ ] **Step 4: Enregistrer dans `_DETECTEURS_COMPLEXES` (avant l'inverseur)**

Dans la liste `_DETECTEURS_COMPLEXES`, juste avant la ligne `detecter_amplificateur_inverseur,` :

```python
    detecter_derivateur_partiel,           # Zin R∥C : inverseur + boost HF
    detecter_amplificateur_inverseur,      # R entrée + R feedback
```

- [ ] **Step 5: Ajouter le wrapper Pattern dans `opamp.py`**

Avant `OPAMP_PATTERNS` :

```python
class PartialDifferentiator(Pattern):
    """@brief Pattern « Ampli inverseur + boost HF (AOP) » (délègue à detecteur)."""
    name = "Ampli inverseur + boost HF (AOP)"
    def match(self, graph): return detecteur.detecter_derivateur_partiel(graph)
```

Et l'insérer dans `OPAMP_PATTERNS` juste avant `InvertingAmplifier()` :

```python
    PartialDifferentiator(),
    InvertingAmplifier(),
```

- [ ] **Step 6: Lancer le test + régression**

Run: `python -m pytest tests/test_cas_rc_inverses.py tests/test_confidence.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add circuit_analyzer/detecteur.py circuit_analyzer/patterns/opamp.py tests/test_cas_rc_inverses.py
git commit -m "feat(detection): ampli inverseur + boost HF (Zin R//C)"
```

---

### Task 3 : Détecteur « action intégrale » (Zf = R+C série)

**Files:**
- Modify: `circuit_analyzer/detecteur.py` (ajouter `detecter_correcteur_pi` ; l'insérer dans `_DETECTEURS_COMPLEXES` avant `detecter_amplificateur_inverseur`)
- Modify: `circuit_analyzer/patterns/opamp.py` (wrapper + `OPAMP_PATTERNS`)
- Test: `tests/test_cas_rc_inverses.py`

**Interfaces:**
- Consumes: `_est_rc_serie`, `_entree_capacitive`, `_type_correspond`.
- Produces: `detecter_correcteur_pi(graphe) -> list[dict]` (circuit_type `"Ampli inverseur + action intégrale (AOP)"`).

- [ ] **Step 1: Écrire le test (RED)**

```python
# tests/test_cas_rc_inverses.py
def test_action_integrale_detecte():
    # Zin = Rin, Zf = Rf + Cf en serie -> action integrale (PI).
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Rf", "R", {"1": "M", "2": "X"}, "10k"),
        Composant("Cf", "C", {"1": "X", "2": "VOUT"}, "100n"),
    ]
    assert "Ampli inverseur + action intégrale (AOP)" in _types(comps)


def test_integrateur_ideal_inchange():
    # Cf seul en feedback -> reste Integrateur (pas action integrale).
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Cf", "C", {"1": "M", "2": "VOUT"}, "100n"),
    ]
    t = _types(comps)
    assert "Intégrateur (AOP)" in t
    assert "action intégrale" not in " ".join(t)
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_cas_rc_inverses.py -k "action_integrale or integrateur_ideal" -q`
Expected: FAIL sur `test_action_integrale_detecte` (classé « Amplificateur inverseur (AOP) »).

- [ ] **Step 3: Ajouter le détecteur (après `detecter_derivateur_partiel`)**

```python
def detecter_correcteur_pi(graphe):
    """@brief Ampli inverseur à feedback R+C série : action intégrale en BF (PI).

    Zin résistive, Zf = R + C (série). Distinct de l'intégrateur idéal/leaky
    (C seul / R∥C) et de l'inverseur pur. @return list[dict].
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
        feedback = entree = None
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
        if (feedback and entree
                and _est_rc_serie(feedback, composants)
                and not _entree_capacitive(entree, composants)):
            resultats.append({
                'circuit_type': 'Ampli inverseur + action intégrale (AOP)',
                'components': [ref_aop] + feedback['refs'] + entree['refs'],
                'nodes': [comp.pins.get('IN+', ''), entree_neg, sortie],
                'impedances': {'Zin': entree, 'Zf': feedback},
                'gain': '−Zf/Zin',
            })
    return resultats
```

- [ ] **Step 4: Enregistrer dans `_DETECTEURS_COMPLEXES` (avant l'inverseur)**

Juste avant `detecter_amplificateur_inverseur,` (et après `detecter_derivateur_partiel,`) :

```python
    detecter_derivateur_partiel,           # Zin R∥C : inverseur + boost HF
    detecter_correcteur_pi,                # Zf R+C série : inverseur + action intégrale
    detecter_amplificateur_inverseur,      # R entrée + R feedback
```

- [ ] **Step 5: Wrapper Pattern dans `opamp.py`**

```python
class PIController(Pattern):
    """@brief Pattern « Ampli inverseur + action intégrale (AOP) » (délègue à detecteur)."""
    name = "Ampli inverseur + action intégrale (AOP)"
    def match(self, graph): return detecteur.detecter_correcteur_pi(graph)
```

Dans `OPAMP_PATTERNS`, avant `InvertingAmplifier()` (à côté de `PartialDifferentiator()`) :

```python
    PartialDifferentiator(),
    PIController(),
    InvertingAmplifier(),
```

- [ ] **Step 6: Lancer le test + régression**

Run: `python -m pytest tests/test_cas_rc_inverses.py tests/test_confidence.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add circuit_analyzer/detecteur.py circuit_analyzer/patterns/opamp.py tests/test_cas_rc_inverses.py
git commit -m "feat(detection): ampli inverseur + action integrale (Zf R+C serie)"
```

---

### Task 4 : Rendu (libellés + drawer) + vérif visuelle

**Files:**
- Modify: `gui/circuit_viewer.py` (`_DRAWERS` ~ligne 3245, `_ROLE_ETAGE` ~ligne 2410)
- Test: `tests/test_cas_rc_inverses.py`
- Create: `tools/render_rc_inverses.py`

**Interfaces:**
- Consumes: `_draw_inverting_amp` (existant), `_make_fig`, `_circuit_principal_ilot`.

- [ ] **Step 1: Écrire le test de rendu (RED)**

```python
# tests/test_cas_rc_inverses.py
import matplotlib
matplotlib.use("Agg")
import gui.circuit_viewer as cv


def _ilot_fig(comps):
    g = construire_graphe(comps)
    res = detecteur.analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    p = cv._circuit_principal_ilot(ilot, g, res)
    return cv._make_fig(p, ci, cv._DRAWERS[p["circuit_type"]],
                        matches=cv._matches_for_island(ilot, res)), p


def test_boost_hf_rendu_cliquable():
    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Cin", "C", {"1": "VIN", "2": "M"}, "100n"),
        Composant("Rf", "R", {"1": "M", "2": "VOUT"}, "100k"),
    ]
    fig, p = _ilot_fig(comps)
    assert p["circuit_type"] == "Ampli inverseur + boost HF (AOP)"
    assert len(fig._z_hitboxes) >= 2          # Zin et Zf cliquables
    txts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert not any("non disponible" in t for t in txts)


def test_role_etage_nouveaux_types():
    assert cv._ROLE_ETAGE["Ampli inverseur + boost HF (AOP)"]
    assert cv._ROLE_ETAGE["Ampli inverseur + action intégrale (AOP)"]
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `python -m pytest tests/test_cas_rc_inverses.py -k "boost_hf_rendu or role_etage" -q`
Expected: FAIL (`KeyError` : type absent de `_DRAWERS` / `_ROLE_ETAGE`).

- [ ] **Step 3: Mapper les types dans `_DRAWERS`**

Dans le dict `_DRAWERS` (gui/circuit_viewer.py), après `"Amplificateur inverseur (AOP)": _draw_inverting_amp,` :

```python
    "Ampli inverseur + boost HF (AOP)":        _draw_inverting_amp,
    "Ampli inverseur + action intégrale (AOP)": _draw_inverting_amp,
```

- [ ] **Step 4: Ajouter les rôles courts dans `_ROLE_ETAGE`**

Dans le dict `_ROLE_ETAGE`, après `"Amplificateur inverseur (AOP)": "Inverseur",` :

```python
    "Ampli inverseur + boost HF (AOP)":         "Inverseur + boost HF",
    "Ampli inverseur + action intégrale (AOP)": "Inverseur + action intégrale",
```

- [ ] **Step 5: Lancer le test + la suite complète**

Run: `python -m pytest tests/test_cas_rc_inverses.py -q && python -m pytest -q`
Expected: PASS (tout vert, aucune régression).

- [ ] **Step 6: Script de rendu visuel + inspection**

```python
# tools/render_rc_inverses.py
"""Rend les 2 montages RC reclasses en PNG pour inspection."""
import os, sys
import matplotlib; matplotlib.use("Agg")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer import detecteur
from gui import circuit_viewer as cv

CASES = {
    "boost_hf": [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Cin", "C", {"1": "VIN", "2": "M"}, "100n"),
        Composant("Rf", "R", {"1": "M", "2": "VOUT"}, "100k"),
    ],
    "action_integrale": [
        Composant("U1", "U", {"IN+": "GND", "IN-": "M", "OUT": "VOUT"}),
        Composant("Rin", "R", {"1": "VIN", "2": "M"}, "10k"),
        Composant("Rf", "R", {"1": "M", "2": "X"}, "10k"),
        Composant("Cf", "C", {"1": "X", "2": "VOUT"}, "100n"),
    ],
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_renders")
os.makedirs(OUT, exist_ok=True)
for nom, comps in CASES.items():
    g = construire_graphe(comps); res = detecteur.analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    p = cv._circuit_principal_ilot(ilot, g, res)
    fig = cv._make_fig(p, ci, cv._DRAWERS[p["circuit_type"]],
                       matches=cv._matches_for_island(ilot, res))
    fig.savefig(os.path.join(OUT, nom + ".png"), dpi=110, bbox_inches="tight")
    print(nom, "->", p["circuit_type"])
```

Run: `python tools/render_rc_inverses.py`
Then: ouvrir `tools/_renders/boost_hf.png` et `action_integrale.png` (outil Read). Vérifier : AOP + Zin/Zf en boîtes Z bleues, libellé correct, pas de chevauchement.

- [ ] **Step 7: Nettoyer + commit**

```bash
rm -rf tools/_renders
git add gui/circuit_viewer.py tools/render_rc_inverses.py tests/test_cas_rc_inverses.py
git commit -m "feat(ilot): rendu cliquable des montages boost HF / action integrale"
```

---

## Self-Review

- **Couverture spec :** helpers + refactor → Task 1 ; détecteur boost HF + ordre + wrapper → Task 2 ; détecteur PI + ordre + wrapper → Task 3 ; rendu (libellés + drawer) + visuel → Task 4. Non-régression couverte Tasks 2/3 (dérivateur/intégrateur idéaux, inverseur pur) + suite complète Task 4.
- **Placeholders :** aucun ; tout le code est fourni.
- **Cohérence des types :** `_est_rc_serie`/`_est_rc_parallele(bloc, composants) -> bool` utilisés identiquement (Tasks 1-3) ; libellés `"Ampli inverseur + boost HF (AOP)"` / `"Ampli inverseur + action intégrale (AOP)"` identiques partout (détecteur, wrapper, `_DRAWERS`, `_ROLE_ETAGE`, tests).
- **Ordre de détection :** les 2 nouveaux insérés ensemble juste avant `detecter_amplificateur_inverseur` ; mutuellement exclusifs des idéaux par structure.
