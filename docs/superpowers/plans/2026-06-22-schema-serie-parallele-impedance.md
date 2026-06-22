# Schéma série/parallèle dans la fenêtre Impédance — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afficher, dans la fenêtre « Impédance équivalente », un schéma série/parallèle lisible (forme manuel) du réseau réduit, à côté de l'expression et du |Z|/phase.

**Architecture:** L'expression réduite (`(R1+R2)//R3`) est parsée en arbre série/parallèle (`arbre_expr`, pur). Une fonction de mise en page pure (`agencer`) transforme l'arbre en primitives positionnées (symboles + fils). Un rendu schemdraw les dessine dans une figure matplotlib embarquée dans la fenêtre. Le cas pont (Y-Δ, opérateurs `*`/`/`) renvoie `None` et n'est pas dessiné (message texte).

**Tech Stack:** Python 3 (stdlib `ast`), networkx (existant), schemdraw + matplotlib (existants), customtkinter (existant).

## Global Constraints

- Aucun commit ne porte `Co-Authored-By Claude` (directive utilisateur).
- Aucune nouvelle dépendance : stdlib + networkx + schemdraw + matplotlib + customtkinter uniquement.
- Branche : `rewrite-simple`.
- La vue îlot (`gui/circuit_viewer.py`) n'est PAS modifiée.

## File Structure

- `circuit_analyzer/impedance.py` (modifier) : ajouter `arbre_expr(expr)` (parsing pur).
- `gui/impedance_schematic.py` (créer) : mise en page (`agencer`) + rendu (`dessiner`).
- `gui/impedance_view.py` (modifier) : embarquer la figure quand l'arbre existe.
- `tests/test_impedance.py` (modifier) : tests de `arbre_expr`.
- `tests/test_impedance_schematic.py` (créer) : tests de `agencer` + smoke de `dessiner`.

---

### Task 1 : `arbre_expr` — parser l'expression en arbre série/parallèle

**Files:**
- Modify: `circuit_analyzer/impedance.py` (ajouter en fin de fichier, avant ou après `evaluer_impedance`)
- Test: `tests/test_impedance.py`

**Interfaces:**
- Consumes: rien (utilise `ast` déjà importé dans `impedance.py`).
- Produces: `arbre_expr(expr: str) -> tuple | None`. Nœuds :
  - feuille : `("feuille", "R1")`
  - série : `("serie", [enfant, ...])`
  - parallèle : `("parallele", [enfant, ...])`
  - `None` si l'expression contient `*` ou `/` (pont/Y-Δ) ou est invalide.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_impedance.py` :

```python
# ── arbre_expr : expression de composition -> arbre serie/parallele ───────────

def test_arbre_expr_serie_simple():
    assert impedance.arbre_expr("R1+R2") == (
        "serie", [("feuille", "R1"), ("feuille", "R2")])


def test_arbre_expr_serie_aplatie():
    # R1+R2+R3 (associatif) -> un seul noeud serie a 3 enfants.
    assert impedance.arbre_expr("R1+R2+R3") == (
        "serie", [("feuille", "R1"), ("feuille", "R2"), ("feuille", "R3")])


def test_arbre_expr_parallele_de_serie():
    assert impedance.arbre_expr("(R1+R2)//R3") == (
        "parallele", [("serie", [("feuille", "R1"), ("feuille", "R2")]),
                      ("feuille", "R3")])


def test_arbre_expr_feuille_seule():
    assert impedance.arbre_expr("R1") == ("feuille", "R1")


def test_arbre_expr_pont_non_serie_parallele():
    # Une expression Y-D contient * et / -> pas de forme serie/parallele.
    assert impedance.arbre_expr("(R1)*(R2)/((R1)+(R2)+(R5))") is None
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run : `python -m pytest tests/test_impedance.py -q -k arbre_expr`
Expected : FAIL — `AttributeError: module 'circuit_analyzer.impedance' has no attribute 'arbre_expr'`.

- [ ] **Step 3 : Implémenter le minimum**

Ajouter dans `circuit_analyzer/impedance.py` (par ex. juste après `evaluer_impedance`) :

```python
def _convertir_noeud(node):
    """@brief Convertit un nœud AST en arbre série/parallèle, ou None si * / /."""
    if isinstance(node, ast.Name):
        return ("feuille", node.id)
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            kind = "serie"
        elif isinstance(node.op, ast.FloorDiv):  # // = parallèle
            kind = "parallele"
        else:
            return None  # * ou / => pont (Y-Δ), pas de forme série/parallèle
        gauche = _convertir_noeud(node.left)
        droite = _convertir_noeud(node.right)
        if gauche is None or droite is None:
            return None
        enfants = []
        for sous in (gauche, droite):
            if sous[0] == kind:          # aplatissement associatif (a+b+c)
                enfants.extend(sous[1])
            else:
                enfants.append(sous)
        return (kind, enfants)
    return None


def arbre_expr(expr: str):
    """@brief Parse une expression de composition en arbre série/parallèle.

    @param expr Expression (ex. « (R1+R2)//R3 »).
    @return tuple|None Arbre (« serie »/« parallele »/« feuille »), ou None si
            l'expression n'est pas purement série/parallèle (pont Y-Δ : * ou /)
            ou est invalide.
    """
    try:
        return _convertir_noeud(ast.parse(expr, mode='eval').body)
    except (SyntaxError, ValueError):
        return None
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

Run : `python -m pytest tests/test_impedance.py -q -k arbre_expr`
Expected : PASS (5 tests).

- [ ] **Step 5 : Commit**

```bash
git add circuit_analyzer/impedance.py tests/test_impedance.py
git commit -m "feat(impedance): arbre_expr parse l'expression en arbre serie/parallele"
```

---

### Task 2 : `agencer` — mise en page pure (arbre → symboles + fils positionnés)

**Files:**
- Create: `gui/impedance_schematic.py`
- Test: `tests/test_impedance_schematic.py`

**Interfaces:**
- Consumes: l'arbre produit par `impedance.arbre_expr` (Task 1).
- Produces:
  - `agencer(arbre) -> (symboles, fils, dims)` avec l'arbre posé coin bas-gauche en (0,0) :
    - `symboles` : `list[(ref:str, x1:float, x2:float, y:float)]` — symbole 2 bornes de (x1,y) à (x2,y).
    - `fils` : `list[((xa,ya),(xb,yb))]` — segments de fil.
    - `dims` : `Dims(largeur, hauteur, y_borne)` (namedtuple). Bornes externes du dessin : gauche `(0, dims.y_borne)`, droite `(dims.largeur, dims.y_borne)`.
  - Constantes : `W_SYMB, H_SYMB, LEAD, GAP_V, RAIL` (floats).

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `tests/test_impedance_schematic.py` :

```python
"""@file test_impedance_schematic.py
@brief Tests de la mise en page serie/parallele (gui/impedance_schematic.py)."""
from gui import impedance_schematic as sch


def test_agencer_serie_aligne_les_enfants_en_ligne():
    arbre = ("serie", [("feuille", "R1"), ("feuille", "R2")])
    symboles, fils, dims = sch.agencer(arbre)
    assert len(symboles) == 2
    # x croissants (R1 a gauche de R2), meme ligne de bornes (y egaux).
    xs = sorted(s[1] for s in symboles)
    assert xs[0] < xs[1]
    assert symboles[0][3] == symboles[1][3]
    # largeur de la boite = 2 symboles + 1 fil entre eux.
    assert abs(dims.largeur - (2 * sch.W_SYMB + sch.LEAD)) < 1e-9


def test_agencer_parallele_empile_les_enfants():
    arbre = ("parallele", [("feuille", "R1"), ("feuille", "R2")])
    symboles, fils, dims = sch.agencer(arbre)
    assert len(symboles) == 2
    # y distincts (empiles), donc hauteur = 2 symboles + 1 ecart vertical.
    ys = sorted(s[3] for s in symboles)
    assert ys[0] < ys[1]
    assert abs(dims.hauteur - (2 * sch.H_SYMB + sch.GAP_V)) < 1e-9
    # des fils relient les branches aux rails (au moins 2 liaisons + 2 rails).
    assert len(fils) >= 4


def test_agencer_feuille_seule():
    symboles, fils, dims = sch.agencer(("feuille", "R1"))
    assert len(symboles) == 1
    assert symboles[0][0] == "R1"
    assert fils == []
    assert abs(dims.largeur - sch.W_SYMB) < 1e-9
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run : `python -m pytest tests/test_impedance_schematic.py -q`
Expected : FAIL — `ModuleNotFoundError: No module named 'gui.impedance_schematic'`.

- [ ] **Step 3 : Implémenter le minimum**

Créer `gui/impedance_schematic.py` avec la mise en page (sans encore le rendu) :

```python
"""
@file impedance_schematic.py
@brief Dessin série/parallèle d'un réseau d'impédances réduit (forme « manuel »).

L'arbre produit par circuit_analyzer.impedance.arbre_expr est mis en page en
primitives (symboles 2 bornes + fils), puis rendu via schemdraw. Série = en
ligne, parallèle = branches empilées entre deux rails. Module isolé : la vue
îlot (circuit_viewer.py) n'est pas concernée.
"""
import collections

Dims = collections.namedtuple("Dims", "largeur hauteur y_borne")

# Unités schemdraw (1 unité ≈ une longueur de symbole).
W_SYMB = 2.0    # longueur d'un symbole 2 bornes
H_SYMB = 1.0    # empreinte verticale d'une feuille (pour l'empilement)
LEAD = 0.6      # fil entre deux composants en série
GAP_V = 1.4     # écart vertical entre branches parallèles
RAIL = 0.6      # extension horizontale d'un rail de chaque côté


def _mesurer(arbre):
    """@brief Dimensions (largeur, hauteur, y des bornes) d'un sous-arbre."""
    kind = arbre[0]
    if kind == "feuille":
        return Dims(W_SYMB, H_SYMB, H_SYMB / 2)
    enfants = [_mesurer(c) for c in arbre[1]]
    if kind == "serie":
        largeur = sum(d.largeur for d in enfants) + LEAD * (len(enfants) - 1)
        hauteur = max(d.hauteur for d in enfants)
        return Dims(largeur, hauteur, hauteur / 2)
    # parallele
    inner = max(d.largeur for d in enfants)
    largeur = inner + 2 * RAIL
    hauteur = sum(d.hauteur for d in enfants) + GAP_V * (len(enfants) - 1)
    return Dims(largeur, hauteur, hauteur / 2)


def _emettre(arbre, x, y, symboles, fils):
    """@brief Place l'arbre, coin bas-gauche en (x,y) ; remplit symboles/fils.

    @return Dims du sous-arbre placé.
    """
    d = _mesurer(arbre)
    ligne_y = y + d.y_borne
    kind = arbre[0]
    if kind == "feuille":
        symboles.append((arbre[1], x, x + W_SYMB, ligne_y))
        return d
    if kind == "serie":
        cx = x
        prev_droite = None
        for c in arbre[1]:
            dc = _mesurer(c)
            _emettre(c, cx, ligne_y - dc.y_borne, symboles, fils)
            if prev_droite is not None:
                fils.append(((prev_droite, ligne_y), (cx, ligne_y)))
            prev_droite = cx + dc.largeur
            cx = prev_droite + LEAD
        return d
    # parallele
    rail_g, rail_d = x, x + d.largeur
    inner = d.largeur - 2 * RAIL
    lignes = []
    haut = y + d.hauteur
    for c in arbre[1]:
        dc = _mesurer(c)
        c_y0 = haut - dc.hauteur
        c_x = x + RAIL + (inner - dc.largeur) / 2
        c_ligne = c_y0 + dc.y_borne
        _emettre(c, c_x, c_y0, symboles, fils)
        fils.append(((rail_g, c_ligne), (c_x, c_ligne)))
        fils.append(((c_x + dc.largeur, c_ligne), (rail_d, c_ligne)))
        lignes.append(c_ligne)
        haut = c_y0 - GAP_V
    fils.append(((rail_g, lignes[0]), (rail_g, lignes[-1])))   # rail gauche
    fils.append(((rail_d, lignes[0]), (rail_d, lignes[-1])))   # rail droit
    return d


def agencer(arbre):
    """@brief Met en page l'arbre, coin bas-gauche en (0,0).

    @param arbre Arbre série/parallèle (cf. impedance.arbre_expr).
    @return (symboles, fils, dims) : voir l'en-tête du module.
    """
    symboles, fils = [], []
    dims = _emettre(arbre, 0.0, 0.0, symboles, fils)
    return symboles, fils, dims
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

Run : `python -m pytest tests/test_impedance_schematic.py -q`
Expected : PASS (3 tests).

- [ ] **Step 5 : Commit**

```bash
git add gui/impedance_schematic.py tests/test_impedance_schematic.py
git commit -m "feat(impedance): agencer - mise en page serie/parallele (pure)"
```

---

### Task 3 : `dessiner` + intégration dans la fenêtre Impédance

**Files:**
- Modify: `gui/impedance_schematic.py` (ajouter `dessiner`)
- Modify: `gui/impedance_view.py` (embarquer la figure)
- Test: `tests/test_impedance_schematic.py` (smoke de `dessiner`)

**Interfaces:**
- Consumes: `agencer` (Task 2) ; `impedance.arbre_expr` (Task 1) ; `graph.graph["components"]` (dict {ref → Composant} avec `.type` et `.value`).
- Produces: `dessiner(arbre, a: str, b: str, comps: dict) -> matplotlib.figure.Figure`.

- [ ] **Step 1 : Écrire le smoke test qui échoue**

Ajouter à `tests/test_impedance_schematic.py` :

```python
def test_dessiner_produit_une_figure_sans_exception():
    from circuit_analyzer.composant import Composant
    comps = {
        "R1": Composant("R1", "R", {"1": "A", "2": "M"}, "1k"),
        "R2": Composant("R2", "R", {"1": "M", "2": "B"}, "2k"),
        "R3": Composant("R3", "R", {"1": "A", "2": "B"}, "3k"),
    }
    arbre = ("parallele", [("serie", [("feuille", "R1"), ("feuille", "R2")]),
                           ("feuille", "R3")])
    fig = sch.dessiner(arbre, "VIN", "VOUT", comps)
    # une figure matplotlib avec au moins un axe.
    assert fig is not None
    assert len(fig.axes) == 1
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run : `python -m pytest tests/test_impedance_schematic.py::test_dessiner_produit_une_figure_sans_exception -q`
Expected : FAIL — `AttributeError: module 'gui.impedance_schematic' has no attribute 'dessiner'`.

- [ ] **Step 3 : Implémenter `dessiner`**

Ajouter en tête de `gui/impedance_schematic.py` (imports) :

```python
import schemdraw
import schemdraw.elements as elm
from matplotlib.figure import Figure
```

Et à la fin du fichier :

```python
SCH_BG = "#fafafa"   # fond clair standard de schéma (idem circuit_viewer)
_WIRE = "#1e293b"
_BUS = "#475569"

# Symbole schemdraw par type de composant ; défaut = boîte Z générique.
_SYMB = {
    "R": elm.Resistor,
    "C": elm.Capacitor,
    "L": elm.Inductor2,
}


def dessiner(arbre, a, b, comps):
    """@brief Figure matplotlib du schéma série/parallèle de l'arbre.

    @param arbre Arbre série/parallèle (cf. impedance.arbre_expr).
    @param a, b Noms des bornes d'entrée/sortie (étiquettes A/B du dessin).
    @param comps Dict {ref → Composant} pour le type (symbole) et la valeur.
    @return matplotlib.figure.Figure prête à embarquer.
    """
    symboles, fils, dims = agencer(arbre)
    fig = Figure(figsize=(max(4.0, dims.largeur * 0.6 + 1.5),
                          max(3.0, dims.hauteur * 0.6 + 1.5)))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")

    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d.config(fontsize=10, inches_per_unit=0.5)
        for ref, x1, x2, y in symboles:
            comp = comps.get(ref)
            cls = _SYMB.get(getattr(comp, "type", ""), elm.ResistorIEC)
            valeur = getattr(comp, "value", "")
            etiquette = f"{ref}\n{valeur}" if valeur else ref
            d += cls().at((x1, y)).to((x2, y)).label(etiquette, loc="bottom",
                                                     fontsize=9)
        for (xa, ya), (xb, yb) in fils:
            d += elm.Line().at((xa, ya)).to((xb, yb)).color(_WIRE)
        d += elm.Dot().at((0.0, dims.y_borne)).label(a, loc="left", color=_BUS)
        d += elm.Dot().at((dims.largeur, dims.y_borne)).label(
            b, loc="right", color=_BUS)

    ax.margins(0.15)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        pass
    return fig
```

- [ ] **Step 4 : Lancer le smoke test pour vérifier qu'il passe**

Run : `python -m pytest tests/test_impedance_schematic.py -q`
Expected : PASS (4 tests).

- [ ] **Step 5 : Intégrer dans `gui/impedance_view.py`**

En tête du fichier, ajouter l'import du canvas Tk (après les imports existants) :

```python
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from gui import impedance_schematic
```

Agrandir la fenêtre — remplacer `win.geometry("560x400")` par :

```python
    win.geometry("720x640")
```

Juste après la création du label `resultat` (et son `.pack(...)`), ajouter un
conteneur pour le schéma :

```python
    schema_holder = ctk.CTkFrame(win, fg_color=SCH_BG, corner_radius=10)
    schema_holder.pack(fill="both", expand=True, padx=24, pady=(4, 12))
```

(Note : `SCH_BG` n'est pas dans `gui.theme`. Ajouter en haut du fichier la
constante locale `SCH_BG = "#fafafa"` à côté des imports de thème.)

Dans `_calculer`, remplacer le bloc `else:` final (calcul numérique + affichage)
pour aussi dessiner le schéma. Le corps de `_calculer` devient, à partir du
calcul de l'expression :

```python
        expr = impedance.impedance_equivalente(graph, a, b)
        # Vider un éventuel schéma précédent.
        for w in schema_holder.winfo_children():
            w.destroy()
        if expr is None:
            resultat.configure(
                text=f"Réseau non réductible entre {a} et {b} par série/parallèle/Y-Δ\n"
                     "(bornes non reliées par des impédances, ou réseau non planaire).",
                text_color="#f59e0b")
            return
        lignes = [f"Z({a},{b}) = {impedance.formater_expr(expr)}"]
        f_txt = var_f.get().strip()
        if f_txt:
            try:
                f = float(f_txt.replace(",", "."))
                z = impedance.evaluer_impedance(graph, expr, f)
                phase = math.degrees(cmath.phase(z))
                lignes.append(f"à {f:g} Hz : |Z| = {_fmt_ohms(abs(z))}"
                              f"  ∠ {phase:+.1f}°")
            except (ValueError, ZeroDivisionError) as e:
                lignes.append(f"(valeur numérique indisponible : {e})")
        arbre = impedance.arbre_expr(expr)
        if arbre is None:
            lignes.append("Réseau en pont (Y-Δ) — pas de forme série/parallèle à dessiner.")
        else:
            fig = impedance_schematic.dessiner(arbre, a, b, graph.graph["components"])
            canvas = FigureCanvasTkAgg(fig, master=schema_holder)
            canvas.draw()
            canvas.get_tk_widget().configure(bg=SCH_BG, highlightthickness=0)
            canvas.get_tk_widget().pack(fill="both", expand=True)
        resultat.configure(text="\n".join(lignes), text_color="#34d399")
```

(Ceci remplace l'ancien bloc qui se terminait par
`resultat.configure(text="\n".join(lignes), text_color=couleur)`. La variable
`couleur` n'est plus utilisée.)

- [ ] **Step 6 : Vérifier la suite complète + lancer l'app manuellement**

Run : `python -m pytest -q`
Expected : PASS (suite complète verte, dont les 4 tests du schéma).

Lancer l'app, ouvrir un circuit `circuits_industriels/impedance_serie_parallele.xml`,
analyser, cliquer « Ω Impédance équiv. », vérifier que le schéma (R4 en série puis
(R1+R2)//R3) s'affiche en forme manuel, avec bornes VIN/VOUT. Tester aussi
`impedance_pont_wheatstone.xml` : le message « Réseau en pont » doit apparaître
sans schéma ni plantage.

- [ ] **Step 7 : Commit**

```bash
git add gui/impedance_schematic.py gui/impedance_view.py tests/test_impedance_schematic.py
git commit -m "feat(impedance): schema serie/parallele dans la fenetre Impedance equivalente"
```

---

## Vérification finale

- `python -m pytest -q` vert (suite complète).
- Schéma série/parallèle lisible (forme manuel) sur `impedance_serie_parallele.xml`
  et `impedance_rlc_mixte.xml` ; message « pont » sur `impedance_pont_wheatstone.xml`.
- Aucun commit avec `Co-Authored-By Claude`.
- La vue îlot (`circuit_viewer.py`) inchangée.
