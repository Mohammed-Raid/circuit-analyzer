"""@file eretro_symboles.py
@brief Lit la bibliotheque VIVANTE d'ERetroDesign et la rend au format `_FORME`.

Sa bibliotheque = UN <DataItem> complet par composant dans `LibItem/Lib/`,
depuis son [MODIF 2026-07-24] (Form1.cs:6104). NE PAS confondre avec
`bin/Debug/Lib/` : fonds MORT, symboles a ~997x201, sans Name ni typ, dont 2
noms seulement sur les 36 employes par ses vraies cartes.

Aucune dependance AU CHARGEMENT du reste du projet : c'est `xml.py` qui
importe ce module, l'inverse ferait un cycle. `chemin_par_defaut()` importe
`eretro_lib` en LOCAL (dans la fonction) pour le dossier partage GUI, sans
alourdir ce module pour la CLI qui n'en a pas besoin.
"""
import glob
import logging
import os
import xml.etree.ElementTree as ET

_log = logging.getLogger(__name__)

#: Emplacement de sa bibliotheque, relatif a la racine du depot.
DOSSIER_RELATIF = os.path.join("ERetroDesign", "ERetroDesign", "bin", "Debug",
                               "LibItem", "Lib")


def chemin_par_defaut():
    """@brief Dossier de bibliotheque, ou None s'il est introuvable.

    Ordre de priorite :
      1. `ERETRO_LIB` (surcharge developpeur/CI, explicite pour ce process) ;
      2. le dossier memorise via l'onglet Composants (`eretro_lib.
         dossier_partage`, persistant dans config/eretro_biblio.json) —
         reglable a la souris, sans variable d'environnement, et modifiable
         a tout moment ;
      3. le chemin relatif au depot, si present.

    Import de `eretro_lib` fait EN LOCAL (pas en tete de module) : ce module
    est charge par `xml.py`, lui-meme utilise par la CLI, et ne doit pas
    trainer les dependances d'`eretro_lib` (cote GUI) a chaque lancement.
    """
    depuis_env = os.environ.get("ERETRO_LIB")
    if depuis_env:
        return depuis_env
    from circuit_analyzer.eretro_lib import dossier_partage
    depuis_partage = dossier_partage()
    if depuis_partage:
        return depuis_partage
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidat = os.path.join(racine, DOSSIER_RELATIF)
    return candidat if os.path.isdir(candidat) else None


def _fragment(conteneur):
    """@brief Contenu d'un conteneur (<datasegment>...) rendu en CHAINE XML.

    `_FORME` stocke la geometrie en texte, que `_xml_composant` concatene tel
    quel. On rend donc du texte, pas des Element.
    """
    if conteneur is None:
        return ""
    morceaux = []
    for enfant in conteneur:
        enfant.tail = None          # sinon l'indentation du fichier suit
        morceaux.append(ET.tostring(enfant, encoding="unicode").strip())
    return "".join(morceaux)


def _nom_broche(broche, rang):
    """@brief Nom d'une broche : Pnumber, sinon Pname, sinon son rang.

    Ses symboles passifs de l'ANCIEN fonds n'avaient aucun nom de broche ; ceux
    de la bibliotheque vivante en ont, mais on garde le repli plutot que de
    perdre une broche (donc une liaison) sur un symbole mal rempli.
    """
    for balise in ("Pnumber", "Pname"):
        valeur = (broche.findtext(balise) or "").strip()
        if valeur:
            return valeur
    return str(rang + 1)


def _lire_symbole(chemin):
    """@brief Un fichier -> (nom, forme), ou (None, None) s'il est inexploitable."""
    racine = ET.parse(chemin).getroot()
    nom = ((racine.findtext("Name") or "").strip()
           or os.path.splitext(os.path.basename(chemin))[0])
    pins = {}
    for rang, broche in enumerate(racine.findall("./datapin/DataPin")):
        point = broche.find("Pin")
        if point is None:
            _log.warning("%s : DataPin sans <Pin> ignoree (rang %d)",
                        os.path.basename(chemin), rang)
            continue
        pins[_nom_broche(broche, rang)] = (int(point.findtext("X") or 0),
                                           int(point.findtext("Y") or 0), rang)
    if not pins:
        # Un symbole sans broche ne se cable pas : l'admettre ferait disparaitre
        # EN SILENCE toutes les liaisons du composant qui l'utiliserait.
        return None, None
    return nom, {"pins": pins,
                 "polygon": _fragment(racine.find("datapolygon")),
                 "segment": _fragment(racine.find("datasegment")),
                 "arc": _fragment(racine.find("dataarc")),
                 "typ": int((racine.findtext("typ") or "0").strip() or 0)}


def charger(dossier=None):
    """@brief Sa bibliotheque, au format des entrees de `_FORME`.

    @param dossier Dossier a lire ; None -> `chemin_par_defaut()`.
    @return dict nom -> {"pins", "polygon", "segment", "arc", "typ"}.

    NE LEVE JAMAIS. On lit le dossier d'un TIERS : il peut etre absent (CI,
    .exe livre, poste sans le depot C#) ou contenir un fichier a moitie ecrit.
    Un dossier introuvable rend {} et l'appelant garde ses formes maison ; un
    symbole illisible est saute, les autres se chargent.
    """
    dossier = dossier or chemin_par_defaut()
    if not dossier or not os.path.isdir(dossier):
        _log.info("bibliotheque ERetroDesign introuvable (%s) : "
                  "on garde les formes maison", dossier)
        return {}
    formes = {}
    for chemin in sorted(glob.glob(os.path.join(dossier, "*.xml"))):
        try:
            nom, forme = _lire_symbole(chemin)
        except (ET.ParseError, OSError, ValueError) as e:
            _log.warning("symbole %s ignore : %s", os.path.basename(chemin), e)
            continue
        if nom:
            formes[nom] = forme
    _log.info("%d symbole(s) charge(s) depuis %s", len(formes), dossier)
    return formes
