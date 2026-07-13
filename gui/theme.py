"""@file theme.py
@brief Jetons de design centralisés (source unique). import : from gui.theme import *"""

# Fonds — élévations croissantes
BG          = "#0a0f1c"
SURFACE     = "#0f172a"
RAISED      = "#182234"
OVERLAY     = "#1e293b"
BORDER      = "#263347"
BORDER_SOFT = "#1c2740"

# Texte (jamais sous TEXT_DIM pour du texte utile)
TEXT        = "#f1f5f9"
TEXT_MUTED  = "#94a3b8"
TEXT_DIM    = "#64748b"

# Marque / accent
BLUE        = "#3b82f6"
BLUE_HOVER  = "#2563eb"
BLUE_PRESS  = "#1d4ed8"
BLUE_SOFT   = "#172554"
CYAN        = "#22d3ee"

# Sémantiques
SUCCESS = "#10b981"
WARN    = "#f59e0b"
ERROR   = "#ef4444"
INFO    = "#3b82f6"

# Échelles
SP   = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}
R    = {"sm": 6, "md": 8, "lg": 12, "xl": 16}
TYPE = {"display": (22, "bold"), "title": (18, "bold"),
        "subtitle": (14, "normal"), "body": (13, "normal"),
        "caption": (11, "normal"), "overline": (9, "bold")}

# Alias rétro-compat (importés tels quels dans app_window, tab_*, etc.)
CARD  = RAISED
CARD2 = SURFACE
MUTED = TEXT_DIM
BLUE_D = BLUE_PRESS

# Neutres / accents supplémentaires (Task 3 — dé-hardcodage circuit_viewer)
WHITE        = "#ffffff"
NEUTRAL      = "#374151"
NEUTRAL_HOVER = "#4b5563"
SUCCESS_SOFT = "#34d399"

from types import MappingProxyType

# ── Schémas (canvas CLAIR — invariant boss : ne jamais assombrir) ──────────
SCHEMA_COLORS = MappingProxyType({
    "SCH_BG":     "#fafafa",   # fond canvas schémas (CLAIR, invariant)
    "WIRE":       "#1e293b",   # fils/encre
    "BUS":        "#475569",   # bus/nets satellites
    "Z_FILL":     "#dbeafe",   # remplissage boîte Z
    "Z_EDGE":     BLUE_HOVER,  # bord boîte Z
    "OPAMP_FILL": "#eef2ff",   # triangle AOP
    "TITRE":      OVERLAY,     # rôle de l'étage
    "GAIN":       "#0f766e",   # gain (teal)
    "LEGENDE":    "#64748b",   # légendes/notes discrètes
    "COMP": MappingProxyType({
        "R": "#1d4ed8", "C": "#0891b2", "L": "#059669", "D": "#dc2626",
        "Q": "#7c3aed", "M": "#6d28d9", "U": "#b45309", "F": "#374151",
    }),
})

SCHEMA_DIMS = MappingProxyType({
    "PAS": 0.5, "MARGE": 1.0, "CANAL_H": 2.0, "CANAL_V": 2.0,
    "X0": 4.5, "PENALITE_COUDE": 1.5,
})
