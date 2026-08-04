"""
@file test_integration.py
@brief Tests automatises pour test_integration.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.detecteur import analyser, detecter_impedances

SAMPLE_NETLIST = """\
# Filtre RC passe-bas
R1  NET_IN   NET_MID  10k
C1  NET_MID  GND      100nF

# Pont diviseur
R2  VCC      NET_DIV  10k
R3  NET_DIV  GND      4.7k

# Découplage
C2  VCC      GND      10uF

# Fusible
F1  LINE_IN  NET_FUSE

# Snubber
R4  NET_A    NET_B    100
C3  NET_A    NET_B    10nF

# Pont de Graetz
D1  AC_POS   DC_POS
D2  AC_NEG   DC_POS
D3  DC_NEG   AC_POS
D4  DC_NEG   AC_NEG

# Transistor en commutation
Q1  NET_BASE  NET_COLL  GND
R5  NET_CMD   NET_BASE  1k

# AOP suiveur
U1  NET_SIG  NET_OUT  NET_OUT  VCC  GND
"""


def test_detecter_impedances_emet_chaque_z():
    # IN ─R1─ MID ─R2─ GND : un seul composite Z1 = R1+R2 entre IN et GND.
    from circuit_analyzer import impedance
    g = construire_graphe([
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '1k'),
        Composant('R2', 'R', {'1': 'MID', '2': 'GND'}, '2k'),
    ])
    reduit = impedance.reduire(g)
    matches = list(detecter_impedances(reduit))
    assert len(matches) == 1
    m = matches[0]
    assert m['circuit_type'] == 'Impédance Z'
    assert m['components'] == ['Z1']           # ref synthétique, expansée par analyser()
    assert set(m['nodes']) == {'IN', 'GND'}
    assert m['composition'] == 'R1+R2'


def test_analyser_filtre_rc_isole_devient_impedance():
    # Filtre RC isolé : plus de "Filtre RC passe-bas", mais une Impédance Z.
    g = construire_graphe([
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '10k'),
        Composant('C1', 'C', {'1': 'MID', '2': 'GND'}, '100n'),
    ])
    res = analyser(g)
    types = [m['circuit_type'] for m in res]
    assert 'Filtre RC passe-bas' not in types
    assert 'Impédance Z' in types
    z = next(m for m in res if m['circuit_type'] == 'Impédance Z')
    assert sorted(z['components']) == ['C1', 'R1']   # vraies refs après expansion


def test_analyser_inverseur_avec_feedback_composite():
    # Rf = R1+R2 (composite homogène) : l'inverseur reste détecté, refs réelles.
    g = construire_graphe([
        Composant('U1', 'U', {'IN+': 'GND', 'IN-': 'INM', 'OUT': 'OUT'}),
        Composant('Re', 'R', {'1': 'IN', '2': 'INM'}, '1k'),
        Composant('R1', 'R', {'1': 'INM', '2': 'MID'}, '4k7'),
        Composant('R2', 'R', {'1': 'MID', '2': 'OUT'}, '4k7'),
    ])
    res = analyser(g)
    inv = next((m for m in res if m['circuit_type'] == 'Amplificateur inverseur (AOP)'), None)
    assert inv is not None
    # Le feedback composite R1+R2 est expansé en vraies refs dans le montage.
    assert {'U1', 'Re', 'R1', 'R2'} <= set(inv['components'])


def test_enrichissement_impedance_z():
    g = construire_graphe([
        Composant('R1', 'R', {'1': 'IN', '2': 'MID'}, '10k'),
        Composant('C1', 'C', {'1': 'MID', '2': 'GND'}, '100n'),
    ])
    res = analyser(g)
    z = next(m for m in res if m['circuit_type'] == 'Impédance Z')
    assert z['functional_category'] == 'impedance'
    assert z['confidence_level'] in ('high', 'medium', 'low')
    # La composition est mentionnée dans les raisons.
    assert any('R1+C1' in r for r in z['reasons'])


def test_full_pipeline():
    """@brief Verifie full pipeline.

    @return None
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        netlist_path = Path(tmpdir) / 'circuit.txt'
        report_path = Path(tmpdir) / 'report.txt'
        netlist_path.write_text(SAMPLE_NETLIST, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, 'main.py', str(netlist_path), '--output', str(report_path)],
            capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        report = report_path.read_text(encoding='utf-8')

        # Les passifs isolés sont désormais classifiés comme "Impédance Z"
        assert 'Impédance Z' in report
        assert 'Pont redresseur (Graetz)' in report
        assert 'Transistor en commutation' in report
        assert 'Suiveur de tension (AOP)' in report
        assert 'R1' in report
        assert 'C1' in report


def test_cli_affiche_les_composants_reels_identifies():
    """@brief Bug reel : la CLI (main.py) n'affichait jamais la section
    "Composants reels identifies" (catalogue) — generate() est appelee sans
    le parametre composants=, contrairement a la GUI (gui/tab_analyze.py) qui
    le passe. Une puce catalogue (ex. NE555) semblait donc invisible en CLI
    alors qu'elle est bien reconnue."""
    netlist = "U1  NET1  NET2  NET3  VCC  GND  NE555\n"
    with tempfile.TemporaryDirectory() as tmpdir:
        netlist_path = Path(tmpdir) / 'circuit.txt'
        report_path = Path(tmpdir) / 'report.txt'
        netlist_path.write_text(netlist, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, 'main.py', str(netlist_path), '--output', str(report_path)],
            capture_output=True, text=True
        )

        assert result.returncode == 0, result.stderr
        report = report_path.read_text(encoding='utf-8')
        assert 'Composants reels identifies' in report or 'Composants réels identifiés' in report
        assert 'NE555' in report
