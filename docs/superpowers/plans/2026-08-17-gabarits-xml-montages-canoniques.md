# Gabarits XML pour les montages canoniques — Implementation Plan

> Suite de : `docs/superpowers/specs/2026-08-10-gabarits-xml-montages-canoniques-design.md`
> (design validé par le boss le 2026-08-17, version complète : détection ET disposition).

**Goal:** Permettre au boss de redéfinir un montage canonique (ce que
l'analyseur reconnaît ET comment il le dispose) en dessinant un schéma
normal — zéro code, zéro JSON — plutôt qu'en éditant du Python.

**Architecture:** Nouveau module `circuit_analyzer/gabarit.py` : moteur de
correspondance structurelle générique, ancré sur LE composant à 3+ broches
du gabarit (l'AOP, le transistor…). Pour chaque broche NOMMÉE de l'ancre, le
moteur classe les voisins directs (composants à 2 broches) en 3 familles :
vers une AUTRE broche nommée de la même ancre (contre-réaction), vers un
rail masse/alim (par FONCTION, `is_gnd`/`is_power`, jamais par nom de net),
ou externe (ni l'un ni l'autre). Deux broches de l'ancre directement au même
nœud (court-circuit) sont détectées séparément. Le même gabarit sert aussi
de patron de DISPOSITION : les positions réelles du schéma de référence
(`<CtrIem>`) sont lues et reproduites (translatées) sur le montage détecté.

**Découpage en phases (repris du design, sécurité à chaque étape) :**
- **Phase 1 (CE PLAN)** : preuve du mécanisme sur 2 montages SANS répétition
  (Suiveur de tension, Amplificateur inverseur). Moteur autonome, testé
  isolément — PAS encore branché dans `analyser()` (les détecteurs Python
  existants restent actifs, rien ne change pour l'utilisateur final tant que
  la Phase 3 n'est pas faite).
- **Phase 2 (futur)** : inférence de répétition (N résistances structurellement
  identiques sur une broche → « 1 ou plus »), migration du Sommateur.
- **Phase 3 (futur)** : les 21 montages restants + bascule réelle dans
  `analyser()`, gardée par « produit EXACTEMENT les mêmes matches que
  l'ancien code sur toute la suite de tests existante, sinon l'ancien
  détecteur reste actif ».

## Global Constraints

- Aucun footer Claude dans les commits ; jamais `git add -A`.
- Valeurs de composants (10k, 100nF…) JAMAIS comparées — seuls types, rôles
  et connexions comptent (cf. comportement des 24 détecteurs actuels).
- Rôle masse/alimentation reconnu par FONCTION (`is_gnd`/`is_power`), jamais
  par nom de net exact.
- Gabarit structurellement ambigu (0 ou 2+ composants à 3+ broches) → rejeté
  proprement (liste vide), jamais de faux positif deviné.
- `patterns_reference/` : un fichier BoardSCH XML par montage, même
  principe qu'un fichier par composant dans la bibliothèque partagée.

---

### Task 1 : Dossier `patterns_reference/` + 2 gabarits de départ

**Files:** `patterns_reference/Suiveur de tension.xml`,
`patterns_reference/Amplificateur inverseur.xml` (nouveaux, générés via
`circuit_analyzer.xml.generer_xml` — même mécanisme que l'export normal,
donc ouvrables tels quels dans ERetroDesign ou l'éditeur Python).

- [x] Générer les 2 fichiers à partir de `Composant` minimaux fidèles aux
  schémas des détecteurs existants (`detecteur.detecter_suiveur_tension`,
  `detecteur.detecter_amplificateur_inverseur`) : un AOP (`U`, pins
  IN+/IN-/OUT/V+/V-) +, pour l'inverseur, 2 résistances (Zin, Zf).
- [x] Ouvrir chaque fichier avec `lire_xml` + `construire_graphe`, vérifier
  à la main qu'il reproduit le graphe attendu (broches nommées, nets
  cohérents) — pas de supposition, mesuré.

### Task 2 : Moteur de correspondance (`circuit_analyzer/gabarit.py`)

**Interfaces:**
- `charger_gabarit(chemin) -> Gabarit | None` — lit le XML, construit le
  graphe, identifie l'ancre (le seul composant à 3+ broches ; None si 0 ou
  2+), construit l'empreinte structurelle. `None` si ambigu (fail-closed).
- `Gabarit.correspondre(graphe_cible) -> list[dict]` — cherche, dans le
  graphe cible, un(des) composant(s) du même type que l'ancre dont la
  structure de broches reproduit EXACTEMENT l'empreinte (Phase 1 : compte
  exact, pas de généralisation « 1 ou plus », voir Phase 2). Retourne des
  matches au même format que les détecteurs existants (`circuit_type` =
  nom du fichier gabarit sans extension, `components`, `nodes`,
  `confidence`, `functional_category`, `reasons`, `warnings`, `satellites`).
- `Gabarit.positions_canoniques(refs_matchees, x, y) -> dict[ref, (x,y[,angle])]`
  — dérive les positions à écrire depuis `<CtrIem>` du gabarit (translation
  relative à l'ancre, comme `_positionner_amplificateur_inverseur` mais
  lu depuis le dessin plutôt qu'écrit à la main).

- [x] **Étape 1 : tests qui échouent d'abord**
  - `test_gabarit_charge_suiveur_et_matche_un_suiveur_reel` : un circuit
    minimal (AOP, IN- == OUT) matche.
  - `test_gabarit_suiveur_ne_matche_pas_un_inverseur` : anti-faux-positif.
  - `test_gabarit_charge_inverseur_et_matche` : AOP + 2 R (Zin, Zf vers OUT).
  - `test_gabarit_ambigu_zero_ancre_rejete` (que des R/C, aucun composant
    3+ broches) : `charger_gabarit` retourne None.
  - `test_gabarit_ambigu_deux_ancres_rejete` (2 AOP dans le fichier) : None.
  - `test_gabarit_ignore_les_valeurs` : même structure, valeurs différentes
    du gabarit (10k dans le gabarit, 47k dans la cible) → matche quand même.
  - `test_gabarit_positions_canoniques_translate_depuis_lancre` : les
    positions dérivées sont bien relatives à la position de l'ancre trouvée
    dans la cible, pas absolues copiées du gabarit.
- [x] **Étape 2 : lancer, vérifier l'échec** (`ModuleNotFoundError`).
- [x] **Étape 3 : implémenter** `gabarit.py`.
- [x] **Étape 4 : lancer, vérifier le succès.**

### Task 3 : Parité avec les détecteurs Python existants (preuve, pas bascule)

**Files:** `tests/test_gabarit_parite.py` (nouveau).

- [x] Sur CHAQUE cas de test existant de `detecter_suiveur_tension` et
  `detecter_amplificateur_inverseur` (`tests/test_detecteur*.py` ou
  équivalent — repérer les cas exacts), faire tourner AUSSI le gabarit et
  comparer `components`/`nodes` (le `circuit_type` peut différer par le nom
  de fichier, documenté, pas un échec). Un seul écart → chantier NON prêt
  pour la Phase 3 sur ce montage, documenté, pas corrigé en force.
- [x] Suite complète `pytest tests/ -q` : zéro régression (le moteur
  n'est appelé nulle part encore dans `analyser()`).

## Fin de chantier (Phase 1)

- [x] Mettre à jour le statut de la spec/section correspondante : Phase 1
  livrée, Phase 2/3 restent à planifier séparément.
- [x] Rapport au boss : le mécanisme marche de bout en bout sur 2 montages
  simples ; PAS encore branché dans l'analyse réelle (aucun changement de
  comportement pour l'instant) — décision explicite avant de faire les 22
  montages restants un par un.

---

## Phase 2 — Inférence de répétition (LIVRÉE, 2026-08-17)

**Goal:** Généraliser une case qui montre 2+ occurrences dans le gabarit en
« 2 ou plus » côté cible, sans coder le seuil en dur par montage — reproduit
`detecter_amplificateur_sommateur` (`len(zin) >= 2`). Seuil verrouillé à 2
(pas 1) pour ne jamais faire collision avec un montage à une seule
occurrence déjà distinct côté détecteurs Python (ex. l'inverseur).

**Files:** `circuit_analyzer/gabarit.py`, `patterns_reference/Amplificateur sommateur.xml`
(nouveau, 3 entrées illustratives + 1 feedback), `tests/test_gabarit.py`,
`tests/test_gabarit_parite.py`.

- [x] `_empreinte` restructurée : voisins groupés par (type, catégorie)
  plutôt qu'en liste plate — la taille du groupe est ce qu'on compare, pas
  chaque élément un par un.
- [x] `_empreintes_correspondent` : nouvelle règle de comparaison (exact si
  le gabarit montre < 2 occurrences, "≥ 2" si le gabarit en montre déjà 2+).
- [x] Tests : 2 entrées (minimum), 5 entrées (plus que l'exemple dessiné),
  1 seule entrée → AUCUN match (anti-collision avec l'inverseur), positions
  empilées sans jamais se superposer.
- [x] **BUG TROUVÉ EN TESTANT** (pas supposé) : un composant qui relie DEUX
  broches nommées de l'ancre à la fois (ex. la résistance de feedback,
  entre IN- et OUT) apparaissait comme voisin depuis CHACUNE des deux
  broches → comptée deux fois dans `components`/`placement`. Invisible en
  Phase 1 car les tests comparaient des `set(...)` (le doublon s'y noyait
  en silence) ; démasqué par un test Phase 2 qui compare une longueur
  exacte. Corrigé par une garde `deja_vus` dans `correspondre()`.
- [x] Parité avec `detecter_amplificateur_sommateur` : 2 entrées, 4 entrées,
  et non-régression (1 entrée ne matche ni l'ancien détecteur ni le
  gabarit) — 3 nouveaux tests, tous verts.
- [x] Suite complète : 2373 passés / 15 échecs (mêmes 15 préexistants,
  vérifiés inchangés), zéro régression.

## Fin de chantier (Phase 2)

- [x] Le moteur gère maintenant les montages SANS et AVEC répétition.
  Toujours PAS branché dans `analyser()` — Phase 3 (bascule réelle + les
  21 montages restants) reste à planifier séparément, décision du boss.

---

## Phase 3 — Migration montage par montage (EN COURS, 2026-08-17)

**Goal:** Prouver le gabarit sur chacun des 21 montages restants, un par un,
par parité stricte avec son détecteur Python (mêmes garde-fous que Phases 1
et 2 : jamais de bascule réelle tant qu'un montage n'a pas sa parité prouvée).

### Lot 1 — 4 montages AOP structurellement proches de l'inverseur (LIVRÉ)

**Files:** `patterns_reference/Amplificateur non-inverseur.xml`,
`patterns_reference/Integrateur.xml`, `patterns_reference/Derivateur.xml`,
`patterns_reference/Amplificateur differentiel.xml` (nouveaux) ;
`tests/test_gabarit_parite.py` (8 nouveaux tests).

- [x] **Amplificateur non-inverseur** : Zf (IN- → OUT) + Zg (IN- → GND,
  classé rail par FONCTION, pas par nom) — preuve que le moteur distingue
  déjà nativement ce cas du pont de l'inverseur (Zg → rail vs Zin → externe),
  sans aucune modification du moteur.
- [x] **Intégrateur** / **Dérivateur** : structurellement IDENTIQUES à
  l'inverseur (Zin sur IN-, Zf → OUT) mais différenciés uniquement par le
  TYPE de composant (C en feedback vs C en entrée) — preuve que le
  groupement par `(type, catégorie)` de l'empreinte (déjà en place depuis la
  Phase 2) suffit à les séparer sans code dédié, et qu'aucun croisement
  Intégrateur↔Dérivateur↔Inverseur ne se produit (testé dans les deux sens).
- [x] **Amplificateur différentiel** : premier montage migré qui utilise
  DEUX broches nommées de l'ancre à la fois (IN+ ET IN-, chacune avec son
  propre pont Z) — preuve que le moteur généralise correctement à plusieurs
  broches structurées simultanément, pas seulement IN-.
- [x] Parité stricte avec `detecter_amplificateur_non_inverseur`,
  `detecter_integrateur`, `detecter_derivateur`,
  `detecter_amplificateur_differentiel` : cas positif + cas croisé
  (structure d'un AUTRE montage, doit échouer des deux côtés) pour chacun —
  16 tests, tous verts au premier passage (aucun bug trouvé ce lot-ci,
  contrairement au lot Sommateur qui avait révélé le bug de double-comptage
  Phase 2).
- [x] Suite complète : 2381 passés / 15 échecs (mêmes 15 préexistants,
  vérifiés inchangés), zéro régression.

**Total migré après le lot 1 : 7 / 25 montages** (Suiveur, Inverseur, Sommateur,
Non-inverseur, Intégrateur, Dérivateur, Différentiel).

### BUG CRITIQUE trouvé et corrigé avant le lot 2 (2026-08-17)

**Reproduit AVANT correction avec un cas minimal** (pas hypothétique) : une
broche d'ancre reliée DIRECTEMENT à un rail (ex. IN+ à GND sur l'inverseur)
scannait quand même les "voisins 2-broches" de ce net. Sur une vraie carte
scannée, GND est un net PARTAGÉ par des dizaines de composants sans aucun
rapport (découplage ailleurs, autres étages...). Conséquence : un inverseur
parfaitement valide cessait de matcher dès qu'UN SEUL composant
supplémentaire, n'importe où sur la carte, touchait GND — **le moteur
aurait échoué sur quasiment toute vraie carte scannée avec plus de 2-3
composants**, alors qu'il passait tous les tests (fixtures isolées, jamais
plus d'un composant sur GND). C'est exactement le type de bug que la
méthode « mesurer, ne jamais deviner » de ce projet est censée intercepter
— trouvé ici en anticipant le passage à des montages transistor/MOSFET
dont la broche (émetteur/source) doit être DIRECTEMENT sur un rail.

**Corrigé** dans `_empreinte` (`circuit_analyzer/gabarit.py`) : une broche
dont le NET LUI-MÊME est un rail n'est plus scannée pour ses voisins —
marquée directement `('rail', 'gnd'|'power')`, indépendamment de ce qui est
connecté ailleurs sur ce rail. Sert aussi de nouvelle capacité : "broche
directement au rail, zéro composant intermédiaire" (nécessaire pour les
montages transistor/MOSFET du lot 2).

**Deuxième bug, plus mineur, trouvé en écrivant le test de non-régression**
du premier : une broche du gabarit dont le groupe de voisins est VIDE (rien
dessiné dessus) ne contraignait rien côté cible — une cible avec des
composants EN TROP sur cette broche passait quand même. Corrigé dans
`_empreintes_correspondent` (la comparaison `set(...)` existait déjà mais
son effet réel n'avait jamais été vérifié par un test dédié).

Suite complète après ces deux corrections : 2383 passés / 15 échecs (mêmes
15 préexistants, vérifiés inchangés), zéro régression. 2 nouveaux tests de
non-régression permanents (`test_gabarit_rail_partage_ailleurs_sur_la_carte_ne_casse_pas_le_match`,
`test_gabarit_broche_vide_rejette_tout_voisin_supplementaire`).

### Lot 2 — broche directement sur un rail (LIVRÉ)

**Files:** `patterns_reference/Comparateur.xml`,
`patterns_reference/Transistor en commutation.xml`,
`patterns_reference/Collecteur commun (suiveur d'emetteur).xml`,
`patterns_reference/MOSFET en commutation.xml`,
`patterns_reference/MOSFET haute-tension (cote haut).xml` (nouveaux) ;
`tests/test_gabarit_parite.py` (9 nouveaux tests).

- [x] **Comparateur** : AOP nu, aucun voisin dessiné sur OUT/IN+/IN- — le
  premier montage qui dépend directement de la correction "broche vide"
  ci-dessus (sans elle, n'importe quel AOP avec contre-réaction aurait
  aussi matché ce gabarit).
- [x] **Transistor en commutation** : émetteur DIRECTEMENT à GND (0 saut,
  pas un voisin) — premier montage non-AOP migré, premier à utiliser la
  correction "rail direct".
- [x] **Collecteur commun (suiveur d'émetteur)** : collecteur directement
  sur VCC + Re (émetteur → GND par un voisin, pas directement) + Rb sur la
  base — combine rail direct (collecteur) ET rail par voisin (Re) sur le
  même montage.
- [x] **MOSFET en commutation** et **MOSFET haute-tension (côté haut)** :
  même patron que les transistors BJT, appliqué à G/D/S.
- [x] **Limitation documentée (pas corrigée, hors périmètre)** : le vrai
  détecteur `detecter_mosfet_commutation` accepte la source DIRECTEMENT à
  GND **OU** via une seule résistance de sense (`_source_relie_a_la_masse`,
  disjonction). Un gabarit unique ne peut représenter qu'UNE seule forme
  structurelle à la fois — celui migré ici ne couvre que la forme directe
  (source = GND, sans résistance de sense). La variante avec résistance de
  sense reste seulement gérée par le détecteur Python. Documenté dans le
  test `test_parite_mosfet_commutation_cas_simple`, pas silencieusement
  ignoré.
- [x] Parité stricte (cas positif + cas croisé pour chaque montage) : 9
  tests, TOUS verts au premier passage (aucun bug supplémentaire trouvé ce
  lot-ci, contrairement au travail préparatoire qui avait révélé les 2 bugs
  critiques ci-dessus).
- [x] Suite complète : 2393 passés / 15 échecs (mêmes 15 préexistants),
  zéro régression.

**Total migré à ce stade : 12 / 25 montages « à ancre unique »** (les 7 du
lot 1 + les 5 du lot 2). Aucun n'est encore branché dans `analyser()` —
décision de bascule réelle toujours en attente du boss.

### Ce qui reste, et pourquoi ce sont des chantiers séparés (pas une suite directe)

Après avoir lu les 27 détecteurs en entier, le reste se répartit en
familles dont AUCUNE ne tient dans le modèle actuel "une ancre à 3+ broches,
voisins classés par rôle" — chacune demanderait une extension d'architecture
distincte, avec son propre cycle conception → tests → preuve, comme le lot 2
ci-dessus (pas une simple suite de gabarits à dessiner) :

1. **Relations à DEUX ancres** (Push-pull, Paire Darlington, Miroir de
   courant BJT) : la structure recherchée est une RELATION entre deux
   composants à 3+ broches (ex. l'émetteur de Q1 attaque la base de Q2),
   pas "un composant + ses voisins 2-broches". Le moteur actuel ne compare
   jamais deux ancres entre elles.
2. **Cycle sans ancre** (Pont redresseur de Graetz) : 4 diodes (toutes à 2
   broches) formant une boucle fermée — AUCUN composant à 3+ broches dans
   ce montage, le moteur actuel rejette un tel gabarit comme "ambigu, 0
   ancre trouvée" par construction (fail-closed voulu).
3. **Composition INTERNE d'un bloc composite** (Correcteur PI, Dérivateur
   partiel) : distingués uniquement par la forme R+C SÉRIE vs R//C
   PARALLÈLE d'un même bloc de contre-réaction (`_est_rc_serie`/
   `_est_rc_parallele`, après réduction du graphe) — le moteur actuel
   classe un voisin par (type, catégorie) mais n'inspecte jamais
   l'intérieur d'une impédance composite.
4. **Ancre à 2 broches** (Diode de roue libre, Diode de protection ESD,
   Redresseur simple, Détecteur de crête) : ces 4 montages sont ancrés sur
   une DIODE (2 broches, pas 3+) — le moteur actuel exige explicitement 3+
   broches pour qu'un composant soit une "ancre" candidate.
5. **Catch-all structurellement vide, PERMANENTS** (Impédance Z, Diodes non
   classifiées) : émettent littéralement "tout ce qui reste après les
   autres détecteurs" — il n'existe AUCUN schéma de référence sensé à
   dessiner pour "un composant non classifié". Ces deux détecteurs Python
   ne seront JAMAIS candidats à la migration, par nature, pas par manque de
   temps.
6. **Ampli émetteur commun** : structurellement proche du lot 2 (Q, R
   collecteur, R base) mais porte une règle qui inspecte les AUTRES
   composants Q du circuit (`base_couplee_dc` : la base est-elle couplée en
   DC au collecteur d'un AUTRE transistor ?) — relève de la famille #1
   (relation entre ancres), pas d'une simple broche/voisin.
7. **Bascule de Schmitt** : la résistance d'entrée (Zin) sur IN+ est
   OPTIONNELLE côté détecteur Python (matche avec OU sans) — un gabarit
   représente UNE structure fixe ; dessiné sans Zin, il rejetterait à tort
   tout montage qui EN a un (le groupe de voisins sur IN+ ne serait plus
   vide). Nécessite soit plusieurs gabarits pour un même nom de montage
   (capacité pas encore construite), soit une notion de "composant
   optionnel" dans le format d'empreinte — pas juste un dessin de plus.

Chacune de ces 7 familles reste un détecteur Python actif et inchangé —
aucune régression, juste pas encore migrée.

---

## Lot 4 — ancre à 2 broches (LIVRÉ, 2026-08-17)

**Files:** `patterns_reference/Diode de roue libre.xml`,
`patterns_reference/Diode de protection ESD.xml` (nouveaux) ;
`tests/test_gabarit.py` (règle d'ancre généralisée + 3 tests réécrits) ;
`tests/test_gabarit_parite.py` (6 nouveaux tests).

- [x] **Généralisation de la règle d'ancre** (`charger_gabarit`) : au lieu
  d'un seuil FIXE "≥ 3 broches", l'ancre est désormais le(s) composant(s)
  possédant le NOMBRE MAXIMAL de broches du fichier (≥ 2). Un fichier
  AOP+résistances garde exactement le même comportement qu'avant (5 > 2,
  un seul candidat) ; un fichier diode SEULE accepte enfin la diode comme
  ancre (2 == 2, seule candidate) ; un fichier diode+résistance (comme
  "Redresseur simple") reste CORRECTEMENT rejeté comme ambigu (2 candidats
  à 2 broches chacun) — pas une régression, une limitation documentée.
- [x] **Diode de roue libre**, **Diode de protection ESD** : chacune
  ancrée sur une diode SEULE (aucun autre composant dans le fichier de
  référence).
- [x] Vérifié empiriquement : sur un cas REPRÉSENTATIF d'une vraie carte
  (l'anode de la diode de roue libre est le collecteur d'un vrai
  transistor de commutation, pas un nœud isolé), le match reste correct —
  `construire_graphe` ne crée jamais d'arête pour un composant à 3+
  broches, donc l'anode n'a "aucun voisin 2-broches" au sens du moteur,
  exactement comme dans le fichier de référence isolé.
- [x] **Divergence réelle documentée (pas corrigée)** : le vrai détecteur
  `detecter_diode_protection_esd` ignore ce qui est branché sur l'AUTRE
  broche de la diode ; le gabarit exige une structure identique à la
  référence — testé explicitement des deux côtés
  (`test_gabarit_diode_esd_avec_passif_supplementaire_sur_le_signal_echoue_cote_gabarit`).
- [x] Suite complète : 2401 passés / 15 échecs (mêmes 15 préexistants),
  zéro régression.

**Total migré à ce stade : 14 / 25 montages.**

## Lot 5 — relations à DEUX ancres (LIVRÉ, 2026-08-17)

**Files:** `circuit_analyzer/gabarit.py` (nouveau mécanisme ADDITIF
`GabaritRelation`/`charger_gabarit_relation`, séparé du moteur à une seule
ancre — zéro modification du code déjà prouvé des lots précédents) ;
`patterns_reference/Miroir de courant BJT.xml`,
`patterns_reference/Etage push-pull.xml`,
`patterns_reference/Paire Darlington.xml` (nouveaux) ;
`tests/test_gabarit_relation.py` (nouveau, 10 tests du mécanisme) ;
`tests/test_gabarit_parite.py` (6 nouveaux tests).

- [x] **Architecture** : les broches de DEUX ancres sont labellisées
  `(index_ancre, nom_broche)` au lieu de juste `nom_broche` — cette seule
  généralisation fait apparaître les courts-circuits ENTRE les deux ancres
  (ex. émetteur de Q1 == base de Q2 pour le Darlington) dans le MÊME
  mécanisme `courts` qui gérait déjà les courts-circuits internes à une
  ancre — `_empreintes_correspondent` (Phase 2) est réutilisée TELLE
  QUELLE, elle ne connaît pas la forme des clés de broche.
- [x] **Miroir de courant BJT** (relation SYMÉTRIQUE : bases communes,
  émetteurs directement à GND).
- [x] **Étage push-pull** (relation SYMÉTRIQUE : émetteurs communs, un
  collecteur sur l'alim, l'autre à la masse).
- [x] **Paire Darlington** (relation DIRECTIONNELLE : émetteur de Q1 →
  base de Q2, PAS l'inverse) — le moteur essaie TOUTES les paires
  ORDONNÉES de candidats, couvre nativement le cas directionnel sans
  logique séparée du cas symétrique ; dédoublonné par paire NON ordonnée
  de références pour ne jamais rapporter la même paire deux fois.
- [x] 16 tests au total (mécanisme + parité), TOUS verts au premier
  passage.
- [x] Suite complète : 2418 passés / 15 échecs (mêmes 15 préexistants),
  zéro régression.

**Total migré à ce stade : 17 / 25 montages.**

## Ce qu'il reste (mis à jour après les lots 4 et 5)

1. **Cycle sans ancre** (Pont redresseur de Graetz) : 4 diodes formant une
   boucle fermée, aucun composant à 3+ broches. Ni le moteur à une ancre
   ni celui à deux ancres ne couvrent une boucle à 4 — demande un
   troisième mécanisme dédié (recherche de cycle), pas une généralisation
   de l'existant.
2. **Composition INTERNE d'un bloc composite** (Correcteur PI, Dérivateur
   partiel) : distingués uniquement par la forme R+C SÉRIE vs R//C
   PARALLÈLE d'un même bloc — le moteur classe un voisin par (type,
   catégorie) mais n'inspecte jamais l'intérieur d'une impédance composite.
3. **Catch-all structurellement vide, PERMANENTS** (Impédance Z, Diodes non
   classifiées) — par nature jamais migrables.
4. **Ampli émetteur commun** : règle qui inspecte les AUTRES composants Q
   du circuit (`base_couplee_dc`) — relève en réalité du mécanisme à DEUX
   ancres (lot 5), candidat naturel pour un prochain lot.
5. **Bascule de Schmitt** : composant OPTIONNEL (Zin peut être présent ou
   absent) — nécessite soit plusieurs gabarits pour un même nom de
   montage, soit une notion de "composant optionnel" dans l'empreinte.

## Lot 6 — Amplificateur émetteur commun, forme simple (LIVRÉ, 2026-08-17)

**Files:** `patterns_reference/Amplificateur emetteur commun.xml`
(nouveau, ancre unique — pas besoin du mécanisme à deux ancres pour la
forme simple) ; `tests/test_gabarit_parite.py` (2 nouveaux tests).

- [x] Rc (collecteur → alim) + Rb (base → externe), collecteur PAS
  directement sur l'alim (négation qui émerge naturellement de la
  comparaison rail-tuple vs groupes-dict, sans code dédié).
- [x] Parité stricte : cas positif + cas croisé (collecteur direct sur
  VCC → ni l'ancien détecteur ni le gabarit ne matchent).
- [x] La variante "base couplée en DC au collecteur d'un AUTRE transistor"
  (`base_couplee_dc`) reste hors périmètre de ce lot — relève du mécanisme
  à deux ancres (lot 5), pourrait être tentée séparément plus tard.

**Total migré à ce stade : 18 / 25 montages.**

## Lot 7 — Bascule de Schmitt, forme sans Zin (LIVRÉ, 2026-08-17)

**Files:** `patterns_reference/Bascule de Schmitt.xml` (nouveau) ;
`tests/test_gabarit_parite.py` (3 nouveaux tests).

- [x] R de OUT vers IN+ (contre-réaction POSITIVE), rien dessiné sur IN-
  (IN- ≠ OUT, exclut le suiveur).
- [x] **Divergence réelle documentée** (même famille que MOSFET
  commutation / Diode ESD) : le vrai détecteur accepte Zin OPTIONNEL sur
  IN+ (avec ou sans) ; le gabarit, dessiné sans Zin, exige qu'IN+ n'ait
  STRICTEMENT que Rf. Prouvé explicitement des deux côtés
  (`test_gabarit_schmitt_avec_zin_divergence_documentee`) : une cible avec
  Zin matche toujours l'ancien détecteur, plus le gabarit.
- [x] Suite complète après lots 6+7 : 2419 passés / 15 échecs (mêmes 15
  préexistants), zéro régression.

**Total migré à ce stade : 19 / 25 montages "candidats".**

## Décision finale sur les 2 derniers cas (2026-08-17)

**Pont redresseur de Graetz — PAS un gap, une non-candidature justifiée.**
En relisant `detecter_pont_redresseur` en détail : sa règle est un cycle de
4 diodes, sans AUCUNE différence de rôle entre elles (`rails_sur_cycle` est
une simple annotation informative, jamais un filtre). Un gabarit dessiné
n'y changerait RIEN — n'importe quel pont à 4 diodes dessiné en référence
produirait exactement la MÊME règle ("cycle fermé de 4 D"), parce que la
règle est une propriété topologique FIXE, pas un patron variable comme les
19 montages déjà migrés (où le dessin fixe VRAIMENT quels rôles/rails
comptent). Construire un troisième mécanisme (recherche de cycle) pour
reproduire une règle qui ne peut structurellement pas varier selon ce qui
est dessiné serait de la machinerie inutile — aucun boss ne pourrait jamais
« redéfinir » ce montage en dessinant un pont différent, le résultat serait
toujours identique. Reste donc, à dessein, un détecteur Python pur —
décision technique, pas un manque de temps.

**Correcteur PI et Dérivateur partiel — gap réel, documenté, pas construit
ce chantier-ci.** Contrairement au pont, ces deux-là VARIENT réellement
selon ce qu'on dessine : ils se distinguent de l'Intégrateur/Dérivateur
migrés uniquement par la composition INTERNE du bloc de contre-réaction ou
d'entrée (R+C EN SÉRIE vs R//C EN PARALLÈLE, calculée par
`impedance.arbre_expr` après réduction du graphe). Un gabarit qui
dessinerait cette forme composite serait un candidat légitime, mais exige
d'apprendre au moteur à inspecter l'intérieur d'un bloc réduit — une
extension réelle, pas construite dans ce chantier, qui touche au pipeline
de réduction (`impedance.reduire`) plutôt qu'au graphe brut comme les 3
mécanismes actuels. Laissé pour un chantier séparé si le boss le demande.

## Bilan final de ce chantier (2026-08-17)

**19 / 27 détecteurs Python ont un gabarit migré et prouvé en parité
stricte** (Suiveur de tension, Amplificateur inverseur, Amplificateur
sommateur, Amplificateur non-inverseur, Intégrateur, Dérivateur,
Amplificateur différentiel, Comparateur, Transistor en commutation,
Collecteur commun/suiveur d'émetteur, MOSFET en commutation, MOSFET
haute-tension, Diode de roue libre, Diode de protection ESD, Miroir de
courant BJT, Étage push-pull, Paire Darlington, Amplificateur émetteur
commun, Bascule de Schmitt).

**2 / 27 sont des catch-alls PERMANENTS** (Impédance Z, Diodes non
classifiées) — n'existe aucun schéma de référence sensé à dessiner pour
« ce qui reste après tout le reste » ; ne seront jamais candidats.

**1 / 27 n'a pas besoin d'être migré** (Pont redresseur de Graetz) — règle
topologique fixe, un gabarit dessiné n'y changerait structurellement rien.

**5 / 27 restent un gap réel mais délimité**, chacun documenté avec sa
raison technique précise et son test de divergence quand applicable :
Correcteur PI et Dérivateur partiel (inspection de composition interne,
touche `impedance.reduire`), plus les variantes non couvertes de 3 montages
DÉJÀ migrés dans leur forme simple (MOSFET commutation sans la variante
« résistance de sense », Diode protection ESD sans passif supplémentaire
sur le signal, Bascule de Schmitt sans Zin).

**Trois mécanismes construits et prouvés cette session**, tous additifs,
zéro modification destructive de l'un par l'autre :
1. `Gabarit` (une ancre, Phase 1/2) — 15 montages.
2. `GabaritRelation` (deux ancres, lot 5) — 3 montages.
3. Aucun troisième mécanisme construit (Pont redresseur n'en avait pas
   besoin, voir décision ci-dessus).

**Deux bugs critiques trouvés et corrigés en cours de route** (voir plus
haut) : le bug de fan-out sur rail partagé (aurait cassé le moteur sur
quasiment toute vraie carte scannée avec 3+ composants) et le bug
d'application vide non contrainte (aurait laissé matcher des montages avec
contre-réaction en trop). Les deux ont leur test de non-régression
permanent.

**Rien de tout ceci n'est branché dans `analyser()`** — chaque migration
reste une preuve de parité isolée, jamais une bascule réelle sur les
analyses de l'utilisateur. La bascule (remplacer réellement un détecteur
Python par son gabarit dans le pipeline réel) reste une décision séparée,
explicitement en attente du boss, comme prévu depuis la Phase 1.

**Suite complète finale de ce chantier : 2419 passés / 15 échecs (mêmes 15
préexistants, vérifiés inchangés à chaque étape), zéro régression
introduite du début à la fin des 7 lots.**

---

## Lot 8 — Bascule réelle : ESSAYÉE, TROUVÉE PRÉMATURÉE, REVERTÉE (2026-08-17)

Le boss a explicitement demandé de brancher les 19 gabarits prouvés dans le
VRAI pipeline (`detecteur.analyser`), pas seulement les garder en preuve
isolée. Construit :

- `circuit_analyzer/gabarit.py` : `detecteurs_gabarit_pour_bascule()` charge
  les 19 fichiers de `patterns_reference/` et les enveloppe en fonctions
  détecteur compatibles, avec repli AUTOMATIQUE sur le détecteur Python
  d'origine si un fichier est absent/illisible/ambigu (jamais de perte
  silencieuse de détection par simple accident de fichier).
- `_CIRCUIT_TYPE_EXACT` : table de correspondance fichier → chaîne EXACTE du
  détecteur Python remplacé — **bug trouvé en vérifiant, avant toute
  bascule** : plusieurs noms de fichiers avaient dérivé sans accent (ex.
  "Etage push-pull" vs le vrai "Étage push-pull", "MOSFET haute-tension
  (cote haut)" vs "(côté haut)") — une bascule qui aurait utilisé le nom de
  fichier tel quel aurait rendu ces montages invisibles à `_CATEGORIES` et
  à tout code aval indexé par la chaîne littérale.
- `detecteur.py` : `_detecteurs_actifs()` substitue, à l'INTÉRIEUR de
  `analyser()` uniquement (les listes `_DETECTEURS_COMPLEXES`/
  `_DETECTEURS_SIMPLES` elles-mêmes restent 100% inchangées, toujours la
  référence Python pure), chaque détecteur dont le gabarit a chargé, EN
  PRÉSERVANT L'ORDRE exact (important pour l'anti-vol entre détecteurs).
  Gabarits mis en cache (chargés une seule fois par run, pas à chaque appel
  d'`analyser()` — coût I/O sinon répété inutilement).

**Vérifié empiriquement AVANT de considérer la bascule prête** (dans cet
ordre) :
1. Le moteur fonctionne correctement sur le graphe RÉDUIT (`impedance.reduire`),
   pas seulement le graphe brut testé jusque-là — y compris un vrai cas de
   réduction série (2 R combinées en une arête composite `Z1`) et un cas
   mixte R//C (confirmé NE PAS matcher à tort un gabarit pur-R ou pur-C).
2. Un appel `analyser()` de bout en bout sur un cas simple produit EXACTEMENT
   le bon `circuit_type`, la bonne `functional_category`, la bonne
   `confidence`/`reasons` (régénérées par `_enrichir`, pas besoin de les
   dupliquer côté gabarit).
3. **Test décisif : la suite complète, PAS seulement mes tests de parité.**
   C'est celui-ci qui a tout changé.

**Résultat du test décisif : régression réelle trouvée sur un vrai fichier
du corpus, bascule REVERTÉE le jour même.**

Sur `ilot_reel_darlington_relais_rlc.xml` (un vrai circuit du corpus de
test, pas une fixture synthétique), la bascule perdait DEUX détections que
le Python pur trouvait correctement (« Paire Darlington » et « Diode de
roue libre »), ce qui libérait leurs composants pour un motif personnalisé
sans rapport (`test impedances`, `custom_circuits.json`) dont le
`match()` renvoie `'nodes': []` — un plantage en aval
(`gui/circuit_viewer.py::_in_nets`, `IndexError: list index out of range`)
lors du rendu des îlots.

**Cause racine, diagnostiquée précisément (pas supposée) :**

Le moteur exige une correspondance EXACTE à CHAQUE broche nommée de
l'ancre, y compris les broches qui ne sont PAS le sujet du motif recherché
(ex. OUT d'un AOP, la broche « libre » d'une diode). Sur un vrai circuit
multi-étages, une telle broche porte très souvent, EN PLUS de ce que le
motif attend, un ou plusieurs composants légitimes que le petit schéma de
référence isolé ne montre pas (l'étage suivant, une charge, un
snubber...). Constaté concrètement :
- **Paire Darlington** : le gabarit exigeait que les DEUX collecteurs
  soient shortés au MÊME net littéral (comme dessiné dans la référence) ;
  sur le vrai fichier, les deux collecteurs touchent bien l'alimentation,
  mais chacun par un nœud local DIFFÉRENT — la règle Python réelle
  (`est_alimentation(q1.pins['C']) or q1.pins['C'] == q2.pins['C']`) est en
  réalité un OU asymétrique qui ne contraint QUE le premier transistor,
  jamais capturé par le modèle de correspondance structurelle stricte.
- **Diode de roue libre** : la broche anode de la référence (isolée, rien
  d'autre dans le fichier) exige zéro voisin ; sur le vrai fichier, l'anode
  réelle porte un composant voisin supplémentaire légitime (absent de la
  référence) — la même famille de divergence déjà documentée pour "Diode de
  protection ESD" et "Bascule de Schmitt" (voir lots 4 et 7), mais dont
  l'impact réel avait été sous-estimé : ce n'est PAS un cas rare, c'est ce
  qui arrive dès qu'une carte a plus de 2-3 composants autour du motif.

**Décision : risque jugé SYSTÉMIQUE, pas limité à ces deux montages** — la
même faiblesse (exiger l'exact, refuser le surplus légitime sur une broche
hors-rôle) pourrait toucher N'IMPORTE LAQUELLE des 19 broches "libres" sur
un autre fichier réel, pas seulement les deux trouvées ce jour-là. Plutôt
que de livrer un pipeline dont le comportement est PIRE que le Python pur
sur au moins un vrai fichier (perte de détection + plantage), la bascule a
été intégralement REVERTÉE le jour même : `_DETECTEURS_COMPLEXES`/
`_DETECTEURS_SIMPLES` restent 100% Python dans `analyser()`, exactement
comme avant ce lot. Le mécanisme de bascule (`_detecteurs_actifs`,
`detecteurs_gabarit_pour_bascule`, la table `_CIRCUIT_TYPE_EXACT`) reste en
place, testé et prêt, mais N'EST PLUS APPELÉ — prochaine tentative
seulement après l'extension nécessaire ci-dessous.

**Suite complète après revert : 2422 passés / 15 échecs (mêmes 15
préexistants), zéro régression, exactement comme avant ce lot.**

### Extension nécessaire avant une prochaine tentative de bascule (DÉTECTION)

Assouplir la comparaison sur les broches HORS-RÔLE du motif (celles qui ne
sont ni la contre-réaction ni un rail explicite du gabarit) : le groupe de
voisins dessiné dans la référence devrait être un SOUS-ENSEMBLE minimal
requis, pas une égalité stricte — la cible peut avoir PLUS, jamais moins.
Resterait strict uniquement sur les broches qui SONT le sujet du motif
(Zin/Zf, rails explicites) — c'est précisément là que la précision
structurelle a sa valeur. Chantier séparé, pas fait ce jour-là faute de
temps pour le concevoir et le tester avec le même niveau de rigueur que le
reste — décision du boss avant de s'y engager.

---

## Lot 9 — Disposition générique, SANS bascule de détection (LIVRÉ, 2026-08-17)

Demande explicite du boss après le revert du lot 8 : « the result in final
is the posibilite to add more schema canonique to the application and when
i export to the other app it will always be the same placement as the
schema canonique (same even if it new added) ». Clarification supplémentaire :
« the only thing u missed is the posibilite to add another canonique one
without hard coding it and still having the placement when exporting to
the other app ».

**Pourquoi ce lot ÉVITE le problème du lot 8** : le lot 8 touchait la
DÉTECTION (quels composants forment quel montage) sur le graphe ENTIER de
la carte — exposé au bruit d'un rail partagé ou d'un voisin d'un autre
étage. Ce lot-ci ne touche QUE la DISPOSITION d'un montage **déjà détecté**
par le détecteur Python (100% inchangé, jamais concerné) — le gabarit n'est
mis en correspondance qu'avec le SOUS-GRAPHE des composants déjà confirmés
appartenir à ce montage précis (`bloc.comps`, sortie du détecteur Python),
jamais le graphe entier de la carte. Le risque qui a fait échouer le lot 8
(un voisin supplémentaire légitime ailleurs sur la carte) ne peut
structurellement pas se produire ici, puisque ces voisins ne sont jamais
inclus dans le sous-graphe interrogé.

**Files:**
- `circuit_analyzer/gabarit.py` : `positions_depuis_gabarit(circuit_type,
  comps_du_bloc, x, y)` — construit un graphe à partir de `comps_du_bloc`
  UNIQUEMENT, fait correspondre le gabarit dessus, refuse (retourne `None`,
  jamais une exception) si 0 correspondance, si correspondance ambiguë, ou
  si la correspondance ne couvre pas EXACTEMENT tous les composants du bloc
  (jamais un placement partiel). `_gabarit_pour_disposition(circuit_type)` —
  cache paresseux, cherche `patterns_reference/{circuit_type EXACT}.xml`
  (recherche GÉNÉRIQUE par nom, aucune table à maintenir), avec un repli
  vers les noms de fichiers abrégés historiques des 19 gabarits déjà migrés
  (`_CIRCUIT_TYPE_EXACT_VERS_FICHIER`, compatibilité, pas requis pour un
  montage nouvellement ajouté).
- `circuit_analyzer/xml.py::_positionner_composants_bloc` : essaie le
  gabarit EN PREMIER (avant `_POSITIONNEURS_PAR_MOTIF` et tout le reste de
  la chaîne de repli existante, qui reste 100% inchangée) ; import différé
  (pas en tête de fichier) pour éviter un cycle d'import avec `gabarit.py`
  (qui importe déjà `lire_xml` DEPUIS `xml.py`).
- `tests/test_positions_depuis_gabarit.py` (nouveau, 4 tests).

**Zéro code Python à écrire pour ajouter un nouveau montage** : le fichier
doit simplement s'appeler EXACTEMENT comme le `circuit_type` déjà affiché
par l'analyseur (accents compris, ex. "Filtre RC passe-bas.xml") — vérifié
par une preuve en 3 étapes séparées (3 process Python distincts, pour
simuler fidèlement "le boss ajoute un fichier, puis relance une analyse") :
1. Un motif qui n'a JAMAIS eu la moindre ligne de code Python de
   positionnement écrite pour lui → repli générique (grille).
2. Le boss exporte un exemple minimal de son montage vers
   `patterns_reference/{nom exact}.xml` — AUCUN fichier `.py` modifié.
3. Nouveau process (nouvelle "analyse") : la disposition suit désormais le
   dessin, automatiquement.
- [x] Vérifié aussi sur les 2 fichiers réels qui avaient fait échouer le
  lot 8 (`ilot_reel_darlington_relais_rlc.xml`, `reel_555_astable.xml`) :
  détection strictement identique à toujours (Python pur, inchangé —
  « Paire Darlington » de nouveau détectée correctement), positionnement
  réussi sans le moindre plantage.
- [x] Suite complète : 2426 passés / 15 échecs (mêmes 15 préexistants),
  zéro régression.

**Résultat conforme à la demande du boss** : ajouter un schéma canonique
plus tard = déposer un fichier `.xml` nommé exactement comme le montage
dans `patterns_reference/` — aucun redémarrage de chantier de code requis,
la disposition à l'export suit ce dessin automatiquement dès la prochaine
analyse.

## Vérification finale : round-trip par la VRAIE appli C# (2026-08-18)

Demande explicite du boss : « test adding a schemas new one and send it to
the other app check that the placement works well ». Tout ce qui précède
n'avait été prouvé qu'avec des fichiers `generer_xml` (synthétiques) ou en
patchant à la main un fichier de carte scannée déjà existant — jamais avec
un schéma construit dans le VRAI `Form1`, avec de VRAIS composants de
bibliothèque, sauvegardé par le VRAI `SeveXMLFile.SaveData`.

Ajout dans `SizeTraceHarness/Program.cs` : cas `gabarit-real-app-e2e`
(fonction `GabaritRealAppEndToEnd`, même méthode que `via-real-app-e2e` /
`layer-real-app-e2e`) — pose une VRAIE Diode + un VRAI Condensateur + un
VRAI GND depuis `ItemLibList`, dans une disposition volontairement dispersée
(sans rapport avec le gabarit `Détecteur de crête`), câble avec de VRAIS
`DwLine`/`AddPtoLine`/`EndLine`, sauvegarde par le VRAI `SnapshotBoard`.

**BUG TROUVÉ EN TESTANT ce chemin réel (jamais atteint par les tests
synthétiques)** : `bin\Debug\LibItem\Lib\Diode.xml` portait `Pnumber`
inversé par rapport à `Pname` (cathode `Pnumber="1"`, anode `Pnumber="2"`)
alors que `circuit_analyzer/xml.py::lire_xml` privilégie `Pnumber` sur
`Pname` et que sa table d'alias suppose `Pnumber "1"=anode/"2"=cathode`
(convention respectée par `Diode Schottky.xml`, `Diode Zener.xml`,
`LED.xml`, `Photodiode.xml` — `Diode.xml` était seul à l'inverse). La
polarité était donc lue à l'envers pour toute VRAIE diode posée depuis la
bibliothèque partagée, empêchant la détection de « Détecteur de crête »
(et, par le même mécanisme, de tout autre montage ancré sur une diode réelle
— roue libre, ESD, redresseur simple). Sans rapport avec le moteur de
gabarit lui-même : un bug de lecture de bibliothèque, situé une couche en
dessous, jamais exercé par les fixtures synthétiques de la suite pytest.
Corrigé dans le fichier de bibliothèque (permutation des deux `<Pnumber>`
uniquement — géométrie, `Pname`, index de broche inchangés ; voir
`JOURNAL_MODIFICATIONS.md` §31 pour le détail complet).

Après correctif, round-trip complet vérifié :
- Détection Python réelle : `Détecteur de crête` reconnu (`['D1', 'C1']`).
- `eretro_patch.ecrire_groupes` (mécanisme réel d'export) réécrit D1/C1 à
  l'offset EXACT du gabarit de référence — delta (320, 0) entre Diode et
  Condensateur, identique dans `patterns_reference/Détecteur de crête.xml`
  (D1 à (250,250), CCH à (570,250)) et dans le fichier patché réel (D1 à
  (1190,1000), C1 à (1510,1000)) — alors que les positions de départ dans
  l'appli étaient (300,200) et (2400,1800), sans aucun rapport géométrique.
  GND, hors du montage détecté, reste intact à sa position d'origine.
- Fichier patché rechargé dans un VRAI `Form1` (`SizeTraceHarness
  real-schema`) : chargement sans exception, 4/4 bouts de fil accrochés à
  leur broche à la nouvelle position, aucun fil ne traverse un composant.

Le round-trip C# (pose + câblage réels) → Python (détection + disposition
canonique) → C# (rechargement) est donc intact de bout en bout, sur un
montage qui n'avait encore jamais été exercé par la VRAIE bibliothèque.
