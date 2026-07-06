"""
@file schema_labels.py
@brief Moteur anti-collision de labels pour les figures de schemas (ilots,
reseaux d'impedance depliees, ponts).

`ajuster_labels(fig)` est la passe de resolution appliquee EN FIN de
construction par toutes les fabriques de figures (`_make_fig`,
`_make_chain_fig`, `_make_branched_fig`, `_make_island_fig` dans
gui/circuit_viewer.py ; `_dessiner_impl`/`dessiner_pont` dans
gui/impedance_schematic.py) : garantit, a partir des METRIQUES REELLES du
renderer (`Text.get_window_extent`, pas d'approximation geometrique), qu'aucun
Text visible ne chevauche un autre Text ni un segment de fil/symbole (Line2D)
du schema.

Principe (cf. design docs/superpowers/specs/2026-07-06-ilots-rendu-rigoureux-
design.md section 1) :
  - un rendu Agg unique fournit le renderer ;
  - obstacles = bboxes des autres Text + points echantillonnes le long des
    Line2D de chaque axe (fils/symboles), en coordonnees display ;
  - resolution DETERMINISTE (textes tries par (x arrondi, y arrondi,
    contenu)), iterations bornees (<= 20) : a chaque chevauchement, le texte
    de moindre priorite est pousse le long de l'axe de moindre recouvrement,
    du recouvrement + une marge ;
  - priorites : titres/suptitles/labels d'axe (IMMOBILES, ne bougent jamais)
    > noms de net (heuristique : texte tout en majuscules, ex. VIN/VOUT/VCC/
    GND) > labels de composant (tout le reste) ;
  - apres resolution, les limites de chaque axe sont re-etendues pour
    contenir toutes les bboxes de texte qui lui appartiennent (aucun label
    clippe, quel que soit le zoom) ;
  - AUCUN deplacement si aucune collision n'est detectee (stabilite visuelle
    : sur une figure deja propre, la passe est un no-op strict).

AUCUN cycle d'import : ce module n'importe ni gui.circuit_viewer ni
gui.impedance_schematic (c'est l'inverse qui est vrai -- ces deux modules
l'importent en fin de fabrique de figure).
"""
import logging
import math

from matplotlib.backends.backend_agg import FigureCanvasAgg

_log = logging.getLogger(__name__)

# Bornes de la resolution deterministe (cf. design section 1).
_MAX_ITER = 20

# Marge ajoutee au recouvrement mesure avant de pousser un texte, en points
# d'ecran convertis en pixels via le dpi de la figure. schema_labels n'a pas
# acces aux unites schemdraw internes des appelants (aucun cycle d'import) :
# on definit donc sa PROPRE unite de marge, independante des constantes
# _Z_DETAIL_*/_Z_LABEL_CLEAR de circuit_viewer.
_MARGE_POINTS = 3.0

# Echantillonnage des Line2D : un point tous les N pixels le long de chaque
# segment (borne a un nombre max de points par segment pour rester rapide sur
# les grandes figures d'ilot).
_ECHANTILLON_PAS_PX = 8.0
_ECHANTILLON_MAX_PAR_SEGMENT = 16

# Priorites de resolution (plus haut = plus important / plus immobile).
_PRIO_COMPOSANT = 0
_PRIO_NET = 1
_PRIO_IMMOBILE = 2


def _est_nom_de_net(texte):
    """@brief Heuristique simple : un nom de net (VIN, VOUT, VCC, GND, NOUT...)
    s'ecrit tout en majuscules.

    Limitation connue et assumee (heuristique documentee, cf. design) : une
    reference de composant sans minuscule (ex. "R1") est logee au meme rang
    -- sans consequence sur la garantie principale (les deux textes sont de
    toute facon separes par la resolution si collision il y a), seul l'ORDRE
    de resolution en patit dans ce cas de figure.
    """
    s = texte.strip()
    if not s or not any(c.isalpha() for c in s):
        return False
    return s.upper() == s


def _texte_significatif(t):
    return t.get_visible() and bool(t.get_text().strip())


def _classer(t, ax):
    """@brief (priorite, mobile) pour un objet Text donne."""
    if ax is not None and (t is ax.title or t is ax.xaxis.label or t is ax.yaxis.label):
        return _PRIO_IMMOBILE, False
    if _est_nom_de_net(t.get_text()):
        return _PRIO_NET, True
    return _PRIO_COMPOSANT, True


def _collecter_entrees(fig):
    """@brief Liste des Text visibles/non vides de la figure, avec priorite."""
    entrees = []
    for ax in fig.axes:
        titre = ax.title
        if _texte_significatif(titre):
            entrees.append({"text": titre, "priority": _PRIO_IMMOBILE, "movable": False})
        for lbl in (ax.xaxis.label, ax.yaxis.label):
            if _texte_significatif(lbl):
                entrees.append({"text": lbl, "priority": _PRIO_IMMOBILE, "movable": False})
        for t in ax.texts:
            if not _texte_significatif(t):
                continue
            prio, mobile = _classer(t, ax)
            entrees.append({"text": t, "priority": prio, "movable": mobile})
    suptitle = getattr(fig, "_suptitle", None)
    if suptitle is not None and _texte_significatif(suptitle):
        entrees.append({"text": suptitle, "priority": _PRIO_IMMOBILE, "movable": False})
    for t in fig.texts:
        if not _texte_significatif(t):
            continue
        prio, mobile = _classer(t, None)
        entrees.append({"text": t, "priority": prio, "movable": mobile})
    return entrees


def _echantillonner_ligne(ax, line):
    """@brief Points (coordonnees display) echantillonnes le long d'un Line2D."""
    xy = line.get_xydata()
    if xy is None or len(xy) == 0:
        return []
    disp = ax.transData.transform(xy)
    finite = [(x, y) for x, y in disp if math.isfinite(x) and math.isfinite(y)]
    if len(finite) == 1:
        return [finite[0]]
    pts = []
    for (x0, y0), (x1, y1) in zip(finite[:-1], finite[1:]):
        seg_len = math.hypot(x1 - x0, y1 - y0)
        n = max(1, min(_ECHANTILLON_MAX_PAR_SEGMENT, int(seg_len // _ECHANTILLON_PAS_PX)))
        for k in range(n + 1):
            frac = k / n
            pts.append((x0 + (x1 - x0) * frac, y0 + (y1 - y0) * frac))
    return pts


def _collecter_points_lignes(fig):
    points = []
    for ax in fig.axes:
        for line in ax.lines:
            points.extend(_echantillonner_ligne(ax, line))
    return points


def _sort_key(entry):
    bbox = entry["_bbox0"]
    return (round(bbox.x0), round(bbox.y0), entry["text"].get_text())


def _push_bbox_vs_bbox(bbox_t, bbox_o, marge):
    """@brief (amount, dx, dy) pour separer bbox_t de bbox_o (bbox_t bouge).

    None si les deux bboxes ne se chevauchent pas. `amount` sert a comparer
    plusieurs collisions candidates (la plus severe est resolue en premier).
    """
    overlap_x = min(bbox_t.x1, bbox_o.x1) - max(bbox_t.x0, bbox_o.x0)
    overlap_y = min(bbox_t.y1, bbox_o.y1) - max(bbox_t.y0, bbox_o.y0)
    if overlap_x <= 0 or overlap_y <= 0:
        return None
    cxt, cxo = (bbox_t.x0 + bbox_t.x1) / 2, (bbox_o.x0 + bbox_o.x1) / 2
    cyt, cyo = (bbox_t.y0 + bbox_t.y1) / 2, (bbox_o.y0 + bbox_o.y1) / 2
    if overlap_x <= overlap_y:
        amount = overlap_x + marge
        dx = amount if cxt >= cxo else -amount
        return amount, dx, 0.0
    amount = overlap_y + marge
    dy = amount if cyt >= cyo else -amount
    return amount, 0.0, dy


def _push_bbox_vs_point(bbox_t, px, py, marge):
    """@brief (amount, dx, dy) pour extraire bbox_t d'un point de fil px,py.

    None si le point n'est pas a l'interieur de bbox_t. Pousse vers le bord
    le plus proche (deplacement minimal) le long de l'axe qui demande le
    moins de mouvement.
    """
    if not (bbox_t.x0 <= px <= bbox_t.x1 and bbox_t.y0 <= py <= bbox_t.y1):
        return None
    dl, dr = px - bbox_t.x0, bbox_t.x1 - px
    db, dt = py - bbox_t.y0, bbox_t.y1 - py
    push_x, push_y = min(dl, dr) + marge, min(db, dt) + marge
    if push_x <= push_y:
        dx = push_x if dl <= dr else -push_x
        return push_x, dx, 0.0
    dy = push_y if db <= dt else -push_y
    return push_y, 0.0, dy


def _deplacer(text, dx, dy):
    """@brief Translate un Text de (dx,dy) PIXELS, quel que soit son repere
    (data, axes, figure) : ancre -> display, translation, retour au repere
    d'origine. No-op si (dx,dy) == (0,0)."""
    if dx == 0.0 and dy == 0.0:
        return
    transform = text.get_transform()
    x, y = text.get_position()
    dispx, dispy = transform.transform((x, y))
    nx, ny = transform.inverted().transform((dispx + dx, dispy + dy))
    text.set_position((nx, ny))


_REEXTEND_MAX_ITER = 20
_REEXTEND_TOL = 1e-9


def _reetendre_axes(fig, entrees, renderer):
    """@brief Etend xlim/ylim de chaque ax pour contenir toutes ses bboxes de
    texte (aucun label clippe, quel que soit le zoom, cf. design section 1).

    Boucle bornee (`_REEXTEND_MAX_ITER`) : deux effets de bord mesures
    empiriquement rendent ceci un point fixe a resoudre iterativement, pas un
    calcul direct :
      1. un `Text` ancre en coordonnees DONNEES voit sa position PIXEL
         changer des qu'on appelle `ax.set_xlim` (transData recalcule),
         alors que sa taille de police (en points) ne change pas -- englober
         sa bbox COURANTE peut donc laisser une bbox legerement hors cadre
         une fois le nouveau transData applique ;
      2. `ax.set_aspect("equal")` (adjustable="box", le defaut, utilise par
         tous les appelants) ne recalcule la BOITE des axes qu'au prochain
         `apply_aspect()` -- implicitement lors du prochain rendu complet.
         Sans l'appeler explicitement ici, la boite utilisee pour nos
         mesures reste celle d'AVANT la derniere extension, et le rendu
         final (un futur canvas.draw()) la retrecit pour rester carree avec
         le nouveau xlim/ylim, recreant le chevauchement qu'on vient de
         resoudre.
    Reboucler jusqu'a stabilisation (tolerance `_REEXTEND_TOL`, sinon la
    borne d'iterations) fait converger ce point fixe (la correction requise
    retrecit geometriquement a chaque iteration)."""
    for ax in fig.axes:
        textes = [e["text"] for e in entrees
                  if getattr(e["text"], "axes", None) is ax
                  and e["text"].get_text().strip()]
        if not textes:
            continue
        for _ in range(_REEXTEND_MAX_ITER):
            bboxes = [t.get_window_extent(renderer) for t in textes]
            disp_x0 = min(b.x0 for b in bboxes)
            disp_y0 = min(b.y0 for b in bboxes)
            disp_x1 = max(b.x1 for b in bboxes)
            disp_y1 = max(b.y1 for b in bboxes)
            inv = ax.transData.inverted()
            dxa, dya = inv.transform((disp_x0, disp_y0))
            dxb, dyb = inv.transform((disp_x1, disp_y1))
            data_x0, data_x1 = min(dxa, dxb), max(dxa, dxb)
            data_y0, data_y1 = min(dya, dyb), max(dya, dyb)
            x0, x1 = ax.get_xlim()
            y0, y1 = ax.get_ylim()
            nx0, nx1 = min(x0, data_x0), max(x1, data_x1)
            ny0, ny1 = min(y0, data_y0), max(y1, data_y1)
            echelle = max(abs(x1 - x0), abs(y1 - y0), 1e-9)
            converge = (abs(nx0 - x0) < _REEXTEND_TOL * echelle
                        and abs(nx1 - x1) < _REEXTEND_TOL * echelle
                        and abs(ny0 - y0) < _REEXTEND_TOL * echelle
                        and abs(ny1 - y1) < _REEXTEND_TOL * echelle)
            # set_xlim/set_ylim sont appeles INCONDITIONNELLEMENT (meme si
            # les bornes calculees sont identiques aux bornes courantes) :
            # l'appel desactive l'autoscale de l'axe (auto=False par
            # defaut), ce qui est necessaire pour empecher un
            # ax.margins()/tight_layout() APPELE PLUS TARD par l'appelant de
            # re-deriver xlim/ylim depuis dataLim seul (Line2D/Patch) et de
            # re-couper le texte -- exactement le bug que ce module corrige
            # (cf. commentaire historique de circuit_viewer._make_fig sur
            # l'autoscale qui ignore les Text).
            ax.set_xlim(nx0, nx1)
            ax.set_ylim(ny0, ny1)
            # cf. point 2 de la docstring : force la boite "equal aspect" a
            # se remettre a jour MAINTENANT (pas au prochain rendu), pour que
            # get_window_extent() a la prochaine iteration (ou chez
            # l'appelant) reflete la geometrie FINALE, pas une geometrie
            # perimee qui va encore bouger.
            ax.apply_aspect()
            if converge:
                break


def ajuster_labels(fig):
    """@brief Passe de resolution anti-collision (cf. docstring du module).

    No-op strict si aucune collision n'est detectee (stabilite visuelle,
    cf. design section 1) : ni deplacement de texte, ni extension d'axe si
    tout est deja contenu dans le cadre courant.
    """
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()

    entrees = _collecter_entrees(fig)
    if not entrees:
        return
    points_lignes = _collecter_points_lignes(fig)
    marge = _MARGE_POINTS * fig.dpi / 72.0

    for e in entrees:
        e["_bbox0"] = e["text"].get_window_extent(renderer)
    ordre = sorted(range(len(entrees)), key=lambda i: _sort_key(entrees[i]))
    rang = {idx: pos for pos, idx in enumerate(ordre)}

    for _ in range(_MAX_ITER):
        bboxes = [e["text"].get_window_extent(renderer) for e in entrees]
        collision = False
        for idx in ordre:
            e = entrees[idx]
            if not e["movable"]:
                continue
            bbox_t = bboxes[idx]
            pire = None
            for jdx in ordre:
                if jdx == idx:
                    continue
                autre = entrees[jdx]
                doit_bouger = e["priority"] < autre["priority"] or (
                    e["priority"] == autre["priority"] and rang[idx] > rang[jdx])
                if not doit_bouger:
                    continue
                cand = _push_bbox_vs_bbox(bbox_t, bboxes[jdx], marge)
                if cand and (pire is None or cand[0] > pire[0]):
                    pire = cand
            for (px, py) in points_lignes:
                cand = _push_bbox_vs_point(bbox_t, px, py, marge)
                if cand and (pire is None or cand[0] > pire[0]):
                    pire = cand
            if pire is not None:
                _deplacer(e["text"], pire[1], pire[2])
                bboxes[idx] = e["text"].get_window_extent(renderer)
                collision = True
        if not collision:
            break
    else:
        _log.debug("ajuster_labels: iterations epuisees sans convergence complete")

    _reetendre_axes(fig, entrees, renderer)
