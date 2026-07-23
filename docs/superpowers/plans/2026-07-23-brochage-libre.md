# Brochage libre par instance — Plan d'implémentation

> **Pour l'exécutant :** recopier ce plan dans
> `docs/superpowers/plans/2026-07-23-brochage-libre.md` au démarrage (le mode
> plan n'autorise qu'un seul fichier en écriture). Exécution via
> `superpowers:subagent-driven-development` ou `superpowers:executing-plans`.

**Spec de référence :** `docs/superpowers/specs/2026-07-23-brochage-libre-design.md` (commit `b628b50`).

## Context

Poser un composant dans l'éditeur de schéma (`gui/schematic_editor.py`) n'offre
**aucune liberté sur les broches** : soit une géométrie figée écrite en dur
(`COMP_DEFS`, l. 29), soit `_auto_def` (l. 68) qui répartit mécaniquement les
broches moitié à gauche / moitié à droite, pas de 30 px. Les seuls choix à la
pose sont la position et la rotation.

Or les vraies cartes ERetroDesign sont pleines de connecteurs et d'ICs dont le
brochage physique ne ressemble pas à un partage gauche/droite. Le boss veut
poser une boîte et **dire où sont les broches**, à la souris.

**Résultat visé :** chaque composant **posé** peut avoir son propre brochage —
défini au clic sur les bords de sa boîte, aimanté à la grille, numéroté
automatiquement et renommable. Par instance uniquement : aucune écriture dans
la bibliothèque, pas de « sauver comme type » (v1).

**Goal :** un brochage libre par instance, éditable à la souris, qui se dessine,
se câble, s'exporte, s'annule et se sauvegarde correctement.

**Architecture :** un champ optionnel `pinout` sur `CompInst` (nom → `(côté,
décalage)`), résolu en géométrie absolue par un accesseur unique `_geom(comp)`
qui remplace les 15 lectures directes de `self._defs[comp.comp_type]`. Le
stockage sur `CompInst` rend l'annulation gratuite (`_snapshot`, l. 210,
deep-copie déjà `_comps`). Le rendu passe par un traceur dédié via un type de
rendu substitué, sans toucher le dispatch existant.

**Tech Stack :** Python 3.11, Tkinter/customtkinter, pytest. Aucune nouvelle
dépendance.

## Global Constraints

- Commits en **français**, **jamais** de footer `Co-Authored-By: Claude` ni
  `Generated with Claude Code`.
- **Jamais `git add -A`** : fichiers ajoutés un par un.
- **Ne jamais committer** `custom_circuits.json` ni `component_library.json`
  (règle perso du boss, gardée telle quelle).
- `docs.rar`, `SolutionERetroDesignX20260813/` et `CARTE POUR TESTER (VRAI
  TEST)/` : lecture seule, jamais committés.
- `PYTHONUTF8=1` sur toutes les commandes pytest.
- `schemdraw==0.22` pinné (0.23 casse ~30 tests de rendu).
- Canvas des schémas **clair** ; le chrome suit `theme.py` (jamais de hex en dur).
- Flake connu : `test_500_portes_sous_budget` → relancer isolé si rouge.
- Branche `rewrite-simple` ; rien n'est poussé sans accord explicite.

## Structure des fichiers

| Fichier | Responsabilité ajoutée |
|---|---|
| `gui/schematic_symbols.py` | Fonctions **pures** de géométrie (`geometrie_libre`, `aimanter_bord`) + traceur `_tr_boite_libre`. Testables sans Tk. |
| `gui/schematic_editor.py` | Champ `pinout`, résolveur `_geom` + cache, type `"X"`, mode `pinedit`, duplication. |
| `gui/schematic_io.py` | Sérialisation de `pinout` ; `_pin_monde` / `points_jonction` prennent un résolveur. |
| `tests/test_schematic_symbols.py` | Tests des fonctions pures (T1). |
| `tests/test_brochage_libre.py` | **Créé** — résolveur, rendu, mode `pinedit`, persistance (T2→T7). |

---

### Task 1 : Géométrie libre — fonctions pures

**Files:**
- Modify: `gui/schematic_symbols.py` (après `def_puce`, ~l. 238)
- Test: `tests/test_schematic_symbols.py`

**Interfaces produites :**
- `geometrie_libre(pinout: dict[str, tuple[str, int]]) -> dict` → `{"label",
  "color", "w", "h", "pins": {nom: (dx, dy)}, "cotes": {nom: côté},
  "default_value"}`
- `aimanter_bord(dx: float, dy: float, w: int, h: int, pas: int) -> tuple[str, int]`
- Constantes `BOITE_MIN_W = 80`, `BOITE_MIN_H = 60`, `BOITE_MARGE = 20`

- [ ] **Step 1 : écrire les tests qui échouent** — `tests/test_schematic_symbols.py`

```python
from gui.schematic_symbols import geometrie_libre, aimanter_bord


def test_boite_vide_a_la_taille_minimale():
    d = geometrie_libre({})
    assert d["pins"] == {}
    assert (d["w"], d["h"]) == (80, 60)


def test_cotes_vers_offsets_absolus():
    d = geometrie_libre({"1": ("L", -20), "2": ("R", 20), "3": ("T", 0)})
    w2, h2 = d["w"] // 2, d["h"] // 2
    assert d["pins"]["1"] == (-w2, -20)     # bord gauche : le décalage est un y
    assert d["pins"]["2"] == (w2, 20)
    assert d["pins"]["3"] == (0, -h2)       # bord haut : le décalage est un x
    assert d["cotes"]["3"] == "T"


def test_boite_s_agrandit_pour_contenir_les_broches():
    d = geometrie_libre({"1": ("L", -100)})
    assert d["h"] >= 220                    # 2*100 + marge
    assert d["pins"]["1"] == (-d["w"] // 2, -100)


def test_aimantation_choisit_le_bord_le_plus_proche():
    assert aimanter_bord(-38, 7, 80, 60, 20) == ("L", 0)
    assert aimanter_bord(38, -13, 80, 60, 20) == ("R", -20)
    assert aimanter_bord(11, -29, 80, 60, 20) == ("T", 20)


def test_aimantation_au_coin_les_bords_horizontaux_gagnent():
    # coin haut-gauche exact : distance nulle aux deux bords -> T
    assert aimanter_bord(-40, -30, 80, 60, 20)[0] == "T"
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_schematic_symbols.py -q`
Attendu : `ImportError: cannot import name 'geometrie_libre'`

- [ ] **Step 3 : implémenter** — dans `gui/schematic_symbols.py`, après `def_puce`

```python
BOITE_MIN_W = 80
BOITE_MIN_H = 60
BOITE_MARGE = 20


def geometrie_libre(pinout):
    """@brief Def d'une boîte au brochage libre (spec 2026-07-23).

    @param pinout {nom: (côté 'L'/'R'/'T'/'B', décalage signé sur ce bord)}.
    @return def compatible COMP_DEFS, taille AUTO-AJUSTÉE pour contenir les
            broches — on ne peut jamais manquer de bord, d'où l'absence de
            poignée de redimensionnement.
    """
    lat = [abs(d) for c, d in pinout.values() if c in ("L", "R")]
    ver = [abs(d) for c, d in pinout.values() if c in ("T", "B")]
    h = max(BOITE_MIN_H, 2 * max(lat, default=0) + BOITE_MARGE)
    w = max(BOITE_MIN_W, 2 * max(ver, default=0) + BOITE_MARGE)
    w2, h2 = w // 2, h // 2
    pins, cotes = {}, {}
    for nom, (cote, dec) in pinout.items():
        pins[nom] = {"L": (-w2, dec), "R": (w2, dec),
                     "T": (dec, -h2), "B": (dec, h2)}[cote]
        cotes[nom] = cote
    return {"label": "", "color": AUTO_COLOR, "w": w, "h": h,
            "pins": pins, "cotes": cotes, "default_value": ""}


def aimanter_bord(dx, dy, w, h, pas):
    """@brief (dx,dy) relatif au centre -> (côté, décalage aligné sur `pas`).

    Bord dont la distance perpendiculaire est la plus faible. À ÉGALITÉ (coin),
    les bords HORIZONTAUX gagnent : arbitraire, mais déterministe donc testable.
    """
    w2, h2 = w / 2, h / 2
    d = {"L": abs(dx + w2), "R": abs(dx - w2),
         "T": abs(dy + h2), "B": abs(dy - h2)}
    m = min(d.values())
    for cote in ("T", "B", "L", "R"):          # cet ordre = arbitrage du coin
        if d[cote] == m:
            long_ = dx if cote in ("T", "B") else dy
            return (cote, int(round(long_ / pas) * pas))
```

**Couleur :** `_AUTO_COLOR` vit aujourd'hui dans `schematic_editor.py`. La
**déplacer** dans `schematic_symbols.py` sous le nom `AUTO_COLOR` et l'importer
côté éditeur (`from gui.schematic_symbols import … AUTO_COLOR as _AUTO_COLOR`)
— une seule source, aucun hex dupliqué.

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_schematic_symbols.py -q` → PASS

- [ ] **Step 5 : commit**

```bash
git add gui/schematic_symbols.py gui/schematic_editor.py tests/test_schematic_symbols.py
git commit -m "feat(editeur): geometrie de brochage libre (cote+decalage -> offsets, aimantation bord)"
```

---

### Task 2 : Le résolveur `_geom` (bascule des 15 sites)

Refactor **pur** : rien ne change tant que `pinout is None`. Doit être
**atomique** — un site oublié = fil qui pointe à côté.

**Files:**
- Modify: `gui/schematic_editor.py` (dataclass `CompInst` + ~15 sites)
- Modify: `gui/schematic_io.py:65` `_pin_monde`, `:72` `points_jonction`
- Test: `tests/test_brochage_libre.py` (créé)

**Interfaces produites :**
- `CompInst.pinout: Optional[dict[str, tuple[str, int]]] = None`
- `SchematicEditor._geom(comp) -> dict`
- `SchematicEditor._invalider_geom(comp_id=None)`
- `_pin_monde(comp, pin, geom)` / `points_jonction(comps, wires, geom)` où
  `geom` est un **callable** `(comp) -> dict`

- [ ] **Step 1 : tests qui échouent** — `tests/test_brochage_libre.py`

```python
"""@file test_brochage_libre.py
@brief Brochage libre par instance (spec 2026-07-23). Tk -> skip sans display.
"""
import pytest

ctk = pytest.importorskip("customtkinter")
from gui.schematic_editor import SchematicEditor        # noqa: E402


@pytest.fixture
def editeur():
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("pas de display Tk")
    root.withdraw()
    ed = SchematicEditor(root)
    ed.pack()
    root.update_idletasks()
    yield ed
    root.destroy()


def _place(ed, t, cx, cy):
    ed._place_type, ed._state = t, "placing"
    return ed._place_at(cx, cy)


def test_geom_sans_pinout_rend_la_def_du_type(editeur):
    c = _place(editeur, "R", 200, 200)
    assert editeur._geom(c) is editeur._defs["R"]


def test_geom_avec_pinout_ignore_la_def_du_type(editeur):
    c = _place(editeur, "R", 200, 200)
    c.pinout = {"A": ("L", 0), "B": ("R", 0), "C": ("T", 0)}
    editeur._invalider_geom()
    assert set(editeur._geom(c)["pins"]) == {"A", "B", "C"}


def test_hit_test_trouve_une_broche_libre(editeur):
    c = _place(editeur, "R", 200, 200)
    c.pinout = {"VCC": ("T", 0)}
    editeur._invalider_geom()
    editeur._redraw_all()
    dx, dy = editeur._geom(c)["pins"]["VCC"]
    assert editeur._find_pin_at(200 + dx, 200 + dy) == (c.id, "VCC")


def test_export_utilise_les_broches_libres_sans_polluer_la_valeur(editeur):
    c = _place(editeur, "R", 200, 200)
    c.pinout = {"1": ("L", 0), "2": ("R", 0), "3": ("B", 0)}
    editeur._invalider_geom()
    comp = next(x for x in editeur.exporter_composants() if x.ref == c.ref)
    assert set(comp.pins) == {"1", "2", "3"}
    assert comp.type == "R"
```

- [ ] **Step 2 : vérifier l'échec** — `AttributeError: … '_geom'`

- [ ] **Step 3 : implémenter**

1. `CompInst` : ajouter `pinout: Optional[dict] = None` après `rotation`.
2. Initialiser `self._geom_cache: dict[int, dict] = {}` dans `__init__`, à côté
   de `self._defs` (l. 204).
3. Ajouter le résolveur :

```python
    def _geom(self, comp: "CompInst") -> dict:
        """@brief Géométrie EFFECTIVE : brochage d'instance sinon def du type.

        Mémoïsé : `_find_pin_at` balaye tous les composants à chaque mouvement
        de souris. Invalidé par `_invalider_geom` (édition de broche, undo/redo,
        chargement, suppression) — un cache périmé donne des fils qui pointent
        à côté, symptôme pénible à diagnostiquer.
        """
        if comp.pinout is None:
            return self._defs[comp.comp_type]
        d = self._geom_cache.get(comp.id)
        if d is None:
            d = geometrie_libre(comp.pinout)
            base = self._defs.get(comp.comp_type)
            if base:
                d["color"] = base["color"]
            self._geom_cache[comp.id] = d
        return d

    def _invalider_geom(self, comp_id: int = None):
        """@brief Purge le cache de géométrie (tout, ou un seul composant)."""
        if comp_id is None:
            self._geom_cache.clear()
        else:
            self._geom_cache.pop(comp_id, None)
```

4. **Basculer les 15 sites** `self._defs[X.comp_type]` → `self._geom(X)` :
   `_draw_comp` (659, 719-724), `_draw_wire` (746, 748), `_redraw_jonctions`
   (777), `_find_pin_at` (802), `_find_comp_at` (811), `_find_wire_at` (827,
   829), `fit_to_view` (1077), câblage (1119, 1128), redessin (1195),
   `load_dict` (1399, 1401), `to_netlist` (1476), `exporter_composants` (1505),
   `unconnected_pins` (1528).

   **Ne PAS toucher** (gestion de *types*, pas d'instances) : l. 636
   (`_place_at` lit la def du type avant que le composant existe), 345, 455,
   464, 582-604, 1007, 1384.

5. Invalidation : `_restore` (l. 227) et `load_dict` → `self._invalider_geom()` ;
   `_delete_comp` → `self._invalider_geom(comp_id)`.
6. `gui/schematic_io.py` : `_pin_monde(comp, pin, geom)` et
   `points_jonction(comps, wires, geom)` prennent un **callable**
   (`geom(comp)["pins"][pin]`). Mettre à jour l'appel l. 777 en
   `points_jonction(self._comps, self._wires, self._geom)` et les tests de
   `tests/test_schematic_io.py` qui les appellent directement.
   `build_from_components(composants, defs)` (l. 96) est **hors périmètre** :
   il part de `Composant` analysés et garde son dict indexé par type.

- [ ] **Step 4 : vérifier le vert + la NON-RÉGRESSION**

```bash
PYTHONUTF8=1 python -m pytest tests/test_brochage_libre.py tests/test_schematic_editor.py \
  tests/test_editor_edition.py tests/test_schematic_io.py -q
```
Attendu : tout vert. Puis `grep -n '_defs\[.*comp_type\]' gui/schematic_editor.py`
ne doit laisser que les sites « gestion de types » du point 4.

- [ ] **Step 5 : commit**

```bash
git add gui/schematic_editor.py gui/schematic_io.py tests/test_brochage_libre.py tests/test_schematic_io.py
git commit -m "refactor(editeur): resolveur _geom, geometrie par instance possible"
```

---

### Task 3 : Rendu — un brochage libre se dessine en boîte

**Files:**
- Modify: `gui/schematic_symbols.py` (traceur + dispatch `primitives`)
- Modify: `gui/schematic_editor.py:658-739` (`_draw_comp`)
- Test: `tests/test_brochage_libre.py`

**Interfaces produites :** `TYPE_LIBRE = "__libre__"` (exporté par
`schematic_symbols`).

**Pourquoi un traceur dédié :** `_tr_boite` (l. 185) décide le côté avec
`bord = corps if px > 0 else -corps` — purement horizontal, il ne sait pas
dessiner une broche en haut/bas. L'étendre risquerait de casser le rendu DIP
des puces catalogue (chantier ERetroDesign). Et le dispatch de `primitives()`
se fait par `comp_type` : passer `TYPE_LIBRE` route vers le nouveau traceur, et
`est_boite_generique(TYPE_LIBRE)` renvoie déjà `True` (ni `"D"` ni dans
`_TRACEURS`) — donc `_draw_comp` n'ajoutera pas un second libellé par-dessus.
**Aucune modification du dispatch existant.**

- [ ] **Step 1 : tests qui échouent**

```python
def test_resistance_rebrochee_devient_une_boite(editeur):
    c = _place(editeur, "R", 200, 200)
    c.pinout = {"1": ("L", 0), "2": ("R", 0)}
    editeur._invalider_geom()
    editeur._redraw_all()
    items = editeur._canvas.find_withtag(f"comp_{c.id}")
    lignes = [i for i in items if editeur._canvas.type(i) == "line"]
    assert not any(len(editeur._canvas.coords(i)) >= 16 for i in lignes)  # zigzag parti
    assert any(editeur._canvas.type(i) == "polygon" for i in items)       # boîte


def test_resistance_intacte_garde_son_zigzag(editeur):
    c = _place(editeur, "R", 200, 200)
    items = editeur._canvas.find_withtag(f"comp_{c.id}")
    lignes = [i for i in items if editeur._canvas.type(i) == "line"]
    assert any(len(editeur._canvas.coords(i)) >= 16 for i in lignes)


def test_broche_du_haut_est_dessinee(editeur):
    c = _place(editeur, "R", 200, 200)
    c.pinout = {"VCC": ("T", 0)}
    editeur._invalider_geom()
    editeur._redraw_all()
    assert editeur._canvas.find_withtag(f"pin_{c.id}_VCC")
```

- [ ] **Step 2 : vérifier l'échec** (le zigzag est encore dessiné)

- [ ] **Step 3 : implémenter** — dans `gui/schematic_symbols.py`

```python
TYPE_LIBRE = "__libre__"   # type de RENDU d'un composant au brochage libre


def _tr_boite_libre(defn):
    """@brief Boîte au brochage libre : broches sur les 4 bords (spec 2026-07-23).

    `_tr_boite` ne sait placer que des broches gauche/droite (test `px > 0`),
    d'où ce traceur séparé, qui lit `defn["cotes"]` et oriente le libellé.
    """
    w2, h2 = defn["w"] // 2, defn["h"] // 2
    prims = [("polygon", [(-w2, -h2), (w2, -h2), (w2, h2), (-w2, h2)], False)]
    for pn, (px, py) in defn["pins"].items():
        cote = (defn.get("cotes") or {}).get(pn, "L")
        if cote in ("L", "R"):
            ancre = "w" if cote == "L" else "e"
            tx, ty = px + (6 if cote == "L" else -6), py
        else:
            ancre = "center"
            tx, ty = px, py + (10 if cote == "T" else -10)
        prims.append(("text", (tx, ty), pn, 7, ancre))
    return prims
```

Dans `primitives()` (l. 229), **avant** le test `comp_type == "D"` :

```python
    if comp_type == TYPE_LIBRE:
        prims = _tr_boite_libre(defn)
    elif comp_type == "D":
        ...
```

Dans `_draw_comp` (l. 658-670 et 723), substituer le type de rendu :

```python
        defn = self._geom(comp)
        # Brochage libre -> boîte honnête : le symbole d'origine (zigzag…) est
        # dessiné POUR ses broches d'origine, il mentirait une fois rebroché.
        t_rendu = TYPE_LIBRE if comp.pinout is not None else comp.comp_type
        ...
        prims = primitives(t_rendu, defn, rot, comp.value)
        ...
        boite = est_boite_generique(t_rendu)
```

- [ ] **Step 4 : vérifier le vert** (`test_brochage_libre.py`,
  `test_schematic_symbols.py`, `test_schematic_editor.py`)
- [ ] **Step 5 : commit**

```bash
git add gui/schematic_symbols.py gui/schematic_editor.py tests/test_brochage_libre.py
git commit -m "feat(editeur): un composant au brochage libre se rend en boite honnete"
```

---

### Task 4 : Boîte vierge en palette (type `"X"`)

**Files:**
- Modify: `gui/schematic_editor.py:29` (`COMP_DEFS`), `:626` (`_place_at`)
- Test: `tests/test_brochage_libre.py`

`"X"` est libre (types actuels : C, D, F, GND, K, L, M, Q, R, SW, T, U, VCC) et
c'est déjà la convention maison de la boîte noire côté import ERetroDesign :
les réfs se numérotent `X1`, `X2`… et l'export donne `Composant(type="X")`, que
l'analyseur sait traiter. Le bouton de palette apparaît **automatiquement**
(`_build_palette`, l. 345, itère `self._defs`).

- [ ] **Step 1 : tests qui échouent**

```python
def test_boite_vierge_posee_sans_broche(editeur):
    c = _place(editeur, "X", 200, 200)
    assert c.ref == "X1"
    assert c.pinout == {}
    assert editeur._geom(c)["pins"] == {}


def test_boite_vierge_a_un_bouton_de_palette(editeur):
    assert "X" in editeur._palette_btns
```

- [ ] **Step 2 : vérifier l'échec** — `KeyError: 'X'`

- [ ] **Step 3 : implémenter**

Étendre l'import de `gui.schematic_symbols` (l. 16) avec `BOITE_MIN_W`,
`BOITE_MIN_H` — `COMP_DEFS` est défini l. 29, après les imports. Puis :

```python
    "X": {"label": "Boîte", "color": _AUTO_COLOR, "w": BOITE_MIN_W,
          "h": BOITE_MIN_H, "pins": {}, "default_value": ""},
```

Dans `_place_at` (l. 626), juste après la création de `comp` :

```python
        if t == "X":
            comp.pinout = {}      # boîte vierge : brochage libre, zéro broche
```

- [ ] **Step 4 : vérifier le vert**
- [ ] **Step 5 : commit**

```bash
git add gui/schematic_editor.py tests/test_brochage_libre.py
git commit -m "feat(editeur): boite vierge en palette (type X, zero broche)"
```

---

### Task 5 : Mode `pinedit` — entrée, amorçage paresseux, ajout de broche

**Files:**
- Modify: `gui/schematic_editor.py` (`_on_right_click` l. 947, `_on_click`
  l. 842, `_on_escape` l. 976)
- Test: `tests/test_brochage_libre.py`

**Interfaces produites :**
- `_entrer_pinedit(comp_id)` / `_quitter_pinedit()`
- `_amorcer_pinout(comp) -> dict`
- `_ajouter_broche(comp, wx, wy) -> str` (nom attribué)
- `_nom_broche_libre(pinout) -> str`
- État `self._state == "pinedit"`, `self._pinedit_id`

- [ ] **Step 1 : tests qui échouent**

```python
def test_entrer_et_sortir_sans_toucher_ne_change_rien(editeur):
    c = _place(editeur, "R", 200, 200)
    editeur._entrer_pinedit(c.id)
    editeur._quitter_pinedit()
    assert c.pinout is None            # amorçage PARESSEUX
    assert editeur._state == "idle"


def test_premiere_mutation_amorce_sans_bouger_les_broches(editeur):
    c = _place(editeur, "R", 200, 200)
    avant = dict(editeur._geom(c)["pins"])
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200, 200 - 40)
    assert c.pinout is not None
    for pn, xy in avant.items():
        assert editeur._geom(c)["pins"][pn] == xy


def test_broches_numerotees_automatiquement(editeur):
    c = _place(editeur, "X", 200, 200)
    editeur._entrer_pinedit(c.id)
    assert editeur._ajouter_broche(c, 200 - 40, 200) == "1"
    assert editeur._ajouter_broche(c, 200 - 40, 200 + 20) == "2"


def test_nom_reutilise_le_plus_petit_entier_libre(editeur):
    c = _place(editeur, "X", 200, 200)
    editeur._entrer_pinedit(c.id)
    for dy in (-20, 0, 20):
        editeur._ajouter_broche(c, 200 - 40, 200 + dy)
    del c.pinout["2"]
    editeur._invalider_geom(c.id)
    assert editeur._ajouter_broche(c, 200 - 40, 200) == "2"


def test_ajout_de_broche_est_annulable(editeur):
    c = _place(editeur, "X", 200, 200)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    editeur._undo()
    assert editeur._comps[c.id].pinout == {}
```

- [ ] **Step 2 : vérifier l'échec**

- [ ] **Step 3 : implémenter**

```python
    def _nom_broche_libre(self, pinout) -> str:
        """@brief Plus petit entier >= 1 non utilisé (une suppression se recycle)."""
        n = 1
        while str(n) in pinout:
            n += 1
        return str(n)

    def _amorcer_pinout(self, comp) -> dict:
        """@brief Projette les broches du TYPE sur les bords -> (côté, décalage).

        PARESSEUX : appelé à la première mutation seulement. Sinon, comme
        `pinout is not None` déclenche le rendu en boîte (Task 3), ouvrir
        l'éditeur puis faire Échap transformerait le symbole sans qu'on ait
        rien touché.
        """
        d = self._defs[comp.comp_type]
        return {pn: aimanter_bord(dx, dy, d["w"], d["h"], GRID)
                for pn, (dx, dy) in d["pins"].items()}

    def _ajouter_broche(self, comp, wx, wy) -> str:
        """@brief Ajoute une broche aimantée au bord le plus proche du clic."""
        self._push_undo()
        if comp.pinout is None:
            comp.pinout = self._amorcer_pinout(comp)
        d = self._geom(comp)
        nom = self._nom_broche_libre(comp.pinout)
        comp.pinout[nom] = aimanter_bord(wx - comp.cx, wy - comp.cy,
                                         d["w"], d["h"], GRID)
        self._invalider_geom(comp.id)
        self._draw_comp(comp)
        return nom
```

`_entrer_pinedit(comp_id)` : `self._cancel_wiring()`, `self._state =
"pinedit"`, `self._pinedit_id = comp_id`, contour pointillé sur la boîte,
statut « Clic bord = broche / Double-clic = renommer / Suppr = retirer / Échap
= fin ». `_quitter_pinedit()` : repasse en `"idle"`, efface le contour, remet
`_pinedit_id = None`.

Câblage UI : entrée « ⊹ Éditer broches » dans `_on_right_click` après
« ↻ Rotation » (l. 968) ; dans `_on_click`, si `self._state == "pinedit"`,
router vers `_ajouter_broche` (ou le glissé) au lieu du comportement normal ;
dans `_on_escape` (l. 976), traiter le cas `"pinedit"`.

- [ ] **Step 4 : vérifier le vert**
- [ ] **Step 5 : commit**

```bash
git add gui/schematic_editor.py tests/test_brochage_libre.py
git commit -m "feat(editeur): mode edition de broches, ajout aimante et numerote"
```

---

### Task 6 : Glisser, renommer, supprimer une broche

**Files:**
- Modify: `gui/schematic_editor.py` (`_on_b1_motion` l. 882, `_on_b1_release`
  l. 905, `_on_double_click` l. 941, `_on_delete` l. 973)
- Test: `tests/test_brochage_libre.py`

**Interfaces produites :**
- `_deplacer_broche(comp, nom, wx, wy)`
- `_renommer_broche(comp, ancien, nouveau) -> bool` (False si vide/doublon)
- `_supprimer_broche(comp, nom)` — supprime **aussi** les fils rattachés

- [ ] **Step 1 : tests qui échouent**

```python
def test_glisser_une_broche_l_aimante_a_la_grille(editeur):
    c = _place(editeur, "X", 200, 200)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    editeur._deplacer_broche(c, "1", 200 - 40, 200 + 27)
    cote, dec = c.pinout["1"]
    assert cote == "L" and dec % 20 == 0


def test_glisser_au_dela_du_coin_agrandit_la_boite(editeur):
    c = _place(editeur, "X", 200, 200)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    h_avant = editeur._geom(c)["h"]
    editeur._deplacer_broche(c, "1", 200 - 40, 200 + 200)
    assert editeur._geom(c)["h"] > h_avant


def test_renommage_refuse_vide_et_doublon(editeur):
    c = _place(editeur, "X", 200, 200)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    editeur._ajouter_broche(c, 200 + 40, 200)
    assert editeur._renommer_broche(c, "1", "VCC") is True
    assert "VCC" in c.pinout and "1" not in c.pinout
    assert editeur._renommer_broche(c, "2", "VCC") is False
    assert editeur._renommer_broche(c, "2", "") is False
    assert "2" in c.pinout


def test_renommage_suit_les_fils(editeur):
    c = _place(editeur, "X", 200, 200)
    g = _place(editeur, "GND", 300, 300)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    editeur._quitter_pinedit()
    editeur._add_wire(c.id, "1", g.id, next(iter(editeur._geom(g)["pins"])))
    editeur._renommer_broche(c, "1", "OUT")
    assert editeur._wires[0].from_pin == "OUT"


def test_supprimer_une_broche_supprime_ses_fils(editeur):
    c = _place(editeur, "X", 200, 200)
    g = _place(editeur, "GND", 300, 300)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    editeur._quitter_pinedit()
    editeur._add_wire(c.id, "1", g.id, next(iter(editeur._geom(g)["pins"])))
    editeur._supprimer_broche(c, "1")
    assert "1" not in c.pinout
    assert editeur._wires == []          # aucun fil orphelin
```

Signature vérifiée : `_add_wire(from_id, from_pin, to_id, to_pin)`
(schematic_editor l. 1147) — il empile son propre undo et renvoie `None` sur
doublon.

- [ ] **Step 2 : vérifier l'échec**

- [ ] **Step 3 : implémenter**

```python
    def _deplacer_broche(self, comp, nom, wx, wy):
        """@brief Fait coulisser une broche ; aimantation bord + grille au relâché."""
        self._push_undo()
        d = self._geom(comp)
        comp.pinout[nom] = aimanter_bord(wx - comp.cx, wy - comp.cy,
                                         d["w"], d["h"], GRID)
        self._invalider_geom(comp.id)
        self._draw_comp(comp)
        self._redraw_wires_of(comp.id)

    def _renommer_broche(self, comp, ancien, nouveau) -> bool:
        """@brief Renomme une broche ET les fils qui la référencent (par NOM).

        @return False si le nom est vide ou déjà pris (refus signalé au statut).
        """
        nouveau = (nouveau or "").strip()
        if not nouveau or nouveau in comp.pinout:
            self._set_status("Nom vide ou\ndéjà utilisé")
            return False
        self._push_undo()
        comp.pinout[nouveau] = comp.pinout.pop(ancien)
        for w in self._wires:                   # les fils référencent par NOM
            if w.from_comp_id == comp.id and w.from_pin == ancien:
                w.from_pin = nouveau
            if w.to_comp_id == comp.id and w.to_pin == ancien:
                w.to_pin = nouveau
        self._invalider_geom(comp.id)
        self._draw_comp(comp)
        return True

    def _supprimer_broche(self, comp, nom):
        """@brief Retire une broche ET les fils rattachés (sinon fils orphelins)."""
        self._push_undo()
        comp.pinout.pop(nom, None)
        self._wires = [w for w in self._wires
                       if not ((w.from_comp_id == comp.id and w.from_pin == nom)
                               or (w.to_comp_id == comp.id and w.to_pin == nom))]
        self._invalider_geom(comp.id)
        self._redraw_all()
```

Câblage UI : en `pinedit`, `_on_b1_motion` / `_on_b1_release` glissent la broche
sous le curseur ; `_on_double_click` ouvre `simpledialog.askstring` puis appelle
`_renommer_broche` ; `_on_delete` supprime la broche sélectionnée. Ces méthodes
empilent déjà leur undo — **ne pas doubler** côté handler.

- [ ] **Step 4 : vérifier le vert**
- [ ] **Step 5 : commit**

```bash
git add gui/schematic_editor.py tests/test_brochage_libre.py
git commit -m "feat(editeur): glisser, renommer et supprimer une broche libre"
```

---

### Task 7 : Duplication et persistance `.circ`

**Files:**
- Modify: `gui/schematic_editor.py` (`_add_comp` l. 997, `_copy` l. 1024,
  `_paste` l. 1033, `_duplicate` l. 1047, `load_dict` l. 1381)
- Modify: `gui/schematic_io.py:34-41` (`editor_to_dict`)
- Test: `tests/test_brochage_libre.py`

Version `.circ` **inchangée (1)** : `load_dict` (l. 1373) rejette tout ce qui
n'est pas version 1 — bumper rendrait illisibles les schémas existants. Champ
additif : absent ⇒ `pinout=None` ⇒ comportement actuel.

- [ ] **Step 1 : tests qui échouent**

```python
def test_duplication_clone_le_brochage(editeur):
    c = _place(editeur, "X", 200, 200)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    editeur._quitter_pinedit()
    editeur._select(c.id)
    editeur._duplicate()
    copie = [x for x in editeur._comps.values() if x.id != c.id][0]
    copie.pinout["ZZ"] = ("R", 0)
    assert "ZZ" not in c.pinout          # dicts DISTINCTS, pas partagés


def test_round_trip_circ_conserve_brochage_et_fils(editeur):
    c = _place(editeur, "X", 200, 200)
    g = _place(editeur, "GND", 300, 300)
    editeur._entrer_pinedit(c.id)
    editeur._ajouter_broche(c, 200 - 40, 200)
    editeur._quitter_pinedit()
    editeur._add_wire(c.id, "1", g.id, next(iter(editeur._geom(g)["pins"])))
    editeur.load_dict(editeur.to_dict())
    r = next(x for x in editeur._comps.values() if x.comp_type == "X")
    assert r.pinout == {"1": ("L", 0)}
    assert len(editeur._wires) == 1


def test_circ_sans_pinout_se_relit(editeur):
    _place(editeur, "R", 200, 200)
    d = editeur.to_dict()
    for comp in d["components"]:
        comp.pop("pinout", None)
    editeur.load_dict(d)                 # ne doit pas lever
    assert all(c.pinout is None for c in editeur._comps.values())
```

- [ ] **Step 2 : vérifier l'échec**

- [ ] **Step 3 : implémenter**

1. `editor_to_dict` (schematic_io l. 38), dans le dict composant :

```python
             **({"pinout": {n: list(v) for n, v in c.pinout.items()}}
                if c.pinout is not None else {}),
```

2. `load_dict` (l. 1386) :

```python
            po = c.get("pinout")
            ci = CompInst(int(c["id"]), c["ref"], t, c.get("value", ""),
                          int(c["cx"]), int(c["cy"]), int(c.get("rotation", 0)),
                          pinout=({n: tuple(v) for n, v in po.items()}
                                  if po is not None else None))
```

   Le filtre l. 1384 (`if t not in self._defs: continue`) reste tel quel :
   `"X"` est désormais un type intégré, il passe.

3. `_add_comp` (l. 997) : nouveau paramètre `pinout=None`, et
   `CompInst(..., pinout=copy.deepcopy(pinout))`. `_copy` et `_duplicate`
   ajoutent `"pinout": comp.pinout` au `_clipboard` ; `_paste` le repasse à
   `_add_comp`. Le `deepcopy` **dans** `_add_comp` garantit que les deux
   chemins (coller, dupliquer) clonent — « par instance » l'exige.

- [ ] **Step 4 : vérifier le vert** (+ `tests/test_schematic_io.py`)
- [ ] **Step 5 : commit**

```bash
git add gui/schematic_editor.py gui/schematic_io.py tests/test_brochage_libre.py
git commit -m "feat(editeur): brochage libre clone a la duplication et sauve dans le .circ"
```

---

### Task 8 : Suite complète + boucle visuelle (exigence boss)

- [ ] **Step 1 : suite complète**

```bash
PYTHONUTF8=1 python -m pytest -q
```
Attendu : ~1817 passed + les nouveaux, **0 failed**. Si
`test_500_portes_sous_budget` casse, le relancer isolé (flake connu).

- [ ] **Step 2 : boucle visuelle** — script scratch **hors dépôt**
  (scratchpad), 3 cas rendus en PNG et **réellement inspectés puis décrits** :
  1. boîte vierge brochée à la main sur les 4 bords → boîte, libellés lisibles,
     aucun chevauchement, broches du bon côté ;
  2. connecteur multi-broches rebroché → fils orthogonaux corrects ;
  3. schéma existant **non modifié** (résistances, AOP) → **strictement
     identique** à avant (non-régression visuelle).
- [ ] **Step 3 : supprimer PNG et scripts** (jamais committés).
- [ ] **Step 4 : revue** — `superpowers:requesting-code-review` sur la branche,
  puis `superpowers:finishing-a-development-branch`. **Rien n'est poussé sans
  accord explicite du boss.**

---

## Vérification (bout en bout)

1. **Tests** : `PYTHONUTF8=1 python -m pytest -q` — tout vert, dont
   `tests/test_brochage_libre.py` (nouveau) et les suites d'éditeur existantes
   **sans modifier leurs assertions** (seule exception : les appels directs à
   `points_jonction` / `_pin_monde` dans `test_schematic_io.py`, dont la
   signature change en Task 2).
2. **Non-régression greppable** : `grep -n '_defs\[.*comp_type\]'
   gui/schematic_editor.py` ne laisse que les sites « gestion de types »
   (palette, `_ensure_dyn_def`, `_add_comp`, filtre de type de `load_dict`).
3. **À la main dans l'app** : palette « Boîte » → poser → clic sur chaque bord
   (4 broches) → glisser l'une au-delà du coin (la boîte grandit) → double-clic
   → renommer en `VCC` → câbler vers un GND → `Ctrl+Z` ×2 → sauver en `.circ`,
   rouvrir, vérifier broches et fils.
4. **Preuve visuelle** : les 3 PNG de la Task 8, inspectés et décrits.

## Réserve connue

Un composant typé (résistance, AOP…) dont on édite les broches **perd son
symbole** au profit d'une boîte étiquetée (§4 de la spec, validé par le boss le
2026-07-23). Le `comp_type` est conservé : l'export et l'analyse ne changent
pas. L'arbitrage d'aimantation au coin (« bords horizontaux gagnent ») est
arbitraire — isolé dans `aimanter_bord`, donc changeable en une ligne + un test
si le ressenti ne convient pas à l'usage.
