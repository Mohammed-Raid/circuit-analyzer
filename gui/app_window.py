import customtkinter as ctk
from gui.tab_analyze import TabAnalyze
from gui.tab_circuits import TabCircuits
from gui.tab_components import TabComponents

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Design tokens ────────────────────────────────────────────────────────────
BG      = "#070d1a"
SURFACE = "#0f172a"
CARD    = "#1e293b"
BORDER  = "#263347"
TEXT    = "#f1f5f9"
MUTED   = "#64748b"
BLUE    = "#3b82f6"
BLUE_D  = "#1d4ed8"


class AppWindow:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Circuit Analyzer")
        self.root.geometry("1160x740")
        self.root.minsize(900, 600)
        self.root.configure(fg_color=BG)
        self._active = 0
        self._nav_btns = []
        self._build()

    def _build(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # ── Sidebar ──────────────────────────────────────────────────────────
        sidebar = ctk.CTkFrame(self.root, width=210, corner_radius=0,
                               fg_color=SURFACE)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(3, weight=1)

        # Logo block
        logo = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo.grid(row=0, column=0, sticky="ew", padx=18, pady=(26, 20))
        ctk.CTkLabel(logo, text="⚡", font=ctk.CTkFont(size=28),
                     text_color=BLUE).pack(side="left", padx=(0, 8))
        name_col = ctk.CTkFrame(logo, fg_color="transparent")
        name_col.pack(side="left")
        ctk.CTkLabel(name_col, text="Circuit",
                     font=ctk.CTkFont("Segoe UI", 16, "bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(name_col, text="Analyzer",
                     font=ctk.CTkFont("Segoe UI", 16, "bold"),
                     text_color=BLUE).pack(anchor="w")

        # Divider
        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).grid(
            row=1, column=0, sticky="ew", padx=18, pady=(0, 14))

        ctk.CTkLabel(sidebar, text="MENU",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=MUTED).grid(
                         row=2, column=0, sticky="w", padx=22, pady=(0, 6))

        # Nav items
        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.grid(row=3, column=0, sticky="nsew", padx=10)

        items = [
            ("🔍", "Analyser",    "Lire et analyser"),
            ("⚡", "Circuits",    "Patterns personnalisés"),
            ("🔧", "Composants",  "Bibliothèque"),
        ]
        for i, (icon, label, sub) in enumerate(items):
            btn = _NavButton(nav_frame, icon, label, sub,
                             command=lambda x=i: self._switch(x))
            btn.pack(fill="x", pady=2)
            self._nav_btns.append(btn)

        # Footer
        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).grid(
            row=4, column=0, sticky="ew", padx=18, pady=10)
        ctk.CTkLabel(sidebar, text="v2.0  ·  144 tests ✓",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=MUTED).grid(
                         row=5, column=0, pady=(0, 18))

        # ── Content area ─────────────────────────────────────────────────────
        content = ctk.CTkFrame(self.root, corner_radius=0, fg_color=BG)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        tab_a = TabAnalyze(content)
        tab_c = TabCircuits(content)
        tab_p = TabComponents(content,
                              on_save=tab_c.refresh_component_list)

        self._frames = [tab_a.frame, tab_c.frame, tab_p.frame]
        for f in self._frames:
            f.grid(row=0, column=0, sticky="nsew")

        self._switch(0)

    def _switch(self, idx: int):
        self._active = idx
        for i, btn in enumerate(self._nav_btns):
            btn.set_active(i == idx)
        self._frames[idx].tkraise()

    def run(self):
        self.root.mainloop()


class _NavButton(ctk.CTkFrame):
    """Sidebar nav item with icon, label, subtitle and active indicator."""

    def __init__(self, parent, icon, label, subtitle, command):
        super().__init__(parent, fg_color="transparent", corner_radius=10)
        self._cmd = command
        self._active = False

        self._accent = ctk.CTkFrame(self, width=3, corner_radius=2,
                                    fg_color="transparent")
        self._accent.pack(side="left", fill="y", padx=(4, 0), pady=4)

        inner = ctk.CTkFrame(self, fg_color="transparent",
                             corner_radius=8)
        inner.pack(side="left", fill="both", expand=True,
                   padx=(4, 6), pady=4)

        ctk.CTkLabel(inner, text=icon,
                     font=ctk.CTkFont(size=18),
                     text_color=MUTED, width=28).pack(side="left")

        texts = ctk.CTkFrame(inner, fg_color="transparent")
        texts.pack(side="left", padx=8)
        self._lbl = ctk.CTkLabel(texts, text=label,
                                  font=ctk.CTkFont("Segoe UI", 13),
                                  text_color=MUTED, anchor="w")
        self._lbl.pack(anchor="w")
        self._sub = ctk.CTkLabel(texts, text=subtitle,
                                  font=ctk.CTkFont("Segoe UI", 9),
                                  text_color="#334155", anchor="w")
        self._sub.pack(anchor="w")

        for w in (self, inner, texts, self._lbl, self._sub):
            w.bind("<Button-1>", lambda _: command())
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def set_active(self, active: bool):
        self._active = active
        if active:
            self._accent.configure(fg_color=BLUE)
            self.configure(fg_color=CARD)
            self._lbl.configure(text_color=TEXT,
                                font=ctk.CTkFont("Segoe UI", 13, "bold"))
            self._sub.configure(text_color=MUTED)
        else:
            self._accent.configure(fg_color="transparent")
            self.configure(fg_color="transparent")
            self._lbl.configure(text_color=MUTED,
                                font=ctk.CTkFont("Segoe UI", 13))
            self._sub.configure(text_color="#334155")

    def _on_enter(self, _=None):
        if not self._active:
            self.configure(fg_color="#172033")

    def _on_leave(self, _=None):
        if not self._active:
            self.configure(fg_color="transparent")
