"""
@file tab_draw.py
@brief Onglet « Schéma » : encapsule l'éditeur interactif et déclenche l'analyse.
"""
import tempfile
from typing import Callable, Optional

import customtkinter as ctk
from tkinter import messagebox

from gui.theme import BG, CARD, CARD2, BORDER, TEXT, MUTED
from gui.schematic_editor import SchematicEditor


class TabDraw:
    """@brief Onglet éditeur de schéma (palette + canvas + barre d'actions)."""

    def __init__(self, parent, on_analyze: Optional[Callable[[str], None]] = None):
        """@brief Construit l'onglet.

        @param parent     Widget parent (zone de contenu).
        @param on_analyze Callback(path) appelé avec le chemin du fichier netlist
                          temporaire après clic sur « Analyser ».
        """
        self.frame       = ctk.CTkFrame(parent, corner_radius=0, fg_color=BG)
        self._on_analyze = on_analyze
        self._build()

    def _build(self):
        # ── En-tête ──────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self.frame, fg_color=CARD, corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        hinner = ctk.CTkFrame(header, fg_color="transparent")
        hinner.pack(fill="both", expand=True, padx=28)

        ctk.CTkLabel(hinner, text="Éditeur de schéma",
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color=TEXT).pack(side="left", pady=18)
        ctk.CTkLabel(hinner,
                     text="Palette → clic pour placer  ·  Clic sur un pin → fil  ·  Broche rouge = non câblée  ·  Double-clic → modifier",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).pack(side="left", padx=14, pady=18)

        # ── Éditeur (zone centrale) ───────────────────────────────────────────
        self._editor = SchematicEditor(self.frame)
        self._editor.pack(fill="both", expand=True)

        # ── Barre inférieure ──────────────────────────────────────────────────
        bar = ctk.CTkFrame(self.frame, fg_color=CARD2, corner_radius=0, height=50)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        bar_inner = ctk.CTkFrame(bar, fg_color="transparent")
        bar_inner.pack(fill="both", padx=28)

        ctk.CTkLabel(bar_inner,
                     text="Suppr = effacer  ·  Ctrl+Z = annuler  ·  Échap = sortir du mode  ·  Clic droit = menu",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=MUTED).pack(side="left", pady=10)

        ctk.CTkButton(
            bar_inner,
            text="▶  Analyser ce circuit",
            width=190, height=34, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            fg_color="#16a34a", hover_color="#15803d",
            command=self._launch_analyze,
        ).pack(side="right", pady=8)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _launch_analyze(self):
        """@brief Exporte la netlist et transfère le chemin vers le pipeline d'analyse."""
        if self._editor.comp_count() == 0:
            messagebox.showwarning("Circuit vide",
                                   "Ajoutez au moins un composant avant d'analyser.",
                                   parent=self.frame)
            return

        netlist = self._editor.to_netlist()
        if not netlist.strip():
            messagebox.showwarning("Circuit vide",
                                   "Aucun composant réel trouvé dans le schéma.",
                                   parent=self.frame)
            return

        # Écriture dans un fichier temporaire .sp conservé jusqu'à la prochaine analyse
        tmp = tempfile.NamedTemporaryFile(
            suffix=".sp", mode="w", encoding="utf-8",
            delete=False, prefix="schema_editeur_",
        )
        tmp.write(netlist)
        tmp.close()

        if self._on_analyze:
            self._on_analyze(tmp.name)
        else:
            # Fallback : afficher la netlist brute
            messagebox.showinfo("Netlist générée", netlist, parent=self.frame)
