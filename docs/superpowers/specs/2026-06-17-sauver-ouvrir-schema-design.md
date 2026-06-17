# Design — Sauvegarder / ouvrir un schéma + import dans l'éditeur

**Date :** 2026-06-17
**Portée :** format de projet `.circ` (natif) **et** import `.xml`/netlist dans l'éditeur. Validé « les deux d'un coup ».

## Problème

L'éditeur ne sait ni enregistrer ni rouvrir un dessin : fermer l'app perd tout. Et il n'existe aucun
chemin pour éditer visuellement un `.xml`/netlist existant (analyse et dessin sont à sens unique).

## Format `.circ`

JSON sérialisant exactement l'état de l'éditeur :

```json
{ "format": "circ", "version": 1,
  "components": [{"id":1,"ref":"R1","type":"R","value":"10k","cx":120,"cy":120,"rotation":0}],
  "wires": [{"from_comp_id":1,"from_pin":"2","to_comp_id":2,"to_pin":"1"}],
  "counters": {"R":1}, "next_id": 3 }
```

## Architecture

### Nouveau module `gui/schematic_io.py` (logique pure, testable sans Tk)

- `editor_to_dict(comps, wires, counters, next_id) -> dict` : produit le dict `.circ`.
- `build_from_components(composants, defs) -> dict` : convertit une liste de `Composant`
  (`lire_netlist`/`lire_xml`) en **ce même format**. Retourne aussi une clé `_report`
  (`ignored_components`, `dropped_pins`). L'import et le natif convergent vers un seul chemin de
  chargement.

### Éditeur (`SchematicEditor`)

- `to_dict()` → délègue à `editor_to_dict`.
- `load_dict(d)` → valide `format`/`version`, vide l'état, reconstruit `_comps`/`_wires`/
  `_counters`/`_next_id`, redessine. Ignore composants de type inconnu et fils dont une broche
  n'existe pas dans `self._defs`. Empile l'annulation si un dessin était présent (l'ouverture est
  annulable par Ctrl+Z).

### Onglet Schéma (`tab_draw`)

- Deux boutons dans la barre du bas : **📂 Ouvrir** et **💾 Enregistrer** (`filedialog`).
- `_save_circuit()` : `asksaveasfilename(defaultextension=".circ")` → JSON de `editor.to_dict()`.
- `_open_circuit()` : `askopenfilename` acceptant `.circ` / `.xml` / `.txt .sp .cir .net`.
  - `.circ` → `json.load` → `editor.load_dict`.
  - sinon → `lire_xml` (xml) ou `lire_netlist` → `build_from_components(defs)` → `editor.load_dict`.
  - Canvas non vide → confirmation avant écrasement.
  - `_report` non vide → message récapitulatif (composants/broches ignorés).

## Reconstruction à l'import (`build_from_components`)

1. **Filtrage** : un composant de type absent de `defs` (ou GND/VCC) est ignoré (→ `_report`).
2. **Placement en grille** déterministe : colonnes = ⌈√n⌉, pas 200×160, aligné sur la grille (20).
3. **Fils depuis les nœuds** : pour chaque broche connue (présente dans `defs[type]["pins"]`,
   sinon `dropped_pins += 1`), on indexe `nœud → [(id, broche)]`.
   - **Nœud signal** : broches reliées en chaîne (n−1 fils).
   - **Nœud `GND`/`VCC`** (`is_gnd`/`is_power`) : un **symbole GND/VCC dédié** créé près de chaque
     broche, relié par un fil (convention schématique, évite une étoile géante).

## Gestion d'erreurs

- `.circ` corrompu / version inconnue → `ValueError` clair, **dessin courant préservé** (validation
  avant toute mutation).
- Type inconnu / broche inconnue → ignoré et compté dans `_report`.
- Fichier illisible → message d'erreur, pas de plantage.

## Tests (headless, sans Tk)

- Round-trip : `editor_to_dict(...)` → `load_dict` reconstruit les mêmes composants/fils
  (test via instanciation Tk sautée sans affichage, ou validation pure du dict).
- `build_from_components` : 2 composants sur un nœud → 1 fil ; broche sur `GND` → symbole GND + fil ;
  broche inconnue (`V+` d'un U) → comptée dans `dropped_pins` ; type inconnu → `ignored_components`.
- Validation : dict sans `format` → `ValueError`.
- Les 343 tests existants restent verts.

## Hors périmètre

- Placement « joli » automatique (on reste en grille — rendu à réorganiser à la main).
- Broches `V+`/`V-` des AOP (l'éditeur n'a que 3 broches sur `U` — limite connue, connexions ignorées).
