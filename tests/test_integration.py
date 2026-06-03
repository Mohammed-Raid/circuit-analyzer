import subprocess, sys, os, tempfile
from pathlib import Path


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
"""


def test_full_pipeline():
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
        assert 'Snubber RC' in report
        assert 'Pont redresseur (Graetz)' in report
        assert 'R1' in report
        assert 'C1' in report
