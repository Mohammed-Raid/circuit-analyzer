import customtkinter as ctk
from gui.tab_analyze import TabAnalyze
from gui.tab_circuits import TabCircuits
from gui.tab_components import TabComponents

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

SIDEBAR_W = 220
NAV_ITEMS = [
    ("🔍  Analyser",    0),
    ("⚡  Circuits",    1),
    ("🔧  Composants",  2),
]


class AppWindow:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Circuit Analyzer")
        self.root.geometry("1100x720")
        self.root.minsize(860, 580)
        self._active_tab = 0
        self._nav_btns = []
        self._build()

    def _build(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # ── Sidebar ─────────────────────────────────────────────────────────
        sidebar = ctk.CTkFrame(self.root, width=SIDEBAR_W,
                               corner_radius=0,
                               fg_color="#0f172a")
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        # Logo
        ctk.CTkLabel(
            sidebar,
            text="⚡ Circuit\n   Analyzer",
            font=ctk.CTkFont("Segoe UI", 22, "bold"),
            text_color="#60a5fa",
        ).pack(pady=(28, 4), padx=20, anchor="w")

        ctk.CTkLabel(
            sidebar, text="v2.0  —  Industrial",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color="#475569",
        ).pack(padx=20, anchor="w")

        ctk.CTkFrame(sidebar, height=1, fg_color="#1e293b").pack(
            fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            sidebar, text="NAVIGATION",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color="#475569",
        ).pack(padx=20, anchor="w", pady=(0, 8))

        for label, idx in NAV_ITEMS:
            btn = ctk.CTkButton(
                sidebar,
                text=label,
                width=SIDEBAR_W - 24,
                height=44,
                corner_radius=10,
                font=ctk.CTkFont("Segoe UI", 13),
                anchor="w",
                fg_color="transparent",
                text_color="#94a3b8",
                hover_color="#1e293b",
                command=lambda i=idx: self._switch(i),
            )
            btn.pack(padx=12, pady=2)
            self._nav_btns.append(btn)

        # Spacer + footer
        ctk.CTkFrame(sidebar, fg_color="transparent").pack(expand=True)
        ctk.CTkLabel(
            sidebar, text="144 tests ✓",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color="#334155",
        ).pack(pady=(0, 20))

        # ── Content area ────────────────────────────────────────────────────
        self._content = ctk.CTkFrame(self.root, corner_radius=0,
                                     fg_color="#0f172a")
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        # Build all tab frames
        self._tab_analyze    = TabAnalyze(self._content)
        self._tab_circuits   = TabCircuits(self._content)
        self._tab_components = TabComponents(
            self._content,
            on_save=self._tab_circuits.refresh_component_list,
        )

        self._frames = [
            self._tab_analyze.frame,
            self._tab_circuits.frame,
            self._tab_components.frame,
        ]
        for f in self._frames:
            f.grid(row=0, column=0, sticky="nsew")

        self._switch(0)

    def _switch(self, idx: int):
        self._active_tab = idx
        for i, btn in enumerate(self._nav_btns):
            if i == idx:
                btn.configure(
                    fg_color="#1d4ed8",
                    text_color="#ffffff",
                    font=ctk.CTkFont("Segoe UI", 13, "bold"),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color="#94a3b8",
                    font=ctk.CTkFont("Segoe UI", 13),
                )
        self._frames[idx].tkraise()

    def run(self):
        self.root.mainloop()
