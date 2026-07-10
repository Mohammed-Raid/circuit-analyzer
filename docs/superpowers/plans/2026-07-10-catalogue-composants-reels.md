# Catalogue de composants réels v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Identifier chaque référence constructeur (NE555, 74HC00, LM393, 7805, PC817, x741…) et la dessiner juste — sans détection de montages (v1).

**Architecture:** Un module de données `circuit_analyzer/catalogue.py` (table déclarative + `identifier()`), une passe d'aliasing de broches à la lecture (741 → AOP standard, zéro modification des matchers), une garde anti-fausse-détection dans `detecteur.py`, et un rendu d'îlot « 1 puce + Z autour » via `schemdraw elm.Ic` (jamais de grille générique pour une puce identifiée).

**Tech Stack:** Python 3.14, schemdraw==0.22 (`elm.Ic`/`elm.IcPin`/`elm.LED` vérifiés présents), matplotlib Agg, pytest.

## Global Constraints

- schemdraw reste sur l'API **0.22** (requirements cappé `<0.23`) ; aucun nouveau package.
- Interpréteur : `python` (= pythoncore-3.14-64) ; **toujours** `PYTHONUTF8=1` devant pytest (shell cp1252 sinon mojibake).
- Commits en **français**, JAMAIS de footer « Co-Authored-By: Claude » / « Generated with Claude Code ».
- **Zéro nouvelle exclusion** dans `tests/test_puces_resolution.py`.
- Canvas des schémas reste CLAIR (`#fafafa`) ; jamais de vue générique pour une puce identifiée.
- Piège schemdraw : tout élément posé porte une orientation explicite (`.right()` / `.theta(0)`) — sinon héritage de la direction du stylo (bug D4 historique).
- PNG des deux vues rendus **et inspectés** après toute modification de dessin (règle boss).
- Spec de référence : `docs/superpowers/specs/2026-07-10-catalogue-composants-reels-design.md` (table des pinouts EXACTE à recopier — ne pas réinventer).

---

### Task 1: `circuit_analyzer/catalogue.py` — table + `identifier()`

**Files:**
- Create: `circuit_analyzer/catalogue.py`
- Test: `tests/test_catalogue.py`

**Interfaces:**
- Produces: `identifier(type_: str, value: str) -> dict | None` avec clés
  `categorie` (str), `nom` (str), `broches` (dict {"1": "GND", …} | None),
  `alias` (bool), `symbole` ("puce" | "led" | None), `couleur` (str, LED
  seulement). Consommé par les Tasks 2, 3, 5, 6, 7.
- Produces: `_normaliser(valeur) -> str` (interne, testée).

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_catalogue.py
"""@file test_catalogue.py
@brief Identification des références constructeur (catalogue déclaratif)."""
import pytest

from circuit_analyzer import catalogue


@pytest.mark.parametrize("valeur,categorie", [
    ("NE555", "Timer"), ("ne 555", "Timer"),           # normalisation
    ("LM393", "Comparateur double"), ("LM339", "Comparateur quadruple"),
    ("PC817", "Optocoupleur"),
    ("74HC00", "Porte NAND x4"), ("74HCT00", "Porte NAND x4"),   # famille
    ("74HC04N", "Inverseur x6"),                        # suffixe boîtier
    ("74HC08", "Porte AND x4"), ("74HC32", "Porte OR x4"),
    ("74HC74", "Bascule D x2"), ("74HC157", "Multiplexeur 2:1 x4"),
    ("74HC138", "Demultiplexeur 3:8"),
    ("LM741", "AOP"), ("UA741", "AOP"),                 # suffixe libre
    ("MC1458", "AOP double"), ("LM1458", "AOP double"),
    ("7805", "Regulateur +5 V"), ("LM7805", "Regulateur +5 V"),
    ("7812", "Regulateur +12 V"), ("LM317", "Regulateur ajustable"),
    ("74HC125", "Logique 74HC"),                        # repli famille
])
def test_identifier_u(valeur, categorie):
    e = catalogue.identifier("U", valeur)
    assert e is not None and e["categorie"] == categorie


@pytest.mark.parametrize("valeur,categorie", [
    ("2N2222", "Transistor NPN"), ("BC547", "Transistor NPN"),
    ("2N3904", "Transistor NPN"),
])
def test_identifier_q(valeur, categorie):
    assert catalogue.identifier("Q", valeur)["categorie"] == categorie


@pytest.mark.parametrize("valeur", ["IRFZ44N", "BS170", "IRLZ44N"])
def test_identifier_m(valeur):
    assert catalogue.identifier("M", valeur)["categorie"] == "MOSFET canal N"


@pytest.mark.parametrize("valeur,couleur", [
    ("LED rouge", "red"), ("rouge", "red"),
    ("LED verte", "green"), ("LED bleue", "blue"),
])
def test_identifier_led(valeur, couleur):
    e = catalogue.identifier("D", valeur)
    assert e["categorie"] == "LED" and e["couleur"] == couleur


def test_identifier_inconnu_et_type_non_concerne():
    assert catalogue.identifier("U", "") is None
    assert catalogue.identifier("U", "XYZ999") is None
    assert catalogue.identifier("R", "10k") is None
    # une LED n'est identifiée QUE sur le type D :
    assert catalogue.identifier("U", "rouge") is None


def test_broches_et_alias():
    e555 = catalogue.identifier("U", "NE555")
    assert e555["broches"]["2"] == "TRIG" and e555["broches"]["8"] == "VCC"
    assert e555["alias"] is False
    e741 = catalogue.identifier("U", "LM741")
    assert e741["broches"]["2"] == "IN-" and e741["broches"]["6"] == "OUT"
    assert e741["alias"] is True                       # mono-unité -> AOP existant
    e7805 = catalogue.identifier("U", "7805")
    assert e7805["broches"] == {"1": "IN", "2": "GND", "3": "OUT"}
    assert e7805["alias"] is True
    e458 = catalogue.identifier("U", "MC1458")
    assert e458["alias"] is False                      # multi-unité : jamais aliasé
    assert catalogue.identifier("Q", "2N2222")["broches"] is None
```

- [ ] **Step 2: Vérifier l'échec**

Run: `PYTHONUTF8=1 python -m pytest tests/test_catalogue.py -q`
Expected: FAIL — `ModuleNotFoundError: circuit_analyzer.catalogue`.

- [ ] **Step 3: Implémenter le module**

```python
# circuit_analyzer/catalogue.py
"""
@file catalogue.py
@brief Catalogue déclaratif des composants réels (références constructeur).

Ajouter un composant = ajouter UNE entrée de données ci-dessous (jamais de
code). Les pinouts (n° boîtier -> fonction) viennent de la spec
docs/superpowers/specs/2026-07-10-catalogue-composants-reels-design.md.

`alias=True` = puce MONO-unité dont les broches sont renommées à la lecture
vers un rôle déjà connu de l'app (x741 -> AOP IN-/IN+/OUT ; régulateurs ->
IN/GND/OUT). Les multi-unités (x458, LM393, 74HC00…) restent en fonctions de
boîtier et passent par la boîte puce.
"""
import re


def _normaliser(valeur):
    """@brief Majuscules, espaces/tirets/underscores retirés."""
    return re.sub(r"[\s\-_]", "", (valeur or "").upper())


def _e(categorie, nom, broches=None, alias=False, symbole="puce"):
    return {"categorie": categorie, "nom": nom, "broches": broches,
            "alias": alias, "symbole": symbole}


_BROCHES_7400 = {"1": "1A", "2": "1B", "3": "1Y", "4": "2A", "5": "2B",
                 "6": "2Y", "7": "GND", "8": "3Y", "9": "3A", "10": "3B",
                 "11": "4Y", "12": "4A", "13": "4B", "14": "VCC"}

# ── U : correspondance EXACTE (après normalisation) ─────────────────────────
_EXACTS_U = {
    "NE555": _e("Timer", "NE555",
                {"1": "GND", "2": "TRIG", "3": "OUT", "4": "RESET",
                 "5": "CTRL", "6": "THR", "7": "DIS", "8": "VCC"}),
    "LM393": _e("Comparateur double", "LM393",
                {"1": "OUT1", "2": "IN1-", "3": "IN1+", "4": "GND",
                 "5": "IN2+", "6": "IN2-", "7": "OUT2", "8": "VCC"}),
    "LM339": _e("Comparateur quadruple", "LM339",
                {"1": "OUT2", "2": "OUT1", "3": "VCC", "4": "IN1-",
                 "5": "IN1+", "6": "IN2-", "7": "IN2+", "8": "IN3-",
                 "9": "IN3+", "10": "IN4-", "11": "IN4+", "12": "GND",
                 "13": "OUT4", "14": "OUT3"}),
    "PC817": _e("Optocoupleur", "PC817",
                {"1": "ANODE", "2": "CATHODE", "3": "EMETTEUR",
                 "4": "COLLECTEUR"}),
    "LM317": _e("Regulateur ajustable", "LM317",
                {"1": "ADJ", "2": "OUT", "3": "IN"}, alias=True),
}

# ── U : familles 74HC/74HCT (le T et le suffixe boîtier sont tolérés) ───────
_FAMILLES_74HC = {
    "00": _e("Porte NAND x4", "74HC00", dict(_BROCHES_7400)),
    "08": _e("Porte AND x4", "74HC08", dict(_BROCHES_7400)),
    "32": _e("Porte OR x4", "74HC32", dict(_BROCHES_7400)),
    "04": _e("Inverseur x6", "74HC04",
             {"1": "1A", "2": "1Y", "3": "2A", "4": "2Y", "5": "3A",
              "6": "3Y", "7": "GND", "8": "4Y", "9": "4A", "10": "5Y",
              "11": "5A", "12": "6Y", "13": "6A", "14": "VCC"}),
    "74": _e("Bascule D x2", "74HC74",
             {"1": "1CLR", "2": "1D", "3": "1CLK", "4": "1PRE", "5": "1Q",
              "6": "1NQ", "7": "GND", "8": "2NQ", "9": "2Q", "10": "2PRE",
              "11": "2CLK", "12": "2D", "13": "2CLR", "14": "VCC"}),
    "157": _e("Multiplexeur 2:1 x4", "74HC157",
              {"1": "SEL", "2": "1A", "3": "1B", "4": "1Y", "5": "2A",
               "6": "2B", "7": "2Y", "8": "GND", "9": "3Y", "10": "3B",
               "11": "3A", "12": "4Y", "13": "4B", "14": "4A",
               "15": "NEN", "16": "VCC"}),
    "138": _e("Demultiplexeur 3:8", "74HC138",
              {"1": "A0", "2": "A1", "3": "A2", "4": "NE1", "5": "NE2",
               "6": "E3", "7": "Y7", "8": "GND", "9": "Y6", "10": "Y5",
               "11": "Y4", "12": "Y3", "13": "Y2", "14": "Y1",
               "15": "Y0", "16": "VCC"}),
}

# ── U : suffixes libres (tout préfixe constructeur : LM741, UA741, MC1458…) ─
_SUFFIXES_U = {
    "741": _e("AOP", "741",
              {"1": "OFFSET1", "2": "IN-", "3": "IN+", "4": "V-",
               "5": "OFFSET2", "6": "OUT", "7": "V+", "8": "NC"},
              alias=True),
    "1458": _e("AOP double", "1458",
               {"1": "OUT1", "2": "IN1-", "3": "IN1+", "4": "V-",
                "5": "IN2+", "6": "IN2-", "7": "OUT2", "8": "V+"}),
    "458": _e("AOP double", "x458",
              {"1": "OUT1", "2": "IN1-", "3": "IN1+", "4": "V-",
               "5": "IN2+", "6": "IN2-", "7": "OUT2", "8": "V+"}),
    "7805": _e("Regulateur +5 V", "7805",
               {"1": "IN", "2": "GND", "3": "OUT"}, alias=True),
    "7812": _e("Regulateur +12 V", "7812",
               {"1": "IN", "2": "GND", "3": "OUT"}, alias=True),
}

_REPLI_74HC = _e("Logique 74HC", "74HC (famille)", None)

# ── Q / M / D : catégorie seule (les broches nommées existent déjà) ─────────
_EXACTS_Q = {v: _e("Transistor NPN", v, None, symbole=None)
             for v in ("2N2222", "BC547", "2N3904")}
_EXACTS_M = {v: _e("MOSFET canal N", v, None, symbole=None)
             for v in ("IRFZ44N", "BS170", "IRLZ44N")}
_EXACTS_D = {v: _e("Diode signal" if v == "1N4148" else "Diode redressement",
                   v, None, symbole=None)
             for v in ("1N4148", "1N4007")}

_COULEURS_LED = {"ROUGE": "red", "VERT": "green", "BLEU": "blue"}


def identifier(type_, value):
    """@brief Entrée de catalogue d'un composant, ou None si inconnu.

    Priorité : exact > famille 74HC précise > suffixe libre > repli 74HC.
    None = comportement actuel de l'app inchangé (compat totale).

    @param type_ Lettre de type BoardSCH ("U", "Q", "M", "D"…).
    @param value Champ value du composant (référence constructeur).
    @return dict {categorie, nom, broches, alias, symbole[, couleur]} | None.
    """
    v = _normaliser(value)
    if not v:
        return None
    if type_ == "D":
        for cle, couleur in _COULEURS_LED.items():
            if cle in v:            # "LEDROUGE", "ROUGE", "LEDVERTE"…
                e = dict(_e("LED", f"LED ({couleur})", None, symbole="led"))
                e["couleur"] = couleur
                return e
        return _EXACTS_D.get(v)
    if type_ == "Q":
        return _EXACTS_Q.get(v)
    if type_ == "M":
        return _EXACTS_M.get(v)
    if type_ != "U":
        return None
    if v in _EXACTS_U:
        return _EXACTS_U[v]
    m = re.fullmatch(r"74HCT?(\d+)[A-Z]*", v)
    if m:
        if m.group(1) in _FAMILLES_74HC:
            return _FAMILLES_74HC[m.group(1)]
        return _REPLI_74HC
    for suffixe, entree in sorted(_SUFFIXES_U.items(),
                                  key=lambda kv: -len(kv[0])):
        if re.fullmatch(rf"[A-Z0-9]*{suffixe}[A-Z]*", v):
            return entree
    return None
```

NB (implémenteur) : « verte »/« bleue » normalisés = `VERTE`/`BLEUE` — le
test `in` sur `VERT`/`BLEU` les couvre. Le suffixe `1458` est testé AVANT
`458` (tri par longueur décroissante) pour que `MC1458` prenne l'entrée
nominale ; les deux donnent la même catégorie.

- [ ] **Step 4: Vérifier le vert**

Run: `PYTHONUTF8=1 python -m pytest tests/test_catalogue.py -q`
Expected: tous PASS.

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/catalogue.py tests/test_catalogue.py
git commit -m "feat(catalogue): table declarative des composants reels + identifier()"
```

---

### Task 2: Aliasing de broches à la lecture

**Files:**
- Modify: `circuit_analyzer/catalogue.py` (ajout `appliquer_catalogue`)
- Modify: `circuit_analyzer/xml.py` (fin de `lire_xml`, ~ligne 1200 juste avant le `return`)
- Modify: `circuit_analyzer/composant.py` (fin de `lire_netlist`, juste avant son `return`)
- Test: `tests/test_catalogue.py` (ajouts)

**Interfaces:**
- Consumes: `identifier()` (Task 1).
- Produces: `appliquer_catalogue(comps) -> comps` (mutation en place des
  `.pins` des composants aliasés ; renvoie la même liste). Branchée dans les
  DEUX producteurs de listes de composants (`lire_xml`, `lire_netlist`).

- [ ] **Step 1: Tests qui échouent**

```python
# à ajouter dans tests/test_catalogue.py
from circuit_analyzer.composant import Composant


def test_appliquer_catalogue_alias_741():
    c = Composant(ref="U1", type="U", value="LM741",
                  pins={"2": "NIN", "3": "GND", "6": "NOUT",
                        "7": "VCC", "4": "VEE"})
    catalogue.appliquer_catalogue([c])
    assert c.pins == {"IN-": "NIN", "IN+": "GND", "OUT": "NOUT",
                      "V+": "VCC", "V-": "VEE"}


def test_appliquer_catalogue_ne_touche_pas_multi_unites_ni_inconnus():
    c555 = Composant(ref="U2", type="U", value="NE555",
                     pins={"2": "A", "3": "B"})
    inconnu = Composant(ref="U3", type="U", value="XYZ",
                        pins={"IN-": "A", "OUT": "B"})
    catalogue.appliquer_catalogue([c555, inconnu])
    assert c555.pins == {"2": "A", "3": "B"}          # multi-unité : intact
    assert inconnu.pins == {"IN-": "A", "OUT": "B"}   # inconnu : intact


def test_appliquer_catalogue_broche_deja_nommee_intacte():
    # Fichier mixte : un 741 déjà saisi en broches fonctionnelles ne casse pas.
    c = Composant(ref="U1", type="U", value="UA741",
                  pins={"IN-": "A", "IN+": "B", "OUT": "C"})
    catalogue.appliquer_catalogue([c])
    assert c.pins == {"IN-": "A", "IN+": "B", "OUT": "C"}
```

- [ ] **Step 2: Vérifier l'échec** — `PYTHONUTF8=1 python -m pytest tests/test_catalogue.py -q` → FAIL (`appliquer_catalogue` absent).

- [ ] **Step 3: Implémentation** (fin de `catalogue.py`)

```python
def appliquer_catalogue(comps):
    """@brief Passe post-lecture : renomme les broches numérotées des puces
    mono-unité identifiées (alias=True) vers leur rôle connu (741 -> AOP…).

    Idempotente : une broche déjà fonctionnelle (clé absente du pinout
    numéroté) est laissée telle quelle. Mutation en place ; renvoie comps.
    """
    for c in comps:
        entree = identifier(getattr(c, "type", ""), getattr(c, "value", ""))
        if not entree or not entree.get("alias") or not entree.get("broches"):
            continue
        broches = entree["broches"]
        c.pins = {broches.get(num, num): net for num, net in c.pins.items()}
    return comps
```

Branchement — `circuit_analyzer/xml.py`, tout en bas de `lire_xml`, juste
avant le `return composants` final :

```python
    from circuit_analyzer.catalogue import appliquer_catalogue
    appliquer_catalogue(composants)
```

Même ajout à la fin de `lire_netlist` dans `circuit_analyzer/composant.py`
(avant son `return`), sur sa variable de liste de composants (vérifier son
nom réel dans la fonction).

- [ ] **Step 4: Vert + non-régression lecture**

Run: `PYTHONUTF8=1 python -m pytest tests/test_catalogue.py tests/test_xml*.py -q`
Expected: PASS (aucun fichier corpus actuel ne porte de value cataloguée → no-op prouvé par la suite).

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/catalogue.py circuit_analyzer/xml.py circuit_analyzer/composant.py tests/test_catalogue.py
git commit -m "feat(catalogue): aliasing des broches numerotees a la lecture (741/regulateurs)"
```

---

### Task 3: Garde anti-fausse-détection dans `detecteur.py`

**Files:**
- Modify: `circuit_analyzer/detecteur.py` (les 11 sites `if comp.type != 'U': continue` — lignes ~118, 172, 225, 303, 378, 421, 463, 513, 573, 620, 678)
- Test: `tests/test_catalogue.py` (ajouts)

**Interfaces:**
- Consumes: `identifier()` (Task 1).
- Produces: `_u_candidat_aop(comp) -> bool` dans `detecteur.py`, utilisé par
  TOUS les détecteurs AOP/comparateur à la place du test de type brut.

- [ ] **Step 1: Tests qui échouent**

```python
# à ajouter dans tests/test_catalogue.py
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser


def _r(ref, a, b, val="10k"):
    return Composant(ref=ref, type="R", pins={"1": a, "2": b}, value=val)


def test_555_nest_jamais_detecte_comme_aop():
    # Un NE555 câblé pour RESSEMBLER à un inverseur AOP (broches renommées
    # exprès IN-/OUT par le fichier) ne doit PAS matcher : U identifié non-AOP.
    u = Composant(ref="U1", type="U", value="NE555",
                  pins={"IN-": "N1", "IN+": "GND", "OUT": "N2"})
    comps = [u, _r("R1", "VIN", "N1"), _r("R2", "N1", "N2")]
    res = analyser(construire_graphe(comps))
    assert not any("(AOP)" in m["circuit_type"] for m in res)


def test_741_alias_est_detecte_inverseur():
    # Bout-en-bout : broches NUMÉROTÉES + value LM741 -> aliasing (simulé ici
    # par appliquer_catalogue, comme le fait lire_xml) -> matcher AOP existant.
    u = Composant(ref="U1", type="U", value="LM741",
                  pins={"2": "N1", "3": "GND", "6": "N2", "7": "VCC", "4": "VEE"})
    comps = catalogue.appliquer_catalogue(
        [u, _r("R1", "VIN", "N1"), _r("R2", "N1", "N2")])
    res = analyser(construire_graphe(comps))
    assert any(m["circuit_type"] == "Amplificateur inverseur (AOP)" for m in res)


def test_u_inconnu_reste_candidat_aop():
    # Compat : un U sans value cataloguée garde le comportement historique.
    u = Composant(ref="U1", type="U", value="",
                  pins={"IN-": "N1", "IN+": "GND", "OUT": "N2"})
    comps = [u, _r("R1", "VIN", "N1"), _r("R2", "N1", "N2")]
    res = analyser(construire_graphe(comps))
    assert any(m["circuit_type"] == "Amplificateur inverseur (AOP)" for m in res)
```

- [ ] **Step 2: Vérifier l'échec** — le test 555 échoue (il matche inverseur aujourd'hui).

- [ ] **Step 3: Implémentation**

Dans `detecteur.py`, près des imports :

```python
def _u_candidat_aop(comp):
    """@brief Un composant U entre dans les détecteurs AOP/comparateur ssi il
    n'est pas identifié comme une AUTRE puce du catalogue (NE555, 74HC…).

    U inconnu -> True (comportement historique). U aliasé mono-AOP (x741) ->
    True : ses broches sont déjà IN-/IN+/OUT après appliquer_catalogue.
    """
    if comp.type != 'U':
        return False
    from circuit_analyzer.catalogue import identifier
    entree = identifier('U', getattr(comp, 'value', ''))
    return entree is None or entree['categorie'] == 'AOP'
```

Puis remplacer, aux 11 sites listés :

```python
        if comp.type != 'U':
            continue
```

par :

```python
        if not _u_candidat_aop(comp):
            continue
```

- [ ] **Step 4: Vert + suite détection**

Run: `PYTHONUTF8=1 python -m pytest tests/test_catalogue.py tests/test_detecteur*.py tests/test_aop*.py -q` (adapter aux noms réels des fichiers de tests détection)
Expected: PASS, zéro régression.

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/detecteur.py tests/test_catalogue.py
git commit -m "feat(detecteur): garde catalogue - un U identifie non-AOP sort des matchers AOP"
```

---

### Task 4: Corpus `reel_*.xml` + générateur

**Files:**
- Create: `tools/gen_reel_corpus.py`
- Create: `circuits_industriels/reel_*.xml` (8 fichiers, générés)
- Test: `tests/test_reel_integration.py`

**Interfaces:**
- Consumes: `Composant`, `generer_xml` (mêmes imports que `tools/gen_logic_corpus.py` — s'en inspirer, même style), `identifier`, `lire_xml`.
- Produces: les 8 fichiers corpus consommés par les Tasks 5, 6, 8.

- [ ] **Step 1: Écrire le générateur**

```python
# tools/gen_reel_corpus.py
# @file gen_reel_corpus.py
# @brief Corpus des composants réels (circuits_industriels/reel_*.xml) —
# relançable, déterministe (même style que gen_logic_corpus.py).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuit_analyzer.composant import Composant
from circuit_analyzer.xml import generer_xml

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "circuits_industriels")


def _r(ref, a, b, val="10k"):
    return Composant(ref=ref, type="R", pins={"1": a, "2": b}, value=val)


def _c(ref, a, b, val="100n"):
    return Composant(ref=ref, type="C", pins={"1": a, "2": b}, value=val)


def _u(ref, val, **pins):
    # pins par numéro de boîtier : _u("U1", "NE555", p1="GND", p2="TRIG_NET"…)
    return Composant(ref=ref, type="U", value=val,
                     pins={k[1:]: v for k, v in pins.items()})


CIRCUITS = {
    # Preuve d'aliasing : broches numérotées 741 -> détecté inverseur AOP.
    "reel_741_inverseur.xml": [
        _u("U1", "LM741", p2="NIN", p3="GND", p6="NOUT", p7="VCC", p4="VEE"),
        _r("R1", "VIN", "NIN"), _r("R2", "NIN", "NOUT", "100k")],
    "reel_555_astable.xml": [
        _u("U1", "NE555", p1="GND", p2="NTRIG", p3="NOUT", p4="VCC",
           p5="NCTRL", p6="NTRIG", p7="NDIS", p8="VCC"),
        _r("RA", "VCC", "NDIS", "4.7k"), _r("RB", "NDIS", "NTRIG", "10k"),
        _c("C1", "NTRIG", "GND", "10u"), _c("C2", "NCTRL", "GND", "10n")],
    "reel_7805_alim.xml": [
        _u("U1", "7805", p1="VIN", p2="GND", p3="V5"),
        _c("C1", "VIN", "GND", "330n"), _c("C2", "V5", "GND", "100n")],
    "reel_lm317_variable.xml": [
        _u("U1", "LM317", p1="NADJ", p2="VOUT", p3="VIN"),
        _r("R1", "VOUT", "NADJ", "240"), _r("R2", "NADJ", "GND", "1.2k")],
    "reel_pc817_entree.xml": [
        _u("U1", "PC817", p1="NA", p2="GND", p3="GND", p4="NC1"),
        _r("R1", "VIN", "NA", "1k"), _r("R2", "VCC", "NC1", "10k")],
    "reel_74hc00_seul.xml": [
        _u("U1", "74HC00", p1="NA1", p2="NB1", p3="NY1", p7="GND",
           p14="VCC")],
    "reel_lm393_seuil.xml": [
        _u("U1", "LM393", p2="NREF", p3="NMES", p1="NOUT", p4="GND",
           p8="VCC"),
        _r("R1", "VCC", "NREF", "10k"), _r("R2", "NREF", "GND", "10k"),
        _r("R3", "VCC", "NOUT", "4.7k")],
    "reel_led_r.xml": [
        Composant(ref="D1", type="D", value="LED rouge",
                  pins={"A": "NLED", "K": "GND"}),
        _r("R1", "VCC", "NLED", "330")],
}


def main():
    for nom, comps in CIRCUITS.items():
        chemin = os.path.join(OUT_DIR, nom)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(generer_xml(comps))
        print("->", chemin)


if __name__ == "__main__":
    main()
```

NB : vérifier la signature réelle de `generer_xml` dans
`tools/gen_logic_corpus.py` (même appel, même écriture de fichier) et
S'ALIGNER dessus — c'est la référence.

- [ ] **Step 2: Générer + test d'intégration structure**

Run: `PYTHONUTF8=1 python tools/gen_reel_corpus.py` → 8 fichiers.

```python
# tests/test_reel_integration.py
"""@file test_reel_integration.py
@brief Corpus reel_* : identification + aliasing + non-régression détection."""
import glob

import pytest

from circuit_analyzer import catalogue
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser
from circuit_analyzer.xml import lire_xml

FICHIERS = sorted(glob.glob("circuits_industriels/reel_*.xml"))


def test_corpus_present():
    assert len(FICHIERS) == 8


@pytest.mark.parametrize("fichier", FICHIERS)
def test_lecture_et_analyse_sans_exception(fichier):
    comps = lire_xml(fichier)
    res = analyser(construire_graphe(comps))
    assert res is not None


def test_741_du_corpus_detecte_inverseur():
    comps = lire_xml("circuits_industriels/reel_741_inverseur.xml")
    # l'aliasing a eu lieu DANS lire_xml :
    u = next(c for c in comps if c.ref == "U1")
    assert "IN-" in u.pins and "OUT" in u.pins
    res = analyser(construire_graphe(comps))
    assert any(m["circuit_type"] == "Amplificateur inverseur (AOP)" for m in res)


def test_555_du_corpus_identifie_et_pas_daop():
    comps = lire_xml("circuits_industriels/reel_555_astable.xml")
    u = next(c for c in comps if c.ref == "U1")
    assert catalogue.identifier(u.type, u.value)["categorie"] == "Timer"
    assert "2" in u.pins                      # multi-unité/non-alias : intact
    res = analyser(construire_graphe(comps))
    assert not any("(AOP)" in m["circuit_type"] for m in res)
```

Run: `PYTHONUTF8=1 python -m pytest tests/test_reel_integration.py -q` → PASS.
Regénérer (`python tools/gen_reel_corpus.py`) → `git diff` vide (déterminisme).

- [ ] **Step 3: Commit**

```bash
git add tools/gen_reel_corpus.py circuits_industriels/reel_*.xml tests/test_reel_integration.py
git commit -m "test(catalogue): corpus reel_* (8 familles) + integration lecture/aliasing/detection"
```

---

### Task 5: Rendu îlot « 1 puce + Z autour » (`_draw_puce` + `_puce_ilot`)

**Files:**
- Create: `gui/puce_schematic.py` (module dédié, précédent : `logic_schematic.py` — circuit_viewer.py a ~4000 lignes)
- Modify: `gui/circuit_viewer.py` (recognizer `_puce_ilot` + branchement dans `show_island` ~ligne 783 et `construire_fig` ~ligne 823)
- Modify: `tools/render_ilots_v2.py` (~ligne 103, même branchement AVANT `_paire_croisee`… non : après `deux`, avant `paire` — voir Step 3)
- Test: `tests/test_puce_drawing.py`

**Interfaces:**
- Consumes: `identifier()` ; `elm.Ic`/`elm.IcPin` (schemdraw 0.22 — VÉRIFIÉ :
  `Ic(pins=[IcPin(name='TRIG', pin='2', side='left'), …])` expose les ancres
  par NOM de fonction (`.TRIG`, `.OUT`) et par numéro (`.pin2`)) ;
  `_enregistrer_position`, `_dessiner_impedances_locales(d, stages, ancres,
  z_matches, z_utilises, ci)` et `_est_couplage` de circuit_viewer.
- Produces: `puce_schematic.dessiner_puce(d, ref, entree, ci) -> dict
  {"in","out","title","nets","absorbed_refs"}` (même contrat que les drawers
  existants) ; `cv._puce_ilot(ilot, graph) -> (ref, entree) | None` ;
  `cv._make_puce_fig(ref, entree, comp_info, matches, detaille) -> Figure`.

- [ ] **Step 1: Tests qui échouent**

```python
# tests/test_puce_drawing.py
"""@file test_puce_drawing.py
@brief Boîte puce (elm.Ic) : ancres par fonction, nets, contrat puces bandeau,
jamais de grille générique pour un îlot à puce identifiée."""
import matplotlib
matplotlib.use("Agg")
import schemdraw

from circuit_analyzer import catalogue
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser
from circuit_analyzer.xml import lire_xml
import gui.circuit_viewer as cv
from gui import puce_schematic

CI_555 = {"U1": {"type": "U", "value": "NE555",
                 "pins": {"1": "GND", "2": "NTRIG", "3": "NOUT", "4": "VCC",
                          "5": "NCTRL", "6": "NTRIG", "7": "NDIS", "8": "VCC"}}}


def _dessiner(detaille=False):
    entree = catalogue.identifier("U", "NE555")
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = detaille
        res = puce_schematic.dessiner_puce(d, "U1", entree, CI_555)
    return d, res


def test_contrat_ancres_et_nets():
    d, res = _dessiner()
    for cle in ("in", "out", "title", "nets", "absorbed_refs"):
        assert cle in res
    # chaque net câblé de la puce a un point d'ancrage réel
    for net in ("NTRIG", "NOUT", "NDIS", "NCTRL", "GND", "VCC"):
        assert net in res["nets"], net
    assert "U1" in d._comp_positions          # puce bandeau cliquable


def test_puce_ilot_reconnait_le_555():
    comps = lire_xml("circuits_industriels/reel_555_astable.xml")
    g = construire_graphe(comps)
    res = analyser(g)
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    trouve = cv._puce_ilot(ilot, g)
    assert trouve is not None
    ref, entree = trouve
    assert ref == "U1" and entree["categorie"] == "Timer"


def test_puce_ilot_ignore_les_aop_et_inconnus():
    comps = lire_xml("circuits_industriels/reel_741_inverseur.xml")
    g = construire_graphe(comps)
    res = analyser(g)
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    assert cv._puce_ilot(ilot, g) is None     # aliasé AOP -> chemins AOP


def test_make_puce_fig_deux_vues_et_z_cliquables():
    comps = lire_xml("circuits_industriels/reel_555_astable.xml")
    g = construire_graphe(comps)
    res = analyser(g)
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
          for c in comps}
    ref, entree = cv._puce_ilot(ilot, g)
    matches = cv._matches_for_island(ilot, res)
    for detaille in (False, True):
        fig = cv._make_puce_fig(ref, entree, ci, matches, detaille=detaille)
        assert "U1" in fig._comp_positions, f"puce non cliquable ({detaille=})"
        txts = [t.get_text() for ax in fig.axes for t in ax.texts]
        assert any("TRIG" in t for t in txts), "broches étiquetées par fonction"
        assert any("NE555" in t or "Timer" in t for t in txts), "titre puce"
```

- [ ] **Step 2: Vérifier l'échec** — `ModuleNotFoundError: gui.puce_schematic`.

- [ ] **Step 3: Implémentation**

```python
# gui/puce_schematic.py
"""
@file puce_schematic.py
@brief Boîte à puce générique (elm.Ic) pour les composants réels identifiés
(NE555, 74HC…, LM393, PC817…). Module dédié (précédent : logic_schematic.py).

Répartition des broches : alimentations en haut (VCC/VDD/V+) et en bas
(GND/VSS/V-), sorties (fonction contenant OUT/Y/Q) à droite, le reste à
gauche. Chaque broche câblée reçoit un stub + point + nom de net.

Piège schemdraw 0.22 : orientation EXPLICITE (.right()) sur tout élément —
sinon héritage de la direction courante du stylo (bug D4 historique).
"""
import re

import schemdraw.elements as elm
from schemdraw.elements import intcircuits as ic


_HAUT = {"VCC", "VDD", "V+"}
_BAS = {"GND", "VSS", "V-"}


def _cote(fonction):
    f = fonction.upper()
    if f in _HAUT:
        return "top"
    if f in _BAS:
        return "bottom"
    if "OUT" in f or re.fullmatch(r"\d?N?[YQ]\d?", f) or f.startswith("Y"):
        return "right"
    return "left"


def dessiner_puce(d, ref, entree, ci, origin=(4.0, 0), titre=True):
    """@brief Dessine la boîte puce de `ref` ; contrat de retour identique aux
    drawers de montages ({"in","out","title","nets","absorbed_refs"})."""
    from gui.circuit_viewer import _enregistrer_position
    pins_nets = (ci.get(ref, {}) or {}).get("pins", {}) or {}
    broches = entree.get("broches") or {n: n for n in pins_nets}
    # ne dessiner que les broches CÂBLÉES (une 74HC00 à 5 nets ne montre pas
    # ses 9 broches en l'air), ordre = numéro de boîtier.
    cablees = [(num, broches.get(num, num)) for num in sorted(
        pins_nets, key=lambda n: (len(n), n)) if pins_nets.get(num)]
    ic_pins = [ic.IcPin(name=fonction, pin=num, side=_cote(fonction),
                        anchorname=f"p{num}")
               for num, fonction in cablees]
    puce = ic.Ic(pins=ic_pins)   # pas de kwargs de padding : non garantis en 0.22
    d.add(puce.right().at(origin).label(entree["nom"], loc="center"))
    centre = puce.center
    _enregistrer_position(d, ref, tuple(centre))

    nets = {}
    delta = {"left": (-0.7, 0), "right": (0.7, 0),
             "top": (0, 0.7), "bottom": (0, -0.7)}
    locs = {"left": "left", "right": "right", "top": "top", "bottom": "bottom"}
    for num, fonction in cablees:
        net = pins_nets[num]
        a = getattr(puce, f"p{num}")
        cote = _cote(fonction)
        dx, dy = delta[cote]
        bout = (a[0] + dx, a[1] + dy)
        d.add(elm.Line().at(a).to(bout))
        if net not in nets:                  # un seul label par net (VCC x2…)
            d.add(elm.Dot().at(bout).label(net, loc=locs[cote], fontsize=9))
            nets[net] = bout
        else:
            d.add(elm.Dot().at(bout))
    haut = max((p[1] for p in nets.values()), default=origin[1]) + 0.8
    title_pt = (centre[0], haut + 0.4)
    if titre:
        from gui.circuit_viewer import _TITRE_COLOR
        d.add(elm.Label().at(title_pt).label(
            f"{entree['categorie']} ({entree['nom']})",
            color=_TITRE_COLOR, fontsize=11))
    sorties = [pins_nets[num] for num, f in cablees if _cote(f) == "right"]
    entrees_g = [pins_nets[num] for num, f in cablees if _cote(f) == "left"]
    return {"in": nets.get(entrees_g[0]) if entrees_g else tuple(centre),
            "out": nets.get(sorties[0]) if sorties else tuple(centre),
            "title": title_pt, "nets": nets, "absorbed_refs": set()}
```

Dans `gui/circuit_viewer.py` — le recognizer (placer près de
`_circuit_principal_ilot`) :

```python
def _puce_ilot(ilot, graph):
    """@brief Îlot dont l'unique actif est une puce identifiée non-AOP ->
    (ref, entrée catalogue), sinon None. Branché AVANT la grille générique :
    une puce identifiée ne tombe JAMAIS en vue générique."""
    from circuit_analyzer.catalogue import identifier
    raw = getattr(graph, "graph", {}).get("components", {}) or {}
    refs = [r for r in ilot.get("composants", []) if r in raw]
    actifs = [r for r in refs
              if len(getattr(raw.get(r), "pins", {}) or {}) > 2]
    if len(actifs) != 1:
        return None
    comp = raw[actifs[0]]
    if comp.type != "U":
        return None
    entree = identifier("U", getattr(comp, "value", ""))
    if entree is None or entree.get("alias"):
        return None          # inconnu -> comportement actuel ; 741 -> AOP
    return (actifs[0], entree)
```

La fabrique de figure `_make_puce_fig(ref, entree, comp_info, matches,
detaille=False)` : COPIER la structure exacte de `_make_latch_fig`
(création Figure/axes SCH_BG, `d.config(fontsize=12, inches_per_unit=0.5)`,
`_z_hitboxes`/`_comp_positions`, bbox + `set_size_inches`, `ajuster_labels`)
en remplaçant le corps de dessin par :

```python
            from gui import puce_schematic
            res = puce_schematic.dessiner_puce(d, ref, entree, comp_info)
            coupl = [m for m in (matches or []) if _est_couplage(m)]
            stage = {"components": [ref], "nodes": list(res["nets"])}
            _dessiner_impedances_locales(d, [stage], [res], coupl, set(),
                                         comp_info)
```

(La signature réelle de `_dessiner_impedances_locales` est
`(d, stages, ancres, z_matches, z_utilises, ci)` — vérifier sur place à la
ligne ~3680 et s'y conformer ; les blocs Z des passifs voisins deviennent
cliquables par la même mécanique que les chaînes.)

Branchements (les DEUX dispatchs, dérive interdite) :

1. `show_island` (~ligne 783) — calculer `_puce = _puce_ilot(ilot, graph)`
   quand tous les recognizers précédents sont None, AVANT `_paire`/`_chaine` ;
   dans `construire_fig`, avant le repli générique :

```python
        if _puce is not None:
            _ref_puce, _entree_puce = _puce
            return _make_puce_fig(_ref_puce, _entree_puce, comp_info,
                                  _matches_for_island(ilot, results),
                                  detaille=detaille)
```

2. `tools/render_ilots_v2.py` (~ligne 103) — même test avant
   `cv._paire_croisee` :

```python
    puce = cv._puce_ilot(ilot, graph)
    if puce is not None:
        return cv._make_puce_fig(puce[0], puce[1], comp_info,
                                 matches, detaille=detaille)
```

(vérifier le nom réel de la variable graphe dans `_fig_for_ilot` — `graph` —
et s'aligner).

- [ ] **Step 4: Vert**

Run: `PYTHONUTF8=1 python -m pytest tests/test_puce_drawing.py tests/test_reel_integration.py -q`
Expected: PASS.

- [ ] **Step 5: Boucle visuelle OBLIGATOIRE**

Rendre les PNG des DEUX vues des 8 `reel_*.xml` (réutiliser le pattern du
script scratchpad d'audit : `render_ilots_v2._fig_for_ilot` sur chaque îlot,
`savefig`). LES INSPECTER UN PAR UN (broches lisibles, nets non superposés,
Z cliquables présents, canvas clair). Corriger AVANT de committer.

- [ ] **Step 6: Commit**

```bash
git add gui/puce_schematic.py gui/circuit_viewer.py tools/render_ilots_v2.py tests/test_puce_drawing.py
git commit -m "feat(dessin): boite puce elm.Ic + ilot '1 puce + Z autour' (jamais generique)"
```

---

### Task 6: LED colorée

**Files:**
- Modify: `gui/circuit_viewer.py` (site(s) où une `D` est dessinée — les trouver via `grep -n "Diode" gui/circuit_viewer.py gui/impedance_schematic.py`)
- Test: `tests/test_puce_drawing.py` (ajout)

**Interfaces:**
- Consumes: `identifier()` ; corpus `reel_led_r.xml`.
- Produces: helper `_symbole_diode(ref, ci)` dans circuit_viewer, utilisé à chaque site de dessin d'une diode.

- [ ] **Step 1: Test qui échoue**

```python
# à ajouter dans tests/test_puce_drawing.py
def test_led_dessinee_en_led_coloree():
    comps = lire_xml("circuits_industriels/reel_led_r.xml")
    g = construire_graphe(comps)
    res = analyser(g)
    ilot = max(res.ilots, key=lambda i: len(i.get("composants", [])))
    from tools.render_ilots_v2 import _fig_for_ilot   # via sys.path tools/
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
          for c in comps}
    fig = _fig_for_ilot(ilot, g, ci, res, detaille=True)
    # au moins un élément LED (schemdraw pose des flèches de rayonnement :
    # on vérifie par la couleur rouge d'un patch/ligne de l'axe)
    import matplotlib.colors as mcolors
    rouge = mcolors.to_rgba("red")
    ax = fig.axes[0]
    couleurs = ([l.get_color() for l in ax.lines]
                + [p.get_edgecolor() for p in ax.patches])
    assert any(mcolors.to_rgba(c) == rouge for c in couleurs), \
        "aucun trait rouge : la LED n'est pas dessinée en LED colorée"
```

(NB : si l'import de `_fig_for_ilot` diffère, reprendre l'idiome exact du
script d'audit `render_logic_all.py` — `sys.path.insert` sur `tools/`.)

- [ ] **Step 2: Vérifier l'échec.**

- [ ] **Step 3: Implémentation** — helper dans `circuit_viewer.py` :

```python
def _symbole_diode(ref, ci):
    """@brief elm.LED coloré si la D est identifiée LED, sinon elm.Diode."""
    from circuit_analyzer.catalogue import identifier
    info = ci.get(ref, {}) or {}
    entree = identifier("D", info.get("value", ""))
    if entree and entree.get("symbole") == "led":
        return elm.LED().color(entree["couleur"])
    return elm.Diode()
```

Puis, à CHAQUE site trouvé au grep où `elm.Diode()` est instancié avec une
ref de composant disponible, substituer `_symbole_diode(ref, ci)` (en passant
`ci` si le site ne l'a pas déjà). Garder l'orientation existante du site.

- [ ] **Step 4: Vert + PNG inspecté** (`reel_led_r.xml`, deux vues — la LED
doit être rouge, l'étiquette lisible).

- [ ] **Step 5: Commit**

```bash
git add gui/circuit_viewer.py tests/test_puce_drawing.py
git commit -m "feat(dessin): LED coloree (catalogue) a la place de la diode generique"
```

---

### Task 7: Rapport « Composants réels identifiés »

**Files:**
- Modify: `circuit_analyzer/rapport.py` (fonction `generate`)
- Test: `tests/test_reel_integration.py` (ajout)

**Interfaces:**
- Consumes: `identifier()` ; `generate(results, input_file, total_components, all_refs=...)` (signature réelle — cf. tests/test_logic_integration.py:139).
- Produces: une section rapport listant les composants identifiés.

- [ ] **Step 1: Test qui échoue**

```python
# à ajouter dans tests/test_reel_integration.py
def test_rapport_liste_les_composants_reels():
    from circuit_analyzer.rapport import generate
    comps = lire_xml("circuits_industriels/reel_555_astable.xml")
    res = analyser(construire_graphe(comps))
    texte = generate(res, "reel_555_astable.xml", len(comps),
                     all_refs=[c.ref for c in comps])
    assert "U1" in texte and "Timer" in texte and "NE555" in texte
```

- [ ] **Step 2: Vérifier l'échec.**

- [ ] **Step 3: Implémentation** — `generate` ne reçoit que des refs, pas les
composants : ajouter un paramètre optionnel `composants=None` (liste de
`Composant`) SANS casser les appels existants, et le renseigner depuis
`gui/tab_analyze.py::_coeur_analyse` (l'appelant réel a `comps` sous la
main). Dans `generate`, après la section des montages :

```python
    if composants:
        from circuit_analyzer.catalogue import identifier
        lignes_reelles = []
        for c in composants:
            e = identifier(getattr(c, 'type', ''), getattr(c, 'value', ''))
            if e:
                lignes_reelles.append(
                    f"    {c.ref} - {e['categorie']} ({e['nom']})")
        if lignes_reelles:
            lignes.append('Composants reels identifies :')
            lignes.extend(lignes_reelles)
```

Adapter le test pour passer `composants=comps` là où l'appelant le fait ;
mettre à jour l'appel dans `tab_analyze.py`.

DÉVIATION SPEC ACTÉE (à rappeler au reviewer) : la spec §5 mentionnait
`_CATEGORIES`/`functional_category` — non applicable en v1 : les puces ne
produisent AUCUN match (pas de détection de montages), donc
`functional_category` n'est jamais évalué pour elles. La catégorie est
surfacée par cette section rapport + le titre de la figure îlot (Task 5).
Idem pour la couleur de l'onglet Analyser (les cartes affichent des matches).

- [ ] **Step 4: Vert** — `PYTHONUTF8=1 python -m pytest tests/test_reel_integration.py tests/test_logic_integration.py -q`.

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/rapport.py gui/tab_analyze.py tests/test_reel_integration.py
git commit -m "feat(rapport): section composants reels identifies (catalogue)"
```

---

### Task 8: Contrats corpus + sweep final + exe

**Files:**
- Modify: `tests/test_labels_property.py`, `tests/test_puces_resolution.py`, `tools/render_ilots_v2.py` (globs — motif existant lignes ~27-32 de test_puces_resolution.py)
- Test: suite complète.

- [ ] **Step 1: Étendre les globs** — dans les trois fichiers, ajouter au
motif corpus existant :

```python
    + glob.glob("circuits_industriels/reel_*.xml")
```

- [ ] **Step 2: Vert intégral** — corriger le DESSIN (jamais les tests) si
labels en collision ou puce bandeau non résolue ; **ZÉRO nouvelle exclusion**
dans test_puces_resolution.py.

Run: `PYTHONUTF8=1 python -m pytest -q`
Expected: tout vert (1318+ + nouveaux).

- [ ] **Step 3: Boucle visuelle finale** — `python tools/render_ilots_v2.py`
+ PNG des deux vues des 8 reel_* inspectés un à un (critère boss).

- [ ] **Step 4: Exe** — `python tools/build_exe.py` →
`Distribution prête : ... AnalyseurCircuits-1.7.0.zip` + smoke « Rapport conforme ».
(Si « fichier verrouillé » : une instance de l'exe est ouverte — demander au
boss de la fermer, ne pas tuer le process.)

- [ ] **Step 5: Commit**

```bash
git add tests/ tools/render_ilots_v2.py
git commit -m "test(catalogue): contrats corpus etendus aux reel_* (labels, puces, sweep)"
```

---

## Ordre et dépendances

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 (séquentiel strict : chaque task consomme les interfaces de la précédente).

## Critères d'acceptation globaux (rappel spec)

- Chaque référence de la liste identifiée (tests Task 1).
- Un îlot à puce identifiée ne tombe JAMAIS en grille générique (Task 5).
- 741 broches numérotées détecté « Amplificateur inverseur (AOP) » (Tasks 2-4).
- Suite complète verte, zéro nouvelle exclusion de puce bandeau.
- PNG deux vues du corpus reel_* rendus et INSPECTÉS.
- Exe reconstruit + smoke test.
- Ledger `.superpowers/sdd/progress.md` tenu à jour task par task.
