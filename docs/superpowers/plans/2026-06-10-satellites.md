# Rattachement des composants satellites — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rattacher les composants non classifiés (pull-up, découplage, roue libre, R série…) aux circuits détectés, avec un score de rattachement (sûr / possible), sans modifier les 27 détecteurs.

**Architecture:** Nouveau module `circuit_analyzer/satellites.py` appelé en fin de `detecteur.analyser()`. Phase 1 : absorption des circuits annexes mono-composant (roue libre / découplage / ESD) adjacents à un circuit multi-composants. Phase 2 : classification des leftovers par rôle topologique avec score. Rendu dans `rapport.py` et regroupement dans `xml.py`.

**Tech Stack:** Python 3.10+, NetworkX (MultiGraph), pytest. Réutilise `value_parser.py` et `patterns/base.py`.

**Spec:** `docs/superpowers/specs/2026-06-10-satellites-design.md`

## Corrections imposées (revue utilisateur — PRIORITAIRES sur les blocs de code ci-dessous)

1. **Encodage cp1252** : aucune nouvelle chaîne (reasons, lignes rapport, warnings) ne
   contient `≈ ⚠ → ≥ ─`. Formes ASCII : `~`, `ATTENTION`, `->`, `>=`, `-`. Les accents
   français (é, è, û, ç) sont cp1252-compatibles et autorisés. Le préfixe `⚠` existant
   de rapport.py pour les warnings n'est pas modifié (déjà en production).
2. **Non classifiés** : seuls les satellites **sûrs** sortent de « Composants non
   classifiés ». Les possibles apparaissent dans une nouvelle section
   « À vérifier (rattachement possible) » avec leur circuit hôte et la raison.
3. **Absorption découplage par rails seulement** : jamais « sure ».
   - hôte partageant un nœud signal → absorbé, status `sure` (score = confidence) ;
   - exactement un hôte candidat par rails → absorbé, status `possible`, score plafonné à 0.55 ;
   - zéro ou plusieurs hôtes par rails → PAS d'absorption (l'annexe reste un circuit).
4. **Construction du graphe dans les tests** : `build_graph` partout (même import que
   les tests existants). Ne pas mélanger avec `construire_graphe`.
5. **series-r** : score 0.55 par défaut (→ possible) ; 0.7 uniquement si la valeur
   parsée est cohérente avec une résistance série (1 Ω <= v <= 1 kΩ).
6. **Champ `status`** : chaque satellite porte `'status': 'sure' | 'possible'`, calculé
   une seule fois dans `rattacher_satellites` / `_absorber_annexes`
   (`sure` si score >= SEUIL_SUR). `rapport.py` et `xml.py` lisent `status`,
   jamais SEUIL_SUR.
7. **Warning par satellite possible** : ajouter à `match['warnings']` :
   `f"{ref} : rattachement possible uniquement, validation ingénieur nécessaire"`.
8. **XML** : seuls les satellites `status == 'sure'` rejoignent le bloc du circuit ;
   test explicite que les possibles restent dans Divers.

**Contexte codebase indispensable :**
- Le graphe : nœuds = nets électriques, arêtes = composants 2 broches. `graphe.graph['components']` contient TOUS les composants (`{ref: Composant}`), chaque `Composant` a `.ref`, `.type`, `.value`, `.pins` (dict nom_broche → net). Voir `circuit_analyzer/composant.py:187-207`.
- `analyser()` est dans `circuit_analyzer/detecteur.py:1411` ; la boucle remplit `circuits_trouves` (matches enrichis avec `confidence`, etc.) et `composants_utilises` (set de refs verrouillées).
- Un match = `{'circuit_type', 'components', 'nodes', 'confidence', 'confidence_level', 'reasons', 'warnings', 'functional_category', 'locked_components'}`.
- Tests : `Component(ref, type, pins_dict, value=...)` depuis `circuit_analyzer.parser`, `build_graph` depuis `circuit_analyzer.graph_builder`, `match_patterns` depuis `circuit_analyzer.matcher` (alias de `analyser`).
- Commande de test : `python -m pytest tests/test_satellites.py -v` (Windows, exécuter depuis la racine du repo).
- **Jamais** de `Co-Authored-By: Claude` dans les commits.
- Pas de caractère `≈` ni d'autres caractères hors cp1252 dans les chaînes destinées au rapport (console Windows). Les accents français (é, û, —, ⚠) sont OK (déjà utilisés).

---

### Task 1: Squelette de `satellites.py` — helpers de topologie

**Files:**
- Create: `circuit_analyzer/satellites.py`
- Create: `tests/test_satellites.py`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
"""
test_satellites.py — Tests du rattachement des composants satellites.
"""
import pytest
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.satellites import (
    SEUIL_SUR, SEUIL_POSSIBLE,
    _est_rail, _noeuds_internes, _rails_alim,
)


# =============================================================================
# Helpers de topologie
# =============================================================================

def test_est_rail():
    assert _est_rail('GND')
    assert _est_rail('VCC')
    assert _est_rail('PE')
    assert not _est_rail('NET_BASE')
    assert not _est_rail('')
    assert not _est_rail(None)

def test_noeuds_internes_exclut_les_rails():
    match = {'nodes': ['NET_IN', 'NET_MID', 'GND', 'VCC', '', None]}
    assert _noeuds_internes(match) == {'NET_IN', 'NET_MID'}

def test_rails_alim():
    match = {'nodes': ['NET_IN', 'GND', 'VCC', '+5V']}
    assert _rails_alim(match) == {'VCC', '+5V'}

def test_seuils():
    assert SEUIL_POSSIBLE < SEUIL_SUR
    assert SEUIL_SUR == 0.6
    assert SEUIL_POSSIBLE == 0.3
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'circuit_analyzer.satellites'`

- [ ] **Step 3: Implémenter le squelette**

```python
"""
satellites.py — Rattachement des composants satellites aux circuits détectés.

Après la détection des 27 patterns, deux phases :
  Phase 1 : les circuits annexes mono-composant (roue libre, découplage, ESD)
            adjacents à un circuit multi-composants sont absorbés comme satellites.
  Phase 2 : les composants restés non classifiés sont examinés ; ceux qui touchent
            un circuit détecté reçoivent un rôle et un score de rattachement.

Score ≥ SEUIL_SUR      → « satellite sûr »     (verrouillé, exporté dans le bloc XML)
SEUIL_POSSIBLE ≤ score < SEUIL_SUR → « satellite possible » (affiché avec ?, non verrouillé)

Format d'un satellite :
    {'ref': 'R2', 'role': 'pull-down', 'score': 0.9,
     'reason': 'R 10k entre NET_BASE et GND'}
"""
from circuit_analyzer.patterns.base import (
    is_ground_net, is_power_net, is_protective_earth_net,
)
from circuit_analyzer.value_parser import (
    classifier_resistance, classifier_condensateur,
)

SEUIL_SUR      = 0.6
SEUIL_POSSIBLE = 0.3


def _est_rail(net) -> bool:
    """Vrai si le net est une masse, une alimentation ou une terre de protection."""
    if not net:
        return False
    return is_ground_net(net) or is_power_net(net) or is_protective_earth_net(net)


def _noeuds_internes(match: dict) -> set:
    """Nœuds du circuit qui ne sont ni GND, ni alim, ni PE (= nœuds signal)."""
    return {n for n in match.get('nodes', []) if n and not _est_rail(n)}


def _rails_alim(match: dict) -> set:
    """Rails d'alimentation effectivement présents dans les nœuds du circuit."""
    return {n for n in match.get('nodes', []) if n and is_power_net(n)}
```

- [ ] **Step 4: Vérifier le passage**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/satellites.py tests/test_satellites.py
git commit -m "feat: satellites module skeleton with topology helpers"
```

---

### Task 2: Évaluation des rôles — résistances (pull-up / pull-down / série)

**Files:**
- Modify: `circuit_analyzer/satellites.py`
- Modify: `tests/test_satellites.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `tests/test_satellites.py` (import `_evaluer` en haut du fichier dans le bloc d'import existant de `circuit_analyzer.satellites`) :

```python
from circuit_analyzer.satellites import _evaluer


class _Comp:
    """Composant minimal pour tester _evaluer sans construire un graphe."""
    def __init__(self, ref, type_, pins, value=''):
        self.ref, self.type, self.pins, self.value = ref, type_, pins, value


# =============================================================================
# _evaluer — résistances
# =============================================================================

def test_pull_down_avec_valeur():
    r = _Comp('R2', 'R', {'1': 'NET_BASE', '2': 'GND'}, '10k')
    role, score, reason = _evaluer(r, internes={'NET_BASE'}, rails=set())
    assert role == 'pull-down'
    assert score == 0.9
    assert 'NET_BASE' in reason and 'GND' in reason

def test_pull_up_avec_valeur():
    r = _Comp('R3', 'R', {'1': 'VCC', '2': 'NET_BASE'}, '47k')
    role, score, reason = _evaluer(r, internes={'NET_BASE'}, rails=set())
    assert role == 'pull-up'
    assert score == 0.9

def test_pull_sans_valeur_score_reduit():
    r = _Comp('R2', 'R', {'1': 'NET_BASE', '2': 'GND'})
    role, score, reason = _evaluer(r, internes={'NET_BASE'}, rails=set())
    assert role == 'pull-down'
    assert score == 0.7

def test_r_faible_vers_rail_role_incertain():
    # 100 ohms vers GND : trop faible pour un pull → voisin inconnu
    r = _Comp('R5', 'R', {'1': 'NET_BASE', '2': 'GND'}, '100')
    role, score, reason = _evaluer(r, internes={'NET_BASE'}, rails=set())
    assert role == 'unknown-neighbor'
    assert score == 0.4

def test_r_serie_vers_noeud_signal():
    r = _Comp('R4', 'R', {'1': 'NET_IN', '2': 'NET_EXT'}, '100')
    role, score, reason = _evaluer(r, internes={'NET_IN'}, rails=set())
    assert role == 'series-r'
    assert score == 0.7

def test_r_sans_contact_retourne_none():
    r = _Comp('R9', 'R', {'1': 'NET_X', '2': 'NET_Y'}, '10k')
    assert _evaluer(r, internes={'NET_BASE'}, rails=set()) is None

def test_r_uniquement_via_rail_retourne_none():
    # R entre VCC et GND : ne touche le circuit par aucun nœud interne → pas un voisin
    r = _Comp('R9', 'R', {'1': 'VCC', '2': 'GND'}, '10k')
    assert _evaluer(r, internes={'NET_BASE'}, rails=set()) is None
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: FAIL — `ImportError: cannot import name '_evaluer'`

- [ ] **Step 3: Implémenter `_evaluer` (résistances + voisin inconnu)**

Ajouter à `circuit_analyzer/satellites.py` :

```python
def _evaluer(comp, internes: set, rails: set):
    """
    Évalue le rôle d'un composant candidat vis-à-vis d'un circuit.

    Arguments :
        comp     : Composant (.type, .pins, .value)
        internes : nœuds signal du circuit
        rails    : rails d'alimentation du circuit

    Retourne (role, score, reason) ou None si le composant ne touche pas le circuit.
    """
    nets = [n for n in comp.pins.values() if n]
    touche_interne = [n for n in nets if n in internes]

    # ── Découplage / bulk : C entre un rail d'alim du circuit et GND ─────────
    # Seul rôle qui ne passe pas par un nœud interne : un découplage vit
    # par définition entre rails, mais doit toucher le rail utilisé par le circuit.
    if comp.type == 'C' and len(nets) == 2:
        rail = next((n for n in nets if n in rails), None)
        if rail:
            autre = nets[1] if nets[0] == rail else nets[0]
            if is_ground_net(autre):
                classe = classifier_condensateur(comp.value, entre_power_gnd=True)
                if classe == 'decoupling':
                    return ('decoupling', 0.9, f"C {comp.value} entre {rail} et {autre}")
                if classe == 'bulk_filter':
                    return ('bulk', 0.8, f"C {comp.value} entre {rail} et {autre}")
                return ('decoupling', 0.7, f"C entre {rail} et {autre} (valeur inconnue)")

    if not touche_interne:
        return None
    noeud = touche_interne[0]

    # ── Résistances : pull-up / pull-down / série ─────────────────────────────
    if comp.type == 'R' and len(nets) == 2:
        autre = nets[1] if nets[0] == noeud else nets[0]
        if is_ground_net(autre) or is_power_net(autre):
            role = 'pull-down' if is_ground_net(autre) else 'pull-up'
            classe = classifier_resistance(comp.value)
            if classe == 'pull':
                return (role, 0.9, f"R {comp.value} entre {noeud} et {autre}")
            if classe == 'unknown':
                return (role, 0.7, f"R entre {noeud} et {autre} (valeur inconnue)")
            return ('unknown-neighbor', 0.4,
                    f"R {comp.value} entre {noeud} et {autre} (trop faible pour un pull)")
        if not _est_rail(autre):
            return ('series-r', 0.7, f"R en série sur {noeud} (vers {autre})")

    # ── Diode de roue libre : anode sur nœud interne, cathode sur rail ───────
    if comp.type == 'D':
        anode, cathode = comp.pins.get('A'), comp.pins.get('K')
        if anode in internes and cathode and is_power_net(cathode):
            return ('flyback', 0.85, f"D anode sur {anode}, cathode sur {cathode}")

    # ── Voisin direct sans rôle identifié ─────────────────────────────────────
    return ('unknown-neighbor', 0.4, f"adjacent à {noeud}, rôle non identifié")
```

- [ ] **Step 4: Vérifier le passage**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/satellites.py tests/test_satellites.py
git commit -m "feat: satellite role evaluation for resistors"
```

---

### Task 3: Évaluation des rôles — condensateurs, diodes, voisin inconnu

**Files:**
- Modify: `tests/test_satellites.py`

Le code de `_evaluer` (Task 2) couvre déjà C/D/inconnu — cette task ajoute les tests qui verrouillent ce comportement.

- [ ] **Step 1: Écrire les tests**

```python
# =============================================================================
# _evaluer — condensateurs, diodes, voisin inconnu
# =============================================================================

def test_decoupling_avec_valeur():
    c = _Comp('C3', 'C', {'1': 'VCC', '2': 'GND'}, '100nF')
    role, score, reason = _evaluer(c, internes={'NET_X'}, rails={'VCC'})
    assert role == 'decoupling'
    assert score == 0.9

def test_bulk_grosse_valeur():
    c = _Comp('C4', 'C', {'1': 'VCC', '2': 'GND'}, '47uF')
    role, score, reason = _evaluer(c, internes=set(), rails={'VCC'})
    assert role == 'bulk'
    assert score == 0.8

def test_decoupling_sans_valeur_score_reduit():
    c = _Comp('C3', 'C', {'1': 'VCC', '2': 'GND'})
    role, score, reason = _evaluer(c, internes=set(), rails={'VCC'})
    assert role == 'decoupling'
    assert score == 0.7

def test_c_sur_rail_non_utilise_par_le_circuit():
    # Le circuit n'utilise pas VBAT → ce C n'est pas son découplage
    c = _Comp('C5', 'C', {'1': 'VBAT', '2': 'GND'}, '100nF')
    assert _evaluer(c, internes={'NET_X'}, rails={'VCC'}) is None

def test_flyback():
    d = _Comp('D1', 'D', {'A': 'NET_SW', 'K': 'VCC'})
    role, score, reason = _evaluer(d, internes={'NET_SW'}, rails={'VCC'})
    assert role == 'flyback'
    assert score == 0.85

def test_diode_sens_inverse_pas_flyback():
    # Anode sur rail, cathode sur nœud interne : pas une roue libre
    d = _Comp('D2', 'D', {'A': 'VCC', 'K': 'NET_SW'})
    role, score, reason = _evaluer(d, internes={'NET_SW'}, rails={'VCC'})
    assert role == 'unknown-neighbor'
    assert score == 0.4

def test_voisin_inconnu():
    c = _Comp('C9', 'C', {'1': 'NET_COLL', '2': 'NET_X'}, '10nF')
    role, score, reason = _evaluer(c, internes={'NET_COLL'}, rails=set())
    assert role == 'unknown-neighbor'
    assert score == 0.4
    assert 'NET_COLL' in reason
```

- [ ] **Step 2: Lancer les tests**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: 18 passed (si un test échoue, corriger `_evaluer` — ne pas modifier le test)

- [ ] **Step 3: Commit**

```bash
git add tests/test_satellites.py
git commit -m "test: satellite role evaluation for capacitors and diodes"
```

---

### Task 4: `rattacher_satellites` — leftovers, conflits, verrouillage

**Files:**
- Modify: `circuit_analyzer/satellites.py`
- Modify: `tests/test_satellites.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter l'import `rattacher_satellites` au bloc d'import de `circuit_analyzer.satellites`, puis :

```python
from circuit_analyzer.composant import construire_graphe


def _graphe(comps):
    return construire_graphe(comps)


def _match(circuit_type, components, nodes, confidence=0.8):
    return {'circuit_type': circuit_type, 'components': list(components),
            'nodes': list(nodes), 'confidence': confidence}


# =============================================================================
# rattacher_satellites — phase leftovers
# =============================================================================

def test_leftover_rattache_comme_sur():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R2', 'R', {'1': 'NET_BASE', '2': 'GND'}, '10k'),
    ]
    g = _graphe(comps)
    circuits = [_match('Transistor en commutation', ['Q1'],
                       ['NET_BASE', 'NET_COLL', 'GND'], confidence=0.85)]
    utilises = {'Q1'}
    rattacher_satellites(circuits, g, utilises)
    sats = circuits[0]['satellites']
    assert len(sats) == 1
    assert sats[0]['ref'] == 'R2'
    assert sats[0]['role'] == 'pull-down'
    assert sats[0]['score'] >= SEUIL_SUR
    # Un satellite sûr est verrouillé
    assert 'R2' in utilises

def test_satellite_possible_non_verrouille():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('C9', 'C', {'1': 'NET_COLL', '2': 'NET_X'}, '10nF'),
    ]
    g = _graphe(comps)
    circuits = [_match('Transistor en commutation', ['Q1'],
                       ['NET_BASE', 'NET_COLL', 'GND'])]
    utilises = {'Q1'}
    rattacher_satellites(circuits, g, utilises)
    sats = circuits[0]['satellites']
    assert len(sats) == 1
    assert sats[0]['role'] == 'unknown-neighbor'
    assert sats[0]['score'] < SEUIL_SUR
    assert 'C9' not in utilises

def test_composant_deja_classifie_jamais_reexamine():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R2', 'R', {'1': 'NET_BASE', '2': 'GND'}, '10k'),
    ]
    g = _graphe(comps)
    circuits = [_match('Transistor en commutation', ['Q1'],
                       ['NET_BASE', 'NET_COLL', 'GND'])]
    utilises = {'Q1', 'R2'}          # R2 appartient déjà à un circuit
    rattacher_satellites(circuits, g, utilises)
    assert circuits[0]['satellites'] == []

def test_composant_isole_non_rattache():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R8', 'R', {'1': 'NET_LOIN', '2': 'NET_AILLEURS'}, '1k'),
    ]
    g = _graphe(comps)
    circuits = [_match('Transistor en commutation', ['Q1'],
                       ['NET_BASE', 'NET_COLL', 'GND'])]
    utilises = {'Q1'}
    rattacher_satellites(circuits, g, utilises)
    assert circuits[0]['satellites'] == []

def test_satellites_toujours_present_meme_vide():
    g = _graphe([Component('Q1', 'Q', {'B': 'A', 'C': 'B', 'E': 'GND'})])
    circuits = [_match('Transistor en commutation', ['Q1'], ['A', 'B', 'GND'])]
    rattacher_satellites(circuits, g, {'Q1'})
    assert 'satellites' in circuits[0]

def test_conflit_egalite_va_a_la_meilleure_confiance():
    # R2 pull-down touche NET_A (circuit 1) ET NET_A est aussi interne au circuit 2
    comps = [
        Component('R2', 'R', {'1': 'NET_A', '2': 'GND'}, '10k'),
    ]
    g = _graphe(comps)
    c1 = _match('Circuit faible', ['Q1'], ['NET_A', 'GND'], confidence=0.7)
    c2 = _match('Circuit fort',   ['Q2'], ['NET_A', 'GND'], confidence=0.95)
    utilises = {'Q1', 'Q2'}
    rattacher_satellites([c1, c2], g, utilises)
    assert c1['satellites'] == []
    assert len(c2['satellites']) == 1 and c2['satellites'][0]['ref'] == 'R2'

def test_conflit_meilleur_score_gagne(monkeypatch):
    import circuit_analyzer.satellites as sat
    def faux_evaluer(comp, internes, rails):
        if 'N_FAIBLE' in internes:
            return ('role-faible', 0.5, 'x')
        return ('role-fort', 0.9, 'y')
    monkeypatch.setattr(sat, '_evaluer', faux_evaluer)
    comps = [Component('R2', 'R', {'1': 'N_FAIBLE', '2': 'N_FORT'}, '1k')]
    g = _graphe(comps)
    c1 = _match('A', ['Q1'], ['N_FAIBLE'], confidence=0.99)
    c2 = _match('B', ['Q2'], ['N_FORT'],   confidence=0.70)
    rattacher_satellites([c1, c2], g, {'Q1', 'Q2'})
    assert c1['satellites'] == []
    assert c2['satellites'][0]['role'] == 'role-fort'
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: FAIL — `ImportError: cannot import name 'rattacher_satellites'`

- [ ] **Step 3: Implémenter `rattacher_satellites` (sans la phase absorption pour l'instant)**

Ajouter à `circuit_analyzer/satellites.py` :

```python
def rattacher_satellites(circuits: list, graphe, composants_utilises: set) -> None:
    """
    Rattache les composants non classifiés aux circuits détectés.

    Mute les matches en place : chaque match reçoit une clé 'satellites'
    (liste, toujours présente). Les satellites sûrs (score >= SEUIL_SUR)
    sont ajoutés à composants_utilises ; les « possibles » restent libres.

    Conflit (un candidat éligible pour plusieurs circuits) : rattaché au
    meilleur score de rôle ; à égalité, au circuit avec la meilleure confidence.
    """
    for m in circuits:
        m.setdefault('satellites', [])

    infos = [(m, _noeuds_internes(m), _rails_alim(m)) for m in circuits]
    tous = graphe.graph.get('components', {})

    for ref, comp in tous.items():
        if ref in composants_utilises:
            continue
        meilleur = None   # (cle_de_tri, match, role, score, reason)
        for m, internes, rails in infos:
            resultat = _evaluer(comp, internes, rails)
            if resultat is None:
                continue
            role, score, reason = resultat
            cle = (score, m.get('confidence', 0))
            if meilleur is None or cle > meilleur[0]:
                meilleur = (cle, m, role, score, reason)
        if meilleur is None:
            continue
        _, m, role, score, reason = meilleur
        if score < SEUIL_POSSIBLE:
            continue
        m['satellites'].append(
            {'ref': ref, 'role': role, 'score': score, 'reason': reason}
        )
        if score >= SEUIL_SUR:
            composants_utilises.add(ref)
```

**Attention au monkeypatch :** la boucle doit appeler `_evaluer` via le module
(résolution au moment de l'appel). En Python, `_evaluer(...)` écrit au niveau module
se résout dans le namespace global du module à l'exécution — le monkeypatch
`setattr(sat, '_evaluer', ...)` fonctionne donc tel quel. Ne PAS faire
`from ... import _evaluer` dans une closure locale.

- [ ] **Step 4: Vérifier le passage**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: 25 passed

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/satellites.py tests/test_satellites.py
git commit -m "feat: attach leftover components as satellites with conflict resolution"
```

---

### Task 5: Phase d'absorption des circuits annexes mono-composant

**Files:**
- Modify: `circuit_analyzer/satellites.py`
- Modify: `tests/test_satellites.py`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# =============================================================================
# Absorption des circuits annexes mono-composant
# =============================================================================

def test_roue_libre_absorbee_par_circuit_multi():
    circuits = [
        _match('Commande de relais', ['Q1', 'K1'],
               ['NET_BASE', 'NET_COLL', 'GND', 'VCC'], confidence=0.9),
        _match('Diode de roue libre', ['D1'],
               ['NET_COLL', 'VCC'], confidence=0.75),
    ]
    g = _graphe([])
    rattacher_satellites(circuits, g, {'Q1', 'K1', 'D1'})
    assert len(circuits) == 1
    assert circuits[0]['circuit_type'] == 'Commande de relais'
    sats = circuits[0]['satellites']
    assert len(sats) == 1
    assert sats[0]['ref'] == 'D1'
    assert sats[0]['role'] == 'flyback'
    assert sats[0]['score'] == 0.75
    assert sats[0]['reason'] == 'Diode de roue libre'

def test_decouplage_absorbe_via_rail_partage():
    circuits = [
        _match('Amplificateur inverseur (AOP)', ['U1', 'R1', 'R2'],
               ['NET_IN', 'NET_INM', 'NET_OUT', 'VCC', 'GND'], confidence=0.9),
        _match('Condensateur de découplage', ['C3'],
               ['VCC', 'GND'], confidence=0.85),
    ]
    g = _graphe([])
    rattacher_satellites(circuits, g, {'U1', 'R1', 'R2', 'C3'})
    assert len(circuits) == 1
    assert circuits[0]['satellites'][0]['role'] == 'decoupling'

def test_annexe_sans_circuit_hote_reste_un_circuit():
    # Une roue libre seule (aucun circuit multi-composants) reste un circuit
    circuits = [
        _match('Diode de roue libre', ['D1'], ['NET_SW', 'VCC'], confidence=0.75),
    ]
    g = _graphe([])
    rattacher_satellites(circuits, g, {'D1'})
    assert len(circuits) == 1
    assert circuits[0]['circuit_type'] == 'Diode de roue libre'

def test_annexe_non_adjacente_reste_un_circuit():
    circuits = [
        _match('Commande de relais', ['Q1', 'K1'],
               ['NET_BASE', 'NET_COLL', 'GND'], confidence=0.9),
        _match('Diode de roue libre', ['D9'],
               ['NET_LOIN', 'VBAT'], confidence=0.75),
    ]
    g = _graphe([])
    rattacher_satellites(circuits, g, {'Q1', 'K1', 'D9'})
    assert len(circuits) == 2

def test_absorption_prefere_noeud_signal_au_rail():
    # D1 partage NET_COLL (signal) avec c1 et seulement VCC (rail) avec c2
    c1 = _match('Commande de relais', ['Q1', 'K1'],
                ['NET_BASE', 'NET_COLL', 'VCC', 'GND'], confidence=0.7)
    c2 = _match('Amplificateur inverseur (AOP)', ['U1', 'R1'],
                ['NET_X', 'NET_Y', 'VCC', 'GND'], confidence=0.99)
    annexe = _match('Diode de roue libre', ['D1'], ['NET_COLL', 'VCC'],
                    confidence=0.75)
    circuits = [c1, c2, annexe]
    g = _graphe([])
    rattacher_satellites(circuits, g, {'Q1', 'K1', 'U1', 'R1', 'D1'})
    assert len(c1['satellites']) == 1      # malgré la confiance plus faible
    assert c2['satellites'] == []
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: les 5 nouveaux tests FAIL (les annexes ne sont pas absorbées)

- [ ] **Step 3: Implémenter l'absorption**

Dans `circuit_analyzer/satellites.py`, ajouter après les helpers :

```python
# Circuits annexes mono-composant absorbables par un circuit multi-composants.
_ANNEXES: dict[str, str] = {
    'Diode de roue libre':        'flyback',
    'Condensateur de découplage': 'decoupling',
    'Diode de protection ESD':    'esd',
}


def _absorber_annexes(circuits: list) -> None:
    """
    Les circuits annexes mono-composant (roue libre, découplage, ESD) adjacents
    à un circuit multi-composants sont retirés de la liste et convertis en
    satellite de celui-ci (score = leur confidence, reason = leur type).

    Priorité : partage d'un nœud signal > partage d'un rail d'alim ;
    à égalité, le circuit hôte avec la meilleure confidence.
    """
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
        meilleur = None   # (cle_de_tri, hote)
        for hote in hotes:
            if noeuds_annexe & _noeuds_internes(hote):
                cle = (1, hote.get('confidence', 0))
            elif noeuds_annexe & _rails_alim(hote):
                cle = (0, hote.get('confidence', 0))
            else:
                continue
            if meilleur is None or cle > meilleur[0]:
                meilleur = (cle, hote)
        if meilleur is None:
            continue
        meilleur[1]['satellites'].append({
            'ref':    annexe['components'][0],
            'role':   role,
            'score':  annexe.get('confidence', SEUIL_SUR),
            'reason': annexe['circuit_type'],
        })
        a_retirer.append(annexe)

    for annexe in a_retirer:
        circuits.remove(annexe)
```

Puis modifier le début de `rattacher_satellites` pour appeler l'absorption :

```python
    for m in circuits:
        m.setdefault('satellites', [])

    _absorber_annexes(circuits)

    infos = [(m, _noeuds_internes(m), _rails_alim(m)) for m in circuits]
```

- [ ] **Step 4: Vérifier le passage**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: 30 passed

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/satellites.py tests/test_satellites.py
git commit -m "feat: absorb single-component annex circuits as satellites"
```

---

### Task 6: Intégration dans `analyser()`

**Files:**
- Modify: `circuit_analyzer/detecteur.py:1411-1460` (fonction `analyser`)
- Modify: `tests/test_satellites.py`

- [ ] **Step 1: Écrire les tests bout-en-bout qui échouent**

```python
# =============================================================================
# Intégration bout-en-bout via analyser()
# =============================================================================

def test_e2e_pull_down_devient_satellite():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_BASE'}, '1k'),
        Component('R2', 'R', {'1': 'NET_BASE', '2': 'GND'}, '10k'),
    ]
    results = match_patterns(build_graph(comps))
    commut = [m for m in results if m['circuit_type'] == 'Transistor en commutation']
    assert len(commut) == 1
    sats = commut[0]['satellites']
    assert any(s['ref'] == 'R2' and s['role'] == 'pull-down' for s in sats)

def test_e2e_tous_les_matches_ont_la_cle_satellites():
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    assert results
    for m in results:
        assert isinstance(m['satellites'], list)

def test_e2e_roue_libre_absorbee():
    # Commande de relais + diode de roue libre sur le nœud de commutation
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_SW', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_BASE'}, '1k'),
        Component('K1', 'K', {'A1': 'NET_SW', 'A2': 'VCC', 'C': 'NET_C', 'NC': 'NET_NC'}),
        Component('D1', 'D', {'A': 'NET_SW', 'K': 'VCC'}),
    ]
    results = match_patterns(build_graph(comps))
    types = [m['circuit_type'] for m in results]
    assert 'Diode de roue libre' not in types
    hote = [m for m in results if any(s['ref'] == 'D1' for s in m['satellites'])]
    assert len(hote) == 1

def test_e2e_aucune_regression_sans_satellite():
    # Un circuit sans composant orphelin : aucun satellite, comportement inchangé
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_DIV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_DIV', '2': 'GND'}, '4.7k'),
    ]
    results = match_patterns(build_graph(comps))
    assert len(results) == 1
    assert results[0]['satellites'] == []
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: les 4 tests e2e FAIL — `KeyError: 'satellites'`

- [ ] **Step 3: Brancher dans `analyser()`**

Dans `circuit_analyzer/detecteur.py`, ajouter l'import en haut du fichier (à côté
des imports `circuit_analyzer.*` existants) :

```python
from circuit_analyzer.satellites import rattacher_satellites
```

Puis dans `analyser()`, remplacer la fin :

```python
    resultats = ResultatsAnalyse(circuits_trouves)
    resultats.supprimes = supprimes
    return resultats
```

par :

```python
    # Passe satellite : absorbe les annexes mono-composant puis rattache
    # les composants restés non classifiés aux circuits détectés.
    rattacher_satellites(circuits_trouves, graphe, composants_utilises)

    resultats = ResultatsAnalyse(circuits_trouves)
    resultats.supprimes = supprimes
    return resultats
```

- [ ] **Step 4: Vérifier le passage + non-régression complète**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: 34 passed

Run: `python -m pytest -q`
Expected: tous les tests passent. **Si un test existant échoue parce qu'il compte
les groupes et qu'une annexe est maintenant absorbée** (ex. un test d'intégration
sur `circuits_industriels/` qui attendait « Diode de roue libre » comme circuit
séparé) : vérifier que le nouveau comportement est bien celui de la spec
(annexe adjacente à un circuit multi-composants → satellite), puis mettre à jour
l'assertion du test en commentant le changement dans le message de commit.
Tout autre échec = vraie régression à corriger dans satellites.py.

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/detecteur.py tests/test_satellites.py
git commit -m "feat: run satellite attachment pass in analyser()"
```

(ajouter les tests d'intégration mis à jour au commit le cas échéant)

---

### Task 7: Rendu dans le rapport

**Files:**
- Modify: `circuit_analyzer/rapport.py:50-59` (boucle des matches) et `:41` (set `classifies`)
- Modify: `tests/test_satellites.py`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
from circuit_analyzer.rapport import generer_rapport


# =============================================================================
# Rapport
# =============================================================================

def _resultats_avec_satellite():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_BASE'}, '1k'),
        Component('R2', 'R', {'1': 'NET_BASE', '2': 'GND'}, '10k'),
        Component('C9', 'C', {'1': 'NET_COLL', '2': 'NET_X'}, '10nF'),
    ]
    refs = [c.ref for c in comps]
    return match_patterns(build_graph(comps)), refs

def test_rapport_affiche_satellites_surs():
    results, refs = _resultats_avec_satellite()
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    assert 'Satellites sûrs' in rapport
    assert 'R2' in rapport
    assert 'pull-down' in rapport

def test_rapport_affiche_satellites_possibles_avec_marqueur():
    results, refs = _resultats_avec_satellite()
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    assert 'Satellites possibles' in rapport
    assert 'C9 ?' in rapport

def test_rapport_satellites_sortent_des_non_classifies():
    results, refs = _resultats_avec_satellite()
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    if 'non classifiés' in rapport:
        section = rapport.split('non classifiés')[1]
        assert 'R2' not in section
        assert 'C9' not in section

def test_rapport_pas_de_lignes_satellites_quand_vide():
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_DIV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_DIV', '2': 'GND'}, '4.7k'),
    ]
    refs = [c.ref for c in comps]
    results = match_patterns(build_graph(comps))
    rapport = generer_rapport(results, 'test.txt', len(refs), refs)
    assert 'Satellites' not in rapport
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: les 3 premiers tests rapport FAIL (pas de lignes Satellites)

- [ ] **Step 3: Implémenter le rendu**

Dans `circuit_analyzer/rapport.py`, ajouter l'import en haut :

```python
from circuit_analyzer.satellites import SEUIL_SUR
```

Puis dans la boucle des matches, après la ligne `Nœuds` (`lignes.append(f'    Nœuds ...')`)
et avant le bloc `if reasons:` :

```python
        sats = match.get('satellites', [])
        surs = [s for s in sats if s['score'] >= SEUIL_SUR]
        poss = [s for s in sats if s['score'] < SEUIL_SUR]
        if surs:
            lignes.append('    Satellites sûrs     : ' + ' ; '.join(
                f"{s['ref']} ({s['role']} — {s['reason']})" for s in surs))
        if poss:
            lignes.append('    Satellites possibles: ' + ' ; '.join(
                f"{s['ref']} ? ({s['reason']})" for s in poss))
```

Et après `classifies.update(match['components'])` ajouter :

```python
        classifies.update(s['ref'] for s in sats)
```

- [ ] **Step 4: Vérifier le passage**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: 38 passed

Run: `python -m pytest tests/ -q -k "report or rapport"`
Expected: tous les tests de rapport existants passent (le format historique
`=== ANALYSE DU CIRCUIT ===` et `Groupes identifiés : N` est inchangé)

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/rapport.py tests/test_satellites.py
git commit -m "feat: show sure/possible satellites in report"
```

---

### Task 8: Export XML — satellites sûrs dans le bloc du circuit

**Files:**
- Modify: `circuit_analyzer/xml.py:342-359` (`_grouper_par_circuit`)
- Modify: `tests/test_satellites.py`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
from circuit_analyzer.xml import generer_xml


# =============================================================================
# Export XML
# =============================================================================

def test_xml_satellite_sur_dans_le_bloc_du_circuit():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_BASE'}, '1k'),
        Component('R2', 'R', {'1': 'NET_BASE', '2': 'GND'}, '10k'),
    ]
    results = match_patterns(build_graph(comps))
    xml_str = generer_xml(comps, results)
    # R2 (satellite sûr) est exporté — et il n'y a pas de bloc Divers pour lui
    assert 'R2' in xml_str

def test_xml_satellite_possible_reste_en_divers():
    from circuit_analyzer.xml import _grouper_par_circuit
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_BASE'}, '1k'),
        Component('C9', 'C', {'1': 'NET_COLL', '2': 'NET_X'}, '10nF'),
    ]
    results = match_patterns(build_graph(comps))
    blocs = _grouper_par_circuit(comps, results)
    divers = [b for b in blocs if b.label == 'Divers']
    assert divers and any(c.ref == 'C9' for c in divers[0].comps)

def test_xml_groupement_satellite_sur_quitte_divers():
    from circuit_analyzer.xml import _grouper_par_circuit
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_BASE'}, '1k'),
        Component('R2', 'R', {'1': 'NET_BASE', '2': 'GND'}, '10k'),
    ]
    results = match_patterns(build_graph(comps))
    blocs = _grouper_par_circuit(comps, results)
    bloc_commut = [b for b in blocs if 'commutation' in b.label]
    assert bloc_commut and any(c.ref == 'R2' for c in bloc_commut[0].comps)
    for b in blocs:
        if b.label == 'Divers':
            assert all(c.ref != 'R2' for c in b.comps)
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: `test_xml_groupement_satellite_sur_quitte_divers` FAIL (R2 en Divers)

- [ ] **Step 3: Implémenter le regroupement**

Dans `circuit_analyzer/xml.py`, ajouter l'import (à côté des imports
`circuit_analyzer.patterns.base` existants) :

```python
from circuit_analyzer.satellites import SEUIL_SUR
```

Puis remplacer `_grouper_par_circuit` :

```python
def _refs_du_bloc(r) -> list:
    """Refs d'un circuit + ses satellites sûrs (les « possibles » restent en Divers)."""
    refs = list(r["components"])
    refs += [s['ref'] for s in r.get('satellites', []) if s['score'] >= SEUIL_SUR]
    return refs


def _grouper_par_circuit(composants, resultats):
    """Regroupe les composants par circuit détecté. Composants non classifiés → bloc 'Divers'."""
    comp_par_ref = {c.ref: c for c in composants if _TYPE_VERS_FORME.get(c.type) is not None}
    type_du_ref: dict = {}
    for r in resultats or []:
        for ref in _refs_du_bloc(r):
            type_du_ref.setdefault(ref, r["circuit_type"])
    blocs = []
    for r in resultats or []:
        label = r["circuit_type"]
        b = _Bloc(label, [comp_par_ref[ref] for ref in _refs_du_bloc(r)
                          if ref in comp_par_ref and type_du_ref.get(ref) == label])
        if b.comps:
            blocs.append(b)
    divers = [c for ref, c in comp_par_ref.items() if ref not in type_du_ref]
    if divers:
        blocs.append(_Bloc("Divers", divers))
    return blocs
```

- [ ] **Step 4: Vérifier le passage + non-régression XML**

Run: `python -m pytest tests/test_satellites.py -v`
Expected: 41 passed

Run: `python -m pytest tests/ -q -k "xml"`
Expected: tous les tests XML existants passent

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/xml.py tests/test_satellites.py
git commit -m "feat: group sure satellites into their circuit's XML block"
```

---

### Task 9: Vérification finale sur cas réel + documentation

**Files:**
- Modify: `README.md` (section Score de confiance + Limitations connues)

- [ ] **Step 1: Suite complète**

Run: `python -m pytest -q`
Expected: ~220+ tests, 0 échec

- [ ] **Step 2: Vérification sur un circuit industriel réel**

Run:
```bash
python main.py circuits_industriels/relay_driver.xml --output rapport_satellites.txt
```
Puis lire `rapport_satellites.txt` et vérifier :
- la diode de roue libre apparaît en « Satellites sûrs » du circuit de commande
  (ou reste un circuit séparé si elle n'est pas adjacente — vérifier la topologie réelle du fichier) ;
- la section « Composants non classifiés » a diminué par rapport à avant ;
- aucune erreur d'encodage console (cp1252).
Supprimer `rapport_satellites.txt` après vérification.

- [ ] **Step 3: Mettre à jour le README**

Dans `README.md` :
- Section **Score de confiance** : ajouter un exemple de lignes satellites :

```
    Satellites sûrs     : R2 (pull-down — R 10k entre NET_BASE et GND)
    Satellites possibles: C9 ? (adjacent à NET_COLL, rôle non identifié)
```

- Section **Limitations connues** : supprimer la puce
  « **Composants autour d'un circuit de base** — une résistance de pull-up ou un
  condensateur de bypass adjacent ne sera pas automatiquement rattaché au circuit
  principal » et la remplacer par :

```
- **Satellites « possibles »** — un voisin sans rôle identifiable est signalé
  (score faible) mais jamais intégré au schéma exporté
```

- Mettre à jour le compteur de tests dans la section **Tests** (valeur réelle après Step 1).
- Dans **Structure du projet**, ajouter `├── satellites.py  ← rattachement des composants satellites`
  sous `detecteur.py`.

- [ ] **Step 4: Commit final**

```bash
git add README.md
git commit -m "docs: document satellite attachment in README"
```

---

## Critères de fin

- `python -m pytest -q` : 0 échec, ~24 nouveaux tests.
- `match['satellites']` présent sur tous les matches (liste, vide par défaut).
- Rapport : lignes « Satellites sûrs / possibles » uniquement quand non vides ;
  satellites retirés des « non classifiés ».
- XML : satellites sûrs dans le bloc du circuit, possibles en Divers.
- Annexes mono-composant (roue libre / découplage / ESD) absorbées quand adjacentes
  à un circuit multi-composants.
