# Refonte « Dark Premium » — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hisser Circuit Analyzer à une UI sombre *premium* et cohérente sur les 4 onglets + l'esthétique des schémas, via un système de tokens + un kit de widgets, Inter embarquée et un jeu d'icônes Lucide.

**Architecture:** Un module de tokens (`gui/theme.py` étendu) est la source unique de couleurs/espacements/typo. Un kit (`gui/ui_kit.py`) expose des fabriques de widgets qui consomment ces tokens. Chaque écran migre vers le kit. Le rendu des schémas tire ses couleurs d'accent des mêmes tokens. La police et les icônes sont des assets embarqués (`assets/`).

**Tech Stack:** Python 3.14, CustomTkinter (+ tkinter brut pour l'éditeur de schéma), Pillow, matplotlib/schemdraw, PyInstaller.

## Global Constraints
- Direction **Dark premium** : on élève l'existant, on ne change pas d'identité ni de palette de marque (bleu `#3b82f6`).
- **Aucun co-auteur Claude** dans les commits/PR (ni footer « Generated with »).
- Windows-only : enregistrement de police via `AddFontResourceEx(FR_PRIVATE)` acceptable.
- **Aucune dépendance SVG au runtime** : icônes pré-rasterisées en PNG committés dans `assets/icons/`.
- Valeurs R/L/C en mono = **Consolas** (présent sur Windows, zéro asset).
- Texte utile **jamais sous `#64748b`**.
- Les **575 tests existants restent verts** à chaque tâche ; ils testent structure/hitboxes/positions, pas les hex.
- Le **canvas des schémas reste clair** (convention lisibilité) ; seuls les accents bleus s'alignent sur les tokens. Ne pas assombrir le fond des dessins.
- GUI peu testable unitairement → seams testables = vrais tests ; le reste = **vérification par capture d'écran de l'app réelle** (méthode validée par le boss).
- PONYTAIL actif : le plus court chemin qui marche ; pas d'abstraction spéculative.

## Fichiers
| Fichier | Responsabilité |
|---|---|
| `gui/theme.py` (modif) | Tokens : couleurs (élévations, texte, marque, sémantiques), `SP`, `R`, `TYPE` (rôles typo). |
| `gui/fonts.py` (créer) | Enregistrement privé d'Inter au démarrage + fallback ; expose `FONT_FAMILY`. |
| `gui/ui_kit.py` (créer) | `icon()`, `font()`, `Card`, `StatCard`, `PrimaryButton/SecondaryButton/GhostButton/DangerButton/IconButton`, `SectionHeader`, `Field`. |
| `tools/gen_icons.py` (créer) | Dev-time : rasterise le sous-ensemble Lucide → `assets/icons/*.png` (régénérable). |
| `assets/fonts/Inter-*.ttf` (ajout) | Police embarquée. |
| `assets/icons/*.png` (ajout) | Icônes Lucide teintées (1x + 2x). |
| `gui/app_window.py` (modif) | Shell : lockup marque + nav via kit. |
| `gui/tab_analyze.py` (modif) | Header héro, `StatCard`, vue résultats, état vide. |
| `gui/tab_draw.py` (modif) | Toolbar/header via kit. |
| `gui/schematic_editor.py` (modif) | Re-thème palette/canvas tkinter sur tokens + Inter. |
| `gui/tab_circuits.py` (modif) | Cartes/listes/formulaires cohérents. |
| `gui/tab_components.py` (modif) | Idem. |
| `gui/circuit_viewer.py` (modif) | Constantes couleur tirées des tokens. |
| `gui/impedance_schematic.py` (modif) | Idem (drill-down Z). |
| `packaging/analyseur.spec` (modif) | Embarque `assets/fonts` + `assets/icons`. |
| `tests/test_ui_kit.py`, `tests/test_theme_tokens.py`, `tests/test_fonts.py` (créer) | Smoke/contrat. |

---

## VAGUE 1 — Fondation

### Task 1 : Tokens de design (`gui/theme.py`)

**Files:** Modify `gui/theme.py` ; Test `tests/test_theme_tokens.py`

**Interfaces — Produces:**
- Couleurs (str hex) : `BG, SURFACE, RAISED, OVERLAY, BORDER, BORDER_SOFT, TEXT, TEXT_MUTED, TEXT_DIM, BLUE, BLUE_HOVER, BLUE_PRESS, BLUE_SOFT, CYAN, SUCCESS, WARN, ERROR, INFO`.
- `SP = {"xs":4,"sm":8,"md":12,"lg":16,"xl":24,"xxl":32}` (dict[str,int]).
- `R = {"sm":6,"md":8,"lg":12,"xl":16}` (dict[str,int]).
- `TYPE = {"display":(22,"bold"), "title":(18,"bold"), "subtitle":(14,"normal"), "body":(13,"normal"), "caption":(11,"normal"), "overline":(9,"bold")}` (dict[str,tuple[int,str]]).
- Alias rétro-compat conservés : `CARD = RAISED`, `CARD2 = SURFACE`, `MUTED = TEXT_DIM`, `BLUE_D = BLUE_PRESS` (l'app les importe déjà partout).

- [ ] **Step 1: Écrire le test**
```python
# tests/test_theme_tokens.py
from gui import theme

def test_token_families_present():
    for name in ("BG","SURFACE","RAISED","OVERLAY","BORDER","BORDER_SOFT",
                 "TEXT","TEXT_MUTED","TEXT_DIM","BLUE","BLUE_HOVER","BLUE_PRESS",
                 "SUCCESS","WARN","ERROR"):
        v = getattr(theme, name)
        assert isinstance(v, str) and v.startswith("#") and len(v) == 7, name

def test_scales_are_ordered():
    assert list(theme.SP.values()) == sorted(theme.SP.values())
    assert list(theme.R.values()) == sorted(theme.R.values())
    assert set(theme.TYPE) >= {"display","title","body","caption","overline"}

def test_backcompat_aliases():
    assert theme.CARD == theme.RAISED
    assert theme.MUTED == theme.TEXT_DIM
    assert theme.BLUE_D == theme.BLUE_PRESS
```

- [ ] **Step 2: Vérifier l'échec** — `python -m pytest tests/test_theme_tokens.py -q` → FAIL (attributs manquants).

- [ ] **Step 3: Implémenter** — remplacer le contenu de `gui/theme.py` :
```python
"""@file theme.py
@brief Jetons de design centralisés (source unique). import : from gui.theme import *"""

# Fonds — élévations croissantes
BG          = "#0a0f1c"
SURFACE     = "#0f172a"
RAISED      = "#182234"
OVERLAY     = "#1e293b"
BORDER      = "#263347"
BORDER_SOFT = "#1c2740"

# Texte (jamais sous TEXT_DIM pour du texte utile)
TEXT        = "#f1f5f9"
TEXT_MUTED  = "#94a3b8"
TEXT_DIM    = "#64748b"

# Marque / accent
BLUE        = "#3b82f6"
BLUE_HOVER  = "#2563eb"
BLUE_PRESS  = "#1d4ed8"
BLUE_SOFT   = "#172554"
CYAN        = "#22d3ee"

# Sémantiques
SUCCESS = "#10b981"
WARN    = "#f59e0b"
ERROR   = "#ef4444"
INFO    = "#3b82f6"

# Échelles
SP   = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}
R    = {"sm": 6, "md": 8, "lg": 12, "xl": 16}
TYPE = {"display": (22, "bold"), "title": (18, "bold"),
        "subtitle": (14, "normal"), "body": (13, "normal"),
        "caption": (11, "normal"), "overline": (9, "bold")}

# Alias rétro-compat (importés tels quels dans app_window, tab_*, etc.)
CARD  = RAISED
CARD2 = SURFACE
MUTED = TEXT_DIM
BLUE_D = BLUE_PRESS
```

- [ ] **Step 4: Vérifier** — `python -m pytest tests/test_theme_tokens.py -q` → PASS ; puis `python -m pytest -q` → **575 verts** (alias préservés).

- [ ] **Step 5: Commit** — `git add gui/theme.py tests/test_theme_tokens.py && git commit -m "feat(ui): systeme de tokens de design (couleurs, espacement, typo)"`

---

### Task 2 : Police Inter embarquée (`gui/fonts.py` + assets)

**Files:** Create `gui/fonts.py`, `assets/fonts/Inter-Regular.ttf`, `Inter-Medium.ttf`, `Inter-SemiBold.ttf`, `Inter-Bold.ttf` ; Test `tests/test_fonts.py`

**Interfaces — Produces:** `register_fonts() -> str` (retourne la famille effective : `"Inter"` si l'enregistrement réussit, sinon `"Segoe UI"`) ; constante module `FONT_FAMILY` (fixée par `register_fonts()`).

- [ ] **Step 1: Obtenir les assets** — récupérer Inter (OFL, https://github.com/rsms/inter/releases → `Inter-Regular/Medium/SemiBold/Bold.ttf`) dans `assets/fonts/`. **Si pas de réseau** : sauter cette tâche, laisser `FONT_FAMILY="Segoe UI"` (le kit fonctionne à l'identique en fallback). Vérifier présence : `python -c "import os;print([f for f in os.listdir('assets/fonts')])"`.

- [ ] **Step 2: Écrire le test**
```python
# tests/test_fonts.py
from gui import fonts

def test_register_returns_a_family():
    fam = fonts.register_fonts()
    assert fam in ("Inter", "Segoe UI")
    assert fonts.FONT_FAMILY == fam
```

- [ ] **Step 3: Vérifier l'échec** — `python -m pytest tests/test_fonts.py -q` → FAIL (module absent).

- [ ] **Step 4: Implémenter**
```python
# gui/fonts.py
"""@file fonts.py
@brief Enregistrement privé (sans installation système) de la police Inter.
Windows : AddFontResourceEx(FR_PRIVATE). Fallback Segoe UI si absent/échec."""
import os, sys, ctypes

FONT_FAMILY = "Segoe UI"

def _assets_dir() -> str:
    # PyInstaller onedir : les assets sont à cote de l'exe (_MEIPASS) ou du package.
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base, "assets", "fonts")

def register_fonts() -> str:
    global FONT_FAMILY
    d = _assets_dir()
    ttfs = [os.path.join(d, f) for f in ("Inter-Regular.ttf", "Inter-Medium.ttf",
            "Inter-SemiBold.ttf", "Inter-Bold.ttf")]
    if sys.platform == "win32" and all(os.path.exists(p) for p in ttfs):
        FR_PRIVATE = 0x10
        ok = all(ctypes.windll.gdi32.AddFontResourceExW(ctypes.c_wchar_p(p), FR_PRIVATE, 0)
                 for p in ttfs)
        if ok:
            FONT_FAMILY = "Inter"
    return FONT_FAMILY
```

- [ ] **Step 5: Vérifier** — `python -m pytest tests/test_fonts.py -q` → PASS.

- [ ] **Step 6: Commit** — `git add gui/fonts.py tests/test_fonts.py assets/fonts && git commit -m "feat(ui): police Inter embarquee (enregistrement prive + fallback)"`

---

### Task 3 : Pipeline d'icônes Lucide (`tools/gen_icons.py` + assets)

**Files:** Create `tools/gen_icons.py`, `assets/icons/*.png` (générés)

**Interfaces — Produces:** fichiers `assets/icons/<name>.png` et `<name>@2x.png` pour les ~24 noms : `search, pen-tool, zap, wrench, folder-open, save, trash-2, copy, check, alert-triangle, x, chevron-down, chevron-right, play, activity, cpu, layers, sliders, plus, rotate-cw, maximize, download, file-text, sigma`.

- [ ] **Step 1: Écrire `tools/gen_icons.py`** — rasterise les SVG Lucide (MIT, https://github.com/lucide-icons/lucide/tree/main/icons) en PNG teintés `TEXT_MUTED` (1x=20px, 2x=40px). Rendu SVG via `cairosvg` si dispo, **sinon** fallback : dessin PIL au trait pour les glyphes de la liste. Écrit dans `assets/icons/`.
```python
# tools/gen_icons.py  (dev-time, régénérable ; committe les PNG produits)
import os
NAMES = ["search","pen-tool","zap","wrench","folder-open","save","trash-2","copy",
         "check","alert-triangle","x","chevron-down","chevron-right","play","activity",
         "cpu","layers","sliders","plus","rotate-cw","maximize","download","file-text","sigma"]
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "icons")
COLOR = (148, 163, 184, 255)  # TEXT_MUTED #94a3b8

def _render_cairosvg(svg_bytes, px):
    import cairosvg
    return cairosvg.svg2png(bytestring=svg_bytes, output_width=px, output_height=px)

def main():
    os.makedirs(OUT, exist_ok=True)
    # ... récupère chaque SVG (fichier local vendored OU download), teinte stroke=COLOR,
    #     rasterise à 20 et 40 px, sauvegarde <name>.png / <name>@2x.png.
    # Fallback si cairosvg/SVG indisponible : from PIL import Image,ImageDraw -> glyphes au trait.
if __name__ == "__main__":
    main()
```
> Détail d'exécution (à l'implémentation) : soit vendoriser les 24 SVG dans `tools/lucide_svg/`, soit les télécharger une fois. Le trait Lucide est `stroke="currentColor"` : remplacer par `COLOR`. Le fallback PIL dessine des glyphes simples (loupe = cercle+trait, engrenage = étoile, etc.) — suffisant si offline.

- [ ] **Step 2: Générer** — `python tools/gen_icons.py` puis vérifier : `python -c "import os;a=os.listdir('assets/icons');print(len(a),'fichiers')"` → au moins 48 (24 × {1x,2x}).

- [ ] **Step 3: Commit** — `git add tools/gen_icons.py assets/icons && git commit -m "feat(ui): jeu d'icones Lucide rasterise (assets PNG)"`

---

### Task 4 : Kit de widgets (`gui/ui_kit.py`)

**Files:** Create `gui/ui_kit.py` ; Test `tests/test_ui_kit.py`

**Interfaces:**
- Consumes : `gui.theme` (tokens), `gui.fonts.FONT_FAMILY`, `assets/icons/*.png`.
- Produces :
  - `font(role: str, weight: str|None=None) -> ctk.CTkFont` — Inter, taille/graisse depuis `theme.TYPE[role]`.
  - `icon(name: str, size: int=20, color: str|None=None) -> ctk.CTkImage` — charge `assets/icons/<name>.png` (+@2x), cache par (name,size). `color` ignoré (PNG déjà teinté) — signature gardée pour usage futur ; **ne pas** implémenter la reteinte (YAGNI).
  - `Card(parent, **kw) -> ctk.CTkFrame` — fill `RAISED`, bordure `BORDER_SOFT`, rayon `R["lg"]`.
  - `StatCard(parent, value, label, icon_name, accent) -> ctk.CTkFrame`.
  - `PrimaryButton/SecondaryButton/GhostButton/DangerButton(parent, text, command, icon_name=None, **kw) -> ctk.CTkButton`.
  - `IconButton(parent, icon_name, command, **kw) -> ctk.CTkButton` (carré, ghost).
  - `SectionHeader(parent, text) -> ctk.CTkLabel` (overline, `TEXT_DIM`, majuscules).
  - `Field(parent, textvariable=None, placeholder="", **kw) -> ctk.CTkEntry`.

- [ ] **Step 1: Écrire le test** (headless : un seul root CTk, on ne fait pas `.mainloop()`)
```python
# tests/test_ui_kit.py
import os, pytest
os.environ.setdefault("DISPLAY", "")  # no-op Windows
ctk = pytest.importorskip("customtkinter")
from gui import ui_kit

@pytest.fixture(scope="module")
def root():
    r = ctk.CTk(); r.withdraw(); yield r; r.destroy()

def test_font_roles(root):
    f = ui_kit.font("title")
    assert f.cget("size") == 18

def test_icon_returns_image(root):
    img = ui_kit.icon("search")
    assert isinstance(img, ctk.CTkImage)

def test_factories_build(root):
    assert ui_kit.Card(root)
    assert ui_kit.StatCard(root, "17", "Composants", "cpu", "#3b82f6")
    assert ui_kit.PrimaryButton(root, "OK", lambda: None)
    assert ui_kit.GhostButton(root, "Annuler", lambda: None)
    assert ui_kit.SectionHeader(root, "MENU")
    assert ui_kit.Field(root, placeholder="chemin…")
```

- [ ] **Step 2: Vérifier l'échec** — `python -m pytest tests/test_ui_kit.py -q` → FAIL (module absent).

- [ ] **Step 3: Implémenter `gui/ui_kit.py`** — factories consommant les tokens. Squelette (l'implémenteur complète chaque fabrique sur ce modèle) :
```python
import os, sys
import customtkinter as ctk
from gui import theme
from gui.fonts import FONT_FAMILY

def _icons_dir():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base, "assets", "icons")

_ICON_CACHE = {}

def font(role, weight=None):
    size, w = theme.TYPE[role]
    return ctk.CTkFont(FONT_FAMILY, size, weight or w)

def icon(name, size=20, color=None):
    from PIL import Image
    key = (name, size)
    if key not in _ICON_CACHE:
        p1 = os.path.join(_icons_dir(), f"{name}.png")
        p2 = os.path.join(_icons_dir(), f"{name}@2x.png")
        img = Image.open(p1); img2 = Image.open(p2) if os.path.exists(p2) else img
        _ICON_CACHE[key] = ctk.CTkImage(light_image=img2, dark_image=img2, size=(size, size))
    return _ICON_CACHE[key]

def Card(parent, **kw):
    kw.setdefault("fg_color", theme.RAISED); kw.setdefault("border_color", theme.BORDER_SOFT)
    kw.setdefault("border_width", 1); kw.setdefault("corner_radius", theme.R["lg"])
    return ctk.CTkFrame(parent, **kw)

def PrimaryButton(parent, text, command, icon_name=None, **kw):
    return ctk.CTkButton(parent, text=text, command=command,
        image=icon(icon_name, 18) if icon_name else None,
        height=34, corner_radius=theme.R["md"], font=font("body", "bold"),
        fg_color=theme.BLUE, hover_color=theme.BLUE_HOVER, **kw)
# ... SecondaryButton (fg RAISED + border), GhostButton (transparent), DangerButton (ERROR),
#     IconButton (carré ghost), StatCard, SectionHeader (overline TEXT_DIM upper), Field.
```

- [ ] **Step 4: Vérifier** — `python -m pytest tests/test_ui_kit.py -q` → PASS ; `python -m pytest -q` → 575+ verts.

- [ ] **Step 5: Câbler le démarrage** — dans `app_window.py`, appeler `register_fonts()` **avant** toute création de widget (au tout début de `AppWindow.__init__` ou en tête de `run()`), pour qu'Inter soit dispo. Vérif visuelle plus tard.

- [ ] **Step 6: Commit** — `git add gui/ui_kit.py tests/test_ui_kit.py gui/app_window.py && git commit -m "feat(ui): kit de widgets (icones, boutons, cartes, champs)"`

---

### Task 5 : Assets dans le build (`packaging/analyseur.spec`)

**Files:** Modify `packaging/analyseur.spec`

- [ ] **Step 1: Ajouter les datas** — après `_DONNEES_GUI` :
```python
_ASSETS = [
    (os.path.join(RACINE, 'assets', 'fonts'), 'assets/fonts'),
    (os.path.join(RACINE, 'assets', 'icons'), 'assets/icons'),
]
```
et étendre `datas=_DONNEES_GUI + _ASSETS` dans `a_gui`.

- [ ] **Step 2: Vérifier** — `python tools/build_exe.py` → « Rapport conforme » + zip créé ; lancer l'exe, la police/les icônes se chargent (vérif visuelle vague 2).

- [ ] **Step 3: Commit** — `git add packaging/analyseur.spec && git commit -m "build: embarque assets fonts + icones dans l'exe"`

---

## VAGUE 2 — Shell + Analyser

### Task 6 : Shell (nav + marque)
**Files:** Modify `gui/app_window.py`
- [ ] Remplacer le logo `⚡` par le logo Z (`assets/icons` ou l'`app_icon`) via `ui_kit.icon`; items de nav avec icônes Lucide (`search, pen-tool, zap, wrench`) au lieu des emojis, libellés via `ui_kit.font`, contrastes déjà corrigés (garder hauteur 52 + `pack_propagate(False)`).
- [ ] **Vérif** : capturer l'app (script PowerShell existant), inspecter les 4 items + marque. `python -m pytest -q` vert.
- [ ] Commit `feat(ui): shell — marque + nav a icones nettes`.

### Task 7 : Analyser — header + KPI
**Files:** Modify `gui/tab_analyze.py`
- [ ] Header héro (`font("display")` + sous-titre `TEXT_MUTED`) ; les 4 KPI passent en `ui_kit.StatCard` (icônes `cpu/check/activity/alert-triangle`, grand nombre, élévation `RAISED`). Boutons `Parcourir`=Secondary, `Charger demo`=Ghost, `Analyser`=Primary(`play`).
- [ ] **Vérif** : capture (charger un circuit démo), inspecter KPI + cartes non rognées. Tests verts.
- [ ] Commit.

### Task 8 : Analyser — vue résultats + état vide
**Files:** Modify `gui/tab_analyze.py`
- [ ] Cartes de montage en `ui_kit.Card`, `SectionHeader` pour « STRUCTURE EN ÉTAGES », chips Z cliquables cohérents, accordéon d'îlot avec chevrons (`chevron-down/right`). État vide avec `icon("file-text", 48)`. Barre basse : boutons presets.
- [ ] **Vérif** : capture avec `ilot_reel_fanout_filtres_rlc.xml`, confirmer aucun rognage (défaut #4 de l'audit), lisibilité. Tests verts.
- [ ] Commit.

---

## VAGUE 3 — Schéma

### Task 9 : `tab_draw` — toolbar/header
**Files:** Modify `gui/tab_draw.py`
- [ ] Header + barre basse via kit (`Ouvrir`=Secondary(`folder-open`), `Enregistrer`=Secondary(`save`), `Analyser ce circuit`=Primary(`play`), `Enregistrer comme pattern`=Primary bleu). Légende raccourcis déjà retirée (dans la palette).
- [ ] **Vérif** capture. Tests verts. Commit.

### Task 10 : `schematic_editor` — re-thème tkinter
**Files:** Modify `gui/schematic_editor.py`
- [ ] Remplacer les hex en dur (`#1e293b`, `#334155`, `#141e2e`…) par des refs `theme.*` ; police des labels palette/status en `theme.FONT_... (Inter via tk font)` ; boutons palette + actions (`Supprimer`=`trash-2`, `Effacer tout`, `Ajuster`=`maximize`) alignés ; couleur de grille du canvas depuis `theme`. Garder largeur palette 174 (Task précédente d'audit).
- [ ] **Vérif** : capture de l'onglet Schéma, palette lisible + cohérente avec le reste. Tests verts. Commit.

---

## VAGUE 4 — Circuits + Composants

### Task 11 : `tab_circuits`
**Files:** Modify `gui/tab_circuits.py`
- [ ] Listes/cartes en `ui_kit.Card` + `SectionHeader`, boutons presets, champs `Field`.
- [ ] **Vérif** capture. Tests verts. Commit.

### Task 12 : `tab_components`
**Files:** Modify `gui/tab_components.py`
- [ ] Idem (bibliothèque de composants).
- [ ] **Vérif** capture. Tests verts. Commit.

---

## VAGUE 5 — Rendu des schémas

### Task 13 : Couleurs des dessins depuis les tokens
**Files:** Modify `gui/circuit_viewer.py`, `gui/impedance_schematic.py`
- [ ] Faire pointer les constantes de rendu vers les tokens **sans assombrir le canvas** :
  `_Z_EDGE = theme.BLUE_HOVER` (#2563eb, déjà proche), `_TITRE_COLOR = theme.OVERLAY`/slate, `_GAIN_COLOR` inchangé (teal lisible). `_WIRE`, `_Z_FILL`, `_OPAMP_FILL` restent **clairs** (fond blanc du schéma). Centraliser ces valeurs en tête de fichier avec un commentaire « alignées tokens ».
- [ ] Soigner le drill-down « 1 AOP + 3 Z » (`impedance_schematic`) : cohérence des labels/bornes.
- [ ] **Vérif** : régénérer les 60 PNG d'îlots (script scratch `gen_ilots.py`), inspecter un échantillon transistors — aucun changement de structure, accents cohérents. `python -m pytest -q` → tous verts (les tests ne bloquent pas sur les hex).
- [ ] Commit.

---

## FINALISATION
- [ ] `python -m pytest -q` → tous verts.
- [ ] `python tools/build_exe.py` → exe 1.7.x, smoke conforme.
- [ ] Balayage de captures des 4 onglets + échantillon d'îlots → validation visuelle boss.
- [ ] Mettre à jour la mémoire (nouveau système de design) si pertinent.

## Auto-revue (writing-plans)
- **Couverture spec** : tokens (T1), Inter (T2), icônes (T3), kit (T4), build assets (T5), shell (T6), Analyser (T7-8), Schéma (T9-10), Circuits/Composants (T11-12), rendu (T13). ✔ tous les points du spec ont une tâche.
- **Placeholders** : les seams testables ont des tests réels ; le visuel a une vérif capture explicite par tâche (nature GUI). Le détail de rasterisation d'icônes est le seul point laissé à l'exécution (source SVG vendored/download + fallback PIL) — borné et documenté.
- **Cohérence des types** : `FONT_FAMILY` (fonts→ui_kit), `icon()/font()/Card/StatCard/*Button/SectionHeader/Field` (ui_kit→écrans), tokens (theme→partout) — signatures constantes d'une tâche à l'autre.
