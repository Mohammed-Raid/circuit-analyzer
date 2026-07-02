# Îlots v2 — vue dépliée R/L/C + polissage — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** bouton bascule « Vue détaillée R/L/C » dans la fenêtre îlot (mêmes schémas, composants réels à la place des boîtes Z) + polissage de l'affichage (chrome, lisibilité, espacement, zoom) sans changer la structure des schémas.

**Architecture:** l'expansion passe par le point unique `_z_box()` (drapeau `d._mode_detaille`), la mise en page réutilise `impedance.arbre_expr` + `impedance_schematic.agencer` transformés sur le segment p1→p2. `show_island` encapsule son choix de rendu dans `construire_fig(detaille)` que le toggle rappelle.

**Tech Stack:** Python, CustomTkinter (chrome via gui/ui_kit + gui/theme), schemdraw/matplotlib (rendu), pytest.

## Global Constraints

- Le canvas des schémas reste CLAIR (`SCH_BG #fafafa`) ; aucun token de surface sombre dans le dessin.
- Structure des drawers INCHANGÉE : mêmes ancres, mêmes fils, même topologie ; seuls le contenu entre les bornes des Z, les labels/marges et le chrome changent.
- En vue Z (défaut), le comportement actuel (clic → `show_dipole_detail`, hitboxes, curseur) est strictement inchangé.
- Chrome fenêtre : uniquement `ui_kit`/`theme` (pas de « Segoe UI »/hex en dur) ; boutons presets.
- `python -m pytest -q` vert à chaque tâche (591+ ; tolérer 1-2 skip Tk flaky) ; commit par tâche, message français, **jamais** de footer Co-Authored-By/Generated.
- Mode lazy/minimal : pas d'abstraction non demandée.

---

### Task 1 : Agencement d'un réseau entre deux points (cœur, pur)

**Files:**
- Modify: `gui/circuit_viewer.py` (nouvelles fonctions module, près de `_z_box`)
- Test: `tests/test_z_reseau.py` (nouveau)

**Interfaces:**
- Produces: `_agencement_entre(p1: tuple, p2: tuple, arbre) -> tuple[list, list]` — PURE :
  prend l'arbre série/parallèle (`impedance.arbre_expr`) et retourne
  `(symboles, fils)` en coordonnées GLOBALES : `symboles = [(ref, (xa,ya), (xb,yb))]`,
  `fils = [((xa,ya),(xb,yb))]`. Mise en œuvre : `impedance_schematic.agencer(arbre)`
  donne symboles/fils/dims en coordonnées locales (borne gauche `(0, dims.y_borne)`,
  droite `(dims.largeur, dims.y_borne)`) ; transformation = translation p1 +
  rotation `atan2(p2-p1)` + échelle uniforme `dist(p1,p2)/dims.largeur`
  (le perpendiculaire utilise `(y_local - dims.y_borne) * échelle`).
- Produces: `_z_reseau(d, p1, p2, bloc, ci) -> bool` — dessine le réseau réel :
  `arbre_expr(bloc["composition"])` ; si None → return False (l'appelant garde la Z).
  Sinon dessine chaque symbole avec le type réel (`elm.Resistor`/`elm.Capacitor`/
  `elm.Inductor2`, défaut `elm.ResistorIEC`), couleur `_COMP_COLORS.get(type, _WIRE)`,
  label `ref` + `impedance.formater_valeur(value, type)` (fontsize 9), chaque fil en
  `elm.Line().color(_WIRE)` ; return True.

- [ ] **Step 1 : tests qui échouent** — dans `tests/test_z_reseau.py` :

```python
"""Expansion d'une composition Z en réseau R/L/C entre deux points (vue détaillée)."""
import math
from circuit_analyzer.impedance import arbre_expr
from gui.circuit_viewer import _agencement_entre


def _pres(a, b, tol=1e-6):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def test_serie_horizontale_reste_sur_l_axe():
    arbre = arbre_expr("(R1)+(R2)")
    symboles, fils = _agencement_entre((0.0, 0.0), (6.0, 0.0), arbre)
    assert [s[0] for s in symboles] == ["R1", "R2"]
    for _ref, pa, pb in symboles:          # tout sur l'axe y=0
        assert abs(pa[1]) < 1e-6 and abs(pb[1]) < 1e-6
    assert symboles[0][1][0] < symboles[0][2][0] <= symboles[1][1][0]


def test_parallele_branches_de_part_et_d_autre():
    arbre = arbre_expr("(R1)//(C1)")
    symboles, fils = _agencement_entre((0.0, 0.0), (6.0, 0.0), arbre)
    ys = sorted(s[1][1] for s in symboles)
    assert len(symboles) == 2 and ys[0] < ys[1]      # branches empilées
    assert fils, "rails et connecteurs attendus"


def test_segment_vertical_pivote():
    arbre = arbre_expr("(R1)+(R2)")
    symboles, _ = _agencement_entre((0.0, 0.0), (0.0, -6.0), arbre)
    for _ref, pa, pb in symboles:          # tout sur l'axe x=0, y décroissant
        assert abs(pa[0]) < 1e-6 and abs(pb[0]) < 1e-6
    assert symboles[0][1][1] > symboles[1][1][1]


def test_composition_pont_non_depliable():
    assert arbre_expr("(R1)*(R2)/((R1)+(R2)+(R3))") is None
```

- [ ] **Step 2 :** `python -m pytest tests/test_z_reseau.py -q` → FAIL (`_agencement_entre` inexistant).
- [ ] **Step 3 :** implémenter `_agencement_entre` + `_z_reseau` dans `gui/circuit_viewer.py` (import module-level `math` déjà présent ? sinon l'ajouter ; imports lazy de `impedance_schematic`/`impedance` DANS les fonctions, comme le fait déjà `show_island`).
- [ ] **Step 4 :** tests verts + `python -m pytest -q` complet vert.
- [ ] **Step 5 :** commit `feat(ilots): agencement d'un reseau R/L/C entre deux points`.

---

### Task 2 : Mode détaillé de bout en bout + toggle dans la fenêtre îlot

**Files:**
- Modify: `gui/circuit_viewer.py` (`_z_box`, `_enregistrer_hitbox`, `_make_fig`, `_make_chain_fig`, `_make_branched_fig`, `_make_island_fig`, `show_island`)
- Test: `tests/test_z_reseau.py` (compléter)

**Interfaces:**
- Consumes: `_z_reseau` (Task 1).
- Produces: paramètre `detaille: bool = False` sur les 4 fabriques `_make_*fig` ;
  elles posent `d._mode_detaille = detaille` sur le Drawing avant d'appeler le drawer.
- `_z_box` : si `getattr(d, "_mode_detaille", False)` — bloc à 1 réf → dessine le
  symbole réel (type/couleur/label comme `_z_reseau`) ; sinon tente `_z_reseau` ;
  si False (pont) → boîte Z classique. En mode détaillé, `_enregistrer_hitbox`
  ne fait rien (`d._mode_detaille` → return) : plus de zones cliquables.
- `show_island` : la chaîne if/elif actuelle devient `construire_fig(detaille: bool)`
  (les stratégies `impedance_schematic` reçoivent le flag en Task 3 ; d'ici là le
  flag ne s'applique qu'aux chemins `_make_*fig`). Le popup garde l'état
  `mode = {"detaille": False}` ; un bouton toggle dans la barre basse reconstruit
  la figure, détruit l'ancien canvas (`canvas.get_tk_widget().destroy()` ou le
  viewport scrollable) et remonte le nouveau via le même code d'empaquetage
  (extraire l'empaquetage actuel — scrollable ou plein cadre — en fonction locale
  `monter_canvas(fig)` réutilisée). Reconnecter `_on_click`/`_suivre_curseur_z`
  sur le nouveau canvas ; libellé du bouton mis à jour
  (« Vue détaillée R/L/C » ↔ « Vue simplifiée Z »).

- [ ] **Step 1 : test qui échoue** — ajouter à `tests/test_z_reseau.py` :

```python
def test_make_fig_detaille_sans_hitboxes():
    import gui.circuit_viewer as cv
    match = {"circuit_type": "Impédance Z", "components": ["R1", "R2"],
             "nodes": ["A", "B"],
             "impedances": {"Z": {"refs": ["R1", "R2"],
                                   "composition": "(R1)+(R2)",
                                   "nodes": ["A", "B"]}}}
    ci = {"R1": {"type": "R", "value": "10k"}, "R2": {"type": "R", "value": "4.7k"}}
    fig_z = cv._make_fig(match, ci, cv._DRAWERS["Impédance Z"])
    fig_d = cv._make_fig(match, ci, cv._DRAWERS["Impédance Z"], detaille=True)
    assert fig_z._z_hitboxes, "vue Z : la boîte reste cliquable"
    assert fig_d._z_hitboxes == [], "vue détaillée : aucune hitbox"
```

  (Adapter la forme exacte du `match` à ce que `_draw_impedance` consomme —
  lire le drawer d'abord ; l'assertion clé est hitboxes non vides vs vides.)
- [ ] **Step 2 :** FAIL (`detaille` inconnu).
- [ ] **Step 3 :** implémenter (fabriques + `_z_box` + `_enregistrer_hitbox` + refactor `show_island` avec `construire_fig`/`monter_canvas`/toggle). Le bouton toggle utilise un widget provisoire `ctk.CTkButton` stylé comme les voisins (le passage complet au kit est Task 4).
- [ ] **Step 4 :** suite complète verte ; lancer `python app.py` 5 s (zéro traceback).
- [ ] **Step 5 :** commit `feat(ilots): bascule vue detaillee R/L/C dans la fenetre ilot`.

---

### Task 3 : Mode détaillé des rendus impedance_schematic (bloc 2 bornes, pont)

**Files:**
- Modify: `gui/impedance_schematic.py` (`dessiner_bloc`, `dessiner_pont`), `gui/circuit_viewer.py` (`construire_fig` passe le flag)
- Test: `tests/test_z_reseau.py` (compléter)

**Interfaces:**
- Produces: `dessiner_bloc(arbre, a, b, comps, detaille=False)` — si `detaille`,
  rend TOUT le réseau réel : `_dessiner_impl(arbre, a, b, comps, {})` (groupes
  vides = mécanisme existant), hitboxes vides.
- Produces: `dessiner_pont(pont, comps, titre=None, detaille=False)` — si
  `detaille`, chaque bras dont `arbre_expr(composition)` est série/parallèle est
  déplié entre ses deux sommets (réutiliser `_agencement_entre` importé de
  `gui.circuit_viewer` OU dupliquer la transformation locale si l'import croisé
  gêne — préférer l'import, il est sans cycle car lazy) ; bras non réductible →
  boîte Z conservée ; hitboxes vides en mode détaillé.
- `construire_fig` (show_island) transmet `detaille` aux appels
  `dessiner_bloc`/`dessiner_pont`.

- [ ] **Step 1 : tests qui échouent** :

```python
def test_dessiner_bloc_detaille_tout():
    from circuit_analyzer.impedance import arbre_expr
    from circuit_analyzer.composant import Composant
    from gui import impedance_schematic as isch
    comps = {"R1": Composant("R1", ["A", "M"], "10k"),
             "R2": Composant("R2", ["M", "B"], "4.7k")}
    arbre = arbre_expr("(R1)+(R2)")
    fig_z = isch.dessiner_bloc(arbre, "A", "B", comps)
    fig_d = isch.dessiner_bloc(arbre, "A", "B", comps, detaille=True)
    assert fig_z._z_hitboxes and fig_d._z_hitboxes == []
```

  (Vérifier la signature réelle de `Composant` avant d'écrire le test — adapter
  la construction des comps au constructeur réel.)
- [ ] **Step 2 :** FAIL. **Step 3 :** implémenter. **Step 4 :** suite verte.
- [ ] **Step 5 :** commit `feat(ilots): mode detaille des blocs et ponts impedance_schematic`.

---

### Task 4 : Chrome des fenêtres îlot et drill-down au design kit

**Files:**
- Modify: `gui/circuit_viewer.py` (`show_island`, `show_dipole_detail`, `_export`, `_pack_scrollable_figure` si besoin de couleurs)

**Interfaces:** Consumes `gui.ui_kit` (`font`, boutons presets, icônes `download`, `layers`, `x`) et `gui.theme` (tokens ; `UI_BG`/`UI_CARD` locaux remplacés par `theme.SURFACE`/`theme.OVERLAY`).

- [ ] **Step 1 :** migrer le chrome : header (`ui_kit.font("subtitle", "bold")`, `theme.TEXT`), gain (`Consolas` conservé pour la valeur — mono volontaire — couleur `theme.SUCCESS`), chips composants (fonds `_COMP_COLORS` conservés — sémantiques — police `ui_kit.font("caption")`), barre basse : Exporter PNG = `SecondaryButton(icon "download")`, toggle Task 2 = `SecondaryButton(icon "layers")`, Fermer = `GhostButton`. Idem `show_dipole_detail` (header + fermer). Aucun « Segoe UI »/hex de chrome restant dans ces deux fonctions (les couleurs sémantiques `_COMP_COLORS`/gain restent).
- [ ] **Step 2 :** suite verte ; lancement app 5 s sans traceback ; capture de la fenêtre îlot (script scratch : `show_island` sur `ilot_reel_darlington_relais_rlc.xml` + `ImageGrab`) inspectée.
- [ ] **Step 3 :** commit `feat(ilots): chrome des fenetres schema au design kit`.

---

### Task 5 : Taille/zoom — ajustement + boutons − / 100 % / +

**Files:**
- Modify: `gui/circuit_viewer.py` (`show_island` : état zoom + re-rendu ; `_pack_scrollable_figure` réutilisé)
- Test: `tests/test_z_reseau.py` (compléter si seam testable, sinon vérif visuelle)

**Interfaces:** état local `zoom = {"facteur": 1.0}` ; boutons « − » / « 100 % » / « + » (IconButton/GhostButton) dans la barre basse : facteur borné [0.5, 3.0] par pas ×1.25 ; le re-rendu applique `fig.set_size_inches(base_w*f, base_h*f)` sur une figure RECONSTRUITE (`construire_fig` mémorise `base_w/base_h` à la construction) puis remonte le canvas via `monter_canvas` ; au-delà de la taille du viewport le chemin scrollable existant prend le relais (forcer le chemin scrollable dès que `f > 1.0`).

- [ ] **Step 1 :** implémenter (réutiliser `construire_fig`/`monter_canvas` de Task 2 — le zoom et le toggle partagent le même chemin de reconstruction).
- [ ] **Step 2 :** suite verte ; vérif manuelle scriptée : capture à 100 % et à +2 crans, le schéma grossit et le scroll apparaît.
- [ ] **Step 3 :** commit `feat(ilots): zoom -/100%/+ dans la fenetre schema`.

---

### Task 6 : Passe lisibilité/espacement + boucle visuelle bimode

**Files:**
- Modify: `gui/circuit_viewer.py`, `gui/impedance_schematic.py` (réglages : fontsize labels/titres, `_Z_LABEL_CLEAR`, marges, lw)
- Scratch: script de rendu bimode (répertoire scratchpad) → `tools/_renders/ilots_v2/{z,detaille}/`

**Interfaces:** aucun nouveau symbole public — uniquement des constantes de réglage existantes et corrections locales de labels.

- [ ] **Step 1 :** script scratch : pour chaque `circuits_industriels/ilot_*.xml` ET un échantillon d'autres circuits (aop_*, tr_*), rendre la figure de `show_island` en modes Z et détaillé (appeler `construire_fig` extrait ou reproduire la chaîne comme `gen_ilots.py` de la Task 13 précédente) → PNG dans `tools/_renders/ilots_v2/`.
- [ ] **Step 2 :** inspecter TOUS les PNG transistors + un échantillon AOP dans les deux modes ; lister les défauts (collisions de labels, réseaux dépliés trop denses, titres).
- [ ] **Step 3 :** corriger par ajustements ciblés (labels/marges/fontsize/`_Z_LABEL_CLEAR`, étalement perpendiculaire de `_agencement_entre` si branches trop serrées) — PAS de re-layout. Re-rendre et re-inspecter jusqu'à propre.
- [ ] **Step 4 :** suite complète verte.
- [ ] **Step 5 :** commit `fix(ilots): passe lisibilite et espacement des schemas (bimode verifie)`.

---

## FINALISATION
- [ ] `python -m pytest -q` → tous verts.
- [ ] Sweep visuel contrôleur : fenêtre îlot réelle (chrome + toggle + zoom) capturée et inspectée.
- [ ] `python tools/build_exe.py` → smoke conforme (tuer les exes ouverts avant).
- [ ] Revue finale de branche.

## Auto-revue (writing-plans)
- **Couverture spec :** §1 bascule = Tasks 1-3 ; §2 chrome = Task 4 ; §3 lisibilité = Task 6 ; §4 zoom = Task 5 ; §5 vérification = tests par tâche + Task 6 + finalisation. ✔
- **Placeholders :** les deux tests « à adapter » (forme du match `_draw_impedance`, constructeur `Composant`) sont explicitement des vérifications à faire par l'implémenteur AVANT d'écrire le test — pas des TODO d'implémentation.
- **Cohérence des types :** `_agencement_entre(p1, p2, arbre) -> (symboles, fils)` (T1) consommé par `_z_reseau` (T1) et `dessiner_pont` (T3) ; `detaille: bool` uniforme sur `_make_*fig` (T2) et `dessiner_bloc/pont` (T3) ; `construire_fig`/`monter_canvas` (T2) réutilisés par le zoom (T5). ✔
