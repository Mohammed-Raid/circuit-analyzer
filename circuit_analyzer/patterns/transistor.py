from circuit_analyzer.patterns.base import Pattern, is_gnd


class TransistorSwitch(Pattern):
    name = "Transistor en commutation"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for q_ref, comp in components.items():
            if comp.type != 'Q':
                continue
            base = comp.pins.get('B')
            collector = comp.pins.get('C')
            emitter = comp.pins.get('E')
            if not all([base, collector, emitter]):
                continue
            if not is_gnd(emitter):
                continue
            r_at_base = [d['ref'] for u, v, d in graph.edges(base, data=True) if d['type'] == 'R']
            if r_at_base:
                matches.append({
                    'components': [q_ref] + r_at_base,
                    'nodes': [base, collector, emitter],
                })
        return matches


class CommonEmitterAmp(Pattern):
    name = "Amplificateur émetteur commun"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for q_ref, comp in components.items():
            if comp.type != 'Q':
                continue
            base = comp.pins.get('B')
            collector = comp.pins.get('C')
            emitter = comp.pins.get('E')
            if not all([base, collector, emitter]):
                continue
            r_at_collector = [d['ref'] for u, v, d in graph.edges(collector, data=True) if d['type'] == 'R']
            r_at_base = [d['ref'] for u, v, d in graph.edges(base, data=True) if d['type'] == 'R']
            if r_at_collector and r_at_base:
                matches.append({
                    'components': [q_ref] + r_at_collector + r_at_base,
                    'nodes': [base, collector, emitter],
                })
        return matches


class CurrentMirror(Pattern):
    name = "Miroir de courant BJT"

    def match(self, graph):
        components = graph.graph.get('components', {})
        bjts = [(ref, comp) for ref, comp in components.items() if comp.type == 'Q']
        matches = []
        seen = set()
        for i in range(len(bjts)):
            for j in range(i + 1, len(bjts)):
                ref1, q1 = bjts[i]
                ref2, q2 = bjts[j]
                base1 = q1.pins.get('B')
                base2 = q2.pins.get('B')
                emitter1 = q1.pins.get('E')
                emitter2 = q2.pins.get('E')
                if not all([base1, base2, emitter1, emitter2]):
                    continue
                if base1 == base2 and is_gnd(emitter1) and is_gnd(emitter2):
                    key = frozenset([ref1, ref2])
                    if key not in seen:
                        seen.add(key)
                        matches.append({
                            'components': [ref1, ref2],
                            'nodes': [base1, q1.pins.get('C', ''), q2.pins.get('C', '')],
                        })
        return matches


class MosfetSwitch(Pattern):
    name = "MOSFET en commutation"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for m_ref, comp in components.items():
            if comp.type != 'M':
                continue
            gate = comp.pins.get('G')
            drain = comp.pins.get('D')
            source = comp.pins.get('S')
            if not all([gate, drain, source]):
                continue
            if not is_gnd(source):
                continue
            r_at_gate = [d['ref'] for u, v, d in graph.edges(gate, data=True) if d['type'] == 'R']
            if r_at_gate:
                matches.append({
                    'components': [m_ref] + r_at_gate,
                    'nodes': [gate, drain, source],
                })
        return matches


TRANSISTOR_PATTERNS = [
    TransistorSwitch(),
    CommonEmitterAmp(),
    CurrentMirror(),
    MosfetSwitch(),
]
