# Routage en L des fils internes au groupe — Design

**Date :** 2026-08-12
**Statut :** design validé en conversation, prêt pour le plan d'implémentation.

**Suite de :**
[2026-08-11-disposition-canonique-cartes-scannees-design.md](2026-08-11-disposition-canonique-cartes-scannees-design.md).
Ce chantier remplace la ligne droite diagonale (déjà en place, commit
`121786d`) par un routage en angle droit pour les fils internes à un
groupe déplacé — comparaison visuelle demandée par le boss avec le rendu
îlots (`tools/_renders/ilots_pour_chatgpt/*.png`, propre, angles droits,
sans diagonale).

## Contexte (pourquoi)

`gui/schema_router.py` fait déjà du routage Manhattan A* propre pour les
îlots, mais c'est un module à l'échelle schemdraw (`PAS = 0.5`, depuis
`gui/theme.SCHEMA_DIMS`), alors que nos coordonnées BoardSCH sont de
l'ordre de 80 à 260 unités par pas. Réutiliser tel quel exigerait de
reconvertir toute l'échelle et ferait chercher l'A* sur des milliers de
pas de grille pour une distance qui, chez nous, tient en 1 à 3 segments —
risque réel de dépasser `_MAX_NOEUDS` (20000) ou d'être simplement plus
lourd que le problème ne le justifie (2 à 4 fils, topologie entièrement
connue et contrôlée par notre propre calcul de positions, pas un problème
de placement générique).

## Décisions verrouillées

| Question | Décision |
|---|---|
| Algorithme | Routage en L sur-mesure (pas de réutilisation directe de `schema_router.py`) — un seul coude, deux chemins candidats par fil. |
| Chemins candidats | Horizontal-puis-vertical (`p1 → (x2,y1) → p2`) et vertical-puis-horizontal (`p1 → (x1,y2) → p2`). |
| Évitement | Chaque AUTRE composant de rôle du groupe (pas les deux que ce fil relie) obtient une boîte rectangulaire approximative (~160 de large, ~80 de haut, centrée sur sa position — approximation, `Composant` ne porte pas de forme réelle côté analyse). Un chemin est rejeté si un de ses segments traverse l'INTÉRIEUR d'une de ces boîtes. |
| Choix entre les deux chemins | Premier chemin (dans l'ordre horizontal-puis-vertical, vertical-puis-horizontal) qui ne traverse aucune boîte. |
| Aucun chemin ne marche | Repli sur la ligne droite actuelle (commit `121786d`) — jamais pire que ce qui est déjà livré. |
| Chemin déjà droit | Si les deux segments du L calculé sont colinéaires (le coude est dégénéré), on renvoie directement la ligne à 2 points — pas de coude inutile. |
| Portée | Toujours uniquement les fils dont les DEUX extrémités sont dans le groupe déplacé (même périmètre que le fix précédent) — rien ne change pour les fils sortant vers un composant non déplacé. |

## Architecture

Deux nouvelles fonctions dans `circuit_analyzer/eretro_patch.py`, juste
avant `_appliquer_deltas` :

### `_segment_croise_rectangle(p, q, rect) -> bool`

Teste si un segment axis-aligned (horizontal ou vertical — jamais
diagonal, puisque nos deux candidats ne produisent que des segments
horizontaux/verticaux) traverse l'intérieur d'un rectangle
`(x0, y0, x1, y1)`. Frontière = praticable (comme `Rect.contient_strict`
dans `schema_grid.py`, même principe, pas le même code — pas de nouvelle
dépendance vers `gui/`).

### `_router_fil_en_l(p1, p2, obstacles) -> list[tuple[float, float]]`

@param p1, p2 : nouvelles positions des deux extrémités (après delta).
@param obstacles : liste de rectangles `(x0, y0, x1, y1)` des AUTRES
composants de rôle du groupe.
@return Liste de 2 points (ligne droite) ou 3 points (chemin en L).

Construit les deux chemins candidats, teste chacun avec
`_segment_croise_rectangle` contre tous les `obstacles`, renvoie le
premier valide ; sinon `[p1, p2]`.

### Intégration dans `_appliquer_deltas`

La boucle existante sur `source.lignes` (qui gère aujourd'hui 3 cas :
même delta aux deux bouts, deltas différents aux deux bouts, un seul bout
déplacé) voit son cas « deltas différents aux deux bouts » remplacé :
au lieu d'écrire une ligne droite à 2 points, elle appelle
`_router_fil_en_l` avec les positions déjà translatées (lues sur
`source.elements[ref]` APRÈS la boucle de translation des `<CtrIem>`,
qui s'exécute avant celle des fils — ordre déjà en place) et les boîtes
des autres refs de `deltas` (excluant les deux extrémités de ce fil),
puis remplace tous les `<PointF>` existants du fil par le chemin obtenu.

## Gestion d'erreurs

Aucune nouvelle surface d'erreur : `_router_fil_en_l` ne lève jamais (pas
d'accès qui pourrait échouer), et son repli (ligne droite) est déjà le
comportement testé et livré aujourd'hui — dégradation, jamais une
régression en dessous de l'existant.

## Tests

- Unitaires sur `_segment_croise_rectangle` : segment horizontal et
  vertical, cas dedans/dehors/frontière.
- Unitaires sur `_router_fil_en_l` : cas où le chemin H-puis-V est libre,
  cas où seul V-puis-H est libre (obstacle place exprès sur l'autre),
  cas où aucun n'est libre (repli ligne droite), cas dégénéré (p1/p2
  alignés → 2 points, pas de coude).
- Intégration sur `_appliquer_deltas` : reprendre le scénario à 3 points
  du test précédent (`test_appliquer_deltas_avec_coude_et_deltas_differents_retrace_en_ligne_droite`),
  vérifier que le résultat est maintenant un chemin en L (3 points, angle
  droit) quand aucun obstacle ne le bloque.
- Non-régression : la suite existante sur `ecrire_groupes`/`_appliquer_deltas`
  (fils à un seul bout déplacé, deltas identiques aux deux bouts) reste
  inchangée.
- Visuel : régénérer `tools/_renders/carte_scannee_apres.png` (et un rendu
  sur `inver.xml` comme lors du fix précédent), inspecter réellement —
  comparer au rendu îlots de référence.

## Points ouverts pour le plan d'implémentation

- Taille exacte de la boîte d'évitement (proposé : 160×80, à confirmer si
  un composant réel s'avère systématiquement plus large/haut dans les
  cartes de test disponibles).
- Ordre de préférence entre les deux candidats quand LES DEUX sont libres
  (actuellement : premier de la liste, horizontal-puis-vertical, choix
  arbitraire mais déterministe — pas de critère esthétique supplémentaire
  pour l'instant).
