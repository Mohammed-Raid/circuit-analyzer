import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from circuit_analyzer.component_library.loader import load_library
from circuit_analyzer.patterns.basic_circuits import ALL_PATTERNS as BASIC_PATTERNS
from circuit_analyzer.patterns.transistor import TRANSISTOR_PATTERNS
from circuit_analyzer.patterns.opamp import OPAMP_PATTERNS
from custom_circuits.loader import (
    load_custom_circuits, save_custom_circuits, CONDITION_LABELS
)

BG     = "#070d1a"
CARD   = "#1e293b"
CARD2  = "#0f172a"
BORDER = "#263347"
TEXT   = "#f1f5f9"
MUTED  = "#64748b"
BLUE   = "#3b82f6"
BLUE_D = "#1d4ed8"

_BASE_NAMES = [p.name for p in BASIC_PATTERNS + TRANSISTOR_PATTERNS + OPAMP_PATTERNS]


class TabCircuits:
    def __init__(self, parent):
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color=BG)
        self._custom = []
        self._current_idx = None
        self._comp_vars: dict[str, tk.BooleanVar] = {}
        self._cond_vars:  dict[str, tk.BooleanVar] = {}
        self._build()
        self._load()

    def _build(self):
        # ── Page header
        header = ctk.CTkFrame(self.frame, fg_color=CARD,
                              corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        h = ctk.CTkFrame(header, fg_color="transparent")
        h.pack(fill="both", expand=True, padx=28)
        ctk.CTkLabel(h, text="Circuits reconnus",
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color=TEXT).pack(side="left", pady=18)
        ctk.CTkLabel(h, text="Gérer les patterns personnalisés",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=MUTED).pack(side="left", padx=14)

        # ── Body
        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # ── Left: list panel
        left = ctk.CTkFrame(body, corner_radius=14, fg_color=CARD,
                            border_width=1, border_color=BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.grid_rowconfigure(1, weight=1)

        lhdr = ctk.CTkFrame(left, fg_color="transparent")
        lhdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        ctk.CTkLabel(lhdr, text="Liste des circuits",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=TEXT).pack(side="left")

        # Listbox in dark frame
        lb_f = ctk.CTkFrame(left, fg_color=CARD2, corner_radius=8)
        lb_f.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self._listbox = tk.Listbox(
            lb_f, width=34, height=24,
            bg=CARD2, fg=MUTED,
            selectbackground=BLUE_D, selectforeground=TEXT,
            font=("Segoe UI", 11), relief="flat", bd=0,
            activestyle="none", highlightthickness=0,
        )
        sb = tk.Scrollbar(lb_f, command=self._listbox.yview,
                          bg=CARD, troughcolor=CARD2)
        self._listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._listbox.pack(fill="both", expand=True, padx=6, pady=6)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        # Buttons
        br = ctk.CTkFrame(left, fg_color="transparent")
        br.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 12))
        ctk.CTkButton(br, text="＋  Nouveau", height=36,
                      corner_radius=8, font=ctk.CTkFont("Segoe UI", 12),
                      fg_color=BLUE_D, hover_color=BLUE,
                      command=self._new).pack(
                          side="left", expand=True, padx=(0, 4))
        ctk.CTkButton(br, text="🗑  Supprimer", height=36,
                      corner_radius=8, font=ctk.CTkFont("Segoe UI", 12),
                      fg_color="#7f1d1d", hover_color="#991b1b",
                      command=self._delete).pack(
                          side="left", expand=True)

        # ── Right: form panel
        right = ctk.CTkFrame(body, corner_radius=14, fg_color=CARD,
                             border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        # Form header
        fhdr = ctk.CTkFrame(right, fg_color=CARD2, corner_radius=0,
                            height=50)
        fhdr.grid(row=0, column=0, sticky="ew")
        fhdr.grid_propagate(False)
        ctk.CTkLabel(fhdr,
                     text="Définir un nouveau circuit personnalisé",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=TEXT).pack(side="left", padx=18, pady=12)

        # Name row
        name_row = ctk.CTkFrame(right, fg_color="transparent")
        name_row.grid(row=1, column=0, sticky="ew", padx=18, pady=(14, 10))
        ctk.CTkLabel(name_row, text="Nom du circuit",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).pack(anchor="w")
        self._name_var = tk.StringVar()
        ctk.CTkEntry(name_row,
                     textvariable=self._name_var,
                     height=40, corner_radius=8,
                     font=ctk.CTkFont("Segoe UI", 13),
                     fg_color=CARD2, border_color=BORDER,
                     text_color=TEXT,
                     placeholder_text="Ex: Filtre RLC série").pack(
                         fill="x", pady=(4, 0))

        # Two columns: components | conditions
        cols = ctk.CTkFrame(right, fg_color="transparent")
        cols.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 10))
        cols.grid_columnconfigure((0, 1), weight=1)
        cols.grid_rowconfigure(0, weight=1)

        # Components column
        comp_col = ctk.CTkFrame(cols, corner_radius=10,
                                fg_color=CARD2,
                                border_width=1, border_color=BORDER)
        comp_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(comp_col, text="⚙  Composants requis",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=BLUE).pack(
                         anchor="w", padx=12, pady=(10, 6))
        self._comp_scroll = ctk.CTkScrollableFrame(
            comp_col, fg_color="transparent")
        self._comp_scroll.pack(fill="both", expand=True,
                               padx=6, pady=(0, 8))

        # Conditions column
        cond_col = ctk.CTkFrame(cols, corner_radius=10,
                                fg_color=CARD2,
                                border_width=1, border_color=BORDER)
        cond_col.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(cond_col, text="✅  Conditions",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color="#10b981").pack(
                         anchor="w", padx=12, pady=(10, 6))
        for label in CONDITION_LABELS:
            var = tk.BooleanVar()
            self._cond_vars[label] = var
            ctk.CTkCheckBox(
                cond_col, text=label, variable=var,
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=TEXT,
                fg_color=BLUE_D, hover_color=BLUE,
                checkmark_color=TEXT,
            ).pack(anchor="w", padx=12, pady=4)

        # Save button
        ctk.CTkButton(right, text="💾  Sauvegarder ce circuit",
                      height=42, corner_radius=10,
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      fg_color="#15803d", hover_color="#16a34a",
                      command=self._save).grid(
                          row=3, column=0, sticky="ew",
                          padx=18, pady=(0, 16))

    # ── Data ─────────────────────────────────────────────────────────────────

    def _build_comp_checkboxes(self):
        for w in self._comp_scroll.winfo_children():
            w.destroy()
        self._comp_vars = {}
        for key, val in load_library().items():
            var = tk.BooleanVar()
            self._comp_vars[key] = var
            ctk.CTkCheckBox(
                self._comp_scroll,
                text=f"{key}  —  {val['name']}",
                variable=var,
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=TEXT,
                fg_color=BLUE_D, hover_color=BLUE,
                checkmark_color=TEXT,
            ).pack(anchor="w", padx=4, pady=3)

    def refresh_component_list(self):
        self._build_comp_checkboxes()

    def _load(self):
        self._build_comp_checkboxes()
        self._listbox.delete(0, "end")
        for name in _BASE_NAMES:
            self._listbox.insert("end", f"  {name}")
        for i in range(len(_BASE_NAMES)):
            self._listbox.itemconfig(i, foreground="#374151")
        self._custom = load_custom_circuits()
        for c in self._custom:
            self._listbox.insert("end", f"  ★  {c['name']}")
            self._listbox.itemconfig(
                self._listbox.size() - 1, foreground="#60a5fa")

    def _on_select(self, _=None):
        sel = self._listbox.curselection()
        if not sel or sel[0] < len(_BASE_NAMES):
            return
        self._current_idx = sel[0] - len(_BASE_NAMES)
        c = self._custom[self._current_idx]
        self._name_var.set(c["name"])
        sel_c = set(c.get("components", []))
        for k, v in self._comp_vars.items():
            v.set(k in sel_c)
        for l, v in self._cond_vars.items():
            v.set(l in c.get("conditions", []))

    def _new(self):
        self._current_idx = None
        self._name_var.set("")
        for v in self._comp_vars.values():
            v.set(False)
        for v in self._cond_vars.values():
            v.set(False)

    def _delete(self):
        if self._current_idx is None:
            messagebox.showinfo("Info",
                "Sélectionnez un circuit personnalisé.")
            return
        name = self._custom[self._current_idx]["name"]
        if messagebox.askyesno("Confirmer", f"Supprimer '{name}' ?"):
            self._custom.pop(self._current_idx)
            save_custom_circuits(self._custom)
            self._current_idx = None
            self._load()

    def _save(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showerror("Erreur", "Nom obligatoire.")
            return
        comps = [k for k, v in self._comp_vars.items() if v.get()]
        if not comps:
            messagebox.showerror("Erreur",
                "Sélectionnez au moins un composant.")
            return
        conds = [k for k, v in self._cond_vars.items() if v.get()]
        c = {"name": name, "components": comps, "conditions": conds}
        if self._current_idx is not None:
            self._custom[self._current_idx] = c
        else:
            self._custom.append(c)
            self._current_idx = len(self._custom) - 1
        save_custom_circuits(self._custom)
        self._load()
        messagebox.showinfo("Succès", f"'{name}' sauvegardé.")
