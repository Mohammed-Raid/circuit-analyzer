"""
@file logique.py
@brief Détection des portes logiques CMOS (NOT / NAND-N / NOR-N) construites
en MOSFET — spec docs/superpowers/specs/2026-07-08-portes-logiques-cmos-design.md.

Organisation (unités testables indépendamment) :
  1. Algèbre d'arbres série/parallèle — fonctions PURES, sans référence aux
     transistors (c'est l'unité que AOI/OAI v2 étendra). Arbres = tuples
     ("feuille", ref) / ("serie", [...]) / ("parallele", [...]) — même
     convention de forme que impedance.py, mais algèbre PROPRE à ce module
     (les arêtes portent des nets de grille, pas des dipôles : les coupler
     serait du faux DRY).
"""


def reduire_reseau(arcs, a, b):
    """@brief Réduit un réseau d'arêtes en arbre série/parallèle entre a et b.

    @param arcs list[(ref, net1, net2)] — une arête par transistor.
    @param a, b Bornes du réseau (ex. OUT et GND).
    @return arbre ("feuille"/"serie"/"parallele", ...) ou None si le réseau
            n'est pas série/parallèle (pont), est vide, ou ne relie pas a à b.
    """
    edges = [(("feuille", ref), n1, n2) for ref, n1, n2 in arcs if n1 != n2]
    if not edges:
        return None

    def _enfants(arbre, genre):
        return list(arbre[1]) if arbre[0] == genre else [arbre]

    def _renverse(arbre):
        """Renverse le sens de parcours d'un arbre (chaîne lue à l'envers)."""
        genre = arbre[0]
        if genre == "feuille":
            return arbre
        enfants = [_renverse(e) for e in arbre[1]]
        if genre == "serie":
            enfants.reverse()
        return (genre, enfants)

    change = True
    while change:
        change = False
        # Fusion PARALLÈLE : arêtes entre la même paire de nets.
        par_paire = {}
        fusionne = []
        for t, n1, n2 in edges:
            cle = frozenset((n1, n2))
            if cle in par_paire:
                i = par_paire[cle]
                prev_t, pn1, pn2 = fusionne[i]
                fusionne[i] = (("parallele",
                                _enfants(prev_t, "parallele") + [t]), pn1, pn2)
                change = True
            else:
                par_paire[cle] = len(fusionne)
                fusionne.append((t, n1, n2))
        edges = fusionne
        # Fusion SÉRIE : net interne (ni a ni b) de degré exactement 2.
        degres = {}
        for _t, n1, n2 in edges:
            degres[n1] = degres.get(n1, 0) + 1
            degres[n2] = degres.get(n2, 0) + 1
        for net, deg in degres.items():
            if net in (a, b) or deg != 2:
                continue
            incidentes = [e for e in edges if net in (e[1], e[2])]
            if len(incidentes) != 2:
                continue
            (t1, x1, y1), (t2, x2, y2) = incidentes
            # Arêtes NON ORIENTÉES : l'ordre (n1, n2) d'un arc est arbitraire
            # (drain/source d'un MOSFET). On normalise chaque arête pour lire
            # la chaîne autre1 -> net -> autre2 : si le net commun est du
            # mauvais côté, on échange (n1, n2) et on renverse l'arbre (une
            # chaîne série lue à l'envers reste valide, enfants inversés).
            if x1 == net:
                t1, x1, y1 = _renverse(t1), y1, x1
            if y2 == net:
                t2, x2, y2 = _renverse(t2), y2, x2
            autre1, autre2 = x1, y2
            # autre1 == autre2 (auto-boucle) est impossible ici : la passe
            # parallèle vient de dédoublonner chaque paire de nets dans cette
            # même itération, donc deux arêtes incidentes à `net` ont
            # forcément des extrémités opposées distinctes.
            edges = [e for e in edges if e not in incidentes]
            edges.append((("serie", _enfants(t1, "serie")
                           + _enfants(t2, "serie")), autre1, autre2))
            change = True
            break

    if len(edges) == 1:
        t, n1, n2 = edges[0]
        if (n1, n2) == (a, b):
            return t
        if (n1, n2) == (b, a):
            # Chaîne aboutie mais lue b -> a : renverser pour le sens a -> b.
            return _renverse(t)
    return None


def feuilles(arbre):
    """@brief Refs des feuilles d'un arbre, en ordre de parcours (stable)."""
    if arbre[0] == "feuille":
        return [arbre[1]]
    refs = []
    for enfant in arbre[1]:
        refs.extend(feuilles(enfant))
    return refs


def forme_pure(arbre):
    """@brief (genre, refs) si l'arbre est une FORME PURE v1, sinon None.

    Formes pures : feuille seule, série de feuilles, parallèle de feuilles.
    Un arbre mixte (AOI valide compris) renvoie None — grammaire v1, cf. spec
    § 1.4 (le comparateur de dualité canonique général est différé à AOI v2).
    """
    if arbre[0] == "feuille":
        return ("feuille", [arbre[1]])
    genre, enfants = arbre
    if all(e[0] == "feuille" for e in enfants):
        return (genre, [e[1] for e in enfants])
    return None
