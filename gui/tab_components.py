"""
@file tab_components.py
@brief Onglet « Composants » : consultation des types intégrés et édition des types personnalisés.
"""
import json
import xml.etree.ElementTree as ET
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, filedialog

from circuit_analyzer.composant import (
    TYPES_COMPOSANTS as COMPONENT_TYPES, chemin_bibliotheque,
)
from circuit_analyzer.eretro_lib import (
    composant_vers_symbole_xml, composants_depuis_xml,
)
from gui.pin_canvas import GRILLE, PinCanvas
from gui.theme import BG, CARD, CARD2, TEXT, TEXT_MUTED, BLUE, ERROR
from gui import ui_kit
from gui.widgets import ListeSectionnee, BandeauEtat, ligne_aide, lier_molette


def _amorcer(broches: list) -> list:
    """@brief Projette la géométrie historique sur les bords de la boîte.

    Un type créé AVANT le brochage positionné (spec 2026-07-23) n'a que des
    noms de broches : on rejoue la répartition moitié gauche / moitié droite de
    `_auto_def`, puis on aimante chaque broche sur son bord — ainsi la
    réouverture ne perd aucune broche et montre ce que l'utilisateur voyait.

    @param broches Liste ordonnée de noms.
    @return list [(nom, côté, décalage)] dans le même ordre.
    """
    from gui.schematic_editor import _auto_def
    from gui.schematic_symbols import aimanter_bord
    broches = [b for b in broches if b]
    if not broches:
        return []
    d = _auto_def("", list(broches))
    return [(b, *aimanter_bord(*d["pins"][b], d["w"], d["h"], GRILLE))
            for b in broches]


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
        # Brochage ORDONNÉ [(nom, côté, décalage)] : l'ordre EST celui de la
        # netlist et de la saisie rapide (spec 2026-07-23).
        self._brochage: list = []
        self._modeles = {"DIP-8": ("DIP", 8), "DIP-14": ("DIP", 14),
                         "DIP-16": ("DIP", 16), "Bornier 2": ("Connecteur", 2),
                         "Bornier 3": ("Connecteur", 3),
                         "Bornier 4": ("Connecteur", 4),
                         "Connecteur N": ("Connecteur", 0)}
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

        ui_kit.SectionHeader(form, "Valeur par défaut").pack(anchor="w")
        self._default_var = tk.StringVar()
        self._default_entry = ui_kit.Field(
            form, textvariable=self._default_var,
            placeholder="Ex: LM358", height=40)
        self._default_entry.pack(fill="x", pady=(4, 2))
        ligne_aide(form, "Pré-remplie quand tu poses le composant "
                         "(aujourd'hui toujours vide pour un type perso).")

        ui_kit.SectionHeader(form, "Broches").pack(anchor="w")

        mrow = ctk.CTkFrame(form, fg_color="transparent")
        mrow.pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(mrow, text="Modèle :", font=ui_kit.font("caption"),
                     text_color=TEXT_MUTED).pack(side="left", padx=(0, 6))
        self._modele_var = tk.StringVar(value="DIP-8")
        ctk.CTkOptionMenu(mrow, values=list(self._modeles),
                          variable=self._modele_var, width=140,
                          height=30).pack(side="left")
        self._n_var = tk.StringVar(value="8")
        ui_kit.Field(mrow, textvariable=self._n_var, width=56, height=30,
                     placeholder="N").pack(side="left", padx=6)
        self._btn_modele = ui_kit.SecondaryButton(
            mrow, "Poser", self._poser_modele, icon_name="plus",
            width=90, height=30)
        self._btn_modele.pack(side="left")

        self._canvas_broches = PinCanvas(form, on_change=self._sur_brochage)
        self._canvas_broches.pack(fill="x", pady=(4, 6))

        trow = ctk.CTkFrame(form, fg_color="transparent")
        trow.pack(fill="x", pady=(0, 2))
        self._auto_taille_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(trow, text="Ajuster automatiquement",
                        variable=self._auto_taille_var,
                        command=self._sur_auto_taille,
                        font=ui_kit.font("caption")).pack(side="left")
        ctk.CTkLabel(trow, text="Largeur", font=ui_kit.font("caption"),
                     text_color=TEXT_MUTED).pack(side="left", padx=(14, 4))
        self._w_var = tk.StringVar()
        self._w_entry = ui_kit.Field(trow, textvariable=self._w_var,
                                     width=70, height=30)
        self._w_entry.pack(side="left")
        ctk.CTkLabel(trow, text="Hauteur", font=ui_kit.font("caption"),
                     text_color=TEXT_MUTED).pack(side="left", padx=(10, 4))
        self._h_var = tk.StringVar()
        self._h_entry = ui_kit.Field(trow, textvariable=self._h_var,
                                     width=70, height=30)
        self._h_entry.pack(side="left")
        self._sur_auto_taille()
        ligne_aide(form, "Clic sur un bord = poser une broche · glisser = "
                         "déplacer · double-clic = renommer · Suppr = retirer. "
                         "Le bandeau donne l'ordre de la netlist (glisser pour "
                         "réordonner).")

        # ── Pied épinglé (hors scroll) : toujours visible
        pied = ctk.CTkFrame(right, fg_color="transparent")
        pied.pack(fill="x", padx=14, pady=(0, 14))
        self._btn_save = ui_kit.PrimaryButton(
            pied, "Sauvegarder le composant", self._sauvegarder,
            icon_name="save", height=42)
        self._btn_dupliquer = ui_kit.SecondaryButton(
            pied, "Dupliquer comme personnalisé", self._dupliquer,
            icon_name="copy", height=42)
        # Partage avec la bibliotheque ERetroDesign du collegue.
        self._btn_export = ui_kit.SecondaryButton(
            pied, "Exporter vers ERetroDesign (.xml)", self._exporter_eretro,
            height=38)
        self._btn_import = ui_kit.SecondaryButton(
            pied, "Importer un composant ERetroDesign", self._importer_eretro,
            icon_name="download", height=38)
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
        # Le canevas porte son propre verrou : `_remplir_formulaire` le charge
        # avec `lecture_seule`, aucun clic ne mute alors le brochage.
        for b in (self._btn_save, self._btn_dupliquer,
                  self._btn_export, self._btn_import):
            b.pack_forget()
        (self._btn_dupliquer if lecture else self._btn_save).pack(fill="x")
        # Export : seulement pour un perso DEJA enregistre (on exporte le JSON).
        if self._current_key in self._custom:
            self._btn_export.pack(fill="x", pady=(8, 0))
        self._btn_import.pack(fill="x", pady=(8, 0))   # import : toujours dispo

    def _afficher_nouveau(self):
        """@brief Affiche un formulaire vierge en mode « nouveau »."""
        self._current_key = None
        self._remplir_formulaire('', '', [])
        self._definir_mode('nouveau', "➕  Nouveau type de composant")
        self._prendre_snapshot()

    def _afficher_perso(self, key: str):
        """@brief Affiche un type personnalisé en mode édition.

        @param key Préfixe du type personnalisé.
        @return None
        """
        self._current_key = key
        v = self._custom[key]
        self._remplir_formulaire(key, v.get("name", ""), v.get("pins", []),
                                 v.get("brochage"),
                                 default_value=v.get("default_value", ""),
                                 fonctions=v.get("fonctions"),
                                 boite=v.get("boite"))
        self._definir_mode('edition', f"✏  Modification de ★ {key}")
        self._prendre_snapshot()

    def _afficher_integre(self, key: str):
        """@brief Affiche un type intégré en lecture seule.

        @param key Préfixe du type intégré.
        @return None
        """
        self._current_key = None
        v = COMPONENT_TYPES[key]
        self._remplir_formulaire(key, v["name"], v["pins"], None,
                                 lecture_seule=True,
                                 default_value=v.get("default_value", ""))
        self._definir_mode('lecture',
                           f"🔒  Type intégré {key} — lecture seule")
        self._prendre_snapshot()

    def _sur_auto_taille(self):
        """@brief Grise les champs de taille tant que l'auto est coché."""
        etat = "disabled" if self._auto_taille_var.get() else "normal"
        self._w_entry.configure(state=etat)
        self._h_entry.configure(state=etat)

    def _poser_modele(self):
        """@brief Remplace le brochage par celui du boîtier choisi.

        DESTRUCTIF : demande confirmation si un brochage existe déjà.
        """
        if self._mode == 'lecture':
            return
        modele, n = self._modeles.get(self._modele_var.get(), (None, 0))
        if modele is None:
            return
        if not n:                              # « Connecteur N » : N est saisi
            try:
                n = int(self._n_var.get())
            except ValueError:
                messagebox.showerror("Erreur", "Nombre de broches invalide.")
                return
        if self._brochage and not messagebox.askyesno(
                "Remplacer le brochage",
                "Poser un modèle REMPLACE le brochage actuel "
                f"({len(self._brochage)} broches). Continuer ?"):
            return
        try:
            self._canvas_broches.poser_modele(modele, n)
        except ValueError as e:
            messagebox.showerror("Erreur", str(e))
            return
        self._brochage = self._canvas_broches.brochage()

    def _sur_brochage(self, brochage: list):
        """@brief Le canevas a muté : sa liste ordonnée devient l'état du form."""
        self._brochage = list(brochage)

    def _remplir_formulaire(self, prefixe: str, nom: str, broches: list,
                            brochage: dict = None, lecture_seule: bool = False,
                            default_value: str = "", fonctions: dict = None,
                            boite: dict = None):
        """@brief Remplit les champs du formulaire (préfixe, nom, brochage).

        @param prefixe Préfixe du type.
        @param nom Nom complet du type.
        @param broches Liste ORDONNÉE des noms de broches (ordre netlist).
        @param brochage {nom: [côté, décalage]} du fichier, ou None.
        @param lecture_seule Vrai pour un type intégré (canevas non éditable).
        @return None
        """
        # Réactiver avant d'écrire : un Entry disabled ignore les set()
        self._prefix_entry.configure(state="normal")
        self._name_entry.configure(state="normal")
        self._prefix_var.set(prefixe)
        self._name_var.set(nom)
        if brochage:
            # L'ORDRE vient de `pins`, les POSITIONS de `brochage` : une broche
            # présente dans l'un et pas dans l'autre est simplement ignorée.
            self._brochage = [(b, *brochage[b]) for b in broches
                              if b in brochage]
        else:
            self._brochage = _amorcer(broches)
        self._default_var.set(default_value or "")
        b = boite or {}
        self._auto_taille_var.set(not b)
        self._w_var.set(str(b.get("w", "")) if b else "")
        self._h_var.set(str(b.get("h", "")) if b else "")
        self._sur_auto_taille()
        self._canvas_broches.charger(self._brochage, lecture_seule,
                                     roles=fonctions,
                                     w_mini=b.get("w"), h_mini=b.get("h"))

    # ── Anti-perte de saisie ─────────────────────────────────────────────────

    def _etat_courant(self) -> tuple:
        """@brief Instantané (préfixe, nom, broches) de l'état courant du formulaire.
        @return tuple État courant, pour détecter les modifications non sauvegardées.
        """
        return (self._prefix_var.get().strip(),
                self._name_var.get().strip(),
                tuple(self._brochage),
                self._default_var.get().strip(),
                tuple(sorted(self._canvas_broches.roles().items())),
                (self._auto_taille_var.get(),
                 self._w_var.get().strip(), self._h_var.get().strip()))

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
        broches = [n for n, _c, _d in self._brochage]
        positions = {n: [c, d] for n, c, d in self._brochage}
        self._liste.deselectionner()
        self._current_key = None
        b = {}
        if not self._auto_taille_var.get():
            b = {"w": self._w_var.get(), "h": self._h_var.get()}
            b = {k: int(v) for k, v in b.items() if str(v).strip().isdigit()}
        self._remplir_formulaire('', f"{nom} (copie)", broches, positions,
                                 default_value=self._default_var.get(),
                                 fonctions=self._canvas_broches.roles(),
                                 boite=b or None)
        self._definir_mode('nouveau',
                           "➕  Nouveau type (copie) — choisir un préfixe")
        self._prendre_snapshot()

    def _exporter_eretro(self):
        """@brief Exporte le composant personnalisé courant en symbole Lib
        ERetroDesign (<DataItem>, a importer via le bouton « Importer composant »)."""
        key = self._current_key
        if key not in self._custom:
            messagebox.showinfo(
                "Info", "Enregistrez d'abord le composant, puis exportez-le.")
            return
        entree = self._custom[key]
        defaut = f"{entree.get('name') or key}.xml"
        chemin = filedialog.asksaveasfilename(
            title="Exporter vers la bibliotheque ERetroDesign",
            defaultextension=".xml", initialfile=defaut,
            filetypes=[("Bibliotheque ERetroDesign", "*.xml")])
        if not chemin:
            return
        try:
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(composant_vers_symbole_xml(key, entree))
        except OSError as e:
            messagebox.showerror("Erreur", f"Ecriture impossible : {e}")
            return
        messagebox.showinfo(
            "Export ERetroDesign",
            "Composant exporte.\n\nDans ERetroDesign : bouton « Importer "
            "composant » (sous la palette), puis choisissez ce fichier.\n"
            "Il apparait dans la palette : cliquez-le pour le poser.\n"
            "(Ne PAS utiliser « Ouvrir » : ce n'est pas un schema.)")

    def _importer_eretro(self):
        """@brief Importe un paquet ERetroDesign (.xml) : ajoute ses composants."""
        chemin = filedialog.askopenfilename(
            title="Importer un composant / une bibliotheque ERetroDesign",
            filetypes=[("Bibliotheque ERetroDesign", "*.xml"), ("Tous", "*.*")])
        if not chemin:
            return
        try:
            trouves = composants_depuis_xml(chemin)
        except (ValueError, OSError, ET.ParseError) as e:
            messagebox.showerror(
                "Import impossible",
                f"Fichier illisible ou format inattendu :\n{e}")
            return
        if not trouves:
            messagebox.showwarning(
                "Import", "Aucun composant simple trouve dans ce fichier.")
            return
        dernier, ajoutes = None, 0
        for prefix, entree in trouves:
            base = "".join(ch for ch in prefix if ch.isalnum()) or "X"
            prefix = base
            n = 1
            while prefix in COMPONENT_TYPES or prefix in self._custom:
                n += 1
                prefix = f"{base}{n}"
            self._custom[prefix] = entree
            dernier, ajoutes = prefix, ajoutes + 1
        self._ecrire()
        self._load()
        if dernier:
            self._afficher_perso(dernier)
        if self._on_save:
            self._on_save()
        messagebox.showinfo(
            "Import ERetroDesign",
            f"{ajoutes} composant(s) importe(s).")

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
        pins   = [n.strip() for n, _c, _d in self._brochage if n.strip()]
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
        entree = {"name": name, "pins": pins,
                  "brochage": {n: [c, d] for n, c, d in self._brochage}}
        defaut = self._default_var.get().strip()
        if defaut:
            entree["default_value"] = defaut
        roles = self._canvas_broches.roles()
        if roles:
            entree["fonctions"] = roles
        if not self._auto_taille_var.get():
            try:
                entree["boite"] = {"w": int(self._w_var.get()),
                                   "h": int(self._h_var.get())}
            except ValueError:
                messagebox.showerror(
                    "Erreur", "Largeur et hauteur doivent être des entiers "
                              "(ou coche « Ajuster automatiquement »).")
                return
        if self._current_key and self._current_key != prefix:
            self._custom.pop(self._current_key, None)
        self._custom[prefix] = entree
        self._ecrire()
        self._load()
        self._afficher_perso(prefix)
        if self._on_save:
            self._on_save()
        messagebox.showinfo("Succès", f"'{prefix}' sauvegardé.")

    def refresh_component_list(self):
        """@brief Recharge la bibliothèque (appelé quand un autre onglet la modifie)."""
        self._load()
