# Disposition canonique sur cartes scannées — Design

**Date :** 2026-08-11
**Statut :** design validé en conversation, prêt pour le plan d'implémentation.

**Suite de :** [2026-08-10-disposition-canonique-montages-detectes-design.md](2026-08-10-disposition-canonique-montages-detectes-design.md)
— ce chantier étend la disposition canonique (déjà livrée pour l'ampli
inverseur côté `generer_xml`/netlist) au chemin patch-en-place
(`eretro_patch.ecrire_groupes`), utilisé pour les VRAIES cartes scannées.

## Contexte (pourquoi)

Le chantier précédent a livré la disposition canonique (Zin/AOP/Zf) mais
UNIQUEMENT sur le chemin `generer_xml` (analyse partie d'une netlist, sans
fichier XML source). Sur le chemin réel (analyse partie d'un `.xml` scanné),
l'export passe par `eretro_patch.ecrire_groupes`, qui — par conception
délibérée et documentée comme non négociable — ne déplace JAMAIS rien : il
ne fait que poser les tags de groupe (`GpId`/`Begrp`/`GRPS`).

Le boss veut maintenant que les groupes reconnus soient AUSSI disposés
canoniquement sur une vraie carte scannée. Décision explicite : c'est une
exception délibérée à la règle « jamais déplacer une carte reçue », limitée
aux composants d'un groupe reconnu — le reste de la carte (composants non
reconnus, satellites) garde ses positions réelles intactes.

## Décisions verrouillées (clarifications en conversation)

| Question | Décision |
|---|---|
| Casser la règle « jamais déplacer » ? | Oui, mais UNIQUEMENT pour les composants strictement identifiés par rôle (aop/Zin/Zf) d'un groupe reconnu et migré. Tout le reste de la carte (satellites inclus) garde sa position réelle. |
| Ancrage de la disposition | Centrée sur le CENTROÏDE RÉEL actuel du groupe (moyenne des positions scannées), pas une origine arbitraire — minimise le risque de chevaucher un composant réel voisin non déplacé. |
| Rotation | Aucune — translation pure. On ne touche jamais `<angle>`. Choix qui élimine tout le risque de fils désynchronisés d'un symbole tourné (cf. bug déjà rencontré et corrigé côté `generer_xml`). |
| Mécanisme géométrique | Translation, pas reconstruction depuis un catalogue de formes. Une carte réelle a déjà sa propre géométrie de broches (`<datapin><Pin><X>/<Y>` — RELATIF à `<CtrIem>`, vérifié sur `exemples/carte pour tester.xml`) — décaler `<CtrIem>` suffit, les broches suivent automatiquement. Pas besoin de `_FORME`/`_ALIAS` (catalogue utilisé uniquement par la fabrication, `Composant` côté lecture ne porte aucune info de forme). |
| Fils | `<Line><LP><PointF>` est en coordonnées ABSOLUES (vérifié). Chaque fil touchant un composant déplacé doit avoir SON extrémité décalée du même delta que ce composant — l'autre extrémité (composant non déplacé) reste intacte. |
| Satellites | Jamais déplacés dans cette première version — seuls aop/Zin/Zf (rôles stricts) bougent. Le placement en grille utilisé côté `generer_xml` pour les satellites n'a pas de sens sur une carte dense déjà peuplée. |
| Connectivité | Garantie par construction : `CFirst`/`CLast` (quel fil relie quelles broches) n'est jamais modifié, seules des coordonnées bougent — même garantie que le chantier précédent, pas de nouveau test de robustesse requis sur ce point (mais un test de non-régression reste utile). |
| Montage(s) concerné(s) | Amplificateur inverseur uniquement, même périmètre que le chantier précédent — pas d'extension à d'autres montages dans ce chantier. |

## Architecture

### Où ça s'accroche

`eretro_patch.ecrire_groupes` appelle déjà `_grouper_par_circuit` (import
existant depuis `circuit_analyzer.xml`), qui — depuis le chantier précédent
— peuple déjà `bloc.roles` (aop/Zin/Zf) pour l'ampli inverseur. Cette info
existe donc déjà en mémoire à l'endroit exact où le patch s'exécute ; elle
n'est aujourd'hui utilisée que pour nommer le groupe (`getattr(b, "label", ...)`).

### Nouvelle fonction : `_deltas_disposition_canonique(source, bloc)`

Nouveau, dans `eretro_patch.py` (ou un module sœur `circuit_analyzer/eretro_disposition.py`
si `eretro_patch.py` devient trop chargé — à trancher dans le plan) :

1. Si `bloc.label` n'est pas dans `_POSITIONNEURS_PAR_MOTIF` (import depuis
   `circuit_analyzer.xml`) OU `bloc.roles` est vide : renvoyer `{}` (aucun
   déplacement) — même garde que le chemin `generer_xml`, aucune régression
   possible sur les montages non migrés.
2. Lire les positions RÉELLES actuelles des refs de rôle
   (`source.elements[ref].find("CtrIem/X").text`, etc.) — uniquement pour
   les refs de `bloc.roles` (aop/Zin/Zf), jamais les satellites.
3. Calculer le centroïde réel de ces positions.
4. Appeler `_positionner_amplificateur_inverseur(comps_de_role, bloc.roles, x, y)`
   avec `(x, y)` choisi pour que le centre de la disposition canonique
   coïncide avec le centroïde réel (pas l'origine bloc-grille habituelle).
5. Pour chaque ref de rôle : `delta = (nouvelle_x - x_reelle, nouvelle_y - y_reelle)`.
   Une ref dont la position canonique est déjà sa position réelle (delta nul)
   n'a rien à faire.
6. Renvoyer `{ref: (dx, dy)}`.

### Application des deltas

Nouvelle fonction `_appliquer_deltas(source, deltas)` :
- Pour chaque `ref, (dx, dy)` : lit `<CtrIem><X>/<Y>` actuels sur
  `source.elements[ref]`, écrit `x+dx, y+dy` via `_ecrire` (déjà existant,
  tags déjà présents sur toute carte réelle — vérifié).
- Pour chaque ligne de `source.lignes` (via `source.lignes_refs`) : si
  `ref_a` a un delta, décaler le PREMIER `PointF` de `<LP>` ; si `ref_b` a
  un delta, décaler le SECOND. Un fil entre deux refs de rôle voit ses DEUX
  extrémités décalées, chacune de son propre delta.
- Ne touche jamais `<angle>`, jamais `<datapin>` (les broches suivent
  `<CtrIem>` automatiquement, coordonnées relatives).

`ecrire_groupes` appelle ces deux fonctions pour chaque bloc, juste après
avoir calculé `blocs` — avant l'écriture des groupes elle-même (l'ordre
n'a pas d'importance fonctionnelle, mais écrire les positions avant les
`<GRPS>` permet à `_rectangle()` de calculer le cadre du groupe sur les
positions DÉJÀ déplacées).

## Gestion d'erreurs

Même philosophie fail-soft que le reste du projet :
- Ref de rôle absente de `source.elements` (dialecte inattendu) : ignorée,
  pas de crash — même logique que `_appliquer` pour `GpId`.
- `<CtrIem>` ou `<Line><LP>` incomplet/malformé sur un composant ou fil
  réel : ce composant/fil est laissé intact, averti en log, jamais de
  levée d'exception qui bloquerait tout l'export.
- Aucune vérification de collision avec un composant non déplacé dans
  cette première version (ancrage au centroïde réel est le seul garde-fou
  retenu) — à revisiter si l'inspection visuelle sur cartes réelles montre
  des chevauchements problématiques.

## Tests

- Unitaires sur `_deltas_disposition_canonique` : positions réelles
  synthétiques, vérifie que le delta ramène bien vers la disposition
  canonique centrée sur le centroïde d'entrée.
- Unitaires sur `_appliquer_deltas` : composant + fil synthétiques,
  vérifie `<CtrIem>` ET l'extrémité de fil correspondante décalées du même
  delta, l'autre extrémité intacte.
- Non-régression : la suite existante sur `ecrire_groupes` (montages non
  migrés, cartes sans ampli inverseur) ne doit rien changer.
- Bout en bout sur un fixture réel contenant un ampli inverseur
  (`exemples/carte pour tester.xml` ou équivalent dans
  `circuits_industriels/`) : patcher, reparser, vérifier que la
  connectivité (mêmes broches, mêmes appartenances de net) est identique
  à l'original — même contrat que le chantier précédent.
- Visuel : rendre le résultat en PNG (réutiliser/étendre
  `tools/render_boardsch_layout.py`) et l'inspecter, avant/après, sur au
  moins un fixture réel.

## Points ouverts pour le plan d'implémentation

- `eretro_patch.py` vs nouveau module sœur pour les deux nouvelles
  fonctions — trancher selon la taille que ça prend une fois écrit.
- Ordre exact d'appel dans `ecrire_groupes` (avant ou après la boucle
  `_appliquer`/`GpId` existante) — vérifier qu'aucune des deux ne dépend
  de l'autre avant de figer.
- Choix du fixture réel de test bout-en-bout (lequel des fichiers sous
  `exemples/`/`circuits_industriels/`/`CARTE POUR TESTER (VRAI TEST)/`
  contient un ampli inverseur détectable).
