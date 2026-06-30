# Vue îlot « chaîne branchée » (DAG en couches)

**Date :** 2026-06-25
**Statut :** approuvé (approche A)

## Objectif

Les îlots multi-AOP **branchés** (ex. `pid_controller` : entrée → P/I/D en
parallèle → sommateur → buffer) doivent s'afficher en **schéma connecté
gauche→droite**, comme `chaine_5_aop`, au lieu de retomber sur la grille
abstraite (`_make_island_fig`).

## Portée

- **Dans le périmètre :** ordonnancement en couches d'un DAG de montages, câblage
  fan-out / fan-in, placement gauche→droite, réutilisation des drawers AOP
  existants.
- **Hors périmètre :** la *qualité de détection* (ex. l'étage P de pid vu comme
  différentiel ayant absorbé C4/R12/R14). Le layout sera correct ; chaque AOP
  s'affiche selon sa détection actuelle. À traiter séparément.
- **Inchangé :** îlots linéaires → vue chaîne actuelle ; îlots non ordonnançables
  (cycle, topologie inattendue) → repli grille.

## Architecture

### 1. Ordonnancement en couches — `_layers_montages_flux(matches)`
- **Entrées d'un montage** (`in_nets(m)`), selon le type :
  - inverseur / intégrateur / dérivateur : nœud extérieur de `Zin` (1).
  - sommateur : nœud extérieur de **chaque** entrée de `Zin` (liste).
  - différentiel : nœuds extérieurs de `Z1` et `Z3` (2).
  - non-inverseur / suiveur : net IN+ (`nodes[0]`).
- **Sortie** : `out_net(m) = nodes[-1]`.
- **Graphe** : arête `i→j` si `out_net(i)` ∈ `in_nets(j)`.
- **Couches** : profondeur = plus long chemin depuis une source (étage dont
  aucune entrée n'est la sortie d'un autre). Étages d'une même profondeur empilés.
- **Retour** : `list[list[match]]` (couches ordonnées) **ou None** si pas un DAG
  couvrant exploitable (cycle, étage isolé, < 2 montages).

### 2. Ancres par net d'entrée
Les drawers (`_draw_aop_*`) renvoient, en plus de `{"in","out"}`, une clé
`"ins": {net_d_entrée → (x,y)}`. `in` reste (rétro-compatible : = première ancre).
`_dessiner_montage_a` propage `ins`. Couverture : inverseur/intég/dériv (1 net),
non-inv/suiveur (1 net), Schmitt/comparateur (1 net), sommateur (N nets),
différentiel (2 nets).

### 3. Dessin — `_draw_branched_chain(d, layers, ci)`
- Place chaque étage à `x = base + couche * _CHAINE_DX`, `y` réparti dans la
  couche (étages parallèles centrés autour de 0).
- Pour chaque arête producteur→consommateur sur le net `n` : fil en Z de
  `producteur.out` vers `consommateur.ins[n]`.
- Les entrées externes (alimentées par aucun étage) gardent leur libellé/stub ;
  la sortie finale garde `VOUT`.

### 4. Intégration — `_make_branched_fig` + `show_island`
- `_make_branched_fig(layers, ci)` : même cadre/scroll que `_make_chain_fig`.
- `show_island`, ordre d'essai : montage principal unique → chaîne linéaire
  (`_ordonner_montages_flux`) → **couches branchées** (`_layers_montages_flux`) →
  grille (`_make_island_fig`).

## Critère de réussite
- `_layers_montages_flux` sur pid renvoie 3 couches : `[{P,I,D}, {sommateur}, {buffer}]`.
- La vue îlot de pid se rend en schéma connecté (aucun « Schéma non disponible »,
  pas de repli grille), avec les boîtes Z cliquables préservées.
- `chaine_5_aop` (linéaire) reste rendu par la vue chaîne existante (non-régression).
- Suite de tests verte.

## Tests (TDD)
- Unitaire ordonnancement : pid → 3 couches `[{P,I,D}, {sommateur}, {buffer}]`.
  (Le cas linéaire est géré en amont par `_ordonner_montages_flux` ; `show_island`
  n'appelle la voie branchée qu'après échec du linéaire, donc on ne contraint pas
  le retour de `_layers_montages_flux` sur une chaîne linéaire.)
- Unitaire ancres : `_dessiner_montage_a` d'un sommateur expose `ins` avec un point
  par entrée ; différentiel expose 2 ; inverseur expose 1.
- Intégration : `_make_branched_fig(pid)` sans « non disponible », hitboxes Z ≥ N.
