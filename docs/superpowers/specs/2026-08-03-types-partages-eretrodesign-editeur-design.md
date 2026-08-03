# Types partagés ERetroDesign dans l'éditeur — conception

**Date :** 2026-08-03
**Branche :** `rewrite-simple`
**Suite de :** `docs/superpowers/specs/2026-07-31-bibliotheque-partagee-design.md` (Plan 1,
terminé) — ceci est le **Plan 2a** annoncé dans ce spec (« Rendu de notre côté »),
restreint à l'éditeur interactif Tk (`gui/schematic_editor.py` /
`gui/schematic_symbols.py`). Le rendu schemdraw des popups de circuit détecté
(`gui/circuit_viewer.py`, `gui/impedance_schematic.py`) est un chantier
distinct, non commencé (« Plan 2b »), plus risqué (sémantique d'ancrage
schemdraw, ~3300 lignes de tests de rendu) — hors périmètre ici.

## Le problème

Sa bibliothèque vivante (`ERetroDesign/.../LibItem/Lib/`) contient 4 symboles
que notre éditeur ne sait pas dessiner ni même placer aujourd'hui :
`Gate2`, `NOT`, `OR`, `Potentiomètre`. Ils existent déjà dans
`circuit_analyzer.xml._FORME` depuis la fusion du Plan 1 (ajoutés tels quels,
puisque rien ne les référençait encore), mais aucune lettre de type ni bouton
de palette ne leur correspond côté éditeur.

**Reformulation importante faite pendant la conception** : l'hypothèse
initiale (« combler les trous de rendu ») s'est révélée plus étroite que
prévu — les 11 types existants de l'éditeur (R/C/L/F/Q/M/U/GND/VCC/T/K) ont
tous déjà un traceur maison dédié et approuvé visuellement ; il a été décidé
de ne PAS y toucher. Le seul vrai trou de rendu (`SW`, sans traceur dédié) n'a
pas de symbole correspondant dans sa bibliothèque — hors périmètre. La valeur
réelle de ce chantier est donc : **ajouter 4 nouveaux types plaçables**,
dessinés depuis sa géométrie plutôt qu'à la main.

## Décision de périmètre

Ces 4 types sont des **boîtes noires exportables**, au même titre qu'un
composant catalogue non identifié électriquement :
- aucune détection, aucune règle DRC, aucune sémantique électrique nouvelle
  dans `detecteur.py` / `satellites.py` / `ilots.py` ;
- non rattachés à un montage détecté → ils apparaissent en section
  « Divers »/non-classifiés du rapport, comme n'importe quel composant
  inconnu aujourd'hui.

## Vérifications faites pendant la conception (données réelles)

Pins post-fusion (`circuit_analyzer.xml._FORME`, dossier ERetroDesign présent
sur ce poste) :

```
Gate2         -> {'S1': (64, -32, 0), 'S2': (64, 32, 1), 'D8': (-64, 0, 2)}
NOT           -> {'1': (-80, 0, 0), '2': (80, 0, 1)}
OR            -> {'1': (-80, -17, 0), '2': (80, -2, 1), '3': (-80, 10, 2)}
Potentiomètre -> {'1': (-80, 12, 0), '2': (-6, -22, 1), '3': (80, 12, 2)}
```

Géométrie : ces 4 formes n'utilisent que `<DataSegment>` et `<DataArc>`
(jamais `<DataPolygon>`). Format `DataArc` confirmé par lecture directe :
`<pCenter><X/><Y/></pCenter><stAngle>deg</stAngle><swAngle>deg</swAngle>
<Spoint/><Epoint/>` — conversion mécanique vers la primitive Tk
`("arc", bbox, start_deg, extent_deg)` (`bbox` déduite de `pCenter` ± rayon,
rayon = distance `pCenter`→`Spoint`).

Échelle : confirmée à ×0,5 depuis unités BoardSCH vers unités éditeur, en
comparant la Résistance partagée (broches à ±80 chez lui/nous en XML) à
`COMP_DEFS["R"]["pins"]` de l'éditeur (broches à ±40) — `gui/schematic_editor.py:35-36`.

## Architecture

**Rendu — `gui/schematic_symbols.py`** : nouvelle fonction
`primitives_depuis_forme(nom_forme)`. Lit `_FORME[nom_forme]` (déjà fusionné
au chargement de `circuit_analyzer.xml`, rien à ré-implémenter côté
chargement), parse les fragments XML (regex simple, même famille que le
parsing déjà fait dans `eretro_symboles.py:_lire_symbole`), mets à l'échelle
×0,5, retourne une liste de primitives (`line`/`arc`/`polygon`) — le format
que `primitives()` sait déjà dispatcher. Enregistrée dans `_TRACEURS` comme
les 11 traceurs existants :

```python
_TRACEURS["POT"]   = lambda d: primitives_depuis_forme("Potentiomètre")
_TRACEURS["NOT"]   = lambda d: primitives_depuis_forme("NOT")
_TRACEURS["OR"]    = lambda d: primitives_depuis_forme("OR")
_TRACEURS["GATE2"] = lambda d: primitives_depuis_forme("Gate2")
```

Aucun changement à `primitives()` ni à `_draw_comp` (`schematic_editor.py`) :
le dispatch existant fonctionne tel quel.

**Palette — `gui/schematic_editor.py`** : nouvelle fonction
`_types_partages_eretro() -> dict`, appelée par `_compute_defs()` (qui fusionne
déjà la bibliothèque JSON personnalisée dans `self._defs` — même point
d'extension, pas de nouveau mécanisme). Pour chacun des 4 noms présents dans
`circuit_analyzer.xml._FORME`, construit une entrée `COMP_DEFS`-compatible :
`w`/`h` dérivés de l'étendue de la géométrie mise à l'échelle, `pins` alias
(table ci-dessous), `default_value` vide, couleur `AUTO_COLOR`. Un nom absent
de `_FORME` (dossier ERetroDesign absent ou fusion jamais faite) est
simplement omis — le bouton de palette n'apparaît pas, comme toute def
absente de `self._defs` aujourd'hui.

**Renommage des broches** (affichage + export uniquement — jamais la
géométrie, qui reste en clés numériques/brutes en interne le temps du
rendu) :

| Forme | Ses noms | Nos alias |
|---|---|---|
| `NOT` | `1`, `2` | `IN`, `OUT` |
| `OR` | `1`, `2`, `3` | `IN1` (x=-80,y=-17), `OUT` (x=+80), `IN2` (x=-80,y=10) |
| `Potentiomètre` | `1`, `2`, `3` | `A` (x=-80), `W` (x=-6, curseur — position décalée), `B` (x=+80) |
| `Gate2` | `S1`, `S2`, `D8` | **non figé** — voir Réserve |

## Composants touchés

| Fichier | Changement |
|---|---|
| `gui/schematic_symbols.py` | + `primitives_depuis_forme(nom_forme)` (parsing + échelle), + 4 entrées `_TRACEURS` |
| `gui/schematic_editor.py` | + `_types_partages_eretro()`, appelée depuis `_compute_defs()` |
| `circuit_analyzer/composant.py` | à vérifier à l'implémentation (voir Réserve) |

Aucun changement à `circuit_analyzer/detecteur.py`, `satellites.py`,
`ilots.py`, `drc.py`, `rapport.py` (cohérent avec la décision de périmètre).

## Gestion des erreurs / repli

Identique au principe déjà validé en Plan 1 : dossier ERetroDesign absent ou
symbole corrompu → le(s) type(s) concerné(s) sont simplement absents de la
palette (pas de bouton, pas de crash, pas de composant fantôme). Aucun
nouveau mode d'échec introduit par rapport à ce qui existe déjà pour la
fusion de bibliothèque.

## Tests

| Objet | Ce qui est vérifié |
|---|---|
| `primitives_depuis_forme` (unitaire, pur) | synthétique avec segment+arc connus, mise à l'échelle ×0,5 correcte, format de sortie conforme à `primitives()` |
| Les 4 vrais symboles (`skipif` dossier absent) | se chargent, se dessinent sans exception, produisent au moins une primitive |
| Repli | dossier ERetroDesign absent → les 4 types absents de la palette, `_compute_defs()` ne lève pas |
| Export | un composant placé de chaque nouveau type s'exporte (netlist et/ou XML) sans lever, avec les alias de broches attendus |

**Boucle PNG obligatoire** (convention constante de ce projet, cf. mémoire de
session « Résultats visuels attendus ») : les 4 nouveaux symboles rendus et
inspectés avant de committer — script scratch hors dépôt, jamais de PNG
committé. En particulier pour `Gate2`, dont le sens IN/OUT n'est pas certain
depuis les seuls noms de broches.

## Réserves

1. **`Gate2` : noms de broches non figés.** `S1`/`S2` (à x=+64) vs `D8`
   (à x=-64, seul de son côté) suggèrent une forme à 2 entrées + 1 sortie,
   mais rien ne garantit que le côté `D8` soit la sortie plutôt que
   l'entrée — à trancher après rendu visuel et comparaison avec l'apparence
   dans ERetroDesign lui-même si possible. Le renommage de ses broches est
   la dernière étape de l'implémentation, pas la première.
2. **`composant.py` / `TYPES_COMPOSANTS`** : ce spec suppose que
   `construire_graphe`/`exporter_composants` n'exigent pas qu'un type soit
   enregistré dans `TYPES_COMPOSANTS` pour fonctionner (les pins viennent de
   l'instance `Composant` déjà construite, pas d'un second lookup). À vérifier
   empiriquement en tout début d'implémentation ; si faux, ajouter une entrée
   minimale (nom, pins par défaut) sans lui donner de sémantique de
   détection.
3. **Pas de couverture `TYPES_COMPOSANTS`/détection** : si le boss souhaite un
   jour une vraie sémantique électrique pour le potentiomètre (résistance
   variable 3 bornes) ou une détection de porte logique packagée (distincte
   de la détection CMOS transistor-niveau existante dans `logique.py`), ce
   sera un chantier séparé, plus lourd (nouvelles règles `detecteur.py`,
   tests dédiés) — explicitement hors périmètre ici (YAGNI).
4. Réserve héritée du Plan 1, toujours valable : le rendu de nos propres
   symboles poussés dans sa bibliothèque n'est pas validé côté C#.

## Contraintes de projet

- Commits en français, jamais de `Co-Authored-By: Claude`.
- Jamais `git add -A` ; fichiers ajoutés un par un.
- Ne jamais committer `custom_circuits.json` ni `component_library.json`.
- `ERetroDesign/`, `CARTE POUR TESTER (VRAI TEST)/`, `docs.rar`, `dist_demo/`,
  `test14.xml` : lecture seule, jamais committés.
- `PYTHONUTF8=1` sur toutes les commandes pytest.
- `schemdraw==0.22` pinné (non directement concerné ici, mais contrainte
  globale du dépôt).
- Branche `rewrite-simple` ; rien n'est poussé sans accord explicite.
- PNG rendus et inspectés avant tout commit touchant du dessin ; jamais de
  PNG committé.
