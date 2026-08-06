"""
@file tab_draw.py
@brief Onglet « Schéma » : encapsule l'éditeur interactif et déclenche l'analyse.
"""
import json
import os
import tempfile
from collections.abc import Callable
from tkinter import filedialog, messagebox

import customtkinter as ctk

from circuit_analyzer.composant import construire_graphe, lire_netlist
from circuit_analyzer.detecteur import analyser as detecter_montages
from circuit_analyzer.xml import generer_xml, lire_xml
from gui import ui_kit
from gui.schematic_editor import SchematicEditor
from gui.schematic_io import build_from_components
from gui.theme import BG, CARD, CARD2, TEXT, TEXT_MUTED


def _xml_groupe_par_circuit(composants) -> str:
    """@brief XML BoardSCH avec groupage automatique par circuit reconnu.

    Fait tourner le meme detecteur que l'onglet Analyser sur les composants
    du schema dessine a la main, pour que l'export profite du meme groupage
    <GrpL> que l'onglet Analyse (tab_analyze.py::_texte_export_analyse) —
    jusqu'ici toujours vide faute de `results` passe a generer_xml.

    Filtre les detecteurs catch-all (impedances Z isolees et diodes non
    classifiees) qui sont des filets de securite du detecteur, pas des
    circuits reconnus : generer_xml en fusion toujours en <GRPS> meme
    monocomposant, ce qui briserait le contrat non-regression (vide si
    aucun montage reconnu).
    """
    graphe    = construire_graphe(composants)
    resultats = detecter_montages(graphe)
    # Exclure les detecteurs catch-all (filets de securite, pas des montages)
    _CATCH_ALL = {"Impédance Z", "Diode non classifiée"}
    resultats_filtres = [r for r in resultats
                         if r.get("circuit_type") not in _CATCH_ALL]
    return generer_xml(composants, results=resultats_filtres)


class TabDraw:
    """@brief Onglet éditeur de schéma (palette + canvas + barre d'actions)."""

    def __init__(self, parent, on_analyze: Callable[[str], None] | None = None,
                 on_pattern_created: Callable[[], None] | None = None):
        """@brief Construit l'onglet.

        @param parent     Widget parent (zone de contenu).
        @param on_analyze Callback(path) appelé avec le chemin du fichier netlist
                          temporaire après clic sur « Analyser ».
        @param on_pattern_created Callback() appelé après création d'un pattern
                          depuis le wizard. Non câblé par app_window depuis le
                          retrait de l'onglet Circuits (aucun consommateur
                          actuel) ; conservé pour un futur abonné.
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
                     font=ui_kit.font("display"),
                     text_color=TEXT).pack(side="left", pady=18)
        ctk.CTkLabel(hinner,
                     text="Palette → clic pour placer  ·  Clic sur un pin → fil  ·  Broche rouge = non câblée  ·  Double-clic → modifier",
                     font=ui_kit.font("body"),
                     text_color=TEXT_MUTED).pack(side="left", padx=14, pady=18)

        # ── Éditeur (zone centrale) ───────────────────────────────────────────
        self._editor = SchematicEditor(self.frame)
        self._editor.pack(fill="both", expand=True)

        # ── Barre inférieure ──────────────────────────────────────────────────
        bar = ctk.CTkFrame(self.frame, fg_color=CARD2, corner_radius=0, height=50)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        bar_inner = ctk.CTkFrame(bar, fg_color="transparent")
        bar_inner.pack(fill="both", padx=28)

        ui_kit.SecondaryButton(
            bar_inner, "Ouvrir", self._open_circuit,
            icon_name="folder-open", width=110, height=34,
        ).pack(side="left", padx=(0, 8), pady=8)

        ui_kit.SecondaryButton(
            bar_inner, "Enregistrer", self._save_circuit,
            icon_name="save", width=140, height=34,
        ).pack(side="left", padx=(0, 8), pady=8)

        ui_kit.SecondaryButton(
            bar_inner, "Exporter (ERetroDesign)", self._export_circuit_xml,
            icon_name="download", width=200, height=34,
        ).pack(side="left", padx=(0, 14), pady=8)

        # Légende raccourcis retirée ici : déjà affichée dans la palette (_legend_lbl,
        # label dédié et persistant — séparé du statut transitoire _status_lbl).
        # Elle débordait et masquait le bouton « Enregistrer comme pattern ».

        ui_kit.PrimaryButton(
            bar_inner, "Analyser ce circuit", self._launch_analyze,
            icon_name="play", width=200, height=34,
        ).pack(side="right", pady=8)

        # Secondary : seule l'action de flux principal (Analyser) reste primaire.
        ui_kit.SecondaryButton(
            bar_inner, "Enregistrer comme pattern", self._save_as_pattern,
            width=220, height=34,
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

    def _export_circuit_xml(self):
        """@brief Exporte le schéma en BoardSCH XML importable dans ERetroDesign.

        Format nouveau dialecte : réfs ConnRef « c_p_n_l » présentes dans les
        NodeL des broches (connexité par égalité de chaînes, comme l'app C#).
        """
        if self._editor.comp_count() == 0:
            messagebox.showwarning("Schéma vide",
                                   "Rien à exporter.", parent=self.frame)
            return
        composants = self._editor.exporter_composants()
        if not composants:
            messagebox.showwarning("Schéma vide",
                                   "Aucun composant réel à exporter.",
                                   parent=self.frame)
            return
        path = filedialog.asksaveasfilename(
            parent=self.frame, defaultextension=".xml",
            filetypes=[("Schéma XML (BoardSCH ERetroDesign)", "*.xml"),
                       ("Tous", "*.*")],
            title="Exporter vers ERetroDesign")
        if not path:
            return
        try:
            # REGENERATION assumee, et sans avertissement — contrairement a
            # l'onglet Analyse (`_texte_export_analyse`, gui/tab_analyze.py),
            # qui rend la carte RECUE intacte et alerte quand il doit se
            # replier sur `generer_xml`. Ici il n'y a pas de carte source : ce
            # schema est dessine dans l'app, il n'y a rien a preserver. Ne PAS
            # en conclure que l'export est fidele — l'editeur fidele est le
            # Chantier B, differe (voir docs/superpowers/specs/
            # 2026-07-29-retour-fidele-eretrodesign-design.md).
            with open(path, "w", encoding="utf-8") as f:
                f.write(_xml_groupe_par_circuit(composants))
        except OSError as exc:
            messagebox.showerror("Erreur",
                                 f"Impossible d'écrire le fichier :\n{exc}",
                                 parent=self.frame)
            return
        messagebox.showinfo(
            "Export ERetroDesign",
            f"Schéma exporté :\n{path}\n\nOuvrez-le dans ERetroDesign.",
            parent=self.frame)

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
        """@brief Exporte le circuit de l'éditeur dans un fichier temporaire XML.

        Contrôles « circuit vide » partagés par l'analyse et l'enregistrement de
        pattern. L'XML BoardSCH conserve les noms et le nombre de broches des
        puces du catalogue, contrairement à une netlist SPICE positionnelle.
        N'affiche PAS l'avertissement de broches non câblées (spécifique à
        l'analyse, géré par l'appelant).

        @param prefix Préfixe du fichier temporaire.
        @return str | None Chemin du fichier écrit, ou None si le circuit est vide.
        """
        if self._editor.comp_count() == 0:
            messagebox.showwarning("Circuit vide",
                                   "Ajoutez au moins un composant.",
                                   parent=self.frame)
            return None

        composants = self._editor.exporter_composants()
        if not composants:
            messagebox.showwarning("Circuit vide",
                                   "Aucun composant réel trouvé dans le schéma.",
                                   parent=self.frame)
            return None

        tmp = tempfile.NamedTemporaryFile(
            suffix=".xml", mode="w", encoding="utf-8",
            delete=False, prefix=prefix,
        )
        tmp.write(_xml_groupe_par_circuit(composants))
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
        L'éditeur exporte son XML, on reconstruit le graphe, puis le
        PatternWizard pré-coche tous les composants et détecte automatiquement
        les conditions topologiques vraies (via suggest_conditions).
        """
        path = self._export_netlist_file(prefix="pattern_editeur_")
        if path is None:
            return

        try:
            composants = lire_xml(path)
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
        """@brief Après création d'un pattern : notifie l'appelant et confirme."""
        if self._on_pattern_created:
            self._on_pattern_created()
        messagebox.showinfo(
            "Pattern créé",
            "Le pattern a été enregistré.\n"
            "Il sera reconnu à la prochaine analyse.",
            parent=self.frame)
