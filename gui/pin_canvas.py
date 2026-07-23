"""
@file pin_canvas.py
@brief Canevas de brochage de l'onglet « Composants » (spec 2026-07-23).

Repère FIXE : échelle 1, origine au centre du canevas. Aucun zoom, aucun pan —
c'est ce qui permet de ne PAS embarquer `SchematicEditor` (palette, câblage,
undo, export) pour un simple placement de broches.

Le brochage est une LISTE ordonnée `[(nom, côté, décalage), …]` : l'ordre EST
la donnée de la netlist (cf. `saisie.py:_broches_du_type` et `to_netlist`), et
les positions n'en dépendent pas.
"""
import tkinter as tk

import customtkinter as ctk

from gui.schematic_symbols import (AUTO_COLOR, TYPE_LIBRE, aimanter_bord,
                                   geometrie_libre, primitives)
from gui.theme import CARD2, TEXT_MUTED

GRILLE = 20
_R_BROCHE = 5
_R_CLIC = 12
_PIN_OFF = "#ef4444"
_FOND = "#0f172a"


class PinCanvas(ctk.CTkFrame):
    """@brief Placement des broches d'un TYPE à la souris.

    @param on_change Callback appelé après toute mutation, avec le brochage.
    """

    def __init__(self, parent, on_change=None, hauteur=260):
        super().__init__(parent, fg_color=CARD2)
        self._on_change = on_change
        self._brochage: list = []          # [(nom, côté, décalage)] ORDONNÉ
        self._lecture_seule = False
        self._selection = None
        self._cv = tk.Canvas(self, height=hauteur, highlightthickness=0,
                             bg=_FOND)
        self._cv.pack(fill="both", expand=True, padx=8, pady=8)
        self._cv.bind("<Configure>", lambda _e: self._dessiner())

    # ── API publique ────────────────────────────────────────────────────────

    def charger(self, brochage: list, lecture_seule: bool = False):
        """@brief Remplace le brochage affiché (liste ordonnée de tuples)."""
        self._brochage = [tuple(b) for b in brochage]
        self._lecture_seule = lecture_seule
        self._selection = None
        self._dessiner()

    def brochage(self) -> list:
        """@brief Brochage courant, dans l'ordre (= ordre de la netlist)."""
        return list(self._brochage)

    # ── Géométrie ───────────────────────────────────────────────────────────

    def _defn(self) -> dict:
        """@brief Def de boîte auto-ajustée, via la fonction pure partagée."""
        return geometrie_libre({n: (c, d) for n, c, d in self._brochage})

    def _centre(self) -> tuple:
        return (self._cv.winfo_width() // 2, self._cv.winfo_height() // 2)

    def _nom_libre(self) -> str:
        """@brief Plus petit entier >= 1 non utilisé (une suppression se recycle)."""
        pris = {n for n, _c, _d in self._brochage}
        i = 1
        while str(i) in pris:
            i += 1
        return str(i)

    # ── Mutations ───────────────────────────────────────────────────────────

    def _ajouter(self, wx, wy):
        """@brief Ajoute une broche aimantée au bord le plus proche.

        @param wx,wy Coordonnées dans le repère BOÎTE (origine au centre).
        @return Nom attribué, ou None en lecture seule.
        """
        if self._lecture_seule:
            return None
        d = self._defn()
        nom = self._nom_libre()
        cote, dec = aimanter_bord(wx, wy, d["w"], d["h"], GRILLE)
        self._brochage.append((nom, cote, dec))     # toujours EN FIN
        self._muter()
        return nom

    def _muter(self):
        """@brief Redessine et notifie le parent (état du formulaire)."""
        self._dessiner()
        if self._on_change:
            self._on_change(self.brochage())

    # ── Dessin ──────────────────────────────────────────────────────────────

    def _dessiner(self):
        self._cv.delete("all")
        cx, cy = self._centre()
        if cx <= 1:
            return                      # widget pas encore dimensionné
        d = self._defn()
        for p in primitives(TYPE_LIBRE, d, 0):
            if p[0] == "polygon":
                pts = [c for x, y in p[1] for c in (cx + x, cy + y)]
                self._cv.create_polygon(*pts, fill="", outline=AUTO_COLOR,
                                        width=2)
            elif p[0] == "text":
                self._cv.create_text(cx + p[1][0], cy + p[1][1], text=p[2],
                                     fill=TEXT_MUTED,
                                     font=("Consolas", 8),
                                     anchor={"e": "e", "w": "w"}.get(p[4],
                                                                     "center"))
        for nom, (px, py) in d["pins"].items():
            x, y = cx + px, cy + py
            contour = AUTO_COLOR if nom == self._selection else _PIN_OFF
            self._cv.create_oval(x - _R_BROCHE, y - _R_BROCHE,
                                 x + _R_BROCHE, y + _R_BROCHE,
                                 fill=_FOND, outline=contour, width=2,
                                 tags=(f"broche_{nom}",))
