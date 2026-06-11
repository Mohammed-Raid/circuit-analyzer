import json
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox

from circuit_analyzer.composant import (
    TYPES_COMPOSANTS as COMPONENT_TYPES, chemin_bibliotheque,
)
from gui.theme import BG, CARD, CARD2, BORDER, TEXT, MUTED
from gui.widgets import ListeSectionnee, BandeauEtat, ligne_aide, lier_molette


class TabComponents:
    """
    Onglet « Composants » : bibliothèque des types (R, C, Q…).

    Gauche : liste sectionnée (types intégrés consultables / personnalisés
    modifiables). Droite : formulaire scrollable avec bandeau d'état
    (nouveau / édition / lecture seule) et bouton Sauvegarder épinglé en bas.
    """

    def __init__(self, parent, on_save=None):
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color=BG)
        self._on_save = on_save
        self._custom: dict = {}
        self._current_key: str | None = None       # clé du perso en édition
        self._mode = 'nouveau'                     # nouveau | edition | lecture
        self._pin_lignes: list = []                # [(StringVar, CTkEntry)]
        self._etat_initial: tuple = ('', '', ())   # snapshot anti-perte
        self._build()
        self._load()
        self._afficher_nouveau()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self):
        header = ctk.CTkFrame(self.frame, fg_color=CARD,
                              corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        h = ctk.CTkFrame(header, fg_color="transparent")
        h.pack(fill="both", expand=True, padx=28)
        ctk.CTkLabel(h, text="Bibliothèque de composants",
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color=TEXT).pack(side="left", pady=18)
        ctk.CTkLabel(h, text="Consulter les types intégrés, créer les vôtres",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=MUTED).pack(side="left", padx=14)

        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._liste = ListeSectionnee(
            body, titre="Types de composants",
            on_select=self._sur_selection,
            on_new=self._nouveau,
            on_delete=self._supprimer,
        )
        self._liste.frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # ── Droite : bandeau + formulaire scrollable + pied épinglé
        right = ctk.CTkFrame(body, corner_radius=14, fg_color=CARD,
                             border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew")

        self._bandeau = BandeauEtat(right)
        self._bandeau.pack(fill="x", padx=14, pady=(14, 8))

        # Tout le formulaire scrolle : ajouter 40 broches ne pousse plus
        # le bouton Sauvegarder hors écran.
        form = ctk.CTkScrollableFrame(right, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=14, pady=(0, 4))
        self._form = form

        ctk.CTkLabel(form, text="Préfixe",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).pack(anchor="w")
        pfx_row = ctk.CTkFrame(form, fg_color="transparent")
        pfx_row.pack(fill="x", pady=(4, 2))
        self._prefix_var = tk.StringVar()
        self._prefix_var.trace_add("write", self._valider_prefixe)
        self._prefix_entry = ctk.CTkEntry(
            pfx_row, textvariable=self._prefix_var,
            width=110, height=40, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            fg_color=CARD2, border_color=BORDER,
            text_color="#60a5fa", placeholder_text="IC")
        self._prefix_entry.pack(side="left")
        self._pfx_warn = ctk.CTkLabel(pfx_row, text="",
                                      font=ctk.CTkFont("Segoe UI", 11),
                                      text_color="#f87171")
        self._pfx_warn.pack(side="left", padx=10)
        ligne_aide(form, "Lettres en début de référence dans la netlist : "
                         "R1 -> préfixe R, IC3 -> préfixe IC.")

        ctk.CTkLabel(form, text="Nom complet",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).pack(anchor="w")
        self._name_var = tk.StringVar()
        self._name_entry = ctk.CTkEntry(
            form, textvariable=self._name_var,
            height=40, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color=CARD2, border_color=BORDER,
            text_color=TEXT, placeholder_text="Ex: Circuit intégré")
        self._name_entry.pack(fill="x", pady=(4, 2))
        ligne_aide(form, "Nom lisible affiché dans les listes et le rapport.")

        ctk.CTkLabel(form, text="Broches",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).pack(anchor="w")
        pins_card = ctk.CTkFrame(form, corner_radius=10, fg_color=CARD2,
                                 border_width=1, border_color=BORDER)
        pins_card.pack(fill="x", pady=(4, 6))
        self._pins_inner = ctk.CTkFrame(pins_card, fg_color="transparent")
        self._pins_inner.pack(fill="x", padx=10, pady=10)

        pin_btns = ctk.CTkFrame(form, fg_color="transparent")
        pin_btns.pack(fill="x", pady=(0, 2))
        self._btn_add_pin = ctk.CTkButton(
            pin_btns, text="＋ Broche", width=110, height=32,
            corner_radius=6, font=ctk.CTkFont("Segoe UI", 11),
            fg_color=CARD, hover_color="#263347",
            border_width=1, border_color=BORDER,
            command=self._ajouter_broche)
        self._btn_add_pin.pack(side="left", padx=(0, 6))
        self._btn_del_pin = ctk.CTkButton(
            pin_btns, text="− Broche", width=110, height=32,
            corner_radius=6, font=ctk.CTkFont("Segoe UI", 11),
            fg_color=CARD, hover_color="#263347",
            border_width=1, border_color=BORDER,
            command=self._retirer_broche)
        self._btn_del_pin.pack(side="left")
        ligne_aide(form, "Noms des broches dans l'ordre de la netlist "
                         "(ex : B, C, E pour un transistor).")

        # ── Pied épinglé (hors scroll) : toujours visible
        pied = ctk.CTkFrame(right, fg_color="transparent")
        pied.pack(fill="x", padx=14, pady=(0, 14))
        self._btn_save = ctk.CTkButton(
            pied, text="💾  Sauvegarder le composant",
            height=42, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color="#15803d", hover_color="#16a34a",
            command=self._sauvegarder)
        self._btn_dupliquer = ctk.CTkButton(
            pied, text="⧉  Dupliquer comme personnalisé",
            height=42, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color="#1d4ed8", hover_color="#3b82f6",
            command=self._dupliquer)
        self._btn_save.pack(fill="x")

        # La molette défile le formulaire même au-dessus des champs et des
        # lignes de broches (rappelée à chaque ajout/retrait de broche).
        lier_molette(self._form)

    # ── Modes du formulaire ──────────────────────────────────────────────────

    def _definir_mode(self, mode: str, texte: str):
        self._mode = mode
        self._bandeau.definir(mode if mode != 'edition' else 'edition', texte)
        lecture = (mode == 'lecture')
        etat = "disabled" if lecture else "normal"
        self._prefix_entry.configure(state=etat)
        self._name_entry.configure(state=etat)
        self._btn_add_pin.configure(state=etat)
        self._btn_del_pin.configure(state=etat)
        for _, entry in self._pin_lignes:
            entry.configure(state=etat)
        self._btn_save.pack_forget()
        self._btn_dupliquer.pack_forget()
        if lecture:
            self._btn_dupliquer.pack(fill="x")
        else:
            self._btn_save.pack(fill="x")

    def _afficher_nouveau(self):
        self._current_key = None
        self._remplir_formulaire('', '', [''])
        self._definir_mode('nouveau', "➕  Nouveau type de composant")
        self._prendre_snapshot()

    def _afficher_perso(self, key: str):
        self._current_key = key
        v = self._custom[key]
        self._remplir_formulaire(key, v.get("name", ""), v.get("pins", []))
        self._definir_mode('edition', f"✏  Modification de ★ {key}")
        self._prendre_snapshot()

    def _afficher_integre(self, key: str):
        self._current_key = None
        v = COMPONENT_TYPES[key]
        self._remplir_formulaire(key, v["name"], v["pins"])
        self._definir_mode('lecture',
                           f"🔒  Type intégré {key} — lecture seule")
        self._prendre_snapshot()

    def _remplir_formulaire(self, prefixe: str, nom: str, broches: list):
        # Réactiver avant d'écrire : un Entry disabled ignore les set()
        self._prefix_entry.configure(state="normal")
        self._name_entry.configure(state="normal")
        self._prefix_var.set(prefixe)
        self._name_var.set(nom)
        for w in self._pins_inner.winfo_children():
            w.destroy()
        self._pin_lignes = []
        for b in broches:
            self._ajouter_broche(b)

    # ── Anti-perte de saisie ─────────────────────────────────────────────────

    def _etat_courant(self) -> tuple:
        return (self._prefix_var.get().strip(),
                self._name_var.get().strip(),
                tuple(v.get().strip() for v, _ in self._pin_lignes))

    def _prendre_snapshot(self):
        self._etat_initial = self._etat_courant()

    def _confirmer_abandon(self) -> bool:
        """Vrai si on peut quitter le formulaire (rien à perdre, ou confirmé)."""
        if self._mode == 'lecture' or self._etat_courant() == self._etat_initial:
            return True
        return messagebox.askyesno(
            "Modifications non sauvegardées",
            "Le formulaire contient des modifications non sauvegardées.\n"
            "Les abandonner ?")

    # ── Broches ──────────────────────────────────────────────────────────────

    def _ajouter_broche(self, valeur=""):
        n = len(self._pin_lignes) + 1
        row = ctk.CTkFrame(self._pins_inner, fg_color="transparent")
        row.pack(anchor="w", pady=2)
        ctk.CTkLabel(row, text=f"{n}.",
                     width=24, font=ctk.CTkFont("Segoe UI", 10),
                     text_color=MUTED).pack(side="left")
        var = tk.StringVar(value=valeur)
        entry = ctk.CTkEntry(row, textvariable=var,
                             width=140, height=30, corner_radius=6,
                             font=ctk.CTkFont("Consolas", 11),
                             fg_color=CARD, border_color=BORDER,
                             text_color="#60a5fa",
                             placeholder_text=f"Broche {n}")
        entry.pack(side="left")
        self._pin_lignes.append((var, entry))
        # Nouvelle ligne → la relier à la molette du formulaire scrollable.
        lier_molette(self._form)

    def _retirer_broche(self):
        if self._pin_lignes:
            self._pin_lignes.pop()
            children = self._pins_inner.winfo_children()
            if children:
                children[-1].destroy()

    # ── Validation ───────────────────────────────────────────────────────────

    def _valider_prefixe(self, *_):
        p = self._prefix_var.get().strip().upper()
        if self._mode == 'lecture':
            self._pfx_warn.configure(text="")
        elif p in COMPONENT_TYPES:
            self._pfx_warn.configure(text="⚠  Préfixe réservé (type intégré)")
        elif p and p in self._custom and p != self._current_key:
            self._pfx_warn.configure(text="⚠  Déjà utilisé")
        else:
            self._pfx_warn.configure(text="")

    # ── Données ──────────────────────────────────────────────────────────────

    def _load(self):
        self._custom = {}
        chemin = chemin_bibliotheque()
        if chemin.exists():
            with open(chemin, encoding="utf-8") as f:
                data = json.load(f)
            self._custom = {k: v for k, v in data.items()
                            if k not in COMPONENT_TYPES}
        self._liste.remplir(
            integres=[f"{k}  —  {v['name']}"
                      for k, v in COMPONENT_TYPES.items()],
            personnalises=[f"{k}  —  {v.get('name', '')}"
                           for k, v in self._custom.items()],
        )

    def _ecrire(self):
        with open(chemin_bibliotheque(), "w", encoding="utf-8") as f:
            json.dump(self._custom, f, ensure_ascii=False, indent=2)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _sur_selection(self, section: str, index: int):
        if not self._confirmer_abandon():
            self._liste.deselectionner()
            return
        if section == 'integre':
            self._afficher_integre(list(COMPONENT_TYPES.keys())[index])
        else:
            self._afficher_perso(list(self._custom.keys())[index])

    def _nouveau(self):
        if not self._confirmer_abandon():
            return
        self._liste.deselectionner()
        self._afficher_nouveau()

    def _dupliquer(self):
        """Préremplit un nouveau personnalisé à partir du type affiché."""
        nom = self._name_var.get()
        broches = [v.get() for v, _ in self._pin_lignes]
        self._liste.deselectionner()
        self._current_key = None
        self._remplir_formulaire('', f"{nom} (copie)", broches)
        self._definir_mode('nouveau',
                           "➕  Nouveau type (copie) — choisir un préfixe")
        self._prendre_snapshot()

    def _supprimer(self):
        if self._mode != 'edition' or not self._current_key:
            messagebox.showinfo(
                "Info", "Sélectionnez d'abord un composant personnalisé (★).\n"
                        "Les types intégrés ne peuvent pas être supprimés.")
            return
        if messagebox.askyesno("Confirmer",
                               f"Supprimer '{self._current_key}' ?"):
            self._custom.pop(self._current_key, None)
            self._ecrire()
            self._load()
            self._afficher_nouveau()
            # Comme à la sauvegarde : prévenir l'onglet Circuits que la
            # bibliothèque a changé, sinon le composant supprimé reste proposé.
            if self._on_save:
                self._on_save()

    def _sauvegarder(self):
        prefix = self._prefix_var.get().strip().upper()
        name   = self._name_var.get().strip()
        pins   = [v.get().strip()
                  for v, _ in self._pin_lignes if v.get().strip()]
        if not prefix:
            messagebox.showerror("Erreur", "Préfixe obligatoire.")
            return
        if prefix in COMPONENT_TYPES:
            messagebox.showerror(
                "Erreur", f"'{prefix}' est un type intégré réservé.")
            return
        if not pins:
            messagebox.showerror("Erreur", "Au moins une broche requise.")
            return
        if self._current_key and self._current_key != prefix:
            self._custom.pop(self._current_key, None)
        self._custom[prefix] = {"name": name, "pins": pins}
        self._ecrire()
        self._load()
        self._afficher_perso(prefix)
        if self._on_save:
            self._on_save()
        messagebox.showinfo("Succès", f"'{prefix}' sauvegardé.")

    def refresh_component_list(self):
        self._load()
