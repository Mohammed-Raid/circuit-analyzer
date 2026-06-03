from abc import ABC, abstractmethod
import networkx as nx


GND_NETS = {'GND', 'AGND', 'DGND', '0', 'VSS', 'V-'}
POWER_NETS = {'VCC', 'VDD', 'AVCC', 'AVDD', 'DVCC', 'VIN', 'VBAT', 'PWR', 'V+'}


def is_gnd(net: str) -> bool:
    return net.upper() in GND_NETS or any(g in net.upper() for g in GND_NETS)


def is_power(net: str) -> bool:
    return net.upper() in POWER_NETS or any(p in net.upper() for p in POWER_NETS)


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
