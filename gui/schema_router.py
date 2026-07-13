"""@file schema_router.py
@brief Routage Manhattan A* pour les fils inter-etages (spec 2026-07-13 §4).
Module PUR (aucun import graphique). Noeuds = grille au pas PAS ; interdits =
interieur STRICT des obstacles ; cout = PAS par arete + PENALITE_COUDE par
virage ; les aretes des nets deja routes sont reservees (pas de chevauchement
colineaire ; croisement perpendiculaire libre).
"""
import heapq

from gui.schema_grid import PAS, Rect, snap

PENALITE_COUDE = 1.5   # 3 * PAS — favorise les longs segments droits
_MAX_NOEUDS = 20000    # garde-fou : au-dela, on abandonne (repli appelant)
_DIRS = ((PAS, 0.0), (-PAS, 0.0), (0.0, PAS), (0.0, -PAS))


def _cle(p):
    return (round(p[0], 6), round(p[1], 6))


def _arete(p, q):
    a, b = _cle(p), _cle(q)
    return (a, b) if a <= b else (b, a)


def _zone(nets, obstacles):
    """@brief Bbox englobante (ports + obstacles) dilatee de 2 canaux."""
    xs, ys = [], []
    for _n, dep, arr in nets:
        xs += [dep[0], arr[0]]; ys += [dep[1], arr[1]]
    for r in obstacles:
        xs += [r.x0, r.x1]; ys += [r.y0, r.y1]
    m = 4 * PAS
    return Rect(snap(min(xs)) - m, snap(min(ys)) - m,
                snap(max(xs)) + m, snap(max(ys)) + m)


def _fusionner(points):
    """@brief Supprime les points intermediaires colineaires (garde un point
    seulement si la direction change)."""
    if len(points) < 3:
        return points
    res = [points[0]]
    for i in range(1, len(points) - 1):
        dx1 = points[i][0] - points[i - 1][0]
        dy1 = points[i][1] - points[i - 1][1]
        dx2 = points[i + 1][0] - points[i][0]
        dy2 = points[i + 1][1] - points[i][1]
        if (dx1 == 0) != (dx2 == 0) or (dy1 == 0) != (dy2 == 0):
            res.append(points[i])
    res.append(points[-1])
    return res


def _astar(dep, arr, obstacles, zone, reservees):
    """@brief A* 4-directions ; etat = (noeud, direction d'arrivee)."""
    dep, arr = _cle(dep), _cle(arr)

    def h(p):
        return abs(p[0] - arr[0]) + abs(p[1] - arr[1])

    def praticable(p, exempt):
        if not (zone.x0 <= p[0] <= zone.x1 and zone.y0 <= p[1] <= zone.y1):
            return False
        if p in (dep, arr):
            return True
        return not any(r.contient_strict(p[0], p[1]) for r in obstacles)

    ouverts = [(h(dep), 0.0, dep, None, None)]  # f, g, noeud, dir, parent-etat
    vus = {}
    parents = {}
    explores = 0
    while ouverts:
        f, g, p, dirn, parent = heapq.heappop(ouverts)
        etat = (p, dirn)
        if etat in vus and vus[etat] <= g:
            continue
        vus[etat] = g
        parents[etat] = parent
        explores += 1
        if explores > _MAX_NOEUDS:
            return None
        if p == arr:
            chemin = [p]
            while parents[etat] is not None:
                etat = parents[etat]
                chemin.append(etat[0])
            return list(reversed(chemin))
        for dx, dy in _DIRS:
            q = _cle((p[0] + dx, p[1] + dy))
            if not praticable(q, (dep, arr)):
                continue
            # Arete bloquee si son milieu est STRICTEMENT dans un obstacle
            mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
            if any(r.contient_strict(mx, my) for r in obstacles):
                continue
            if _arete(p, q) in reservees:
                continue
            ng = g + PAS + (PENALITE_COUDE if dirn and dirn != (dx, dy) else 0.0)
            netat = (q, (dx, dy))
            if netat in vus and vus[netat] <= ng:
                continue
            heapq.heappush(ouverts, (ng + h(q), ng, q, (dx, dy), (p, dirn)))
    return None


def router(nets, obstacles):
    """@brief Route chaque net dans l'ordre de la liste (spec §4.2).

    @param nets [(nom, depart, arrivee), ...] — depart/arrivee snappes PAS.
    @param obstacles list[Rect] (slots d'etages + stubs Z locales).
    @return dict nom -> polyligne (coudes fusionnes) | None si echec.
    """
    if not nets:
        return {}
    zone = _zone(nets, obstacles)
    reservees = set()
    resultats = {}
    for nom, dep, arr in nets:
        chemin = _astar(dep, arr, obstacles, zone, reservees)
        if chemin is None:
            resultats[nom] = None
            continue
        for p, q in zip(chemin, chemin[1:]):
            reservees.add(_arete(p, q))
        resultats[nom] = _fusionner(chemin)
    return resultats
