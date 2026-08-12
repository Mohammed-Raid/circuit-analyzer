"""
tools/gen_icons.py  (dev-time, re-runnable; commits the produced PNGs)

Rasterizer: PIL fallback (cairosvg not available on this Windows host — no
libcairo-2.dll).  Approach:
  1. Download Lucide SVGs from raw.githubusercontent.com (vendored in
     tools/lucide_svg/ so subsequent runs are offline-capable).
  2. Parse each SVG with xml.etree.ElementTree; extract <path>, <circle>,
     <line>, <polyline>, <polygon>, <rect> elements.
  3. Render at 4× supersampling with Pillow, then LANCZOS-downsample to
     target size (20 px for 1x, 40 px for 2x).
  4. Write assets/icons/<name>.png  and  assets/icons/<name>@2x.png.

Runtime dependency: NONE (only PIL at runtime for the GUI; this script is
dev-time only).
"""

import math
import os
import urllib.request
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NAMES = [
    "search", "pen-tool", "zap", "wrench", "folder-open", "save", "trash-2",
    "copy", "check", "alert-triangle", "x", "chevron-down", "chevron-right",
    "play", "activity", "cpu", "layers", "sliders", "plus", "rotate-cw",
    "maximize", "download", "file-text", "sigma",
]

# Lucide renamed some icons in recent versions; map brief-name → actual filename.
LUCIDE_ALIASES = {
    "alert-triangle": "triangle-alert",
    "sliders": "sliders-horizontal",
}

COLOR = (148, 163, 184, 255)  # TEXT_MUTED  #94a3b8

_BASE = os.path.dirname(__file__)
SVG_DIR = os.path.join(_BASE, "lucide_svg")
OUT_DIR = os.path.join(_BASE, "..", "assets", "icons")

LUCIDE_RAW = "https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{name}.svg"
SVG_VIEWBOX = 24.0          # Lucide icons all use viewBox="0 0 24 24"

# Supersampling factor: render at SS× then downsample.
SS = 4
SIZES = [(20, ""), (40, "@2x")]   # (target_px, suffix)

NS = {"svg": "http://www.w3.org/2000/svg"}

# ---------------------------------------------------------------------------
# SVG path → list of subpaths (sequences of (x, y) float tuples)
# ---------------------------------------------------------------------------
def _parse_number(s):
    return float(s)

def _tokenize_path(d):
    """Yield (cmd, [args]) pairs from an SVG path 'd' attribute."""
    import re
    token_re = re.compile(
        r"([MmZzLlHhVvCcSsQqTtAa])|"
        r"([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
    )
    tokens = token_re.findall(d)
    cmd = None
    args = []
    for cmd_tok, num_tok in tokens:
        if cmd_tok:
            if cmd is not None:
                yield cmd, args
            cmd = cmd_tok
            args = []
        elif num_tok:
            args.append(float(num_tok))
    if cmd is not None:
        yield cmd, args


def _arc_to_lines(x1, y1, rx, ry, phi_deg, large_arc, sweep, x2, y2, n=32):
    """Convert SVG arc to a list of (x, y) points (endpoint parametrization)."""
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    phi = math.radians(phi_deg)
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)
    dx = (x1 - x2) / 2
    dy = (y1 - y2) / 2
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy
    rx = abs(rx)
    ry = abs(ry)
    # Ensure radii are large enough
    lam = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if lam > 1:
        sq = math.sqrt(lam)
        rx *= sq
        ry *= sq
    num = max(0.0, rx**2 * ry**2 - rx**2 * y1p**2 - ry**2 * x1p**2)
    den = rx**2 * y1p**2 + ry**2 * x1p**2
    sq = math.sqrt(num / den) if den != 0 else 0
    if large_arc == sweep:
        sq = -sq
    cxp = sq * rx * y1p / ry
    cyp = -sq * ry * x1p / rx
    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2

    def angle(ux, uy, vx, vy):
        n = math.sqrt(ux**2 + uy**2) * math.sqrt(vx**2 + vy**2)
        if n == 0:
            return 0
        c = max(-1.0, min(1.0, (ux * vx + uy * vy) / n))
        a = math.acos(c)
        if ux * vy - uy * vx < 0:
            a = -a
        return a

    theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = angle(
        (x1p - cxp) / rx, (y1p - cyp) / ry,
        (-x1p - cxp) / rx, (-y1p - cyp) / ry,
    )
    if not sweep and dtheta > 0:
        dtheta -= 2 * math.pi
    elif sweep and dtheta < 0:
        dtheta += 2 * math.pi

    pts = []
    for i in range(1, n + 1):
        t = theta1 + dtheta * i / n
        xp = rx * math.cos(t)
        yp = ry * math.sin(t)
        pts.append((
            cos_phi * xp - sin_phi * yp + cx,
            sin_phi * xp + cos_phi * yp + cy,
        ))
    return pts


def _cubic_bezier_pts(x0, y0, x1, y1, x2, y2, x3, y3, n=16):
    pts = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        x = u**3*x0 + 3*u**2*t*x1 + 3*u*t**2*x2 + t**3*x3
        y = u**3*y0 + 3*u**2*t*y1 + 3*u*t**2*y2 + t**3*y3
        pts.append((x, y))
    return pts


def _quad_bezier_pts(x0, y0, x1, y1, x2, y2, n=12):
    pts = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        x = u**2*x0 + 2*u*t*x1 + t**2*x2
        y = u**2*y0 + 2*u*t*y1 + t**2*y2
        pts.append((x, y))
    return pts


def path_to_subpaths(d):
    """
    Parse an SVG path 'd' string into a list of sub-paths.
    Each sub-path is a list of (x, y) float tuples.
    Returns (subpaths, close_flags) where close_flags[i] is True if subpath i
    was closed with Z.
    """
    subpaths = []
    close_flags = []
    cur = []
    closed = False
    cx, cy = 0.0, 0.0   # current point
    sx, sy = 0.0, 0.0   # start of current subpath (for Z)
    last_ctrl = None     # last control point for S/s and T/t

    def flush():
        nonlocal cur, closed
        if cur:
            subpaths.append(cur[:])
            close_flags.append(closed)
        cur = []
        closed = False

    def consume(cmd, raw_args):
        nonlocal cx, cy, sx, sy, last_ctrl, cur, closed

        def pairs(lst, n):
            return [lst[i:i+n] for i in range(0, len(lst), n)]

        upper = cmd.upper()

        if upper == 'M':
            flush()
            coords = pairs(raw_args, 2)
            x, y = (coords[0][0], coords[0][1]) if cmd == 'M' else (cx + coords[0][0], cy + coords[0][1])
            cx, cy = x, y
            sx, sy = cx, cy
            cur = [(cx, cy)]
            last_ctrl = None
            # Additional pairs treated as implicit L
            for p in coords[1:]:
                if cmd == 'M':
                    nx, ny = p[0], p[1]
                else:
                    nx, ny = cx + p[0], cy + p[1]
                cur.append((nx, ny))
                cx, cy = nx, ny
                last_ctrl = None

        elif upper == 'Z':
            if cur:
                cur.append((sx, sy))
                closed = True
                flush()
            cx, cy = sx, sy
            last_ctrl = None

        elif upper == 'L':
            for p in pairs(raw_args, 2):
                nx, ny = (p[0], p[1]) if cmd == 'L' else (cx + p[0], cy + p[1])
                cur.append((nx, ny))
                cx, cy = nx, ny
            last_ctrl = None

        elif upper == 'H':
            for v in raw_args:
                nx = v if cmd == 'H' else cx + v
                cur.append((nx, cy))
                cx = nx
            last_ctrl = None

        elif upper == 'V':
            for v in raw_args:
                ny = v if cmd == 'V' else cy + v
                cur.append((cx, ny))
                cy = ny
            last_ctrl = None

        elif upper == 'C':
            for chunk in pairs(raw_args, 6):
                if cmd == 'C':
                    x1, y1, x2, y2, x3, y3 = chunk
                else:
                    x1, y1 = cx + chunk[0], cy + chunk[1]
                    x2, y2 = cx + chunk[2], cy + chunk[3]
                    x3, y3 = cx + chunk[4], cy + chunk[5]
                pts = _cubic_bezier_pts(cx, cy, x1, y1, x2, y2, x3, y3)
                cur.extend(pts)
                last_ctrl = (x2, y2)
                cx, cy = x3, y3

        elif upper == 'S':
            for chunk in pairs(raw_args, 4):
                if cmd == 'S':
                    x2, y2, x3, y3 = chunk
                else:
                    x2, y2 = cx + chunk[0], cy + chunk[1]
                    x3, y3 = cx + chunk[2], cy + chunk[3]
                if last_ctrl:
                    x1 = 2 * cx - last_ctrl[0]
                    y1 = 2 * cy - last_ctrl[1]
                else:
                    x1, y1 = cx, cy
                pts = _cubic_bezier_pts(cx, cy, x1, y1, x2, y2, x3, y3)
                cur.extend(pts)
                last_ctrl = (x2, y2)
                cx, cy = x3, y3

        elif upper == 'Q':
            for chunk in pairs(raw_args, 4):
                if cmd == 'Q':
                    x1, y1, x2, y2 = chunk
                else:
                    x1, y1 = cx + chunk[0], cy + chunk[1]
                    x2, y2 = cx + chunk[2], cy + chunk[3]
                pts = _quad_bezier_pts(cx, cy, x1, y1, x2, y2)
                cur.extend(pts)
                last_ctrl = (x1, y1)
                cx, cy = x2, y2

        elif upper == 'T':
            for chunk in pairs(raw_args, 2):
                if cmd == 'T':
                    x2, y2 = chunk
                else:
                    x2, y2 = cx + chunk[0], cy + chunk[1]
                if last_ctrl:
                    x1 = 2 * cx - last_ctrl[0]
                    y1 = 2 * cy - last_ctrl[1]
                else:
                    x1, y1 = cx, cy
                pts = _quad_bezier_pts(cx, cy, x1, y1, x2, y2)
                cur.extend(pts)
                last_ctrl = (x1, y1)
                cx, cy = x2, y2

        elif upper == 'A':
            for chunk in pairs(raw_args, 7):
                if cmd == 'A':
                    rx, ry, phi, la, sw, x2, y2 = chunk
                else:
                    rx, ry, phi, la, sw, dx, dy = chunk
                    x2, y2 = cx + dx, cy + dy
                pts = _arc_to_lines(cx, cy, rx, ry, phi, int(la), int(sw), x2, y2)
                cur.extend(pts)
                cx, cy = x2, y2
                last_ctrl = None

    for cmd, args in _tokenize_path(d):
        consume(cmd, args)

    flush()
    return subpaths, close_flags


# ---------------------------------------------------------------------------
# SVG element → drawing operations
# ---------------------------------------------------------------------------
def _attr(el, name, default=None):
    """Get attribute from element, checking both plain and namespaced forms."""
    v = el.get(name)
    if v is None:
        v = el.get("{http://www.w3.org/2000/svg}" + name)
    return v if v is not None else default


def _parse_points(s):
    """Parse SVG 'points' attribute into list of (x, y)."""
    import re
    nums = [float(n) for n in re.findall(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?", s)]
    return list(zip(nums[0::2], nums[1::2]))


def svg_to_draw_ops(svg_bytes):
    """
    Parse SVG bytes and return a list of drawing operations.
    Each op is a dict: {'type': 'polyline'|'circle'|'ellipse'|'rect',
                        'points': [...], 'cx': ..., 'cy': ..., 'r': ..., ...}
    All coordinates are in the SVG viewBox space (0..24).
    """
    root = ET.fromstring(svg_bytes)
    ops = []

    def strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    def walk(el):
        tag = strip_ns(el.tag)

        if tag == "path":
            d = _attr(el, "d", "")
            if d:
                subpaths, _ = path_to_subpaths(d)
                for pts in subpaths:
                    if pts:
                        ops.append({"type": "polyline", "points": pts})

        elif tag == "circle":
            cx = float(_attr(el, "cx", "0"))
            cy = float(_attr(el, "cy", "0"))
            r  = float(_attr(el, "r",  "0"))
            ops.append({"type": "circle", "cx": cx, "cy": cy, "r": r})

        elif tag == "ellipse":
            cx = float(_attr(el, "cx", "0"))
            cy = float(_attr(el, "cy", "0"))
            rx = float(_attr(el, "rx", "0"))
            ry = float(_attr(el, "ry", "0"))
            ops.append({"type": "ellipse", "cx": cx, "cy": cy, "rx": rx, "ry": ry})

        elif tag == "line":
            x1 = float(_attr(el, "x1", "0"))
            y1 = float(_attr(el, "y1", "0"))
            x2 = float(_attr(el, "x2", "0"))
            y2 = float(_attr(el, "y2", "0"))
            ops.append({"type": "polyline", "points": [(x1, y1), (x2, y2)]})

        elif tag in ("polyline", "polygon"):
            pts_str = _attr(el, "points", "")
            pts = _parse_points(pts_str)
            if pts:
                if tag == "polygon" and pts[0] != pts[-1]:
                    pts = pts + [pts[0]]
                ops.append({"type": "polyline", "points": pts})

        elif tag == "rect":
            x  = float(_attr(el, "x", "0"))
            y  = float(_attr(el, "y", "0"))
            w  = float(_attr(el, "width",  "0"))
            h  = float(_attr(el, "height", "0"))
            rx = float(_attr(el, "rx", "0"))
            ry = float(_attr(el, "ry", "0") if _attr(el, "ry") else _attr(el, "rx", "0"))
            if rx == 0 and ry == 0:
                pts = [(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)]
                ops.append({"type": "polyline", "points": pts})
            else:
                # Approximate rounded rect with arcs
                r = min(rx, ry, w/2, h/2)
                d = (f"M {x+r},{y} "
                     f"L {x+w-r},{y} Q {x+w},{y} {x+w},{y+r} "
                     f"L {x+w},{y+h-r} Q {x+w},{y+h} {x+w-r},{y+h} "
                     f"L {x+r},{y+h} Q {x},{y+h} {x},{y+h-r} "
                     f"L {x},{y+r} Q {x},{y} {x+r},{y} Z")
                subpaths, _ = path_to_subpaths(d)
                for sp in subpaths:
                    if sp:
                        ops.append({"type": "polyline", "points": sp})

        for child in el:
            walk(child)

    walk(root)
    return ops


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def render_ops(ops, canvas_px, color):
    """Render drawing ops to a PIL RGBA image of canvas_px × canvas_px."""
    img = Image.new("RGBA", (canvas_px, canvas_px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    scale = canvas_px / SVG_VIEWBOX
    # Stroke width: Lucide uses stroke-width=2 in 24-unit space.
    sw = max(1, round(2.0 * scale))

    def t(x, y):
        return (x * scale, y * scale)

    for op in ops:
        otype = op["type"]

        if otype == "polyline":
            pts = op["points"]
            if len(pts) < 2:
                continue
            screen_pts = [t(x, y) for x, y in pts]
            draw.line(screen_pts, fill=color, width=sw, joint="curve")
            # Draw round caps via small circles
            r = sw / 2
            for px, py in (screen_pts[0], screen_pts[-1]):
                draw.ellipse([(px-r, py-r), (px+r, py+r)], fill=color)

        elif otype == "circle":
            x0, y0 = t(op["cx"] - op["r"], op["cy"] - op["r"])
            x1, y1 = t(op["cx"] + op["r"], op["cy"] + op["r"])
            draw.ellipse([(x0, y0), (x1, y1)], outline=color, width=sw)

        elif otype == "ellipse":
            x0, y0 = t(op["cx"] - op["rx"], op["cy"] - op["ry"])
            x1, y1 = t(op["cx"] + op["rx"], op["cy"] + op["ry"])
            draw.ellipse([(x0, y0), (x1, y1)], outline=color, width=sw)

    return img


def make_icon(ops, target_px, color):
    """Render at SS× then downsample."""
    hi_res = render_ops(ops, target_px * SS, color)
    return hi_res.resize((target_px, target_px), Image.LANCZOS)


# ---------------------------------------------------------------------------
# Download / cache SVGs
# ---------------------------------------------------------------------------
def fetch_svg(name):
    """Return SVG bytes, downloading if needed and caching locally.

    Checks LUCIDE_ALIASES so that brief-names that differ from the Lucide
    filename still resolve correctly.
    """
    lucide_name = LUCIDE_ALIASES.get(name, name)
    local = os.path.join(SVG_DIR, f"{name}.svg")
    if os.path.exists(local):
        with open(local, "rb") as f:
            return f.read()
    url = LUCIDE_RAW.format(name=lucide_name)
    print(f"  downloading {url}")
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = resp.read()
    os.makedirs(SVG_DIR, exist_ok=True)
    with open(local, "wb") as f:
        f.write(data)
    return data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(SVG_DIR, exist_ok=True)
    ok = 0
    for name in NAMES:
        print(f"[{name}]")
        try:
            raw = fetch_svg(name)
            ops = svg_to_draw_ops(raw)
            if not ops:
                print(f"  WARNING: no draw ops for {name}")
            for target_px, suffix in SIZES:
                img = make_icon(ops, target_px, COLOR)
                out_path = os.path.join(OUT_DIR, f"{name}{suffix}.png")
                img.save(out_path, "PNG")
                ok += 1
                print(f"  wrote {out_path}")
        except Exception as exc:
            print(f"  ERROR: {exc}")

    total = len(NAMES) * len(SIZES)
    print(f"\nDone: {ok}/{total} files written to {os.path.abspath(OUT_DIR)}")
    if ok < total:
        print("WARNING: some icons failed — check errors above.")


if __name__ == "__main__":
    main()
