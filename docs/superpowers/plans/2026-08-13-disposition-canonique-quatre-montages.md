# Disposition canonique — 4 montages supplémentaires — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Étendre la disposition canonique (déjà livrée pour l'Amplificateur
inverseur, sur les deux chemins `generer_xml` et `ecrire_groupes`) à 4
montages AOP supplémentaires : Amplificateur sommateur, Intégrateur,
Dérivateur, Amplificateur différentiel.

**Architecture:** 3 des 4 montages (Sommateur, Intégrateur, Dérivateur) ont
exactement la même forme de rôles `{'Zin': ..., 'Zf': ...}` que l'ampli
inverseur (Sommateur : `Zin` est une LISTE, déjà géré) — ils se contentent
d'un enregistrement dans `_POSITIONNEURS_PAR_MOTIF` pointant vers la
fonction EXISTANTE `_positionner_amplificateur_inverseur`, sans la
modifier. L'Amplificateur différentiel a une forme différente à 4 rôles
(`Z1`, `Zf`, `Z3`, `Zg` — deux chemins d'entrée) et reçoit une nouvelle
fonction `_positionner_amplificateur_differentiel`. Le registre
`_POSITIONNEURS_PAR_MOTIF` est déjà consommé par les deux chemins
(`generer_xml` et `ecrire_groupes`) via `_positionner_composants_bloc` —
aucun branchement supplémentaire nécessaire.

**Tech Stack:** Python, `circuit_analyzer/xml.py` (positionneurs),
`circuit_analyzer/detecteur.py` (lecture seule, déjà vérifié), pytest,
matplotlib (rendu visuel de vérification).

## Global Constraints

- Angle toujours 0 — jamais de rotation (même règle que tous les
  positionneurs canoniques existants : une rotation de symbole n'est pas
  fiable côté fils dans ERetroDesign, cf. docstring de
  `_positionner_amplificateur_inverseur`).
- Aucune modification de `_roles_du_bloc`, `_refs_du_role`,
  `_deltas_disposition_canonique`, `_appliquer_deltas` — déjà génériques,
  déjà vérifiées pour la forme `Zin` en LISTE (Sommateur) dans un chantier
  précédent.
- Tout composant du bloc absent des `roles` connus (satellite) doit rester
  placé (jamais perdu) via `_positionner_grille_compacte`, comme pour
  l'ampli inverseur.
- `_PAS_X_BLOC = 260`, `_PAS_Y_BLOC = 190` (constantes existantes,
  `circuit_analyzer/xml.py:788-789`) — réutiliser telles quelles, ne pas en
  créer de nouvelles.
- Ne jamais committer avec un trailer `Co-Authored-By: Claude` (convention
  du projet).

---

### Task 1: `_positionner_amplificateur_differentiel`

**Files:**
- Modify: `circuit_analyzer/xml.py` (nouvelle fonction, juste après
  `_positionner_amplificateur_inverseur`, avant l'assignation de
  `_POSITIONNEURS_PAR_MOTIF` qui est à la ligne 1045 aujourd'hui)
- Test: `tests/test_xml_generator.py` (nouveaux tests, juste après la
  section `# ── Positionneur canonique : amplificateur inverseur ──`,
  avant la section `# ── Dispatch du positionneur canonique...`)

**Interfaces:**
- Consomme : `_PAS_X_BLOC`, `_PAS_Y_BLOC`, `_positionner_grille_compacte`
  (toutes déjà définies dans `circuit_analyzer/xml.py`).
- Produit : `_positionner_amplificateur_differentiel(comps, roles, x, y) ->
  dict[str, tuple]` — même signature que
  `_positionner_amplificateur_inverseur`. `roles` a la forme
  `{'aop': [...], 'Z1': [...], 'Zf': [...], 'Z3': [...], 'Zg': [...]}`
  (confirmé contre `circuit_analyzer/detecteur.py:665-668`, fonction
  `detecter_amplificateur_differentiel`). Consommé par Task 2 (registre).

- [ ] **Step 1: Écrire les tests (ils doivent échouer — la fonction
  n'existe pas encore)**

Ajouter dans `tests/test_xml_generator.py`, juste après
`test_positionner_amplificateur_inverseur_ignore_role_hors_bloc` (avant la
ligne `# ── Dispatch du positionneur canonique + angle dans le XML ──`) :

```python
# ── Positionneur canonique : amplificateur différentiel ─────────────────────

from circuit_analyzer.xml import _positionner_amplificateur_differentiel


def test_positionner_amplificateur_differentiel_places_roles_canoniquement():
    """@brief Zf au-dessus, Z1 a la hauteur de l'AOP (comme Zin de l'inverseur),
    Z3 une ligne EN DESSOUS de l'AOP, Zg encore en dessous, alignee sous l'AOP."""
    comps = [
        Component("U1", "U", {"IN+": "NET_INPLUS", "IN-": "NET_INMOINS",
                              "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INMOINS", "2": "NET_IN1"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INMOINS"}),
        Component("R3", "R", {"1": "NET_INPLUS", "2": "NET_IN2"}),
        Component("R4", "R", {"1": "NET_INPLUS", "2": "GND"}),
    ]
    roles = {"aop": ["U1"], "Z1": ["R1"], "Zf": ["R2"], "Z3": ["R3"], "Zg": ["R4"]}
    pos = _positionner_amplificateur_differentiel(comps, roles, 100, 200)
    x_aop, y_aop = 100 + 2 * _PAS_X_BLOC, 200 + _PAS_Y_BLOC
    assert pos["U1"] == (x_aop, y_aop, 0)
    assert pos["R1"] == (100, y_aop, 0)                      # Z1
    assert pos["R2"] == (x_aop, 200, 0)                      # Zf
    assert pos["R3"] == (100, y_aop + _PAS_Y_BLOC, 0)         # Z3
    assert pos["R4"] == (x_aop, y_aop + 2 * _PAS_Y_BLOC, 0)   # Zg
    # Ordre vertical attendu : Zf (haut) -> AOP -> Z3 -> Zg (bas)
    assert pos["R2"][1] < pos["U1"][1] < pos["R3"][1] < pos["R4"][1]


def test_positionner_amplificateur_differentiel_garde_les_satellites():
    """@brief Un composant du bloc absent des roles (satellite) est place, pas perdu."""
    comps = [
        Component("U1", "U", {"IN+": "NET_INPLUS", "IN-": "NET_INMOINS",
                              "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INMOINS", "2": "NET_IN1"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INMOINS"}),
        Component("R3", "R", {"1": "NET_INPLUS", "2": "NET_IN2"}),
        Component("R4", "R", {"1": "NET_INPLUS", "2": "GND"}),
        Component("C9", "C", {"1": "NET_IN1", "2": "GND"}),
    ]
    roles = {"aop": ["U1"], "Z1": ["R1"], "Zf": ["R2"], "Z3": ["R3"], "Zg": ["R4"]}
    pos = _positionner_amplificateur_differentiel(comps, roles, 0, 0)
    assert "C9" in pos
    assert len(pos["C9"]) == 2


def test_positionner_amplificateur_differentiel_ignore_role_hors_bloc():
    """@brief Un ref present dans `roles` mais absent de `comps` ne doit JAMAIS
    recevoir de position ici (meme garde-fou que l'ampli inverseur : evite le
    vol de position inter-blocs via le `pos.update(...)` partage de
    `_positionner_blocs`)."""
    comps = [
        Component("U1", "U", {"IN+": "NET_INPLUS", "IN-": "NET_INMOINS",
                              "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INMOINS", "2": "NET_IN1"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INMOINS"}),
        Component("R3", "R", {"1": "NET_INPLUS", "2": "NET_IN2"}),
        Component("R4", "R", {"1": "NET_INPLUS", "2": "GND"}),
    ]
    roles = {"aop": ["U1"], "Z1": ["R1"], "Zf": ["R2"], "Z3": ["R3"],
             "Zg": ["R4", "R99"]}
    pos = _positionner_amplificateur_differentiel(comps, roles, 0, 0)
    assert "R99" not in pos
    assert all(ref in pos for ref in ("U1", "R1", "R2", "R3", "R4"))
```

- [ ] **Step 2: Lancer les tests, verifier qu'ils echouent**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k differentiel -v`
Expected: FAIL — `ImportError: cannot import name '_positionner_amplificateur_differentiel'`

- [ ] **Step 3: Ecrire l'implementation**

Dans `circuit_analyzer/xml.py`, juste apres la fonction
`_positionner_amplificateur_inverseur` (avant la ligne
`_POSITIONNEURS_PAR_MOTIF = {`) :

```python
def _positionner_amplificateur_differentiel(comps, roles, x: int, y: int) -> dict:
    """@brief Gabarit canonique de l'amplificateur différentiel.

    Deux chemins d'entrée empilés autour de l'AOP : Zf (contre-réaction,
    IN-) strictement au-dessus (même convention que Zf de l'ampli
    inverseur), Z1 (entrée IN-) à la même hauteur que l'AOP (même
    convention que Zin de l'ampli inverseur), puis Z3 (entrée IN+) une
    ligne EN DESSOUS de l'AOP, et Zg (référence masse de IN+) encore une
    ligne en dessous, alignée sous l'AOP. Angle toujours 0 (même raison
    que l'ampli inverseur — cf. sa docstring).

    @param comps Composants du bloc (Composant/Component).
    @param roles {'aop': [...], 'Z1': [...], 'Zf': [...], 'Z3': [...], 'Zg': [...]}.
    @param x, y Origine du bloc.
    @return dict {ref: (x, y, angle)} pour les rôles connus,
            {ref: (x, y)} pour les satellites.
    """
    pos = {}
    refs_du_bloc = {c.ref for c in comps}
    x_aop, y_aop = x + 2 * _PAS_X_BLOC, y + _PAS_Y_BLOC
    for ref in roles.get('aop', []):
        if ref in refs_du_bloc:
            pos[ref] = (x_aop, y_aop, 0)
    for j, ref in enumerate(roles.get('Z1', [])):
        if ref in refs_du_bloc:
            pos[ref] = (x + j * _PAS_X_BLOC, y_aop, 0)
    for j, ref in enumerate(roles.get('Zf', [])):
        if ref in refs_du_bloc:
            pos[ref] = (x_aop + j * _PAS_X_BLOC, y, 0)
    for j, ref in enumerate(roles.get('Z3', [])):
        if ref in refs_du_bloc:
            pos[ref] = (x + j * _PAS_X_BLOC, y_aop + _PAS_Y_BLOC, 0)
    for j, ref in enumerate(roles.get('Zg', [])):
        if ref in refs_du_bloc:
            pos[ref] = (x_aop + j * _PAS_X_BLOC, y_aop + 2 * _PAS_Y_BLOC, 0)
    restants = [c for c in comps if c.ref not in pos]
    pos.update(_positionner_grille_compacte(restants, x, y + 3 * _PAS_Y_BLOC))
    return pos
```

- [ ] **Step 4: Lancer les tests, verifier qu'ils passent**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k differentiel -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add circuit_analyzer/xml.py tests/test_xml_generator.py
git commit -m "feat(disposition): _positionner_amplificateur_differentiel, gabarit a 4 roles"
```

---

### Task 2: Registre + tests de dispatch et bout-en-bout (les 2 chemins)

**Files:**
- Modify: `circuit_analyzer/xml.py` (extension de
  `_POSITIONNEURS_PAR_MOTIF`, ligne 1045-1047 aujourd'hui)
- Test: `tests/test_xml_generator.py` (tests de dispatch + roundtrip
  fabrication, section `# ── Dispatch du positionneur canonique...`)
- Test: `tests/test_eretro_patch.py` (tests bout-en-bout chemin patch,
  après `test_ecrire_groupes_preserve_la_connectivite_apres_translation`)

**Interfaces:**
- Consomme : `_positionner_amplificateur_inverseur` (Task existante,
  inchangée), `_positionner_amplificateur_differentiel` (Task 1).
- Produit : `_POSITIONNEURS_PAR_MOTIF` avec 5 entrées — plus rien à
  produire pour des tâches suivantes, ce chantier se termine ici (Task 3
  est uniquement visuel/inspection).

- [ ] **Step 1: Écrire les tests de dispatch (registre) — doivent échouer**

Ajouter dans `tests/test_xml_generator.py`, juste après
`test_positionner_composants_bloc_repli_si_pas_de_roles` (avant la
fonction `_item`) :

```python
def test_positionner_composants_bloc_dispatch_sommateur_integrateur_derivateur():
    """@brief Les 3 montages qui partagent la forme {Zin, Zf} de l'ampli
    inverseur reutilisent LE MEME positionneur via le registre — y compris
    le Sommateur, dont Zin est une LISTE (plusieurs entrees), deja gere par
    _positionner_amplificateur_inverseur."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN1"}),
        Component("R2", "R", {"1": "NET_INV", "2": "NET_IN2"}),
        Component("Rf", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    roles = {"aop": ["U1"], "Zin": ["R1", "R2"], "Zf": ["Rf"]}
    for label in ("Amplificateur sommateur (AOP)", "Intégrateur (AOP)",
                  "Dérivateur (AOP)"):
        bloc = _Bloc(label, comps, roles=roles)
        attendu = _positionner_amplificateur_inverseur(comps, roles, 50, 60)
        assert _positionner_composants_bloc(bloc, 50, 60) == attendu


def test_positionner_composants_bloc_dispatch_differentiel():
    """@brief L'Amplificateur différentiel utilise son propre positionneur
    (forme a 4 roles, pas celle de l'ampli inverseur)."""
    comps = [
        Component("U1", "U", {"IN+": "NET_INPLUS", "IN-": "NET_INMOINS",
                              "OUT": "NET_OUT"}),
        Component("R1", "R", {"1": "NET_INMOINS", "2": "NET_IN1"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INMOINS"}),
        Component("R3", "R", {"1": "NET_INPLUS", "2": "NET_IN2"}),
        Component("R4", "R", {"1": "NET_INPLUS", "2": "GND"}),
    ]
    roles = {"aop": ["U1"], "Z1": ["R1"], "Zf": ["R2"], "Z3": ["R3"], "Zg": ["R4"]}
    bloc = _Bloc("Amplificateur différentiel (AOP)", comps, roles=roles)
    attendu = _positionner_amplificateur_differentiel(comps, roles, 50, 60)
    assert _positionner_composants_bloc(bloc, 50, 60) == attendu
```

Ajouter aussi, dans la section roundtrip existante (après
`test_roundtrip_combined_multi_pattern`, avant
`test_disposition_canonique_preserve_la_connectivite`) :

```python
def test_roundtrip_amplificateur_differentiel():
    """@brief Le montage differentiel survit au roundtrip XML (connectivite)."""
    comps = [
        Component("U1", "U", {"IN+": "NET_INPLUS", "IN-": "NET_INMOINS",
                              "OUT": "NET_OUT", "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INMOINS", "2": "NET_IN1"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INMOINS"}),
        Component("R3", "R", {"1": "NET_INPLUS", "2": "NET_IN2"}),
        Component("R4", "R", {"1": "NET_INPLUS", "2": "GND"}),
    ]
    xml = components_to_xml(comps)
    back = _xml_to_components(xml)
    types = [r["circuit_type"] for r in match_patterns(build_graph(back))]
    assert "Amplificateur différentiel (AOP)" in types


def test_roundtrip_amplificateur_sommateur():
    """@brief Le montage sommateur survit au roundtrip XML (connectivite)."""
    comps = [
        Component("U1", "U", {"IN+": "GND", "IN-": "NET_INV", "OUT": "NET_OUT",
                              "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INV", "2": "NET_IN1"}),
        Component("R2", "R", {"1": "NET_INV", "2": "NET_IN2"}),
        Component("Rf", "R", {"1": "NET_OUT", "2": "NET_INV"}),
    ]
    xml = components_to_xml(comps)
    back = _xml_to_components(xml)
    types = [r["circuit_type"] for r in match_patterns(build_graph(back))]
    assert "Amplificateur sommateur (AOP)" in types
```

- [ ] **Step 2: Lancer les tests, verifier qu'ils echouent**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py -k "dispatch_sommateur or dispatch_differentiel or roundtrip_amplificateur" -v`
Expected: FAIL — les dispatchs retombent sur le gabarit famille generique
(l'assertion d'egalite avec `attendu` echoue) car le registre ne contient
pas encore ces labels.

- [ ] **Step 3: Ecrire les tests bout-en-bout chemin patch (ecrire_groupes) — doivent echouer**

Ajouter dans `tests/test_eretro_patch.py`, juste apres
`test_ecrire_groupes_preserve_la_connectivite_apres_translation` :

```python
def test_ecrire_groupes_deplace_amplificateur_differentiel(tmp_path):
    """@brief Chemin carte scannee : le differentiel (nouvellement migre)
    est translate vers sa disposition canonique, pas seulement groupe.
    Meme style d'assertion (positions avant/apres) que le test existant
    test_ecrire_groupes_deplace_lampli_inverseur_vers_sa_disposition_canonique
    (ligne 1136) : AVANT le Step 5 de ce Task (registre pas encore etendu),
    `_deltas_disposition_canonique` exclut ce bloc (garde
    `bloc.label not in _POSITIONNEURS_PAR_MOTIF`, eretro_patch.py:119) donc
    AUCUNE position ne bouge — ce test DOIT echouer avant le Step 5."""
    from circuit_analyzer.eretro_patch import ecrire_groupes

    comps = [
        Composant("U1", "U", {"IN+": "NET_INPLUS", "IN-": "NET_INMOINS",
                              "OUT": "NET_OUT", "V+": "VCC", "V-": "GND"}),
        Composant("R1", "R", {"1": "NET_INMOINS", "2": "NET_IN1"}),
        Composant("R2", "R", {"1": "NET_OUT", "2": "NET_INMOINS"}),
        Composant("R3", "R", {"1": "NET_INPLUS", "2": "NET_IN2"}),
        Composant("R4", "R", {"1": "NET_INPLUS", "2": "GND"}),
    ]
    chemin = _fichier_synthetique(tmp_path, comps)
    lus, res = _analyser(chemin)
    positions_avant = {
        ref: (float(el.find("CtrIem/X").text), float(el.find("CtrIem/Y").text))
        for ref, el in lus.source.elements.items()
    }

    xml_patche = ecrire_groupes(lus.source, lus, res)
    racine = ET.fromstring(xml_patche)
    positions_apres = {
        item.findtext("reference"):
            (float(item.find("CtrIem/X").text), float(item.find("CtrIem/Y").text))
        for item in racine.findall(".//CmpntL/DataItem")
    }
    assert any(positions_avant[ref] != positions_apres[ref]
               for ref in ("U1", "R1", "R2", "R3", "R4"))

    # Connectivite : le montage reste detectable apres translation.
    chemin_patche = os.path.join(str(tmp_path), "patche.xml")
    with open(chemin_patche, "w", encoding="utf-8") as f:
        f.write(xml_patche)
    relu, res_relu = _analyser(chemin_patche)
    types_relu = sorted(r["circuit_type"] for r in res_relu)
    assert "Amplificateur différentiel (AOP)" in types_relu
    assert {c.ref for c in relu} == {"U1", "R1", "R2", "R3", "R4"}


def test_ecrire_groupes_deplace_les_trois_montages_a_deux_roles(tmp_path):
    """@brief Sommateur, Integrateur, Derivateur (partagent la forme {Zin, Zf})
    sont chacun translates vers une disposition canonique apres migration,
    sur le chemin carte scannee. Meme raisonnement rouge/vert que le test
    precedent : DOIT echouer avant le Step 5 (registre pas encore etendu)."""
    from circuit_analyzer.eretro_patch import ecrire_groupes

    cas = {
        "Amplificateur sommateur (AOP)": [
            Composant("U1", "U", {"IN+": "GND", "IN-": "NET_INV",
                                  "OUT": "NET_OUT", "V+": "VCC", "V-": "GND"}),
            Composant("R1", "R", {"1": "NET_INV", "2": "NET_IN1"}),
            Composant("R2", "R", {"1": "NET_INV", "2": "NET_IN2"}),
            Composant("Rf", "R", {"1": "NET_OUT", "2": "NET_INV"}),
        ],
        "Intégrateur (AOP)": [
            Composant("U1", "U", {"IN+": "GND", "IN-": "NET_INV",
                                  "OUT": "NET_OUT", "V+": "VCC", "V-": "GND"}),
            Composant("R1", "R", {"1": "NET_INV", "2": "NET_IN"}),
            Composant("C1", "C", {"1": "NET_INV", "2": "NET_OUT"}),
        ],
        "Dérivateur (AOP)": [
            Composant("U1", "U", {"IN+": "GND", "IN-": "NET_INV",
                                  "OUT": "NET_OUT", "V+": "VCC", "V-": "GND"}),
            Composant("C1", "C", {"1": "NET_INV", "2": "NET_IN"}),
            Composant("R1", "R", {"1": "NET_INV", "2": "NET_OUT"}),
        ],
    }
    for idx, (label, comps) in enumerate(cas.items()):
        # `_fichier_synthetique` ecrit toujours vers le meme nom fixe
        # ("synth.xml") DANS tmp_path (voir son implementation,
        # test_eretro_patch.py:83-97) — reutiliser tmp_path directement
        # pour chaque cas est sans risque : le fichier est relu en memoire
        # (`lus = lire_xml(chemin)`) avant l'iteration suivante, donc
        # l'ecrasement entre cas n'aliase rien.
        chemin = _fichier_synthetique(tmp_path, comps)
        lus, res = _analyser(chemin)
        refs = [c.ref for c in comps]
        positions_avant = {
            ref: (float(lus.source.elements[ref].find("CtrIem/X").text),
                  float(lus.source.elements[ref].find("CtrIem/Y").text))
            for ref in refs
        }

        xml_patche = ecrire_groupes(lus.source, lus, res)
        racine = ET.fromstring(xml_patche)
        positions_apres = {
            item.findtext("reference"):
                (float(item.find("CtrIem/X").text), float(item.find("CtrIem/Y").text))
            for item in racine.findall(".//CmpntL/DataItem")
        }
        assert any(positions_avant[ref] != positions_apres[ref] for ref in refs), \
            f"{label} : aucune position n'a bouge"

        chemin_patche = os.path.join(str(tmp_path), f"patche_{idx}.xml")
        with open(chemin_patche, "w", encoding="utf-8") as f:
            f.write(xml_patche)
        relu, res_relu = _analyser(chemin_patche)
        types_relu = [r["circuit_type"] for r in res_relu]
        assert label in types_relu, f"{label} non redetecte apres translation"
```

- [ ] **Step 4: Lancer les tests bout-en-bout, verifier qu'ils echouent**

Run: `PYTHONUTF8=1 python -m pytest tests/test_eretro_patch.py -k "deplace_amplificateur_differentiel or deplace_les_trois_montages" -v`
Expected: FAIL — `_deltas_disposition_canonique` exclut tout bloc dont le
label n'est pas dans `_POSITIONNEURS_PAR_MOTIF`
(`circuit_analyzer/eretro_patch.py:119`), donc avant le Step 5 aucune
position ne bouge pour ces 4 montages : l'assertion
`assert any(positions_avant[ref] != positions_apres[ref] ...)` echoue
(`False`). Si un des deux tests echoue pour une AUTRE raison (ex.
`KeyError`, montage non detecte du tout), s'arreter et investiguer avant
de continuer — un echec de connectivite a ce stade indiquerait un bug de
fixture, pas simplement un registre incomplet.

- [ ] **Step 5: Etendre le registre**

Dans `circuit_analyzer/xml.py`, remplacer :

```python
_POSITIONNEURS_PAR_MOTIF = {
    "Amplificateur inverseur (AOP)": _positionner_amplificateur_inverseur,
}
```

par :

```python
_POSITIONNEURS_PAR_MOTIF = {
    "Amplificateur inverseur (AOP)": _positionner_amplificateur_inverseur,
    "Amplificateur sommateur (AOP)": _positionner_amplificateur_inverseur,
    "Intégrateur (AOP)": _positionner_amplificateur_inverseur,
    "Dérivateur (AOP)": _positionner_amplificateur_inverseur,
    "Amplificateur différentiel (AOP)": _positionner_amplificateur_differentiel,
}
```

- [ ] **Step 6: Lancer toute la suite des deux fichiers de test**

Run: `PYTHONUTF8=1 python -m pytest tests/test_xml_generator.py tests/test_eretro_patch.py -v`
Expected: tous les tests passent (existants + nouveaux) — les 2 tests de
dispatch, les 2 tests roundtrip, et les 2 tests bout-en-bout ecrits aux
Steps 1 et 3 passent maintenant que le registre est etendu.

- [ ] **Step 7: Commit**

```bash
git add circuit_analyzer/xml.py tests/test_xml_generator.py tests/test_eretro_patch.py
git commit -m "feat(disposition): etend le registre canonique a 4 montages supplementaires"
```

---

### Task 3: Vérification visuelle

**Files:**
- Modify: `tools/render_boardsch_layout.py` (ajout d'un cas de démo
  différentiel, dans le bloc `if __name__ == "__main__":`)

**Interfaces:**
- Consomme : `render()` (fonction existante, inchangée),
  `_positionner_amplificateur_differentiel` (Task 1, indirectement via le
  registre).
- Produit : rien pour d'autres tâches — dernière tâche du plan.

- [ ] **Step 1: Étendre le bloc de démo**

Dans `tools/render_boardsch_layout.py`, juste après le bloc existant qui
écrit `disposition_ampli_inverseur.png` (après la ligne
`print(f"Rendu ecrit : {OUT / 'disposition_ampli_inverseur.png'}")`, avant
le commentaire `# Chemin carte scannee (ecrire_groupes)...`), ajouter :

```python
    # Amplificateur différentiel (nouvellement migré) : vérifie les 4
    # lignes empilées (Zf haut / AOP+Z1 / Z3 / Zg bas).
    comps_diff = [
        Component("U1", "U", {"IN+": "NET_INPLUS", "IN-": "NET_INMOINS",
                              "OUT": "NET_OUT", "V+": "VCC", "V-": "GND"}),
        Component("R1", "R", {"1": "NET_INMOINS", "2": "NET_IN1"}),
        Component("R2", "R", {"1": "NET_OUT", "2": "NET_INMOINS"}),
        Component("R3", "R", {"1": "NET_INPLUS", "2": "NET_IN2"}),
        Component("R4", "R", {"1": "NET_INPLUS", "2": "GND"}),
    ]
    resultats_diff = match_patterns(build_graph(comps_diff))
    xml_diff = components_to_xml(comps_diff, resultats_diff)
    render(xml_diff, OUT / "disposition_ampli_differentiel.png")
    print(f"Rendu ecrit : {OUT / 'disposition_ampli_differentiel.png'}")
```

- [ ] **Step 2: Regenerer et inspecter**

Run: `PYTHONUTF8=1 python tools/render_boardsch_layout.py`

Puis lire (outil Read, pas juste lister) le fichier
`tools/_renders/disposition_ampli_differentiel.png` genere, et confirmer
visuellement : 4 lignes horizontales empilees, dans l'ordre de haut en bas
Zf (R2) / AOP(U1)+Z1(R1) / Z3(R3) / Zg(R4), toutes alignees verticalement
sur la colonne de l'AOP a droite (Z1 seul a gauche, sur la ligne de
l'AOP). Aucune rotation visible (angle=0 partout).

- [ ] **Step 3: Commit**

```bash
git add tools/render_boardsch_layout.py
git commit -m "test(disposition): ajoute un rendu visuel pour l'amplificateur differentiel"
```

Note : ne pas committer les PNG regeneres (`tools/_renders/` est
git-ignore, comme pour les chantiers precedents sur ce meme fichier).
