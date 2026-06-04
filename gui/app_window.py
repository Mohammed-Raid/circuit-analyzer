import tkinter as tk
from tkinter import ttk
from gui.tab_analyze import TabAnalyze
from gui.tab_circuits import TabCircuits
from gui.tab_components import TabComponents

ACCENT   = '#2563eb'
BG       = '#f1f5f9'
FG       = '#1e293b'
TAB_BG   = '#ffffff'


class AppWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Circuit Analyzer")
        self.root.geometry("1000x700")
        self.root.minsize(800, 550)
        self.root.configure(bg=BG)
        self._apply_theme()
        self._build()

    def _apply_theme(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')

        style.configure('.',
            background=BG, foreground=FG,
            font=('Segoe UI', 10),
            borderwidth=0,
        )
        style.configure('TNotebook', background=BG, tabmargins=[2, 4, 2, 0])
        style.configure('TNotebook.Tab',
            background='#cbd5e1', foreground=FG,
            padding=[14, 6], font=('Segoe UI', 10),
        )
        style.map('TNotebook.Tab',
            background=[('selected', TAB_BG)],
            foreground=[('selected', ACCENT)],
            font=[('selected', ('Segoe UI', 10, 'bold'))],
        )
        style.configure('TFrame', background=BG)
        style.configure('Tab.TFrame', background=TAB_BG)
        style.configure('TLabel', background=BG, foreground=FG)
        style.configure('Tab.TLabel', background=TAB_BG)
        style.configure('TEntry',
            fieldbackground='#ffffff', foreground=FG,
            bordercolor='#cbd5e1', relief='flat',
            padding=4,
        )
        style.configure('TButton',
            background=ACCENT, foreground='white',
            padding=[12, 6], relief='flat',
            font=('Segoe UI', 10, 'bold'),
        )
        style.map('TButton',
            background=[('active', '#1d4ed8'), ('pressed', '#1e40af')],
        )
        style.configure('Secondary.TButton',
            background='#e2e8f0', foreground=FG,
            padding=[10, 5], font=('Segoe UI', 10),
        )
        style.map('Secondary.TButton',
            background=[('active', '#cbd5e1')],
        )
        style.configure('Danger.TButton',
            background='#ef4444', foreground='white',
            padding=[10, 5], font=('Segoe UI', 10),
        )
        style.map('Danger.TButton',
            background=[('active', '#dc2626')],
        )
        style.configure('TCheckbutton', background=TAB_BG, foreground=FG)
        style.configure('TScrollbar', background='#e2e8f0', troughcolor=BG)
        style.configure('TLabelframe',
            background=TAB_BG, foreground=FG,
            relief='flat', borderwidth=1,
        )
        style.configure('TLabelframe.Label',
            background=TAB_BG, foreground='#64748b',
            font=('Segoe UI', 9, 'bold'),
        )

    def _build(self):
        # Header bar
        header = tk.Frame(self.root, bg=ACCENT, height=48)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text='⚡ Circuit Analyzer',
                 bg=ACCENT, fg='white',
                 font=('Segoe UI', 14, 'bold')).pack(side='left', padx=16, pady=10)
        tk.Label(header, text='v2.0',
                 bg=ACCENT, fg='#93c5fd',
                 font=('Segoe UI', 10)).pack(side='left', pady=10)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=0, pady=0)

        tab_analyze    = TabAnalyze(notebook)
        tab_circuits   = TabCircuits(notebook)
        tab_components = TabComponents(notebook, on_save=tab_circuits.refresh_component_list)

        notebook.add(tab_analyze.frame,    text='  🔍 Analyser  ')
        notebook.add(tab_circuits.frame,   text='  ⚡ Circuits  ')
        notebook.add(tab_components.frame, text='  🔧 Composants  ')

    def run(self):
        self.root.mainloop()
