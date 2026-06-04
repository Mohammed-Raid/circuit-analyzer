from circuit_analyzer.patterns.base import Pattern, is_gnd, is_power


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


class HighSideMosfet(Pattern):
    """MOSFET haute-tension (source non reliée à la masse) avec résistance de grille."""
    name = "MOSFET haute-tension (high-side)"

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
            # High-side: source NOT at GND (already matched by MosfetSwitch)
            if is_gnd(source):
                continue
            # Drain must be at a power rail (high-side switch)
            if not is_power(drain):
                continue
            r_at_gate = [d['ref'] for u, v, d in graph.edges(gate, data=True) if d['type'] == 'R']
            if r_at_gate:
                matches.append({
                    'components': [m_ref] + r_at_gate,
                    'nodes': [gate, drain, source],
                })
        return matches


class RelayDriver(Pattern):
    """Commande de relais — bobine K alimentée par transistor (BJT ou MOSFET) en commutation."""
    name = "Commande de relais"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        seen = set()

        # Find all relay coils
        relays = [(ref, comp) for ref, comp in components.items() if comp.type == 'K']

        for k_ref, k_comp in relays:
            a1 = k_comp.pins.get('A1')
            a2 = k_comp.pins.get('A2')
            if not a1 or not a2:
                continue

            # Determine which coil terminal is the switch node (collector/drain)
            # Case A: A1=power rail, A2=switch node (collector/drain to GND)
            # Case B: A1=switch node, A2=GND (collector/drain from power)
            if is_power(a1) and not is_power(a2) and not is_gnd(a2):
                sw_node = a2
            elif is_gnd(a2) and not is_gnd(a1) and not is_power(a1):
                sw_node = a1
            else:
                continue

            # Find transistor (BJT collector or MOSFET drain) at sw_node with emitter/source at GND
            transistors = []
            for ref2, comp2 in components.items():
                if comp2.type == 'Q':
                    collector = comp2.pins.get('C')
                    emitter = comp2.pins.get('E')
                    if collector == sw_node and is_gnd(emitter):
                        transistors.append(ref2)
                elif comp2.type == 'M':
                    drain = comp2.pins.get('D')
                    source = comp2.pins.get('S')
                    if drain == sw_node and is_gnd(source):
                        transistors.append(ref2)

            if not transistors:
                continue

            key = frozenset([k_ref] + transistors)
            if key in seen:
                continue
            seen.add(key)
            # Nodes: coil supply → switch node (avoid duplicating sw_node = a1 or a2)
            nodes = [a1, sw_node] if sw_node != a1 else [sw_node, a2]
            matches.append({
                'components': [k_ref] + transistors,
                'nodes': nodes,
            })
        return matches


TRANSISTOR_PATTERNS = [
    TransistorSwitch(),
    CommonEmitterAmp(),
    CurrentMirror(),
    MosfetSwitch(),
    HighSideMosfet(),
    RelayDriver(),
]
