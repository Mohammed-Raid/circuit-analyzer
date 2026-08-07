"""
@file schematic_editor.py
@brief Éditeur de schéma interactif : palette, canvas zoomable, placement, rotation, câblage.
"""
import copy
import logging
import math
import tkinter as tk
from dataclasses import dataclass
from tkinter import simpledialog
from typing import Optional

from circuit_analyzer.catalogue import entrees_catalogue, identifier
from circuit_analyzer.composant import Composant, charger_bibliotheque
from gui.fonts import FONT_FAMILY
from gui.schematic_io import editor_to_dict, points_jonction, type_reel
from gui.schematic_symbols import AUTO_COLOR as _AUTO_COLOR
from gui.schematic_symbols import (
    BOITE_MIN_H,
    BOITE_MIN_W,
    TYPE_LIBRE,
    aimanter_bord,
    def_puce,
    est_boite_generique,
    etendue_primitives,
    geometrie_libre,
    primitives,
)
from gui.schematic_symbols import rotate_pin as _rotate_pin
from gui.theme import (
    BLUE,
    BORDER,
    ERROR,
    OVERLAY,
    RAISED,
    SCHEMA_COLORS,
    SURFACE,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
)

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
    # Boîte vierge : zéro broche, à brocher à la main (spec 2026-07-23). "X"
    # est la convention maison de la boîte noire côté import ERetroDesign, donc
    # les réfs se numérotent X1, X2… et l'analyseur sait déjà traiter ce type.
    "X":   {"label": "Boîte",        "color": _AUTO_COLOR,
            "w": BOITE_MIN_W, "h": BOITE_MIN_H,
            "pins": {},                                        "default_value": ""},
}

# _AUTO_COLOR : importé de schematic_symbols (source unique, cf. AUTO_COLOR).


def _auto_def(name: str, pins: list, brochage: dict = None,
              default_value: str = "", fonctions: dict = None,
              boite: dict = None, forme_primitives: list = None) -> dict:
    """@brief Génère une géométrie générique pour un type personnalisé.

    Si le type porte un `brochage` POSITIONNÉ (défini au canevas de l'onglet
    Composants, spec 2026-07-23), il fait foi. Sinon, répartition historique
    moitié à gauche / moitié à droite d'une boîte rectangulaire ; aucun dessin
    sur-mesure n'est requis (le moteur de rendu gère ce cas).

    @param name Nom lisible du type (affiché comme libellé).
    @param pins Liste ordonnée des noms de broches.
    @param brochage {nom: (côté, décalage)} ou None.
    @param forme_primitives Contour réel importé d'ERetroDesign (spec
           2026-08-05, `entree["primitives"]`) ou None/vide — copié tel quel
           dans le def si présent. Sa présence bascule aussi `boite` en taille
           EXACTE (`geometrie_libre(w_exact=…)`) plutôt qu'en simple plancher :
           le remplissage genereux pense pour une boite etiquetee a la main
           faisait flotter une broche loin d'un contour reel deja dessine
           (defaut trouve en boucle visuelle sur Vss.xml/VCC+.xml du boss).
    @return dict Entrée compatible COMP_DEFS (label, color, w, h, pins, default_value).
    """
    if brochage:
        b = boite or {}
        pinout = {n: tuple(v) for n, v in brochage.items()}
        if forme_primitives:
            w_exact, h_exact = b.get("w"), b.get("h")
            if w_exact is None or h_exact is None:
                bw, bh = etendue_primitives(forme_primitives)
                w_exact = w_exact if w_exact is not None else bw
                h_exact = h_exact if h_exact is not None else bh
            d = geometrie_libre(pinout, roles=fonctions or {},
                                w_exact=w_exact, h_exact=h_exact)
        else:
            d = geometrie_libre(pinout, b.get("w"), b.get("h"), fonctions or {})
        d["label"] = name
        d["default_value"] = default_value or ""
        if forme_primitives:
            d["primitives"] = forme_primitives
        return d
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
            "pins": pinmap, "default_value": default_value or "",
            "fonctions": dict(fonctions or {})}


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
        defs[key] = _auto_def(val.get("name", key), broches,
                              val.get("brochage"),
                              val.get("default_value", ""),
                              val.get("fonctions"), val.get("boite"),
                              val.get("primitives"))
    return defs

_PIN_R = 5     # rayon visuel pin
_HIT_R = 12   # rayon détection clic sur pin (aussi : tolérance d'aimantation)
_PIN_OFF = "#ef4444"   # contour des broches NON connectées (rouge = à câbler)
_WIRE_COLOR = SCHEMA_COLORS["BUS"]   # couleur des fils/jonctions (== #475569 historique)


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
    # Brochage LIBRE de cette instance : {nom: (côté 'L'/'R'/'T'/'B', décalage)}.
    # None = la géométrie du TYPE fait foi (comportement historique) ; un dict
    # (même vide) prend le pas dessus — cf. `_geom` (spec 2026-07-23).
    pinout:    dict | None = None
    # Contour reel (import catch-all, choix bibliotheque, ou dessine a la
    # main) : liste de primitives ou None. Purement ADDITIF au rendu -- ne
    # remplace jamais `pinout` (spec 2026-08-07).
    forme_primitives: list | None = None


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
        super().__init__(parent, bg=SURFACE)
        self._comps:    dict[int, CompInst] = {}
        self._wires:    list[WireInst]      = []
        self._next_id:  int                 = 1
        self._counters: dict[str, int]      = {}
        self._zoom:     float               = 1.0
        self._ox:       float               = 0.0
        self._oy:       float               = 0.0

        # machine à états : idle | placing | wiring
        self._state       = "idle"
        self._place_type: str | None            = None
        self._place_rotation: int                   = 0
        self._selected_ids: set[int]               = set()
        self._wire_src:   tuple[int, str] | None = None
        self._rubber_band: int | None           = None

        # drag
        self._drag_comp_id: int | None = None
        self._drag_moved:   bool          = False
        self._drag_origins: dict[int, tuple[int, int]] = {}
        self._sel_rect_start: tuple[float, float] | None = None
        self._sel_rect: int | None = None
        self._pan_start: tuple[float, float, float, float] | None = None

        # piles d'annulation/rétablissement (Ctrl+Z / Ctrl+Y)
        self._undo_stack: list = []
        self._redo_stack: list = []
        self._UNDO_MAX = 50

        # presse-papier (Ctrl+C/V/D) : {type, value, rotation}
        self._clipboard: dict | None = None
        # valeur imposée par le catalogue pour le PROCHAIN placement (Task 5) —
        # ex. "LED rouge" pour une entrée D du catalogue (les U catalogue n'en
        # ont pas besoin : def_puce() range déjà la ref dans default_value).
        self._place_value: str | None = None
        # dernière position monde du curseur (cible du coller)
        self._cursor_w: tuple = (200, 200)

        # boutons palette (pour feedback visuel actif/inactif)
        self._palette_btns: dict[str, tk.Button] = {}
        self._palette_parent: tk.Frame | None = None

        # géométrie effective : intégrés + types personnalisés (bibliothèque)
        self._defs: dict = _compute_defs()
        # Mémoïsation des géométries d'instance (brochage libre) — cf. `_geom`.
        self._geom_cache: dict[int, dict] = {}
        # Édition de broches : composant ciblé et broche sélectionnée.
        self._pinedit_id: int | None = None
        self._pin_selectionnee: str | None = None

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
        # Les CompInst restaurés sont d'AUTRES objets (deepcopy) : tout
        # brochage libre mémoïsé est périmé.
        self._invalider_geom()
        self._selected_ids.clear()
        self._drag_comp_id = None
        self._drag_moved   = False
        self._drag_origins.clear()
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
        return wx * self._zoom + self._ox, wy * self._zoom + self._oy

    def _s2w(self, sx, sy):
        """Écran → monde."""
        return (sx - self._ox) / self._zoom, (sy - self._oy) / self._zoom

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
        palette_outer = tk.Frame(self, bg=OVERLAY, width=174)
        palette_outer.pack(side="left", fill="y")
        palette_outer.pack_propagate(False)

        # Pied de palette FIXE (statut + légende) : HORS du canvas défilable,
        # donc toujours visible même fenêtre courte (1280x820) — avant ce fix
        # la légende sortait du cadre et n'apparaissait qu'après un défilement
        # manuel. Packé AVANT le canvas (side="bottom") pour garder sa place.
        footer = tk.Frame(palette_outer, bg=OVERLAY)
        footer.pack(side="bottom", fill="x")
        tk.Frame(footer, bg=BORDER, height=1).pack(fill="x", padx=8, pady=(0, 2))
        self._build_footer(footer)

        pcanvas = tk.Canvas(palette_outer, bg=OVERLAY, highlightthickness=0,
                            bd=0, width=158)
        psb = tk.Scrollbar(palette_outer, orient="vertical", command=pcanvas.yview)
        pcanvas.configure(yscrollcommand=psb.set)
        psb.pack(side="right", fill="y")
        pcanvas.pack(side="left", fill="both", expand=True)

        palette = tk.Frame(pcanvas, bg=OVERLAY)
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

        wrap = tk.Frame(self, bg=SURFACE)
        wrap.pack(side="left", fill="both", expand=True)
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(wrap, bg=SURFACE, highlightthickness=0,
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
        tk.Label(parent, text="COMPOSANTS", fg=TEXT_DIM, bg=OVERLAY,
                 font=(FONT_FAMILY, 8, "bold")).pack(pady=(14, 4), padx=8, anchor="w")

        for ct, defn in self._defs.items():
            color = defn["color"]
            b = tk.Button(
                parent,
                text=f"{ct}  {defn['label']}",
                bg=OVERLAY, fg=color,
                activebackground=BORDER, activeforeground=color,
                relief="flat", anchor="w",
                font=(FONT_FAMILY, 9, "bold"), cursor="hand2", padx=10,
                command=lambda t=ct: self._start_placing(t),
            )
            b.pack(fill="x", padx=4, pady=2)
            self._palette_btns[ct] = b

        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=8, pady=8)
        self._build_catalogue_section(parent)

        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=8, pady=8)

        tk.Button(parent, text="🗑  Supprimer",
                  bg=OVERLAY, fg=ERROR, activebackground=BORDER,
                  activeforeground=ERROR, relief="flat", anchor="w",
                  font=(FONT_FAMILY, 9), cursor="hand2", padx=10,
                  command=self._delete_selected).pack(fill="x", padx=4, pady=2)
        tk.Button(parent, text="⬜  Effacer tout",
                  bg=OVERLAY, fg=TEXT_MUTED, activebackground=BORDER,
                  activeforeground=TEXT_MUTED, relief="flat", anchor="w",
                  font=(FONT_FAMILY, 9), cursor="hand2", padx=10,
                  command=self.clear_all).pack(fill="x", padx=4, pady=2)
        tk.Button(parent, text="⊡  Ajuster (F)",
                  bg=OVERLAY, fg=BLUE, activebackground=BORDER,
                  activeforeground=BLUE, relief="flat", anchor="w",
                  font=(FONT_FAMILY, 9), cursor="hand2", padx=10,
                  command=self.fit_to_view).pack(fill="x", padx=4, pady=2)

    def _build_footer(self, parent):
        """@brief Pied de palette fixe : statut transitoire + légende raccourcis.

        Créé UNE fois dans `_build` (jamais reconstruit par `refresh_palette`,
        qui ne touche que la zone défilable). Deux labels SÉPARÉS :
        - `_status_lbl` : messages transitoires ("Placé R1", "Ajusté ⊡"…),
          hauteur fixe 3 lignes pour que son contenu variable ne déplace pas
          la légende ;
        - `_legend_lbl` : légende des raccourcis, PERSISTANTE — jamais réécrite
          par `_set_status` (avant ce fix un seul label servait aux deux usages
          et la légende disparaissait dès la première action).
        """
        self._status_lbl = tk.Label(
            parent, text="Prêt", fg=TEXT_DIM, bg=OVERLAY,
            font=(FONT_FAMILY, 7), justify="center", wraplength=140, height=3,
        )
        self._status_lbl.pack(padx=8, pady=(1, 0))

        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=8, pady=1)

        # Lignes courtes (chacune tient dans wraplength=140 sans repli au
        # milieu d'un raccourci — vérifié sur capture 1280x820).
        self._legend_lbl = tk.Label(
            parent,
            text="Clic = placer · Espace = rotation\n"
                 "Ctrl+C/V = copier/coller\n"
                 "Ctrl+D = dupliquer\n"
                 "Ctrl+Z/Y = annuler/rétablir\n"
                 "Molette = zoom · milieu = pan\n"
                 "Glisser = sélection · Suppr = effacer\n"
                 "Clic droit = menu · F = ajuster\n"
                 "Échap = annuler",
            fg=TEXT_DIM, bg=OVERLAY,
            font=(FONT_FAMILY, 7), justify="center", wraplength=140,
        )
        self._legend_lbl.pack(padx=8, pady=(0, 3))

    def _build_catalogue_section(self, parent):
        """@brief Section « Puces réelles » : liste déroulante compacte (Task 5).

        Une Listbox (pas un bouton par entrée — ~30 entrées, palette compacte)
        alimentée par `entrees_catalogue()`, triée par valeur affichée. Simple
        clic (sélection) -> `_activer_catalogue`.
        """
        tk.Label(parent, text="PUCES RÉELLES", fg=TEXT_DIM, bg=OVERLAY,
                 font=(FONT_FAMILY, 8, "bold")).pack(pady=(0, 4), padx=8, anchor="w")

        entries = sorted(entrees_catalogue(), key=lambda e: e[1])
        self._catalogue_entries = entries

        lb = tk.Listbox(parent, bg=SURFACE, fg=TEXT,
                         selectbackground=BLUE, selectforeground=TEXT,
                         highlightthickness=0, bd=0, exportselection=False,
                         height=8, font=(FONT_FAMILY, 9))
        for t, v, e in entries:
            lb.insert("end", f"{v} — {e.get('categorie', '')}")
        lb.pack(fill="x", padx=8, pady=(0, 4))

        def _on_select(_evt=None):
            sel = lb.curselection()
            if sel:
                t, v, _e = self._catalogue_entries[sel[0]]
                self._activer_catalogue(t, v)

        lb.bind("<<ListboxSelect>>", _on_select)
        self._catalogue_listbox = lb

    def refresh_palette(self):
        """@brief Recharge la bibliothèque et reconstruit la palette.

        Appelé quand l'onglet Composants modifie la bibliothèque : un nouveau type
        apparaît dans la palette, un type supprimé en disparaît. Les composants
        déjà posés d'un type devenu inconnu sont retirés du canvas (avec leurs
        fils) pour éviter un plantage au redessin.
        """
        self._defs = _compute_defs()
        # Puces catalogue posées ("U::NE555"…) : def dynamique absente de
        # _compute_defs() (elle ne vient pas de la bibliothèque perso) —
        # régénérée sinon la purge ci-dessous les considère obsolètes à tort.
        for c in self._comps.values():
            self._ensure_dyn_def(c.comp_type)

        # Purge des composants dont le type n'existe plus dans la bibliothèque.
        obsoletes = {cid for cid, c in self._comps.items()
                     if c.comp_type not in self._defs}
        if obsoletes:
            self._wires = [w for w in self._wires
                           if w.from_comp_id not in obsoletes
                           and w.to_comp_id not in obsoletes]
            for cid in obsoletes:
                self._comps.pop(cid, None)
            self._selected_ids.difference_update(obsoletes)
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
        x = self._ox % step
        while x <= W + 1:
            ix = int(x)
            self._canvas.create_line(ix, 0, ix, H, fill=RAISED, width=1, tags="grid")
            x += step
        y = self._oy % step
        while y <= H + 1:
            iy = int(y)
            self._canvas.create_line(0, iy, W, iy, fill=RAISED, width=1, tags="grid")
            y += step
        self._canvas.configure(scrollregion=(0, 0, W, H))
        self._canvas.tag_lower("grid")

    def _bind_events(self):
        c = self._canvas
        c.bind("<Button-1>",         self._on_click)
        c.bind("<B1-Motion>",        self._on_b1_motion)
        c.bind("<ButtonRelease-1>",  self._on_b1_release)
        c.bind("<Button-2>",         self._on_pan_start)
        c.bind("<B2-Motion>",        self._on_pan_motion)
        c.bind("<ButtonRelease-2>",  self._on_pan_release)
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
        c.bind("<MouseWheel>",       self._on_zoom)
        c.focus_set()

    # ── Zoom ─────────────────────────────────────────────────────────────────

    def _on_zoom(self, event):
        n = event.delta / 120
        factor = 1.1 ** n
        sx, sy = self._cc(event)
        self._zoom_wheel(factor, sx, sy)

    def _zoom_wheel(self, factor: float, sx: float, sy: float):
        """Zoom cursor-centre : le point monde sous le curseur reste immobile."""
        old = self._zoom
        new = max(0.2, min(5.0, old * factor))
        if new == old:
            return
        self._ox = sx - (sx - self._ox) * (new / old)
        self._oy = sy - (sy - self._oy) * (new / old)
        self._zoom = new
        self._redraw_all()

    def _redraw_all(self):
        """Redessine tout le canvas (utilisé après zoom)."""
        self._canvas.delete("all")
        self._draw_grid()
        for comp in self._comps.values():
            self._draw_comp(comp)
        for wire in self._wires:
            self._draw_wire(wire)
        self._redraw_jonctions()
        selected = set(self._selected_ids)
        self._selected_ids.clear()
        for sid in selected:
            self._select(sid, append=True)

    # ── Placement ────────────────────────────────────────────────────────────

    def _ensure_dyn_def(self, comp_type: str):
        """@brief Régénère la def dynamique d'une puce catalogue (Task 5, §4).

        Un comp_type "T::VALEUR" ne fait PAS partie de `_compute_defs()` (il
        n'existe que dans `self._defs`, construit à la volée) — après un
        `refresh_palette()` ou la relecture d'un `.circ`, il faut le
        reconstruire depuis le catalogue AVANT tout redessin, sinon
        `_draw_comp` lève un KeyError. No-op si déjà présent ou non catalogue.
        """
        if comp_type in self._defs or not comp_type or "::" not in comp_type:
            return
        t, v = type_reel(comp_type)
        entree = identifier(t, v)
        broches = (entree or {}).get("broches")
        if broches:
            self._defs[comp_type] = def_puce(v, dict(broches))

    def _activer_catalogue(self, type_: str, value: str):
        """@brief Prépare le placement d'une entrée catalogue (Task 5).

        U avec broches catalogue -> def DIP dynamique enregistrée sous
        "U::VALEUR" (idempotent) et placement de ce type composite (la
        réf/valeur suivent `def_puce`, pas besoin de valeur imposée). Sinon
        (Q/M/D dont LED) -> type intégré existant, mais la valeur par défaut
        du placement devient celle du catalogue (ex. "LED rouge").
        """
        entree = identifier(type_, value) if type_ == "U" else None
        broches = (entree or {}).get("broches") if entree else None
        if type_ == "U" and broches:
            key = f"U::{value}"
            if key not in self._defs:
                self._defs[key] = def_puce(value, dict(broches))
            self._start_placing(key)
            return
        self._start_placing(type_)
        self._place_value = value

    def _start_placing(self, comp_type: str):
        self._cancel_wiring()
        self._deselect()
        self._state      = "placing"
        self._place_type = comp_type
        self._place_rotation = 0
        self._place_value = None
        self._canvas.configure(cursor="crosshair")
        # Feedback visuel dans la palette (une puce catalogue "U::NE555" n'a pas
        # de bouton dédié — elle vient de la Listbox « Puces réelles »).
        for t, btn in self._palette_btns.items():
            btn.configure(bg=OVERLAY, relief="flat")
        if comp_type in self._palette_btns:
            self._palette_btns[comp_type].configure(bg=BORDER, relief="groove")
        self._set_status(f"Clic pour\nplacer {comp_type}\nÉchap = annuler")

    def _place_at(self, wx: int, wy: int) -> "CompInst":
        """Place un composant en coordonnées monde — reste en mode placing.

        Extrait du handler de clic pour être appelable directement (tests).
        Le compteur/la référence utilisent le type RÉEL (`type_reel`) : une
        puce catalogue "U::NE555" numérote comme "U", ref "U1" — jamais
        "U::NE5551" (revue Task 2) — et partage la séquence avec les autres U.
        """
        self._push_undo()
        t    = self._place_type
        defn = self._defs[t]
        tipo, _ = type_reel(t)
        n    = self._counters.get(tipo, 0) + 1
        self._counters[tipo] = n
        # GND et VCC n'ont pas de numéro affiché
        ref   = f"{tipo}{n}" if tipo not in ("GND", "VCC") else tipo
        value = self._place_value if self._place_value is not None else defn["default_value"]
        comp = CompInst(self._next_id, ref, t, value, wx, wy,
                        self._place_rotation)
        if t == "X":
            comp.pinout = {}      # boîte vierge : brochage libre, zéro broche
        self._next_id += 1
        self._comps[comp.id] = comp
        self._draw_comp(comp)
        # Reste en mode placing (Échap pour sortir)
        self._set_status(f"Placé {ref}\nClic = autre\nÉchap = stop")
        return comp

    def _place_comp(self, wx: int, wy: int):
        """@brief Alias historique de `_place_at` (compat tests existants)."""
        return self._place_at(wx, wy)

    # ── Géométrie effective (type ou brochage libre) ──────────────────────────

    def _geom(self, comp: CompInst) -> dict:
        """@brief Géométrie EFFECTIVE : brochage d'instance sinon def du type.

        Point d'accès UNIQUE à la géométrie d'un composant posé — tout ce qui
        lisait `self._defs[comp.comp_type]` passe désormais par ici (spec
        2026-07-23). Mémoïsé car `_find_pin_at` balaye tous les composants à
        chaque mouvement de souris. Invalidé par `_invalider_geom` (édition de
        broche, undo/redo, chargement, suppression) : un cache périmé donne des
        fils qui pointent à côté, symptôme pénible à diagnostiquer.
        """
        if comp.pinout is None and not comp.forme_primitives:
            return self._defs[comp.comp_type]
        d = self._geom_cache.get(comp.id)
        if d is None:
            pinout = comp.pinout or {}
            d = geometrie_libre(pinout)
            base = self._defs.get(comp.comp_type)
            if base:
                d["color"] = base["color"]
            if comp.forme_primitives:
                d["primitives"] = comp.forme_primitives
            self._geom_cache[comp.id] = d
        return d

    def _invalider_geom(self, comp_id: int | None = None):
        """@brief Purge le cache de géométrie (tout, ou un seul composant)."""
        if comp_id is None:
            self._geom_cache.clear()
        else:
            self._geom_cache.pop(comp_id, None)

    # ── Édition de broches (mode "pinedit", spec 2026-07-23) ──────────────────

    def _entrer_pinedit(self, comp_id: int):
        """@brief Passe en édition de broches sur CE composant."""
        if comp_id not in self._comps:
            return
        self._cancel_wiring()
        self._deselect()
        self._state      = "pinedit"
        self._pinedit_id = comp_id
        self._pin_selectionnee = None
        self._canvas.configure(cursor="crosshair")
        self._dessiner_cadre_pinedit()
        self._set_status("Clic bord = broche\nDouble-clic = renommer\n"
                         "Suppr = retirer\nÉchap = fin")

    def _quitter_pinedit(self):
        """@brief Sort du mode d'édition de broches."""
        self._canvas.delete("pinedit")
        self._state      = "idle"
        self._pinedit_id = None
        self._pin_selectionnee = None
        self._canvas.configure(cursor="")
        self._set_status("Prêt")

    def _dessiner_cadre_pinedit(self):
        """@brief Cadre pointillé autour du composant en cours d'édition."""
        self._canvas.delete("pinedit")
        comp = self._comps.get(self._pinedit_id)
        if not comp:
            return
        d = self._geom(comp)
        rot = comp.rotation
        w2 = (d["w"] // 2 if rot % 180 == 0 else d["h"] // 2) + 8
        h2 = (d["h"] // 2 if rot % 180 == 0 else d["w"] // 2) + 8
        x0, y0 = self._w2s(comp.cx - w2, comp.cy - h2)
        x1, y1 = self._w2s(comp.cx + w2, comp.cy + h2)
        self._canvas.create_rectangle(x0, y0, x1, y1, outline=BLUE,
                                      dash=(4, 3), width=2, tags="pinedit")

    def _nom_broche_libre(self, pinout: dict) -> str:
        """@brief Plus petit entier >= 1 non utilisé (une suppression se recycle)."""
        n = 1
        while str(n) in pinout:
            n += 1
        return str(n)

    def _amorcer_pinout(self, comp: CompInst) -> dict:
        """@brief Projette les broches du TYPE sur les bords -> (côté, décalage).

        PARESSEUX : appelé à la PREMIÈRE mutation seulement. Sinon, comme
        `pinout is not None` déclenche le rendu en boîte, entrer dans le mode
        puis faire Échap transformerait le symbole sans qu'on ait rien touché.
        """
        d = self._defs[comp.comp_type]
        return {pn: aimanter_bord(dx, dy, d["w"], d["h"], GRID)
                for pn, (dx, dy) in d["pins"].items()}

    def _ajouter_broche(self, comp: CompInst, wx: int, wy: int) -> str:
        """@brief Ajoute une broche aimantée au bord le plus proche du clic.

        @return Nom attribué (numérotation automatique).
        """
        self._push_undo()
        if comp.pinout is None:
            comp.pinout = self._amorcer_pinout(comp)
        d = self._geom(comp)
        nom = self._nom_broche_libre(comp.pinout)
        comp.pinout[nom] = aimanter_bord(wx - comp.cx, wy - comp.cy,
                                         d["w"], d["h"], GRID)
        self._invalider_geom(comp.id)
        self._draw_comp(comp)
        self._dessiner_cadre_pinedit()
        return nom

    def _deplacer_broche(self, comp: CompInst, nom: str, wx: int, wy: int):
        """@brief Fait coulisser une broche ; aimantation bord + grille."""
        if comp.pinout is None or nom not in comp.pinout:
            return
        self._push_undo()
        d = self._geom(comp)
        comp.pinout[nom] = aimanter_bord(wx - comp.cx, wy - comp.cy,
                                         d["w"], d["h"], GRID)
        self._invalider_geom(comp.id)
        self._draw_comp(comp)
        self._redraw_wires_of(comp.id)
        self._dessiner_cadre_pinedit()

    def _renommer_broche(self, comp: CompInst, ancien: str, nouveau: str) -> bool:
        """@brief Renomme une broche ET les fils qui la référencent (par NOM).

        @return False si le nom est vide ou déjà pris (refus signalé au statut).
        """
        if comp.pinout is None or ancien not in comp.pinout:
            return False
        nouveau = (nouveau or "").strip()
        if not nouveau or nouveau in comp.pinout:
            self._set_status("Nom vide ou\ndéjà utilisé")
            return False
        self._push_undo()
        comp.pinout[nouveau] = comp.pinout.pop(ancien)
        # Les fils référencent les broches par NOM : sans cette reprise, le
        # renommage les rendrait orphelins au prochain redessin.
        for w in self._wires:
            if w.from_comp_id == comp.id and w.from_pin == ancien:
                w.from_pin = nouveau
            if w.to_comp_id == comp.id and w.to_pin == ancien:
                w.to_pin = nouveau
        if self._pin_selectionnee == ancien:
            self._pin_selectionnee = nouveau
        self._invalider_geom(comp.id)
        self._draw_comp(comp)
        return True

    def _supprimer_broche(self, comp: CompInst, nom: str):
        """@brief Retire une broche ET les fils rattachés (sinon fils orphelins)."""
        if comp.pinout is None or nom not in comp.pinout:
            return
        self._push_undo()
        comp.pinout.pop(nom, None)
        self._wires = [w for w in self._wires
                       if not ((w.from_comp_id == comp.id and w.from_pin == nom)
                               or (w.to_comp_id == comp.id and w.to_pin == nom))]
        if self._pin_selectionnee == nom:
            self._pin_selectionnee = None
        self._invalider_geom(comp.id)
        self._redraw_all()
        self._dessiner_cadre_pinedit()

    # ── Rendu ────────────────────────────────────────────────────────────────

    def _draw_comp(self, comp: CompInst):
        defn  = self._geom(comp)
        color = defn["color"]
        z     = self._zoom
        rot   = comp.rotation
        # Brochage positionné -> boîte honnête. Le symbole d'origine (zigzag
        # d'une résistance, triangle d'un AOP…) est dessiné POUR ses broches
        # d'origine : une fois rebroché, il mentirait (spec 2026-07-23 §4).
        # Le critère est la présence de `cotes` dans la géométrie EFFECTIVE, ce
        # qui couvre les DEUX sources : brochage d'instance (`comp.pinout`) et
        # brochage de TYPE défini au canevas de l'onglet Composants. Tester
        # `comp.pinout` seul laissait le second cas retomber sur `_tr_boite`,
        # qui ne sait pas placer une broche en haut/bas et rejetait « VCC »
        # hors de la boîte (défaut trouvé en boucle visuelle).
        # Le comp_type, lui, ne bouge pas — l'export et l'analyse non plus.
        # PRÉSENCE de la clé, pas sa valeur : une boîte vierge a `cotes == {}`,
        # qui est falsy et la ferait retomber sur `_tr_boite`.
        t_rendu = TYPE_LIBRE if "cotes" in defn else comp.comp_type
        scx, scy = self._w2s(comp.cx, comp.cy)
        w2, h2   = defn["w"] // 2, defn["h"] // 2
        pr   = max(2, _PIN_R * z)
        tag  = f"comp_{comp.id}"
        self._canvas.delete(tag)

        # Symbole : primitives vectorielles (Task 1), rotation déjà appliquée.
        prims = primitives(t_rendu, defn, rot, comp.value)
        for p in prims:
            if p[0] == "line":
                flat = [c for x, y in p[1] for c in self._w2s(comp.cx + x, comp.cy + y)]
                self._canvas.create_line(*flat, fill=color,
                                         width=max(1, int(p[2] * z)),
                                         joinstyle="round", tags=tag)
            elif p[0] == "polygon":
                flat = [c for x, y in p[1] for c in self._w2s(comp.cx + x, comp.cy + y)]
                self._canvas.create_polygon(
                    *flat, fill=color if p[2] else "",
                    outline=color, width=max(1, int(2 * z)), tags=tag)
            elif p[0] == "arc":
                x0, y0, x1, y1 = p[1]
                sx0, sy0 = self._w2s(comp.cx + x0, comp.cy + y0)
                sx1, sy1 = self._w2s(comp.cx + x1, comp.cy + y1)
                self._canvas.create_arc(sx0, sy0, sx1, sy1, start=p[2],
                                        extent=p[3], style="arc",
                                        outline=color,
                                        width=max(1, int(2 * z)), tags=tag)
            elif p[0] == "text":
                sx, sy = self._w2s(comp.cx + p[1][0], comp.cy + p[1][1])
                self._canvas.create_text(sx, sy, text=p[2], fill=color,
                                         font=("Consolas", max(5, int(p[3] * z))),
                                         anchor={"e": "e", "w": "w"}.get(p[4], "center"),
                                         tags=tag)

        # Textes : refs/valeurs horizontaux (position tournée, texte pas tourné,
        # comme KiCad). Le nom de type n'est plus dessiné.
        if comp.comp_type in ("GND", "VCC"):
            # Le traceur n'émet pas de texte : "GND"/"VCC" (== comp.ref) reste ici.
            toff = (0, -28) if comp.comp_type == "GND" else (0, 30)
            tx, ty = _rotate_pin(*toff, rot)
            self._canvas.create_text(scx+tx*z, scy+ty*z,
                                     text=comp.ref, fill=color,
                                     font=("Consolas", max(7, int(8*z))), tags=tag)
        else:
            # Une broche sur le bord HAUT (resp. BAS) occupe déjà l'emplacement
            # historique du titre (resp. de la valeur), calibré à une époque où
            # aucune broche ne pouvait s'y trouver : on les repousse. Défaut
            # trouvé en boucle visuelle, invisible aux tests d'alors.
            cotes = set((defn.get("cotes") or {}).values())
            d_ref = 24 if "T" in cotes else 10
            d_val = 24 if "B" in cotes else 10
            rx, ry = _rotate_pin(0, -h2 - d_ref, rot)
            self._canvas.create_text(scx+rx*z, scy+ry*z,
                                     text=comp.ref, fill="#e2e8f0",
                                     font=("Consolas", max(7, int(9*z)), "bold"),
                                     tags=tag)
            vx, vy = _rotate_pin(0, h2 + d_val, rot)
            self._canvas.create_text(scx+vx*z, scy+vy*z,
                                     text=comp.value, fill="#64748b",
                                     font=("Consolas", max(6, int(8*z))),
                                     tags=tag)

        # Pastilles de broches + labels (>2 broches)
        nb_pins = len(defn["pins"])
        # Boîte générique (types perso, puces catalogue) : _tr_boite dessine
        # déjà un libellé par broche dans ses primitives — un second libellé
        # générique ici les superposerait (spec §5, défaut visuel Task 5).
        boite = est_boite_generique(t_rendu)
        for pn, (pdx, pdy) in defn["pins"].items():
            rdx, rdy = _rotate_pin(pdx, pdy, rot)
            spx = scx + rdx * z
            spy = scy + rdy * z
            pfill, pout = self._pin_style(comp.id, pn, color)
            self._canvas.create_oval(spx-pr, spy-pr, spx+pr, spy+pr,
                                     fill=pfill, outline=pout,
                                     width=max(1, int(2*z)),
                                     tags=(tag, f"pin_{comp.id}_{pn}"))
            if nb_pins > 2 and not boite:
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
        dx_a, dy_a = self._geom(ca)["pins"][wire.from_pin]
        rdx_a, rdy_a = _rotate_pin(dx_a, dy_a, ca.rotation)
        dx_b, dy_b = self._geom(cb)["pins"][wire.to_pin]
        rdx_b, rdy_b = _rotate_pin(dx_b, dy_b, cb.rotation)

        wx1, wy1 = ca.cx + rdx_a, ca.cy + rdy_a
        wx2, wy2 = cb.cx + rdx_b, cb.cy + rdy_b
        sx1, sy1 = self._w2s(wx1, wy1)
        sx2, sy2 = self._w2s(wx2, wy2)

        tag = f"wire_{wire.id}"
        self._canvas.delete(tag)
        lw = max(1, int(2 * self._zoom))
        self._canvas.create_line(sx1, sy1, sx2, sy1, sx2, sy2,
                                  fill=_WIRE_COLOR, width=lw,
                                  joinstyle="round", tags=tag)

    def _redraw_wires_of(self, comp_id: int):
        for w in self._wires:
            if w.from_comp_id == comp_id or w.to_comp_id == comp_id:
                self._draw_wire(w)
        self._redraw_jonctions()

    def _redraw_jonctions(self):
        """@brief Redessine les points de jonction (>=3 extrémités de fils, Task 2/4).

        Disque plein, rayon 4*zoom, couleur du fil — posé APRÈS les fils pour
        rester visible par-dessus (tag "jonction", purgé avant redessin).
        """
        self._canvas.delete("jonction")
        r = 4 * self._zoom
        for wx, wy in points_jonction(self._comps, self._wires, self._geom):
            sx, sy = self._w2s(wx, wy)
            self._canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                                     fill=_WIRE_COLOR, outline=_WIRE_COLOR,
                                     tags=("jonction",))

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

    def _find_pin_at(self, wx, wy) -> tuple[int, str] | None:
        tol = _HIT_R / self._zoom  # rayon de détection en coordonnées monde
        for comp in self._comps.values():
            for pn, (dx, dy) in self._geom(comp)["pins"].items():
                rdx, rdy = _rotate_pin(dx, dy, comp.rotation)
                px, py = comp.cx + rdx, comp.cy + rdy
                if (wx - px)**2 + (wy - py)**2 <= tol**2:
                    return (comp.id, pn)
        return None

    def _find_comp_at(self, wx, wy) -> int | None:
        for comp in self._comps.values():
            defn = self._geom(comp)
            rot  = comp.rotation
            w2 = (defn["w"] // 2 if rot % 180 == 0 else defn["h"] // 2) + 6
            h2 = (defn["h"] // 2 if rot % 180 == 0 else defn["w"] // 2) + 6
            if comp.cx - w2 <= wx <= comp.cx + w2 and comp.cy - h2 <= wy <= comp.cy + h2:
                return comp.id
        return None

    def _find_wire_at(self, wx, wy, tol=8) -> int | None:
        """Cherche un fil proche de (wx,wy) en coordonnées monde."""
        tol_w = tol / self._zoom
        for w in self._wires:
            ca = self._comps.get(w.from_comp_id)
            cb = self._comps.get(w.to_comp_id)
            if not ca or not cb:
                continue
            dx_a, dy_a = self._geom(ca)["pins"][w.from_pin]
            rdx_a, rdy_a = _rotate_pin(dx_a, dy_a, ca.rotation)
            dx_b, dy_b = self._geom(cb)["pins"][w.to_pin]
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
            self._place_at(swx, swy)
            return

        if self._state == "pinedit":
            comp = self._comps.get(self._pinedit_id)
            if comp is None:
                self._quitter_pinedit()
                return
            # Clic SUR une broche = la sélectionner (le glissé la déplacera) ;
            # clic ailleurs sur le bord = nouvelle broche.
            cible = self._find_pin_at(wx, wy)
            if cible and cible[0] == comp.id:
                self._pin_selectionnee = cible[1]
            else:
                self._pin_selectionnee = self._ajouter_broche(comp, wx, wy)
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
            self._start_wiring(*pin)
            return

        comp_id = self._find_comp_at(wx, wy)
        if comp_id:
            if comp_id not in self._selected_ids:
                self._select(comp_id)
            self._drag_comp_id = comp_id
            self._drag_moved   = False
            self._drag_origins = {
                cid: (self._comps[cid].cx, self._comps[cid].cy)
                for cid in self._selected_ids if cid in self._comps
            }
        else:
            self._deselect()
            self._sel_rect_start = (wx, wy)
            sx, sy = self._w2s(wx, wy)
            self._sel_rect = self._canvas.create_rectangle(
                sx, sy, sx, sy, outline=BLUE, dash=(4, 3), tags="selrect")

    def _on_b1_motion(self, event):
        if self._state == "pinedit" and self._pin_selectionnee:
            comp = self._comps.get(self._pinedit_id)
            if comp:
                wx, wy = self._cw(event)
                self._deplacer_broche(comp, self._pin_selectionnee, wx, wy)
            return

        if self._state == "idle" and self._drag_comp_id is not None:
            wx, wy   = self._cw(event)
            swx, swy = self._snap(wx, wy)
            origin = self._drag_origins.get(self._drag_comp_id)
            if origin and (origin[0] != swx or origin[1] != swy):
                # Empile l'annulation une seule fois, au premier déplacement réel
                # (un simple clic de sélection ne crée pas d'instantané).
                if not self._drag_moved:
                    self._push_undo()
                    self._drag_moved = True
                dx, dy = swx - origin[0], swy - origin[1]
                for cid, (cx, cy) in self._drag_origins.items():
                    comp = self._comps.get(cid)
                    if comp:
                        comp.cx, comp.cy = cx + dx, cy + dy
                self._redraw_all()
        elif self._state == "idle" and self._sel_rect_start:
            wx, wy = self._cw(event)
            sx0, sy0 = self._w2s(*self._sel_rect_start)
            sx1, sy1 = self._w2s(wx, wy)
            self._canvas.coords(self._sel_rect, sx0, sy0, sx1, sy1)

    def _on_b1_release(self, event=None):
        if self._sel_rect_start:
            wx, wy = self._cw(event)
            self._select_in_rect(*self._sel_rect_start, wx, wy)
            self._canvas.delete("selrect")
            self._sel_rect_start = None
            self._sel_rect = None
        self._drag_comp_id = None
        self._drag_moved   = False
        self._drag_origins.clear()

    def _on_motion(self, event):
        self._cursor_w = self._cw(event)
        if self._state == "wiring" and self._wire_src:
            self._update_wire_preview(*self._cursor_w)

    def _on_pan_start(self, event):
        sx, sy = self._cc(event)
        self._pan_start = (sx, sy, self._ox, self._oy)
        self._canvas.configure(cursor="fleur")

    def _on_pan_motion(self, event):
        if not self._pan_start:
            return
        sx, sy = self._cc(event)
        x0, y0, ox, oy = self._pan_start
        self._ox, self._oy = ox + sx - x0, oy + sy - y0
        self._redraw_all()

    def _on_pan_release(self, _=None):
        self._pan_start = None
        if self._state in ("placing", "wiring"):
            self._canvas.configure(cursor="crosshair")
        else:
            self._canvas.configure(cursor="")

    def _on_double_click(self, event):
        wx, wy  = self._cw(event)

        # En édition de broches, le double-clic RENOMME la broche visée
        # (il n'ouvre pas la fiche du composant).
        if self._state == "pinedit":
            comp = self._comps.get(self._pinedit_id)
            cible = self._find_pin_at(wx, wy)
            if comp and cible and cible[0] == comp.id:
                nouveau = simpledialog.askstring(
                    "Renommer la broche",
                    f"Nouveau nom pour « {cible[1]} » :",
                    initialvalue=cible[1], parent=self)
                if nouveau is not None:
                    self._renommer_broche(comp, cible[1], nouveau)
            return

        comp_id = self._find_comp_at(wx, wy)
        if comp_id:
            self._edit_comp(comp_id)

    def _on_right_click(self, event):
        wx, wy = self._cw(event)

        # Priorité 1 : fil
        wire_id = self._find_wire_at(wx, wy)
        if wire_id is not None:
            m = tk.Menu(self._canvas, tearoff=0, bg=OVERLAY, fg=TEXT,
                        activebackground=BLUE, activeforeground=TEXT)
            m.add_command(label="🗑  Supprimer ce fil",
                          command=lambda: self._delete_wire(wire_id))
            m.post(event.x_root, event.y_root)
            return

        # Priorité 2 : composant
        comp_id = self._find_comp_at(wx, wy)
        if not comp_id:
            return
        self._select(comp_id)
        m = tk.Menu(self._canvas, tearoff=0, bg=OVERLAY, fg=TEXT,
                    activebackground=BLUE, activeforeground=TEXT)
        m.add_command(label="✏  Modifier…",  command=lambda: self._edit_comp(comp_id))
        m.add_command(label="↻  Rotation",   command=lambda: self._rotate_comp(comp_id))
        m.add_command(label="⊹  Éditer broches",
                      command=lambda: self._entrer_pinedit(comp_id))
        m.add_separator()
        m.add_command(label="🗑  Supprimer", command=lambda: self._delete_comp(comp_id))
        m.post(event.x_root, event.y_root)

    def _on_delete(self, _=None):
        # En édition de broches, Suppr retire la BROCHE sélectionnée, pas le
        # composant (qui reste la cible du mode).
        if self._state == "pinedit":
            comp = self._comps.get(self._pinedit_id)
            if comp and self._pin_selectionnee:
                self._supprimer_broche(comp, self._pin_selectionnee)
            return
        self._delete_selected()

    def _on_escape(self, _=None):
        if self._state == "pinedit":
            self._quitter_pinedit()
            return
        if self._state == "wiring":
            self._cancel_wiring()
        elif self._state == "placing":
            self._state      = "idle"
            self._place_type = None
            self._canvas.configure(cursor="")
            for btn in self._palette_btns.values():
                btn.configure(bg=OVERLAY, relief="flat")
            self._set_status("Prêt")
        self._deselect()

    def _on_rotate(self, _=None):
        if self._state == "placing":
            self._place_rotation = (self._place_rotation + 90) % 360
            self._set_status(f"Rotation {self._place_rotation}°\nClic = placer")
        else:
            self._rotate_selection()

    # ── Copier / coller / dupliquer ───────────────────────────────────────────

    def _add_comp(self, comp_type: str, value: str, rotation: int,
                  wx: int, wy: int, pinout: dict | None = None,
                  forme_primitives: list | None = None
                  ) -> Optional['CompInst']:
        """@brief Crée, dessine et sélectionne un nouveau composant.

        Numérote la référence via le compteur du type (ex. R3). N'empile PAS
        l'annulation (l'appelant le fait), pour grouper coller/dupliquer en une
        seule étape annulable.

        @return CompInst créé, ou None si le type est inconnu.
        """
        if comp_type not in self._defs:
            return None
        # Type RÉEL pour la numérotation (revue Task 2) : "U::NE555" numérote
        # comme "U" — ref "U1", jamais "U::NE5551" — et partage la séquence
        # avec les autres composants "U".
        tipo, _ = type_reel(comp_type)
        n = self._counters.get(tipo, 0) + 1
        self._counters[tipo] = n
        ref = f"{tipo}{n}" if tipo not in ("GND", "VCC") else tipo
        # deepcopy du brochage : « par instance » interdit que deux copies
        # partagent le même dict (éditer l'une modifierait l'autre).
        comp = CompInst(self._next_id, ref, comp_type, value, wx, wy, rotation,
                        pinout=copy.deepcopy(pinout),
                        forme_primitives=copy.deepcopy(forme_primitives))
        self._next_id += 1
        self._comps[comp.id] = comp
        self._draw_comp(comp)
        self._deselect()
        self._select(comp.id)
        return comp

    def _copy(self, _=None):
        """@brief Copie le composant sélectionné dans le presse-papier (Ctrl+C)."""
        comp = self._comps.get(next(iter(self._selected_ids), None))
        if not comp:
            return
        self._clipboard = {"type": comp.comp_type, "value": comp.value,
                           "rotation": comp.rotation, "pinout": comp.pinout,
                           "forme_primitives": comp.forme_primitives}
        self._set_status(f"Copié\n{comp.ref}")

    def _paste(self, _=None):
        """@brief Colle le composant du presse-papier à la position du curseur (Ctrl+V)."""
        if not self._clipboard:
            return
        wx, wy = self._snap(*self._cursor_w)
        self._push_undo()
        comp = self._add_comp(self._clipboard["type"], self._clipboard["value"],
                              self._clipboard["rotation"], wx, wy,
                              self._clipboard.get("pinout"),
                              self._clipboard.get("forme_primitives"))
        if comp is None:
            # Type devenu inconnu : annule l'instantané inutile.
            self._undo_stack.pop()
            return
        self._set_status(f"Collé\n{comp.ref}")

    def _duplicate(self, _=None):
        """@brief Duplique le composant sélectionné en décalé (Ctrl+D)."""
        src = self._comps.get(next(iter(self._selected_ids), None))
        if not src:
            return
        self._clipboard = {"type": src.comp_type, "value": src.value,
                           "rotation": src.rotation, "pinout": src.pinout,
                           "forme_primitives": src.forme_primitives}
        self._push_undo()
        comp = self._add_comp(src.comp_type, src.value, src.rotation,
                              src.cx + GRID * 2, src.cy + GRID * 2, src.pinout,
                              src.forme_primitives)
        if comp is None:
            self._undo_stack.pop()
            return
        self._set_status(f"Dupliqué\n{comp.ref}")

    # ── Recentrer / ajuster à l'écran ─────────────────────────────────────────

    def fit_to_view(self, _=None):
        """@brief Ajuste le zoom et le défilement pour montrer tout le schéma (F)."""
        if not self._comps:
            self._zoom = 1.0
            self._ox = self._oy = 0.0
            self._redraw_all()
            self._canvas.xview_moveto(0)
            self._canvas.yview_moveto(0)
            self._set_status("Vue\nréinitialisée")
            return

        xs, ys = [], []
        for c in self._comps.values():
            d = self._geom(c)
            w2, h2 = d["w"] // 2 + 30, d["h"] // 2 + 30
            xs += [c.cx - w2, c.cx + w2]
            ys += [c.cy - h2, c.cy + h2]
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
        bw, bh = max(1, maxx - minx), max(1, maxy - miny)

        cw = self._canvas.winfo_width()  or 800
        ch = self._canvas.winfo_height() or 600
        self._zoom = max(0.2, min(3.0, min(cw / bw, ch / bh)))
        self._ox = cw / 2 - ((minx + maxx) / 2) * self._zoom
        self._oy = ch / 2 - ((miny + maxy) / 2) * self._zoom
        self._redraw_all()
        self._canvas.xview_moveto(0)
        self._canvas.yview_moveto(0)
        self._set_status("Ajusté ⊡")

    # ── Câblage ──────────────────────────────────────────────────────────────

    def _start_wiring(self, comp_id: int, pin: str):
        """Démarre un câblage depuis (comp_id, pin) — extrait pour tests directs."""
        self._state    = "wiring"
        self._wire_src = (comp_id, pin)
        self._canvas.configure(cursor="crosshair")
        comp = self._comps[comp_id]
        # 3 lignes max : le label de statut du pied de palette a height=3.
        self._set_status(f"Fil depuis {comp.ref}.{pin}\nClic = cible\nÉchap = annuler")

    def _update_wire_preview(self, wx: float, wy: float):
        """@brief Aperçu de câblage en L (3 points) — extrait pour tests directs.

        Coude orthogonal `(x1,y1) -> (ex,y1) -> (ex,ey)` (H puis V). Si une
        broche libre se trouve à <= 12 px écran de (wx, wy), l'aperçu s'y
        termine (aimantation) et un halo bleu la met en évidence.

        @param wx, wy Point monde courant (curseur).
        """
        if self._state != "wiring" or not self._wire_src:
            return
        comp = self._comps.get(self._wire_src[0])
        if not comp:
            return
        dx, dy = self._geom(comp)["pins"][self._wire_src[1]]
        rdx, rdy = _rotate_pin(dx, dy, comp.rotation)
        x1, y1 = self._w2s(comp.cx + rdx, comp.cy + rdy)

        # Aimantation : broche la plus proche (hors source) à <= 12 px écran.
        target = self._find_pin_at(wx, wy)
        halo_xy = None
        if target and target != self._wire_src:
            tcomp = self._comps[target[0]]
            tdx, tdy = self._geom(tcomp)["pins"][target[1]]
            trdx, trdy = _rotate_pin(tdx, tdy, tcomp.rotation)
            ex, ey = self._w2s(tcomp.cx + trdx, tcomp.cy + trdy)
            halo_xy = (ex, ey)
        else:
            ex, ey = self._w2s(wx, wy)

        z = self._zoom
        self._canvas.delete("apercu")
        self._rubber_band = self._canvas.create_line(
            x1, y1, ex, y1, ex, ey,
            fill="#4ade80", width=max(1, int(2*z)), dash=(5, 3), tags=("apercu",))
        if halo_xy:
            hx, hy = halo_xy
            hr = _PIN_R * z + 4
            self._canvas.create_oval(hx-hr, hy-hr, hx+hr, hy+hr,
                                     outline=BLUE, width=max(1, int(2*z)),
                                     tags=("apercu",))

    def _add_wire(self, from_id: int, from_pin: str,
                  to_id: int, to_pin: str) -> Optional['WireInst']:
        """@brief Crée un fil broche-à-broche — extrait pour tests / `_complete_wire`.

        @return WireInst créé, ou None si ce fil existe déjà (doublon silencieux).
        """
        for w in self._wires:
            if ({w.from_comp_id, w.from_pin} == {from_id, from_pin} and
                    {w.to_comp_id, w.to_pin} == {to_id, to_pin}):
                return None
        self._push_undo()
        wire = WireInst(self._next_id, from_id, from_pin, to_id, to_pin)
        self._next_id += 1
        self._wires.append(wire)
        self._draw_wire(wire)
        # Rafraîchit les broches des 2 composants (passent de « rouge » à pleines)
        for cid in (from_id, to_id):
            if cid in self._comps:
                self._draw_comp(self._comps[cid])
                self._redraw_wires_of(cid)
        return wire

    def _complete_wire(self, dst: tuple[int, str]):
        src_cid, src_pin = self._wire_src
        dst_cid, dst_pin = dst
        self._add_wire(src_cid, src_pin, dst_cid, dst_pin)
        self._cancel_wiring()

    def _cancel_wiring(self):
        self._state    = "idle"
        self._wire_src = None
        self._canvas.delete("apercu")
        self._rubber_band = None
        self._canvas.configure(cursor="")
        self._set_status("Prêt")

    # ── Sélection ────────────────────────────────────────────────────────────

    def _select(self, comp_id: int, append: bool = False):
        if comp_id not in self._comps:
            return
        if not append:
            self._deselect()
        if comp_id in self._selected_ids:
            return
        self._selected_ids.add(comp_id)
        comp = self._comps.get(comp_id)
        if comp:
            defn  = self._geom(comp)
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
        for comp_id in self._selected_ids:
            self._canvas.delete(f"sel_{comp_id}")
        self._selected_ids.clear()

    def _select_in_rect(self, x0, y0, x1, y1):
        """Sélectionne les composants dont le centre tombe dans le rectangle monde."""
        minx, maxx = sorted((x0, x1))
        miny, maxy = sorted((y0, y1))
        self._deselect()
        for comp in self._comps.values():
            if minx <= comp.cx <= maxx and miny <= comp.cy <= maxy:
                self._select(comp.id, append=True)

    # ── Édition / suppression ─────────────────────────────────────────────────

    def _rotate_comp(self, comp_id: int):
        """Tourne un composant unique (menu contextuel)."""
        comp = self._comps.get(comp_id)
        if comp and comp.comp_type not in ("GND", "VCC"):
            self._push_undo()
            comp.rotation = (comp.rotation + 90) % 360
            self._redraw_all()

    def _rotate_selection(self):
        """Tourne la sélection d'un quart de tour en une seule annulation."""
        rotatables = [self._comps[cid] for cid in self._selected_ids
                       if cid in self._comps and self._comps[cid].comp_type not in ("GND", "VCC")]
        if not rotatables:
            return
        self._push_undo()
        for comp in rotatables:
            comp.rotation = (comp.rotation + 90) % 360
        self._redraw_all()

    def _edit_comp(self, comp_id: int):
        comp = self._comps.get(comp_id)
        if not comp:
            return
        dlg = tk.Toplevel(self)
        dlg.title(f"Modifier {comp.ref}")
        dlg.configure(bg=OVERLAY)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.lift()

        fields = [("Référence :", comp.ref), ("Valeur :", comp.value)]
        vars_list = []
        for row, (lbl, val) in enumerate(fields):
            tk.Label(dlg, text=lbl, fg=TEXT_MUTED, bg=OVERLAY,
                     font=(FONT_FAMILY, 10)).grid(row=row, column=0, padx=14,
                                                  pady=(14 if row == 0 else 6, 4),
                                                  sticky="w")
            v = tk.StringVar(value=val)
            tk.Entry(dlg, textvariable=v, bg=SURFACE, fg=TEXT,
                     font=(FONT_FAMILY, 11), relief="flat", width=16,
                     insertbackground=TEXT).grid(row=row, column=1,
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
                  bg=BLUE, fg=TEXT, relief="flat",
                  font=(FONT_FAMILY, 10, "bold"), padx=16, pady=5,
                  cursor="hand2").grid(row=2, column=0, columnspan=2, pady=12)
        dlg.bind("<Return>", lambda _: _save())

    def _delete_selected(self):
        self._delete_selection()

    def _delete_selection(self):
        """Supprime la sélection et ses fils avec un unique instantané undo."""
        ids = set(self._selected_ids)
        if not ids:
            return
        self._push_undo()
        self._wires = [w for w in self._wires
                       if w.from_comp_id not in ids and w.to_comp_id not in ids]
        for comp_id in ids:
            self._comps.pop(comp_id, None)
        self._deselect()
        self._redraw_all()

    def _delete_comp(self, comp_id: int):
        """Supprime un seul composant (menu contextuel) sans toucher au reste
        de la sélection en cours (revue Task 6 : supprimer B ne doit pas
        désélectionner un A sans rapport)."""
        if comp_id not in self._comps:
            return
        self._push_undo()
        self._wires = [w for w in self._wires
                       if w.from_comp_id != comp_id and w.to_comp_id != comp_id]
        self._comps.pop(comp_id, None)
        self._invalider_geom(comp_id)
        self._selected_ids.discard(comp_id)
        self._canvas.delete(f"sel_{comp_id}")
        self._redraw_all()

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
        self._selected_ids.clear()
        self._wire_src     = None
        self._rubber_band  = None
        self._drag_comp_id = None
        for btn in self._palette_btns.values():
            btn.configure(bg=OVERLAY, relief="flat")
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
            self._ensure_dyn_def(t)           # puce catalogue "U::NE555" (§4)
            if t not in self._defs:
                continue                      # type inconnu : ignoré
            po = c.get("pinout")
            ci = CompInst(int(c["id"]), c["ref"], t, c.get("value", ""),
                          int(c["cx"]), int(c["cy"]), int(c.get("rotation", 0)),
                          pinout=({n: tuple(v) for n, v in po.items()}
                                  if po is not None else None),
                          forme_primitives=c.get("forme_primitives"))
            new_comps[ci.id] = ci
            max_id = max(max_id, ci.id)

        next_id = max(int(d.get("next_id", 1)), max_id + 1)

        new_wires: list[WireInst] = []
        for w in d.get("wires", []):
            fa, ta = w.get("from_comp_id"), w.get("to_comp_id")
            if fa not in new_comps or ta not in new_comps:
                continue
            fp, tp = w.get("from_pin"), w.get("to_pin")
            if fp not in self._geom(new_comps[fa])["pins"]:
                continue
            if tp not in self._geom(new_comps[ta])["pins"]:
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
        self._selected_ids.clear()
        self._wire_src     = None
        self._rubber_band  = None
        self._drag_comp_id = None
        self._invalider_geom()      # ids réattribués : cache d'instance périmé
        self._redraw_all()
        self._set_status("Schéma\nchargé")

    # ── Export netlist ────────────────────────────────────────────────────────

    def _build_net_namer(self):
        """@brief Nommeur de nœuds (Union-Find broche->réseau) partagé par
        `to_netlist()` et `exporter_composants()`.

        @return callable net_of(node: "id:broche") -> nom de réseau ("GND",
                "VCC" ou "NET<n>").
        """
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

        return net_of

    def to_netlist(self) -> str:
        """@brief Génère une netlist SPICE depuis le schéma courant."""
        real_comps = {cid: c for cid, c in self._comps.items()
                      if c.comp_type not in ("GND", "VCC")}
        if not real_comps:
            return ""

        net_of = self._build_net_namer()

        lines = ["* Schéma généré par Circuit Analyzer — éditeur interactif", ""]
        for comp in real_comps.values():
            pins = self._geom(comp)["pins"]
            nets = " ".join(net_of(f"{comp.id}:{pn}") for pn in pins)
            _t, v = type_reel(comp.comp_type)
            lines.append(f"{comp.ref} {nets} {v or comp.value}")

        return "\n".join(lines)

    def exporter_composants(self) -> list:
        """@brief Exporte les composants réels en objets `Composant` (Task 5).

        Contrairement à `to_netlist()` (netlist SPICE textuelle — pins
        positionnelles limitées aux quelques broches génériques que
        `circuit_analyzer.composant` connaît pour "U", ce qui tronquerait une
        puce catalogue multi-broches à la relecture), cet export construit les
        `Composant` directement en mémoire et garde les broches NOMMÉES
        (ex. "1".."8" d'un NE555). `type_reel` sépare comp_type -> une puce
        catalogue reste identifiable par `circuit_analyzer.catalogue.identifier`.

        @return list[Composant] Composants réels (GND/VCC exclus).
        """
        real_comps = {cid: c for cid, c in self._comps.items()
                      if c.comp_type not in ("GND", "VCC")}
        if not real_comps:
            return []

        net_of = self._build_net_namer()

        composants = []
        for comp in real_comps.values():
            pins = self._geom(comp)["pins"]
            t, v = type_reel(comp.comp_type)
            broches = {pn: net_of(f"{comp.id}:{pn}") for pn in pins}
            composants.append(Composant(ref=comp.ref, type=t, pins=broches,
                                        value=v or comp.value))
        return composants

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
            for pn in self._geom(comp)["pins"]:
                if not self._pin_connected(comp.id, pn):
                    loose.append((comp.ref, pn))
        return loose
