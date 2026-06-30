"""
@file impedance_view.py
@brief Boîte de dialogue « Impédance équivalente » : choisir deux bornes d'un
       réseau d'impédances pures et afficher la Z équivalente (série/parallèle/Y-Δ).

Ne traite que les impédances : les arêtes non-R/L/C du graphe sont ignorées.
"""
import cmath
import math

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from circuit_analyzer import impedance
from gui import impedance_schematic
from gui.theme import BG, CARD, CARD2, BORDER, TEXT, MUTED, BLUE

SCH_BG = "#fafafa"   # fond clair standard de schema (idem circuit_viewer)


def _fmt_ohms(x: float) -> str:
    """@brief Formate une magnitude d'impédance en Ω avec préfixe ingénieur.

    @param x Magnitude en ohms.
    @return str Ex. « 1.59 kΩ », « 470 Ω », « 2.2 MΩ », « ∞ Ω ».
    """
    if not math.isfinite(x):
        return "∞ Ω"
    for seuil, suff in ((1e6, "M"), (1e3, "k"), (1.0, "")):
        if abs(x) >= seuil:
            return f"{x / seuil:.3g} {suff}Ω"
    return f"{x:.3g} Ω"


def show_impedance_equivalent(graph, parent=None):
    """@brief Ouvre la fenêtre de calcul d'impédance équivalente pour `graph`.

    @param graph Graphe analysé (les arêtes R/L/C sont les seules considérées).
    @param parent Fenêtre parente (optionnelle).
    @return None
    """
    bornes = impedance.bornes_possibles(graph)
    win = ctk.CTkToplevel(parent)
    win.title("Impédance équivalente")
    win.geometry("720x640")
    win.configure(fg_color=BG)
    if parent is not None:
        win.transient(parent.winfo_toplevel())

    ctk.CTkLabel(win, text="Impédance équivalente",
                 font=ctk.CTkFont("Segoe UI", 18, "bold"),
                 text_color=TEXT).pack(anchor="w", padx=24, pady=(20, 2))
    ctk.CTkLabel(win, text="Réduction série · parallèle · étoile↔triangle (symbolique)",
                 font=ctk.CTkFont("Segoe UI", 12), text_color=MUTED).pack(
                     anchor="w", padx=24)

    if len(bornes) < 2:
        ctk.CTkLabel(win, text="Ce circuit ne contient pas de réseau d'impédances.",
                     font=ctk.CTkFont("Segoe UI", 13), text_color="#f59e0b").pack(
                         padx=24, pady=40)
        return

    sel = ctk.CTkFrame(win, fg_color=CARD2, corner_radius=10)
    sel.pack(fill="x", padx=24, pady=18)
    # Pré-sélection des bornes d'entrée/sortie si présentes (fluidité démo).
    defaut_a = "VIN" if "VIN" in bornes else bornes[0]
    defaut_b = "VOUT" if "VOUT" in bornes else next(
        (n for n in bornes if n != defaut_a), bornes[0])
    var_a = ctk.StringVar(value=defaut_a)
    var_b = ctk.StringVar(value=defaut_b)
    for label, var in (("Borne A", var_a), ("Borne B", var_b)):
        row = ctk.CTkFrame(sel, fg_color="transparent")
        row.pack(side="left", expand=True, fill="x", padx=14, pady=14)
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=MUTED).pack(anchor="w")
        ctk.CTkOptionMenu(row, variable=var, values=bornes,
                          fg_color=CARD, button_color=BLUE,
                          font=ctk.CTkFont("Consolas", 12)).pack(fill="x", pady=(4, 0))

    # Fréquence pour l'évaluation numérique (R/L/C → Z complexe). Vide = symbolique seul.
    freq_row = ctk.CTkFrame(win, fg_color="transparent")
    freq_row.pack(fill="x", padx=24)
    ctk.CTkLabel(freq_row, text="Fréquence (Hz)", font=ctk.CTkFont("Segoe UI", 11, "bold"),
                 text_color=MUTED).pack(side="left")
    var_f = ctk.StringVar(value="1000")
    ctk.CTkEntry(freq_row, textvariable=var_f, width=120, fg_color=CARD,
                 font=ctk.CTkFont("Consolas", 12)).pack(side="left", padx=10)

    resultat = ctk.CTkLabel(win, text="Choisissez deux bornes puis « Calculer ».",
                            font=ctk.CTkFont("Consolas", 13), text_color=TEXT,
                            wraplength=500, justify="left")
    resultat.pack(fill="x", padx=24, pady=(4, 8))

    schema_holder = ctk.CTkFrame(win, fg_color=SCH_BG, corner_radius=10)
    schema_holder.pack(fill="both", expand=True, padx=24, pady=(4, 12))

    def _calculer():
        a, b = var_a.get(), var_b.get()
        if a == b:
            resultat.configure(text="Choisissez deux bornes différentes.",
                               text_color="#f59e0b")
            return
        expr = impedance.impedance_equivalente(graph, a, b)
        # Vider un eventuel schema precedent.
        for w in schema_holder.winfo_children():
            w.destroy()
        if expr is None:
            resultat.configure(
                text=f"Réseau non réductible entre {a} et {b} par série/parallèle/Y-Δ\n"
                     "(bornes non reliées par des impédances, ou réseau non planaire).",
                text_color="#f59e0b")
            return
        lignes = [f"Z({a},{b}) = {impedance.formater_expr(expr)}"]
        f_txt = var_f.get().strip()
        if f_txt:
            try:
                f = float(f_txt.replace(",", "."))
                z = impedance.evaluer_impedance(graph, expr, f)
                phase = math.degrees(cmath.phase(z))
                lignes.append(f"à {f:g} Hz : |Z| = {_fmt_ohms(abs(z))}"
                              f"  ∠ {phase:+.1f}°")
            except (ValueError, ZeroDivisionError) as e:
                lignes.append(f"(valeur numérique indisponible : {e})")
        arbre = impedance.arbre_expr(expr)
        pont = impedance.detecter_pont(graph, a, b) if arbre is None else None
        fig = None
        if arbre is not None:
            fig = impedance_schematic.dessiner_bloc(arbre, a, b, graph.graph["components"])
        elif pont is not None:
            fig = impedance_schematic.dessiner_pont(pont, graph.graph["components"])
            lignes.append("Réseau en pont — cliquez une boîte Z pour le détail.")
        else:
            lignes.append("Réseau en pont (Y-Δ) — pas de forme série/parallèle à dessiner.")
        if fig is not None:
            canvas = FigureCanvasTkAgg(fig, master=schema_holder)
            canvas.draw()
            canvas.get_tk_widget().configure(bg=SCH_BG, highlightthickness=0)
            canvas.get_tk_widget().pack(fill="both", expand=True)

            def _on_click(event, _fig=fig):
                if event.xdata is None or event.ydata is None:
                    return
                from gui import circuit_viewer
                for x0, x1, y0, y1, refs, composition in getattr(_fig, "_z_hitboxes", []):
                    if x0 <= event.xdata <= x1 and y0 <= event.ydata <= y1:
                        circuit_viewer.show_dipole_detail(refs, composition, graph, {}, win)
                        return

            canvas.mpl_connect("button_press_event", _on_click)
        resultat.configure(text="\n".join(lignes), text_color="#34d399")

    ctk.CTkButton(win, text="Calculer", height=38, corner_radius=8,
                  font=ctk.CTkFont("Segoe UI", 12, "bold"),
                  fg_color="#16a34a", hover_color="#15803d",
                  command=_calculer).pack(padx=24, pady=(4, 16), anchor="w")
