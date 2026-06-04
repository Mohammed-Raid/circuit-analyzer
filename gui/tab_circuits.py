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

_BASE_PATTERN_NAMES = [p.name for p in BASIC_PATTERNS + TRANSISTOR_PATTERNS + OPAMP_PATTERNS]


class TabCircuits:
    def __init__(self, parent):
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color="#0f172a")
        self._custom = []
        self._current_idx = None
        self._comp_vars: dict[str, tk.BooleanVar] = {}
        self._cond_vars: dict[str, tk.BooleanVar] = {}
        self._build()
        self._load()

    def _build(self):
        # ── Title
        ctk.CTkLabel(self.frame,
                     text="Circuits reconnus",
                     font=ctk.CTkFont("Segoe UI", 20, "bold"),
                     text_color="#f1f5f9").pack(
                         anchor="w", padx=28, pady=(24, 12))

        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28, pady=(0, 16))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # ── Left: list card
        left_card = ctk.CTkFrame(body, corner_radius=14, fg_color="#1e293b")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left_card, text="Liste",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color="#94a3b8").grid(
                         row=0, column=0, sticky="w", padx=14, pady=(12, 4))

        list_frame = ctk.CTkFrame(left_card, fg_color="#0a0f1e",
                                  corner_radius=8)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))

        self._listbox = tk.Listbox(
            list_frame, width=32, height=22,
            bg="#0a0f1e", fg="#94a3b8",
            selectbackground="#1d4ed8", selectforeground="#ffffff",
            font=("Segoe UI", 11), relief="flat", bd=0,
            activestyle="none", highlightthickness=0,
        )
        sb = tk.Scrollbar(list_frame, command=self._listbox.yview,
                          bg="#1e293b", troughcolor="#0a0f1e")
        self._listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._listbox.pack(fill="both", expand=True, padx=6, pady=6)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        # List buttons
        btn_row = ctk.CTkFrame(left_card, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 12))
        ctk.CTkButton(btn_row, text="+ Nouveau", height=34,
                      corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color="#1d4ed8", hover_color="#2563eb",
                      command=self._new).pack(side="left", expand=True,
                                              padx=(0, 4))
        ctk.CTkButton(btn_row, text="Supprimer", height=34,
                      corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color="#7f1d1d", hover_color="#991b1b",
                      command=self._delete).pack(side="left", expand=True)

        # ── Right: form card
        right_card = ctk.CTkFrame(body, corner_radius=14, fg_color="#1e293b")
        right_card.grid(row=0, column=1, sticky="nsew")
        right_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right_card, text="Définir un circuit personnalisé",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color="#94a3b8").pack(
                         anchor="w", padx=18, pady=(14, 10))

        # Name field
        ctk.CTkLabel(right_card, text="Nom du circuit",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color="#64748b").pack(
                         anchor="w", padx=18)
        self._name_var = tk.StringVar()
        ctk.CTkEntry(right_card,
                     textvariable=self._name_var,
                     height=38, corner_radius=8,
                     font=ctk.CTkFont("Segoe UI", 12),
                     fg_color="#0a0f1e", border_color="#334155",
                     text_color="#e2e8f0",
                     placeholder_text="Ex: Filtre RLC série").pack(
                         fill="x", padx=18, pady=(4, 12))

        # Two-column layout for checkboxes
        cols = ctk.CTkFrame(right_card, fg_color="transparent")
        cols.pack(fill="both", expand=True, padx=18)
        cols.grid_columnconfigure((0, 1), weight=1)

        # Components column
        comp_col = ctk.CTkFrame(cols, corner_radius=10,
                                fg_color="#0a0f1e")
        comp_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 10))
        ctk.CTkLabel(comp_col, text="Composants requis",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color="#60a5fa").pack(
                         anchor="w", padx=12, pady=(10, 6))
        self._comp_scroll = ctk.CTkScrollableFrame(
            comp_col, fg_color="transparent", height=180)
        self._comp_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        # Conditions column
        cond_col = ctk.CTkFrame(cols, corner_radius=10,
                                fg_color="#0a0f1e")
        cond_col.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 10))
        ctk.CTkLabel(cond_col, text="Conditions",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color="#60a5fa").pack(
                         anchor="w", padx=12, pady=(10, 6))
        for label in CONDITION_LABELS:
            var = tk.BooleanVar()
            self._cond_vars[label] = var
            ctk.CTkCheckBox(
                cond_col, text=label, variable=var,
                font=ctk.CTkFont("Segoe UI", 11),
                text_color="#e2e8f0",
                fg_color="#1d4ed8", hover_color="#2563eb",
            ).pack(anchor="w", padx=12, pady=3)

        ctk.CTkButton(right_card, text="💾  Sauvegarder le circuit",
                      height=40, corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 12, "bold"),
                      fg_color="#059669", hover_color="#10b981",
                      command=self._save).pack(
                          fill="x", padx=18, pady=(0, 16))

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
                text_color="#e2e8f0",
                fg_color="#1d4ed8", hover_color="#2563eb",
            ).pack(anchor="w", padx=6, pady=2)

    def refresh_component_list(self):
        self._build_comp_checkboxes()

    def _load(self):
        self._build_comp_checkboxes()
        self._listbox.delete(0, "end")
        for name in _BASE_PATTERN_NAMES:
            self._listbox.insert("end", f"  {name}")
        for i in range(len(_BASE_PATTERN_NAMES)):
            self._listbox.itemconfig(i, foreground="#475569")
        self._custom = load_custom_circuits()
        for c in self._custom:
            self._listbox.insert("end", f"  ★  {c['name']}")
            self._listbox.itemconfig(
                self._listbox.size() - 1, foreground="#60a5fa")

    def _on_select(self, _=None):
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(_BASE_PATTERN_NAMES):
            return
        self._current_idx = idx - len(_BASE_PATTERN_NAMES)
        c = self._custom[self._current_idx]
        self._name_var.set(c["name"])
        sel_comps = set(c.get("components", []))
        for k, v in self._comp_vars.items():
            v.set(k in sel_comps)
        for label, v in self._cond_vars.items():
            v.set(label in c.get("conditions", []))

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
                "Sélectionnez un circuit personnalisé à supprimer.")
            return
        name = self._custom[self._current_idx]["name"]
        if messagebox.askyesno("Confirmer",
                               f"Supprimer '{name}' ?"):
            self._custom.pop(self._current_idx)
            save_custom_circuits(self._custom)
            self._current_idx = None
            self._load()

    def _save(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showerror("Erreur", "Le nom est obligatoire.")
            return
        comps = [k for k, v in self._comp_vars.items() if v.get()]
        if not comps:
            messagebox.showerror("Erreur",
                "Sélectionnez au moins un composant.")
            return
        conds = [k for k, v in self._cond_vars.items() if v.get()]
        circuit = {"name": name, "components": comps, "conditions": conds}
        if self._current_idx is not None:
            self._custom[self._current_idx] = circuit
        else:
            self._custom.append(circuit)
            self._current_idx = len(self._custom) - 1
        save_custom_circuits(self._custom)
        self._load()
        messagebox.showinfo("Succès", f"Circuit '{name}' sauvegardé.")
