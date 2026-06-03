from circuit_analyzer.reporter import generate


SAMPLE_RESULTS = [
    {'circuit_type': 'Filtre RC passe-bas', 'components': ['R1', 'C1'], 'nodes': ['NET_IN', 'NET_MID', 'GND']},
    {'circuit_type': 'Pont diviseur de tension', 'components': ['R2', 'R3'], 'nodes': ['VCC', 'NET_DIV', 'GND']},
]


def test_report_contains_header():
    report = generate(SAMPLE_RESULTS, 'circuit.txt', 4)
    assert '=== ANALYSE DU CIRCUIT ===' in report


def test_report_contains_circuit_type():
    report = generate(SAMPLE_RESULTS, 'circuit.txt', 4)
    assert 'Filtre RC passe-bas' in report
    assert 'Pont diviseur de tension' in report


def test_report_contains_components():
    report = generate(SAMPLE_RESULTS, 'circuit.txt', 4)
    assert 'R1' in report
    assert 'C1' in report


def test_report_contains_group_count():
    report = generate(SAMPLE_RESULTS, 'circuit.txt', 4)
    assert 'Groupes identifiés : 2' in report


def test_report_contains_total_components():
    report = generate(SAMPLE_RESULTS, 'circuit.txt', 4)
    assert 'Composants totaux : 4' in report


def test_report_lists_unclassified_components():
    results = [{'circuit_type': 'Filtre RC passe-bas', 'components': ['R1', 'C1'], 'nodes': ['A', 'B', 'GND']}]
    all_refs = ['R1', 'C1', 'U1', 'Q1']
    report = generate(results, 'circuit.txt', 4, all_refs=all_refs)
    assert 'U1' in report
    assert 'Q1' in report
