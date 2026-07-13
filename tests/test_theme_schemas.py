"""@file test_theme_schemas.py
@brief Interdit tout litteral couleur hex dans les modules de dessin des
schemas (spec 2026-07-13 §6) : la source unique est gui/theme.py.
Liste d'exclusions VIDE par contrat (meme regle que test_puces_resolution).
"""
import re
from pathlib import Path

import pytest

GUI = Path(__file__).resolve().parent.parent / "gui"
MODULES = ["circuit_viewer.py", "impedance_schematic.py",
           "logic_schematic.py", "puce_schematic.py"]
HEX = re.compile(r'["\']#[0-9a-fA-F]{3,8}["\']')


@pytest.mark.parametrize("nom", MODULES)
def test_aucun_hex_en_dur(nom):
    src = (GUI / nom).read_text(encoding="utf-8")
    lignes = [(i + 1, l) for i, l in enumerate(src.splitlines())
              if HEX.search(l)]
    assert not lignes, f"{nom}: littéraux hex interdits -> {lignes[:10]}"


def test_tokens_schemas_presents_et_figes():
    from types import MappingProxyType
    from gui import theme
    assert isinstance(theme.SCHEMA_COLORS, MappingProxyType)
    assert isinstance(theme.SCHEMA_DIMS, MappingProxyType)
    # Invariant boss : canvas des schemas CLAIR.
    assert theme.SCHEMA_COLORS["SCH_BG"] == "#fafafa"
    assert theme.SCHEMA_DIMS["PAS"] == 0.5
    assert theme.SCHEMA_DIMS["X0"] == 4.5


def test_grid_lit_ses_constantes_dans_theme():
    from gui import schema_grid, theme
    assert schema_grid.PAS is theme.SCHEMA_DIMS["PAS"] or \
        schema_grid.PAS == theme.SCHEMA_DIMS["PAS"]
