# Spec — Schéma d'îlot « à plat » assaini (bus-colonnes)

Date : 2026-06-18
Branche : `rewrite-simple`
Fichier cible : `gui/circuit_viewer.py` (rendu d'îlot), tests `tests/test_island_viewer.py`.

## Contexte

La vue d'îlot doit afficher **un vrai schéma électronique par îlot** (symboles réels +
fils), pas un graphe de bulles. La première tentative (graphe `spring_layout`) puis la
seconde (bus-colonnes brut, codex) restaient illisibles sur les **gros îlots
hétérogènes**. Référence concrète : `circuits_industriels/signal_conditioning.xml`,
« Îlot 1 - comparaison » = 24 composants, 18 nets (3 AOP + 2 diodes + ~19 dipôles R/C).

Les **petits îlots (≤6 composants) se rendent déjà proprement** avec le layout
bus-colonnes ; seul le passage à l'échelle pose problème. Décision (chef/utilisateur) :
**garder un schéma à plat par îlot, mais l'assainir** (pas de découpage par sous-circuit,
pas de layout fonctionnel hybride — hors périmètre).

## Modèle conservé

- **Net = colonne verticale (bus)**, **composant = ligne horizontale**.
- Symboles réels schemdraw, **valeurs réelles** (`10k`, `100pF`) — on n'affiche pas « Z »
  ici : la vue d'îlot montre les composants physiques.

## Changements

### 1. Filtrage des nets (supprimer les colonnes parasites)
- Exclure les nets `NC` / non connectés : **aucune colonne**.
- Un net qui ne touche qu'**une seule** broche dans l'îlot est une **E/S** (stub), pas un
  bus → dessiné comme un **moignon court étiqueté** sur le composant, pas une colonne
  pleine hauteur.
- Seuls les nets à **≥2 connexions** deviennent des colonnes-bus.

### 2. Extent de bus rogné + convention de jonction
- La ligne verticale d'une colonne s'étend **uniquement de la ligne connectée la plus
  haute à la plus basse** (pas pleine hauteur) → supprime la majorité des croisements.
- **Point (dot) à chaque connexion réelle** ; un simple croisement sans point = pas de
  liaison (convention EDA standard). **Légende d'une ligne** rappelant la convention.
- Ordre des colonnes : masse à gauche, nets de signal au centre **triés par ligne
  moyenne de connexion** (heuristique anti-croisement bon marché), rails d'alim à droite.
  Colonnes de masse : symbole ⏚ en bas.

### 3. Lignes de composants — fin des collisions
- Pas vertical de ligne augmenté pour que `ref`+`value` ne se chevauchent jamais
  (valeur au-dessus, ref en dessous, cohérent).
- Composants 2 broches (R/C/L/D/F) : symbole réel entre leurs deux colonnes.

### 4. Composants multi-broches en pièces réelles
- AOP (`U`) : **triangle `elm.Opamp`** dans sa propre bande plus haute, broches
  raccordées + étiquetées vers leurs colonnes (au lieu du `Ic` générique qui se chevauche).
- Connecteurs / autres ICs : boîte étiquetée propre, chacune dans sa bande, sans
  chevauchement du voisin.

### 5. Refactor pour testabilité
- `_build_island_schematic_plan(model)` devient la **fonction pure unique** qui fait tout
  le filtrage / ordonnancement / assignation de lignes / classification stub-vs-colonne et
  renvoie un dict `plan`. Le drawer ne fait que consommer le plan.
- Structure de `plan` (étendue) :
  ```
  {
    "label": str,
    "columns": [ {"net": str, "x": float, "kind": "ground|power|signal",
                  "y_top": float, "y_bottom": float} ],   # nets ≥2 connexions
    "rows": [ {"ref","type","value","symbol","y",
               "pins":[(pin,net)],            # toutes broches
               "stubs":[(pin,net)] } ],       # broches vers nets E/S (1 connexion)
    "caption": str,
  }
  ```

## Tests (TDD, sur le plan pur surtout)
1. **NC exclu** : un composant avec une broche sur `NC` → `NC` absent de `columns`.
2. **Stub vs colonne** : net à 1 connexion → présent dans un `rows[*].stubs`, absent de
   `columns` ; net à ≥2 connexions → présent dans `columns`.
3. **Extent rogné** : `y_top`/`y_bottom` d'une colonne = lignes des composants connectés
   (pas les extrêmes de la figure).
4. **Ordre colonnes** : masse à gauche (x min), alim à droite (x max).
5. **AOP** : composant `U` → `row["symbol"] == "opamp"` ; pas de chevauchement (bande
   dédiée — vérifié via espacement `y` strictement croissant et |Δy| ≥ seuil).
6. **Non-régression** : les tests existants de `test_island_viewer.py` restent verts
   (adaptés à la nouvelle structure de `plan` si nécessaire).
7. **Fumée** : `_make_island_fig` rend le gros îlot de `signal_conditioning.xml` sans
   exception et produit une figure non vide.

## Hors périmètre
- Découpage par sous-circuit détecté ; layout fonctionnel hybride.
- Arcs de « saut » (hops) sur croisements — option future si l'ambiguïté gêne.
- Routage orthogonal optimal / minimisation exacte des croisements (NP-difficile).

## Vérification finale
- Rendu headless (`debug_render_ilots.py`) du gros îlot + comparaison visuelle.
- `python -m pytest tests/test_island_viewer.py -q` vert.
- Suite complète verte.

(Commits sans co-auteur Claude — directive utilisateur.)
