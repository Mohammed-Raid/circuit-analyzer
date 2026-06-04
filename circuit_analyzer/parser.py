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
    seen_refs: set[str] = set()

    with open(path, encoding='utf-8') as f:
        for line_no, raw_line in enumerate(f, 1):
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()

            ref = parts[0]

            # Point 3: duplicate reference detection
            if ref in seen_refs:
                raise ValueError(
                    f"Référence dupliquée '{ref}' — ligne {line_no}: {repr(line)}"
                )
            seen_refs.add(ref)

            comp_type = _infer_type(ref, library)
            pin_names = library.get(comp_type, {}).get('pins', ['1', '2'])
            n_pins = len(pin_names)

            raw_nets = parts[1:1 + n_pins]

            # Point 2: dimensional validation
            if len(raw_nets) < n_pins:
                raise ValueError(
                    f"Composant '{ref}' ({comp_type}) attend {n_pins} nœud(s) "
                    f"mais {len(raw_nets)} trouvé(s) — ligne {line_no}: {repr(line)}"
                )

            # Point 1: lexical normalization (case + spaces)
            nets = [n.upper().replace(' ', '') for n in raw_nets]

            value = parts[1 + n_pins] if len(parts) > 1 + n_pins else ''
            pins = dict(zip(pin_names, nets))

            components.append(Component(ref=ref, type=comp_type, pins=pins, value=value))
    return components
