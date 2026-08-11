"""@file test_pattern_wizard.py
@brief PatternWizard : apercu schematique de l'etape 4, rejet des doublons
de nom (spec 2026-08-04). Tk -> skip sans display.
"""
import pytest

ctk = pytest.importorskip("customtkinter")


@pytest.fixture
def ctk_root():
    import tkinter as tk
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("pas d'affichage Tk disponible")
    root.withdraw()
    yield root
    root.destroy()


def _wizard(ctk_root, refs_info):
    """@brief Construit un PatternWizard avec des composants deja coches.

    @param refs_info dict {ref: {"type":..., "value":..., "pins": {...}}}
    """
    from gui.pattern_wizard import PatternWizard
    return PatternWizard(ctk_root, graph=None,
                         unclassified=list(refs_info), comp_info=refs_info)


def test_apercu_dessine_un_symbole_par_composant_selectionne(ctk_root):
    refs_info = {
        "R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N2"}},
        "C1": {"type": "C", "value": "100n", "pins": {"1": "N2", "2": "GND"}},
    }
    w = _wizard(ctk_root, refs_info)
    fig = w._dessiner_apercu()
    with_elements = [el for ax in fig.axes for el in ax.texts]
    textes = {t.get_text() for t in with_elements}
    assert "R1" in textes and "C1" in textes


def test_apercu_relie_deux_composants_qui_partagent_un_net(ctk_root):
    refs_info = {
        "R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N2"}},
        "C1": {"type": "C", "value": "100n", "pins": {"1": "N2", "2": "GND"}},
    }
    w = _wizard(ctk_root, refs_info)
    fig = w._dessiner_apercu()
    assert set(fig._apercu_connexions) == {("R1", "C1")}


def test_apercu_dessine_un_composant_isole_sans_fil(ctk_root):
    """Aucun net partage entre R1 et C1 -> composants dessines, aucun fil."""
    refs_info = {
        "R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N2"}},
        "C1": {"type": "C", "value": "100n", "pins": {"1": "N3", "2": "N4"}},
    }
    w = _wizard(ctk_root, refs_info)
    fig = w._dessiner_apercu()
    textes = {t.get_text() for ax in fig.axes for t in ax.texts}
    assert "R1" in textes and "C1" in textes
    assert fig._apercu_connexions == [], "aucun net partage : pas de fil attendu"


def test_apercu_sans_selection_ne_leve_pas(ctk_root):
    w = _wizard(ctk_root, {})
    fig = w._dessiner_apercu()
    assert fig is not None


def test_go_to_etape_4_affiche_l_apercu(ctk_root):
    """La navigation vers l'etape 4 declenche bien le rendu (pas seulement
    un appel manuel isole a _dessiner_apercu)."""
    refs_info = {"R1": {"type": "R", "value": "10k",
                        "pins": {"1": "N1", "2": "N2"}}}
    w = _wizard(ctk_root, refs_info)
    w._go_to(2)
    w._name_var.set("Mon pattern")
    w._go_to(4)
    assert w._apercu_canvas is not None


def test_doublon_de_nom_refuse_a_l_etape_2(ctk_root, monkeypatch, tmp_path):
    """Remplace test_doublon_pattern_refuse (testait TabCircuits, retire) :
    meme comportement reel, teste directement sur PatternWizard, le seul
    chemin de creation qui subsiste apres le retrait de l'onglet Circuits."""
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)
    loader.save_custom_circuits([{"name": "Mon montage", "components": ["R"],
                                  "conditions": []}])

    refs_info = {"R1": {"type": "R", "value": "10k",
                        "pins": {"1": "N1", "2": "N2"}}}
    w = _wizard(ctk_root, refs_info)
    w._go_to(2)
    w._name_var.set("Mon montage")
    assert w._validate_current() is False


def test_doublon_de_nom_avec_un_circuit_integre_refuse_a_l_etape_2(
        ctk_root, monkeypatch, tmp_path):
    """Fix 5-1 : la validation doit aussi rejeter un nom qui collide avec un
    circuit INTEGRE (NOMS_CIRCUITS), pas seulement avec les personnalises.
    Sinon circuit_viewer decide "personnalise" par NOM : un pattern nomme
    comme un circuit integre ferait apparaitre un bouton Supprimer sur ce
    circuit integre, qui supprimerait en realite l'entree personnalisee
    homonyme."""
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)
    loader.save_custom_circuits([])

    refs_info = {"R1": {"type": "R", "value": "10k",
                        "pins": {"1": "N1", "2": "N2"}}}
    w = _wizard(ctk_root, refs_info)
    w._go_to(2)
    w._name_var.set("Suiveur de tension (AOP)")
    assert w._validate_current() is False


def test_apercu_rend_diode_sans_lever(ctk_root):
    """Fumee : l'apercu ne doit pas lever pour un composant D et affiche bien
    sa reference. Le VRAI test de non-regression (le symbole rendu est
    elm.Diode, pas une resistance) vit dans test_impedance_schematic.py
    (test_style_symbole_diode_rend_elm_diode) : style_symbole() est la
    fonction partagee que le wizard appelle pour choisir la classe schemdraw,
    donc c'est la qu'on verifie la classe reellement retournee."""
    refs_info = {
        "D1": {"type": "D", "value": "1N4007", "pins": {"1": "N1", "2": "GND"}},
    }
    w = _wizard(ctk_root, refs_info)
    fig = w._dessiner_apercu()
    textes = {t.get_text() for ax in fig.axes for t in ax.texts}
    assert "D1" in textes, "La diode doit avoir sa reference affichee"


def test_apercu_trois_composants_sur_un_net_font_une_chaine_pas_clique(ctk_root):
    """Fix 2: Trois composants partageant un net ne doivent pas creer une
    clique (3 connexions : R1-C1, R1-R2, C1-R2) mais une chaine
    (2 connexions : R1-C1, C1-R2). Cela evite que les fils ne traversent
    les composants intermediaires."""
    refs_info = {
        "R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "GND"}},
        "C1": {"type": "C", "value": "100n", "pins": {"1": "N2", "2": "GND"}},
        "R2": {"type": "R", "value": "1k", "pins": {"1": "N3", "2": "GND"}},
    }
    w = _wizard(ctk_root, refs_info)
    fig = w._dessiner_apercu()
    # Verifier une chaine (2 connexions) pas une clique (3 connexions)
    connexions = fig._apercu_connexions
    # Doit avoir exactement 2 connexions (chaine) et non 3 (clique)
    assert len(connexions) == 2, \
        f"Expected chain (2 connections) but got {len(connexions)}: {connexions}"
