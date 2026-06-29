# Robustesse détection — Sous-projet 3 : cascade DC (couplage direct)

**Date :** 2026-06-29
**Statut :** approuvé

## Problème

Une cascade à couplage direct (collecteur de Q1 = base de Q2, sans résistance
de base ni condensateur de liaison) **perd le 2e transistor** dans la vue îlot.

Cause : `detecter_amplificateur_emetteur_commun` exige une résistance de base
(`r_base`). Q2 n'en a pas, donc le détecteur emprunte `Rc1` (sur le net
collecteur1 = base2) comme fausse résistance de base. La règle « un composant =
un seul circuit » attribue ensuite `Rc1` à Q1, invalide le match de Q2, et Q2
disparaît — exactement la « vue générique / composant en vrac » proscrite.

## Objectif

Détecter l'étage couplé en DC comme un émetteur commun à part entière, sans
voler le `Rc` de l'étage précédent, pour que les deux étages se dessinent en
chaîne via la machinerie existante.

## Composant unique : détection de base couplée DC

Dans `detecter_amplificateur_emetteur_commun`, avant la décision :

- Construire l'ensemble des nets collecteurs des **autres** transistors.
- Si le net de base de l'étage courant ∈ cet ensemble → **base couplée DC** :
  - détecter en émetteur commun dès que `r_collecteur` existe, **sans exiger ni
    inclure** de résistance de base (le R présent est le `Rc` de l'étage amont) ;
  - `components = [Q] + r_collecteur` (aucune résistance de base récupérée).
- Sinon : comportement inchangé (`r_collecteur and r_base`).

Le libellé reste « Amplificateur émetteur commun ». Aucun nouveau type, drawer
ni enregistrement : le rendu en chaîne (`_ordonner_montages_flux` +
`_make_chain_fig`) dessine la cascade. Validé :
`[['Q1','Rc1','Rb1'], ['Q2','Rc2']]`.

## Pourquoi le risque de régression est quasi nul

Le déclencheur est purement topologique (« mon net de base est le collecteur
d'un autre transistor »). Pour tout circuit qui n'est pas une vraie cascade DC,
la branche n'est jamais prise → comportement identique.

## Hors périmètre
- Couplage inter-étage **résistif** (Rb2 entre collecteur1 et base2).
- Cascades de plus de 2 étages.
- Couplage AC / condensateur de liaison.

## Tests
- **Détection :** cascade DC pure → Q2 détecté en émetteur commun couplé DC,
  `components` de Q2 = `[Q2, Rc2]` (ne contient pas `Rc1`).
- **Non-régression :** émetteur commun simple (vrai Rb) inchangé ; CE à pont
  diviseur (Rb vers rail) inchangé ; Darlington inchangé.
- **Rendu îlot :** les 2 transistors présents, chaîne formée, pas de « Schéma
  non disponible ».
- **Visuel :** un PNG de la cascade inspecté.

## Critère de réussite
- Q2 n'est plus perdu ; la cascade DC se dessine en 2 étages chaînés.
- Suite verte, aucune régression sur CE simple / Darlington.
