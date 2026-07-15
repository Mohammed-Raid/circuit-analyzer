# Onglet « Saisie » rapide — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un 5e onglet où l'on construit un circuit au clavier (tableau netlist + insertion catalogue), enregistré en XML BoardSCH et analysable en un clic.

**Architecture:** Modèle pur `circuit_analyzer/saisie.py` (refs auto, validation, lignes ↔ Composant, sans Tk) consommé par `gui/tab_quick_entry.py` (widgets seuls, pattern TabDraw). Le catalogue expose un itérateur public ; `lire_xml` gagne un opt-out d'aliasing rétro-compatible.

**Tech Stack:** Python 3.14 local (`python`), customtkinter/ui_kit existants, pytest. Aucune dépendance nouvelle.

**Spec:** `docs/superpowers/specs/2026-07-15-onglet-saisie-rapide-design.md`

## Global Constraints

- `PYTHONUTF8=1` devant chaque commande python/pytest (shell cp1252).
- `circuit_analyzer/saisie.py` : AUCUN import tkinter/customtkinter/matplotlib (test subprocess, pattern schema_grid).
- AUCUN hex en dur dans gui/tab_quick_entry.py : tokens `gui.theme` / `ui_kit` uniquement (le test grep anti-hex ne couvre que les 4 modules de dessin, mais la règle chrome s'applique — le reviewer la vérifie).
- Rails standard proposés en autocomplétion, dans CET ordre : `VIN, VOUT, VCC, GND`.
- `lire_xml(chemin)` sans argument : comportement STRICTEMENT inchangé (aliasing appliqué) — aucun appelant existant ne change.
- Convention broche vide : absente de `Composant.pins` à la génération (net singleton `NET#` créé par generer_xml) ; à la relecture d'un fichier généré, une broche dont le net est un `NET\d+` singleton est réaffichée VIDE.
- Suite complète verte à chaque tâche (~1636 passed / 15 skipped ; flake connu : test_500_portes_sous_budget sous charge → relancer isolément avant de conclure).
- Commits en FRANÇAIS, JAMAIS de footer Co-Authored-By/Generated. `git add` fichier par fichier, JAMAIS -A (docs.rar non suivi = fichier du boss, intouchable). Rien n'est poussé.

---

### Task 1: catalogue.entrees_catalogue() + lire_xml opt-out d'aliasing

**Files:**
- Modify: `circuit_analyzer/catalogue.py` (fin de fichier)
- Modify: `circuit_analyzer/xml.py:1093` (signature lire_xml) et `:1274-1276` (garde)
- Test: `tests/test_saisie_fondations.py`

**Interfaces:**
- Produit : `catalogue.entrees_catalogue()` — générateur de tuples `(type_, value, entree)` où `entree` est le dict catalogue (`categorie`, `nom`, `broches`, ...). Couvre : `_EXACTS_U`, `_FAMILLES_74HC` (value préfixée `74HC`), `_SUFFIXES_U`, `_EXACTS_Q`, `_EXACTS_M`, `_EXACTS_D`, LED (`("D", "LED rouge"/"LED verte"/"LED bleue")`).
- Produit : `lire_xml(chemin, alias_catalogue=True)` — `False` = lecture brute (pas d'`appliquer_catalogue`).

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_saisie_fondations.py
"""@file test_saisie_fondations.py
@brief Fondations de l'onglet Saisie (spec 2026-07-15 §2.3/§3.3) :
itérateur public du catalogue et lecture XML sans aliasing.
"""
from pathlib import Path

from circuit_analyzer.catalogue import entrees_catalogue, identifier
from circuit_analyzer.xml import lire_xml

ROOT = Path(__file__).resolve().parent.parent


def test_entrees_catalogue_couvre_les_familles():
    entrees = list(entrees_catalogue())
    valeurs = {(t, v) for t, v, _e in entrees}
    for attendu in [("U", "NE555"), ("U", "74HC00"), ("U", "LM317"),
                    ("U", "7805"), ("Q", "2N2222"), ("M", "IRFZ44N"),
                    ("D", "1N4148"), ("D", "LED rouge")]:
        assert attendu in valeurs, attendu


def test_entrees_catalogue_coherentes_avec_identifier():
    # Chaque entrée listée doit être re-identifiée par identifier()
    # (même nom de catalogue) : l'itérateur ne peut pas dériver des tables.
    for type_, value, entree in entrees_catalogue():
        vu = identifier(type_, value)
        assert vu is not None, (type_, value)
        assert vu["nom"] == entree["nom"], (type_, value)


def test_lire_xml_sans_aliasing_garde_les_broches_numerotees():
    chemin = str(ROOT / "circuits_industriels" / "reel_741_inverseur.xml")
    brut = lire_xml(chemin, alias_catalogue=False)
    u1 = next(c for c in brut if c.ref == "U1")
    assert set(u1.pins) == {"2", "3", "6", "7", "4"}


def test_lire_xml_defaut_inchange_broches_aliassees():
    chemin = str(ROOT / "circuits_industriels" / "reel_741_inverseur.xml")
    alias = lire_xml(chemin)
    u1 = next(c for c in alias if c.ref == "U1")
    assert {"IN-", "IN+", "OUT"} <= set(u1.pins)
```

- [ ] **Step 2: Vérifier l'échec**

Run: `PYTHONUTF8=1 python -m pytest tests/test_saisie_fondations.py -q`
Expected: FAIL — `ImportError: cannot import name 'entrees_catalogue'`

- [ ] **Step 3: Implémenter**

Ajouter à la fin de `circuit_analyzer/catalogue.py` :

```python
def entrees_catalogue():
    """@brief Itère (type_, value, entree) sur tout le catalogue affichable.

    Source UNIQUE : les tables du module (aucune liste dupliquée). `value`
    est la chaîne telle qu'un utilisateur la saisirait (re-identifiable par
    `identifier()`). Consommé par l'onglet Saisie (« + Puce réelle »).
    """
    for v, e in _EXACTS_U.items():
        yield "U", v, e
    for suffixe, e in _FAMILLES_74HC.items():
        yield "U", f"74HC{suffixe}", e
    for suffixe, e in _SUFFIXES_U.items():
        yield "U", suffixe, e
    for v, e in _EXACTS_Q.items():
        yield "Q", v, e
    for v, e in _EXACTS_M.items():
        yield "M", v, e
    for v, e in _EXACTS_D.items():
        yield "D", v, e
    for cle, (couleur, fr) in _COULEURS_LED.items():
        e = dict(_e("LED", fr, None, symbole="led"))
        e["couleur"] = couleur
        yield "D", f"LED {fr}", e
```

Dans `circuit_analyzer/xml.py`, changer la signature (ligne 1093) :

```python
def lire_xml(chemin: str, alias_catalogue: bool = True) -> list:
```

et compléter la docstring (`@param alias_catalogue False = lecture BRUTE,
sans renommage des broches par le catalogue — utilisé par l'onglet Saisie
pour éditer le fichier tel quel`), puis garder l'appel existant (ligne
~1274-1276) sous condition :

```python
    if alias_catalogue:
        from circuit_analyzer.catalogue import appliquer_catalogue
        appliquer_catalogue(composants)

    return composants
```

- [ ] **Step 4: Vérifier le vert + non-régression**

Run: `PYTHONUTF8=1 python -m pytest tests/test_saisie_fondations.py tests/test_catalogue.py tests/test_xml_generator.py -q`
Expected: tout vert.

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/catalogue.py circuit_analyzer/xml.py tests/test_saisie_fondations.py
git commit -m "feat(saisie): entrees_catalogue() public + lire_xml sans aliasing (opt-out retro-compatible)"
```

---

### Task 2: circuit_analyzer/saisie.py — modèle pur du tableau

**Files:**
- Create: `circuit_analyzer/saisie.py`
- Test: `tests/test_saisie.py`

**Interfaces:**
- Consomme : `entrees_catalogue`, `identifier` (Task 1) ; `charger_bibliotheque`, `Composant` de `circuit_analyzer.composant` ; `generer_xml`/`lire_xml` (round-trip, tests seulement).
- Produit (utilisé par Task 3) :
  - `LigneSaisie(ref: str, type: str, value: str, pins: dict[str, str], fonctions: dict[str, str])` (dataclass, mutable)
  - `RAILS = ("VIN", "VOUT", "VCC", "GND")`
  - `ModeleSaisie()` : `.lignes` (list), `.ref_auto(type_) -> str`, `.ajouter(type_, value="", pins=None, fonctions=None) -> LigneSaisie`, `.ajouter_catalogue(type_, value) -> LigneSaisie`, `.supprimer(index)`, `.nets_connus() -> list[str]`, `.valider() -> (list[str], list[str])`, `.vers_composants() -> list[Composant]`, `ModeleSaisie.depuis_composants(comps)` (classmethod).

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_saisie.py
"""@file test_saisie.py
@brief Modèle pur de l'onglet Saisie (spec 2026-07-15 §3.2) : refs auto,
catalogue, validation, nets connus, round-trip XML, pureté d'import.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from circuit_analyzer.saisie import RAILS, LigneSaisie, ModeleSaisie
from circuit_analyzer.xml import generer_xml, lire_xml


def test_ref_auto_par_prefixe_de_type():
    m = ModeleSaisie()
    assert m.ajouter("R").ref == "R1"
    assert m.ajouter("R").ref == "R2"
    assert m.ajouter("C").ref == "C1"
    u = m.ajouter("U")
    assert u.ref == "U1"
    m.supprimer(m.lignes.index(u))
    assert m.ajouter("U").ref == "U1"   # index libéré réutilisé


def test_ajouter_expose_les_broches_du_type():
    m = ModeleSaisie()
    q = m.ajouter("Q")
    assert list(q.pins) == ["B", "C", "E"]
    d = m.ajouter("D")
    assert list(d.pins) == ["A", "K"]


def test_ajouter_catalogue_ne555_et_led():
    m = ModeleSaisie()
    u = m.ajouter_catalogue("U", "NE555")
    assert u.value == "NE555"
    assert list(u.pins) == [str(i) for i in range(1, 9)]
    assert u.fonctions["2"] == "TRIG" and u.fonctions["3"] == "OUT"
    led = m.ajouter_catalogue("D", "LED rouge")
    assert led.value == "LED rouge" and list(led.pins) == ["A", "K"]


def test_valider_bloquants_et_avertissements():
    m = ModeleSaisie()
    r1 = m.ajouter("R"); r1.pins["1"] = "VIN"; r1.pins["2"] = "NET1"
    r2 = m.ajouter("R"); r2.pins["1"] = "NET1"; r2.pins["2"] = "GND"
    bloquants, avert = m.valider()
    assert not bloquants and not avert
    r2.ref = "R1"                       # doublon
    bloquants, _ = m.valider()
    assert any("R1" in b for b in bloquants)
    r2.ref = "R2"
    r2.pins["2"] = "NSEUL"              # singleton
    _, avert = m.valider()
    assert any("NSEUL" in a for a in avert)


def test_nets_connus_rails_d_abord_sans_doublons():
    m = ModeleSaisie()
    r = m.ajouter("R"); r.pins["1"] = "VIN"; r.pins["2"] = "NETB"
    c = m.ajouter("C"); c.pins["1"] = "NETB"; c.pins["2"] = "NETA"
    nets = m.nets_connus()
    assert nets[:4] == list(RAILS)
    assert nets[4:] == ["NETA", "NETB"]


def test_round_trip_xml_complet():
    # Circuit mixte : R câblée, Q, U catalogue, broche VIDE (spec §3.2).
    m = ModeleSaisie()
    r = m.ajouter("R", value="10k"); r.pins["1"] = "VIN"; r.pins["2"] = "NB"
    q = m.ajouter("Q", value="2N2222")
    q.pins["B"] = "NB"; q.pins["C"] = "VCC"; q.pins["E"] = "GND"
    u = m.ajouter_catalogue("U", "NE555")
    u.pins["1"] = "GND"; u.pins["8"] = "VCC"; u.pins["3"] = "NOUT"
    r2 = m.ajouter("R", value="1k"); r2.pins["1"] = "NOUT"; r2.pins["2"] = "GND"
    with tempfile.TemporaryDirectory() as tmp:
        chemin = str(Path(tmp) / "essai.xml")
        Path(chemin).write_text(generer_xml(m.vers_composants()),
                                encoding="utf-8")
        relu = ModeleSaisie.depuis_composants(
            lire_xml(chemin, alias_catalogue=False))
    par_ref = {l.ref: l for l in relu.lignes}
    assert set(par_ref) == {"R1", "Q1", "U1", "R2"}
    assert par_ref["R1"].value == "10k"
    assert par_ref["Q1"].pins == {"B": "NB", "C": "VCC", "E": "GND"}
    # Broches non câblées de U1 : relues comme VIDES (les NET# singletons
    # crees par generer_xml sont re-masques, convention spec §3.2).
    assert par_ref["U1"].pins["2"] == ""
    assert par_ref["U1"].pins["3"] == "NOUT"


def test_import_sans_backend_graphique():
    code = ("import sys; import circuit_analyzer.saisie; "
            "sys.exit(1 if any(m in sys.modules for m in "
            "('tkinter', 'customtkinter', 'matplotlib')) else 0)")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert r.returncode == 0, r.stderr
```

- [ ] **Step 2: Vérifier l'échec**

Run: `PYTHONUTF8=1 python -m pytest tests/test_saisie.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'circuit_analyzer.saisie'`

- [ ] **Step 3: Implémenter**

```python
# circuit_analyzer/saisie.py
"""@file saisie.py
@brief Modèle PUR de l'onglet Saisie (spec 2026-07-15 §3.2) : tableau
netlist en mémoire (refs auto, validation, nets connus) et conversions
lignes ↔ Composant. AUCUN import graphique (testé en subprocess).
"""
import re
from collections import Counter
from dataclasses import dataclass, field

from circuit_analyzer.catalogue import identifier
from circuit_analyzer.composant import Composant, charger_bibliotheque

RAILS = ("VIN", "VOUT", "VCC", "GND")
_NET_AUTO = re.compile(r"NET\d+$")


@dataclass
class LigneSaisie:
    """@brief Une ligne du tableau : un composant en cours de saisie.

    pins : nom de broche -> net ("" = non câblée) ; l'ORDRE des clés est
    l'ordre d'affichage. fonctions : nom -> rôle indicatif catalogue
    ("" si aucun), ex. "2" -> "TRIG" pour un NE555.
    """
    ref: str
    type: str
    value: str = ""
    pins: dict = field(default_factory=dict)
    fonctions: dict = field(default_factory=dict)


class ModeleSaisie:
    """@brief État du tableau + opérations. L'onglet Tk ne calcule rien."""

    def __init__(self):
        self.lignes = []
        self._bibliotheque = charger_bibliotheque()

    def ref_auto(self, type_):
        """@brief Premier index libre pour le préfixe du type (R1, R2, U1…)."""
        pris = {l.ref for l in self.lignes}
        i = 1
        while f"{type_}{i}" in pris:
            i += 1
        return f"{type_}{i}"

    def _broches_du_type(self, type_):
        info = self._bibliotheque.get(type_) or {}
        return list(info.get("pins") or ("1", "2"))

    def ajouter(self, type_, value="", pins=None, fonctions=None):
        """@brief Ajoute une ligne ; broches du type si `pins` absent."""
        if pins is None:
            pins = {p: "" for p in self._broches_du_type(type_)}
        ligne = LigneSaisie(ref=self.ref_auto(type_), type=type_,
                            value=value, pins=dict(pins),
                            fonctions=dict(fonctions or {}))
        self.lignes.append(ligne)
        return ligne

    def ajouter_catalogue(self, type_, value):
        """@brief Ligne pré-remplie depuis le catalogue constructeur.

        U : broches NUMÉROTÉES du boîtier + fonctions indicatives (le flux
        réel : l'aliasing/identification existants s'appliquent à
        l'analyse). Q/M/D : broches du TYPE (B/C/E, G/D/S, A/K).
        """
        entree = identifier(type_, value) or {}
        broches = entree.get("broches")
        if type_ == "U" and broches:
            pins = {num: "" for num in sorted(broches, key=int)}
            fonctions = {num: broches[num] for num in pins}
            return self.ajouter(type_, value, pins, fonctions)
        return self.ajouter(type_, value)

    def supprimer(self, index):
        del self.lignes[index]

    def nets_connus(self):
        """@brief Rails d'abord (ordre fixe), puis nets saisis triés."""
        vus = {n for l in self.lignes for n in l.pins.values() if n}
        return list(RAILS) + sorted(vus - set(RAILS))

    def valider(self):
        """@brief (bloquants, avertissements) — spec §2.5."""
        bloquants, avertissements = [], []
        refs = [l.ref for l in self.lignes]
        for ref, n in Counter(refs).items():
            if not ref:
                bloquants.append("Une ligne n'a pas de référence.")
            elif n > 1:
                bloquants.append(f"Référence en double : {ref}.")
        for l in self.lignes:
            if not l.type:
                bloquants.append(f"{l.ref or '(sans ref)'} : type manquant.")
        compte_nets = Counter(n for l in self.lignes
                              for n in l.pins.values() if n)
        for net, n in sorted(compte_nets.items()):
            if n == 1:
                avertissements.append(
                    f"Le net {net} n'apparaît qu'une fois.")
        if not self.lignes:
            avertissements.append("Aucun composant saisi.")
        return bloquants, avertissements

    def vers_composants(self):
        """@brief Composants prêts pour generer_xml (broches vides EXCLUES :
        generer_xml leur crée un net singleton NET#, convention existante)."""
        return [Composant(ref=l.ref, type=l.type, value=l.value,
                          pins={p: n for p, n in l.pins.items() if n})
                for l in self.lignes]

    @classmethod
    def depuis_composants(cls, comps):
        """@brief Reconstruit le tableau depuis des Composant lus (lecture
        BRUTE conseillée : lire_xml(..., alias_catalogue=False)).

        Les nets auto NET# singletons (broches non câblées à la génération)
        sont RE-MASQUÉS en champs vides ; les fonctions indicatives sont
        re-dérivées du catalogue quand la valeur est identifiée.
        """
        m = cls()
        compte = Counter(n for c in comps for n in c.pins.values() if n)
        for c in comps:
            pins = {}
            for p, net in c.pins.items():
                cache = bool(net) and _NET_AUTO.match(net) and compte[net] == 1
                pins[p] = "" if cache else (net or "")
            entree = identifier(getattr(c, "type", ""),
                                getattr(c, "value", "")) or {}
            broches = entree.get("broches") or {}
            fonctions = {p: broches.get(p, "") for p in pins}
            ligne = LigneSaisie(ref=c.ref, type=c.type,
                                value=getattr(c, "value", "") or "",
                                pins=pins, fonctions=fonctions)
            m.lignes.append(ligne)
        return m
```

- [ ] **Step 4: Vérifier le vert**

Run: `PYTHONUTF8=1 python -m pytest tests/test_saisie.py tests/test_saisie_fondations.py -q`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/saisie.py tests/test_saisie.py
git commit -m "feat(saisie): modele pur du tableau netlist (refs auto, catalogue, validation, round-trip XML)"
```

---

### Task 3: gui/tab_quick_entry.py — l'onglet

**Files:**
- Create: `gui/tab_quick_entry.py`
- Test: `tests/test_tab_quick_entry.py`

**Interfaces:**
- Consomme : `ModeleSaisie`/`RAILS` (Task 2), `entrees_catalogue` (Task 1), `generer_xml`, `lire_xml(..., alias_catalogue=False)`, `gui.ui_kit`, `gui.theme`.
- Produit : `TabQuickEntry(parent, on_analyze=None, on_saved=None)` avec `.frame` (pattern TabDraw) ; attributs de test : `._modele`, `._ajouter_type(type_)`, `._inserer_catalogue(type_, value)`, `._enregistrer(chemin=None)`, `._analyser()`, `._btn_analyser`, `._lignes_widgets` (list de dicts {"ref": Entry, "type": menu, "value": Entry, "pins": dict[nom -> widget]}).

- [ ] **Step 1: Écrire les tests qui échouent**

Style Tk du repo (regarder `tests/test_island_viewport.py` pour la fixture
racine CTk et le skip sans display ; reproduire l'idiome local, ex.
`pytest.importorskip` + try/except sur l'init Tk) :

```python
# tests/test_tab_quick_entry.py
"""@file test_tab_quick_entry.py
@brief Onglet Saisie (spec 2026-07-15 §2) : construction, broches par type,
insertion catalogue, enregistrer/analyser, validation UI.
"""
import tempfile
from pathlib import Path

import pytest

ctk = pytest.importorskip("customtkinter")

from circuit_analyzer.xml import lire_xml           # noqa: E402
from gui.tab_quick_entry import TabQuickEntry       # noqa: E402


@pytest.fixture
def racine():
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("pas de display Tk")
    root.withdraw()
    yield root
    root.destroy()


def test_ajout_r_puis_type_q_reconstruit_les_broches(racine):
    tab = TabQuickEntry(racine)
    tab._ajouter_type("R")
    assert list(tab._lignes_widgets[0]["pins"]) == ["1", "2"]
    tab._changer_type(0, "Q")
    assert list(tab._lignes_widgets[0]["pins"]) == ["B", "C", "E"]
    assert tab._modele.lignes[0].type == "Q"


def test_insertion_catalogue_ne555_libelle_les_broches(racine):
    tab = TabQuickEntry(racine)
    tab._inserer_catalogue("U", "NE555")
    ligne = tab._modele.lignes[0]
    assert ligne.value == "NE555" and len(ligne.pins) == 8
    libelles = tab._libelles_broches(0)
    assert "2 (TRIG)" in libelles and "3 (OUT)" in libelles


def test_enregistrer_produit_un_xml_relisible(racine, tmp_path):
    tab = TabQuickEntry(racine)
    tab._ajouter_type("R")
    tab._modele.lignes[0].pins.update({"1": "VIN", "2": "GND"})
    chemin = str(tmp_path / "essai.xml")
    tab._enregistrer(chemin)
    assert len(lire_xml(chemin)) == 1


def test_analyser_appelle_le_callback(racine, tmp_path, monkeypatch):
    appels = []
    tab = TabQuickEntry(racine, on_analyze=appels.append)
    tab._ajouter_type("R")
    tab._modele.lignes[0].pins.update({"1": "VIN", "2": "GND"})
    monkeypatch.setattr(tab, "_chemin_analyse",
                        lambda: str(tmp_path / "tmp.xml"))
    tab._analyser()
    assert len(appels) == 1 and appels[0].endswith(".xml")


def test_ref_dupliquee_grise_analyser(racine):
    tab = TabQuickEntry(racine)
    tab._ajouter_type("R"); tab._ajouter_type("R")
    tab._modele.lignes[1].ref = "R1"
    tab._rafraichir_validation()
    assert tab._btn_analyser.cget("state") == "disabled"
```

- [ ] **Step 2: Vérifier l'échec**

Run: `PYTHONUTF8=1 python -m pytest tests/test_tab_quick_entry.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gui.tab_quick_entry'` (ou skip intégral sans display : dans ce cas noter le skip et s'appuyer sur le RED des méthodes une fois le module créé vide).

- [ ] **Step 3: Implémenter l'onglet**

Structure imposée (suivre le style TabDraw : en-tête CARD, zone centrale,
barre inférieure CARD2 ; boutons `ui_kit.SecondaryButton`/`PrimaryButton`
selon ce que ui_kit expose — vérifier dans gui/ui_kit.py) :

```python
# gui/tab_quick_entry.py
"""@file tab_quick_entry.py
@brief Onglet « Saisie » : tableau netlist clavier + insertion catalogue
(spec 2026-07-15). Les CALCULS vivent dans circuit_analyzer.saisie ;
ce module ne fait que les widgets.
"""
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, Optional

import customtkinter as ctk

from circuit_analyzer.composant import charger_bibliotheque
from circuit_analyzer.saisie import ModeleSaisie
from circuit_analyzer.catalogue import entrees_catalogue
from circuit_analyzer.xml import generer_xml, lire_xml
from gui import ui_kit
from gui.theme import (BG, CARD, CARD2, OVERLAY, TEXT, TEXT_MUTED,
                        TEXT_DIM, ERROR, WARN)


class TabQuickEntry:
    """@brief Onglet Saisie (pattern TabDraw : .frame + callbacks)."""

    def __init__(self, parent, on_analyze: Optional[Callable] = None,
                 on_saved: Optional[Callable] = None):
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color=BG)
        self._on_analyze = on_analyze
        self._on_saved = on_saved
        self._modele = ModeleSaisie()
        self._lignes_widgets = []
        self._chemin_courant = None
        self._build()
```

Corps à réaliser (détail impératif, l'implémenteur écrit le code widget en
suivant ces règles) :

1. `_build` : en-tête (titre « Saisie rapide » + aide courte), barre
   d'actions haute ([+ Composant] menu des types de la bibliothèque,
   [+ Puce réelle] → `_popup_catalogue`, [Ouvrir…] `_ouvrir`,
   [Enregistrer] `_enregistrer`, [Analyser] `_analyser` — garder la
   référence `self._btn_analyser`), zone scrollable (même technique
   tk.Canvas + frame interne + scrollbar que `gui/tab_analyze.py`
   lignes ~154-165 — la reprendre, pas de CTkScrollableFrame), barre
   d'état basse (`self._lbl_etat` : fichier courant + n composants +
   1er message de validation, couleur ERROR si bloquant, WARN si
   avertissement, TEXT_MUTED sinon).
2. `_ajouter_type(type_)` : `self._modele.ajouter(type_)` puis
   `_construire_ligne(index)` ; `_changer_type(index, type_)` : remplace
   la ligne du modèle (nouvelles broches du type via
   `ModeleSaisie._broches_du_type` — exposer une méthode publique
   `changer_type(index, type_)` DANS LE MODÈLE plutôt que de bidouiller
   côté widget : l'ajouter à saisie.py avec un test unitaire dans
   test_saisie.py) puis reconstruit les widgets de la ligne.
3. `_construire_ligne(index)` : un CTkFrame par ligne — Entry ref (liée au
   modèle par trace/FocusOut), option-menu type, Entry valeur, puis un
   widget par broche : `ttk.Combobox` éditable (values =
   `self._modele.nets_connus()` rafraîchies au clic/focus via
   postcommand), libellé au-dessus `nom` ou `nom (FONCTION)` si
   `ligne.fonctions[nom]`. Bouton ✕ → `self._modele.supprimer(index)` +
   reconstruction. `_libelles_broches(index)` renvoie la liste des
   libellés affichés (pour les tests).
   Bindings clavier : Entrée sur le dernier champ broche →
   `_ajouter_type(type de la ligne)`.
4. Chaque modification (ref, net, valeur) répercute dans le modèle PUIS
   appelle `_rafraichir_validation()` : `bloquants, avert =
   self._modele.valider()` ; Analyser+Enregistrer `state="disabled"` si
   bloquants ; message dans `self._lbl_etat`.
5. `_popup_catalogue` : CTkToplevel (titre « Catalogue »), Entry filtre +
   tk.Listbox (styles tokens), remplie de `f"{value} — {entree['categorie']}"`
   depuis `entrees_catalogue()` triée par value ; Entrée/double-clic →
   `_inserer_catalogue(type_, value)` + fermeture.
   `_inserer_catalogue(type_, value)` : `self._modele.ajouter_catalogue`
   + `_construire_ligne`.
6. `_enregistrer(chemin=None)` : si bloquants → messagebox et abandon ;
   chemin = argument, sinon `self._chemin_courant`, sinon
   `filedialog.asksaveasfilename(initialdir="custom_circuits",
   defaultextension=".xml")` ; écrit `generer_xml(self._modele.
   vers_composants())` (encoding utf-8) ; mémorise `_chemin_courant`,
   met à jour l'état, appelle `self._on_saved()` si fourni.
7. `_chemin_analyse()` : chemin temporaire stable (reprendre l'idiome de
   TabDraw pour son fichier temporaire — même dossier) ; `_analyser()` :
   `_enregistrer(self._chemin_courant or self._chemin_analyse())` puis
   `self._on_analyze(chemin)` si fourni.
8. `_ouvrir(chemin=None)` : dialogue sur custom_circuits/ si pas
   d'argument ; `ModeleSaisie.depuis_composants(lire_xml(chemin,
   alias_catalogue=False))` ; reconstruit toutes les lignes ;
   `_chemin_courant = chemin`.
9. AUCUN hex : uniquement les tokens importés. Combobox ttk : appliquer
   un ttk.Style local aux couleurs tokens (fieldbackground=OVERLAY,
   foreground=TEXT) — pas de hex.

- [ ] **Step 4: Vérifier le vert**

Run: `PYTHONUTF8=1 python -m pytest tests/test_tab_quick_entry.py tests/test_saisie.py -q`
Expected: PASS (ou skips display légitimes en environnement sans écran —
sur CE poste il y a un display, les tests doivent réellement passer).

- [ ] **Step 5: Commit**

```bash
git add gui/tab_quick_entry.py circuit_analyzer/saisie.py tests/test_tab_quick_entry.py tests/test_saisie.py
git commit -m "feat(saisie): onglet Saisie - tableau netlist clavier, catalogue, ouvrir/enregistrer/analyser"
```

---

### Task 4: Intégration app_window + clôture

**Files:**
- Modify: `gui/app_window.py:103-129` (création des onglets, `_frames`, navigation)
- Test: `tests/test_app_window.py` (étendre s'il existe, sinon vérification via test Tk minimal dans test_tab_quick_entry.py)

**Interfaces:**
- Consomme : `TabQuickEntry(parent, on_analyze=..., on_saved=...)` (Task 3).

- [ ] **Step 1: Lire l'existant**

Lire `gui/app_window.py` EN ENTIER (~150 lignes autour de la zone 103-129
vue au plan) : comment les 4 onglets sont créés, l'ordre de `self._frames`,
comment la barre de navigation nomme/affiche les onglets, et le câblage
`on_analyze` de TabDraw (`tab_a._file_path.set(path)` + `tab_a._analyze()`).

- [ ] **Step 2: Test qui échoue**

Ajouter à `tests/test_tab_quick_entry.py` :

```python
def test_app_window_a_l_onglet_saisie(racine):
    # L'app expose 5 onglets et le 5e est la Saisie (spec §2.1). On
    # instancie la fenêtre complète — même pattern que les tests existants
    # de l'app s'il y en a, sinon construction directe.
    from gui.app_window import AppWindow   # adapter au nom réel de la classe
    app = AppWindow()
    try:
        assert any("Saisie" in str(b.cget("text"))
                   for b in app._nav_buttons)   # adapter à l'attribut réel
    finally:
        app.destroy()
```

NOTE à l'implémenteur : les noms `AppWindow`/`_nav_buttons` sont à ADAPTER
à ce que Step 1 révèle ; le CONTRAT du test est : la fenêtre expose un 5e
onglet nommé « Saisie », branché sur TabQuickEntry.

Run: `PYTHONUTF8=1 python -m pytest tests/test_tab_quick_entry.py -q -k app_window`
Expected: FAIL (import ou assertion).

- [ ] **Step 3: Intégrer**

Dans `gui/app_window.py`, sur le modèle exact du câblage TabDraw existant :

```python
        from gui.tab_quick_entry import TabQuickEntry
        tab_s = TabQuickEntry(
            content,
            on_analyze=lambda path: (self._show_frame(0),
                                     tab_a._file_path.set(path),
                                     tab_a._analyze()),
            on_saved=lambda: tab_c.refresh_circuits(),
        )
```

(adapter `self._show_frame(0)` au mécanisme réel de bascule d'onglet vu au
Step 1 — l'analyse doit AMENER l'utilisateur sur l'onglet Analyser, comme
le fait le flux TabDraw) ; ajouter `tab_s.frame` à `self._frames` et
l'entrée « Saisie » à la navigation, APRÈS « Composants ».

- [ ] **Step 4: Suite complète + vérification manuelle**

Run: `PYTHONUTF8=1 python -m pytest -q`
Expected: verte intégrale (~1650 ; flake perf connu → relancer isolément).

Lancer l'app 10 secondes pour une vérification humaine du chrome :
`PYTHONUTF8=1 python main.py` (ou le point d'entrée réel — le trouver via
`git grep -l "AppWindow("`) — ouvrir l'onglet Saisie, ajouter un R et un
NE555 catalogue, vérifier visuellement l'alignement/les couleurs, fermer.
Décrire ce qui a été vu dans le rapport.

- [ ] **Step 5: Commit**

```bash
git add gui/app_window.py tests/test_tab_quick_entry.py
git commit -m "feat(saisie): onglet Saisie branche dans l'app (analyse directe, rafraichissement Circuits)"
```

---

## Self-review (fait à l'écriture du plan)

- Spec §2.1→T3/T4, §2.2→T2/T3, §2.3→T1/T2/T3, §2.4→T3/T4, §2.5→T2/T3,
  §3.2→T2, §3.3→T1, §3.4→T3, §3.5→T4, §5 tests 1-8→T1/T2, 9-12→T3/T4.
- `changer_type` ajouté au modèle en T3 avec test unitaire (découvert en
  écrivant le test widget) — noté dans la tâche.
- Noms d'attributs app_window inconnus du plan : Step 1 de T4 impose la
  lecture, le test énonce le CONTRAT et signale explicitement l'adaptation.
