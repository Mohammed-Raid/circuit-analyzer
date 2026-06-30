# Demo Executive Summary Design

## Objectif

Préparer une première démonstration claire de l'application pour un responsable
qui ne l'a jamais vue. L'amélioration doit rendre le résultat d'analyse
compréhensible en moins d'une minute, sans nécessiter d'explication détaillée du
graphe, des patterns ou du code.

## Portée

Cette itération ajoute un résumé exécutif dans l'onglet `Analyser` après chaque
analyse réussie. Elle prépare aussi un fichier de démonstration recommandé, sans
ajouter de gros mode démo ni refondre l'interface.

Hors portée pour cette itération :

- refonte complète de l'interface ;
- nouveau moteur de détection ;
- nouveaux patterns électroniques ;
- génération automatique de slides ;
- bouton intégré "Charger exemple de démo", sauf si le fichier de démo seul ne
  suffit pas pendant la répétition.

## Expérience Utilisateur

Après clic sur `Analyser`, un bloc `Résumé exécutif` apparaît au-dessus de la
structure en étages et des cartes de circuits. Il présente :

- le nombre total de composants analysés ;
- le nombre de circuits reconnus ;
- le taux de classification ;
- une lecture rapide des catégories dominantes ;
- le nombre de points à vérifier.

Le texte doit rester lisible pour un non-développeur :

```text
Résumé exécutif
Analyse terminée : 42 composants analysés, 5 circuits reconnus.

Lecture rapide :
Le schéma contient principalement de la commutation, de l'alimentation et des protections.

Points à vérifier :
3 composants restent non classifiés ou nécessitent une validation ingénieur.
```

## Données Et Calculs

Le résumé utilise uniquement les données déjà disponibles dans `TabAnalyze` :

- `comps` pour le nombre total de composants ;
- `results` pour les circuits détectés ;
- `classified` et `unclassified` pour le taux de classification ;
- `result["circuit_type"]` et la fonction `_category()` pour les familles
  dominantes ;
- `result["satellites"]` et `result["warnings"]` si disponibles pour estimer les
  points nécessitant vérification.

Le calcul doit rester déterministe et sans nouvelle dépendance.

## Intégration GUI

L'implémentation reste dans `gui/tab_analyze.py` :

- ajouter un helper de synthèse textuelle ;
- ajouter un widget interne `_ExecutiveSummary` ou une méthode de rendu dédiée ;
- appeler ce rendu au début de `_render_cards()`, avant `_render_islands()`.

Le bloc doit respecter le style existant : `CARD`, `CARD2`, `BORDER`, `TEXT`,
`MUTED`, `BLUE`, sans palette nouvelle dominante.

## Exemple De Démo

La démo utilisera un fichier existant qui produit un résultat riche et stable,
à choisir parmi :

- `circuits_industriels/relay_driver.xml` ;
- `circuits_industriels/smps_full.xml` ;
- `circuits_industriels/motor_control.xml` ;
- `exemples/test_circuit_complet.txt`.

Le choix final se fera après exécution rapide : on retient celui qui montre le
mieux les circuits détectés, les statistiques, les éventuels satellites, et un
rapport lisible.

## Gestion Des Erreurs

Le résumé n'apparaît que pour une analyse réussie. En cas d'erreur de lecture ou
de parsing, le comportement actuel reste inchangé : boîte de dialogue et retour
à l'état vide.

Si aucun circuit n'est détecté, le résumé doit rester utile :

```text
Analyse terminée : 12 composants analysés, aucun circuit reconnu.
Lecture rapide : le schéma ne correspond pas encore aux patterns intégrés.
Points à vérifier : 12 composants restent non classifiés.
```

## Tests

Ajouter des tests ciblés si la logique de résumé est extraite dans une fonction
pure. Sinon, vérifier au minimum :

- collecte pytest ;
- suite pytest complète ;
- ouverture/analyse manuelle d'un fichier de démo dans l'interface si possible.

La priorité est de ne pas perturber les 309 tests existants.

## Critères D'Acceptation

- Après une analyse réussie, le résumé exécutif apparaît en haut des résultats.
- Le résumé contient total composants, circuits reconnus, taux de classification
  et points à vérifier.
- Le texte reste clair pour une première présentation.
- Les cartes de circuits, la structure en étages, la sauvegarde et l'export XML
  continuent de fonctionner.
- Un fichier de démo recommandé est identifié pour la présentation.
