# Moteur de réduction Z — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire un moteur qui réduit tout réseau passif R/L/C d'un graphe de circuit en impédances équivalentes Z (dipôles), série-d'abord puis parallèle, en préservant la liste des vrais composants — base du nouveau pipeline.

**Architecture:** Nouveau module `circuit_analyzer/impedance.py`, indépendant de l'ancien `reduction.py` (qui reste branché dans `detecteur.py` jusqu'au sous-projet 2). Fonction publique `reduire(graphe)` qui renvoie une copie réduite du `MultiGraph` : chaque arête passive porte un dict Z (`ref`, `type`, `refs`, `composition`, `value`). Les nœuds « bornes » (broches actives, rails, jonctions irréductibles) ne sont jamais éliminés. Les fusibles sont rendus transparents.

**Tech Stack:** Python 3, NetworkX (`MultiGraph`), pytest. Réutilise `circuit_analyzer.patterns.base` (`is_ground_net`, `is_power_net`, `is_protective_earth_net`) et `circuit_analyzer.composant` (`Composant`, `construire_graphe`).

---

## Modèle de données (rappel du spec §3)

Une arête du graphe réduit porte ces attributs :

| clé | composite | singleton |
|-----|-----------|-----------|
| `ref` | `'Z1'`, `'Z2'`… | vraie ref (`'R1'`) |
| `type` | `'R'`/`'C'`/`'L'` (homogène) ou `'Z'` (mixte) | vrai type |
| `refs` | `['R1','R2']` | `['R1']` |
| `composition` | `'R1+R2'`, `'(R1//C1)'` | `'R1'` (= ref) |
| `value` | la composition | vraie valeur (`'10k'`) |

Règle de composition (déterministe, à tester telle quelle) :
- série de deux exprs `a`, `b` → `f"{a}+{b}"`
- parallèle d'exprs → chaque opérande contenant un `+` est mis entre parenthèses, puis jointes par `//`, puis le tout entre parenthèses : `"(" + "//".join(...) + ")"`.

Exemples : `R1+R2`, `(R1//C1)`, `((R1+R2)//C1)`.

---

## File Structure

- **Create** `circuit_analyzer/impedance.py` — moteur de réduction Z (ce plan).
- **Create** `tests/test_impedance.py` — tests du moteur (ce plan).
- L'ancien `circuit_analyzer/reduction.py` n'est **pas touché** (déprécié au sous-projet 2).

---

### Task 1 : Squelette du module + `_combiner_type`

**Files:**
- Create: `circuit_analyzer/impedance.py`
- Test: `tests/test_impedance.py`

- [ ] **Step 1 : Écrire le test qui échoue**

```python
# tests/test_impedance.py
"""
@file test_impedance.py
@brief Tests du moteur de réduction Z (circuit_analyzer/impedance.py).
"""
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer import impedance


def _graphe(*composants):
    """@brief Construit un graphe de test à partir de composants."""
    return construire_graphe(list(composants))


def _aretes(graphe):
    """@brief (frozenset(nœuds), type, ref) triées, pour comparaison stable."""
    return sorted(
        (tuple(sorted((u, v))), d['type'], d['ref'])
        for u, v, d in graphe.edges(data=True)
    )


def test_combiner_type_homogene_et_mixte():
    assert impedance._combiner_type('R', 'R') == 'R'
    assert impedance._combiner_type('C', 'C') == 'C'
    assert impedance._combiner_type('R', 'C') == 'Z'
    assert impedance._combiner_type('Z', 'R') == 'Z'
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

Run: `python -m pytest tests/test_impedance.py::test_combiner_type_homogene_et_mixte -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'circuit_analyzer.impedance'`

- [ ] **Step 3 : Écrire l'implémentation minimale**

```python
# circuit_analyzer/impedance.py
"""
@file impedance.py
@brief Réduction des réseaux passifs R/L/C en impédances équivalentes Z.

Pipeline « Z d'abord » : on simplifie les chaînes SÉRIE en un bloc, puis ce qui
est en PARALLÈLE avec ces blocs, itéré jusqu'à point fixe. Le résultat est une
impédance Z — un dipôle qui est aussi un sous-circuit consommé par les grands
montages (inverseur, intégrateur…). But premier : qu'aucun composant passif ne
reste « non classifié » — tout R/L/C devient au minimum une Z singleton.
"""
import networkx as nx

from circuit_analyzer.patterns.base import (
    is_ground_net, is_power_net, is_protective_earth_net,
)

# Seuls ces types fusionnent en impédance.
TYPES_REDUCTIBLES = {'R', 'C', 'L'}


def _combiner_type(t1: str, t2: str) -> str:
    """@brief Type équivalent : le type commun, ou 'Z' (mixte) sinon.

    @param t1 Type du premier composant ('R', 'C', 'L' ou 'Z').
    @param t2 Type du second.
    @return str Type commun si t1 == t2, sinon 'Z'.
    """
    return t1 if t1 == t2 else 'Z'
```

- [ ] **Step 4 : Lancer le test, vérifier qu'il passe**

Run: `python -m pytest tests/test_impedance.py::test_combiner_type_homogene_et_mixte -v`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/impedance.py tests/test_impedance.py
git commit -m "feat(impedance): squelette module + _combiner_type"
```

---

### Task 2 : `reduire()` — graphe sans composite reste identique (non-régression)

**Files:**
- Modify: `circuit_analyzer/impedance.py`
- Test: `tests/test_impedance.py`

- [ ] **Step 1 : Écrire le test qui échoue**

```python
def test_aucune_reduction_graphe_inchange():
    # Deux R indépendantes (aucun nœud interne fusionnable) → graphe identique.
    g = _graphe(
        Composant('R1', 'R', {'1': 'IN', '2': 'OUT'}, '10k'),
        Composant('R2', 'R', {'1': 'VCC', '2': 'GND'}, '1k'),
    )
    reduit = impedance.reduire(g)
    assert _aretes(reduit) == _aretes(g)
    # Les valeurs réelles sont préservées sur les singletons.
    vals = {d['ref']: d['value'] for _, _, d in reduit.edges(data=True)}
    assert vals == {'R1': '10k', 'R2': '1k'}
    # Chaque singleton porte refs/composition cohérents.
    r1 = next(d for _, _, d in reduit.edges(data=True) if d['ref'] == 'R1')
    assert r1['refs'] == ['R1'] and r1['composition'] == 'R1'
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

Run: `python -m pytest tests/test_impedance.py::test_aucune_reduction_graphe_inchange -v`
Expected: FAIL — `AttributeError: module 'circuit_analyzer.impedance' has no attribute 'reduire'`

- [ ] **Step 3 : Écrire l'implémentation minimale**

Ajouter à `circuit_analyzer/impedance.py` :

```python
def _est_rail(net) -> bool:
    """@brief Vrai si le net est masse, alimentation ou terre de protection.

    @param net Nom du net (peut être vide/None).
    @return bool True si rail.
    """
    if not net:
        return False
    return is_ground_net(net) or is_power_net(net) or is_protective_earth_net(net)


def _graphe_de_travail(graphe) -> nx.MultiGraph:
    """@brief Sous-graphe des seules arêtes passives réductibles (R/L/C), annotées.

    @param graphe Graphe d'origine.
    @return nx.MultiGraph Arêtes R/L/C avec (type, refs, expr, value).
    """
    W = nx.MultiGraph()
    for u, v, data in graphe.edges(data=True):
        if data.get('type') in TYPES_REDUCTIBLES:
            ref = data['ref']
            W.add_edge(u, v, type=data['type'], refs=[ref], expr=ref,
                       value=data.get('value', ''))
    return W


def reduire(graphe) -> nx.MultiGraph:
    """@brief Réduit les réseaux passifs R/L/C en impédances équivalentes Z.

    @param graphe MultiGraph d'origine (arêtes 2-broches + dict 'components').
    @return nx.MultiGraph Copie réduite : chaque arête passive porte un dict Z
            (ref, type, refs, composition, value). Les arêtes non réductibles et
            le dict 'components' sont conservés tels quels.
    """
    W = _graphe_de_travail(graphe)

    # Reconstruire le graphe réduit : on retire les arêtes passives d'origine et
    # on réémet celles de W (réduites ou non).
    reduit = graphe.copy()
    for u, v, k, data in list(reduit.edges(keys=True, data=True)):
        if data.get('type') in TYPES_REDUCTIBLES:
            reduit.remove_edge(u, v, k)

    compteur = 0
    for u, v, data in W.edges(data=True):
        refs = data['refs']
        if len(refs) > 1:
            compteur += 1
            reduit.add_edge(u, v, ref=f"Z{compteur}", type=data['type'],
                            refs=list(refs), composition=data['expr'],
                            value=data['expr'])
        else:
            reduit.add_edge(u, v, ref=refs[0], type=data['type'],
                            refs=list(refs), composition=refs[0],
                            value=data.get('value', ''))

    # Élaguer les nœuds devenus isolés par la réduction (ex. le milieu d'une
    # chaîne série) — sauf s'ils sont une broche d'un composant actif.
    actifs = set()
    for comp in reduit.graph.get('components', {}).values():
        actifs.update(n for n in comp.pins.values() if n)
    for n in list(reduit.nodes()):
        if reduit.degree(n) == 0 and n not in actifs:
            reduit.remove_node(n)

    return reduit
```

- [ ] **Step 4 : Lancer le test, vérifier qu'il passe**

Run: `python -m pytest tests/test_impedance.py::test_aucune_reduction_graphe_inchange -v`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/impedance.py tests/test_impedance.py
git commit -m "feat(impedance): reduire() squelette + singletons non-regression"
```

---

### Task 3 : Bornes + passe SÉRIE

**Files:**
- Modify: `circuit_analyzer/impedance.py`
- Test: `tests/test_impedance.py`

- [ ] **Step 1 : Écrire le test qui échoue**

```python
def test_serie_deux_resistances_entre_bornes():
    # IN ─R1─ MID ─R2─ OUT : MID interne degré 2 → fusion en Z1 = R1+R2.
    # IN et OUT sont des feuilles (degré 1) → bornes, jamais éliminées.
    g = _graphe(
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '1k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'OUT'}, '2k'),
    )
    reduit = impedance.reduire(g)
    aretes = [d for _, _, d in reduit.edges(data=True)]
    assert len(aretes) == 1
    z = aretes[0]
    assert z['type'] == 'R'
    assert sorted(z['refs']) == ['R1', 'R2']
    assert z['composition'] == 'R1+R2'
    assert z['ref'] == 'Z1'
    assert 'MID' not in reduit.nodes()
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

Run: `python -m pytest tests/test_impedance.py::test_serie_deux_resistances_entre_bornes -v`
Expected: FAIL — deux arêtes au lieu d'une (pas encore de passe série)

- [ ] **Step 3 : Écrire l'implémentation minimale**

Ajouter `_bornes` et `_passe_serie`, et brancher la boucle dans `reduire` (avant la reconstruction). Insérer ces fonctions avant `reduire`, et modifier `reduire` :

```python
def _bornes(graphe, W) -> set:
    """@brief Nœuds jamais éliminés : rails, broches actives, jonctions
    touchées par une arête non réductible.

    Les feuilles (degré 1 dans W) ne peuvent de toute façon pas être éliminées
    par la passe série (qui exige un degré 2), inutile de les lister ici.

    @param graphe Graphe d'origine.
    @param W Graphe de travail des arêtes passives.
    @return set Ensemble des nœuds-bornes.
    """
    bornes = set()
    for n in graphe.nodes():
        if _est_rail(n):
            bornes.add(n)
    for comp in graphe.graph.get('components', {}).values():
        if len(comp.pins) != 2:
            bornes.update(v for v in comp.pins.values() if v)
    for u, v, data in graphe.edges(data=True):
        if data.get('type') not in TYPES_REDUCTIBLES:
            bornes.add(u)
            bornes.add(v)
    return bornes


def _passe_serie(W: nx.MultiGraph, bornes: set) -> bool:
    """@brief Élimine en une passe les nœuds internes de degré 2 non-bornes.

    Chaque tel nœud fusionne ses deux arêtes en un dipôle série a+b.

    @param W Graphe de travail (muté en place).
    @param bornes Nœuds à ne jamais éliminer.
    @return bool True si au moins une fusion a eu lieu.
    """
    change = False
    for n in list(W.nodes()):
        if n in bornes or W.degree(n) != 2:
            continue
        aretes = list(W.edges(n, keys=True, data=True))
        if len(aretes) != 2:  # garde-fou (multi-arête résiduelle = parallèle)
            continue
        (u1, v1, _k1, d1), (u2, v2, _k2, d2) = aretes
        a = v1 if u1 == n else u1
        b = v2 if u2 == n else u2
        if a == b:
            continue  # banc parallèle : laisser la passe parallèle agir
        type_eq = _combiner_type(d1['type'], d2['type'])
        refs = d1['refs'] + d2['refs']
        expr = f"{d1['expr']}+{d2['expr']}"
        W.remove_node(n)
        W.add_edge(a, b, type=type_eq, refs=refs, expr=expr, value='')
        change = True
    return change
```

Modifier `reduire` pour appeler la boucle après `_graphe_de_travail(graphe)` :

```python
    W = _graphe_de_travail(graphe)
    bornes = _bornes(graphe, W)

    while True:
        if _passe_serie(W, bornes):
            continue
        break
```

(le reste de `reduire` — reconstruction — inchangé)

- [ ] **Step 4 : Lancer le test, vérifier qu'il passe**

Run: `python -m pytest tests/test_impedance.py::test_serie_deux_resistances_entre_bornes -v`
Expected: PASS

- [ ] **Step 5 : Lancer toute la suite du module + commit**

Run: `python -m pytest tests/test_impedance.py -v`
Expected: PASS (3 tests)

```bash
git add circuit_analyzer/impedance.py tests/test_impedance.py
git commit -m "feat(impedance): bornes + passe serie"
```

---

### Task 4 : Passe PARALLÈLE

**Files:**
- Modify: `circuit_analyzer/impedance.py`
- Test: `tests/test_impedance.py`

- [ ] **Step 1 : Écrire le test qui échoue**

```python
def test_parallele_r_et_c_meme_paire():
    # R1 // C1 entre A et B (deux feuilles) → Z mixte, composition (R1//C1).
    g = _graphe(
        Composant('R1', 'R', {'1': 'A', '2': 'B'}, '1k'),
        Composant('C1', 'C', {'1': 'A', '2': 'B'}, '1u'),
    )
    reduit = impedance.reduire(g)
    aretes = [d for _, _, d in reduit.edges(data=True)]
    assert len(aretes) == 1
    z = aretes[0]
    assert z['type'] == 'Z'  # mixte R+C
    assert sorted(z['refs']) == ['C1', 'R1']
    assert z['composition'] == '(R1//C1)'
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

Run: `python -m pytest tests/test_impedance.py::test_parallele_r_et_c_meme_paire -v`
Expected: FAIL — deux arêtes restantes (pas de passe parallèle)

- [ ] **Step 3 : Écrire l'implémentation minimale**

Ajouter `_par_operande` et `_passe_parallele`, et brancher dans la boucle de `reduire` (parallèle après série) :

```python
def _par_operande(expr: str) -> str:
    """@brief Parenthèse une expression série avant de l'insérer dans un parallèle.

    @param expr Expression de composition.
    @return str expr entre parenthèses si elle contient un '+' de haut niveau.
    """
    return f"({expr})" if '+' in expr else expr


def _passe_parallele(W: nx.MultiGraph, bornes: set) -> bool:
    """@brief Fusionne en une passe tous les bancs d'arêtes parallèles.

    (Arêtes multiples entre la même paire de nœuds.)

    @param W Graphe de travail (muté en place).
    @param bornes Inutilisé pour l'instant (le parallèle ne supprime pas de nœud) ;
           présent pour symétrie de signature.
    @return bool True si au moins une fusion a eu lieu.
    """
    paires = set()
    for u, v in W.edges():
        if u != v and W.number_of_edges(u, v) > 1:
            paires.add(frozenset((u, v)))

    for paire in paires:
        u, v = tuple(paire)
        paquet = list(W.get_edge_data(u, v).values())
        type_eq = paquet[0]['type']
        refs, exprs = [], []
        for d in paquet:
            type_eq = _combiner_type(type_eq, d['type'])
            refs.extend(d['refs'])
            exprs.append(_par_operande(d['expr']))
        for _ in range(len(paquet)):
            W.remove_edge(u, v)
        W.add_edge(u, v, type=type_eq, refs=refs,
                   expr="(" + "//".join(exprs) + ")", value='')
    return bool(paires)
```

Modifier la boucle de `reduire` (série d'abord, parallèle ensuite) :

```python
    while True:
        if _passe_serie(W, bornes):
            continue
        if _passe_parallele(W, bornes):
            continue
        break
```

- [ ] **Step 4 : Lancer le test, vérifier qu'il passe**

Run: `python -m pytest tests/test_impedance.py::test_parallele_r_et_c_meme_paire -v`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/impedance.py tests/test_impedance.py
git commit -m "feat(impedance): passe parallele (serie d'abord puis parallele)"
```

---

### Task 5 : Imbrication série→parallèle `(R1+R2)//C1`

**Files:**
- Test: `tests/test_impedance.py` (aucune modif de code attendue — vérifie la boucle)

- [ ] **Step 1 : Écrire le test qui échoue (ou valide la boucle)**

```python
def test_serie_puis_parallele_imbrique():
    # A ─R1─ MID ─R2─ B  avec  C1 directement entre A et B.
    # Série d'abord : R1+R2 entre A et B ; puis // C1.
    g = _graphe(
        Composant('R1', 'R', {'1': 'A', '2': 'MID'}, '1k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'B'}, '2k'),
        Composant('C1', 'C', {'1': 'A', '2': 'B'}, '1u'),
    )
    reduit = impedance.reduire(g)
    aretes = [d for _, _, d in reduit.edges(data=True)]
    assert len(aretes) == 1
    z = aretes[0]
    assert z['type'] == 'Z'
    assert sorted(z['refs']) == ['C1', 'R1', 'R2']
    assert z['composition'] == '((R1+R2)//C1)'
    assert 'MID' not in reduit.nodes()
```

- [ ] **Step 2 : Lancer le test**

Run: `python -m pytest tests/test_impedance.py::test_serie_puis_parallele_imbrique -v`
Expected: PASS (la boucle série→parallèle gère déjà ce cas). Si FAIL sur la chaîne de composition, vérifier `_par_operande` et l'ordre des passes.

- [ ] **Step 3 : Commit**

```bash
git add tests/test_impedance.py
git commit -m "test(impedance): imbrication serie puis parallele"
```

---

### Task 6 : Fusion vers un rail (filtre RC isolé → Z = R+C)

**Files:**
- Test: `tests/test_impedance.py`

- [ ] **Step 1 : Écrire le test**

```python
def test_filtre_rc_isole_devient_z_vers_gnd():
    # IN ─R1─ MID ─C1─ GND : MID interne degré 2 (non-borne), GND est un rail
    # mais on AUTORISE la fusion vers le rail → Z1 = R1+C1 entre IN et GND.
    g = _graphe(
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '10k'),
        Composant('C1', 'C', {'1': 'MID', '2': 'GND'}, '100n'),
    )
    reduit = impedance.reduire(g)
    aretes = [d for _, _, d in reduit.edges(data=True)]
    assert len(aretes) == 1
    z = aretes[0]
    assert z['type'] == 'Z'
    assert sorted(z['refs']) == ['C1', 'R1']
    assert z['composition'] == 'R1+C1'
    assert 'MID' not in reduit.nodes()
    assert set(reduit.nodes()) == {'IN', 'GND'}
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il passe**

Run: `python -m pytest tests/test_impedance.py::test_filtre_rc_isole_devient_z_vers_gnd -v`
Expected: PASS — `_passe_serie` n'interdit pas la fusion quand un voisin est un rail (seules les **bornes** bloquent, et un rail n'est borne que s'il porte le nœud central `n`, pas ses voisins). MID n'est ni rail ni borne → éliminé.

> Note : si ce test échoue, c'est qu'une protection « voisin = rail » a été réintroduite par erreur. Le spec §4.1 l'interdit explicitement.

- [ ] **Step 3 : Commit**

```bash
git add tests/test_impedance.py
git commit -m "test(impedance): filtre RC isole se reduit en Z vers GND"
```

---

### Task 7 : Les bornes actives protègent le nœud milieu (diviseur chargé)

**Files:**
- Test: `tests/test_impedance.py`

- [ ] **Step 1 : Écrire le test**

```python
def test_milieu_relie_a_aop_non_fusionne():
    # Pont diviseur VCC ─R1─ MID ─R2─ GND, mais MID alimente IN- d'un AOP.
    # MID est une broche active → borne → NON éliminé : R1 et R2 restent
    # deux singletons distincts (l'AOP les verra séparément au sous-projet 2).
    g = _graphe(
        Composant('U1', 'U', {'IN+': 'P', 'IN-': 'MID', 'OUT': 'O'}),
        Composant('R1', 'R', {'1': 'VCC', '2': 'MID'}, '10k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'GND'}, '10k'),
    )
    reduit = impedance.reduire(g)
    refs = sorted(d['ref'] for _, _, d in reduit.edges(data=True))
    assert refs == ['R1', 'R2']  # pas de Z1, MID préservé
    assert 'MID' in reduit.nodes()
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il passe**

Run: `python -m pytest tests/test_impedance.py::test_milieu_relie_a_aop_non_fusionne -v`
Expected: PASS — `_bornes` ajoute les broches de tout composant à `len(pins) != 2` (donc l'AOP), MID en fait partie.

- [ ] **Step 3 : Commit**

```bash
git add tests/test_impedance.py
git commit -m "test(impedance): borne active protege le noeud milieu"
```

---

### Task 8 : Fusible rendu transparent

**Files:**
- Modify: `circuit_analyzer/impedance.py`
- Test: `tests/test_impedance.py`

- [ ] **Step 1 : Écrire le test qui échoue**

```python
def test_fusible_transparent():
    # VIN ─F1─ N ─R1─ OUT : le fusible est transparent (ses deux nœuds
    # fusionnent). Il ne reste QUE R1, entre VIN et OUT. Aucune arête 'F'.
    g = _graphe(
        Composant('F1', 'F', {'1': 'VIN', '2': 'N'}),
        Composant('R1', 'R', {'1': 'N', '2': 'OUT'}, '1k'),
    )
    reduit = impedance.reduire(g)
    types = sorted(d['type'] for _, _, d in reduit.edges(data=True))
    assert types == ['R']  # plus aucune arête 'F'
    r1 = next(d for _, _, d in reduit.edges(data=True) if d['ref'] == 'R1')
    bornes = {u for u, _, d in reduit.edges(data=True) if d['ref'] == 'R1'}
    bornes |= {v for _, v, d in reduit.edges(data=True) if d['ref'] == 'R1'}
    assert bornes == {'VIN', 'OUT'}  # N a été absorbé dans VIN
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

Run: `python -m pytest tests/test_impedance.py::test_fusible_transparent -v`
Expected: FAIL — une arête 'F' subsiste et N n'est pas absorbé.

- [ ] **Step 3 : Écrire l'implémentation minimale**

Ajouter `_rendre_fusibles_transparents` et l'appeler en tête de `reduire`. Un fusible relie ses deux nets : on choisit un représentant et on renomme l'autre partout (arêtes + broches des composants).

```python
def _rendre_fusibles_transparents(graphe) -> nx.MultiGraph:
    """@brief Fusionne les deux nœuds de chaque fusible (≈ fil ~0 Ω) et retire
    l'arête F. Le fusible disparaît du graphe.

    @param graphe Graphe d'origine.
    @return nx.MultiGraph Copie sans fusible, nets fusionnés.
    """
    # Union-Find des nets reliés par un fusible.
    parent: dict = {}

    def trouver(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def unir(a, b):
        ra, rb = trouver(a), trouver(b)
        if ra != rb:
            parent[rb] = ra

    for _u, _v, data in graphe.edges(data=True):
        if data.get('type') == 'F':
            unir(_u, _v)

    if not parent:  # aucun fusible
        return graphe

    g2 = nx.MultiGraph()
    # Recopier les composants en renommant leurs broches.
    comps = {}
    for ref, comp in graphe.graph.get('components', {}).items():
        comps[ref] = comp
    g2.graph['components'] = comps

    for u, v, data in graphe.edges(data=True):
        if data.get('type') == 'F':
            continue  # le fusible disparaît
        g2.add_edge(trouver(u), trouver(v), **data)
    for n in graphe.nodes():
        g2.add_node(trouver(n))
    # Renommer aussi les broches des composants multi-broches (cohérence des nets).
    for comp in comps.values():
        comp.pins = {p: trouver(net) for p, net in comp.pins.items()}
    return g2
```

Modifier le début de `reduire` :

```python
def reduire(graphe) -> nx.MultiGraph:
    """..."""  # docstring inchangée
    graphe = _rendre_fusibles_transparents(graphe)
    W = _graphe_de_travail(graphe)
    bornes = _bornes(graphe, W)
    # ... (reste inchangé)
```

> Note de conception : `_rendre_fusibles_transparents` mute `comp.pins` des
> composants partagés. Comme `reduire` travaille déjà sur une intention de copie
> réduite, c'est acceptable ici ; si un appelant a besoin du graphe d'origine
> intact, il devra passer une copie. Documenté dans la docstring au sous-projet 2.

- [ ] **Step 4 : Lancer le test, vérifier qu'il passe**

Run: `python -m pytest tests/test_impedance.py::test_fusible_transparent -v`
Expected: PASS

- [ ] **Step 5 : Lancer toute la suite + commit**

Run: `python -m pytest tests/test_impedance.py -v`
Expected: PASS (8 tests)

```bash
git add circuit_analyzer/impedance.py tests/test_impedance.py
git commit -m "feat(impedance): fusible rendu transparent (noeuds fusionnes)"
```

---

### Task 9 : Pont irréductible signalé en bloc

**Files:**
- Modify: `circuit_analyzer/impedance.py`
- Test: `tests/test_impedance.py`

- [ ] **Step 1 : Écrire le test qui échoue**

```python
def test_pont_wheatstone_irreductible_en_bloc():
    # Pont en H : A,B,C,D avec une diagonale R5 entre C et D. Aucun nœud
    # interne de degré 2, aucun banc parallèle → série/parallèle impuissant.
    # On signale le bloc passif comme une Z unique listant tous ses composants.
    g = _graphe(
        Composant('U1', 'U', {'IN+': 'A', 'IN-': 'X', 'OUT': 'B'}),  # ancre A,B
        Composant('R1', 'R', {'1': 'A', '2': 'C'}, '1k'),
        Composant('R2', 'R', {'1': 'A', '2': 'D'}, '1k'),
        Composant('R3', 'R', {'1': 'C', '2': 'B'}, '1k'),
        Composant('R4', 'R', {'1': 'D', '2': 'B'}, '1k'),
        Composant('R5', 'R', {'1': 'C', '2': 'D'}, '1k'),
    )
    reduit = impedance.reduire(g)
    zs = [d for _, _, d in reduit.edges(data=True) if str(d['ref']).startswith('Z')]
    assert len(zs) == 1
    z = zs[0]
    assert sorted(z['refs']) == ['R1', 'R2', 'R3', 'R4', 'R5']
    assert z['type'] == 'Z'
    assert z['composition'].startswith('pont{')
    # Les nœuds internes C et D du pont ont disparu (absorbés dans le bloc).
    assert 'C' not in reduit.nodes() and 'D' not in reduit.nodes()
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

Run: `python -m pytest tests/test_impedance.py::test_pont_wheatstone_irreductible_en_bloc -v`
Expected: FAIL — le pont reste éclaté en 5 arêtes (R1..R5), pas de bloc Z unique.

- [ ] **Step 3 : Écrire l'implémentation minimale**

Après la boucle série/parallèle dans `reduire`, ajouter une passe « bloc irréductible » : toute composante connexe de `W` contenant encore un nœud interne non-borne (donc non réductible par série/parallèle) est repliée en une seule arête entre ses deux bornes de contact, listant tous ses refs.

Ajouter la fonction :

```python
def _replier_blocs_irreductibles(W: nx.MultiGraph, bornes: set) -> None:
    """@brief Replie chaque composante passive non réductible (pont) en une seule
    arête Z entre ses deux bornes de contact.

    @param W Graphe de travail (muté en place).
    @param bornes Nœuds-bornes.
    @return None
    """
    for composante in list(nx.connected_components(W)):
        internes = [n for n in composante if n not in bornes]
        if not internes:
            continue  # déjà réduit (au plus des arêtes borne-à-borne)
        contacts = sorted(n for n in composante if n in bornes)
        if len(contacts) < 2:
            continue  # pas assez de bornes pour replier : laisser le bloc intact
        refs, types = [], set()
        for u, v, d in list(W.edges(composante, data=True)):
            refs.extend(d['refs'])
            types.add(d['type'])
        # Retirer toutes les arêtes et les nœuds internes de la composante.
        for u, v, k in list(W.edges(composante, keys=True)):
            W.remove_edge(u, v, k)
        for n in internes:
            if n in W:
                W.remove_node(n)
        a, b = contacts[0], contacts[1]
        type_eq = next(iter(types)) if len(types) == 1 else 'Z'
        W.add_edge(a, b, type='Z' if len(types) > 1 else type_eq,
                   refs=refs, expr="pont{" + ",".join(sorted(refs)) + "}",
                   value='')
```

Brancher après la boucle dans `reduire` :

```python
    while True:
        if _passe_serie(W, bornes):
            continue
        if _passe_parallele(W, bornes):
            continue
        break

    _replier_blocs_irreductibles(W, bornes)
```

- [ ] **Step 4 : Lancer le test, vérifier qu'il passe**

Run: `python -m pytest tests/test_impedance.py::test_pont_wheatstone_irreductible_en_bloc -v`
Expected: PASS

- [ ] **Step 5 : Lancer toute la suite + commit**

Run: `python -m pytest tests/test_impedance.py -v`
Expected: PASS (9 tests)

```bash
git add circuit_analyzer/impedance.py tests/test_impedance.py
git commit -m "feat(impedance): replie les ponts irreductibles en bloc Z"
```

---

### Task 10 : Vérification de non-régression globale

**Files:**
- (aucune modif — vérification)

- [ ] **Step 1 : Lancer toute la suite de tests du projet**

Run: `python -m pytest -q`
Expected: PASS — aucun test existant cassé (l'ancien `reduction.py` est intact, `impedance.py` est additif).

- [ ] **Step 2 : Vérifier l'import depuis l'app**

Run: `python -c "from circuit_analyzer import impedance; import networkx as nx; print('ok')"`
Expected: affiche `ok`

- [ ] **Step 3 : Commit éventuel (si ajustements)**

```bash
git add -A
git commit -m "chore(impedance): verification non-regression globale"
```

---

## Notes pour les sous-projets suivants (hors périmètre de ce plan)

- **Sous-projet 2 (détecteurs)** : brancher `detecteur.analyser()` sur
  `impedance.reduire()` à la place de `reduire_dipoles`/`expandre_composites` ;
  généraliser les détecteurs actifs pour lire les Z (helper `_impedances_sur`) ;
  supprimer les 7 détecteurs passifs et `reduction.py` ; adapter/retirer
  `tests/test_reduction.py`.
- **Sous-projet 3** : rapport / enrichissement (branche « Impédance Z »,
  panneau non classifiés quasi vide).
- **Sous-projet 4** : dessin par îlot (drawer schemdraw générique).
