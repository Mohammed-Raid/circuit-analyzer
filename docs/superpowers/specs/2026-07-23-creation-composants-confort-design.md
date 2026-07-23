# Création de composants : confort et options — Design

**Date :** 2026-07-23
**Statut :** design validé par le boss, en attente de relecture spec avant plan.
**Suite de :** `2026-07-23-brochage-a-la-creation-design.md` (canevas de brochage, livré).

## Context (pourquoi)

Le canevas de brochage donne la liberté de **placement**, mais créer un
composant reste lent et pauvre en informations :

| Gêne | État actuel |
|---|---|
| Partir de zéro est long | Un boîtier DIP-8 = 8 clics puis 8 double-clics |
| Renommer est pénible | Une fenêtre modale par broche |
| Pas de valeur par défaut | Un type perso se pose toujours avec une valeur vide |
| Pas de rôle de broche | Rien ne distingue une alimentation d'une sortie |
| Taille subie | La boîte s'ajuste seule, sans réglage possible |

Le boss a demandé les quatre : **plus de liberté, plus d'options, plus facile.**

## Deux clés existent déjà — on les branche, on ne les invente pas

- **`default_value`** est déjà une clé de premier rang de la bibliothèque
  (`circuit_analyzer/composant.py:26`) et déjà lue par la saisie rapide
  (`circuit_analyzer/saisie.py:58`). Seuls manquent : le champ dans l'onglet, et
  sa propagation par `_auto_def` (qui renvoie `""` en dur).
- **`fonctions`** est déjà **dessiné** par `_tr_boite`
  (`gui/schematic_symbols.py:204`, qui compose « n FONCTION ») et déjà
  transporté par `ModeleSaisie.ajouter(..., fonctions=…)`. Ranger les rôles de
  broche sous cette clé les fait apparaître dans le symbole quasiment sans
  code de rendu neuf.

## Non-goals

- Pas de symbole autre que le rectangle.
- Pas de rôle libre en texte : une liste fermée (voir §C), pour rester lisible
  et exploitable plus tard.
- Pas de modèles exotiques (SOIC, QFP, BGA…) : DIP + bornier + connecteur
  couvrent les cartes réelles du projet.
- **Aucun changement pour l'analyseur** : il ne lit que `pins`, dont l'ordre est
  préservé.

## A. Modèles de boîtier

Fonction **pure**, dans `gui/schematic_symbols.py` :

```python
def modele_brochage(modele: str, n: int = 0) -> list[tuple[str, str, int]]
```

| Modèle | Disposition |
|---|---|
| `DIP-8`, `DIP-14`, `DIP-16` | `1..n/2` à **gauche de haut en bas**, `n/2+1..n` à **droite de bas en haut** (convention DIP réelle, celle que `def_puce` applique déjà aux puces du catalogue) |
| `Bornier 2`, `Bornier 3`, `Bornier 4` | toutes à gauche, `1..n` de haut en bas |
| `Connecteur N` | même disposition, mais `n` est saisi (2 à 64) |

Bornier et connecteur produisent la **même** disposition : les borniers sont
simplement les trois tailles courantes en accès direct, sans passer par le champ
`n`. `n` pair et ≥ 4 est **exigé** pour un DIP (un DIP-7 n'existe pas) ; une
valeur invalide lève `ValueError` et l'UI refuse de poser en l'annonçant.

Décalages multiples du pas de grille, centrés sur le bord. Le résultat est une
liste ordonnée `(nom, côté, décalage)` : **l'ordre du modèle devient l'ordre de
la netlist**, ce qui est exactement la numérotation du boîtier réel.

**UI** (onglet Composants, au-dessus du canevas) : menu déroulant + champ `N`
(actif seulement pour Bornier/Connecteur) + bouton **Poser**. Si le brochage
courant n'est pas vide, une confirmation est demandée avant remplacement —
poser un modèle est destructif et doit le dire.

## B. Saisie rapide

**B1 — Champ de nom lié à la sélection.** Sous le canevas, un champ unique
affiche le nom de la broche sélectionnée. **`Entrée` valide et sélectionne
automatiquement la suivante** dans l'ordre du bandeau. Nommer huit broches
devient une seule séquence au clavier, sans aucune fenêtre modale. Le
double-clic (modale) reste comme raccourci pour une retouche isolée.

Règles de refus inchangées (nom vide ou déjà pris → refus signalé au statut, la
sélection ne bouge pas). Après la dernière broche, l'avance boucle sur la
première.

**B2 — Pose groupée.** Bouton **« + [N] broches à [côté] »** : pose `N` broches
d'un coup sur le côté choisi, espacées d'un pas de grille et centrées, nommées
par la numérotation automatique existante, **ajoutées en fin** de la liste.

## C. Options du composant

**C1 — Valeur par défaut.** Champ texte dans le formulaire, entre « Nom
complet » et « Broches ». Écrit sous `default_value`. Consommateurs déjà en
place : `saisie.py:58` et, via `_auto_def`, la pose dans l'éditeur
(`_place_at` lit `defn["default_value"]`).

**C2 — Rôle par broche.** Dans le bandeau d'ordre, chaque pastille gagne un
menu de rôle. Liste fermée : *(vide)*, `Alim`, `Entrée`, `Sortie`, `Masse`,
`E/S`. Écrit sous `fonctions` (`{nom: rôle}`, entrées vides omises).

`_tr_boite_libre` apprend à composer « nom RÔLE » comme `_tr_boite` le fait
déjà. La largeur de boîte tient compte du libellé **rôle compris**, sinon on
retombe sur le chevauchement corrigé plus tôt aujourd'hui.

## D. Taille manuelle

Champs **Largeur** / **Hauteur** + case **« Ajuster automatiquement »** (cochée
par défaut ; les champs sont désactivés tant qu'elle est cochée).

```python
def geometrie_libre(pinout, w_mini=None, h_mini=None) -> dict
```

Les valeurs saisies sont un **plancher**, jamais un plafond : la boîte fait au
moins la taille demandée, et l'auto-ajustement continue de garantir que broches
et libellés tiennent. **Décision assumée** — sans ce garde-fou on peut
fabriquer un composant dont les broches débordent du cadre, ce qui produit un
schéma faux. Écrit sous `boite: {"w": …, "h": …}` ; absent quand la case est
cochée.

## Format de bibliothèque — additif de bout en bout

```json
"U2": {
  "name": "Ampli double",
  "pins": ["VCC", "IN1", "OUT1", "GND"],
  "default_value": "LM358",
  "brochage":  {"VCC": ["T", 0], "IN1": ["L", -20],
                "OUT1": ["R", -20], "GND": ["B", 0]},
  "fonctions": {"VCC": "Alim", "GND": "Masse"},
  "boite":     {"w": 120, "h": 160}
}
```

Toute clé absente ⇒ comportement actuel. Un `component_library.json` écrit
avant ce chantier se relit sans erreur et rend à l'identique.

## Impact

| Fichier | Changement |
|---|---|
| `gui/schematic_symbols.py` | `modele_brochage` (neuf) ; `geometrie_libre(+w_mini,+h_mini)` ; largeur tenant compte du rôle ; `_tr_boite_libre` affiche « nom RÔLE » |
| `gui/pin_canvas.py` | pose groupée, champ de nom chaîné, menus de rôle dans le bandeau, `charger()` accepte rôles + taille |
| `gui/tab_components.py` | menu Modèle + Poser, champ Valeur par défaut, Largeur/Hauteur + case auto ; `_remplir_formulaire` et `_sauvegarder` transportent les nouvelles clés |
| `gui/schematic_editor.py` | `_auto_def` propage `default_value`, `fonctions`, `boite` |

`circuit_analyzer/` : **aucune modification**.

## Tests

**Fonctions pures** (`tests/test_schematic_symbols.py`) : DIP-8 respecte la
convention (gauche haut→bas, droite bas→haut) ; bornier/connecteur tout à
gauche ; `n` impair refusé pour un DIP ; `w_mini`/`h_mini` agrandissent ;
plancher **jamais** en dessous du besoin réel des broches ; largeur tenant
compte du rôle ; « nom RÔLE » présent dans les primitives.

**Canevas** (`tests/test_pin_canvas.py`) : pose groupée ajoute N broches en fin
sur le bon côté ; le nom chaîné avance d'une broche et boucle ; refus (vide,
doublon) ne fait pas avancer ; rôle enregistré et restitué ; aller-retour
`charger`/`brochage` fidèle rôles et taille compris.

**Onglet** (`tests/test_tab_components.py`) : Poser un modèle remplit le
brochage ; confirmation demandée si non vide ; `default_value`, `fonctions` et
`boite` écrits dans le JSON ; relecture fidèle ; type intégré toujours en
lecture seule.

**Non-régression** : un type sans les nouvelles clés rend **exactement** comme
aujourd'hui ; `_auto_def` sans `brochage` garde la répartition moitié/moitié ;
`ModeleSaisie._broches_du_type` rend les broches dans l'ordre ; suite existante
verte sans modification d'assertion.

**Isolation** : les tests écrivent dans un `tmp_path` (monkeypatch de
`chemin_bibliotheque`) — le vrai `component_library.json` n'est jamais touché
ni committé.

## Risques

| Risque | Parade |
|---|---|
| Poser un modèle écrase un brochage en cours | Confirmation explicite avant remplacement |
| Le champ chaîné et le double-clic divergent | Les deux appellent `_renommer` ; le chaînage n'ajoute que l'avance de sélection |
| Le rôle rallonge le libellé et fait déborder | La largeur intègre le rôle (test dédié) |
| Plancher de taille mal compris | Libellé UI explicite (« taille minimale ») + test « jamais en dessous du besoin » |

## Preuve visuelle (exigence permanente)

PNG rendus **et inspectés** : (1) l'onglet après « Poser DIP-8 » puis renommage
chaîné, (2) le composant **posé dans l'éditeur** avec ses rôles affichés et sa
taille imposée, (3) un type d'avant le chantier, inchangé. Puis suppression des
PNG (jamais committés).
