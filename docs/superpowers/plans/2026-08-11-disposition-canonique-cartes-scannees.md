# Disposition canonique sur cartes scannées Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the canonical layout (Zin/AOP/Zf) already shipped for the
netlist path (`generer_xml`) to the patch-in-place path
(`eretro_patch.ecrire_groupes`), used for real scanned BoardSCH boards —
by translating only the role-identified components of a recognized,
migrated pattern, anchored on their real centroid.

**Architecture:** Two new pure functions in `circuit_analyzer/eretro_patch.py`:
`_deltas_disposition_canonique` (compute per-ref `(dx, dy)` from real
positions + the existing canonical-layout math) and `_appliquer_deltas`
(translate `<CtrIem>` and touched wire endpoints). Both wired into
`ecrire_groupes`, reusing the `blocs`/`roles` it already computes via
`_grouper_par_circuit`.

**Tech Stack:** Python, `xml.etree.ElementTree`, `pytest`.

## Global Constraints

- Only components in `bloc.roles` (`aop`/`Zin`/`Zf`) of a bloc whose
  `label` is in `_POSITIONNEURS_PAR_MOTIF` move. Every other component
  (satellites included) keeps its real scanned position untouched.
- Pure translation — never write `<angle>`. No rotation risk.
- Anchor the canonical layout on the group's current real centroid, not
  an arbitrary origin — minimizes collision risk with unmoved neighbors.
- `<CtrIem>` gets translated; connected wire endpoints (`<Line><LP><PointF>`)
  get the SAME delta as whichever of their two components moved. The
  other endpoint (on an unmoved component) is never touched.
- `CFirst`/`CLast` (which wire connects which pins) is never modified —
  connectivity is preserved by construction, same guarantee as the
  netlist-path feature.
- Fail-soft: missing/malformed `<CtrIem>` or `<LP>` on a real element
  → that element/wire is left untouched, never an exception.
- Scope: "Amplificateur inverseur (AOP)" only, same as the netlist-path
  feature — no other pattern is touched by this plan.

---

### Task 1: `_deltas_disposition_canonique` — compute per-ref translation deltas

**Files:**
- Modify: `circuit_analyzer/eretro_patch.py:16` (imports), add new function after `_ecrire` (currently ends line 90, before `ecrire_groupes` at line 93)
- Test: `tests/test_eretro_patch.py`

**Interfaces:**
- Consumes: `_positionner_amplificateur_inverseur(comps, roles, x, y) -> dict` and `_POSITIONNEURS_PAR_MOTIF: dict[str, callable]` and `_PAS_X_BLOC`/`_PAS_Y_BLOC` (all existing, from `circuit_analyzer.xml`). `SourceXML.elements: dict[str, ET.Element]` (existing). `_Bloc.label: str` / `.roles: dict[str, list[str]]` (existing, from Task 1 of the previous plan).
- Produces: `_deltas_disposition_canonique(source, composants, blocs) -> dict[str, tuple[float, float]]` — `{ref: (dx, dy)}`, only for refs whose canonical position differs from their real one. Empty dict when nothing qualifies.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_eretro_patch.py`, after the imports (near the top, after
`_DOSSIER_REEL = ...` at line 13):

```python
def test_deltas_disposition_canonique_ancre_sur_le_centroide_reel(tmp_path):
    """@brief Les refs de role (aop/Zin/Zf) d'un ampli inverseur recoivent un
    delta qui les ramene vers la disposition canonique, centree sur leur
    centroide REEL actuel — pas une origine arbitraire."""
    from circuit_analyzer.eretro_patch import _deltas_disposition_canonique
    from circuit_analyzer.xml import _grouper_par_circuit

    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Composant("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Composant("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, res = _analyser(chemin)
    source = lus.source
    blocs = _grouper_par_circuit(lus, res)
    assert len(blocs) == 1 and blocs[0].roles, "l'ampli inverseur doit etre reconnu avec ses roles"

    deltas = _deltas_disposition_canonique(source, lus, blocs)
    assert set(deltas) == {"U1", "R1", "R2"}
    for ref, (dx, dy) in deltas.items():
        assert isinstance(dx, (int, float)) and isinstance(dy, (int, float))


def test_deltas_disposition_canonique_vide_sans_roles(tmp_path):
    """@brief Un montage non migre (pas de roles) ne produit aucun delta."""
    from circuit_analyzer.eretro_patch import _deltas_disposition_canonique
    from circuit_analyzer.xml import _Bloc

    comps = [Composant("R1", "R", {"1": "A", "2": "B"})]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, _ = _analyser(chemin)
    bloc_sans_roles = _Bloc("Divers", list(lus))
    deltas = _deltas_disposition_canonique(lus.source, lus, [bloc_sans_roles])
    assert deltas == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -k deltas_disposition_canonique -v`
Expected: FAIL — `ImportError: cannot import name '_deltas_disposition_canonique'`

- [ ] **Step 3: Write the implementation**

In `circuit_analyzer/eretro_patch.py`, change the import line (currently line 16):

```python
from circuit_analyzer.xml import _grouper_par_circuit, _ids_groupes_par_ref
```
to:
```python
from circuit_analyzer.xml import (
    _grouper_par_circuit,
    _ids_groupes_par_ref,
    _PAS_X_BLOC,
    _PAS_Y_BLOC,
    _POSITIONNEURS_PAR_MOTIF,
    _positionner_amplificateur_inverseur,
)
```

Add this function right after `_ecrire` (currently ends at line 90, right
before `def ecrire_groupes` at line 93):

```python
def _deltas_disposition_canonique(source, composants, blocs) -> dict:
    """@brief Deplacements (dx, dy) des composants de role d'un montage migre.

    @param source SourceXML (pont ref -> ET.Element).
    @param composants Composants analyses (Composant, avec .ref).
    @param blocs Sortie de _grouper_par_circuit (porte .label et .roles).
    @return dict {ref: (dx, dy)} ; {} si rien a deplacer.

    N'agit QUE sur les refs de role (aop/Zin/Zf) d'un montage dont le label
    est dans _POSITIONNEURS_PAR_MOTIF ET dont roles est peuple — meme garde
    que le chemin generer_xml, aucune regression possible sur un montage non
    migre. Les satellites et tout le reste de la carte ne sont jamais
    consideres ici.

    La disposition canonique est ANCREE sur le centroide REEL actuel du
    groupe (pas une origine arbitraire) : minimise le risque de chevaucher
    un composant reel voisin non deplace.
    """
    comp_par_ref = {c.ref: c for c in composants}
    deltas = {}
    for bloc in blocs:
        if bloc.label not in _POSITIONNEURS_PAR_MOTIF or not bloc.roles:
            continue
        refs_role = [ref for refs in bloc.roles.values() for ref in refs]
        positions_reelles = {}
        for ref in refs_role:
            element = source.elements.get(ref)
            if element is None:
                continue
            x_elem, y_elem = element.find("CtrIem/X"), element.find("CtrIem/Y")
            if x_elem is None or y_elem is None:
                continue
            try:
                positions_reelles[ref] = (float(x_elem.text), float(y_elem.text))
            except (TypeError, ValueError):
                continue
        if not positions_reelles:
            continue

        cx = sum(p[0] for p in positions_reelles.values()) / len(positions_reelles)
        cy = sum(p[1] for p in positions_reelles.values()) / len(positions_reelles)
        # _positionner_amplificateur_inverseur(comps, roles, x, y) centre son
        # AOP a (x + 2*_PAS_X_BLOC, y + _PAS_Y_BLOC) et sa chaine Zf a (., y) :
        # on choisit (x, y) pour que ce centre approximatif de la disposition
        # coincide avec le centroide reel calcule ci-dessus.
        x_origine = cx - 1.5 * _PAS_X_BLOC
        y_origine = cy - _PAS_Y_BLOC
        comps_role = [comp_par_ref[ref] for ref in positions_reelles if ref in comp_par_ref]
        nouvelles = _positionner_amplificateur_inverseur(
            comps_role, bloc.roles, x_origine, y_origine)

        for ref, position in nouvelles.items():
            if ref not in positions_reelles:
                continue
            nx, ny = position[0], position[1]
            ox, oy = positions_reelles[ref]
            dx, dy = nx - ox, ny - oy
            if dx or dy:
                deltas[ref] = (dx, dy)
    return deltas
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -k deltas_disposition_canonique -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full existing eretro_patch suite to confirm no regressions**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -q`
Expected: all previously-passing tests still pass

- [ ] **Step 6: Commit**

```bash
git add circuit_analyzer/eretro_patch.py tests/test_eretro_patch.py
git commit -m "feat(disposition): calcule les deltas de disposition canonique ancres sur le centroide reel"
```

---

### Task 2: `_appliquer_deltas` — translate CtrIem and touched wire endpoints

**Files:**
- Modify: `circuit_analyzer/eretro_patch.py`, add new functions right after `_deltas_disposition_canonique` (from Task 1), before `def ecrire_groupes`
- Test: `tests/test_eretro_patch.py`

**Interfaces:**
- Consumes: `SourceXML.elements`, `.lignes`, `.lignes_refs` (existing). The `deltas: dict[str, tuple[float, float]]` shape produced by Task 1's `_deltas_disposition_canonique`.
- Produces: `_appliquer_deltas(source, deltas) -> None` — mutates the ET tree in place (matches the existing `_ecrire`/`_appliquer` mutation style in this file). `_decaler_point(point, delta)` — small helper, translates one `<PointF>`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_eretro_patch.py`:

```python
def test_appliquer_deltas_translate_ctriem_et_lextremite_du_fil_touchee(tmp_path):
    """@brief Un ref avec un delta voit son CtrIem ET l'extremite de fil qui le
    touche decales du meme montant. L'AUTRE extremite (composant non deplace)
    reste intacte."""
    from circuit_analyzer.eretro_patch import _appliquer_deltas

    comps = [
        Composant("R1", "R", {"1": "N1", "2": "N2"}),
        Composant("R2", "R", {"1": "N2", "2": "N3"}),
    ]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, _ = _analyser(chemin)
    source = lus.source

    x_avant = float(source.elements["R1"].find("CtrIem/X").text)
    y_avant = float(source.elements["R1"].find("CtrIem/Y").text)
    x2_avant = float(source.elements["R2"].find("CtrIem/X").text)

    # Le fil entre R1 et R2 (les deux refs connues du pont) : capte SES
    # PointF AVANT translation pour comparer apres.
    idx_fil = next(i for i, (ra, rb) in source.lignes_refs.items()
                   if {ra, rb} == {"R1", "R2"})
    points_avant = [(float(p.findtext("X")), float(p.findtext("Y")))
                    for p in source.lignes[idx_fil].findall("LP/PointF")]

    _appliquer_deltas(source, {"R1": (50.0, -30.0)})

    assert float(source.elements["R1"].find("CtrIem/X").text) == x_avant + 50.0
    assert float(source.elements["R1"].find("CtrIem/Y").text) == y_avant - 30.0
    # R2 n'a pas de delta : son CtrIem est intact.
    assert float(source.elements["R2"].find("CtrIem/X").text) == x2_avant

    points_apres = [(float(p.findtext("X")), float(p.findtext("Y")))
                    for p in source.lignes[idx_fil].findall("LP/PointF")]
    # Exactement UNE extremite a bouge de (50, -30), l'autre est intacte.
    deltas_observes = sorted(
        (round(ax - bx, 6), round(ay - by, 6))
        for (ax, ay), (bx, by) in zip(points_apres, points_avant))
    assert deltas_observes == sorted([(0.0, 0.0), (50.0, -30.0)])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -k appliquer_deltas -v`
Expected: FAIL — `ImportError: cannot import name '_appliquer_deltas'`

- [ ] **Step 3: Write the implementation**

Add to `circuit_analyzer/eretro_patch.py`, right after `_deltas_disposition_canonique`:

```python
def _decaler_point(point, delta) -> None:
    """@brief Translate un <PointF> (X, Y) du delta donne. No-op si malforme."""
    dx, dy = delta
    x_elem, y_elem = point.find("X"), point.find("Y")
    if x_elem is None or y_elem is None:
        return
    try:
        x_elem.text = str(float(x_elem.text) + dx)
        y_elem.text = str(float(y_elem.text) + dy)
    except (TypeError, ValueError):
        return


def _appliquer_deltas(source, deltas) -> None:
    """@brief Translate <CtrIem> et les extremites de fil des refs deplacees.

    @param source SourceXML (pont ref -> ET.Element, fils, refs de fils).
    @param deltas {ref: (dx, dy)} — sortie de _deltas_disposition_canonique.

    Ne touche jamais <angle> (translation pure). Un fil dont une SEULE
    extremite est dans `deltas` ne voit QUE cette extremite bouger — l'autre
    (composant non deplace) reste a sa position reelle scannee. Un fil dont
    les DEUX extremites sont dans `deltas` (fil interne au groupe) voit
    chacune bouger de SON propre delta.
    """
    for ref, delta in deltas.items():
        element = source.elements.get(ref)
        if element is None:
            continue
        ctr = element.find("CtrIem")
        if ctr is None:
            continue
        _decaler_point(ctr, delta)

    for idx, ligne in enumerate(source.lignes):
        ra, rb = source.lignes_refs.get(idx, (None, None))
        points = ligne.findall("LP/PointF")
        if len(points) < 2:
            continue
        if ra in deltas:
            _decaler_point(points[0], deltas[ra])
        if rb in deltas:
            _decaler_point(points[-1], deltas[rb])
```

Note: `_decaler_point` is reused for both `<CtrIem>` (which has direct
`<X>`/`<Y>` children, same shape as `<PointF>`) and wire `<PointF>` — both
are `X`/`Y` pairs, so the same helper applies to both without duplication.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -k appliquer_deltas -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Run the full existing eretro_patch suite to confirm no regressions**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -q`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add circuit_analyzer/eretro_patch.py tests/test_eretro_patch.py
git commit -m "feat(disposition): translate CtrIem et les extremites de fil touchees"
```

---

### Task 3: wire both into `ecrire_groupes`, end-to-end

**Files:**
- Modify: `circuit_analyzer/eretro_patch.py:119-120` (inside `ecrire_groupes`)
- Test: `tests/test_eretro_patch.py`

**Interfaces:**
- Consumes: `_deltas_disposition_canonique` (Task 1), `_appliquer_deltas` (Task 2), existing `_grouper_par_circuit`/`ecrire_groupes`.
- Produces: `ecrire_groupes` now applies canonical translation for migrated, role-populated patterns before writing groups. No signature change.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_eretro_patch.py`:

```python
def test_ecrire_groupes_deplace_lampli_inverseur_vers_sa_disposition_canonique(tmp_path):
    """@brief Bout en bout : un ampli inverseur reconnu sur une carte "scannee"
    (chemin ecrire_groupes) est translate vers sa disposition canonique."""
    from circuit_analyzer.eretro_patch import ecrire_groupes

    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Composant("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Composant("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, res = _analyser(chemin)
    positions_avant = {
        ref: (float(el.find("CtrIem/X").text), float(el.find("CtrIem/Y").text))
        for ref, el in lus.source.elements.items()
    }

    xml_patche = ecrire_groupes(lus.source, lus, res)
    racine = ET.fromstring(xml_patche)
    positions_apres = {
        item.findtext("reference"):
            (float(item.find("CtrIem/X").text), float(item.find("CtrIem/Y").text))
        for item in racine.findall(".//CmpntL/DataItem")
    }

    # Les 3 composants de l'ampli inverseur ont bouge (ou sont deja canoniques,
    # peu probable ici mais pas garanti faux) — au moins un a bouge.
    assert any(positions_avant[ref] != positions_apres[ref] for ref in ("U1", "R1", "R2"))


def test_ecrire_groupes_ne_deplace_jamais_un_montage_non_migre(tmp_path):
    """@brief Garde-fou : un montage SANS positionneur canonique (ex. suiveur
    de tension) garde ses positions reelles intactes, seul le groupage s'applique."""
    from circuit_analyzer.eretro_patch import ecrire_groupes

    comps = [
        Composant("U1", "U", {"IN+": "N1", "IN-": "N2", "OUT": "N2"}),
    ]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, res = _analyser(chemin)
    x_avant = float(lus.source.elements["U1"].find("CtrIem/X").text)
    y_avant = float(lus.source.elements["U1"].find("CtrIem/Y").text)

    xml_patche = ecrire_groupes(lus.source, lus, res)
    racine = ET.fromstring(xml_patche)
    item = next(i for i in racine.findall(".//CmpntL/DataItem")
                if i.findtext("reference") == "U1")
    assert float(item.find("CtrIem/X").text) == x_avant
    assert float(item.find("CtrIem/Y").text) == y_avant


def test_ecrire_groupes_preserve_la_connectivite_apres_translation(tmp_path):
    """@brief Contrainte dure : la translation ne change AUCUNE connexion —
    reparse le resultat et confirme que l'ampli inverseur est toujours detecte
    avec les memes composants."""
    from circuit_analyzer.xml import lire_xml
    from circuit_analyzer.eretro_patch import ecrire_groupes

    comps = [
        Composant("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Composant("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Composant("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, res = _analyser(chemin)
    xml_patche = ecrire_groupes(lus.source, lus, res)

    chemin_patche = os.path.join(str(tmp_path), "patche.xml")
    with open(chemin_patche, "w", encoding="utf-8") as f:
        f.write(xml_patche)
    relu, res_relu = _analyser(chemin_patche)
    types_relu = sorted(r["circuit_type"] for r in res_relu)
    assert "Amplificateur inverseur (AOP)" in types_relu
    assert {c.ref for c in relu} == {"U1", "R1", "R2"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -k "deplace_lampli or ne_deplace_jamais or preserve_la_connectivite_apres_translation" -v`
Expected: FAIL — `test_ecrire_groupes_deplace_lampli_inverseur_vers_sa_disposition_canonique`
fails (positions unchanged, since `ecrire_groupes` doesn't call the new
functions yet); the other two pass already by pre-existing behavior (nothing
to break yet) — that's fine, they become real regression guards once Task 3's
implementation lands.

- [ ] **Step 3: Write the implementation**

In `circuit_analyzer/eretro_patch.py`, change `ecrire_groupes`'s opening
lines (currently lines 119-120):

```python
    blocs = _grouper_par_circuit(composants, resultats) if resultats else []
    gid_par_ref = _ids_groupes_par_ref(blocs) if blocs else {}
```
to:
```python
    blocs = _grouper_par_circuit(composants, resultats) if resultats else []
    if blocs:
        _appliquer_deltas(source, _deltas_disposition_canonique(source, composants, blocs))
    gid_par_ref = _ids_groupes_par_ref(blocs) if blocs else {}
```

Positions are translated BEFORE `_ecrire_grpl` runs (still further down in
the same function, unchanged) — so the group's bounding rectangle
(`_rectangle`, called from `_ecrire_grpl`) is computed from the ALREADY
translated positions, giving a correctly-sized group box around the
canonical layout rather than the original scanned one.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -k "deplace_lampli or ne_deplace_jamais or preserve_la_connectivite_apres_translation" -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full test suite to confirm no regressions**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -q`
Expected: all tests pass

Run: `PYTHONUTF8=1 python -m pytest -q`
Expected: no new failures compared to the pre-existing baseline.

- [ ] **Step 6: Commit**

```bash
git add circuit_analyzer/eretro_patch.py tests/test_eretro_patch.py
git commit -m "feat(disposition): branche la translation canonique dans ecrire_groupes"
```

---

### Task 4: visual verification (render before/after and look at it)

**Files:**
- Modify: `tools/render_boardsch_layout.py` (extend, don't rewrite — add a
  second demo path)

**Interfaces:**
- Consumes: `ecrire_groupes`, `_fichier_synthetique`-equivalent construction, the existing `render(xml_str, out_path, ...)` function (unchanged signature).
- Produces: two new PNGs for manual inspection, no new production code.

- [ ] **Step 1: Add a second demo block to the renderer**

In `tools/render_boardsch_layout.py`, the `if __name__ == "__main__":` block
currently renders one PNG (the netlist-path demo). Extend it to also render
a before/after pair for the patch-in-place path:

```python
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

    # Chemin carte scannee (ecrire_groupes) : avant/apres translation.
    import tempfile

    from circuit_analyzer.eretro_patch import ecrire_groupes
    from circuit_analyzer.xml import lire_xml

    with tempfile.TemporaryDirectory() as tmp:
        chemin = str(Path(tmp) / "carte.xml")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(xml)
        render(xml, OUT / "carte_scannee_avant.png")
        print(f"Rendu ecrit : {OUT / 'carte_scannee_avant.png'}")

        relus = lire_xml(chemin)
        res_relus = match_patterns(build_graph(relus))
        xml_patche = ecrire_groupes(relus.source, relus, res_relus)
        render(xml_patche, OUT / "carte_scannee_apres.png")
        print(f"Rendu ecrit : {OUT / 'carte_scannee_apres.png'}")
```

- [ ] **Step 2: Run it**

Run: `PYTHONUTF8=1 python tools/render_boardsch_layout.py`
Expected: prints three "Rendu ecrit" lines, all three PNG files exist under
`tools/_renders/`.

- [ ] **Step 3: Actually look at both PNGs**

Read `tools/_renders/carte_scannee_avant.png` and
`tools/_renders/carte_scannee_apres.png`. Confirm: in "avant", the 3
components are wherever `generer_xml`'s plain grid put them (not
canonical). In "apres", R1/U1/R2 are in the canonical layout (Zin left,
AOP center, Zf above) and wires still connect to their boxes — same visual
check as the netlist-path feature. If anything looks disconnected or
overlapping, that's a bug in Task 1-3 — fix there and re-render, don't
adjust the renderer to hide it.

- [ ] **Step 4: Commit**

```bash
git add tools/render_boardsch_layout.py
git commit -m "tools(disposition): rendu avant/apres pour le chemin carte scannee"
```
(The PNGs themselves are gitignored under `tools/_renders/` — not committed.)

---

## After this plan

Collision detection against unmoved real neighbors (explicitly deferred in
the design doc) and extending beyond the inverting amplifier are both out
of scope here — each is a candidate for a future, separate plan once this
one is validated against real usage.
