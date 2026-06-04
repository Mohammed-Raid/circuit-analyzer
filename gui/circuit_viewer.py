"""
Schematic viewer using schemdraw 0.22 + matplotlib TkAgg backend.
Each detected circuit pattern has a dedicated drawing function.
"""
import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import schemdraw
import schemdraw.elements as elm

UI_BG   = "#0f172a"
UI_CARD = "#1e293b"
SCH_BG  = "#fafafa"   # light background — standard for schematics

_COMP_COLORS = {
    "R": "#1d4ed8", "C": "#0891b2", "L": "#059669",
    "D": "#dc2626", "Q": "#7c3aed", "M": "#6d28d9",
    "U": "#b45309", "F": "#374151",
}


# ── Public entry point ────────────────────────────────────────────────────────

def show_circuit(result: dict, comp_info: dict, parent=None):
    name    = result["circuit_type"]
    drawer  = _DRAWERS.get(name)

    popup = ctk.CTkToplevel(parent)
    popup.title(f"Schéma — {name}")
    popup.geometry("720x540")
    popup.configure(fg_color=UI_BG)
    popup.grab_set()

    # Header
    hdr = ctk.CTkFrame(popup, fg_color=UI_CARD, corner_radius=0, height=54)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    ctk.CTkLabel(hdr, text=f"⚡  {name}",
                 font=ctk.CTkFont("Segoe UI", 14, "bold"),
                 text_color="#f1f5f9").pack(side="left", padx=18, pady=14)

    # Component chips
    chips = ctk.CTkFrame(popup, fg_color=UI_BG)
    chips.pack(fill="x", padx=14, pady=(8, 2))
    ctk.CTkLabel(chips, text="Composants :",
                 font=ctk.CTkFont("Segoe UI", 10),
                 text_color="#64748b").pack(side="left")
    for ref in result["components"]:
        info = comp_info.get(ref, {})
        val  = info.get("value", "")
        typ  = info.get("type", "?")
        txt  = f" {ref} {val} ".strip()
        color = _COMP_COLORS.get(typ, "#374151")
        ctk.CTkLabel(chips, text=txt,
                     font=ctk.CTkFont("Consolas", 10, "bold"),
                     fg_color=color, text_color="#ffffff",
                     corner_radius=4).pack(side="left", padx=3)

    # Schematic area
    fig = _make_fig(result, comp_info, drawer)
    canvas_frame = ctk.CTkFrame(popup, fg_color=SCH_BG, corner_radius=10)
    canvas_frame.pack(fill="both", expand=True, padx=14, pady=(4, 0))

    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().configure(bg=SCH_BG, highlightthickness=0)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

    # Bottom bar
    bar = ctk.CTkFrame(popup, fg_color=UI_CARD, corner_radius=0, height=44)
    bar.pack(fill="x", side="bottom")
    bar.pack_propagate(False)
    ctk.CTkButton(bar, text="💾  Exporter PNG",
                  width=140, height=30, corner_radius=6,
                  font=ctk.CTkFont("Segoe UI", 11),
                  fg_color="#1d4ed8", hover_color="#2563eb",
                  command=lambda: _export(fig, name, popup)).pack(
                      side="left", padx=12, pady=7)
    ctk.CTkButton(bar, text="Fermer",
                  width=90, height=30, corner_radius=6,
                  font=ctk.CTkFont("Segoe UI", 11),
                  fg_color="#374151", hover_color="#4b5563",
                  command=popup.destroy).pack(side="right", padx=12, pady=7)


# ── Figure builder ────────────────────────────────────────────────────────────

def _make_fig(result, comp_info, drawer_fn):
    plt.close("all")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    fig.patch.set_facecolor(SCH_BG)
    ax.set_facecolor(SCH_BG)
    ax.axis("off")

    if drawer_fn:
        try:
            with schemdraw.Drawing(canvas=ax, show=False) as d:
                d.config(fontsize=11, inches_per_unit=0.5)
                drawer_fn(d, result, comp_info)
        except Exception as e:
            ax.text(0.5, 0.5, f"Schéma non disponible\n{e}",
                    ha="center", va="center",
                    transform=ax.transAxes,
                    fontsize=12, color="#64748b")
    else:
        ax.text(0.5, 0.6, result["circuit_type"],
                ha="center", va="center", transform=ax.transAxes,
                fontsize=14, fontweight="bold", color="#1e293b")
        ax.text(0.5, 0.45,
                "  ·  ".join(result["components"]),
                ha="center", va="center", transform=ax.transAxes,
                fontsize=11, color="#64748b", fontfamily="monospace")

    fig.tight_layout(pad=0.2)
    return fig


def _export(fig, name, parent):
    from tkinter import filedialog
    path = filedialog.asksaveasfilename(
        parent=parent, defaultextension=".png",
        filetypes=[("PNG", "*.png"), ("SVG", "*.svg")],
        title="Exporter le schéma",
    )
    if path:
        fig.savefig(path, dpi=150, bbox_inches="tight",
                    facecolor=SCH_BG, edgecolor="none")


# ── Label helpers ─────────────────────────────────────────────────────────────

def _lbl(ref, comp_info):
    val = comp_info.get(ref, {}).get("value", "")
    return f"{ref}\n{val}" if val else ref

def _ref(result, comp_info, typ):
    for r in result["components"]:
        if comp_info.get(r, {}).get("type") == typ:
            return r
    return result["components"][0] if result["components"] else "?"

def _refs(result, comp_info, typ):
    return [r for r in result["components"]
            if comp_info.get(r, {}).get("type") == typ]


# ── Drawing functions ─────────────────────────────────────────────────────────

def _draw_rc_lowpass(d, result, ci):
    r = _ref(result, ci, "R"); c = _ref(result, ci, "C")
    d += elm.Resistor().right().label(_lbl(r, ci), loc="top")
    d.push()
    d += elm.Capacitor().down().label(_lbl(c, ci), loc="right")
    d += elm.Ground()
    d.pop()
    d += elm.Line().right(1.5)


def _draw_rc_highpass(d, result, ci):
    c = _ref(result, ci, "C"); r = _ref(result, ci, "R")
    d += elm.Capacitor().right().label(_lbl(c, ci), loc="top")
    d.push()
    d += elm.Resistor().down().label(_lbl(r, ci), loc="right")
    d += elm.Ground()
    d.pop()
    d += elm.Line().right(1.5)


def _draw_lc_filter(d, result, ci):
    l = _ref(result, ci, "L"); c = _ref(result, ci, "C")
    d += elm.Inductor().right().label(_lbl(l, ci), loc="top")
    d.push()
    d += elm.Capacitor().down().label(_lbl(c, ci), loc="right")
    d += elm.Ground()
    d.pop()
    d += elm.Line().right(1.5)


def _draw_voltage_divider(d, result, ci):
    rs = _refs(result, ci, "R")
    r1 = rs[0] if rs else result["components"][0]
    r2 = rs[1] if len(rs) > 1 else result["components"][1]
    d += elm.Line().right(1).label("V+", loc="left")
    d += elm.Resistor().down().label(_lbl(r1, ci), loc="right")
    d.push()
    d += elm.Line().right(1.5).label("Vout", loc="right")
    d.pop()
    d += elm.Resistor().down().label(_lbl(r2, ci), loc="right")
    d += elm.Ground()


def _draw_decoupling(d, result, ci):
    c = _ref(result, ci, "C")
    d += elm.Line().right(1).label("VCC", loc="left")
    d += elm.Capacitor().down().label(_lbl(c, ci), loc="right")
    d += elm.Ground()


def _draw_snubber(d, result, ci):
    r = _ref(result, ci, "R"); c = _ref(result, ci, "C")
    d += elm.Resistor().right().label(_lbl(r, ci), loc="top")
    d.push()
    d += elm.Line().left(3).up(1.5)
    d += elm.Capacitor().right().label(_lbl(c, ci), loc="top")
    d.pop()


def _draw_fuse(d, result, ci):
    f = result["components"][0]
    d += elm.Fuse().right().label(_lbl(f, ci), loc="top")


def _draw_half_wave(d, result, ci):
    diode = _ref(result, ci, "D"); r = _ref(result, ci, "R")
    d += elm.Diode().right().label(_lbl(diode, ci), loc="top")
    d.push()
    d += elm.Resistor().down().label(_lbl(r, ci), loc="right")
    d += elm.Ground()
    d.pop()
    d += elm.Line().right(1.5).label("DC", loc="right")


def _draw_peak_detector(d, result, ci):
    diode = _ref(result, ci, "D"); c = _ref(result, ci, "C")
    d += elm.Diode().right().label(_lbl(diode, ci), loc="top")
    d.push()
    d += elm.Capacitor().down().label(_lbl(c, ci), loc="right")
    d += elm.Ground()
    d.pop()
    d += elm.Line().right(1.5).label("PEAK", loc="right")


def _draw_bridge_rectifier(d, result, ci):
    ds = _refs(result, ci, "D")
    while len(ds) < 4:
        ds.append("D?")
    d += elm.Line().right(0.5).label("AC1", loc="left")
    d += elm.Diode().right().label(ds[0], loc="top")
    d += elm.Line().right(1).label("DC+", loc="right")
    d.push()
    d += elm.Line().down(2)
    d += elm.Ground()
    d.pop()
    d += elm.Line().at((0, -2)).right(0.5).label("AC2", loc="left")
    d += elm.Diode().flip().up().label(ds[1], loc="right")
    d += elm.Diode().right().label(ds[2], loc="bottom")
    d += elm.Line().right(0.5).label("DC−", loc="right")


def _draw_flyback(d, result, ci):
    diode = result["components"][0]
    d += elm.Line().right(0.5).label("SW", loc="left")
    d += elm.Diode().right().label(_lbl(diode, ci), loc="top")
    d += elm.Line().right(0.5).label("VCC", loc="right")


def _draw_esd(d, result, ci):
    diode = result["components"][0]
    d += elm.Line().right(0.5).label("SIG", loc="left")
    d += elm.Zener().down().label(_lbl(diode, ci), loc="right")
    d += elm.Ground()


# ── AOP patterns ─────────────────────────────────────────────────────────────

def _draw_inverting_amp(d, result, ci):
    rs = _refs(result, ci, "R")
    rin = rs[0] if rs else "Rin"
    rf  = rs[1] if len(rs) > 1 else "Rf"

    op = d.add(elm.Opamp().anchor("in1").at((4.5, 0)))

    d.add(elm.Resistor().at(op.in1).left().label(_lbl(rin, ci), loc="top"))
    mid_pt = op.in1
    d.add(elm.Line().at(op.in2).left(1))
    d.add(elm.Ground())

    # Feedback path
    above = (mid_pt[0], mid_pt[1] + 1.5)
    d.add(elm.Line().at(mid_pt).up(1.5))
    d.add(elm.Resistor().right().label(_lbl(rf, ci), loc="top")
          .at(above))
    d.add(elm.Line().down(1.5).to(op.out))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


def _draw_non_inverting_amp(d, result, ci):
    rs = _refs(result, ci, "R")
    rf  = rs[0] if rs else "Rf"
    rg  = rs[1] if len(rs) > 1 else "Rg"

    op = d.add(elm.Opamp().anchor("in2").at((4.5, 0)))

    d.add(elm.Line().at(op.in2).left(1.2).label("IN+", loc="left"))

    fb_pt = op.in1
    d.add(elm.Resistor().at(fb_pt).down().label(_lbl(rg, ci), loc="right"))
    d.add(elm.Ground())

    above = (fb_pt[0], fb_pt[1] + 1.5)
    d.add(elm.Line().at(fb_pt).up(1.5))
    d.add(elm.Resistor().right().label(_lbl(rf, ci), loc="top").at(above))
    d.add(elm.Line().down(1.5).to(op.out))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


def _draw_follower(d, result, ci):
    u = _ref(result, ci, "U")
    op = d.add(elm.Opamp().anchor("in2").at((4.5, 0)))
    d.add(elm.Line().at(op.in2).left(1.2).label("IN", loc="left"))

    out_pt  = op.out
    in1_pt  = op.in1
    above_x = (out_pt[0] + 0.8, in1_pt[1] + 1.2)
    d.add(elm.Line().at(out_pt).right(0.8))
    d.add(elm.Line().up(in1_pt[1] + 1.2 - out_pt[1]))
    d.add(elm.Line().left(above_x[0] - in1_pt[0]))
    d.add(elm.Line().down(1.2).to(in1_pt))
    d.add(elm.Dot().at(out_pt).label("OUT", loc="right"))


def _draw_integrator(d, result, ci):
    rs = _refs(result, ci, "R"); cs = _refs(result, ci, "C")
    r = rs[0] if rs else "R"
    c = cs[0] if cs else "C"

    op = d.add(elm.Opamp().anchor("in1").at((4.5, 0)))
    d.add(elm.Resistor().at(op.in1).left().label(_lbl(r, ci), loc="top"))
    mid_pt = op.in1
    d.add(elm.Line().at(op.in2).left(1))
    d.add(elm.Ground())

    above = (mid_pt[0], mid_pt[1] + 1.5)
    d.add(elm.Line().at(mid_pt).up(1.5))
    d.add(elm.Capacitor().right().label(_lbl(c, ci), loc="top").at(above))
    d.add(elm.Line().down(1.5).to(op.out))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


def _draw_differentiator(d, result, ci):
    cs = _refs(result, ci, "C"); rs = _refs(result, ci, "R")
    c = cs[0] if cs else "C"
    r = rs[0] if rs else "R"

    op = d.add(elm.Opamp().anchor("in1").at((4.5, 0)))
    d.add(elm.Capacitor().at(op.in1).left().label(_lbl(c, ci), loc="top"))
    mid_pt = op.in1
    d.add(elm.Line().at(op.in2).left(1))
    d.add(elm.Ground())

    above = (mid_pt[0], mid_pt[1] + 1.5)
    d.add(elm.Line().at(mid_pt).up(1.5))
    d.add(elm.Resistor().right().label(_lbl(r, ci), loc="top").at(above))
    d.add(elm.Line().down(1.5).to(op.out))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


def _draw_comparator(d, result, ci):
    op = d.add(elm.Opamp().anchor("center").at((4.5, 0)))
    d.add(elm.Line().at(op.in2).left(1.2).label("IN+", loc="left"))
    d.add(elm.Line().at(op.in1).left(1.2).label("IN−", loc="left"))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


def _draw_schmitt(d, result, ci):
    rs = _refs(result, ci, "R")
    rf = rs[0] if rs else "Rf"

    op = d.add(elm.Opamp().anchor("center").at((4.5, 0)))
    d.add(elm.Line().at(op.in1).left(1.2).label("REF", loc="left"))

    in2_pt = op.in2
    d.add(elm.Line().at(in2_pt).left(0.8).label("IN", loc="left"))
    fb_junc = (in2_pt[0], in2_pt[1] + 1.5)
    d.add(elm.Line().at(in2_pt).up(1.5))
    d.add(elm.Resistor().right().label(_lbl(rf, ci), loc="top").at(fb_junc))
    d.add(elm.Line().down(1.5).to(op.out))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


def _draw_differential_amp(d, result, ci):
    rs = _refs(result, ci, "R")
    r1  = rs[0] if len(rs) > 0 else "R1"
    rg  = rs[1] if len(rs) > 1 else "Rg"
    r2  = rs[2] if len(rs) > 2 else "R2"
    rf  = rs[3] if len(rs) > 3 else "Rf"

    op = d.add(elm.Opamp().anchor("center").at((5.5, 0)))

    # IN+ path
    d.add(elm.Resistor().at(op.in2).left().label(_lbl(r1, ci), loc="top"))
    d.add(elm.Dot().label("IN1", loc="left"))
    d.add(elm.Resistor().at(op.in2).down().label(_lbl(rg, ci), loc="right"))
    d.add(elm.Ground())

    # IN- path with feedback
    in1_pt = op.in1
    d.add(elm.Resistor().at(in1_pt).left().label(_lbl(r2, ci), loc="top"))
    d.add(elm.Dot().label("IN2", loc="left"))
    above = (in1_pt[0], in1_pt[1] + 1.5)
    d.add(elm.Line().at(in1_pt).up(1.5))
    d.add(elm.Resistor().right().label(_lbl(rf, ci), loc="top").at(above))
    d.add(elm.Line().down(1.5).to(op.out))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


def _draw_summing_amp(d, result, ci):
    rs = _refs(result, ci, "R")
    rf = rs[0] if rs else "Rf"
    inputs = rs[1:] if len(rs) > 1 else ["Ra", "Rb"]

    op = d.add(elm.Opamp().anchor("in1").at((5, 0)))
    in1_pt = op.in1
    d.add(elm.Line().at(op.in2).left(1))
    d.add(elm.Ground())

    # Draw summing resistors
    spacing = 1.2
    for i, r in enumerate(inputs[:3]):
        y_off = i * spacing - (len(inputs[:3]) - 1) * spacing / 2
        start = (in1_pt[0] - 3, in1_pt[1] + y_off)
        d.add(elm.Resistor().right().label(_lbl(r, ci), loc="top").at(start))
        end = (in1_pt[0], in1_pt[1] + y_off)
        if i < len(inputs[:3]) - 1:
            d.add(elm.Line().at(end).to(in1_pt))

    # Feedback
    above = (in1_pt[0], in1_pt[1] + 1.5 + (len(inputs[:3]) - 1) * spacing / 2)
    d.add(elm.Line().at(in1_pt).up(above[1] - in1_pt[1]))
    d.add(elm.Resistor().right().label(_lbl(rf, ci), loc="top").at(above))
    d.add(elm.Line().down(above[1] - op.out[1]).to(op.out))
    d.add(elm.Line().at(op.out).right(1).label("OUT", loc="right"))


# ── Transistor patterns ───────────────────────────────────────────────────────

def _draw_bjt_switch(d, result, ci):
    q = _ref(result, ci, "Q"); r = _ref(result, ci, "R")
    t = d.add(elm.BjtNpn().at((3, 0)))
    d.add(elm.Resistor().at(t.base).left().label(_lbl(r, ci), loc="top"))
    d.add(elm.Dot().label("IN", loc="left"))
    d.add(elm.Line().at(t.collector).up(1).label("LOAD", loc="right"))
    d.add(elm.Line().at(t.emitter).down(0.5))
    d.add(elm.Ground())


def _draw_common_emitter(d, result, ci):
    q = _ref(result, ci, "Q")
    rs = _refs(result, ci, "R")
    rb = rs[0] if rs else "Rb"
    rc = rs[1] if len(rs) > 1 else "Rc"
    t = d.add(elm.BjtNpn().at((3, 0)))
    d.add(elm.Resistor().at(t.base).left().label(_lbl(rb, ci), loc="top"))
    d.add(elm.Dot().label("IN", loc="left"))
    d.add(elm.Resistor().at(t.collector).up().label(_lbl(rc, ci), loc="right"))
    d.add(elm.Dot().label("VCC", loc="right"))
    d.add(elm.Line().at(t.emitter).down(0.5))
    d.add(elm.Ground())
    d.add(elm.Line().at(t.collector).right(1.5).label("OUT", loc="right"))


def _draw_mosfet_switch(d, result, ci):
    m = _ref(result, ci, "M"); r = _ref(result, ci, "R")
    t = d.add(elm.NFet().at((3, 0)))
    d.add(elm.Resistor().at(t.gate).left().label(_lbl(r, ci), loc="top"))
    d.add(elm.Dot().label("IN", loc="left"))
    d.add(elm.Line().at(t.drain).up(1).label("LOAD", loc="right"))
    d.add(elm.Line().at(t.source).down(0.5))
    d.add(elm.Ground())


def _draw_current_mirror(d, result, ci):
    qs = _refs(result, ci, "Q")
    q1 = qs[0] if qs else "Q1"
    q2 = qs[1] if len(qs) > 1 else "Q2"
    t1 = d.add(elm.BjtNpn().at((1.5, 0)))
    t2 = d.add(elm.BjtNpn().at((4.5, 0)))
    # Shared base connection
    d.add(elm.Line().at(t1.base).right().to(t2.base))
    # Diode-connect Q1: collector to base
    d.add(elm.Line().at(t1.collector).down().to(t1.base))
    # Collectors
    d.add(elm.Line().at(t1.collector).up(0.8).label("Iref", loc="right"))
    d.add(elm.Line().at(t2.collector).up(0.8).label("Iout", loc="right"))
    # Emitters to GND
    d.add(elm.Line().at(t1.emitter).down(0.3))
    d.add(elm.Ground())
    d.add(elm.Line().at(t2.emitter).down(0.3))
    d.add(elm.Ground())


# ── Pattern registry ──────────────────────────────────────────────────────────

_DRAWERS = {
    "Filtre RC passe-bas":               _draw_rc_lowpass,
    "Filtre RC passe-haut":              _draw_rc_highpass,
    "Filtre LC":                         _draw_lc_filter,
    "Pont diviseur de tension":          _draw_voltage_divider,
    "Condensateur de découplage":        _draw_decoupling,
    "Snubber RC":                        _draw_snubber,
    "Protection par fusible":            _draw_fuse,
    "Redresseur simple alternance":      _draw_half_wave,
    "Détecteur de crête":                _draw_peak_detector,
    "Pont redresseur (Graetz)":          _draw_bridge_rectifier,
    "Diode de roue libre":               _draw_flyback,
    "Diode de protection ESD":           _draw_esd,
    "Amplificateur inverseur (AOP)":     _draw_inverting_amp,
    "Amplificateur non-inverseur (AOP)": _draw_non_inverting_amp,
    "Suiveur de tension (AOP)":          _draw_follower,
    "Intégrateur (AOP)":                 _draw_integrator,
    "Dérivateur (AOP)":                  _draw_differentiator,
    "Comparateur (AOP)":                 _draw_comparator,
    "Trigger de Schmitt (AOP)":          _draw_schmitt,
    "Amplificateur différentiel (AOP)":  _draw_differential_amp,
    "Amplificateur sommateur (AOP)":     _draw_summing_amp,
    "Transistor en commutation":         _draw_bjt_switch,
    "Amplificateur émetteur commun":     _draw_common_emitter,
    "Miroir de courant BJT":             _draw_current_mirror,
    "MOSFET en commutation":             _draw_mosfet_switch,
}
