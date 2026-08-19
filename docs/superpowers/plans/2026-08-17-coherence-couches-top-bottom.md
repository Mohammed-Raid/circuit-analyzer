# Cohérence des couches Top/Bottom — Implementation Plan

**Goal:** Avertir (jamais bloquer) quand un fil relie directement (sans
via) deux composants sur des couches Top/Bottom différentes — impossibilité
physique aujourd'hui invisible pour l'analyseur.

**Architecture:** Helper `_couche_de(elem)` + un test additionnel dans la
boucle des fils de `lire_xml`, juste après `unir(bf, bl)`. Voir design :
[[2026-08-17-coherence-couches-top-bottom-design]].

## Global Constraints

- Aucun footer Claude dans les commits ; jamais `git add -A`.
- Ne jamais avertir sur un bout via/jonction non résolu, ni sur un fichier
  sans `<Top>`/`<Bottom>` (dialecte ancien).

---

### Task 1 : `_couche_de` + avertissement dans `lire_xml`

**Files:** `circuit_analyzer/xml.py`, `tests/test_eretro_nouveau_format.py`.

- [ ] Étendre `_item`/`_fil` dans les fixtures de test pour accepter un
  paramètre optionnel `top` (`True`/`False`/`None`) → émet
  `<Top>.../<Bottom>...` seulement si fourni (non-régressif).
- [ ] Cas : A Top + B Top + fil Top → 0 warning. A Top + B Bottom + fil Top
  (aucun via) → 1 warning, connexité toujours unie. Même scénario AVEC un
  via entre les deux → 0 warning.
- [ ] Lancer, vérifier l'échec (pas encore implémenté).
- [ ] Implémenter `_couche_de` + le check dans `lire_xml` (voir design pour
  le code exact).
- [ ] Lancer, vérifier le succès. Suite complète `pytest tests/ -q` : zéro
  régression (comparer au relevé du chantier précédent : mêmes 15 échecs
  préexistants, jamais plus).

### Task 2 : Bout en bout avec la vraie appli

**Files:** `SizeTraceHarness/Program.cs` (nouveau cas, même patron que
`via-real-app-e2e`).

- [ ] Construire avec le VRAI `Form1` : composant A posé `top: true`,
  composant B posé `top: false`, fil direct A→B (PAS de via cette fois).
  Sauvegarder via le même bloc `SeveXMLFile.SaveData` que le chantier via.
- [ ] Lire le fichier réel avec le VRAI `lire_xml` Python, confirmer
  l'avertissement présent et le net toujours unifié (le fil continue de
  fonctionner électriquement, on avertit seulement).

## Fin de chantier

- [ ] `Statut` de la spec : `approuvé` → `livré`.
- [ ] Commit FR listant explicitement les fichiers touchés.
