# Reconnaissance de composants inconnus par la forme — Design

**Date :** 2026-07-20
**Branche cible :** `rewrite-simple` (suite du chantier Import ERetroDesign)

## Contexte et problème

L'import ERetroDesign (livré, commits `f290e56..059ecdd`) mappe les noms de
bibliothèque de l'éditeur C# vers nos types (R/C/L/D/Q/M/U…). Quand un
composant porte un nom que ni la table `_MAPPING_ERETRO` ni le catalogue de
puces ne connaissent, il tombe en **boîte noire (type X)** : ses broches et
sa connexité sont préservées, un avertissement est émis, mais il n'est pas
analysé (`circuit_analyzer/xml.py:1364-1376`).

Sur le corpus réel, ces inconnus ne sont pas une longue traîne : TestDiagram
compte **188× `Gate2`** et 2× `ICI1` sur ses 425 avertissements. Le boss ne
peut pas modifier l'éditeur C# (contrainte durable), donc toute amélioration
doit rester **100 % côté Python**.

Fait décisif vérifié : les fichiers `Lib/*.xml` de l'éditeur **ne portent que
de la géométrie** (segments, arcs, positions de broches), aucune sémantique
électrique. Le nom seul ne suffit donc pas. **Mais** cette géométrie voyage
aussi dans le fichier carte lui-même — chaque `DataItem` d'un BoardSCH
contient ses `datasegment`/`dataarc`/`datapin` (confirmé : SaveDiag = 22
segments + 8 arcs sur 6 composants ; TestDiagram = 1518 segments + 361 arcs
sur 285 composants). Le **dessin** est donc la seule information partagée qui
porte de quoi deviner le type — et il est déjà dans le fichier qu'on lit.

## Objectif

Ajouter un classifieur **géométrique** qui, pour un composant dont le nom est
inconnu, déduit son type à partir de la forme de son symbole, de façon
**conservatrice** : il ne type que sur une forme franche, s'abstient dès qu'il
y a ambiguïté, et ne rend donc jamais un composant sous un faux type (règle
boss « jamais de vue générique fausse »).

## Hors périmètre (non-goals)

- **Aucune modification côté C#** (l'éditeur ERetroDesign reste intouché).
- **Pas d'apprentissage / plus-proche-voisin** : règles écrites à la main,
  transparentes et corrigeables (décision boss). Le voisinage sur les Lib est
  écarté pour v1.
- **Pas de reconnaissance des formes ambiguës** entre familles proches (ex.
  transistor vs porte logique, tous deux à arc + 3 broches ; triangle d'AOP
  vs triangle de diode) : en cas de collision de features, on **s'abstient**
  (boîte noire), on ne devine pas.
- **Pas de nouveau drawer** : on ne classe QUE vers des types qui possèdent
  déjà un drawer dans l'app (porte, R, C, L, D), sinon on retomberait sur une
  vue générique — interdit.
- **Le dialecte `T…`/multi-chiffres** de TestDiagram (fils internes non
  résolus) reste un chantier séparé, non traité ici.

## Architecture — insertion dans la chaîne de mapping

La chaîne actuelle de l'Étape 5 de `lire_xml` est :

```
correspondance = _NOM_VERS_TYPE.get(nom) or eretro.mapper_nom(nom)
if correspondance is None: → boîte noire type X + avertissement
```

On insère un **troisième palier**, consulté uniquement si le nom est inconnu :

```
correspondance = (_NOM_VERS_TYPE.get(nom)
                  or eretro.mapper_nom(nom)
                  or eretro.classer_par_forme(features_geo, nb_broches))
```

Propriété : la forme n'est jamais consultée quand un mapping par nom réussit,
donc **non-régression totale** sur tout ce qui fonctionne déjà (dialecte
natif comme fichiers ERetroDesign déjà reconnus).

## Extraction des features géométriques

`lire_xml` ne lit aujourd'hui que les broches d'un `DataItem`. On ajoute, dans
`circuit_analyzer/eretro.py`, une fonction pure qui extrait de l'élément
`DataItem` (ou de sa géométrie déjà parsée) un jeu compact de features :

- `nb_broches` (déjà disponible)
- `nb_segments` (nombre de `DataSegment`)
- `nb_arcs` (nombre de `DataArc`)
- prédicats de forme dérivés des coordonnées des segments :
  - `paire_longs_paralleles` (deux longs segments parallèles rapprochés = plaques d'un condensateur)
  - `zigzag` (série de courts segments diagonaux alternés = corps de résistance)
  - `triangle_et_barre` (segments convergeant en pointe + barre transverse = diode)
  - `arc_avec_dos_droit` (un arc + un segment droit formant le dos = porte logique)
  - `bobine` (arcs répétés / demi-cercles en série = inductance)

Les features sont calculées en coordonnées **relatives / normalisées** (par
rapport à la boîte englobante du symbole) pour être indépendantes de l'échelle
et de la position sur la carte.

## Règles de classification (conservatrices)

`eretro.classer_par_forme(features, nb_broches) -> (type, plan) | None`.
~12 règles en ordre de priorité, chacune exigeant une correspondance nette et
un **nombre de broches cohérent** (le pin-count désambiguïse beaucoup) :

| Forme franche | Broches | → Type | Plan |
|---|---|---|---|
| `arc_avec_dos_droit` | 3 | porte logique (`U`/gate) | positionnel |
| `paire_longs_paralleles` | 2 | condensateur (`C`) | positionnel |
| `zigzag` (≥6 segments) | 2 | résistance (`R`) | positionnel |
| `triangle_et_barre` | 2 | diode (`D`) | A/K |
| `bobine` | 2 | inductance (`L`) | positionnel |

Toute entrée qui ne matche aucune règle nette, ou qui matche des features
contradictoires, retourne `None` → boîte noire (comportement actuel inchangé).
Les seuils exacts (longueur « longue », angle « diagonal », nombre de segments
d'un zigzag) sont fixés par TDD dans le plan, calibrés sur les vrais symboles.

## Garantie anti-erreur : oracle de test sur les Lib

Chaque `Lib/*.xml` a un nom de fichier qui **est** sa vérité terrain
(`resistance trad.xml` = résistance, `condo.xml` = condensateur,
`DIODE.xml` = diode, `Gate2.xml` = porte…). Test de propriété fort, exécuté
sur les ~50 symboles de la bibliothèque :

1. **Jamais de contresens** : pour chaque Lib dont le vrai type est connu,
   `classer_par_forme` retourne soit ce type, soit `None` (abstention) —
   **jamais un autre type**. C'est la garantie mesurable de la règle boss.
2. **Couverture des familles ciblées** : les symboles de porte / R / C / L / D
   sont bien reconnus (pas seulement « pas faux »).
3. En particulier, les symboles à collision potentielle (`npn`,
   `Transistor NPN`, AOP `TL084`…) ne doivent JAMAIS être classés porte ou
   diode : ils s'abstiennent (leur nom, lui, est déjà mappé par ailleurs).

`skipif` si le dossier `Lib/` est absent du poste (fichiers du boss, lecture
seule, jamais committés).

## Avertissements et traçabilité

Un composant typé par sa forme émet un avertissement **distinct** de l'inconnu
pur, ex. : `Composant 'Gate2' (id=…) typé par sa forme (dessin) → traité comme
PORTE`. Ainsi l'utilisateur voit dans le bandeau ce qui a été deviné, peut le
vérifier, et le fige définitivement en ajoutant une ligne à `_MAPPING_ERETRO`
s'il le souhaite (le mapping par nom reste prioritaire sur la forme).

## Boucle visuelle (exigence boss)

Après implémentation : rendre en PNG les composants nouvellement reconnus
(en particulier les `Gate2` de TestDiagram, désormais dessinés en portes
logiques) et les inspecter — pas seulement des tests verts. Canvas des schémas
clair, aucune vue générique.

## Contraintes de projet (rappel)

Commits en français sans footer Claude ; jamais `git add -A` ; `docs.rar` et
`SolutionERetroDesignX20260813/` en lecture seule, jamais committés ;
`PYTHONUTF8=1` devant python/pytest ; schemdraw pinné ==0.22 ; suite complète
verte par tâche ; boucle visuelle après toute modif d'affichage.

## Découpage prévisionnel (le plan détaillera en tâches TDD)

1. Extraction des features géométriques depuis un `DataItem` (fonction pure + tests).
2. `classer_par_forme` : les règles conservatrices + l'oracle de test sur les Lib.
3. Branchement dans `lire_xml` Étape 5 (palier forme) + avertissement dédié + non-régression.
4. Intégration corpus (TestDiagram : Gate2 → portes) + boucle visuelle PNG + bandeau.
