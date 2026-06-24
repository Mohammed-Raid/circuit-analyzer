# Design — Chaîne de schémas connectés (vue îlot multi-AOP)

Date : 2026-06-24
Statut : approuvé (en attente de revue du spec)

## Problème

La vue îlot actuelle (`_make_island_fig`) dessine un layout générique : pour un
îlot à un seul composant actif, `_circuit_principal_ilot` route vers le drawer
dédié (schéma propre « AOP + Z »). Mais dès qu'un îlot contient **plusieurs AOP**
(ex. une chaîne de conditionnement à 5 étages), ce routage échoue
(`len(actifs) != 1`) et on retombe sur le layout générique : tous les AOP empilés
verticalement, boîtes Z éparpillées, fils croisés sur toute la largeur →
**illisible**. On ne distingue ni les types de montage, ni quel Z appartient à
quel étage, ni le flux du signal.

## Objectif

Pour un îlot multi-AOP qui forme une **chaîne de signal linéaire**, afficher
**un seul grand schéma** où chaque étage est dessiné par son drawer dédié (donc
lisible, avec ses boîtes Z cliquables) et où la **sortie de l'étage N est reliée
par un fil à l'entrée de l'étage N+1**. Le signal se lit de gauche à droite.

## Périmètre

Ne concerne QUE les îlots avec **≥2 composants actifs** (>2 broches) dont :
- tous les montages détectés possèdent un drawer dédié, et
- les étages forment une chaîne linéaire résoluble (cf. ordonnancement).

Inchangés (repli sur le comportement actuel) :
- îlot à 1 actif → drawer dédié (`_circuit_principal_ilot`) ;
- îlot passif → série/parallèle (`_arbre_serie_parallele_ilot`) ou pont (`_pont_ilot`) ;
- îlot multi-AOP non résoluble (branche, cycle, montage sans drawer) → vue
  générique `_make_island_fig`.

## Architecture

Tout est confiné à `gui/circuit_viewer.py`.

### 1. Ordonnancement — `_ordonner_montages_flux(matches, graph) -> list[dict] | None`

Pour chaque match de montage :
- `out_net` = net de la broche OUT de l'AOP (dernier élément de `match["nodes"]`).
- `in_net` = net d'entrée du signal :
  - si `match["impedances"]` contient `"Zin"` : nœud extérieur de Zin,
    soit `impedances["Zin"]["nodes"][1]` (inverseur / intégrateur / dérivateur) ;
  - sinon : net IN+ = `match["nodes"][0]` (non-inverseur, suiveur).

Construire les arêtes orientées `i → j` quand `out_net(i) == in_net(j)`.
Trier topologiquement. Retourner la liste ordonnée **seulement si** c'est un
chemin linéaire unique couvrant tous les montages ; sinon retourner `None`.

### 2. Drawers paramétrables + ancres

Les drawers partagés acceptent une origine et renvoient leurs points de
connexion. Signatures modifiées (rétro-compatibles par défaut) :

```
_draw_aop_inverseur_zin_zf(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT") -> {"in": pt, "out": pt}
_draw_aop_non_inverseur_zf_zg(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT") -> {"in": pt, "out": pt}
_draw_follower(d, result, ci, origin=(4.5, 0), in_label="IN", out_label="OUT") -> {"in": pt, "out": pt}
```

- L'AOP est ancré à `origin` au lieu de `(4.5, 0)` codé en dur.
- `in` = point le plus à gauche (le dot d'entrée) ; `out` = bout du fil de sortie.
- Les libellés IN/OUT deviennent paramétrables (pour les vider en interne de la
  chaîne et n'afficher que VIN/VOUT aux extrémités).
- Les appelants existants (`show_circuit`, îlot mono-actif via `_make_fig`)
  passent les valeurs par défaut → **comportement inchangé**, valeur de retour
  ignorée.

### 3. Dispatcher — `_dessiner_montage_a(d, match, ci, origin, in_label, out_label) -> {"in", "out"}`

Choisit le bon drawer partagé selon le match :
- `impedances` contient `"Zg"` → `_draw_aop_non_inverseur_zf_zg` ;
- `impedances` contient `"Zin"` → `_draw_aop_inverseur_zin_zf`
  (couvre inverseur, intégrateur, dérivateur — ils délèguent tous à ce drawer) ;
- type « Suiveur de tension (AOP) » → `_draw_follower`.

### 4. Orchestrateur — `_draw_island_chain(d, ordered, ci)`

- Pose le bloc N à `origin = (N * ΔX, 0)` (ΔX = largeur de bloc + marge, constante).
- Récupère les ancres `in`/`out` de chaque bloc.
- Libellés : premier bloc `in_label="VIN"`, dernier `out_label="VOUT"`,
  internes `""`.
- Trace un fil `out(N) → in(N+1)` (segment horizontal, même hauteur y=0).
- Les boîtes Z poussent leurs hitboxes dans `d._z_hitboxes` (déjà en coords
  absolues, donc correctement décalées) → drill-down conservé.

### 5. Figure + défilement — `_make_chain_fig(ordered, comp_info) -> Figure`

Miroir de `_make_fig` mais appelle `_draw_island_chain`. La figure est large
(N blocs). Affichage dans `show_island` via un **conteneur à défilement
horizontal** (canvas matplotlib dans un cadre scrollable) : lecture gauche→droite,
hauteur bornée comme `_make_fig` (≤ 4.2") pour tenir dans la fenêtre. `fig._z_hitboxes`
renseigné pour les clics, comme `_make_fig`.

### 6. Branchement dans `show_island`

Nouvelle branche, avant le repli `_make_island_fig` :

```
principal = _circuit_principal_ilot(...)
if principal is not None:            # 1 actif -> drawer dédié (inchangé)
    ...
elif _sp is not None: ...            # passif série/parallèle (inchangé)
elif _pont is not None: ...          # pont (inchangé)
else:
    ordered = _ordonner_montages_flux(_matches_for_island(ilot, results), graph)
    if ordered and len(ordered) >= 2:
        fig = _make_chain_fig(ordered, comp_info)   # NOUVEAU : chaîne connectée
        # + canvas dans conteneur scrollable horizontal
    else:
        fig = _make_island_fig(model, matches=...)  # repli générique (inchangé)
```

## Flux de données

`detecter_ilots` → îlot (refs) → `show_island` → `_matches_for_island` →
`_ordonner_montages_flux` (ordre flux) → `_draw_island_chain`
(`_dessiner_montage_a` par bloc + fils) → `_make_chain_fig` → canvas scrollable
+ hitboxes Z cliquables (drill-down R/L/C via `show_dipole_detail`).

## Gestion d'erreurs / replis

- Ordonnancement non linéaire ou montage sans drawer → `None` → vue générique.
- Aucune régression sur les îlots mono-actif, passifs, ou non-AOP.

## Tests

- `_ordonner_montages_flux` sur `chaine_5_aop.xml` → ordre
  [non-inverseur, inverseur, intégrateur, dérivateur, suiveur].
- `_ordonner_montages_flux` sur un îlot non chaîné → `None`.
- `_draw_island_chain` sur la chaîne → N hitboxes Z (une par boîte cliquable
  de chaque étage) présentes, et un fil de liaison entre blocs consécutifs.
- Non-régression : `show_island` sur un îlot mono-AOP utilise toujours le drawer
  dédié (pas la chaîne).

## Hors périmètre (YAGNI)

- Pas de gestion des branches/arborescences de signal (uniquement chaîne linéaire).
- Pas de réarrangement « serpent » multi-lignes (défilement horizontal suffit).
- Pas de nouveau type de montage : on réutilise les drawers existants.
