import networkx as nx
from circuit_analyzer.patterns.base import Pattern, is_gnd, is_power


class ESDProtectionDiode(Pattern):
    """Diode de protection ESD / TVS / Zener shunt.
    Covers three sub-topologies:
    - Forward low-side clamp: anode=GND, cathode=signal (prevents negative excursions)
    - Reverse Zener/TVS shunt: anode=GND, cathode=power rail (voltage clamping)
    - Reverse Zener shunt: anode=signal, cathode=GND (clamp above GND)
    """
    name = "Diode de protection ESD"

    def match(self, graph):
        matches = []
        all_comps = graph.graph.get('components', {})
        for d_ref, comp in all_comps.items():
            if comp.type != 'D':
                continue
            anode = comp.pins.get('A') or comp.pins.get('1', '')
            cathode = comp.pins.get('K') or comp.pins.get('2', '')
            if not anode or not cathode:
                continue
            # Anode at GND: forward clamp (negative) or reverse Zener shunt (positive)
            if is_gnd(anode):
                matches.append({'components': [d_ref], 'nodes': [anode, cathode]})
            # Anode at signal or power, cathode at GND: Zener/TVS shunt or reverse protection
            elif is_gnd(cathode):
                matches.append({'components': [d_ref], 'nodes': [anode, cathode]})
        return matches


class FlybackDiode(Pattern):
    """Diode de roue libre — cathode on power rail, anode at switch output node."""
    name = "Diode de roue libre"

    def match(self, graph):
        matches = []
        all_comps = graph.graph.get('components', {})
        for d_ref, comp in all_comps.items():
            if comp.type != 'D':
                continue
            cathode = comp.pins.get('K')
            anode = comp.pins.get('A')
            if not cathode or not anode:
                continue
            # Flyback: cathode at power rail, anode at switch node (not GND, not power)
            if is_power(cathode) and not is_gnd(anode) and not is_power(anode):
                matches.append({
                    'components': [d_ref],
                    'nodes': [anode, cathode],
                })
        return matches


class RCLowPassFilter(Pattern):
    name = "Filtre RC passe-bas"

    def match(self, graph):
        matches = []
        seen = set()
        for node in graph.nodes():
            r_edges, c_edges = [], []
            for u, v, data in graph.edges(node, data=True):
                other = v if u == node else u
                if data['type'] == 'R':
                    r_edges.append((other, data['ref']))
                elif data['type'] == 'C':
                    c_edges.append((other, data['ref']))
            for r_other, r_ref in r_edges:
                for c_other, c_ref in c_edges:
                    if is_gnd(c_other):
                        key = frozenset([r_ref, c_ref])
                        if key not in seen:
                            seen.add(key)
                            matches.append({'components': [r_ref, c_ref], 'nodes': [r_other, node, c_other]})
        return matches


class RCHighPassFilter(Pattern):
    name = "Filtre RC passe-haut"

    def match(self, graph):
        matches = []
        seen = set()
        for node in graph.nodes():
            r_edges, c_edges = [], []
            for u, v, data in graph.edges(node, data=True):
                other = v if u == node else u
                if data['type'] == 'R':
                    r_edges.append((other, data['ref']))
                elif data['type'] == 'C':
                    c_edges.append((other, data['ref']))
            for r_other, r_ref in r_edges:
                if is_gnd(r_other):
                    for c_other, c_ref in c_edges:
                        key = frozenset([r_ref, c_ref])
                        if key not in seen:
                            seen.add(key)
                            matches.append({'components': [r_ref, c_ref], 'nodes': [c_other, node, r_other]})
        return matches


class LCFilter(Pattern):
    name = "Filtre LC"

    def match(self, graph):
        matches = []
        seen = set()
        for node in graph.nodes():
            l_edges, c_edges = [], []
            for u, v, data in graph.edges(node, data=True):
                other = v if u == node else u
                if data['type'] == 'L':
                    l_edges.append((other, data['ref']))
                elif data['type'] == 'C':
                    c_edges.append((other, data['ref']))
            for l_other, l_ref in l_edges:
                for c_other, c_ref in c_edges:
                    if is_gnd(c_other):
                        key = frozenset([l_ref, c_ref])
                        if key not in seen:
                            seen.add(key)
                            matches.append({'components': [l_ref, c_ref], 'nodes': [l_other, node, c_other]})
        return matches


class VoltageDivider(Pattern):
    name = "Pont diviseur de tension"

    def match(self, graph):
        matches = []
        seen = set()
        for node in graph.nodes():
            r_edges = []
            for u, v, data in graph.edges(node, data=True):
                other = v if u == node else u
                if data['type'] == 'R':
                    r_edges.append((other, data['ref']))
            for i in range(len(r_edges)):
                for j in range(i + 1, len(r_edges)):
                    other1, ref1 = r_edges[i]
                    other2, ref2 = r_edges[j]
                    if other1 == other2:
                        continue
                    key = frozenset([ref1, ref2])
                    if key not in seen:
                        seen.add(key)
                        matches.append({'components': [ref1, ref2], 'nodes': [other1, node, other2]})
        return matches


class DecouplingCapacitor(Pattern):
    name = "Condensateur de découplage"

    def match(self, graph):
        matches = []
        for u, v, data in graph.edges(data=True):
            if data['type'] != 'C':
                continue
            if (is_power(u) and is_gnd(v)) or (is_gnd(u) and is_power(v)):
                matches.append({'components': [data['ref']], 'nodes': [u, v]})
        return matches


class BridgeRectifier(Pattern):
    name = "Pont redresseur (Graetz)"

    def match(self, graph):
        # Build diode adjacency: node -> list of (neighbor, ref)
        diode_adj = {}
        for u, v, data in graph.edges(data=True):
            if data['type'] != 'D':
                continue
            if u not in diode_adj:
                diode_adj[u] = []
            if v not in diode_adj:
                diode_adj[v] = []
            diode_adj[u].append((v, data['ref']))
            diode_adj[v].append((u, data['ref']))

        matches = []
        seen_cycles = set()

        for n1, n1_neighbors in diode_adj.items():
            for n2, d1_ref in n1_neighbors:
                if n2 == n1:
                    continue
                for n3, d2_ref in diode_adj.get(n2, []):
                    if n3 in (n1, n2):
                        continue
                    for n4, d3_ref in diode_adj.get(n3, []):
                        if n4 in (n1, n2, n3):
                            continue
                        # Check if n4 connects back to n1
                        for n1_check, d4_ref in diode_adj.get(n4, []):
                            if n1_check == n1 and len({d1_ref, d2_ref, d3_ref, d4_ref}) == 4:
                                cycle_nodes = {n1, n2, n3, n4}
                                # Exclude ESD clamp arrays: those have BOTH a power rail AND a GND
                                # rail in the 4-node cycle (two clamp rails + two signal nodes).
                                # A real bridge rectifier has at most one rail type in its cycle.
                                has_pwr = any(is_power(n) for n in cycle_nodes)
                                has_gnd = any(is_gnd(n) for n in cycle_nodes)
                                if has_pwr and has_gnd:
                                    continue
                                cycle_key = frozenset([d1_ref, d2_ref, d3_ref, d4_ref])
                                if cycle_key not in seen_cycles:
                                    seen_cycles.add(cycle_key)
                                    matches.append({
                                        'components': [d1_ref, d2_ref, d3_ref, d4_ref],
                                        'nodes': [n1, n2, n3, n4]
                                    })
        return matches


class FuseProtection(Pattern):
    name = "Protection par fusible"

    def match(self, graph):
        matches = []
        for u, v, data in graph.edges(data=True):
            if data['type'] == 'F':
                matches.append({'components': [data['ref']], 'nodes': [u, v]})
        return matches


class RCSnubber(Pattern):
    name = "Snubber RC"

    def match(self, graph):
        matches = []
        seen = set()
        for node in graph.nodes():
            for neighbor in graph.neighbors(node):
                pair = tuple(sorted([node, neighbor]))
                if pair in seen:
                    continue
                seen.add(pair)
                parallel = list(graph[node][neighbor].values())
                r_refs = [d['ref'] for d in parallel if d['type'] == 'R']
                c_refs = [d['ref'] for d in parallel if d['type'] == 'C']
                if r_refs and c_refs:
                    matches.append({'components': r_refs + c_refs, 'nodes': list(pair)})
        return matches


class HalfWaveRectifier(Pattern):
    name = "Redresseur simple alternance"

    def match(self, graph):
        matches = []
        seen = set()
        all_comps = graph.graph.get('components', {})
        for d_ref, comp in all_comps.items():
            if comp.type != 'D':
                continue
            anode = comp.pins.get('A') or comp.pins.get('1', '')
            # Only the cathode (K) is the DC output — never match the anode side
            cathode = comp.pins.get('K') or comp.pins.get('2', '')
            if not cathode or not anode:
                continue
            # Exclude flyback diodes: cathode on a power rail means this is not a rectifier
            if is_power(cathode):
                continue
            # Exclude reverse-polarity ESD clamps and GND-anode diodes
            if is_gnd(anode):
                continue
            # Exclude always-forward-biased diodes: anode on a power rail (e.g. LED indicators)
            if is_power(anode):
                continue
            for ou, ov, od in graph.edges(cathode, data=True):
                if od['ref'] == d_ref:
                    continue
                other = ov if ou == cathode else ou
                if od['type'] == 'R' and is_gnd(other):
                    key = frozenset([d_ref, od['ref']])
                    if key not in seen:
                        seen.add(key)
                        matches.append({
                            'components': [d_ref, od['ref']],
                            'nodes': [anode, cathode, other],
                        })
        return matches


class PeakDetector(Pattern):
    name = "Détecteur de crête"

    def match(self, graph):
        matches = []
        seen = set()
        all_comps = graph.graph.get('components', {})
        for d_ref, comp in all_comps.items():
            if comp.type != 'D':
                continue
            anode = comp.pins.get('A') or comp.pins.get('1', '')
            # Only the cathode (K) is the peak-hold node — never match the anode side
            cathode = comp.pins.get('K') or comp.pins.get('2', '')
            if not cathode or not anode:
                continue
            # Exclude flyback diodes: cathode on a power rail means this is not a peak detector
            if is_power(cathode):
                continue
            # Exclude reverse-polarity ESD clamps: anode at GND means this clamps below GND
            if is_gnd(anode):
                continue
            for ou, ov, od in graph.edges(cathode, data=True):
                if od['ref'] == d_ref:
                    continue
                other = ov if ou == cathode else ou
                if od['type'] == 'C' and is_gnd(other):
                    key = frozenset([d_ref, od['ref']])
                    if key not in seen:
                        seen.add(key)
                        matches.append({
                            'components': [d_ref, od['ref']],
                            'nodes': [anode, cathode, other],
                        })
        return matches


ALL_PATTERNS = [
    RCSnubber(),
    DecouplingCapacitor(),   # must precede RCLowPassFilter (power-rail caps)
    RCLowPassFilter(),
    RCHighPassFilter(),
    LCFilter(),
    BridgeRectifier(),
    FlybackDiode(),
    ESDProtectionDiode(),
    HalfWaveRectifier(),
    PeakDetector(),
    VoltageDivider(),
    FuseProtection(),
]
