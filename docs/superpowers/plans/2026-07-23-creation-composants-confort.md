# Création de composants : confort et options — Plan d'implémentation

> Exécution via `superpowers:executing-plans`. Étapes en cases à cocher.

**Spec :** `docs/superpowers/specs/2026-07-23-creation-composants-confort-design.md` (`8e1544f`).

**Goal :** poser un boîtier courant en un clic, nommer les broches au clavier
sans modale, leur donner un rôle, et fixer valeur par défaut et taille du type.

**Architecture :** tout le calcul est en **fonctions pures** dans
`gui/schematic_symbols.py` (`modele_brochage`, `geometrie_libre` étendue) ;
`gui/pin_canvas.py` gagne la pose groupée, le champ de nom chaîné et les menus
de rôle ; `gui/tab_components.py` expose les nouveaux champs et transporte trois
clés **additives** (`default_value`, `fonctions`, `boite`) dont deux sont déjà
consommées ailleurs dans le projet.

**Tech Stack :** Python 3.11, Tkinter/customtkinter, pytest. Aucune dépendance neuve.

## Global Constraints

- Commits en **français**, **jamais** de footer `Co-Authored-By: Claude`.
- **Jamais `git add -A`** : fichiers un par un.
- **Ne jamais committer** `component_library.json` ni `custom_circuits.json` ;
  les tests écrivent dans un `tmp_path` (monkeypatch de `chemin_bibliotheque`).
- **Neutraliser `messagebox` dans toute fixture d'onglet** : une modale non
  remplacée GÈLE la suite de tests (piège rencontré au chantier précédent).
- `docs.rar`, `SolutionERetroDesignX20260813/`, `CARTE POUR TESTER (VRAI TEST)/` :
  lecture seule, jamais committés.
- `PYTHONUTF8=1` partout ; `schemdraw==0.22` pinné.
- `gui/schematic_symbols.py` doit rester **pur** (`test_purete_import` :
  aucun import tkinter/customtkinter/matplotlib).
- Chrome via `theme.py`/`ui_kit.py`, jamais de hex en dur.
- Branche `rewrite-simple` ; rien n'est poussé sans accord explicite.

## Structure des fichiers

| Fichier | Ajout |
|---|---|
| `gui/schematic_symbols.py` | `modele_brochage` ; `geometrie_libre(+w_mini,+h_mini)` ; largeur intégrant le rôle ; `_tr_boite_libre` affiche « nom RÔLE » |
| `gui/pin_canvas.py` | `_poser_groupe`, champ de nom chaîné, menus de rôle, `charger()` étendu |
| `gui/tab_components.py` | menu Modèle + Poser, Valeur par défaut, Largeur/Hauteur + case auto, persistance |
| `gui/schematic_editor.py` | `_auto_def` propage `default_value`, `fonctions`, `boite` |
| `tests/test_schematic_symbols.py` | T1, T2 |
| `tests/test_pin_canvas.py` | T3, T4, T5 |
| `tests/test_tab_components.py` | T6 |

---

### Task 1 : `modele_brochage` — fonction pure

**Files:** Modify `gui/schematic_symbols.py`, `tests/test_schematic_symbols.py`

**Interfaces produites :** `modele_brochage(modele: str, n: int = 0) -> list[tuple[str, str, int]]`

- [ ] **Step 1 : tests qui échouent**

```python
def test_modele_dip8_suit_la_convention_reelle():
    from gui.schematic_symbols import modele_brochage
    b = modele_brochage("DIP", 8)
    assert [n for n, _c, _d in b] == [str(i) for i in range(1, 9)]
    cotes = {n: c for n, c, _d in b}
    assert all(cotes[str(i)] == "L" for i in range(1, 5))
    assert all(cotes[str(i)] == "R" for i in range(5, 9))
    dec = {n: d for n, _c, d in b}
    # gauche : 1..4 de HAUT en BAS  -> décalages croissants
    assert [dec[str(i)] for i in range(1, 5)] == sorted(dec[str(i)] for i in range(1, 5))
    # droite : 5..8 de BAS en HAUT -> décalages décroissants
    droite = [dec[str(i)] for i in range(5, 9)]
    assert droite == sorted(droite, reverse=True)
    assert all(d % 20 == 0 for d in dec.values())


def test_modele_connecteur_tout_a_gauche():
    from gui.schematic_symbols import modele_brochage
    b = modele_brochage("Connecteur", 3)
    assert [n for n, _c, _d in b] == ["1", "2", "3"]
    assert {c for _n, c, _d in b} == {"L"}


def test_modele_dip_impair_refuse():
    import pytest
    from gui.schematic_symbols import modele_brochage
    with pytest.raises(ValueError):
        modele_brochage("DIP", 7)
    with pytest.raises(ValueError):
        modele_brochage("DIP", 2)
```

- [ ] **Step 2 : vérifier l'échec** — `ImportError: cannot import name 'modele_brochage'`

- [ ] **Step 3 : implémenter** (dans la section « Brochage libre » de `schematic_symbols.py`)

```python
MODELES = ("DIP", "Connecteur")


def modele_brochage(modele, n=0):
    """@brief Brochage tout fait d'un boitier courant (spec 2026-07-23).

    DIP : 1..n/2 a GAUCHE de haut en bas, n/2+1..n a DROITE de bas en haut —
    la numerotation d'un vrai boitier, la meme que `def_puce`. Connecteur (et
    bornier, qui n'en est qu'un raccourci de taille) : tout a gauche.

    @return list [(nom, cote, decalage)] ORDONNEE = ordre de la netlist.
    @throws ValueError Si `n` est hors bornes, ou impair/trop petit pour un DIP.
    """
    n = int(n)
    if not 2 <= n <= 64:
        raise ValueError(f"nombre de broches hors bornes : {n}")
    pas = 20
    if modele == "DIP":
        if n % 2 or n < 4:
            raise ValueError(f"un DIP exige un nombre pair >= 4 : {n}")
        m = n // 2
        y0 = -((m - 1) * pas) // 2
        y0 -= y0 % pas
        gauche = [(str(i + 1), "L", y0 + i * pas) for i in range(m)]
        droite = [(str(n - i), "R", y0 + i * pas) for i in range(m)]
        return gauche + droite[::-1]
    if modele == "Connecteur":
        y0 = -((n - 1) * pas) // 2
        y0 -= y0 % pas
        return [(str(i + 1), "L", y0 + i * pas) for i in range(n)]
    raise ValueError(f"modele inconnu : {modele!r}")
```

- [ ] **Step 4 : vérifier le vert**

`PYTHONUTF8=1 python -m pytest tests/test_schematic_symbols.py -q`

- [ ] **Step 5 : commit**

```bash
git add gui/schematic_symbols.py tests/test_schematic_symbols.py
git commit -m "feat(composants): modeles de boitier (DIP, connecteur) en fonction pure"
```

---

### Task 2 : taille plancher et rôle dans le libellé

**Files:** Modify `gui/schematic_symbols.py`, `tests/test_schematic_symbols.py`

**Interfaces produites :**
- `geometrie_libre(pinout, w_mini=None, h_mini=None, roles=None) -> dict`
  (la def gagne la clé `fonctions` quand `roles` est fourni)

- [ ] **Step 1 : tests qui échouent**

```python
def test_taille_mini_agrandit_la_boite():
    from gui.schematic_symbols import geometrie_libre
    d = geometrie_libre({"1": ("L", 0)}, w_mini=200, h_mini=300)
    assert d["w"] >= 200 and d["h"] >= 300


def test_taille_mini_ne_descend_jamais_sous_le_besoin_reel():
    """Plancher, JAMAIS plafond : sinon les broches sortent du cadre."""
    from gui.schematic_symbols import geometrie_libre
    auto = geometrie_libre({"1": ("L", -200)})
    force = geometrie_libre({"1": ("L", -200)}, w_mini=40, h_mini=40)
    assert force["h"] == auto["h"] and force["w"] == auto["w"]


def test_role_apparait_dans_le_libelle():
    from gui.schematic_symbols import _tr_boite_libre, geometrie_libre
    d = geometrie_libre({"VCC": ("L", 0)}, roles={"VCC": "Alim"})
    textes = [p[2] for p in _tr_boite_libre(d) if p[0] == "text"]
    assert "VCC Alim" in textes


def test_largeur_tient_compte_du_role():
    from gui.schematic_symbols import geometrie_libre
    sans = geometrie_libre({"A": ("L", 0), "B": ("R", 0)})
    avec = geometrie_libre({"A": ("L", 0), "B": ("R", 0)},
                           roles={"A": "Alim", "B": "Sortie"})
    assert avec["w"] > sans["w"]
```

- [ ] **Step 2 : vérifier l'échec**

- [ ] **Step 3 : implémenter**

Dans `geometrie_libre`, remplacer la signature et le calcul de `w`/`h` :

```python
def geometrie_libre(pinout, w_mini=None, h_mini=None, roles=None):
    """@brief Def d'une boite au brochage libre (spec 2026-07-23).

    @param w_mini,h_mini Taille PLANCHER imposee par l'utilisateur : la boite
           fait au moins ca, mais l'auto-ajustement continue de garantir que
           broches et libelles tiennent (on ne peut pas fabriquer un composant
           dont les broches debordent).
    @param roles {nom: role} — affiche « nom ROLE », comme `_tr_boite`.
    """
    roles = roles or {}

    def _lab(n):
        return f"{n} {roles.get(n, '')}".strip()

    lat = [abs(d) for c, d in pinout.values() if c in ("L", "R")]
    ver = [abs(d) for c, d in pinout.values() if c in ("T", "B")]
    lg = max((len(_lab(n)) for n, (c, _d) in pinout.items() if c == "L"), default=0)
    ld = max((len(_lab(n)) for n, (c, _d) in pinout.items() if c == "R"), default=0)
    h = max(BOITE_MIN_H, 2 * max(lat, default=0) + BOITE_MARGE)
    w = max(BOITE_MIN_W, 2 * max(ver, default=0) + BOITE_MARGE,
            (lg + ld) * CHAR_W + 3 * BOITE_MARGE)
    if ver:
        h += 2 * BOITE_MARGE
    # PLANCHER, applique APRES l'auto-ajustement : jamais en dessous du besoin.
    w = max(w, int(w_mini or 0))
    h = max(h, int(h_mini or 0))
```

puis, dans le `return`, ajouter `"fonctions": dict(roles)`.

Dans `_tr_boite_libre`, remplacer `pn` par le libellé composé :

```python
        fonction = (defn.get("fonctions") or {}).get(pn, "")
        libelle = f"{pn} {fonction}".strip()
```
et utiliser `libelle` dans la primitive `("text", …)`.

- [ ] **Step 4 : vérifier le vert** (fichier entier — les tests de non-chevauchement
      existants doivent rester verts)
- [ ] **Step 5 : commit**

```bash
git add gui/schematic_symbols.py tests/test_schematic_symbols.py
git commit -m "feat(composants): taille plancher et role de broche dans le libelle"
```

---

### Task 3 : canevas — pose groupée et chargement étendu

**Files:** Modify `gui/pin_canvas.py`, `tests/test_pin_canvas.py`

**Interfaces produites :**
- `PinCanvas.charger(brochage, lecture_seule=False, roles=None, w_mini=None, h_mini=None)`
- `PinCanvas.roles() -> dict`
- `PinCanvas._poser_groupe(cote: str, n: int) -> list[str]`
- `PinCanvas.poser_modele(modele: str, n: int)`

- [ ] **Step 1 : tests qui échouent**

```python
def test_pose_groupee_ajoute_n_broches_en_fin(canevas):
    canevas.charger([("A", "R", 0)])
    noms = canevas._poser_groupe("L", 3)
    assert noms == ["1", "2", "3"]
    assert [n for n, _c, _d in canevas.brochage()] == ["A", "1", "2", "3"]
    assert {c for n, c, _d in canevas.brochage() if n != "A"} == {"L"}


def test_pose_groupee_espace_les_broches(canevas):
    canevas._poser_groupe("L", 3)
    decs = sorted(d for _n, _c, d in canevas.brochage())
    assert len(set(decs)) == 3
    assert all(d % 20 == 0 for d in decs)


def test_poser_modele_remplace_le_brochage(canevas):
    canevas.charger([("VIEUX", "L", 0)])
    canevas.poser_modele("DIP", 8)
    assert [n for n, _c, _d in canevas.brochage()] == [str(i) for i in range(1, 9)]


def test_charger_transporte_roles_et_taille(canevas):
    canevas.charger([("VCC", "L", 0)], roles={"VCC": "Alim"},
                    w_mini=200, h_mini=240)
    assert canevas.roles() == {"VCC": "Alim"}
    assert canevas._defn()["w"] >= 200 and canevas._defn()["h"] >= 240
```

- [ ] **Step 2 : vérifier l'échec**

- [ ] **Step 3 : implémenter**

```python
    def charger(self, brochage, lecture_seule=False, roles=None,
                w_mini=None, h_mini=None):
        self._brochage = [tuple(b) for b in brochage]
        self._roles = dict(roles or {})
        self._w_mini, self._h_mini = w_mini, h_mini
        self._lecture_seule = lecture_seule
        self._selection = None
        self._dessiner()
        self._construire_bandeau()

    def roles(self) -> dict:
        """@brief {nom: role} des broches renseignées (vides omis)."""
        return {n: r for n, r in self._roles.items() if r}

    def _defn(self):
        return geometrie_libre({n: (c, d) for n, c, d in self._brochage},
                               self._w_mini, self._h_mini, self.roles())

    def _poser_groupe(self, cote: str, n: int) -> list:
        """@brief Pose n broches espacées sur un côté, ajoutées EN FIN."""
        if self._lecture_seule:
            return []
        pas = GRILLE
        y0 = -((n - 1) * pas) // 2
        y0 -= y0 % pas
        noms = []
        for i in range(int(n)):
            nom = self._nom_libre()
            self._brochage.append((nom, cote, y0 + i * pas))
            noms.append(nom)
        self._muter()
        return noms

    def poser_modele(self, modele: str, n: int):
        """@brief REMPLACE le brochage par celui d'un boîtier type."""
        if self._lecture_seule:
            return
        self._brochage = list(modele_brochage(modele, n))
        self._roles = {}
        self._selection = None
        self._muter()
```

Initialiser `self._roles = {}`, `self._w_mini = self._h_mini = None` dans
`__init__`, et importer `modele_brochage`.

- [ ] **Step 4 : vérifier le vert**
- [ ] **Step 5 : commit**

```bash
git add gui/pin_canvas.py tests/test_pin_canvas.py
git commit -m "feat(composants): pose groupee de broches et modeles de boitier au canevas"
```

---

### Task 4 : canevas — champ de nom chaîné

**Files:** Modify `gui/pin_canvas.py`, `tests/test_pin_canvas.py`

**Interfaces produites :** `PinCanvas._valider_nom(nouveau: str) -> bool`
(renomme la broche sélectionnée puis **avance** la sélection) ;
`PinCanvas._selection_suivante()`

- [ ] **Step 1 : tests qui échouent**

```python
def test_nom_chaine_avance_a_la_broche_suivante(canevas):
    canevas.charger([("1", "L", -20), ("2", "L", 0), ("3", "L", 20)])
    canevas._selection = "1"
    assert canevas._valider_nom("GND") is True
    assert [n for n, _c, _d in canevas.brochage()] == ["GND", "2", "3"]
    assert canevas._selection == "2"


def test_nom_chaine_boucle_apres_la_derniere(canevas):
    canevas.charger([("1", "L", 0), ("2", "L", 20)])
    canevas._selection = "2"
    canevas._valider_nom("OUT")
    assert canevas._selection == "1"


def test_refus_n_avance_pas(canevas):
    canevas.charger([("1", "L", 0), ("2", "L", 20)])
    canevas._selection = "1"
    assert canevas._valider_nom("2") is False        # doublon
    assert canevas._selection == "1"
    assert canevas._valider_nom("   ") is False      # vide
    assert canevas._selection == "1"
```

- [ ] **Step 2 : vérifier l'échec**

- [ ] **Step 3 : implémenter**

```python
    def _selection_suivante(self):
        """@brief Avance la sélection d'un rang, en bouclant."""
        if not self._brochage:
            self._selection = None
            return
        i = self._index(self._selection)
        self._selection = self._brochage[(i + 1) % len(self._brochage)][0]

    def _valider_nom(self, nouveau) -> bool:
        """@brief Renomme la broche sélectionnée PUIS passe à la suivante.

        C'est tout l'intérêt du champ chaîné : nommer huit broches devient une
        seule séquence au clavier. Un refus (vide, doublon) NE FAIT PAS avancer,
        sinon on perdrait la broche qu'on essayait de nommer.
        """
        if not self._selection:
            return False
        if not self._renommer(self._selection, nouveau):
            return False
        self._selection_suivante()
        self._sync_champ()
        self._dessiner()
        return True
```

UI : un `ui_kit.Field` sous le canevas (au-dessus du bandeau), lié à
`<Return>` → `_valider_nom(champ.get())`. `_sync_champ()` recopie le nom de la
broche sélectionnée dans le champ ; appelée par `_sur_clic`, `_muter` et
`_selection_suivante`. Le champ est désactivé en lecture seule.

- [ ] **Step 4 : vérifier le vert**
- [ ] **Step 5 : commit**

```bash
git add gui/pin_canvas.py tests/test_pin_canvas.py
git commit -m "feat(composants): champ de nom chaine, Entree passe a la broche suivante"
```

---

### Task 5 : canevas — rôle par broche dans le bandeau

**Files:** Modify `gui/pin_canvas.py`, `tests/test_pin_canvas.py`

**Interfaces produites :** `PinCanvas._definir_role(nom: str, role: str)` ;
constante `ROLES = ("", "Alim", "Entrée", "Sortie", "Masse", "E/S")`

- [ ] **Step 1 : tests qui échouent**

```python
def test_role_enregistre_et_restitue(canevas):
    canevas.charger([("VCC", "T", 0)])
    canevas._definir_role("VCC", "Alim")
    assert canevas.roles() == {"VCC": "Alim"}


def test_role_vide_est_omis(canevas):
    canevas.charger([("VCC", "T", 0)])
    canevas._definir_role("VCC", "Alim")
    canevas._definir_role("VCC", "")
    assert canevas.roles() == {}


def test_renommage_conserve_le_role(canevas):
    canevas.charger([("1", "L", 0)])
    canevas._definir_role("1", "Masse")
    canevas._renommer("1", "GND")
    assert canevas.roles() == {"GND": "Masse"}


def test_suppression_retire_le_role(canevas):
    canevas.charger([("1", "L", 0)])
    canevas._definir_role("1", "Masse")
    canevas._supprimer("1")
    assert canevas.roles() == {}
```

- [ ] **Step 2 : vérifier l'échec**

- [ ] **Step 3 : implémenter**

```python
ROLES = ("", "Alim", "Entrée", "Sortie", "Masse", "E/S")
```

```python
    def _definir_role(self, nom, role):
        if self._lecture_seule:
            return
        if role:
            self._roles[nom] = role
        else:
            self._roles.pop(nom, None)
        self._muter()
```

Dans `_renommer`, après la permutation du nom, reporter le rôle :
```python
        if ancien in self._roles:
            self._roles[nouveau] = self._roles.pop(ancien)
```
Dans `_supprimer` : `self._roles.pop(nom, None)`.
Dans `_construire_bandeau`, ajouter sous chaque pastille un
`ctk.CTkOptionMenu(values=list(ROLES), command=…)` appelant `_definir_role`,
désactivé en lecture seule.

- [ ] **Step 4 : vérifier le vert**
- [ ] **Step 5 : commit**

```bash
git add gui/pin_canvas.py tests/test_pin_canvas.py
git commit -m "feat(composants): role par broche (alim, entree, sortie, masse)"
```

---

### Task 6 : onglet — modèles, valeur par défaut, taille, persistance

**Files:** Modify `gui/tab_components.py`, `gui/schematic_editor.py`,
`tests/test_tab_components.py`

- [ ] **Step 1 : tests qui échouent**

```python
def test_sauvegarde_ecrit_les_nouvelles_cles(onglet):
    t, chemin = onglet
    t._prefix_var.set("IC")
    t._name_var.set("Ampli")
    t._default_var.set("LM358")
    t._auto_taille_var.set(False)
    t._w_var.set("120"); t._h_var.set("160")
    t._brochage = [("VCC", "T", 0), ("GND", "B", 0)]
    t._canvas_broches.charger(t._brochage, roles={"VCC": "Alim"})
    t._sauvegarder()
    d = json.loads(chemin.read_text(encoding="utf-8"))["IC"]
    assert d["default_value"] == "LM358"
    assert d["fonctions"] == {"VCC": "Alim"}
    assert d["boite"] == {"w": 120, "h": 160}


def test_taille_auto_n_ecrit_pas_la_cle_boite(onglet):
    t, chemin = onglet
    t._prefix_var.set("IC"); t._name_var.set("X")
    t._auto_taille_var.set(True)
    t._brochage = [("1", "L", 0)]
    t._sauvegarder()
    assert "boite" not in json.loads(chemin.read_text(encoding="utf-8"))["IC"]


def test_relecture_restitue_les_nouvelles_cles(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({"IC": {
        "name": "Ampli", "pins": ["VCC"], "default_value": "LM358",
        "brochage": {"VCC": ["T", 0]}, "fonctions": {"VCC": "Alim"},
        "boite": {"w": 120, "h": 160}}}), encoding="utf-8")
    t._load(); t._afficher_perso("IC")
    assert t._default_var.get() == "LM358"
    assert t._canvas_broches.roles() == {"VCC": "Alim"}
    assert t._auto_taille_var.get() is False
    assert t._w_var.get() == "120"


def test_poser_modele_remplit_le_brochage(onglet):
    t, _ = onglet
    t._modele_var.set("DIP-8")
    t._poser_modele()
    assert [n for n, _c, _d in t._brochage] == [str(i) for i in range(1, 9)]


def test_auto_def_propage_valeur_role_et_taille():
    from gui.schematic_editor import _auto_def
    d = _auto_def("Ampli", ["VCC"], {"VCC": ["T", 0]},
                  default_value="LM358", fonctions={"VCC": "Alim"},
                  boite={"w": 200, "h": 240})
    assert d["default_value"] == "LM358"
    assert d["fonctions"] == {"VCC": "Alim"}
    assert d["w"] >= 200 and d["h"] >= 240
```

- [ ] **Step 2 : vérifier l'échec**

- [ ] **Step 3 : implémenter**

1. **`_auto_def`** (`gui/schematic_editor.py`) : nouveaux paramètres
   `default_value=""`, `fonctions=None`, `boite=None`.
   ```python
       if brochage:
           b = boite or {}
           d = geometrie_libre({n: tuple(v) for n, v in brochage.items()},
                               b.get("w"), b.get("h"), fonctions or {})
           d["label"] = name
           d["default_value"] = default_value or ""
           return d
   ```
   et propager le reste du chemin historique : `"default_value": default_value or ""`.
   `_compute_defs` transmet `val.get("default_value", "")`,
   `val.get("fonctions")`, `val.get("boite")`.
2. **`tab_components._build`** : au-dessus du canevas, une rangée
   `[Modèle ▾] [N] [Poser]` ; sous « Nom complet », un champ
   « Valeur par défaut » (`self._default_var`) ; sous le canevas, une rangée
   `Largeur [ ] Hauteur [ ] [x] Ajuster automatiquement`
   (`self._w_var`, `self._h_var`, `self._auto_taille_var`), les deux champs
   désactivés tant que la case est cochée.
3. **`_poser_modele`** : `("DIP-8"→("DIP",8), "DIP-14"→("DIP",14),
   "DIP-16"→("DIP",16), "Bornier 2/3/4"→("Connecteur",n),
   "Connecteur N"→("Connecteur", int(self._n_var.get())))`. Si `self._brochage`
   n'est pas vide, `messagebox.askyesno` avant de remplacer. `ValueError` →
   `messagebox.showerror` avec le message, sans rien changer.
4. **`_remplir_formulaire`** : nouveaux paramètres `default_value=""`,
   `fonctions=None`, `boite=None` ; renseigne les variables et appelle
   `charger(..., roles=fonctions, w_mini=…, h_mini=…)`.
   `_afficher_perso` / `_afficher_integre` / `_afficher_nouveau` transmettent.
5. **`_etat_courant`** : ajouter `self._default_var.get().strip()`,
   `tuple(sorted(self._canvas_broches.roles().items()))` et la taille — sinon
   l'anti-perte de saisie rate ces champs.
6. **`_sauvegarder`** : écrit `default_value` (si non vide), `fonctions` (si non
   vide), `boite` (seulement si la case auto est **décochée** et les deux champs
   sont des entiers valides ; sinon `messagebox.showerror` et abandon).
7. **`_dupliquer`** : transporte valeur, rôles et taille.

- [ ] **Step 4 : vérifier le vert + non-régression**

```bash
PYTHONUTF8=1 python -m pytest tests/test_tab_components.py tests/test_pin_canvas.py \
  tests/test_schematic_symbols.py tests/test_schematic_editor.py \
  tests/test_brochage_libre.py tests/test_gui_sync.py tests/test_palette_et_doublon.py -q
```

- [ ] **Step 5 : commit**

```bash
git add gui/tab_components.py gui/schematic_editor.py tests/test_tab_components.py
git commit -m "feat(composants): modeles, valeur par defaut, roles et taille dans l'onglet"
```

---

### Task 7 : suite complète + boucle visuelle

- [ ] **Step 1 :** `PYTHONUTF8=1 python -m pytest -q` → **0 failed**
  (référence : 1874 passed / 50 skipped).
- [ ] **Step 2 : boucle visuelle** — script scratch **hors dépôt**, dialogues
  neutralisés (`messagebox` remplacé), 3 PNG **inspectés et décrits** :
  1. l'onglet après « Poser DIP-8 » + renommage chaîné + rôles renseignés ;
  2. **le composant posé dans l'éditeur** : rôles affichés (« VCC Alim »),
     taille imposée respectée, valeur par défaut pré-remplie — c'est la preuve
     que la chaîne onglet → JSON → `_auto_def` → canevas tient ;
  3. un type d'avant le chantier, **inchangé**.
- [ ] **Step 3 :** supprimer PNG et scripts.
- [ ] **Step 4 :** vérifier que `component_library.json` n'est pas dans le diff,
  puis `superpowers:finishing-a-development-branch`.

---

## Vérification (bout en bout)

1. Suite complète verte, sans modifier les assertions existantes.
2. `git status` : aucune modification de `component_library.json`.
3. **À la main** : onglet Composants → Nouveau → `U` / `NE555` / valeur
   `NE555` → Modèle `DIP-8` → Poser → clic sur la broche 1 → taper
   `GND↵ TRIG↵ OUT↵ RESET↵ CTRL↵ THR↵ DIS↵ VCC↵` → rôles `Alim` sur VCC et
   `Masse` sur GND → décocher « Ajuster automatiquement », 140×200 →
   Sauvegarder → éditeur : le NE555 se pose avec sa valeur, ses rôles et sa
   taille.
4. Les 3 PNG de la Task 7, inspectés et décrits.
