# Import ERetroDesign (fichiers réels) — Design

**Date :** 2026-07-17
**Statut :** validé en brainstorming (workflow, livrable, inconnus, composés, approche A)
**Chantier :** 1 de 2 — l'export round-trip vers ERetroDesign fera l'objet d'une spec séparée.

## 1. Contexte et objectif

ERetroDesign est l'éditeur C# maison de l'entreprise (WinForms .NET 4.7.2, sources dans
`SolutionERetroDesignX20260813/ERetroDesign/`, également en développement). Usage : rétro-conception
de cartes — photos Top/Bottom en fond, l'utilisateur redessine composants et liaisons par-dessus.
Il sauvegarde tout en XML (`XmlSerializer` .NET brut, racine `<BoardSCH>`) et n'a **aucun export
netlist** : le fichier de sauvegarde EST la donnée.

Découverte clé : notre application parle déjà un **dialecte simplifié** de ce format —
`generer_xml`/`lire_xml` (`circuit_analyzer/xml.py`) produisent et lisent du BoardSCH. Mais les
fichiers **réels** d'ERetroDesign cassent la lecture actuelle sur quatre points précis :

1. **Refs de connexion anciennes concaténées.** `_analyser_ref_noeud` exige le format `i_j_u_v`
   (underscores). Les vieux fichiers réels portent des refs concaténées sans séparateur
   (`2011`, `T40132`, `X300`) → `ValueError` avalé silencieusement → **toute la connexité perdue**.
2. **`CCmpntL` jamais lu.** Les puces « composées » (boîtier + portes internes + fils internes)
   remplissent les vraies cartes (`TestDiagram.xml` en est plein) et sont aujourd'hui ignorées.
3. **Noms de bibliothèque non mappés.** `_NOM_VERS_TYPE` connaît NOS noms (« Résistance », « Capa »,
   « AOP », « Puce8 »…) mais pas les leurs (« resistance trad », « condo », « npn », « NE555 »,
   « CD4011 »…) → tout tombe en type X (boîte inconnue), aucune analyse.
4. **Indexation par `<id>`.** `lire_xml` indexe les composants par le champ `<id>` ; la sémantique
   C# référence les composants par **position dans `CmpntL`**, et les vrais fichiers peuvent porter
   `id=0` partout → collisions d'index, composants écrasés.

**Objectif :** ouvrir un fichier réel ERetroDesign dans l'onglet Analyser exactement comme un
fichier natif, et obtenir l'analyse complète existante (îlots, montages détectés, blocs Z
cliquables) sans jamais rien perdre ni planter. Aucune modification du projet C#.

## 2. Architecture

Un **seul chemin de lecture** : `lire_xml(chemin)` reste l'unique point d'entrée (contrat inchangé :
retourne `ListeComposantsXML` avec `.warnings` ; l'UI ne change pas). Les traitements spécifiques
ERetroDesign vivent dans un **nouveau module pur** `circuit_analyzer/eretro.py`, appelé par
`lire_xml` — pas de dépendance GUI, testable isolément.

Pipeline de lecture révisé :

```
BoardSCH.xml
  → parse ElementTree (existant)
  → eretro.aplatir_composes(racine)        # CCmpntL → composants + fils supplémentaires
  → indexation des composants PAR POSITION dans CmpntL (remplace la clé <id>)
  → eretro.resoudre_connexions(...)        # égalité NodeL ↔ CFirst/CLast, fallback refs i_j_u_v
  → Union-Find + nommage des nets           (existant, inchangé)
  → mapping noms → types (table existante + table ERetroDesign)
  → Composant(...) + appliquer_catalogue    (existant, inchangé)
```

Aucun discriminateur de dialecte n'est nécessaire : la résolution par égalité de chaînes fonctionne
pour les vieux fichiers, les nouveaux, ET notre dialecte (notre `generer_xml` remplit déjà `NodeL`
avec les mêmes chaînes que `CFirst`/`CLast`). Le fallback `_analyser_ref_noeud` n'est utilisé que
pour un fil dont aucune extrémité ne trouve de correspondance NodeL.

**Non-régression absolue :** le dialecte natif (fichiers produits par `generer_xml`, dont ceux de
l'éditeur) doit continuer à produire exactement les mêmes composants/nets — la suite existante
(~1683 tests) est le garde-fou.

## 3. Reconstruction de la connexité (règle exacte)

C'est la règle que le C# d'ERetroDesign applique lui-même (Form1.cs, partout) : un fil (`Line`)
appartient à la broche dont la liste `NodeL` contient **la chaîne exacte** de son extrémité
(`CFirst` ou `CLast`). On ne parse **jamais** le format packé des refs (il a changé au fil du temps
et le format concaténé est ambigu — `14001` est indécodable sans les largeurs de champs).

- Index préalable : `{chaîne_ref → (index_composant, index_broche)}` construit en balayant tous les
  `datapin/NodeL/string` de tous les composants (après aplatissement des composés).
- Chaque `Line` devient une arête Union-Find entre les deux broches résolues.
- Préfixes rencontrés dans les refs : `T` (composant composé), `C` (item interne), `X` (broche
  interne de composé) — tous traités par la même égalité de chaînes, aucun cas particulier.
- Extrémité non résolue (chaîne absente de tout NodeL, ou vide) : le fil est ignoré pour cette
  extrémité et un avertissement est ajouté (`"Fil non résolu : CFirst='…'"`). Jamais d'exception.
- Fallback : si les NodeL du fichier sont tous vides (fichier dégradé), on retombe sur
  `_analyser_ref_noeud` comme aujourd'hui.

## 4. Aplatissement des puces composées (`CCmpntL`)

Un `CComp` = un `DataItem` (boîtier, broches externes avec `NodeL`) + `DItemL` (items internes,
chacun avec ses propres broches/`NodeL`) + `CCLine` (fils internes, refs préfixées `C`/`X`).

Règle d'aplatissement (décision brainstorming : **déplier**, la valeur d'analyse est à l'intérieur) :

1. Chaque item interne devient un composant à part entière dans la liste globale ; sa référence est
   préfixée par la puce (`U3` → items `U3.1`, `U3.2`, …). Le **nom de la puce est conservé** dans
   une table exposée sur la liste retournée, même idiome que `.warnings` :
   `composants.groupes_puces = {'U3': 'CD4011', …}` — les vues peuvent afficher « dans CD4011 »
   sans nouveau champ sur `Composant`.
2. Les `CCLine` sont ajoutés à la liste globale des fils — la résolution par égalité NodeL les
   traite comme les autres.
3. Les refs `X` (broche interne ↔ broche externe du boîtier) créent une arête Union-Find entre la
   broche externe et le net interne : les connexions du schéma principal vers la puce traversent
   ainsi le boîtier jusqu'aux portes internes.
4. **Dégradation jamais bloquante :** un composé sans intérieur lisible (DItemL vide ou
   incohérent) est importé comme **boîte noire** avec ses broches externes + un avertissement.

## 5. Mapping des types

Nouvelle table déclarative dans `eretro.py` (`_MAPPING_ERETRO`), consultée quand le nom n'est pas
dans `_NOM_VERS_TYPE`. Correspondance **tolérante** : minuscules, accents retirés, espaces
multiples repliés (« Resistance  Trad » == « resistance trad »).

| Noms bibliothèque ERetroDesign | Type app |
|---|---|
| `resistance trad`, `resistance cms`, `pot`, `thermistance`, `varistance` | R |
| `condo`, `condo cms` | C |
| `inductance` | L |
| `diode`, `zener`, LEDs | D |
| `npn`, `transistor npn` | Q (NPN) |
| `transistor pnp` | Q (PNP) |
| `mosfet`, `mosfet p`, `mosfet p1` | M |
| `fusible` | F |
| `relais 2rt` | K |
| Puces nommées (`NE555`, `LM324`, `TL084`, `tl082`, `LM339`, `LM1458`, `CD40xx`, `ULN2024`, `HCPL312`, `HI-200`, régulateurs…) | U — identité par nom via `identifier()` du catalogue existant ; leurs libs portent de vrais `Pnumber`/`Pname` (ex. NE555 broche 2 = TRIGGER) qui alimentent l'aliasing catalogue |
| Alimentations (typ `G`/`V`/`N` ou nom rail) | rails GND / VCC / -VCC — mêmes règles que `_NOMS_ALIMENTATION`/`nom_net` existants, étendues au champ `typ` |
| Tout le reste (`transfo`, `opto`, `IGBT`, `BUFFER` isolé…) | X — boîte générique avec broches, **jamais supprimée**, warning existant conservé |

La valeur (`value`) est reprise telle quelle (texte libre, comme aujourd'hui). Ajouter un mapping
plus tard = une ligne dans la table.

## 6. Intégration GUI

**Aucun nouveau bouton.** Le flux existant Analyser → Parcourir ouvre le fichier tel quel (même
racine `<BoardSCH>`, même `lire_xml`). Après import, si `composants.warnings` est non vide, le
résumé est présenté à l'utilisateur (réutiliser l'affichage d'avertissements existant de l'onglet
Analyser s'il existe ; sinon un encart compact) : « N composants importés, X inconnus gardés en
boîtes, Y connexions non résolues », avec le détail déroulable. L'analyse s'affiche ensuite dans
les vues existantes — l'import EST la fonctionnalité, pas de nouveau format de sortie.

## 7. Gestion d'erreurs

- Fichier XML invalide → `ValueError` avec message clair (comportement actuel conservé).
- Tout le reste **ne lève jamais** : broche sans NodeL, fil non résolu, composé illisible, champ
  manquant (vieux fichiers : `Pnumber` vide, `pGap` absent…), `id` dupliqués → import au mieux +
  avertissement agrégé. Un fichier réel de 2,4 Mo plein de bizarreries doit s'ouvrir.

## 8. Tests

Unitaires (`tests/test_eretro.py`, fixtures BoardSCH synthétiques écrites à la main) :

1. Connexité par égalité NodeL : 2 composants, 1 fil, refs **sans** underscore → 1 net commun.
2. Vieux format concaténé réaliste (refs `2011`-style, `T`-refs) → nets corrects.
3. `id=0` partout → indexation par position, aucun composant écrasé.
4. Aplatissement d'un composé simple (boîtier + 2 portes internes + 1 fil interne) → composants
   `U1.1`/`U1.2`, net interne correct, nom de puce conservé.
5. Ref `X` : broche externe du composé fusionnée avec le net interne (le signal traverse le boîtier).
6. Composé sans intérieur lisible → boîte noire + warning, pas d'exception.
7. Mapping : un cas par famille (resistance trad→R, condo→C, npn→Q, zener→D, mosfet p→M,
   fusible→F, relais→K, NE555→U reconnu par `identifier()`, transfo→X avec warning).
8. Alimentations typ `G`/`V` → rails GND/VCC, exclues des composants comme aujourd'hui.
9. Fil à extrémité non résolue → warning, le reste du fichier importé.

Intégration (corpus réel, fichiers en place dans
`SolutionERetroDesignX20260813/ERetroDesign/ERetroDesign/bin/Debug/`) :

10. `SaveDiag.xml` : import sans erreur, nombre de composants attendu, `analyser()` passe.
11. `Diag2.xml` : idem + au moins un îlot non vide.
12. `TestDiagram.xml` (2,4 Mo, vraie carte) : import + analyse complète **sous 30 s**, zéro exception.
13. Non-régression dialecte natif : la suite existante reste verte (mêmes nets sur les fichiers
    produits par `generer_xml`).

**Boucle visuelle (exigence maison) :** rendre en PNG les îlots d'une carte réelle importée
(`Diag2.xml` et un extrait de `TestDiagram.xml`), inspecter avant tout commit touchant au dessin.

## 9. Hors périmètre (chantier 2 et plus tard)

- Export vers le format ERetroDesign (round-trip éditeur) — spec séparée à venir.
- Import vers le canvas de NOTRE éditeur (positions/symboles) — analyse seulement pour l'instant.
- Toute modification du projet C# `SolutionERetroDesignX20260813/` (lecture seule, jamais commité
  par nous).
- Analyse des composants hors périmètre impédances (relais, transfo… restent des boîtes).

## 10. Contraintes globales

- `schemdraw==0.22` épinglé ; `PYTHONUTF8=1` devant chaque commande python/pytest.
- Canvas des schémas reste clair ; aucun hex en dur dans le chrome (tokens `theme.py`).
- Commits en français, sans footer « Co-Authored-By »/« Generated with » ; `git add` fichier par
  fichier ; ne jamais toucher `docs.rar` ni `SolutionERetroDesignX20260813/`.
- Suite complète verte à chaque tâche (`test_500_portes_sous_budget` : flake connu sous charge,
  relancer isolé).
