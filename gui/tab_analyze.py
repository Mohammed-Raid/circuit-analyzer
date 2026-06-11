import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox
from circuit_analyzer.composant import lire_netlist as parse_file, construire_graphe as build_graph
from circuit_analyzer.xml import lire_xml as parse_xml, generer_xml as components_to_xml
from circuit_analyzer.detecteur import analyser as match_patterns
from circuit_analyzer.rapport import generate
from gui.circuit_viewer import show_circuit

from gui.theme import BG, CARD, CARD2, BORDER, TEXT, MUTED, BLUE

# Circuit type → (bg, text, icon)
TYPE_COLORS = {
    "AOP":         ("#1a237e", "#90caf9", "🔬"),
    "Transistor":  ("#4a148c", "#ce93d8", "📡"),
    "MOSFET":      ("#311b92", "#b39ddb", "📡"),
    "Pont":        ("#1b5e20", "#a5d6a7", "🔌"),
    "Redresseur":  ("#1b5e20", "#a5d6a7", "🔌"),
    "Filtre":      ("#0d47a1", "#90caf9", "📊"),
    "Condensateur":("#004d40", "#80cbc4", "⚡"),
    "Diviseur":    ("#33691e", "#c5e1a5", "⚖"),
    "Absorbeur":   ("#e65100", "#ffcc80", "🛡"),
    "Protection":  ("#b71c1c", "#ef9a9a", "🛡"),
    "Fusible":     ("#b71c1c", "#ef9a9a", "🛡"),
    "Diode":       ("#f57f17", "#fff176", "💡"),
    "Miroir":      ("#4a148c", "#ce93d8", "🔄"),
    "default":     ("#1e293b", "#94a3b8", "⚙"),
}

def _type_style(name: str):
    for key, style in TYPE_COLORS.items():
        if key.lower() in name.lower():
            return style
    return TYPE_COLORS["default"]


class TabAnalyze:
    def __init__(self, parent):
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color=BG)
        self._file_path = tk.StringVar()
        self._report_text = ""
        self._results = []
        self._all_refs = []
        self._unclassified = []
        self._comp_info = {}
        self._comps = []          # parsed Component objects (for XML export)
        self._build()

    def _build(self):
        # ── Page header ──────────────────────────────────────────────────────
        header = ctk.CTkFrame(self.frame, fg_color=CARD,
                              corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        hinner = ctk.CTkFrame(header, fg_color="transparent")
        hinner.pack(fill="both", expand=True, padx=28)

        ctk.CTkLabel(hinner, text="Analyser un circuit",
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color=TEXT).pack(side="left", pady=18)
        ctk.CTkLabel(hinner, text="Chargez un fichier netlist .txt ou schéma .xml",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=MUTED).pack(side="left", padx=14, pady=18)

        # ── File picker bar ──────────────────────────────────────────────────
        picker = ctk.CTkFrame(self.frame, fg_color=CARD2,
                              corner_radius=0, height=62)
        picker.pack(fill="x")
        picker.pack_propagate(False)

        pin = ctk.CTkFrame(picker, fg_color="transparent")
        pin.pack(fill="both", expand=True, padx=28)

        self._entry = ctk.CTkEntry(
            pin,
            textvariable=self._file_path,
            placeholder_text="  Choisir un fichier .txt ou .xml …",
            height=38, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color="#111827", border_color=BORDER,
            text_color=TEXT,
        )
        self._entry.pack(side="left", expand=True, fill="x",
                         padx=(0, 10), pady=12)
        self._entry.bind("<Double-Button-1>", lambda _: self._browse())

        ctk.CTkButton(pin, text="📂  Parcourir",
                      width=130, height=38, corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color="#1e293b", hover_color="#263347",
                      border_width=1, border_color=BORDER,
                      command=self._browse).pack(side="left", padx=(0, 8))

        self._analyze_btn = ctk.CTkButton(
            pin, text="▶  Analyser",
            width=130, height=38, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            fg_color="#16a34a", hover_color="#15803d",
            command=self._analyze,
        )
        self._analyze_btn.pack(side="left")

        # ── Stats row (hidden until first run) ───────────────────────────────
        self._stats_row = ctk.CTkFrame(self.frame, fg_color=BG,
                                       corner_radius=0)
        self._s_total  = _StatCard(self._stats_row, "—", "Composants", "#3b82f6", "📦")
        self._s_groups = _StatCard(self._stats_row, "—", "Circuits identifiés", "#10b981", "✅")
        self._s_pct    = _StatCard(self._stats_row, "—", "Taux de classification", "#8b5cf6", "📈")
        self._s_unc    = _StatCard(self._stats_row, "—", "Non classifiés", "#ef4444", "⚠")
        for sc in (self._s_total, self._s_groups, self._s_pct, self._s_unc):
            sc.pack(side="left", expand=True, padx=8, pady=12)

        # ── Content: empty state or results ──────────────────────────────────
        self._body = ctk.CTkFrame(self.frame, fg_color=BG,
                                  corner_radius=0)
        self._body.pack(fill="both", expand=True)
        self._body.grid_columnconfigure(0, weight=1)
        self._body.grid_rowconfigure(0, weight=1)

        self._empty_state = _EmptyState(self._body)
        self._empty_state.grid(row=0, column=0)

        # Lightweight scroll container — tk.Canvas is much faster than CTkScrollableFrame
        scroll_outer = tk.Frame(self._body, bg=BG)
        scroll_outer.grid(row=0, column=0, sticky="nsew")
        scroll_outer.grid_columnconfigure(0, weight=1)
        scroll_outer.grid_rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(scroll_outer, bg=BG,
                                  highlightthickness=0, bd=0)
        vsb = tk.Scrollbar(scroll_outer, orient="vertical",
                           command=self._canvas.yview,
                           bg="#1e293b", troughcolor=BG)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        self._canvas.grid(row=0, column=0, sticky="nsew")

        self._results_view = tk.Frame(self._canvas, bg=BG)
        self._canvas_win = self._canvas.create_window(
            (0, 0), window=self._results_view, anchor="nw")

        self._results_view.bind("<Configure>", self._on_scroll_configure)
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        # Mousewheel active only while cursor is inside the scroll area
        scroll_outer.bind("<Enter>", lambda _: self._canvas.bind_all(
            "<MouseWheel>", self._on_mousewheel))
        scroll_outer.bind("<Leave>", lambda _: self._canvas.unbind_all(
            "<MouseWheel>"))

        scroll_outer.grid_remove()   # hide until first analysis
        self._scroll_outer = scroll_outer

        # ── Bottom bar ───────────────────────────────────────────────────────
        bar = ctk.CTkFrame(self.frame, fg_color=CARD2,
                           corner_radius=0, height=50)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        bar_inner = ctk.CTkFrame(bar, fg_color="transparent")
        bar_inner.pack(fill="both", padx=28)
        ctk.CTkButton(bar_inner, text="💾  Sauvegarder",
                      width=140, height=34, corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 11),
                      fg_color="#1e293b", hover_color="#263347",
                      border_width=1, border_color=BORDER,
                      command=self._save).pack(side="left", pady=8)
        ctk.CTkButton(bar_inner, text="📋  Copier rapport",
                      width=140, height=34, corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 11),
                      fg_color="#1e293b", hover_color="#263347",
                      border_width=1, border_color=BORDER,
                      command=self._copy).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(bar_inner, text="🔧  Exporter XML (design)",
                      width=190, height=34, corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 11),
                      fg_color="#1e293b", hover_color="#263347",
                      border_width=1, border_color=BORDER,
                      command=self._export_xml).pack(side="left", padx=8, pady=8)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Choisir un fichier netlist",
            filetypes=[
                ("Netlists & schémas", "*.txt *.xml"),
                ("Fichiers texte", "*.txt"),
                ("Schémas XML (BoardSCH)", "*.xml"),
                ("Tous", "*.*"),
            ],
        )
        if path:
            self._file_path.set(path)

    def _analyze(self):
        path = self._file_path.get().strip()
        if not path:
            messagebox.showwarning("Attention",
                "Veuillez sélectionner un fichier.")
            return

        self._analyze_btn.configure(state="disabled", text="⏳  Analyse…")
        self.frame.update()

        try:
            if path.lower().endswith('.xml'):
                comps = parse_xml(path)
            else:
                comps    = parse_file(path)
            graph    = build_graph(comps)
            results  = match_patterns(graph)
            all_refs = [c.ref for c in comps]
            report   = generate(results, path, len(comps), all_refs=all_refs)

            self._report_text = report
            self._results     = results
            self._all_refs    = all_refs
            self._comps       = comps

            classified  = {ref for r in results for ref in r["components"]}
            unclassified = [r for r in all_refs if r not in classified]
            self._unclassified = unclassified

            total = len(comps)
            pct   = int(100 * len(classified) / total) if total else 0

            self._s_total.update(str(total))
            self._s_groups.update(str(len(results)))
            self._s_pct.update(f"{pct}%")
            self._s_unc.update(str(len(unclassified)))

            self._stats_row.pack(fill="x", padx=20, before=self._body)
            self._scroll_outer.grid()
            # Build comp_info dict for the schematic viewer
            self._comp_info = {
                c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
                for c in comps
            }
            self._render_cards(results, unclassified)

        except FileNotFoundError:
            messagebox.showerror("Erreur", f"Fichier introuvable :\n{path}")
            self._stats_row.pack_forget()
            self._scroll_outer.grid_remove()
            self._empty_state.grid()
        except ValueError as e:
            messagebox.showerror("Erreur netlist", str(e))
            self._stats_row.pack_forget()
            self._scroll_outer.grid_remove()
            self._empty_state.grid()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            self._stats_row.pack_forget()
            self._scroll_outer.grid_remove()
            self._empty_state.grid()
        finally:
            self._analyze_btn.configure(state="normal", text="▶  Analyser")

    def _save(self):
        if not self._report_text:
            messagebox.showinfo("Info", "Aucun rapport à sauvegarder.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texte", "*.txt")],
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._report_text)
            messagebox.showinfo("Succès", f"Rapport sauvegardé :\n{path}")

    def _export_xml(self):
        if not self._comps:
            messagebox.showinfo("Info", "Analysez d'abord un circuit.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xml",
            filetypes=[("Schéma BoardSCH", "*.xml")],
            title="Exporter le schéma pour le logiciel de design",
        )
        if not path:
            return
        try:
            xml = components_to_xml(self._comps, results=self._results)
            with open(path, "w", encoding="utf-8") as f:
                f.write(xml)
            messagebox.showinfo("Succès ✓",
                f"Schéma XML exporté :\n{path}\n\n"
                "Ouvrable dans le logiciel de design.")
        except Exception as e:
            messagebox.showerror("Erreur export XML", str(e))

    def _on_scroll_configure(self, _=None):
        self._canvas.configure(
            scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._canvas_win, width=event.width)

    def _copy(self):
        if not self._report_text:
            messagebox.showinfo("Info", "Aucun rapport à copier.")
            return
        self.frame.clipboard_clear()
        self.frame.clipboard_append(self._report_text)
        messagebox.showinfo("Copié ✓", "Rapport copié dans le presse-papiers.")

    # ── Card rendering ───────────────────────────────────────────────────────

    def _on_mousewheel(self, event):
        """Single handler — registered once on _results_view so every child inherits it."""
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _render_cards(self, results: list, unclassified: list):
        # Clear old cards
        for w in self._results_view.winfo_children():
            w.destroy()

        self._empty_state.grid_remove()

        # Structure en étages (îlots fonctionnels)
        self._render_islands(results)

        # Group by type categories
        groups = {}
        for r in results:
            cat = _category(r["circuit_type"])
            groups.setdefault(cat, []).append(r)

        for cat, items in groups.items():
            # Category header
            ch = ctk.CTkFrame(self._results_view,
                              fg_color="transparent")
            ch.pack(fill="x", padx=16, pady=(12, 2))
            ctk.CTkLabel(ch, text=cat,
                         font=ctk.CTkFont("Segoe UI", 10, "bold"),
                         text_color=MUTED).pack(side="left")
            ctk.CTkFrame(ch, height=1, fg_color=BORDER).pack(
                side="left", fill="x", expand=True, padx=10)

            # Circuit cards in a grid (2 per row)
            grid = ctk.CTkFrame(self._results_view,
                                fg_color="transparent")
            grid.pack(fill="x", padx=16, pady=2)
            grid.grid_columnconfigure((0, 1), weight=1)

            for i, item in enumerate(items):
                card = _CircuitCard(grid, item, self._comp_info)
                card.grid(row=i // 2, column=i % 2,
                          sticky="ew", padx=4, pady=4)

        # Unclassified section
        self._render_unclassified(unclassified)

    def _render_islands(self, results):
        """Panneau repliable « Structure en étages » (îlots fonctionnels)."""
        ilots = getattr(results, 'ilots', [])
        if not ilots:
            return

        hdr = ctk.CTkFrame(self._results_view, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(14, 2))
        ctk.CTkLabel(hdr, text="STRUCTURE EN ÉTAGES",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=BLUE).pack(side="left")
        ctk.CTkFrame(hdr, height=1, fg_color=BORDER).pack(
            side="left", fill="x", expand=True, padx=10)

        for ilot in ilots:
            _IslandSection(self._results_view, ilot, results).pack(
                fill="x", padx=16, pady=3)

    def _render_unclassified(self, unclassified: list):
        if unclassified:
            uch = ctk.CTkFrame(self._results_view,
                               fg_color="transparent")
            uch.pack(fill="x", padx=16, pady=(16, 2))
            ctk.CTkLabel(uch, text="NON CLASSIFIÉS",
                         font=ctk.CTkFont("Segoe UI", 10, "bold"),
                         text_color="#ef4444").pack(side="left")
            ctk.CTkFrame(uch, height=1, fg_color="#4d1515").pack(
                side="left", fill="x", expand=True, padx=10)

            uc_card = ctk.CTkFrame(self._results_view,
                                   fg_color="#1c0a0a",
                                   corner_radius=12,
                                   border_width=1,
                                   border_color="#7f1d1d")
            uc_card.pack(fill="x", padx=16, pady=(4, 16))
            wrap = ctk.CTkFrame(uc_card, fg_color="transparent")
            wrap.pack(fill="x", padx=14, pady=10)
            for chunk in _chunks(unclassified, 8):
                row = ctk.CTkFrame(wrap, fg_color="transparent")
                row.pack(anchor="w", pady=2)
                for ref in chunk:
                    ctk.CTkLabel(row, text=ref,
                                 font=ctk.CTkFont("Consolas", 11, "bold"),
                                 text_color="#fca5a5",
                                 fg_color="#7f1d1d",
                                 corner_radius=4).pack(
                                     side="left", padx=3)


# ── Helper widgets ────────────────────────────────────────────────────────────

class _StatCard(ctk.CTkFrame):
    def __init__(self, parent, value, label, color, icon):
        super().__init__(parent, corner_radius=12,
                         fg_color=CARD,
                         border_width=1, border_color=BORDER)
        ctk.CTkLabel(self, text=icon,
                     font=ctk.CTkFont(size=20),
                     text_color=color).pack(pady=(12, 2))
        self._val = ctk.CTkLabel(self, text=value,
                                  font=ctk.CTkFont("Segoe UI", 26, "bold"),
                                  text_color=color)
        self._val.pack()
        ctk.CTkLabel(self, text=label,
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=MUTED).pack(pady=(2, 12))

    def update(self, value: str):
        self._val.configure(text=value)


class _EmptyState(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        ctk.CTkLabel(self, text="📂",
                     font=ctk.CTkFont(size=56),
                     text_color="#1e293b").pack(pady=(60, 8))
        ctk.CTkLabel(self, text="Aucun circuit chargé",
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color="#334155").pack()
        ctk.CTkLabel(self,
                     text="Cliquez sur Parcourir pour charger\nun fichier netlist .txt ou schéma .xml",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color=MUTED, justify="center").pack(pady=8)


class _IslandSection(ctk.CTkFrame):
    """Section repliable pour un îlot fonctionnel (structure en étages)."""

    def __init__(self, parent, ilot: dict, results):
        super().__init__(parent, corner_radius=10,
                         fg_color=CARD,
                         border_width=1, border_color=BORDER)
        self._ouvert = True

        nb = len(ilot['composants'])
        titre = f"{ilot['label']}  ({nb} composant{'s' if nb > 1 else ''})"
        self._btn = ctk.CTkButton(
            self, text=f"▼  {titre}",
            anchor="w", height=32, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            fg_color="transparent", hover_color=CARD2,
            text_color=TEXT,
            command=self._toggle,
        )
        self._btn.pack(fill="x", padx=6, pady=(4, 0))
        self._titre = titre

        self._contenu = ctk.CTkFrame(self, fg_color="transparent")
        self._contenu.pack(fill="x", padx=20, pady=(0, 8))

        if ilot['circuits']:
            for idx in ilot['circuits']:
                try:
                    match = results[idx]
                except (IndexError, TypeError):
                    continue
                surs = [s['ref'] for s in match.get('satellites', [])
                        if s.get('status') == 'sure']
                suffixe = f"  (+ {', '.join(surs)})" if surs else ''
                ligne = (f"[{idx + 1}] {match['circuit_type']} : "
                         f"{', '.join(match['components'])}{suffixe}")
                ctk.CTkLabel(self._contenu, text=ligne,
                             font=ctk.CTkFont("Consolas", 11),
                             text_color=MUTED, anchor="w",
                             justify="left").pack(fill="x", pady=1)
        else:
            ctk.CTkLabel(self._contenu,
                         text=', '.join(ilot['composants']),
                         font=ctk.CTkFont("Consolas", 11),
                         text_color=MUTED, anchor="w",
                         wraplength=700,
                         justify="left").pack(fill="x", pady=1)

    def _toggle(self):
        self._ouvert = not self._ouvert
        if self._ouvert:
            self._contenu.pack(fill="x", padx=20, pady=(0, 8))
            self._btn.configure(text=f"▼  {self._titre}")
        else:
            self._contenu.pack_forget()
            self._btn.configure(text=f"▶  {self._titre}")


class _CircuitCard(ctk.CTkFrame):
    def __init__(self, parent, result: dict, comp_info: dict = None):
        bg, fg, icon = _type_style(result["circuit_type"])
        super().__init__(parent, corner_radius=12,
                         fg_color=bg,
                         border_width=1,
                         border_color=_darken(bg))
        self._result = result
        self._comp_info = comp_info or {}

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(hdr, text=icon,
                     font=ctk.CTkFont(size=16)).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(hdr, text=result["circuit_type"],
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=fg, wraplength=220,
                     justify="left", anchor="w").pack(side="left")
        ctk.CTkButton(hdr, text="🔬",
                      width=30, height=24, corner_radius=6,
                      font=ctk.CTkFont(size=14),
                      fg_color=_darken(bg), hover_color=_brighten(_darken(bg)),
                      command=self._open_schema).pack(side="right")

        # Divider
        ctk.CTkFrame(self, height=1,
                     fg_color=_darken(bg)).pack(
                         fill="x", padx=12, pady=2)

        # Components
        c_row = ctk.CTkFrame(self, fg_color="transparent")
        c_row.pack(fill="x", padx=12, pady=(4, 2))
        ctk.CTkLabel(c_row, text="Composants",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=MUTED, width=75,
                     anchor="w").pack(side="left")
        refs_text = "  ".join(result["components"])
        ctk.CTkLabel(c_row, text=refs_text,
                     font=ctk.CTkFont("Consolas", 10, "bold"),
                     text_color=fg, wraplength=230,
                     justify="left", anchor="w").pack(
                         side="left", fill="x", expand=True)

        # Nodes
        if result.get("nodes"):
            n_row = ctk.CTkFrame(self, fg_color="transparent")
            n_row.pack(fill="x", padx=12, pady=(0, 10))
            ctk.CTkLabel(n_row, text="Nœuds",
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color=MUTED, width=75,
                         anchor="w").pack(side="left")
            nodes = [n for n in result["nodes"] if n]
            nodes_text = " → ".join(nodes[:3])
            ctk.CTkLabel(n_row, text=nodes_text,
                         font=ctk.CTkFont("Consolas", 9),
                         text_color=_brighten(bg),
                         wraplength=230,
                         justify="left", anchor="w").pack(side="left")

    def _open_schema(self):
        show_circuit(self._result, self._comp_info)


# ── Utilities ────────────────────────────────────────────────────────────────

def _category(name: str) -> str:
    if "AOP" in name:           return "AMPLIFICATEURS OPÉRATIONNELS"
    if any(x in name for x in ("Transistor", "MOSFET", "Miroir", "Relais")):
        return "TRANSISTORS & COMMUTATION"
    if any(x in name for x in ("Pont", "Redresseur", "Crête", "Roue")):
        return "REDRESSEURS & DIODES"
    if any(x in name for x in ("Filtre", "Condensateur", "Absorbeur", "LC", "RC")):
        return "FILTRES & PASSIFS"
    if any(x in name for x in ("Diviseur", "Fusible", "Protection", "ESD")):
        return "PROTECTION & AUTRES"
    return "AUTRES"


def _darken(hex_color: str) -> str:
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    r, g, b = max(0, r - 20), max(0, g - 20), max(0, b - 20)
    return f"#{r:02x}{g:02x}{b:02x}"


def _brighten(hex_color: str) -> str:
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    r, g, b = min(255, r + 60), min(255, g + 60), min(255, b + 60)
    return f"#{r:02x}{g:02x}{b:02x}"


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]
