# Forme série/parallèle dans la vue d'îlot — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quand un îlot est un réseau d'impédances réductible entre VIN et VOUT, `show_island` affiche le schéma série/parallèle « manuel » au lieu du dessin colonnes-bus ; sinon, comportement inchangé.

**Architecture:** Un helper pur reconstruit le sous-graphe de l'îlot depuis les composants originaux, le réduit entre VIN/VOUT et le parse en arbre série/parallèle. `show_island` dessine via `impedance_schematic.dessiner` si l'arbre existe, sinon via l'actuel `_make_island_fig`. Purement additif.

**Tech Stack:** Python ; networkx ; schemdraw + matplotlib (existants) ; modules `circuit_analyzer.impedance`, `gui.impedance_schematic` déjà en place.

## Global Constraints

- Aucun commit ne porte `Co-Authored-By Claude` (directive utilisateur).
- Aucune nouvelle dépendance.
- Branche : `rewrite-simple`.
- `_make_island_fig`, `_build_island_model`, `_draw_island_schematic` et la fenêtre « Ω Impédance équiv. » ne sont PAS modifiés. Les 21 tests d'îlot existants doivent rester verts.

## File Structure

- `gui/circuit_viewer.py` (modifier) : ajouter `_arbre_serie_parallele_ilot(ilot, graph)` ; hook dans `show_island` (remplacer la source de `fig`).
- `tests/test_island_viewer.py` (modifier) : 2 tests du helper pur.

---

### Task 1 : helper série/parallèle pour la vue d'îlot + hook `show_island`

**Files:**
- Modify: `gui/circuit_viewer.py` (ajouter le helper ; modifier `show_island` autour de la ligne `fig = _make_island_fig(model, matches=matches)`)
- Test: `tests/test_island_viewer.py`

**Interfaces:**
- Consumes : `circuit_analyzer.impedance.{bornes_possibles, impedance_equivalente, arbre_expr}` ; `circuit_analyzer.composant.construire_graphe` ; `gui.impedance_schematic.dessiner(arbre, a, b, comps)`.
- Produces : `_arbre_serie_parallele_ilot(ilot, graph) -> tuple | None` renvoyant `(arbre, comps)` ou `None`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_island_viewer.py` (le fichier importe déjà le module viewer ; si besoin, ajouter en tête `from circuit_analyzer.composant import Composant, construire_graphe` et `from gui import circuit_viewer`). Utiliser le nom d'import du viewer déjà présent dans le fichier (souvent `from gui import circuit_viewer as cv` ; sinon utiliser `circuit_viewer`).

```python
def test_arbre_serie_parallele_ilot_reductible_vin_vout():
    from circuit_analyzer.composant import Composant, construire_graphe
    from gui import circuit_viewer
    g = construire_graphe([
        Composant("R1", "R", {"1": "VIN", "2": "M"}, "1k"),
        Composant("R2", "R", {"1": "M", "2": "VOUT"}, "2k"),
        Composant("R3", "R", {"1": "VIN", "2": "VOUT"}, "3k"),
    ])
    ilot = {"label": "Ilot", "composants": ["R1", "R2", "R3"]}
    res = circuit_viewer._arbre_serie_parallele_ilot(ilot, g)
    assert res is not None
    arbre, comps = res
    # (R1+R2)//R3 -> racine parallele.
    assert arbre[0] == "parallele"
    assert set(comps) == {"R1", "R2", "R3"}


def test_arbre_serie_parallele_ilot_sans_vin_vout_renvoie_none():
    from circuit_analyzer.composant import Composant, construire_graphe
    from gui import circuit_viewer
    g = construire_graphe([
        Composant("R1", "R", {"1": "A", "2": "B"}, "1k"),
    ])
    ilot = {"label": "Ilot", "composants": ["R1"]}
    assert circuit_viewer._arbre_serie_parallele_ilot(ilot, g) is None
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run : `python -m pytest tests/test_island_viewer.py -q -k arbre_serie_parallele_ilot`
Expected : FAIL — `AttributeError: module 'gui.circuit_viewer' has no attribute '_arbre_serie_parallele_ilot'`.

- [ ] **Step 3 : Implémenter le helper**

Ajouter dans `gui/circuit_viewer.py` (par ex. juste avant `def show_island`) :

```python
def _arbre_serie_parallele_ilot(ilot, graph):
    """@brief Arbre série/parallèle d'un îlot réductible entre VIN et VOUT.

    Reconstruit le sous-graphe de l'îlot depuis les composants ORIGINAUX, puis le
    réduit symboliquement entre VIN et VOUT.

    @param ilot Îlot détecté (clé "composants" = refs brutes).
    @param graph Graphe original (porte graph["components"] : {ref → Composant}).
    @return (arbre, comps) | None : arbre série/parallèle (cf. impedance.arbre_expr)
            et dict {ref → Composant} du sous-graphe, ou None si non dessinable
            (pas de composant, VIN/VOUT absents, pont Y-Δ, ou non série/parallèle).
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
    expr = impedance.impedance_equivalente(sous, "VIN", "VOUT")
    if expr is None:
        return None
    arbre = impedance.arbre_expr(expr)
    if arbre is None:
        return None
    return arbre, sous.graph["components"]
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

Run : `python -m pytest tests/test_island_viewer.py -q -k arbre_serie_parallele_ilot`
Expected : PASS (2 tests).

- [ ] **Step 5 : Brancher dans `show_island`**

Dans `gui/circuit_viewer.py`, fonction `show_island`, repérer la ligne :

```python
    matches = _matches_for_island(ilot, results)
    fig = _make_island_fig(model, matches=matches)
```

La remplacer par :

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

(Le reste de `show_island` est inchangé : le canvas, le handler `_on_click` qui
lit `getattr(fig, "_z_hitboxes", [])` — absent sur la nouvelle figure, donc pas de
drill-down et pas de crash —, l'export PNG et le bouton Fermer.)

- [ ] **Step 6 : Vérifier la suite complète + import**

Run : `python -c "import gui.circuit_viewer; print('import ok')"`
Run : `python -m pytest -q`
Expected : suite complète verte, dont les 21 tests d'îlot existants et les 2 nouveaux.

- [ ] **Step 7 : Commit**

```bash
git add gui/circuit_viewer.py tests/test_island_viewer.py
git commit -m "feat(viewer): vue d'ilot en serie/parallele quand reductible entre VIN et VOUT"
```

---

## Vérification finale

- `python -m pytest -q` vert.
- Lancer l'app, ouvrir `circuits_industriels/impedance_serie_parallele.xml`, analyser,
  ouvrir le schéma d'îlot : il doit s'afficher en forme série/parallèle (R4 en série
  puis (R1+R2)//R3), pas en colonnes-bus.
- Ouvrir `impedance_pont_wheatstone.xml` : la vue d'îlot doit garder l'ancien dessin
  (pont non réductible en série/parallèle), sans crash.
- Aucun commit avec `Co-Authored-By Claude`.
