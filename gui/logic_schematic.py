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
    # Task 8 — en attendant, la vue détaillée montre le symbole (jamais d'écran vide).
    return _porte_symbole(d, result, ci, origin, titre, in_label, out_label)
