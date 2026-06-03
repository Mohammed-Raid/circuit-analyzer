# Circuit Analyzer

Outil CLI qui analyse un fichier texte décrivant un circuit électronique industriel et identifie automatiquement les sous-circuits de base présents, en groupant les composants correspondants.

## Installation

```bash
pip install -r requirements.txt
```

## Utilisation

```bash
python main.py circuit.txt
python main.py circuit.txt --output rapport.txt
python main.py circuit.txt --output rapport.txt --format txt
```

### Format du fichier d'entrée

Un composant par ligne : `<référence> <net1> <net2> [valeur optionnelle]`

```
# Les lignes commençant par # sont des commentaires
R1  NET_IN   NET_MID  10k
C1  NET_MID  GND      100nF
D1  AC_POS   DC_POS
F1  LINE_IN  NET_FUSE
```

Le **type** du composant est déduit automatiquement du premier caractère de la référence :

| Préfixe | Type |
|---|---|
| R | Résistance |
| C | Condensateur |
| L | Inductance |
| D | Diode |
| F | Fusible |

### Exemple de sortie

```
=== ANALYSE DU CIRCUIT ===
Fichier           : circuit.txt
Composants totaux : 12
Groupes identifiés : 5

------------------------------------------------------------
[1] Filtre RC passe-bas
    Composants : R1, C1
    Nœuds     : NET_IN → NET_MID → GND

[2] Pont diviseur de tension
    Composants : R2, R3
    Nœuds     : VCC → NET_DIV → GND

[3] Condensateur de découplage
    Composants : C2
    Nœuds     : VCC → GND

[4] Pont redresseur (Graetz)
    Composants : D1, D2, D3, D4
    Nœuds     : AC_POS → DC_POS → AC_NEG → DC_NEG

[5] Protection par fusible
    Composants : F1
    Nœuds     : LINE_IN → NET_FUSE
------------------------------------------------------------

Composants non classifiés (3) :
    U1, Q1, T1
```

## Circuits reconnus

| Circuit | Composants | Condition |
|---|---|---|
| Filtre RC passe-bas | R + C | R en série, C vers GND |
| Filtre RC passe-haut | R + C | C en série, R vers GND |
| Filtre LC | L + C | L en série, C vers GND |
| Pont diviseur de tension | R + R | deux R en série avec nœud central |
| Condensateur de découplage | C | entre rail d'alimentation et GND |
| Pont redresseur (Graetz) | 4 × D | configuration pont complet |
| Protection par fusible | F | en série sur une ligne |
| Snubber RC | R + C | R et C en parallèle |

Un même composant peut appartenir à plusieurs groupes simultanément.

---

## Étendre l'outil

### Ajouter un nouveau circuit

1. Ouvre `circuit_analyzer/patterns/basic_circuits.py`
2. Crée une nouvelle classe héritant de `Pattern` :

```python
class MonNouveauCircuit(Pattern):
    name = "Mon nouveau circuit"

    def match(self, graph):
        matches = []
        # graph est un nx.MultiGraph
        # Nodes = noms de nets (strings)
        # Edges = composants avec attributs: ref, type, value
        for u, v, data in graph.edges(data=True):
            if data['type'] == 'X':  # X = type de composant voulu
                matches.append({
                    'components': [data['ref']],
                    'nodes': [u, v]
                })
        return matches
```

3. Ajoute-la à `ALL_PATTERNS` en bas du fichier :

```python
ALL_PATTERNS = [
    RCLowPassFilter(),
    ...
    MonNouveauCircuit(),  # ← ajoute ici
]
```

C'est tout. Aucun autre fichier à modifier.

**Helpers disponibles** dans `circuit_analyzer/patterns/base.py` :
- `is_gnd(net)` → `True` si le net est une masse (GND, AGND, DGND, VSS, 0...)
- `is_power(net)` → `True` si le net est une alimentation (VCC, VDD, VIN, VBAT...)

---

### Changer le format d'entrée

Le parser est isolé dans `circuit_analyzer/parser.py`. Pour ajouter XML ou CSV :

1. Ajoute une fonction dans `parser.py` :

```python
def parse_xml(path: str) -> list[Component]:
    # lire le XML, retourner une liste de Component
    import xml.etree.ElementTree as ET
    tree = ET.parse(path)
    components = []
    for comp in tree.findall('.//component'):
        ref = comp.get('ref')
        net1 = comp.find("pin[@name='1']").get('net')
        net2 = comp.find("pin[@name='2']").get('net')
        value = comp.get('value', '')
        components.append(Component(ref=ref, type=ref[0].upper(), net1=net1, net2=net2, value=value))
    return components
```

2. Dans `main.py`, choisis la fonction de parsing selon l'extension du fichier :

```python
if input_path.suffix == '.xml':
    components = parse_xml(str(input_path))
else:
    components = parse_file(str(input_path))
```

---

### Changer le format de sortie

Le reporter est isolé dans `circuit_analyzer/reporter.py`. Pour ajouter JSON :

1. Ajoute un formateur dans `reporter.py` :

```python
import json

def _format_json(results, input_file, total_components, all_refs):
    classified = {ref for m in results for ref in m['components']}
    return json.dumps({
        'file': input_file,
        'total_components': total_components,
        'groups': results,
        'unclassified': [r for r in (all_refs or []) if r not in classified]
    }, ensure_ascii=False, indent=2)
```

2. Ajoute le cas dans `generate()` :

```python
def generate(results, input_file, total_components, all_refs=None, format='txt'):
    if format == 'txt':
        return _format_txt(results, input_file, total_components, all_refs)
    if format == 'json':          # ← ajoute ici
        return _format_json(results, input_file, total_components, all_refs)
    raise ValueError(f"Format non supporté : {format}")
```

3. Déclare le choix dans `main.py` :

```python
parser.add_argument('--format', choices=['txt', 'json'], default='txt')
```

---

## Structure du projet

```
circuit_analyzer/
├── parser.py            ← lecture du fichier d'entrée
├── graph_builder.py     ← construction du graphe NetworkX
├── matcher.py           ← applique tous les patterns
├── patterns/
│   ├── base.py          ← classe Pattern + helpers is_gnd/is_power
│   └── basic_circuits.py ← 8 circuits de base + ALL_PATTERNS
└── reporter.py          ← génération du rapport (txt, extensible)
main.py                  ← point d'entrée CLI
tests/                   ← tests unitaires + intégration (32 tests)
sample_circuit.txt       ← exemple de circuit de test
```

## Tests

```bash
pytest tests/ -v
```
