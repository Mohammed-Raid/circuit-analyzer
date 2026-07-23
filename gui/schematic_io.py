"""
@file schematic_io.py
@brief Sérialisation du schéma de l'éditeur (format .circ) et import depuis une
       liste de Composant (netlist/XML) — logique pure, testable sans Tk.
"""
import math

from circuit_analyzer.patterns.base import is_gnd, is_power

FORMAT  = "circ"
VERSION = 1

_GRID    = 20
_COL_DX  = 200      # espacement horizontal en grille à l'import
_ROW_DY  = 160      # espacement vertical
_ORIGIN  = (140, 120)
_RAIL_DY = 40       # décalage du symbole GND/VCC sous/au-dessus de la broche


def _snap(v: float) -> int:
    """@brief Aligne une coordonnée sur la grille."""
    return int(round(v / _GRID) * _GRID)


def editor_to_dict(comps, wires, counters, next_id) -> dict:
    """@brief Sérialise l'état de l'éditeur en dict .circ.

    @param comps    Dict {id -> CompInst}.
    @param wires    Liste de WireInst.
    @param counters Dict {type -> compteur de référence}.
    @param next_id  Prochain identifiant libre.
    @return dict Document .circ prêt à être écrit en JSON.
    """
    return {
        "format": FORMAT,
        "version": VERSION,
        "components": [
            {"id": c.id, "ref": c.ref, "type": c.comp_type, "value": c.value,
             "cx": c.cx, "cy": c.cy, "rotation": c.rotation}
            for c in comps.values()
        ],
        "wires": [
            {"from_comp_id": w.from_comp_id, "from_pin": w.from_pin,
             "to_comp_id": w.to_comp_id, "to_pin": w.to_pin}
            for w in wires
        ],
        "counters": dict(counters),
        "next_id": next_id,
    }


def type_reel(comp_type: str) -> tuple:
    """@brief Sépare la convention "U::NE555" -> ("U", "NE555").

    Les puces catalogue de la palette portent leur référence dans le
    comp_type (spec 2026-07-15 §5) : le .circ les stocke tels quels, tout
    EXPORT (netlist/Composant) doit re-séparer. Type simple -> value "".
    """
    if "::" in comp_type:
        t, _, v = comp_type.partition("::")
        return t, v
    return comp_type, ""


def _pin_monde(comp, pin, geom):
    """@brief Position monde d'une broche (rotation appliquée).

    @param geom Résolveur `(comp) -> def` — PAS un dict indexé par type : deux
           instances d'un même type peuvent avoir des brochages différents
           (brochage libre, spec 2026-07-23).
    """
    from gui.schematic_symbols import rotate_pin
    dx, dy = geom(comp)["pins"][pin]
    rdx, rdy = rotate_pin(dx, dy, comp.rotation)
    return (comp.cx + rdx, comp.cy + rdy)


def points_jonction(comps, wires, geom) -> list:
    """@brief Points monde où >= 3 extrémités de fils coïncident (spec §4).

    Une extrémité = la broche (monde, rotation appliquée) d'un bout de fil.
    Deux fils qui se REJOIGNENT sur une même broche = >= 3 extrémités au
    même point — le seuil >= 3 évite le point sur une simple liaison à 2.

    @param geom Résolveur `(comp) -> def` (cf. `_pin_monde`).
    """
    from collections import Counter
    compte = Counter()
    for w in wires:
        ca, cb = comps.get(w.from_comp_id), comps.get(w.to_comp_id)
        if not ca or not cb:
            continue
        compte[_pin_monde(ca, w.from_pin, geom)] += 1
        compte[_pin_monde(cb, w.to_pin, geom)] += 1
    return sorted(p for p, n in compte.items() if n >= 3)


def _ref_number(ref: str, type_: str) -> int:
    """@brief Numéro de fin de référence (R12 → 12), 0 si absent."""
    suffix = ref[len(type_):] if ref.startswith(type_) else ""
    return int(suffix) if suffix.isdigit() else 0


def build_from_components(composants, defs) -> dict:
    """@brief Convertit une liste de Composant en dict .circ (placement + fils).

    Les netlists/XML stockent des nœuds électriques, pas des fils broche-à-broche.
    On place les composants en grille puis on reconstruit les fils : chaîne pour
    un nœud signal, symbole GND/VCC dédié pour un rail.

    @param composants Liste de Composant (ref, type, pins{broche→nœud}, value).
    @param defs        Géométrie des types de l'éditeur ({type -> {'pins': {...}}}).
    @return dict Document .circ enrichi d'une clé '_report'
            ({'ignored_components': [...], 'dropped_pins': int}).
    """
    report = {"ignored_components": [], "dropped_pins": 0}

    placeable = []
    for comp in composants:
        if comp.type in ("GND", "VCC") or comp.type not in defs:
            report["ignored_components"].append(comp.ref)
            continue
        placeable.append(comp)

    components: list = []
    counters: dict = {}
    next_id = 1
    placed: list = []   # (id, comp, cx, cy)

    n = len(placeable)
    cols = max(1, int(math.ceil(math.sqrt(n)))) if n else 1
    for i, comp in enumerate(placeable):
        row, col = divmod(i, cols)
        cx = _snap(_ORIGIN[0] + col * _COL_DX)
        cy = _snap(_ORIGIN[1] + row * _ROW_DY)
        cid = next_id
        next_id += 1
        counters[comp.type] = max(counters.get(comp.type, 0),
                                  _ref_number(comp.ref, comp.type))
        components.append({"id": cid, "ref": comp.ref, "type": comp.type,
                           "value": comp.value, "cx": cx, "cy": cy,
                           "rotation": 0})
        placed.append((cid, comp, cx, cy))

    # Indexe nœud → [(id, broche, cx, cy, type)] pour les broches dessinables.
    net_pins: dict = {}
    for cid, comp, cx, cy in placed:
        avail = defs[comp.type]["pins"]
        for pin, net in comp.pins.items():
            if pin not in avail:
                report["dropped_pins"] += 1
                continue
            net_pins.setdefault(net, []).append((cid, pin, cx, cy, comp.type))

    wires: list = []
    for net, plist in net_pins.items():
        if is_gnd(net) or is_power(net):
            sym_type = "GND" if is_gnd(net) else "VCC"
            for cid, pin, cx, cy, ctype in plist:
                pdx, pdy = defs[ctype]["pins"][pin]
                px, py = cx + pdx, cy + pdy
                sy = py + _RAIL_DY if sym_type == "GND" else py - _RAIL_DY
                sid = next_id
                next_id += 1
                components.append({"id": sid, "ref": sym_type, "type": sym_type,
                                   "value": sym_type,
                                   "cx": _snap(px), "cy": _snap(sy),
                                   "rotation": 0})
                wires.append({"from_comp_id": cid, "from_pin": pin,
                              "to_comp_id": sid, "to_pin": "1"})
        else:
            for i in range(len(plist) - 1):
                (a_id, a_pin, *_), (b_id, b_pin, *_) = plist[i], plist[i + 1]
                wires.append({"from_comp_id": a_id, "from_pin": a_pin,
                              "to_comp_id": b_id, "to_pin": b_pin})

    return {
        "format": FORMAT,
        "version": VERSION,
        "components": components,
        "wires": wires,
        "counters": counters,
        "next_id": next_id,
        "_report": report,
    }
