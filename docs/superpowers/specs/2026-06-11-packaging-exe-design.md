# Design — Packaging Windows (.exe)

**Date :** 2026-06-11
**Statut :** approuvé
**Sous-projet :** 4/4 du chantier « optimisation industrielle » (après : satellites,
îlots, performance)

## Décisions actées

| Question | Décision |
|----------|----------|
| Contenu | Deux exes : `AnalyseurCircuits.exe` (GUI, fenêtré sans console) + `analyseur-cli.exe` (console) |
| Format | PyInstaller **onedir** partagé, livré en `.zip` (démarrage rapide, antivirus, portable) |
| Données modifiables | À côté de l'exe : `config/net_aliases.json` et `custom_circuits.json` dans le dossier de l'appli |
| Nom | `AnalyseurCircuits` (dossier `dist/AnalyseurCircuits/`) |
| Approche | Un seul `.spec` (deux `Analysis`, un `COLLECT` commun) + script de build avec test de fumée |

## Contexte technique

- Points d'entrée : `app.py` (GUI) et `main.py` (CLI).
- Dépendances réelles : networkx, customtkinter, matplotlib (backend TkAgg
  uniquement, via `gui/circuit_viewer.py`), schemdraw. `requirements.txt`
  n'en liste qu'une partie — à compléter.
- Deux fichiers de données sensibles au gel :
  - `config/net_aliases.json` : localisé via `Path(__file__).parent.parent.parent`
    dans `circuit_analyzer/patterns/base.py` — pointe dans `_MEIPASS`/le bundle
    une fois gelé, donc non modifiable par l'utilisateur.
  - `custom_circuits.json` : chemin relatif au répertoire courant dans
    `custom_circuits/loader.py` — casse si l'exe est lancé depuis le menu
    Démarrer (CWD quelconque).

## Composants

### 1. `circuit_analyzer/chemins.py` (nouveau)

```python
def racine_application() -> Path:
    """Racine de l'application : dossier de l'exe si gelé (PyInstaller),
    racine du projet sinon."""
```

- Gelé (`getattr(sys, 'frozen', False)`) → `Path(sys.executable).parent`.
- Sinon → racine du projet (`Path(__file__).parent.parent`).
- Consommateurs migrés :
  - `patterns/base.py` : cherche `racine_application()/config/net_aliases.json`
    (l'ancien fallback `Path('config')/...` disparaît) ; fichier absent →
    défauts intégrés (comportement existant conservé).
  - `custom_circuits/loader.py` : le chemin par défaut de
    `custom_circuits.json` devient `racine_application()/custom_circuits.json`
    (les appels avec chemin explicite, dont les tests, sont inchangés).

### 2. `packaging/analyseur.spec`

- `Analysis(app.py)` → EXE `AnalyseurCircuits` avec `console=False`.
- `Analysis(main.py)` → EXE `analyseur-cli` avec `console=True`.
- `collect_data_files('customtkinter')` (thèmes/assets requis au runtime).
- Exclusions pour alléger : backends matplotlib non-TkAgg (Qt, GTK, wx, web),
  et modules non utilisés évidents si besoin.
- Un seul `COLLECT` regroupant les deux EXE → `dist/AnalyseurCircuits/`
  (DLLs partagées, un seul dossier).
- Pas d'icône ni de ressource de version (aucun .ico dans le dépôt — YAGNI).

### 3. `tools/build_exe.py`

Étapes, dans l'ordre, avec arrêt au premier échec :

1. Vérifier que PyInstaller est importable (message clair sinon :
   `pip install pyinstaller`).
2. `pyinstaller packaging/analyseur.spec --noconfirm` (nettoie `dist/` avant).
3. Copier `config/net_aliases.json` dans `dist/AnalyseurCircuits/config/`
   (fichier modifiable par l'utilisateur, hors bundle).
4. **Test de fumée** : exécuter
   `dist/AnalyseurCircuits/analyseur-cli.exe circuits_industriels/relay_driver.xml --output <tmp>`
   et vérifier code retour 0 + « Commande de relais » dans le rapport.
5. Zipper le dossier en `dist/AnalyseurCircuits-<version>.zip`
   (version : constante `VERSION = '1.0.0'` en tête du script).

### 4. Hygiène

- `requirements.txt` complété : networkx, customtkinter, matplotlib, schemdraw,
  pytest (dev). PyInstaller documenté comme dépendance de build dans le README
  (pas dans requirements.txt — inutile au runtime).
- `.gitignore` : `build/` et `dist/` (le spec `packaging/analyseur.spec` est
  versionné, pas d'exclusion globale `*.spec`).
- README : section « Distribution Windows (.exe) » — comment builder
  (`python tools/build_exe.py`), contenu du zip, emplacement des fichiers
  modifiables.

## Comportements en mode gelé

- GUI fenêtrée : pas de console ; les `print()` éventuels sont silencieux
  (`sys.stdout` à None est toléré par `print`).
- `custom_circuits.json` créé/écrit à côté de l'exe au premier ajout de
  circuit personnalisé (dossier supposé inscriptible — distribution portable).
- `config/net_aliases.json` absent → défauts intégrés, l'appli fonctionne.

## Tests

- `tests/test_chemins.py` : `racine_application()` en mode normal (racine du
  projet) et en mode gelé simulé (monkeypatch `sys.frozen` + `sys.executable`).
- Test du chemin par défaut de `custom_circuits/loader.py` (suit
  `racine_application()`).
- Suite complète verte (les chemins explicites des tests existants ne changent pas).
- La validation de l'exe est le test de fumée du script de build — pas dans
  pytest (build trop lent, dépend de PyInstaller installé).

## Critères de succès

- `python tools/build_exe.py` produit `dist/AnalyseurCircuits-1.0.0.zip` sans
  erreur, test de fumée inclus.
- Le zip extrait sur une machine sans Python : la GUI s'ouvre, l'analyse de
  `relay_driver.xml` donne le même rapport que la version Python.
- `net_aliases.json` et `custom_circuits.json` éditables à côté de l'exe et
  pris en compte au lancement suivant.
- Suite pytest complète verte.
