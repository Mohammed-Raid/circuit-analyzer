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

from circuit_analyzer.patterns.base import is_ground_net, is_power_net


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


def graphe_conduction(graphe):
    """@brief Arcs D/S des MOSFET : [(ref, net_D, net_S)]. UNE construction
    par appel de détection — les candidats OUT sont exclusivement les nets de
    ce graphe (jamais les nets du circuit entier : garde-fou perf, spec § 1.1).

    @return liste vide si le circuit n'a aucun composant M (garde zéro-M)."""
    arcs = []
    for ref, comp in (graphe.graph.get('components', {}) or {}).items():
        if getattr(comp, 'type', None) != 'M':
            continue
        d, s = comp.pins.get('D'), comp.pins.get('S')
        if d and s and d != s:
            arcs.append((ref, d, s))
    return arcs


def _reseau(arcs, out, terminaux, interdits):
    """@brief SUR-ENSEMBLE des arêtes situées sur un chemin out→terminal
    (approximation R1 ∩ R2 — jamais un sous-ensemble).

    Deux passes d'atteignabilité (les nets terminaux/interdits et `out` ne
    sont jamais TRAVERSÉS, seulement atteints) :
      R1 = arêtes atteignables depuis `out` ;
      R2 = arêtes depuis lesquelles un terminal est atteignable.
    Réseau = R1 ∩ R2.

    L'intersection retient AUSSI des arêtes qui ne sont sur aucun chemin
    out→terminal : impasses pendantes sur un net du corridor, cycles
    latéraux, arêtes touchant un rail interdit depuis le corridor (mesuré
    ~5,3 % des graphes aléatoires). Le rejet de ces parasites est DÉLÉGUÉ
    à l'aval : `reduire_reseau` (jonctions irréductibles → None) puis
    `forme_pure` (arbres mixtes → None). En v1, les parasites ne peuvent
    donc produire que des faux négatifs, jamais un match faux.

    AVERTISSEMENT AOI v2 : si la grammaire accepte un jour les arbres
    MIXTES, ce sur-ensemble peut produire un arbre bien formé encodant un
    pseudo-chemin qui traverse un rail interdit (ex. OUT-M1-X, X-Ma-VDD-Mb-Y,
    X-Mz1-Z-Mz2-Y, Y-M4-GND). Il faudra alors un filtrage EXACT des chemins
    AVANT d'étendre la grammaire.
    """
    adjacence = {}
    for i, (_ref, n1, n2) in enumerate(arcs):
        adjacence.setdefault(n1, []).append((i, n2))
        adjacence.setdefault(n2, []).append((i, n1))

    bloques = set(interdits) | {out}

    def _atteignables(departs, stop_traverse):
        vues, frontiere, arete_vue = set(departs), list(departs), set()
        while frontiere:
            net = frontiere.pop()
            for i, voisin in adjacence.get(net, ()):  # ponytail: DFS simple, tailles = nb de MOSFET
                arete_vue.add(i)
                if voisin in vues or voisin in stop_traverse:
                    vues.add(voisin)
                    continue
                vues.add(voisin)
                frontiere.append(voisin)
        return arete_vue

    r1 = _atteignables([out], set(terminaux) | set(interdits))
    r2 = _atteignables(list(terminaux), bloques)
    return [arcs[i] for i in sorted(r1 & r2)]


def _classifier(genre_bas, refs_bas, genre_haut):
    """@brief (circuit_type, nom_fonction) selon la forme pure du pull-down.

    Grammaire v1 : dans les formes pures, « forme complémentaire + multisets
    de grilles égaux » ÉQUIVAUT à la dualité d'arbres (spec § 1.4)."""
    complementaire = {"feuille": "feuille", "serie": "parallele",
                      "parallele": "serie"}
    if genre_haut != complementaire[genre_bas]:
        return None
    if genre_bas == "feuille":
        return ("Inverseur (CMOS)", "NOT")
    if genre_bas == "serie":
        return ("Porte NAND (CMOS)", "NAND")
    return ("Porte NOR (CMOS)", "NOR")


def detecter_portes_cmos(graphe):
    """@brief Détecteur UNIQUE (une passe) des portes CMOS statiques.

    Émet les trois circuit_type (Inverseur/NAND/NOR) — enregistré en TÊTE de
    detecteur._DETECTEURS_COMPLEXES : l'anti-vol du matcher fait la priorité.
    Tout cas hors grammaire v1 est un rejet SILENCIEUX (zéro match, les M
    retombent sur le pipeline existant). @return list[dict] au contrat spec § 1.5.
    """
    arcs = graphe_conduction(graphe)
    if not arcs:                                   # garde zéro-M (perf)
        return []
    composants = graphe.graph.get('components', {}) or {}
    rails = {n for _r, n1, n2 in arcs for n in (n1, n2) if is_power_net(n)}
    masses = {n for _r, n1, n2 in arcs for n in (n1, n2) if is_ground_net(n)}
    candidats = sorted({n for _r, n1, n2 in arcs for n in (n1, n2)}
                       - rails - masses)

    matches = []
    for out in candidats:
        bas = _reseau(arcs, out, masses, rails)
        haut = _reseau(arcs, out, rails, masses)
        if not bas or not haut:
            continue
        refs_bas = {r for r, _n1, _n2 in bas}
        refs_haut = {r for r, _n1, _n2 in haut}
        if refs_bas & refs_haut:                   # transistor partagé
            continue
        # Rails du pull-up : UN SEUL net de rail (rejet bi-rail, PAR candidat).
        rails_haut = {n for _r, n1, n2 in haut for n in (n1, n2) if n in rails}
        masses_bas = {n for _r, n1, n2 in bas for n in (n1, n2) if n in masses}
        if len(rails_haut) != 1 or len(masses_bas) != 1:
            continue
        vdd, gnd = next(iter(rails_haut)), next(iter(masses_bas))

        arbre_bas = reduire_reseau(bas, out, gnd)
        arbre_haut = reduire_reseau(haut, out, vdd)
        if arbre_bas is None or arbre_haut is None:
            continue
        pur_bas = forme_pure(arbre_bas)
        pur_haut = forme_pure(arbre_haut)
        if pur_bas is None or pur_haut is None:
            continue

        grilles_bas = sorted(composants[r].pins.get('G', '') for r in pur_bas[1])
        grilles_haut = sorted(composants[r].pins.get('G', '') for r in pur_haut[1])
        if grilles_bas != grilles_haut:            # multisets de grilles égaux
            continue
        entrees = grilles_bas
        if len(set(entrees)) != len(entrees):      # grilles dupliquées
            continue
        if any((not e) or e in rails or e in masses or is_power_net(e)
               or is_ground_net(e) for e in entrees):   # grille sur rail
            continue
        if out in entrees:                         # sortie réinjectée
            continue
        # Rejet si une entrée est branchée sur un net interne des réseaux.
        nets_bas = {n for _, n1, n2 in bas for n in (n1, n2)}
        nets_haut = {n for _, n1, n2 in haut for n in (n1, n2)}
        internal_nets = (nets_bas | nets_haut) - {out, vdd, gnd}
        if any(e in internal_nets for e in entrees):
            continue

        classement = _classifier(pur_bas[0], pur_bas[1], pur_haut[0])
        if classement is None:
            continue
        circuit_type, nom_fn = classement

        # Cas 1+1 : critère d'orientation D/S (spec § 1.3) — source au rail.
        if nom_fn == "NOT":
            m_haut, m_bas = pur_haut[1][0], pur_bas[1][0]
            if composants[m_haut].pins.get('S') != vdd:
                continue
            if composants[m_bas].pins.get('S') != gnd:
                continue

        polarites = {r: "P" for r in refs_haut}
        polarites.update({r: "N" for r in refs_bas})
        matches.append({
            'circuit_type': circuit_type,
            'components': sorted(refs_haut | refs_bas),
            'nodes': {'entrees': list(entrees), 'sortie': out,
                      'vdd': vdd, 'gnd': gnd},
            'io': {'ins': list(entrees), 'out': out},
            'polarites': polarites,
            'arbres': {'pull_down': arbre_bas, 'pull_up': arbre_haut},
            'fonction': (nom_fn, list(entrees)),
            'expression': f"{out} = {nom_fn}({', '.join(entrees)})",
        })
    return matches
