"""@file eretro_lib.py
@brief Partage de composants avec la bibliotheque ERetroDesign (paquet LibraryBundle).

Un composant cree dans l'onglet Composants (nom, broches, brochage cote+decalage,
boite) s'exporte en un fichier .xml au format `LibraryBundle` d'ERetroDesign,
que l'on relit chez le collegue via « Importer la bibliotheque ». Inversement, un
paquet exporte par ERetroDesign (« Exporter la bibliotheque ») se relit ici. Les
deux sens passent par le MEME modele boite+broches, d'ou un aller-retour exact.

@note Convention CALEE SUR LE SOURCE C# d'ERetroDesign (pas devinee) :
- La palette se charge depuis `LibItem/Lib.xml`, PAS depuis des fichiers Lib/<Nom>.xml
  isoles. Pour ajouter un composant, ERetroDesign lit un `LibraryBundle`
  (`{List<DataItem> Items; List<CComp> CComps}`) via `ImportLibrary` — d'ou
  l'enrobage OBLIGATOIRE en <LibraryBundle> (un <DataItem> nu s'importe VIDE).
- Un DataItem porte Name + geometrie ; CtrIem/TL/BR restent nuls, recalcules au
  placement (Form1.InsertItem, qui force zmH=zmV=1).
- Le dessin place une broche a `CtrIem + Pin*zoom` (FDraw.Pinp) : Pin est un
  DECALAGE par rapport au centre -> geometrie centree sur (0,0), symbole sur le
  curseur. Seul CtrIem est accroche a la grille (Snap, GridStep=10) ; nos broches
  tombent sur des multiples de 10 -> cablage propre.
"""
import math
import os
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from gui.schematic_symbols import aimanter_bord, geometrie_libre, primitives_depuis_dataitem

# Unites ERetroDesign par pixel de l'editeur ; geometrie CENTREE sur (0,0).
# ECHELLE=1 : les vrais symboles de Lib.xml sont centres avec des coords ~±48..80
# (Capa 96x96, AOP/Resistance 160 de large). La vignette de la palette
# (pictureBox2_Paint) dessine `CtrIem_cellule + coord` dans une cellule de 146 px :
# une echelle trop grande sort de la cellule -> vignette VIDE (composant « pas
# importable »). Notre boite ~80x60 px tombe pile dans cette plage.
ECHELLE = 1
GRILLE = 20

# Boite CLIQUABLE d'une vignette de palette (coordonnees pixel de pictureBox2 ;
# la ligne courante ajoute 146*c en Y). Le clic teste litteralement
# `e.X > TL.X && e.X < BR.X && e.Y > TL.Y + 146*c && e.Y < BR.Y + 146*c`
# (Form1.pictureBox2_MouseDown) : a TL=BR=(0,0) la condition est TOUJOURS
# fausse -> le composant s'affiche dans la palette mais est IMPOSSIBLE a
# selectionner, donc a poser. Les 12 symboles de LibItem/Lib.xml portent tous
# exactement ces deux valeurs.
_CLIC_TL = (50, 25)
_CLIC_BR = (210, 121)

_ENTETE_XSD = ('xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
               'xmlns:xsd="http://www.w3.org/2001/XMLSchema"')


def _pinout(entree):
    """@brief brochage {nom:[cote,dec]} -> {nom:(cote,dec)} pour geometrie_libre."""
    br = entree.get("brochage") or {}
    return {nom: (cote, dec) for nom, (cote, dec) in br.items()}


def _dataitem_fragment(prefix, entree):
    """@brief Fragment <DataItem> (geometrie centree) — sans declaration XML."""
    pinout = _pinout(entree)
    boite = entree.get("boite") or {}
    geo = geometrie_libre(pinout, boite.get("w"), boite.get("h"))
    w, h = geo["w"], geo["h"]

    def abs_pt(dx, dy):
        # Centre a l'origine : Pin = decalage / CtrIem (=0 dans un symbole Lib).
        return int(round(dx * ECHELLE)), int(round(dy * ECHELLE))

    x0, y0 = abs_pt(-w / 2, -h / 2)
    x1, y1 = abs_pt(w / 2, h / 2)

    def seg(xa, ya, xb, yb):
        return (f"<DataSegment><Spoint><X>{xa}</X><Y>{ya}</Y></Spoint>"
                f"<Epoint><X>{xb}</X><Y>{yb}</Y></Epoint>"
                f"<SPtGap><X>0</X><Y>0</Y></SPtGap>"
                f"<EPtGap><X>0</X><Y>0</Y></EPtGap>"
                f"<ESelected>false</ESelected><SSelected>false</SSelected></DataSegment>")

    # Boite = 4 aretes du rectangle.
    segments = "".join([
        seg(x0, y0, x1, y0), seg(x1, y0, x1, y1),
        seg(x1, y1, x0, y1), seg(x0, y1, x0, y0),
    ])

    broches = []
    for nom, (dx, dy) in geo["pins"].items():
        px, py = abs_pt(dx, dy)
        broches.append(
            f"<DataPin><Pname>{escape(str(nom))}</Pname>"
            f"<Pnumber>{escape(str(nom))}</Pnumber>"
            f"<Pin><X>{px}</X><Y>{py}</Y></Pin>"
            f"<PinGap><X>0</X><Y>0</Y></PinGap><Size>9</Size>"
            f"<Selected>false</Selected>"
            f"<ShowNbTxt>true</ShowNbTxt><ShowNmTxt>false</ShowNmTxt></DataPin>")

    nom_symbole = entree.get("name") or prefix
    valeur = entree.get("default_value", "") or ""
    return (
        f"<DataItem>"
        f"<Name>{escape(nom_symbole)}</Name><Group>{escape(prefix)}</Group>"
        f"<reference /><value>{escape(valeur)}</value>"
        f"<datapolygon /><datasegment>{segments}</datasegment><dataarc />"
        f"<datapin>{''.join(broches)}</datapin>"
        # CtrIem nul : recalcule a chaque rendu de palette (pictureBox2_Paint).
        # TL/BR, EUX, NE SONT PAS NULS : c'est la boite CLIQUABLE de la vignette
        # (cf. _CLIC_*), pas la geometrie du symbole.
        "<CtrIem><X>0</X><Y>0</Y></CtrIem>"
        f"<TL><X>{_CLIC_TL[0]}</X><Y>{_CLIC_TL[1]}</Y></TL>"
        f"<BR><X>{_CLIC_BR[0]}</X><Y>{_CLIC_BR[1]}</Y></BR>"
        "<angle>0</angle><id>0</id><selected>false</selected>"
        "<focus>false</focus><Visible>true</Visible></DataItem>")


def composant_vers_symbole_xml(prefix, entree):
    """@brief Composant importable par ERetroDesign (bouton « Importer composant »).

    Racine = <DataItem> NU, et non un <LibraryBundle> : `ImportComponent`
    aiguille sur le NOM DE LA RACINE et n'y connait que ArrayOfDataItem /
    ArrayOfCComp / CComp, tout le reste partant en deserialisation `DataItem`
    (un LibraryBundle y echoue). Ce meme fichier reste accepte par « Importer
    bibliotheque » (branche root == "DataItem") : un seul format pour les deux.

    @param prefix Prefixe de type ('IC'...) ; conserve dans <Group> (aller-retour).
    @param entree {name, pins, brochage{nom:[cote,dec]}, boite{w,h}, default_value}.
    @return str Document XML <DataItem> autonome (un composant simple).
    """
    fragment = _dataitem_fragment(prefix, entree)
    # L'entete xsi/xsd va sur la RACINE : c'est ce qu'ecrit le C# (SeveXMLFile).
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            + fragment.replace("<DataItem>", f"<DataItem {_ENTETE_XSD}>", 1))


_INTERDITS_FICHIER = '/\\:*?"<>|'


def _nom_fichier(nom, pris):
    """@brief Nom de fichier sur pour un composant (unique dans `pris`).

    Le nom du composant reste INTACT dans le XML : seul le nom de FICHIER est
    assaini. C'est `<Name>` qui identifie le composant cote C#, pas le fichier.
    """
    base = "".join("_" if c in _INTERDITS_FICHIER else c for c in (nom or "")).strip()
    base = base or "composant"
    candidat, n = base, 2
    while candidat.lower() in pris:
        candidat, n = f"{base} ({n})", n + 1
    pris.add(candidat.lower())
    return candidat


def ecrire_dans_dossier(dossier, composants):
    """@brief Ecrit un `<DataItem>.xml` par composant dans le dossier partage.

    C'est le format de `LibItem/Lib` cote ERetroDesign (un fichier par
    composant depuis 2026-07-24) : le C# relit tout le dossier au demarrage.

    @warning On n'EFFACE JAMAIS le dossier, contrairement au C#
        (`SaveSimpleLibToDisk` supprime tous les .xml avant de reecrire depuis
        sa liste en memoire). Un envoi depuis notre app ne doit pas detruire la
        bibliotheque du collegue : on ecrase uniquement nos propres noms.

    @warning Les composants COMPOSES (`entree["compose"]`, venus de `CCLib`)
        sont IGNORES : cette fonction ne sait ecrire que des <DataItem>, et
        recopier un compose ici l'aplatirait dans `Lib` alors que son original
        vit dans `CCLib` -- doublon dans la palette du collegue, entrailles
        perdues. L'appelant deduit le nombre d'ignores de `len(composants) -
        len(retour)` pour le dire a l'utilisateur.

    @param dossier Dossier cible (cree s'il manque).
    @param composants Iterable de (prefix, entree).
    @return list[str] Chemins ecrits.
    """
    os.makedirs(dossier, exist_ok=True)
    pris, ecrits = set(), []
    for prefix, entree in composants:
        if entree.get("compose"):
            continue
        chemin = os.path.join(dossier,
                              _nom_fichier(entree.get("name") or prefix, pris) + ".xml")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(composant_vers_symbole_xml(prefix, entree))
        ecrits.append(chemin)
    return ecrits


def ecrire_formes_dans_dossier(dossier, formes, typs=None):
    """@brief Pousse nos formes `_FORME` dans sa bibliotheque, geometrie verbatim.

    A ne pas confondre avec `ecrire_dans_dossier`, qui part du modele
    boite+brochage de l'onglet Composants et REGENERE une boite generique :
    l'employer ici perdrait nos dessins (zigzag de resistance, triangle d'AOP).

    @warning N'ECRASE JAMAIS un fichier existant. Sa bibliotheque est son
        travail ; on ne pousse que ce qui lui manque. Un nom deja pris est
        saute et n'apparait pas dans le retour.

    @param dossier Dossier `LibItem/Lib` cible (cree s'il manque).
    @param formes dict nom -> entree `_FORME` (`pins`, `polygon`, `segment`, `arc`).
    @param typs dict nom -> `typ` entier, ou None.
    @return list[str] Chemins reellement ecrits.
    """
    os.makedirs(dossier, exist_ok=True)
    typs = typs or {}
    ecrits = []
    for nom, forme in sorted(formes.items()):
        chemin = os.path.join(dossier, _nom_fichier(nom, set()) + ".xml")
        if os.path.exists(chemin):
            continue
        broches = "".join(
            f"<DataPin><Pname>{escape(str(b))}</Pname>"
            f"<Pnumber>{escape(str(b))}</Pnumber>"
            f"<Pin><X>{x}</X><Y>{y}</Y></Pin>"
            f"<PinGap><X>0</X><Y>0</Y></PinGap><Size>9</Size>"
            f"<Selected>false</Selected><ShowNbTxt>false</ShowNbTxt>"
            f"<ShowNmTxt>false</ShowNmTxt><VltgP>0</VltgP><typ>0</typ></DataPin>"
            for b, (x, y, _rang) in sorted(forme["pins"].items(),
                                           key=lambda kv: kv[1][2]))
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(
                '<?xml version="1.0" encoding="utf-8"?>\n'
                f'<DataItem {_ENTETE_XSD}>'
                f"<Name>{escape(nom)}</Name><Group /><reference /><value />"
                f'<datapolygon>{forme.get("polygon", "")}</datapolygon>'
                f'<datasegment>{forme.get("segment", "")}</datasegment>'
                f'<dataarc>{forme.get("arc", "")}</dataarc>'
                f"<datapin>{broches}</datapin><PinCL />"
                f"<CtrIem><X>0</X><Y>0</Y></CtrIem><pgap><X>0</X><Y>0</Y></pgap>"
                f"<TL><X>{_CLIC_TL[0]}</X><Y>{_CLIC_TL[1]}</Y></TL>"
                f"<BR><X>{_CLIC_BR[0]}</X><Y>{_CLIC_BR[1]}</Y></BR>"
                f"<angle>0</angle><id>0</id><GpId>0</GpId>"
                f"<zmH>1</zmH><zmV>1</zmV><FlipX>n</FlipX><FlipY>n</FlipY>"
                f"<typ>{int(typs.get(nom, 0))}</typ>"
                f"<Bottom>false</Bottom><selected>false</selected>"
                f"<focus>false</focus><Visible>true</Visible><Top>true</Top>"
                f"<Begrp>false</Begrp><freeze>false</freeze></DataItem>")
        ecrits.append(chemin)
    return ecrits


def _dossiers_bibliotheque(dossier):
    """@brief Dossiers à balayer pour une bibliothèque ERetroDesign.

    Côté C#, simples et composés vivent dans DEUX dossiers frères
    (`LibItem/Lib` et `LibItem/CCLib`). Désigner l'un ne doit pas faire rater
    l'autre en silence : on prend le dossier choisi, ses sous-dossiers, et le
    frère `CCLib`/`Lib` quand on a désigné l'autre.
    """
    # UNIQUEMENT les deux sous-dossiers de bibliothèque connus : `LibItem`
    # contient aussi des ARCHIVES (`Archiv`, `Save<date>`…) pleines de vieux
    # agrégats — les balayer ramènerait des centaines de composants périmés.
    dossiers = [dossier]
    for sous in sorted(os.listdir(dossier)):
        chemin = os.path.join(dossier, sous)
        if os.path.isdir(chemin) and sous.lower() in ("lib", "cclib"):
            dossiers.append(chemin)
    parent, base = os.path.dirname(dossier.rstrip("/\\")), os.path.basename(
        dossier.rstrip("/\\")).lower()
    frere = {"lib": "CCLib", "cclib": "Lib"}.get(base)
    if frere and parent:
        chemin = os.path.join(parent, frere)
        if os.path.isdir(chemin) and chemin not in dossiers:
            dossiers.append(chemin)
    return dossiers


def _chemin_config():
    """@brief Fichier retenant le dossier de bibliotheque partagee."""
    from circuit_analyzer.chemins import racine_application
    return racine_application() / "config" / "eretro_biblio.json"


def dossier_partage():
    """@brief Dossier de bibliotheque partagee memorise, ou None."""
    import json
    chemin = _chemin_config()
    try:
        with open(chemin, encoding="utf-8") as f:
            valeur = (json.load(f) or {}).get("dossier") or None
    except (OSError, ValueError):
        return None
    # Un dossier disparu (cle USB retiree, appli deplacee) ne doit pas faire
    # croire a une configuration valide.
    return valeur if valeur and os.path.isdir(valeur) else None


def definir_dossier_partage(dossier):
    """@brief Memorise le dossier de bibliotheque partagee."""
    import json
    chemin = _chemin_config()
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump({"dossier": str(dossier)}, f, ensure_ascii=False, indent=2)


def _racine(source):
    """@brief Element racine depuis un chemin, une chaine XML, ou un Element."""
    if isinstance(source, ET.Element):
        return source
    texte = source
    if "<" not in str(source):                 # chemin de fichier
        with open(source, encoding="utf-8") as f:
            texte = f.read()
    return ET.fromstring(texte)


def _entree_depuis_dataitem(r):
    """@brief Convertit un element <DataItem> en (prefix, entree bibliotheque).

    `coords` doit couvrir TOUTE la geometrie visible (segments -- pattes --,
    ET polygones/arcs -- le corps du symbole), pas seulement les segments :
    un symbole dont le corps est un polygone loin de sa patte (ex. Vss, VCC+)
    aurait sinon un centre et une boite calcules sur la seule patte, minuscule
    et hors-corps -- broche qui flotte, loin de la forme reelle une fois celle-ci
    dessinee (spec 2026-08-05, defaut trouve en boucle visuelle apres livraison).
    """
    coords = []
    for s in r.findall("./datasegment/DataSegment"):
        for tag in ("Spoint", "Epoint"):
            e = s.find(tag)
            if e is not None:
                coords.append((float(e.findtext("X") or 0), float(e.findtext("Y") or 0)))
    for pg in r.findall("./datapolygon/DataPolygon"):
        pt = pg.find("point")
        if pt is not None:
            coords.append((float(pt.findtext("X") or 0), float(pt.findtext("Y") or 0)))
    for a in r.findall("./dataarc/DataArc"):
        c, sp = a.find("pCenter"), a.find("Spoint")
        if c is not None and sp is not None:
            acx, acy = float(c.findtext("X") or 0), float(c.findtext("Y") or 0)
            rayon = math.hypot(float(sp.findtext("X") or 0) - acx,
                               float(sp.findtext("Y") or 0) - acy)
            coords.append((acx - rayon, acy - rayon))
            coords.append((acx + rayon, acy + rayon))
    pins_xy = []
    for dp in r.findall("./datapin/DataPin"):
        p = dp.find("Pin")
        nom = (dp.findtext("Pname") or dp.findtext("Pnumber") or "").strip()
        if p is not None:
            pins_xy.append((nom, float(p.findtext("X") or 0), float(p.findtext("Y") or 0)))
    if not coords:
        coords = [(x, y) for _n, x, y in pins_xy]
    if not coords:
        raise ValueError("Symbole sans geometrie ni broche")

    xs = [x for x, _y in coords]
    ys = [y for _x, y in coords]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    w = max(GRILLE, int(round((max(xs) - min(xs)) / ECHELLE / GRILLE)) * GRILLE)
    h = max(GRILLE, int(round((max(ys) - min(ys)) / ECHELLE / GRILLE)) * GRILLE)

    pins, brochage = [], {}
    for i, (nom, px, py) in enumerate(pins_xy):
        nom = nom or str(i + 1)
        dx, dy = (px - cx) / ECHELLE, (py - cy) / ECHELLE
        cote, dec = aimanter_bord(dx, dy, w, h, GRILLE)
        pins.append(nom)
        brochage[nom] = [cote, dec]

    prefix = (r.findtext("Group") or "").strip().upper()
    nom_symbole = (r.findtext("Name") or "").strip()
    if not prefix:
        prefix = (nom_symbole[:3].upper() or "X")
    xml_texte = ET.tostring(r, encoding="unicode")
    entree = {"name": nom_symbole, "pins": pins, "brochage": brochage,
              "boite": {"w": w, "h": h},
              "primitives": primitives_depuis_dataitem(xml_texte, ECHELLE, cx, cy),
              "xml_source": xml_texte}
    # Un COMPOSE (<CComp>, dossier CCLib) se lit comme une boite a broches,
    # mais il ne doit JAMAIS repartir en <DataItem> : son original vit dans
    # CCLib et porte des entrailles (DItemL/CCLine) que nous ne modelisons pas.
    # Sans ce marqueur, l'envoi le recopiait aplati dans Lib -> doublon dans la
    # palette du collegue et version riche perdue. Cf. `ecrire_dans_dossier`.
    if r.tag.rsplit("}", 1)[-1] == "CComp":
        entree["compose"] = True
    valeur = (r.findtext("value") or "").strip()
    if valeur:
        entree["default_value"] = valeur
    return prefix, entree


def composants_depuis_xml(source):
    """@brief Tous les composants SIMPLES d'une source ERetroDesign.

    Accepte, dans l'ordre de ce que produit l'app du collegue :
    - un DOSSIER de .xml (`LibItem/Lib`) — format COURANT depuis 2026-07-24,
      un fichier par composant ;
    - un `<ArrayOfDataItem>` (agregat historique `LibItem/Lib.xml`) ;
    - un `<LibraryBundle>` (paquet « Exporter la bibliotheque ») ;
    - un `<DataItem>` nu (notre export, et l'export unitaire du collegue).

    Les composants COMPOSES (CComps/CCLib) sont ignores ici (geometrie
    imbriquee — a traiter separement).

    @param source Chemin de fichier ou de DOSSIER, chaine XML, ou Element.
    @return list[tuple] Liste de (prefix, entree).
    """
    # Dossier : on concatene les composants de chaque .xml (tri stable pour un
    # ordre reproductible d'une machine a l'autre).
    if not isinstance(source, ET.Element) and "<" not in str(source) \
            and os.path.isdir(str(source)):
        return [c for d in _dossiers_bibliotheque(str(source))
                for nom in sorted(os.listdir(d)) if nom.lower().endswith(".xml")
                for c in composants_depuis_xml(os.path.join(d, nom))]

    r = _racine(source)
    # Un <CComp> (composant COMPOSÉ) porte la MÊME enveloppe qu'un DataItem :
    # datasegment + datapin + CtrIem/TL/BR. Son extérieur est donc déjà une
    # boîte à broches exploitable ; seules ses entrailles (DItemL/CCLine) sont
    # spécifiques, et elles ne concernent pas notre modèle boîte+broches.
    if r.tag in ("DataItem", "CComp"):
        items = [r]
    else:
        # ArrayOfDataItem / ArrayOfCComp (agrégats) : enfants DIRECTS.
        items = (r.findall("./Items/DataItem") or r.findall(".//Items/DataItem")
                 or r.findall("./DataItem") or r.findall("./CComp")
                 or r.findall("./CComps/CComp") or r.findall(".//CComps/CComp"))
        if not items and r.tag.rsplit("}", 1)[-1] in ("DataItem", "CComp"):
            items = [r]                                  # namespace éventuel
    out = []
    for it in items:
        try:
            out.append(_entree_depuis_dataitem(it))
        except ValueError:
            continue
    return out


def symbole_vers_composant(source):
    """@brief Premier composant simple du fichier (compat).

    @param source Chemin, chaine XML, ou Element.
    @return tuple (prefix, entree).
    @throws ValueError si aucun composant simple exploitable.
    """
    comps = composants_depuis_xml(source)
    if not comps:
        raise ValueError("Aucun composant simple exploitable dans le fichier")
    return comps[0]
