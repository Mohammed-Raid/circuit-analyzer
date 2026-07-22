"""
@file circuit_viewer.py
@brief Visualiseur de schémas (schemdraw 0.22 + backend matplotlib TkAgg).

Chaque pattern de circuit détecté a sa propre fonction de dessin, enregistrée
dans _DRAWERS. Les fonctions _draw_* reçoivent toutes (d, result, ci) :
  @param d Dessin schemdraw en cours.
  @param result Match du circuit détecté.
  @param ci Dict {ref -> infos composant} (comp_info).
"""
import logging
import math

import customtkinter as ctk
import tkinter as tk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as mpatches
import schemdraw
import schemdraw.elements as elm
from circuit_analyzer.patterns.base import (
    is_ground_net,
    is_power_net,
    is_protective_earth_net,
)
from gui import theme
from gui import ui_kit
from gui.schema_labels import ajuster_labels, obtenir_renderer
from gui.theme import BLUE_HOVER

_log = logging.getLogger(__name__)

SCH_BG  = theme.SCHEMA_COLORS["SCH_BG"]   # light background — standard for schematics

_COMP_COLORS = dict(theme.SCHEMA_COLORS["COMP"])

# --- Couleurs de rendu du schéma — alignées tokens --------------------------
# Directive boss : le canvas des schémas reste CLAIR (fond SCH_BG #fafafa,
# standard pour les schémas électroniques). Toutes les couleurs sont lues
# depuis theme.SCHEMA_COLORS (source unique, Task 3) ; les fonds clairs et
# l'encre (_WIRE, _Z_FILL, _OPAMP_FILL) restent des couleurs de canvas clair,
# pas des tokens de surface sombre — mais leur VALEUR vit désormais dans
# theme.py, pas ici.
_BUS = theme.SCHEMA_COLORS["BUS"]           # bus/nets — gris ardoise moyen, lisible sur clair
_WIRE = theme.SCHEMA_COLORS["WIRE"]         # fils/encre — slate foncé, lisible sur SCH_BG
_LBL_OFST = 0.25           # décalage des labels de net pour les décoller des symboles

# Boîtes Z : remplissage bleu clair + contour bleu. Double rôle — rend le
# schéma plus lisible ET signale visuellement que la boîte est cliquable.
_Z_FILL = theme.SCHEMA_COLORS["Z_FILL"]     # remplissage clair (canvas clair, non touché)
_Z_EDGE = theme.SCHEMA_COLORS["Z_EDGE"]     # alignée tokens = theme.BLUE_HOVER (#2563eb)
_OPAMP_FILL = theme.SCHEMA_COLORS["OPAMP_FILL"]   # triangle AOP légèrement teinté (canvas clair, non touché)

_TITRE_COLOR = theme.SCHEMA_COLORS["TITRE"]   # rôle de l'étage — alignée tokens = theme.OVERLAY (#1e293b, slate foncé lisible sur clair)
_GAIN_COLOR = theme.SCHEMA_COLORS["GAIN"]     # gain de l'étage (teal) — inchangé, déjà lisible


def _figure_pixel_size(fig):
    """@brief Taille native d'une figure Matplotlib en pixels."""
    w, h = fig.get_size_inches()
    return max(1, int(round(w * fig.dpi))), max(1, int(round(h * fig.dpi)))


_VIEWER_ZOOM_STEP = 1.15
_VIEWER_ZOOM_MIN = 0.3
_VIEWER_ZOOM_MAX = 3.0


def _zoom_next_scale(current, wheel_delta):
    """@brief Calcule le prochain zoom borne pour un evenement molette."""
    factor = _VIEWER_ZOOM_STEP if wheel_delta > 0 else 1 / _VIEWER_ZOOM_STEP
    return max(_VIEWER_ZOOM_MIN, min(_VIEWER_ZOOM_MAX, current * factor))


_ISLAND_ZOOM_MIN = 0.5
_ISLAND_ZOOM_MAX = 3.0
_ISLAND_ZOOM_STEP = 1.25
# Bornes larges du bouton « Ajuster à la fenêtre » — distinctes des bornes
# manuelles ci-dessus : Ajuster peut poser un facteur hors [0.5, 3.0] (ex.
# chaîne de 7 AOP très large -> facteur < 0.5) ; les boutons -/+ repartiront
# ensuite normalement de ce facteur via `_island_zoom_next`, qui les
# re-clampera vers 0.5/3.0 si besoin (comportement documenté, pas un bug).
_ISLAND_AJUSTER_MIN = 0.15
_ISLAND_AJUSTER_MAX = 3.0
# Paddings internes du `canvas_frame` à déduire pour mesurer le viewport utile
# du schéma : le chemin plein-cadre ET le chemin défilant packent leur widget
# avec padx=4/pady=4 (8px par dimension) ; le chemin défilant réserve en plus
# des barres de défilement Tk (~15px) — réservées par prudence même si elles
# ne s'affichent pas forcément, pour ne jamais surestimer l'espace utile.
_ISLAND_VIEWPORT_PAD = 8 + 15
# Largeur (pouces, dpi 100) au-dela de laquelle le popup ilot bascule en
# defilement horizontal plutot que de tasser le schema. Alignee sur la
# largeur utile du popup 1200px (audit fenetre F6).
_ISLAND_DEFILE_WIDTH_IN = 11.6

# Clic sur une puce "Composants : ..." -> centrage + surbrillance (section A).
_CHIP_HIGHLIGHT_RADIUS = 0.8       # unites data, cf. design
_CHIP_HIGHLIGHT_DELAY_MS = 1400
# Clic = FOCUS (demande utilisateur 2026-07-07) : si le zoom courant est sous
# ce facteur, on y monte d'abord (la vue devient defilante) puis on centre le
# composant -- « centrer » = s'en approcher, pas seulement l'entourer. Un zoom
# manuel deja superieur est conserve.
_CHIP_FOCUS_FACTEUR = 2.0
# Duree d'affichage du message « X n'est pas dessiné dans cette vue » (barre
# basse) apres un clic sur une puce indisponible.
_CHIP_MSG_DELAY_MS = 2500
# Export PNG cadre sur le contenu reel (section B) : marge uniforme en
# unites data appliquee de chaque cote de la bbox de contenu avant savefig.
_EXPORT_MARGE_DATA = 0.5

_Z_DETAIL_PERP_MIN_SCALE = 0.85
_Z_DETAIL_LABEL_AXIS_EPS = 0.05
# 7 illisible en fenetre compressee (audit fenetre F2) ; 8 reste compact tout
# en restant net une fois la figure redimensionnee dans le popup.
_Z_DETAIL_LABEL_FONTSIZE = 8
_Z_DETAIL_LABEL_CLEAR = 0.3
# Degagement vertical (branche horizontale) : doit couvrir l'amplitude du
# zigzag/de la spirale (~0.25 unite) + marge, sinon le label chevauche les
# crêtes (audit fenetre F1).
_Z_DETAIL_LABEL_CLEAR_VERT = 0.5
_Z_DETAIL_COMPACT_LABEL_SCALE = 0.65
_Z_DETAIL_COMPACT_INLINE_MAX = 3
# 0.45 laissait l'etiquette "VCC" du montage appelant frôler la premiere
# branche decalee (ex. L1 du reseau darlington+relais) -> 0.6 degage le texte
# voisin d'au moins 0.4 unite (audit fenetre F5).
_Z_DETAIL_COMPACT_SIDE_CLEAR = 0.6
# 0.55 collait zigzags/bobines des branches paralleles (labels sur symboles) ;
# 0.9 laisse respirer sans envahir les voisins (verifie sur le sweep bimode).
_Z_DETAIL_COMPACT_PERP_SCALE = 0.9
# Degagement label/rail pour les branches verticales d'un reseau decale (F2) :
# le rail est a `rang max`, on veut le label AU-DESSUS, jamais dans l'entrefer
# etroit symbole<->rail (souvent < 0.25 unite, insuffisant pour un label lisible).
_Z_DETAIL_COMPACT_RAIL_CLEAR = 0.14
# Longueur minimale absolue (unites schemdraw) sous laquelle un symbole
# periodique (zigzag Resistor, spirale Inductor2) deborde de ses propres
# bornes au lieu de se compresser proprement (audit fenetre F3/F4).
_Z_DETAIL_SYMBOL_MIN_LEN = 1.0
_Z_BOX_LABEL_FONTSIZE = 10
# Taille UNIQUE des labels satellites (« Rb = 10 kΩ », Rc/Re/Rg...) : trois
# tailles coexistaient (14 heritee du d.config global via _r_simple, 8 et 9
# explicites selon le drawer) pour le meme role visuel. Contrat =
# tests/test_labels_satellites.py.
_SATELLITE_LABEL_FONTSIZE = 9


def _island_zoom_next(current, direction):
    """@brief Calcule le prochain facteur de zoom pour les boutons -/100%/+
    de la fenêtre îlot (distinct du zoom molette du viewport scrollable).

    @param current Facteur courant.
    @param direction "in" (bouton +), "out" (bouton -) ou "reset" (bouton 100 %).
    @return Facteur borné [_ISLAND_ZOOM_MIN, _ISLAND_ZOOM_MAX].
    """
    if direction == "reset":
        return 1.0
    factor = (current * _ISLAND_ZOOM_STEP if direction == "in"
              else current / _ISLAND_ZOOM_STEP)
    return max(_ISLAND_ZOOM_MIN, min(_ISLAND_ZOOM_MAX, factor))


def _zoom_scroll_fractions(old_size, new_size, viewport, pointer, canvas_origin):
    """@brief Fractions x/y pour garder le point sous la souris pendant le zoom.

    @param old_size Taille scrollregion avant zoom.
    @param new_size Taille scrollregion apres zoom.
    @param viewport Taille visible du canvas.
    @param pointer Position souris dans le viewport.
    @param canvas_origin Coordonnees monde du coin visible avant zoom.
    """
    old_w, old_h = old_size
    new_w, new_h = new_size
    px, py = pointer
    ox, oy = canvas_origin

    scale_x = new_w / old_w if old_w else 1.0
    scale_y = new_h / old_h if old_h else 1.0
    target_x = (ox + px) * scale_x - px
    target_y = (oy + py) * scale_y - py
    # Convention Tk (cf. `_fraction_centree`) : `xview_moveto(f)` place le
    # bord gauche a `f * new_w` -- denominateur = taille totale, sans quoi le
    # point sous la souris derive pendant le zoom molette.
    fx = max(0.0, min(1.0, target_x / max(1, new_w)))
    fy = max(0.0, min(1.0, target_y / max(1, new_h)))
    return fx, fy


def _position_composant(fig, ref):
    """@brief Position (x, y) DATA d'un composant dans une figure d'ilot deja
    construite -- utilisee par le clic sur une puce « Composants : ... » pour
    centrer la vue et poser l'anneau de surbrillance dessus.

    Trois sources, dans l'ordre :
      1. `fig._comp_positions` (registre rempli AU MOMENT DU DESSIN par les
         drawers -- cf. `_enregistrer_position` -- seule source qui couvre les
         composants dont le SCHEMA n'affiche que le role, jamais la reference
         brute : Q/M/U des montages transistor/AOP -- leur titre est un role,
         pas "Q1" -- et les satellites Rb/Rc/Re/Rg/diode de roue
         libre/bobine de relais, dessines en symbole reel avec une etiquette
         de role (« Rb = 10 kΩ »), jamais leur ref).
      2. `fig._z_hitboxes` (zones cliquables des boites Z, cf. `_make_fig`) :
         si `ref` figure dans les refs d'une hitbox, le centre de sa boite.
      3. un `Text` d'un axe dont le contenu COMMENCE par `ref` sur une
         frontiere de mot (« R5 », « Rb = 10k », « C1\\n100nF » matchent pour
         ref="R5"/"Rb"/"C1" ; « R51 » NE matche PAS ref="R5").

    @param fig Figure matplotlib d'ilot (porte fig._comp_positions/_z_hitboxes).
    @param ref Reference recherchee (ex. "R5").
    @return (x, y) en coordonnees data, ou None si introuvable.
    """
    positions = getattr(fig, "_comp_positions", None) or {}
    if ref in positions:
        return positions[ref]
    for x0, x1, y0, y1, refs, _composition in getattr(fig, "_z_hitboxes", None) or ():
        if ref in (refs or ()):
            return (x0 + x1) / 2.0, (y0 + y1) / 2.0
    for ax in fig.axes:
        for t in ax.texts:
            texte = t.get_text()
            if not texte.startswith(ref):
                continue
            suivant = texte[len(ref):len(ref) + 1]
            if not suivant or not suivant.isalnum():
                return t.get_position()
    return None


def _fraction_centree(cible_px, total_px, viewport_px):
    """@brief Fraction xview/yview (Tk Canvas) pour CENTRER `cible_px` dans un
    viewport de `viewport_px` pixels, sur une scrollregion de `total_px`
    pixels.

    Convention Tk : `xview_moveto(f)` place le bord gauche visible a
    `f * total_px` -- le denominateur est la taille TOTALE de la scrollregion,
    PAS `total - viewport` (l'erreur historique : elle sur-defilait d'un
    facteur total/(total-viewport), d'autant plus que la cible etait loin --
    audit 2026-07-08 : 317/344 centrages rates). Tk clampe lui-meme au bord si
    la fraction depasse le defilement possible ; le clamp [0, 1] ici couvre
    les cibles dans la premiere demi-fenetre."""
    bord_gauche_vise = cible_px - viewport_px / 2.0
    return max(0.0, min(1.0, bord_gauche_vise / max(1, total_px)))


def _bind_scrollable_mpl_events(widget, on_mousewheel, on_pan_start, on_pan_drag):
    """@brief Ajoute scroll/pan sans ecraser les bindings Tk de Matplotlib."""
    widget.bind("<MouseWheel>", on_mousewheel, add="+")
    widget.bind("<ButtonPress-1>", on_pan_start, add="+")
    widget.bind("<B1-Motion>", on_pan_drag, add="+")


def _is_rail_net(net: str) -> bool:
    return bool(net) and (
        is_ground_net(net) or is_power_net(net) or is_protective_earth_net(net)
    )


def _info_for_ref(ref: str, graph, comp_info: dict) -> dict:
    info = dict(comp_info.get(ref, {}) or {})
    if info.get("pins"):
        return info
    comp = getattr(graph, "graph", {}).get("components", {}).get(ref)
    if comp is None:
        return info
    info.setdefault("type", getattr(comp, "type", "?"))
    info.setdefault("value", getattr(comp, "value", ""))
    info.setdefault("pins", getattr(comp, "pins", {}))
    info.setdefault("boite_ic", getattr(comp, "boite_ic", False))
    return info


def _build_island_model(ilot: dict, graph, comp_info: dict) -> dict:
    """@brief Modele d'ilot au niveau « Impedance Z ».

    Construit depuis le graphe reduit (impedance.reduire) : chaque dipole passif
    (R/L/C combine ou seul) devient une unite « Z » horizontale portant ses
    composants bruts (refs) pour le drill-down ; les diodes restent des diodes ;
    les composants multi-broches (AOP, transistors) restent dessines tels quels.

    @param ilot Ilot detecte (cle 'composants' = refs bruts).
    @param graph Graphe brut (porte graph['components']).
    @param comp_info Dict {ref -> {type, value, pins}}.
    @return dict {label, components} ou chaque unite porte refs + composition.
    """
    from circuit_analyzer import impedance

    island_refs = set(ilot.get("composants", []))
    reduit = impedance.reduire(graph)
    raw_comps = getattr(graph, "graph", {}).get("components", {}) or {}

    units = []
    consumed = set()
    z_index = 0
    for u, v, data in reduit.edges(data=True):
        ref = data.get("ref")
        refs = list(data.get("refs") or ([ref] if ref else []))
        if not (set(refs) & island_refs):
            continue
        consumed.update(refs)
        composition = data.get("composition") or " + ".join(refs)
        typ = data.get("type")
        if typ == "D":
            comp = raw_comps.get(ref)
            pins = dict(getattr(comp, "pins", {}) or {})
            units.append({
                "ref": ref, "type": "D",
                "value": getattr(comp, "value", "") if comp else "",
                "pins": {"A": pins.get("A", u), "K": pins.get("K", v)},
                "symbol": "diode", "refs": refs, "composition": composition,
            })
        elif typ in {"R", "L", "C", "Z"}:
            z_index += 1
            detail_info = {r: _info_for_ref(r, graph, comp_info) for r in refs}
            units.append({
                "ref": f"Z{z_index}", "type": "Z", "value": "",
                "pins": {"1": u, "2": v},
                "symbol": "impedance", "refs": refs, "composition": composition,
                "detail_info": detail_info,
            })
        else:
            # autre dipole 2 bornes (ex. relais) : on garde son symbole/ref.
            comp = raw_comps.get(ref)
            units.append({
                "ref": ref, "type": typ,
                "value": getattr(comp, "value", "") if comp else "",
                "pins": {"1": u, "2": v},
                "symbol": _schematic_symbol(typ), "refs": refs, "composition": composition,
            })

    # Composants multi-broches (AOP, transistors) : pas des aretes 2 bornes.
    for ref in sorted(island_refs - consumed):
        info = _info_for_ref(ref, graph, comp_info)
        pins = dict(info.get("pins", {}) or {})
        if len(pins) <= 2:
            continue
        units.append({
            "ref": ref, "type": info.get("type", "?"),
            "value": info.get("value", ""), "pins": pins,
            "symbol": _schematic_symbol(info.get("type", "?")),
            "refs": [ref], "composition": ref,
            "boite_ic": info.get("boite_ic", False),
        })

    return {"label": ilot.get("label", "Ilot"), "components": units}


def _build_dipole_model(refs, graph, comp_info, label="Detail Z") -> dict:
    """@brief Modele brut (R/L/C reels) des composants d'un dipole Z, pour le drill-down.

    @param refs Refs bruts composant le Z.
    @param graph Graphe brut.
    @param comp_info Dict {ref -> {...}}.
    @param label Titre du sous-schema.
    @return dict {label, components} avec symboles reels (resistor/capacitor/...).
    """
    units = []
    for ref in refs:
        info = _info_for_ref(ref, graph, comp_info)
        units.append({
            "ref": ref, "type": info.get("type", "?"),
            "value": info.get("value", ""),
            "pins": dict(info.get("pins", {}) or {}),
            "symbol": _schematic_symbol(info.get("type", "?")),
            "refs": [ref], "composition": ref,
        })
    return {"label": label, "components": units}


# ── Public entry point ────────────────────────────────────────────────────────

def _texte_gain(result, graph):
    """@brief Texte du gain pour l'entête : symbolique + numérique si évaluable.

    @param result Match (porte 'gain' symbolique et éventuellement 'impedances').
    @param graph Graphe d'origine (pour évaluer numériquement), ou None.
    @return str|None « Av = −Zf/Zin = -20 » (résistif) / « … (|Av|≈3.2 à 1000 Hz) »
            (réactif) / « Av = −Zf/Zin » si non évaluable, ou None si pas de gain.
    """
    if result and result.get("expression"):
        return result["expression"]
    g = result.get("gain")
    if not g:
        return None
    imp = result.get("impedances")
    if imp and graph is not None:
        from circuit_analyzer import impedance
        zin = imp.get("Zin")
        if "Zg" in imp:        # non-inverseur : Av = 1 + Zf/Zg
            num = impedance.gain_non_inverseur(
                graph, imp["Zf"]["composition"], imp["Zg"]["composition"])
        elif isinstance(zin, dict):   # inverseur / intégrateur / dérivateur : Av = −Zf/Zin
            num = impedance.gain_inverseur(
                graph, zin["composition"], imp["Zf"]["composition"])
        else:                  # sommateur (Zin = liste d'entrées) : pas d'Av scalaire
            num = None
        if num:
            return f"Av = {g}  ({num})" if num.startswith("|Av|") else f"Av = {g} = {num}"
    return f"Av = {g}"


def _suivre_curseur_z(canvas, fig):
    """@brief Curseur « main » au survol d'une boîte Z cliquable (découvrabilité).

    @return Le cid `mpl_connect` — l'appelant DOIT le garder (aux côtés de
        celui du clic) pour pouvoir le `mpl_disconnect` lors du teardown
        déterministe (cf. `monter_canvas` / démontage §3), sans quoi le
        callback (qui ferme sur `fig`) reste vivant dans la CallbackRegistry
        du canvas et retarde la libération de la figure remplacée.
    """
    widget = canvas.get_tk_widget()
    def _on_motion(event):
        over = event.xdata is not None and event.ydata is not None and any(
            x0 <= event.xdata <= x1 and y0 <= event.ydata <= y1
            for x0, x1, y0, y1, *_ in getattr(fig, "_z_hitboxes", []))
        widget.configure(cursor="hand2" if over else "")
    return canvas.mpl_connect("motion_notify_event", _on_motion)


def show_circuit(result: dict, comp_info: dict, parent=None, graph=None):
    """@brief Ouvre une fenêtre affichant le schéma d'un circuit détecté.

    @param result Match du circuit détecté (type, composants, nœuds).
    @param comp_info Dict {ref -> {type, value, pins}} des composants.
    @param parent Fenêtre parente (optionnel).
    @param graph Graphe du circuit, requis pour le clic drill-down sur les boîtes Z (optionnel).
    @return None
    """
    name    = result["circuit_type"]
    drawer  = _DRAWERS.get(name)

    popup = ctk.CTkToplevel(parent)
    popup.title(f"Schéma — {name}")
    popup.geometry("960x560")
    popup.configure(fg_color=theme.SURFACE)
    popup.grab_set()

    # Header
    hdr = ctk.CTkFrame(popup, fg_color=theme.OVERLAY, corner_radius=0, height=54)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    ctk.CTkLabel(hdr, text=f"⚡  {name}",
                 font=ctk.CTkFont("Segoe UI", 14, "bold"),
                 text_color=theme.TEXT).pack(side="left", padx=18, pady=14)
    _gain_txt = _texte_gain(result, graph)
    if _gain_txt:
        ctk.CTkLabel(hdr, text=_gain_txt,
                     font=ctk.CTkFont("Consolas", 12, "bold"),
                     text_color=theme.SUCCESS_SOFT).pack(side="right", padx=18)

    # Component chips
    chips = ctk.CTkFrame(popup, fg_color=theme.SURFACE)
    chips.pack(fill="x", padx=14, pady=(8, 2))
    ctk.CTkLabel(chips, text="Composants :",
                 font=ctk.CTkFont("Segoe UI", 10),
                 text_color=theme.TEXT_DIM).pack(side="left")
    for ref in result["components"]:
        info = comp_info.get(ref, {})
        val  = info.get("value", "")
        typ  = info.get("type", "?")
        txt  = f" {ref} {val} ".strip()
        color = _COMP_COLORS.get(typ, theme.NEUTRAL)
        ctk.CTkLabel(chips, text=txt,
                     font=ctk.CTkFont("Consolas", 10, "bold"),
                     fg_color=color, text_color=theme.WHITE,
                     corner_radius=4).pack(side="left", padx=3)

    # Schematic area
    fig = _make_fig(result, comp_info, drawer)
    canvas_frame = ctk.CTkFrame(popup, fg_color=SCH_BG, corner_radius=10)
    canvas_frame.pack(fill="both", expand=True, padx=14, pady=(4, 0))

    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().configure(bg=SCH_BG, highlightthickness=0)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

    # Clic sur une boîte Z -> détail R/L/C (drill-down série/parallèle existant).
    def _on_click(event):
        if graph is None or event.xdata is None or event.ydata is None:
            return
        for x0, x1, y0, y1, refs, composition in getattr(fig, "_z_hitboxes", []):
            if x0 <= event.xdata <= x1 and y0 <= event.ydata <= y1:
                show_dipole_detail(refs, composition, graph, comp_info, popup)
                return
    canvas.mpl_connect("button_press_event", _on_click)
    if graph is not None:
        _suivre_curseur_z(canvas, fig)

    # Bottom bar
    bar = ctk.CTkFrame(popup, fg_color=theme.OVERLAY, corner_radius=0, height=44)
    bar.pack(fill="x", side="bottom")
    bar.pack_propagate(False)
    ctk.CTkButton(bar, text="💾  Exporter PNG",
                  width=140, height=30, corner_radius=6,
                  font=ctk.CTkFont("Segoe UI", 11),
                  fg_color=theme.BLUE_PRESS, hover_color=theme.BLUE_HOVER,
                  command=lambda: _export(fig, name, popup)).pack(
                      side="left", padx=12, pady=7)
    ctk.CTkButton(bar, text="Fermer",
                  width=90, height=30, corner_radius=6,
                  font=ctk.CTkFont("Segoe UI", 11),
                  fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                  command=popup.destroy).pack(side="right", padx=12, pady=7)


# ── Figure builder ────────────────────────────────────────────────────────────

def _ilot_a_composant_actif(refs, raw_comps) -> bool:
    """@brief Vrai si l'îlot contient un composant actif multi-broches (AOP, transistor).

    Un tel îlot ne doit pas être réduit en dipôle passif série/parallèle : le
    chemin VIN→VOUT peut traverser le réseau de contre-réaction, mais l'actif
    casse la mise en série/parallèle (ex. l'AOP met IN- à la masse virtuelle).

    @param refs Refs des composants de l'îlot.
    @param raw_comps Dict {ref → Composant} du graphe original.
    @return bool True si au moins un composant a plus de 2 broches.
    """
    for r in refs:
        comp = raw_comps.get(r)
        if comp and len(getattr(comp, "pins", {}) or {}) > 2:
            return True
    return False


def _circuit_principal_ilot(ilot, graph, results):
    """@brief Match du circuit actif de l'îlot ayant un drawer dédié, ou None.

    Un îlot qui EST un montage actif détecté (AOP, transistor) doit être dessiné
    par son drawer dédié (schéma propre, ex. « AOP + Zin/Zf »), et non par le
    layout générique d'îlot. On ne route ainsi que les îlots à composant actif :
    les îlots passifs gardent la vue « boîte Z » / pont.

    @param ilot Îlot détecté (clé 'composants').
    @param graph Graphe original (porte graph['components']).
    @param results Résultats d'analyse (pour résoudre ilot['circuits']).
    @return dict|None Le match à dessiner, ou None.
    """
    raw = getattr(graph, "graph", {}).get("components", {}) or {}
    refs = [r for r in ilot.get("composants", []) if r in raw]
    actifs = [r for r in refs if len(getattr(raw.get(r), "pins", {}) or {}) > 2]

    # Montages de l'îlot ayant un drawer dédié (hors « Impédance Z »). Un drawer
    # dédié ne représente qu'UN montage : si l'îlot en contient plusieurs (cascade
    # d'AOP, etc.), on laisse le layout générique les dessiner tous.
    drawer_matches = [m for m in _matches_for_island(ilot, results)
                      if m.get("circuit_type") in _DRAWERS
                      and m.get("circuit_type") != "Impédance Z"]
    if len(drawer_matches) != 1:
        return None

    # Le montage peut être multi-actif (push-pull, Darlington, relais = 2 actifs),
    # mais TOUS les composants actifs de l'îlot doivent lui appartenir : sinon il
    # reste un actif hors drawer → layout générique.
    m = drawer_matches[0]
    montage = set(m.get("components", []))
    if any(a not in montage for a in actifs):
        return None
    return m


def _puce_ilot(ilot, graph):
    """@brief Îlot dont l'unique actif est une puce identifiée non-AOP ->
    (ref, entrée catalogue), sinon None. Branché AVANT la grille générique :
    une puce identifiée ne tombe JAMAIS en vue générique.

    Miroir de `detecteur._u_candidat_aop` : seule la catégorie AOP est
    exclue (ses détecteurs dédiés IN+/IN-/OUT la traitent). Un régulateur
    aliasé (7805/LM317…) N'A PAS de détecteur AOP/comparateur qui matche
    IN/GND/OUT -> sans cette boîte puce il retombait en grille générique
    (régle dure violée, cf. revue Task 5)."""
    from circuit_analyzer.catalogue import identifier
    raw = getattr(graph, "graph", {}).get("components", {}) or {}
    refs = [r for r in ilot.get("composants", []) if r in raw]
    actifs = [r for r in refs
              if len(getattr(raw.get(r), "pins", {}) or {}) > 2]
    if len(actifs) != 1:
        return None
    comp = raw[actifs[0]]
    nom = getattr(comp, "value", "") or "?"
    if comp.type == "J":
        # Connecteur multi-broches (dialecte réel) -> boîte étiquetée honnête,
        # jamais une puce/AOP générique.
        return (actifs[0], {"categorie": "Connecteur", "nom": nom, "broches": None})
    if comp.type != "U":
        return None
    entree = identifier("U", getattr(comp, "value", ""))
    if entree is not None and entree.get("categorie") == "AOP":
        return None                     # 741… → détecteurs AOP dédiés
    if entree is None:
        if getattr(comp, "par_forme", False) or getattr(comp, "boite_ic", False):
            # Reconnu par forme (arc + 3 broches = porte logique) OU marqué
            # boîte IC par le dialecte réel (Task 3), hors catalogue : boîte
            # IC NEUTRE honnête (jamais le triangle d'AOP de la vue générique
            # "U"→"opamp"). Le vrai AOP passe par le nom, pas par la forme,
            # donc n'est jamais marqué par_forme → intact.
            return (actifs[0], {"categorie": "CI", "nom": nom, "broches": None})
        return None                     # inconnu ordinaire → comportement actuel
    return (actifs[0], entree)


def _arbre_serie_parallele_ilot(ilot, graph):
    """@brief Arbre série/parallèle d'un îlot réductible entre VIN et VOUT.

    Reconstruit le sous-graphe de l'îlot depuis les composants ORIGINAUX, puis le
    réduit symboliquement entre VIN et VOUT.

    @param ilot Îlot détecté (clé "composants" = refs brutes).
    @param graph Graphe original (porte graph["components"] : {ref → Composant}).
    @return (arbre, comps) | None : arbre série/parallèle (cf. impedance.arbre_expr)
            et dict {ref → Composant} du sous-graphe, ou None si non dessinable
            (pas de composant, VIN/VOUT absents, pont Y-Δ, ou non série/parallèle).
    """
    from circuit_analyzer import impedance
    from circuit_analyzer.composant import construire_graphe

    raw = getattr(graph, "graph", {}).get("components", {}) or {}
    refs = [r for r in ilot.get("composants", []) if r in raw]
    if not refs or _ilot_a_composant_actif(refs, raw):
        return None
    sous = construire_graphe([raw[r] for r in refs])
    bornes = impedance.bornes_possibles(sous)
    if "VIN" not in bornes or "VOUT" not in bornes:
        return None
    expr = impedance.impedance_equivalente(sous, "VIN", "VOUT")
    if expr is None:
        return None
    arbre = impedance.arbre_expr(expr)
    if arbre is None:
        return None
    return arbre, sous.graph["components"]


def _pont_ilot(ilot, graph):
    """@brief Structure pont (Wheatstone) d'un îlot entre VIN et VOUT, ou None.

    @param ilot Îlot détecté (clé "composants" = refs brutes).
    @param graph Graphe original (porte graph["components"]).
    @return (pont, comps) | None : structure de impedance.detecter_pont et dict
            {ref → Composant} du sous-graphe, ou None si ce n'est pas un pont.
    """
    from circuit_analyzer import impedance
    from circuit_analyzer.composant import construire_graphe

    raw = getattr(graph, "graph", {}).get("components", {}) or {}
    refs = [r for r in ilot.get("composants", []) if r in raw]
    if not refs or _ilot_a_composant_actif(refs, raw):
        return None
    sous = construire_graphe([raw[r] for r in refs])
    bornes = impedance.bornes_possibles(sous)
    if "VIN" not in bornes or "VOUT" not in bornes:
        return None
    pont = impedance.detecter_pont(sous, "VIN", "VOUT")
    if pont is None:
        return None
    return pont, sous.graph["components"]


def _compo_2bornes(refs, a, b, raw):
    """@brief Composition symbolique (serie/parallele) des passifs entre a et b.

    @param refs Liste de refs du sous-reseau. @param a/b Nets bornes.
    @param raw Dict {ref -> Composant} original.
    @return str Expression reparsable (ex. 'R7//C7'), ou la ref unique.
    """
    from circuit_analyzer import impedance
    from circuit_analyzer.composant import construire_graphe
    if len(refs) == 1:
        return refs[0]
    sous = construire_graphe([raw[r] for r in refs])
    expr = impedance.impedance_equivalente(sous, a, b)
    return expr if expr else "//".join(refs)


def _reseau_derive_ilot(ilot, graph):
    """@brief Reseau passif derive sur prise (diviseur de reference / filtrage rail).

    Forme : <rail source> -[Z serie]- (prise) -[Z shunt]- GND. Couvre le diviseur
    pur, le diviseur + cap de bypass, et le filtrage de rail.

    @param ilot Ilot detecte (cle 'composants' = refs brutes).
    @param graph Graphe original (porte graph['components']).
    @return dict {top, prise, serie, shunt} ou None si la forme ne s'applique pas.
    """
    from circuit_analyzer.ilots import _nets_derives, _est_gnd, _PASSIFS
    from circuit_analyzer.patterns.base import is_power_net

    raw = getattr(graph, "graph", {}).get("components", {}) or {}
    refs = [r for r in ilot.get("composants", []) if r in raw]
    if not refs or any(raw[r].type not in _PASSIFS for r in refs):
        return None
    island_nets = {n for r in refs for n in raw[r].pins.values() if n}
    # La prise est le net derive qui possede, DANS cet ilot, un passif vers GND.
    # Un rail source decouple ailleurs peut etre globalement « derive » mais n'a
    # pas de shunt-vers-GND ici -> on l'ecarte (evite len(prises)!=1 a tort).
    prises = {n for n in (_nets_derives(graph) & island_nets)
              if any(n in raw[r].pins.values()
                     and any(_est_gnd(m) for m in raw[r].pins.values() if m != n)
                     for r in refs)}
    if len(prises) != 1:
        return None
    prise = next(iter(prises))

    serie_refs, shunt_refs, tops = [], [], set()
    for r in refs:
        nets = {n for n in raw[r].pins.values() if n}
        if prise not in nets:
            return None                       # tout composant doit toucher la prise
        autre = nets - {prise}
        if any(_est_gnd(n) for n in autre):
            shunt_refs.append(r)
        else:
            rails = [n for n in autre if is_power_net(n)]
            if not rails:
                return None
            serie_refs.append(r)
            tops.update(rails)
    if not serie_refs or len(tops) != 1:
        return None
    top = next(iter(tops))
    serie = {"refs": serie_refs,
             "composition": _compo_2bornes(serie_refs, top, prise, raw)}
    gnd_net = next((m for r in shunt_refs for m in raw[r].pins.values()
                    if _est_gnd(m)), "GND")
    shunt = ({"refs": shunt_refs,
              "composition": _compo_2bornes(shunt_refs, prise, gnd_net, raw)}
             if shunt_refs else None)
    return {"top": top, "prise": prise, "serie": serie, "shunt": shunt}


def _reseau_deux_bornes_ilot(ilot, graph):
    """@brief Reseau passif compact entre exactement 2 nets-bornes (rails/ports).

    Repli propre de la grille generique : charges de sortie, decouplages,
    filtres se reduisant a UNE impedance entre deux rails (GND/VOUT, GND/VCC,
    AVCC/GND...). Les nœuds NETxx internes sont tolere (ex. R-NET10-C en serie).

    @param ilot Ilot detecte (cle 'composants' = refs brutes).
    @param graph Graphe original (porte graph['components']).
    @return (arbre, a, b, comps) | None : arbre serie/parallele reductible,
            les deux nets-bornes, et le dict {ref -> Composant} du sous-graphe.
    """
    from circuit_analyzer import impedance
    from circuit_analyzer.composant import construire_graphe
    from circuit_analyzer.satellites import _est_rail

    raw = getattr(graph, "graph", {}).get("components", {}) or {}
    refs = [r for r in ilot.get("composants", []) if r in raw]
    if not refs or _ilot_a_composant_actif(refs, raw):
        return None
    sous = construire_graphe([raw[r] for r in refs])
    bornes = [n for n in impedance.bornes_possibles(sous) if _est_rail(n)]
    if len(bornes) != 2:
        return None
    a, b = bornes
    expr = impedance.impedance_equivalente(sous, a, b)
    if expr is None:
        return None
    arbre = impedance.arbre_expr(expr)
    if arbre is None:
        return None
    return arbre, a, b, sous.graph["components"]


def show_island(ilot: dict, graph, comp_info: dict, parent=None, results=None):
    """Ouvre une fenetre affichant le schema reel d'un ilot."""
    model = _build_island_model(ilot, graph, comp_info)
    name = model["label"]

    popup = ctk.CTkToplevel(parent)
    popup.title(f"Schema ilot - {name}")
    # 1200x720 (audit fenetre F6) borne a l'ecran dispo : un ecran bas (petit
    # portable, VM) laisserait sinon la barre du bas (Exporter/toggle/Fermer)
    # hors-champ derriere la barre des taches.
    largeur = min(1200, popup.winfo_screenwidth() - 40)
    hauteur = min(720, popup.winfo_screenheight() - 200)
    # Position explicite (centree) : le placement en cascade par defaut du
    # gestionnaire de fenetres n'a aucune garantie de tenir a l'ecran une fois
    # la taille appliquee (verifie sur un ecran bas : la barre du bas sortait
    # du cadre malgre une hauteur bornee a l'ecran).
    pos_x = max(0, (popup.winfo_screenwidth() - largeur) // 2)
    pos_y = max(0, (popup.winfo_screenheight() - hauteur) // 2)
    popup.geometry(f"{largeur}x{hauteur}+{pos_x}+{pos_y}")
    popup.configure(fg_color=theme.SURFACE)
    popup.grab_set()

    hdr = ctk.CTkFrame(popup, fg_color=theme.OVERLAY, corner_radius=0, height=54)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    ctk.CTkLabel(hdr, text=f"Schema ilot - {name}",
                 font=ui_kit.font("subtitle", "bold"),
                 text_color=theme.TEXT).pack(side="left", padx=18, pady=14)
    _principal_hdr = _circuit_principal_ilot(ilot, graph, results)
    _gain_txt = _texte_gain(_principal_hdr, graph) if _principal_hdr else None
    if _gain_txt:
        # Consolas conservée volontairement : valeur numérique, chasse fixe mono.
        ctk.CTkLabel(hdr, text=_gain_txt,
                     font=ctk.CTkFont("Consolas", 12, "bold"),
                     text_color=theme.SUCCESS).pack(side="right", padx=18)

    chips = ctk.CTkFrame(popup, fg_color=theme.SURFACE)
    chips.pack(fill="x", padx=14, pady=(8, 2))
    ctk.CTkLabel(chips, text="Composants :",
                 font=ui_kit.font("caption"),
                 text_color=theme.TEXT_DIM).pack(side="left")
    # Les puces sont (re)construites par `_reconstruire_puces` (appelee en
    # fin de `_rendre`) : leur CONTENU depend de la vue courante (refs de
    # modele Z1/Z2... en vue Z, refs REELLES R/L/C en vue detaillee) et leur
    # DISPONIBILITE (grisee si le composant n'est pas dessine) se resout sur
    # la figure courante -- qui n'existe pas encore ici.
    puces_zone = ctk.CTkFrame(chips, fg_color="transparent")
    puces_zone.pack(side="left", fill="x")

    principal = _circuit_principal_ilot(ilot, graph, results)
    _sp = _arbre_serie_parallele_ilot(ilot, graph) if principal is None else None
    _pont = _pont_ilot(ilot, graph) if (principal is None and _sp is None) else None
    _derive = (_reseau_derive_ilot(ilot, graph)
               if (principal is None and _sp is None and _pont is None) else None)
    _deux = (_reseau_deux_bornes_ilot(ilot, graph)
             if (principal is None and _sp is None and _pont is None
                 and _derive is None) else None)
    _chaine = _branches = _paire = _puce = None
    if (principal is None and _sp is None and _pont is None and _derive is None
            and _deux is None):
        # Puce identifiée (NE555, 74HC…, LM393, PC817…) AVANT la paire/chaîne :
        # une puce identifiée ne tombe JAMAIS en vue générique (règle projet).
        _puce = _puce_ilot(ilot, graph)
    if (principal is None and _sp is None and _pont is None and _derive is None
            and _deux is None and _puce is None):
        # Paire croisée (latch SR) AVANT la chaîne : le layout par flux rejette
        # ce motif (2 sources -> profondeur 0) -> échelle générique (audit D1).
        _paire = _paire_croisee(_matches_for_island(ilot, results), comp_info)
        if _paire is None:
            _chaine = _ordonner_montages_flux(_matches_for_island(ilot, results), comp_info)
        if _paire is None and _chaine is None:   # pas linéaire -> essai DAG en couches (PID…)
            _branches = _layers_montages_flux(_matches_for_island(ilot, results), comp_info)
    def construire_fig(detaille):
        """@brief Construit la figure du schéma selon la stratégie de rendu de
        l'îlot (montage actif, arbre série/parallèle, pont, chaîne...).

        @param detaille Vue détaillée R/L/C (True) ou boîtes Z classiques (False).
            Transmis à tous les chemins de rendu (`_make_*fig` et
            `impedance_schematic.dessiner_bloc/dessiner_pont`).
        """
        if principal is not None:
            # Îlot = montage actif détecté : on réutilise son drawer dédié (schéma
            # propre « AOP + Zin/Zf », hitboxes Z cliquables), pas le layout générique.
            # On passe les matches pour que les réseaux Z restants (charges/couplages)
            # soient dessinés cliquables au lieu d'être ignorés.
            return _make_fig(principal, comp_info, _DRAWERS[principal["circuit_type"]],
                             matches=_matches_for_island(ilot, results), detaille=detaille)
        if _sp is not None:
            from gui import impedance_schematic
            _arbre, _comps = _sp
            return impedance_schematic.dessiner_bloc(_arbre, "VIN", "VOUT", _comps,
                                                     detaille=detaille)
        if _pont is not None:
            from gui import impedance_schematic
            _pont_struct, _comps = _pont
            return impedance_schematic.dessiner_pont(_pont_struct, _comps,
                                                      detaille=detaille)
        if _derive is not None:
            return _make_fig(_derive, comp_info, _draw_reseau_derive, detaille=detaille)
        if _deux is not None:
            # Reseau passif compact a 2 bornes : une boite Z entre deux rails
            # etiquetes (cliquable), au lieu de la grille generique encombree.
            from gui import impedance_schematic
            _arbre, _a, _b, _comps = _deux
            return impedance_schematic.dessiner_bloc(_arbre, _a, _b, _comps,
                                                     detaille=detaille)
        if _puce is not None:
            # Puce identifiée non-AOP : boîte puce (elm.Ic) + Z cliquables
            # autour, jamais la grille générique (règle projet).
            _ref_puce, _entree_puce = _puce
            return _make_puce_fig(_ref_puce, _entree_puce, comp_info,
                                  _matches_for_island(ilot, results), detaille=detaille)
        if _paire is not None:
            # Paire croisée (latch SR) : deux portes empilées, retours croisés.
            return _make_latch_fig(_paire, comp_info,
                                   matches=_matches_for_island(ilot, results), detaille=detaille)
        if _chaine is not None:
            # Îlot multi-AOP en chaîne : un seul grand schéma, étages reliés OUT->IN.
            return _make_chain_fig(_chaine, comp_info,
                                   matches=_matches_for_island(ilot, results), detaille=detaille)
        if _branches is not None:
            # Îlot multi-AOP branché (P/I/D parallèles -> sommateur…) : schéma en couches.
            return _make_branched_fig(_branches, comp_info,
                                      matches=_matches_for_island(ilot, results), detaille=detaille)
        matches = _matches_for_island(ilot, results)
        return _make_island_fig(model, matches=matches, detaille=detaille)

    # `etat["fig"]` = figure actuellement montee ; `etat["canvas"]` = son
    # FigureCanvasTkAgg ; `etat["cids"]` = les cid `mpl_connect` a deconnecter
    # avant tout remontage (cf. `_demonter_contexte`, demontage deterministe
    # section 3 du design). Les trois sont reecrits ENSEMBLE a chaque
    # (re)montage, jamais partiellement.
    etat = {"fig": None, "canvas": None, "cids": []}
    mode = {"detaille": True}
    zoom = {"facteur": 1.0}

    canvas_frame = ctk.CTkFrame(popup, fg_color=SCH_BG, corner_radius=10)
    canvas_frame.pack(fill="both", expand=True, padx=14, pady=(4, 0))

    def _demonter_contexte():
        """@brief Demonte totalement le contexte de rendu courant : deconnecte
        les cid matplotlib, detruit le widget Tk du canvas puis vide la
        figure remplacee. Partage par toute reconstruction (`monter_canvas`,
        appele par le toggle et le zoom) ET par la fermeture du popup
        (bouton Fermer / WM_DELETE_WINDOW) — un seul chemin de teardown.

        Pourquoi pas `plt.close()` : nos figures sont creees via
        `matplotlib.figure.Figure()` DIRECTEMENT (jamais via `plt.figure()`),
        donc jamais enregistrees dans le registre pyplot (`Gcf`) — `plt.close()`
        n'aurait rien a fermer. L'equivalent deterministe est : `mpl_disconnect`
        (retire les callbacks de la CallbackRegistry du canvas, qui referencent
        la figure via leurs closures `_on_click`/`_on_motion`) puis destruction
        du widget Tk (rompt le dernier lien canvas Tk <-> figure) puis `clf()`
        (vide les axes/artistes, rompt les cycles Artist<->Figure internes) —
        apres quoi plus aucune reference forte ne subsiste et `gc.collect()`
        recupere la figure IMMEDIATEMENT (au lieu d'attendre un futur passage
        du GC cyclique).
        """
        ancien_canvas = etat.get("canvas")
        if ancien_canvas is not None:
            for cid in etat.get("cids") or ():
                try:
                    ancien_canvas.mpl_disconnect(cid)
                except Exception:
                    _log.debug("mpl_disconnect ignore au demontage", exc_info=True)
            try:
                ancien_canvas.get_tk_widget().destroy()
            except tk.TclError:
                pass
        # Filet de securite : detruit tout residu (ex. le cadre `viewport` +
        # scrollbars de `_pack_scrollable_figure`, dont seul le widget mpl
        # interne vient d'etre detruit ci-dessus explicitement).
        for enfant in canvas_frame.winfo_children():
            enfant.destroy()
        # Les figures du cache bimode (`etat["figs"]`) survivent au demontage
        # d'un remontage (toggle/zoom) : seule la fermeture du popup (`_fermer`)
        # les clf() -- sinon un toggle vers l'autre mode viderait la figure
        # qu'on s'apprete a reafficher au prochain retour (cf. cache bimode).
        ancienne_fig = etat.get("fig")
        if ancienne_fig is not None and ancienne_fig not in (
                etat.get("figs") or {}).values():
            ancienne_fig.clf()
        etat["canvas"] = None
        etat["cids"] = []
        etat["fig"] = None

    def monter_canvas(fig, facteur=1.0):
        """@brief Demonte l'ancien contexte puis empaquette `fig` dans
        `canvas_frame`, reconnecte le clic drill-down et le curseur « main »
        sur les Z.

        Vues larges (chaîne OU gros îlot-grille) : défilement horizontal à taille
        native pour ne pas écraser le schéma dans le popup. Les petites vues
        remplissent simplement le cadre. Un zoom (`facteur` > 1.0, boutons
        -/100%/+) force aussi le chemin défilant : la figure agrandie ne doit
        pas être écrasée dans le cadre.

        DPI : la figure garde un DPI CONSTANT (`fig.dpi` inchangé) ; c'est
        `set_size_inches` (appelé par `_rendre` avant ce montage) qui fait
        varier la taille pixel native — un re-rendu vectoriel natif a chaque
        facteur, equivalent a un reglage de DPI mais sans jamais invalider
        `_figure_pixel_size` (qui lit `fig.dpi` en le supposant stable).
        """
        _demonter_contexte()

        _defile = (_chaine is not None or _branches is not None
                   or fig.get_size_inches()[0] > _ISLAND_DEFILE_WIDTH_IN
                   or facteur > 1.0)
        if _defile:
            canvas = _pack_scrollable_figure(canvas_frame, fig)
        else:
            canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
            canvas.draw()
            widget = canvas.get_tk_widget()
            widget.configure(bg=SCH_BG, highlightthickness=0)
            # Centrage EXPLICITE (design section 2) : ax.set_anchor("C") fixe
            # le point d'ancrage de la boite equal-aspect au centre (deja la
            # valeur par defaut de Matplotlib pour adjustable="box", mais
            # rendue explicite ici pour ne plus dependre d'un defaut
            # implicite qui pourrait changer sous nos pieds).
            for ax in fig.axes:
                ax.set_anchor("C")
            if facteur < 1.0:
                # Zoom REDUIT (bouton -) : surtout PAS fill="both". Un fill
                # forcerait le widget Tk a grandir jusqu'au cadre disponible,
                # ce qui declenche le handler `resize()` de FigureCanvasTkAgg
                # (lie a <Configure>) — celui-ci recalcule bêtement
                # `figure.set_size_inches(largeur_cadre/dpi, ...)` et annule
                # purement et simplement le facteur de reduction qu'on vient
                # d'appliquer (bug verifie : le schema « zoome out » revenait
                # visuellement a 100 %). `expand=True` SANS `fill` garde la
                # taille native (deja reduite) du widget et le centre dans
                # l'espace disponible — jamais clippe, jamais reetire.
                widget.pack(expand=True, padx=4, pady=4)
            else:
                widget.pack(fill="both", expand=True, padx=4, pady=4)

        def _on_click(event):
            # Clic dans une zone de Z -> ouvre le sous-schema des R/L/C qui le composent.
            if event.xdata is None or event.ydata is None:
                return
            for x0, x1, y0, y1, refs, composition in getattr(fig, "_z_hitboxes", []):
                if x0 <= event.xdata <= x1 and y0 <= event.ydata <= y1:
                    show_dipole_detail(refs, composition, graph, comp_info, popup)
                    return

        cid_click = canvas.mpl_connect("button_press_event", _on_click)
        cid_motion = _suivre_curseur_z(canvas, fig)
        etat["canvas"] = canvas
        etat["cids"] = [cid_click, cid_motion]
        return canvas

    def _on_chip_click(refs):
        """@brief Callback de clic sur une puce « Composants : ... » : FOCUS
        sur le composant vise -- zoome a `_CHIP_FOCUS_FACTEUR` si le zoom
        courant est inferieur (la vue devient defilante), centre la vue sur
        le composant et pose un anneau de surbrillance temporaire.

        @param refs Un ref (str) ou une liste de refs CANDIDATS (str),
            essayes dans l'ordre via `_position_composant` jusqu'au premier
            qui resout (cf. commentaire de construction des puces ci-dessus :
            necessaire pour les puces Z composites, dont le ref de modele ne
            correspond pas toujours au libelle local affiche sur le schema).

        Liaison TARDIVE a `etat["fig"]`/`etat["canvas"]` : les puces sont
        creees UNE SEULE FOIS, avant le premier `monter_canvas`, mais la
        figure/le canvas sont remplaces a chaque (re)montage (toggle vue
        detaillee, zoom, Ajuster) -- on doit donc toujours lire l'etat
        COURANT au moment du clic, jamais capturer `fig`/`canvas` par
        fermeture au moment de la creation des puces.

        No-op silencieux si AUCUN candidat n'est trouvable dans la figure
        courante (cf. `_position_composant`).
        """
        candidats = [refs] if isinstance(refs, str) else list(refs)
        fig = etat.get("fig")
        canvas = etat.get("canvas")
        if fig is None or canvas is None or not fig.axes:
            return
        pos = None
        for r in candidats:
            pos = _position_composant(fig, r)
            if pos is not None:
                break
        if pos is None:
            # Defensif : les puces indisponibles sont grisees et ne passent
            # pas par ici (cf. _reconstruire_puces) -- mais jamais muet.
            _puce_indisponible_cliquee(candidats[0] if candidats else "?")
            return

        # Clic = FOCUS : sous _CHIP_FOCUS_FACTEUR on zoome d'abord sur le
        # schema (le composant seulement entoure d'un anneau a 100 % ne
        # suffisait pas -- retour utilisateur). Le re-rendu remplace figure
        # et canvas : on re-resout la position sur la figure COURANTE.
        if zoom["facteur"] < _CHIP_FOCUS_FACTEUR:
            zoom["facteur"] = _CHIP_FOCUS_FACTEUR
            _rendre()
            fig = etat.get("fig")
            canvas = etat.get("canvas")
            if fig is None or canvas is None or not fig.axes:
                return
            pos = None
            for r in candidats:
                pos = _position_composant(fig, r)
                if pos is not None:
                    break
            if pos is None:
                _puce_indisponible_cliquee(candidats[0] if candidats else "?")
                return

        view = getattr(canvas, "_scroll_view", None)
        if view is not None:
            # Le viewport peut sortir d'un re-rendu immediat : forcer la mise
            # en page Tk avant de mesurer, sinon winfo_width() vaut 1 et la
            # fraction de centrage est fausse.
            popup.update_idletasks()
            ax0 = fig.axes[0]
            dispx, dispy = ax0.transData.transform(pos)
            fig_w_px, fig_h_px = _figure_pixel_size(fig)
            # Conversion display matplotlib (origine bas-gauche, y vers le
            # haut) -> pixel canvas Tk (origine haut-gauche, y vers le bas),
            # meme convention que le rendu Agg sous-jacent du widget.
            vw = max(1, view.winfo_width())
            vh = max(1, view.winfo_height())
            view.xview_moveto(_fraction_centree(dispx, fig_w_px, vw))
            view.yview_moveto(_fraction_centree(fig_h_px - dispy, fig_h_px, vh))

        anneau = mpatches.Circle(pos, radius=_CHIP_HIGHLIGHT_RADIUS, fill=False,
                                  lw=2.5, edgecolor=BLUE_HOVER, zorder=50)
        # Marqueur ad hoc (meme idiome que `fig._z_hitboxes`) : distingue cet
        # anneau des Circle deja dessines par schemdraw sur le meme axe (ex.
        # points de jonction, rayon ~0.075) -- utilise par les tests pour
        # cibler precisement l'anneau de surbrillance sans dependre du rayon.
        anneau._surbrillance_puce = True
        fig.axes[0].add_patch(anneau)
        try:
            canvas.draw_idle()
        except tk.TclError:
            _log.debug("draw_idle ignore (canvas deja detruit ?)", exc_info=True)

        def _retirer_anneau(fig_cible=fig, anneau_cible=anneau):
            # `fig_cible`/`anneau_cible` figent la figure/l'anneau VISES au
            # moment du clic (arguments par defaut, pas une fermeture sur les
            # variables mutables `etat`) : si un toggle/zoom a depuis remonte
            # une AUTRE figure, `etat["fig"]` a change -- on retire quand meme
            # l'anneau de la figure d'origine (propre, meme demontee) mais on
            # ne redessine QUE si cette figure est encore celle affichee.
            try:
                if anneau_cible.axes is not None:
                    anneau_cible.remove()
                if etat.get("fig") is fig_cible:
                    canvas_courant = etat.get("canvas")
                    if canvas_courant is not None:
                        canvas_courant.draw_idle()
            except Exception:
                _log.debug("retrait anneau surbrillance ignore", exc_info=True)

        try:
            popup.after(_CHIP_HIGHLIGHT_DELAY_MS, _retirer_anneau)
        except Exception:
            _log.debug("popup.after ignore (popup deja ferme ?)", exc_info=True)

    def _maj_bouton_pct():
        """@brief Reflète le facteur de zoom courant sur le bouton « % » de la
        barre basse (créé APRÈS le premier rendu : d'où le get tolérant)."""
        b = etat.get("bouton_pct")
        if b is not None:
            try:
                b.configure(text=f"{round(zoom['facteur'] * 100)} %")
            except tk.TclError:
                _log.debug("maj bouton pct ignoree (widget detruit ?)", exc_info=True)

    def _liste_puces():
        """@brief (libelle, type, candidats) des puces selon la vue courante.

        Vue Z : une puce par composant de MODELE (Z1, Z2, D1, Q1...) ;
        candidats = refs RAW sous-jacents d'abord (ceux effectivement portes
        par les hitboxes/labels du schema -- chaque etage d'une chaine
        multi-AOP renumerote ses Zin/Zf/Z1... a partir de 1), le ref de
        modele en repli.
        Vue detaillee : chaque Z composite est remplace par UNE PUCE PAR
        COMPOSANT REEL (R/L/C), coherent avec le schema affiche qui ne
        montre plus de boites Z ; les actifs (Q/U/D...) restent tels quels.
        """
        items = {}
        for comp in model["components"]:
            ref = comp["ref"]
            refs = [r for r in (comp.get("refs") or ()) if r]
            if mode["detaille"] and refs:
                for r in refs:
                    typ = (comp_info.get(r, {}) or {}).get("type")
                    items.setdefault(r, (typ, [r]))
            else:
                txt = f"{ref} {comp.get('value', '')}".strip()
                candidats = list(dict.fromkeys([*refs, ref]))
                items.setdefault(txt, (comp.get("type"), candidats))
        return [(txt, typ, cands) for txt, (typ, cands) in items.items()]

    def _message_puce(texte):
        """@brief Message transitoire de la barre basse (clic sur une puce
        indisponible) ; s'efface seul, sauf si un message plus recent l'a
        deja remplace."""
        lbl = etat.get("msg_puce")
        if lbl is None:
            return
        def _effacer(t=texte):
            try:
                if lbl.cget("text") == t:
                    lbl.configure(text="")
            except tk.TclError:
                _log.debug("effacement message puce ignore", exc_info=True)
        try:
            lbl.configure(text=texte)
            lbl.after(_CHIP_MSG_DELAY_MS, _effacer)
        except tk.TclError:
            _log.debug("message puce ignore (widget detruit ?)", exc_info=True)

    def _puce_indisponible_cliquee(txt):
        _message_puce(f"{txt} n'est pas dessiné dans cette vue")

    def _reconstruire_puces():
        """@brief (Re)construit le bandeau « Composants » : contenu selon la
        vue courante (cf. `_liste_puces`), puce GRISEE si aucun candidat ne
        resout de position sur la figure courante -- son clic affiche alors
        un message au lieu d'etre muet (retour utilisateur 2026-07-08 :
        « des fois quand je clique il ne se passe rien »)."""
        fig = etat.get("fig")
        for w in puces_zone.winfo_children():
            w.destroy()
        etat["puces"] = []
        for txt, typ, candidats in _liste_puces():
            dispo = fig is not None and any(
                _position_composant(fig, r) is not None for r in candidats)
            puce = ctk.CTkLabel(
                puces_zone, text=f" {txt} ",
                font=ui_kit.font("caption", "bold"),
                fg_color=_COMP_COLORS.get(typ, theme.OVERLAY) if dispo
                         else theme.SURFACE,
                text_color=theme.TEXT if dispo else theme.TEXT_DIM,
                corner_radius=4,
                cursor="hand2" if dispo else "arrow")
            puce.pack(side="left", padx=3)
            if dispo:
                puce.bind("<Button-1>", lambda _e, c=candidats: _on_chip_click(c))
            else:
                puce.bind("<Button-1>",
                          lambda _e, t=txt: _puce_indisponible_cliquee(t))
            etat["puces"].append(
                {"texte": txt, "dispo": dispo, "candidats": candidats})

    # Cache bimode : une figure par valeur de `mode["detaille"]`, construite
    # au plus une fois chacune (construction paresseuse -- le toggle ne
    # reconstruit jamais une figure deja vue, il la reaffiche). `base` memorise
    # la taille NATIVE (facteur 1.0) de chaque figure au moment de sa
    # construction : indispensable pour le zoom (cf. piege ci-dessous),
    # `nb_constructions` sert de sonde de test (une construction reelle par
    # mode, jamais plus).
    etat.setdefault("figs", {False: None, True: None})
    etat.setdefault("base", {False: None, True: None})
    etat.setdefault("nb_constructions", 0)

    def _rendre():
        """@brief Chemin de reconstruction partagé par le toggle vue détaillée
        et les boutons de zoom : chacun conserve l'état de l'autre (le toggle
        redessine au zoom courant, le zoom conserve le mode courant).

        Reutilise la figure du cache bimode `etat["figs"][det]` si elle existe
        deja (toggle aller-retour = pas de reconstruction), sinon la construit
        via `construire_fig` et la memorise.

        PIEGE zoom : `set_size_inches` MUTE la figure -- si on relit sa taille
        courante via `get_size_inches()` pour en deriver le prochain facteur,
        deux zooms successifs sur une figure REUTILISEE du cache se
        composeraient (base deja x1.25 -> x1.25 a nouveau -> x1.5625 au lieu
        de x1.25). La taille NATIVE de chaque mode est donc figee UNE FOIS
        (`etat["base"][det]`, a la premiere construction de ce mode) et
        relue -- jamais recalculee depuis la figure courante, qui peut porter
        un zoom/tassage d'un rendu precedent.
        """
        det = mode["detaille"]
        nouvelle_fig = etat["figs"][det]
        if nouvelle_fig is None:
            nouvelle_fig = construire_fig(det)
            etat["figs"][det] = nouvelle_fig
            etat["nb_constructions"] += 1
            etat["base"][det] = nouvelle_fig.get_size_inches()
        base_w, base_h = etat["base"][det]
        # Mémorisés AVANT tassage/zoom (taille native au facteur 1.0) — sert
        # au bouton « Ajuster à la fenêtre » (`_ajuster`) sans reconstruire de
        # figure juste pour mesurer.
        etat["base_w"], etat["base_h"], etat["dpi"] = base_w, base_h, nouvelle_fig.dpi
        facteur = zoom["facteur"]
        if facteur != 1.0:
            nouvelle_fig.set_size_inches(base_w * facteur, base_h * facteur)
        elif (_chaine is None and _branches is None
                and base_w > _ISLAND_DEFILE_WIDTH_IN):
            # Depassement MARGINAL (<= 15 %) du viewport : on tasse la figure
            # pour tenir sans barre de defilement au facteur 100 % plutot que
            # de faire apparaitre un scroll pour quelques pixels (audit
            # fenetre F6). Un depassement plus large (chaine large...) garde
            # le defilement natif (cf. `_defile` dans monter_canvas).
            ratio = base_w / _ISLAND_DEFILE_WIDTH_IN
            if ratio <= 1.15:
                nouvelle_fig.set_size_inches(base_w / ratio, base_h / ratio)
            else:
                nouvelle_fig.set_size_inches(base_w, base_h)
        else:
            # Facteur 100 % sans tassage : reset explicite a la taille native
            # -- `nouvelle_fig` peut etre une figure REUTILISEE du cache qui
            # porte encore un zoom/tassage d'un rendu precedent sur ce mode.
            nouvelle_fig.set_size_inches(base_w, base_h)
        monter_canvas(nouvelle_fig, facteur)
        etat["fig"] = nouvelle_fig
        _maj_bouton_pct()
        # Bandeau reconstruit a CHAQUE rendu (un seul point de verite :
        # premier affichage, toggle, zoom, Ajuster) : contenu et
        # disponibilite dependent de la vue et de la figure courantes.
        _reconstruire_puces()

    _rendre()

    bar = ctk.CTkFrame(popup, fg_color=theme.OVERLAY, corner_radius=0, height=44)
    bar.pack(fill="x", side="bottom")
    bar.pack_propagate(False)
    ui_kit.SecondaryButton(bar, text="Exporter PNG", icon_name="download",
                  width=140, height=30,
                  command=lambda: _export(etat["fig"], name, popup)).pack(
                      side="left", padx=12, pady=7)

    def _toggle_detaille():
        mode["detaille"] = not mode["detaille"]
        _rendre()
        toggle_btn.configure(
            text="Vue simplifiée Z" if mode["detaille"] else "Vue détaillée R/L/C")

    toggle_btn = ui_kit.SecondaryButton(bar, text="Vue simplifiée Z", icon_name="layers",
                  width=170, height=30,
                  command=_toggle_detaille)
    toggle_btn.pack(side="left", padx=(0, 12), pady=7)

    # Message transitoire des puces indisponibles (cf. `_message_puce`).
    etat["msg_puce"] = ctk.CTkLabel(bar, text="", font=ui_kit.font("caption"),
                                    text_color=theme.TEXT_DIM)
    etat["msg_puce"].pack(side="left", padx=(0, 12))

    def _zoom(direction):
        zoom["facteur"] = _island_zoom_next(zoom["facteur"], direction)
        _rendre()

    def _ajuster():
        """@brief Pose le facteur de zoom qui fait tenir la figure ENTIÈRE
        dans le viewport courant : `f = min(vw/wpx, vh/hpx)` où (vw, vh) est
        la taille utile de `canvas_frame` (paddings/scrollbars déduits, cf.
        `_ISLAND_VIEWPORT_PAD`) et (wpx, hpx) la taille native de la figure au
        facteur 1.0 (mémorisée dans `etat` par `_rendre`). Mode détaillé/Z
        conservé — seul `zoom["facteur"]` change, `_rendre()` réutilise le
        chemin partagé (centrage < 1x déjà géré).
        """
        popup.update_idletasks()
        vw = canvas_frame.winfo_width() - _ISLAND_VIEWPORT_PAD
        vh = canvas_frame.winfo_height() - _ISLAND_VIEWPORT_PAD
        wpx = etat["base_w"] * etat["dpi"]
        hpx = etat["base_h"] * etat["dpi"]
        if vw <= 0 or vh <= 0 or wpx <= 0 or hpx <= 0:
            return
        f = min(vw / wpx, vh / hpx)
        zoom["facteur"] = max(_ISLAND_AJUSTER_MIN, min(_ISLAND_AJUSTER_MAX, f))
        _rendre()

    def _fermer():
        """@brief Fermeture du popup (bouton Fermer ET WM_DELETE_WINDOW) : meme
        teardown déterministe qu'un remontage (cf. `_demonter_contexte`) AVANT
        `popup.destroy()` — sinon le dernier contexte affiché ne serait jamais
        démonté explicitement (seul le GC cyclique l'aurait récupéré, un jour).

        Vide aussi le cache bimode (`etat["figs"]`) : celui-ci protège les DEUX
        figures d'un `clf()` prématuré pendant la vie du popup (cf.
        `_demonter_contexte`), mais a la fermeture il n'y a plus de retour
        possible vers l'autre mode -- les DEUX doivent etre liberees ici."""
        for f in (etat.get("figs") or {}).values():
            if f is not None:
                f.clf()
        etat["figs"] = {False: None, True: None}
        _demonter_contexte()
        popup.destroy()

    popup.protocol("WM_DELETE_WINDOW", _fermer)

    # Fermer est packé side="right" en premier pour rester à l'extrémité
    # droite ; les boutons de zoom, packés ensuite, s'empilent à sa gauche
    # dans l'ordre de lecture −, 100 %, +.
    ui_kit.GhostButton(bar, text="Fermer", icon_name="x",
                  width=90, height=30,
                  command=_fermer).pack(side="right", padx=12, pady=7)
    ui_kit.GhostButton(bar, text="+", width=40, height=30,
                  command=lambda: _zoom("in")).pack(side="right", padx=(0, 12), pady=7)
    # Affiche le POURCENTAGE COURANT (mis a jour par _rendre) tout en gardant
    # son role de remise a 100 % au clic : depuis le clic-focus des puces, le
    # facteur peut changer sans passer par les boutons -/+, un « 100 % » fige
    # mentirait sur l'etat reel de la vue.
    bouton_pct = ui_kit.GhostButton(bar, text="100 %", width=56, height=30,
                  command=lambda: _zoom("reset"))
    bouton_pct.pack(side="right", padx=0, pady=7)
    etat["bouton_pct"] = bouton_pct
    _maj_bouton_pct()
    ui_kit.GhostButton(bar, text="−", width=40, height=30,
                  command=lambda: _zoom("out")).pack(side="right", padx=(12, 0), pady=7)
    ui_kit.GhostButton(bar, text="Ajuster", icon_name="maximize",
                  width=100, height=30,
                  command=_ajuster).pack(side="right", padx=(12, 0), pady=7)

    # Hook de test minimal (jamais utilise par l'UI, prefixe _test) : expose
    # l'etat interne (mode/zoom/etat de montage) et les actions declenchantes
    # pour verrouiller par test la persistance croisee mode<->zoom (section 2)
    # et l'absence de fuite au demontage (section 3), sans dependre des
    # libelles de bouton (fragiles a une traduction/un refactor visuel) ni
    # exposer les widgets Tk eux-memes. Meme idiome que `fig._z_hitboxes`
    # (attribut ad hoc attache a un objet existant plutot qu'une API dediee).
    popup._etat_test = {
        "etat": etat,
        "mode": mode,
        "zoom": zoom,
        "canvas_frame": canvas_frame,
        "toggle_btn": toggle_btn,
        "toggle": _toggle_detaille,
        "zoom_in": lambda: _zoom("in"),
        "zoom_out": lambda: _zoom("out"),
        "zoom_reset": lambda: _zoom("reset"),
        "ajuster": _ajuster,
        "fermer": _fermer,
        "cliquer_composant": _on_chip_click,
        "cliquer_puce_indisponible": _puce_indisponible_cliquee,
    }
    return popup


def _pack_scrollable_figure(parent, fig):
    """@brief Affiche une figure a sa taille native dans un viewport scrollable.

    `base_w`/`base_h` (donc la scrollregion initiale) sont derives de
    `_figure_pixel_size(fig)`, qui lit `fig.get_size_inches() * fig.dpi` — a
    l'appel, `fig` a DEJA recu son `set_size_inches` post-facteur de zoom
    (cf. `_rendre` dans `show_island`) : le DPI reste constant, seule la
    taille pouce varie, donc `_figure_pixel_size` reste toujours juste sans
    avoir a suivre un DPI mouvant.
    """
    base_w, base_h = _figure_pixel_size(fig)
    state = {"scale": 1.0}

    viewport = tk.Frame(parent, bg=SCH_BG)
    viewport.pack(fill="both", expand=True, padx=4, pady=4)
    viewport.grid_rowconfigure(0, weight=1)
    viewport.grid_columnconfigure(0, weight=1)

    xbar = tk.Scrollbar(viewport, orient="horizontal")
    ybar = tk.Scrollbar(viewport, orient="vertical")
    view = tk.Canvas(
        viewport,
        bg=SCH_BG,
        highlightthickness=0,
        cursor="fleur",
        xscrollcommand=xbar.set,
        yscrollcommand=ybar.set,
    )
    xbar.configure(command=view.xview)
    ybar.configure(command=view.yview)

    view.grid(row=0, column=0, sticky="nsew")
    ybar.grid(row=0, column=1, sticky="ns")
    xbar.grid(row=1, column=0, sticky="ew")

    inner = tk.Frame(view, bg=SCH_BG)
    view.create_window((0, 0), window=inner, anchor="nw")

    canvas = FigureCanvasTkAgg(fig, master=inner)
    canvas.draw()
    canvas.get_tk_widget().configure(
        width=base_w,
        height=base_h,
        bg=SCH_BG,
        highlightthickness=0,
    )
    canvas.get_tk_widget().pack()

    inner.bind("<Configure>", lambda _e: view.configure(scrollregion=view.bbox("all")))

    def _resize_matplotlib_widget(scale):
        w = max(1, int(round(base_w * scale)))
        h = max(1, int(round(base_h * scale)))
        canvas.get_tk_widget().configure(width=w, height=h)
        inner.configure(width=w, height=h)
        view.configure(scrollregion=(0, 0, w, h))
        return w, h

    def _on_mousewheel(event):
        old_scale = state["scale"]
        new_scale = _zoom_next_scale(old_scale, getattr(event, "delta", 0))
        if abs(new_scale - old_scale) < 1e-9:
            return "break"

        old_size = (max(1, int(round(base_w * old_scale))),
                    max(1, int(round(base_h * old_scale))))
        origin = (view.canvasx(0), view.canvasy(0))
        new_size = _resize_matplotlib_widget(new_scale)
        state["scale"] = new_scale
        fx, fy = _zoom_scroll_fractions(
            old_size=old_size,
            new_size=new_size,
            viewport=(max(1, view.winfo_width()), max(1, view.winfo_height())),
            pointer=(event.x, event.y),
            canvas_origin=origin,
        )
        view.xview_moveto(fx)
        view.yview_moveto(fy)
        return "break"

    def _on_pan_start(event):
        view.scan_mark(event.x, event.y)
        view.configure(cursor="fleur")
        return "break"

    def _on_pan_drag(event):
        view.scan_dragto(event.x, event.y, gain=1)
        return "break"

    view.bind("<MouseWheel>", _on_mousewheel)
    view.bind("<ButtonPress-1>", _on_pan_start)
    view.bind("<B1-Motion>", _on_pan_drag)
    for widget in (inner,):
        widget.bind("<MouseWheel>", _on_mousewheel)
        widget.bind("<ButtonPress-1>", _on_pan_start)
        widget.bind("<B1-Motion>", _on_pan_drag)
    _bind_scrollable_mpl_events(
        canvas.get_tk_widget(), _on_mousewheel, _on_pan_start, _on_pan_drag)
    # Hook de test minimal (meme idiome que `fig._z_hitboxes`) : expose le
    # canvas Tk scrollable pour verrouiller par test que la scrollregion
    # colle exactement aux bornes du schema (xview_moveto(1)/yview_moveto(1)
    # atteignent le bord sans rien couper ni deborder, cf. design section 2).
    canvas._scroll_view = view
    return canvas


def show_dipole_detail(refs, composition, graph, comp_info, parent=None):
    """@brief Affiche le sous-schema reel (R/L/C) composant une Impedance Z.

    @param refs Refs bruts du dipole (ex. ['C3', 'R8']).
    @param composition Formule lisible (ex. '(C6 // C7)').
    @param graph Graphe brut.
    @param comp_info Dict {ref -> {...}}.
    @param parent Fenetre parente.
    @return None
    """
    titre = f"Z = {composition}" if composition else "Detail Z"
    # Detail en forme serie/parallele si la composition est reductible (coherent
    # avec la vue principale) ; sinon (ex. « pont{...} ») on garde l'ancien dessin.
    from circuit_analyzer import impedance
    from gui import impedance_schematic
    arbre = impedance.arbre_expr(composition) if composition else None
    if arbre is not None:
        comps = getattr(graph, "graph", {}).get("components", {}) or {}
        fig = impedance_schematic.dessiner(arbre, "A", "B", comps, titre=titre)
    else:
        model = _build_dipole_model(refs, graph, comp_info, label=titre)
        fig = _make_island_fig(model)

    popup = ctk.CTkToplevel(parent)
    popup.title(titre)
    popup.geometry("760x560")
    popup.configure(fg_color=theme.SURFACE)
    popup.grab_set()

    hdr = ctk.CTkFrame(popup, fg_color=theme.OVERLAY, corner_radius=0, height=48)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    ctk.CTkLabel(hdr, text=f"Composition de l'impedance : {composition}",
                 font=ui_kit.font("subtitle", "bold"),
                 text_color=theme.TEXT).pack(side="left", padx=18, pady=12)

    canvas_frame = ctk.CTkFrame(popup, fg_color=SCH_BG, corner_radius=10)
    canvas_frame.pack(fill="both", expand=True, padx=14, pady=10)
    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().configure(bg=SCH_BG, highlightthickness=0)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

    bar = ctk.CTkFrame(popup, fg_color=theme.OVERLAY, corner_radius=0, height=44)
    bar.pack(fill="x", side="bottom")
    bar.pack_propagate(False)
    ui_kit.SecondaryButton(bar, text="Exporter PNG", icon_name="download",
                  width=140, height=30,
                  command=lambda: _export(fig, titre, popup)).pack(
                      side="left", padx=12, pady=7)
    ui_kit.GhostButton(bar, text="Fermer", icon_name="x",
                  width=90, height=30,
                  command=popup.destroy).pack(side="right", padx=12, pady=7)


def _make_fig(result, comp_info, drawer_fn, matches=None, detaille: bool = False):
    """@brief Construit la figure matplotlib du schéma (ou un texte de repli).

    @param result Match du circuit détecté.
    @param comp_info Dict des infos composants.
    @param drawer_fn Fonction de dessin dédiée, ou None.
    @param matches Matches de l'îlot : si fournis, les réseaux d'impédance Z
        restants (couplages/charges non dessinés par le montage) sont ajoutés en
        boîtes Z cliquables autour du montage, au lieu d'être ignorés.
    @param detaille Si True, les boîtes Z sont remplacées par le réseau R/L/C
        réel (cf. `_z_box`) et n'ont plus de zone cliquable.
    @return matplotlib.figure.Figure La figure prête à afficher.
    """
    fig = Figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    # aspect egal : sinon l'etirement vertical de la figure deforme les symboles
    # (la boite d'impedance, horizontale, paraissait verticale).
    ax.set_aspect("equal")

    fig._z_hitboxes = []   # zones cliquables des Z (renseignées par le drawer)
    fig._comp_positions = {}   # registre ref -> position (renseigné par le drawer)
    if drawer_fn:
        try:
            with schemdraw.Drawing(canvas=ax, show=False) as d:
                d.config(fontsize=14, inches_per_unit=0.62)
                d._z_hitboxes = []
                d._comp_positions = {}
                d._mode_detaille = detaille
                ancres = drawer_fn(d, result, comp_info)
                # Réseaux d'impédance Z restants de l'îlot (charges/couplages que le
                # montage seul ne dessine pas) -> boîtes Z cliquables, pas ignorés.
                coupl = [m for m in (matches or []) if _est_couplage(m)]
                if coupl and isinstance(ancres, dict) and ancres.get("nets"):
                    _dessiner_impedances_locales(d, [result], [ancres], coupl, set(), comp_info)
                fig._z_hitboxes = list(d._z_hitboxes)
                fig._comp_positions = dict(d._comp_positions)
                # Ajuster la figure au format réel du dessin : sinon le schéma
                # (large) est « letterboxé » dans une figure carrée -> petit, avec
                # de grandes bandes vides. On colle le format de la figure à celui
                # du tracé pour qu'il remplisse la fenêtre.
                try:
                    bb = d.get_bbox()
                    # Cadrage explicite des axes sur le bbox schemdraw (qui, lui,
                    # compte le texte des étiquettes via SegmentText.get_bbox) : sur
                    # un ax existant (canvas=ax), schemdraw NE fixe PAS xlim/ylim
                    # lui-même (cf. mpl.py getfig(): "if not self.userfig") et
                    # laisse l'autoscale par défaut de Matplotlib faire le travail —
                    # or cet autoscale ne considère QUE les Line2D/Patch (dataLim),
                    # jamais les Text (ax.text, utilisé par elm.Label). Une boîte Z
                    # isolée (rien d'autre pour étendre la vue) voit alors son
                    # étiquette hors cadre. On fixe donc xlim/ylim nous-mêmes depuis
                    # le bbox complet (texte inclus), avec une petite marge.
                    marge = 0.3
                    ax.set_xlim(bb.xmin - marge, bb.xmax + marge)
                    ax.set_ylim(bb.ymin - marge, bb.ymax + marge)
                    w, h = (bb.xmax - bb.xmin), (bb.ymax - bb.ymin)
                    if w > 0 and h > 0:
                        asp = max(0.4, min(3.2, w / h))
                        # La fenêtre fait 560 px de haut ; après en-tête + puces +
                        # barre du bas il reste ~420 px (~4.2") pour le tracé. Le
                        # canvas Tk ne redimensionne pas la figure : si elle dépasse,
                        # le haut (où se trouve Zf) est rogné. On la borne donc à 4.2".
                        haut = 4.2
                        fig.set_size_inches(haut * asp, haut)
                except Exception:
                    _log.debug("ajustement de taille de figure ignoré", exc_info=True)
        except Exception as e:
            _log.warning("rendu du schéma échoué", exc_info=True)
            ax.text(0.5, 0.5, f"Schéma non disponible\n{e}",
                    ha="center", va="center",
                    transform=ax.transAxes,
                    fontsize=12, color=theme.SCHEMA_COLORS["LEGENDE"])
    else:
        ax.text(0.5, 0.6, result["circuit_type"],
                ha="center", va="center", transform=ax.transAxes,
                fontsize=14, fontweight="bold", color=theme.SCHEMA_COLORS["TITRE"])
        ax.text(0.5, 0.45,
                "  ·  ".join(result["components"]),
                ha="center", va="center", transform=ax.transAxes,
                fontsize=11, color=theme.SCHEMA_COLORS["LEGENDE"], fontfamily="monospace")

    # Astuce de découvrabilité : si le schéma comporte des boîtes Z cliquables,
    # on l'indique (sinon l'utilisateur ne sait pas qu'il peut déplier les Z).
    # Placée en coords FIGURE sous le tracé, avec une marge basse réservée par
    # tight_layout(rect) : sinon elle chevauche un label bas du dessin (ex. Z2
    # du diviseur dans le suiveur, cf. buffer_reference ilot0).
    rect = (0, 0, 1, 1)
    if fig._z_hitboxes:
        fig.text(0.01, 0.012, "Astuce : cliquez une boîte Z pour voir le détail R/L/C",
                 fontsize=9, color=theme.SCHEMA_COLORS["LEGENDE"], va="bottom", ha="left")
        rect = (0, 0.05, 1, 1)

    # Marge réduite : le tracé occupe presque toute la figure (lisibilité).
    ax.margins(0.06)
    try:
        fig.tight_layout(rect=rect, pad=0.4)
    except Exception:
        _log.debug("tight_layout ignoré", exc_info=True)
    # Filet de sécurité mathématique : résout tout chevauchement de labels
    # restant (métriques réelles du renderer) et ré-étend les limites d'axe.
    # APRÈS tight_layout/margins (pas avant, contrairement à une première
    # tentative) : tight_layout()/ax.margins() peuvent réduire la boîte des
    # axes (subplot params), or la taille de police est fixée en POINTS (pas
    # en unités de données) -> une boîte plus petite pour le MÊME xlim/ylim
    # fait mécaniquement déborder un texte qui tenait tout juste avant. Seule
    # une résolution APRÈS que la géométrie finale des axes soit figée
    # garantit "aucun label clippé" pour de vrai (cf. gui/schema_labels.py).
    ajuster_labels(fig)
    return fig


def _make_chain_fig(ordered, comp_info, matches=None, detaille: bool = False):
    """@brief Figure d'une chaîne de montages connectés (vue îlot multi-AOP).

    Large par construction (un bloc par étage) : destinée à un conteneur à
    défilement horizontal. Hauteur bornée à 4.2" pour tenir dans la fenêtre.

    @param ordered Montages triés par flux (cf. _ordonner_montages_flux).
    @param comp_info Dict {ref -> {type, value}}.
    @param detaille Si True, les boîtes Z sont remplacées par le réseau R/L/C réel.
    @return matplotlib.figure.Figure (porte fig._z_hitboxes).
    """
    fig = Figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")
    fig._z_hitboxes = []
    fig._comp_positions = {}
    try:
        with schemdraw.Drawing(canvas=ax, show=False) as d:
            d.config(fontsize=12, inches_per_unit=0.5)
            d._z_hitboxes = []
            d._comp_positions = {}
            d._mode_detaille = detaille
            _draw_island_chain(d, ordered, ci=comp_info,
                               couplages=(matches or ordered))
            fig._z_hitboxes = list(d._z_hitboxes)
            fig._comp_positions = dict(d._comp_positions)
            try:
                bb = d.get_bbox()
                # get_bbox ne compte PAS le texte des étiquettes : on fixe des
                # limites explicites avec marge (Zf au-dessus, VIN/VOUT sur les
                # côtés, masses en dessous) et on cale l'aspect figure dessus.
                # Sinon set_aspect('equal') rogne/écrase le dernier étage.
                x0, x1 = bb.xmin - 1.5, bb.xmax + 1.8
                y0, y1 = bb.ymin - 0.7, bb.ymax + 0.9
                ax.set_xlim(x0, x1)
                ax.set_ylim(y0, y1)
                w, h = (x1 - x0), (y1 - y0)
                if w > 0 and h > 0:
                    haut = 4.2
                    fig.set_size_inches(haut * (w / h), haut)   # PAS de plafond : large -> scroll
            except Exception:
                _log.debug("ajustement de taille de figure ignoré", exc_info=True)
    except Exception as e:
        _log.warning("rendu du schéma échoué", exc_info=True)
        ax.text(0.5, 0.5, f"Schéma non disponible\n{e}", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color=theme.SCHEMA_COLORS["LEGENDE"])
    if fig._z_hitboxes:
        ax.text(0.005, 0.01, "Astuce : cliquez une boîte Z pour voir le détail R/L/C",
                transform=ax.transAxes, fontsize=9, color=theme.SCHEMA_COLORS["LEGENDE"], va="bottom", ha="left")
    ax.margins(0.04)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        _log.debug("tight_layout ignoré", exc_info=True)
    # Après tight_layout/margins (cf. commentaire de _make_fig) : la boîte
    # des axes est figée avant la résolution finale des labels.
    ajuster_labels(fig)
    return fig


def _make_branched_fig(layers, comp_info, matches=None, detaille: bool = False):
    """@brief Figure d'un îlot multi-AOP branché (DAG en couches, cf.
    _layers_montages_flux). Large et haute -> conteneur à défilement.

    @param layers list[list[match]] couches ordonnées.
    @param comp_info Dict {ref -> {type, value}}.
    @param detaille Si True, les boîtes Z sont remplacées par le réseau R/L/C réel.
    @return matplotlib.figure.Figure (porte fig._z_hitboxes).
    """
    fig = Figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")
    fig._z_hitboxes = []
    fig._comp_positions = {}
    try:
        with schemdraw.Drawing(canvas=ax, show=False) as d:
            d.config(fontsize=12, inches_per_unit=0.5)
            d._z_hitboxes = []
            d._comp_positions = {}
            d._mode_detaille = detaille
            _draw_branched_chain(d, layers, ci=comp_info,
                                 couplages=(matches or [m for L in layers for m in L]))
            fig._z_hitboxes = list(d._z_hitboxes)
            fig._comp_positions = dict(d._comp_positions)
            try:
                bb = d.get_bbox()
                x0, x1 = bb.xmin - 1.5, bb.xmax + 1.8
                y0, y1 = bb.ymin - 0.9, bb.ymax + 0.9
                ax.set_xlim(x0, x1)
                ax.set_ylim(y0, y1)
                w, h = (x1 - x0), (y1 - y0)
                if w > 0 and h > 0:
                    scale = 0.45                     # ~0.45"/unité, sans écraser l'aspect
                    fig.set_size_inches(min(40.0, w * scale), min(20.0, h * scale))
            except Exception:
                _log.debug("ajustement de taille de figure ignoré", exc_info=True)
    except Exception as e:
        _log.warning("rendu du schéma échoué", exc_info=True)
        ax.text(0.5, 0.5, f"Schéma non disponible\n{e}", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color=theme.SCHEMA_COLORS["LEGENDE"])
    if fig._z_hitboxes:
        ax.text(0.005, 0.01, "Astuce : cliquez une boîte Z pour voir le détail R/L/C",
                transform=ax.transAxes, fontsize=9, color=theme.SCHEMA_COLORS["LEGENDE"], va="bottom", ha="left")
    ax.margins(0.04)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        _log.debug("tight_layout ignoré", exc_info=True)
    # Après tight_layout/margins (cf. commentaire de _make_fig).
    ajuster_labels(fig)
    return fig


def _draw_paire_croisee(d, paire, ci):
    """@brief Deux portes empilées + contre-réactions croisées (latch SR).

    Chaque porte est dessinée par SON drawer (vue Z ou détaillée selon
    d._mode_detaille). Entrées de feedback masquées via in_label dict (le nom
    du net est déjà porté par la sortie de l'autre porte) ; entrées externes
    (S/R) et sorties (Q/Q̄) gardent leur vrai nom. Le croisement unique des
    deux fils de retour est le « X » classique du latch — croisement
    PERPENDICULAIRE assumé (cf. légende connexion).
    """
    g_haut, g_bas = paire
    _ih, o_haut = _io_montage(g_haut, ci)
    _ib, o_bas = _io_montage(g_bas, ci)
    dy = 6.0 if getattr(d, "_mode_detaille", False) else 2.2
    res_h = _dessiner_montage_a(d, g_haut, ci, (4.5, dy), {o_bas: ""}, None)
    res_b = _dessiner_montage_a(d, g_bas, ci, (4.5, -dy), {o_haut: ""}, None)
    _annoter_etage(d, res_h, g_haut)
    # Porte basse : expression seule. Son titre serait dans la bande médiane
    # (zone des retours croisés) et répéterait celui de la porte haute.
    gain_b = _texte_gain(g_bas, None)
    if gain_b:
        out_b = res_b["out"]
        d.add(elm.Label().at((out_b[0] + 1.4, out_b[1] - 0.85)).label(
            gain_b, color=_GAIN_COLOR, fontsize=8))

    # Canaux verticaux AU-DELÀ du texte des étiquettes d'entrée (~2 unités à
    # gauche du dot) : à x_ins-1.0 ils barraient « NET1 »/« NET5 » (audit D1).
    x_l = min(p[0] for r in (res_h, res_b) for p in r["ins"].values()) - 2.6
    for res_src, res_dst, net, y_gap, x_gauche in (
            (res_h, res_b, o_haut, +0.45, x_l),
            (res_b, res_h, o_bas, -0.45, x_l - 0.6)):
        out_pt = res_src["out"]
        in_pt = res_dst["ins"][net]
        # descente/montée VERTICALE depuis le dot de sortie (jamais vers la
        # droite : le label du net y est posé et serait barré par le fil)
        d.add(elm.Line().at(out_pt).to((out_pt[0], y_gap)))
        d.add(elm.Line().at((out_pt[0], y_gap)).to((x_gauche, y_gap)))
        d.add(elm.Line().at((x_gauche, y_gap)).to((x_gauche, in_pt[1])))
        d.add(elm.Line().at((x_gauche, in_pt[1])).to(in_pt))


def _make_latch_fig(paire, comp_info, matches=None, detaille: bool = False):
    """@brief Figure d'une paire croisée (latch SR) : deux portes empilées,
    retours croisés — à la place de l'échelle générique (audit D1).

    @param paire (g_haut, g_bas) de _paire_croisee.
    @return matplotlib.figure.Figure (porte fig._z_hitboxes).
    """
    fig = Figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")
    fig._z_hitboxes = []
    fig._comp_positions = {}
    try:
        with schemdraw.Drawing(canvas=ax, show=False) as d:
            d.config(fontsize=12, inches_per_unit=0.5)
            d._z_hitboxes = []
            d._comp_positions = {}
            d._mode_detaille = detaille
            _draw_paire_croisee(d, paire, comp_info)
            fig._z_hitboxes = list(d._z_hitboxes)
            fig._comp_positions = dict(d._comp_positions)
            try:
                bb = d.get_bbox()
                x0, x1 = bb.xmin - 1.5, bb.xmax + 1.8
                y0, y1 = bb.ymin - 0.9, bb.ymax + 0.9
                ax.set_xlim(x0, x1)
                ax.set_ylim(y0, y1)
                w, h = (x1 - x0), (y1 - y0)
                if w > 0 and h > 0:
                    scale = 0.45
                    fig.set_size_inches(min(40.0, w * scale), min(20.0, h * scale))
            except Exception:
                _log.debug("ajustement de taille de figure ignoré", exc_info=True)
    except Exception as e:
        _log.warning("rendu du schéma échoué", exc_info=True)
        ax.text(0.5, 0.5, f"Schéma non disponible\n{e}", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color=theme.SCHEMA_COLORS["LEGENDE"])
    ax.margins(0.04)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        _log.debug("tight_layout ignoré", exc_info=True)
    ajuster_labels(fig)
    return fig


def _make_puce_fig(ref, entree, comp_info, matches, detaille: bool = False):
    """@brief Figure d'un îlot « 1 puce identifiée + Z autour » — boîte puce
    (elm.Ic, cf. gui.puce_schematic) et boîtes Z cliquables pour les réseaux
    passifs voisins (charges/couplages), à la place de la grille générique.

    @param ref Référence de la puce (ex. "U1").
    @param entree Entrée catalogue (cf. circuit_analyzer.catalogue.identifier).
    @return matplotlib.figure.Figure (porte fig._z_hitboxes/_comp_positions).
    """
    fig = Figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")
    fig._z_hitboxes = []
    fig._comp_positions = {}
    try:
        with schemdraw.Drawing(canvas=ax, show=False) as d:
            d.config(fontsize=12, inches_per_unit=0.5)
            d._z_hitboxes = []
            d._comp_positions = {}
            d._mode_detaille = detaille
            from gui import puce_schematic
            # Titre différé (titre=False) : les Z locales dessinées ensuite
            # peuvent dépasser au-dessus des broches du HAUT (ex. VCC) — le
            # titre est replacé APRÈS, au-dessus de la bbox réelle, pour ne
            # jamais chevaucher une boîte Z (cf. dessiner_z_locales).
            res = puce_schematic.dessiner_puce(d, ref, entree, comp_info,
                                               titre=False)
            coupl = [m for m in (matches or []) if _est_couplage(m)]
            puce_schematic.dessiner_z_locales(d, res, coupl, comp_info)
            try:
                bb_titre = d.get_bbox()
                title_pt = (res["title"][0], bb_titre.ymax + 0.4)
            except Exception:
                title_pt = res["title"]
            d.add(elm.Label().at(title_pt).label(
                f"{entree['categorie']} ({entree['nom']})",
                color=_TITRE_COLOR, fontsize=11))
            fig._z_hitboxes = list(d._z_hitboxes)
            fig._comp_positions = dict(d._comp_positions)
            try:
                bb = d.get_bbox()
                x0, x1 = bb.xmin - 1.5, bb.xmax + 1.8
                y0, y1 = bb.ymin - 0.9, bb.ymax + 0.9
                ax.set_xlim(x0, x1)
                ax.set_ylim(y0, y1)
                w, h = (x1 - x0), (y1 - y0)
                if w > 0 and h > 0:
                    scale = 0.45
                    fig.set_size_inches(min(40.0, w * scale), min(20.0, h * scale))
            except Exception:
                _log.debug("ajustement de taille de figure ignoré", exc_info=True)
    except Exception as e:
        _log.warning("rendu du schéma échoué", exc_info=True)
        ax.text(0.5, 0.5, f"Schéma non disponible\n{e}", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color=theme.SCHEMA_COLORS["LEGENDE"])
    ax.margins(0.04)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        _log.debug("tight_layout ignoré", exc_info=True)
    ajuster_labels(fig)
    return fig


def _make_island_fig(model, matches=None, detaille: bool = False):
    """@brief Construit un vrai rendu schematique d'un ilot.

    Le rendu n'utilise plus des bulles composant/net. Il fabrique un petit
    plan electrique : chemin principal gauche-droite, derives vers rails, puis
    symboles generiques pour les composants multi-broches.

    @param model Modele d'ilot (cf. _build_island_model).
    @param detaille Drapeau pose sur le Drawing (`d._mode_detaille`) ; les
        lignes d'impedance Z du rendu generique sont alors deplies sans hitbox.
    @return matplotlib.figure.Figure Figure prete a afficher/exporter.
    """
    components = model["components"]
    plan = _build_island_schematic_plan(model)
    width = max(8.0, 1.4 * max(2, len(plan["columns"])) + 6.0)
    # hauteur proportionnelle a l'extent vertical reel (bandes), pas au nombre de
    # lignes : le compactage reduit le nombre de bandes, donc la figure raccourcit.
    yvals = [r["y"] for r in plan["rows"]] or [0.0]
    height = max(4.8, 0.7 * (max(yvals) - min(yvals)) + 3.0)
    # Largeur non plafonnee a l'ecrasement : les gros ilots s'affichent a taille
    # native et defilent horizontalement (cf. show_island). Hauteur bornee (pas de
    # scroll vertical confortable).
    fig = Figure(figsize=(min(40.0, width), min(15.0, height)))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")

    hitboxes = []
    fig._z_hitboxes = hitboxes   # zones cliquables des Z (renseignees par le drawer)
    fig._comp_positions = {}   # registre ref -> position (renseigné par le drawer)

    if not components:
        ax.text(0.5, 0.5, "Ilot vide", ha="center", va="center",
                transform=ax.transAxes, fontsize=13, color=theme.SCHEMA_COLORS["LEGENDE"])
        ajuster_labels(fig)
        return fig

    try:
        with schemdraw.Drawing(canvas=ax, show=False) as d:
            d.config(fontsize=10, inches_per_unit=0.5)
            d._mode_detaille = detaille
            d._comp_positions = {}
            _draw_island_schematic(d, plan, hitboxes)
            fig._comp_positions = dict(d._comp_positions)
    except Exception as exc:
        _log.warning("schéma automatique de l'îlot indisponible", exc_info=True)
        ax.text(0.5, 0.56, model.get("label", "Ilot"),
                ha="center", va="center", transform=ax.transAxes,
                fontsize=14, fontweight="bold", color=theme.SCHEMA_COLORS["TITRE"])
        ax.text(0.5, 0.44, f"Schema automatique indisponible\n{exc}",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=10, color=theme.SCHEMA_COLORS["LEGENDE"])

    caption = plan["caption"]
    if hitboxes:
        caption += "   ·   cliquez un Z pour voir sa composition (R/L/C)"
    ax.text(0.01, 0.01, caption, transform=ax.transAxes,
            fontsize=8, color=theme.SCHEMA_COLORS["LEGENDE"], va="bottom", ha="left")
    ax.margins(0.16)
    fig.subplots_adjust(left=0.03, right=0.97, top=0.96, bottom=0.06)
    # Après margins/subplots_adjust (cf. commentaire de _make_fig).
    ajuster_labels(fig)
    return fig


def _matches_for_island(ilot, results):
    if not results:
        return []
    matches = []
    for idx in ilot.get("circuits", []):
        try:
            matches.append(results[idx])
        except (TypeError, IndexError):
            continue
    return matches


def _ordonner_montages_flux(matches, ci=None):
    """@brief Ordonne des montages par flux de signal (OUT(N) -> IN(N+1)).

    Les couplages (Impédance Z 2 nœuds) sont retirés des étages et utilisés pour
    relier deux étages séparés par un condensateur de liaison (via union-find).
    Les nets d'E/S sont résolus selon le type (`_io_montage`). @return montages
    triés entrée->sortie, ou None si ce n'est pas une chaîne linéaire unique.
    """
    etages = [m for m in matches if not _est_couplage(m)]
    if len(etages) < 2:
        return None
    ci = ci or {}
    find = _couplage_find(matches)

    io = {}
    for m in etages:
        ins, out = _io_montage(m, ci)
        io[id(m)] = ([find(n) for n in ins if n], find(out) if out else None)

    par_in = {}
    for m in etages:
        for net in io[id(m)][0]:
            par_in.setdefault(net, []).append(m)
    outs = {io[id(m)][1] for m in etages if io[id(m)][1] is not None}

    # Tête de chaîne : un étage dont aucune entrée n'est la sortie d'un autre.
    tetes = [m for m in etages if not any(n in outs for n in io[id(m)][0])]
    if len(tetes) != 1:
        return None

    ordre, vus, courant = [], set(), tetes[0]
    while courant is not None and id(courant) not in vus:
        ordre.append(courant)
        vus.add(id(courant))
        out = io[id(courant)][1]
        suivants = [s for s in par_in.get(out, []) if id(s) not in vus] if out else []
        if len(suivants) > 1:
            return None                      # bifurcation : pas linéaire
        courant = suivants[0] if suivants else None

    if len(ordre) != len(etages):
        return None
    return ordre


def _in_nets(m):
    """@brief Nets d'entrée d'un montage (côté source du signal), selon son type.

    Différentiel : nœuds extérieurs de Z1 et Z3. Sommateur : nœud extérieur de
    chaque entrée Zin (liste). Inverseur/intégrateur/dérivateur : nœud extérieur de
    Zin. Non-inverseur/suiveur/comparateur : net IN+ (nodes[0]).
    @return list[str] nets d'entrée.
    """
    imp = m.get("impedances") or {}
    if "Z1" in imp and "Z3" in imp:
        return [imp["Z1"]["nodes"][1], imp["Z3"]["nodes"][1]]
    zin = imp.get("Zin")
    if isinstance(zin, list):
        return [e["nodes"][1] for e in zin]
    if isinstance(zin, dict):
        return [zin["nodes"][1]]
    return [m["nodes"][0]]


_MONTAGES_TRANSISTOR_CHAINABLES = {
    "Amplificateur émetteur commun",
    "Transistor en commutation",
    "Collecteur commun (suiveur d'émetteur)",
    "Étage push-pull",
    "Paire Darlington",
}
_MONTAGES_TRANSISTOR_TERMINAUX = {
    "Miroir de courant BJT",
    "Commande de relais",
    "MOSFET en commutation",
    "MOSFET haute-tension (côté haut)",
}
# Portes CMOS : mêmes contrats de chaînage que les montages transistor
# (dispatch direct via _DRAWERS dans _dessiner_montage_a) -- sinon la chaîne/
# le DAG de portes (logic_chaine_and.xml, logic_dag_2vers1.xml) retombe sur
# _draw_follower (drawer AOP générique) et aucune ref M n'est enregistrée.
_MONTAGES_PORTES_CMOS = {
    "Inverseur (CMOS)",
    "Porte NAND (CMOS)",
    "Porte NOR (CMOS)",
}


def _io_transistor(match, ci):
    """@brief (in_nets, out_net) d'un montage transistor via les broches du Q.

    Émetteur commun / commutation : OUT = collecteur. Suiveur / push-pull :
    OUT = émetteur. Darlington : IN = base(Q1), OUT = émetteur(Q2).
    """
    ct = match["circuit_type"]
    qs = [r for r in match["components"] if ci.get(r, {}).get("type") == "Q"]
    pins = {r: ci.get(r, {}).get("pins", {}) for r in qs}
    if not qs:
        return [match["nodes"][0]] if match.get("nodes") else [], None
    if ct == "Paire Darlington":
        emetteurs = {pins[r].get("E") for r in qs}
        q2 = next((r for r in qs if pins[r].get("B") in emetteurs), qs[-1])
        q1 = next((r for r in qs if r != q2), qs[0])
        return [pins[q1].get("B")], _darlington_sortie(pins[q2])
    p = pins[qs[0]]
    if ct in ("Collecteur commun (suiveur d'émetteur)", "Étage push-pull"):
        return [p.get("B")], p.get("E")
    return [p.get("B")], p.get("C")


def _darlington_config(q2_pins):
    """@brief Configuration d'un Darlington d'après les broches de Q2.

    @return "emetteur_commun" si l'émetteur de Q2 est à la masse (sortie sur le
        collecteur), sinon "suiveur" (collecteurs au rail, sortie sur l'émetteur).
    """
    emetteur, collecteur = q2_pins.get("E"), q2_pins.get("C")
    if is_ground_net(emetteur) and not is_power_net(collecteur):
        return "emetteur_commun"
    return "suiveur"


def _darlington_sortie(q2_pins):
    """@brief Net de sortie d'un Darlington : collecteur (émetteur commun) ou
    émetteur (suiveur), selon la configuration."""
    if _darlington_config(q2_pins) == "emetteur_commun":
        return q2_pins.get("C")
    return q2_pins.get("E")


def _io_montage(match, ci):
    """@brief Nets d'entrée/sortie d'un montage, selon son type.

    PRIORITÉ au contrat embarqué `match['io']` ({'ins': [...], 'out': net}) :
    les nouvelles familles (portes CMOS...) transportent leur propre routage
    — plus AUCUNE extension de whitelist par circuit_type (décision revue
    d'architecture 2026-07-08). Familles historiques sans `io` : inchangées.

    AOP (et montages historiques) : (_in_nets, nodes[-1]) — inchangé. Transistor
    chaînable : via broches. Transistor terminal : out_net = None (jamais relié
    en aval). @return (in_nets: list[str], out_net: str | None).
    """
    io = match.get("io")
    if io is not None:
        return list(io.get("ins") or []), io.get("out")
    ct = match.get("circuit_type", "")
    if ct in _MONTAGES_TRANSISTOR_CHAINABLES:
        return _io_transistor(match, ci)
    if ct in _MONTAGES_TRANSISTOR_TERMINAUX:
        return _in_nets(match), None
    return _in_nets(match), match["nodes"][-1]


def _est_couplage(match):
    """@brief Vrai si le match est un dipôle de couplage (Impédance Z à 2 nœuds)."""
    return (match.get("circuit_type") == "Impédance Z"
            and len(match.get("nodes", ())) == 2)


def _couplage_find(matches):
    """@brief Union-find des nets reliés par un couplage (Cc, R série…).

    @return fonction find(net) -> représentant ; deux nets reliés par un dipôle
            de couplage partagent le même représentant.
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        racine = x
        while parent[racine] != racine:
            racine = parent[racine]
        while parent[x] != racine:        # compression de chemin
            parent[x], x = racine, parent[x]
        return racine

    for m in matches:
        if _est_couplage(m):
            n1, n2 = m["nodes"]
            parent[find(n1)] = find(n2)
    return find


def _layers_montages_flux(matches, ci=None):
    """@brief Ordonne des montages branchés en couches (DAG par flux de signal).

    Pour les îlots non linéaires (ex. PID : entrée → P/I/D parallèles → sommateur →
    buffer). Arête producteur→consommateur quand out_net(producteur) ∈ in_nets(conso).
    Les étages ayant une entrée *externe* (non produite par un autre étage) sont des
    sources (couche 0) ; un back-edge vers une source est ignoré (tolère les boucles
    issues d'une détection imparfaite). Profondeur = plus long chemin depuis une source.

    @param matches Matches d'un même îlot.
    @return list[list[match]] couches ordonnées (≥ 2), ou None si pas exploitable.
    """
    ci = ci or {}
    stages = [m for m in matches if not _est_couplage(m)]
    if len(stages) < 2:
        return None
    find = _couplage_find(matches)

    out_net = {}
    in_nets = {}
    for m in stages:
        ins, out = _io_montage(m, ci)
        out_net[id(m)] = find(out) if out else None
        in_nets[id(m)] = [find(n) for n in ins if n]
    producteurs = {out_net[id(m)]: m for m in stages if out_net[id(m)] is not None}

    incoming = {}      # id(stage) -> list des étages producteurs (dans l'îlot)
    a_entree_externe = {}
    for m in stages:
        prods = []
        externe = False
        for net in in_nets[id(m)]:
            p = producteurs.get(net)
            if p is not None and p is not m:
                prods.append(p)
            else:
                externe = True            # net non produit par un étage = entrée externe
        incoming[id(m)] = prods
        a_entree_externe[id(m)] = externe

    # Sources : entrée externe (signal d'entrée), fixées en couche 0.
    layer = {id(m): (0 if a_entree_externe[id(m)] else None) for m in stages}

    for _ in range(len(stages)):           # relaxation bornée (longest-path, sources figées)
        change = False
        for m in stages:
            if a_entree_externe[id(m)]:
                continue                   # source figée à 0 -> ignore les back-edges
            niveaux = [layer[id(p)] for p in incoming[id(m)] if layer[id(p)] is not None]
            if niveaux:
                nouveau = 1 + max(niveaux)
                if layer[id(m)] != nouveau:
                    layer[id(m)] = nouveau
                    change = True
        if not change:
            break

    if any(layer[id(m)] is None for m in stages):
        return None                        # étage non rattaché (cycle pur / isolé)

    profondeur_max = max(layer.values())
    if profondeur_max < 1:
        return None                        # tout en une couche : pas une chaîne
    couches = [[] for _ in range(profondeur_max + 1)]
    for m in stages:                       # ordre d'apparition préservé dans chaque couche
        couches[layer[id(m)]].append(m)
    return couches


def _paire_croisee(matches, ci):
    """@brief Deux portes CMOS bouclées l'une sur l'autre (latch SR), ou None.

    Le layout par flux rejette ce motif : chaque porte a une entrée EXTERNE
    (S/R) donc les deux sont « sources » en couche 0 -> profondeur 0 -> repli
    échelle générique (audit D1). Reconnaissance : exactement 2 étages, la
    sortie de chacun figure dans les entrées de l'autre.

    @return (g_haut, g_bas) ordonnée par net de sortie (déterministe), ou None.
    """
    stages = [m for m in matches if not _est_couplage(m)]
    if len(stages) != 2:
        return None
    if any(m.get("circuit_type") not in _MONTAGES_PORTES_CMOS for m in stages):
        return None
    (i1, o1), (i2, o2) = (_io_montage(m, ci) for m in stages)
    if not o1 or not o2 or o1 == o2:
        return None
    if o1 not in (i2 or []) or o2 not in (i1 or []):
        return None
    return tuple(sorted(stages, key=lambda m: _io_montage(m, ci)[1]))


_NC_NAMES = {"NC", "N/C", "NRELIEE", ""}
ROW_PITCH = 2.0        # pas vertical entre deux bandes de dipoles (symbole + label + marge)
MULTI_PITCH = 3.4      # pas elargi autour d'un composant multi-broches (AOP, bloc)
COL_PITCH = 2.4
LABEL_LINE = 0.5       # rallonge le pas quand une bande porte une valeur (2 lignes)
BAND_GAP = 1.0         # marge horizontale entre deux dipoles d'une meme bande
STUB_REACH = 3.4       # extent x d'un moignon (symbole + fil + label/drapeau de net)
ISO_REACH = 2.0        # extent x d'un dipole isole


def _dipole_span(pins, x_by_net):
    """@brief Extent horizontal [lo, hi] occupe par le dessin d'un dipole.

    Sert au compactage : deux dipoles dont les extents ne se chevauchent pas
    peuvent partager la meme bande (meme y). Entre deux colonnes -> [xa, xb] ;
    moignon E/S -> [x_colonne, +STUB_REACH] ; isole -> [0, ISO_REACH].
    """
    cols = sorted(x_by_net[n] for _p, n in pins if n in x_by_net)
    if len(cols) >= 2:
        return (cols[0], cols[-1])
    if len(cols) == 1:
        return (cols[0], cols[0] + STUB_REACH)
    return (0.0, ISO_REACH)


def _pack_bands(spans):
    """@brief Range des intervalles en bandes sans chevauchement (partition par
    intervalles, glouton par bord gauche). @return liste d'index de bande par span."""
    band_of = [0] * len(spans)
    bands = []   # par bande : liste d'intervalles (lo, hi) deja occupes
    # tri par bord gauche, puis largeur decroissante (les intervalles larges, plus
    # durs a caser, sont places en premier -> moins de bandes au total).
    for i in sorted(range(len(spans)),
                    key=lambda k: (spans[k][0], -(spans[k][1] - spans[k][0]))):
        lo, hi = spans[i]
        placed = next(
            (bi for bi, occ in enumerate(bands)
             if all(hi + BAND_GAP <= o_lo or o_hi + BAND_GAP <= lo
                    for o_lo, o_hi in occ)),
            None,
        )
        if placed is None:
            placed = len(bands)
            bands.append([])
        bands[placed].append((lo, hi))
        band_of[i] = placed
    return band_of


def _make_row(comp, y, net_pins, col_nets):
    """@brief Construit une ligne de plan (dipole ou device) a l'ordonnee y."""
    pins = list((comp.get("pins", {}) or {}).items())
    stubs = [(p, n) for p, n in pins if n in net_pins and n not in col_nets]
    return {
        "ref": comp.get("ref", "?"),
        "type": comp.get("type", "?"),
        "value": comp.get("value", ""),
        "symbol": comp.get("symbol") or _schematic_symbol(comp.get("type", "?")),
        "y": y,
        "pins": pins,
        "stubs": stubs,
        "refs": comp.get("refs", [comp.get("ref")]),
        "composition": comp.get("composition", comp.get("ref", "")),
        "detail_info": comp.get("detail_info", {}),
        "boite_ic": comp.get("boite_ic", False),
    }


def _is_multi_pin(comp) -> bool:
    """@brief Vrai si le composant occupe une bande haute (AOP ou >2 broches)."""
    pins = comp.get("pins", {}) or {}
    return _schematic_symbol(comp.get("type", "?")) == "opamp" or len(pins) > 2


def _is_not_connected(net) -> bool:
    """@brief Vrai si le net est « non connecte » (NC, vide) — pas de colonne ni stub."""
    return (not net) or net.upper() in _NC_NAMES


def _net_kind(net: str) -> str:
    """@brief Classe un net : 'ground', 'power' ou 'signal'."""
    if is_ground_net(net) or is_protective_earth_net(net):
        return "ground"
    if is_power_net(net):
        return "power"
    return "signal"


def _schematic_symbol(ctype):
    """@brief Symbole schematique associe a un type de composant."""
    return {
        "Z": "impedance",
        "R": "resistor",
        "C": "capacitor",
        "L": "inductor",
        "D": "diode",
        "F": "fuse",
        "SW": "switch",
        "U": "opamp",
        "Q": "bjt",
        "M": "mosfet",
        "K": "relay",
        "X": "connector",
        "J": "jumper",
    }.get(ctype, "block")


def _build_island_schematic_plan(model):
    """@brief Plan netlist-fidele assaini d'un ilot (fonction pure, testable).

    Filtre les nets (NC supprimes ; E/S a 1 connexion -> moignon ; >=2 -> colonne),
    ordonne les colonnes-bus, puis COMPACTE les dipoles en bandes horizontales :
    ceux dont les extents x ne se chevauchent pas partagent une bande (meme y),
    ce qui reduit la hauteur et casse l'escalier diagonal. Les composants
    multi-broches (AOP/blocs) occupent une bande chacun, sous les dipoles.

    @param model Modele d'ilot (cf. _build_island_model).
    @return dict {label, columns, rows, caption}.
    """
    components = list(model.get("components", []))

    # Connexions par net (dans l'ilot), en ignorant NC / vides.
    net_pins = {}
    for comp in components:
        for pin, net in (comp.get("pins", {}) or {}).items():
            if _is_not_connected(net):
                continue
            net_pins.setdefault(net, []).append((comp["ref"], pin))

    # Nets-hubs rendus en drapeaux locaux (pas en colonnes-bus) : la masse toujours
    # (convention CAO), l'alimentation seulement si elle est peripherique. Un rail
    # d'alim dominant (relie a >= la moitie des unites) reste une colonne.
    # ponytail: fraction 0.5, a ajuster si un rail legitime passe en drapeaux.
    n_comps = len(components)

    def _is_hub(net):
        kind = _net_kind(net)
        if kind == "ground":
            return True
        if kind == "power":
            return len(net_pins.get(net, [])) < max(2, n_comps / 2)
        return False

    col_nets = {net for net, pins in net_pins.items()
                if len(pins) >= 2 and not _is_hub(net)}

    dipoles = [c for c in components if not _is_multi_pin(c)]
    devices = [c for c in components if _is_multi_pin(c)]

    columns = _order_columns(col_nets)
    x_by_net = {c["net"]: c["x"] for c in columns}

    # Compactage des dipoles en bandes (anti-escalier).
    dip_pins = [list((c.get("pins", {}) or {}).items()) for c in dipoles]
    spans = [_dipole_span(p, x_by_net) for p in dip_pins]
    band_of = _pack_bands(spans)
    n_bands = max(band_of) + 1 if band_of else 0

    # Une bande dont un dipole porte une valeur est espacee davantage (label 2 lignes).
    band_value = [False] * n_bands
    for c, bi in zip(dipoles, band_of):
        if c.get("value"):
            band_value[bi] = True

    band_y = []
    y = 0.0
    for bi in range(n_bands):
        if bi > 0:
            y -= ROW_PITCH + (LABEL_LINE if (band_value[bi] or band_value[bi - 1]) else 0.0)
        band_y.append(y)

    rows = []
    # Dipoles ordonnes par (bande, bord gauche, ref) -> rendu deterministe, et les
    # dipoles d'une meme paire (meme span) restent contigus.
    for i in sorted(range(len(dipoles)),
                    key=lambda k: (band_of[k], spans[k][0], dipoles[k].get("ref", ""))):
        rows.append(_make_row(dipoles[i], band_y[band_of[i]], net_pins, col_nets))

    # Composants multi-broches : places pres du barycentre vertical de leurs
    # colonnes (fils courts), en evitant le recouvrement (>= MULTI_PITCH entre eux).
    col_y = {}
    for net in col_nets:
        ys = [r["y"] for r in rows if net in (n for _p, n in r["pins"])]
        if ys:
            col_y[net] = sum(ys) / len(ys)
    floor = band_y[-1] if band_y else 0.0

    def _target_y(dev):
        ys = [col_y[n] for n in (dev.get("pins", {}) or {}).values() if n in col_y]
        return sum(ys) / len(ys) if ys else floor

    last = None
    for dev in sorted(devices, key=lambda d: -_target_y(d)):
        ty = _target_y(dev)
        y = ty if last is None else min(ty, last - MULTI_PITCH)
        rows.append(_make_row(dev, y, net_pins, col_nets))
        last = y

    _fill_column_extents(columns, net_pins, rows)

    return {
        "label": model.get("label", "Ilot"),
        "columns": columns,
        "rows": rows,
        "caption": "● connexion — un croisement sans point n'est pas une liaison",
    }


def _order_columns(col_nets):
    """@brief Ordonne les colonnes-bus (masse gauche / signal / alim droite) et leur
    assigne une abscisse fixe, independante du placement vertical.

    @return list[dict] {net, x, kind, y_top, y_bottom} (extents remplis ensuite).
    """
    order = {"ground": 0, "signal": 1, "power": 2}
    ordered = sorted(col_nets, key=lambda net: (order[_net_kind(net)], net))
    return [
        {"net": net, "x": float(i * COL_PITCH), "kind": _net_kind(net),
         "y_top": 0.0, "y_bottom": 0.0}
        for i, net in enumerate(ordered)
    ]


def _fill_column_extents(columns, net_pins, rows):
    """@brief Rogne l'extent vertical de chaque colonne aux lignes qui la touchent."""
    y_by_ref = {r["ref"]: r["y"] for r in rows}
    for c in columns:
        ys = [y_by_ref[ref] for ref, _pin in net_pins.get(c["net"], []) if ref in y_by_ref]
        if ys:
            c["y_top"], c["y_bottom"] = max(ys), min(ys)


_SYMBOL_ELM = {
    "impedance": elm.ResistorIEC,   # boite rectangulaire = impedance generique Z
    "resistor": elm.Resistor,
    "capacitor": elm.Capacitor,
    "inductor": elm.Inductor2,
    "diode": elm.Diode,
    "fuse": elm.Fuse,
    "switch": elm.Switch,
    "jumper": elm.Jumper,
}


def _draw_island_schematic(d, plan, hitboxes=None):
    """@brief Dessine le schema assaini a partir du plan (colonnes + lignes + stubs).

    @param hitboxes Liste (optionnelle) remplie de zones cliquables des Z :
        (x0, x1, y0, y1, refs, composition) en coordonnees data.
    """
    columns = plan["columns"]
    rows = plan["rows"]
    if not columns and not rows:
        return
    x_by_net = {c["net"]: c["x"] for c in columns}
    # Voie dediee a droite pour les composants multi-broches (AOP, blocs) :
    # ils y sont empiles par ligne, donc deux composants actifs ne se chevauchent
    # jamais (chacun a son y) et ne se regroupent plus au barycentre.
    device_x = max((c["x"] for c in columns), default=0.0) + COL_PITCH

    # Colonnes-bus rognees : ligne verticale + etiquette + masse eventuelle.
    for c in columns:
        # les colonnes ne sont jamais des nets de masse (rendus en drapeaux locaux).
        top = c["y_top"] + 0.5
        bottom = c["y_bottom"] - 0.5
        d += elm.Line().at((c["x"], top)).to((c["x"], bottom)).color(_BUS)
        d += elm.Dot().at((c["x"], top)).label(
            c["net"], loc="top", color=_BUS, ofst=_LBL_OFST)

    for row in rows:
        cols_pins = [(p, n) for p, n in row["pins"] if n in x_by_net]
        if row["symbol"] != "opamp" and len(row["pins"]) == 2:
            # label toujours en haut : le pas adaptatif garantit l'air necessaire.
            _draw_two_pin_row(d, row, x_by_net, "top", hitboxes)
        else:
            _draw_block_row(d, row, cols_pins, x_by_net, device_x)


def _draw_net_end(d, net, at=None, loc="right"):
    """@brief Termine un fil sur un net : drapeau de masse/alim si net-hub, sinon
    point + nom de net (convention CAO ; @at None = position courante du dessin)."""
    kind = _net_kind(net)
    if kind == "ground":
        el = elm.Ground()
    elif kind == "power":
        el = elm.Vdd().label(net, loc="top", color=_BUS, ofst=_LBL_OFST)
    else:
        el = elm.Dot().label(net, loc=loc, color=_BUS, ofst=_LBL_OFST)
    d += el.at(at) if at is not None else el


def _draw_two_pin_row(d, row, x_by_net, label_loc="top", hitboxes=None):
    """@brief Composant 2 broches : symbole entre deux colonnes, ou colonne->moignon E/S."""
    (p1, n1), (p2, n2) = row["pins"]
    x1, x2 = x_by_net.get(n1), x_by_net.get(n2)
    y = row["y"]
    element = _SYMBOL_ELM.get(row["symbol"], elm.Resistor)
    label = _component_label(row)

    def _draw_symbol(p1, p2):
        if getattr(d, "_mode_detaille", False) and row["symbol"] == "impedance":
            if _z_reseau(d, p1, p2, row, row.get("detail_info", {})):
                return
        _ajouter_symbole(d, element().at(p1).to(p2), row, label, label_loc)

    def _hit(xa, xb):
        # zone cliquable d'un Z (un peu elargie) pour ouvrir sa composition.
        if (hitboxes is not None and row["symbol"] == "impedance"
                and not getattr(d, "_mode_detaille", False)):
            hitboxes.append((min(xa, xb) - 0.3, max(xa, xb) + 0.3, y - 0.5, y + 0.5,
                             row.get("refs", []), row.get("composition", "")))

    if x1 is not None and x2 is not None and x1 != x2:
        left, right = sorted((x1, x2))
        mid = (left + right) / 2
        slen = min(1.6, max(0.8, right - left - 0.6))
        d += elm.Dot().at((left, y)).color(_WIRE)
        d += elm.Line().at((left, y)).tox(mid - slen / 2).color(_WIRE)
        _draw_symbol((mid - slen / 2, y), (mid + slen / 2, y))
        d += elm.Line().at((mid + slen / 2, y)).tox(right).color(_WIRE)
        d += elm.Dot().at((right, y)).color(_WIRE)
        _hit(mid - slen / 2, mid + slen / 2)
        return

    if x1 is not None or x2 is not None:
        # un cote sur un bus, l'autre est une E/S (moignon etiquete).
        if x1 is not None:
            col_x, stub_net = x1, n2
        else:
            col_x, stub_net = x2, n1
        d += elm.Dot().at((col_x, y)).color(_WIRE)
        d += elm.Line().at((col_x, y)).right(0.3).color(_WIRE)
        _draw_symbol((col_x + 0.3, y), (col_x + 1.7, y))
        d += elm.Line().at((col_x + 1.7, y)).right(0.35).color(_WIRE)
        if not _is_not_connected(stub_net):
            _draw_net_end(d, stub_net)
        _hit(col_x + 0.3, col_x + 1.7)
        return

    # composant isole (deux moignons) : symbole HORIZONTAL + deux bornes etiquetees.
    # On ne met PAS de drapeau masse/alim ici : les deux bouts sont les bornes du
    # dipole (ses ports), pas des rails distribues -> bornes nommees, dipole droit.
    _draw_symbol((0.0, y), (1.4, y))
    if not _is_not_connected(n1):
        d += elm.Dot().at((0.0, y)).label(n1, loc="left", color=_BUS, ofst=_LBL_OFST)
    if not _is_not_connected(n2):
        d += elm.Dot().at((1.4, y)).label(n2, loc="right", color=_BUS, ofst=_LBL_OFST)
    _hit(0.0, 1.4)


def _draw_block_row(d, row, cols_pins, x_by_net, device_x):
    """@brief Composant multi-broches : AOP (triangle) ou bloc, place dans la voie
    dediee a droite (device_x), broches cablees vers les colonnes."""
    y = row["y"]
    if row["symbol"] == "opamp":
        op = elm.Opamp().at((device_x, y)).right().color(_WIRE).fill(_OPAMP_FILL).label(
            row["ref"], loc="center")
        d += op
        block_right = tuple(op.out)          # pointe droite du triangle
    else:
        d += elm.Rect(w=1.8, h=0.8).at((device_x, y)).label(row["ref"])
        block_right = (device_x + 0.9, y)    # bord droit du bloc
    _enregistrer_position(d, row.get("ref"), (device_x, y))

    for pin, net in cols_pins:
        x = x_by_net[net]
        d += elm.Line().at((x, y)).to((device_x, y)).color(_WIRE)
        # pas de label de broche : le nom de pin (IN+/IN-/OUT) est redondant avec
        # les marques +/- du triangle et encombre le milieu du schema.
        d += elm.Dot().at((x, y)).color(_WIRE)

    # le moignon de sortie quitte le bord droit du symbole, jamais son centre
    # (sinon le label de net chevauche l'etiquette ref de l'AOP) ; plusieurs
    # moignons sont decales verticalement pour ne pas se superposer.
    stub_dy = 0.0
    for pin, net in row["stubs"]:
        if _is_not_connected(net):
            continue
        d += elm.Line().at((block_right[0], block_right[1] + stub_dy)).right(0.6).color(_WIRE)
        _draw_net_end(d, net)
        stub_dy += 0.7


def _component_label(comp):
    if comp.get("symbol") == "impedance":
        composition = comp.get("composition") or comp.get("ref", "Z")
        return f"{comp['ref']}\n{composition}" if composition != comp.get("ref") else comp["ref"]
    value = comp.get("value") or ""
    return f"{comp['ref']}\n{value}" if value else comp["ref"]


def _couleur_symbole(row):
    """@brief (couleur de trait, remplissage|None) d'un symbole d'îlot selon son type.

    Boîte Z → bleu rempli (cohérent avec la vue AOP) ; R/C/L → couleur par type ;
    autre → fil slate. Unifie le langage visuel des trois vues.
    """
    if row.get("symbol") == "impedance":
        return _Z_EDGE, _Z_FILL
    return _COMP_COLORS.get(row.get("type", ""), _WIRE), None


def _ajouter_symbole(d, element, row, label, label_loc):
    """@brief Ajoute un symbole 2 bornes coloré (déjà positionné via .at/.right)."""
    coul, rempl = _couleur_symbole(row)
    el = element.color(coul)
    if rempl:
        el = el.fill(rempl)
    d += el.label(label, loc=label_loc, color=coul)


def _bbox_contenu(fig):
    """@brief Bbox DATA (x0, x1, y0, y1) du contenu reel d'un axe de schema
    d'ilot -- union des Text de l'axe (rendu reel du renderer, meme technique
    que `gui.schema_labels.ajuster_labels`/`_reetendre_axes` : mesure via
    `Text.get_window_extent` puis inversion par `ax.transData`) et des
    donnees Line2D/patches deja tenues a jour par `ax.dataLim` (cf.
    commentaire historique de `_make_fig` sur l'autoscale qui ignore les
    Text mais suit bien Line2D/Patch).

    Sert au cadrage de l'export PNG (`_exporter_figure`) : les limites d'axe
    AFFICHEES a l'ecran sont volontairement asymetriques (marges de cadrage,
    extensions unilaterales de l'anti-collision de labels) -> le contenu reel
    y est souvent decentre.

    N'inclut QUE les Text ancres en coordonnees DATA (`t.get_transform() is
    ax.transData`, le defaut de `ax.text()`) : les captions/indices d'usage
    ("Astuce : cliquez une boite Z...", légende de repli "Schema non
    disponible") sont ancres en fraction d'AXE ou de FIGURE (`transAxes`/
    `transFigure`), donc a une position qui depend elle-meme de la boite des
    axes courante -- les inclure ferait DIVERGER la recherche de point fixe
    ci-dessous (leur "equivalent donnees" change a chaque iteration, dans le
    meme sens que l'ajustement qui vient de les deplacer). `_exporter_figure`
    les masque explicitement pour l'export (ce ne sont que des indices
    d'usage de l'app, hors-propos dans un PNG statique).

    @param fig Figure matplotlib d'ilot (un seul axe, cf. tous les `_make_*fig`).
    @return (x0, x1, y0, y1) en coordonnees data, ou None si aucun axe/contenu.
    """
    renderer = obtenir_renderer(fig)
    x0 = y0 = math.inf
    x1 = y1 = -math.inf
    for ax in fig.axes:
        dl = ax.dataLim
        if math.isfinite(dl.x0) and math.isfinite(dl.x1) and (dl.width > 0 or dl.height > 0):
            x0, x1 = min(x0, dl.x0), max(x1, dl.x1)
            y0, y1 = min(y0, dl.y0), max(y1, dl.y1)
        inv = ax.transData.inverted()
        for t in ax.texts:
            if t.get_transform() is not ax.transData:
                continue
            if not (t.get_visible() and t.get_text().strip()):
                continue
            bbox = t.get_window_extent(renderer)
            dx0, dy0 = inv.transform((bbox.x0, bbox.y0))
            dx1, dy1 = inv.transform((bbox.x1, bbox.y1))
            x0, x1 = min(x0, dx0, dx1), max(x1, dx0, dx1)
            y0, y1 = min(y0, dy0, dy1), max(y1, dy0, dy1)
    if not math.isfinite(x0):
        return None
    return x0, x1, y0, y1


def _masquer_textes_hors_donnees(fig):
    """@brief Masque temporairement les Text qui ne sont PAS ancres en
    coordonnees data (`fig.texts` + `ax.texts` en `transAxes`/`transFigure` :
    captions/indices d'usage de l'app, cf. `_bbox_contenu`) pour l'export PNG.

    `bbox_inches="tight"` engloberait sinon leur position fixe (coin de l'axe
    ou de la figure) dans le cadrage final, quel que soit le xlim/ylim pose --
    hors-propos dans un export statique et potentiellement tres excentre une
    fois le schema recadre sur son contenu reel.

    @param fig Figure matplotlib d'ilot.
    @return list Les Text masques (a rendre visible via leur `set_visible(True)`).
    """
    masques = []
    for t in fig.texts:
        if t.get_visible():
            masques.append(t)
    for ax in fig.axes:
        for t in ax.texts:
            if t.get_visible() and t.get_transform() is not ax.transData:
                masques.append(t)
    for t in masques:
        t.set_visible(False)
    return masques


_EXPORT_MAX_ITER = 8
_EXPORT_TOL = 1e-6


def _exporter_figure(fig, path):
    """@brief Sauvegarde `fig` en PNG/SVG cadre sur son CONTENU reel (marge
    uniforme), pas sur les limites d'axe affichees a l'ecran (volontairement
    asymetriques, cf. `_bbox_contenu`).

    Isolee de `_export` (qui ne fait plus que la boite de dialogue Tk) pour
    rester testable sans dependance a `tkinter.filedialog`.

    Point fixe itere (meme raison que `gui.schema_labels._reetendre_axes`) :
    la taille d'un `Text` est fixee en POINTS, pas en unites de donnees --
    resserrer xlim/ylim change l'echelle pixels/donnee de l'axe, donc la
    largeur EN DONNEES occupee par ce meme texte. Une seule passe peut donc
    laisser un residu asymetrique (le texte le plus proche d'un bord grossit
    ou retrecit en donnees differemment d'un bord a l'autre) ; on reboucle
    jusqu'a stabilisation des limites (bornee, `_EXPORT_MAX_ITER`).

    L'AFFICHAGE A L'ECRAN N'EST PAS MODIFIE : les limites d'axe et la
    visibilite des textes de figure sont restaurees dans un `finally`, avant
    le retour de la fonction.

    @param fig Figure matplotlib a exporter.
    @param path Chemin de destination (.png ou .svg).
    @return None
    """
    ax = fig.axes[0] if fig.axes else None
    limites_orig = (ax.get_xlim(), ax.get_ylim()) if ax is not None else None
    textes_masques = []
    if ax is not None:
        textes_masques = _masquer_textes_hors_donnees(fig)
        for _ in range(_EXPORT_MAX_ITER):
            bbox = _bbox_contenu(fig)
            if bbox is None:
                break
            x0, x1, y0, y1 = bbox
            nx0, nx1 = x0 - _EXPORT_MARGE_DATA, x1 + _EXPORT_MARGE_DATA
            ny0, ny1 = y0 - _EXPORT_MARGE_DATA, y1 + _EXPORT_MARGE_DATA
            cx0, cx1 = ax.get_xlim()
            cy0, cy1 = ax.get_ylim()
            ax.set_xlim(nx0, nx1)
            ax.set_ylim(ny0, ny1)
            ax.apply_aspect()
            echelle = max(abs(nx1 - nx0), abs(ny1 - ny0), 1e-9)
            if (abs(nx0 - cx0) < _EXPORT_TOL * echelle and abs(nx1 - cx1) < _EXPORT_TOL * echelle
                    and abs(ny0 - cy0) < _EXPORT_TOL * echelle and abs(ny1 - cy1) < _EXPORT_TOL * echelle):
                break
    try:
        fig.savefig(path, dpi=150, bbox_inches="tight",
                    facecolor=SCH_BG, edgecolor="none")
    finally:
        for t in textes_masques:
            t.set_visible(True)
        if limites_orig is not None:
            ax.set_xlim(limites_orig[0])
            ax.set_ylim(limites_orig[1])
            ax.apply_aspect()


def _export(fig, name, parent):
    """@brief Exporte la figure en PNG/SVG via une boîte de dialogue.

    @param fig Figure matplotlib à exporter.
    @param name Nom du circuit (titre par défaut).
    @param parent Fenêtre parente de la boîte de dialogue.
    @return None
    """
    from tkinter import filedialog
    path = filedialog.asksaveasfilename(
        parent=parent, defaultextension=".png",
        filetypes=[("PNG", "*.png"), ("SVG", "*.svg")],
        title="Exporter le schéma",
    )
    if path:
        _exporter_figure(fig, path)


# ── Label helpers ─────────────────────────────────────────────────────────────

def _lbl(ref, comp_info):
    """@brief Libellé d'un composant : « ref\\nvaleur » ou « ref » si pas de valeur.

    @param ref Référence du composant.
    @param comp_info Dict des infos composants.
    @return str Libellé prêt à afficher.
    """
    val = comp_info.get(ref, {}).get("value", "")
    return f"{ref}\n{val}" if val else ref


def _z_label(prefix, zinfo, comp_info):
    """@brief Étiquette d'une boîte Z : « Zin / composition [= valeur si 1 composant] ».

    Pour une impédance d'un seul composant, on affiche directement sa valeur
    formatée (« Zf / R4 = 22 kΩ »). Pour un composite, on garde la composition
    symbolique (« Zin / R1+(C1//R2) ») — le détail chiffré s'obtient au clic.

    @param prefix « Zin » ou « Zf ».
    @param zinfo Dict {'refs', 'composition', ...} de l'impédance.
    @param comp_info Dict {ref → {type, value}}.
    @return str Étiquette multi-lignes.
    """
    from circuit_analyzer.impedance import formater_expr, formater_valeur
    compo = formater_expr(zinfo["composition"])
    refs = zinfo.get("refs", [])
    if len(refs) == 1:
        info = comp_info.get(refs[0], {})
        val = formater_valeur(info.get("value", ""), info.get("type", "R"))
        if val:
            # Évite « Rb / Rb = 10 kΩ » quand la ref porte déjà le nom du rôle.
            if compo == prefix:
                return f"{prefix} = {val}"
            return f"{prefix}\n{compo} = {val}"
    return f"{prefix}\n{compo}"


def _ref(result, comp_info, typ):
    """@brief Première référence d'un type donné dans le circuit.

    @param result Match du circuit détecté.
    @param comp_info Dict des infos composants.
    @param typ Type recherché ('R', 'C', 'Q'…).
    @return str Référence trouvée, sinon le premier composant ou '?'.
    """
    for r in result["components"]:
        if comp_info.get(r, {}).get("type") == typ:
            return r
    return result["components"][0] if result["components"] else "?"

def _refs(result, comp_info, typ):
    """@brief Toutes les références d'un type donné dans le circuit.

    @param result Match du circuit détecté.
    @param comp_info Dict des infos composants.
    @param typ Type recherché.
    @return list[str] Références de ce type.
    """
    return [r for r in result["components"]
            if comp_info.get(r, {}).get("type") == typ]

def _ref_on_net(refs, comp_info, net, fallback=None):
    """@brief Première référence (parmi refs) dont une broche touche un net donné.

    @param refs Références candidates.
    @param comp_info Dict des infos composants.
    @param net Net recherché.
    @param fallback Valeur retournée si aucune correspondance.
    @return str|None Référence trouvée, sinon fallback.
    """
    if not net:
        return fallback
    for ref in refs:
        pins = comp_info.get(ref, {}).get("pins", {})
        if net in pins.values():
            return ref
    return fallback


# ── Drawing functions ─────────────────────────────────────────────────────────

def _symbole_diode(ref, ci):
    """@brief elm.LED coloré si la D est identifiée LED, sinon elm.Diode.

    @param ref Référence du composant D (peut être None/absente de `ci`).
    @param ci Dict des infos composants (ref -> {type, value, pins}).
    @return Élément schemdraw non orienté (à chaîner avec .right()/.up()...).
    """
    from circuit_analyzer.catalogue import identifier
    info = ci.get(ref, {}) or {}
    entree = identifier("D", info.get("value", ""))
    if entree and entree.get("symbole") == "led":
        return elm.LED().color(entree["couleur"])
    return elm.Diode()


def _draw_impedance(d, result, ci):
    """@brief Dessine une « Impédance Z » : boîte Z entre ses deux bornes.

    Le libellé est la composition (ex. « (R1+R2)//C1 »), sinon la liste des
    composants. Les nets sont annotés à gauche et à droite. Passe par
    `_z_box` (point d'entrée unique de la bascule Z/détaillé) au lieu de
    dessiner la boîte à la main : cliquable en vue Z, réseau réel déplié en
    vue détaillée.

    Note : cette boîte étant souvent le SEUL contenu du schéma (« Impédance Z »
    isolée), rien d'autre n'étend la vue jusqu'au label placé au-dessus par
    `_z_label_anchor`. C'est `_make_fig` qui cadre explicitement les axes sur
    `d.get_bbox()` (texte des étiquettes inclus) pour que ce label reste visible
    — sans ce cadrage, l'autoscale par défaut de Matplotlib (basé sur les seuls
    Line2D/Patch, jamais les Text) le laisse hors cadre.
    """
    nets = [n for n in result.get("nodes", []) if n]
    gauche = nets[0] if nets else ""
    droite = nets[1] if len(nets) > 1 else ""
    compo = result.get("composition") or " // ".join(result.get("components", []))
    bloc = {"refs": result.get("components", []), "composition": compo}
    p0, p1, p2, p3 = (0.0, 0.0), (0.6, 0.0), (2.6, 0.0), (3.2, 0.0)
    d.add(elm.Dot().at(p0).label(gauche, loc="left"))
    d.add(elm.Line().at(p0).to(p1))
    _z_box(d, p1, p2, "Z", bloc, ci)
    d.add(elm.Line().at(p2).to(p3))
    d.add(elm.Dot().at(p3).label(droite, loc="right"))


def _draw_half_wave(d, result, ci):
    """@brief Dessine le schéma « Redresseur simple alternance »."""
    diode = _ref(result, ci, "D"); r = _ref(result, ci, "R")
    d += _symbole_diode(diode, ci).right().label(_lbl(diode, ci), loc="top")
    d.push()
    d += elm.Resistor().down().label(_lbl(r, ci), loc="right")
    d += elm.Ground()
    d.pop()
    d += elm.Line().right(1.5).label("DC", loc="right")


def _draw_peak_detector(d, result, ci):
    """@brief Dessine le schéma « Détecteur de crête »."""
    diode = _ref(result, ci, "D"); c = _ref(result, ci, "C")
    d += _symbole_diode(diode, ci).right().label(_lbl(diode, ci), loc="top")
    d.push()
    d += elm.Capacitor().down().label(_lbl(c, ci), loc="right")
    d += elm.Ground()
    d.pop()
    d += elm.Line().right(1.5).label("PEAK", loc="right")


def _draw_bridge_rectifier(d, result, ci):
    """@brief Dessine le schéma « Pont redresseur (Graetz) ».

    Disposition en deux colonnes, toutes les diodes pointant vers le haut :
      colonne gauche  : DC- → D3 → AC1 → D1 → DC+
      colonne droite  : DC- → D4 → AC2 → D2 → DC+
    Les rails horizontaux relient le haut (DC+) et le bas (DC-).
    """
    ds = _refs(result, ci, "D")
    while len(ds) < 4:
        ds.append("D?")

    COL = 4.0   # horizontal distance between the two columns

    # ── Left column ───────────────────────────────────────────────
    d.add(elm.Dot().at((0, 0)).label("DC−", loc="left"))
    # Diode labels omitted — node labels (AC1/DC+/DC−) are sufficient;
    # component refs are shown in the header chip badges.
    d.add(_symbole_diode(ds[2], ci).up().at((0, 0)))   # D3
    d.add(elm.Dot().label("AC1", loc="left"))
    d.add(_symbole_diode(ds[0], ci).up())              # D1
    dc_plus_y = d.here[1]
    d.add(elm.Dot().label("DC+", loc="left"))

    # ── Right column ──────────────────────────────────────────────
    d.add(elm.Dot().at((COL, 0)).label("DC−", loc="right"))
    d.add(_symbole_diode(ds[3], ci).up().at((COL, 0)))  # D4
    d.add(elm.Dot().label("AC2", loc="right"))
    d.add(_symbole_diode(ds[1], ci).up())               # D2
    d.add(elm.Dot().label("DC+", loc="right"))

    # ── Connecting rails ──────────────────────────────────────────
    d.add(elm.Line().at((0, 0)).right(COL))                       # DC- rail
    d.add(elm.Line().at((0, dc_plus_y)).right(COL))               # DC+ rail


def _draw_flyback(d, result, ci):
    """@brief Dessine le schéma « Diode de roue libre »."""
    diode = result["components"][0]
    d += elm.Line().right(0.5).label("SW", loc="start")
    d += _symbole_diode(diode, ci).right().label(_lbl(diode, ci), loc="top")
    d += elm.Line().right(0.5).label("VCC", loc="end")


def _draw_esd(d, result, ci):
    """@brief Dessine le schéma « Diode de protection ESD »."""
    diode = result["components"][0]
    # Vertical diodes are broken in schemdraw 0.22 — L-shaped layout with horizontal diode
    # SIG ──●──[D1→]──┐
    #                  |
    #                 GND
    d.add(elm.Line().right(0.5).label("SIG", loc="start"))
    sig_pt = d.here
    d.add(elm.Dot().at(sig_pt))
    d.add(_symbole_diode(diode, ci).right().label(_lbl(diode, ci), loc="top"))
    d.add(elm.Line().down(1.5))
    d.add(elm.Ground())
    # Net SIG (borne non-masse de la diode) : ancre pour les Impédances Z
    # restantes de l'îlot (ex. R série de limitation) -- sinon un satellite
    # connecté à SIG n'est jamais dessiné (cf. `_dessiner_impedances_locales`).
    sig_net = next((n for n in result.get("nodes", ()) if n and not is_ground_net(n)),
                    None)
    return {"nets": {sig_net: sig_pt} if sig_net else {}, "absorbed_refs": {diode}}


# ── AOP patterns ─────────────────────────────────────────────────────────────

def _draw_inverting_amp(d, result, ci):
    """@brief Dessine « Amplificateur inverseur (AOP) » : AOP + Zin/Zf en blocs Z cliquables.

    Repli : si le match ne porte pas d'impédances structurées, dessin résistances.
    """
    imp = result.get("impedances")
    if not imp:
        rs = _refs(result, ci, "R")
        rf = rs[0] if rs else "Rf"
        rin = rs[1] if len(rs) > 1 else "Rin"
        op = d.add(elm.Opamp().anchor("in1").at((4.5, 0)))
        _enregistrer_position(d, _ref(result, ci, "U"), (4.5, 0))
        d.add(elm.Resistor().at(op.in1).left().label(_lbl(rin, ci), loc="top"))
        d.add(elm.Dot().label("IN", loc="left"))
        d.add(elm.Line().at(op.in2).left(1))
        d.add(elm.Ground())
        above = (op.in1[0], op.in1[1] + 1.5)
        d.add(elm.Line().at(op.in1).up(1.5))
        d.add(elm.Resistor().at(above).right().tox(op.out[0]).label(_lbl(rf, ci), loc="top"))
        d.add(elm.Line().toy(op.out[1]))
        d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))
        return

    _draw_aop_inverseur_zin_zf(d, imp, ci, ref=_ref(result, ci, "U"))


_Z_LABEL_CLEAR = 0.95
_SUM_INPUT_SPACING = 2.2
_SUM_INPUT_LABEL_DX = 0.25
_SUM_INPUT_LABEL_DY = 0.45


def _z_label_anchor(p1, p2, label_loc="top"):
    """@brief Positionne un label Z hors du corps du composant.

    Les labels Z sont souvent sur deux lignes ; le label schemdraw par defaut est
    trop proche et retombe sur le symbole. @return dict pos/ha/va pour elm.Label.
    """
    x0, x1 = sorted((p1[0], p2[0]))
    y0, y1 = sorted((p1[1], p2[1]))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if label_loc == "bottom":
        return {"pos": (cx, y0 - _Z_LABEL_CLEAR), "ha": "center", "va": "top"}
    if label_loc == "left":
        return {"pos": (x0 - _Z_LABEL_CLEAR, cy), "ha": "right", "va": "center"}
    if label_loc == "right":
        return {"pos": (x1 + _Z_LABEL_CLEAR, cy), "ha": "left", "va": "center"}
    return {"pos": (cx, y1 + _Z_LABEL_CLEAR), "ha": "center", "va": "bottom"}


def _sum_input_label_anchor(dot_pt):
    """@brief Ancre un label INx hors de la piste d'entree du sommateur."""
    return {
        "pos": (dot_pt[0] - _SUM_INPUT_LABEL_DX, dot_pt[1] + _SUM_INPUT_LABEL_DY),
        "ha": "right",
        "va": "bottom",
    }


def _agencement_entre(p1, p2, arbre):
    """@brief Place le réseau R/L/C de `arbre` entre p1 et p2 (coordonnées globales).

    Réutilise impedance_schematic.agencer(arbre) (mise en page locale ; borne
    gauche (0, dims.y_borne), borne droite (dims.largeur, dims.y_borne)) puis
    applique translation p1 + rotation (angle p1->p2) + échelle uniforme
    (dist(p1,p2) / dims.largeur), pour amener les deux bornes locales sur p1/p2.
    Le perpendiculaire local (écart à l'axe des bornes) utilise la même échelle
    avec un minimum lisible pour ne pas écraser les branches parallèles courtes.

    @param p1, p2 Bornes globales (x, y) entre lesquelles agencer le réseau.
    @param arbre Arbre série/parallèle (cf. circuit_analyzer.impedance.arbre_expr).
    @return (symboles, fils) en coordonnées globales :
        symboles = [(ref, (xa,ya), (xb,yb))] ; fils = [((xa,ya),(xb,yb))].
    """
    from gui import impedance_schematic
    symboles_loc, fils_loc, dims = impedance_schematic.agencer(arbre)
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    dist = math.hypot(dx, dy)
    echelle = dist / dims.largeur if dims.largeur else 0.0
    # Les couplages courts compriment fortement les branches paralleles si l'on
    # applique l'echelle uniforme aux deux axes. Garder un minimum perpendiculaire
    # preserve la lisibilite des labels sans changer les bornes p1/p2.
    echelle_perp = max(echelle, _Z_DETAIL_PERP_MIN_SCALE)
    theta = math.atan2(dy, dx)
    cos_t, sin_t = math.cos(theta), math.sin(theta)

    def _vers_global(lx, ly):
        along = lx * echelle
        perp = (ly - dims.y_borne) * echelle_perp
        return (p1[0] + along * cos_t - perp * sin_t,
                p1[1] + along * sin_t + perp * cos_t)

    symboles = [(ref, _vers_global(x1, y), _vers_global(x2, y))
                for ref, x1, x2, y in symboles_loc]
    fils = [(_vers_global(xa, ya), _vers_global(xb, yb))
            for (xa, ya), (xb, yb) in fils_loc]
    return symboles, fils


def _label_loc_side(label_loc, nx, ny):
    """@brief Signe du cote de decalage correspondant a un label_loc."""
    vecteurs = {
        "top": (0.0, 1.0),
        "bottom": (0.0, -1.0),
        "left": (-1.0, 0.0),
        "right": (1.0, 0.0),
    }
    vx, vy = vecteurs.get(label_loc, vecteurs["top"])
    return 1.0 if vx * nx + vy * ny >= 0 else -1.0


def _agencement_compact_decale(p1, p2, arbre, label_loc="top"):
    """@brief Agencement compact decale d'un reseau trop dense.

    Quand le segment principal est trop court, le depliage lineaire ecrase les
    branches paralleles. Ce placement garde les bornes p1/p2, mais pousse tout
    le reseau d'un seul cote avec deux petits fils de liaison orthogonaux :
    l'utilisateur voit toujours les vrais symboles R/L/C, sans boite Z ni
    chevauchement des deux cotes du fil porteur.
    """
    from gui import impedance_schematic

    symboles_loc, fils_loc, dims = impedance_schematic.agencer(arbre)
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    dist = math.hypot(dx, dy)
    echelle = dist / dims.largeur if dims.largeur else 0.0
    dist_norm = dist or 1.0
    ux, uy = dx / dist_norm, dy / dist_norm
    nx, ny = -uy, ux
    cote = _label_loc_side(label_loc, nx, ny)
    local_ys = [dims.y_borne]
    local_ys.extend(y for _ref, _x1, _x2, y in symboles_loc)
    for (xa, ya), (xb, yb) in fils_loc:
        local_ys.extend((ya, yb))
    rels = [y - dims.y_borne for y in local_ys]
    min_rel, max_rel = min(rels), max(rels)
    echelle_perp = max(echelle, _Z_DETAIL_COMPACT_PERP_SCALE)

    def _rang(rel):
        if cote >= 0:
            return rel - min_rel
        return max_rel - rel

    def _vers_global(lx, ly):
        along = lx * echelle
        rel = ly - dims.y_borne
        perp = cote * (_Z_DETAIL_COMPACT_SIDE_CLEAR + _rang(rel) * echelle_perp)
        return (p1[0] + along * ux + perp * nx,
                p1[1] + along * uy + perp * ny)

    symboles = [(ref, _vers_global(x1, y), _vers_global(x2, y))
                for ref, x1, x2, y in symboles_loc]
    fils = [(_vers_global(xa, ya), _vers_global(xb, yb))
            for (xa, ya), (xb, yb) in fils_loc]
    entree = _vers_global(0.0, dims.y_borne)
    sortie = _vers_global(dims.largeur, dims.y_borne)
    fils.extend([(p1, entree), (sortie, p2)])
    return symboles, fils, entree, sortie


def _amorce_centree(pa, pb, fraction=0.65, min_len=_Z_DETAIL_SYMBOL_MIN_LEN):
    """@brief Rétrécit (pa,pb) sur ~`fraction` du segment, CENTRÉ.

    schemdraw ne compresse pas les motifs périodiques (zigzag Resistor, spirale
    Inductor2) en dessous de leur taille naturelle (~1 unité) : un symbole
    dessiné sur un segment plus court DÉBORDE de ses propres bornes (audit
    fenêtre F4, ex. R1 d'un stub compact). Sur les boucles parallèles, un
    symbole qui occupe 100 % du segment vient aussi buter visuellement sur les
    coins des rails (F3). Ce helper renvoie les nouvelles bornes du symbole et
    les segments de fil d'amorce à dessiner de part et d'autre (liste vide si
    le segment est déjà trop court pour dégager de la place).

    @return (sa, sb, fils_amorce) ; fils_amorce = [(pa,sa), (sb,pb)] ou [].
    """
    ax, ay = pa
    bx, by = pb
    dist = math.hypot(bx - ax, by - ay)
    if dist < 1e-9:
        return pa, pb, []
    cible = min(dist, max(dist * fraction, min(dist, min_len)))
    marge = (dist - cible) / 2
    if marge < 1e-6:
        return pa, pb, []
    ux, uy = (bx - ax) / dist, (by - ay) / dist
    sa = (ax + ux * marge, ay + uy * marge)
    sb = (bx - ux * marge, by - uy * marge)
    return sa, sb, [(pa, sa), (sb, pb)]


def _z_reseau(d, p1, p2, bloc, ci, label_loc="top", wire_color=_WIRE) -> bool:
    """@brief Dessine le réseau R/L/C réel de `bloc` entre p1 et p2 (vue détaillée).

    Déplie la composition (`bloc["composition"]`) en son arbre série/parallèle
    et dessine chaque composant avec son symbole/couleur réels (au lieu de la
    boîte Z générique). Si la composition n'est pas dépliable (pont Y-Δ),
    ne dessine rien : l'appelant garde alors la boîte Z (cf. _z_box).

    @param d Dessin schemdraw.
    @param p1, p2 Extrémités globales du bloc Z remplacé.
    @param bloc Bloc d'impédance {'refs','composition',...}.
    @param ci Dict {ref → {type, value}} pour l'étiquette de chaque composant.
    @param wire_color Couleur des fils de jonction internes (rungs du réseau
        déplié) — `_WIRE` par défaut (chemin principal/couplage de chaîne),
        `_BUS` quand ce réseau habille un stub satellite (cf. `_dessiner_z_locale`).
        Les symboles gardent leur propre couleur sémantique, non affectée.
    @return bool True si le réseau a été dessiné, False sinon.
    """
    from circuit_analyzer import impedance
    from gui import impedance_schematic
    arbre = impedance.arbre_expr(bloc["composition"])
    if arbre is None:
        return False
    _sym_loc, _fils_loc, dims = impedance_schematic.agencer(arbre)
    dist_segment = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    compact = bool(dims.largeur and dist_segment / dims.largeur < _Z_DETAIL_COMPACT_LABEL_SCALE)
    decale = compact and len(_sym_loc) > _Z_DETAIL_COMPACT_INLINE_MAX
    if decale:
        symboles, fils, label_p1, label_p2 = _agencement_compact_decale(
            p1, p2, arbre, label_loc)
    else:
        symboles, fils = _agencement_entre(p1, p2, arbre)
        label_p1, label_p2 = p1, p2
    dx, dy = label_p2[0] - label_p1[0], label_p2[1] - label_p1[1]
    dist = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / dist, dx / dist
    for ref, pa, pb in symboles:
        info = ci.get(ref, {})
        typ = info.get("type", "")
        cls, coul, ref_txt, valeur = impedance_schematic.style_symbole(
            typ, info.get("value", ""), ref)
        if compact:
            # Reseau compact : seule la ref est lisible a cette echelle
            # (comportement inchange, cf. audits fenetre).
            valeur = ""
        mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
        _enregistrer_position(d, ref, (mx, my))
        sdx, sdy = pb[0] - pa[0], pb[1] - pa[1]
        # Symbole recentre sur ~65% du segment (mini absolu pour les motifs
        # periodiques R/L) + fils d'amorce de part et d'autre : evite le
        # debordement de bornes (F4) et le symbole rail-a-rail dans les
        # boucles paralleles (F3). mx/my restent le milieu du segment
        # D'ORIGINE (identique a celui du symbole recentre) pour la logique
        # de placement des labels ci-dessous.
        sa, sb, amorces = _amorce_centree(pa, pb)
        for fa, fb in amorces:
            d.add(elm.Line().at(fa).to(fb).color(coul))
        pa, pb = sa, sb
        if decale and abs(sdy) > abs(sdx):
            d.add(cls().at(pa).to(pb).color(coul))
            # Le label va AU-DESSUS du rail le plus proche (jamais dans
            # l'entrefer symbole<->rail, souvent trop etroit pour un texte
            # lisible - audit fenetre F2). On choisit le rail dont la branche
            # est la plus proche : une branche plus courte que ses voisines
            # (ecart bas > ecart haut) bascule son etiquette SOUS le rail bas.
            rail_haut = max(label_p1[1], label_p2[1])
            rail_bas = min(label_p1[1], label_p2[1])
            ecart_haut = rail_haut - max(pa[1], pb[1])
            ecart_bas = min(pa[1], pb[1]) - rail_bas
            if ecart_haut <= ecart_bas:
                ly = rail_haut + _Z_DETAIL_COMPACT_RAIL_CLEAR
                valign = "bottom"
                pas = _Z_DETAIL_LABEL_CLEAR
            else:
                ly = rail_bas - _Z_DETAIL_COMPACT_RAIL_CLEAR
                valign = "top"
                pas = -_Z_DETAIL_LABEL_CLEAR
            d.add(elm.Label().at((mx, ly)).label(
                ref_txt, halign="center", valign=valign,
                fontsize=_Z_DETAIL_LABEL_FONTSIZE, color=coul))
            # Regle ref/valeur (design section 1) adaptee a ce reseau decale
            # (audit F2) : la valeur est empilee plus loin que la ref, DU
            # MEME cote (celui deja choisi pour degager le rail) plutot que
            # du cote oppose -- le cote oppose est le territoire du rail/du
            # reseau, precisement ce que la ref evite deja. Ecart assume et
            # documente (cf. design, "Ecart au brief assumé et documenté").
            if valeur:
                d.add(elm.Label().at((mx, ly + pas)).label(
                    valeur, halign="center", valign=valign,
                    fontsize=_Z_DETAIL_LABEL_FONTSIZE, color=coul))
            continue
        signed_perp = ((mx - label_p1[0]) * (-dy) + (my - label_p1[1]) * dx) / dist
        if abs(signed_perp) < _Z_DETAIL_LABEL_AXIS_EPS:
            # Axe quasi nul (reseau serie, une seule rangee) : le label reste
            # attache au symbole (comme avant) ; "top" pousse le label du cote
            # oppose a l'entree du reseau, la ou un satellite (Rb, ...) est
            # deja etiquete juste apres le point p1 (cf.
            # ilot_reel_ce_suiveur_sortie_rlc). Regle ref/valeur : la valeur
            # va cote oppose ("bottom") -- schemdraw tourne ses ancres avec
            # l'element, donc un symbole vertical bascule automatiquement en
            # gauche/droite, sans logique dediee ici.
            el = cls().at(pa).to(pb).color(coul).label(
                ref_txt, loc="top", fontsize=_Z_DETAIL_LABEL_FONTSIZE, color=coul)
            if valeur:
                el = el.label(valeur, loc="bottom",
                              fontsize=_Z_DETAIL_LABEL_FONTSIZE, color=coul)
            d.add(el)
            continue
        d.add(cls().at(pa).to(pb).color(coul))
        # Branche parallele hors axe : pousser le label VERS l'axe (interieur
        # du reseau) plutot que vers l'exterieur. L'exterieur est le
        # territoire d'un voisin externe (satellite Rb/Re du montage appelant)
        # que _z_reseau ne voit pas, alors que l'espace ENTRE les branches est
        # garanti libre (c'est l'ecart perpendiculaire qui les separe). Un
        # placement manuel (plutot que le loc="top"/"bottom" de schemdraw)
        # evite aussi l'ambiguite de rotation : pour un segment vertical,
        # "top"/"bottom" se traduisent en gauche/droite selon le sens de
        # tracage de l'element, ce qui inversait le cote attendu.
        sign = -1.0 if signed_perp > 0 else 1.0
        # Poussee verticale (branche horizontale, ex. R5//L1 d'un couplage) :
        # il faut degager l'AMPLITUDE du zigzag/de la spirale (~0.25 unite),
        # plus large que la demi-largeur etroite qu'une poussee horizontale
        # doit degager (branche verticale) -> deux degagements distincts,
        # sinon le petit degagement laisse le label chevaucher les crêtes
        # (audit fenetre F1, ex. R5 de ilot_reel_2ce_bias_rlc).
        clear = _Z_DETAIL_LABEL_CLEAR if abs(nx) >= abs(ny) else _Z_DETAIL_LABEL_CLEAR_VERT
        lx = mx + sign * nx * clear
        ly = my + sign * ny * clear
        if abs(nx) >= abs(ny):
            ha = "left" if sign * nx > 0 else "right"
            va = "center"
        else:
            ha = "center"
            va = "bottom" if sign * ny > 0 else "top"
        if not valeur:
            d.add(elm.Label().at((lx, ly)).label(
                ref_txt, halign=ha, valign=va,
                fontsize=_Z_DETAIL_LABEL_FONTSIZE, color=coul))
            continue
        # Regle ref/valeur (design section 1), re-adaptee a l'audit ilots
        # 2026-07-13 : ref et valeur COTE A COTE le long de la branche, au
        # MEME degagement perpendiculaire. L'empilement en profondeur (valeur
        # un cran plus loin vers l'axe) faisait converger les labels des DEUX
        # branches d'un parallele non compact au meme x median : colonne
        # fusionnee illisible "R2 / 10 kΩ / 10 nF / C1" (Zf des inverseurs),
        # voire chevauchement reel avec un satellite voisin (pid_controller).
        # L'espace LE LONG de la branche appartient a la branche elle-meme :
        # y etaler ses deux textes ne mord sur aucun voisin.
        dist_b = math.hypot(sdx, sdy) or 1.0
        ux, uy = sdx / dist_b, sdy / dist_b
        shift = min(0.8, 0.28 * dist_b)
        d.add(elm.Label().at((lx - shift * ux, ly - shift * uy)).label(
            ref_txt, halign=ha, valign=va,
            fontsize=_Z_DETAIL_LABEL_FONTSIZE, color=coul))
        d.add(elm.Label().at((lx + shift * ux, ly + shift * uy)).label(
            valeur, halign=ha, valign=va,
            fontsize=_Z_DETAIL_LABEL_FONTSIZE, color=coul))
    for pa, pb in fils:
        d.add(elm.Line().at(pa).to(pb).color(wire_color))
    return True


def _z_box(d, p1, p2, name, bloc, ci, label_loc="top", wire_color=_WIRE):
    """@brief Dessine une boîte Z cliquable (ResistorIEC bleue) de p1 à p2 et
    enregistre sa hitbox sur d._z_hitboxes.

    En vue détaillée (`d._mode_detaille`), dessine à la place le réseau R/L/C
    réel : un bloc à une seule ref est tracé directement avec son symbole/sa
    couleur/son étiquette (comme `_z_reseau`) ; un bloc composite passe par
    `_z_reseau`. Si aucun des deux n'est possible (pont non dépliable), la
    boîte Z classique reste le repli. Dans tous les cas, `_enregistrer_hitbox`
    est appelé mais devient un no-op en vue détaillée : aucune zone cliquable.

    @param d Dessin schemdraw.
    @param p1/p2 Extrémités de la boîte (x, y).
    @param name Préfixe d'étiquette (« Zin », « Zf »…).
    @param bloc Bloc d'impédance {'refs','composition','nodes'}.
    @param ci Dict {ref → {type, value}} pour l'étiquette.
    @param label_loc Position de l'étiquette schemdraw.
    @param wire_color Couleur des fils de jonction internes du réseau déplié
        (vue détaillée uniquement) — transmis tel quel à `_z_reseau`. Sans
        effet sur la boîte Z elle-même (toujours `_Z_EDGE`, cliquable) ni sur
        les symboles réels (couleur sémantique R/L/C inchangée).
    @return None
    """
    # Position de repli pour CHAQUE ref du bloc (centre de la boite) : couvre
    # les candidats ('R1','Z1') meme quand ni hitbox (vue detaillee : no-op,
    # cf. `_enregistrer_hitbox`) ni texte de ref n'est present sur le dessin.
    # Ecrasee plus bas par une position plus precise (symbole reel deplie)
    # quand `_z_reseau`/le repli 1-ref l'obtient.
    centre_boite = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
    for r in bloc.get("refs", []) or ():
        _enregistrer_position(d, r, centre_boite)

    dessine = False
    if getattr(d, "_mode_detaille", False):
        refs = bloc.get("refs", [])
        if len(refs) == 1:
            from circuit_analyzer import impedance
            from gui import impedance_schematic
            ref = refs[0]
            info = ci.get(ref, {})
            typ = info.get("type", "")
            cls = impedance_schematic._SYMB.get(typ, elm.ResistorIEC)
            coul = _COMP_COLORS.get(typ, _WIRE)
            vfmt = impedance.formater_valeur(info.get("value", ""), typ)
            label = f"{ref}\n{vfmt}" if vfmt else ref
            # Label place via _z_label_anchor : honore le label_loc choisi par
            # le drawer appelant (audits fenetre), la ou le .label() schemdraw
            # tournait avec l'element -- sur une boite VERTICALE, le defaut
            # retombait a GAUCHE meme quand le caller demandait "right"
            # (audit ilots 2026-07-13, Zg du differentiel sur pid_controller).
            anc = _z_label_anchor(p1, p2, label_loc)
            d.add(cls().at(p1).to(p2).color(coul))
            d.add(elm.Label().at(anc["pos"]).label(
                label, halign=anc["ha"], valign=anc["va"],
                fontsize=9, color=coul))
            _enregistrer_position(d, ref, centre_boite)
            dessine = True
        elif _z_reseau(d, p1, p2, bloc, ci, label_loc=label_loc, wire_color=wire_color):
            dessine = True
    if not dessine:
        d.add(elm.ResistorIEC().at(p1).to(p2).color(_Z_EDGE).fill(_Z_FILL))
        label = _z_label_anchor(p1, p2, label_loc)
        # fontsize explicite (au lieu du 13/14 par defaut du Drawing) : une boite Z
        # posee pres d'un composant voisin (ex. Rc du montage emetteur commun)
        # voyait son etiquette (parfois 2 lignes) deborder sur le symbole voisin.
        d.add(elm.Label().at(label["pos"]).label(
            _z_label(name, bloc, ci),
            halign=label["ha"],
            valign=label["va"],
            fontsize=_Z_BOX_LABEL_FONTSIZE,
            color=_Z_EDGE,
        ))
    _enregistrer_hitbox(d, p1, p2, bloc["refs"], bloc["composition"])


def _enregistrer_hitbox(d, p1, p2, refs, composition, pad=0.5):
    """@brief Enregistre une zone cliquable (drill-down R/L/C) sur d._z_hitboxes.

    Permet de rendre n'importe quel symbole cliquable (boîte Z OU symbole réel
    comme un condensateur de liaison), pas seulement les ResistorIEC bleues.
    No-op en vue détaillée (`d._mode_detaille`) : plus aucune zone cliquable,
    les réfs/valeurs étant déjà visibles sur les composants réels.
    @param p1/p2 Extrémités du symbole. @param refs Composants bruts du dipôle.
    @param composition Expression symbolique pour le sous-schéma.
    """
    if getattr(d, "_mode_detaille", False):
        return
    hb = getattr(d, "_z_hitboxes", None)
    if hb is not None:
        hb.append((min(p1[0], p2[0]) - pad, max(p1[0], p2[0]) + pad,
                   min(p1[1], p2[1]) - pad, max(p1[1], p2[1]) + pad,
                   list(refs), composition))


def _enregistrer_position(d, ref, pos):
    """@brief Enregistre la position (x, y) DATA d'un composant sur
    `d._comp_positions`, au moment ou son symbole est effectivement pose.

    Contrepartie de `_enregistrer_hitbox` pour les composants qu'aucune
    hitbox Z ni aucun texte de ref ne rend cliquables autrement : les
    transistors/AOP (dont le titre du montage affiche un ROLE, jamais leur
    ref) et les satellites R/L/C dessines en symbole reel avec une etiquette
    de role (« Rb = 10 kΩ ») plutot que leur ref -- cf. `_r_simple`,
    `_charge_verticale`, `_z_box`, `_z_reseau`.

    No-op si `d` ne porte pas `_comp_positions` (meme idiome que
    `_enregistrer_hitbox`/`d._z_hitboxes` : les Drawings crees hors des
    fabriques `_make_*fig` n'ont pas ce dict) ou si `ref` est vide/None.

    @param d Dessin schemdraw (ou tout objet portant `_comp_positions`).
    @param ref Reference du composant (ex. "Q1"), ou None/"" (no-op).
    @param pos (x, y) en coordonnees data.
    """
    if not ref:
        return
    positions = getattr(d, "_comp_positions", None)
    if positions is not None:
        positions[ref] = (float(pos[0]), float(pos[1]))


def _draw_reseau_derive(d, info, ci):
    """@brief Dessine un reseau derive : rail haut -[Z serie]- prise -[Z shunt]- GND.

    @param d Dessin schemdraw. @param info Dict de _reseau_derive_ilot.
    @param ci Dict {ref -> {type, value, pins}}.
    @return dict (ancres ; vide ici).
    """
    p_top, p_prise, p_gnd = (0, 5), (0, 3), (0, 1)
    d.add(elm.Line().at(p_top).up(0.5).color(_WIRE))
    d.add(elm.Label().at((0, 5.8)).label(info["top"], color=_WIRE))
    _z_box(d, p_top, p_prise, "Z", info["serie"], ci, label_loc="left")
    d.add(elm.Dot().at(p_prise).color(_WIRE))
    d.add(elm.Line().at(p_prise).right(1.8).color(_WIRE))
    d.add(elm.Label().at((1.9, 3)).label(f"{info['prise']}  ->",
                                         halign="left", color=_WIRE))
    if info["shunt"]:
        _z_box(d, p_prise, p_gnd, "Z", info["shunt"], ci, label_loc="left")
        d.add(elm.Ground().at(p_gnd).color(_WIRE))
    else:
        d.add(elm.Ground().at(p_prise).color(_WIRE))
    return {}


def _draw_aop_inverseur_zin_zf(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT",
                               ref=None):
    """@brief Dessin commun des montages à topologie inverseuse : AOP + Zin/Zf cliquables.

    Partagé par l'ampli inverseur, l'intégrateur, le dérivateur (même structure :
    Zin sur IN-, Zf de IN- vers OUT, IN+ à la masse).

    @param imp Dict {'Zin': bloc, 'Zf': bloc} (cf. détecteurs).
    @param ci Dict {ref → {type, value}} pour étiquettes/valeurs.
    @param origin Position de l'AOP (pour chaîner plusieurs montages).
    @param in_label/out_label Libellés d'entrée/sortie ("" pour les masquer).
    @param ref Référence U du montage (registre de positions), ou None.
    @return dict {"in": (x,y), "out": (x,y)} : points de connexion du bloc.
    """
    zin, zf = imp["Zin"], imp["Zf"]
    op = d.add(elm.Opamp().right().anchor("in1").at(origin).color(_WIRE).fill(_OPAMP_FILL))
    _enregistrer_position(d, ref, origin)
    in1, out = op.in1, op.out

    # Nœud de sommation, déporté à GAUCHE du triangle : Zin y arrive, un court fil
    # le relie à IN-, et la contre-réaction en repart vers le haut.
    noeud = (in1[0] - 1.3, in1[1])
    d.add(elm.Line().at(noeud).to(in1).color(_WIRE))
    d.add(elm.Dot().at(noeud).color(_WIRE))

    # Zin : entrée -> nœud de sommation (boîte Z bleue, cliquable)
    zin_p1 = (noeud[0] - 3.0, noeud[1])
    _z_box(d, zin_p1, noeud, "Zin", zin, ci)
    d.add(elm.Line().at(zin_p1).left(0.7).color(_WIRE))
    in_pt = (zin_p1[0] - 0.7, zin_p1[1])
    d.add(elm.Dot().at(in_pt).color(_WIRE).label(in_label, loc="left", color=_WIRE))
    # IN+ à la masse
    d.add(elm.Line().at(op.in2).left(1.0).color(_WIRE))
    d.add(elm.Ground().color(_WIRE))
    # Zf : contre-réaction nœud -> OUT (riser à gauche, dans le vide, puis par le haut)
    above_y = in1[1] + 2.0
    if getattr(d, "_mode_detaille", False) and len(zf.get("refs") or []) > 1:
        # Réseau composite déplié : la branche basse d'un parallèle descend
        # ~1.2 sous l'axe et frôlait le sommet du triangle (audit ilots
        # 2026-07-13, Zf = R//C des inverseurs). On relève d'autant.
        above_y += 1.2
    d.add(elm.Line().at(noeud).up(above_y - noeud[1]).color(_WIRE))
    zf_p1, zf_p2 = (noeud[0], above_y), (out[0], above_y)
    _z_box(d, zf_p1, zf_p2, "Zf", zf, ci)
    d.add(elm.Line().at(zf_p2).toy(out[1]).color(_WIRE))
    out_pt = (out[0] + 1.0, out[1])
    d.add(elm.Line().at(out).to(out_pt).color(_WIRE).label(out_label, loc="right", color=_WIRE))

    return {"in": in_pt, "out": out_pt}


def _draw_aop_sommateur(d, imp, ci, origin=(5.0, 0), in_label="IN1", out_label="OUT",
                        ref=None):
    """@brief Dessine le sommateur : bus d'entrées Zin + Zf cliquables sur IN-.

    @param imp Dict {'Zf': bloc, 'Zin': [bloc, ...]} (cf. détecteur).
    @param ref Référence U du montage (registre de positions), ou None.
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    zf, zin = imp["Zf"], imp["Zin"]
    op = d.add(elm.Opamp().right().anchor("in1").at(origin).color(_WIRE).fill(_OPAMP_FILL))
    _enregistrer_position(d, ref, origin)
    inm, out = op.in1, op.out

    # IN+ à la masse
    d.add(elm.Line().at(op.in2).left(0.8).color(_WIRE))
    d.add(elm.Ground().color(_WIRE))

    node_x = inm[0] - 1.3
    d.add(elm.Line().at((node_x, inm[1])).to(inm).color(_WIRE))
    n = len(zin)
    spacing = _SUM_INPUT_SPACING
    top_y = inm[1] + (n - 1) * spacing
    d.add(elm.Line().at((node_x, inm[1])).toy(top_y).color(_WIRE))   # bus vertical
    d.add(elm.Dot().at((node_x, inm[1])).color(_WIRE))

    in_pts = []                            # une ancre par entrée (ordre des Zin)
    for i, bloc in enumerate(zin):
        y = inm[1] + i * spacing
        p1 = (node_x - 3.0, y)
        _z_box(d, p1, (node_x, y), f"Z{i+1}", bloc, ci)
        d.add(elm.Line().at(p1).left(0.5).color(_WIRE))
        label = in_label if i == 0 else f"IN{i+1}"
        dot_pt = (p1[0] - 0.5, y)
        dot = elm.Dot().at(dot_pt).color(_WIRE)
        if label:
            lab = _sum_input_label_anchor(dot_pt)
            d.add(elm.Label().at(lab["pos"]).label(
                label,
                halign=lab["ha"],
                valign=lab["va"],
                color=_WIRE,
            ))
        d.add(dot)
        in_pts.append(dot_pt)

    # Zf : du nœud de sommation vers le haut puis OUT
    above_y = top_y + 1.2
    d.add(elm.Line().at((node_x, inm[1])).up(above_y - inm[1]).color(_WIRE))
    _z_box(d, (node_x, above_y), (out[0], above_y), "Zf", zf, ci)
    d.add(elm.Line().at((out[0], above_y)).toy(out[1]).color(_WIRE))

    out_pt = (out[0] + 1.0, out[1])
    d.add(elm.Line().at(out).to(out_pt).color(_WIRE).label(out_label, loc="right", color=_WIRE))
    return {"in": in_pts[0], "out": out_pt, "in_pts": in_pts}


def _draw_aop_non_inverseur_zf_zg(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT",
                                  ref=None):
    """@brief Dessin du non-inverseur : signal sur IN+, pont Zf/Zg cliquable sur IN-.

    Topologie distincte de l'inverseur : l'entrée attaque IN+, et IN- porte un
    diviseur Zf (vers OUT, par le haut) / Zg (vers la masse). Gain = 1 + Zf/Zg.

    @param imp Dict {'Zf': bloc, 'Zg': bloc} (cf. détecteur).
    @param ci Dict {ref → {type, value}} pour étiquettes/valeurs.
    @param origin/in_label/out_label cf. _draw_aop_inverseur_zin_zf.
    @param ref Référence U du montage (registre de positions), ou None.
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    zf, zg = imp["Zf"], imp["Zg"]
    op = d.add(elm.Opamp().right().anchor("in2").at(origin).color(_WIRE).fill(_OPAMP_FILL))
    _enregistrer_position(d, ref, origin)
    in1, out = op.in1, op.out                          # in1 = IN-, in2 = IN+ (signal)

    # Entrée -> IN+ (broche du bas)
    d.add(elm.Line().at(op.in2).left(1.2).color(_WIRE))
    in_pt = (op.in2[0] - 1.2, op.in2[1])
    d.add(elm.Dot().at(in_pt).color(_WIRE).label(in_label, loc="left", color=_WIRE))

    # Nœud du diviseur, juste à gauche de IN-. Zf en repart vers le haut (puis OUT)
    # et Zg vers la gauche (horizontale, comme la Zin de l'inverseur) jusqu'à la masse.
    noeud = (in1[0] - 1.3, in1[1])
    d.add(elm.Line().at(noeud).to(in1).color(_WIRE))
    d.add(elm.Dot().at(noeud).color(_WIRE))

    # Zf : contre-réaction nœud -> OUT (riser à gauche puis par le haut)
    above_y = in1[1] + 2.0
    d.add(elm.Line().at(noeud).up(above_y - noeud[1]).color(_WIRE))
    zf_p1, zf_p2 = (noeud[0], above_y), (out[0], above_y)
    _z_box(d, zf_p1, zf_p2, "Zf", zf, ci)
    d.add(elm.Line().at(zf_p2).toy(out[1]).color(_WIRE))
    out_pt = (out[0] + 1.0, out[1])
    d.add(elm.Line().at(out).to(out_pt).color(_WIRE).label(out_label, loc="right", color=_WIRE))

    # Zg : nœud -> masse (boîte Z horizontale vers la gauche, masse en bout)
    zg_p1 = (noeud[0] - 3.0, noeud[1])
    _z_box(d, zg_p1, noeud, "Zg", zg, ci)
    d.add(elm.Line().at(zg_p1).left(0.5).color(_WIRE))
    d.add(elm.Ground().color(_WIRE))

    return {"in": in_pt, "out": out_pt}


def _draw_non_inverting_amp(d, result, ci):
    """@brief Dessine le schéma « Amplificateur non-inverseur (AOP) » : AOP + Zf/Zg cliquables.

    Repli : si le match ne porte pas d'impédances structurées, dessin R fixe.
    """
    imp = result.get("impedances")
    if imp:
        _draw_aop_non_inverseur_zf_zg(d, imp, ci, ref=_ref(result, ci, "U"))
        return

    rs = _refs(result, ci, "R")
    rf  = rs[0] if rs else "Rf"
    rg  = rs[1] if len(rs) > 1 else "Rg"

    op = d.add(elm.Opamp().anchor("in2").at((4.5, 0)))
    _enregistrer_position(d, _ref(result, ci, "U"), (4.5, 0))
    d.add(elm.Line().at(op.in2).left(1.2).label("IN+", loc="left"))

    fb_pt = op.in1  # IN− pin
    # Rg: move left 2.2 units (past IN+ wire endpoint at x=3.3) then down
    d.add(elm.Line().at(fb_pt).left(2.2))
    d.add(elm.Resistor().down().label(_lbl(rg, ci), loc="right"))
    d.add(elm.Ground())
    d.add(elm.Dot().at(fb_pt))

    # Rf feedback: up from IN−, tox to out.x, toy down to out
    above = (fb_pt[0], fb_pt[1] + 1.5)
    d.add(elm.Line().at(fb_pt).up(1.5))
    d.add(elm.Resistor().at(above).right().tox(op.out[0])
          .label(_lbl(rf, ci), loc="top"))
    d.add(elm.Line().toy(op.out[1]))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


def _diviseur_sur_net(net, ci):
    """@brief Repère un pont diviseur (passif vers une alim + passif vers la masse)
    branché sur `net`.

    @param net Net à inspecter (typiquement l'entrée IN+ d'un suiveur).
    @param ci Dict {ref → {type, value, pins}}.
    @return tuple (haut, bas) de blocs Z {'refs','composition','nodes'} si `net`
            porte exactement une jambe vers l'alim et une vers la masse, sinon None.
    """
    if not net:
        return None
    haut = bas = None
    for ref, info in (ci or {}).items():
        if (info.get("type") or "").upper() not in ("R", "C", "L"):
            continue
        nets = list(((info or {}).get("pins") or {}).values())
        if net not in nets:
            continue
        autres = [n for n in nets if n != net]
        if len(autres) != 1:
            continue
        autre = autres[0]
        bloc = {"refs": [ref], "composition": ref, "nodes": (net, autre)}
        if is_power_net(autre):
            haut = bloc
        elif is_ground_net(autre):
            bas = bloc
    return (haut, bas) if (haut and bas) else None


def _draw_follower(d, result, ci, origin=(4.5, 0), in_label="IN", out_label="OUT"):
    """@brief Dessine le schéma « Suiveur de tension (AOP) ».

    Si l'entrée IN+ est alimentée par un pont diviseur rail↔masse (cas du buffer
    de référence), le pont est dessiné en deux boîtes Z cliquables ; sinon IN+ est
    une simple entrée. cf. _diviseur_sur_net.

    @param origin/in_label/out_label cf. _draw_aop_inverseur_zin_zf.
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    op = d.add(elm.Opamp().right().anchor("in2").at(origin))
    if isinstance(result, dict) and result.get("components"):
        _enregistrer_position(d, _ref(result, ci, "U"), origin)
    in_net = (result.get("nodes") or [None])[0] if isinstance(result, dict) else None
    pont = _diviseur_sur_net(in_net, ci)
    if pont:
        haut, bas = pont
        npt = (op.in2[0] - 1.2, op.in2[1])
        d.add(elm.Line().at(op.in2).to(npt).color(_WIRE))
        d.add(elm.Dot().at(npt).color(_WIRE))
        # Jambe haute -> alim. Labels LATERAUX (audit ilots 2026-07-13) : en
        # "top"/"bottom" ils tombaient au BOUT des boites, le label de Z1
        # ecrasant celui du rail VCC juste au-dessus.
        ztop = (npt[0], npt[1] + 1.7)
        _z_box(d, npt, ztop, "Z1", haut, ci, label_loc="left")
        d.add(elm.Line().at(ztop).up(0.4).color(_WIRE))
        # Label VCC pose explicitement AU-DESSUS du fil : .label(loc="top")
        # sur un fil vertical tourne avec lui et retombe a gauche, dans le
        # territoire du label lateral de Z1.
        d.add(elm.Label().at((ztop[0], ztop[1] + 0.55)).label(
            "VCC", halign="center", valign="bottom", color=_WIRE))
        # Jambe basse -> masse
        zbot = (npt[0], npt[1] - 1.7)
        _z_box(d, npt, zbot, "Z2", bas, ci, label_loc="left")
        d.add(elm.Line().at(zbot).down(0.4).color(_WIRE))
        d.add(elm.Ground().color(_WIRE))
        in_pt = npt
    else:
        d.add(elm.Line().at(op.in2).left(1.2))
        in_pt = (op.in2[0] - 1.2, op.in2[1])
        d.add(elm.Dot().at(in_pt).label(in_label, loc="left"))

    out_pt0 = op.out
    in1_pt = op.in1   # IN− (upper pin)

    # Feedback routes ABOVE the opamp to avoid crossing IN+:
    # OUT → right → up above opamp → left back to IN− x → down to IN−
    top_y = in1_pt[1] + 2.0
    branch_pt = (out_pt0[0] + 0.75, out_pt0[1])
    out_pt = (branch_pt[0] + 0.8, branch_pt[1])
    d.add(elm.Line().at(out_pt0).to(branch_pt))
    d.add(elm.Dot().at(branch_pt))
    feedback_x = in1_pt[0] - 0.85
    d.add(elm.Line().at(branch_pt).toy(top_y))
    d.add(elm.Line().tox(feedback_x))
    d.add(elm.Line().toy(in1_pt[1]))
    d.add(elm.Line().to(in1_pt))
    d.add(elm.Line().at(branch_pt).to(out_pt).label(out_label, loc="right"))
    return {"in": in_pt, "out": out_pt}


_CHAINE_DX = 10.0     # pas horizontal entre deux blocs de montage (largeur bloc + marge)
_AOP_OUT_DY = 0.625   # décalage broche->sortie de l'AOP schemdraw (out sous in1, mesuré)


def _dessiner_montage_a(d, match, ci, origin, in_label, out_label):
    """@brief Dessine un montage à `origin` via son drawer partagé ; renvoie ses ancres.

    @return dict {"in": (x,y), "out": (x,y)}.
    """
    imp = match.get("impedances") or {}
    ct = match.get("circuit_type", "")
    if ct in _DRAWERS and (ct in _MONTAGES_TRANSISTOR_CHAINABLES
                           or ct in _MONTAGES_TRANSISTOR_TERMINAUX
                           or ct in _MONTAGES_PORTES_CMOS):
        res = _DRAWERS[ct](d, match, ci, origin=origin, titre=False,
                           in_label=in_label, out_label=out_label)
        ins, _out = _io_montage(match, ci)
        # SEULES les portes CMOS exposent un point réel par net (res["nets"],
        # posé par gui.logic_schematic._porte_symbole/_porte_transistors) : une
        # porte à N entrées (NAND/NOR) ne doit pas les collapser toutes sur
        # l'unique point res["in"] (première entrée). Les familles transistor
        # mono-entrée restent sur le stub externe res["in"] : leur res["nets"]
        # pointe des nœuds INTERNES (ex. base du Darlington après Rb), qu'un
        # consommateur aval court-circuiterait s'il s'y raccordait.
        if ct in _MONTAGES_PORTES_CMOS:
            nets = res.get("nets") or {}
            res["ins"] = {n: nets.get(n, res["in"]) for n in ins}
        else:
            res["ins"] = {n: res["in"] for n in ins}
        return res

    # Montages ancrés "center" (à router avant les branches Zin/Zg) :
    u_ref = _ref(match, ci, "U")
    if "sommateur" in ct.lower():
        res = _draw_aop_sommateur(d, imp, ci, origin, in_label, out_label, ref=u_ref)
    elif "différentiel" in ct.lower() or "differentiel" in ct.lower():
        in1 = "VIN-" if in_label == "VIN" else (in_label or "IN1")
        in2 = "VIN+" if in_label == "VIN" else "IN2"
        res = _draw_aop_differentiel(
            d, imp, ci, origin,
            in1_label=in1,
            in2_label=in2,
            out_label=out_label,
            ref=u_ref,
        )
    elif "Schmitt" in ct:
        res = _draw_aop_schmitt(d, imp, ci, origin, in_label, out_label, ref=u_ref)
    elif "Comparateur" in ct:
        res = _draw_aop_comparateur(d, match, ci, origin, in_label, out_label)
    elif "Zg" in imp:
        res = _draw_aop_non_inverseur_zf_zg(d, imp, ci, origin, in_label, out_label, ref=u_ref)
    elif "Zin" in imp:
        res = _draw_aop_inverseur_zin_zf(d, imp, ci, origin, in_label, out_label, ref=u_ref)
    else:
        res = _draw_follower(d, match, ci, origin, in_label, out_label)

    # Ancres par net d'entrée (pour le câblage branché) : les drawers multi-entrées
    # exposent "in_pts" (ordonné comme _in_nets) ; sinon l'unique "in" suffit.
    in_pts = res.get("in_pts") or [res["in"]]
    res["ins"] = dict(zip(_in_nets(match), in_pts))
    return res


def _couplage_entre(m_out, m_in, couplages, find, ci):
    """@brief Couplage reliant la sortie de m_out à l'entrée de m_in, ou None."""
    out = _io_montage(m_out, ci)[1]
    ins = _io_montage(m_in, ci)[0]
    if out is None:
        return None
    entrees = {n for n in ins if n}
    for z in couplages:
        a, b = z["nodes"]
        if out in (a, b) and (a in entrees or b in entrees):
            return z
    cibles = {find(n) for n in ins if n}
    for z in couplages:
        a, b = z["nodes"]
        if (find(out) in (find(a), find(b))
                and (find(a) in cibles or find(b) in cibles)):
            return z
    return None


def _fil_avec_couplage(d, out_pt, in_pt, cc, ci):
    """@brief Relie out_pt -> in_pt en intercalant le symbole du couplage."""
    midx = (out_pt[0] + in_pt[0]) / 2
    demi = 0.6 + _z_locale_extra(d, cc, 1.2) / 2
    p1 = (midx - demi, out_pt[1])
    p2 = (midx + demi, out_pt[1])
    d.add(elm.Line().at(out_pt).to(p1).color(_WIRE))
    _dessiner_symbole_couplage(d, p1, p2, cc, ci)
    d.add(elm.Line().at(p2).to((in_pt[0], out_pt[1])).color(_WIRE))
    d.add(elm.Line().at((in_pt[0], out_pt[1])).to(in_pt).color(_WIRE))


def _fil_canal_avec_couplage(d, out_pt, in_pt, channel_x, cc, ci):
    """@brief Fil en canal avec le couplage dessiné sur la branche de destination.

    Le réseau déplié (`_z_reseau`) peut avoir besoin de plus de largeur que
    l'espace [channel_x, in_pt] alloué par le routage (réseaux composites,
    cf. `_z_locale_extra`) : un centrage symétrique naïf sur ce segment
    déborderait alors des DEUX côtés à la fois -- l'amorce gauche traverserait
    le bus vertical du canal, et la borne droite du réseau engloutirait le
    point d'entrée de la destination (et son Dot de prise, posé à une position
    fixe qui suppose une boîte compacte). On ancre donc le réseau sur sa borne
    réelle de sortie (le même petit dégagement qu'un réseau qui rentre déjà
    dans l'espace alloué) et on repousse le canal vertical à gauche pour
    rejoindre sa borne réelle d'entrée -- jamais l'inverse : les fils du
    caller se terminent toujours sur les bornes réelles p1/p2 du réseau
    (cf. `_agencement_entre`), sans jamais les dépasser.
    """
    cap_x = (channel_x + in_pt[0]) / 2
    demi = 0.6 + _z_locale_extra(d, cc, 1.2) / 2
    p1x, p2x = cap_x - demi, cap_x + demi
    if p2x > in_pt[0] - _Z_DETAIL_LABEL_CLEAR:
        p2x = in_pt[0] - _Z_DETAIL_LABEL_CLEAR
        p1x = p2x - 2 * demi
    p1, p2 = (p1x, in_pt[1]), (p2x, in_pt[1])
    canal_x = min(channel_x, p1x)
    d.add(elm.Line().at(out_pt).to((canal_x, out_pt[1])).color(_WIRE))
    d.add(elm.Line().at((canal_x, out_pt[1])).to((canal_x, in_pt[1])).color(_WIRE))
    d.add(elm.Line().at((canal_x, in_pt[1])).to(p1).color(_WIRE))
    _dessiner_symbole_couplage(d, p1, p2, cc, ci)
    d.add(elm.Line().at(p2).to(in_pt).color(_WIRE))


def _refs_couplage(cc):
    """@brief Refs brutes d'un match Impédance Z de couplage."""
    refs = cc.get("refs") or cc.get("components") or []
    return [r for r in refs if isinstance(r, str) and not r.startswith("Z")]


def _couplage_simple_cap(cc, ci):
    """@brief Vrai si le couplage est un condensateur unique."""
    refs = _refs_couplage(cc)
    return len(refs) == 1 and ci.get(refs[0], {}).get("type") == "C"


def _bloc_couplage(cc):
    """@brief Bloc compatible _z_box pour un couplage Impédance Z."""
    refs = _refs_couplage(cc)
    compo = cc.get("composition") or " // ".join(refs) or "Z"
    return {"refs": refs or [compo], "composition": compo,
            "nodes": tuple(cc.get("nodes", ()))}


def _dessiner_symbole_couplage(d, p1, p2, cc, ci):
    """@brief Dessine un couplage en boîte Z cliquable.

    Même un condensateur de liaison seul reste une Impédance Z dans la vue îlot :
    l'afficher en Zc garde une convention visuelle unique pour le drill-down.
    """
    _z_box(d, p1, p2, "Zc", _bloc_couplage(cc), ci)


def _iter_z_locales(stages, ancres, z_matches, ci):
    """@brief (ancre, z, other_net, index, bloque_bas) de chaque Impédance Z
    locale attribuée à un étage, SANS dessiner.

    Logique d'ATTRIBUTION (quel étage/net/index reçoit quelle Z) ET détection
    géométrique `bloque_bas` (un élément de l'étage sous l'ancre force la
    boîte EN LIGNE, cf. `_dessiner_z_locale`) — POINT DE VÉRITÉ UNIQUE
    partagé par `_dessiner_impedances_locales` (dessin réel) et
    `_obstacles_stubs` (rects prévisionnels pour le routeur) : toute
    évolution ici, jamais dupliquée (revue Task 4 : `bloque_bas` calculé côté
    dessin seulement laissait `_obstacles_stubs` protéger une case vide).
    """
    offsets = {}
    for z in z_matches:
        zrefs = set(_refs_couplage(z))
        znets = [n for n in z.get("nodes", []) if n]
        for stage, a in zip(stages, ancres):
            absorbees = set(a.get("absorbed_refs", ()))
            if zrefs and zrefs.issubset(absorbees):
                break
            net_pts = a.get("nets", {})
            communs = [n for n in znets if n in net_pts]
            if not communs:
                continue
            net = communs[0]
            other = next((n for n in znets if n != net), "")
            key = (id(stage), net)
            offsets[key] = offsets.get(key, 0) + 1
            pos = net_pts[net]
            bloque_bas = any(abs(p[0] - pos[0]) < 0.3 and p[1] < pos[1] - 0.3
                             for p in net_pts.values() if p != pos)
            yield pos, z, other, offsets[key] - 1, bloque_bas
            break


def _dessiner_impedances_locales(d, stages, ancres, z_matches, z_utilises, ci):
    """@brief Dessine les Impedances Z locales connectees aux nets d'un etage."""
    restants = [z for z in z_matches if id(z) not in z_utilises]
    for pos, z, other, index, bloque_bas in _iter_z_locales(
            stages, ancres, restants, ci):
        _dessiner_z_locale(d, pos, other, z, ci, index, bloque_bas=bloque_bas)


def _z_locale_extra(d, z, base):
    """@brief Rallonge (unites schemdraw) du moignon d'une Z locale composite.

    En vue detaillee, un moignon a longueur fixe ecrase un reseau a 2+
    composants (chaque symbole n'a plus qu'une fraction d'unite) : le zigzag
    Resistor/la spirale Inductor2 debordent alors de leurs propres bornes
    (audit fenetre F4) et, en parallele, occupent toute la boucle jusqu'aux
    coins des rails (F3). Calcule la longueur nécessaire pour que le plus
    grand symbole atteigne `_Z_DETAIL_SYMBOL_MIN_LEN`, a partir de la mise en
    page reelle (`impedance_schematic.agencer`). Sans effet en vue Z (boîte
    generique, taille libre) ni pour un couplage a une seule ref.
    """
    if not getattr(d, "_mode_detaille", False):
        return 0.0
    refs = _refs_couplage(z)
    if len(refs) <= 1:
        return 0.0
    from circuit_analyzer import impedance
    from gui import impedance_schematic
    arbre = impedance.arbre_expr(z.get("composition") or " // ".join(refs))
    if arbre is None:
        return 0.0
    _sym, _fils, dims = impedance_schematic.agencer(arbre)
    if not dims.largeur:
        return 0.0
    besoin = _Z_DETAIL_SYMBOL_MIN_LEN * dims.largeur / impedance_schematic.W_SYMB
    return max(0.0, besoin - base)


def _dessiner_z_locale(d, anchor, other_net, z, ci, index=0, bloque_bas=False):
    """@brief Dessine une Z locale depuis `anchor` vers un rail ou une etiquette.

    Plusieurs Z sur un même nœud sont étalées horizontalement (`index`) et leur
    étiquette passe dessous pour ne pas se chevaucher.

    @param bloque_bas True si un élément de l'étage occupe l'espace directement
        sous l'ancre (collecteur aligné au-dessus de l'émetteur) : le stub
        vertical le traverserait, on dessine alors la boîte EN LIGNE.

    Hiérarchie visuelle (Task 3) : les fils qui QUITTENT le chemin principal
    pour rejoindre ce stub (branches VCC/GND et branche vers un net satellite)
    sont tracés en `_BUS` (gris net), y compris les fils internes du réseau
    déplié (`wire_color=_BUS` transmis à `_z_box`/`_z_reseau`) — la boîte Z et
    les symboles réels gardent leurs couleurs sémantiques inchangées. Le cas
    `bloque_bas` est un repli géométrique où la boîte est posée EN LIGNE, à
    même le fil de sortie du montage (pas de fil dédié qui « quitte » le
    chemin) : conservé en `_WIRE` par défaut, choix conservateur documenté ici
    car l'appartenance stub/chemin y est ambiguë.
    """
    ax, ay = anchor
    # Étalement horizontal large quand plusieurs Z partagent le même nœud
    # (ex. couplage d'entrée + polarisation sur la même base) -> pas de chevauchement.
    dx = index * 1.8
    if other_net == "VCC":
        extra = _z_locale_extra(d, z, 1.2)
        p1, p2 = (ax + dx, ay + 0.45), (ax + dx, ay + 1.65 + extra)
        d.add(elm.Line().at(anchor).to(p1).color(_BUS))
        _z_box(d, p1, p2, "Z", _bloc_couplage(z), ci, label_loc="right", wire_color=_BUS)
        d.add(elm.Line().at(p2).up(0.35).color(_BUS))
        # Label VCC explicitement AU-DESSUS du stub : .label(loc="top") sur un
        # fil vertical tourne avec lui et retombait a GAUCHE, a moitie sous la
        # boite Z voisine (audit ilots 2026-07-13, darlington relais).
        d.add(elm.Label().at((p2[0], p2[1] + 0.5)).label(
            "VCC", halign="center", valign="bottom", color=_WIRE))
    elif other_net == "GND":
        extra = _z_locale_extra(d, z, 1.2)
        p1, p2 = (ax + dx, ay - 0.45), (ax + dx, ay - 1.65 - extra)
        d.add(elm.Line().at(anchor).to(p1).color(_BUS))
        _z_box(d, p1, p2, "Z", _bloc_couplage(z), ci, label_loc="right", wire_color=_BUS)
        d.add(elm.Line().at(p2).down(0.25).color(_BUS))
        d.add(elm.Ground())
    elif bloque_bas:
        # Un élément (l'émetteur) occupe l'espace sous l'ancre (collecteur) : un
        # stub vertical le traverserait -> boîte EN LIGNE sur le fil de sortie.
        # Reste en _WIRE (cf. docstring) : ce Z est posé sur le fil de sortie
        # du montage lui-même, il ne le quitte pas visuellement.
        extra = _z_locale_extra(d, z, 1.0)
        p1, p2 = (ax + 0.4 + dx, ay), (ax + 1.4 + dx + extra, ay)
        _z_box(d, p1, p2, "Z", _bloc_couplage(z), ci)
    else:
        # Couplage vers un net non-rail : stub vertical vers le BAS (hors du fil
        # d'entrée/sortie horizontal de l'étage), TERMINÉ par le second nœud réel
        # étiqueté -> pas de borne flottante qui paraît coupée. L'étiquette de la Z
        # passe à droite pour laisser la place au nom du nœud sous la boîte.
        extra = _z_locale_extra(d, z, 1.2)
        p1, p2 = (ax + dx, ay - 0.55), (ax + dx, ay - 1.75 - extra)
        d.add(elm.Line().at(anchor).to(p1).color(_BUS))
        _z_box(d, p1, p2, "Z", _bloc_couplage(z), ci, label_loc="right", wire_color=_BUS)
        # Terminer le moignon par un nœud étiqueté du nom du net réel de
        # destination : sinon la boîte paraît avoir une borne flottante coupée
        # et anonyme, même quand ce net est déjà nommé ailleurs sur le schéma
        # (ex. VIN/VOUT du port principal) — deux points distincts du même net
        # portent chacun leur étiquette, pratique standard en schématique.
        d.add(elm.Line().at(p2).down(0.3).color(_BUS))
        fin = (p2[0], p2[1] - 0.3)
        d.add(elm.Dot(open=True).at(fin).color(_BUS))
        if other_net:
            d.add(elm.Label().at((fin[0], fin[1] - 0.25))
                  .label(other_net, halign="center", valign="top",
                         color=_BUS, fontsize=9))


# Cache module des mesures de drawers : cle hashable (circuit_type, refs) ;
# un dict simple (pas de lru_cache : `match` est un dict non hashable).
_MESURES = {}


def _mesurer_montage(match, ci, detaille=False):
    """@brief (largeur, hauteur, ancrage_x) de la bbox du drawer de `match`.

    Dry-run : dessine le montage dans un Drawing jetable a l'origine
    (0, _oy_for(match)), sans titre, et mesure d.get_bbox(). Memoise par
    (circuit_type, refs, detaille) — un meme montage/mode n'est jamais
    mesure deux fois. ancrage_x = 0 - bbox.xmin (decalage origine -> bord
    gauche).

    @param detaille Doit refleter le MODE REEL du rendu appelant (`d.
        _mode_detaille`) : une porte CMOS (entre autres) est nettement plus
        HAUTE en vue detaillee (transistors) qu'en vue Z (symbole compact)
        — mesurer toujours en mode Z (comme avant Task 5) sous-estime la
        hauteur reelle des BANDES d'un DAG multi-rangees en vue detaillee,
        et deux etages parallèles se chevauchent visuellement (audit
        visuel logic_dag_2vers1, Task 5 : titre/VDD du 2e inverseur
        percutant le 1er). La chaîne lineaire (une seule bande) n'exposait
        pas ce piège : ses etages AOP ne varient qu'en LARGEUR entre modes.

    Le Drawing jetable est ouvert via `with` (et non juste instancié) :
    schemdraw empile le Drawing "actif" dans un registre GLOBAL
    (`drawing_stack`) pour permettre `elm.X()` sans `d.add()` explicite.
    `_mesurer_montage` est toujours appelé DEPUIS l'intérieur du `with
    schemdraw.Drawing(canvas=ax) as d:` réel de `_make_chain_fig` — sans
    `with` ici, ce Drawing jetable ne serait jamais poussé sur la pile, le
    Drawing RÉEL resterait "actif", et les éléments du dry-run (labels des
    entrées non câblées type "NET3", notamment) FUITERAIENT sur le schéma
    réel (dédoublement constaté à l'audit visuel Task 4, 2026-07-13 —
    `tests/test_labels_property.py` l'attrapait). `with` empile CE Drawing
    jetable le temps du dry-run, l'isolant du Drawing réel.
    """
    cle = (match.get("circuit_type", ""),
           tuple(sorted(match.get("components") or [])), bool(detaille))
    if cle in _MESURES:
        return _MESURES[cle]
    with schemdraw.Drawing(show=False) as d:
        d._mode_detaille = bool(detaille)
        _dessiner_montage_a(d, match, ci, (0.0, _oy_for(match)), "", "")
        bb = d.get_bbox()
    mesure = (float(bb.xmax - bb.xmin), float(bb.ymax - bb.ymin),
              float(0.0 - bb.xmin))
    _MESURES[cle] = mesure
    return mesure


def _draw_island_chain(d, ordered, ci, couplages=None):
    """@brief Chaîne de montages posee sur la grille absolue (schema_grid)
    et cablee par le routeur Manhattan (schema_router). Spec 2026-07-13.
    `_fil_en_z` ne subsiste que comme REPLI (router -> None), journalise.

    Si un couplage AC (Impédance Z 2 nœuds) relie deux étages, il est dessiné
    sur le fil. Premier bloc étiqueté VIN, dernier VOUT, internes sans
    libellé. Les boîtes Z poussent leurs hitboxes (coords absolues) -> le
    drill-down R/L/C reste cliquable.

    @param ordered Montages triés par flux (cf. _ordonner_montages_flux).
    @param ci Dict {ref → {type, value}}.
    """
    from gui import schema_grid, schema_router
    n = len(ordered)
    mode_detaille = getattr(d, "_mode_detaille", False)
    etages = []
    for i, match in enumerate(ordered):
        larg, haut, ancr = _mesurer_montage(match, ci, detaille=mode_detaille)
        etages.append(schema_grid.EtageMesure(
            cle=f"{i:03d}", colonne=i, bande=0, largeur=larg,
            hauteur=haut, ancrage_x=ancr, ancrage_y=_oy_for(match)))
    plan = schema_grid.poser(etages)

    ancres = []
    rects_io = []
    for i, match in enumerate(ordered):
        in_label = "VIN" if i == 0 else ""
        out_label = "VOUT" if i == n - 1 else ""
        origin = plan.origines[f"{i:03d}"]
        ancres.append(_dessiner_montage_a(d, match, ci, origin,
                                          in_label, out_label))
        _annoter_etage(d, ancres[-1], match)
        rects_io += _rects_ports_etiquetes(ancres[-1], in_label, out_label)

    coupl = [m for m in (couplages or []) if _est_couplage(m)]
    find = _couplage_find(couplages or [])
    couplages_utilises = set()
    obstacles = list(plan.obstacles) + _obstacles_stubs(ordered, ancres,
                                                        coupl, ci)
    for a, m in zip(ancres, ordered):
        obstacles += _rects_annotations(a, m)
    obstacles += rects_io
    nets = []
    for i in range(n - 1):
        # Ports PROJETES sur la FRONTIERE des slots (x1 cote sortie, x0 cote
        # entree), pas l'ancre snappee brute : une ancre est INTERIEURE a son
        # slot-obstacle, et l'A* (interieur strict interdit) ne peut pas en
        # sortir -- le milieu du premier pas est deja strictement dans le
        # slot. 24 replis _fil_en_z sur le corpus au premier render Task 4 ;
        # la frontiere, elle, est praticable par contrat (spec 4.1).
        s_out = plan.slots[f"{i:03d}"]
        s_in = plan.slots[f"{i + 1:03d}"]
        nets.append((f"lien{i}",
                     (s_out.x1, schema_grid.snap(ancres[i]["out"][1])),
                     (s_in.x0, schema_grid.snap(ancres[i + 1]["in"][1]))))
    routes = schema_router.router(nets, obstacles)
    for i in range(n - 1):
        out_pt, in_pt = ancres[i]["out"], ancres[i + 1]["in"]
        poly = routes.get(f"lien{i}")
        cc = _couplage_entre(ordered[i], ordered[i + 1], coupl, find, ci)
        if poly is None:
            _log.warning("routage Manhattan impossible pour lien%d ; "
                         "repli _fil_en_z", i)
            if cc is not None:
                couplages_utilises.add(id(cc))
                _fil_avec_couplage(d, out_pt, in_pt, cc, ci)
            else:
                _fil_en_z(d, out_pt, in_pt)
            continue
        # Raccords port reel -> premier/dernier point snappe (droits, courts)
        _raccord(d, out_pt, poly[0])
        _raccord(d, in_pt, poly[-1])
        if cc is not None:
            couplages_utilises.add(id(cc))
            _polyligne_avec_couplage(d, poly, cc, ci)
        else:
            _tracer_polyligne(d, poly)
    _dessiner_impedances_locales(d, ordered, ancres, coupl,
                                 couplages_utilises, ci)


def _raccord(d, reel, snappe):
    """@brief Fil en L entre l'ancre reelle d'un drawer et son port de grille
    (frontiere du slot) : horizontal puis vertical. dx couvre la traversee de
    la marge du slot (jusqu'a ~2 unites), dy < PAS (residu de snap)."""
    if reel == tuple(snappe):
        return
    coin = (snappe[0], reel[1])
    if coin != tuple(reel):
        d.add(elm.Line().at(reel).to(coin).color(_WIRE))
    if coin != tuple(snappe):
        d.add(elm.Line().at(coin).to(snappe).color(_WIRE))


def _tracer_polyligne(d, poly, couleur=None):
    """@brief Trace une polyligne orthogonale du routeur, segment par segment."""
    c = couleur or _WIRE
    for p, q in zip(poly, poly[1:]):
        d.add(elm.Line().at(p).to(q).color(c))


def _polyligne_avec_couplage(d, poly, cc, ci):
    """@brief Pose le couplage (C serie...) au MILIEU du plus long segment
    horizontal de la polyligne (garanti >= 4*PAS par les couloirs CANAL_H)."""
    segs = [(p, q) for p, q in zip(poly, poly[1:]) if p[1] == q[1]]
    if not segs:
        # Inatteignable aujourd'hui (colonnes distinctes => au moins un
        # segment horizontal) mais garde explicite : repli sur le plus long
        # segment tout court (couplage pose verticalement).
        segs = list(zip(poly, poly[1:]))
    p, q = max(segs, key=lambda s: abs(s[1][0] - s[0][0]))
    milieu = ((p[0] + q[0]) / 2, p[1])
    demi = 0.9
    a, b = (milieu[0] - demi, milieu[1]), (milieu[0] + demi, milieu[1])
    for s, e in zip(poly, poly[1:]):
        if (s, e) == (p, q):
            d.add(elm.Line().at(s).to(a).color(_WIRE))
            _z_box(d, a, b, "Zc", _bloc_couplage(cc), ci)
            d.add(elm.Line().at(b).to(e).color(_WIRE))
        else:
            d.add(elm.Line().at(s).to(e).color(_WIRE))


def _obstacles_stubs(stages, ancres, coupl, ci):
    """@brief Rects previsionnels des stubs Z locales (spec §3.3) — MEME
    geometrie que _dessiner_z_locale (largeur boite 1.2 centree sur l'ancre
    + index*1.8, hauteur 1.65+extra au-dessus (VCC) ou en dessous (autres)).
    Toute evolution de _dessiner_z_locale doit mettre a jour cette fonction
    (test corpus : aucun fil route ne traverse un stub)."""
    from gui.schema_grid import Rect
    rects = []
    for pos, z, other_net, index, bloque_bas in _iter_z_locales(
            stages, ancres, coupl, ci):
        ax, ay = pos
        dx = index * 1.8
        extra = 1.2   # borne haute de _z_locale_extra (previsionnel)
        if bloque_bas and other_net != "VCC":
            # Boite EN LIGNE sur le fil de sortie (cf. _dessiner_z_locale) :
            # p1=(ax+0.4+dx, ay) -> p2=(ax+1.4+dx+extra, ay), demi-hauteur
            # de boite ~0.4 (revue Task 4 : ce cas protegeait une case vide).
            rects.append(Rect(ax + 0.4 + dx, ay - 0.4,
                              ax + 1.4 + dx + extra, ay + 0.4))
        elif other_net == "VCC":
            rects.append(Rect(ax + dx - 0.6, ay, ax + dx + 0.6,
                              ay + 2.0 + extra))
        else:
            rects.append(Rect(ax + dx - 0.6, ay - 2.05 - extra,
                              ax + dx + 0.6, ay))
    return rects


def _oy_for(match):
    """@brief Décalage y de l'origine d'un montage pour que sa sortie tombe sur la
    ligne de base de sa bande (alignement des triangles).

    Schmitt/comparateur/différentiel ancrés "center" -> 0. Inverseur/intég/dériv
    ancrés in1 (haut) et sommateur -> +dy. Non-inverseur/suiveur (in2, bas) -> -dy.
    """
    imp = match.get("impedances") or {}
    ct = match.get("circuit_type", "")
    if ct in _MONTAGES_TRANSISTOR_CHAINABLES or ct in _MONTAGES_TRANSISTOR_TERMINAUX:
        # OUT = collecteur (origine + 0.697) ou émetteur (origine - 0.697).
        # On place l'origine pour que la sortie tombe à peu près sur la ligne de base.
        if ct in ("Collecteur commun (suiveur d'émetteur)", "Étage push-pull",
                  "Paire Darlington"):
            return 0.697
        return -0.697
    if "sommateur" in ct.lower():
        return _AOP_OUT_DY
    if ("Schmitt" in ct or "Comparateur" in ct
            or "différentiel" in ct.lower() or "differentiel" in ct.lower()):
        return 0.0
    if "Zin" in imp:
        return _AOP_OUT_DY
    return -_AOP_OUT_DY


def _fil_en_z(d, out_pt, in_pt):
    """@brief Relie deux points par un fil en Z (horizontal, vertical, horizontal)."""
    _fil_canal(d, out_pt, in_pt, (out_pt[0] + in_pt[0]) / 2)


def _fil_canal(d, out_pt, in_pt, channel_x):
    """@brief Relie out_pt -> in_pt en passant par un canal vertical à `channel_x`
    (horizontal jusqu'au canal, vertical, horizontal jusqu'à l'entrée)."""
    d.add(elm.Line().at(out_pt).to((channel_x, out_pt[1])).color(_WIRE))
    d.add(elm.Line().at((channel_x, out_pt[1])).to((channel_x, in_pt[1])).color(_WIRE))
    d.add(elm.Line().at((channel_x, in_pt[1])).to(in_pt).color(_WIRE))


_ROLE_ETAGE = {
    "Amplificateur différentiel (AOP)":  "Différentiel",
    "Amplificateur sommateur (AOP)":     "Sommateur",
    "Amplificateur non-inverseur (AOP)": "Non-inverseur",
    "Amplificateur inverseur (AOP)":     "Inverseur",
    "Ampli inverseur + boost HF (AOP)":  "Inverseur + boost HF",
    "Ampli inverseur + action intégrale (AOP)": "Inverseur + action intégrale",
    "Intégrateur (AOP)":                 "Intégrateur",
    "Dérivateur (AOP)":                  "Dérivateur",
    "Suiveur de tension (AOP)":          "Suiveur",
    "Comparateur (AOP)":                 "Comparateur",
    "Bascule de Schmitt (AOP)":          "Schmitt",
    # Transistors
    "Transistor en commutation":         "Commutation",
    "Amplificateur émetteur commun":     "Émetteur commun",
    "Collecteur commun (suiveur d'émetteur)": "Suiveur d'émetteur",
    "Étage push-pull":                   "Push-pull",
    "Paire Darlington":                  "Darlington",
    "Miroir de courant BJT":             "Miroir de courant",
    "MOSFET en commutation":             "MOSFET commutation",
    "MOSFET haute-tension (côté haut)":  "MOSFET côté-haut",
    "Commande de relais":                "Commande relais",
}


def _titre_etage(match):
    """@brief Rôle court d'un montage pour l'étiqueter dans la chaîne / le DAG."""
    ct = match.get("circuit_type", "")
    return _ROLE_ETAGE.get(ct, ct.replace(" (AOP)", ""))


def _titre_montage(d, result, pt):
    """@brief Affiche le rôle d'un montage (titre) au point `pt` d'un drawer standalone."""
    d.add(elm.Label().at(pt).label(_titre_etage(result), color=_TITRE_COLOR, fontsize=12))


def _r_simple(d, ref, ci, p1, p2, nom, label_loc="top"):
    """@brief Dessine un passif en résistance simple (symbole classique + étiquette).

    Version « schéma simple » des montages transistor : pas de boîte Z, pas de
    drill-down cliquable. Étiquette « nom = valeur » (ex. « Rb = 10 kΩ »).

    @param ref Référence du passif (R/C/L), ou None pour ne rien dessiner.
    @param p1/p2 Extrémités du composant. @param nom Préfixe d'étiquette.
    @param label_loc Position de l'étiquette ('top'/'bottom'/'left'/'right').
    """
    if not ref:
        return
    _enregistrer_position(d, ref, ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0))
    elem = elm.Resistor().at(p1).to(p2)
    if nom is None:
        d.add(elem)
        return
    d.add(elem.label(_texte_passif_simple(ref, ci, nom), loc=label_loc,
                     fontsize=_SATELLITE_LABEL_FONTSIZE))


def _texte_passif_simple(ref, ci, nom):
    """@brief Texte court d'un passif simple (ex. Rb = 10 kΩ)."""
    from circuit_analyzer.impedance import formater_valeur
    info = ci.get(ref, {})
    val = formater_valeur(info.get("value", ""), info.get("type", "R"))
    return f"{nom} = {val}" if val else nom


def _refs_type_sur_net(ci, typ, net):
    """@brief Références de type `typ` connectées au net donné."""
    if not net:
        return []
    return [
        ref for ref, info in (ci or {}).items()
        if info.get("type") == typ and net in ((info.get("pins") or {}).values())
    ]


def _autre_net_passif(ci, ref, net):
    """@brief Autre borne d'un passif `ref` connecte a `net`, ou None."""
    pins = (ci.get(ref, {}) or {}).get("pins", {}) or {}
    vals = [n for n in pins.values() if n]
    if net not in vals:
        return None
    return next((n for n in vals if n != net), None)


def _ref_passif_simple(ci, types, net, pred_autre):
    """@brief Unique passif de `types` entre `net` et un autre net valide.

    Si plusieurs passifs existent (reseau complexe), on ne choisit rien : la Z
    locale reste dessinee et cliquable.
    """
    candidats = []
    for ref, info in (ci or {}).items():
        if info.get("type") not in types:
            continue
        autre = _autre_net_passif(ci, ref, net)
        if autre and pred_autre(autre):
            candidats.append(ref)
    return candidats[0] if len(candidats) == 1 else None


def _ref_passif_simple_vers_masse(ci, types, net):
    """@brief Unique passif simple entre `net` et une masse."""
    return _ref_passif_simple(ci, types, net, is_ground_net)


def _ref_passif_simple_vers_alim(ci, types, net):
    """@brief Unique passif simple entre `net` et une alimentation."""
    return _ref_passif_simple(ci, types, net, is_power_net)


def _ref_resistance_entree_simple(ci, net):
    """@brief Unique resistance serie entre `net` et un net signal externe."""
    def est_signal_entree(autre):
        n = (autre or "").strip().upper()
        return (not is_ground_net(autre)
                and (not is_power_net(autre) or n in {"VIN", "VIN+", "VIN-"}))

    return _ref_passif_simple(
        ci, ("R",), net,
        est_signal_entree,
    )


def _charge_verticale(d, ref, ci, longueur=1.1):
    """@brief Dessine une charge simple verticale (L/R/C) et son libelle."""
    typ = ci.get(ref, {}).get("type")
    if typ in ("L", "K"):
        elem = elm.Inductor2(nturns=4)
    elif typ == "C":
        elem = elm.Capacitor()
    elif typ == "R":
        elem = elm.Resistor()
    else:
        elem = elm.Line()
    e = d.add(elem.up(longueur))
    _enregistrer_position(d, ref, e.center)
    # Label cale a DROITE du symbole : loc="right" retombe centre sur le fil
    # vertical (les spires de l'inductance rendent la bbox symetrique), d'ou un
    # chevauchement label/fil a l'audit visuel.
    d.add(elm.Label().at((e.center[0] + 0.45, e.center[1]))
          .label(_lbl(ref, ci), fontsize=9, halign="left"))


def _points_annotation(ancres, match):
    """@brief (title_pt, gain_pt|None) d'un étage — POINT DE VÉRITÉ UNIQUE
    partagé par `_annoter_etage` (dessin) et `_rects_annotations` (obstacles
    prévisionnels du routeur, revue finale Task 7)."""
    out = ancres.get("out")
    if not out:
        return None, None
    title_pt = ancres.get("title") or (out[0] + 1.4, out[1] + 0.85)
    gain_pt = (out[0] + 1.4, out[1] - 0.85) if _texte_gain(match, None) else None
    return title_pt, gain_pt


def _rects_annotations(ancres, match):
    """@brief Rects prévisionnels couvrant le rôle et le gain d'un étage,
    à réserver comme OBSTACLES du routeur Manhattan.

    Les annotations vivent dans le couloir CANAL_H, plus étroit que leurs
    textes : un bus vertical routé les traversait et le moteur anti-collision
    oscillait entre les deux bus encadrants (itérations épuisées — revue
    finale Task 7, pid_controller). Les rects laissent libre la bande y du
    port de sortie (à out.y, ENTRE titre et gain) pour ne pas réintroduire le
    piège Task 4 (départ enfermé dans un obstacle)."""
    from gui.schema_grid import Rect, snap
    title_pt, gain_pt = _points_annotation(ancres, match)
    rects = []
    for pt, demi_h in ((title_pt, 0.4), (gain_pt, 0.35)):
        if pt is None:
            continue
        rects.append(Rect(snap(pt[0] - 1.5), snap(pt[1] - demi_h),
                          snap(pt[0] + 1.5), snap(pt[1] + demi_h)))
    return rects


def _rects_ports_etiquetes(ancres, in_label, out_label):
    """@brief Rects-obstacles des labels de ports (VIN/VOUT/VINx/VOUTx).

    Un bus routé qui contourne par l'extérieur passait SUR le label d'une
    entrée (revue finale Task 7, 'VIN3' de pid_controller). Sans risque de
    ré-enfermer un port routé : une entrée étiquetée (couche 0) n'est jamais
    une arrivée de routage, une sortie étiquetée (dernière couche) jamais un
    départ."""
    from gui.schema_grid import Rect, snap
    rects = []
    p = ancres.get("in")
    if in_label and p is not None:
        rects.append(Rect(snap(p[0] - 1.9), snap(p[1] - 0.45),
                          snap(p[0]), snap(p[1] + 0.45)))
    p = ancres.get("out")
    if out_label and p is not None:
        rects.append(Rect(snap(p[0]), snap(p[1] - 0.45),
                          snap(p[0] + 1.9), snap(p[1] + 0.45)))
    return rects


def _annoter_etage(d, ancres, match):
    """@brief Étiquette un étage : rôle au-dessus de sa sortie, gain en dessous.

    Placé à droite de l'AOP (espace inter-étages) pour ne pas percuter le réseau
    Zf/Zg. Purement additif : aucun impact sur le câblage ni les ancres.
    """
    title_pt, gain_pt = _points_annotation(ancres, match)
    if title_pt is None:
        return
    d.add(elm.Label().at(title_pt).label(
        _titre_etage(match), color=_TITRE_COLOR, fontsize=11))
    if gain_pt is not None:
        d.add(elm.Label().at(gain_pt).label(
            _texte_gain(match, None), color=_GAIN_COLOR, fontsize=8))


def _branched_edges(layers, ci=None, matches=None):
    """@brief Arêtes AVANT du DAG de montages (producteur.couche < consommateur.couche).

    Ignore les back-edges (issus d'une détection imparfaite) qui traverseraient le
    schéma. Agnostique au type via `_io_montage`.
    @return list[(prod_match, cons_match, net)].
    """
    ci = ci or {}
    find = _couplage_find(matches or [m for L in layers for m in L])
    layer_of = {id(m): lx for lx, L in enumerate(layers) for m in L}
    out_by_net = {}
    for L in layers:
        for m in L:
            _ins, out = _io_montage(m, ci)
            if out:
                out_by_net[find(out)] = m
    edges = []
    for couche in layers:
        for cons in couche:
            ins, _out = _io_montage(cons, ci)
            for net in ins:
                prod = out_by_net.get(find(net))
                if prod is None or prod is cons:
                    continue
                if layer_of[id(prod)] >= layer_of[id(cons)]:
                    continue
                edges.append((prod, cons, net))
    return edges


def _draw_branched_chain(d, layers, ci, couplages=None):
    """@brief Dessine un îlot multi-AOP branché en couches (cf. _layers_montages_flux),
    posé sur la grille absolue (schema_grid) et câblé par le routeur Manhattan
    (schema_router) — même architecture que `_draw_island_chain` (spec 2026-07-13),
    généralisée aux couches multi-bandes (colonne = couche, bande = position dans
    la couche) et au fan-out (une arête routée par consommateur).

    `_fil_canal` ne subsiste que comme REPLI (router -> None), journalisé.

    @param layers list[list[match]] couches ordonnées entrée->sortie.
    @param ci Dict {ref → {type, value}}.
    """
    from gui import schema_grid, schema_router
    dernier = len(layers) - 1
    # Plusieurs sorties parallèles dans la dernière couche -> labels distincts
    # (VOUT1, VOUT2…) pour lever l'ambiguïté ; une seule sortie reste « VOUT ».
    # Même logique pour les entrées de la première couche (VIN / VIN1, VIN2…) :
    # sans label, le point d'entrée du fan-out restait anonyme (audit D5).
    n_sorties = len(layers[dernier]) if layers else 0
    n_entrees = len(layers[0]) if layers else 0

    mode_detaille = getattr(d, "_mode_detaille", False)
    cle_of = {}
    etages = []
    for lx, couche in enumerate(layers):
        for ry, match in enumerate(couche):
            cle = f"{lx:02d}_{ry:02d}"
            cle_of[id(match)] = cle
            larg, haut, ancr = _mesurer_montage(match, ci, detaille=mode_detaille)
            etages.append(schema_grid.EtageMesure(
                cle=cle, colonne=lx, bande=ry, largeur=larg, hauteur=haut,
                ancrage_x=ancr, ancrage_y=_oy_for(match)))
    plan = schema_grid.poser(etages)

    ancres = {}                            # id(match) -> ancres ("out","ins",...)
    rects_io = []
    for lx, couche in enumerate(layers):
        for ry, match in enumerate(couche):
            if lx != dernier:
                out_label = ""
            elif n_sorties > 1:
                out_label = f"VOUT{ry + 1}"
            else:
                out_label = "VOUT"
            if lx != 0:
                in_label = ""
            elif n_entrees > 1:
                in_label = f"VIN{ry + 1}"
            else:
                in_label = "VIN"
            origin = plan.origines[cle_of[id(match)]]
            ancres[id(match)] = _dessiner_montage_a(d, match, ci, origin,
                                                    in_label, out_label)
            _annoter_etage(d, ancres[id(match)], match)
            rects_io += _rects_ports_etiquetes(ancres[id(match)],
                                               in_label, out_label)

    coupl = [m for m in (couplages or []) if _est_couplage(m)]
    find = _couplage_find(couplages or [])
    flat = [m for couche in layers for m in couche]
    flat_ancres = [ancres[id(m)] for m in flat]

    # Nets à router : une arête PAR consommateur (fan-out non partagé, cf. spec
    # §4.2/brief Task 5 — lisibilité, chaque branche reste indépendamment
    # écartable par le routeur). Ports PROJETÉS sur la FRONTIÈRE des slots
    # (x1 côté sortie, x0 côté entrée), jamais l'ancre snappée brute (cf.
    # _draw_island_chain / piège Task 4 : une ancre est INTÉRIEURE à son
    # slot-obstacle, l'A* ne peut pas en sortir). Tri par (couche du
    # producteur, nom) avant routage -> déterminisme des réservations d'arêtes.
    layer_of = {id(m): lx for lx, couche in enumerate(layers) for m in couche}
    edges = _branched_edges(layers, ci, matches=couplages)

    def _nom_net(prod, cons, net):
        # Cles de grille STABLES (cle_of, format "lx_ry" positionnel) plutot
        # que id(prod)/id(cons) : id() varie d'un process Python a l'autre
        # (adresse memoire), ce qui rendait le nom de net -- et donc le tri
        # des aretes servant au routage -- non reproductible inter-process
        # (revue finale Task 7, FIX 1).
        return f"{net}_{cle_of[id(prod)]}_{cle_of[id(cons)]}"

    edges = sorted(edges, key=lambda e: (layer_of[id(e[0])], _nom_net(*e)))
    par_producteur = {}
    for prod, _cons, _net in edges:
        par_producteur[id(prod)] = par_producteur.get(id(prod), 0) + 1
    dots_poses = set()

    # Couplage par arête, résolu AVANT le calcul des obstacles : un couplage
    # consommé ici (dessiné EN LIGNE sur le fil routé) ne doit pas être aussi
    # réservé comme Z locale par `_obstacles_stubs` -- sinon un même couplage
    # (ex. Cc collecteur->base d'un fan-out à 2 branches) se retrouve compté
    # deux fois (index 0 et 1 empilés au même point) et condamne le SEUL
    # chemin d'échappement du départ commun à une unique direction, que 2
    # arêtes distinctes (non partageables) ne peuvent plus emprunter toutes
    # les deux -- 2 replis constatés sur ilot_branche_ce_fanout/ilot_reel_
    # fanout_filtres_rlc (revue Task 5).
    cc_par_arete = {}
    couplages_utilises = set()
    for prod, cons, net in edges:
        cc = _couplage_entre(prod, cons, coupl, find, ci)
        cc_par_arete[(id(prod), id(cons), net)] = cc
        if cc is not None:
            couplages_utilises.add(id(cc))
    coupl_locaux = [z for z in coupl if id(z) not in couplages_utilises]
    obstacles = list(plan.obstacles) + _obstacles_stubs(flat, flat_ancres,
                                                        coupl_locaux, ci)
    for m in flat:
        obstacles += _rects_annotations(ancres[id(m)], m)
    obstacles += rects_io

    nets = []
    for prod, cons, net in edges:
        s_out = plan.slots[cle_of[id(prod)]]
        s_in = plan.slots[cle_of[id(cons)]]
        out_pt = ancres[id(prod)]["out"]
        in_pt = ancres[id(cons)]["ins"][net]
        nets.append((_nom_net(prod, cons, net),
                     (s_out.x1, schema_grid.snap(out_pt[1])),
                     (s_in.x0, schema_grid.snap(in_pt[1]))))
    routes = schema_router.router(nets, obstacles)

    for prod, cons, net in edges:
        nom = _nom_net(prod, cons, net)
        out_pt, in_pt = ancres[id(prod)]["out"], ancres[id(cons)]["ins"][net]
        # Départ commun d'un fan-out (>1 consommateur) : un Dot rend le
        # branchement explicite, posé une seule fois par producteur.
        if par_producteur.get(id(prod), 0) > 1 and id(prod) not in dots_poses:
            d.add(elm.Dot().at(out_pt).color(_WIRE))
            dots_poses.add(id(prod))
        poly = routes.get(nom)
        cc = cc_par_arete[(id(prod), id(cons), net)]
        if poly is None:
            _log.warning("routage Manhattan impossible pour %s ; "
                         "repli _fil_canal", nom)
            channel_x = (out_pt[0] + in_pt[0]) / 2
            if cc is not None:
                couplages_utilises.add(id(cc))
                _fil_canal_avec_couplage(d, out_pt, in_pt, channel_x, cc, ci)
            else:
                _fil_canal(d, out_pt, in_pt, channel_x)
            continue
        # Raccords port réel -> premier/dernier point snappé (droits, courts).
        _raccord(d, out_pt, poly[0])
        _raccord(d, in_pt, poly[-1])
        if cc is not None:
            couplages_utilises.add(id(cc))
            _polyligne_avec_couplage(d, poly, cc, ci)
        else:
            _tracer_polyligne(d, poly)

    _dessiner_impedances_locales(d, flat, flat_ancres, coupl, couplages_utilises, ci)


def _draw_integrator(d, result, ci):
    """@brief Dessine le schéma « Intégrateur (AOP) » : AOP + Zin/Zf cliquables.

    Repli : si le match ne porte pas d'impédances structurées, dessin R/C fixe.
    """
    imp = result.get("impedances")
    if imp:
        _draw_aop_inverseur_zin_zf(d, imp, ci, ref=_ref(result, ci, "U"))
        return

    rs = _refs(result, ci, "R"); cs = _refs(result, ci, "C")
    r = rs[0] if rs else "R"
    c = cs[0] if cs else "C"

    op = d.add(elm.Opamp().anchor("in1").at((4.5, 0)))
    _enregistrer_position(d, _ref(result, ci, "U"), (4.5, 0))
    d.add(elm.Resistor().at(op.in1).left().label(_lbl(r, ci), loc="top"))
    d.add(elm.Dot().label("IN", loc="left"))
    mid_pt = op.in1
    d.add(elm.Line().at(op.in2).left(1))
    d.add(elm.Ground())

    above = (mid_pt[0], mid_pt[1] + 1.5)
    d.add(elm.Line().at(mid_pt).up(1.5))
    d.add(elm.Capacitor().at(above).right().tox(op.out[0])
          .label(_lbl(c, ci), loc="top"))
    d.add(elm.Line().toy(op.out[1]))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


def _draw_differentiator(d, result, ci):
    """@brief Dessine le schéma « Dérivateur (AOP) » : AOP + Zin/Zf cliquables.

    Repli : si le match ne porte pas d'impédances structurées, dessin C/R fixe.
    """
    imp = result.get("impedances")
    if imp:
        _draw_aop_inverseur_zin_zf(d, imp, ci, ref=_ref(result, ci, "U"))
        return

    cs = _refs(result, ci, "C"); rs = _refs(result, ci, "R")
    c = cs[0] if cs else "C"
    r = rs[0] if rs else "R"

    op = d.add(elm.Opamp().anchor("in1").at((4.5, 0)))
    _enregistrer_position(d, _ref(result, ci, "U"), (4.5, 0))
    d.add(elm.Capacitor().at(op.in1).left().label(_lbl(c, ci), loc="top"))
    d.add(elm.Dot().label("IN", loc="left"))
    mid_pt = op.in1
    d.add(elm.Line().at(op.in2).left(1))
    d.add(elm.Ground())

    above = (mid_pt[0], mid_pt[1] + 1.5)
    d.add(elm.Line().at(mid_pt).up(1.5))
    d.add(elm.Resistor().at(above).right().tox(op.out[0])
          .label(_lbl(r, ci), loc="top"))
    d.add(elm.Line().toy(op.out[1]))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


def _draw_aop_comparateur(d, _result, ci, origin=(4.5, 0), in_label="IN+", out_label="OUT"):
    """@brief Comparateur (AOP) en boucle ouverte : IN+ signal / IN- REF / OUT.

    Aucune impédance (pas de Z cliquable). Paramétré (origin/libellés) et renvoyant
    ses ancres pour être chaînable dans la vue îlot.

    @return dict {"in": (x,y), "out": (x,y)}.
    """
    op = d.add(elm.Opamp().right().anchor("center").at(origin).color(_WIRE).fill(_OPAMP_FILL))
    if isinstance(_result, dict) and _result.get("components"):
        _enregistrer_position(d, _ref(_result, ci, "U"), origin)
    d.add(elm.Line().at(op.in2).left(1.3).color(_WIRE))
    in_pt = (op.in2[0] - 1.3, op.in2[1])
    d.add(elm.Dot().at(in_pt).color(_WIRE).label(in_label, loc="left", color=_WIRE))
    d.add(elm.Line().at(op.in1).left(1.3).color(_WIRE))
    d.add(elm.Dot().at((op.in1[0] - 1.3, op.in1[1])).color(_WIRE).label("REF", loc="left", color=_WIRE))
    out_pt = (op.out[0] + 1.3, op.out[1])
    d.add(elm.Line().at(op.out).to(out_pt).color(_WIRE).label(out_label, loc="right", color=_WIRE))
    return {"in": in_pt, "out": out_pt}


def _draw_comparator(d, result, ci):
    """@brief Dessine le schéma « Comparateur (AOP) » (vue autonome)."""
    _draw_aop_comparateur(d, result, ci)


def _draw_aop_schmitt(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT", ref=None):
    """@brief Dessine la bascule de Schmitt : contre-réaction positive Zf
    (OUT → IN+) + patte d'entrée Zin sur IN+, toutes deux cliquables.

    @param imp Dict {'Zf': bloc, 'Zin': bloc?} (cf. détecteur).
    @param ref Référence U du montage (registre de positions), ou None.
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    zf = imp["Zf"]
    zin = imp.get("Zin")
    op = d.add(elm.Opamp().right().anchor("center").at(origin).color(_WIRE).fill(_OPAMP_FILL))
    _enregistrer_position(d, ref, origin)
    inm, inp, out = op.in1, op.in2, op.out

    # IN- = référence. Étiquette au-DESSUS de la patte (l'étiquette de Zin occupe
    # l'espace à gauche, entre les deux entrées) -> évite le chevauchement REF/Zin.
    d.add(elm.Line().at(inm).left(1.2).color(_WIRE))
    d.add(elm.Dot().at((inm[0] - 1.2, inm[1])).color(_WIRE).label("REF", loc="top", color=_WIRE))

    # Nœud IN+
    np_node = (inp[0] - 1.0, inp[1])
    d.add(elm.Line().at(np_node).to(inp).color(_WIRE))
    d.add(elm.Dot().at(np_node).color(_WIRE))
    in_pt = np_node

    # Zin : entrée -> IN+ (horizontale vers la gauche). Étiquette en DESSOUS :
    # REF est au-dessus (sur IN-), l'étiquette de la couche supérieure servirait
    # sinon de zone de collision (REF / titre de l'étage amont en vue chaîne).
    if zin:
        zin_p1 = (np_node[0] - 3.0, np_node[1])
        _z_box(d, zin_p1, np_node, "Zin", zin, ci, label_loc="bottom")
        d.add(elm.Line().at(zin_p1).left(0.5).color(_WIRE))
        in_pt = (zin_p1[0] - 0.5, zin_p1[1])
        d.add(elm.Dot().at(in_pt).color(_WIRE).label(in_label, loc="left", color=_WIRE))

    # Zf : contre-réaction positive OUT -> IN+ (par le bas pour éviter le corps)
    below_y = inp[1] - 1.8
    d.add(elm.Line().at(np_node).down(np_node[1] - below_y).color(_WIRE))
    _z_box(d, (np_node[0], below_y), (out[0], below_y), "Zf", zf, ci, label_loc="bottom")
    d.add(elm.Line().at((out[0], below_y)).toy(out[1]).color(_WIRE))

    out_pt = (out[0] + 1.2, out[1])
    d.add(elm.Line().at(out).to(out_pt).color(_WIRE).label(out_label, loc="right", color=_WIRE))
    return {"in": in_pt, "out": out_pt}


def _draw_schmitt(d, result, ci):
    """@brief Dessine le schéma « Bascule de Schmitt (AOP) »."""
    imp = result.get("impedances")
    if imp:
        _draw_aop_schmitt(d, imp, ci, ref=_ref(result, ci, "U"))
        return

    rs = _refs(result, ci, "R")
    rf = rs[0] if rs else "Rf"

    op = d.add(elm.Opamp().anchor("center").at((4.5, 0)))
    _enregistrer_position(d, _ref(result, ci, "U"), (4.5, 0))
    d.add(elm.Line().at(op.in1).left(1.2).label("REF", loc="left"))

    in2_pt = op.in2  # IN+ (non-inverting, lower pin)
    d.add(elm.Line().at(in2_pt).left(0.8).label("IN", loc="left"))
    d.add(elm.Dot().at(in2_pt))

    # Positive feedback routes BELOW the opamp to avoid body overlap:
    # OUT → right → down below → Rf left past opamp → up to IN+
    out_pt = op.out
    bot_y  = in2_pt[1] - 1.2   # below IN+
    d.add(elm.Line().at(out_pt).right(0.6))
    d.add(elm.Line().toy(bot_y))
    d.add(elm.Resistor().left().tox(in2_pt[0]).label(_lbl(rf, ci), loc="bottom"))
    d.add(elm.Line().toy(in2_pt[1]))
    # OUT label (overlaps the short right(0.6) wire — visually one segment)
    d.add(elm.Line().at(out_pt).right(1.6).label("OUT", loc="right"))


def _draw_aop_differentiel(d, imp, ci, origin=(6.0, 0),
                           in1_label="IN1", in2_label="IN2", out_label="OUT", ref=None):
    """@brief Dessine le différentiel : AOP + pont Z1/Zf/Z3/Zg cliquable.

    @param imp Dict {'Z1','Zf','Z3','Zg'} (cf. détecteur).
    @param ref Référence U du montage (registre de positions), ou None.
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    z1, zf, z3, zg = imp["Z1"], imp["Zf"], imp["Z3"], imp["Zg"]
    op = d.add(elm.Opamp().right().anchor("center").at(origin).color(_WIRE).fill(_OPAMP_FILL))
    _enregistrer_position(d, ref, origin)
    inm, inp, out = op.in1, op.in2, op.out

    # IN- (haut) : Z1 depuis la source, Zf en contre-réaction par le haut
    nm = (inm[0] - 1.3, inm[1])
    d.add(elm.Line().at(nm).to(inm).color(_WIRE))
    d.add(elm.Dot().at(nm).color(_WIRE))
    z1_p1 = (nm[0] - 3.0, nm[1])
    _z_box(d, z1_p1, nm, "Z1", z1, ci)
    d.add(elm.Line().at(z1_p1).left(0.6).color(_WIRE))
    in1_pt = (z1_p1[0] - 0.6, z1_p1[1])
    d.add(elm.Dot().at(in1_pt).color(_WIRE).label(in1_label, loc="left", color=_WIRE))
    above_y = inm[1] + 2.2
    d.add(elm.Line().at(nm).up(above_y - nm[1]).color(_WIRE))
    _z_box(d, (nm[0], above_y), (out[0], above_y), "Zf", zf, ci)
    d.add(elm.Line().at((out[0], above_y)).toy(out[1]).color(_WIRE))

    # IN+ (bas) : Z3 depuis la source, Zg vers la masse (verticale)
    npn = (inp[0] - 1.3, inp[1])
    d.add(elm.Line().at(npn).to(inp).color(_WIRE))
    d.add(elm.Dot().at(npn).color(_WIRE))
    z3_p1 = (npn[0] - 3.0, npn[1])
    # Label sous la boite : la branche IN+ est tout pres de IN- (meme plage x),
    # un label "top" percuterait la boite Z1 au-dessus.
    _z_box(d, z3_p1, npn, "Z3", z3, ci, label_loc="bottom")
    d.add(elm.Line().at(z3_p1).left(0.6).color(_WIRE))
    in2_pt = (z3_p1[0] - 0.6, z3_p1[1])
    d.add(elm.Dot().at(in2_pt).color(_WIRE).label(in2_label, loc="left", color=_WIRE))
    zg_p2 = (npn[0], npn[1] - 1.6)
    # Label a droite de la boite verticale : "bottom" percute la legende « Astuce »
    # en bas de l'axe, "left" percute la boite Z3 au-dessus (audit visuel).
    _z_box(d, npn, zg_p2, "Zg", zg, ci, label_loc="right")
    d.add(elm.Line().at(zg_p2).down(0.4).color(_WIRE))
    d.add(elm.Ground().color(_WIRE))

    out_pt = (out[0] + 1.0, out[1])
    d.add(elm.Line().at(out).to(out_pt).color(_WIRE).label(out_label, loc="right", color=_WIRE))
    # in_pts ordonné comme _in_nets (Z1 puis Z3) pour le câblage branché.
    return {"in": in1_pt, "out": out_pt, "in_pts": [in1_pt, in2_pt]}


def _draw_differential_amp(d, result, ci):
    """@brief Dessine le schéma « Amplificateur différentiel (AOP) »."""
    imp = result.get("impedances")
    if imp:
        _draw_aop_differentiel(d, imp, ci, ref=_ref(result, ci, "U"))
        return

    rs = _refs(result, ci, "R")
    # Pattern returns [U, r_inp_to_gnd, r_inp_from_src, r_inm_feedback, r_inm_from_src]
    rg  = rs[0] if len(rs) > 0 else "Rg"   # IN+ → GND  (bias/gain)
    r1  = rs[1] if len(rs) > 1 else "R1"   # source → IN+ (input)
    rf  = rs[2] if len(rs) > 2 else "Rf"   # IN- → OUT  (feedback)
    r2  = rs[3] if len(rs) > 3 else "R2"   # source → IN- (input)

    op = d.add(elm.Opamp().anchor("center").at((6.0, 0)))
    _enregistrer_position(d, _ref(result, ci, "U"), (6.0, 0))

    # IN+ path: R1 goes left from IN+; loc="bottom" keeps label away from r2 above it
    d.add(elm.Resistor().at(op.in2).left(1.35).label(_lbl(r1, ci), loc="bottom"))
    in1_junc = d.here                             # left end of R1 = IN1 node
    d.add(elm.Dot().label("IN1", loc="left"))
    d.add(elm.Resistor().at(in1_junc).down(1.25).label(_lbl(rg, ci), loc="top"))
    d.add(elm.Ground())

    # IN- path with feedback
    in1_pt = op.in1
    d.add(elm.Resistor().at(in1_pt).left(1.35).label(_lbl(r2, ci), loc="top"))
    d.add(elm.Dot().label("IN2", loc="left"))
    above = (in1_pt[0], in1_pt[1] + 1.8)
    d.add(elm.Line().at(in1_pt).up(1.8))
    d.add(elm.Resistor().at(above).right().tox(op.out[0])
          .label(_lbl(rf, ci), loc="top"))
    d.add(elm.Line().toy(op.out[1]))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


def _draw_summing_amp(d, result, ci):
    """@brief Dessine le schéma « Amplificateur sommateur (AOP) »."""
    imp = result.get("impedances")
    if imp:
        _draw_aop_sommateur(d, imp, ci, ref=_ref(result, ci, "U"))
        return

    rs = _refs(result, ci, "R")
    rf = rs[0] if rs else "Rf"
    inputs = rs[1:] if len(rs) > 1 else ["Ra", "Rb"]
    n = min(len(inputs), 3)

    op = d.add(elm.Opamp().anchor("in1").at((5, 0)))
    _enregistrer_position(d, _ref(result, ci, "U"), (5, 0))
    in1_pt = op.in1  # summing node (IN-)
    # Route IN+ straight down to GND — avoids merging visually with the bottom of the input bus
    d.add(elm.Line().at(op.in2).left(0.65))
    d.add(elm.Line().down(0.75))
    d.add(elm.Ground())

    spacing = 1.4
    y_offs = [i * spacing for i in range(n)]
    top_y  = in1_pt[1] + y_offs[-1]
    bot_y  = in1_pt[1]

    # Vertical bus at in1_pt.x connecting all input ends to summing node
    if n > 1:
        d.add(elm.Line().at((in1_pt[0], bot_y)).toy(top_y))
    # Junction dot always present (even n==1, marks summing node clearly)
    d.add(elm.Dot().at(in1_pt))

    # Input resistors going left from the bus; dot + INx label at each left end
    for i in range(n):
        node_y = in1_pt[1] + y_offs[i]
        d.add(elm.Resistor().at((in1_pt[0], node_y)).left()
              .label(_lbl(inputs[i], ci), loc="top"))
        d.add(elm.Dot().label(f"IN{i+1}", loc="left"))

    # Feedback Rf: up from in1_pt, then tox(out.x), then toy to out
    above_y = top_y + 0.8
    d.add(elm.Line().at(in1_pt).toy(above_y))
    d.add(elm.Resistor().at((in1_pt[0], above_y)).right().tox(op.out[0])
          .label(_lbl(rf, ci), loc="top"))
    d.add(elm.Line().toy(op.out[1]))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


# ── Transistor patterns ───────────────────────────────────────────────────────

def _draw_bjt_switch(d, result, ci, origin=(3, 0), titre=True,
                     in_label="IN", out_label="LOAD"):
    """@brief Schéma « Transistor en commutation ». Paramétrique en origine."""
    q = _ref(result, ci, "Q"); r = _ref(result, ci, "R")
    q_pins = ci.get(q, {}).get("pins", {})
    absorbed_refs = {r} if r in ci else set()
    load = _ref_on_net(_refs(result, ci, "L"), ci, q_pins.get("C"))
    if not load:
        load = _ref_passif_simple_vers_alim(ci, ("L", "R", "C"), q_pins.get("C"))
    if load:
        absorbed_refs.add(load)
    t = d.add(elm.BjtNpn().at(origin))
    _enregistrer_position(d, q, origin)
    bx, by = t.base
    in_pt = (bx - 2.6, by)
    _r_simple(d, r, ci, in_pt, (bx - 0.9, by), None)
    d.add(elm.Label().at(((in_pt[0] + bx - 0.9) / 2, by + 0.52))
          .label(_texte_passif_simple(r, ci, "Rb"),
                 fontsize=_SATELLITE_LABEL_FONTSIZE))
    d.add(elm.Line().at((bx - 0.9, by)).to((bx, by)))
    dot = elm.Dot().at(in_pt)
    if in_label:
        dot = dot.label(in_label, loc="left")
    d.add(dot)
    cx, cy = t.collector
    out_pt = (cx, cy + 1.0)
    if load:
        d.add(elm.Line().at(t.collector).up(0.35))
        _charge_verticale(d, load, ci)
        d.add(elm.Line().up(1.2))
        d.add(elm.Dot().label("VCC", loc="top"))
        line = elm.Line().at(t.collector).to((cx + 1.0, cy))
        if out_label:
            line = line.label(out_label, loc="right")
        d.add(line)
        out_pt = (cx + 1.0, cy)
    else:
        line = elm.Line().at(t.collector).to(out_pt)
        if out_label:
            line = line.label(out_label, loc="right")
        d.add(line)
    emitter_net = q_pins.get("E")
    if emitter_net == "GND":
        d.add(elm.Line().at(t.emitter).down(0.5))
        d.add(elm.Ground())
    else:
        d.add(elm.Dot().at(t.emitter))
    title_pt = (cx, cy + (3.8 if load else 1.8))
    if titre:
        _titre_montage(d, result, title_pt)
    return {"in": in_pt, "out": out_pt, "title": title_pt,
            "nets": {q_pins.get("B"): in_pt,
                     q_pins.get("C"): out_pt,
                     q_pins.get("E"): t.emitter},
            "absorbed_refs": absorbed_refs}


def _draw_common_emitter(d, result, ci, origin=(3, 0), titre=True,
                         in_label="IN", out_label="OUT"):
    """@brief Schéma « Amplificateur émetteur commun ». Paramétrique en origine,
    renvoie ses ancres {"in","out"} (réutilisé en vue chaîne)."""
    q = _ref(result, ci, "Q")
    rs = _refs(result, ci, "R")
    # Pattern returns [Q, r_at_collector, r_at_base] → rs[0]=Rc, rs[1]=Rb
    q_pins = ci.get(q, {}).get("pins", {})
    rc = _ref_on_net(rs, ci, q_pins.get("C"), rs[0] if rs else "Rc")
    remaining = [r for r in rs if r != rc]
    rb = _ref_on_net(remaining, ci, q_pins.get("B")) if remaining else None
    # .right() force une orientation DETERMINISTE : sans direction explicite, le
    # BjtNpn herite de la direction courante du dessin, qu'un drawer amont (ex.
    # Darlington en vue chaine) peut laisser inversee -> transistor mirroir dont
    # l'emetteur percute l'etiquette Rb (cf. ilot_chaine_darlington_ce).
    t = d.add(elm.BjtNpn().at(origin).right())
    _enregistrer_position(d, q, origin)
    bx, by = t.base
    in_pt = (bx - 2.6, by)
    if rb:
        _r_simple(d, rb, ci, in_pt, (bx - 0.9, by), None)
        # Ajustement ciblé d'ancre (D2) : centré strictement sur Rb (comme
        # avant), le label tombait à l'aplomb du stub d'entrée déplié (C1+R1,
        # pendu sous VIN en vue détaillée) et traversait les plaques de C1.
        # Recentré (toujours halign="center", par défaut) dans la fenêtre
        # libre entre le stub (gauche) et la base du transistor (droite) :
        # dégage C1 sans pour autant chevaucher le symbole du transistor.
        d.add(elm.Label().at((bx - 1.2, by - 0.78))
              .label(_texte_passif_simple(rb, ci, "Rb"),
                     fontsize=_SATELLITE_LABEL_FONTSIZE))
        d.add(elm.Line().at((bx - 0.9, by)).to((bx, by)))
    else:
        # Couplage DC (base = collecteur amont) : fil direct, pas de Rb fantôme.
        d.add(elm.Line().at(in_pt).to((bx, by)))
    dot = elm.Dot().at(in_pt)
    if in_label:
        dot = dot.label(in_label, loc="left")
    d.add(dot)
    # Rc en boîte Z verticale, du collecteur vers VCC
    cx, cy = t.collector
    _r_simple(d, rc, ci, (cx, cy + 0.5), (cx, cy + 1.9), None)
    # halign="right" : l'étiquette se TERMINE à l'ancre (côté gauche du zigzag)
    # au lieu d'être centrée dessus -> sans ça, la moitié droite du texte
    # ("kΩ") traverse le symbole (audit fenêtre F1).
    d.add(elm.Label().at((cx - 1.05, cy + 1.35))
          .label(_texte_passif_simple(rc, ci, "Rc"),
                 fontsize=_SATELLITE_LABEL_FONTSIZE, halign="right"))
    d.add(elm.Line().at(t.collector).to((cx, cy + 0.5)))
    d.add(elm.Line().at((cx, cy + 1.9)).up(0.4).label("VCC", loc="top"))
    emitter_net = q_pins.get("E")
    if emitter_net == "GND":
        d.add(elm.Line().at(t.emitter).down(0.5))
        d.add(elm.Ground())
    else:
        d.add(elm.Dot().at(t.emitter))
    out_pt = (cx + 1.5, cy)
    line = elm.Line().at(t.collector).to(out_pt)
    if out_label:
        line = line.label(out_label, loc="right")
    d.add(line)
    if titre:
        _titre_montage(d, result, (cx, cy + 2.7))
    return {"in": in_pt, "out": out_pt, "title": (cx, cy + 2.7),
            "nets": {q_pins.get("B"): in_pt,
                     q_pins.get("C"): t.collector,
                     q_pins.get("E"): t.emitter}}


def _draw_mosfet_switch(d, result, ci, origin=(3, 0), titre=True,
                        in_label="IN", out_label="LOAD"):
    """@brief Dessine le schéma « MOSFET en commutation »."""
    m = _ref(result, ci, "M"); r = _ref(result, ci, "R")
    m_pins = ci.get(m, {}).get("pins", {})
    absorbed_refs = {r} if r in ci else set()
    load = _ref_passif_simple_vers_alim(ci, ("L", "R", "C"), m_pins.get("D"))
    if load:
        absorbed_refs.add(load)
    # .reverse() : NFet 0.22 place sa grille à DROITE par défaut (drain/source
    # inchangés) -> IN se retrouvait à droite du symbole, flux droite->gauche,
    # en miroir par rapport à tous les autres montages (IN toujours à gauche).
    # reverse() ramène la grille à GAUCHE sans toucher drain/source (cf. D3).
    t = d.add(elm.NFet().at(origin).reverse())
    _enregistrer_position(d, m, origin)
    gx, gy = t.gate
    _r_simple(d, r, ci, (gx - 0.9, gy), (gx - 2.6, gy), "Rg")
    d.add(elm.Line().at(t.gate).to((gx - 0.9, gy)))
    in_pt = (gx - 2.6, gy)
    dot = elm.Dot().at(in_pt)
    if in_label:
        dot = dot.label(in_label, loc="left")
    d.add(dot)
    if load:
        d.add(elm.Line().at(t.drain).up(0.35))
        _charge_verticale(d, load, ci)
        d.add(elm.Line().up(1.2))
        d.add(elm.Dot().label("VCC", loc="top"))
        out_pt = t.drain
    else:
        line = elm.Line().at(t.drain).up(1)
        if out_label:
            line = line.label(out_label, loc="right")
        d.add(line)
        out_pt = d.here
    d.add(elm.Line().at(t.source).down(0.5))
    d.add(elm.Ground())
    title_pt = (t.drain[0], t.drain[1] + (3.8 if load else 1.8))
    if titre:
        _titre_montage(d, result, title_pt)
    return {"in": in_pt, "out": out_pt, "title": title_pt,
            "nets": {m_pins.get("G"): in_pt,
                     m_pins.get("D"): t.drain,
                     m_pins.get("S"): t.source},
            "absorbed_refs": absorbed_refs}


def _draw_high_side_mosfet(d, result, ci):
    """@brief Dessine le schéma « MOSFET haute-tension (côté haut) »."""
    m = _ref(result, ci, "M")
    r = _ref(result, ci, "R")
    # .reverse() : cf. D3 dans _draw_mosfet_switch — ramène la grille à GAUCHE
    # (sans toucher drain/source) pour garder IN à gauche, comme partout ailleurs.
    t = d.add(elm.NFet().at((3, 0)).reverse())
    _enregistrer_position(d, m, (3, 0))
    gx, gy = t.gate
    _r_simple(d, r, ci, (gx - 0.9, gy), (gx - 2.6, gy), "Rg")
    d.add(elm.Line().at(t.gate).to((gx - 0.9, gy)))
    d.add(elm.Dot().at((gx - 2.6, gy)).label("IN", loc="left"))
    # Drain at top → VCC power rail
    d.add(elm.Line().at(t.drain).up(1))
    d.add(elm.Dot().label("VCC", loc="right"))
    # Source at bottom → load (not GND)
    d.add(elm.Line().at(t.source).down(1))
    d.add(elm.Dot().label("LOAD", loc="left"))
    _titre_montage(d, result, (t.drain[0], t.drain[1] + 1.8))


def _draw_relay_driver(d, result, ci):
    """@brief Dessine le schéma « Commande de relais » (K + Q/M + diode flyback)."""
    k   = _ref(result, ci, "K")
    qs  = _refs(result, ci, "Q")
    ms  = _refs(result, ci, "M")
    rbs = _refs(result, ci, "R")
    dbs = _refs(result, ci, "D")

    use_mosfet = not qs and bool(ms)
    t = d.add((elm.NFet() if use_mosfet else elm.BjtNpn()).at((3.5, 0)))
    _enregistrer_position(d, (ms[0] if use_mosfet else (qs[0] if qs else None)), (3.5, 0))

    ctrl_pin = t.gate if use_mosfet else t.base
    coll_pin = t.drain if use_mosfet else t.collector
    emit_pin = t.source if use_mosfet else t.emitter
    ctrl_lbl = "VG" if use_mosfet else "CMD"

    # Contrôle : résistance de base en boîte Z cliquable, ou ligne directe
    cxp, cyp = ctrl_pin
    if not rbs:
        ctrl_net = None
        if qs:
            ctrl_net = ci.get(qs[0], {}).get("pins", {}).get("B")
        elif ms:
            ctrl_net = ci.get(ms[0], {}).get("pins", {}).get("G")
        rbs = _refs_type_sur_net(ci, "R", ctrl_net)
    if rbs:
        _r_simple(d, rbs[0], ci, (cxp - 2.4, cyp), (cxp - 0.7, cyp), "Rb")
        d.add(elm.Line().at((cxp - 0.7, cyp)).to((cxp, cyp)))
        d.add(elm.Dot().at((cxp - 2.4, cyp)).label(ctrl_lbl, loc="left"))
    else:
        d.add(elm.Line().at(ctrl_pin).left(1).label(ctrl_lbl, loc="left"))

    # Bobine du relais : collecteur → petit segment → bobine → VCC. Le segment
    # dégage l'étiquette K1 du fil de collecteur.
    coil_len = 1.8
    d.add(elm.Line().at(coll_pin).up(0.4))
    coil_bot = d.here
    d.add(elm.Dot().at(coil_bot))
    d.add(elm.Inductor2(nturns=4).up(coil_len))
    coil_top = d.here
    d.add(elm.Dot().at(coil_top))
    d.add(elm.Line().up(0.3).label("VCC", loc="top"))
    _enregistrer_position(d, k, (coil_bot[0], (coil_bot[1] + coil_top[1]) / 2))
    # Étiquette de la bobine à gauche, dégagée du fil
    d.add(elm.Label().at((coil_bot[0] - 0.7, (coil_bot[1] + coil_top[1]) / 2))
          .label(_lbl(k, ci)))

    # Diode flyback en parallèle de la bobine (anode côté collecteur, cathode VCC).
    # dbs peut etre vide (la diode n'est pas toujours incluse dans les
    # composants detectes du montage) alors que le symbole, lui, est TOUJOURS
    # trace -- on retrouve alors sa ref par ses broches (meme idiome que le
    # repli `rbs` ci-dessus) pour le registre de positions UNIQUEMENT : le
    # libelle affiche (`diode_lbl`) reste inchange (aucun impact visuel).
    d1_ref = dbs[0] if dbs else None
    if not d1_ref:
        coll_net = None
        if qs:
            coll_net = ci.get(qs[0], {}).get("pins", {}).get("C")
        elif ms:
            coll_net = ci.get(ms[0], {}).get("pins", {}).get("D")
        cand = _refs_type_sur_net(ci, "D", coll_net)
        d1_ref = cand[0] if cand else None
    diode_lbl = _lbl(dbs[0], ci) if dbs else ""
    d.add(elm.Line().at(coil_bot).right(1.6))
    diode_el = d.add(_symbole_diode(d1_ref, ci).up(coil_len).label(diode_lbl, loc="right"))
    _enregistrer_position(d, d1_ref, diode_el.center)
    d.add(elm.Line().tox(coil_top[0]))

    # Émetteur → GND
    d.add(elm.Line().at(emit_pin).down(0.5))
    d.add(elm.Ground())
    _titre_montage(d, result, (coil_top[0], coil_top[1] + 0.9))


def _draw_current_mirror(d, result, ci):
    """@brief Dessine le schéma « Miroir de courant BJT »."""
    qs = _refs(result, ci, "Q")
    t1 = d.add(elm.BjtNpn().at((1.5, 0)))
    t2 = d.add(elm.BjtNpn().at((4.5, 0)))
    _enregistrer_position(d, qs[0] if qs else None, (1.5, 0))
    _enregistrer_position(d, qs[1] if len(qs) > 1 else None, (4.5, 0))

    # Shared base wire + junction dots at both bases
    d.add(elm.Line().at(t1.base).tox(t2.base[0]))
    d.add(elm.Dot().at(t1.base))
    d.add(elm.Dot().at(t2.base))

    # T-junction above Q1 body (collector.y + 0.6 clears the body top)
    junc_y  = t1.collector[1] + 0.6        # ≈ 1.30
    junc_pt = (t1.collector[0], junc_y)    # ≈ (2.25, 1.30)

    # Collector → UP to junction
    d.add(elm.Line().at(t1.collector).toy(junc_y))
    d.add(elm.Dot().at(junc_pt))            # T-junction dot

    # Diode branch: LEFT then DOWN to Q1.base — stays outside body
    d.add(elm.Line().at(junc_pt).tox(t1.base[0]))
    d.add(elm.Line().toy(t1.base[1]))

    # Iref up from the junction; Iout at same absolute height for symmetry
    iref_top = junc_y + 0.7
    d.add(elm.Line().at(junc_pt).toy(iref_top).label("Iref", loc="right"))
    d.add(elm.Line().at(t2.collector).toy(iref_top).label("Iout", loc="right"))

    # Emitters to GND
    d.add(elm.Line().at(t1.emitter).down(0.3))
    d.add(elm.Ground())
    d.add(elm.Line().at(t2.emitter).down(0.3))
    d.add(elm.Ground())
    _titre_montage(d, result, ((t1.collector[0] + t2.collector[0]) / 2, iref_top + 0.7))


def _draw_suiveur_emetteur(d, result, ci, origin=(3, 0), titre=True,
                           in_label="IN", out_label="OUT"):
    """@brief « Collecteur commun (suiveur d'émetteur) ». Paramétrique en origine."""
    q = _ref(result, ci, "Q")
    rs = _refs(result, ci, "R")
    q_pins = ci.get(q, {}).get("pins", {})
    re = _ref_on_net(rs, ci, q_pins.get("E"), rs[0] if rs else "Re")
    rb = next((r for r in rs if r != re), None)
    t = d.add(elm.BjtNpn().at(origin))
    _enregistrer_position(d, q, origin)
    bx, by = t.base
    in_pt = (bx - 2.6, by)
    if rb:
        _r_simple(d, rb, ci, in_pt, (bx - 0.9, by), "Rb")
        d.add(elm.Line().at((bx - 0.9, by)).to((bx, by)))
        dot = elm.Dot().at(in_pt)
        if in_label:
            dot = dot.label(in_label, loc="left")
        d.add(dot)
    else:
        in_pt = (bx - 1.0, by)
        line = elm.Line().at(t.base).to(in_pt)
        if in_label:
            line = line.label(in_label, loc="left")
        d.add(line)
    # Collecteur -> VCC
    d.add(elm.Line().at(t.collector).up(1).label("VCC", loc="top"))
    # Émetteur -> Re -> GND, sortie au point d'émetteur
    ex, ey = t.emitter
    # Ajustement ciblé d'ancre (D1) : en vue détaillée, une charge Z dépliée en
    # aval (ex. L1//R8) s'étale perpendiculairement de part et d'autre de son
    # ancre -> à 1.4 du noeud émetteur elle percute Re (qui reste, lui, à
    # l'aplomb de l'émetteur). On éloigne le segment de sortie pour lui laisser
    # sa marge d'étalement ; la vue Z garde 1.4 (sa boîte compacte ne collisionne pas).
    out_dx = 2.6 if getattr(d, "_mode_detaille", False) else 1.4
    out_pt = (ex + out_dx, ey)
    line = elm.Line().at(t.emitter).to(out_pt)
    if out_label:
        line = line.label(out_label, loc="right")
    d.add(line)
    _r_simple(d, re, ci, (ex, ey - 0.6), (ex, ey - 2.0), None)
    # Label a GAUCHE de Re : a droite du noeud emetteur/OUT, la chaine peut poser
    # une boite Z de sortie (ex. L1//R8) qui percuterait "Re = ..." (audit visuel).
    # halign="right" : le texte se TERMINE à l'ancre au lieu d'être centré
    # dessus, sinon sa moitié droite traverse le zigzag (audit fenêtre F1).
    d.add(elm.Label().at((ex - 0.9, ey - 1.25))
          .label(_texte_passif_simple(re, ci, "Re"),
                 fontsize=_SATELLITE_LABEL_FONTSIZE, halign="right"))
    d.add(elm.Line().at(t.emitter).to((ex, ey - 0.6)))
    d.add(elm.Line().at((ex, ey - 2.0)).down(0.4))
    d.add(elm.Ground())
    if titre:
        _titre_montage(d, result, (t.collector[0], t.collector[1] + 1.8))
    return {"in": in_pt, "out": out_pt,
            "title": (t.collector[0], t.collector[1] + 1.8),
            "nets": {q_pins.get("B"): in_pt,
                     q_pins.get("C"): t.collector,
                     q_pins.get("E"): out_pt}}


def _draw_push_pull(d, result, ci, origin=(3, 0), titre=True,
                    in_label="IN", out_label="OUT"):
    """@brief « Étage push-pull ». Paramétrique en origine."""
    ox, oy = origin
    qn = d.add(elm.BjtNpn().at((ox, oy + 1.7)))
    qp = d.add(elm.BjtPnp().at((ox, oy - 1.7)))
    # Ref NPN/PNP distinguees par leur collecteur (NPN -> alim, PNP -> masse),
    # meme convention que le cablage juste en dessous.
    qs = _refs(result, ci, "Q")
    npn_ref = next((r for r in qs if is_power_net(ci.get(r, {}).get("pins", {}).get("C"))), None)
    pnp_ref = next((r for r in qs if r != npn_ref), None)
    _enregistrer_position(d, npn_ref, (ox, oy + 1.7))
    _enregistrer_position(d, pnp_ref, (ox, oy - 1.7))
    # Bases communes (entrée) reliées verticalement, prise d'entrée à gauche
    d.add(elm.Line().at(qn.base).to(qp.base))
    midb = ((qn.base[0] + qp.base[0]) / 2, (qn.base[1] + qp.base[1]) / 2)
    d.add(elm.Dot().at(midb))
    # Moignon d'entrée allongé : sinon les nœuds IN et OUT (proches sur un totem-pole)
    # paraissent confondus. On éloigne nettement les bornes de part et d'autre.
    in_pt = (midb[0] - 2.6, midb[1])
    line = elm.Line().at(midb).to(in_pt)
    if in_label:
        line = line.label(in_label, loc="left")
    d.add(line)
    # Collecteurs : NPN -> VCC, PNP -> GND
    d.add(elm.Line().at(qn.collector).up(1.0).label("VCC", loc="top"))
    d.add(elm.Line().at(qp.collector).down(1.0))
    d.add(elm.Ground())
    # Émetteurs communs -> sortie, prise de sortie bien à droite
    d.add(elm.Line().at(qn.emitter).to(qp.emitter))
    mide = ((qn.emitter[0] + qp.emitter[0]) / 2, (qn.emitter[1] + qp.emitter[1]) / 2)
    d.add(elm.Dot().at(mide))
    out_pt = (mide[0] + 2.6, mide[1])
    line = elm.Line().at(mide).to(out_pt)
    if out_label:
        line = line.label(out_label, loc="right")
    d.add(line)
    if titre:
        _titre_montage(d, result, (qn.collector[0], qn.collector[1] + 1.8))
    return {"in": in_pt, "out": out_pt,
            "title": (qn.collector[0], qn.collector[1] + 1.8)}


def _draw_darlington(d, result, ci, origin=(3, 0), titre=True,
                     in_label="IN", out_label="OUT"):
    """@brief « Paire Darlington » (suiveur OU émetteur commun selon Q2).

    Suiveur : collecteurs au rail, sortie sur l'émetteur de Q2 via Re. Émetteur
    commun : émetteur de Q2 à la masse, sortie sur le collecteur de Q2 (cas du
    Darlington pilotant une charge côté collecteur, ex. relais)."""
    ox, oy = origin
    qs = _refs(result, ci, "Q")
    pins = {r: ci.get(r, {}).get("pins", {}) for r in qs}
    emetteurs = {pins[r].get("E") for r in qs}
    q2ref = next((r for r in qs if pins[r].get("B") in emetteurs), qs[-1] if qs else None)
    q1ref = next((r for r in qs if r != q2ref), qs[0] if qs else None)
    q1pins = pins.get(q1ref, {})
    q2pins = pins.get(q2ref, {})
    config = _darlington_config(q2pins) if q2pins else "suiveur"
    absorbed_refs = set()
    rin = _ref_resistance_entree_simple(ci, q1pins.get("B"))
    if rin:
        absorbed_refs.add(rin)

    q1 = d.add(elm.BjtNpn().at((ox, oy + 1.7)))
    q2 = d.add(elm.BjtNpn().at((ox + 1.8, oy - 1.4)))
    _enregistrer_position(d, q1ref, (ox, oy + 1.7))
    _enregistrer_position(d, q2ref, (ox + 1.8, oy - 1.4))
    if rin:
        in_pt = (q1.base[0] - 2.8, q1.base[1])
        base_node = (q1.base[0] - 0.65, q1.base[1])
        _r_simple(d, rin, ci, in_pt, (q1.base[0] - 1.05, q1.base[1]), "Rb")
        d.add(elm.Line().at((q1.base[0] - 1.05, q1.base[1])).to(q1.base))
        dot = elm.Dot().at(in_pt)
        if in_label:
            dot = dot.label(in_label, loc="left")
        d.add(dot)
    else:
        in_pt = (q1.base[0] - 1.4, q1.base[1])
        base_node = q1.base
        line = elm.Line().at(q1.base).to(in_pt)
        if in_label:
            line = line.label(in_label, loc="left")
        d.add(line)
    # E(Q1) -> B(Q2) : descente verticale puis horizontale (pas de diagonale)
    d.add(elm.Line().at(q1.emitter).toy(q2.base[1]))
    d.add(elm.Line().tox(q2.base[0]))
    d.add(elm.Dot().at(q2.base))
    nets = {q1pins.get("B"): base_node}

    if config == "emetteur_commun":
        # Q1.C -> VCC ; sortie sur le COLLECTEUR de Q2 ; émetteur de Q2 -> GND.
        d.add(elm.Line().at(q1.collector).up(0.9).label("VCC", loc="top"))
        cx, cy = q2.collector
        node = (cx, cy + 0.7)
        d.add(elm.Line().at(q2.collector).to(node))
        out_pt = (node[0] + 1.6, node[1])
        line = elm.Line().at(node).to(out_pt)
        if out_label:
            line = line.label(out_label, loc="right")
        d.add(line)
        d.add(elm.Line().at(q2.emitter).down(0.5))
        d.add(elm.Ground())
        title_pt = (q1.collector[0], q1.collector[1] + 1.5)
        if q2pins.get("C"):
            nets[q2pins["C"]] = node
        if q2pins.get("E"):
            nets[q2pins["E"]] = q2.emitter
    else:
        # Suiveur : collecteurs communs -> VCC, sortie sur l'émetteur de Q2 via Re.
        rs = _refs(result, ci, "R")
        re = _ref_on_net(rs, ci, q2pins.get("E"))
        if not re:
            re = _ref_passif_simple_vers_masse(ci, ("R",), q2pins.get("E"))
        if re:
            absorbed_refs.add(re)
        d.add(elm.Line().at(q1.collector).up(0.9))
        top = d.here
        d.add(elm.Line().at(q2.collector).toy(top[1]))
        d.add(elm.Line().tox(top[0]))
        d.add(elm.Line().at(top).up(0.4).label("VCC", loc="top"))
        ex, ey = q2.emitter
        out_pt = (ex + 1.6, ey)
        line = elm.Line().at(q2.emitter).to(out_pt)
        if out_label:
            line = line.label(out_label, loc="right")
        d.add(line)
        if re:
            _r_simple(d, re, ci, (ex, ey - 0.6), (ex, ey - 2.0), None)
            # halign="left" : le texte COMMENCE à l'ancre (côté droit du
            # zigzag) au lieu d'être centré dessus, sinon sa moitié gauche
            # traverse le symbole (audit fenêtre F1, ilot_chaine_darlington_ce).
            d.add(elm.Label().at((ex + 0.85, ey - 1.25))
                  .label(_texte_passif_simple(re, ci, "Re"),
                         fontsize=_SATELLITE_LABEL_FONTSIZE, halign="left"))
            d.add(elm.Line().at(q2.emitter).to((ex, ey - 0.6)))
            d.add(elm.Line().at((ex, ey - 2.0)).down(0.4))
            d.add(elm.Ground())
        title_pt = (top[0], top[1] + 1.2)
        if q2pins.get("E"):
            nets[q2pins["E"]] = out_pt

    if titre:
        _titre_montage(d, result, title_pt)
    return {"in": in_pt, "out": out_pt, "title": title_pt, "nets": nets,
            "absorbed_refs": absorbed_refs}


def _draw_porte_cmos(d, result, ci, origin=(3, 0), titre=True,
                     in_label=None, out_label=None):
    """@brief Délégation au module dédié (import LAZY : pas de cycle)."""
    from gui import logic_schematic
    return logic_schematic.dessiner_porte(d, result, ci, origin=origin,
                                          titre=titre, in_label=in_label,
                                          out_label=out_label)


# ── Pattern registry ──────────────────────────────────────────────────────────

## @brief Registre {nom de circuit -> fonction de dessin schemdraw}.
_DRAWERS = {
    "Impédance Z":                       _draw_impedance,
    "Redresseur simple alternance":      _draw_half_wave,
    "Détecteur de crête":                _draw_peak_detector,
    "Pont redresseur (Graetz)":          _draw_bridge_rectifier,
    "Diode de roue libre":               _draw_flyback,
    "Diode de protection ESD":           _draw_esd,
    "Amplificateur inverseur (AOP)":     _draw_inverting_amp,
    "Ampli inverseur + boost HF (AOP)":  _draw_inverting_amp,
    "Ampli inverseur + action intégrale (AOP)": _draw_inverting_amp,
    "Amplificateur non-inverseur (AOP)": _draw_non_inverting_amp,
    "Suiveur de tension (AOP)":          _draw_follower,
    "Intégrateur (AOP)":                 _draw_integrator,
    "Dérivateur (AOP)":                  _draw_differentiator,
    "Comparateur (AOP)":                 _draw_comparator,
    "Bascule de Schmitt (AOP)":          _draw_schmitt,
    "Amplificateur différentiel (AOP)":  _draw_differential_amp,
    "Amplificateur sommateur (AOP)":     _draw_summing_amp,
    "Commande de relais":                _draw_relay_driver,
    "Transistor en commutation":         _draw_bjt_switch,
    "Amplificateur émetteur commun":     _draw_common_emitter,
    "Miroir de courant BJT":             _draw_current_mirror,
    "MOSFET en commutation":             _draw_mosfet_switch,
    "MOSFET haute-tension (côté haut)": _draw_high_side_mosfet,
    "Collecteur commun (suiveur d'émetteur)": _draw_suiveur_emetteur,
    "Étage push-pull":                   _draw_push_pull,
    "Paire Darlington":                  _draw_darlington,
    "Inverseur (CMOS)":                  _draw_porte_cmos,
    "Porte NAND (CMOS)":                 _draw_porte_cmos,
    "Porte NOR (CMOS)":                  _draw_porte_cmos,
}
