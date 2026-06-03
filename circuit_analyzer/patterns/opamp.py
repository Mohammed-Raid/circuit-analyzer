from circuit_analyzer.patterns.base import Pattern, is_gnd


class InvertingAmplifier(Pattern):
    name = "Amplificateur inverseur (AOP)"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for u_ref, comp in components.items():
            if comp.type != 'U':
                continue
            inm = comp.pins.get('IN-')
            out = comp.pins.get('OUT')
            if not all([inm, out]):
                continue
            r_at_inm = [
                (d['ref'], v if u == inm else u)
                for u, v, d in graph.edges(inm, data=True)
                if d['type'] == 'R'
            ]
            feedback_r = [r for r, other in r_at_inm if other == out]
            input_r = [r for r, other in r_at_inm if other != out]
            if feedback_r and input_r:
                matches.append({
                    'components': [u_ref] + feedback_r + input_r,
                    'nodes': [comp.pins.get('IN+', ''), inm, out],
                })
        return matches


class NonInvertingAmplifier(Pattern):
    name = "Amplificateur non-inverseur (AOP)"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for u_ref, comp in components.items():
            if comp.type != 'U':
                continue
            inm = comp.pins.get('IN-')
            out = comp.pins.get('OUT')
            if not all([inm, out]):
                continue
            r_at_inm = [
                (d['ref'], v if u == inm else u)
                for u, v, d in graph.edges(inm, data=True)
                if d['type'] == 'R'
            ]
            feedback_r = [r for r, other in r_at_inm if other == out]
            gnd_r = [r for r, other in r_at_inm if is_gnd(other)]
            if feedback_r and gnd_r:
                matches.append({
                    'components': [u_ref] + feedback_r + gnd_r,
                    'nodes': [comp.pins.get('IN+', ''), inm, out],
                })
        return matches


class VoltageFollower(Pattern):
    name = "Suiveur de tension (AOP)"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for u_ref, comp in components.items():
            if comp.type != 'U':
                continue
            inm = comp.pins.get('IN-')
            out = comp.pins.get('OUT')
            if inm and out and inm == out:
                matches.append({
                    'components': [u_ref],
                    'nodes': [comp.pins.get('IN+', ''), out],
                })
        return matches


class Integrator(Pattern):
    name = "Intégrateur (AOP)"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for u_ref, comp in components.items():
            if comp.type != 'U':
                continue
            inm = comp.pins.get('IN-')
            out = comp.pins.get('OUT')
            if not inm or not out:
                continue
            r_input = []
            c_feedback = []
            for u, v, d in graph.edges(inm, data=True):
                other = v if u == inm else u
                if d['type'] == 'R' and other != out:
                    r_input.append(d['ref'])
                elif d['type'] == 'C' and other == out:
                    c_feedback.append(d['ref'])
            if r_input and c_feedback:
                matches.append({
                    'components': [u_ref] + r_input + c_feedback,
                    'nodes': [comp.pins.get('IN+', ''), inm, out],
                })
        return matches


class Comparator(Pattern):
    name = "Comparateur (AOP)"

    def match(self, graph):
        components = graph.graph.get('components', {})
        matches = []
        for u_ref, comp in components.items():
            if comp.type != 'U':
                continue
            inm = comp.pins.get('IN-')
            inp = comp.pins.get('IN+')
            out = comp.pins.get('OUT')
            if not all([inm, inp, out]):
                continue
            if inm == out:
                continue
            feedback = [
                d for u, v, d in graph.edges(inm, data=True)
                if d['type'] in ('R', 'C') and (v if u == inm else u) == out
            ]
            if not feedback:
                matches.append({
                    'components': [u_ref],
                    'nodes': [inp, inm, out],
                })
        return matches


OPAMP_PATTERNS = [
    InvertingAmplifier(),
    NonInvertingAmplifier(),
    VoltageFollower(),
    Integrator(),
    Comparator(),
]
