# Retour fidèle vers ERetroDesign (chantier A) — Plan d'implémentation

> **Pour l'exécutant :** SOUS-COMPÉTENCE REQUISE — utiliser
> `superpowers:subagent-driven-development` (recommandé) ou
> `superpowers:executing-plans` pour dérouler ce plan tâche par tâche. Les
> étapes sont des cases à cocher (`- [ ]`).

**Spec de référence :** `docs/superpowers/specs/2026-07-29-retour-fidele-eretrodesign-design.md` (commit `ad8a062`).

> ## ⚠️ ARBITRÉ LE 2026-07-30 — NE PAS RECOPIER LES DRAPEAUX DE CE PLAN
>
> **Ce plan est LIVRÉ.** Il reste ici comme trace, mais un point a été tranché
> en fin de chantier et **tout ce qu'il dit de `<Begrp>` / `<BeIngrp>` est
> périmé** : la v1 livrée n'écrit **que `<GpId>`**.
>
> Concrètement, ne recopiez PAS d'ici :
> - `_poser_groupe(element, gid, balise_drapeau)` (§Task 2) — **fonction
>   supprimée du code** ; une seule balise est atomique par définition ;
> - les assertions `attendu = "true" if int(...GpId...) else "false"`
>   (§Task 2, §Task 4) — elles **échoueraient** aujourd'hui ;
> - `_CHAMPS_GROUPE = {"GpId", "Begrp", "BeIngrp"}` (§Task 2) — le gardien réel
>   est resserré à `{"GpId"}`, précisément pour faire **échouer** toute
>   écriture de drapeau.
>
> **Pourquoi.** La preuve C# de la Task 7 a montré que `Begrp=true` interdit la
> sélection individuelle d'un composant dans son éditeur
> (`ERetroDesign/ERetroDesign/Forms/Form1.cs:2192, 2269, 2337, 2697, 3767,
> 5510`), tandis que l'appartenance fait autorité dans `<GrpL>`, que nous
> n'écrivons pas. Les composants groupés seraient devenus **inertes** chez lui.
>
> **Source de vérité :** la docstring de `ecrire_groupes`
> (`circuit_analyzer/eretro_patch.py`).

**Goal :** l'export XML de l'onglet Analyse renvoie **le fichier du collègue
lui-même**, enrichi de la seule information d'analyse (`GpId`), au lieu
d'une carte régénérée qui perd ses positions, ses symboles, ses angles et ses
zooms.

**Architecture :** `lire_xml` conserve l'arbre `ElementTree` d'origine et publie
un pont `ref → élément XML` sur un attribut additif `.source` de
`ListeComposantsXML`. Un module neuf `circuit_analyzer/eretro_patch.py` prend ce
pont et **écrit uniquement** `<GpId>`/`<Begrp>` sur les éléments existants, sans
jamais régénérer le document. `generer_xml` n'est pas touché : il reste le
chemin des schémas créés chez nous.

**Tech Stack :** Python 3.11, `xml.etree.ElementTree` (stdlib), pytest. Aucune
nouvelle dépendance.

## Global Constraints

- Commits en **français**, **jamais** de footer `Co-Authored-By: Claude` ni
  `Generated with Claude Code`.
- **Jamais `git add -A`** : fichiers ajoutés un par un.
- **Ne jamais committer** `custom_circuits.json` ni `component_library.json`.
- `docs.rar`, `ERetroDesign/`, `CARTE POUR TESTER (VRAI TEST)/`, `test14.xml`,
  `dist_demo/` : **lecture seule, jamais committés**.
- `PYTHONUTF8=1` sur toutes les commandes pytest.
- `schemdraw==0.22` pinné (0.23 casse ~30 tests de rendu).
- Branche `rewrite-simple` ; **rien n'est poussé sans accord explicite du boss**.
- Python réel : `Python311`. Identité git : `Mohammed-Raid`.
- **Aucune balise non citée dans ce plan ne doit être écrite, déplacée, créée ou
  supprimée** dans un fichier reçu. C'est l'invariant central du chantier.

## Faits vérifiés sur les 4 cartes réelles (2026-07-29)

À citer tel quel, ne pas re-supposer :

| Fait | Conséquence |
|---|---|
| `<DataItem>`, `<CComp>` et `<Line>` portent **tous** déjà un `<GpId>` (100 % des éléments des 4 cartes) | On **modifie** un élément existant, on n'en **insère** jamais |
| Tous les `GpId` valent `0`, tous les `Begrp` valent `false` | Le collègue n'utilise pas le groupement : notre écriture inaugure ce chemin |
| Aucune carte ne contient de `<GrpL>` | v1 n'en écrit pas — voir §Réserve de la spec |
| L'enfant compagnon d'un `<Line>` s'appelle **`BeIngrp`**, pas `Begrp` | Ne pas confondre : `Begrp` sur composant, `BeIngrp` sur fil |
| `<CComp>` de `PowtranAlim20260809.xml` : `Name=Optocoupleur_simple`, `zmH=0.799999952`, `DItemL/DataItem` = 2 | Cas de test des puces composées |
| `TL`/`BR` ne sont pas dans le repère de `CtrIem` (`TL 50,25` / `BR 210,121` pour `CtrIem 168,330` sur `PG 2`) | Ne **jamais** fabriquer de rectangle de groupe |

## Structure des fichiers

| Fichier | Responsabilité ajoutée |
|---|---|
| `circuit_analyzer/eretro.py` | Dataclass `SourceXML` (posée ici : `eretro` n'importe aucun module du projet, donc pas de cycle avec `xml.py`). Ajout de la clé `'xml'` sur les entrées d'éléments composés. |
| `circuit_analyzer/xml.py` | Ajout de la clé `'xml'` (Étape 1), collecte `ligne_vers_cids` et `cid_vers_ref`, publication de `.source`. **Aucune ligne de `generer_xml` modifiée.** |
| `circuit_analyzer/eretro_patch.py` | **Créé.** `ecrire_groupes(source, composants, resultats) -> str`. Le seul écrivain du chantier. |
| `gui/tab_analyze.py` | `_export_xml` route vers `eretro_patch` si `.source` existe, sinon repli `generer_xml` **avec avertissement à l'écran**. |
| `tests/test_eretro_patch.py` | **Créé.** Pont, patch simple, composés, fils, repli. |
| `tests/test_retour_fidele_cartes.py` | **Créé.** Invariance arbre-à-arbre et stabilité de netlist sur les 4 vraies cartes (skip si absentes). |

---

### Task 1 : Le pont `ref → élément XML`

Tâche de **données pures** : rien ne change dans le comportement existant, on
expose seulement ce que `lire_xml` savait déjà et jetait.

**Files:**
- Modify: `circuit_analyzer/eretro.py` (fin de fichier + `extraire_composes`, l. 427/436/443)
- Modify: `circuit_analyzer/xml.py` (l. 1199, l. 1289-1302, après la boucle l. 1422)
- Test: `tests/test_eretro_patch.py` (créé)

**Interfaces:**
- Consomme : rien.
- Produit :
  ```python
  @dataclass
  class SourceXML:
      arbre: "ET.ElementTree"            # l'arbre PARSÉ d'origine, jamais recréé
      elements: dict[str, "ET.Element"]  # ref composant -> <DataItem> ou <CComp>
      lignes: list["ET.Element"]         # <Line> de lineL, dans l'ordre du fichier
      lignes_refs: dict[int, tuple]      # indice de fil -> (ref_a, ref_b), refs connues seulement
  ```
  et `ListeComposantsXML.source: SourceXML | None` (None si la liste ne vient
  pas d'un XML).

- [ ] **Step 1 : écrire les tests qui échouent** — `tests/test_eretro_patch.py`

```python
"""@file test_eretro_patch.py
@brief Retour fidele vers ERetroDesign : pont ref->element et ecriture des groupes.
"""
import os
import xml.etree.ElementTree as ET

import pytest

from circuit_analyzer.composant import Composant
from circuit_analyzer.xml import generer_xml, lire_xml

_DOSSIER_REEL = "CARTE POUR TESTER (VRAI TEST)"


def _fichier_synthetique(tmp_path, comps=None):
    """@brief Ecrit un BoardSCH valide via generer_xml et renvoie son chemin.

    On part de notre PROPRE generateur : il produit un document que lire_xml
    sait relire, donc le test n'a pas besoin des cartes reelles (absentes en CI).
    """
    comps = comps or [
        Composant("R1", "R", {"1": "IN", "2": "N1"}, "10k"),
        Composant("C1", "C", {"1": "N1", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "N1", "IN-": "N2", "OUT": "OUT"}, ""),
    ]
    p = os.path.join(str(tmp_path), "synth.xml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(generer_xml(comps))
    return p


def test_source_absente_quand_la_liste_ne_vient_pas_d_un_xml():
    assert getattr([], "source", None) is None


def test_lire_xml_publie_l_arbre_et_le_pont(tmp_path):
    comps = lire_xml(_fichier_synthetique(tmp_path))
    src = comps.source
    assert src is not None
    assert isinstance(src.arbre, ET.ElementTree)
    # Une entree de pont par composant emis, et pas une de plus.
    assert set(src.elements) == {c.ref for c in comps}


def test_le_pont_designe_le_bon_element(tmp_path):
    comps = lire_xml(_fichier_synthetique(tmp_path))
    src = comps.source
    items = src.arbre.getroot().findall(".//CmpntL/DataItem")
    for c in comps:
        assert src.elements[c.ref] in items


def test_le_pont_expose_les_fils_dans_l_ordre_du_fichier(tmp_path):
    comps = lire_xml(_fichier_synthetique(tmp_path))
    src = comps.source
    assert src.lignes == src.arbre.getroot().findall(".//lineL/Line")
    # Chaque fil resolu designe deux refs connues du pont.
    for idx, (ra, rb) in src.lignes_refs.items():
        assert 0 <= idx < len(src.lignes)
        assert ra in src.elements and rb in src.elements


@pytest.mark.skipif(not os.path.isdir(_DOSSIER_REEL), reason="cartes reelles absentes")
def test_un_compose_pointe_sur_son_boitier_pas_sur_ses_entrailles():
    chemin = os.path.join(_DOSSIER_REEL, "PowtranAlim20260809.xml")
    comps = lire_xml(chemin)
    src = comps.source
    boitiers = src.arbre.getroot().findall(".//CCmpntL/CComp")
    internes = [r for r in src.elements if "." in r]
    assert internes, "la carte de reference contient une puce composee"
    for ref in internes:
        assert src.elements[ref] in boitiers
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -q`
Attendu : `AttributeError: 'ListeComposantsXML' object has no attribute 'source'`

- [ ] **Step 3 : implémenter — `circuit_analyzer/eretro.py`**

À la fin du fichier (aucun import projet ici : c'est ce qui évite le cycle avec
`xml.py`, qui importe déjà `eretro`) :

```python
@dataclass
class SourceXML:
    """@brief Fichier BoardSCH d'ORIGINE, conserve pour etre patche tel quel.

    On garde l'arbre parse plutot que le chemin : le patch doit ecrire dans les
    MEMES elements que ceux qui ont servi a la lecture, sinon rien ne garantit
    que l'indexation par position (cle de tout le decodage) reste la meme.
    """
    arbre: object                    # ET.ElementTree
    elements: dict                   # ref -> ET.Element (<DataItem> ou <CComp>)
    lignes: list                     # <Line> de lineL, dans l'ordre du fichier
    lignes_refs: dict                # indice de fil -> (ref_a, ref_b)
```

Ajouter `from dataclasses import dataclass` en tête de `eretro.py` (le fichier
n'importe aujourd'hui que `math`, `re`, `unicodedata`).

Dans `extraire_composes`, ajouter la clé `'xml'` aux **trois** dictionnaires
créés — l'élément à patcher est **toujours le boîtier `cc`**, jamais l'item
interne :

```python
            elements_sup[idx] = {'id': idx, 'name': nom_puce, 'value': valeur,
                                 'pins': _lire_broches(cc),
                                 'emettre': True, 'puce': None, 'xml': cc}   # boite noire
...
        elements_sup[idx] = {'id': idx, 'name': nom_puce, 'value': valeur,
                             'pins': _lire_broches(cc),
                             'emettre': False, 'puce': None, 'xml': cc}      # boitier
...
            elements_sup[idx] = {'id': idx, 'name': nom_int, 'value': val_int,
                                 'pins': _lire_broches(item),
                                 'emettre': True, 'puce': (num, nom_puce),
                                 'xml': cc}   # DELIBERE : le boitier, pas `item`.
```

- [ ] **Step 4 : implémenter — `circuit_analyzer/xml.py`**

1. Étape 1, l. 1199, ajouter la clé `'xml'` :

```python
        elements[idx] = {'id': idx, 'name': nom, 'value': valeur, 'pins': broches,
                         'rail': eretro.classer_rail(typc, valeur, len(broches), nom),
                         'geo': eretro.extraire_geometrie(item),
                         'xml': item}
```

2. Boucle des fils (l. 1289), mémoriser les deux extrémités résolues. La liste
   `lignes_xml` sert au patch ; `lignes_cids` sera traduite en refs plus bas :

```python
    ligne_vers_broche: Dict[str, tuple] = {}
    lignes_xml = racine.findall('.//lineL/Line')
    lignes_cids: Dict[int, tuple] = {}
    for idx_fil, fil in enumerate(lignes_xml):
```

   puis, juste après `unir(bf, bl)` (l. 1298) :

```python
        if bf is not None and bl is not None:
            unir(bf, bl)
            lignes_cids[idx_fil] = (bf[0], bl[0])
```

   Attention : `enumerate(racine.findall(...))` était recalculé ici ; on itère
   désormais sur `lignes_xml` pour que le patch et la lecture voient **la même
   liste d'objets**.

3. Dans la boucle de construction (l. 1422), après l'appel à `generer_ref`,
   mémoriser `cid → ref`. Le `ref` est déjà calculé pour chaque composant émis :
   ajouter, juste avant que le `Composant` soit ajouté à `composants`, une
   ligne `cid_vers_ref[cid] = ref`, avec `cid_vers_ref: Dict[int, str] = {}`
   initialisé à côté de `refs_puces` (l. 1398).

   **Attention** : il y a deux branches (type connu / type inconnu) qui
   appellent `generer_ref`. Vérifier avec
   `grep -n "generer_ref(" circuit_analyzer/xml.py` que **chaque** appel est
   suivi de l'enregistrement, sinon le pont sera troué.

4. En fin de `lire_xml`, avant le `return`, publier la source :

```python
    composants.source = eretro.SourceXML(
        arbre=arbre,
        elements={ref: elements[cid]['xml']
                  for cid, ref in cid_vers_ref.items()
                  if elements[cid].get('xml') is not None},
        lignes=lignes_xml,
        lignes_refs={idx: (cid_vers_ref[a], cid_vers_ref[b])
                     for idx, (a, b) in lignes_cids.items()
                     if a in cid_vers_ref and b in cid_vers_ref},
    )
```

5. `ListeComposantsXML.__init__` (l. 1099) : ajouter `self.source = None` et
   compléter la docstring de classe (l. 1094) d'une ligne sur `.source`.

- [ ] **Step 5 : vérifier le vert et la non-régression**

```bash
PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py tests/test_cartes_reelles.py tests/test_xml.py -q
```
Attendu : tout vert. Le pont est **additif** : aucun test existant ne doit bouger.

- [ ] **Step 6 : commit**

```bash
git add circuit_analyzer/eretro.py circuit_analyzer/xml.py tests/test_eretro_patch.py
git commit -m "feat(interop): lire_xml conserve l'arbre d'origine et le pont ref->element"
```

---

### Task 2 : `ecrire_groupes` — composants simples

**Files:**
- Create: `circuit_analyzer/eretro_patch.py`
- Test: `tests/test_eretro_patch.py`

**Interfaces:**
- Consomme : `SourceXML` (Task 1), `_grouper_par_circuit(composants, resultats)`
  (`xml.py:553`, renvoie une `list[_Bloc]` avec `.label` et `.comps`),
  `_ids_groupes_par_ref(blocs) -> dict[str, int]` (`xml.py:786`, ids à partir de 1).
- Produit : `ecrire_groupes(source, composants, resultats=None) -> str` — le
  document XML **patché**, sérialisé en `str` (même contrat de retour que
  `generer_xml`, pour que l'appelant ne change pas d'écriture fichier).

- [ ] **Step 1 : écrire les tests qui échouent** — ajouter à `tests/test_eretro_patch.py`

```python
def _analyser(chemin):
    """@brief Chaine d'analyse minimale : composants + resultats du detecteur."""
    from circuit_analyzer.graph_builder import build_graph
    from circuit_analyzer.matcher import match_patterns
    comps = lire_xml(chemin)
    return comps, match_patterns(build_graph(comps))


def test_patch_ecrit_un_gpid_non_nul_sur_les_composants_groupes(tmp_path):
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    gpids = {int(d.findtext("GpId") or 0) for d in racine.findall(".//CmpntL/DataItem")}
    assert gpids != {0}, "aucun groupe ecrit"


def test_begrp_suit_toujours_gpid(tmp_path):
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    for d in racine.findall(".//CmpntL/DataItem"):
        attendu = "true" if int(d.findtext("GpId") or 0) else "false"
        assert (d.findtext("Begrp") or "").strip() == attendu


def test_patch_sans_resultats_ne_groupe_rien(tmp_path):
    from circuit_analyzer.eretro_patch import ecrire_groupes
    comps = lire_xml(_fichier_synthetique(tmp_path))
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, None))
    assert {int(d.findtext("GpId") or 0)
            for d in racine.findall(".//CmpntL/DataItem")} == {0}


def test_un_composant_absent_de_la_source_ne_cree_rien(tmp_path):
    """Cas limite spec §4 : un composant inconnu du fichier n'ajoute aucun element."""
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    n_avant = len(ET.parse(chemin).getroot().findall(".//CmpntL/DataItem"))
    comps.append(Composant("R99", "R", {"1": "IN", "2": "GND"}, "1k"))
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    assert len(racine.findall(".//CmpntL/DataItem")) == n_avant


def test_patch_ne_touche_a_rien_d_autre(tmp_path):
    """Invariant central : hors GpId/Begrp/BeIngrp, l'arbre est identique."""
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    avant = ET.parse(chemin).getroot()
    apres = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    _comparer_sauf_groupes(avant, apres)


_CHAMPS_GROUPE = {"GpId", "Begrp", "BeIngrp"}


def _comparer_sauf_groupes(a, b, chemin="/"):
    """@brief Egalite RECURSIVE de deux arbres, hors champs de groupe.

    Compare la structure (tag, ordre, nombre d'enfants), le texte et les
    attributs. On compare arbre a arbre et NON octet a octet : ElementTree
    re-serialise tout le document (balises auto-fermantes, espaces), un diff
    textuel serait rouge en permanence et donc jamais relu.
    """
    assert a.tag == b.tag, f"{chemin} : {a.tag} != {b.tag}"
    assert a.attrib == b.attrib, f"{chemin}{a.tag} : attributs modifies"
    ea, eb = list(a), list(b)
    assert [x.tag for x in ea] == [x.tag for x in eb], \
        f"{chemin}{a.tag} : enfants ajoutes, retires ou reordonnes"
    if a.tag not in _CHAMPS_GROUPE:
        assert (a.text or "").strip() == (b.text or "").strip(), \
            f"{chemin}{a.tag} : texte modifie"
    for i, (x, y) in enumerate(zip(ea, eb)):
        _comparer_sauf_groupes(x, y, f"{chemin}{a.tag}[{i}]/")
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -q`
Attendu : `ModuleNotFoundError: No module named 'circuit_analyzer.eretro_patch'`

- [ ] **Step 3 : implémenter** — `circuit_analyzer/eretro_patch.py`

```python
"""@file eretro_patch.py
@brief Ecrit les groupes d'analyse DANS le fichier BoardSCH d'origine.

Contrat unique et non negociable : on MODIFIE des balises existantes, on n'en
cree, ne deplace ni ne supprime aucune. Tout ce qu'on ne comprend pas du format
(et il en reste) ressort donc intact, par construction.

Ne pas confondre avec `generer_xml`, qui FABRIQUE un document depuis une
netlist : lui reinvente positions, formes et zooms, ce qui est correct pour un
schema cree chez nous et destructeur pour une carte recue.
"""
import logging
import xml.etree.ElementTree as ET

from circuit_analyzer.xml import _grouper_par_circuit, _ids_groupes_par_ref

_log = logging.getLogger(__name__)


def _ecrire(element, balise, valeur):
    """@brief Ecrit une balise SI elle existe deja. Renvoie False sinon.

    Refus delibere de creer la balise manquante : l'XmlSerializer C# est
    sensible a l'ORDRE des elements d'une sequence, et on ne connait pas
    l'ordre attendu. Les 4 cartes reelles portent GpId/Begrp/BeIngrp sur 100 %
    de leurs elements — un manque signale un fichier hors dialecte, pas un cas
    a rattraper en devinant.
    """
    cible = element.find(balise)
    if cible is None:
        return False
    cible.text = str(valeur)
    return True


def _poser_groupe(element, gid, balise_drapeau):
    """@brief Pose GpId + son drapeau compagnon sur un element du fichier."""
    ok = _ecrire(element, "GpId", gid)
    _ecrire(element, balise_drapeau, "true" if gid else "false")
    return ok


def ecrire_groupes(source, composants, resultats=None) -> str:
    """@brief Renvoie le XML d'origine, enrichi des groupes d'analyse.

    @param source SourceXML publiee par lire_xml (arbre + pont ref->element).
    @param composants Composants analyses (le retour de lire_xml).
    @param resultats Sortie de detecteur.match_patterns, ou None (aucun groupe).
    @return str Document BoardSCH patche.
    """
    blocs = _grouper_par_circuit(composants, resultats) if resultats else []
    gid_par_ref = _ids_groupes_par_ref(blocs) if blocs else {}

    manquants = 0
    for ref, element in source.elements.items():
        if not _poser_groupe(element, gid_par_ref.get(ref, 0), "Begrp"):
            manquants += 1
    if manquants:
        _log.warning("%d element(s) sans balise GpId : groupe non ecrit "
                     "(fichier hors dialecte BoardSCH connu)", manquants)

    racine = source.arbre.getroot()
    return ET.tostring(racine, encoding="unicode")
```

**Piège à ne pas rater :** `ecrire_groupes` doit poser `GpId = 0` sur les
composants **non groupés** aussi. Sans cela, deux analyses successives
laisseraient des groupes fantômes d'une passe précédente — l'arbre est mutable
et partagé.

- [ ] **Step 4 : vérifier le vert**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -q` → PASS

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/eretro_patch.py tests/test_eretro_patch.py
git commit -m "feat(interop): les groupes d'analyse s'ecrivent dans le fichier recu"
```

---

### Task 3 : Puces composées — le groupe va sur le boîtier

**Files:**
- Modify: `circuit_analyzer/eretro_patch.py`
- Test: `tests/test_eretro_patch.py`

**Interfaces:**
- Consomme : `ecrire_groupes` (Task 2), `SourceXML.elements` (Task 1) — où
  plusieurs refs internes (`U7.1`, `U7.2`, …) pointent sur **le même** `<CComp>`.
- Produit : rien de nouveau ; c'est la règle d'arbitrage interne
  `_groupe_majoritaire(gids) -> int`.

**Pourquoi une règle spéciale :** le pont fait pointer `U7.1` et `U7.2` sur le
même élément. Sans arbitrage, la boucle de la Task 2 écrit deux fois sur le même
`<CComp>` et **le dernier passage gagne**, silencieusement, dans un ordre de
dictionnaire. Un composé est un objet unique posé sur sa carte : son groupe doit
être décidé, pas subi.

- [ ] **Step 1 : écrire les tests qui échouent**

```python
def test_groupe_majoritaire_tranche_et_s_abstient_a_egalite():
    from circuit_analyzer.eretro_patch import _groupe_majoritaire
    assert _groupe_majoritaire([2, 2, 5]) == 2
    assert _groupe_majoritaire([2, 5]) == 0          # egalite -> abstention
    assert _groupe_majoritaire([0, 0, 3]) == 3       # les non-groupes ne votent pas
    assert _groupe_majoritaire([0, 0]) == 0
    assert _groupe_majoritaire([]) == 0


@pytest.mark.skipif(not os.path.isdir(_DOSSIER_REEL), reason="cartes reelles absentes")
def test_le_compose_est_groupe_sur_son_boitier_ses_entrailles_intactes():
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = os.path.join(_DOSSIER_REEL, "PowtranAlim20260809.xml")
    comps, res = _analyser(chemin)
    avant = ET.parse(chemin).getroot()
    apres = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    for cc_av, cc_ap in zip(avant.findall(".//CCmpntL/CComp"),
                            apres.findall(".//CCmpntL/CComp")):
        # Les items INTERNES ne bougent pas d'un iota, GpId compris.
        for di_av, di_ap in zip(cc_av.findall("DItemL/DataItem"),
                                cc_ap.findall("DItemL/DataItem")):
            assert (di_av.findtext("GpId") or "") == (di_ap.findtext("GpId") or "")
            assert (di_av.findtext("Begrp") or "") == (di_ap.findtext("Begrp") or "")
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -q`
Attendu : `ImportError: cannot import name '_groupe_majoritaire'`

- [ ] **Step 3 : implémenter** — dans `circuit_analyzer/eretro_patch.py`

```python
from collections import Counter


def _groupe_majoritaire(gids) -> int:
    """@brief Groupe d'une puce composee, a la majorite de ses composants internes.

    Les gids nuls (composants non classes) ne votent pas. A EGALITE, on
    s'abstient : mieux vaut une puce non groupee qu'une puce rattachee au
    hasard de l'ordre d'un dictionnaire.
    """
    votes = Counter(g for g in gids if g)
    if not votes:
        return 0
    (gagnant, n), *reste = votes.most_common()
    if reste and reste[0][1] == n:
        return 0
    return gagnant
```

Puis remplacer la boucle d'écriture de la Task 2 par une version qui **agrège
d'abord, écrit ensuite** — un élément n'est écrit qu'une seule fois :

```python
    votes_par_element = {}
    for ref, element in source.elements.items():
        # `element` EST la cle : ET.Element se hache par identite, donc deux
        # refs internes d'un meme composé (U7.1, U7.2) tombent dans la meme
        # entree. Surtout pas `id()` : le depot proscrit ce motif, et il est
        # ici inutile puisque le dict garde l'objet en vie.
        votes_par_element.setdefault(element, []).append(gid_par_ref.get(ref, 0))

    manquants = 0
    for element, gids in votes_par_element.items():
        gid = gids[0] if len(gids) == 1 else _groupe_majoritaire(gids)
        if not _poser_groupe(element, gid, "Begrp"):
            manquants += 1
```

- [ ] **Step 4 : vérifier le vert**

```bash
PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -q
```

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/eretro_patch.py tests/test_eretro_patch.py
git commit -m "feat(interop): une puce composee se groupe sur son boitier, jamais sur ses entrailles"
```

---

### Task 4 : Les fils suivent leur groupe

**Files:**
- Modify: `circuit_analyzer/eretro_patch.py`
- Test: `tests/test_eretro_patch.py`

**Interfaces:**
- Consomme : `SourceXML.lignes` et `SourceXML.lignes_refs` (Task 1),
  `gid_par_ref` (Task 2).
- Produit : rien de nouveau ; extension de `ecrire_groupes`.

**Règle :** un fil ne prend un `GpId` que si ses **deux** extrémités tombent dans
le même groupe. Un fil qui traverse deux montages n'appartient à aucun des deux —
le grouper à moitié n'aurait aucun sens à l'écran chez lui. Le drapeau compagnon
d'un `<Line>` s'appelle **`BeIngrp`** (vérifié sur les 4 cartes).

- [ ] **Step 1 : écrire les tests qui échouent**

```python
def test_un_fil_intra_groupe_prend_le_groupe(tmp_path):
    from circuit_analyzer.eretro_patch import ecrire_groupes
    comps, res = _analyser(_fichier_synthetique(tmp_path))
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    items = racine.findall(".//CmpntL/DataItem")
    lignes = racine.findall(".//lineL/Line")
    assert items and lignes  # garde-fou : le fichier synthetique est non vide
    # Des lors qu'un groupe existe, au moins un fil doit le porter.
    if {int(d.findtext("GpId") or 0) for d in items} != {0}:
        assert any(int(l.findtext("GpId") or 0) for l in lignes)


def test_un_fil_entre_deux_groupes_reste_a_zero(tmp_path):
    """Un fil dont les deux bouts n'ont pas le meme groupe n'est jamais groupe."""
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    src = comps.source
    from circuit_analyzer.xml import _grouper_par_circuit, _ids_groupes_par_ref
    gid = _ids_groupes_par_ref(_grouper_par_circuit(comps, res)) if res else {}
    racine = ET.fromstring(ecrire_groupes(src, comps, res))
    lignes = racine.findall(".//lineL/Line")
    for idx, (ra, rb) in src.lignes_refs.items():
        ga, gb = gid.get(ra, 0), gid.get(rb, 0)
        attendu = ga if (ga and ga == gb) else 0
        assert int(lignes[idx].findtext("GpId") or 0) == attendu


def test_beingrp_suit_le_gpid_du_fil(tmp_path):
    from circuit_analyzer.eretro_patch import ecrire_groupes
    chemin = _fichier_synthetique(tmp_path)
    comps, res = _analyser(chemin)
    racine = ET.fromstring(ecrire_groupes(comps.source, comps, res))
    for l in racine.findall(".//lineL/Line"):
        attendu = "true" if int(l.findtext("GpId") or 0) else "false"
        assert (l.findtext("BeIngrp") or "").strip() == attendu
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -q`
Attendu : échec sur `BeIngrp`/`GpId` de fil restés à leur valeur d'origine.

- [ ] **Step 3 : implémenter** — dans `ecrire_groupes`, avant le `return`

```python
    for idx, ligne in enumerate(source.lignes):
        ra, rb = source.lignes_refs.get(idx, (None, None))
        ga, gb = gid_par_ref.get(ra, 0), gid_par_ref.get(rb, 0)
        # Un fil qui traverse deux montages n'appartient a aucun des deux.
        _poser_groupe(ligne, ga if (ga and ga == gb) else 0, "BeIngrp")
```

- [ ] **Step 4 : vérifier le vert**

```bash
PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -q
```

- [ ] **Step 5 : commit**

```bash
git add circuit_analyzer/eretro_patch.py tests/test_eretro_patch.py
git commit -m "feat(interop): un fil interne a un montage porte son groupe"
```

---

### Task 5 : Brancher l'onglet Analyse, avec repli annoncé

**Files:**
- Modify: `gui/tab_analyze.py:373-398` (`_export_xml`)
- Test: `tests/test_eretro_patch.py`

**Interfaces:**
- Consomme : `ecrire_groupes` (Tasks 2-4), `ListeComposantsXML.source` (Task 1).
- Produit : `_texte_export_analyse(comps, resultats) -> tuple[str, bool]` —
  fonction **libre de Tk**, donc testable sans display : renvoie
  `(xml, fidele)`. `fidele=False` signale le repli sur `generer_xml`.

**Pourquoi extraire la fonction :** `_export_xml` mêle boîtes de dialogue et
logique. Le choix « patcher ou régénérer » est la décision métier du chantier :
elle doit être testée sans ouvrir de fenêtre.

- [ ] **Step 1 : écrire les tests qui échouent**

```python
def test_export_analyse_est_fidele_quand_la_source_existe(tmp_path):
    from gui.tab_analyze import _texte_export_analyse
    comps, res = _analyser(_fichier_synthetique(tmp_path))
    xml, fidele = _texte_export_analyse(comps, res)
    assert fidele is True
    assert ET.fromstring(xml).findall(".//CmpntL/DataItem")


def test_export_analyse_replie_sur_le_generateur_sans_source():
    from gui.tab_analyze import _texte_export_analyse
    comps = [Composant("R1", "R", {"1": "IN", "2": "GND"}, "1k")]
    xml, fidele = _texte_export_analyse(comps, None)
    assert fidele is False
    assert ET.fromstring(xml).findall(".//CmpntL/DataItem")
```

- [ ] **Step 2 : vérifier l'échec**

Run : `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -q`
Attendu : `ImportError: cannot import name '_texte_export_analyse'`

- [ ] **Step 3 : implémenter** — `gui/tab_analyze.py`

Au niveau module (hors de la classe), après les imports :

```python
def _texte_export_analyse(comps, resultats):
    """@brief XML a exporter depuis l'onglet Analyse.

    @return tuple (xml, fidele). fidele=True : la carte RECUE est renvoyee
    telle quelle, enrichie des groupes. fidele=False : elle a ete REGENEREE
    (positions, formes et zooms inventes) faute de fichier source — cas d'une
    analyse partie d'un .net.
    """
    source = getattr(comps, "source", None)
    if source is not None:
        from circuit_analyzer.eretro_patch import ecrire_groupes
        return ecrire_groupes(source, comps, resultats), True
    from circuit_analyzer.xml import generer_xml
    return generer_xml(comps, results=resultats), False
```

Puis dans `_export_xml`, remplacer les lignes 389-395 par :

```python
            xml, fidele = _texte_export_analyse(self._comps, self._results)
            with open(path, "w", encoding="utf-8") as f:
                f.write(xml)
            if fidele:
                messagebox.showinfo("Succès ✓",
                    f"Schéma XML exporté :\n{path}\n\n"
                    "Carte d'origine conservée (positions, symboles, angles) "
                    "avec les groupes d'analyse ajoutés.")
            else:
                messagebox.showwarning("Exporté, mais REGÉNÉRÉ",
                    f"Schéma XML exporté :\n{path}\n\n"
                    "Aucun fichier XML source : le schéma a été REDESSINÉ sur "
                    "une grille. Positions, symboles et zooms sont inventés.\n\n"
                    "Pour un retour fidèle, partez d'un .xml ERetroDesign.")
```

Le repli **ne doit jamais être silencieux** : c'est exactement le défaut que ce
chantier corrige.

- [ ] **Step 4 : vérifier le vert**

```bash
PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py tests/test_tab_analyze.py -q
```
(Si `tests/test_tab_analyze.py` n'existe pas, se limiter au premier fichier.)

- [ ] **Step 5 : commit**

```bash
git add gui/tab_analyze.py tests/test_eretro_patch.py
git commit -m "feat(interop): l'onglet Analyse renvoie la carte recue, le repli est annonce"
```

---

### Task 6 : Preuve sur les 4 vraies cartes

**Files:**
- Create: `tests/test_retour_fidele_cartes.py`

**Interfaces:**
- Consomme : tout ce qui précède.
- Produit : rien de code ; c'est le filet de sécurité du chantier.

- [ ] **Step 1 : écrire les tests** — `tests/test_retour_fidele_cartes.py`

```python
"""@file test_retour_fidele_cartes.py
@brief Le fichier d'un collegue revient intact, aux groupes pres (4 vraies cartes).
"""
import os
import xml.etree.ElementTree as ET

import pytest

from circuit_analyzer.xml import lire_xml
from circuit_analyzer.eretro_patch import ecrire_groupes
from tests.test_eretro_patch import _comparer_sauf_groupes

_DOSSIER = "CARTE POUR TESTER (VRAI TEST)"
_FICHIERS = ["PG 2.xml", "PG 3.xml", "PowtranAlim20260809.xml", "pg carte.xml"]

pytestmark = pytest.mark.skipif(
    not os.path.isdir(_DOSSIER), reason="cartes reelles absentes")


def _patcher(fichier):
    from circuit_analyzer.graph_builder import build_graph
    from circuit_analyzer.matcher import match_patterns
    chemin = os.path.join(_DOSSIER, fichier)
    comps = lire_xml(chemin)
    res = match_patterns(build_graph(comps))
    return chemin, comps, ecrire_groupes(comps.source, comps, res)


@pytest.mark.parametrize("fichier", _FICHIERS)
def test_invariance_hors_groupes(fichier):
    chemin, _comps, xml = _patcher(fichier)
    _comparer_sauf_groupes(ET.parse(chemin).getroot(), ET.fromstring(xml))


@pytest.mark.parametrize("fichier", _FICHIERS)
def test_positions_angles_et_zooms_mot_pour_mot(fichier):
    """Garde-fou EXPLICITE sur les champs que l'ancien export detruisait."""
    chemin, _comps, xml = _patcher(fichier)
    avant, apres = ET.parse(chemin).getroot(), ET.fromstring(xml)
    for tag in ("DataItem", "CComp"):
        for a, b in zip(avant.iter(tag), apres.iter(tag)):
            for champ in ("angle", "zmH", "zmV", "Flip", "typ", "Name", "value"):
                assert (a.findtext(champ) or "") == (b.findtext(champ) or ""), \
                    f"{fichier} : {tag}/{champ} modifie"
            for boite in ("CtrIem", "TL", "BR"):
                ea, eb = a.find(boite), b.find(boite)
                if ea is not None:
                    assert [(c.tag, c.text) for c in ea] == \
                           [(c.tag, c.text) for c in eb], \
                        f"{fichier} : {tag}/{boite} modifie"


@pytest.mark.parametrize("fichier", _FICHIERS)
def test_netlist_stable_apres_patch(fichier, tmp_path):
    """Un NodeL casse changerait la connexite : ce test le verrait."""
    chemin, comps, xml = _patcher(fichier)
    p = os.path.join(str(tmp_path), "patche.xml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(xml)
    relu = lire_xml(p)
    assert [(c.ref, c.type, c.value) for c in relu] == \
           [(c.ref, c.type, c.value) for c in comps]
    assert [c.pins for c in relu] == [c.pins for c in comps]


@pytest.mark.parametrize("fichier", _FICHIERS)
def test_le_patch_est_idempotent(fichier, tmp_path):
    """Deux passes donnent le meme fichier : pas de groupe fantome accumule."""
    from circuit_analyzer.graph_builder import build_graph
    from circuit_analyzer.matcher import match_patterns
    _chemin, _comps, xml1 = _patcher(fichier)
    p = os.path.join(str(tmp_path), "p1.xml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(xml1)
    c2 = lire_xml(p)
    xml2 = ecrire_groupes(c2.source, c2, match_patterns(build_graph(c2)))
    _comparer_sauf_groupes(ET.fromstring(xml1), ET.fromstring(xml2))
    for a, b in zip(ET.fromstring(xml1).iter("GpId"), ET.fromstring(xml2).iter("GpId")):
        assert (a.text or "") == (b.text or "")
```

- [ ] **Step 2 : lancer**

```bash
PYTHONUTF8=1 python -m pytest tests/test_retour_fidele_cartes.py -q
```
Attendu : PASS. **Un échec ici est un vrai défaut, jamais un test à assouplir** —
si un champ diffère, c'est que le patch écrit quelque part où il ne doit pas.

- [ ] **Step 3 : suite complète**

```bash
PYTHONUTF8=1 python -m pytest -q
```
Attendu : ~2048 passed + les nouveaux, **0 failed**.

- [ ] **Step 4 : commit**

```bash
git add tests/test_retour_fidele_cartes.py
git commit -m "test(interop): les 4 cartes reelles reviennent intactes aux groupes pres"
```

---

### Task 7 : Preuve par le vrai code C#

Les tests précédents prouvent que **notre** lecteur relit ce que **notre**
patcheur écrit. Seul son C# prouve qu'il l'accepte.

**Files:** aucun fichier du dépôt (harnais **hors dépôt**, dans le scratchpad).

- [ ] **Step 1 : monter le harnais** — dans le scratchpad de session (jamais
  dans le dépôt), un projet net472 référençant l'assembly du dossier
  `ERetroDesign/` (lecture seule). Localiser d'abord le `.exe`/`.dll` construit :

```bash
ls ERetroDesign/ERetroDesign/bin/*/*.exe ERetroDesign/ERetroDesign/bin/*/*.dll 2>/dev/null
```

  Programme de contrôle (`Program.cs`) — il utilise **son** `XmlSerializer`,
  c'est tout l'intérêt : si son désérialiseur accepte le fichier, la question
  est réglée.

```csharp
using System;
using System.IO;
using System.Xml.Serialization;

class Sonde {
    static int Main(string[] a) {
        var s = new XmlSerializer(typeof(ERetroDesign.BoardSCH));
        using (var r = new StreamReader(a[0])) {
            var b = (ERetroDesign.BoardSCH)s.Deserialize(r);
            Console.WriteLine("composants=" + b.CmpntL.Count
                            + " fils=" + b.lineL.Count);
            foreach (var d in b.CmpntL) Console.WriteLine("  " + d.Name + " GpId=" + d.GpId);
            return 0;
        }
    }
}
```

  Si le type ne s'appelle pas `BoardSCH` ou si les champs diffèrent, **lire le
  C# du dépôt** (`ERetroDesign/`) plutôt que deviner : c'est la source de vérité
  du format.

- [ ] **Step 2 : lui faire avaler un fichier patché**

```bash
PYTHONUTF8=1 python -c "
from circuit_analyzer.xml import lire_xml
from circuit_analyzer.graph_builder import build_graph
from circuit_analyzer.matcher import match_patterns
from circuit_analyzer.eretro_patch import ecrire_groupes
c = lire_xml('CARTE POUR TESTER (VRAI TEST)/pg carte.xml')
open('<scratchpad>/patche.xml','w',encoding='utf-8').write(
    ecrire_groupes(c.source, c, match_patterns(build_graph(c))))
"
dotnet run --project <scratchpad>/cstest -- "<scratchpad>/patche.xml"
```

  Attendu : désérialisation **sans exception**, `composants=` et `fils=` égaux
  aux compteurs du fichier d'origine (79 et 72 pour `pg carte.xml`), et des
  `GpId` non nuls visibles. Passer aussi le fichier **non patché** pour disposer
  du point de comparaison.

- [ ] **Step 3 : trancher la réserve `<GrpL>`** — si les groupes ne sont pas
  exploitables côté C# sans `<GrpL>`, **ne pas improviser** : consigner ce que le
  C# attend exactement (ordre des éléments, contenu de `GRect`) et revenir au
  boss avec le constat. `<GrpL>` s'insère **après `<CCmpntL>`, avant `<zoom>`** —
  `XmlSerializer` est sensible à l'ordre des éléments de séquence.

- [ ] **Step 4 : ouverture à la main dans son application** (le boss, ou le
  collègue) sur une carte patchée. C'est la validation n°4 de la spec ; le
  chantier n'est pas fini sans elle.

- [ ] **Step 5 : revue et clôture** — `superpowers:requesting-code-review` sur la
  branche, puis `superpowers:finishing-a-development-branch`. **Rien n'est poussé
  sans accord explicite du boss.**

---

## Vérification (bout en bout)

1. **Tests** : `PYTHONUTF8=1 python -m pytest -q` — tout vert, dont
   `tests/test_eretro_patch.py` et `tests/test_retour_fidele_cartes.py`
   (nouveaux), **sans modifier aucune assertion existante**.
2. **Non-régression greppable** : `git diff master -- circuit_analyzer/xml.py`
   ne doit toucher **aucune ligne** de `generer_xml` ni de `_Generateur`.
3. **À la main dans l'app** : onglet Analyse → ouvrir `pg carte.xml` → analyser →
   « Exporter » → message « Carte d'origine conservée » (pas l'avertissement) →
   ouvrir le fichier produit dans ERetroDesign : carte reconnaissable.
4. **Repli visible** : refaire l'opération depuis un `.net` → l'avertissement
   « REGÉNÉRÉ » doit s'afficher.

## Réserves connues

- **`<GrpL>` non écrit en v1** (§Réserve de la spec). Tranché par la Task 7.
- **Chantier B non couvert** : l'onglet Dessin exporte toujours via
  `generer_xml`, donc invente positions et zooms. C'est conforme à la spec —
  l'éditeur fidèle est un chantier séparé.
- **`zmH`/`zmV` non uniformes** (un composant réel à `0,55 / 0,50`) : préservés
  ici puisqu'on ne les écrit pas, mais ils resteront un point dur du chantier B.
