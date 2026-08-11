"""@file schematic_symbols.py
@brief Primitives vectorielles des symboles de l'editeur (spec 2026-07-15
§3). Module PUR (aucun import graphique) : chaque traceur produit des
primitives en coordonnees MONDE centrees sur (0,0), rotation appliquee ici.

Primitive :
  ("line", [(x,y),...], epaisseur)
  ("polygon", [(x,y),...], rempli: bool)
  ("arc", (x0,y0,x1,y1), start_deg, extent_deg)
  ("text", (x,y), texte, taille, ancre)
"""

import math
import xml.etree.ElementTree as ET

from gui.theme import SCHEMA_COLORS

# Couleur des composants sans symbole dedie (boite generique, brochage libre).
# Source UNIQUE : l'editeur l'importe, aucun hex duplique.
AUTO_COLOR = "#94a3b8"


def rotate_pin(dx, dy, rotation):
    """@brief Tourne (dx,dy) de `rotation` degres sens horaire (0/90/180/270)."""
    if rotation == 90:
        return (dy, -dx)
    if rotation == 180:
        return (-dx, -dy)
    if rotation == 270:
        return (-dy, dx)
    return (dx, dy)


def _rot_prims(prims, rotation):
    """@brief Applique la rotation a toutes les primitives."""
    if rotation % 360 == 0:
        return prims
    out = []
    for p in prims:
        if p[0] in ("line", "polygon"):
            out.append((p[0], [rotate_pin(x, y, rotation) for x, y in p[1]],
                        p[2]))
        elif p[0] == "arc":
            x0, y0, x1, y1 = p[1]
            (ax, ay) = rotate_pin(x0, y0, rotation)
            (bx, by) = rotate_pin(x1, y1, rotation)
            out.append(("arc", (ax, ay, bx, by),
                        (p[2] + rotation) % 360, p[3]))
        elif p[0] == "text":
            out.append(("text", rotate_pin(*p[1], rotation), p[2], p[3], p[4]))
    return out


def _tr_r(d):
    # Zigzag 6 crêtes entre -24 et 24, amorces jusqu'aux pins.
    a = 8
    pts = [(-40, 0), (-24, 0)]
    xs = [-24 + i * 8 for i in range(1, 6)]
    for i, x in enumerate(xs):
        pts.append((x, -a if i % 2 == 0 else a))
    pts += [(24, 0), (40, 0)]
    return [("line", pts, 2)]


def _tr_c(d):
    return [
        ("line", [(-30, 0), (-4, 0)], 2),
        ("line", [(-4, -12), (-4, 12)], 3),
        ("line", [(4, -12), (4, 12)], 3),
        ("line", [(4, 0), (30, 0)], 2),
    ]


def _tr_l(d):
    prims = [("line", [(-40, 0), (-24, 0)], 2)]
    for i in range(3):
        x0 = -24 + i * 16
        prims.append(("arc", (x0, -8, x0 + 16, 8), 0, 180))
    prims.append(("line", [(24, 0), (40, 0)], 2))
    return prims


def _tr_d(d, value=""):
    prims = [
        ("line", [(-30, 0), (-8, 0)], 2),
        ("polygon", [(-8, -10), (-8, 10), (8, 0)], True),
        ("line", [(8, -10), (8, 10)], 3),
        ("line", [(8, 0), (30, 0)], 2),
    ]
    if (value or "").upper().startswith("LED"):
        prims.append(("line", [(2, -12), (10, -20)], 1))
        prims.append(("line", [(8, -10), (16, -18)], 1))
    return prims


def _tr_f(d):
    return [
        ("line", [(-40, 0), (40, 0)], 2),
        ("polygon", [(-20, -7), (20, -7), (20, 7), (-20, 7)], False),
    ]


def _tr_q(d):
    # NPN : barre de base verticale, cercle, collecteur haut, émetteur bas fléché.
    return [
        ("line", [(-30, 0), (-8, 0)], 2),
        ("line", [(-8, -16), (-8, 16)], 3),
        ("line", [(-8, -8), (30, -30)], 2),
        ("line", [(-8, 8), (30, 30)], 2),
        ("polygon", [(18, 20), (30, 30), (16, 28)], True),   # flèche émetteur
        # Cercle en 2 demi-arcs : tk n'affiche rien pour un "arc" 360° d'un
        # seul tenant (extent 360 == 0 visuellement, verifie empiriquement).
        ("arc", (-24, -24, 24, 24), 0, 180),
        ("arc", (-24, -24, 24, 24), 180, 180),
    ]


def _tr_m(d):
    # MOSFET canal N simplifié : grille + 3 segments de canal + flèche.
    return [
        ("line", [(-30, 0), (-10, 0)], 2),
        ("line", [(-10, -16), (-10, 16)], 3),
        ("line", [(-4, -18), (-4, -6)], 2),
        ("line", [(-4, -6), (-4, 6)], 2),
        ("line", [(-4, 6), (-4, 18)], 2),
        ("line", [(-4, -12), (30, -30)], 2),
        ("line", [(-4, 12), (30, 30)], 2),
        ("polygon", [(4, 8), (-4, 12), (4, 16)], True),      # flèche substrat
    ]


def _tr_u(d):
    # Triangle AOP : pins IN+ (-40,-20), IN- (-40,20), OUT (40,0).
    return [
        ("polygon", [(-24, -32), (-24, 32), (40, 0)], False),
        ("line", [(-40, -20), (-24, -20)], 2),
        ("line", [(-40, 20), (-24, 20)], 2),
        ("text", (-16, -20), "+", 10, "center"),
        ("text", (-16, 20), "-", 10, "center"),
    ]


def _tr_gnd(d):
    prims = [("line", [(0, -20), (0, 0)], 2)]
    for i, hw in enumerate([16, 10, 5]):
        prims.append(("line", [(-hw, i * 5), (hw, i * 5)], 2))
    return prims


def _tr_vcc(d):
    return [
        ("line", [(0, 20), (0, 2)], 2),
        ("polygon", [(-10, 2), (10, 2), (0, -14)], True),
    ]


def _tr_t(d):
    # Transfo : 2 enroulements verticaux + 2 barres centrales.
    prims = []
    for cote in (-1, 1):
        x = cote * 12
        for i in range(3):
            y0 = -24 + i * 16
            prims.append(("arc", (x - 8, y0, x + 8, y0 + 16),
                          90 if cote < 0 else 270, 180))
        prims.append(("line", [(cote * 40, -20), (x, -20)], 2))
        prims.append(("line", [(cote * 40, 20), (x, 20)], 2))
    prims.append(("line", [(-3, -26), (-3, 26)], 1))
    prims.append(("line", [(3, -26), (3, 26)], 1))
    return prims


def _tr_k(d):
    # Relais : bobine (rectangle) + contact incliné.
    return [
        ("polygon", [(-36, -12), (-4, -12), (-4, 12), (-36, 12)], False),
        ("line", [(-40, -20), (-20, -20), (-20, -12)], 2),
        ("line", [(-40, 20), (-20, 20), (-20, 12)], 2),
        ("line", [(8, -20), (40, -20)], 2),
        ("line", [(8, 20), (40, 20)], 2),
        ("line", [(8, 20), (28, -16)], 2),
    ]


_TRACEURS = {
    "R": _tr_r, "C": _tr_c, "L": _tr_l, "F": _tr_f, "Q": _tr_q,
    "M": _tr_m, "U": _tr_u, "GND": _tr_gnd, "VCC": _tr_vcc,
    "T": _tr_t, "K": _tr_k,
}


def _tr_boite(defn):
    """@brief Boîte générique à encoche (types perso, puces catalogue) :
    rectangle + encoche haut + stub par broche (le trait court qui va du
    corps a la broche, style DIP)."""
    w2, h2 = defn["w"] // 2, defn["h"] // 2
    corps = w2 - 8
    prims = [
        ("polygon", [(-corps, -h2), (corps, -h2), (corps, h2), (-corps, h2)],
         False),
        ("arc", (-8, -h2 - 4, 8, -h2 + 8), 180, 180),
    ]
    for pn, (px, py) in defn["pins"].items():
        bord = corps if px > 0 else -corps
        if abs(px) > corps:
            prims.append(("line", [(bord, py), (px, py)], 2))
        fonction = (defn.get("fonctions") or {}).get(pn, "")
        libelle = f"{pn} {fonction}".strip()
        # Ancre côté BORD (pas côté pin) : le libellé doit croître VERS
        # l'intérieur du boîtier, jamais vers la broche/l'encoche (bug
        # trouvé lors de la boucle visuelle Task 5 — "n FONCTION" débordait
        # sur la pastille de broche pour les fonctions longues, ex. "RESET").
        ancre = "w" if px < 0 else "e"
        tx = bord + (6 if px < 0 else -6)
        prims.append(("text", (tx, py), libelle, 7, ancre))
    return prims


def est_boite_generique(comp_type: str) -> bool:
    """@brief Vrai si `primitives()` rend ce type via `_tr_boite` (boîte à
    encoche + libellés "n FONCTION" déjà dessinés dans les primitives).

    Utilisé par l'éditeur pour éviter de superposer un second libellé de
    broche générique (bare pin name) par-dessus celui de la boîte — les
    deux se chevauchaient (ex. puces catalogue, spec §5).
    """
    return comp_type != "D" and comp_type not in _TRACEURS


def primitives(comp_type, defn, rotation, value=""):
    """@brief Primitives monde du symbole, rotation appliquee.

    Types traces : table _TRACEURS. Un type avec une forme importee
    (defn["primitives"], spec 2026-08-05) court-circuite le dispatch. Tout
    autre type (perso, puce catalogue) -> boite generique a encoche.
    """
    if defn.get("primitives"):
        prims = list(defn["primitives"]) + _libelles_broches(defn)
    elif comp_type == TYPE_LIBRE:
        prims = _tr_boite_libre(defn)
    elif comp_type == "D":
        prims = _tr_d(defn, value)
    elif comp_type in _TRACEURS:
        prims = _TRACEURS[comp_type](defn)
    else:
        prims = _tr_boite(defn)
    return _rot_prims(prims, rotation)


def def_puce(value, broches):
    """@brief Def dynamique DIP pour une puce catalogue (spec §5).

    Broches 1..n/2 a GAUCHE de haut en bas, n/2+1..n a DROITE de bas en
    haut (convention DIP). Pas vertical 20, largeur 120, coordonnees sur
    grille 20. Cles compatibles COMP_DEFS + "fonctions".
    """
    nums = sorted(broches, key=int)
    n = len(nums)
    gauche = nums[: (n + 1) // 2]
    droite = nums[(n + 1) // 2:]
    rangees = max(len(gauche), len(droite))
    h2 = ((rangees + 1) * 20) // 2
    h2 = h2 + (20 - h2 % 20) % 20        # multiple de 20
    pins = {}
    for i, pn in enumerate(gauche):
        pins[pn] = (-60, -h2 + 20 * (i + 1))
    for i, pn in enumerate(droite):
        pins[pn] = (60, h2 - 20 * (i + 1))
    return {
        "label": value, "color": SCHEMA_COLORS["COMP"]["U"], "w": 120, "h": h2 * 2,
        "pins": pins, "default_value": value,
        "fonctions": dict(broches),
    }


def primitives_depuis_dataitem(xml_texte: str, echelle: float,
                                cx: float = 0.0, cy: float = 0.0) -> list:
    """@brief Contour reel d'un <DataItem> ERetroDesign en primitives d'edition.

    Parse datasegment/DataSegment (Spoint/Epoint -> "line"), dataarc/DataArc
    (pCenter/stAngle/swAngle, rayon = distance pCenter->Spoint -> "arc"),
    datapolygon/DataPolygon (points groupes -> un seul "polygon" ferme).
    Chaque coordonnee est recentree sur (cx, cy) PUIS divisee par *echelle* —
    exactement la meme formule que le calcul des broches dans eretro_lib.py
    (`(px - cx) / ECHELLE`), pour que forme et broches partagent la meme
    origine. L'appelant DOIT passer le meme (cx, cy, echelle) que celui utilise
    pour les broches, jamais des valeurs cablees en dur ici, sous peine de
    desaligner pattes et contour.
    Ne leve JAMAIS : XML invalide ou geometrie degeneree -> ignores, jamais
    une exception qui ferait echouer tout l'import du composant.

    @param xml_texte Fragment <DataItem>...</DataItem> (texte).
    @param echelle Facteur d'echelle unites BoardSCH -> unites editeur (=
           eretro_lib.ECHELLE, actuellement 1 : pas de mise a l'echelle).
    @param cx, cy Origine (centroide) a soustraire avant division, en unites
           XML — memes valeurs que le cx, cy utilises pour les broches.
    @return list[tuple] Primitives ("line"|"arc"|"polygon", ...). Vide si le
            composant n'a ni polygone, ni segment, ni arc exploitable.
    """
    try:
        r = ET.fromstring(xml_texte)
    except ET.ParseError:
        return []
    prims = []
    for s in r.findall("./datasegment/DataSegment"):
        try:
            sp, ep = s.find("Spoint"), s.find("Epoint")
            x1 = (float(sp.findtext("X") or 0) - cx) / echelle
            y1 = (float(sp.findtext("Y") or 0) - cy) / echelle
            x2 = (float(ep.findtext("X") or 0) - cx) / echelle
            y2 = (float(ep.findtext("Y") or 0) - cy) / echelle
            prims.append(("line", [(x1, y1), (x2, y2)], 2))
        except (AttributeError, ValueError, TypeError):
            continue
    for a in r.findall("./dataarc/DataArc"):
        try:
            c = a.find("pCenter")
            acx = (float(c.findtext("X") or 0) - cx) / echelle
            acy = (float(c.findtext("Y") or 0) - cy) / echelle
            sp = a.find("Spoint")
            sx = (float(sp.findtext("X") or 0) - cx) / echelle
            sy = (float(sp.findtext("Y") or 0) - cy) / echelle
            rayon = math.hypot(sx - acx, sy - acy)
            if rayon <= 0:
                continue
            debut = float(a.findtext("stAngle") or 0)
            etendue = float(a.findtext("swAngle") or 0)
            prims.append(("arc",
                         (acx - rayon, acy - rayon, acx + rayon, acy + rayon),
                         debut, etendue))
        except (AttributeError, ValueError, TypeError):
            continue
    points = []
    for p in r.findall("./datapolygon/DataPolygon"):
        try:
            pt = p.find("point")
            points.append(((float(pt.findtext("X") or 0) - cx) / echelle,
                           (float(pt.findtext("Y") or 0) - cy) / echelle))
        except (AttributeError, ValueError, TypeError):
            continue
    if len(points) >= 3:
        prims.append(("polygon", points, False))
    return prims


# ── Brochage libre par instance (spec 2026-07-23) ────────────────────────────

TYPE_LIBRE = "__libre__"   # type de RENDU d'un composant au brochage libre

BOITE_MIN_W = 80
BOITE_MIN_H = 60
BOITE_MARGE = 20
CHAR_W = 7          # largeur approx. d'un caractere du libelle de broche


def geometrie_libre(pinout, w_mini=None, h_mini=None, roles=None,
                    w_exact=None, h_exact=None):
    """@brief Def d'une boite au brochage libre (spec 2026-07-23).

    @param pinout  {nom: (cote 'L'/'R'/'T'/'B', decalage signe sur ce bord)}.
    @param w_mini,h_mini Taille PLANCHER voulue par l'utilisateur : la boite
           fait au moins ca, mais l'auto-ajustement continue de garantir que
           broches et libelles tiennent — on ne peut donc pas fabriquer un
           composant dont les broches debordent du cadre.
    @param roles   {nom: role} — le libelle devient « nom ROLE », comme le fait
           deja `_tr_boite` pour les puces du catalogue.
    @param w_exact,h_exact Taille EXACTE (pas un plancher) : court-circuite le
           calcul heuristique de marge/libelle ci-dessous. Reserve aux formes
           importees (primitives reelles, spec 2026-08-05) dont la vraie
           taille est deja connue -- le remplissage genereux pense pour une
           boite etiquetee A LA MAIN n'a pas de sens pour un contour reel deja
           dessine : broche qui flotte loin de la forme (defaut trouve en
           boucle visuelle sur Vss.xml/VCC+.xml du boss apres livraison).
    @return def compatible COMP_DEFS, taille AUTO-AJUSTEE (ou EXACTE).
    """
    roles = roles or {}

    def _lab(n):
        return f"{n} {roles.get(n, '')}".strip()

    if w_exact is not None and h_exact is not None:
        # EXACTE veut dire EXACTE : pas de BOITE_MIN_W/H ici, sinon une forme
        # reelle plus petite que le plancher UI (ex. VCC+/Vss, h=20) se fait
        # regonfler et la broche recalculee au-dela du contour reel (meme
        # symptome que le bug corrige en bf341d4, cette fois pour w_exact/
        # h_exact eux-memes). Le plancher `1` evite juste un rectangle
        # degenere si une forme importee a une dimension nulle.
        w = max(1, int(w_exact))
        h = max(1, int(h_exact))
    else:
        lat = [abs(d) for c, d in pinout.values() if c in ("L", "R")]
        ver = [abs(d) for c, d in pinout.values() if c in ("T", "B")]
        # La boite doit aussi loger les LIBELLES, dessines a l'interieur : sans
        # ca les noms des bords opposes se telescopent ("IN1 VCCOUT1", defaut
        # trouve en boucle visuelle le 2026-07-23). Le ROLE en fait partie.
        lg = max((len(_lab(n)) for n, (c, _d) in pinout.items() if c == "L"), default=0)
        ld = max((len(_lab(n)) for n, (c, _d) in pinout.items() if c == "R"), default=0)
        h = max(BOITE_MIN_H, 2 * max(lat, default=0) + BOITE_MARGE)
        w = max(BOITE_MIN_W, 2 * max(ver, default=0) + BOITE_MARGE,
                (lg + ld) * CHAR_W + 3 * BOITE_MARGE)
        if ver:
            # Les libelles du haut/bas mordent vers l'interieur : on leur
            # reserve une bande, sinon ils croisent ceux des bords lateraux.
            h += 2 * BOITE_MARGE
        # PLANCHER applique APRES l'auto-ajustement : jamais sous le besoin reel.
        w = max(w, int(w_mini or 0))
        h = max(h, int(h_mini or 0))
    w2, h2 = w // 2, h // 2
    pins, cotes = {}, {}
    for nom, (cote, dec) in pinout.items():
        pins[nom] = {"L": (-w2, dec), "R": (w2, dec),
                     "T": (dec, -h2), "B": (dec, h2)}[cote]
        cotes[nom] = cote
    return {"label": "", "color": AUTO_COLOR, "w": w, "h": h,
            "pins": pins, "cotes": cotes, "fonctions": dict(roles),
            "default_value": ""}


def etendue_primitives(prims) -> tuple:
    """@brief (largeur, hauteur) totale de primitives, centrees sur (0,0).

    Sert de repli quand une forme reelle est choisie sans `boite` explicite
    (ex. nouveau composant + forme piochee au selecteur, "Ajuster
    automatiquement" coche) -- sans lui, `geometrie_libre` retombe sur
    l'heuristique de remplissage et fait a nouveau flotter la broche loin
    du contour reel (meme defaut que bf341d4, cette fois cote hand-picked
    plutot qu'import).
    """
    mx = my = 0
    for p in prims:
        if p[0] in ("line", "polygon"):
            for x, y in p[1]:
                mx, my = max(mx, abs(x)), max(my, abs(y))
        elif p[0] == "arc":
            x0, y0, x1, y1 = p[1]
            mx = max(mx, abs(x0), abs(x1))
            my = max(my, abs(y0), abs(y1))
    return mx * 2, my * 2


def geometrie_reelle(pinout, primitives=None, w_exact=None, h_exact=None, **kwargs):
    """@brief `geometrie_libre` qui derive w_exact/h_exact d'un contour reel.

    Centralise la combinaison `etendue_primitives(primitives)` +
    `geometrie_libre(..., w_exact=, h_exact=)` reprise A L'IDENTIQUE sur
    plusieurs sites independants (export XML `_xml_composant`, rendu editeur
    `_geom`, import `.circ` `build_from_components`) -- revue finale de
    branche round 1, Important 3+4. Sans elle, une broche recalculee
    "flotte" hors du contour reel des qu'un site oublie w_exact/h_exact
    (meme defaut que bf341d4/48ddf30, propage ailleurs).

    @param pinout {nom: (cote, decalage)} — brochage libre de l'instance.
    @param primitives Contour reel de l'instance, ou None/vide (heuristique
           habituelle de `geometrie_libre`).
    @param w_exact Largeur EXACTE a imposer, si l'appelant l'a deja calculee
           autrement qu'a partir de `primitives` (ex. boite catalogue) --
           prime alors sur le calcul automatique depuis `primitives`. None
           (defaut) laisse `primitives` decider.
    @param h_exact Idem pour la hauteur.
    @param kwargs Reste transmis tel quel a `geometrie_libre` (ex. `roles`).
           Note (revue finale round 2, Minor A) : `w_exact`/`h_exact` sont
           desormais des parametres nommes explicites -- avant ce fix, un
           appelant qui les passait via `**kwargs` declenchait
           `TypeError: got multiple values for keyword argument 'w_exact'`,
           puisque la fonction les passait deja par mot-cle en interne.
           Piege latent : personne ne les passait encore, mais restait un
           piege pour le prochain appelant.
    """
    if (w_exact is None or h_exact is None) and primitives:
        bw, bh = etendue_primitives(primitives)
        w_exact = w_exact if w_exact is not None else bw
        h_exact = h_exact if h_exact is not None else bh
    return geometrie_libre(pinout, w_exact=w_exact, h_exact=h_exact, **kwargs)


def aimanter_bord(dx, dy, w, h, pas):
    """@brief (dx,dy) relatif au centre -> (cote, decalage aligne sur `pas`).

    Bord dont la distance perpendiculaire est la plus faible. A EGALITE (coin),
    les bords HORIZONTAUX gagnent : arbitraire, mais deterministe donc testable
    (changer l'ordre du parcours ci-dessous suffit a changer l'arbitrage).
    """
    w2, h2 = w / 2, h / 2
    d = {"L": abs(dx + w2), "R": abs(dx - w2),
         "T": abs(dy + h2), "B": abs(dy - h2)}
    m = min(d.values())
    for cote in ("T", "B", "L", "R"):          # cet ordre = arbitrage du coin
        if d[cote] == m:
            long_ = dx if cote in ("T", "B") else dy
            return (cote, int(round(long_ / pas) * pas))


def modele_brochage(modele, n=0):
    """@brief Brochage tout fait d'un boitier courant (spec 2026-07-23).

    DIP : 1..n/2 a GAUCHE de haut en bas, n/2+1..n a DROITE de bas en haut —
    la numerotation d'un vrai boitier, la meme que `def_puce`. Connecteur (le
    « bornier » n'en est qu'un raccourci de taille) : tout a gauche.

    @return list [(nom, cote, decalage)] ORDONNEE = ordre de la netlist.
    @throws ValueError Si `n` est hors bornes, impair ou trop petit pour un DIP,
            ou si le modele est inconnu.
    """
    n = int(n)
    if not 2 <= n <= 64:
        raise ValueError(f"nombre de broches hors bornes : {n}")
    pas = 20

    def _depart(m):
        """Premier decalage pour m broches centrees, aligne sur la grille."""
        y = -((m - 1) * pas) // 2
        return y - (y % pas)

    if modele == "DIP":
        if n % 2 or n < 4:
            raise ValueError(f"un DIP exige un nombre pair >= 4 : {n}")
        m = n // 2
        y0 = _depart(m)
        gauche = [(str(i + 1), "L", y0 + i * pas) for i in range(m)]
        droite = [(str(n - i), "R", y0 + i * pas) for i in range(m)]
        return gauche + droite[::-1]
    if modele == "Connecteur":
        y0 = _depart(n)
        return [(str(i + 1), "L", y0 + i * pas) for i in range(n)]
    raise ValueError(f"modele inconnu : {modele!r}")


def _libelles_broches(defn):
    """@brief Un libelle texte par broche, positionne selon son cote (defn["cotes"]).

    Factorise depuis `_tr_boite_libre` : reutilise par tout traceur qui a
    besoin des labels de broches standard sans les redessiner lui-meme (forme
    reelle importee d'ERetroDesign, spec 2026-08-05).
    """
    prims = []
    for pn, (px, py) in defn["pins"].items():
        cote = (defn.get("cotes") or {}).get(pn, "L")
        fonction = (defn.get("fonctions") or {}).get(pn, "")
        libelle = f"{pn} {fonction}".strip()
        if cote in ("L", "R"):
            ancre = "w" if cote == "L" else "e"
            tx, ty = px + (6 if cote == "L" else -6), py
        else:
            ancre = "center"
            tx, ty = px, py + (10 if cote == "T" else -10)
        prims.append(("text", (tx, ty), libelle, 7, ancre))
    return prims


def _tr_boite_libre(defn):
    """@brief Boite au brochage libre : broches sur les 4 bords (spec 2026-07-23).

    `_tr_boite` ne sait placer que des broches gauche/droite (il tranche le cote
    sur `px > 0`), d'ou ce traceur separe qui lit `defn["cotes"]` et oriente le
    libelle en consequence. Le laisser separe protege le rendu DIP des puces
    catalogue, dont depend tout l'import ERetroDesign.
    """
    w2, h2 = defn["w"] // 2, defn["h"] // 2
    prims = [("polygon", [(-w2, -h2), (w2, -h2), (w2, h2), (-w2, h2)], False)]
    prims.extend(_libelles_broches(defn))
    return prims
