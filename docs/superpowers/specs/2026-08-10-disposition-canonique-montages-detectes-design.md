# Disposition canonique des montages détectés — Design

**Date :** 2026-08-10
**Statut :** design validé en conversation, prêt pour le plan d'implémentation.

**Suite de :** aucune — indépendant du chantier « gabarits XML pour les
montages canoniques » (2026-08-10, en attente de validation du boss) qui
touche la DÉTECTION (rendre les 24 détecteurs modifiables via XML), pas la
DISPOSITION. Les deux partagent le vocabulaire « montage canonique » mais
n'ont aucune dépendance technique.

## Contexte (pourquoi)

Pipeline visé : ERetroDesign scanne une carte → export XML → notre
analyseur Python détecte les montages (`detecteur.analyser`) → on regénère
un schéma BoardSCH où chaque montage reconnu est disposé selon SA
disposition canonique (AOP centré, Zin à gauche, Zf en arc de contre-
réaction, etc.) au lieu d'un simple regroupement par type de composant →
ce fichier régénéré est ouvert dans ERetroDesign, où l'arrangement
D'ENSEMBLE des montages les uns par rapport aux autres se fait (pas notre
problème pour ce chantier).

Aujourd'hui, `circuit_analyzer/xml.py` sait déjà positionner par FAMILLE de
composants (`_positionner_aop` place n'importe quel montage dont le libellé
contient "aop"/"amplificateur"/"comparateur"/... de la même façon : AOP
centré, 2 premières résistances dessous, le reste en grille) — mais sans
connaître les RÔLES (quelle résistance est Zin, laquelle est Zf). Pas de
disposition vraiment canonique.

## Décisions verrouillées

| Question | Décision |
|---|---|
| Périmètre du chantier | `circuit_analyzer/xml.py` (fonctions `_positionner_*`) et son appelant `xml_generator.generer_xml`. Aucun code C#/ERetroDesign touché. |
| Chemin de régénération | Via `generer_xml` (fabrication), PAS `eretro_patch.ecrire_groupes` (patch en place). Choix délibéré et assumé : les positions réelles scannées sont ENTIÈREMENT abandonnées au profit des positions canoniques. |
| Composants non reconnus | Pas de préservation partielle des positions scannées — hors périmètre. Si un besoin de « ne régénérer que les montages reconnus, garder le reste tel que scanné » apparaît plus tard, c'est un autre chantier (`generer_xml` ne sait pas faire du mélange aujourd'hui). |
| Arrangement d'ensemble | Hors périmètre — le placement des BLOCS les uns par rapport aux autres (`_positionner_blocs`, grille simple) reste tel quel. Seule la disposition INTERNE à un bloc/montage devient canonique. |
| **Contrainte dure** | **La connectivité doit être préservée à l'identique** : si A était relié à B avant régénération, A doit être relié à B après. Déjà garanti par construction (`generer_xml` reconstruit les fils depuis `comp.pins`, jamais depuis les positions) — vérifié par un test de bout en bout dédié, pas juste affirmé. |
| Validation | 1 seul montage d'abord : Amplificateur inverseur (AOP) — le plus simple structurellement, cas cohérent avec la phase 1 du chantier « gabarits XML » (indépendant mais même choix de départ). |

## Architecture

Trois paliers de repli dans `_positionner_composants_bloc`, aucune
régression pour ce qui n'est pas migré :

```
_positionner_composants_bloc(bloc, x, y)
  1. bloc.roles non vide ET circuit_type dans _POSITIONNEURS_PAR_MOTIF
       -> nouveau positionneur role-aware (ex. _positionner_amplificateur_inverseur)
  2. label correspond a une famille connue ("aop", "rc", "commande de relais"...)
       -> _positionner_aop / _positionner_rc / ... (INCHANGES)
  3. rien ne correspond
       -> _positionner_grille_compacte (INCHANGE)
```

`_POSITIONNEURS_PAR_MOTIF` est un dict `{circuit_type_exact: fonction}`,
un enregistrement par montage migré — additif, pas de chaîne if/elif qui
grossit indéfiniment. Migration montage par montage, comme le principe déjà
établi ailleurs dans le projet (ex. le chantier gabarits XML).

## Données : où sont les rôles aujourd'hui

`detecteur.detecter_amplificateur_inverseur` renvoie déjà, par match :

```python
{'circuit_type': 'Amplificateur inverseur (AOP)',
 'components': [ref_aop, *feedback_refs, *entree_refs],
 'impedances': {'Zin': {'refs': [...], 'composition': ..., 'nodes': (...)},
                'Zf':  {'refs': [...], 'composition': ..., 'nodes': (...)}},
 ...}
```

Cette info existe déjà en mémoire mais est jetée par `_grouper_par_circuit`,
qui aplatit tout en une simple liste de refs pour construire `_Bloc`.

**Changement :** `_Bloc` gagne un champ `roles: dict[str, list[str]]`
(ex. `{'aop': [ref_aop], 'Zin': [...], 'Zf': [...]}`), rempli une fois à
côté de la logique d'aplatissement existante (qui ne change pas), vide par
défaut (Divers, ou montage pas encore migré).

## Le positionneur canonique (premier cas : ampli inverseur)

`_positionner_amplificateur_inverseur(roles, x, y) -> dict[str, tuple[int, int, int]]`

- AOP à une position ancre fixe.
- `roles['Zin']` : ses refs disposées en petite chaîne horizontale à
  GAUCHE de l'entrée IN- de l'AOP (une Zin composite R+C en série reste
  lisible comme UN bloc d'impédance, pas deux composants isolés).
- `roles['Zf']` : ses refs disposés AU-DESSUS de l'AOP, entre l'abscisse
  de IN- et celle de OUT (l'arc de contre-réaction visuel).
- Retourne des TRIPLETS `(x, y, angle)`, pas des paires — `angle` existe
  déjà de bout en bout (`_Comp.angle`, `gen.ajouter(angle=...)`,
  `<angle>` en sortie XML) mais aucun `_positionner_*` actuel ne le
  renseigne (toujours 0 implicite). `_positionner_blocs`/`generer_xml`
  acceptent les deux formats : paire (angle 0 implicite, fonctions
  existantes inchangées) ou triplet (nouvelles fonctions).

## Gestion d'erreurs

Même philosophie fail-soft que le reste du projet (cf. `eretro_patch.py` :
avertir et continuer, jamais deviner ni planter) : si `roles` est vide ou
incomplet pour un match, le palier 1 est simplement sauté, repli sur le
palier 2 exactement comme aujourd'hui. Un montage ne peut jamais finir
moins bien disposé qu'avant ce chantier.

## Tests

- Unitaires sur `_positionner_amplificateur_inverseur` : `roles` synthétique
  (Zin/Zf à 1 ref, puis Zin composite à 2 refs), assertions x/y/angle
  concrètes.
- Non-régression : suite existante sur `_positionner_aop`/`_positionner_blocs`/
  `generer_xml` inchangée — prouve que les paliers 2/3 ne bougent pas.
- **Connectivité de bout en bout** (contrainte dure du boss) : fichier
  scanné de test → détection → `generer_xml` → reparser la sortie via
  `lire_xml`/`construire_graphe` → assertion que le graphe de connectivité
  (mêmes broches, mêmes appartenances de net) est IDENTIQUE à celui du
  fichier scanné d'origine.
- Visuel : rendre le XML régénéré en PNG et l'inspecter réellement, pas
  seulement des tests verts (convention déjà en place sur ce projet).
  Mécanisme de rendu exact (probablement via le canevas de
  `gui/tab_draw.py`, qui charge déjà via `lire_xml`/`generer_xml`) à
  préciser dans le plan d'implémentation.

## Points ouverts pour le plan d'implémentation

- Mécanisme précis de rendu PNG pour la vérification visuelle.
- Ordre exact de placement des refs composites de Zin/Zf quand plus de 2
  composants (au-delà du cas de test initial R+C).
- Migration des montages suivants après validation de l'ampli inverseur —
  ordre à déterminer, probablement du plus simple au plus complexe comme
  pour le chantier gabarits XML.
