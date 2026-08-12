# Forme réelle dans l'onglet Composants + export fidèle — Plan d'implémentation

> **Pour l'exécutant :** Exécution via `superpowers:subagent-driven-development`
> (recommandé) ou `superpowers:executing-plans`.

**Spec de référence :** `docs/superpowers/specs/2026-08-05-forme-reelle-composants-onglet-design.md`
(commit `89253ea`).

**Goal :** l'onglet Composants montre la vraie forme d'un composant importé
(au lieu d'une boîte générique) ; on peut choisir une forme réelle en créant
un composant à la main ; l'export vers ERetroDesign écrit cette vraie forme
au lieu d'un rectangle générique. Les broches restent toujours indépendantes
de la forme affichée/choisie.

**Architecture :** `gui/pin_canvas.py` gagne un fond visuel optionnel (les
vraies primitives, dessinées en référence sous la boîte de brochage éditable
existante — jamais liées au placement des broches). `gui/tab_components.py`
transmet automatiquement la forme d'un import à ce fond, ajoute un sélecteur
de forme pour la création, et préserve `primitives`/`xml_source` à la
sauvegarde (au lieu de les effacer silencieusement comme aujourd'hui).
`circuit_analyzer/eretro_lib.py::_dataitem_fragment` écrit ces primitives
dans le XML exporté (via un nouveau convertisseur, inverse de
`primitives_depuis_dataitem`) au lieu d'un rectangle générique, avec le même
correctif de dimensionnement exact (`w_exact`/`h_exact`) que l'éditeur.

**Tech Stack :** Python 3.11, Tkinter/customtkinter, pytest. Aucune nouvelle
dépendance (`math`, stdlib, déjà importé dans `eretro_lib.py`).

## Global Constraints

- Commits en **français**, **jamais** de footer `Co-Authored-By: Claude` ni
  `Generated with Claude Code`.
- **Jamais `git add -A`** : fichiers ajoutés un par un.
- **Ne jamais committer** `custom_circuits.json` ni `component_library.json`.
- `ERetroDesign/`, `CARTE POUR TESTER (VRAI TEST)/`, `docs.rar`, `dist_demo/`,
  `test14.xml` : lecture seule, jamais committés.
- `PYTHONUTF8=1` sur toutes les commandes pytest.
- `schemdraw==0.22` pinné (non concerné ici, contrainte globale du dépôt).
- Branche `rewrite-simple` ; rien n'est poussé sans accord explicite.
- PNG rendus et inspectés avant tout commit touchant du dessin ; jamais de
  PNG committé.
- Les formes du sélecteur viennent UNIQUEMENT des composants déjà importés
  (ceux avec `primitives` non vide en bibliothèque) — pas de formes
  prédéfinies maison.
- Les broches restent TOUJOURS indépendantes de la forme choisie/affichée —
  jamais de gabarit de brochage imposé par une forme.

## Structure des fichiers

| Fichier | Responsabilité ajoutée |
|---|---|
| `gui/pin_canvas.py` | `charger(forme_primitives=…)`, `definir_forme()`, fond visuel dans `_dessiner()`/`_echelle()`. |
| `circuit_analyzer/eretro_lib.py` | `_primitives_vers_xml()` (inverse de `primitives_depuis_dataitem`), `_dataitem_fragment` écrit le vrai contour + bypass `w_exact`/`h_exact`. |
| `gui/tab_components.py` | Sélecteur de forme, transmission automatique après import/duplication, `_sauvegarder` préserve la forme. |
| `tests/test_pin_canvas.py` | Tests du fond visuel (T1). |
| `tests/test_eretro_lib.py` | Tests de `_primitives_vers_xml` et de l'export réel (T2). |
| `tests/test_tab_components.py` | Tests du sélecteur et de la préservation à la sauvegarde (T3). |

---

### Task 1 : `gui/pin_canvas.py` — fond visuel optionnel

**Files:**
- Modify: `gui/pin_canvas.py` (`__init__`, `charger`, `_echelle`, `_dessiner`, + `definir_forme` nouveau)
- Test: `tests/test_pin_canvas.py`

**Interfaces produites :**
- `PinCanvas.charger(brochage, lecture_seule=False, roles=None, w_mini=None, h_mini=None, forme_primitives=None)`
- `PinCanvas.definir_forme(forme_primitives=None)` — change UNIQUEMENT le
  fond, sans toucher au brochage.

- [ ] **Step 1 : écrire les tests qui échouent** — ajouter en fin de
  `tests/test_pin_canvas.py` :

```python
def test_charger_avec_forme_dessine_un_fond(canevas):
    canevas.charger([("1", "L", 0)],
                    forme_primitives=[("polygon", [(0, -10), (10, 10), (-10, 10)], False)])
    items = canevas._cv.find_all()
    polygones = [i for i in items if canevas._cv.type(i) == "polygon"]
    # 1 polygone de fond (forme) + 1 polygone de boite editable = 2
    assert len(polygones) == 2


def test_sans_forme_pas_de_fond(canevas):
    canevas.charger([("1", "L", 0)])
    items = canevas._cv.find_all()
    polygones = [i for i in items if canevas._cv.type(i) == "polygon"]
    assert len(polygones) == 1          # seulement la boite editable


def test_definir_forme_ne_touche_pas_au_brochage(canevas):
    canevas.charger([("1", "L", 0)])
    canevas.definir_forme([("polygon", [(0, -10), (10, 10), (-10, 10)], False)])
    assert canevas.brochage() == [("1", "L", 0)]
    items = canevas._cv.find_all()
    polygones = [i for i in items if canevas._cv.type(i) == "polygon"]
    assert len(polygones) == 2


def test_boite_reste_cliquable_par_dessus_le_fond(canevas):
    canevas.charger(
        [], forme_primitives=[("polygon", [(0, -200), (200, 200), (-200, 200)], False)])
    # Une forme bien plus grande que la boite par defaut ne doit pas empecher
    # de cliquer sur le bord GAUCHE de la boite editable (toujours reference).
    assert canevas._ajouter(-40, 0) == "1"
    _nom, cote, _dec = canevas.brochage()[0]
    assert cote == "L"


def test_echelle_tient_compte_de_la_forme_plus_grande_que_la_boite(canevas):
    canevas._cv.configure(width=400, height=400)
    canevas._cv.update_idletasks()
    canevas.charger([("1", "L", 0)])
    sans_forme = canevas._echelle()
    canevas.definir_forme([("polygon", [(0, -300), (300, 300), (-300, 300)], False)])
    avec_forme = canevas._echelle()
    assert avec_forme < sans_forme
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_pin_canvas.py -q`
Attendu : `TypeError: charger() got an unexpected keyword argument 'forme_primitives'`
(les deux derniers tests échoueront différemment une fois ce premier obstacle
levé — c'est normal, continuer).

- [ ] **Step 3 : implémenter** — dans `gui/pin_canvas.py`

Dans `__init__`, juste après `self._w_mini = self._h_mini = None` (ligne 57) :

```python
        self._forme_primitives: list = []   # fond visuel de reference (spec 2026-08-05)
```

Remplacer `charger` :

```python
    def charger(self, brochage: list, lecture_seule: bool = False,
                roles: dict = None, w_mini=None, h_mini=None,
                forme_primitives: list = None):
        """@brief Remplace le brochage affiché (liste ordonnée de tuples).

        @param roles        {nom: rôle} — affiché « nom RÔLE » dans le symbole.
        @param w_mini,h_mini Taille PLANCHER voulue (None = auto-ajustement).
        @param forme_primitives Forme réelle à dessiner en fond (référence,
               JAMAIS liée au placement des broches), ou None (spec 2026-08-05).
        """
        self._brochage = [tuple(b) for b in brochage]
        self._roles = dict(roles or {})
        self._w_mini, self._h_mini = w_mini, h_mini
        self._forme_primitives = list(forme_primitives or [])
        self._lecture_seule = lecture_seule
        self._selection = None
        self._dessiner()
        self._construire_bandeau()
        self._sync_champ()

    def definir_forme(self, forme_primitives: list = None):
        """@brief Change UNIQUEMENT le fond visuel (forme de référence), sans
        toucher au brochage — pour le sélecteur de forme de l'onglet
        Composants (spec 2026-08-05).
        """
        self._forme_primitives = list(forme_primitives or [])
        self._dessiner()
```

Remplacer `_echelle` (ajouter le nouvel helper juste avant) :

```python
    def _etendue_forme(self) -> tuple:
        """@brief (largeur, hauteur) totale du fond visuel, centré sur (0,0)."""
        mx = my = 0
        for p in self._forme_primitives:
            if p[0] in ("line", "polygon"):
                for x, y in p[1]:
                    mx, my = max(mx, abs(x)), max(my, abs(y))
            elif p[0] == "arc":
                x0, y0, x1, y1 = p[1]
                mx = max(mx, abs(x0), abs(x1))
                my = max(my, abs(y0), abs(y1))
        return mx * 2, my * 2

    def _echelle(self) -> float:
        """@brief Facteur d'affichage pour que la boîte ET le fond TIENNENT
        dans le cadre.

        Une taille imposée (ou un DIP-16, ou une forme réelle importée) déborde
        du canevas : sans réduction on ne voyait que le milieu des bords
        latéraux, ni haut ni bas (défaut trouvé en boucle visuelle). On ne
        grossit jamais — le facteur est plafonné à 1.
        """
        lw, lh = self._cv.winfo_width(), self._cv.winfo_height()
        if lw <= 1 or lh <= 1:
            return 1.0
        d = self._defn()
        fw, fh = self._etendue_forme()
        w, h = max(d["w"], fw), max(d["h"], fh)
        marge = 44          # place pour les pastilles et les libellés
        return min(1.0, (lw - marge) / w, (lh - marge) / h)
```

Remplacer `_dessiner` (ajoute la boucle de fond AVANT la boucle existante,
rien d'autre ne change) :

```python
    def _dessiner(self):
        self._cv.delete("all")
        cx, cy = self._centre()
        if cx <= 1:
            return                      # widget pas encore dimensionné
        d = self._defn()
        k = self._echelle()
        for p in self._forme_primitives:
            if p[0] == "line":
                pts = [c for x, y in p[1] for c in (cx + x * k, cy + y * k)]
                self._cv.create_line(*pts, fill=TEXT_MUTED,
                                     width=max(1, int(p[2] * k)))
            elif p[0] == "polygon":
                pts = [c for x, y in p[1] for c in (cx + x * k, cy + y * k)]
                self._cv.create_polygon(*pts, fill="", outline=TEXT_MUTED,
                                        width=1)
            elif p[0] == "arc":
                x0, y0, x1, y1 = p[1]
                self._cv.create_arc(cx + x0 * k, cy + y0 * k,
                                    cx + x1 * k, cy + y1 * k,
                                    start=p[2], extent=p[3], style="arc",
                                    outline=TEXT_MUTED, width=1)
        for p in primitives(TYPE_LIBRE, d, 0):
            if p[0] == "polygon":
                pts = [c for x, y in p[1] for c in (cx + x * k, cy + y * k)]
                self._cv.create_polygon(*pts, fill="", outline=AUTO_COLOR,
                                        width=2)
            elif p[0] == "text":
                self._cv.create_text(cx + p[1][0] * k, cy + p[1][1] * k,
                                     text=p[2], fill=TEXT_MUTED,
                                     font=("Consolas", max(6, int(8 * k))),
                                     anchor={"e": "e", "w": "w"}.get(p[4],
                                                                     "center"))
        for nom, (px, py) in d["pins"].items():
            x, y = cx + px * k, cy + py * k
            contour = AUTO_COLOR if nom == self._selection else _PIN_OFF
            self._cv.create_oval(x - _R_BROCHE, y - _R_BROCHE,
                                 x + _R_BROCHE, y + _R_BROCHE,
                                 fill=_FOND, outline=contour, width=2,
                                 tags=(f"broche_{nom}",))
```

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_pin_canvas.py -q` → PASS

- [ ] **Step 5 : commit**

```bash
git add gui/pin_canvas.py tests/test_pin_canvas.py
git commit -m "feat(composants): fond visuel optionnel dans le canevas de brochage"
```

---

### Task 2 : `circuit_analyzer/eretro_lib.py` — export du vrai contour

**Files:**
- Modify: `circuit_analyzer/eretro_lib.py` (`_dataitem_fragment` + nouvelles fonctions)
- Test: `tests/test_eretro_lib.py`

**Interfaces produites :**
- `_primitives_vers_xml(prims, abs_pt) -> tuple[str, str, str]` — (segments,
  polygone, arcs), fragments XML prêts à insérer.
- `_dataitem_fragment` : écrit le vrai contour si `entree.get("primitives")`,
  sinon comportement inchangé (boîte générique).

- [ ] **Step 1 : écrire les tests qui échouent**

Ajouter en fin de `tests/test_eretro_lib.py` :

```python
def test_primitives_vers_xml_ligne_produit_un_segment():
    from circuit_analyzer.eretro_lib import _primitives_vers_xml

    def abs_pt(dx, dy):
        return int(round(dx)), int(round(dy))

    segments, polygone, arcs = _primitives_vers_xml(
        [("line", [(10.0, 20.0), (30.0, 20.0)], 2)], abs_pt)
    assert polygone == "" and arcs == ""
    r = ET.fromstring(f"<x>{segments}</x>")
    seg = r.find("DataSegment")
    assert (seg.find("Spoint").findtext("X"), seg.find("Spoint").findtext("Y")) == ("10", "20")
    assert (seg.find("Epoint").findtext("X"), seg.find("Epoint").findtext("Y")) == ("30", "20")


def test_primitives_vers_xml_polygone_produit_un_point_par_sommet():
    from circuit_analyzer.eretro_lib import _primitives_vers_xml

    def abs_pt(dx, dy):
        return int(round(dx)), int(round(dy))

    segments, polygone, arcs = _primitives_vers_xml(
        [("polygon", [(52.0, 0.0), (-52.0, -48.0), (-52.0, 48.0)], False)], abs_pt)
    assert segments == "" and arcs == ""
    r = ET.fromstring(f"<x>{polygone}</x>")
    pts = [(p.find("point").findtext("X"), p.find("point").findtext("Y"))
           for p in r.findall("DataPolygon")]
    assert pts == [("52", "0"), ("-52", "-48"), ("-52", "48")]


def test_primitives_vers_xml_arc_aller_retour_via_primitives_depuis_dataitem():
    # Fragment reel (Self.xml) : centre (0,0), rayon 16, demi-cercle.
    from circuit_analyzer.eretro_lib import _primitives_vers_xml
    from gui.schematic_symbols import primitives_depuis_dataitem

    def abs_pt(dx, dy):
        return int(round(dx)), int(round(dy))

    original = [("arc", (-16.0, -16.0, 16.0, 16.0), -180.0, 180.0)]
    segments, polygone, arcs = _primitives_vers_xml(original, abs_pt)
    assert segments == "" and polygone == ""
    xml = f"<DataItem><datasegment/><datapolygon/><dataarc>{arcs}</dataarc></DataItem>"
    relu = primitives_depuis_dataitem(xml, 1.0)
    assert relu == original


def test_export_avec_primitives_ecrit_un_vrai_contour_pas_une_boite():
    entree = {"name": "Test", "pins": ["1", "2"],
              "brochage": {"1": ["L", 0], "2": ["R", 0]},
              "boite": {"w": 80, "h": 60},
              "primitives": [("polygon", [(0, -10), (10, 10), (-10, 10)], False)]}
    xml = composant_vers_symbole_xml("IC", entree)
    r = ET.fromstring(xml)
    assert len(r.findall("./datapolygon/DataPolygon")) == 3   # 3 sommets, pas 0
    assert len(r.findall("./datasegment/DataSegment")) == 0   # plus de boite generique


def test_export_sans_primitives_garde_la_boite_generique():
    entree = {"name": "Test", "pins": ["1", "2"],
              "brochage": {"1": ["L", 0], "2": ["R", 0]},
              "boite": {"w": 80, "h": 60}}
    xml = composant_vers_symbole_xml("IC", entree)
    r = ET.fromstring(xml)
    assert len(r.findall("./datapolygon/DataPolygon")) == 0
    assert len(r.findall("./datasegment/DataSegment")) == 4   # boite inchangee


def test_export_avec_forme_decentree_positionne_la_broche_pres_du_contour():
    """Meme piege que Vss.xml/VCC+.xml (chantier precedent, commit bf341d4) :
    sans le bypass w_exact/h_exact ici aussi, l'export retomberait sur le
    bug de broche flottante deja corrige cote editeur."""
    entree = {"name": "VCCTest", "pins": ["+"],
              "brochage": {"+": ["B", 0]},
              "boite": {"w": 160, "h": 20},
              "primitives": [("line", [(0.0, -7.0), (0.0, 7.0)], 2),
                            ("polygon", [(-80.0, -14.5), (80.0, -14.5),
                                        (80.0, 7.0), (-80.0, 7.0)], False)]}
    xml = composant_vers_symbole_xml("IC", entree)
    r = ET.fromstring(xml)
    pin = r.find("./datapin/DataPin/Pin")
    py = float(pin.findtext("Y"))
    assert abs(py) <= 20   # proche du corps (h=20), pas a 50 (bug corrige)
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_lib.py -q`
Attendu : `ImportError: cannot import name '_primitives_vers_xml'`

- [ ] **Step 3 : implémenter** — dans `circuit_analyzer/eretro_lib.py`

Extraire le helper `seg()` actuellement local à `_dataitem_fragment` en
fonction de module (juste avant `_dataitem_fragment`), et ajouter
`_primitives_vers_xml` juste après :

```python
def _seg_xml(xa, ya, xb, yb):
    """@brief Fragment <DataSegment> — partagé par la boîte générique et
    `_primitives_vers_xml` (même format, une seule source)."""
    return (f"<DataSegment><Spoint><X>{xa}</X><Y>{ya}</Y></Spoint>"
            f"<Epoint><X>{xb}</X><Y>{yb}</Y></Epoint>"
            f"<SPtGap><X>0</X><Y>0</Y></SPtGap>"
            f"<EPtGap><X>0</X><Y>0</Y></EPtGap>"
            f"<ESelected>false</ESelected><SSelected>false</SSelected></DataSegment>")


def _primitives_vers_xml(prims, abs_pt):
    """@brief Inverse de `primitives_depuis_dataitem` : primitives -> fragments XML.

    @param prims Primitives ("line"|"arc"|"polygon", ...), mêmes coordonnées
           que `geo["pins"]` (repère centré, AVANT `abs_pt`).
    @param abs_pt Même transformation que celle déjà utilisée pour les
           broches et la boîte -- même repère, aucune conversion
           supplémentaire (spec 2026-08-05).
    @return tuple (segments_xml, polygone_xml, arcs_xml) -- chaînes
            concaténées, prêtes à insérer dans
            <datasegment>/<datapolygon>/<dataarc>.
    """
    segments, polygone, arcs = [], [], []
    for p in prims:
        if p[0] == "line":
            (x1, y1), (x2, y2) = p[1]
            xa, ya = abs_pt(x1, y1)
            xb, yb = abs_pt(x2, y2)
            segments.append(_seg_xml(xa, ya, xb, yb))
        elif p[0] == "polygon":
            for x, y in p[1]:
                px, py = abs_pt(x, y)
                polygone.append(
                    f"<DataPolygon><point><X>{px}</X><Y>{py}</Y></point>"
                    "<Selected>false</Selected>"
                    "<PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>")
        elif p[0] == "arc":
            x0, y0, x1, y1 = p[1]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            rayon = abs(x1 - x0) / 2
            debut, etendue = p[2], p[3]
            sx = cx + rayon * math.cos(math.radians(debut))
            sy = cy + rayon * math.sin(math.radians(debut))
            ex = cx + rayon * math.cos(math.radians(debut + etendue))
            ey = cy + rayon * math.sin(math.radians(debut + etendue))
            acx, acy = abs_pt(cx, cy)
            asx, asy = abs_pt(sx, sy)
            aex, aey = abs_pt(ex, ey)
            arcs.append(
                f"<DataArc><pCenter><X>{acx}</X><Y>{acy}</Y></pCenter>"
                f"<stAngle>{debut}</stAngle><swAngle>{etendue}</swAngle>"
                f"<Spoint><X>{asx}</X><Y>{asy}</Y></Spoint>"
                f"<Epoint><X>{aex}</X><Y>{aey}</Y></Epoint></DataArc>")
    return "".join(segments), "".join(polygone), "".join(arcs)
```

Remplacer `_dataitem_fragment` en entier :

```python
def _dataitem_fragment(prefix, entree):
    """@brief Fragment <DataItem> (geometrie centree) — sans declaration XML."""
    pinout = _pinout(entree)
    boite = entree.get("boite") or {}
    prims = entree.get("primitives")
    if prims:
        # Bypass w_exact/h_exact : meme correctif que _auto_def (commit
        # bf341d4) -- sans lui, une forme importee decentree (Vss, VCC+...)
        # exporterait une broche flottante, comme avant ce correctif.
        geo = geometrie_libre(pinout, w_exact=boite.get("w"), h_exact=boite.get("h"))
    else:
        geo = geometrie_libre(pinout, boite.get("w"), boite.get("h"))
    w, h = geo["w"], geo["h"]

    def abs_pt(dx, dy):
        # Centre a l'origine : Pin = decalage / CtrIem (=0 dans un symbole Lib).
        return int(round(dx * ECHELLE)), int(round(dy * ECHELLE))

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

    if prims:
        segments, polygone, arcs = _primitives_vers_xml(prims, abs_pt)
    else:
        x0, y0 = abs_pt(-w / 2, -h / 2)
        x1, y1 = abs_pt(w / 2, h / 2)
        # Boite = 4 aretes du rectangle.
        segments = "".join([
            _seg_xml(x0, y0, x1, y0), _seg_xml(x1, y0, x1, y1),
            _seg_xml(x1, y1, x0, y1), _seg_xml(x0, y1, x0, y0),
        ])
        polygone, arcs = "", ""

    nom_symbole = entree.get("name") or prefix
    valeur = entree.get("default_value", "") or ""
    return (
        f"<DataItem>"
        f"<Name>{escape(nom_symbole)}</Name><Group>{escape(prefix)}</Group>"
        f"<reference /><value>{escape(valeur)}</value>"
        f"<datapolygon>{polygone}</datapolygon>"
        f"<datasegment>{segments}</datasegment>"
        f"<dataarc>{arcs}</dataarc>"
        f"<datapin>{''.join(broches)}</datapin>"
        # CtrIem nul : recalcule a chaque rendu de palette (pictureBox2_Paint).
        # TL/BR, EUX, NE SONT PAS NULS : c'est la boite CLIQUABLE de la vignette
        # (cf. _CLIC_*), pas la geometrie du symbole.
        "<CtrIem><X>0</X><Y>0</Y></CtrIem>"
        f"<TL><X>{_CLIC_TL[0]}</X><Y>{_CLIC_TL[1]}</Y></TL>"
        f"<BR><X>{_CLIC_BR[0]}</X><Y>{_CLIC_BR[1]}</Y></BR>"
        "<angle>0</angle><id>0</id><selected>false</selected>"
        "<focus>false</focus><Visible>true</Visible></DataItem>")
```

`_primitives_vers_xml` utilise `math.cos`/`math.radians` : le module a déjà
`import math` en tête de fichier depuis le chantier précédent (commit
`bf341d4`) — aucun nouvel import à ajouter.

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_lib.py -q` → PASS

Non-régression explicite (les tests d'aller-retour existants exportent
toujours SANS primitives — confirmer qu'ils passent toujours à l'identique) :

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_lib.py tests/test_eretro_corpus.py tests/test_eretro_dialecte.py -q` → PASS

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/eretro_lib.py tests/test_eretro_lib.py
git commit -m "feat(interop): l'export ecrit le vrai contour au lieu d'une boite generique"
```

---

### Task 3 : `gui/tab_components.py` — sélecteur de forme + préservation

**Files:**
- Modify: `gui/tab_components.py` (`__init__`, `_build`, `_load`,
  `_remplir_formulaire`, `_afficher_perso`, `_afficher_nouveau`, `_dupliquer`,
  `_sauvegarder`, + `_sur_forme` nouveau)
- Test: `tests/test_tab_components.py`

**Interfaces produites :**
- `TabComponents._sur_forme(choix: str)` — callback du sélecteur.
- État : `self._forme_primitives`, `self._formes_disponibles`,
  `self._xml_source_valide`, `self._xml_source_courant`.

- [ ] **Step 1 : écrire les tests qui échouent**

Ajouter en fin de `tests/test_tab_components.py` :

```python
def test_selecteur_de_forme_liste_les_composants_importes(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "AOP2": {"name": "AOP2", "pins": ["1"], "brochage": {"1": ["L", 0]},
                 "primitives": [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]},
        "SANS": {"name": "SansForme", "pins": ["1"], "brochage": {"1": ["L", 0]}},
    }), encoding="utf-8")
    t._load()
    assert any("AOP2" in cle for cle in t._formes_disponibles)
    assert not any("SANS" in cle for cle in t._formes_disponibles)


def test_choisir_une_forme_met_a_jour_l_apercu_sans_toucher_aux_broches(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "AOP2": {"name": "AOP2", "pins": ["1"], "brochage": {"1": ["L", 0]},
                 "primitives": [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]},
    }), encoding="utf-8")
    t._load()
    t._afficher_nouveau()
    t._brochage = [("X", "L", 0)]
    cle = next(c for c in t._formes_disponibles if "AOP2" in c)
    t._sur_forme(cle)
    assert t._forme_primitives == [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]
    assert t._brochage == [("X", "L", 0)]     # broches inchangees


def test_afficher_perso_montre_la_forme_de_l_import(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "AOP2": {"name": "AOP2", "pins": ["1"], "brochage": {"1": ["L", 0]},
                 "primitives": [["polygon", [[0, -10], [10, 10], [-10, 10]], False]],
                 "xml_source": "<DataItem>...</DataItem>"},
    }), encoding="utf-8")
    t._load()
    t._afficher_perso("AOP2")
    assert t._forme_primitives == [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]
    assert t._xml_source_valide is True


def test_resauver_sans_toucher_la_forme_preserve_primitives_et_xml_source(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "AOP2": {"name": "AOP2", "pins": ["1"], "brochage": {"1": ["L", 0]},
                 "primitives": [["polygon", [[0, -10], [10, 10], [-10, 10]], False]],
                 "xml_source": "<DataItem>ORIGINAL</DataItem>"},
    }), encoding="utf-8")
    t._load()
    t._afficher_perso("AOP2")
    t._sauvegarder()
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert data["AOP2"]["primitives"] == [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]
    assert data["AOP2"]["xml_source"] == "<DataItem>ORIGINAL</DataItem>"


def test_changer_de_forme_invalide_le_xml_source_a_la_sauvegarde(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "AOP2": {"name": "AOP2", "pins": ["1"], "brochage": {"1": ["L", 0]},
                 "primitives": [["polygon", [[0, -10], [10, 10], [-10, 10]], False]],
                 "xml_source": "<DataItem>ORIGINAL</DataItem>"},
        "SELF2": {"name": "Self2", "pins": ["2"], "brochage": {"2": ["R", 0]},
                  "primitives": [["line", [[0, -7], [0, 7]], 2]]},
    }), encoding="utf-8")
    t._load()
    t._afficher_perso("AOP2")
    cle = next(c for c in t._formes_disponibles if "SELF2" in c)
    t._sur_forme(cle)
    t._sauvegarder()
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert "xml_source" not in data["AOP2"]
    assert data["AOP2"]["primitives"] == [["line", [[0, -7], [0, 7]], 2]]


def test_nouveau_composant_avec_forme_choisie_a_primitives_mais_pas_xml_source(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "AOP2": {"name": "AOP2", "pins": ["1"], "brochage": {"1": ["L", 0]},
                 "primitives": [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]},
    }), encoding="utf-8")
    t._load()
    t._afficher_nouveau()
    t._prefix_var.set("NEUF")
    t._brochage = [("A", "L", 0), ("B", "R", 0)]
    cle = next(c for c in t._formes_disponibles if "AOP2" in c)
    t._sur_forme(cle)
    t._sauvegarder()
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert data["NEUF"]["primitives"] == [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]
    assert "xml_source" not in data["NEUF"]
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_tab_components.py -q`
Attendu : `AttributeError: 'TabComponents' object has no attribute '_formes_disponibles'`

- [ ] **Step 3 : implémenter** — dans `gui/tab_components.py`

Dans `__init__`, juste après `self._etat_initial: tuple = ('', '', ())`
(ligne 83) :

```python
        self._forme_primitives: list = []          # fond actif (spec 2026-08-05)
        self._formes_disponibles: dict = {}         # {libelle: primitives}
        self._xml_source_valide = False
        self._xml_source_courant = ""
```

Dans `_build`, insérer une nouvelle ligne entre le bloc `mrow` (qui se
termine par `self._btn_modele.pack(side="left")`, ligne 182) et la
construction de `PinCanvas` (ligne 184) :

```python
        frow = ctk.CTkFrame(form, fg_color="transparent")
        frow.pack(fill="x", pady=(2, 2))
        ctk.CTkLabel(frow, text="Forme :", font=ui_kit.font("caption"),
                     text_color=TEXT_MUTED).pack(side="left", padx=(0, 6))
        self._forme_var = tk.StringVar(value="Aucune")
        self._forme_menu = ctk.CTkOptionMenu(
            frow, values=["Aucune"], variable=self._forme_var,
            width=200, height=30, command=self._sur_forme)
        self._forme_menu.pack(side="left")
```

Remplacer `_load` en entier :

```python
    def _load(self):
        """@brief Charge la bibliothèque (types intégrés + personnalisés) et peuple la liste."""
        self._custom = {}
        chemin = chemin_bibliotheque()
        if chemin.exists():
            with open(chemin, encoding="utf-8") as f:
                data = json.load(f)
            self._custom = {k: v for k, v in data.items()
                            if k not in COMPONENT_TYPES}
        self._liste.remplir(
            integres=[f"{k}  —  {v['name']}"
                      for k, v in COMPONENT_TYPES.items()],
            personnalises=[f"{k}  —  {v.get('name', '')}"
                           for k, v in self._custom.items()],
        )
        # Sélecteur de forme : uniquement les composants avec une forme réelle
        # importée (spec 2026-08-05) — jamais de forme prédéfinie maison.
        self._formes_disponibles = {
            (f"{k} — {v['name']}" if v.get("name") else k): v["primitives"]
            for k, v in self._custom.items() if v.get("primitives")
        }
        self._forme_menu.configure(values=["Aucune"] + sorted(self._formes_disponibles))
```

Ajouter la méthode `_sur_forme` (par exemple juste après `_sur_brochage`) :

```python
    def _sur_forme(self, choix: str):
        """@brief Le sélecteur de forme a changé : met à jour l'aperçu SANS
        toucher au brochage, et invalide `xml_source` (spec 2026-08-05 —
        une forme piochée à la main n'est plus « l'import original »)."""
        self._xml_source_valide = False
        self._forme_primitives = list(self._formes_disponibles.get(choix) or [])
        self._canvas_broches.definir_forme(self._forme_primitives)
```

Modifier `_remplir_formulaire` — signature + fin de méthode :

```python
    def _remplir_formulaire(self, prefixe: str, nom: str, broches: list,
                            brochage: dict = None, lecture_seule: bool = False,
                            default_value: str = "", fonctions: dict = None,
                            boite: dict = None, primitives: list = None):
        """@brief Remplit les champs du formulaire (préfixe, nom, brochage).

        @param prefixe Préfixe du type.
        @param nom Nom complet du type.
        @param broches Liste ORDONNÉE des noms de broches (ordre netlist).
        @param brochage {nom: [côté, décalage]} du fichier, ou None.
        @param lecture_seule Vrai pour un type intégré (canevas non éditable).
        @param primitives Forme réelle du composant affiché (import), ou
               None — dessinée en fond dans le canevas (spec 2026-08-05).
        @return None
        """
        # Réactiver avant d'écrire : un Entry disabled ignore les set()
        self._prefix_entry.configure(state="normal")
        self._name_entry.configure(state="normal")
        self._prefix_var.set(prefixe)
        self._name_var.set(nom)
        if brochage:
            # L'ORDRE vient de `pins`, les POSITIONS de `brochage` : une broche
            # présente dans l'un et pas dans l'autre est simplement ignorée.
            self._brochage = [(b, *brochage[b]) for b in broches
                              if b in brochage]
        else:
            self._brochage = _amorcer(broches)
        self._default_var.set(default_value or "")
        b = boite or {}
        self._auto_taille_var.set(not b)
        self._w_var.set(str(b.get("w", "")) if b else "")
        self._h_var.set(str(b.get("h", "")) if b else "")
        self._sur_auto_taille()
        self._forme_primitives = list(primitives or [])
        self._forme_var.set("Aucune")
        self._canvas_broches.charger(self._brochage, lecture_seule,
                                     roles=fonctions,
                                     w_mini=b.get("w"), h_mini=b.get("h"),
                                     forme_primitives=self._forme_primitives)
```

Modifier `_afficher_perso` :

```python
    def _afficher_perso(self, key: str):
        """@brief Affiche un type personnalisé en mode édition.

        @param key Préfixe du type personnalisé.
        @return None
        """
        self._current_key = key
        v = self._custom[key]
        self._remplir_formulaire(key, v.get("name", ""), v.get("pins", []),
                                 v.get("brochage"),
                                 default_value=v.get("default_value", ""),
                                 fonctions=v.get("fonctions"),
                                 boite=v.get("boite"),
                                 primitives=v.get("primitives"))
        self._xml_source_valide = bool(v.get("xml_source"))
        self._xml_source_courant = v.get("xml_source", "")
        self._definir_mode('edition', f"✏  Modification de ★ {key}")
        self._prendre_snapshot()
```

Modifier `_afficher_nouveau` :

```python
    def _afficher_nouveau(self):
        """@brief Affiche un formulaire vierge en mode « nouveau »."""
        self._current_key = None
        self._remplir_formulaire('', '', [])
        self._xml_source_valide = False
        self._xml_source_courant = ""
        self._definir_mode('nouveau', "➕  Nouveau type de composant")
        self._prendre_snapshot()
```

Modifier `_dupliquer` — ajouter `primitives=self._forme_primitives` à l'appel
existant, et invalider `xml_source` :

```python
    def _dupliquer(self):
        """@brief Préremplit un nouveau type personnalisé à partir du type affiché."""
        nom = self._name_var.get()
        broches = [n for n, _c, _d in self._brochage]
        positions = {n: [c, d] for n, c, d in self._brochage}
        self._liste.deselectionner()
        self._current_key = None
        b = {}
        if not self._auto_taille_var.get():
            b = {"w": self._w_var.get(), "h": self._h_var.get()}
            b = {k: int(v) for k, v in b.items() if str(v).strip().isdigit()}
        self._remplir_formulaire('', f"{nom} (copie)", broches, positions,
                                 default_value=self._default_var.get(),
                                 fonctions=self._canvas_broches.roles(),
                                 boite=b or None,
                                 primitives=self._forme_primitives)
        self._xml_source_valide = False
        self._xml_source_courant = ""
        self._definir_mode('nouveau',
                           "➕  Nouveau type (copie) — choisir un préfixe")
        self._prendre_snapshot()
```

Modifier `_sauvegarder` — insérer après la création du dict `entree`
(après la ligne `"brochage": {n: [c, d] for n, c, d in self._brochage}}`) :

```python
        entree = {"name": name, "pins": pins,
                  "brochage": {n: [c, d] for n, c, d in self._brochage}}
        if self._forme_primitives:
            entree["primitives"] = self._forme_primitives
            if self._xml_source_valide:
                entree["xml_source"] = self._xml_source_courant
        defaut = self._default_var.get().strip()
```

(Le reste de `_sauvegarder` — `defaut`, `roles`, `boite`, écriture — ne
change pas.)

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_tab_components.py -q` → PASS

Non-régression large (le fichier de test existant a plusieurs autres tests
qui appellent `_afficher_perso`/`_sauvegarder`/`_dupliquer` — confirmer
qu'ils passent toujours à l'identique) :

Run : `PYTHONUTF8=1 python -m pytest tests/test_tab_components.py tests/test_pin_canvas.py tests/test_palette_et_doublon.py -q` → PASS

- [ ] **Step 5 : commit**

```bash
git add gui/tab_components.py tests/test_tab_components.py
git commit -m "feat(composants): selecteur de forme reelle a la creation, preservee a la sauvegarde"
```

---

### Task 4 : Suite complète + boucle visuelle (exigence boss)

- [ ] **Step 1 : suite complète, deux fois**

```bash
PYTHONUTF8=1 python -m pytest -q
```

Attendu : même nombre de PASS les deux fois, 0 échec — **sauf** les 14
échecs déjà connus et déjà diagnostiqués comme non liés à ce dépôt de code
(`tests/test_puces_resolution.py::test_puce_composant_resout_une_position[reel_555_astable.xml...]`,
fuite du vrai `custom_circuits.json` via un trou d'isolation préexistant
dans `tests/conftest.py`, sans rapport avec ce chantier — ne PAS tenter de
les corriger ici, hors périmètre). Si un échec supplémentaire apparaît,
c'est un vrai problème de ce chantier à corriger.

- [ ] **Step 2 : boucle visuelle** — script scratch **hors dépôt**
  (scratchpad), composants réels rendus en PNG et **réellement inspectés
  puis décrits** :
  1. Importer un composant réel (ex. `AOP.xml` ou `Vss.xml` via
     `ERetroDesign/ERetroDesign/bin/Debug/LibItem/Lib/`) dans une
     bibliothèque temporaire, ouvrir l'onglet Composants dessus (ou appeler
     `_afficher_perso` directement) → la vraie forme doit apparaître en fond
     du canevas de brochage, atténuée, avec la boîte de broches éditable
     par-dessus.
  2. Créer un nouveau composant, choisir une forme dans le sélecteur → même
     rendu (fond + boîte éditable), broches placées indépendamment de la
     forme.
  3. Exporter ce nouveau composant (`composant_vers_symbole_xml`) → ouvrir
     le XML produit et vérifier à l'œil que `<datapolygon>`/`<dataarc>`
     contiennent la vraie géométrie (pas vides), pas seulement via les tests.
  4. Un composant SANS forme choisie → canevas et export **strictement
     identiques** à avant (non-régression visuelle).
- [ ] **Step 3 : supprimer PNG et scripts** (jamais committés).
- [ ] **Step 4 : revue** — `superpowers:requesting-code-review` sur la
  branche, puis `superpowers:finishing-a-development-branch`. Rien n'est
  poussé sans accord explicite.

---

## Vérification (bout en bout)

1. **Tests** : `PYTHONUTF8=1 python -m pytest -q` — tout vert hors les 14
   échecs préexistants déjà diagnostiqués (hors périmètre), dont
   `tests/test_pin_canvas.py`, `tests/test_eretro_lib.py`,
   `tests/test_tab_components.py` sans régression sur leurs tests existants.
2. **À la main dans l'app** : onglet Composants → afficher un import → vraie
   forme visible en fond ; créer un composant → choisir une forme dans le
   sélecteur → aperçu correct, broches indépendantes ; exporter → XML avec
   vrai contour.
3. **Preuve visuelle** : les captures de la Task 4, inspectées et décrites.

## Réserves (héritées du spec)

1. Le rendu de l'export chez ERetroDesign (côté C#) n'est pas vérifiable
   depuis ici — réserve déjà actée pour tout export vers sa bibliothèque.
2. La reconstruction `Spoint`/`Epoint` d'un arc à l'export est une
   trigonométrie standard cohérente avec l'import, jamais comparée à ce
   qu'écrirait le C# lui-même pour le même contour.
