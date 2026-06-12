# Design — Export XML organisé par circuit détecté

Date : 2026-06-08
Statut : approuvé (design), en attente de revue du spec écrit

## Problème

`components_to_xml()` (dans `circuit_analyzer/xml_generator.py`) place actuellement
les composants sur une grille naïve :

```python
x = 250 + (i % PER_ROW) * COL_W
y = 250 + (i // PER_ROW) * ROW_H
```

L'ordre est celui de la liste `components`, sans rapport avec la topologie. Le
schéma exporté (ouvert dans l'application de design) est donc désorganisé : les
composants d'un même circuit (ex. les 3 éléments d'un ampli inverseur) sont
dispersés, les fils se croisent inutilement. L'utilisateur veut un schéma
**regroupé et un peu organisé**.

## Décisions validées

1. **Regroupement par circuit détecté.** On lance le matcher sur les composants ;
   chaque pattern reconnu (`Amplificateur inverseur (AOP)`, `Filtre RC passe-bas`,
   etc.) devient un **bloc visuel** contenant ses composants. Les composants
   qu'aucun pattern ne revendique vont dans un bloc **« Divers »**.

2. **Symboles d'alimentation globaux.** Un seul symbole par net d'alimentation
   distinct (GND, VCC, VMOT_48V, …), partagé par tous les blocs, placé dans une
   **rangée d'alimentation** sous les blocs. On accepte des fils plus longs qui
   traversent le schéma. C'est déjà la logique actuelle (un symbole par net) ;
   on ne change que le **placement**, pas le nombre de symboles.

## Architecture visuelle

```
┌─ Filtre RC passe-bas ─┐  ┌─ Ampli inverseur (AOP) ─┐  ┌─ Transistor commut. ─┐
│  R1 ── C1             │  │  R2   U1   R3            │  │  Q1   R4             │
└───────────────────────┘  └─────────────────────────┘  └──────────────────────┘
┌─ Divers ──────────────────────────────────────────────────────────────────────┐
│  R9   D2   L1                                                                   │
└────────────────────────────────────────────────────────────────────────────────┘
─── Rangée d'alimentation (symboles globaux, un par net) ───
   GND        VCC        VMOT_48V        AGND ...
```

## Composants et responsabilités

### 1. `_layout_groups(components, results) -> list[_Block]`  *(nouveau)*

Fonction pure (sans effet de bord), testable isolément.

- Entrée : la liste `components` et `results` (sortie de `match_patterns`, chaque
  item = `{'circuit_type': str, 'components': [ref, ...], 'nodes': [...]}`).
- Construit un mapping `ref -> circuit_type` à partir de `results` (premier pattern
  qui revendique le ref — le matcher garantit déjà l'exclusivité via `locked`).
- Regroupe les composants **dessinables** (type présent dans `_TYPE_TO_SHAPE`) par
  `circuit_type` ; les composants sans pattern → bloc `"Divers"`.
- Retourne une liste de blocs `_Block(label: str, comps: list[Component])`, dans
  un ordre déterministe (patterns dans l'ordre de `results`, « Divers » en dernier).

### 2. `_place_blocks(blocks) -> dict[ref, (x, y)]`  *(nouveau, ou inline)*

Calcule la position absolue de chaque composant.

- Les blocs sont disposés sur une **grille de blocs** (`BLOCKS_PER_ROW = 3`).
- À l'intérieur d'un bloc, les composants sont alignés horizontalement
  (espacement `COL_W`), enveloppés au besoin sur plusieurs lignes si le bloc est
  large.
- La hauteur d'une rangée de blocs s'adapte au bloc le plus haut.

### 3. `components_to_xml(components, results=None)`  *(signature étendue)*

- **Rétrocompatible** : `results=None` → comportement grille actuel inchangé
  (les appelants existants — `netlist_to_xml.py`, tests round-trip — continuent
  de fonctionner sans modification).
- `results` fourni → utilise `_layout_groups` + `_place_blocks` pour positionner
  les composants signal, puis applique la **logique d'alimentation existante**
  (un symbole par net, repositionné dans la rangée d'alimentation sous le bloc le
  plus bas).
- Le câblage des nets (regroupement par net, chaînage des broches, symboles
  d'alim) reste **identique** : seules les coordonnées `CtrIem` changent.

### 4. `gui/tab_analyze.py` — `_export_xml`

Passe `self._results` (déjà stocké lors de l'analyse) à `components_to_xml` :

```python
xml = components_to_xml(self._comps, results=self._results)
```

## Flux de données

```
components ──┐
             ├─► match_patterns ──► results ──► _layout_groups ──► blocks
             │                                                       │
             │                                              _place_blocks
             │                                                       │
             └──────────────────────────► positions (ref → x, y) ◄───┘
                                                  │
                          net grouping + power symbols (logique existante)
                                                  │
                                                  ▼
                                            BoardSCH XML
```

Remarque : `_export_xml` a déjà `results` sous la main ; `netlist_to_xml.py`
peut soit passer `results`, soit rester en mode grille. On lui fera passer
`results` pour bénéficier du regroupement.

## Ce qui ne change PAS

- Le format XML (`<DataItem>`, `<Line>`, `CFirst`/`CLast`).
- La logique des symboles d'alimentation (déjà un par net, préservant les noms
  de rails distincts).
- L'analyse / le matcher : le regroupement n'affecte que des coordonnées
  visuelles, jamais la connectivité. Le round-trip (XML relu → mêmes patterns)
  reste donc valide par construction.

## Gestion des cas limites

- **Composant dans plusieurs patterns** : impossible — le matcher verrouille
  (`locked`) chaque ref dans un seul pattern. On prend le premier quand même par
  sécurité.
- **Aucun pattern détecté** : tous les composants vont dans « Divers » → un seul
  bloc, équivalent visuel d'une grille propre.
- **Composant non dessinable** (type absent de `_TYPE_TO_SHAPE`) : ignoré comme
  aujourd'hui, jamais placé.
- **Net partagé entre deux blocs** : géré par le symbole d'alim global / le
  chaînage de net existant — la position des broches est juste plus éloignée.

## Stratégie de test

Ajouts à `tests/test_xml_generator.py` :

1. **Regroupement** : un circuit à 2 patterns → chaque composant du pattern A est
   spatialement proche des autres de A, séparé du bloc B (vérifier via les `CtrIem`
   ou indirectement via `_layout_groups`).
2. **Bloc « Divers »** : un composant non revendiqué → présent dans le bloc
   « Divers ».
3. **Rétrocompatibilité** : `components_to_xml(comps)` (sans `results`) produit la
   même sortie qu'avant (grille).
4. **Round-trip préservé** : `components_to_xml(comps, results=match_patterns(...))`
   relu → mêmes patterns détectés que l'original (le regroupement ne casse aucune
   connexion).
5. **`_layout_groups` isolé** : test unitaire pur sur le mapping
   ref → bloc, sans XML.

Tous les 156 tests existants doivent continuer à passer (rétrocompatibilité).
