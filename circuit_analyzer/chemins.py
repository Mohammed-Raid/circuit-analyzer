"""
chemins.py — Résolution des chemins de l'application.

Gelée par PyInstaller, l'application vit dans un dossier portable : les
fichiers modifiables par l'utilisateur (config/net_aliases.json,
custom_circuits.json) sont cherchés à côté de l'exe, pas dans le bundle.
"""
import sys
from pathlib import Path


def racine_application() -> Path:
    """
    Racine de l'application :
      - gelée (PyInstaller pose sys.frozen) -> dossier contenant l'exe ;
      - sinon -> racine du projet (parent de circuit_analyzer/).
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent
