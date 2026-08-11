# Retrait onglet Circuits + aperçu schématique wizard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retirer l'onglet Circuits (redondant avec le wizard de création de
pattern déjà accessible depuis Analyser/Schéma), en remplaçant ses deux
capacités réelles perdues (suppression d'un circuit personnalisé, aperçu
visuel) par des équivalents ailleurs — jamais une liste texte.

**Architecture :** Trois changements indépendants, dans l'ordre où ils sont
livrés ici : (1) un aperçu schématique simple s'ajoute à l'étape 4 du
`PatternWizard`, (2) un bouton « Supprimer » s'ajoute à la popup de schéma
déjà existante (`circuit_viewer.show_circuit`) pour les circuits
personnalisés, (3) seulement une fois ces deux remplacements en place et
testés, l'onglet Circuits est retiré. Cet ordre garantit qu'aucune capacité
n'est perdue à un moment intermédiaire du chantier.

**Tech Stack :** Python 3.11, CustomTkinter, schemdraw==0.22 (épinglé),
matplotlib, pytest.

## Global Constraints

- Commits en **français**, jamais de footer `Co-Authored-By: Claude` ni
  `Generated with Claude Code`.
- **Jamais `git add -A`** : fichiers ajoutés un par un.
- **Ne jamais committer** `custom_circuits.json` ni `component_library.json`.
- `PYTHONUTF8=1` sur toutes les commandes pytest.
- Branche `rewrite-simple` ; rien n'est poussé sans accord explicite.
- **`gui/app_window.py` contient des modifications en cours de l'utilisateur,
  non liées à ce chantier (feature d'auto-analyse au démarrage,
  `initial_file`/`_auto_analyze`), déjà présentes sur le fichier AVANT de
  commencer et jamais committées.** Ce plan modifie ce fichier (Tâche 3), mais
  **`git add gui/app_window.py` est INTERDIT** pour cette tâche : utiliser
  `git add -p gui/app_window.py` et ne sélectionner QUE les hunks relatifs au
  retrait de l'onglet Circuits (import `TabCircuits`, son instanciation, les
  deux callbacks, l'entrée de nav). Ne jamais toucher aux lignes de
  `initial_file`/`_auto_analyze`/`self._tab_a` : elles ne font pas partie de
  ce chantier et appartiennent à l'utilisateur.
- Aucune fonctionnalité hors de ce périmètre (pas de nouvelle feature, pas de
  refonte non demandée). Périmètre exact défini dans
  `docs/superpowers/specs/2026-08-04-retrait-onglet-circuits-apercu-wizard-design.md`.

---

### Task 1 : Aperçu schématique à l'étape 4 du wizard

**Files:**
- Modify: `gui/pattern_wizard.py`
- Test: `tests/test_pattern_wizard.py` (nouveau — `PatternWizard` n'a
  actuellement aucune couverture de test)

**Interfaces:**
- Consumes : `gui.impedance_schematic.style_symbole(typ, value, ref) ->
  (cls, coul, ref_txt, valeur)` (déjà public, déjà utilisé par
  `circuit_viewer.py`).
- Produces : `PatternWizard._dessiner_apercu(self) ->
  matplotlib.figure.Figure` (nouvelle méthode, utilisée en interne par
  `_update_preview`).

- [ ] **Step 1 : écrire les tests qui échouent**

Créer `tests/test_pattern_wizard.py` :

```python
"""@file test_pattern_wizard.py
@brief PatternWizard : apercu schematique de l'etape 4, rejet des doublons
de nom (spec 2026-08-04). Tk -> skip sans display.
"""
import pytest

ctk = pytest.importorskip("customtkinter")


@pytest.fixture
def ctk_root():
    import tkinter as tk
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("pas d'affichage Tk disponible")
    root.withdraw()
    yield root
    root.destroy()


def _wizard(ctk_root, refs_info):
    """@brief Construit un PatternWizard avec des composants deja coches.

    @param refs_info dict {ref: {"type":..., "value":..., "pins": {...}}}
    """
    from gui.pattern_wizard import PatternWizard
    return PatternWizard(ctk_root, graph=None,
                         unclassified=list(refs_info), comp_info=refs_info)


def test_apercu_dessine_un_symbole_par_composant_selectionne(ctk_root):
    refs_info = {
        "R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N2"}},
        "C1": {"type": "C", "value": "100n", "pins": {"1": "N2", "2": "GND"}},
    }
    w = _wizard(ctk_root, refs_info)
    fig = w._dessiner_apercu()
    with_elements = [el for ax in fig.axes for el in ax.texts]
    textes = {t.get_text() for t in with_elements}
    assert "R1" in textes and "C1" in textes


def test_apercu_relie_deux_composants_qui_partagent_un_net(ctk_root):
    refs_info = {
        "R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N2"}},
        "C1": {"type": "C", "value": "100n", "pins": {"1": "N2", "2": "GND"}},
    }
    w = _wizard(ctk_root, refs_info)
    fig = w._dessiner_apercu()
    assert set(fig._apercu_connexions) == {("R1", "C1")}


def test_apercu_dessine_un_composant_isole_sans_fil(ctk_root):
    """Aucun net partage entre R1 et C1 -> composants dessines, aucun fil."""
    refs_info = {
        "R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N2"}},
        "C1": {"type": "C", "value": "100n", "pins": {"1": "N3", "2": "N4"}},
    }
    w = _wizard(ctk_root, refs_info)
    fig = w._dessiner_apercu()
    textes = {t.get_text() for ax in fig.axes for t in ax.texts}
    assert "R1" in textes and "C1" in textes
    assert fig._apercu_connexions == [], "aucun net partage : pas de fil attendu"


def test_apercu_sans_selection_ne_leve_pas(ctk_root):
    w = _wizard(ctk_root, {})
    fig = w._dessiner_apercu()
    assert fig is not None


def test_go_to_etape_4_affiche_l_apercu(ctk_root):
    """La navigation vers l'etape 4 declenche bien le rendu (pas seulement
    un appel manuel isole a _dessiner_apercu)."""
    refs_info = {"R1": {"type": "R", "value": "10k",
                        "pins": {"1": "N1", "2": "N2"}}}
    w = _wizard(ctk_root, refs_info)
    w._go_to(2)
    w._name_var.set("Mon pattern")
    w._go_to(4)
    assert w._apercu_canvas is not None


def test_doublon_de_nom_refuse_a_l_etape_2(ctk_root, monkeypatch, tmp_path):
    """Remplace test_doublon_pattern_refuse (testait TabCircuits, retire) :
    meme comportement reel, teste directement sur PatternWizard, le seul
    chemin de creation qui subsiste apres le retrait de l'onglet Circuits."""
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)
    loader.save_custom_circuits([{"name": "Mon montage", "components": ["R"],
                                  "conditions": []}])

    refs_info = {"R1": {"type": "R", "value": "10k",
                        "pins": {"1": "N1", "2": "N2"}}}
    w = _wizard(ctk_root, refs_info)
    w._go_to(2)
    w._name_var.set("Mon montage")
    assert w._validate_current() is False
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_pattern_wizard.py -q`
Attendu : `AttributeError: 'PatternWizard' object has no attribute
'_dessiner_apercu'` (et `_apercu_canvas` absent).

- [ ] **Step 3 : implémenter**

Dans `gui/pattern_wizard.py`, ajouter les imports en tête de fichier (après
les imports existants) :

```python
import schemdraw
import schemdraw.elements as elm
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from gui.impedance_schematic import style_symbole
```

Ajouter `self._apercu_canvas = None` dans `__init__`, juste après la ligne
`self._json_box    = None` (l. 118).

Ajouter la méthode `_dessiner_apercu`, après `_selected_conditions` (l. 645) :

```python
    def _dessiner_apercu(self) -> Figure:
        """@brief Apercu schematique simple des composants selectionnes.

        Rendu volontairement simple (spec 2026-08-04) : vrais symboles
        (style_symbole), alignes en ligne, fils droits entre composants
        partageant un net. Pas de gestion rails/branches/compaction — ce
        n'est pas le moteur ilots, une decision explicite du boss.

        @return matplotlib.figure.Figure prete a afficher dans un canvas Tk.
        """
        refs = self._selected_refs()
        fig = Figure(figsize=(6.5, 2.4))
        ax = fig.add_subplot(111)
        fig.patch.set_facecolor(_BG)
        ax.set_facecolor(_BG)
        ax.axis("off")
        ax.set_aspect("equal")
        # Paires (ref_a, ref_b) reliees par un fil, dans l'ordre de trace —
        # meme idiome que fig._z_hitboxes/_comp_positions ailleurs dans le
        # projet : le test inspecte cet etat plutot que de gratter les
        # artistes matplotlib (les symboles eux-memes contiennent deja des
        # segments de ligne, ambigu a distinguer d'un vrai fil par type).
        fig._apercu_connexions = []
        if not refs:
            return fig

        espace = 2.5
        bornes = {}
        with schemdraw.Drawing(canvas=ax, show=False) as d:
            d.config(fontsize=10, inches_per_unit=0.5)
            for i, ref in enumerate(refs):
                info = self._comp_info.get(ref, {})
                typ = info.get("type", "?")
                val = info.get("value", "")
                cls, coul, ref_txt, valeur = style_symbole(typ, val, ref)
                x0, x1 = i * espace, i * espace + 1.5
                el = cls().at((x0, 0)).to((x1, 0)).color(coul).label(
                    ref_txt, loc="bottom", fontsize=9, color=coul)
                if valeur:
                    el = el.label(valeur, loc="top", fontsize=9, color=coul)
                d.add(el)
                bornes[ref] = (x0, x1)

            for i, ref_a in enumerate(refs):
                nets_a = set((self._comp_info.get(ref_a, {})
                             .get("pins") or {}).values())
                for ref_b in refs[i + 1:]:
                    nets_b = set((self._comp_info.get(ref_b, {})
                                 .get("pins") or {}).values())
                    if nets_a & nets_b:
                        _xa0, xa1 = bornes[ref_a]
                        xb0, _xb1 = bornes[ref_b]
                        d.add(elm.Line().at((xa1, 0)).to((xb0, 0))
                              .color("#64748b"))
                        fig._apercu_connexions.append((ref_a, ref_b))
        try:
            fig.tight_layout(pad=0.4)
        except Exception:
            _log.debug("tight_layout ignore", exc_info=True)
        return fig
```

Modifier `_build_step4` (l. 452-487) pour insérer une zone de dessin
au-dessus de `_preview_box`, en réduisant l'espace laissé au JSON (qui reste
visible en secondaire, plus petit) :

```python
    def _build_step4(self):
        """@brief Construit le contenu de l'étape 4 (aperçu schéma + JSON + bouton Créer)."""
        frame = ctk.CTkFrame(self._left, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_remove()
        frame.grid_rowconfigure(0, weight=2)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        self._step_frames[4] = frame

        self._apercu_frame = ctk.CTkFrame(frame, fg_color=_JSON_BG,
                                          corner_radius=10)
        self._apercu_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        self._preview_box = ctk.CTkTextbox(
            frame,
            fg_color=_JSON_BG,
            text_color=_JSON_FG,
            font=ctk.CTkFont("Consolas", 11),
            corner_radius=10,
            border_width=1, border_color=BORDER,
            wrap="none",
            state="disabled",
        )
        self._preview_box.grid(row=1, column=0, sticky="nsew", pady=(0, 10))

        self._summary_label = ctk.CTkLabel(
            frame, text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=MUTED, justify="left", anchor="w",
            wraplength=560)
        self._summary_label.grid(row=2, column=0, sticky="ew")

        self._btn_create = ctk.CTkButton(
            frame,
            text="Créer le pattern",
            height=42, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=_BTN_CREATE, hover_color=_BTN_CREATE_H,
            command=self._create_pattern)
        self._btn_create.grid(row=3, column=0, sticky="ew", pady=(10, 0))
```

Modifier `_update_preview` (l. 698-713) pour (re)construire le canvas à
chaque affichage de l'étape 4 :

```python
    def _update_preview(self):
        """@brief Reconstruit l'apercu schematique et met a jour JSON/resume de l'etape 4."""
        if self._apercu_canvas is not None:
            self._apercu_canvas.get_tk_widget().destroy()
        fig = self._dessiner_apercu()
        self._apercu_canvas = FigureCanvasTkAgg(fig, master=self._apercu_frame)
        self._apercu_canvas.draw()
        self._apercu_canvas.get_tk_widget().configure(
            bg=_JSON_BG, highlightthickness=0)
        self._apercu_canvas.get_tk_widget().pack(
            fill="both", expand=True, padx=4, pady=4)

        payload = self._build_pattern_dict()
        text = json.dumps(payload, ensure_ascii=False, indent=2)

        self._preview_box.configure(state="normal")
        self._preview_box.delete("1.0", "end")
        self._preview_box.insert("1.0", text)
        self._preview_box.configure(state="disabled")

        types = self._selected_types()
        n_conds = len(self._selected_conditions())
        type_str = ", ".join(types) if types else "?"
        self._summary_label.configure(
            text=f"Ce pattern sera reconnu dans tout circuit contenant "
                 f"[{type_str}] avec {n_conds} condition(s).")
```

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_pattern_wizard.py -q`
Attendu : 6/6 PASS.

- [ ] **Step 5 : commit**

```bash
git add gui/pattern_wizard.py tests/test_pattern_wizard.py
git commit -m "feat(wizard): apercu schematique a l'etape de confirmation (symboles reels + fils)"
```

---

### Task 2 : Supprimer un circuit personnalisé depuis la popup schéma

**Files:**
- Modify: `gui/circuit_viewer.py`
- Test: `tests/test_show_circuit_popup.py` (nouveau — `show_circuit` n'a
  actuellement aucune couverture de test)

**Interfaces:**
- Consumes : `custom_circuits.loader.load_custom_circuits() -> list[dict]`,
  `custom_circuits.loader.save_custom_circuits(circuits: list[dict]) -> None`
  (déjà publics, déjà utilisés ailleurs).

- [ ] **Step 1 : écrire les tests qui échouent**

Créer `tests/test_show_circuit_popup.py` :

```python
"""@file test_show_circuit_popup.py
@brief Bouton de suppression d'un circuit personnalise dans la popup de
schema (spec 2026-08-04). Tk -> skip sans display.
"""
import pytest

ctk = pytest.importorskip("customtkinter")


@pytest.fixture
def ctk_root():
    import tkinter as tk
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("pas d'affichage Tk disponible")
    root.withdraw()
    yield root
    root.destroy()


def _custom_circuits(monkeypatch, tmp_path, circuits):
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)
    loader.save_custom_circuits(circuits)
    return chemin


def _textes_des_boutons_de_la_barre_du_bas(popup):
    """@brief Textes des boutons de la barre du bas de la popup show_circuit.

    La barre du bas est un CTkFrame direct enfant de `popup`, contenant les
    boutons en enfants directs (pas de nesting supplementaire, cf.
    `show_circuit`) : une recherche a 2 niveaux suffit, plus robuste qu'une
    recursion non bornee sur tout l'arbre de widgets.
    """
    textes = []
    for cadre in popup.winfo_children():
        for w in cadre.winfo_children():
            if hasattr(w, "cget"):
                try:
                    textes.append(w.cget("text"))
                except Exception:
                    pass
    return textes


def test_bouton_supprimer_visible_pour_un_circuit_personnalise(
        ctk_root, monkeypatch, tmp_path):
    _custom_circuits(monkeypatch, tmp_path,
                     [{"name": "Mon montage", "components": ["R"],
                       "conditions": []}])
    from gui import circuit_viewer as cv
    result = {"circuit_type": "Mon montage", "components": ["R1"],
              "nodes": ["A", "B"]}
    cv.show_circuit(result, {"R1": {"type": "R", "value": "10k"}},
                    parent=ctk_root)
    popup = ctk_root.winfo_children()[-1]
    assert any("Supprimer" in t
              for t in _textes_des_boutons_de_la_barre_du_bas(popup))


def test_bouton_supprimer_absent_pour_un_circuit_integre(
        ctk_root, monkeypatch, tmp_path):
    _custom_circuits(monkeypatch, tmp_path, [])
    from gui import circuit_viewer as cv
    result = {"circuit_type": "Suiveur de tension (AOP)",
              "components": ["U1"], "nodes": ["A", "B"]}
    cv.show_circuit(result, {"U1": {"type": "U", "value": ""}},
                    parent=ctk_root)
    popup = ctk_root.winfo_children()[-1]
    assert not any("Supprimer" in t
                  for t in _textes_des_boutons_de_la_barre_du_bas(popup))


def test_supprimer_retire_le_circuit_du_fichier(
        ctk_root, monkeypatch, tmp_path):
    from tkinter import messagebox
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    _custom_circuits(monkeypatch, tmp_path,
                     [{"name": "Mon montage", "components": ["R"],
                       "conditions": []},
                      {"name": "Autre", "components": ["C"],
                       "conditions": []}])
    from gui import circuit_viewer as cv
    result = {"circuit_type": "Mon montage", "components": ["R1"],
              "nodes": ["A", "B"]}
    cv.show_circuit(result, {"R1": {"type": "R", "value": "10k"}},
                    parent=ctk_root)

    from custom_circuits.loader import load_custom_circuits
    cv._supprimer_circuit_personnalise("Mon montage")
    noms = [c["name"] for c in load_custom_circuits()]
    assert noms == ["Autre"]
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_show_circuit_popup.py -q`
Attendu : le 1er test échoue (bouton absent), le 3e échoue
(`AttributeError: module 'gui.circuit_viewer' has no attribute
'_supprimer_circuit_personnalise'`).

- [ ] **Step 3 : implémenter**

Dans `gui/circuit_viewer.py`, ajouter l'import en tête de fichier (section
imports, après les imports `tkinter`) :

```python
from tkinter import messagebox

from custom_circuits.loader import load_custom_circuits, save_custom_circuits
```

Ajouter la fonction, avant `show_circuit` (l. 446) :

```python
def _supprimer_circuit_personnalise(nom: str) -> None:
    """@brief Retire un pattern personnalise de custom_circuits.json par nom.

    @param nom Nom exact du pattern (result["circuit_type"]).
    @return None
    """
    circuits = [c for c in load_custom_circuits() if c.get("name") != nom]
    save_custom_circuits(circuits)
```

Modifier `show_circuit` : après la construction de `drawer` (l. 456),
détecter si c'est un circuit personnalisé :

```python
    name    = result["circuit_type"]
    drawer  = _DRAWERS.get(name)
    est_perso = any(c.get("name") == name for c in load_custom_circuits())
```

Dans la « Bottom bar » (l. 516-530), ajouter le bouton entre « Exporter PNG »
et « Fermer » :

```python
    if est_perso:
        def _supprimer():
            if messagebox.askyesno(
                    "Confirmer",
                    f"Supprimer le circuit personnalisé « {name} » ?\n"
                    "Les prochaines analyses ne le reconnaîtront plus."):
                _supprimer_circuit_personnalise(name)
                popup.destroy()
        ctk.CTkButton(bar, text="🗑  Supprimer",
                      width=140, height=30, corner_radius=6,
                      font=ctk.CTkFont("Segoe UI", 11),
                      fg_color=theme.ERROR, hover_color="#dc2626",
                      command=_supprimer).pack(side="left", padx=(0, 12), pady=7)
```

(Placer ce bloc juste après le `.pack(...)` du bouton « 💾 Exporter PNG »,
avant le bouton « Fermer ».)

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_show_circuit_popup.py -q`
Attendu : 3/3 PASS.

- [ ] **Step 5 : commit**

```bash
git add gui/circuit_viewer.py tests/test_show_circuit_popup.py
git commit -m "feat(viewer): bouton supprimer pour un circuit personnalise dans la popup schema"
```

---

### Task 3 : Retirer l'onglet Circuits

**Files:**
- Delete: `gui/tab_circuits.py`
- Delete: `tests/test_pattern_refresh.py` (couvre uniquement le
  rafraîchissement de l'onglet Circuits, qui disparaît)
- Modify: `tests/test_gui_sync.py` (retirer le test lié à Circuits)
- Modify: `tests/test_palette_et_doublon.py` (retirer le test lié à
  Circuits — remplacé par `test_doublon_de_nom_refuse_a_l_etape_2` de la
  Tâche 1)
- Modify: `gui/app_window.py` (désincrire l'onglet — **voir contrainte
  `git add -p` en tête de plan**)
- Modify: `README.md`

**Interfaces:**
- Consumes : rien de nouveau — cette tâche ne fait que retirer du câblage
  devenu mort maintenant que les Tâches 1 et 2 couvrent les deux capacités
  réelles de l'ancien onglet.

- [ ] **Step 1 : retirer les tests devenus obsolètes**

Dans `tests/test_gui_sync.py`, supprimer entièrement la fonction
`test_suppression_composant_retiree_de_l_onglet_circuits` (l. 141-176) : elle
ne teste que le rafraîchissement interne de `TabCircuits._comp_vars`, un
mécanisme qui disparaît avec la classe — aucun comportement réel équivalent
à préserver (la synchronisation palette éditeur ↔ bibliothèque composants
reste couverte par `test_palette_et_doublon.py`).

Dans `tests/test_palette_et_doublon.py`, supprimer entièrement la fonction
`test_doublon_pattern_refuse` (l. 118-146) et la section « Partie 3 : doublon
de pattern » qui la précède (l. 116-117) : remplacée par
`test_doublon_de_nom_refuse_a_l_etape_2` dans
`tests/test_pattern_wizard.py` (Tâche 1), qui teste le même comportement
réel sur le chemin qui subsiste (`PatternWizard`).

Supprimer le fichier `tests/test_pattern_refresh.py` entièrement (`rm
tests/test_pattern_refresh.py` ou suppression via l'outil de fichiers) : il
ne teste que `TabCircuits.refresh_circuits()`, qui n'existe plus.

- [ ] **Step 2 : vérifier que la suite reste verte sans ces tests**

Run : `PYTHONUTF8=1 python -m pytest tests/test_gui_sync.py
tests/test_palette_et_doublon.py tests/test_pattern_wizard.py -q`
Attendu : tout PASS (aucun test ne référence encore `TabCircuits` dans ces
fichiers).

- [ ] **Step 3 : supprimer `gui/tab_circuits.py`**

```bash
rm gui/tab_circuits.py
```

Vérifier qu'aucune référence ne subsiste :

```bash
grep -rn "TabCircuits\|tab_circuits" --include=*.py . | grep -v __pycache__
```

Attendu à ce stade : seulement `gui/app_window.py` (Step 4 ci-dessous s'en
charge).

- [ ] **Step 4 : désincrire l'onglet dans `gui/app_window.py`**

Retirer l'import (l. 11) :
```python
from gui.tab_circuits import TabCircuits
```

Retirer l'entrée de navigation (l. 102) dans la liste `items` :
```python
            ("zap",      "Circuits",   "Patterns personnalisés"),
```

Remplacer le bloc `_on_pattern_created`/`_on_lib_change`/instanciation
(l. 125-152) :

AVANT :
```python
        # Liaison tardive : tab_c n'existe pas encore quand tab_a/tab_d sont créés,
        # mais ce callback n'est appelé qu'après une action utilisateur (le nom
        # tab_c est alors résolu).
        def _on_pattern_created():
            # Un pattern vient d'être créé (éditeur/analyse) : recharger la liste
            # de l'onglet Circuits, sinon il n'y apparaît qu'au prochain démarrage.
            tab_c.refresh_circuits()

        tab_a = TabAnalyze(content, on_pattern_created=_on_pattern_created)
        self._tab_a = tab_a  # référence gardée pour l'auto-analyse au démarrage (voir _auto_analyze)
        tab_d = TabDraw(content,
                        on_analyze=lambda path: (
                            tab_a._file_path.set(path),
                            tab_a._analyze(),
                            self._switch(0),
                        ),
                        on_pattern_created=_on_pattern_created)
        tab_c = TabCircuits(content)

        def _on_lib_change():
            # La bibliothèque a changé : rafraîchir l'onglet Circuits ET la
            # palette de l'éditeur de schéma (nouveaux types / types supprimés).
            tab_c.refresh_component_list()
            tab_d.refresh_palette()

        tab_p = TabComponents(content, on_save=_on_lib_change)

        self._frames = [tab_a.frame, tab_d.frame, tab_c.frame, tab_p.frame]
```

APRÈS :
```python
        tab_a = TabAnalyze(content)
        self._tab_a = tab_a  # référence gardée pour l'auto-analyse au démarrage (voir _auto_analyze)
        tab_d = TabDraw(content,
                        on_analyze=lambda path: (
                            tab_a._file_path.set(path),
                            tab_a._analyze(),
                            self._switch(0),
                        ))

        tab_p = TabComponents(content, on_save=tab_d.refresh_palette)

        self._frames = [tab_a.frame, tab_d.frame, tab_p.frame]
```

`on_pattern_created` est déjà `None` par défaut dans les deux constructeurs
(`gui/tab_analyze.py:104`, `gui/tab_draw.py:25`), et les deux gardent l'appel
derrière `if self._on_pattern_created_cb:` / `if self._on_pattern_created:`
(`gui/tab_analyze.py:761`, `gui/tab_draw.py:336`) — l'omettre est donc déjà
sûr, vérifié, pas la peine de passer `None` explicitement.

Mettre à jour le docstring de la classe (l. 22) :
```python
    """@brief Fenêtre principale de l'application (barre latérale + 3 onglets)."""
```

Mettre à jour le docstring de `_switch` (l. 161) :
```python
        @param idx Indice de l'onglet à afficher (0=Analyser, 1=Schéma, 2=Composants).
```

Mettre à jour le commentaire de `_NavButton` (l. 187) :
```python
        # Hauteur fixe : sans elle un CTkFrame garde sa hauteur par défaut (200 px)
        # et les onglets ne tenaient pas tous à l'écran.
```

- [ ] **Step 5 : vérifier manuellement que l'app démarre**

Run : `PYTHONUTF8=1 python app.py` — vérifier à l'œil que 3 onglets
apparaissent (Analyser, Schéma, Composants), qu'aucune exception n'est levée
à l'ouverture, et que créer un pattern personnalisé depuis Analyser ou
Schéma fonctionne toujours (le wizard s'ouvre, étape 4 affiche un schéma).
Fermer l'app avant de continuer.

- [ ] **Step 6 : mettre à jour `README.md`**

Chercher le tableau des 4 onglets (section Utilisation, table `| Onglet |
Rôle |`) et retirer la ligne `| **Circuits** | ... |`.

- [ ] **Step 7 : suite complète**

Run : `PYTHONUTF8=1 python -m pytest -q`
Attendu : 0 échec (hors le flake de timing connu et documenté
`test_500_portes_sous_budget`, déjà budgeté à 20 s — relancer isolément
s'il échoue en suite complète).

- [ ] **Step 8 : commit**

**Rappel de la contrainte du plan (section Global Constraints) : ne jamais
`git add gui/app_window.py` tel quel.**

```bash
git add gui/tab_circuits.py  # fichier supprime (Step 3) : git enregistre la suppression
git add tests/test_gui_sync.py tests/test_palette_et_doublon.py
git add tests/test_pattern_refresh.py  # supprime (Step 1) : idem, enregistre la suppression
git add README.md
git add -p gui/app_window.py
# Dans le mode interactif : accepter (y) UNIQUEMENT les hunks qui retirent
# l'import TabCircuits, l'entrée de nav "Circuits", et le bloc
# _on_pattern_created/_on_lib_change/instanciation/_frames. Refuser (n) tout
# hunk touchant initial_file, _auto_analyze, self._tab_a, ou le docstring
# __init__ — ce ne sont pas des changements de ce chantier.
git status  # confirmer qu'aucune ligne liee a initial_file/_auto_analyze n'est stagee
git commit -m "refactor(gui): retire l'onglet Circuits (redondant avec le wizard depuis Analyser/Schema)"
```

---

### Task 4 : Validation finale

- [ ] **Step 1 : suite complète, deux fois**

```bash
PYTHONUTF8=1 python -m pytest -q
```

Relancer une seconde fois pour confirmer la stabilité (pas de flake
introduit par ce chantier). Attendu les deux fois : même nombre de PASS,
0 échec hors `test_500_portes_sous_budget` (connu, relancer isolé si
besoin).

- [ ] **Step 2 : vérifier qu'aucune trace de code mort ne subsiste**

```bash
grep -rn "TabCircuits\|tab_circuits" --include=*.py . | grep -v __pycache__
```

Attendu : aucun résultat.

- [ ] **Step 3 : revue de l'état git**

```bash
git status
git log --oneline -5
```

Confirmer : 3 commits de ce chantier présents (Tâches 1, 2, 3), aucun fichier
inattendu stagé, `gui/app_window.py` encore modifié en local (les hunks NON
liés à ce chantier — la feature de l'utilisateur — toujours présents et
non commités).

- [ ] **Step 4 : rien n'est poussé sans accord explicite du boss.**
