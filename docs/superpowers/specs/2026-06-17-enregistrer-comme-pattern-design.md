# Design — « Enregistrer comme pattern » depuis l'éditeur de schéma

**Date :** 2026-06-17
**Portée :** Partie A uniquement (création de pattern à partir d'un circuit dessiné). L'onglet « Circuits » manuel n'est pas modifié.

## Problème

Créer un circuit personnalisé est anti-naturel : dans l'onglet « Circuits » il faut cocher, dans
l'abstrait, des composants et des « conditions » topologiques sans aucun exemple. L'utilisateur a
jugé le concept confus.

Le flux naturel — « voici mon circuit, enregistre-le comme pattern » — existe déjà à moitié via le
`PatternWizard`, mais il est verrouillé : il ne s'ouvre qu'après analyse et seulement sur les
composants **non reconnus** (≥ 2).

## Solution

Débloquer le wizard en lui donnant un point d'entrée depuis l'onglet **Schéma**.

### Composant modifié : `gui/tab_draw.py`

1. **Nouveau bouton** dans la barre du bas : « 💾 Enregistrer comme pattern », à gauche de
   « ▶ Analyser ce circuit ».
2. **Refactor** : extraire l'écriture de la netlist dans un helper `_export_netlist_file() -> str | None`
   (contrôles « circuit vide » + écriture du fichier temporaire). Réutilisé par `_launch_analyze`
   (qui garde en plus son avertissement broches non câblées) et par la nouvelle méthode.
3. **Nouvelle méthode** `_save_as_pattern()` :
   - obtient le fichier netlist via le helper (sort si `None`) ;
   - `composants = lire_netlist(path)` puis `graph = construire_graphe(composants)` ;
   - construit `comp_info = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} ...}` ;
   - ouvre `PatternWizard(self.frame, graph, refs_de_tous_les_composants, comp_info,
     on_created=callback)` ;
   - le callback affiche une confirmation « pattern créé ».

### Code réutilisé tel quel (aucune modification)

- `PatternWizard` : son étape 1 pré-coche tous les composants reçus ; son étape 3 appelle
  `suggest_conditions()` qui détecte et pré-coche automatiquement les conditions vraies. Le
  paramètre nommé `unclassified` sert ici de « liste de composants candidats » — sémantique
  élargie, signature inchangée.
- `lire_netlist`, `construire_graphe`, `suggest_conditions`.

## Flux de données

```
Éditeur (_comps) --to_netlist--> fichier .sp temporaire
   --lire_netlist--> list[Composant] --construire_graphe--> MultiGraph
   --> PatternWizard (étape 1: tous pré-cochés, étape 3: conditions auto)
   --> custom_circuits.json (append)
```

## Gestion d'erreurs

- Circuit vide / netlist vide : message d'avertissement (helper partagé), pas d'ouverture du wizard.
- Échec de `suggest_conditions` : déjà géré par le wizard (try/except → aucune suggestion).
- Nom de pattern en doublon : déjà géré par la validation de l'étape 2 du wizard.

## Tests

- `tests/test_tab_draw_pattern.py` (nouveau, headless) : construire un éditeur, placer R + C reliés à
  GND, vérifier que `lire_netlist`/`construire_graphe` sur sa netlist produit un graphe sur lequel
  `suggest_conditions` renvoie au moins « C connecté à GND ». Valide le pont éditeur → graphe sans
  ouvrir de fenêtre Tk.
- La suite complète (335 tests) reste verte.

## Hors périmètre

- Nettoyage de l'onglet « Circuits » manuel (doublon de conditions, regroupement, libellés) — Partie B,
  reportée.
- Bouton « détecter depuis mon schéma » dans l'onglet manuel — remplacé par ce flux.
