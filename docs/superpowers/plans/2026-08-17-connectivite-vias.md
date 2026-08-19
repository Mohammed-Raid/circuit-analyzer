# Connectivité des vias — Implementation Plan

**Goal:** Un via qui touche plusieurs fils (coïncidence géométrique exacte
entre `<Via><Pos>` et le premier/dernier point `<LP><PointF>` d'un fil dont
le bout correspondant est non résolu) fusionne ces fils dans le même net
électrique, comme le fait déjà une jonction fil-sur-fil (marque `999999`).

**Architecture:** Extension de l'Union-Find existant dans
`circuit_analyzer/xml.py::lire_xml` — nœud synthétique `('via', idx)` traité
exactement comme une clé `(cid, pidx)` par `unir()`/`trouver()`. Aucune
nouvelle structure, aucun nouveau fichier.

**Tech Stack:** Python, `xml.etree.ElementTree`, pytest.

## Global Constraints

- Aucun `Co-Authored-By: Claude` ni footer « Generated with Claude Code »
  dans les commits ; jamais `git add -A`.
- `SolutionERetroDesignX20260813/` et `CARTE POUR TESTER (VRAI TEST)/` en
  LECTURE SEULE.
- Ne PAS fusionner deux vias par simple égalité de `<Net>` (voir design —
  ce n'est pas le contrat C#, seule la position géométrique compte).
- Ne PAS toucher `eretro_patch.py` (le round-trip C#→Python→C# n'a besoin
  d'aucun changement, `<Vias>` traverse déjà intact).
- Toute modif de connexité → au moins un schéma de bout en bout re-rendu et
  regardé (PNG jamais committé), pas seulement des tests verts.

---

### Task 1 : Fusion par via dans `lire_xml`

**Files:**
- Modify: `circuit_analyzer/xml.py` (`lire_xml`)
- Test: `tests/test_eretro_nouveau_format.py`

**Interfaces:**
- Consumes : `<Vias>/<Via>/<Pos>/<X|Y>`, `<lineL>/<Line>/<LP>/<PointF>`.
- Produces : rien de nouveau en sortie — les broches déjà unies par le via
  se retrouvent simplement dans le même `groupes_nets`.

- [ ] **Step 1 : Étendre les fixtures pour porter `<LP>`**

Le générateur compact `_fil(idx, cf, cl)` dans `test_eretro_nouveau_format.py`
n'émet aujourd'hui aucune géométrie. Ajouter un paramètre optionnel `lp`
(liste de `(x, y)`) qui émet `<LP>{points}</LP>` quand fourni, vide sinon
(non-régressif : les cas existants n'en ont pas besoin, ne changent pas).

- [ ] **Step 2 : Écrire les tests qui échouent**

Ajouter à `CAS` (même patron que `03_jonction` / `09_jonction_chaine`) :

```python
"10_via_simple": (
    _carte(
        items=[_res("R1", "10k", 0), _res("R2", "22k", 1)],
        fils=[_fil(0, "0_1_0_0", "", lp=[(0, 0), (50, 0)]),
              _fil(1, "", "1_0_0_0", lp=[(50, 0), (100, 0)])],
        vias=[(50, "N1")]),
    [[(0, "2"), (1, "1")]]),

"11_via_chaine": (
    _carte(
        items=[_res(f"R{i+1}", "10k", i) for i in range(3)],
        fils=[_fil(0, "0_1_0_0", "", lp=[(0, 0), (50, 0)]),
              _fil(1, "1_0_0_0", "", lp=[(0, 0), (50, 0)]),
              _fil(2, "", "2_0_0_0", lp=[(50, 0), (100, 0)])],
        vias=[(50, "N1")]),
    [[(0, "2"), (1, "1"), (2, "1")]]),

# Garde-fou : même <Net> mais AUCUN fil ne relie les deux vias -> pas de
# fusion entre eux (non-régression du non-goal "pas par <Net>").
"12_deux_vias_meme_net_sans_fil": (
    _carte(items=[_res("R1", "10k", 0), _res("R2", "22k", 1)],
           vias=[(20, "N1"), (280, "N1")]),
    []),
```

(`05_via` reste inchangé et doit continuer à rendre `[]`.)

- [ ] **Step 3 : Lancer, vérifier l'échec**

Run (depuis `test3`, venv du projet) :
`.buildvenv\Scripts\python.exe -m pytest tests/test_eretro_nouveau_format.py -q`
Expected : FAIL sur `10_via_simple` / `11_via_chaine` (pas encore fusionnés),
PASS déjà sur `12_deux_vias_meme_net_sans_fil` (comportement actuel correct
par accident — sert de garde-fou).

- [ ] **Step 4 : Implémenter dans `lire_xml`**

Juste avant la boucle `for idx_fil, fil in enumerate(lignes_xml)` :

```python
vias_index: dict[tuple, int] = {}
for vidx, via in enumerate(racine.findall('.//Vias/Via')):
    x = via.findtext('Pos/X')
    y = via.findtext('Pos/Y')
    try:
        vias_index[(round(float(x)), round(float(y)))] = vidx
    except (TypeError, ValueError):
        continue

def via_au_bout(fil, premier: bool):
    """@brief Nœud synthétique ('via', idx) si ce bout de fil touche
    exactement un via, None sinon."""
    if not vias_index:
        return None
    points = fil.findall('LP/PointF')
    if not points:
        return None
    p = points[0] if premier else points[-1]
    x, y = p.findtext('X'), p.findtext('Y')
    try:
        cle = (round(float(x)), round(float(y)))
    except (TypeError, ValueError):
        return None
    vidx = vias_index.get(cle)
    return ('via', vidx) if vidx is not None else None
```

Dans la boucle des fils, seulement quand le bout brut est vide (jamais une
référence mal formée — celle-ci reste un vrai avertissement) :

```python
bf = resoudre_extremite(cf, autoriser_packe=True)
if bf is None and not cf:
    bf = via_au_bout(fil, premier=True)
bl = resoudre_extremite(cl, autoriser_packe=True)
if bl is None and not cl:
    bl = via_au_bout(fil, premier=False)
```

Le reste de la boucle (`unir`, `ligne_vers_broche`, avertissement) est
INCHANGÉ — il consomme déjà `bf`/`bl` génériquement.

- [ ] **Step 5 : Lancer, vérifier le succès**

Même commande qu'à l'étape 3. Tous les cas `CAS` doivent passer, y compris
les 3 nouveaux et `05_via` (inchangé).

- [ ] **Step 6 : Suite complète**

`.buildvenv\Scripts\python.exe -m pytest tests/ -q` — zéro régression.

---

### Task 2 : Boucle visuelle + oracle réel

**Files:**
- Script jetable (jamais committé) dans un dossier scratch, PAS dans
  `test3/` — utilise `circuit_analyzer.xml.lire_xml` + `rapport.py` +
  détecteurs.
- Test (si des vias existent réellement) : oracle `CARTE POUR TESTER (VRAI
  TEST)/`, lecture seule, `skipif` si absent.

- [ ] **Step 1** : construire un petit schéma « filtre RC coupé par un via »
  (R en entrée, via au milieu, C vers GND de l'autre côté) via le même
  générateur `_carte`/`_fil`/`_pin`, ou directement un fichier `.xml`
  BoardSCH complet, à la main.
- [ ] **Step 2** : lancer `lire_xml` + `detecteur.analyser` dessus ; avant
  ce chantier, « Filtre RC passe-bas » n'est PAS détecté (nets coupés) ;
  après, il doit l'être.
- [ ] **Step 3** : rendre le résultat (pipeline `rapport.py`/`circuit_viewer.py`
  existant) en PNG, l'ouvrir et l'inspecter visuellement (pas seulement lire
  le rapport texte) — confirmer qu'aucune anomalie de dessin n'apparaît
  autour du point de fusion. Supprimer le PNG ensuite (jamais committé).
- [ ] **Step 4** : si des vias existent dans un fichier réel de `CARTE POUR
  TESTER (VRAI TEST)/`, vérifier qu'il se lit toujours sans erreur et sans
  régression du nombre d'inconnus.

---

## Fin de chantier

- [ ] Mettre à jour le `Statut` de la spec (`approuvé` → `livré`).
- [ ] Commit FR, sans footer Claude, sans `git add -A` (lister les fichiers
  explicitement : `xml.py`, `test_eretro_nouveau_format.py`, les deux docs
  `specs`/`plans`).
