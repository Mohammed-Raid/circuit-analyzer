# Disposition canonique — rôles multi-composants série/parallèle/fan-in — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer la disposition « toujours en rangée » d'un rôle
multi-composants (Zin/Z1/Zf/Z3/Zg) par un empilement vertical quand ce
rôle est réellement parallèle (composition `'//'` pure) ou fan-in (une
liste de blocs indépendants, ex. le Sommateur) — et retirer le besoin du
correctif « saute-colonne-2 » pour ces cas, sans rien changer pour les
rôles qui restent en série (comportement byte-identique).

**Architecture:** Une nouvelle fonction pure `_roles_a_empiler` lit
`impedances` (déjà calculé par le détecteur) et décide, par rôle, s'il
faut empiler. `_Bloc` porte ce résultat (`roles_empiles`). Les deux
positionneurs canoniques (`_positionner_amplificateur_inverseur`,
`_positionner_amplificateur_differentiel`) calculent la hauteur de
chaque « bande » verticale (1 ligne, ou N si empilée) et placent les
bandes suivantes en cascade — au lieu de décalages verticaux fixes. Le
routage de fils déjà en place (`_router_fil_en_l`) n'a besoin d'aucune
modification : il route automatiquement vers les nouvelles positions.

**Tech Stack:** Python, `circuit_analyzer/xml.py`,
`circuit_analyzer/eretro_patch.py`, pytest, matplotlib (rendu visuel de
vérification).

## Global Constraints

- Angle toujours 0 — jamais de rotation (règle déjà en place, ne change
  pas dans ce chantier).
- `roles_empiles` vide (cas par défaut) DOIT produire un résultat
  BYTE-IDENTIQUE à avant ce chantier, pour les deux positionneurs — c'est
  la garantie de non-régression centrale de ce plan, vérifiée
  explicitement dans chaque tâche qui touche un positionneur.
- Aucune modification de `_roles_du_bloc`, `_refs_du_role`,
  `_deltas_disposition_canonique` (au-delà du fil de connexion
  `roles_empiles`), `_appliquer_deltas`, `_router_fil_en_l` — le routage
  de fils déjà en place gère automatiquement les nouvelles positions,
  aucun changement nécessaire là.
- `_PAS_X_BLOC = 260`, `_PAS_Y_BLOC = 190` — réutiliser telles quelles.
- Ne jamais committer avec un trailer `Co-Authored-By: Claude`.

---

### Task 1 : `_roles_a_empiler`

**Files:**
- Modify: `circuit_analyzer/xml.py` (nouvelle fonction, juste après
  `_roles_du_bloc`/`_refs_du_role`)
- Test: `tests/test_xml_generator.py`

**Interfaces:**
- Consomme : rien de nouveau (lit `r['impedances']`, déjà présent sur
  chaque match du détecteur).
- Produit : `_roles_a_empiler(r) -> frozenset[str]`. Consommé par Task 4
  (câblage dans `_grouper_par_circuit`).

- [ ] **Step 1: Écrire les tests (doivent échouer)**

Ajouter dans `tests/test_xml_generator.py`, dans une nouvelle section
juste avant `# ── Positionneur canonique : amplificateur inverseur ──` :

```python
# ── Detection des roles a empiler (serie/parallele/fan-in) ──────────────────

from circuit_analyzer.xml import _roles_a_empiler


def test_roles_a_empiler_liste_toujours_empilee():
    """@brief Un role dont la valeur brute est une LISTE (fan-in, ex. Zin
    du Sommateur) est toujours empile, quel que soit le nombre d'items."""
    r = {'impedances': {'Zin': [{'refs': ['R1']}, {'refs': ['R2']}],
                         'Zf': {'refs': ['Rf']}}}
    assert _roles_a_empiler(r) == frozenset({'Zin'})


def test_roles_a_empiler_parallele_pur():
    """@brief Un bloc unique a 2+ refs avec composition parallele pure
    ('//' present, '+' absent) est empile."""
    r = {'impedances': {'Zf': {'refs': ['C1', 'R6'], 'composition': '(C1//R6)'}}}
    assert _roles_a_empiler(r) == frozenset({'Zf'})


def test_roles_a_empiler_serie_pure_non_empilee():
    """@brief Une composition serie pure ('+', pas de '//') reste en rangee."""
    r = {'impedances': {'Zf': {'refs': ['R2', 'R3'], 'composition': 'R2+R3'}}}
    assert _roles_a_empiler(r) == frozenset()


def test_roles_a_empiler_composition_mixte_non_empilee():
    """@brief Une composition mixte ('+' ET '//', ex. R1+(R2//C1)) reste en
    rangee -- repli sur le comportement existant, sur, pas de risque
    d'empiler un cas imbrique mal compris."""
    r = {'impedances': {'Zin': {'refs': ['R1', 'R2', 'C1'],
                                'composition': 'R1+(R2//C1)'}}}
    assert _roles_a_empiler(r) == frozenset()


def test_roles_a_empiler_une_seule_ref_jamais_empilee():
    """@brief Un role a 1 seule ref n'a rien a empiler, meme si sa
    composition contenait '//' par erreur."""
    r = {'impedances': {'Zf': {'refs': ['R1'], 'composition': 'R1'}}}
    assert _roles_a_empiler(r) == frozenset()


def test_roles_a_empiler_sans_impedances():
    """@brief Match sans 'impedances' (Divers, ou motif pas encore migre)
    -> frozenset vide, jamais d'exception."""
    assert _roles_a_empiler({}) == frozenset()
    assert _roles_a_empiler({'impedances': None}) == frozenset()
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k roles_a_empiler -v`
Expected: FAIL — `ImportError: cannot import name '_roles_a_empiler'`

- [ ] **Step 3: Écrire l'implémentation**

Dans `circuit_analyzer/xml.py`, juste après la fonction `_refs_du_role`
(qui suit `_roles_du_bloc`) :

```python
def _roles_a_empiler(r) -> frozenset:
    """@brief Noms de role dont la valeur brute doit etre empilee verticalement.

    @param r Match d'un circuit detecte (sortie de detecteur.py).
    @return frozenset des noms de role : soit une LISTE de blocs dans
            r['impedances'] (fan-in, ex. Zin du Sommateur -- plusieurs
            entrees independantes), soit un bloc unique a 2+ refs dont la
            composition est un parallele PUR ('//' present, '+' absent,
            ex. '(C1//R6)' -- un integrateur reel avec resistance de
            fuite). Une composition serie ('+') ou mixte ('R1+(R2//C1)')
            reste en rangee (repli sur le comportement existant, jamais
            d'empilement pour un cas imbrique mal compris). Un role a 1
            seule ref n'a jamais rien a empiler.
    """
    impedances = r.get('impedances')
    if not impedances:
        return frozenset()
    empiles = set()
    for nom, valeur in impedances.items():
        if isinstance(valeur, list):
            empiles.add(nom)
            continue
        if not isinstance(valeur, dict):
            continue
        refs = valeur.get('refs', [])
        if len(refs) < 2:
            continue
        composition = valeur.get('composition', '') or ''
        if '//' in composition and '+' not in composition:
            empiles.add(nom)
    return frozenset(empiles)
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k roles_a_empiler -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/xml.py tests/test_xml_generator.py
git commit -m "feat(disposition): _roles_a_empiler detecte les roles serie/parallele/fan-in"
```

---

### Task 2 : `_positionner_amplificateur_inverseur` — bandes verticales

**Files:**
- Modify: `circuit_analyzer/xml.py`
- Test: `tests/test_xml_generator.py`

**Interfaces:**
- Consomme : `_PAS_X_BLOC`, `_PAS_Y_BLOC`, `_positionner_grille_compacte`
  (inchangées).
- Produit : `_positionner_amplificateur_inverseur(comps, roles, x, y,
  roles_empiles=frozenset()) -> dict` — signature étendue (5e paramètre,
  valeur par défaut vide pour rétrocompatibilité). Consommé par Task 4.

- [ ] **Step 1: Écrire les tests (doivent échouer)**

Ajouter dans `tests/test_xml_generator.py`, juste après
`test_positionner_amplificateur_inverseur_zin_a_trois_entrees_evite_laop` :

```python
def test_positionner_amplificateur_inverseur_roles_empiles_vide_est_byte_identique():
    """@brief Garantie centrale de ce chantier : roles_empiles vide (par
    defaut) produit EXACTEMENT le meme resultat qu'avant l'ajout de ce
    parametre -- non-regression explicite."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    roles = {"aop": ["U1"], "Zin": ["R1"], "Zf": ["R2"]}
    avec_defaut = _positionner_amplificateur_inverseur(comps, roles, 100, 200)
    avec_vide = _positionner_amplificateur_inverseur(comps, roles, 100, 200, frozenset())
    assert avec_defaut == avec_vide
    x_aop, y_aop = 100 + 2 * _PAS_X_BLOC, 200 + _PAS_Y_BLOC
    assert avec_defaut["U1"] == (x_aop, y_aop, 0)
    assert avec_defaut["R1"] == (100, y_aop, 0)
    assert avec_defaut["R2"] == (x_aop, 200, 0)


def test_positionner_amplificateur_inverseur_zin_empile_meme_colonne_lignes_distinctes():
    """@brief Zin empile (fan-in, 3 entrees) : meme colonne x que le debut
    de la rangee d'aujourd'hui, 3 lignes y distinctes en descendant depuis
    la ligne de l'AOP (j=0 partage la ligne de l'AOP, comme le cas a 1
    seule entree)."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN1"}),
        Component("R2", "R", {"1": "NET_INV", "2": "NET_IN2"}),
        Component("R3", "R", {"1": "NET_INV", "2": "NET_IN3"}),
        Component("Rf", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    roles = {"aop": ["U1"], "Zin": ["R1", "R2", "R3"], "Zf": ["Rf"]}
    pos = _positionner_amplificateur_inverseur(comps, roles, 0, 0, frozenset({"Zin"}))
    assert pos["R1"] == (0, 190, 0)
    assert pos["R2"] == (0, 380, 0)
    assert pos["R3"] == (0, 570, 0)
    assert pos["U1"] == (520, 190, 0)          # AOP inchange (col 2, ligne 190)
    assert pos["R1"][0] == pos["R2"][0] == pos["R3"][0]   # meme colonne
    assert len({pos["R1"][1], pos["R2"][1], pos["R3"][1]}) == 3  # 3 lignes distinctes


def test_positionner_amplificateur_inverseur_zf_empile_cas_reel_c1_parallele_r6():
    """@brief Cas reel trouve sur test_pid_3.xml : Zf = C1//R6 (integrateur
    avec resistance de fuite). Empile verticalement au-dessus de l'AOP au
    lieu d'une rangee -- c'est ce qui corrige le fil en diagonale observe
    dans ERetroDesign."""
    comps = [
        Component("U2", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R5", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("C1", "C", {"1": "NET_INV", "2": "NET_OUT"}),
        Component("R6", "R", {"1": "NET_INV", "2": "NET_OUT"}),
    ]
    roles = {"aop": ["U2"], "Zin": ["R5"], "Zf": ["C1", "R6"]}
    pos = _positionner_amplificateur_inverseur(comps, roles, 0, 0, frozenset({"Zf"}))
    x_aop = 2 * _PAS_X_BLOC
    assert pos["C1"] == (x_aop, 0, 0)
    assert pos["R6"] == (x_aop, _PAS_Y_BLOC, 0)
    assert pos["U2"] == (x_aop, 2 * _PAS_Y_BLOC, 0)   # AOP sous les 2 lignes de Zf
    assert pos["R5"] == (0, 2 * _PAS_Y_BLOC, 0)        # Zin non empile, meme ligne que l'AOP


def test_positionner_amplificateur_inverseur_satellites_apres_bande_zin_empilee():
    """@brief Un satellite (composant hors roles) se place TOUJOURS sous la
    derniere bande utilisee -- meme quand cette bande est agrandie par un
    empilement, jamais de chevauchement."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN1"}),
        Component("R2", "R", {"1": "NET_INV", "2": "NET_IN2"}),
        Component("Rf", "R", {"1": "NET_OUT", "2": "NET_INV"}),
        Component("C9", "C", {"1": "NET_IN1", "2": "GND"}),
    ]
    roles = {"aop": ["U1"], "Zin": ["R1", "R2"], "Zf": ["Rf"]}
    pos = _positionner_amplificateur_inverseur(comps, roles, 0, 0, frozenset({"Zin"}))
    plus_bas = max(pos["R1"][1], pos["R2"][1], pos["U1"][1])
    assert pos["C9"][1] > plus_bas
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k "roles_empiles_vide_est_byte_identique or zin_empile_meme_colonne or zf_empile_cas_reel or satellites_apres_bande" -v`
Expected: FAIL — `TypeError: _positionner_amplificateur_inverseur() takes 4 positional arguments but 5 were given` (ou equivalent, le parametre n'existe pas encore)

- [ ] **Step 3: Réécrire l'implémentation**

Dans `circuit_analyzer/xml.py`, remplacer intégralement le corps de
`_positionner_amplificateur_inverseur` (garder la docstring existante,
juste étendre la liste `@param` avec `roles_empiles`) :

```python
def _positionner_amplificateur_inverseur(comps, roles, x: int, y: int,
                                          roles_empiles: frozenset = frozenset()) -> dict:
    """@brief Gabarit canonique de l'ampli inverseur.

    Zin en chaîne horizontale à gauche de l'AOP (alignée sur son entrée),
    AOP au centre, Zf en chaîne horizontale AU-DESSUS de l'AOP — c'est la
    POSITION (strictement au-dessus), pas une rotation, qui distingue le
    chemin de contre-réaction de la chaîne Zin. Angle toujours 0 : la
    rotation des broches de fil (_xml_fil) n'est pas fiable pour un symbole
    tourné dans ERetroDesign — confirmé : une Zf à angle=90 s'affichait mal
    (fils désalignés). Ne pas réintroduire de rotation sans corriger
    _xml_fil pour tenir compte de comp.angle.
    Tout composant du bloc absent de `roles` (satellite) est placé par la
    grille compacte existante, sous la disposition canonique — jamais perdu.

    Zin et Zf sont chacun soit une RANGÉE horizontale (comportement par
    défaut, roles_empiles vide) soit un EMPILEMENT vertical (colonne
    partagée, une ligne par ref) quand leur nom figure dans
    `roles_empiles` — cf. _roles_a_empiler pour la décision. La hauteur de
    la bande Zf détermine où commence la ligne de l'AOP/Zin ; la hauteur de
    la bande Zin détermine où commencent les satellites.

    @param comps Composants du bloc (Composant/Component).
    @param roles {'aop': [...], 'Zin': [...], 'Zf': [...]}.
    @param x, y Origine du bloc.
    @param roles_empiles Noms de rôle ('Zin' et/ou 'Zf') à empiler
           verticalement au lieu d'aligner en rangée — cf.
           _roles_a_empiler. Vide par défaut : comportement rangée
           identique à avant l'ajout de ce paramètre.
    @return dict {ref: (x, y, angle)} pour les rôles connus,
            {ref: (x, y)} pour les satellites.
    """
    pos = {}
    refs_du_bloc = {c.ref for c in comps}
    zf_refs = roles.get('Zf', [])
    zin_refs = roles.get('Zin', [])
    hauteur_zf = len(zf_refs) if 'Zf' in roles_empiles and zf_refs else 1
    hauteur_zin = max(1, len(zin_refs)) if 'Zin' in roles_empiles else 1

    y_zf = y
    y_aop = y + hauteur_zf * _PAS_Y_BLOC
    x_aop = x + 2 * _PAS_X_BLOC

    for ref in roles.get('aop', []):
        if ref in refs_du_bloc:
            pos[ref] = (x_aop, y_aop, 0)

    for j, ref in enumerate(zin_refs):
        if ref not in refs_du_bloc:
            continue
        if 'Zin' in roles_empiles:
            pos[ref] = (x, y_aop + j * _PAS_Y_BLOC, 0)
        else:
            col = j if j < 2 else j + 1
            pos[ref] = (x + col * _PAS_X_BLOC, y_aop, 0)

    for j, ref in enumerate(zf_refs):
        if ref not in refs_du_bloc:
            continue
        if 'Zf' in roles_empiles:
            pos[ref] = (x_aop, y_zf + j * _PAS_Y_BLOC, 0)
        else:
            pos[ref] = (x_aop + j * _PAS_X_BLOC, y_zf, 0)

    restants = [c for c in comps if c.ref not in pos]
    pos.update(_positionner_grille_compacte(
        restants, x, y_aop + hauteur_zin * _PAS_Y_BLOC))
    return pos
```

- [ ] **Step 4: Lancer TOUS les tests de ce positionneur, vérifier qu'ils passent**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k "amplificateur_inverseur" -v`
Expected: tous passent (les 5 tests existants + les 4 nouveaux) — en
particulier `test_positionner_amplificateur_inverseur_places_roles_canoniquement`,
`test_positionner_amplificateur_inverseur_garde_les_satellites`,
`test_positionner_amplificateur_inverseur_zin_composite_en_chaine`,
`test_positionner_amplificateur_inverseur_ignore_role_hors_bloc`,
`test_positionner_amplificateur_inverseur_zin_a_trois_entrees_evite_laop`
(écrits AVANT ce chantier, avec l'ancienne signature à 4 arguments — s'ils
échouent, la rétrocompatibilité par défaut de `roles_empiles` est cassée,
corriger avant de continuer).

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/xml.py tests/test_xml_generator.py
git commit -m "feat(disposition): _positionner_amplificateur_inverseur empile Zin/Zf en bandes"
```

---

### Task 3 : `_positionner_amplificateur_differentiel` — bandes verticales

**Files:**
- Modify: `circuit_analyzer/xml.py`
- Test: `tests/test_xml_generator.py`

**Interfaces:**
- Consomme : identique à Task 2.
- Produit : `_positionner_amplificateur_differentiel(comps, roles, x, y,
  roles_empiles=frozenset()) -> dict` — même extension de signature.
  Consommé par Task 4.

- [ ] **Step 1: Écrire les tests (doivent échouer)**

Ajouter dans `tests/test_xml_generator.py`, juste après
`test_positionner_amplificateur_differentiel_z1_a_trois_entrees_evite_laop` :

```python
def test_positionner_amplificateur_differentiel_roles_empiles_vide_est_byte_identique():
    """@brief Meme garantie de non-regression que pour l'ampli inverseur."""
    comps = [
        Component("U1", "U", {"IN+": "NET_INPLUS", "IN-": "NET_INMOINS",
                              "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INMOINS", "2": "NET_IN1"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INMOINS"}),
        Component("R3", "R", {"1": "NET_INPLUS", "2": "NET_IN2"}),
        Component("R4", "R", {"1": "NET_INPLUS", "2": "GND"}),
    ]
    roles = {"aop": ["U1"], "Z1": ["R1"], "Zf": ["R2"], "Z3": ["R3"], "Zg": ["R4"]}
    avec_defaut = _positionner_amplificateur_differentiel(comps, roles, 100, 200)
    avec_vide = _positionner_amplificateur_differentiel(comps, roles, 100, 200, frozenset())
    assert avec_defaut == avec_vide
    x_aop, y_aop = 100 + 2 * _PAS_X_BLOC, 200 + _PAS_Y_BLOC
    assert avec_defaut["U1"] == (x_aop, y_aop, 0)
    assert avec_defaut["R3"] == (100, y_aop + _PAS_Y_BLOC, 0)
    assert avec_defaut["R4"] == (x_aop, y_aop + 2 * _PAS_Y_BLOC, 0)


def test_positionner_amplificateur_differentiel_zf_empile_pousse_les_bandes_suivantes():
    """@brief Zf empile (2 elements paralleles) grandit vers le haut ; l'AOP,
    Z3 et Zg descendent tous d'autant pour ne jamais chevaucher Zf."""
    comps = [
        Component("U1", "U", {"IN+": "NET_INPLUS", "IN-": "NET_INMOINS",
                              "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INMOINS", "2": "NET_IN1"}),
        Component("C2", "C", {"1": "NET_OUT", "2": "NET_INMOINS"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INMOINS"}),
        Component("R3", "R", {"1": "NET_INPLUS", "2": "NET_IN2"}),
        Component("R4", "R", {"1": "NET_INPLUS", "2": "GND"}),
    ]
    roles = {"aop": ["U1"], "Z1": ["R1"], "Zf": ["C2", "R2"], "Z3": ["R3"], "Zg": ["R4"]}
    pos = _positionner_amplificateur_differentiel(comps, roles, 0, 0, frozenset({"Zf"}))
    x_aop = 2 * _PAS_X_BLOC
    assert pos["C2"] == (x_aop, 0, 0)
    assert pos["R2"] == (x_aop, _PAS_Y_BLOC, 0)
    assert pos["U1"] == (x_aop, 2 * _PAS_Y_BLOC, 0)
    assert pos["R1"] == (0, 2 * _PAS_Y_BLOC, 0)          # Z1 : meme ligne que l'AOP
    assert pos["R3"] == (0, 3 * _PAS_Y_BLOC, 0)          # Z3 : une bande plus bas qu'avant
    assert pos["R4"] == (x_aop, 4 * _PAS_Y_BLOC, 0)      # Zg : idem


def test_positionner_amplificateur_differentiel_z1_empile_meme_colonne():
    """@brief Z1 empile (fan-in a 3 entrees) : meme colonne, lignes
    distinctes -- meme garde-fou que Zin de l'ampli inverseur."""
    comps = [
        Component("U1", "U", {"IN+": "NET_INPLUS", "IN-": "NET_INMOINS",
                              "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INMOINS", "2": "NET_A"}),
        Component("R2", "R", {"1": "NET_A", "2": "NET_B"}),
        Component("R3", "R", {"1": "NET_B", "2": "NET_IN1"}),
        Component("Rf", "R", {"1": "NET_OUT", "2": "NET_INMOINS"}),
        Component("R5", "R", {"1": "NET_INPLUS", "2": "NET_IN2"}),
        Component("R6", "R", {"1": "NET_INPLUS", "2": "GND"}),
    ]
    roles = {"aop": ["U1"], "Z1": ["R1", "R2", "R3"], "Zf": ["Rf"],
             "Z3": ["R5"], "Zg": ["R6"]}
    pos = _positionner_amplificateur_differentiel(comps, roles, 0, 0, frozenset({"Z1"}))
    assert pos["R1"][0] == pos["R2"][0] == pos["R3"][0]
    assert len({pos["R1"][1], pos["R2"][1], pos["R3"][1]}) == 3
    assert pos["R5"][1] > max(pos["R1"][1], pos["R2"][1], pos["R3"][1])  # Z3 sous les 3 lignes de Z1
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k "differentiel_roles_empiles_vide or differentiel_zf_empile or differentiel_z1_empile" -v`
Expected: FAIL — signature à 4 arguments, `roles_empiles` n'existe pas encore.

- [ ] **Step 3: Réécrire l'implémentation**

Dans `circuit_analyzer/xml.py`, remplacer intégralement le corps de
`_positionner_amplificateur_differentiel` (garder la docstring, étendre
la liste `@param`) :

```python
def _positionner_amplificateur_differentiel(comps, roles, x: int, y: int,
                                             roles_empiles: frozenset = frozenset()) -> dict:
    """@brief Gabarit canonique de l'amplificateur différentiel.

    Deux chemins d'entrée empilés autour de l'AOP : Zf (contre-réaction,
    IN-) strictement au-dessus (même convention que Zf de l'ampli
    inverseur), Z1 (entrée IN-) à la même hauteur que l'AOP (même
    convention que Zin de l'ampli inverseur), puis Z3 (entrée IN+) une
    ligne EN DESSOUS de l'AOP, et Zg (référence masse de IN+) encore une
    ligne en dessous, alignée sous l'AOP. Angle toujours 0 (même raison
    que l'ampli inverseur — cf. sa docstring).

    Chaque rôle à 2+ refs est soit une RANGÉE horizontale (par défaut)
    soit un EMPILEMENT vertical (cf. _roles_a_empiler) quand son nom
    figure dans `roles_empiles`. Les 4 bandes (Zf, AOP+Z1, Z3, Zg) sont
    placées EN CASCADE : la hauteur de chaque bande (1 ligne, ou N si
    empilée) détermine où commence la bande suivante — un empilement
    dans une bande pousse toutes les bandes en dessous, jamais de
    chevauchement.

    @param comps Composants du bloc (Composant/Component).
    @param roles {'aop': [...], 'Z1': [...], 'Zf': [...], 'Z3': [...], 'Zg': [...]}.
    @param x, y Origine du bloc.
    @param roles_empiles Noms de rôle à empiler verticalement — cf.
           _roles_a_empiler. Vide par défaut : comportement rangée
           identique à avant l'ajout de ce paramètre.
    @return dict {ref: (x, y, angle)} pour les rôles connus,
            {ref: (x, y)} pour les satellites.
    """
    pos = {}
    refs_du_bloc = {c.ref for c in comps}
    zf_refs = roles.get('Zf', [])
    z1_refs = roles.get('Z1', [])
    z3_refs = roles.get('Z3', [])
    zg_refs = roles.get('Zg', [])
    hauteur_zf = len(zf_refs) if 'Zf' in roles_empiles and zf_refs else 1
    hauteur_z1 = max(1, len(z1_refs)) if 'Z1' in roles_empiles else 1
    hauteur_z3 = len(z3_refs) if 'Z3' in roles_empiles and z3_refs else 1
    hauteur_zg = len(zg_refs) if 'Zg' in roles_empiles and zg_refs else 1

    y_zf = y
    y_aop = y + hauteur_zf * _PAS_Y_BLOC
    y_z3 = y_aop + hauteur_z1 * _PAS_Y_BLOC
    y_zg = y_z3 + hauteur_z3 * _PAS_Y_BLOC
    x_aop = x + 2 * _PAS_X_BLOC

    for ref in roles.get('aop', []):
        if ref in refs_du_bloc:
            pos[ref] = (x_aop, y_aop, 0)

    for j, ref in enumerate(z1_refs):
        if ref not in refs_du_bloc:
            continue
        if 'Z1' in roles_empiles:
            pos[ref] = (x, y_aop + j * _PAS_Y_BLOC, 0)
        else:
            col = j if j < 2 else j + 1
            pos[ref] = (x + col * _PAS_X_BLOC, y_aop, 0)

    for j, ref in enumerate(zf_refs):
        if ref not in refs_du_bloc:
            continue
        if 'Zf' in roles_empiles:
            pos[ref] = (x_aop, y_zf + j * _PAS_Y_BLOC, 0)
        else:
            pos[ref] = (x_aop + j * _PAS_X_BLOC, y_zf, 0)

    for j, ref in enumerate(z3_refs):
        if ref not in refs_du_bloc:
            continue
        if 'Z3' in roles_empiles:
            pos[ref] = (x, y_z3 + j * _PAS_Y_BLOC, 0)
        else:
            pos[ref] = (x + j * _PAS_X_BLOC, y_z3, 0)

    for j, ref in enumerate(zg_refs):
        if ref not in refs_du_bloc:
            continue
        if 'Zg' in roles_empiles:
            pos[ref] = (x_aop, y_zg + j * _PAS_Y_BLOC, 0)
        else:
            pos[ref] = (x_aop + j * _PAS_X_BLOC, y_zg, 0)

    restants = [c for c in comps if c.ref not in pos]
    pos.update(_positionner_grille_compacte(
        restants, x, y_zg + max(0, hauteur_zg - 1) * _PAS_Y_BLOC))
    return pos
```

- [ ] **Step 4: Lancer TOUS les tests de ce positionneur, vérifier qu'ils passent**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k "amplificateur_differentiel" -v`
Expected: tous passent (les 4 tests existants avec l'ancienne signature +
les 3 nouveaux, moins la ligne dead-code retirée à l'étape 1).

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/xml.py tests/test_xml_generator.py
git commit -m "feat(disposition): _positionner_amplificateur_differentiel empile ses roles en cascade"
```

---

### Task 4 : Câblage — `_Bloc`, `_grouper_par_circuit`, les deux chemins d'appel

**Files:**
- Modify: `circuit_analyzer/xml.py` (`_Bloc`, `_grouper_par_circuit`,
  `_positionner_composants_bloc`)
- Modify: `circuit_analyzer/eretro_patch.py` (`_deltas_disposition_canonique`)
- Test: `tests/test_xml_generator.py`, `tests/test_eretro_patch.py`

**Interfaces:**
- Consomme : `_roles_a_empiler` (Task 1), signatures étendues des deux
  positionneurs (Tasks 2 et 3).
- Produit : `_Bloc.roles_empiles: frozenset` peuplé automatiquement pour
  tout bloc issu de `_grouper_par_circuit` — dernière pièce du chantier,
  rien d'autre n'en dépend.

- [ ] **Step 1: Écrire les tests (doivent échouer)**

Ajouter dans `tests/test_xml_generator.py`, juste après
`test_positionner_composants_bloc_dispatch_differentiel` :

```python
def test_grouper_par_circuit_peuple_roles_empiles_depuis_le_match():
    """@brief _grouper_par_circuit calcule roles_empiles pour chaque bloc,
    a partir du meme match que roles (pas un calcul separe/desynchronise)."""
    r = {
        'circuit_type': 'Intégrateur (AOP)',
        'components': ['U2', 'R5', 'C1', 'R6'],
        'impedances': {
            'Zin': {'refs': ['R5'], 'composition': 'R5'},
            'Zf': {'refs': ['C1', 'R6'], 'composition': '(C1//R6)'},
        },
    }
    comps = [
        Component("U2", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R5", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("C1", "C", {"1": "NET_INV", "2": "NET_OUT"}),
        Component("R6", "R", {"1": "NET_INV", "2": "NET_OUT"}),
    ]
    blocs = _grouper_par_circuit(comps, [r])
    bloc = next(b for b in blocs if b.label == 'Intégrateur (AOP)')
    assert bloc.roles_empiles == frozenset({'Zf'})


def test_positionner_composants_bloc_transmet_roles_empiles_au_positionneur():
    """@brief _positionner_composants_bloc passe bien bloc.roles_empiles au
    positionneur dispatche -- pas seulement bloc.roles."""
    comps = [
        Component("U2", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R5", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("C1", "C", {"1": "NET_INV", "2": "NET_OUT"}),
        Component("R6", "R", {"1": "NET_INV", "2": "NET_OUT"}),
    ]
    roles = {"aop": ["U2"], "Zin": ["R5"], "Zf": ["C1", "R6"]}
    bloc = _Bloc("Intégrateur (AOP)", comps, roles=roles,
                 roles_empiles=frozenset({"Zf"}))
    attendu = _positionner_amplificateur_inverseur(comps, roles, 50, 60, frozenset({"Zf"}))
    assert _positionner_composants_bloc(bloc, 50, 60) == attendu
```

Ajouter dans `tests/test_eretro_patch.py`, juste après
`test_ecrire_groupes_deplace_les_trois_montages_a_deux_roles` :

```python
def test_ecrire_groupes_empile_un_zf_reellement_parallele(tmp_path):
    """@brief Bout en bout, chemin carte scannee : un Zf reellement
    parallele (C1//R6, le cas reel de test_pid_3.xml) est empile
    verticalement -- pas seulement translate en rangee. Verifie la FORME
    complete (comme les tests renforces plus tot aujourd'hui), pas juste
    'une position a bouge'."""
    from circuit_analyzer.eretro_patch import ecrire_groupes
    from circuit_analyzer.xml import _positionner_amplificateur_inverseur

    comps = [
        Composant("U2", "U", {"IN+": "GND", "IN-": "NET_INV",
                              "OUT": "NET_OUT", "V+": "VCC", "V-": "GND"}),
        Composant("R5", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Composant("C1", "C", {"1": "NET_INV", "2": "NET_OUT"}),
        Composant("R6", "R", {"1": "NET_INV", "2": "NET_OUT"}),
    ]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, res = _analyser(chemin)

    xml_patche = ecrire_groupes(lus.source, lus, res)
    racine = ET.fromstring(xml_patche)
    positions_apres = {
        item.findtext("reference"):
            (float(item.find("CtrIem/X").text), float(item.find("CtrIem/Y").text))
        for item in racine.findall(".//CmpntL/DataItem")
    }

    refs = ["U2", "R5", "C1", "R6"]
    min_x = min(positions_apres[ref][0] for ref in refs)
    min_y = min(positions_apres[ref][1] for ref in refs)
    forme_obtenue = {ref: (positions_apres[ref][0] - min_x,
                            positions_apres[ref][1] - min_y) for ref in refs}

    roles = {"aop": ["U2"], "Zin": ["R5"], "Zf": ["C1", "R6"]}
    canonique = _positionner_amplificateur_inverseur(comps, roles, 0, 0, frozenset({"Zf"}))
    can_min_x = min(p[0] for p in canonique.values())
    can_min_y = min(p[1] for p in canonique.values())
    forme_attendue = {ref: (pos[0] - can_min_x, pos[1] - can_min_y)
                       for ref, pos in canonique.items()}
    assert forme_obtenue == forme_attendue

    chemin_patche = os.path.join(str(tmp_path), "patche.xml")
    with open(chemin_patche, "w", encoding="utf-8") as f:
        f.write(xml_patche)
    relu, res_relu = _analyser(chemin_patche)
    types_relu = [r["circuit_type"] for r in res_relu]
    assert "Intégrateur (AOP)" in types_relu
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k "grouper_par_circuit_peuple_roles_empiles or transmet_roles_empiles" tests/test_eretro_patch.py -k "empile_un_zf_reellement_parallele" -v`
Expected: FAIL — `_Bloc` n'a pas encore de champ `roles_empiles`
(`TypeError: __init__() got an unexpected keyword argument`), et le
dispatch dans `_positionner_composants_bloc`/`_deltas_disposition_canonique`
ne transmet pas encore ce champ.

- [ ] **Step 3: Câbler `_Bloc` et `_grouper_par_circuit`**

Dans `circuit_analyzer/xml.py`, modifier `_Bloc` :

```python
@dataclass
class _Bloc:
    """@brief Bloc de mise en page : un libellé de circuit et ses composants.

    `roles` associe un nom de rôle (ex. 'aop', 'Zin', 'Zf') à la liste des
    refs qui le jouent — vide si le montage n'a pas de décomposition par
    rôle connue (Divers, ou montage pas encore migré vers un positionneur
    canonique).
    `roles_empiles` : ensemble des noms de rôle à empiler verticalement
    (fan-in ou parallèle pur) au lieu d'une rangée horizontale — cf.
    _roles_a_empiler. Vide si rien à empiler.
    """
    label: str
    comps: list
    roles: dict = field(default_factory=dict)
    roles_empiles: frozenset = field(default_factory=frozenset)
```

Dans `_grouper_par_circuit`, remplacer la construction du bloc :

```python
        b = _Bloc(label, [comp_par_ref[ref] for ref in _refs_du_bloc(r)
                          if ref in comp_par_ref and type_du_ref.get(ref) == label],
                  roles=_roles_du_bloc(r))
```

par :

```python
        b = _Bloc(label, [comp_par_ref[ref] for ref in _refs_du_bloc(r)
                          if ref in comp_par_ref and type_du_ref.get(ref) == label],
                  roles=_roles_du_bloc(r), roles_empiles=_roles_a_empiler(r))
```

- [ ] **Step 4: Câbler `_positionner_composants_bloc`**

Dans `circuit_analyzer/xml.py`, dans `_positionner_composants_bloc`,
remplacer :

```python
    positionneur = _POSITIONNEURS_PAR_MOTIF.get(bloc.label)
    if positionneur is not None and bloc.roles:
        return positionneur(bloc.comps, bloc.roles, x, y)
```

par :

```python
    positionneur = _POSITIONNEURS_PAR_MOTIF.get(bloc.label)
    if positionneur is not None and bloc.roles:
        return positionneur(bloc.comps, bloc.roles, x, y, bloc.roles_empiles)
```

- [ ] **Step 5: Câbler `_deltas_disposition_canonique` (chemin carte scannée)**

Dans `circuit_analyzer/eretro_patch.py`, dans `_deltas_disposition_canonique`,
remplacer :

```python
        provisoire = _POSITIONNEURS_PAR_MOTIF[bloc.label](comps_role, bloc.roles, 0, 0)
```

par :

```python
        provisoire = _POSITIONNEURS_PAR_MOTIF[bloc.label](comps_role, bloc.roles, 0, 0, bloc.roles_empiles)
```

- [ ] **Step 6: Lancer tous les tests des deux fichiers**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py tests/test_eretro_patch.py -v`
Expected: tous passent (existants + nouveaux). Prêter une attention
particulière aux tests écrits AVANT ce chantier
(`test_positionner_composants_bloc_utilise_le_canonique_si_roles`,
`test_positionner_composants_bloc_dispatch_sommateur_integrateur_derivateur`,
etc.) — s'ils échouent, une régression de compatibilité s'est glissée
dans le câblage.

- [ ] **Step 7: Commit**

```bash
git add circuit_analyzer/xml.py circuit_analyzer/eretro_patch.py tests/test_xml_generator.py tests/test_eretro_patch.py
git commit -m "feat(disposition): cable roles_empiles de bout en bout (les deux chemins)"
```

---

### Task 5 : Vérification bout en bout sur la carte réelle + visuel

**Files:**
- Modify: `tools/render_boardsch_layout.py` (ajout d'un cas de démo
  Intégrateur avec Zf parallèle)

**Interfaces:**
- Consomme : le positionneur (Task 2) via le pipeline complet
  (`match_patterns`/`build_graph`/`components_to_xml`, comme les démos
  existantes du fichier).
- Produit : rien pour d'autres tâches — dernière tâche du plan.

- [ ] **Step 1: Étendre le bloc de démo (cas synthétique, committé)**

Dans `tools/render_boardsch_layout.py`, juste après le bloc différentiel
ajouté lors du chantier précédent (après la ligne
`print(f"Rendu ecrit : {OUT / 'disposition_ampli_differentiel.png'}")`,
avant le commentaire `# Chemin carte scannee (ecrire_groupes)...`),
ajouter :

```python
    # Integrateur avec Zf reellement parallele (C1//R6) : verifie
    # l'empilement vertical au lieu de la rangee -- le cas reel trouve sur
    # test_pid_3.xml, qui produisait un fil en diagonale avant ce chantier.
    comps_zf_parallele = [
        Component("U2", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R5", "R", {"1": "NET_INV", "2": "NET_IN"}),
        Component("C1", "C", {"1": "NET_INV", "2": "NET_OUT"}),
        Component("R6", "R", {"1": "NET_INV", "2": "NET_OUT"}),
    ]
    resultats_zf_par = match_patterns(build_graph(comps_zf_parallele))
    xml_zf_par = components_to_xml(comps_zf_parallele, resultats_zf_par)
    render(xml_zf_par, OUT / "disposition_zf_parallele.png")
    print(f"Rendu ecrit : {OUT / 'disposition_zf_parallele.png'}")
```

- [ ] **Step 2: Régénérer et inspecter le cas synthétique**

Run: `PYTHONUTF8=1 python tools/render_boardsch_layout.py`

Puis lire (outil Read, pas juste lister) `tools/_renders/disposition_zf_parallele.png`,
et confirmer visuellement : C1 et R6 empilés en 2 lignes horizontales
distinctes au-dessus de l'AOP (PAS côte à côte sur la même ligne), tous
deux alignés sur la même colonne que l'AOP. Aucune rotation visible.

- [ ] **Step 3: Vérification sur la carte réelle du boss (`test_pid_3.xml`)**

Ce fichier n'est PAS commité (fichier personnel fourni par le boss,
présent à la racine du dépôt principal, pas dans ce worktree). Le copier
depuis le dépôt principal avant de continuer :

```bash
cp "../../../test_pid_3.xml" .
```

(Adapter le chemin relatif si besoin — le fichier doit être à la racine
DU DÉPÔT PRINCIPAL `C:\Users\Utilisateur\Desktop\test3\test_pid_3.xml`,
copié vers la racine de CE worktree.)

Lancer :

```bash
PYTHONUTF8=1 python -c "
from circuit_analyzer.composant import construire_graphe as build_graph
from circuit_analyzer.detecteur import analyser as match_patterns
from circuit_analyzer.xml import lire_xml
from circuit_analyzer.eretro_patch import ecrire_groupes

comps = lire_xml('test_pid_3.xml')
graph = build_graph(comps)
results = match_patterns(graph)
xml = ecrire_groupes(comps.source, comps, results)
with open('test_pid_3_groupe_empile.xml', 'w', encoding='utf-8') as f:
    f.write(xml)

for ref in ('U2', 'R5', 'C1', 'R6'):
    el = comps.source.elements.get(ref)
    if el is not None:
        print(ref, el.find('CtrIem/X').text, el.find('CtrIem/Y').text)
"
```

Attendu : C1 et R6 doivent avoir la MÊME coordonnée X (empilés), des Y
différents espacés de 190. Si ce n'est pas le cas, investiguer avant de
continuer — ce test contre la carte réelle du boss est la preuve finale
que le chantier corrige le problème original.

Ne PAS committer `test_pid_3.xml` ni `test_pid_3_groupe_empile.xml` (fichiers
personnels/de vérification, hors dépôt).

- [ ] **Step 4: Régénérer le rendu visuel sur la carte réelle**

```bash
PYTHONUTF8=1 python -c "
from tools.render_boardsch_layout import render
with open('test_pid_3_groupe_empile.xml', encoding='utf-8') as f:
    render(f.read(), 'test_pid_3_apres_empilement.png')
"
```

Lire (outil Read) `test_pid_3_apres_empilement.png` et comparer
visuellement à l'ancien rendu (`test pid.png`, fourni par le boss plus tôt
dans la conversation) : le fil auparavant en diagonale entre U2/C1/R6 doit
avoir disparu, remplacé par un empilement propre avec des fils à angle
droit ou colinéaires. Décrire précisément ce qui est observé dans le
rapport de tâche — pas une description générique.

- [ ] **Step 5: Commit (uniquement le fichier source, pas les artefacts de vérification)**

```bash
git add tools/render_boardsch_layout.py
git commit -m "test(disposition): ajoute un rendu visuel pour Zf reellement parallele"
```

Note : ne pas committer les PNG régénérés (`tools/_renders/` est
git-ignoré), ni `test_pid_3.xml`/`test_pid_3_groupe_empile.xml`/
`test_pid_3_apres_empilement.png` (fichiers de vérification locaux, hors
dépôt — les supprimer du worktree après inspection si l'outil de nettoyage
final du chantier ne le fait pas automatiquement).
