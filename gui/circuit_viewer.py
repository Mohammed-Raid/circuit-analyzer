"""
@file circuit_viewer.py
@brief Visualiseur de schémas (schemdraw 0.22 + backend matplotlib TkAgg).

Chaque pattern de circuit détecté a sa propre fonction de dessin, enregistrée
dans _DRAWERS. Les fonctions _draw_* reçoivent toutes (d, result, ci) :
  @param d Dessin schemdraw en cours.
  @param result Match du circuit détecté.
  @param ci Dict {ref -> infos composant} (comp_info).
"""
import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import schemdraw
import schemdraw.elements as elm
from circuit_analyzer.patterns.base import (
    is_ground_net,
    is_power_net,
    is_protective_earth_net,
)

UI_BG   = "#0f172a"
UI_CARD = "#1e293b"
SCH_BG  = "#fafafa"   # light background — standard for schematics

_COMP_COLORS = {
    "R": "#1d4ed8", "C": "#0891b2", "L": "#059669",
    "D": "#dc2626", "Q": "#7c3aed", "M": "#6d28d9",
    "U": "#b45309", "F": "#374151",
}


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
            units.append({
                "ref": f"Z{z_index}", "type": "Z", "value": "",
                "pins": {"1": u, "2": v},
                "symbol": "impedance", "refs": refs, "composition": composition,
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

def show_circuit(result: dict, comp_info: dict, parent=None):
    """@brief Ouvre une fenêtre affichant le schéma d'un circuit détecté.

    @param result Match du circuit détecté (type, composants, nœuds).
    @param comp_info Dict {ref -> {type, value, pins}} des composants.
    @param parent Fenêtre parente (optionnel).
    @return None
    """
    name    = result["circuit_type"]
    drawer  = _DRAWERS.get(name)

    popup = ctk.CTkToplevel(parent)
    popup.title(f"Schéma — {name}")
    popup.geometry("720x540")
    popup.configure(fg_color=UI_BG)
    popup.grab_set()

    # Header
    hdr = ctk.CTkFrame(popup, fg_color=UI_CARD, corner_radius=0, height=54)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    ctk.CTkLabel(hdr, text=f"⚡  {name}",
                 font=ctk.CTkFont("Segoe UI", 14, "bold"),
                 text_color="#f1f5f9").pack(side="left", padx=18, pady=14)

    # Component chips
    chips = ctk.CTkFrame(popup, fg_color=UI_BG)
    chips.pack(fill="x", padx=14, pady=(8, 2))
    ctk.CTkLabel(chips, text="Composants :",
                 font=ctk.CTkFont("Segoe UI", 10),
                 text_color="#64748b").pack(side="left")
    for ref in result["components"]:
        info = comp_info.get(ref, {})
        val  = info.get("value", "")
        typ  = info.get("type", "?")
        txt  = f" {ref} {val} ".strip()
        color = _COMP_COLORS.get(typ, "#374151")
        ctk.CTkLabel(chips, text=txt,
                     font=ctk.CTkFont("Consolas", 10, "bold"),
                     fg_color=color, text_color="#ffffff",
                     corner_radius=4).pack(side="left", padx=3)

    # Schematic area
    fig = _make_fig(result, comp_info, drawer)
    canvas_frame = ctk.CTkFrame(popup, fg_color=SCH_BG, corner_radius=10)
    canvas_frame.pack(fill="both", expand=True, padx=14, pady=(4, 0))

    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().configure(bg=SCH_BG, highlightthickness=0)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

    # Bottom bar
    bar = ctk.CTkFrame(popup, fg_color=UI_CARD, corner_radius=0, height=44)
    bar.pack(fill="x", side="bottom")
    bar.pack_propagate(False)
    ctk.CTkButton(bar, text="💾  Exporter PNG",
                  width=140, height=30, corner_radius=6,
                  font=ctk.CTkFont("Segoe UI", 11),
                  fg_color="#1d4ed8", hover_color="#2563eb",
                  command=lambda: _export(fig, name, popup)).pack(
                      side="left", padx=12, pady=7)
    ctk.CTkButton(bar, text="Fermer",
                  width=90, height=30, corner_radius=6,
                  font=ctk.CTkFont("Segoe UI", 11),
                  fg_color="#374151", hover_color="#4b5563",
                  command=popup.destroy).pack(side="right", padx=12, pady=7)


# ── Figure builder ────────────────────────────────────────────────────────────

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
    if not refs:
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
    if not refs:
        return None
    sous = construire_graphe([raw[r] for r in refs])
    bornes = impedance.bornes_possibles(sous)
    if "VIN" not in bornes or "VOUT" not in bornes:
        return None
    pont = impedance.detecter_pont(sous, "VIN", "VOUT")
    if pont is None:
        return None
    return pont, sous.graph["components"]


def show_island(ilot: dict, graph, comp_info: dict, parent=None, results=None):
    """Ouvre une fenetre affichant le schema reel d'un ilot."""
    model = _build_island_model(ilot, graph, comp_info)
    name = model["label"]

    popup = ctk.CTkToplevel(parent)
    popup.title(f"Schema ilot - {name}")
    popup.geometry("820x580")
    popup.configure(fg_color=UI_BG)
    popup.grab_set()

    hdr = ctk.CTkFrame(popup, fg_color=UI_CARD, corner_radius=0, height=54)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    ctk.CTkLabel(hdr, text=f"Schema ilot - {name}",
                 font=ctk.CTkFont("Segoe UI", 14, "bold"),
                 text_color="#f1f5f9").pack(side="left", padx=18, pady=14)

    chips = ctk.CTkFrame(popup, fg_color=UI_BG)
    chips.pack(fill="x", padx=14, pady=(8, 2))
    ctk.CTkLabel(chips, text="Composants :",
                 font=ctk.CTkFont("Segoe UI", 10),
                 text_color="#64748b").pack(side="left")
    for comp in model["components"]:
        txt = f" {comp['ref']} {comp.get('value', '')} ".strip()
        color = _COMP_COLORS.get(comp.get("type"), "#374151")
        ctk.CTkLabel(chips, text=txt,
                     font=ctk.CTkFont("Consolas", 10, "bold"),
                     fg_color=color, text_color="#ffffff",
                     corner_radius=4).pack(side="left", padx=3)

    _sp = _arbre_serie_parallele_ilot(ilot, graph)
    _pont = _pont_ilot(ilot, graph) if _sp is None else None
    if _sp is not None:
        from gui import impedance_schematic
        _arbre, _comps = _sp
        fig = impedance_schematic.dessiner(_arbre, "VIN", "VOUT", _comps)
    elif _pont is not None:
        from gui import impedance_schematic
        _pont_struct, _comps = _pont
        fig = impedance_schematic.dessiner_pont(_pont_struct, _comps)
    else:
        matches = _matches_for_island(ilot, results)
        fig = _make_island_fig(model, matches=matches)
    canvas_frame = ctk.CTkFrame(popup, fg_color=SCH_BG, corner_radius=10)
    canvas_frame.pack(fill="both", expand=True, padx=14, pady=(4, 0))

    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().configure(bg=SCH_BG, highlightthickness=0)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

    def _on_click(event):
        # Clic dans une zone de Z -> ouvre le sous-schema des R/L/C qui le composent.
        if event.xdata is None or event.ydata is None:
            return
        for x0, x1, y0, y1, refs, composition in getattr(fig, "_z_hitboxes", []):
            if x0 <= event.xdata <= x1 and y0 <= event.ydata <= y1:
                show_dipole_detail(refs, composition, graph, comp_info, popup)
                return

    canvas.mpl_connect("button_press_event", _on_click)

    bar = ctk.CTkFrame(popup, fg_color=UI_CARD, corner_radius=0, height=44)
    bar.pack(fill="x", side="bottom")
    bar.pack_propagate(False)
    ctk.CTkButton(bar, text="Exporter PNG",
                  width=140, height=30, corner_radius=6,
                  font=ctk.CTkFont("Segoe UI", 11),
                  fg_color="#1d4ed8", hover_color="#2563eb",
                  command=lambda: _export(fig, name, popup)).pack(
                      side="left", padx=12, pady=7)
    ctk.CTkButton(bar, text="Fermer",
                  width=90, height=30, corner_radius=6,
                  font=ctk.CTkFont("Segoe UI", 11),
                  fg_color="#374151", hover_color="#4b5563",
                  command=popup.destroy).pack(side="right", padx=12, pady=7)


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
    model = _build_dipole_model(refs, graph, comp_info, label=titre)
    fig = _make_island_fig(model)

    popup = ctk.CTkToplevel(parent)
    popup.title(titre)
    popup.geometry("560x460")
    popup.configure(fg_color=UI_BG)
    popup.grab_set()

    hdr = ctk.CTkFrame(popup, fg_color=UI_CARD, corner_radius=0, height=48)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    ctk.CTkLabel(hdr, text=f"Composition de l'impedance : {composition}",
                 font=ctk.CTkFont("Segoe UI", 13, "bold"),
                 text_color="#f1f5f9").pack(side="left", padx=18, pady=12)

    canvas_frame = ctk.CTkFrame(popup, fg_color=SCH_BG, corner_radius=10)
    canvas_frame.pack(fill="both", expand=True, padx=14, pady=10)
    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().configure(bg=SCH_BG, highlightthickness=0)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

    bar = ctk.CTkFrame(popup, fg_color=UI_CARD, corner_radius=0, height=44)
    bar.pack(fill="x", side="bottom")
    bar.pack_propagate(False)
    ctk.CTkButton(bar, text="Exporter PNG",
                  width=140, height=30, corner_radius=6,
                  font=ctk.CTkFont("Segoe UI", 11),
                  fg_color="#1d4ed8", hover_color="#2563eb",
                  command=lambda: _export(fig, titre, popup)).pack(
                      side="left", padx=12, pady=7)
    ctk.CTkButton(bar, text="Fermer",
                  width=90, height=30, corner_radius=6,
                  font=ctk.CTkFont("Segoe UI", 11),
                  fg_color="#374151", hover_color="#4b5563",
                  command=popup.destroy).pack(side="right", padx=12, pady=7)


def _make_fig(result, comp_info, drawer_fn):
    """@brief Construit la figure matplotlib du schéma (ou un texte de repli).

    @param result Match du circuit détecté.
    @param comp_info Dict des infos composants.
    @param drawer_fn Fonction de dessin dédiée, ou None.
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

    if drawer_fn:
        try:
            with schemdraw.Drawing(canvas=ax, show=False) as d:
                d.config(fontsize=11, inches_per_unit=0.5)
                drawer_fn(d, result, comp_info)
        except Exception as e:
            ax.text(0.5, 0.5, f"Schéma non disponible\n{e}",
                    ha="center", va="center",
                    transform=ax.transAxes,
                    fontsize=12, color="#64748b")
    else:
        ax.text(0.5, 0.6, result["circuit_type"],
                ha="center", va="center", transform=ax.transAxes,
                fontsize=14, fontweight="bold", color="#1e293b")
        ax.text(0.5, 0.45,
                "  ·  ".join(result["components"]),
                ha="center", va="center", transform=ax.transAxes,
                fontsize=11, color="#64748b", fontfamily="monospace")

    # Marge autour du tracé : évite que les étiquettes (labels de bornes,
    # composition d'une Impédance Z) soient rognées par le bord de la figure.
    ax.margins(0.15)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        pass
    return fig


def _make_island_fig(model, matches=None):
    """@brief Construit un vrai rendu schematique d'un ilot.

    Le rendu n'utilise plus des bulles composant/net. Il fabrique un petit
    plan electrique : chemin principal gauche-droite, derives vers rails, puis
    symboles generiques pour les composants multi-broches.

    @param model Modele d'ilot (cf. _build_island_model).
    @return matplotlib.figure.Figure Figure prete a afficher/exporter.
    """
    components = model["components"]
    plan = _build_island_schematic_plan(model)
    width = max(8.0, 1.4 * max(2, len(plan["columns"])) + 6.0)
    # hauteur proportionnelle a l'extent vertical reel (bandes), pas au nombre de
    # lignes : le compactage reduit le nombre de bandes, donc la figure raccourcit.
    yvals = [r["y"] for r in plan["rows"]] or [0.0]
    height = max(4.8, 0.7 * (max(yvals) - min(yvals)) + 3.0)
    fig = Figure(figsize=(min(20.0, width), min(15.0, height)))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")

    hitboxes = []
    fig._z_hitboxes = hitboxes   # zones cliquables des Z (renseignees par le drawer)

    if not components:
        ax.text(0.5, 0.5, "Ilot vide", ha="center", va="center",
                transform=ax.transAxes, fontsize=13, color="#64748b")
        return fig

    try:
        with schemdraw.Drawing(canvas=ax, show=False) as d:
            d.config(fontsize=10, inches_per_unit=0.5)
            _draw_island_schematic(d, plan, hitboxes)
    except Exception as exc:
        ax.text(0.5, 0.56, model.get("label", "Ilot"),
                ha="center", va="center", transform=ax.transAxes,
                fontsize=14, fontweight="bold", color="#1e293b")
        ax.text(0.5, 0.44, f"Schema automatique indisponible\n{exc}",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=10, color="#64748b")

    caption = plan["caption"]
    if hitboxes:
        caption += "   ·   cliquez un Z pour voir sa composition (R/L/C)"
    ax.text(0.01, 0.01, caption, transform=ax.transAxes,
            fontsize=8, color="#64748b", va="bottom", ha="left")
    ax.margins(0.16)
    fig.subplots_adjust(left=0.03, right=0.97, top=0.96, bottom=0.06)
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
}

_BUS = "#475569"
_WIRE = "#1e293b"
_LBL_OFST = 0.25   # decalage des labels de net pour les decoller des symboles


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

    def _hit(xa, xb):
        # zone cliquable d'un Z (un peu elargie) pour ouvrir sa composition.
        if hitboxes is not None and row["symbol"] == "impedance":
            hitboxes.append((min(xa, xb) - 0.3, max(xa, xb) + 0.3, y - 0.5, y + 0.5,
                             row.get("refs", []), row.get("composition", "")))

    if x1 is not None and x2 is not None and x1 != x2:
        left, right = sorted((x1, x2))
        mid = (left + right) / 2
        slen = min(1.6, max(0.8, right - left - 0.6))
        d += elm.Dot().at((left, y)).color(_WIRE)
        d += elm.Line().at((left, y)).tox(mid - slen / 2).color(_WIRE)
        d += element().at((mid - slen / 2, y)).right(slen).label(label, loc=label_loc)
        d += elm.Line().tox(right).color(_WIRE)
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
        d += element().right(1.4).label(label, loc=label_loc)
        d += elm.Line().right(0.35).color(_WIRE)
        if not _is_not_connected(stub_net):
            _draw_net_end(d, stub_net)
        _hit(col_x + 0.3, col_x + 1.7)
        return

    # composant isole (deux moignons) : symbole HORIZONTAL + deux bornes etiquetees.
    # On ne met PAS de drapeau masse/alim ici : les deux bouts sont les bornes du
    # dipole (ses ports), pas des rails distribues -> bornes nommees, dipole droit.
    d += element().at((0.0, y)).right(1.4).label(label, loc=label_loc)
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
        op = elm.Opamp().at((device_x, y)).right().label(row["ref"], loc="center")
        d += op
        block_right = tuple(op.out)          # pointe droite du triangle
    else:
        d += elm.Rect(w=1.8, h=0.8).at((device_x, y)).label(row["ref"])
        block_right = (device_x + 0.9, y)    # bord droit du bloc

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
    value = comp.get("value") or ""
    return f"{comp['ref']}\n{value}" if value else comp["ref"]


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
        fig.savefig(path, dpi=150, bbox_inches="tight",
                    facecolor=SCH_BG, edgecolor="none")


# ── Label helpers ─────────────────────────────────────────────────────────────

def _lbl(ref, comp_info):
    """@brief Libellé d'un composant : « ref\\nvaleur » ou « ref » si pas de valeur.

    @param ref Référence du composant.
    @param comp_info Dict des infos composants.
    @return str Libellé prêt à afficher.
    """
    val = comp_info.get(ref, {}).get("value", "")
    return f"{ref}\n{val}" if val else ref

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

def _draw_impedance(d, result, ci):
    """@brief Dessine une « Impédance Z » : boîte Z entre ses deux bornes.

    Le libellé est la composition (ex. « (R1+R2)//C1 »), sinon la liste des
    composants. Les nets sont annotés à gauche et à droite.
    """
    nets = [n for n in result.get("nodes", []) if n]
    gauche = nets[0] if nets else ""
    droite = nets[1] if len(nets) > 1 else ""
    compo = result.get("composition") or " // ".join(result.get("components", []))
    d += elm.Dot().label(gauche, loc="left")
    d += elm.Line().right(0.6)
    d += elm.ResistorIEC().right().label("Z", loc="top").label(compo, loc="bottom")
    d += elm.Line().right(0.6)
    d += elm.Dot().label(droite, loc="right")


def _draw_half_wave(d, result, ci):
    """@brief Dessine le schéma « Redresseur simple alternance »."""
    diode = _ref(result, ci, "D"); r = _ref(result, ci, "R")
    d += elm.Diode().right().label(_lbl(diode, ci), loc="top")
    d.push()
    d += elm.Resistor().down().label(_lbl(r, ci), loc="right")
    d += elm.Ground()
    d.pop()
    d += elm.Line().right(1.5).label("DC", loc="right")


def _draw_peak_detector(d, result, ci):
    """@brief Dessine le schéma « Détecteur de crête »."""
    diode = _ref(result, ci, "D"); c = _ref(result, ci, "C")
    d += elm.Diode().right().label(_lbl(diode, ci), loc="top")
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
    d.add(elm.Diode().up().at((0, 0)))   # D3
    d.add(elm.Dot().label("AC1", loc="left"))
    d.add(elm.Diode().up())              # D1
    dc_plus_y = d.here[1]
    d.add(elm.Dot().label("DC+", loc="left"))

    # ── Right column ──────────────────────────────────────────────
    d.add(elm.Dot().at((COL, 0)).label("DC−", loc="right"))
    d.add(elm.Diode().up().at((COL, 0)))  # D4
    d.add(elm.Dot().label("AC2", loc="right"))
    d.add(elm.Diode().up())               # D2
    d.add(elm.Dot().label("DC+", loc="right"))

    # ── Connecting rails ──────────────────────────────────────────
    d.add(elm.Line().at((0, 0)).right(COL))                       # DC- rail
    d.add(elm.Line().at((0, dc_plus_y)).right(COL))               # DC+ rail


def _draw_flyback(d, result, ci):
    """@brief Dessine le schéma « Diode de roue libre »."""
    diode = result["components"][0]
    d += elm.Line().right(0.5).label("SW", loc="start")
    d += elm.Diode().right().label(_lbl(diode, ci), loc="top")
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
    d.add(elm.Diode().right().label(_lbl(diode, ci), loc="top"))
    d.add(elm.Line().down(1.5))
    d.add(elm.Ground())


# ── AOP patterns ─────────────────────────────────────────────────────────────

def _draw_inverting_amp(d, result, ci):
    """@brief Dessine le schéma « Amplificateur inverseur (AOP) »."""
    rs = _refs(result, ci, "R")
    # Pattern returns [U, feedback_r, input_r] — rf is first, rin is second
    rf  = rs[0] if rs else "Rf"
    rin = rs[1] if len(rs) > 1 else "Rin"

    op = d.add(elm.Opamp().anchor("in1").at((4.5, 0)))

    d.add(elm.Resistor().at(op.in1).left().label(_lbl(rin, ci), loc="top"))
    d.add(elm.Dot().label("IN", loc="left"))
    mid_pt = op.in1
    d.add(elm.Line().at(op.in2).left(1))
    d.add(elm.Ground())

    # Feedback: go up, then tox to align with op.out, then toy down to op.out
    above = (mid_pt[0], mid_pt[1] + 1.5)
    d.add(elm.Line().at(mid_pt).up(1.5))
    d.add(elm.Resistor().at(above).right().tox(op.out[0])
          .label(_lbl(rf, ci), loc="top"))
    d.add(elm.Line().toy(op.out[1]))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


def _draw_non_inverting_amp(d, result, ci):
    """@brief Dessine le schéma « Amplificateur non-inverseur (AOP) »."""
    rs = _refs(result, ci, "R")
    rf  = rs[0] if rs else "Rf"
    rg  = rs[1] if len(rs) > 1 else "Rg"

    op = d.add(elm.Opamp().anchor("in2").at((4.5, 0)))
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


def _draw_follower(d, result, ci):
    """@brief Dessine le schéma « Suiveur de tension (AOP) »."""
    op = d.add(elm.Opamp().anchor("in2").at((4.5, 0)))
    d.add(elm.Line().at(op.in2).left(1.2).label("IN", loc="left"))

    out_pt = op.out
    in1_pt = op.in1   # IN− (upper pin)

    # Feedback routes ABOVE the opamp to avoid crossing IN+:
    # OUT → right → up above opamp → left back to IN− x → down to IN−
    top_y = in1_pt[1] + 1.2
    d.add(elm.Line().at(out_pt).right(0.6))
    d.add(elm.Line().toy(top_y))
    d.add(elm.Line().tox(in1_pt[0]))
    d.add(elm.Line().toy(in1_pt[1]))
    d.add(elm.Dot().at(out_pt))
    d.add(elm.Line().at(out_pt).right(1).label("OUT", loc="right"))


def _draw_integrator(d, result, ci):
    """@brief Dessine le schéma « Intégrateur (AOP) »."""
    rs = _refs(result, ci, "R"); cs = _refs(result, ci, "C")
    r = rs[0] if rs else "R"
    c = cs[0] if cs else "C"

    op = d.add(elm.Opamp().anchor("in1").at((4.5, 0)))
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
    """@brief Dessine le schéma « Dérivateur (AOP) »."""
    cs = _refs(result, ci, "C"); rs = _refs(result, ci, "R")
    c = cs[0] if cs else "C"
    r = rs[0] if rs else "R"

    op = d.add(elm.Opamp().anchor("in1").at((4.5, 0)))
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


def _draw_comparator(d, result, ci):
    """@brief Dessine le schéma « Comparateur (AOP) »."""
    op = d.add(elm.Opamp().anchor("center").at((4.5, 0)))
    d.add(elm.Line().at(op.in2).left(1.2).label("IN+", loc="left"))
    d.add(elm.Line().at(op.in1).left(1.2).label("IN−", loc="left"))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


def _draw_schmitt(d, result, ci):
    """@brief Dessine le schéma « Bascule de Schmitt (AOP) »."""
    rs = _refs(result, ci, "R")
    rf = rs[0] if rs else "Rf"

    op = d.add(elm.Opamp().anchor("center").at((4.5, 0)))
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


def _draw_differential_amp(d, result, ci):
    """@brief Dessine le schéma « Amplificateur différentiel (AOP) »."""
    rs = _refs(result, ci, "R")
    # Pattern returns [U, r_inp_to_gnd, r_inp_from_src, r_inm_feedback, r_inm_from_src]
    rg  = rs[0] if len(rs) > 0 else "Rg"   # IN+ → GND  (bias/gain)
    r1  = rs[1] if len(rs) > 1 else "R1"   # source → IN+ (input)
    rf  = rs[2] if len(rs) > 2 else "Rf"   # IN- → OUT  (feedback)
    r2  = rs[3] if len(rs) > 3 else "R2"   # source → IN- (input)

    op = d.add(elm.Opamp().anchor("center").at((6.0, 0)))

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
    rs = _refs(result, ci, "R")
    rf = rs[0] if rs else "Rf"
    inputs = rs[1:] if len(rs) > 1 else ["Ra", "Rb"]
    n = min(len(inputs), 3)

    op = d.add(elm.Opamp().anchor("in1").at((5, 0)))
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

def _draw_bjt_switch(d, result, ci):
    """@brief Dessine le schéma « Transistor en commutation »."""
    q = _ref(result, ci, "Q"); r = _ref(result, ci, "R")
    t = d.add(elm.BjtNpn().at((3, 0)))
    d.add(elm.Resistor().at(t.base).left().label(_lbl(r, ci), loc="top"))
    d.add(elm.Dot().label("IN", loc="left"))
    d.add(elm.Line().at(t.collector).up(1).label("LOAD", loc="right"))
    d.add(elm.Line().at(t.emitter).down(0.5))
    d.add(elm.Ground())


def _draw_common_emitter(d, result, ci):
    """@brief Dessine le schéma « Amplificateur émetteur commun »."""
    q = _ref(result, ci, "Q")
    rs = _refs(result, ci, "R")
    # Pattern returns [Q, r_at_collector, r_at_base] → rs[0]=Rc, rs[1]=Rb
    q_pins = ci.get(q, {}).get("pins", {})
    rc = _ref_on_net(rs, ci, q_pins.get("C"), rs[0] if rs else "Rc")
    remaining = [r for r in rs if r != rc]
    rb = _ref_on_net(remaining, ci, q_pins.get("B"), remaining[0] if remaining else "Rb")
    t = d.add(elm.BjtNpn().at((3, 0)))
    d.add(elm.Resistor().at(t.base).left().label(_lbl(rb, ci), loc="top"))
    d.add(elm.Dot().label("IN", loc="left"))
    # loc="bot" on UP element = physical right side at midpoint; no overlap with VCC at top-end
    d.add(elm.Resistor().at(t.collector).up(1.15).label(_lbl(rc, ci), loc="bot"))
    d.add(elm.Dot())
    d.add(elm.Line().up(0.45).label("VCC", loc="top"))
    d.add(elm.Line().at(t.emitter).down(0.5))
    d.add(elm.Ground())
    d.add(elm.Line().at(t.collector).right(1.5).label("OUT", loc="right"))


def _draw_mosfet_switch(d, result, ci):
    """@brief Dessine le schéma « MOSFET en commutation »."""
    m = _ref(result, ci, "M"); r = _ref(result, ci, "R")
    t = d.add(elm.NFet().at((3, 0)))
    # In schemdraw 0.22, NFet gate is on the RIGHT side — resistor goes right (no body overlap)
    d.add(elm.Resistor().at(t.gate).right().label(_lbl(r, ci), loc="top"))
    d.add(elm.Dot().label("IN", loc="right"))
    d.add(elm.Line().at(t.drain).up(1).label("LOAD", loc="right"))
    d.add(elm.Line().at(t.source).down(0.5))
    d.add(elm.Ground())


def _draw_high_side_mosfet(d, result, ci):
    """@brief Dessine le schéma « MOSFET haute-tension (côté haut) »."""
    m = _ref(result, ci, "M")
    r = _ref(result, ci, "R")
    t = d.add(elm.NFet().at((3, 0)))
    # Gate resistor goes right (gate is on right in NFet 0.22)
    d.add(elm.Resistor().at(t.gate).right().label(_lbl(r, ci), loc="top"))
    d.add(elm.Dot().label("IN", loc="right"))
    # Drain at top → VCC power rail
    d.add(elm.Line().at(t.drain).up(1))
    d.add(elm.Dot().label("VCC", loc="right"))
    # Source at bottom → load (not GND)
    d.add(elm.Line().at(t.source).down(1))
    d.add(elm.Dot().label("LOAD", loc="left"))


def _draw_relay_driver(d, result, ci):
    """@brief Dessine le schéma « Commande de relais » (K + Q/M + diode flyback)."""
    k   = _ref(result, ci, "K")
    qs  = _refs(result, ci, "Q")
    ms  = _refs(result, ci, "M")
    rbs = _refs(result, ci, "R")
    dbs = _refs(result, ci, "D")

    use_mosfet = not qs and bool(ms)
    t = d.add((elm.NFet() if use_mosfet else elm.BjtNpn()).at((3.5, 0)))

    ctrl_pin = t.gate if use_mosfet else t.base
    coll_pin = t.drain if use_mosfet else t.collector
    emit_pin = t.source if use_mosfet else t.emitter
    ctrl_lbl = "VG" if use_mosfet else "CMD"

    # Contrôle : résistance de base ou ligne directe
    if rbs:
        d.add(elm.Resistor().at(ctrl_pin).left().label(_lbl(rbs[0], ci), loc="top"))
        d.add(elm.Dot().label(ctrl_lbl, loc="left"))
    else:
        d.add(elm.Line().at(ctrl_pin).left(1).label(ctrl_lbl, loc="left"))

    # Bobine du relais : collecteur → haut → VCC
    coil_len = 1.8
    d.add(elm.Inductor2(nturns=3).at(coll_pin).up(coil_len).label(_lbl(k, ci), loc="left"))
    coil_top = d.here
    d.add(elm.Dot().at(coil_top))
    d.add(elm.Line().up(0.3).label("VCC", loc="top"))

    # Diode flyback : anode côté collecteur, cathode côté VCC (protection inductive)
    diode_lbl = _lbl(dbs[0], ci) if dbs else ""
    d.add(elm.Line().at(coll_pin).right(1.6))
    d.add(elm.Diode().up(coil_len).label(diode_lbl, loc="right"))
    d.add(elm.Line().tox(coil_top[0]))

    # Émetteur → GND
    d.add(elm.Line().at(emit_pin).down(0.5))
    d.add(elm.Ground())


def _draw_current_mirror(d, result, ci):
    """@brief Dessine le schéma « Miroir de courant BJT »."""
    qs = _refs(result, ci, "Q")
    t1 = d.add(elm.BjtNpn().at((1.5, 0)))
    t2 = d.add(elm.BjtNpn().at((4.5, 0)))

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
}
