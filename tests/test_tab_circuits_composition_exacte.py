"""@file test_tab_circuits_composition_exacte.py
@brief TabCircuits._est_avance/_resume_avance face à "composition_exacte"
(demande utilisateur 2026-08-19, cf. custom_circuits/loader.py).

[MODIF 2026-08-19] BUG TROUVÉ EN TESTANT : `composition_exacte` est une clé
de NIVEAU PATTERN (pas dans "components"/"conditions"), donc invisible aux
deux `any(isinstance(x, dict) ...)` de `_est_avance` -- un pattern par
ailleurs "simple" (aucun composant/condition en dict) mais avec
`composition_exacte: true` passait en mode 'edition' (cases à cocher), dont
`_sauvegarder` reconstruit `c = {"name", "components", "conditions"}` FROM
SCRATCH -> la clé était silencieusement perdue au premier "Enregistrer"
depuis cet onglet. `_est_avance`/`_resume_avance` ne touchent pas de widget
Tk (juste le dict passé en argument) -- testables sans fenêtre réelle via
`__new__` (bypass `__init__`, qui construit les frames ctk).
"""
from gui.tab_circuits import TabCircuits


def _tab() -> TabCircuits:
    return TabCircuits.__new__(TabCircuits)


def test_composition_exacte_seule_rend_le_pattern_avance():
    """Un pattern SANS aucun composant/condition en dict, mais avec
    composition_exacte=True, doit quand même être détecté "avancé" (lecture
    seule) -- sinon la case est silencieusement perdue au prochain Enregistrer
    depuis cet onglet."""
    tab = _tab()
    c = {"name": "test", "components": ["U", "X"], "conditions": [],
         "composition_exacte": True}
    assert tab._est_avance(c) is True


def test_sans_composition_exacte_reste_simple():
    """Regression guard : un pattern tout-string, sans la clé, reste éditable
    (comportement historique inchangé)."""
    tab = _tab()
    c = {"name": "test", "components": ["R", "C"], "conditions": []}
    assert tab._est_avance(c) is False


def test_composition_exacte_false_explicite_reste_simple():
    """La clé présente mais à False (comportement par défaut explicite) ne
    doit pas non plus forcer le mode avancé."""
    tab = _tab()
    c = {"name": "test", "components": ["R"], "conditions": [],
         "composition_exacte": False}
    assert tab._est_avance(c) is False


def test_resume_avance_mentionne_la_composition_exacte():
    tab = _tab()
    c = {"name": "test", "components": [{"type": "U", "categorie": "AOP"}],
         "conditions": [], "composition_exacte": True}
    texte = tab._resume_avance(c)
    assert "EXACTE" in texte
