# Import ERetroDesign (fichiers réels) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ouvrir un fichier réel ERetroDesign (BoardSCH XML de l'éditeur C# de l'entreprise) dans l'onglet Analyser et obtenir l'analyse complète existante (îlots, montages, blocs Z), sans jamais rien perdre ni planter.

**Architecture:** `lire_xml` (`circuit_analyzer/xml.py`) reste l'unique point d'entrée ; les traitements spécifiques ERetroDesign vivent dans un nouveau module pur `circuit_analyzer/eretro.py` (mapping des noms, classification des rails, aplatissement des puces composées). La connexité se résout par ÉGALITÉ DE CHAÎNES entre `datapin/NodeL/string` et `Line.CFirst`/`CLast` (la règle que le C# applique lui-même) — on ne parse jamais le format packé des refs, ambigu dans les vieux fichiers.

**Tech Stack:** Python 3.11, `xml.etree.ElementTree` (stdlib, aucune dépendance nouvelle), pytest, tkinter/customtkinter pour le bandeau GUI.

**Spec:** `docs/superpowers/specs/2026-07-17-import-eretrodesign-design.md` (lue et approuvée par le boss).

## Global Constraints

- `schemdraw==0.22` épinglé — ne jamais monter de version.
- `PYTHONUTF8=1` devant CHAQUE commande python/pytest (`$env:PYTHONUTF8='1'; python -m pytest …` en PowerShell, `PYTHONUTF8=1 python -m pytest …` en bash).
- Suite complète verte à chaque tâche. `test_500_portes_sous_budget` est un flake connu sous charge machine : s'il échoue seul avec `len(matches)==500` correct, le relancer isolé.
- Commits en FRANÇAIS, JAMAIS de footer « Co-Authored-By » ni « Generated with Claude Code ».
- `git add` fichier par fichier — JAMAIS `git add -A`. Ne JAMAIS ajouter `docs.rar` ni quoi que ce soit sous `SolutionERetroDesignX20260813/` (dossier du boss, lecture seule).
- **Non-régression absolue du dialecte natif** : les fichiers produits par `generer_xml` doivent donner exactement les mêmes composants/nets qu'avant — la suite existante (~1683 tests) est le garde-fou ; la lancer en entier avant chaque commit.
- Tout ce qui est illisible/inconnu dans un fichier réel → import au mieux + warning dans `composants.warnings`, jamais d'exception (seul un XML syntaxiquement invalide lève `ValueError`, comportement actuel conservé).

## Corpus réel (lecture seule)

`SolutionERetroDesignX20260813/ERetroDesign/ERetroDesign/bin/Debug/` :
- `SaveDiag.xml` — 6 DataItem, 6 Line, 0 CComp, refs concaténées sans underscore (`1001`, `2011`).
- `Diag2.xml` — 6 DataItem, 6 Line, 2 CComp, refs `T…`/`X…`, 7 `id=0` (collisions d'id).
- `TestDiagram.xml` — 2,4 Mo, vraie carte : 285 DataItem, 212 Line, 63 CComp, 41 `id=0`.
- `Lib/*.xml` — symboles : les broches des passifs n'ont NI `Pname` NI `Pnumber` (éléments absents) ; `npn.xml` a `Pname` vide et `Pnumber` = B/C/E ; `DIODE.xml` a `Pname` = ANODE/CATHODE et `Pnumber` = 1/2 ; `NE555.xml` a `Pname` = TRIGGER… et `Pnumber` = 1-8.

## Faits de code existant (vérifiés 2026-07-17)

- `lire_xml` : `circuit_analyzer/xml.py:1093`. Étape 1 indexe par `<id>` (l.1115-1127, à remplacer par la position). Étape 2 : Union-Find `trouver`/`unir` + arêtes via `_analyser_ref_noeud` (l.1163-1170). Étape 4 : `nom_net` (l.1183). Étape 5 : branche inconnue → type X (l.1231-1243), branche connue via `_NOM_VERS_TYPE` (l.1245).
- `_analyser_ref_noeud` (l.1077) : exige `i_j_…` avec underscores, lève `ValueError` sinon.
- `ListeComposantsXML` (l.1053) : `list` + attribut `.warnings`.
- `_NOMS_ALIMENTATION` (l.1037), `_NET_ALIMENTATION` (l.1068), helpers `is_power`/`is_gnd` importés depuis `circuit_analyzer.patterns.base` (déjà utilisés par `nom_net`).
- Notre `generer_xml` écrit `<id>` = index séquentiel, `Pnumber` = `Pname`, `NodeL` rempli avec les mêmes chaînes que `CFirst`/`CLast` (`c_p_0|1_wid`), `<typ>` = code ASCII entier.
- `identifier(type_, value)` : `circuit_analyzer/catalogue.py:112`, retourne l'entrée catalogue ou `None` ; mémoïsée, ne JAMAIS muter le retour.
- GUI : `gui/tab_analyze.py` route déjà `.xml` → `lire_xml` (`_analyze`, l.264-265). `self._stats_row` est packé `before=self._body` (l.294) en cas de succès, `pack_forget()` dans les 3 chemins d'erreur.
- Les détecteurs déduisent NPN/PNP de la TOPOLOGIE (collecteur au rail vs masse) — pas de champ polarité sur `Composant` : `npn` et `transistor pnp` mappent tous deux vers `Q`.

## Structure de fichiers

- **Create** `circuit_analyzer/eretro.py` — normalisation de noms, table `_MAPPING_ERETRO`, `mapper_nom`, `classer_rail`, `extraire_composes`. Module pur, aucune dépendance GUI.
- **Modify** `circuit_analyzer/xml.py` — `lire_xml` : indexation par position, lecture `Pnumber`/`NodeL`/`typ`, résolution des fils par égalité, intégration composés, branche mapping, rails, `groupes_puces`.
- **Modify** `gui/tab_analyze.py` — bandeau d'avertissements d'import.
- **Create** `tests/test_eretro.py` (unitaires, fixtures synthétiques) et `tests/test_eretro_corpus.py` (intégration corpus réel).

---

### Task 1: eretro.py — mapping des noms + lecture des broches Pnumber/positionnelle

**Files:**
- Create: `circuit_analyzer/eretro.py`
- Modify: `circuit_analyzer/xml.py` (Étape 1 lecture broches ~l.1125-1126 ; Étape 5 branche inconnue ~l.1231 et broches ~l.1249-1253)
- Test: `tests/test_eretro.py` (create)

**Interfaces:**
- Consumes: `identifier(type_, value)` de `circuit_analyzer.catalogue` (existant).
- Produces: `normaliser_nom(nom: str) -> str` ; `mapper_nom(nom: str) -> tuple[str, dict | None] | None` (plan `None` = broches numérotées par position). Task 2-4 réutilisent le fichier `tests/test_eretro.py` et son helper `_lire`.

- [ ] **Step 1: Écrire les tests RED**

Créer `tests/test_eretro.py` :

```python
"""
@file test_eretro.py
@brief Tests unitaires de l'import des fichiers réels ERetroDesign
(circuit_analyzer/eretro.py + adaptations de lire_xml). Fixtures BoardSCH
synthétiques écrites à la main — le corpus réel est couvert par
test_eretro_corpus.py.
"""
import os
import tempfile

import pytest

from circuit_analyzer.eretro import normaliser_nom, mapper_nom
from circuit_analyzer.xml import lire_xml


# ── Helpers fixtures ──────────────────────────────────────────────────────────

ENTETE = ('<?xml version="1.0" encoding="utf-8"?>\n'
          '<BoardSCH xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
          'xmlns:xsd="http://www.w3.org/2001/XMLSchema">')


def _pin(refs=(), pnumber='', pname=''):
    """@brief Fragment <DataPin> ERetroDesign (Pname/Pnumber optionnels, comme les vrais fichiers)."""
    node_l = ''.join(f'<string>{r}</string>' for r in refs)
    morceaux = ['    <DataPin>']
    if pname:
        morceaux.append(f'      <Pname>{pname}</Pname>')
    if pnumber:
        morceaux.append(f'      <Pnumber>{pnumber}</Pnumber>')
    morceaux.append(f'      <NodeL>{node_l}</NodeL>')
    morceaux.append('      <Pin><X>0</X><Y>0</Y></Pin>')
    morceaux.append('    </DataPin>')
    return '\n'.join(morceaux)


def _item(name, value='', pins=(), comp_id=0, typ=None):
    """@brief Fragment <DataItem> ERetroDesign. pins = liste de fragments _pin()."""
    typ_xml = f'<typ>{typ}</typ>' if typ is not None else ''
    return (f'  <DataItem>\n'
            f'    <Name>{name}</Name><value>{value}</value>\n'
            f'    <datapin>\n' + '\n'.join(pins) + '\n    </datapin>\n'
            f'    <id>{comp_id}</id>{typ_xml}\n'
            f'  </DataItem>')


def _fil(cfirst, clast):
    """@brief Fragment <Line> ERetroDesign (extrémités = refs chaîne brutes)."""
    return (f'  <Line><CFirst>{cfirst}</CFirst><CLast>{clast}</CLast>'
            f'<LP /><ID>0</ID></Line>')


def _boardsch(items, fils, ccomps=''):
    """@brief Document BoardSCH complet à partir des fragments."""
    return (f'{ENTETE}\n<CmpntL>\n' + '\n'.join(items) + '\n</CmpntL>\n'
            f'<lineL>\n' + '\n'.join(fils) + '\n</lineL>\n'
            f'<CCmpntL>{ccomps}</CCmpntL>\n</BoardSCH>')


def _lire(xml_texte):
    """@brief Écrit le XML dans un fichier temporaire et le lit via lire_xml."""
    with tempfile.NamedTemporaryFile('w', suffix='.xml', delete=False,
                                     encoding='utf-8') as f:
        f.write(xml_texte)
        chemin = f.name
    try:
        return lire_xml(chemin)
    finally:
        os.unlink(chemin)


# ── Task 1 : normalisation + mapping ─────────────────────────────────────────

def test_normaliser_nom():
    assert normaliser_nom('Résistance  Trad') == 'resistance trad'
    assert normaliser_nom('  CONDO CMS ') == 'condo cms'


@pytest.mark.parametrize('nom, type_attendu', [
    ('resistance trad', 'R'), ('Resistance CMS', 'R'), ('pot', 'R'),
    ('THERMISTANCE', 'R'), ('VARISTANCE', 'R'),
    ('condo', 'C'), ('Condo CMS', 'C'),
    ('inductance', 'L'),
    ('DIODE', 'D'), ('ZENER', 'D'),
    ('npn', 'Q'), ('Transistor NPN', 'Q'), ('Transistor PNP', 'Q'),
    ('mosfet', 'M'), ('mosfet p', 'M'),
    ('FUSIBLE', 'F'), ('RELAIS 2RT', 'K'),
])
def test_mapper_nom_familles(nom, type_attendu):
    correspondance = mapper_nom(nom)
    assert correspondance is not None, f'{nom!r} devrait être mappé'
    assert correspondance[0] == type_attendu


def test_mapper_nom_puce_catalogue():
    # NE555 n'est pas dans la table ERetroDesign : reconnu via identifier()
    assert mapper_nom('NE555') == ('U', {})


def test_mapper_nom_inconnu():
    assert mapper_nom('transfo') is None
    assert mapper_nom('') is None


def test_import_npn_broches_pnumber():
    # npn.xml réel : Pname VIDE, Pnumber = B/C/E → les broches doivent
    # s'appeler B/C/E (préférence Pnumber sur Pname).
    xml = _boardsch(
        [_item('npn', pins=[_pin(refs=['0_0_0_0'], pnumber='B'),
                            _pin(pnumber='C'), _pin(pnumber='E')], comp_id=0),
         _item('resistance trad', value='10k',
               pins=[_pin(refs=['1_0_1_0']), _pin()], comp_id=1)],
        [_fil('0_0_0_0', '1_0_1_0')],
    )
    comps = _lire(xml)
    q = next(c for c in comps if c.type == 'Q')
    r = next(c for c in comps if c.type == 'R')
    assert set(q.pins) == {'B', 'C', 'E'}
    # passif ERetroDesign : broches anonymes → numérotées par position
    assert set(r.pins) == {'1', '2'}
    # la base du transistor et la broche 1 de la résistance partagent un net
    assert q.pins['B'] == r.pins['1']


def test_import_diode_plan_anode_cathode():
    # DIODE.xml réel : Pnumber = 1/2 → plan '1'→A, '2'→K
    xml = _boardsch(
        [_item('DIODE', pins=[_pin(pnumber='1', pname='ANODE'),
                              _pin(pnumber='2', pname='CATHODE')])],
        [],
    )
    comps = _lire(xml)
    d = next(c for c in comps if c.type == 'D')
    assert set(d.pins) == {'A', 'K'}


def test_import_inconnu_reste_boite_x():
    xml = _boardsch([_item('transfo', pins=[_pin(), _pin(), _pin(), _pin()])], [])
    comps = _lire(xml)
    x = next(c for c in comps if c.type == 'X')
    assert len(x.pins) == 4
    assert any('transfo' in w for w in comps.warnings)
```

- [ ] **Step 2: Vérifier RED**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'circuit_analyzer.eretro'`.

- [ ] **Step 3: Créer `circuit_analyzer/eretro.py`**

```python
"""
@file eretro.py
@brief Import des fichiers réels ERetroDesign (éditeur C# maison de l'entreprise).

Spécificités des vrais fichiers BoardSCH par rapport au dialecte natif produit
par generer_xml : refs de connexion historiques concaténées sans underscore,
puces composées (CCmpntL), noms de bibliothèque français, broches identifiées
par Pnumber (Pname souvent vide, parfois les deux absents), champ <typ> = code
ASCII du char C#.

Règle d'or (spec 2026-07-17 §3) : la connexité se résout par ÉGALITÉ DE
CHAÎNES entre datapin/NodeL et Line.CFirst/CLast — on ne parse JAMAIS le
format packé des refs (ambigu dans les vieux fichiers : '14001' est
indécodable sans les largeurs de champs).
"""
import unicodedata


def normaliser_nom(nom: str) -> str:
    """@brief Nom de bibliothèque canonique : minuscules, sans accents,
    espaces repliés — « Résistance  Trad » == « resistance trad ».

    @param nom Nom brut lu dans le fichier.
    @return str Clé normalisée pour _MAPPING_ERETRO.
    """
    sans_accents = ''.join(c for c in unicodedata.normalize('NFD', nom)
                           if unicodedata.category(c) != 'Mn')
    return ' '.join(sans_accents.lower().split())


_PLAN_D = {'A': 'A', 'K': 'K', '1': 'A', '2': 'K',
           'ANODE': 'A', 'CATHODE': 'K'}
_PLAN_Q = {'B': 'B', 'C': 'C', 'E': 'E'}
_PLAN_M = {'G': 'G', 'D': 'D', 'S': 'S'}

# Table des noms de bibliothèque ERetroDesign → (type, plan de broches).
# plan None = broches numérotées par POSITION ('1', '2', …) : les libs des
# passifs ERetroDesign n'ont ni Pname ni Pnumber sur leurs broches.
# NPN et PNP mappent tous deux vers Q : les détecteurs déduisent la polarité
# de la topologie (collecteur au rail vs masse), pas d'un champ.
_MAPPING_ERETRO = {
    'resistance trad': ('R', None), 'resistance cms': ('R', None),
    'pot': ('R', None), 'thermistance': ('R', None), 'varistance': ('R', None),
    'condo': ('C', None), 'condo cms': ('C', None),
    'inductance': ('L', None),
    'diode': ('D', _PLAN_D), 'zener': ('D', _PLAN_D), 'led': ('D', _PLAN_D),
    'npn': ('Q', _PLAN_Q), 'transistor npn': ('Q', _PLAN_Q),
    'transistor pnp': ('Q', _PLAN_Q),
    'mosfet': ('M', _PLAN_M), 'mosfet p': ('M', _PLAN_M),
    'mosfet p1': ('M', _PLAN_M),
    'fusible': ('F', None),
    'relais 2rt': ('K', {}),
}


def mapper_nom(nom: str):
    """@brief (type, plan) pour un nom de bibliothèque ERetroDesign, ou None.

    Priorité : table exacte normalisée > catalogue de puces (identifier).
    Une puce du catalogue retourne ('U', {}) : plan vide = passthrough des
    numéros de broches, l'aliasing catalogue (appliquer_catalogue) tourne
    après la lecture comme pour les formes PuceN natives.

    @param nom Nom brut lu dans <Name>.
    @return tuple|None (type, plan) ou None si vraiment inconnu.
    """
    if not nom:
        return None
    cle = normaliser_nom(nom)
    if cle in _MAPPING_ERETRO:
        return _MAPPING_ERETRO[cle]
    from circuit_analyzer.catalogue import identifier
    if identifier('U', nom) is not None:
        return ('U', {})
    return None
```

- [ ] **Step 4: Brancher dans `lire_xml`**

Dans `circuit_analyzer/xml.py` :

4a. En tête de fichier, avec les autres imports du module :

```python
from circuit_analyzer import eretro
```

4b. Étape 1 — remplacer la lecture des broches (actuellement la compréhension
`broches = [{'pname': (dp.findtext('Pname') or '').strip()} …]`, ~l.1125-1126) par :

```python
        broches = []
        for pidx, dp in enumerate(item.findall('.//datapin/DataPin')):
            pnum = (dp.findtext('Pnumber') or '').strip()
            pnom = (dp.findtext('Pname') or '').strip()
            # ERetroDesign : l'identité de broche vit dans Pnumber (Pname
            # souvent vide) ; les passifs n'ont ni l'un ni l'autre →
            # numérotation par position pour ne pas écraser les clés.
            broches.append({'pname': pnum or pnom or str(pidx + 1)})
```

(Non-régression : notre dialecte écrit `Pnumber` == `Pname`, résultat identique.)

4c. Étape 5 — remplacer le début de la boucle par composant (l'actuel
`if nom not in _NOM_VERS_TYPE:` l.1231 et le déballage `type_prefix, plan = _NOM_VERS_TYPE[nom]` l.1245) par :

```python
        correspondance = _NOM_VERS_TYPE.get(nom) or eretro.mapper_nom(nom)
        if correspondance is None:
            # Composant inconnu : on le garde sous type 'X' pour ne pas perdre ses connexions
            compteurs_type['X'] = compteurs_type.get('X', 0) + 1
            ref = f'X{compteurs_type["X"]}'
            broches = {}
            for pidx, info_b in enumerate(elem['pins']):
                net = broche_vers_net.get((cid, pidx), 'NC')
                broches[str(pidx + 1)] = net
            composants.append(Component(ref=ref, type='X', pins=broches, value=elem['value']))
            composants.warnings.append(
                f"Composant inconnu '{nom}' (id={cid}) → gardé comme {ref} (type X)"
            )
            continue

        type_prefix, plan = correspondance
```

4d. Toujours Étape 5 — dans la boucle des broches du composant reconnu
(l.1249-1253), gérer le plan positionnel (`plan is None`) :

```python
        broches = {}
        for pidx, info_b in enumerate(elem['pins']):
            pnom = info_b['pname']
            # plan None (passif ERetroDesign) : broches par position.
            broche_lib = str(pidx + 1) if plan is None else plan.get(pnom, pnom)
            net = broche_vers_net.get((cid, pidx), 'NC')
            broches[broche_lib] = net
```

Et adapter les deux usages suivants de `plan` (l.1259 `if type_prefix == 'U' and plan:`
et l.1270 `] if plan else []`) — ils traitent déjà le plan vide `{}` comme « pas de
plan nommé » ; `None` doit suivre le même chemin : remplacer par
`if type_prefix == 'U' and plan:` (inchangé, `None` est falsy) et `] if plan else []`
(inchangé). Vérifier qu'aucun autre usage de `plan` ne suppose un dict.

- [ ] **Step 5: Vérifier GREEN + suite complète**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro.py -q` → PASS.
Run: `PYTHONUTF8=1 python -m pytest -q` → verte intégrale (budget ~5 min).

- [ ] **Step 6: Commit**

```bash
git add circuit_analyzer/eretro.py circuit_analyzer/xml.py tests/test_eretro.py
git commit -m "feat(eretro): mapping des noms de bibliotheque ERetroDesign et broches Pnumber/positionnelles"
```

---

### Task 2: Connexité par égalité NodeL + indexation par position

**Files:**
- Modify: `circuit_analyzer/xml.py` (Étape 1 ~l.1113-1127, Étape 2 arêtes ~l.1163-1170, création des warnings)
- Test: `tests/test_eretro.py` (étendre)

**Interfaces:**
- Consumes: helper `_lire`/fixtures de Task 1.
- Produces: `elements` indexé par POSITION dans `CmpntL` (plus par `<id>`), chaque broche porte `'refs': list[str]` (contenu de `NodeL`). Une liste `avertissements: list[str]` collectée pendant la lecture puis versée dans `composants.warnings` à l'Étape 5. Task 3 s'appuie sur ces structures.

- [ ] **Step 1: Tests RED**

Ajouter à `tests/test_eretro.py` :

```python
# ── Task 2 : connexité par égalité NodeL, indexation par position ────────────

def test_connexite_refs_sans_underscore():
    # Vieux format réel (SaveDiag.xml) : refs concaténées '1001'/'2011' —
    # indécodables par parsing, résolues par égalité avec NodeL.
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['1001']), _pin()], comp_id=0),
         _item('condo', pins=[_pin(refs=['2011']), _pin()], comp_id=0)],
        [_fil('1001', '2011')],
    )
    comps = _lire(xml)
    r = next(c for c in comps if c.type == 'R')
    c = next(c for c in comps if c.type == 'C')
    assert r.pins['1'] == c.pins['1']          # même net
    assert r.pins['1'].startswith('NET')


def test_id_zero_partout_indexation_par_position():
    # 41 composants id=0 dans TestDiagram.xml : la clé <id> écraserait tout.
    xml = _boardsch(
        [_item('resistance trad', value='1k',
               pins=[_pin(refs=['A']), _pin()], comp_id=0),
         _item('resistance trad', value='2k',
               pins=[_pin(refs=['B']), _pin()], comp_id=0),
         _item('resistance trad', value='3k',
               pins=[_pin(refs=['C']), _pin()], comp_id=0)],
        [_fil('A', 'B'), _fil('B', 'C')],
    )
    comps = _lire(xml)
    rs = [c for c in comps if c.type == 'R']
    assert len(rs) == 3                        # aucun composant écrasé
    assert {r.value for r in rs} == {'1k', '2k', '3k'}
    # les trois broches 1 sont sur le même net via les deux fils
    assert len({r.pins['1'] for r in rs}) == 1


def test_fil_non_resolu_warning_sans_exception():
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['OK']), _pin()])],
        [_fil('OK', 'REF_FANTOME')],
    )
    comps = _lire(xml)
    assert len([c for c in comps if c.type == 'R']) == 1
    assert any('REF_FANTOME' in w for w in comps.warnings)


def test_dialecte_natif_round_trip_inchange():
    # Non-régression ciblée : un fichier produit par notre générateur donne
    # les mêmes nets qu'avant (la suite complète reste le vrai garde-fou).
    from circuit_analyzer.xml_generator import BoardSCHGenerator
    g = BoardSCHGenerator()
    r1 = g.add('Résistance', '10k')
    c1 = g.add('Capa', '100n')
    g.connect(r1, '1', c1, '+')
    comps = _lire(g.to_xml())
    r = next(c for c in comps if c.type == 'R')
    c = next(c for c in comps if c.type == 'C')
    assert r.pins['1'] == c.pins['1']
```

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro.py -q`
Expected: les 3 premiers FAIL (refs non résolues / composants écrasés / pas de
warning), le round-trip PASS déjà.

- [ ] **Step 2: Implémenter dans `lire_xml`**

2a. Étape 1 — indexation par position et collecte des refs NodeL. Remplacer le
bloc actuel (l.1113-1127, y compris le `continue` sur `<id>` manquant) par :

```python
    # Étape 1 : extraire tous les composants du fichier.
    # Indexation par POSITION dans CmpntL (sémantique du C# ERetroDesign) :
    # les vrais fichiers portent des <id> dupliqués (id=0 partout) qui
    # écraseraient les entrées d'un dict indexé par id.
    avertissements: list = []
    elements: Dict[int, dict] = {}
    for idx, item in enumerate(racine.findall('.//CmpntL/DataItem')):
        nom    = (item.findtext('Name') or '').strip()
        valeur = (item.findtext('value') or '').strip()
        broches = []
        for pidx, dp in enumerate(item.findall('.//datapin/DataPin')):
            pnum = (dp.findtext('Pnumber') or '').strip()
            pnom = (dp.findtext('Pname') or '').strip()
            refs = [(s.text or '').strip() for s in dp.findall('NodeL/string')]
            broches.append({'pname': pnum or pnom or str(pidx + 1),
                            'refs': [r for r in refs if r]})
        elements[idx] = {'id': idx, 'name': nom, 'value': valeur, 'pins': broches}
```

2b. Étape 2 — résolution des arêtes par égalité de chaînes, fallback parsing.
Remplacer la boucle des fils (l.1163-1170) par :

```python
    # Index {chaîne de ref NodeL → (composant, broche)} : la connexité
    # ERetroDesign se résout par égalité de chaînes (règle du C# lui-même),
    # jamais en parsant le format packé (ambigu dans les vieux fichiers).
    ref_vers_broche: Dict[str, tuple] = {}
    for cid, comp in elements.items():
        for pidx, b in enumerate(comp['pins']):
            for r in b['refs']:
                ref_vers_broche.setdefault(r, (cid, pidx))

    def resoudre_extremite(ref):
        """@brief (composant, broche) pour une extrémité de fil, ou None.

        Égalité NodeL d'abord ; fallback sur le format i_j_u_v (dialecte
        natif sans NodeL) avec garde d'existence.

        @param ref Chaîne CFirst/CLast brute.
        @return tuple|None (cid, pidx) valide, ou None si irrésoluble.
        """
        if not ref:
            return None
        broche = ref_vers_broche.get(ref)
        if broche is not None:
            return broche
        try:
            cid, pidx = _analyser_ref_noeud(ref)
        except ValueError:
            return None
        if cid in elements and 0 <= pidx < len(elements[cid]['pins']):
            return (cid, pidx)
        return None

    for fil in racine.findall('.//lineL/Line'):
        cf = (fil.findtext('CFirst') or '').strip()
        cl = (fil.findtext('CLast') or '').strip()
        bf, bl = resoudre_extremite(cf), resoudre_extremite(cl)
        if bf is not None and bl is not None:
            unir(bf, bl)
        elif cf or cl:
            avertissements.append(
                f"Fil non résolu : CFirst={cf!r}, CLast={cl!r}"
            )
```

2c. Étape 5 — juste après la création `composants = ListeComposantsXML()`
(l.1220), verser les avertissements collectés :

```python
    composants = ListeComposantsXML()
    composants.warnings.extend(avertissements)
```

- [ ] **Step 3: GREEN + suite complète**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro.py -q` → PASS.
Run: `PYTHONUTF8=1 python -m pytest -q` → verte intégrale. Attention
particulière à `tests/test_xml_generator.py` et `tests/test_tab_draw_pattern.py`
(round-trip du dialecte natif).

- [ ] **Step 4: Commit**

```bash
git add circuit_analyzer/xml.py tests/test_eretro.py
git commit -m "feat(eretro): connexite par egalite NodeL et indexation par position (vieux formats de refs supportes)"
```

---

### Task 3: Aplatissement des puces composées (CCmpntL)

**Files:**
- Modify: `circuit_analyzer/eretro.py` (ajouter `extraire_composes`)
- Modify: `circuit_analyzer/xml.py` (intégration après l'Étape 1 ; refs `U3.n` et `groupes_puces` à l'Étape 5 ; `ListeComposantsXML.groupes_puces`)
- Test: `tests/test_eretro.py` (étendre)

**Interfaces:**
- Consumes: structures `elements`/`avertissements` de Task 2, `mapper_nom` de Task 1.
- Produces: `extraire_composes(racine, prochain_idx: int) -> tuple[dict, list, list]` = `(elements_sup, fils_sup, avertissements)` où `elements_sup` a la même forme que `elements` avec en plus les clés `'emettre': bool` et `'puce': tuple[int, str] | None` ; `fils_sup` = `list[tuple[str, str]]` (CFirst, CLast). `ListeComposantsXML` gagne `.groupes_puces: dict[str, str]` (ref boîtier → nom de puce).

- [ ] **Step 1: Tests RED**

Ajouter à `tests/test_eretro.py` :

```python
# ── Task 3 : puces composées ─────────────────────────────────────────────────

def _ccomp(name, pins_ext=(), items_int=(), fils_int=()):
    """@brief Fragment <CComp> : boîtier + items internes (DItemL) + fils internes (CCLine)."""
    return (f'  <CComp>\n'
            f'    <Name>{name}</Name><value />\n'
            f'    <datapin>\n' + '\n'.join(pins_ext) + '\n    </datapin>\n'
            f'    <id>0</id>\n'
            f'    <DItemL>\n' + '\n'.join(items_int) + '\n    </DItemL>\n'
            f'    <CCLine>\n' + '\n'.join(fils_int) + '\n    </CCLine>\n'
            f'  </CComp>')


def test_compose_aplati_en_items_internes():
    # Une « puce » de 2 transistors internes reliés par un fil interne ; la
    # broche externe est fusionnée au réseau interne par la ref X partagée
    # (X1 apparaît dans le NodeL externe ET comme extrémité de CCLine).
    ccomp = _ccomp(
        'MODHYB',
        pins_ext=[_pin(refs=['T0000', 'X1'])],
        items_int=[
            _item('npn', pins=[_pin(refs=['X1'], pnumber='B'),
                               _pin(refs=['C10'], pnumber='C'),
                               _pin(pnumber='E')]),
            _item('npn', pins=[_pin(refs=['C11'], pnumber='B'),
                               _pin(pnumber='C'), _pin(pnumber='E')]),
        ],
        fils_int=[_fil('C10', 'C11')],
    )
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['R00']), _pin()])],
        [_fil('R00', 'T0000')],
        ccomps=ccomp,
    )
    comps = _lire(xml)
    internes = [c for c in comps if '.' in c.ref]
    assert len(internes) == 2
    assert all(c.type == 'Q' for c in internes)
    assert comps.groupes_puces == {internes[0].ref.split('.')[0]: 'MODHYB'}
    # le signal traverse le boîtier : R → broche externe → X1 → base interne
    r = next(c for c in comps if c.type == 'R')
    q1 = next(c for c in internes if c.ref.endswith('.1'))
    assert r.pins['1'] == q1.pins['B']
    # le fil interne relie le collecteur de Q.1 à la base de Q.2
    q2 = next(c for c in internes if c.ref.endswith('.2'))
    assert q1.pins['C'] == q2.pins['B']


def test_compose_sans_interieur_devient_boite_noire():
    ccomp = _ccomp('MYSTERE', pins_ext=[_pin(refs=['T0000']), _pin()])
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['R00']), _pin()])],
        [_fil('R00', 'T0000')],
        ccomps=ccomp,
    )
    comps = _lire(xml)
    boite = next(c for c in comps if c.ref.startswith('X') or c.type == 'U')
    assert len(boite.pins) == 2
    assert any('MYSTERE' in w for w in comps.warnings)
    # la connexion externe est conservée
    r = next(c for c in comps if c.type == 'R')
    assert r.pins['1'] in boite.pins.values()
```

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro.py -q`
Expected: les 2 nouveaux FAIL (`AttributeError: groupes_puces` / composés ignorés).

- [ ] **Step 2: Implémenter `extraire_composes` dans `eretro.py`**

```python
def _lire_broches(item_et):
    """@brief Broches d'un DataItem/CComp ElementTree, même forme que lire_xml.

    ATTENTION : chemins DIRECTS ('datapin/DataPin', pas './/') — un CComp
    contient des DataItem internes dont les broches ne doivent pas fuir dans
    celles du boîtier.

    @param item_et Élément <DataItem> ou <CComp>.
    @return list[dict] [{'pname': str, 'refs': list[str]}].
    """
    broches = []
    for pidx, dp in enumerate(item_et.findall('datapin/DataPin')):
        pnum = (dp.findtext('Pnumber') or '').strip()
        pnom = (dp.findtext('Pname') or '').strip()
        refs = [(s.text or '').strip() for s in dp.findall('NodeL/string')]
        broches.append({'pname': pnum or pnom or str(pidx + 1),
                        'refs': [r for r in refs if r]})
    return broches


def extraire_composes(racine, prochain_idx):
    """@brief Aplatit les puces composées (CCmpntL) d'un BoardSCH réel.

    Décision spec §4 : DÉPLIER — les items internes deviennent des composants
    à part entière ; le boîtier reste un pseudo-composant NON émis dont les
    broches externes participent à l'Union-Find (les refs X partagées entre
    NodeL externe et fils internes fusionnent les nets à travers le boîtier).
    Un composé sans intérieur lisible dégrade en boîte noire émise (jamais
    d'exception).

    @param racine Élément racine <BoardSCH> parsé.
    @param prochain_idx Premier index libre après les composants de CmpntL.
    @return tuple (elements_sup, fils_sup, avertissements) :
        elements_sup dict[int, dict] — entrées au format de lire_xml Étape 1,
        enrichies de 'emettre' (bool) et 'puce' ((num, nom) ou None) ;
        fils_sup list[(CFirst, CLast)] — fils internes CCLine ;
        avertissements list[str].
    """
    elements_sup, fils_sup, avertissements = {}, [], []
    idx = prochain_idx
    for num, cc in enumerate(racine.findall('.//CCmpntL/CComp')):
        nom_puce = (cc.findtext('Name') or '').strip() or f'Compose{num + 1}'
        valeur   = (cc.findtext('value') or '').strip()
        items_internes = cc.findall('DItemL/DataItem')
        if not items_internes:
            # Boîte noire : émise telle quelle avec ses broches externes.
            elements_sup[idx] = {'id': idx, 'name': nom_puce, 'value': valeur,
                                 'pins': _lire_broches(cc),
                                 'emettre': True, 'puce': None}
            idx += 1
            avertissements.append(
                f"Puce composée '{nom_puce}' sans intérieur lisible → boîte noire"
            )
            continue
        # Boîtier pass-through : broches dans l'Union-Find, composant non émis.
        elements_sup[idx] = {'id': idx, 'name': nom_puce, 'value': valeur,
                             'pins': _lire_broches(cc),
                             'emettre': False, 'puce': None}
        idx += 1
        for item in items_internes:
            nom_int = (item.findtext('Name') or '').strip()
            val_int = (item.findtext('value') or '').strip()
            elements_sup[idx] = {'id': idx, 'name': nom_int, 'value': val_int,
                                 'pins': _lire_broches(item),
                                 'emettre': True, 'puce': (num, nom_puce)}
            idx += 1
        for fil in cc.findall('CCLine/Line'):
            cf = (fil.findtext('CFirst') or '').strip()
            cl = (fil.findtext('CLast') or '').strip()
            if cf or cl:
                fils_sup.append((cf, cl))
    return elements_sup, fils_sup, avertissements
```

- [ ] **Step 3: Intégrer dans `lire_xml`**

3a. `ListeComposantsXML.__init__` (l.1059-1066) — ajouter l'attribut :

```python
        self.warnings: list[str] = []
        self.groupes_puces: dict[str, str] = {}
```

3b. Juste après l'Étape 1 :

```python
    # Étape 1 bis : puces composées ERetroDesign (CCmpntL) — dépliées.
    elements_cc, fils_cc, avert_cc = eretro.extraire_composes(racine, len(elements))
    elements.update(elements_cc)
    avertissements.extend(avert_cc)
```

3c. Étape 2 — après la boucle `for fil in racine.findall('.//lineL/Line')`,
traiter les fils internes avec la même résolution :

```python
    for cf, cl in fils_cc:
        bf, bl = resoudre_extremite(cf), resoudre_extremite(cl)
        if bf is not None and bl is not None:
            unir(bf, bl)
        elif cf or cl:
            avertissements.append(
                f"Fil interne de puce non résolu : CFirst={cf!r}, CLast={cl!r}"
            )
```

3d. Étape 5 — au début de la boucle `for cid in sorted(elements):`, gérer les
marqueurs des composés (avant le test `_NOMS_ALIMENTATION`) :

```python
        elem = elements[cid]
        nom  = elem['name']

        # Boîtier de puce composée : pass-through Union-Find, non émis.
        if elem.get('emettre') is False:
            continue
```

3e. Étape 5 — pour les items internes (clé `'puce'` non nulle), la référence
est `<ref_boîtier>.<n>` et le nom de puce est enregistré. Juste après le
déballage `type_prefix, plan = correspondance` (et le bloc X inconnu — les
items internes inconnus type X doivent AUSSI porter la ref préfixée), gérer
la ref ainsi — introduire avant la boucle des composants :

```python
    refs_puces: Dict[int, str] = {}     # num composé → ref boîtier ('U7')
    compteurs_internes: Dict[int, int] = {}
```

puis, à l'endroit où la ref est générée (branche inconnue ET branche connue),
remplacer la génération `ref = f'{type_prefix}{compteurs_type[type_prefix]}'`
(et son équivalent X) par :

```python
        puce = elem.get('puce')
        if puce is not None:
            num_puce, nom_puce = puce
            if num_puce not in refs_puces:
                compteurs_type['U'] = compteurs_type.get('U', 0) + 1
                refs_puces[num_puce] = f'U{compteurs_type["U"]}'
                composants.groupes_puces[refs_puces[num_puce]] = nom_puce
            compteurs_internes[num_puce] = compteurs_internes.get(num_puce, 0) + 1
            ref = f'{refs_puces[num_puce]}.{compteurs_internes[num_puce]}'
        else:
            compteurs_type[type_prefix] = compteurs_type.get(type_prefix, 0) + 1
            ref = f'{type_prefix}{compteurs_type[type_prefix]}'
```

(dans la branche inconnue, `type_prefix` vaut `'X'` — même logique, le compteur
X ne s'incrémente que pour les non-internes).

- [ ] **Step 4: GREEN + suite complète**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro.py -q` → PASS.
Run: `PYTHONUTF8=1 python -m pytest -q` → verte intégrale (notre dialecte écrit
`<CCmpntL />` vide → `extraire_composes` retourne des structures vides,
comportement natif inchangé).

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/eretro.py circuit_analyzer/xml.py tests/test_eretro.py
git commit -m "feat(eretro): puces composees CCmpntL depliees (items internes reels, fusion X-refs, groupes_puces)"
```

---

### Task 4: Alimentations par champ typ (G/V/N)

**Files:**
- Modify: `circuit_analyzer/eretro.py` (ajouter `classer_rail`)
- Modify: `circuit_analyzer/xml.py` (Étape 1 : lecture `<typ>` ; `nom_net` ; exclusion Étape 5)
- Test: `tests/test_eretro.py` (étendre)

**Interfaces:**
- Consumes: structures de Task 2 ; `is_power`/`is_gnd` de `circuit_analyzer.patterns.base`.
- Produces: `classer_rail(typc: str, valeur: str, nb_broches: int) -> str | None` (nom de net rail ou None). `elements[idx]['rail']` pré-calculé à l'Étape 1.

- [ ] **Step 1: Tests RED**

Ajouter à `tests/test_eretro.py` :

```python
# ── Task 4 : alimentations par champ typ ─────────────────────────────────────

def test_alim_typ_g_devient_gnd():
    # <typ> = code ASCII du char C# : 71 = 'G' (masse ERetroDesign).
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['R01']), _pin(refs=['R02'])]),
         _item('MASSE1', pins=[_pin(refs=['G01'])], typ=71)],
        [_fil('R02', 'G01')],
    )
    comps = _lire(xml)
    r = next(c for c in comps if c.type == 'R')
    assert r.pins['2'] == 'GND'
    # le symbole d'alim n'est pas un composant
    assert all('MASSE1' != getattr(c, 'value', '') for c in comps)
    assert len([c for c in comps if c.type != 'R']) == 0


def test_alim_typ_v_devient_vcc():
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['R01']), _pin(refs=['R02'])]),
         _item('ALIM1', pins=[_pin(refs=['V01'])], typ=86)],   # 86 = 'V'
        [_fil('R01', 'V01')],
    )
    comps = _lire(xml)
    r = next(c for c in comps if c.type == 'R')
    assert r.pins['1'] == 'VCC'


def test_alim_typ_v_avec_rail_nomme_dans_value():
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['R01']), _pin(refs=['R02'])]),
         _item('ALIM1', value='+12V', pins=[_pin(refs=['V01'])], typ=86)],
        [_fil('R01', 'V01')],
    )
    comps = _lire(xml)
    r = next(c for c in comps if c.type == 'R')
    assert r.pins['1'] == '+12V'


def test_typ_v_deux_broches_reste_composant():
    # Garde anti-faux-positif : 2 broches = pas un symbole de rail (un vrai
    # composant peut porter typ 'V' par accident d'encodage ord(nom[0])).
    xml = _boardsch(
        [_item('VARISTANCE', pins=[_pin(), _pin()], typ=86)],
        [],
    )
    comps = _lire(xml)
    assert len(comps) == 1
    assert comps[0].type == 'R'    # mappé par Task 1, pas avalé comme rail
```

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro.py -q` → les 3 premiers FAIL.

- [ ] **Step 2: Implémenter**

2a. `eretro.py` — ajouter :

```python
def classer_rail(typc, valeur, nb_broches):
    """@brief Nom de net rail pour un symbole d'alimentation ERetroDesign, ou None.

    Le C# marque les alims par le char typ : 'G' (masse), 'V' (alim
    positive), 'N' (alim négative). Garde : un seul point de connexion —
    un composant 2 broches n'est jamais un symbole de rail (le typ natif
    est parfois ord(nom[0]), donc 'V' peut apparaître par accident).

    @param typc Char typ décodé ('' si absent).
    @param valeur Champ <value> (peut nommer le rail : '+12V', 'VMOT'…).
    @param nb_broches Nombre de broches du composant.
    @return str|None Nom de net ('GND', 'VCC', 'VSS', ou rail nommé), ou None.
    """
    if nb_broches != 1 or typc not in ('G', 'V', 'N'):
        return None
    if typc == 'G':
        return 'GND'
    from circuit_analyzer.patterns.base import is_gnd, is_power
    val = (valeur or '').lstrip('/').upper()
    if val and (is_power(val) or is_gnd(val)):
        return val
    return 'VCC' if typc == 'V' else 'VSS'
```

2b. `xml.py` Étape 1 — après la construction de `broches`, lire `<typ>` et
classer :

```python
        typ_txt = (item.findtext('typ') or '').strip()
        typc = chr(int(typ_txt)) if typ_txt.isdigit() and 0 < int(typ_txt) < 0x110000 else ''
        elements[idx] = {'id': idx, 'name': nom, 'value': valeur, 'pins': broches,
                         'rail': eretro.classer_rail(typc, valeur, len(broches))}
```

2c. `xml.py` `nom_net` — dans la boucle des membres du net (l.1192, après les
vérifications par nom existantes, avant le `norm = cnom.lstrip('/')…`), ajouter :

```python
            rail = elements[cid].get('rail')
            if rail:
                racine_vers_net[cle] = rail; return rail
```

2d. `xml.py` Étape 5 — juste après le test `_NOMS_ALIMENTATION` existant :

```python
        # Symboles d'alimentation ERetroDesign (typ G/V/N, 1 broche)
        if elem.get('rail'):
            continue
```

2e. Les entrées produites par `extraire_composes` (Task 3) n'ont pas de clé
`'rail'` — `elem.get('rail')` retourne `None`, aucun changement nécessaire ;
le vérifier en relisant le code.

- [ ] **Step 3: GREEN + suite complète**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro.py -q` → PASS.
Run: `PYTHONUTF8=1 python -m pytest -q` → verte intégrale (notre dialecte passe
par les noms `_NOMS_ALIMENTATION` AVANT le rail typ — ordre inchangé).

- [ ] **Step 4: Commit**

```bash
git add circuit_analyzer/eretro.py circuit_analyzer/xml.py tests/test_eretro.py
git commit -m "feat(eretro): rails GND/VCC/VSS depuis le champ typ C# (G/V/N, garde 1 broche)"
```

---

### Task 5: Corpus réel + bandeau d'avertissements GUI + boucle visuelle + clôture

**Files:**
- Create: `tests/test_eretro_corpus.py`
- Modify: `gui/tab_analyze.py` (`_build` ~l.135-152, `_analyze` ~l.294 et chemins d'erreur)
- Modify: `.superpowers/sdd/progress.md` (append)

**Interfaces:**
- Consumes: tout Task 1-4 ; corpus réel en lecture seule.
- Produces: chantier complet, prêt pour la revue finale.

- [ ] **Step 1: Tests d'intégration RED**

Créer `tests/test_eretro_corpus.py` :

```python
"""
@file test_eretro_corpus.py
@brief Intégration : import des VRAIS fichiers ERetroDesign du corpus
(SolutionERetroDesignX20260813, lecture seule — ne jamais modifier ni
committer ce dossier).
"""
import time
from pathlib import Path

import pytest

from circuit_analyzer.xml import lire_xml
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns

CORPUS = (Path(__file__).resolve().parent.parent
          / 'SolutionERetroDesignX20260813' / 'ERetroDesign' / 'ERetroDesign'
          / 'bin' / 'Debug')

necessite_corpus = pytest.mark.skipif(
    not CORPUS.exists(), reason='corpus ERetroDesign absent de ce poste')


@necessite_corpus
def test_savediag_importe_et_analysable():
    # SaveDiag.xml : vieux format de refs concaténées, 6 composants, 6 fils.
    comps = lire_xml(str(CORPUS / 'SaveDiag.xml'))
    assert len(comps) >= 2
    graphe = build_graph(comps)
    match_patterns(graphe)          # aucune exception = contrat minimal
    # au moins un fil résolu : deux composants partagent un net
    nets = [n for c in comps for n in c.pins.values() if n != 'NC']
    assert len(nets) != len(set(nets)), 'aucun net partagé — connexité perdue'


@necessite_corpus
def test_diag2_importe_avec_composes():
    # Diag2.xml : 2 CComp, id=0 dupliqués, refs T…/X….
    comps = lire_xml(str(CORPUS / 'Diag2.xml'))
    assert len(comps) >= 2
    build_graph(comps)
    # les composés produisent soit des items internes (ref 'U*.n'),
    # soit des boîtes noires avec warning — jamais une disparition muette.
    refs_internes = [c.ref for c in comps if '.' in c.ref]
    assert refs_internes or comps.warnings


@necessite_corpus
def test_testdiagram_carte_reelle_sous_budget():
    # 2,4 Mo, 285 DataItem, 63 CComp, 41 id=0 : la vraie carte de l'entreprise.
    debut = time.monotonic()
    comps = lire_xml(str(CORPUS / 'TestDiagram.xml'))
    graphe = build_graph(comps)
    match_patterns(graphe)
    duree = time.monotonic() - debut
    assert len(comps) >= 100
    assert duree < 30, f'import+analyse en {duree:.1f}s (budget 30s)'
```

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_corpus.py -q`
Expected: PASS si Task 1-4 sont correctes — sinon les échecs ici sont des bugs
réels à corriger AVANT de continuer (TDD : ne jamais affaiblir une assertion
pour passer ; diagnostiquer). Ces tests sont le juge de paix du chantier.

- [ ] **Step 2: Bandeau d'avertissements dans l'onglet Analyser**

Dans `gui/tab_analyze.py` :

2a. `_build` — juste après la création de `self._stats_row` et de ses
StatCards (~l.140), créer le bandeau caché (mêmes tokens que le fichier,
AUCUN hex en dur) :

```python
        # Bandeau d'avertissements d'import (fichiers ERetroDesign réels) :
        # créé une fois, montré seulement si lire_xml a produit des warnings.
        self._warn_banner = ctk.CTkLabel(
            self.frame, text="", anchor="w", justify="left",
            text_color=ERROR, fg_color=BG, cursor="hand2")
        self._warn_banner.bind("<Button-1>", self._voir_warnings)
        self._warnings_import: list[str] = []
```

2b. Nouvelle méthode (à côté de `_analyze`) :

```python
    def _voir_warnings(self, _evt=None):
        """@brief Détail des avertissements d'import dans une boîte de dialogue."""
        if self._warnings_import:
            messagebox.showwarning(
                "Avertissements d'import",
                "\n".join(self._warnings_import[:60]))
```

2c. `_analyze` — dans le chemin de succès, juste après
`self._stats_row.pack(fill="x", padx=20, before=self._body)` (l.294) :

```python
            self._warnings_import = list(getattr(comps, 'warnings', []) or [])
            if self._warnings_import:
                self._warn_banner.configure(
                    text=f"⚠ {len(self._warnings_import)} avertissement(s) "
                         f"d'import — cliquer pour le détail")
                self._warn_banner.pack(fill="x", padx=20, before=self._body)
            else:
                self._warn_banner.pack_forget()
```

2d. Dans les TROIS chemins d'erreur de `_analyze` (l.307, 314, 322), à côté de
`self._stats_row.pack_forget()`, ajouter :

```python
            self._warn_banner.pack_forget()
```

- [ ] **Step 3: Suite complète**

Run: `PYTHONUTF8=1 python -m pytest -q` → verte intégrale (corpus inclus).

- [ ] **Step 4: Boucle visuelle (exigence boss)**

Script scratchpad (PAS commité) : ouvrir l'application réelle (`AppWindow`),
onglet Analyser, charger `Diag2.xml` puis `TestDiagram.xml` du corpus, lancer
l'analyse, capturer en PNG : (1) l'onglet avec le bandeau d'avertissements
visible, (2) les stats et les cartes de résultats, (3) le schéma d'un îlot
ouvert depuis les résultats (chemin de rendu existant). INSPECTER les PNG :
bandeau lisible et cliquable, aucun symbole en vrac, îlots cohérents avec la
carte. Tout défaut de rendu = fix TDD avant commit. Consigner le verdict
visuel (fichiers PNG + description) dans le rapport de tâche.

- [ ] **Step 5: Ledger + commit**

Append `.superpowers/sdd/progress.md` : section chantier import ERetroDesign
(commits, suite, corpus importé, verdict visuel, warnings typiques observés
sur TestDiagram.xml).

```bash
git add tests/test_eretro_corpus.py gui/tab_analyze.py .superpowers/sdd/progress.md
git commit -m "feat(eretro): corpus reel importe (SaveDiag/Diag2/TestDiagram) et bandeau d'avertissements dans l'onglet Analyser"
```

---

## Self-review (fait à l'écriture du plan)

- Spec §2 (architecture, un seul chemin) → T1-T4 modifient `lire_xml` en place,
  `eretro.py` pur ; §3 (égalité NodeL, fallback, warnings) → T2 ; §4
  (aplatissement, X-refs, boîte noire, groupes_puces) → T3 ; §5 (mapping,
  rails, inconnus X) → T1+T4 ; §6 (GUI bandeau) → T5 ; §7 (jamais d'exception)
  → warnings partout T2-T4 ; §8 tests 1-9 → T1-T4, tests 10-13 → T5 + suite ;
  boucle visuelle → T5.
- `_pin`/`_item`/`_fil`/`_boardsch`/`_lire` définis UNE fois (T1) et réutilisés.
- Signatures cohérentes : `mapper_nom` (T1) consommé T3/Étape 5 ;
  `extraire_composes(racine, prochain_idx)` (T3) ; `classer_rail(typc, valeur,
  nb_broches)` (T4) ; `resoudre_extremite` locale à `lire_xml` (T2) réutilisée
  T3 pour `fils_cc`.
- Ordre des étapes dans `lire_xml` après T4 : Étape 1 (position + Pnumber +
  NodeL + typ/rail) → 1 bis (composés) → 2 (résolution + fils internes) →
  3/4 (inchangées + rail dans nom_net) → 5 (rails exclus, boîtiers non émis,
  refs internes, mapping eretro, warnings versés).
- Piège documenté : chemins ElementTree DIRECTS dans `_lire_broches`
  (`datapin/DataPin`, pas `.//`) pour ne pas aspirer les broches internes des
  composés dans le boîtier.
- Le test T4 `test_typ_v_deux_broches_reste_composant` verrouille la garde
  anti-faux-positif (typ natif = parfois `ord(nom[0])`).
