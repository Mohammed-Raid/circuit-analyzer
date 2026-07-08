# Portes logiques CMOS — Design

Date : 2026-07-08 · Statut : validé (approche A)

## Contexte et objectif

Après les montages AOP/transistors et la réduction d'impédances, l'app doit
reconnaître les **portes logiques construites en transistors MOS** dans la
netlist (BoardSCH XML), les afficher en symbole de porte, et offrir la même
expérience que les impédances Z : vue simplifiée ↔ vue détaillée.

Décisions de cadrage (validées une à une) :

1. **Source** : topologies transistors (CMOS statique complémentaire) — pas de
   nouveau type de composant XML.
2. **Polarité NMOS/PMOS** : inférence topologique. Le format ne distingue pas
   les MOSFET (`<Name>MOSFET</Name>`, type `M`) ; dans une porte CMOS statique
   le réseau relié au rail d'alimentation est PMOS par construction, celui
   relié à la masse est NMOS. Aucune modification du XML ni de l'éditeur.
3. **Périmètre v1** : NOT, NAND-N, NOR-N (N entrées quelconque). AND/OR
   émergent comme chaînes (NAND→NOT) via le chaînage de montages existant.
4. **Livrable** : symétrie complète avec les Z — symbole de porte en vue
   simplifiée, transistors réels en vue détaillée (toggle existant), bandeau
   de puces cliquables, expression logique en en-tête (comme le gain AOP).

**Hors périmètre v1 (acté)** : XOR/XNOR, portes de transmission (Tgate),
AOI/OAI composites, table de vérité, palette NMOS/PMOS explicite, logique
NMOS-only à résistance de pull-up.

## Approche retenue (A)

Les portes sont des **montages détectés** ordinaires : un module de détection
`circuit_analyzer/logique.py` + trois patterns « Porte NOT/NAND/NOR (CMOS) »
enregistrés EN TÊTE de `_DETECTEURS_COMPLEXES` (detecteur.py) — l'anti-vol du
matcher (`composants_utilises`) garantit qu'une porte réclame ses transistors
avant « MOSFET en commutation ». Tout l'existant est hérité sans code
nouveau : îlots, chaînage (`_ordonner_montages_flux`/`_layers_montages_flux`),
bandeau de puces dynamique, toggle détaillé, moteur anti-collision, sweep
visuel, export PNG.

Approches rejetées : pipeline numérique séparé (duplique l'affichage — la
dette de dispatch dupliqué existe déjà) ; réduction en composants virtuels
« G » façon impedance.py (contamine comp_info/rapport/îlots).

## 1. Détection — `circuit_analyzer/logique.py`

### Algorithme

Pour chaque net candidat `OUT` (ni rail de puissance, ni masse) :

1. **Réseaux** : construire le sous-graphe des transistors `M` chaînés par
   leurs broches D/S (la grille G n'est pas conductrice) :
   - *pull-down* = transistors sur les chemins D/S entre `OUT` et une masse
     (`is_ground_net`) ;
   - *pull-up* = transistors sur les chemins D/S entre `OUT` et un rail
     (`is_power_net`).
   Un transistor ne peut appartenir qu'à un réseau (sinon rejet).
2. **Polarité inférée** : pull-up → PMOS, pull-down → NMOS (stockée dans le
   match, clé `polarites: {ref: "P"|"N"}` — les drawers en ont besoin).
3. **Réduction série/parallèle** de chaque réseau en arbre (même esprit que
   `impedance.arbre_expr`, mais sur les arêtes D/S : nouvelle petite réduction
   locale au module, les nœuds sont des nets, les arêtes des transistors).
   Réseau non réductible (pont, AOI…) → rejet.
4. **Fonction logique** : sur le pull-down, série = ET, parallèle = OU, chaque
   transistor porte le net de sa grille. `OUT = NOT(f_pulldown)`.
5. **Dualité** : l'arbre du pull-up doit être le dual exact (série↔parallèle)
   du pull-down avec le MÊME multiset de grilles. Sinon rejet.
6. **Classification** :
   - 1 transistor de chaque côté → `Porte NOT (CMOS)` ;
   - pull-down = série de N feuilles → `Porte NAND (CMOS)` (N entrées) ;
   - pull-down = parallèle de N feuilles → `Porte NOR (CMOS)` (N entrées) ;
   - tout autre arbre série/parallèle dual (AOI valide) → rejet v1.

### Contrat du match

```python
{
  'circuit_type': 'Porte NAND (CMOS)',      # ou NOT / NOR
  'components':   ['M1', 'M2', 'M3', 'M4'],
  'nodes': {'entrees': ['A', 'B'], 'sortie': 'OUT',
            'vdd': 'VDD', 'gnd': 'GND'},
  'polarites': {'M1': 'P', 'M2': 'P', 'M3': 'N', 'M4': 'N'},
  'expression': 'OUT = NAND(A, B)',          # NOT(A) / NOR(A, B, C)…
}
```

`nodes['entrees']` ordonnées par tri alphabétique des nets (déterminisme).
Le chaînage existant lit `nodes` : `sortie` joue le rôle de OUT, chaque
entrée celui d'IN — une chaîne NAND→NOT est ordonnée comme un
Darlington→CE aujourd'hui.

### Garanties de rejet

Jamais d'exception sur un réseau exotique : tout cas hors périmètre retourne
simplement zéro match et les MOSFET restent traités comme aujourd'hui
(commutation, satellites…). La détection tourne sur le graphe RÉDUIT
(`impedance.reduire`) comme tous les détecteurs — les transistors n'y sont
pas touchés.

## 2. Affichage — `gui/circuit_viewer.py`

### Vue simplifiée (drawer symbole)

- `schemdraw.logic.Not / Nand / Nor` (v0.22 installée, `inputs=N` supporté),
  stubs d'entrées étiquetés par net (A, B…), stub OUT, dans le style existant
  (couleurs thème, canvas clair `#fafafa` inchangé).
- **Registre de positions** : TOUTES les refs M du montage sont enregistrées
  sur le centre du symbole (`_enregistrer_position`) — une puce M1 cliquée
  focalise la porte ; aucune puce grisée en vue simplifiée.
- En-tête fenêtre îlot : l'expression logique s'affiche là où va le gain AOP
  (`_texte_gain` → généralisé : si le montage principal porte `expression`,
  elle est affichée).

### Vue détaillée (drawer transistors)

- PMOS côté VDD (empilés si série, côte à côte si parallèle), NMOS côté GND
  (dual), grilles câblées vers des stubs d'entrée communs, nœud OUT au milieu.
- Symboles : `elm.PFet`/`elm.NFet` schemdraw — rappel piège connu : NFet met
  la grille à DROITE par défaut → `.reverse()` pour les grilles à gauche
  (tests de garde existants sur ce point pour le drawer MOSFET).
- Chaque M enregistre SA position (contrat tests/test_puces_resolution.py).
- Dispatch : même mécanisme `detaille=` que les montages actuels
  (`_make_fig(..., detaille=...)` choisit le drawer symbole ou transistors —
  les drawers de portes sont les premiers montages actifs à avoir une vraie
  variante détaillée ; le point d'entrée reste `_DRAWERS[circuit_type]`).

### Îlots / bandeau

Rien à écrire : `_circuit_principal_ilot` compte les montages (la porte en
est un), le bandeau dynamique liste les M (actifs) et les satellites
éventuels, le toggle et le clic-focus fonctionnent par contrat.

## 3. Corpus et tests (TDD strict)

Nouveaux circuits `circuits_industriels/logic_*.xml` (générés via
`circuit_analyzer/xml_generator.py` comme les corpus précédents) :

| Fichier | Contenu | Attendu |
|---|---|---|
| logic_cmos_not.xml | 1P+1N | Porte NOT |
| logic_cmos_nand2.xml | 2P ∥ + 2N série | Porte NAND (2 entrées) |
| logic_cmos_nand3.xml | 3P ∥ + 3N série | Porte NAND (3 entrées) |
| logic_cmos_nor2.xml | 2P série + 2N ∥ | Porte NOR (2 entrées) |
| logic_chaine_and.xml | NAND2 → NOT | chaîne de 2 portes |
| logic_non_dual.xml | pull-up ≠ dual du pull-down | AUCUNE porte (rejet) |

- Unitaires `tests/test_logique.py` : réseaux, polarités, dualité, N entrées,
  tous les rejets (non-dual, non série/parallèle, transistor partagé,
  pas de rail).
- Drawers : ancres, registre de positions, expression en en-tête.
- **Contrats corpus étendus** : les globs de `tests/test_labels_property.py`
  et `tests/test_puces_resolution.py` (et `tools/render_ilots_v2.py`)
  ajoutent `logic_*.xml` — anti-collision et puces cliquables couverts
  automatiquement.
- Boucle visuelle boss : sweep rendu + inspection PNG des deux vues de
  chaque porte avant livraison.

## 4. Risques identifiés

- **Vol de composants** : un détecteur transistor existant pourrait matcher
  avant les portes s'il restait devant dans la liste → les patterns portes
  sont insérés en TÊTE de `_DETECTEURS_COMPLEXES`, et un test verrouille
  qu'un inverseur CMOS ne produit AUCUN « MOSFET en commutation ».
- **Rails multiples** (VCC et VDD dans le même fichier) : le pull-up accepte
  n'importe quel net `is_power_net` ; le rail retenu est stocké dans
  `nodes['vdd']`.
- **`_ISLAND_DEFILE_WIDTH_IN` / cadrage** : les figures de portes passent
  par `_make_fig` existant (bbox auto) — aucun chemin de montage nouveau.
