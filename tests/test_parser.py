import os, tempfile, pytest
from circuit_analyzer.parser import parse_file, Component


def _write_tmp(content):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
    f.write(content)
    f.close()
    return f.name


def test_parse_resistor_with_value():
    path = _write_tmp("R1  NET_A  NET_B  10k\n")
    comps = parse_file(path)
    os.unlink(path)
    assert len(comps) == 1
    c = comps[0]
    assert c.ref == 'R1'
    assert c.type == 'R'
    assert c.net1 == 'NET_A'
    assert c.net2 == 'NET_B'
    assert c.value == '10k'


def test_parse_diode_without_value():
    path = _write_tmp("D1  NET_A  NET_B\n")
    comps = parse_file(path)
    os.unlink(path)
    assert len(comps) == 1
    assert comps[0].type == 'D'
    assert comps[0].value == ''


def test_comments_and_blank_lines_ignored():
    path = _write_tmp("# commentaire\n\nR1 A B 10k\n")
    comps = parse_file(path)
    os.unlink(path)
    assert len(comps) == 1


def test_multiple_components():
    path = _write_tmp("R1 A B 10k\nC1 B GND 100nF\n")
    comps = parse_file(path)
    os.unlink(path)
    assert len(comps) == 2


def test_type_deduced_from_prefix():
    cases = [('R1', 'R'), ('C2', 'C'), ('L3', 'L'), ('D4', 'D'), ('F5', 'F')]
    lines = '\n'.join(f'{ref} A B' for ref, _ in cases)
    path = _write_tmp(lines)
    comps = parse_file(path)
    os.unlink(path)
    for comp, (_, expected_type) in zip(comps, cases):
        assert comp.type == expected_type


def test_transistor_parsed_with_correct_pin_names():
    path = _write_tmp("Q1  NET_BASE  NET_COLL  NET_EMIT\n")
    comps = parse_file(path)
    os.unlink(path)
    assert len(comps) == 1
    c = comps[0]
    assert c.type == 'Q'
    assert c.pins == {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'NET_EMIT'}
    assert c.net1 == 'NET_BASE'


def test_sw_prefix_detected_as_two_chars():
    path = _write_tmp("SW1  NET_A  NET_B\n")
    comps = parse_file(path)
    os.unlink(path)
    assert len(comps) == 1
    assert comps[0].type == 'SW'


def test_opamp_parsed_with_five_pins():
    path = _write_tmp("U1  NET_INP  NET_INM  NET_OUT  VCC  GND\n")
    comps = parse_file(path)
    os.unlink(path)
    assert len(comps) == 1
    c = comps[0]
    assert c.type == 'U'
    assert c.pins == {'IN+': 'NET_INP', 'IN-': 'NET_INM', 'OUT': 'NET_OUT', 'V+': 'VCC', 'V-': 'GND'}
