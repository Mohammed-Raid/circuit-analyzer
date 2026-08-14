# Interprétation fonctionnelle des groupes — Design

**Date :** 2026-08-14
**Statut :** design validé en conversation, prêt pour le plan d'implémentation.
**Classification :** Architectural (nouvelle capacité, pas une extension d'un
flux existant).

## Contexte (pourquoi)

En analysant deux cartes réelles fournies par le boss (`flyback.xml`,
`SAN.xml`), la détection structurelle existante (`detecteur.analyser`,
`rapport.generate`) donne déjà le NOM du motif (« Intégrateur (AOP) »),
sa confiance, ses composants, ses satellites — mais jamais le RÔLE
fonctionnel probable dans l'ensemble de la carte (« c'est probablement
l'amplificateur d'erreur de la boucle de régulation »). Cette lecture,
faite manuellement pendant la session, doit devenir automatique et,
surtout, visible **directement dans ERetroDesign** — pas seulement dans
un rapport texte séparé que le boss devrait croiser à la main.

Deuxième volet, demandé explicitement par le boss après la première
validation de ce design : `flyback.xml` doit servir de référence pour
qu'à l'avenir, une carte présentant la MÊME combinaison de motifs
(rectification secteur + boucle intégrateur/comparateur sur une même
puce) soit reconnue comme « probablement un convertisseur à découpage
type flyback » — pas juste ses sous-parties étiquetées séparément.

## Décisions verrouillées

| Question | Décision |
|---|---|
| Portée de l'inférence | Un ensemble RESTREINT et curaté de combinaisons connues (pas un moteur de raisonnement général) — cohérent avec la directive du projet de ne jamais gold-plater au-delà du périmètre actuel. |
| Où le résultat apparaît | Dans le nom du groupe (`<GRPS><Name>`) écrit par `circuit_analyzer/eretro_patch.py` — le même champ déjà rendu par ERetroDesign comme titre du cadre de groupe. Pas dans le rapport texte (`rapport.py`) pour cette itération. |
| Trois catégories de règles | (a) Motif SIMPLE connu → note directe (ex. Pont redresseur Graetz → rectification secteur). (b) COMBINAISON de motifs AOP partageant la MÊME puce physique (ex. Intégrateur + Comparateur sur U3) → note de boucle probable. (c) COMBINAISON SYSTÈME : la combinaison (b) ci-dessus PLUS un motif Pont redresseur présent quelque part sur la carte → note de « convertisseur flyback probable ». |
| Où va la note système | Sur le groupe Pont redresseur UNIQUEMENT (pas sur l'intégrateur/comparateur, qui gardent leur note locale (b) inchangée) — évite de répéter la même affirmation de portée carte-entière sur 3 titres de groupe différents. |
| Certitude affichée | Toujours au conditionnel/hédgé (« probable », « probablement ») — jamais affirmatif, même style que les libellés « ATTENTION » déjà utilisés pour les satellites incertains. |
| Portée des deux chemins | S'applique aux deux chemins d'écriture XML (`generer_xml` ET `ecrire_groupes`), car les deux partagent déjà le même mécanisme de nommage de groupe (`bloc.label` → `noms` → `<GRPS><Name>`). |
| Sécurité | Le champ `<GRPS><Name>` est déjà documenté dans le code existant comme purement DÉCORATIF et ne devant jamais faire échouer l'écriture — l'interprétation hérite de cette garantie : toute donnée manquante/inattendue fait sauter la note, jamais une exception. |

## Architecture

### Nouveau module : `circuit_analyzer/interpretation.py`

Un petit module isolé, à la frontière entre la détection (`detecteur.py`)
et l'écriture XML (`xml.py`/`eretro_patch.py`) — ne modifie AUCUN des deux,
lu par eux.

**Table des motifs simples** (`dict[str, str]`) : nom de `circuit_type` →
note. Une seule entrée au départ :
`'Pont redresseur (Graetz)': "rectification secteur probable (entrée AC → DC)"`.

**Table des combinaisons même-puce** (`list[tuple[frozenset[str], str]]`) :
ensemble de `circuit_type` requis (tous doivent être présents, sur la
MÊME puce) → note. Une seule entrée au départ :
`({'Intégrateur (AOP)', 'Comparateur (AOP)'}, "boucle de contre-réaction / protection probable (intégrateur + comparateur sur la même puce)")`.

**Table des combinaisons système** (`list[tuple[frozenset[str], str, str]]`) :
ensemble de `circuit_type` requis pour la combinaison même-puce ci-dessus
(doit avoir DÉJÀ matché), type de motif « ancre » qui doit être présent
ailleurs sur la carte (sans contrainte de puce — un pont de diodes n'est
pas « sur une puce »), et note additionnelle attachée à l'ancre. Une seule
entrée au départ :
`({'Intégrateur (AOP)', 'Comparateur (AOP)'}, 'Pont redresseur (Graetz)', "élément probable d'un convertisseur à découpage type flyback (rectification + boucle de régulation détectées ensemble)")`.

**Fonction `_ref_puce(ref: str) -> str`** : `ref.split('.')[0]` — même
convention déjà observée partout ailleurs dans le projet pour les
sous-références de puce composée (`U3.11` → `U3`).

**Fonction `_ref_aop(match) -> str | None`** : extrait la ref de l'AOP d'un
match AOP — le seul composant du match absent de tous les rôles
d'impédance (`impedances`), même logique que `_roles_du_bloc`
(`circuit_analyzer/xml.py`) utilise déjà pour isoler le rôle `'aop'`.

**Fonction `interpreter(resultats) -> None`** : mute chaque match
qualifiant en place, ajoutant une clé `'interpretation'` (absente sinon —
rétrocompatible avec tout consommateur existant de la liste de matches).
Trois passes, dans l'ordre :
1. Motifs simples : note directe par `circuit_type`.
2. Combinaisons même-puce : regroupement des matches AOP par puce via
   `_ref_puce(_ref_aop(match))`, puis vérification que l'ensemble des
   `circuit_type` du groupe couvre une combinaison connue — note attachée
   à chaque match du groupe concerné (remplace ou étend la note simple
   éventuelle du même match).
3. Combinaisons système : pour chaque entrée, si la combinaison même-puce
   correspondante a été trouvée à l'étape 2 (n'importe où sur la carte,
   n'importe quelle puce) ET qu'au moins un match du `circuit_type` ancre
   existe dans `resultats`, ajouter la note système à CE match ancre (en
   la concaténant à sa note existante s'il en a déjà une, ex. sa note de
   motif simple).

### Intégration côté écriture XML

Dans `circuit_analyzer/eretro_patch.py` (fonction contenant la ligne
`noms = {i: getattr(b, "label", "") or "Montage" ...}`, ligne ~419), et
dans l'équivalent côté `generer_xml` (`circuit_analyzer/xml.py`) : après
avoir appelé `interpretation.interpreter(resultats)` une fois (tôt, sur
la liste de matches originale — AVANT la construction des `_Bloc`, pour
avoir accès à `impedances`/`components` complets), construire `noms` en
ajoutant `— {interpretation}` au label quand le match correspondant porte
une clé `'interpretation'` non vide.

## Gestion d'erreurs

- Match sans `'impedances'` (motif non-AOP, Divers) : `_ref_aop` renvoie
  `None`, jamais inclus dans le regroupement par puce — pas d'exception.
- Aucune combinaison ne matche : `resultats` reste inchangé, `noms`
  identique à avant ce chantier (rétrocompatibilité byte-identique quand
  rien ne qualifie).
- Refs de puce mal formées (pas de `.`) : `_ref_puce` renvoie la ref
  entière telle quelle — un composant seul (pas de puce composée) ne
  peut jamais accidentellement « partager » une puce avec un autre.
- Combinaison système sans ancre présente (ex. boucle intégrateur/
  comparateur détectée mais aucun pont redresseur sur la carte) : aucune
  note système ajoutée, aucune exception — la combinaison même-puce garde
  sa note locale normalement.
- Plusieurs matches du type ancre (rare, mais possible) : la note système
  s'ajoute à CHACUN — jamais de choix arbitraire d'un seul parmi plusieurs
  candidats équivalents.

## Tests

- Unitaires sur `interpreter` : motif simple seul (Graetz) → note
  attachée ; combinaison même-puce (2 matches AOP, refs `U3.X`/`U3.Y`)
  → note attachée aux deux ; même combinaison de types mais puces
  DIFFÉRENTES (`U3.X`/`U4.Y`) → aucune note même-puce (donc aucune note
  système non plus, elle en dépend) ; motif sans `impedances`
  (Divers) → jamais de crash, aucune note.
- Unitaires sur la combinaison système : les 3 motifs présents ensemble
  (Graetz + intégrateur/comparateur même puce) → le Graetz porte la note
  système CONCATÉNÉE à sa note simple existante ; intégrateur/comparateur
  gardent SEULEMENT leur note locale (b), jamais la note système ; boucle
  même-puce présente mais AUCUN Graetz sur la carte → aucune note système
  nulle part, aucune exception.
- Intégration : `noms` construit correctement avec le suffixe
  d'interprétation, sur les deux chemins (`generer_xml` et
  `ecrire_groupes`), avec un cas où rien ne qualifie (nom inchangé,
  non-régression explicite).
- Bout en bout sur `flyback.xml` (fichier réel du boss, déjà utilisé
  aujourd'hui) : patcher le fichier, relire le XML produit, vérifier que
  `<GRPS><Name>` du groupe Intégrateur et du groupe Comparateur portent
  bien la note de boucle de contre-réaction, et que le groupe Pont
  redresseur porte À LA FOIS sa note de rectification secteur ET la note
  système de convertisseur flyback probable. Régénérer le rendu visuel
  existant (`tools/render_boardsch_layout.py`) pour une inspection
  réelle, même exigence que tous les chantiers précédents de cette
  session.

## Points ouverts pour le plan d'implémentation

- Emplacement exact du séparateur dans le nom composé (« — » choisi ici,
  à confirmer visuellement une fois rendu — un nom de groupe trop long
  pourrait déborder du cadre dans ERetroDesign, à observer sur le rendu
  réel avant de figer le format). Le groupe Pont redresseur portera
  potentiellement DEUX notes concaténées (simple + système) : vérifier
  concrètement sur le rendu que la longueur reste lisible, sinon
  reconsidérer au moment du plan (ex. ne garder que la note système,
  plus informative, quand les deux sont présentes).
- Faut-il aussi enrichir `rapport.py` (le rapport texte) dans la foulée,
  maintenant que la logique existe, ou strictement la garder hors
  périmètre pour cette itération comme décidé ? Décision explicite du
  boss à cette étape : hors périmètre, mais la fonction `interpreter`
  étant un module séparé et pur, rien n'empêche `rapport.py` de
  l'appeler plus tard sans aucune modification de ce chantier.
