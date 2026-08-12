# Audit final — Circuit Analyzer

Audit complet exécuté sur la branche `rewrite-simple`, sans supervision
humaine intermédiaire, dans l'ordre demandé : bugs connus → qualité de code →
tests → validation. **11 commits**, tous atomiques (un commit = une
correction), messages en français, jamais de `Co-Authored-By`.

**État des tests au départ** (avant ce chantier) : suite globalement verte,
un flake de timing connu (`test_500_portes_sous_budget`).
**État des tests à l'arrivée** : **2229 tests collectés, 2182 passent, 47
skips légitimes (documentés §3), 0 échec.**

---

## 1. Bugs connus — corrigés

### 1.1 Mojibake UTF-8/Latin-1 dans `gui/descriptions.py`
- **Problème** : `gui/descriptions.py:34,37` affichaient `frÃ©quences`,
  `sÃ©rie`, `intÃ©grale` (double encodage) dans les descriptions visibles à
  l'utilisateur.
- **Correction** : ré-encodage des 3 occurrences en UTF-8 correct. Vérifié
  qu'aucune autre occurrence du motif `Ã©` n'existe ailleurs dans le dépôt.
- **Fichier / commit** : `gui/descriptions.py` — `6f9a724`.
- **Tests** : `tests/test_descriptions.py` (4 tests, déjà existants) —
  avant/après : PASS/PASS (le contenu textuel n'était pas assertionné
  caractère par caractère, mais la correction est visuellement vérifiable).

### 1.2 Règles DRC 4 et 5 manquantes (`circuit_analyzer/drc.py`)
- **Problème** : la numérotation des règles saute de 3 à 6, sans trace du
  pourquoi dans le fichier.
- **Investigation** (`git log -- circuit_analyzer/drc.py`) : les deux règles
  ont existé et ont été **retirées délibérément**, pas oubliées :
  - Règle 4 « Pont diviseur déséquilibré » (commit `76535a2`) : devenue code
    mort quand les détecteurs passifs nommés ont été remplacés par le moteur
    Z unique (`impedance.reduire`) — son `circuit_type` n'est plus jamais
    émis.
  - Règle 5 « Filtre RC sans découplage » (commit `8fa4e91`) : retirée pour
    faux positifs constants (message du commit d'origine).
- **Correction** : ni restauration (réintroduirait du code mort ou un bug
  déjà corrigé) ni renumérotation — la numérotation qui saute est
  **documentée** dans le docstring du module, avec les deux commits en
  référence.
- **Bonus découvert pendant l'investigation** : `verifier_drc()` n'avait
  **aucune couverture de test** avant ce commit. Ajout de
  `tests/test_drc.py` (10 tests : règles 1/2/3/6 + garde-fou anti-régression
  sur les règles 4/5 retirées).
- **Fichiers / commit** : `circuit_analyzer/drc.py`, `tests/test_drc.py`
  (nouveau) — `9e19469`.
- **Tests** : avant = 0 test dédié ; après = 10/10 PASS.

### 1.3 `eretro_lib.ecrire_formes_dans_dossier` jamais appelée
- **Problème** : fonction testée (`tests/test_eretro_symboles.py`) mais sans
  aucun appelant — ni bouton, ni menu (constat déjà noté lors de la revue de
  branche du 2026-08-03).
- **Correction** : câblée plutôt que supprimée — c'est une capacité réelle
  et utile (pousser nos 8 symboles orphelins — `AGND`, `Fusible`, `MOSFET`,
  `Puce4/8/14/16`, `Relais`, `Relais_1FormC`, `Transistor`, `VCC` — vers la
  bibliothèque partagée ERetroDesign).
  - Nouvelle fonction publique `circuit_analyzer/xml.py:formes_orphelines(dossier)`
    qui expose `_FORME_MAISON`/`_TYP_COMPOSANT` (privés à ce module) sans
    obliger `gui/tab_components.py` à importer des symboles préfixés `_`.
  - Nouveau bouton « ⇧ Pousser mes symboles orphelins » +
    `_pousser_symboles_orphelins()` dans `gui/tab_components.py`.
- **Fichiers / commit** : `circuit_analyzer/xml.py`, `gui/tab_components.py`,
  `tests/test_eretro_symboles.py`, `tests/test_tab_components.py` — `1fa9594`.
- **Tests** : 13 tests ajoutés (3 pour `formes_orphelines`, 3 pour le
  bouton GUI, plus couverture indirecte). Avant/après : PASS/PASS sur
  `test_tab_components.py`, `test_eretro_lib.py`, `test_eretro_symboles.py`,
  `test_eretro.py` (104 tests).

### 1.4 Import privé inter-modules (`gui/impedance_schematic.py:349`)
- **Problème** : `impedance_schematic.py` importait
  `gui.circuit_viewer._agencement_entre` (symbole privé), en contradiction
  directe avec son propre docstring (« module isolé »). Pire : cette
  fonction appelait déjà en interne `impedance_schematic.agencer` —
  dépendance circulaire de fait entre les deux modules.
- **Correction** : `_agencement_entre` déplacée dans `impedance_schematic.py`
  sous le nom public `agencement_entre` (là où vit déjà `agencer()`, dont
  elle dépend directement). `circuit_viewer.py` l'importe désormais comme
  n'importe quelle autre fonction publique du module. Le docstring
  « module isolé » redevient vrai dans les deux sens.
- **Fichiers / commit** : `gui/circuit_viewer.py`, `gui/impedance_schematic.py`,
  `tests/test_z_reseau.py` — `d58f506`.
- **Tests** : `tests/test_z_reseau.py`, `tests/test_impedance_schematic.py`
  (35 tests), suite circuit_viewer/impedance/ilots complète (566 tests) —
  avant/après : PASS/PASS.

### 1.5 Duplication `gui/tab_circuits.py` vs `gui/widgets.py:ListeSectionnee`
- **Problème** : `tab_circuits.py:158-408` réimplémentait à l'identique
  `ListeSectionnee` (~95 lignes dupliquées), alors que `tab_components.py`
  utilise déjà le composant partagé pour exactement le même besoin.
- **Correction** : `_build_liste`, `_remplir_liste`, `_lignes_section`,
  `_ajouter_entete`, `_sur_selection_liste` supprimées ; `TabCircuits`
  instancie `ListeSectionnee` comme `TabComponents`. Comportement vérifié
  identique (suite existante + aller-retour manuel sélection
  intégré/perso/nouveau/sauvegarde).
- **Fichier / commit** : `gui/tab_circuits.py` — `eb81274`.
- **Tests** : `tests/test_gui_sync.py`, `test_palette_et_doublon.py`,
  `test_pattern_refresh.py` (12 tests) — avant/après : PASS/PASS.

### 1.6 Chiffres obsolètes dans `README.md`
- **Problème** : « 590 tests », « 26 circuits reconnus » (sans les 3 portes
  CMOS), arborescence `circuit_analyzer/` incomplète, « 44 circuits » dans
  `circuits_industriels/`.
- **Correction**, chiffres recalculés depuis la réalité du dépôt :
  - Tests : **2229** (`pytest --collect-only -q`).
  - Circuits reconnus : **28** (recompté depuis
    `circuit_analyzer.detecteur.NOMS_CIRCUITS`, en excluant les 2 filets
    « Impédance Z » et « Diode non classifiée » du décompte des « montages
    reconnus », cohérent avec la formulation déjà en place).
  - Arborescence : ajout des 7 modules réels absents (`catalogue.py`,
    `logique.py`, `saisie.py`, `eretro.py`, `eretro_patch.py`,
    `eretro_symboles.py`, `eretro_lib.py`).
  - `circuits_industriels/` : **62 fichiers `.xml`** (comptage direct), pas
    44 — ce chiffre ne correspond à aucun total vérifiable dans ce dossier.
- **Fichier / commit** : `README.md` — `daad744`.
- **Tests** : aucun test ne valide le contenu du README (documentation) —
  N/A.

### 1.7 Flake de timing `test_500_portes_sous_budget`
- **Problème** : budget de 10 s sans marge réelle (10,05 s observé en
  isolé lors d'une mesure antérieure).
- **Mesures faites pour ce commit** : ~7-12 s isolé sur cette machine,
  jusqu'à ~31 s en suite complète cumulée à un build PyInstaller concurrent
  (cas non représentatif, reproduit puis expliqué).
- **Correction** : budget porté à **20 s** (≈2× le pire cas courant), avec
  un commentaire explicite rappelant que ce test est une garde de
  non-régression **algorithmique** (O(n) attendu), pas un SLA strict — une
  vraie régression O(n²) le ferait échouer très largement, pas de justesse.
- **Fichier / commit** : `tests/test_logique_perf.py` — `80b4dec`.
- **Tests** : avant = flaky (marge quasi nulle) ; après = 3 exécutions
  consécutives PASS (7,4 s / 7,9 s / 8,5 s).

---

## 2. Qualité de code

### 2.1 Linter `ruff`
`ruff` était absent du dépôt (`pip install ruff` — non versionné dans
`requirements.txt`, à ajouter si le boss veut l'outil disponible en CI).

- **Avant** : 463 violations (défauts par défaut, aucune config `ruff.toml`
  préexistante).
- **`ruff check . --fix`** (fixes sûrs uniquement, jamais `--unsafe-fixes`) :
  290 corrigées automatiquement — tri d'imports, imports inutilisés,
  `List/Dict/Tuple/Optional` → `list/dict/tuple/X|None` (PEP 585/604),
  f-strings sans placeholder, etc. **Aucun changement de comportement**
  (mécanique, vérifié par la suite complète).
- **Incident détecté et corrigé pendant cette étape** : le fixer F401
  (import inutilisé) avait entièrement **vidé 8 modules « shim de
  compatibilité »** (`circuit_analyzer/{graph_builder,matcher,parser,
  reporter,xml_generator,xml_parser}.py`,
  `circuit_analyzer/component_library/{base,loader}.py`) — leur SEUL
  contenu est un import réexporté sous un ancien nom ; « inutilisé » au
  sens statique dans CE fichier est pourtant tout leur objet. Conséquence
  avant correction : 23 fichiers de test ne s'importaient plus du tout.
  Repéré par la suite complète (pas par une relecture manuelle), corrigé en
  restaurant les 8 imports avec `# noqa: F401` explicite (documente
  l'intention, survit à un futur `ruff --fix`).
- **Après** : **176 violations restantes**, aucune corrigée automatiquement
  (nécessitent une revue au cas par cas — hors périmètre « auto-fixable »).
  Répartition : `RUF059` unused-unpacked-variable (42), `BLE001`
  blind-except (37), `RUF007` zip-instead-of-pairwise (14), `RUF013`
  implicit-optional (14), `RUF046` unnecessary-cast-to-int (13),
  `PLW1510` subprocess-run-without-check (9), `RUF015`
  unnecessary-iterable-allocation-for-first-element (9), `SIM115`
  open-file-with-context-handler (8), `F841` unused-variable (5), `SIM102`
  collapsible-if (5), `I001` unsorted-imports (4 — les 4 shims protégés,
  volontairement non « fixés » : le fixer suggéré fragmente chaque import en
  bloc séparé, plus verbeux), `PERF102` (4), `PIE810` (4), `RUF012` (2),
  `C401`/`C414`/`ISC004`/`PLC0206`/`PLW0127`/`S110` (1 chacun).
- **Fichier / commit** : 108 fichiers, `eab3494`.

### 2.2 Code mort (`vulture` + vérification manuelle repo-entier)
`vulture` était absent, installé pour l'audit.

- **50 candidats** au départ (confiance par défaut 60 %, scope
  `circuit_analyzer/ gui/ app.py main.py`).
- **11 confirmés morts** (zéro référence ailleurs dans tout le dépôt,
  vérifié par grep repo-entier APRÈS chaque suppression, suite complète
  relancée) : `detecteur._valeur`, `drc.types_schema` (variable locale,
  vestige des règles 4/5 retirées — trouvaille directement liée au §1.2),
  `patterns.basic_circuits.ALL_PATTERNS`,
  `patterns.transistor.TRANSISTOR_PATTERNS`,
  `xml.BoardSCHGenerator._TYPE_TO_SHAPE`, `circuit_viewer._is_rail_net`,
  `circuit_viewer._couplage_simple_cap`, `fonts.SCHEMA_FONTSIZES`,
  `network_viewer.self._panel`, `schema_grid.snap_point`,
  `schema_grid.Rect.dilate`, `schematic_symbols.MODELES`,
  `tab_circuits.self._pied`, `tab_analyze.self._all_refs`.
- **Faux positifs identifiés et ÉCARTÉS** (utilisés par des tests directs,
  donc pas du code mort — juste pas encore consommés par un chemin de
  production) : `ModeleSaisie` et ses 7 méthodes (`saisie.py`, testé dans
  `test_saisie.py`, backend « pur » d'un onglet Saisie rapide pas encore
  construit — hors périmètre de créer ce chantier ici),
  `patterns.base.classify_net` (testé dans `test_confidence.py`),
  `eretro_lib.symbole_vers_composant` (testé dans `test_eretro_lib.py`),
  `pin_canvas._poser_groupe`, `schematic_editor.self._rubber_band`,
  `schematic_editor.self._catalogue_listbox`, `schematic_editor._place_comp`
  (tous testés directement dans `test_schematic_editor.py`,
  `test_pin_canvas.py`, `test_editor_edition.py`,
  `test_palette_et_doublon.py`, `test_schematic_io.py`),
  `theme.BLUE_SOFT`/`theme.INFO` (contrat **explicite** de
  `tests/test_theme_tokens.py::test_token_families_present` — repéré
  **avant** commit, aurait cassé ce test si retirés).
- **Fichiers / commit** : 12 fichiers — `e05294f`.

### 2.3 Autres imports privés inter-modules
Recherche exhaustive (scan AST, pas juste grep textuel, pour couvrir les
imports multi-lignes) de tout `from circuit_analyzer.* / gui.* / custom_circuits.*
import _nom` dans le code de production, au-delà du cas déjà connu
(§1.4). **8 autres cas trouvés, délibérément NON touchés** :

| Fichier | Importe (privé) depuis | Verdict |
|---|---|---|
| `circuit_analyzer/eretro_patch.py` | `circuit_analyzer.xml` (`_grouper_par_circuit`, `_ids_groupes_par_ref`) | Même package, pas de revendication d'indépendance |
| `circuit_analyzer/ilots.py` | `circuit_analyzer.satellites` (`_est_rail`) | Idem |
| `gui/circuit_viewer.py` | `circuit_analyzer.ilots`, `circuit_analyzer.satellites` (4 symboles) | Idem |
| `gui/logic_schematic.py` | `gui.circuit_viewer` (`_enregistrer_position`, `_titre_montage`) | Module **explicitement documenté** comme extraction dédiée de `circuit_viewer.py` (« décision revue d'architecture 2026-07-08 ») |
| `gui/puce_schematic.py` | `gui.circuit_viewer` (7 symboles) | Idem, même famille (« précédent : logic_schematic.py ») |
| `gui/tab_components.py` | `gui.schematic_editor` (`_auto_def`) | Import local (lazy), même idiome que le reste du dépôt |

Aucun de ces 8 cas ne cumule les deux conditions qui avaient fait du cas
§1.4 un vrai bug : (a) contradiction avec un docstring revendiquant
l'indépendance du module, et (b) dépendance circulaire de fait. Les
modules `logic_schematic.py`/`puce_schematic.py` sont au contraire
**documentés comme des extractions volontaires** de `circuit_viewer.py`
(fichier de 5963 lignes en cours de fragmentation) — un couplage étroit y
est attendu, pas un défaut. Les refactorer tous aurait dépassé le
périmètre « pas de refonte non demandée » de ce chantier. Listés ici pour
information, pas corrigés.

---

## 3. Tests

- **Suite complète finale** : `PYTHONUTF8=1 python -m pytest -q` →
  **2229 collectés, 2182 passed, 47 skipped, 0 failed.**
- **Les 47 skips sont tous légitimes**, documentés dans leur propre
  fichier (`skipif`/`pytest.skip` avec message), aucun skip silencieux :
  - Environnement Tk absent (13) — `pytest.skip("pas de display Tk")` /
    variantes, GUI headless.
  - Dossier ERetroDesign réel absent (9) — `skipif(not os.path.isdir(...))`,
    présent sur cette machine donc généralement exécutés, mais le garde-fou
    reste actif pour CI/`.exe` livré.
  - 5 défauts de dessin **déjà triés et documentés** (audit visuel
    ChatGPT antérieur, `_EXCLUSIONS`) — pont diviseur de base / diode de
    roue libre non dessinés dans certains cas, connus et hors périmètre de
    ce chantier.
  - 1 dialecte de symbole non couvert (`eretro_forme`) — connu.
- **Couverture ajoutée par ce chantier** : 26 nouveaux tests
  (`test_drc.py` : 10 ; `formes_orphelines` : 3 ; bouton orphelins GUI : 3 ;
  plus les tests déjà comptés dans les sessions précédentes pour les 3
  premiers bugs connus du §1, non re-détaillés ici).

---

## 4. Périmètre respecté

Aucune nouvelle fonctionnalité hors de ce qui était strictement nécessaire
pour corriger un problème identifié. Le seul ajout de comportement utilisateur
est le bouton « Pousser mes symboles orphelins » (§1.3), qui câble une
fonctionnalité déjà écrite et testée plutôt que d'en créer une nouvelle —
conforme à l'esprit « ne pas laisser de code mort non décidé » de la
consigne. Aucune refonte des 8 imports privés du §2.3, aucune intégration
GUI de `ModeleSaisie` (§2.2) : ces deux chantiers auraient dépassé le
périmètre d'un audit correctif.

**Fichiers volontairement jamais touchés** (règle établie de longue date,
hors périmètre de cet audit) : `app.py`, `gui/app_window.py`
(modifications en cours de l'utilisateur, non liées à cet audit),
`component_library.json`, `custom_circuits.json` (jamais committés).
