# Sous-projet C — Vue îlot multi-transistors (chaîne câblée)

**Date :** 2026-06-26
**Statut :** approuvé

## Problème

Quand un îlot contient **plusieurs montages transistor** (ex. deux étages
émetteur commun cascadés, AC-couplés), la vue îlot retombe sur la grille
générique : transistors en carrés Q1/Q2, résistances en boîtes Z. C'est
précisément la vue que le boss refuse (cf. [[feedback_jamais_vue_generique]]).

Cause : le moteur de chaîne (`_ordonner_montages_flux`, `_layers_montages_flux`,
`_dessiner_montage_a`) est codé en dur pour l'AOP et casse pour les transistors
sur trois points :
1. **OUT net = `nodes[-1]`** : valable pour l'AOP, mais l'émetteur commun a
   `nodes = [base, collecteur, émetteur]` → lit GND comme sortie au lieu du
   collecteur.
2. **Vue branchée filtrée à `"(AOP)"`** : les transistors sont exclus.
3. **Liaison par égalité de net** : les étages AOP se touchent directement, mais
   les étages transistor sont **AC-couplés** (un `Cc` entre collecteur et base
   crée deux nets distincts) → la chaîne ne relie jamais les étages.

## Objectif

Rendre le moteur de chaîne **agnostique au type de montage** : une cascade de
montages transistor s'affiche comme une chaîne câblée gauche→droite, chaque
étage dessiné en entier (transistor + Rb + Rc + VCC/GND), reliés OUT→(Cc)→IN.
Les vues AOP existantes restent strictement identiques (zéro régression).

## Portée
- **Dans le périmètre :** rendu de la chaîne / DAG branché pour des étages
  transistor (et îlots mixtes AOP + transistor).
- **Hors périmètre :** la détection (inchangée — chaque étage doit être détecté
  indépendamment, p. ex. cascades AC-couplées avec polarisation propre) ; le
  point de fonctionnement ; de nouveaux types de montage.

## Composants

### Brique 1 — Nets d'E/S conscients du type
Helper `_io_montage(match, ci) -> (in_nets: list[str], out_net: str | None)` :
- **AOP** : délègue à la logique actuelle (`_in_nets(match)`, `nodes[-1]`).
  Valeurs identiques → comportement AOP inchangé.
- **Transistor** : résout via les broches du/des transistor(s) du match :
  - émetteur commun / commutation : IN = net de base, OUT = net de collecteur ;
  - suiveur d'émetteur / push-pull : IN = base, OUT = émetteur ;
  - Darlington : IN = base(Q1), OUT = émetteur(Q2) (Q1 = base pilotée de
    l'extérieur ; Q2 = émetteur de sortie).
- Types non chaînables (miroir de courant, commande relais, MOSFET de
  puissance) : `out_net = None` → terminaux (dessinés, jamais reliés en aval).

### Brique 2 — Traversée des couplages
Les Impédances Z à 2 nœuds présentes dans l'îlot sont des **couplages**
(condensateur de liaison, R série). On construit une union-find sur les nets
qu'elles relient, puis on relie étage *i* → *j* quand `find(out_net_i)` rejoint
un `find(in_net_j)`. Conséquences :
- ces Impédances Z sont **retirées de la liste des étages** (ce ne sont pas des
  montages) et **réutilisées comme liens**, dessinées sur le fil inter-étage ;
- rétro-compatible : un îlot AOP sans couplage n'obtient aucun lien parasite
  (la traversée n'ajoute que des liens devant exister).

### Brique 3 — Dessin d'étage polymorphe
`_dessiner_montage_a` route les types transistor vers les drawers transistor,
rendus **paramétriques en origine** et **renvoyant leurs ancres** `{"in","out"}`
(et `"ins"`/`"in_pts"` pour le branché). Refactor rétro-compatible : `_make_fig`
conserve l'appel actuel via une origine par défaut et ignore la valeur de retour.
Un seul code de dessin par montage, partagé vue isolée ↔ vue chaîne.

### Brique 4 — Mise en page
- `_oy_for` étendu : aligne la sortie des étages transistor sur la ligne de base.
- Pas horizontal (`_CHAINE_DX`) ajusté (un étage transistor est plus large :
  rail VCC + Rc au-dessus).
- Titre de rôle par étage via `_titre_etage`, sans doublon.
- `_layers_montages_flux` et `_branched_edges` : le filtre `"(AOP)"` devient
  « est un étage montage » et passe par les briques 1 & 2 → vue branchée
  polymorphe.

## Flux de données
`analyser()` → matches de l'îlot → séparation **étages** (montages à drawer) /
**couplages** (Impédance Z 2 nœuds) → ordonnancement via `_io_montage` +
union-find couplage → `_draw_island_chain` (ou branché) dessine chaque étage avec
son drawer et tire les fils OUT → (Cc) → IN.

## Tests
- Unitaire : `_io_montage` rend (base, collecteur) pour CE, (base, émetteur)
  pour suiveur ; AOP inchangé (même in_nets / out_net qu'aujourd'hui).
- Unitaire : la traversée de couplage relie deux CE séparés par un `Cc`.
- Intégration : 2 CE cascadés (AC-couplés) → `_ordonner_montages_flux` rend la
  chaîne ordonnée [Q1, Q2] ; la figure contient ≥ 2 symboles transistor,
  **aucun** Opamp, pas de « Schéma non disponible ».
- Régression : chaînes/DAG AOP existants (chaine_5_aop, pid) inchangés.
- Visuel : PNG de l'îlot 2-CE rendu et inspecté.

## Critère de réussite
- Un îlot de N étages transistor cascadés s'affiche en chaîne câblée, chaque
  étage en schéma complet, reliés par leur couplage — plus de grille générique
  ni de symboles AOP.
- Les vues AOP existantes sont strictement identiques.
- Suite de tests verte ; PNG vérifié.
