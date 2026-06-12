"""
build_exe.py — Construit la distribution Windows de l'application.

Usage : python tools/build_exe.py

Étapes (arrêt au premier échec) :
  1. Vérifie que PyInstaller est installé.
  2. Build PyInstaller depuis packaging/analyseur.spec -> dist/AnalyseurCircuits/
  3. Copie config/net_aliases.json à côté des exes (fichier éditable).
  4. Test de fumée : analyse de circuits_industriels/relay_driver.xml
     avec l'exe CLI fraîchement compilé.
  5. Zip : dist/AnalyseurCircuits-<VERSION>.zip
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VERSION = '1.1.0'

RACINE = Path(__file__).resolve().parent.parent
DIST = RACINE / 'dist'
DOSSIER_APP = DIST / 'AnalyseurCircuits'


def etape(titre: str) -> None:
    print(f'\n=== {titre} ===', flush=True)


def verifier_pyinstaller() -> None:
    etape('1/5 Vérification de PyInstaller')
    try:
        import PyInstaller
        print(f'PyInstaller {PyInstaller.__version__}')
    except ImportError:
        sys.exit('PyInstaller manquant. Installer avec : pip install pyinstaller')


def build() -> None:
    etape('2/5 Build PyInstaller (plusieurs minutes)')
    if DOSSIER_APP.exists():
        shutil.rmtree(DOSSIER_APP)
    resultat = subprocess.run(
        [sys.executable, '-m', 'PyInstaller',
         str(RACINE / 'packaging' / 'analyseur.spec'),
         '--noconfirm',
         '--distpath', str(DIST),
         '--workpath', str(RACINE / 'build')],
        cwd=RACINE,
    )
    if resultat.returncode != 0:
        sys.exit('Échec du build PyInstaller.')
    for exe in ('AnalyseurCircuits.exe', 'analyseur-cli.exe'):
        if not (DOSSIER_APP / exe).exists():
            sys.exit(f'{exe} absent du dossier de sortie.')


def copier_config() -> None:
    etape('3/5 Copie de config/net_aliases.json (fichier éditable)')
    cible = DOSSIER_APP / 'config'
    cible.mkdir(exist_ok=True)
    shutil.copy2(RACINE / 'config' / 'net_aliases.json', cible / 'net_aliases.json')
    print(f'-> {cible / "net_aliases.json"}')


def test_de_fumee() -> None:
    etape('4/5 Test de fumée (analyse de relay_driver.xml avec l\'exe CLI)')
    with tempfile.TemporaryDirectory() as tmp:
        rapport = Path(tmp) / 'rapport.txt'
        resultat = subprocess.run(
            [str(DOSSIER_APP / 'analyseur-cli.exe'),
             str(RACINE / 'circuits_industriels' / 'relay_driver.xml'),
             '--output', str(rapport)],
            capture_output=True, text=True,
        )
        if resultat.returncode != 0:
            sys.exit(f'Échec du test de fumée :\n{resultat.stdout}\n{resultat.stderr}')
        contenu = rapport.read_text(encoding='utf-8')
        if 'Commande de relais' not in contenu:
            sys.exit('Test de fumée : « Commande de relais » absent du rapport.')
    print('Rapport conforme.')


def zipper() -> Path:
    etape('5/5 Création du zip')
    archive = shutil.make_archive(
        str(DIST / f'AnalyseurCircuits-{VERSION}'), 'zip',
        root_dir=DIST, base_dir='AnalyseurCircuits',
    )
    return Path(archive)


if __name__ == '__main__':
    verifier_pyinstaller()
    build()
    copier_config()
    test_de_fumee()
    archive = zipper()
    taille_mo = archive.stat().st_size / (1024 * 1024)
    print(f'\nDistribution prête : {archive} ({taille_mo:.0f} Mo)')
