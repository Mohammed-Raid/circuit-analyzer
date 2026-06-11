"""Tests de circuit_analyzer/chemins.py — résolution de la racine de
l'application en mode normal et en mode gelé (PyInstaller)."""
import sys
from pathlib import Path

from circuit_analyzer import chemins
from custom_circuits import loader


def test_racine_application_mode_normal():
    # Hors gel : la racine du projet (contient circuit_analyzer/ et config/)
    racine = chemins.racine_application()
    assert (racine / 'circuit_analyzer').is_dir()
    assert (racine / 'main.py').is_file()


def test_racine_application_mode_gele(monkeypatch):
    # Gelé par PyInstaller : sys.frozen est posé, la racine est le dossier de l'exe.
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable',
                        r'C:\Apps\AnalyseurCircuits\AnalyseurCircuits.exe')
    assert chemins.racine_application() == Path(r'C:\Apps\AnalyseurCircuits')


def test_chemin_custom_circuits_suit_la_racine(monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable',
                        r'C:\Apps\AnalyseurCircuits\AnalyseurCircuits.exe')
    assert loader.chemin_custom_circuits() == \
        Path(r'C:\Apps\AnalyseurCircuits\custom_circuits.json')


def test_chemin_custom_circuits_mode_normal():
    # Hors gel : custom_circuits.json à la racine du projet, plus au CWD.
    assert loader.chemin_custom_circuits() == \
        chemins.racine_application() / 'custom_circuits.json'
