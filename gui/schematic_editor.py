"""
@file schematic_editor.py
@brief Éditeur de schéma interactif : palette, canvas avec grille, placement, câblage.
"""
import tkinter as tk
from dataclasses import dataclass
from typing import Optional

GRID = 20  # pas de la grille en pixels

# ── Définitions des composants ────────────────────────────────────────────────
# pins : {nom_pin: (dx, dy)} — déplacement depuis le centre du composant
COMP_DEFS: dict = {
    "R":   {"label": "Résistance",   "color": "#f97316", "w": 80, "h": 40,
            "pins": {"1": (-40, 0),  "2": (40, 0)},          "default_value": "10k"},
    "C":   {"label": "Condensateur", "color": "#3b82f6", "w": 60, "h": 40,
            "pins": {"1": (-30, 0),  "2": (30, 0)},          "default_value": "100n"},
    "L":   {"label": "Self",         "color": "#8b5cf6", "w": 80, "h": 40,
            "pins": {"1": (-40, 0),  "2": (40, 0)},          "default_value": "10µH"},
    "D":   {"label": "Diode",        "color": "#22c55e", "w": 60, "h": 40,
            "pins": {"A": (-30, 0),  "K": (30, 0)},          "default_value": "1N4148"},
    "Q":   {"label": "BJT",          "color": "#ec4899", "w": 60, "h": 80,
            "pins": {"B": (-30, 0),  "C": (30, -30), "E": (30, 30)},
            "default_value": "2N2222"},
    "U":   {"label": "AOP",          "color": "#06b6d4", "w": 80, "h": 80,
            "pins": {"IN+": (-40, -20), "IN-": (-40, 20), "OUT": (40, 0)},
            "default_value": "LM741"},
    "K":   {"label": "Relais",       "color": "#eab308", "w": 80, "h": 60,
            "pins": {"A1": (-40, -20), "A2": (-40, 20),
                     "11": (40, -20),  "12": (40, 20)},
            "default_value": "RY1"},
    "GND": {"label": "GND",          "color": "#94a3b8", "w": 40, "h": 40,
            "pins": {"1": (0, -20)},                          "default_value": "GND"},
    "VCC": {"label": "VCC",          "color": "#ef4444", "w": 40, "h": 40,
            "pins": {"1": (0, 20)},                           "default_value": "VCC"},
}

_PIN_RADIUS  = 5    # rayon visuel des pins
_HIT_RADIUS  = 12   # rayon de détection clic sur pin


@dataclass
class CompInst:
    id:        int
    ref:       str
    comp_type: str
    value:     str
    cx:        int
    cy:        int


@dataclass
class WireInst:
    id:           int
    from_comp_id: int
    from_pin:     str
    to_comp_id:   int
    to_pin:       str


class SchematicEditor(tk.Frame):
    """@brief Canvas interactif pour dessiner un schéma électronique.

    États internes : idle | placing | wiring.
    """

    def __init__(self, parent):
        super().__init__(parent, bg="#0f172a")
        self._comps:   dict[int, CompInst] = {}
        self._wires:   list[WireInst]      = []
        self._next_id: int                 = 1
        self._counters: dict[str, int]     = {}

        # état machine
        self._state       = "idle"
        self._place_type: Optional[str]             = None
        self._selected_id: Optional[int]            = None
        self._wire_src:   Optional[tuple[int, str]] = None
        self._rubber_band: Optional[int]            = None

        # drag
        self._drag_comp_id: Optional[int]   = None
        self._drag_last:    Optional[tuple] = None

        self._build()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self):
        # palette gauche
        palette = tk.Frame(self, bg="#1e293b", width=136)
        palette.pack(side="left", fill="y")
        palette.pack_propagate(False)
        self._build_palette(palette)

        # zone canvas + scrollbars
        wrap = tk.Frame(self, bg="#0f172a")
        wrap.pack(side="left", fill="both", expand=True)
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(
            wrap, bg="#0f172a", highlightthickness=0,
            scrollregion=(0, 0, 2400, 1800),
        )
        vsb = tk.Scrollbar(wrap, orient="vertical",   command=self._canvas.yview)
        hsb = tk.Scrollbar(wrap, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._draw_grid()
        self._bind_events()

    def _build_palette(self, parent):
        tk.Label(parent, text="COMPOSANTS", fg="#64748b", bg="#1e293b",
                 font=("Segoe UI", 8, "bold")).pack(pady=(14, 4), padx=8, anchor="w")

        for comp_type, defn in COMP_DEFS.items():
            color = defn["color"]
            short_label = defn["label"][:11]
            b = tk.Button(
                parent,
                text=f"{comp_type}  {short_label}",
                bg="#1e293b", fg=color, activebackground="#263347",
                activeforeground=color, relief="flat", anchor="w",
                font=("Segoe UI", 9, "bold"), cursor="hand2", padx=10,
                command=lambda t=comp_type: self._start_placing(t),
            )
            b.pack(fill="x", padx=4, pady=2)

        tk.Frame(parent, bg="#334155", height=1).pack(fill="x", padx=8, pady=8)

        tk.Button(parent, text="🗑  Supprimer",
                  bg="#1e293b", fg="#ef4444", activebackground="#263347",
                  activeforeground="#ef4444", relief="flat", anchor="w",
                  font=("Segoe UI", 9), cursor="hand2", padx=10,
                  command=self._delete_selected).pack(fill="x", padx=4, pady=2)

        tk.Button(parent, text="⬜  Effacer tout",
                  bg="#1e293b", fg="#94a3b8", activebackground="#263347",
                  activeforeground="#94a3b8", relief="flat", anchor="w",
                  font=("Segoe UI", 9), cursor="hand2", padx=10,
                  command=self.clear_all).pack(fill="x", padx=4, pady=2)

        tk.Frame(parent, bg="#334155", height=1).pack(fill="x", padx=8, pady=8)

        self._status_lbl = tk.Label(
            parent, text="Cliquer sur\nla palette\npour placer",
            fg="#475569", bg="#1e293b",
            font=("Segoe UI", 8), justify="center",
        )
        self._status_lbl.pack(padx=8, pady=4)

    def _draw_grid(self):
        for x in range(0, 2400, GRID):
            for y in range(0, 1800, GRID):
                self._canvas.create_oval(x - 1, y - 1, x + 1, y + 1,
                                         fill="#1e293b", outline="", tags="grid")

    def _bind_events(self):
        c = self._canvas
        c.bind("<Button-1>",        self._on_click)
        c.bind("<B1-Motion>",       self._on_b1_motion)
        c.bind("<ButtonRelease-1>", self._on_b1_release)
        c.bind("<Motion>",          self._on_motion)
        c.bind("<Double-Button-1>", self._on_double_click)
        c.bind("<Button-3>",        self._on_right_click)
        c.bind("<Delete>",          self._on_delete)
        c.bind("<BackSpace>",       self._on_delete)
        c.bind("<Escape>",          self._on_escape)
        c.bind("<MouseWheel>",      lambda e: c.yview_scroll(int(-e.delta / 120), "units"))
        c.bind("<Shift-MouseWheel>",lambda e: c.xview_scroll(int(-e.delta / 120), "units"))
        c.focus_set()

    # ── Placement ────────────────────────────────────────────────────────────

    def _start_placing(self, comp_type: str):
        self._cancel_wiring()
        self._deselect()
        self._state      = "placing"
        self._place_type = comp_type
        self._canvas.configure(cursor="crosshair")
        self._set_status(f"Clic pour\nplacer {comp_type}")

    def _place_comp(self, cx: int, cy: int):
        t     = self._place_type
        defn  = COMP_DEFS[t]
        n     = self._counters.get(t, 0) + 1
        self._counters[t] = n
        ref   = f"{t}{n}" if t not in ("GND", "VCC") else f"{t}{n}"
        comp  = CompInst(self._next_id, ref, t, defn["default_value"], cx, cy)
        self._next_id += 1
        self._comps[comp.id] = comp
        self._draw_comp(comp)
        self._state      = "idle"
        self._place_type = None
        self._canvas.configure(cursor="")
        self._set_status("Prêt")

    # ── Rendu ────────────────────────────────────────────────────────────────

    def _draw_comp(self, comp: CompInst):
        defn  = COMP_DEFS[comp.comp_type]
        color = defn["color"]
        cx, cy = comp.cx, comp.cy
        w2, h2 = defn["w"] // 2, defn["h"] // 2
        tag   = f"comp_{comp.id}"
        self._canvas.delete(tag)

        if comp.comp_type == "GND":
            self._canvas.create_line(cx, cy - 20, cx, cy, fill=color, width=2, tags=tag)
            for i, hw in enumerate([16, 10, 5]):
                yy = cy + i * 5
                self._canvas.create_line(cx - hw, yy, cx + hw, yy,
                                         fill=color, width=2, tags=tag)
            self._canvas.create_text(cx, cy - 25, text=comp.ref,
                                     fill=color, font=("Consolas", 8), tags=tag)
        elif comp.comp_type == "VCC":
            self._canvas.create_line(cx, cy + 20, cx, cy + 2, fill=color, width=2, tags=tag)
            self._canvas.create_polygon(cx - 10, cy + 2, cx + 10, cy + 2, cx, cy - 14,
                                        fill=color, outline="", tags=tag)
            self._canvas.create_text(cx, cy + 28, text=comp.ref,
                                     fill=color, font=("Consolas", 8), tags=tag)
        else:
            # Rectangle avec coin arrondi (simulé)
            self._canvas.create_rectangle(cx - w2, cy - h2, cx + w2, cy + h2,
                                          fill="#0f172a", outline=color, width=2, tags=tag)
            # Type badge (coin haut-gauche)
            self._canvas.create_text(cx - w2 + 6, cy - h2 + 8,
                                     text=comp.comp_type,
                                     fill=color, font=("Consolas", 8, "bold"),
                                     anchor="w", tags=tag)
            # Ref (centre haut)
            self._canvas.create_text(cx, cy - 6, text=comp.ref,
                                     fill="#e2e8f0", font=("Consolas", 9, "bold"), tags=tag)
            # Valeur (centre bas)
            self._canvas.create_text(cx, cy + 8, text=comp.value,
                                     fill="#64748b", font=("Consolas", 8), tags=tag)

        # Pins
        for pin_name, (dx, dy) in defn["pins"].items():
            px, py = cx + dx, cy + dy
            self._canvas.create_oval(px - _PIN_RADIUS, py - _PIN_RADIUS,
                                     px + _PIN_RADIUS, py + _PIN_RADIUS,
                                     fill="#0f172a", outline=color, width=2,
                                     tags=(tag, f"pin_{comp.id}_{pin_name}"))
            # petit label pin si composant complexe (>2 pins)
            if len(defn["pins"]) > 2:
                anchor = "e" if dx < 0 else "w"
                self._canvas.create_text(px + (-8 if dx < 0 else 8), py,
                                         text=pin_name, fill="#475569",
                                         font=("Consolas", 7), anchor=anchor, tags=tag)

    def _draw_wire(self, wire: WireInst):
        ca = self._comps.get(wire.from_comp_id)
        cb = self._comps.get(wire.to_comp_id)
        if not ca or not cb:
            return
        dx_a, dy_a = COMP_DEFS[ca.comp_type]["pins"][wire.from_pin]
        dx_b, dy_b = COMP_DEFS[cb.comp_type]["pins"][wire.to_pin]
        x1, y1 = ca.cx + dx_a, ca.cy + dy_a
        x2, y2 = cb.cx + dx_b, cb.cy + dy_b
        tag = f"wire_{wire.id}"
        self._canvas.delete(tag)
        # routage Manhattan : horizontal puis vertical
        self._canvas.create_line(x1, y1, x2, y1, x2, y2,
                                 fill="#475569", width=2,
                                 joinstyle="round", tags=tag)

    def _redraw_wires_of(self, comp_id: int):
        for w in self._wires:
            if w.from_comp_id == comp_id or w.to_comp_id == comp_id:
                self._draw_wire(w)

    # ── Hit-testing ──────────────────────────────────────────────────────────

    def _cc(self, event):
        """Coordonnées canvas depuis un événement (scroll corrigé)."""
        return self._canvas.canvasx(event.x), self._canvas.canvasy(event.y)

    def _snap(self, x, y):
        return round(x / GRID) * GRID, round(y / GRID) * GRID

    def _find_pin_at(self, x, y) -> Optional[tuple[int, str]]:
        for comp in self._comps.values():
            for pn, (dx, dy) in COMP_DEFS[comp.comp_type]["pins"].items():
                px, py = comp.cx + dx, comp.cy + dy
                if (x - px) ** 2 + (y - py) ** 2 <= _HIT_RADIUS ** 2:
                    return (comp.id, pn)
        return None

    def _find_comp_at(self, x, y) -> Optional[int]:
        for comp in self._comps.values():
            defn = COMP_DEFS[comp.comp_type]
            w2, h2 = defn["w"] // 2 + 6, defn["h"] // 2 + 6
            if comp.cx - w2 <= x <= comp.cx + w2 and comp.cy - h2 <= y <= comp.cy + h2:
                return comp.id
        return None

    # ── Gestionnaires d'événements ────────────────────────────────────────────

    def _on_click(self, event):
        self._canvas.focus_set()
        cx, cy = self._cc(event)
        sx, sy = self._snap(cx, cy)

        if self._state == "placing":
            self._place_comp(sx, sy)
            return

        if self._state == "wiring":
            pin = self._find_pin_at(cx, cy)
            if pin and pin != self._wire_src:
                self._complete_wire(pin)
            else:
                self._cancel_wiring()
            return

        # IDLE : priorité pin > corps de composant
        pin = self._find_pin_at(cx, cy)
        if pin:
            self._start_wiring(pin)
            return

        comp_id = self._find_comp_at(cx, cy)
        if comp_id:
            self._select(comp_id)
            self._drag_comp_id = comp_id
            self._drag_last    = (cx, cy)
        else:
            self._deselect()

    def _on_b1_motion(self, event):
        if self._state == "idle" and self._drag_comp_id is not None:
            cx, cy = self._cc(event)
            sx, sy = self._snap(cx, cy)
            comp = self._comps.get(self._drag_comp_id)
            if comp and (comp.cx != sx or comp.cy != sy):
                comp.cx, comp.cy = sx, sy
                self._draw_comp(comp)
                self._redraw_wires_of(self._drag_comp_id)
                # déplacer aussi le cadre de sélection
                self._deselect()
                self._select(self._drag_comp_id)

    def _on_b1_release(self, event):
        self._drag_comp_id = None
        self._drag_last    = None

    def _on_motion(self, event):
        if self._state == "wiring" and self._wire_src:
            cx, cy = self._cc(event)
            comp = self._comps.get(self._wire_src[0])
            if comp:
                dx, dy = COMP_DEFS[comp.comp_type]["pins"][self._wire_src[1]]
                x1, y1 = comp.cx + dx, comp.cy + dy
                if self._rubber_band:
                    self._canvas.delete(self._rubber_band)
                self._rubber_band = self._canvas.create_line(
                    x1, y1, cx, y1, cx, cy,
                    fill="#4ade80", width=2, dash=(5, 3),
                )

    def _on_double_click(self, event):
        cx, cy = self._cc(event)
        comp_id = self._find_comp_at(cx, cy)
        if comp_id:
            self._edit_comp(comp_id)

    def _on_right_click(self, event):
        cx, cy = self._cc(event)
        comp_id = self._find_comp_at(cx, cy)
        if not comp_id:
            return
        self._select(comp_id)
        m = tk.Menu(self._canvas, tearoff=0, bg="#1e293b", fg="white",
                    activebackground="#3b82f6", activeforeground="white")
        m.add_command(label="✏  Modifier…", command=lambda: self._edit_comp(comp_id))
        m.add_separator()
        m.add_command(label="🗑  Supprimer", command=lambda: self._delete_comp(comp_id))
        m.post(event.x_root, event.y_root)

    def _on_delete(self, _=None):
        self._delete_selected()

    def _on_escape(self, _=None):
        if self._state == "wiring":
            self._cancel_wiring()
        elif self._state == "placing":
            self._state      = "idle"
            self._place_type = None
            self._canvas.configure(cursor="")
            self._set_status("Prêt")
        else:
            self._deselect()

    # ── Câblage ───────────────────────────────────────────────────────────────

    def _start_wiring(self, pin: tuple[int, str]):
        self._state    = "wiring"
        self._wire_src = pin
        self._canvas.configure(cursor="crosshair")
        comp = self._comps[pin[0]]
        self._set_status(f"Câblage depuis\n{comp.ref}.{pin[1]}\nClic sur un pin")

    def _complete_wire(self, dst: tuple[int, str]):
        src_cid, src_pin = self._wire_src
        dst_cid, dst_pin = dst
        # pas de doublon
        for w in self._wires:
            if ({w.from_comp_id, w.from_pin} == {src_cid, src_pin} and
                    {w.to_comp_id, w.to_pin} == {dst_cid, dst_pin}):
                self._cancel_wiring()
                return
        wire = WireInst(self._next_id, src_cid, src_pin, dst_cid, dst_pin)
        self._next_id += 1
        self._wires.append(wire)
        self._draw_wire(wire)
        self._cancel_wiring()

    def _cancel_wiring(self):
        self._state    = "idle"
        self._wire_src = None
        if self._rubber_band:
            self._canvas.delete(self._rubber_band)
            self._rubber_band = None
        self._canvas.configure(cursor="")
        self._set_status("Prêt")

    # ── Sélection ─────────────────────────────────────────────────────────────

    def _select(self, comp_id: int):
        if self._selected_id == comp_id:
            return
        self._deselect()
        self._selected_id = comp_id
        comp = self._comps.get(comp_id)
        if comp:
            defn  = COMP_DEFS[comp.comp_type]
            w2, h2 = defn["w"] // 2, defn["h"] // 2
            self._canvas.create_rectangle(
                comp.cx - w2 - 5, comp.cy - h2 - 5,
                comp.cx + w2 + 5, comp.cy + h2 + 5,
                outline="#4ade80", width=2, dash=(5, 3),
                tags=f"sel_{comp_id}",
            )

    def _deselect(self):
        if self._selected_id is not None:
            self._canvas.delete(f"sel_{self._selected_id}")
            self._selected_id = None

    # ── Édition / suppression ─────────────────────────────────────────────────

    def _edit_comp(self, comp_id: int):
        comp = self._comps.get(comp_id)
        if not comp:
            return
        dlg = tk.Toplevel(self)
        dlg.title(f"Modifier {comp.ref}")
        dlg.configure(bg="#1e293b")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.lift()

        for row, (lbl, var_init) in enumerate([("Référence :", comp.ref),
                                                ("Valeur :", comp.value)]):
            tk.Label(dlg, text=lbl, fg="#94a3b8", bg="#1e293b",
                     font=("Segoe UI", 10)).grid(row=row, column=0, padx=14,
                                                  pady=(14 if row == 0 else 6, 4),
                                                  sticky="w")
            var = tk.StringVar(value=var_init)
            e   = tk.Entry(dlg, textvariable=var, bg="#0f172a", fg="white",
                           font=("Segoe UI", 11), relief="flat", width=16,
                           insertbackground="white")
            e.grid(row=row, column=1, padx=(0, 14),
                   pady=(14 if row == 0 else 6, 4))
            if row == 0:
                ref_var = var
            else:
                val_var = var

        def _save():
            r = ref_var.get().strip()
            v = val_var.get().strip()
            if r:
                comp.ref   = r
            if v:
                comp.value = v
            self._draw_comp(comp)
            self._redraw_wires_of(comp_id)
            dlg.destroy()

        tk.Button(dlg, text="  OK  ", command=_save,
                  bg="#3b82f6", fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=16, pady=5,
                  cursor="hand2").grid(row=2, column=0, columnspan=2, pady=12)
        dlg.bind("<Return>", lambda _: _save())

    def _delete_selected(self):
        if self._selected_id is not None:
            self._delete_comp(self._selected_id)

    def _delete_comp(self, comp_id: int):
        if self._selected_id == comp_id:
            self._canvas.delete(f"sel_{comp_id}")
            self._selected_id = None
        to_rm = [w for w in self._wires
                 if w.from_comp_id == comp_id or w.to_comp_id == comp_id]
        for w in to_rm:
            self._canvas.delete(f"wire_{w.id}")
            self._wires.remove(w)
        self._canvas.delete(f"comp_{comp_id}")
        self._comps.pop(comp_id, None)

    def clear_all(self):
        from tkinter import messagebox
        if (self._comps or self._wires) and not messagebox.askyesno(
                "Effacer", "Effacer tout le schéma ?", parent=self):
            return
        self._canvas.delete("all")
        self._comps.clear()
        self._wires.clear()
        self._counters.clear()
        self._next_id     = 1
        self._state       = "idle"
        self._selected_id = None
        self._wire_src    = None
        self._rubber_band = None
        self._drag_comp_id = None
        self._draw_grid()
        self._set_status("Prêt")

    # ── Export netlist ────────────────────────────────────────────────────────

    def to_netlist(self) -> str:
        """@brief Génère une netlist SPICE depuis le schéma courant.

        @return str Netlist SPICE (vide si aucun composant).
        """
        real_comps = {cid: c for cid, c in self._comps.items()
                      if c.comp_type not in ("GND", "VCC")}
        if not real_comps:
            return ""

        # Union-Find sur les nœuds "{comp_id}:{pin_name}"
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent.get(x, x), parent.get(x, x))
                x = parent.get(x, x)
            return x

        def union(a: str, b: str):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for w in self._wires:
            union(f"{w.from_comp_id}:{w.from_pin}", f"{w.to_comp_id}:{w.to_pin}")

        # Nommer les nets
        net_names:   dict[str, str] = {}
        net_counter: list[int]      = [0]

        # Priorité aux nœuds GND / VCC (nets spéciaux)
        for comp in self._comps.values():
            if comp.comp_type in ("GND", "VCC"):
                root = find(f"{comp.id}:1")
                net_names[root] = comp.comp_type

        def net_of(node: str) -> str:
            root = find(node)
            if root not in net_names:
                net_counter[0] += 1
                net_names[root] = f"NET{net_counter[0]}"
            return net_names[root]

        lines = ["* Schéma généré par Circuit Analyzer — éditeur interactif", ""]
        for comp in real_comps.values():
            pins   = COMP_DEFS[comp.comp_type]["pins"]
            nets   = " ".join(net_of(f"{comp.id}:{pn}") for pn in pins)
            lines.append(f"{comp.ref} {nets} {comp.value}")

        return "\n".join(lines)

    # ── Utilitaires ───────────────────────────────────────────────────────────

    def _set_status(self, text: str):
        self._status_lbl.configure(text=text)

    def comp_count(self) -> int:
        return len([c for c in self._comps.values() if c.comp_type not in ("GND", "VCC")])
