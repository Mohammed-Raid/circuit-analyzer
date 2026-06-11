# Redirige vers xml.py — gardé pour la compatibilité des tests existants.
from circuit_analyzer.xml import (
    generer_xml as components_to_xml,
    _grouper_par_circuit as _layout_groups,
    _positionner_blocs as _place_blocks,
    _Bloc as _Block,
    _BLOCS_PAR_RANGEE as _BLOCKS_PER_ROW,
    _LARG_COMP as _COMP_W,
    _HAUT_RANGEE as _BLOCK_ROW_H,
    BoardSCHGenerator,
)
