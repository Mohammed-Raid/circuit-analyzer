import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox
from circuit_analyzer.parser import parse_file
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.reporter import generate

# Report colour tags (applied to the embedded tk.Text widget)
TAGS = {
    "section_header": {"foreground": "#f1f5f9",  "font": ("Consolas", 11, "bold")},
    "separator":      {"foreground": "#334155",   "font": ("Consolas", 9)},
    "meta_key":       {"foreground": "#64748b",   "font": ("Consolas", 10)},
    "meta_val":       {"foreground": "#e2e8f0",   "font": ("Consolas", 10, "bold")},
    "circuit_num":    {"foreground": "#60a5fa",   "font": ("Consolas", 11, "bold")},
    "circuit_name":   {"foreground": "#93c5fd",   "font": ("Consolas", 11, "bold")},
    "label":          {"foreground": "#475569",   "font": ("Consolas", 10)},
    "comp_ref":       {"foreground": "#34d399",   "font": ("Consolas", 10, "bold")},
    "node_ref":       {"foreground": "#c084fc",   "font": ("Consolas", 10)},
    "unc_header":     {"foreground": "#f87171",   "font": ("Consolas", 10, "bold")},
    "unc_ref":        {"foreground": "#fca5a5",   "font": ("Consolas", 10)},
}


class TabAnalyze:
    def __init__(self, parent):
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color="#0f172a")
        self._file_path = tk.StringVar()
        self._report_content = ""
        self._build()

    def _build(self):
        # ── Page title
        title_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        title_row.pack(fill="x", padx=28, pady=(24, 4))
        ctk.CTkLabel(title_row,
                     text="Analyser un circuit",
                     font=ctk.CTkFont("Segoe UI", 20, "bold"),
                     text_color="#f1f5f9").pack(side="left")

        # ── File picker card
        card = ctk.CTkFrame(self.frame, corner_radius=14,
                            fg_color="#1e293b")
        card.pack(fill="x", padx=28, pady=(8, 0))

        ctk.CTkLabel(card, text="Fichier netlist",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color="#94a3b8").pack(anchor="w", padx=18, pady=(14, 4))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 14))

        self._entry = ctk.CTkEntry(
            row,
            textvariable=self._file_path,
            placeholder_text="Choisir un fichier .txt …",
            height=40,
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color="#0f172a",
            border_color="#334155",
            text_color="#e2e8f0",
        )
        self._entry.pack(side="left", expand=True, fill="x", padx=(0, 10))
        self._entry.bind("<Double-Button-1>", lambda _: self._browse())

        ctk.CTkButton(row, text="Parcourir", width=110, height=40,
                      corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color="#1d4ed8", hover_color="#2563eb",
                      command=self._browse).pack(side="left", padx=(0, 8))

        ctk.CTkButton(row, text="▶  Analyser", width=130, height=40,
                      corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 12, "bold"),
                      fg_color="#059669", hover_color="#10b981",
                      command=self._analyze).pack(side="left")

        # ── Stats bar (hidden until first run)
        self._stats_card = ctk.CTkFrame(self.frame, corner_radius=14,
                                        fg_color="#1e293b")
        self._s_total  = self._make_stat(self._stats_card, "—", "Composants")
        self._s_groups = self._make_stat(self._stats_card, "—", "Groupes identifiés")
        self._s_pct    = self._make_stat(self._stats_card, "—", "Classifiés")
        # hidden initially — shown after first analysis

        # ── Report area
        report_card = ctk.CTkFrame(self.frame, corner_radius=14,
                                   fg_color="#1e293b")
        report_card.pack(fill="both", expand=True, padx=28, pady=(10, 0))

        hdr = ctk.CTkFrame(report_card, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(hdr, text="Rapport",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color="#94a3b8").pack(side="left")

        # Embed a standard tk.Text for tag-based coloring
        text_frame = ctk.CTkFrame(report_card, fg_color="#0a0f1e",
                                  corner_radius=10)
        text_frame.pack(fill="both", expand=True, padx=14, pady=(6, 0))

        self._text = tk.Text(
            text_frame,
            state="disabled", wrap="none",
            font=("Consolas", 11),
            bg="#0a0f1e", fg="#e2e8f0",
            relief="flat", bd=0,
            selectbackground="#1d4ed8",
            insertbackground="#60a5fa",
            padx=14, pady=10,
            cursor="arrow",
        )
        sb_y = tk.Scrollbar(text_frame, orient="vertical",
                            command=self._text.yview,
                            bg="#1e293b", troughcolor="#0a0f1e")
        sb_x = tk.Scrollbar(text_frame, orient="horizontal",
                            command=self._text.xview,
                            bg="#1e293b", troughcolor="#0a0f1e")
        self._text.configure(yscrollcommand=sb_y.set,
                             xscrollcommand=sb_x.set)
        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        self._text.pack(fill="both", expand=True)
        self._setup_tags()

        # ── Bottom buttons
        btns = ctk.CTkFrame(self.frame, fg_color="transparent")
        btns.pack(fill="x", padx=28, pady=12)

        ctk.CTkButton(btns, text="💾  Sauvegarder",
                      width=150, height=36, corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color="#334155", hover_color="#475569",
                      command=self._save).pack(side="left", padx=(0, 8))

        ctk.CTkButton(btns, text="📋  Copier",
                      width=110, height=36, corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color="#334155", hover_color="#475569",
                      command=self._copy).pack(side="left")

    def _make_stat(self, parent, value, label):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(side="left", expand=True, padx=20, pady=14)
        val = ctk.CTkLabel(f, text=value,
                           font=ctk.CTkFont("Segoe UI", 28, "bold"),
                           text_color="#60a5fa")
        val.pack()
        ctk.CTkLabel(f, text=label,
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color="#64748b").pack()
        return val

    def _setup_tags(self):
        for name, cfg in TAGS.items():
            self._text.tag_configure(name, **cfg)

    # ── Actions ─────────────────────────────────────────────────────────────

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Choisir un fichier netlist",
            filetypes=[("Fichiers texte", "*.txt"), ("Tous", "*.*")],
        )
        if path:
            self._file_path.set(path)

    def _analyze(self):
        path = self._file_path.get().strip()
        if not path:
            self._show_error("Veuillez sélectionner un fichier circuit.")
            return
        try:
            comps    = parse_file(path)
            graph    = build_graph(comps)
            results  = match_patterns(graph)
            all_refs = [c.ref for c in comps]
            report   = generate(results, path, len(comps), all_refs=all_refs)
            self._report_content = report

            total      = len(comps)
            groups     = len(results)
            classified = sum(len(r["components"]) for r in results)
            pct        = int(100 * classified / total) if total else 0

            self._s_total.configure(text=str(total))
            self._s_groups.configure(text=str(groups))
            pct_color = ("#34d399" if pct >= 80
                         else "#fbbf24" if pct >= 60
                         else "#f87171")
            self._s_pct.configure(text=f"{pct}%", text_color=pct_color)
            self._stats_card.pack(fill="x", padx=28, pady=(10, 0),
                                  before=self._text.master.master)
            self._render(report)

        except FileNotFoundError:
            self._show_error(f"Fichier introuvable :\n{path}")
        except ValueError as e:
            self._show_error(f"Erreur netlist :\n{e}")
        except Exception as e:
            self._show_error(f"Erreur :\n{e}")

    def _save(self):
        if not self._report_content:
            messagebox.showinfo("Info", "Aucun rapport à sauvegarder.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texte", "*.txt")],
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._report_content)
            messagebox.showinfo("Succès", f"Sauvegardé :\n{path}")

    def _copy(self):
        if not self._report_content:
            return
        self.frame.clipboard_clear()
        self.frame.clipboard_append(self._report_content)

    # ── Rendering ───────────────────────────────────────────────────────────

    def _show_error(self, msg):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", msg, "unc_header")
        self._text.configure(state="disabled")

    def _ins(self, text, tag=""):
        self._text.insert("end", text, tag or ())

    def _render(self, text: str):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        in_unc = False
        for line in text.splitlines():
            if line.startswith("==="):
                self._ins(line + "\n", "section_header"); in_unc = False
            elif set(line.strip()) == {"-"} and len(line.strip()) > 4:
                self._ins(line + "\n", "separator")
            elif line.strip() and line.strip()[0] == "[":
                i = line.index("]") + 1
                self._ins(line[:i], "circuit_num")
                self._ins(line[i:] + "\n", "circuit_name")
                in_unc = False
            elif "    Composants :" in line:
                pos = line.index(":") + 1
                self._ins(line[:pos], "label")
                for j, part in enumerate(line[pos:].split(",")):
                    r = part.strip()
                    if r:
                        self._ins(" " + r, "comp_ref")
                        if j < len(line[pos:].split(",")) - 1:
                            self._ins(",", "label")
                self._ins("\n")
            elif "    Nœuds" in line:
                pos = line.index(":") + 1
                self._ins(line[:pos], "label")
                self._ins(line[pos:] + "\n", "node_ref")
            elif any(k in line for k in ("Fichier", "Composants totaux", "Groupes identifiés")):
                if ":" in line:
                    pos = line.index(":") + 1
                    self._ins(line[:pos], "meta_key")
                    self._ins(line[pos:] + "\n", "meta_val")
                else:
                    self._ins(line + "\n")
            elif "non classifiés" in line:
                self._ins(line + "\n", "unc_header"); in_unc = True
            elif in_unc and line.startswith("    "):
                self._ins(line + "\n", "unc_ref")
            else:
                self._ins(line + "\n")
        self._text.configure(state="disabled")
        self._text.see("1.0")
