import os, collections
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
