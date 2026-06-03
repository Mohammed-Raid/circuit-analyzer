import tkinter as tk
from tkinter import ttk, messagebox
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
        self.frame = ttk.Frame(parent)
        self._custom = []
        self._current_idx = None
        self._comp_vars = {}
        self._cond_vars = {}
        self._build()
        self._load()

    def _build(self):
        left = ttk.Frame(self.frame)
        left.pack(side='left', fill='y', padx=(10, 5), pady=10)

        ttk.Label(left, text="Circuits").pack()
        self._listbox = tk.Listbox(left, width=30, height=20)
        self._listbox.pack(fill='y', expand=True)
        self._listbox.bind('<<ListboxSelect>>', self._on_select)

        btn_f = ttk.Frame(left)
        btn_f.pack(fill='x', pady=(5, 0))
        ttk.Button(btn_f, text="+ Nouveau", command=self._new).pack(side='left')
        ttk.Button(btn_f, text="Supprimer", command=self._delete).pack(side='left', padx=5)

        right = ttk.Frame(self.frame)
        right.pack(side='left', fill='both', expand=True, padx=5, pady=10)

        ttk.Label(right, text="Nom du circuit :").grid(row=0, column=0, sticky='w', pady=4)
        self._name_var = tk.StringVar()
        ttk.Entry(right, textvariable=self._name_var, width=35).grid(row=0, column=1, sticky='w')

        ttk.Label(right, text="Composants requis :").grid(row=1, column=0, sticky='nw', pady=4)
        comp_outer = ttk.Frame(right)
        comp_outer.grid(row=1, column=1, sticky='w')
        comp_canvas = tk.Canvas(comp_outer, width=280, height=180)
        comp_sb = ttk.Scrollbar(comp_outer, orient='vertical', command=comp_canvas.yview)
        self._comp_frame = ttk.Frame(comp_canvas)
        self._comp_frame.bind('<Configure>',
            lambda e: comp_canvas.configure(scrollregion=comp_canvas.bbox('all')))
        comp_canvas.create_window((0, 0), window=self._comp_frame, anchor='nw')
        comp_canvas.configure(yscrollcommand=comp_sb.set)
        comp_sb.pack(side='right', fill='y')
        comp_canvas.pack(side='left', fill='both', expand=True)

        ttk.Label(right, text="Conditions :").grid(row=2, column=0, sticky='nw', pady=4)
        self._cond_frame = ttk.Frame(right)
        self._cond_frame.grid(row=2, column=1, sticky='w')
        for label in CONDITION_LABELS:
            var = tk.BooleanVar()
            self._cond_vars[label] = var
            ttk.Checkbutton(self._cond_frame, text=label, variable=var).pack(anchor='w')

        ttk.Button(right, text="  Sauvegarder  ", command=self._save).grid(
            row=3, column=0, columnspan=2, pady=10)

    def _build_comp_checkboxes(self):
        for w in self._comp_frame.winfo_children():
            w.destroy()
        self._comp_vars = {}
        library = load_library()
        for key, val in library.items():
            var = tk.BooleanVar()
            self._comp_vars[key] = var
            ttk.Checkbutton(
                self._comp_frame,
                text=f"{key}  —  {val['name']}",
                variable=var
            ).pack(anchor='w')

    def refresh_component_list(self):
        self._build_comp_checkboxes()

    def _load(self):
        self._build_comp_checkboxes()
        self._listbox.delete(0, 'end')
        for name in _BASE_PATTERN_NAMES:
            self._listbox.insert('end', name)
        for i in range(len(_BASE_PATTERN_NAMES)):
            self._listbox.itemconfig(i, foreground='gray')
        self._custom = load_custom_circuits()
        for c in self._custom:
            self._listbox.insert('end', c['name'])

    def _on_select(self, _=None):
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        base_count = len(_BASE_PATTERN_NAMES)
        if idx < base_count:
            return
        self._current_idx = idx - base_count
        circuit = self._custom[self._current_idx]
        self._name_var.set(circuit['name'])
        selected = set(circuit.get('components', []))
        for key, var in self._comp_vars.items():
            var.set(key in selected)
        selected_conds = set(circuit.get('conditions', []))
        for label, var in self._cond_vars.items():
            var.set(label in selected_conds)

    def _new(self):
        self._current_idx = None
        self._name_var.set('')
        for var in self._comp_vars.values():
            var.set(False)
        for var in self._cond_vars.values():
            var.set(False)

    def _delete(self):
        if self._current_idx is None:
            messagebox.showinfo("Info", "Sélectionnez un circuit personnalisé à supprimer.")
            return
        name = self._custom[self._current_idx]['name']
        if messagebox.askyesno("Confirmer", f"Supprimer le circuit '{name}' ?"):
            self._custom.pop(self._current_idx)
            save_custom_circuits(self._custom)
            self._current_idx = None
            self._load()

    def _save(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showerror("Erreur", "Le nom du circuit est obligatoire.")
            return
        components = [k for k, v in self._comp_vars.items() if v.get()]
        if not components:
            messagebox.showerror("Erreur", "Sélectionnez au moins un type de composant.")
            return
        conditions = [k for k, v in self._cond_vars.items() if v.get()]

        circuit = {'name': name, 'components': components, 'conditions': conditions}
        if self._current_idx is not None:
            self._custom[self._current_idx] = circuit
        else:
            self._custom.append(circuit)
            self._current_idx = len(self._custom) - 1

        save_custom_circuits(self._custom)
        self._load()
        messagebox.showinfo("Succès", f"Circuit '{name}' sauvegardé.")
