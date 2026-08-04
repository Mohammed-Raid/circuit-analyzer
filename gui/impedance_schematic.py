"""
@file impedance_schematic.py
@brief Dessin série/parallèle d'un réseau d'impédances réduit (forme « manuel »).

L'arbre produit par circuit_analyzer.impedance.arbre_expr est mis en page en
primitives (symboles 2 bornes + fils), puis rendu via schemdraw. Série = en
ligne, parallèle = branches empilées entre deux rails. Module isolé : la vue
îlot (circuit_viewer.py) n'est pas concernée.
"""
import collections
import logging
import math

import schemdraw
import schemdraw.elements as elm
from matplotlib.figure import Figure

from gui.schema_labels import ajuster_labels
from gui.theme import SCHEMA_COLORS

_log = logging.getLogger(__name__)

Dims = collections.namedtuple("Dims", "largeur hauteur y_borne")

# Unités schemdraw (1 unité ≈ une longueur de symbole).
W_SYMB = 2.0    # longueur d'un symbole 2 bornes
H_SYMB = 1.0    # empreinte verticale d'une feuille (pour l'empilement)
LEAD = 0.6      # fil entre deux composants en série
GAP_V = 1.4     # écart vertical entre branches parallèles
GAP_V_DENSE = 0.35  # écart compact pour 4+ branches dans une fenêtre de détail
RAIL = 0.6      # extension horizontale d'un rail de chaque côté


def _gap_parallele(nb_branches):
    """@brief Ecart vertical adapte au nombre de branches paralleles."""
    return GAP_V_DENSE if nb_branches >= 4 else GAP_V


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
    gap = _gap_parallele(len(enfants))
    hauteur = sum(d.hauteur for d in enfants) + gap * (len(enfants) - 1)
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
    gap = _gap_parallele(len(arbre[1]))
    for c in arbre[1]:
        dc = _mesurer(c)
        c_y0 = haut - dc.hauteur
        c_x = x + RAIL + (inner - dc.largeur) / 2
        c_ligne = c_y0 + dc.y_borne
        _emettre(c, c_x, c_y0, symboles, fils)
        fils.append(((rail_g, c_ligne), (c_x, c_ligne)))
        fils.append(((c_x + dc.largeur, c_ligne), (rail_d, c_ligne)))
        lignes.append(c_ligne)
        haut = c_y0 - gap
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


# Echelle perpendiculaire minimale pour agencement_entre (cf. sa docstring).
_PERP_MIN_SCALE = 0.85


def agencement_entre(p1, p2, arbre):
    """@brief Place le réseau R/L/C de `arbre` entre p1 et p2 (coordonnées globales).

    Réutilise agencer(arbre) (mise en page locale ; borne gauche
    (0, dims.y_borne), borne droite (dims.largeur, dims.y_borne)) puis
    applique translation p1 + rotation (angle p1->p2) + échelle uniforme
    (dist(p1,p2) / dims.largeur), pour amener les deux bornes locales sur p1/p2.
    Le perpendiculaire local (écart à l'axe des bornes) utilise la même échelle
    avec un minimum lisible pour ne pas écraser les branches parallèles courtes.

    Utilisée par ce module (`_bras_detaille`) et par `circuit_viewer.py`
    (vue îlot, dépliage d'un bloc Z) : fonction publique, pas un détail privé
    de l'un ou l'autre.

    @param p1, p2 Bornes globales (x, y) entre lesquelles agencer le réseau.
    @param arbre Arbre série/parallèle (cf. circuit_analyzer.impedance.arbre_expr).
    @return (symboles, fils) en coordonnées globales :
        symboles = [(ref, (xa,ya), (xb,yb))] ; fils = [((xa,ya),(xb,yb))].
    """
    symboles_loc, fils_loc, dims = agencer(arbre)
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    dist = math.hypot(dx, dy)
    echelle = dist / dims.largeur if dims.largeur else 0.0
    # Les couplages courts compriment fortement les branches paralleles si l'on
    # applique l'echelle uniforme aux deux axes. Garder un minimum perpendiculaire
    # preserve la lisibilite des labels sans changer les bornes p1/p2.
    echelle_perp = max(echelle, _PERP_MIN_SCALE)
    theta = math.atan2(dy, dx)
    cos_t, sin_t = math.cos(theta), math.sin(theta)

    def _vers_global(lx, ly):
        along = lx * echelle
        perp = (ly - dims.y_borne) * echelle_perp
        return (p1[0] + along * cos_t - perp * sin_t,
                p1[1] + along * sin_t + perp * cos_t)

    symboles = [(ref, _vers_global(x1, y), _vers_global(x2, y))
                for ref, x1, x2, y in symboles_loc]
    fils = [(_vers_global(xa, ya), _vers_global(xb, yb))
            for (xa, ya), (xb, yb) in fils_loc]
    return symboles, fils


# --- Couleurs de rendu — alignées tokens (canvas clair préservé, cf. brief) -
# Directive boss : le canvas reste CLAIR (fond #fafafa, standard de schéma).
# Toutes les couleurs sont lues depuis theme.SCHEMA_COLORS (source unique,
# Task 3) ; le reste (fonds clairs, encre) sont des couleurs de canvas clair
# et non des tokens de surface sombre — mais leur VALEUR vit dans theme.py.
SCH_BG = SCHEMA_COLORS["SCH_BG"]   # fond clair standard de schéma (idem circuit_viewer)
_WIRE = SCHEMA_COLORS["WIRE"]      # fils/encre — slate foncé, lisible sur SCH_BG
_BUS = SCHEMA_COLORS["BUS"]        # bus/nets — gris ardoise moyen, lisible sur clair

# Boîtes Z : bleu rempli (idem circuit_viewer) — lisibilité + affordance du clic.
_Z_FILL = SCHEMA_COLORS["Z_FILL"]  # remplissage clair (canvas clair, non touché)
_Z_EDGE = SCHEMA_COLORS["Z_EDGE"]  # alignée tokens = theme.BLUE_HOVER (#2563eb)
# Couleur des symboles par type (idem palette _COMP_COLORS de l'app).
_COMP_COLORS = {k: SCHEMA_COLORS["COMP"][k] for k in ("R", "C", "L")}

# Symbole schemdraw par type de composant ; défaut = boîte Z générique.
_SYMB = {
    "R": elm.Resistor,
    "C": elm.Capacitor,
    "L": elm.Inductor2,
}


def style_symbole(typ, value, ref):
    """@brief (classe schemdraw, couleur, ref, valeur formatée) pour un
    composant réel.

    Facteur commun aux 3 endroits qui dessinent un R/L/C réel (symbole+couleur
    par type) : _dessiner_impl et _bras_detaille ci-dessous, et
    circuit_viewer._z_reseau. Règle ref/valeur (décision d'architecte, cf.
    design 2026-07-06) : ref et valeur sont deux `Text` DISTINCTS posés de
    part et d'autre du symbole (ref toujours affichée ; `valeur` vide "" si
    non formatable, l'appelant n'affiche alors que la ref). Fontsize/loc
    restent au choix de chaque appelant (échelles différentes).
    """
    from circuit_analyzer import impedance
    cls = _SYMB.get(typ, elm.ResistorIEC)
    coul = _COMP_COLORS.get(typ, _WIRE)
    vfmt = impedance.formater_valeur(value, typ)
    return cls, coul, ref, vfmt


def _dessiner_impl(arbre_a_tracer, a, b, comps, groupes, titre=None):
    """@brief Cœur de rendu série/parallèle.

    Trace `arbre_a_tracer` (déjà mis en page par agencer). Une feuille dont la clé
    est dans `groupes` est rendue comme une BOÎTE Z numérotée (Zn) + composition,
    et enregistrée comme zone cliquable ; sinon comme le composant réel.

    @param groupes Dict {clé → (refs, composition)} ; vide = tout détaillé.
    @param titre Titre embarqué sur la figure (ex. « Z = (R1//C1)+R2 ») ; None = aucun.
    @return matplotlib.figure.Figure ; fig._z_hitboxes = zones cliquables des Z.
    """
    from circuit_analyzer import impedance
    symboles, fils, dims = agencer(arbre_a_tracer)
    fig = Figure(figsize=(max(3.6, dims.largeur * 0.8 + 1.4),
                          max(2.4, dims.hauteur * 0.8 + 1.4)))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")
    ax.set_aspect("equal")
    if titre:
        ax.set_title(titre, fontsize=12, color=_Z_EDGE, pad=8)

    ordre_groupes = list(groupes)
    hitboxes = []
    # Registre ref -> position (meme idiome que circuit_viewer._enregistrer_position) :
    # une feuille groupee (boite Zn) affiche "Zn / composition", jamais les refs
    # brutes qui la composent -- on les enregistre ici pour que le clic sur une
    # puce composant ('R1' d'un Z composite, ex.) resolve quand meme sa position.
    # Une feuille NON groupee affiche deja sa ref reelle (`ref_txt`) : deja
    # resoluble par le fallback texte de `_position_composant`, pas besoin ici.
    positions = {}
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d.config(fontsize=13, inches_per_unit=0.5)
        for ref, x1, x2, y in symboles:
            if ref in groupes:
                grefs, gcompo = groupes[ref]
                n = ordre_groupes.index(ref) + 1
                prefixe = "Z" if len(ordre_groupes) == 1 else f"Z{n}"
                label = f"{prefixe}\n{impedance.formater_expr(gcompo)}"
                d += elm.ResistorIEC().at((x1, y)).to((x2, y)).color(_Z_EDGE).fill(
                    _Z_FILL).label(label, loc="bottom", fontsize=11, color=_Z_EDGE)
                hitboxes.append((x1 - 0.1, x2 + 0.1, y - 0.6, y + 0.6,
                                 list(grefs), gcompo))
                for r in grefs:
                    positions[r] = ((x1 + x2) / 2.0, y)
            else:
                comp = comps.get(ref)
                typ = getattr(comp, "type", "")
                cls, coul, ref_txt, valeur = style_symbole(
                    typ, getattr(comp, "value", ""), ref)
                # Règle ref/valeur (feuille dépliée) : ref au-dessus (+Y),
                # valeur en dessous (-Y) — deux Text distincts. schemdraw
                # tourne ses ancres "top"/"bottom" avec l'élément : un
                # symbole vertical voit donc ref/valeur basculer à
                # gauche/droite automatiquement, sans logique dédiée ici.
                el = cls().at((x1, y)).to((x2, y)).color(coul).label(
                    ref_txt, loc="top", fontsize=11, color=coul)
                if valeur:
                    el = el.label(valeur, loc="bottom", fontsize=11, color=coul)
                d += el
        for (xa, ya), (xb, yb) in fils:
            d += elm.Line().at((xa, ya)).to((xb, yb)).color(_WIRE)
        d += elm.Dot().at((0.0, dims.y_borne)).label(a, loc="left", color=_BUS)
        d += elm.Dot().at((dims.largeur, dims.y_borne)).label(
            b, loc="right", color=_BUS)

    fig._z_hitboxes = hitboxes
    fig._comp_positions = positions
    ax.margins(0.1)
    try:
        fig.tight_layout(pad=0.3)
    except Exception:
        _log.debug("tight_layout ignoré", exc_info=True)
    # Après tight_layout/margins (pas avant) : tight_layout()/ax.margins()
    # peuvent réduire la boîte des axes (subplot params), or la taille de
    # police est fixée en POINTS (pas en unités de données) -> une boîte plus
    # petite pour le MÊME xlim/ylim fait mécaniquement déborder un texte qui
    # tenait tout juste avant. Seule une résolution APRÈS que la géométrie
    # finale des axes soit figée garantit "aucun label clippé" pour de vrai.
    ajuster_labels(fig)
    return fig


def dessiner(arbre, a, b, comps, titre=None):
    """@brief Schéma série/parallèle DÉTAILLÉ (tous les R/L/C). Pas de boîte Z.

    @param arbre Arbre série/parallèle (cf. impedance.arbre_expr).
    @param a, b Noms des bornes d'entrée/sortie (étiquettes du dessin).
    @param comps Dict {ref → Composant} pour le type (symbole) et la valeur.
    @param titre Titre embarqué (ex. « Z = (R1//C1)+R2 ») ; None = aucun.
    @return matplotlib.figure.Figure prête à embarquer.
    """
    return _dessiner_impl(arbre, a, b, comps, {}, titre=titre)


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


def dessiner_bloc(arbre, a, b, comps, detaille=False):
    """@brief Schéma compact : tout le réseau réductible = UNE boîte Z cliquable.

    Le réseau entier (composant seul inclus) est représenté par une seule boîte Z
    entre a et b (composition affichée dessous) ; le clic ouvre le détail complet
    R/L/C en série/parallèle (cf. show_dipole_detail). Un réseau d'un seul
    composant est dessiné tel quel (rien à déplier).

    @param detaille Si True, rend tout le réseau réel (R/L/C, symboles/couleurs
        réels) au lieu de la boîte Z unique ; aucune zone cliquable dans ce cas.
    @return matplotlib.figure.Figure ; fig._z_hitboxes = la zone cliquable du bloc
        (vide en mode détaillé).
    """
    refs = _refs_arbre(arbre)
    if detaille or len(refs) <= 1:
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
        # Idiome feuille unifie (meme regle que `_dessiner_impl`) : ref et
        # valeur de part et d'autre du symbole, deux Texts distincts -- pas
        # de « ref\nvaleur » combine propre aux bras de pont.
        cls, coul, ref_txt, valeur = style_symbole(
            typ, getattr(comp, "value", ""), ref)
        el = cls().at(p1).to(p2).color(coul).label(
            ref_txt, loc="top", fontsize=11, color=coul)
        if valeur:
            el = el.label(valeur, loc="bottom", fontsize=11, color=coul)
        return el, None
    label = impedance.formater_expr(bras["composition"])
    el = elm.ResistorIEC().at(p1).to(p2).color(_Z_EDGE).fill(_Z_FILL).label(
        label, loc="bottom", fontsize=11, color=_Z_EDGE)
    # Hitbox centrée sur le SYMBOLE (milieu du bras), pas sur tout le segment :
    # deux bras adjacents partagent un sommet, donc des bbox pleine-longueur se
    # chevaucheraient près des sommets et rendraient le clic ambigu.
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    half = 0.9
    hit = (mx - half, mx + half, my - half, my + half, list(refs), bras["composition"])
    return el, hit


def _bras_detaille(d, p1, p2, bras, comps):
    """@brief Tente de déplier un bras composite entre p1 et p2 (mode détaillé).

    Réutilise `agencement_entre` (défini dans ce module) pour placer les
    symboles réels R/L/C le long du segment p1->p2.

    @param d Dessin schemdraw en cours.
    @param p1, p2 Extrémités globales du bras.
    @param bras Bras {"refs": [...], "composition": str}.
    @param comps Dict {ref → Composant}.
    @return bool True si dessiné (arbre série/parallèle valide), False si le
        bras n'est pas dépliable (l'appelant garde alors la boîte Z).
    """
    from circuit_analyzer import impedance
    arbre = impedance.arbre_expr(bras["composition"])
    if arbre is None or arbre[0] not in ("serie", "parallele"):
        return False
    symboles, fils = agencement_entre(p1, p2, arbre)
    for ref, pa, pb in symboles:
        comp = comps.get(ref)
        typ = getattr(comp, "type", "")
        cls, coul, ref_txt, valeur = style_symbole(typ, getattr(comp, "value", ""), ref)
        # Règle ref/valeur : ref+valeur de part et d'autre (loc="top"/
        # "bottom", tournent avec l'élément). loc="bottom" pour la ref est
        # conservé tel quel (évite qu'elle colle au rail du bras, cf. avant) ;
        # la valeur va de l'autre côté ("top").
        el = cls().at(pa).to(pb).color(coul).label(
            ref_txt, loc="bottom", fontsize=9, color=coul)
        if valeur:
            el = el.label(valeur, loc="top", fontsize=9, color=coul)
        d.add(el)
    for pa, pb in fils:
        d.add(elm.Line().at(pa).to(pb).color(_WIRE))
    return True


def dessiner_pont(pont, comps, titre=None, detaille=False):
    """@brief Figure matplotlib d'un pont (type Wheatstone) en losange.

    @param pont Structure de impedance.detecter_pont (bras = {refs, composition}).
    @param comps Dict {ref → Composant}.
    @param titre Titre embarqué sur la figure ; None = aucun.
    @param detaille Si True, chaque bras composite dont la composition est
        série/parallèle est déplié en composants réels (cf. `_bras_detaille`) ;
        un bras non dépliable garde sa boîte Z. Aucune zone cliquable dans ce mode.
    @return matplotlib.figure.Figure ; fig._z_hitboxes liste les boîtes Z
        composites (vide en mode détaillé).
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
    if titre:
        ax.set_title(titre, fontsize=12, color=_Z_EDGE, pad=8)

    hitboxes = []
    # Registre ref -> position (meme idiome que `_dessiner_impl`) : un bras
    # composite non deplie affiche sa composition, pas ses refs brutes.
    positions = {}
    with schemdraw.Drawing(canvas=ax, show=False) as d:
        d.config(fontsize=13, inches_per_unit=0.5)
        for b, p1, p2 in segments:
            centre = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
            for r in b.get("refs", []) or ():
                positions[r] = centre
            if detaille and len(b["refs"]) > 1 and _bras_detaille(d, p1, p2, b, comps):
                continue
            el, hit = _elem_bras(b, comps, p1, p2)
            d += el
            if hit is not None and not detaille:
                hitboxes.append(hit)
        d += elm.Dot().at(haut).label(pont["haut"], loc="top", color=_BUS)
        d += elm.Dot().at(bas).label(pont["bas"], loc="bottom", color=_BUS)

    fig._z_hitboxes = hitboxes
    fig._comp_positions = positions
    ax.margins(0.2)
    try:
        fig.tight_layout(pad=0.4)
    except Exception:
        _log.debug("tight_layout ignoré", exc_info=True)
    # Après tight_layout/margins (cf. commentaire de _dessiner_impl).
    ajuster_labels(fig)
    return fig
