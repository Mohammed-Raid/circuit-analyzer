import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from circuit_analyzer.parser import parse_file
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.reporter import generate


class TabAnalyze:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self._file_path = tk.StringVar()
        self._report_content = ''
        self._build()

    def _build(self):
        file_frame = ttk.Frame(self.frame)
        file_frame.pack(fill='x', padx=10, pady=(10, 5))
        ttk.Label(file_frame, text="Fichier :").pack(side='left')
        ttk.Entry(file_frame, textvariable=self._file_path, width=50).pack(side='left', padx=5)
        ttk.Button(file_frame, text="Parcourir", command=self._browse).pack(side='left')

        ttk.Button(self.frame, text="  Analyser  ", command=self._analyze).pack(pady=5)

        report_frame = ttk.Frame(self.frame)
        report_frame.pack(fill='both', expand=True, padx=10)
        self._text = tk.Text(report_frame, state='disabled', wrap='word',
                              font=('Courier', 10))
        sb = ttk.Scrollbar(report_frame, command=self._text.yview)
        self._text.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._text.pack(side='left', fill='both', expand=True)

        ttk.Button(self.frame, text="Sauvegarder le rapport",
                   command=self._save).pack(pady=(5, 10))

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Choisir un fichier circuit",
            filetypes=[("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")]
        )
        if path:
            self._file_path.set(path)

    def _analyze(self):
        path = self._file_path.get().strip()
        if not path:
            self._show("Veuillez sélectionner un fichier circuit.")
            return
        try:
            comps = parse_file(path)
            graph = build_graph(comps)
            results = match_patterns(graph)
            all_refs = [c.ref for c in comps]
            report = generate(results, path, len(comps), all_refs=all_refs)
            self._report_content = report
            self._show(report)
        except FileNotFoundError:
            self._show(f"Erreur : fichier introuvable :\n{path}")
        except Exception as e:
            self._show(f"Erreur lors de l'analyse :\n{e}")

    def _save(self):
        if not self._report_content:
            messagebox.showinfo("Information", "Aucun rapport à sauvegarder.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Fichiers texte", "*.txt")],
            title="Sauvegarder le rapport"
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._report_content)
            messagebox.showinfo("Succès", f"Rapport sauvegardé dans :\n{path}")

    def _show(self, text: str):
        self._text.configure(state='normal')
        self._text.delete('1.0', 'end')
        self._text.insert('1.0', text)
        self._text.configure(state='disabled')
