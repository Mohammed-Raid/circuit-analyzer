"""@file test_puces_resolution.py
@brief Contrat : chaque puce composant d'un ilot doit resoudre une position
(clic -> zoom-focus + anneau) dans les deux vues (Z / detaillee).

Garde-fou anti-regression pour le registre `fig._comp_positions` (cf.
`gui.circuit_viewer._enregistrer_position`) : avant son introduction, 216/344
verifications echouaient (transistors/AOP dont le titre du montage n'affiche
qu'un role -- jamais leur ref -- et satellites R/L/C dessines en symbole reel
avec une etiquette de role comme « Rb = 10 kΩ »). Reprend la logique du script
d'audit ayant servi a diagnostiquer le bug : pour chaque circuit du corpus,
chaque ilot, chaque composant du modele (`_build_island_model`) et chaque mode
(Z / detaille), au moins une des refs candidates (les refs brutes du composant
+ sa ref synthetique, ex. Z3) doit resoudre une position dans la figure rendue.
"""
import glob
import os

import pytest

from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser
from circuit_analyzer.xml import lire_xml
from gui import circuit_viewer as cv
from tools import render_ilots_v2 as rv

_CORPUS = sorted(
    glob.glob("circuits_industriels/ilot_*.xml")
    + glob.glob("circuits_industriels/tr_*.xml")
    + glob.glob("circuits_industriels/aop_*.xml")
    # Portes CMOS -- logic_non_dual est EXCLU des contrats visuels (fichier
    # de rejet : ilot de MOSFET non matches, reserve aux tests unitaires).
    + [f for f in glob.glob("circuits_industriels/logic_*.xml")
       if "non_dual" not in f]
    + glob.glob("circuits_industriels/reel_*.xml")
)

## @brief Exclusions EXPLICITES : composant reellement absent du dessin dans
## cette vue (pas un defaut du registre de positions) -- chaque entree
## documente la raison. Cle = (fichier, ref du composant dans le modele).
##
## Racine commune aux 6 entrees : polarisation par pont diviseur de base
## (2 resistances vers la base d'un CE -- l'une vers l'alim, l'autre vers la
## masse). `_draw_common_emitter`/`_ref_on_net` n'en choisit qu'UNE comme
## « Rb » ; l'autre (ou la combinaison R//R quand `impedance.reduire` les
## fusionne en un seul Z, cf. Z3 de l'ampli 3 etages) n'est tracee nulle part
## dans le schema -- ni boite Z, ni symbole reel, ni texte. Corriger
## `_draw_common_emitter` pour dessiner le pont complet deborderait du
## perimetre de cette tache (registre de positions, aucun changement visuel,
## cf. directive du boss de ne pas gold-plater les reseaux passifs exotiques).
_EXCLUSIONS = {
    ("ilot_reel_2ce_bias_rlc.xml", "Z2"):
        "pont diviseur de base Q1 : 2e resistance (R2, base->GND) non dessinee",
    ("ilot_reel_2ce_bias_rlc.xml", "Z8"):
        "pont diviseur de base Q2 : 2e resistance (R7, base->GND) non dessinee",
    ("ilot_reel_ampli_audio_3etages.xml", "Z3"):
        "pont diviseur de base Q1 : R1//R3 (base->GND, fusionnes par reduire) non dessines",
    ("ilot_reel_ampli_audio_3etages.xml", "Z11"):
        "pont diviseur de base Q2 : 2e resistance (R7, base->GND) non dessinee",
    ("ilot_reel_ce_suiveur_sortie_rlc.xml", "Z2"):
        "pont diviseur de base Q1 : 2e resistance (R3, base->GND) non dessinee",
    ("ilot_reel_fanout_filtres_rlc.xml", "Z2"):
        "pont diviseur de base Q1 : 2e resistance (R2, base->GND) non dessinee",
    # Diode de roue libre non absorbee par aucun match detecte (le darlington
    # pilote directement l'inductance de charge L1 ; D1 n'appartient ni aux
    # composants du montage, ni a un couplage Impedance Z) -> jamais tracee.
    ("ilot_reel_darlington_relais_rlc.xml", "D1"):
        "diode de roue libre hors montage/couplage detecte : jamais dessinee",
}


def _cas_ilots():
    """@brief Genere (fichier, index ilot, ref, candidats, mode_detaille)."""
    cas = []
    for fx in _CORPUS:
        base = os.path.basename(fx)
        comps = lire_xml(fx)
        g = construire_graphe(comps)
        res = analyser(g)
        ci = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}
        for k, ilot in enumerate(res.ilots):
            model = cv._build_island_model(ilot, g, ci)
            figs = {
                detaille: rv._fig_for_ilot(ilot, g, ci, res, detaille=detaille)
                for detaille in (False, True)
            }
            for comp in model["components"]:
                ref = comp["ref"]
                candidats = tuple(dict.fromkeys([*(comp.get("refs") or ()), ref]))
                for detaille, fig in figs.items():
                    cas.append((base, k, ref, candidats, detaille, fig))
    return cas


def _id_cas(cas):
    base, k, ref, _candidats, detaille = cas
    return f"{base}[{k}]:{ref}:{'detaille' if detaille else 'Z'}"


_CAS = _cas_ilots()
_PARAMS = [
    pytest.param(base, k, ref, candidats, detaille, fig,
                 id=_id_cas((base, k, ref, candidats, detaille)))
    for base, k, ref, candidats, detaille, fig in _CAS
]


@pytest.mark.parametrize("base,k,ref,candidats,detaille,fig", _PARAMS)
def test_puce_composant_resout_une_position(base, k, ref, candidats, detaille, fig):
    """Chaque puce « Composants : ... » doit pouvoir centrer la vue + poser
    l'anneau de surbrillance -- cf. `cv._position_composant`."""
    if (base, ref) in _EXCLUSIONS:
        pytest.skip(_EXCLUSIONS[(base, ref)])
    ok = any(cv._position_composant(fig, r) is not None for r in candidats)
    assert ok, (
        f"aucune position resolue pour {ref} (candidats={candidats}) "
        f"dans {base} ilot={k} mode={'detaille' if detaille else 'Z'}"
    )


def test_exclusions_toujours_necessaires():
    """Garde-fou inverse : si une exclusion resout desormais une position
    (regression du perimetre, ou fix ulterieur du dessin), l'entree doit etre
    retiree de `_EXCLUSIONS` plutot que de rester une exclusion morte."""
    resolues = set()
    for base, _k, ref, candidats, _detaille, fig in _CAS:
        if (base, ref) in _EXCLUSIONS and any(
                cv._position_composant(fig, r) is not None for r in candidats):
            resolues.add((base, ref))
    assert not resolues, f"exclusions devenues inutiles (a retirer) : {sorted(resolues)}"
