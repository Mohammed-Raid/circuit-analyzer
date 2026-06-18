# Plan 2c — Nettoyage des passifs nommés + fusibles transparents

**Contexte.** Le moteur Z (sous-projets 1, 2a, 2b) est branché : tout passif R/L/C
résiduel devient une « Impédance Z ». Les 7 détecteurs passifs nommés (filtre RC
passe-bas/haut, filtre LC, pont diviseur, condensateur de découplage, absorbeur RC,
fusible) sont déjà retirés de la chaîne d'analyse mais leur code mort subsiste dans
plusieurs fichiers. Directive chef : « Z générique seulement » + « le fusible ne sert
à rien, on peut le supprimer ». Ce plan supprime le code mort et corrige le report
des fusibles devenus transparents.

**Diodes conservées.** Le chef n'a pas tranché sur les circuits à diodes : on garde
`detecter_pont_redresseur`, `detecter_diode_roue_libre`, `detecter_diode_protection_esd`,
`detecter_redresseur_simple`, `detecter_detecteur_crete`.

## Tâches

### Tâche 1 — `detecteur.py`
Supprimer les 7 fonctions passives : `detecter_condensateur_decouplage`,
`detecter_filtre_rc_passe_bas`, `detecter_filtre_rc_passe_haut`, `detecter_filtre_lc`,
`detecter_pont_diviseur`, `detecter_absorbeur_rc`, `detecter_fusible`. Retirer leurs
branches dans `_enrichir`, leurs entrées dans `_CATEGORIES` et `NOMS_CIRCUITS`.
Conserver `detecter_impedances` et tous les détecteurs actifs/diodes.

### Tâche 2 — `patterns/basic_circuits.py`
Supprimer les 7 classes `Pattern` passives qui déléguaient à ces détecteurs.
Conserver `PontRedresseur`.

### Tâche 3 — `gui/circuit_viewer.py`
Supprimer les 7 drawers passifs (`_draw_rc_lowpass`, `_draw_rc_highpass`,
`_draw_lc_filter`, `_draw_voltage_divider`, `_draw_decoupling`, `_draw_snubber`,
`_draw_fuse`) et leurs entrées dans `_DRAWERS`.

### Tâche 4 — `gui/descriptions.py`
Supprimer les 7 descriptions passives.

### Tâche 5 — `drc.py`
Supprimer la règle morte « Pont diviseur déséquilibré » (le type n'est plus émis).
Conserver « AOP sans découplage » et « Aucun fusible sur VCC » (basées sur les types
de composants, toujours valides).

### Tâche 6 — `satellites.py`
Retirer `'Condensateur de découplage'` de `_ANNEXES` (type plus produit). Conserver
les annexes diodes.

### Tâche 7 — Suppression de `reduction.py`
Supprimer `circuit_analyzer/reduction.py`, `tests/test_reduction.py`,
`tests/test_reduction_integration.py`. Vérifier qu'aucun code de production ne
l'importe encore.

### Tâche 8 — Fusibles transparents non comptés comme « non classifiés »
`impedance.reduire()` enregistre sur le graphe réduit les refs de fusibles rendus
transparents (`reduit.graph['fusibles_transparents']`). `analyser()` les remonte sur
`ResultatsAnalyse.transparents`. `rapport.py` les exclut de la liste « non classifiés »
et les affiche dans une ligne dédiée « Fusibles ignorés (transparents) ».

### Tâche 9 — Vérification bout en bout
Suite complète verte + smoke test sur circuits industriels (aucun passif non
classifié, fusibles non listés comme non classifiés).
