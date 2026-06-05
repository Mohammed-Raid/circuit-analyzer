"""Parser for BoardSCH XML schematic files."""
import xml.etree.ElementTree as ET
from .parser import Component

# XML component Name → (type_prefix, {Pname: library_pin_name})
_COMP_MAP: dict[str, tuple[str, dict[str, str]]] = {
    'Résistance':   ('R', {'1': '1', '2': '2'}),
    'Resistance':   ('R', {'1': '1', '2': '2'}),
    'Capa':         ('C', {'+': '1', '-': '2'}),
    'Condensateur': ('C', {'+': '1', '-': '2'}),
    'AOP':          ('U', {'+': 'IN+', '-': 'IN-', 's': 'OUT'}),
    'Bobine':       ('L', {'1': '1', '2': '2'}),
    'Inductance':   ('L', {'1': '1', '2': '2'}),
    'Diode':        ('D', {'A': 'A', 'K': 'K', '1': 'A', '2': 'K'}),
    'Transistor':   ('Q', {'B': 'B', 'C': 'C', 'E': 'E'}),
    'MOSFET':       ('M', {'G': 'G', 'D': 'D', 'S': 'S'}),
    'Relais':       ('K', {'A1': 'A1', 'A2': 'A2', '11': '11', '12': '12', '14': '14'}),
    'Fusible':      ('F', {'1': '1', '2': '2'}),
}

# Component names that are power/ground symbols (not real components)
_POWER_NAMES = {
    'GND', 'AGND', 'PGND', 'DGND',
    'VCC', 'VDD', 'VSS', 'Vss', 'Vdd', 'Vcc',
    'VBUS', 'VMOT', 'VREG', 'VREF', 'VOUT',
    '+5V', '+3.3V', '+12V', '-12V',
}


def _parse_node_ref(nid: str) -> tuple[int, int]:
    """Parse a node reference 'compId_pinIdx_...' and return (compId, pinIdx)."""
    parts = nid.split('_')
    return int(parts[0]), int(parts[1])


def parse_xml(path: str) -> list[Component]:
    """Parse a BoardSCH XML file and return a list of Component objects."""
    tree = ET.parse(path)
    root = tree.getroot()

    # ── Step 1: Extract all DataItems ─────────────────────────────────────────
    items: dict[int, dict] = {}
    for item in root.findall('.//CmpntL/DataItem'):
        comp_id = int(item.findtext('id') or '0')
        name    = (item.findtext('Name') or '').strip()
        value   = (item.findtext('value') or '').strip()

        pins = []
        for dp in item.findall('.//datapin/DataPin'):
            pname = (dp.findtext('Pname') or '').strip()
            pins.append({'pname': pname})

        items[comp_id] = {'id': comp_id, 'name': name, 'value': value, 'pins': pins}

    # ── Step 2: Union-Find on (compId, pinIdx) pairs via lineL wires ──────────
    parent: dict[tuple, tuple] = {}

    def find(x):
        if x not in parent:
            parent[x] = x
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Initialise every pin as its own set
    for cid, comp in items.items():
        for pidx in range(len(comp['pins'])):
            find((cid, pidx))

    # Connect pins based on wires
    for line in root.findall('.//lineL/Line'):
        cf = (line.findtext('CFirst') or '').strip()
        cl = (line.findtext('CLast')  or '').strip()
        if cf and cl:
            union(_parse_node_ref(cf), _parse_node_ref(cl))

    # ── Step 3: Group pins into nets ──────────────────────────────────────────
    net_groups: dict[tuple, list] = {}
    for cid, comp in items.items():
        for pidx in range(len(comp['pins'])):
            root_key = find((cid, pidx))
            net_groups.setdefault(root_key, []).append((cid, pidx))

    # ── Step 4: Name the nets ─────────────────────────────────────────────────
    root_to_net: dict[tuple, str] = {}
    _counter = [0]

    def get_net(root_key: tuple) -> str:
        if root_key in root_to_net:
            return root_to_net[root_key]
        for (cid, _) in net_groups.get(root_key, []):
            cname = items[cid]['name']
            if cname in ('GND', 'AGND', 'PGND', 'DGND'):
                root_to_net[root_key] = 'GND'
                return 'GND'
            if cname in ('VCC', 'Vcc', '+5V', '+3.3V', '+12V'):
                root_to_net[root_key] = 'VCC'
                return 'VCC'
            if cname in ('VDD', 'Vdd'):
                root_to_net[root_key] = 'VDD'
                return 'VDD'
            if cname in ('VSS', 'Vss'):
                root_to_net[root_key] = 'VSS'
                return 'VSS'
        _counter[0] += 1
        name = f'NET{_counter[0]}'
        root_to_net[root_key] = name
        return name

    pin_net: dict[tuple, str] = {}
    for root_key, members in net_groups.items():
        net = get_net(root_key)
        for key in members:
            pin_net[key] = net

    # ── Step 5: Build Component objects ───────────────────────────────────────
    components: list[Component] = []
    ref_counters: dict[str, int] = {}

    for cid in sorted(items):
        comp = items[cid]
        name = comp['name']

        if name in _POWER_NAMES:
            continue
        if name not in _COMP_MAP:
            continue

        type_prefix, pname_map = _COMP_MAP[name]

        ref_counters[type_prefix] = ref_counters.get(type_prefix, 0) + 1
        ref = f'{type_prefix}{ref_counters[type_prefix]}'

        pins: dict[str, str] = {}
        for pidx, pin_info in enumerate(comp['pins']):
            pname    = pin_info['pname']
            lib_pin  = pname_map.get(pname, pname)
            net      = pin_net.get((cid, pidx), 'NC')
            pins[lib_pin] = net

        # Ensure U (op-amp) has all standard pins
        if type_prefix == 'U':
            for std in ('IN+', 'IN-', 'OUT', 'V+', 'V-'):
                pins.setdefault(std, 'NC')

        components.append(Component(ref=ref, type=type_prefix, pins=pins, value=comp['value']))

    return components
