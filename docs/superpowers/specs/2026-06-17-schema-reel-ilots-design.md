# Schema reel des ilots - Design

## Objectif

Afficher chaque ilot fonctionnel comme un schema electronique reel depuis l'onglet Analyse, en utilisant les composants et les nets du graphe analyse.

## Portee

- Ajouter un bouton d'ouverture de schema dans chaque section "Structure en etages".
- Ouvrir une fenetre semblable au visualiseur de circuits existant.
- Dessiner tous les composants de l'ilot, pas seulement les circuits detectes.
- Conserver les rails comme labels visibles (`GND`, `VCC`, etc.) sans les utiliser pour fusionner les ilots.
- Permettre l'export PNG/SVG comme les schemas de circuits.

## Architecture

Le rendu sera ajoute dans `gui/circuit_viewer.py`, pres du visualiseur schemdraw existant. Une fonction pure construira un modele de dessin a partir de `(ilot, graph, comp_info)` : refs de composants, nets internes/rails et edges composant-net. Le rendu graphique consommera ce modele pour dessiner un schema lisible avec composants en colonnes, bornes de nets, fils simples et labels.

`gui/tab_analyze.py` passera le graphe et `comp_info` aux sections d'ilots. Chaque `_IslandSection` ajoutera un bouton "Schema ilot" qui appelle le nouveau visualiseur.

## Contraintes

- Pas de nouvelle dependance : utiliser `schemdraw`, `matplotlib`, `customtkinter` deja presents.
- Le rendu doit toujours afficher quelque chose, meme pour un ilot complexe.
- Les tests verifient la construction du modele de schema, pas le rendu pixel.
- Le build PyInstaller doit continuer a passer avec le smoke test CLI.
