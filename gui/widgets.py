"""
widgets.py — Briques d'interface partagées par les onglets Composants et Circuits.

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

from gui.theme import CARD, CARD2, BORDER, TEXT, MUTED, BLUE, BLUE_D

_GRIS_INTEGRE = "#94a3b8"   # éléments intégrés : consultables, non modifiables
_BLEU_PERSO   = "#60a5fa"   # éléments personnalisés (étoile)
_GRIS_ENTETE  = "#475569"   # en-têtes de section


class ListeSectionnee:
    """
    Panneau de liste à sections pour le côté gauche des onglets.

    Usage :
        panneau = ListeSectionnee(parent, titre="Liste des circuits",
                                  on_select=cb, on_new=cb, on_delete=cb)
        panneau.frame.grid(...)
        panneau.remplir(integres=["R — Résistance", ...],
                        personnalises=["Mon circuit", ...])

    on_select reçoit (section, index) avec section dans {'integre', 'perso'}.
    """

    def __init__(self, parent, titre: str, on_select, on_new, on_delete):
        self._on_select_cb = on_select
        # rangée listbox -> ('entete', None) | ('integre', i) | ('perso', i)
        self._lignes: list[tuple] = []

        self.frame = ctk.CTkFrame(parent, corner_radius=14, fg_color=CARD,
                                  border_width=1, border_color=BORDER)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.frame, text=titre,
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=TEXT).grid(row=0, column=0, sticky="w",
                                           padx=14, pady=(14, 6))

        lb_f = ctk.CTkFrame(self.frame, fg_color=CARD2, corner_radius=8)
        lb_f.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self._listbox = tk.Listbox(
            lb_f, width=32, height=24,
            bg=CARD2, fg=MUTED,
            selectbackground=BLUE_D, selectforeground=TEXT,
            font=("Segoe UI", 11), relief="flat", bd=0,
            activestyle="none", highlightthickness=0,
        )
        sb = tk.Scrollbar(lb_f, command=self._listbox.yview,
                          bg=CARD, troughcolor=CARD2)
        self._listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._listbox.pack(fill="both", expand=True, padx=6, pady=6)
        self._listbox.bind("<<ListboxSelect>>", self._sur_selection)

        br = ctk.CTkFrame(self.frame, fg_color="transparent")
        br.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 12))
        ctk.CTkButton(br, text="＋  Nouveau", height=36,
                      corner_radius=8, font=ctk.CTkFont("Segoe UI", 12),
                      fg_color=BLUE_D, hover_color=BLUE,
                      command=on_new).pack(side="left", expand=True,
                                           padx=(0, 4))
        ctk.CTkButton(br, text="🗑  Supprimer", height=36,
                      corner_radius=8, font=ctk.CTkFont("Segoe UI", 12),
                      fg_color="#7f1d1d", hover_color="#991b1b",
                      command=on_delete).pack(side="left", expand=True)

    def remplir(self, integres: list[str], personnalises: list[str]) -> None:
        """(Re)peuple la liste : section intégrés puis section personnalisés."""
        self._listbox.delete(0, "end")
        self._lignes = []

        self._entete(f"INTÉGRÉS ({len(integres)}) — consultables")
        for texte in integres:
            self._listbox.insert("end", f"   {texte}")
            self._listbox.itemconfig("end", foreground=_GRIS_INTEGRE)
            self._lignes.append(('integre', len(self._lignes_de('integre'))))

        self._entete(f"PERSONNALISÉS ({len(personnalises)}) — modifiables")
        if not personnalises:
            self._listbox.insert("end", "   (aucun — bouton ＋ Nouveau)")
            self._listbox.itemconfig("end", foreground=_GRIS_ENTETE)
            self._lignes.append(('entete', None))
        for texte in personnalises:
            self._listbox.insert("end", f"   ★  {texte}")
            self._listbox.itemconfig("end", foreground=_BLEU_PERSO)
            self._lignes.append(('perso', len(self._lignes_de('perso'))))

    def deselectionner(self) -> None:
        self._listbox.selection_clear(0, "end")

    def _lignes_de(self, section: str) -> list:
        return [l for l in self._lignes if l[0] == section]

    def _entete(self, texte: str) -> None:
        self._listbox.insert("end", f" — {texte} —")
        self._listbox.itemconfig("end", foreground=_GRIS_ENTETE)
        self._lignes.append(('entete', None))

    def _sur_selection(self, _=None):
        sel = self._listbox.curselection()
        if not sel:
            return
        section, index = self._lignes[sel[0]]
        if section == 'entete':
            self._listbox.selection_clear(0, "end")
            return
        self._on_select_cb(section, index)


class BandeauEtat:
    """Bandeau de mode du formulaire : nouveau / édition / lecture seule."""

    _STYLES = {
        'nouveau':  ("#14532d", "#4ade80"),   # fond vert sombre, texte vert
        'edition':  ("#1e3a8a", "#93c5fd"),   # fond bleu sombre, texte bleu
        'lecture':  ("#374151", "#d1d5db"),   # fond gris, texte gris clair
    }

    def __init__(self, parent):
        self._frame = ctk.CTkFrame(parent, corner_radius=8, height=34)
        self._frame.pack_propagate(False)
        self._label = ctk.CTkLabel(self._frame, text="",
                                   font=ctk.CTkFont("Segoe UI", 12, "bold"))
        self._label.pack(side="left", padx=12, pady=6)

    def pack(self, **kwargs):
        self._frame.pack(**kwargs)

    def grid(self, **kwargs):
        self._frame.grid(**kwargs)

    def definir(self, mode: str, texte: str) -> None:
        fond, couleur = self._STYLES[mode]
        self._frame.configure(fg_color=fond)
        self._label.configure(text=texte, text_color=couleur)


def ligne_aide(parent, texte: str) -> ctk.CTkLabel:
    """Petite ligne d'aide grise sous un champ de formulaire."""
    label = ctk.CTkLabel(parent, text=texte,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=MUTED, justify="left", anchor="w")
    label.pack(anchor="w", pady=(0, 8))
    return label


def lier_molette(zone_scrollable) -> None:
    """Rend `zone_scrollable` (un CTkScrollableFrame) défilable à la molette
    où que soit le curseur — y compris au-dessus d'enfants ajoutés après coup.

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
        if getattr(event, "num", 0) == 4:        # Linux : molette haut
            canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", 0) == 5:      # Linux : molette bas
            canvas.yview_scroll(1, "units")
        else:                                    # Windows / macOS
            canvas.yview_scroll(int(-event.delta / 120), "units")

    def _relier(widget):
        widget.bind("<MouseWheel>", _defiler)    # Windows / macOS
        widget.bind("<Button-4>", _defiler)      # Linux
        widget.bind("<Button-5>", _defiler)      # Linux
        for enfant in widget.winfo_children():
            _relier(enfant)

    _relier(zone_scrollable)
