import json
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from circuit_analyzer.component_library.base import COMPONENT_TYPES

LIBRARY_FILE = 'component_library.json'
TAB_BG = '#ffffff'


class TabComponents:
    def __init__(self, parent, on_save=None):
        self.frame = ttk.Frame(parent, style='Tab.TFrame')
        self._on_save = on_save
        self._custom = {}
        self._current_key = None
        self._pin_vars = []
        self._build()
        self._load()

    def _build(self):
        # ── Left panel
        left = ttk.LabelFrame(self.frame, text='Bibliothèque de composants',
                              style='TLabelframe')
        left.pack(side='left', fill='y', padx=(12, 6), pady=12)

        self._listbox = tk.Listbox(
            left, width=30, height=22,
            bg=TAB_BG, fg='#1e293b',
            selectbackground='#bfdbfe', selectforeground='#1e293b',
            font=('Segoe UI', 10), relief='flat', bd=0,
            activestyle='none',
        )
        sb = ttk.Scrollbar(left, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._listbox.pack(side='left', fill='both', expand=True,
                           padx=4, pady=4)
        self._listbox.bind('<<ListboxSelect>>', self._on_select)

        btn_f = tk.Frame(left, bg=TAB_BG)
        btn_f.pack(fill='x', padx=4, pady=(0, 4))
        ttk.Button(btn_f, text='+ Nouveau',
                   command=self._new).pack(side='left')
        ttk.Button(btn_f, text='Supprimer',
                   style='Danger.TButton',
                   command=self._delete).pack(side='left', padx=6)

        # ── Right panel — form
        right = ttk.LabelFrame(self.frame, text='Détail du composant',
                               style='TLabelframe')
        right.pack(side='left', fill='both', expand=True,
                   padx=(0, 12), pady=12)

        inner = tk.Frame(right, bg=TAB_BG)
        inner.pack(fill='both', expand=True, padx=12, pady=8)

        # Prefix
        tk.Label(inner, text='Préfixe (ex: IC, REL) :',
                 bg=TAB_BG, fg='#64748b',
                 font=('Segoe UI', 9, 'bold')).grid(
                     row=0, column=0, sticky='w', pady=(0, 2))
        prefix_row = tk.Frame(inner, bg=TAB_BG)
        prefix_row.grid(row=1, column=0, columnspan=2,
                        sticky='w', pady=(0, 8))
        self._prefix_var = tk.StringVar()
        self._prefix_var.trace_add('write', self._validate_prefix)
        self._prefix_entry = ttk.Entry(prefix_row,
                                       textvariable=self._prefix_var,
                                       width=12)
        self._prefix_entry.pack(side='left')
        self._prefix_warn = tk.Label(prefix_row, text='',
                                     bg=TAB_BG, fg='#dc2626',
                                     font=('Segoe UI', 9))
        self._prefix_warn.pack(side='left', padx=8)

        # Name
        tk.Label(inner, text='Nom complet :',
                 bg=TAB_BG, fg='#64748b',
                 font=('Segoe UI', 9, 'bold')).grid(
                     row=2, column=0, sticky='w', pady=(0, 2))
        self._name_var = tk.StringVar()
        ttk.Entry(inner, textvariable=self._name_var, width=34).grid(
            row=3, column=0, columnspan=2, sticky='w', pady=(0, 10))

        # Pins
        tk.Label(inner, text='Broches :',
                 bg=TAB_BG, fg='#64748b',
                 font=('Segoe UI', 9, 'bold')).grid(
                     row=4, column=0, sticky='w')
        self._pins_frame = tk.Frame(inner, bg=TAB_BG)
        self._pins_frame.grid(row=5, column=0, columnspan=2,
                              sticky='w', pady=(2, 6))

        pin_btns = tk.Frame(inner, bg=TAB_BG)
        pin_btns.grid(row=6, column=0, columnspan=2,
                      sticky='w', pady=(0, 10))
        ttk.Button(pin_btns, text='+ Broche',
                   style='Secondary.TButton',
                   command=self._add_pin).pack(side='left')
        ttk.Button(pin_btns, text='- Broche',
                   style='Secondary.TButton',
                   command=self._remove_pin).pack(side='left', padx=6)

        ttk.Button(inner, text='💾  Sauvegarder',
                   command=self._save).grid(
                       row=7, column=0, columnspan=2,
                       sticky='w', pady=(0, 4))

    # ── Validation ──────────────────────────────────────────────────────────

    def _validate_prefix(self, *_):
        prefix = self._prefix_var.get().strip().upper()
        if prefix in COMPONENT_TYPES:
            self._prefix_warn.config(text='⚠ Préfixe réservé')
        elif prefix and prefix in self._custom and prefix != self._current_key:
            self._prefix_warn.config(text='⚠ Déjà utilisé')
        else:
            self._prefix_warn.config(text='')

    # ── Data ────────────────────────────────────────────────────────────────

    def _load(self):
        self._listbox.delete(0, 'end')
        for key, val in COMPONENT_TYPES.items():
            self._listbox.insert('end', f'  {key}  —  {val["name"]}')
        for i in range(len(COMPONENT_TYPES)):
            self._listbox.itemconfig(i, foreground='#94a3b8')

        self._custom = {}
        p = Path(LIBRARY_FILE)
        if p.exists():
            with open(p, encoding='utf-8') as f:
                data = json.load(f)
            for key, val in data.items():
                if key not in COMPONENT_TYPES:
                    self._custom[key] = val
                    self._listbox.insert(
                        'end',
                        f'  ★ {key}  —  {val.get("name", "")}',
                    )

    def _on_select(self, _=None):
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(COMPONENT_TYPES):
            return
        keys = list(self._custom.keys())
        key  = keys[idx - len(COMPONENT_TYPES)]
        self._current_key = key
        val  = self._custom[key]
        self._prefix_var.set(key)
        self._name_var.set(val.get('name', ''))
        self._set_pins(val.get('pins', []))

    def _set_pins(self, pins: list):
        for w in self._pins_frame.winfo_children():
            w.destroy()
        self._pin_vars = []
        for pin in pins:
            self._add_pin(pin)

    def _add_pin(self, value=''):
        v = tk.StringVar(value=value)
        self._pin_vars.append(v)
        row = tk.Frame(self._pins_frame, bg=TAB_BG)
        row.pack(anchor='w', pady=1)
        tk.Label(row, text=f'  {len(self._pin_vars)}.',
                 bg=TAB_BG, fg='#94a3b8',
                 font=('Segoe UI', 9)).pack(side='left')
        ttk.Entry(row, textvariable=v, width=14).pack(side='left')

    def _remove_pin(self):
        if self._pin_vars:
            self._pin_vars.pop()
            children = self._pins_frame.winfo_children()
            if children:
                children[-1].destroy()

    def _new(self):
        self._current_key = None
        self._prefix_var.set('')
        self._name_var.set('')
        self._set_pins([])

    def _delete(self):
        if not self._current_key:
            messagebox.showinfo('Info',
                'Sélectionnez un composant personnalisé à supprimer.')
            return
        if messagebox.askyesno('Confirmer',
                               f"Supprimer '{self._current_key}' ?"):
            self._custom.pop(self._current_key, None)
            self._current_key = None
            self._write_file()
            self._load()

    def _save(self):
        prefix = self._prefix_var.get().strip().upper()
        name   = self._name_var.get().strip()
        pins   = [v.get().strip() for v in self._pin_vars if v.get().strip()]

        if not prefix:
            messagebox.showerror('Erreur', 'Le préfixe est obligatoire.')
            return
        if prefix in COMPONENT_TYPES:
            messagebox.showerror('Erreur',
                f"Le préfixe '{prefix}' est réservé aux types de base.")
            return
        if not pins:
            messagebox.showerror('Erreur', 'Au moins une broche est requise.')
            return

        if self._current_key and self._current_key != prefix:
            self._custom.pop(self._current_key, None)

        self._custom[prefix] = {'name': name, 'pins': pins}
        self._current_key = prefix
        self._write_file()
        self._load()
        if self._on_save:
            self._on_save()
        messagebox.showinfo('Succès', f"Composant '{prefix}' sauvegardé.")

    def _write_file(self):
        with open(LIBRARY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._custom, f, ensure_ascii=False, indent=2)

    def refresh_component_list(self):
        pass
