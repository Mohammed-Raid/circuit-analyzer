# Îlots — pipeline de rendu rigoureux (labels, viewport, cycle de vie) — Design

**But :** remplacer les garanties « cas par cas » de la vue îlot par trois garanties
systémiques : (1) zéro chevauchement de texte prouvé par les métriques réelles du
renderer, (2) comportement zoom/viewport exact (centrage < 1×, scrollregion
exacte > 1×, états zoom↔mode indépendants), (3) démontage déterministe des
contextes de rendu (zéro fuite mesurable).

**Fichiers :** `gui/circuit_viewer.py`, `gui/impedance_schematic.py`,
nouveau `gui/schema_labels.py` (moteur anti-collision, sans cycle d'import).

## 1. Moteur anti-collision de labels (`gui/schema_labels.py`)

`ajuster_labels(fig)` — passe de résolution appliquée par TOUTES les fabriques de
figures (les 4 `_make_*fig`, `_dessiner_impl`, `dessiner_pont`) juste avant le
retour :

- Un rendu Agg unique fournit le renderer ; chaque `Text` expose son
  `get_window_extent(renderer)` (métriques réelles, pas d'approximation).
- Obstacles : bboxes des autres textes + segments des `Line2D` (fils/symboles),
  convertis en coordonnées display.
- Résolution DÉTERMINISTE : textes triés par (x arrondi, y arrondi, contenu) ;
  itérations bornées (≤ 20) ; à chaque chevauchement, le texte de moindre
  priorité (labels composants < noms de nets < titres, qui ne bougent jamais)
  est poussé le long de son axe d'échappement (perpendiculaire à son symbole
  d'ancrage, sinon axe du plus petit recouvrement) du recouvrement + marge
  (`_Z_LABEL_CLEAR` converti en pixels via la figure).
- Après résolution : les limites d'axe sont ré-étendues pour contenir toutes
  les bboxes de texte (aucun label clippé, quel que soit le zoom).
- Les offsets constants existants restent le PLACEMENT INITIAL (déterminisme
  visuel) ; le moteur est le filet de sécurité mathématique.

**Règle ref/valeur (décision d'architecte) :** la règle « ref à +Y / valeur à −Y
(horizontal), ref à −X / valeur à +X (vertical) » est appliquée aux FEUILLES des
réseaux dépliés (`_z_reseau`, `_dessiner_impl`, `_bras_detaille`) : deux `Text`
distincts de part et d'autre du symbole — c'est là que la densité la justifie
(convention EDA type KiCad). Les labels satellites mono-chaîne des drawers
(« Rc = 2.2 kΩ ») restent une seule chaîne : le boss a validé ces visuels et le
moteur garantit déjà leur non-chevauchement. Écart au brief assumé et documenté.

**Test propriété (le contrat) :** pour TOUS les circuits du sweep
(ilot_*, tr_*, échantillon aop_*) × les DEUX modes : aucun couple de textes dont
les bboxes renderer se recouvrent (tolérance 1 px) ; aucun texte hors des
limites d'axe finales. Ce test global remplace les gardes ponctuelles à venir
(les gardes existantes restent).

## 2. Viewport zoom exact (`show_island`)

- États `mode`/`zoom` déjà croisés-persistants : ajouter le test unitaire qui le
  verrouille (toggle ne touche pas `zoom["facteur"]`, zoom ne touche pas
  `mode["detaille"]`).
- **< 1.0×** : chemin non défilant ; centrage EXPLICITE (`ax.set_anchor("C")` +
  empaquetage centré) — le réseau réduit est parfaitement centré dans le
  viewport, bords jamais clippés (les limites incluent les textes, cf. §1).
- **> 1.0×** : chemin défilant ; la `scrollregion` du canvas Tk est recalculée
  depuis la taille pixel native de la figure APRÈS application du facteur
  (`_figure_pixel_size`), scrollbars mappées exactement sur les bornes du
  schéma, labels de bord inclus (limites §1). Vérif : à 2×, `xview_moveto(1)` /
  `yview_moveto(1)` montrent le coin du schéma entier, rien de coupé.
- **DPI :** stratégie constante-DPI + `set_size_inches` (re-rendu vectoriel
  natif à chaque facteur — équivalent au réglage DPI, sans invalider
  `_figure_pixel_size`). Documenté dans le code.

## 3. Démontage déterministe (zéro fuite)

- `monter_canvas` enregistre le contexte courant (`etat["canvas"]`,
  `etat["cids"]`) ; toute reconstruction (toggle, zoom, re-rendu) exécute
  d'abord : `mpl_disconnect` de tous les cids (clic + curseur), destruction du
  widget Tk, `ancienne_fig.clf()`, purge des références (`etat` réécrit).
  `_suivre_curseur_z` retourne désormais son cid.
- **Pourquoi pas `plt.close()` :** les figures sont créées via
  `matplotlib.figure.Figure()` directement — jamais enregistrées dans le
  registre pyplot ; l'équivalent déterministe est disconnect + destroy + clf.
  Commentaire dans le code.
- **Test de fuite (le contrat) :** sur un vrai root Tk (skip si headless),
  ouvrir la fenêtre îlot, exécuter ≥ 8 cycles toggle/zoom en gardant un
  `weakref` sur chaque figure remplacée ; après `gc.collect()`, TOUTES les
  weakrefs sont mortes. Croissance mémoire bornée, prouvée.

## Hors périmètre (YAGNI, assumé)

Pas de re-layout des drawers ni des réseaux (positions des symboles inchangées) ;
pas de moteur de placement global type force-directed (le placement initial
reste par règles, le moteur ne fait que résoudre) ; pas de changement du style
des labels satellites validé par le boss ; pas de virtualisation du canvas.

## Vérification

- `python -m pytest -q` vert (623 + nouveaux : propriété labels, persistance
  états, fuite, scrollregion).
- Sweep FENÊTRE (win_sweep) : 11 circuits × 2 modes + captures à 0.64× et 2×
  sur 3 circuits — centrage, scroll exact, zéro texte coupé/chevauché.
- Rebuild exe + smoke.
