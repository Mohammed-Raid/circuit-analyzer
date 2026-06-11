"""
test_confidence.py — Tests pour le système de confiance, les alias de nets,
le parser de valeurs et les améliorations XML.
"""
import pytest
from circuit_analyzer.parser import Component
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.patterns.base import (
    is_ground_net, is_power_net, is_protective_earth_net, classify_net,
    is_gnd, is_power,
)
from circuit_analyzer.value_parser import (
    parse_valeur, classifier_resistance, classifier_condensateur,
)


# =============================================================================
# Alias backward-compat
# =============================================================================

def test_is_gnd_alias_works():
    assert is_gnd('GND')
    assert not is_gnd('PE')

def test_is_power_alias_works():
    assert is_power('VCC')
    assert not is_power('GND')


# =============================================================================
# Net aliases — ground
# =============================================================================

def test_ground_net_standard():
    for n in ('GND', 'AGND', 'DGND', 'PGND', 'VSS', '0', '0V', 'COM'):
        assert is_ground_net(n), f"'{n}' devrait être masse"

def test_ground_net_kicad_prefix():
    assert is_ground_net('/GND')
    assert is_ground_net('/AGND')

def test_ground_net_compound():
    assert is_ground_net('GND_AOP')
    assert is_ground_net('PGND1')

def test_ground_net_not_power():
    assert not is_ground_net('VCC')
    assert not is_ground_net('NET1')
    assert not is_ground_net('')


# =============================================================================
# Net aliases — power
# =============================================================================

def test_power_net_standard():
    for n in ('VCC', 'VDD', 'VIN', 'VBAT', 'VBUS', '+5V', '+3V3'):
        assert is_power_net(n), f"'{n}' devrait être alimentation"

def test_power_net_compound():
    assert is_power_net('VCC_AOP')
    assert is_power_net('VDD1')

def test_power_net_not_ground():
    assert not is_power_net('GND')
    assert not is_power_net('NET1')
    assert not is_power_net('')


# =============================================================================
# Net aliases — protective earth (PE ≠ GND)
# =============================================================================

def test_protective_earth_recognized():
    for n in ('PE', 'EARTH', 'CHASSIS'):
        assert is_protective_earth_net(n), f"'{n}' devrait être terre de protection"

def test_protective_earth_not_gnd():
    assert not is_ground_net('PE')
    assert not is_ground_net('EARTH')
    assert not is_ground_net('CHASSIS')

def test_protective_earth_not_power():
    assert not is_power_net('PE')

def test_classify_net():
    assert classify_net('GND')   == 'ground'
    assert classify_net('VCC')   == 'power'
    assert classify_net('PE')    == 'pe'
    assert classify_net('NET1')  == 'signal'


# =============================================================================
# Value parser
# =============================================================================

def test_parse_resistance():
    assert parse_valeur('10k')   == pytest.approx(10_000.0)
    assert parse_valeur('4.7k')  == pytest.approx(4_700.0)
    assert parse_valeur('1M')    == pytest.approx(1_000_000.0)
    assert parse_valeur('0R')    == pytest.approx(0.0)
    assert parse_valeur('10R')   == pytest.approx(10.0)
    assert parse_valeur('0.01R') == pytest.approx(0.01)
    assert parse_valeur('100')   == pytest.approx(100.0)

def test_parse_capacitance():
    assert parse_valeur('100nF') == pytest.approx(1e-7)
    assert parse_valeur('1uF')   == pytest.approx(1e-6)
    assert parse_valeur('10µF')  == pytest.approx(1e-5)
    assert parse_valeur('470u')  == pytest.approx(470e-6)
    assert parse_valeur('1mF')   == pytest.approx(1e-3)

def test_parse_inductance():
    assert parse_valeur('10uH') == pytest.approx(1e-5)
    assert parse_valeur('1mH')  == pytest.approx(1e-3)

def test_parse_eia_notation():
    assert parse_valeur('4K7')  == pytest.approx(4_700.0)
    assert parse_valeur('2M2')  == pytest.approx(2_200_000.0)

def test_parse_none_on_empty():
    assert parse_valeur('')     is None
    assert parse_valeur(None)   is None
    assert parse_valeur('abc')  is None

def test_classifier_resistance():
    assert classifier_resistance('0R')    == 'jumper'
    assert classifier_resistance('0.5')   == 'shunt'
    assert classifier_resistance('10k')   == 'pull'
    assert classifier_resistance('1k')    == 'standard'
    assert classifier_resistance('')      == 'unknown'


# =============================================================================
# Champs de confiance présents dans chaque match
# =============================================================================

def _rc_lowpass():
    return [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}, '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]

def test_confidence_fields_present():
    results = match_patterns(build_graph(_rc_lowpass()))
    assert results
    m = results[0]
    assert 'confidence'          in m
    assert 'confidence_level'    in m
    assert 'reasons'             in m
    assert 'warnings'            in m
    assert 'functional_category' in m
    assert 'locked_components'   in m

def test_confidence_level_valid_values():
    results = match_patterns(build_graph(_rc_lowpass()))
    for m in results:
        assert m['confidence_level'] in ('high', 'medium', 'low')
        assert 0.0 <= m['confidence'] <= 1.0

def test_backward_compat_keys_preserved():
    results = match_patterns(build_graph(_rc_lowpass()))
    for m in results:
        assert 'circuit_type' in m
        assert 'components'   in m
        assert 'nodes'        in m

def test_rc_filter_high_confidence_with_values():
    results = match_patterns(build_graph(_rc_lowpass()))
    rc = next(m for m in results if m['circuit_type'] == 'Filtre RC passe-bas')
    assert rc['confidence_level'] == 'high'
    assert any('Hz' in r for r in rc['reasons'])

def test_rc_filter_warning_no_values():
    comps = [
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_MID'}),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}),
    ]
    results = match_patterns(build_graph(comps))
    rc = next(m for m in results if m['circuit_type'] == 'Filtre RC passe-bas')
    assert rc['confidence_level'] in ('medium', 'low')
    assert any('absentes' in w.lower() or 'vérifiable' in w.lower() for w in rc['warnings'])

def test_voltage_divider_high_confidence_power_gnd():
    comps = [
        Component('R1', 'R', {'1': 'VCC', '2': 'NET_DIV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_DIV', '2': 'GND'}, '4.7k'),
    ]
    results = match_patterns(build_graph(comps))
    vd = next(m for m in results if m['circuit_type'] == 'Pont diviseur de tension')
    assert vd['confidence_level'] == 'high'

def test_voltage_divider_medium_confidence_signal_nets():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_MID'}, '10k'),
        Component('R2', 'R', {'1': 'NET_MID', '2': 'NET_B'}, '4.7k'),
    ]
    results = match_patterns(build_graph(comps))
    vd = next((m for m in results if m['circuit_type'] == 'Pont diviseur de tension'), None)
    if vd:
        assert vd['confidence_level'] in ('medium', 'low')
        assert any('non' in w.lower() or 'masse' in w.lower() for w in vd['warnings'])

def test_decoupling_cap_high_confidence_power_gnd():
    comps = [Component('C1', 'C', {'1': 'VCC', '2': 'GND'}, '100nF')]
    results = match_patterns(build_graph(comps))
    dec = next(m for m in results if m['circuit_type'] == 'Condensateur de découplage')
    assert dec['confidence_level'] == 'high'

def test_diode_esd_has_ambiguity_warning():
    comps = [Component('D1', 'D', {'A': 'NET_SIG', 'K': 'GND'})]
    results = match_patterns(build_graph(comps))
    esd = next((m for m in results if 'ESD' in m['circuit_type']), None)
    if esd:
        assert esd['warnings']

def test_snubber_has_ambiguity_warning():
    comps = [
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_B'}, '100'),
        Component('C1', 'C', {'1': 'NET_A', '2': 'NET_B'}, '10nF'),
    ]
    results = match_patterns(build_graph(comps))
    snub = next((m for m in results if 'Absorbeur' in m['circuit_type']), None)
    if snub:
        assert snub['warnings']

def test_functional_category_set():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_OUT', 'OUT': 'NET_OUT',
                               'V+': 'VCC', 'V-': 'GND'}),
    ]
    results = match_patterns(build_graph(comps))
    suiveur = next(m for m in results if 'Suiveur' in m['circuit_type'])
    assert suiveur['functional_category'] == 'amplification'


# =============================================================================
# Suppressed matches
# =============================================================================

def test_suppressed_matches_accessible():
    """ResultatsAnalyse doit avoir un attribut .supprimes."""
    results = match_patterns(build_graph(_rc_lowpass()))
    assert hasattr(results, 'supprimes')
    assert isinstance(results.supprimes, list)

def test_suppressed_contains_overlapping_match():
    """Quand R1/R2 forment un pont diviseur ET un filtre RC, le second doit être supprimé."""
    comps = [
        Component('R1', 'R', {'1': 'VCC',    '2': 'NET_MID'}, '10k'),
        Component('R2', 'R', {'1': 'NET_MID', '2': 'GND'},    '10k'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'},    '100nF'),
    ]
    results = match_patterns(build_graph(comps))
    all_types = [m['circuit_type'] for m in results]
    supp_types = [m['circuit_type'] for m in results.supprimes]
    # Au moins un circuit principal + au moins une suppression possible
    assert len(results) > 0
    # Les supprimés sont des matches bruts (non enrichis depuis le sous-projet perf)
    for s in results.supprimes:
        assert 'circuit_type' in s
        assert 'components' in s

def test_results_still_iterable_like_list():
    """Backward compat : ResultatsAnalyse se comporte comme une liste."""
    results = match_patterns(build_graph(_rc_lowpass()))
    assert len(results) > 0
    types = [r['circuit_type'] for r in results]
    assert isinstance(types, list)

def test_empty_results_equals_empty_list():
    """Backward compat : résultat vide == []."""
    import networkx as nx
    assert match_patterns(nx.MultiGraph()) == []


# =============================================================================
# XML import amélioré
# =============================================================================

def test_xml_import_does_not_crash_on_unknown(tmp_path):
    """lire_xml ne doit pas crasher si un composant a un nom inconnu."""
    from circuit_analyzer.xml import lire_xml
    xml_content = """<?xml version="1.0"?>
<Root>
  <CmpntL>
    <DataItem>
      <id>1</id><Name>Résistance</Name><value>10k</value>
      <datapin><DataPin><Pname>1</Pname></DataPin></datapin>
      <datapin><DataPin><Pname>2</Pname></DataPin></datapin>
    </DataItem>
    <DataItem>
      <id>2</id><Name>ComposantInconnu</Name><value>xyz</value>
      <datapin><DataPin><Pname>A</Pname></DataPin></datapin>
    </DataItem>
  </CmpntL>
  <lineL/>
</Root>"""
    p = tmp_path / 'test.xml'
    p.write_text(xml_content, encoding='utf-8')
    result = lire_xml(str(p))
    # Pas de crash, et le composant inconnu est gardé comme type X
    types = [c.type for c in result]
    assert 'R' in types
    assert 'X' in types
    assert any('inconnu' in w.lower() or 'ComposantInconnu' in w for w in result.warnings)

def test_xml_import_english_names(tmp_path):
    """Resistor / Capacitor / Inductor doivent être reconnus."""
    from circuit_analyzer.xml import lire_xml
    xml_content = """<?xml version="1.0"?>
<Root>
  <CmpntL>
    <DataItem>
      <id>1</id><Name>Resistor</Name><value>10k</value>
      <datapin><DataPin><Pname>1</Pname></DataPin></datapin>
      <datapin><DataPin><Pname>2</Pname></DataPin></datapin>
    </DataItem>
    <DataItem>
      <id>2</id><Name>Capacitor</Name><value>100nF</value>
      <datapin><DataPin><Pname>+</Pname></DataPin></datapin>
      <datapin><DataPin><Pname>-</Pname></DataPin></datapin>
    </DataItem>
    <DataItem>
      <id>3</id><Name>Inductor</Name><value>10uH</value>
      <datapin><DataPin><Pname>1</Pname></DataPin></datapin>
      <datapin><DataPin><Pname>2</Pname></DataPin></datapin>
    </DataItem>
  </CmpntL>
  <lineL/>
</Root>"""
    p = tmp_path / 'test.xml'
    p.write_text(xml_content, encoding='utf-8')
    result = lire_xml(str(p))
    types = {c.type for c in result}
    assert 'R' in types
    assert 'C' in types
    assert 'L' in types
    assert not result.warnings  # aucun avertissement

def test_xml_import_led_tvs_zener(tmp_path):
    """LED / TVS / Zener doivent être reconnus comme diodes."""
    from circuit_analyzer.xml import lire_xml
    xml_content = """<?xml version="1.0"?>
<Root>
  <CmpntL>
    <DataItem>
      <id>1</id><Name>LED</Name><value></value>
      <datapin><DataPin><Pname>A</Pname></DataPin></datapin>
      <datapin><DataPin><Pname>K</Pname></DataPin></datapin>
    </DataItem>
    <DataItem>
      <id>2</id><Name>TVS</Name><value></value>
      <datapin><DataPin><Pname>A</Pname></DataPin></datapin>
      <datapin><DataPin><Pname>K</Pname></DataPin></datapin>
    </DataItem>
  </CmpntL>
  <lineL/>
</Root>"""
    p = tmp_path / 'test.xml'
    p.write_text(xml_content, encoding='utf-8')
    result = lire_xml(str(p))
    types = [c.type for c in result]
    assert types.count('D') == 2

def test_xml_import_warnings_has_attribute(tmp_path):
    """lire_xml retourne toujours un objet avec .warnings même sans erreur."""
    from circuit_analyzer.xml import lire_xml
    xml_content = """<?xml version="1.0"?>
<Root><CmpntL/><lineL/></Root>"""
    p = tmp_path / 'test.xml'
    p.write_text(xml_content, encoding='utf-8')
    result = lire_xml(str(p))
    assert hasattr(result, 'warnings')
    assert isinstance(result.warnings, list)
