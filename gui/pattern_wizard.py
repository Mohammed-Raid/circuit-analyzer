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

from custom_circuits.loader import (
    CONDITION_LABELS,
    CONDITION_DESCRIPTIONS,
    condition_display,
    load_custom_circuits,
    save_custom_circuits,
    suggest_conditions,
)
from gui.theme import CARD, CARD2, BORDER, TEXT, MUTED, BLUE, BLUE_D

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
    "X": "Connecteur",
}


def _type_color(t: str) -> str:
    return _TYPE_COLORS.get(t, "#94a3b8")


def _type_label(t: str) -> str:
    return _TYPE_LABELS.get(t, t)


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
                 comp_info: dict, on_created=None):
        super().__init__(parent)

        self._graph       = graph
        self._unclassified = list(unclassified)
        self._comp_info   = comp_info
        self._on_created  = on_created

        # État du wizard
        self._step        = 1          # étape courante (1–4)
        self._comp_vars: dict[str, tk.BooleanVar] = {}
        self._name_var    = tk.StringVar()
        self._cond_vars: dict[str, tk.BooleanVar] = {}
        self._suggested: set[str] = set()  # conditions détectées automatiquement

        # Widgets de navigation / feedback
        self._btn_prev    = None
        self._btn_next    = None
        self._err_label   = None
        self._step_labels = []        # labels ●●○○

        # Zones de contenu par étape (un seul visible à la fois)
        self._step_frames: dict[int, ctk.CTkFrame] = {}

        # Panneau JSON live
        self._json_box    = None

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
            label_txt = _type_label(t)

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

        for label in CONDITION_LABELS:
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
        """@brief Construit le contenu de l'étape 4 (résumé JSON + bouton Créer)."""
        frame = ctk.CTkFrame(self._left, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_remove()
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        self._step_frames[4] = frame

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
        self._preview_box.grid(row=0, column=0, sticky="nsew", pady=(0, 10))

        self._summary_label = ctk.CTkLabel(
            frame, text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=MUTED, justify="left", anchor="w",
            wraplength=560)
        self._summary_label.grid(row=1, column=0, sticky="ew")

        self._btn_create = ctk.CTkButton(
            frame,
            text="Créer le pattern",
            height=42, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=_BTN_CREATE, hover_color=_BTN_CREATE_H,
            command=self._create_pattern)
        self._btn_create.grid(row=2, column=0, sticky="ew", pady=(10, 0))

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
            # Vérifier doublon
            existing = [c.get("name", "") for c in load_custom_circuits()]
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

    def _selected_conditions(self) -> list[str]:
        """@brief Liste des conditions cochées.

        @return list[str] Labels des conditions activées.
        """
        return [lbl for lbl, var in self._cond_vars.items() if var.get()]

    def _build_pattern_dict(self) -> dict:
        """@brief Construit le dict JSON du pattern en cours de création.

        Le champ "components" contient les *types* (R, C, Q…), pas les références :
        c'est ce qu'attend CustomCircuitPattern et ce qui est réellement
        sauvegardé par _create_pattern(). L'aperçu reflète donc l'artefact final.

        @return dict Pattern partiel ou complet selon l'étape.
        """
        d: dict = {}
        types = self._selected_types()
        if types:
            d["components"] = types

        name = self._name_var.get().strip()
        if name:
            d["name"] = name

        conds = self._selected_conditions()
        if conds:
            d["conditions"] = conds

        # Réordonner les clés pour un affichage logique
        ordered: dict = {}
        if "name" in d:
            ordered["name"] = d["name"]
        if "components" in d:
            ordered["components"] = d["components"]
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
        """@brief Met à jour la grande boîte JSON et le résumé texte de l'étape 4."""
        payload = self._build_pattern_dict()
        text = json.dumps(payload, ensure_ascii=False, indent=2)

        self._preview_box.configure(state="normal")
        self._preview_box.delete("1.0", "end")
        self._preview_box.insert("1.0", text)
        self._preview_box.configure(state="disabled")

        types = self._selected_types()
        n_conds = len(self._selected_conditions())
        type_str = ", ".join(types) if types else "?"
        self._summary_label.configure(
            text=f"Ce pattern sera reconnu dans tout circuit contenant "
                 f"[{type_str}] avec {n_conds} condition(s).")

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
            "components": self._selected_types(),
            "conditions": self._selected_conditions(),
        }

        circuits = load_custom_circuits()
        circuits.append(pattern)
        save_custom_circuits(circuits)

        if callable(self._on_created):
            self._on_created()

        self.destroy()
