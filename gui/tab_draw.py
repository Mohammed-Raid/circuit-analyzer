"""
@file tab_draw.py
@brief Onglet « Schéma » : encapsule l'éditeur interactif et déclenche l'analyse.
"""
import json
import os
import tempfile
from typing import Callable, Optional

import customtkinter as ctk
from tkinter import messagebox, filedialog

from gui.theme import BG, CARD, CARD2, BORDER, TEXT, MUTED
from gui.schematic_editor import SchematicEditor
from gui.schematic_io import build_from_components
from circuit_analyzer.composant import lire_netlist, construire_graphe
from circuit_analyzer.xml import lire_xml


class TabDraw:
    """@brief Onglet éditeur de schéma (palette + canvas + barre d'actions)."""

    def __init__(self, parent, on_analyze: Optional[Callable[[str], None]] = None,
                 on_pattern_created: Optional[Callable[[], None]] = None):
        """@brief Construit l'onglet.

        @param parent     Widget parent (zone de contenu).
        @param on_analyze Callback(path) appelé avec le chemin du fichier netlist
                          temporaire après clic sur « Analyser ».
        @param on_pattern_created Callback() appelé après création d'un pattern
                          (pour rafraîchir l'onglet Circuits).
        """
        self.frame               = ctk.CTkFrame(parent, corner_radius=0, fg_color=BG)
        self._on_analyze         = on_analyze
        self._on_pattern_created = on_pattern_created
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

        ctk.CTkButton(
            bar_inner, text="📂  Ouvrir",
            width=96, height=34, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            fg_color=CARD, hover_color="#263347",
            border_width=1, border_color=BORDER,
            command=self._open_circuit,
        ).pack(side="left", padx=(0, 8), pady=8)

        ctk.CTkButton(
            bar_inner, text="💾  Enregistrer",
            width=120, height=34, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            fg_color=CARD, hover_color="#263347",
            border_width=1, border_color=BORDER,
            command=self._save_circuit,
        ).pack(side="left", padx=(0, 14), pady=8)

        ctk.CTkLabel(bar_inner,
                     text="Espace/R rotation  ·  Ctrl+Z/Y annuler·rétablir  ·  Ctrl+C/V/D copier·coller·dupliquer  ·  F ajuster  ·  Clic droit = menu",
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

        ctk.CTkButton(
            bar_inner,
            text="💾  Enregistrer comme pattern",
            width=210, height=34, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            fg_color="#2563eb", hover_color="#1d4ed8",
            command=self._save_as_pattern,
        ).pack(side="right", padx=(0, 10), pady=8)

    # ── Synchronisation bibliothèque ──────────────────────────────────────────

    def refresh_palette(self):
        """@brief Reconstruit la palette de l'éditeur (bibliothèque modifiée)."""
        self._editor.refresh_palette()

    # ── Sauvegarde / ouverture du schéma ──────────────────────────────────────

    def _save_circuit(self):
        """@brief Enregistre le schéma courant dans un fichier .circ (JSON)."""
        if self._editor.comp_count() == 0:
            messagebox.showwarning("Schéma vide",
                                   "Rien à enregistrer.", parent=self.frame)
            return
        path = filedialog.asksaveasfilename(
            parent=self.frame, defaultextension=".circ",
            filetypes=[("Schéma Circuit Analyzer", "*.circ"), ("Tous", "*.*")],
            title="Enregistrer le schéma")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._editor.to_dict(), f, ensure_ascii=False, indent=2)
        except OSError as exc:
            messagebox.showerror("Erreur",
                                 f"Impossible d'écrire le fichier :\n{exc}",
                                 parent=self.frame)
            return
        messagebox.showinfo("Enregistré",
                            f"Schéma enregistré :\n{path}", parent=self.frame)

    def _open_circuit(self):
        """@brief Ouvre un .circ, ou importe un .xml / netlist dans l'éditeur."""
        path = filedialog.askopenfilename(
            parent=self.frame,
            filetypes=[
                ("Schémas & netlists", "*.circ *.xml *.txt *.cir *.sp *.net"),
                ("Schéma Circuit Analyzer", "*.circ"),
                ("Schéma XML (BoardSCH)", "*.xml"),
                ("Netlists", "*.txt *.cir *.sp *.net"),
                ("Tous", "*.*"),
            ],
            title="Ouvrir un schéma ou une netlist")
        if not path:
            return

        if self._editor.comp_count() > 0 and not messagebox.askyesno(
                "Remplacer le schéma",
                "Le canvas n'est pas vide. Remplacer le schéma courant ?",
                parent=self.frame):
            return

        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".circ":
                with open(path, encoding="utf-8") as f:
                    self._editor.load_dict(json.load(f))
                report = None
            else:
                composants = (lire_xml(path) if ext == ".xml"
                              else lire_netlist(path))
                doc = build_from_components(composants, self._editor._defs)
                report = doc.pop("_report", None)
                self._editor.load_dict(doc)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Ouverture impossible",
                                 f"Fichier illisible ou invalide :\n{exc}",
                                 parent=self.frame)
            return

        if report and (report["ignored_components"] or report["dropped_pins"]):
            ignored = report["ignored_components"]
            details = []
            if ignored:
                apercu = ", ".join(ignored[:8])
                suite = "" if len(ignored) <= 8 else f" (+{len(ignored) - 8})"
                details.append(f"{len(ignored)} composant(s) ignoré(s) "
                               f"(type inconnu) : {apercu}{suite}")
            if report["dropped_pins"]:
                details.append(f"{report['dropped_pins']} connexion(s) de broche "
                               "ignorée(s) (broche absente de l'éditeur, ex. V+/V-).")
            messagebox.showinfo("Import terminé",
                                "Schéma importé (placement automatique à "
                                "réorganiser).\n\n" + "\n".join(details),
                                parent=self.frame)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _export_netlist_file(self, prefix: str = "schema_editeur_"):
        """@brief Exporte la netlist de l'éditeur dans un fichier temporaire .sp.

        Contrôles « circuit vide » partagés par l'analyse et l'enregistrement de
        pattern. N'affiche PAS l'avertissement de broches non câblées (spécifique
        à l'analyse, géré par l'appelant).

        @param prefix Préfixe du fichier temporaire.
        @return str | None Chemin du fichier écrit, ou None si le circuit est vide.
        """
        if self._editor.comp_count() == 0:
            messagebox.showwarning("Circuit vide",
                                   "Ajoutez au moins un composant.",
                                   parent=self.frame)
            return None

        netlist = self._editor.to_netlist()
        if not netlist.strip():
            messagebox.showwarning("Circuit vide",
                                   "Aucun composant réel trouvé dans le schéma.",
                                   parent=self.frame)
            return None

        tmp = tempfile.NamedTemporaryFile(
            suffix=".sp", mode="w", encoding="utf-8",
            delete=False, prefix=prefix,
        )
        tmp.write(netlist)
        tmp.close()
        return tmp.name

    def _launch_analyze(self):
        """@brief Exporte la netlist et transfère le chemin vers le pipeline d'analyse."""
        if self._editor.comp_count() == 0:
            messagebox.showwarning("Circuit vide",
                                   "Ajoutez au moins un composant avant d'analyser.",
                                   parent=self.frame)
            return

        # Avertissement : broches non câblées (cause n°1 de mauvaise reconnaissance)
        loose = self._editor.unconnected_pins()
        if loose:
            detail = ", ".join(f"{ref}.{pn}" for ref, pn in loose[:8])
            more = "" if len(loose) <= 8 else f"  (+{len(loose) - 8})"
            if not messagebox.askyesno(
                "Broches non câblées",
                f"{len(loose)} broche(s) ne sont pas connectées :\n{detail}{more}\n\n"
                "Une broche non câblée empêche souvent la reconnaissance du circuit "
                "(ex. un inverseur dont le feedback n'est pas bouclé sur OUT "
                "devient un comparateur).\n\nAnalyser quand même ?",
                parent=self.frame):
                return

        path = self._export_netlist_file()
        if path is None:
            return

        if self._on_analyze:
            self._on_analyze(path)
        else:
            # Fallback : afficher la netlist brute
            messagebox.showinfo("Netlist générée",
                                self._editor.to_netlist(), parent=self.frame)

    def _save_as_pattern(self):
        """@brief Ouvre le wizard pour enregistrer le circuit dessiné comme pattern.

        Le geste naturel : « voici mon circuit, enregistre-le comme pattern ».
        L'éditeur exporte sa netlist, on reconstruit le graphe, puis le
        PatternWizard pré-coche tous les composants et détecte automatiquement
        les conditions topologiques vraies (via suggest_conditions).
        """
        path = self._export_netlist_file(prefix="pattern_editeur_")
        if path is None:
            return

        try:
            composants = lire_netlist(path)
            graph = construire_graphe(composants)
        except Exception as exc:
            messagebox.showerror(
                "Erreur", f"Impossible de reconstruire le circuit :\n{exc}",
                parent=self.frame)
            return

        comp_info = {
            c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
            for c in composants
        }
        refs = list(comp_info.keys())
        if not refs:
            messagebox.showwarning("Circuit vide",
                                   "Aucun composant à enregistrer.",
                                   parent=self.frame)
            return

        from gui.pattern_wizard import PatternWizard
        PatternWizard(
            self.frame, graph, refs, comp_info,
            on_created=self._pattern_created,
        )

    def _pattern_created(self):
        """@brief Après création d'un pattern : rafraîchit Circuits et confirme."""
        if self._on_pattern_created:
            self._on_pattern_created()
        messagebox.showinfo(
            "Pattern créé",
            "Le pattern a été enregistré et ajouté à l'onglet « Circuits ».\n"
            "Il sera reconnu à la prochaine analyse.",
            parent=self.frame)
