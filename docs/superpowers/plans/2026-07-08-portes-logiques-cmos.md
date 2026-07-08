# Portes logiques CMOS v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Détecter les portes CMOS (NOT/NAND-N/NOR-N) construites en MOSFET dans les netlists BoardSCH et les afficher avec la symétrie complète vue simplifiée (symbole) ↔ vue détaillée (transistors).

**Architecture:** Un module de détection pur `circuit_analyzer/logique.py` (algèbre d'arbres série/parallèle isolée + graphe de conduction + classification par formes pures), UN détecteur `detecter_portes_cmos` en tête de `_DETECTEURS_COMPLEXES`, un module de dessin dédié `gui/logic_schematic.py` enregistré dans `_DRAWERS`, et un champ `match['io']` lu en priorité par `_io_montage` (jamais d'extension de whitelist). Spec : `docs/superpowers/specs/2026-07-08-portes-logiques-cmos-design.md`.

**Tech Stack:** Python 3.14, NetworkX (graphe), schemdraw 0.22 (`schemdraw.logic.Not/Nand/Nor`, `elm.PFet/NFet`), matplotlib, pytest, corpus BoardSCH XML via `circuit_analyzer.xml.generer_xml`.

## Global Constraints

- `circuit_type` EXACTS : `"Inverseur (CMOS)"`, `"Porte NAND (CMOS)"`, `"Porte NOR (CMOS)"` — ce sont des clés de dispatch, ne jamais dévier.
- Contrat match (spec § 1.5) : clés `components`, `nodes` (`{'entrees': list, 'sortie', 'vdd', 'gnd'}`), `io` (`{'ins': list, 'out': str}`), `polarites` (`{ref: 'P'|'N'}`), `arbres` (`{'pull_down': arbre, 'pull_up': arbre}`), `fonction` (`('NAND', ['A','B'])`), `expression` (`"OUT = NAND(A, B)"`). Arbre = tuples `("feuille", ref)` / `("serie", [enfants])` / `("parallele", [enfants])` (convention impedance.py).
- `entrees`/`ins` triées alphabétiquement (déterminisme).
- Détection : seuls les composants `type == 'M'` ; garde « zéro M » = retour immédiat ; graphe de conduction construit UNE fois par appel ; UN SEUL détecteur émettant les trois types.
- Rejets v1 (chacun = un test nommé) : grille sur rail/masse, `sortie ∈ entrees`, grilles dupliquées dans un réseau, pull-up touchant deux rails différents, transistor dans les deux réseaux, arbre non pur, non-dualité formes/multisets, cas 1+1 sans source-au-rail.
- Dessin : nouveau module `gui/logic_schematic.py` (PAS dans circuit_viewer.py) ; canvas schéma reste CLAIR (`SCH_BG`) ; `elm.NFet/PFet` toujours `.reverse()` (grille à gauche) ; chaque drawer appelle `_enregistrer_position` (contrat puces) et retourne le dict d'ancres `{"in", "out", "title", "nets", "absorbed_refs"}`.
- Messages/commits en FRANÇAIS ; JAMAIS de footer « Co-Authored-By: Claude » ni « Generated with Claude Code » dans les commits.
- Après toute modification de dessin : rendus PNG inspectés (boucle visuelle boss), pas seulement des tests verts.
- Zéro nouvelle exclusion dans tests/test_puces_resolution.py.
- Ne pas toucher au fichier non suivi `docs.rar`.

## File Structure

| Fichier | Rôle |
|---|---|
| Create `circuit_analyzer/logique.py` | Algèbre d'arbres (fonctions pures) + graphe de conduction + réseaux + classification + `detecter_portes_cmos` |
| Create `tests/test_logique.py` | Unitaires détection (arbres, réseaux, D/S, rejets, matches) |
| Modify `circuit_analyzer/detecteur.py` | Import + insertion tête `_DETECTEURS_COMPLEXES` + `NOMS_CIRCUITS` |
| Create `tools/gen_logic_corpus.py` | Génère les `circuits_industriels/logic_*.xml` via `generer_xml` |
| Create `circuits_industriels/logic_*.xml` (10) | Corpus (cf. tableau spec § 3) |
| Create `tests/test_logic_integration.py` | Détection sur fichiers réels, anti-faux-positifs, non-régression, chaîne/DAG/latch, rapport |
| Modify `gui/circuit_viewer.py` | `_io_montage` lecture prioritaire `io` (~8 lignes) ; 3 entrées `_DRAWERS` ; en-tête expression |
| Create `gui/logic_schematic.py` | `dessiner_porte` (dispatch symbole/détaillé), layout des deux vues |
| Create `tests/test_logic_drawing.py` | Ancres, positions, reverse, expression en-tête |
| Modify `tests/test_labels_property.py`, `tests/test_puces_resolution.py`, `tools/render_ilots_v2.py` | Globs + `logic_*.xml` (sauf `logic_non_dual.xml`) |
| Create `tests/test_logique_perf.py` | Garde zéro-M + budget 500 portes |

---

### Task 1: Algèbre d'arbres série/parallèle (fonctions pures)

**Files:**
- Create: `circuit_analyzer/logique.py`
- Test: `tests/test_logique.py`

**Interfaces:**
- Produces: `reduire_reseau(arcs, a, b) -> arbre | None` où `arcs = list[tuple[str, str, str]]` (ref, net1, net2), arbre = `("feuille", ref) | ("serie", [arbres]) | ("parallele", [arbres])` ; `feuilles(arbre) -> list[str]` (refs, ordre stable) ; `forme_pure(arbre) -> tuple[str, list[str]] | None` — `("feuille", [ref])`, `("serie", [refs])`, `("parallele", [refs])`, sinon `None` (arbre mixte).
- Consumes: rien (fonctions pures, aucune dépendance projet).

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/test_logique.py
"""@file test_logique.py
@brief Détection des portes CMOS (circuit_analyzer/logique.py) : algèbre
d'arbres série/parallèle, réseaux pull-up/pull-down, classification et rejets."""
import pytest

from circuit_analyzer import logique


# ── Algèbre d'arbres ─────────────────────────────────────────────────────────

def test_reduire_arete_unique():
    assert logique.reduire_reseau([("M1", "OUT", "GND")], "OUT", "GND") == \
        ("feuille", "M1")


def test_reduire_deux_en_serie():
    arbre = logique.reduire_reseau(
        [("M1", "OUT", "X"), ("M2", "X", "GND")], "OUT", "GND")
    assert arbre == ("serie", [("feuille", "M1"), ("feuille", "M2")])


def test_reduire_deux_en_parallele():
    arbre = logique.reduire_reseau(
        [("M1", "OUT", "GND"), ("M2", "OUT", "GND")], "OUT", "GND")
    assert arbre == ("parallele", [("feuille", "M1"), ("feuille", "M2")])


def test_reduire_trois_en_serie_aplatis():
    arbre = logique.reduire_reseau(
        [("M1", "OUT", "X"), ("M2", "X", "Y"), ("M3", "Y", "GND")],
        "OUT", "GND")
    assert arbre == ("serie", [("feuille", "M1"), ("feuille", "M2"),
                               ("feuille", "M3")])


def test_reduire_pont_non_serie_parallele_renvoie_none():
    # Pont de Wheatstone : irréductible en série/parallèle.
    arcs = [("M1", "A", "X"), ("M2", "A", "Y"), ("M3", "X", "B"),
            ("M4", "Y", "B"), ("M5", "X", "Y")]
    assert logique.reduire_reseau(arcs, "A", "B") is None


def test_reduire_reseau_vide_renvoie_none():
    assert logique.reduire_reseau([], "OUT", "GND") is None


def test_feuilles_ordre_stable():
    arbre = ("serie", [("feuille", "M2"), ("parallele",
             [("feuille", "M3"), ("feuille", "M1")])])
    assert logique.feuilles(arbre) == ["M2", "M3", "M1"]


def test_forme_pure():
    assert logique.forme_pure(("feuille", "M1")) == ("feuille", ["M1"])
    assert logique.forme_pure(
        ("serie", [("feuille", "M1"), ("feuille", "M2")])) == \
        ("serie", ["M1", "M2"])
    assert logique.forme_pure(
        ("parallele", [("feuille", "M1"), ("feuille", "M2")])) == \
        ("parallele", ["M1", "M2"])
    # Mixte (AOI) : pas une forme pure en v1.
    mixte = ("serie", [("feuille", "M1"),
                       ("parallele", [("feuille", "M2"), ("feuille", "M3")])])
    assert logique.forme_pure(mixte) is None
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_logique.py -q`
Expected: FAIL — `ModuleNotFoundError` ou `AttributeError: module 'circuit_analyzer.logique' has no attribute 'reduire_reseau'`.

- [ ] **Step 3: Implémentation minimale**

```python
# circuit_analyzer/logique.py
"""
@file logique.py
@brief Détection des portes logiques CMOS (NOT / NAND-N / NOR-N) construites
en MOSFET — spec docs/superpowers/specs/2026-07-08-portes-logiques-cmos-design.md.

Organisation (unités testables indépendamment) :
  1. Algèbre d'arbres série/parallèle — fonctions PURES, sans référence aux
     transistors (c'est l'unité que AOI/OAI v2 étendra). Arbres = tuples
     ("feuille", ref) / ("serie", [...]) / ("parallele", [...]) — même
     convention de forme que impedance.py, mais algèbre PROPRE à ce module
     (les arêtes portent des nets de grille, pas des dipôles : les coupler
     serait du faux DRY).
"""


def reduire_reseau(arcs, a, b):
    """@brief Réduit un réseau d'arêtes en arbre série/parallèle entre a et b.

    @param arcs list[(ref, net1, net2)] — une arête par transistor.
    @param a, b Bornes du réseau (ex. OUT et GND).
    @return arbre ("feuille"/"serie"/"parallele", ...) ou None si le réseau
            n'est pas série/parallèle (pont), est vide, ou ne relie pas a à b.
    """
    edges = [(("feuille", ref), n1, n2) for ref, n1, n2 in arcs if n1 != n2]
    if not edges:
        return None

    def _enfants(arbre, genre):
        return list(arbre[1]) if arbre[0] == genre else [arbre]

    change = True
    while change:
        change = False
        # Fusion PARALLÈLE : arêtes entre la même paire de nets.
        par_paire = {}
        fusionne = []
        for t, n1, n2 in edges:
            cle = frozenset((n1, n2))
            if cle in par_paire:
                i = par_paire[cle]
                prev_t, pn1, pn2 = fusionne[i]
                fusionne[i] = (("parallele",
                                _enfants(prev_t, "parallele") + [t]), pn1, pn2)
                change = True
            else:
                par_paire[cle] = len(fusionne)
                fusionne.append((t, n1, n2))
        edges = fusionne
        # Fusion SÉRIE : net interne (ni a ni b) de degré exactement 2.
        degres = {}
        for _t, n1, n2 in edges:
            degres[n1] = degres.get(n1, 0) + 1
            degres[n2] = degres.get(n2, 0) + 1
        for net, deg in degres.items():
            if net in (a, b) or deg != 2:
                continue
            incidentes = [e for e in edges if net in (e[1], e[2])]
            if len(incidentes) != 2:
                continue
            (t1, x1, y1), (t2, x2, y2) = incidentes
            autre1 = x1 if y1 == net else y1
            autre2 = x2 if y2 == net else y2
            edges = [e for e in edges if e not in incidentes]
            edges.append((("serie", _enfants(t1, "serie")
                           + _enfants(t2, "serie")), autre1, autre2))
            change = True
            break

    if len(edges) == 1:
        t, n1, n2 = edges[0]
        if frozenset((n1, n2)) == frozenset((a, b)):
            return t
    return None


def feuilles(arbre):
    """@brief Refs des feuilles d'un arbre, en ordre de parcours (stable)."""
    if arbre[0] == "feuille":
        return [arbre[1]]
    refs = []
    for enfant in arbre[1]:
        refs.extend(feuilles(enfant))
    return refs


def forme_pure(arbre):
    """@brief (genre, refs) si l'arbre est une FORME PURE v1, sinon None.

    Formes pures : feuille seule, série de feuilles, parallèle de feuilles.
    Un arbre mixte (AOI valide compris) renvoie None — grammaire v1, cf. spec
    § 1.4 (le comparateur de dualité canonique général est différé à AOI v2).
    """
    if arbre[0] == "feuille":
        return ("feuille", [arbre[1]])
    genre, enfants = arbre
    if all(e[0] == "feuille" for e in enfants):
        return (genre, [e[1] for e in enfants])
    return None
```

- [ ] **Step 4: Vérifier le vert**

Run: `python -m pytest tests/test_logique.py -q`
Expected: `8 passed`.

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/logique.py tests/test_logique.py
git commit -m "feat(logique): algebre d'arbres serie/parallele pure (base detection portes CMOS)"
```

---

### Task 2: Graphe de conduction et extraction des réseaux pull-up/pull-down

**Files:**
- Modify: `circuit_analyzer/logique.py`
- Test: `tests/test_logique.py`

**Interfaces:**
- Consumes: `reduire_reseau` (Task 1) ; `is_power_net`, `is_ground_net` depuis `circuit_analyzer.patterns.base` ; graphe NetworkX avec `graphe.graph['components']` = `{ref: Composant}` (Composant a `.type`, `.pins` dict).
- Produces: `graphe_conduction(graphe) -> list[tuple[str, str, str]]` (ref M, net D, net S ; liste vide si aucun M) ; `_reseau(arcs, out, terminaux, interdits) -> list[arc]` — arêtes situées sur un chemin `out` → un net de `terminaux` ne traversant ni `out` ni un net de `interdits` en position intermédiaire.

**Idiome de test** (identique aux tests détecteur existants) : construire une liste de `Composant` puis `construire_graphe` :

```python
from circuit_analyzer.composant import Composant, construire_graphe
```

- [ ] **Step 1: Tests qui échouent** (ajouter à `tests/test_logique.py`)

```python
# ── Graphe de conduction et réseaux ──────────────────────────────────────────

def _m(ref, g, d, s):
    return Composant(ref=ref, type="M", pins={"G": g, "D": d, "S": s}, value="")


def _graphe_inverseur():
    # M1 : VDD—OUT (grille A), M2 : OUT—GND (grille A). Sources aux rails.
    comps = [_m("M1", "A", "OUT", "VDD"), _m("M2", "A", "OUT", "GND")]
    return construire_graphe(comps)


def test_graphe_conduction_liste_les_arcs_ds():
    arcs = logique.graphe_conduction(_graphe_inverseur())
    assert sorted(arcs) == [("M1", "OUT", "VDD"), ("M2", "OUT", "GND")]


def test_graphe_conduction_sans_mosfet_vide():
    comps = [Composant(ref="R1", type="R", pins={"1": "A", "2": "B"}, value="1k")]
    assert logique.graphe_conduction(construire_graphe(comps)) == []


def test_reseau_pull_down_nand2():
    # Pull-down : M3 (OUT—X) + M4 (X—GND) ; pull-up : M1, M2 (OUT—VDD).
    arcs = [("M1", "OUT", "VDD"), ("M2", "OUT", "VDD"),
            ("M3", "OUT", "X"), ("M4", "X", "GND")]
    bas = logique._reseau(arcs, "OUT", {"GND"}, {"VDD"})
    assert sorted(r for r, _, _ in bas) == ["M3", "M4"]
    haut = logique._reseau(arcs, "OUT", {"VDD"}, {"GND"})
    assert sorted(r for r, _, _ in haut) == ["M1", "M2"]


def test_reseau_ne_traverse_pas_un_net_interdit():
    # Chemin OUT—VDD—GND : ne doit PAS compter M2 dans le pull-down
    # (il faudrait traverser VDD).
    arcs = [("M1", "OUT", "VDD"), ("M2", "VDD", "GND")]
    bas = logique._reseau(arcs, "OUT", {"GND"}, {"VDD"})
    assert bas == []
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_logique.py -q`
Expected: FAIL — `AttributeError: ... 'graphe_conduction'`.

- [ ] **Step 3: Implémentation** (ajouter à `circuit_analyzer/logique.py`)

```python
from circuit_analyzer.patterns.base import is_ground_net, is_power_net


def graphe_conduction(graphe):
    """@brief Arcs D/S des MOSFET : [(ref, net_D, net_S)]. UNE construction
    par appel de détection — les candidats OUT sont exclusivement les nets de
    ce graphe (jamais les nets du circuit entier : garde-fou perf, spec § 1.1).

    @return liste vide si le circuit n'a aucun composant M (garde zéro-M)."""
    arcs = []
    for ref, comp in (graphe.graph.get('components', {}) or {}).items():
        if getattr(comp, 'type', None) != 'M':
            continue
        d, s = comp.pins.get('D'), comp.pins.get('S')
        if d and s and d != s:
            arcs.append((ref, d, s))
    return arcs


def _reseau(arcs, out, terminaux, interdits):
    """@brief Arêtes situées sur AU MOINS un chemin out→terminal.

    Deux passes d'atteignabilité (les nets terminaux/interdits et `out` ne
    sont jamais TRAVERSÉS, seulement atteints) :
      R1 = arêtes atteignables depuis `out` ;
      R2 = arêtes depuis lesquelles un terminal est atteignable.
    Réseau = R1 ∩ R2.
    """
    adjacence = {}
    for i, (_ref, n1, n2) in enumerate(arcs):
        adjacence.setdefault(n1, []).append((i, n2))
        adjacence.setdefault(n2, []).append((i, n1))

    bloques = set(interdits) | {out}

    def _atteignables(departs, stop_traverse):
        vues, frontiere, arete_vue = set(departs), list(departs), set()
        while frontiere:
            net = frontiere.pop()
            for i, voisin in adjacence.get(net, ()):  # ponytail: BFS simple, tailles = nb de MOSFET
                arete_vue.add(i)
                if voisin in vues or voisin in stop_traverse:
                    vues.add(voisin)
                    continue
                vues.add(voisin)
                frontiere.append(voisin)
        return arete_vue

    r1 = _atteignables([out], set(terminaux) | set(interdits))
    r2 = _atteignables(list(terminaux), bloques)
    return [arcs[i] for i in sorted(r1 & r2)]
```

- [ ] **Step 4: Vérifier le vert**

Run: `python -m pytest tests/test_logique.py -q`
Expected: `12 passed`.

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/logique.py tests/test_logique.py
git commit -m "feat(logique): graphe de conduction D/S et extraction des reseaux pull-up/pull-down"
```

---

### Task 3: Classification, rejets et assemblage des matches (`detecter_portes_cmos`)

**Files:**
- Modify: `circuit_analyzer/logique.py`
- Test: `tests/test_logique.py`

**Interfaces:**
- Consumes: Task 1 + Task 2 ; `Composant.pins` (`{'G','D','S'}`).
- Produces: `detecter_portes_cmos(graphe) -> list[dict]` — matches au contrat EXACT de la spec § 1.5 (cf. Global Constraints). C'est LA fonction publique enregistrée dans le matcher (Task 4).

- [ ] **Step 1: Tests qui échouent** (ajouter à `tests/test_logique.py`)

```python
# ── Détection complète ───────────────────────────────────────────────────────

def _detecter(comps):
    return logique.detecter_portes_cmos(construire_graphe(comps))


def test_detecte_inverseur_cmos():
    matches = _detecter([_m("M1", "A", "OUT", "VDD"),
                         _m("M2", "A", "OUT", "GND")])
    assert len(matches) == 1
    m = matches[0]
    assert m["circuit_type"] == "Inverseur (CMOS)"
    assert sorted(m["components"]) == ["M1", "M2"]
    assert m["nodes"] == {"entrees": ["A"], "sortie": "OUT",
                          "vdd": "VDD", "gnd": "GND"}
    assert m["io"] == {"ins": ["A"], "out": "OUT"}
    assert m["polarites"] == {"M1": "P", "M2": "N"}
    assert m["fonction"] == ("NOT", ["A"])
    assert m["expression"] == "OUT = NOT(A)"
    assert m["arbres"]["pull_down"] == ("feuille", "M2")


def _nand2():
    return [_m("M1", "A", "OUT", "VDD"), _m("M2", "B", "OUT", "VDD"),
            _m("M3", "A", "OUT", "X"), _m("M4", "B", "X", "GND")]


def test_detecte_nand2():
    matches = _detecter(_nand2())
    assert len(matches) == 1
    m = matches[0]
    assert m["circuit_type"] == "Porte NAND (CMOS)"
    assert m["nodes"]["entrees"] == ["A", "B"]
    assert m["fonction"] == ("NAND", ["A", "B"])
    assert m["expression"] == "OUT = NAND(A, B)"
    assert m["polarites"] == {"M1": "P", "M2": "P", "M3": "N", "M4": "N"}


def test_detecte_nor3():
    comps = [_m("M1", "A", "VDD", "P1"), _m("M2", "B", "P1", "P2"),
             _m("M3", "C", "P2", "OUT"),
             _m("M4", "A", "OUT", "GND"), _m("M5", "B", "OUT", "GND"),
             _m("M6", "C", "OUT", "GND")]
    matches = _detecter(comps)
    assert len(matches) == 1
    assert matches[0]["circuit_type"] == "Porte NOR (CMOS)"
    assert matches[0]["fonction"] == ("NOR", ["A", "B", "C"])


def test_nets_internes_nand_ne_matchent_pas():
    # Invariant anti-candidats-internes (spec § 1.4) : le net X du NAND2
    # ne doit produire aucun match — seule OUT matche.
    matches = _detecter(_nand2())
    assert [m["nodes"]["sortie"] for m in matches] == ["OUT"]


# ── Rejets (un test nommé chacun, spec § 1.4) ────────────────────────────────

def test_rejet_suiveur_sources_sur_out():
    # Paire complémentaire, grilles communes, mais S des DEUX transistors
    # sur OUT : push-pull suiveur, PAS un inverseur (critère D/S).
    matches = _detecter([_m("M1", "A", "VDD", "OUT"),
                         _m("M2", "A", "GND", "OUT")])
    assert matches == []


def test_rejet_cablage_panache():
    # Un transistor source-au-rail, l'autre source-à-OUT : incohérent.
    matches = _detecter([_m("M1", "A", "OUT", "VDD"),
                         _m("M2", "A", "GND", "OUT")])
    assert matches == []


def test_rejet_grille_sur_rail():
    matches = _detecter([_m("M1", "VDD", "OUT", "VDD"),
                         _m("M2", "VDD", "OUT", "GND")])
    assert matches == []


def test_rejet_sortie_reinjectee():
    matches = _detecter([_m("M1", "OUT", "OUT", "VDD"),
                         _m("M2", "OUT", "OUT", "GND")])
    assert matches == []


def test_rejet_grilles_dupliquees():
    # Deux NMOS en parallèle sur la MÊME grille (drive strength) : rejet v1.
    comps = [_m("M1", "A", "VDD", "P1"), _m("M2", "A", "P1", "OUT"),
             _m("M3", "A", "OUT", "GND"), _m("M4", "A", "OUT", "GND")]
    assert _detecter(comps) == []


def test_rejet_pull_up_bi_rail():
    comps = [_m("M1", "A", "OUT", "VDD"), _m("M2", "B", "OUT", "VCC"),
             _m("M3", "A", "OUT", "X"), _m("M4", "B", "X", "GND")]
    assert _detecter(comps) == []


def test_rejet_non_dual():
    # Pull-down série(A,B), pull-up une seule feuille A : multisets inégaux.
    comps = [_m("M1", "A", "OUT", "VDD"),
             _m("M2", "A", "OUT", "X"), _m("M3", "B", "X", "GND")]
    assert _detecter(comps) == []


def test_rejet_sans_rail_ou_sans_masse():
    assert _detecter([_m("M1", "A", "OUT", "N1"),
                      _m("M2", "A", "OUT", "GND")]) == []


def test_garde_zero_mosfet():
    comps = [Composant(ref="R1", type="R", pins={"1": "A", "2": "B"}, value="1k")]
    assert _detecter(comps) == []
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_logique.py -q`
Expected: FAIL — `AttributeError: ... 'detecter_portes_cmos'`.

- [ ] **Step 3: Implémentation** (ajouter à `circuit_analyzer/logique.py`)

```python
def _classifier(genre_bas, refs_bas, genre_haut):
    """@brief (circuit_type, nom_fonction) selon la forme pure du pull-down.

    Grammaire v1 : dans les formes pures, « forme complémentaire + multisets
    de grilles égaux » ÉQUIVAUT à la dualité d'arbres (spec § 1.4)."""
    complementaire = {"feuille": "feuille", "serie": "parallele",
                      "parallele": "serie"}
    if genre_haut != complementaire[genre_bas]:
        return None
    if genre_bas == "feuille":
        return ("Inverseur (CMOS)", "NOT")
    if genre_bas == "serie":
        return ("Porte NAND (CMOS)", "NAND")
    return ("Porte NOR (CMOS)", "NOR")


def detecter_portes_cmos(graphe):
    """@brief Détecteur UNIQUE (une passe) des portes CMOS statiques.

    Émet les trois circuit_type (Inverseur/NAND/NOR) — enregistré en TÊTE de
    detecteur._DETECTEURS_COMPLEXES : l'anti-vol du matcher fait la priorité.
    Tout cas hors grammaire v1 est un rejet SILENCIEUX (zéro match, les M
    retombent sur le pipeline existant). @return list[dict] au contrat spec § 1.5.
    """
    arcs = graphe_conduction(graphe)
    if not arcs:                                   # garde zéro-M (perf)
        return []
    composants = graphe.graph.get('components', {}) or {}
    rails = {n for _r, n1, n2 in arcs for n in (n1, n2) if is_power_net(n)}
    masses = {n for _r, n1, n2 in arcs for n in (n1, n2) if is_ground_net(n)}
    candidats = sorted({n for _r, n1, n2 in arcs for n in (n1, n2)}
                       - rails - masses)

    matches = []
    for out in candidats:
        bas = _reseau(arcs, out, masses, rails)
        haut = _reseau(arcs, out, rails, masses)
        if not bas or not haut:
            continue
        refs_bas = {r for r, _n1, _n2 in bas}
        refs_haut = {r for r, _n1, _n2 in haut}
        if refs_bas & refs_haut:                   # transistor partagé
            continue
        # Rails du pull-up : UN SEUL net de rail (rejet bi-rail, PAR candidat).
        rails_haut = {n for _r, n1, n2 in haut for n in (n1, n2) if n in rails}
        masses_bas = {n for _r, n1, n2 in bas for n in (n1, n2) if n in masses}
        if len(rails_haut) != 1 or len(masses_bas) != 1:
            continue
        vdd, gnd = next(iter(rails_haut)), next(iter(masses_bas))

        arbre_bas = reduire_reseau(bas, out, gnd)
        arbre_haut = reduire_reseau(haut, out, vdd)
        if arbre_bas is None or arbre_haut is None:
            continue
        pur_bas = forme_pure(arbre_bas)
        pur_haut = forme_pure(arbre_haut)
        if pur_bas is None or pur_haut is None:
            continue

        grilles_bas = sorted(composants[r].pins.get('G', '') for r in pur_bas[1])
        grilles_haut = sorted(composants[r].pins.get('G', '') for r in pur_haut[1])
        if grilles_bas != grilles_haut:            # multisets de grilles égaux
            continue
        entrees = grilles_bas
        if len(set(entrees)) != len(entrees):      # grilles dupliquées
            continue
        if any((not e) or e in rails or e in masses or is_power_net(e)
               or is_ground_net(e) for e in entrees):   # grille sur rail
            continue
        if out in entrees:                         # sortie réinjectée
            continue

        classement = _classifier(pur_bas[0], pur_bas[1], pur_haut[0])
        if classement is None:
            continue
        circuit_type, nom_fn = classement

        # Cas 1+1 : critère d'orientation D/S (spec § 1.3) — source au rail.
        if nom_fn == "NOT":
            m_haut, m_bas = pur_haut[1][0], pur_bas[1][0]
            if composants[m_haut].pins.get('S') != vdd:
                continue
            if composants[m_bas].pins.get('S') != gnd:
                continue

        polarites = {r: "P" for r in refs_haut}
        polarites.update({r: "N" for r in refs_bas})
        matches.append({
            'circuit_type': circuit_type,
            'components': sorted(refs_haut | refs_bas),
            'nodes': {'entrees': list(entrees), 'sortie': out,
                      'vdd': vdd, 'gnd': gnd},
            'io': {'ins': list(entrees), 'out': out},
            'polarites': polarites,
            'arbres': {'pull_down': arbre_bas, 'pull_up': arbre_haut},
            'fonction': (nom_fn, list(entrees)),
            'expression': f"{out} = {nom_fn}({', '.join(entrees)})",
        })
    return matches
```

- [ ] **Step 4: Vérifier le vert**

Run: `python -m pytest tests/test_logique.py -q`
Expected: `26 passed` (les 12 précédents + 14 nouveaux).

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/logique.py tests/test_logique.py
git commit -m "feat(logique): detecter_portes_cmos - classification formes pures, critere D/S, rejets nommes"
```

---

### Task 4: Enregistrement dans le matcher + anti-faux-positifs + non-régression

**Files:**
- Modify: `circuit_analyzer/detecteur.py` (ligne ~1560 `_DETECTEURS_COMPLEXES`, ligne ~1597 `NOMS_CIRCUITS`)
- Create: `tests/test_logic_integration.py`

**Interfaces:**
- Consumes: `logique.detecter_portes_cmos` (Task 3).
- Produces: `detecteur.analyser()` émet les matches de portes en priorité ; les trois noms figurent dans `NOMS_CIRCUITS`.

- [ ] **Step 1: Tests qui échouent**

```python
# tests/test_logic_integration.py
"""@file test_logic_integration.py
@brief Intégration des portes CMOS dans le pipeline complet (matcher,
anti-vol, anti-faux-positifs sur le corpus analogique existant)."""
import glob

import pytest

from circuit_analyzer import detecteur, logique
from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.xml import lire_xml


def _m(ref, g, d, s):
    return Composant(ref=ref, type="M", pins={"G": g, "D": d, "S": s}, value="")


def test_analyser_detecte_l_inverseur_en_priorite():
    graphe = construire_graphe([_m("M1", "A", "OUT", "VDD"),
                                _m("M2", "A", "OUT", "GND")])
    res = detecteur.analyser(graphe)
    types = [c["circuit_type"] for c in res]
    assert "Inverseur (CMOS)" in types
    # Anti-vol : les M de la porte ne sont pas repris par un détecteur MOSFET.
    assert "MOSFET en commutation" not in types


def test_noms_circuits_contiennent_les_portes():
    for nom in ("Inverseur (CMOS)", "Porte NAND (CMOS)", "Porte NOR (CMOS)"):
        assert nom in detecteur.NOMS_CIRCUITS


# LE filet anti-régression de la démo : le détecteur de portes ne matche
# RIEN sur tout le corpus analogique existant.
@pytest.mark.parametrize("fichier", sorted(
    glob.glob("circuits_industriels/ilot_*.xml")
    + glob.glob("circuits_industriels/tr_*.xml")
    + glob.glob("circuits_industriels/aop_*.xml")))
def test_zero_faux_positif_sur_corpus_analogique(fichier):
    graphe = construire_graphe(lire_xml(fichier))
    assert logique.detecter_portes_cmos(graphe) == []


@pytest.mark.parametrize("fichier", sorted(
    glob.glob("circuits_industriels/ilot_*.xml")
    + glob.glob("circuits_industriels/tr_*.xml")
    + glob.glob("circuits_industriels/aop_*.xml")))
def test_non_regression_types_detectes_corpus(fichier):
    # L'insertion en tête ne change la détection d'AUCUN fichier existant :
    # aucun type porte ne doit apparaître dans leurs résultats.
    res = detecteur.analyser(construire_graphe(lire_xml(fichier)))
    for c in res:
        assert "(CMOS)" not in c["circuit_type"]
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_logic_integration.py -q -x`
Expected: FAIL sur `test_analyser_detecte_l_inverseur_en_priorite` (« Inverseur (CMOS) » absent) et sur `test_noms_circuits...`.

- [ ] **Step 3: Implémentation** — dans `circuit_analyzer/detecteur.py` :

En tête de fichier (près des imports existants) :
```python
from circuit_analyzer.logique import detecter_portes_cmos
```

Dans `_DETECTEURS_COMPLEXES` (ligne ~1560), insérer EN PREMIÈRE POSITION :
```python
_DETECTEURS_COMPLEXES = [
    detecter_portes_cmos,                  # portes CMOS AVANT tout détecteur M (anti-vol)
    detecter_amplificateur_differentiel,   # 4 résistances en pont
    ...  # (liste existante inchangée)
```

Dans `NOMS_CIRCUITS` (ligne ~1597), ajouter après « Paire Darlington » :
```python
    "Inverseur (CMOS)", "Porte NAND (CMOS)", "Porte NOR (CMOS)",
```

- [ ] **Step 4: Vérifier le vert + suite complète**

Run: `python -m pytest tests/test_logic_integration.py tests/test_logique.py -q`
Expected: tous verts (le sweep corpus = ~60 fichiers × 2 tests).
Run: `python -m pytest -q` — suite COMPLÈTE verte (l'insertion en tête ne casse rien).

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/detecteur.py tests/test_logic_integration.py
git commit -m "feat(detecteur): portes CMOS en tete du matcher + filet anti-faux-positifs corpus"
```

---

### Task 5: Corpus `logic_*.xml` + tests de détection sur fichiers réels

**Files:**
- Create: `tools/gen_logic_corpus.py`
- Create: `circuits_industriels/logic_cmos_not.xml`, `logic_cmos_nand2.xml`, `logic_cmos_nand3.xml`, `logic_cmos_nor2.xml`, `logic_chaine_and.xml`, `logic_dag_2vers1.xml`, `logic_latch_sr.xml`, `logic_not_r_grille.xml`, `logic_suiveur_mos.xml`, `logic_non_dual.xml`
- Test: `tests/test_logic_integration.py` (ajouts)

**Interfaces:**
- Consumes: `circuit_analyzer.xml.generer_xml(composants) -> str` (écrit le BoardSCH) ; `lire_xml(chemin)` pour le round-trip.
- Produces: les 10 fichiers corpus, consommés par les Tasks 6-9.

- [ ] **Step 1: Écrire le générateur**

```python
# tools/gen_logic_corpus.py
"""@file gen_logic_corpus.py
@brief Génère le corpus de portes CMOS (circuits_industriels/logic_*.xml)
via circuit_analyzer.xml.generer_xml — relançable, déterministe."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuit_analyzer.composant import Composant
from circuit_analyzer.xml import generer_xml

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "circuits_industriels")


def _m(ref, g, d, s):
    return Composant(ref=ref, type="M", pins={"G": g, "D": d, "S": s}, value="")


def _r(ref, a, b, val="10k"):
    return Composant(ref=ref, type="R", pins={"1": a, "2": b}, value=val)


def _inverseur(prefixe, entree, sortie, i0=1):
    # Sources aux rails (critère D/S de la détection).
    return [_m(f"M{i0}", entree, sortie, "VDD"),
            _m(f"M{i0 + 1}", entree, sortie, "GND")]


def _nand2(entree_a, entree_b, sortie, i0=1, interne=None):
    interne = interne or f"X{i0}"
    return [_m(f"M{i0}", entree_a, sortie, "VDD"),
            _m(f"M{i0 + 1}", entree_b, sortie, "VDD"),
            _m(f"M{i0 + 2}", entree_a, sortie, interne),
            _m(f"M{i0 + 3}", entree_b, interne, "GND")]


def _nor2(entree_a, entree_b, sortie, i0=1, interne=None):
    interne = interne or f"P{i0}"
    return [_m(f"M{i0}", entree_a, "VDD", interne),
            _m(f"M{i0 + 1}", entree_b, interne, sortie),
            _m(f"M{i0 + 2}", entree_a, sortie, "GND"),
            _m(f"M{i0 + 3}", entree_b, sortie, "GND")]


CIRCUITS = {
    "logic_cmos_not.xml": _inverseur("", "A", "OUT"),
    "logic_cmos_nand2.xml": _nand2("A", "B", "OUT"),
    "logic_cmos_nand3.xml": [
        _m("M1", "A", "OUT", "VDD"), _m("M2", "B", "OUT", "VDD"),
        _m("M3", "C", "OUT", "VDD"),
        _m("M4", "A", "OUT", "X1"), _m("M5", "B", "X1", "X2"),
        _m("M6", "C", "X2", "GND")],
    "logic_cmos_nor2.xml": _nor2("A", "B", "OUT"),
    # NAND2 → NOT : AND en deux étages chaînés.
    "logic_chaine_and.xml": _nand2("A", "B", "N1") + _inverseur("", "N1", "OUT", i0=5),
    # DAG : deux NOT alimentant un NAND2.
    "logic_dag_2vers1.xml": (_inverseur("", "A", "N1")
                             + _inverseur("", "B", "N2", i0=3)
                             + _nand2("N1", "N2", "OUT", i0=5)),
    # Latch SR : deux NOR2 croisés (rendu de repli figé, spec § 2).
    "logic_latch_sr.xml": (_nor2("S", "NQ", "Q", i0=1, interne="P1")
                           + _nor2("R", "Q", "NQ", i0=5, interne="P2")),
    # Inverseur + R série de grille (satellite dessiné, spec § 2).
    "logic_not_r_grille.xml": [_r("R1", "IN", "A")] + _inverseur("", "A", "OUT"),
    # Suiveur : sources des DEUX transistors sur OUT → aucune porte.
    "logic_suiveur_mos.xml": [_m("M1", "A", "VDD", "OUT"),
                              _m("M2", "A", "GND", "OUT")],
    # Non-dual : pull-down série(A,B), pull-up feuille(A) → aucune porte.
    # (fichier réservé aux tests UNITAIRES, hors globs visuels)
    "logic_non_dual.xml": [_m("M1", "A", "OUT", "VDD"),
                           _m("M2", "A", "OUT", "X"), _m("M3", "B", "X", "GND")],
}


def main():
    for nom, comps in CIRCUITS.items():
        chemin = os.path.join(OUT_DIR, nom)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(generer_xml(comps))
        print(f"{nom}: {len(comps)} composants")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Générer et vérifier le round-trip à la main**

Run: `python tools/gen_logic_corpus.py`
Expected: 10 lignes `logic_*.xml: N composants`.
Run: `python -c "from circuit_analyzer.xml import lire_xml; c = lire_xml('circuits_industriels/logic_cmos_nand2.xml'); print(sorted((x.ref, x.type, x.pins) for x in c))"`
Expected: 4 MOSFET avec les pins G/D/S EXACTEMENT comme définis (si `generer_xml` renomme les nets ou perd des pins, corriger le générateur AVANT de continuer — c'est le risque outillage identifié par la spec ; en dernier recours les XML s'écrivent à la main sur le modèle de `tr_mosfet_commutation.xml`).

- [ ] **Step 3: Tests de détection sur les fichiers réels** (ajouter à `tests/test_logic_integration.py`)

```python
# ── Détection sur le corpus logic_* (fichiers réels, round-trip XML) ─────────

_ATTENDUS = [
    ("logic_cmos_not.xml", ["Inverseur (CMOS)"], [("NOT", ["A"])]),
    ("logic_cmos_nand2.xml", ["Porte NAND (CMOS)"], [("NAND", ["A", "B"])]),
    ("logic_cmos_nand3.xml", ["Porte NAND (CMOS)"], [("NAND", ["A", "B", "C"])]),
    ("logic_cmos_nor2.xml", ["Porte NOR (CMOS)"], [("NOR", ["A", "B"])]),
    ("logic_chaine_and.xml",
     ["Porte NAND (CMOS)", "Inverseur (CMOS)"],
     [("NAND", ["A", "B"]), ("NOT", ["N1"])]),
    ("logic_dag_2vers1.xml",
     ["Inverseur (CMOS)", "Inverseur (CMOS)", "Porte NAND (CMOS)"],
     [("NOT", ["A"]), ("NOT", ["B"]), ("NAND", ["N1", "N2"])]),
    ("logic_latch_sr.xml",
     ["Porte NOR (CMOS)", "Porte NOR (CMOS)"],
     [("NOR", ["NQ", "S"]), ("NOR", ["Q", "R"])]),
    ("logic_not_r_grille.xml", ["Inverseur (CMOS)"], [("NOT", ["A"])]),
    ("logic_suiveur_mos.xml", [], []),
    ("logic_non_dual.xml", [], []),
]


@pytest.mark.parametrize("fichier,types,fonctions", _ATTENDUS)
def test_detection_corpus_logic(fichier, types, fonctions):
    graphe = construire_graphe(lire_xml(f"circuits_industriels/{fichier}"))
    matches = logique.detecter_portes_cmos(graphe)
    assert sorted(m["circuit_type"] for m in matches) == sorted(types)
    assert sorted(m["fonction"] for m in matches) == sorted(fonctions)
```

- [ ] **Step 4: Vérifier le vert**

Run: `python -m pytest tests/test_logic_integration.py -q`
Expected: tous verts (dont les 10 nouveaux cas).

- [ ] **Step 5: Commit**

```bash
git add tools/gen_logic_corpus.py circuits_industriels/logic_*.xml tests/test_logic_integration.py
git commit -m "feat(corpus): 10 circuits logic_* generes + attendus de detection verrouilles"
```

---

### Task 6: Contrat de routage `io` dans `_io_montage` + chaîne/DAG

**Files:**
- Modify: `gui/circuit_viewer.py` (fonction `_io_montage`, ligne ~1889)
- Test: `tests/test_logic_integration.py` (ajouts)

**Interfaces:**
- Consumes: matches avec champ `io` (Task 3) ; `cv._ordonner_montages_flux(matches, ci)`, `cv._layers_montages_flux(matches, ci)` (existants).
- Produces: `_io_montage` lit `match['io']` EN PRIORITÉ ; les familles existantes (sans `io`) passent par le chemin actuel INCHANGÉ.

- [ ] **Step 1: Tests qui échouent** (ajouter à `tests/test_logic_integration.py`)

```python
# ── Routage io : chaîne et DAG de portes ─────────────────────────────────────

def _matches_fichier(fichier):
    from circuit_analyzer.detecteur import analyser
    res = analyser(construire_graphe(lire_xml(f"circuits_industriels/{fichier}")))
    return [c for c in res if "(CMOS)" in c["circuit_type"]], res


def test_io_montage_lit_le_champ_io_en_priorite():
    import gui.circuit_viewer as cv
    match = {"circuit_type": "Porte NAND (CMOS)",
             "io": {"ins": ["A", "B"], "out": "OUT"}, "nodes": {}}
    assert cv._io_montage(match, {}) == (["A", "B"], "OUT")


def test_chaine_nand_not_ordonnee():
    import gui.circuit_viewer as cv
    matches, _res = _matches_fichier("logic_chaine_and.xml")
    ordre = cv._ordonner_montages_flux(matches, {})
    assert ordre is not None
    assert [m["circuit_type"] for m in ordre] == \
        ["Porte NAND (CMOS)", "Inverseur (CMOS)"]


def test_dag_deux_not_vers_nand_en_couches():
    import gui.circuit_viewer as cv
    matches, _res = _matches_fichier("logic_dag_2vers1.xml")
    couches = cv._layers_montages_flux(matches, {})
    assert couches is not None
    assert [sorted(m["circuit_type"] for m in c) for c in couches] == \
        [["Inverseur (CMOS)", "Inverseur (CMOS)"], ["Porte NAND (CMOS)"]]
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_logic_integration.py -q -k "io or chaine or dag"`
Expected: FAIL — `_io_montage` tombe dans le chemin par défaut (`match["nodes"][-1]` → `KeyError: -1` sur un dict, ou mauvais résultat).

- [ ] **Step 3: Implémentation** — dans `gui/circuit_viewer.py`, fonction `_io_montage` (~1889), ajouter EN TÊTE du corps :

```python
def _io_montage(match, ci):
    """@brief Nets d'entrée/sortie d'un montage, selon son type.

    PRIORITÉ au contrat embarqué `match['io']` ({'ins': [...], 'out': net}) :
    les nouvelles familles (portes CMOS...) transportent leur propre routage
    — plus AUCUNE extension de whitelist par circuit_type (décision revue
    d'architecture 2026-07-08). Familles historiques sans `io` : inchangées.
    """
    io = match.get("io")
    if io is not None:
        return list(io.get("ins") or []), io.get("out")
    ct = match.get("circuit_type", "")
    # ... (corps existant INCHANGÉ à partir d'ici)
```

- [ ] **Step 4: Vérifier le vert + non-régression viewport**

Run: `python -m pytest tests/test_logic_integration.py tests/test_chaine_ilot.py -q`
Expected: tous verts (les tests chaîne existants prouvent le chemin legacy intact).

- [ ] **Step 5: Commit**

```bash
git add gui/circuit_viewer.py tests/test_logic_integration.py
git commit -m "feat(routage): champ match[io] lu en priorite par _io_montage - chaine et DAG de portes"
```

---

### Task 7: Drawer vue SIMPLIFIÉE (symbole de porte) + enregistrement `_DRAWERS` + expression en en-tête

**Files:**
- Create: `gui/logic_schematic.py`
- Modify: `gui/circuit_viewer.py` (`_DRAWERS` ligne ~4930 ; `_texte_gain`)
- Test: `tests/test_logic_drawing.py`

**Interfaces:**
- Consumes: match complet (Task 3) ; `cv._enregistrer_position(d, ref, pos)`, `cv._make_fig` (appelle `drawer_fn(d, result, comp_info)` et lit `d._mode_detaille`) ; chemin chaîne appelle `_DRAWERS[ct](d, match, ci, origin=..., titre=False, in_label=..., out_label=...)`.
- Produces: `logic_schematic.dessiner_porte(d, result, ci, origin=(3, 0), titre=True, in_label=None, out_label=None) -> dict` au contrat d'ancres `{"in", "out", "title", "nets", "absorbed_refs"}` (mêmes clés que `_draw_mosfet_switch`) ; en mode `d._mode_detaille` il délègue à `_porte_transistors` (Task 8 — pour cette task, le mode détaillé DOIT au minimum dessiner le symbole aussi, sans lever).

- [ ] **Step 1: Tests qui échouent**

```python
# tests/test_logic_drawing.py
"""@file test_logic_drawing.py
@brief Drawers des portes CMOS (gui/logic_schematic.py) : ancres, registre
de positions (contrat puces), expression en en-tête."""
import matplotlib
matplotlib.use("Agg")
import pytest
import schemdraw

import gui.circuit_viewer as cv
from gui import logic_schematic

NAND2 = {
    "circuit_type": "Porte NAND (CMOS)",
    "components": ["M1", "M2", "M3", "M4"],
    "nodes": {"entrees": ["A", "B"], "sortie": "OUT", "vdd": "VDD", "gnd": "GND"},
    "io": {"ins": ["A", "B"], "out": "OUT"},
    "polarites": {"M1": "P", "M2": "P", "M3": "N", "M4": "N"},
    "arbres": {"pull_down": ("serie", [("feuille", "M3"), ("feuille", "M4")]),
               "pull_up": ("parallele", [("feuille", "M1"), ("feuille", "M2")])},
    "fonction": ("NAND", ["A", "B"]),
    "expression": "OUT = NAND(A, B)",
}
CI = {f"M{i}": {"type": "M", "value": "", "pins": {}} for i in range(1, 5)}


def _dessiner(match, detaille=False):
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = detaille
        res = logic_schematic.dessiner_porte(d, match, CI)
    return d, res


def test_symbole_ancres_contrat():
    _d, res = _dessiner(NAND2)
    for cle in ("in", "out", "title", "nets", "absorbed_refs"):
        assert cle in res
    # nets : chaque entrée et la sortie ont un point d'ancrage.
    for net in ("A", "B", "OUT"):
        assert net in res["nets"]


def test_symbole_enregistre_toutes_les_refs_m():
    # Contrat puces (vue simplifiée) : TOUTES les refs M pointent le symbole.
    d, _res = _dessiner(NAND2)
    for ref in NAND2["components"]:
        assert ref in d._comp_positions
    positions = {d._comp_positions[r] for r in NAND2["components"]}
    assert len(positions) == 1, "toutes les refs sur le CENTRE du symbole"


def test_drawers_enregistres_pour_les_trois_types():
    for ct in ("Inverseur (CMOS)", "Porte NAND (CMOS)", "Porte NOR (CMOS)"):
        assert ct in cv._DRAWERS


def test_expression_affichee_en_en_tete():
    # Généralisation _texte_gain : un montage porteur d'expression l'affiche.
    assert cv._texte_gain(NAND2, None) == "OUT = NAND(A, B)"
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_logic_drawing.py -q`
Expected: FAIL — `ModuleNotFoundError: gui.logic_schematic`.

- [ ] **Step 3: Implémentation**

`gui/logic_schematic.py` :

```python
"""
@file logic_schematic.py
@brief Drawers des portes logiques CMOS — module DÉDIÉ (décision revue
d'architecture 2026-07-08 : circuit_viewer.py ~4000 lignes n'accueille plus
de famille de dessin ; précédent : impedance_schematic.py).

Deux vues, dispatch sur d._mode_detaille (posé par circuit_viewer._make_fig) :
  - simplifiée : symbole schemdraw.logic (Not/Nand/Nor), TOUTES les refs M
    enregistrées sur le centre du symbole (contrat puces) ;
  - détaillée : transistors réels agencés d'après match['arbres'] (Task 8).
"""
import schemdraw.elements as elm
from schemdraw import logic as slogic


_SYMBOLES = {"NOT": slogic.Not, "NAND": slogic.Nand, "NOR": slogic.Nor}


def dessiner_porte(d, result, ci, origin=(3, 0), titre=True,
                   in_label=None, out_label=None):
    """@brief Point d'entrée UNIQUE enregistré dans cv._DRAWERS pour les trois
    circuit_type — même signature et même contrat de retour que les drawers
    transistor ({"in","out","title","nets","absorbed_refs"})."""
    if getattr(d, "_mode_detaille", False):
        return _porte_transistors(d, result, ci, origin, titre,
                                  in_label, out_label)
    return _porte_symbole(d, result, ci, origin, titre, in_label, out_label)


def _porte_symbole(d, result, ci, origin, titre, in_label, out_label):
    from gui.circuit_viewer import _enregistrer_position, _titre_montage
    nom_fn, entrees = result["fonction"]
    sortie = result["nodes"]["sortie"]
    cls = _SYMBOLES[nom_fn]
    n = len(entrees)
    porte = cls().at(origin) if n <= 1 else cls(inputs=n).at(origin)
    d.add(porte)

    centre = ((porte.get_bbox().xmin + porte.get_bbox().xmax) / 2.0 + origin[0],
              (porte.get_bbox().ymin + porte.get_bbox().ymax) / 2.0 + origin[1])
    for ref in result["components"]:
        _enregistrer_position(d, ref, centre)   # contrat puces : le clic focalise la porte

    nets = {}
    for i, net in enumerate(entrees, start=1):
        broche = getattr(porte, f"in{i}") if n > 1 else porte.start
        stub = (broche[0] - 0.8, broche[1])
        d.add(elm.Line().at(broche).to(stub))
        d.add(elm.Dot().at(stub).label(in_label or net, loc="left"))
        nets[net] = stub
    out_pt = (porte.end[0] + 0.8, porte.end[1])
    d.add(elm.Line().at(porte.end).to(out_pt))
    d.add(elm.Dot().at(out_pt).label(out_label or sortie, loc="right"))
    nets[sortie] = out_pt

    title_pt = (centre[0], porte.get_bbox().ymax + origin[1] + 0.9)
    if titre:
        _titre_montage(d, result, title_pt)
    return {"in": nets[entrees[0]], "out": out_pt, "title": title_pt,
            "nets": nets, "absorbed_refs": set()}


def _porte_transistors(d, result, ci, origin, titre, in_label, out_label):
    # Task 8 — en attendant, la vue détaillée montre le symbole (jamais d'écran vide).
    return _porte_symbole(d, result, ci, origin, titre, in_label, out_label)
```

Dans `gui/circuit_viewer.py`, `_DRAWERS` (~4930), ajouter :
```python
    "Inverseur (CMOS)":                  _draw_porte_cmos,
    "Porte NAND (CMOS)":                 _draw_porte_cmos,
    "Porte NOR (CMOS)":                  _draw_porte_cmos,
```
avec, juste au-dessus du dict :
```python
def _draw_porte_cmos(d, result, ci, origin=(3, 0), titre=True,
                     in_label=None, out_label=None):
    """@brief Délégation au module dédié (import LAZY : pas de cycle)."""
    from gui import logic_schematic
    return logic_schematic.dessiner_porte(d, result, ci, origin=origin,
                                          titre=titre, in_label=in_label,
                                          out_label=out_label)
```
Dans `_texte_gain(match, graph)` : ajouter EN TÊTE `if match and match.get("expression"): return match["expression"]` (lire d'abord la fonction existante — si elle a une autre signature/garde, adapter en préservant le comportement AOP).

- [ ] **Step 4: Vérifier le vert + rendu inspecté (boucle boss)**

Run: `python -m pytest tests/test_logic_drawing.py -q` — Expected: 4 passed.
Run: `python tools/render_ilots_v2.py` puis OUVRIR les PNG de `logic_cmos_not/nand2/nor2` (vue Z) et VÉRIFIER : symbole propre, stubs étiquetés, expression en en-tête de fenêtre (via un `win_sweep` sur un fichier logic_*). Ne pas committer sans avoir regardé les images.

- [ ] **Step 5: Commit**

```bash
git add gui/logic_schematic.py gui/circuit_viewer.py tests/test_logic_drawing.py
git commit -m "feat(dessin): vue simplifiee des portes CMOS (symbole schemdraw.logic) + expression en en-tete"
```

---

### Task 8: Drawer vue DÉTAILLÉE (transistors réels depuis `match['arbres']`)

**Files:**
- Modify: `gui/logic_schematic.py` (remplacer le stub `_porte_transistors`)
- Test: `tests/test_logic_drawing.py` (ajouts)

**Interfaces:**
- Consumes: `result['arbres']` (pull_up/pull_down, formes pures garanties par la détection), `result['polarites']`, `cv._enregistrer_position`.
- Produces: `_porte_transistors` — PMOS côté VDD (empilés si l'arbre pull_up est série, côte à côte si parallèle), NMOS côté GND (dual), grilles câblées vers des stubs d'entrée communs à gauche, nœud OUT au milieu ; CHAQUE ref M enregistrée sur SON symbole ; même contrat de retour.

- [ ] **Step 1: Tests qui échouent** (ajouter à `tests/test_logic_drawing.py`)

```python
def test_detaille_chaque_m_a_sa_position():
    d, res = _dessiner(NAND2, detaille=True)
    positions = [d._comp_positions[r] for r in NAND2["components"]]
    assert len(set(positions)) == 4, "en vue détaillée chaque M a SA position"
    for cle in ("in", "out", "title", "nets", "absorbed_refs"):
        assert cle in res


def test_detaille_fets_grille_a_gauche():
    # Piège NFet/PFet schemdraw 0.22 : grille à DROITE par défaut → .reverse().
    # Garde : les x des grilles sont STRICTEMENT à gauche des x drain/source.
    import schemdraw
    with schemdraw.Drawing(show=False) as d:
        d._comp_positions = {}
        d._z_hitboxes = []
        d._mode_detaille = True
        from gui import logic_schematic
        elems_avant = len(d.elements)
        logic_schematic.dessiner_porte(d, NAND2, CI)
        fets = [e for e in d.elements[elems_avant:]
                if hasattr(e, "gate") and hasattr(e, "drain")]
    assert len(fets) == 4
    for f in fets:
        assert f.gate[0] < f.drain[0] and f.gate[0] < f.source[0]
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_logic_drawing.py -q -k detaille`
Expected: FAIL — le stub dessine le symbole (positions identiques, pas de fets).

- [ ] **Step 3: Implémentation** — remplacer `_porte_transistors` dans `gui/logic_schematic.py` :

```python
_PAS_Y = 1.7      # écart vertical entre transistors empilés (série)
_PAS_X = 2.2      # écart horizontal entre branches parallèles
_STUB_GAUCHE = 2.4  # longueur du rail de grille vers les stubs d'entrée


def _porte_transistors(d, result, ci, origin, titre, in_label, out_label):
    """@brief Vue détaillée : transistors réels agencés d'après les arbres
    (formes pures GARANTIES par la détection — le drawer ne re-dérive rien)."""
    from gui.circuit_viewer import _enregistrer_position, _titre_montage
    from circuit_analyzer.logique import forme_pure
    entrees = result["nodes"]["entrees"]
    sortie = result["nodes"]["sortie"]
    comps = {r: (ci.get(r, {}) or {}) for r in result["components"]}
    grille_de = {r: (comps[r].get("pins") or {}).get("G") for r in comps}

    genre_haut, refs_haut = forme_pure(result["arbres"]["pull_up"])
    genre_bas, refs_bas = forme_pure(result["arbres"]["pull_down"])
    ox, oy = origin

    def _colonne(refs, y0, sens, fet_cls):
        """Empile (série) des transistors sur x=ox ; renvoie [(ref, elem)]."""
        poses = []
        y = y0
        for ref in refs:
            e = d.add(fet_cls().at((ox, y)).reverse())
            _enregistrer_position(d, ref, (ox, y))
            poses.append((ref, e))
            y += sens * _PAS_Y
        # fils drain->source entre étages successifs
        for (r1, e1), (r2, e2) in zip(poses, poses[1:]):
            d.add(elm.Line().at(e1.source if sens < 0 else e1.drain)
                  .to(e2.drain if sens < 0 else e2.source))
        return poses

    def _rangee(refs, y, fet_cls):
        """Aligne (parallèle) des transistors sur y ; renvoie [(ref, elem)]."""
        poses = []
        for k, ref in enumerate(refs):
            x = ox + k * _PAS_X
            e = d.add(fet_cls().at((x, y)).reverse())
            _enregistrer_position(d, ref, (x, y))
            poses.append((ref, e))
        return poses

    # PMOS en haut (vers VDD), NMOS en bas (vers GND), OUT au milieu (oy).
    if genre_haut == "parallele" or genre_haut == "feuille":
        haut = _rangee(refs_haut, oy + _PAS_Y, elm.PFet)
        y_vdd = oy + _PAS_Y + 1.2
        for _r, e in haut:
            d.add(elm.Line().at(e.source).to((e.source[0], y_vdd)))
            d.add(elm.Line().at(e.drain).to((e.drain[0], oy)))
        xs = [e.drain[0] for _r, e in haut]
    else:                                   # série (NOR) : pile verticale
        haut = _colonne(refs_haut, oy + len(refs_haut) * _PAS_Y, -1, elm.PFet)
        y_vdd = oy + len(refs_haut) * _PAS_Y + 1.2
        d.add(elm.Line().at(haut[0][1].source).to((ox, y_vdd)))
        d.add(elm.Line().at(haut[-1][1].drain).to((ox, oy)))
        xs = [ox]
    d.add(elm.Line().at((min(xs), y_vdd)).to((max(xs), y_vdd)))
    d.add(elm.Dot().at(((min(xs) + max(xs)) / 2.0, y_vdd))
          .label(result["nodes"]["vdd"], loc="top"))

    if genre_bas == "parallele" or genre_bas == "feuille":
        bas = _rangee(refs_bas, oy - _PAS_Y, elm.NFet)
        y_gnd = oy - _PAS_Y - 1.2
        for _r, e in bas:
            d.add(elm.Line().at(e.source).to((e.source[0], y_gnd)))
            d.add(elm.Line().at(e.drain).to((e.drain[0], oy)))
        xs_b = [e.drain[0] for _r, e in bas]
    else:                                   # série (NAND) : pile verticale
        bas = _colonne(refs_bas, oy - _PAS_Y, -1, elm.NFet)
        y_gnd = oy - len(refs_bas) * _PAS_Y - 1.2
        d.add(elm.Line().at(bas[0][1].drain).to((ox, oy)))
        d.add(elm.Line().at(bas[-1][1].source).to((ox, y_gnd)))
        xs_b = [ox]
    d.add(elm.Line().at((min(xs_b), y_gnd)).to((max(xs_b), y_gnd)))
    d.add(elm.Ground().at(((min(xs_b) + max(xs_b)) / 2.0, y_gnd)))

    # Barre OUT (relie les colonnes/rangées au niveau oy) + stub à droite.
    x_max = max(xs + xs_b)
    d.add(elm.Line().at((min(xs + xs_b), oy)).to((x_max, oy)))
    out_pt = (x_max + 1.0, oy)
    d.add(elm.Line().at((x_max, oy)).to(out_pt))
    d.add(elm.Dot().at(out_pt).label(out_label or sortie, loc="right"))

    # Rails de grilles : un stub par ENTRÉE à gauche, relié aux grilles.
    nets = {sortie: out_pt}
    x_stub = min(xs + xs_b) - _STUB_GAUCHE
    tous = list(haut) + list(bas)
    for i, net in enumerate(entrees):
        y_net = oy + 0.5 - i * 0.9
        pt = (x_stub, y_net)
        d.add(elm.Dot().at(pt).label(in_label or net, loc="left"))
        for ref, e in tous:
            if grille_de.get(ref) == net:
                d.add(elm.Line().at(pt).to((e.gate[0], y_net)))
                d.add(elm.Line().at((e.gate[0], y_net)).to(e.gate))
        nets[net] = pt

    title_pt = (ox, y_vdd + 0.8)
    if titre:
        _titre_montage(d, result, title_pt)
    return {"in": nets[entrees[0]], "out": out_pt, "title": title_pt,
            "nets": nets, "absorbed_refs": set()}
```

- [ ] **Step 4: Vérifier le vert + RENDUS INSPECTÉS (obligatoire)**

Run: `python -m pytest tests/test_logic_drawing.py -q` — Expected: 6 passed.
Run: `python tools/render_ilots_v2.py` et INSPECTER les PNG détaillés de `logic_cmos_not/nand2/nand3/nor2` : pull-up/pull-down lisibles, aucune collision de labels, grilles reliées aux bons stubs. Itérer sur `_PAS_X/_PAS_Y` si nécessaire AVANT de committer (boucle visuelle boss).
Run: `python -m pytest tests/test_labels_property.py -q` (si Task 9 a déjà étendu les globs, sinon différer).

- [ ] **Step 5: Commit**

```bash
git add gui/logic_schematic.py tests/test_logic_drawing.py
git commit -m "feat(dessin): vue detaillee des portes CMOS - transistors reels depuis match[arbres]"
```

---

### Task 9: Contrats corpus + rapport/onglet + fenêtre réelle (latch, satellite)

**Files:**
- Modify: `tests/test_labels_property.py`, `tests/test_puces_resolution.py`, `tools/render_ilots_v2.py` (globs corpus)
- Modify: `tests/test_logic_integration.py` (rapport), `tests/test_island_viewport.py` (fenêtre logic)
- Modify: `gui/tab_analyze.py` (couleurs des nouveaux types si le dict l'exige — vérifier le fallback)

**Interfaces:**
- Consumes: corpus Task 5, drawers Tasks 7-8.
- Produces: les portes couvertes par les MÊMES contrats que le reste (anti-collision, puces cliquables, sweep visuel) ; rapport sans exception.

- [ ] **Step 1: Étendre les globs** — dans les trois fichiers, le motif corpus (rechercher `glob.glob("circuits_industriels/ilot_*.xml")`) devient :

```python
    glob.glob("circuits_industriels/ilot_*.xml")
    + glob.glob("circuits_industriels/tr_*.xml")
    + glob.glob("circuits_industriels/aop_*.xml")
    # Portes CMOS — logic_non_dual est EXCLU des contrats visuels (fichier de
    # rejet : îlot de MOSFET non matchés, réservé aux tests unitaires).
    + [f for f in glob.glob("circuits_industriels/logic_*.xml")
       if "non_dual" not in f]
```

- [ ] **Step 2: Tests rapport + fenêtre réelle** (ajouter à `tests/test_logic_integration.py`)

```python
# ── Rapport et onglet (la forme nouvelle du match ne casse aucun consommateur) ─

@pytest.mark.parametrize("fichier", ["logic_cmos_nand2.xml", "logic_latch_sr.xml"])
def test_rapport_se_genere_avec_des_portes(fichier):
    from circuit_analyzer.detecteur import analyser
    from circuit_analyzer.rapport import generer_rapport
    graphe = construire_graphe(lire_xml(f"circuits_industriels/{fichier}"))
    res = analyser(graphe)
    texte = generer_rapport(res, graphe)
    assert "CMOS" in texte
```

(NB : si `rapport.py` expose un autre nom que `generer_rapport`, utiliser le
point d'entrée réellement appelé par `gui/tab_analyze.py` — le trouver via
`grep "import rapport" gui/` — et adapter l'assertion : le critère est
« aucune exception + le type porte apparaît ».)

Et dans `tests/test_island_viewport.py` (réutilise `_ouvrir`) :

```python
def test_fenetre_ilot_porte_nand_toggle_et_expression(ctk_root):
    """La fenêtre îlot d'une porte : expression en en-tête (comme le gain),
    toggle simplifié/détaillé sans exception, puces M cliquables."""
    popup = _ouvrir(ctk_root, "logic_cmos_nand2.xml")
    t = popup._etat_test
    assert t["etat"]["fig"] is not None
    refs = [p["texte"] for p in t["etat"]["puces"]]
    assert any(r.startswith("M") for r in refs)
    assert all(p["dispo"] for p in t["etat"]["puces"]), "aucune puce grisée"
    t["toggle"]()
    ctk_root.update()
    assert t["mode"]["detaille"] is True
    assert all(p["dispo"] for p in t["etat"]["puces"]), "détaillé : chaque M dessiné"
    popup.destroy()


def test_fenetre_ilot_latch_sr_ouvre_sans_exception(ctk_root):
    """Rendu de repli des topologies bouclées (spec § 2) : FIGÉ — la fenêtre
    s'ouvre, une figure existe, le toggle ne lève pas."""
    popup = _ouvrir(ctk_root, "logic_latch_sr.xml")
    t = popup._etat_test
    assert t["etat"]["fig"] is not None
    t["toggle"]()
    ctk_root.update()
    assert t["etat"]["fig"] is not None
    popup.destroy()
```

- [ ] **Step 3: Vérifier l'échec puis le vert**

Run: `python -m pytest tests/test_puces_resolution.py tests/test_labels_property.py tests/test_logic_integration.py tests/test_island_viewport.py -q`
Expected: d'abord identifier les échecs réels (collisions de labels du drawer détaillé, puces non résolues, satellite R1 de `logic_not_r_grille` absorbé ou non) — CORRIGER le drawer (pas les tests) jusqu'au vert, avec ZÉRO nouvelle exclusion dans test_puces_resolution.py. Pour `gui/tab_analyze.py` : vérifier que le dict de couleurs (ligne ~35) a un fallback pour les types inconnus ; sinon ajouter une entrée « Porte » réutilisant les tokens theme existants.

- [ ] **Step 4: Boucle visuelle finale**

Run: `python tools/render_ilots_v2.py` + captures fenêtre réelle (win_sweep scratchpad) sur les 9 fichiers logic_ visuels, DEUX vues. Inspecter chaque PNG. C'est le critère d'acceptation du boss.

- [ ] **Step 5: Commit**

```bash
git add tests/ tools/render_ilots_v2.py gui/tab_analyze.py
git commit -m "test(portes): contrats corpus etendus (labels, puces, sweep) + rapport + fenetre reelle (latch fige)"
```

---

### Task 10: Performance — garde zéro-M et budget 500 portes

**Files:**
- Create: `tests/test_logique_perf.py`

**Interfaces:**
- Consumes: `logique.detecter_portes_cmos`, `detecteur.analyser`, générateurs de Task 5 (`_nand2` importable depuis `tools.gen_logic_corpus`).

- [ ] **Step 1: Tests qui échouent (ou passent immédiatement — les budgets sont le point)**

```python
# tests/test_logique_perf.py
"""@file test_logique_perf.py
@brief Gardes de performance des portes CMOS : le détecteur en TÊTE du
matcher ne doit rien coûter aux corpus analogiques (garde zéro-M) et rester
linéaire sur un circuit de 500 portes (protège l'acquis 5000 comps ≈ 3,3 s)."""
import time

from circuit_analyzer import detecteur, logique
from circuit_analyzer.composant import Composant, construire_graphe


def _m(ref, g, d, s):
    return Composant(ref=ref, type="M", pins={"G": g, "D": d, "S": s}, value="")


def _circuit_500_portes():
    comps = []
    for k in range(500):                     # 500 NAND2 chaînés = 2000 MOSFET
        a = f"N{k}" if k else "A0"
        b = f"B{k}"
        out = f"N{k + 1}"
        x = f"X{k}"
        i0 = 4 * k + 1
        comps += [_m(f"M{i0}", a, out, "VDD"), _m(f"M{i0+1}", b, out, "VDD"),
                  _m(f"M{i0+2}", a, out, x), _m(f"M{i0+3}", b, x, "GND")]
    return comps


def test_garde_zero_m_est_immediate():
    comps = [Composant(ref=f"R{i}", type="R",
                       pins={"1": f"N{i}", "2": f"N{i+1}"}, value="1k")
             for i in range(2000)]
    graphe = construire_graphe(comps)
    debut = time.perf_counter()
    assert logique.detecter_portes_cmos(graphe) == []
    assert time.perf_counter() - debut < 0.2, "zero MOSFET = retour immediat"


def test_500_portes_sous_budget():
    graphe = construire_graphe(_circuit_500_portes())
    debut = time.perf_counter()
    matches = logique.detecter_portes_cmos(graphe)
    duree = time.perf_counter() - debut
    assert len(matches) == 500
    assert duree < 10.0, f"500 portes en {duree:.1f}s (budget 10 s)"
```

- [ ] **Step 2: Exécuter et corriger si budget dépassé**

Run: `python -m pytest tests/test_logique_perf.py -q -s`
Expected: 2 passed. Si `test_500_portes_sous_budget` dépasse : le point chaud attendu est `_reseau` appelé par candidat sur TOUT le graphe de conduction — restreindre l'exploration à la composante connexe du candidat (early-exit), ou pré-indexer l'adjacence UNE fois hors de la boucle candidats. Ne PAS optimiser sans mesure.

- [ ] **Step 3: Suite complète + exe**

Run: `python -m pytest -q` — Expected: tout vert.
Run: `python tools/build_exe.py` — Expected: `Distribution prête : ... AnalyseurCircuits-1.7.0.zip` + smoke test « Rapport conforme ».

- [ ] **Step 4: Commit**

```bash
git add tests/test_logique_perf.py
git commit -m "test(perf): garde zero-M immediate + budget 500 portes CMOS"
```

---

## Ordre et dépendances

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 (strictement séquentiel : chaque task consomme les interfaces de la précédente).

## Critères d'acceptation globaux (rappel)

- Suite complète verte (~1080 tests existants + ~60 nouveaux), zéro nouvelle exclusion de puce.
- PNG des deux vues de chaque fichier logic_* inspectés (pas seulement des tests verts).
- Exe reconstruit + smoke test.
- Ledger `.superpowers/sdd/progress.md` tenu à jour task par task.
