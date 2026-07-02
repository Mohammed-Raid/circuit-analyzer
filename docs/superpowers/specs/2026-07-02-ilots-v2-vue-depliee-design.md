# Îlots v2 — vue dépliée R/L/C + polissage — Design

**But :** dans la fenêtre « Schéma îlot », (a) un bouton bascule affichant le même
schéma avec les composants R/L/C réels à la place des boîtes Z simplifiées,
(b) un polissage global de l'affichage (chrome fenêtre, lisibilité du dessin,
espacement, taille/zoom) — **en gardant la structure des schémas**.

**Décisions verrouillées (brainstorming 2026-07-02) :**
- Bascule **dans la même fenêtre** (toggle, un seul schéma visible à la fois).
- Périmètre polissage : chrome popup + lisibilité dessin + espacement/collisions
  + taille/zoom (les 4 axes validés).
- Structure des drawers inchangée : mêmes ancres, mêmes fils, même topologie.

## 1. Bouton bascule « Vue détaillée R/L/C »

- Barre du bas de `show_island` : bouton toggle « Vue détaillée R/L/C » ↔
  « Vue simplifiée Z » (`ui_kit.SecondaryButton`, icône `layers`). Le clic
  reconstruit la figure et remplace le canvas en place (scroll conservé).
- `show_island` : la chaîne if/elif de choix de rendu devient une fonction
  locale `construire_fig(detaille: bool)` réutilisée par le toggle.
- **Mécanique d'expansion** — point de passage unique `_z_box(d, p1, p2, …)`
  (gui/circuit_viewer.py) consulte un drapeau `d._mode_detaille` (posé par les
  fabriques de figures `_make_fig`/`_make_chain_fig`/`_make_branched_fig`/
  `_make_island_fig` via un paramètre `detaille=False`) :
  - détaillé : `impedance.arbre_expr(composition)` → arbre série/parallèle →
    `impedance_schematic.agencer(arbre)` → symboles réels R/C/L (réf + valeur
    formatée, couleurs `_COMP_COLORS`) dessinés **entre p1 et p2** : mise à
    l'échelle uniforme (largeur réseau → longueur du segment), rotation selon
    l'orientation du segment, branches parallèles empilées perpendiculairement.
  - bloc à 1 seul composant → symbole réel direct (pas de réseau).
  - composition non série/parallèle (`arbre_expr` → None, pont Y-Δ) → la boîte Z
    reste dessinée (fallback honnête).
  - Helper dédié : `_z_reseau(d, p1, p2, bloc, ci)` dans circuit_viewer.py.
- Îlots rendus par `impedance_schematic` : `dessiner_bloc(..., detaille=False)`
  et `dessiner_pont(..., detaille=False)` — en mode détaillé, groupes vides =
  tout déplié (mécanisme `_dessiner_impl(..., groupes={})` existant) ; pour le
  pont, chaque bras série/parallèle est déplié via la même expansion, un bras
  non-réductible reste en Z.
- Vue détaillée : pas de hitboxes Z (tout est visible) ; vue Z : comportement
  clic/drill-down actuel strictement inchangé.

## 2. Chrome de la fenêtre (design kit)

`show_island` ET `show_dipole_detail` : header, chips composants, barre basse
migrés sur `ui_kit`/`theme` (Inter via `ui_kit.font`, tokens — plus de
« Segoe UI »/hex en dur dans le chrome). Boutons : Exporter PNG =
`SecondaryButton(icon "download")`, Fermer = `GhostButton`, toggle = cf. §1.
Le canvas de schéma reste CLAIR (#fafafa) — directive boss inchangée.

## 3. Lisibilité + espacement (structure conservée)

Passe centralisée sur le rendu schemdraw de circuit_viewer/impedance_schematic :
- tailles de police cohérentes (labels composants, labels Z, titres, astuce) ;
- épaisseur de trait homogène ; taille des symboles inchangée ;
- dégagement des labels Z (`_Z_LABEL_CLEAR`) et marges revus ;
- corrections ciblées de collisions révélées par la boucle de rendu (pas de
  re-layout : ajustements de labels/marges uniquement).

## 4. Taille / zoom dans la fenêtre

- Ajustement auto amélioré : la figure remplit la fenêtre sans être écrasée
  (borne min de lisibilité conservée, scroll natif au-delà).
- Boutons « − / 100 % / + » dans la barre basse : re-rendu de la figure à
  l'échelle (facteur sur `set_size_inches`), le viewport scrollable absorbe
  le dépassement.

## 5. Vérification

- Suite existante verte (591) — les tests structure/hitbox ne changent pas.
- Nouveaux tests ciblés : expansion série/parallèle (`_z_reseau` : positions/
  nombre de symboles pour « R1+R2 » et « R1//C1 »), fallback pont (Z conservée),
  `construire_fig(detaille=True)` produit une figure sans hitboxes Z,
  `dessiner_bloc(detaille=True)` détaille tout.
- **Boucle visuelle** : les ~60 îlots de circuits_industriels rendus dans les
  DEUX modes → PNG inspectés (focus transistors), aucun chevauchement, canvas
  clair intact.

## Hors périmètre (YAGNI)

Pas de re-layout des drawers, pas de mode d'édition, pas de dépliage des ponts
Y-Δ non série/parallèle, pas de persistance du mode entre fenêtres.
