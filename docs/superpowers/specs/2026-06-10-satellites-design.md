# Design — Rattachement des composants satellites

**Date :** 2026-06-10
**Statut :** approuvé
**Sous-projet :** 1/4 du chantier « optimisation industrielle » (suivront : îlots fonctionnels, performance, packaging .exe)

---

## Problème

Les circuits réels entourent les patterns de base de composants annexes : résistance de
pull-up, condensateur de découplage, diode de roue libre, résistance série de base/grille.
Aujourd'hui ces composants restent « non classifiés » dans le rapport, alors qu'ils font
fonctionnellement partie du circuit détecté. Élargir les gabarits est impossible
(combinaisons infinies) ; on classifie donc les orphelins **après** la détection.

## Décisions actées

| Question | Décision |
|----------|----------|
| Règle de rattachement | **Hybride** : tout voisin direct est candidat, avec un score de rôle (sûr / possible) |
| Conflit entre deux circuits | Rattaché **au meilleur score de rôle** ; à égalité, au circuit avec la meilleure `confidence`. Un composant = un seul circuit. |
| Position dans le pipeline | **Passe après détection, leftovers only** : les 27 détecteurs ne changent pas ; seuls les composants non classifiés sont examinés |
| Architecture | **Nouveau module** `circuit_analyzer/satellites.py` (approche A) |

## Architecture

### Nouveau module `circuit_analyzer/satellites.py`

Fonction publique unique :

```python
def rattacher_satellites(circuits: list[dict], graphe, composants_utilises: set) -> None
```

- Appelée à la fin de `detecteur.analyser()`, après la boucle de détection et avant le retour.
- Mute chaque match en place : ajoute `satellites: list[dict]` (toujours présent, vide par défaut).
- Met à jour `composants_utilises` avec les refs rattachées en « sûr » uniquement
  (les « possibles » restent disponibles et listés à part).

Format d'un satellite :

```python
{'ref': 'R2', 'role': 'pull-down', 'score': 0.9,
 'reason': 'R 10k entre NET_BASE et GND'}
```

### Rôles reconnus (liste blanche)

| Rôle | Condition topologique | Score |
|------|----------------------|-------|
| `pull-up` / `pull-down` | R entre nœud interne du circuit et rail (VCC / GND), valeur ≥ 10k | 0.9 (0.7 sans valeur) |
| `decoupling` | C ≤ 1µF entre rail d'alim utilisé par le circuit et GND | 0.9 (0.7 sans valeur) |
| `bulk` | C > 1µF entre rails | 0.8 |
| `flyback` | D cathode sur rail, anode sur nœud de commutation du circuit | 0.85 |
| `series-r` | R en série sur un nœud d'entrée du circuit (degré 2, faible valeur) | 0.7 |
| `unknown-neighbor` | composant touchant un nœud interne, rôle non identifié | 0.4 |

Seuils :
- **score ≥ 0.6 → « Satellites sûrs »** (rattachés, verrouillés, exportés dans le bloc XML du circuit)
- **0.3 ≤ score < 0.6 → « Satellites possibles »** (affichés avec `?`, non verrouillés, restent dans le bloc Divers de l'export)

Réutilise l'existant : `parse_valeur`, `classifier_resistance`, `classifier_condensateur`
(`value_parser.py`) et `classify_net`, `is_ground_net`, `is_power_net` (`patterns/base.py`).

### Définition de « nœud interne »

Les nœuds d'un match (`match['nodes']`) qui ne sont ni GND, ni rail d'alimentation, ni PE.
Les rails sont partagés par tout le schéma : un composant qui ne touche un circuit que par
VCC/GND n'est PAS un voisin (exception : le découplage, qui par définition vit entre rails
mais doit toucher le rail d'alim effectivement utilisé par le circuit).

## Rapport (`rapport.py`)

```
[1] Commande de relais
    Confiance    : élevée (90%) — commande
    Composants   : Q1, K1, D1
    Satellites sûrs     : R2 (pull-down — R 10k entre NET_BASE et GND)
    Satellites possibles: R7 ? (rôle inconnu, adjacent à NET_COLL)
```

- Les satellites (sûrs ET possibles) sortent de la liste « Composants non classifiés ».
- Les « possibles » portent un marqueur `?`.
- Lignes absentes si le match n'a aucun satellite (pas de bruit).

## Export XML (`xml.py`)

- Satellites **sûrs** : ajoutés au bloc visuel de leur circuit dans le layout groupé.
- Satellites **possibles** : restent dans le bloc Divers (pas de rattachement incertain
  dans un schéma destiné au logiciel de design).

## Hors périmètre (v1)

- Pas de rendu schemdraw des satellites dans `gui/circuit_viewer.py` — le schéma du
  pattern reste canonique.
- Pas de rôles configurables en JSON (la logique exige du Python ; YAGNI).
- Détection d'îlots fonctionnels = sous-projet 2, design séparé.
- Performance grosses netlists = sous-projet 3.
- Packaging .exe = sous-projet 4.

## Tests (`tests/test_satellites.py`, ~20 tests)

1. Chaque rôle détecté avec valeur → score fort ; sans valeur → score réduit.
2. Voisin inconnu → 0.4, classé « possible ».
3. Conflit deux circuits → rattaché au meilleur score ; à égalité, à la meilleure confiance.
4. Invariant leftovers-only : aucun composant déjà classifié n'est réexaminé ni déplacé.
5. Composant touchant un circuit uniquement par un rail → non rattaché (sauf découplage).
6. Rendu rapport : lignes « Satellites sûrs / possibles », disparition des refs de
   « non classifiés », absence de lignes quand vide.
7. Export XML : satellite sûr dans le bloc du circuit, possible dans Divers.
8. Rétro-compatibilité : `match['satellites']` toujours présent ; **zéro régression sur
   les 200 tests existants**.

## Critères de succès

- `python -m pytest -q` : 200 tests existants verts + ~20 nouveaux.
- Sur `circuits_industriels/relay_driver.xml` : la diode de roue libre et les R/C annexes
  apparaissent comme satellites du circuit de commande au lieu de « non classifiés ».
- Le rapport reste lisible : aucun satellite affiché quand il n'y en a pas.
