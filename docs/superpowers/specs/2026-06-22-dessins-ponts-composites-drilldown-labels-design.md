# Dessins : ponts à bras composites + clic-pour-déplier + étiquettes pro

Date : 2026-06-22
Branche : `rewrite-simple`

## Contexte

Les dessins d'impédance fonctionnent : forme série/parallèle (`dessiner`) et pont de
Wheatstone en losange (`dessiner_pont`), dans la fenêtre « Ω Impédance équiv. » et la
vue d'îlot. Trois améliorations demandées, toutes côté dessin :

1. **Ponts à bras composites** — `detecter_pont` n'accepte qu'UN composant par bras
   (4 nœuds / 5 arêtes simples). Un bras avec plusieurs R/L/C fait échouer la
   détection → repli sur l'ancien dessin. On veut réduire chaque bras en une **Z**
   d'abord, puis dessiner le losange avec des boîtes Z étiquetées par leur composition.
2. **Clic-pour-déplier** — les dessins série/parallèle et losange n'ont pas le
   drill-down (clic sur une Z → détail des R/L/C). On le rétablit pour les boîtes
   **composites**, dans la vue d'îlot ET la fenêtre Impédance.
3. **Étiquettes pro** — formater les valeurs avec unité : `10k`→`10 kΩ`,
   `100n`→`100 nF`, `1m`→`1 mH`, `470`→`470 Ω`.

## Décisions (validées)

- Bras composite : **boîte Z générique + composition lisible** (ex. « R1+C1 ») ;
  clic → détail.
- Drill-down : **vue d'îlot + fenêtre Impédance**.

## Périmètre

- **Dans le périmètre** : réduction des bras avant détection du pont ; labels
  composite = composition ; hitboxes sur les boîtes composites ; dessin du pont dans
  la fenêtre Impédance (aujourd'hui : simple message) ; handler de clic dans la
  fenêtre Impédance ; formatage des valeurs avec unité.
- **Hors périmètre** : gestion fine des collisions de labels (au-delà du formatage,
  best-effort) ; topologies non-S/P autres que le pont ; drill-down sur les feuilles
  simples des dessins série/parallèle (rien à déplier — chaque feuille est déjà un
  composant brut).

## Composants

### 1. `circuit_analyzer.impedance.formater_valeur(value, typ)` (pur, #3)

```
@param value Chaîne valeur ingénieur ("10k", "100n", "470", "").
@param typ   Type du composant ("R"/"L"/"C"/autre).
@return str  "10 kΩ", "100 nF", "1 mH", "470 Ω" ; "" si value vide ; value tel quel
             si non interprétable. Unité : R→Ω, L→H, C→F, autre→"".
```
Réutilise la même regex `[0-9]*\.?[0-9]+` + préfixe que `_parse_valeur`.

### 2. `circuit_analyzer.impedance.detecter_pont(graphe, a, b)` — bras composites (#1)

Avant le test du motif, **réduire** le graphe de travail par série + parallèle avec
`bornes = {a, b}` (réutilise `_passe_serie`/`_passe_parallele` jusqu'au point fixe).
Un vrai pont irréductible laisse le squelette 4 nœuds / 5 arêtes, chaque arête
portant `refs` (liste) et `expr` (composition). Les vérifs de motif sont inchangées
(4 nœuds, 5 arêtes simples, a/b degré 2 non adjacents, n1/n2 degré 3 adjacents).

**Changement de contrat** : chaque valeur de `bras[role]` devient un dict
`{"refs": [...], "composition": expr}` (au lieu d'une simple ref). Les tests existants
de `detecter_pont` sont mis à jour en conséquence.

```
return {
  "haut": a, "bas": b, "gauche": n1, "droite": n2,
  "bras": { role: {"refs": [...], "composition": "R1+C1"} for role in
            (haut_gauche, haut_droite, bas_gauche, bas_droite, pont) },
}
```

### 3. `gui.impedance_schematic` — labels + hitboxes (#1, #2, #3)

- `dessiner(...)` : étiquette d'une feuille = `ref` + `impedance.formater_valeur(value, type)`
  (au lieu de la valeur brute). Pas de hitbox (feuilles toujours simples).
- `dessiner_pont(pont, comps)` : pour chaque bras `{refs, composition}` :
  - **simple** (len(refs)==1) : symbole selon le type, label = `ref` +
    `formater_valeur` ;
  - **composite** (len>1) : boîte `elm.ResistorIEC`, label = `impedance.formater_expr(composition)`,
    et **hitbox** ajouté.
  - Les hitboxes composites sont stockés dans `fig._z_hitboxes` au format attendu par
    le handler : `(x0, x1, y0, y1, refs, composition)` (bbox de l'arête + marge).
  Renvoie la `fig` (avec `fig._z_hitboxes`).

### 4. `gui.impedance_view` — dessin du pont + clic (#1, #2)

Dans `_calculer`, quand `arbre is None` (pont/Y-Δ) :
- tenter `pont = impedance.detecter_pont(graph, a, b)` ;
- si `pont` : `fig = impedance_schematic.dessiner_pont(pont, graph.graph["components"])`,
  embarquer dans `schema_holder` via `FigureCanvasTkAgg`, et brancher un handler de
  clic qui lit `getattr(fig, "_z_hitboxes", [])` et appelle
  `circuit_viewer.show_dipole_detail(refs, composition, graph, {}, win)` ;
- sinon : message « pont non dessinable » (repli actuel).

La **vue d'îlot** n'a aucun changement : son `_on_click` lit déjà `fig._z_hitboxes`,
donc le drill-down du losange marche dès que `dessiner_pont` les pose.

## Gestion des cas limites

- Pont à bras simples : `refs` de longueur 1 → symbole normal, pas de hitbox (rien à
  déplier) — comportement identique à aujourd'hui, sauf labels formatés.
- Bras avec banc parallèle interne : réduit par `_passe_parallele` → composition
  `(…//…)` → boîte Z composite. OK.
- Réduction qui ne laisse pas un squelette 4/5 : `detecter_pont` → None → repli.
- `formater_valeur` sur valeur vide/illisible : "" ou valeur brute, jamais d'exception.

## Tests

`tests/test_impedance.py` :
- `formater_valeur` : 10k/R→"10 kΩ", 100n/C→"100 nF", 1m/L→"1 mH", 470/R→"470 Ω", ""→"".
- `detecter_pont` (mis à jour) : bras simples → `bras[role] == {"refs":[r],"composition":r}`.
- `detecter_pont` bras composite : un bras = R+C en série → `bras[role]["refs"]` contient
  les deux, `composition` = "R…+…". Toujours détecté comme pont.

`tests/test_impedance_schematic.py` :
- `dessiner_pont` avec un bras composite → figure OK et `fig._z_hitboxes` non vide ;
  avec bras tous simples → `fig._z_hitboxes` vide.

Suite complète verte (21 tests d'îlot + reste).

## Hors périmètre (futur)

- Collisions de labels en réseaux denses (placement adaptatif).
- Drill-down sur réseaux non-pont.
