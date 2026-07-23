"""@file test_resume_executif.py
@brief Le résumé exécutif de l'onglet Analyser doit décrire la carte HONNÊTEMENT.

Défaut trouvé en répétition de démo (2026-07-23) : sur une vraie carte
(31 « Impédance Z » + 3 « Amplificateur émetteur commun »), le résumé annonçait
« principalement des fonctions annexes » — faux, et contraire à la règle
« jamais de vue générique fausse ». L'analyseur calcule pourtant déjà
`functional_category` correctement ; le résumé le re-devinait depuis le nom.
"""
from gui.tab_analyze import _format_category_list


def test_impedances_ne_sont_pas_des_fonctions_annexes():
    res = [{"circuit_type": "Impédance Z", "functional_category": "impedance"}]
    texte = _format_category_list(res)
    assert "annexe" not in texte
    assert "impédance" in texte.lower()


def test_amplificateur_a_transistor_est_de_l_amplification():
    res = [{"circuit_type": "Amplificateur émetteur commun",
            "functional_category": "amplification"}]
    assert _format_category_list(res) == "de l'amplification"


def test_carte_reelle_melange_impedances_et_amplis():
    res = ([{"circuit_type": "Impédance Z",
             "functional_category": "impedance"}] * 31 +
           [{"circuit_type": "Amplificateur émetteur commun",
             "functional_category": "amplification"}] * 3)
    texte = _format_category_list(res)
    assert "annexe" not in texte
    assert "impédance" in texte.lower() and "amplification" in texte


def test_toutes_les_categories_ont_un_libelle():
    """Aucune catégorie de l'analyseur ne doit tomber dans le fourre-tout."""
    from circuit_analyzer.detecteur import _CATEGORIES
    for cat in set(_CATEGORIES.values()):
        texte = _format_category_list([{"circuit_type": "X",
                                        "functional_category": cat}])
        assert "annexe" not in texte, f"{cat} -> {texte}"


def test_categorie_absente_retombe_sur_le_nom():
    """Rétro-compatibilité : sans `functional_category`, on garde le nom."""
    res = [{"circuit_type": "Filtre RC passe-bas"}]
    assert _format_category_list(res) == "du filtrage"
