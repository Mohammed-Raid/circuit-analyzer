"""@file schema_grid.py
@brief Grille absolue deterministe pour l'ASSEMBLAGE des ilots (spec
2026-07-13 §3). Module PUR : aucune dependance schemdraw/matplotlib/tkinter ;
entrees = mesures fournies par l'appelant, sorties = positions/rectangles.
"""
import math
from dataclasses import dataclass, field

# Constantes de grille — déplacées vers theme.SCHEMA_DIMS en Task 3
# (schema_grid les REimportera depuis theme à ce moment-là).
PAS = 0.5
MARGE = 1.0
CANAL_H = 2.0
CANAL_V = 2.0
X0 = 4.5


def snap(v: float) -> float:
    """@brief Arrondit au multiple de PAS le plus proche."""
    return round(v / PAS) * PAS


def snap_ceil(v: float) -> float:
    """@brief Arrondit au multiple de PAS superieur (jamais plus petit)."""
    return math.ceil(v / PAS - 1e-9) * PAS


@dataclass(frozen=True)
class Rect:
    """@brief Rectangle axis-aligned (x0<=x1, y0<=y1) en unites schemdraw."""
    x0: float
    y0: float
    x1: float
    y1: float

    def contient_strict(self, x: float, y: float) -> bool:
        """@brief Interieur STRICT (la frontiere reste praticable, spec §4.1)."""
        return self.x0 < x < self.x1 and self.y0 < y < self.y1

    def dilate(self, m: float) -> "Rect":
        return Rect(self.x0 - m, self.y0 - m, self.x1 + m, self.y1 + m)


@dataclass(frozen=True)
class EtageMesure:
    """@brief Mesures d'un etage (bbox du drawer, dry-run cote appelant).

    @param cle Identifiant stable (ref du montage, ex. "U1").
    @param ancrage_x Decalage origine-drawer -> bord gauche de sa bbox.
    @param ancrage_y Decalage vertical (oy_for du montage).
    """
    cle: str
    colonne: int
    bande: int
    largeur: float
    hauteur: float
    ancrage_x: float
    ancrage_y: float


@dataclass
class PlanGrille:
    """@brief Sortie de poser() : origines snappees + obstacles (slots)."""
    origines: dict = field(default_factory=dict)
    obstacles: list = field(default_factory=list)
    slots: dict = field(default_factory=dict)


def poser(etages) -> PlanGrille:
    """@brief Applique les formules de la spec §3.2.

    L(c)  = snap_ceil(max largeur de la colonne + 2*MARGE)
    x(0)  = X0 ; x(c) = x(c-1) + L(c-1) + CANAL_H
    H(b)  = snap_ceil(max hauteur de la bande)
    y(0)  = 0  ; y(b) = y(b-1) - H(b-1) - CANAL_V
    origine(e) = (snap(x(c) + MARGE + ancrage_x), snap(y(b) + ancrage_y))
    Obstacle(e) = slot complet [x(c), x(c)+L(c)] x [y(b)-H(b), y(b)].

    Deterministe : tri stable des etages par (colonne, bande, cle) ; aucune
    dependance a l'ordre d'entree.
    """
    etages = sorted(etages, key=lambda e: (e.colonne, e.bande, e.cle))
    if not etages:
        return PlanGrille()

    colonnes = sorted({e.colonne for e in etages})
    bandes = sorted({e.bande for e in etages})
    L = {c: snap_ceil(max(e.largeur for e in etages if e.colonne == c)
                      + 2 * MARGE) for c in colonnes}
    H = {b: snap_ceil(max(e.hauteur for e in etages if e.bande == b))
         for b in bandes}

    x = {}
    cour = X0
    for c in colonnes:
        x[c] = cour
        cour += L[c] + CANAL_H
    y = {}
    cour = 0.0
    for b in bandes:
        y[b] = cour
        cour -= H[b] + CANAL_V

    plan = PlanGrille()
    for e in etages:
        plan.origines[e.cle] = (snap(x[e.colonne] + MARGE + e.ancrage_x),
                                snap(y[e.bande] + e.ancrage_y))
        slot = Rect(x[e.colonne], snap(y[e.bande] - H[e.bande]),
                    snap(x[e.colonne] + L[e.colonne]), y[e.bande])
        plan.slots[e.cle] = slot
        plan.obstacles.append(slot)
    return plan
