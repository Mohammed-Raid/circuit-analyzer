COMPONENT_TYPES = {
    'R':  {'name': 'Résistance',       'pins': ['1', '2']},
    'C':  {'name': 'Condensateur',     'pins': ['1', '2']},
    'L':  {'name': 'Inductance',       'pins': ['1', '2']},
    'D':  {'name': 'Diode',            'pins': ['A', 'K']},
    'F':  {'name': 'Fusible',          'pins': ['1', '2']},
    'Q':  {'name': 'Transistor BJT',   'pins': ['B', 'C', 'E']},
    'M':  {'name': 'MOSFET',           'pins': ['G', 'D', 'S']},
    'U':  {'name': 'Circuit intégré',  'pins': ['IN+', 'IN-', 'OUT', 'V+', 'V-']},
    'T':  {'name': 'Transformateur',   'pins': ['P1', 'P2', 'S1', 'S2']},
    'K':  {'name': 'Relais',           'pins': ['A1', 'A2', '11', '12', '14']},
    'SW': {'name': 'Interrupteur',     'pins': ['1', '2']},
}
