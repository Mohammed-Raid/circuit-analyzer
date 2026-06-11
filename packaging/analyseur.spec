# -*- mode: python ; coding: utf-8 -*-
"""
analyseur.spec — Build PyInstaller de l'application (onedir partagé).

Deux exécutables dans un seul dossier dist/AnalyseurCircuits/ :
  - AnalyseurCircuits.exe : interface graphique (sans console)
  - analyseur-cli.exe     : ligne de commande (console)

Build : python tools/build_exe.py  (ou : pyinstaller packaging/analyseur.spec)
"""
import os

from PyInstaller.utils.hooks import collect_data_files

RACINE = os.path.abspath(os.path.join(SPECPATH, '..'))

# custom_circuits.loader est importé paresseusement dans analyser() :
# PyInstaller ne le voit pas en scannant les imports de main.py.
_CACHES = ['custom_circuits', 'custom_circuits.loader']

# Assets requis au runtime (thèmes customtkinter, polices schemdraw).
_DONNEES_GUI = collect_data_files('customtkinter') + collect_data_files('schemdraw')

_EXCLUSIONS = ['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'IPython', 'jupyter']


a_gui = Analysis(
    [os.path.join(RACINE, 'app.py')],
    pathex=[RACINE],
    datas=_DONNEES_GUI,
    hiddenimports=_CACHES,
    excludes=_EXCLUSIONS,
    # Seul le backend TkAgg est utilisé (gui/circuit_viewer.py).
    hooksconfig={'matplotlib': {'backends': ['TkAgg']}},
)

a_cli = Analysis(
    [os.path.join(RACINE, 'main.py')],
    pathex=[RACINE],
    hiddenimports=_CACHES,
    excludes=_EXCLUSIONS + ['matplotlib', 'schemdraw', 'customtkinter'],
)

pyz_gui = PYZ(a_gui.pure)
pyz_cli = PYZ(a_cli.pure)

exe_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    [],
    exclude_binaries=True,
    name='AnalyseurCircuits',
    console=False,
)

exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    [],
    exclude_binaries=True,
    name='analyseur-cli',
    console=True,
)

coll = COLLECT(
    exe_gui, a_gui.binaries, a_gui.datas,
    exe_cli, a_cli.binaries, a_cli.datas,
    name='AnalyseurCircuits',
)
