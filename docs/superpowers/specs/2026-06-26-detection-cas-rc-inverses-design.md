# Robustesse détection — Sous-projet 1 : cas RC « inverses »

**Date :** 2026-06-26
**Statut :** approuvé

## Problème

Deux topologies d'ampli à AOP sont aujourd'hui noyées dans « Amplificateur
inverseur (AOP) » alors qu'elles ont une fonction distincte (cf.
[[differentiel_integrateur_cas_rc_inverses]]) :

- **Zin = R∥C (parallèle), Zf = R** : gain DC fini + boost +20 dB/déc en HF
  (dérivateur partiel / passe-haut).
- **Zin = R, Zf = R+C (série)** : action intégrale en BF + proportionnelle en HF
  (correcteur PI / intégrateur réel).

Le détecteur d'inverseur les capture comme de simples Z (R-équivalentes), donc
elles perdent leur identité fonctionnelle.

## Objectif

Reclasser ces deux topologies sous des libellés explicites, sans régression sur
les montages existants (inverseur, dérivateur/intégrateur idéaux).

Libellés (choix « descriptif simple », vus dans l'app) :
- `"Ampli inverseur + boost HF (AOP)"`
- `"Ampli inverseur + action intégrale (AOP)"`

## Portée
- **Dans le périmètre :** détection des 2 topologies + libellés + rendu (boîtes
  Zin/Zf cliquables, réutilise le drawer inverseur) + rôles de chaîne.
- **Hors périmètre :** gain numérique chiffré ; autres combinaisons Zin/Zf
  exotiques ; variantes non-inverseuses ; nouveaux symboles de dessin.

## Composants

### 1. Helpers de structure (factorisation)
Extraire des sous-branches existantes de `_entree_capacitive` /
`_feedback_capacitif` (detecteur.py) :
- `_est_rc_serie(bloc, composants) -> bool` : composition = série de 2 feuilles
  {une R, une C}.
- `_est_rc_parallele(bloc, composants) -> bool` : composition = parallèle de 2
  feuilles {une R, une C}.

`_entree_capacitive` (branche réel) réutilise `_est_rc_serie` ;
`_feedback_capacitif` (branche leaky) réutilise `_est_rc_parallele`. Comportement
inchangé (refactor pur, couvert par les tests existants).

### 2. `detecter_derivateur_partiel(graphe)`
Même parcours d'arêtes que `detecter_amplificateur_inverseur` : sur IN-, une
arête vers la sortie (Zf) et une autre (Zin). Conditions :
- Zin (arête non-sortie) vérifie `_est_rc_parallele` ;
- Zf (arête vers OUT) est résistive (`_type_correspond(data,'R',inclure_z=True)`
  et **pas** capacitive).
Émet `circuit_type "Ampli inverseur + boost HF (AOP)"`, `impedances {Zin, Zf}`,
`gain "−Zf/Zin"`, `nodes [IN+, IN-, OUT]`, `components [aop]+Zf.refs+Zin.refs`.

### 3. `detecter_correcteur_pi(graphe)`
Symétrique :
- Zf (arête vers OUT) vérifie `_est_rc_serie` ;
- Zin (arête non-sortie) est résistive et **pas** capacitive.
Émet `circuit_type "Ampli inverseur + action intégrale (AOP)"`, mêmes clés.

### 4. Ordre de priorité (point de non-régression)
Insérer les deux détecteurs dans la liste des détecteurs **après**
dérivateur/intégrateur (idéaux), **avant** `detecter_amplificateur_inverseur`.
Justification : les idéaux (C seul) et leaky (R∥C feedback) ont des structures
distinctes → mutuellement exclusifs ; l'inverseur générique avalerait sinon les 2
nouveaux cas (il accepte les Z). La règle « un composant = un seul circuit »
(analyser) fait le reste.

### 5. Rendu (quasi gratuit)
- `gui/circuit_viewer.py` `_DRAWERS` : mapper les 2 types → `_draw_inverting_amp`
  (délègue à `_draw_aop_inverseur_zin_zf` quand `impedances` présent → Zin/Zf en
  boîtes Z cliquables).
- `_ROLE_ETAGE` : libellés courts, p. ex. `"+ boost HF"` et `"+ action intégrale"`.
- Aucune modif de `_dessiner_montage_a`/`_oy_for` : la branche `"Zin" in imp` les
  gère déjà (chaîne/îlot).

## Flux de données
graphe réduit → `detecter_derivateur_partiel` / `detecter_correcteur_pi`
(structure Zin/Zf) → match avec `impedances` → viewer rend via le drawer inverseur
existant (boîtes Z cliquables).

## Tests
- **Détection :** Zin=R∥C + Zf=R → « boost HF » ; Zin=R + Zf=R+C série → « action
  intégrale ».
- **Priorité / non-régression :** dérivateur idéal (C seul) reste dérivateur ;
  intégrateur idéal/leaky reste intégrateur ; inverseur R/R pur reste inverseur.
- **Helpers :** `_est_rc_serie` / `_est_rc_parallele` (vrais/faux cas), et
  `_entree_capacitive`/`_feedback_capacitif` toujours verts (refactor).
- **Rendu :** chaque nouveau type rend 2 boîtes Z (hitboxes) + libellé de rôle,
  sans « Schéma non disponible ».
- **Visuel :** PNG d'un « boost HF » et d'un « action intégrale » inspectés.

## Critère de réussite
- Les 2 topologies sont détectées sous leur libellé propre.
- Aucune régression sur inverseur / dérivateur / intégrateur (suite verte).
- Rendu cliquable vérifié (PNG).
