"""@file test_demos_aop.py
@brief Démos industrielles réalistes : chaque netlist .txt doit faire détecter
son montage AOP attendu (cf. docs/superpowers/specs/2026-06-25-demos-aop-restants-design.md)."""
import pytest

from circuit_analyzer.composant import lire_netlist, construire_graphe
from circuit_analyzer.detecteur import analyser

# (netlist simulations/*.txt, circuit_type attendu)
DEMOS = [
    ("ampli_shunt_inverseur.txt",       "Amplificateur inverseur (AOP)"),
    ("ampli_capteur_non_inverseur.txt", "Amplificateur non-inverseur (AOP)"),
    ("integrateur_consigne.txt",        "Intégrateur (AOP)"),
    ("derivateur_choc.txt",             "Dérivateur (AOP)"),
    ("sommateur_offset.txt",            "Amplificateur sommateur (AOP)"),
    ("ampli_diff_shunt.txt",            "Amplificateur différentiel (AOP)"),
    ("buffer_reference.txt",            "Suiveur de tension (AOP)"),
]


@pytest.mark.parametrize("fichier, attendu", DEMOS)
def test_demo_detecte_le_bon_montage(fichier, attendu):
    comps = lire_netlist(f"simulations/{fichier}")
    detectes = [r["circuit_type"] for r in analyser(construire_graphe(comps))]
    assert attendu in detectes, f"{fichier}: attendu '{attendu}', obtenu {detectes}"
