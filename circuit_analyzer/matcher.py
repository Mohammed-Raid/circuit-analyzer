import networkx as nx
from circuit_analyzer.patterns.opamp import (
    DifferentialAmplifier, SummingAmplifier, Integrator, Differentiator,
    SchmittTrigger, NonInvertingAmplifier, InvertingAmplifier,
    VoltageFollower, Comparator,
)
from circuit_analyzer.patterns.transistor import (
    CurrentMirror, CommonEmitterAmp, TransistorSwitch, MosfetSwitch,
    HighSideMosfet, RelayDriver,
)
from circuit_analyzer.patterns.basic_circuits import (
    BridgeRectifier, HalfWaveRectifier, PeakDetector,
    RCSnubber, RCLowPassFilter, RCHighPassFilter, LCFilter,
    VoltageDivider, DecouplingCapacitor, FuseProtection, FlybackDiode,
    ESDProtectionDiode,
)

# Point 4: ordered from most specific (AOP) to least specific (isolated).
# More specific patterns are evaluated first; once a component is locked by a
# high-priority match it cannot be claimed by a lower-priority pattern.
_BUILTIN_HIGH = [
    # AOP — ordered by structural specificity (most constrained first)
    DifferentialAmplifier(),
    SummingAmplifier(),
    Integrator(),
    Differentiator(),
    SchmittTrigger(),
    NonInvertingAmplifier(),
    InvertingAmplifier(),
    VoltageFollower(),
    Comparator(),
    # Transistors — ordered most constrained first
    CurrentMirror(),
    RelayDriver(),
    CommonEmitterAmp(),
    TransistorSwitch(),
    MosfetSwitch(),
    HighSideMosfet(),
    # Complex passive
    BridgeRectifier(),
    FlybackDiode(),
    ESDProtectionDiode(),
    HalfWaveRectifier(),
    PeakDetector(),
]

_BUILTIN_LOW = [
    # Simple passive — evaluated after all complex structures.
    # DecouplingCapacitor before RCSnubber: power-rail caps must be locked first
    # so that the snubber doesn't absorb decoupling caps alongside a signal resistor.
    DecouplingCapacitor(),
    RCSnubber(),
    RCLowPassFilter(),
    RCHighPassFilter(),
    LCFilter(),
    VoltageDivider(),
    FuseProtection(),
]


def match_patterns(graph: nx.MultiGraph) -> list[dict]:
    try:
        from custom_circuits.loader import get_custom_patterns
        custom = get_custom_patterns()
    except Exception:
        custom = []

    # Custom patterns evaluated between complex and simple passive
    ordered = _BUILTIN_HIGH + custom + _BUILTIN_LOW

    locked: set[str] = set()
    results = []

    for pattern in ordered:
        for match in pattern.match(graph):
            # Point 4: skip if any component already consumed by a higher-priority match
            if any(c in locked for c in match['components']):
                continue
            locked.update(match['components'])
            results.append({
                'circuit_type': pattern.name,
                'components': match['components'],
                'nodes': match['nodes'],
            })

    return results
