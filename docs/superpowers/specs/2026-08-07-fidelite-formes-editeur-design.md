# Fidélité de forme réelle à l'ouverture/export du schéma + dessin libre à la création — conception

**Date :** 2026-08-07
**Branche :** `rewrite-simple`
**Suite de :** `docs/superpowers/specs/2026-08-05-forme-reelle-composants-onglet-design.md`
(livré) — ce chantier traitait la forme réelle dans l'onglet Composants
(bibliothèque partagée). Angle mort découvert en l'utilisant : l'**éditeur de
schéma** (`gui/tab_draw.py` + `gui/schematic_editor.py`) ouvre et exporte des
fichiers de carte complète (BoardSCH) par un chemin de code totalement
différent, qui n'a jamais reçu ce traitement.

## Le problème

Confirmé en lisant le code (`_open_circuit`, `gui/tab_draw.py:199-231`) :
ouvrir un fichier XML dans l'éditeur passe par `lire_xml()`
(`circuit_analyzer/xml.py`), qui ne garde que type/broches/valeur de chaque
composant — la forme réelle du fichier (`<DataPolygon>`/`<DataSegment>`/
`<DataArc>` de chaque `<DataItem>`) est lue une fois pour DEVINER le type
(`eretro.classer_par_forme`), puis jetée. `build_from_components`
(`gui/schematic_io.py:109`) place ensuite chaque composant avec la géométrie
générique de son type — jamais son vrai contour. Un composant de type non
reconnu peut même être ignoré silencieusement (`report["ignored_components"]`).

Symétriquement, à l'export (`generer_xml`, `circuit_analyzer/xml.py:936`),
chaque `<DataItem>` écrit est construit en cherchant la forme **par nom** dans
un catalogue partagé (`_FORME`) — jamais depuis un contour propre au
composant posé. Un composant placé dans notre éditeur avec une forme réelle
(bibliothèque ou dessiné à la main) perd donc cette forme dès l'export.

Confirmé avec le boss (démonstration visuelle sur un composant réel du
fichier `pg carte.xml`, `A788J`, 16 broches) : il veut que la vraie forme
survive dans les deux sens entre les deux applications, **et** un moyen de
dessiner une forme à la main pour un composant tout neuf plutôt que d'être
limité aux formes déjà capturées.

## Décisions de périmètre (tranchées avec le boss)

- **Aller-retour complet** : fichier généré par ERetroDesign ouvert chez
  nous, ET fichier généré chez nous ouvert dans ERetroDesign — les deux
  doivent montrer la vraie forme.
- **Composant de type inconnu à l'ouverture** : posé sur le schéma avec sa
  vraie forme (contour honnête), plus jamais supprimé silencieusement.
- **Dessin libre (nouveau composant)** : même mécanisme que la forme
  importée — un contour dessiné à la main est stocké et utilisé exactement
  comme un contour importé (mêmes chemins de dessin/export, aucune
  distinction en aval).
- **Mode de dessin** : clic sur chaque coin du contour dans l'ordre,
  aimanté à la grille ; on ferme la forme en revenant sur le premier point
  (ou une touche dédiée).

## Architecture

### Principe commun

Un composant **posé** (dans l'éditeur, `CompInst`) peut porter un contour
réel — une liste de primitives (`"line"`/`"polygon"`/`"arc"`, même format que
`primitives_depuis_dataitem`/`primitives()` savent déjà dessiner). Nouveau
champ `CompInst.forme_primitives: list | None = None`, à côté du `pinout`
existant (même esprit : `None` = comportement actuel inchangé, présent =
bascule).

`SchematicEditor._geom(comp)` (le résolveur déjà en place, spec
2026-07-23) construit le def effectif : si `forme_primitives` est renseigné,
le def inclut `d["primitives"] = comp.forme_primitives` — `primitives()`
(`gui/schematic_symbols.py`) sait déjà retourner ces primitives directement
quand un def les porte (mécanisme livré par le chantier « import fidèle »,
2026-08-05, jamais branché sur l'éditeur jusqu'ici). Aucun nouveau traceur à
écrire : on branche l'éditeur sur une capacité déjà construite mais jusque-là
seulement utilisée par l'onglet Composants.

Trois façons de remplir `forme_primitives`, toutes convergent vers le même
champ :

### 1. Import — `_open_circuit` / `lire_xml` / `build_from_components`

`circuit_analyzer/xml.py::lire_xml` capture, pour chaque `<DataItem>`, son
contour réel en plus de la classification actuelle (réutilise le parseur
déjà existant côté bibliothèque — même famille que
`primitives_depuis_dataitem` — appliqué ici à chaque composant de la carte,
pas seulement à une entrée de bibliothèque). `Composant`
(`circuit_analyzer/composant.py`, importé sous l'alias `Component` dans
`xml.py`) gagne un champ optionnel `primitives`.

`build_from_components` (`gui/schematic_io.py`) copie `comp.primitives` sur
le `CompInst.forme_primitives` de chaque composant placé. Un composant de
type non résolu (aujourd'hui : ignoré) est désormais toujours placé — avec
sa vraie forme si elle est présente, sinon la boîte `X` générique actuelle
(comportement de repli inchangé).

Les broches suivent le même principe que le chantier précédent : positions
réelles du fichier converties en côté+décalage (même helper d'aimantation
déjà utilisé pour le brochage libre), pas un brochage générique gauche/droite.

### 2. Export — `generer_xml`

Le générateur de `<DataItem>` (`circuit_analyzer/xml.py`, la fonction qui
sérialise un composant posé) vérifie d'abord si le composant exporté porte un
`forme_primitives` propre ; si oui, le contour XML vient de là (réutilise
`_primitives_vers_xml`, déjà écrit pour l'export bibliothèque —
`circuit_analyzer/eretro_lib.py` — le format `<DataItem>` étant le même des
deux côtés). Sinon, comportement actuel inchangé : recherche par nom dans le
catalogue `_FORME`.

### 3. Dessin libre — nouveau mode dans l'éditeur

Nouveau mode d'édition (même famille que le mode `pinedit` existant, spec
2026-07-23 : entrer/sortir, clic pour agir, Échap pour terminer) : au lieu de
poser des broches sur les bords d'une boîte fixe, l'utilisateur clique les
coins du contour un par un (aimantés à la grille), et referme la forme en
revenant sur le premier point. Le résultat est stocké tel quel dans
`comp.forme_primitives` — dessiner un contour et importer un contour
produisent exactement la même donnée, consommée par le même code de rendu
et d'export décrits ci-dessus. Le placement des broches reste une étape
séparée (mode `pinedit` existant), comme pour une forme importée.

## Gestion des erreurs / repli

| Cas | Comportement |
|---|---|
| Composant sans forme réelle (comportement actuel) | Boîte générique par type — inchangé, aucune migration |
| Composant de type inconnu à l'ouverture, sans forme dans le fichier | Boîte `X` générique, posé (pas de perte de connexions) — inchangé sauf qu'il n'est plus supprimé si son type était déjà inconnu pour une autre raison |
| Contour dégénéré/malformé (primitive incomplète) à l'import ou à l'export | Ignorée silencieusement, jamais d'échec de l'ouverture/export (même discipline que le chantier précédent) |
| Dessin libre : forme non refermée, ou fermée avec moins de 3 points | Refusé au moment de fermer (message dans la barre de statut), pas de composant à moitié dessiné |

## Composants touchés

| Fichier | Changement |
|---|---|
| `circuit_analyzer/composant.py` | `Component` gagne un champ `primitives` optionnel |
| `circuit_analyzer/xml.py` | `lire_xml` capture le contour réel par composant ; `generer_xml`/générateur de `<DataItem>` l'utilise en priorité s'il est présent |
| `gui/schematic_io.py` | `build_from_components` fait suivre `primitives` vers `CompInst.forme_primitives` ; un type non résolu n'est plus ignoré |
| `gui/schematic_editor.py` | `CompInst.forme_primitives` ; `_geom` en tient compte ; nouveau mode « dessin de contour » (entrée/sortie, clic, fermeture, undo) |
| `circuit_analyzer/eretro_lib.py` | `_primitives_vers_xml` réutilisée telle quelle (pas de changement de fond attendu, à confirmer en écrivant le plan) |

## Tests

| Objet | Ce qui est vérifié |
|---|---|
| `lire_xml` (unitaire) | Un `<DataItem>` avec un vrai contour produit un `Component.primitives` fidèle ; un `<DataItem>` sans forme donne `None` (non-régression) |
| `build_from_components` | Un composant de type inconnu est posé (pas dans `ignored_components`) avec sa forme si présente ; un composant reconnu sans forme garde le comportement actuel |
| `generer_xml` / générateur `<DataItem>` | Un composant avec `forme_primitives` exporte son vrai contour ; sans, comportement actuel inchangé (non-régression explicite) |
| Aller-retour bout en bout | Ouvrir un fichier réel (`A788J` de `pg carte.xml`, lecture seule, jamais committé), l'exporter, ré-ouvrir l'export : même contour, mêmes broches |
| Mode dessin de contour (Tk) | Séquence de clics produit les bonnes primitives ; fermeture refusée sous 3 points ; annulable (Ctrl+Z) ; le composant dessiné se comporte ensuite comme un composant importé (export identique) |

**Boucle PNG obligatoire** (convention du projet) : capture avant/après sur
un fichier réel pour l'ouverture, capture du mode dessin de contour en cours
d'utilisation, capture de l'export ré-ouvert — avant tout commit touchant le
dessin.

## Réserves

1. Le rendu de notre export chez ERetroDesign (côté C#) reste non vérifiable
   depuis ici — réserve déjà actée pour tout export vers cette application,
   pas nouvelle à ce chantier.
2. La conversion broches réelles → côté+décalage suppose des broches sur les
   4 bords du composant (vrai pour tous les exemples réels examinés) ; une
   broche véritablement flottante au milieu du contour n'est pas couverte
   (aucun exemple de ce cas trouvé dans les fichiers réels disponibles).

## Contraintes de projet

- Commits en français, jamais de `Co-Authored-By: Claude`.
- Jamais `git add -A` ; fichiers ajoutés un par un.
- Ne jamais committer `custom_circuits.json` ni `component_library.json`.
- `ERetroDesign/`, `CARTE POUR TESTER (VRAI TEST)/`, `docs.rar`, `dist_demo/`,
  `test14.xml` : lecture seule, jamais committés.
- `PYTHONUTF8=1` sur toutes les commandes pytest.
- `schemdraw==0.22` pinné (non concerné ici, contrainte globale du dépôt).
- Branche `rewrite-simple` ; rien n'est poussé sans accord explicite.
- PNG rendus et inspectés avant tout commit touchant du dessin ; jamais de
  PNG committé.
