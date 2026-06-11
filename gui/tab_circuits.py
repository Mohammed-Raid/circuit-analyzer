import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from circuit_analyzer.composant import charger_bibliotheque as load_library
from circuit_analyzer.detecteur import NOMS_CIRCUITS
from custom_circuits.loader import (
    load_custom_circuits, save_custom_circuits,
    CONDITION_LABELS, CONDITION_DESCRIPTIONS,
)

from gui.theme import BG, CARD, CARD2, BORDER, TEXT, MUTED, BLUE, BLUE_D
from gui.widgets import ListeSectionnee, BandeauEtat, lier_molette

_BASE_NAMES = NOMS_CIRCUITS


class TabCircuits:
    """
    Onglet « Circuits » : patterns reconnus par l'analyseur.

    Même grammaire que l'onglet Composants : liste sectionnée à gauche
    (INTÉGRÉS détectés automatiquement / PERSONNALISÉS modifiables), bandeau
    d'état + formulaire à droite, bouton Sauvegarder épinglé en bas.

    Un circuit intégré est détecté par du code (pas de définition éditable) :
    le sélectionner passe le formulaire en mode lecture seule avec un message.
    """

    def __init__(self, parent):
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color=BG)
        self._custom: list = []
        self._current_idx: int | None = None       # index du perso en édition
        self._mode = 'nouveau'                      # nouveau | edition | lecture
        self._comp_vars: dict[str, tk.BooleanVar] = {}
        self._comp_boxes: list = []                 # CTkCheckBox composants
        self._cond_vars: dict[str, tk.BooleanVar] = {}
        self._cond_boxes: list = []                 # CTkCheckBox conditions
        self._etat_initial: tuple = ('', frozenset(), frozenset())
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
        ctk.CTkLabel(h, text="Circuits reconnus",
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color=TEXT).pack(side="left", pady=18)
        ctk.CTkLabel(h, text="Consulter les patterns intégrés, créer les vôtres",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=MUTED).pack(side="left", padx=14)

        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._liste = ListeSectionnee(
            body, titre="Circuits reconnus",
            on_select=self._sur_selection,
            on_new=self._nouveau,
            on_delete=self._supprimer,
        )
        self._liste.frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # ── Droite : bandeau + formulaire + pied épinglé
        right = ctk.CTkFrame(body, corner_radius=14, fg_color=CARD,
                             border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        self._bandeau = BandeauEtat(right)
        self._bandeau.grid(row=0, column=0, sticky="ew",
                           padx=14, pady=(14, 8))

        # Nom du circuit
        name_row = ctk.CTkFrame(right, fg_color="transparent")
        name_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        ctk.CTkLabel(name_row, text="Nom du circuit",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).pack(anchor="w")
        self._name_var = tk.StringVar()
        self._name_entry = ctk.CTkEntry(
            name_row, textvariable=self._name_var,
            height=40, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 13),
            fg_color=CARD2, border_color=BORDER, text_color=TEXT,
            placeholder_text="Ex: Filtre RLC série")
        self._name_entry.pack(fill="x", pady=(4, 0))

        # Note affichée pour les circuits intégrés (lecture seule)
        self._lecture_note = ctk.CTkLabel(
            right,
            text="Ce circuit est reconnu automatiquement par l'analyseur.\n"
                 "Sa définition est dans le code — rien à paramétrer ici.",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=MUTED, justify="left")

        # Deux colonnes : composants requis | conditions
        cols = ctk.CTkFrame(right, fg_color="transparent")
        cols.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 8))
        cols.grid_columnconfigure((0, 1), weight=1)
        cols.grid_rowconfigure(0, weight=1)
        self._cols = cols

        comp_col = ctk.CTkFrame(cols, corner_radius=10, fg_color=CARD2,
                                border_width=1, border_color=BORDER)
        comp_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(comp_col, text="⚙  Composants requis",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=BLUE).pack(anchor="w", padx=12, pady=(10, 6))
        self._comp_scroll = ctk.CTkScrollableFrame(
            comp_col, fg_color="transparent")
        self._comp_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        cond_col = ctk.CTkFrame(cols, corner_radius=10, fg_color=CARD2,
                                border_width=1, border_color=BORDER)
        cond_col.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(cond_col, text="✅  Conditions",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color="#10b981").pack(anchor="w", padx=12, pady=(10, 6))
        self._cond_scroll = ctk.CTkScrollableFrame(
            cond_col, fg_color="transparent")
        self._cond_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        self._build_conditions()

        # ── Pied épinglé : bouton Sauvegarder
        pied = ctk.CTkFrame(right, fg_color="transparent")
        pied.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 14))
        pied.grid_columnconfigure(0, weight=1)
        self._pied = pied
        self._btn_save = ctk.CTkButton(
            pied, text="💾  Sauvegarder ce circuit",
            height=42, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color="#15803d", hover_color="#16a34a",
            command=self._sauvegarder)
        self._btn_save.grid(row=0, column=0, sticky="ew")

    def _build_conditions(self):
        """Une case par condition, avec sa description courte en dessous."""
        for label in CONDITION_LABELS:
            var = tk.BooleanVar()
            self._cond_vars[label] = var
            box = ctk.CTkCheckBox(
                self._cond_scroll, text=label, variable=var,
                font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT,
                fg_color=BLUE_D, hover_color=BLUE, checkmark_color=TEXT)
            box.pack(anchor="w", padx=6, pady=(8, 0))
            self._cond_boxes.append(box)
            desc = CONDITION_DESCRIPTIONS.get(label, "")
            if desc:
                ctk.CTkLabel(self._cond_scroll, text=desc,
                             font=ctk.CTkFont("Segoe UI", 10),
                             text_color=MUTED, justify="left",
                             anchor="w").pack(anchor="w", padx=30, pady=(0, 4))
        lier_molette(self._cond_scroll)

    def _build_comp_checkboxes(self):
        for w in self._comp_scroll.winfo_children():
            w.destroy()
        self._comp_vars = {}
        self._comp_boxes = []
        for key, val in load_library().items():
            var = tk.BooleanVar()
            self._comp_vars[key] = var
            box = ctk.CTkCheckBox(
                self._comp_scroll, text=f"{key}  —  {val['name']}",
                variable=var, font=ctk.CTkFont("Segoe UI", 11),
                text_color=TEXT, fg_color=BLUE_D, hover_color=BLUE,
                checkmark_color=TEXT)
            box.pack(anchor="w", padx=4, pady=3)
            self._comp_boxes.append(box)
        lier_molette(self._comp_scroll)

    # ── Modes du formulaire ──────────────────────────────────────────────────

    def _definir_mode(self, mode: str, texte: str):
        self._mode = mode
        self._bandeau.definir(mode, texte)
        lecture = (mode == 'lecture')
        etat = "disabled" if lecture else "normal"
        self._name_entry.configure(state=etat)
        for box in self._comp_boxes:
            box.configure(state=etat)
        for box in self._cond_boxes:
            box.configure(state=etat)

        # Intégré (lecture) : on masque les colonnes et le bouton, on montre la
        # note ; sinon on remontre le formulaire éditable.
        if lecture:
            self._cols.grid_remove()
            self._btn_save.grid_remove()
            self._lecture_note.grid(row=2, column=0, sticky="nw",
                                    padx=18, pady=10)
        else:
            self._lecture_note.grid_remove()
            self._cols.grid(row=2, column=0, sticky="nsew",
                            padx=14, pady=(0, 8))
            self._btn_save.grid(row=0, column=0, sticky="ew")

    def _afficher_nouveau(self):
        self._current_idx = None
        self._remplir_formulaire('', set(), set())
        self._definir_mode('nouveau', "➕  Nouveau circuit personnalisé")
        self._prendre_snapshot()

    def _afficher_perso(self, idx: int):
        self._current_idx = idx
        c = self._custom[idx]
        self._remplir_formulaire(c.get("name", ""),
                                 set(c.get("components", [])),
                                 set(c.get("conditions", [])))
        self._definir_mode('edition', f"✏  Modification de ★ {c.get('name', '')}")
        self._prendre_snapshot()

    def _afficher_integre(self, nom: str):
        self._current_idx = None
        self._remplir_formulaire(nom, set(), set())
        self._definir_mode(
            'lecture', f"🔒  Circuit intégré « {nom} » — détecté automatiquement")
        self._prendre_snapshot()

    def _remplir_formulaire(self, nom: str, composants: set, conditions: set):
        # Réactiver avant d'écrire : un widget disabled ignore les set()
        self._name_entry.configure(state="normal")
        self._name_var.set(nom)
        for key, var in self._comp_vars.items():
            var.set(key in composants)
        for label, var in self._cond_vars.items():
            var.set(label in conditions)

    # ── Anti-perte de saisie ─────────────────────────────────────────────────

    def _etat_courant(self) -> tuple:
        return (self._name_var.get().strip(),
                frozenset(k for k, v in self._comp_vars.items() if v.get()),
                frozenset(l for l, v in self._cond_vars.items() if v.get()))

    def _prendre_snapshot(self):
        self._etat_initial = self._etat_courant()

    def _confirmer_abandon(self) -> bool:
        if self._mode == 'lecture' or self._etat_courant() == self._etat_initial:
            return True
        return messagebox.askyesno(
            "Modifications non sauvegardées",
            "Le formulaire contient des modifications non sauvegardées.\n"
            "Les abandonner ?")

    # ── Données ──────────────────────────────────────────────────────────────

    def _load(self):
        self._build_comp_checkboxes()
        self._custom = load_custom_circuits()
        self._liste.remplir(
            integres=list(_BASE_NAMES),
            personnalises=[c.get("name", "") for c in self._custom],
        )

    def refresh_component_list(self):
        # La bibliothèque a changé : reconstruire les cases en gardant les choix.
        coches = {k for k, v in self._comp_vars.items() if v.get()}
        self._build_comp_checkboxes()
        for k, v in self._comp_vars.items():
            v.set(k in coches)
        # Réappliquer l'état (lecture désactive les cases neuves)
        if self._mode == 'lecture':
            for box in self._comp_boxes:
                box.configure(state="disabled")

    # ── Actions ──────────────────────────────────────────────────────────────

    def _sur_selection(self, section: str, index: int):
        if not self._confirmer_abandon():
            self._liste.deselectionner()
            return
        if section == 'integre':
            self._afficher_integre(list(_BASE_NAMES)[index])
        else:
            self._afficher_perso(index)

    def _nouveau(self):
        if not self._confirmer_abandon():
            return
        self._liste.deselectionner()
        self._afficher_nouveau()

    def _supprimer(self):
        if self._mode != 'edition' or self._current_idx is None:
            messagebox.showinfo(
                "Info", "Sélectionnez d'abord un circuit personnalisé (★).\n"
                        "Les circuits intégrés ne peuvent pas être supprimés.")
            return
        nom = self._custom[self._current_idx].get("name", "")
        if messagebox.askyesno("Confirmer", f"Supprimer '{nom}' ?"):
            self._custom.pop(self._current_idx)
            save_custom_circuits(self._custom)
            self._load()
            self._afficher_nouveau()

    def _sauvegarder(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showerror("Erreur", "Nom obligatoire.")
            return
        comps = [k for k, v in self._comp_vars.items() if v.get()]
        if not comps:
            messagebox.showerror("Erreur",
                                 "Sélectionnez au moins un composant.")
            return
        conds = [l for l, v in self._cond_vars.items() if v.get()]
        c = {"name": name, "components": comps, "conditions": conds}
        if self._current_idx is not None:
            self._custom[self._current_idx] = c
            idx = self._current_idx
        else:
            self._custom.append(c)
            idx = len(self._custom) - 1
        save_custom_circuits(self._custom)
        self._load()
        self._afficher_perso(idx)
        messagebox.showinfo("Succès", f"'{name}' sauvegardé.")
