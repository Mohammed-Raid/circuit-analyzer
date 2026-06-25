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
import tkinter as tk
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
    view_w, view_h = viewport
    px, py = pointer
    ox, oy = canvas_origin

    scale_x = new_w / old_w if old_w else 1.0
    scale_y = new_h / old_h if old_h else 1.0
    target_x = (ox + px) * scale_x - px
    target_y = (oy + py) * scale_y - py
    max_x = max(1, new_w - view_w)
    max_y = max(1, new_h - view_h)
    fx = max(0.0, min(1.0, target_x / max_x))
    fy = max(0.0, min(1.0, target_y / max_y))
    return fx, fy


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

def _texte_gain(result, graph):
    """@brief Texte du gain pour l'entête : symbolique + numérique si évaluable.

    @param result Match (porte 'gain' symbolique et éventuellement 'impedances').
    @param graph Graphe d'origine (pour évaluer numériquement), ou None.
    @return str|None « Av = −Zf/Zin = -20 » (résistif) / « … (|Av|≈3.2 à 1000 Hz) »
            (réactif) / « Av = −Zf/Zin » si non évaluable, ou None si pas de gain.
    """
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
    """@brief Curseur « main » au survol d'une boîte Z cliquable (découvrabilité)."""
    widget = canvas.get_tk_widget()
    def _on_motion(event):
        over = event.xdata is not None and event.ydata is not None and any(
            x0 <= event.xdata <= x1 and y0 <= event.ydata <= y1
            for x0, x1, y0, y1, *_ in getattr(fig, "_z_hitboxes", []))
        widget.configure(cursor="hand2" if over else "")
    canvas.mpl_connect("motion_notify_event", _on_motion)


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
    popup.configure(fg_color=UI_BG)
    popup.grab_set()

    # Header
    hdr = ctk.CTkFrame(popup, fg_color=UI_CARD, corner_radius=0, height=54)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    ctk.CTkLabel(hdr, text=f"⚡  {name}",
                 font=ctk.CTkFont("Segoe UI", 14, "bold"),
                 text_color="#f1f5f9").pack(side="left", padx=18, pady=14)
    _gain_txt = _texte_gain(result, graph)
    if _gain_txt:
        ctk.CTkLabel(hdr, text=_gain_txt,
                     font=ctk.CTkFont("Consolas", 12, "bold"),
                     text_color="#34d399").pack(side="right", padx=18)

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
    # Le drawer dédié ne sait représenter qu'UN seul composant actif. Si l'îlot en
    # contient plusieurs (cascade d'AOP, etc.), on laisse le layout générique les
    # dessiner tous au lieu de n'en montrer qu'un.
    actifs = [r for r in refs if len(getattr(raw.get(r), "pins", {}) or {}) > 2]
    if len(actifs) != 1:
        return None
    for m in _matches_for_island(ilot, results):
        ct = m.get("circuit_type")
        if ct in _DRAWERS and ct != "Impédance Z":
            return m
    return None


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


def show_island(ilot: dict, graph, comp_info: dict, parent=None, results=None):
    """Ouvre une fenetre affichant le schema reel d'un ilot."""
    model = _build_island_model(ilot, graph, comp_info)
    name = model["label"]

    popup = ctk.CTkToplevel(parent)
    popup.title(f"Schema ilot - {name}")
    popup.geometry("1000x600")
    popup.configure(fg_color=UI_BG)
    popup.grab_set()

    hdr = ctk.CTkFrame(popup, fg_color=UI_CARD, corner_radius=0, height=54)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    ctk.CTkLabel(hdr, text=f"Schema ilot - {name}",
                 font=ctk.CTkFont("Segoe UI", 14, "bold"),
                 text_color="#f1f5f9").pack(side="left", padx=18, pady=14)
    _principal_hdr = _circuit_principal_ilot(ilot, graph, results)
    _gain_txt = _texte_gain(_principal_hdr, graph) if _principal_hdr else None
    if _gain_txt:
        ctk.CTkLabel(hdr, text=_gain_txt,
                     font=ctk.CTkFont("Consolas", 12, "bold"),
                     text_color="#34d399").pack(side="right", padx=18)

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

    principal = _circuit_principal_ilot(ilot, graph, results)
    _sp = _arbre_serie_parallele_ilot(ilot, graph) if principal is None else None
    _pont = _pont_ilot(ilot, graph) if (principal is None and _sp is None) else None
    _chaine = _branches = None
    if principal is None and _sp is None and _pont is None:
        _chaine = _ordonner_montages_flux(_matches_for_island(ilot, results))
        if _chaine is None:                # pas linéaire -> essai DAG en couches (PID…)
            _branches = _layers_montages_flux(_matches_for_island(ilot, results))
    if principal is not None:
        # Îlot = montage actif détecté : on réutilise son drawer dédié (schéma
        # propre « AOP + Zin/Zf », hitboxes Z cliquables), pas le layout générique.
        fig = _make_fig(principal, comp_info, _DRAWERS[principal["circuit_type"]])
    elif _sp is not None:
        from gui import impedance_schematic
        _arbre, _comps = _sp
        fig = impedance_schematic.dessiner_bloc(_arbre, "VIN", "VOUT", _comps)
    elif _pont is not None:
        from gui import impedance_schematic
        _pont_struct, _comps = _pont
        fig = impedance_schematic.dessiner_pont(_pont_struct, _comps)
    elif _chaine is not None:
        # Îlot multi-AOP en chaîne : un seul grand schéma, étages reliés OUT->IN.
        fig = _make_chain_fig(_chaine, comp_info)
    elif _branches is not None:
        # Îlot multi-AOP branché (P/I/D parallèles -> sommateur…) : schéma en couches.
        fig = _make_branched_fig(_branches, comp_info)
    else:
        matches = _matches_for_island(ilot, results)
        fig = _make_island_fig(model, matches=matches)
    canvas_frame = ctk.CTkFrame(popup, fg_color=SCH_BG, corner_radius=10)
    canvas_frame.pack(fill="both", expand=True, padx=14, pady=(4, 0))

    # Vues larges (chaîne OU gros îlot-grille) : défilement horizontal à taille
    # native pour ne pas écraser le schéma dans le popup. Les petites vues
    # remplissent simplement le cadre.
    _defile = (_chaine is not None or _branches is not None
               or fig.get_size_inches()[0] > 11.0)
    if _defile:
        canvas = _pack_scrollable_figure(canvas_frame, fig)
    else:
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
    _suivre_curseur_z(canvas, fig)

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


def _pack_scrollable_figure(parent, fig):
    """@brief Affiche une figure a sa taille native dans un viewport scrollable."""
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
    for widget in (inner, canvas.get_tk_widget()):
        widget.bind("<MouseWheel>", _on_mousewheel)
        widget.bind("<ButtonPress-1>", _on_pan_start)
        widget.bind("<B1-Motion>", _on_pan_drag)
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
        fig = impedance_schematic.dessiner(arbre, "A", "B", comps)
    else:
        model = _build_dipole_model(refs, graph, comp_info, label=titre)
        fig = _make_island_fig(model)

    popup = ctk.CTkToplevel(parent)
    popup.title(titre)
    popup.geometry("760x560")
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

    fig._z_hitboxes = []   # zones cliquables des Z (renseignées par le drawer)
    if drawer_fn:
        try:
            with schemdraw.Drawing(canvas=ax, show=False) as d:
                d.config(fontsize=14, inches_per_unit=0.62)
                d._z_hitboxes = []
                drawer_fn(d, result, comp_info)
                fig._z_hitboxes = list(d._z_hitboxes)
                # Ajuster la figure au format réel du dessin : sinon le schéma
                # (large) est « letterboxé » dans une figure carrée -> petit, avec
                # de grandes bandes vides. On colle le format de la figure à celui
                # du tracé pour qu'il remplisse la fenêtre.
                try:
                    bb = d.get_bbox()
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
                    pass
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

    # Astuce de découvrabilité : si le schéma comporte des boîtes Z cliquables,
    # on l'indique (sinon l'utilisateur ne sait pas qu'il peut déplier les Z).
    if fig._z_hitboxes:
        ax.text(0.01, 0.01, "Astuce : cliquez une boîte Z pour voir le détail R/L/C",
                transform=ax.transAxes, fontsize=9, color="#64748b",
                va="bottom", ha="left")

    # Marge réduite : le tracé occupe presque toute la figure (lisibilité).
    ax.margins(0.06)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        pass
    return fig


def _make_chain_fig(ordered, comp_info):
    """@brief Figure d'une chaîne de montages connectés (vue îlot multi-AOP).

    Large par construction (un bloc par étage) : destinée à un conteneur à
    défilement horizontal. Hauteur bornée à 4.2" pour tenir dans la fenêtre.

    @param ordered Montages triés par flux (cf. _ordonner_montages_flux).
    @param comp_info Dict {ref -> {type, value}}.
    @return matplotlib.figure.Figure (porte fig._z_hitboxes).
    """
    fig = Figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")
    fig._z_hitboxes = []
    try:
        with schemdraw.Drawing(canvas=ax, show=False) as d:
            d.config(fontsize=12, inches_per_unit=0.5)
            d._z_hitboxes = []
            _draw_island_chain(d, ordered, ci=comp_info)
            fig._z_hitboxes = list(d._z_hitboxes)
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
                pass
    except Exception as e:
        ax.text(0.5, 0.5, f"Schéma non disponible\n{e}", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color="#64748b")
    if fig._z_hitboxes:
        ax.text(0.005, 0.01, "Astuce : cliquez une boîte Z pour voir le détail R/L/C",
                transform=ax.transAxes, fontsize=9, color="#64748b", va="bottom", ha="left")
    ax.margins(0.04)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        pass
    return fig


def _make_branched_fig(layers, comp_info):
    """@brief Figure d'un îlot multi-AOP branché (DAG en couches, cf.
    _layers_montages_flux). Large et haute -> conteneur à défilement.

    @param layers list[list[match]] couches ordonnées.
    @param comp_info Dict {ref -> {type, value}}.
    @return matplotlib.figure.Figure (porte fig._z_hitboxes).
    """
    fig = Figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")
    fig._z_hitboxes = []
    try:
        with schemdraw.Drawing(canvas=ax, show=False) as d:
            d.config(fontsize=12, inches_per_unit=0.5)
            d._z_hitboxes = []
            _draw_branched_chain(d, layers, ci=comp_info)
            fig._z_hitboxes = list(d._z_hitboxes)
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
                pass
    except Exception as e:
        ax.text(0.5, 0.5, f"Schéma non disponible\n{e}", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color="#64748b")
    if fig._z_hitboxes:
        ax.text(0.005, 0.01, "Astuce : cliquez une boîte Z pour voir le détail R/L/C",
                transform=ax.transAxes, fontsize=9, color="#64748b", va="bottom", ha="left")
    ax.margins(0.04)
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


def _ordonner_montages_flux(matches):
    """@brief Ordonne des montages AOP par flux de signal (OUT(N) -> IN(N+1)).

    Pour chaque montage : out_net = net de la broche OUT (= nodes[-1]) ; in_net =
    nœud extérieur de Zin si présent (inverseur/intégrateur/dérivateur), sinon le
    net IN+ (= nodes[0], non-inverseur/suiveur). On relie i->j quand
    out_net(i) == in_net(j), puis on suit la chaîne depuis l'unique étage dont
    l'entrée n'est alimentée par aucun autre.

    @param matches Liste des matches de montages d'un même îlot.
    @return list[dict] | None Montages triés entrée->sortie, ou None si ce n'est
            pas une chaîne linéaire unique couvrant tous les montages.
    """
    if len(matches) < 2:
        return None

    def out_net(m):
        return m["nodes"][-1]

    def in_net(m):
        imp = m.get("impedances") or {}
        zin = imp.get("Zin")
        # Zin unique (dict) = entrée chaînable ; Zin liste (sommateur multi-entrées)
        # ou absent (non-inverseur/suiveur) -> on retombe sur le net IN+.
        if isinstance(zin, dict):
            return zin["nodes"][1]
        return m["nodes"][0]

    par_in = {}
    for m in matches:
        par_in.setdefault(in_net(m), []).append(m)
    outs = {out_net(m) for m in matches}

    # Tête de chaîne : un montage dont l'entrée n'est la sortie d'aucun autre.
    tetes = [m for m in matches if in_net(m) not in outs]
    if len(tetes) != 1:
        return None

    ordre = []
    vus = set()
    courant = tetes[0]
    while courant is not None and id(courant) not in vus:
        ordre.append(courant)
        vus.add(id(courant))
        suivants = par_in.get(out_net(courant), [])
        if len(suivants) > 1:
            return None                      # bifurcation : pas une chaîne linéaire
        courant = suivants[0] if suivants else None

    if len(ordre) != len(matches):
        return None                          # tous les montages ne sont pas chaînés
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


def _layers_montages_flux(matches):
    """@brief Ordonne des montages AOP branchés en couches (DAG par flux de signal).

    Pour les îlots non linéaires (ex. PID : entrée → P/I/D parallèles → sommateur →
    buffer). Arête producteur→consommateur quand out_net(producteur) ∈ in_nets(conso).
    Les étages ayant une entrée *externe* (non produite par un autre étage) sont des
    sources (couche 0) ; un back-edge vers une source est ignoré (tolère les boucles
    issues d'une détection imparfaite). Profondeur = plus long chemin depuis une source.

    @param matches Matches d'un même îlot (les non-AOP sont ignorés).
    @return list[list[match]] couches ordonnées (≥ 2), ou None si pas exploitable.
    """
    stages = [m for m in matches if "(AOP)" in m.get("circuit_type", "")]
    if len(stages) < 2:
        return None

    out_net = {id(m): m["nodes"][-1] for m in stages}
    producteurs = {net: m for m in stages for net in [out_net[id(m)]]}

    incoming = {}      # id(stage) -> list des étages producteurs (dans l'îlot)
    a_entree_externe = {}
    for m in stages:
        prods = []
        externe = False
        for net in _in_nets(m):
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

# Accent des boîtes Z : remplissage bleu clair + contour bleu. Double rôle —
# rend le schéma plus lisible ET signale visuellement que la boîte est cliquable.
_Z_FILL = "#dbeafe"
_Z_EDGE = "#2563eb"
_OPAMP_FILL = "#eef2ff"   # triangle AOP légèrement teinté


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
        _ajouter_symbole(d, element().at((mid - slen / 2, y)).right(slen), row, label, label_loc)
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
        _ajouter_symbole(d, element().right(1.4), row, label, label_loc)
        d += elm.Line().right(0.35).color(_WIRE)
        if not _is_not_connected(stub_net):
            _draw_net_end(d, stub_net)
        _hit(col_x + 0.3, col_x + 1.7)
        return

    # composant isole (deux moignons) : symbole HORIZONTAL + deux bornes etiquetees.
    # On ne met PAS de drapeau masse/alim ici : les deux bouts sont les bornes du
    # dipole (ses ports), pas des rails distribues -> bornes nommees, dipole droit.
    _ajouter_symbole(d, element().at((0.0, y)).right(1.4), row, label, label_loc)
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
    """@brief Dessine « Amplificateur inverseur (AOP) » : AOP + Zin/Zf en blocs Z cliquables.

    Repli : si le match ne porte pas d'impédances structurées, dessin résistances.
    """
    imp = result.get("impedances")
    if not imp:
        rs = _refs(result, ci, "R")
        rf = rs[0] if rs else "Rf"
        rin = rs[1] if len(rs) > 1 else "Rin"
        op = d.add(elm.Opamp().anchor("in1").at((4.5, 0)))
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

    _draw_aop_inverseur_zin_zf(d, imp, ci)


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


def _z_box(d, p1, p2, name, bloc, ci, label_loc="top"):
    """@brief Dessine une boîte Z cliquable (ResistorIEC bleue) de p1 à p2 et
    enregistre sa hitbox sur d._z_hitboxes.

    @param d Dessin schemdraw.
    @param p1/p2 Extrémités de la boîte (x, y).
    @param name Préfixe d'étiquette (« Zin », « Zf »…).
    @param bloc Bloc d'impédance {'refs','composition','nodes'}.
    @param ci Dict {ref → {type, value}} pour l'étiquette.
    @param label_loc Position de l'étiquette schemdraw.
    @return None
    """
    d.add(elm.ResistorIEC().at(p1).to(p2).color(_Z_EDGE).fill(_Z_FILL))
    label = _z_label_anchor(p1, p2, label_loc)
    d.add(elm.Label().at(label["pos"]).label(
        _z_label(name, bloc, ci),
        halign=label["ha"],
        valign=label["va"],
        color=_Z_EDGE,
    ))
    hb = getattr(d, "_z_hitboxes", None)
    if hb is not None:
        pad = 0.5
        hb.append((min(p1[0], p2[0]) - pad, max(p1[0], p2[0]) + pad,
                   min(p1[1], p2[1]) - pad, max(p1[1], p2[1]) + pad,
                   list(bloc["refs"]), bloc["composition"]))


def _draw_aop_inverseur_zin_zf(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT"):
    """@brief Dessin commun des montages à topologie inverseuse : AOP + Zin/Zf cliquables.

    Partagé par l'ampli inverseur, l'intégrateur, le dérivateur (même structure :
    Zin sur IN-, Zf de IN- vers OUT, IN+ à la masse).

    @param imp Dict {'Zin': bloc, 'Zf': bloc} (cf. détecteurs).
    @param ci Dict {ref → {type, value}} pour étiquettes/valeurs.
    @param origin Position de l'AOP (pour chaîner plusieurs montages).
    @param in_label/out_label Libellés d'entrée/sortie ("" pour les masquer).
    @return dict {"in": (x,y), "out": (x,y)} : points de connexion du bloc.
    """
    zin, zf = imp["Zin"], imp["Zf"]
    op = d.add(elm.Opamp().right().anchor("in1").at(origin).color(_WIRE).fill(_OPAMP_FILL))
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
    d.add(elm.Line().at(noeud).up(above_y - noeud[1]).color(_WIRE))
    zf_p1, zf_p2 = (noeud[0], above_y), (out[0], above_y)
    _z_box(d, zf_p1, zf_p2, "Zf", zf, ci)
    d.add(elm.Line().at(zf_p2).toy(out[1]).color(_WIRE))
    out_pt = (out[0] + 1.0, out[1])
    d.add(elm.Line().at(out).to(out_pt).color(_WIRE).label(out_label, loc="right", color=_WIRE))

    return {"in": in_pt, "out": out_pt}


def _draw_aop_sommateur(d, imp, ci, origin=(5.0, 0), in_label="IN1", out_label="OUT"):
    """@brief Dessine le sommateur : bus d'entrées Zin + Zf cliquables sur IN-.

    @param imp Dict {'Zf': bloc, 'Zin': [bloc, ...]} (cf. détecteur).
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    zf, zin = imp["Zf"], imp["Zin"]
    op = d.add(elm.Opamp().right().anchor("in1").at(origin).color(_WIRE).fill(_OPAMP_FILL))
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


def _draw_aop_non_inverseur_zf_zg(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT"):
    """@brief Dessin du non-inverseur : signal sur IN+, pont Zf/Zg cliquable sur IN-.

    Topologie distincte de l'inverseur : l'entrée attaque IN+, et IN- porte un
    diviseur Zf (vers OUT, par le haut) / Zg (vers la masse). Gain = 1 + Zf/Zg.

    @param imp Dict {'Zf': bloc, 'Zg': bloc} (cf. détecteur).
    @param ci Dict {ref → {type, value}} pour étiquettes/valeurs.
    @param origin/in_label/out_label cf. _draw_aop_inverseur_zin_zf.
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    zf, zg = imp["Zf"], imp["Zg"]
    op = d.add(elm.Opamp().right().anchor("in2").at(origin).color(_WIRE).fill(_OPAMP_FILL))
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
        _draw_aop_non_inverseur_zf_zg(d, imp, ci)
        return

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
    in_net = (result.get("nodes") or [None])[0] if isinstance(result, dict) else None
    pont = _diviseur_sur_net(in_net, ci)
    if pont:
        haut, bas = pont
        npt = (op.in2[0] - 1.2, op.in2[1])
        d.add(elm.Line().at(op.in2).to(npt).color(_WIRE))
        d.add(elm.Dot().at(npt).color(_WIRE))
        # Jambe haute -> alim
        ztop = (npt[0], npt[1] + 1.7)
        _z_box(d, npt, ztop, "Z1", haut, ci)
        d.add(elm.Line().at(ztop).up(0.4).color(_WIRE).label("VCC", loc="top", color=_WIRE))
        # Jambe basse -> masse
        zbot = (npt[0], npt[1] - 1.7)
        _z_box(d, npt, zbot, "Z2", bas, ci, label_loc="bottom")
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
    # Montages ancrés "center" (à router avant les branches Zin/Zg) :
    if "sommateur" in ct.lower():
        res = _draw_aop_sommateur(d, imp, ci, origin, in_label, out_label)
    elif "différentiel" in ct.lower() or "differentiel" in ct.lower():
        in1 = "VIN-" if in_label == "VIN" else (in_label or "IN1")
        in2 = "VIN+" if in_label == "VIN" else "IN2"
        res = _draw_aop_differentiel(
            d, imp, ci, origin,
            in1_label=in1,
            in2_label=in2,
            out_label=out_label,
        )
    elif "Schmitt" in ct:
        res = _draw_aop_schmitt(d, imp, ci, origin, in_label, out_label)
    elif "Comparateur" in ct:
        res = _draw_aop_comparateur(d, match, ci, origin, in_label, out_label)
    elif "Zg" in imp:
        res = _draw_aop_non_inverseur_zf_zg(d, imp, ci, origin, in_label, out_label)
    elif "Zin" in imp:
        res = _draw_aop_inverseur_zin_zf(d, imp, ci, origin, in_label, out_label)
    else:
        res = _draw_follower(d, match, ci, origin, in_label, out_label)

    # Ancres par net d'entrée (pour le câblage branché) : les drawers multi-entrées
    # exposent "in_pts" (ordonné comme _in_nets) ; sinon l'unique "in" suffit.
    in_pts = res.get("in_pts") or [res["in"]]
    res["ins"] = dict(zip(_in_nets(match), in_pts))
    return res


def _draw_island_chain(d, ordered, ci):
    """@brief Dessine une chaîne de montages reliés OUT(N) -> IN(N+1).

    Chaque montage est posé à un x croissant ; un fil en Z relie la sortie d'un
    bloc à l'entrée du suivant. Premier bloc étiqueté VIN, dernier VOUT, internes
    sans libellé. Les boîtes Z poussent leurs hitboxes (coords absolues) -> le
    drill-down R/L/C reste cliquable.

    @param ordered Montages triés par flux (cf. _ordonner_montages_flux).
    @param ci Dict {ref → {type, value}}.
    """
    n = len(ordered)
    ancres = []
    for i, match in enumerate(ordered):
        in_label = "VIN" if i == 0 else ""
        out_label = "VOUT" if i == n - 1 else ""
        # y de l'origine : la sortie de chaque AOP doit tomber sur la même ligne
        # (y=0) pour aligner les triangles. Inverseur/intég/dériv sont ancrés par
        # IN- (broche du haut) -> on monte de +dy ; non-inverseur/suiveur ancrés
        # par IN+ (broche du bas) -> on descend de -dy.
        origin = (4.5 + i * _CHAINE_DX, _oy_for(match))
        ancres.append(_dessiner_montage_a(d, match, ci, origin, in_label, out_label))
        _annoter_etage(d, ancres[-1], match)

    for i in range(n - 1):
        out_pt = ancres[i]["out"]
        in_pt = ancres[i + 1]["in"]
        _fil_en_z(d, out_pt, in_pt)


def _oy_for(match):
    """@brief Décalage y de l'origine d'un montage pour que sa sortie tombe sur la
    ligne de base de sa bande (alignement des triangles).

    Schmitt/comparateur/différentiel ancrés "center" -> 0. Inverseur/intég/dériv
    ancrés in1 (haut) et sommateur -> +dy. Non-inverseur/suiveur (in2, bas) -> -dy.
    """
    imp = match.get("impedances") or {}
    ct = match.get("circuit_type", "")
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


_BRANCHE_ROW_GAP = 9.0     # écart vertical entre étages parallèles d'une même couche
_BRANCHE_DX = 13.0         # pas horizontal entre couches (large : place pour les canaux)

_TITRE_COLOR = "#1e293b"   # rôle de l'étage (slate foncé)
_GAIN_COLOR = "#0f766e"    # gain de l'étage (teal)
_ROLE_ETAGE = {
    "Amplificateur différentiel (AOP)":  "Différentiel",
    "Amplificateur sommateur (AOP)":     "Sommateur",
    "Amplificateur non-inverseur (AOP)": "Non-inverseur",
    "Amplificateur inverseur (AOP)":     "Inverseur",
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


def _z_passif(d, ref, ci, p1, p2, nom, label_loc="top"):
    """@brief Dessine un passif unique en boîte Z cliquable (drill-down R/L/C).

    @param ref Référence du passif (R/C/L), ou None pour ne rien dessiner.
    @param p1/p2 Extrémités de la boîte. @param nom Préfixe d'étiquette.
    """
    if not ref:
        return
    bloc = {"refs": [ref], "composition": ref, "nodes": ()}
    _z_box(d, p1, p2, nom, bloc, ci, label_loc=label_loc)


def _annoter_etage(d, ancres, match):
    """@brief Étiquette un étage : rôle au-dessus de sa sortie, gain en dessous.

    Placé à droite de l'AOP (espace inter-étages) pour ne pas percuter le réseau
    Zf/Zg. Purement additif : aucun impact sur le câblage ni les ancres.
    """
    out = ancres.get("out")
    if not out:
        return
    x = out[0] + 1.4
    d.add(elm.Label().at((x, out[1] + 0.85)).label(
        _titre_etage(match), color=_TITRE_COLOR, fontsize=11))
    gain = _texte_gain(match, None)
    if gain:
        d.add(elm.Label().at((x, out[1] - 0.85)).label(
            gain, color=_GAIN_COLOR, fontsize=8))


def _branched_edges(layers):
    """@brief Arêtes AVANT du DAG de montages (producteur.couche < consommateur.couche).

    Ignore les back-edges (issus d'une détection imparfaite) qui traverseraient le
    schéma. @return list[(prod_match, cons_match, net)].
    """
    layer_of = {id(m): lx for lx, L in enumerate(layers) for m in L}
    out_by_net = {m["nodes"][-1]: m for L in layers for m in L}
    edges = []
    for couche in layers:
        for cons in couche:
            for net in _in_nets(cons):
                prod = out_by_net.get(net)
                if prod is None or prod is cons:
                    continue
                if layer_of[id(prod)] >= layer_of[id(cons)]:
                    continue
                edges.append((prod, cons, net))
    return edges


def _draw_branched_chain(d, layers, ci):
    """@brief Dessine un îlot multi-AOP branché en couches (cf. _layers_montages_flux).

    Couche = colonne (x croissant) ; étages parallèles empilés verticalement. Chaque
    arête avant relie producteur.out -> consommateur.ins[net] via un canal vertical
    dédié (étalé par consommateur) pour éviter les chevauchements du fan-in.

    @param layers list[list[match]] couches ordonnées entrée->sortie.
    @param ci Dict {ref → {type, value}}.
    """
    ancres = {}                            # id(match) -> ancres ("out","ins",...)
    dernier = len(layers) - 1
    for lx, couche in enumerate(layers):
        m = len(couche)
        for ry, match in enumerate(couche):
            y_row = (ry - (m - 1) / 2.0) * _BRANCHE_ROW_GAP
            origin = (4.5 + lx * _BRANCHE_DX, y_row + _oy_for(match))
            out_label = "VOUT" if lx == dernier else ""
            ancres[id(match)] = _dessiner_montage_a(d, match, ci, origin, "", out_label)
            _annoter_etage(d, ancres[id(match)], match)

    # Câblage : un canal vertical distinct par entrée d'un même consommateur (fan-in).
    par_conso = {}
    for prod, cons, net in _branched_edges(layers):
        par_conso.setdefault(id(cons), []).append((prod, cons, net))
    for groupe in par_conso.values():
        groupe.sort(key=lambda e: ancres[id(e[1])]["ins"][e[2]][1])
        for k, (prod, cons, net) in enumerate(groupe):
            in_pt = ancres[id(cons)]["ins"][net]
            channel_x = in_pt[0] - 1.0 - k * 1.4
            _fil_canal(d, ancres[id(prod)]["out"], in_pt, channel_x)


def _draw_integrator(d, result, ci):
    """@brief Dessine le schéma « Intégrateur (AOP) » : AOP + Zin/Zf cliquables.

    Repli : si le match ne porte pas d'impédances structurées, dessin R/C fixe.
    """
    imp = result.get("impedances")
    if imp:
        _draw_aop_inverseur_zin_zf(d, imp, ci)
        return

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
    """@brief Dessine le schéma « Dérivateur (AOP) » : AOP + Zin/Zf cliquables.

    Repli : si le match ne porte pas d'impédances structurées, dessin C/R fixe.
    """
    imp = result.get("impedances")
    if imp:
        _draw_aop_inverseur_zin_zf(d, imp, ci)
        return

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


def _draw_aop_comparateur(d, _result, ci, origin=(4.5, 0), in_label="IN+", out_label="OUT"):
    """@brief Comparateur (AOP) en boucle ouverte : IN+ signal / IN- REF / OUT.

    Aucune impédance (pas de Z cliquable). Paramétré (origin/libellés) et renvoyant
    ses ancres pour être chaînable dans la vue îlot.

    @return dict {"in": (x,y), "out": (x,y)}.
    """
    op = d.add(elm.Opamp().right().anchor("center").at(origin).color(_WIRE).fill(_OPAMP_FILL))
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


def _draw_aop_schmitt(d, imp, ci, origin=(4.5, 0), in_label="IN", out_label="OUT"):
    """@brief Dessine la bascule de Schmitt : contre-réaction positive Zf
    (OUT → IN+) + patte d'entrée Zin sur IN+, toutes deux cliquables.

    @param imp Dict {'Zf': bloc, 'Zin': bloc?} (cf. détecteur).
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    zf = imp["Zf"]
    zin = imp.get("Zin")
    op = d.add(elm.Opamp().right().anchor("center").at(origin).color(_WIRE).fill(_OPAMP_FILL))
    inm, inp, out = op.in1, op.in2, op.out

    # IN- = référence
    d.add(elm.Line().at(inm).left(1.2).color(_WIRE))
    d.add(elm.Dot().at((inm[0] - 1.2, inm[1])).color(_WIRE).label("REF", loc="left", color=_WIRE))

    # Nœud IN+
    np_node = (inp[0] - 1.0, inp[1])
    d.add(elm.Line().at(np_node).to(inp).color(_WIRE))
    d.add(elm.Dot().at(np_node).color(_WIRE))
    in_pt = np_node

    # Zin : entrée -> IN+ (horizontale vers la gauche)
    if zin:
        zin_p1 = (np_node[0] - 3.0, np_node[1])
        _z_box(d, zin_p1, np_node, "Zin", zin, ci)
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
        _draw_aop_schmitt(d, imp, ci)
        return

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


def _draw_aop_differentiel(d, imp, ci, origin=(6.0, 0),
                           in1_label="IN1", in2_label="IN2", out_label="OUT"):
    """@brief Dessine le différentiel : AOP + pont Z1/Zf/Z3/Zg cliquable.

    @param imp Dict {'Z1','Zf','Z3','Zg'} (cf. détecteur).
    @return dict {"in": (x,y), "out": (x,y)}.
    """
    z1, zf, z3, zg = imp["Z1"], imp["Zf"], imp["Z3"], imp["Zg"]
    op = d.add(elm.Opamp().right().anchor("center").at(origin).color(_WIRE).fill(_OPAMP_FILL))
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
    _z_box(d, npn, zg_p2, "Zg", zg, ci, label_loc="bottom")
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
        _draw_aop_differentiel(d, imp, ci)
        return

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
    imp = result.get("impedances")
    if imp:
        _draw_aop_sommateur(d, imp, ci)
        return

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
    """@brief Dessine le schéma « Transistor en commutation » (Rb en boîte Z)."""
    q = _ref(result, ci, "Q"); r = _ref(result, ci, "R")
    t = d.add(elm.BjtNpn().at((3, 0)))
    bx, by = t.base
    _z_passif(d, r, ci, (bx - 2.6, by), (bx - 0.9, by), "Rb")
    d.add(elm.Line().at((bx - 0.9, by)).to((bx, by)))
    d.add(elm.Dot().at((bx - 2.6, by)).label("IN", loc="left"))
    d.add(elm.Line().at(t.collector).up(1).label("LOAD", loc="right"))
    d.add(elm.Line().at(t.emitter).down(0.5))
    d.add(elm.Ground())
    _titre_montage(d, result, (t.collector[0], t.collector[1] + 1.8))


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
    bx, by = t.base
    _z_passif(d, rb, ci, (bx - 2.6, by), (bx - 0.9, by), "Rb")
    d.add(elm.Line().at((bx - 0.9, by)).to((bx, by)))
    d.add(elm.Dot().at((bx - 2.6, by)).label("IN", loc="left"))
    # Rc en boîte Z verticale, du collecteur vers VCC
    cx, cy = t.collector
    _z_passif(d, rc, ci, (cx, cy + 0.5), (cx, cy + 1.9), "Rc", label_loc="left")
    d.add(elm.Line().at(t.collector).to((cx, cy + 0.5)))
    d.add(elm.Line().at((cx, cy + 1.9)).up(0.4).label("VCC", loc="top"))
    d.add(elm.Line().at(t.emitter).down(0.5))
    d.add(elm.Ground())
    d.add(elm.Line().at(t.collector).right(1.5).label("OUT", loc="right"))
    _titre_montage(d, result, (cx, cy + 2.7))


def _draw_mosfet_switch(d, result, ci):
    """@brief Dessine le schéma « MOSFET en commutation »."""
    m = _ref(result, ci, "M"); r = _ref(result, ci, "R")
    t = d.add(elm.NFet().at((3, 0)))
    # NFet 0.22 : grille à DROITE -> Rg en boîte Z vers la droite.
    gx, gy = t.gate
    _z_passif(d, r, ci, (gx + 0.9, gy), (gx + 2.6, gy), "Rg")
    d.add(elm.Line().at(t.gate).to((gx + 0.9, gy)))
    d.add(elm.Dot().at((gx + 2.6, gy)).label("IN", loc="right"))
    d.add(elm.Line().at(t.drain).up(1).label("LOAD", loc="right"))
    d.add(elm.Line().at(t.source).down(0.5))
    d.add(elm.Ground())
    _titre_montage(d, result, (t.drain[0], t.drain[1] + 1.8))


def _draw_high_side_mosfet(d, result, ci):
    """@brief Dessine le schéma « MOSFET haute-tension (côté haut) »."""
    m = _ref(result, ci, "M")
    r = _ref(result, ci, "R")
    t = d.add(elm.NFet().at((3, 0)))
    # Rg en boîte Z vers la droite (grille à droite dans NFet 0.22).
    gx, gy = t.gate
    _z_passif(d, r, ci, (gx + 0.9, gy), (gx + 2.6, gy), "Rg")
    d.add(elm.Line().at(t.gate).to((gx + 0.9, gy)))
    d.add(elm.Dot().at((gx + 2.6, gy)).label("IN", loc="right"))
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

    ctrl_pin = t.gate if use_mosfet else t.base
    coll_pin = t.drain if use_mosfet else t.collector
    emit_pin = t.source if use_mosfet else t.emitter
    ctrl_lbl = "VG" if use_mosfet else "CMD"

    # Contrôle : résistance de base en boîte Z cliquable, ou ligne directe
    cxp, cyp = ctrl_pin
    if rbs:
        _z_passif(d, rbs[0], ci, (cxp - 2.4, cyp), (cxp - 0.7, cyp), "Rb")
        d.add(elm.Line().at((cxp - 0.7, cyp)).to((cxp, cyp)))
        d.add(elm.Dot().at((cxp - 2.4, cyp)).label(ctrl_lbl, loc="left"))
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
    _titre_montage(d, result, (coil_top[0], coil_top[1] + 0.9))


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
    _titre_montage(d, result, ((t1.collector[0] + t2.collector[0]) / 2, iref_top + 0.7))


def _draw_suiveur_emetteur(d, result, ci):
    """@brief « Collecteur commun (suiveur d'émetteur) » : collecteur sur VCC,
    sortie sur l'émetteur via Re (boîtes Z cliquables : Rb base, Re émetteur)."""
    q = _ref(result, ci, "Q")
    rs = _refs(result, ci, "R")
    q_pins = ci.get(q, {}).get("pins", {})
    re = _ref_on_net(rs, ci, q_pins.get("E"), rs[0] if rs else "Re")
    rb = next((r for r in rs if r != re), None)
    t = d.add(elm.BjtNpn().at((3, 0)))
    bx, by = t.base
    if rb:
        _z_passif(d, rb, ci, (bx - 2.6, by), (bx - 0.9, by), "Rb")
        d.add(elm.Line().at((bx - 0.9, by)).to((bx, by)))
        d.add(elm.Dot().at((bx - 2.6, by)).label("IN", loc="left"))
    else:
        d.add(elm.Line().at(t.base).left(1).label("IN", loc="left"))
    # Collecteur -> VCC
    d.add(elm.Line().at(t.collector).up(1).label("VCC", loc="top"))
    # Émetteur -> Re -> GND, sortie au point d'émetteur
    ex, ey = t.emitter
    d.add(elm.Line().at(t.emitter).right(1.4).label("OUT", loc="right"))
    _z_passif(d, re, ci, (ex, ey - 0.6), (ex, ey - 2.0), "Re", label_loc="right")
    d.add(elm.Line().at(t.emitter).to((ex, ey - 0.6)))
    d.add(elm.Line().at((ex, ey - 2.0)).down(0.4))
    d.add(elm.Ground())
    _titre_montage(d, result, (t.collector[0], t.collector[1] + 1.8))


def _draw_push_pull(d, result, ci):
    """@brief « Étage push-pull » : NPN (haut, C=VCC) + PNP (bas, C=GND),
    émetteurs communs = sortie, bases communes = entrée."""
    qn = d.add(elm.BjtNpn().at((3, 1.5)))
    qp = d.add(elm.BjtPnp().at((3, -1.5)))
    # Bases communes (entrée) reliées verticalement
    d.add(elm.Line().at(qn.base).to(qp.base))
    midb = ((qn.base[0] + qp.base[0]) / 2, (qn.base[1] + qp.base[1]) / 2)
    d.add(elm.Dot().at(midb))
    d.add(elm.Line().at(midb).left(1.2).label("IN", loc="left"))
    # Collecteurs : NPN -> VCC, PNP -> GND
    d.add(elm.Line().at(qn.collector).up(0.8).label("VCC", loc="top"))
    d.add(elm.Line().at(qp.collector).down(0.8))
    d.add(elm.Ground())
    # Émetteurs communs -> sortie
    d.add(elm.Line().at(qn.emitter).to(qp.emitter))
    mide = ((qn.emitter[0] + qp.emitter[0]) / 2, (qn.emitter[1] + qp.emitter[1]) / 2)
    d.add(elm.Dot().at(mide))
    d.add(elm.Line().at(mide).right(1.4).label("OUT", loc="right"))
    _titre_montage(d, result, (qn.collector[0], qn.collector[1] + 1.6))


def _draw_darlington(d, result, ci):
    """@brief « Paire Darlington » : émetteur de Q1 sur la base de Q2, collecteurs
    communs ; Re (charge d'émetteur) en boîte Z cliquable."""
    re = _ref(result, ci, "R")
    q1 = d.add(elm.BjtNpn().at((2.5, 1.4)))
    q2 = d.add(elm.BjtNpn().at((4.2, -1.0)))
    d.add(elm.Line().at(q1.base).left(1.2).label("IN", loc="left"))
    # Collecteurs communs -> VCC
    d.add(elm.Line().at(q1.collector).up(0.8))
    top = d.here
    d.add(elm.Line().at(q2.collector).toy(top[1]))
    d.add(elm.Line().at((q2.collector[0], top[1])).to(top))
    d.add(elm.Line().at(top).up(0.4).label("VCC", loc="top"))
    # E(Q1) -> B(Q2)
    d.add(elm.Line().at(q1.emitter).to(q2.base))
    d.add(elm.Dot().at(q2.base))
    # Sortie sur l'émetteur de Q2, Re vers GND
    ex, ey = q2.emitter
    d.add(elm.Line().at(q2.emitter).right(1.4).label("OUT", loc="right"))
    _z_passif(d, re, ci, (ex, ey - 0.6), (ex, ey - 2.0), "Re", label_loc="right")
    d.add(elm.Line().at(q2.emitter).to((ex, ey - 0.6)))
    d.add(elm.Line().at((ex, ey - 2.0)).down(0.4))
    d.add(elm.Ground())
    _titre_montage(d, result, (top[0], top[1] + 1.2))


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
    "Collecteur commun (suiveur d'émetteur)": _draw_suiveur_emetteur,
    "Étage push-pull":                   _draw_push_pull,
    "Paire Darlington":                  _draw_darlington,
}
