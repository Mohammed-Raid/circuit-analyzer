"""
@file tab_components.py
@brief Onglet « Composants » : consultation des types intégrés et édition des types personnalisés.
"""
import json
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox

from circuit_analyzer.composant import (
    TYPES_COMPOSANTS as COMPONENT_TYPES, chemin_bibliotheque,
)
from gui.theme import BG, CARD, CARD2, TEXT, TEXT_MUTED, BLUE, ERROR
from gui import ui_kit
from gui.widgets import ListeSectionnee, BandeauEtat, ligne_aide, lier_molette


class TabComponents:
    """
    @brief Onglet « Composants » : bibliothèque des types (R, C, Q…).

    Gauche : liste sectionnée (types intégrés consultables / personnalisés
    modifiables). Droite : formulaire scrollable avec bandeau d'état
    (nouveau / édition / lecture seule) et bouton Sauvegarder épinglé en bas.
    """

    def __init__(self, parent, on_save=None):
        """@brief Construit l'onglet, charge la bibliothèque et affiche le mode « nouveau ».

        @param parent Widget parent (zone de contenu).
        @param on_save Callback appelé après sauvegarde/suppression (rafraîchit l'onglet Circuits).
        """
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
        """@brief Construit l'en-tête, la liste sectionnée et le formulaire d'édition."""
        header = ctk.CTkFrame(self.frame, fg_color=CARD,
                              corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        h = ctk.CTkFrame(header, fg_color="transparent")
        h.pack(fill="both", expand=True, padx=28)
        ctk.CTkLabel(h, text="Bibliothèque de composants",
                     font=ui_kit.font("display"),
                     text_color=TEXT).pack(side="left", pady=18)
        ctk.CTkLabel(h, text="Consulter les types intégrés, créer les vôtres",
                     font=ui_kit.font("body"),
                     text_color=TEXT_MUTED).pack(side="left", padx=14, pady=18)

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
        right = ui_kit.Card(body)
        right.grid(row=0, column=1, sticky="nsew")

        self._bandeau = BandeauEtat(right)
        self._bandeau.pack(fill="x", padx=14, pady=(14, 8))

        # Tout le formulaire scrolle : ajouter 40 broches ne pousse plus
        # le bouton Sauvegarder hors écran.
        form = ctk.CTkScrollableFrame(right, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=14, pady=(0, 4))
        self._form = form

        ui_kit.SectionHeader(form, "Préfixe").pack(anchor="w")
        pfx_row = ctk.CTkFrame(form, fg_color="transparent")
        pfx_row.pack(fill="x", pady=(4, 2))
        self._prefix_var = tk.StringVar()
        self._prefix_var.trace_add("write", self._valider_prefixe)
        self._prefix_entry = ui_kit.Field(
            pfx_row, textvariable=self._prefix_var,
            placeholder="IC", width=110, height=40,
            font=ui_kit.font("subtitle", "bold"),
            text_color=BLUE)
        self._prefix_entry.pack(side="left")
        self._pfx_warn = ctk.CTkLabel(pfx_row, text="",
                                      font=ui_kit.font("caption"),
                                      text_color=ERROR)
        self._pfx_warn.pack(side="left", padx=10)
        ligne_aide(form, "Lettres en début de référence dans la netlist : "
                         "R1 -> préfixe R, IC3 -> préfixe IC.")

        ui_kit.SectionHeader(form, "Nom complet").pack(anchor="w")
        self._name_var = tk.StringVar()
        self._name_entry = ui_kit.Field(
            form, textvariable=self._name_var,
            placeholder="Ex: Circuit intégré", height=40)
        self._name_entry.pack(fill="x", pady=(4, 2))
        ligne_aide(form, "Nom lisible affiché dans les listes et le rapport.")

        ui_kit.SectionHeader(form, "Broches").pack(anchor="w")
        pins_card = ui_kit.Card(form, fg_color=CARD2)
        pins_card.pack(fill="x", pady=(4, 6))
        self._pins_inner = ctk.CTkFrame(pins_card, fg_color="transparent")
        self._pins_inner.pack(fill="x", padx=10, pady=10)

        pin_btns = ctk.CTkFrame(form, fg_color="transparent")
        pin_btns.pack(fill="x", pady=(0, 2))
        self._btn_add_pin = ui_kit.SecondaryButton(
            pin_btns, "Ajouter une broche", self._ajouter_broche,
            icon_name="plus", width=170, height=32)
        self._btn_add_pin.pack(side="left", padx=(0, 6))
        self._btn_del_pin = ui_kit.SecondaryButton(
            pin_btns, "Retirer la broche", self._retirer_broche,
            icon_name="x", width=170, height=32)
        self._btn_del_pin.pack(side="left")
        ligne_aide(form, "Noms des broches dans l'ordre de la netlist "
                         "(ex : B, C, E pour un transistor).")

        # ── Pied épinglé (hors scroll) : toujours visible
        pied = ctk.CTkFrame(right, fg_color="transparent")
        pied.pack(fill="x", padx=14, pady=(0, 14))
        self._btn_save = ui_kit.PrimaryButton(
            pied, "Sauvegarder le composant", self._sauvegarder,
            icon_name="save", height=42)
        self._btn_dupliquer = ui_kit.SecondaryButton(
            pied, "Dupliquer comme personnalisé", self._dupliquer,
            icon_name="copy", height=42)
        self._btn_save.pack(fill="x")

        # La molette défile le formulaire même au-dessus des champs et des
        # lignes de broches (rappelée à chaque ajout/retrait de broche).
        lier_molette(self._form)

    # ── Modes du formulaire ──────────────────────────────────────────────────

    def _definir_mode(self, mode: str, texte: str):
        """@brief Bascule le formulaire en mode nouveau / édition / lecture seule.

        @param mode Mode cible ('nouveau', 'edition', 'lecture').
        @param texte Texte du bandeau d'état.
        @return None
        """
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
        """@brief Affiche un formulaire vierge en mode « nouveau »."""
        self._current_key = None
        self._remplir_formulaire('', '', [''])
        self._definir_mode('nouveau', "➕  Nouveau type de composant")
        self._prendre_snapshot()

    def _afficher_perso(self, key: str):
        """@brief Affiche un type personnalisé en mode édition.

        @param key Préfixe du type personnalisé.
        @return None
        """
        self._current_key = key
        v = self._custom[key]
        self._remplir_formulaire(key, v.get("name", ""), v.get("pins", []))
        self._definir_mode('edition', f"✏  Modification de ★ {key}")
        self._prendre_snapshot()

    def _afficher_integre(self, key: str):
        """@brief Affiche un type intégré en lecture seule.

        @param key Préfixe du type intégré.
        @return None
        """
        self._current_key = None
        v = COMPONENT_TYPES[key]
        self._remplir_formulaire(key, v["name"], v["pins"])
        self._definir_mode('lecture',
                           f"🔒  Type intégré {key} — lecture seule")
        self._prendre_snapshot()

    def _remplir_formulaire(self, prefixe: str, nom: str, broches: list):
        """@brief Remplit les champs du formulaire (préfixe, nom, broches).

        @param prefixe Préfixe du type.
        @param nom Nom complet du type.
        @param broches Liste des noms de broches.
        @return None
        """
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
        """@brief Instantané (préfixe, nom, broches) de l'état courant du formulaire.
        @return tuple État courant, pour détecter les modifications non sauvegardées.
        """
        return (self._prefix_var.get().strip(),
                self._name_var.get().strip(),
                tuple(v.get().strip() for v, _ in self._pin_lignes))

    def _prendre_snapshot(self):
        """@brief Mémorise l'état courant comme référence anti-perte de saisie."""
        self._etat_initial = self._etat_courant()

    def _confirmer_abandon(self) -> bool:
        """@brief Vrai si on peut quitter le formulaire (rien à perdre, ou confirmé).
        @return bool True si l'abandon est autorisé.
        """
        if self._mode == 'lecture' or self._etat_courant() == self._etat_initial:
            return True
        return messagebox.askyesno(
            "Modifications non sauvegardées",
            "Le formulaire contient des modifications non sauvegardées.\n"
            "Les abandonner ?")

    # ── Broches ──────────────────────────────────────────────────────────────

    def _ajouter_broche(self, valeur=""):
        """@brief Ajoute une ligne de saisie de broche au formulaire.

        @param valeur Valeur initiale de la broche (vide par défaut).
        @return None
        """
        n = len(self._pin_lignes) + 1
        row = ctk.CTkFrame(self._pins_inner, fg_color="transparent")
        row.pack(anchor="w", pady=2)
        ctk.CTkLabel(row, text=f"{n}.",
                     width=24, font=ui_kit.font("caption"),
                     text_color=TEXT_MUTED).pack(side="left")
        var = tk.StringVar(value=valeur)
        entry = ui_kit.Field(
            row, textvariable=var,
            placeholder=f"Broche {n}",
            width=140, height=30, corner_radius=6,
            font=ctk.CTkFont("Consolas", 11),
            text_color=BLUE)
        entry.pack(side="left")
        self._pin_lignes.append((var, entry))
        # Nouvelle ligne → la relier à la molette du formulaire scrollable.
        lier_molette(self._form)

    def _retirer_broche(self):
        """@brief Retire la dernière ligne de broche du formulaire."""
        if self._pin_lignes:
            self._pin_lignes.pop()
            children = self._pins_inner.winfo_children()
            if children:
                children[-1].destroy()

    # ── Validation ───────────────────────────────────────────────────────────

    def _valider_prefixe(self, *_):
        """@brief Affiche un avertissement si le préfixe saisi est réservé ou déjà utilisé."""
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
        """@brief Charge la bibliothèque (types intégrés + personnalisés) et peuple la liste."""
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
        """@brief Écrit les types personnalisés dans le fichier de bibliothèque (JSON UTF-8)."""
        with open(chemin_bibliotheque(), "w", encoding="utf-8") as f:
            json.dump(self._custom, f, ensure_ascii=False, indent=2)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _sur_selection(self, section: str, index: int):
        """@brief Gère la sélection d'un type dans la liste (intégré ou personnalisé).

        @param section Section sélectionnée ('integre' ou 'perso').
        @param index Index dans la section.
        @return None
        """
        if not self._confirmer_abandon():
            self._liste.deselectionner()
            return
        if section == 'integre':
            self._afficher_integre(list(COMPONENT_TYPES.keys())[index])
        else:
            self._afficher_perso(list(self._custom.keys())[index])

    def _nouveau(self):
        """@brief Démarre la création d'un nouveau type (après confirmation d'abandon)."""
        if not self._confirmer_abandon():
            return
        self._liste.deselectionner()
        self._afficher_nouveau()

    def _dupliquer(self):
        """@brief Préremplit un nouveau type personnalisé à partir du type affiché."""
        nom = self._name_var.get()
        broches = [v.get() for v, _ in self._pin_lignes]
        self._liste.deselectionner()
        self._current_key = None
        self._remplir_formulaire('', f"{nom} (copie)", broches)
        self._definir_mode('nouveau',
                           "➕  Nouveau type (copie) — choisir un préfixe")
        self._prendre_snapshot()

    def _supprimer(self):
        """@brief Supprime le type personnalisé en cours d'édition (avec confirmation)."""
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
        """@brief Valide et enregistre le type personnalisé saisi (préfixe, nom, broches)."""
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
        """@brief Recharge la bibliothèque (appelé quand un autre onglet la modifie)."""
        self._load()
