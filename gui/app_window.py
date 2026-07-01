"""
@file app_window.py
@brief Fenêtre principale CustomTkinter : barre latérale de navigation et onglets.
"""
import customtkinter as ctk
from circuit_analyzer import __version__
from gui.tab_analyze import TabAnalyze
from gui.tab_circuits import TabCircuits
from gui.tab_components import TabComponents
from gui.tab_draw import TabDraw

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

from gui.theme import BG, SURFACE, CARD, BORDER, TEXT, MUTED, BLUE, BLUE_D


class AppWindow:
    """@brief Fenêtre principale de l'application (barre latérale + 4 onglets)."""

    def __init__(self):
        """@brief Construit la fenêtre, ses dimensions et son contenu."""
        self.root = ctk.CTk()
        self.root.title("Circuit Analyzer")
        self.root.geometry("1160x740")
        self.root.minsize(900, 600)
        self.root.configure(fg_color=BG)
        self._active = 0
        self._nav_btns = []
        self._build()

    def _build(self):
        """@brief Construit la barre latérale, les boutons de navigation et les onglets."""
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # ── Sidebar ──────────────────────────────────────────────────────────
        sidebar = ctk.CTkFrame(self.root, width=210, corner_radius=0,
                               fg_color=SURFACE)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        # La zone de navigation (row 3) absorbe l'espace et défile : aucun onglet
        # n'est jamais coupé, même fenêtre courte ou mise à l'échelle Windows 150 %.
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

        # Nav items — zone défilable pour que les onglets restent toujours
        # accessibles même si la hauteur disponible est insuffisante.
        nav_frame = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        nav_frame.grid(row=3, column=0, sticky="nsew", padx=6)

        items = [
            ("🔍", "Analyser",    "Lire et analyser"),
            ("✏",  "Schéma",     "Dessiner un circuit"),
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
        ctk.CTkLabel(sidebar, text=f"v{__version__}",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=MUTED).grid(
                         row=5, column=0, pady=(0, 18))

        # ── Content area ─────────────────────────────────────────────────────
        content = ctk.CTkFrame(self.root, corner_radius=0, fg_color=BG)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        # Liaison tardive : tab_c n'existe pas encore quand tab_a/tab_d sont créés,
        # mais ce callback n'est appelé qu'après une action utilisateur (le nom
        # tab_c est alors résolu).
        def _on_pattern_created():
            # Un pattern vient d'être créé (éditeur/analyse) : recharger la liste
            # de l'onglet Circuits, sinon il n'y apparaît qu'au prochain démarrage.
            tab_c.refresh_circuits()

        tab_a = TabAnalyze(content, on_pattern_created=_on_pattern_created)
        tab_d = TabDraw(content,
                        on_analyze=lambda path: (
                            tab_a._file_path.set(path),
                            tab_a._analyze(),
                            self._switch(0),
                        ),
                        on_pattern_created=_on_pattern_created)
        tab_c = TabCircuits(content)

        def _on_lib_change():
            # La bibliothèque a changé : rafraîchir l'onglet Circuits ET la
            # palette de l'éditeur de schéma (nouveaux types / types supprimés).
            tab_c.refresh_component_list()
            tab_d.refresh_palette()

        tab_p = TabComponents(content, on_save=_on_lib_change)

        self._frames = [tab_a.frame, tab_d.frame, tab_c.frame, tab_p.frame]
        for f in self._frames:
            f.grid(row=0, column=0, sticky="nsew")

        self._switch(0)

    def _switch(self, idx: int):
        """@brief Active l'onglet d'indice idx et met à jour la navigation.

        @param idx Indice de l'onglet à afficher (0=Analyser, 1=Schéma, 2=Circuits, 3=Composants).
        @return None
        """
        self._active = idx
        for i, btn in enumerate(self._nav_btns):
            btn.set_active(i == idx)
        self._frames[idx].tkraise()

    def run(self):
        """@brief Lance la boucle d'événements Tk (bloquant jusqu'à fermeture)."""
        self.root.mainloop()


class _NavButton(ctk.CTkFrame):
    """@brief Élément de navigation latéral : icône, libellé, sous-titre et indicateur actif."""

    def __init__(self, parent, icon, label, subtitle, command):
        """@brief Construit le bouton de navigation.

        @param parent Widget parent.
        @param icon Icône (emoji) affichée.
        @param label Libellé principal.
        @param subtitle Sous-titre descriptif.
        @param command Callback appelé au clic.
        """
        # Hauteur fixe : sans elle un CTkFrame garde sa hauteur par défaut (200 px)
        # et seuls 2 des 4 onglets tenaient à l'écran (Circuits/Composants cachés).
        super().__init__(parent, fg_color="transparent", corner_radius=10, height=52)
        self.pack_propagate(False)
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
                                  text_color="#94a3b8", anchor="w")
        self._lbl.pack(anchor="w")
        self._sub = ctk.CTkLabel(texts, text=subtitle,
                                  font=ctk.CTkFont("Segoe UI", 9),
                                  text_color=MUTED, anchor="w")
        self._sub.pack(anchor="w")

        for w in (self, inner, texts, self._lbl, self._sub):
            w.bind("<Button-1>", lambda _: command())
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def set_active(self, active: bool):
        """@brief Met le bouton en état actif ou inactif (couleurs, accent, gras).

        @param active True pour l'état actif.
        @return None
        """
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
            self._lbl.configure(text_color="#94a3b8",
                                font=ctk.CTkFont("Segoe UI", 13))
            self._sub.configure(text_color=MUTED)

    def _on_enter(self, _=None):
        """@brief Survol : applique une couleur de fond si le bouton est inactif."""
        if not self._active:
            self.configure(fg_color="#172033")

    def _on_leave(self, _=None):
        """@brief Fin de survol : restaure le fond transparent si inactif."""
        if not self._active:
            self.configure(fg_color="transparent")
