# Design — Lisibilité des gros îlots (passe ciblée)

Date : 2026-06-19
Branche : `rewrite-simple`
Fichier principal : `gui/circuit_viewer.py`

## Problème

La vue d'îlot au niveau Impédance Z rend bien les petits îlots (≤ 5 dipôles :
colonne-bus propre, Z horizontaux, jonctions nettes). Au-delà, elle se dégrade.
Sur l'îlot dense `signal_conditioning.xml` → « Îlot 1 - comparaison » (23 unités,
16 Z), quatre défauts :

1. **Chevauchements d'étiquettes** : `Z2`/`Z3`, `D4`/`Z4`, `Z10`/`Z11` écrits les
   uns sur les autres.
2. **Labels de net collés aux symboles / AOP** : `NET12` mord sur Z6,
   `NET13`/`NET8` rentrent dans les triangles U2/U3.
3. **Disposition en escalier diagonal** : étalement en diagonale, vide en haut à
   gauche, fils très longs (D1, D3 traversent le vide jusqu'à AVCC).
4. **Densité** : 16 Z empilés rendent la figure haute et grêle.

## Cause racine

Dans `_build_island_schematic_plan`, chaque composant occupe sa propre ligne `y`
(décrément fixe `ROW_PITCH = 1.6`) **dans l'ordre du modèle**. Un Z 2-broches est
ensuite dessiné au milieu entre ses deux colonnes-bus. Des Z successifs relient des
paires de nets différentes (chaîne NET1→NET4→NET11→NET2…), donc leurs milieux `x`
dérivent vers la droite pendant que `y` descend → **diagonale**. Les collisions de
texte viennent du pas trop serré pour une étiquette `ref\nvaleur` avec alternance
haut/bas, et des labels de net posés sans marge.

La diagonale n'est donc pas un bug de dessin : c'est le **couplage entre l'ordre des
lignes et l'abscisse des colonnes**.

## Approche retenue : passe lisibilité ciblée (A)

Confinée à `_build_island_schematic_plan` / `_layout_columns` + quelques constantes.
Le moteur de dessin `_draw_*` et les hitboxes de drill-down restent intacts (sauf
ajout de marges `ofst` sur les labels). Pas de refonte en grille (option B écartée
par l'utilisateur), pas de simple cosmétique (option C jugée insuffisante).

### 1. Réordonner les lignes pour casser l'escalier

Avant l'assignation des `y` :

- **Partition** : `dipoles` (≤ 2 broches) vs `devices` (AOP / multi-broches, via
  `_is_multi_pin`).
- Pour chaque dipôle, calculer sa **clé de paire** =
  `tuple(sorted(nets de la ligne présents dans col_nets))` (0, 1 ou 2 nets-colonnes).
- Trier les dipôles par `(clé_de_paire, ref)`.
- Concaténer `devices` à la fin (ils partent déjà dans la voie dédiée `device_x`).

Effet : tous les Z reliant la **même paire de colonnes** deviennent contigus, donc
s'empilent **verticalement à la même abscisse** (même demi-distance entre les deux
colonnes) au lieu de dériver. L'alignement vertical d'une pile est invariant à
l'ordre des colonnes (une ligne reliant {A,B} est toujours dessinée entre la colonne
A et la colonne B) ; `_layout_columns` peut donc conserver son tri par `avg_y`.

### 2. Espacement adaptatif

Remplacer le décrément fixe par un pas calculé entre deux lignes voisines :

```
ROW_PITCH   = 2.0   # (était 1.6) — symbole 0.8 + bande label + marge
MULTI_PITCH = 3.4   # inchangé, autour d'un AOP/bloc
LABEL_LINE  = 0.5   # rallonge si une étiquette porte une valeur (2 lignes)

gap(prev, cur):
    si prev ou cur est multi-broches → MULTI_PITCH
    sinon → ROW_PITCH + (LABEL_LINE si prev a une valeur ou cur a une valeur)
```

**Abandon de l'alternance haut/bas** des labels de dipôles : avec le pas à 2.0 + le
regroupement, tous les labels passent en **haut** de façon cohérente. Marge :
label en haut (~y+0.5) vs symbole de la ligne au-dessus (~y+2.0−0.4) → ~1.1 d'air.

### 3. Marges des labels de net

- Labels de net de moignon (`loc="right"`) et de colonne (`loc="top"`) reçoivent un
  petit `ofst` pour se décoller du symbole/AOP voisin.
- Moignon E/S : longueur de fil constante avant le point étiqueté, pour que le texte
  ne retombe jamais sur le symbole suivant.

### 4. Canvas

Le regroupement compacte naturellement la figure. On conserve `set_aspect("equal")`
et le calcul de largeur sur le nombre de colonnes.

## Hors périmètre (assumé)

- Pas de routage des fils longs diode → alim (colonne la plus à droite) ; fil net,
  sans recouvrement → acceptable. Le routage serait la refonte grille (option B).
- `_draw_block_row` (AOP) modifié uniquement pour le `ofst` des labels de net.

## Tests

Les 10 tests de `tests/test_island_viewer.py` servent de filet. Évolutions :

- `test_opamp_symbol_and_rows_do_not_overlap` : écart minimal `≥ 1.5` → `≥ ROW_PITCH`
  (toujours vérifié).
- **Nouveau test** : les dipôles partageant une paire de colonnes sont contigus dans
  `plan["rows"]` et alignés en `x` une fois dessinés (vérifie l'anti-escalier).

## Vérification

1. `python -m pytest tests/test_island_viewer.py -q` vert.
2. `python -m pytest -q` (suite complète) vert.
3. Re-rendu de `signal_conditioning.xml` via `debug_render_ilots.py` : inspection
   visuelle de l'îlot dense → aucun texte chevauchant, piles de Z alignées, moins de
   diagonale.

## Contrainte projet

Aucun commit ne doit porter `Co-Authored-By Claude` (directive utilisateur).
