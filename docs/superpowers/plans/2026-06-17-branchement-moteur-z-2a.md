# Branchement du moteur Z dans l'analyse (sous-projet 2a) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Brancher `detecteur.analyser()` sur le nouveau moteur `impedance.reduire()`, faire apparaître toute impédance Z (composite ou singleton) comme un résultat « Impédance Z » de première classe, et retirer les 7 détecteurs passifs de l'analyse — pour qu'aucun composant passif ne reste « non classifié ».

**Architecture:** `analyser()` appelle `impedance.reduire(graphe)` à la place de `reduire_dipoles`, construit une table d'expansion `{Z1: [R1,R2]}` depuis le graphe réduit, et conserve `expandre_composites` (recopié dans `impedance.py`). Un nouveau détecteur `detecter_impedances` émet chaque arête Z non consommée par un montage actif comme un résultat « Impédance Z ». Les détecteurs actifs existants restent inchangés : un composite homogène (`R1+R2`, type `R`) est déjà reconnu, puis expansé en vraies refs.

**Tech Stack:** Python 3, NetworkX, pytest. S'appuie sur `circuit_analyzer/impedance.py` (livré en sous-projet 1) et modifie `circuit_analyzer/detecteur.py`.

---

## Périmètre

**DANS 2a :** branchement, expansion, détecteur « Impédance Z », retrait des 7 passifs de la liste `_DETECTEURS_SIMPLES`, enrichissement « Impédance Z », mise à jour des tests du chemin `analyser()`.

**HORS 2a (plans suivants) :**
- 2b : accepter les Z **mixtes** (type `Z`) dans les détecteurs actifs (cas `(R1+C)//R2`).
- 2c : suppression des fonctions passives mortes, de `reduction.py`, des classes `basic_circuits`, des drawers `circuit_viewer`, de la règle DRC « Pont diviseur déséquilibré », et nettoyage final des tests.

Les fonctions `detecter_filtre_*`, `detecter_pont_diviseur`, etc. **restent définies** dans `detecteur.py` (juste retirées de `_DETECTEURS_SIMPLES`) pour ne pas casser `basic_circuits.py`, `circuit_viewer.py` et les tests unitaires qui les appellent directement. Leur suppression est l'objet de 2c.

---

## Décisions de conception (à valider en relecture)

1. **Détecteur Z générique** : émet une entrée par arête Z restante, qu'elle soit composite (`Z1 = R1+R2`) ou singleton (`R1`). Placé en DERNIER, après les détecteurs actifs : l'anti-vol d'`analyser()` saute les Z dont les composants sont déjà pris par un montage actif.
2. **Interaction satellites** : comme tout passif devient un résultat « Impédance Z », la passe satellites n'absorbe plus les R/C passifs comme rôles (pull-up, découplage). C'est cohérent avec la décision « Z générique seulement ». Les annexes mono-composant à **diode** (roue libre, ESD) restent absorbables (elles ne sont pas des Z).
3. **Confiance** d'une « Impédance Z » : neutre (0.80), `functional_category = 'impedance'`.

---

## File Structure

- **Modify** `circuit_analyzer/impedance.py` — ajouter `expandre_composites` + `expansion_depuis_graphe`.
- **Modify** `circuit_analyzer/detecteur.py` — `detecter_impedances`, câblage d'`analyser()`, retrait des 7 passifs, branche `_enrichir`.
- **Test** `tests/test_impedance.py`, `tests/test_integration.py` (et triage des tests cassés).

---

### Task 1 : Expansion des composites dans `impedance.py`

**Files:**
- Modify: `circuit_analyzer/impedance.py`
- Test: `tests/test_impedance.py`

- [ ] **Step 1 : Écrire le test qui échoue**

```python
def test_expansion_depuis_graphe_et_expandre():
    # Chaîne série R1+R2 → Z1 ; l'expansion mappe Z1 -> [R1, R2].
    g = _graphe(
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '1k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'OUT'}, '2k'),
    )
    reduit = impedance.reduire(g)
    exp = impedance.expansion_depuis_graphe(reduit)
    assert exp == {'Z1': ['R1', 'R2']}
    # expandre_composites remplace la ref synthétique par les vraies refs.
    match = {'circuit_type': 'X', 'components': ['Z1'], 'nodes': ['IN', 'OUT']}
    out = impedance.expandre_composites(match, exp)
    assert out['components'] == ['R1', 'R2']
    # match d'origine non muté
    assert match['components'] == ['Z1']
    # sans expansion (singleton), la ref passe telle quelle
    assert impedance.expandre_composites({'components': ['R5']}, {})['components'] == ['R5']
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

Run: `python -m pytest tests/test_impedance.py::test_expansion_depuis_graphe_et_expandre -v`
Expected: FAIL — `AttributeError: module 'circuit_analyzer.impedance' has no attribute 'expansion_depuis_graphe'`

- [ ] **Step 3 : Écrire l'implémentation minimale**

Ajouter à la fin de `circuit_analyzer/impedance.py` :

```python
def expansion_depuis_graphe(reduit) -> dict:
    """@brief Table {ref_synthetique -> [refs_reelles]} des arêtes composites du graphe réduit.

    @param reduit Graphe réduit produit par reduire().
    @return dict Mapping des refs synthétiques 'Zn' vers leurs vraies refs.
    """
    expansion = {}
    for _u, _v, data in reduit.edges(data=True):
        ref = data.get('ref', '')
        refs = data.get('refs', [])
        if len(refs) > 1:
            expansion[ref] = list(refs)
    return expansion


def expandre_composites(match: dict, expansion: dict) -> dict:
    """@brief Remplace dans match['components'] chaque ref synthétique par ses vraies refs.

    @param match Dict du circuit détecté (clé 'components').
    @param expansion Table {ref_synthetique -> [refs_reelles]}.
    @return dict Copie du match aux vraies refs ; l'original n'est pas modifié.
    """
    if not expansion:
        return match
    comps = []
    for ref in match['components']:
        comps.extend(expansion.get(ref, [ref]))
    return {**match, 'components': comps}
```

- [ ] **Step 4 : Lancer le test, vérifier qu'il passe**

Run: `python -m pytest tests/test_impedance.py::test_expansion_depuis_graphe_et_expandre -v`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/impedance.py tests/test_impedance.py
git commit -m "feat(impedance): expansion_depuis_graphe + expandre_composites"
```

---

### Task 2 : Détecteur générique « Impédance Z »

**Files:**
- Modify: `circuit_analyzer/detecteur.py`
- Test: `tests/test_integration.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter dans `tests/test_integration.py` (imports en tête du fichier déjà présents : `Composant`, `construire_graphe`, `analyser` ; sinon les ajouter) :

```python
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.detecteur import detecter_impedances


def test_detecter_impedances_emet_chaque_z():
    # IN ─R1─ MID ─R2─ GND : un seul composite Z1 = R1+R2 entre IN et GND.
    from circuit_analyzer import impedance
    g = construire_graphe([
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '1k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'GND'}, '2k'),
    ])
    reduit = impedance.reduire(g)
    matches = list(detecter_impedances(reduit))
    assert len(matches) == 1
    m = matches[0]
    assert m['circuit_type'] == 'Impédance Z'
    assert m['components'] == ['Z1']           # ref synthétique, expansée par analyser()
    assert set(m['nodes']) == {'IN', 'GND'}
    assert m['composition'] == 'R1+R2'
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

Run: `python -m pytest tests/test_integration.py::test_detecter_impedances_emet_chaque_z -v`
Expected: FAIL — `ImportError: cannot import name 'detecter_impedances'`

- [ ] **Step 3 : Écrire l'implémentation minimale**

Ajouter dans `circuit_analyzer/detecteur.py`, juste avant la section « FONCTION PRINCIPALE » :

```python
def detecter_impedances(graphe):
    """
    @brief Émet chaque arête Z (passive réduite) comme une « Impédance Z ».

    @param graphe Graphe RÉDUIT (sortie de impedance.reduire()).
    @return list[dict] Un match par arête passive, {'circuit_type', 'components',
            'nodes', 'composition'}.

    Placé en dernier dans la chaîne de détection : l'anti-vol d'analyser() saute
    les Z dont les composants sont déjà pris par un montage actif. Ce qui reste
    devient une impédance nommée — plus aucun passif « non classifié ».
    """
    resultats = []
    for u, v, data in graphe.edges(data=True):
        if data.get('type') not in ('R', 'C', 'L', 'Z'):
            continue  # diodes, etc. : pas des impédances passives
        resultats.append({
            'circuit_type': 'Impédance Z',
            'components': [data['ref']],
            'nodes': [u, v],
            'composition': data.get('composition', data['ref']),
        })
    return resultats
```

- [ ] **Step 4 : Lancer le test, vérifier qu'il passe**

Run: `python -m pytest tests/test_integration.py::test_detecter_impedances_emet_chaque_z -v`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/detecteur.py tests/test_integration.py
git commit -m "feat(detecteur): detecteur generique Impedance Z"
```

---

### Task 3 : Câbler `analyser()` sur le moteur Z + retirer les 7 passifs

**Files:**
- Modify: `circuit_analyzer/detecteur.py`
- Test: `tests/test_integration.py`

- [ ] **Step 1 : Écrire le test qui échoue**

```python
def test_analyser_filtre_rc_isole_devient_impedance():
    # Filtre RC isolé : plus de "Filtre RC passe-bas", mais une Impédance Z.
    g = construire_graphe([
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '10k'),
        Composant('C1', 'C', {'1': 'MID', '2': 'GND'}, '100n'),
    ])
    res = analyser(g)
    types = [m['circuit_type'] for m in res]
    assert 'Filtre RC passe-bas' not in types
    assert 'Impédance Z' in types
    z = next(m for m in res if m['circuit_type'] == 'Impédance Z')
    assert sorted(z['components']) == ['C1', 'R1']   # vraies refs après expansion


def test_analyser_inverseur_avec_feedback_composite():
    # Rf = R1+R2 (composite homogène) : l'inverseur reste détecté, refs réelles.
    g = construire_graphe([
        Composant('U1', 'U', {'IN+': 'GND', 'IN-': 'INM', 'OUT': 'OUT'}),
        Composant('Re', 'R', {'1': 'IN', '2': 'INM'}, '1k'),
        Composant('R1', 'R', {'1': 'INM', '2': 'MID'}, '4k7'),
        Composant('R2', 'R', {'1': 'MID', '2': 'OUT'}, '4k7'),
    ])
    res = analyser(g)
    inv = next((m for m in res if m['circuit_type'] == 'Amplificateur inverseur (AOP)'), None)
    assert inv is not None
    # Le feedback composite R1+R2 est expansé en vraies refs dans le montage.
    assert {'U1', 'Re', 'R1', 'R2'} <= set(inv['components'])
```

- [ ] **Step 2 : Lancer les tests, vérifier qu'ils échouent**

Run: `python -m pytest tests/test_integration.py::test_analyser_filtre_rc_isole_devient_impedance tests/test_integration.py::test_analyser_inverseur_avec_feedback_composite -v`
Expected: FAIL — le filtre est encore « Filtre RC passe-bas » et/ou pas d'« Impédance Z ».

- [ ] **Step 3 : Écrire l'implémentation minimale**

Dans `circuit_analyzer/detecteur.py` :

(a) Remplacer l'import en tête :
```python
from circuit_analyzer.reduction import reduire_dipoles, expandre_composites
```
par :
```python
from circuit_analyzer import impedance
from circuit_analyzer.impedance import expandre_composites
```

(b) Réduire `_DETECTEURS_SIMPLES` au seul détecteur Z générique (les 7 passifs sont retirés de la chaîne d'analyse ; leurs fonctions restent définies pour 2c) :
```python
_DETECTEURS_SIMPLES = [
    detecter_impedances,
]
```

(c) Dans `analyser()`, remplacer la ligne :
```python
    graphe_reduit, expansion = reduire_dipoles(graphe)
```
par :
```python
    graphe_reduit = impedance.reduire(graphe)
    expansion = impedance.expansion_depuis_graphe(graphe_reduit)
```

(le reste d'`analyser()` — boucle de détection, `expandre_composites`, satellites, îlots — est inchangé).

- [ ] **Step 4 : Lancer les tests, vérifier qu'ils passent**

Run: `python -m pytest tests/test_integration.py::test_analyser_filtre_rc_isole_devient_impedance tests/test_integration.py::test_analyser_inverseur_avec_feedback_composite -v`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/detecteur.py tests/test_integration.py
git commit -m "feat(detecteur): analyser() branche sur impedance.reduire + retrait passifs"
```

---

### Task 4 : Enrichissement « Impédance Z »

**Files:**
- Modify: `circuit_analyzer/detecteur.py`
- Test: `tests/test_integration.py`

- [ ] **Step 1 : Écrire le test qui échoue**

```python
def test_enrichissement_impedance_z():
    g = construire_graphe([
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '10k'),
        Composant('C1', 'C', {'1': 'MID', '2': 'GND'}, '100n'),
    ])
    res = analyser(g)
    z = next(m for m in res if m['circuit_type'] == 'Impédance Z')
    assert z['functional_category'] == 'impedance'
    assert z['confidence_level'] in ('high', 'medium', 'low')
    # La composition est mentionnée dans les raisons.
    assert any('R1+C1' in r for r in z['reasons'])
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

Run: `python -m pytest tests/test_integration.py::test_enrichissement_impedance_z -v`
Expected: FAIL — `functional_category` vaut `'divers'` et aucune raison ne mentionne la composition.

- [ ] **Step 3 : Écrire l'implémentation minimale**

Dans `_enrichir()` de `circuit_analyzer/detecteur.py`, ajouter une branche AVANT le calcul du niveau de confiance (après les autres `elif ct == …`) :

```python
    elif ct == 'Impédance Z':
        confidence = 0.80
        compo = match.get('composition', '')
        if compo:
            reasons.append(f"Impédance équivalente : {compo}")
        else:
            reasons.append("Impédance passive réduite")
```

Et ajouter l'entrée dans le dict `_CATEGORIES` :
```python
    'Impédance Z':                         'impedance',
```

> Note : `_enrichir` lit `match.get('composition', '')` — la clé est présente sur les
> matches de `detecter_impedances` (Task 2) et absente ailleurs (→ `''`, sans effet).

- [ ] **Step 4 : Lancer le test, vérifier qu'il passe**

Run: `python -m pytest tests/test_integration.py::test_enrichissement_impedance_z -v`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/detecteur.py tests/test_integration.py
git commit -m "feat(detecteur): enrichissement de l'Impedance Z (categorie + composition)"
```

---

### Task 5 : Triage et mise à jour des tests du chemin `analyser()`

Le retrait des 7 passifs change le comportement d'`analyser()` : les tests qui
attendaient un nom de circuit passif (« Filtre RC passe-bas », « Pont diviseur de
tension », « Absorbeur RC », « Condensateur de découplage », « Filtre LC »,
« Filtre RC passe-haut », « Protection par fusible ») via `analyser()` /
`match_patterns()` vont échouer. Il faut les mettre à jour.

**Files:**
- Modify: les tests qui cassent (à identifier en lançant la suite). Candidats probables :
  `tests/test_integration.py`, `tests/test_confidence.py`, `tests/test_reporter.py`,
  `tests/test_matcher.py`, `tests/test_gui_sync.py`, `tests/test_satellites.py`.
- **Ne PAS toucher** : `tests/test_reduction.py`, `tests/test_reduction_integration.py`
  (ils testent l'ancien `reduire_dipoles`, toujours présent — laissés à 2c), ni les
  tests qui appellent les fonctions `detecter_filtre_*` / `detecter_pont_diviseur`
  DIRECTEMENT (les fonctions existent encore).

- [ ] **Step 1 : Lancer la suite complète et lister les échecs**

Run: `python -m pytest -q`
Expected: plusieurs FAIL. Noter chaque test et l'assertion en cause.

- [ ] **Step 2 : Pour chaque test cassé sur le chemin `analyser()`, appliquer la règle de mise à jour**

Règle (à appliquer test par test, en lisant l'intention de chaque test) :
- Si le test vérifiait qu'un montage **passif isolé** est nommé (`assert 'Filtre RC passe-bas' in types`) → remplacer par l'attente du nouveau comportement : `assert 'Impédance Z' in types` et, le cas échéant, vérifier `sorted(components)` sur les vraies refs.
- Si le test comptait le nombre total de circuits détectés sur un schéma contenant des passifs → recalculer le compte attendu (chaque réseau passif réduit = 1 « Impédance Z »).
- Si le test vérifiait un **rôle satellite** passif (pull-up/découplage) désormais émis comme « Impédance Z » → ajuster l'attente (le composant apparaît maintenant comme Impédance Z, pas comme satellite). Voir décision §2.
- Si le test vérifie un **montage actif** (AOP/transistor/diode) → il doit continuer à passer ; s'il échoue, c'est un vrai bug de régression à corriger dans le code, pas dans le test.

Pour chaque test modifié, montrer le diff exact (avant/après) dans le message de commit.

- [ ] **Step 3 : Relancer jusqu'au vert**

Run: `python -m pytest -q`
Expected: PASS (hors `test_reduction*.py` qui doivent rester verts sans modification).

- [ ] **Step 4 : Commit**

```bash
git add tests/
git commit -m "test: adapter les tests du chemin analyser() au modele Impedance Z"
```

> Si un test révèle une régression réelle sur un **montage actif** (ex. un inverseur
> avec feedback composite n'est plus détecté), NE PAS contourner par le test :
> rapporter en DONE_WITH_CONCERNS ou BLOCKED — c'est un défaut de conception à
> traiter (potentiellement le cas mixte renvoyé à 2b).

---

### Task 6 : Vérification de bout en bout

**Files:** (aucune modif — vérification)

- [ ] **Step 1 : Suite complète verte**

Run: `python -m pytest -q`
Expected: PASS (tout vert).

- [ ] **Step 2 : Fumée sur un schéma réel**

Run:
```bash
python -c "from circuit_analyzer.composant import Composant, construire_graphe; from circuit_analyzer.detecteur import analyser; g=construire_graphe([Composant('R1','R',{'1':'IN','2':'M'},'10k'),Composant('C1','C',{'1':'M','2':'GND'},'100n')]); print([(m['circuit_type'], m['components']) for m in analyser(g)])"
```
Expected: une seule entrée `('Impédance Z', ['R1', 'C1'])` (ordre des refs indifférent).

- [ ] **Step 3 : Vérifier qu'il ne reste aucun « non classifié » passif**

Run:
```bash
python -c "from circuit_analyzer.composant import Composant, construire_graphe; from circuit_analyzer.detecteur import analyser; g=construire_graphe([Composant('R1','R',{'1':'A','2':'B'},'1k'),Composant('R2','R',{'1':'C','2':'D'},'1k')]); res=analyser(g); used={c for m in res for c in m['components']}; print('non classifies:', {'R1','R2'}-used)"
```
Expected: `non classifies: set()` — chaque R isolée est une Impédance Z.

- [ ] **Step 4 : Commit éventuel**

```bash
git add -A
git commit -m "chore: verification bout en bout branchement moteur Z (2a)"
```

---

## Notes pour 2b / 2c

- **2b** : généraliser les détecteurs actifs aux Z **mixtes** (type `Z`). Décider, pour
  l'inverseur/l'intégrateur/le dérivateur, comment classer un feedback ou une entrée
  de type `Z` (proposition : `Z` traité comme « résistif » par défaut, `C` pur =
  capacitif). Ajouter `_impedances_sur(graphe, noeud)` si besoin.
- **2c** : supprimer `detecter_filtre_rc_passe_bas/haut`, `detecter_filtre_lc`,
  `detecter_pont_diviseur`, `detecter_absorbeur_rc`, `detecter_condensateur_decouplage`,
  `detecter_fusible` ; supprimer `circuit_analyzer/reduction.py` et `tests/test_reduction*.py` ;
  retirer les classes correspondantes de `patterns/basic_circuits.py`, les drawers de
  `gui/circuit_viewer.py`, la règle DRC « Pont diviseur déséquilibré » de `drc.py`, et
  les entrées de `gui/descriptions.py`.
