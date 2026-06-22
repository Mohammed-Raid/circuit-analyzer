# Pilote — Ampli inverseur affiché « AOP + Zin/Zf cliquables + gain »

Date : 2026-06-22
Branche : `rewrite-simple`

## Contexte

Le boss a validé l'étape impédances. But final : afficher les montages actifs
(AOP, transistors) comme **composant principal + blocs Z dépliables** (clic sur une
Z → détail R/L/C en série/parallèle). Voir [[directive-focus-impedances]].

État réel du code (exploré 2026-06-22) :
- La **détection AOP marche déjà** : `detecteur.py::analyser` tourne sur le graphe
  **réduit** ; les détecteurs AOP matchent avec `inclure_z=True`, donc un ampli dont
  l'entrée/contre-réaction est un **composite** (`Zf = R1+R2`, `R//C`…) est reconnu.
- **Manque côté dessin** : `_draw_inverting_amp` dessine `Rin`/`Rf` en résistances
  fixes (ref brute), pas en **blocs Z dépliables**. `show_circuit` ne câble aucun
  clic, et `_make_fig` ne fait pas remonter de zones cliquables.
- Pas de **gain** affiché.

Ce pilote établit, sur **l'ampli inverseur seul**, le motif réutilisable
« AOP + blocs Z cliquables + gain », à répliquer ensuite aux autres montages.

## Périmètre

- **Dans le périmètre** : ampli inverseur uniquement. Enrichir sa détection
  (impédances structurées + gain), redessiner en AOP + Zin/Zf (boîtes Z cliquables),
  câbler le clic dans `show_circuit` (drill-down série/parallèle existant), gain
  symbolique `Av = −Zf/Zin`.
- **Hors périmètre** : les 8 autres montages AOP, les transistors, le gain
  **numérique** (réutiliser `evaluer_impedance` plus tard), le rapport texte.

## Composants

### 1. `detecteur.py::detecter_amplificateur_inverseur` — match enrichi (pur)

Aujourd'hui le match = `{circuit_type, components:[U, rf…, rin…], nodes}`. Le détecteur
tourne sur le graphe réduit : l'arête IN-↔OUT et l'arête IN-↔entrée portent `refs`
(refs réelles) + `composition`. On ajoute :

```
match['impedances'] = {
  'Zin': {'refs': [...], 'composition': '<expr>', 'nodes': (entree_neg, entree_src)},
  'Zf' : {'refs': [...], 'composition': '<expr>', 'nodes': (entree_neg, sortie)},
}
match['gain'] = '−Zf/Zin'
```

`refs`/`composition` lus directement sur l'arête réduite (indépendant de
`expandre_composites`). `components` reste inchangé (anti-vol + chips OK). Quand
l'entrée a plusieurs résistances (cas sommateur), ce détecteur ne s'applique pas
(inchangé) — l'inverseur exige exactement une entrée et une contre-réaction.

### 2. `gui/circuit_viewer.py::_draw_inverting_amp` — dessin en blocs Z

Lit `result['impedances']`. Dessine :
- AOP (`elm.Opamp`), entrée IN+ à la masse.
- **Zin** : `elm.ResistorIEC` de l'entrée vers IN-, label `Zin` + `formater_expr(composition)`.
- **Zf** : `elm.ResistorIEC` en contre-réaction IN-→OUT, label `Zf` + composition.
- Étiquette **`Av = −Zf/Zin`** sous le schéma.
- Pour chaque bloc Z, **ajoute un hitbox** `(x0,x1,y0,y1, refs, composition)` à
  `d._z_hitboxes` (voir plumbing). Le label affiché reste `Zin`/`Zf` même si
  l'impédance est un seul composant (clic → détail de ce composant).

Repli : si `result` n'a pas d'`impedances` (ancien match), garder le dessin actuel
(résistances) pour ne rien casser.

### 3. Plumbing du clic (non invasif)

- `_make_fig` : avant d'appeler le drawer, `d._z_hitboxes = []` ; après,
  `fig._z_hitboxes = list(getattr(d, '_z_hitboxes', []))`. Les drawers existants ne
  touchent pas `d._z_hitboxes` → liste vide → aucune régression.
- `show_circuit(result, comp_info, parent=None, graph=None)` : nouveau paramètre
  `graph`. Après création du canvas, câbler
  `canvas.mpl_connect("button_press_event", _on_click)` ; `_on_click` lit
  `getattr(fig, "_z_hitboxes", [])` et appelle
  `show_dipole_detail(refs, composition, graph, comp_info, popup)` (drill-down
  série/parallèle déjà en place). Si `graph is None`, pas de clic (sûr).
- Site d'appel `gui/tab_analyze.py` : passer `graph=self._graph` à `show_circuit`.

### 4. Démo

Si aucun ampli inverseur à `Zf` composite n'existe dans `circuits_industriels`, en
générer un via `generer_xml` (AOP + Rin + Zf = R1+R2 en série) pour démontrer le clic.

## Gestion des cas limites

- Impédance d'un seul composant : boîte `Zin`/`Zf` quand même, clic → détail du
  composant seul. Cohérent.
- Match sans `impedances` (autre drawer, ancien chemin) : `_make_fig` →
  `fig._z_hitboxes` vide ; `_draw_inverting_amp` retombe sur le dessin résistances.
- `graph is None` dans `show_circuit` : pas de handler de clic (pas de crash).

## Tests

`tests/test_detecteur.py` (ou fichier existant des détecteurs) :
- ampli inverseur à `Zf = R1+R2` (R1, R2 en série entre IN- et OUT), `Rin` simple →
  le match porte `impedances['Zf']` avec `set(refs) == {R1,R2}` et composition
  contenant « + », `impedances['Zin']` avec le Rin, et `gain == '−Zf/Zin'`.

`tests/test_circuit_viewer.py` (ou test viewer existant) :
- `_make_fig` sur ce match (drawer inverseur) → `fig._z_hitboxes` de longueur 2,
  chaque hitbox au format `(x0,x1,y0,y1,refs,composition)`.

Suite complète verte.

## Hors périmètre (suite de la phase)

- Répliquer le motif aux autres montages AOP (non-inverseur, intégrateur,
  dérivateur, sommateur, différentiel, Schmitt, comparateur, suiveur).
- Gain **numérique** : |Av| et phase à une fréquence via `evaluer_impedance`.
- Transistors. Rapport texte enrichi (gain dans le rapport).
