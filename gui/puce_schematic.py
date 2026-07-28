"""
@file puce_schematic.py
@brief Boîte à puce générique (elm.Ic) pour les composants réels identifiés
(NE555, 74HC…, LM393, PC817…). Module dédié (précédent : logic_schematic.py).

Répartition des broches : alimentations en haut (VCC/VDD/V+) et en bas
(GND/VSS/V-), sorties (fonction contenant OUT/Y/Q) à droite, le reste à
gauche. Chaque broche câblée reçoit un stub + point + nom de net.

Piège schemdraw 0.22 : orientation EXPLICITE (.right()) sur tout élément —
sinon héritage de la direction courante du stylo (bug D4 historique).
"""
import re

import schemdraw.elements as elm
from schemdraw.elements import intcircuits as ic


_HAUT = {"VCC", "VDD", "V+"}
_BAS = {"GND", "VSS", "V-"}


def _cote(fonction):
    f = fonction.upper()
    if f in _HAUT:
        return "top"
    if f in _BAS:
        return "bottom"
    if "OUT" in f or re.fullmatch(r"\d?N?[YQ]\d?", f) or f.startswith("Y"):
        return "right"
    return "left"


def _nets_partages(ci):
    """@brief Ensemble des nets portés par au moins 2 broches, toutes puces
    et composants confondus (utilisé par `_broche_cablee`)."""
    compte = {}
    for info in (ci or {}).values():
        for net in (info.get("pins") or {}).values():
            if net:
                compte[net] = compte.get(net, 0) + 1
    return {n for n, c in compte.items() if c > 1}


def _broche_cablee(net, partages):
    """@brief Vrai si une broche physique est réellement CÂBLÉE, au sens où
    elle mérite un stub dessiné — pas un net singleton fantôme.

    Convention de lecture (`circuit_analyzer.xml.lire_xml`) : toute broche
    physique NON câblée d'un composant ressort avec son PROPRE net singleton
    nommé `NET<n>` (jamais `NC`, jamais partagé avec une autre broche) —
    fidèle au fichier réel (ex. une 74HC00 posée seule a 12 broches logiques
    "en l'air" sur ses 14). Dessiner ces singletons produirait des broches
    fantômes (9 sur une 74HC00 isolée).

    Une broche est câblée si son net est non vide, différent de `NC`, ET
    (partagé par au moins une autre broche du schéma OU son nom ne suit PAS
    la convention générée `NET<chiffres>`) — un rail nommé GND/VCC/VDD... par
    exemple reste câblé même s'il n'est porté que par cette seule broche dans
    le fichier (cas légitime, contrairement au singleton auto-généré).

    @param net Nom du net porté par la broche (peut être vide/None).
    @param partages Ensemble des nets partagés (cf. `_nets_partages`).
    @return bool
    """
    if not net or net == "NC":
        return False
    if net in partages:
        return True
    return not re.fullmatch(r"NET\d+", net)


def _taille_ic(cablees):
    """@brief (largeur, hauteur) en unités schemdraw pour `elm.Ic(size=...)`.

    Reproduit le calcul natif de `Ic._autosize` (0.22) — pad=0.5, spacing=0.6,
    lofst=0.15, lsize=14, cf. `Ic._element_defaults` — et y ajoute une marge
    de sécurité horizontale : l'auto-dimensionnement retombe souvent sur son
    plancher `2 + edgepadW` dès qu'une seule broche occupe chaque côté (ex.
    LM393 réduit à IN1-/OUT1 câblés) et la marge réelle observée est trop
    juste (« IN1-OUT1 » collé au centre de la boîte).
    """
    from schemdraw.elements.intcircuits import text_size
    par_cote = {"left": [], "right": [], "top": [], "bottom": []}
    for _num, fonction in cablees:
        par_cote[_cote(fonction)].append(fonction)
    edgepad, spacing, lofst, lsize = 0.5, 0.6, 0.15, 14
    lengths, labelw = {}, {}
    for cote, noms in par_cote.items():
        n = len(noms)
        lengths[cote] = edgepad * 2 + spacing * (n - 1) if n else 0.0
        labelw[cote] = max((text_size(nom, size=lsize)[0] / 72 * 2 for nom in noms),
                           default=0.0)
    hauteur = max(lengths["left"], lengths["right"], 2 + edgepad)
    besoin_texte = labelw["left"] + labelw["right"] + 4 * lofst
    largeur = max(lengths["top"], lengths["bottom"], 2 + edgepad, besoin_texte)
    return largeur + 0.6, hauteur    # +0.6 : marge de sécurité horizontale


def dessiner_puce(d, ref, entree, ci, origin=(4.0, 0), titre=True):
    """@brief Dessine la boîte puce de `ref` ; contrat de retour identique aux
    drawers de montages ({"in","out","title","nets","absorbed_refs"})."""
    from gui.circuit_viewer import _enregistrer_position
    pins_nets = (ci.get(ref, {}) or {}).get("pins", {}) or {}
    broches = entree.get("broches") or {n: n for n in pins_nets}
    partages = _nets_partages(ci)
    # ne dessiner que les broches CÂBLÉES (une 74HC00 seule ne montre pas ses
    # 9 broches en l'air), ordre = numéro de boîtier.
    cablees = [(num, broches.get(num, num)) for num in sorted(
        pins_nets, key=lambda n: (len(n), n))
        if _broche_cablee(pins_nets.get(num), partages)]
    # pin= n'affiche le numéro de boîtier QUE s'il est numérique : sur une
    # puce ALIASÉE (7805…), les clés de broches sont déjà les noms
    # fonctionnels -> "GND" s'affichait en triple (numéro + fonction + net),
    # audit A4.
    ic_pins = [ic.IcPin(name=fonction, pin=num if num.isdigit() else None,
                        side=_cote(fonction), anchorname=f"p{num}")
               for num, fonction in cablees]
    # pas de kwargs de padding (non garantis en 0.22) -- taille explicite
    # (cf. _taille_ic) pour éviter les noms de fonction gauche/droite
    # collés au centre d'une boîte étroite (LM393 : "IN1-OUT1").
    puce = ic.Ic(pins=ic_pins, size=_taille_ic(cablees))
    # Pas de label interne au centre (loc="center") : redondant avec le
    # titre externe posé plus bas (entree["categorie"]/entree["nom"]) et il
    # chevauchait le nom de fonction du premier pin gauche sur les puces à
    # plusieurs broches (ex. NE555 : "THR" collé à "NE555" centré).
    d.add(puce.right().at(origin))
    centre = puce.center
    _enregistrer_position(d, ref, tuple(centre))

    nets = {}
    cotes = {}          # net -> côté (revu par dessiner_z_locales)
    # Haut/bas légèrement décalés en x (et non alignés pile sur le centre) :
    # une puce avec UNE alimentation en haut et UNE masse en bas (cas
    # fréquent : NE555, 74HC…) les alignerait sinon exactement à la même
    # abscisse, ce qui déclenche à tort l'heuristique `bloque_bas` de
    # `circuit_viewer._dessiner_z_locale` (pensée pour un élément de montage
    # directement sous l'ancre).
    delta = {"left": (-0.7, 0), "right": (0.7, 0),
             "top": (-0.2, 0.7), "bottom": (0.2, -0.7)}
    locs = {"left": "left", "right": "right", "top": "top", "bottom": "bottom"}
    # Ordre de dessin : broches d'ALIMENTATION (fonction VCC/GND/VDD…)
    # d'abord, pour que l'ancre retenue dans `nets`/`cotes` (utilisée pour
    # brancher les Z locales, cf. `dessiner_z_locales`) soit le rail
    # canonique — pas une broche signal accidentellement tirée au même net
    # (ex. RESET relié à VCC sur un 555 astable, qui viendrait sinon
    # "voler" l'ancre VCC et attirer une Z de couplage tout contre
    # l'étiquette RESET).
    ordre = sorted(cablees, key=lambda item: 0 if _cote(item[1]) in
                   ("top", "bottom") else 1)
    for num, fonction in ordre:
        net = pins_nets[num]
        a = getattr(puce, f"p{num}")
        cote = _cote(fonction)
        dx, dy = delta[cote]
        bout = (a[0] + dx, a[1] + dy)
        d.add(elm.Line().at(a).to(bout))
        # Chaque broche câblée garde SON étiquette (même réseau que la
        # broche d'alimentation : dire "VCC" sur RESET est correct et
        # évite un point sans nom en bout de fil) — SAUF si le net porte
        # exactement le nom de la fonction (GND sur la broche GND) : le
        # répéter au dot empilait "GND" trois fois (audit A4).
        dot = elm.Dot().at(bout)
        if net != fonction:
            dot = dot.label(net, loc=locs[cote], fontsize=9)
        d.add(dot)
        nets.setdefault(net, bout)
        cotes.setdefault(net, cote)
    haut = max((p[1] for p in nets.values()), default=origin[1]) + 0.8
    title_pt = (centre[0], haut + 0.4)
    if titre:
        from gui.circuit_viewer import _TITRE_COLOR, _sans_redite
        d.add(elm.Label().at(title_pt).label(
            _sans_redite(entree["categorie"], entree["nom"], "{c} ({n})"),
            color=_TITRE_COLOR, fontsize=11))
    sorties = [pins_nets[num] for num, f in cablees if _cote(f) == "right"]
    entrees_g = [pins_nets[num] for num, f in cablees if _cote(f) == "left"]
    return {"in": nets.get(entrees_g[0]) if entrees_g else tuple(centre),
            "out": nets.get(sorties[0]) if sorties else tuple(centre),
            "title": title_pt, "nets": nets, "absorbed_refs": set(),
            "_cotes": cotes}


_DIR = {"left": (-1, 0), "right": (1, 0), "top": (0, 1), "bottom": (0, -1)}
_HALIGN = {"left": "right", "right": "left", "top": "center", "bottom": "center"}
_VALIGN = {"left": "center", "right": "center", "top": "bottom", "bottom": "top"}


def dessiner_z_locales(d, res, z_matches, ci):
    """@brief Dessine les Impédances Z locales (couplages/charges) connectées
    aux nets déjà présents sur une puce (`res` = retour de `dessiner_puce`),
    en repartant de chaque broche dans la DIRECTION DE SON PROPRE STUB
    (gauche/droite/haut/bas).

    Ne réutilise PAS `circuit_viewer._dessiner_impedances_locales` : cette
    dernière suppose une ancre posée sur une ligne de montage avec de
    l'espace libre EN BAS (le cas des drawers de transistors/AOP en chaîne).
    Une puce a de l'espace libre dans la direction propre à CHAQUE côté de sa
    boîte — réutiliser l'heuristique générique ferait plonger une Z partant
    d'une broche du HAUT (ex. VCC) tout droit dans la boîte dès que l'autre
    nœud du couplage n'est pas littéralement nommé "VCC" (cas réel et
    fréquent : R du réseau de temporisation d'un 555 entre VCC et DIS).
    """
    from gui.circuit_viewer import _z_box, _bloc_couplage, _est_couplage, _BUS
    nets = res.get("nets", {})
    cotes = res.get("_cotes", {})
    offsets = {}
    for z in z_matches:
        if not _est_couplage(z):
            continue
        znets = [n for n in z.get("nodes", []) if n]
        communs = [n for n in znets if n in nets]
        if not communs:
            continue
        net = communs[0]
        other = next((n for n in znets if n != net), "")
        cote = cotes.get(net, "left")
        ux, uy = _DIR[cote]
        idx = offsets.get(net, 0)
        offsets[net] = idx + 1
        perp = (-uy, ux)          # étalement perpendiculaire si plusieurs Z partagent le net
        ax, ay = nets[net]
        # Pas d'étalement par CÔTÉ : en gauche/droite les étiquettes de
        # valeur sont au-dessus des boîtes (label_loc="top") -> 1.7 suffit ;
        # en haut/bas elles s'étendent HORIZONTALEMENT (label_loc="right",
        # « C1 = 10 uF » ~2.2 unités) -> 2.8 sinon deux Z voisines d'un même
        # rail se chevauchent (audit A5, 3 Z sous le GND du 555).
        pas = 1.7 if cote in ("left", "right") else 2.8
        base = (ax + perp[0] * idx * pas, ay + perp[1] * idx * pas)
        if idx:
            # Riser d'étalement DÉCALÉ de la colonne des dots (audit A1 :
            # sur le LM317 il passait PAR le dot de la broche IN -> lecture
            # court-circuit ADJ-IN, un dot = jonction). Coude de 0.35 DANS le
            # stub (colinéaire, invisible), riser sur la colonne décalée (il
            # croise les stubs voisins PERPENDICULAIREMENT, couvert par la
            # légende « croisement sans point »), retour sur base.
            rentre = (ax - ux * 0.35, ay - uy * 0.35)
            bas_riser = (rentre[0] + perp[0] * idx * pas,
                         rentre[1] + perp[1] * idx * pas)
            d.add(elm.Line().at((ax, ay)).to(rentre).color(_BUS))
            d.add(elm.Line().at(rentre).to(bas_riser).color(_BUS))
            d.add(elm.Line().at(bas_riser).to(base).color(_BUS))
        # Départ plus large à gauche/droite qu'en haut/bas : l'étiquette de
        # net de la broche elle-même (loc=cote) s'étend horizontalement sur
        # une largeur de TEXTE (souvent > 0.5 unité, ex. "NET1") alors
        # qu'en haut/bas elle ne prend qu'une hauteur de ligne — un même
        # départ à 0.5 collisionnait avec l'étiquette gauche/droite.
        depart = 0.5 if cote in ("top", "bottom") else 1.4
        p1 = (base[0] + ux * depart, base[1] + uy * depart)
        p2 = (base[0] + ux * (depart + 1.2), base[1] + uy * (depart + 1.2))
        label_loc = "top" if cote in ("left", "right") else "right"
        d.add(elm.Line().at(base).to(p1).color(_BUS))
        _z_box(d, p1, p2, "Z", _bloc_couplage(z), ci, label_loc=label_loc, wire_color=_BUS)
        fin = (p2[0] + ux * 0.3, p2[1] + uy * 0.3)
        d.add(elm.Line().at(p2).to(fin).color(_BUS))
        d.add(elm.Dot(open=True).at(fin).color(_BUS))
        if other:
            lp = (fin[0] + ux * 0.1, fin[1] + uy * 0.15)
            d.add(elm.Label().at(lp).label(
                other, halign=_HALIGN[cote], valign=_VALIGN[cote],
                color=_BUS, fontsize=9))
