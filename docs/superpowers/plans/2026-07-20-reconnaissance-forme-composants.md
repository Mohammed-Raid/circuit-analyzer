# Reconnaissance de composants inconnus par la forme — Plan d'implémentation

> **Pour les workers agentiques :** SOUS-SKILL REQUISE : superpowers:subagent-driven-development pour exécuter ce plan tâche par tâche. Les étapes utilisent des cases à cocher (`- [ ]`).

**Goal :** Déduire le type d'un composant ERetroDesign au nom inconnu à partir de la forme géométrique de son symbole, de façon conservatrice (jamais de faux type).

**Architecture :** Un palier « forme » s'insère dans la chaîne de mapping de `lire_xml` (Étape 5), consulté UNIQUEMENT si le nom est inconnu. `eretro.extraire_geometrie` lit les segments/arcs/broches d'un `DataItem` ; `eretro.classer_par_forme` applique ~5 règles géométriques conservatrices avec abstention. Non-régressif par construction.

**Tech Stack :** Python (stdlib `xml.etree`, `math`), pytest, PYTHONUTF8=1.

## Global Constraints

- Commits en FRANÇAIS, sans footer « Co-Authored-By »/« Generated with Claude ».
- Jamais `git add -A` — fichiers ajoutés un par un.
- `docs.rar` et `SolutionERetroDesignX20260813/` : lecture seule, JAMAIS committés/modifiés.
- `PYTHONUTF8=1` devant chaque python/pytest ; suite complète verte par tâche (~1724+ passed / 15 skipped ; flake connu `test_500_portes_sous_budget` → relancer isolé).
- schemdraw pinné ==0.22 ; canvas des schémas CLAIR ; boucle visuelle PNG après toute modif d'affichage.
- **Règle boss « jamais de vue générique fausse »** : on ne classe que vers des types déjà pourvus d'un drawer (U boîte IC, R/C impédance Z, D diode) ; toute forme ambiguë → `None` (boîte noire, comportement actuel).
- La forme n'est consultée QUE si le mapping par nom échoue (non-régression totale).

## File Structure

- `circuit_analyzer/eretro.py` (modifié) : `extraire_geometrie`, helpers géométriques privés, `classer_par_forme`.
- `circuit_analyzer/xml.py` (modifié) : Étape 1 stocke `elements[idx]['geo']` ; Étape 5 ajoute le palier forme + avertissement dédié.
- `tests/test_eretro_forme.py` (nouveau) : unités géométriques + oracle sur les `Lib/*.xml`.
- `tests/test_eretro_corpus.py` (modifié) : intégration TestDiagram (Gate2 → U).

## Périmètre v1 (précision vs spec)

Familles livrées : **porte (U), résistance (R), condensateur (C), diode (D)** — les quatre dont la géométrie réelle a été vérifiée (Gate2, resistance trad, condo, DIODE). **L'inductance est reportée** : son symbole n'a pas été vérifié et les inducteurs *nommés* sont déjà mappés (`'inductance'→L`), donc aucun cas inconnu connu. La fonction `classer_par_forme` est structurée pour ajouter la règle L plus tard sans refonte.

---

### Task 1 : Extraction de la géométrie d'un DataItem

**Files :**
- Modify : `circuit_analyzer/eretro.py`
- Test : `tests/test_eretro_forme.py` (créé ici)

**Interfaces :**
- Produces : `extraire_geometrie(item_et) -> dict` avec clés `'segments'` (list[tuple[float,float,float,float]] = (sx,sy,ex,ey)), `'nb_arcs'` (int), `'nb_broches'` (int). Chemins DIRECTS (`datasegment/DataSegment`, pas `.//`) pour ne pas aspirer la géométrie interne d'une puce composée.

- [ ] **Step 1 : Test rouge**

```python
# tests/test_eretro_forme.py
import xml.etree.ElementTree as ET
from circuit_analyzer import eretro


def _item_geo(segments=(), nb_arcs=0, nb_pins=0):
    """Construit un <DataItem> minimal avec segments/arcs/broches."""
    it = ET.Element('DataItem')
    ds = ET.SubElement(it, 'datasegment')
    for (sx, sy, ex, ey) in segments:
        seg = ET.SubElement(ds, 'DataSegment')
        sp = ET.SubElement(seg, 'Spoint')
        ET.SubElement(sp, 'X').text = str(sx); ET.SubElement(sp, 'Y').text = str(sy)
        ep = ET.SubElement(seg, 'Epoint')
        ET.SubElement(ep, 'X').text = str(ex); ET.SubElement(ep, 'Y').text = str(ey)
    da = ET.SubElement(it, 'dataarc')
    for _ in range(nb_arcs):
        ET.SubElement(da, 'DataArc')
    dp = ET.SubElement(it, 'datapin')
    for _ in range(nb_pins):
        ET.SubElement(dp, 'DataPin')
    return it


def test_extraire_geometrie_compte_segments_arcs_broches():
    it = _item_geo(segments=[(0, 0, 10, 0), (10, 0, 10, 10)], nb_arcs=1, nb_pins=3)
    geo = eretro.extraire_geometrie(it)
    assert geo['segments'] == [(0.0, 0.0, 10.0, 0.0), (10.0, 0.0, 10.0, 10.0)]
    assert geo['nb_arcs'] == 1
    assert geo['nb_broches'] == 3


def test_extraire_geometrie_ignore_geometrie_interne_de_compose():
    # Un DataItem contenant un DItemL interne ne doit pas voir ses segments.
    it = _item_geo(segments=[(0, 0, 1, 1)], nb_pins=2)
    ditem_l = ET.SubElement(it, 'DItemL')
    interne = ET.SubElement(ditem_l, 'DataItem')
    ds = ET.SubElement(interne, 'datasegment')
    seg = ET.SubElement(ds, 'DataSegment')
    for tag, x, y in [('Spoint', 5, 5), ('Epoint', 9, 9)]:
        pt = ET.SubElement(seg, tag)
        ET.SubElement(pt, 'X').text = str(x); ET.SubElement(pt, 'Y').text = str(y)
    geo = eretro.extraire_geometrie(it)
    assert geo['segments'] == [(0.0, 0.0, 1.0, 1.0)]  # pas le (5,5,9,9) interne
```

- [ ] **Step 2 : Vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_forme.py -q`
Expected : FAIL (`AttributeError: module 'circuit_analyzer.eretro' has no attribute 'extraire_geometrie'`).

- [ ] **Step 3 : Implémentation**

```python
# circuit_analyzer/eretro.py  (ajouter)
def extraire_geometrie(item_et):
    """@brief Géométrie brute d'un DataItem (segments/arcs/broches).

    Chemins DIRECTS : la géométrie interne d'une puce composée (DItemL/DataItem)
    ne doit pas fuir dans celle du boîtier.

    @param item_et Élément <DataItem>.
    @return dict {'segments': list[(sx,sy,ex,ey)], 'nb_arcs': int, 'nb_broches': int}.
    """
    segments = []
    for s in item_et.findall('datasegment/DataSegment'):
        sx = float(s.findtext('Spoint/X') or 0.0)
        sy = float(s.findtext('Spoint/Y') or 0.0)
        ex = float(s.findtext('Epoint/X') or 0.0)
        ey = float(s.findtext('Epoint/Y') or 0.0)
        segments.append((sx, sy, ex, ey))
    return {'segments': segments,
            'nb_arcs': len(item_et.findall('dataarc/DataArc')),
            'nb_broches': len(item_et.findall('datapin/DataPin'))}
```

- [ ] **Step 4 : Vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_forme.py -q`
Expected : PASS (2 tests).

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/eretro.py tests/test_eretro_forme.py
git commit -m "feat(eretro): extraction de la geometrie d'un DataItem (segments/arcs/broches)"
```

---

### Task 2 : `classer_par_forme` + oracle sur les Lib

**Files :**
- Modify : `circuit_analyzer/eretro.py`
- Test : `tests/test_eretro_forme.py`

**Interfaces :**
- Consumes : `extraire_geometrie` (Task 1), `_PLAN_D` (déjà dans eretro.py).
- Produces : `classer_par_forme(geo) -> tuple(type, plan) | None`. `geo` = retour de `extraire_geometrie`. Types possibles : `('U', {})` (porte→boîte IC), `('R', None)`, `('C', None)`, `('D', _PLAN_D)`, ou `None` (abstention). `None` sur toute forme ambiguë.

- [ ] **Step 1 : Tests rouges — unités par famille (fixtures = géométrie réelle des Lib)**

```python
# tests/test_eretro_forme.py  (ajouter)

# Géométries extraites des vrais symboles Lib/*.xml (vérité terrain).
_SEG_RESISTANCE = [(502, 500, 749, 500), (749, 500, 799, 402), (800, 401, 901, 596),
                   (903, 599, 997, 401), (999, 403, 1099, 601), (1101, 602, 1196, 402),
                   (1198, 401, 1249, 499), (1251, 499, 1499, 499)]
_SEG_CONDO = [(501, 399, 1097, 399), (501, 599, 1097, 598),
              (802, 396, 802, 198), (801, 598, 801, 798)]
_SEG_DIODE = [(600, 299, 600, 700), (1002, 500, 602, 299), (602, 701, 1003, 501),
              (1001, 198, 1001, 799), (299, 499, 600, 499), (1005, 499, 1302, 499)]
_SEG_GATE = [(900, 800, 900, 200), (900, 300, 1200, 300),
             (899, 700, 1200, 700), (400, 500, 600, 500)]
_SEG_NPN = [(800, 352, 800, 650), (803, 400, 1100, 200), (803, 600, 1101, 800),
            (500, 500, 800, 500), (901, 663, 1000, 600), (901, 667, 944, 786)]


def test_forme_resistance():
    geo = {'segments': _SEG_RESISTANCE, 'nb_arcs': 0, 'nb_broches': 2}
    assert eretro.classer_par_forme(geo) == ('R', None)


def test_forme_condensateur():
    geo = {'segments': _SEG_CONDO, 'nb_arcs': 0, 'nb_broches': 2}
    assert eretro.classer_par_forme(geo) == ('C', None)


def test_forme_diode():
    geo = {'segments': _SEG_DIODE, 'nb_arcs': 0, 'nb_broches': 2}
    assert eretro.classer_par_forme(geo) == ('D', eretro._PLAN_D)


def test_forme_porte_arc_trois_broches():
    geo = {'segments': _SEG_GATE, 'nb_arcs': 1, 'nb_broches': 3}
    assert eretro.classer_par_forme(geo) == ('U', {})


def test_forme_transistor_npn_sabstient():
    # 3 broches mais 0 arc : ne doit PAS être classé porte (collision évitée).
    geo = {'segments': _SEG_NPN, 'nb_arcs': 0, 'nb_broches': 3}
    assert eretro.classer_par_forme(geo) is None


def test_forme_ambigue_deux_broches_vide_sabstient():
    assert eretro.classer_par_forme({'segments': [], 'nb_arcs': 0, 'nb_broches': 2}) is None
```

- [ ] **Step 2 : Vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_forme.py -q`
Expected : FAIL (`classer_par_forme` inexistant).

- [ ] **Step 3 : Implémentation (helpers + règles)**

```python
# circuit_analyzer/eretro.py  (ajouter)
import math

def _bbox(segs):
    xs = [c for s in segs for c in (s[0], s[2])]
    ys = [c for s in segs for c in (s[1], s[3])]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 0.0, 0.0)

def _diag(segs):
    x0, y0, x1, y1 = _bbox(segs)
    return math.hypot(x1 - x0, y1 - y0) or 1.0

def _long(s):
    return math.hypot(s[2] - s[0], s[3] - s[1])

def _diagonal(s, ref):
    """Segment ni horizontal ni vertical (|dx| et |dy| tous deux significatifs)."""
    dx, dy = abs(s[2] - s[0]), abs(s[3] - s[1])
    seuil = 0.06 * ref
    return dx > seuil and dy > seuil

def _forme_zigzag(segs):
    """Corps de résistance : ≥4 segments diagonaux (le zigzag)."""
    ref = _diag(segs)
    return sum(1 for s in segs if _diagonal(s, ref)) >= 4

def _forme_paire_plaques(segs):
    """Condensateur : 2 longs segments parallèles séparés par un vrai écart
    (exclut 2 pattes colinéaires, écart ≈ 0)."""
    ref = _diag(segs)
    longs = [s for s in segs if _long(s) > 0.35 * ref]
    for i in range(len(longs)):
        for j in range(i + 1, len(longs)):
            a, b = longs[i], longs[j]
            a_horiz = abs(a[3] - a[1]) < 0.15 * _long(a)
            b_horiz = abs(b[3] - b[1]) < 0.15 * _long(b)
            if a_horiz != b_horiz:
                continue  # orientations différentes
            if a_horiz:
                ecart = abs((a[1] + a[3]) / 2 - (b[1] + b[3]) / 2)
            else:
                ecart = abs((a[0] + a[2]) / 2 - (b[0] + b[2]) / 2)
            if 0.1 * ref < ecart < 0.45 * ref:
                return True
    return False

def _forme_triangle_barre(segs):
    """Diode : deux segments convergeant en un sommet + une barre transverse
    près de ce sommet."""
    ref = _diag(segs)
    prox = 0.12 * ref
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            a, b = segs[i], segs[j]
            # sommet = extrémités quasi confondues des deux segments
            for pa in ((a[0], a[1]), (a[2], a[3])):
                for pb in ((b[0], b[1]), (b[2], b[3])):
                    if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) < prox:
                        apex_x = (pa[0] + pb[0]) / 2
                        # barre = segment ~vertical proche de l'abscisse du sommet
                        for c in segs:
                            if c in (a, b):
                                continue
                            vertical = abs(c[2] - c[0]) < 0.15 * (_long(c) or 1.0)
                            near = abs((c[0] + c[2]) / 2 - apex_x) < prox
                            if vertical and near and _long(c) > 0.25 * ref:
                                return True
    return False

def classer_par_forme(geo):
    """@brief Type déduit de la forme du symbole, ou None (abstention).

    Conservateur : ne classe que sur une forme franche, le nombre de broches
    désambiguïse (14 broches d'AOP ≠ 2 d'une diode). Ambigu → None → boîte noire.
    Ne classe que vers des types déjà pourvus d'un drawer (U/R/C/D).

    @param geo dict de extraire_geometrie.
    @return tuple(type, plan) ou None.
    """
    segs, arcs, nb = geo['segments'], geo['nb_arcs'], geo['nb_broches']
    # Porte logique : arc + dos + exactement 3 broches (transistor = 0 arc → exclu).
    if arcs >= 1 and nb == 3:
        return ('U', {})
    if nb == 2 and segs:
        if _forme_triangle_barre(segs):
            return ('D', _PLAN_D)
        if _forme_zigzag(segs):
            return ('R', None)
        if _forme_paire_plaques(segs):
            return ('C', None)
    return None
```

- [ ] **Step 4 : Vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_forme.py -q`
Expected : PASS (unités des 6 tests). Calibrer les seuils (0.06/0.35/0.12…) si un test franc échoue — ne JAMAIS relâcher un test d'abstention.

- [ ] **Step 5 : Oracle sur les vrais Lib (garde anti-contresens)**

```python
# tests/test_eretro_forme.py  (ajouter)
import os, glob
import xml.etree.ElementTree as ET
import pytest
from circuit_analyzer.eretro import extraire_geometrie, classer_par_forme, mapper_nom

_LIB = os.path.join('SolutionERetroDesignX20260813', 'ERetroDesign',
                    'ERetroDesign', 'bin', 'Debug', 'Lib')

pytestmark = pytest.mark.skipif(not os.path.isdir(_LIB), reason="corpus Lib absent")


def _type_attendu(nom_fichier):
    """Vrai type d'un symbole d'après son nom de fichier (via le mapping existant)."""
    nom = os.path.splitext(os.path.basename(nom_fichier))[0]
    corr = mapper_nom(nom)
    return corr[0] if corr else None


@pytest.mark.parametrize('chemin', sorted(glob.glob(os.path.join(_LIB, '*.xml'))))
def test_oracle_lib_jamais_de_contresens(chemin):
    """Sur CHAQUE symbole Lib : classer_par_forme retourne son vrai type OU None,
    jamais un autre type. (S'abstenir = permis ; se tromper = interdit.)"""
    attendu = _type_attendu(chemin)
    if attendu is None:
        pytest.skip("type de référence inconnu pour ce symbole")
    it = ET.parse(chemin).getroot()
    obtenu = classer_par_forme(extraire_geometrie(it))
    if obtenu is not None:
        assert obtenu[0] == attendu, f"contresens {chemin}: {obtenu[0]} != {attendu}"


def test_oracle_lib_couvre_les_familles_ciblees():
    """Les symboles francs des familles v1 sont bien reconnus (pas seulement 'pas faux')."""
    attendus = {'resistance trad.xml': 'R', 'condo.xml': 'C',
                'DIODE.xml': 'D', 'Gate2.xml': 'U'}
    for fichier, typ in attendus.items():
        chemin = os.path.join(_LIB, fichier)
        if not os.path.exists(chemin):
            continue
        obtenu = classer_par_forme(extraire_geometrie(ET.parse(chemin).getroot()))
        assert obtenu is not None and obtenu[0] == typ, f"{fichier} → {obtenu}"
```

- [ ] **Step 6 : Vérifier le vert (oracle)**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_forme.py -q`
Expected : PASS. Si un symbole déclenche un contresens, RESSERRER la règle fautive (ou la faire s'abstenir), pas relâcher l'oracle. Documenter tout symbole où l'on choisit l'abstention.

- [ ] **Step 7 : Commit**

```bash
git add circuit_analyzer/eretro.py tests/test_eretro_forme.py
git commit -m "feat(eretro): classer_par_forme (regles geometriques conservatrices) + oracle sur les Lib"
```

---

### Task 3 : Branchement dans `lire_xml` (palier forme + avertissement)

**Files :**
- Modify : `circuit_analyzer/xml.py` (Étape 1 : stocker `geo` ; Étape 5 : palier forme)
- Test : `tests/test_eretro.py` (réutilise helpers `_item`/`_boardsch`/`_lire`)

**Interfaces :**
- Consumes : `eretro.extraire_geometrie`, `eretro.classer_par_forme`.
- Le helper de test `_item` doit accepter des segments/arcs ; si absent, étendre `_item` (voir Step 1).

- [ ] **Step 1 : Test rouge (intégration bout en bout)**

```python
# tests/test_eretro.py  (ajouter ; adapter _item pour segments/nb_arcs si besoin)
def test_inconnu_type_par_sa_forme_zigzag_devient_R():
    # Nom inconnu + forme zigzag 2 broches → R, avec avertissement dédié.
    segs = [(502, 500, 749, 500), (749, 500, 799, 402), (800, 401, 901, 596),
            (903, 599, 997, 401), (999, 403, 1099, 601), (1101, 602, 1196, 402),
            (1198, 401, 1249, 499), (1251, 499, 1499, 499)]
    item = _item('ZigMachin', pins=[_pin(refs=['n1']), _pin(refs=['n2'])],
                 segments=segs)
    comps = _lire(_boardsch([item], []))
    c = comps[0]
    assert c.type == 'R'
    assert any('forme' in w.lower() and 'ZigMachin' in w for w in comps.warnings)


def test_inconnu_sans_forme_franche_reste_boite_noire():
    item = _item('Truc', pins=[_pin(refs=['a']), _pin(refs=['b'])], segments=[])
    comps = _lire(_boardsch([item], []))
    assert comps[0].type == 'X'
```

- [ ] **Step 2 : Vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro.py::test_inconnu_type_par_sa_forme_zigzag_devient_R -q`
Expected : FAIL (`ZigMachin` classé X, pas de warning « forme »).

- [ ] **Step 3 : Implémentation**

Étape 1 de `lire_xml` — stocker la géométrie à côté des broches :

```python
# dans la boucle d'indexation des DataItem (Étape 1), après avoir construit 'pins' :
elements[idx]['geo'] = eretro.extraire_geometrie(item)
```

Étape 1 bis (`extraire_composes`) — les entrées composées n'ont pas de `geo` pertinente : garantir une valeur par défaut à la lecture (Étape 5) via `.get('geo')`.

Étape 5 — insérer le palier forme et l'avertissement :

```python
        nom_corr = _NOM_VERS_TYPE.get(nom) or eretro.mapper_nom(nom)
        correspondance, par_forme = nom_corr, False
        if correspondance is None:
            geo = elem.get('geo')
            forme = eretro.classer_par_forme(geo) if geo else None
            if forme is not None:
                correspondance, par_forme = forme, True

        if correspondance is None:
            # Composant inconnu : boîte noire type X (inchangé).
            ref = generer_ref('X', elem)
            broches = {}
            for pidx, info_b in enumerate(elem['pins']):
                net = broche_vers_net.get((cid, pidx), 'NC')
                broches[str(pidx + 1)] = net
            composants.append(Component(ref=ref, type='X', pins=broches, value=elem['value']))
            composants.warnings.append(
                f"Composant inconnu '{nom}' (id={cid}) → gardé comme {ref} (type X)")
            continue

        type_prefix, plan = correspondance
        ref = generer_ref(type_prefix, elem)
        # ... (construction des broches inchangée) ...
        if par_forme:
            composants.warnings.append(
                f"Composant '{nom}' (id={cid}) typé par sa forme (dessin) "
                f"→ traité comme {type_prefix} ({ref})")
```

(Adapter au code réel : relire l'Étape 5 courante, le bloc broches connu est déjà présent — n'ajouter que la résolution `par_forme` et l'avertissement.)

- [ ] **Step 4 : Vérifier le vert + non-régression ciblée**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro.py tests/test_eretro_corpus.py tests/test_xml_generator.py -q`
Expected : PASS (dialecte natif inchangé : nos fichiers n'ont pas de segments franc-formés hors symboles réels → aucun reclassement).

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/xml.py tests/test_eretro.py
git commit -m "feat(eretro): palier de reconnaissance par forme dans lire_xml (apres le nom, avant la boite noire)"
```

---

### Task 4 : Intégration corpus réel + boucle visuelle

**Files :**
- Modify : `tests/test_eretro_corpus.py`
- Boucle visuelle : script scratch (hors dépôt), PNG inspectés.

- [ ] **Step 1 : Test rouge/vert corpus (TestDiagram : Gate2 reconnu)**

```python
# tests/test_eretro_corpus.py  (ajouter)
def test_testdiagram_gate2_reconnus_par_forme():
    comps = _lire_corpus('TestDiagram.xml')  # helper existant
    # Les 188 Gate2 (arc + 3 broches) ne sont plus des X : ils deviennent U.
    gate2_en_U = [c for c in comps if c.ref.startswith('U')]
    assert len(gate2_en_U) >= 100
    assert any('forme' in w.lower() for w in comps.warnings)
    # Aucun composant correctement typé auparavant ne régresse en type faux :
    assert all(c.type in ('R', 'C', 'L', 'D', 'Q', 'M', 'U', 'K', 'F', 'X')
               for c in comps)
```

(Si `_lire_corpus` n'existe pas, réutiliser le chargement des tests corpus existants.)

- [ ] **Step 2 : Vérifier**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_corpus.py -q`
Expected : PASS. Noter dans le rapport le nombre de warnings TestDiagram AVANT/APRÈS (425 → attendu nettement moins : les ~188 Gate2 passent d'« inconnu » à « typé par forme »).

- [ ] **Step 3 : Boucle visuelle (exigence boss)**

Script scratch (dossier scratch hors dépôt) : importer `TestDiagram.xml`, rendre en PNG quelques îlots contenant d'anciens Gate2 désormais en boîte IC (drawer puce), + un R/C/D reconnu par forme s'il en existe. INSPECTER les PNG (lire les images) : boîte IC étiquetée à 3 broches, canvas clair, aucune vue générique, aucun symbole en vrac. Décrire ce qui est vu dans le rapport. Supprimer les PNG/scripts après inspection (jamais committés).

- [ ] **Step 4 : Suite complète + commit**

Run : `PYTHONUTF8=1 python -m pytest -q` (relancer `test_500_portes_sous_budget` isolé si flake).
Expected : tout vert.

```bash
git add tests/test_eretro_corpus.py
git commit -m "feat(eretro): corpus reel — Gate2 reconnus par forme (boite IC) et non-regression des types"
```

- [ ] **Step 5 : Ledger**

Ajouter l'entrée de clôture du chantier dans `.superpowers/sdd/progress.md`.

---

## Self-Review (rédaction du plan)

- **Couverture spec :** palier forme non-régressif ✓ ; règles conservatrices + abstention ✓ ; oracle Lib anti-contresens ✓ ; avertissement dédié ✓ ; rendu porte = boîte IC (pas de NAND deviné) ✓ ; boucle visuelle ✓. Écart assumé : inductance reportée (justifié §Périmètre).
- **Placeholders :** aucun — code complet à chaque étape.
- **Cohérence des types :** `extraire_geometrie`/`classer_par_forme` signatures identiques entre tâches ; `_PLAN_D` réutilisé (déjà défini).
