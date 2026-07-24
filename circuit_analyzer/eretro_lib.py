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
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from gui.schematic_symbols import geometrie_libre, aimanter_bord

# Unites ERetroDesign par pixel de l'editeur ; geometrie CENTREE sur (0,0).
# ECHELLE=1 : les vrais symboles de Lib.xml sont centres avec des coords ~±48..80
# (Capa 96x96, AOP/Resistance 160 de large). La vignette de la palette
# (pictureBox2_Paint) dessine `CtrIem_cellule + coord` dans une cellule de 146 px :
# une echelle trop grande sort de la cellule -> vignette VIDE (composant « pas
# importable »). Notre boite ~80x60 px tombe pile dans cette plage.
ECHELLE = 1
GRILLE = 20

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
        # Comme un vrai symbole Lib : CtrIem/TL/BR nuls, recalcules au placement.
        "<CtrIem><X>0</X><Y>0</Y></CtrIem>"
        "<TL><X>0</X><Y>0</Y></TL><BR><X>0</X><Y>0</Y></BR>"
        "<angle>0</angle><id>0</id><selected>false</selected>"
        "<focus>false</focus><Visible>true</Visible></DataItem>")


def composant_vers_symbole_xml(prefix, entree):
    """@brief Paquet LibraryBundle importable par ERetroDesign (« Importer la biblio »).

    @param prefix Prefixe de type ('IC'...) ; conserve dans <Group> (aller-retour).
    @param entree {name, pins, brochage{nom:[cote,dec]}, boite{w,h}, default_value}.
    @return str Document XML <LibraryBundle> autonome (un composant simple).
    """
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<LibraryBundle {_ENTETE_XSD}>'
        f"<Items>{_dataitem_fragment(prefix, entree)}</Items>"
        "<CComps /></LibraryBundle>")


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
    """@brief Convertit un element <DataItem> en (prefix, entree bibliotheque)."""
    coords = []
    for s in r.findall("./datasegment/DataSegment"):
        for tag in ("Spoint", "Epoint"):
            e = s.find(tag)
            if e is not None:
                coords.append((float(e.findtext("X") or 0), float(e.findtext("Y") or 0)))
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
    entree = {"name": nom_symbole, "pins": pins, "brochage": brochage,
              "boite": {"w": w, "h": h}}
    valeur = (r.findtext("value") or "").strip()
    if valeur:
        entree["default_value"] = valeur
    return prefix, entree


def composants_depuis_xml(source):
    """@brief Tous les composants SIMPLES d'un fichier ERetroDesign.

    Accepte un `LibraryBundle` (paquet « Exporter la bibliotheque », plusieurs
    Items), un `<DataItem>` nu (ancien symbole Lib/<Nom>.xml), ou une racine qui
    en contient. Les composants COMPOSES (CComps) sont ignores ici (geometrie
    imbriquee — a traiter separement).

    @param source Chemin, chaine XML, ou Element.
    @return list[tuple] Liste de (prefix, entree).
    """
    r = _racine(source)
    if r.tag == "DataItem":
        items = [r]
    else:
        items = r.findall("./Items/DataItem") or r.findall(".//Items/DataItem")
        if not items and r.tag.endswith("}DataItem"):   # namespace éventuel
            items = [r]
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
