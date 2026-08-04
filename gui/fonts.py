"""@file fonts.py
@brief Enregistrement privé (sans installation système) de la police Inter.
Windows : AddFontResourceEx(FR_PRIVATE). Fallback Segoe UI si absent/échec."""
import ctypes
import os
import sys

FONT_FAMILY = "Segoe UI"


def _assets_dir() -> str:
    # PyInstaller onedir : les assets sont à côté de l'exe (_MEIPASS) ou du package.
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base, "assets", "fonts")


def register_fonts() -> str:
    global FONT_FAMILY
    d = _assets_dir()
    ttfs = [os.path.join(d, f) for f in ("Inter-Regular.ttf", "Inter-Medium.ttf",
            "Inter-SemiBold.ttf", "Inter-Bold.ttf")]
    if sys.platform == "win32" and all(os.path.exists(p) for p in ttfs):
        FR_PRIVATE = 0x10
        ok = all(ctypes.windll.gdi32.AddFontResourceExW(ctypes.c_wchar_p(p), FR_PRIVATE, 0)
                 for p in ttfs)
        if ok:
            FONT_FAMILY = "Inter"
    return FONT_FAMILY


# Tailles de police des schémas (valeurs historiques, juste nommées).
SCHEMA_FONTSIZES = {"label": 9, "titre": 11, "gain": 8, "legende": 9}
