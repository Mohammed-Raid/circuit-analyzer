"""
@file render_ilots_v2.py
@brief Rendu de controle bimode des fenetres ilots v2.

Usage:
  python tools/render_ilots_v2.py

Genere les PNG Z et detaille sous tools/_renders/ilots_v2/{z,detaille}/ pour:
  - circuits_industriels/ilot_*.xml
  - circuits_industriels/tr_*.xml
  - circuits_industriels/aop_*.xml

Genere aussi quatre planches de contact pour inspection rapide.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from matplotlib import pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from circuit_analyzer import detecteur  # noqa: E402
from circuit_analyzer.composant import construire_graphe  # noqa: E402
from circuit_analyzer.xml import lire_xml  # noqa: E402
from gui import circuit_viewer as cv  # noqa: E402

OUT = ROOT / "tools" / "_renders" / "ilots_v2"


def _safe_name(text: str) -> str:
    """@brief Nom de fichier portable a partir d'un label d'ilot."""
    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:120]


def _xml_files() -> list[Path]:
    """@brief Fichiers de demo couverts par la boucle visuelle Task 6."""
    ci = ROOT / "circuits_industriels"
    return sorted(
        list(ci.glob("ilot_*.xml"))
        + list(ci.glob("tr_*.xml"))
        + list(ci.glob("aop_*.xml"))
    )


def _fig_for_ilot(ilot, graph, comp_info, results, detaille=False):
    """@brief Reproduit la strategie de rendu de show_island sans ouvrir Tk."""
    model = cv._build_island_model(ilot, graph, comp_info)
    principal = cv._circuit_principal_ilot(ilot, graph, results)
    sp = cv._arbre_serie_parallele_ilot(ilot, graph) if principal is None else None
    pont = cv._pont_ilot(ilot, graph) if principal is None and sp is None else None
    derive = (
        cv._reseau_derive_ilot(ilot, graph)
        if principal is None and sp is None and pont is None
        else None
    )
    deux = (
        cv._reseau_deux_bornes_ilot(ilot, graph)
        if principal is None and sp is None and pont is None and derive is None
        else None
    )
    matches = cv._matches_for_island(ilot, results)

    if principal is not None:
        return cv._make_fig(
            principal,
            comp_info,
            cv._DRAWERS[principal["circuit_type"]],
            matches=matches,
            detaille=detaille,
        )
    if sp is not None:
        from gui import impedance_schematic

        arbre, comps = sp
        return impedance_schematic.dessiner_bloc(
            arbre, "VIN", "VOUT", comps, detaille=detaille
        )
    if pont is not None:
        from gui import impedance_schematic

        pont_struct, comps = pont
        return impedance_schematic.dessiner_pont(
            pont_struct, comps, detaille=detaille
        )
    if derive is not None:
        return cv._make_fig(derive, comp_info, cv._draw_reseau_derive, detaille=detaille)
    if deux is not None:
        from gui import impedance_schematic

        arbre, a, b, comps = deux
        return impedance_schematic.dessiner_bloc(arbre, a, b, comps, detaille=detaille)

    chaine = cv._ordonner_montages_flux(matches, comp_info)
    if chaine is not None:
        return cv._make_chain_fig(
            chaine, comp_info, matches=matches, detaille=detaille
        )

    branches = cv._layers_montages_flux(matches, comp_info)
    if branches is not None:
        return cv._make_branched_fig(
            branches, comp_info, matches=matches, detaille=detaille
        )

    return cv._make_island_fig(model, matches=matches, detaille=detaille)


def render_all() -> int:
    """@brief Rend tous les PNG bimode et retourne leur nombre."""
    for mode in ("z", "detaille"):
        (OUT / mode).mkdir(parents=True, exist_ok=True)

    count = 0
    for path in _xml_files():
        comps = lire_xml(str(path))
        graph = construire_graphe(comps)
        results = detecteur.analyser(graph)
        comp_info = {
            c.ref: {"type": c.type, "value": c.value, "pins": c.pins}
            for c in comps
        }
        for idx, ilot in enumerate(results.ilots):
            label = ilot.get("label") or f"ilot{idx}"
            base = f"{path.stem}__{idx:02d}_{_safe_name(label)}.png"
            for mode, detaille in (("z", False), ("detaille", True)):
                fig = _fig_for_ilot(ilot, graph, comp_info, results, detaille=detaille)
                out = OUT / mode / base
                fig.savefig(
                    out,
                    dpi=150,
                    bbox_inches="tight",
                    facecolor=fig.get_facecolor(),
                )
                plt.close(fig)
                count += 1
    return count


def _make_contact_sheet(mode: str, predicate, out_name: str, thumb_w: int = 420) -> None:
    """@brief Assemble une planche de contact pour inspection rapide."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow absent: planche de contact ignoree")
        return

    files = [p for p in sorted((OUT / mode).glob("*.png")) if predicate(p.name)]
    if not files:
        return

    font = ImageFont.load_default()
    thumbs = []
    for path in files:
        image = Image.open(path).convert("RGB")
        scale = thumb_w / image.width
        size = (thumb_w, max(1, int(image.height * scale)))
        image = image.resize(size, Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (thumb_w, size[1] + 38), "white")
        tile.paste(image, (0, 38))
        ImageDraw.Draw(tile).text(
            (4, 4), f"{mode}: {path.stem[:64]}", fill=(0, 0, 0), font=font
        )
        thumbs.append(tile)

    cols, gap = 2, 12
    rows = (len(thumbs) + cols - 1) // cols
    heights = [
        max(thumbs[i].height for i in range(r * cols, min(len(thumbs), (r + 1) * cols)))
        for r in range(rows)
    ]
    sheet = Image.new(
        "RGB",
        (cols * thumb_w + (cols + 1) * gap, sum(heights) + (rows + 1) * gap),
        (245, 245, 245),
    )
    y = gap
    for row, height in enumerate(heights):
        x = gap
        for col in range(cols):
            idx = row * cols + col
            if idx < len(thumbs):
                sheet.paste(thumbs[idx], (x, y))
            x += thumb_w + gap
        y += height + gap
    sheet.save(OUT / out_name)


def make_contact_sheets() -> None:
    """@brief Genere les quatre planches inspectees pour Task 6."""
    transistor = lambda name: name.startswith("tr_") or name.startswith("ilot_")
    aop_sample = lambda name: name.startswith("aop_") or name.startswith("ilot_tous_aop")
    for mode in ("z", "detaille"):
        _make_contact_sheet(mode, transistor, f"_contact_{mode}_transistors.png")
        _make_contact_sheet(mode, aop_sample, f"_contact_{mode}_aop.png")


def main() -> None:
    count = render_all()
    make_contact_sheets()
    print(f"{count} PNG rendus dans {OUT}")


if __name__ == "__main__":
    main()
