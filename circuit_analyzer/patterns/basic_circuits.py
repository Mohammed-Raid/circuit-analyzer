import networkx as nx
from circuit_analyzer.patterns.base import Pattern, is_gnd, is_power


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
        for u, v, data in graph.edges(data=True):
            if data['type'] != 'D':
                continue
            for output_node in (u, v):
                for ou, ov, od in graph.edges(output_node, data=True):
                    if od['ref'] == data['ref']:
                        continue
                    other = ov if ou == output_node else ou
                    if od['type'] == 'R' and is_gnd(other):
                        key = frozenset([data['ref'], od['ref']])
                        if key not in seen:
                            seen.add(key)
                            matches.append({
                                'components': [data['ref'], od['ref']],
                                'nodes': [u, v, other],
                            })
        return matches


class PeakDetector(Pattern):
    name = "Détecteur de crête"

    def match(self, graph):
        matches = []
        seen = set()
        for u, v, data in graph.edges(data=True):
            if data['type'] != 'D':
                continue
            for output_node in (u, v):
                for ou, ov, od in graph.edges(output_node, data=True):
                    if od['ref'] == data['ref']:
                        continue
                    other = ov if ou == output_node else ou
                    if od['type'] == 'C' and is_gnd(other):
                        key = frozenset([data['ref'], od['ref']])
                        if key not in seen:
                            seen.add(key)
                            matches.append({
                                'components': [data['ref'], od['ref']],
                                'nodes': [u, v, other],
                            })
        return matches


ALL_PATTERNS = [
    RCLowPassFilter(),
    RCHighPassFilter(),
    LCFilter(),
    VoltageDivider(),
    DecouplingCapacitor(),
    BridgeRectifier(),
    HalfWaveRectifier(),
    PeakDetector(),
    FuseProtection(),
    RCSnubber(),
]
