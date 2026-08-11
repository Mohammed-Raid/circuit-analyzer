# Types partagés ERetroDesign dans l'éditeur — Plan d'implémentation

> **Pour l'exécutant :** REQUIRED SUB-SKILL : utiliser
> `superpowers:subagent-driven-development` (recommandé) ou
> `superpowers:executing-plans` pour exécuter ce plan tâche par tâche.

**Spec de référence :** `docs/superpowers/specs/2026-08-03-types-partages-eretrodesign-editeur-design.md`
(commit `077c51d`).

**Goal :** rendre plaçables dans l'éditeur de schéma (`gui/schematic_editor.py`)
4 symboles de la bibliothèque vivante d'ERetroDesign (`Potentiomètre`, `NOT`,
`OR`, `Gate2`) — dessinés depuis SA géométrie réelle (`circuit_analyzer.xml._FORME`
post-fusion), pas à la main. Boîtes noires exportables, aucune sémantique de
détection nouvelle.

**Architecture :** un traceur générique (`primitives_depuis_forme`, module pur)
convertit les fragments XML bruts (`DataSegment`/`DataArc`/`DataPolygon`) de
`_FORME[nom]` en primitives Tk, à l'échelle ×0,5 (facteur mesuré sur la
Résistance partagée). Une seule source de vérité pour le nom-de-forme et
l'alias des broches : `circuit_analyzer.xml._TYPE_VERS_FORME` (déjà le
mécanisme du Plan 1 pour GND/VCC/VSS) — la palette de l'éditeur ET l'export
XML lisent la MÊME entrée, rien n'est dupliqué entre les deux fichiers.

**Tech Stack :** Python 3.11+, `xml.etree.ElementTree` (déjà utilisé par
`circuit_analyzer/xml.py`), Tkinter/CustomTkinter, pytest. Aucune nouvelle
dépendance.

## Global Constraints

- Commits en **français**, **jamais** de footer `Co-Authored-By: Claude` ni
  `Generated with Claude Code`.
- **Jamais `git add -A`** : fichiers ajoutés un par un.
- **Ne jamais committer** `custom_circuits.json` ni `component_library.json`.
- `ERetroDesign/`, `CARTE POUR TESTER (VRAI TEST)/`, `docs.rar`, `dist_demo/`,
  `test14.xml` : lecture seule, jamais committés.
- `PYTHONUTF8=1` sur toutes les commandes pytest.
- `schemdraw==0.22` pinné (non touché par ce plan, contrainte globale du dépôt).
- Branche `rewrite-simple` ; rien n'est poussé sans accord explicite.
- **PNG rendus et inspectés** (via l'outil Read, jamais committés, script
  scratch hors dépôt) avant tout commit touchant du dessin — exigence
  constante de ce projet.
- Décision de périmètre actée dans la spec : ces 4 types sont des **boîtes
  noires exportables** — aucun changement à `circuit_analyzer/detecteur.py`,
  `satellites.py`, `ilots.py`, `drc.py`, `rapport.py`, `composant.py`.

## Faits vérifiés pendant la conception (à ne pas re-dériver)

- Pins post-fusion (`circuit_analyzer.xml._FORME`, dossier ERetroDesign
  présent sur ce poste) :
  ```
  Gate2         -> {'S1': (64, -32, 0), 'S2': (64, 32, 1), 'D8': (-64, 0, 2)}
  NOT           -> {'1': (-80, 0, 0), '2': (80, 0, 1)}
  OR            -> {'1': (-80, -17, 0), '2': (80, -2, 1), '3': (-80, 10, 2)}
  Potentiomètre -> {'1': (-80, 12, 0), '2': (-6, -22, 1), '3': (80, 12, 2)}
  ```
- `NOT` a 5 `<DataSegment>`, 0 `<DataArc>` : triangle (3 segments,
  base à x=-26, apex à x=+33) + 2 amorces de broche. L'apex (sortie) est du
  côté x>0, donc du côté de la broche `"2"` (x=+80) → confirme `IN`=`"1"`,
  `OUT`=`"2"`.
- `OR` et `Gate2` ont des `<DataArc>` avec le schéma
  `<pCenter><X/><Y/></pCenter><stAngle>deg</stAngle><swAngle>deg</swAngle>
  <Spoint/><Epoint/>` — rayon = distance `pCenter`→`Spoint`.
- `<DataPolygon>` : **un tag = un point** ; le polygone est la liste ordonnée
  des points de plusieurs `<DataPolygon>` frères (déjà le format utilisé par
  nos propres formes, ex. `Résistance` dans `circuit_analyzer/xml.py:41-53`).
- Échelle : Résistance partagée, broches à ±80 (BoardSCH, `xml.py:40`) vs
  ±40 (éditeur, `gui/schematic_editor.py:35-36`, `COMP_DEFS["R"]["pins"]`)
  → facteur **×0,5** de BoardSCH vers unités éditeur.
- `circuit_analyzer.composant.construire_graphe` (`composant.py:478-501`)
  n'utilise QUE `comp.pins` (déjà peuplé sur l'instance) — aucune dépendance
  à `TYPES_COMPOSANTS` pour ne pas lever. **Reserve #2 de la spec est levée** :
  aucun changement à `composant.py` n'est nécessaire.
- `_TYP_COMPOSANT` (valeur `<typ>` exportée) est déjà rempli pour les 4 formes
  par le `setdefault` du Plan 1 (`xml.py:336`) : `NOT`→0, `OR`→0,
  `Potentiomètre`→0, `Gate2`→43. Vérifié en direct (`_TYP_COMPOSANT.get(nom)`),
  aucune valeur `None` — pas de risque d'écrire `<typ>None</typ>`.
- Sans entrée `_TYPE_VERS_FORME`, un composant à noms de broches non-numériques
  (nos alias `IN`/`OUT`/`A`/`W`/`B`…) tombe dans le "dernier recours" de
  `generer_xml` (`xml.py:957-970`, boîte DIP générique `PuceN`) — **pas de
  crash, pas de perte de liaison**, juste une géométrie moins fidèle tant que
  `_TYPE_VERS_FORME` n'a pas d'entrée pour ce type.
- `_TYPE_VERS_FORME[type]` a la forme `(nom_forme, {notre_nom_broche: son_nom_broche})`
  — vérifié sur l'entrée `GND: ("GND", {"1": "GND"})` (`xml.py:296`, notre
  broche éditeur `"1"` → sa broche de forme `"GND"`).

---

### Task 1 : Traceur générique — primitives depuis la géométrie brute

**Files :**
- Modify : `gui/schematic_symbols.py` (nouvelle section en fin de fichier,
  après `_tr_boite_libre`, ligne 404)
- Test : `tests/test_schematic_symbols.py`

**Interfaces produites :**
- `primitives_depuis_geometrie(polygon_frag: str, segment_frag: str, arc_frag: str) -> list`
  — fonction PURE, sans dépendance à `_FORME`, testable avec des chaînes
  littérales.
- `primitives_depuis_forme(nom_forme: str) -> list` — fine enveloppe qui lit
  `circuit_analyzer.xml._FORME[nom_forme]` et délègue à
  `primitives_depuis_geometrie`.
- `ECHELLE_ERETRO = 0.5` (constante nommée).

- [ ] **Step 1 : écrire les tests qui échouent**

```python
# --- à ajouter en fin de tests/test_schematic_symbols.py ---

from gui.schematic_symbols import primitives_depuis_geometrie, ECHELLE_ERETRO


def test_echelle_eretro_est_un_demi():
    assert ECHELLE_ERETRO == 0.5


def test_segment_devient_une_ligne_a_l_echelle():
    frag = """<DataSegment><Spoint><X>16</X><Y>48</Y></Spoint>
    <Epoint><X>16</X><Y>-48</Y></Epoint></DataSegment>"""
    prims = primitives_depuis_geometrie("", frag, "")
    assert prims == [("line", [(8.0, 24.0), (8.0, -24.0)], 2)]


def test_deux_segments_donnent_deux_lignes():
    frag = """<DataSegment><Spoint><X>0</X><Y>0</Y></Spoint>
    <Epoint><X>10</X><Y>0</Y></Epoint></DataSegment>
    <DataSegment><Spoint><X>0</X><Y>0</Y></Spoint>
    <Epoint><X>0</X><Y>10</Y></Epoint></DataSegment>"""
    prims = primitives_depuis_geometrie("", frag, "")
    assert len(prims) == 2
    assert prims[0] == ("line", [(0.0, 0.0), (5.0, 0.0)], 2)
    assert prims[1] == ("line", [(0.0, 0.0), (0.0, 5.0)], 2)


def test_arc_devient_bbox_centre_rayon_a_l_echelle():
    frag = """<DataArc><pCenter><X>16</X><Y>0</Y></pCenter>
    <stAngle>-90</stAngle><swAngle>-180</swAngle>
    <Spoint><X>16</X><Y>-48</Y></Spoint>
    <Epoint><X>16</X><Y>48</Y></Epoint></DataArc>"""
    prims = primitives_depuis_geometrie("", "", frag)
    # centre (8,0) à l'échelle, rayon = distance centre->Spoint = 48*0.5 = 24
    assert prims == [("arc", (-16.0, -24.0, 24.0, 24.0), -90.0, -180.0)]


def test_polygone_un_tag_par_point():
    frag = """<DataPolygon><point><X>10</X><Y>10</Y></point></DataPolygon>
    <DataPolygon><point><X>-10</X><Y>10</Y></point></DataPolygon>
    <DataPolygon><point><X>-10</X><Y>-10</Y></point></DataPolygon>"""
    prims = primitives_depuis_geometrie(frag, "", "")
    assert prims == [("polygon", [(5.0, 5.0), (-5.0, 5.0), (-5.0, -5.0)], False)]


def test_fragments_vides_ne_produisent_rien():
    assert primitives_depuis_geometrie("", "", "") == []


def test_primitives_depuis_forme_lit_la_vraie_forme_not():
    import pytest
    from circuit_analyzer.xml import _FORME
    if "NOT" not in _FORME:
        pytest.skip("dossier ERetroDesign absent sur ce poste")
    from gui.schematic_symbols import primitives_depuis_forme
    prims = primitives_depuis_forme("NOT")
    lignes = [p for p in prims if p[0] == "line"]
    assert len(lignes) == 5   # 3 triangle + 2 amorces, mesuré en conception
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_schematic_symbols.py -q`
Attendu : `ImportError: cannot import name 'primitives_depuis_geometrie'`

- [ ] **Step 3 : implémenter** — dans `gui/schematic_symbols.py`, en fin de
  fichier (après `_tr_boite_libre`, ligne 404) :

```python
# ── Rendu generique depuis la bibliotheque partagee ERetroDesign ────────────
# (spec 2026-08-03 : Potentiometre/NOT/OR/Gate2, dessines depuis SA geometrie
# plutot qu'a la main — voir circuit_analyzer.xml._FORME et _TYPE_VERS_FORME,
# seule source de verite pour le nom de forme et l'alias de broches.)

import math
import xml.etree.ElementTree as ET

ECHELLE_ERETRO = 0.5   # unites BoardSCH (xml.py::_FORME) -> unites editeur.
# Verifie en conception sur la Resistance partagee : ses broches (memes que
# les notres cote xml.py) sont a +-80, celles de l'editeur (COMP_DEFS["R"])
# a +-40.


def _points_polygone(fragment):
    """@brief <DataPolygon> repetes -> liste de points (UN point par tag)."""
    if not (fragment or "").strip():
        return []
    racine = ET.fromstring(f"<r>{fragment}</r>")
    pts = []
    for el in racine.findall("DataPolygon"):
        x = float(el.findtext("point/X", "0"))
        y = float(el.findtext("point/Y", "0"))
        pts.append((x, y))
    return pts


def _lignes_segments(fragment):
    """@brief <DataSegment> repetes -> une primitive "line" par segment."""
    if not (fragment or "").strip():
        return []
    racine = ET.fromstring(f"<r>{fragment}</r>")
    lignes = []
    for el in racine.findall("DataSegment"):
        x1 = float(el.findtext("Spoint/X", "0"))
        y1 = float(el.findtext("Spoint/Y", "0"))
        x2 = float(el.findtext("Epoint/X", "0"))
        y2 = float(el.findtext("Epoint/Y", "0"))
        lignes.append((x1, y1, x2, y2))
    return lignes


def _arcs(fragment):
    """@brief <DataArc> repetes -> (centre_x, centre_y, rayon, debut, etendue)."""
    if not (fragment or "").strip():
        return []
    racine = ET.fromstring(f"<r>{fragment}</r>")
    out = []
    for el in racine.findall("DataArc"):
        cx = float(el.findtext("pCenter/X", "0"))
        cy = float(el.findtext("pCenter/Y", "0"))
        sx = float(el.findtext("Spoint/X", str(cx)))
        sy = float(el.findtext("Spoint/Y", str(cy)))
        rayon = math.hypot(sx - cx, sy - cy)
        debut = float(el.findtext("stAngle", "0"))
        etendue = float(el.findtext("swAngle", "0"))
        out.append((cx, cy, rayon, debut, etendue))
    return out


def primitives_depuis_geometrie(polygon_frag, segment_frag, arc_frag):
    """@brief Primitives Tk depuis des fragments XML BoardSCH bruts (spec
    2026-08-03), mis a l'echelle ECHELLE_ERETRO. Fonction PURE : aucune
    dependance a _FORME, testable avec des chaines litterales.

    @return list[primitive] — meme format que les traceurs de _TRACEURS.
    """
    prims = []
    pts = _points_polygone(polygon_frag)
    if pts:
        prims.append(("polygon",
                      [(x * ECHELLE_ERETRO, y * ECHELLE_ERETRO) for x, y in pts],
                      False))
    for x1, y1, x2, y2 in _lignes_segments(segment_frag):
        prims.append(("line",
                      [(x1 * ECHELLE_ERETRO, y1 * ECHELLE_ERETRO),
                       (x2 * ECHELLE_ERETRO, y2 * ECHELLE_ERETRO)], 2))
    for cx, cy, rayon, debut, etendue in _arcs(arc_frag):
        cx, cy, rayon = cx * ECHELLE_ERETRO, cy * ECHELLE_ERETRO, rayon * ECHELLE_ERETRO
        prims.append(("arc", (cx - rayon, cy - rayon, cx + rayon, cy + rayon),
                      debut, etendue))
    return prims


def primitives_depuis_forme(nom_forme):
    """@brief Primitives Tk d'une forme de circuit_analyzer.xml._FORME.

    @throws KeyError si nom_forme absent de _FORME — l'appelant (cf.
            _TRACEURS ci-apres) doit verifier l'appartenance avant d'appeler.
    """
    from circuit_analyzer.xml import _FORME
    forme = _FORME[nom_forme]
    return primitives_depuis_geometrie(forme.get("polygon", ""),
                                       forme.get("segment", ""),
                                       forme.get("arc", ""))
```

**Note d'implémentation :** l'import de `circuit_analyzer.xml` est fait à
l'intérieur de la fonction (pas en tête de fichier) uniquement pour éviter un
import circulaire de convenance au moment où ce module est chargé pendant les
tests purs de Step 1 (qui n'ont pas besoin de `_FORME`). Ce n'est PAS une
optimisation de démarrage : `gui/schematic_editor.py` importe déjà
`circuit_analyzer.composant`, qui importe déjà `networkx`, donc `networkx` est
déjà chargé au démarrage de l'appli quel que soit ce plan.

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_schematic_symbols.py -q`
Attendu : tout PASS (le dernier test se `skip` si `ERetroDesign/` est absent
de ce poste).

- [ ] **Step 5 : commit**

```bash
git add gui/schematic_symbols.py tests/test_schematic_symbols.py
git commit -m "feat(editeur): traceur generique depuis la geometrie brute ERetroDesign"
```

---

### Task 2 : NOT / OR / Potentiomètre — bout en bout (mapping, traceur, palette, export)

**Files :**
- Modify : `circuit_analyzer/xml.py:281-301` (`_TYPE_VERS_FORME`)
- Modify : `gui/schematic_symbols.py` (wiring `_TRACEURS`, fin de la section
  Task 1)
- Modify : `gui/schematic_editor.py` (imports, `_types_partages_eretro()`,
  `_compute_defs()`)
- Test : `tests/test_xml_generator.py`, `tests/test_brochage_libre.py`
  (ou nouveau fichier `tests/test_types_partages_eretro.py` si plus lisible
  — choix libre de l'exécutant, garder les deux préoccupations — export XML
  et palette éditeur — clairement séparées dans les noms de test)

**Interfaces produites :**
- `_TYPE_VERS_FORME["NOT"]`, `["OR"]`, `["POT"]` (nouvelles clés)
- `gui.schematic_editor._types_partages_eretro() -> dict`
- `_TYPES_EDITEUR_DEPUIS_ERETRO = ("NOT", "OR", "POT", "GATE2")` (tuple des 4
  types cibles — `GATE2` y figure déjà, son entrée `_TYPE_VERS_FORME` arrive
  en Task 3, tout le reste du mécanisme est déjà générique)

**Interfaces consommées (Task 1) :**
- `gui.schematic_symbols.primitives_depuis_forme(nom_forme) -> list`
- `gui.schematic_symbols.ECHELLE_ERETRO`

- [ ] **Step 1 : écrire les tests qui échouent**

Dans `tests/test_xml_generator.py` (ou fichier équivalent déjà existant qui
teste `generer_xml`) :

```python
def test_porte_not_placee_s_exporte_avec_sa_vraie_geometrie():
    import pytest
    from circuit_analyzer.xml import _FORME
    if "NOT" not in _FORME:
        pytest.skip("dossier ERetroDesign absent sur ce poste")
    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml
    comp = Composant(ref="NOT1", type="NOT", pins={"IN": "NET_A", "OUT": "NET_B"})
    xml_out = generer_xml([comp])
    assert "<Name>NOT</Name>" in xml_out
    assert "Puce" not in xml_out   # pas de repli boite generique


def test_porte_or_toutes_broches_presentes():
    import pytest
    from circuit_analyzer.xml import _FORME
    if "OR" not in _FORME:
        pytest.skip("dossier ERetroDesign absent sur ce poste")
    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml
    comp = Composant(ref="OR1", type="OR",
                     pins={"IN1": "NET_A", "IN2": "NET_B", "OUT": "NET_C"})
    xml_out = generer_xml([comp])
    assert xml_out.count("<Line>") >= 3   # 3 liaisons, aucune broche perdue


def test_potentiometre_place_s_exporte_avec_sa_vraie_geometrie():
    import pytest
    from circuit_analyzer.xml import _FORME
    if "Potentiomètre" not in _FORME:
        pytest.skip("dossier ERetroDesign absent sur ce poste")
    from circuit_analyzer.composant import Composant
    from circuit_analyzer.xml import generer_xml
    comp = Composant(ref="POT1", type="POT",
                     pins={"A": "NET_A", "W": "NET_W", "B": "NET_B"})
    xml_out = generer_xml([comp])
    assert "<Name>Potentiomètre</Name>" in xml_out
```

Dans `tests/test_brochage_libre.py` (fixture `editeur`/`_place` déjà présentes
dans ce fichier, cf. `docs/superpowers/plans/2026-07-23-brochage-libre.md`) :

```python
def test_not_placable_si_sa_bibliotheque_est_chargee(editeur):
    import pytest
    from circuit_analyzer.xml import _FORME
    if "NOT" not in _FORME:
        pytest.skip("dossier ERetroDesign absent sur ce poste")
    assert "NOT" in editeur._defs
    c = _place(editeur, "NOT", 200, 200)
    assert set(editeur._geom(c)["pins"]) == {"IN", "OUT"}


def test_repli_sans_dossier_eretro_pas_de_bouton_pas_de_crash(monkeypatch):
    import importlib
    monkeypatch.setenv("ERETRO_LIB", "Z:/chemin/qui/n/existe/pas")
    import circuit_analyzer.xml as cx
    importlib.reload(cx)
    from gui.schematic_editor import _types_partages_eretro
    assert _types_partages_eretro() == {}
    importlib.reload(cx)   # restaure l'etat normal pour les tests suivants
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py tests/test_brochage_libre.py -q`
Attendu : `KeyError`/`AttributeError` selon le test (types absents de
`_TYPE_VERS_FORME`, `_types_partages_eretro` inexistante).

- [ ] **Step 3 : implémenter**

**3a. `circuit_analyzer/xml.py`** — ajouter 3 entrées à `_TYPE_VERS_FORME`
(juste après l'entrée `"VSS"`, avant `"X"`, ligne 298) :

```python
    # Types partages ERetroDesign, places par l'editeur (spec 2026-08-03).
    # Boites noires exportables : aucune semantique de detection. Noms de
    # broches verifies sur _FORME apres fusion + geometrie du symbole NOT
    # (l'apex du triangle, cote sortie, est du cote x>0 = broche "2").
    "NOT": ("NOT", {"IN": "1", "OUT": "2"}),
    "OR": ("OR", {"IN1": "1", "OUT": "2", "IN2": "3"}),
    "POT": ("Potentiomètre", {"A": "1", "W": "2", "B": "3"}),
```

**3b. `gui/schematic_symbols.py`** — à la toute fin du fichier (après la
section Task 1) :

```python
# Types dont le nom-de-forme et l'alias de broches vivent dans
# _TYPE_VERS_FORME (source unique, xml.py) — un type sans entree n'a
# simplement pas de traceur ici, `primitives()` retombe sur `_tr_boite`.
from circuit_analyzer.xml import _TYPE_VERS_FORME as _TVF_AU_CHARGEMENT

_TYPES_EDITEUR_DEPUIS_ERETRO = ("NOT", "OR", "POT", "GATE2")


def _traceur_depuis_forme(type_lettre):
    """@brief Fabrique un traceur _TRACEURS pour `type_lettre`, dont le nom de
    forme vit dans _TYPE_VERS_FORME (source unique, xml.py). `type_lettre` est
    capture par argument de fabrique, pas par variable de boucle — evite le
    piege classique de liaison tardive des closures Python."""
    def _tracer(defn):
        from circuit_analyzer.xml import _TYPE_VERS_FORME
        nom_forme, _plan = _TYPE_VERS_FORME[type_lettre]
        return primitives_depuis_forme(nom_forme)
    return _tracer


for _type_lettre in _TYPES_EDITEUR_DEPUIS_ERETRO:
    if _type_lettre in _TVF_AU_CHARGEMENT:
        _TRACEURS[_type_lettre] = _traceur_depuis_forme(_type_lettre)
del _type_lettre
```

**Note d'implémentation :** cette section importe `circuit_analyzer.xml` au
niveau module (contrairement à `primitives_depuis_forme` de la Task 1, qui
l'importe en local) — c'est nécessaire pour lire `_TYPE_VERS_FORME` une fois
au chargement et savoir quels traceurs enregistrer. Sans conséquence sur le
démarrage de l'appli : `gui/schematic_editor.py` importe déjà
`circuit_analyzer.composant`, qui importe déjà `networkx` (cf. Task 1).

**3c. `gui/schematic_editor.py`** — imports (après la ligne 22, dans le
bloc `from gui.schematic_symbols import (...)`) :

```python
from gui.schematic_symbols import (primitives, rotate_pin as _rotate_pin,
                                    def_puce, est_boite_generique,
                                    aimanter_bord, geometrie_libre,
                                    AUTO_COLOR as _AUTO_COLOR,
                                    BOITE_MIN_W, BOITE_MIN_H, BOITE_MARGE,
                                    ECHELLE_ERETRO, TYPE_LIBRE)
```

*(`BOITE_MARGE` n'était pas encore importé ici — l'ajouter à la liste
existante.)*

Puis, avant `_compute_defs()` (ligne 123) :

```python
def _types_partages_eretro() -> dict:
    """@brief Types plaçables dérivés de sa bibliothèque (spec 2026-08-03).

    Un type de `_TYPES_EDITEUR_DEPUIS_ERETRO` n'apparaît dans la palette QUE
    si sa forme est chargée dans `_FORME` (dossier ERetroDesign présent et
    fusionné) ET que son entrée `_TYPE_VERS_FORME` existe (alias de broches
    décidés). Absent sinon — pas de bouton, pas d'exception (même principe de
    repli que le Plan 1 : `circuit_analyzer.xml._fusionner_bibliotheque_eretro`).
    """
    from circuit_analyzer.xml import _FORME, _TYPE_VERS_FORME
    from gui.schematic_symbols import _TYPES_EDITEUR_DEPUIS_ERETRO

    defs = {}
    for type_lettre in _TYPES_EDITEUR_DEPUIS_ERETRO:
        spec = _TYPE_VERS_FORME.get(type_lettre)
        if spec is None:
            continue
        nom_forme, plan_broches = spec
        if nom_forme not in _FORME:
            continue
        pins_forme = _FORME[nom_forme]["pins"]
        pins = {}
        for nom_nous, nom_lui in plan_broches.items():
            if nom_lui not in pins_forme:
                continue
            x, y, _rang = pins_forme[nom_lui]
            pins[nom_nous] = (x * ECHELLE_ERETRO, y * ECHELLE_ERETRO)
        if not pins:
            continue
        xs = [abs(x) for x, y in pins.values()]
        ys = [abs(y) for x, y in pins.values()]
        w = max(BOITE_MIN_W, 2 * max(xs, default=0) + BOITE_MARGE)
        h = max(BOITE_MIN_H, 2 * max(ys, default=0) + BOITE_MARGE)
        defs[type_lettre] = {"label": nom_forme, "color": _AUTO_COLOR,
                              "w": w, "h": h, "pins": pins,
                              "default_value": ""}
    return defs
```

Puis modifier `_compute_defs()` (ligne 123-146) :

```python
def _compute_defs() -> dict:
    """@brief Defs effectives de l'éditeur : intégrés + partagés ERetroDesign
    + types personnalisés générés.

    @return dict {type -> géométrie}. Les types intégrés (COMP_DEFS) priment ;
            les types partagés ERetroDesign comblent des types ABSENTS de
            COMP_DEFS ; les types perso de la bibliothèque reçoivent une
            géométrie auto en dernier.
    """
    defs = dict(COMP_DEFS)
    for key, val in _types_partages_eretro().items():
        defs.setdefault(key, val)
    try:
        lib = charger_bibliotheque()
    except Exception:
        _log.warning("bibliothèque de composants illisible — types personnalisés "
                     "ignorés dans la palette", exc_info=True)
        lib = {}
    for key, val in lib.items():
        if key in defs:
            continue          # géométrie intégrée ou ERetroDesign prioritaire
        broches = val.get("pins", [])
        if not broches:
            continue          # type sans broche : non plaçable
        defs[key] = _auto_def(val.get("name", key), broches,
                              val.get("brochage"),
                              val.get("default_value", ""),
                              val.get("fonctions"), val.get("boite"))
    return defs
```

- [ ] **Step 4 : vérifier le vert + la NON-RÉGRESSION**

```bash
PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py tests/test_brochage_libre.py \
  tests/test_schematic_symbols.py tests/test_schematic_editor.py tests/test_editor_edition.py -q
```
Attendu : tout vert (les tests dépendant de la vraie bibliothèque se `skip`
si `ERetroDesign/` est absent).

- [ ] **Step 5 : boucle visuelle (OBLIGATOIRE avant de committer)**

Script scratch (hors dépôt, ex. `scratchpad/render_not_or_pot.py`) :

```python
"""Scratch — rendu PNG de NOT/OR/Potentiometre pour inspection visuelle.
NE JAMAIS committer ce fichier ni son PNG."""
import tkinter as tk
import customtkinter as ctk
from gui.schematic_editor import SchematicEditor

root = ctk.CTk()
ed = SchematicEditor(root)
ed.pack()
root.update_idletasks()

for t, x in (("NOT", 150), ("OR", 350), ("POT", 550)):
    if t in ed._defs:
        ed._place_type, ed._state = t, "placing"
        ed._place_at(x, 200)
ed._redraw_all()
root.update_idletasks()
ed._canvas.postscript(file="scratchpad/not_or_pot.eps")
root.destroy()
```

Convertir l'EPS en PNG (Pillow, déjà une dépendance du projet) puis
**inspecter avec l'outil Read** — vérifier : les 3 boîtes sont dessinées
(pas de rectangle vide), les libellés de broches sont lisibles et ne se
chevauchent pas, le triangle NOT pointe vers sa broche `OUT`. Décrire ce qui
est vu avant de continuer. Supprimer le script et le PNG ensuite.

- [ ] **Step 6 : commit**

```bash
git add circuit_analyzer/xml.py gui/schematic_symbols.py gui/schematic_editor.py \
  tests/test_xml_generator.py tests/test_brochage_libre.py
git commit -m "feat(editeur): NOT/OR/Potentiometre plaçables, dessines depuis sa geometrie"
```

---

### Task 3 : Gate2 — décision visuelle puis branchement (mécanisme déjà générique)

**Files :**
- Modify : `circuit_analyzer/xml.py:281-301` (`_TYPE_VERS_FORME`, une seule
  nouvelle entrée)
- Test : ajout dans le même fichier de test que Task 2

**Interfaces consommées (Task 2) :** `_TYPES_EDITEUR_DEPUIS_ERETRO` contient
déjà `"GATE2"` ; `_types_partages_eretro()` et le wiring `_TRACEURS` de
`gui/schematic_symbols.py` sont déjà génériques — **aucun code de palette ou
de rendu à écrire dans cette tâche**, uniquement la donnée
`_TYPE_VERS_FORME["GATE2"]`.

Ses broches (mesurées en conception) : `S1: (64, -32)`, `S2: (64, 32)`,
`D8: (-64, 0)` — 2 broches à x=+64 (droite), 1 broche seule à x=-64
(gauche). Sa géométrie n'a pas encore été rendue visuellement à ce stade du
plan — c'est l'objet de cette tâche.

- [ ] **Step 1 : rendu PNG AVANT toute décision de nommage**

Script scratch temporaire, même mécanique que Task 2 Step 5, mais AVANT
d'ajouter l'entrée `_TYPE_VERS_FORME["GATE2"]` — dessiner directement avec
`gui.schematic_symbols.primitives_depuis_forme("Gate2")` sur un canevas nu
(pas besoin de l'éditeur complet) :

```python
"""Scratch — rendu PNG de Gate2 seul, AVANT de decider ses alias de broches."""
import tkinter as tk
from gui.schematic_symbols import primitives_depuis_forme

root = tk.Tk()
cv = tk.Canvas(root, width=400, height=300, bg="white")
cv.pack()
cx, cy = 200, 150
for prim in primitives_depuis_forme("Gate2"):
    if prim[0] == "line":
        (x1, y1), (x2, y2) = prim[1]
        cv.create_line(cx + x1, cy - y1, cx + x2, cy - y2, width=prim[2])
    elif prim[0] == "arc":
        x0, y0, x1, y1 = prim[1]
        cv.create_arc(cx + x0, cy - y1, cx + x1, cy - y0,
                      start=prim[2], extent=prim[3], style=tk.ARC)
    elif prim[0] == "polygon":
        pts = [(cx + x, cy - y) for x, y in prim[1]]
        cv.create_polygon(pts, fill="" if not prim[2] else "black", outline="black")
# broches brutes, pour se reperer
from circuit_analyzer.xml import _FORME
for nom, (x, y, _r) in _FORME["Gate2"]["pins"].items():
    x, y = x * 0.5, y * 0.5
    cv.create_oval(cx+x-3, cy-y-3, cx+x+3, cy-y+3, fill="red")
    cv.create_text(cx+x, cy-y-10, text=nom)
root.update_idletasks()
cv.postscript(file="scratchpad/gate2.eps")
root.destroy()
```

Convertir en PNG et **inspecter avec l'outil Read**. Décrire ce qui est vu :
forme du corps (silhouette AND/OR/tampon ?), quel côté porte l'entrée /
la sortie d'après le dessin (pas seulement les noms de broches `S1`/`S2`/`D8`,
qui ne préjugent de rien).

- [ ] **Step 2 : décider et écrire les alias de broches**

D'après ce qui est observé au Step 1, choisir le mapping `{notre_nom: son_nom}`.
Par défaut raisonnable si le rendu confirme 2 entrées à droite (`S1`/`S2`) et
1 sortie à gauche (`D8`) — inhabituel (entrées/sortie inversées par rapport à
la convention gauche→droite des 3 autres portes) mais géométriquement
cohérent avec les coordonnées mesurées :

```python
def test_gate2_a_un_mapping_de_broches_conforme_a_la_geometrie():
    import pytest
    from circuit_analyzer.xml import _FORME
    if "Gate2" not in _FORME:
        pytest.skip("dossier ERetroDesign absent sur ce poste")
    from circuit_analyzer.xml import _TYPE_VERS_FORME
    nom_forme, plan = _TYPE_VERS_FORME["GATE2"]
    assert nom_forme == "Gate2"
    assert set(plan.values()) == {"S1", "S2", "D8"}
    assert not any("A_REMPLIR" in cle for cle in plan), \
        "gabarit du plan non finalise : remplacer les cles apres inspection visuelle"
```

*(Ce test verrouille seulement la complétude du mapping — pas les noms
choisis, qui dépendent de l'inspection visuelle du Step 1 et sont à écrire
en clair par l'exécutant une fois l'inspection faite. Ne pas deviner les
noms sans avoir réellement regardé le PNG.)*

Dans `circuit_analyzer/xml.py`, ajouter à `_TYPE_VERS_FORME` (à la suite de
Task 2) :

```python
    # Gate2 : nommage decide apres inspection visuelle (voir plan Task 3,
    # scratchpad/gate2.eps au moment de l'implementation — pas de PNG committe).
    "GATE2": ("Gate2", {"<A_REMPLIR_APRES_INSPECTION>": "S1",
                        "<A_REMPLIR_APRES_INSPECTION>": "S2",
                        "<A_REMPLIR_APRES_INSPECTION>": "D8"}),
```

*(Les clés `<A_REMPLIR_APRES_INSPECTION>` sont un gabarit — l'exécutant les
remplace par les noms réels choisis d'après le Step 1, jamais laissées telles
quelles dans le commit.)*

- [ ] **Step 3 : vérifier le vert + non-régression**

```bash
PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py tests/test_brochage_libre.py \
  tests/test_schematic_symbols.py -q
```

Puis vérifier manuellement que `"GATE2"` apparaît maintenant dans la palette
(bouton visible) — placer une instance, vérifier ses noms de broches dans
`editeur._geom(c)["pins"]`, comme au Task 2.

- [ ] **Step 4 : boucle visuelle finale (le composant complet, pas juste sa géométrie brute)**

Même script que Task 2 Step 5, en ajoutant `("GATE2", 750)` à la liste de
placement. Inspecter, décrire, supprimer script + PNG.

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/xml.py tests/test_xml_generator.py
git commit -m "feat(editeur): Gate2 placable, alias de broches decides apres inspection visuelle"
```

---

### Task 4 : Suite complète + nettoyage + rapport

- [ ] **Step 1 : suite complète**

```bash
PYTHONUTF8=1 python -m pytest -q
```
Attendu : verte, hors le flake connu `test_500_portes_sous_budget` (relancer
isolé si rouge — connu pour ne pas toujours repasser sous 10 s en suite
complète, cf. mémoire de session).

- [ ] **Step 2 : vérifier qu'aucun PNG/script scratch n'a été committé**

```bash
git status --short
git log --oneline -5 --stat
```
Confirmer qu'aucun fichier `.png`/`.eps`/`scratchpad/` n'apparaît dans les
commits de ce plan.

- [ ] **Step 3 : grep de garde**

```bash
grep -n "A_REMPLIR_APRES_INSPECTION" circuit_analyzer/xml.py
```
Attendu : **aucun résultat** — si ce motif apparaît encore, Task 3 Step 2
n'a pas été finalisée, ne pas continuer.

- [ ] **Step 4 : revue** — `superpowers:requesting-code-review` sur la
  branche, puis `superpowers:finishing-a-development-branch`. Rien n'est
  poussé sans accord explicite du boss.

---

## Vérification (bout en bout)

1. **Tests** : `PYTHONUTF8=1 python -m pytest -q` — tout vert (flake connu mis
   à part), y compris les tests `skipif` qui s'exécutent réellement sur ce
   poste (dossier `ERetroDesign/` présent).
2. **Non-régression** : les 11 types existants de l'éditeur (R/C/L/F/Q/M/U/
   GND/VCC/T/K) ne changent PAS visuellement — aucun de leurs traceurs n'est
   touché par ce plan.
3. **À la main dans l'app** : `python app.py` → onglet Schéma → les boutons
   `NOT`, `OR`, `POT`, `GATE2` apparaissent dans la palette → poser chacun →
   vérifier les noms de broches affichés → câbler → exporter en XML → recharger
   le fichier exporté dans un éditeur de texte, vérifier que la balise
   `<Name>` correspond à sa vraie forme (pas `Puce4`).
4. **Repli** : avec `ERETRO_LIB` pointant vers un chemin inexistant, les 4
   boutons disparaissent de la palette, aucune exception au démarrage de
   l'éditeur ni à `_compute_defs()`.

## Réserves

1. Héritée de la spec : le rendu de nos propres symboles poussés dans sa
   bibliothèque n'est pas validé côté C#.
2. Aucune sémantique électrique n'est ajoutée pour ces 4 types (pas de
   détection, pas de règle DRC) — décision de périmètre explicite, à
   reconsidérer dans un chantier séparé si le besoin apparaît.
3. Le mapping de `Gate2` dépend d'une inspection visuelle qui n'a pas encore
   eu lieu au moment de l'écriture de ce plan — Task 3 ne peut pas être
   pré-remplie plus précisément que ça sans deviner.
