# Démos industrielles réalistes — montages AOP restants

**Date :** 2026-06-25
**Statut :** approuvé

## Objectif

Fournir une démo industrielle *réaliste* (scénario d'application réel, nœuds
nommés, valeurs plausibles, en-tête de commentaires) pour chaque montage AOP qui
n'en avait qu'une fixture scolaire ou aucune. Schmitt et comparateur ont déjà
leur démo réaliste (`conditionneur_capteur_schmitt`, `detecteur_surtension`).

## Périmètre — 7 montages

| Fichier (`.txt` + `.xml`)        | Montage       | Scénario industriel                                              | Topologie / gain                         |
|----------------------------------|---------------|-----------------------------------------------------------------|------------------------------------------|
| `ampli_shunt_inverseur`          | Inverseur     | Mise en forme de la chute d'un shunt de courant avant l'ADC     | Rin 10k + Rf 100k, IN+→GND, gain −10     |
| `ampli_capteur_non_inverseur`    | Non-inverseur | Ampli de capteur haute impédance (pont de jauge / photodiode)   | Rf 10k + Rg 1k, signal→IN+, gain ×11     |
| `integrateur_consigne`           | Intégrateur   | Cœur intégrateur de boucle PI / générateur de rampe de consigne | Rin 10k + Cf 100n                        |
| `derivateur_choc`                | Dérivateur    | Détecteur de taux de variation / front (choc accéléromètre)     | Cin 100n + Rf 100k                       |
| `sommateur_offset`               | Sommateur     | Sommation signal + offset de calibration (mélangeur)            | 3×R 10k + Rf 10k, IN+→GND                |
| `ampli_diff_shunt`               | Différentiel  | Mesure de courant sur shunt, réjection du mode commun           | R1/Rf/R3/Rg, gain diff 10                |
| `buffer_reference`               | Suiveur       | Buffer d'impédance d'une réf. de tension (pont haute-Z) → ADC   | OUT→IN−, pont Rd1/Rd2 100k sur IN+       |

## Approche

- Chemin `.txt` lisible → `netlist_to_xml.py` → XML (même pipeline que les 3 démos
  récentes), pas le générateur programmatique `generate_test_circuits.py`.
- Noms de fichiers basés sur le scénario (cohérent avec `detecteur_surtension`).
- Chaque `.txt` porte un en-tête de commentaires décrivant le rôle industriel.
- Non-destructif : les vieilles fixtures scolaires (`summing_aop`, `differential_aop`,
  `integrator_aop`, …) restent en place ; leur éventuel retrait est une décision de
  nettoyage séparée.

## Critère de réussite

Pour chaque démo, l'analyseur (`construire_graphe` + `analyser`) détecte le
`circuit_type` attendu listé ci-dessus, plus « Impédance Z » pour les passifs.
Vérifié par un test paramétré.

## Point de vigilance

Suiveur : le pont diviseur sur IN+ pourrait être lu comme un non-inverseur. Si la
détection échoue, rabattre sur un suiveur minimal (signal direct sur IN+) et
décrire le pont en commentaire uniquement.

## Hors périmètre

- Pas de drawer dédié intégrateur/dérivateur (ils se dessinent déjà correctement
  via le drawer inverseur partagé `_draw_aop_inverseur_zin_zf`).
- Pas de refonte du pipeline de génération XML.
