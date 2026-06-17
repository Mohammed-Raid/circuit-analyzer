# Design — Confort d'édition de l'éditeur de schéma

**Date :** 2026-06-17
**Portée :** A+B+C (redo, copier/coller/dupliquer, recentrer/ajuster). La sélection multiple (D)
est reportée à une étape isolée car elle restructure le modèle de sélection.

## Problème

L'éditeur n'a ni redo, ni copier/coller, ni recentrage. Refaire des composants identiques et se
repérer sur le canvas 2400×1800 est pénible.

## A — Redo (Ctrl+Y)

La pile d'annulation existe déjà. On factorise `_snapshot()` / `_restore()` et on ajoute une pile
`_redo_stack` :
- `_push_undo` empile l'état **et vide le redo** (toute nouvelle action le rend caduc).
- `_undo` pousse l'état courant sur le redo avant de restaurer.
- `_redo` fait l'inverse.

## B — Copier / coller / dupliquer (Ctrl+C / V / D)

Sur la sélection simple actuelle. Presse-papier = `{type, value, rotation}`.
- `_copy` mémorise le composant sélectionné.
- `_paste` crée une copie à la position du curseur (suivie dans `_on_motion`).
- `_duplicate` crée une copie décalée du composant sélectionné.
- Helper partagé `_add_comp(type, value, rotation, wx, wy)` (numérote la réf, dessine, sélectionne).
  Les opérations empilent l'annulation (annulables d'un coup).

## C — Recentrer / ajuster (touche F + bouton palette « ⊡ Ajuster »)

`fit_to_view()` : bbox de tous les composants → zoom = min(largeur, hauteur) borné [0.2, 3.0] →
`_redraw_all` → centre la bbox via `xview_moveto`/`yview_moveto`. Canvas vide → zoom 1.0 et retour
à l'origine.

## Gestion d'erreurs

- Coller/dupliquer un type devenu inconnu (`_add_comp` renvoie None) → l'instantané d'annulation
  inutile est dépilé.
- `fit_to_view` sur canvas non encore affiché → dimensions par défaut (800×600).

## Tests (Tk sauté sans affichage)

- Redo rétablit après undo ; une nouvelle action vide le redo.
- Copier/coller crée un 2e composant du même type ; coller annulable.
- Dupliquer crée un composant décalé.
- `fit_to_view` ne plante pas (zoom borné) ; canvas vide → zoom 1.0.

## Hors périmètre

- Sélection multiple, rubber-band, déplacement/suppression de groupe (étape D, séparée).
