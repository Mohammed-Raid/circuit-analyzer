# Circuit Analyzer

Outil d'analyse automatique de circuits électroniques industriels.  
Charge un fichier netlist, identifie les sous-circuits connus (filtres, AOP, transistors, alimentations…), et génère un rapport clair.

---

## Fonctionnalités

- **Analyse de netlists** au format texte — compatible exports KiCad et formats maison
- **23 patterns reconnus** : filtres RC/LC, AOP (9 montages), transistors BJT/MOSFET, redresseurs, protections…
- **Interface graphique** (CustomTkinter) pour les techniciens sans connaissance Python
- **Schémas visuels** — rendu automatique de chaque circuit détecté (schemdraw)
- **Export XML BoardSCH** — exporte le schéma organisé par circuit détecté, ouvrable dans le logiciel de design
- **Patterns personnalisés** — ajouter de nouveaux circuits sans toucher au code
- **Bibliothèque de composants extensible** — ajouter de nouveaux types de composants
- **Résolution hiérarchique** — les circuits complexes ont priorité sur les circuits simples (pas de faux positifs)
- **Taux de classification moyen : 85%** sur 12 circuits industriels réels

---

## Installation

### Prérequis
- Python 3.10 ou supérieur
- Dépendances : `customtkinter`, `schemdraw`, `networkx`

```bash
pip install customtkinter schemdraw networkx
```

### Étapes

```bash
git clone https://github.com/Mohammed-Raid/circuit-analyzer.git
cd circuit-analyzer
```

Pour vérifier que tout fonctionne :
```bash
python -m pytest -q
```

---

## Utilisation

### Interface graphique (recommandée)

```bash
python app.py
```

La fenêtre s'ouvre avec 3 onglets :

| Onglet | Rôle |
|--------|------|
| **Analyser** | Charger un fichier netlist et lancer l'analyse |
| **Circuits** | Voir les circuits reconnus, ajouter des circuits personnalisés |
| **Composants** | Ajouter de nouveaux types de composants à la bibliothèque |

**Procédure d'analyse :**
1. Onglet **Analyser** → cliquer **Parcourir** → sélectionner votre fichier `.txt` ou `.xml`
2. Cliquer **Analyser**
3. Le rapport s'affiche avec les circuits détectés et leur schéma visuel
4. Optionnel : cliquer **Sauvegarder le rapport** pour exporter en `.txt`
5. Optionnel : cliquer **Exporter XML (design)** pour obtenir un schéma BoardSCH organisé, ouvrable dans le logiciel de design

### Ligne de commande

```bash
python main.py mon_circuit.txt --output rapport.txt
```

---

## Format du fichier netlist

Chaque ligne décrit un composant :

```
REFERENCE  NOEUD1  NOEUD2  [VALEUR]
```

**Exemples :**
```
R1   NET_IN    NET_MID   10k
C1   NET_MID   GND       100nF
D1   AC_POS    DC_POS
Q1   NET_BASE  NET_COLL  GND
U1   NET_INP   NET_INM   NET_OUT   VCC   GND
```

**Règles :**
- Les lignes commençant par `#` sont des commentaires
- Les noms de nœuds sont insensibles à la casse (`vcc` = `VCC`)
- Les nets KiCad avec `/` sont supportés (`/PGND`, `/VCC_AOP`)
- Les références dupliquées déclenchent une erreur explicite
- Une ligne incomplète déclenche une erreur avec le numéro de ligne

**Composants supportés :**

| Préfixe | Type | Broches |
|---------|------|---------|
| R | Résistance | 1, 2 |
| C | Condensateur | 1, 2 |
| L | Inductance | 1, 2 |
| D | Diode | A (anode), K (cathode) |
| F | Fusible | 1, 2 |
| Q | Transistor BJT | B (base), C (collecteur), E (émetteur) |
| M | MOSFET | G (grille), D (drain), S (source) |
| U | AOP | IN+, IN-, OUT, V+, V- |
| T | Transformateur | P1, P2, S1, S2 |
| K | Relais | A1, A2, C, NC |
| SW | Interrupteur | 1, 2 |

---

## Circuits reconnus

### Montages AOP
| Circuit | Topologie détectée |
|---------|--------------------|
| Amplificateur différentiel | 4 résistances en pont + AOP |
| Amplificateur sommateur | ≥2 R d'entrée + R feedback |
| Intégrateur | R entrée + C feedback |
| Dérivateur | C entrée + R feedback |
| Trigger de Schmitt | R feedback positif (OUT→IN+) |
| Amplificateur non-inverseur | R feedback + R vers GND |
| Amplificateur inverseur | R entrée + R feedback |
| Suiveur de tension | IN− directement relié à OUT |
| Comparateur | AOP sans feedback |

### Transistors
| Circuit | Topologie détectée |
|---------|--------------------|
| Transistor en commutation | BJT + R de base + émetteur GND |
| Amplificateur émetteur commun | BJT + R collecteur + R base |
| Miroir de courant BJT | 2 BJT base commune + émetteurs GND |
| MOSFET en commutation | MOSFET + R de grille + source GND |
| MOSFET côté haut | MOSFET + drain sur rail + R de grille |
| Driver relais | Relais K piloté par BJT/MOSFET |

### Circuits passifs et alimentation
| Circuit | Topologie détectée |
|---------|--------------------|
| Pont redresseur (Graetz) | 4 diodes en pont |
| Redresseur simple alternance | Diode cathode + R charge vers GND |
| Détecteur de crête | Diode cathode + C vers GND |
| Diode de roue libre | Cathode sur rail, anode sur nœud commutation |
| Diode de protection ESD | Anode ou cathode à GND |
| Filtre RC passe-bas | R série + C vers GND |
| Filtre RC passe-haut | C série + R vers GND |
| Filtre LC | L série + C vers GND |
| Pont diviseur de tension | 2 R en série |
| Condensateur de découplage | C entre alimentation et GND |
| Absorbeur RC | R et C en parallèle |
| Protection par fusible | Fusible F seul |

---

## Ajouter un circuit personnalisé (via l'interface)

1. Ouvrir l'onglet **Circuits**
2. Cliquer **+ Nouveau**
3. Renseigner le nom du circuit
4. Cocher les types de composants requis
5. Cocher les conditions topologiques applicables
6. Cliquer **Sauvegarder**

Le circuit est immédiatement actif pour les analyses suivantes.

---

## Ajouter un type de composant (via l'interface)

1. Ouvrir l'onglet **Composants**
2. Cliquer **+ Nouveau**
3. Renseigner le préfixe (ex : `IC`), le nom, et les broches
4. Cliquer **Sauvegarder**

---

## Résultats sur circuits industriels

Tests effectués sur 12 netlists industrielles réelles (alimentations, commande moteur, conditionnement signal, protection) :

| Métrique | Valeur |
|----------|--------|
| Taux de classification moyen | **85%** |
| Meilleur résultat | 96% (régulateur LDO) |
| Résultat typique | 83–90% |

---

## Limitations connues

Ces topologies ne sont **pas détectables** depuis la netlist seule :

- **Inductances isolées** — impossible de distinguer une self de stockage buck d'un filtre de mode commun sans contexte
- **Condensateurs bootstrap** — aucune extrémité sur GND ou alimentation connue
- **Transistors en source de courant** — émetteur/source sur nœud flottant non reconnu
- **LEDs indicateurs** — topologiquement identiques à un redresseur simple alternance
- **Condensateurs Y vers PE** — la terre de protection (PE) n'est pas assimilée à GND pour des raisons de sécurité

---

## Tests

```bash
python -m pytest -q
```

162 tests automatisés couvrant le parseur, les patterns, le générateur XML, l'intégration bout en bout et les circuits industriels.

---

## Structure du projet

```
circuit_analyzer/
├── parser.py              ← lecture et validation de la netlist
├── graph_builder.py       ← construction du graphe NetworkX
├── matcher.py             ← résolution hiérarchique des patterns
├── reporter.py            ← génération du rapport texte
├── xml_parser.py          ← lecture de schémas BoardSCH .xml
├── xml_generator.py       ← génération de schémas BoardSCH .xml (groupés)
├── component_library/     ← bibliothèque de composants (base + JSON)
└── patterns/
    ├── base.py            ← Pattern ABC, is_gnd(), is_power()
    ├── basic_circuits.py  ← filtres, redresseurs, passifs
    ├── opamp.py           ← montages AOP
    └── transistor.py      ← BJT, MOSFET, relais

gui/
├── app_window.py          ← fenêtre principale CustomTkinter
├── tab_analyze.py         ← onglet Analyser (analyse + export XML)
├── tab_circuits.py        ← onglet Circuits
├── tab_components.py      ← onglet Composants
├── circuit_viewer.py      ← rendu schemdraw des circuits détectés
└── theme.py               ← palette de couleurs centralisée

custom_circuits/
└── loader.py              ← circuits personnalisés (JSON)

simulations/               ← 12 netlists industrielles de test
circuits_industriels/      ← schémas BoardSCH générés (groupés)
tests/                     ← suite de tests pytest (162 tests)
netlist_to_xml.py          ← convertit simulations/ → circuits_industriels/
app.py                     ← point d'entrée interface graphique
main.py                    ← point d'entrée ligne de commande
```
