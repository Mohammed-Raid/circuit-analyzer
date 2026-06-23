"""
@file app.py
@brief Point d'entrée de l'interface graphique.

Affiche d'abord un splash (tkinter brut, déjà chargé → instantané) PENDANT le
chargement des libs lourdes (customtkinter, networkx…), puis lance AppWindow.
Sans ça, la fenêtre n'apparaît qu'après ~1,5 s d'imports : l'utilisateur a
l'impression que rien ne se passe.
"""


def _afficher_splash():
    """@brief Petite fenêtre « Chargement… » rendue immédiatement.

    Utilise tkinter brut (pas customtkinter, qui coûte ~1 s à importer). Renvoie
    la fenêtre, à détruire une fois l'app prête, ou None si l'affichage échoue.
    """
    import tkinter as tk
    s = tk.Tk()
    s.overrideredirect(True)                       # sans barre de titre
    s.configure(bg="#0f172a")
    w, h = 380, 170
    x = (s.winfo_screenwidth() - w) // 2
    y = (s.winfo_screenheight() - h) // 2
    s.geometry(f"{w}x{h}+{x}+{y}")
    tk.Label(s, text="⚡", bg="#0f172a", fg="#3b82f6",
             font=("Segoe UI Emoji", 34)).pack(pady=(28, 0))
    tk.Label(s, text="Circuit Analyzer", bg="#0f172a", fg="#f1f5f9",
             font=("Segoe UI", 17, "bold")).pack()
    tk.Label(s, text="Chargement…", bg="#0f172a", fg="#94a3b8",
             font=("Segoe UI", 11)).pack(pady=(6, 0))
    s.update()                                     # force le rendu immédiat
    return s


if __name__ == '__main__':
    try:
        splash = _afficher_splash()
    except Exception:
        splash = None   # l'app doit démarrer même si le splash échoue

    from gui.app_window import AppWindow          # imports lourds (couverts par le splash)
    app = AppWindow()

    if splash is not None:
        splash.destroy()
    app.run()
