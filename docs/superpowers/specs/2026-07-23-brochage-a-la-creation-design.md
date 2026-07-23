# Brochage positionné à la création d'un composant — Design

**Date :** 2026-07-23
**Statut :** design validé par le boss, en attente de relecture spec avant plan.

## Context (pourquoi)

Dans l'onglet « Composants » (`gui/tab_components.py`), créer un type revient à
saisir un **préfixe**, un **nom**, et une **pile de lignes de texte** — une par
broche. Le fichier `component_library.json` ne stocke donc qu'une **liste
ordonnée de noms** :

```json
"IC": {"name": "Circuit intégré", "pins": ["VCC", "IN", "OUT", "GND"]}
```

La géométrie n'est jamais du ressort de l'utilisateur : `_auto_def`
(`gui/schematic_editor.py:68`) l'invente à la pose — première moitié des broches
à gauche, seconde moitié à droite, dans l'ordre de saisie, boîte de 80 px. On ne
peut donc **pas** dire qu'une broche va en haut, en bas, ni la placer, ni
l'espacer. Un `VCC` finit à gauche et un `GND` à droite sans recours.

Limites concrètes du formulaire actuel :

| Impossible aujourd'hui | Cause |
|---|---|
| Choisir le **côté** d'une broche | Le format ne stocke aucune position |
| Broche en **haut / en bas** | `_auto_def` ne connaît que gauche/droite |
| Supprimer une broche **du milieu** | `_retirer_broche` ne retire que la dernière |
| **Réordonner** / **insérer** au milieu | Ajout en fin uniquement |
| **Voir** le résultat avant de poser | Aucun aperçu |

**But :** placer les broches **à la souris, à la création du type**, et que ce
brochage vaille partout où le type est utilisé.

## Décisions verrouillées (arbitrage boss, 2026-07-23)

| Question | Décision |
|---|---|
| Mode de saisie | **Mini-canevas** dans l'onglet : clic sur un bord = broche, glisser = déplacer |
| Ordre des broches (netlist) | **Ordre de pose**, réordonnable au glisser dans un bandeau |
| Nommage | **Double-clic** sur la broche → boîte de dialogue |
| Liste de saisie textuelle | **Remplacée** par le canevas |
| Taille de boîte | **Auto-ajustée** aux broches (pas de poignée) |

## Non-goals

- Pas de colonne de noms tabulable en parallèle du canevas (c'est la
  proposition écartée ; le canevas est le seul moyen de saisie).
- Pas de poignée de redimensionnement : la boîte s'ajuste seule.
- Pas de rôle/fonction par broche (le catalogue des puces réelles a son champ
  `fonctions` ; la bibliothèque perso ne l'aura pas en v1).
- Pas de symbole autre que le rectangle.
- Pas de zoom ni de défilement dans le canevas de l'onglet.
- **Aucun changement** pour l'analyseur : il ne lit que `pins`.

## Architecture

### 1. La source de vérité devient une LISTE de données

Aujourd'hui le brochage vit dans des **widgets** :
`self._pin_lignes: list[tuple[StringVar, CTkEntry]]`, lue par cinq méthodes.
Un canevas ne peut pas alimenter ça. On la remplace par :

```python
self._brochage: list[tuple[str, str, int]]   # [(nom, côté, décalage), …]
```

- `côté` ∈ `{"L", "R", "T", "B"}` ; `décalage` = distance signée, multiple du
  pas de grille, depuis le milieu de ce bord (même convention que le brochage
  libre de l'éditeur, spec `2026-07-23-brochage-libre-design.md`).
- **Pourquoi une liste et pas un dict :** l'ordre de pose **EST** la donnée
  demandée (netlist positionnelle + ordre des champs de la saisie rapide).
  Réordonner = permuter deux éléments. Un dict aurait imposé un champ « ordre »
  séparé à garder cohérent.
- Bénéfice collatéral : `_etat_courant` devient `tuple(self._brochage)`, donc
  l'anti-perte de saisie couvre **aussi** les côtés et les positions, gratuitement.

### 2. Nouveau widget `gui/pin_canvas.py`

```python
class PinCanvas(ctk.CTkFrame):
    def __init__(self, parent, on_change=None, hauteur=260)
    def charger(self, brochage: list, lecture_seule: bool = False)
    def brochage(self) -> list[tuple[str, str, int]]
```

Widget **autonome**, sans dépendance à l'éditeur de schéma. Il réutilise les
fonctions **pures** déjà livrées et testées dans `gui/schematic_symbols.py` :

| Réutilisé | Rôle |
|---|---|
| `geometrie_libre(pinout)` | côtés+décalages → boîte auto-ajustée + offsets absolus |
| `aimanter_bord(dx, dy, w, h, pas)` | position du clic → `(côté, décalage grille)` |
| `primitives(TYPE_LIBRE, defn, 0)` + `_tr_boite_libre` | dessin de la boîte à 4 bords |
| `AUTO_COLOR`, `BOITE_MIN_W/H` | couleur et taille plancher |

**On n'embarque PAS `SchematicEditor`** : il traîne palette, câblage, zoom, pan,
undo et export — rien d'utile ici. Le canevas de l'onglet a un repère fixe
(échelle 1, origine au centre du canevas), ce qui supprime tout le code de
transformation monde↔écran.

### 3. Bandeau d'ordre

Sous le canevas, une rangée de pastilles dans l'ordre de `self._brochage` :

```
Ordre (netlist) :  [VCC][IN1][IN2][OUT1][OUT2][GND]
```

Glisser une pastille la déplace dans la liste. Le canevas ne bouge pas (les
positions sont indépendantes de l'ordre) — seul l'ordre de la netlist change.

### 4. Format de bibliothèque : champ additif

```json
"U2": {
  "name": "Ampli double",
  "pins": ["VCC", "IN1", "IN2", "OUT1", "OUT2", "GND"],
  "brochage": {"VCC": ["T", 0],    "IN1": ["L", -20], "IN2": ["L", 20],
               "OUT1": ["R", -20], "OUT2": ["R", 20], "GND": ["B", 0]}
}
```

- `pins` = `[nom for nom, _, _ in self._brochage]` — **inchangé dans sa forme et
  son ordre**. L'analyseur, `saisie.py:_broches_du_type` et `to_netlist`
  continuent de ne lire que lui : **zéro impact**.
- `brochage` absent ⇒ comportement actuel (`_auto_def` moitié/moitié). Un
  fichier existant se relit tel quel, et un type créé par une version
  antérieure reste utilisable.
- `brochage` est un **dict** dans le fichier (lisible, diff-able) et une
  **liste** en mémoire (l'ordre vient de `pins`) — la conversion se fait au
  chargement/à l'écriture.

### 5. `_auto_def` honore le brochage

`gui/schematic_editor.py:68` :

```python
def _auto_def(name: str, pins: list, brochage: dict | None = None) -> dict:
    if brochage:
        d = geometrie_libre({n: tuple(v) for n, v in brochage.items()})
        d["label"] = name
        return d
    ...  # répartition moitié/moitié actuelle, inchangée
```

et `_compute_defs` passe `val.get("brochage")`. Trois lignes, non régressif par
construction (le chemin actuel n'est pris que si `brochage` est absent).

## Interactions

**Canevas** (repère fixe, grille visible, échelle 1) :

| Geste | Effet |
|---|---|
| Clic sur un bord, à vide | Ajoute une broche, nommée du **plus petit entier ≥ 1 libre**, aimantée bord+grille, **ajoutée en FIN** de `self._brochage` |
| Glisser une broche | La fait coulisser ; aimantation bord + grille ; l'ordre ne change pas |
| Double-clic sur une broche | Renomme (`simpledialog.askstring`) ; refuse vide et doublon |
| Broche sélectionnée + `Suppr` | La retire de `self._brochage` |

**Bandeau** : glisser une pastille → permutation dans `self._brochage`.

Chaque mutation appelle `on_change(brochage)`, qui met à jour l'état du
formulaire (donc l'anti-perte de saisie et le bandeau).

**Modes du formulaire** (`nouveau | edition | lecture`) :
- `nouveau` : canevas **vide**, 0 broche (aujourd'hui : une ligne vide).
- `edition` (type perso) : chargé depuis `brochage` s'il existe, **sinon amorcé**
  en projetant la géométrie `_auto_def` actuelle sur les bords via
  `aimanter_bord` — aucune broche n'est perdue.
- `lecture` (type intégré) : canevas **non éditable** (aucun clic ne mute), comme
  le reste du formulaire.

## Impact sur `gui/tab_components.py`

| Méthode (ligne) | Changement |
|---|---|
| `__init__` (38) | `self._pin_lignes` → `self._brochage: list` |
| `_build` (113-130) | La carte « Broches » (lignes + 2 boutons) devient `PinCanvas` + bandeau |
| `_remplir_formulaire` (205) | Prend `brochage` en plus de `broches` ; amorce si absent |
| `_afficher_perso` (188) | Passe `v.get("brochage")` |
| `_afficher_integre` (200) | Passe `None` + `lecture_seule=True` |
| `_afficher_nouveau` (176) | Brochage **vide** au lieu de `['']` |
| `_etat_courant` (226) | `tuple(self._brochage)` |
| `_dupliquer` (347) | Copie `self._brochage` (deepcopy de la liste) |
| `_sauvegarder` (377-391) | `pins` dérivé du brochage ; écrit `brochage` |
| `_ajouter_broche` / `_retirer_broche` (251, 275) | **Supprimées** (remplacées par le canevas) |

`_load` et `_ecrire` (JSON brut) : **inchangés**.

## Tests

Fixture Tk existante (`ctk.CTk()` + `pytest.skip` sans display), API interne
appelée directement, comme le fait déjà `tests/test_schematic_editor.py`.

**`tests/test_pin_canvas.py`** (widget seul) :
1. Canevas vide → `brochage() == []`, boîte à la taille plancher.
2. Clic sur le bord gauche → une broche `"1"`, côté `L`, décalage multiple de 20.
3. Deuxième clic → `"2"`, **ajoutée en fin** de liste.
4. Suppression de `"1"` puis ajout → recycle `"1"` et l'ajoute **en fin**.
5. Glisser une broche → côté/décalage mis à jour, **ordre inchangé**.
6. Glisser au-delà du coin → la boîte grandit.
7. Renommage → refuse vide et doublon ; le reste de la liste est intact.
8. `lecture_seule=True` → un clic ne mute rien.
9. `charger()` puis `brochage()` → aller-retour fidèle (ordre compris).
10. Réordonnancement → permutation, positions inchangées.

**`tests/test_tab_components.py`** (intégration onglet) :
11. Sauvegarde d'un type broché → `pins` **dans l'ordre de pose** et `brochage`
    cohérent dans le JSON.
12. Type sans broche → refus « Au moins une broche requise » (règle conservée).
13. Réouverture d'un type perso **avec** `brochage` → canevas identique.
14. Réouverture d'un type perso **sans** `brochage` (rétro-compat) → broches
    amorcées sur les bords, aucune perdue.
15. Type intégré → canevas en lecture seule.
16. Anti-perte de saisie : déplacer une broche rend le formulaire « sale ».
17. Duplication → brochage cloné, l'original n'est pas modifié.

**Non-régression :**
18. `_auto_def` sans `brochage` → géométrie moitié/moitié **identique** à
    aujourd'hui (les suites `test_schematic_editor.py`, `test_schematic_io.py`
    restent vertes sans modification).
19. `saisie.py:_broches_du_type` rend les broches **dans l'ordre** du fichier.
20. Un `component_library.json` sans `brochage` se charge sans erreur.

## Risques

| Risque | Parade |
|---|---|
| Le glisser-réordonner de pastilles Tk est le morceau d'UI le moins trivial | Tâche isolée, testée par l'API interne (`_reordonner(i, j)`) et non par la souris |
| Perte de la saisie rapide au clavier pour un composant à 40 broches | Compromis **assumé** par le boss (choix du canevas contre la liste), signalé deux fois |
| `_pin_lignes` lue par 5 méthodes : un oubli casse l'anti-perte silencieusement | Supprimer complètement l'attribut ; `grep -n "_pin_lignes"` doit ne **rien** rendre |
| Écriture accidentelle de `component_library.json` en test | Les tests écrivent dans un `tmp_path` via monkeypatch de `chemin_bibliotheque` — **jamais** le vrai fichier (règle permanente : il n'est jamais committé) |

## Preuve visuelle (exigence permanente)

PNG rendus **et inspectés** : (1) un type à broches sur les 4 bords dans
l'onglet, (2) le même type **posé dans l'éditeur** — il doit y apparaître avec
le brochage choisi, pas la répartition moitié/moitié, (3) un type existant
**sans** `brochage`, inchangé. Puis suppression des PNG (jamais committés).
