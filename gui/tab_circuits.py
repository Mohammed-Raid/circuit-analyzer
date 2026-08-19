"""
@file tab_circuits.py
@brief Onglet « Circuits » : patterns reconnus (intégrés consultables, personnalisés éditables).
"""
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from circuit_analyzer.composant import charger_bibliotheque as load_library
from circuit_analyzer.detecteur import NOMS_CIRCUITS
from custom_circuits.loader import (
    load_custom_circuits, save_custom_circuits,
    CONDITION_LABELS, CONDITION_DESCRIPTIONS,
    CONDITION_GROUPS, condition_display,
    libelle_nombre_composants_ilot,
)

from gui.theme import (BG, CARD, CARD2, TEXT, TEXT_MUTED, TEXT_DIM,
                       BLUE, BLUE_PRESS, R)
from gui import ui_kit
from gui.widgets import lier_molette

_BASE_NAMES = NOMS_CIRCUITS

# Styles du bandeau d'état du formulaire (fond, couleur du texte)
_BANDEAU_STYLES = {
    'nouveau':  ("#14532d", "#4ade80"),
    'edition':  ("#1e3a8a", "#93c5fd"),
    'lecture':  (CARD2, TEXT_MUTED),
    # [MODIF 2026-08-18] cf. _est_avance : pattern perso créé par l'assistant
    # avec nom verrouillé / condition générique -- lecture seule ICI mais
    # bien "à soi" (supprimable), distinct visuellement d'un intégré verrouillé.
    'lecture_perso': ("#78350f", "#fbbf24"),
}

# Texte fixe de _lecture_note pour un circuit INTÉGRÉ (restauré à chaque
# sélection d'intégré -- _afficher_perso le réécrit pour un pattern avancé).
_NOTE_INTEGRE = ("Ce circuit est reconnu automatiquement par l'analyseur.\n"
                "Sa définition est dans le code — rien à paramétrer ici.")


class TabCircuits:
    """
    @brief Onglet « Circuits » : patterns reconnus par l'analyseur.

    Même grammaire que l'onglet Composants : liste sectionnée à gauche
    (INTÉGRÉS détectés automatiquement / PERSONNALISÉS modifiables), bandeau
    d'état + formulaire à droite, bouton Sauvegarder épinglé en bas.

    Un circuit intégré est détecté par du code (pas de définition éditable) :
    le sélectionner passe le formulaire en mode lecture seule avec un message.
    """

    def __init__(self, parent):
        """@brief Construit l'onglet, charge les circuits et affiche le mode « nouveau ».

        @param parent Widget parent (zone de contenu).
        """
        self.frame = ctk.CTkFrame(parent, corner_radius=0, fg_color=BG)
        self._custom: list = []
        self._current_idx: int | None = None       # index du perso en édition
        self._mode = 'nouveau'                      # nouveau | edition | lecture
        self._comp_vars: dict[str, tk.BooleanVar] = {}
        self._comp_boxes: list = []                 # CTkCheckBox composants
        self._cond_vars: dict[str, tk.BooleanVar] = {}
        self._cond_boxes: list = []                 # CTkCheckBox conditions
        self._lignes: list[tuple] = []               # rangées listbox (section, index)
        self._etat_initial: tuple = ('', frozenset(), frozenset())
        self._build()
        self._load()
        self._afficher_nouveau()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self):
        """@brief Construit l'en-tête, la liste sectionnée et le formulaire (composants + conditions)."""
        header = ctk.CTkFrame(self.frame, fg_color=CARD,
                              corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        h = ctk.CTkFrame(header, fg_color="transparent")
        h.pack(fill="both", expand=True, padx=28)
        ctk.CTkLabel(h, text="Circuits reconnus",
                     font=ui_kit.font("display"),
                     text_color=TEXT).pack(side="left", pady=18)
        ctk.CTkLabel(h, text="Consulter les patterns intégrés, créer les vôtres",
                     font=ui_kit.font("body"),
                     text_color=TEXT_MUTED).pack(side="left", padx=14, pady=18)

        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_liste(body)

        # ── Droite : bandeau + formulaire + pied épinglé
        right = ui_kit.Card(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        self._bandeau_frame = ctk.CTkFrame(right, corner_radius=R["md"], height=34)
        self._bandeau_frame.pack_propagate(False)
        self._bandeau_frame.grid(row=0, column=0, sticky="ew",
                                 padx=14, pady=(14, 8))
        self._bandeau_label = ctk.CTkLabel(
            self._bandeau_frame, text="", font=ui_kit.font("body", "bold"))
        self._bandeau_label.pack(side="left", padx=12, pady=6)

        # Nom du circuit
        name_row = ctk.CTkFrame(right, fg_color="transparent")
        name_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        ui_kit.SectionHeader(name_row, "Nom du circuit").pack(anchor="w")
        self._name_var = tk.StringVar()
        self._name_entry = ui_kit.Field(
            name_row, textvariable=self._name_var,
            placeholder="Ex: Filtre RLC série")
        self._name_entry.pack(fill="x", pady=(4, 0))

        # Note affichée en lecture seule (circuit intégré, ou pattern perso
        # avancé -- cf. _est_avance). Texte réécrit par _afficher_integre /
        # _afficher_perso selon le cas.
        self._lecture_note = ctk.CTkLabel(
            right, text=_NOTE_INTEGRE,
            font=ui_kit.font("body"),
            text_color=TEXT_MUTED, justify="left")

        # Deux colonnes : composants requis | conditions
        cols = ctk.CTkFrame(right, fg_color="transparent")
        cols.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 8))
        cols.grid_columnconfigure((0, 1), weight=1)
        cols.grid_rowconfigure(0, weight=1)
        self._cols = cols

        comp_col = ui_kit.Card(cols, fg_color=CARD2)
        comp_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        comp_head = ctk.CTkFrame(comp_col, fg_color="transparent")
        comp_head.pack(fill="x", padx=12, pady=(10, 6))
        ctk.CTkLabel(comp_head, image=ui_kit.icon("cpu", 16),
                     text="").pack(side="left", padx=(0, 6))
        ui_kit.SectionHeader(comp_head, "Composants requis").pack(side="left")
        self._comp_scroll = ctk.CTkScrollableFrame(
            comp_col, fg_color="transparent")
        self._comp_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        cond_col = ui_kit.Card(cols, fg_color=CARD2)
        cond_col.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        cond_head = ctk.CTkFrame(cond_col, fg_color="transparent")
        cond_head.pack(fill="x", padx=12, pady=(10, 6))
        ctk.CTkLabel(cond_head, image=ui_kit.icon("check", 16),
                     text="").pack(side="left", padx=(0, 6))
        ui_kit.SectionHeader(cond_head, "Conditions").pack(side="left")
        self._cond_scroll = ctk.CTkScrollableFrame(
            cond_col, fg_color="transparent")
        self._cond_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        self._build_conditions()

        # ── Pied épinglé : bouton Sauvegarder
        pied = ctk.CTkFrame(right, fg_color="transparent")
        pied.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 14))
        pied.grid_columnconfigure(0, weight=1)
        self._pied = pied
        self._btn_save = ui_kit.PrimaryButton(
            pied, "Sauvegarder ce circuit", self._sauvegarder,
            icon_name="save", height=42)
        self._btn_save.grid(row=0, column=0, sticky="ew")

    def _build_liste(self, body):
        """@brief Construit la carte de liste sectionnée (intégrés / personnalisés).

        @param body Conteneur parent (grille de l'onglet).
        @return None
        """
        liste_card = ui_kit.Card(body)
        liste_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        liste_card.grid_rowconfigure(1, weight=1)
        liste_card.grid_columnconfigure(0, weight=1)

        ui_kit.SectionHeader(liste_card, "Circuits reconnus").grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 6))

        lb_f = ctk.CTkFrame(liste_card, fg_color=CARD2, corner_radius=R["md"])
        lb_f.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self._listbox = tk.Listbox(
            lb_f, width=32, height=24,
            bg=CARD2, fg=TEXT_MUTED,
            selectbackground=BLUE_PRESS, selectforeground=TEXT,
            font=ui_kit.font("body"), relief="flat", bd=0,
            activestyle="none", highlightthickness=0,
        )
        sb = tk.Scrollbar(lb_f, command=self._listbox.yview,
                          bg=CARD, troughcolor=CARD2)
        self._listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._listbox.pack(fill="both", expand=True, padx=6, pady=6)
        self._listbox.bind("<<ListboxSelect>>", self._sur_selection_liste)

        br = ctk.CTkFrame(liste_card, fg_color="transparent")
        br.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 12))
        ui_kit.PrimaryButton(
            br, "Nouveau", self._nouveau, icon_name="plus",
            height=36).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ui_kit.DangerButton(
            br, "Supprimer", self._supprimer, icon_name="trash-2",
            height=36).pack(side="left", expand=True, fill="x")

    def _build_conditions(self):
        """@brief Cases à cocher des conditions, regroupées par famille, libellés clairs.

        Les variables restent indexées par la clé stable (pas le libellé affiché),
        pour que la sauvegarde du pattern soit inchangée.
        """
        for titre, cles in CONDITION_GROUPS:
            ui_kit.SectionHeader(self._cond_scroll, titre).pack(
                anchor="w", padx=4, pady=(12, 2))
            for cle in cles:
                var = tk.BooleanVar()
                self._cond_vars[cle] = var
                box = ctk.CTkCheckBox(
                    self._cond_scroll, text=condition_display(cle), variable=var,
                    font=ui_kit.font("body"), text_color=TEXT,
                    fg_color=BLUE_PRESS, hover_color=BLUE, checkmark_color=TEXT)
                box.pack(anchor="w", padx=10, pady=(6, 0))
                self._cond_boxes.append(box)
                desc = CONDITION_DESCRIPTIONS.get(cle, "")
                if desc:
                    ctk.CTkLabel(self._cond_scroll, text=desc,
                                 font=ui_kit.font("caption"),
                                 text_color=TEXT_DIM, justify="left",
                                 anchor="w").pack(anchor="w", padx=34, pady=(0, 4))
        lier_molette(self._cond_scroll)

    def _build_comp_checkboxes(self):
        """@brief (Re)construit les cases à cocher des composants requis depuis la bibliothèque."""
        for w in self._comp_scroll.winfo_children():
            w.destroy()
        self._comp_vars = {}
        self._comp_boxes = []
        for key, val in load_library().items():
            var = tk.BooleanVar()
            self._comp_vars[key] = var
            box = ctk.CTkCheckBox(
                self._comp_scroll, text=f"{key}  —  {val['name']}",
                variable=var, font=ui_kit.font("body"),
                text_color=TEXT, fg_color=BLUE_PRESS, hover_color=BLUE,
                checkmark_color=TEXT)
            box.pack(anchor="w", padx=4, pady=3)
            self._comp_boxes.append(box)
        lier_molette(self._comp_scroll)

    # ── Modes du formulaire ──────────────────────────────────────────────────

    def _definir_mode(self, mode: str, texte: str):
        """@brief Bascule le formulaire en mode nouveau / édition / lecture seule.

        @param mode Mode cible ('nouveau', 'edition', 'lecture').
        @param texte Texte du bandeau d'état.
        @return None
        """
        self._mode = mode
        fond, couleur = _BANDEAU_STYLES[mode]
        self._bandeau_frame.configure(fg_color=fond)
        self._bandeau_label.configure(text=texte, text_color=couleur)
        # [MODIF 2026-08-18] 'lecture_perso' (pattern avancé) est AUSSI lecture
        # seule pour le formulaire -- seule la suppression reste permise (gérée
        # séparément par _supprimer, indépendant du mode).
        lecture = mode.startswith('lecture')
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
        """@brief Affiche un formulaire vierge en mode « nouveau »."""
        self._current_idx = None
        self._remplir_formulaire('', set(), set())
        self._definir_mode('nouveau', "➕  Nouveau circuit personnalisé")
        self._prendre_snapshot()

    def _afficher_perso(self, idx: int):
        """@brief Affiche un circuit personnalisé (édition, ou lecture seule
        si le pattern utilise une fonctionnalité avancée de l'assistant).

        [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (« voir tous les schémas et
        pouvoir en supprimer un ») : `set(c.get("components", []))` /
        `set(c.get("conditions", []))` PLANTAIENT (`TypeError: unhashable
        type: 'dict'`) dès qu'un pattern créé par l'assistant contenait un
        nom verrouillé (`{"type":.., "categorie":..}`) ou une condition
        générique paramétrée (dict, ex. "connexion_broches") -- les cases à
        cocher de cet onglet ne représentent QUE les 12 conditions nommées et
        des types nus. Pire que la perte silencieuse redoutée ailleurs cette
        session : ici, resauvegarder aurait carrément écrasé le pattern avec
        une version appauvrie (verrou perdu). Un tel pattern est donc affiché
        en LECTURE SEULE avec un résumé lisible (`_resume_avance`) --
        toujours supprimable, juste pas éditable depuis ces cases à cocher.

        @param idx Index du circuit personnalisé.
        @return None
        """
        self._current_idx = idx
        c = self._custom[idx]
        if self._est_avance(c):
            self._remplir_formulaire(c.get("name", ""), set(), set())
            self._lecture_note.configure(text=self._resume_avance(c))
            self._definir_mode(
                'lecture_perso',
                f"⚙  ★ {c.get('name', '')} — pattern avancé (lecture seule)")
        else:
            self._remplir_formulaire(c.get("name", ""),
                                     set(c.get("components", [])),
                                     set(c.get("conditions", [])))
            self._definir_mode('edition', f"✏  Modification de ★ {c.get('name', '')}")
        self._prendre_snapshot()

    def _est_avance(self, c: dict) -> bool:
        """@brief Vrai si ce pattern utilise une fonctionnalité de l'assistant
        non représentable par les cases à cocher de cet onglet (nom précis
        verrouillé sur un composant, ou condition générique paramétrée).

        @param c Définition du pattern personnalisé (dict JSON).
        @return bool True si le pattern doit s'afficher en lecture seule ici.
        """
        # [MODIF 2026-08-19] BUG TROUVÉ EN TESTANT : `composition_exacte` est une
        # clé de NIVEAU PATTERN (pas dans "components"/"conditions"), donc invisible
        # aux deux `any(...)` ci-dessus -- un pattern par ailleurs "simple" (aucun
        # composant/condition en dict) mais avec `composition_exacte: true` passait
        # en mode 'edition' (cases à cocher), dont `_sauvegarder` reconstruit
        # `c = {"name", "components", "conditions"}` FROM SCRATCH -> la clé était
        # silencieusement perdue au premier "Enregistrer" depuis cet onglet.
        # [MODIF 2026-08-19] `nombre_composants_ilot` est aussi une clé de niveau
        # PATTERN (même piège que `composition_exacte` ci-dessus, corrigé le
        # même jour) -- sans ce check, un pattern n'utilisant QUE cette option
        # passerait en mode 'edition', dont `_sauvegarder` reconstruit
        # `{"name","components","conditions"}` FROM SCRATCH et perdrait la clé.
        return (any(isinstance(x, dict) for x in c.get("components", []))
               or any(isinstance(x, dict) for x in c.get("conditions", []))
               or bool(c.get("composition_exacte"))
               or bool(c.get("nombre_composants_ilot")))

    def _resume_avance(self, c: dict) -> str:
        """@brief Résumé lisible (composants + conditions) d'un pattern avancé.

        @param c Définition du pattern personnalisé (dict JSON).
        @return str Texte multi-lignes pour `self._lecture_note`.
        """
        lignes = [
            "Ce pattern utilise une fonctionnalité avancée de l'assistant",
            "(nom précis verrouillé et/ou condition paramétrée) : non",
            "éditable depuis ces cases à cocher. Modifiez-le depuis",
            "l'assistant (Analyser → « Suggérer un pattern », ou",
            "Éditeur → « Enregistrer comme pattern »). Toujours",
            "supprimable avec le bouton « Supprimer » à gauche.",
            "",
        ]
        if c.get("composition_exacte"):
            lignes.append("⚠  Composition EXACTE : aucun autre composant toléré "
                          "dans le circuit.")
            lignes.append("")
        if c.get("nombre_composants_ilot"):
            lignes.append("⚠  " + libelle_nombre_composants_ilot(c["nombre_composants_ilot"]))
            lignes.append("")
        lignes.append("Composants requis :")
        for comp in c.get("components", []):
            if isinstance(comp, dict):
                t, cat = comp.get("type"), comp.get("categorie")
                lignes.append(f"  •  {t}" + (f"  (« {cat} » précisément)" if cat else ""))
            else:
                lignes.append(f"  •  {comp}")
        lignes += ["", "Conditions :"]
        conds = c.get("conditions", [])
        if not conds:
            lignes.append("  (aucune)")
        for cond in conds:
            lignes.append(f"  •  {condition_display(cond)}")
        return "\n".join(lignes)

    def _afficher_integre(self, nom: str):
        """@brief Affiche un circuit intégré en lecture seule (détecté par le code).

        @param nom Nom du circuit intégré.
        @return None
        """
        self._current_idx = None
        self._remplir_formulaire(nom, set(), set())
        self._lecture_note.configure(text=_NOTE_INTEGRE)
        self._definir_mode(
            'lecture', f"🔒  Circuit intégré « {nom} » — détecté automatiquement")
        self._prendre_snapshot()

    def _remplir_formulaire(self, nom: str, composants: set, conditions: set):
        """@brief Remplit le formulaire (nom, cases composants, cases conditions).

        @param nom Nom du circuit.
        @param composants Ensemble des types de composants requis cochés.
        @param conditions Ensemble des conditions cochées.
        @return None
        """
        # Réactiver avant d'écrire : un widget disabled ignore les set()
        self._name_entry.configure(state="normal")
        self._name_var.set(nom)
        for key, var in self._comp_vars.items():
            var.set(key in composants)
        for label, var in self._cond_vars.items():
            var.set(label in conditions)

    # ── Anti-perte de saisie ─────────────────────────────────────────────────

    def _etat_courant(self) -> tuple:
        """@brief Instantané (nom, composants cochés, conditions cochées) du formulaire.
        @return tuple État courant, pour détecter les modifications non sauvegardées.
        """
        return (self._name_var.get().strip(),
                frozenset(k for k, v in self._comp_vars.items() if v.get()),
                frozenset(l for l, v in self._cond_vars.items() if v.get()))

    def _prendre_snapshot(self):
        """@brief Mémorise l'état courant comme référence anti-perte de saisie."""
        self._etat_initial = self._etat_courant()

    def _confirmer_abandon(self) -> bool:
        """@brief Vrai si on peut quitter le formulaire (rien à perdre, ou confirmé).
        @return bool True si l'abandon est autorisé.
        """
        if self._mode.startswith('lecture') or self._etat_courant() == self._etat_initial:
            return True
        return messagebox.askyesno(
            "Modifications non sauvegardées",
            "Le formulaire contient des modifications non sauvegardées.\n"
            "Les abandonner ?")

    # ── Liste sectionnée ─────────────────────────────────────────────────────

    def _remplir_liste(self, integres: list[str], personnalises: list[str]) -> None:
        """@brief (Re)peuple la liste : section intégrés puis section personnalisés.

        @param integres Libellés des éléments intégrés (consultables).
        @param personnalises Libellés des éléments personnalisés (modifiables).
        @return None
        """
        self._listbox.delete(0, "end")
        self._lignes = []

        self._ajouter_entete(f"INTÉGRÉS ({len(integres)}) — consultables")
        for texte in integres:
            self._listbox.insert("end", f"   {texte}")
            self._listbox.itemconfig("end", foreground=TEXT_MUTED)
            self._lignes.append(('integre', len(self._lignes_section('integre'))))

        self._ajouter_entete(f"PERSONNALISÉS ({len(personnalises)}) — modifiables")
        if not personnalises:
            self._listbox.insert("end", "   (aucun — bouton ＋ Nouveau)")
            self._listbox.itemconfig("end", foreground=TEXT_DIM)
            self._lignes.append(('entete', None))
        for texte in personnalises:
            self._listbox.insert("end", f"   ★  {texte}")
            self._listbox.itemconfig("end", foreground=BLUE)
            self._lignes.append(('perso', len(self._lignes_section('perso'))))

    def _lignes_section(self, section: str) -> list:
        """@brief Lignes appartenant à une section donnée.

        @param section Nom de section ('integre', 'perso', 'entete').
        @return list Lignes (tuples) de cette section.
        """
        return [l for l in self._lignes if l[0] == section]

    def _ajouter_entete(self, texte: str) -> None:
        """@brief Insère une ligne d'en-tête non sélectionnable.

        @param texte Libellé de l'en-tête.
        @return None
        """
        self._listbox.insert("end", f" — {texte} —")
        self._listbox.itemconfig("end", foreground=TEXT_DIM)
        self._lignes.append(('entete', None))

    def _sur_selection_liste(self, _=None):
        """@brief Gestionnaire d'événement de sélection de la liste : route vers le callback.

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
        self._sur_selection(section, index)

    # ── Données ──────────────────────────────────────────────────────────────

    def _load(self):
        """@brief Reconstruit les cases composants, charge les circuits personnalisés et peuple la liste."""
        self._build_comp_checkboxes()
        self._custom = load_custom_circuits()
        self._remplir_liste(
            integres=list(_BASE_NAMES),
            personnalises=[c.get("name", "") for c in self._custom],
        )

    def refresh_circuits(self):
        """@brief Recharge la liste des patterns personnalisés (créés depuis un autre onglet).

        Appelé après la création d'un pattern via l'éditeur ou l'analyse : sans
        ça, le pattern enregistré dans le fichier n'apparaît dans cette liste qu'au
        prochain démarrage. Ne touche pas au formulaire en cours d'édition.
        """
        self._custom = load_custom_circuits()
        self._remplir_liste(
            integres=list(_BASE_NAMES),
            personnalises=[c.get("name", "") for c in self._custom],
        )

    def refresh_component_list(self):
        """@brief Reconstruit les cases composants en conservant les choix (la bibliothèque a changé)."""
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
        """@brief Gère la sélection d'un circuit dans la liste (intégré ou personnalisé).

        @param section Section sélectionnée ('integre' ou 'perso').
        @param index Index dans la section.
        @return None
        """
        if not self._confirmer_abandon():
            self._listbox.selection_clear(0, "end")
            return
        if section == 'integre':
            self._afficher_integre(list(_BASE_NAMES)[index])
        else:
            self._afficher_perso(index)

    def _nouveau(self):
        """@brief Démarre la création d'un nouveau circuit (après confirmation d'abandon)."""
        if not self._confirmer_abandon():
            return
        self._listbox.selection_clear(0, "end")
        self._afficher_nouveau()

    def _supprimer(self):
        """@brief Supprime le circuit personnalisé en cours d'édition (avec confirmation).

        [MODIF 2026-08-18] Ancien garde `self._mode != 'edition'` -- bloquait
        la suppression d'un pattern avancé affiché en 'lecture_perso' (cf.
        `_afficher_perso`/`_est_avance`), alors que `self._current_idx` seul
        distingue déjà correctement perso (idx défini) d'intégré/nouveau
        (idx None) : la suppression doit rester possible en lecture seule.
        """
        if self._current_idx is None:
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
        """@brief Valide et enregistre le circuit personnalisé saisi (nom, composants, conditions)."""
        name = self._name_var.get().strip()
        if not name:
            messagebox.showerror("Erreur", "Nom obligatoire.")
            return
        comps = [k for k, v in self._comp_vars.items() if v.get()]
        if not comps:
            messagebox.showerror("Erreur",
                                 "Sélectionnez au moins un composant.")
            return
        # Doublon de nom : circuits intégrés + personnalisés (hors celui édité).
        deja_pris = set(_BASE_NAMES) | {
            c.get("name", "") for i, c in enumerate(self._custom)
            if i != self._current_idx
        }
        if name in deja_pris:
            messagebox.showinfo(
                "Déjà existant",
                f"Un circuit nommé « {name} » existe déjà.\n"
                "Choisissez un autre nom.")
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
