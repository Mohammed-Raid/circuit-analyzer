# Design — Détection d'îlots fonctionnels

**Date :** 2026-06-10
**Statut :** approuvé
**Sous-projet :** 2/4 du chantier « optimisation industrielle » (après : satellites ;
avant : performance, packaging .exe)

## Problème

Le rapport liste les circuits détectés à plat, sans vision de la structure en étages
du schéma (étage alim, étage commande, étage mesure). L'objectif : regrouper les
composants en îlots fonctionnels même quand aucun pattern exact ne matche.

## Décisions actées

| Question | Décision |
|----------|----------|
| Usages | Section rapport + export XML ordonné par îlot + arbre repliable dans la GUI |
| Nommage | Catégorie fonctionnelle majoritaire des circuits contenus ; égalité → « cat1 + cat2 » ; aucun circuit → « non identifié » |
| Composants rail-to-rail | Un îlot par rail d'alimentation : « alimentation VCC_12V »… ; uniquement GND/PE → « non identifié » |
| GUI | Panneau repliable « Structure en étages » dans l'onglet Analyser (frames + boutons toggle, pas de treeview) |
| Architecture | Module `circuit_analyzer/ilots.py`, calcul unique dans `analyser()`, résultat attaché à `ResultatsAnalyse.ilots` |

## Algorithme (`circuit_analyzer/ilots.py`)

```python
def detecter_ilots(graphe, circuits: list) -> list[dict]
```

1. **Union-Find sur les refs** : pour chaque net non-rail, unionner tous les composants
   qui le touchent. Réutilise `_est_rail` de `satellites.py`.
2. **Composants rail-only** : groupés par premier rail d'alim touché (tri alphabétique
   pour le déterminisme). Que GND/PE → îlot « non identifié ».
3. **Mapping circuits → îlots** : un match appartient à l'îlot contenant son premier
   composant. `circuits` = indices dans la liste des résultats.
4. **Tri** : par taille décroissante (nombre de composants), numérotation « Îlot N ».

Format de sortie :

```python
{'label': 'Îlot 1 - commutation', 'categorie': 'commutation',
 'composants': ['D1', 'K1', 'Q1', 'R1', 'R2'],   # triés
 'circuits': [0, 1],                                # indices dans resultats
 'rail': None}                                      # ou 'VCC_12V'
```

## Intégration

- `detecteur.analyser()` : `resultats.ilots = detecter_ilots(graphe, circuits_trouves)`
  après la passe satellites. `ResultatsAnalyse.__init__` initialise `ilots = []`.
- **Rapport** : section `=== STRUCTURE EN ETAGES ===` après les circuits, avant les
  non-classifiés. Une ligne par îlot + sous-lignes circuits (avec satellites sûrs
  entre parenthèses) ou liste de composants si aucun circuit. 100 % cp1252.
- **XML** : `_grouper_par_circuit` ordonne les blocs par îlot (les circuits du même
  îlot consécutifs dans la grille), Divers en dernier. Format inchangé.
- **GUI** (`gui/tab_analyze.py`) : panneau « Structure en étages » repliable sous le
  rapport ; chaque îlot = section avec bouton toggle, lignes circuits/composants.

## Hors périmètre

- Héritage de catégorie pour les composants orphelins
- Fusion inter-îlots via transformateurs/optocoupleurs (l'isolation galvanique est
  une frontière fonctionnelle légitime)
- Nouvel onglet GUI

## Tests (`tests/test_ilots.py`, ~16 tests)

Union-Find (îlots disjoints, AOP multi-broches, pont entre îlots), îlots par rail,
GND-only → non identifié, nommage (majorité / égalité / aucun circuit), mapping
circuits→îlots, section rapport + encodage cp1252, ordre des blocs XML,
rétro-compat (`.ilots` toujours présent), e2e type relay driver, zéro régression
sur les 247 tests existants.

## Critères de succès

- `python -m pytest -q` : 247 tests existants verts + ~16 nouveaux.
- Sur `relay_driver.xml` : les 3 étages relais apparaissent comme îlots distincts,
  les découplages regroupés par rail (VCC_12V / VCC_5V), X1-X3 en « non identifié ».
- La GUI affiche l'arbre sans dépendance nouvelle.
