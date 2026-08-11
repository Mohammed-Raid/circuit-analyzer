# Circuit Analyzer

Outil d'analyse automatique de circuits électroniques industriels.  
Charge un fichier netlist ou un schéma XML, identifie les sous-circuits connus, et génère un rapport avec score de confiance.

---

## Fonctionnalités

- **Analyse de netlists** au format texte — compatible exports KiCad et formats maison
- **Import XML BoardSCH** — lit directement les schémas du logiciel de design (noms FR/EN acceptés)
- **28 circuits reconnus** : 11 montages AOP, 9 montages transistors (BJT/MOSFET, Darlington, push-pull…), 3 portes logiques CMOS (inverseur, NAND, NOR), redressement et protections diode — les réseaux passifs résiduels sont réduits en dipôles « Impédance Z », les diodes isolées classées « Diode non classifiée »
- **Score de confiance** — chaque circuit détecté reçoit un score (élevé/moyen/faible) avec les raisons et les avertissements
- **Composants satellites** — les composants autour d'un circuit détecté (pull-up, découplage, roue libre, R série…) lui sont rattachés avec un statut sûr/possible
- **Îlots fonctionnels** — le schéma est découpé en étages (connexité hors rails) : rapport, export XML et GUI montrent la structure en blocs fonctionnels
- **Détection des ambiguïtés** — avertissements automatiques pour les topologies polyvalentes (LED/ESD, snubber/filtre, diviseur sans rails connus…)
- **Parser de valeurs** — interprète les valeurs réelles (`10k`, `100nF`, `4K7`, `0R`…) pour les rapports et l'export
- **Alias de nets configurables** — `config/net_aliases.json` définit GND, alimentation et terre de protection (PE ≠ GND)
- **Interface graphique** (CustomTkinter) pour les techniciens sans connaissance Python
- **Schémas visuels** — rendu automatique de chaque circuit détecté (schemdraw)
- **Export XML BoardSCH groupé** — schéma organisé par circuit détecté, ouvrable dans le logiciel de design
- **Patterns personnalisés** — ajouter de nouveaux circuits sans toucher au code
- **Résolution hiérarchique** — les circuits complexes ont priorité sur les circuits simples
- **Impédances équivalentes** — une contre-réaction ou une entrée composite (`Zf = R1+R2`, `R//C`…) est réduite en un dipôle unique avant détection ; les réseaux passifs qui ne participent à aucun montage actif deviennent des circuits « Impédance Z » avec leur composition détaillée

---

## Installation

### Prérequis
- Python 3.10 ou supérieur
- Dépendances : `customtkinter`, `schemdraw`, `matplotlib`, `networkx`, `Pillow`

```bash
pip install -r requirements.txt
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
| **Schéma** | Dessiner un circuit à la souris (palette, câblage) puis l'analyser directement |
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

## Distribution Windows (.exe)

L'application se distribue sans Python via PyInstaller :

```bash
pip install pyinstaller
python tools/build_exe.py
```

Le script construit `dist/AnalyseurCircuits-<version>.zip` et valide l'exe
par un test de fumée (analyse de `circuits_industriels/aop_inverseur_zf_composite.xml`).
Le zip extrait contient :

```
AnalyseurCircuits/
├── AnalyseurCircuits.exe      ← interface graphique (double-clic)
├── analyseur-cli.exe          ← ligne de commande (scripts, traitement par lots)
├── config/net_aliases.json   ← alias de nets, éditable
└── _internal/                 ← DLLs et bibliothèques (partagées par les 2 exes)
```

Le dossier est **portable** (clé USB, partage réseau) : `net_aliases.json`
et `custom_circuits.json` (créé au premier circuit personnalisé) vivent à
côté des exes et sont pris en compte au lancement suivant.

```bash
analyseur-cli.exe mon_circuit.xml --output rapport.txt
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

## Circuits reconnus (26)

### Montages AOP (11)
| Circuit | Topologie détectée |
|---------|--------------------|
| Amplificateur différentiel | 4 résistances en pont + AOP |
| Amplificateur sommateur | ≥2 impédances d'entrée + impédance feedback |
| Intégrateur | R entrée + C feedback |
| Dérivateur | C entrée + R feedback |
| Bascule de Schmitt | R feedback positif (OUT→IN+) |
| Amplificateur non-inverseur | R feedback + R vers GND |
| Amplificateur inverseur | Z entrée + Z feedback sur IN− |
| Ampli inverseur + boost HF | Zin = R//C (gain croissant en HF) |
| Ampli inverseur + action intégrale | Zf = R+C en série |
| Suiveur de tension | IN− directement relié à OUT |
| Comparateur | AOP sans feedback |

### Transistors (9)
| Circuit | Topologie détectée |
|---------|--------------------|
| Transistor en commutation | BJT + R de base + émetteur GND |
| Amplificateur émetteur commun | BJT + R collecteur + R base |
| Collecteur commun (suiveur d'émetteur) | Collecteur sur rail, charge sur l'émetteur |
| Paire Darlington | Émetteur de Q1 sur la base de Q2 |
| Étage push-pull | NPN + PNP, émetteurs communs en sortie |
| Miroir de courant BJT | 2 BJT base commune + émetteurs GND |
| MOSFET en commutation | MOSFET + R de grille + source GND |
| MOSFET haute-tension (côté haut) | MOSFET + drain sur rail + R de grille |
| Commande de relais | Relais K piloté par BJT/MOSFET |

### Diodes et redressement (5)
| Circuit | Topologie détectée |
|---------|--------------------|
| Pont redresseur (Graetz) | 4 diodes en pont |
| Redresseur simple alternance | Diode cathode + R charge vers GND |
| Détecteur de crête | Diode cathode + C vers GND |
| Diode de roue libre | Cathode sur rail, anode sur nœud commutation |
| Diode de protection ESD | Anode ou cathode à GND |

### Impédance Z (1)
Les composants passifs (R, L, C) qui ne participent à aucun montage actif ne
sont plus détectés comme des patterns nommés (filtre RC, pont diviseur,
découplage…) : ils sont **réduits en dipôles équivalents « Impédance Z »**
(`circuit_analyzer/impedance.py`), dont la composition série/parallèle liste
les composants d'origine. Dans la GUI, un clic sur une boîte Z ouvre le détail
R/L/C du réseau.

---

## Score de confiance

Chaque circuit détecté expose :

```
[1] Commande de relais
    Confiance    : élevée (92%) — commutation
    Composants   : K1, Q1
    Nœuds        : NET_CMD -> NET_COIL -> VCC_12V
    Satellites sûrs     : D1 (flyback - cathode sur VCC_12V)
    Satellites possibles: C9 ? (adjacent à NET_CMD, rôle non identifié)
    Raisons      : Relais piloté par un BJT en commutation ;
                   Diode de roue libre présente sur la bobine
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

Les circuits annexes mono-composant à diode déjà détectés (roue libre, ESD)
adjacents à un circuit multi-composants sont absorbés comme satellites de celui-ci
(les annexes passives R/L/C sont devenues des « Impédance Z » et ne sont plus
concernées).
Un découplage qui ne partage que des rails avec son hôte n'est jamais « sûr ».
Seuls les satellites **sûrs** rejoignent le bloc du circuit dans l'export XML —
les « possibles » restent dans le bloc Divers.

---

## Îlots fonctionnels (structure en étages)

En retirant les rails (GND / alimentations / PE) du graphe, les composants se
séparent en groupes connexes : les **îlots**. Chaque îlot est nommé d'après la
catégorie majoritaire de ses circuits, et les composants rail-to-rail forment
un îlot par rail d'alimentation :

```
=== STRUCTURE EN ETAGES ===

Îlot 1 - commutation (3 circuits, 12 composants)
    [1] Commande de relais : K1, Q1 (+ D1)
    [2] Commande de relais : K2, Q2 (+ D3)
    Autres : R13
Îlot 2 - alimentation VCC_12V (3 composants)
    C1, C2, C5
Îlot 3 - non identifié (2 composants)
    X1, X2
```

La même structure pilote l'**ordre des blocs dans l'export XML** (les circuits
d'un même étage sont placés côte à côte) et le **panneau repliable « Structure
en étages »** de l'onglet Analyser.

Les **avertissements** signalent les ambiguïtés, par exemple :
- `Diode de protection ESD` → *"Topologie compatible LED / TVS / Zener selon le contexte"*
- Satellites « possibles » → *"rattachement possible uniquement, validation ingénieur nécessaire"*

---

## Impédances équivalentes (réseaux passifs)

Les réseaux passifs R/L/C sont **réduits en impédances équivalentes Z**
(`circuit_analyzer/impedance.py`), pipeline « Z d'abord » :

- les chaînes **série** (via un nœud interne) sont fusionnées en un bloc, puis
  ce qui est en **parallèle** avec ces blocs, itéré jusqu'à point fixe ;
- type équivalent `R` / `C` / `L` si le réseau est homogène, `Z` (impédance
  composite) sinon ; l'expression de composition (`R1+R2`, `R3//C1`…) conserve
  les références d'origine ;
- jamais de fusion à travers un rail (GND / alimentation / PE) ;
- une impédance Z sert de brique aux grands montages : c'est elle qui permet de
  reconnaître les variantes AOP à contre-réaction composite (« boost HF »
  `Zin = R//C`, « action intégrale » `Zf = R+C`) ;
- but premier : **aucun passif non classifié** — tout R/L/C isolé devient au
  minimum une « Impédance Z » singleton visible dans le rapport et la GUI.

---

## Performance

L'analyse est calibrée pour les netlists industrielles (mesures avec
`tools/benchmark.py`, étages de relais répliqués) :

| Composants | Analyse | Avant optimisation |
|-----------:|--------:|-------------------:|
| 500 | 0.12 s | 9.56 s |
| 1000 | 0.19 s | ~45 s |
| 2000 | 0.75 s | 206.87 s |
| 5000 | 3.28 s | 1039.94 s (17 min) |

Les correctifs sont électriquement justifiés en plus d'être algorithmiques :
le nœud milieu d'un pont diviseur et la jonction d'un filtre RC/LC sont des
nœuds **signal** — les énumérer sur GND/VCC produisait des milliers de faux
matches quadratiques. Le miroir de courant n'apparie que les BJT de base
commune, l'enrichissement n'est calculé que pour les circuits retenus, et la
classification des nets est mémoïsée.

- `python tools/benchmark.py` — tableau des temps sur netlists synthétiques
  (100 à 5000 composants).
- `tests/test_performance.py` — garde-fou dans la suite : 1000 composants
  doivent s'analyser en moins de 5 s.
- Le rapport plafonne l'affichage des matches supprimés à 50 lignes
  (le total exact reste indiqué).

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

Le point d'entrée est l'assistant **PatternWizard** (4 étapes), accessible
depuis deux endroits :

- Onglet **Analyser** : après une analyse laissant des composants non
  classifiés, cliquer **Suggérer un pattern**.
- Onglet **Schéma** : après avoir dessiné un circuit, cliquer
  **Enregistrer comme pattern**.

L'assistant guide ensuite : nom du circuit, composants requis, conditions
topologiques, puis un aperçu schématique du pattern avant sauvegarde.

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

2229 tests automatisés (`pytest --collect-only -q`) couvrant le parseur, les 28 circuits reconnus, le score de confiance, les composants satellites, les îlots fonctionnels, la réduction en impédances Z, la performance, les chemins d'application, les alias de nets, le parser de valeurs, le générateur XML, l'import XML, les circuits industriels, l'interopérabilité ERetroDesign et la GUI.

> **Note :** certains tests (reporter, intégration) utilisent des résultats
> synthétiques portant d'anciens noms de patterns passifs (« Filtre RC
> passe-bas », « Pont diviseur de tension »…). Ces noms testent le formatage
> du rapport mais **ne sont plus produits par `analyser()`** : les passifs
> résiduels sortent désormais en « Impédance Z ».

---

## Structure du projet

```
circuit_analyzer/
├── composant.py           ← lecture netlist + graphe NetworkX + bibliothèque
├── detecteur.py           ← 28 circuits détectés + score de confiance
├── satellites.py          ← rattachement des composants satellites
├── ilots.py               ← îlots fonctionnels (structure en étages)
├── impedance.py           ← réduction des réseaux passifs en impédances Z
├── logique.py             ← détection des portes logiques CMOS (NOT/NAND/NOR)
├── catalogue.py           ← catalogue déclaratif de composants réels (référence → pinout)
├── saisie.py              ← modèle pur de l'onglet Saisie rapide (tableau netlist en mémoire)
├── drc.py                 ← vérification de règles de conception (DRC)
├── rapport.py             ← génération du rapport texte
├── xml.py                 ← import/export BoardSCH XML + bibliothèque de formes + fusion ERetroDesign
├── eretro.py              ← quirks des fichiers ERetroDesign réels (refs packées, puces composées, typ C#…)
├── eretro_patch.py        ← patch non-destructif : écrit les groupes d'analyse DANS le fichier XML d'origine
├── eretro_symboles.py     ← chargeur de la bibliothèque de symboles live d'ERetroDesign (LibItem/Lib/*.xml)
├── eretro_lib.py          ← échange bidirectionnel de bibliothèque de composants avec ERetroDesign
├── chemins.py             ← résolution des chemins (portable / PyInstaller)
├── value_parser.py        ← parse 10k / 100nF / 1mH / 4K7 / 0R…
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
└── component_library/     ← redirects → composant.py

config/
└── net_aliases.json       ← alias GND / alimentation / terre de protection

gui/
├── app_window.py          ← fenêtre principale CustomTkinter (3 onglets)
├── tab_analyze.py         ← onglet Analyser (KPI, cartes, exports)
├── tab_draw.py            ← onglet Schéma (toolbar de l'éditeur)
├── schematic_editor.py    ← éditeur de schéma tkinter (palette, câblage)
├── schematic_io.py        ← sérialisation éditeur ↔ netlist
├── tab_components.py      ← onglet Composants
├── pattern_wizard.py      ← wizard de création de pattern personnalisé
├── circuit_viewer.py      ← rendu schemdraw des circuits et îlots
├── impedance_schematic.py ← dessin série/parallèle d'un réseau Z
├── impedance_view.py      ← fenêtre de détail d'une impédance Z
├── network_viewer.py      ← vue du graphe de connexions
├── descriptions.py        ← fiche descriptive de chaque circuit intégré
├── theme.py               ← design tokens (couleurs, espacements, typo)
├── ui_kit.py              ← kit de widgets (cartes, boutons, icônes)
├── fonts.py               ← enregistrement de la police Inter embarquée
└── widgets.py             ← widgets divers

assets/                    ← polices Inter + icônes Lucide embarquées
packaging/                 ← spec PyInstaller + icône de l'exe
tools/                     ← build_exe.py, benchmark.py, gen_icons.py…

custom_circuits/
└── loader.py              ← circuits personnalisés (JSON)

circuits_industriels/      ← schémas BoardSCH d'exemple (62 fichiers .xml, générés par tools/gen_*.py)
exemples/                  ← netlists et schéma XML d'exemple (entrées de test)
tests/                     ← 2229 tests pytest
docs/
└── explication_logiciel.md ← explication pédagogique du fonctionnement

app.py                     ← point d'entrée interface graphique
main.py                    ← point d'entrée ligne de commande
```
