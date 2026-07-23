# Brochage positionné à la création — Plan d'implémentation

> **Pour l'exécutant :** exécution via `superpowers:executing-plans` ou
> `superpowers:subagent-driven-development`. Étapes en cases à cocher.

**Spec :** `docs/superpowers/specs/2026-07-23-brochage-a-la-creation-design.md` (commit `c261dc9`).

**Goal :** placer les broches d'un type à la souris dans l'onglet « Composants »,
et que ce brochage vaille partout où le type est posé.

**Architecture :** un widget canevas autonome `gui/pin_canvas.py` qui réutilise
les fonctions **pures** livrées le 2026-07-23 (`geometrie_libre`,
`aimanter_bord`, `_tr_boite_libre`) ; la source de vérité du formulaire passe de
widgets (`_pin_lignes`) à une **liste de données** `self._brochage:
list[(nom, côté, décalage)]` dont l'ordre est celui de la netlist ; un champ
**additif** `brochage` dans `component_library.json`, honoré par `_auto_def`.

**Tech Stack :** Python 3.11, Tkinter/customtkinter, pytest. Aucune dépendance neuve.

## Global Constraints

- Commits en **français**, **jamais** de footer `Co-Authored-By: Claude`.
- **Jamais `git add -A`** : fichiers un par un.
- **Ne jamais committer** `component_library.json` ni `custom_circuits.json`.
  Les tests écrivent dans un `tmp_path` (monkeypatch de `chemin_bibliotheque`),
  **jamais** le vrai fichier.
- `docs.rar`, `SolutionERetroDesignX20260813/`, `CARTE POUR TESTER (VRAI TEST)/` :
  lecture seule, jamais committés.
- `PYTHONUTF8=1` sur tout pytest ; `schemdraw==0.22` pinné.
- Chrome via `theme.py`/`ui_kit.py`, **jamais de hex en dur**.
- Flake connu : `test_500_portes_sous_budget` → relancer isolé.
- Branche `rewrite-simple` ; rien n'est poussé sans accord explicite.

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `gui/pin_canvas.py` | **Créé** — widget `PinCanvas` (dessin, ajout, glisser, renommer, supprimer) + bandeau d'ordre |
| `gui/schematic_editor.py` | `_auto_def` honore `brochage` (3 lignes) ; `_compute_defs` le transmet |
| `gui/tab_components.py` | `_pin_lignes` → `self._brochage` ; carte « Broches » → `PinCanvas` |
| `tests/test_pin_canvas.py` | **Créé** — widget seul (T1→T3) |
| `tests/test_tab_components.py` | **Créé** — intégration onglet (T5) |

---

### Task 1 : `PinCanvas` — dessin et ajout de broche

**Files:** Create `gui/pin_canvas.py`, `tests/test_pin_canvas.py`

**Interfaces produites :**
- `PinCanvas(parent, on_change=None, hauteur=260)`
- `.charger(brochage: list, lecture_seule: bool = False)`
- `.brochage() -> list[tuple[str, str, int]]`
- `._ajouter(wx, wy) -> str | None` (coordonnées **repère boîte**, origine au centre)
- `._nom_libre() -> str`

- [ ] **Step 1 : tests qui échouent** — `tests/test_pin_canvas.py`

```python
"""@file test_pin_canvas.py
@brief Canevas de brochage de l'onglet Composants (spec 2026-07-23).
Tk -> skip sans display.
"""
import pytest

ctk = pytest.importorskip("customtkinter")

from gui.pin_canvas import PinCanvas          # noqa: E402


@pytest.fixture
def canevas():
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("pas de display Tk")
    root.withdraw()
    pc = PinCanvas(root)
    pc.pack()
    root.update_idletasks()
    yield pc
    root.destroy()


def test_canevas_vierge(canevas):
    assert canevas.brochage() == []


def test_clic_bord_gauche_ajoute_une_broche(canevas):
    assert canevas._ajouter(-40, 0) == "1"
    (nom, cote, dec), = canevas.brochage()
    assert (nom, cote) == ("1", "L")
    assert dec % 20 == 0


def test_broches_ajoutees_en_fin_et_numerotees(canevas):
    canevas._ajouter(-40, -20)
    canevas._ajouter(-40, 20)
    canevas._ajouter(0, -30)
    assert [n for n, _, _ in canevas.brochage()] == ["1", "2", "3"]


def test_charger_puis_brochage_est_fidele(canevas):
    src = [("VCC", "T", 0), ("IN", "L", -20), ("GND", "B", 0)]
    canevas.charger(src)
    assert canevas.brochage() == src


def test_lecture_seule_ne_mute_pas(canevas):
    canevas.charger([("VCC", "T", 0)], lecture_seule=True)
    canevas._ajouter(-40, 0)
    assert canevas.brochage() == [("VCC", "T", 0)]
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_pin_canvas.py -q`
Attendu : `ModuleNotFoundError: No module named 'gui.pin_canvas'`

- [ ] **Step 3 : implémenter** — `gui/pin_canvas.py`

```python
"""
@file pin_canvas.py
@brief Canevas de brochage de l'onglet « Composants » (spec 2026-07-23).

Repère FIXE : échelle 1, origine au centre du canevas. Aucun zoom, aucun pan —
c'est ce qui permet de ne PAS embarquer `SchematicEditor` (palette, câblage,
undo, export) pour un simple placement de broches.
"""
import tkinter as tk
from tkinter import simpledialog

import customtkinter as ctk

from gui.schematic_symbols import (AUTO_COLOR, TYPE_LIBRE, aimanter_bord,
                                   geometrie_libre, primitives)
from gui.theme import CARD2, TEXT_MUTED

GRILLE = 20
_R_BROCHE = 5
_R_CLIC = 12
_PIN_OFF = "#ef4444"


class PinCanvas(ctk.CTkFrame):
    """@brief Placement des broches d'un TYPE à la souris.

    @param on_change Callback appelé après toute mutation, avec le brochage.
    """

    def __init__(self, parent, on_change=None, hauteur=260):
        super().__init__(parent, fg_color=CARD2)
        self._on_change = on_change
        self._brochage: list = []          # [(nom, côté, décalage)] ORDONNÉ
        self._lecture_seule = False
        self._selection: str | None = None
        self._cv = tk.Canvas(self, height=hauteur, highlightthickness=0,
                             bg="#0f172a")
        self._cv.pack(fill="both", expand=True, padx=8, pady=8)
        self._cv.bind("<Configure>", lambda _e: self._dessiner())

    # ── API publique ────────────────────────────────────────────────────────

    def charger(self, brochage: list, lecture_seule: bool = False):
        """@brief Remplace le brochage affiché (liste ordonnée de tuples)."""
        self._brochage = [tuple(b) for b in brochage]
        self._lecture_seule = lecture_seule
        self._selection = None
        self._dessiner()

    def brochage(self) -> list:
        """@brief Brochage courant, dans l'ordre (= ordre de la netlist)."""
        return list(self._brochage)

    # ── Géométrie ───────────────────────────────────────────────────────────

    def _defn(self) -> dict:
        return geometrie_libre({n: (c, d) for n, c, d in self._brochage})

    def _centre(self) -> tuple:
        return (self._cv.winfo_width() // 2, self._cv.winfo_height() // 2)

    def _nom_libre(self) -> str:
        """@brief Plus petit entier >= 1 non utilisé (une suppression se recycle)."""
        pris = {n for n, _, _ in self._brochage}
        i = 1
        while str(i) in pris:
            i += 1
        return str(i)

    # ── Mutations ───────────────────────────────────────────────────────────

    def _ajouter(self, wx, wy):
        """@brief Ajoute une broche aimantée au bord le plus proche.

        @param wx,wy Coordonnées dans le repère BOÎTE (origine au centre).
        @return Nom attribué, ou None en lecture seule.
        """
        if self._lecture_seule:
            return None
        d = self._defn()
        nom = self._nom_libre()
        cote, dec = aimanter_bord(wx, wy, d["w"], d["h"], GRILLE)
        self._brochage.append((nom, cote, dec))     # toujours EN FIN
        self._muter()
        return nom

    def _muter(self):
        self._dessiner()
        if self._on_change:
            self._on_change(self.brochage())

    # ── Dessin ──────────────────────────────────────────────────────────────

    def _dessiner(self):
        self._cv.delete("all")
        cx, cy = self._centre()
        if cx <= 1:
            return                      # widget pas encore dimensionné
        d = self._defn()
        for p in primitives(TYPE_LIBRE, d, 0):
            if p[0] == "polygon":
                pts = [c for x, y in p[1] for c in (cx + x, cy + y)]
                self._cv.create_polygon(*pts, fill="", outline=AUTO_COLOR,
                                        width=2)
            elif p[0] == "text":
                self._cv.create_text(cx + p[1][0], cy + p[1][1], text=p[2],
                                     fill=TEXT_MUTED,
                                     font=("Consolas", 8),
                                     anchor={"e": "e", "w": "w"}.get(p[4],
                                                                     "center"))
        for nom, (px, py) in d["pins"].items():
            x, y = cx + px, cy + py
            self._cv.create_oval(x - _R_BROCHE, y - _R_BROCHE,
                                 x + _R_BROCHE, y + _R_BROCHE,
                                 fill="#0f172a", outline=_PIN_OFF, width=2,
                                 tags=(f"broche_{nom}",))
```

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_pin_canvas.py -q` → PASS

- [ ] **Step 5 : commit**

```bash
git add gui/pin_canvas.py tests/test_pin_canvas.py
git commit -m "feat(composants): canevas de brochage, pose de broche aimantee au bord"
```

---

### Task 2 : `PinCanvas` — glisser, renommer, supprimer

**Files:** Modify `gui/pin_canvas.py`, `tests/test_pin_canvas.py`

**Interfaces produites :**
- `._broche_a(wx, wy) -> str | None` (hit-test, repère boîte)
- `._deplacer(nom, wx, wy)`
- `._renommer(ancien, nouveau) -> bool`
- `._supprimer(nom)`

- [ ] **Step 1 : tests qui échouent**

```python
def test_glisser_conserve_l_ordre_et_aimante(canevas):
    canevas._ajouter(-40, -20)
    canevas._ajouter(-40, 20)
    canevas._deplacer("1", -40, 27)
    noms = [n for n, _, _ in canevas.brochage()]
    assert noms == ["1", "2"]                    # ordre INCHANGE
    cote, dec = next((c, d) for n, c, d in canevas.brochage() if n == "1")
    assert cote == "L" and dec % 20 == 0


def test_glisser_au_dela_du_coin_agrandit_la_boite(canevas):
    canevas._ajouter(-40, 0)
    h_avant = canevas._defn()["h"]
    canevas._deplacer("1", -40, 200)
    assert canevas._defn()["h"] > h_avant


def test_renommage_refuse_vide_et_doublon(canevas):
    canevas._ajouter(-40, -20)
    canevas._ajouter(-40, 20)
    assert canevas._renommer("1", "VCC") is True
    assert [n for n, _, _ in canevas.brochage()] == ["VCC", "2"]
    assert canevas._renommer("2", "VCC") is False
    assert canevas._renommer("2", "  ") is False
    assert [n for n, _, _ in canevas.brochage()] == ["VCC", "2"]


def test_suppression_puis_ajout_recycle_le_nom_en_fin(canevas):
    for dy in (-20, 0, 20):
        canevas._ajouter(-40, dy)
    canevas._supprimer("2")
    assert [n for n, _, _ in canevas.brochage()] == ["1", "3"]
    canevas._ajouter(40, 0)
    assert [n for n, _, _ in canevas.brochage()] == ["1", "3", "2"]


def test_hit_test_trouve_la_broche(canevas):
    canevas._ajouter(-40, 0)
    px, py = canevas._defn()["pins"]["1"]
    assert canevas._broche_a(px, py) == "1"
    assert canevas._broche_a(px + 200, py) is None
```

- [ ] **Step 2 : vérifier l'échec** — `AttributeError: '_deplacer'`

- [ ] **Step 3 : implémenter** — ajouter à `PinCanvas`

```python
    def _broche_a(self, wx, wy):
        """@brief Nom de la broche sous (wx,wy) en repère BOÎTE, sinon None."""
        for nom, (px, py) in self._defn()["pins"].items():
            if (wx - px) ** 2 + (wy - py) ** 2 <= _R_CLIC ** 2:
                return nom
        return None

    def _index(self, nom):
        for i, (n, _c, _d) in enumerate(self._brochage):
            if n == nom:
                return i
        return -1

    def _deplacer(self, nom, wx, wy):
        """@brief Fait coulisser une broche. L'ORDRE ne change pas (position et
        rang sont deux données indépendantes)."""
        if self._lecture_seule:
            return
        i = self._index(nom)
        if i < 0:
            return
        d = self._defn()
        cote, dec = aimanter_bord(wx, wy, d["w"], d["h"], GRILLE)
        self._brochage[i] = (nom, cote, dec)
        self._muter()

    def _renommer(self, ancien, nouveau) -> bool:
        """@brief Renomme une broche en place.
        @return False si vide ou déjà pris."""
        if self._lecture_seule:
            return False
        nouveau = (nouveau or "").strip()
        i = self._index(ancien)
        if i < 0 or not nouveau:
            return False
        if any(n == nouveau for n, _c, _d in self._brochage):
            return False
        _n, cote, dec = self._brochage[i]
        self._brochage[i] = (nouveau, cote, dec)
        if self._selection == ancien:
            self._selection = nouveau
        self._muter()
        return True

    def _supprimer(self, nom):
        """@brief Retire une broche (les suivantes remontent d'un rang)."""
        if self._lecture_seule:
            return
        i = self._index(nom)
        if i < 0:
            return
        self._brochage.pop(i)
        if self._selection == nom:
            self._selection = None
        self._muter()
```

Puis le câblage souris dans `__init__` :

```python
        self._cv.bind("<Button-1>", self._sur_clic)
        self._cv.bind("<B1-Motion>", self._sur_glisse)
        self._cv.bind("<Double-Button-1>", self._sur_double_clic)
        self._cv.bind("<Delete>", self._sur_suppr)
        self._cv.bind("<Button-1>", lambda e: self._cv.focus_set(), add="+")
```

```python
    def _boite(self, event):
        """@brief Événement écran -> coordonnées repère BOÎTE."""
        cx, cy = self._centre()
        return event.x - cx, event.y - cy

    def _sur_clic(self, event):
        wx, wy = self._boite(event)
        touchee = self._broche_a(wx, wy)
        self._selection = touchee if touchee else self._ajouter(wx, wy)

    def _sur_glisse(self, event):
        if self._selection:
            self._deplacer(self._selection, *self._boite(event))

    def _sur_double_clic(self, event):
        nom = self._broche_a(*self._boite(event))
        if not nom or self._lecture_seule:
            return
        nouveau = simpledialog.askstring(
            "Renommer la broche", f"Nouveau nom pour « {nom} » :",
            initialvalue=nom, parent=self)
        if nouveau is not None and not self._renommer(nom, nouveau):
            tk.messagebox.showerror("Erreur", "Nom vide ou déjà utilisé.")

    def _sur_suppr(self, _event=None):
        if self._selection:
            self._supprimer(self._selection)
```

Et dessiner la broche sélectionnée en surbrillance dans `_dessiner`.

- [ ] **Step 4 : vérifier le vert**
- [ ] **Step 5 : commit**

```bash
git add gui/pin_canvas.py tests/test_pin_canvas.py
git commit -m "feat(composants): glisser, renommer et supprimer une broche au canevas"
```

---

### Task 3 : Bandeau d'ordre réordonnable

**Files:** Modify `gui/pin_canvas.py`, `tests/test_pin_canvas.py`

**Interfaces produites :** `._reordonner(depuis: int, vers: int)` ; bandeau
construit sous le canevas, reconstruit à chaque `_muter`.

Le glisser-déposer de pastilles est le morceau d'UI le moins trivial du
chantier : la **logique** est testée via `_reordonner`, pas via la souris.

- [ ] **Step 1 : tests qui échouent**

```python
def test_reordonner_permute_sans_bouger_les_positions(canevas):
    canevas.charger([("A", "L", -20), ("B", "L", 20), ("C", "R", 0)])
    positions = dict(canevas._defn()["pins"])
    canevas._reordonner(2, 0)
    assert [n for n, _, _ in canevas.brochage()] == ["C", "A", "B"]
    assert dict(canevas._defn()["pins"]) == positions   # dessin inchangé


def test_reordonner_index_hors_bornes_est_sans_effet(canevas):
    canevas.charger([("A", "L", 0), ("B", "R", 0)])
    canevas._reordonner(5, 0)
    canevas._reordonner(0, 9)
    assert [n for n, _, _ in canevas.brochage()] == ["A", "B"]
```

- [ ] **Step 2 : vérifier l'échec**

- [ ] **Step 3 : implémenter**

```python
    def _reordonner(self, depuis: int, vers: int):
        """@brief Déplace la broche de rang `depuis` au rang `vers`.

        L'ordre est la donnée de la NETLIST ; les positions à l'écran n'en
        dépendent pas et ne bougent donc pas.
        """
        if self._lecture_seule:
            return
        n = len(self._brochage)
        if not (0 <= depuis < n) or not (0 <= vers < n) or depuis == vers:
            return
        item = self._brochage.pop(depuis)
        self._brochage.insert(vers, item)
        self._muter()
```

Bandeau, construit dans `__init__` sous le canevas et reconstruit par `_muter` :

```python
    def _construire_bandeau(self):
        """@brief Pastilles dans l'ORDRE de la netlist, réordonnables au glisser."""
        for w in self._bandeau.winfo_children():
            w.destroy()
        self._pastilles = []
        ctk.CTkLabel(self._bandeau, text="Ordre (netlist) :",
                     font=ui_kit.font("caption"),
                     text_color=TEXT_MUTED).pack(side="left", padx=(0, 6))
        for i, (nom, _c, _d) in enumerate(self._brochage):
            p = ctk.CTkLabel(self._bandeau, text=nom, fg_color=CARD2,
                             corner_radius=6, padx=8,
                             font=ctk.CTkFont("Consolas", 11))
            p.pack(side="left", padx=2)
            if not self._lecture_seule:
                p.bind("<Button-1>", lambda _e, k=i: self._debut_glisse(k))
                p.bind("<ButtonRelease-1>", self._fin_glisse)
            self._pastilles.append(p)

    def _debut_glisse(self, index):
        self._glisse_depuis = index

    def _fin_glisse(self, event):
        """@brief Dépose : la pastille sous le curseur donne le rang cible."""
        if self._glisse_depuis is None:
            return
        cible = self._pastille_sous(event.x_root, event.y_root)
        if cible is not None:
            self._reordonner(self._glisse_depuis, cible)
        self._glisse_depuis = None

    def _pastille_sous(self, x_root, y_root):
        """@brief Rang de la pastille aux coordonnées écran données, sinon None."""
        for i, p in enumerate(self._pastilles):
            x0, y0 = p.winfo_rootx(), p.winfo_rooty()
            if (x0 <= x_root <= x0 + p.winfo_width()
                    and y0 <= y_root <= y0 + p.winfo_height()):
                return i
        return None
```

Initialiser `self._glisse_depuis = None` et `self._pastilles = []` dans
`__init__`, et créer `self._bandeau = ctk.CTkFrame(self, fg_color="transparent")`
sous le canevas.

- [ ] **Step 4 : vérifier le vert**
- [ ] **Step 5 : commit**

```bash
git add gui/pin_canvas.py tests/test_pin_canvas.py
git commit -m "feat(composants): bandeau d'ordre des broches, reordonnable"
```

---

### Task 4 : `_auto_def` honore le champ `brochage`

**Files:** Modify `gui/schematic_editor.py:68` (`_auto_def`) et `_compute_defs`
(~l. 99) ; Test `tests/test_schematic_editor.py`

- [ ] **Step 1 : tests qui échouent**

```python
def test_auto_def_utilise_le_brochage_quand_il_existe():
    from gui.schematic_editor import _auto_def
    d = _auto_def("Ampli", ["VCC", "IN", "GND"],
                  {"VCC": ["T", 0], "IN": ["L", -20], "GND": ["B", 0]})
    w2, h2 = d["w"] // 2, d["h"] // 2
    assert d["pins"]["VCC"] == (0, -h2)
    assert d["pins"]["IN"] == (-w2, -20)
    assert d["pins"]["GND"] == (0, h2)
    assert d["label"] == "Ampli"


def test_auto_def_sans_brochage_reste_moitie_gauche_moitie_droite():
    from gui.schematic_editor import _auto_def
    d = _auto_def("X", ["1", "2", "3", "4"])
    assert d["pins"]["1"][0] < 0 and d["pins"]["2"][0] < 0
    assert d["pins"]["3"][0] > 0 and d["pins"]["4"][0] > 0
```

- [ ] **Step 2 : vérifier l'échec** — `TypeError: _auto_def() takes 2 positional arguments`

- [ ] **Step 3 : implémenter**

```python
def _auto_def(name: str, pins: list, brochage: dict = None) -> dict:
    """@brief Géométrie d'un type personnalisé.

    Si le type porte un `brochage` positionné (défini au canevas de l'onglet
    Composants, spec 2026-07-23), il fait foi. Sinon, répartition historique
    moitié gauche / moitié droite.
    """
    if brochage:
        d = geometrie_libre({n: tuple(v) for n, v in brochage.items()})
        d["label"] = name
        return d
    ...  # corps actuel, inchangé
```

et dans `_compute_defs` :

```python
        defs[key] = _auto_def(val.get("name", key), broches,
                              val.get("brochage"))
```

- [ ] **Step 4 : vérifier le vert** (+ `test_schematic_editor.py` entier)
- [ ] **Step 5 : commit**

```bash
git add gui/schematic_editor.py tests/test_schematic_editor.py
git commit -m "feat(composants): _auto_def honore le brochage positionne du type"
```

---

### Task 5 : Bascule de l'onglet Composants sur `self._brochage`

**Files:** Modify `gui/tab_components.py` ; Create `tests/test_tab_components.py`

C'est la tâche qui **supprime `_pin_lignes`**. Contrôle greppable en fin de
tâche : `grep -n "_pin_lignes" gui/` ne doit **rien** rendre.

- [ ] **Step 1 : tests qui échouent** — `tests/test_tab_components.py`

```python
"""@file test_tab_components.py
@brief Onglet Composants : brochage positionné (spec 2026-07-23).
Tk -> skip sans display. La bibliothèque est isolée dans tmp_path : le VRAI
component_library.json ne doit jamais être touché.
"""
import json

import pytest

ctk = pytest.importorskip("customtkinter")


@pytest.fixture
def onglet(tmp_path, monkeypatch):
    chemin = tmp_path / "component_library.json"
    monkeypatch.setattr("gui.tab_components.chemin_bibliotheque",
                        lambda: chemin)
    from gui.tab_components import TabComponents
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("pas de display Tk")
    root.withdraw()
    t = TabComponents(root)
    root.update_idletasks()
    yield t, chemin
    root.destroy()


def test_sauvegarde_ecrit_pins_dans_l_ordre_et_le_brochage(onglet, monkeypatch):
    t, chemin = onglet
    monkeypatch.setattr("gui.tab_components.messagebox.showinfo",
                        lambda *a, **k: None)
    t._prefix_var.set("IC")
    t._name_var.set("Ampli")
    t._brochage = [("VCC", "T", 0), ("IN", "L", -20), ("GND", "B", 0)]
    t._sauvegarder()
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert data["IC"]["pins"] == ["VCC", "IN", "GND"]
    assert data["IC"]["brochage"]["VCC"] == ["T", 0]


def test_relecture_d_un_type_sans_brochage_amorce_les_broches(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps(
        {"ZZ": {"name": "Ancien", "pins": ["A", "B", "C"]}}),
        encoding="utf-8")
    t._load()
    t._afficher_perso("ZZ")
    noms = [n for n, _, _ in t._brochage]
    assert noms == ["A", "B", "C"]                  # aucune broche perdue
    assert all(c in ("L", "R", "T", "B") for _n, c, _d in t._brochage)


def test_type_integre_est_en_lecture_seule(onglet):
    t, _ = onglet
    t._afficher_integre("R")
    assert t._canvas_broches._lecture_seule is True


def test_deplacer_une_broche_rend_le_formulaire_sale(onglet):
    t, _ = onglet
    t._prefix_var.set("IC")
    t._brochage = [("1", "L", 0)]
    t._prendre_snapshot()
    t._brochage = [("1", "R", 0)]
    assert t._etat_courant() != t._etat_initial


def test_duplication_clone_le_brochage(onglet):
    t, _ = onglet
    t._brochage = [("VCC", "T", 0)]
    t._dupliquer()
    t._brochage[0] = ("GND", "B", 0)
    assert t._etat_initial[2][0][0] == "VCC"        # snapshot non altéré


def test_sauvegarde_refuse_un_type_sans_broche(onglet, monkeypatch):
    t, chemin = onglet
    erreurs = []
    monkeypatch.setattr("gui.tab_components.messagebox.showerror",
                        lambda _t, m: erreurs.append(m))
    t._prefix_var.set("IC")
    t._name_var.set("Vide")
    t._brochage = []
    t._sauvegarder()
    assert erreurs and "broche" in erreurs[0].lower()
    assert not chemin.exists() or "IC" not in json.loads(
        chemin.read_text(encoding="utf-8"))


def test_relecture_d_un_type_avec_brochage_est_fidele(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({"IC": {
        "name": "Ampli", "pins": ["VCC", "IN", "GND"],
        "brochage": {"VCC": ["T", 0], "IN": ["L", -20], "GND": ["B", 0]}}}),
        encoding="utf-8")
    t._load()
    t._afficher_perso("IC")
    assert t._brochage == [("VCC", "T", 0), ("IN", "L", -20), ("GND", "B", 0)]


def test_saisie_rapide_voit_les_broches_dans_l_ordre(onglet, monkeypatch):
    """L'ordre du canevas doit ressortir tel quel côté saisie rapide."""
    t, chemin = onglet
    monkeypatch.setattr("gui.tab_components.messagebox.showinfo",
                        lambda *a, **k: None)
    t._prefix_var.set("IC")
    t._name_var.set("Ampli")
    t._brochage = [("GND", "B", 0), ("VCC", "T", 0), ("IN", "L", 0)]
    t._sauvegarder()
    monkeypatch.setattr("circuit_analyzer.composant.chemin_bibliotheque",
                        lambda: chemin)
    from circuit_analyzer.saisie import Saisie
    assert Saisie()._broches_du_type("IC") == ["GND", "VCC", "IN"]
```

> **Note d'exécution :** vérifier le nom réel de la classe de `saisie.py` (le
> plan suppose `Saisie`) et le point d'injection de `chemin_bibliotheque` — si
> `charger_bibliotheque` est appelée à l'import, patcher plutôt cette dernière.
> Ne pas changer l'intention du test : l'ordre doit être préservé.

- [ ] **Step 2 : vérifier l'échec**

- [ ] **Step 3 : implémenter**

1. `__init__` : `self._pin_lignes` → `self._brochage: list = []`.
2. `_build` : remplacer la carte « Broches » (lignes + boutons Ajouter/Retirer,
   l. 113-130) par
   `self._canvas_broches = PinCanvas(form, on_change=self._sur_brochage)`,
   suivi de `ligne_aide(...)` décrivant les gestes.
   ```python
   def _sur_brochage(self, brochage):
       """@brief Le canevas a muté : la liste ordonnée devient l'état du form."""
       self._brochage = list(brochage)
   ```
3. `_remplir_formulaire(prefixe, nom, broches, brochage=None, lecture_seule=False)` :
   ```python
       if brochage:
           # L'ORDRE vient de `pins` ; les positions de `brochage`.
           self._brochage = [(b, *brochage[b]) for b in broches if b in brochage]
       else:
           self._brochage = _amorcer(broches)   # projection sur les bords
       self._canvas_broches.charger(self._brochage, lecture_seule)
   ```
   avec, au niveau module :
   ```python
   def _amorcer(broches: list) -> list:
       """@brief Projette la géométrie historique (moitié G / moitié D) sur les
       bords, pour qu'un type créé AVANT le brochage positionné ne perde
       aucune broche à la réouverture."""
       from gui.schematic_editor import _auto_def
       from gui.schematic_symbols import aimanter_bord
       d = _auto_def("", list(broches))
       return [(b, *aimanter_bord(*d["pins"][b], d["w"], d["h"], 20))
               for b in broches]
   ```
4. `_afficher_perso` : `self._remplir_formulaire(key, v.get("name", ""),
   v.get("pins", []), v.get("brochage"))`.
5. `_afficher_integre` : `..., v["pins"], None, lecture_seule=True)`.
6. `_afficher_nouveau` : `self._remplir_formulaire('', '', [])` (canevas vide).
7. `_etat_courant` : troisième membre = `tuple(self._brochage)`.
8. `_dupliquer` : `broches = [n for n, _, _ in self._brochage]` puis
   `self._remplir_formulaire('', f"{nom} (copie)", broches,
   {n: [c, d] for n, c, d in self._brochage})`.
9. `_sauvegarder` :
   ```python
       pins = [n for n, _c, _d in self._brochage if n.strip()]
       ...
       self._custom[prefix] = {"name": name, "pins": pins,
                               "brochage": {n: [c, d]
                                            for n, c, d in self._brochage}}
   ```
10. **Supprimer** `_ajouter_broche` et `_retirer_broche`, et les attributs
    `_pins_inner`, `_btn_add_pin`, `_btn_del_pin`.

- [ ] **Step 4 : vérifier le vert + contrôle greppable**

```bash
PYTHONUTF8=1 python -m pytest tests/test_tab_components.py tests/test_pin_canvas.py \
  tests/test_schematic_editor.py -q
grep -rn "_pin_lignes" gui/          # doit ne RIEN rendre
```

- [ ] **Step 5 : commit**

```bash
git add gui/tab_components.py tests/test_tab_components.py
git commit -m "feat(composants): l'onglet passe au canevas de brochage (liste ordonnee)"
```

---

### Task 6 : Suite complète + boucle visuelle

- [ ] **Step 1 :** `PYTHONUTF8=1 python -m pytest -q` → **0 failed**
  (référence : 1846 passed / 50 skipped avant ce chantier).
- [ ] **Step 2 : boucle visuelle** — script scratch **hors dépôt**, 3 PNG
  **réellement inspectés et décrits** :
  1. l'onglet Composants avec un type broché sur les 4 bords (canevas + bandeau
     d'ordre lisibles, aucun chevauchement) ;
  2. **le même type posé dans l'éditeur** — il doit y apparaître avec le
     brochage choisi, **pas** la répartition moitié/moitié : c'est la preuve que
     la chaîne onglet → JSON → `_auto_def` → canevas tient de bout en bout ;
  3. un type existant **sans** `brochage`, inchangé (non-régression).
- [ ] **Step 3 :** supprimer PNG et scripts (jamais committés).
- [ ] **Step 4 :** vérifier que `component_library.json` **n'est pas** dans le
  diff (`git status`), puis `superpowers:finishing-a-development-branch`.

---

## Vérification (bout en bout)

1. **Tests** : suite complète verte, dont `test_pin_canvas.py` et
   `test_tab_components.py` (nouveaux), sans modifier les assertions des suites
   existantes.
2. **Greppable** : `grep -rn "_pin_lignes" gui/` ne rend rien.
3. **Isolation** : `git status` ne montre aucune modification de
   `component_library.json` imputable aux tests.
4. **À la main** : onglet Composants → Nouveau → préfixe `IC`, nom `Ampli` →
   clics sur les 4 bords → double-clic pour renommer en `VCC`/`GND` → glisser
   une pastille du bandeau pour réordonner → Sauvegarder → aller dans l'éditeur,
   poser le type : **les broches sont là où tu les as mises**.
5. **Preuve visuelle** : les 3 PNG de la Task 6, inspectés et décrits.
