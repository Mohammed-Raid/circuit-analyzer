# Cohérence des couches Top/Bottom — Design

**Date :** 2026-08-17
**Statut :** livré. Implémenté dans `circuit_analyzer/xml.py` (`_couche_de`
+ vérification dans `lire_xml`) ; 3 nouveaux tests dans
`tests/test_eretro_nouveau_format.py` (26/26 passent) ; suite complète
2352 passés / 15 échecs (mêmes 15 préexistants qu'avant ce chantier,
non liés). Bout en bout avec la VRAIE appli (`SizeTraceHarness`,
`layer-real-app-e2e`) : découverte que ce n'est PAS qu'une protection
défensive théorique — basculer de vue (Top→Bottom) EN COURS DE TRACÉ
(`DwLine` puis `EndLine`) est un chemin réel et non bloqué par le C#
aujourd'hui pour produire un fil Top/Bottom incohérent ; le fichier réel
qui en sort déclenche bien l'avertissement Python attendu, connexité
intacte.

## Context (pourquoi)

Suite du même objectif : le boss dessine dans l'éditeur C#, analyse avec
cette appli Python, récupère le résultat. `Line.cs`/`DataItem.cs` portent
tous les deux `Top`/`Bottom` (côté de la carte double-face) — confirmé
absent de `lire_xml` : zéro occurrence de lecture, seules des valeurs
`true`/`false` codées en dur existent côté ÉCRITURE (`generer_xml`, le
chemin « pas de fichier source », jamais lues en entrée).

**Recherche avant design (important)** : contrairement au via (chantier
précédent), l'absence de lecture de `Top`/`Bottom` n'est **pas** un bug de
connexité aujourd'hui — `lire_xml` ne déduit jamais une connexion d'une
coïncidence géométrique de couche (uniquement des refs symboliques + la
correspondance de position pour les vias, qui par définition relient
toujours les deux couches). Donc ignorer `Top`/`Bottom` n'a **jamais fait
fusionner deux nets à tort**. Le vrai gain n'est pas une correction de bug,
c'est une **détection de données incohérentes** sur les vraies cartes
scannées (double-face) : un fil direct qui prétend relier deux points sur
des couches différentes sans passer par un via est une impossibilité
physique — jamais signalée aujourd'hui.

Le contrat exact, retrouvé côté C# (`Forms/Form1.cs`, commentaire sur
`WireSegmentAt`) : *« un clic near un fil du Bottom pendant qu'on est en
vue Top... créer une jonction Top↔Bottom — électriquement impossible sauf
via un via »* — l'éditeur lui-même applique déjà cette règle à la saisie.
Python doit simplement la vérifier en LECTURE.

## But (v1)

Un avertissement (`.warnings`, mécanisme déjà existant, jamais bloquant)
quand un fil AVEC ses deux bouts résolus sur de VRAIES broches (pas un
via, un via relie légitimement les deux couches par définition) a sa
propre couche (`<Line><Top>/<Bottom>`) différente de la couche d'un
composant qu'il touche (`<DataItem><Top>/<Bottom>`).

## Non-goals (v1)

- Ne PAS vérifier la cohérence à travers un via (c'est précisément son
  rôle de relier les deux couches — jamais un warning là).
- Ne PAS vérifier à travers une jonction fil-sur-fil différemment d'un fil
  normal (elle se résout déjà par la MÊME boucle, au même titre qu'un fil
  ordinaire — pas de traitement spécial nécessaire).
- Ne PAS exposer `couche` comme nouveau champ sur `Composant` / dans le
  rapport (spéculatif, aucun consommateur aujourd'hui — YAGNI, s'ajoute
  facilement plus tard si un besoin réel apparaît).
- Ne PAS toucher au rendu (`gui/`, `tools/render_ilots_v2.py`) : ce
  chantier est une vérification de données, pas un affichage.
- Fichiers/composants sans `<Top>`/`<Bottom>` (dialecte ancien) → couche
  `None`, jamais de warning (silencieux, non-régressif par construction).

## Architecture

Même mécanisme que le chantier via : extension MINIME de `lire_xml`.

1. Helper pur `_couche_de(elem)` (élément `<Line>` OU `<DataItem>`, les
   deux portent `<Top>`/`<Bottom>` en enfants directs) → `'Top'`,
   `'Bottom'`, ou `None` si absent/ambigu (les deux `true`, les deux
   `false`, ou illisible — jamais de couche devinée).
2. Stocker `elements[idx]['couche'] = _couche_de(item)` au moment de
   l'extraction des composants (même boucle que `rail`/`geo`).
3. Dans la boucle des fils, juste après `unir(bf, bl)` (donc UNIQUEMENT
   quand les DEUX bouts sont résolus — un bout via/jonction non résolu ne
   déclenche jamais cette vérification) : si `_couche_de(fil)` est connue
   et diffère de la couche connue d'un des deux composants touchés →
   avertissement, format `"Fil #N sur {couche fil} relie un composant sur
   {couche composant} sans via (couches incohérentes)."`.

## Tests

- Unité `_couche_de` : `Top=true/Bottom=false` → `'Top'` ; inverse →
  `'Bottom'` ; absents, ambigus (les deux `true`) → `None`.
- Nouveau cas dans `test_eretro_nouveau_format.py` : deux composants +
  fil, tous `Top=true` → **aucun** avertissement (cas normal, garde-fou
  anti-faux-positif).
- Cas positif : composant A `Top`, composant B `Bottom`, fil direct
  `Top` entre eux (aucun via) → avertissement présent, connexité
  électrique INCHANGÉE (le fil continue de les unir — on avertit, on ne
  bloque jamais).
- Garde-fou : le MÊME scénario mais avec un via entre A (Top) et B
  (Bottom) → **aucun** avertissement (le via a le droit de changer de
  couche).
- Non-régression `05_via`/`10_via_simple`/`11_via_chaine` (chantier
  précédent) : toujours verts, aucun `<Top>`/`<Bottom>` dans ces fixtures
  → couche `None` partout → jamais de warning.
- Bout en bout (méthode du chantier précédent) : reconstruire avec le VRAI
  `Form1` (harness `SizeTraceHarness`) un fil direct entre deux composants
  posés sur des côtés différents (`WPlaceFromLib(..., top: true/false)`),
  sauvegarder avec le VRAI `SeveXMLFile.SaveData`, lire avec le VRAI
  `lire_xml` Python, confirmer l'avertissement.

## Contraintes permanentes

Identiques au chantier via : commits FR sans footer Claude, jamais
`git add -A`, `SolutionERetroDesignX20260813/` en lecture seule pour le
reste (seul le harness C# `SizeTraceHarness/` en dehors de `test3/` est
modifiable, comme au chantier précédent), rendu inspecté si le rendu est
touché (pas le cas ici).
