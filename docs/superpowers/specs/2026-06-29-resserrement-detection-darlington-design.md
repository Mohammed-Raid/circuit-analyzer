# Robustesse détection — Sous-projet 2 : resserrement Darlington

**Date :** 2026-06-29
**Statut :** approuvé

## Problème

`detecter_darlington` (detecteur.py:890) ne teste que `E(Q1)==B(Q2)` et que
`E(Q1)` n'est pas un rail. Tout circuit où l'émetteur de Q1 attaque la base de
Q2 est étiqueté « Paire Darlington », même si Q1 est en réalité un étage
amplificateur autonome (collecteur chargé) — faux positif.

Aujourd'hui le corpus ne contient que 3 cas, tous légitimes : le resserrement
est **préventif**, pas correctif.

## Objectif

Ajouter une condition structurelle qui rejette les faux E1→B2 sans reclasser
aucun cas existant ni toucher au rendu.

## Composant unique : garde-fou collecteur

Dans `detecter_darlington`, en plus des conditions actuelles, exiger :

> **`Q1.C` est une alimentation OU `Q1.C == Q2.C`.**

Justification :
- Dans une vraie Darlington, le collecteur de Q1 est lié au collecteur composite
  → soit un rail (forme follower / CE actuelle), soit le nœud collecteur commun.
- Si `Q1.C` est un net signal quelconque (≠ rail, ≠ Q2.C), Q1 a sa propre charge
  de collecteur → c'est un étage CE autonome, donc une cascade 2-étages, pas un
  composant Darlington.

Couverture :
- `tr_paire_darlington`, `ilot_chaine_darlington_ce` (Q1/Q2), `ilot_reel_darlington_relais_rlc` : `Q1.C=VCC` → passent (clause rail).
- Composite CE à collecteurs communs sur charge (sans rail) : `Q1.C==Q2.C` → passent (clause égalité).
- Faux positif (Q1 = CE autonome, `Q1.C` signal ≠ Q2.C) → rejeté.

## Hors périmètre
- Polarité NPN/PNP : le modèle `Composant` ne porte que `type='Q'`, impossible à
  exprimer. Explicitement abandonné.
- Rendu / drawers : les deux formes se dessinent déjà correctement (vérifié cette
  session). Aucune modif.
- Cascades DC C1→B2 : structure distincte, sous-projet 3.

## Tests
- **Non-régression :** les 3 fixtures existantes restent « Paire Darlington ».
- **Nouveau (négatif) :** cascade synthétique où Q1 est CE autonome
  (`Q1.C` = net signal avec Rc vers VCC, `E1→B2`) → **non** détecté Darlington.

## Critère de réussite
- Le faux positif est rejeté, les 3 cas réels restent détectés.
- Suite verte, aucun changement de rendu.
