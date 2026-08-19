# Connectivité des vias — Design

**Date :** 2026-08-17
**Statut :** livré. Implémenté dans `circuit_analyzer/xml.py::lire_xml` ;
3 nouveaux cas + 1 garde-fou dans `tests/test_eretro_nouveau_format.py`
(23/23 passent) ; suite complète 2348 passés / 15 échecs (mêmes 15,
préexistants, vérifiés inchangés avant/après ce chantier — non liés aux
vias) ; boucle visuelle faite (filtre RC coupé par un via → R1+C1 regroupés
en une seule Impédance Z, rendu PNG inspecté, aucune anomalie).

## Context (pourquoi)

Le boss utilise l'éditeur C# pour dessiner un schéma, l'analyse avec cette
appli Python, puis récupère le résultat (schéma canonique / rapport) dans
l'éditeur C#. Sur les vraies cartes, deux fils qui semblent électriquement
reliés passent souvent par un **via** (liaison Top/Bottom, posé par
l'éditeur C# — voir `ERetroDesign/Via.cs`).

`lire_xml` (Union-Find sur les broches) ignore aujourd'hui totalement
`<Vias>` : confirmé par le cas de test `05_via` (`tests/test_eretro_nouveau_format.py`),
dont le commentaire dit explicitement *« la fusion par via reste à faire
quand le collègue la câblera côté C# »* — et le collègue l'a câblée
(chantier 2026-08-13 côté C# : un fil peut démarrer/finir SUR un via). Sans
ce chantier, un filtre RC (ou n'importe quel motif) coupé par un via au
milieu est vu comme DEUX nets disjoints → mauvaise détection, ou détection
manquée.

**But :** un via qui touche N fils (par coïncidence géométrique exacte de
position, pas par nom) doit fusionner ces N fils dans le même net électrique
— exactement comme une jonction fil-sur-fil (marque `999999`) fusionne déjà
plusieurs fils au même point aujourd'hui.

## Comment un via se raccorde côté C# (contrat, ne pas réinventer)

Confirmé en lisant `Forms/Form1.cs` (`DwLine`/`EndLine`) : un fil qui
démarre ou finit sur un via n'a **aucune référence formelle** à ce bout
(`CFirst`/`CLast` = `null`) — la seule trace est **géométrique** : le
premier ou dernier point de `<LP><PointF>` du fil est posé exactement à
`<Via><Pos>` (`vLine.LP.Add(new PointF(via.Pos.X, via.Pos.Y))`, copie
directe, pas d'arrondi séparé). Donc : la connexité via se résout en
comparant la position d'un bout de fil non résolu à la position de chaque
via, PAS par le champ `<Net>` du via (qui est un simple libellé utilisateur
optionnel — le cas `05_via` a deux vias avec le même `<Net>N1</Net>` et
AUCUNE fusion attendue entre eux tant qu'aucun fil ne les touche : la preuve
que `<Net>` n'est pas le mécanisme électrique).

## Non-goals (v1)

- Ne PAS fusionner deux vias entre eux par simple égalité de `<Net>` — ce
  n'est pas le contrat C#, voir ci-dessus.
- Ne PAS toucher `Top`/`Bottom` (chantier séparé, prochaine étape annoncée
  au boss — un via relie déjà les deux côtés par définition, mais la
  distinction de couche pour le reste des fils reste un problème différent).
- Ne PAS toucher `eretro_patch.py` / le retour fidèle : `<Vias>` traverse
  déjà intact (aucune écriture dessus), donc le round-trip C#→Python→C# n'a
  besoin d'aucun changement là-dessus.
- Ne PAS ajouter de représentation du via dans les `Composant` retournés
  (pas un composant électrique au sens du graphe — un point de fusion pur,
  même traitement qu'une jonction).

## Architecture

Tout dans `circuit_analyzer/xml.py::lire_xml`, en étendant l'Union-Find déjà
en place (mécanisme identique à celui qui fusionne déjà les jonctions
fil-sur-fil et les étiquettes de réseau — pas de nouvelle structure).

1. Nouvelle étape, juste avant la boucle `for idx_fil, fil in
   enumerate(lignes_xml)` : lire `.//Vias/Via`, construire un index
   `{(round(x), round(y)): idx_via}` (les positions sont des entiers côté
   C#, `round()` absorbe le bruit flottant XML sans tolérance ad hoc).
2. Dans la boucle des fils : quand `resoudre_extremite(cf)` (ou `cl`) rend
   `None` **et** que la référence brute est vide (signature d'un bout
   via — jamais un bout de broche mal formé, qui lui porte toujours une
   chaîne), chercher le premier/dernier point de `<LP><PointF>` du fil dans
   l'index des vias. Si trouvé → ce bout devient le nœud synthétique
   `('via', idx_via)`, réutilisé tel quel par `unir()`/`trouver()` (l'Union-
   Find n'est pas typé, une clé `('via', n)` fonctionne exactement comme une
   clé `(cid, pidx)` — aucune modification de l'algorithme lui-même).
3. Deux fils qui touchent le MÊME via se retrouvent donc unis transitivement
   par ce nœud commun, sans jamais apparaître dans `groupes_nets` (qui
   n'itère que les broches réelles de `elements`) — le via est un pur point
   de fusion, invisible en sortie, comme une jonction.
4. Effet de bord correct : le faux avertissement *« Fil non résolu »*
   actuellement émis pour CHAQUE fil connecté à un via (son bout via ne
   résout jamais) disparaît pour les bouts qui matchent effectivement un
   via — un vrai fil non résolu (aucun via à cette position) continue de
   l'émettre normalement.

## Tests

- **Unité (`tests/test_eretro_nouveau_format.py`)** :
  - Étendre `_carte`/`_fil` si besoin pour émettre `<LP><PointF>` (absent
    aujourd'hui des fixtures compactes — nécessaire ici puisque le
    mécanisme est géométrique).
  - Nouveau cas : deux résistances, fil A relie R1 à un via V, fil B relie
    V à R2 → même net attendu (R1.2, R2.1), comme `01_base_simple`.
  - Cas jonction-par-via en chaîne (3 fils qui touchent le même via) → tous
    au même net, même patron que `09_jonction_chaine`.
  - Non-régression `05_via` : toujours `[]` (vias posés, aucun fil ne les
    touche encore) — ne doit PAS changer.
  - Deux vias distincts, même `<Net>`, aucun fil ne les relie → toujours
    PAS de fusion entre eux (garde-fou anti-régression explicite du non-goal
    ci-dessus).
- **Oracle corpus réel** : si des vias existent dans `CARTE POUR TESTER
  (VRAI TEST)/`, vérifier que la lecture ne régresse pas (nombre d'inconnus,
  zéro type invalide) — lecture seule, `skipif` si dossier absent (patron
  déjà en place pour les autres oracles).
- **Boucle visuelle** : construire un petit schéma réel (filtre RC coupé en
  deux par un via) côté fixture, faire tourner la détection de bout en bout,
  confirmer que « Filtre RC passe-bas » est maintenant détecté (il ne
  l'était pas avant ce chantier), et rendre le résultat pour inspection
  visuelle (PNG regardé, jamais committé).

## Contraintes permanentes

Commits FR sans footer Claude ; jamais `git add -A` ; `docs.rar`,
`SolutionERetroDesignX20260813/` et `CARTE POUR TESTER (VRAI TEST)/` en
LECTURE SEULE ; `PYTHONUTF8=1` ; canvas des schémas CLAIR ; rendu
schématique inspecté à chaque changement de dessin.
