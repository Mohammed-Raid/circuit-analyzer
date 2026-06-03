from itertools import combinations
import networkx as nx
from circuit_analyzer.patterns.base import Pattern, is_gnd, is_power


class RCLowPassFilter(Pattern):
    name = "Filtre RC passe-bas"

    def match(self, graph):
        matches = []
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
                        matches.append({'components': [r_ref, c_ref], 'nodes': [r_other, node, c_other]})
        return matches


class RCHighPassFilter(Pattern):
    name = "Filtre RC passe-haut"

    def match(self, graph):
        matches = []
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
                        matches.append({'components': [r_ref, c_ref], 'nodes': [c_other, node, r_other]})
        return matches


class LCFilter(Pattern):
    name = "Filtre LC"

    def match(self, graph):
        matches = []
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
        dg = nx.Graph()
        diode_map = {}
        for u, v, data in graph.edges(data=True):
            if data['type'] == 'D' and not dg.has_edge(u, v):
                dg.add_edge(u, v)
                diode_map[tuple(sorted([u, v]))] = data['ref']

        matches = []
        for combo in combinations(dg.nodes(), 4):
            sub = dg.subgraph(combo)
            if sub.number_of_edges() == 4 and all(sub.degree(n) == 2 for n in combo):
                refs = [diode_map[tuple(sorted([u, v]))] for u, v in sub.edges()]
                matches.append({'components': refs, 'nodes': list(combo)})
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
            for u, v, data in graph.edges(node, data=True):
                other = v if u == node else u
                pair = tuple(sorted([node, other]))
                if pair in seen:
                    continue
                seen.add(pair)
                between = [(d['ref'], d['type']) for a, b, d in graph.edges(data=True)
                           if {a, b} == {node, other}]
                r_refs = [ref for ref, t in between if t == 'R']
                c_refs = [ref for ref, t in between if t == 'C']
                if r_refs and c_refs:
                    matches.append({'components': r_refs + c_refs, 'nodes': list(pair)})
        return matches


ALL_PATTERNS = [
    RCLowPassFilter(),
    RCHighPassFilter(),
    LCFilter(),
    VoltageDivider(),
    DecouplingCapacitor(),
    BridgeRectifier(),
    FuseProtection(),
    RCSnubber(),
]
