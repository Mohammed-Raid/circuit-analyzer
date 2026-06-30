# Transistors — dessin riche, sous-projet A : Z cliquables + titres de rôle

**Date :** 2026-06-25
**Statut :** approuvé

## Objectif

Donner aux montages transistor le début du traitement « riche » des AOP :
passifs en **boîtes Z cliquables** (drill-down R/L/C) et **titre de rôle** au-dessus
du montage. Inclut les **drawers manquants** des 3 montages récemment détectés.

## Portée (A uniquement)
- **Dans le périmètre :** drawers des 3 nouveaux types + passifs cliquables +
  titres de rôle, sur les drawers transistor existants.
- **Hors périmètre :** point de fonctionnement (sous-projet B), intégration
  vue chaîne/îlot connectée (sous-projet C), détection (déjà faite).

## Composants

### 1. Drawers manquants (enregistrés dans `_DRAWERS`)
- `_draw_suiveur_emetteur` — « Collecteur commun (suiveur d'émetteur) »
- `_draw_push_pull` — « Étage push-pull »
- `_draw_darlington` — « Paire Darlington »

Sans eux, `_circuit_principal_ilot` (qui n'accepte que les types présents dans
`_DRAWERS`) les ignore et l'îlot retombe sur la grille générique. Symboles réels
(BjtNpn / BjtPnp).

### 2. Passifs cliquables — helper `_z_passif`
`_z_passif(d, ref, ci, p1, p2, nom, label_loc="top")` : enveloppe un passif unique
dans `_z_box` (bloc `{refs:[ref], composition:ref}`) → hitbox cliquable, drill-down
R/L/C via `show_dipole_detail`. `_make_fig` arme déjà `_z_hitboxes`. Appliqué à
Rb / Rc / Re / Rg / charge dans : commutation BJT, émetteur commun, suiveur,
MOSFET commutation, MOSFET côté-haut, commande de relais, Darlington. (Miroir et
push-pull n'ont pas de R à envelopper.)

### 3. Titres de rôle
Étendre `_ROLE_ETAGE` avec les types transistor ; afficher le rôle au-dessus du
montage dans chaque drawer transistor.

## Critère de réussite
- « Collecteur commun (suiveur d'émetteur) », « Étage push-pull », « Paire
  Darlington » sont dans `_DRAWERS` et rendent sans « Schéma non disponible ».
- Chaque drawer transistor portant des passifs produit ≥ 1 boîte Z (hitbox).
- Le titre de rôle apparaît dans le rendu.
- Rendu PNG vérifié pour 2-3 montages.
- Suite de tests verte.
