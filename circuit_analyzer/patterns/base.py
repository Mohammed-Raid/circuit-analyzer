from abc import ABC, abstractmethod
import re
import networkx as nx


def is_gnd(net: str) -> bool:
    # Strip KiCad hierarchy prefix (e.g. /PGND → PGND, /GND_AOP → GND_AOP)
    net_upper = net.lstrip('/').upper()
    if net_upper == '0':
        return True
    GND_EXACT = {'GND', 'AGND', 'DGND', 'PGND', 'VSS', 'V-'}
    if net_upper in GND_EXACT:
        return True
    return bool(re.match(r'^(GND|AGND|DGND|PGND|VSS)[\d_]', net_upper))


def is_power(net: str) -> bool:
    # Strip KiCad hierarchy prefix (e.g. /VCC_AOP → VCC_AOP)
    net_upper = net.lstrip('/').upper()
    POWER_EXACT = {'VCC', 'VDD', 'AVCC', 'AVDD', 'DVCC', 'VIN', 'VBAT', 'PWR', 'V+', 'VMOT', 'VBUS',
                   'VLOOP', 'VREG', 'VRAW', 'VSUPPLY', 'VPWR', 'VSYS'}
    if net_upper in POWER_EXACT:
        return True
    return bool(re.match(
        r'^(VCC|VDD|AVCC|AVDD|DVCC|VIN|VBAT|PWR|VOUT|VMOT|VBUS|VLOOP|VREG|VRAW|VSUPPLY|VPWR|VSYS)[\d_]',
        net_upper
    ))


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
