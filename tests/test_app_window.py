"""@file test_app_window.py
@brief Contrat de la fenetre principale : 4 onglets (Analyser, Schema,
       Composants, Circuits), l'editeur remplace Saisie.

[MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (demande utilisateur : « add a
posibilite to see all the schema existed in the app and be able to edit or
dealte one ») : l'onglet Circuits avait ete retire (2026-08-04, cf.
docs/superpowers/plans/2026-08-04-retrait-onglet-circuits-apercu-wizard.md)
au profit du bouton Supprimer de la popup schema + de l'apercu du wizard --
mais ca supprimait aussi la seule facon de PARCOURIR tous les patterns
personnalises existants (on ne tombe sur un pattern que s'il matche quelque
chose). Rebranche (gui/app_window.py) : TabCircuits corrige au passage pour
ne plus planter sur un pattern avance (nom verrouille / condition generique,
cf. gui/tab_circuits.py::_est_avance) -- affiche en lecture seule,
supprimable, comme demande.
"""
import pytest

ctk = pytest.importorskip("customtkinter")

from gui.app_window import AppWindow


def test_quatre_onglets_sans_saisie_avec_circuits():
    try:
        app = AppWindow()
    except Exception:
        pytest.skip("pas de display Tk")
    try:
        assert len(app._frames) == 4
        labels = [button._lbl.cget("text") for button in app._nav_btns]
        assert "Saisie" not in labels
        assert "Circuits" in labels
    finally:
        app.root.destroy()
