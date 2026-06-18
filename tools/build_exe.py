"""
@file build_exe.py
@brief Construit la distribution Windows de l'application.

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

RACINE = Path(__file__).resolve().parent.parent
DIST = RACINE / 'dist'
DOSSIER_APP = DIST / 'AnalyseurCircuits'


def _lire_version() -> str:
    """@brief Lit la version depuis circuit_analyzer/__init__.py (source unique).

    Parse le fichier sans importer le package (évite de charger ses dépendances
    juste pour un numéro de version).

    @return str Version (ex. '1.5.0'), ou '0.0.0' si introuvable.
    """
    init = RACINE / 'circuit_analyzer' / '__init__.py'
    for ligne in init.read_text(encoding='utf-8').splitlines():
        if ligne.strip().startswith('__version__'):
            return ligne.split('=', 1)[1].strip().strip('"').strip("'")
    return '0.0.0'


VERSION = _lire_version()


def etape(titre: str) -> None:
    """@brief Affiche un titre d'étape de build.
    @param titre Libellé de l'étape.
    @return None
    """
    print(f'\n=== {titre} ===', flush=True)


def verifier_pyinstaller() -> None:
    """@brief Vérifie que PyInstaller est installé (arrête le build sinon)."""
    etape('1/5 Vérification de PyInstaller')
    try:
        import PyInstaller
        print(f'PyInstaller {PyInstaller.__version__}')
    except ImportError:
        sys.exit('PyInstaller manquant. Installer avec : pip install pyinstaller')


def _processus_verrouillant() -> list:
    """@brief Best-effort : processus dont l'exe est sous DOSSIER_APP (via psutil).

    @return list[tuple] Liste de (pid, nom) ; vide si psutil absent ou rien trouvé.
    """
    try:
        import psutil
    except ImportError:
        return []
    cible = str(DOSSIER_APP).lower()
    trouves = []
    for p in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            exe = (p.info.get('exe') or '').lower()
            if exe and cible in exe:
                trouves.append((p.info['pid'], p.info['name']))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return trouves


def liberer_dossier_app() -> None:
    """@brief Supprime l'ancienne distribution ; message clair si elle est verrouillée.

    Remplace l'ancien rmtree(ignore_errors=True) qui masquait un verrou : ici on
    échoue tôt avec un message actionnable plutôt que de laisser PyInstaller
    planter avec une stack trace cryptique à l'étape COLLECT.
    """
    if not DOSSIER_APP.exists():
        return
    try:
        shutil.rmtree(DOSSIER_APP)
    except PermissionError as e:
        verrou = getattr(e, 'filename', '') or str(e)
        procs = _processus_verrouillant()
        details = ''
        if procs:
            details = '\n  Processus à fermer : ' + ', '.join(
                f'{nom} (PID {pid})' for pid, nom in procs)
        sys.exit(
            "Impossible de supprimer l'ancienne distribution (fichier verrouillé) :\n"
            f"  {verrou}\n"
            "Une instance d'AnalyseurCircuits.exe est probablement encore ouverte, "
            "ou le dossier dist/ est ouvert dans l'Explorateur."
            f"{details}\n"
            "Fermez-la puis relancez : python tools/build_exe.py"
        )


def build() -> None:
    """@brief Lance PyInstaller depuis le .spec et vérifie la présence des exes produits."""
    etape('2/5 Build PyInstaller (plusieurs minutes)')
    liberer_dossier_app()
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
    """@brief Copie config/net_aliases.json et circuits_industriels/ à côté des exes."""
    etape('3/5 Copie de config/net_aliases.json (fichier éditable)')
    cible_cfg = DOSSIER_APP / 'config'
    cible_cfg.mkdir(exist_ok=True)
    shutil.copy2(RACINE / 'config' / 'net_aliases.json', cible_cfg / 'net_aliases.json')
    print(f'-> {cible_cfg / "net_aliases.json"}')

    src_ci = RACINE / 'circuits_industriels'
    if src_ci.exists():
        cible_ci = DOSSIER_APP / 'circuits_industriels'
        if cible_ci.exists():
            shutil.rmtree(cible_ci)
        shutil.copytree(src_ci, cible_ci)
        print(f'-> {cible_ci} ({len(list(cible_ci.iterdir()))} fichiers)')


def test_de_fumee() -> None:
    """@brief Test de fumée : analyse relay_driver.xml avec l'exe CLI fraîchement compilé."""
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
    """@brief Crée l'archive zip de la distribution.
    @return Path Chemin de l'archive créée.
    """
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
