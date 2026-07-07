# Îlots — tiercé affichage : Ajuster, terminaisons, hiérarchie — Spec + Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal :** trois améliorations d'affichage de la fenêtre « Schéma îlot », validées
utilisateur (2026-07-07) : bouton « Ajuster à la fenêtre », terminaisons de stubs
explicites (nom du net au lieu d'un point flottant), hiérarchie visuelle
montage principal vs satellites.

## Global Constraints

- Canvas de schéma CLAIR (#fafafa) ; chrome via ui_kit/theme uniquement.
- Aucune régression : positions des symboles inchangées sauf mention explicite ;
  comportements toggle/zoom/clic/export inchangés.
- Le test propriété (tests/test_labels_property.py : zéro chevauchement, zéro
  clipping, tous circuits × 2 modes) reste VERT — c'est le filet.
- `python -m pytest -q` vert à chaque tâche (717+1skip + nouveaux) ; commit par
  tâche, message français, JAMAIS de footer Co-Authored-By/Generated.
- Vérification par captures de la VRAIE fenêtre (win_sweep) en plus des PNG.

---

### Task 1 : Bouton « Ajuster à la fenêtre »

**Files:** Modify `gui/circuit_viewer.py` (show_island), test dans
`tests/test_island_viewport.py`.

- Bouton `ui_kit.GhostButton(icon_name="maximize")` (icône déjà dans les assets)
  dans la barre basse, à gauche du groupe − / 100 % / +.
- Action : calcule le facteur pour que la figure ENTIÈRE tienne dans le viewport
  courant : `f = min(vw/wpx, vh/hpx)` où (vw, vh) = taille utile de
  `canvas_frame` (winfo_width/height − padding) et (wpx, hpx) =
  `_figure_pixel_size` de la figure au facteur 1.0 (reconstruire via
  `construire_fig` ou mémoriser base_w/h). Borné à [0.15, 3.0] (le zoom manuel
  −/+ garde ses bornes 0.5–3.0 et repart du facteur posé par Ajuster).
- Pose `zoom["facteur"] = f` puis `_rendre()` — réutilise le chemin existant
  (centrage < 1× déjà géré). Mode détaillé/Z conservé.
- Test : sur une chaîne large (ilot_tous_aop), après Ajuster la figure tient
  dans le viewport (wpx ≤ vw et hpx ≤ vh) et le facteur est < 1 ; sur un îlot
  compact, Ajuster ne dépasse jamais 3.0 et le résultat tient aussi.
- Vérif fenêtre : capture avant/après Ajuster sur ilot_tous_aop (chaîne 7 AOP)
  et ilot_reel_darlington_relais_rlc.

### Task 2 : Terminaisons de stubs explicites

**Files:** Modify `gui/circuit_viewer.py` (`_dessiner_z_locale`,
`_dessiner_impedances_locales`, et le chemin détaillé correspondant), tests.

- Tout stub d'impédance locale (couplage/charge/entrée dessiné depuis un nœud
  de montage vers un autre net) qui se termine aujourd'hui par un Dot « nu »
  affiche à la place : le NOM DU NET réel de destination (`other_net`), style
  net (`_BUS`, fontsize 9), avec un petit dot ouvert (`elm.Dot(open=True)`).
  Rails : GND → symbole masse (déjà le cas), net d'alim → nom du rail (déjà
  souvent le cas) — la tâche cible les nets SIGNAL anonymes.
- Vues Z ET détaillée (le stub déplié se termine pareil).
- Le moteur `ajuster_labels` gère les collisions éventuelles des nouveaux
  labels (filet) ; s'assurer que le test propriété reste vert.
- Test : sur ilot_reel_ce_suiveur_sortie_rlc (stub C1+R1 sous VIN) et
  ilot_reel_ampli_audio_3etages, les figures contiennent le nom du net de
  destination du stub ; plus aucun Dot plein « nu » en bout de stub (assert sur
  les texts + inspection ciblée).
- Vérif fenêtre : captures des deux circuits, deux modes.

### Task 3 : Hiérarchie visuelle montage / satellites

**Files:** Modify `gui/circuit_viewer.py` (fils des stubs locaux), tests.

- Les FILS des réseaux d'impédance locaux (stubs satellites/couplages hors
  chemin principal du montage) passent de l'encre principale `_WIRE` au gris
  net `_BUS` (#475569) — le chemin principal du montage (transistor/AOP,
  entrée→sortie, rails du montage) reste en `_WIRE` plein. Les symboles gardent
  leurs couleurs sémantiques (R bleu, C cyan, L vert, Z bleu cliquable).
- Périmètre STRICT : seuls les fils tracés par le chemin des impédances
  locales/stubs ; ne pas toucher aux fils des drawers ni aux chaînes.
- Test : sur un îlot avec stub (ce_suiveur), au moins un segment de fil du stub
  est en `_BUS` et le fil principal reste `_WIRE` (inspection des Line2D par
  couleur).
- Vérif fenêtre : capture darlington + suiveur, deux modes — l'œil doit aller
  au montage, les stubs en retrait mais lisibles.

### FINALISATION
- Suite complète verte ; win_sweep complet re-capturé et inspecté (contrôleur) ;
  rebuild exe + smoke.

## Auto-revue
- Couverture : 3 demandes utilisateur = 3 tâches. ✔
- Interfaces : Task 1 réutilise `zoom`/`_rendre`/`_figure_pixel_size` existants ;
  Tasks 2-3 touchent le même chemin stub (séquencer 2 puis 3 pour éviter les
  conflits). Pas de nouveau module. ✔
- Placeholders : aucun ; valeurs exactes (bornes, couleurs, icône) fournies. ✔
