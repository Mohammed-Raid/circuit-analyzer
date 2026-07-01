# -*- mode: python ; coding: utf-8 -*-
"""
analyseur.spec — Build PyInstaller de l'application (onedir partagé).

Deux exécutables dans un seul dossier dist/AnalyseurCircuits/ :
  - AnalyseurCircuits.exe : interface graphique (sans console)
  - analyseur-cli.exe     : ligne de commande (console)

Build : python tools/build_exe.py  (ou : pyinstaller packaging/analyseur.spec)
"""
import os
import sys

from PyInstaller.utils.hooks import collect_data_files

RACINE = os.path.abspath(os.path.join(SPECPATH, '..'))
PY_BASE = sys.base_prefix

# Icône de l'exe (Explorateur / barre des tâches) : boîte Z impédance.
_ICONE = os.path.join(SPECPATH, 'app_icon.ico')

# custom_circuits.loader est importé paresseusement dans analyser() :
# PyInstaller ne le voit pas en scannant les imports de main.py.
_CACHES = ['custom_circuits', 'custom_circuits.loader']

# Tkinter est requis par CustomTkinter. Sur l'installation Python 3.14 locale,
# le hook PyInstaller peut considérer Tcl/Tk comme "broken" et l'exclure malgré
# un import tkinter fonctionnel. On force donc le package, l'extension native,
# les DLL Tcl/Tk et les scripts Tcl/Tk dans l'exe GUI.
_TK_HIDDEN = [
    'tkinter',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'tkinter.ttk',
    '_tkinter',
]

_TK_BINARIES = [
    (os.path.join(PY_BASE, 'DLLs', '_tkinter.pyd'), '.'),
    (os.path.join(PY_BASE, 'DLLs', 'tcl86t.dll'), '.'),
    (os.path.join(PY_BASE, 'DLLs', 'tk86t.dll'), '.'),
]

_TK_DATAS = [
    (os.path.join(PY_BASE, 'Lib', 'tkinter'), 'tkinter'),
    # Ces noms doivent correspondre aux constantes attendues par
    # PyInstaller/hooks/rthooks/pyi_rth__tkinter.py.
    (os.path.join(PY_BASE, 'tcl', 'tcl8.6'), '_tcl_data'),
    (os.path.join(PY_BASE, 'tcl', 'tk8.6'), '_tk_data'),
]

# Assets requis au runtime (thèmes customtkinter, polices schemdraw).
_DONNEES_GUI = collect_data_files('customtkinter') + collect_data_files('schemdraw') + _TK_DATAS

# Assets : polices et icônes pour la vague 2 (Dark Premium).
_ASSETS = [
    (os.path.join(RACINE, 'assets', 'fonts'), 'assets/fonts'),
    (os.path.join(RACINE, 'assets', 'icons'), 'assets/icons'),
]

_EXCLUSIONS = ['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'IPython', 'jupyter']


a_gui = Analysis(
    [os.path.join(RACINE, 'app.py')],
    pathex=[RACINE],
    datas=_DONNEES_GUI + _ASSETS,
    binaries=_TK_BINARIES,
    hiddenimports=_CACHES + _TK_HIDDEN,
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
    icon=_ICONE,
)

exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    [],
    exclude_binaries=True,
    name='analyseur-cli',
    console=True,
    icon=_ICONE,
)

coll = COLLECT(
    exe_gui, a_gui.binaries, a_gui.datas,
    exe_cli, a_cli.binaries, a_cli.datas,
    name='AnalyseurCircuits',
)
