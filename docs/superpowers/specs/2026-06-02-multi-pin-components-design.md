# Multi-Pin Components Extension — Design Spec
**Date:** 2026-06-02

## Objectif

Étendre le circuit analyzer pour supporter les composants à plus de 2 broches (transistors BJT/MOSFET, AOP, transformateurs, relais, etc.) et ajouter les patterns de circuits correspondants, tout en préservant la rétrocompatibilité avec les 32 tests existants.

---

## Contexte

L'outil actuel reconnaît 8 circuits de base composés uniquement de composants 2-broches (R, C, L, D, F). Le modèle `Component` n'a que `net1` et `net2`. Cette extension ajoute le support multi-broches via l'approche B : deux structures parallèles — le graphe NetworkX existant pour les 2-broches, et un dict `{ref: Component}` attaché au graphe pour les multi-broches.

---

## Changements au modèle de données

### `Component` étendu (`circuit_analyzer/parser.py`)

```python
@dataclass
class Component:
    ref: str
    type: str
    pins: dict[str, str]   # {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'NET_EMIT'}
    value: str = ''

    @property
    def net1(self) -> str:
        return list(self.pins.values())[0] if self.pins else ''

    @property
    def net2(self) -> str:
        vals = list(self.pins.values())
        return vals[1] if len(vals) > 1 else ''
```

Les instanciations existantes `Component('R1', 'R', 'NET_A', 'NET_B', '10k')` deviennent `Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '10k')`. Les tests sont mis à jour en conséquence.

### `build_graph()` (`circuit_analyzer/graph_builder.py`)

- Composants 2-broches → arêtes dans le graphe (comportement inchangé)
- Composants multi-broches → nœuds ajoutés au graphe + stockés dans `graph.graph['components']`
- Tous les composants stockés dans `graph.graph['components']` (dict `{ref: Component}`)

```python
def build_graph(components: list[Component]) -> nx.MultiGraph:
    G = nx.MultiGraph()
    G.graph['components'] = {c.ref: c for c in components}
    for comp in components:
        if len(comp.pins) == 2:
            net1, net2 = list(comp.pins.values())
            G.add_edge(net1, net2, ref=comp.ref, type=comp.type, value=comp.value)
        else:
            for net in comp.pins.values():
                G.add_node(net)
    return G
```

### Interface `Pattern.match()` — inchangée

Les patterns existants ignorent `graph.graph['components']`. Les nouveaux patterns y accèdent :

```python
components = graph.graph.get('components', {})
```

---

## Bibliothèque de composants

### Bibliothèque de base (`circuit_analyzer/component_library/base.py`)

```python
COMPONENT_TYPES = {
    'R':  {'name': 'Résistance',       'pins': ['1', '2']},
    'C':  {'name': 'Condensateur',     'pins': ['1', '2']},
    'L':  {'name': 'Inductance',       'pins': ['1', '2']},
    'D':  {'name': 'Diode',            'pins': ['A', 'K']},
    'F':  {'name': 'Fusible',          'pins': ['1', '2']},
    'Q':  {'name': 'Transistor BJT',   'pins': ['B', 'C', 'E']},
    'M':  {'name': 'MOSFET',           'pins': ['G', 'D', 'S']},
    'U':  {'name': 'Circuit intégré',  'pins': ['IN+', 'IN-', 'OUT', 'V+', 'V-']},
    'T':  {'name': 'Transformateur',   'pins': ['P1', 'P2', 'S1', 'S2']},
    'K':  {'name': 'Relais',           'pins': ['A1', 'A2', '11', '12', '14']},
    'SW': {'name': 'Interrupteur',     'pins': ['1', '2']},
}
```

### Extension externe (`circuit_analyzer/component_library/loader.py`)

Charge la bibliothèque de base, fusionne un fichier `component_library.json` s'il existe dans le répertoire courant. Le JSON a priorité sur la bibliothèque de base.

```json
{
  "IC": {"name": "Mon CI spécifique", "pins": ["VCC", "GND", "IN", "OUT", "EN"]}
}
```

### Nouveaux fichiers

```
circuit_analyzer/component_library/
├── __init__.py
├── base.py      ← définitions Python
└── loader.py    ← charge base + fusionne JSON externe
```

---

## Nouveaux patterns

### `circuit_analyzer/patterns/transistor.py`

| Pattern | Composants | Condition topologique |
|---|---|---|
| Transistor BJT en commutation | Q + R_base | émetteur à GND, R connectée à la base |
| Amplificateur émetteur commun | Q + R_C + R_B | R au collecteur + R de polarisation à la base |
| Miroir de courant BJT | Q1 + Q2 | bases connectées ensemble, émetteurs à GND |
| MOSFET en commutation | M + R_gate | source à GND, R sur la grille |

### `circuit_analyzer/patterns/opamp.py`

| Pattern | Composants | Condition topologique |
|---|---|---|
| Amplificateur inverseur | U + R_in + R_fb | R entrée vers IN-, R feedback OUT→IN- |
| Amplificateur non-inverseur | U + R_fb + R_gnd | R feedback OUT→IN-, R de IN- à GND |
| Suiveur de tension | U | OUT connecté directement à IN- |
| Intégrateur | U + R + C | R entrée vers IN-, C feedback OUT→IN- |
| Comparateur | U | IN+ et IN- connectés à des signaux, pas de feedback OUT→IN- |

### Intégration dans `matcher.py`

```python
from circuit_analyzer.patterns.basic_circuits import ALL_PATTERNS as BASIC
from circuit_analyzer.patterns.transistor import TRANSISTOR_PATTERNS
from circuit_analyzer.patterns.opamp import OPAMP_PATTERNS

ALL_PATTERNS = BASIC + TRANSISTOR_PATTERNS + OPAMP_PATTERNS
```

---

## Parser — inchangé pour l'instant

Le format d'entrée pour les composants multi-broches sera défini quand l'utilisateur fournit ses fichiers. Le parser actuel (2-broches) reste en place. Un nouveau `parse_multipin()` sera ajouté à ce moment-là.

---

## Structure des fichiers modifiés/créés

```
circuit_analyzer/
├── parser.py                    ← Component étendu (pins dict + net1/net2 compat)
├── graph_builder.py             ← stocke graph.graph['components']
├── matcher.py                   ← importe basic + transistor + opamp
├── component_library/           ← NOUVEAU
│   ├── __init__.py
│   ├── base.py
│   └── loader.py
└── patterns/
    ├── base.py                  ← inchangé
    ├── basic_circuits.py        ← inchangé
    ├── transistor.py            ← NOUVEAU (4 patterns)
    └── opamp.py                 ← NOUVEAU (5 patterns)
tests/
├── test_parser.py               ← mis à jour (instanciations Component)
├── test_graph_builder.py        ← mis à jour
├── test_component_library.py    ← NOUVEAU
├── test_transistor_patterns.py  ← NOUVEAU
└── test_opamp_patterns.py       ← NOUVEAU
```

---

## Hors scope (pour l'instant)

- Adaptation du parser au format multi-broches de l'utilisateur
- Patterns pour transformateurs, relais
- Patterns MOSFET avancés (amplificateur, source commune)
- Visualisation graphique
