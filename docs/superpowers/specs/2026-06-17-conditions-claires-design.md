# Design — Conditions de reconnaissance plus claires

**Date :** 2026-06-17
**Portée :** « les deux » — renommer/regrouper les conditions ET résumé en clair dans le wizard.

## Problème

Les conditions sont du jargon (« Feedback OUT→IN- »), il y a un doublon, et 13 cases en vrac. Elles
apparaissent à la fois dans l'onglet Circuits et l'étape 3 du wizard.

## Contrainte clé : ne pas casser la persistance

Le libellé d'une condition sert aussi de **clé** dans `_check_condition` et de **valeur stockée** dans
`custom_circuits.json`. On garde donc les chaînes actuelles comme **clés stables** et on ajoute une
couche d'affichage séparée. La logique et les patterns existants restent valides.

## Partie 1 — Renommer + regrouper (`custom_circuits/loader.py`)

- `CONDITION_LABELS` : on retire le doublon « Transistor émetteur à GND » (sous-cas exact de
  « Émetteur/Source à GND »). Sa branche dans `_check_condition` est conservée (alias rétro-compatible).
- Nouveau `CONDITION_DISPLAY` : clé → libellé clair en français.
- Nouveau `CONDITION_GROUPS` : 3 familles ordonnées (Présence de composants · Masse & alimentation ·
  Câblage), chacune listant ses clés. Couvre exactement `CONDITION_LABELS`.
- `CONDITION_DESCRIPTIONS` : inchangé (déjà couvrant), reformulé si utile.

## Partie 2 — Affichage

- **`tab_circuits._build_conditions`** : itère `CONDITION_GROUPS`, affiche un titre de famille puis,
  par condition, une case dont le texte est `CONDITION_DISPLAY[clé]` et la description en dessous.
  `self._cond_vars` reste indexé par **clé** (sauvegarde inchangée).
- **`pattern_wizard` étape 3** :
  - Une phrase en clair toujours visible : « Ce qui distingue ce circuit : … » construite depuis les
    conditions détectées (`self._suggested`) via `CONDITION_DISPLAY`.
  - Les cases techniques passent sous un repli « Options avancées » (masqué par défaut), et utilisent
    aussi `CONDITION_DISPLAY`.

## Gestion d'erreurs

- Clé sans entrée `CONDITION_DISPLAY` → on retombe sur la clé brute (jamais de case vide).
- Aucune condition détectée dans le wizard → phrase « Aucune condition particulière détectée. »

## Tests

- `CONDITION_DISPLAY` couvre toutes les clés de `CONDITION_LABELS` ; `CONDITION_GROUPS` aussi
  (union = `CONDITION_LABELS`, sans doublon).
- Le doublon retiré matche toujours via son alias (`_check_condition`).
- Invariants existants conservés (description par condition, présence des clés clés).
- 357 tests restent verts.

## Hors périmètre

- Conditions à contraintes de valeurs (R1≈R2, C>1µF) — feature séparée de l'audit.
