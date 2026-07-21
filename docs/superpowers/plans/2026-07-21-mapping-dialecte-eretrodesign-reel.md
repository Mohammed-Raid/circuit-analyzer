# Mapping du dialecte ERetroDesign réel — Plan d'implémentation

> **Pour les workers agentiques :** SOUS-SKILL REQUISE : superpowers:subagent-driven-development pour exécuter ce plan tâche par tâche. Les étapes utilisent des cases à cocher (`- [ ]`).

**Goal :** Reconnaître par NOM les composants des vraies cartes ERetroDesign (résistances `R <code>` avec valeur décodée, transistors, connecteurs, ICs, condensateurs polarisés, photodiodes) que ni le mapping actuel ni la forme n'attrapent, pour passer de ~30 % à ~80 % de reconnaissance.

**Architecture :** On étend le mapping par NOM dans `circuit_analyzer/eretro.py` (`normaliser_nom`, `_MAPPING_ERETRO`, `mapper_nom`) + un décodeur de valeur R-code pur. Le rendu réutilise la boîte IC honnête (`gui/puce_schematic.py::dessiner_puce` via `_puce_ilot`) pour les connecteurs multi-broches et les ICs nommées, et `elm.Jumper` pour les connecteurs 2-broches. Non-régressif : les nouvelles règles ne se déclenchent qu'après échec des lookups exacts existants.

**Tech Stack :** Python (stdlib `re`), schemdraw ==0.22, pytest, PYTHONUTF8=1.

## Global Constraints

- Commits en FRANÇAIS, sans footer « Co-Authored-By »/« Generated with Claude ».
- Jamais `git add -A` — fichiers ajoutés un par un.
- `docs.rar`, `SolutionERetroDesignX20260813/` et **`CARTE POUR TESTER (VRAI TEST)/`** : LECTURE SEULE, JAMAIS committés/modifiés.
- `PYTHONUTF8=1` devant chaque python/pytest ; suite complète verte par tâche (~1760+ passed / 51 skipped ; flake connu `test_500_portes_sous_budget` → relancer isolé).
- schemdraw pinné ==0.22 ; canvas des schémas CLAIR ; **rendu schématique PNG rendu ET inspecté** après tout changement de dessin (livrable permanent, pas option).
- **« Jamais de vue générique fausse »** : toute famille reconnue produit un symbole/boîte honnête ; jamais un faux symbole ni un triangle d'AOP inventé.
- Non-régression : la forme/le nom ne sont consultés qu'après échec des lookups exacts ; le dialecte natif et l'échantillon Lib restent inchangés.

## File Structure

- `circuit_analyzer/eretro.py` (modifié) : `normaliser_nom` (underscore), `_MAPPING_ERETRO` (+2 entrées), `mapper_nom` (règles connecteur + R-code), nouveau `decoder_valeur_resistance` + helper `_ohms_vers_str`.
- `circuit_analyzer/composant.py` (modifié) : champ `Composant.boite_ic`.
- `circuit_analyzer/xml.py` (modifié, Étape 5) : valeur R-code, catch-all IC (≥3 broches nommées → U boîte), propagation `boite_ic` + nom→value.
- `circuit_analyzer/catalogue.py` (modifié) : entrée `78L05` non-aliasée.
- `gui/circuit_viewer.py` (modifié) : `_puce_ilot` (types U marqués + J multi-broches → boîte), `_schematic_symbol`/`_SYMBOL_ELM` (type J 2-broches → `elm.Jumper`).
- Tests : `tests/test_eretro.py`, `tests/test_eretro_forme.py` (ou nouveau `tests/test_eretro_dialecte.py`), `tests/test_puce_drawing.py`, `tests/test_cartes_reelles.py` (nouveau, oracle corpus réel).

---

### Task 1 : Décodeur de valeur R-code

**Files :**
- Modify : `circuit_analyzer/eretro.py`
- Test : `tests/test_eretro_dialecte.py` (créé ici)

**Interfaces :**
- Produces : `decoder_valeur_resistance(nom: str) -> str` — reçoit le NOM brut (`"R 810"`, `"R810"`, `"R 3R90"`, `"RINF"`), renvoie la valeur d'ingénierie à stocker dans `Composant.value` (`"81"`, `"1k"`, `"3.9"`, `"open"`), ou `""` si non-résistance. `_ohms_vers_str(ohms: float) -> str` (privé).

- [ ] **Step 1 : Test rouge**

```python
# tests/test_eretro_dialecte.py
import pytest
from circuit_analyzer.eretro import decoder_valeur_resistance


@pytest.mark.parametrize("nom, attendu", [
    ("R 810", "81"), ("R810", "81"),
    ("R 561", "560"), ("R 332", "3.3k"), ("R332", "3.3k"),
    ("R 1001", "1k"), ("R2001", "2k"), ("R 3903", "390k"),
    ("R5101", "5.1k"), ("R512", "5.1k"),
    ("R300", "30"), ("R2400", "240"), ("R 3300", "330"),
    ("R 3R90", "3.9"), ("R 60R4", "60.4"), ("R 47R0", "47"),
    ("RINF", "open"),
    ("R 308", "308"), ("R 30A", "30A"),   # indécodables/aberrants -> code brut
])
def test_decoder_valeur_resistance(nom, attendu):
    assert decoder_valeur_resistance(nom) == attendu
```

- [ ] **Step 2 : Vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_dialecte.py -q`
Expected : FAIL (`ImportError: cannot import name 'decoder_valeur_resistance'`).

- [ ] **Step 3 : Implémentation**

```python
# circuit_analyzer/eretro.py  (ajouter ; `import re` est déjà présent en tête —
# vérifier par grep, l'ajouter seulement s'il manque)
def _ohms_vers_str(ohms: float) -> str:
    """@brief Ohms -> chaîne d'ingénierie ('81', '3.3k', '390k')."""
    if ohms >= 1_000_000:
        s, suf = ohms / 1_000_000, 'M'
    elif ohms >= 1_000:
        s, suf = ohms / 1_000, 'k'
    else:
        s, suf = ohms, ''
    return f"{s:g}{suf}"


def decoder_valeur_resistance(nom: str) -> str:
    """@brief Valeur d'une résistance depuis son NOM ERetroDesign 'R <code>'.

    Notation résistance standard : EIA (dernier chiffre = multiplicateur),
    'R'-décimal (R = virgule), 'RINF' = non peuplée. Repli gracieux : un code
    indécodable ou aberrant (>100 MΩ) est rendu BRUT — jamais une valeur inventée.

    @param nom Nom brut ('R 810', 'R810', 'R 3R90', 'RINF').
    @return str Valeur pour Composant.value ('81', '1k', '3.9', 'open'), ou '' si pas une résistance.
    """
    code = re.sub(r'(?i)^r\s*', '', (nom or '').strip())
    if not code:
        return ''
    if code.upper() == 'INF':
        return 'open'
    m = re.fullmatch(r'(?i)(\d+)R(\d+)', code)      # 3R90 -> 3.9
    if m:
        return f"{m.group(1)}.{m.group(2)}".rstrip('0').rstrip('.')
    if code.isdigit() and len(code) >= 2:
        ohms = int(code[:-1]) * (10 ** int(code[-1]))
        if ohms <= 100_000_000:
            return _ohms_vers_str(ohms)
    return code                                     # aberrant/indécodable -> brut
```

- [ ] **Step 4 : Vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_dialecte.py -q`
Expected : PASS (19 cas).

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/eretro.py tests/test_eretro_dialecte.py
git commit -m "feat(eretro): decodeur de valeur des resistances R-code (EIA, R-decimal, RINF, repli brut)"
```

---

### Task 2 : Règles de nom (underscore, connecteurs, R-code, familles exactes)

**Files :**
- Modify : `circuit_analyzer/eretro.py` (`normaliser_nom`, `_MAPPING_ERETRO`, `mapper_nom`)
- Test : `tests/test_eretro_dialecte.py`

**Interfaces :**
- Consumes : `decoder_valeur_resistance` (Task 1).
- Produces : `mapper_nom(nom)` reconnaît désormais aussi `('R', None)` (R-code), `('J', None)` (connecteurs), `('Q', _PLAN_Q)` (Transistor_NPN via underscore), `('C', None)` (Condensateur_polarise), `('D', _PLAN_D)` (Photodiode). Nouveau type `'J'` = connecteur.

- [ ] **Step 1 : Test rouge**

```python
# tests/test_eretro_dialecte.py  (ajouter)
from circuit_analyzer.eretro import mapper_nom


@pytest.mark.parametrize("nom, type_attendu", [
    ("Transistor_NPN", "Q"),          # underscore : mappe via 'transistor npn'
    ("Condensateur_polarise", "C"),
    ("Photodiode", "D"),
    ("R 810", "R"), ("R810", "R"), ("RINF", "R"), ("R 30A", "R"),
    ("open connecter", "J"), ("JUMPER", "J"), ("jumper 2 broches", "J"),
    ("connecteur traversant", "J"), ("Borne", "J"),
])
def test_mapper_nom_dialecte_reel(nom, type_attendu):
    corr = mapper_nom(nom)
    assert corr is not None and corr[0] == type_attendu


@pytest.mark.parametrize("nom", ["RELAIS 2RT", "reset", "resistance trad"])
def test_mapper_nom_pas_de_faux_positif_r(nom):
    # 'RELAIS 2RT' -> K (exact), 'reset' -> None, 'resistance trad' -> R (exact) :
    # la règle R-code ne doit JAMAIS transformer ces noms en R via le préfixe.
    corr = mapper_nom(nom)
    if nom == "reset":
        assert corr is None
    elif nom == "RELAIS 2RT":
        assert corr[0] == "K"
    else:
        assert corr[0] == "R"
```

- [ ] **Step 2 : Vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_dialecte.py -q -k dialecte_reel`
Expected : FAIL (Transistor_NPN/Borne/R 810 → None aujourd'hui).

- [ ] **Step 3 : Implémentation**

Dans `circuit_analyzer/eretro.py` :

`normaliser_nom` — replier aussi les underscores en espaces (récupère `Transistor_NPN`) :
```python
def normaliser_nom(nom: str) -> str:
    sans_accents = ''.join(c for c in unicodedata.normalize('NFD', nom)
                           if unicodedata.category(c) != 'Mn')
    return ' '.join(sans_accents.replace('_', ' ').lower().split())
```

`_MAPPING_ERETRO` — ajouter 2 entrées (dans le dict existant) :
```python
    'condensateur polarise': ('C', None),
    'photodiode': ('D', _PLAN_D),
```

`mapper_nom` — insérer les règles APRÈS le lookup exact, AVANT le catalogue :
```python
def mapper_nom(nom: str):
    if not nom:
        return None
    cle = normaliser_nom(nom)
    if cle in _MAPPING_ERETRO:
        return _MAPPING_ERETRO[cle]
    # Connecteurs/jumpers/bornes -> type dédié 'J' (dialecte réel).
    if any(mot in cle for mot in ('connect', 'jumper', 'borne')):
        return ('J', None)
    # Résistance 'R <code>' : R suivi d'un chiffre, ou 'RINF'. 'RELAIS' (lettre
    # après R) ne matche pas ; l'exact 'relais 2rt' est déjà intercepté au-dessus.
    if re.match(r'r\s*(\d|inf)', cle):
        return ('R', None)
    from circuit_analyzer.catalogue import identifier
    if identifier('U', nom) is not None:
        return ('U', {})
    return None
```

- [ ] **Step 4 : Vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_dialecte.py -q`
Expected : PASS. Puis non-régression ciblée :
`PYTHONUTF8=1 python -m pytest tests/test_eretro.py tests/test_eretro_forme.py tests/test_eretro_corpus.py -q` → PASS.

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/eretro.py tests/test_eretro_dialecte.py
git commit -m "feat(eretro): mapping par nom du dialecte reel (underscore, connecteurs J, R-code, condo polarise, photodiode)"
```

---

### Task 3 : Valeur R-code + catch-all IC + marqueur boîte + catalogue 78L05

**Files :**
- Modify : `circuit_analyzer/composant.py` (champ `boite_ic`)
- Modify : `circuit_analyzer/xml.py` (Étape 5)
- Modify : `circuit_analyzer/catalogue.py` (entrée 78L05)
- Test : `tests/test_eretro_dialecte.py`

**Interfaces :**
- Consumes : `decoder_valeur_resistance`, `mapper_nom` (Tasks 1-2).
- Produces : `Composant.boite_ic: bool = False` (rendu boîte IC neutre). Après `lire_xml`, un R-code porte sa valeur décodée ; une IC nommée non reconnue (≥3 broches) devient `U` + `boite_ic=True` + `value=<nom>` ; un connecteur `J` porte `value=<nom>`.

- [ ] **Step 1 : Test rouge**

```python
# tests/test_eretro_dialecte.py  (ajouter)
from circuit_analyzer.composant import Composant


def test_composant_boite_ic_defaut_false():
    assert Composant(ref="U1", type="U", pins={}).boite_ic is False


def test_ic_nommee_multibroches_devient_boite_ic():
    # helpers _item/_pin/_boardsch/_lire réutilisés depuis test_eretro (importés en tête).
    from tests.test_eretro import _item, _pin, _boardsch, _lire
    pins = [_pin(refs=[f'n{i}']) for i in range(8)]
    item = _item('SI844AB', pins=pins)          # nom inconnu, 8 broches, pas de forme franche
    comps = _lire(_boardsch([item], []))
    c = comps[0]
    assert c.type == 'U' and c.boite_ic is True and c.value == 'SI844AB'


def test_rcode_porte_sa_valeur_decodee():
    from tests.test_eretro import _item, _pin, _boardsch, _lire
    item = _item('R 1001', pins=[_pin(refs=['a']), _pin(refs=['b'])])
    comps = _lire(_boardsch([item], []))
    c = comps[0]
    assert c.type == 'R' and c.value == '1k'
```

(Si `_item`/`_pin`/`_boardsch`/`_lire` ne sont pas importables tels quels, relire `tests/test_eretro.py` et réutiliser exactement ses helpers de construction BoardSCH.)

- [ ] **Step 2 : Vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_dialecte.py -q -k "boite_ic or rcode_porte or ic_nommee"`
Expected : FAIL (`boite_ic` inexistant ; SI844AB → X ; valeur R vide).

- [ ] **Step 3 : Implémentation**

`circuit_analyzer/composant.py` — ajouter le champ après `value` :
```python
    value: str = ''
    par_forme: bool = False
    boite_ic: bool = False
```

`circuit_analyzer/catalogue.py` — ajouter à `_SUFFIXES_U` (NON-aliasée : le pinout
78L05 TO-92 est l'inverse du 7805, on ne renomme donc PAS les broches ; boîte
étiquetée « Regulateur +5 V (78L05) ») :
```python
    "78L05": _e("Regulateur +5 V", "78L05", None),
```

`circuit_analyzer/xml.py`, Étape 5 — trois ajouts. (a) valeur R-code, (b) catch-all
IC, (c) propagation. Le bloc de résolution devient :

```python
        correspondance = _NOM_VERS_TYPE.get(nom) or eretro.mapper_nom(nom)
        par_forme = False
        if correspondance is None:
            geo = elem.get('geo')
            forme = eretro.classer_par_forme(geo) if geo else None
            if forme is not None:
                correspondance, par_forme = forme, True

        boite_ic = False
        # Catch-all IC : nom réel + ≥3 broches, non reconnu autrement -> boîte IC
        # honnête étiquetée du nom (jamais une boîte noire X muette ni un faux AOP).
        if correspondance is None and nom.strip() and len(elem['pins']) >= 3:
            correspondance, boite_ic = ('U', {}), True

        if correspondance is None:
            # (branche X inchangée)
            ...
            continue

        type_prefix, plan = correspondance
        # Connecteur J et IB boîte : étiquette = nom réel (le champ value est vide).
        if type_prefix in ('J', 'U') and not elem['value'] and (boite_ic or type_prefix == 'J'):
            elem = {**elem, 'value': nom}
            boite_ic = True
        # Résistance R-code : valeur décodée depuis le nom si value vide.
        if type_prefix == 'R' and not elem['value']:
            v = eretro.decoder_valeur_resistance(nom)
            if v:
                elem = {**elem, 'value': v}
        ...
        composants.append(Component(ref=ref, type=type_prefix, pins=broches,
                                    value=elem['value'], par_forme=par_forme,
                                    boite_ic=boite_ic))
```

(Adapter au code réel : relire l'Étape 5 courante — la construction des broches et
le `Component(...)` existent déjà, n'insérer que la résolution `boite_ic`/valeur et
les 2 kwargs. Le `type J` n'a pas de plan nommé : `plan` reste `None`, broches par
position, comme les passifs.)

- [ ] **Step 4 : Vérifier le vert + non-régression**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_dialecte.py tests/test_eretro.py tests/test_eretro_corpus.py tests/test_puce_drawing.py -q`
Expected : PASS. Noter tout basculement de comptage de type sur TestDiagram (le catch-all IC peut transformer d'anciens X ≥3 broches en U boîte — vérifier qu'aucune assertion existante ne casse ; si `test_testdiagram_gate2_reconnus_par_forme` régresse, restreindre le catch-all aux composants de premier niveau).

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/composant.py circuit_analyzer/xml.py circuit_analyzer/catalogue.py tests/test_eretro_dialecte.py
git commit -m "feat(eretro): valeur R-code + catch-all IC boite + type J + catalogue 78L05"
```

---

### Task 4 : Rendu — connecteurs/ICs en boîte, jumper 2 broches

**Files :**
- Modify : `gui/circuit_viewer.py` (`_puce_ilot`, `_schematic_symbol`, `_SYMBOL_ELM`)
- Test : `tests/test_puce_drawing.py`

**Interfaces :**
- Consumes : `Composant.boite_ic`, type `J` (Task 3).
- Produces : `_puce_ilot` rend une boîte étiquetée pour un U/J marqué non-AOP ; un `J` 2-broches (arête) rend `elm.Jumper` au lieu du défaut `elm.Resistor`.

- [ ] **Step 1 : Test rouge**

```python
# tests/test_puce_drawing.py  (ajouter)
def test_puce_ilot_connecteur_multibroches_donne_boite():
    from circuit_analyzer.composant import Composant, construire_graphe
    comp = Composant(ref="J1", type="J",
                     pins={"1": "A", "2": "B", "3": "C"}, value="Borne", boite_ic=True)
    g = construire_graphe([comp])
    trouve = cv._puce_ilot({"composants": ["J1"]}, g)
    assert trouve is not None
    ref, entree = trouve
    assert entree["categorie"] == "Connecteur" and entree["nom"] == "Borne"


def test_puce_ilot_ic_nommee_donne_boite_ci():
    from circuit_analyzer.composant import Composant, construire_graphe
    comp = Composant(ref="U1", type="U",
                     pins={str(i): f"n{i}" for i in range(1, 9)},
                     value="SI844AB", boite_ic=True)
    g = construire_graphe([comp])
    ref, entree = cv._puce_ilot({"composants": ["U1"]}, g)
    assert entree["categorie"] != "AOP" and entree["nom"] == "SI844AB"


def test_symbole_jumper_2_broches():
    import schemdraw.elements as elm
    assert cv._SYMBOL_ELM.get(cv._schematic_symbol("J")) is elm.Jumper
```

- [ ] **Step 2 : Vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_puce_drawing.py -q -k "connecteur or ic_nommee or jumper"`
Expected : FAIL (`_puce_ilot` renvoie None pour J/U marqués ; type J absent de `_SYMBOL_ELM`).

- [ ] **Step 3 : Implémentation**

`gui/circuit_viewer.py::_puce_ilot` — généraliser à U/J marqués. Remplacer le corps
après `comp = raw[actifs[0]]` :
```python
    comp = raw[actifs[0]]
    nom = getattr(comp, "value", "") or "?"
    if comp.type == "J":
        # Connecteur multi-broches -> boîte étiquetée honnête.
        return (actifs[0], {"categorie": "Connecteur", "nom": nom, "broches": None})
    if comp.type != "U":
        return None
    entree = identifier("U", getattr(comp, "value", ""))
    if entree is not None and entree.get("categorie") == "AOP":
        return None
    if entree is None:
        if getattr(comp, "par_forme", False) or getattr(comp, "boite_ic", False):
            return (actifs[0], {"categorie": "CI", "nom": nom, "broches": None})
        return None
    return (actifs[0], entree)
```

`_schematic_symbol` (~l.2377) — mapper le type `J` vers un symbole 2-broches :
ajouter `"J": "jumper"` dans son dict de correspondance. `_SYMBOL_ELM` (~l.2529) —
ajouter l'entrée :
```python
    "jumper": elm.Jumper,
```

- [ ] **Step 4 : Vérifier le vert + non-régression**

Run : `PYTHONUTF8=1 python -m pytest tests/test_puce_drawing.py -q`
Expected : PASS. `test_puce_ilot_ignore_les_aop_et_inconnus` (741 → None) reste vert.

- [ ] **Step 5 : Commit**

```bash
git add gui/circuit_viewer.py tests/test_puce_drawing.py
git commit -m "feat(gui): rendu boite pour connecteurs/ICs nommees, jumper 2 broches (dialecte reel)"
```

---

### Task 5 : Oracle corpus réel + boucle visuelle + clôture

**Files :**
- Create : `tests/test_cartes_reelles.py`
- Boucle visuelle : script scratch (hors dépôt), PNG inspectés.

**Interfaces :**
- Consumes : tout le pipeline (Tasks 1-4).

- [ ] **Step 1 : Test rouge/vert corpus réel (LECTURE SEULE)**

```python
# tests/test_cartes_reelles.py
import os, collections
import pytest
from circuit_analyzer.xml import lire_xml

_DOSSIER = "CARTE POUR TESTER (VRAI TEST)"
_FICHIERS = ["PG 2.xml", "PG 3.xml", "PowtranAlim20260809.xml", "pg carte.xml"]

pytestmark = pytest.mark.skipif(
    not os.path.isdir(_DOSSIER), reason="cartes reelles absentes")

_TYPES_VALIDES = set("RCLDQMUKFXJ")


@pytest.mark.parametrize("fichier", _FICHIERS)
def test_carte_reelle_reconnaissance_et_types(fichier):
    comps = lire_xml(os.path.join(_DOSSIER, fichier))
    types = collections.Counter(c.type for c in comps)
    # Aucun type invalide (J = connecteur désormais légal).
    assert set(types) <= _TYPES_VALIDES, types
    # Chute franche des inconnus X : au moins la moitié des composants reconnus.
    assert types.get('X', 0) <= len(comps) // 2, dict(types)


def test_toutes_cartes_baisse_globale_des_inconnus():
    total, inconnus, resistances = 0, 0, 0
    for f in _FICHIERS:
        comps = lire_xml(os.path.join(_DOSSIER, f))
        total += len(comps)
        inconnus += sum(1 for c in comps if c.type == 'X')
        resistances += sum(1 for c in comps if c.type == 'R')
    assert inconnus <= 40, f"trop d'inconnus restants : {inconnus}/{total}"
    assert resistances >= 90, f"resistances reconnues : {resistances}"
```

- [ ] **Step 2 : Vérifier**

Run : `PYTHONUTF8=1 python -m pytest tests/test_cartes_reelles.py -q`
Expected : PASS. Consigner dans le rapport les chiffres AVANT/APRÈS par carte (inconnus 144 → attendu ≤ ~40 ; ≥ ~99 résistances).

- [ ] **Step 3 : Boucle visuelle (exigence boss — livrable)**

Script scratch (dossier scratch hors dépôt) réutilisant le pipeline réel
(`lire_xml → construire_graphe → analyser → tools/render_ilots_v2._fig_for_ilot`) :
rendre en PNG, sur les 4 cartes, un échantillon d'îlots contenant (a) une résistance
`R <code>` — symbole R avec **valeur affichée** ; (b) un connecteur multi-broches
(boîte « Connecteur (…) ») ; (c) un jumper 2 broches (symbole cavalier, pas une
résistance) ; (d) une IC nommée (boîte « CI (SI844AB) ») ; (e) le régulateur 78L05
(boîte « Regulateur +5 V »). INSPECTER les PNG : canvas clair, aucune boîte noire X
pour ces familles, aucun faux AOP, aucune collision. Décrire ce qui est vu dans le
rapport. Supprimer PNG/scripts après inspection (jamais committés).

- [ ] **Step 4 : Suite complète + commit**

Run : `PYTHONUTF8=1 python -m pytest -q` (relancer `test_500_portes_sous_budget` isolé si flake).
Expected : tout vert.

```bash
git add tests/test_cartes_reelles.py
git commit -m "feat(eretro): oracle corpus reel (4 cartes) — reconnaissance dialecte >= 80%"
```

- [ ] **Step 5 : Ledger**

Consigner le chantier dans `.superpowers/sdd/progress.md`.

---

## Self-Review (rédaction du plan)

- **Couverture spec :** R-code+valeur (T1) ✓ ; underscore+connecteurs+R-code+condo polarisé+photodiode (T2) ✓ ; catch-all IC boîte + type J + marqueur + 78L05 (T3) ✓ ; rendu boîte connecteur/IC + jumper 2 broches (T4) ✓ ; oracle corpus réel + boucle visuelle (T5) ✓. Principe « toujours des schémas » ancré dans les contraintes + T5.
- **Placeholders :** aucun — code complet à chaque étape. Le catch-all IC porte un risque de régression documenté (T3 Step 4) tranché par la suite complète.
- **Cohérence des types :** `decoder_valeur_resistance`/`_ohms_vers_str`/`boite_ic`/`mapper_nom` signatures identiques entre tâches ; type `J` introduit T2-T3, rendu T4 ; `_PLAN_Q`/`_PLAN_D` réutilisés (déjà définis).
- **Risques de rendu (spec) :** connecteur 2-broches (arête `elm.Jumper`) vs multi-broches (boîte) couverts T4 ; rôles B/C/E des `Transistor_NPN` — mappés `_PLAN_Q` en T2 mais broches réelles NUMÉROTÉES : la boucle visuelle T5 sur `PowtranAlim` (11 transistors) est le juge ; si mal câblés, tâche de suivi (aliasing positionnel), hors périmètre v1.
