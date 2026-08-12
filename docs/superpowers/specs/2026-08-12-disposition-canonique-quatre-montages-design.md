# Disposition canonique — 4 montages supplémentaires — Design

**Date :** 2026-08-12
**Statut :** design validé en conversation, prêt pour le plan d'implémentation.

**Suite de :**
[2026-08-10-disposition-canonique-montages-detectes-design.md](2026-08-10-disposition-canonique-montages-detectes-design.md)
(disposition canonique côté `generer_xml`, ampli inverseur) et
[2026-08-11-disposition-canonique-cartes-scannees-design.md](2026-08-11-disposition-canonique-cartes-scannees-design.md)
(extension au chemin patch-en-place `ecrire_groupes`). Ce chantier étend
juste la LISTE de montages migrés — même architecture, aucun changement
d'infrastructure.

## Contexte (pourquoi)

Un fichier de test réel (`test_pid_3.xml`, un correcteur PID) contient 5
montages AOP détectés — Amplificateur différentiel, Amplificateur
sommateur, Intégrateur, Dérivateur, Suiveur de tension — dont AUCUN n'est
« Amplificateur inverseur (AOP) », le seul migré jusqu'ici. Résultat :
aucun n'obtient de disposition canonique, seul le groupage s'applique —
comportement correct par conception (repli fail-soft), mais qui laisse la
majorité des montages réels sans la disposition canonique promise.

## Décisions verrouillées

| Question | Décision |
|---|---|
| Quels montages migrer ? | Amplificateur différentiel, Amplificateur sommateur, Intégrateur, Dérivateur. Le Suiveur de tension (un seul composant, pas d'impédance) n'a pas de disposition à calculer — hors périmètre, rien à faire pour lui. |
| Sommateur / Intégrateur / Dérivateur : nouveau code ? | NON. Vérifié dans `detecteur.py` : les trois ont exactement la forme `impedances: {'Zin': ..., 'Zf': ...}` (Sommateur : `Zin` est une LISTE de blocs, déjà géré par `_positionner_amplificateur_inverseur` — testé dès le premier chantier). Les trois se contentent d'un enregistrement dans `_POSITIONNEURS_PAR_MOTIF` pointant vers la fonction EXISTANTE, sans la modifier. |
| Amplificateur différentiel : nouveau code ? | OUI. Forme différente : `impedances: {'Z1': ..., 'Zf': ..., 'Z3': ..., 'Zg': ...}` (detecteur.py:668) — deux chemins d'entrée (IN− et IN+), pas un seul. Nouvelle fonction `_positionner_amplificateur_differentiel`. |
| Disposition canonique du différentiel | AOP au centre. Z1 (entrée IN−) à gauche, sur la même ligne que l'AOP. Zf (contre-réaction) au-dessus — même convention que l'ampli inverseur. Z3 (entrée IN+) à gauche, une ligne EN DESSOUS de l'AOP. Zg (référence masse du IN+) encore en dessous, alignée sous l'AOP. Quatre lignes empilées : Zf (haut) → AOP+Z1 → Z3 → Zg (bas). |
| S'applique à quel(s) chemin(s) ? | Les deux, automatiquement — `_POSITIONNEURS_PAR_MOTIF` est déjà consommé par `_positionner_composants_bloc`, utilisé à la fois par `generer_xml` (netlist) et `ecrire_groupes` (carte scannée). Aucun branchement supplémentaire nécessaire, contrairement au chantier précédent qui devait créer ce pont. |
| Rotation ? | Aucune — même règle que les chantiers précédents, jamais d'angle non nul. |
| Connectivité / fail-soft | Mêmes garanties qu'avant, déjà assurées par l'infrastructure existante (`_roles_du_bloc`, `_deltas_disposition_canonique`, `_appliquer_deltas`) — aucune modification requise à ces fonctions. |

## Architecture

### Sommateur / Intégrateur / Dérivateur (aucun nouveau code de disposition)

Ajout de 3 entrées à `_POSITIONNEURS_PAR_MOTIF` (dans `circuit_analyzer/xml.py`,
juste après l'entrée existante) :

```python
_POSITIONNEURS_PAR_MOTIF = {
    "Amplificateur inverseur (AOP)": _positionner_amplificateur_inverseur,
    "Amplificateur sommateur (AOP)": _positionner_amplificateur_inverseur,
    "Intégrateur (AOP)": _positionner_amplificateur_inverseur,
    "Dérivateur (AOP)": _positionner_amplificateur_inverseur,
    "Amplificateur différentiel (AOP)": _positionner_amplificateur_differentiel,
}
```

`_roles_du_bloc` (déjà générique) extrait déjà `{'Zin': [...], 'Zf': [...],
'aop': [...]}` pour ces trois montages sans changement — la fonction lit
`impedances` par nom de clé, pas par type de montage.

### Amplificateur différentiel (nouveau)

Nouvelle fonction `_positionner_amplificateur_differentiel(comps, roles, x, y)`
dans `circuit_analyzer/xml.py`, juste après `_positionner_amplificateur_inverseur` :

- `x_aop, y_aop = x + 2*_PAS_X_BLOC, y + _PAS_Y_BLOC` (même ancre que
  l'ampli inverseur).
- `Z1` (entrée IN−) : chaîne horizontale à gauche, à `y_aop` — identique au
  traitement de `Zin` dans l'ampli inverseur.
- `Zf` (contre-réaction) : chaîne horizontale au-dessus, à `y` — identique
  au traitement de `Zf` dans l'ampli inverseur.
- `Z3` (entrée IN+) : chaîne horizontale à gauche, à `y_aop + _PAS_Y_BLOC`
  (une ligne sous l'AOP).
- `Zg` (référence masse du IN+) : chaîne horizontale alignée sous l'AOP, à
  `y_aop + 2*_PAS_Y_BLOC`.
- Tout composant du bloc absent de `roles` (satellite) : grille compacte
  existante, sous la disposition (à `y + 3*_PAS_Y_BLOC` pour laisser la
  place aux 4 lignes).

Réutilise `_refs_du_role`/`_roles_du_bloc` sans modification — `roles` a
simplement 5 clés (`aop`, `Z1`, `Zf`, `Z3`, `Zg`) au lieu de 3.

## Gestion d'erreurs

Aucune nouvelle surface d'erreur : `_positionner_amplificateur_differentiel`
suit exactement le même schéma défensif que `_positionner_amplificateur_inverseur`
(placement par rôle présent uniquement, `roles.get(cle, [])` partout,
jamais d'accès direct qui pourrait lever `KeyError`).

## Tests

- Unitaires sur `_positionner_amplificateur_differentiel` : roles
  synthétiques (Z1/Zf/Z3/Zg à 1 ref chacun), assertions x/y concrètes pour
  les 4 lignes.
- Unitaires sur le registre étendu : un montage Sommateur (roles avec Zin
  en LISTE, cas déjà couvert par les tests existants de
  `_positionner_amplificateur_inverseur`) dispatché correctement via
  `_positionner_composants_bloc`.
- Non-régression : suite existante sur l'ampli inverseur et les montages
  non migrés (ex. Suiveur de tension) inchangée.
- Bout en bout sur les deux chemins (`generer_xml` ET `ecrire_groupes`,
  via `test_pid_3.xml` transposé en fixture synthétique si besoin) : les 4
  montages nouvellement migrés obtiennent une disposition canonique, le
  Suiveur de tension reste en repli générique (comportement inchangé,
  attendu).
- Visuel : étendre `tools/render_boardsch_layout.py` avec un cas
  différentiel, rendre en PNG, inspecter réellement.

## Points ouverts pour le plan d'implémentation

- Nom exact des refs de test pour le différentiel (suivre la convention
  `detecteur.py` : Z1/Zf/Z3/Zg comme noms de rôle, mais les refs réelles
  peuvent être R1-R4 comme dans `test_pid_3.xml`).
- Vérifier si `test_pid_3.xml` (fourni par le boss) peut servir de fixture
  réelle pour le test bout-en-bout du différentiel ET du sommateur —
  contrairement à l'ampli inverseur, cette carte réelle CONTIENT ces
  montages, donc pas besoin de fixture synthétique pour la validation
  finale.
