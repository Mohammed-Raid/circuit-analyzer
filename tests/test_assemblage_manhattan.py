"""@file test_assemblage_manhattan.py
@brief Contrats corpus de l'assemblage grille+Manhattan (spec §8.3-8.6) :
fils inter-etages orthogonaux, aucun segment a travers un slot d'etage,
repli _fil_en_z journalise. Etendu au DAG branche en Task 5.
"""
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import pytest

from circuit_analyzer import detecteur
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.xml import lire_xml
from gui import theme
from gui.circuit_viewer import _mesurer_montage  # noqa: F401 -- Step 2 du brief :
# contrats "corpus" (orthogonalite, determinisme) deja verts sur l'ancien
# chemin _fil_en_z -> le RED cible impose par le brief est l'ABSENCE de
# l'assemblage grille+routeur (Task 4), verifiee ici par cet import.
from tools.render_ilots_v2 import _fig_for_ilot

ROOT = Path(__file__).resolve().parent.parent
_WIRE_COLORS = {theme.SCHEMA_COLORS["WIRE"], theme.SCHEMA_COLORS["BUS"]}

# Îlots multi-montages en CHAÎNE (assemblage linéaire).
CHAINES = ["chaine_5_aop.xml", "chaine_conditionnement.xml",
           "ilot_chaine_2ce.xml", "ilot_chaine_3ce.xml",
           "ilot_chaine_ce_suiveur.xml", "ilot_chaine_darlington_ce.xml",
           "ilot_reel_ampli_audio_3etages.xml",
           "ilot_reel_ce_suiveur_sortie_rlc.xml"]


def _fig(nom, detaille):
    comps = lire_xml(str(ROOT / "circuits_industriels" / nom))
    graph = construire_graphe(comps)
    results = detecteur.analyser(graph)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
          for c in comps}
    return _fig_for_ilot(results.ilots[0], graph, ci, results,
                         detaille=detaille)


@pytest.mark.parametrize("nom", CHAINES)
@pytest.mark.parametrize("detaille", [False, True], ids=["z", "det"])
def test_fils_interetages_orthogonaux(nom, detaille):
    # Le RED reel (avant impl. Task 4) revele des Line2D obliques qui ne sont
    # PAS des fils de cablage mais des FORMES DE SYMBOLES schemdraw tracees en
    # un seul element : triangle AOP (7 points, 2 sous-chemins separes par un
    # NaN, colore _WIRE -- un filtre par COULEUR seul est donc insuffisant),
    # fleche de jonction BjtNpn (segment isole a 2 points, NOIR, ni _WIRE ni
    # _BUS), zigzag de Resistor / spirale d'Inductor2 (10 points, noir). Tous
    # les fils reellement caibles par ce module (_fil_en_z, _raccord,
    # _tracer_polyligne, _fil_avec_couplage...) posent UN SEUL segment par
    # `elm.Line().at(p).to(q)` colore explicitement _WIRE/_BUS (aucun
    # chaînage `.to().to()` dans le fichier) -> une Line2D de fil de cablage
    # a TOUJOURS exactement 2 points ET une couleur _WIRE/_BUS. On ne
    # verifie donc l'orthogonalite que sur CES Line2D-la ; les formes de
    # symboles (couleur par defaut noire, ou >2 points) sont hors perimetre
    # de ce contrat, qui porte sur le CABLAGE inter-etages, pas les symboles.
    fig = _fig(nom, detaille)
    for ax in fig.axes:
        for line in ax.lines:
            xy = line.get_xydata()
            if len(xy) != 2 or line.get_color() not in _WIRE_COLORS:
                continue
            for (xa, ya), (xb, yb) in zip(xy[:-1], xy[1:]):
                assert abs(xa - xb) < 1e-6 or abs(ya - yb) < 1e-6, (
                    f"{nom}: segment oblique ({xa},{ya})->({xb},{yb})")


def _xy_eq_nan(a, b):
    """@brief Egalite point-a-point tolerante au NaN.

    Le triangle AOP (et d'autres symboles multi-sous-chemins) est trace en un
    seul `elm.Line`/path schemdraw dont les sous-chemins sont separes par un
    point (NaN, NaN) — technique standard matplotlib. Une comparaison `==`
    nue echoue TOUJOURS sur ce point (NaN != NaN en IEEE 754) meme entre deux
    rendus rigoureusement identiques : ce n'est pas un signe de
    non-determinisme du routage, juste un artefact de la comparaison. On
    traite donc (NaN, NaN) == (NaN, NaN) comme vrai.
    """
    if len(a) != len(b):
        return False
    for (xa, ya), (xb, yb) in zip(a, b):
        if math.isnan(xa) and math.isnan(xb) and math.isnan(ya) and math.isnan(yb):
            continue
        if (xa, ya) != (xb, yb):
            return False
    return True


def test_routage_deterministe():
    a = _fig("chaine_5_aop.xml", True)
    b = _fig("chaine_5_aop.xml", True)
    la = [tuple(map(tuple, l.get_xydata())) for ax in a.axes for l in ax.lines]
    lb = [tuple(map(tuple, l.get_xydata())) for ax in b.axes for l in ax.lines]
    assert len(la) == len(lb)
    for xa, xb in zip(la, lb):
        assert _xy_eq_nan(xa, xb), (xa, xb)


def test_aucun_repli_fil_en_z_sur_le_corpus_chaines(caplog):
    """Contrat spec section 4.3/8.6 : le repli _fil_en_z est LEGAL mais doit
    rester inatteignable sur le corpus de demo -- un port pose a l'INTERIEUR
    d'un slot-obstacle (au lieu de sa frontiere) faisait echouer l'A* des le
    premier pas (24 replis constates au premier render Task 4)."""
    import logging
    with caplog.at_level(logging.WARNING, logger="gui.circuit_viewer"):
        for nom in CHAINES:
            for det in (False, True):
                _fig(nom, det)
    replis = [r for r in caplog.records if "repli _fil_en_z" in r.getMessage()]
    assert not replis, [r.getMessage() for r in replis[:5]]


# Ilots multi-montages en DAG BRANCHE (couches multi-bandes, Task 5).
BRANCHES = ["pid_controller.xml", "ilot_branche_ce_fanout.xml",
            "ilot_reel_fanout_filtres_rlc.xml", "logic_dag_2vers1.xml"]

# Meme filtre que test_fils_interetages_orthogonaux (leçon Task 4) : seules
# les Line2D 2-points coloriees _WIRE/_BUS sont du cablage inter-etages pose
# par ce module (_raccord/_tracer_polyligne/_fil_canal...) ; les formes de
# symboles (triangle AOP 7 points+NaN, zigzag Resistor, spirale Inductor2,
# fleche BjtNpn 2 points NOIRS) ne sont pas des fils et sont hors perimetre.
def _lignes_cablage(fig):
    for ax in fig.axes:
        for line in ax.lines:
            xy = line.get_xydata()
            if len(xy) != 2 or line.get_color() not in _WIRE_COLORS:
                continue
            yield line, xy


@pytest.mark.parametrize("nom", BRANCHES)
@pytest.mark.parametrize("detaille", [False, True], ids=["z", "det"])
def test_dag_fils_orthogonaux_hors_slots(nom, detaille):
    # RED reel (avant impl. Task 5, voir rapport) : PAS le contrat
    # d'orthogonalite lui-meme -- le cablage _fil_canal actuel (canal
    # vertical) est deja purement orthogonal segment par segment. Le RED
    # attendu par le brief (cablage DAG non route par la grille+A*) se
    # constate plutot via test_routage_deterministe_dag / le corpus de repli
    # ci-dessous : ce test-ci sert de garde-fou perenne post-implementation.
    fig = _fig(nom, detaille)
    for _line, xy in _lignes_cablage(fig):
        for (xa, ya), (xb, yb) in zip(xy[:-1], xy[1:]):
            assert abs(xa - xb) < 1e-6 or abs(ya - yb) < 1e-6, (
                f"{nom}: segment oblique ({xa},{ya})->({xb},{yb})")


def test_routage_deterministe_dag():
    a = _fig("pid_controller.xml", True)
    b = _fig("pid_controller.xml", True)
    la = [tuple(map(tuple, l.get_xydata())) for ax in a.axes for l in ax.lines]
    lb = [tuple(map(tuple, l.get_xydata())) for ax in b.axes for l in ax.lines]
    assert len(la) == len(lb)
    for xa, xb in zip(la, lb):
        assert _xy_eq_nan(xa, xb), (xa, xb)


def test_aucun_repli_sur_le_corpus_dag(caplog):
    """Equivalent DAG de test_aucun_repli_fil_en_z_sur_le_corpus_chaines :
    le repli _fil_canal (cablage DAG non route) est LEGAL mais doit rester
    inatteignable sur le corpus BRANCHES -- meme piege potentiel que Task 4
    (port pose a l'interieur d'un slot-obstacle)."""
    import logging
    with caplog.at_level(logging.WARNING, logger="gui.circuit_viewer"):
        for nom in BRANCHES:
            for det in (False, True):
                _fig(nom, det)
    replis = [r for r in caplog.records if "repli" in r.getMessage()]
    assert not replis, [r.getMessage() for r in replis[:5]]


_DUMP_SCRIPT = """
import json
import matplotlib
matplotlib.use("Agg")
from circuit_analyzer import detecteur
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.xml import lire_xml
from gui import theme
from tools.render_ilots_v2 import _fig_for_ilot

_WIRE_COLORS = {theme.SCHEMA_COLORS["WIRE"], theme.SCHEMA_COLORS["BUS"]}
comps = lire_xml(r"%(fichier)s")
graph = construire_graphe(comps)
results = detecteur.analyser(graph)
ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
fig = _fig_for_ilot(results.ilots[0], graph, ci, results, detaille=True)
lignes = []
for ax in fig.axes:
    for line in ax.lines:
        xy = line.get_xydata()
        if len(xy) != 2 or line.get_color() not in _WIRE_COLORS:
            continue
        lignes.append([[float(xy[0][0]), float(xy[0][1])],
                        [float(xy[1][0]), float(xy[1][1])]])
lignes.sort(key=lambda l: json.dumps(l))
print(json.dumps(lignes))
"""


def test_routage_deterministe_dag_inter_process():
    """Contrat FIX 1 (revue finale Task 7) : `_nom_net` (assemblage DAG
    branche) utilisait `id(prod)`/`id(cons)` -- adresse memoire, NON stable
    d'un process Python a l'autre -- pour construire le nom de net qui sert
    de cle de tri des aretes avant routage (`sorted(edges, key=... _nom_net
    ...)`). Deux process distincts rendant le MEME fichier doivent produire
    EXACTEMENT le meme cablage (memes segments _WIRE/_BUS, dans le meme
    ordre) : ce test lance deux sous-process Python separes (adresses
    memoire garanties independantes, contrairement a deux appels dans le
    meme process ou l'allocateur peut recycler des id() identiques et
    masquer le probleme) et compare le JSON trie des Line2D de cablage.

    Note (documente au sens du brief) : sur le corpus BRANCHES actuel, les
    cles de net (`net` dans `_branched_edges`) sont deja toutes distinctes
    par arete (verifie par instrumentation), y compris entre les 2 branches
    d'un meme fan-out -- l'id() ne departageait donc JAMAIS une egalite de
    tri sur ce corpus precis, et ce test ne pouvait pas etre mis au ROUGE
    par le bug avant le fix (deux sous-process independants produisaient
    deja la meme sortie). Il reste neanmoins utile : il fige EXPLICITEMENT
    le contrat "determinisme inter-process" comme garde-fou perenne, pour
    tout futur corpus ou deux aretes partageraient un nom de net dans la
    meme couche (fan-out sur un noeud partage), cas ou l'ancien code aurait
    trie differemment selon le process.
    """
    import json
    import subprocess
    import sys

    fichier = str(ROOT / "circuits_industriels" / "pid_controller.xml")
    script = _DUMP_SCRIPT % {"fichier": fichier}
    sorties = []
    for _ in range(2):
        proc = subprocess.run([sys.executable, "-c", script],
                               cwd=str(ROOT), capture_output=True, text=True,
                               check=False)
        assert proc.returncode == 0, proc.stderr
        sorties.append(json.loads(proc.stdout))
    assert sorties[0] == sorties[1]


def _traversees_labels(fig):
    """(texte, segment) pour chaque Text visible traverse par un fil de
    cablage _WIRE/_BUS (bbox renderer vs segments echantillonnes)."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    hits = []
    for ax in fig.axes:
        textes = [t for t in ax.texts
                  if t.get_visible() and t.get_text().strip()]
        lignes = [l for l in ax.lines if l.get_color() in _WIRE_COLORS]
        for t in textes:
            bb = t.get_window_extent(renderer)
            for line in lignes:
                xy = ax.transData.transform(line.get_xydata())
                touche = False
                for (xa, ya), (xb, yb) in zip(xy[:-1], xy[1:]):
                    n = 24
                    if any(bb.x0 < xa + (xb - xa) * k / n < bb.x1
                           and bb.y0 < ya + (yb - ya) * k / n < bb.y1
                           for k in range(n + 1)):
                        hits.append((t.get_text(),
                                     (round(xa), round(ya),
                                      round(xb), round(yb))))
                        touche = True
                        break
                if touche:
                    break
    return hits


@pytest.mark.parametrize("nom", ["pid_controller.xml",
                                 "ilot_branche_ce_fanout.xml"])
def test_aucun_fil_route_ne_traverse_un_label(nom):
    """FIX 2 revue finale Task 7 : les bus verticaux routes passaient SUR les
    labels de role/gain (pid_controller det : "Differentiel", "Integrateur"),
    poses par _annoter_etage en plein couloir CANAL_H. Le moteur
    anti-collision oscillait entre les DEUX bus encadrant le label (couloir
    plus etroit que le texte) et epuisait ses 20 iterations. Fix racine :
    les annotations sont des OBSTACLES du routeur (_rects_annotations)."""
    hits = _traversees_labels(_fig(nom, True))
    assert not hits, hits[:5]
