# Disposition canonique — rôles multi-composants série/parallèle/fan-in — Design

**Date :** 2026-08-13
**Statut :** design validé en conversation, prêt pour le plan d'implémentation.

**Suite de :**
[2026-08-13-disposition-canonique-quatre-montages.md](2026-08-13-disposition-canonique-quatre-montages.md)
(migration des 4 montages, qui a d'abord introduit un correctif ponctuel —
« sauter la colonne 2 » — pour éviter qu'un Zin/Z1 à 3+ entrées ne
chevauche l'AOP). Ce chantier remplace ce correctif ponctuel par une vraie
disposition, motivé par un test réel sur `test_pid_3.xml` (export
`ecrire_groupes` → ERetroDesign, capture d'écran fournie par le boss) :

- L'Intégrateur de cette carte a un Zf **réellement parallèle**
  (`composition: '(C1//R6)'`, un intégrateur « qui fuit » — C1 et R6
  pontent tous deux IN- et OUT) mais notre positionneur le dessine comme
  une CHAÎNE (une rangée), ce qui implique visuellement une série. Un des
  4 fils entre {U2, C1, R6} tombe alors en diagonale (aucun candidat en L
  ne passe, faute de place cohérente avec un layout en chaîne).
- Le Sommateur de la même carte a 3 entrées indépendantes (Zin est une
  LISTE, `R8/R9/R10`), actuellement étalées en rangée horizontale à côté
  de l'AOP — ce qui a motivé plus tôt aujourd'hui le correctif « sauter la
  colonne 2 » pour éviter la collision avec l'AOP. Le rendu de référence
  îlots (`summing_aop__ilot0.png`) montre au contraire ces entrées
  **empilées verticalement**, convergeant vers un bus unique dans l'AOP.

## Contexte (pourquoi)

Le détecteur (`circuit_analyzer/detecteur.py`) donne déjà, pour chaque
rôle à un seul bloc, une chaîne `composition` qui encode sa structure
série/parallèle (ex. `'(C1//R6)'`, `'R1+(R2//C1)'`). Le positionneur
actuel (`_positionner_amplificateur_inverseur`,
`_positionner_amplificateur_differentiel`) ignore totalement ce champ : il
place TOUT rôle à 2+ refs en rangée horizontale (Zin/Z1) ou verticale-vers
l'AOP (Zf existant), qu'il s'agisse d'une vraie série (correct, déjà
conforme au rendu de référence `aop_inverseur_zf_composite`) ou d'un vrai
parallèle (incorrect — chevauchement visuel, fil en diagonale).

Un module existant et déjà testé, `gui/impedance_schematic.py`
(`agencer`/`_emettre`, utilisé par la popup « Ω Impédance équiv. »), sait
déjà dessiner un réseau série/parallèle : série = éléments alignés avec un
fil court entre chaque ; parallèle = N branches empilées entre deux rails
partagés. C'est la convention de référence de ce projet — on en reprend
le PRINCIPE (pas le code : ce module dessine en unités schemdraw pour un
canvas séparé, pas en unités BoardSCH `_PAS_X_BLOC`/`_PAS_Y_BLOC`).

## Décisions verrouillées

| Question | Décision |
|---|---|
| Périmètre | Les deux cas ensemble (Intégrateur/parallèle réel ET Sommateur/fan-in), même chantier — visuellement c'est le même geste (empiler), et un seul passage évite deux styles différents à la suite. |
| Où ça s'applique | Générique, sur TOUT rôle de TOUT montage migré ayant 2+ refs — pas un cas spécial par motif. Un rôle à 1 seule ref est inchangé. |
| Comment on décide « empiler » vs « rangée » | Un rôle empile SI : (a) sa valeur dans `impedances` est une LISTE de blocs (fan-in, ex. Sommateur `Zin`), OU (b) c'est un bloc unique dont la `composition` ne contient PAS de `'+'` mais contient `'//'` (parallèle pur, ex. `'(C1//R6)'`). Sinon (série, ou composition mixte/imbriquée du type `'R1+(R2//C1)'`) : comportement RANGÉE actuel, inchangé — aucune régression sur les cas déjà corrects. |
| Géométrie de l'empilement | Toutes les refs d'un rôle empilé partagent la MÊME colonne x (celle où la rangée se plaçait aujourd'hui pour ce rôle), et occupent des lignes y successives espacées de `_PAS_Y_BLOC`, au lieu d'occuper des colonnes x successives sur UNE ligne y. |
| Fils | Aucun changement de logique de fils : le routage en L déjà en place (`_router_fil_en_l`, `_appliquer_deltas`) route automatiquement chaque fil vers sa nouvelle position — pas besoin de « dessiner des rails », juste de repositionner les composants et laisser le routeur déjà construit faire son travail. |
| Correctif « saute-colonne-2 » (Zin/Z1, ajouté plus tôt aujourd'hui) | Supprimé : avec l'empilement, un Zin/Z1 à 3+ refs ne s'étend plus jamais horizontalement vers la colonne de l'AOP — le problème qu'il corrigeait ne peut plus se produire. |
| Espace occupé | Un rôle empilé à N refs occupe N lignes au lieu d'1 seule — tout ce qui se plaçait EN DESSOUS (satellites, rôles suivants) doit décaler sa ligne d'origine du nombre de lignes supplémentaires, pour ne jamais chevaucher. |

## Architecture

### Nouveau champ sur `_Bloc` : refs empilables par rôle

Dans `circuit_analyzer/xml.py`, `_Bloc` gagne un champ additif (pas de
changement de type sur `roles`, donc aucun consommateur existant de
`roles: dict[str, list[str]]` ne casse) :

```python
@dataclass
class _Bloc:
    label: str
    comps: list
    roles: dict = field(default_factory=dict)
    roles_empiles: frozenset = field(default_factory=frozenset)
```

`roles_empiles` : ensemble des NOMS de rôle (ex. `{'Zf'}`) qui doivent
être empilés plutôt qu'alignés en rangée — vide par défaut, donc tout
code qui ne lit pas ce champ garde exactement son comportement actuel.

### Nouvelle fonction pure : `_roles_a_empiler(r) -> frozenset`

Dans `circuit_analyzer/xml.py`, à côté de `_roles_du_bloc` :

```python
@param r Match d'un circuit détecté (sortie de detecteur.py).
@return frozenset des noms de rôle dont la valeur dans r['impedances']
        est une LISTE (fan-in), ou un bloc unique dont la composition
        est un parallèle pur ('//' present, '+' absent).
```

Logique par rôle : inspecter la valeur BRUTE dans `r['impedances'][nom]`
(pas la version déjà aplatie de `_roles_du_bloc`) :
- Valeur = liste → toujours empilé (fan-in), peu importe la longueur.
- Valeur = dict à 1 seule ref → jamais empilé (rien à empiler).
- Valeur = dict à 2+ refs avec `'//' in composition and '+' not in composition` → empilé.
- Sinon (série pure ou composition imbriquée mixte) → pas empilé, comportement rangée actuel.

`_grouper_par_circuit` appelle cette fonction en plus de `_roles_du_bloc`
lors de la construction de chaque `_Bloc`.

### Positionneurs : rangée devient empilement conditionnel

`_positionner_amplificateur_inverseur` et
`_positionner_amplificateur_differentiel` gagnent un 5e paramètre
`roles_empiles` (vide par défaut, rétrocompatible pour tout appelant qui
ne le fournit pas encore pendant la transition). Pour chaque rôle dont la
boucle place actuellement plusieurs refs sur UNE ligne (`Zin` de
l'inverseur, `Z1` du différentiel — PAS `Zf`/`Z3`/`Zg`, qui ne sont
concernés par cette itération que si CE rôle précis est dans
`roles_empiles`, cf. le cas réel `Zf='(C1//R6)'`) :

```python
for j, ref in enumerate(roles.get('Zin', [])):
    if ref not in refs_du_bloc:
        continue
    if 'Zin' in roles_empiles:
        pos[ref] = (x, y_aop - j * _PAS_Y_BLOC, 0)   # empile vers le haut
    else:
        col = j if j < 2 else j + 1
        pos[ref] = (x + col * _PAS_X_BLOC, y_aop, 0)  # rangee, inchangee
```

(Le sens — empiler vers le haut, le bas, ou reprendre exactement l'ancien
calcul de colonne pour compatibilité visuelle avec le rendu déjà validé —
et l'ordre exact des rôles empilés par rapport aux rôles non empilés du
même montage sont des points ouverts pour le plan, cf. plus bas — la
question n'a pas de réponse unique évidente sans dessiner les 5 montages
empilés côte à côte.)

Le décalage de l'espace occupé (satellites, etc.) doit tenir compte du
nombre de lignes RÉELLEMENT utilisées par le montage (`1 + max(0,
nb_refs_du_role_empile - 1)` par rôle empilé, sommé), pas un nombre de
lignes fixe comme aujourd'hui.

### `_deltas_disposition_canonique` (chemin carte scannée)

`circuit_analyzer/eretro_patch.py` doit lire `bloc.roles_empiles` (déjà
porté par `_Bloc`, aucun nouveau calcul ici) et le passer au positionneur
dispatché : `_POSITIONNEURS_PAR_MOTIF[bloc.label](comps_role, bloc.roles,
0, 0, bloc.roles_empiles)`.

### Suppression du correctif saute-colonne-2

Le `col = j if j < 2 else j + 1` (ajouté plus tôt aujourd'hui dans les
boucles `Zin`/`Z1`) reste tel quel dans la branche NON empilée (toujours
utile pour une série à 3+ refs, ex. `R1+R2+R3`, cas rare mais possible) —
il n'est retiré QUE parce qu'il ne peut plus être atteint par la branche
empilée, pas supprimé du code.

## Gestion d'erreurs

- Composition absente ou vide (`bloc.get('composition', '')`) : traité
  comme non-parallèle (`'//' not in ''`) → comportement rangée, jamais
  d'exception.
- Rôle à 1 seule ref dans `roles_empiles` par erreur (ne devrait jamais
  arriver vu la garde `2+ refs` dans `_roles_a_empiler`) : la boucle
  empilée avec `j=0` produit exactement la même position que la boucle
  rangée avec `j=0` — dégénère proprement, pas de branche à protéger
  explicitement.
- Angle : toujours 0, aucun changement — même règle que tous les
  positionneurs canoniques existants.

## Tests

- Unitaires sur `_roles_a_empiler` : rôle-liste (fan-in) → empilé quel
  que soit le nombre d'items ; rôle-dict parallèle pur (`'A//B'`) →
  empilé ; rôle-dict série pure (`'A+B'`) → pas empilé ; rôle-dict mixte
  (`'A+(B//C)'`) → pas empilé (repli sûr) ; rôle à 1 ref → jamais empilé.
- Unitaires sur les positionneurs modifiés : `roles_empiles` vide →
  comportement BYTE-IDENTIQUE à avant ce chantier (non-régression
  explicite, comparée aux tests déjà existants) ; `roles_empiles={'Zin'}`
  ou `{'Z1'}` à 3 refs → 3 positions sur la même colonne x, 3 lignes y
  distinctes ; `roles_empiles={'Zf'}` (le cas réel `C1//R6`) → 2 positions
  sur la même colonne x que l'AOP, 2 lignes y distinctes.
- Bout en bout sur `test_pid_3.xml` (le fichier réel du boss, déjà dans
  le dépôt) : chemin `ecrire_groupes`, vérifier que Zf de l'Intégrateur
  (C1, R6) empile bien et que le fil auparavant en diagonale (`U2-R6` ou
  équivalent) devient soit collinéaire (2 points) soit un L propre (3
  points) — plus de repli diagonal inexpliqué. Même vérification sur le
  Sommateur (3 entrées empilées, plus de saut de colonne).
- Visuel : régénérer `tools/render_boardsch_layout.py` avec un cas
  Intégrateur-parallèle ET un cas Sommateur-3-entrées, produire les PNG,
  les inspecter réellement (`Read` sur le fichier, pas juste vérifier
  qu'il existe) — même exigence que les chantiers précédents.

## Points ouverts pour le plan d'implémentation

- Sens exact de l'empilement (vers le haut/bas de l'AOP) pour chaque
  rôle, et combien de lignes il faut réserver AU-DESSUS vs EN-DESSOUS
  du montage pour que les 5 patterns restent lisibles côte à côte sur un
  vrai board — nécessite de dessiner/comparer les 5 layouts empilés, pas
  une décision qui se prend en l'abstrait.
- Où EXACTEMENT couper le correctif saute-colonne-2 (le garder identique
  dans la branche non-empilée, ou le simplifier maintenant qu'il ne sert
  plus qu'aux séries à 3+ refs, un cas plus rare) — décision de moindre
  risque (garder tel quel) vs. code plus simple, à trancher au moment
  d'écrire le plan.
