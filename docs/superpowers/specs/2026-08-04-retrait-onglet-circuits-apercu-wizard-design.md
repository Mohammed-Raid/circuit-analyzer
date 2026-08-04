# Retrait de l'onglet Circuits + aperçu schématique du wizard — Design

**Date :** 2026-08-04
**Statut :** design présenté, approuvé par le boss section par section — en
attente d'écriture du plan d'implémentation.

**Suite de :** aucune — nouveau chantier, indépendant du chantier « éditeur
fidèle » (Schéma → export XML avec positions réelles) mis explicitement de
côté pendant le brainstorming (ampleur différente, deux specs séparées).

## Contexte (pourquoi)

L'onglet **Circuits** (`gui/tab_circuits.py`) fait aujourd'hui deux choses :
consulter en lecture seule la description des 28 circuits intégrés, et
créer/modifier/supprimer des circuits personnalisés via une liste texte à
gauche + formulaire à droite.

Or la création d'un circuit personnalisé est déjà possible **depuis les
onglets Analyser et Schéma**, via `PatternWizard` (`gui/pattern_wizard.py`,
assistant en 4 étapes) — l'onglet Circuits est donc redondant pour la
création. Le boss veut le retirer.

Deuxième problème, indépendant mais découvert pendant le brainstorming : un
circuit personnalisé n'a **jamais de représentation visuelle**, ni à sa
création (l'étape 4 du wizard affiche le JSON brut du pattern), ni plus tard
quand il est détecté et cliqué dans un rapport
(`circuit_viewer.show_circuit` cherche un dessinateur dédié par nom
`_DRAWERS.get(name)` ; un nom de circuit personnalisé n'y est jamais
enregistré, donc bascule sur un repli texte : nom + liste de refs séparées
par des points). Le boss ne veut plus de texte ou de liste — il veut du
visuel.

**Décision de périmètre (verrouillée pendant le brainstorming) :** on ne
corrige le rendu texte **qu'à l'étape de confirmation du wizard**. Le repli
texte de `show_circuit()` pour un circuit personnalisé déjà détecté (clic
depuis un rapport, après création) reste inchangé — hors périmètre de ce
chantier.

## Décisions verrouillées (brainstorming avec le boss)

| Question | Décision |
|---|---|
| Onglet Circuits | Retiré entièrement (nav + fichier + wiring `app_window.py`) |
| Description des 28 circuits intégrés (lecture seule) | Perdue, sans remplacement — décision explicite |
| Modifier un circuit personnalisé existant | Non nécessaire : supprimer + recréer via le wizard suffit |
| Supprimer un circuit personnalisé existant | Oui, requis — bouton dans la popup schéma déjà existante (`show_circuit`), jamais une liste dédiée |
| Aperçu visuel à l'étape 4 du wizard | Requis — remplace le JSON brut affiché aujourd'hui |
| Moteur de rendu de cet aperçu | **Nouveau code dédié au wizard**, PAS de réutilisation du moteur îlots (`_make_island_fig`/`_build_island_model`) — décision explicite malgré la recommandation inverse |
| Sophistication de ce rendu | Simple : vrais symboles (`style_symbole`), alignement en ligne/grille, fils droits entre nets partagés — pas de gestion rails/branches multiples/compaction |
| Export ERetroDesign d'un circuit personnalisé | Aucun changement : le chemin existant (`eretro_patch`, actif quand la source d'analyse est un `.xml`) s'applique déjà sans travail supplémentaire |

## Non-goals

- Édition d'un circuit personnalisé existant (formulaire de modification).
- Correction du repli texte de `show_circuit()` pour un circuit personnalisé
  déjà détecté et cliqué depuis un rapport (reste tel quel).
- Toute réutilisation du moteur de rendu îlots — écarté explicitement.
- Le chantier « éditeur fidèle » (positions réelles du Schéma dans l'export
  XML) — spec séparée, à venir.
- Modification de `custom_circuits.json` en un autre format (XML) — écarté
  pendant le brainstorming : ce fichier contient des règles de détection
  abstraites (types de composants + conditions), pas des schémas ; rien à
  « ouvrir dans ERetroDesign » pour une règle qui ne dessine rien.

## Architecture

### 1. Retrait de l'onglet Circuits

- `gui/app_window.py` : retirer l'entrée `("zap", "Circuits", "Patterns
  personnalisés")` de la liste `items` (nav), l'import `TabCircuits`,
  l'instanciation `tab_c = TabCircuits(content)`, et son entrée dans
  `self._frames`.
- `_on_pattern_created()` (callback partagé Analyser/Schéma après création
  via le wizard) : ne fait plus rien pour Circuits — supprimer l'appel
  `tab_c.refresh_circuits()`. Vérifier qu'aucun autre effet de bord de ce
  callback ne dépendait de Circuits (à date, non : c'était son seul rôle).
- `_on_lib_change()` (callback après modification de la bibliothèque de
  composants) : supprimer l'appel `tab_c.refresh_component_list()`, garder
  `tab_d.refresh_palette()`.
- Supprimer `gui/tab_circuits.py` entièrement (aucun autre module n'importe
  `TabCircuits`, vérifié par grep).
- Tests à réécrire (pas juste supprimer, car ils couvrent un comportement
  réel — création de pattern personnalisé — qui doit rester testé via
  d'autres entrées) :
  - `tests/test_gui_sync.py`, `tests/test_palette_et_doublon.py`,
    `tests/test_pattern_refresh.py` instancient `TabCircuits` directement.
    Reporter leurs assertions utiles (ex. `test_doublon_pattern_refuse`)
    vers des tests pilotant `PatternWizard` + `load_custom_circuits`
    directement, sans passer par un onglet.

### 2. Suppression d'un circuit personnalisé depuis la popup schéma

- `gui/circuit_viewer.py:show_circuit(result, comp_info, parent, graph)` :
  ajouter un bouton dans la barre du bas (`bar`, à côté de « 💾 Exporter
  PNG »), affiché **seulement si** `result["circuit_type"]` correspond au
  nom d'une entrée de `custom_circuits.json` (chargé via
  `custom_circuits.loader.load_custom_circuits()`).
- Handler : confirmation (`messagebox.askyesno`), puis retire l'entrée de la
  liste chargée et `save_custom_circuits(circuits)`, puis ferme la popup.
- N'affecte pas le résultat déjà affiché dans le rapport courant (il reste
  visible jusqu'à la prochaine analyse) — cohérent avec le fait qu'on
  supprime la RÈGLE, pas un match déjà calculé.

### 3. Aperçu schématique à l'étape 4 du wizard

Nouvelle fonction, ex. `gui/pattern_wizard.py:_dessiner_apercu(refs, graph,
comp_info) -> Figure` :

- Pour chaque `ref` sélectionnée (`self._selected_refs()`), récupérer son
  `Composant` (type, value, pins) depuis `graph.graph['components']`.
- Pour chaque paire de composants sélectionnés partageant un net commun
  (comparaison des valeurs de `pins`), calculer une connexion à dessiner.
- Layout simple : composants placés en ligne (ou grille si plus de ~5-6,
  seuil à affiner en implémentation) à espacement fixe.
- Chaque composant dessiné avec son vrai symbole via
  `gui.impedance_schematic.style_symbole(typ, value, ref)` (déjà public,
  déjà réutilisé par `circuit_viewer.py` — import normal, pas de symbole
  privé).
- Fils : lignes droites `schemdraw.elements.Line` entre les points de
  connexion des composants partageant un net, façon `impedance_schematic._
  dessiner_impl` mais sans la logique série/parallèle (juste une ligne par
  paire connectée).
- Retourne une `matplotlib.figure.Figure`, affichée dans l'étape 4 à la
  place de (ou au-dessus de) `self._preview_box` (JSON) — le JSON peut
  rester en secondaire (repli/debug) ou disparaître, à trancher en
  implémentation selon le rendu obtenu.

**Composants isolés (aucun net partagé avec le reste de la sélection) :**
dessinés quand même, simplement sans fil — pas d'erreur, pas d'exclusion
silencieuse (cohérent avec la philosophie du projet : jamais un composant
invisible).

## Gestion d'erreurs

- Aucun composant sélectionné à l'étape 4 : ne devrait pas arriver (le
  wizard bloque déjà la progression sans sélection à l'étape 1, vérifié
  dans `_validate_current`) — pas de garde supplémentaire nécessaire.
- Type de composant sans symbole connu dans `style_symbole` : déjà géré par
  son repli `_SYMB.get(typ, elm.ResistorIEC)` — comportement existant,
  inchangé.
- Suppression d'un circuit personnalisé dont le nom ne matche plus exactement
  une entrée (fichier modifié entre-temps) : `save_custom_circuits` sur la
  liste rechargée à l'instant du clic, pas de cache périmé — pas de cas
  d'erreur particulier à gérer.

## Tests

- `tests/test_pattern_wizard.py` (**nouveau** — `PatternWizard` n'a
  aujourd'hui aucune couverture de test, vérifié : aucun fichier de test ne
  l'importe) : aperçu schématique généré sans exception pour 2/3/6+
  composants, composant isolé dessiné sans fil, symboles corrects par type.
- `tests/test_z_reseau.py` ou nouveau fichier : bouton supprimer visible
  seulement pour un `circuit_type` présent dans les patterns personnalisés,
  absent pour un circuit intégré ; suppression retire bien l'entrée de
  `custom_circuits.json` (fichier temporaire, jamais le vrai fichier de
  l'utilisateur).
- Réécriture de `test_gui_sync.py` / `test_palette_et_doublon.py` /
  `test_pattern_refresh.py` (cf. §Architecture 1) pour ne plus dépendre de
  `TabCircuits`.
- Suite complète verte après suppression du fichier + de ses imports.

## Documentation à mettre à jour

- `README.md` : le tableau des 4 onglets (§Utilisation) passe à 3 ; le
  chiffre « 28 circuits reconnus » (déjà corrigé lors de l'audit du
  2026-08-04) n'est plus affiché nulle part dans l'UI mais reste correct
  dans le texte du README (qui documente le moteur de détection, pas la
  navigation).
