"""
@file widgets.py
@brief Briques d'interface partagées par les onglets Composants et Circuits.

  - ListeSectionnee : listbox à deux sections (intégrés / personnalisés) avec
    en-têtes non sélectionnables, scrollbar et boutons Nouveau/Supprimer.
  - BandeauEtat     : bandeau indiquant le mode du formulaire
    (nouveau / édition / lecture seule).
  - ligne_aide      : petite ligne de texte d'aide sous un champ.
  - lier_molette    : rend une zone scrollable défilable à la molette partout,
    y compris au-dessus d'enfants ajoutés dynamiquement.
"""
import tkinter as tk
import customtkinter as ctk

from gui import theme
from gui import ui_kit


class ListeSectionnee:
    """
    @brief Panneau de liste à deux sections (intégrés / personnalisés) pour les onglets.

    Usage :
        panneau = ListeSectionnee(parent, titre="Liste des circuits",
                                  on_select=cb, on_new=cb, on_delete=cb)
        panneau.frame.grid(...)
        panneau.remplir(integres=["R — Résistance", ...],
                        personnalises=["Mon circuit", ...])

    on_select reçoit (section, index) avec section dans {'integre', 'perso'}.
    """

    def __init__(self, parent, titre: str, on_select, on_new, on_delete):
        """@brief Construit le panneau de liste sectionné.

        @param parent Widget parent.
        @param titre Titre affiché au-dessus de la liste.
        @param on_select Callback (section, index) à la sélection d'un élément.
        @param on_new Callback du bouton « Nouveau ».
        @param on_delete Callback du bouton « Supprimer ».
        """
        self._on_select_cb = on_select
        # rangée listbox -> ('entete', None) | ('integre', i) | ('perso', i)
        self._lignes: list[tuple] = []

        self.frame = ui_kit.Card(parent)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        ui_kit.SectionHeader(self.frame, titre).grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 6))

        lb_f = ctk.CTkFrame(self.frame, fg_color=theme.SURFACE,
                            corner_radius=theme.R["md"])
        lb_f.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self._listbox = tk.Listbox(
            lb_f, width=32, height=24,
            bg=theme.SURFACE, fg=theme.TEXT_MUTED,
            selectbackground=theme.BLUE_PRESS, selectforeground=theme.TEXT,
            font=ui_kit.font("body"), relief="flat", bd=0,
            activestyle="none", highlightthickness=0,
        )
        sb = tk.Scrollbar(lb_f, command=self._listbox.yview,
                          bg=theme.RAISED, troughcolor=theme.SURFACE)
        self._listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._listbox.pack(fill="both", expand=True, padx=6, pady=6)
        self._listbox.bind("<<ListboxSelect>>", self._sur_selection)

        br = ctk.CTkFrame(self.frame, fg_color="transparent")
        br.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 12))
        ui_kit.PrimaryButton(
            br, "Nouveau", on_new, icon_name="plus",
            height=36).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ui_kit.DangerButton(
            br, "Supprimer", on_delete, icon_name="trash-2",
            height=36).pack(side="left", expand=True, fill="x")

    def remplir(self, integres: list[str], personnalises: list[str]) -> None:
        """@brief (Re)peuple la liste : section intégrés puis section personnalisés.

        @param integres Libellés des éléments intégrés (consultables).
        @param personnalises Libellés des éléments personnalisés (modifiables).
        @return None
        """
        self._listbox.delete(0, "end")
        self._lignes = []

        self._entete(f"INTÉGRÉS ({len(integres)}) — consultables")
        for texte in integres:
            self._listbox.insert("end", f"   {texte}")
            self._listbox.itemconfig("end", foreground=theme.TEXT_MUTED)
            self._lignes.append(('integre', len(self._lignes_de('integre'))))

        self._entete(f"PERSONNALISÉS ({len(personnalises)}) — modifiables")
        if not personnalises:
            self._listbox.insert("end", "   (aucun — bouton ＋ Nouveau)")
            self._listbox.itemconfig("end", foreground=theme.TEXT_DIM)
            self._lignes.append(('entete', None))
        for texte in personnalises:
            self._listbox.insert("end", f"   ★  {texte}")
            self._listbox.itemconfig("end", foreground=theme.BLUE)
            self._lignes.append(('perso', len(self._lignes_de('perso'))))

    def deselectionner(self) -> None:
        """@brief Efface la sélection courante de la liste."""
        self._listbox.selection_clear(0, "end")

    def _lignes_de(self, section: str) -> list:
        """@brief Lignes appartenant à une section donnée.

        @param section Nom de section ('integre', 'perso', 'entete').
        @return list Lignes (tuples) de cette section.
        """
        return [l for l in self._lignes if l[0] == section]

    def _entete(self, texte: str) -> None:
        """@brief Insère une ligne d'en-tête non sélectionnable.

        @param texte Libellé de l'en-tête.
        @return None
        """
        self._listbox.insert("end", f" — {texte} —")
        self._listbox.itemconfig("end", foreground=theme.TEXT_DIM)
        self._lignes.append(('entete', None))

    def _sur_selection(self, _=None):
        """@brief Gestionnaire d'événement de sélection : route vers le callback.

        @param _ Événement Tk (ignoré).
        @return None
        """
        sel = self._listbox.curselection()
        if not sel:
            return
        section, index = self._lignes[sel[0]]
        if section == 'entete':
            self._listbox.selection_clear(0, "end")
            return
        self._on_select_cb(section, index)


class BandeauEtat:
    """@brief Bandeau de mode du formulaire : nouveau / édition / lecture seule."""

    _STYLES = {
        'nouveau':  ("#14532d", "#4ade80"),   # fond vert sombre, texte vert
        'edition':  ("#1e3a8a", "#93c5fd"),   # fond bleu sombre, texte bleu
        'lecture':  (theme.SURFACE, theme.TEXT_MUTED),
    }

    def __init__(self, parent):
        """@brief Construit le bandeau d'état dans son widget parent.

        @param parent Widget parent.
        @return None
        """
        self._frame = ctk.CTkFrame(parent, corner_radius=theme.R["md"], height=34)
        self._frame.pack_propagate(False)
        self._label = ctk.CTkLabel(self._frame, text="",
                                   font=ui_kit.font("body", "bold"))
        self._label.pack(side="left", padx=12, pady=6)

    def pack(self, **kwargs):
        """@brief Délègue le placement pack() au frame interne.

        @param kwargs Options passées à CTkFrame.pack().
        @return None
        """
        self._frame.pack(**kwargs)

    def grid(self, **kwargs):
        self._frame.grid(**kwargs)

    def definir(self, mode: str, texte: str) -> None:
        """@brief Fixe le mode et le texte du bandeau.

        @param mode Mode d'affichage ('nouveau', 'edition', 'lecture').
        @param texte Texte à afficher.
        @return None
        """
        fond, couleur = self._STYLES[mode]
        self._frame.configure(fg_color=fond)
        self._label.configure(text=texte, text_color=couleur)


def ligne_aide(parent, texte: str) -> ctk.CTkLabel:
    """@brief Petite ligne d'aide grise sous un champ de formulaire.

    @param parent Widget parent.
    @param texte Texte d'aide à afficher.
    @return ctk.CTkLabel Le label créé.
    """
    label = ctk.CTkLabel(parent, text=texte,
                         font=ui_kit.font("caption"),
                         text_color=theme.TEXT_DIM, justify="left", anchor="w")
    label.pack(anchor="w", pady=(0, 8))
    return label


def lier_molette(zone_scrollable) -> None:
    """@brief Rend une zone défilable à la molette partout, enfants dynamiques compris.

    Rend `zone_scrollable` (un CTkScrollableFrame) défilable à la molette
    où que soit le curseur — y compris au-dessus d'enfants ajoutés après coup.

    @param zone_scrollable Le CTkScrollableFrame à rendre défilable.
    @return None

    CTkScrollableFrame ne lie la molette qu'au canvas et aux enfants présents à
    la construction ; les widgets ajoutés ensuite (lignes de broches, cases à
    cocher) ou des CTkEntry « avalent » l'évènement au lieu de le transmettre.
    On contourne en reliant le défilement récursivement sur la zone et tous ses
    descendants. Idempotent : on peut la rappeler après chaque ajout/retrait —
    les anciennes liaisons sont remplacées (pas accumulées), les nouvelles
    ajoutées.
    """
    canvas = getattr(zone_scrollable, "_parent_canvas", None)
    if canvas is None:
        return

    def _defiler(event):
        """@brief Traduit l'événement de molette en défilement vertical du canvas.

        @param event Événement Tk de molette.
        @return None
        """
        if getattr(event, "num", 0) == 4:        # Linux : molette haut
            canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", 0) == 5:      # Linux : molette bas
            canvas.yview_scroll(1, "units")
        else:                                    # Windows / macOS
            canvas.yview_scroll(int(-event.delta / 120), "units")

    def _relier(widget):
        """@brief Lie récursivement la molette sur un widget et ses enfants.

        @param widget Widget Tk/CTk à relier.
        @return None
        """
        widget.bind("<MouseWheel>", _defiler)    # Windows / macOS
        widget.bind("<Button-4>", _defiler)      # Linux
        widget.bind("<Button-5>", _defiler)      # Linux
        for enfant in widget.winfo_children():
            _relier(enfant)

    _relier(zone_scrollable)
