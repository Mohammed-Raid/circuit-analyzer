"""
@file test_integration.py
@brief Tests automatises pour test_integration.
"""

import subprocess, sys, os, tempfile
from pathlib import Path

from circuit_analyzer.composant import Composant, construire_graphe
from circuit_analyzer.detecteur import detecter_impedances, analyser


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

        assert 'Filtre RC passe-bas' in report
        assert 'Pont diviseur de tension' in report
        assert 'Condensateur de découplage' in report
        assert 'Protection par fusible' in report
        assert 'Absorbeur RC' in report
        assert 'Pont redresseur (Graetz)' in report
        assert 'Transistor en commutation' in report
        assert 'Suiveur de tension (AOP)' in report
        assert 'R1' in report
        assert 'C1' in report
