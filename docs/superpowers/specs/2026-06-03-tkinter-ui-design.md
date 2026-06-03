# Interface Tkinter — Design Spec
**Date :** 2026-06-03

## Objectif

Ajouter une interface graphique Tkinter à l'outil d'analyse de circuits, permettant à un technicien (sans connaissance Python) d'analyser des circuits, de gérer les types de composants et de définir de nouveaux circuits personnalisés — le tout en français, depuis une fenêtre unique.

---

## Architecture

```
app.py                    ← point d'entrée : python app.py
gui/
├── __init__.py
├── app_window.py         ← fenêtre principale + onglets ttk.Notebook
├── tab_analyze.py        ← onglet Analyser
├── tab_circuits.py       ← onglet Circuits
└── tab_components.py     ← onglet Composants
custom_circuits/
├── __init__.py
└── loader.py             ← charge/sauvegarde custom_circuits.json
```

Les onglets appellent directement les modules existants du projet :
- `circuit_analyzer.parser.parse_file`
- `circuit_analyzer.graph_builder.build_graph`
- `circuit_analyzer.matcher.match_patterns`
- `circuit_analyzer.reporter.generate`
- `circuit_analyzer.component_library.loader.load_library`

Aucune nouvelle dépendance — `tkinter` est inclus dans Python.

**Lancement :**
```bash
python app.py
```

---

## Onglet 1 — Analyser

**Éléments UI :**
- Champ texte + bouton **Parcourir** → boîte de dialogue `filedialog.askopenfilename`
- Bouton **Analyser** → pipeline complet (`parse_file` → `build_graph` → `match_patterns` → `generate`)
- Zone de texte scrollable (lecture seule) → affiche le rapport
- Bouton **Sauvegarder le rapport** → `filedialog.asksaveasfilename` → écrit le rapport `.txt`

**Comportement :**
- Si aucun fichier sélectionné et "Analyser" cliqué → message d'erreur dans la zone de texte
- Si le fichier n'existe pas → message d'erreur clair en français
- L'analyse tourne dans le thread principal (circuits industriels = quelques ms, pas besoin de thread séparé)

---

## Onglet 2 — Circuits

**Éléments UI :**
- Listbox à gauche :
  - Circuits de base (non modifiables, affichés en gris)
  - Circuits personnalisés depuis `custom_circuits.json` (modifiables)
- Formulaire à droite (activé quand un circuit personnalisé est sélectionné ou "Nouveau" cliqué) :
  - Champ **Nom** du circuit
  - Liste scrollable de cases à cocher — un par type de composant de la bibliothèque (préfixe + nom complet)
  - Cases à cocher pour **Conditions** prédéfinies :
    - "C connecté à GND"
    - "R en série"
    - "R vers alimentation"
    - "Émetteur/Source à GND"
    - "Feedback OUT→IN-"
- Boutons **+ Nouveau**, **Supprimer**, **Sauvegarder**

**Comportement :**
- La liste des composants est générée depuis `load_library()` → dynamique
- Sauvegarder → écrit dans `custom_circuits.json` via `custom_circuits/loader.py`
- Supprimer → supprime l'entrée de `custom_circuits.json`
- Les circuits de base sont listés en lecture seule (non sélectionnables pour modification)
- Les circuits personnalisés sont interprétés par un `CustomCircuitPattern` générique qui lit `custom_circuits.json`

---

## Onglet 3 — Composants

**Éléments UI :**
- Listbox à gauche :
  - Types de base (R, C, L, D, F, Q, M, U, T, K, SW) en gris, non modifiables
  - Types personnalisés depuis `component_library.json` (modifiables)
- Formulaire à droite :
  - Champ **Préfixe** (ex: `IC`, `REL`)
  - Champ **Nom** (ex: "Mon circuit intégré")
  - Liste des broches avec boutons **+ Broche** et **- Broche**
- Boutons **+ Nouveau**, **Supprimer**, **Sauvegarder**

**Comportement :**
- Sauvegarder → écrit dans `component_library.json`
- Les types ajoutés ici apparaissent immédiatement dans l'onglet Circuits (rechargement de la liste)
- Validation : préfixe obligatoire, au moins 1 broche, pas de doublon avec les types de base

---

## Fichier `custom_circuits.json`

Format :
```json
[
  {
    "name": "Filtre RLC série",
    "components": ["R", "L", "C"],
    "conditions": ["C connecté à GND", "R en série"]
  },
  {
    "name": "Mon circuit moteur",
    "components": ["Q", "R", "D"],
    "conditions": ["Émetteur/Source à GND"]
  }
]
```

---

## `CustomCircuitPattern`

Classe générique dans `custom_circuits/loader.py` qui interprète une entrée JSON comme un pattern :

```python
class CustomCircuitPattern(Pattern):
    def __init__(self, definition: dict):
        self._name = definition['name']
        self._required_types = set(definition['components'])
        self._conditions = definition.get('conditions', [])

    @property
    def name(self):
        return self._name

    def match(self, graph):
        # 1. Collecte tous les composants des types requis (depuis graph.graph['components'] pour multi-broches
        #    et depuis graph.edges() pour 2-broches)
        # 2. Pour chaque condition dans self._conditions, applique le filtre correspondant :
        #    - "C connecté à GND" → vérifie is_gnd() sur les voisins des condensateurs
        #    - "R en série" → vérifie que R partage un nœud avec un autre composant requis
        #    - "Émetteur/Source à GND" → vérifie is_gnd(comp.pins.get('E') ou 'S')
        #    - "Feedback OUT→IN-" → vérifie qu'un composant relie OUT à IN-
        # 3. Retourne les groupes qui satisfont toutes les conditions
```

Les patterns personnalisés sont ajoutés à `_ALL_PATTERNS` dans `matcher.py` via `load_custom_patterns()`.

---

## Fichiers créés/modifiés

| Fichier | Rôle |
|---|---|
| `app.py` | Point d'entrée GUI |
| `gui/__init__.py` | Package |
| `gui/app_window.py` | Fenêtre principale + onglets |
| `gui/tab_analyze.py` | Onglet Analyser |
| `gui/tab_circuits.py` | Onglet Circuits |
| `gui/tab_components.py` | Onglet Composants |
| `custom_circuits/__init__.py` | Package |
| `custom_circuits/loader.py` | Charge/sauvegarde custom_circuits.json + CustomCircuitPattern |
| `circuit_analyzer/matcher.py` | Modifié : intègre les patterns personnalisés |

---

## Hors scope

- Circuits complexes via l'interface (miroir de courant, pont de Graetz) — restent en Python
- Thème visuel avancé / style personnalisé
- Internationalisation (autre que français)
- Tests automatiques pour l'UI (Tkinter est difficile à tester automatiquement)
