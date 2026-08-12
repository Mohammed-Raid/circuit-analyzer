"""
@file test_parsers.py
@brief Tests des parsers SPICE/LTspice et KiCad.
"""

import os
import tempfile

from circuit_analyzer.composant import (
    _detect_format,
    lire_kicad_net,
    lire_netlist,
    lire_spice,
)
from circuit_analyzer.detecteur import match_patterns
from circuit_analyzer.graph_builder import build_graph

# ── SPICE parser ──────────────────────────────────────────────────────────────

SPICE_RC = """\
* Test: RC filtre passe-bas
R1 VCC NET_A 10k
C1 NET_A GND 100n
"""

SPICE_BJT = """\
* Test: transistor en commutation
* BJT SPICE order: Q collector base emitter [model]
Q1 NET_COLL NET_BASE GND 2N2222
R1 NET_CMD NET_BASE 1k
"""

SPICE_DIODE = """\
* Test: diode simple
* SPICE order: D anode cathode
D1 NET_A NET_K 1N4148
R1 VCC NET_A 1k
"""

SPICE_MOSFET = """\
* Test: MOSFET commutation
M1 NET_D NET_G GND NMOS
R1 VCC NET_D 100
R2 NET_G_CMD NET_G 10k
"""

SPICE_SKIP_DIRECTIVES = """\
* Circuit avec directives
.param Rval=10k
.tran 1ms 10ms
.model 2N2222 NPN
R1 VCC GND 10k
C1 VCC GND 100n
.backanno
.END
"""


def _write_tmp(content, suffix='.cir'):
    """Écrit un fichier temporaire et retourne son chemin."""
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix,
                                     delete=False, encoding='utf-8') as f:
        f.write(content)
        return f.name


def test_spice_detect_format():
    """@brief _detect_format reconnaît un fichier SPICE à la première ligne '*'."""
    path = _write_tmp(SPICE_RC)
    try:
        assert _detect_format(path) == 'spice'
    finally:
        os.unlink(path)


def test_spice_rc_filter():
    """@brief Parser SPICE : R et C correctement extraits avec leurs nets."""
    path = _write_tmp(SPICE_RC)
    try:
        comps = lire_spice(path)
    finally:
        os.unlink(path)
    refs = {c.ref: c for c in comps}
    assert 'R1' in refs and 'C1' in refs
    assert refs['R1'].pins == {'1': 'VCC', '2': 'NET_A'}
    assert refs['C1'].pins == {'1': 'NET_A', '2': 'GND'}
    assert refs['R1'].value == '10k'
    assert refs['C1'].value == '100n'


def test_spice_bjt_pin_order():
    """@brief Parser SPICE : BJT avec ordre SPICE C-B-E correctement mappé."""
    path = _write_tmp(SPICE_BJT)
    try:
        comps = lire_spice(path)
    finally:
        os.unlink(path)
    q = next(c for c in comps if c.type == 'Q')
    # SPICE order: Q ref collector base emitter → notre mapping C/B/E
    assert q.pins['C'] == 'NET_COLL'
    assert q.pins['B'] == 'NET_BASE'
    assert q.pins['E'] == 'GND'


def test_spice_diode_pin_order():
    """@brief Parser SPICE : Diode avec ordre SPICE anode-cathode."""
    path = _write_tmp(SPICE_DIODE)
    try:
        comps = lire_spice(path)
    finally:
        os.unlink(path)
    d = next(c for c in comps if c.type == 'D')
    assert d.pins['A'] == 'NET_A'
    assert d.pins['K'] == 'NET_K'


def test_spice_mosfet_pin_order():
    """@brief Parser SPICE : MOSFET avec ordre SPICE D-G-S."""
    path = _write_tmp(SPICE_MOSFET)
    try:
        comps = lire_spice(path)
    finally:
        os.unlink(path)
    m = next(c for c in comps if c.type == 'M')
    assert m.pins['D'] == 'NET_D'
    assert m.pins['G'] == 'NET_G'
    assert m.pins['S'] == 'GND'


def test_spice_skip_directives():
    """@brief Parser SPICE : lignes '.' et '*' ignorées, composants extraits."""
    path = _write_tmp(SPICE_SKIP_DIRECTIVES)
    try:
        comps = lire_spice(path)
    finally:
        os.unlink(path)
    types = {c.type for c in comps}
    assert 'R' in types and 'C' in types
    assert all(c.ref not in ('', None) for c in comps)


def test_spice_lire_netlist_autodect():
    """@brief lire_netlist() auto-détecte le format SPICE et délègue."""
    path = _write_tmp(SPICE_RC)
    try:
        comps = lire_netlist(path)
    finally:
        os.unlink(path)
    assert any(c.type == 'R' for c in comps)
    assert any(c.type == 'C' for c in comps)


def test_spice_pattern_detection():
    """@brief Pipeline complet : SPICE → parse → graphe → pattern detection."""
    path = _write_tmp(SPICE_BJT)
    try:
        comps = lire_spice(path)
    finally:
        os.unlink(path)
    results = match_patterns(build_graph(comps))
    types = [r['circuit_type'] for r in results]
    assert 'Transistor en commutation' in types


# ── KiCad parser ─────────────────────────────────────────────────────────────

KICAD_NET_V5 = """\
(net-list
  (components
    (comp (ref R1)
      (value 10k)
    )
    (comp (ref C1)
      (value 100n)
    )
    (comp (ref Q1)
      (value 2N2222)
    )
  )
  (nets
    (net (code 1) (name /GND)
      (node (ref R1) (pin 2))
      (node (ref Q1) (pin E))
    )
    (net (code 2) (name /VCC)
      (node (ref R1) (pin 1))
    )
    (net (code 3) (name /NET_A)
      (node (ref C1) (pin 1))
      (node (ref Q1) (pin C))
    )
    (net (code 4) (name /NET_B)
      (node (ref C1) (pin 2))
      (node (ref Q1) (pin B))
    )
  )
)
"""

KICAD_NET_V6 = """\
(export (version "E")
  (components
    (comp (ref "R1") (value "10k"))
    (comp (ref "C1") (value "100n"))
  )
  (nets
    (net (code "1") (name "GND")
      (node (ref "R1") (pin "1") (pintype "passive"))
      (node (ref "C1") (pin "2") (pintype "passive"))
    )
    (net (code "2") (name "VCC")
      (node (ref "R1") (pin "2") (pintype "passive"))
    )
    (net (code "3") (name "NET_A")
      (node (ref "C1") (pin "1") (pintype "passive"))
    )
  )
)
"""


def test_kicad_detect_format():
    """@brief _detect_format reconnaît un fichier KiCad à la première ligne '('."""
    path = _write_tmp(KICAD_NET_V5, suffix='.net')
    try:
        assert _detect_format(path) == 'kicad'
    finally:
        os.unlink(path)


def test_kicad_v5_components():
    """@brief Parser KiCad v5 : composants extraits avec valeurs."""
    path = _write_tmp(KICAD_NET_V5, suffix='.net')
    try:
        comps = lire_kicad_net(path)
    finally:
        os.unlink(path)
    refs = {c.ref: c for c in comps}
    assert 'R1' in refs and 'C1' in refs and 'Q1' in refs
    assert refs['R1'].value == '10k'
    assert refs['C1'].value == '100n'


def test_kicad_v5_nets():
    """@brief Parser KiCad v5 : nets correctement assignés aux broches."""
    path = _write_tmp(KICAD_NET_V5, suffix='.net')
    try:
        comps = lire_kicad_net(path)
    finally:
        os.unlink(path)
    refs = {c.ref: c for c in comps}
    r1 = refs['R1']
    # pin 1 → VCC, pin 2 → GND
    all_nets = set(r1.pins.values())
    assert 'VCC' in all_nets or 'NET_B' in all_nets  # au moins un net connu


def test_kicad_v6_components():
    """@brief Parser KiCad v6+ : composants avec pins et nets."""
    path = _write_tmp(KICAD_NET_V6, suffix='.net')
    try:
        comps = lire_kicad_net(path)
    finally:
        os.unlink(path)
    refs = {c.ref: c for c in comps}
    assert 'R1' in refs and 'C1' in refs
    r1_nets = set(refs['R1'].pins.values())
    assert 'GND' in r1_nets or 'VCC' in r1_nets


def test_kicad_lire_netlist_autodetect():
    """@brief lire_netlist() auto-détecte KiCad et délègue à lire_kicad_net."""
    path = _write_tmp(KICAD_NET_V6, suffix='.net')
    try:
        comps = lire_netlist(path)
    finally:
        os.unlink(path)
    assert len(comps) >= 2


def test_kicad_v5_bjt_nets():
    """@brief Parser KiCad v5 : pins BJT nommés explicitement (B, C, E) récupérés."""
    path = _write_tmp(KICAD_NET_V5, suffix='.net')
    try:
        comps = lire_kicad_net(path)
    finally:
        os.unlink(path)
    q = next((c for c in comps if c.type == 'Q'), None)
    assert q is not None
    nets = set(q.pins.values())
    assert 'GND' in nets      # émetteur
    assert 'NET_A' in nets    # collecteur


# ── Format texte natif — non-régression ──────────────────────────────────────

TEXTE_SIMPLE = """\
# Filtre passe-bas
R1  VCC  NET_A  10k
C1  NET_A  GND  100n
"""


def test_texte_non_regression():
    """@brief Le format texte natif continue de fonctionner après refactoring."""
    path = _write_tmp(TEXTE_SIMPLE, suffix='.txt')
    try:
        comps = lire_netlist(path)
    finally:
        os.unlink(path)
    refs = {c.ref: c for c in comps}
    assert refs['R1'].value == '10k'
    assert refs['C1'].value == '100n'
    assert refs['R1'].pins == {'1': 'VCC', '2': 'NET_A'}
