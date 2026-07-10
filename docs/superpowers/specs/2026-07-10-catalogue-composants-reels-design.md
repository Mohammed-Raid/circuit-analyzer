# Catalogue de composants réels — identification + rendu (v1)

Validé par le boss le 2026-07-10 (approche A : bibliothèque déclarative +
boîte à puce générique).

## Contexte et but

Les prochains circuits utiliseront des composants réels : 74HC00/04/08/32,
74HC74/157/138, NE555, LM393/LM339, x741/x458, 7805/7812/LM317, PC817,
2N2222/BC547/2N3904, IRFZ44N/BS170/IRLZ44N, 1N4148/1N4007, LED (rouge, verte,
bleue), buffers famille 74HC/74HCT (variantes de gain x1/x2).

Aujourd'hui **tout `U` est traité comme un AOP** (broches IN+/IN−/OUT/V+/V−).
Un NE555 ou un 74HC00 (8/14 broches numérotées) casserait ce postulat : fausse
détection possible, et surtout **îlot rendu en grille générique** — interdit
(« jamais de vue générique »).

**But v1 : identifier chaque référence et la dessiner juste.** Pas de
détection de montages autour de ces puces en v1.

## Format d'entrée (décisions boss)

- Les composants arrivent avec leur **type existant** (`U`, `Q`, `M`, `D`) et
  la **référence constructeur dans `value`** (ex. `type=U value="NE555"`).
- Les broches des puces (`U`) sont **numérotées comme le boîtier DIP réel**
  (1..8, 1..14, 1..16). La correspondance numéro → fonction vient de la
  bibliothèque interne de l'app.
- `Q`/`M`/`D` gardent leurs broches nommées actuelles (B/C/E, G/D/S, A/K).
- Notations de la liste : `74HCXX`/`74HCTXX` = toute la famille ;
  `x741`/`x458` = tout préfixe constructeur (LM741, UA741, MC1458…) ;
  « pas x1/x2 » = variantes de gain du buffer (info d'usage, rien à encoder).

## Architecture

### 1. `circuit_analyzer/catalogue.py` (nouveau module, données + 1 fonction)

Table déclarative `CATALOGUE` : liste d'entrées
`{motif, categorie, nom, broches, symbole}` avec trois genres de motifs :

- `("exact", "PC817")` — égalité stricte après normalisation ;
- `("famille", "74HC00")` — tolère l'insert T et les suffixes de boîtier
  (74HCT00, 74HC00N) ;
- `("suffixe", "741")` — tout préfixe constructeur (LM741, UA741…).

Normalisation : majuscules, espaces/tirets retirés. Priorité de match :
exact > famille > suffixe > repli famille 74HC.

**Fonction unique** : `identifier(type_, value) -> entree | None`.
`None` = composant inconnu → comportement actuel inchangé (compat totale).

Repli famille : un `U` dont value matche `74HC(T)?\d+` sans entrée précise →
catégorie « Logique 74HC », boîte à broches numérotées brutes.

### 2. Aliasing de broches à la lecture

Pour un composant identifié dont l'entrée porte `alias_broches`, les numéros
de boîtier sont renommés en fonctions **juste après `lire_xml`** (passe
unique, avant construire_graphe). Le x741 (2→IN−, 3→IN+, 6→OUT, 7→V+, 4→V−)
redevient un AOP standard : **toute la détection AOP existante fonctionne
telle quelle, zéro modification des matchers**. Pareil pour les régulateurs
(7805 : 1→IN, 2→GND, 3→OUT).

Seules les puces **mono-unité** sont aliasées vers un rôle existant (x741).
Les multi-unités (x458 dual, LM393 dual, LM339 quad, 74HC00 quad…) restent
en broches fonctionnelles de boîtier (OUT1, IN1−…) et passent par la boîte
puce — leur éclatement en unités logiques est hors périmètre v1.

### 3. Garde anti-fausse-détection

Un `U` identifié **non-AOP** est exclu des détecteurs AOP/comparateur
(un seul point de garde, au niveau du recensement des U candidats).
Un `U` **non identifié** garde le comportement actuel.

### 4. Rendu îlot « 1 puce + Z autour » (anti-vue-générique)

Nouveau recognizer `_puce_ilot` branché **avant** la grille générique dans
`show_island` ET dans `tools/render_ilots_v2.py` (les deux dispatchs) :
îlot dont l'actif principal est une puce identifiée →

- boîte `schemdraw elm.Ic` : broches étiquetées par leur **fonction**
  (TRIG, THR, OUT…), nets affichés au bout des broches ;
- passifs autour en **blocs Z cliquables** (réutilise la mécanique
  satellites/impédances existante), deux vues (Z / détaillée R/L/C) ;
- puces du bandeau cliquables (contrat `test_puces_resolution`, zéro
  nouvelle exclusion) ;
- piège schemdraw connu : orientation explicite (`.right()`/`.theta(0)`)
  sur tout élément posé (héritage de la direction du stylo).

LED : une `D` identifiée LED est dessinée `elm.LED` avec sa couleur (rouge/
verte/bleue) partout où une diode serait dessinée.

### 5. Rapport + onglet Analyser

- Rapport : « U3 — Timer (NE555) » au lieu de « Circuit intégré ».
- `_CATEGORIES`/`functional_category` : entrée propre par catégorie
  (jamais « divers »).
- Onglet : couleur/catégorie affichées (vérifier le fallback couleurs).

## Catalogue v1 (contenu exact)

| Motif | Catégorie | Broches (n° → fonction) | Symbole |
|---|---|---|---|
| suffixe 741 | AOP (mono) | 1 OFFSET1, 2 IN−, 3 IN+, 4 V−, 5 OFFSET2, 6 OUT, 7 V+, 8 NC | alias → AOP existant |
| suffixe 458 | AOP double | 1 OUT1, 2 IN1−, 3 IN1+, 4 V−, 5 IN2+, 6 IN2−, 7 OUT2, 8 V+ | boîte puce |
| exact NE555 | Timer | 1 GND, 2 TRIG, 3 OUT, 4 RESET, 5 CTRL, 6 THR, 7 DIS, 8 VCC | boîte puce |
| exact LM393 | Comparateur double | 1 OUT1, 2 IN1−, 3 IN1+, 4 GND, 5 IN2+, 6 IN2−, 7 OUT2, 8 VCC | boîte puce |
| exact LM339 | Comparateur quadruple | 1 OUT2, 2 OUT1, 3 VCC, 4 IN1−, 5 IN1+, 6 IN2−, 7 IN2+, 8 IN3−, 9 IN3+, 10 IN4−, 11 IN4+, 12 GND, 13 OUT4, 14 OUT3 | boîte puce |
| suffixe 7805 | Régulateur +5 V | 1 IN, 2 GND, 3 OUT | alias + boîte 3 broches |
| suffixe 7812 | Régulateur +12 V | 1 IN, 2 GND, 3 OUT | alias + boîte 3 broches |
| exact LM317 | Régulateur ajustable | 1 ADJ, 2 OUT, 3 IN | boîte 3 broches |
| famille 74HC00 | Porte NAND ×4 | 1 1A, 2 1B, 3 1Y, 4 2A, 5 2B, 6 2Y, 7 GND, 8 3Y, 9 3A, 10 3B, 11 4Y, 12 4A, 13 4B, 14 VCC | boîte puce |
| famille 74HC08 | Porte AND ×4 | même brochage que 74HC00 | boîte puce |
| famille 74HC32 | Porte OR ×4 | même brochage que 74HC00 | boîte puce |
| famille 74HC04 | Inverseur ×6 | 1 1A, 2 1Y, 3 2A, 4 2Y, 5 3A, 6 3Y, 7 GND, 8 4Y, 9 4A, 10 5Y, 11 5A, 12 6Y, 13 6A, 14 VCC | boîte puce |
| famille 74HC74 | Bascule D ×2 | 1 1CLR, 2 1D, 3 1CLK, 4 1PRE, 5 1Q, 6 1Q̄, 7 GND, 8 2Q̄, 9 2Q, 10 2PRE, 11 2CLK, 12 2D, 13 2CLR, 14 VCC | boîte puce |
| famille 74HC157 | Multiplexeur 2:1 ×4 | 1 SEL, 2 1A, 3 1B, 4 1Y, 5 2A, 6 2B, 7 2Y, 8 GND, 9 3Y, 10 3B, 11 3A, 12 4Y, 13 4B, 14 4A, 15 EN̄, 16 VCC | boîte puce |
| famille 74HC138 | Démultiplexeur 3:8 | 1 A0, 2 A1, 3 A2, 4 E1̄, 5 E2̄, 6 E3, 7 Y7, 8 GND, 9 Y6, 10 Y5, 11 Y4, 12 Y3, 13 Y2, 14 Y1, 15 Y0, 16 VCC | boîte puce |
| exact PC817 | Optocoupleur | 1 ANODE, 2 CATHODE, 3 ÉMETTEUR, 4 COLLECTEUR | boîte puce (symbole composé = v2) |
| repli 74HC(T)?\d+ | Logique 74HC (buffers…) | numéros bruts | boîte puce |
| exact 2N2222, BC547, 2N3904 | Transistor NPN | B/C/E existants | natif Q (catégorie seule) |
| exact IRFZ44N, IRLZ44N, BS170 | MOSFET canal N | G/D/S existants | natif M (catégorie seule) |
| exact 1N4148 | Diode signal | A/K existants | natif D |
| exact 1N4007 | Diode redressement | A/K existants | natif D |
| D + value contenant LED/rouge/verte/bleue | LED | A/K | `elm.LED` coloré |

## Corpus + contrats + boucle visuelle

- `tools/gen_reel_corpus.py` → `circuits_industriels/reel_*.xml`, un par
  famille : 555+RC, 7805+condensateurs, PC817+R, 74HC00 seul, LED+R,
  LM393+pont diviseur, LM317+R/R, 741 en inverseur (preuve aliasing → la
  détection AOP existante le matche).
- Globs contrats étendus : `test_labels_property`, `test_puces_resolution`
  (zéro nouvelle exclusion), `render_ilots_v2`.
- Tests unitaires `identifier()` : exact/famille/suffixe/repli/inconnu/
  normalisation ; alias 741 → match AOP inverseur de bout en bout.
- **PNG des deux vues inspectés** (critère d'acceptation du boss).

## Hors périmètre v1 (explicite)

- Détection de montages (555 astable/monostable, hystérésis LM393,
  filtre d'alim 7805…).
- Éclatement des puces multi-unités en unités logiques (74HC00 → 4 NAND
  dans la détection de portes, x458 → 2 AOP).
- Palette de l'éditeur de schéma (tab_draw).
- Symbole composé de l'optocoupleur (boîte v1 ; défaut visuel v2 si besoin).

## Critères d'acceptation

1. Chaque référence de la liste identifiée (tests `identifier()`).
2. Un îlot à puce identifiée ne tombe **jamais** en grille générique.
3. Un 741 en montage inverseur est détecté par le matcher AOP existant
   (preuve de l'aliasing), rapport « Amplificateur inverseur (AOP) ».
4. Aucune régression : suite complète verte (1318+), zéro nouvelle
   exclusion de puce bandeau.
5. PNG deux vues de tout le corpus reel_* rendus et inspectés.
6. Exe reconstruit + smoke test.
