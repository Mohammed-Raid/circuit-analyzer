# Refonte du pipeline : impédances Z comme briques de premier plan

**Date :** 2026-06-17
**Branche :** `rewrite-simple`
**Auteur :** Mohammed-Raid (directive du chef)

---

## 1. Contexte et motivation

Le chef demande de **repenser l'algorithme d'analyse**. Le principe :

> Commencer par traiter les composants **R, L, C**, les combiner en **série et
> parallèle**, et les simplifier en **impédances Z**. Une Z est à la fois une
> impédance *et* un sous-circuit. « Idem pour toute la carte. »

Cette directive prolonge l'annotation manuscrite en rouge du document de
référence (« montages Electroniques de base.doc », section 4 — sommateur) :
« il faut *créer* le dipôle Rf qui est en réalité peut-être complexe… chercher à
réaliser tous les sous-composants complexes entre le point − et Vs, − et Vi,
+ et Vs. Idem pour toute la carte. »

### État actuel (à remplacer)

- `circuit_analyzer/reduction.py` fait déjà une réduction série/parallèle, mais
  **timide** : uniquement les réseaux *ancrés* à un composant actif, et les Z
  sont **ré-expansés** aussitôt après la détection (invisibles dans le rapport).
- Les circuits passifs (filtre RC/LC, pont diviseur, snubber, découplage,
  fusible) sont détectés **séparément** sur la topologie d'origine, par 7
  détecteurs dédiés.

### Décisions validées lors du brainstorming

1. **Refonte complète du pipeline** : R/L/C réduits en Z *d'abord*, sur toute la
   carte ; la détection des montages actifs se construit *par-dessus* les Z.
2. **Approche A** retenue pour le moteur : réduction série + parallèle
   topologique (avec suivi des refs), pas de matrice d'admittance.
3. **Z générique seulement** pour le passif : plus de circuits passifs nommés
   (« Filtre RC passe-bas », « Pont diviseur »…). La Z, avec sa composition
   affichée (`R1+R2`, `R3//C1`), *est* le sous-circuit.
4. Les **montages actifs gardent leurs noms** (Amplificateur inverseur, etc.) ;
   ce sont eux qui consomment les Z.
5. **Un dessin par îlot** : visualisation graphique de chaque étage
   (organe actif + boîtes Z).

---

## 2. Objectifs / Non-objectifs

### Objectifs

- **But premier : éliminer les composants « non classifiés ».** Tout composant
  passif R/L/C devient au minimum une **Z singleton** (composition = sa propre
  ref). Plus aucun R/L/C ne reste orphelin : il est soit absorbé dans une Z
  composite, soit une Z singleton. La catégorie « non identifié » se vide.
- Réduire tout réseau passif R/L/C entre bornes en une impédance équivalente Z.
- Faire de Z un objet de première classe, affiché avec sa composition.
- Généraliser les détecteurs actifs pour qu'ils consomment des Z (donc
  reconnaître `Rf = R1+R2` ou `(R1+C)//R2` automatiquement).
- Afficher chaque îlot fonctionnel sous forme de schéma dessiné.

### Critère de succès

Après analyse, le rapport ne contient plus que : des **montages actifs nommés**,
des **circuits à diodes nommés**, et des **Z** (composites ou singletons). Le
seul résidu « non identifié » admissible est un composant d'un **type inconnu**
(ni R/L/C, ni actif `U`/`Q`/`M`/`K`, ni diode/fusible) — ce qui ne devrait pas
arriver sur une carte normale.

### Non-objectifs (YAGNI)

- Calcul **symbolique** de l'impédance (formule en jω). On garde la composition
  topologique lisible (`R1+R2`), pas `Z = R/(1+jRCω)`.
- Réduction **étoile→triangle** des ponts irréductibles (Wheatstone). Ils sont
  rares ; on les signale en bloc sans les réduire.
- Reclassifier une Z en nom de filtre (« passe-bas »…). Décision validée :
  Z générique.

---

## 3. Modèle de données — l'interface centrale

Une **impédance Z** est un dipôle équivalent entre deux bornes :

```python
{
  'id': 'Z1',                    # identifiant synthétique stable
  'noeuds': ('OUT', 'IN_MOINS'), # les 2 bornes (tuple ordonné)
  'refs': ['R1', 'R2'],          # vrais composants à l'intérieur (ordre préservé)
  'composition': 'R1+R2',        # expression lisible (série '+', parallèle '//')
  'type': 'R',                   # 'R' | 'C' | 'L' (homogène) ou 'Z' (mixte)
}
```

- `type` vaut le type commun si tous les composants sont homogènes, sinon `'Z'`.
- Une Z « singleton » (un seul composant non fusionné) garde `id` = sa vraie ref,
  `refs = [ref]`, `composition = ref` → le graphe réduit reste identique à
  l'original quand il n'y a rien à réduire (garantie de non-régression).

Le **graphe réduit** est un `MultiGraph` dont les arêtes sont des Z, entre
**bornes** uniquement.

### Bornes (nœuds jamais éliminés)

- broches d'un composant **actif / multi-broches** (AOP `U`, transistor `Q`/`M`,
  relais `K`) ;
- **rails** : GND, alimentation, terre de protection (PE) ;
- nœuds touchés par une **arête non réductible** (diode `D`, interrupteur…) ;
  le **fusible `F` est l'exception** : rendu transparent (voir §5), il ne fait
  pas borne ;
- **feuilles** : nœuds de degré 1 (entrées/sorties pendantes du circuit) ;
- jonctions d'un **pont irréductible** (degré ≥ 3 non décomposable en
  série/parallèle).

Tout autre nœud purement passif (degré 2, entouré de R/L/C) est éliminé.

---

## 4. Moteur de réduction (approche A)

Évolution de `reduction.py`. **Ordre imposé : série d'abord, puis parallèle**,
le tout itéré jusqu'à point fixe. On simplifie les chaînes série en un bloc, puis
on regarde ce qui est en parallèle *avec* ce bloc série, et on recommence — la
boucle capture les imbrications série/parallèle de proche en proche. Le résultat
final est une **Z** : un dipôle équivalent qui est aussi un **sous-circuit**
consommé par les grands montages (inverseur, intégrateur…).

### 4.1 Passe série (en premier)

Nœud interne `N` de **degré 2**, **non-borne**, avec deux voisins distincts
`a` et `b` → on retire `N` et on fusionne les deux arêtes en `expr_a+expr_b`
entre `a` et `b`.

**Changement clé vs. l'actuel :** on **autorise la fusion même quand un voisin
est un rail**. Conséquence : un filtre RC isolé `IN─R─MID─C─GND` devient
`Z = R+C` entre `IN` et `GND`. (Validé : « Z générique », on perd le nom
« filtre » ; la Z est le sous-circuit.) La seule protection restante est la
liste des **bornes** ci-dessus.

### 4.2 Passe parallèle (ensuite)

Arêtes multiples entre la même paire de bornes — y compris une arête issue d'une
réduction série de l'étape 4.1 et une autre qui lui est parallèle → fusion en
`(expr_a//expr_b//…)`. Le `type` reste homogène ou devient `'Z'`.

> La boucle `tant que (série puis parallèle) change` garantit qu'un motif comme
> `(R1+R2)//C1` est bien réduit : R1+R2 d'abord (série), puis `//C1` (parallèle).

### 4.3 Ponts irréductibles

Si, au point fixe, une composante connexe passive conserve des nœuds internes de
degré ≥ 3 (pont de Wheatstone), on ne la décompose pas : on l'émet comme une Z
unique de `type='Z'` listant tous ses `refs`, `composition` = `pont{R1,…,Rn}`.

### 4.4 Sortie

`reduire(graphe) -> graphe_reduit` où chaque arête porte un dict Z complet
(`id`, `refs`, `composition`, `type`). Plus de mécanisme de ré-expansion : les
détecteurs et le rapport travaillent directement sur les Z.

---

## 5. Détection des montages actifs (généralisée)

Les détecteurs de `detecteur.py` cherchent désormais une **Z (de n'importe quel
type)** là où ils cherchaient une arête de type `'R'` ou `'C'`.

- Helper `_voisins_de_type(graphe, noeud, type)` → remplacé/complété par
  `_impedances_sur(graphe, noeud)` qui renvoie les Z incidentes (avec l'autre
  borne et le dict Z).
- Exemple — **Amplificateur inverseur** : une Z entre `OUT` et `IN−` (feedback),
  une Z entre `IN−` et un nœud ≠ `OUT` (entrée). `Rf = R1+R2` reconnu d'office.
- Les détecteurs qui exigeaient un type précis (intégrateur = C en feedback ;
  dérivateur = C en entrée) testent désormais `z['type']` de la Z équivalente.
- `components` d'un match contient les **vraies refs** (via `z['refs']`), pour
  que verrouillage anti-vol, satellites et îlots fonctionnent inchangés.

### Détecteurs conservés

Tous les montages **actifs** (AOP : inverseur, non-inverseur, suiveur,
intégrateur, dérivateur, Schmitt, comparateur, différentiel, sommateur ;
transistors : commutation, émetteur commun, miroir, MOSFET haut/bas, relais).

Les circuits à **diodes** (pont redresseur, roue libre, ESD, redresseur simple,
détecteur de crête) sont **conservés** : la diode est non réductible, ce ne sont
pas des réseaux R/L/C, et ce sont des topologies nommées utiles.

> ⚠ **Décision provisoire — à confirmer avec le chef.** Il n'a pas encore
> tranché le sort des circuits à diodes. Défaut retenu en attendant : on les
> garde nommés. À revoir s'il veut les traiter autrement (les fondre en blocs,
> les supprimer, etc.). Ce choix est isolé : le revoir ne touche que la liste
> des détecteurs conservés, pas le moteur de réduction Z.

### Détecteurs supprimés (deviennent des Z)

`detecter_condensateur_decouplage`, `detecter_filtre_rc_passe_bas`,
`detecter_filtre_rc_passe_haut`, `detecter_filtre_lc`, `detecter_absorbeur_rc`,
`detecter_pont_diviseur`, `detecter_fusible`.

> **Fusible (`F`) supprimé** (le chef : « il ne sert à rien »). On ne le détecte
> plus *et* on ne le garde pas comme arête à part. Comme un fusible sain est
> électriquement un fil (~0 Ω), on le rend **transparent** : ses deux nœuds sont
> fusionnés avant la réduction, il disparaît du graphe. Aucune arête `F`
> orpheline ne subsiste (cohérent avec le but « zéro non classifié »).

---

## 6. Rapport et enrichissement

- Le rapport liste, par îlot : les **montages actifs nommés** + les **Z** avec
  leur composition et leurs bornes.
- `_enrichir()` : on retire les branches des 7 circuits passifs supprimés ; on
  ajoute une branche générique « Impédance Z » (composition, type, bornes,
  confiance neutre). Le calcul de fréquence de coupure RC/LC disparaît (plus de
  filtre nommé).
- **Panneau « non classifiés » (`_render_unclassified`) quasi vide** : puisque
  toute Z singleton est désormais un résultat à part entière, la passe
  satellites (`rattacher_satellites`) n'a plus de passif orphelin à recoller.
  On vérifie que ce panneau ne liste plus que d'éventuels types inconnus.

---

## 7. Visualisation : un dessin par îlot

Nouvelle vue, appuyée sur `circuit_viewer.py` (schemdraw).

- Un **drawer générique d'îlot** : place l'organe actif (AOP/transistor) au
  centre et dessine chaque Z incidente comme une **boîte rectangulaire
  étiquetée** (`Z1`, et la composition `R1+R2` en sous-titre). schemdraw rend
  une impédance générique par un rectangle — un seul drawer couvre tous les
  montages, au lieu d'un par type.
- Îlot **purement passif** : les Z dessinées entre leurs bornes (rails / E-S).
- Interaction : clic sur une boîte Z → détail de sa composition et de ses refs.
- Point d'entrée depuis le panneau « Structure en étages » (`tab_analyze.py`,
  `_IslandSection`) : un bouton « Voir le schéma » par îlot.

---

## 8. Plan de découpage (sous-projets)

Étroitement couplés autour du modèle de données (§3), mais livrables en ordre :

1. **Moteur de réduction Z** (`reduction.py` réécrit) + tests unitaires.
2. **Détecteurs généralisés** (`detecteur.py`) consommant des Z + suppression
   des 7 passifs + tests.
3. **Rapport / enrichissement** mis à jour.
4. **Dessin par îlot** (GUI) — dépend du modèle de données figé en 1-2.

---

## 9. Tests et non-régression

- Réduction : série pure, parallèle pur, mixte (`R+C`, `(R//C)`), ancrage aux
  bornes, filtre RC isolé → `Z=R+C`, pont irréductible signalé, circuit sans
  composite → graphe identique (refs/types/valeurs préservés).
- Détection : inverseur avec `Rf = R1+R2`, intégrateur avec C composite,
  montages classiques inchangés.
- Suppression : vérifier qu'un filtre RC isolé n'apparaît plus comme
  « Filtre RC passe-bas » mais comme Z.
- GUI : ouverture du schéma d'un îlot AOP + îlot passif sans erreur.
- Suite existante : adapter/retirer les tests des 7 détecteurs supprimés.

---

## 10. Risques

- **Régression de couverture** : des montages passifs auparavant nommés
  deviennent anonymes (accepté, décision §1.3).
- **Fusion trop agressive vers les rails** : valider que les ponts diviseurs
  *chargés* (milieu relié à une broche active) ne sont pas écrasés — protégés
  car le milieu est une borne.
- **Tests existants** nombreux à adapter (les 7 détecteurs supprimés).
