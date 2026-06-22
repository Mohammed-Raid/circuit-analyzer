# Dessin du pont de Wheatstone (losange) dans la vue d'îlot

Date : 2026-06-22
Branche : `rewrite-simple`

## Contexte

La vue d'îlot dessine maintenant la forme série/parallèle quand le réseau se réduit
entre VIN et VOUT (`gui/circuit_viewer.py::_arbre_serie_parallele_ilot` + hook dans
`show_island`). Mais un **pont de Wheatstone** n'est pas série/parallèle : il retombe
sur l'ancien dessin colonnes-bus, toujours incompréhensible.

Un pont a une forme canonique reconnaissable — le **losange**. On détecte ce motif
précis et on le dessine ainsi ; tout autre réseau non-S/P garde l'ancien dessin.

Topologie cible (vérifiée sur `circuits_industriels/impedance_pont_wheatstone.xml`) :
4 nœuds — VIN, VOUT (degré 2, non adjacents), et 2 nœuds internes (degré 3) ;
5 arêtes — VIN-N1, VIN-N2, N1-VOUT, N2-VOUT, N1-N2 (diagonale).

```
            VIN
           /    \
        R1        R2
        /          \
      N1 ──  R5  ── N2
        \          /
        R3        R4
           \    /
            VOUT
```

## Périmètre

- **Dans le périmètre** : détecter le motif pont (exactement 4 nœuds / 5 arêtes
  R/L/C dans la configuration ci-dessus, entre 2 bornes) et le dessiner en losange.
  Branché dans `show_island` après l'essai série/parallèle, avant le repli.
- **Hors périmètre** : tout autre réseau non-série/parallèle (repli sur l'ancien
  dessin) ; les ponts à impédances composites dans les bras (seuls des dipôles
  simples sur chaque arête sont gérés — voir « cas limites ») ; la fenêtre
  « Ω Impédance équiv. » ; `_make_island_fig`/`_build_island_model`.

## Composants

### 1. `circuit_analyzer.impedance.detecter_pont(graphe, a, b)` (pur, testable)

Détecte le motif pont entre les bornes `a` et `b` sur les arêtes R/L/C.

```
@return dict | None
  {
    "haut": a, "bas": b,
    "gauche": n1, "droite": n2,          # n1 = min(internes), n2 = l'autre
    "bras": {                            # rôle -> ref du composant de l'arête
        "haut_gauche": ref(a, n1),
        "haut_droite": ref(a, n2),
        "bas_gauche":  ref(n1, b),
        "bas_droite":  ref(n2, b),
        "pont":        ref(n1, n2),
    },
  }
```

Conditions pour renvoyer un dict (sinon None) :
- sous-graphe R/L/C = exactement 4 nœuds et 5 arêtes simples ;
- `a` et `b` présents, de degré 2, NON adjacents ;
- les 2 autres nœuds (`n1`, `n2`) de degré 3, adjacents entre eux ;
- les 5 arêtes sont exactement `a-n1, a-n2, n1-b, n2-b, n1-n2`.
`n1 = min(n1, n2)` (ordre déterministe via `sorted`).

### 2. `gui.impedance_schematic.dessiner_pont(pont, comps)` (rendu)

```
@param pont  structure renvoyée par impedance.detecter_pont.
@param comps dict {ref → Composant} (type pour le symbole, value pour l'étiquette).
@return matplotlib.figure.Figure (losange).
```
Coordonnées (unités schemdraw) : haut=(0,4), gauche=(-2,2), droite=(2,2), bas=(0,0).
Arêtes (symbole `R/L/C` selon le type, défaut boîte Z), placées `.at(p1).to(p2)` :
- `haut_gauche` : haut→gauche ; `haut_droite` : haut→droite ;
- `bas_gauche` : gauche→bas ; `bas_droite` : droite→bas ; `pont` : gauche→droite.
Étiquette de chaque arête : `ref` ou `ref\nvalue`. Deux `Dot` étiquetés : `a` au
sommet haut (loc="top"), `b` en bas (loc="bottom"). `ax.set_aspect("equal")`,
fond `SCH_BG`. Réutilise la sélection de symbole déjà présente pour `dessiner`.

### 3. `circuit_viewer._pont_ilot(ilot, graph)` + hook `show_island`

`_pont_ilot(ilot, graph) -> (pont, comps) | None` : même reconstruction de
sous-graphe que `_arbre_serie_parallele_ilot` (composants originaux dont la ref ∈
`ilot["composants"]`), vérifie VIN/VOUT bornes, appelle `detecter_pont(sous, "VIN",
"VOUT")`, renvoie `(pont, sous.graph["components"])` ou None.

Hook dans `show_island`, après l'essai série/parallèle et avant le repli :
```
res = _arbre_serie_parallele_ilot(ilot, graph)
if res is not None:
    fig = impedance_schematic.dessiner(arbre, "VIN", "VOUT", comps)
else:
    pont = _pont_ilot(ilot, graph)
    if pont is not None:
        fig = impedance_schematic.dessiner_pont(pont_struct, comps)
    else:
        matches = _matches_for_island(ilot, results)
        fig = _make_island_fig(model, matches=matches)
```

## Cas limites

- Réseau pas en pont (S/P, ou >4 nœuds, multi-broches) : `detecter_pont` → None →
  repli inchangé.
- Bras avec dipôle composite (plusieurs R/L/C entre deux nœuds) : non géré (sortirait
  du motif « 4 nœuds / 5 arêtes simples ») → None → repli. Acceptable : les ponts de
  démo ont un composant par bras.
- Figure pont sans `_z_hitboxes` : le handler `_on_click` lit
  `getattr(fig, "_z_hitboxes", [])` → pas de drill-down, pas de crash.

## Tests

`tests/test_impedance.py` :
- `detecter_pont` sur le pont (R1..R5) → dict avec le bon mapping rôle→ref ;
- `detecter_pont` sur un réseau série/parallèle → None ;
- `detecter_pont` sur un réseau à 3 nœuds (triangle) → None.

`tests/test_impedance_schematic.py` :
- `dessiner_pont` → Figure avec 1 axe (smoke), sur une structure pont jouet.

`tests/test_island_viewer.py` :
- `_pont_ilot` sur un îlot pont VIN/VOUT → (pont, comps) ; sur un îlot S/P → None.

Les 21 tests d'îlot et la suite complète restent verts.

## Hors périmètre (futur)

- Ponts à bras composites (réduire chaque bras d'abord, puis dessiner).
- Réseaux non-S/P généraux autres que le pont.
