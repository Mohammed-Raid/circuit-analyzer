# Circuit Analyzer — Design Spec
**Date:** 2026-06-02

## Objectif

Outil CLI qui prend un fichier texte décrivant un circuit industriel (composants + connexions) et identifie automatiquement les sous-circuits de base présents, en groupant les composants correspondants.

---

## Architecture

Pipeline en 4 étapes isolées et extensibles :

```
circuit.txt
    ↓
[Parser]        — lit le fichier texte, extrait composants et connexions
    ↓
[Graph Builder] — construit un graphe NetworkX (nœuds = nets, arêtes = composants)
    ↓
[Matcher]       — cherche les motifs de circuits de base dans le graphe
    ↓
[Reporter]      — génère le rapport texte
    ↓
report.txt
```

**Structure des fichiers :**
```
circuit_analyzer/
├── main.py                  ← point d'entrée CLI
├── parser.py                ← lecture du fichier texte
├── graph_builder.py         ← construction du graphe NetworkX
├── matcher.py               ← algorithme de correspondance de motifs
├── patterns/
│   ├── base.py              ← classe abstraite Pattern
│   └── basic_circuits.py   ← 8 circuits de base définis
└── reporter.py              ← génération du rapport .txt
```

---

## Interface CLI

```bash
python main.py circuit.txt
python main.py circuit.txt --output results/report.txt
python main.py circuit.txt --format txt        # défaut
python main.py circuit.txt --format json       # extensible plus tard
python main.py circuit.txt --format xml        # extensible plus tard
```

---

## Format d'entrée (texte)

Un composant par ligne : `<ref> <net_pin1> <net_pin2> [valeur]`

```
# Commentaires avec #
R1  NET_A  NET_B  10k
C1  NET_B  GND    100nF
R2  VCC    NET_C  10k
R3  NET_C  GND    4.7k
D1  NET_D  NET_E
D2  NET_E  NET_F
D3  NET_F  NET_G
D4  NET_G  NET_D
```

- `ref` : référence du composant (ex: R1, C2, L3, D4)
- `net_pin1`, `net_pin2` : noms des nœuds/nets connectés aux deux broches
- `valeur` : optionnelle (10k, 100nF, etc.)
- Le type du composant est déduit du préfixe de la référence (R=résistance, C=condensateur, L=inductance, D=diode, F=fusible)

**Extensibilité entrée :** le parser est isolé dans `parser.py`. Ajouter XML ou CSV = ajouter une fonction `parse_xml()` ou `parse_csv()` dans ce fichier, sans toucher au reste.

---

## Représentation interne (graphe)

- **Nœuds** = nets électriques (GND, VCC, NET_A, NET_B...)
- **Arêtes** = composants, avec attributs `ref`, `type`, `value`
- Bibliothèque : `networkx` (Python)

---

## Circuits de base reconnus

| # | Circuit | Composants | Condition topologique |
|---|---|---|---|
| 1 | Filtre RC passe-bas | R + C | R en série, C entre nœud commun et GND |
| 2 | Filtre RC passe-haut | R + C | C en série, R entre nœud commun et GND |
| 3 | Filtre LC | L + C | L en série, C entre nœud commun et GND |
| 4 | Pont diviseur de tension | R + R | deux R en série entre deux potentiels |
| 5 | Condensateur de découplage | C | entre rail d'alimentation et GND |
| 6 | Pont redresseur (Graetz) | 4 × D | configuration pont de Graetz |
| 7 | Protection par fusible | F | en série sur une ligne |
| 8 | Snubber RC | R + C | R + C en parallèle sur un composant |

- Un composant peut appartenir à plusieurs groupes simultanément.
- **Extensibilité circuits :** ajouter un circuit = créer une nouvelle classe héritant de `Pattern` dans `patterns/basic_circuits.py`, sans modifier `matcher.py`.

---

## Format de sortie (rapport texte)

Fichier `report.txt` généré dans le même dossier que le fichier d'entrée (ou dans `--output` si spécifié).

```
=== ANALYSE DU CIRCUIT ===
Fichier : circuit.txt
Composants totaux : 42
Groupes identifiés : 5

------------------------------------------------------------
[1] Filtre RC passe-bas
    Composants : R1, C1
    Nœuds     : NET_A → NET_B → GND

[2] Pont diviseur de tension
    Composants : R2, R3
    Nœuds     : VCC → NET_C → GND

[3] Condensateur de découplage
    Composants : C3
    Nœuds     : VCC → GND

[4] Pont redresseur (Graetz)
    Composants : D1, D2, D3, D4
    Nœuds     : NET_D → NET_E → NET_F → NET_G

[5] Protection par fusible
    Composants : F1
    Nœuds     : LINE_IN → NET_H
------------------------------------------------------------

Composants non classifiés (12) :
    Q1, Q2, U1, U2, ...
```

**Extensibilité sortie :** `reporter.py` expose une interface `generate(results, format)`. Ajouter JSON ou XML = ajouter un formateur dans ce fichier.

---

## Dépendances Python

- `networkx` — graphe et algorithmes de correspondance
- `argparse` — interface CLI (standard library)

---

## Ce qui est hors scope (pour l'instant)

- Interface web
- Sortie JSON/XML
- Format d'entrée XML ou CSV
- Circuits canoniques avancés (H-bridge, PID, SMPS...)
- Visualisation graphique
