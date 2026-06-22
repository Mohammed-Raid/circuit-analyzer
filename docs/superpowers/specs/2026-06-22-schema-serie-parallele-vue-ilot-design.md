# Forme série/parallèle dans la vue d'îlot (popup `show_island`)

Date : 2026-06-22
Branche : `rewrite-simple`

## Contexte

Le boss a trouvé le schéma d'îlot incompréhensible pour les réseaux série/parallèle
(forme « colonnes-bus » non reconnaissable). Une première étape a ajouté un rendu
série/parallèle « manuel » dans la fenêtre annexe « Ω Impédance équiv. »
(`gui/impedance_schematic.py` : `arbre_expr`, `agencer`, `dessiner`). Mais c'est le
**schéma d'îlot** (popup `gui/circuit_viewer.py::show_island`) que le boss regardait :
il n'a pas changé.

Cette étape amène la forme série/parallèle dans `show_island`, quand le réseau de
l'îlot est un réseau d'impédances réductible entre **VIN** et **VOUT**.

## Périmètre

- **Dans le périmètre** : `show_island` dessine en série/parallèle quand l'îlot se
  réduit entre VIN et VOUT ; sinon, comportement actuel inchangé.
- **Hors périmètre** : `_make_island_fig`, `_build_island_model`, `_draw_island_schematic`
  ne sont PAS modifiés. La fenêtre « Ω Impédance équiv. » n'est pas modifiée. Choix
  automatique de bornes autres que VIN/VOUT (repli sur l'ancien dessin).

## Flux

```
show_island(ilot, graph, comp_info, parent, results)
   |
   v
res = _arbre_serie_parallele_ilot(ilot, graph)     # helper pur, nouveau
   |                                   \
   | res = (arbre, comps)               \ res = None
   v                                     v
fig = impedance_schematic.dessiner(      fig = _make_island_fig(model, matches)
        arbre, "VIN", "VOUT", comps)            # exactement l'existant
   |                                     |
   +------------------> embarquer dans le canvas (FigureCanvasTkAgg) <--+
```

## Composant

### `circuit_viewer._arbre_serie_parallele_ilot(ilot, graph)` (pur, testable)

```
@param ilot  dict de l'îlot ; clé "composants" = liste des refs brutes.
@param graph graphe original (porte graph["components"] : {ref → Composant}).
@return (arbre, comps) | None
    arbre : arbre série/parallèle (cf. impedance.arbre_expr) ;
    comps : dict {ref → Composant} du sous-graphe (pour les symboles/valeurs) ;
    None si : aucun composant brut, ou VIN/VOUT absents des bornes, ou réseau
    non réductible (pont Y-Δ), ou expression non purement série/parallèle.
```

Étapes :
1. `raw = getattr(graph, "graph", {}).get("components", {})`.
2. `refs = [r for r in ilot.get("composants", []) if r in raw]` ; si vide → None.
3. `sous = construire_graphe([raw[r] for r in refs])`.
4. `bornes = impedance.bornes_possibles(sous)` ; si "VIN" ∉ bornes ou "VOUT" ∉ bornes → None.
5. `expr = impedance.impedance_equivalente(sous, "VIN", "VOUT")` ; si None → None.
6. `arbre = impedance.arbre_expr(expr)` ; si None → None.
7. retourner `(arbre, sous.graph["components"])`.

### Hook dans `show_island`

Avant de construire le modèle/figure existant, tenter le helper. S'il renvoie un
résultat, embarquer la figure de `impedance_schematic.dessiner(arbre, "VIN",
"VOUT", comps)`. Sinon, exécuter le chemin actuel (`_build_island_model` +
`_make_island_fig`) sans aucun changement. Le reste de `show_island` (popup,
titre, bouton export, drill-down) est inchangé ; seule la `fig` change de source.

## Gestion des cas limites

- Îlot sans VIN/VOUT, pont (Y-Δ), composants multi-broches (AOP) : helper → None →
  ancien dessin. Aucune régression.
- `construire_graphe` sur des composants déjà connus : réutilise l'API existante.

## Tests

`tests/test_island_viewer.py` (ou `tests/test_impedance_schematic.py`) :
- **réductible** : îlot VIN ─R1─ M ─R2─ VOUT avec R3 entre VIN et VOUT →
  `_arbre_serie_parallele_ilot` renvoie un arbre dont la forme correspond à
  `(R1+R2)//R3` (parallèle racine), et `comps` contient R1, R2, R3.
- **non VIN/VOUT** : îlot A ─R1─ B (pas de VIN/VOUT) → renvoie None.
- Les 21 tests d'îlot existants restent verts (helper additif).

## Hors périmètre (futur)

- Choix de bornes autres que VIN/VOUT.
- Dessin de la topologie d'un pont.
- Appliquer la forme aux circuits multi-broches.
