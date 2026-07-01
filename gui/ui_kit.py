"""@file ui_kit.py
@brief Kit de widgets réutilisables (Dark Premium). Consomme gui.theme et gui.fonts.

Toutes les fabriques retournent des widgets CTk configurés avec les jetons de design ;
aucune hiérarchie de classes — factories fines sur CTk (cf. contrainte PONYTAIL)."""
import os
import sys

import customtkinter as ctk

from gui import theme
from gui.fonts import FONT_FAMILY


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _icons_dir() -> str:
    """Résout le répertoire assets/icons sous PyInstaller (_MEIPASS) et en source."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base, "assets", "icons")


_ICON_CACHE: dict = {}


# ---------------------------------------------------------------------------
# Fabriques publiques
# ---------------------------------------------------------------------------

def font(role: str, weight: str | None = None) -> ctk.CTkFont:
    """Retourne un CTkFont Inter configuré depuis theme.TYPE[role].

    @param role  Clé dans theme.TYPE (display/title/subtitle/body/caption/overline).
    @param weight Surcharge de la graisse ; None → valeur du token.
    @return ctk.CTkFont prêt à l'emploi.
    """
    size, w = theme.TYPE[role]
    return ctk.CTkFont(FONT_FAMILY, size, weight or w)


def icon(name: str, size: int = 20, color: str | None = None) -> ctk.CTkImage:
    """Charge et cache une icône PNG depuis assets/icons/.

    @param name  Nom du fichier sans extension (ex. "search").
    @param size  Côté carré en pixels logiques (défaut 20).
    @param color Accepté pour compatibilité future, ignoré (YAGNI — PNGs déjà teintés).
    @return ctk.CTkImage mis en cache par (name, size).
    """
    from PIL import Image  # import local : PIL non obligatoire pour les tests sans GUI

    key = (name, size)
    if key not in _ICON_CACHE:
        d = _icons_dir()
        p1 = os.path.join(d, f"{name}.png")
        p2 = os.path.join(d, f"{name}@2x.png")
        img = Image.open(p1)
        img2 = Image.open(p2) if os.path.exists(p2) else img
        _ICON_CACHE[key] = ctk.CTkImage(light_image=img2, dark_image=img2,
                                        size=(size, size))
    return _ICON_CACHE[key]


def Card(parent, **kw) -> ctk.CTkFrame:
    """Carte de surface élevée avec bordure douce.

    @param parent Widget parent Tk/CTk.
    @param **kw   Surcharges CTkFrame (fg_color, corner_radius, …).
    @return ctk.CTkFrame configuré.
    """
    kw.setdefault("fg_color", theme.RAISED)
    kw.setdefault("border_color", theme.BORDER_SOFT)
    kw.setdefault("border_width", 1)
    kw.setdefault("corner_radius", theme.R["lg"])
    return ctk.CTkFrame(parent, **kw)


def StatCard(parent, value: str, label: str,
             icon_name: str, accent: str) -> ctk.CTkFrame:
    """Carte statistique : valeur numérique + libellé + icône accentuée.

    @param parent    Widget parent.
    @param value     Valeur à afficher (ex. "17").
    @param label     Libellé descriptif (ex. "Composants").
    @param icon_name Nom de l'icône (ex. "cpu").
    @param accent    Couleur d'accent hexadécimale (ex. "#3b82f6").
    @return ctk.CTkFrame composé.
    """
    frame = Card(parent, fg_color=theme.RAISED)
    frame.grid_columnconfigure(0, weight=1)

    # Icône + valeur
    top = ctk.CTkFrame(frame, fg_color="transparent")
    top.pack(fill="x", padx=theme.SP["md"], pady=(theme.SP["md"], 0))

    ctk.CTkLabel(top, image=icon(icon_name, 20), text="",
                 width=20).pack(side="left")
    ctk.CTkLabel(top, text=value,
                 font=font("display"), text_color=accent).pack(side="right")

    # Libellé
    ctk.CTkLabel(frame, text=label,
                 font=font("caption"), text_color=theme.TEXT_MUTED,
                 anchor="w").pack(fill="x", padx=theme.SP["md"],
                                  pady=(2, theme.SP["md"]))
    return frame


def PrimaryButton(parent, text: str, command,
                  icon_name: str | None = None, **kw) -> ctk.CTkButton:
    """Bouton d'action principale (fond BLUE).

    @param parent    Widget parent.
    @param text      Libellé.
    @param command   Callback.
    @param icon_name Icône optionnelle à gauche du texte.
    @param **kw      Surcharges CTkButton.
    @return ctk.CTkButton configuré.
    """
    kw.setdefault("height", 34)
    kw.setdefault("corner_radius", theme.R["md"])
    kw.setdefault("font", font("body", "bold"))
    kw.setdefault("fg_color", theme.BLUE)
    kw.setdefault("hover_color", theme.BLUE_HOVER)
    kw.setdefault("text_color", theme.TEXT)
    img = icon(icon_name, 18) if icon_name else None
    return ctk.CTkButton(parent, text=text, command=command, image=img, **kw)


def SecondaryButton(parent, text: str, command,
                    icon_name: str | None = None, **kw) -> ctk.CTkButton:
    """Bouton secondaire (fond RAISED + bordure BORDER).

    @param parent    Widget parent.
    @param text      Libellé.
    @param command   Callback.
    @param icon_name Icône optionnelle.
    @param **kw      Surcharges CTkButton.
    @return ctk.CTkButton configuré.
    """
    kw.setdefault("height", 34)
    kw.setdefault("corner_radius", theme.R["md"])
    kw.setdefault("font", font("body"))
    kw.setdefault("fg_color", theme.RAISED)
    kw.setdefault("hover_color", theme.OVERLAY)
    kw.setdefault("border_color", theme.BORDER)
    kw.setdefault("border_width", 1)
    kw.setdefault("text_color", theme.TEXT)
    img = icon(icon_name, 18) if icon_name else None
    return ctk.CTkButton(parent, text=text, command=command, image=img, **kw)


def GhostButton(parent, text: str, command,
                icon_name: str | None = None, **kw) -> ctk.CTkButton:
    """Bouton fantôme (transparent, texte MUTED).

    @param parent    Widget parent.
    @param text      Libellé.
    @param command   Callback.
    @param icon_name Icône optionnelle.
    @param **kw      Surcharges CTkButton.
    @return ctk.CTkButton configuré.
    """
    kw.setdefault("height", 34)
    kw.setdefault("corner_radius", theme.R["md"])
    kw.setdefault("font", font("body"))
    kw.setdefault("fg_color", "transparent")
    kw.setdefault("hover_color", theme.OVERLAY)
    kw.setdefault("text_color", theme.TEXT_MUTED)
    img = icon(icon_name, 18) if icon_name else None
    return ctk.CTkButton(parent, text=text, command=command, image=img, **kw)


def DangerButton(parent, text: str, command,
                 icon_name: str | None = None, **kw) -> ctk.CTkButton:
    """Bouton de danger (fond ERROR).

    @param parent    Widget parent.
    @param text      Libellé.
    @param command   Callback.
    @param icon_name Icône optionnelle.
    @param **kw      Surcharges CTkButton.
    @return ctk.CTkButton configuré.
    """
    kw.setdefault("height", 34)
    kw.setdefault("corner_radius", theme.R["md"])
    kw.setdefault("font", font("body", "bold"))
    kw.setdefault("fg_color", theme.ERROR)
    kw.setdefault("hover_color", "#dc2626")
    kw.setdefault("text_color", theme.TEXT)
    img = icon(icon_name, 18) if icon_name else None
    return ctk.CTkButton(parent, text=text, command=command, image=img, **kw)


def IconButton(parent, icon_name: str, command, **kw) -> ctk.CTkButton:
    """Bouton carré ghost avec icône seule (pas de texte).

    @param parent    Widget parent.
    @param icon_name Icône (ex. "trash-2").
    @param command   Callback.
    @param **kw      Surcharges CTkButton.
    @return ctk.CTkButton carré configuré.
    """
    kw.setdefault("width", 34)
    kw.setdefault("height", 34)
    kw.setdefault("corner_radius", theme.R["md"])
    kw.setdefault("fg_color", "transparent")
    kw.setdefault("hover_color", theme.OVERLAY)
    kw.setdefault("text_color", theme.TEXT_MUTED)
    return ctk.CTkButton(parent, text="", command=command,
                         image=icon(icon_name, 18), **kw)


def SectionHeader(parent, text: str) -> ctk.CTkLabel:
    """Libellé d'en-tête de section (overline, TEXT_DIM, majuscules).

    @param parent Widget parent.
    @param text   Texte — sera affiché en majuscules.
    @return ctk.CTkLabel configuré.
    """
    return ctk.CTkLabel(parent, text=text.upper(),
                        font=font("overline"), text_color=theme.TEXT_DIM,
                        anchor="w")


def Field(parent, textvariable=None, placeholder: str = "", **kw) -> ctk.CTkEntry:
    """Champ de saisie thématisé.

    @param parent       Widget parent.
    @param textvariable Variable Tk associée (optionnel).
    @param placeholder  Texte indicatif affiché quand le champ est vide.
    @param **kw         Surcharges CTkEntry.
    @return ctk.CTkEntry configuré.
    """
    kw.setdefault("height", 34)
    kw.setdefault("corner_radius", theme.R["md"])
    kw.setdefault("font", font("body"))
    kw.setdefault("fg_color", theme.OVERLAY)
    kw.setdefault("border_color", theme.BORDER)
    kw.setdefault("border_width", 1)
    kw.setdefault("text_color", theme.TEXT)
    kw.setdefault("placeholder_text_color", theme.TEXT_DIM)
    return ctk.CTkEntry(parent, textvariable=textvariable,
                        placeholder_text=placeholder, **kw)
