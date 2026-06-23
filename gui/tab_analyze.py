"""
@file tab_analyze.py
@brief Onglet « Analyser » : chargement d'un fichier, analyse, cartes de résultats et exports.
"""
import tkinter as tk
import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog, messagebox
# Le cœur d'analyse tire networkx (~1 s). Importé à la demande (chargement /
# analyse d'un circuit) via _coeur_analyse(), pas au démarrage : la fenêtre
# s'affiche sans attendre networkx.
def _coeur_analyse():
    """@brief Importe et renvoie les fonctions du cœur d'analyse (lazy, networkx)."""
    from circuit_analyzer.composant import lire_netlist as parse_file, construire_graphe as build_graph
    from circuit_analyzer.xml import lire_xml as parse_xml, generer_xml as components_to_xml
    from circuit_analyzer.detecteur import analyser as match_patterns
    from circuit_analyzer.rapport import generate
    from circuit_analyzer.drc import verifier_drc
    return (parse_file, build_graph, parse_xml, components_to_xml,
            match_patterns, generate, verifier_drc)
# gui.circuit_viewer importe matplotlib + schemdraw (~2 s). On le charge à la
# demande (ouverture d'un schéma), pas au démarrage : la fenêtre s'affiche vite.

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
    """@brief Style visuel (fond, texte, icône) associé à un type de circuit.

    @param name Nom du circuit détecté.
    @return tuple (couleur_fond, couleur_texte, icône).
    """
    for key, style in TYPE_COLORS.items():
        if key.lower() in name.lower():
            return style
    return TYPE_COLORS["default"]


class TabAnalyze:
    """@brief Onglet « Analyser » : sélection de fichier, analyse et affichage des résultats."""

    def __init__(self, parent, on_pattern_created=None):
        """@brief Construit l'onglet et son état interne.

        @param parent Widget parent (zone de contenu).
        @param on_pattern_created Callback() après création d'un pattern
                                  (rafraîchit l'onglet Circuits).
        """
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color=BG)
        self._on_pattern_created_cb = on_pattern_created
        self._file_path = tk.StringVar()
        self._report_text    = ""
        self._results        = []
        self._all_refs       = []
        self._unclassified   = []
        self._comp_info      = {}
        self._comps          = []
        self._graph          = None
        self._drc_violations = []
        self._build()

    def _build(self):
        """@brief Construit l'en-tête, le sélecteur de fichier, les statistiques et la zone de résultats."""
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
        ctk.CTkLabel(hinner, text="Chargez un fichier netlist (.txt .cir .sp .net) ou schéma .xml",
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
            placeholder_text="  Choisir un fichier .txt / .cir / .sp / .net / .xml …",
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

        ctk.CTkButton(pin, text="Charger demo",
                      width=130, height=38, corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color="#0f766e", hover_color="#115e59",
                      border_width=1, border_color=BORDER,
                      command=self._load_demo).pack(side="left", padx=(0, 8))

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
        self._btn_reseau = ctk.CTkButton(
            bar_inner, text="🕸  Vue réseau",
            width=140, height=34, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 11),
            fg_color="#1e293b", hover_color="#263347",
            border_width=1, border_color=BORDER,
            state="disabled",
            command=self._open_network_viewer)
        self._btn_reseau.pack(side="left", padx=8, pady=8)
        self._btn_imped = ctk.CTkButton(
            bar_inner, text="Ω  Impédance équiv.",
            width=170, height=34, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 11),
            fg_color="#1e293b", hover_color="#263347",
            border_width=1, border_color=BORDER,
            state="disabled",
            command=self._open_impedance)
        self._btn_imped.pack(side="left", padx=8, pady=8)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _browse(self):
        """@brief Ouvre un sélecteur de fichier et mémorise le chemin choisi."""
        path = filedialog.askopenfilename(
            title="Choisir un fichier netlist",
            filetypes=[
                ("Netlists & schémas", "*.txt *.xml *.cir *.sp *.net"),
                ("Fichiers texte", "*.txt"),
                ("SPICE / LTspice", "*.cir *.sp"),
                ("KiCad netlist", "*.net"),
                ("Schémas XML (BoardSCH)", "*.xml"),
                ("Tous", "*.*"),
            ],
        )
        if path:
            self._file_path.set(path)

    def _load_demo(self):
        """@brief Charge le fichier de demo recommande et lance l'analyse."""
        path = _find_demo_file()
        if not path:
            messagebox.showerror(
                "Demo introuvable",
                "Aucun fichier de demo disponible dans circuits_industriels/ ou exemples/.",
            )
            return
        self._file_path.set(path)
        self._analyze()

    def _analyze(self):
        """@brief Analyse le fichier sélectionné et met à jour statistiques et cartes.

        Lit la netlist/XML, construit le graphe, lance la détection, génère le
        rapport et affiche les résultats ; gère les erreurs via des boîtes de dialogue.
        """
        path = self._file_path.get().strip()
        if not path:
            messagebox.showwarning("Attention",
                "Veuillez sélectionner un fichier.")
            return

        self._analyze_btn.configure(state="disabled", text="⏳  Analyse…")
        self._btn_reseau.configure(state="disabled")
        self.frame.update()

        try:
            (parse_file, build_graph, parse_xml, _components_to_xml,
             match_patterns, generate, verifier_drc) = _coeur_analyse()
            if path.lower().endswith('.xml'):
                comps = parse_xml(path)
            else:
                comps    = parse_file(path)
            graph    = build_graph(comps)
            results  = match_patterns(graph)
            all_refs = [c.ref for c in comps]
            report   = generate(results, path, len(comps), all_refs=all_refs)
            drc      = verifier_drc(results, graph)

            self._report_text    = report
            self._results        = results
            self._all_refs       = all_refs
            self._comps          = comps
            self._graph          = graph
            self._drc_violations = drc

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
            self._btn_reseau.configure(state="normal")
            self._btn_imped.configure(state="normal")
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
            self._graph = None
            self._drc_violations = []
        except ValueError as e:
            messagebox.showerror("Erreur netlist", str(e))
            self._stats_row.pack_forget()
            self._scroll_outer.grid_remove()
            self._empty_state.grid()
            self._graph = None
            self._drc_violations = []
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            self._stats_row.pack_forget()
            self._scroll_outer.grid_remove()
            self._empty_state.grid()
            self._graph = None
            self._drc_violations = []
        finally:
            self._analyze_btn.configure(state="normal", text="▶  Analyser")

    def _save(self):
        """@brief Sauvegarde le rapport texte courant dans un fichier choisi par l'utilisateur."""
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
        """@brief Exporte le schéma BoardSCH XML (groupé par circuit) vers un fichier."""
        if not self._comps:
            messagebox.showinfo("Info", "Analysez d'abord un circuit.")
            return
        current_path = self._file_path.get().strip()
        stem = Path(current_path).stem if current_path else "schema"
        path = filedialog.asksaveasfilename(
            defaultextension=".xml",
            filetypes=[("Schéma BoardSCH", "*.xml")],
            title="Exporter le schéma pour le logiciel de design",
            initialfile=f"{stem}_groupe.xml",
        )
        if not path:
            return
        try:
            from circuit_analyzer.xml import generer_xml as components_to_xml
            xml = components_to_xml(self._comps, results=self._results)
            with open(path, "w", encoding="utf-8") as f:
                f.write(xml)
            messagebox.showinfo("Succès ✓",
                f"Schéma XML exporté :\n{path}\n\n"
                "Ouvrable dans le logiciel de design.")
        except Exception as e:
            messagebox.showerror("Erreur export XML", str(e))

    def _on_scroll_configure(self, _=None):
        """@brief Met à jour la zone défilable du canvas après reconfiguration du contenu."""
        self._canvas.configure(
            scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        """@brief Ajuste la largeur de la fenêtre interne au redimensionnement du canvas.

        @param event Événement Tk de configuration (porte la nouvelle largeur).
        """
        self._canvas.itemconfig(self._canvas_win, width=event.width)

    def _copy(self):
        """@brief Copie le rapport texte courant dans le presse-papiers."""
        if not self._report_text:
            messagebox.showinfo("Info", "Aucun rapport à copier.")
            return
        self.frame.clipboard_clear()
        self.frame.clipboard_append(self._report_text)
        messagebox.showinfo("Copié ✓", "Rapport copié dans le presse-papiers.")

    # ── Card rendering ───────────────────────────────────────────────────────

    def _on_mousewheel(self, event):
        """@brief Gestionnaire unique de molette, enregistré sur _results_view pour tous les enfants.

        @param event Événement Tk de molette (porte le delta).
        """
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _render_cards(self, results: list, unclassified: list):
        """@brief Affiche les cartes de circuits, regroupées par catégorie, plus les sections annexes.

        @param results Circuits détectés (sortie de analyser()).
        @param unclassified Références non classifiées.
        @return None
        """
        # Clear old cards
        for w in self._results_view.winfo_children():
            w.destroy()

        self._empty_state.grid_remove()

        self._render_executive_summary(results, unclassified)
        self._render_group_preview(results)

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
                card = _CircuitCard(grid, item, self._comp_info, graph=self._graph)
                card.grid(row=i // 2, column=i % 2,
                          sticky="ew", padx=4, pady=4)

        # Unclassified section
        self._render_unclassified(unclassified)

        # DRC violations section
        self._render_drc(self._drc_violations)

    def _render_executive_summary(self, results: list, unclassified: list):
        """@brief Affiche le résumé exécutif en tête des résultats.

        @param results Circuits détectés (sortie de analyser()).
        @param unclassified Références non classifiées.
        @return None
        """
        classified = {ref for r in results for ref in r.get("components", [])}
        summary = _build_executive_summary(
            results,
            total=len(self._comps),
            classified_count=len(classified),
            unclassified=unclassified,
        )

        card = ctk.CTkFrame(self._results_view,
                            fg_color=CARD,
                            corner_radius=8,
                            border_width=1,
                            border_color=BORDER)
        card.pack(fill="x", padx=16, pady=(14, 8))

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(header, text="Résumé exécutif",
                     font=ctk.CTkFont("Segoe UI", 15, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkLabel(header, text="Vue rapide pour la présentation",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).pack(side="left", padx=12)

        lines = (
            ("Analyse", summary["headline"], BLUE),
            ("Classification", summary["classification"], "#10b981"),
            ("Lecture rapide", summary["reading"], TEXT),
            ("À vérifier", summary["review"], "#f59e0b"),
        )
        for label, value, color in lines:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(0, 8))
            ctk.CTkLabel(row, text=label,
                         font=ctk.CTkFont("Segoe UI", 10, "bold"),
                         text_color=color,
                         width=110,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value,
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color=TEXT,
                         anchor="w",
                         justify="left",
                         wraplength=760).pack(side="left", fill="x", expand=True)

    def _render_group_preview(self, results: list):
        """@brief Affiche un apercu compact des groupes detectes.

        @param results Circuits detectes.
        @return None
        """
        groups = _build_group_preview(results)
        if not groups:
            return

        hdr = ctk.CTkFrame(self._results_view, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 2))
        ctk.CTkLabel(hdr, text="APERCU DES GROUPES",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=BLUE).pack(side="left")
        ctk.CTkFrame(hdr, height=1, fg_color=BORDER).pack(
            side="left", fill="x", expand=True, padx=10)

        grid = ctk.CTkFrame(self._results_view, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=(2, 8))
        grid.grid_columnconfigure((0, 1, 2), weight=1)
        for i, group in enumerate(groups):
            bg, fg, icon = _type_style(group["title"])
            card = ctk.CTkFrame(grid, fg_color=bg, corner_radius=8,
                                border_width=1, border_color=_darken(bg))
            card.grid(row=i // 3, column=i % 3, sticky="ew", padx=4, pady=4)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(top, text=icon,
                         font=ctk.CTkFont(size=14),
                         text_color=fg).pack(side="left", padx=(0, 5))
            ctk.CTkLabel(top, text=group["title"],
                         font=ctk.CTkFont("Segoe UI", 10, "bold"),
                         text_color=fg,
                         wraplength=190,
                         justify="left").pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(top, text=group["confidence"],
                         font=ctk.CTkFont("Segoe UI", 9, "bold"),
                         text_color=fg).pack(side="right")

            ctk.CTkLabel(card, text="  ".join(group["refs"]),
                         font=ctk.CTkFont("Consolas", 10, "bold"),
                         text_color=TEXT,
                         wraplength=250,
                         justify="left",
                         anchor="w").pack(fill="x", padx=10, pady=(2, 8))

    def _render_islands(self, results):
        """@brief Affiche le panneau repliable « Structure en étages » (îlots fonctionnels).

        @param results Résultats d'analyse (avec attribut .ilots).
        @return None
        """
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
            _IslandSection(
                self._results_view,
                ilot,
                results,
                self._graph,
                self._comp_info,
                self.frame,
            ).pack(
                fill="x", padx=16, pady=3)

    def _render_unclassified(self, unclassified: list):
        """@brief Affiche la section des composants non classifiés.

        @param unclassified Références non classifiées.
        @return None
        """
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
            if len(unclassified) >= 2:
                ctk.CTkButton(
                    uc_card,
                    text="✨  Suggérer un pattern",
                    width=200, height=32, corner_radius=8,
                    font=ctk.CTkFont("Segoe UI", 11),
                    fg_color="#1e3a5f", hover_color="#1e4a7f",
                    border_width=1, border_color="#3b82f6",
                    command=self._ouvrir_wizard_pattern
                ).pack(anchor="w", padx=14, pady=(4, 10))

    def _render_drc(self, violations: list):
        """@brief Affiche la section DRC (règles de conception).

        @param violations Liste de violations {'rule', 'severity', 'message', 'refs'}.
        @return None
        """
        if not violations:
            return

        hdr = ctk.CTkFrame(self._results_view, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(16, 2))
        ctk.CTkLabel(hdr, text="RÈGLES DE CONCEPTION",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color="#f97316").pack(side="left")
        ctk.CTkFrame(hdr, height=1, fg_color="#7c2d12").pack(
            side="left", fill="x", expand=True, padx=10)

        for v in violations:
            is_warn = v.get("severity") == "warning"
            bg      = "#1c0f06" if is_warn else "#06101c"
            border  = "#7c2d12" if is_warn else "#1e3a5f"
            badge   = "#f97316" if is_warn else "#60a5fa"
            label   = "⚠ AVERTISSEMENT" if is_warn else "ℹ INFO"

            card = ctk.CTkFrame(self._results_view,
                                fg_color=bg,
                                corner_radius=10,
                                border_width=1,
                                border_color=border)
            card.pack(fill="x", padx=16, pady=3)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(8, 2))
            ctk.CTkLabel(top, text=label,
                         font=ctk.CTkFont("Segoe UI", 9, "bold"),
                         text_color=badge).pack(side="left")
            ctk.CTkLabel(top, text=v.get("rule", ""),
                         font=ctk.CTkFont("Segoe UI", 10, "bold"),
                         text_color="#e2e8f0").pack(side="left", padx=8)

            ctk.CTkLabel(card, text=v.get("message", ""),
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color="#94a3b8",
                         wraplength=640,
                         justify="left").pack(
                             anchor="w", padx=12, pady=(2, 8))

    def _open_network_viewer(self):
        """@brief Ouvre la fenêtre de visualisation du réseau de composants."""
        if self._graph is None:
            return
        from gui.network_viewer import NetworkGraphViewer
        NetworkGraphViewer(self._graph, self._results)

    def _open_impedance(self):
        """@brief Ouvre le calcul d'impédance équivalente (réseau d'impédances pures)."""
        if self._graph is None:
            return
        from gui.impedance_view import show_impedance_equivalent
        show_impedance_equivalent(self._graph, self.frame)

    def _on_pattern_created(self):
        """@brief Callback appelé après création d'un pattern depuis le wizard."""
        from tkinter import messagebox
        if self._on_pattern_created_cb:
            self._on_pattern_created_cb()
        messagebox.showinfo("Pattern créé ✓",
            "Le pattern a été sauvegardé et ajouté à l'onglet « Circuits ».\n"
            "Il sera actif à la prochaine analyse.")

    def _ouvrir_wizard_pattern(self):
        """@brief Ouvre le wizard de suggestion de pattern pour les composants non classifiés."""
        if not self._unclassified or self._graph is None:
            return
        from gui.pattern_wizard import PatternWizard
        PatternWizard(
            self.frame,
            self._graph,
            self._unclassified,
            self._comp_info,
            on_created=self._on_pattern_created,
        )


# ── Helper widgets ────────────────────────────────────────────────────────────

class _StatCard(ctk.CTkFrame):
    """@brief Carte de statistique (icône, valeur, libellé) de la barre de résultats."""

    def __init__(self, parent, value, label, color, icon):
        """@brief Construit la carte de statistique.

        @param parent Widget parent.
        @param value Valeur initiale affichée.
        @param label Libellé sous la valeur.
        @param color Couleur d'accent.
        @param icon Icône affichée.
        """
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
        """@brief Met à jour la valeur affichée.

        @param value Nouvelle valeur (chaîne).
        @return None
        """
        self._val.configure(text=value)


class _EmptyState(ctk.CTkFrame):
    """@brief Écran d'accueil affiché tant qu'aucun circuit n'a été chargé."""

    def __init__(self, parent):
        """@brief Construit l'écran vide.

        @param parent Widget parent.
        """
        super().__init__(parent, fg_color="transparent")
        ctk.CTkLabel(self, text="📂",
                     font=ctk.CTkFont(size=56),
                     text_color="#1e293b").pack(pady=(60, 8))
        ctk.CTkLabel(self, text="Aucun circuit chargé",
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color="#334155").pack()
        ctk.CTkLabel(self,
                     text="Cliquez sur Parcourir pour charger\nun fichier netlist .txt / .cir / .sp / .net / .xml",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color=MUTED, justify="center").pack(pady=8)


class _IslandSection(ctk.CTkFrame):
    """@brief Section repliable pour un îlot fonctionnel (structure en étages)."""

    def __init__(self, parent, ilot: dict, results,
                 graph=None, comp_info: dict = None, viewer_parent=None):
        """@brief Construit la section d'un îlot.

        @param parent Widget parent.
        @param ilot Dict décrivant l'îlot (label, composants, circuits).
        @param results Résultats d'analyse (pour résoudre les circuits par indice).
        """
        super().__init__(parent, corner_radius=10,
                         fg_color=CARD,
                         border_width=1, border_color=BORDER)
        self._ouvert = True
        self._ilot = ilot
        self._results = results
        self._graph = graph
        self._comp_info = comp_info or {}
        self._viewer_parent = viewer_parent

        nb = len(ilot['composants'])
        titre = f"{ilot['label']}  ({nb} composant{'s' if nb > 1 else ''})"
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=6, pady=(4, 0))
        self._btn = ctk.CTkButton(
            header, text=f"▼  {titre}",
            anchor="w", height=32, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            fg_color="transparent", hover_color=CARD2,
            text_color=TEXT,
            command=self._toggle,
        )
        self._btn.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            header,
            text="Schema ilot",
            width=105,
            height=28,
            corner_radius=7,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            fg_color="#1e293b",
            hover_color="#263347",
            border_width=1,
            border_color=BORDER,
            command=self._open_island_schema,
        ).pack(side="right", padx=(8, 0))
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
        """@brief Replie ou déplie le contenu de la section."""
        self._ouvert = not self._ouvert
        if self._ouvert:
            self._contenu.pack(fill="x", padx=20, pady=(0, 8))
            self._btn.configure(text=f"▼  {self._titre}")
        else:
            self._contenu.pack_forget()
            self._btn.configure(text=f"▶  {self._titre}")

    def _open_island_schema(self):
        """@brief Ouvre le schema reel de l'ilot."""
        if self._graph is None:
            return
        from gui.circuit_viewer import show_island
        show_island(
            self._ilot,
            self._graph,
            self._comp_info,
            self._viewer_parent,
            results=self._results,
        )


class _CircuitCard(ctk.CTkFrame):
    """@brief Carte d'un circuit détecté (type, composants, nœuds, ouverture du schéma)."""

    def __init__(self, parent, result: dict, comp_info: dict = None, graph=None):
        """@brief Construit la carte d'un circuit.

        @param parent Widget parent.
        @param result Match du circuit détecté.
        @param comp_info Dict {ref -> infos composant} pour le rendu du schéma.
        @param graph Graphe du circuit (pour le clic drill-down sur les boîtes Z).
        """
        bg, fg, icon = _type_style(result["circuit_type"])
        super().__init__(parent, corner_radius=12,
                         fg_color=bg,
                         border_width=1,
                         border_color=_darken(bg))
        self._result = result
        self._comp_info = comp_info or {}
        self._graph = graph

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
        """@brief Ouvre la fenêtre de schéma du circuit de cette carte."""
        from gui.circuit_viewer import show_circuit
        show_circuit(self._result, self._comp_info, graph=self._graph)


# ── Utilities ────────────────────────────────────────────────────────────────

def _category(name: str) -> str:
    """@brief Catégorie d'affichage (en-tête de section) d'un type de circuit.

    @param name Nom du circuit détecté.
    @return str Libellé de catégorie.
    """
    lower = name.lower()
    if "aop" in lower:           return "AMPLIFICATEURS OPÉRATIONNELS"
    if any(x in lower for x in ("transistor", "mosfet", "miroir", "relais")):
        return "TRANSISTORS & COMMUTATION"
    if any(x in lower for x in ("pont", "redresseur", "crête", "roue")):
        return "REDRESSEURS & DIODES"
    if any(x in lower for x in ("filtre", "condensateur", "absorbeur", "lc", "rc")):
        return "FILTRES & PASSIFS"
    if any(x in lower for x in ("diviseur", "fusible", "protection", "esd")):
        return "PROTECTION & AUTRES"
    return "AUTRES"


def _build_executive_summary(results: list, total: int,
                             classified_count: int, unclassified: list) -> dict:
    """@brief Construit les textes du résumé exécutif après analyse.

    @param results Circuits détectés.
    @param total Nombre total de composants analysés.
    @param classified_count Nombre de composants rattachés à un circuit détecté.
    @param unclassified Références non classifiées.
    @return dict Textes prêts à afficher dans le bloc résumé.
    """
    nb_circuits = len(results)
    if nb_circuits == 0:
        headline = (
            f"Analyse terminée : {total} composant{_s(total)} analysé{_s(total)}, "
            "aucun circuit reconnu."
        )
        reading = "Le schéma ne correspond pas encore aux patterns intégrés."
    else:
        headline = (
            f"Analyse terminée : {total} composant{_s(total)} analysé{_s(total)}, "
            f"{nb_circuits} circuit{_s(nb_circuits)} reconnu{_s(nb_circuits)}."
        )
        categories = _format_category_list(results)
        reading = f"Le schéma contient principalement {categories}."

    pct = int(100 * classified_count / total) if total else 0
    classification = (
        f"{classified_count} composant{_s(classified_count)} "
        f"classé{_s(classified_count)} ({pct}%)."
    )

    review_points = _count_review_points(results, unclassified)
    if review_points == 0:
        review = "Aucun point bloquant identifié pour cette première lecture."
    elif nb_circuits == 0 and review_points == len(unclassified):
        review = f"{review_points} composant{_s(review_points)} restent non classifiés."
    else:
        review = (
            f"{review_points} point{_s(review_points)} nécessitent "
            "une vérification ingénieur."
        )

    return {
        "headline": headline,
        "classification": classification,
        "reading": reading,
        "review": review,
    }


def _find_demo_file(root=None) -> str:
    """@brief Choisit un fichier de demo au hasard dans circuits_industriels/.

    @param root Racine du projet (optionnelle, pour les tests).
    @return str Chemin du fichier choisi, ou chaine vide.
    """
    import random as _random
    if root is not None:
        base = Path(root)
    else:
        from circuit_analyzer.chemins import racine_application
        base = racine_application()
    dossier = base / "circuits_industriels"
    fichiers = sorted(dossier.glob("*.xml")) if dossier.exists() else []
    if fichiers:
        return str(_random.choice(fichiers))
    fallback = base / "exemples" / "test_circuit_complet.txt"
    return str(fallback) if fallback.exists() else ""


def _build_group_preview(results: list, limit: int = 9) -> list:
    """@brief Construit les donnees d'affichage de l'apercu des groupes.

    @param results Circuits detectes.
    @param limit Nombre maximum de groupes affiches.
    @return list[dict] Groupes synthetiques pour la GUI.
    """
    preview = []
    for result in results[:limit]:
        refs = list(result.get("components", []))
        refs += [
            sat["ref"]
            for sat in result.get("satellites", [])
            if sat.get("status") == "sure" and sat.get("ref") not in refs
        ]
        confidence = result.get("confidence")
        confidence_text = "" if confidence is None else f"{int(round(confidence * 100))}%"
        title = result.get("circuit_type", "Circuit detecte")
        preview.append({
            "title": title,
            "category": _category(title),
            "refs": refs,
            "confidence": confidence_text,
        })
    return preview


def _format_category_list(results: list) -> str:
    """@brief Résume les catégories fonctionnelles dominantes des circuits.

    @param results Circuits détectés.
    @return str Liste courte de catégories en français courant.
    """
    labels = []
    for result in results:
        category = _category(result.get("circuit_type", ""))
        if "COMMUTATION" in category:
            label = "de la commutation"
        elif "PROTECTION" in category or "DIODES" in category:
            label = "de la protection"
        elif "FILTRES" in category:
            label = "du filtrage"
        elif "OPÉRATIONNELS" in category:
            label = "de l'amplification"
        else:
            label = "des fonctions annexes"
        if label not in labels:
            labels.append(label)
    return _join_fr(labels[:3]) if labels else "des fonctions non classifiées"


def _count_review_points(results: list, unclassified: list) -> int:
    """@brief Compte les éléments à signaler comme points de vérification.

    @param results Circuits détectés.
    @param unclassified Références non classifiées.
    @return int Nombre de points à vérifier.
    """
    total = len(unclassified)
    for result in results:
        total += len(result.get("warnings", []))
        total += sum(1 for sat in result.get("satellites", [])
                     if sat.get("status") == "possible")
    return total


def _join_fr(items: list) -> str:
    """@brief Joint une liste courte avec des virgules et un dernier 'et'.

    @param items Éléments textuels à joindre.
    @return str Phrase jointe.
    """
    if len(items) <= 1:
        return items[0] if items else ""
    if len(items) == 2:
        return f"{items[0]} et {items[1]}"
    return f"{', '.join(items[:-1])} et {items[-1]}"


def _s(count: int) -> str:
    """@brief Suffixe pluriel français minimal.

    @param count Quantité à tester.
    @return str 's' si count > 1, sinon chaîne vide.
    """
    return "s" if count > 1 else ""


def _darken(hex_color: str) -> str:
    """@brief Assombrit une couleur hexadécimale.

    @param hex_color Couleur au format '#rrggbb'.
    @return str Couleur assombrie '#rrggbb'.
    """
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    r, g, b = max(0, r - 20), max(0, g - 20), max(0, b - 20)
    return f"#{r:02x}{g:02x}{b:02x}"


def _brighten(hex_color: str) -> str:
    """@brief Éclaircit une couleur hexadécimale.

    @param hex_color Couleur au format '#rrggbb'.
    @return str Couleur éclaircie '#rrggbb'.
    """
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    r, g, b = min(255, r + 60), min(255, g + 60), min(255, b + 60)
    return f"#{r:02x}{g:02x}{b:02x}"


def _chunks(lst, n):
    """@brief Découpe une liste en tranches successives de n éléments.

    @param lst Liste à découper.
    @param n Taille de chaque tranche.
    @return generator Tranches successives (listes).
    """
    for i in range(0, len(lst), n):
        yield lst[i:i + n]
