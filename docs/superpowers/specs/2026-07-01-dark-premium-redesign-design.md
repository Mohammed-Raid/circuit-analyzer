# Refonte « Dark Premium » — Design

**But :** hisser Circuit Analyzer d'un thème sombre fonctionnel à une UI sombre *premium* et cohérente (niveau Linear/Vercel), sur toute l'app (4 onglets) + l'esthétique des schémas, pour une démo qui en impose.

**Décisions verrouillées (brainstorming 2026-07-01) :**
- Direction : **Dark premium** (on élève l'existant, on ne change pas d'identité).
- Périmètre : **toute l'app** — Analyser, Schéma, Circuits, Composants + rendu des schémas.
- Approche : **tokens + kit de widgets, migration écran par écran** (pas de restyle en place).
- Typo : **Inter embarquée** dans l'exe.
- Icônes : **jeu Lucide (MIT) rasterisé** en PNG, chargé via `CTkImage`.

**Stack :** Python, CustomTkinter (+ tkinter brut pour l'éditeur de schéma), matplotlib/schemdraw (rendu), PyInstaller.

## Contraintes / plafonds (honnêtes)
- CustomTkinter **n'a pas d'ombres réelles ni d'animations riches** → profondeur *simulée* (bordure + fill légèrement plus clair), transitions limitées aux états hover/press natifs.
- L'éditeur de schéma (`schematic_editor.py`) est en **tkinter brut** : pas de widgets CTk dedans → on le re-thème à la main avec les mêmes tokens (couleurs, police Inter via police Tk).
- Police bundlée chargée **sans installation système** via `AddFontResourceEx(..., FR_PRIVATE)` (Windows) au démarrage — l'app est Windows-only.
- Les icônes sont **pré-rasterisées au dev-time** en PNG committés (`assets/icons/`) → **aucune dépendance SVG au runtime**, on charge juste des PNG.

---

## 1. Fondation — design tokens (`gui/theme.py` étendu)

**Couleurs (élévations de fond) :**
| token | hex | usage |
|---|---|---|
| `BG` | `#0a0f1c` | canvas de l'app |
| `SURFACE` | `#0f172a` | sidebar, header |
| `RAISED` | `#182234` | cartes |
| `OVERLAY` | `#1e293b` | inputs, popovers, hover de carte |
| `BORDER` | `#263347` | bordures |
| `BORDER_SOFT` | `#1c2740` | séparateurs discrets |

**Texte (jamais sous `#64748b` pour du texte utile) :**
`TEXT #f1f5f9` · `TEXT_MUTED #94a3b8` · `TEXT_DIM #64748b`.

**Marque / accent :** `BLUE #3b82f6` · `BLUE_HOVER #2563eb` · `BLUE_PRESS #1d4ed8` · `BLUE_SOFT #172554` (fond bleuté discret). Accent secondaire `CYAN #22d3ee` (parcimonie).

**Sémantiques :** `SUCCESS #10b981` · `WARN #f59e0b` · `ERROR #ef4444` · `INFO #3b82f6` (+ variantes « soft » pour fonds).

**Espacement (rythme 8) :** `SP = {xs:4, sm:8, md:12, lg:16, xl:24, xxl:32}`.
**Rayons :** `R = {sm:6, md:8, lg:12, xl:16}`.
**Typo (rôles → CTkFont Inter) :** `display 22/bold` · `title 18/semibold` · `subtitle 14/medium` · `body 13/regular` · `caption 11/medium` · `overline 9/bold uppercase`. **Valeurs R/L/C en mono** = `Consolas` (présent sur Windows, zéro asset).

## 2. Kit de widgets (`gui/ui_kit.py`, nouveau)
Fabriques réutilisables, une responsabilité chacune :
- `icon(name, size=18, color=TEXT_MUTED) -> CTkImage` — cache de PNG Lucide teintés.
- `font(role) -> CTkFont` — Inter par rôle.
- `Card(parent, pad=SP.lg)` — CTkFrame `RAISED` + `BORDER_SOFT` + rayon `lg`.
- `StatCard(parent, value, label, icon_name, accent)` — carte KPI (icône + grand nombre + libellé).
- `PrimaryButton / SecondaryButton / GhostButton / DangerButton / IconButton` — presets CTkButton (couleur, hauteur 34, rayon `md`, Inter, hover).
- `SectionHeader(parent, text)` — libellé `overline` tracké, `TEXT_DIM`.
- `Field(parent, ...)` — entry stylée (fond `OVERLAY`, bordure, focus bleu).

**Jeu d'icônes Lucide (~24) :** search, pen-tool, zap, wrench, folder-open, save, trash-2, copy, check, alert-triangle, x, chevron-down, chevron-right, play, activity, cpu, layers, sliders, plus, rotate-cw, maximize, download, file-text, sigma. Rendues mono aux couleurs du thème (1x + 2x) → `assets/icons/`.

**Police :** `assets/fonts/Inter-*.ttf` embarqués ; enregistrement privé au démarrage (`gui/fonts.py`, `AddFontResourceEx`). Fallback Segoe UI si l'enregistrement échoue.

## 3. Écrans (migration vers le kit)
- **Shell (`app_window.py`)** : lockup de marque = logo Z (image) + « Circuit Analyzer » ; items de nav via `IconButton`-like (déjà : hauteur fixe + contrastes corrigés), footer propre.
- **Analyser (`tab_analyze.py`)** : header héro ; KPI en `StatCard` (icônes Lucide, grand nombre, élévation) ; vue résultats en `Card` (cartes de montage, accordéon d'îlot, *chips* Z cliquables) ; état vide avec icône `file-text`.
- **Schéma (`tab_draw.py` + `schematic_editor.py`)** : **re-thème de la palette/canvas tkinter** sur les tokens (fini les hex en dur), toolbar en `IconButton`, couleur de grille du canvas depuis les tokens.
- **Circuits / Composants (`tab_circuits.py`, `tab_components.py`)** : listes/cartes/formulaires cohérents (`Card`, `Field`, boutons presets).

## 4. Rendu des schémas (`gui/circuit_viewer.py`, `impedance_schematic.py`)
- Les constantes couleur (`_WIRE, _Z_FILL, _Z_EDGE, _OPAMP_FILL, _GAIN_COLOR, _TITRE_COLOR`) **tirées d'une source unique** alignée sur les tokens (cohérence app ↔ dessin).
- Typo des labels cohérente ; soigner le moment signature **« 1 AOP + 3 Z au clic »** (drill-down).
- Les tests existants restent verts : ils vérifient structure/hitboxes/positions, **pas les hex exacts**.

## 5. Micro-interactions
Hover/press sur tous les boutons, anneau de focus bleu sur les inputs, hiérarchie de boutons claire (primaire bleu / secondaire outline / ghost / danger rouge), chevrons d'accordéon.

---

## Exécution — en vagues, chacune vérifiée
1. **Fondation** : tokens + `ui_kit` + Inter + assets d'icônes. Vérif : écran-démo listant tokens/icônes/boutons.
2. **Shell + Analyser**.
3. **Schéma** (inclut re-thème tkinter).
4. **Circuits + Composants**.
5. **Rendu des schémas**.

Chaque vague : **captures de l'app réelle** inspectées + **suite de tests verte** + smoke build. Rebuild `.exe` en fin de chantier.

## Tests / vérification
- GUI difficilement testable unitairement → **vérification par capture** (méthode validée par le boss) + les **575 tests existants restent verts** à chaque vague.
- Un **smoke test** léger : l'app démarre, `ui_kit.icon(...)` charge un PNG, la police Inter s'enregistre (ou fallback).
- Rendu : les tests `circuit_viewer` (structure/hitboxes) protègent contre la casse ; on inspecte les PNG d'îlots après la vague 5.

## Hors périmètre (YAGNI)
Pas de mode clair, pas de thèmes multiples, pas de système d'animation, pas de refonte d'architecture non-UI, pas de i18n. Les shims de compat et fichiers parasites (`skidl_REPL.*`) ne sont pas concernés.
