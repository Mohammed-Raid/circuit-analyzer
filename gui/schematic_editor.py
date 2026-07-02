"""
@file schematic_editor.py
@brief Éditeur de schéma interactif : palette, canvas zoomable, placement, rotation, câblage.
"""
import copy
import logging
import math
import tkinter as tk
from dataclasses import dataclass, field
from typing import Optional

from circuit_analyzer.composant import charger_bibliotheque
from gui.schematic_io import editor_to_dict

_log = logging.getLogger(__name__)

GRID = 20  # pas de la grille en coordonnées monde

# Géométrie de dessin des types intégrés (couleur, taille, positions de broches).
# Les broches correspondent à TYPES_COMPOSANTS pour que la netlist exportée soit
# reconnue par l'analyseur. Les types personnalisés (onglet Composants) sont
# ajoutés dynamiquement via _auto_def().
COMP_DEFS: dict = {
    "R":   {"label": "Résistance",   "color": "#f97316", "w": 80, "h": 40,
            "pins": {"1": (-40, 0),  "2": (40, 0)},           "default_value": "10k"},
    "C":   {"label": "Condensateur", "color": "#3b82f6", "w": 60, "h": 40,
            "pins": {"1": (-30, 0),  "2": (30, 0)},           "default_value": "100n"},
    "L":   {"label": "Self",         "color": "#8b5cf6", "w": 80, "h": 40,
            "pins": {"1": (-40, 0),  "2": (40, 0)},           "default_value": "10µH"},
    "D":   {"label": "Diode",        "color": "#22c55e", "w": 60, "h": 40,
            "pins": {"A": (-30, 0),  "K": (30, 0)},           "default_value": "1N4148"},
    "F":   {"label": "Fusible",      "color": "#f59e0b", "w": 80, "h": 40,
            "pins": {"1": (-40, 0),  "2": (40, 0)},           "default_value": "1A"},
    "Q":   {"label": "BJT",          "color": "#ec4899", "w": 60, "h": 80,
            "pins": {"B": (-30, 0),  "C": (30, -30), "E": (30, 30)},
            "default_value": "2N2222"},
    "M":   {"label": "MOSFET",       "color": "#a855f7", "w": 60, "h": 80,
            "pins": {"G": (-30, 0),  "D": (30, -30), "S": (30, 30)},
            "default_value": "IRF540"},
    "U":   {"label": "AOP",          "color": "#06b6d4", "w": 80, "h": 80,
            "pins": {"IN+": (-40, -20), "IN-": (-40, 20), "OUT": (40, 0)},
            "default_value": "LM741"},
    "T":   {"label": "Transfo",      "color": "#0ea5e9", "w": 80, "h": 60,
            "pins": {"P1": (-40, -20), "P2": (-40, 20),
                     "S1": (40, -20),  "S2": (40, 20)},
            "default_value": ""},
    "K":   {"label": "Relais",       "color": "#eab308", "w": 80, "h": 60,
            "pins": {"A1": (-40, -20), "A2": (-40, 20),
                     "11": (40, -20),  "12": (40, 20)},
            "default_value": "RY1"},
    "SW":  {"label": "Interrupteur", "color": "#10b981", "w": 80, "h": 40,
            "pins": {"1": (-40, 0),  "2": (40, 0)},           "default_value": ""},
    "GND": {"label": "GND",          "color": "#94a3b8", "w": 40, "h": 40,
            "pins": {"1": (0, -20)},                           "default_value": "GND"},
    "VCC": {"label": "VCC",          "color": "#ef4444", "w": 40, "h": 40,
            "pins": {"1": (0, 20)},                            "default_value": "VCC"},
}

_AUTO_COLOR = "#94a3b8"   # couleur des composants personnalisés (boîte générique)


def _auto_def(name: str, pins: list) -> dict:
    """@brief Génère une géométrie générique pour un type personnalisé.

    Broches réparties moitié à gauche / moitié à droite d'une boîte rectangulaire ;
    aucun dessin sur-mesure n'est requis (le moteur de rendu gère ce cas).

    @param name Nom lisible du type (affiché comme libellé).
    @param pins Liste ordonnée des noms de broches.
    @return dict Entrée compatible COMP_DEFS (label, color, w, h, pins, default_value).
    """
    pins = [str(p) for p in pins]
    n = len(pins)
    half = (n + 1) // 2
    left, right = pins[:half], pins[half:]
    rows = max(len(left), len(right), 1)
    h = max(40, rows * 30 + 10)
    w = 80
    pinmap: dict = {}

    def _place(items, x):
        m = len(items)
        for i, pn in enumerate(items):
            y = int(round((i - (m - 1) / 2) * 30))
            pinmap[pn] = (x, y)

    _place(left, -w // 2)
    _place(right, w // 2)
    return {"label": name, "color": _AUTO_COLOR, "w": w, "h": h,
            "pins": pinmap, "default_value": ""}


def _compute_defs() -> dict:
    """@brief Defs effectives de l'éditeur : intégrés + types personnalisés générés.

    @return dict {type -> géométrie}. Les types intégrés (COMP_DEFS) priment ;
            les types perso de la bibliothèque reçoivent une géométrie auto.
    """
    defs = dict(COMP_DEFS)
    try:
        lib = charger_bibliotheque()
    except Exception:
        _log.warning("bibliothèque de composants illisible — types personnalisés "
                     "ignorés dans la palette", exc_info=True)
        lib = {}
    for key, val in lib.items():
        if key in defs:
            continue          # géométrie intégrée prioritaire
        broches = val.get("pins", [])
        if not broches:
            continue          # type sans broche : non plaçable
        defs[key] = _auto_def(val.get("name", key), broches)
    return defs

_PIN_R = 5     # rayon visuel pin
_HIT_R = 12   # rayon détection clic sur pin
_PIN_OFF = "#ef4444"   # contour des broches NON connectées (rouge = à câbler)


def _rotate_pin(dx: int, dy: int, rotation: int) -> tuple[int, int]:
    """Tourne un vecteur (dx,dy) de `rotation` degrés dans le sens horaire."""
    if rotation == 90:  return (dy, -dx)
    if rotation == 180: return (-dx, -dy)
    if rotation == 270: return (-dy, dx)
    return (dx, dy)


def _dist_to_segment(px, py, ax, ay, bx, by) -> float:
    """Distance du point (px,py) au segment (ax,ay)-(bx,by)."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax)*dx + (py - ay)*dy) / (dx*dx + dy*dy)))
    return math.hypot(px - ax - t*dx, py - ay - t*dy)


@dataclass
class CompInst:
    id:        int
    ref:       str
    comp_type: str
    value:     str
    cx:        int      # coordonnées monde
    cy:        int
    rotation:  int = 0  # 0, 90, 180, 270


@dataclass
class WireInst:
    id:           int
    from_comp_id: int
    from_pin:     str
    to_comp_id:   int
    to_pin:       str


class SchematicEditor(tk.Frame):
    """@brief Canvas interactif pour dessiner un schéma — zoom, rotation, câblage."""

    def __init__(self, parent):
        super().__init__(parent, bg="#0f172a")
        self._comps:    dict[int, CompInst] = {}
        self._wires:    list[WireInst]      = []
        self._next_id:  int                 = 1
        self._counters: dict[str, int]      = {}
        self._zoom:     float               = 1.0

        # machine à états : idle | placing | wiring
        self._state       = "idle"
        self._place_type: Optional[str]            = None
        self._selected_id: Optional[int]           = None
        self._wire_src:   Optional[tuple[int, str]] = None
        self._rubber_band: Optional[int]           = None

        # drag
        self._drag_comp_id: Optional[int] = None
        self._drag_moved:   bool          = False

        # piles d'annulation/rétablissement (Ctrl+Z / Ctrl+Y)
        self._undo_stack: list = []
        self._redo_stack: list = []
        self._UNDO_MAX = 50

        # presse-papier (Ctrl+C/V/D) : {type, value, rotation}
        self._clipboard: Optional[dict] = None
        # dernière position monde du curseur (cible du coller)
        self._cursor_w: tuple = (200, 200)

        # boutons palette (pour feedback visuel actif/inactif)
        self._palette_btns: dict[str, tk.Button] = {}
        self._palette_parent: Optional[tk.Frame] = None

        # géométrie effective : intégrés + types personnalisés (bibliothèque)
        self._defs: dict = _compute_defs()

        self._build()

    # ── Annulation / rétablissement (Ctrl+Z / Ctrl+Y) ──────────────────────────

    def _snapshot(self) -> tuple:
        """@brief Instantané profond de l'état mutable (comps, fils, compteurs, id)."""
        return (
            copy.deepcopy(self._comps),
            copy.deepcopy(self._wires),
            dict(self._counters),
            self._next_id,
        )

    def _push_undo(self):
        """@brief Empile l'état courant avant une mutation et invalide le redo."""
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > self._UNDO_MAX:
            self._undo_stack.pop(0)
        # Une nouvelle action rend le « rétablir » caduc.
        self._redo_stack.clear()

    def _restore(self, snap: tuple):
        """@brief Restaure un instantané et réinitialise les états transitoires."""
        comps, wires, counters, next_id = snap
        self._comps    = comps
        self._wires    = wires
        self._counters = counters
        self._next_id  = next_id
        self._selected_id  = None
        self._drag_comp_id = None
        self._drag_moved   = False
        if self._state == "wiring":
            self._cancel_wiring()
        self._redraw_all()

    def _undo(self, _=None):
        """@brief Annule la dernière mutation (Ctrl+Z)."""
        if not self._undo_stack:
            self._set_status("Rien à\nannuler")
            return
        self._redo_stack.append(self._snapshot())
        self._restore(self._undo_stack.pop())
        self._set_status("Annulé ↶")

    def _redo(self, _=None):
        """@brief Rétablit la dernière annulation (Ctrl+Y)."""
        if not self._redo_stack:
            self._set_status("Rien à\nrétablir")
            return
        self._undo_stack.append(self._snapshot())
        self._restore(self._redo_stack.pop())
        self._set_status("Rétabli ↷")

    # ── Système de coordonnées ────────────────────────────────────────────────

    def _w2s(self, wx, wy):
        """Monde → écran (canvas)."""
        return wx * self._zoom, wy * self._zoom

    def _s2w(self, sx, sy):
        """Écran → monde."""
        return sx / self._zoom, sy / self._zoom

    def _cc(self, event):
        """Coordonnées canvas (écran) depuis un événement."""
        return self._canvas.canvasx(event.x), self._canvas.canvasy(event.y)

    def _cw(self, event):
        """Coordonnées monde depuis un événement."""
        sx, sy = self._cc(event)
        return self._s2w(sx, sy)

    def _snap(self, wx, wy):
        """Aligne sur la grille (en coordonnées monde)."""
        return round(wx / GRID) * GRID, round(wy / GRID) * GRID

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self):
        # Palette défilable : conteneur fixe (largeur 152) + canvas interne, pour
        # que tous les composants/boutons restent accessibles même fenêtre courte
        # ou avec la mise à l'échelle Windows (125/150 %).
        palette_outer = tk.Frame(self, bg="#1e293b", width=174)
        palette_outer.pack(side="left", fill="y")
        palette_outer.pack_propagate(False)

        pcanvas = tk.Canvas(palette_outer, bg="#1e293b", highlightthickness=0,
                            bd=0, width=158)
        psb = tk.Scrollbar(palette_outer, orient="vertical", command=pcanvas.yview)
        pcanvas.configure(yscrollcommand=psb.set)
        psb.pack(side="right", fill="y")
        pcanvas.pack(side="left", fill="both", expand=True)

        palette = tk.Frame(pcanvas, bg="#1e293b")
        pcanvas.create_window((0, 0), window=palette, anchor="nw", width=158)
        palette.bind("<Configure>",
                     lambda _e: pcanvas.configure(scrollregion=pcanvas.bbox("all")))
        # Molette active seulement quand le curseur est sur la palette (sinon
        # elle entrerait en conflit avec le défilement du canvas de dessin).
        pcanvas.bind("<Enter>", lambda _e: pcanvas.bind_all(
            "<MouseWheel>",
            lambda ev: pcanvas.yview_scroll(int(-ev.delta / 120), "units")))
        pcanvas.bind("<Leave>", lambda _e: pcanvas.unbind_all("<MouseWheel>"))

        self._build_palette(palette)

        wrap = tk.Frame(self, bg="#0f172a")
        wrap.pack(side="left", fill="both", expand=True)
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(wrap, bg="#0f172a", highlightthickness=0,
                                  scrollregion=(0, 0, 2400, 1800))
        vsb = tk.Scrollbar(wrap, orient="vertical",   command=self._canvas.yview)
        hsb = tk.Scrollbar(wrap, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._draw_grid()
        self._bind_events()

    def _build_palette(self, parent):
        self._palette_parent = parent
        self._palette_btns = {}
        tk.Label(parent, text="COMPOSANTS", fg="#64748b", bg="#1e293b",
                 font=("Segoe UI", 8, "bold")).pack(pady=(14, 4), padx=8, anchor="w")

        for ct, defn in self._defs.items():
            color = defn["color"]
            b = tk.Button(
                parent,
                text=f"{ct}  {defn['label']}",
                bg="#1e293b", fg=color,
                activebackground="#263347", activeforeground=color,
                relief="flat", anchor="w",
                font=("Segoe UI", 9, "bold"), cursor="hand2", padx=10,
                command=lambda t=ct: self._start_placing(t),
            )
            b.pack(fill="x", padx=4, pady=2)
            self._palette_btns[ct] = b

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
        tk.Button(parent, text="⊡  Ajuster (F)",
                  bg="#1e293b", fg="#60a5fa", activebackground="#263347",
                  activeforeground="#60a5fa", relief="flat", anchor="w",
                  font=("Segoe UI", 9), cursor="hand2", padx=10,
                  command=self.fit_to_view).pack(fill="x", padx=4, pady=2)

        tk.Frame(parent, bg="#334155", height=1).pack(fill="x", padx=8, pady=8)

        self._status_lbl = tk.Label(
            parent,
            text="Clic = placer\nEspace/R = rotation\nCtrl+C/V = copier/coller\nCtrl+D = dupliquer\n"
                 "Ctrl+Z/Y = annuler/rétablir\nClic droit = menu\nF = ajuster · Ctrl+molette = zoom",
            fg="#475569", bg="#1e293b",
            font=("Segoe UI", 7), justify="center",
        )
        self._status_lbl.pack(padx=8, pady=4)

    def refresh_palette(self):
        """@brief Recharge la bibliothèque et reconstruit la palette.

        Appelé quand l'onglet Composants modifie la bibliothèque : un nouveau type
        apparaît dans la palette, un type supprimé en disparaît. Les composants
        déjà posés d'un type devenu inconnu sont retirés du canvas (avec leurs
        fils) pour éviter un plantage au redessin.
        """
        self._defs = _compute_defs()

        # Purge des composants dont le type n'existe plus dans la bibliothèque.
        obsoletes = {cid for cid, c in self._comps.items()
                     if c.comp_type not in self._defs}
        if obsoletes:
            self._wires = [w for w in self._wires
                           if w.from_comp_id not in obsoletes
                           and w.to_comp_id not in obsoletes]
            for cid in obsoletes:
                self._comps.pop(cid, None)
            if self._selected_id in obsoletes:
                self._selected_id = None
            # Un instantané d'annulation pourrait contenir un type disparu :
            # on vide la pile plutôt que de risquer un redessin impossible.
            self._undo_stack.clear()

        if self._state == "wiring":
            self._cancel_wiring()

        if self._palette_parent is not None:
            for w in self._palette_parent.winfo_children():
                w.destroy()
            self._build_palette(self._palette_parent)

        self._redraw_all()

    def _draw_grid(self):
        """Grille légère (lignes) — 210 items au lieu de 10 800."""
        self._canvas.delete("grid")
        z = self._zoom
        W = int(2400 * z)
        H = int(1800 * z)
        step = GRID * z
        x = 0.0
        while x <= W + 1:
            ix = int(x)
            self._canvas.create_line(ix, 0, ix, H, fill="#141e2e", width=1, tags="grid")
            x += step
        y = 0.0
        while y <= H + 1:
            iy = int(y)
            self._canvas.create_line(0, iy, W, iy, fill="#141e2e", width=1, tags="grid")
            y += step
        self._canvas.configure(scrollregion=(0, 0, W, H))
        self._canvas.tag_lower("grid")

    def _bind_events(self):
        c = self._canvas
        c.bind("<Button-1>",         self._on_click)
        c.bind("<B1-Motion>",        self._on_b1_motion)
        c.bind("<ButtonRelease-1>",  self._on_b1_release)
        c.bind("<Motion>",           self._on_motion)
        c.bind("<Double-Button-1>",  self._on_double_click)
        c.bind("<Button-3>",         self._on_right_click)
        c.bind("<Delete>",           self._on_delete)
        c.bind("<BackSpace>",        self._on_delete)
        c.bind("<Escape>",           self._on_escape)
        c.bind("<r>",                self._on_rotate)
        c.bind("<R>",                self._on_rotate)
        c.bind("<space>",            self._on_rotate)
        c.bind("<Control-z>",        self._undo)
        c.bind("<Control-Z>",        self._undo)
        c.bind("<Control-y>",        self._redo)
        c.bind("<Control-Y>",        self._redo)
        c.bind("<Control-c>",        self._copy)
        c.bind("<Control-C>",        self._copy)
        c.bind("<Control-v>",        self._paste)
        c.bind("<Control-V>",        self._paste)
        c.bind("<Control-d>",        self._duplicate)
        c.bind("<Control-D>",        self._duplicate)
        c.bind("<f>",                self.fit_to_view)
        c.bind("<F>",                self.fit_to_view)
        c.bind("<Control-MouseWheel>", self._on_zoom)
        c.bind("<MouseWheel>",       lambda e: c.yview_scroll(int(-e.delta / 120), "units"))
        c.bind("<Shift-MouseWheel>", lambda e: c.xview_scroll(int(-e.delta / 120), "units"))
        c.focus_set()

    # ── Zoom ─────────────────────────────────────────────────────────────────

    def _on_zoom(self, event):
        factor = 1.15 if event.delta > 0 else (1 / 1.15)
        self._zoom = max(0.2, min(5.0, self._zoom * factor))
        self._redraw_all()

    def _redraw_all(self):
        """Redessine tout le canvas (utilisé après zoom)."""
        self._canvas.delete("all")
        self._draw_grid()
        for comp in self._comps.values():
            self._draw_comp(comp)
        for wire in self._wires:
            self._draw_wire(wire)
        if self._selected_id is not None:
            sid = self._selected_id
            self._selected_id = None
            self._select(sid)

    # ── Placement ────────────────────────────────────────────────────────────

    def _start_placing(self, comp_type: str):
        self._cancel_wiring()
        self._deselect()
        self._state      = "placing"
        self._place_type = comp_type
        self._canvas.configure(cursor="crosshair")
        # Feedback visuel dans la palette
        for t, btn in self._palette_btns.items():
            btn.configure(bg="#1e293b", relief="flat")
        self._palette_btns[comp_type].configure(bg="#263347", relief="groove")
        self._set_status(f"Clic pour\nplacer {comp_type}\nÉchap = annuler")

    def _place_comp(self, wx: int, wy: int):
        """Place un composant en coordonnées monde — reste en mode placing."""
        self._push_undo()
        t    = self._place_type
        defn = self._defs[t]
        n    = self._counters.get(t, 0) + 1
        self._counters[t] = n
        # GND et VCC n'ont pas de numéro affiché
        ref  = f"{t}{n}" if t not in ("GND", "VCC") else t
        comp = CompInst(self._next_id, ref, t, defn["default_value"], wx, wy)
        self._next_id += 1
        self._comps[comp.id] = comp
        self._draw_comp(comp)
        # Reste en mode placing (Échap pour sortir)
        self._set_status(f"Placé {ref}\nClic = autre\nÉchap = stop")

    # ── Rendu ────────────────────────────────────────────────────────────────

    def _draw_comp(self, comp: CompInst):
        defn  = self._defs[comp.comp_type]
        color = defn["color"]
        z     = self._zoom
        rot   = comp.rotation
        scx, scy = self._w2s(comp.cx, comp.cy)
        w2, h2   = defn["w"] // 2, defn["h"] // 2
        # Pour 90°/270°, les dimensions s'échangent
        rw2 = (w2 if rot % 180 == 0 else h2) * z
        rh2 = (h2 if rot % 180 == 0 else w2) * z
        pr   = max(2, _PIN_R * z)
        tag  = f"comp_{comp.id}"
        self._canvas.delete(tag)

        if comp.comp_type == "GND":
            dx, dy = _rotate_pin(0, -20, rot)
            spx, spy = scx + dx*z, scy + dy*z  # pin (haut)
            d1x, d1y = _rotate_pin(0, -20, rot)
            d2x, d2y = _rotate_pin(0, 0, rot)
            self._canvas.create_line(scx+d1x*z, scy+d1y*z,
                                     scx+d2x*z, scy+d2y*z,
                                     fill=color, width=max(1, int(2*z)), tags=tag)
            for i, hw in enumerate([16, 10, 5]):
                bx, by = _rotate_pin(0, i*5, rot)
                lx, ly = _rotate_pin(hw, i*5, rot)
                rx, ry = _rotate_pin(-hw, i*5, rot)
                self._canvas.create_line(
                    scx+lx*z, scy+ly*z, scx+rx*z, scy+ry*z,
                    fill=color, width=max(1, int(2*z)), tags=tag)
            tx, ty = _rotate_pin(0, -28, rot)
            self._canvas.create_text(scx+tx*z, scy+ty*z,
                                     text="GND", fill=color,
                                     font=("Consolas", max(7, int(8*z))), tags=tag)
            # pin circle
            pfill, pout = self._pin_style(comp.id, "1", color)
            self._canvas.create_oval(spx-pr, spy-pr, spx+pr, spy+pr,
                                     fill=pfill, outline=pout,
                                     width=max(1, int(2*z)),
                                     tags=(tag, f"pin_{comp.id}_1"))

        elif comp.comp_type == "VCC":
            dx, dy = _rotate_pin(0, 20, rot)
            spx, spy = scx + dx*z, scy + dy*z  # pin (bas)
            d1x, d1y = _rotate_pin(0, 20, rot)
            d2x, d2y = _rotate_pin(0, 2, rot)
            self._canvas.create_line(scx+d1x*z, scy+d1y*z,
                                     scx+d2x*z, scy+d2y*z,
                                     fill=color, width=max(1, int(2*z)), tags=tag)
            # Flèche triangulaire
            p0x, p0y = _rotate_pin(-10, 2, rot)
            p1x, p1y = _rotate_pin(10, 2, rot)
            p2x, p2y = _rotate_pin(0, -14, rot)
            self._canvas.create_polygon(
                scx+p0x*z, scy+p0y*z,
                scx+p1x*z, scy+p1y*z,
                scx+p2x*z, scy+p2y*z,
                fill=color, outline="", tags=tag)
            tx, ty = _rotate_pin(0, 30, rot)
            self._canvas.create_text(scx+tx*z, scy+ty*z,
                                     text="VCC", fill=color,
                                     font=("Consolas", max(7, int(8*z))), tags=tag)
            pfill, pout = self._pin_style(comp.id, "1", color)
            self._canvas.create_oval(spx-pr, spy-pr, spx+pr, spy+pr,
                                     fill=pfill, outline=pout,
                                     width=max(1, int(2*z)),
                                     tags=(tag, f"pin_{comp.id}_1"))

        else:
            # Rectangle + labels
            self._canvas.create_rectangle(
                scx - rw2, scy - rh2, scx + rw2, scy + rh2,
                fill="#0f172a", outline=color,
                width=max(1, int(2*z)), tags=tag)
            lbx, lby = _rotate_pin(-w2 + 6, -h2 + 8, rot)
            self._canvas.create_text(
                scx + lbx*z, scy + lby*z,
                text=comp.comp_type, fill=color,
                font=("Consolas", max(6, int(8*z)), "bold"),
                anchor="center", tags=tag)
            rx, ry = _rotate_pin(0, -8, rot)
            self._canvas.create_text(scx+rx*z, scy+ry*z,
                                     text=comp.ref, fill="#e2e8f0",
                                     font=("Consolas", max(7, int(9*z)), "bold"),
                                     tags=tag)
            vx, vy = _rotate_pin(0, 8, rot)
            self._canvas.create_text(scx+vx*z, scy+vy*z,
                                     text=comp.value, fill="#64748b",
                                     font=("Consolas", max(6, int(8*z))),
                                     tags=tag)

            # Pins
            nb_pins = len(defn["pins"])
            for pn, (pdx, pdy) in defn["pins"].items():
                rdx, rdy = _rotate_pin(pdx, pdy, rot)
                spx = scx + rdx * z
                spy = scy + rdy * z
                pfill, pout = self._pin_style(comp.id, pn, color)
                self._canvas.create_oval(spx-pr, spy-pr, spx+pr, spy+pr,
                                         fill=pfill, outline=pout,
                                         width=max(1, int(2*z)),
                                         tags=(tag, f"pin_{comp.id}_{pn}"))
                if nb_pins > 2:
                    anch = "e" if rdx < 0 else "w"
                    ox = -8*z if rdx < 0 else 8*z
                    self._canvas.create_text(spx+ox, spy,
                                             text=pn, fill="#475569",
                                             font=("Consolas", max(5, int(7*z))),
                                             anchor=anch, tags=tag)

    def _draw_wire(self, wire: WireInst):
        ca = self._comps.get(wire.from_comp_id)
        cb = self._comps.get(wire.to_comp_id)
        if not ca or not cb:
            return
        dx_a, dy_a = self._defs[ca.comp_type]["pins"][wire.from_pin]
        rdx_a, rdy_a = _rotate_pin(dx_a, dy_a, ca.rotation)
        dx_b, dy_b = self._defs[cb.comp_type]["pins"][wire.to_pin]
        rdx_b, rdy_b = _rotate_pin(dx_b, dy_b, cb.rotation)

        wx1, wy1 = ca.cx + rdx_a, ca.cy + rdy_a
        wx2, wy2 = cb.cx + rdx_b, cb.cy + rdy_b
        sx1, sy1 = self._w2s(wx1, wy1)
        sx2, sy2 = self._w2s(wx2, wy2)

        tag = f"wire_{wire.id}"
        self._canvas.delete(tag)
        lw = max(1, int(2 * self._zoom))
        self._canvas.create_line(sx1, sy1, sx2, sy1, sx2, sy2,
                                  fill="#475569", width=lw,
                                  joinstyle="round", tags=tag)

    def _redraw_wires_of(self, comp_id: int):
        for w in self._wires:
            if w.from_comp_id == comp_id or w.to_comp_id == comp_id:
                self._draw_wire(w)

    def _pin_connected(self, comp_id: int, pin: str) -> bool:
        """@brief Vrai si au moins un fil est rattaché à cette broche."""
        return any(
            (w.from_comp_id == comp_id and w.from_pin == pin) or
            (w.to_comp_id == comp_id and w.to_pin == pin)
            for w in self._wires
        )

    def _pin_style(self, comp_id: int, pin: str, color: str) -> tuple[str, str]:
        """@brief (fill, outline) d'une broche : pleine si connectée, rouge creuse sinon."""
        if self._pin_connected(comp_id, pin):
            return color, color
        return "#0f172a", _PIN_OFF

    # ── Hit-testing (en coordonnées monde) ───────────────────────────────────

    def _find_pin_at(self, wx, wy) -> Optional[tuple[int, str]]:
        tol = _HIT_R / self._zoom  # rayon de détection en coordonnées monde
        for comp in self._comps.values():
            for pn, (dx, dy) in self._defs[comp.comp_type]["pins"].items():
                rdx, rdy = _rotate_pin(dx, dy, comp.rotation)
                px, py = comp.cx + rdx, comp.cy + rdy
                if (wx - px)**2 + (wy - py)**2 <= tol**2:
                    return (comp.id, pn)
        return None

    def _find_comp_at(self, wx, wy) -> Optional[int]:
        for comp in self._comps.values():
            defn = self._defs[comp.comp_type]
            rot  = comp.rotation
            w2 = (defn["w"] // 2 if rot % 180 == 0 else defn["h"] // 2) + 6
            h2 = (defn["h"] // 2 if rot % 180 == 0 else defn["w"] // 2) + 6
            if comp.cx - w2 <= wx <= comp.cx + w2 and comp.cy - h2 <= wy <= comp.cy + h2:
                return comp.id
        return None

    def _find_wire_at(self, wx, wy, tol=8) -> Optional[int]:
        """Cherche un fil proche de (wx,wy) en coordonnées monde."""
        tol_w = tol / self._zoom
        for w in self._wires:
            ca = self._comps.get(w.from_comp_id)
            cb = self._comps.get(w.to_comp_id)
            if not ca or not cb:
                continue
            dx_a, dy_a = self._defs[ca.comp_type]["pins"][w.from_pin]
            rdx_a, rdy_a = _rotate_pin(dx_a, dy_a, ca.rotation)
            dx_b, dy_b = self._defs[cb.comp_type]["pins"][w.to_pin]
            rdx_b, rdy_b = _rotate_pin(dx_b, dy_b, cb.rotation)
            x1, y1 = ca.cx + rdx_a, ca.cy + rdy_a
            x2, y2 = cb.cx + rdx_b, cb.cy + rdy_b
            # Fil en L : (x1,y1)→(x2,y1)→(x2,y2)
            d1 = _dist_to_segment(wx, wy, x1, y1, x2, y1)
            d2 = _dist_to_segment(wx, wy, x2, y1, x2, y2)
            if min(d1, d2) < tol_w:
                return w.id
        return None

    # ── Événements ───────────────────────────────────────────────────────────

    def _on_click(self, event):
        self._canvas.focus_set()
        wx, wy   = self._cw(event)
        swx, swy = self._snap(wx, wy)

        if self._state == "placing":
            self._place_comp(swx, swy)
            return

        if self._state == "wiring":
            pin = self._find_pin_at(wx, wy)
            if pin and pin != self._wire_src:
                self._complete_wire(pin)
            else:
                self._cancel_wiring()
            return

        # IDLE : priorité pin > composant
        pin = self._find_pin_at(wx, wy)
        if pin:
            self._start_wiring(pin)
            return

        comp_id = self._find_comp_at(wx, wy)
        if comp_id:
            self._select(comp_id)
            self._drag_comp_id = comp_id
            self._drag_moved   = False
        else:
            self._deselect()

    def _on_b1_motion(self, event):
        if self._state == "idle" and self._drag_comp_id is not None:
            wx, wy   = self._cw(event)
            swx, swy = self._snap(wx, wy)
            comp = self._comps.get(self._drag_comp_id)
            if comp and (comp.cx != swx or comp.cy != swy):
                # Empile l'annulation une seule fois, au premier déplacement réel
                # (un simple clic de sélection ne crée pas d'instantané).
                if not self._drag_moved:
                    self._push_undo()
                    self._drag_moved = True
                comp.cx, comp.cy = swx, swy
                self._draw_comp(comp)
                self._redraw_wires_of(self._drag_comp_id)
                self._deselect()
                self._select(self._drag_comp_id)

    def _on_b1_release(self, _=None):
        self._drag_comp_id = None
        self._drag_moved   = False

    def _on_motion(self, event):
        self._cursor_w = self._cw(event)
        if self._state == "wiring" and self._wire_src:
            sx, sy = self._cc(event)
            comp = self._comps.get(self._wire_src[0])
            if comp:
                dx, dy = self._defs[comp.comp_type]["pins"][self._wire_src[1]]
                rdx, rdy = _rotate_pin(dx, dy, comp.rotation)
                x1, y1 = self._w2s(comp.cx + rdx, comp.cy + rdy)
                if self._rubber_band:
                    self._canvas.delete(self._rubber_band)
                self._rubber_band = self._canvas.create_line(
                    x1, y1, sx, y1, sx, sy,
                    fill="#4ade80", width=max(1, int(2*self._zoom)), dash=(5, 3))

    def _on_double_click(self, event):
        wx, wy  = self._cw(event)
        comp_id = self._find_comp_at(wx, wy)
        if comp_id:
            self._edit_comp(comp_id)

    def _on_right_click(self, event):
        wx, wy = self._cw(event)

        # Priorité 1 : fil
        wire_id = self._find_wire_at(wx, wy)
        if wire_id is not None:
            m = tk.Menu(self._canvas, tearoff=0, bg="#1e293b", fg="white",
                        activebackground="#3b82f6", activeforeground="white")
            m.add_command(label="🗑  Supprimer ce fil",
                          command=lambda: self._delete_wire(wire_id))
            m.post(event.x_root, event.y_root)
            return

        # Priorité 2 : composant
        comp_id = self._find_comp_at(wx, wy)
        if not comp_id:
            return
        self._select(comp_id)
        m = tk.Menu(self._canvas, tearoff=0, bg="#1e293b", fg="white",
                    activebackground="#3b82f6", activeforeground="white")
        m.add_command(label="✏  Modifier…",  command=lambda: self._edit_comp(comp_id))
        m.add_command(label="↻  Rotation",   command=lambda: self._rotate_comp(comp_id))
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
            for btn in self._palette_btns.values():
                btn.configure(bg="#1e293b", relief="flat")
            self._set_status("Prêt")
        else:
            self._deselect()

    def _on_rotate(self, _=None):
        if self._selected_id is not None:
            self._rotate_comp(self._selected_id)

    # ── Copier / coller / dupliquer ───────────────────────────────────────────

    def _add_comp(self, comp_type: str, value: str, rotation: int,
                  wx: int, wy: int) -> Optional['CompInst']:
        """@brief Crée, dessine et sélectionne un nouveau composant.

        Numérote la référence via le compteur du type (ex. R3). N'empile PAS
        l'annulation (l'appelant le fait), pour grouper coller/dupliquer en une
        seule étape annulable.

        @return CompInst créé, ou None si le type est inconnu.
        """
        if comp_type not in self._defs:
            return None
        n = self._counters.get(comp_type, 0) + 1
        self._counters[comp_type] = n
        ref = f"{comp_type}{n}" if comp_type not in ("GND", "VCC") else comp_type
        comp = CompInst(self._next_id, ref, comp_type, value, wx, wy, rotation)
        self._next_id += 1
        self._comps[comp.id] = comp
        self._draw_comp(comp)
        self._deselect()
        self._select(comp.id)
        return comp

    def _copy(self, _=None):
        """@brief Copie le composant sélectionné dans le presse-papier (Ctrl+C)."""
        comp = self._comps.get(self._selected_id) if self._selected_id else None
        if not comp:
            return
        self._clipboard = {"type": comp.comp_type, "value": comp.value,
                           "rotation": comp.rotation}
        self._set_status(f"Copié\n{comp.ref}")

    def _paste(self, _=None):
        """@brief Colle le composant du presse-papier à la position du curseur (Ctrl+V)."""
        if not self._clipboard:
            return
        wx, wy = self._snap(*self._cursor_w)
        self._push_undo()
        comp = self._add_comp(self._clipboard["type"], self._clipboard["value"],
                              self._clipboard["rotation"], wx, wy)
        if comp is None:
            # Type devenu inconnu : annule l'instantané inutile.
            self._undo_stack.pop()
            return
        self._set_status(f"Collé\n{comp.ref}")

    def _duplicate(self, _=None):
        """@brief Duplique le composant sélectionné en décalé (Ctrl+D)."""
        src = self._comps.get(self._selected_id) if self._selected_id else None
        if not src:
            return
        self._clipboard = {"type": src.comp_type, "value": src.value,
                           "rotation": src.rotation}
        self._push_undo()
        comp = self._add_comp(src.comp_type, src.value, src.rotation,
                              src.cx + GRID * 2, src.cy + GRID * 2)
        if comp is None:
            self._undo_stack.pop()
            return
        self._set_status(f"Dupliqué\n{comp.ref}")

    # ── Recentrer / ajuster à l'écran ─────────────────────────────────────────

    def fit_to_view(self, _=None):
        """@brief Ajuste le zoom et le défilement pour montrer tout le schéma (F)."""
        if not self._comps:
            self._zoom = 1.0
            self._redraw_all()
            self._canvas.xview_moveto(0)
            self._canvas.yview_moveto(0)
            self._set_status("Vue\nréinitialisée")
            return

        xs, ys = [], []
        for c in self._comps.values():
            d = self._defs[c.comp_type]
            w2, h2 = d["w"] // 2 + 30, d["h"] // 2 + 30
            xs += [c.cx - w2, c.cx + w2]
            ys += [c.cy - h2, c.cy + h2]
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
        bw, bh = max(1, maxx - minx), max(1, maxy - miny)

        cw = self._canvas.winfo_width()  or 800
        ch = self._canvas.winfo_height() or 600
        self._zoom = max(0.2, min(3.0, min(cw / bw, ch / bh)))
        self._redraw_all()

        # Centre la bbox dans la zone visible.
        total_w, total_h = 2400 * self._zoom, 1800 * self._zoom
        cx_s = ((minx + maxx) / 2) * self._zoom
        cy_s = ((miny + maxy) / 2) * self._zoom
        self._canvas.xview_moveto(max(0.0, (cx_s - cw / 2) / total_w))
        self._canvas.yview_moveto(max(0.0, (cy_s - ch / 2) / total_h))
        self._set_status("Ajusté ⊡")

    # ── Câblage ──────────────────────────────────────────────────────────────

    def _start_wiring(self, pin: tuple[int, str]):
        self._state    = "wiring"
        self._wire_src = pin
        self._canvas.configure(cursor="crosshair")
        comp = self._comps[pin[0]]
        self._set_status(f"Fil depuis\n{comp.ref}.{pin[1]}\nClic = cible\nÉchap = annuler")

    def _complete_wire(self, dst: tuple[int, str]):
        src_cid, src_pin = self._wire_src
        dst_cid, dst_pin = dst
        # éviter les doublons
        for w in self._wires:
            if ({w.from_comp_id, w.from_pin} == {src_cid, src_pin} and
                    {w.to_comp_id, w.to_pin} == {dst_cid, dst_pin}):
                self._cancel_wiring()
                return
        self._push_undo()
        wire = WireInst(self._next_id, src_cid, src_pin, dst_cid, dst_pin)
        self._next_id += 1
        self._wires.append(wire)
        self._draw_wire(wire)
        # Rafraîchit les broches des 2 composants (passent de « rouge » à pleines)
        for cid in (src_cid, dst_cid):
            if cid in self._comps:
                self._draw_comp(self._comps[cid])
                self._redraw_wires_of(cid)
        self._cancel_wiring()

    def _cancel_wiring(self):
        self._state    = "idle"
        self._wire_src = None
        if self._rubber_band:
            self._canvas.delete(self._rubber_band)
            self._rubber_band = None
        self._canvas.configure(cursor="")
        self._set_status("Prêt")

    # ── Sélection ────────────────────────────────────────────────────────────

    def _select(self, comp_id: int):
        if self._selected_id == comp_id:
            return
        self._deselect()
        self._selected_id = comp_id
        comp = self._comps.get(comp_id)
        if comp:
            defn  = self._defs[comp.comp_type]
            rot   = comp.rotation
            z     = self._zoom
            rw2 = ((defn["w"] // 2 if rot % 180 == 0 else defn["h"] // 2) + 5) * z
            rh2 = ((defn["h"] // 2 if rot % 180 == 0 else defn["w"] // 2) + 5) * z
            scx, scy = self._w2s(comp.cx, comp.cy)
            self._canvas.create_rectangle(
                scx - rw2, scy - rh2, scx + rw2, scy + rh2,
                outline="#4ade80", width=max(1, int(2*z)),
                dash=(5, 3), tags=f"sel_{comp_id}")

    def _deselect(self):
        if self._selected_id is not None:
            self._canvas.delete(f"sel_{self._selected_id}")
            self._selected_id = None

    # ── Édition / suppression ─────────────────────────────────────────────────

    def _rotate_comp(self, comp_id: int):
        comp = self._comps.get(comp_id)
        if comp and comp.comp_type not in ("GND", "VCC"):
            self._push_undo()
            comp.rotation = (comp.rotation + 90) % 360
            self._draw_comp(comp)
            self._redraw_wires_of(comp_id)
            if self._selected_id == comp_id:
                self._deselect()
                self._select(comp_id)

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

        fields = [("Référence :", comp.ref), ("Valeur :", comp.value)]
        vars_list = []
        for row, (lbl, val) in enumerate(fields):
            tk.Label(dlg, text=lbl, fg="#94a3b8", bg="#1e293b",
                     font=("Segoe UI", 10)).grid(row=row, column=0, padx=14,
                                                  pady=(14 if row == 0 else 6, 4),
                                                  sticky="w")
            v = tk.StringVar(value=val)
            tk.Entry(dlg, textvariable=v, bg="#0f172a", fg="white",
                     font=("Segoe UI", 11), relief="flat", width=16,
                     insertbackground="white").grid(row=row, column=1,
                                                     padx=(0, 14),
                                                     pady=(14 if row == 0 else 6, 4))
            vars_list.append(v)

        def _save():
            r = vars_list[0].get().strip()
            v = vars_list[1].get().strip()
            # N'empile une annulation que si quelque chose change vraiment.
            if (r and r != comp.ref) or (v and v != comp.value):
                self._push_undo()
            if r: comp.ref   = r
            if v: comp.value = v
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
        if comp_id not in self._comps:
            return
        self._push_undo()
        if self._selected_id == comp_id:
            self._canvas.delete(f"sel_{comp_id}")
            self._selected_id = None
        # Composants voisins dont une broche redeviendra non connectée.
        voisins = set()
        for w in [w for w in self._wires
                  if w.from_comp_id == comp_id or w.to_comp_id == comp_id]:
            voisins.add(w.to_comp_id if w.from_comp_id == comp_id else w.from_comp_id)
            self._canvas.delete(f"wire_{w.id}")
            self._wires.remove(w)
        self._canvas.delete(f"comp_{comp_id}")
        self._comps.pop(comp_id, None)
        for cid in voisins:
            if cid in self._comps:
                self._draw_comp(self._comps[cid])
                self._redraw_wires_of(cid)

    def _delete_wire(self, wire_id: int):
        wire = next((w for w in self._wires if w.id == wire_id), None)
        if wire:
            self._push_undo()
            self._canvas.delete(f"wire_{wire_id}")
            self._wires.remove(wire)
            # Broches des 2 extrémités : peuvent redevenir non connectées (rouge).
            for cid in (wire.from_comp_id, wire.to_comp_id):
                if cid in self._comps:
                    self._draw_comp(self._comps[cid])
                    self._redraw_wires_of(cid)

    def clear_all(self):
        from tkinter import messagebox
        if (self._comps or self._wires) and not messagebox.askyesno(
                "Effacer", "Effacer tout le schéma ?", parent=self):
            return
        # Empile avant d'effacer pour que Ctrl+Z restaure le schéma.
        if self._comps or self._wires:
            self._push_undo()
        self._canvas.delete("all")
        self._comps.clear()
        self._wires.clear()
        self._counters.clear()
        self._next_id      = 1
        self._state        = "idle"
        self._selected_id  = None
        self._wire_src     = None
        self._rubber_band  = None
        self._drag_comp_id = None
        for btn in self._palette_btns.values():
            btn.configure(bg="#1e293b", relief="flat")
        self._draw_grid()
        self._set_status("Prêt")

    # ── Sauvegarde / chargement (.circ) ───────────────────────────────────────

    def to_dict(self) -> dict:
        """@brief Sérialise le schéma courant au format .circ.

        @return dict Document .circ (composants, fils, compteurs, next_id).
        """
        return editor_to_dict(self._comps, self._wires,
                              self._counters, self._next_id)

    def load_dict(self, d: dict):
        """@brief Remplace le schéma courant par celui décrit par un dict .circ.

        Valide format/version AVANT toute mutation (le dessin courant est préservé
        en cas d'erreur). Ignore les composants de type inconnu et les fils dont
        une broche n'existe pas dans la géométrie courante.

        @param d Document .circ (natif ou produit par build_from_components).
        @throws ValueError Si le format ou la version n'est pas reconnu.
        """
        if not isinstance(d, dict) or d.get("format") != "circ":
            raise ValueError("Format de fichier non reconnu (.circ attendu).")
        if d.get("version") != 1:
            raise ValueError(
                f"Version de schéma non supportée : {d.get('version')!r}.")

        # Reconstruction dans des structures temporaires : on ne touche à l'état
        # qu'une fois la validation passée.
        new_comps: dict[int, CompInst] = {}
        max_id = 0
        for c in d.get("components", []):
            t = c.get("type")
            if t not in self._defs:
                continue                      # type inconnu : ignoré
            ci = CompInst(int(c["id"]), c["ref"], t, c.get("value", ""),
                          int(c["cx"]), int(c["cy"]), int(c.get("rotation", 0)))
            new_comps[ci.id] = ci
            max_id = max(max_id, ci.id)

        next_id = max(int(d.get("next_id", 1)), max_id + 1)

        new_wires: list[WireInst] = []
        for w in d.get("wires", []):
            fa, ta = w.get("from_comp_id"), w.get("to_comp_id")
            if fa not in new_comps or ta not in new_comps:
                continue
            fp, tp = w.get("from_pin"), w.get("to_pin")
            if fp not in self._defs[new_comps[fa].comp_type]["pins"]:
                continue
            if tp not in self._defs[new_comps[ta].comp_type]["pins"]:
                continue
            new_wires.append(WireInst(next_id, fa, fp, ta, tp))
            next_id += 1

        # Ouverture annulable : on empile l'état courant s'il y a quelque chose.
        if self._comps or self._wires:
            self._push_undo()

        self._canvas.delete("all")
        self._comps    = new_comps
        self._wires    = new_wires
        self._counters = {k: int(v) for k, v in d.get("counters", {}).items()}
        self._next_id  = next_id
        self._state        = "idle"
        self._selected_id  = None
        self._wire_src     = None
        self._rubber_band  = None
        self._drag_comp_id = None
        self._redraw_all()
        self._set_status("Schéma\nchargé")

    # ── Export netlist ────────────────────────────────────────────────────────

    def to_netlist(self) -> str:
        """@brief Génère une netlist SPICE depuis le schéma courant."""
        real_comps = {cid: c for cid, c in self._comps.items()
                      if c.comp_type not in ("GND", "VCC")}
        if not real_comps:
            return ""

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

        net_names:   dict[str, str] = {}
        net_counter: list[int]      = [0]

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
            pins = self._defs[comp.comp_type]["pins"]
            nets = " ".join(net_of(f"{comp.id}:{pn}") for pn in pins)
            lines.append(f"{comp.ref} {nets} {comp.value}")

        return "\n".join(lines)

    # ── Utilitaires ──────────────────────────────────────────────────────────

    def _set_status(self, text: str):
        self._status_lbl.configure(text=text)

    def comp_count(self) -> int:
        return len([c for c in self._comps.values() if c.comp_type not in ("GND", "VCC")])

    def unconnected_pins(self) -> list:
        """@brief Liste des broches non câblées : [(ref, nom_broche), …].

        Une broche non câblée fait souvent échouer la reconnaissance du circuit
        (un inverseur sans feedback bouclé sur OUT devient un comparateur).
        """
        loose = []
        for comp in self._comps.values():
            for pn in self._defs[comp.comp_type]["pins"]:
                if not self._pin_connected(comp.id, pn):
                    loose.append((comp.ref, pn))
        return loose
