"""
@file network_viewer.py
@brief Vue réseau interactive : graphe zoomable/pannable des composants.
"""
import math
import tkinter as tk
import customtkinter as ctk

# Couleur de fond par type de composant
_COMP_COLORS = {
    'R': '#f97316',  # orange
    'C': '#3b82f6',  # bleu
    'L': '#8b5cf6',  # violet
    'D': '#22c55e',  # vert
    'Q': '#ec4899',  # rose
    'M': '#f43f5e',  # rouge
    'U': '#06b6d4',  # cyan
    'K': '#eab308',  # jaune
    'F': '#ef4444',  # rouge vif
}
_DEFAULT_COMP  = '#94a3b8'
_EDGE_COLOR    = '#334155'
_LABEL_COLOR   = '#e2e8f0'
_NET_LABEL_CLR = '#64748b'
_BG            = '#0f172a'
_PANEL_BG      = '#1e293b'

# Palette de couleurs pour les groupes détectés (circuit_type)
_GROUP_PALETTE = [
    '#7c3aed', '#0e7490', '#15803d', '#b45309',
    '#be185d', '#4338ca', '#0369a1', '#9f1239',
]


def _group_color_map(results: list) -> dict:
    """@brief Associe chaque circuit_type à une couleur de groupe."""
    mapping = {}
    palette_idx = 0
    for r in results:
        ct = r.get('circuit_type', '')
        if ct and ct not in mapping:
            mapping[ct] = _GROUP_PALETTE[palette_idx % len(_GROUP_PALETTE)]
            palette_idx += 1
    return mapping


class NetworkGraphViewer(ctk.CTkToplevel):
    """@brief Fenêtre de visualisation du réseau de composants (NetworkX + tk.Canvas)."""

    def __init__(self, graph, results: list):
        """@brief Crée la fenêtre de visualisation.

        @param graph MultiGraph NetworkX du circuit (graphe.graph['components']).
        @param results Circuits détectés (sortie de match_patterns).
        """
        super().__init__()
        self.title("Vue réseau — Graphe des composants")
        self.geometry("1100x700")
        self.configure(fg_color=_BG)

        self._graph   = graph
        self._results = results
        self._group_colors = _group_color_map(results)

        # Mapping ref -> circuit_type (pour colorier le fond des nœuds)
        self._ref_to_group: dict[str, str] = {}
        for r in results:
            for ref in r.get('components', []):
                self._ref_to_group[ref] = r.get('circuit_type', '')
            for s in r.get('satellites', []):
                self._ref_to_group[s['ref']] = r.get('circuit_type', '')

        # État de la caméra
        self._scale  = 1.0
        self._offset = [0.0, 0.0]   # [ox, oy] translation pixels

        # Nœud sélectionné
        self._selected: str | None = None

        self._build_layout()
        self._build_ui()
        self._draw()

    # ── Layout (positions NetworkX) ───────────────────────────────────────────

    def _build_layout(self):
        """@brief Calcule les positions des nœuds via spring_layout."""
        try:
            import networkx as nx
        except ImportError:
            self._positions: dict = {}
            return

        composants = self._graph.graph.get('components', {})
        # Construire un graphe simplifié composant-composant (via nets partagés)
        G = nx.Graph()
        for ref in composants:
            G.add_node(ref)
        # Arête entre deux composants si ils partagent un net (via les edges du graphe)
        edges_seen: set = set()
        for u, v, d in self._graph.edges(data=True):
            ref = d.get('ref')
            if ref is None:
                continue
            # u et v sont des nœuds de net ; find autres composants sur ces nets
            for u2, v2, d2 in self._graph.edges(u, data=True):
                ref2 = d2.get('ref')
                if ref2 and ref2 != ref:
                    key = tuple(sorted([ref, ref2]))
                    if key not in edges_seen:
                        edges_seen.add(key)
                        G.add_edge(ref, ref2)

        pos = nx.spring_layout(G, seed=42, k=2.0 / math.sqrt(max(len(G), 1)))
        self._positions = pos   # {ref: array([x, y])} in [-1, 1]

        # Normalize to [0.1, 0.9]
        if pos:
            xs = [p[0] for p in pos.values()]
            ys = [p[1] for p in pos.values()]
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            xrange = xmax - xmin or 1
            yrange = ymax - ymin or 1
            self._positions = {
                ref: ((p[0] - xmin) / xrange * 0.8 + 0.1,
                      (p[1] - ymin) / yrange * 0.8 + 0.1)
                for ref, p in pos.items()
            }

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        """@brief Construit le canvas, le panneau latéral et la légende."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self._canvas = tk.Canvas(self, bg=_BG, highlightthickness=0, cursor="crosshair")
        self._canvas.grid(row=0, column=0, sticky="nsew")

        # Panneau latéral (infos nœud sélectionné)
        panel = tk.Frame(self, bg=_PANEL_BG, width=220)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_propagate(False)
        self._panel = panel

        tk.Label(panel, text="COMPOSANT", bg=_PANEL_BG, fg="#64748b",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(12, 4))
        self._panel_ref   = tk.Label(panel, text="—", bg=_PANEL_BG, fg="#f1f5f9",
                                     font=("Consolas", 14, "bold"))
        self._panel_ref.pack(anchor="w", padx=12)
        self._panel_type  = tk.Label(panel, text="", bg=_PANEL_BG, fg="#94a3b8",
                                     font=("Segoe UI", 10))
        self._panel_type.pack(anchor="w", padx=12, pady=2)
        self._panel_value = tk.Label(panel, text="", bg=_PANEL_BG, fg="#cbd5e1",
                                     font=("Segoe UI", 11))
        self._panel_value.pack(anchor="w", padx=12)
        self._panel_group = tk.Label(panel, text="", bg=_PANEL_BG, fg="#7c3aed",
                                     font=("Segoe UI", 9), wraplength=196, justify="left")
        self._panel_group.pack(anchor="w", padx=12, pady=(6, 0))
        tk.Frame(panel, bg="#334155", height=1).pack(fill="x", padx=12, pady=10)
        tk.Label(panel, text="BROCHES", bg=_PANEL_BG, fg="#64748b",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12)
        self._panel_pins = tk.Label(panel, text="", bg=_PANEL_BG, fg="#94a3b8",
                                    font=("Consolas", 10), justify="left", wraplength=196)
        self._panel_pins.pack(anchor="w", padx=12, pady=4)

        # Légende en bas
        legend = tk.Frame(self, bg=_PANEL_BG, height=34)
        legend.grid(row=1, column=0, columnspan=2, sticky="ew")
        tk.Label(legend, text="Groupes : ", bg=_PANEL_BG, fg="#64748b",
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 4))
        for ct, color in self._group_colors.items():
            tk.Label(legend, text="■", bg=_PANEL_BG, fg=color,
                     font=("Segoe UI", 12)).pack(side="left")
            short = ct[:22] + "…" if len(ct) > 22 else ct
            tk.Label(legend, text=short, bg=_PANEL_BG, fg="#94a3b8",
                     font=("Segoe UI", 9)).pack(side="left", padx=(2, 10))

        # Bindings
        self._canvas.bind("<ButtonPress-1>",   self._on_click)
        self._canvas.bind("<B1-Motion>",        self._on_pan)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<MouseWheel>",       self._on_zoom)
        self._canvas.bind("<Configure>",        self._on_resize)
        self._pan_start = None

    # ── Dessin ────────────────────────────────────────────────────────────────

    def _world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        """@brief Transforme coordonnées monde [0,1] -> pixels canvas."""
        w = self._canvas.winfo_width()  or 800
        h = self._canvas.winfo_height() or 600
        base_w, base_h = w - 30, h - 30
        sx = wx * base_w * self._scale + self._offset[0] + 15
        sy = wy * base_h * self._scale + self._offset[1] + 15
        return sx, sy

    def _screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        """@brief Transforme pixels canvas -> coordonnées monde [0,1]."""
        w = self._canvas.winfo_width()  or 800
        h = self._canvas.winfo_height() or 600
        base_w, base_h = w - 30, h - 30
        wx = (sx - 15 - self._offset[0]) / (base_w * self._scale)
        wy = (sy - 15 - self._offset[1]) / (base_h * self._scale)
        return wx, wy

    def _draw(self):
        """@brief Redessine tout le canvas."""
        self._canvas.delete("all")
        composants = self._graph.graph.get('components', {})
        if not self._positions:
            self._canvas.create_text(
                (self._canvas.winfo_width() or 400) // 2,
                (self._canvas.winfo_height() or 300) // 2,
                text="NetworkX non disponible — pip install networkx",
                fill="#ef4444", font=("Segoe UI", 13))
            return

        # ── Arêtes (nets partagés) ────────────────────────────────────────────
        drawn_pairs: set = set()
        net_labels: dict = {}   # (ref1,ref2) -> net name
        for u, v, d in self._graph.edges(data=True):
            ref = d.get('ref')
            if ref is None:
                continue
            for u2, v2, d2 in self._graph.edges(u, data=True):
                ref2 = d2.get('ref')
                if ref2 and ref2 != ref:
                    key = tuple(sorted([ref, ref2]))
                    if key not in drawn_pairs and ref in self._positions and ref2 in self._positions:
                        drawn_pairs.add(key)
                        x1, y1 = self._world_to_screen(*self._positions[ref])
                        x2, y2 = self._world_to_screen(*self._positions[ref2])
                        self._canvas.create_line(x1, y1, x2, y2,
                                                 fill=_EDGE_COLOR, width=1.5, tags="edge")
                        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                        self._canvas.create_text(mx, my, text=u,
                                                 fill=_NET_LABEL_CLR,
                                                 font=("Consolas", 7), tags="netlabel")

        # ── Nœuds (composants) ────────────────────────────────────────────────
        r = max(14, int(18 * self._scale))
        self._node_coords: dict[str, tuple] = {}   # ref -> (cx, cy)
        for ref, pos in self._positions.items():
            cx, cy = self._world_to_screen(*pos)
            self._node_coords[ref] = (cx, cy)
            comp   = composants.get(ref)
            ctype  = comp.type if comp else '?'
            group  = self._ref_to_group.get(ref, '')
            ring   = self._group_colors.get(group, '#334155')
            fill   = _COMP_COLORS.get(ctype, _DEFAULT_COMP)
            sel    = ref == self._selected
            outline_w = 3 if sel else 2

            self._canvas.create_oval(
                cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3,
                fill=ring, outline=ring, tags=("node_ring", f"ring_{ref}"))
            self._canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill=fill, outline="#ffffff" if sel else fill,
                width=outline_w, tags=("node", f"node_{ref}"))
            self._canvas.create_text(cx, cy, text=ctype,
                                     fill="white",
                                     font=("Consolas", max(7, r - 4), "bold"),
                                     tags=("nodelabel", f"nodelabel_{ref}"))
            self._canvas.create_text(cx, cy + r + 8, text=ref,
                                     fill=_LABEL_COLOR,
                                     font=("Segoe UI", max(7, int(9 * self._scale))),
                                     tags=("reflabel", f"ref_{ref}"))

        # Mettre les arêtes derrière les nœuds
        self._canvas.tag_lower("edge")
        self._canvas.tag_lower("netlabel")

    # ── Interactions ──────────────────────────────────────────────────────────

    def _hit_test(self, sx: float, sy: float) -> str | None:
        """@brief Retourne la ref du nœud le plus proche du clic (ou None)."""
        r = max(14, int(18 * self._scale)) + 4
        best_ref, best_d = None, float('inf')
        for ref, (cx, cy) in getattr(self, '_node_coords', {}).items():
            d = math.hypot(sx - cx, sy - cy)
            if d < r and d < best_d:
                best_d, best_ref = d, ref
        return best_ref

    def _on_click(self, event):
        """@brief Clic gauche : sélectionner un nœud ou démarrer le pan."""
        hit = self._hit_test(event.x, event.y)
        if hit:
            self._selected = hit
            self._update_panel(hit)
            self._draw()
        else:
            self._pan_start = (event.x, event.y)

    def _on_pan(self, event):
        """@brief Drag : déplacer la caméra."""
        if self._pan_start:
            dx = event.x - self._pan_start[0]
            dy = event.y - self._pan_start[1]
            self._offset[0] += dx
            self._offset[1] += dy
            self._pan_start = (event.x, event.y)
            self._draw()

    def _on_release(self, _event):
        """@brief Fin du drag."""
        self._pan_start = None

    def _on_zoom(self, event):
        """@brief Zoom molette centré sur le curseur."""
        factor = 1.1 if event.delta > 0 else 0.9
        wx, wy = self._screen_to_world(event.x, event.y)
        self._scale = max(0.2, min(8.0, self._scale * factor))
        # Recalcule l'offset pour que le point sous le curseur reste fixe
        nx_, ny_ = self._world_to_screen(wx, wy)
        self._offset[0] += event.x - nx_
        self._offset[1] += event.y - ny_
        self._draw()

    def _on_resize(self, _event):
        """@brief Redessine après redimensionnement de la fenêtre."""
        self._draw()

    def _update_panel(self, ref: str):
        """@brief Met à jour le panneau latéral avec les infos du composant sélectionné."""
        composants = self._graph.graph.get('components', {})
        comp = composants.get(ref)
        if comp is None:
            return
        self._panel_ref.configure(text=ref)
        self._panel_type.configure(text=f"Type : {comp.type}")
        self._panel_value.configure(text=comp.value or "—")
        group = self._ref_to_group.get(ref, '')
        color = self._group_colors.get(group, '#64748b')
        self._panel_group.configure(text=group or "Non classifié", fg=color)
        pins_txt = "\n".join(f"  {pin}: {net}" for pin, net in (comp.pins or {}).items())
        self._panel_pins.configure(text=pins_txt or "—")
