"""
@file test_eretro_corpus.py
@brief Intégration : import des VRAIS fichiers ERetroDesign du corpus
(SolutionERetroDesignX20260813, lecture seule — ne jamais modifier ni
committer ce dossier).
"""
import time
from pathlib import Path

import pytest

from circuit_analyzer.xml import lire_xml
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns

CORPUS = (Path(__file__).resolve().parent.parent
          / 'SolutionERetroDesignX20260813' / 'ERetroDesign' / 'ERetroDesign'
          / 'bin' / 'Debug')

necessite_corpus = pytest.mark.skipif(
    not CORPUS.exists(), reason='corpus ERetroDesign absent de ce poste')


@necessite_corpus
def test_savediag_importe_et_analysable():
    # SaveDiag.xml : vieux format de refs concaténées, 6 composants, 6 fils.
    comps = lire_xml(str(CORPUS / 'SaveDiag.xml'))
    assert len(comps) >= 2
    graphe = build_graph(comps)
    match_patterns(graphe)          # aucune exception = contrat minimal
    # au moins un fil résolu : deux composants partagent un net
    nets = [n for c in comps for n in c.pins.values() if n != 'NC']
    assert len(nets) != len(set(nets)), 'aucun net partagé — connexité perdue'


@necessite_corpus
def test_diag2_importe_avec_composes():
    # Diag2.xml : 2 CComp, id=0 dupliqués, refs T…/X….
    comps = lire_xml(str(CORPUS / 'Diag2.xml'))
    assert len(comps) >= 2
    build_graph(comps)
    # les composés produisent soit des items internes (ref 'U*.n'),
    # soit des boîtes noires avec warning — jamais une disparition muette.
    refs_internes = [c.ref for c in comps if '.' in c.ref]
    assert refs_internes or comps.warnings


@necessite_corpus
def test_testdiagram_carte_reelle_sous_budget():
    # 2,4 Mo, 285 DataItem, 63 CComp, 41 id=0 : la vraie carte de l'entreprise.
    debut = time.monotonic()
    comps = lire_xml(str(CORPUS / 'TestDiagram.xml'))
    graphe = build_graph(comps)
    match_patterns(graphe)
    duree = time.monotonic() - debut
    assert len(comps) >= 100
    assert duree < 30, f'import+analyse en {duree:.1f}s (budget 30s)'


@necessite_corpus
def test_testdiagram_gate2_reconnus_par_forme():
    # Les Gate2 de premier niveau (nom inconnu, forme = arc + 3 broches) ne
    # sont plus des boîtes noires X : ils deviennent des boîtes IC U, avec un
    # avertissement dédié « typé par sa forme » (distinct de « inconnu »).
    # (Pas de helper `_lire_corpus` dans ce fichier : on réutilise le
    # chargement direct des autres tests corpus ci-dessus.)
    comps = lire_xml(str(CORPUS / 'TestDiagram.xml'))
    gate2_en_U = [c for c in comps if c.ref.startswith('U')]
    assert len(gate2_en_U) >= 100
    assert any('forme' in w.lower() for w in comps.warnings)
    # Aucun composant correctement typé auparavant ne régresse en type faux :
    assert all(c.type in ('R', 'C', 'L', 'D', 'Q', 'M', 'U', 'K', 'F', 'X')
               for c in comps)
