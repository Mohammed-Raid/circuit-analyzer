# Design — Performance grosses netlists

**Date :** 2026-06-10
**Statut :** approuvé
**Sous-projet :** 3/4 du chantier « optimisation industrielle » (après : satellites,
îlots ; avant : packaging .exe)

## Baseline mesurée (blocs relay-driver répliqués, nets uniques par bloc)

| Composants | Analyse | Matches supprimés |
|-----------:|--------:|------------------:|
| 96 | 0.38 s | 498 |
| 496 | 9.56 s | 13 423 |
| 2000 | 206.87 s | 218 625 |
| 5000 | **1039.94 s (17 min)** | **1 366 875** |

Croissance quadratique. Causes identifiées :

1. `detecter_pont_diviseur` énumère les paires de R sur **chaque nœud, y compris
   GND/VCC** (deg² sur les rails). Électriquement faux en plus : un diviseur n'a
   jamais un rail comme nœud milieu.
2. `detecter_miroir_courant` compare **toutes les paires de BJT** du schéma alors
   que le miroir exige une base commune.
3. `analyser()` appelle `_enrichir()` (calcul de confiance complet) **avant** le
   test anti-vol : 1.37 M de matches supprimés enrichis pour rien.
4. `_absorber_annexes` recalcule `_noeuds_internes`/`_rails_alim` par paire
   annexe×hôte.

## Cible (validée)

- **5000 composants < 10 s** (pipeline complet : graphe + détection + satellites + îlots)
- 496 composants : < 1 s (vs 9.56 s)

## Décisions actées

- **Changement de comportement accepté** : les faux diviseurs via rail et les
  faux snubbers entre rails disparaissent ; les tests existants concernés sont
  mis à jour (commit explicite).
- Pas de trace « paire ignorée » dans le rapport (verbosité inutile).

## Correctifs

### 1. Détecteurs (électriquement justifiés)

| Détecteur | Correctif |
|-----------|-----------|
| Pont diviseur | le nœud milieu doit être **non-rail** : `continue` sur GND/alim/PE avant d'énumérer les paires |
| Absorbeur RC | ignorer les paires de nœuds **toutes deux rails** (R∥C entre VCC et GND = bleeder + découplage, pas un snubber) |
| Miroir de courant | grouper les BJT **par net de base**, n'apparier qu'au sein d'un groupe |

### 2. Enrichissement différé (`analyser()`)

Test anti-vol AVANT enrichissement. Les matches supprimés ne sont plus enrichis :
le rapport n'utilise que `circuit_type`, `components` et `locked_components`
(fallback `components` déjà en place dans rapport.py).

### 3. Cache absorption satellites

Pré-calculer `(_noeuds_internes(h), _rails_alim(h))` une fois par hôte dans
`_absorber_annexes`.

### 4. Rapport : plafond des supprimés

Affichage limité à 50 lignes + `... et N autres matches supprimés`.

### 5. Outillage de mesure

- `tools/benchmark.py` : netlists synthétiques 100/500/1000/2000/5000, tableau
  temps graphe/analyse + compteurs. Sert à valider la cible et à détecter les
  régressions futures.
- `tests/test_performance.py` : garde-fou dans la suite — 1000 composants
  analysés en **< 5 s** (seuil large anti-flaky, mais qui échoue si un
  quadratique revient).

## Correctifs ajoutés en implémentation

Deux causes supplémentaires identifiées au benchmark/profilage :

5. **Filtres RC/LC** : même défaut que le pont diviseur — la jonction R-C
   (ou L-C) d'un filtre est un nœud signal, mais les détecteurs énuméraient
   les paires sur VCC/GND (R série depuis VCC x C de découplage = faux
   « Filtre RC passe-bas » quadratique). Correctif : `continue` sur les rails.
6. **Classification des nets** : `is_power_net`/`is_ground_net` reconstruisaient
   ~18 regex (`re.escape` + `re.match`) à chaque appel — 863 000 matchs regex
   à 2000 composants pour ~1250 nets distincts. Correctif : une regex alternée
   précompilée par catégorie + `lru_cache` (sûr : les alias sont figés à
   l'import du module).

## Critères de succès

- `tools/benchmark.py` : 5000 composants < 10 s.
- Suite complète verte (tests des faux diviseurs/snubbers mis à jour).
- `relay_driver.xml` : plus aucun « Pont diviseur » avec un rail en nœud milieu ;
  les R concernées redeviennent satellites ou non-classifiées.

## Résultats mesurés (2026-06-11)

| Composants | Avant | Après |
|-----------:|------:|------:|
| 100 | 0.38 s | 0.02 s |
| 500 | 9.56 s | 0.12 s |
| 1000 | — | 0.19 s |
| 2000 | 206.87 s | 0.75 s |
| 5000 | 1039.94 s | **3.28 s** |

Matches supprimés à 5000 comps : 1 366 875 -> 625 (1 par bloc, linéaire).
`relay_driver.xml` : 5 ponts diviseurs restants, tous à nœud milieu signal ;
8 supprimés (avant : des centaines). Suite : 282 tests verts.
