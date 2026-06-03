from dataclasses import dataclass


@dataclass
class Component:
    ref: str
    type: str
    net1: str
    net2: str
    value: str = ''


def parse_file(path: str) -> list[Component]:
    components = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            ref = parts[0]
            net1 = parts[1]
            net2 = parts[2]
            value = parts[3] if len(parts) > 3 else ''
            comp_type = ref[0].upper()
            components.append(Component(ref=ref, type=comp_type, net1=net1, net2=net2, value=value))
    return components
