"""
@file app_window.py
@brief Fenêtre principale CustomTkinter : barre latérale de navigation et onglets.
"""
import customtkinter as ctk

from circuit_analyzer import __version__
from gui import ui_kit
from gui.fonts import FONT_FAMILY, register_fonts
from gui.tab_analyze import TabAnalyze
from gui.tab_circuits import TabCircuits
from gui.tab_components import TabComponents
from gui.tab_draw import TabDraw

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

from gui.theme import BG, BLUE, BORDER, CARD, MUTED, SURFACE, TEXT


class AppWindow:
    """@brief Fenêtre principale de l'application (barre latérale + 4 onglets)."""

    def __init__(self, initial_file=None):
        """@brief Construit la fenêtre, ses dimensions et son contenu.

        @param initial_file Chemin d'un schéma à charger et analyser automatiquement au
               démarrage (passé en argument de ligne de commande par ERetroDesign pour le
               bouton « Analyser le schéma » — un clic, sans action manuelle). None = normal.
        """
        register_fonts()  # Enregistre Inter avant toute création de widget
        self.root = ctk.CTk()
        self.root.title("Circuit Analyzer")
        self.root.geometry("1160x740")
        self.root.minsize(900, 600)
        self.root.configure(fg_color=BG)
        self._active = 0
        self._nav_btns = []
        self._build()
        if initial_file:
            # Laisse la fenêtre se réaliser avant d'attaquer l'analyse (même délai que
            # l'ancien hook, évite toute course avec le premier rendu Tk).
            self._initial_file = initial_file
            self.root.after(300, self._auto_analyze)

    def _auto_analyze(self):
        """@brief Charge et analyse le fichier passé au démarrage (onglet Analyser).

        Reprend exactement le chemin déjà utilisé par TabDraw (bouton "Analyser" du
        Schéma) : _file_path.set(path) puis _analyze(), pour rester sur le même code
        testé plutôt que d'appeler l'analyse par un autre biais.
        """
        self._tab_a._file_path.set(self._initial_file)
        self._tab_a._analyze()
        self._switch(0)

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
        ctk.CTkLabel(logo, text="Z", font=ctk.CTkFont(FONT_FAMILY, 26, "bold"),
                     text_color=BLUE).pack(side="left", padx=(0, 8))
        name_col = ctk.CTkFrame(logo, fg_color="transparent")
        name_col.pack(side="left")
        ctk.CTkLabel(name_col, text="Circuit",
                     font=ui_kit.font("title"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(name_col, text="Analyzer",
                     font=ui_kit.font("title"),
                     text_color=BLUE).pack(anchor="w")

        # Divider
        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).grid(
            row=1, column=0, sticky="ew", padx=18, pady=(0, 14))

        ctk.CTkLabel(sidebar, text="MENU",
                     font=ui_kit.font("overline"),
                     text_color=MUTED).grid(
                         row=2, column=0, sticky="w", padx=22, pady=(0, 6))

        # Nav items — zone défilable pour que les onglets restent toujours
        # accessibles même si la hauteur disponible est insuffisante.
        nav_frame = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        nav_frame.grid(row=3, column=0, sticky="nsew", padx=6)

        items = [
            ("search",   "Analyser",   "Lire et analyser"),
            ("pen-tool", "Schéma",     "Dessiner un circuit"),
            ("wrench",   "Composants", "Bibliothèque"),
            ("zap",      "Circuits",   "Patterns personnalisés"),
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
                     font=ui_kit.font("caption"),
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
        self._tab_a = tab_a  # référence gardée pour l'auto-analyse au démarrage (voir _auto_analyze)
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

        self._frames = [tab_a.frame, tab_d.frame, tab_p.frame, tab_c.frame]
        for f in self._frames:
            f.grid(row=0, column=0, sticky="nsew")

        self._switch(0)

    def _switch(self, idx: int):
        """@brief Active l'onglet d'indice idx et met à jour la navigation.

        @param idx Indice de l'onglet à afficher (0=Analyser, 1=Schéma, 2=Composants, 3=Circuits).
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
        @param icon Nom d'icône Lucide (ex. "search") rendu via ui_kit.icon.
        @param label Libellé principal.
        @param subtitle Sous-titre descriptif.
        @param command Callback appelé au clic.
        """
        # Hauteur fixe : sans elle un CTkFrame garde sa hauteur par défaut (200 px)
        # et tous les onglets ne tenaient pas à l'écran (Composants caché).
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

        self._icon_lbl = ctk.CTkLabel(inner, image=ui_kit.icon(icon, 18),
                                      text="", width=28)
        self._icon_lbl.pack(side="left")

        texts = ctk.CTkFrame(inner, fg_color="transparent")
        texts.pack(side="left", padx=8)
        self._lbl = ctk.CTkLabel(texts, text=label,
                                  font=ui_kit.font("body"),
                                  text_color="#94a3b8", anchor="w")
        self._lbl.pack(anchor="w")
        self._sub = ctk.CTkLabel(texts, text=subtitle,
                                  font=ui_kit.font("caption"),
                                  text_color=MUTED, anchor="w")
        self._sub.pack(anchor="w")

        for w in (self, inner, texts, self._lbl, self._sub, self._icon_lbl):
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
                                font=ui_kit.font("body", "bold"))
            self._sub.configure(text_color=MUTED)
        else:
            self._accent.configure(fg_color="transparent")
            self.configure(fg_color="transparent")
            self._lbl.configure(text_color="#94a3b8",
                                font=ui_kit.font("body"))
            self._sub.configure(text_color=MUTED)

    def _on_enter(self, _=None):
        """@brief Survol : applique une couleur de fond si le bouton est inactif."""
        if not self._active:
            self.configure(fg_color="#172033")

    def _on_leave(self, _=None):
        """@brief Fin de survol : restaure le fond transparent si inactif."""
        if not self._active:
            self.configure(fg_color="transparent")
