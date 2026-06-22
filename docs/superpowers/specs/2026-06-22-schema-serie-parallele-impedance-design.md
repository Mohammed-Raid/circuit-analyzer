# Schéma série/parallèle dans la fenêtre Impédance équivalente

Date : 2026-06-22
Branche : `rewrite-simple`

## Contexte et problème

Après la démo, le boss n'a **pas compris** le schéma d'îlot actuel pour les réseaux
série/parallèle. Deux causes identifiées :

1. **Forme non reconnaissable** : le viewer dessine un schéma « colonnes-bus »
   (`gui/circuit_viewer.py`, `_build_island_schematic_plan`) où chaque net est une
   colonne verticale et chaque composant un trait horizontal. Ce n'est pas la forme
   qu'attend un électronicien (série = en ligne, parallèle = branches empilées).
2. **Surcharge** : trop de traits, de croisements et de labels de net internes
   (`NET1`, `NET2`…).

L'application est désormais focalisée **impédances** (cf. directive boss). Le moteur
calcule déjà la réduction sous forme d'expression série/parallèle, p.ex.
`(R1+R2)//R3` via `impedance.impedance_equivalente(graphe, a, b)`. Cette expression
**est** l'arbre série/parallèle : il suffit de la dessiner dans la forme « manuel ».

Forme cible (exemple fourni par l'utilisateur) :

```
      ___           ___
  +--|_R1_|-------|_R2_|--+        R1, R2 en SÉRIE
  |                       |
  |         ___           |        R3 en PARALLÈLE de (R1+R2)
  +--------|_R3_|---------+        => (R1+R2)//R3
```

## Périmètre

- **Dans le périmètre** : afficher, dans la fenêtre « Impédance équivalente », un
  schéma série/parallèle du réseau réduit, à côté de l'expression et du |Z|/phase
  déjà présents.
- **Hors périmètre** : la vue îlot (`circuit_viewer.py`) n'est pas modifiée ; le
  dessin de la topologie d'un pont (Y-Δ) ; les composants multi-broches (AOP…).

## Flux de données

```
impedance_equivalente(graphe, a, b)  ->  expr (str, ex. "(R1+R2)//R3")
        |
        v
arbre_expr(expr)  ->  arbre Serie/Parallele/Feuille   (None si pont : * ou /)
        |
        v
agencer(arbre)    ->  boîtes positionnées (coords)     [gui/impedance_schematic.py]
        |
        v
dessiner(...)     ->  figure matplotlib (schemdraw)    embarquée dans la fenêtre
```

## Composants

### 1. `circuit_analyzer/impedance.py` — `arbre_expr(expr)` (pur, testable)

Parse l'expression de composition en arbre, via l'AST (même technique que
`evaluer_impedance`).

- `BinOp(Add)`        → nœud **Série**     : `("serie", [enfants...])`
- `BinOp(FloorDiv)`   → nœud **Parallèle** : `("parallele", [enfants...])`
- `Name(id)`          → **Feuille**        : `("feuille", "R1")`
- `BinOp(Mult|Div)`   → **non série/parallèle** : retourne `None` (cas pont/Y-Δ)

Aplatissement : `a+b+c` et `(a//b)//c` donnent un seul nœud à N enfants
(série/parallèle associatifs) pour un dessin plus plat.

Représentation : tuples `(kind, payload)` — léger, pas de classe nécessaire.

Signature : `arbre_expr(expr: str) -> tuple | None`.

### 2. `gui/impedance_schematic.py` — mise en page + rendu (nouveau fichier isolé)

#### `agencer(arbre) -> Boite`
Calcule récursivement une boîte par nœud. Une `Boite` expose :
`largeur`, `hauteur`, `y_borne` (ordonnée des bornes gauche/droite, relative au
bas de la boîte) et de quoi émettre ses symboles/fils une fois placée à `(x, y)`.

- **Feuille** : largeur = `W_SYMB` (+ marges fil), hauteur = `H_SYMB`,
  `y_borne` = milieu.
- **Série** : enfants juxtaposés horizontalement, reliés bout à bout par un fil ;
  alignés sur une même ligne de bornes. `largeur` = Σ enfants + fils ;
  `hauteur` = max ; `y_borne` = ligne commune.
- **Parallèle** : enfants empilés verticalement (écart `GAP_V`). Chaque enfant
  plus court est complété par des fils de liaison à gauche/droite pour atteindre
  un rail vertical gauche et un rail droit communs. `largeur` = max enfant + rails ;
  `hauteur` = Σ enfants + écarts ; `y_borne` = milieu des rails.

#### `dessiner(arbre, a, b) -> Figure`
- Place chaque feuille comme élément schemdraw (`R/L/C` via la table de symboles,
  sinon boîte Z générique) entre les deux points calculés.
- Fils et rails : `elm.Line().at(...).to(...)`.
- Étiquettes : **uniquement** `A` (entrée) et `B` (sortie). Sous chaque symbole :
  ref + valeur (`R1` / `10k`).
- `ax.set_aspect("equal")` (cohérent avec la vue îlot, évite l'étirement).

### 3. `gui/impedance_view.py` — intégration

Après le calcul de `expr` :
- `arbre = impedance.arbre_expr(expr)`
- si `arbre` : afficher la figure `dessiner(arbre, a, b)` dans un canvas embarqué.
- sinon (pont) : message « Réseau en pont (Y-Δ) — pas de forme série/parallèle
  simple à dessiner », et on garde l'expression + |Z|/phase.

La fenêtre est agrandie pour loger le canvas.

## Gestion des erreurs / cas limites

- **Pont / Y-Δ** (`*`,`/` dans l'expression) : `arbre_expr` renvoie `None` ; la
  fenêtre affiche un message clair, sans planter.
- **Réseau non réductible** (`expr is None`, déjà géré) : message existant inchangé.
- **Feuille seule** (`expr == "R1"`) : un seul symbole entre A et B.
- **Valeur manquante** sur une feuille : le dessin reste valide (label = ref seul).

## Tests

**`arbre_expr` (TDD, dans `tests/test_impedance.py`)**
- `"R1+R2"` → `("serie", [feuille R1, feuille R2])`
- `"(R1+R2)//R3"` → `("parallele", [serie[R1,R2], feuille R3])`
- `"R1+R2+R3"` → série aplatie à 3 enfants
- `"R1"` → `("feuille", "R1")`
- expression avec `*` ou `/` → `None`

**`agencer` (dans `tests/test_impedance_schematic.py`)**
- série : les enfants ont des x croissants, même ligne de bornes (y égaux)
- parallèle : les enfants ont des y distincts (empilés), bornes alignées sur les rails
- les dimensions de la boîte parent englobent les enfants

**`dessiner`** : smoke test — produit une figure sans exception sur
`(R1+R2)//R3` et sur une feuille seule.

## Hors périmètre (futur éventuel)

- Dessiner la topologie d'un pont de Wheatstone (forme losange).
- Appliquer le même rendu en arbre à la vue îlot.
- Réseaux multi-broches (AOP, transistors).
