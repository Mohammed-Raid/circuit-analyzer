# Retour fidèle vers ERetroDesign (chantier A) — Design

**Date :** 2026-07-29
**Statut :** design présenté, en attente de relecture spec avant plan.

> ## ⚠️ ARBITRÉ LE 2026-07-30 — CE DOCUMENT EST PÉRIMÉ SUR UN POINT
>
> **Tout ce qui suit et qui décrit l'écriture de `<Begrp>` / `<BeIngrp>` est
> FAUX.** La v1 livrée n'écrit **que `<GpId>`**, jamais les drapeaux.
>
> **Pourquoi.** La Task 7 a sondé le vrai C# (harnais net472 contre
> `ERetroDesign.exe`). Dans son modèle, `<GrpL>` est la liste de membres
> **faisant autorité** ; `GpId`/`Begrp`/`BeIngrp` ne sont que des
> rétro-pointeurs. Or `Begrp=true` **interdit la sélection individuelle** d'un
> composant (`ERetroDesign/ERetroDesign/Forms/Form1.cs:2192, 2269, 2337, 2697,
> 3767, 5510`) et `SelectGroup` (`Form1.cs:9036`) balaye `GrpL`. Poser les
> drapeaux sans écrire `<GrpL>` aurait rendu les composants groupés **inertes**
> chez lui : ni sélectionnables un par un, ni en groupe.
>
> Les sections concernées sont §« Ce qu'on écrit », §« Invariant de test » et
> §« Réserve `<GrpL>` ». En particulier, l'invariant y autorise `{GpId, Begrp}`
> alors que le gardien réel (`_CHAMPS_GROUPE` dans `tests/test_eretro_patch.py`)
> est resserré à `{"GpId"}` — **suivre la spec réintroduirait la régression que
> ce resserrement sert justement à attraper.**
>
> **Source de vérité :** la docstring de `ecrire_groupes`
> (`circuit_analyzer/eretro_patch.py`). Le reste de ce document — patcher
> l'arbre plutôt que régénérer, le pont `ref → élément`, la capture d'en-tête,
> les 4 niveaux de validation — reste valable.

## Context (pourquoi)

Le pipeline de lecture est **à sens unique et destructeur**. `lire_xml`
(`circuit_analyzer/xml.py:1158`) extrait des `Composant` qui ne portent que
`ref, type, pins, value, par_forme, boite_ic` (`composant.py:103`) : **aucune
position, aucune forme, aucun angle, aucun zoom**. La connectique est *déduite*
par Union-Find sur l'égalité des chaînes `NodeL` — le reste du fichier est lu
puis jeté.

À l'export, `generer_xml` (`xml.py:799`) **réinvente tout** : positions sur une
grille de 4 par rangée, nos propres `datasegment`, et `<zmH>1</zmH><zmV>1</zmV>`
en dur (`xml.py:477`). Or ses vraies cartes portent un zoom **par composant**
(0,15 à 1,0, dont un cas non uniforme `0,55 / 0,50`) et des angles 0/90/180/270.

Conséquence concrète : le collègue nous envoie sa carte, on la lui renvoie
**méconnaissable**. C'est un défaut d'interopérabilité, pas d'affichage.

## Décisions verrouillées (arbitrage boss, 2026-07-28)

| Question | Décision |
|---|---|
| Objectif | **Aller-retour fidèle** : sa carte revient intacte (positions, symboles, angles, fils). Nos vues gardent le schéma assaini (colonnes, îlots, blocs Z). |
| Contenu de l'export Analyse | **Sa carte intacte + les groupes** : on n'ajoute QUE l'information d'analyse (quel composant appartient à quel montage détecté). |
| Onglet Dessin | Éditeur fidèle aussi — **hors périmètre v1**, voir §Non-goals. |
| Technique | **Patcher l'arbre d'origine**. Jamais de régénération. |

## Non-goals (v1)

- **Chantier B (éditeur fidèle)** : charger les vraies positions dans
  `gui/schematic_editor.py`, gérer la conversion d'échelle et les rotations,
  réexporter. Chantier séparé, bien plus gros.
- Pas de modification de `generer_xml` : il reste le chemin des schémas **créés
  chez nous** (onglet Dessin, analyse partie d'un `.net`).
- Pas de `<GrpL>` en v1 (voir §Réserve).
- Pas de touche au code C# ERetroDesign.

## Architecture

### 1. Ce qui manque : le pont `ref → élément XML`

`lire_xml` connaît déjà les deux moitiés du pont mais n'en rend aucune :

- `cid → élément` : les `DataItem` sont indexés **par position**
  (`enumerate(racine.findall(...))`, `xml.py:1184`) — indispensable, car les
  vraies cartes ont `<id>0</id>` partout.
- `cid → ref` : produit par `generer_ref` (`xml.py:1401`).

On expose donc un attribut **additif** sur `ListeComposantsXML` (`xml.py:1093`),
dans le même esprit que `.warnings` et `.groupes_puces` :

```python
composants.source = SourceXML(arbre=arbre, elements={ref: element})
```

Aucune signature ne change ; le code existant qui traite le retour comme une
`list` continue de marcher.

### 2. Un module qui ne fait qu'une chose

`circuit_analyzer/eretro_patch.py` :

```
lire_xml(chemin)  ──►  ListeComposantsXML
                         .warnings, .groupes_puces   (existant)
                         .source                     ← NOUVEAU

tab_analyze._export_xml()
   ├─ .source présente  → eretro_patch.ecrire_groupes(source, composants, resultats)
   └─ pas de source     → generer_xml()  +  AVERTISSEMENT à l'écran
```

`ecrire_groupes` réutilise `_grouper_par_circuit` (`xml.py:553`) et
`_ids_groupes_par_ref` (`xml.py:786`) **sans les modifier**, puis écrit
uniquement, sur les éléments d'origine :

- `<GpId>` = identifiant du montage (1..n, 0 = non groupé) ;
- `<Begrp>` = `true` si `GpId != 0` ;
- `<GpId>` sur une `<Line>` quand ses **deux** extrémités tombent dans le même
  groupe.

Tout le reste ressort tel quel : `CtrIem`, `TL`, `BR`, `angle`, `zmH`, `zmV`,
`datasegment`, `datapin`, `NodeL`, `Flip`, `typ`, **et toutes les balises qu'on
ne comprend pas** — parce qu'on ne les réécrit jamais.

### 3. Puces composées

Vérifié sur `PowtranAlim20260809.xml` : un `<CComp>` porte la **même enveloppe**
qu'un `DataItem`, `GpId` et `Begrp` compris (`Name = Optocoupleur_simple`,
`zmH = 0.799999952`, `DItemL/DataItem = 2`).

Règle : **on ne touche jamais aux `DItemL`**. Un composé est un objet unique posé
sur sa carte ; le grouper par ses entrailles n'aurait pas de sens chez lui. Le
`GpId` va sur le `<CComp>` lui-même, décidé **à la majorité** de ses composants
internes (`U7.1`, `U7.2`…). Égalité ou absence de majorité ⇒ pas de groupe.

### 4. Cas limites, tous à comportement explicite

| Cas | Comportement |
|---|---|
| Analyse partie d'un `.net` (pas de source XML) | Repli sur `generer_xml`, **avec avertissement à l'écran** |
| Composant du fichier qu'aucun circuit ne réclame | Laissé tel quel, `GpId` inchangé |
| Composant absent de la source | Impossible en Analyse (lecture seule) — verrouillé par un test |
| Balise inconnue de nous | Jamais réécrite, donc jamais perdue |

### 5. Ce que « intact » veut dire exactement

`ElementTree` **re-sérialise le document entier** même pour un seul champ
modifié : ordre des attributs, balises auto-fermantes (`<Group />` vs
`<Group/>`), espaces, déclaration XML peuvent différer. Ce qui est garanti,
c'est que **toutes les valeurs** sont préservées, **pas la suite d'octets**. Son
`XmlSerializer` C# s'en moque ; un `diff` de fichiers, non — d'où la validation
arbre-à-arbre ci-dessous.

## Validation

1. **Invariance sur les 4 vraies cartes.** Lire, patcher, relire, comparer
   **arbre à arbre** : chaque `CtrIem`, `TL`, `BR`, `angle`, `zmH`, `zmV`,
   `datasegment`, `datapin`, `NodeL`, `Line` identique à la source. Seul delta
   autorisé : `{GpId, Begrp}`. Échoue au moindre champ oublié, y compris ceux
   qu'on ne connaît pas encore.
2. **Netlist stable.** `lire_xml(patché)` produit exactement les mêmes
   `Composant` que `lire_xml(source)`. Un `NodeL` cassé changerait la connexité
   et ce test le verrait.
3. **Désérialisation par son vrai code C#.** Un mini-projet net472 référençant
   son `ERetroDesign.exe` (`ERetroDesign/` à la racine, lecture seule) avale un
   fichier patché. Seule preuve qui vaille sur un format d'échange. **À
   recréer** : le harnais monté en session vit dans le scratchpad temporaire,
   pas dans le dépôt — hors dépôt volontairement, il ne se committe pas.
4. **Ouverture à la main dans son app** avant de déclarer le chantier fini.

## Réserve connue : `<GrpL>`

Aucune de ses 4 cartes ne contient de `<GrpL>`, et tous les `GpId` y valent `0` —
il n'utilise pas le groupement aujourd'hui. Notre générateur, lui, émet un
`<GrpL>` avec un rectangle englobant (`_rect_groupe`, `xml.py:404`).

Il est donc **possible** qu'un `GpId` sans `<GrpL>` soit invisible côté C#. On ne
devine pas : v1 écrit `GpId`/`Begrp` seuls, la validation n°3 tranche, et
`<GrpL>` n'est ajouté que si la preuve l'exige. Raison de ne pas l'écrire à
l'aveugle : `TL 50,25` / `BR 210,121` pour un `CtrIem 168,330` (carte `PG 2`)
montre que `TL`/`BR` ne sont **pas** dans le repère de `CtrIem`. Fabriquer un
rectangle sur cette base serait une invention de plus — exactement ce que ce
chantier supprime.

Si `<GrpL>` s'avère nécessaire, il s'insère **après `<CCmpntL>`, avant
`<zoom>`** : `XmlSerializer` est sensible à l'ordre des éléments de séquence.
