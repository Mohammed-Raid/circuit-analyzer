import os, collections, tempfile
import pytest
from circuit_analyzer.xml import lire_xml

_DOSSIER = "CARTE POUR TESTER (VRAI TEST)"
_FICHIERS = ["PG 2.xml", "PG 3.xml", "PowtranAlim20260809.xml", "pg carte.xml"]

pytestmark = pytest.mark.skipif(
    not os.path.isdir(_DOSSIER), reason="cartes reelles absentes")

_TYPES_VALIDES = set("RCLDQMUKFXJ")


@pytest.mark.parametrize("fichier", _FICHIERS)
def test_carte_reelle_reconnaissance_et_types(fichier):
    comps = lire_xml(os.path.join(_DOSSIER, fichier))
    types = collections.Counter(c.type for c in comps)
    # Aucun type invalide (J = connecteur désormais légal).
    assert set(types) <= _TYPES_VALIDES, types
    # Chute franche des inconnus X : au moins la moitié des composants reconnus.
    assert types.get('X', 0) <= len(comps) // 2, dict(types)


def test_toutes_cartes_baisse_globale_des_inconnus():
    total, inconnus, resistances = 0, 0, 0
    for f in _FICHIERS:
        comps = lire_xml(os.path.join(_DOSSIER, f))
        total += len(comps)
        inconnus += sum(1 for c in comps if c.type == 'X')
        resistances += sum(1 for c in comps if c.type == 'R')
    assert inconnus <= 40, f"trop d'inconnus restants : {inconnus}/{total}"
    assert resistances >= 90, f"resistances reconnues : {resistances}"


def _collisions_labels(fig, seuil=0.30):
    """@brief Chevauchements RESIDUELS texte-texte d'une figure d'ilot, mesures
    aux metriques reelles du renderer (get_window_extent), apres ajuster_labels.
    Ignore la legende de bas de figure. Renvoie la liste des paires (a, b)."""
    from gui.schema_labels import obtenir_renderer
    rnd = obtenir_renderer(fig)
    textes = []
    for ax in fig.axes:
        for t in ax.texts:
            s = (t.get_text() or "").strip()
            if not t.get_visible() or not s:
                continue
            if s.startswith("connexion") or s.startswith("cliquez"):
                continue
            textes.append((s, t.get_window_extent(rnd)))

    def aire(b):
        return max(0.0, b.x1 - b.x0) * max(0.0, b.y1 - b.y0)

    def inter(a, b):
        ox = min(a.x1, b.x1) - max(a.x0, b.x0)
        oy = min(a.y1, b.y1) - max(a.y0, b.y0)
        return max(0.0, ox) * max(0.0, oy)

    paires = []
    for i in range(len(textes)):
        for j in range(i + 1, len(textes)):
            it = inter(textes[i][1], textes[j][1])
            if it > 0 and it / (min(aire(textes[i][1]), aire(textes[j][1])) or 1.0) > seuil:
                paires.append((textes[i][0], textes[j][0]))
    return paires


def test_cartes_reelles_ilots_sans_chevauchement_de_labels():
    """@brief Aucun ilot des 4 cartes reelles ne doit garder de chevauchement
    d'etiquettes apres l'anti-collision (defaut boite connecteur multi-broches)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from circuit_analyzer.composant import construire_graphe
    from circuit_analyzer import detecteur
    from tools import render_ilots_v2 as R

    residuels = []
    for f in _FICHIERS:
        comps = lire_xml(os.path.join(_DOSSIER, f))
        g = construire_graphe(comps)
        res = detecteur.analyser(g)
        ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
        for idx, il in enumerate(res.ilots):
            fig = R._fig_for_ilot(il, g, ci, res, detaille=False)
            cols = _collisions_labels(fig)
            plt.close(fig)
            if cols:
                residuels.append((f, idx, cols))
    assert not residuels, f"chevauchements residuels d'etiquettes : {residuels}"


def test_aller_retour_des_vraies_cartes_ne_perd_ni_composant_ni_liaison():
    """Contrat « les deux applis travaillent ensemble » : relire une vraie
    carte puis la RE-EXPORTER doit rendre le meme circuit.

    A l'origine, 9 des 23 composants de PG 2 disparaissaient (les connecteurs
    type J n'avaient aucune forme -> `if spec is None: continue`), et les
    broches au nom hors plan (D1 en '-'/'+') perdaient leurs liaisons.
    """
    from circuit_analyzer.xml import generer_xml

    def partition(comps):
        # signature INDEPENDANTE des refs : les connecteurs reexportes en
        # boitier PuceN se relisent en 'U' avec une autre ref, sans que la
        # connexite change.
        nets = {}
        for c in comps:
            for n in c.pins.values():
                nets.setdefault(n, []).append(c.value or c.type)
        return sorted(tuple(sorted(v)) for v in nets.values() if len(v) > 1)

    for nom in _FICHIERS:
        avant = lire_xml(os.path.join(_DOSSIER, nom))
        f = tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False,
                                        encoding="utf-8")
        f.write(generer_xml(avant))
        f.close()
        try:
            apres = lire_xml(f.name)
        finally:
            os.unlink(f.name)
        assert len(apres) >= len(avant), (
            f"{nom} : {len(avant)} -> {len(apres)} composants (perte)")
        assert partition(avant) == partition(apres), f"{nom} : connexite alteree"
