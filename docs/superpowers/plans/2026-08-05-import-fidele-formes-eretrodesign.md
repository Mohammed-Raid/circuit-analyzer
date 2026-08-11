# Import fidèle des formes de bibliothèque ERetroDesign — Plan d'implémentation

> **Pour l'exécutant :** Exécution via `superpowers:subagent-driven-development`
> (recommandé) ou `superpowers:executing-plans`.

**Spec de référence :** `docs/superpowers/specs/2026-08-05-import-fidele-formes-eretrodesign-design.md`
(commit `5c126c5`).

**Goal :** un composant importé de la bibliothèque partagée ERetroDesign se
dessine dans l'éditeur avec sa vraie forme (polygones/segments/arcs), pas une
boîte générique — sans rien casser pour les types qui n'ont pas de forme
capturée (connecteurs nus, bibliothèques créées avant cette feature).

**Architecture :** une nouvelle fonction pure `primitives_depuis_dataitem`
parse `datasegment`/`dataarc`/`datapolygon` d'un `<DataItem>` en primitives
d'édition (même format que `primitives()` sait déjà dispatcher).
`circuit_analyzer/eretro_lib.py::_entree_depuis_dataitem` l'appelle à l'import
et stocke le résultat (`primitives`) + le XML brut (`xml_source`, réservé à
un chantier futur) sur l'entrée de bibliothèque. `gui/schematic_editor.py`
fait suivre `primitives` jusqu'au def de l'éditeur. `primitives()` retourne
ces primitives directement quand elles existent, sinon le comportement actuel
(boîte générique `TYPE_LIBRE`) est inchangé à l'identique.

**Tech Stack :** Python 3.11, Tkinter/customtkinter, pytest. Aucune nouvelle
dépendance (`xml.etree.ElementTree` et `math`, stdlib, déjà utilisés ailleurs
dans le projet).

## Global Constraints

- Commits en **français**, **jamais** de footer `Co-Authored-By: Claude` ni
  `Generated with Claude Code`.
- **Jamais `git add -A`** : fichiers ajoutés un par un.
- **Ne jamais committer** `custom_circuits.json` ni `component_library.json`.
- `ERetroDesign/`, `CARTE POUR TESTER (VRAI TEST)/`, `docs.rar`, `dist_demo/`,
  `test14.xml` : lecture seule, jamais committés.
- `PYTHONUTF8=1` sur toutes les commandes pytest.
- `schemdraw==0.22` pinné (non concerné directement ici, contrainte globale
  du dépôt).
- Branche `rewrite-simple` ; rien n'est poussé sans accord explicite.
- PNG rendus et inspectés avant tout commit touchant du dessin ; jamais de
  PNG committé.
- Périmètre : uniquement `gui/schematic_editor.py`, `gui/schematic_symbols.py`,
  `circuit_analyzer/eretro_lib.py`. Aucun changement à `detecteur.py` /
  `satellites.py` / `ilots.py` / `drc.py` / `rapport.py` / `circuit_viewer.py` /
  `impedance_schematic.py`.

## Structure des fichiers

| Fichier | Responsabilité ajoutée |
|---|---|
| `gui/schematic_symbols.py` | `primitives_depuis_dataitem()` (parsing pur XML → primitives), `_libelles_broches()` (extrait de `_tr_boite_libre`), court-circuit en tête de `primitives()`. |
| `circuit_analyzer/eretro_lib.py` | `_entree_depuis_dataitem` : capture `entree["primitives"]` et `entree["xml_source"]`. |
| `gui/schematic_editor.py` | `_auto_def` : fait suivre `forme_primitives` jusqu'au def retourné. |
| `tests/test_schematic_symbols.py` | Tests de `primitives_depuis_dataitem`, `_libelles_broches`, dispatch `primitives()` (T1, T2). |
| `tests/test_eretro_lib.py` | Tests de `_entree_depuis_dataitem` (T3). |
| `tests/test_import_fidele_formes.py` | **Créé** — tests éditeur Tk bout en bout (T4). |

---

### Task 1 : `primitives_depuis_dataitem` — parser pur XML → primitives

**Files:**
- Modify: `gui/schematic_symbols.py` (imports en tête + nouvelle fonction, après `def_puce`)
- Test: `tests/test_schematic_symbols.py`

**Interfaces produites :**
- `primitives_depuis_dataitem(xml_texte: str, echelle: float) -> list` —
  liste de primitives `("line", [(x,y),(x,y)], epaisseur)` /
  `("arc", (x0,y0,x1,y1), start_deg, extent_deg)` /
  `("polygon", [(x,y),...], False)`. Jamais d'exception, jamais `None`.

- [ ] **Step 1 : écrire les tests qui échouent**

`tests/test_schematic_symbols.py` n'importe encore ni `pytest` ni `os` :
ajouter `import os` et `import pytest` tout en haut du fichier (avant
`import subprocess`), et étendre l'import existant
`from gui.schematic_symbols import (...)` avec le nouveau nom
`primitives_depuis_dataitem` (ordre alphabétique, comme les noms existants) :

```python
from gui.schematic_symbols import (
    aimanter_bord,
    def_puce,
    est_boite_generique,
    geometrie_libre,
    primitives,
    primitives_depuis_dataitem,
    rotate_pin,
)
```

Puis ajouter en fin de fichier :

```python
def test_primitives_depuis_dataitem_segment_devient_une_ligne():
    xml = ('<DataItem><datasegment><DataSegment>'
           '<Spoint><X>10</X><Y>20</Y></Spoint>'
           '<Epoint><X>30</X><Y>20</Y></Epoint>'
           '</DataSegment></datasegment></DataItem>')
    assert primitives_depuis_dataitem(xml, 1.0) == [
        ("line", [(10.0, 20.0), (30.0, 20.0)], 2)]


def test_primitives_depuis_dataitem_applique_l_echelle():
    xml = ('<DataItem><datasegment><DataSegment>'
           '<Spoint><X>10</X><Y>20</Y></Spoint>'
           '<Epoint><X>30</X><Y>20</Y></Epoint>'
           '</DataSegment></datasegment></DataItem>')
    assert primitives_depuis_dataitem(xml, 0.5) == [
        ("line", [(5.0, 10.0), (15.0, 10.0)], 2)]


def test_primitives_depuis_dataitem_arc_devient_un_arc():
    # Fragment reel (Self.xml de la bibliotheque ERetroDesign).
    xml = ('<DataItem><dataarc><DataArc>'
           '<pCenter><X>0</X><Y>0</Y></pCenter>'
           '<stAngle>-180</stAngle><swAngle>180</swAngle>'
           '<Spoint><X>-16</X><Y>0</Y></Spoint>'
           '<Epoint><X>16</X><Y>0</Y></Epoint>'
           '</DataArc></dataarc></DataItem>')
    assert primitives_depuis_dataitem(xml, 1.0) == [
        ("arc", (-16.0, -16.0, 16.0, 16.0), -180.0, 180.0)]


def test_primitives_depuis_dataitem_arc_de_rayon_nul_ignore():
    xml = ('<DataItem><dataarc><DataArc>'
           '<pCenter><X>5</X><Y>5</Y></pCenter>'
           '<stAngle>0</stAngle><swAngle>90</swAngle>'
           '<Spoint><X>5</X><Y>5</Y></Spoint>'
           '<Epoint><X>5</X><Y>5</Y></Epoint>'
           '</DataArc></dataarc></DataItem>')
    assert primitives_depuis_dataitem(xml, 1.0) == []


def test_primitives_depuis_dataitem_polygone_groupe_en_une_forme_fermee():
    # Fragment reel (AOP.xml) : 3 <DataPolygon>, un point chacun -> 1 triangle.
    xml = ('<DataItem><datapolygon>'
           '<DataPolygon><point><X>52</X><Y>0</Y></point></DataPolygon>'
           '<DataPolygon><point><X>-52</X><Y>-48</Y></point></DataPolygon>'
           '<DataPolygon><point><X>-52</X><Y>48</Y></point></DataPolygon>'
           '</datapolygon></DataItem>')
    assert primitives_depuis_dataitem(xml, 1.0) == [
        ("polygon", [(52.0, 0.0), (-52.0, -48.0), (-52.0, 48.0)], False)]


def test_primitives_depuis_dataitem_polygone_incomplet_ignore():
    xml = ('<DataItem><datapolygon>'
           '<DataPolygon><point><X>0</X><Y>0</Y></point></DataPolygon>'
           '<DataPolygon><point><X>10</X><Y>0</Y></point></DataPolygon>'
           '</datapolygon></DataItem>')
    assert primitives_depuis_dataitem(xml, 1.0) == []


def test_primitives_depuis_dataitem_sans_forme_retourne_vide():
    xml = '<DataItem><datapin><DataPin><Pname>1</Pname></DataPin></datapin></DataItem>'
    assert primitives_depuis_dataitem(xml, 1.0) == []


def test_primitives_depuis_dataitem_xml_invalide_ne_leve_pas():
    assert primitives_depuis_dataitem("pas du xml", 1.0) == []


_DOSSIER_REEL = os.path.join("ERetroDesign", "ERetroDesign", "bin", "Debug",
                             "LibItem", "Lib")


@pytest.mark.skipif(not os.path.isdir(_DOSSIER_REEL), reason="ERetroDesign absent")
@pytest.mark.parametrize("nom,famille", [
    ("AOP.xml", "polygon"),
    ("Self.xml", "arc"),
    ("Diode.xml", "polygon"),
])
def test_vrais_symboles_produisent_la_famille_de_primitive_attendue(nom, famille):
    with open(os.path.join(_DOSSIER_REEL, nom), encoding="utf-8") as f:
        xml = f.read()
    prims = primitives_depuis_dataitem(xml, 1.0)
    assert any(p[0] == famille for p in prims)
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_schematic_symbols.py -q`
Attendu : `ImportError: cannot import name 'primitives_depuis_dataitem'`

- [ ] **Step 3 : implémenter** — dans `gui/schematic_symbols.py`

Ajouter en tête du fichier (après le docstring de module, avant
`from gui.theme import SCHEMA_COLORS`) :

```python
import math
import xml.etree.ElementTree as ET
```

Puis, après `def_puce` (fin de fichier avant la section « Brochage libre »,
ou juste après — l'ordre entre fonctions n'a pas d'importance) :

```python
def primitives_depuis_dataitem(xml_texte: str, echelle: float) -> list:
    """@brief Contour reel d'un <DataItem> ERetroDesign en primitives d'edition.

    Parse datasegment/DataSegment (Spoint/Epoint -> "line"), dataarc/DataArc
    (pCenter/stAngle/swAngle, rayon = distance pCenter->Spoint -> "arc"),
    datapolygon/DataPolygon (points groupes -> un seul "polygon" ferme).
    Mise a l'echelle *echelle* — l'appelant DOIT passer la meme constante
    ECHELLE que celle utilisee pour les broches (eretro_lib.py), jamais une
    valeur cablee en dur ici, sous peine de desaligner pattes et contour.
    Ne leve JAMAIS : XML invalide ou geometrie degeneree -> ignores, jamais
    une exception qui ferait echouer tout l'import du composant.

    @param xml_texte Fragment <DataItem>...</DataItem> (texte).
    @param echelle Facteur d'echelle unites BoardSCH -> unites editeur (=
           eretro_lib.ECHELLE, actuellement 1 : pas de mise a l'echelle).
    @return list[tuple] Primitives ("line"|"arc"|"polygon", ...). Vide si le
            composant n'a ni polygone, ni segment, ni arc exploitable.
    """
    try:
        r = ET.fromstring(xml_texte)
    except ET.ParseError:
        return []
    prims = []
    for s in r.findall("./datasegment/DataSegment"):
        try:
            sp, ep = s.find("Spoint"), s.find("Epoint")
            x1 = float(sp.findtext("X") or 0) * echelle
            y1 = float(sp.findtext("Y") or 0) * echelle
            x2 = float(ep.findtext("X") or 0) * echelle
            y2 = float(ep.findtext("Y") or 0) * echelle
            prims.append(("line", [(x1, y1), (x2, y2)], 2))
        except (AttributeError, ValueError, TypeError):
            continue
    for a in r.findall("./dataarc/DataArc"):
        try:
            c = a.find("pCenter")
            cx = float(c.findtext("X") or 0) * echelle
            cy = float(c.findtext("Y") or 0) * echelle
            sp = a.find("Spoint")
            sx = float(sp.findtext("X") or 0) * echelle
            sy = float(sp.findtext("Y") or 0) * echelle
            rayon = math.hypot(sx - cx, sy - cy)
            if rayon <= 0:
                continue
            debut = float(a.findtext("stAngle") or 0)
            etendue = float(a.findtext("swAngle") or 0)
            prims.append(("arc",
                         (cx - rayon, cy - rayon, cx + rayon, cy + rayon),
                         debut, etendue))
        except (AttributeError, ValueError, TypeError):
            continue
    points = []
    for p in r.findall("./datapolygon/DataPolygon"):
        try:
            pt = p.find("point")
            points.append((float(pt.findtext("X") or 0) * echelle,
                           float(pt.findtext("Y") or 0) * echelle))
        except (AttributeError, ValueError, TypeError):
            continue
    if len(points) >= 3:
        prims.append(("polygon", points, False))
    return prims
```

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_schematic_symbols.py -q` → PASS

- [ ] **Step 5 : commit**

```bash
git add gui/schematic_symbols.py tests/test_schematic_symbols.py
git commit -m "feat(editeur): parse le vrai contour d'un DataItem ERetroDesign en primitives"
```

---

### Task 2 : Brancher les primitives dans le dispatch de rendu

**Files:**
- Modify: `gui/schematic_symbols.py` (`_tr_boite_libre`, `primitives()`)
- Test: `tests/test_schematic_symbols.py`

**Interfaces produites :**
- `_libelles_broches(defn) -> list` — libellés texte, un par broche, factorisé
  depuis `_tr_boite_libre`.
- `primitives()` : si `defn.get("primitives")` est non vide, les retourne
  (+ labels), en court-circuitant `_TRACEURS`/`TYPE_LIBRE`.

**Contexte :** `est_boite_generique(comp_type)` renvoie `True` pour tout type
importé (jamais `"D"`, jamais dans `_TRACEURS`) — ça supprime le libellé de
broche générique dessiné ailleurs et suppose que le traceur dessine
lui-même ses labels, comme le fait déjà `_tr_boite_libre`. Sans
`_libelles_broches` appliqué à la nouvelle branche, un composant à forme
réelle importée n'aurait AUCUN libellé de broche.

- [ ] **Step 1 : écrire les tests qui échouent**

Ces tests utilisent `TYPE_LIBRE`, pas encore importé (Task 1 ne l'a pas
ajouté — seul `primitives_depuis_dataitem` l'était, pour rester lint-propre
tant qu'il n'était pas utilisé) : ajouter `TYPE_LIBRE` à l'import existant
`from gui.schematic_symbols import (...)` (ordre alphabétique, avant
`aimanter_bord`). Puis ajouter à `tests/test_schematic_symbols.py` :

```python
def test_primitives_utilise_les_primitives_de_la_def_si_presentes():
    defn = {"w": 80, "h": 60, "pins": {"1": (-40, 0)}, "cotes": {"1": "L"},
            "primitives": [("polygon", [(0, -10), (10, 10), (-10, 10)], False)]}
    prims = primitives("PERSO", defn, 0)
    assert ("polygon", [(0, -10), (10, 10), (-10, 10)], False) in prims
    # Piege identifie en auto-revision du spec : le libelle de broche standard
    # doit etre ajoute par-dessus la vraie forme, sinon il disparait.
    assert any(p[0] == "text" and p[2] == "1" for p in prims)


def test_primitives_repli_boite_libre_si_pas_de_primitives():
    defn = {"w": 80, "h": 60, "pins": {"1": (-40, 0)}, "cotes": {"1": "L"}}
    prims = primitives(TYPE_LIBRE, defn, 0)
    # Non-regression explicite : la boite generique reste un rectangle 4 sommets.
    assert prims[0] == ("polygon", [(-40, -30), (40, -30), (40, 30), (-40, 30)], False)


def test_primitives_avec_primitives_subissent_la_rotation():
    defn = {"w": 80, "h": 60, "pins": {}, "cotes": {},
            "primitives": [("line", [(0, 0), (10, 5)], 2)]}
    prims = primitives("PERSO", defn, 90)
    ligne = next(p for p in prims if p[0] == "line")
    assert ligne[1] == [rotate_pin(0, 0, 90), rotate_pin(10, 5, 90)]
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_schematic_symbols.py -q`
Attendu : `test_primitives_utilise_les_primitives_de_la_def_si_presentes` et
`test_primitives_avec_primitives_subissent_la_rotation` échouent (les
primitives ne sont pas retournées, aucun texte de libellé) ;
`test_primitives_repli_boite_libre_si_pas_de_primitives` doit déjà passer
(non-régression du comportement actuel — le confirmer avant de continuer).

- [ ] **Step 3 : implémenter** — dans `gui/schematic_symbols.py`

Remplacer `_tr_boite_libre` par (extraire la boucle de labels dans un nouveau
helper `_libelles_broches`, appelé aussi par la nouvelle branche de
`primitives()`) :

```python
def _libelles_broches(defn):
    """@brief Un libelle texte par broche, positionne selon son cote (defn["cotes"]).

    Factorise depuis `_tr_boite_libre` : reutilise par tout traceur qui a
    besoin des labels de broches standard sans les redessiner lui-meme (forme
    reelle importee d'ERetroDesign, spec 2026-08-05).
    """
    prims = []
    for pn, (px, py) in defn["pins"].items():
        cote = (defn.get("cotes") or {}).get(pn, "L")
        fonction = (defn.get("fonctions") or {}).get(pn, "")
        libelle = f"{pn} {fonction}".strip()
        if cote in ("L", "R"):
            ancre = "w" if cote == "L" else "e"
            tx, ty = px + (6 if cote == "L" else -6), py
        else:
            ancre = "center"
            tx, ty = px, py + (10 if cote == "T" else -10)
        prims.append(("text", (tx, ty), libelle, 7, ancre))
    return prims


def _tr_boite_libre(defn):
    """@brief Boite au brochage libre : broches sur les 4 bords (spec 2026-07-23).

    `_tr_boite` ne sait placer que des broches gauche/droite (il tranche le cote
    sur `px > 0`), d'ou ce traceur separe qui lit `defn["cotes"]` et oriente le
    libelle en consequence. Le laisser separe protege le rendu DIP des puces
    catalogue, dont depend tout l'import ERetroDesign.
    """
    w2, h2 = defn["w"] // 2, defn["h"] // 2
    prims = [("polygon", [(-w2, -h2), (w2, -h2), (w2, h2), (-w2, h2)], False)]
    prims.extend(_libelles_broches(defn))
    return prims
```

Puis modifier `primitives()` (ajouter la branche AVANT le test `TYPE_LIBRE`
existant, tout le reste de la fonction inchangé) :

```python
def primitives(comp_type, defn, rotation, value=""):
    """@brief Primitives monde du symbole, rotation appliquee.

    Types traces : table _TRACEURS. Un type avec une forme importee
    (defn["primitives"], spec 2026-08-05) court-circuite le dispatch. Tout
    autre type (perso, puce catalogue) -> boite generique a encoche.
    """
    if defn.get("primitives"):
        prims = list(defn["primitives"]) + _libelles_broches(defn)
    elif comp_type == TYPE_LIBRE:
        prims = _tr_boite_libre(defn)
    elif comp_type == "D":
        prims = _tr_d(defn, value)
    elif comp_type in _TRACEURS:
        prims = _TRACEURS[comp_type](defn)
    else:
        prims = _tr_boite(defn)
    return _rot_prims(prims, rotation)
```

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_schematic_symbols.py -q` → PASS

- [ ] **Step 5 : commit**

```bash
git add gui/schematic_symbols.py tests/test_schematic_symbols.py
git commit -m "feat(editeur): dessine la vraie forme importee quand elle existe, libelles conserves"
```

---

### Task 3 : Capturer la forme à l'import (`eretro_lib.py`)

**Files:**
- Modify: `circuit_analyzer/eretro_lib.py` (imports + `_entree_depuis_dataitem`)
- Test: `tests/test_eretro_lib.py`

**Interfaces produites :**
- `entree["primitives"]` (toujours présent, liste — vide si rien d'exploitable)
- `entree["xml_source"]` (toujours présent, texte du fragment `<DataItem>` original)

- [ ] **Step 1 : écrire les tests qui échouent**

`tests/test_eretro_lib.py` n'importe pas encore `json` : ajouter `import json`
tout en haut du fichier (avant `import xml.etree.ElementTree as ET`). Puis
ajouter en fin de fichier :

```python
def test_entree_depuis_dataitem_capture_primitives_et_xml_source():
    xml = ('<DataItem><Name>Test</Name>'
           '<datasegment><DataSegment>'
           '<Spoint><X>10</X><Y>0</Y></Spoint>'
           '<Epoint><X>30</X><Y>0</Y></Epoint>'
           '</DataSegment></datasegment>'
           '<datapin><DataPin><Pname>1</Pname>'
           '<Pin><X>40</X><Y>0</Y></Pin></DataPin></datapin></DataItem>')
    _prefix, entree = symbole_vers_composant(xml)
    assert entree["primitives"] == [("line", [(10.0, 0.0), (30.0, 0.0)], 2)]
    assert "<Name>Test</Name>" in entree["xml_source"]


def test_entree_depuis_dataitem_connecteur_sans_forme_a_primitives_vide():
    xml = ('<DataItem><Name>Connecteur</Name>'
           '<datapin><DataPin><Pname>1</Pname>'
           '<Pin><X>0</X><Y>0</Y></Pin></DataPin></datapin></DataItem>')
    _prefix, entree = symbole_vers_composant(xml)
    assert entree["primitives"] == []
    assert entree["xml_source"]      # toujours present, meme sans forme


def test_entree_depuis_dataitem_survit_a_un_aller_retour_json():
    xml = ('<DataItem><Name>Test</Name>'
           '<datasegment><DataSegment>'
           '<Spoint><X>10</X><Y>0</Y></Spoint>'
           '<Epoint><X>30</X><Y>0</Y></Epoint>'
           '</DataSegment></datasegment>'
           '<datapin><DataPin><Pname>1</Pname>'
           '<Pin><X>40</X><Y>0</Y></Pin></DataPin></datapin></DataItem>')
    _prefix, entree = symbole_vers_composant(xml)
    relu = json.loads(json.dumps(entree))
    # JSON n'a pas de tuple : les listes imbriquees restent utilisables telles
    # quelles par primitives()/_rot_prims (aucun code ne teste isinstance(tuple)).
    assert relu["primitives"] == [["line", [[10.0, 0.0], [30.0, 0.0]], 2]]
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_lib.py -q`
Attendu : `KeyError: 'primitives'`

- [ ] **Step 3 : implémenter** — dans `circuit_analyzer/eretro_lib.py`

Modifier l'import en tête de fichier :

```python
from gui.schematic_symbols import aimanter_bord, geometrie_libre, primitives_depuis_dataitem
```

Dans `_entree_depuis_dataitem`, remplacer :

```python
    entree = {"name": nom_symbole, "pins": pins, "brochage": brochage,
              "boite": {"w": w, "h": h}}
```

par :

```python
    xml_texte = ET.tostring(r, encoding="unicode")
    entree = {"name": nom_symbole, "pins": pins, "brochage": brochage,
              "boite": {"w": w, "h": h},
              "primitives": primitives_depuis_dataitem(xml_texte, ECHELLE),
              "xml_source": xml_texte}
```

(Le reste de la fonction — marqueur `compose`, `default_value` — ne change pas ;
ces clés continuent de s'ajouter APRÈS, comme aujourd'hui.)

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_lib.py -q` → PASS

Vérifier explicitement la NON-régression des tests d'aller-retour existants
(ils exportent `entree` via `composant_vers_symbole_xml`, qui ignore les clés
inconnues — confirmer que ça reste vrai) :

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_lib.py tests/test_eretro_corpus.py tests/test_eretro_dialecte.py -q` → PASS

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/eretro_lib.py tests/test_eretro_lib.py
git commit -m "feat(interop): capture la forme reelle et le xml source a l'import ERetroDesign"
```

---

### Task 4 : Faire suivre les primitives jusqu'à l'éditeur (`_auto_def`)

**Files:**
- Modify: `gui/schematic_editor.py` (`_auto_def`, `_compute_defs`)
- Test: `tests/test_import_fidele_formes.py` (**créé**)

**Interfaces produites :**
- `_auto_def(name, pins, brochage=None, default_value="", fonctions=None, boite=None, forme_primitives=None) -> dict`
  — copie `forme_primitives` dans `d["primitives"]` si non vide.

- [ ] **Step 1 : écrire les tests qui échouent** — créer
  `tests/test_import_fidele_formes.py` :

```python
"""@file test_import_fidele_formes.py
@brief Import fidele des formes de bibliotheque ERetroDesign (spec 2026-08-05) :
_auto_def fait suivre les primitives reelles jusqu'a l'editeur. Tk -> skip
sans display.
"""
import pytest

ctk = pytest.importorskip("customtkinter")

from gui.schematic_editor import SchematicEditor, _auto_def


@pytest.fixture
def editeur():
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("pas de display Tk")
    root.withdraw()
    ed = SchematicEditor(root)
    ed.pack()
    root.update_idletasks()
    yield ed
    root.destroy()


def _place(ed, t, cx, cy):
    ed._place_type, ed._state = t, "placing"
    return ed._place_at(cx, cy)


def test_auto_def_copie_les_primitives_de_forme_si_presentes():
    d = _auto_def("Test", ["1", "2"], {"1": ["L", 0], "2": ["R", 0]},
                  forme_primitives=[("polygon", [(0, -10), (10, 10), (-10, 10)], False)])
    assert d["primitives"] == [("polygon", [(0, -10), (10, 10), (-10, 10)], False)]
    assert set(d["pins"]) == {"1", "2"}      # le brochage reste inchange


def test_auto_def_sans_primitives_ne_pose_pas_la_cle():
    d = _auto_def("Test", ["1", "2"], {"1": ["L", 0], "2": ["R", 0]})
    assert "primitives" not in d


def test_composant_avec_forme_se_dessine_sans_la_boite_generique(editeur):
    editeur._defs["FORME"] = {
        "label": "Test", "color": "#94a3b8", "w": 80, "h": 60,
        "pins": {"1": (-40, 0)}, "cotes": {"1": "L"}, "default_value": "",
        "primitives": [("polygon", [(0, -20), (20, 20), (-20, 20)], False)],
    }
    c = _place(editeur, "FORME", 200, 200)
    items = editeur._canvas.find_withtag(f"comp_{c.id}")
    polygones = [i for i in items if editeur._canvas.type(i) == "polygon"]
    assert polygones
    # Le triangle importe a 3 sommets (6 coordonnees) ; la boite generique
    # (test suivant) en a 4 (8 coordonnees) : ce nombre distingue les deux.
    assert len(editeur._canvas.coords(polygones[0])) == 6


def test_composant_avec_forme_garde_ses_libelles_de_broches(editeur):
    editeur._defs["FORME"] = {
        "label": "Test", "color": "#94a3b8", "w": 80, "h": 60,
        "pins": {"1": (-40, 0)}, "cotes": {"1": "L"}, "default_value": "",
        "primitives": [("line", [(-10, 0), (10, 0)], 2)],
    }
    c = _place(editeur, "FORME", 200, 200)
    items = editeur._canvas.find_withtag(f"comp_{c.id}")
    textes = [i for i in items if editeur._canvas.type(i) == "text"
             and editeur._canvas.itemcget(i, "text").strip() == "1"]
    assert textes    # le libelle "1" est bien dessine malgre la vraie forme


def test_composant_sans_forme_garde_la_boite_generique_actuelle(editeur):
    editeur._defs["SANSFORME"] = {
        "label": "Test", "color": "#94a3b8", "w": 80, "h": 60,
        "pins": {"1": (-40, 0)}, "cotes": {"1": "L"}, "default_value": "",
    }
    c = _place(editeur, "SANSFORME", 200, 200)
    items = editeur._canvas.find_withtag(f"comp_{c.id}")
    polygones = [i for i in items if editeur._canvas.type(i) == "polygon"]
    assert polygones
    assert len(editeur._canvas.coords(polygones[0])) == 8   # rectangle 4 sommets
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_import_fidele_formes.py -q`
Attendu : `TypeError: _auto_def() got an unexpected keyword argument 'forme_primitives'`
(les deux derniers tests, sans ce kwarg, doivent déjà passer — confirmer la
non-régression avant de continuer).

- [ ] **Step 3 : implémenter** — dans `gui/schematic_editor.py`

Modifier `_auto_def` :

```python
def _auto_def(name: str, pins: list, brochage: dict = None,
              default_value: str = "", fonctions: dict = None,
              boite: dict = None, forme_primitives: list = None) -> dict:
    """@brief Génère une géométrie générique pour un type personnalisé.

    Si le type porte un `brochage` POSITIONNÉ (défini au canevas de l'onglet
    Composants, spec 2026-07-23), il fait foi. Sinon, répartition historique
    moitié à gauche / moitié à droite d'une boîte rectangulaire ; aucun dessin
    sur-mesure n'est requis (le moteur de rendu gère ce cas).

    @param name Nom lisible du type (affiché comme libellé).
    @param pins Liste ordonnée des noms de broches.
    @param brochage {nom: (côté, décalage)} ou None.
    @param forme_primitives Contour réel importé d'ERetroDesign (spec
           2026-08-05, `entree["primitives"]`) ou None/vide — copié tel quel
           dans le def si présent, le brochage/boîte restent inchangés.
    @return dict Entrée compatible COMP_DEFS (label, color, w, h, pins, default_value).
    """
    if brochage:
        b = boite or {}
        d = geometrie_libre({n: tuple(v) for n, v in brochage.items()},
                            b.get("w"), b.get("h"), fonctions or {})
        d["label"] = name
        d["default_value"] = default_value or ""
        if forme_primitives:
            d["primitives"] = forme_primitives
        return d
    pins = [str(p) for p in pins]
    n = len(pins)
    half = (n + 1) // 2
    left, right = pins[:half], pins[half:]
    rows = max(len(left), len(right), 1)
    h = max(40, rows * 30 + 10)
    w = 80
    pinmap: dict = {}

    def _place(items, x):
        m = len(items)
        for i, pn in enumerate(items):
            y = int(round((i - (m - 1) / 2) * 30))
            pinmap[pn] = (x, y)

    _place(left, -w // 2)
    _place(right, w // 2)
    return {"label": name, "color": _AUTO_COLOR, "w": w, "h": h,
            "pins": pinmap, "default_value": default_value or "",
            "fonctions": dict(fonctions or {})}
```

Puis dans `_compute_defs`, faire suivre la nouvelle clé de bibliothèque :

```python
    for key, val in lib.items():
        if key in defs:
            continue          # géométrie intégrée prioritaire
        broches = val.get("pins", [])
        if not broches:
            continue          # type sans broche : non plaçable
        defs[key] = _auto_def(val.get("name", key), broches,
                              val.get("brochage"),
                              val.get("default_value", ""),
                              val.get("fonctions"), val.get("boite"),
                              val.get("primitives"))
```

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_import_fidele_formes.py -q` → PASS

Non-régression large :

Run : `PYTHONUTF8=1 python -m pytest tests/test_schematic_editor.py tests/test_editor_edition.py tests/test_brochage_libre.py -q` → PASS

- [ ] **Step 5 : commit**

```bash
git add gui/schematic_editor.py tests/test_import_fidele_formes.py
git commit -m "feat(editeur): l'editeur dessine la forme importee au lieu de la boite generique"
```

---

### Task 5 : Suite complète + boucle visuelle (exigence boss)

- [ ] **Step 1 : suite complète, deux fois**

```bash
PYTHONUTF8=1 python -m pytest -q
```

Attendu : même nombre de PASS les deux fois, 0 échec (hors
`test_500_portes_sous_budget`, flake connu — relancer isolé si rouge).

- [ ] **Step 2 : boucle visuelle** — script scratch **hors dépôt**
  (scratchpad), composants réels rendus en PNG et **réellement inspectés
  puis décrits** :
  1. AOP importé (`ERetroDesign/ERetroDesign/bin/Debug/LibItem/Lib/AOP.xml`)
     posé dans l'éditeur → triangle net, petits traits `+`/`-`, libellés de
     broches lisibles, aucun chevauchement avec le contour.
  2. Self importée (`Self.xml`) → 3 bosses en arc dans le bon sens (si les
     arcs semblent inversés/hors-forme, le signe de `swAngle` est le point à
     inverser dans `primitives_depuis_dataitem` — cf. réserve 1 du spec).
  3. Diode importée (`Diode.xml`) → triangle + barre.
  4. Un composant SANS forme capturée (ex. connecteur, ou un type de
     bibliothèque personnalisé créé à la main dans l'onglet Composants) →
     boîte générique **strictement identique** à avant (non-régression
     visuelle).
- [ ] **Step 3 : supprimer PNG et scripts** (jamais committés).
- [ ] **Step 4 : revue** — `superpowers:requesting-code-review` sur la
  branche, puis `superpowers:finishing-a-development-branch`. Rien n'est
  poussé sans accord explicite.

---

## Vérification (bout en bout)

1. **Tests** : `PYTHONUTF8=1 python -m pytest -q` — tout vert, dont
   `tests/test_import_fidele_formes.py` (nouveau) et les suites existantes
   (`test_schematic_symbols.py`, `test_eretro_lib.py`, `test_schematic_editor.py`,
   `test_brochage_libre.py`) sans modifier leurs assertions existantes.
2. **À la main dans l'app** : onglet Composants → recevoir/importer la
   bibliothèque ERetroDesign → onglet Schéma → poser un AOP/une Self/une
   Diode importés → vraie forme visible, pas une boîte ; poser un type sans
   forme capturée → boîte générique comme avant.
3. **Preuve visuelle** : les 4 PNG de la Task 5, inspectés et décrits.

## Réserve connue (héritée du spec)

Le signe/sens de `swAngle` (`dataarc`) n'est vérifié que visuellement (pas de
donnée de référence côté C# pour comparer automatiquement) — si les arcs
d'un composant réel semblent tournés dans le mauvais sens à l'inspection
PNG, inverser le signe d'`etendue` dans `primitives_depuis_dataitem` est un
changement d'une ligne, isolé, sans impact sur le reste (même esprit que
l'arbitrage de coin d'`aimanter_bord`).
