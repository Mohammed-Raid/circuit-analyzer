# Design — Composants étendus, palette synchronisée, doublon de pattern

**Date :** 2026-06-17
**Portée :** trois fonctionnalités liées autour des composants et des patterns.

## Contexte

- L'éditeur de schéma utilise un `COMP_DEFS` global figé (géométrie : couleur, taille, positions
  de broches). Il ne connaît que 7 types (R, C, L, D, Q, U, K) + GND/VCC.
- L'analyseur reconnaît 11 types via `TYPES_COMPOSANTS` : R, C, L, D, **F**, Q, **M**, U, **T**, K, **SW**.
- L'onglet Composants édite une bibliothèque JSON (`{préfixe: {name, pins[]}}`, sans géométrie). À la
  sauvegarde/suppression il appelle `on_save` → ne rafraîchit que l'onglet Circuits.
- La création de pattern manuelle (`TabCircuits._sauvegarder`) n'a aucun contrôle de doublon de nom.

## Partie 1 — Standards manquants dans la palette

Ajouter à `COMP_DEFS` (éditeur) F, M, T, SW avec broches identiques à `TYPES_COMPOSANTS` :

| Type | Nom | Broches | Géométrie |
|---|---|---|---|
| F | Fusible | 1, 2 | 80×40, ambre `#f59e0b`, défaut « 1A » |
| M | MOSFET | G, D, S | 60×80, violet `#a855f7`, défaut « IRF540 » |
| T | Transfo | P1, P2, S1, S2 | 80×60, bleu `#0ea5e9` |
| SW | Interrupteur | 1, 2 | 80×40, émeraude `#10b981` |

`_trouver_type` gère déjà les préfixes 3→2→1 lettres, donc `SW1` → type `SW`.

## Partie 2 — Synchronisation bibliothèque → palette de l'éditeur

1. **`_auto_def(nom, pins)`** (fonction module) : génère une géométrie générique pour un type sans
   dessin sur-mesure — boîte 80 de large, broches réparties moitié gauche / moitié droite, couleur
   neutre `#94a3b8`, hauteur selon le nombre de broches. La branche `else` du moteur de rendu dessine
   déjà ce cas.
2. **Defs par instance** : `self._defs = {**COMP_DEFS, **types_perso_générés}`. Toutes les lectures
   `COMP_DEFS[...]` dans les méthodes deviennent `self._defs[...]` (~13 sites). La globale reste la
   base des types intégrés.
3. **`_compute_defs()`** : `charger_bibliotheque()` (déjà fusionnée intégrés+perso) → pour chaque type
   absent de `COMP_DEFS`, ajoute `_auto_def(...)`.
4. **`refresh_palette()`** sur l'éditeur : recadre `self._defs`, **retire du canvas les composants
   d'un type devenu inconnu** (+ leurs fils), vide la pile d'annulation (un instantané pourrait
   contenir un type disparu), reconstruit les boutons de palette, redessine.
5. **Câblage `app_window`** : le callback de l'onglet Composants appelle `tab_c.refresh_component_list`
   **et** `tab_d.refresh_palette`. `TabDraw.refresh_palette()` délègue à l'éditeur.

### Gestion d'erreurs

- Suppression d'un type encore posé sur le canvas → retrait des composants concernés (choix validé,
  alternative « bloquer » écartée).
- `charger_bibliotheque` en échec → bibliothèque vide, palette = seuls les intégrés.
- Type perso sans broches → ignoré (non plaçable).

## Partie 3 — Doublon de pattern à la création

Dans `TabCircuits._sauvegarder`, avant d'ajouter : si le nom existe déjà (parmi les circuits intégrés
`NOMS_CIRCUITS` ou les personnalisés, hors celui en cours d'édition) → `showinfo` « existe déjà » et
on n'ajoute pas. Sinon ajout normal. Le `PatternWizard` fait déjà ce contrôle côté assistant.

## Tests

- `_auto_def` : 2 broches → gauche/droite ; 4 broches → 2+2 ; clés = noms de broches.
- Netlist : un `SW` placé s'exporte et se relit comme type `SW`.
- Sync palette : créer un type perso → bouton présent dans `_palette_btns` de l'éditeur ; le
  supprimer → bouton retiré et composant éventuel purgé du canvas (sur le modèle de
  `test_gui_sync.py`, sauté sans affichage Tk).
- Doublon de pattern : `_sauvegarder` avec un nom existant n'ajoute rien.
- Les 337 tests existants restent verts.

## Hors périmètre

- Modifier la géométrie de U (3 broches dans l'éditeur vs 5 dans `TYPES_COMPOSANTS`) — inchangé.
- Éditeur de géométrie sur-mesure pour les composants perso (positions/couleur manuelles).
