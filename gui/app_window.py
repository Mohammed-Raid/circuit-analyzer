import tkinter as tk
from tkinter import ttk
from gui.tab_analyze import TabAnalyze
from gui.tab_circuits import TabCircuits
from gui.tab_components import TabComponents


class AppWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Circuit Analyzer")
        self.root.geometry("850x620")
        self.root.minsize(700, 500)
        self._build()

    def _build(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)

        tab_analyze = TabAnalyze(notebook)
        tab_circuits = TabCircuits(notebook)
        tab_components = TabComponents(notebook, on_save=tab_circuits.refresh_component_list)

        notebook.add(tab_analyze.frame, text='  Analyser  ')
        notebook.add(tab_circuits.frame, text='  Circuits  ')
        notebook.add(tab_components.frame, text='  Composants  ')

    def run(self):
        self.root.mainloop()
