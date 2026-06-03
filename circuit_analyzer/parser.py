from dataclasses import dataclass


@dataclass
class Component:
    ref: str
    type: str
    pins: dict[str, str]
    value: str = ''

    @property
    def net1(self) -> str:
        return list(self.pins.values())[0] if self.pins else ''

    @property
    def net2(self) -> str:
        vals = list(self.pins.values())
        return vals[1] if len(vals) > 1 else ''


def _infer_type(ref: str, library: dict) -> str:
    for length in range(min(3, len(ref)), 0, -1):
        prefix = ref[:length].upper()
        if prefix in library:
            return prefix
    return ref[0].upper()


def parse_file(path: str, library: dict = None) -> list[Component]:
    from circuit_analyzer.component_library.loader import load_library
    if library is None:
        library = load_library()

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
            comp_type = _infer_type(ref, library)
            pin_names = library.get(comp_type, {}).get('pins', ['1', '2'])
            n_pins = len(pin_names)

            nets = parts[1:1 + n_pins]
            if len(nets) < n_pins:
                continue

            value = parts[1 + n_pins] if len(parts) > 1 + n_pins else ''
            pins = dict(zip(pin_names, nets))

            components.append(Component(ref=ref, type=comp_type, pins=pins, value=value))
    return components
