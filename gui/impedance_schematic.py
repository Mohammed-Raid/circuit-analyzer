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

# Boîtes Z : bleu rempli (idem circuit_viewer) — lisibilité + affordance du clic.
_Z_FILL = "#dbeafe"
_Z_EDGE = "#2563eb"
# Couleur des symboles par type (idem palette _COMP_COLORS de l'app).
_COMP_COLORS = {"R": "#1d4ed8", "C": "#0891b2", "L": "#059669"}

# Symbole schemdraw par type de composant ; défaut = boîte Z générique.
_SYMB = {
    "R": elm.Resistor,
    "C": elm.Capacitor,
    "L": elm.Inductor2,
}


def _dessiner_impl(arbre_a_tracer, a, b, comps, groupes):
    """@brief Cœur de rendu série/parallèle.

    Trace `arbre_a_tracer` (déjà mis en page par agencer). Une feuille dont la clé
    est dans `groupes` est rendue comme une BOÎTE Z numérotée (Zn) + composition,
    et enregistrée comme zone cliquable ; sinon comme le composant réel.

    @param groupes Dict {clé → (refs, composition)} ; vide = tout détaillé.
    @return matplotlib.figure.Figure ; fig._z_hitboxes = zones cliquables des Z.
    """
    from circuit_analyzer import impedance
    symboles, fils, dims = agencer(arbre_a_tracer)
    fig = Figure(figsize=(max(4.0, dims.largeur * 0.6 + 1.5),
                          max(3.0, dims.hauteur * 0.6 + 1.5)))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")

    ordre_groupes = list(groupes)
    hitboxes = []
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d.config(fontsize=10, inches_per_unit=0.5)
        for ref, x1, x2, y in symboles:
            if ref in groupes:
                grefs, gcompo = groupes[ref]
                n = ordre_groupes.index(ref) + 1
                prefixe = "Z" if len(ordre_groupes) == 1 else f"Z{n}"
                label = f"{prefixe}\n{impedance.formater_expr(gcompo)}"
                d += elm.ResistorIEC().at((x1, y)).to((x2, y)).color(_Z_EDGE).fill(
                    _Z_FILL).label(label, loc="bottom", fontsize=9, color=_Z_EDGE)
                hitboxes.append((x1 - 0.1, x2 + 0.1, y - 0.6, y + 0.6,
                                 list(grefs), gcompo))
            else:
                comp = comps.get(ref)
                typ = getattr(comp, "type", "")
                cls = _SYMB.get(typ, elm.ResistorIEC)
                coul = _COMP_COLORS.get(typ, _WIRE)
                vfmt = impedance.formater_valeur(getattr(comp, "value", ""), typ)
                etiquette = f"{ref}\n{vfmt}" if vfmt else ref
                d += cls().at((x1, y)).to((x2, y)).color(coul).label(
                    etiquette, loc="bottom", fontsize=9, color=coul)
        for (xa, ya), (xb, yb) in fils:
            d += elm.Line().at((xa, ya)).to((xb, yb)).color(_WIRE)
        d += elm.Dot().at((0.0, dims.y_borne)).label(a, loc="left", color=_BUS)
        d += elm.Dot().at((dims.largeur, dims.y_borne)).label(
            b, loc="right", color=_BUS)

    fig._z_hitboxes = hitboxes
    ax.margins(0.15)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        pass
    return fig


def dessiner(arbre, a, b, comps):
    """@brief Schéma série/parallèle DÉTAILLÉ (tous les R/L/C). Pas de boîte Z.

    @param arbre Arbre série/parallèle (cf. impedance.arbre_expr).
    @param a, b Noms des bornes d'entrée/sortie (étiquettes du dessin).
    @param comps Dict {ref → Composant} pour le type (symbole) et la valeur.
    @return matplotlib.figure.Figure prête à embarquer.
    """
    return _dessiner_impl(arbre, a, b, comps, {})


def _refs_arbre(node):
    """@brief Toutes les refs (feuilles) d'un sous-arbre."""
    if node[0] == "feuille":
        return [node[1]]
    out = []
    for c in node[1]:
        out.extend(_refs_arbre(c))
    return out


def _compo_arbre(node):
    """@brief Reconstruit l'expression de composition d'un sous-arbre.

    Parenthèse les opérandes série au sein d'un parallèle pour rester reparsable
    (« (R2+C1)//(L1+R3) »).
    """
    if node[0] == "feuille":
        return node[1]
    if node[0] == "serie":
        return "+".join(_compo_arbre(c) for c in node[1])
    parts = []
    for c in node[1]:
        s = _compo_arbre(c)
        parts.append(f"({s})" if "+" in s else s)
    return "//".join(parts)


def dessiner_bloc(arbre, a, b, comps):
    """@brief Schéma compact : tout le réseau réductible = UNE boîte Z cliquable.

    Le réseau entier (composant seul inclus) est représenté par une seule boîte Z
    entre a et b (composition affichée dessous) ; le clic ouvre le détail complet
    R/L/C en série/parallèle (cf. show_dipole_detail). Un réseau d'un seul
    composant est dessiné tel quel (rien à déplier).

    @return matplotlib.figure.Figure ; fig._z_hitboxes = la zone cliquable du bloc.
    """
    refs = _refs_arbre(arbre)
    if len(refs) <= 1:
        return _dessiner_impl(arbre, a, b, comps, {})
    cle = "__Z__"
    return _dessiner_impl(("feuille", cle), a, b, comps,
                          {cle: (refs, _compo_arbre(arbre))})


def _elem_bras(bras, comps, p1, p2):
    """@brief (élément schemdraw, hitbox|None) pour un bras du pont.

    Bras simple (1 réf) : symbole du type + « ref\\nvaleur ». Bras composite : boîte Z
    + composition lisible, et un hitbox (x0,x1,y0,y1,refs,composition).
    """
    from circuit_analyzer import impedance
    refs = bras["refs"]
    if len(refs) == 1:
        ref = refs[0]
        comp = comps.get(ref)
        typ = getattr(comp, "type", "")
        cls = _SYMB.get(typ, elm.ResistorIEC)
        coul = _COMP_COLORS.get(typ, _WIRE)
        vfmt = impedance.formater_valeur(getattr(comp, "value", ""), typ)
        label = f"{ref}\n{vfmt}" if vfmt else ref
        return cls().at(p1).to(p2).color(coul).label(
            label, loc="bottom", fontsize=9, color=coul), None
    label = impedance.formater_expr(bras["composition"])
    el = elm.ResistorIEC().at(p1).to(p2).color(_Z_EDGE).fill(_Z_FILL).label(
        label, loc="bottom", fontsize=9, color=_Z_EDGE)
    # Hitbox centrée sur le SYMBOLE (milieu du bras), pas sur tout le segment :
    # deux bras adjacents partagent un sommet, donc des bbox pleine-longueur se
    # chevaucheraient près des sommets et rendraient le clic ambigu.
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    half = 0.9
    hit = (mx - half, mx + half, my - half, my + half, list(refs), bras["composition"])
    return el, hit


def dessiner_pont(pont, comps):
    """@brief Figure matplotlib d'un pont (type Wheatstone) en losange.

    @param pont Structure de impedance.detecter_pont (bras = {refs, composition}).
    @param comps Dict {ref → Composant}.
    @return matplotlib.figure.Figure ; fig._z_hitboxes liste les boîtes Z composites.
    """
    haut, gauche, droite, bas = (0.0, 4.0), (-2.0, 2.0), (2.0, 2.0), (0.0, 0.0)
    bras = pont["bras"]
    segments = [
        (bras["haut_gauche"], haut, gauche),
        (bras["haut_droite"], haut, droite),
        (bras["bas_gauche"], gauche, bas),
        (bras["bas_droite"], droite, bas),
        (bras["pont"], gauche, droite),
    ]
    fig = Figure(figsize=(5.0, 5.5))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")

    hitboxes = []
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d.config(fontsize=10, inches_per_unit=0.5)
        for b, p1, p2 in segments:
            el, hit = _elem_bras(b, comps, p1, p2)
            d += el
            if hit is not None:
                hitboxes.append(hit)
        d += elm.Dot().at(haut).label(pont["haut"], loc="top", color=_BUS)
        d += elm.Dot().at(bas).label(pont["bas"], loc="bottom", color=_BUS)

    fig._z_hitboxes = hitboxes
    ax.margins(0.2)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        pass
    return fig
