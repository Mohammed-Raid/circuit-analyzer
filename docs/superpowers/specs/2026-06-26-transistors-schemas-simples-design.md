# Transistors — schémas simples (retrait des boîtes Z)

**Date :** 2026-06-26
**Statut :** approuvé

## Objectif

Remplacer le dessin « riche » des montages transistor (boîtes Z bleues
cliquables + drill-down) par des **schémas simples** : symboles classiques de
composants + petit titre du montage. Le boss veut du simple et lisible pour les
transistors, pas le traitement impédance des AOP.

## Portée
- **Focus (soignés) :** les 3 montages BJT de base —
  « Transistor en commutation », « Amplificateur émetteur commun »,
  « Collecteur commun (suiveur d'émetteur) ».
- **Aussi simplifiés (cohérence) :** push-pull, Darlington, miroir de courant,
  commande de relais, MOSFET commutation, MOSFET côté-haut.
- **Plus tard :** traitement dédié MOSFET / JFET / etc.
- **Hors périmètre :** la détection (inchangée) ; les drawers AOP (gardent leurs
  boîtes Z `_z_box` / `_z_hitboxes`).

## Style cible
Symboles normaux (`elm.Resistor`, `elm.BjtNpn`, `elm.NFet`, …), étiquettes
`IN / OUT / VCC / GND` et `nom = valeur` (ex. `Rb = 10k`), titre du montage
au-dessus. Pas de boîte Z, pas de hitbox cliquable sur les passifs transistor.

## Changements techniques
1. Helper `_r_simple(d, ref, ci, p1, p2, nom, loc="top")` : dessine
   `elm.Resistor().at(p1).to(p2)` avec étiquette `« nom = valeur »`. Même
   signature que `_z_passif` → remplacement quasi mécanique aux points d'appel.
2. Remplacer tous les appels `_z_passif(...)` par `_r_simple(...)` dans les
   drawers transistor / MOSFET (commutation BJT, émetteur commun, suiveur,
   Darlington, commande relais, MOSFET commutation, MOSFET côté-haut).
3. Conserver `_titre_montage` (titre du montage).
4. Supprimer `_z_passif` une fois inutilisé. `_z_box` / `_z_hitboxes` restent
   (utilisés par les AOP).
5. `tests/test_transistor_drawing.py` : retirer les assertions « ≥ 2 boîtes Z »,
   vérifier à la place la présence des étiquettes de résistance + titre + rendu
   sans « Schéma non disponible ».

## Critère de réussite
- Les drawers transistor rendent sans « Schéma non disponible ».
- Aucune boîte Z / hitbox sur les passifs transistor (`fig._z_hitboxes` vide
  pour ces montages).
- Le titre du montage apparaît ; les résistances portent `nom = valeur`.
- PNG vérifiés pour les 3 montages BJT de base.
- Suite de tests verte.
