"""Contrat typographique des labels satellites (Rb/Rc/Re/Rg... = valeur).

Un satellite est une impedance de role dessinee en symbole reel autour d'un
montage transistor (« Rb = 10 kΩ »). Trois tailles coexistaient (14 heritee du
d.config global via `_r_simple`, 8 et 9 explicites selon le drawer) : le meme
role visuel doit avoir UNE taille -- `cv._SATELLITE_LABEL_FONTSIZE`.
"""
import pytest

from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser
from circuit_analyzer.xml import lire_xml
from gui import circuit_viewer as cv
from tools import render_ilots_v2 as rv

# Couvre les trois familles historiques : _r_simple sans fontsize (heritait
# 14 : darlington Rb, mosfet Rg), fontsize=8 (cascade CE Rb/Rc) et
# fontsize=9 (push-pull/CE Re).
_CIRCUITS = [
    "circuits_industriels/ilot_reel_darlington_relais_rlc.xml",
    "circuits_industriels/tr_mosfet_commutation.xml",
    "circuits_industriels/tr_emetteur_commun.xml",
    "circuits_industriels/tr_suiveur_emetteur.xml",
]

_ROLES = ("Rb", "Rc", "Re", "Rg", "Rd", "Rs")


def _labels_satellites(fig):
    for ax in fig.axes:
        for t in ax.texts:
            texte = t.get_text()
            if texte.startswith(_ROLES) and "=" in texte:
                yield t


@pytest.mark.parametrize("chemin", _CIRCUITS)
def test_labels_satellites_taille_unique(chemin):
    comps = lire_xml(chemin)
    g = construire_graphe(comps)
    res = analyser(g)
    ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
          for c in comps}
    trouves = 0
    for ilot in res.ilots:
        for detaille in (False, True):
            fig = rv._fig_for_ilot(ilot, g, ci, res, detaille=detaille)
            for t in _labels_satellites(fig):
                trouves += 1
                assert t.get_fontsize() == cv._SATELLITE_LABEL_FONTSIZE, (
                    f"{chemin} detaille={detaille} : label satellite "
                    f"{t.get_text()!r} en taille {t.get_fontsize()}")
    assert trouves > 0, f"{chemin} : aucun label satellite trouve"
