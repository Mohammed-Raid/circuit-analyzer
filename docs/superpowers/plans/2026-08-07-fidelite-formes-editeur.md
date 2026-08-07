# Fidélité de forme réelle à l'ouverture/export du schéma + dessin libre — Plan d'implémentation

> **Pour l'exécutant :** REQUIRED SUB-SKILL : `superpowers:subagent-driven-development`
> (recommandé) ou `superpowers:executing-plans` pour exécuter ce plan tâche par
> tâche. Les étapes utilisent la syntaxe case à cocher (`- [ ]`) pour le suivi.

**Spec de référence :** `docs/superpowers/specs/2026-08-07-fidelite-formes-editeur-design.md`
(commit `2c8d25d`).

**Goal :** un composant ouvert depuis un fichier ERetroDesign, exporté vers
ERetroDesign, ou dessiné à la main dans l'éditeur, porte sa VRAIE forme (et
son vrai brochage nommé) dans les deux applications — plus de boîte
générique ni de broches perdues pour un composant de type inconnu (« puce »).

**Architecture :** un composant posé (`CompInst`) et un composant analysé
(`Composant`) gagnent chacun deux champs optionnels miroirs — `primitives`
(contour réel : lignes/arcs/polygones) et `pinout` (brochage réel :
`{nom: (côté, décalage)}`, même format que le brochage libre existant,
spec 2026-07-23). Trois sources alimentent ces champs (import, choix
bibliothèque déjà livré, dessin à la main) ; un seul chemin de lecture
(`_geom`) et un seul chemin d'écriture (`_xml_composant`/`generer_xml`) les
consomment. Réutilise au maximum le code déjà écrit par le chantier
précédent (`primitives_depuis_dataitem`, `geometrie_libre`, `aimanter_bord`,
`_primitives_vers_xml`, `eretro_lib._entree_depuis_dataitem`) plutôt que de
réécrire un second parseur.

**Périmètre volontairement restreint (décision d'implémentation, cohérente
avec le problème réellement démontré au boss) :** le brochage/contour réel
ne remplace le comportement générique QUE pour les composants qui tombent
aujourd'hui dans les chemins catch-all de `circuit_analyzer/xml.py`
(`boite_ic` → type `U` à plan vide, et type `X` inconnu) — c'est-à-dire
exactement les « puces » sans symbole dédié. Les types à PLAN NOMMÉ
(R/C/D/AOP historique) gardent leur symbole maison inchangé : ils ont déjà
un dessin correct, et toucher leur remappage de broches (A/K, IN+/IN-...)
serait un chantier séparé, hors du problème démontré (directive connue du
boss : ne pas gold-plater les réseaux passifs déjà couverts).

**Tech Stack :** Python 3.11, Tkinter/customtkinter, pytest. Aucune nouvelle
dépendance.

## Global Constraints

- Commits en **français**, **jamais** de footer `Co-Authored-By: Claude` ni
  `Generated with Claude Code`.
- **Jamais `git add -A`** : fichiers ajoutés un par un.
- **Ne jamais committer** `custom_circuits.json` ni `component_library.json`.
- `ERetroDesign/`, `CARTE POUR TESTER (VRAI TEST)/`, `docs.rar`, `dist_demo/`,
  `test14.xml` : lecture seule, jamais committés.
- `PYTHONUTF8=1` sur toutes les commandes pytest.
- `schemdraw==0.22` pinné (contrainte globale du dépôt, non touchée ici).
- Branche `rewrite-simple` ; rien n'est poussé sans accord explicite.
- PNG rendus et inspectés avant tout commit touchant le dessin ; jamais de
  PNG committé.

## Structure des fichiers

| Fichier | Responsabilité ajoutée |
|---|---|
| `circuit_analyzer/composant.py` | `Composant` gagne `primitives`/`pinout` optionnels |
| `circuit_analyzer/xml.py` | `lire_xml` capture le contour/brochage réel pour `U`(vide)/`X` ; `_Comp`/`_Generateur`/`generer_xml` les écrivent à l'export |
| `gui/schematic_io.py` | `build_from_components` utilise le brochage réel s'il existe ; `editor_to_dict`/(lecture dans `schematic_editor.py`) le font persister dans le `.circ` |
| `gui/schematic_editor.py` | `CompInst.forme_primitives` ; `_geom` le combine au brochage ; nouveau mode « dessin de contour » ; `exporter_composants` le fait suivre |
| `tests/test_eretro.py`, `tests/test_schematic_io.py`, `tests/test_xml_generator.py`, `tests/test_brochage_libre.py` | Tests de chaque étage |

---

### Task 1 : `Composant.primitives`/`pinout` + capture à l'import

**Files:**
- Modify: `circuit_analyzer/composant.py` (dataclass `Composant`, après `par_forme`)
- Modify: `circuit_analyzer/xml.py` (`lire_xml`, boucle `_reconnaitre`, autour de `l.1656-1680`)
- Test: `tests/test_eretro.py`

**Interfaces produites :**
- `Composant.primitives: list | None = None`
- `Composant.pinout: dict | None = None`

- [ ] **Step 1 : écrire les tests qui échouent**

Dans `tests/test_eretro.py`, étendre les helpers existants (additif — tous
les appels existants, sans les nouveaux paramètres, restent inchangés) :

```python
def _pin(refs=(), pnumber='', pname='', x=0, y=0):
    """@brief Fragment <DataPin> ERetroDesign (Pname/Pnumber optionnels, comme les vrais fichiers)."""
    node_l = ''.join(f'<string>{r}</string>' for r in refs)
    morceaux = ['    <DataPin>']
    if pname:
        morceaux.append(f'      <Pname>{pname}</Pname>')
    if pnumber:
        morceaux.append(f'      <Pnumber>{pnumber}</Pnumber>')
    morceaux.append(f'      <NodeL>{node_l}</NodeL>')
    morceaux.append(f'      <Pin><X>{x}</X><Y>{y}</Y></Pin>')
    morceaux.append('    </DataPin>')
    return '\n'.join(morceaux)


def _polygon(points):
    """@brief Fragment <datapolygon> ERetroDesign — un point par élément."""
    pts = ''.join(
        f'<DataPolygon><point><X>{x}</X><Y>{y}</Y></point></DataPolygon>'
        for x, y in points)
    return f'<datapolygon>{pts}</datapolygon>'
```

(`_item` construit déjà `<datapolygon>{...}</datapolygon>` VIDE en dur —
remplacer cette ligne fixe par un paramètre `polygon_xml=''` par défaut, pour
pouvoir y injecter `_polygon(...)` sans dupliquer `_item`.)

```python
def test_import_puce_catch_all_garde_contour_et_broches_reelles():
    # 4 broches reelles sur les cotes gauche/droite d'un rectangle 72x96 —
    # meme forme que le vrai composant A788J (pg carte.xml).
    xml = _boardsch(
        [_item('A788J', pins=[
            _pin(pname='Vin+', x=-36, y=-42), _pin(pname='Vin-', x=-36, y=-6),
            _pin(pname='GND1', x=-36, y=42),
            _pin(pname='Vout', x=36, y=6), _pin(pname='GND2', x=36, y=42),
            _pin(pname='GND2b', x=36, y=-42),
        ], polygon_xml=_polygon([(-36, -48), (-36, 48), (36, 48), (36, -48)]))],
        [],
    )
    comps = _lire(xml)
    u = next(c for c in comps if c.type == 'U')
    assert set(u.pins) == {'Vin+', 'Vin-', 'GND1', 'Vout', 'GND2', 'GND2b'}
    assert u.primitives is not None and len(u.primitives) >= 1
    assert u.pinout is not None
    assert set(u.pinout) == set(u.pins)
    cote, dec = u.pinout['Vin+']
    assert cote == 'L'


def test_import_inconnu_garde_aussi_le_contour():
    xml = _boardsch(
        [_item('transfo', pins=[_pin(x=-20, y=-10), _pin(x=-20, y=10),
                                _pin(x=20, y=-10), _pin(x=20, y=10)],
               polygon_xml=_polygon([(-20, -20), (-20, 20), (20, 20), (20, -20)]))],
        [],
    )
    comps = _lire(xml)
    x = next(c for c in comps if c.type == 'X')
    assert x.primitives is not None
    assert x.pinout is not None and len(x.pinout) == 4


def test_import_resistance_plan_nomme_sans_forme_reelle():
    # Non-regression : un type a PLAN NOMME (R) reste hors perimetre --
    # primitives/pinout absents, comportement generique inchange.
    xml = _boardsch(
        [_item('resistance trad', value='1k',
               pins=[_pin(refs=['A']), _pin()])],
        [],
    )
    comps = _lire(xml)
    r = next(c for c in comps if c.type == 'R')
    assert r.primitives is None
    assert r.pinout is None
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro.py -k "catch_all or inconnu_garde or plan_nomme_sans" -v`
Attendu : `AttributeError: 'Composant' object has no attribute 'primitives'`
(ou `polygon_xml` inattendu tant que `_item` n'a pas été étendu).

- [ ] **Step 3 : implémenter**

`circuit_analyzer/composant.py`, dans la dataclass `Composant`, juste après
le champ `boite_ic: bool = False` (`l.124`) :

```python
    # Contour reel (lignes/arcs/polygones) capture a l'import, uniquement
    # pour les types catch-all sans symbole dedie (U a plan vide, X) --
    # spec 2026-08-07. None = comportement generique inchange.
    primitives: list | None = None
    # Brochage reel {nom: (cote, decalage)}, meme format que CompInst.pinout
    # (spec 2026-07-23) -- toujours renseigne EN MEME TEMPS que primitives.
    pinout: dict | None = None
```

`tests/test_eretro.py`, `_item()` : remplacer la ligne fixe
`f'    <datasegment>{segs_xml}</datasegment>\n'` — NON, ne pas toucher les
segments. Ajouter un paramètre `polygon_xml=''` et l'insérer à la place du
`<datapolygon></datapolygon>` vide actuel :

```python
def _item(name, value='', pins=(), comp_id=0, typ=None, segments=(),
          nb_arcs=0, polygon_xml=''):
    ...
    return (f'  <DataItem>\n'
            f'    <Name>{name}</Name><value>{value}</value>\n'
            f'    {polygon_xml or "<datapolygon></datapolygon>"}\n'
            f'    <datasegment>{segs_xml}</datasegment>\n'
            f'    <dataarc>{arcs_xml}</dataarc>\n'
            f'    <datapin>\n' + '\n'.join(pins) + '\n    </datapin>\n'
            f'    <id>{comp_id}</id>{typ_xml}\n'
            f'  </DataItem>')
```

`circuit_analyzer/xml.py` : ajouter l'import en tête (à côté des imports
existants de `eretro`/`eretro_symboles`) :

```python
from circuit_analyzer import eretro_lib
```

Dans la boucle `_reconnaitre` (fonction où vivent les branches `boite_ic` et
`correspondance is None`, autour de `l.1656-1680`), capturer le contour réel
**avant** la construction de `broches` — l'élément XML brut est déjà
disponible via `elem['xml']` (stocké à la construction de `elements[idx]`,
`l.1404`) :

```python
        boite_ic = False
        if (correspondance is None and elem.get('puce') is None
                and nom.strip() and len(elem['pins']) >= 6):
            correspondance, boite_ic = ('U', {}), True

        def _forme_et_brochage_reels():
            """Capture le contour/brochage reel via le meme parseur que la
            bibliotheque (`eretro_lib._entree_depuis_dataitem`), ou (None, None)
            si le symbole n'a ni geometrie ni broche exploitable."""
            try:
                _prefix, _entree = eretro_lib._entree_depuis_dataitem(elem['xml'])
            except ValueError:
                return None, None
            if not _entree.get('primitives'):
                return None, None
            return _entree['primitives'], {n: tuple(cd) for n, cd in _entree['brochage'].items()}

        if correspondance is None:
            ref = generer_ref('X', elem)
            cid_vers_ref[cid] = ref
            broches = {}
            for pidx, info_b in enumerate(elem['pins']):
                net = broche_vers_net.get((cid, pidx), 'NC')
                broches[str(pidx + 1)] = net
            forme_reelle, brochage_reel = _forme_et_brochage_reels()
            composants.append(Component(ref=ref, type='X', pins=broches, value=elem['value'],
                                        primitives=forme_reelle, pinout=brochage_reel))
            composants.warnings.append(
                f"Composant inconnu '{nom}' (id={cid}) → gardé comme {ref} (type X)"
            )
            continue
```

Puis, au site de construction du `Component` du cas général — EXACTEMENT
(vérifié en lisant le fichier, `l.1732-1734`) :

```python
        composants.append(Component(ref=ref, type=type_prefix, pins=broches,
                                    value=valeur, par_forme=par_forme,
                                    boite_ic=boite_ic))
```

— insérer la capture juste avant cet appel, gardée par la valeur FINALE de
`boite_ic` (celle-ci vient d'être remise à jour deux lignes plus haut,
`l.1724-1725` : `if type_prefix == 'J' or boite_ic: boite_ic = True` — donc
un connecteur `J` profite aussi du contour réel, cohérent avec le
commentaire déjà présent qui les traite comme le même cas : « Boîte neutre
étiquetée : connecteur J et IC catch-all hors catalogue ») :

```python
        forme_reelle, brochage_reel = ((None, None) if not boite_ic
                                       else _forme_et_brochage_reels())
        composants.append(Component(ref=ref, type=type_prefix, pins=broches,
                                    value=valeur, par_forme=par_forme,
                                    boite_ic=boite_ic,
                                    primitives=forme_reelle, pinout=brochage_reel))
```

(Seule cette ligne `composants.append(...)` change ; les ~30 lignes qui la
précèdent dans la fonction — calcul de `manquantes`, `valeur`, décodage
résistance — restent inchangées.)

**Nommage cohérent :** `_entree_depuis_dataitem` nomme chaque broche par
`Pname or Pnumber or str(i+1)` (`eretro_lib.py:432`) — EXACTEMENT la même
priorité que `broche_lib = plan.get(pnom, pnom)` avec `plan={}` (qui renvoie
`pnom`) pour `boite_ic`, et la même que `str(pidx+1)` pour le cas `X` non
reconnu (puisque `_entree_depuis_dataitem` retombe aussi sur `str(i+1)`
quand aucun nom n'est présent). Les clés de `pinout` correspondent donc
toujours exactement aux clés de `pins` — vérifié par les tests ci-dessus
(`set(u.pinout) == set(u.pins)`).

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro.py -v`
Attendu : tous les tests passent, y compris les 3 nouveaux et les existants
(`test_import_inconnu_reste_boite_x` etc., non modifiés) inchangés.

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/composant.py circuit_analyzer/xml.py tests/test_eretro.py
git commit -m "feat(interop): capture le contour et le brochage reels des puces catch-all a l'import"
```

---

### Task 2 : `build_from_components` utilise le brochage réel

**Files:**
- Modify: `gui/schematic_io.py` (`build_from_components`, `l.109-190`)
- Test: `tests/test_schematic_io.py`

**Interfaces consommées :** `Composant.primitives`/`Composant.pinout`
(Task 1). `geometrie_libre` (`gui/schematic_symbols.py`, déjà importable —
vérifier l'import en tête de `schematic_io.py`, l'ajouter sinon).

**Interfaces produites :** les dict composants du document `.circ` retourné
portent désormais `"forme_primitives"`/`"pinout"` (mêmes clés que celles déjà
lues par `SchematicEditor.load_dict`) quand `comp.primitives`/`comp.pinout`
sont renseignés.

- [ ] **Step 1 : écrire les tests qui échouent**

`tests/test_schematic_io.py` teste `build_from_components` avec `COMP_DEFS`
(la vraie table de l'éditeur, déjà importée `l.9`) et un double léger `_Comp`
(`l.19-24`, SEULEMENT `ref/type/pins/value`). `test_import_broche_inconnue_est_comptee`
(`l.50-57`) montre déjà qu'un `U` avec des broches hors du plan générique
(`IN+/IN-/OUT`) se fait compter en `dropped_pins` — exactement le bug que
Task 2 corrige quand le composant porte un brochage réel. Étendre `_Comp`
(additif, tous les appels existants sans les deux nouveaux champs restent
valides) et ajouter :

```python
@dataclass
class _Comp:
    ref: str
    type: str
    pins: dict
    value: str = ""
    primitives: list | None = None
    pinout: dict | None = None


def test_build_garde_le_brochage_reel_dune_puce_catch_all():
    """Meme scenario que test_import_broche_inconnue_est_comptee, mais avec
    un brochage reel : les broches ne doivent plus etre droppees."""
    comp = _Comp("U1", "U",
                 {"Vin+": "N1", "Vin-": "N2", "GND1": "GND"}, "",
                 primitives=[("polygon", [(-36, -48), (-36, 48), (36, 48), (36, -48)], False)],
                 pinout={"Vin+": ("L", -42), "Vin-": ("L", -6), "GND1": ("L", 42)})
    doc = build_from_components([comp], COMP_DEFS)
    c = doc["components"][0]
    assert c["type"] == "U"
    assert c["forme_primitives"] == comp.primitives
    assert c["pinout"] == {"Vin+": ["L", -42], "Vin-": ["L", -6], "GND1": ["L", 42]}
    assert doc["_report"]["dropped_pins"] == 0


def test_build_sans_brochage_reel_comportement_inchange():
    """Non-regression explicite : test_import_broche_inconnue_est_comptee
    doit encore dropper V+/V- quand AUCUN brochage reel n'est fourni."""
    comp = _Comp("U1", "U",
                 {"IN+": "A", "IN-": "B", "OUT": "O", "V+": "VCC", "V-": "GND"})
    doc = build_from_components([comp], COMP_DEFS)
    assert doc["_report"]["dropped_pins"] == 2
    assert "forme_primitives" not in doc["components"][0]
    assert "pinout" not in doc["components"][0]
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_schematic_io.py -k "brochage_reel_dune_puce or sans_brochage_reel" -v`
Attendu : `TypeError: __init__() got an unexpected keyword argument 'primitives'`
(le double `_Comp` local n'a pas encore les deux champs).

- [ ] **Step 3 : implémenter**

En tête de `gui/schematic_io.py`, ajouter l'import (à côté des imports
existants) :

```python
from gui.schematic_symbols import geometrie_libre
```

Dans `build_from_components`, remplacer la boucle de placement et la
construction de `components.append(...)` (`l.137-147`) pour transporter
`primitives`/`pinout` :

```python
    for i, comp in enumerate(placeable):
        row, col = divmod(i, cols)
        cx = _snap(_ORIGIN[0] + col * _COL_DX)
        cy = _snap(_ORIGIN[1] + row * _ROW_DY)
        cid = next_id
        next_id += 1
        counters[comp.type] = max(counters.get(comp.type, 0),
                                  _ref_number(comp.ref, comp.type))
        entry = {"id": cid, "ref": comp.ref, "type": comp.type,
                "value": comp.value, "cx": cx, "cy": cy, "rotation": 0}
        if getattr(comp, "pinout", None):
            entry["pinout"] = {n: list(v) for n, v in comp.pinout.items()}
        if getattr(comp, "primitives", None):
            entry["forme_primitives"] = comp.primitives
        components.append(entry)
        placed.append((cid, comp, cx, cy))
```

Puis, dans la boucle d'indexation des broches câblables (`l.150-158`),
utiliser le brochage réel quand il existe au lieu du `defs[comp.type]["pins"]`
générique :

```python
    net_pins: dict = {}
    for cid, comp, cx, cy in placed:
        if getattr(comp, "pinout", None):
            avail = geometrie_libre(comp.pinout)["pins"]
        else:
            avail = defs[comp.type]["pins"]
        for pin, net in comp.pins.items():
            if pin not in avail:
                report["dropped_pins"] += 1
                continue
            net_pins.setdefault(net, []).append((cid, pin, cx, cy, comp.type))
```

Et dans la boucle de création des fils GND/VCC (`l.161-175`), même bascule
pour lire la position de la broche (`pdx, pdy`) :

```python
    wires: list = []
    for net, plist in net_pins.items():
        if is_gnd(net) or is_power(net):
            sym_type = "GND" if is_gnd(net) else "VCC"
            for cid, pin, cx, cy, ctype in plist:
                src = next(c for c in placed if c[0] == cid)[1]
                if getattr(src, "pinout", None):
                    pdx, pdy = geometrie_libre(src.pinout)["pins"][pin]
                else:
                    pdx, pdy = defs[ctype]["pins"][pin]
                px, py = cx + pdx, cy + pdy
                ...
```

(Le reste de la boucle GND/VCC et la boucle `else` de câblage direct
n'utilisent pas les positions de broches — inchangés.)

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_schematic_io.py -v`
Attendu : tout vert, y compris les tests existants (aucun composant sans
`pinout` ne change de comportement — `getattr(comp, "pinout", None)` est
`None` pour eux, branche `else` inchangée).

- [ ] **Step 5 : commit**

```bash
git add gui/schematic_io.py tests/test_schematic_io.py
git commit -m "fix(editeur): l'ouverture d'une carte cable le vrai brochage d'une puce catch-all"
```

---

### Task 3 : `CompInst.forme_primitives` — rendu et persistance `.circ`

**Files:**
- Modify: `gui/schematic_editor.py` (`CompInst`, `_geom`, `load_dict`, `_add_comp`, `_copy`/`_paste`/`_duplicate`)
- Modify: `gui/schematic_io.py` (`editor_to_dict`)
- Test: `tests/test_brochage_libre.py`

**Interfaces consommées :** le document `.circ` produit par Task 2 porte
déjà `"forme_primitives"`/`"pinout"` sur les composants concernés — ce sont
les MÊMES clés que `load_dict` doit lire.

**Interfaces produites :** `CompInst.forme_primitives: list | None = None`.

- [ ] **Step 1 : écrire les tests qui échouent**

Ajouter à `tests/test_brochage_libre.py` (réutilise `_place`/`editeur` déjà
définis dans ce fichier) :

```python
def test_geom_combine_pinout_et_forme_reelle(editeur):
    c = _place(editeur, 'X', 200, 200)
    c.pinout = {'A': ('L', 0), 'B': ('R', 0)}
    c.forme_primitives = [('polygon', [(-10, -10), (-10, 10), (10, 10), (10, -10)], False)]
    editeur._invalider_geom()
    d = editeur._geom(c)
    assert set(d['pins']) == {'A', 'B'}
    assert d.get('primitives') == c.forme_primitives


def test_round_trip_circ_conserve_la_forme_reelle(editeur):
    c = _place(editeur, 'X', 200, 200)
    c.pinout = {'1': ('L', 0)}
    c.forme_primitives = [('polygon', [(-5, -5), (-5, 5), (5, 5), (5, -5)], False)]
    editeur._invalider_geom()
    editeur.load_dict(editeur.to_dict())
    r = next(x for x in editeur._comps.values() if x.comp_type == 'X')
    assert r.forme_primitives == [('polygon', [(-5, -5), (-5, 5), (5, 5), (5, -5)], False)]


def test_circ_sans_forme_reelle_se_relit(editeur):
    _place(editeur, 'R', 200, 200)
    d = editeur.to_dict()
    for comp in d['components']:
        comp.pop('forme_primitives', None)
    editeur.load_dict(d)
    assert all(c.forme_primitives is None for c in editeur._comps.values())
```

(`editeur.to_dict()` : vérifier le nom exact de la méthode publique de
sérialisation sur `SchematicEditor` dans `gui/schematic_editor.py` — d'après
le plan de brochage libre déjà livré, elle existe et enveloppe
`schematic_io.editor_to_dict(self._comps, self._wires, ...)`.)

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_brochage_libre.py -k "forme_reelle" -v`
Attendu : `TypeError: __init__() got an unexpected keyword argument 'forme_primitives'`
(ou `AttributeError` selon le test).

- [ ] **Step 3 : implémenter**

`gui/schematic_editor.py`, dataclass `CompInst` (`l.199-211`), après
`pinout` :

```python
    # Contour reel (import catch-all, choix bibliotheque, ou dessine a la
    # main) : liste de primitives ou None. Purement ADDITIF au rendu -- ne
    # remplace jamais `pinout` (spec 2026-08-07).
    forme_primitives: list | None = None
```

`_geom` (`l.735-754`), combiner les deux au lieu de ne gérer que `pinout` :

```python
    def _geom(self, comp: CompInst) -> dict:
        if comp.pinout is None and not comp.forme_primitives:
            return self._defs[comp.comp_type]
        d = self._geom_cache.get(comp.id)
        if d is None:
            pinout = comp.pinout or {}
            d = geometrie_libre(pinout)
            base = self._defs.get(comp.comp_type)
            if base:
                d["color"] = base["color"]
            if comp.forme_primitives:
                d["primitives"] = comp.forme_primitives
            self._geom_cache[comp.id] = d
        return d
```

`load_dict` (`l.1671-1701`), lire `forme_primitives` en plus de `pinout` :

```python
            po = c.get("pinout")
            ci = CompInst(int(c["id"]), c["ref"], t, c.get("value", ""),
                          int(c["cx"]), int(c["cy"]), int(c.get("rotation", 0)),
                          pinout=({n: tuple(v) for n, v in po.items()}
                                  if po is not None else None),
                          forme_primitives=c.get("forme_primitives"))
            new_comps[ci.id] = ci
```

`gui/schematic_io.py::editor_to_dict` (`l.36-46`), sérialiser le champ en
plus de `pinout` (même style additif, `getattr` pour les doubles de test
légers) :

```python
            {"id": c.id, "ref": c.ref, "type": c.comp_type, "value": c.value,
             "cx": c.cx, "cy": c.cy, "rotation": c.rotation,
             **({"pinout": {n: list(v) for n, v in pinout.items()}}
                if (pinout := getattr(c, "pinout", None)) is not None else {}),
             **({"forme_primitives": fp}
                if (fp := getattr(c, "forme_primitives", None)) else {})}
            for c in comps.values()
```

`_add_comp` (`l.1301-1330`), nouveau paramètre optionnel, pour que
copier/coller/dupliquer (qui l'appellent) puissent le transporter :

```python
    def _add_comp(self, comp_type: str, value: str, rotation: int,
                  wx: int, wy: int, pinout: dict | None = None,
                  forme_primitives: list | None = None
                  ) -> Optional['CompInst']:
        if comp_type not in self._defs:
            return None
        tipo, _ = type_reel(comp_type)
        n = self._counters.get(tipo, 0) + 1
        self._counters[tipo] = n
        ref = f"{tipo}{n}" if tipo not in ("GND", "VCC") else tipo
        comp = CompInst(self._next_id, ref, comp_type, value, wx, wy, rotation,
                        pinout=copy.deepcopy(pinout),
                        forme_primitives=copy.deepcopy(forme_primitives))
        self._next_id += 1
        self._comps[comp.id] = comp
        self._draw_comp(comp)
        self._deselect()
        self._select(comp.id)
        return comp
```

Dans `_copy`/`_paste`/`_duplicate` (autour de `l.1332-1366`), ajouter
`"forme_primitives": comp.forme_primitives` au clipboard dict à côté de
`"pinout"`, et faire suivre `self._clipboard.get("forme_primitives")` /
`src.forme_primitives` dans les appels à `_add_comp` correspondants (même
motif que `pinout`, une ligne de plus à chaque site).

- [ ] **Step 4 : vérifier le vert + non-régression**

Run : `PYTHONUTF8=1 python -m pytest tests/test_brochage_libre.py tests/test_schematic_editor.py tests/test_schematic_io.py -v`
Attendu : tout vert.

- [ ] **Step 5 : commit**

```bash
git add gui/schematic_editor.py gui/schematic_io.py tests/test_brochage_libre.py
git commit -m "feat(editeur): un composant pose peut porter son contour reel (forme_primitives)"
```

---

### Task 4 : Export BoardSCH — contour et brochage réels prioritaires

**Files:**
- Modify: `circuit_analyzer/xml.py` (`_Comp`, `_Generateur.ajouter`, `_Generateur._idx_broche`, `_Generateur._xml_composant`)
- Test: `tests/test_xml_generator.py`

**Interfaces consommées :** `eretro_lib._primitives_vers_xml(prims, abs_pt)`
(déjà écrite, réutilisée telle quelle).

**Interfaces produites :** `_Generateur.ajouter(..., primitives=None, pinout=None)`.

- [ ] **Step 1 : écrire les tests qui échouent**

`tests/test_xml_generator.py` mélange deux pipelines : les imports en tête
de fichier (`circuit_analyzer.xml_generator`, `.xml_parser`, `.parser`,
`.graph_builder`, `.matcher`) sont un ANCIEN pipeline séparé, non concerné
ici. Les tests de `generer_xml`/`Composant` (ceux qui nous concernent, ex.
`l.518-527`) importent `circuit_analyzer.xml`/`circuit_analyzer.composant`
EN LOCAL dans chaque fonction de test — même style à reprendre ici, avec en
plus l'import explicite de `_Generateur` (classe interne, jamais testée
directement jusqu'ici mais rien ne l'empêche — même module) :

```python
def test_generateur_ecrit_le_contour_reel_dune_instance():
    from circuit_analyzer.xml import _Generateur
    gen = _Generateur()
    cid = gen.ajouter('U', 'NE555', x=100, y=100,
                      primitives=[('polygon', [(-36, -48), (-36, 48), (36, 48), (36, -48)], False)],
                      pinout={'Vin+': ('L', -42), 'GND1': ('L', 42)})
    xml = gen.vers_xml()
    assert '<DataPolygon>' in xml
    assert '<X>-36</X><Y>-48</Y>' in xml or '-36' in xml  # contour reel present
    assert 'Vin+' in xml and 'GND1' in xml


def test_generateur_sans_contour_reel_comportement_inchange():
    from circuit_analyzer.xml import _Generateur
    gen = _Generateur()
    gen.ajouter('Résistance', '1k', x=100, y=100)
    xml = gen.vers_xml()
    assert '<Name>Résistance</Name>' in xml
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k "contour_reel" -v`
Attendu : `TypeError: ajouter() got an unexpected keyword argument 'primitives'`.

- [ ] **Step 3 : implémenter**

En tête de `circuit_analyzer/xml.py`, ajouter (à côté des autres imports
`gui.schematic_symbols`-adjacents — vérifier si un import similaire existe
déjà avant d'en ajouter un second) :

```python
from circuit_analyzer.eretro_lib import _primitives_vers_xml
from gui.schematic_symbols import geometrie_libre
```

`_Comp` (`l.440-442`), deux champs de plus :

```python
@dataclass
class _Comp:
    """@brief Composant placé sur le schéma (id, nom de forme, valeur, position, forme)."""
    cid: int; name: str; value: str; x: int; y: int; angle: int = 0; shape: str = ""; group_id: int = 0; ref: str = ""
    primitives: list | None = None
    pinout: dict | None = None
```

`_Generateur.ajouter` (`l.459-474`), transporter les deux nouveaux
paramètres :

```python
    def ajouter(self, nom, valeur="", x=0, y=0, angle=0, forme="", group_id=0,
               ref="", primitives=None, pinout=None) -> int:
        cid = len(self._comps)
        self._comps.append(_Comp(cid, nom, valeur, x, y, angle, forme, group_id,
                                 ref=ref, primitives=primitives, pinout=pinout))
        return cid
```

`_idx_broche` (`l.559-573`), brochage réel prioritaire :

```python
    def _idx_broche(self, cid, nom_broche) -> int:
        comp = self._comps[cid]
        if comp.pinout:
            pins = sorted(comp.pinout)  # ordre stable, arbitraire mais deterministe
            if nom_broche in pins:
                return pins.index(nom_broche)
            raise ValueError(f"Broche '{nom_broche}' introuvable sur composant {cid} ({comp.name}). "
                             f"Disponibles : {pins}")
        forme_nom = _ALIAS.get(self._comps[cid].name, self._comps[cid].name)
        forme = _FORME.get(forme_nom, {})
        broches = forme.get("pins", {})
        if nom_broche not in broches:
            raise ValueError(f"Broche '{nom_broche}' introuvable sur composant {cid} ({self._comps[cid].name}). "
                             f"Disponibles : {list(broches.keys())}")
        return broches[nom_broche][2]
```

`_xml_composant` (`l.575-618`), contour et broches réels prioritaires :

```python
    def _xml_composant(self, comp, noeuds_pins) -> str:
        if comp.pinout:
            geo = geometrie_libre(comp.pinout)
            pins_ordonnees = sorted(comp.pinout)
            parties_broches = []
            for pidx, nom_b in enumerate(pins_ordonnees):
                lx, ly = geo["pins"][nom_b]
                refs_noeud = noeuds_pins.get((comp.cid, pidx), [])
                node_l = ''.join(f'<string>{r}</string>' for r in refs_noeud)
                parties_broches.append(f"""      <DataPin>
        <Pname>{nom_b}</Pname><Pnumber>{nom_b}</Pnumber>
        <NodeL>{node_l}</NodeL>
        <Pin><X>{lx}</X><Y>{ly}</Y></Pin>
        <PinGap><X>0</X><Y>0</Y></PinGap><Size>9</Size>
        <Selected>false</Selected><ShowNbTxt>false</ShowNbTxt><ShowNmTxt>false</ShowNmTxt>
        <VltgP>0</VltgP><typ>{ord(nom_b[0]) if nom_b else 0}</typ>
      </DataPin>""")
            tous_refs = []
            for pidx in range(len(pins_ordonnees)):
                tous_refs.extend(noeuds_pins.get((comp.cid, pidx), []))
            pin_cl = ''.join(f'<string>{r}</string>' for r in tous_refs)
            if comp.primitives:
                seg, poly, arc = _primitives_vers_xml(comp.primitives, lambda dx, dy: (int(round(dx)), int(round(dy))))
            else:
                seg, poly, arc = "", "", ""
            typ_val = ord(comp.name[0]) if comp.name and comp.name[0].isascii() else 85
        else:
            cle_forme = comp.shape or comp.name
            nom_forme = _ALIAS.get(cle_forme, cle_forme)
            forme = _FORME.get(nom_forme, {"pins": {}, "polygon": "", "segment": ""})
            broches_info = forme.get("pins", {})
            parties_broches = []
            for nom_b, (lx, ly, pidx) in sorted(broches_info.items(), key=lambda kv: kv[1][2]):
                refs_noeud = noeuds_pins.get((comp.cid, pidx), [])
                node_l = ''.join(f'<string>{r}</string>' for r in refs_noeud)
                parties_broches.append(f"""      <DataPin>
        <Pname>{nom_b}</Pname><Pnumber>{nom_b}</Pnumber>
        <NodeL>{node_l}</NodeL>
        <Pin><X>{lx}</X><Y>{ly}</Y></Pin>
        <PinGap><X>0</X><Y>0</Y></PinGap><Size>9</Size>
        <Selected>false</Selected><ShowNbTxt>false</ShowNbTxt><ShowNmTxt>false</ShowNmTxt>
        <VltgP>0</VltgP><typ>{ord(nom_b[0]) if nom_b else 0}</typ>
      </DataPin>""")
            tous_refs = []
            for pidx in range(len(broches_info)):
                tous_refs.extend(noeuds_pins.get((comp.cid, pidx), []))
            pin_cl = ''.join(f'<string>{r}</string>' for r in tous_refs)
            poly, seg, arc = forme.get("polygon", ""), forme.get("segment", ""), forme.get("arc", "")
            typ_val = _TYP_COMPOSANT.get(nom_forme, ord(nom_forme[0]) if nom_forme and nom_forme[0].isascii() else 82)
        return f"""    <DataItem>
      <Name>{_esc(comp.name)}</Name><Group /><reference>{_esc(comp.ref)}</reference><value>{_esc(comp.value)}</value>
      <datapolygon>{poly}</datapolygon><datasegment>{seg}</datasegment><dataarc>{arc}</dataarc>
      <datapin>
{''.join(parties_broches)}
      </datapin>
      <PinCL>{pin_cl}</PinCL>
      <CtrIem><X>{comp.x}</X><Y>{comp.y}</Y></CtrIem>
      <pgap><X>0</X><Y>0</Y></pgap><TL><X>50</X><Y>25</Y></TL><BR><X>210</X><Y>121</Y></BR>
      <angle>{comp.angle}</angle><id>{comp.cid}</id><GpId>{comp.group_id}</GpId>
      <zmH>1</zmH><zmV>1</zmV><FlipX>0</FlipX><FlipY>0</FlipY>
      <typ>{typ_val}</typ>
      <Bottom>false</Bottom><selected>false</selected><focus>false</focus>
      <Visible>true</Visible><Top>true</Top><Begrp>{_bool_xml(bool(comp.group_id))}</Begrp><freeze>false</freeze>
    </DataItem>"""
```

(La branche `else` est un COPIER-COLLER EXACT du corps actuel de la
fonction — vérifiée non-régressée par `test_generateur_sans_contour_reel_comportement_inchange`.)

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -v`
Attendu : tout vert.

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/xml.py tests/test_xml_generator.py
git commit -m "feat(interop): l'export du schema ecrit le vrai contour d'une instance quand il existe"
```

---

### Task 5 : Relier bout en bout — `generer_xml` et `exporter_composants`

**Files:**
- Modify: `circuit_analyzer/xml.py` (`generer_xml`, l'appel `gen.ajouter(...)` du composant, autour de `l.1020`)
- Modify: `gui/schematic_editor.py` (`exporter_composants`, `l.1797-1824`)
- Test: `tests/test_xml_generator.py`, `tests/test_schematic_editor.py`

**Interfaces consommées :** `Composant.primitives`/`Composant.pinout`
(Task 1), `_Generateur.ajouter(..., primitives=, pinout=)` (Task 4),
`CompInst.forme_primitives`/`CompInst.pinout` (Task 3).

- [ ] **Step 1 : écrire les tests qui échouent**

`tests/test_xml_generator.py` (même style d'import local que les tests
`generer_xml` existants du fichier, ex. `l.518-527`) :

```python
def test_generer_xml_transporte_le_contour_dun_composant_analyse():
    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml
    comp = Composant(ref='U1', type='U', pins={'Vin+': 'N1', 'GND1': 'GND'}, value='',
                     primitives=[('polygon', [(-36, -48), (-36, 48), (36, 48), (36, -48)], False)],
                     pinout={'Vin+': ('L', -42), 'GND1': ('L', 42)})
    xml = generer_xml([comp])
    assert '<DataPolygon>' in xml
    assert 'Vin+' in xml
```

`tests/test_schematic_editor.py` (Tk, réutilise la fixture `editeur`
existante de ce fichier) :

```python
def test_exporter_composants_transporte_le_contour_reel(editeur):
    c = _place(editeur, 'X', 200, 200)
    c.pinout = {'1': ('L', 0)}
    c.forme_primitives = [('polygon', [(-5, -5), (-5, 5), (5, 5), (5, -5)], False)]
    editeur._invalider_geom()
    comp = next(x for x in editeur.exporter_composants() if x.ref == c.ref)
    assert comp.primitives == c.forme_primitives
    assert comp.pinout == {'1': ('L', 0)}
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py tests/test_schematic_editor.py -k "transporte_le_contour" -v`
Attendu : le composant XML généré n'a pas de `<DataPolygon>`, ou
`comp.primitives` vaut `None` côté éditeur.

- [ ] **Step 3 : implémenter**

`circuit_analyzer/xml.py::generer_xml`, à l'appel `gen.ajouter(nom_forme,
comp.value, x=x, y=y, ref=comp.ref, ...)` (autour de `l.1020`), ajouter les
deux arguments :

```python
        cid = gen.ajouter(nom_forme, comp.value, x=x, y=y, ref=comp.ref,
                          primitives=getattr(comp, "primitives", None),
                          pinout=getattr(comp, "pinout", None))
```

(Ne pas toucher le reste des arguments déjà présents à cet appel —
uniquement ajouter les deux nouveaux.)

`gui/schematic_editor.py::exporter_composants` (`l.1797-1824`), transporter
`forme_primitives`/`pinout` de l'instance vers le `Composant` exporté :

```python
        for comp in real_comps.values():
            pins = self._geom(comp)["pins"]
            t, v = type_reel(comp.comp_type)
            broches = {pn: net_of(f"{comp.id}:{pn}") for pn in pins}
            composants.append(Composant(
                ref=comp.ref, type=t, pins=broches, value=v or comp.value,
                primitives=comp.forme_primitives,
                pinout=comp.pinout))
        return composants
```

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py tests/test_schematic_editor.py -v`
Attendu : tout vert.

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/xml.py gui/schematic_editor.py tests/test_xml_generator.py tests/test_schematic_editor.py
git commit -m "feat(interop): relie l'import, l'editeur et l'export du contour reel bout en bout"
```

---

### Task 6 : Dessin de contour à la main (nouveau composant)

**Files:**
- Modify: `gui/schematic_editor.py` (`_on_right_click`, `_on_click`, `_on_escape`, nouvelles méthodes)
- Test: `tests/test_brochage_libre.py`

**Interfaces produites :**
- `_entrer_dessin_forme(comp_id)` / `_quitter_dessin_forme()`
- `_ajouter_point_forme(comp, wx, wy)`
- `_fermer_forme(comp) -> bool` (`False` si moins de 3 points)
- État `self._state == "shapedraw"`, `self._shapedraw_id`, `self._shapedraw_points: list`

Même famille que le mode `pinedit` déjà livré (spec 2026-07-23,
`_entrer_pinedit`/`_quitter_pinedit`/`l.765-786`) : entrer/sortir, clic pour
agir, Échap pour terminer, undo empilé une seule fois à la fermeture (pas à
chaque point, pour ne pas polluer la pile d'un clic par clic).

- [ ] **Step 1 : écrire les tests qui échouent**

```python
def test_dessiner_une_forme_produit_un_polygone(editeur):
    c = _place(editeur, 'X', 200, 200)
    editeur._entrer_dessin_forme(c.id)
    editeur._ajouter_point_forme(c, 200 - 20, 200 - 20)
    editeur._ajouter_point_forme(c, 200 - 20, 200 + 20)
    editeur._ajouter_point_forme(c, 200 + 20, 200 + 20)
    assert editeur._fermer_forme(c) is True
    assert c.forme_primitives == [('polygon', [(-20, -20), (-20, 20), (20, 20)], False)]
    assert editeur._state == 'idle'


def test_fermer_avec_moins_de_3_points_est_refuse(editeur):
    c = _place(editeur, 'X', 200, 200)
    editeur._entrer_dessin_forme(c.id)
    editeur._ajouter_point_forme(c, 200 - 20, 200 - 20)
    assert editeur._fermer_forme(c) is False
    assert c.forme_primitives is None
    assert editeur._state == 'shapedraw'  # reste en mode dessin


def test_dessin_de_forme_est_annulable(editeur):
    c = _place(editeur, 'X', 200, 200)
    c.forme_primitives = [('polygon', [(0, 0), (0, 1), (1, 1)], False)]
    editeur._entrer_dessin_forme(c.id)
    editeur._ajouter_point_forme(c, 200 - 10, 200 - 10)
    editeur._ajouter_point_forme(c, 200 - 10, 200 + 10)
    editeur._ajouter_point_forme(c, 200 + 10, 200 + 10)
    editeur._fermer_forme(c)
    editeur._undo()
    assert editeur._comps[c.id].forme_primitives == [('polygon', [(0, 0), (0, 1), (1, 1)], False)]


def test_echap_en_dessin_annule_la_forme_en_cours(editeur):
    c = _place(editeur, 'X', 200, 200)
    editeur._entrer_dessin_forme(c.id)
    editeur._ajouter_point_forme(c, 200 - 10, 200 - 10)
    editeur._on_escape()
    assert editeur._state == 'idle'
    assert c.forme_primitives is None
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_brochage_libre.py -k "dessiner_une_forme or fermer_avec or dessin_de_forme_est or echap_en_dessin" -v`
Attendu : `AttributeError: 'SchematicEditor' object has no attribute '_entrer_dessin_forme'`.

- [ ] **Step 3 : implémenter**

Dans `__init__` (à côté de `self._pinedit_id`/`self._pin_selectionnee`,
`l.275-276`) :

```python
        # Dessin de contour (spec 2026-08-07) : composant cible et points
        # accumules (coordonnees MONDE relatives au centre du composant).
        self._shapedraw_id: int | None = None
        self._shapedraw_points: list = []
```

Nouvelles méthodes, à côté de `_entrer_pinedit`/`_quitter_pinedit`
(`l.765-786`) :

```python
    # ── Dessin de contour (mode "shapedraw", spec 2026-08-07) ─────────────────

    def _entrer_dessin_forme(self, comp_id: int):
        """@brief Passe en dessin de contour sur CE composant, clic par clic."""
        if comp_id not in self._comps:
            return
        self._cancel_wiring()
        self._deselect()
        self._state           = "shapedraw"
        self._shapedraw_id     = comp_id
        self._shapedraw_points = []
        self._canvas.configure(cursor="crosshair")
        self._set_status("Clic = point du contour\n"
                         "Revenir au 1er point = fermer\nÉchap = annuler")

    def _quitter_dessin_forme(self):
        """@brief Sort du mode de dessin de contour, sans rien valider."""
        self._canvas.delete("shapedraw")
        self._state           = "idle"
        self._shapedraw_id     = None
        self._shapedraw_points = []
        self._canvas.configure(cursor="")
        self._set_status("Prêt")

    def _ajouter_point_forme(self, comp, wx, wy):
        """@brief Ajoute un point aimanté à la grille au contour en cours."""
        swx, swy = self._snap(wx, wy)
        self._shapedraw_points.append((swx - comp.cx, swy - comp.cy))
        self._dessiner_previsu_forme(comp)

    def _dessiner_previsu_forme(self, comp):
        """@brief Trace les segments déjà posés du contour en cours d'édition."""
        self._canvas.delete("shapedraw")
        pts = self._shapedraw_points
        if len(pts) < 2:
            return
        coords = []
        for dx, dy in pts:
            sx, sy = self._w2s(comp.cx + dx, comp.cy + dy)
            coords.extend([sx, sy])
        self._canvas.create_line(*coords, fill=BLUE, dash=(4, 3), width=2,
                                 tags="shapedraw")

    def _fermer_forme(self, comp) -> bool:
        """@brief Referme le contour en cours (>= 3 points) et l'enregistre.

        @return False si moins de 3 points -- reste en mode dessin, aucune
                mutation (permet à l'appelant de continuer à cliquer).
        """
        if len(self._shapedraw_points) < 3:
            self._set_status("Il faut au moins\n3 points")
            return False
        self._push_undo()
        comp.forme_primitives = [("polygon", list(self._shapedraw_points), False)]
        self._invalider_geom(comp.id)
        self._draw_comp(comp)
        self._quitter_dessin_forme()
        return True
```

Câblage dans `_on_click` (`l.1098-1119`, juste après la branche `pinedit`) :

```python
        if self._state == "shapedraw":
            comp = self._comps.get(self._shapedraw_id)
            if comp is None:
                self._quitter_dessin_forme()
                return
            # Clic proche du 1er point deja pose = fermer le contour.
            if self._shapedraw_points:
                x0, y0 = self._shapedraw_points[0]
                if math.hypot((wx - comp.cx) - x0, (wy - comp.cy) - y0) <= GRID / 2:
                    self._fermer_forme(comp)
                    return
            self._ajouter_point_forme(comp, wx, wy)
            return
```

(`math` est déjà importé en tête du fichier — utilisé par `_dist_point_segment`
existant.)

Dans `_on_escape` (`l.1277-1290`), ajouter la branche AVANT `pinedit` (même
priorité que les autres modes exclusifs) :

```python
    def _on_escape(self, _=None):
        if self._state == "shapedraw":
            self._quitter_dessin_forme()
            return
        if self._state == "pinedit":
            self._quitter_pinedit()
            return
        ...
```

Dans `_on_right_click` (`l.1239-1265`), ajouter l'entrée de menu après
« Éditer broches » :

```python
        m.add_command(label="✎  Dessiner le contour",
                      command=lambda: self._entrer_dessin_forme(comp_id))
```

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_brochage_libre.py tests/test_schematic_editor.py -v`
Attendu : tout vert.

- [ ] **Step 5 : commit**

```bash
git add gui/schematic_editor.py tests/test_brochage_libre.py
git commit -m "feat(editeur): mode de dessin de contour a la main pour un nouveau composant"
```

---

### Task 7 : Suite complète + boucle visuelle + revue finale

- [ ] **Step 1 : suite complète (deux fois)**

```bash
PYTHONUTF8=1 python -m pytest -q
```

Attendu : 0 failed les deux fois (le flake connu
`test_500_portes_sous_budget`, s'il apparaît, se relance isolé — pas un
échec réel de ce chantier). `test_puces_resolution.py` doit rester vert :
son corpus (`circuits_industriels/reel_*.xml`, `ilot_*.xml`) ne passe PAS
par `lire_xml`/`build_from_components` (chemin détection/rendu séparé,
`gui/circuit_viewer.py` + `tools/render_ilots_v2.py`, hors périmètre de ce
chantier) — si un échec apparaît là, investiguer avant de continuer, ne pas
supposer une régression pré-existante sans vérifier (cf. l'incident de
faux-diagnostic du merge précédent).

- [ ] **Step 2 : boucle visuelle** — script scratch (scratchpad, jamais
  committé), 3 scénarios rendus en PNG et RÉELLEMENT inspectés :
  1. Ouvrir un fichier réel contenant un composant catch-all avec forme
     (utiliser une fixture synthétique construite avec les mêmes helpers que
     Task 1 — PAS `CARTE POUR TESTER (VRAI TEST)/`, lecture seule, jamais
     manipulée par un script) → le composant se dessine avec son vrai
     contour et ses vraies broches nommées dans l'éditeur.
  2. Exporter ce même schéma, ré-ouvrir l'export → même contour, mêmes
     broches (aller-retour).
  3. Dessiner un contour à la main sur un nouveau composant → le contour
     dessiné apparaît immédiatement sur le canevas, et l'export du composant
     porte ce même contour.
- [ ] **Step 3 : supprimer PNG et scripts** (jamais committés).
- [ ] **Step 4 : revue** — `superpowers:requesting-code-review` sur la
  branche, puis `superpowers:finishing-a-development-branch`. Rien n'est
  poussé sans accord explicite du boss.

---

## Vérification (bout en bout)

1. **Tests** : `PYTHONUTF8=1 python -m pytest -q` — tout vert.
2. **Non-régression** : tous les tests existants de `test_eretro.py`,
   `test_schematic_io.py`, `test_xml_generator.py`, `test_schematic_editor.py`,
   `test_brochage_libre.py` passent SANS modification de leurs assertions
   (seule exception déjà notée : l'extension additive de `_item`/`_pin` dans
   `test_eretro.py`, qui ne change aucun appel existant).
3. **À la main dans l'app** : ouvrir un fichier réel avec une puce non
   cataloguée → vraie forme + vraies broches. Poser une boîte vierge,
   « Dessiner le contour », cliquer 4 coins, refermer → le composant a sa
   forme. L'exporter vers un `.xml`, le ré-ouvrir → forme et broches
   identiques.
4. **Preuve visuelle** : les 3 PNG de la Task 7, inspectés et décrits.

## Réserves (héritées de la conception, non résolues par ce plan)

1. Le rendu de notre export chez ERetroDesign (côté C#) reste non
   vérifiable depuis ici.
2. La conversion broches réelles → côté+décalage suppose des broches sur les
   4 bords ; aucun exemple de broche flottante au milieu du contour trouvé
   dans les fichiers réels disponibles, donc non couvert.
3. Les types à plan nommé (R/C/D/AOP historique) restent hors périmètre —
   volontairement, cf. section Architecture.
