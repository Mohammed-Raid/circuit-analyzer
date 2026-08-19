"""
@file test_positions_depuis_gabarit.py
@brief Lot 9 -- demande explicite du boss : « add another canonique one
without hard coding it and still having the placement when exporting to
the other app ». Teste `gabarit.positions_depuis_gabarit` et son branchement
dans `xml._positionner_composants_bloc`.

Contrairement au lot 8 (bascule de DÉTECTION, revertée après régression
réelle), ceci ne touche QUE la DISPOSITION d'un montage DÉJÀ détecté par le
détecteur Python (inchangé, jamais concerné) -- le risque du lot 8 (voisin
supplémentaire légitime sur une vraie carte) ne s'applique pas ici, car le
gabarit n'est mis en correspondance qu'avec le sous-graphe de `bloc.comps`
lui-même, jamais le graphe entier de la carte.
"""
import os

from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.gabarit import positions_depuis_gabarit
from circuit_analyzer.parser import Component
from circuit_analyzer.xml import _grouper_par_circuit, _positionner_blocs, generer_xml


def _ecrire_gabarit(tmp_path_dir, nom, comps):
    path = os.path.join(str(tmp_path_dir), f"{nom}.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(generer_xml(comps))
    return path


def test_positions_depuis_gabarit_none_si_aucun_fichier():
    comps = [Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET1', 'OUT': 'NET2',
                                   'V+': 'VCC', 'V-': 'GND'})]
    assert positions_depuis_gabarit("Montage Qui N'existe Pas Du Tout", comps, 0, 0) is None


def test_positions_depuis_gabarit_utilise_le_fichier_nomme_exactement(tmp_path, monkeypatch):
    import circuit_analyzer.gabarit as gabmod
    monkeypatch.setattr(gabmod, "racine_patterns_reference", lambda: tmp_path)
    monkeypatch.setattr(gabmod, "_cache_gabarits_disposition", {}, raising=False)

    nom = "Montage Test Lot9"
    ref = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_A', 'OUT': 'NET_B',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_C', '2': 'NET_A'}, '10k'),
    ]
    _ecrire_gabarit(tmp_path, nom, ref)

    cible = [
        Component('U9', 'U', {'IN+': 'GND', 'IN-': 'NET_X', 'OUT': 'NET_Y',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R9', 'R', {'1': 'NET_Z', '2': 'NET_X'}, '4k7'),
    ]
    positions = positions_depuis_gabarit(nom, cible, 100, 100)
    assert positions is not None
    assert set(positions) == {'U9', 'R9'}
    assert positions['U9'] == (100, 100)
    assert positions['R9'] != positions['U9']


def test_positions_depuis_gabarit_none_si_correspondance_partielle(tmp_path, monkeypatch):
    """@brief Le bloc contient un composant EN TROP que le gabarit ne
    montre pas -- doit refuser proprement (None) plutôt que de ne placer
    qu'une partie du bloc."""
    import circuit_analyzer.gabarit as gabmod
    monkeypatch.setattr(gabmod, "racine_patterns_reference", lambda: tmp_path)
    monkeypatch.setattr(gabmod, "_cache_gabarits_disposition", {}, raising=False)

    nom = "Montage Partiel Lot9"
    ref = [Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_A', 'OUT': 'NET_B',
                                 'V+': 'VCC', 'V-': 'GND'})]
    _ecrire_gabarit(tmp_path, nom, ref)

    cible = [
        Component('U9', 'U', {'IN+': 'GND', 'IN-': 'NET_X', 'OUT': 'NET_Y',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R9', 'R', {'1': 'NET_Z', '2': 'NET_X'}, '4k7'),   # absent du gabarit
    ]
    assert positions_depuis_gabarit(nom, cible, 0, 0) is None


def test_integration_bloc_utilise_le_gabarit_avant_le_repli_generique(tmp_path, monkeypatch):
    """@brief Bout en bout via `_grouper_par_circuit`/`_positionner_blocs` :
    un montage qui n'a JAMAIS eu de code Python de positionnement (aucune
    entrée dans _POSITIONNEURS_PAR_MOTIF, jamais un mot-clé reconnu par le
    repli générique) obtient quand même une disposition dérivée du dessin,
    dès qu'un fichier au bon nom existe -- ET redevient la grille générique
    dès que ce fichier n'existe plus (aucune dépendance cachée)."""
    import circuit_analyzer.gabarit as gabmod
    monkeypatch.setattr(gabmod, "racine_patterns_reference", lambda: tmp_path)
    monkeypatch.setattr(gabmod, "_cache_gabarits_disposition", {}, raising=False)

    nom = "Motif Jamais Code En Python"
    cible = [
        Component('U5', 'U', {'IN+': 'GND', 'IN-': 'NET_X', 'OUT': 'NET_Y',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('RX', 'R', {'1': 'NET_Z', '2': 'NET_X'}, '10k'),
    ]
    match = {'circuit_type': nom, 'components': ['U5', 'RX'], 'nodes': [],
             'confidence': 0.8, 'confidence_level': 'high', 'reasons': [],
             'warnings': [], 'functional_category': 'divers', 'satellites': []}

    blocs_avant = _grouper_par_circuit(cible, [match])
    positions_avant = _positionner_blocs(blocs_avant)

    ref = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_A', 'OUT': 'NET_B',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_C', '2': 'NET_A'}, '10k'),
    ]
    _ecrire_gabarit(tmp_path, nom, ref)
    gabmod._cache_gabarits_disposition.clear()   # simule un nouveau run (le cache n'est vide qu'au demarrage)

    blocs_apres = _grouper_par_circuit(cible, [match])
    positions_apres = _positionner_blocs(blocs_apres)

    assert positions_avant != positions_apres, (
        "l'ajout du fichier de reference doit changer la disposition, "
        "sans qu'aucun code Python n'ait ete touche pour ce motif")
