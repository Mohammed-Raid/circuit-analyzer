# Bibliothèque partagée ERetroDesign — Plan 1 (chargeur et export)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** faire de la bibliothèque vivante d'ERetroDesign (`LibItem/Lib/*.xml`) la source du dessin de nos exports, corriger les deux défauts qui rendent nos schémas illisibles chez lui, et lui pousser les symboles qu'il n'a pas.

**Architecture :** un module neuf `circuit_analyzer/eretro_symboles.py` (stdlib seule) lit ses `.xml` et rend un dict à la forme de `_FORME`. `xml.py` fusionne ce dict par-dessus ses formes maison au chargement du module ; en l'absence du dossier, tout retombe sur les formes maison sans exception. `eretro_lib.py` gagne un écrivain qui pousse nos formes orphelines dans son dossier.

**Rien à faire sur le vocabulaire.** La spec impose d'exporter avec les noms de
sa bibliothèque vivante (`Résistance`, `Capa`, `AOP`, `Diode`, `Self`, `2N2B`,
`GND`, `Vss`) — c'est **déjà** ce que `_FORME` et `_TYPE_VERS_FORME` emploient.
Aucune table de traduction n'est nécessaire, et il ne faut surtout pas basculer
sur le vocabulaire de ses vieilles cartes (`R 1001`, `Condensateur`), qui n'est
plus dans sa palette.

**Tech Stack :** Python 3.11, `xml.etree.ElementTree`, pytest. Aucune dépendance nouvelle.

**Spec de référence :** `docs/superpowers/specs/2026-07-31-bibliotheque-partagee-design.md` (commit `7dc3d28`).

## Global Constraints

- Commits en **français**, **jamais** de `Co-Authored-By: Claude` ni `Generated with Claude Code`.
- **Jamais `git add -A`** : fichiers ajoutés un par un.
- **Ne jamais committer** `custom_circuits.json` ni `component_library.json`.
- `ERetroDesign/`, `CARTE POUR TESTER (VRAI TEST)/`, `docs.rar`, `dist_demo/`, `test14.xml` : lecture seule, **jamais committés**.
- `PYTHONUTF8=1` sur toutes les commandes pytest.
- `schemdraw==0.22` pinné (0.23 casse ~30 tests de rendu).
- Branche `rewrite-simple` ; **rien n'est poussé sans accord explicite du boss**.
- **Ne pas toucher à `<TL>`/`<BR>`** dans `_xml_composant` : `(50,25)`/`(210,121)` est une constante de son format, présente sur les 209 composants posés de ses 4 cartes et sur tous ses symboles de bibliothèque.
- **Ne pas toucher au retour fidèle** (`eretro_patch.py`) : il patche le fichier reçu et n'a rien à voir avec la génération.
- Flake connu : `test_500_portes_sous_budget` → relancer isolé si rouge.

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `circuit_analyzer/eretro_symboles.py` | **Créé.** Lire `LibItem/Lib/*.xml` → dict à la forme de `_FORME`. Stdlib seule, aucune dépendance projet (sinon import circulaire avec `xml.py`). |
| `circuit_analyzer/xml.py` | Fusion des formes chargées par-dessus `_FORME` ; `_Comp.ref` et `<reference>` ; entrées `GND`/`VCC`/`VSS` dans `_TYPE_VERS_FORME`. |
| `circuit_analyzer/eretro_lib.py` | `ecrire_formes_dans_dossier` : pousse nos formes orphelines en `<DataItem>.xml`. |
| `tests/test_eretro_symboles.py` | **Créé.** Chargeur, repli, robustesse. |
| `tests/test_export_lisible.py` | **Créé.** Les deux correctifs d'export, vérifiés sur la sortie de `generer_xml`. |

---

### Task 1 : le chargeur de symboles

**Files:**
- Create: `circuit_analyzer/eretro_symboles.py`
- Test: `tests/test_eretro_symboles.py`

**Interfaces:**
- Consumes: rien (première tâche).
- Produces:
  - `charger(dossier: str | None = None) -> dict[str, dict]` — `nom -> {"pins": {str: (int, int, int)}, "polygon": str, "segment": str, "arc": str, "typ": int}`
  - `chemin_par_defaut() -> str | None`
  - `DOSSIER_RELATIF: str` (constante du chemin par défaut dans le dépôt)

- [ ] **Step 1 : écrire les tests qui échouent** — `tests/test_eretro_symboles.py`

```python
"""@file test_eretro_symboles.py
@brief Chargement de la bibliotheque VIVANTE d'ERetroDesign (LibItem/Lib).

Sa bibliotheque est un <DataItem> complet par composant depuis son
[MODIF 2026-07-24] (Form1.cs:6104). Ne pas confondre avec bin/Debug/Lib/,
fonds MORT dont les symboles font ~997x201 et n'ont ni Name ni typ.
"""
import os
import xml.etree.ElementTree as ET

import pytest

from circuit_analyzer import eretro_symboles

_DOSSIER_REEL = os.path.join("ERetroDesign", "ERetroDesign", "bin", "Debug",
                             "LibItem", "Lib")


def _symbole(tmp_path, nom, pins, typ="0", segments=1):
    """@brief Ecrit un symbole minimal au format LibItem/Lib."""
    dp = "".join(
        f"<DataPin><Pname>{n}</Pname><Pnumber>{n}</Pnumber>"
        f"<Pin><X>{x}</X><Y>{y}</Y></Pin></DataPin>"
        for n, (x, y) in pins.items())
    seg = "".join(
        "<DataSegment><Spoint><X>-10</X><Y>0</Y></Spoint>"
        "<Epoint><X>10</X><Y>0</Y></Epoint></DataSegment>"
        for _ in range(segments))
    chemin = os.path.join(str(tmp_path), nom + ".xml")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(f'<?xml version="1.0" encoding="utf-8"?>'
                f"<DataItem><Name>{nom}</Name>"
                f"<datapolygon /><datasegment>{seg}</datasegment><dataarc />"
                f"<datapin>{dp}</datapin><typ>{typ}</typ></DataItem>")
    return chemin


def test_un_symbole_donne_ses_broches_avec_leur_rang(tmp_path):
    """Le 3e membre du tuple est le RANG dans <datapin> : c'est lui que
    `_xml_composant` emet comme index de broche, et sur lequel les refs de
    connexion `cid_pidx_..._wid` sont construites."""
    _symbole(tmp_path, "Truc", {"2": (-80, 0), "1": (80, 0)})
    formes = eretro_symboles.charger(str(tmp_path))
    assert formes["Truc"]["pins"] == {"2": (-80, 0, 0), "1": (80, 0, 1)}


def test_la_geometrie_ressort_en_fragments_xml(tmp_path):
    """`_FORME` stocke polygon/segment/arc en CHAINE XML, prete a etre
    concatenee par `_xml_composant`. On rend donc la meme chose."""
    _symbole(tmp_path, "Truc", {"1": (0, 0)}, segments=2)
    f = eretro_symboles.charger(str(tmp_path))["Truc"]
    assert f["segment"].count("<DataSegment>") == 2
    assert f["polygon"] == "" and f["arc"] == ""
    ET.fromstring("<r>" + f["segment"] + "</r>")   # fragment bien forme


def test_le_typ_du_symbole_est_rendu(tmp_path):
    _symbole(tmp_path, "Truc", {"1": (0, 0)}, typ="76")
    assert eretro_symboles.charger(str(tmp_path))["Truc"]["typ"] == 76


def test_un_symbole_sans_broche_est_ecarte(tmp_path):
    """Un symbole sans broche ne se cable pas : le garder ferait disparaitre
    en silence toutes les liaisons du composant qui l'utiliserait."""
    _symbole(tmp_path, "Muet", {})
    assert "Muet" not in eretro_symboles.charger(str(tmp_path))


def test_un_symbole_corrompu_n_empeche_pas_les_autres(tmp_path):
    """Robustesse exigee par la spec : on lit le dossier d'un TIERS, qui
    bouge sans nous prevenir."""
    _symbole(tmp_path, "Bon", {"1": (0, 0)})
    with open(os.path.join(str(tmp_path), "Casse.xml"), "w", encoding="utf-8") as f:
        f.write("<DataItem><Name>Casse</Name><datapin>")   # jamais referme
    formes = eretro_symboles.charger(str(tmp_path))
    assert "Bon" in formes and "Casse" not in formes


def test_un_dossier_absent_ne_leve_pas(tmp_path):
    """La CI n'a pas son dossier, et le .exe livre non plus."""
    assert eretro_symboles.charger(os.path.join(str(tmp_path), "nexiste_pas")) == {}


def test_le_chemin_vient_de_la_variable_d_environnement(tmp_path, monkeypatch):
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    assert eretro_symboles.chemin_par_defaut() == str(tmp_path)


@pytest.mark.skipif(not os.path.isdir(_DOSSIER_REEL), reason="ERetroDesign absent")
def test_sa_vraie_bibliotheque_se_charge():
    """Garde-fou anti-test-creux : les tests ci-dessus tournent sur des
    symboles que NOUS fabriquons. Celui-ci lit les siens."""
    formes = eretro_symboles.charger(_DOSSIER_REEL)
    assert {"Résistance", "Capa", "AOP", "Diode", "GND", "Self", "2N2B"} <= set(formes)
    r = formes["Résistance"]
    assert set(r["pins"]) == {"1", "2"}
    assert r["pins"]["1"][:2] == (80, 0)
    assert r["pins"]["2"][:2] == (-80, 0)
    aop = formes["AOP"]
    assert set(aop["pins"]) == {"+", "-", "s"}, \
        "ses noms de broches sont ceux de nos plans _TYPE_VERS_FORME"
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_symboles.py -q`
Attendu : `ModuleNotFoundError: No module named 'circuit_analyzer.eretro_symboles'`

- [ ] **Step 3 : implémenter** — `circuit_analyzer/eretro_symboles.py`

```python
"""@file eretro_symboles.py
@brief Lit la bibliotheque VIVANTE d'ERetroDesign et la rend au format `_FORME`.

Sa bibliotheque = UN <DataItem> complet par composant dans `LibItem/Lib/`,
depuis son [MODIF 2026-07-24] (Form1.cs:6104). NE PAS confondre avec
`bin/Debug/Lib/` : fonds MORT, symboles a ~997x201, sans Name ni typ, dont 2
noms seulement sur les 36 employes par ses vraies cartes.

Aucune dependance au reste du projet : c'est `xml.py` qui importe ce module,
l'inverse ferait un cycle.
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

    `ERETRO_LIB` l'emporte : le dossier du collegue n'est pas toujours dans le
    depot, et un chemin en dur serait le meme piege que ses `<ImageTop>`
    absolus, qui cassent des qu'un fichier bouge.
    """
    depuis_env = os.environ.get("ERETRO_LIB")
    if depuis_env:
        return depuis_env
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
```

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_symboles.py -q`
Attendu : 8 passed (le dernier `skipped` si `ERetroDesign/` est absent).

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/eretro_symboles.py
git add tests/test_eretro_symboles.py
git commit -m "feat(interop): chargeur de sa bibliotheque vivante LibItem/Lib"
```

---

### Task 2 : ses formes l'emportent, les nôtres restent en repli

**Files:**
- Modify: `circuit_analyzer/xml.py` (après `_TYP_COMPOSANT`, ~l. 297)
- Test: `tests/test_eretro_symboles.py`

**Interfaces:**
- Consumes: `eretro_symboles.charger()` (Task 1).
- Produces: `circuit_analyzer.xml._FORME_MAISON: dict` — les formes historiques, avant fusion. `_FORME` reste le nom consommé partout ailleurs.

- [ ] **Step 1 : écrire les tests qui échouent** — à la fin de `tests/test_eretro_symboles.py`

```python
def test_ses_formes_ecrasent_les_notres_a_nom_egal(tmp_path, monkeypatch):
    """Decision du boss : SA geometrie fait foi sur les noms communs."""
    _symbole(tmp_path, "Résistance", {"1": (80, 0), "2": (-80, 0)}, segments=3)
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    import importlib

    from circuit_analyzer import xml as cx
    importlib.reload(cx)
    try:
        assert cx._FORME["Résistance"]["segment"].count("<DataSegment>") == 3
        assert cx._FORME_MAISON["Résistance"]["segment"].count("<DataSegment>") != 3
    finally:
        monkeypatch.delenv("ERETRO_LIB")
        importlib.reload(cx)


def test_nos_orphelines_survivent_a_la_fusion(tmp_path, monkeypatch):
    """Il n'a ni MOSFET ni Fusible ni PuceN : les ecraser par un dict vide
    supprimerait des formes dont l'export depend."""
    _symbole(tmp_path, "Résistance", {"1": (80, 0), "2": (-80, 0)})
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    import importlib

    from circuit_analyzer import xml as cx
    importlib.reload(cx)
    try:
        assert {"MOSFET", "Fusible", "Puce4", "Puce8"} <= set(cx._FORME)
    finally:
        monkeypatch.delenv("ERETRO_LIB")
        importlib.reload(cx)


def test_le_typ_reste_le_notre(tmp_path, monkeypatch):
    """MESURE : son GND.xml porte typ=0 alors que le notre vaut 71 ('G'),
    valeur dont `eretro.classer_rail` se sert pour reconnaitre une masse.
    Adopter son typ ferait perdre la classification des rails."""
    _symbole(tmp_path, "GND", {"1": (0, -47)}, typ="0")
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    import importlib

    from circuit_analyzer import xml as cx
    importlib.reload(cx)
    try:
        assert cx._TYP_COMPOSANT["GND"] == 71
    finally:
        monkeypatch.delenv("ERETRO_LIB")
        importlib.reload(cx)
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_symboles.py -q -k fusion or notre or ecrasent`
Attendu : `AttributeError: module 'circuit_analyzer.xml' has no attribute '_FORME_MAISON'`

- [ ] **Step 3 : implémenter** — dans `circuit_analyzer/xml.py`, juste après `_TYP_COMPOSANT` (l. 297)

Ajouter l'import en tête de fichier, à côté des autres imports du paquet :

```python
from circuit_analyzer import eretro_symboles
```

Puis, après la définition de `_TYP_COMPOSANT` :

```python
#: Nos formes historiques, AVANT fusion. Conservees telles quelles : ce sont
#: elles qui servent de repli quand son dossier est absent (CI, .exe livre),
#: et le point de comparaison quand un dessin diverge.
_FORME_MAISON = {nom: dict(forme) for nom, forme in _FORME.items()}


def _fusionner_bibliotheque_eretro():
    """@brief Superpose SA bibliotheque vivante sur nos formes maison.

    Decision du boss (2026-07-31) : sur les noms communs, SA geometrie fait
    foi — nos deux bibliotheques sont deux copies divergees de la meme, et il
    faut une seule source. Nos formes orphelines (MOSFET, Fusible, PuceN,
    Relais...) sont CONSERVEES : il ne les a pas, et l'export en depend.

    Le `typ`, lui, ne suit PAS le symbole. On partage la geometrie, pas la
    semantique electrique : son `GND.xml` porte `typ=0` la ou le notre vaut 71
    ('G'), la valeur meme dont `eretro.classer_rail` se sert pour reconnaitre
    une masse. D'ou un `setdefault`, qui ne comble qu'une entree absente.
    """
    for nom, forme in eretro_symboles.charger().items():
        _TYP_COMPOSANT.setdefault(nom, forme["typ"])
        _FORME[nom] = {cle: valeur for cle, valeur in forme.items() if cle != "typ"}


_fusionner_bibliotheque_eretro()
```

- [ ] **Step 4 : vérifier le vert + la non-régression**

```bash
PYTHONUTF8=1 python -m pytest tests/test_eretro_symboles.py tests/test_xml_generator.py \
  tests/test_eretro_patch.py tests/test_retour_fidele_cartes.py -q
```
Attendu : tout vert. Si un test de `test_xml_generator.py` rougit sur une
coordonnée, c'est que sa géométrie a remplacé la nôtre — le comportement
VOULU : mettre le test à jour en le disant explicitement dans son message.

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/xml.py
git add tests/test_eretro_symboles.py
git commit -m "feat(interop): sa bibliotheque prime, nos formes servent de repli"
```

---

### Task 3 : la référence du composant voyage dans le fichier

**Files:**
- Modify: `circuit_analyzer/xml.py` — `_Comp` (l. 305-307), `_Generateur.ajouter` (l. 324), `_xml_composant` (l. 469), l'appel `gen.ajouter` (l. 884)
- Test: `tests/test_export_lisible.py` (créé)

**Interfaces:**
- Consumes: rien de Task 1-2.
- Produces: `_Comp.ref: str` (défaut `""`) ; `_Generateur.ajouter(..., ref="")`.

**Pourquoi :** mesuré avec son `XmlSerializer`, tous nos composants sortent avec
`ref=''`. Sans référence, son éditeur n'affiche aucun `R1`/`U1` : le schéma est
illisible, ce qui est le premier reproche du boss.

- [ ] **Step 1 : écrire les tests qui échouent** — `tests/test_export_lisible.py`

```python
"""@file test_export_lisible.py
@brief Ce que SON editeur doit pouvoir afficher d'un schema que NOUS generons.

Defauts mesures en desserialisant nos sorties avec son XmlSerializer (harnais
net472). Ne PAS ajouter d'assertion sur <TL>/<BR> : (50,25)/(210,121) est une
constante de son format, portee par les 209 composants poses de ses 4 cartes.
"""
import xml.etree.ElementTree as ET

from circuit_analyzer.composant import Composant
from circuit_analyzer.xml import generer_xml


def test_chaque_composant_porte_sa_reference():
    comps = [Composant("R1", "R", {"1": "IN", "2": "N1"}, "10k"),
             Composant("C1", "C", {"1": "N1", "2": "GND"}, "100n")]
    racine = ET.fromstring(generer_xml(comps))
    refs = [(d.findtext("reference") or "").strip()
            for d in racine.findall("./CmpntL/DataItem")]
    assert "R1" in refs and "C1" in refs


def test_la_reference_ne_pollue_pas_la_valeur():
    """`value` porte 10k, PAS R1 : son editeur affiche les deux separement."""
    racine = ET.fromstring(generer_xml(
        [Composant("R1", "R", {"1": "IN", "2": "N1"}, "10k")]))
    d = racine.find("./CmpntL/DataItem")
    assert (d.findtext("reference") or "").strip() == "R1"
    assert (d.findtext("value") or "").strip() == "10k"


def test_les_rails_ajoutes_n_usurpent_pas_une_reference():
    """Les symboles de masse/alim naissent d'un NET, pas d'un composant :
    leur donner la reference d'un voisin creerait un doublon chez lui."""
    racine = ET.fromstring(generer_xml(
        [Composant("R1", "R", {"1": "IN", "2": "GND"}, "10k")]))
    refs = [(d.findtext("reference") or "").strip()
            for d in racine.findall("./CmpntL/DataItem")]
    assert refs.count("R1") == 1
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_export_lisible.py -q`
Attendu : FAIL, `assert 'R1' in ['', '']`

- [ ] **Step 3 : implémenter**

1. `_Comp` (l. 305-307) — ajouter le champ en DERNIER pour ne casser aucun appel positionnel :

```python
@dataclass
class _Comp:
    """@brief Composant placé sur le schéma (id, nom de forme, valeur, position, forme)."""
    cid: int; name: str; value: str; x: int; y: int; angle: int = 0; shape: str = ""; group_id: int = 0
    ref: str = ""
```

2. `_Generateur.ajouter` (l. 324) — nouveau paramètre nommé, et le passer au `_Comp` :

```python
    def ajouter(self, nom, valeur="", x=0, y=0, angle=0, forme="", group_id=0,
                ref="") -> int:
```

Dans le corps, ajouter `ref=ref` à la construction du `_Comp`.

3. `_xml_composant` (l. 469) — remplacer `<reference />` :

```python
      <Name>{_esc(comp.name)}</Name><Group /><reference>{_esc(comp.ref)}</reference><value>{_esc(comp.value)}</value>
```

4. L'appel de `generer_xml` (l. 884) :

```python
        cid = gen.ajouter(nom_forme, comp.value, x=x, y=y, ref=comp.ref,
                          group_id=ids_groupes.get(comp.ref, 0))
```

Les rails ajoutés depuis les nets n'ont pas de `ref` : leur `ajouter` reste
inchangé et `_Comp.ref` vaut `""`, donc `<reference />` sort vide — comportement
attendu par `test_les_rails_ajoutes_n_usurpent_pas_une_reference`.

- [ ] **Step 4 : vérifier le vert**

```bash
PYTHONUTF8=1 python -m pytest tests/test_export_lisible.py tests/test_xml_generator.py -q
```

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/xml.py
git add tests/test_export_lisible.py
git commit -m "feat(interop): la reference du composant voyage dans le XML exporte"
```

---

### Task 4 : plus de boîtier fantôme sur les masses et les alimentations

**Files:**
- Modify: `circuit_analyzer/xml.py` — `_TYPE_VERS_FORME` (l. 279-291)
- Test: `tests/test_export_lisible.py`

**Interfaces:**
- Consumes: rien.
- Produces: rien de nouveau ; `_TYPE_VERS_FORME` gagne les clés `"GND"`, `"VCC"`, `"VSS"`.

**Pourquoi :** `_TYPE_VERS_FORME` n'a pas d'entrée `GND`. Un
`Composant("GND1","GND",{"1":"GND"})` tombe donc dans la branche « toutes les
broches numérotées » (`xml.py:829`) — `"1"` **est** un chiffre — et ressort en
boîtier DIP 4 broches. Mesuré : 3 composants en entrée, 4 en sortie.

- [ ] **Step 1 : écrire les tests qui échouent**

```python
def test_une_masse_ne_devient_pas_un_boitier_dip():
    """`_TYPE_VERS_FORME` sans entree GND -> la broche numerotee "1" faisait
    tomber le composant dans la branche PuceN (xml.py:829)."""
    racine = ET.fromstring(generer_xml(
        [Composant("R1", "R", {"1": "IN", "2": "GND"}, "10k"),
         Composant("GND1", "GND", {"1": "GND"}, "")]))
    noms = [d.findtext("Name") for d in racine.findall("./CmpntL/DataItem")]
    assert not any((n or "").startswith("Puce") for n in noms), \
        f"boitier fantome : {noms}"


def test_l_alimentation_non_plus():
    racine = ET.fromstring(generer_xml(
        [Composant("R1", "R", {"1": "VCC", "2": "N1"}, "10k"),
         Composant("VCC1", "VCC", {"1": "VCC"}, "")]))
    noms = [d.findtext("Name") for d in racine.findall("./CmpntL/DataItem")]
    assert not any((n or "").startswith("Puce") for n in noms), \
        f"boitier fantome : {noms}"


def test_les_composants_declares_sont_tous_emis():
    """Corollaire mesurable : 2 composants en entree, 2 formes en sortie
    (plus les rails nes des nets, qui ne portent pas de reference)."""
    racine = ET.fromstring(generer_xml(
        [Composant("R1", "R", {"1": "IN", "2": "GND"}, "10k"),
         Composant("GND1", "GND", {"1": "GND"}, "")]))
    refs = [(d.findtext("reference") or "").strip()
            for d in racine.findall("./CmpntL/DataItem")]
    assert "R1" in refs and "GND1" in refs
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_export_lisible.py -q -k fantome`
Attendu : FAIL, `boitier fantome : ['Résistance', 'Puce4', 'GND']`

- [ ] **Step 3 : implémenter** — dans `_TYPE_VERS_FORME` (l. 279), avant l'entrée `"X"` :

```python
    # Les rails portent une broche NUMEROTEE ("1") : sans entree ici, ils
    # tombaient dans la branche « toutes broches numerotees » (l. 829) et
    # ressortaient en boitier DIP 4 broches. Mesure : 3 composants en entree,
    # 4 en sortie, dont un fantome.
    "GND": ("GND", {"1": "1"}),
    "VCC": ("VCC", {"1": "1"}),
    "VSS": ("Vss", {"1": "1"}),
```

**Attention — étape OBLIGATOIRE, pas facultative.** Le nom de broche de droite
doit exister dans `_FORME[forme]["pins"]` **après la fusion de Task 2**, donc
tel que SA bibliothèque le définit. Un nom absent fait silencieusement perdre la
liaison du rail.

Mesure faite au moment d'écrire ce plan : son `GND.xml` a une broche sans
`Pname` ni `Pnumber`, donc le chargeur la nomme `"1"` par repli — d'où
`{"1": "1"}`. `VCC` et `Vss` n'ont pas été vérifiés. Lancer :

```bash
PYTHONUTF8=1 python -c "from circuit_analyzer.xml import _FORME; \
print({f: list(_FORME[f]['pins']) for f in ('GND','VCC','Vss') if f in _FORME})"
```

et aligner la droite de chaque entrée sur ce qui sort. Si `_FORME` ne contient
pas `VCC` (il a `VCC+`/`VCC-`, pas `VCC`), c'est notre forme maison qui reste —
et c'est le comportement voulu.

- [ ] **Step 4 : vérifier le vert**

```bash
PYTHONUTF8=1 python -m pytest tests/test_export_lisible.py tests/test_xml_generator.py \
  tests/test_eretro_patch.py -q
```

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/xml.py
git add tests/test_export_lisible.py
git commit -m "fix(interop): les rails GND/VCC/VSS ne sortent plus en boitier fantome"
```

---

### Task 5 : pousser nos symboles orphelins dans sa bibliothèque

**Files:**
- Modify: `circuit_analyzer/eretro_lib.py` (après `ecrire_dans_dossier`, l. 182)
- Test: `tests/test_eretro_symboles.py`

**Interfaces:**
- Consumes: `circuit_analyzer.xml._FORME`, `_TYP_COMPOSANT`.
- Produces: `ecrire_formes_dans_dossier(dossier: str, formes: dict, typs: dict | None = None) -> list[str]` — renvoie les chemins écrits.

**Pourquoi :** il n'a ni `MOSFET`, ni `Fusible`, ni `Relais`, ni `PuceN`. Sans
eux, il ne peut pas poser à la main un composant que nos exports contiennent.
`ecrire_dans_dossier` ne convient pas : il part du modèle boîte+brochage de
l'onglet Composants et REGENERE une boîte générique, ce qui perdrait nos
dessins. Il faut un écrivain qui émette notre géométrie verbatim.

- [ ] **Step 1 : écrire les tests qui échouent**

```python
def test_pousser_ecrit_un_fichier_par_forme(tmp_path):
    from circuit_analyzer.eretro_lib import ecrire_formes_dans_dossier
    formes = {"MonSymbole": {"pins": {"1": (-80, 0, 0), "2": (80, 0, 1)},
                             "polygon": "", "arc": "",
                             "segment": "<DataSegment><Spoint><X>-10</X>"
                                        "<Y>0</Y></Spoint><Epoint><X>10</X>"
                                        "<Y>0</Y></Epoint></DataSegment>"}}
    ecrits = ecrire_formes_dans_dossier(str(tmp_path), formes)
    assert len(ecrits) == 1
    assert os.path.isfile(os.path.join(str(tmp_path), "MonSymbole.xml"))


def test_le_fichier_pousse_est_relisible_par_notre_chargeur(tmp_path):
    """Aller-retour : ce qu'on lui envoie doit revenir identique chez nous.
    C'est la seule verification d'integrite qu'on puisse faire sans son GUI."""
    from circuit_analyzer.eretro_lib import ecrire_formes_dans_dossier
    formes = {"MonSymbole": {"pins": {"1": (-80, 0, 0), "2": (80, 0, 1)},
                             "polygon": "", "arc": "",
                             "segment": "<DataSegment><Spoint><X>-10</X>"
                                        "<Y>0</Y></Spoint><Epoint><X>10</X>"
                                        "<Y>0</Y></Epoint></DataSegment>"}}
    ecrire_formes_dans_dossier(str(tmp_path), formes)
    relu = eretro_symboles.charger(str(tmp_path))
    assert relu["MonSymbole"]["pins"] == {"1": (-80, 0, 0), "2": (80, 0, 1)}


def test_on_n_ecrase_jamais_un_symbole_a_lui(tmp_path):
    """Regle absolue : sa bibliotheque est SON travail. `ecrire_dans_dossier`
    documente deja qu'on n'efface jamais son dossier ; ici on ne remplace pas
    davantage un fichier existant."""
    from circuit_analyzer.eretro_lib import ecrire_formes_dans_dossier
    cible = os.path.join(str(tmp_path), "Sien.xml")
    with open(cible, "w", encoding="utf-8") as f:
        f.write("<DataItem><Name>Sien</Name></DataItem>")
    ecrits = ecrire_formes_dans_dossier(
        str(tmp_path), {"Sien": {"pins": {"1": (0, 0, 0)},
                                 "polygon": "", "segment": "", "arc": ""}})
    assert ecrits == []
    with open(cible, encoding="utf-8") as f:
        assert f.read() == "<DataItem><Name>Sien</Name></DataItem>"


def test_la_boite_de_palette_porte_la_constante_de_son_format(tmp_path):
    """A TL=BR=(0,0) le composant s'affiche dans sa palette mais est
    IMPOSSIBLE a selectionner (eretro_lib.py:37-45)."""
    from circuit_analyzer.eretro_lib import ecrire_formes_dans_dossier
    ecrire_formes_dans_dossier(
        str(tmp_path), {"S": {"pins": {"1": (0, 0, 0)},
                              "polygon": "", "segment": "", "arc": ""}})
    r = ET.parse(os.path.join(str(tmp_path), "S.xml")).getroot()
    assert (r.find("TL").findtext("X"), r.find("TL").findtext("Y")) == ("50", "25")
    assert (r.find("BR").findtext("X"), r.find("BR").findtext("Y")) == ("210", "121")
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_symboles.py -q -k pousser or pousse or ecrase or palette`
Attendu : `ImportError: cannot import name 'ecrire_formes_dans_dossier'`

- [ ] **Step 3 : implémenter** — dans `circuit_analyzer/eretro_lib.py`, après `ecrire_dans_dossier`

```python
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
```

- [ ] **Step 4 : vérifier le vert**

```bash
PYTHONUTF8=1 python -m pytest tests/test_eretro_symboles.py tests/test_eretro_lib.py -q
```

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/eretro_lib.py
git add tests/test_eretro_symboles.py
git commit -m "feat(interop): pousser nos symboles orphelins dans sa bibliotheque"
```

---

### Task 6 : preuve contre son binaire, et suite complète

**Files:**
- Aucun fichier du dépôt modifié. Scripts **hors dépôt** (scratchpad).

**Interfaces:**
- Consumes: tout ce qui précède.
- Produces: rien.

**Pourquoi :** les cinq tâches précédentes se testent contre notre propre lecture
du format. La seule preuve qui vaille sur une question d'interopérabilité est la
désérialisation par **son** `XmlSerializer` — le harnais net472 existe déjà dans
le scratchpad (`cstest/`) et référence `ERetroDesign/ERetroDesign/bin/Debug/ERetroDesign.exe`.

- [ ] **Step 1 : régénérer les trois schémas simples**

Script scratchpad, **hors dépôt** :

```python
"""Schemas SIMPLES produits par NOTRE generateur, pour ouverture chez lui."""
import os
import sys

from circuit_analyzer.composant import Composant
from circuit_analyzer.xml import generer_xml

DST = sys.argv[1]
os.makedirs(DST, exist_ok=True)

CAS = {
    "01_deux_resistances": [
        Composant("R1", "R", {"1": "IN", "2": "N1"}, "10k"),
        Composant("R2", "R", {"1": "N1", "2": "GND"}, "22k"),
    ],
    "02_rc_masse": [
        Composant("R1", "R", {"1": "IN", "2": "N1"}, "1k"),
        Composant("C1", "C", {"1": "N1", "2": "GND"}, "100n"),
        Composant("GND1", "GND", {"1": "GND"}, ""),
    ],
    "03_aop_inverseur": [
        Composant("R1", "R", {"1": "IN", "2": "N1"}, "10k"),
        Composant("R2", "R", {"1": "N1", "2": "OUT"}, "100k"),
        Composant("U1", "U", {"IN-": "N1", "IN+": "GND", "OUT": "OUT"}, "TL071"),
        Composant("GND1", "GND", {"1": "GND"}, ""),
    ],
}

for nom, comps in CAS.items():
    chemin = os.path.join(DST, nom + ".xml")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(generer_xml(comps))
    print("ecrit", chemin, os.path.getsize(chemin), "octets")
```

Lancer avec `PYTHONPATH` sur la racine du dépôt :

```bash
PYTHONUTF8=1 PYTHONPATH=. python <script> <dossier_scratchpad>/simple
```

**Repère mesuré avant ce plan** (état à battre) : `02_rc_masse` sortait
**4 composants pour 3 déclarés** (un `Puce4` fantôme) et `reference` vide
partout.

- [ ] **Step 2 : les passer à son désérialiseur**

Le harnais doit vérifier, pour chaque fichier :
- désérialisation sans exception (prouve que l'ordre des champs tient) ;
- `reference` non vide sur chaque composant issu d'un `Composant` déclaré ;
- aucun composant dont le nom commence par `Puce` alors qu'aucune puce n'est déclarée ;
- `poly + seg + arc > 0` sur chaque composant (aucun composant muet) ;
- `TL=(50,25)` et `BR=(210,121)` — la constante de son format, inchangée ;
- connexité : tous les fils reliés à leurs deux bouts.

Attendu : les 3 fichiers passent les 6 points.

- [ ] **Step 3 : suite complète**

```bash
PYTHONUTF8=1 python -m pytest -q
```
Attendu : **0 failed**. Le retour fidèle des 4 vraies cartes doit rester vert —
il patche le fichier reçu et ne dépend pas de la génération. Si
`test_500_portes_sous_budget` casse, le relancer isolé (flake connu).

- [ ] **Step 4 : livrer les schémas au boss**

Copier les 3 XML dans `C:\Users\Utilisateur\Desktop\schemas_generes_a_tester\`
et lui dire de les ouvrir dans ERetroDesign **puis d'appuyer sur `F`** — sa vue
n'est jamais recadrée à l'ouverture (`RestoreBoard` n'appelle pas
`CenterDiagram`), et sans ça le schéma peut tomber hors de l'écran.

- [ ] **Step 5 : supprimer les scripts du scratchpad, ne rien committer**

---

## Vérification (bout en bout)

1. **Tests** : `PYTHONUTF8=1 python -m pytest -q` — 0 failed, dont
   `tests/test_eretro_symboles.py` et `tests/test_export_lisible.py` (nouveaux).
2. **Repli prouvé** : `ERETRO_LIB=/dossier/inexistant PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -q`
   reste vert — l'application fonctionne sans son dossier.
3. **Preuve C#** : les 3 schémas simples passent les 6 points de la Task 6.
4. **À la main, par le boss** : ouvrir les 3 XML dans ERetroDesign, appuyer sur
   `F`, vérifier que les références s'affichent et qu'aucun boîtier inattendu
   n'apparaît.

## Réserves connues

1. Le rendu de nos symboles poussés dans sa bibliothèque n'a jamais été validé
   visuellement côté C# (réserve héritée de `eretro_lib.py`).
2. `TATA` et `yoyo` ressemblent à des symboles d'essai ; `TATA` porte des broches
   à ±400, hors de l'échelle commune. Ils sont chargés comme les autres — à
   revoir s'ils polluent la palette.
3. La lecture directe de son dossier reste fragile par nature ; c'est le repli
   qui rend ce choix tenable, d'où l'insistance des tests sur ce chemin.
4. Le rendu de NOS vues (schemdraw) n'est pas touché par ce plan : il fait
   l'objet du Plan 2, avec sa propre conception.
