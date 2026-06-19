"""
@file impedance_view.py
@brief Boîte de dialogue « Impédance équivalente » : choisir deux bornes d'un
       réseau d'impédances pures et afficher la Z équivalente (série/parallèle/Y-Δ).

Ne traite que les impédances : les arêtes non-R/L/C du graphe sont ignorées.
"""
import customtkinter as ctk

from circuit_analyzer import impedance
from gui.theme import BG, CARD, CARD2, BORDER, TEXT, MUTED, BLUE


def show_impedance_equivalent(graph, parent=None):
    """@brief Ouvre la fenêtre de calcul d'impédance équivalente pour `graph`.

    @param graph Graphe analysé (les arêtes R/L/C sont les seules considérées).
    @param parent Fenêtre parente (optionnelle).
    @return None
    """
    bornes = impedance.bornes_possibles(graph)
    win = ctk.CTkToplevel(parent)
    win.title("Impédance équivalente")
    win.geometry("560x340")
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

    resultat = ctk.CTkLabel(win, text="Choisissez deux bornes puis « Calculer ».",
                            font=ctk.CTkFont("Consolas", 13), text_color=TEXT,
                            wraplength=500, justify="left")
    resultat.pack(fill="x", padx=24, pady=(4, 8))

    def _calculer():
        a, b = var_a.get(), var_b.get()
        if a == b:
            resultat.configure(text="Choisissez deux bornes différentes.",
                               text_color="#f59e0b")
            return
        expr = impedance.impedance_equivalente(graph, a, b)
        if expr is None:
            resultat.configure(
                text=f"Réseau non réductible entre {a} et {b} par série/parallèle/Y-Δ\n"
                     "(bornes non reliées par des impédances, ou réseau non planaire).",
                text_color="#f59e0b")
        else:
            resultat.configure(
                text=f"Z({a},{b}) = {impedance.formater_expr(expr)}",
                text_color="#34d399")

    ctk.CTkButton(win, text="Calculer", height=38, corner_radius=8,
                  font=ctk.CTkFont("Segoe UI", 12, "bold"),
                  fg_color="#16a34a", hover_color="#15803d",
                  command=_calculer).pack(padx=24, pady=(4, 16), anchor="w")
