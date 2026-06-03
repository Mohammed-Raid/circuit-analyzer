import json
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from circuit_analyzer.component_library.base import COMPONENT_TYPES

LIBRARY_FILE = 'component_library.json'


class TabComponents:
    def __init__(self, parent, on_save=None):
        self.frame = ttk.Frame(parent)
        self._on_save = on_save
        self._custom = {}
        self._current_key = None
        self._pin_vars = []
        self._build()
        self._load()

    def _build(self):
        left = ttk.Frame(self.frame)
        left.pack(side='left', fill='y', padx=(10, 5), pady=10)

        ttk.Label(left, text="Bibliothèque de composants").pack()
        self._listbox = tk.Listbox(left, width=28, height=20)
        self._listbox.pack(fill='y', expand=True)
        self._listbox.bind('<<ListboxSelect>>', self._on_select)

        btn_f = ttk.Frame(left)
        btn_f.pack(fill='x', pady=(5, 0))
        ttk.Button(btn_f, text="+ Nouveau", command=self._new).pack(side='left')
        ttk.Button(btn_f, text="Supprimer", command=self._delete).pack(side='left', padx=5)

        right = ttk.Frame(self.frame)
        right.pack(side='left', fill='both', expand=True, padx=5, pady=10)

        ttk.Label(right, text="Préfixe :").grid(row=0, column=0, sticky='w', pady=4)
        self._prefix_var = tk.StringVar()
        ttk.Entry(right, textvariable=self._prefix_var, width=10).grid(row=0, column=1, sticky='w')

        ttk.Label(right, text="Nom :").grid(row=1, column=0, sticky='w', pady=4)
        self._name_var = tk.StringVar()
        ttk.Entry(right, textvariable=self._name_var, width=30).grid(row=1, column=1, sticky='w')

        ttk.Label(right, text="Broches :").grid(row=2, column=0, sticky='nw', pady=4)
        self._pins_frame = ttk.Frame(right)
        self._pins_frame.grid(row=2, column=1, sticky='w')

        pin_btns = ttk.Frame(right)
        pin_btns.grid(row=3, column=1, sticky='w', pady=4)
        ttk.Button(pin_btns, text="+ Broche", command=self._add_pin).pack(side='left')
        ttk.Button(pin_btns, text="- Broche", command=self._remove_pin).pack(side='left', padx=5)

        ttk.Button(right, text="  Sauvegarder  ", command=self._save).grid(
            row=4, column=0, columnspan=2, pady=10)

    def _load(self):
        self._listbox.delete(0, 'end')
        for key, val in COMPONENT_TYPES.items():
            self._listbox.insert('end', f"{key}  —  {val['name']}")
        for i in range(len(COMPONENT_TYPES)):
            self._listbox.itemconfig(i, foreground='gray')

        self._custom = {}
        p = Path(LIBRARY_FILE)
        if p.exists():
            with open(p, encoding='utf-8') as f:
                data = json.load(f)
            for key, val in data.items():
                if key not in COMPONENT_TYPES:
                    self._custom[key] = val
                    self._listbox.insert('end', f"{key}  —  {val.get('name', '')}")

    def _on_select(self, _=None):
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(COMPONENT_TYPES):
            return
        keys = list(self._custom.keys())
        key = keys[idx - len(COMPONENT_TYPES)]
        self._current_key = key
        val = self._custom[key]
        self._prefix_var.set(key)
        self._name_var.set(val.get('name', ''))
        self._set_pins(val.get('pins', []))

    def _set_pins(self, pins: list):
        for w in self._pins_frame.winfo_children():
            w.destroy()
        self._pin_vars = []
        for pin in pins:
            v = tk.StringVar(value=pin)
            self._pin_vars.append(v)
            ttk.Entry(self._pins_frame, textvariable=v, width=15).pack(anchor='w', pady=1)

    def _add_pin(self):
        v = tk.StringVar()
        self._pin_vars.append(v)
        ttk.Entry(self._pins_frame, textvariable=v, width=15).pack(anchor='w', pady=1)

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
            messagebox.showinfo("Info", "Sélectionnez un composant personnalisé à supprimer.")
            return
        if messagebox.askyesno("Confirmer", f"Supprimer '{self._current_key}' ?"):
            self._custom.pop(self._current_key, None)
            self._current_key = None
            self._write_file()
            self._load()

    def _save(self):
        prefix = self._prefix_var.get().strip().upper()
        name = self._name_var.get().strip()
        pins = [v.get().strip() for v in self._pin_vars if v.get().strip()]

        if not prefix:
            messagebox.showerror("Erreur", "Le préfixe est obligatoire.")
            return
        if prefix in COMPONENT_TYPES:
            messagebox.showerror("Erreur",
                f"Le préfixe '{prefix}' est réservé aux types de base.")
            return
        if not pins:
            messagebox.showerror("Erreur", "Au moins une broche est requise.")
            return

        if self._current_key and self._current_key != prefix:
            self._custom.pop(self._current_key, None)

        self._custom[prefix] = {'name': name, 'pins': pins}
        self._current_key = prefix
        self._write_file()
        self._load()
        if self._on_save:
            self._on_save()
        messagebox.showinfo("Succès", f"Composant '{prefix}' sauvegardé.")

    def _write_file(self):
        with open(LIBRARY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._custom, f, ensure_ascii=False, indent=2)

    def refresh_component_list(self):
        pass
