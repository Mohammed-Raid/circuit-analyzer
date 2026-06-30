# Montages AOP restants — impédances Z cliquables

**Date:** 2026-06-24
**Statut:** conception validée

## Objectif

Donner aux 4 montages AOP restants le même traitement « 1 AOP + Z au clic » que les
5 déjà faits (inverseur, non-inverseur, suiveur, intégrateur, dérivateur) :
- **Différentiel** : 4 impédances cliquables
- **Sommateur** : Zf + N entrées cliquables
- **Bascule de Schmitt** : réseau d'hystérésis complet cliquable (Zf + autre patte IN+)
- **Comparateur** : pas d'impédance (boucle ouverte) → dessin propre uniquement

Directive boss : focus impédances, blocs Z dépliables autour de l'AOP, ne pas
gold-plater les réseaux passifs exotiques.

## Architecture (Approche A)

Séparation existante conservée : **le détecteur possède la topologie** (construit
des *blocs* d'impédance), **le drawer est du rendu pur**.

Un *bloc* d'impédance a la forme déjà en place :
```python
{'refs': [...], 'composition': 'R1+R2', 'nodes': (node_a, node_b)}
```

### Helper partagé `_z_box()` (gui/circuit_viewer.py)

Factoriser le dessin d'une boîte Z cliquable, aujourd'hui dupliqué inline dans
chaque drawer (4 sites) :

```python
def _z_box(d, p1, p2, name, bloc, ci, label_loc="top"):
    """Dessine une boîte Z (ResistorIEC bleue) de p1 à p2, étiquetée, et
    enregistre sa hitbox cliquable. Renvoie rien (effet de bord sur d)."""
```

Elle dessine `elm.ResistorIEC().at(p1).to(p2).color(_Z_EDGE).fill(_Z_FILL)
.label(_z_label(name, bloc, ci))` et append la hitbox
`(x_min, x_max, y_min, y_max, list(bloc["refs"]), bloc["composition"])` à
`d._z_hitboxes` (avec le padding actuel 0.5). Les drawers existants
(`_draw_aop_inverseur_zin_zf`, `_draw_aop_non_inverseur_zf_zg`) sont réécrits
pour l'utiliser — réduction nette de code, pas de changement visuel.

## Détecteurs (circuit_analyzer/detecteur.py)

Chaque détecteur ci-dessous, qui renvoie aujourd'hui des refs brutes via
`_voisins_de_type`, est réécrit pour construire des blocs en itérant les arêtes
(comme `detecter_amplificateur_inverseur` aux lignes 111-124).

### Différentiel
Émet `'impedances': {'Z1': bloc, 'Zf': bloc, 'Z3': bloc, 'Zg': bloc}` :
- `Z1` : source → IN−
- `Zf` : IN− → OUT (contre-réaction)
- `Z3` : source → IN+
- `Zg` : IN+ → GND
- `'gain': 'Zf/Z1 · (V2−V1)'`

### Sommateur
Émet `'impedances': {'Zf': bloc, 'Zin': [bloc, ...]}` :
- `Zf` : IN− → OUT
- `Zin` : liste des blocs d'entrée (chaque entrée → IN−)
- `'gain': '−Σ Zf/Zk'`

### Bascule de Schmitt (option b — réseau complet)
Aujourd'hui le détecteur ne capture que la patte OUT → IN+. On capture aussi
l'autre patte sur IN+ (vers la source d'entrée ou vers GND/réf). Émet
`'impedances': {'Zf': bloc, 'Zin': bloc}` :
- `Zf` : OUT → IN+ (contre-réaction positive)
- `Zin` : autre patte sur IN+ (signal d'entrée ou réf)
- `'gain': 'hystérésis ±Vsat·Zin/(Zin+Zf)'`

Si l'autre patte est absente, n'émettre que `Zf` (repli gracieux).

### Comparateur
Inchangé : aucune impédance. Continue de renvoyer `{circuit_type, components,
nodes}` sans clé `impedances`.

## Drawers (gui/circuit_viewer.py)

Chaque drawer modifié suit le motif de repli déjà en place
(`if result.get("impedances"): <dessin Z cliquable>; return` puis dessin
fixe R/C actuel conservé en fallback).

- `_draw_aop_differentiel(d, imp, ci)` — **nouveau** : pont 4 Z, toutes cliquables.
- `_draw_aop_sommateur(d, imp, ci)` — **nouveau** : bus d'entrées + Zf, toutes cliquables.
- `_draw_schmitt` — **modifié** : Zf + Zin cliquables quand `impedances` présent.
- `_draw_comparator` — **modifié** : dessin propre (IN+ signal / IN− REF / OUT),
  pas de Z cliquable.
- `_draw_differential_amp` / `_draw_summing_amp` — **modifiés** : délèguent aux
  nouveaux helpers quand `impedances` présent, sinon dessin fixe actuel.

Pas de changement à `_DRAWERS` : on modifie des fonctions déjà enregistrées.

## Tests

- `tests/test_detecteur_aop.py` : chaque détecteur émet les bons blocs
  (refs/composition/nodes) et la clé `gain`.
- `tests/test_circuit_viewer.py` : chaque drawer enregistre le bon nombre de
  hitboxes (4 différentiel, n+1 sommateur, 2 Schmitt, 0 comparateur).
- Démos XML sous `circuits_industriels/` : un fichier par montage, déclenchant
  la détection et le drill-down.

## Hors périmètre

- Réseaux passifs exotiques (directive boss).
- Comparateur : pas de Z, pas de drill-down.
- Aucune nouvelle dépendance ; matplotlib/schemdraw déjà en place.
