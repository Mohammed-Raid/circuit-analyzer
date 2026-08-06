# Groupage automatique à l'export du schéma dessiné — conception

**Date :** 2026-08-06
**Branche :** `rewrite-simple` (implémenté dans le worktree `groupage-export-schema`)

## Le problème

Le bouton « Exporter (ERetroDesign) » de l'onglet Schéma
(`gui/tab_draw.py:131-173`, `_export_circuit_xml`) appelle
`generer_xml(composants)` **sans `results=`**. Or `generer_xml` (et le
`_grouper_par_circuit` qu'elle appelle en interne, `circuit_analyzer/xml.py`)
sait déjà grouper les composants par circuit reconnu — c'est exactement ce que
fait l'onglet Analyser à l'export (`gui/tab_analyze.py:70-86`,
`_texte_export_analyse`, qui passe `results=resultats`). Sans `results`,
`_grouper_par_circuit` reçoit `resultats=None`, ne trouve aucun bloc, et
`_xml_groupes()` écrit toujours `<GrpL />` vide — même quand le schéma dessiné
à la main contient plusieurs montages reconnaissables (ex. deux étages
ampli-op distincts).

Un schéma dessiné dans l'éditeur et exporté vers ERetroDesign n'est donc
**jamais groupé**, alors que la même XML reçoit des groupes quand elle sort du
pipeline d'analyse. Le boss veut que l'export du schéma « maison » profite du
même groupage automatique par circuit reconnu.

## Décision de périmètre

**Aucune nouvelle logique de groupage.** L'infrastructure existe déjà et est
déjà testée (`_grouper_par_circuit`, le repli « Divers » pour les composants
non reconnus, `_xml_groupes`). Le seul trou est que `TabDraw` ne fait jamais
tourner le détecteur avant d'exporter. On branche l'existant, on n'invente
rien.

- Groupage **automatique**, par circuit reconnu par `detecteur.analyser` —
  pas de sélection manuelle ni de bouton « Grouper » dans l'éditeur (écarté
  en discussion : ce n'est pas ce qui a été demandé).
- Les composants non reconnus suivent le comportement existant de
  `_grouper_par_circuit` (bloc « Divers », rattachement par net partagé si
  possible) — comportement hérité tel quel, non modifié.
- Seul `_export_circuit_xml` change. `_launch_analyze` /
  `_export_netlist_file` (le chemin « Analyser ce circuit ») ne changent
  **pas** : ils exportent déjà une netlist temporaire que `tab_analyze.py`
  analyse lui-même de bout en bout (avec ses propres `resultats`) ; dupliquer
  la détection ici serait un travail perdu.
- Si le détecteur ne reconnaît rien du tout (`resultats == []`), le
  comportement observable doit rester **identique à aujourd'hui** :
  `<GrpL />` vide, aucune régression sur un schéma qui n'a jamais eu de
  groupe. `_grouper_par_circuit(composants, [])` retourne déjà `[]` dans ce
  cas (le bloc « Divers » n'apparaît que si des `resultats` existent) — pas de
  branche spéciale à écrire.

## Architecture

### `gui/tab_draw.py` — nouvelle fonction module-level `_xml_groupe_par_circuit`

Même précédent que `tab_analyze.py::_texte_export_analyse` (ligne 70) : une
fonction **module-level**, pas une méthode, pour être testable sans Tk.

```python
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser as detecter_montages


def _xml_groupe_par_circuit(composants) -> str:
    """@brief XML BoardSCH avec groupage automatique par circuit reconnu.

    Fait tourner le même détecteur que l'onglet Analyser sur les composants
    du schéma dessiné à la main, pour que l'export profite du même groupage
    <GrpL> — jusqu'ici toujours vide faute de `results` passé à generer_xml.
    """
    graphe    = construire_graphe(composants)
    resultats = detecter_montages(graphe)
    return generer_xml(composants, results=resultats)
```

`_export_circuit_xml` (ligne 163-164) et `_export_netlist_file`
(ligne 261 — utilisée par « Analyser ce circuit », voir plus bas) appellent
`_xml_groupe_par_circuit(composants)` au lieu de `generer_xml(composants)`.

Les deux imports rejoignent ceux déjà en tête de fichier
(`from circuit_analyzer.xml import generer_xml, lire_xml`, ligne 14) —
mêmes fonctions que celles importées à la demande dans
`tab_analyze.py::_coeur_analyse` (sous les alias historiques
`build_graph`/`match_patterns`), donc pas de nouveau coût d'import :
`networkx` est déjà tiré dès qu'on ouvre l'onglet Schéma via
`circuit_analyzer.composant`.

Le commentaire existant lignes 154-162 (qui explique que l'export du Schéma
n'est PAS fidèle, contrairement à l'onglet Analyse) reste valable et n'a pas
besoin d'être réécrit — le groupage ne change rien à cette distinction : les
positions/formes restent régénérées, seul `<GrpL>` devient réel.

**`_export_netlist_file` aussi, précision de périmètre :** cette fonction
écrit un fichier XML temporaire qui sert de **relais** vers l'onglet Analyser
(`_launch_analyze` → `on_analyze(path)` → `tab_analyze.py` relit ce fichier et
lance SA PROPRE analyse). Le fichier temporaire lui-même n'est jamais vu par
l'utilisateur ni exporté tel quel — le grouper ou non n'a aucun effet
observable, puisque `tab_analyze.py` régénère son propre export avec ses
propres `resultats` s'il exporte à son tour. On la fait quand même passer par
`_xml_groupe_par_circuit` pour une seule raison : **cohérence** (une seule
fonction fabrique le XML d'un schéma dessiné à la main dans ce fichier), pas
parce que ça change un comportement observable.

### Rien d'autre ne change

`circuit_analyzer/xml.py` (`generer_xml`, `_grouper_par_circuit`,
`_xml_groupes`) : **non modifié**, déjà correct et déjà testé
(`tests/test_xml_generator.py`, `tests/test_eretro_groupes_reels.py`).

## Tests

`tests/test_tab_draw.py` n'existe pas encore — créé par ce chantier, sur le
même principe que `test_eretro_patch.py` qui teste
`tab_analyze._texte_export_analyse` directement (import du module, aucun Tk).

- **Cas nominal :** liste de `Composant` synthétiques formant un montage
  reconnu — réutiliser exactement le montage de
  `tests/test_eretro_groupes_reels.py::_carte` (R1/R2 diviseur + C1 + U1 AOP,
  déjà prouvé détecté par `test_grpl_est_creee_meme_absente_de_la_source`) —
  passée à `_xml_groupe_par_circuit` → le XML produit contient au moins un
  `<GRPS>` (`ET.fromstring(...).findall("./GrpL/GRPS")` non vide).
- **Non-régression :** une seule résistance isolée (aucun montage reconnu)
  passée à `_xml_groupe_par_circuit` → `<GrpL />` vide, comme le comportement
  actuel de `generer_xml(composants)` sans `results`.
- **Import :** vérifier que `gui.tab_draw` expose bien `_xml_groupe_par_circuit`
  (garantit que le câblage dans `_export_circuit_xml`/`_export_netlist_file`
  n'a pas été oublié — ces deux méthodes elles-mêmes restent non testées
  directement, comme le reste des méthodes Tk de ce fichier aujourd'hui).

## Réserve connue

Le boss a explicitement écarté le groupage manuel (sélection + bouton
« Grouper ») dans cette discussion — uniquement le groupage automatique par
circuit reconnu. Si un besoin de groupage manuel apparaît plus tard, c'est un
chantier séparé (sélection multiple existe déjà dans l'éditeur — bande de
sélection, Ctrl+clic — mais aucun état de groupe persistant n'existe sur
`CompInst`).
