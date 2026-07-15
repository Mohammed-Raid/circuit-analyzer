# Onglet « Saisie » — création rapide de circuits au clavier

Date : 2026-07-15
Statut : validé (design approuvé en session : tableau netlist + insertion
catalogue, nouvel onglet dédié, remplace le passage par BoardSCH/canvas pour
la SAISIE de circuits)

## 1. Objectif

Construire un circuit complet dans l'app, au clavier, sans BoardSCH externe
et sans le canvas Dessiner : un tableau type netlist (une ligne par
composant, connexions par noms de nets), l'insertion de puces réelles depuis
le catalogue constructeur, l'enregistrement en XML BoardSCH standard et
l'analyse directe.

Périmètre : la SAISIE/ÉDITION de circuits. HORS périmètre : le canvas
Dessiner (intouché), l'onglet Composants (bibliothèque de types, intouché),
tout rendu schématique dans l'onglet (l'aperçu, c'est l'analyse).

## 2. UX

### 2.1 Onglet

5e onglet « Saisie » (après Composants), construit comme les autres
(ui_kit + tokens theme, AUCUN hex en dur). Barre d'actions en haut :
[+ Composant] [+ Puce réelle] [Ouvrir…] [Enregistrer] [Analyser] ;
zone tableau scrollable au centre ; barre d'état en bas (nom de fichier
courant, nombre de composants, avertissements de validation).

### 2.2 Tableau

- Colonnes : `Ref | Type | Valeur | Broche 1..N | ✕` (suppression de ligne).
- `Ref` : proposée automatiquement au choix du type (`R1`, `R2`, `C1`,
  `U1`… — premier index libre par préfixe de type), éditable, unicité
  validée.
- `Type` : menu des types de `charger_bibliotheque()` (défauts +
  personnalisés) — la liste suit la bibliothèque, jamais de liste codée en
  dur. Changer le type reconstruit les champs de broches de la ligne
  (noms de broches du type : Q → B/C/E, D → A/K…).
- `Valeur` : texte libre, pré-remplie avec la valeur par défaut du type
  quand elle existe (mêmes défauts que la palette du canvas).
- Champs broches : un par broche du type, libellé par le nom de broche.
  AUTOCOMPLÉTION des nets : suggestions = nets déjà saisis dans le tableau
  + rails standard (VIN, VOUT, VCC, GND). Champ vide = broche non câblée
  (convention existante : net singleton `NET#` à la génération, cf. mémoire
  catalogue).
- Clavier : Tab avance de champ en champ ; Entrée sur le dernier champ d'une
  ligne ajoute une ligne du même type ; bouton ✕ supprime la ligne.

### 2.3 Insertion catalogue (« + Puce réelle »)

Popup liste (filtrable au clavier) construite depuis
`circuit_analyzer.catalogue` : entrées exactes U (NE555, LM393, LM339,
PC817, LM317), familles 74HC/74HCT connues (00/08/32/04/74/157/138),
suffixes U (741, 1458, x458, 7805, 7812), transistors (2N2222, BC547,
2N3904), MOSFET (IRFZ44N, BS170, IRLZ44N), diodes (1N4148, 1N4007), LED
(rouge/verte/bleue). La liste est DÉRIVÉE des tables du catalogue (pas de
duplication : exposer un itérateur public `catalogue.entrees_catalogue()`
qui yield (type_, value, entree)).

Sélection → une ligne est insérée :
- U : type U, valeur = référence constructeur, broches NUMÉROTÉES du
  boîtier (fidèle au flux réel — l'aliasing/identification existants font
  le reste à l'analyse), chaque champ broche libellé `n (FONCTION)` d'après
  `entree["broches"]` (ex. `2 (TRIG)`), fonction purement indicative ;
- Q/M/D : type correspondant, valeur = référence (broches B/C/E, G/D/S,
  A/K du type) ;
- LED : type D, valeur `LED rouge|verte|bleue`.

### 2.4 Ouvrir / Enregistrer / Analyser

- Ouvrir : dialogue fichier sur `custom_circuits/` (XML) ; `lire_xml` SANS
  aliasing catalogue (lecture BRUTE des broches pour l'édition — voir §3.3) ;
  les lignes remplissent le tableau. Tout XML lisible par l'app s'ouvre,
  fixtures comprises.
- Enregistrer : `generer_xml(composants)` vers `custom_circuits/<nom>.xml`
  (dialogue si pas de nom courant). Rafraîchit l'onglet Circuits (même
  callback croisé que les autres onglets, cf. app_window `_on_lib_change`/
  `refresh_circuits`).
- Analyser : enregistre (fichier temporaire dans le dossier de config si
  pas de nom) puis appelle le même callback que TabDraw
  (`on_analyze(path)` → l'onglet Analyser charge et lance l'analyse).

### 2.5 Validation (barre d'état, en continu)

- BLOQUANT (Enregistrer/Analyser grisés + message) : refs vides ou en
  double ; ligne sans type.
- AVERTISSEMENT (non bloquant) : nets singletons (« NET3 n'apparaît qu'une
  fois ») ; tableau vide.

## 3. Architecture

### 3.1 Fichiers

```
circuit_analyzer/saisie.py   (NOUVEAU, modèle PUR : aucun import tkinter/
                              customtkinter/matplotlib — testable headless)
gui/tab_quick_entry.py       (NOUVEAU : widgets uniquement, délègue tout
                              calcul au modèle)
circuit_analyzer/catalogue.py (ÉTENDU : entrees_catalogue() public)
gui/app_window.py            (MODIFIÉ : 5e onglet + câblages croisés)
```

### 3.2 Modèle (`circuit_analyzer/saisie.py`)

```python
@dataclass
class LigneSaisie:
    ref: str
    type: str
    value: str
    pins: dict[str, str]        # nom de broche -> net ("" = non câblée)
    fonctions: dict[str, str]   # nom de broche -> fonction indicative ("" si aucune)

class ModeleSaisie:
    lignes: list[LigneSaisie]
    def ref_auto(self, type_) -> str            # premier index libre par préfixe
    def ajouter(self, type_, value="", pins=None, fonctions=None) -> LigneSaisie
    def ajouter_catalogue(self, type_, value) -> LigneSaisie   # broches/fonctions du catalogue
    def supprimer(self, index) -> None
    def nets_connus(self) -> list[str]          # tri stable, rails d'abord
    def valider(self) -> tuple[list[str], list[str]]   # (bloquants, avertissements)
    def vers_composants(self) -> list[Composant]       # pins vides exclues
    @classmethod
    def depuis_composants(cls, comps) -> "ModeleSaisie"
```

Round-trip contractuel : `depuis_composants(lire_xml(generer_xml(
m.vers_composants())))` reproduit refs/types/valeurs et la TOPOLOGIE des
nets câblés (quelles broches partagent le même net), PAS les noms de nets
internes : le format BoardSCH ne porte aucun nom de net interne
(`lire_xml`/`nom_net()` ne nomme que les rails, le reste redevient `NET#`
à la relecture). Les broches vides ↔ nets singletons `NET#` re-masqués à
la relecture restent tels quels (convention existante).

### 3.3 Lecture sans aliasing

`lire_xml` applique `appliquer_catalogue` (741 → IN-/IN+/OUT…). Pour
l'ÉDITION on veut les broches du fichier telles quelles. `lire_xml` gagne
un paramètre `alias_catalogue=True` (défaut inchangé — AUCUN appelant
existant ne change) ; l'onglet Saisie lit avec `alias_catalogue=False`.
Un composant aux broches déjà nommées (AOP IN+/IN-/OUT d'un XML canvas)
s'édite tel quel : les champs broches suivent les CLEFS du composant lu,
pas le type théorique.

### 3.4 Onglet (`gui/tab_quick_entry.py`)

- `TabQuickEntry(parent, on_analyze=None, on_saved=None)` — même signature
  d'intégration que TabDraw.
- Lignes = cadre par ligne dans un conteneur scrollable léger (même
  technique tk.Canvas que tab_analyze) ; chaque champ net = combobox
  éditable alimentée par `modele.nets_connus()` au focus.
- L'onglet ne calcule RIEN : refs, validation, conversion = modèle.
- Popup catalogue : CTkToplevel, Entry filtre + Listbox, Entrée valide.

### 3.5 app_window

5e onglet « Saisie » ; `on_analyze` branché comme TabDraw ;
`on_saved` → `tab_c.refresh_circuits()`. L'ordre des `_frames` et la barre
de navigation suivent le pattern existant.

## 4. Ce qui ne change pas

- Le canvas Dessiner, l'onglet Composants, l'analyseur, le format XML.
- `generer_xml`/`lire_xml` : seul l'ajout du paramètre opt-out d'aliasing
  (§3.3), rétro-compatible.
- Aucune dépendance nouvelle.

## 5. Tests (TDD)

`tests/test_saisie.py` (modèle pur, sans display) :
1. `ref_auto` : R1 puis R2 ; U1 après suppression de U1 → U1 réutilisé.
2. `ajouter_catalogue("U", "NE555")` : 8 broches numérotées, fonctions
   TRIG/OUT... ; `("D", "LED rouge")` : broches A/K.
3. `valider` : ref en double = bloquant ; net singleton = avertissement.
4. Round-trip §3.2 sur un circuit mixte (R, Q, U catalogue, broche vide).
5. `nets_connus` : rails d'abord, puis nets saisis triés, sans doublons.
6. Pureté d'import (pattern schema_grid : subprocess sans tkinter).
7. `lire_xml(..., alias_catalogue=False)` : reel_741_inverseur garde ses
   broches 2/3/6/7/4 ; défaut True inchangé (broches IN-/IN+...).
8. `catalogue.entrees_catalogue()` : contient NE555, 74HC00, 2N2222,
   LED rouge ; chaque entrée cohérente avec `identifier()`.

`tests/test_tab_quick_entry.py` (Tk, skip sans display, style
test_island_viewport) :
9. L'onglet se construit ; ajouter un R crée les champs 1/2 ; changer le
   type en Q reconstruit B/C/E.
10. Insertion catalogue NE555 → 8 champs libellés `n (FONCTION)`.
11. Enregistrer écrit un XML relu par `lire_xml` (même nombre de
    composants) ; Analyser appelle `on_analyze` avec le chemin.
12. Validation UI : ref dupliquée grise Analyser.

## 6. Risques et décisions

- Combobox nets : autocomplétion simple (liste au focus + préfixe), pas de
  fuzzy — YAGNI.
- Perf : cadres par ligne OK ≤ ~100 lignes (corpus démo ≤ 30) ; pas de
  virtualisation.
- Les XML BoardSCH générés par `generer_xml` restent la source de vérité :
  pas de format de sauvegarde parallèle.
- Broches vides ↔ nets singletons : convention existante réutilisée telle
  quelle (documentée dans le contrat round-trip).
