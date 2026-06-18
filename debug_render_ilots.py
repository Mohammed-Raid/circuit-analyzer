"""Rendu headless des schemas d'ilots pour inspection visuelle."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

from circuit_analyzer.xml import lire_xml
from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import analyser
import gui.circuit_viewer as cv

xml = sys.argv[1] if len(sys.argv) > 1 else "circuits_industriels/signal_conditioning.xml"
out = Path("build_rebuild/ilots_render")
out.mkdir(parents=True, exist_ok=True)

comps = lire_xml(xml)
g = construire_graphe(comps)
res = analyser(g)
comp_info = {c.ref: {"type": c.type, "value": c.value, "pins": c.pins} for c in comps}

ilots = getattr(res, "ilots", [])
print(f"{xml}: {len(ilots)} ilots")
for i, ilot in enumerate(ilots):
    model = cv._build_island_model(ilot, g, comp_info)
    fig = cv._make_island_fig(model)
    name = ilot.get("label", f"ilot{i}").replace(" ", "_").replace("/", "_")
    path = out / f"{i:02d}_{name}.png"
    fig.savefig(path, dpi=120, facecolor=fig.get_facecolor())
    zs = [u for u in model['components'] if u['type'] == 'Z']
    print(f"  [{i}] {ilot.get('label')!r} -> {path}  ({len(model['components'])} unites, "
          f"{len(zs)} Z)")
