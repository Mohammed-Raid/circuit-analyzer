# Gabarits XML pour les montages canoniques — Design

**Date :** 2026-08-10
**Statut :** design présenté au relais du boss, en attente de validation par le
boss lui-même avant écriture du plan d'implémentation.

**Suite de :** aucune — nouveau chantier, indépendant de « fidélité de forme
réelle éditeur » (import/export XML, en cours de revue sur la branche
`fidelite-formes-editeur`). Les deux chantiers touchent le même format XML
BoardSCH mais n'ont pas de dépendance technique l'un envers l'autre.

## Contexte (pourquoi)

Les 24 montages canoniques que l'analyseur reconnaît aujourd'hui
(Amplificateur inverseur, Sommateur, Intégrateur, Comparateur, Transistor en
commutation, Impédance Z...) sont **écrits en dur en code Python**
(`circuit_analyzer/detecteur.py` + `circuit_analyzer/patterns/*.py`). Chaque
montage a sa propre fonction `detecter_xxx(graphe)` qui marche à la main les
broches et les nœuds du graphe pour reconnaître la structure.

Le boss veut pouvoir **modifier la structure d'un montage de base
directement**, sans dépendre d'un développeur pour changer le code Python.
Contrainte forte, explicite : le boss n'est **pas électronicien de formation
technique logicielle** et n'est **pas la personne qui va lire du code ou du
JSON** — toute interaction doit passer par un schéma qu'il dessine/modifie
normalement, comme n'importe quel autre schéma dans l'app ou dans
ERetroDesign.

Décision explicitement demandée en clarification (voir historique de
conversation, pas de doc figé antérieur) : modifier le schéma de référence
d'un montage doit changer ce que l'analyseur DÉTECTE sur les cartes
importées — ce n'est pas un schéma de documentation passif, c'est la source
de vérité de la détection, une fois migré.

## Décisions verrouillées (clarifications avec le relais du boss)

| Question | Décision |
|---|---|
| Quoi rendre modifiable ? | Les 24 montages de BASE eux-mêmes (pas seulement créer de nouveaux montages personnalisés — ça existe déjà via `PatternWizard`). |
| Éditer l'original ou dupliquer ? | Éditer l'ORIGINAL directement — pas un système de fork/copie. |
| Quel niveau de modification ? | La STRUCTURE/topologie recherchée elle-même, pas seulement des seuils numériques ou du texte affiché. |
| Format du fichier ? | XML — le même format BoardSCH que l'import/export existant, pour pouvoir l'ouvrir directement dans ERetroDesign OU dans notre éditeur. |
| Effet sur la détection ? | Modifier le XML doit changer ce que l'analyseur détecte, pas juste servir de documentation. |
| Complexité pour l'utilisateur ? | **Zéro syntaxe spéciale.** Le boss ouvre un schéma normal, le modifie comme un dessin normal (déplacer/ajouter un composant, changer une valeur, ajouter un fil), sauvegarde. Aucune case à cocher, aucun marqueur, aucun concept de "motif répétable" à comprendre de son côté — ça reste un problème d'ingénierie côté app. |
| Réutilisation future ? | Le dossier de gabarits est pensé comme une bibliothèque durable, pas un one-shot — on pourra y ajouter de nouveaux montages plus tard. |

## Architecture

### Stockage : un fichier BoardSCH XML par montage, dans un dossier dédié

Nouveau dossier `patterns_reference/` (nom à confirmer), un fichier XML par
montage canonique — même principe que la bibliothèque de composants
partagée déjà existante (`circuit_analyzer/eretro_lib.py`,
`ecrire_dans_dossier` : un fichier par élément dans un dossier, jamais un
gros fichier bundle). Cohérence avec un mécanisme déjà en place et déjà
compris par l'équipe.

Chaque fichier est un schéma BoardSCH normal, produit avec l'export existant
(`circuit_analyzer.xml.generer_xml`) — un montage minimal et correct
(composants, valeurs illustratives, câblage réel), directement ouvrable dans
ERetroDesign ou dans `gui/schematic_editor.py` via import XML.

### Nouveau moteur de correspondance structurelle

Nouveau module (`circuit_analyzer/gabarit.py`, nom à confirmer) :

1. **Chargement** : lit le XML de référence avec `lire_xml` (déjà existant),
   construit son graphe avec `construire_graphe` (déjà existant).
2. **Reconnaissance des rôles** : les nœuds de masse/alimentation sont
   reconnus par rôle (`is_gnd`, `is_power`, déjà existants), pas par nom de
   net exact — un `NET7` dans le gabarit et un `N42` dans la carte importée
   doivent pouvoir correspondre s'ils jouent le même rôle.
3. **Inférence automatique de répétition** : pour un composant ancre (ex.
   l'AOP), on regarde les composants connectés à chacune de ses broches. Si
   le gabarit montre **plusieurs composants du même type jouant un rôle
   structurellement identique** (ex. 3 résistances qui arrivent toutes sur
   IN- sans aller vers OUT), le moteur généralise automatiquement en « 1 ou
   plus » — pas de marqueur explicite à écrire dans le XML, la répétition
   elle-même dans le dessin EST le signal. Une seule occurrence dans le
   gabarit reste une exigence stricte (exactement un).
   - Cette règle reproduit fidèlement ce que fait déjà le code actuel du
     Sommateur (`zin` = liste de blocs d'entrée, exige `len(zin) >= 2`) —
     ce n'est pas une invention, c'est la généralisation d'un pattern déjà
     observé dans 4-5 des 24 détecteurs actuels.
4. **Valeurs non exigées** : les valeurs de composants du gabarit (`10k`,
   `100nF`...) sont illustratives, jamais comparées à l'identique — seule la
   structure (types + rôles + connexions) compte, cohérent avec le
   comportement actuel des 24 détecteurs.
5. **Résultat compatible** : le moteur renvoie un match au même format que
   l'existant (`circuit_type`, `components`, `nodes`, `composition`,
   `confidence`, `functional_category`...) pour ne rien casser en aval
   (rendu `_DRAWERS`, rapports, îlots, satellites).

### Ce qui reste HORS PÉRIMÈTRE de ce chantier

- Les `warnings`/`satellites` (composants voisins non classifiés,
  rattachement possible) : le nouveau moteur les ignore dans une première
  version — un montage migré perd temporairement cette finesse jusqu'à ce
  qu'on décide si/comment la généraliser aussi.
- Les valeurs numériques EXACTES (ex. exiger un rapport de gain précis) :
  aucun des 24 détecteurs actuels ne le fait, donc le nouveau moteur ne le
  fait pas non plus — pas une régression.
- Les montages non-AOP structurellement différents (Impédance Z, ponts
  redresseurs...) peuvent avoir des besoins de reconnaissance différents
  des montages AOP — à valider migration par migration, pas supposé
  résolu d'avance par la même mécanique.

## Migration (comment on ne casse rien)

1. **Phase 1 — preuve du mécanisme** : migrer 1-2 montages simples et SANS
   répétition (candidats : Suiveur de tension, Amplificateur inverseur) —
   les plus simples structurellement, pour valider XML → graphe →
   correspondance → détection de bout en bout, sans la complexité de
   l'inférence de répétition.
2. **Phase 2 — montage avec répétition** : migrer le Sommateur (le cas de
   référence pour la règle de répétition automatique) — valider que
   l'inférence généralise correctement (2, 3, N entrées).
3. **Phase 3 — le reste** : les 21 autres montages, un par un, dans un ordre
   à déterminer (probablement du plus simple au plus complexe).
4. **Garde-fou à chaque migration** : la suite de tests existante teste déjà
   précisément chacun des 24 détecteurs (cas positifs et négatifs). Un
   montage n'est considéré migré QUE quand le nouveau moteur, piloté par son
   XML de référence, produit EXACTEMENT les mêmes matches que l'ancien code
   Python sur TOUS les tests existants qui le concernent — sinon, l'ancien
   code reste actif pour ce montage.
5. **Aucun montage n'est cassé en cours de route** : tant qu'un montage
   n'est pas migré, son détecteur Python reste actif inchangé, exactement
   comme aujourd'hui.

## Utilisation pratique (workflow du boss)

1. Il ouvre le fichier XML du montage voulu dans `patterns_reference/` — via
   ERetroDesign, ou via notre éditeur (import XML existant).
2. Il modifie le schéma comme un schéma normal : déplacer/ajouter/supprimer
   un composant, changer une valeur, ajouter/retirer un fil.
3. Il sauvegarde (export XML depuis ERetroDesign, ou notre éditeur).
4. L'app recharge les gabarits (au démarrage, ou via un bouton "recharger
   les patrons" — détail d'implémentation à trancher dans le plan) et
   détecte désormais selon le schéma modifié.

## Gestion d'erreurs

- **XML de référence invalide ou illisible** : l'app doit dégrader
  proprement (ignorer ce gabarit précis, logger un avertissement clair en
  français, continuer avec les autres montages) — jamais planter au
  démarrage à cause d'un fichier modifié par erreur.
- **Gabarit structurellement ambigu** (ex. deux composants ancre possibles,
  aucune broche de rôle reconnaissable) : le moteur doit refuser
  silencieusement de produire des faux positifs plutôt que deviner — même
  philosophie fail-closed que le reste de l'analyseur (cf. détection de
  collisions de noms de broches, déjà en place ailleurs dans le projet).
- **Gabarit qui ne matche plus rien après modification** : comportement
  attendu et acceptable (le boss a le droit de casser un montage en le
  modifiant) — pas un bug à corriger, un risque à documenter dans l'aide.

## Tests

- Suite de non-régression existante par montage (déjà précise) = le
  contrat que chaque migration doit satisfaire à l'identique.
- Nouveaux tests pour le moteur de correspondance lui-même : cas simple
  sans répétition, cas avec répétition (2, 3, N occurrences), cas de rôle
  masse/alimentation reconnu par fonction pas par nom de net, cas d'échec
  propre (XML invalide, gabarit ambigu).
- Test de bout en bout : modifier un gabarit migré (ex. passer le Sommateur
  de 3 à 4 entrées dans le XML), relire, confirmer que l'analyseur détecte
  désormais un sommateur à 4 entrées sur un cas de test construit pour
  l'occasion.

## Points encore ouverts pour le plan d'implémentation

- Nom exact du dossier et du module (`patterns_reference/` et
  `circuit_analyzer/gabarit.py` sont des propositions, pas verrouillés).
- Mécanisme exact de « recharger les patrons » (redémarrage obligatoire vs
  bouton dans l'UI).
- Comment un montage migré interagit avec `_CATEGORIES` (catégorie
  fonctionnelle) et `_DRAWERS` (rendu visuel du montage détecté) — ces deux
  dictionnaires sont aujourd'hui indexés par le NOM du `circuit_type`, donc
  a priori inchangés tant que le nom du montage ne change pas dans le XML —
  mais le cas où le boss RENOMME le montage dans son schéma modifié doit
  être tranché explicitement (nom = identité du montage, ou champ séparé ?).
- Ordre précis de migration des 21 montages de la phase 3.
