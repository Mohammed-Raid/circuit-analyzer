# Détection du suiveur d'émetteur (corriger le faux positif émetteur commun)

**Date :** 2026-06-25
**Statut :** approuvé

## Problème

Un suiveur d'émetteur (collecteur commun : collecteur sur VCC, sortie sur
l'émetteur via Re) est **mal classé en « Amplificateur émetteur commun »**.
`detecter_amplificateur_emetteur_commun` n'exige qu'« une R sur le net collecteur
ET une R sur le net base » ; comme le collecteur EST VCC, la R de polarisation
base→VCC compte comme R-collecteur → faux positif. Le collecteur directement sur
un rail n'est jamais exclu.

## Fix (2 parties)

1. **Durcir l'émetteur commun** : dans `detecter_amplificateur_emetteur_commun`,
   ignorer le transistor si `est_alimentation(collecteur)` (collecteur sur rail).
   Un vrai émetteur commun a son Rc entre le rail et le collecteur → le collecteur
   est un nœud interne. Le test canonique (C=NCOL) reste valide.

2. **Nouveau `detecter_suiveur_emetteur(graphe)`** : transistor Q avec
   `est_alimentation(collecteur)`, émetteur non masse, et une R de l'émetteur vers
   GND (Re). `circuit_type = "Collecteur commun (suiveur d'émetteur)"`,
   `components = [Q, Re, (+ R de base si présente)]`, `nodes = [base, collecteur,
   emetteur]`. Exposé via un pattern `SuiveurEmetteur` ajouté à
   `TRANSISTOR_PATTERNS` **avant** `CommonEmitterAmp`.

## Critère de réussite
- Suiveur d'émetteur (C=VCC, Re émetteur→GND) → « Collecteur commun (suiveur
  d'émetteur) », et PLUS « Amplificateur émetteur commun ».
- Émetteur commun canonique (C=NCOL, Rc rail→collecteur, Rb) → toujours
  « Amplificateur émetteur commun » (non-régression).
- Suiveur sans Re vers GND → non détecté.
- Suite de tests verte.

## Hors périmètre
Push-pull, Darlington, source de courant (autres trous de l'audit) — phase
suivante éventuelle. Aucun travail de *dessin* ici (détection uniquement).
