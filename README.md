# Circuit Analyzer

Outil d'analyse automatique de circuits électroniques industriels.  
Charge un fichier netlist ou un schéma XML, identifie les sous-circuits connus, et génère un rapport avec score de confiance.

---

## Fonctionnalités

- **Analyse de netlists** au format texte — compatible exports KiCad et formats maison
- **Import XML BoardSCH** — lit directement les schémas du logiciel de design (noms FR/EN acceptés)
- **27 patterns reconnus** : filtres RC/LC, AOP (9 montages), transistors BJT/MOSFET, redresseurs, protections…
- **Score de confiance** — chaque circuit détecté reçoit un score (élevé/moyen/faible) avec les raisons et les avertissements
- **Composants satellites** — les composants autour d'un circuit détecté (pull-up, découplage, roue libre, R série…) lui sont rattachés avec un statut sûr/possible
- **Détection des ambiguïtés** — avertissements automatiques pour les topologies polyvalentes (LED/ESD, snubber/filtre, diviseur sans rails connus…)
- **Parser de valeurs** — calcule la fréquence de coupure des filtres RC/LC à partir des valeurs réelles
- **Alias de nets configurables** — `config/net_aliases.json` définit GND, alimentation et terre de protection (PE ≠ GND)
- **Interface graphique** (CustomTkinter) pour les techniciens sans connaissance Python
- **Schémas visuels** — rendu automatique de chaque circuit détecté (schemdraw)
- **Export XML BoardSCH groupé** — schéma organisé par circuit détecté, ouvrable dans le logiciel de design
- **Patterns personnalisés** — ajouter de nouveaux circuits sans toucher au code
- **Résolution hiérarchique** — les circuits complexes ont priorité sur les circuits simples

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
| **Analyser** | Charger un fichier netlist (`.txt`) ou schéma (`.xml`) et lancer l'analyse |
| **Circuits** | Voir les circuits reconnus, ajouter des circuits personnalisés |
| **Composants** | Ajouter de nouveaux types de composants à la bibliothèque |

**Procédure d'analyse :**
1. Onglet **Analyser** → cliquer **Parcourir** → sélectionner votre fichier `.txt` ou `.xml`
2. Cliquer **Analyser**
3. Le rapport s'affiche avec les circuits détectés, leur score de confiance et les avertissements
4. Optionnel : cliquer **Sauvegarder le rapport** pour exporter en `.txt`
5. Optionnel : cliquer **Exporter XML (design)** pour obtenir un schéma BoardSCH organisé par circuit

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

## Circuits reconnus (27)

### Montages AOP
| Circuit | Confiance typique | Topologie détectée |
|---------|------------------|--------------------|
| Amplificateur différentiel | élevée | 4 résistances en pont + AOP |
| Amplificateur sommateur | élevée | ≥2 R d'entrée + R feedback |
| Intégrateur | élevée | R entrée + C feedback |
| Dérivateur | élevée | C entrée + R feedback |
| Bascule de Schmitt | élevée | R feedback positif (OUT→IN+) |
| Amplificateur non-inverseur | élevée | R feedback + R vers GND |
| Amplificateur inverseur | élevée | R entrée + R feedback |
| Suiveur de tension | élevée | IN− directement relié à OUT |
| Comparateur | moyenne | AOP sans feedback |

### Transistors
| Circuit | Confiance typique | Topologie détectée |
|---------|------------------|--------------------|
| Transistor en commutation | élevée | BJT + R de base + émetteur GND |
| Amplificateur émetteur commun | élevée | BJT + R collecteur + R base |
| Miroir de courant BJT | élevée | 2 BJT base commune + émetteurs GND |
| MOSFET en commutation | élevée | MOSFET + R de grille + source GND |
| MOSFET côté haut | élevée | MOSFET + drain sur rail + R de grille |
| Commande de relais | élevée | Relais K piloté par BJT/MOSFET |

### Circuits passifs et alimentation
| Circuit | Confiance typique | Topologie détectée |
|---------|------------------|--------------------|
| Pont redresseur (Graetz) | élevée | 4 diodes en pont |
| Redresseur simple alternance | moyenne | Diode cathode + R charge vers GND |
| Détecteur de crête | moyenne | Diode cathode + C vers GND |
| Diode de roue libre | moyenne | Cathode sur rail, anode sur nœud commutation |
| Diode de protection ESD | faible/moyenne | Anode ou cathode à GND |
| Filtre RC passe-bas | élevée | R série + C vers GND |
| Filtre RC passe-haut | élevée | C série + R vers GND |
| Filtre LC | élevée | L série + C vers GND |
| Pont diviseur de tension | élevée si VCC/GND, moyenne sinon | 2 R en série |
| Condensateur de découplage | élevée si entre rails | C entre alimentation et GND |
| Absorbeur RC | moyenne | R et C en parallèle |
| Protection par fusible | élevée | Fusible F seul |

---

## Score de confiance

Chaque circuit détecté expose :

```
[1] Filtre RC passe-bas
    Confiance    : élevée (90%) — filtrage
    Composants   : R1, C1
    Nœuds        : NET_IN -> NET_MID -> GND
    Satellites sûrs     : R3 (pull-up - R 47k entre NET_MID et VCC)
    Satellites possibles: C9 ? (adjacent à NET_MID, rôle non identifié)
    Raisons      : Résistance série + condensateur vers GND ;
                   Fréquence de coupure ~ 159.2 Hz (R=10k, C=100nF)
```

Le rapport se termine par une section **À vérifier (rattachement possible)** listant
les satellites incertains, chacun accompagné d'un avertissement
*« rattachement possible uniquement, validation ingénieur nécessaire »*.

### Composants satellites

Après la détection des patterns, une passe dédiée rattache les composants restants :

| Rôle | Condition | Statut typique |
|------|-----------|----------------|
| pull-up / pull-down | R >= 10k entre un nœud du circuit et un rail | sûr |
| decoupling / bulk | C entre le rail d'alim du circuit et GND | sûr |
| flyback | D cathode sur rail, anode sur nœud de commutation | sûr |
| series-r | R en série (1 Ω – 1 kΩ) sur un nœud du circuit | sûr |
| unknown-neighbor | voisin direct sans rôle identifiable | possible |

Les circuits annexes mono-composant déjà détectés (roue libre, découplage, ESD)
adjacents à un circuit multi-composants sont absorbés comme satellites de celui-ci.
Un découplage qui ne partage que des rails avec son hôte n'est jamais « sûr ».
Seuls les satellites **sûrs** rejoignent le bloc du circuit dans l'export XML —
les « possibles » restent dans le bloc Divers.

Les **avertissements** signalent les ambiguïtés :
- `Diode de protection ESD` → *"Topologie compatible LED / TVS / Zener selon le contexte"*
- `Pont diviseur` sans VCC/GND identifiés → *"Peut être un pont résistif quelconque"*
- `Absorbeur RC` → *"Topologie compatible avec un filtre ou une compensation"*
- `Filtre RC` sans valeurs → *"Fréquence de coupure non vérifiable"*

---

## Configuration des alias de nets

Le fichier `config/net_aliases.json` définit les noms reconnus pour chaque catégorie :

```json
{
  "ground": ["GND", "AGND", "DGND", "PGND", "0", "0V", "COM", "VSS"],
  "power":  ["VCC", "VDD", "VIN", "VBAT", "+5V", "+3V3", "AVCC", ...],
  "protective_earth": ["PE", "EARTH", "CHASSIS"]
}
```

> **Important** : `PE`/`EARTH`/`CHASSIS` ne sont **jamais** traités comme `GND`.  
> Ils apparaissent comme avertissement dans le rapport si un circuit en dépend.

---

## Import XML BoardSCH

Les noms de composants FR et EN sont acceptés :

| FR | EN |
|----|----|
| Résistance | Resistor |
| Condensateur / Capa | Capacitor |
| Bobine / Inductance | Inductor |
| Diode | LED / Zener / TVS |
| AOP | OpAmp |
| Transistor | BJT |
| Relais | Relay |
| Fusible | Fuse |

Les composants avec un nom inconnu sont conservés sous le type `X` (visibles dans le rapport et dans le bloc *Divers* de l'export XML) sans faire planter l'analyse.

---

## Ajouter un circuit personnalisé (via l'interface)

1. Ouvrir l'onglet **Circuits**
2. Cliquer **+ Nouveau**
3. Renseigner le nom du circuit
4. Cocher les types de composants requis
5. Cocher les conditions topologiques applicables
6. Cliquer **Sauvegarder**

---

## Limitations connues

Ces topologies ne sont **pas détectables** depuis la netlist seule :

- **Inductances isolées** — impossible de distinguer une self de stockage buck d'un filtre sans contexte
- **Condensateurs bootstrap** — aucune extrémité sur GND ou alimentation connue
- **Transistors en source de courant** — émetteur/source sur nœud flottant non reconnu
- **LEDs indicateurs** — topologiquement identiques à un redresseur simple alternance (avertissement généré)
- **Satellites « possibles »** — un voisin sans rôle identifiable est signalé (score faible, section À vérifier) mais jamais intégré au schéma exporté
- **Valeurs avec tolérance** — `"10k ±5%"` n'est pas parsé ; seule la valeur nominale est extraite si possible

> Cet outil est une aide à l'analyse — il ne remplace pas une validation par un ingénieur électronique qualifié.

---

## Tests

```bash
python -m pytest -q
```

247 tests automatisés couvrant le parseur, les 27 patterns, le score de confiance, les composants satellites, les alias de nets, le parser de valeurs, le générateur XML, l'import XML et les circuits industriels.

---

## Structure du projet

```
circuit_analyzer/
├── composant.py           ← lecture netlist + graphe NetworkX + bibliothèque
├── detecteur.py           ← 27 fonctions de détection + score de confiance
├── satellites.py          ← rattachement des composants satellites
├── rapport.py             ← génération du rapport texte
├── xml.py                 ← import/export BoardSCH XML
│
├── parser.py              ← alias → composant.py  (compat)
├── graph_builder.py       ← alias → composant.py  (compat)
├── matcher.py             ← alias → detecteur.py  (compat)
├── reporter.py            ← alias → rapport.py    (compat)
├── xml_generator.py       ← alias → xml.py        (compat)
├── xml_parser.py          ← alias → xml.py        (compat)
│
├── patterns/
│   ├── base.py            ← is_ground_net / is_power_net / is_protective_earth_net
│   ├── basic_circuits.py  ← wrappers → detecteur.py
│   ├── opamp.py           ← wrappers → detecteur.py
│   └── transistor.py      ← wrappers → detecteur.py
│
├── component_library/     ← redirects → composant.py
└── value_parser.py        ← parse 10k / 100nF / 1mH / 4K7 / 0R…

config/
└── net_aliases.json       ← alias GND / alimentation / terre de protection

gui/
├── app_window.py          ← fenêtre principale CustomTkinter
├── tab_analyze.py         ← onglet Analyser
├── tab_circuits.py        ← onglet Circuits
├── tab_components.py      ← onglet Composants
├── circuit_viewer.py      ← rendu schemdraw
└── theme.py               ← palette de couleurs

custom_circuits/
└── loader.py              ← circuits personnalisés (JSON)

circuits_industriels/      ← schémas BoardSCH générés (12 circuits)
tests/                     ← 200 tests pytest
docs/
└── explication_logiciel.md ← explication pédagogique du fonctionnement

app.py                     ← point d'entrée interface graphique
main.py                    ← point d'entrée ligne de commande
netlist_to_xml.py          ← convertit netlists → circuits_industriels/
```
