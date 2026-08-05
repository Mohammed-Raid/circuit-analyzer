# Forme réelle dans l'onglet Composants + export fidèle vers ERetroDesign — conception

**Date :** 2026-08-05
**Branche :** `rewrite-simple`
**Suite de :** `docs/superpowers/specs/2026-08-05-import-fidele-formes-eretrodesign-design.md`
(commit `5c126c5`, livré) — ce spec traite le reste de la fidélité visuelle
non couvert par le précédent : l'onglet Composants (édition/création) et
l'export d'un composant vers ERetroDesign.

## Le problème

Deux angles morts découverts en vérifiant le chantier précédent :

1. **L'onglet Composants montre toujours une boîte générique**, même pour un
   composant fraîchement importé avec sa vraie forme. Confirmé volontaire
   (l'écran d'édition des broches, `PinCanvas`, sert à repositionner des
   pattes à la souris — jamais branché sur `primitives()`), mais le boss veut
   voir la vraie forme là aussi.
2. **Un composant créé À LA MAIN dans notre appli n'a jamais de forme
   réelle**, et **l'export vers ERetroDesign écrit toujours une boîte
   générique** (`_dataitem_fragment` : `<datapolygon />`/`<dataarc />` vides,
   quatre `<DataSegment>` de rectangle — vérifié en lisant le code,
   `entree.get("primitives")` n'est jamais lu à l'export, même pour un
   composant importé jamais retouché). Le boss veut pouvoir choisir une
   forme réelle en créant un composant, pour qu'il soit utilisable (avec sa
   vraie forme) une fois renvoyé vers ERetroDesign.

## Décisions de périmètre (tranchées avec le boss)

- Les formes du sélecteur viennent **uniquement des composants déjà importés**
  d'ERetroDesign (ceux avec une `primitives` non vide en bibliothèque) — pas
  de formes prédéfinies maison, pas de dessin libre.
- **Le placement des broches reste indépendant de la forme choisie.** Choisir
  la forme d'un AOP (3 pattes) sur un composant à 5 broches est valide : la
  forme est un calque de référence, jamais un gabarit de brochage.
- `xml_source` (réservé à un futur export de schéma entier, toujours hors
  périmètre) ne survit que pour un import **jamais retouché** — une forme
  piochée à la main n'a pas de « XML d'origine » à elle : sémantique nette
  entre `primitives` (ce qu'on dessine) et `xml_source` (le XML exact reçu).

## Architecture

### 1. `gui/pin_canvas.py` — fond visuel optionnel

`PinCanvas.charger(brochage, lecture_seule=False, roles=None, w_mini=None,
h_mini=None, forme_primitives=None)` — nouveau paramètre, stocké
(`self._forme_primitives = forme_primitives`).

`_dessiner()` (actuellement : dessine SEULEMENT `primitives(TYPE_LIBRE, d, 0)`,
la boîte éditable) dessine, si `self._forme_primitives` est non vide, ces
primitives EN PLUS, en premier (dessous), dans une couleur atténuée distincte
(`TEXT_MUTED` ou équivalent — jamais `AUTO_COLOR`, pour ne pas se confondre
avec la boîte éditable par-dessus). Boucle de dessin réutilisée telle quelle
(`polygon`/`line`/`arc`/`text` déjà gérés) — pas de primitive `"text"` dans le
fond (les libellés de la forme originale n'ont pas de sens ici, seul le
contour compte).

`_echelle()` (actuellement : cadre uniquement `self._defn()`, la boîte)
prend le MAX des étendues boîte et forme, pour que les deux tiennent dans le
canevas sans être coupées.

### 2. `gui/tab_components.py` — bascule automatique + sélecteur

**Voir la vraie forme après import/duplication.** `_remplir_formulaire`
transmet déjà `entree` implicitement (via ses paramètres actuels) —
transmettre en plus `entree.get("primitives")` à
`self._canvas_broches.charger(...)`. Couvre `_afficher_perso`,
`_afficher_integre` (types intégrés : jamais de primitives, `None`,
comportement inchangé) et `_dupliquer` (copie la forme avec le reste).

**Choisir une forme à la création.** Nouveau sélecteur (`CTkOptionMenu`) dans
la ligne `mrow` (ligne « Modèle »), juste avant la construction de
`PinCanvas` (`gui/tab_components.py:184`). Liste : `"Aucune"` (défaut) + le
nom de chaque entrée de `charger_bibliotheque()` dont `.get("primitives")`
est non vide. Sélection → état de formulaire
(`self._forme_primitives_choisie`) → repasse par le même chemin que 2a
(`PinCanvas.charger(..., forme_primitives=...)`).

**`_sauvegarder`** (`gui/tab_components.py:704-744`) — ajoute, si une forme
est active (choisie ou héritée d'un import affiché) :
```python
if self._forme_primitives_choisie:
    entree["primitives"] = self._forme_primitives_choisie
    if self._xml_source_valide:
        entree["xml_source"] = self._xml_source_courant
```
Ferme au passage le trou déjà repéré en revue finale du chantier précédent :
aujourd'hui, ré-enregistrer un composant importé SANS RIEN CHANGER efface
silencieusement sa `primitives`/`xml_source` (jamais reprises par
`_sauvegarder`, qui reconstruit `entree` de zéro à chaque fois).

**Règle de validité de `xml_source` — volontairement simple** : `self
._xml_source_valide` démarre à `True` uniquement quand `_afficher_perso`
charge un import jamais retouché (`entree.get("xml_source")` présent), et
passe à `False` dès que le sélecteur de forme est touché (n'importe quel
choix, y compris re-choisir la même forme), ou sur `_afficher_nouveau`/
`_dupliquer` (une nouvelle entrée ou une copie n'est pas l'original). Ne
traque PAS les autres champs (nom/broches/valeur) — `xml_source` n'a
aujourd'hui aucun consommateur (réservé à un futur export de schéma
entier) ; une règle plus fine serait de la complexité anticipée pour rien
tant que ce futur chantier n'est pas conçu.

### 3. `circuit_analyzer/eretro_lib.py::_dataitem_fragment` — export du vrai contour

**Piège identifié pendant la conception :** `_dataitem_fragment` appelle
`geometrie_libre(pinout, boite.get("w"), boite.get("h"))` DIRECTEMENT — pas
via `_auto_def` (`gui/schematic_editor.py`), qui seul applique le correctif
`w_exact`/`h_exact` du chantier précédent (commit `bf341d4`, celui qui a
réglé les broches flottantes sur `Vss`/`Potentiomètre`). Sans ce même
bypass ici, un composant IMPORTÉ (dont `boite` est déjà correctement
dimensionnée sur toute sa géométrie) exporterait quand même des broches
mal positionnées — le bug corrigé côté éditeur reviendrait côté export.
Fix : même bascule que `_auto_def`, dans `_dataitem_fragment` :
```python
if entree.get("primitives"):
    geo = geometrie_libre(pinout, w_exact=boite.get("w"), h_exact=boite.get("h"))
else:
    geo = geometrie_libre(pinout, boite.get("w"), boite.get("h"))
```

Nouvelle fonction pure `_primitives_vers_xml(prims, abs_pt)` (inverse de
`primitives_depuis_dataitem`) : pour chaque primitive dans `prims`,
génère le fragment `<DataSegment>`/`<DataPolygon>`/`<DataArc>` correspondant,
via le MÊME `abs_pt` déjà utilisé pour les broches et la boîte (donc le
même repère, aucune conversion supplémentaire) :
- `"line"` → un `<DataSegment>` (réutilise le helper `seg()` existant).
- `"polygon"` → un `<DataPolygon>` par point (même convention que le format
  lu à l'import : un point par élément, pas de polygone imbriqué).
- `"arc"` → un `<DataArc>` : centre/rayon déduits de la bbox (comme à
  l'import), `Spoint`/`Epoint` reconstruits par trigonométrie standard
  depuis centre+rayon+angles (`stAngle`/`swAngle` déjà stockés tels quels
  dans la primitive — écrits verbatim).

Dans `_dataitem_fragment` : si `entree.get("primitives")` est non vide,
`<datapolygon>`/`<datasegment>`/`<dataarc>` viennent ENTIÈREMENT de
`_primitives_vers_xml(...)` — le rectangle générique actuel (les 4
`<DataSegment>` de boîte) n'est PAS mélangé avec les primitives réelles, il
est remplacé purement et simplement (les primitives contiennent déjà toute
la géométrie visible, pattes comprises — `primitives_depuis_dataitem` ne
distingue pas « patte » de « trait du corps », les deux sont des `"line"`).
Sinon (pas de forme), comportement strictement inchangé (boîte à 4
segments, `<datapolygon />`/`<dataarc />` vides).

## Gestion des erreurs / repli

| Cas | Comportement |
|---|---|
| Composant sans `primitives` (comportement actuel, tous les composants créés à la main avant ce chantier) | Boîte générique partout — inchangé, aucune migration |
| Forme choisie mais composant a un nombre de broches très différent de l'original | Autorisé (broches indépendantes de la forme, tranché avec le boss) — visuel possiblement surprenant, assumé |
| `_primitives_vers_xml` sur une primitive dégénérée (héritée d'un import déjà toléré silencieusement) | Ignore cette primitive, n'échoue jamais l'export (même discipline que `primitives_depuis_dataitem`) |

## Composants touchés

| Fichier | Changement |
|---|---|
| `gui/pin_canvas.py` | `charger()` + `_dessiner()` + `_echelle()` : fond visuel optionnel |
| `gui/tab_components.py` | Sélecteur de forme, transmission automatique après import/duplication, `_sauvegarder` préserve la forme |
| `circuit_analyzer/eretro_lib.py` | `_primitives_vers_xml()` + `_dataitem_fragment` : export du vrai contour si présent |

## Tests

| Objet | Ce qui est vérifié |
|---|---|
| `PinCanvas` (Tk) | Fond dessiné quand `forme_primitives` fourni ; absent sinon (non-régression) ; boîte éditable reste cliquable par-dessus |
| `tab_components.py` (Tk) | Sélecteur liste bien les imports à primitives ; choix transmis au `PinCanvas` ; `_sauvegarder` préserve `primitives` sur un composant importé ré-enregistré sans modification |
| `_primitives_vers_xml` (unitaire, pur) | Chaque famille (line/polygon/arc) produit le fragment XML attendu ; aller-retour `primitives_depuis_dataitem(_primitives_vers_xml(p)) == p` (à l'échelle/repère près) sur des primitives synthétiques |
| `_dataitem_fragment` | Un composant avec `primitives` exporte un vrai contour (plus de boîte 4-segments) ; un composant sans `primitives` exporte la boîte générique inchangée (non-régression explicite) ; un composant importé dont la patte est loin du corps (type `Vss`/`Potentiomètre`) exporte une broche proche de son contour, pas le bug du bypass manquant (piège identifié ci-dessus) |

**Boucle PNG obligatoire** (convention du projet) : capture de l'onglet
Composants montrant la vraie forme en fond pour un import, et pour un
composant créé à la main avec une forme choisie ; avant tout commit touchant
le dessin.

## Réserves

1. Le rendu de l'export chez ERetroDesign (côté C#) n'est pas vérifiable
   depuis ici — réserve déjà actée pour tout export vers sa bibliothèque
   (héritée des chantiers précédents), pas nouvelle.
2. La reconstruction `Spoint`/`Epoint` d'un arc à l'export est une
   trigonométrie standard, cohérente avec ce que l'import fait déjà (marche
   visuellement chez nous, notamment sur Self.xml) — mais jamais comparée à
   ce qu'écrirait le C# lui-même pour le même contour.

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
