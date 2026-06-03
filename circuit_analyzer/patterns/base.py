from abc import ABC, abstractmethod
import re
import networkx as nx


def is_gnd(net: str) -> bool:
    net_upper = net.upper()
    if net_upper == '0':
        return True
    GND_PREFIXES = {'GND', 'AGND', 'DGND', 'VSS', 'V-'}
    return any(g in net_upper for g in GND_PREFIXES)


def is_power(net: str) -> bool:
    net_upper = net.upper()
    POWER_EXACT = {'VCC', 'VDD', 'AVCC', 'AVDD', 'DVCC', 'VIN', 'VBAT', 'PWR', 'V+'}
    if net_upper in POWER_EXACT:
        return True
    # Match as prefix followed by digit, underscore, or end (e.g. VCC_3V3, VDD1)
    return bool(re.match(r'^(VCC|VDD|AVCC|AVDD|DVCC|VIN|VBAT|PWR)[\d_]', net_upper))


class Pattern(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def match(self, graph: nx.MultiGraph) -> list[dict]:
        """
        Returns list of matches.
        Each match: {'components': [ref, ...], 'nodes': [net, ...]}
        """
        pass
