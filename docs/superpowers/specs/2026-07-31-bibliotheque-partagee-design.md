# Bibliothèque partagée avec ERetroDesign — conception

**Date :** 2026-07-31
**Branche :** `rewrite-simple`
**Décision du boss :** sa `LibItem/Lib/` devient la source de vérité du dessin des deux côtés.

## Le problème, tel qu'il est réellement

Le boss a formulé ainsi : *« notre app et ERetroDesign ne parlent pas la même
langue car on n'a pas les mêmes bibliothèques »*. La mesure a confirmé
l'intuition, mais pas le diagnostic.

**Nos deux bibliothèques portent les mêmes noms, le même repère et la même
échelle.** Ce sont deux copies **divergées** de la même bibliothèque.

Sa bibliothèque vivante, `bin/Debug/LibItem/Lib/`, contient 16 symboles :

```
2N2B  AOP  Capa  Diode  Gate2  GND  NOT  OR
Potentiomètre  Résistance  Self  TATA  VCC-  VCC+  Vss  yoyo
```

Nos `_FORME` (`circuit_analyzer/xml.py:36`) en portent 19, dont 8 de même nom.
Sur ces 8, **3 dessins sont identiques au point près et 5 ont divergé** :

| Symbole | Lui | Nous | |
|---|---|---|---|
| `2N2B` | X[-36,36] Y[-48,48] | X[-36,36] Y[-48,48] | identique |
| `Capa` | X[-48,48] Y[-48,48] | X[-48,48] Y[-48,48] | identique |
| `Self` | X[-80,80] Y[0,0] | X[-80,80] Y[0,0] | identique |
| `Résistance` | X[-80,80] Y[-11,11] | X[-80,80] Y[-22,22] | divergé |
| `AOP` | X[-80,80] Y[-48,48] | X[-72,72] Y[-48,48] | divergé |
| `Diode` | X[-78,78] Y[-48,48] | X[-80,80] Y[-30,30] | divergé |
| `GND` | X[-80,80] Y[-47,47] | X[-72,72] Y[-48,12] | divergé |
| `Vss` | X[-80,80] Y[-14,15] | X[-80,80] Y[-32,32] | divergé |

Et chacun possède ce que l'autre n'a pas :

- **lui seulement** : `Gate2`, `NOT`, `OR`, `Potentiomètre`, `TATA`, `VCC+`, `VCC-`, `yoyo`
- **nous seulement** : `AGND`, `Fusible`, `MOSFET`, `Puce4/8/14/16`, `Relais`, `Relais_1FormC`, `Transistor`, `VCC`

Ses noms de broches sont déjà les nôtres — nos plans de `_TYPE_VERS_FORME`
ont manifestement été construits depuis sa bibliothèque :

| Symbole | Ses broches | Notre plan |
|---|---|---|
| `AOP` | `+`, `-`, `s` | `{"IN+": "+", "IN-": "-", "OUT": "s"}` |
| `2N2B` | `G`, `E`, `C` | `{"B": "G", "C": "C", "E": "E"}` |
| `Résistance` | `1`, `2` | `{"1": "1", "2": "2"}` |
| `Capa` | `-`, `+` | `{"1": "+", "2": "-"}` |

### Deux fausses pistes, écartées par la mesure

**`bin/Debug/Lib/` (57 symboles) est un fonds mort.** Son
`[MODIF 2026-07-24]` (`Form1.cs:6104`) a basculé la bibliothèque sur
`LibItem/Lib/`, un fichier par composant. Les symboles de l'ancien dossier
mesurent ~997 × 201 unités, ne sont pas centrés, n'ont ni `Name` ni `typ`, et
leurs broches passives n'ont pas de nom. Sur les 36 noms distincts employés par
ses 4 vraies cartes, **2 seulement** s'y trouvent.

**Il n'y a aucun problème d'échelle.** `InsertItem` (`Form1.cs:4712`) copie la
géométrie verbatim — `obj.point = item.datapolygon[i].point` — sans
renormaliser. Ses symboles vivants sont donc déjà exprimés en coordonnées de
carte (±80), les mêmes que les nôtres.

### Un troisième vocabulaire : celui de ses cartes existantes

Ses 4 vraies cartes n'emploient **ni** le vocabulaire de l'ancien `Lib/`, **ni**
celui de `LibItem/Lib/`. Elles portent `R 1001`, `R 810`, `Condensateur`,
`Transistor_NPN`, `RINF`, `Led` — un état antérieur de sa bibliothèque, avec la
valeur encodée dans le nom (`R 3R90`, `R 47R0` = codage E96).

**Décision : à l'export on écrit les noms de sa bibliothèque VIVANTE**
(`Résistance`, `Capa`, `AOP`…), pas ceux de ses vieilles cartes. Raison : c'est
sa palette actuelle, donc le seul vocabulaire avec lequel il peut poser,
remplacer ou retrouver un composant aujourd'hui. Le vocabulaire ancien reste
traité **en lecture** par `_MAPPING_ERETRO` (chantier « dialecte » déjà livré),
et rien de ce qui suit ne le modifie.

## Objectif

Une seule bibliothèque, la sienne, lue par notre application ; nos symboles
orphelins poussés chez lui. Les schémas doivent devenir lisibles **dans les deux
applications**.

## Architecture

### Module `circuit_analyzer/eretro_symboles.py` (neuf)

Responsabilité unique : lire sa `LibItem/Lib/*.xml` et l'exposer dans la forme
que `_FORME` consomme déjà.

```python
def charger(dossier: str | None = None) -> dict[str, dict]:
    """nom -> {"pins": {nom: (dx, dy, idx)}, "polygon": str,
               "segment": str, "arc": str, "typ": int}"""

def chemin_par_defaut() -> str | None:
    """Dossier de bibliothèque, ou None s'il est introuvable."""
```

Ne dépend que de la bibliothèque standard. C'est `xml.py` qui dépend de lui —
jamais l'inverse, sous peine d'import circulaire.

### Résolution et repli

```python
_FORME = {**_FORME_MAISON, **eretro_symboles.charger()}
```

Son symbole l'emporte quand il existe, le nôtre sinon. Le chemin vient de la
variable d'environnement `ERETRO_LIB`, sinon d'un défaut relatif au dépôt.

**Le `typ`, lui, ne suit PAS le symbole.** C'est la géométrie qu'on partage, pas
la sémantique électrique. `_TYP_COMPOSANT` reste l'autorité, et le `typ` de son
symbole ne sert qu'à combler une entrée absente (`setdefault`).

Raison mesurée : son `GND.xml` porte `typ=0`, alors que le nôtre vaut 71
(`'G'`) — précisément la valeur dont `eretro.classer_rail` se sert pour
reconnaître un rail de masse. Adopter son `typ` ferait perdre la classification
des masses et des alimentations sur tous nos exports. Ses `Résistance` (0) et
`Diode` (32) sont dans le même cas.

**Le chargeur ne lève jamais d'exception.** Dossier absent → repli complet sur
nos formes et une ligne de log. Symbole illisible → ignoré, les autres se
chargent quand même. C'est la contrepartie assumée de la lecture directe : sans
ce repli, la CI (qui n'a pas son dossier) et le `.exe` livré n'auraient plus un
seul symbole.

## Ce que l'export corrige

Deux défauts mesurés sur des schémas produits par `generer_xml` puis
désérialisés avec **son** `XmlSerializer` :

| Défaut | État actuel | Correctif |
|---|---|---|
| Référence absente | `<reference />` vide sur tous les composants | écrire `comp.ref` (R1, U1…) |
| Composant fantôme | un `GND` devient un boîtier `Puce4` | ajouter `GND`/`VCC`/`VSS` à `_TYPE_VERS_FORME` |

### `TL`/`BR` : faux positif, corrigé après mesure

Une première lecture avait pris `<TL>50,25</TL><BR>210,121</BR>` (`xml.py:476`)
pour une boîte de clic codée en dur par négligence. La mesure dit le contraire :
ces deux valeurs figurent sur **les 209 composants posés de ses 4 cartes** et sur
**la totalité de ses symboles de bibliothèque**. C'est une constante de son
format — la boîte cliquable de la vignette de palette, déjà documentée dans
`eretro_lib.py:37-45` (« à TL=BR=(0,0) le composant s'affiche dans la palette
mais est IMPOSSIBLE à sélectionner »).

**Notre générateur écrit donc déjà la bonne valeur. Ne pas y toucher.**

Le fantôme vient de `xml.py:829` : `_TYPE_VERS_FORME` n'a pas d'entrée `GND`,
donc un `Composant("GND1","GND",{"1":"GND"})` tombe dans la branche « toutes
les broches numérotées » — `"1"` est un chiffre — et devient un DIP 4 broches.

La géométrie écrite devient la sienne, verbatim.

## Rendu de notre côté

Un élément schemdraw générique, construit depuis sa géométrie :

| Sa donnée | schemdraw |
|---|---|
| `datasegment` | `Segment([(x1,y1), (x2,y2)])` |
| `datapolygon` | `SegmentPoly([...])` |
| `dataarc` | `SegmentArc(...)` |
| `datapin` | ancres nommées |

Échelle : ses ±80 divisés par 80 donnent une portée de 2,0, proche de la
longueur d'élément par défaut de schemdraw.

**Point dur identifié :** nos drawers s'appuient sur la sémantique schemdraw
(`.reverse()`, `.theta()`, ancres `start`/`end`). Un élément générique doit
exposer ces ancres, faute de quoi chaque drawer casse. C'est là que vivent les
~3 300 lignes de tests de rendu, et c'est pourquoi cette partie fait l'objet
d'un plan distinct.

## Pousser nos orphelins chez lui

`circuit_analyzer/eretro_lib.py` fait déjà l'export composant → Lib XML. On le
réutilise pour écrire nos 11 symboles absents de sa bibliothèque.

**Écriture gardée :** seulement si le dossier existe, seulement si le fichier
n'y est pas déjà. On n'écrase jamais un symbole à lui. Réserve connue et non
levée : le rendu de nos symboles côté C# n'a jamais été validé visuellement.

## Tests

| Objet | Ce qui est vérifié |
|---|---|
| Chargeur | les 16 symboles réels se chargent (`skipif` si dossier absent) ; noms de broches et bornes géométriques conformes |
| Repli | dossier absent → nos formes, aucune exception |
| Robustesse | un symbole corrompu est ignoré, les autres se chargent |
| Export | `reference` remplie, plus aucun `Puce4` fantôme, `TL`/`BR` inchangés à (50,25)/(210,121) |
| Sonde C# | les schémas se désérialisent, aucun composant muet, aucune boîte dégénérée |
| Non-régression | le retour fidèle des 4 vraies cartes reste intact à l'octet près |

La sonde C# (harnais net472 du scratchpad, qui référence son vrai binaire) est
la seule preuve qui vaille sur une question de format : la faire compiler prouve
déjà que les champs existent avec les bons types.

## Découpage en deux plans

**Plan 1 — chargeur et export.** Module `eretro_symboles.py`, résolution et
repli, les deux correctifs d'export, poussée des orphelins. Autonome et
testable ; son résultat s'ouvre dans son éditeur immédiatement.

**Plan 2 — rendu.** Élément schemdraw générique construit depuis sa géométrie.
Consomme le chargeur du plan 1. Aura sa propre conception, parce que c'est là
que se trouve tout le risque de régression visuelle.

## Contraintes de projet

- Commits en français, jamais de `Co-Authored-By: Claude`.
- Jamais `git add -A` ; fichiers ajoutés un par un.
- Ne jamais committer `custom_circuits.json` ni `component_library.json`.
- `ERetroDesign/`, `CARTE POUR TESTER (VRAI TEST)/`, `docs.rar`, `dist_demo/`,
  `test14.xml` : lecture seule, jamais committés.
- `PYTHONUTF8=1` sur toutes les commandes pytest.
- `schemdraw==0.22` pinné (0.23 casse ~30 tests de rendu).
- Branche `rewrite-simple` ; rien n'est poussé sans accord explicite.
- Le boss exige des PNG rendus **et inspectés** après toute modification de
  dessin — ce qui vaudra surtout pour le plan 2.

## Réserves

1. Le rendu de nos symboles poussés dans sa bibliothèque n'est pas validé côté
   C# (réserve héritée de `eretro_lib.py`).
2. `TATA` et `yoyo` ressemblent à des symboles d'essai ; `TATA` porte des
   broches à ±400, hors de l'échelle commune. Ils sont chargés comme les
   autres, sans traitement particulier — à revoir s'ils polluent la palette.
3. La lecture directe de son dossier reste fragile par nature (le même piège
   que `ImageTop` dans ses cartes : un chemin absolu qui casse dès qu'on
   déplace quoi que ce soit). Le repli est ce qui rend ce choix tenable.
