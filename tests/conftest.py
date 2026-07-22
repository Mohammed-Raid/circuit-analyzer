"""Configuration pytest partagee.

Isole TOUS les tests du fichier `custom_circuits.json` REEL de l'utilisateur
(donnee runtime ecrite a la racine de l'application par la fonctionnalite
« circuits personnalises »). Sans cette isolation, un pattern perso du boss --
p.ex. « Potentionmetre » qui matche tout composant de type X -- est charge par
`detecteur.analyser` / `match_patterns` via le chemin par defaut et fait
echouer les tests d'analyse/rapport qui supposent l'absence de pattern perso
(ex. `test_rapport_etages_...` : un X non classifie doit tomber en « Autres »,
pas « Potentionmetre »).

Les tests qui exercent EXPLICITEMENT les circuits perso re-`monkeypatch`ent
`chemin_custom_circuits` vers leur propre `tmp_path` : leur setattr, applique
apres celui-ci sur le meme `monkeypatch`, l'emporte -- ils ne sont pas affectes.
"""
import pytest


@pytest.fixture(autouse=True)
def _isole_custom_circuits_reel(request, monkeypatch, tmp_path_factory):
    """@brief Pointe `chemin_custom_circuits` vers un fichier tmp inexistant
    (donc aucune definition perso chargee) pour tout test, afin qu'aucun test
    ne lise la vraie `custom_circuits.json` de la machine.

    Exclusion : les modules qui exercent EUX-MEMES la resolution du chemin des
    circuits perso (test de la fonction, ou redirection via sys.frozen/executable,
    ou monkeypatch de leur propre tmp) gerent deja leur isolation -- patcher la
    fonction casserait leur mise en place. On les laisse intacts."""
    _MODULES_GERENT_LE_CHEMIN = (
        "test_chemins",         # teste chemin_custom_circuits() lui-meme
        "test_matcher",         # redirige via sys.frozen/executable (fonction reelle requise)
        "test_custom_circuits",  # feature circuits perso (chemins explicites)
        "test_pattern_refresh",  # monkeypatche son propre tmp
    )
    if any(m in request.node.nodeid for m in _MODULES_GERENT_LE_CHEMIN):
        return
    from custom_circuits import loader
    vide = tmp_path_factory.mktemp("cc_isolation") / "custom_circuits.json"
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: vide)
