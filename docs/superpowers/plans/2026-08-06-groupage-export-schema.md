# Groupage automatique à l'export du schéma dessiné — Plan d'implémentation

> **Pour l'exécutant :** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec de référence :** `docs/superpowers/specs/2026-08-06-groupage-export-schema-design.md` (commit `962b0fd`).

**Goal :** faire écrire un vrai `<GrpL>` (groupes par circuit reconnu) quand on
exporte le schéma dessiné à la main vers ERetroDesign, au lieu du `<GrpL />`
vide actuel.

**Architecture :** une fonction module-level `_xml_groupe_par_circuit(composants)`
dans `gui/tab_draw.py` fait tourner le détecteur de montages existant
(`circuit_analyzer.composant.construire_graphe` +
`circuit_analyzer.detecteur.analyser`) puis appelle
`circuit_analyzer.xml.generer_xml(composants, results=resultats)` — même
mécanisme déjà utilisé par l'onglet Analyser
(`tab_analyze.py::_texte_export_analyse`), aucune nouvelle logique de
groupage. Les deux call sites de `generer_xml(composants)` dans `tab_draw.py`
basculent sur cette fonction.

**Tech Stack :** Python 3.11, pytest. Aucune nouvelle dépendance.

## Global Constraints

- Commits en **français**, **jamais** de footer `Co-Authored-By: Claude` ni
  `Generated with Claude Code`.
- **Jamais `git add -A`** : fichiers ajoutés un par un, avec pathspec explicite
  sur `git commit`.
- **Ne jamais committer** `custom_circuits.json` ni `component_library.json`.
- `PYTHONUTF8=1` sur toutes les commandes pytest.
- Branche `rewrite-simple` (implémenté dans le worktree
  `groupage-export-schema`) ; rien n'est poussé sans accord explicite.
- Comportement observable **inchangé** quand aucun montage n'est reconnu :
  `<GrpL />` vide, comme aujourd'hui (non-régression explicite).

---

### Task 1 : `_xml_groupe_par_circuit` + câblage des deux call sites

**Files:**
- Create: `tests/test_tab_draw.py`
- Modify: `gui/tab_draw.py:13-14` (nouvel import), `gui/tab_draw.py:131-173`
  (`_export_circuit_xml`), `gui/tab_draw.py:232-263` (`_export_netlist_file`)

**Interfaces produites :**
- `gui.tab_draw._xml_groupe_par_circuit(composants: list) -> str` — XML
  BoardSCH, groupé par circuit reconnu si le détecteur en trouve, `<GrpL />`
  vide sinon (même contrat que `generer_xml`, un paramètre en moins).

- [ ] **Step 1 : écrire les tests qui échouent** — créer `tests/test_tab_draw.py`

```python
"""@file test_tab_draw.py
@brief Groupage automatique a l'export du schema dessine (spec 2026-08-06).

Teste _xml_groupe_par_circuit directement (fonction module-level, aucun Tk) —
meme principe que test_eretro_patch.py pour tab_analyze._texte_export_analyse.
"""
import xml.etree.ElementTree as ET

from circuit_analyzer.composant import Composant
from gui.tab_draw import _xml_groupe_par_circuit


def _montage_reconnu():
    """@brief Diviseur R1/R2 + C1 + AOP U1 — meme montage que
    tests/test_eretro_groupes_reels.py::_carte, deja prouve detecte par
    test_grpl_est_creee_meme_absente_de_la_source."""
    return [
        Composant("R1", "R", {"1": "IN", "2": "N1"}, "10k"),
        Composant("R2", "R", {"1": "N1", "2": "OUT"}, "100k"),
        Composant("C1", "C", {"1": "N1", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "GND", "IN-": "N1", "OUT": "OUT"}, ""),
    ]


def test_montage_reconnu_produit_un_groupe():
    xml = _xml_groupe_par_circuit(_montage_reconnu())
    racine = ET.fromstring(xml)
    assert racine.findall("./GrpL/GRPS"), "aucun groupe ecrit pour un montage reconnu"


def test_aucun_montage_reconnu_grpl_vide():
    """Non-regression : une resistance isolee ne doit RIEN grouper."""
    xml = _xml_groupe_par_circuit([Composant("R1", "R", {"1": "IN", "2": "OUT"}, "1k")])
    racine = ET.fromstring(xml)
    assert racine.findall("./GrpL/GRPS") == []
    assert racine.find("GrpL") is not None


def test_fonction_est_bien_exportee_du_module():
    import gui.tab_draw as td
    assert callable(td._xml_groupe_par_circuit)
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_tab_draw.py -q`
Attendu : `ImportError: cannot import name '_xml_groupe_par_circuit' from 'gui.tab_draw'`

- [ ] **Step 3 : implémenter** — dans `gui/tab_draw.py`

La ligne 13 existante importe déjà `construire_graphe` :
`from circuit_analyzer.composant import construire_graphe, lire_netlist`
— rien à changer là. Ajouter une ligne juste après (nouvelle ligne 14) :

```python
from circuit_analyzer.detecteur import analyser as detecter_montages
```

(la ligne `from circuit_analyzer.xml import generer_xml, lire_xml`, qui suit,
ne change pas non plus.)

Ajouter, juste après les imports (avant `class TabDraw:`) :

```python
def _xml_groupe_par_circuit(composants) -> str:
    """@brief XML BoardSCH avec groupage automatique par circuit reconnu.

    Fait tourner le meme detecteur que l'onglet Analyser sur les composants
    du schema dessine a la main, pour que l'export profite du meme groupage
    <GrpL> que l'onglet Analyse (tab_analyze.py::_texte_export_analyse) —
    jusqu'ici toujours vide faute de `results` passe a generer_xml.
    """
    graphe    = construire_graphe(composants)
    resultats = detecter_montages(graphe)
    return generer_xml(composants, results=resultats)
```

Dans `_export_circuit_xml` (ligne ~163-164), remplacer :

```python
            with open(path, "w", encoding="utf-8") as f:
                f.write(generer_xml(composants))
```

par :

```python
            with open(path, "w", encoding="utf-8") as f:
                f.write(_xml_groupe_par_circuit(composants))
```

Dans `_export_netlist_file` (ligne ~261), remplacer :

```python
        tmp.write(generer_xml(composants))
```

par :

```python
        tmp.write(_xml_groupe_par_circuit(composants))
```

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_tab_draw.py -q` → PASS (3/3)

- [ ] **Step 5 : non-régression ciblée**

Run : `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py tests/test_eretro_groupes_reels.py -q`
Attendu : tout vert, inchangé (aucun de ces fichiers ne touche `tab_draw.py`).

- [ ] **Step 6 : commit**

```bash
git add gui/tab_draw.py tests/test_tab_draw.py
git commit -m "feat(schema): groupe automatiquement les circuits reconnus a l'export ERetroDesign"
```

---

### Task 2 : suite complète + revue

- [ ] **Step 1 : suite complète**

```bash
PYTHONUTF8=1 python -m pytest -q
```
Attendu : vert, sans nouvelle régression par rapport à la baseline connue de
la branche (voir la réserve de non-isolation de `test_puces_resolution.py`,
déjà documentée et hors périmètre — ne pas la re-diagnostiquer ici).

- [ ] **Step 2 : à la main dans l'app (si Tk disponible dans l'environnement)**

Onglet Schéma → dessiner un montage reconnu (ex. un diviseur de tension R+R
avec un condensateur et un AOP câblé comme le montage de test) → « Exporter
(ERetroDesign) » → ouvrir le fichier produit → vérifier `<GrpL>` contient au
moins un `<GRPS>` (grep du fichier, ou ouverture dans ERetroDesign si
disponible).

- [ ] **Step 3 : revue** — `superpowers:requesting-code-review` sur la
  branche, puis `superpowers:finishing-a-development-branch`. Rien n'est
  poussé sans accord explicite du boss.
