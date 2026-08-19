"""
@file pattern_wizard.py
@brief Wizard 4 étapes pour créer un pattern circuit personnalisé depuis l'interface.

Ouvre une fenêtre modale 860×540 avec :
  Étape 1 — Sélection des composants
  Étape 2 — Nom du pattern
  Étape 3 — Conditions topologiques
  Étape 4 — Prévisualisation & confirmation
"""
import json
import logging
import tkinter as tk

import customtkinter as ctk
import schemdraw
import schemdraw.elements as elm
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from circuit_analyzer.detecteur import NOMS_CIRCUITS
from custom_circuits.loader import (
    CONDITION_DESCRIPTIONS,
    CONDITION_GROUPS,
    CONDITION_KIND_DESCRIPTIONS,
    CONDITION_KIND_LABELS,
    CONDITION_KINDS,
    CONDITION_LABELS,
    condition_display,
    libelle_nombre_composants_ilot,
    load_custom_circuits,
    save_custom_circuits,
    suggest_conditions,
)
from gui.theme import BLUE, BLUE_D, BORDER, CARD, CARD2, MUTED, TEXT
from gui.impedance_schematic import style_symbole

_log = logging.getLogger(__name__)

# ── Constantes de design ──────────────────────────────────────────────────────
_BG        = "#0f172a"
_JSON_BG   = "#0a0f1a"
_JSON_FG   = "#4ade80"
_BTN_NEXT  = "#3b82f6"
_BTN_NEXT_H = "#2563eb"
_BTN_CREATE = "#22c55e"
_BTN_CREATE_H = "#16a34a"
_BTN_PREV  = "#334155"
_BTN_PREV_H = "#475569"
_ERR       = "#ef4444"
_STEP_ACTIVE = "#3b82f6"
_STEP_DONE   = "#22c55e"
_STEP_IDLE   = "#334155"

# Couleurs des badges par type de composant
_TYPE_COLORS = {
    "R": "#f97316",
    "C": "#3b82f6",
    "L": "#8b5cf6",
    "D": "#22c55e",
    "Q": "#ec4899",
    "U": "#06b6d4",
    "K": "#eab308",
}
_TYPE_LABELS = {
    "R": "Résistance",
    "C": "Condensateur",
    "L": "Inductance",
    "D": "Diode",
    "Q": "Transistor BJT",
    "U": "Circuit intégré",
    "K": "Relais",
    "M": "MOSFET",
    "J": "Connecteur",
    # [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT : 'X' = composant NON reconnu par
    # l'analyseur (nom absent des tables, forme ambiguë) -- 'J' est le vrai type
    # connecteur (`_MAPPING_ERETRO`, mots-clés connect/jumper/borne). Étiqueter 'X'
    # "Connecteur" affirmait à tort ce que le composant EST alors qu'on ne le sait
    # justement pas -- trompeur au moment précis où l'utilisateur choisit de
    # l'inclure dans un nouveau pattern (« Créer le pattern »).
    "X": "Inconnu",
}

# [MODIF 2026-08-18] Comparateurs pour les "kind" numériques (au_moins_n,
# valeur_compare, nombre_broches) -- la CLÉ part dans le JSON (cf.
# custom_circuits.loader._COMPARATEURS, même clés), le LIBELLE est ce que
# l'utilisateur voit dans le menu déroulant du builder.
_COMPARATEUR_CHOIX = [
    (">=", "au moins (≥)"),
    ("==", "exactement (=)"),
    ("<=", "au plus (≤)"),
    (">",  "strictement plus (>)"),
    ("<",  "strictement moins (<)"),
]
_COMPARATEUR_LABELS = [lbl for _cle, lbl in _COMPARATEUR_CHOIX]
_COMPARATEUR_LABEL_VERS_CLE = {lbl: cle for cle, lbl in _COMPARATEUR_CHOIX}
_COMPARATEUR_CLE_VERS_LABEL = {cle: lbl for cle, lbl in _COMPARATEUR_CHOIX}

# [MODIF 2026-08-18] Lot « add more costomation ... 1 to a lot of pins or this
# one should never be connected to this » : "sens" (positif/négatif) et "mode"
# (une seule broche suffit / toutes exigées) du kind "connexion_broches".
_SENS_CHOIX = [
    ("connectee", "doit être connectée"),
    ("jamais_connectee", "ne doit JAMAIS être connectée"),
]
_SENS_LABELS = [lbl for _cle, lbl in _SENS_CHOIX]
_SENS_LABEL_VERS_CLE = {lbl: cle for cle, lbl in _SENS_CHOIX}

_MODE_BROCHES_CHOIX = [
    ("au_moins_une", "au moins une de ces broches"),
    ("toutes", "TOUTES ces broches, chacune"),
]
_MODE_BROCHES_LABELS = [lbl for _cle, lbl in _MODE_BROCHES_CHOIX]
_MODE_BROCHES_LABEL_VERS_CLE = {lbl: cle for cle, lbl in _MODE_BROCHES_CHOIX}


def _type_color(t: str) -> str:
    return _TYPE_COLORS.get(t, "#94a3b8")


def _type_label(t: str, pins=None) -> str:
    """@brief Libellé affiché pour un type de composant.

    [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (« aop is still showing circuit
    integre ») : le type 'U' regroupe TOUT composant "boîte à broches" (AOP,
    TL431, régulateur, IC catalogue quelconque…) — il n'existe pas de lettre
    dédiée "AOP" dans ce système de types, donc `_TYPE_LABELS["U"]` reste
    volontairement générique ("Circuit intégré"). Un AOP est reconnaissable
    sans ambiguïté par ses broches sémantiques (IN+/IN-/OUT, posées par le
    plan `_NOM_VERS_TYPE['AOP']` de `circuit_analyzer/xml.py`) : quand elles
    sont présentes, on affiche un libellé plus précis plutôt que la
    catégorie générique — la lettre de TYPE elle-même (toujours 'U') reste
    inchangée, seul ce texte d'affichage devient plus spécifique.

    @param t Lettre de type ('R', 'U', 'D'...).
    @param pins Dict des broches du composant (optionnel), pour affiner U.
    @return str Libellé lisible.
    """
    if t == "U" and pins and {"IN+", "IN-", "OUT"} <= set(pins):
        return "Amplificateur opérationnel (AOP)"
    return _TYPE_LABELS.get(t, t)


# Boîte max d'affichage de l'aperçu étape 4 -- même ordre de grandeur que le
# Figure(figsize=(6.5, 2.4)) du rendu schemdraw de repli, pour une echelle
# visuelle coherente entre les deux modes d'apercu.
_APERCU_MAX_W = 640
_APERCU_MAX_H = 220


def _taille_affichage(taille_image: tuple[int, int],
                      max_w: int = _APERCU_MAX_W,
                      max_h: int = _APERCU_MAX_H) -> tuple[int, int]:
    """@brief Taille d'affichage d'une image dans une boite max, ratio preserve.

    [MODIF 2026-08-19] BUG TROUVÉ EN TESTANT (« la previsualisation est trop
    zoomee ») : une capture d'ecran reelle du canevas est souvent bien plus
    grande que la petite zone d'apercu de l'etape 4 -- l'afficher a sa taille
    brute ne montrait qu'un morceau agrandi, pas le schema entier. Ne
    RETRECIT que si necessaire (jamais d'agrandissement d'une image deja
    petite, ce n'est pas le probleme signale).

    @param taille_image (largeur, hauteur) de l'image source, en pixels.
    @param max_w Largeur max de la boite d'affichage.
    @param max_h Hauteur max de la boite d'affichage.
    @return tuple[int, int] Taille d'affichage (largeur, hauteur).
    """
    w, h = taille_image
    if w <= max_w and h <= max_h:
        return (w, h)
    echelle = min(max_w / w, max_h / h)
    return (max(1, round(w * echelle)), max(1, round(h * echelle)))


class PatternWizard(ctk.CTkToplevel):
    """
    @brief Wizard 4 étapes (modale 860×540) pour créer un pattern circuit custom.

    Étapes :
      1 — Sélection des composants
      2 — Nom du pattern
      3 — Conditions topologiques (avec suggestion automatique)
      4 — Prévisualisation JSON & confirmation

    @param parent      Widget parent Tk/CTk.
    @param graph       MultiGraph NetworkX du circuit analysé.
    @param unclassified Liste de refs non classifiées (['R3', 'C2', ...]).
    @param comp_info   Dict {ref: {'type': str, 'value': str}}.
    @param on_created  Callback() appelé après sauvegarde (optionnel).
    """

    def __init__(self, parent, graph, unclassified: list[str],
                 comp_info: dict, on_created=None, apercu_image=None):
        super().__init__(parent)

        self._graph       = graph
        self._unclassified = list(unclassified)
        self._comp_info   = comp_info
        self._on_created  = on_created
        # [MODIF 2026-08-19] Capture reelle du canevas de l'editeur (PIL.Image),
        # transmise par TabDraw._save_as_pattern -- quand fournie, l'etape 4
        # l'affiche telle quelle au lieu de regenerer le rendu schemdraw
        # simplifie (boites generiques, disposition en ligne). None quand le
        # wizard est ouvert depuis Analyser (pas de dessin reel a capturer).
        self._apercu_image = apercu_image

        # État du wizard
        self._step        = 1          # étape courante (1–4)
        self._comp_vars: dict[str, tk.BooleanVar] = {}
        # [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (« AOP + photorésistance -> U + R,
        # indiscernable de n'importe quel autre montage U+R ») : case par composant,
        # « exiger précisément ce nom » -- décoché (défaut) = exigence sur le type
        # SEUL, comme avant ; coché = exigence sur type+categorie (cf. Composant.categorie),
        # ex. "R" -> {"type": "R", "categorie": "Photorésistance"}.
        self._verrouiller_categorie_vars: dict[str, tk.BooleanVar] = {}
        # [MODIF 2026-08-18] Nom réel ÉDITABLE par composant (pré-rempli avec
        # Composant.categorie, mais corrigeable -- cf. « ma photorésistance est
        # lue comme R-résistance, je ne peux pas le voir/changer »). Utilisé par
        # `_composants_requis()` à la place de la valeur figée de `comp_info`.
        self._categorie_vars: dict[str, tk.StringVar] = {}
        self._name_var    = tk.StringVar()
        self._cond_vars: dict[str, tk.BooleanVar] = {}
        self._suggested: set[str] = set()  # conditions détectées automatiquement
        # [MODIF 2026-08-18] Conditions GÉNÉRIQUES (dicts) ajoutées par l'utilisateur
        # via le builder de l'étape 3 -- distinctes des 12 conditions nommées
        # (self._cond_vars), fusionnées avec elles dans _selected_conditions().
        self._conditions_perso: list[dict] = []
        self._builder_kind_var = tk.StringVar(value=CONDITION_KIND_LABELS[CONDITION_KINDS[0]])
        self._builder_param_vars: dict[str, tk.StringVar] = {}
        self._builder_params_frame = None
        self._builder_liste_frame = None
        # [MODIF 2026-08-18] État du sélecteur de broches à cases (kind
        # "connexion_broches") -- {'_any': BooleanVar, 'pin_name': BooleanVar, ...}
        # par côté, reconstruit à chaque changement de type. Cf.
        # _construire_selecteur_broches / _broches_selectionnees.
        self._builder_broches_a: dict = {}
        self._builder_broches_b: dict = {}
        self._builder_meme_composant_var = tk.BooleanVar(value=False)
        # [MODIF 2026-08-19] BUG TROUVÉ EN TESTANT (demande utilisateur : pattern
        # « 1 AOP + 1 photorésistance » matchait quand même un îlot contenant EN
        # PLUS 2 ampoules -- « there is no this option » pour l'interdire). Case
        # décochée par défaut (aucun changement pour les patterns existants) --
        # cochée, un îlot ne matche que s'il ne contient AUCUN composant hors de
        # la liste "components" déclarée. Cf. CustomCircuitPattern._composition_exacte.
        self._composition_exacte_var = tk.BooleanVar(value=False)

        # Widgets de navigation / feedback
        self._btn_prev    = None
        self._btn_next    = None
        self._err_label   = None
        self._step_labels = []        # labels ●●○○

        # Zones de contenu par étape (un seul visible à la fois)
        self._step_frames: dict[int, ctk.CTkFrame] = {}

        # Panneau JSON live
        self._json_box    = None
        self._apercu_canvas = None
        self._apercu_image_label = None

        self._setup_window()
        self._build()
        self._go_to(1)

    # ── Fenêtre ───────────────────────────────────────────────────────────────

    def _setup_window(self):
        """@brief Configure titre, taille et fond de la fenêtre modale."""
        self.title("Nouveau pattern circuit")
        self.geometry("860x540")
        self.resizable(False, False)
        self.configure(fg_color=_BG)
        self.grab_set()   # modal

    # ── Construction générale ─────────────────────────────────────────────────

    def _build(self):
        """@brief Construit header, corps (gauche + droite) et footer."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_body()
        self._build_footer()

    def _build_header(self):
        """@brief Header : titre de l'étape + barre de progression 4 points."""
        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=70)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.grid(row=0, column=0, sticky="ew", padx=24, pady=10)
        inner.grid_columnconfigure(0, weight=1)

        self._title_label = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            text_color=TEXT, anchor="w")
        self._title_label.grid(row=0, column=0, sticky="w")

        # Barre de progression : 4 cercles ●●○○
        prog_frame = ctk.CTkFrame(inner, fg_color="transparent")
        prog_frame.grid(row=0, column=1, sticky="e")
        for i in range(1, 5):
            lbl = ctk.CTkLabel(prog_frame, text="●",
                               font=ctk.CTkFont(size=14),
                               text_color=_STEP_IDLE)
            lbl.pack(side="left", padx=4)
            self._step_labels.append(lbl)

    def _build_body(self):
        """@brief Corps : colonne gauche 600px (contenu) + colonne droite 260px (JSON)."""
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1, minsize=600)
        body.grid_columnconfigure(1, minsize=260)
        body.grid_rowconfigure(0, weight=1)

        # ── Colonne gauche : conteneur des étapes
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=12)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        self._left = left

        # Construire chaque étape (cachée par défaut)
        self._build_step1()
        self._build_step2()
        self._build_step3()
        self._build_step4()

        # ── Colonne droite : panneau JSON live
        right = ctk.CTkFrame(body, fg_color=_JSON_BG,
                             corner_radius=10,
                             border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=12)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="APERÇU JSON",
                     font=ctk.CTkFont("Consolas", 9),
                     text_color=MUTED).grid(row=0, column=0,
                                            sticky="w", padx=10, pady=(8, 2))

        self._json_box = ctk.CTkTextbox(
            right,
            fg_color=_JSON_BG,
            text_color=_JSON_FG,
            font=ctk.CTkFont("Consolas", 9),
            corner_radius=0,
            border_width=0,
            wrap="none",
            state="disabled",
        )
        self._json_box.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 8))

    def _build_footer(self):
        """@brief Footer : message d'erreur + boutons Précédent / Suivant."""
        footer = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=60)
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_propagate(False)
        footer.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(footer, fg_color="transparent")
        inner.grid(row=0, column=0, sticky="ew", padx=24, pady=10)
        inner.grid_columnconfigure(0, weight=1)

        self._err_label = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=_ERR, anchor="w")
        self._err_label.grid(row=0, column=0, sticky="w")

        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")

        self._btn_prev = ctk.CTkButton(
            btn_frame, text="← Précédent",
            width=120, height=36, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color=_BTN_PREV, hover_color=_BTN_PREV_H,
            command=self._prev)
        self._btn_prev.pack(side="left", padx=(0, 8))

        self._btn_next = ctk.CTkButton(
            btn_frame, text="Suivant →",
            width=140, height=36, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            fg_color=_BTN_NEXT, hover_color=_BTN_NEXT_H,
            command=self._next)
        self._btn_next.pack(side="left")

    # ── Étape 1 : Sélection des composants ───────────────────────────────────

    def _build_step1(self):
        """@brief Construit le contenu de l'étape 1 (checkboxes des refs non classifiées)."""
        frame = ctk.CTkScrollableFrame(self._left, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_remove()
        self._step_frames[1] = frame

        for ref in self._unclassified:
            info  = self._comp_info.get(ref, {})
            t     = info.get("type", "?")
            val   = info.get("value", "")
            color = _type_color(t)
            label_txt = _type_label(t, info.get("pins"))

            row_frame = ctk.CTkFrame(frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=4, padx=4)

            var = tk.BooleanVar(value=True)
            self._comp_vars[ref] = var

            cb = ctk.CTkCheckBox(
                row_frame, text=ref,
                variable=var,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=TEXT,
                fg_color=BLUE_D, hover_color=BLUE,
                checkmark_color=TEXT,
                command=self._refresh_json)
            cb.pack(side="left", padx=(4, 10))

            # Badge type
            badge_txt = f"{t} · {label_txt}"
            if val:
                badge_txt += f"  ({val})"
            badge = ctk.CTkLabel(
                row_frame, text=badge_txt,
                font=ctk.CTkFont("Segoe UI", 10),
                text_color=color,
                fg_color=CARD2,
                corner_radius=6,
                padx=6, pady=2)
            badge.pack(side="left")

            # [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (« ma photorésistance est lue
            # comme R-résistance, je ne peux pas le voir/changer ») : le nom réel
            # (Composant.categorie) est maintenant un CHAMP ÉDITABLE, pas juste un
            # libellé figé -- pré-rempli avec ce que l'analyseur a capturé, mais
            # l'utilisateur peut le CORRIGER (ex. un symbole "Résistance" générique
            # réutilisé sans le renommer, ou toute détection jugée fausse) avant de
            # verrouiller l'exigence du pattern dessus (cf. « AOP + photorésistance
            # -> U + R, indiscernable de n'importe quel autre montage U+R »). Case
            # décochée par défaut : comportement inchangé (exigence sur le type seul).
            categorie_init = info.get("categorie") or ""
            cat_var = tk.StringVar(value=categorie_init)
            self._categorie_vars[ref] = cat_var
            lock_var = tk.BooleanVar(value=False)
            self._verrouiller_categorie_vars[ref] = lock_var

            lock_row = ctk.CTkFrame(row_frame, fg_color="transparent")
            lock_row.pack(side="left", padx=(10, 0))
            ctk.CTkCheckBox(
                lock_row, text="exiger précisément :",
                variable=lock_var,
                font=ctk.CTkFont("Segoe UI", 9),
                text_color=MUTED,
                fg_color=BLUE_D, hover_color=BLUE,
                checkmark_color=TEXT,
                checkbox_width=14, checkbox_height=14,
                command=self._refresh_json,
            ).pack(side="left")
            cat_entry = ctk.CTkEntry(
                lock_row, textvariable=cat_var,
                width=150, height=22,
                font=ctk.CTkFont("Segoe UI", 9),
                fg_color=CARD, border_color=BORDER, text_color=TEXT)
            cat_entry.pack(side="left", padx=(4, 0))
            cat_var.trace_add("write", lambda *_: self._refresh_json())

        # [MODIF 2026-08-19] BUG TROUVÉ EN TESTANT (demande utilisateur : pattern
        # « 1 AOP + 1 photorésistance » matchait quand même avec 2 ampoules en
        # plus dans l'îlot) : option pattern-globale, pas par composant --
        # placée après la liste, pas dans chaque ligne.
        exact_frame = ctk.CTkFrame(frame, fg_color="transparent")
        exact_frame.pack(fill="x", pady=(14, 4), padx=4)
        ctk.CTkCheckBox(
            exact_frame, text="Composition exacte : aucun autre composant dans le circuit",
            variable=self._composition_exacte_var,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=TEXT,
            fg_color=BLUE_D, hover_color=BLUE,
            checkmark_color=TEXT,
            command=self._refresh_json,
        ).pack(anchor="w")
        ctk.CTkLabel(
            exact_frame,
            text="Décoché (défaut) : accepte des composants supplémentaires non "
                 "listés ici. Coché : l'îlot ne matche que s'il ne contient AUCUN "
                 "composant en dehors de cette liste (ex. exclut un montage avec "
                 "une lampe ajoutée en plus de l'AOP et de la photorésistance).",
            font=ctk.CTkFont("Segoe UI", 9),
            text_color=MUTED,
            justify="left", wraplength=420,
        ).pack(anchor="w", padx=(28, 0))

    def _composants_requis(self) -> list:
        """@brief Liste "components" du pattern : type seul, ou {'type','categorie'}
        pour toute ref dont la case « exiger précisément » est cochée.

        [MODIF 2026-08-18] Le nom utilisé vient de `self._categorie_vars[ref]`
        (champ ÉDITABLE, pré-rempli depuis comp_info mais corrigeable par
        l'utilisateur), PAS directement de `comp_info` -- cf. « ma photorésistance
        est lue comme R-résistance, je ne peux pas le voir/changer ». Un champ
        vidé par l'utilisateur (case cochée mais texte effacé) retombe sur le
        type seul, jamais une categorie vide silencieuse.

        Dédoublonne en préservant l'ordre de première apparition, comme
        `_selected_types()` -- mais sur la clé (type, categorie_ou_None).

        @return list[str|dict] Prête à sérialiser dans "components".
        """
        seen: list = []
        vus: set = set()
        for ref in self._selected_refs():
            info = self._comp_info.get(ref, {})
            t = info.get("type", "?")
            verrou = self._verrouiller_categorie_vars.get(ref)
            cat_var = self._categorie_vars.get(ref)
            categorie = None
            if verrou and verrou.get() and cat_var:
                texte = cat_var.get().strip()
                categorie = texte or None
            cle = (t, categorie)
            if cle in vus:
                continue
            vus.add(cle)
            seen.append({"type": t, "categorie": categorie} if categorie else t)
        return seen

    # ── Étape 2 : Nom du pattern ──────────────────────────────────────────────

    def _build_step2(self):
        """@brief Construit le contenu de l'étape 2 (champ nom)."""
        frame = ctk.CTkFrame(self._left, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_remove()
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        self._step_frames[2] = frame

        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(inner, text="Nom du circuit",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color=MUTED).pack(anchor="w", pady=(0, 4))

        self._name_entry = ctk.CTkEntry(
            inner,
            textvariable=self._name_var,
            width=480, height=48,
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 16),
            fg_color=CARD, border_color=BORDER,
            text_color=TEXT,
            placeholder_text="ex: Snubber RC, Filtre anti-bruit, Bootstrap...",
        )
        self._name_entry.pack(pady=(0, 6))
        self._name_var.trace_add("write", lambda *_: self._on_name_change())

    # ── Étape 3 : Conditions topologiques ────────────────────────────────────

    def _build_step3(self):
        """@brief Étape 3 : résumé en clair des conditions détectées + repli avancé.

        L'utilisateur n'a normalement rien à faire ici : on affiche en clair ce qui
        distingue son circuit. Les cases techniques sont sous « Options avancées »,
        masquées par défaut.
        """
        frame = ctk.CTkFrame(self._left, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_remove()
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        self._step_frames[3] = frame

        # Résumé en clair (rempli par _apply_suggestions)
        self._summary3 = ctk.CTkLabel(
            frame, text="",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=TEXT, justify="left", anchor="nw")
        self._summary3.grid(row=0, column=0, sticky="ew", padx=6, pady=(2, 10))

        # Bouton de repli des options avancées
        self._advanced_shown = False
        self._btn_advanced = ctk.CTkButton(
            frame, text="▸  Options avancées (ajuster les conditions)",
            anchor="w", height=30, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 11),
            fg_color=CARD2, hover_color=BORDER, text_color=MUTED,
            command=self._toggle_advanced3)
        self._btn_advanced.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 6))

        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.grid(row=2, column=0, sticky="nsew")
        scroll.grid_remove()                      # masqué par défaut
        self._cond_scroll3 = scroll

        # [MODIF 2026-08-19] BUG TROUVÉ EN TESTANT (« les conditions
        # topologiques je les trouve un peu flou ») : les 12 cases et le
        # builder de conditions génériques (ci-dessous) se lisaient comme une
        # seule liste continue, sans indication de quand utiliser lequel.
        # En-tête + regroupement par CONDITION_GROUPS (déjà défini côté
        # loader.py mais jamais consommé par l'UI) pour rendre la structure
        # visible, sans rien changer au moteur en dessous.
        ctk.CTkLabel(scroll, text="CONDITIONS PRÉDÉFINIES",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=MUTED).pack(anchor="w", padx=4, pady=(0, 2))
        ctk.CTkLabel(scroll, text="Cases prêtes à l'emploi pour les cas courants.",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=MUTED, anchor="w").pack(anchor="w", padx=4, pady=(0, 8))

        for nom_groupe, labels_du_groupe in CONDITION_GROUPS:
            ctk.CTkLabel(scroll, text=nom_groupe,
                         font=ctk.CTkFont("Segoe UI", 10, "bold"),
                         text_color=TEXT).pack(anchor="w", padx=4, pady=(8, 2))

            for label in labels_du_groupe:
                var = tk.BooleanVar(value=False)
                self._cond_vars[label] = var

                row = ctk.CTkFrame(scroll, fg_color="transparent")
                row.pack(fill="x", pady=(6, 0), padx=4)

                cb = ctk.CTkCheckBox(
                    row, text=condition_display(label),
                    variable=var,
                    font=ctk.CTkFont("Segoe UI", 11),
                    text_color=TEXT,
                    fg_color=BLUE_D, hover_color=BLUE,
                    checkmark_color=TEXT,
                    command=self._refresh_json)
                cb.pack(side="left")

                # Tag "détecté" affiché à droite (caché par défaut)
                detected_lbl = ctk.CTkLabel(
                    row, text="● détecté",
                    font=ctk.CTkFont("Segoe UI", 9),
                    text_color=_JSON_FG)
                detected_lbl.pack(side="left", padx=8)
                detected_lbl.pack_forget()

                desc = CONDITION_DESCRIPTIONS.get(label, "")
                if desc:
                    ctk.CTkLabel(scroll, text=desc,
                                 font=ctk.CTkFont("Segoe UI", 9),
                                 text_color=MUTED, anchor="w",
                                 justify="left").pack(anchor="w", padx=28, pady=(0, 2))

                var._cb_widget       = cb            # type: ignore[attr-defined]
                var._detected_label  = detected_lbl  # type: ignore[attr-defined]

        self._build_condition_builder(scroll)

    # ── Étape 3bis : builder de condition générique ──────────────────────────
    # [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (« les conditions sont vieilles,
    # aucune possibilité d'en ajouter ») : les 12 conditions ci-dessus restent
    # figées (code Python). Ce builder compose une NOUVELLE condition depuis des
    # briques réutilisables (kind + type de composant + broche + cible) sans
    # toucher au code -- cf. custom_circuits.loader._evaluer_condition_generique.

    def _build_condition_builder(self, parent):
        """@brief Section « Ajouter une condition personnalisée » (fin de l'étape 3)."""
        ctk.CTkFrame(parent, height=1, fg_color=BORDER).pack(
            fill="x", padx=4, pady=(14, 10))
        ctk.CTkLabel(parent, text="AJOUTER UNE CONDITION PERSONNALISÉE",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=MUTED).pack(anchor="w", padx=4, pady=(0, 2))
        ctk.CTkLabel(parent,
                     text="Pour un cas non couvert ci-dessus, composez votre propre condition.",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=MUTED, anchor="w").pack(anchor="w", padx=4, pady=(0, 6))

        kind_row = ctk.CTkFrame(parent, fg_color="transparent")
        kind_row.pack(fill="x", padx=4, pady=(0, 2))
        ctk.CTkLabel(kind_row, text="Type de condition :",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=TEXT).pack(side="left", padx=(0, 8))
        kind_menu = ctk.CTkOptionMenu(
            kind_row, variable=self._builder_kind_var,
            values=[CONDITION_KIND_LABELS[k] for k in CONDITION_KINDS],
            width=340, height=30,
            command=lambda *_: self._rebuild_builder_params())
        kind_menu.pack(side="left")

        self._builder_kind_desc = ctk.CTkLabel(
            parent, text="", font=ctk.CTkFont("Segoe UI", 9),
            text_color=MUTED, anchor="w", justify="left", wraplength=520)
        self._builder_kind_desc.pack(anchor="w", padx=4, pady=(2, 8))

        self._builder_params_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._builder_params_frame.pack(fill="x", padx=4, pady=(0, 8))

        # Erreurs de validation affichées dans le footer commun (self._err_label,
        # via _show_error) -- toujours visible, pas besoin de scroller jusqu'ici.
        ctk.CTkButton(
            parent, text="+  Ajouter cette condition",
            height=32, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            fg_color=BLUE_D, hover_color=BLUE,
            command=self._ajouter_condition_perso,
        ).pack(anchor="w", padx=4, pady=(0, 10))

        self._builder_liste_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._builder_liste_frame.pack(fill="x", padx=4)

        self._rebuild_builder_params()
        self._refresh_conditions_perso_liste()

    def _kind_selectionne(self) -> str:
        """@brief Clé stable ("kind") du type de condition choisi dans le menu."""
        libelle = self._builder_kind_var.get()
        for k in CONDITION_KINDS:
            if CONDITION_KIND_LABELS[k] == libelle:
                return k
        return CONDITION_KINDS[0]

    def _types_disponibles(self) -> list[str]:
        """@brief Types de composants présents sur le schéma analysé (pour les menus).

        [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (« je ne peux pas voir/choisir
        ma photorésistance dans nom précis ») : 'X' (non classifié) était exclu
        ici -- exactement le type d'une photorésistance (aucune forme/nom
        dédiés dans le catalogue électrique). Ça empêchait de sélectionner 'X'
        comme type dans le builder de condition, donc `_categories_pour_type`
        n'était jamais interrogé pour lui : son nom réel restait invisible
        alors que l'étape 1 (case « exiger précisément ») le proposait déjà
        très bien pour ce même type. Exclusion retirée -- cohérent avec
        l'étape 1, qui n'a jamais exclu 'X'.
        """
        types = sorted({info.get("type") for info in self._comp_info.values()
                       if info.get("type")})
        return types or ["R"]

    def _broches_pour_type(self, type_comp: str) -> list[str]:
        """@brief Noms de broches observés pour un type de composant donné."""
        broches: set = set()
        for info in self._comp_info.values():
            if info.get("type") == type_comp:
                broches.update((info.get("pins") or {}).keys())
        return sorted(broches) or ["1"]

    def _categories_pour_type(self, type_comp: str) -> list[str]:
        """@brief Noms réels (Composant.categorie) distincts observés pour un type.

        [MODIF 2026-08-18] cf. « AOP + photorésistance -> U + R, indiscernable » :
        permet à une condition du builder de filtrer sur le nom précis, pas
        seulement le type électrique (ex. "R" ne suffit pas à isoler la
        photorésistance d'une résistance ordinaire).

        @param type_comp Lettre de type ('R', 'D'...).
        @return list[str] Noms réels distincts, triés.
        """
        return sorted({info.get("categorie") for info in self._comp_info.values()
                       if info.get("type") == type_comp and info.get("categorie")})

    def _ajouter_ligne_categorie(self, type_var: tk.StringVar, cle: str, parent=None):
        """@brief Ajoute une ligne « Nom précis (optionnel) » liée à `type_var`.

        Stocke le choix dans `self._builder_param_vars[cle]` ; se reconstruit
        automatiquement quand `type_var` change (mêmes noms réels que ce type-là).

        @param type_var Variable du menu "Type" dont dépendent les noms proposés.
        @param cle Clé sous laquelle stocker la variable dans `_builder_param_vars`.
        @param parent [MODIF 2026-08-18] Conteneur parent (par défaut
            `self._builder_params_frame`) -- nécessaire pour un côté B qui se
            reconstruit dans son propre sous-cadre (cf. kind "connexion_broches").
        """
        parent = parent if parent is not None else self._builder_params_frame
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text="Nom précis (optionnel) :",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=TEXT, width=170, anchor="w").pack(side="left")
        choix = ["(n'importe lequel)"] + self._categories_pour_type(type_var.get())
        var = tk.StringVar(value=choix[0])
        menu = ctk.CTkOptionMenu(row, variable=var, values=choix, width=220, height=28)
        menu.pack(side="left")
        self._builder_param_vars[cle] = var

        def _sur_type_change(valeur):
            nouvelles = ["(n'importe lequel)"] + self._categories_pour_type(valeur)
            var.set(nouvelles[0])
            menu.configure(values=nouvelles)
        type_var.trace_add("write", lambda *_: _sur_type_change(type_var.get()))

    def _rebuild_builder_params(self):
        """@brief Reconstruit les champs de paramètres pour le "kind" sélectionné."""
        for w in self._builder_params_frame.winfo_children():
            w.destroy()
        self._builder_param_vars.clear()
        self._clear_error()

        kind = self._kind_selectionne()
        self._builder_kind_desc.configure(
            text=CONDITION_KIND_DESCRIPTIONS.get(kind, ""))
        types = self._types_disponibles()

        def _ligne(texte, parent=None):
            # [MODIF 2026-08-18] `parent` optionnel : le côté B de "connexion_broches"
            # a besoin de reconstruire ses lignes dans son propre sous-cadre.
            parent = parent if parent is not None else self._builder_params_frame
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=texte, font=ctk.CTkFont("Segoe UI", 11),
                        text_color=TEXT, width=110, anchor="w").pack(side="left")
            return row

        def _menu(row, valeurs, defaut, command=None):
            var = tk.StringVar(value=defaut)
            ctk.CTkOptionMenu(row, variable=var, values=valeurs,
                              width=180, height=28, command=command).pack(side="left")
            return var

        if kind == "broche_vers_rail":
            r1 = _ligne("Type :")
            self._builder_param_vars["type"] = _menu(r1, types, types[0])
            self._ajouter_ligne_categorie(self._builder_param_vars["type"], "categorie")
            r2 = _ligne("Broche :")
            broche_choix = ["(n'importe laquelle)"] + self._broches_pour_type(types[0])
            self._builder_param_vars["broche"] = _menu(r2, broche_choix, broche_choix[0])

            def _sur_type_change(valeur):
                nouvelles = ["(n'importe laquelle)"] + self._broches_pour_type(valeur)
                self._builder_param_vars["broche"].set(nouvelles[0])
                menu_widget = r2.winfo_children()[-1]
                menu_widget.configure(values=nouvelles)
            self._builder_param_vars["type"].trace_add(
                "write", lambda *_: _sur_type_change(self._builder_param_vars["type"].get()))

            r3 = _ligne("Rail :")
            self._builder_param_vars["rail"] = _menu(r3, ["Masse", "Alimentation"], "Masse")

        elif kind == "au_moins_n":
            r1 = _ligne("Type :")
            self._builder_param_vars["type"] = _menu(r1, types, types[0])
            self._ajouter_ligne_categorie(self._builder_param_vars["type"], "categorie")
            # [MODIF 2026-08-18] Comparateur ajouté (au lieu du seul ">=" implicite
            # d'avant) -- absent d'une condition sauvegardée AVANT cet ajout, le
            # backend retombe alors sur ">=" (cf. custom_circuits.loader).
            r_cmp = _ligne("Comparateur :")
            self._builder_param_vars["comparateur_txt"] = _menu(
                r_cmp, _COMPARATEUR_LABELS, _COMPARATEUR_LABELS[0])
            r2 = _ligne("Nombre :")
            var_n = tk.StringVar(value="2")
            ctk.CTkEntry(r2, textvariable=var_n, width=80, height=28).pack(side="left")
            self._builder_param_vars["n"] = var_n

        elif kind == "meme_noeud":
            r1 = _ligne("Type 1 :")
            self._builder_param_vars["type1"] = _menu(r1, types, types[0])
            r2 = _ligne("Type 2 :")
            defaut2 = types[1] if len(types) > 1 else types[0]
            self._builder_param_vars["type2"] = _menu(r2, types, defaut2)

        elif kind == "en_serie":
            r1 = _ligne("Type :")
            self._builder_param_vars["type"] = _menu(r1, types, types[0])
            self._ajouter_ligne_categorie(self._builder_param_vars["type"], "categorie")

        elif kind == "en_parallele":
            # [MODIF 2026-08-18] Lot « we are very limited, add all the possible
            # pattern of a schema » : complément d'en_serie -- deux composants qui
            # partagent leurs DEUX broches (pas juste un nœud, cf. meme_noeud).
            # Types 1 et 2 volontairement PAS forcés différents (contrairement à
            # meme_noeud) : le cas le plus courant est "deux R en parallèle", même
            # type, deux instances.
            r1 = _ligne("Type 1 :")
            self._builder_param_vars["type1"] = _menu(r1, types, types[0])
            self._ajouter_ligne_categorie(self._builder_param_vars["type1"], "categorie1")
            r2 = _ligne("Type 2 :")
            self._builder_param_vars["type2"] = _menu(r2, types, types[0])
            self._ajouter_ligne_categorie(self._builder_param_vars["type2"], "categorie2")

        elif kind == "broche_non_connectee":
            r1 = _ligne("Type :")
            self._builder_param_vars["type"] = _menu(r1, types, types[0])
            self._ajouter_ligne_categorie(self._builder_param_vars["type"], "categorie")
            r2 = _ligne("Broche :")
            broche_choix = ["(n'importe laquelle)"] + self._broches_pour_type(types[0])
            self._builder_param_vars["broche"] = _menu(r2, broche_choix, broche_choix[0])

            def _sur_type_change_nc(valeur):
                nouvelles = ["(n'importe laquelle)"] + self._broches_pour_type(valeur)
                self._builder_param_vars["broche"].set(nouvelles[0])
                r2.winfo_children()[-1].configure(values=nouvelles)
            self._builder_param_vars["type"].trace_add(
                "write", lambda *_: _sur_type_change_nc(self._builder_param_vars["type"].get()))

        elif kind == "valeur_compare":
            r1 = _ligne("Type :")
            self._builder_param_vars["type"] = _menu(r1, types, types[0])
            self._ajouter_ligne_categorie(self._builder_param_vars["type"], "categorie")
            r_cmp = _ligne("Comparateur :")
            self._builder_param_vars["comparateur_txt"] = _menu(
                r_cmp, _COMPARATEUR_LABELS, _COMPARATEUR_LABELS[0])
            r2 = _ligne("Seuil :")
            var_seuil = tk.StringVar(value="10k")
            ctk.CTkEntry(r2, textvariable=var_seuil, width=100, height=28).pack(side="left")
            ctk.CTkLabel(r2, text="(ex: 10k, 100n, 4.7k)",
                        font=ctk.CTkFont("Segoe UI", 9),
                        text_color=MUTED).pack(side="left", padx=(6, 0))
            self._builder_param_vars["seuil_txt"] = var_seuil

        elif kind == "meme_valeur":
            r1 = _ligne("Type 1 :")
            self._builder_param_vars["type1"] = _menu(r1, types, types[0])
            self._ajouter_ligne_categorie(self._builder_param_vars["type1"], "categorie1")
            r2 = _ligne("Type 2 :")
            self._builder_param_vars["type2"] = _menu(r2, types, types[0])
            self._ajouter_ligne_categorie(self._builder_param_vars["type2"], "categorie2")

        elif kind == "nombre_broches":
            r1 = _ligne("Type :")
            self._builder_param_vars["type"] = _menu(r1, types, types[0])
            self._ajouter_ligne_categorie(self._builder_param_vars["type"], "categorie")
            r_cmp = _ligne("Comparateur :")
            self._builder_param_vars["comparateur_txt"] = _menu(
                r_cmp, _COMPARATEUR_LABELS, _COMPARATEUR_LABELS[0])
            r2 = _ligne("Nombre de broches :")
            var_n = tk.StringVar(value="8")
            ctk.CTkEntry(r2, textvariable=var_n, width=80, height=28).pack(side="left")
            self._builder_param_vars["n"] = var_n

        elif kind == "type_absent":
            r1 = _ligne("Type :")
            self._builder_param_vars["type"] = _menu(r1, types, types[0])

        elif kind == "contre_reaction":
            r1 = _ligne("Type :")
            self._builder_param_vars["type"] = _menu(r1, types, types[0])
            self._ajouter_ligne_categorie(self._builder_param_vars["type"], "categorie")
            broches0 = self._broches_pour_type(types[0])
            r2 = _ligne("Broche source :")
            self._builder_param_vars["broche_source"] = _menu(r2, broches0, broches0[0])
            r3 = _ligne("Broche cible :")
            defaut_cible = broches0[1] if len(broches0) > 1 else broches0[0]
            self._builder_param_vars["broche_cible"] = _menu(r3, broches0, defaut_cible)

            def _sur_type_change_cr(valeur):
                nouvelles = self._broches_pour_type(valeur)
                self._builder_param_vars["broche_source"].set(nouvelles[0])
                r2.winfo_children()[-1].configure(values=nouvelles)
                cible = nouvelles[1] if len(nouvelles) > 1 else nouvelles[0]
                self._builder_param_vars["broche_cible"].set(cible)
                r3.winfo_children()[-1].configure(values=nouvelles)
            self._builder_param_vars["type"].trace_add(
                "write", lambda *_: _sur_type_change_cr(self._builder_param_vars["type"].get()))

        elif kind == "connexion_broches":
            # [MODIF 2026-08-18] Condition générique demandée par l'utilisateur :
            # « choisir les broches d'un composant et à quoi elles sont reliées,
            # broche par broche, y compris entre deux broches du MÊME composant ».
            # [MODIF 2026-08-18] Lot « add more costomation ... 1 to a lot of pins
            # or this one should never be connected to this » : "Sens" (une
            # connexion attendue, ou au contraire une connexion INTERDITE) placé
            # tout en haut -- s'applique à toute la condition, pas à un seul côté.
            r_sens = _ligne("Sens :")
            self._builder_param_vars["sens_txt"] = _menu(
                r_sens, _SENS_LABELS, _SENS_LABELS[0])

            ctk.CTkLabel(self._builder_params_frame, text="Côté A",
                         font=ctk.CTkFont("Segoe UI", 10, "bold"),
                         text_color=MUTED).pack(anchor="w", pady=(4, 2))
            ra = _ligne("Type :")
            self._builder_param_vars["type_a"] = _menu(ra, types, types[0])
            self._ajouter_ligne_categorie(self._builder_param_vars["type_a"], "categorie_a")
            self._construire_selecteur_broches(
                self._builder_params_frame, self._builder_param_vars["type_a"],
                self._builder_broches_a, "Broches côté A :")
            # "Mode" (une suffit / toutes exigées) n'a de sens QUE si plusieurs
            # broches sont sélectionnées côté A ("n'importe laquelle" cochée =
            # broches=[] côté backend, "toutes les broches du composant" --
            # ambigu à combiner avec "toutes exigées" -- champ affiché quand
            # même, comportement par défaut ("au_moins_une") s'applique aussi
            # dans ce cas, cf. custom_circuits.loader.).
            r_mode = _ligne("Mode côté A :")
            self._builder_param_vars["mode_a_txt"] = _menu(
                r_mode, _MODE_BROCHES_LABELS, _MODE_BROCHES_LABELS[0])

            ctk.CTkFrame(self._builder_params_frame, height=1, fg_color=BORDER).pack(
                fill="x", pady=(10, 6))
            ctk.CTkLabel(self._builder_params_frame, text="Côté B",
                         font=ctk.CTkFont("Segoe UI", 10, "bold"),
                         text_color=MUTED).pack(anchor="w", pady=(0, 2))

            # [MODIF 2026-08-18] Variable NEUVE à chaque reconstruction (pas
            # `.set(False)` sur l'ancienne) : re-sélectionner ce "kind" après
            # être passé par un autre accumulerait sinon des trace_add() sur
            # le même BooleanVar persistant, avec des fermetures obsolètes
            # pointant vers un `cote_b_frame` déjà détruit -> TclError différée.
            self._builder_meme_composant_var = tk.BooleanVar(value=False)
            toggle_row = ctk.CTkFrame(self._builder_params_frame, fg_color="transparent")
            toggle_row.pack(fill="x", pady=2)

            cote_b_frame = ctk.CTkFrame(self._builder_params_frame, fg_color="transparent")
            cote_b_frame.pack(fill="x")

            def _rebuild_cote_b():
                for w in cote_b_frame.winfo_children():
                    w.destroy()
                if self._builder_meme_composant_var.get():
                    self._construire_selecteur_broches(
                        cote_b_frame, self._builder_param_vars["type_a"],
                        self._builder_broches_b, "Broche(s) reliée(s) (même composant) :")
                else:
                    rb = _ligne("Type :", parent=cote_b_frame)
                    self._builder_param_vars["type_b"] = _menu(rb, types, types[0])
                    self._ajouter_ligne_categorie(
                        self._builder_param_vars["type_b"], "categorie_b", parent=cote_b_frame)
                    self._construire_selecteur_broches(
                        cote_b_frame, self._builder_param_vars["type_b"],
                        self._builder_broches_b, "Broches côté B :")

            ctk.CTkCheckBox(
                toggle_row, text="même composant que côté A (autre broche, pas un 2ème composant)",
                variable=self._builder_meme_composant_var,
                font=ctk.CTkFont("Segoe UI", 10)).pack(anchor="w")
            # [MODIF 2026-08-18] trace_add (pas `command=`) : se déclenche même sur
            # un `.set()` programmatique (tests), cohérent avec `_sur_type_change`
            # ailleurs dans ce fichier -- un `command=` de CTkCheckBox ne se
            # déclenche que sur un vrai clic utilisateur.
            self._builder_meme_composant_var.trace_add(
                "write", lambda *_: _rebuild_cote_b())

            _rebuild_cote_b()

    def _construire_selecteur_broches(self, parent, type_var: tk.StringVar,
                                       stockage: dict, label_text: str = "Broches :"):
        """@brief Sélecteur à cases d'un ensemble OR de broches (+ « n'importe laquelle »).

        [MODIF 2026-08-18] Brique pour le kind "connexion_broches" : l'utilisateur
        coche une ou plusieurs broches (OR -- n'importe laquelle des cochées
        convient), ou laisse « n'importe laquelle » cochée (comportement par
        défaut, équivalent à `broches=[]` côté backend). Se reconstruit
        entièrement à chaque changement de `type_var` (les broches dépendent du
        type choisi).

        @param parent Conteneur CTk parent.
        @param type_var Variable du menu "Type" dont dépendent les broches proposées.
        @param stockage Dict à (re)remplir -- `self._builder_broches_a` ou `_b`.
        @param label_text Libellé affiché devant le sélecteur.
        """
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label_text, font=ctk.CTkFont("Segoe UI", 11),
                     text_color=TEXT, width=170, anchor="w").pack(side="left", anchor="n")

        cases_frame = ctk.CTkFrame(row, fg_color="transparent")
        cases_frame.pack(side="left")

        def _rebuild(*_):
            for w in cases_frame.winfo_children():
                w.destroy()
            stockage.clear()
            any_var = tk.BooleanVar(value=True)
            stockage["_any"] = any_var
            case_widgets: list = []

            def _sur_any_toggle():
                etat = "disabled" if any_var.get() else "normal"
                for cb in case_widgets:
                    cb.configure(state=etat)

            ctk.CTkCheckBox(cases_frame, text="n'importe laquelle", variable=any_var,
                             command=_sur_any_toggle,
                             font=ctk.CTkFont("Segoe UI", 10)).pack(anchor="w")

            for broche in self._broches_pour_type(type_var.get()):
                var = tk.BooleanVar(value=False)
                stockage[broche] = var
                cb = ctk.CTkCheckBox(cases_frame, text=broche, variable=var,
                                      state="disabled",
                                      font=ctk.CTkFont("Segoe UI", 10))
                cb.pack(anchor="w")
                case_widgets.append(cb)

        type_var.trace_add("write", _rebuild)
        _rebuild()

    def _broches_selectionnees(self, stockage: dict) -> list:
        """@brief Lit un sélecteur `_construire_selecteur_broches` -> liste de noms.

        @return list[str] Broches cochées, ou `[]` si « n'importe laquelle »
            (convention partagée avec `custom_circuits.loader` : liste vide =
            pas de filtre sur la broche).
        """
        if stockage.get("_any") is not None and stockage["_any"].get():
            return []
        return [nom for nom, var in stockage.items() if nom != "_any" and var.get()]

    def _condition_perso_depuis_champs(self) -> dict | None:
        """@brief Construit le dict de condition depuis les champs du builder.

        @return dict|None La condition, ou None si un champ requis est invalide.
        """
        kind = self._kind_selectionne()
        v = {k: var.get() for k, var in self._builder_param_vars.items()}
        # [MODIF 2026-08-18] "categorie" optionnelle (cf. _ajouter_ligne_categorie) --
        # présente uniquement pour les "kind" qui l'exposent, "(n'importe lequel)" = pas de filtre.
        categorie = v.get("categorie")
        if categorie == "(n'importe lequel)":
            categorie = None

        if kind == "broche_vers_rail":
            broche = None if v["broche"] == "(n'importe laquelle)" else v["broche"]
            rail = "masse" if v["rail"] == "Masse" else "alimentation"
            return {"kind": kind, "type": v["type"], "categorie": categorie,
                    "broche": broche, "rail": rail}
        if kind == "au_moins_n":
            try:
                n = int(v["n"])
            except ValueError:
                self._show_error("Le nombre doit être un entier.")
                return None
            # [MODIF 2026-08-18] Comparateur ajouté -- 0 devient valide pour "==" /
            # "<=" (ex. "exactement 0" == type_absent, redondant mais pas absurde),
            # seul un compte négatif reste rejeté (jamais valide, quel que soit le
            # comparateur).
            if n < 0:
                self._show_error("Le nombre ne peut pas être négatif.")
                return None
            comparateur = _COMPARATEUR_LABEL_VERS_CLE.get(v.get("comparateur_txt"), ">=")
            return {"kind": kind, "type": v["type"], "categorie": categorie,
                    "n": n, "comparateur": comparateur}
        if kind == "meme_noeud":
            if v["type1"] == v["type2"]:
                self._show_error("Choisissez deux types différents.")
                return None
            return {"kind": kind, "types": [v["type1"], v["type2"]]}
        if kind == "en_serie":
            return {"kind": kind, "type": v["type"], "categorie": categorie}
        if kind == "en_parallele":
            cat1 = v.get("categorie1")
            cat1 = None if cat1 == "(n'importe lequel)" else cat1
            cat2 = v.get("categorie2")
            cat2 = None if cat2 == "(n'importe lequel)" else cat2
            return {"kind": kind, "types": [v["type1"], v["type2"]],
                    "categories": [cat1, cat2]}
        if kind == "broche_non_connectee":
            broche = None if v["broche"] == "(n'importe laquelle)" else v["broche"]
            return {"kind": kind, "type": v["type"], "categorie": categorie,
                    "broche": broche}
        if kind == "valeur_compare":
            from circuit_analyzer.value_parser import parse_valeur
            seuil = parse_valeur(v.get("seuil_txt"))
            if seuil is None:
                self._show_error("Seuil illisible (ex : 10k, 100n, 4.7k).")
                return None
            comparateur = _COMPARATEUR_LABEL_VERS_CLE.get(v.get("comparateur_txt"), ">=")
            return {"kind": kind, "type": v["type"], "categorie": categorie,
                    "comparateur": comparateur, "seuil": seuil}
        if kind == "meme_valeur":
            cat1 = v.get("categorie1")
            cat1 = None if cat1 == "(n'importe lequel)" else cat1
            cat2 = v.get("categorie2")
            cat2 = None if cat2 == "(n'importe lequel)" else cat2
            return {"kind": kind, "types": [v["type1"], v["type2"]],
                    "categories": [cat1, cat2]}
        if kind == "nombre_broches":
            try:
                n = int(v["n"])
            except ValueError:
                self._show_error("Le nombre doit être un entier.")
                return None
            if n < 0:
                self._show_error("Le nombre ne peut pas être négatif.")
                return None
            comparateur = _COMPARATEUR_LABEL_VERS_CLE.get(v.get("comparateur_txt"), ">=")
            return {"kind": kind, "type": v["type"], "categorie": categorie,
                    "comparateur": comparateur, "n": n}
        if kind == "type_absent":
            return {"kind": kind, "types": [v["type"]]}
        if kind == "contre_reaction":
            if v["broche_source"] == v["broche_cible"]:
                self._show_error("Choisissez deux broches différentes.")
                return None
            return {"kind": kind, "type": v["type"], "categorie": categorie,
                    "broche_source": v["broche_source"], "broche_cible": v["broche_cible"]}
        if kind == "connexion_broches":
            categorie_a = v.get("categorie_a")
            if categorie_a == "(n'importe lequel)":
                categorie_a = None
            cote_a = {"type": v["type_a"], "categorie": categorie_a,
                      "broches": self._broches_selectionnees(self._builder_broches_a)}
            # [MODIF 2026-08-18] "mode" -- absent = "au_moins_une", donc omis du
            # dict quand c'est le choix par défaut (JSON plus compact, cohérent
            # avec le reste : un champ optionnel absent = comportement d'origine).
            mode_a = _MODE_BROCHES_LABEL_VERS_CLE.get(v.get("mode_a_txt"), "au_moins_une")
            if mode_a != "au_moins_une":
                cote_a["mode"] = mode_a

            broches_b = self._broches_selectionnees(self._builder_broches_b)
            if self._builder_meme_composant_var.get():
                cote_b = {"meme_composant": True, "broches": broches_b}
            else:
                categorie_b = v.get("categorie_b")
                if categorie_b == "(n'importe lequel)":
                    categorie_b = None
                cote_b = {"type": v.get("type_b"), "categorie": categorie_b,
                          "broches": broches_b}
            cond = {"kind": kind, "cote_a": cote_a, "cote_b": cote_b}
            sens = _SENS_LABEL_VERS_CLE.get(v.get("sens_txt"), "connectee")
            if sens != "connectee":
                cond["sens"] = sens
            return cond
        return None

    def _ajouter_condition_perso(self):
        """@brief Valide, ajoute la condition du builder à la liste, et rafraîchit l'affichage."""
        self._clear_error()
        cond = self._condition_perso_depuis_champs()
        if cond is None:
            return
        if cond in self._conditions_perso:
            self._show_error("Cette condition est déjà ajoutée.")
            return
        self._conditions_perso.append(cond)
        self._refresh_conditions_perso_liste()
        self._refresh_json()

    def _supprimer_condition_perso(self, cond: dict):
        """@brief Retire une condition générique déjà ajoutée."""
        if cond in self._conditions_perso:
            self._conditions_perso.remove(cond)
        self._refresh_conditions_perso_liste()
        self._refresh_json()

    def _refresh_conditions_perso_liste(self):
        """@brief Redessine la liste des conditions personnalisées déjà ajoutées."""
        if self._builder_liste_frame is None:
            return
        for w in self._builder_liste_frame.winfo_children():
            w.destroy()
        if not self._conditions_perso:
            return
        ctk.CTkLabel(self._builder_liste_frame, text="Conditions ajoutées :",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=MUTED).pack(anchor="w", pady=(4, 4))
        for cond in list(self._conditions_perso):
            row = ctk.CTkFrame(self._builder_liste_frame, fg_color=CARD2, corner_radius=6)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=condition_display(cond),
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=TEXT, anchor="w",
                         justify="left", wraplength=440).pack(
                             side="left", padx=8, pady=6, fill="x", expand=True)
            ctk.CTkButton(
                row, text="×", width=26, height=26, corner_radius=6,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                fg_color="transparent", hover_color=_ERR, text_color=MUTED,
                command=lambda c=cond: self._supprimer_condition_perso(c),
            ).pack(side="right", padx=6)

    def _toggle_advanced3(self):
        """@brief Affiche/masque les cases de conditions (options avancées)."""
        self._advanced_shown = not self._advanced_shown
        if self._advanced_shown:
            self._cond_scroll3.grid()
            self._btn_advanced.configure(
                text="▾  Options avancées (ajuster les conditions)")
        else:
            self._cond_scroll3.grid_remove()
            self._btn_advanced.configure(
                text="▸  Options avancées (ajuster les conditions)")

    def _apply_suggestions(self):
        """@brief Détecte les conditions, pré-coche les cases et écrit le résumé clair."""
        refs = self._selected_refs()
        try:
            self._suggested = set(suggest_conditions(self._graph, refs))
        except Exception:
            _log.warning("suggestion de conditions échouée — aucune case "
                         "pré-cochée", exc_info=True)
            self._suggested = set()

        for label, var in self._cond_vars.items():
            detected = label in self._suggested
            var.set(detected)
            cb    = getattr(var, "_cb_widget", None)
            d_lbl = getattr(var, "_detected_label", None)
            if cb is not None:
                cb.configure(text_color=_JSON_FG if detected else TEXT)
            if d_lbl is not None:
                if detected:
                    d_lbl.pack(side="left", padx=8)
                else:
                    d_lbl.pack_forget()

        # Résumé en clair des conditions détectées.
        detectees = [condition_display(l) for l in CONDITION_LABELS
                     if l in self._suggested]
        if detectees:
            self._summary3.configure(
                text="Ce qui distingue ce circuit (détecté automatiquement) :\n"
                     + "\n".join(f"   •  {d}" for d in detectees))
        else:
            self._summary3.configure(
                text="Aucune condition particulière détectée.\n"
                     "Le pattern reconnaîtra tout circuit contenant ces composants.")

    # ── Étape 4 : Prévisualisation ────────────────────────────────────────────

    def _build_step4(self):
        """@brief Construit le contenu de l'étape 4 (aperçu schéma + JSON + bouton Créer)."""
        frame = ctk.CTkFrame(self._left, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_remove()
        frame.grid_rowconfigure(0, weight=2)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        self._step_frames[4] = frame

        self._apercu_frame = ctk.CTkFrame(frame, fg_color=_JSON_BG,
                                          corner_radius=10)
        self._apercu_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        self._preview_box = ctk.CTkTextbox(
            frame,
            fg_color=_JSON_BG,
            text_color=_JSON_FG,
            font=ctk.CTkFont("Consolas", 11),
            corner_radius=10,
            border_width=1, border_color=BORDER,
            wrap="none",
            state="disabled",
        )
        self._preview_box.grid(row=1, column=0, sticky="nsew", pady=(0, 10))

        self._summary_label = ctk.CTkLabel(
            frame, text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=MUTED, justify="left", anchor="w",
            wraplength=560)
        self._summary_label.grid(row=2, column=0, sticky="ew")

        self._btn_create = ctk.CTkButton(
            frame,
            text="Créer le pattern",
            height=42, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=_BTN_CREATE, hover_color=_BTN_CREATE_H,
            command=self._create_pattern)
        self._btn_create.grid(row=3, column=0, sticky="ew", pady=(10, 0))

    # ── Navigation ────────────────────────────────────────────────────────────

    def _go_to(self, step: int):
        """@brief Bascule vers l'étape donnée : masque la courante, affiche la cible.

        @param step Numéro d'étape cible (1–4).
        @return None
        """
        # Masquer toutes les frames
        for f in self._step_frames.values():
            f.grid_remove()

        self._step = step

        # Logique d'entrée dans l'étape
        if step == 3:
            self._apply_suggestions()
        if step == 4:
            self._update_preview()

        # Afficher l'étape cible
        self._step_frames[step].grid(row=0, column=0, sticky="nsew")

        self._update_header()
        self._update_buttons()
        self._refresh_json()

    def _prev(self):
        """@brief Navigue vers l'étape précédente."""
        if self._step > 1:
            self._go_to(self._step - 1)

    def _next(self):
        """@brief Valide l'étape courante puis navigue vers la suivante (si valide)."""
        if not self._validate_current():
            return
        if self._step < 4:
            self._go_to(self._step + 1)

    # ── Titres & UI ──────────────────────────────────────────────────────────

    _TITLES = {
        1: "Quels composants forment ce circuit ?",
        2: "Donnez un nom à ce circuit",
        3: "Conditions de reconnaissance",
        4: "Vérifiez votre pattern avant création",
    }

    def _update_header(self):
        """@brief Met à jour le titre et les 4 points de progression."""
        self._title_label.configure(text=self._TITLES[self._step])
        for i, lbl in enumerate(self._step_labels, start=1):
            if i < self._step:
                color = _STEP_DONE
            elif i == self._step:
                color = _STEP_ACTIVE
            else:
                color = _STEP_IDLE
            lbl.configure(text_color=color)

    def _update_buttons(self):
        """@brief Met à jour l'état des boutons Précédent / Suivant selon l'étape."""
        # Précédent : visible sauf étape 1
        if self._step == 1:
            self._btn_prev.configure(state="disabled")
        else:
            self._btn_prev.configure(state="normal")

        # Étape 4 : le bouton principal est "Créer le pattern" dans le corps
        if self._step == 4:
            self._btn_next.configure(state="disabled", text="Suivant →")
        else:
            label = "Suivant →"
            self._btn_next.configure(text=label)
            self._update_next_state()

    def _update_next_state(self):
        """@brief Active/désactive le bouton Suivant selon l'état de l'étape courante."""
        ok = True
        if self._step == 1:
            ok = any(v.get() for v in self._comp_vars.values())
        elif self._step == 2:
            ok = bool(self._name_var.get().strip())
        self._btn_next.configure(state="normal" if ok else "disabled")

    def _on_name_change(self):
        """@brief Réagit au changement du champ nom (validation + refresh JSON)."""
        self._clear_error()
        if self._step == 2:
            self._update_next_state()
        self._refresh_json()

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate_current(self) -> bool:
        """@brief Valide l'étape courante. Affiche un message d'erreur si invalide.

        @return bool True si l'étape est valide.
        """
        self._clear_error()
        if self._step == 1:
            if not any(v.get() for v in self._comp_vars.values()):
                self._show_error("Sélectionnez au moins un composant.")
                return False
        elif self._step == 2:
            name = self._name_var.get().strip()
            if not name:
                self._show_error("Le nom ne peut pas être vide.")
                return False
            # Vérifier doublon : circuits intégrés (NOMS_CIRCUITS) + personnalisés.
            # Sans le volet intégrés, un pattern pourrait reprendre le nom d'un
            # circuit natif ; la popup schéma (circuit_viewer._supprimer) décide
            # alors "personnalisé" PAR NOM et proposerait un bouton Supprimer sur
            # le circuit intégré, qui supprimerait en fait l'entrée personnalisée
            # homonyme.
            existing = set(NOMS_CIRCUITS) | {
                c.get("name", "") for c in load_custom_circuits()
            }
            if name in existing:
                self._show_error(f"Un pattern nommé « {name} » existe déjà.")
                return False
        return True

    def _show_error(self, msg: str):
        """@brief Affiche un message d'erreur dans le footer.

        @param msg Texte d'erreur.
        @return None
        """
        if self._err_label:
            self._err_label.configure(text=f"⚠  {msg}")

    def _clear_error(self):
        """@brief Efface le message d'erreur du footer."""
        if self._err_label:
            self._err_label.configure(text="")

    # ── Données ──────────────────────────────────────────────────────────────

    def _selected_refs(self) -> list[str]:
        """@brief Liste des refs cochées à l'étape 1.

        @return list[str] Refs sélectionnées.
        """
        return [ref for ref, var in self._comp_vars.items() if var.get()]

    def _selected_types(self) -> list[str]:
        """@brief Types de composants uniques parmi les refs sélectionnées.

        @return list[str] Types (ex: ['R', 'C']).
        """
        seen = []
        for ref in self._selected_refs():
            t = self._comp_info.get(ref, {}).get("type", "?")
            if t not in seen:
                seen.append(t)
        return seen

    def _selected_conditions(self) -> list:
        """@brief Liste des conditions actives : nommées cochées + génériques ajoutées.

        [MODIF 2026-08-18] Étend le résultat aux conditions génériques
        (`self._conditions_perso`, dicts construits par le builder) -- la
        sérialisation JSON (`custom_circuits.json`) accepte nativement une
        liste mélangeant str et dict, donc aucun changement de format requis
        en aval (`_build_pattern_dict`/`_create_pattern` les consomment déjà
        via cette seule méthode).

        @return list[str|dict] Conditions nommées (labels) + génériques (dicts).
        """
        return ([lbl for lbl, var in self._cond_vars.items() if var.get()]
                + list(self._conditions_perso))

    def _dessiner_apercu(self) -> Figure:
        """@brief Apercu schematique simple des composants selectionnes.

        Rendu volontairement simple (spec 2026-08-04) : vrais symboles
        (style_symbole), alignes en ligne, fils droits entre composants
        partageant un net. Pas de gestion rails/branches/compaction — ce
        n'est pas le moteur ilots, une decision explicite du boss.

        @return matplotlib.figure.Figure prete a afficher dans un canvas Tk.
        """
        refs = self._selected_refs()
        fig = Figure(figsize=(6.5, 2.4))
        ax = fig.add_subplot(111)
        fig.patch.set_facecolor(_BG)
        ax.set_facecolor(_BG)
        ax.axis("off")
        ax.set_aspect("equal")
        # Paires (ref_a, ref_b) reliees par un fil, dans l'ordre de trace —
        # meme idiome que fig._z_hitboxes/_comp_positions ailleurs dans le
        # projet : le test inspecte cet etat plutot que de gratter les
        # artistes matplotlib (les symboles eux-memes contiennent deja des
        # segments de ligne, ambigu a distinguer d'un vrai fil par type).
        fig._apercu_connexions = []
        if not refs:
            return fig

        espace = 2.5
        bornes = {}
        with schemdraw.Drawing(canvas=ax, show=False) as d:
            d.config(fontsize=10, inches_per_unit=0.5)
            for i, ref in enumerate(refs):
                info = self._comp_info.get(ref, {})
                typ = info.get("type", "?")
                val = info.get("value", "")
                cls, coul, ref_txt, valeur = style_symbole(typ, val, ref)
                x0, x1 = i * espace, i * espace + 1.5
                el = cls().at((x0, 0)).to((x1, 0)).color(coul).label(
                    ref_txt, loc="bottom", fontsize=9, color=coul)
                if valeur:
                    el = el.label(valeur, loc="top", fontsize=9, color=coul)
                d.add(el)
                bornes[ref] = (x0, x1)

            # Câblage par net : chaîne (non clique) pour éviter que les fils
            # ne traversent les composants intermédiaires.
            # Pour chaque net unique, connecter uniquement les composants
            # CONSÉCUTIFS (dans l'ordre de refs) qui le partagent.
            nets_by_ref = {}
            for ref in refs:
                nets_by_ref[ref] = set((self._comp_info.get(ref, {})
                                       .get("pins") or {}).values())

            # Recenser tous les nets
            all_nets = set()
            for nets_set in nets_by_ref.values():
                all_nets.update(nets_set)

            # Pour chaque net, connecter les composants consécutifs qui le partagent
            for net in all_nets:
                components_on_net = [ref for ref in refs
                                    if net in nets_by_ref[ref]]
                # Connecter chaque composant au suivant (dans l'ordre)
                for j in range(len(components_on_net) - 1):
                    ref_a = components_on_net[j]
                    ref_b = components_on_net[j + 1]
                    _xa0, xa1 = bornes[ref_a]
                    xb0, _xb1 = bornes[ref_b]
                    d.add(elm.Line().at((xa1, 0)).to((xb0, 0))
                          .color("#64748b"))
                    fig._apercu_connexions.append((ref_a, ref_b))
        try:
            fig.tight_layout(pad=0.4)
        except Exception:
            _log.debug("tight_layout ignore", exc_info=True)
        return fig

    def _build_pattern_dict(self) -> dict:
        """@brief Construit le dict JSON du pattern en cours de création.

        Le champ "components" contient les *types* (R, C, Q…), pas les références :
        c'est ce qu'attend CustomCircuitPattern et ce qui est réellement
        sauvegardé par _create_pattern(). L'aperçu reflète donc l'artefact final.

        @return dict Pattern partiel ou complet selon l'étape.
        """
        d: dict = {}
        requis = self._composants_requis()
        if requis:
            d["components"] = requis

        name = self._name_var.get().strip()
        if name:
            d["name"] = name

        conds = self._selected_conditions()
        if conds:
            d["conditions"] = conds

        # [MODIF 2026-08-19] Cf. _composition_exacte_var -- omise (comme sens/mode
        # de connexion_broches) quand décochée, aucun impact sur les patterns
        # existants qui n'ont jamais eu cette clé.
        if self._composition_exacte_var.get():
            d["composition_exacte"] = True

        # Réordonner les clés pour un affichage logique
        ordered: dict = {}
        if "name" in d:
            ordered["name"] = d["name"]
        if "components" in d:
            ordered["components"] = d["components"]
        if "composition_exacte" in d:
            ordered["composition_exacte"] = d["composition_exacte"]
        if "conditions" in d:
            ordered["conditions"] = d["conditions"]
        return ordered

    # ── JSON live ─────────────────────────────────────────────────────────────

    def _refresh_json(self):
        """@brief Met à jour le panneau JSON live (colonne droite)."""
        if self._json_box is None:
            return
        payload = self._build_pattern_dict()
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        self._json_box.configure(state="normal")
        self._json_box.delete("1.0", "end")
        self._json_box.insert("1.0", text)
        self._json_box.configure(state="disabled")

        # Mettre aussi à jour le bouton Suivant si on est sur une étape sensible
        if self._step in (1, 2):
            self._update_next_state()

    # ── Prévisualisation étape 4 ──────────────────────────────────────────────

    def _update_preview(self):
        """@brief Reconstruit l'apercu schematique et met a jour JSON/resume de l'etape 4."""
        if self._apercu_canvas is not None:
            self._apercu_canvas.get_tk_widget().destroy()
            self._apercu_canvas = None
        if self._apercu_image_label is not None:
            self._apercu_image_label.destroy()
            self._apercu_image_label = None

        if self._apercu_image is not None:
            ctk_img = ctk.CTkImage(light_image=self._apercu_image,
                                   dark_image=self._apercu_image,
                                   size=_taille_affichage(self._apercu_image.size))
            self._apercu_image_label = ctk.CTkLabel(
                self._apercu_frame, image=ctk_img, text="")
            self._apercu_image_label.image = ctk_img  # garde une reference (anti-GC)
            self._apercu_image_label.pack(fill="both", expand=True, padx=4, pady=4)
        else:
            fig = self._dessiner_apercu()
            self._apercu_canvas = FigureCanvasTkAgg(fig, master=self._apercu_frame)
            self._apercu_canvas.draw()
            self._apercu_canvas.get_tk_widget().configure(
                bg=_JSON_BG, highlightthickness=0)
            self._apercu_canvas.get_tk_widget().pack(
                fill="both", expand=True, padx=4, pady=4)

        payload = self._build_pattern_dict()
        text = json.dumps(payload, ensure_ascii=False, indent=2)

        self._preview_box.configure(state="normal")
        self._preview_box.delete("1.0", "end")
        self._preview_box.insert("1.0", text)
        self._preview_box.configure(state="disabled")

        requis = self._composants_requis()
        conds = self._selected_conditions()
        type_str = ", ".join(
            r if isinstance(r, str) else f"{r['type']} ({r['categorie']})"
            for r in requis) if requis else "?"
        # [MODIF 2026-08-19] BUG TROUVÉ EN TESTANT (demande utilisateur : « the
        # verification etape the last one before confirmation ... need to be
        # exactly precise on what condition u did ») : l'étape 4 est la DERNIÈRE
        # vérification avant sauvegarde, mais son résumé se limitait à un
        # COMPTE ("avec 3 condition(s)") -- aucun texte des conditions
        # elles-mêmes n'y apparaissait (le détail lisible par condition
        # n'existe qu'à l'étape 3, sous « Options avancées », repliée par
        # défaut). Un utilisateur qui valide directement depuis l'étape 4 ne
        # voyait donc JAMAIS ce que chaque condition signifie concrètement.
        # Le JSON brut au-dessus est exact mais illisible pour un non-développeur.
        # Réutilise `condition_display` (même fonction que la liste de
        # l'étape 3 et le futur onglet Circuits) -- une seule source de vérité,
        # donc aucun risque de divergence entre ce qui est affiché et ce qui
        # sera réellement évalué/sauvegardé.
        if self._composition_exacte_var.get():
            lignes = [f"Ce pattern sera reconnu SEULEMENT dans un circuit contenant "
                      f"EXACTEMENT [{type_str}] — aucun autre composant toléré."]
        else:
            lignes = [f"Ce pattern sera reconnu dans tout circuit contenant [{type_str}]."]
        if conds:
            lignes.append("Conditions exigées :")
            lignes.extend(f"   •  {condition_display(c)}" for c in conds)
        else:
            lignes.append("Aucune condition supplémentaire — matche tout "
                          "circuit contenant ces composants.")
        self._summary_label.configure(text="\n".join(lignes))

    # ── Création finale ───────────────────────────────────────────────────────

    def _create_pattern(self):
        """@brief Sauvegarde le pattern, appelle on_created() et ferme le wizard."""
        self._clear_error()

        name = self._name_var.get().strip()
        if not name:
            self._show_error("Le nom est vide — impossible de créer le pattern.")
            return

        pattern = {
            "name":       name,
            "components": self._composants_requis(),
            "conditions": self._selected_conditions(),
        }
        if self._composition_exacte_var.get():
            pattern["composition_exacte"] = True

        circuits = load_custom_circuits()
        circuits.append(pattern)
        save_custom_circuits(circuits)

        if callable(self._on_created):
            self._on_created()

        self.destroy()
