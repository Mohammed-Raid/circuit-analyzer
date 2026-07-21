# Mapping du dialecte ERetroDesign réel — Design

**Date :** 2026-07-21
**Statut :** approuvé (design), en attente de relecture spec avant plan.

## Context (pourquoi)

Le chantier d'import ERetroDesign + la reconnaissance par forme ont été calibrés
sur les fichiers-échantillons `Lib/*.xml`. Le **test grandeur nature** sur 4
vraies cartes du dossier `CARTE POUR TESTER (VRAI TEST)/` (`PG 2.xml`,
`PG 3.xml`, `PowtranAlim20260809.xml`, `pg carte.xml`) a montré que l'éditeur
réel utilise une **bibliothèque de symboles et un vocabulaire de noms
différents** : ~30 % seulement des composants sont reconnus, **144 tombent en
boîte noire X**, et la reconnaissance par forme n'en récupère **aucun**.

Cause : les résistances réelles sont dessinées en **rectangle IEC** (polygone),
géométriquement indiscernables d'un fusible/thermistance/varistance — la forme
ne peut donc pas les classer sans contresens. Le levier fiable sur ces cartes
est le **NOM**, qui est parlant (`R 810`, `Transistor_NPN`, `78L05CP`…) et
encode même la valeur des résistances.

**But :** faire passer la reconnaissance de ~30 % à ~80 % sur les 4 cartes
réelles, par extension du mapping par nom (100 % côté Python, l'éditeur C# est
intouchable).

## Principe permanent : toujours produire le schéma

Directive boss (2026-07-21) : **on fait toujours des schémas comme ça.** Le
rendu schématique honnête n'est pas un simple test de fin de tâche — c'est un
livrable de premier plan. Tout composant/carte importé doit produire un schéma
rendu ET inspecté visuellement (PNG regardés), jamais « des tests verts sans
regarder les rendus ». Aucune famille reconnue ne doit retomber en vue
générique fausse (règle « jamais de vue générique fausse »).

## Non-goals (v1)

- Ne PAS lire la géométrie polygone ni ajouter de règle de forme pour le
  rectangle (indiscernable des fusibles/thermistances — le nom suffit et est
  plus sûr).
- Ne PAS toucher l'éditeur C# ni le format de fichier.
- `Led` et `Varistance` sont **déjà reconnus** (absents des 144 inconnus) —
  hors périmètre.
- Pas de fichier de config externe éditable (YAGNI ; on pourra l'ajouter plus
  tard si besoin d'éditer sans code).

## Architecture

Tout dans `circuit_analyzer/eretro.py`, en étendant `mapper_nom` /
`_MAPPING_ERETRO`. L'ordre de consultation de `lire_xml` (Étape 5) est
**inchangé** : `nom exact → mapper_nom (étendu) → classer_par_forme → boîte
noire X`. Les nouvelles règles ne se déclenchent que si les lookups exacts
échouent → **non-régressif par construction** (dialecte natif et échantillon
Lib passent avant, inchangés).

## Familles reconnues (les 144 inconnus réels)

| Motif / nom | → Type | Occurrences | Rendu |
|---|---|---|---|
| `R <code>` / `R<code>` / `RINF` (chiffre requis après `R`) | **R** + valeur décodée | ~99 | symbole résistance (impédance Z) |
| `Transistor_NPN` | **Q** | 11 | drawer transistor existant |
| `open connecter`, `JUMPER`, `jumper 2 broches`, `connecteur traversant`, `Borne` | **J** (connecteur) | 22 | boîte étiquetée `Connecteur (…)` |
| `SI844AB`, `A788J`, `78L05CP`, `UC2844`, `WRB2424S-3WR2` | **U** | 9 | boîte IC `CI (…)` ; `78L05`→régulateur 5 V catalogué |
| `Condensateur_polarise` | **C** | 3 | symbole condensateur |
| `Photodiode` | **D** | 1 | symbole diode |

**Garde-fou anti-régression** : la règle `R` exige un **chiffre** juste après le
`R` (`R 810`, `R810`), plus le cas exact `RINF`. `RELAIS`, `RINF` mis à part,
tout nom `R`+lettre ne matche pas.

## Décodage de la valeur R-code

Helper pur `decoder_valeur_resistance(code) -> str` (chaîne affichable, ou `''`
si indécodable). Notation résistance standard :

- **`R`-décimal** : `R` interne = virgule. `3R90`→3,9 Ω, `60R4`→60,4 Ω,
  `47R0`→47 Ω.
- **EIA (dernier chiffre = multiplicateur, puissance de 10)** :
  `810`→81 Ω, `561`→560 Ω, `332`→3,3 kΩ, `1001`→1 kΩ, `2001`→2 kΩ,
  `3903`→390 kΩ, `5101`→5,1 kΩ, `512`→5,1 kΩ, `300`→30 Ω, `2400`→240 Ω,
  `3300`→330 Ω. (valeur = `int(chiffres[:-1]) × 10^int(chiffres[-1])`.)
- **`RINF`** → `"open/DNP"` (résistance infinie / non peuplée).
- **Repli gracieux** : si le code ne parse pas proprement OU donne une valeur
  aberrante (ex. `R 308`→30×10⁸ = 3 GΩ, `R 30A`), on garde le **type R** et on
  **affiche le code brut** (`"308"`, `"30A"`) — jamais une valeur inventée.
- Affichage via le `formater_valeur` existant (Ω/kΩ/MΩ) pour la cohérence.

Seuil « aberrant » : valeur > 100 MΩ → repli code brut (aucune résistance
réelle de carte n'atteint cet ordre).

## Rendu : connecteurs et ICs nommées → boîte étiquetée

Réutilisation du drawer boîte IC `gui/puce_schematic.py::dessiner_puce` (déjà
construit au chantier forme) pour DEUX familles :

- **IC nommée hors catalogue** (`SI844AB`, `UC2844`…) → boîte `CI (SI844AB)` ;
  régulateur `78L05CP` → entrée catalogue (5 V, comme `7805`).
- **Connecteur (J)** → même boîte, étiquette `Connecteur (Borne)`.

Mécanisme : `gui/circuit_viewer.py::_puce_ilot` est étendu pour dégrader en
boîte neutre étiquetée **tout composant U ou J réel non-AOP** dont le nom
provient du mapping dialecte réel, via un **marqueur porté par le composant**
(dans le même esprit que `par_forme` du chantier précédent — un drapeau/champ
distinctif sur `Composant`). Un vrai AOP (résolu en catégorie AOP) reste exclu ;
le dialecte natif reste inchangé. Aucun faux triangle d'AOP, aucune vue
générique. Le nom réel de la pièce sert d'étiquette (jamais une fonction
inventée).

Type `J` : nouveau type de composant. **Scindé par nombre de broches** (car
`construire_graphe` fait des 2-broches des arêtes et des ≥3-broches des nœuds) :
- **≥3 broches** (`open connecter`, `connecteur traversant`) → nœud → boîte
  étiquetée `Connecteur (…)` via `dessiner_puce`, routée dans le dispatch
  (show_island + render_ilots_v2) AVANT la vue générique.
- **2 broches** (`jumper 2 broches`, `JUMPER`, `Borne`) → arête → il faut une
  entrée type `J` dans `_SYMBOL_ELM` (symbole de lien/cavalier honnête, ex.
  interrupteur fermé/`elm.Jumper`), SINON le défaut `elm.Resistor` afficherait
  un faux symbole de résistance.

## Risques de rendu à traiter au plan (repérés en self-review)

1. **Connecteur 2 broches vs ≥3 broches** (ci-dessus) : le drawer boîte ne
   couvre que le cas nœud ; le cas arête exige une entrée `_SYMBOL_ELM['J']`.
   La boucle visuelle DOIT montrer les deux cas.
2. **Rôles de broches transistor** : `Transistor_NPN` → Q avec broches
   NUMÉROTÉES (1/2/3), alors que le drawer transistor attend base/collecteur/
   émetteur. Le plan doit soit aliaser les broches par position (convention
   ERetroDesign à vérifier sur les fichiers), soit dégrader proprement si les
   rôles sont inconnus — jamais un transistor mal câblé silencieux. La boucle
   visuelle sur `PowtranAlim` (11 `Transistor_NPN`) est le juge.

## Tests

- **Unités** :
  - `decoder_valeur_resistance` sur tous les cas ci-dessus + repli (`308`,
    `30A`, `RINF`, code vide).
  - Chaque famille de nom → bon type (`R 810`→R+81 Ω, `Transistor_NPN`→Q,
    `Borne`→J, `SI844AB`→U, `Condensateur_polarise`→C, `Photodiode`→D).
  - Non-régression : `RELAIS 2RT` de l'échantillon Lib NE devient PAS R ;
    dialecte natif inchangé.
- **Oracle corpus réel** (`tests/`, `skipif` si dossier absent, LECTURE SEULE
  sur `CARTE POUR TESTER (VRAI TEST)/`) : sur les 4 cartes, assertions
  « inconnus X ≤ ~30 » (contre 144), « ≥ ~99 résistances reconnues », zéro type
  invalide, pas de régression.
- **Boucle visuelle (livrable, pas option)** : rendre des îlots représentatifs
  des 4 cartes → résistances en symbole R avec valeur affichée, connecteurs/ICs
  en boîte étiquetée, canvas clair, aucune boîte noire pour ces familles, aucun
  faux AOP. PNG réellement inspectés et décrits ; supprimés après (jamais
  committés).

## Découpage pressenti (pour le plan)

1. `decoder_valeur_resistance` (helper pur + tests).
2. Règles de nom dans `mapper_nom` (R-code, familles exactes, garde-fou) + type
   `J` + marqueur boîte-IC sur `Composant` + propagation `xml.py`.
3. Rendu : `_puce_ilot` dégrade U/J marqués en boîte étiquetée (connecteur/IC) ;
   catalogue `78L05`.
4. Oracle corpus réel + boucle visuelle + clôture.

## Contraintes permanentes

Commits FR sans footer Claude ; jamais `git add -A` ; `docs.rar`,
`SolutionERetroDesignX20260813/` et `CARTE POUR TESTER (VRAI TEST)/` en LECTURE
SEULE (jamais committés/modifiés) ; `PYTHONUTF8=1` ; schemdraw ==0.22 ; canvas
des schémas CLAIR ; rendu schématique inspecté à chaque changement de dessin.
