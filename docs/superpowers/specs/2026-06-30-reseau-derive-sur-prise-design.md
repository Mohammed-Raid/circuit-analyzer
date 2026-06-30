# Réseau dérivé sur prise (diviseurs de référence + filtrage de rail)

Date : 2026-06-30
Sous-projet : robustesse visuelle des îlots — défaut #2 de l'audit ChatGPT.

## Problème

Les réseaux passifs accrochés aux rails d'alimentation (diviseurs de référence,
filtrages d'alim) tombent dans la **vue grille générique**, que le boss refuse, et
sont parfois **éclatés en plusieurs îlots**. Trois formes constatées dans le corpus :

- **α — diviseur de référence pur** : `R_haut (VCC→VREF)` + `R_bas (VREF→GND)`.
  Le point milieu `VREF` alimente un étage actif (entrée d'AOP/comparateur).
  Présent dans `ilot_tous_aop`, `detecteur_surtension`, `conditionneur_capteur_schmitt`,
  `chaine_conditionnement`, `buffer_reference`.
- **β — diviseur + découplage** : `R_haut` + `R_bas` + condensateur de bypass sur
  la prise. Présent dans `anti_alias_filter` (R6 + R7 + C7 sur `VREF_2V5`).
- **γ — filtrage de rail** : résistance série entre deux rails + condensateurs vers
  GND, sans résistance vers GND. Présent dans `anti_alias_filter`
  (R4 `VCC_5V→AVCC`, C4/C5 `AVCC→GND`).

### Cause racine (vérifiée)

`VREF`, `VREF_2V5`, `AVCC` sont classés `is_power_net=True` → traités comme rails
→ `_net_signal=False`. Dans `detecter_ilots`, les rail-passifs sont groupés par leur
**premier rail alphabétique** : `R_haut` (rails `VCC`,`VREF` → bucket `VCC`) et
`R_bas` (rails `VREF`,`GND` → bucket `VREF`) tombent dans deux îlots séparés. Le cas γ,
lui, est déjà groupé (tous ses composants partagent `AVCC` comme premier rail).

## Concept retenu : « réseau dérivé sur prise »

Les trois formes ont la même topologie :

```
   <rail source>
        |
   [ Z série ]        (R_haut, ou R4)
        |
        ├──● <prise> →   (VREF / VREF_2V5 / AVCC ; sort vers l'étage consommateur)
        |
   [ Z shunt ]        (R_bas ; ou R7//C7 ; ou C4//C5)
        |
       GND
```

Un **seul** drawer couvre α/β/γ. Les deux blocs Z (série et shunt) réutilisent les
boîtes Z cliquables existantes (drill-down R/L/C). La prise est un nœud étiqueté avec
le nom du net dérivé, avec un moignon horizontal « → » indiquant qu'elle alimente un
étage situé dans un autre îlot (on ne fusionne PAS avec l'AOP — choix « diviseur dédié »).

## A. Détection des nets dérivés — `_nets_derives(graphe)`

Nouveau helper (dans `circuit_analyzer/ilots.py`).

Un net `N` est une **prise dérivée** si :

1. `N` est un net d'alimentation (`is_power_net(N)`) et `N ≠ GND` ; **et**
2. il existe un composant passif (type ∈ {R, L, C}) entre `N` et GND ; **et**
3. il existe un composant passif entre `N` et un autre net d'alimentation `M`
   (`M ≠ N`, `M ≠ GND`).

Retour : `set[str]` des nets-prises.

Validation corpus :
- `VREF` ← R16(→VCC), R17(→GND) : (2) R17 vers GND ✓, (3) R16 vers VCC ✓ → **prise**.
- `VREF_2V5` ← R6(→VCC_5V), R7(→GND), C7(→GND) : ✓✓ → **prise**.
- `AVCC` ← R4(→VCC_5V), C4/C5(→GND) : (2) caps vers GND ✓, (3) R4 vers VCC_5V ✓ → **prise**.
- `VCC`, `VCC_5V`, `VBUS` : pas de passif vers GND dans leur réseau → **pas** prise. ✓

Tiebreak (rare, hors corpus) : si dans un même réseau plusieurs nets satisfont (1-3)
— par exemple un `VCC` portant un cap de découplage local **et** une résistance de
diviseur — la prise est le net de **plus faible degré** (nombre de composants attachés) ;
à degré égal, on conserve les deux comme prises (le drawer en empilera deux étages).
*Limite documentée* : ce cas n'existe pas dans le corpus actuel ; le tiebreak est un
garde-fou, pas une fonctionnalité validée.

## B. Regroupement d'îlots — `detecter_ilots`

Étape 2 (composants rail-only) modifiée : la **clé de bucket** d'un composant
rail-passif devient le **net-prise qu'il touche** s'il en touche un, sinon son premier
rail (comportement actuel).

- `R_haut` touche `VREF` (prise) → bucket `VREF`.
- `R_bas` touche `VREF` (prise) → bucket `VREF`.
- → un seul îlot `{R_haut, R_bas}`. Idem β `{R6, R7, C7}` et γ `{R4, C4, C5}`.

Le libellé de ces îlots reste « alimentation <prise> » (déjà cohérent). La catégorie
n'a pas besoin de changer : le routage se fait sur la **forme**, pas sur la catégorie.

Aucun impact sur les îlots signal (les nets-prises restent des rails côté `_net_signal`,
donc ils ne fusionnent pas les étages actifs entre eux).

## C. Reconnaissance de forme — `_reseau_derive_ilot(ilot, graphe)`

Nouveau recognizer (dans `gui/circuit_viewer.py`), appelé dans `show_island` **avant**
le repli grille générique (après principal / série-parallèle / pont).

Renvoie `None` si l'îlot n'est pas un réseau dérivé, sinon :

```python
{
  "top":   "VCC",          # rail source (net d'alim ≠ prise ≠ GND le plus représenté en série)
  "prise": "VREF",         # net dérivé
  "serie": {"refs": [...], "composition": "R16"},      # passifs prise↔rail source
  "shunt": {"refs": [...], "composition": "R17"},      # passifs prise↔GND (caps inclus : C4//C5 pour γ)
}
```

Construction :
- `prise` = l'unique net dérivé de l'îlot (intersection `_nets_derives` ∩ nets de l'îlot).
- `serie` = passifs reliant `prise` à un net d'alim ≠ GND ; `top` = cet autre net.
- `shunt` = passifs reliant `prise` à GND.
- `composition` de chaque côté via la machinerie d'impédance existante
  (`impedance` : série/parallèle des refs), réutilisable par le drill-down.

Si la forme ne se réduit pas (ex. > 1 prise, topologie inattendue), renvoyer `None`
→ repli grille générique (pas de régression).

## D. Dessin — `_draw_reseau_derive(...)`

Nouveau drawer (dans `gui/circuit_viewer.py`), même langage visuel que les autres :
- rail `top` en haut (drapeau d'alim), `GND` en bas (symbole terre) ;
- boîte Z bleue cliquable pour `serie`, puis nœud **prise** (point + label `<prise> →`
  avec moignon horizontal court), puis boîte Z bleue cliquable pour `shunt` ;
- `fig._z_hitboxes` peuplé pour les deux boîtes (drill-down R/L/C au clic) ;
- légende « cliquez un Z… » comme les autres vues.

## E. Tests (TDD)

`tests/test_ilots.py` :
- `test_nets_derives_reconnait_diviseur` : VREF prise, VCC non.
- `test_nets_derives_filtrage_rail` : AVCC prise (caps vers GND comptent).
- `test_diviseur_reference_un_seul_ilot` : R_haut + R_bas dans le même îlot.
- non-régression : un VCC→GND décible seul reste un îlot d'alim (pas une prise).

`tests/test_island_viewer.py` (ou nouveau `test_reseau_derive.py`) :
- `test_reseau_derive_reconnu` : `_reseau_derive_ilot` renvoie top/prise/serie/shunt corrects.
- `test_reseau_derive_non_reconnu_repli` : îlot quelconque → `None`.
- `test_draw_reseau_derive_sans_exception_et_hitboxes` : figure produite, 2 hitboxes Z.
- `test_show_island_route_vers_reseau_derive` : intégration via un îlot diviseur.

Vérification visuelle obligatoire : re-rendre les ~10 îlots concernés (tous_aop,
anti_alias, surtension, schmitt, conditionnement, buffer) et inspecter les PNG.

## Hors périmètre (YAGNI)

- Fusion du diviseur avec l'étage actif consommateur (choix « diviseur dédié »).
- Diviseurs à plus de 2 étages / prises multiples (tiebreak en garde-fou seulement).
- Renommage automatique des prises.
