import tkinter as tk
from tkinter import ttk, messagebox
from circuit_analyzer.component_library.loader import load_library
from circuit_analyzer.patterns.basic_circuits import ALL_PATTERNS as BASIC_PATTERNS
from circuit_analyzer.patterns.transistor import TRANSISTOR_PATTERNS
from circuit_analyzer.patterns.opamp import OPAMP_PATTERNS
from custom_circuits.loader import (
    load_custom_circuits, save_custom_circuits, CONDITION_LABELS
)

TAB_BG = '#ffffff'
_BASE_PATTERN_NAMES = [p.name for p in BASIC_PATTERNS + TRANSISTOR_PATTERNS + OPAMP_PATTERNS]


class TabCircuits:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, style='Tab.TFrame')
        self._custom = []
        self._current_idx = None
        self._comp_vars = {}
        self._cond_vars = {}
        self._build()
        self._load()

    def _build(self):
        # ── Left panel — list
        left = ttk.LabelFrame(self.frame, text='Circuits reconnus',
                              style='TLabelframe')
        left.pack(side='left', fill='y', padx=(12, 6), pady=12)

        self._listbox = tk.Listbox(
            left, width=32, height=22,
            bg=TAB_BG, fg='#1e293b',
            selectbackground='#bfdbfe', selectforeground='#1e293b',
            font=('Segoe UI', 10), relief='flat', bd=0,
            activestyle='none',
        )
        sb = ttk.Scrollbar(left, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._listbox.pack(side='left', fill='both', expand=True, padx=4, pady=4)
        self._listbox.bind('<<ListboxSelect>>', self._on_select)

        btn_f = tk.Frame(left, bg=TAB_BG)
        btn_f.pack(fill='x', padx=4, pady=(0, 4))
        ttk.Button(btn_f, text='+ Nouveau',
                   command=self._new).pack(side='left')
        ttk.Button(btn_f, text='Supprimer',
                   style='Danger.TButton',
                   command=self._delete).pack(side='left', padx=6)

        # ── Right panel — form
        right = ttk.LabelFrame(self.frame, text='Détail du circuit',
                               style='TLabelframe')
        right.pack(side='left', fill='both', expand=True,
                   padx=(0, 12), pady=12)

        inner = tk.Frame(right, bg=TAB_BG)
        inner.pack(fill='both', expand=True, padx=12, pady=8)

        # Name
        tk.Label(inner, text='Nom du circuit :',
                 bg=TAB_BG, fg='#64748b',
                 font=('Segoe UI', 9, 'bold')).grid(
                     row=0, column=0, sticky='w', pady=(0, 2))
        self._name_var = tk.StringVar()
        ttk.Entry(inner, textvariable=self._name_var, width=38).grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(0, 10))

        # Components
        tk.Label(inner, text='Composants requis :',
                 bg=TAB_BG, fg='#64748b',
                 font=('Segoe UI', 9, 'bold')).grid(
                     row=2, column=0, sticky='w')
        comp_outer = tk.Frame(inner, bg='#f1f5f9',
                              relief='flat', bd=1)
        comp_outer.grid(row=3, column=0, columnspan=2,
                        sticky='w', pady=(2, 10))
        comp_canvas = tk.Canvas(comp_outer, width=300, height=160,
                                bg='#f1f5f9', highlightthickness=0)
        comp_sb = ttk.Scrollbar(comp_outer, orient='vertical',
                                command=comp_canvas.yview)
        self._comp_frame = tk.Frame(comp_canvas, bg='#f1f5f9')
        self._comp_frame.bind(
            '<Configure>',
            lambda e: comp_canvas.configure(
                scrollregion=comp_canvas.bbox('all')))
        comp_canvas.create_window((0, 0), window=self._comp_frame, anchor='nw')
        comp_canvas.configure(yscrollcommand=comp_sb.set)
        comp_sb.pack(side='right', fill='y')
        comp_canvas.pack(side='left', fill='both', expand=True, padx=4, pady=4)

        # Conditions
        tk.Label(inner, text='Conditions topologiques :',
                 bg=TAB_BG, fg='#64748b',
                 font=('Segoe UI', 9, 'bold')).grid(
                     row=4, column=0, sticky='w')
        cond_f = tk.Frame(inner, bg='#f1f5f9')
        cond_f.grid(row=5, column=0, columnspan=2,
                    sticky='w', pady=(2, 10))
        for label in CONDITION_LABELS:
            var = tk.BooleanVar()
            self._cond_vars[label] = var
            tk.Checkbutton(
                cond_f, text=label, variable=var,
                bg='#f1f5f9', fg='#1e293b',
                activebackground='#f1f5f9',
                font=('Segoe UI', 10),
                selectcolor='#bfdbfe',
            ).pack(anchor='w', padx=6, pady=1)

        ttk.Button(inner, text='💾  Sauvegarder',
                   command=self._save).grid(
                       row=6, column=0, columnspan=2,
                       sticky='w', pady=(4, 0))

    def _build_comp_checkboxes(self):
        for w in self._comp_frame.winfo_children():
            w.destroy()
        self._comp_vars = {}
        for key, val in load_library().items():
            var = tk.BooleanVar()
            self._comp_vars[key] = var
            tk.Checkbutton(
                self._comp_frame,
                text=f'{key}  —  {val["name"]}',
                variable=var,
                bg='#f1f5f9', fg='#1e293b',
                activebackground='#f1f5f9',
                font=('Segoe UI', 10),
                selectcolor='#bfdbfe',
            ).pack(anchor='w', padx=6, pady=1)

    def refresh_component_list(self):
        self._build_comp_checkboxes()

    def _load(self):
        self._build_comp_checkboxes()
        self._listbox.delete(0, 'end')
        for name in _BASE_PATTERN_NAMES:
            self._listbox.insert('end', '  ' + name)
        for i in range(len(_BASE_PATTERN_NAMES)):
            self._listbox.itemconfig(i, foreground='#94a3b8')
        self._custom = load_custom_circuits()
        for c in self._custom:
            self._listbox.insert('end', '  ★ ' + c['name'])

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
        for label, var in self._cond_vars.items():
            var.set(label in circuit.get('conditions', []))

    def _new(self):
        self._current_idx = None
        self._name_var.set('')
        for var in self._comp_vars.values():
            var.set(False)
        for var in self._cond_vars.values():
            var.set(False)

    def _delete(self):
        if self._current_idx is None:
            messagebox.showinfo('Info',
                'Sélectionnez un circuit personnalisé à supprimer.')
            return
        name = self._custom[self._current_idx]['name']
        if messagebox.askyesno('Confirmer',
                               f"Supprimer le circuit '{name}' ?"):
            self._custom.pop(self._current_idx)
            save_custom_circuits(self._custom)
            self._current_idx = None
            self._load()

    def _save(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showerror('Erreur', 'Le nom du circuit est obligatoire.')
            return
        components = [k for k, v in self._comp_vars.items() if v.get()]
        if not components:
            messagebox.showerror('Erreur',
                'Sélectionnez au moins un type de composant.')
            return
        conditions = [k for k, v in self._cond_vars.items() if v.get()]
        circuit = {'name': name,
                   'components': components,
                   'conditions': conditions}
        if self._current_idx is not None:
            self._custom[self._current_idx] = circuit
        else:
            self._custom.append(circuit)
            self._current_idx = len(self._custom) - 1
        save_custom_circuits(self._custom)
        self._load()
        messagebox.showinfo('Succès', f"Circuit '{name}' sauvegardé.")
