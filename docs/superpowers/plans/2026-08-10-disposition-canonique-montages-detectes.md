# Disposition canonique des montages détectés — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recognized circuit groups (starting with the inverting amplifier)
get their canonical textbook layout (Zin left, AOP center, Zf feedback arc
above) when `circuit_analyzer/xml.py`'s `generer_xml` regenerates a BoardSCH
schema, instead of today's coarse family-bucket placement.

**Architecture:** Three-tier fallback inside `_positionner_composants_bloc`:
an exact-`circuit_type` registry of role-aware positioners (new, tier 1),
falling back to the existing keyword-family functions (unchanged, tier 2),
falling back to compact-grid packing (unchanged, tier 3). Role data
(`aop`/`Zin`/`Zf`) already computed by `detecteur.py` gets threaded through
`_grouper_par_circuit` instead of being discarded. Position values grow from
`(x, y)` to `(x, y, angle)`; `angle` already exists end-to-end in the XML
writer, just unused until now.

**Tech Stack:** Python, `dataclasses`, `xml.etree.ElementTree`, `pytest`,
`matplotlib` (visual verification only — already a project dependency).

## Global Constraints

- Pure Python. No C#/ERetroDesign code is touched by this plan.
- Regeneration goes through `xml_generator.components_to_xml` /
  `circuit_analyzer.xml.generer_xml` (the fabrication path). This plan does
  NOT touch `eretro_patch.ecrire_groupes` (the patch-in-place path).
- **Hard constraint:** connectivity must be identical before and after
  regeneration — verified by a dedicated end-to-end test (Task 4), not just
  asserted.
- Fail-soft: a bloc with empty/missing `roles` must fall through to
  existing behavior without raising. No existing test may start failing.
- Scope for this plan: **one pattern only** — "Amplificateur inverseur
  (AOP)". Every other pattern keeps using tier 2/3 exactly as today.

---

### Task 1: `_Bloc.roles` — carry role data instead of discarding it

**Files:**
- Modify: `circuit_analyzer/xml.py:16` (dataclass import), `circuit_analyzer/xml.py:653-657` (`_Bloc`), `circuit_analyzer/xml.py:660-668` (add `_roles_du_bloc` after `_refs_du_bloc`), `circuit_analyzer/xml.py:706-713` (`_grouper_par_circuit`'s bloc construction)
- Test: `tests/test_xml_generator.py` (near the existing `_Block`/`_layout_groups` tests, ~line 242+)

**Interfaces:**
- Produces: `_Bloc(label: str, comps: list, roles: dict[str, list[str]] = {})` — new optional field, default empty dict. `_roles_du_bloc(r: dict) -> dict[str, list[str]]` — new function, reads `r.get('impedances')` (a dict of `{role_name: {'refs': [...], ...}}`, e.g. `detecteur.py`'s `{'Zin': {...}, 'Zf': {...}}`) plus `r['components']` to find the leftover anchor ref(s) (e.g. the AOP itself, labeled `'aop'`). Returns `{}` when `r` has no `impedances` key (Divers, or a not-yet-migrated pattern).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_xml_generator.py`, right after the existing `_Block`/`_layout_groups` import block (after line ~243):

```python
def test_layout_groups_extracts_roles_from_impedances():
    """@brief Un match avec 'impedances' peuple bloc.roles (aop/Zin/Zf)."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    results = [{
        "circuit_type": "Amplificateur inverseur (AOP)",
        "components": ["U1", "R2", "R1"],
        "nodes": [],
        "impedances": {
            "Zin": {"refs": ["R1"], "composition": "R1", "nodes": ("NET_INV", "NET_IN")},
            "Zf":  {"refs": ["R2"], "composition": "R2", "nodes": ("NET_INV", "NET_OUT")},
        },
    }]
    blocks = _layout_groups(comps, results)
    assert len(blocks) == 1
    assert blocks[0].roles == {"Zin": ["R1"], "Zf": ["R2"], "aop": ["U1"]}


def test_layout_groups_roles_empty_without_impedances():
    """@brief Sans 'impedances' (montage pas migre, ou Divers), roles reste vide."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    results = [{"circuit_type": "Amplificateur inverseur (AOP)",
                "components": ["U1", "R1", "R2"], "nodes": []}]
    blocks = _layout_groups(comps, results)
    assert blocks[0].roles == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k roles -v`
Expected: FAIL — `test_layout_groups_extracts_roles_from_impedances` fails with
`AssertionError` (`blocks[0].roles` doesn't exist / `_Bloc` has no attribute
`roles`, since it's not a dataclass field yet — actual error is a
`TypeError`/`AttributeError` depending on how `_Bloc` is constructed today).

- [ ] **Step 3: Implement**

In `circuit_analyzer/xml.py`, change the import line (currently line 16):

```python
from dataclasses import dataclass
```
to:
```python
from dataclasses import dataclass, field
```

Change `_Bloc` (currently lines 653-657):

```python
@dataclass
class _Bloc:
    """@brief Bloc de mise en page : un libellé de circuit et ses composants."""
    label: str
    comps: list
```
to:
```python
@dataclass
class _Bloc:
    """@brief Bloc de mise en page : un libellé de circuit et ses composants.

    `roles` associe un nom de rôle (ex. 'aop', 'Zin', 'Zf') à la liste des
    refs qui le jouent — vide si le montage n'a pas de décomposition par
    rôle connue (Divers, ou montage pas encore migré vers un positionneur
    canonique).
    """
    label: str
    comps: list
    roles: dict = field(default_factory=dict)
```

Add a new function right after `_refs_du_bloc` (currently ends at line 668,
just before `_ordre_des_circuits`):

```python
def _roles_du_bloc(r) -> dict:
    """@brief Rôles des composants d'un match, depuis 'impedances'.

    @param r Match d'un circuit détecté (sortie de detecteur.py).
    @return dict {nom_role: [refs]} ; {} si le match n'a pas de champ
            'impedances' (Divers, ou montage pas encore migré).

    Le ou les refs de r['components'] qui n'apparaissent dans AUCUN rôle de
    'impedances' sont regroupés sous le rôle 'aop' (l'ancre du montage —
    vrai pour tous les montages AOP actuels, qui n'ont qu'un seul composant
    hors impédances).
    """
    impedances = r.get('impedances')
    if not impedances:
        return {}
    roles = {nom: list(bloc.get('refs', [])) for nom, bloc in impedances.items()}
    refs_connus = {ref for refs in roles.values() for ref in refs}
    ancre = [ref for ref in r['components'] if ref not in refs_connus]
    if ancre:
        roles['aop'] = ancre
    return roles
```

Change `_grouper_par_circuit`'s bloc construction (currently lines 706-713):

```python
    blocs = []
    for i in ordre:
        r = resultats[i]
        label = r["circuit_type"]
        b = _Bloc(label, [comp_par_ref[ref] for ref in _refs_du_bloc(r)
                          if ref in comp_par_ref and type_du_ref.get(ref) == label])
        if b.comps:
            blocs.append(b)
```
to:
```python
    blocs = []
    for i in ordre:
        r = resultats[i]
        label = r["circuit_type"]
        b = _Bloc(label, [comp_par_ref[ref] for ref in _refs_du_bloc(r)
                          if ref in comp_par_ref and type_du_ref.get(ref) == label],
                  roles=_roles_du_bloc(r))
        if b.comps:
            blocs.append(b)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k roles -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full existing suite to confirm no regressions**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -q`
Expected: all previously-passing tests still pass (29 + 2 new = 31 passed)

- [ ] **Step 6: Commit**

```bash
git add circuit_analyzer/xml.py tests/test_xml_generator.py
git commit -m "feat(disposition): _Bloc porte les roles (aop/Zin/Zf) au lieu de les jeter"
```

---

### Task 2: canonical positioner function for the inverting amplifier

**Files:**
- Modify: `circuit_analyzer/xml.py` (add new function right after `_positionner_blocs`, currently ending at line 821, before `_positionner_composants_bloc` at line 824)
- Test: `tests/test_xml_generator.py`

**Interfaces:**
- Consumes: `Composant`/`Component` objects (`.ref` attribute), `_PAS_X_BLOC` (260), `_PAS_Y_BLOC` (190) (existing module constants), `_positionner_grille_compacte(comps, x, y) -> dict[str, tuple[int,int]]` (existing, unchanged).
- Produces: `_positionner_amplificateur_inverseur(comps: list, roles: dict[str, list[str]], x: int, y: int) -> dict[str, tuple]` — values are `(x, y, angle)` for every ref in `roles['aop']`/`roles['Zin']`/`roles['Zf']`, and `(x, y)` (2-tuple, no angle) for any ref present in `comps` but absent from `roles` (satellites), via the existing grid fallback.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_xml_generator.py`:

```python
from circuit_analyzer.xml import _positionner_amplificateur_inverseur, _PAS_X_BLOC, _PAS_Y_BLOC


def test_positionner_amplificateur_inverseur_places_roles_canoniquement():
    """@brief Zin a gauche, AOP au centre, Zf au-dessus avec angle 90 (arc de contre-reaction)."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    roles = {"aop": ["U1"], "Zin": ["R1"], "Zf": ["R2"]}
    pos = _positionner_amplificateur_inverseur(comps, roles, 100, 200)
    x_aop, y_aop = 100 + 2 * _PAS_X_BLOC, 200 + _PAS_Y_BLOC
    assert pos["U1"] == (x_aop, y_aop, 0)
    assert pos["R1"] == (100, y_aop, 0)
    assert pos["R2"] == (x_aop, 200, 90)


def test_positionner_amplificateur_inverseur_garde_les_satellites():
    """@brief Un composant du bloc absent des roles (satellite) est place, pas perdu."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
        Component("C3", "C", {"1": "NET_IN", "2": "GND"}),
    ]
    roles = {"aop": ["U1"], "Zin": ["R1"], "Zf": ["R2"]}
    pos = _positionner_amplificateur_inverseur(comps, roles, 0, 0)
    assert "C3" in pos
    assert len(pos["C3"]) == 2


def test_positionner_amplificateur_inverseur_zin_composite_en_chaine():
    """@brief Un Zin composite (2 refs) se place en chaine horizontale, pas superpose."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_MID"}),
        Component("C1", "C", {"1": "NET_MID", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    roles = {"aop": ["U1"], "Zin": ["R1", "C1"], "Zf": ["R2"]}
    pos = _positionner_amplificateur_inverseur(comps, roles, 0, 0)
    assert pos["R1"][0] != pos["C1"][0]
    assert pos["R1"][1] == pos["C1"][1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k positionner_amplificateur_inverseur -v`
Expected: FAIL — `ImportError: cannot import name '_positionner_amplificateur_inverseur'`

- [ ] **Step 3: Implement**

Add to `circuit_analyzer/xml.py`, right after `_positionner_blocs` (currently
ends line 821) and before `_positionner_composants_bloc` (currently line 824):

```python
def _positionner_amplificateur_inverseur(comps, roles, x: int, y: int) -> dict:
    """@brief Gabarit canonique de l'ampli inverseur.

    Zin en chaîne horizontale à gauche de l'AOP (alignée sur son entrée),
    AOP au centre, Zf en chaîne horizontale AU-DESSUS de l'AOP avec un
    angle de 90° — c'est ce qui distingue visuellement le chemin de
    contre-réaction (OUT -> IN-) de la chaîne Zin (angle 0, horizontale).
    Tout composant du bloc absent de `roles` (satellite) est placé par la
    grille compacte existante, sous la disposition canonique — jamais perdu.

    @param comps Composants du bloc (Composant/Component).
    @param roles {'aop': [...], 'Zin': [...], 'Zf': [...]}.
    @param x, y Origine du bloc.
    @return dict {ref: (x, y, angle)} pour les rôles connus,
            {ref: (x, y)} pour les satellites.
    """
    pos = {}
    x_aop, y_aop = x + 2 * _PAS_X_BLOC, y + _PAS_Y_BLOC
    for ref in roles.get('aop', []):
        pos[ref] = (x_aop, y_aop, 0)
    for j, ref in enumerate(roles.get('Zin', [])):
        pos[ref] = (x + j * _PAS_X_BLOC, y_aop, 0)
    for j, ref in enumerate(roles.get('Zf', [])):
        pos[ref] = (x_aop + j * _PAS_X_BLOC, y, 90)
    restants = [c for c in comps if c.ref not in pos]
    pos.update(_positionner_grille_compacte(restants, x, y + 2 * _PAS_Y_BLOC))
    return pos
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k positionner_amplificateur_inverseur -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/xml.py tests/test_xml_generator.py
git commit -m "feat(disposition): gabarit canonique pour l'ampli inverseur (Zin/AOP/Zf)"
```

---

### Task 3: wire the canonical positioner into the dispatch + XML output

**Files:**
- Modify: `circuit_analyzer/xml.py:824-842` (`_positionner_composants_bloc`, add registry + tier-1 branch), `circuit_analyzer/xml.py:~1014-1021` (`generer_xml`'s position consumption, add angle support)
- Test: `tests/test_xml_generator.py`

**Interfaces:**
- Consumes: `_positionner_amplificateur_inverseur` (Task 2), `_Bloc.roles`/`.label`/`.comps` (Task 1), existing `_positionner_aop` etc. (unchanged), `gen.ajouter(nom, valeur, x, y, angle, forme, group_id, ref)` (existing, already accepts `angle`).
- Produces: `_POSITIONNEURS_PAR_MOTIF: dict[str, callable]` (new module-level registry). `_positionner_composants_bloc(bloc: _Bloc, x: int, y: int) -> dict` now returns 2- or 3-tuples depending on which tier handled the bloc. `generer_xml` now emits the `<angle>` value from a 3-tuple position when present.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_xml_generator.py`:

```python
import xml.etree.ElementTree as ET

from circuit_analyzer.xml import _Bloc, _positionner_composants_bloc


def test_positionner_composants_bloc_utilise_le_canonique_si_roles():
    """@brief Bloc reconnu + roles peuples -> positionneur canonique (pas le gabarit famille)."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    roles = {"aop": ["U1"], "Zin": ["R1"], "Zf": ["R2"]}
    bloc = _Bloc("Amplificateur inverseur (AOP)", comps, roles=roles)
    attendu = _positionner_amplificateur_inverseur(comps, roles, 50, 60)
    assert _positionner_composants_bloc(bloc, 50, 60) == attendu


def test_positionner_composants_bloc_repli_si_pas_de_roles():
    """@brief Meme circuit_type SANS roles (montage pas migre) garde l'ancien gabarit famille."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    bloc = _Bloc("Amplificateur inverseur (AOP)", comps)  # roles={} par defaut
    resultat = _positionner_composants_bloc(bloc, 50, 60)
    # L'ancien gabarit famille place l'AOP a (x + _PAS_X_BLOC, y) — pas x+2*_PAS_X_BLOC.
    assert resultat["U1"][:2] == (50 + _PAS_X_BLOC, 60)


def _item(xml_str, ref):
    """@brief Helper de test : le <DataItem> dont <reference> vaut `ref`."""
    root = ET.fromstring(xml_str)
    for item in root.iter("DataItem"):
        if item.findtext("reference") == ref:
            return item
    return None


def test_generer_xml_ecrit_angle_canonique_pour_zf():
    """@brief La resistance de contre-reaction (Zf) recoit l'angle canonique 90 dans le XML."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    resultats = match_patterns(build_graph(comps))
    xml = components_to_xml(comps, resultats)
    item_zf, item_zin = _item(xml, "R2"), _item(xml, "R1")
    assert item_zf is not None and item_zin is not None
    assert item_zf.findtext("angle") == "90"
    assert item_zin.findtext("angle") == "0"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k "positionner_composants_bloc or ecrit_angle" -v`
Expected: FAIL — dispatch test fails because `_positionner_composants_bloc` doesn't
check `_POSITIONNEURS_PAR_MOTIF` yet (falls into the old `_positionner_aop`
branch regardless of roles); angle test fails because `generer_xml` never
passes `angle=` to `gen.ajouter` (always 0, `item_zf.findtext("angle") == "0"`,
not `"90"`).

- [ ] **Step 3: Implement**

In `circuit_analyzer/xml.py`, add the registry right after
`_positionner_amplificateur_inverseur` (added in Task 2) and before
`_positionner_composants_bloc`:

```python
_POSITIONNEURS_PAR_MOTIF = {
    "Amplificateur inverseur (AOP)": _positionner_amplificateur_inverseur,
}
```

Change `_positionner_composants_bloc` (currently lines 824-842):

```python
def _positionner_composants_bloc(bloc: _Bloc, x: int, y: int) -> dict[str, tuple[int, int]]:
    """@brief Place les composants a l'interieur d'un bloc visuel.

    @param bloc Bloc de circuit detecte.
    @param x Origine horizontale du bloc.
    @param y Origine verticale du bloc.
    @return dict {ref -> (x, y)} Positions absolues.
    """
    if "commande de relais" in bloc.label.lower():
        return _positionner_commande_relais(bloc.comps, x, y)
```
to:
```python
def _positionner_composants_bloc(bloc: _Bloc, x: int, y: int) -> dict:
    """@brief Place les composants a l'interieur d'un bloc visuel.

    @param bloc Bloc de circuit detecte.
    @param x Origine horizontale du bloc.
    @param y Origine verticale du bloc.
    @return dict {ref -> (x, y)} ou {ref -> (x, y, angle)} pour les
            montages avec un gabarit canonique. Positions absolues.
    """
    positionneur = _POSITIONNEURS_PAR_MOTIF.get(bloc.label)
    if positionneur is not None and bloc.roles:
        return positionneur(bloc.comps, bloc.roles, x, y)
    if "commande de relais" in bloc.label.lower():
        return _positionner_commande_relais(bloc.comps, x, y)
```
(rest of the function body — the "pont diviseur"/"aop"/"filtre rc"/default
branches — is unchanged, just keep it below the new lines above.)

Change `generer_xml`'s position consumption (currently, right before the
`gen.ajouter(...)` call):

```python
        if positions and comp.ref in positions:
            x, y = positions[comp.ref]
        else:
            x = 250 + (i % PER_RANGEE) * _LARG_COMP
            y = 250 + (i // PER_RANGEE) * _HAUT_RANGEE
        cid = gen.ajouter(nom_forme, comp.value, x=x, y=y, ref=comp.ref,
                          group_id=ids_groupes.get(comp.ref, 0))
```
to:
```python
        angle = 0
        if positions and comp.ref in positions:
            pos_comp = positions[comp.ref]
            x, y = pos_comp[0], pos_comp[1]
            if len(pos_comp) > 2:
                angle = pos_comp[2]
        else:
            x = 250 + (i % PER_RANGEE) * _LARG_COMP
            y = 250 + (i // PER_RANGEE) * _HAUT_RANGEE
        cid = gen.ajouter(nom_forme, comp.value, x=x, y=y, angle=angle, ref=comp.ref,
                          group_id=ids_groupes.get(comp.ref, 0))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k "positionner_composants_bloc or ecrit_angle" -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full existing suite to confirm no regressions**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -q`
Expected: all tests pass (37 passed: 29 original + 2 from Task 1 + 3 from
Task 2 + 3 from Task 3)

Also run the whole project's test suite once, since `_positionner_composants_bloc`/
`generer_xml` may be exercised by other test files:

Run: `PYTHONUTF8=1 python -m pytest -q`
Expected: no new failures compared to the pre-existing baseline.

- [ ] **Step 6: Commit**

```bash
git add circuit_analyzer/xml.py tests/test_xml_generator.py
git commit -m "feat(disposition): branche le gabarit canonique + ecrit l'angle dans le XML"
```

---

### Task 4: connectivity round-trip test (hard constraint)

**Files:**
- Test: `tests/test_xml_generator.py`

**Interfaces:**
- Consumes: `components_to_xml`, `match_patterns`, `build_graph`, `_xml_to_components` (all existing, already imported at the top of the test file).
- Produces: one new test, no production code change.

- [ ] **Step 1: Write the test**

Add to `tests/test_xml_generator.py`:

```python
def test_disposition_canonique_preserve_la_connectivite():
    """@brief Contrainte dure : la regeneration avec disposition canonique
    ne change AUCUNE connexion — verifie en re-detectant sur le resultat.
    """
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    resultats = match_patterns(build_graph(comps))
    orig = sorted(r["circuit_type"] for r in resultats)
    xml = components_to_xml(comps, resultats)
    back = _xml_to_components(xml)
    roundtrip = sorted(r["circuit_type"] for r in match_patterns(build_graph(back)))
    assert orig == roundtrip
```

This test differs from the existing `test_roundtrip_inverting_amp` (line 94):
that one calls `components_to_xml(comps)` WITHOUT `resultats`, so
`_positionner_blocs`/the new canonical positioner never runs (falls to the
plain `PER_RANGEE` fallback). This new test passes `resultats` explicitly so
the Task 3 code path actually executes, and compares full sorted pattern
lists (not just membership) — matching the codebase's existing idiom for
"connectivity preserved" already used in `test_roundtrip_combined_multi_pattern`.

- [ ] **Step 2: Run to verify it passes**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k connectivite -v`
Expected: PASS (this should pass immediately given Tasks 1-3 — if it fails,
that's a real bug in the canonical positioner, not a missing feature; debug
before proceeding)

- [ ] **Step 3: Commit**

```bash
git add tests/test_xml_generator.py
git commit -m "test(disposition): verifie que la disposition canonique preserve la connectivite"
```

---

### Task 5: visual verification (render to PNG and look at it)

**Files:**
- Create: `tools/render_boardsch_layout.py`

**Interfaces:**
- Consumes: a BoardSCH XML string (as produced by `components_to_xml`) — specifically each `<DataItem>`'s `<reference>`, `<CtrIem><X>/<Y></CtrIem>`, `<angle>`.
- Produces: a PNG file at a given path. Standalone script, no other module depends on it.

- [ ] **Step 1: Write the renderer**

Create `tools/render_boardsch_layout.py`:

```python
"""
@file render_boardsch_layout.py
@brief Rendu minimal (rectangles + labels) d'un schema BoardSCH XML, pour
verification visuelle d'une disposition canonique.

Usage:
  python tools/render_boardsch_layout.py

Genere tools/_renders/disposition_ampli_inverseur.png depuis un cas de test
synthetique (ampli inverseur).

ponytail: rectangles + label + trait d'angle, pas le catalogue de formes
reelles (Puce/AOP/etc.) — suffisant pour verifier gauche/centre/au-dessus a
l'oeil. Upgrade vers les vraies formes si l'inspection visuelle simple ne
suffit plus a juger une disposition.
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "tools" / "_renders"


def render(xml_str: str, out_path: Path, largeur: int = 80, hauteur: int = 40) -> None:
    """@brief Dessine chaque <DataItem> du XML en rectangle labellise.

    @param xml_str Document BoardSCH (sortie de generer_xml/components_to_xml).
    @param out_path Chemin du PNG a ecrire.
    @param largeur, hauteur Taille (px modele) du rectangle par composant.
    """
    root = ET.fromstring(xml_str)
    items = list(root.iter("DataItem"))

    fig, ax = plt.subplots(figsize=(8, 6))
    for item in items:
        ref = item.findtext("reference") or "?"
        cx = float(item.findtext("CtrIem/X") or 0)
        cy = float(item.findtext("CtrIem/Y") or 0)
        angle = float(item.findtext("angle") or 0)
        rect = Rectangle((cx - largeur / 2, cy - hauteur / 2), largeur, hauteur,
                          angle=angle, rotation_point='center',
                          fill=False, edgecolor="black")
        ax.add_patch(rect)
        ax.text(cx, cy, ref, ha="center", va="center", fontsize=9)

    ax.set_aspect("equal")
    ax.autoscale()
    ax.invert_yaxis()  # coordonnees ecran BoardSCH : Y croit vers le bas
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    from circuit_analyzer.graph_builder import build_graph
    from circuit_analyzer.matcher import match_patterns
    from circuit_analyzer.parser import Component
    from circuit_analyzer.xml_generator import components_to_xml

    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    resultats = match_patterns(build_graph(comps))
    xml = components_to_xml(comps, resultats)
    render(xml, OUT / "disposition_ampli_inverseur.png")
    print(f"Rendu ecrit : {OUT / 'disposition_ampli_inverseur.png'}")
```

- [ ] **Step 2: Run it**

Run: `PYTHONUTF8=1 python tools/render_boardsch_layout.py`
Expected: prints `Rendu ecrit : .../tools/_renders/disposition_ampli_inverseur.png`,
file exists.

- [ ] **Step 3: Actually look at the PNG**

Read `tools/_renders/disposition_ampli_inverseur.png` and visually confirm:
R1 (Zin) is to the left of U1 (AOP); R2 (Zf) is above U1, rotated 90°;
nothing overlaps. If it doesn't look right, that's a bug in Task 2's
`_positionner_amplificateur_inverseur` — fix it there and re-run this step,
don't just adjust the renderer to make a wrong layout look acceptable.

- [ ] **Step 4: Commit**

```bash
git add tools/render_boardsch_layout.py
git commit -m "tools(disposition): rendu PNG minimal pour verifier une disposition canonique"
```
(`tools/_renders/` is gitignored — the PNG itself is not committed.)

---

## After this plan

Everything else in the design doc's "Points ouverts" — migrating more
patterns beyond the inverting amplifier, refining composite Zin/Zf ordering
beyond 2 refs — is deliberately out of scope here. Each additional pattern
migration is a new `_positionner_*` function + one `_POSITIONNEURS_PAR_MOTIF`
entry, following the exact shape Tasks 2-3 established.
