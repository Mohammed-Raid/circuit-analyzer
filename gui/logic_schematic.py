"""
@file logic_schematic.py
@brief Drawers des portes logiques CMOS — module DÉDIÉ (décision revue
d'architecture 2026-07-08 : circuit_viewer.py ~4000 lignes n'accueille plus
de famille de dessin ; précédent : impedance_schematic.py).

Deux vues, dispatch sur d._mode_detaille (posé par circuit_viewer._make_fig) :
  - simplifiée : symbole schemdraw.logic (Not/Nand/Nor), TOUTES les refs M
    enregistrées sur le centre du symbole (contrat puces) ;
  - détaillée : transistors réels agencés d'après match['arbres'] (Task 8 —
    pour cette task, délègue encore au symbole : jamais d'écran vide).

Notes d'ancres (schemdraw 0.22, vérifiées empiriquement -- NE PAS faire
confiance aux ancres `start`/`end` du brief d'origine) :
  - `Not()` expose {in1, out} (aussi start/end hérités d'Element2Term, mais
    ils incluent un lead interne qui décale le point du corps de la porte --
    inutilisables ici).
  - `Nand(inputs=n)` / `Nor(inputs=n)` exposent {in1..inN, out} (aussi `end`,
    identique à `out` pour ces classes, mais on utilise `out` par cohérence
    avec Not()).
  - Après `.at(origin)`, ces ancres sont des coordonnées ABSOLUES.
"""
import schemdraw.elements as elm
from schemdraw import logic as slogic


_SYMBOLES = {"NOT": slogic.Not, "NAND": slogic.Nand, "NOR": slogic.Nor}

_PAS_Y = 1.7      # écart vertical entre transistors empilés (série)
_PAS_X = 2.2      # écart horizontal entre branches parallèles
_STUB_GAUCHE = 2.4  # longueur du rail de grille vers les stubs d'entrée (NOT)
_PAS_LABEL = 1.35   # pas vertical des labels d'entrée en fan-in aérée (>=1.2)


def dessiner_porte(d, result, ci, origin=(3, 0), titre=True,
                   in_label=None, out_label=None):
    """@brief Point d'entrée UNIQUE enregistré dans cv._DRAWERS pour les trois
    circuit_type — même signature et même contrat de retour que les drawers
    transistor ({"in","out","title","nets","absorbed_refs"})."""
    if getattr(d, "_mode_detaille", False):
        return _porte_transistors(d, result, ci, origin, titre,
                                  in_label, out_label)
    return _porte_symbole(d, result, ci, origin, titre, in_label, out_label)


def _porte_symbole(d, result, ci, origin, titre, in_label, out_label):
    from gui.circuit_viewer import _enregistrer_position, _titre_montage
    nom_fn, entrees = result["fonction"]
    sortie = result["nodes"]["sortie"]
    cls = _SYMBOLES[nom_fn]
    n = len(entrees)
    porte = cls().at(origin) if n <= 1 else cls(inputs=n).at(origin)
    d.add(porte)

    # Ancres ABSOLUES (post .at()) -- jamais porte.start/porte.end (cf.
    # docstring module : décalées par le lead interne d'Element2Term pour
    # Not(), et simplement redondantes avec `out` pour Nand/Nor).
    in_pts = [getattr(porte, f"in{i}") for i in range(1, n + 1)]
    out_pt_gate = porte.out
    avg_in = (sum(p[0] for p in in_pts) / n, sum(p[1] for p in in_pts) / n)
    centre = ((avg_in[0] + out_pt_gate[0]) / 2.0,
              (avg_in[1] + out_pt_gate[1]) / 2.0)

    for ref in result["components"]:
        _enregistrer_position(d, ref, centre)   # contrat puces : le clic focalise la porte

    nets = {}
    for i, net in enumerate(entrees, start=1):
        broche = in_pts[i - 1]
        stub = (broche[0] - 0.8, broche[1])
        d.add(elm.Line().at(broche).to(stub))
        d.add(elm.Dot().at(stub).label(in_label or net, loc="left"))
        nets[net] = stub
    out_pt = (out_pt_gate[0] + 0.8, out_pt_gate[1])
    d.add(elm.Line().at(out_pt_gate).to(out_pt))
    d.add(elm.Dot().at(out_pt).label(out_label or sortie, loc="right"))
    nets[sortie] = out_pt

    ymax = max(p[1] for p in in_pts + [out_pt_gate]) + 0.5
    title_pt = (centre[0], ymax + 0.4)
    if titre:
        _titre_montage(d, result, title_pt)
    return {"in": nets[entrees[0]], "out": out_pt, "title": title_pt,
            "nets": nets, "absorbed_refs": set()}


def _porte_transistors(d, result, ci, origin, titre, in_label, out_label):
    """@brief Vue détaillée : transistors réels agencés d'après les arbres
    (formes pures GARANTIES par la détection — le drawer ne re-dérive rien).

    Convention géométrique (schemdraw 0.22, vérifiée empiriquement) :
    `PFet()/NFet().at((x, y))` occupent y in [y-1.5, y] (le point posé est
    TOUJOURS le haut du symbole). PFet.source == point posé (donc proche de
    VDD), PFet.drain == point posé - 1.5. NFet.drain == point posé (donc
    proche de OUT/GND selon le sens), NFet.source == point posé - 1.5.

    Chaque étage (rangée parallèle ou étage de colonne série) le plus proche
    du nœud `oy` est placé à un `jeu` (petit espace de routage, dérivé de
    _PAS_Y) de `oy`, jamais collé dessus -- sinon le busbar OUT/GND et les
    fils de grille n'ont plus de place pour se croiser proprement.
    """
    from gui.circuit_viewer import _enregistrer_position, _titre_montage
    from circuit_analyzer.logique import forme_pure
    entrees = result["nodes"]["entrees"]
    sortie = result["nodes"]["sortie"]
    comps = {r: (ci.get(r, {}) or {}) for r in result["components"]}
    grille_de = {r: (comps[r].get("pins") or {}).get("G") for r in comps}

    genre_haut, refs_haut = forme_pure(result["arbres"]["pull_up"])
    genre_bas, refs_bas = forme_pure(result["arbres"]["pull_down"])
    ox, oy = origin
    jeu = max(_PAS_Y - 1.5, 0.15)  # espace de routage entre un étage et oy

    def _rangee(refs, y0, fet_cls):
        """Aligne (parallèle) des transistors sur y0 ; renvoie [(ref, elem)]."""
        poses = []
        for k, ref in enumerate(refs):
            x = ox + k * _PAS_X
            e = d.add(fet_cls().at((x, y0)).reverse())
            _enregistrer_position(d, ref, (x, y0))
            poses.append((ref, e))
        return poses

    def _colonne(refs, y0, fet_cls):
        """Empile (série) des transistors sur x=ox à partir de y0, en
        descendant de _PAS_Y à chaque étage ; renvoie [(ref, elem)]."""
        poses = []
        y = y0
        for ref in refs:
            e = d.add(fet_cls().at((ox, y)).reverse())
            _enregistrer_position(d, ref, (ox, y))
            poses.append((ref, e))
            y -= _PAS_Y
        # fils drain<->source entre étages successifs (bas de e1 -> haut de e2)
        for (_r1, e1), (_r2, e2) in zip(poses, poses[1:]):
            bas1 = e1.drain if fet_cls is elm.PFet else e1.source
            haut2 = e2.source if fet_cls is elm.PFet else e2.drain
            d.add(elm.Line().at(bas1).to(haut2))
        return poses

    # PMOS en haut (vers VDD) : le point le plus proche de oy est le DRAIN
    # (bas du symbole PFet), donc on place à oy + jeu + 1.5.
    if genre_haut in ("parallele", "feuille"):
        haut = _rangee(refs_haut, oy + jeu + 1.5, elm.PFet)
    else:                                   # série (NOR) : pile verticale
        y0 = oy + jeu + 1.5 + (len(refs_haut) - 1) * _PAS_Y
        haut = _colonne(refs_haut, y0, elm.PFet)
    y_vdd = max(e.source[1] for _r, e in haut) + 1.2
    if genre_haut in ("parallele", "feuille"):
        for _r, e in haut:                       # chaque branche : source→VDD, drain→OUT
            d.add(elm.Line().at(e.source).to((e.source[0], y_vdd)))
            d.add(elm.Line().at(e.drain).to((e.drain[0], oy)))
    else:                                        # pile série : SEULS les 2 bouts touchent
        e_som, e_bas = haut[0][1], haut[-1][1]   # étages internes reliés par _colonne
        d.add(elm.Line().at(e_som.source).to((e_som.source[0], y_vdd)))
        d.add(elm.Line().at(e_bas.drain).to((e_bas.drain[0], oy)))
    xs = [e.drain[0] for _r, e in haut]
    d.add(elm.Line().at((min(xs), y_vdd)).to((max(xs), y_vdd)))
    d.add(elm.Dot().at(((min(xs) + max(xs)) / 2.0, y_vdd))
          .label(result["nodes"]["vdd"], loc="top"))

    # NMOS en bas (vers GND) : le point le plus proche de oy est le DRAIN
    # (haut du symbole NFet, = point posé), donc on place à oy - jeu.
    if genre_bas in ("parallele", "feuille"):
        bas = _rangee(refs_bas, oy - jeu, elm.NFet)
    else:                                   # série (NAND) : pile verticale
        bas = _colonne(refs_bas, oy - jeu, elm.NFet)
    y_gnd = min(e.source[1] for _r, e in bas) - 1.2
    if genre_bas in ("parallele", "feuille"):
        for _r, e in bas:                        # chaque branche : drain→OUT, source→GND
            d.add(elm.Line().at(e.source).to((e.source[0], y_gnd)))
            d.add(elm.Line().at(e.drain).to((e.drain[0], oy)))
    else:                                        # pile série : SEULS les 2 bouts touchent
        e_som, e_bas = bas[0][1], bas[-1][1]     # étages internes reliés par _colonne
        d.add(elm.Line().at(e_som.drain).to((e_som.drain[0], oy)))
        d.add(elm.Line().at(e_bas.source).to((e_bas.source[0], y_gnd)))
    xs_b = [e.drain[0] for _r, e in bas]
    d.add(elm.Line().at((min(xs_b), y_gnd)).to((max(xs_b), y_gnd)))
    d.add(elm.Ground().at(((min(xs_b) + max(xs_b)) / 2.0, y_gnd)))

    # Barre OUT (relie les colonnes/rangées au niveau oy) + stub à droite.
    x_max = max(xs + xs_b)
    d.add(elm.Line().at((min(xs + xs_b), oy)).to((x_max, oy)))
    out_pt = (x_max + 1.0, oy)
    d.add(elm.Line().at((x_max, oy)).to(out_pt))
    d.add(elm.Dot().at(out_pt).label(out_label or sortie, loc="right"))

    # Rails de grilles. Deux régimes :
    #
    #  - UNE entrée (NOT) : routage HISTORIQUE inchangé (rendu validé « parfait »
    #    par le coordinateur, à garder pixel-identique) -- deux brins dans la
    #    fine bande `jeu` autour de oy, reliés par un court tronçon vertical.
    #
    #  - PLUSIEURS entrées (NAND/NOR…) : fan-in AÉRÉE. Toute la tuyauterie de
    #    grille reste STRICTEMENT à gauche de la barre OUT (qui commence à
    #    x=min(xs+xs_b) : les tronçons verticaux sont à x < ce bord et les taps
    #    horizontaux se terminent sur les ancres de grille (x = transistor − 1.37),
    #    donc AUCUN fil de grille n'est colinéaire avec / ne recouvre la barre
    #    OUT (défaut #1 signalé). Chaque tap est routé à la hauteur PROPRE de sa
    #    grille (loin du niveau oy), avec un petit décalage `off` par entrée pour
    #    que deux grilles d'une même rangée parallèle ne se recouvrent pas. Les
    #    ÉTIQUETTES sont empilées en escalier (x décalé) ET espacées de
    #    _PAS_LABEL en y (>=1.2) au-dessus des grilles PMOS : « jamais de labels
    #    collés » (défaut #2), et jamais au niveau de la barre OUT.
    nets = {sortie: out_pt}
    tous = list(haut) + list(bas)
    n = len(entrees)

    if n == 1:
        net = entrees[0]
        x_stub = min(xs + xs_b) - _STUB_GAUCHE
        y_h, y_b = oy + jeu / 2.0, oy - jeu / 2.0
        touche_haut = touche_bas = False
        for ref, e in haut:
            if grille_de.get(ref) == net:
                d.add(elm.Line().at((x_stub, y_h)).to((e.gate[0], y_h)))
                d.add(elm.Line().at((e.gate[0], y_h)).to(e.gate))
                touche_haut = True
        for ref, e in bas:
            if grille_de.get(ref) == net:
                d.add(elm.Line().at((x_stub, y_b)).to((e.gate[0], y_b)))
                d.add(elm.Line().at((e.gate[0], y_b)).to(e.gate))
                touche_bas = True
        if touche_haut and touche_bas:
            d.add(elm.Line().at((x_stub, y_h)).to((x_stub, y_b)))
        pt = (x_stub, y_h if touche_haut else y_b)
        d.add(elm.Dot().at(pt).label(in_label or net, loc="left"))
        nets[net] = pt
    else:
        base_top = max(e.gate[1] for _r, e in haut)   # hauteur des grilles PMOS
        x0 = min(xs + xs_b) - _STUB_GAUCHE - 1.6       # colonne poussée à gauche
        for i, net in enumerate(entrees):
            x_i = x0 - i * 1.3                          # escalier horizontal
            y_lab = base_top + 0.9 + i * _PAS_LABEL     # labels aérés vers le haut
            off = (i - (n - 1) / 2.0) * 0.26            # anti-recouvrement rangée
            cibles = [e for ref, e in tous if grille_de.get(ref) == net]
            y_taps = []
            for e in cibles:
                gx, gy = e.gate
                y_tap = gy + off
                d.add(elm.Line().at((x_i, y_tap)).to((gx, y_tap)))
                d.add(elm.Line().at((gx, y_tap)).to((gx, gy)))
                y_taps.append(y_tap)
            y_lo, y_hi = min(y_taps + [y_lab]), max(y_taps + [y_lab])
            d.add(elm.Line().at((x_i, y_lo)).to((x_i, y_hi)))
            pt = (x_i, y_lab)
            d.add(elm.Dot().at(pt).label(in_label or net, loc="left"))
            nets[net] = pt

    title_pt = (ox, y_vdd + 0.8)
    if titre:
        _titre_montage(d, result, title_pt)
    return {"in": nets[entrees[0]], "out": out_pt, "title": title_pt,
            "nets": nets, "absorbed_refs": set()}
