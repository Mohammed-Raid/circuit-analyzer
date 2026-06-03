# Circuit Analyzer

Outil qui lit un fichier texte décrivant un circuit électronique industriel et identifie automatiquement les sous-circuits présents (filtres, ponts diviseurs, transistors, amplificateurs opérationnels...).

---

## Démarrage rapide — 3 étapes

### Étape 1 — Installer Python et les dépendances

Assure-toi d'avoir Python 3.10 ou plus récent. Pour vérifier :

```
python --version
```

Puis installe les dépendances :

```
pip install -r requirements.txt
```

Tu devrais voir un message comme `Successfully installed networkx...`.

---

### Étape 2 — Préparer ton fichier de circuit

Crée un fichier texte (par exemple `mon_circuit.txt`). Chaque ligne décrit un composant :

```
<référence>  <net_broche1>  <net_broche2>  [valeur optionnelle]
```

**Règles simples :**
- Les lignes qui commencent par `#` sont des commentaires (ignorées)
- Les lignes vides sont ignorées
- Le type du composant est lu depuis le **premier caractère** de la référence

**Exemple de fichier :**

```
# Mon circuit industriel

# Alimentation filtrée
C1  VCC   GND    100nF
R1  VCC   NET_A  100
C2  NET_A GND    10uF

# Pont diviseur pour mesure
R2  VCC    NET_DIV  10k
R3  NET_DIV GND    4.7k

# Protection entrée
F1  LINE_IN  NET_PROTECTED

# Transistor de commutation
Q1  NET_BASE  NET_COLL  NET_EMIT
R4  NET_CMD   NET_BASE  1k

# Pont redresseur
D1  AC_P  DC_P
D2  AC_N  DC_P
D3  DC_N  AC_P
D4  DC_N  AC_N
```

**Types de composants reconnus :**

| Préfixe de référence | Type de composant |
|---|---|
| R | Résistance |
| C | Condensateur |
| L | Inductance |
| D | Diode |
| F | Fusible |
| Q | Transistor BJT |
| M | MOSFET |
| U | Circuit intégré / AOP |
| T | Transformateur |
| K | Relais |
| SW | Interrupteur |

> **Note :** Pour les composants multi-broches (transistors, AOP), les noms de broches doivent correspondre à ceux de la bibliothèque. Par exemple, un transistor BJT `Q1` doit avoir ses connexions décrites avec les nets pour les broches B (base), C (collecteur) et E (émetteur).

---

### Étape 3 — Lancer l'analyse

```
python main.py mon_circuit.txt
```

Le rapport s'affiche dans le terminal **et** se sauvegarde dans `report.txt`.

Pour choisir un nom de fichier de sortie :

```
python main.py mon_circuit.txt --output resultats.txt
```

---

## Exemple de résultat

```
=== ANALYSE DU CIRCUIT ===
Fichier           : mon_circuit.txt
Composants totaux : 14
Groupes identifiés : 6

------------------------------------------------------------
[1] Condensateur de découplage
    Composants : C1
    Nœuds     : VCC → GND

[2] Filtre RC passe-bas
    Composants : R1, C2
    Nœuds     : VCC → NET_A → GND

[3] Pont diviseur de tension
    Composants : R2, R3
    Nœuds     : VCC → NET_DIV → GND

[4] Protection par fusible
    Composants : F1
    Nœuds     : LINE_IN → NET_PROTECTED

[5] Transistor en commutation
    Composants : Q1, R4
    Nœuds     : NET_BASE → NET_COLL → NET_EMIT

[6] Pont redresseur (Graetz)
    Composants : D1, D2, D3, D4
    Nœuds     : AC_P → DC_P → AC_N → DC_N
------------------------------------------------------------

Composants non classifiés (2) :
    U2, L1
```

Les **composants non classifiés** sont ceux que l'outil n'a pas pu regrouper dans un circuit connu — utile pour identifier ce qui reste à analyser.

---

## Circuits reconnus

### Circuits passifs

| Circuit | Composants requis | Condition |
|---|---|---|
| Filtre RC passe-bas | R + C | R en série, C vers GND |
| Filtre RC passe-haut | R + C | C en série, R vers GND |
| Filtre LC | L + C | L en série, C vers GND |
| Pont diviseur de tension | R + R | deux R en série avec nœud central |
| Condensateur de découplage | C | entre alimentation et GND |
| Pont redresseur (Graetz) | 4 × D | 4 diodes en pont complet |
| Protection par fusible | F | en série sur une ligne |
| Snubber RC | R + C | R et C en parallèle |

### Transistors

| Circuit | Composants requis | Condition |
|---|---|---|
| Transistor en commutation | Q + R_base | émetteur à GND, R connectée à la base |
| Amplificateur émetteur commun | Q + R_C + R_B | R au collecteur + R de polarisation base |
| Miroir de courant BJT | Q1 + Q2 | bases connectées, émetteurs à GND |
| MOSFET en commutation | M + R_gate | source à GND, R sur la grille |

### Amplificateurs opérationnels (AOP)

| Circuit | Composants requis | Condition |
|---|---|---|
| Amplificateur inverseur | U + R_entrée + R_feedback | R d'entrée vers IN−, R de feedback OUT→IN− |
| Amplificateur non-inverseur | U + R_feedback + R_GND | R feedback OUT→IN−, R de IN− vers GND |
| Suiveur de tension | U | sortie OUT directement connectée à IN− |
| Intégrateur | U + R + C | R d'entrée vers IN−, C de feedback OUT→IN− |
| Comparateur | U | aucun feedback entre OUT et IN− |

> Un même composant peut appartenir à plusieurs groupes simultanément.

---

## Problèmes fréquents

**"python n'est pas reconnu"**
→ Python n'est pas installé ou pas dans le PATH. Télécharge-le sur [python.org](https://python.org) et coche "Add Python to PATH" pendant l'installation.

**"No module named networkx"**
→ Lance `pip install -r requirements.txt` depuis le dossier du projet.

**"Erreur : fichier introuvable"**
→ Vérifie que tu es bien dans le bon dossier et que le nom du fichier est correct.

**L'outil ne trouve pas un circuit que tu sais présent**
→ Vérifie que les noms de nets sont cohérents (ex: `GND` partout, pas `GND` parfois et `gnd` d'autres fois). Les noms de nets sont sensibles à la casse.

**Tous mes composants sont "non classifiés"**
→ Vérifie que les références commencent par le bon préfixe (R pour résistance, C pour condensateur, etc.).

---

## Ajouter un type de composant personnalisé

Crée un fichier `component_library.json` dans le même dossier que `main.py` :

```json
{
  "IC": {
    "name": "Mon circuit intégré",
    "pins": ["VCC", "GND", "IN", "OUT", "EN"]
  },
  "REL": {
    "name": "Relais personnalisé",
    "pins": ["A1", "A2", "COM", "NO", "NC"]
  }
}
```

L'outil le chargera automatiquement au prochain lancement. Les types existants (R, C, Q, U...) restent disponibles.

---

## Ajouter un nouveau circuit à reconnaître

1. Ouvre `circuit_analyzer/patterns/basic_circuits.py`
2. Ajoute une nouvelle classe à la fin du fichier :

```python
class MonCircuit(Pattern):
    name = "Mon circuit"

    def match(self, graph):
        matches = []
        for u, v, data in graph.edges(data=True):
            if data['type'] == 'R':  # adapte selon ton circuit
                matches.append({
                    'components': [data['ref']],
                    'nodes': [u, v]
                })
        return matches
```

3. Ajoute-la à la liste `ALL_PATTERNS` en bas du fichier :

```python
ALL_PATTERNS = [
    ...
    MonCircuit(),
]
```

Pour les circuits avec transistors ou AOP, utilise les fichiers `transistor.py` ou `opamp.py` dans le même dossier.

---

## Structure du projet

```
circuit_analyzer/
├── parser.py                    ← lit le fichier texte d'entrée
├── graph_builder.py             ← construit le graphe interne
├── matcher.py                   ← applique tous les patterns
├── reporter.py                  ← génère le rapport texte
├── component_library/
│   ├── base.py                  ← types de composants de base
│   └── loader.py                ← charge base + component_library.json
└── patterns/
    ├── base.py                  ← classe de base Pattern
    ├── basic_circuits.py        ← 8 circuits passifs
    ├── transistor.py            ← 4 circuits transistors
    └── opamp.py                 ← 5 circuits AOP
main.py                          ← point d'entrée (commande python main.py)
sample_circuit.txt               ← exemple de circuit de test
component_library.json           ← (optionnel) tes composants personnalisés
```

---

## Lancer les tests

```
pytest tests/ -v
```

66 tests automatiques vérifient que tout fonctionne correctement.
