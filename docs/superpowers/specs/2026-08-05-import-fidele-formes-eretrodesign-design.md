# Import fidèle des formes de bibliothèque ERetroDesign — conception

**Date :** 2026-08-05
**Branche :** `rewrite-simple`
**Remplace :** `docs/superpowers/specs/2026-08-03-types-partages-eretrodesign-editeur-design.md`
(jamais implémenté — ce spec généralise la même idée à tout composant importé,
plutôt qu'à 4 noms figés). L'ancien spec est marqué obsolète, pas supprimé.
**Suite de :** discussion du 2026-08-05 sur la fidélité avec ERetroDesign —
**Spec 1 sur 2** d'un chantier plus large (Spec 2, export fidèle vers
ERetroDesign, sera brainstormée séparément une fois celle-ci livrée).

## Le problème

Quand le boss importe des composants depuis la bibliothèque partagée
ERetroDesign (`LibItem/Lib/`, un `<DataItem>` par composant) via l'onglet
Composants (`_recevoir_biblio` / `_importer_eretro` dans `gui/tab_components.py`,
qui appellent `circuit_analyzer.eretro_lib.composants_depuis_xml`), puis les
place dans l'éditeur de schéma (`gui/schematic_editor.py`), **le résultat n'a
rien à voir avec le vrai composant** : une boîte rectangulaire générique avec
les broches au bon endroit, mais aucune des formes réelles (triangle d'un AOP,
bosses d'une self, barre d'une diode…).

**Cause exacte, vérifiée en lisant le code :**
`circuit_analyzer/eretro_lib.py::_entree_depuis_dataitem` lit `datasegment`
et `datapin` pour calculer une boîte englobante et positionner les broches
sur ses bords (`aimanter_bord`), mais **jette** `datapolygon` et `dataarc`, et
ne garde aucune trace du contour interne réel du symbole. L'entrée résultante
(`{"name", "pins", "brochage", "boite"}`) est ensuite consommée par
`gui/schematic_editor.py::_auto_def`, qui construit une géométrie
« brochage libre » (`geometrie_libre`) — la même boîte générique que
n'importe quel type personnalisé créé à la main, rendu via le type de rendu
`TYPE_LIBRE` (`schematic_symbols.py`).

**Vérification faite sur des vrais fichiers** (`ERetroDesign/bin/Debug/LibItem/Lib/`) :
un `<DataItem>` contient bien tout ce qu'il faut pour reconstruire la vraie
forme — confirmé en ouvrant `AOP.xml` (triangle via `<datapolygon>`, pattes
`+`/`-` via deux `<DataSegment>` courts), `Self.xml` (3 bosses via
`<DataArc>`), `Diode.xml` (triangle + barre). Format `DataArc` :
`<pCenter><X/><Y/></pCenter><stAngle>deg</stAngle><swAngle>deg</swAngle>
<Spoint/><Epoint/>` — rayon déductible de la distance `pCenter`→`Spoint`.
Échelle : **corrigé pendant la conception du plan** — `eretro_lib.py` n'a
PLUS de mise à l'échelle depuis sa réécriture pour le partage de bibliothèque
(`ECHELLE = 1`, commentaire en tête de fichier : ses coordonnées ~±48..80
tombent directement dans la plage de nos boîtes ~80×60, aucune division). Le
spec du 2026-08-03 (remplacé) affirmait ×0,5 — c'était vrai avant cette
réécriture, plus maintenant. `_entree_depuis_dataitem` divise déjà chaque
coordonnée de broche par `ECHELLE` (no-op tant qu'elle vaut 1) : la nouvelle
fonction de forme DOIT utiliser cette même constante, pas une valeur câblée
en dur, sous peine de désaligner pattes et contour si `ECHELLE` change un
jour.

## Décision de périmètre

- Uniquement l'éditeur interactif Tk (`gui/schematic_editor.py` /
  `gui/schematic_symbols.py`) et le point d'import
  (`circuit_analyzer/eretro_lib.py`). Le rendu schemdraw des popups de
  circuit détecté (`gui/circuit_viewer.py`, `gui/impedance_schematic.py`) est
  un chantier distinct, plus risqué (sémantique d'ancrage schemdraw), hors
  périmètre ici — décision héritée telle quelle du spec remplacé.
- Aucun changement à `detecteur.py` / `satellites.py` / `ilots.py` / `drc.py` /
  `rapport.py` : un composant importé reste une boîte noire exportable, sans
  détection ni règle DRC nouvelle. Seule sa **forme dessinée** change, pas sa
  sémantique électrique.
- Les 11 types intégrés de l'éditeur (R/C/L/D/F/Q/M/U/T/K/SW) gardent leurs
  traceurs maison dédiés, approuvés visuellement — on n'y touche pas. Ce
  chantier ne concerne que les types **importés** de la bibliothèque partagée
  (jamais un type intégré, qui n'a pas de `<DataItem>` source).

## Architecture

**Nouvelle fonction pure — `gui/schematic_symbols.py::primitives_depuis_dataitem`**

```python
def primitives_depuis_dataitem(xml_texte: str, echelle: float) -> list:
    """@brief Contour reel d'un <DataItem> ERetroDesign en primitives d'edition.

    Parse datasegment/DataSegment (Spoint/Epoint -> "line"), dataarc/DataArc
    (pCenter/stAngle/swAngle, rayon = distance pCenter->Spoint -> "arc"),
    datapolygon/DataPolygon (points groupes -> un seul "polygon" ferme).
    Mise a l'echelle *echelle* — l'appelant DOIT passer la meme constante
    ECHELLE que celle utilisee pour les broches (eretro_lib.py), jamais une
    valeur cablee en dur ici, sous peine de desaligner pattes et contour.
    Sortie : meme format que `primitives()` sait deja dispatcher. Pure, sans
    Tk, testable sur un fragment XML synthetique.

    @param xml_texte Fragment <DataItem>...</DataItem> (texte).
    @param echelle Facteur d'echelle unites BoardSCH -> unites editeur (=
           eretro_lib.ECHELLE, actuellement 1 : pas de mise a l'echelle).
    @return list[tuple] Primitives ("line"|"arc"|"polygon", ...). Vide si le
            composant n'a ni polygone, ni segment, ni arc (ex. connecteur nu).
    """
```

**`circuit_analyzer/eretro_lib.py::_entree_depuis_dataitem`** — après le
calcul actuel de `pins`/`brochage`/`boite` (**inchangé**), ajoute deux clés :

- `entree["primitives"]` = `primitives_depuis_dataitem(ET.tostring(r, encoding="unicode"), ECHELLE)`
  — liste vide si rien d'exploitable (ex. connecteur nu, seulement des broches).
- `entree["xml_source"]` = le fragment `<DataItem>` d'origine tel quel (texte)
  — **non consommé par cette Spec**, réservé pour la Spec 2 (export fidèle :
  un composant jamais modifié dans notre éditeur pourra repartir avec son XML
  original inchangé plutôt que d'être régénéré). Coût de stockage négligeable
  (quelques Ko par composant).

**`gui/schematic_editor.py::_auto_def`** — si l'entrée de bibliothèque porte
des `primitives` non vides, les copie telles quelles dans le def retourné
(`d["primitives"] = val["primitives"]`), **en plus** de la géométrie
boîte/brochage déjà calculée par `geometrie_libre` (les broches restent
positionnées exactement comme aujourd'hui — seule la forme dessinée change).

**`gui/schematic_symbols.py::primitives()`** — en tête de la fonction, avant
le dispatch `_TRACEURS`/`TYPE_LIBRE` existant :

```python
def primitives(comp_type, defn, rotation, value=""):
    if defn.get("primitives"):
        prims = defn["primitives"]
    elif comp_type == TYPE_LIBRE:
        prims = _tr_boite_libre(defn)
    ...
    return _rot_prims(prims, rotation)   # inchange : meme appel final qu'aujourd'hui
```

Court-circuite le dispatch existant sans le modifier — aucun nouveau
`TYPE_RENDU`, aucun changement à `_draw_comp` ni `est_boite_generique`.

**Piège identifié en auto-révision — les libellés de broches.**
`est_boite_generique(comp_type)` renvoie `True` pour **tout** type importé/
personnalisé, `TYPE_LIBRE` compris (sa définition : vrai sauf `"D"` ou un
type dans `_TRACEURS` — jamais vrai pour un type perso). Aujourd'hui ça
supprime le libellé générique externe et laisse `_tr_boite_libre` dessiner
lui-même le nom de chaque broche en primitive `("text", …)`. Un composant
rendu avec `defn["primitives"]` (la vraie forme importée) resterait donc
**sans aucun libellé de broche** si on ne fait que retourner la forme brute.

Fix : factoriser la boucle de libellés de `_tr_boite_libre` en un petit
helper `_libelles_broches(defn)` (même style/position que l'existant),
appelé par `_tr_boite_libre` (inchangé, juste refactorisé) **et** par la
nouvelle branche de `primitives()` :

```python
def primitives(comp_type, defn, rotation, value=""):
    if defn.get("primitives"):
        prims = defn["primitives"] + _libelles_broches(defn)
    elif comp_type == TYPE_LIBRE:
        prims = _tr_boite_libre(defn)
    ...
    return _rot_prims(prims, rotation)
```

## Gestion des erreurs / repli (aucune régression possible)

| Cas | Comportement |
|---|---|
| Composant sans polygone/segment/arc (ex. connecteur nu, juste des broches) | `primitives` vide → repli automatique sur la boîte `TYPE_LIBRE` actuelle, identique à aujourd'hui |
| `component_library.json` existant, créé avant cette feature | `primitives`/`xml_source` absents → comportement inchangé, additif pur, aucune migration |
| Dossier ERetroDesign absent / XML illisible | Déjà géré en amont par `composants_depuis_xml` (lève, capturé côté GUI) — inchangé |
| Fragment `<DataItem>` corrompu au moment du parsing des primitives | `primitives_depuis_dataitem` ne doit jamais lever — une géométrie inattendue (arc dégénéré, polygone à 1 point) est ignorée silencieusement plutôt que de faire échouer tout l'import du composant |

## Composants touchés

| Fichier | Changement |
|---|---|
| `gui/schematic_symbols.py` | + `primitives_depuis_dataitem(xml_texte, echelle)`, court-circuit en tête de `primitives()` |
| `circuit_analyzer/eretro_lib.py` | `_entree_depuis_dataitem` : + `entree["primitives"]`, + `entree["xml_source"]` |
| `gui/schematic_editor.py` | `_auto_def` : copie `primitives` dans le def si présentes |

## Tests

| Objet | Ce qui est vérifié |
|---|---|
| `primitives_depuis_dataitem` (unitaire, pur) | Fragments synthétiques : un `DataSegment` connu → `"line"` attendue, un `DataArc` connu → `"arc"` attendu (bbox/angles corrects), un `DataPolygon` (plusieurs points) → un seul `"polygon"` fermé ; mise à l'échelle vérifiée avec un `echelle` ≠ 1 passé explicitement (ex. 0,5) sur des coordonnées connues, pour prouver que le paramètre est réellement appliqué et pas ignoré |
| Vrais fichiers (`skipif` dossier ERetroDesign absent) | AOP.xml, Diode.xml, Self.xml : parsing sans exception, au moins une primitive de la famille attendue par composant |
| `_entree_depuis_dataitem` | `primitives` et `xml_source` bien peuplés pour un composant avec forme ; `primitives` vide (pas d'erreur) pour un connecteur nu |
| Éditeur (Tk) | Un composant importé avec primitives se dessine SANS le rendu boîte générique (au moins un item canvas hors les 4 côtés du cadre) ; un composant sans primitives garde le rendu boîte actuel — non-régression explicite testée |
| Libellés de broches | Un composant importé avec primitives affiche bien un libellé texte par broche (piège identifié en auto-révision — sans `_libelles_broches`, les labels disparaissent silencieusement) |

**Boucle PNG obligatoire** (convention constante du projet, cf. mémoire de
session « Résultats visuels attendus ») : au moins 3 composants réels rendus
et inspectés avant tout commit touchant le dessin — script scratch hors
dépôt, jamais de PNG committé :
1. AOP (triangle + petites pattes `+`/`-`)
2. Self (3 bosses en arc)
3. Diode (triangle + barre)
4. Un composant SANS primitives (ex. connecteur) → vérifier que la boîte
   générique actuelle est strictement inchangée (non-régression visuelle)

## Réserves

1. Le rayon d'un arc est déduit de `distance(pCenter, Spoint)` — suppose
   `Spoint` et `Epoint` équidistants du centre (vrai dans tous les exemples
   observés, mais pas garanti par le format). Si un arc réel s'avère
   elliptique ou incohérent, `primitives_depuis_dataitem` doit l'ignorer
   plutôt que planter (cf. tableau de repli).
2. `datatext` (texte libre positionné, silkscreen) n'est pas traité par cette
   Spec — vide dans tous les exemples observés dans la bibliothèque actuelle,
   ajouté seulement s'il s'avère nécessaire en pratique (YAGNI).
3. Le champ `typ` racine du `<DataItem>` (code entier interne à ERetroDesign,
   ex. GND=71, Diode=32) reste **non exploité** par cette Spec — la table de
   correspondance est incomplète côté projet et hors périmètre : cette Spec
   ne touche que la forme dessinée, pas la classification électrique.
4. Réserve héritée du spec remplacé : le rendu de nos propres symboles
   poussés dans sa bibliothèque n'est pas validé côté C#.

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
