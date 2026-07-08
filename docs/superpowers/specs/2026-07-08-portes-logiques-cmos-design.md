# Portes logiques CMOS — Design

Date : 2026-07-08 · Statut : validé (approche A, révisé après deux revues
d'architecture — décisions 🔴 verrouillées par l'utilisateur)

## Contexte et objectif

Après les montages AOP/transistors et la réduction d'impédances, l'app doit
reconnaître les **portes logiques construites en transistors MOS** dans la
netlist (BoardSCH XML), les afficher en symbole de porte, et offrir la même
expérience que les impédances Z : vue simplifiée ↔ vue détaillée.

Décisions de cadrage (validées une à une) :

1. **Source** : topologies transistors (CMOS statique complémentaire) — pas de
   nouveau type de composant XML. Seuls les composants `type == 'M'`
   participent aux réseaux (les totem-poles BJT sont exclus).
2. **Polarité NMOS/PMOS** : inférence topologique (pull-up = PMOS,
   pull-down = NMOS), complétée par le critère d'orientation D/S (cf. § 1.3).
   La **palette NMOS/PMOS explicite est actée comme jalon v2** — c'est la
   seule résolution définitive de l'ambiguïté du format, et le prérequis des
   portes de transmission.
3. **Périmètre v1** : NOT, NAND-N, NOR-N (N entrées quelconque). AND/OR
   émergent comme chaînes (NAND→NOT) via le chaînage de montages existant.
4. **Livrable** : symétrie complète avec les Z — symbole de porte en vue
   simplifiée, transistors réels en vue détaillée (toggle existant), bandeau
   de puces cliquables, expression logique en en-tête (comme le gain AOP).

**Hors périmètre v1 (acté)** : XOR/XNOR, portes de transmission (Tgate),
AOI/OAI composites, table de vérité, palette NMOS/PMOS explicite, logique
NMOS-only à résistance de pull-up, déduplication des grilles parallèles
(drive strength), expression composée multi-portes en en-tête,
découplage clé/libellé des `circuit_type` (refactor dédié, au ledger).

## Approche retenue (A)

Les portes sont des **montages détectés** ordinaires : un module de détection
`circuit_analyzer/logique.py` + UN détecteur `detecter_portes_cmos`
(émettant les trois types en une passe) enregistré EN TÊTE de
`_DETECTEURS_COMPLEXES` (detecteur.py) — l'anti-vol du matcher
(`composants_utilises`) garantit qu'une porte réclame ses transistors avant
« MOSFET en commutation ». Tout l'existant est hérité : îlots, chaînage
(`_ordonner_montages_flux`/`_layers_montages_flux` via le nouveau champ
`io`, cf. § 1.5), bandeau de puces dynamique, toggle détaillé, moteur
anti-collision, sweep visuel, export PNG.

Approches rejetées : pipeline numérique séparé (duplique l'affichage) ;
réduction en composants virtuels « G » façon impedance.py (contamine
comp_info/rapport/îlots).

## 1. Détection — `circuit_analyzer/logique.py`

### 1.1 Graphe de conduction (une seule construction)

Construit UNE FOIS par appel : nœuds = nets touchés par une broche D/S d'un
`M`, arêtes = transistors. **Garde-fou perf** : si le circuit ne contient
aucun `M`, le détecteur retourne immédiatement (le corpus analogique de
5 000 composants ne doit rien payer). Les candidats OUT sont UNIQUEMENT les
nets de ce graphe (ni rail, ni masse) — jamais les nets du circuit entier.

### 1.2 Réseaux et réduction

Pour chaque candidat OUT :

- *pull-down* = transistors sur les chemins D/S entre OUT et une masse
  (`is_ground_net`) ; *pull-up* = entre OUT et un rail (`is_power_net`).
  D/S sont traités comme conducteurs symétriques pour la connectivité.
- Un transistor ne peut appartenir qu'à un réseau (sinon rejet du candidat).
- Chaque réseau est réduit en **arbre série/parallèle GÉNÉRAL** (structure
  de tuples mimant les conventions d'impedance.py, mais algèbre propre au
  module — les arêtes portent les nets de grille). Réseau non réductible
  (pont, structure non série/parallèle) → rejet.
- **L'algèbre d'arbres est un ensemble de fonctions pures isolées** (aucune
  référence aux transistors) : c'est l'unité que AOI/OAI v2 étendra.

### 1.3 Polarité et désambiguïsation D/S (cas 1+1)

Pull-up → PMOS, pull-down → NMOS (`polarites: {ref: "P"|"N"}` dans le
match). **Cas ambigu structurel** : la paire complémentaire à grilles
communes a la même netlist qu'un push-pull suiveur MOS. Critère de
désambiguïsation (information réelle du format, broches D/S nommées) :

- les DEUX transistors ont leur **source au rail** (S du haut sur le rail,
  S du bas sur la masse) → porte NOT ;
- les deux sources sur OUT → suiveur : **rejet** ;
- panaché → câblage incohérent : **rejet**.

Ce critère ne s'applique QU'AU cas 1 transistor + 1 transistor (les
empilements NAND/NOR n'ont pas de sosie analogique ; leur connectivité
suffit). Conséquence assumée et testée : un inverseur câblé D/S à l'envers
est un faux négatif diagnosticable (« câbler la source au rail »), jamais
un faux positif silencieux.

### 1.4 Classification (formes pures) et rejets

Sur le pull-down : série = ET, parallèle = OU, chaque feuille porte le net
de grille. `OUT = NOT(f_pulldown)`.

**Grammaire v1 = formes pures uniquement** : pull-down ∈ {feuille,
série(feuilles), parallèle(feuilles)} ; le pull-up doit être la forme pure
complémentaire avec le MÊME multiset de grilles. (Dans cette grammaire,
cette vérification est équivalente à la dualité d'arbres ; le comparateur
canonique général est différé à AOI v2 — la représentation, elle, est déjà
générale.)

- 1 + 1 (avec critère D/S) → `Inverseur (CMOS)` ;
- pull-down série de N feuilles → `Porte NAND (CMOS)` (N entrées) ;
- pull-down parallèle de N feuilles → `Porte NOR (CMOS)` (N entrées).

**Rejets explicites (chacun = un test nommé)** :
- grille d'un transistor du réseau sur un rail ou une masse ;
- `sortie ∈ entrees` (grille rebouclée sur OUT) ;
- grilles dupliquées dans un réseau (deux feuilles de même net) ;
- un réseau pull-up atteignant DEUX rails différents (le rejet est PAR
  candidat : deux portes du même fichier peuvent utiliser des rails
  différents, `nodes['vdd']` est un attribut du match) ;
- arbre non pur (AOI valide compris), réseau non série/parallèle,
  non-dualité des formes ou des multisets ;
- nets internes d'empilement candidats (rejetés par la non-dualité —
  invariant verrouillé par un test dédié sur NAND3).

Jamais d'exception sur un réseau exotique : tout rejet retourne zéro match,
les MOSFET retombent sur le pipeline actuel (détecteurs analogiques,
satellites, puces grisées pour les orphelins — mécanisme existant).

### 1.5 Contrat du match

```python
{
  'circuit_type': 'Porte NAND (CMOS)',   # ou 'Inverseur (CMOS)' / 'Porte NOR (CMOS)'
  'components':   ['M1', 'M2', 'M3', 'M4'],
  'nodes': {'entrees': ['A', 'B'], 'sortie': 'OUT',
            'vdd': 'VDD', 'gnd': 'GND'},
  'io': {'ins': ['A', 'B'], 'out': 'OUT'},          # contrat de ROUTAGE
  'polarites': {'M1': 'P', 'M2': 'P', 'M3': 'N', 'M4': 'N'},
  'arbres': {'pull_down': <arbre>, 'pull_up': <arbre>},  # pour le drawer détaillé
  'fonction': ('NAND', ['A', 'B']),                  # forme STRUCTURÉE (v2 : composition XOR)
  'expression': 'OUT = NAND(A, B)',                  # forme d'AFFICHAGE
}
```

- `entrees`/`ins` ordonnées par tri alphabétique des nets (déterminisme).
- **`io` est le contrat de routage** : `_io_montage` (circuit_viewer.py) lit
  `match['io']` EN PRIORITÉ s'il existe, sinon retombe sur les whitelists
  actuelles — aucune whitelist n'est étendue, aucune famille future n'en
  étendra. `nodes` reste le dict descriptif (affichage, rapport).
- Le plan comporte une tâche d'**audit des consommateurs de `nodes`**
  (rapport, satellites, gain, dessin) : la liste `entrees` ne doit casser
  aucune itération qui suppose des valeurs scalaires.
- Les drawers lisent `arbres` et `polarites` : ils ne re-dérivent JAMAIS la
  structure (pas de duplication détection/affichage).

## 2. Affichage — nouveau module `gui/logic_schematic.py`

Les drawers de portes vivent dans un module dédié (précédent :
impedance_schematic.py) — circuit_viewer.py (~4 000 lignes) ne reçoit que
l'enregistrement dans `_DRAWERS` et la lecture prioritaire de `io` dans
`_io_montage`.

### Vue simplifiée (drawer symbole)

- `schemdraw.logic.Not / Nand / Nor` (v0.22 installée, `inputs=N`),
  stubs d'entrées étiquetés par net, stub OUT, style existant (couleurs
  thème, canvas clair `#fafafa` inchangé).
- **Registre de positions** : TOUTES les refs M du montage sont enregistrées
  sur le centre du symbole (`_enregistrer_position`) — une puce M1 cliquée
  focalise la porte ; aucune puce grisée en vue simplifiée.
- En-tête fenêtre îlot : si le montage principal porte `expression`, elle
  s'affiche là où va le gain AOP (généralisation de `_texte_gain`).
  Îlot multi-portes : pas d'expression composée (v1 assumé).

### Vue détaillée (drawer transistors)

- PMOS côté VDD, NMOS côté GND, agencés d'après `match['arbres']`
  (empilés si série, côte à côte si parallèle), grilles câblées vers des
  stubs d'entrée communs, nœud OUT au milieu.
- Symboles `elm.PFet`/`elm.NFet` — piège connu : NFet met la grille à
  DROITE par défaut → `.reverse()` (tests de garde existants).
- Chaque M enregistre SA position (contrat tests/test_puces_resolution.py).
- Dispatch simplifié/détaillé : même mécanisme `d._mode_detaille` posé par
  `_make_fig` que les montages actuels — ce contrat implicite devient ici
  un contrat assumé (noté au ledger de dette).
- Le drawer retourne le MÊME contrat d'ancres que les drawers transistor
  (dict avec `nets`, points in/out) : satellites rattachés et couplages Z
  restants passent par `_dessiner_impedances_locales` comme aujourd'hui —
  vérifié par un fichier corpus dédié (R série de grille).

### Îlots / bandeau

`_circuit_principal_ilot` compte les montages (la porte en est un), le
bandeau dynamique liste les M, le toggle et le clic-focus fonctionnent par
contrat. Topologies bouclées (latch SR, inverseurs croisés) : détectées
porte par porte ; l'ordonnancement chaîne/DAG échoue proprement et le
rendu de repli est CONSTATÉ en fenêtre réelle puis FIGÉ par un fichier
corpus (`logic_latch_sr.xml`) — pas de mise en page bouclée en v1.

## 3. Corpus et tests (TDD strict)

Nouveaux circuits `circuits_industriels/logic_*.xml` (via
`circuit_analyzer/xml_generator.py`, ou écrits à la main s'il ne sait pas
câbler du multi-entrées) :

| Fichier | Contenu | Attendu |
|---|---|---|
| logic_cmos_not.xml | 1P+1N, S aux rails | Inverseur (CMOS) |
| logic_cmos_nand2.xml | 2P ∥ + 2N série | Porte NAND (2 entrées) |
| logic_cmos_nand3.xml | 3P ∥ + 3N série | Porte NAND (3 entrées) + test nets internes |
| logic_cmos_nor2.xml | 2P série + 2N ∥ | Porte NOR (2 entrées) |
| logic_chaine_and.xml | NAND2 → NOT | chaîne de 2 portes |
| logic_dag_2vers1.xml | 2 portes → 1 porte | DAG en couches (boucle visuelle) |
| logic_latch_sr.xml | 2 NOR croisés | 2 portes, rendu de repli figé |
| logic_not_r_grille.xml | inverseur + R série d'entrée | satellite dessiné |
| logic_suiveur_mos.xml | paire S-à-OUT | AUCUNE porte (rejet D/S) |
| logic_non_dual.xml | pull-up ≠ dual | AUCUNE porte (unitaire SEULEMENT, hors globs visuels) |

- Unitaires `tests/test_logique.py` : réseaux, polarités, critère D/S (3 cas :
  détecté / suiveur rejeté / panaché rejeté), N entrées, la fonction
  STRUCTURÉE (`('NAND', ['A','B'])`, pas les chaînes d'affichage), et TOUS
  les rejets du § 1.4 (un test nommé chacun).
- **Anti-faux-positifs** : le détecteur de portes sur TOUT le corpus
  analogique existant = zéro match.
- **Non-régression matcher** : snapshot des `circuit_type` détectés sur tout
  `circuits_industriels/` avant/après l'insertion en tête.
- **Rapport et onglet analyse** : le rapport d'un fichier logic_* se génère
  sans exception et contient l'expression ; tab_analyze affiche les
  nouveaux types.
- **Contrats corpus étendus** : globs de tests/test_labels_property.py,
  tests/test_puces_resolution.py et tools/render_ilots_v2.py + `logic_*.xml`
  (sauf logic_non_dual) — zéro nouvelle exclusion de puce visée.
- **Perf** : circuit généré ~500 portes ajouté au corpus de perf, budget
  d'`analyser()` asserté (protège l'acquis 5 000 comps → 3,3 s).
- Boucle visuelle boss : sweep + inspection PNG des deux vues de chaque
  porte avant livraison.

## 4. Carte d'évolutivité (v2)

- **AOI/OAI** : ajouter le comparateur canonique d'arbres + cas de
  classification — l'algèbre isolée (§ 1.2) et l'arbre embarqué (§ 1.5)
  suffisent, rien d'autre à préparer.
- **XOR/XNOR** : couche de COMPOSITION au-dessus des matches (motifs dans le
  DAG de portes, via `fonction` structurée) — n'entre pas dans le cadre
  candidat/réseaux-duaux et ne modifiera pas logique.py.
- **Transmission gates** : prérequis = palette NMOS/PMOS (jalon v2 acté).
- **Dette notée au ledger** : `d._mode_detaille` contrat implicite assumé ;
  whitelists `_io_montage` (le champ `io` arrête l'hémorragie, le
  découplage clé/libellé des circuit_type reste un refactor dédié).
