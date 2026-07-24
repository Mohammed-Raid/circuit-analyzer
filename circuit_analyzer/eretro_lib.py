"""@file eretro_lib.py
@brief Partage de composants avec la bibliotheque ERetroDesign (symbole Lib).

Un composant cree dans l'onglet Composants (nom, broches, brochage cote+decalage,
boite) s'exporte en un fichier `Lib/<Nom>.xml` au format `<DataItem>` d'ERetroDesign
(boite en `<datasegment>`, broches en `<datapin>` avec position). Et inversement :
un symbole Lib du collegue se relit en entree de bibliotheque. Les deux sens
passent par le MEME modele boite+broches, d'ou un aller-retour exact.

@note Convention CALEE SUR LE SOURCE C# d'ERetroDesign (pas devinee) :
- un symbole Lib est un <DataItem> sauvegarde par Form2 (button5_Click) qui
  n'ecrit que Name + geometrie ; CtrIem/TL/BR restent nuls, recalcules au
  placement (Form1.InsertItem, qui force aussi zmH=zmV=1).
- le dessin place une broche a `CtrIem + Pin*zoom` (FDraw.Pinp) : Pin est donc
  un DECALAGE par rapport au centre -> on centre la geometrie sur (0,0) pour
  que le symbole apparaisse sur le curseur.
- seul CtrIem est accroche a la grille (Form1.Snap, GridStep=10) ; nos broches
  tombent sur des multiples de 10 -> cablage propre.
"""
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from gui.schematic_symbols import geometrie_libre, aimanter_bord

# Unites ERetroDesign par pixel de l'editeur. La geometrie est CENTREE sur (0,0)
# comme les broches d'un composant place (FDraw : pos = CtrIem + Pin*zoom, donc
# Pin est un decalage par rapport au centre) : le symbole apparait sur le curseur.
ECHELLE = 10
GRILLE = 20


def _pinout(entree):
    """@brief brochage {nom:[cote,decalage]} -> {nom:(cote,decalage)} pour geometrie_libre."""
    br = entree.get("brochage") or {}
    return {nom: (cote, dec) for nom, (cote, dec) in br.items()}


def composant_vers_symbole_xml(prefix, entree):
    """@brief Serialise un composant de bibliotheque en symbole Lib ERetroDesign.

    @param prefix Prefixe de type ('IC', 'R'...) ; conserve dans <Group> pour
        l'aller-retour (champ benin cote ERetroDesign).
    @param entree {name, pins, brochage{nom:[cote,dec]}, boite{w,h}, default_value}.
    @return str Document XML <DataItem> autonome.
    """
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
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<DataItem xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
        f"<Name>{escape(nom_symbole)}</Name><Group>{escape(prefix)}</Group>"
        f"<reference /><value>{escape(valeur)}</value>"
        f"<datapolygon /><datasegment>{segments}</datasegment><dataarc />"
        f"<datapin>{''.join(broches)}</datapin>"
        # Comme un vrai symbole Lib (Form2 n'ecrit que Name + geometrie) :
        # CtrIem/TL/BR restent nuls, recalcules au placement (InsertItem).
        "<CtrIem><X>0</X><Y>0</Y></CtrIem>"
        "<TL><X>0</X><Y>0</Y></TL><BR><X>0</X><Y>0</Y></BR>"
        "<angle>0</angle><id>0</id><selected>false</selected>"
        "<focus>false</focus><Visible>true</Visible></DataItem>")


def _racine(source):
    """@brief Element racine <DataItem> depuis un chemin, une chaine ou un Element."""
    if isinstance(source, ET.Element):
        return source
    texte = source
    if "<" not in str(source):                 # chemin de fichier
        with open(source, encoding="utf-8") as f:
            texte = f.read()
    return ET.fromstring(texte)


def symbole_vers_composant(source):
    """@brief Relit un symbole Lib ERetroDesign en entree de bibliotheque.

    @param source Chemin, chaine XML, ou Element <DataItem>.
    @return tuple (prefix, entree) prete pour component_library.json.
    """
    r = _racine(source)

    def pts(balise):
        out = []
        for e in r.findall(f".//{balise}"):
            x, y = e.findtext("X"), e.findtext("Y")
            if x is not None and y is not None:
                out.append((float(x), float(y)))
        return out

    # Boite : bbox des segments (repli sur les broches si pas de segment).
    coords = []
    for s in r.findall(".//datasegment/DataSegment"):
        for tag in ("Spoint", "Epoint"):
            e = s.find(tag)
            if e is not None:
                coords.append((float(e.findtext("X") or 0), float(e.findtext("Y") or 0)))
    pins_xy = []
    for dp in r.findall(".//datapin/DataPin"):
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
