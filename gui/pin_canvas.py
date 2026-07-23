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
                                   geometrie_libre, modele_brochage,
                                   primitives)
from gui.theme import CARD2, OVERLAY, TEXT, TEXT_MUTED

GRILLE = 20
_R_BROCHE = 5
_R_CLIC = 12
_PIN_OFF = "#ef4444"
_FOND = "#0f172a"


class PinCanvas(ctk.CTkFrame):
    """@brief Placement des broches d'un TYPE à la souris.

    @param on_change Callback appelé après toute mutation, avec le brochage.
    """

    def __init__(self, parent, on_change=None, hauteur=190):
        # 190 et non 260 : à 260, le bandeau d'ordre tombait sous la zone
        # visible du formulaire défilant — invisible alors qu'il porte l'ordre
        # de la netlist (défaut trouvé en boucle visuelle, 2026-07-23).
        super().__init__(parent, fg_color=CARD2)
        self._on_change = on_change
        self._brochage: list = []          # [(nom, côté, décalage)] ORDONNÉ
        self._lecture_seule = False
        self._selection = None
        self._glisse_depuis = None
        self._pastilles: list = []
        self._roles: dict = {}          # {nom: role} — clef `fonctions`
        self._w_mini = self._h_mini = None
        self._cv = tk.Canvas(self, height=hauteur, highlightthickness=0,
                             bg=_FOND)
        self._cv.pack(fill="both", expand=True, padx=8, pady=8)
        self._cv.bind("<Configure>", lambda _e: self._dessiner())
        self._cv.bind("<Button-1>", self._sur_clic)
        self._cv.bind("<B1-Motion>", self._sur_glisse)
        self._cv.bind("<Double-Button-1>", self._sur_double_clic)
        self._cv.bind("<Delete>", self._sur_suppr)
        self._cv.configure(takefocus=1)
        # Champ de nom CHAÎNÉ : Entrée valide et passe à la broche suivante,
        # pour nommer huit broches sans ouvrir huit fenêtres.
        ligne = ctk.CTkFrame(self, fg_color="transparent")
        ligne.pack(fill="x", padx=8, pady=(0, 4))
        ctk.CTkLabel(ligne, text="Nom :", font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED).pack(side="left", padx=(0, 6))
        self._nom_var = tk.StringVar()
        self._champ_nom = ctk.CTkEntry(ligne, textvariable=self._nom_var,
                                       width=160, height=28,
                                       font=ctk.CTkFont("Consolas", 11))
        self._champ_nom.pack(side="left")
        self._champ_nom.bind("<Return>",
                             lambda _e: self._valider_nom(self._nom_var.get()))
        ctk.CTkLabel(ligne, text="Entrée = valider et passer à la suivante",
                     font=ctk.CTkFont(size=10),
                     text_color=TEXT_MUTED).pack(side="left", padx=8)
        self._bandeau = ctk.CTkFrame(self, fg_color="transparent")
        self._bandeau.pack(fill="x", padx=8, pady=(0, 8))
        self._construire_bandeau()

    # ── API publique ────────────────────────────────────────────────────────

    def charger(self, brochage: list, lecture_seule: bool = False,
                roles: dict = None, w_mini=None, h_mini=None):
        """@brief Remplace le brochage affiché (liste ordonnée de tuples).

        @param roles        {nom: rôle} — affiché « nom RÔLE » dans le symbole.
        @param w_mini,h_mini Taille PLANCHER voulue (None = auto-ajustement).
        """
        self._brochage = [tuple(b) for b in brochage]
        self._roles = dict(roles or {})
        self._w_mini, self._h_mini = w_mini, h_mini
        self._lecture_seule = lecture_seule
        self._selection = None
        self._dessiner()
        self._construire_bandeau()
        self._sync_champ()

    def brochage(self) -> list:
        """@brief Brochage courant, dans l'ordre (= ordre de la netlist)."""
        return list(self._brochage)

    # ── Géométrie ───────────────────────────────────────────────────────────

    def roles(self) -> dict:
        """@brief {nom: rôle} des broches renseignées (rôles vides omis)."""
        return {n: r for n, r in self._roles.items() if r}

    def _defn(self) -> dict:
        """@brief Def de boîte auto-ajustée, via la fonction pure partagée."""
        return geometrie_libre({n: (c, d) for n, c, d in self._brochage},
                               self._w_mini, self._h_mini, self.roles())

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

    def _broche_a(self, wx, wy):
        """@brief Nom de la broche sous (wx,wy) en repère BOÎTE, sinon None."""
        for nom, (px, py) in self._defn()["pins"].items():
            if (wx - px) ** 2 + (wy - py) ** 2 <= _R_CLIC ** 2:
                return nom
        return None

    def _index(self, nom):
        for i, (n, _c, _d) in enumerate(self._brochage):
            if n == nom:
                return i
        return -1

    def _deplacer(self, nom, wx, wy):
        """@brief Fait coulisser une broche.

        L'ORDRE ne change pas : position à l'écran et rang dans la netlist sont
        deux données indépendantes (c'est le bandeau qui règle le rang).
        """
        if self._lecture_seule:
            return
        i = self._index(nom)
        if i < 0:
            return
        d = self._defn()
        cote, dec = aimanter_bord(wx, wy, d["w"], d["h"], GRILLE)
        self._brochage[i] = (nom, cote, dec)
        self._muter()

    def _renommer(self, ancien, nouveau) -> bool:
        """@brief Renomme une broche EN PLACE (son rang ne bouge pas).

        @return False si le nom est vide ou déjà pris.
        """
        if self._lecture_seule:
            return False
        nouveau = (nouveau or "").strip()
        i = self._index(ancien)
        if i < 0 or not nouveau:
            return False
        if any(n == nouveau for n, _c, _d in self._brochage):
            return False
        _n, cote, dec = self._brochage[i]
        self._brochage[i] = (nouveau, cote, dec)
        if self._selection == ancien:
            self._selection = nouveau
        self._muter()
        return True

    def _supprimer(self, nom):
        """@brief Retire une broche (les suivantes remontent d'un rang)."""
        if self._lecture_seule:
            return
        i = self._index(nom)
        if i < 0:
            return
        self._brochage.pop(i)
        if self._selection == nom:
            self._selection = None
        self._muter()

    def _selection_suivante(self):
        """@brief Avance la sélection d'un rang, en bouclant sur la première."""
        if not self._brochage:
            self._selection = None
            return
        i = self._index(self._selection)
        self._selection = self._brochage[(i + 1) % len(self._brochage)][0]

    def _valider_nom(self, nouveau) -> bool:
        """@brief Renomme la broche sélectionnée PUIS passe à la suivante.

        C'est tout l'intérêt du champ chaîné. Un refus (nom vide ou déjà pris)
        NE FAIT PAS avancer : sinon on perdrait la broche qu'on essayait de
        nommer, et on ne s'en apercevrait que plusieurs broches plus loin.
        """
        if not self._selection:
            return False
        if not self._renommer(self._selection, nouveau):
            return False
        self._selection_suivante()
        self._sync_champ()
        self._dessiner()
        return True

    def _sync_champ(self):
        """@brief Recopie dans le champ le nom de la broche sélectionnée."""
        if not hasattr(self, "_nom_var"):
            return
        self._nom_var.set(self._selection or "")
        etat = "disabled" if self._lecture_seule else "normal"
        self._champ_nom.configure(state=etat)

    def _reordonner(self, depuis: int, vers: int):
        """@brief Déplace la broche de rang `depuis` au rang `vers`.

        L'ordre est la donnée de la NETLIST ; les positions à l'écran n'en
        dépendent pas et ne bougent donc pas.
        """
        if self._lecture_seule:
            return
        n = len(self._brochage)
        if not (0 <= depuis < n) or not (0 <= vers < n) or depuis == vers:
            return
        self._brochage.insert(vers, self._brochage.pop(depuis))
        self._muter()

    def _poser_groupe(self, cote: str, n: int) -> list:
        """@brief Pose n broches espacées sur un côté, ajoutées EN FIN.

        @return Noms attribués, dans l'ordre.
        """
        if self._lecture_seule:
            return []
        n = int(n)
        y0 = -((n - 1) * GRILLE) // 2
        y0 -= y0 % GRILLE
        noms = []
        for i in range(n):
            nom = self._nom_libre()
            self._brochage.append((nom, cote, y0 + i * GRILLE))
            noms.append(nom)
        self._muter()
        return noms

    def poser_modele(self, modele: str, n: int):
        """@brief REMPLACE le brochage par celui d'un boîtier type.

        Destructif : l'appelant demande confirmation si le brochage courant
        n'est pas vide.
        """
        if self._lecture_seule:
            return
        self._brochage = list(modele_brochage(modele, n))
        self._roles = {}
        self._selection = None
        self._muter()

    def _muter(self):
        """@brief Redessine, reconstruit le bandeau et notifie le parent."""
        self._dessiner()
        self._construire_bandeau()
        self._sync_champ()
        if self._on_change:
            self._on_change(self.brochage())

    # ── Bandeau d'ordre ─────────────────────────────────────────────────────

    def _construire_bandeau(self):
        """@brief Pastilles dans l'ORDRE de la netlist, réordonnables au glisser."""
        for w in self._bandeau.winfo_children():
            w.destroy()
        self._pastilles = []
        ctk.CTkLabel(self._bandeau, text="Ordre (netlist) :",
                     font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED).pack(side="left", padx=(0, 6))
        for i, (nom, _c, _d) in enumerate(self._brochage):
            # Fond CONTRASTÉ avec la carte : sans lui, la pastille ressemble à
            # du texte inerte et rien ne dit qu'elle se glisse.
            p = ctk.CTkLabel(self._bandeau, text=nom, fg_color=OVERLAY,
                             corner_radius=6, padx=8, text_color=TEXT,
                             font=ctk.CTkFont("Consolas", 11))
            p.configure(cursor="hand2" if not self._lecture_seule else "")
            p.pack(side="left", padx=2)
            if not self._lecture_seule:
                p.bind("<Button-1>", lambda _e, k=i: self._debut_glisse(k))
                p.bind("<ButtonRelease-1>", self._fin_glisse)
            self._pastilles.append(p)

    def _debut_glisse(self, index):
        self._glisse_depuis = index

    def _fin_glisse(self, event):
        """@brief Dépose : la pastille sous le curseur donne le rang cible."""
        if self._glisse_depuis is None:
            return
        cible = self._pastille_sous(event.x_root, event.y_root)
        if cible is not None:
            self._reordonner(self._glisse_depuis, cible)
        self._glisse_depuis = None

    def _pastille_sous(self, x_root, y_root):
        """@brief Rang de la pastille aux coordonnées écran données, sinon None."""
        for i, p in enumerate(self._pastilles):
            x0, y0 = p.winfo_rootx(), p.winfo_rooty()
            if (x0 <= x_root <= x0 + p.winfo_width()
                    and y0 <= y_root <= y0 + p.winfo_height()):
                return i
        return None

    # ── Souris / clavier ────────────────────────────────────────────────────

    def _boite(self, event):
        """@brief Événement écran -> coordonnées repère BOÎTE."""
        cx, cy = self._centre()
        return event.x - cx, event.y - cy

    def _sur_clic(self, event):
        """@brief Clic SUR une broche = sélection ; clic ailleurs = nouvelle broche."""
        self._cv.focus_set()
        wx, wy = self._boite(event)
        touchee = self._broche_a(wx, wy)
        self._selection = touchee if touchee else self._ajouter(wx, wy)
        self._sync_champ()
        self._dessiner()

    def _sur_glisse(self, event):
        if self._selection:
            self._deplacer(self._selection, *self._boite(event))

    def _sur_double_clic(self, event):
        if self._lecture_seule:
            return
        nom = self._broche_a(*self._boite(event))
        if not nom:
            return
        from tkinter import messagebox, simpledialog
        nouveau = simpledialog.askstring(
            "Renommer la broche", f"Nouveau nom pour « {nom} » :",
            initialvalue=nom, parent=self)
        if nouveau is not None and not self._renommer(nom, nouveau):
            messagebox.showerror("Erreur", "Nom vide ou déjà utilisé.")

    def _sur_suppr(self, _event=None):
        if self._selection:
            self._supprimer(self._selection)

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
