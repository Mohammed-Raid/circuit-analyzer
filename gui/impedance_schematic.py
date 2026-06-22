"""
@file impedance_schematic.py
@brief Dessin série/parallèle d'un réseau d'impédances réduit (forme « manuel »).

L'arbre produit par circuit_analyzer.impedance.arbre_expr est mis en page en
primitives (symboles 2 bornes + fils), puis rendu via schemdraw. Série = en
ligne, parallèle = branches empilées entre deux rails. Module isolé : la vue
îlot (circuit_viewer.py) n'est pas concernée.
"""
import collections

import schemdraw
import schemdraw.elements as elm
from matplotlib.figure import Figure

Dims = collections.namedtuple("Dims", "largeur hauteur y_borne")

# Unités schemdraw (1 unité ≈ une longueur de symbole).
W_SYMB = 2.0    # longueur d'un symbole 2 bornes
H_SYMB = 1.0    # empreinte verticale d'une feuille (pour l'empilement)
LEAD = 0.6      # fil entre deux composants en série
GAP_V = 1.4     # écart vertical entre branches parallèles
RAIL = 0.6      # extension horizontale d'un rail de chaque côté


def _mesurer(arbre):
    """@brief Dimensions (largeur, hauteur, y des bornes) d'un sous-arbre."""
    kind = arbre[0]
    if kind == "feuille":
        return Dims(W_SYMB, H_SYMB, H_SYMB / 2)
    enfants = [_mesurer(c) for c in arbre[1]]
    if kind == "serie":
        largeur = sum(d.largeur for d in enfants) + LEAD * (len(enfants) - 1)
        hauteur = max(d.hauteur for d in enfants)
        return Dims(largeur, hauteur, hauteur / 2)
    # parallele
    inner = max(d.largeur for d in enfants)
    largeur = inner + 2 * RAIL
    hauteur = sum(d.hauteur for d in enfants) + GAP_V * (len(enfants) - 1)
    return Dims(largeur, hauteur, hauteur / 2)


def _emettre(arbre, x, y, symboles, fils):
    """@brief Place l'arbre, coin bas-gauche en (x,y) ; remplit symboles/fils.

    @return Dims du sous-arbre placé.
    """
    d = _mesurer(arbre)
    ligne_y = y + d.y_borne
    kind = arbre[0]
    if kind == "feuille":
        symboles.append((arbre[1], x, x + W_SYMB, ligne_y))
        return d
    if kind == "serie":
        cx = x
        prev_droite = None
        for c in arbre[1]:
            dc = _mesurer(c)
            _emettre(c, cx, ligne_y - dc.y_borne, symboles, fils)
            if prev_droite is not None:
                fils.append(((prev_droite, ligne_y), (cx, ligne_y)))
            prev_droite = cx + dc.largeur
            cx = prev_droite + LEAD
        return d
    # parallele
    rail_g, rail_d = x, x + d.largeur
    inner = d.largeur - 2 * RAIL
    lignes = []
    haut = y + d.hauteur
    for c in arbre[1]:
        dc = _mesurer(c)
        c_y0 = haut - dc.hauteur
        c_x = x + RAIL + (inner - dc.largeur) / 2
        c_ligne = c_y0 + dc.y_borne
        _emettre(c, c_x, c_y0, symboles, fils)
        fils.append(((rail_g, c_ligne), (c_x, c_ligne)))
        fils.append(((c_x + dc.largeur, c_ligne), (rail_d, c_ligne)))
        lignes.append(c_ligne)
        haut = c_y0 - GAP_V
    fils.append(((rail_g, lignes[0]), (rail_g, lignes[-1])))   # rail gauche
    fils.append(((rail_d, lignes[0]), (rail_d, lignes[-1])))   # rail droit
    return d


def agencer(arbre):
    """@brief Met en page l'arbre, coin bas-gauche en (0,0).

    @param arbre Arbre série/parallèle (cf. impedance.arbre_expr).
    @return (symboles, fils, dims) :
        symboles : list[(ref, x1, x2, y)] — symbole 2 bornes de (x1,y) a (x2,y) ;
        fils     : list[((xa,ya),(xb,yb))] — segments de fil ;
        dims     : Dims(largeur, hauteur, y_borne). Bornes externes : gauche
                   (0, y_borne), droite (largeur, y_borne).
    """
    symboles, fils = [], []
    dims = _emettre(arbre, 0.0, 0.0, symboles, fils)
    return symboles, fils, dims


SCH_BG = "#fafafa"   # fond clair standard de schéma (idem circuit_viewer)
_WIRE = "#1e293b"
_BUS = "#475569"

# Symbole schemdraw par type de composant ; défaut = boîte Z générique.
_SYMB = {
    "R": elm.Resistor,
    "C": elm.Capacitor,
    "L": elm.Inductor2,
}


def dessiner(arbre, a, b, comps):
    """@brief Figure matplotlib du schéma série/parallèle de l'arbre.

    @param arbre Arbre série/parallèle (cf. impedance.arbre_expr).
    @param a, b Noms des bornes d'entrée/sortie (étiquettes A/B du dessin).
    @param comps Dict {ref → Composant} pour le type (symbole) et la valeur.
    @return matplotlib.figure.Figure prête à embarquer.
    """
    symboles, fils, dims = agencer(arbre)
    fig = Figure(figsize=(max(4.0, dims.largeur * 0.6 + 1.5),
                          max(3.0, dims.hauteur * 0.6 + 1.5)))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")

    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d.config(fontsize=10, inches_per_unit=0.5)
        for ref, x1, x2, y in symboles:
            comp = comps.get(ref)
            cls = _SYMB.get(getattr(comp, "type", ""), elm.ResistorIEC)
            valeur = getattr(comp, "value", "")
            etiquette = f"{ref}\n{valeur}" if valeur else ref
            d += cls().at((x1, y)).to((x2, y)).label(etiquette, loc="bottom",
                                                     fontsize=9)
        for (xa, ya), (xb, yb) in fils:
            d += elm.Line().at((xa, ya)).to((xb, yb)).color(_WIRE)
        d += elm.Dot().at((0.0, dims.y_borne)).label(a, loc="left", color=_BUS)
        d += elm.Dot().at((dims.largeur, dims.y_borne)).label(
            b, loc="right", color=_BUS)

    ax.margins(0.15)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        pass
    return fig


def _elem_arete(ref, comps, p1, p2):
    """@brief Élément schemdraw d'une arête (symbole selon type) entre deux points."""
    comp = comps.get(ref)
    cls = _SYMB.get(getattr(comp, "type", ""), elm.ResistorIEC)
    valeur = getattr(comp, "value", "")
    etiquette = f"{ref}\n{valeur}" if valeur else ref
    return cls().at(p1).to(p2).label(etiquette, loc="bottom", fontsize=9)


def dessiner_pont(pont, comps):
    """@brief Figure matplotlib d'un pont (type Wheatstone) en losange.

    @param pont Structure renvoyée par impedance.detecter_pont.
    @param comps Dict {ref → Composant} (type pour le symbole, value pour l'étiquette).
    @return matplotlib.figure.Figure (losange).
    """
    haut, gauche, droite, bas = (0.0, 4.0), (-2.0, 2.0), (2.0, 2.0), (0.0, 0.0)
    bras = pont["bras"]
    fig = Figure(figsize=(5.0, 5.5))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")

    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d.config(fontsize=10, inches_per_unit=0.5)
        d += _elem_arete(bras["haut_gauche"], comps, haut, gauche)
        d += _elem_arete(bras["haut_droite"], comps, haut, droite)
        d += _elem_arete(bras["bas_gauche"], comps, gauche, bas)
        d += _elem_arete(bras["bas_droite"], comps, droite, bas)
        d += _elem_arete(bras["pont"], comps, gauche, droite)
        d += elm.Dot().at(haut).label(pont["haut"], loc="top", color=_BUS)
        d += elm.Dot().at(bas).label(pont["bas"], loc="bottom", color=_BUS)

    ax.margins(0.2)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        pass
    return fig
