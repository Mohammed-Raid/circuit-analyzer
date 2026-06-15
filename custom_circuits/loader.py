"""
@file loader.py
@brief Chargement, sauvegarde et matching des circuits personnalisés (créés via l'interface).
"""
import json
from pathlib import Path
from circuit_analyzer.chemins import racine_application
from circuit_analyzer.patterns.base import Pattern, is_gnd, is_power

CUSTOM_CIRCUITS_FILE = 'custom_circuits.json'


def chemin_custom_circuits() -> Path:
    """@brief Chemin par défaut du fichier des circuits personnalisés.

    À la racine de l'application (à côté de l'exe une fois gelée), pas au CWD.

    @return Path Chemin de custom_circuits.json.
    """
    return racine_application() / CUSTOM_CIRCUITS_FILE

CONDITION_LABELS = [
    "C connecté à GND",
    "R en série",
    "R vers alimentation",
    "Émetteur/Source à GND",
    "Feedback OUT→IN-",
]

# Explication courte affichée sous chaque case dans l'onglet Circuits : les
# libellés ci-dessus sont trop laconiques pour un non-initié. Toute entrée de
# CONDITION_LABELS doit avoir sa description ici (garanti par un test).
CONDITION_DESCRIPTIONS = {
    "C connecté à GND":       "un condensateur du circuit touche la masse",
    "R en série":             "une résistance partage un nœud avec un autre composant",
    "R vers alimentation":    "une résistance est reliée à un rail d'alimentation",
    "Émetteur/Source à GND":  "l'émetteur (BJT) ou la source (MOSFET) est à la masse",
    "Feedback OUT→IN-":       "la sortie de l'AOP reboucle sur l'entrée inverseuse",
}


def load_custom_circuits(path=None) -> list[dict]:
    """@brief Charge les définitions de circuits personnalisés depuis le JSON.

    @param path Chemin du fichier (défaut : chemin_custom_circuits()).
    @return list[dict] Liste des définitions, ou [] si le fichier est absent.
    """
    p = Path(path) if path is not None else chemin_custom_circuits()
    if not p.exists():
        return []
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def save_custom_circuits(circuits: list[dict], path=None) -> None:
    """@brief Sauvegarde les définitions de circuits personnalisés en JSON (UTF-8).

    @param circuits Liste des définitions à écrire.
    @param path Chemin du fichier (défaut : chemin_custom_circuits()).
    @return None
    """
    p = Path(path) if path is not None else chemin_custom_circuits()
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(circuits, f, ensure_ascii=False, indent=2)


def get_custom_patterns(path=None) -> list['CustomCircuitPattern']:
    """@brief Construit les objets Pattern à partir des définitions personnalisées.

    @param path Chemin du fichier JSON (défaut : chemin_custom_circuits()).
    @return list[CustomCircuitPattern] Un pattern par définition chargée.
    """
    return [CustomCircuitPattern(d) for d in load_custom_circuits(path)]


class CustomCircuitPattern(Pattern):
    """@brief Pattern défini par l'utilisateur (types de composants requis + conditions topologiques)."""

    def __init__(self, definition: dict):
        """@brief Construit le pattern depuis sa définition JSON.

        @param definition Dict {'name', 'components', 'conditions'}.
        """
        self._name = definition['name']
        self._required_types = set(definition.get('components', []))
        self._conditions = list(definition.get('conditions', []))

    @property
    def name(self) -> str:
        """@brief Nom du circuit personnalisé.
        @return str Nom affiché du pattern.
        """
        return self._name

    def match(self, graph) -> list[dict]:
        """@brief Recherche le circuit personnalisé dans le graphe.

        Exige que tous les types requis soient présents et que toutes les
        conditions topologiques soient satisfaites.

        @param graph Le MultiGraph NetworkX du circuit.
        @return list[dict] Un match {'components', 'nodes'} si tout est satisfait, sinon [].
        """
        all_comps = graph.graph.get('components', {})
        found = {ref: comp for ref, comp in all_comps.items()
                 if comp.type in self._required_types}

        if not found:
            return []

        found_types = {comp.type for comp in found.values()}
        if not self._required_types.issubset(found_types):
            return []

        for condition in self._conditions:
            if not self._check_condition(condition, graph, found):
                return []

        return [{'components': list(found.keys()), 'nodes': []}]

    def _check_condition(self, condition: str, graph, found: dict) -> bool:
        """@brief Vérifie une condition topologique sur les composants trouvés.

        @param condition Libellé de la condition (cf. CONDITION_LABELS).
        @param graph Le MultiGraph NetworkX du circuit.
        @param found Dict {ref -> Composant} des composants des types requis.
        @return bool True si la condition est satisfaite ; False si non remplie ou inconnue.
        """
        if condition == "C connecté à GND":
            for u, v, d in graph.edges(data=True):
                if d['type'] == 'C' and d['ref'] in found:
                    if is_gnd(u) or is_gnd(v):
                        return True
            return False

        if condition == "R vers alimentation":
            for u, v, d in graph.edges(data=True):
                if d['type'] == 'R' and d['ref'] in found:
                    if is_power(u) or is_power(v):
                        return True
            return False

        if condition == "Émetteur/Source à GND":
            for ref, comp in found.items():
                if comp.type == 'Q':
                    e = comp.pins.get('E', '')
                    if e and is_gnd(e):
                        return True
                elif comp.type == 'M':
                    s = comp.pins.get('S', '')
                    if s and is_gnd(s):
                        return True
            return False

        if condition == "Feedback OUT→IN-":
            for ref, comp in found.items():
                if comp.type == 'U':
                    inm = comp.pins.get('IN-')
                    out = comp.pins.get('OUT')
                    if inm and out:
                        for u, v, d in graph.edges(inm, data=True):
                            other = v if u == inm else u
                            if other == out:
                                return True
            return False

        if condition == "R en série":
            r_refs = {ref for ref, comp in found.items() if comp.type == 'R'}
            other_comps = {ref: comp for ref, comp in found.items() if comp.type != 'R'}
            for r_ref in r_refs:
                r_nets = set(found[r_ref].pins.values())
                for o_comp in other_comps.values():
                    if r_nets & set(o_comp.pins.values()):
                        return True
            return False

        # Unknown condition — fail safe rather than silently accepting
        return False
