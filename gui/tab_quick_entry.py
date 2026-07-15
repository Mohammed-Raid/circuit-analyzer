"""@file tab_quick_entry.py
@brief Onglet « Saisie » : tableau netlist clavier + insertion catalogue
(spec 2026-07-15). Les CALCULS vivent dans circuit_analyzer.saisie ;
ce module ne fait que les widgets.
"""
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional

import customtkinter as ctk

from circuit_analyzer.composant import charger_bibliotheque
from circuit_analyzer.saisie import ModeleSaisie
from circuit_analyzer.catalogue import entrees_catalogue
from circuit_analyzer.xml import generer_xml, lire_xml
from gui import ui_kit
from gui.fonts import FONT_FAMILY
from gui.theme import (BG, CARD, CARD2, OVERLAY, TEXT, TEXT_MUTED,
                        TEXT_DIM, BORDER, BLUE, ERROR, WARN, SP)


class TabQuickEntry:
    """@brief Onglet Saisie (pattern TabDraw : .frame + callbacks)."""

    def __init__(self, parent, on_analyze: Optional[Callable] = None,
                 on_saved: Optional[Callable] = None):
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color=BG)
        self._on_analyze = on_analyze
        self._on_saved = on_saved
        self._modele = ModeleSaisie()
        self._lignes_widgets = []
        self._chemin_courant = None
        self._analyse_tmp = None
        self._tipos = list(charger_bibliotheque().keys())
        self._build()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self):
        self._appliquer_style_combobox()

        # ── En-tête ──────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self.frame, fg_color=CARD, corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        hinner = ctk.CTkFrame(header, fg_color="transparent")
        hinner.pack(fill="both", expand=True, padx=28)

        ctk.CTkLabel(hinner, text="Saisie rapide",
                     font=ui_kit.font("display"),
                     text_color=TEXT).pack(side="left", pady=18)
        ctk.CTkLabel(hinner,
                     text="Tapez votre netlist ligne par ligne, ou insérez une puce du catalogue",
                     font=ui_kit.font("body"),
                     text_color=TEXT_MUTED).pack(side="left", padx=14, pady=18)

        # ── Barre d'actions haute ────────────────────────────────────────────
        actions = ctk.CTkFrame(self.frame, fg_color=CARD2, corner_radius=0, height=54)
        actions.pack(fill="x")
        actions.pack_propagate(False)

        ainner = ctk.CTkFrame(actions, fg_color="transparent")
        ainner.pack(fill="both", expand=True, padx=28)

        self._btn_composant = ui_kit.SecondaryButton(
            ainner, "+ Composant", self._afficher_menu_types,
            icon_name="plus", width=150, height=34,
        )
        self._btn_composant.pack(side="left", padx=(0, 8), pady=10)

        ui_kit.SecondaryButton(
            ainner, "+ Puce réelle", self._popup_catalogue,
            icon_name="search", width=150, height=34,
        ).pack(side="left", padx=(0, 8), pady=10)

        ui_kit.SecondaryButton(
            ainner, "Ouvrir…", self._ouvrir,
            icon_name="folder-open", width=120, height=34,
        ).pack(side="left", padx=(0, 8), pady=10)

        self._btn_enregistrer = ui_kit.SecondaryButton(
            ainner, "Enregistrer", self._enregistrer,
            icon_name="save", width=140, height=34,
        )
        self._btn_enregistrer.pack(side="left", padx=(0, 8), pady=10)

        self._btn_analyser = ui_kit.PrimaryButton(
            ainner, "Analyser", self._analyser,
            icon_name="play", width=140, height=34,
        )
        self._btn_analyser.pack(side="right", pady=10)

        # ── Zone scrollable (tk.Canvas léger, pas de CTkScrollableFrame) ─────
        scroll_outer = tk.Frame(self.frame, bg=BG)
        scroll_outer.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(scroll_outer, bg=BG,
                                  highlightthickness=0, bd=0)
        vsb = tk.Scrollbar(scroll_outer, orient="vertical",
                           command=self._canvas.yview,
                           bg=OVERLAY, troughcolor=BG)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._results_view = tk.Frame(self._canvas, bg=BG)
        self._canvas_win = self._canvas.create_window(
            (0, SP["lg"]), window=self._results_view, anchor="nw")

        self._results_view.bind("<Configure>", self._on_scroll_configure)
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        scroll_outer.bind("<Enter>", lambda _: self._canvas.bind_all(
            "<MouseWheel>", self._on_mousewheel))
        scroll_outer.bind("<Leave>", lambda _: self._canvas.unbind_all(
            "<MouseWheel>"))

        # ── Barre d'état basse ───────────────────────────────────────────────
        bar = ctk.CTkFrame(self.frame, fg_color=CARD2, corner_radius=0, height=40)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self._lbl_etat = ctk.CTkLabel(
            bar, text="", font=ui_kit.font("caption"), text_color=TEXT_MUTED)
        self._lbl_etat.pack(side="left", padx=28, pady=8)

        self._rafraichir_validation()

    def _appliquer_style_combobox(self):
        """@brief Thème ttk local aux combobox de broches (jamais de hex)."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Saisie.TCombobox",
            fieldbackground=OVERLAY, background=OVERLAY,
            foreground=TEXT, arrowcolor=TEXT_MUTED,
            bordercolor=BORDER, lightcolor=OVERLAY, darkcolor=OVERLAY,
            selectbackground=OVERLAY, selectforeground=TEXT,
        )
        style.map(
            "Saisie.TCombobox",
            fieldbackground=[("readonly", OVERLAY)],
            foreground=[("disabled", TEXT_DIM)],
        )

    # ── Défilement (idiome gui/tab_analyze.py) ──────────────────────────────

    def _on_scroll_configure(self, _=None):
        bbox = self._canvas.bbox("all")
        if not bbox:
            return
        _, _, x1, y1 = bbox
        self._canvas.configure(scrollregion=(0, 0, x1, y1))

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._canvas_win, width=event.width)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── Menu des types ───────────────────────────────────────────────────────

    def _afficher_menu_types(self):
        menu = tk.Menu(self.frame, tearoff=0, bg=OVERLAY, fg=TEXT,
                       activebackground=BLUE, activeforeground=TEXT,
                       font=(FONT_FAMILY, 13))
        for t in self._tipos:
            menu.add_command(label=t, command=lambda tt=t: self._ajouter_type(tt))
        x = self._btn_composant.winfo_rootx()
        y = self._btn_composant.winfo_rooty() + self._btn_composant.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    # ── Lignes du modèle ─────────────────────────────────────────────────────

    def _ajouter_type(self, type_):
        self._modele.ajouter(type_)
        index = len(self._modele.lignes) - 1
        self._construire_ligne(index)

    def _changer_type(self, index, type_):
        self._modele.changer_type(index, type_)
        self._construire_ligne(index)

    def _inserer_catalogue(self, type_, value):
        self._modele.ajouter_catalogue(type_, value)
        index = len(self._modele.lignes) - 1
        self._construire_ligne(index)

    def _supprimer_ligne(self, index):
        self._modele.supprimer(index)
        self._reconstruire_tout()

    def _reconstruire_tout(self):
        for w in list(self._results_view.winfo_children()):
            w.destroy()
        self._lignes_widgets = []
        for i in range(len(self._modele.lignes)):
            self._construire_ligne(i)
        self._rafraichir_validation()

    def _libelles_broches(self, index):
        ligne = self._modele.lignes[index]
        return [f"{nom} ({ligne.fonctions[nom]})" if ligne.fonctions.get(nom) else nom
                for nom in ligne.pins]

    def _construire_ligne(self, index):
        ligne = self._modele.lignes[index]

        if index < len(self._lignes_widgets):
            frame = self._lignes_widgets[index]["frame"]
            for w in list(frame.winfo_children()):
                w.destroy()
        else:
            frame = ctk.CTkFrame(self._results_view, fg_color=CARD,
                                 corner_radius=8)
            frame.pack(fill="x", padx=SP["lg"], pady=(0, SP["sm"]))

        ligne_widgets = {"frame": frame, "pins": {}}

        # ── Bandeau haut : ref / type / valeur / supprimer (toujours visible,
        # jamais poussé hors champ par un grand nombre de broches) ───────────
        haut = ctk.CTkFrame(frame, fg_color="transparent")
        haut.pack(fill="x", padx=SP["sm"], pady=(SP["sm"], 2))

        ui_kit.IconButton(
            haut, "x", lambda i=index: self._supprimer_ligne(i),
        ).pack(side="right")

        ref_var = tk.StringVar(value=ligne.ref)

        def _maj_ref(_evt=None, i=index, var=ref_var):
            self._modele.lignes[i].ref = var.get()
            self._rafraichir_validation()

        ref_entry = ui_kit.Field(haut, textvariable=ref_var, width=64)
        ref_entry.pack(side="left", padx=(0, 4))
        ref_entry.bind("<FocusOut>", _maj_ref)
        ref_entry.bind("<Return>", _maj_ref)
        ligne_widgets["ref"] = ref_entry

        type_menu = ctk.CTkOptionMenu(
            haut, values=self._tipos, width=90,
            fg_color=OVERLAY, button_color=OVERLAY, button_hover_color=BLUE,
            text_color=TEXT, font=ui_kit.font("body"),
            command=lambda t, i=index: self._changer_type(i, t))
        type_menu.set(ligne.type)
        type_menu.pack(side="left", padx=4)
        ligne_widgets["type"] = type_menu

        value_var = tk.StringVar(value=ligne.value)

        def _maj_value(_evt=None, i=index, var=value_var):
            self._modele.lignes[i].value = var.get()
            self._rafraichir_validation()

        value_entry = ui_kit.Field(haut, textvariable=value_var, width=100)
        value_entry.pack(side="left", padx=4)
        value_entry.bind("<FocusOut>", _maj_value)
        value_entry.bind("<Return>", _maj_value)
        ligne_widgets["value"] = value_entry

        # ── Broches : grille qui s'enroule (jamais hors champ, même sur les
        # puces 8-16 broches) — 8 colonnes par rangée ────────────────────────
        _COLONNES_PAR_RANGEE = 8
        broches = ctk.CTkFrame(frame, fg_color="transparent")
        broches.pack(fill="x", padx=SP["sm"], pady=(0, SP["sm"]))

        noms = list(ligne.pins.keys())
        for j, nom in enumerate(noms):
            colonne = ctk.CTkFrame(broches, fg_color="transparent")
            colonne.grid(row=j // _COLONNES_PAR_RANGEE,
                        column=j % _COLONNES_PAR_RANGEE,
                        padx=4, pady=2, sticky="w")

            libelle = (f"{nom} ({ligne.fonctions[nom]})"
                      if ligne.fonctions.get(nom) else nom)
            ctk.CTkLabel(colonne, text=libelle, font=ui_kit.font("caption"),
                        text_color=TEXT_DIM, anchor="w").pack(fill="x")

            combo = ttk.Combobox(colonne, style="Saisie.TCombobox", width=10,
                                 font=(FONT_FAMILY, 12))
            combo.set(ligne.pins.get(nom, ""))
            combo["values"] = self._modele.nets_connus()
            combo["postcommand"] = lambda c=combo: c.configure(
                values=self._modele.nets_connus())
            es_derniere = (j == len(noms) - 1)

            def _maj_pin(evt=None, i=index, n=nom, c=combo, derniere=es_derniere):
                self._modele.lignes[i].pins[n] = c.get()
                self._rafraichir_validation()
                if (derniere and evt is not None
                        and getattr(evt, "keysym", "") == "Return"):
                    self._ajouter_type(self._modele.lignes[i].type)

            combo.bind("<<ComboboxSelected>>", _maj_pin)
            combo.bind("<FocusOut>", _maj_pin)
            combo.bind("<Return>", _maj_pin)
            combo.pack()
            ligne_widgets["pins"][nom] = combo

        if index < len(self._lignes_widgets):
            self._lignes_widgets[index] = ligne_widgets
        else:
            self._lignes_widgets.append(ligne_widgets)

        self._rafraichir_validation()
        return ligne_widgets

    # ── Validation ───────────────────────────────────────────────────────────

    def _rafraichir_validation(self):
        bloquants, avert = self._modele.valider()
        etat = "disabled" if bloquants else "normal"
        self._btn_analyser.configure(state=etat)
        self._btn_enregistrer.configure(state=etat)

        nom_fichier = Path(self._chemin_courant).name if self._chemin_courant \
            else "(non enregistré)"
        n = len(self._modele.lignes)
        texte = f"{nom_fichier}  ·  {n} composant(s)"
        couleur = TEXT_MUTED
        if bloquants:
            texte += f"  ·  {bloquants[0]}"
            couleur = ERROR
        elif avert:
            texte += f"  ·  {avert[0]}"
            couleur = WARN
        self._lbl_etat.configure(text=texte, text_color=couleur)

    # ── Catalogue ────────────────────────────────────────────────────────────

    def _popup_catalogue(self):
        top = ctk.CTkToplevel(self.frame)
        top.title("Catalogue")
        top.configure(fg_color=BG)
        top.geometry("420x480")
        top.transient(self.frame.winfo_toplevel())

        filtre_var = tk.StringVar()
        entry = ui_kit.Field(top, textvariable=filtre_var,
                             placeholder="Filtrer…")
        entry.pack(fill="x", padx=SP["md"], pady=(SP["md"], SP["sm"]))

        listbox = tk.Listbox(top, bg=OVERLAY, fg=TEXT,
                             selectbackground=BLUE, selectforeground=TEXT,
                             highlightthickness=0, bd=0,
                             font=(FONT_FAMILY, 13))
        listbox.pack(fill="both", expand=True, padx=SP["md"], pady=(0, SP["md"]))

        items_tous = sorted(entrees_catalogue(), key=lambda t: t[1])
        filtres = list(items_tous)

        def _rafraichir(*_):
            nonlocal filtres
            q = filtre_var.get().strip().lower()
            filtres = ([it for it in items_tous if q in it[1].lower()]
                      if q else list(items_tous))
            listbox.delete(0, "end")
            for type_, value, entree in filtres:
                listbox.insert("end", f"{value} — {entree.get('categorie', '')}")

        def _valider(_evt=None):
            sel = listbox.curselection()
            if not sel:
                return
            type_, value, _entree = filtres[sel[0]]
            self._inserer_catalogue(type_, value)
            top.destroy()

        filtre_var.trace_add("write", _rafraichir)
        entry.bind("<Return>", lambda e: (
            _valider() if filtres else None))
        listbox.bind("<Double-Button-1>", _valider)
        listbox.bind("<Return>", _valider)

        _rafraichir()
        entry.focus_set()

    # ── Enregistrer / Analyser / Ouvrir ─────────────────────────────────────

    def _enregistrer(self, chemin=None):
        bloquants, _ = self._modele.valider()
        if bloquants:
            messagebox.showwarning(
                "Saisie invalide", "\n".join(bloquants), parent=self.frame)
            return None

        if chemin is None:
            chemin = self._chemin_courant
        if chemin is None:
            chemin = filedialog.asksaveasfilename(
                parent=self.frame, initialdir="custom_circuits",
                defaultextension=".xml",
                filetypes=[("Schéma XML (BoardSCH)", "*.xml")],
                title="Enregistrer la saisie")
            if not chemin:
                return None

        Path(chemin).write_text(
            generer_xml(self._modele.vers_composants()), encoding="utf-8")
        self._chemin_courant = chemin
        self._rafraichir_validation()
        if self._on_saved:
            self._on_saved()
        return chemin

    def _chemin_analyse(self):
        if self._analyse_tmp is None:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".xml", prefix="saisie_", delete=False)
            tmp.close()
            self._analyse_tmp = tmp.name
        return self._analyse_tmp

    def _analyser(self):
        chemin = self._enregistrer(self._chemin_courant or self._chemin_analyse())
        if chemin and self._on_analyze:
            self._on_analyze(chemin)

    def _ouvrir(self, chemin=None):
        if chemin is None:
            chemin = filedialog.askopenfilename(
                parent=self.frame, initialdir="custom_circuits",
                filetypes=[("Schéma XML (BoardSCH)", "*.xml"), ("Tous", "*.*")],
                title="Ouvrir une saisie")
            if not chemin:
                return
        try:
            comps = lire_xml(chemin, alias_catalogue=False)
        except (ValueError, OSError) as exc:
            messagebox.showerror(
                "Ouverture impossible",
                f"Fichier illisible ou invalide :\n{exc}", parent=self.frame)
            return

        self._modele = ModeleSaisie.depuis_composants(comps)
        self._chemin_courant = chemin
        self._reconstruire_tout()
