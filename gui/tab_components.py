import json
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from pathlib import Path
from circuit_analyzer.component_library.base import COMPONENT_TYPES

LIBRARY_FILE = "component_library.json"
BG     = "#070d1a"
CARD   = "#1e293b"
CARD2  = "#0f172a"
BORDER = "#263347"
TEXT   = "#f1f5f9"
MUTED  = "#64748b"
BLUE   = "#3b82f6"
BLUE_D = "#1d4ed8"


class TabComponents:
    def __init__(self, parent, on_save=None):
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color=BG)
        self._on_save = on_save
        self._custom: dict = {}
        self._current_key: str | None = None
        self._pin_entries: list = []
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
        ctk.CTkLabel(h, text="Bibliothèque de composants",
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color=TEXT).pack(side="left", pady=18)
        ctk.CTkLabel(h, text="Ajouter de nouveaux types",
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

        ctk.CTkLabel(left, text="Types de composants",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=TEXT).grid(
                         row=0, column=0, sticky="w",
                         padx=14, pady=(14, 6))

        lb_f = ctk.CTkFrame(left, fg_color=CARD2, corner_radius=8)
        lb_f.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self._listbox = tk.Listbox(
            lb_f, width=30, height=24,
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

        # Form header
        fhdr = ctk.CTkFrame(right, fg_color=CARD2, corner_radius=0,
                            height=50)
        fhdr.pack(fill="x")
        fhdr.pack_propagate(False)
        ctk.CTkLabel(fhdr,
                     text="Définir un nouveau type de composant",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=TEXT).pack(side="left", padx=18, pady=12)

        form = ctk.CTkFrame(right, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=18, pady=14)

        # Prefix
        ctk.CTkLabel(form, text="Préfixe",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).pack(anchor="w")
        pfx_row = ctk.CTkFrame(form, fg_color="transparent")
        pfx_row.pack(fill="x", pady=(4, 12))
        self._prefix_var = tk.StringVar()
        self._prefix_var.trace_add("write", self._validate_prefix)
        ctk.CTkEntry(pfx_row,
                     textvariable=self._prefix_var,
                     width=110, height=40, corner_radius=8,
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     fg_color=CARD2, border_color=BORDER,
                     text_color="#60a5fa",
                     placeholder_text="IC").pack(side="left")
        self._pfx_warn = ctk.CTkLabel(pfx_row, text="",
                                      font=ctk.CTkFont("Segoe UI", 11),
                                      text_color="#f87171")
        self._pfx_warn.pack(side="left", padx=10)

        # Name
        ctk.CTkLabel(form, text="Nom complet",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).pack(anchor="w")
        self._name_var = tk.StringVar()
        ctk.CTkEntry(form,
                     textvariable=self._name_var,
                     height=40, corner_radius=8,
                     font=ctk.CTkFont("Segoe UI", 12),
                     fg_color=CARD2, border_color=BORDER,
                     text_color=TEXT,
                     placeholder_text="Ex: Circuit intégré").pack(
                         fill="x", pady=(4, 14))

        # Pins
        ctk.CTkLabel(form, text="Broches",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).pack(anchor="w")
        self._pins_card = ctk.CTkFrame(form, corner_radius=10,
                                       fg_color=CARD2,
                                       border_width=1,
                                       border_color=BORDER)
        self._pins_card.pack(fill="x", pady=(4, 6))
        self._pins_inner = ctk.CTkFrame(self._pins_card,
                                        fg_color="transparent")
        self._pins_inner.pack(fill="x", padx=10, pady=10)

        pin_btns = ctk.CTkFrame(form, fg_color="transparent")
        pin_btns.pack(fill="x", pady=(0, 14))
        ctk.CTkButton(pin_btns, text="＋ Broche", width=110, height=32,
                      corner_radius=6, font=ctk.CTkFont("Segoe UI", 11),
                      fg_color=CARD, hover_color="#263347",
                      border_width=1, border_color=BORDER,
                      command=self._add_pin).pack(side="left", padx=(0, 6))
        ctk.CTkButton(pin_btns, text="− Broche", width=110, height=32,
                      corner_radius=6, font=ctk.CTkFont("Segoe UI", 11),
                      fg_color=CARD, hover_color="#263347",
                      border_width=1, border_color=BORDER,
                      command=self._remove_pin).pack(side="left")

        ctk.CTkButton(form, text="💾  Sauvegarder le composant",
                      height=42, corner_radius=10,
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      fg_color="#15803d", hover_color="#16a34a",
                      command=self._save).pack(fill="x")

    # ── Validation ───────────────────────────────────────────────────────────

    def _validate_prefix(self, *_):
        p = self._prefix_var.get().strip().upper()
        if p in COMPONENT_TYPES:
            self._pfx_warn.configure(text="⚠  Préfixe réservé")
        elif p and p in self._custom and p != self._current_key:
            self._pfx_warn.configure(text="⚠  Déjà utilisé")
        else:
            self._pfx_warn.configure(text="")

    # ── Pins ─────────────────────────────────────────────────────────────────

    def _set_pins(self, pins: list):
        for w in self._pins_inner.winfo_children():
            w.destroy()
        self._pin_entries = []
        for p in pins:
            self._add_pin(p)

    def _add_pin(self, value=""):
        n = len(self._pin_entries) + 1
        row = ctk.CTkFrame(self._pins_inner, fg_color="transparent")
        row.pack(anchor="w", pady=2)
        ctk.CTkLabel(row, text=f"{n}.",
                     width=24, font=ctk.CTkFont("Segoe UI", 10),
                     text_color=MUTED).pack(side="left")
        var = tk.StringVar(value=value)
        self._pin_entries.append(var)
        ctk.CTkEntry(row, textvariable=var,
                     width=140, height=30, corner_radius=6,
                     font=ctk.CTkFont("Consolas", 11),
                     fg_color=CARD, border_color=BORDER,
                     text_color="#60a5fa",
                     placeholder_text=f"Broche {n}").pack(side="left")

    def _remove_pin(self):
        if self._pin_entries:
            self._pin_entries.pop()
            children = self._pins_inner.winfo_children()
            if children:
                children[-1].destroy()

    # ── Data ─────────────────────────────────────────────────────────────────

    def _load(self):
        self._listbox.delete(0, "end")
        for k, v in COMPONENT_TYPES.items():
            self._listbox.insert("end", f"  {k}  —  {v['name']}")
        for i in range(len(COMPONENT_TYPES)):
            self._listbox.itemconfig(i, foreground="#374151")
        self._custom = {}
        p = Path(LIBRARY_FILE)
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if k not in COMPONENT_TYPES:
                    self._custom[k] = v
                    self._listbox.insert(
                        "end", f"  ★  {k}  —  {v.get('name','')}")
                    self._listbox.itemconfig(
                        self._listbox.size() - 1,
                        foreground="#60a5fa")

    def _on_select(self, _=None):
        sel = self._listbox.curselection()
        if not sel or sel[0] < len(COMPONENT_TYPES):
            return
        keys = list(self._custom.keys())
        key  = keys[sel[0] - len(COMPONENT_TYPES)]
        self._current_key = key
        v = self._custom[key]
        self._prefix_var.set(key)
        self._name_var.set(v.get("name", ""))
        self._set_pins(v.get("pins", []))

    def _new(self):
        self._current_key = None
        self._prefix_var.set("")
        self._name_var.set("")
        self._set_pins([])

    def _delete(self):
        if not self._current_key:
            messagebox.showinfo("Info",
                "Sélectionnez un composant personnalisé.")
            return
        if messagebox.askyesno("Confirmer",
                               f"Supprimer '{self._current_key}' ?"):
            self._custom.pop(self._current_key, None)
            self._current_key = None
            self._write()
            self._load()

    def _save(self):
        prefix = self._prefix_var.get().strip().upper()
        name   = self._name_var.get().strip()
        pins   = [v.get().strip()
                  for v in self._pin_entries if v.get().strip()]
        if not prefix:
            messagebox.showerror("Erreur", "Préfixe obligatoire.")
            return
        if prefix in COMPONENT_TYPES:
            messagebox.showerror("Erreur", f"'{prefix}' est réservé.")
            return
        if not pins:
            messagebox.showerror("Erreur", "Au moins une broche requise.")
            return
        if self._current_key and self._current_key != prefix:
            self._custom.pop(self._current_key, None)
        self._custom[prefix] = {"name": name, "pins": pins}
        self._current_key = prefix
        self._write()
        self._load()
        if self._on_save:
            self._on_save()
        messagebox.showinfo("Succès", f"'{prefix}' sauvegardé.")

    def _write(self):
        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(self._custom, f, ensure_ascii=False, indent=2)

    def refresh_component_list(self):
        pass
