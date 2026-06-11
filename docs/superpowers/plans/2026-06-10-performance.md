# Performance grosses netlists — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire passer l'analyse de 5000 composants de 17 minutes à moins de 10 secondes, en corrigeant les détecteurs quadratiques (qui sont aussi électriquement faux) et en différant l'enrichissement.

**Architecture:** Quatre correctifs ciblés dans `circuit_analyzer/detecteur.py` (skip rails dans pont diviseur, skip paires rail-rail dans absorbeur RC, groupement par net de base dans miroir, anti-vol avant `_enrichir`), un cache dans `circuit_analyzer/satellites.py`, un plafond d'affichage dans `circuit_analyzer/rapport.py`, plus l'outillage (`tools/benchmark.py`, `tests/test_performance.py`).

**Tech Stack:** Python 3, NetworkX, pytest. Spec : `docs/superpowers/specs/2026-06-10-performance-design.md`.

**Contrainte permanente :** toutes les chaînes de rapport restent compatibles cp1252 (pas de `≈ ⚠ → ≥ ─` ; utiliser `~`, `ATTENTION`, `->`, `>=`, `-`). Pas de `Co-Authored-By` dans les commits.

---

### Task 1: Pont diviseur — le nœud milieu doit être non-rail

Un diviseur de tension n'a jamais GND/VCC/PE comme nœud milieu. C'est le correctif principal : sur GND, le détecteur énumérait deg² paires de R.

**Files:**
- Modify: `circuit_analyzer/detecteur.py` (~ligne 992, `detecter_pont_diviseur` ; + helper `_est_rail` près des alias ligne 28)
- Test: `tests/test_performance_fixes.py` (créer)

- [ ] **Step 1: Write the failing test**

Créer `tests/test_performance_fixes.py` :

```python
"""Tests des correctifs de performance (sous-projet 3) :
détecteurs corrigés électriquement + enrichissement différé."""
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns


def test_pas_de_diviseur_avec_rail_en_noeud_milieu():
    # Deux R qui se rejoignent sur GND : pas un diviseur (le nœud milieu
    # d'un diviseur est toujours un nœud signal).
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'GND'}, '10k'),
        Component('R2', 'R', {'1': 'NET_B', '2': 'GND'}, '4.7k'),
    ]
    results = match_patterns(build_graph(comps))
    tous = [m['circuit_type'] for m in results] + \
           [m['circuit_type'] for m in results.supprimes]
    assert 'Pont diviseur de tension' not in tous


def test_diviseur_legitime_toujours_detecte():
    # VCC -> NET_DIV -> GND : nœud milieu signal, diviseur réel.
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_DIV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_DIV', '2': 'GND'}, '4.7k'),
    ]
    results = match_patterns(build_graph(comps))
    assert any(m['circuit_type'] == 'Pont diviseur de tension' for m in results)
```

- [ ] **Step 2: Run tests to verify the first fails**

Run: `python -m pytest tests/test_performance_fixes.py -v`
Expected: `test_pas_de_diviseur_avec_rail_en_noeud_milieu` FAIL (le faux diviseur R1/R2 via GND est détecté aujourd'hui) ; `test_diviseur_legitime_toujours_detecte` PASS.

- [ ] **Step 3: Implement**

Dans `circuit_analyzer/detecteur.py`, après les alias (ligne ~32, après `is_power = is_power_net`), ajouter :

```python
def _est_rail(noeud) -> bool:
    """Vrai si le nœud est une masse, une alimentation ou une terre de protection."""
    return bool(noeud) and (
        est_masse(noeud) or est_alimentation(noeud) or is_protective_earth_net(noeud)
    )
```

Dans `detecter_pont_diviseur` (~ligne 1003), au début de la boucle sur les nœuds :

```python
    for noeud in graphe.nodes():
        # Le nœud milieu d'un diviseur est toujours un nœud signal — énumérer
        # les paires de R sur GND/VCC serait à la fois faux et quadratique.
        if _est_rail(noeud):
            continue
        resistances = _voisins_de_type(graphe, noeud, 'R')
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: tout vert (272 tests existants + 2 nouveaux). Si un test existant assertait un diviseur à nœud milieu rail, le mettre à jour (changement de comportement acté dans le spec) et le signaler dans le message de commit.

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/detecteur.py tests/test_performance_fixes.py
git commit -m "fix: pont diviseur exige un noeud milieu non-rail (perf + justesse)"
```

---

### Task 2: Absorbeur RC — ignorer les paires de nœuds toutes deux rails

R∥C entre VCC et GND = bleeder + découplage, pas un snubber.

**Files:**
- Modify: `circuit_analyzer/detecteur.py` (~ligne 1039, `detecter_absorbeur_rc`)
- Test: `tests/test_performance_fixes.py`

- [ ] **Step 1: Write the failing test**

Ajouter à `tests/test_performance_fixes.py` :

```python
def test_pas_de_snubber_entre_rails():
    # R et C en parallèle entre VCC et GND : bleeder + découplage,
    # pas un absorbeur RC.
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'GND'}, '10k'),
        Component('C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    tous = [m['circuit_type'] for m in results] + \
           [m['circuit_type'] for m in results.supprimes]
    assert 'Absorbeur RC' not in tous


def test_snubber_legitime_toujours_detecte():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '100'),
        Component('C1', 'C', {'1': 'NET_A', '2': 'NET_B'}, '10nF'),
    ]
    results = match_patterns(build_graph(comps))
    assert any(m['circuit_type'] == 'Absorbeur RC' for m in results)
```

- [ ] **Step 2: Run tests to verify the first fails**

Run: `python -m pytest tests/test_performance_fixes.py -v`
Expected: `test_pas_de_snubber_entre_rails` FAIL (l'absorbeur VCC/GND apparaît aujourd'hui dans les supprimés, C1 étant pris par le découplage).

- [ ] **Step 3: Implement**

Dans `detecter_absorbeur_rc` (~ligne 1040), dans la boucle sur les voisins :

```python
    for noeud in graphe.nodes():
        for voisin in graphe.neighbors(noeud):
            # R parallèle C entre deux rails = bleeder + découplage, pas un snubber.
            if _est_rail(noeud) and _est_rail(voisin):
                continue
            paire = tuple(sorted([noeud, voisin]))
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: tout vert.

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/detecteur.py tests/test_performance_fixes.py
git commit -m "fix: absorbeur RC ignore les paires de noeuds rail-rail"
```

---

### Task 3: Miroir de courant — grouper les BJT par net de base

Aujourd'hui toutes les paires de BJT du schéma sont comparées (O(n²)) ; le miroir exige une base commune, donc on n'apparie qu'au sein d'un groupe de même base.

**Files:**
- Modify: `circuit_analyzer/detecteur.py:493-523` (`detecter_miroir_courant`)
- Test: `tests/test_performance_fixes.py`

- [ ] **Step 1: Write the pinning test (passe avant ET après — c'est un refactor)**

```python
def test_miroir_apparie_uniquement_par_base_commune():
    comps = [
        Component('Q1', 'Q', {'B': 'NB1', 'C': 'NC1', 'E': 'GND'}),
        Component('Q2', 'Q', {'B': 'NB1', 'C': 'NC2', 'E': 'GND'}),
        Component('Q3', 'Q', {'B': 'NB2', 'C': 'NC3', 'E': 'GND'}),
        Component('Q4', 'Q', {'B': 'NB2', 'C': 'NC4', 'E': 'GND'}),
    ]
    from circuit_analyzer.detecteur import detecter_miroir_courant
    matches = detecter_miroir_courant(build_graph(comps))
    paires = {frozenset(m['components']) for m in matches}
    assert paires == {frozenset({'Q1', 'Q2'}), frozenset({'Q3', 'Q4'})}
```

- [ ] **Step 2: Run to verify it passes (comportement actuel correct, structure lente)**

Run: `python -m pytest tests/test_performance_fixes.py::test_miroir_apparie_uniquement_par_base_commune -v`
Expected: PASS.

- [ ] **Step 3: Refactor**

Remplacer le corps de `detecter_miroir_courant` (lignes 493-523, après la docstring) par :

```python
    resultats = []
    composants = graphe.graph.get('components', {})

    # Grouper par net de base : le miroir exige une base commune, inutile
    # (et quadratique) de comparer des BJT de bases différentes.
    groupes: dict = {}
    for ref, comp in composants.items():
        if comp.type != 'Q':
            continue
        base     = comp.pins.get('B')
        emetteur = comp.pins.get('E')
        if not base or not emetteur or not est_masse(emetteur):
            continue
        groupes.setdefault(base, []).append((ref, comp))

    for base, bjts in groupes.items():
        for i in range(len(bjts)):
            for j in range(i + 1, len(bjts)):
                ref1, q1 = bjts[i]
                ref2, q2 = bjts[j]
                resultats.append({
                    'circuit_type': 'Miroir de courant BJT',
                    'components': [ref1, ref2],
                    'nodes': [base, q1.pins.get('C', ''), q2.pins.get('C', '')],
                })

    return resultats
```

(Le `deja_vus` disparaît : chaque paire d'un groupe n'est énumérée qu'une fois.)

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: tout vert.

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/detecteur.py tests/test_performance_fixes.py
git commit -m "perf: miroir de courant groupe les BJT par net de base"
```

---

### Task 4: Enrichissement différé dans `analyser()`

`_enrichir()` (calcul de confiance complet) est appelé avant le test anti-vol : 1.37 M de matches supprimés enrichis pour rien à 5000 composants. Les supprimés gardent le match brut (`circuit_type`, `components`, `nodes`) — `rapport.py` a déjà le fallback `s.get('locked_components', s['components'])`.

**Files:**
- Modify: `circuit_analyzer/detecteur.py:1453-1460` (boucle d'`analyser()`)
- Modify: `tests/test_confidence.py:248-262` (`test_suppressed_contains_overlapping_match`)
- Test: `tests/test_performance_fixes.py`

- [ ] **Step 1: Write the failing test**

```python
def test_supprimes_non_enrichis():
    # L'enrichissement (confiance) ne doit plus être calculé pour les
    # matches supprimés — seuls circuit_type/components/nodes sont garantis.
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_MID'}, '10k'),
        Component('R2', 'R', {'1': 'NET_MID', '2': 'GND'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    assert results.supprimes   # chevauchement filtre RC / pont diviseur
    for s in results.supprimes:
        assert 'circuit_type' in s and 'components' in s
        assert 'confidence' not in s
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_performance_fixes.py::test_supprimes_non_enrichis -v`
Expected: FAIL (`'confidence' not in s` faux aujourd'hui).

- [ ] **Step 3: Implement**

Dans `analyser()` (lignes 1453-1460), remplacer :

```python
    for detecter in tous_les_detecteurs:
        for match in detecter(graphe):
            match_enrichi = _enrichir(match, graphe)
            if any(c in composants_utilises for c in match['components']):
                supprimes.append(match_enrichi)
                continue
            composants_utilises.update(match['components'])
            circuits_trouves.append(match_enrichi)
```

par :

```python
    for detecter in tous_les_detecteurs:
        for match in detecter(graphe):
            # Test anti-vol AVANT enrichissement : inutile de calculer la
            # confiance des matches supprimés (ils peuvent être très nombreux).
            if any(c in composants_utilises for c in match['components']):
                supprimes.append(match)
                continue
            composants_utilises.update(match['components'])
            circuits_trouves.append(_enrichir(match, graphe))
```

- [ ] **Step 4: Update the existing test**

Dans `tests/test_confidence.py`, `test_suppressed_contains_overlapping_match` (lignes 248-262) : remplacer la boucle finale

```python
    # Les supprimés ont aussi les champs de confiance
    for s in results.supprimes:
        assert 'confidence' in s
```

par :

```python
    # Les supprimés sont des matches bruts (non enrichis depuis le sous-projet perf)
    for s in results.supprimes:
        assert 'circuit_type' in s
        assert 'components' in s
```

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: tout vert. Vérifier en particulier `tests/test_reporter.py` et le rendu GUI (`gui/tab_analyze.py`) : si l'un d'eux lit `confidence`/`functional_category` sur un supprimé, utiliser `.get()` avec défaut.

- [ ] **Step 6: Commit**

```bash
git add circuit_analyzer/detecteur.py tests/test_performance_fixes.py tests/test_confidence.py
git commit -m "perf: enrichissement differe apres le test anti-vol dans analyser()"
```

---

### Task 5: Cache des nœuds internes/rails dans `_absorber_annexes`

`_noeuds_internes(h)`/`_rails_alim(h)` sont recalculés pour chaque paire annexe×hôte (satellites.py:157,163). Les hôtes ne changent pas de `nodes` pendant l'absorption — pré-calculer une fois.

**Files:**
- Modify: `circuit_analyzer/satellites.py:144-167` (`_absorber_annexes`)

- [ ] **Step 1: Refactor (couvert par tests/test_satellites.py existants)**

Dans `_absorber_annexes`, remplacer :

```python
    hotes = [m for m in circuits
             if len(m['components']) > 1 and m['circuit_type'] not in _ANNEXES]
    if not hotes:
        return

    a_retirer = []
    for annexe in circuits:
        role = _ANNEXES.get(annexe['circuit_type'])
        if role is None or len(annexe['components']) != 1:
            continue
        noeuds_annexe = {n for n in annexe.get('nodes', []) if n}

        # 1) Hôtes partageant un nœud signal (rattachement fort)
        hotes_signal = [h for h in hotes if noeuds_annexe & _noeuds_internes(h)]
        if hotes_signal:
            hote = max(hotes_signal, key=lambda h: h.get('confidence', 0))
            score = annexe.get('confidence', SEUIL_SUR)
        else:
            # 2) Hôtes partageant seulement un rail : possible si UN SEUL candidat
            hotes_rail = [h for h in hotes if noeuds_annexe & _rails_alim(h)]
```

par :

```python
    # Pré-calcul par hôte : les nœuds d'un match ne changent pas pendant
    # l'absorption, inutile de les reclasser pour chaque paire annexe x hôte.
    infos_hotes = [(m, _noeuds_internes(m), _rails_alim(m)) for m in circuits
                   if len(m['components']) > 1 and m['circuit_type'] not in _ANNEXES]
    if not infos_hotes:
        return

    a_retirer = []
    for annexe in circuits:
        role = _ANNEXES.get(annexe['circuit_type'])
        if role is None or len(annexe['components']) != 1:
            continue
        noeuds_annexe = {n for n in annexe.get('nodes', []) if n}

        # 1) Hôtes partageant un nœud signal (rattachement fort)
        hotes_signal = [h for h, internes, _ in infos_hotes if noeuds_annexe & internes]
        if hotes_signal:
            hote = max(hotes_signal, key=lambda h: h.get('confidence', 0))
            score = annexe.get('confidence', SEUIL_SUR)
        else:
            # 2) Hôtes partageant seulement un rail : possible si UN SEUL candidat
            hotes_rail = [h for h, _, rails in infos_hotes if noeuds_annexe & rails]
```

(La suite de la fonction — `if len(hotes_rail) != 1`, `_ajouter_satellite`, retrait — est inchangée.)

- [ ] **Step 2: Run the satellites suite then the full suite**

Run: `python -m pytest tests/test_satellites.py -q` puis `python -m pytest tests/ -q`
Expected: tout vert (refactor pur, comportement identique).

- [ ] **Step 3: Commit**

```bash
git add circuit_analyzer/satellites.py
git commit -m "perf: cache noeuds internes/rails par hote dans _absorber_annexes"
```

---

### Task 6: Rapport — plafonner l'affichage des matches supprimés à 50

**Files:**
- Modify: `circuit_analyzer/rapport.py:129-140` (section supprimés)
- Test: `tests/test_performance_fixes.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rapport_plafonne_les_supprimes_a_50():
    from circuit_analyzer.rapport import generer_rapport

    class FauxResultats(list):
        pass

    resultats = FauxResultats([])
    resultats.ilots = []
    resultats.supprimes = [
        {'circuit_type': 'Pont diviseur de tension',
         'components': [f'R{2*i}', f'R{2*i+1}'], 'nodes': ['N1', 'N2', 'N3']}
        for i in range(80)
    ]
    rapport = generer_rapport(resultats, 'test.txt', 0, [])
    assert 'Matches supprimés (80)' in rapport
    assert '... et 30 autres matches supprimés' in rapport
    assert rapport.count('déjà dans un autre circuit') == 50
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_performance_fixes.py::test_rapport_plafonne_les_supprimes_a_50 -v`
Expected: FAIL (80 lignes affichées, pas de ligne « ... et N autres »).

- [ ] **Step 3: Implement**

Dans `circuit_analyzer/rapport.py`, remplacer la section supprimés (lignes 129-140) :

```python
    # Matches supprimés (composants déjà pris) — affichage plafonné :
    # sur une grosse netlist ils peuvent se compter en milliers.
    _PLAFOND_SUPPRIMES = 50
    supprimes = getattr(resultats, 'supprimes', [])
    if supprimes:
        lignes.append(f'\nMatches supprimés ({len(supprimes)}) — composants déjà utilisés :')
        for s in supprimes[:_PLAFOND_SUPPRIMES]:
            ref_conflit = next(
                (c for c in s.get('locked_components', s['components'])
                 if c in classifies), '?'
            )
            lignes.append(
                f'    - {s["circuit_type"]} [{", ".join(s["components"])}]'
                f' — "{ref_conflit}" déjà dans un autre circuit'
            )
        if len(supprimes) > _PLAFOND_SUPPRIMES:
            lignes.append(
                f'    ... et {len(supprimes) - _PLAFOND_SUPPRIMES} autres matches supprimés'
            )
```

(`_PLAFOND_SUPPRIMES = 50` peut aussi être défini au niveau module, à côté de `_SEP`.)

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: tout vert.

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/rapport.py tests/test_performance_fixes.py
git commit -m "feat: rapport plafonne l'affichage des matches supprimes a 50"
```

---

### Task 7: Outillage — `tools/benchmark.py`

Netlists synthétiques (blocs relay-driver répliqués, nets uniques par bloc), tableau des temps. Sert à valider la cible et à détecter les régressions futures.

**Files:**
- Create: `tools/benchmark.py`

- [ ] **Step 1: Create the tool**

```python
"""
benchmark.py — Mesure le temps d'analyse sur des netlists synthétiques.

Usage : python tools/benchmark.py [tailles...]
        python tools/benchmark.py            # 100 500 1000 2000 5000
        python tools/benchmark.py 100 500    # tailles personnalisées

Chaque bloc (8 composants) réplique un étage de commande de relais :
transistor + diviseur de base, relais + roue libre, pont diviseur, découplage.
Les nets sont uniques par bloc (préfixe B{i}_), seuls VCC et GND sont partagés
— comme dans un vrai schéma multi-étages.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.detecteur import analyser


def bloc(i: int) -> list:
    """Un étage de commande de relais (8 composants, nets propres au bloc)."""
    p = f'B{i}_'
    return [
        Component(p + 'Q1', 'Q', {'B': p + 'NB', 'C': p + 'NC', 'E': 'GND'}),
        Component(p + 'R1', 'R', {'1': p + 'CMD', '2': p + 'NB'}, '1k'),
        Component(p + 'R2', 'R', {'1': p + 'NB', '2': 'GND'}, '10k'),
        Component(p + 'K1', 'K', {'A1': p + 'NC', 'A2': 'VCC',
                                  'C': p + 'KC', 'NC': p + 'KN'}),
        Component(p + 'D1', 'D', {'A': p + 'NC', 'K': 'VCC'}),
        Component(p + 'R3', 'R', {'1': 'VCC', '2': p + 'DIV'}, '10k'),
        Component(p + 'R4', 'R', {'1': p + 'DIV', '2': 'GND'}, '4.7k'),
        Component(p + 'C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF'),
    ]


def netlist_synthetique(nb_composants: int) -> list:
    composants = []
    i = 0
    while len(composants) < nb_composants:
        composants.extend(bloc(i))
        i += 1
    return composants[:nb_composants]


def mesurer(nb_composants: int) -> None:
    composants = netlist_synthetique(nb_composants)

    debut = time.perf_counter()
    graphe = build_graph(composants)
    t_graphe = time.perf_counter() - debut

    debut = time.perf_counter()
    resultats = analyser(graphe)
    t_analyse = time.perf_counter() - debut

    print(f'{len(composants):5d} comps | graphe {t_graphe:6.2f}s | '
          f'analyse {t_analyse:8.2f}s | {len(resultats)} circuits, '
          f'{len(resultats.supprimes)} supprimes, {len(resultats.ilots)} ilots',
          flush=True)


if __name__ == '__main__':
    tailles = [int(a) for a in sys.argv[1:]] or [100, 500, 1000, 2000, 5000]
    for taille in tailles:
        mesurer(taille)
```

- [ ] **Step 2: Run it on small sizes to validate the tool**

Run: `python tools/benchmark.py 100 500`
Expected: deux lignes de tableau ; à ce stade (correctifs Tasks 1-5 en place) 500 comps doit déjà être < 1 s (baseline avant : 9.56 s à 496).

- [ ] **Step 3: Commit**

```bash
git add tools/benchmark.py
git commit -m "feat: tools/benchmark.py pour mesurer l'analyse sur netlists synthetiques"
```

---

### Task 8: Garde-fou — `tests/test_performance.py`

1000 composants analysés en < 5 s. Seuil large anti-flaky, mais qui échoue franchement si un quadratique revient (baseline avant correctifs : ~45 s extrapolés à 1000).

**Files:**
- Create: `tests/test_performance.py`

- [ ] **Step 1: Write the test**

```python
"""Garde-fou performance : échoue si un comportement quadratique revient.

Seuil volontairement large (5 s pour 1000 composants, ~1 s attendu) pour
rester stable sur une machine chargée tout en détectant une régression
d'ordre de grandeur.
"""
import time

from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns


def _bloc(i: int) -> list:
    """Même étage de relais que tools/benchmark.py (8 composants)."""
    p = f'B{i}_'
    return [
        Component(p + 'Q1', 'Q', {'B': p + 'NB', 'C': p + 'NC', 'E': 'GND'}),
        Component(p + 'R1', 'R', {'1': p + 'CMD', '2': p + 'NB'}, '1k'),
        Component(p + 'R2', 'R', {'1': p + 'NB', '2': 'GND'}, '10k'),
        Component(p + 'K1', 'K', {'A1': p + 'NC', 'A2': 'VCC',
                                  'C': p + 'KC', 'NC': p + 'KN'}),
        Component(p + 'D1', 'D', {'A': p + 'NC', 'K': 'VCC'}),
        Component(p + 'R3', 'R', {'1': 'VCC', '2': p + 'DIV'}, '10k'),
        Component(p + 'R4', 'R', {'1': p + 'DIV', '2': 'GND'}, '4.7k'),
        Component(p + 'C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF'),
    ]


def test_1000_composants_en_moins_de_5_secondes():
    composants = []
    for i in range(125):           # 125 blocs x 8 = 1000 composants
        composants.extend(_bloc(i))
    graphe = build_graph(composants)

    debut = time.perf_counter()
    resultats = match_patterns(graphe)
    duree = time.perf_counter() - debut

    assert duree < 5.0, f'Analyse de 1000 composants en {duree:.1f}s (limite 5s)'
    assert len(resultats) > 0
```

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_performance.py -v`
Expected: PASS en ~1 s d'analyse.

- [ ] **Step 3: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: tout vert.

- [ ] **Step 4: Commit**

```bash
git add tests/test_performance.py
git commit -m "test: garde-fou performance (1000 composants < 5 s)"
```

---

### Task 9: Validation finale — benchmark 5000, relay_driver, README

**Files:**
- Modify: `README.md` (section performance/outillage)

- [ ] **Step 1: Run the full benchmark**

Run: `python tools/benchmark.py` (en arrière-plan si > 2 min, mais ne devrait plus l'être)
Expected: 5000 composants < 10 s (cible du spec), 500 < 1 s. Noter le tableau complet.

- [ ] **Step 2: Verify on the real case**

Run: `python main.py circuits_industriels/relay_driver.xml --output chk_perf.txt` puis inspecter `chk_perf.txt`.
Expected: plus aucun « Pont diviseur de tension » avec GND/VCC en nœud milieu ; les R concernées redeviennent satellites ou non-classifiées ; les vrais diviseurs (nœud milieu signal) toujours présents. Supprimer `chk_perf.txt` après inspection.

- [ ] **Step 3: Update README**

Ajouter au README (section appropriée, par ex. après les îlots) un court passage :

```markdown
## Performance

L'analyse est calibrée pour les netlists industrielles : ~1 s pour 1000
composants, < 10 s pour 5000 (mesuré avec `tools/benchmark.py`).

- `python tools/benchmark.py` — tableau des temps sur netlists synthétiques
  (100 à 5000 composants).
- `tests/test_performance.py` — garde-fou dans la suite : 1000 composants
  doivent s'analyser en moins de 5 s.

Remplacer les chiffres par les valeurs réellement mesurées au Step 1.
```

- [ ] **Step 4: Final full suite**

Run: `python -m pytest tests/ -q`
Expected: tout vert.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: section performance dans le README (benchmark + garde-fou)"
```

---

## Self-Review (effectuée)

- **Couverture du spec :** correctif diviseur → Task 1 ; absorbeur rail-rail → Task 2 ; miroir par base → Task 3 ; enrichissement différé → Task 4 ; cache absorption → Task 5 ; plafond rapport → Task 6 ; benchmark → Task 7 ; garde-fou → Task 8 ; critères de succès (5000 < 10 s, relay_driver sans faux diviseurs, suite verte) → Task 9. Pas de gap.
- **Placeholders :** aucun.
- **Cohérence des types :** `_est_rail(noeud)` défini Task 1, utilisé Task 2 ; `bloc(i)` de Task 7 dupliqué volontairement en `_bloc(i)` dans Task 8 (les tests ne doivent pas importer `tools/`).
