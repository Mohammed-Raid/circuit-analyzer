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

# Clés stables des conditions : servent à la fois d'identifiant dans
# _check_condition ET de valeur stockée dans custom_circuits.json. NE PAS
# renommer (casserait les patterns sauvegardés) — l'affichage clair passe par
# CONDITION_DISPLAY. Le doublon « Transistor émetteur à GND » (sous-cas exact de
# « Émetteur/Source à GND ») n'est plus proposé, mais reste géré en alias dans
# _check_condition pour les patterns déjà enregistrés.
CONDITION_LABELS = [
    "C connecté à GND",
    "R en série",
    "R vers alimentation",
    "Émetteur/Source à GND",
    "Feedback OUT→IN-",
    "Au moins 2 résistances",
    "Au moins 2 condensateurs",
    "R et C connectés au même nœud signal",
    "Diode cathode sur alimentation",
    "Pas de transistor dans le circuit",
    "Self (inductance) présente",
    "Relais présent",
]

# Libellé clair affiché à l'utilisateur (clé stable → français lisible).
CONDITION_DISPLAY = {
    "C connecté à GND":                     "Un condensateur relié à la masse",
    "R en série":                           "Une résistance en série avec un autre composant",
    "R vers alimentation":                  "Une résistance reliée à l'alimentation (VCC)",
    "Émetteur/Source à GND":                "Émetteur (transistor) ou source (MOSFET) à la masse",
    "Feedback OUT→IN-":                     "Contre-réaction : la sortie de l'AOP revient sur l'entrée −",
    "Au moins 2 résistances":               "Au moins 2 résistances",
    "Au moins 2 condensateurs":             "Au moins 2 condensateurs",
    "R et C connectés au même nœud signal": "Une résistance et un condensateur sur le même fil",
    "Diode cathode sur alimentation":       "Cathode de la diode reliée à l'alimentation",
    "Pas de transistor dans le circuit":    "Aucun transistor dans le circuit",
    "Self (inductance) présente":           "Une bobine (inductance) est présente",
    "Relais présent":                       "Un relais est présent",
}

# Regroupement en familles pour l'affichage (couvre exactement CONDITION_LABELS).
CONDITION_GROUPS = [
    ("Présence de composants", [
        "Au moins 2 résistances",
        "Au moins 2 condensateurs",
        "Self (inductance) présente",
        "Relais présent",
        "Pas de transistor dans le circuit",
    ]),
    ("Masse & alimentation", [
        "C connecté à GND",
        "R vers alimentation",
        "Émetteur/Source à GND",
        "Diode cathode sur alimentation",
    ]),
    ("Câblage", [
        "R en série",
        "R et C connectés au même nœud signal",
        "Feedback OUT→IN-",
    ]),
]


def condition_display(cle) -> str:
    """@brief Libellé clair d'une condition, nommée (str) ou générique (dict).

    @param cle Clé stable (str, cf. CONDITION_LABELS) ou condition générique (dict).
    @return str Libellé lisible, ou la clé brute si une condition nommée est absente.
    """
    if isinstance(cle, dict):
        return condition_display_generique(cle)
    return CONDITION_DISPLAY.get(cle, cle)

# Explication courte affichée sous chaque case dans l'onglet Circuits. Toute
# entrée de CONDITION_LABELS doit avoir sa description ici (garanti par un test).
CONDITION_DESCRIPTIONS = {
    "C connecté à GND":                   "un condensateur du circuit touche la masse",
    "R en série":                         "une résistance partage un nœud avec un autre composant",
    "R vers alimentation":                "une résistance est reliée à un rail d'alimentation",
    "Émetteur/Source à GND":              "l'émetteur (BJT) ou la source (MOSFET) est à la masse",
    "Feedback OUT→IN-":                   "la sortie de l'AOP reboucle sur l'entrée inverseuse",
    "Au moins 2 résistances":             "le circuit contient au minimum deux résistances",
    "Au moins 2 condensateurs":           "le circuit contient au minimum deux condensateurs",
    "R et C connectés au même nœud signal": "une résistance et un condensateur partagent un nœud non-rail",
    "Diode cathode sur alimentation":     "la cathode de la diode est reliée à un rail positif (VCC)",
    "Pas de transistor dans le circuit":  "aucun BJT ni MOSFET n'est présent dans les composants requis",
    "Self (inductance) présente":         "une self (type L) fait partie du circuit",
    "Relais présent":                     "un relais électromécanique (type K) est dans le circuit",
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


def _normaliser_requis(entree) -> dict:
    """@brief Normalise une entrée de `components` en {'type', 'categorie'}.

    [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (« AOP + photorésistance -> U + R,
    indiscernable de n'importe quel autre montage U+R ») : une entrée reste, comme
    avant, une simple lettre de type (str, ex. "R" -- matche N'IMPORTE QUEL R) --
    OU un dict `{"type": "R", "categorie": "Photorésistance"}` (matche UNIQUEMENT
    un R dont le nom réel de bibliothèque est "Photorésistance", cf.
    `Composant.categorie`). Rétro-compatible : toute définition existante
    (`custom_circuits.json`, liste de str) continue de fonctionner à l'identique.

    @param entree str (type seul) ou dict ({'type', 'categorie'}).
    @return dict {'type': str, 'categorie': str|None}.
    """
    if isinstance(entree, dict):
        return {'type': entree.get('type'), 'categorie': entree.get('categorie') or None}
    return {'type': entree, 'categorie': None}


class CustomCircuitPattern(Pattern):
    """@brief Pattern défini par l'utilisateur (types de composants requis + conditions topologiques)."""

    def __init__(self, definition: dict):
        """@brief Construit le pattern depuis sa définition JSON.

        @param definition Dict {'name', 'components', 'conditions'}. Chaque entrée de
               'components' est une lettre de type (str) ou {'type', 'categorie'}
               (cf. `_normaliser_requis`).
        """
        self._name = definition['name']
        self._required_reqs = [_normaliser_requis(c) for c in definition.get('components', [])]
        self._required_types = {r['type'] for r in self._required_reqs}
        self._conditions = list(definition.get('conditions', []))
        # [MODIF 2026-08-19] BUG TROUVÉ EN TESTANT (demande utilisateur : pattern
        # « 1 AOP + 1 photorésistance », testé sur un îlot contenant EN PLUS 2
        # ampoules -- matche quand même). `_requis_satisfaits` ne vérifie que la
        # PRÉSENCE des types requis ; rien ne vérifie qu'il n'y a AUCUN AUTRE
        # composant dans l'îlot. Les ampoules sont de type X comme la photorésistance
        # mais d'une categorie différente ("Ampoule" != "Photoresistance") -- aucune
        # condition existante (toutes filtrées par categorie) ne les voyait jamais.
        # Option OPT-IN (défaut False, aucun impact sur les patterns existants) :
        # cochée, un îlot ne matche QUE si CHAQUE composant qu'il contient
        # correspond à une des exigences déclarées (type + categorie si verrouillée)
        # -- "ce circuit contient CES composants et rien d'autre".
        self._composition_exacte = bool(definition.get('composition_exacte', False))
        # [MODIF 2026-08-19] Option pattern-niveau demandée en lot avec les
        # nouveaux "kind" (voir plus bas) : borne le NOMBRE TOTAL de composants
        # de l'îlot (tous types confondus), indépendamment de `composition_exacte`
        # (qui borne les TYPES tolérés, pas leur nombre) -- les deux peuvent
        # coexister (ex. "exactement ces types, et au plus 5 composants au
        # total"), chacune doit passer indépendamment. Absente/aucune borne
        # renseignée = pas de vérification (comportement d'origine).
        nci = definition.get('nombre_composants_ilot')
        self._nombre_composants_ilot = (
            nci if isinstance(nci, dict) and (nci.get('min') is not None or nci.get('max') is not None)
            else None
        )

    @property
    def name(self) -> str:
        """@brief Nom du circuit personnalisé.
        @return str Nom affiché du pattern.
        """
        return self._name

    def match(self, graph) -> list[dict]:
        """@brief Recherche le circuit personnalisé dans le graphe.

        Exige que tous les types requis soient présents et que toutes les
        conditions topologiques soient satisfaites — un ÎLOT (groupe
        physiquement connecté) à la fois, jamais globalement.

        @param graph Le MultiGraph NetworkX du circuit.
        @return list[dict] Un match {'components', 'nodes'} par îlot qualifiant.
        """
        # [MODIF 2026-08-17] BUG TROUVE EN TESTANT (demande utilisateur : « when the analyser doesnt
        # know something it potes it potentiometre it shouldnt regroup it just leave it like that ») :
        # 'X' est le type "non reconnu" (boite noire, cf. eretro.mapper_nom qui retourne None -> 'X').
        # Un pattern perso qui l'exige NU (ex. custom_circuits.json historique : {"name":
        # "Potentionmetre", "components": ["X"], ...}) regroupe alors N'IMPORTE QUEL composant que
        # l'analyseur ne reconnait pas -- l'exact contraire de "laisser un inconnu inconnu". Deja
        # repere une fois (voir tests/conftest.py::_isole_custom_circuits_reel, qui isolait les TESTS
        # du fichier reel sans jamais corriger le moteur -- le bug restait donc vivant pour de vraies
        # analyses).
        # [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (« j'ai créé un pattern AOP +
        # photorésistance [verrou categorie coché], il ne matche jamais ») : ce garde
        # rejetait TOUT pattern exigeant 'X', categorie verrouillée ou pas -- alors que
        # le chantier categorie (cf. _normaliser_requis) sert EXACTEMENT à distinguer
        # « n'importe quel inconnu » (trop large, à bon droit rejeté) de « CE composant
        # précis, jamais reconnu par le catalogue électrique mais nommé sans ambiguïté »
        # (ex. {"type": "X", "categorie": "Photoresistance"} -- aussi précis qu'un type
        # reconnu). Seul un 'X' SANS categorie reste rejeté ; un 'X' verrouillé sur un
        # nom réel est désormais un type requis comme un autre.
        if any(r['type'] == 'X' and not r['categorie'] for r in self._required_reqs):
            return []
        all_comps = graph.graph.get('components', {})
        found_partout = {ref: comp for ref, comp in all_comps.items()
                          if comp.type in self._required_types}

        if not found_partout:
            return []

        # [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (« les conditions de reconnaissance
        # sont mauvaises quand on ajoute un nouveau schéma simple ») : ce qui précède
        # ramassait TOUS les composants des types requis sur TOUTE LA CARTE, puis
        # vérifiait les conditions sur ce tas -- deux instances du même petit montage,
        # à des endroits totalement différents et SANS AUCUN net partagé, fusionnaient
        # en un seul « match » absurde couvrant toute la carte (mesuré : deux paires
        # R+C sans rapport -> 1 seul match, ['R1','C1','R2','C2']). `detecter_ilots`
        # (déjà utilisé par le reste du pipeline pour la structure en étages) donne le
        # DÉCOUPAGE PHYSIQUE réel par connexité de net signal (hors rails) -- un match
        # par îlot qui satisfait à la fois les types requis ET les conditions, jamais
        # un blob global. `circuits=[]` : la catégorisation par circuit détecté ne sert
        # pas ici, seul le découpage en îlots (étapes 1-3 de detecter_ilots) est utilisé.
        from circuit_analyzer.ilots import detecter_ilots
        resultats = []
        for ilot in detecter_ilots(graph, []):
            found = {ref: found_partout[ref] for ref in ilot['composants']
                     if ref in found_partout}
            if not found:
                continue
            if not self._requis_satisfaits(found):
                continue
            if self._composition_exacte:
                ilot_comps = {ref: all_comps[ref] for ref in ilot['composants']
                              if ref in all_comps}
                if not self._composition_est_exacte(ilot_comps):
                    continue
            if self._nombre_composants_ilot:
                total = len(ilot['composants'])
                lo = self._nombre_composants_ilot.get('min')
                hi = self._nombre_composants_ilot.get('max')
                if lo is not None and total < lo:
                    continue
                if hi is not None and total > hi:
                    continue
            if all(self._check_condition(c, graph, found) for c in self._conditions):
                resultats.append({'components': sorted(found), 'nodes': []})
        return resultats

    def _composition_est_exacte(self, ilot_comps: dict) -> bool:
        """@brief Vrai si TOUS les composants de l'îlot correspondent à une
        exigence déclarée (type, et categorie si verrouillée) -- aucun
        composant "en plus", même d'un type par ailleurs requis (ex. une
        ampoule dans un îlot qui exige une photorésistance : même type X,
        categorie différente -> rejeté).

        [MODIF 2026-08-19] Cf. commentaire de `_composition_exacte` dans
        __init__ -- vérifie l'îlot ENTIER (`ilot_comps`), pas seulement
        `found` (déjà restreint aux types requis, donc incapable de
        détecter un composant hors-liste).

        @param ilot_comps Dict {ref -> Composant} de TOUS les composants de l'îlot.
        @return bool True si aucun composant hors-liste n'est présent.
        """
        for comp in ilot_comps.values():
            if not any(comp.type == req['type']
                       and (req['categorie'] is None or comp.categorie == req['categorie'])
                       for req in self._required_reqs):
                return False
        return True

    def _requis_satisfaits(self, found: dict) -> bool:
        """@brief Vrai si `found` contient, pour CHAQUE exigence, au moins un
        composant du bon type (et, si précisée, de la bonne `categorie` --
        ex. "R" simple = n'importe quel R, "R"+"Photorésistance" = SEULEMENT
        un R nommé ainsi -- cf. `_normaliser_requis`).

        @param found Dict {ref -> Composant} (déjà restreint à un îlot).
        @return bool True si toutes les exigences de `self._required_reqs` sont couvertes.
        """
        for req in self._required_reqs:
            if not any(c.type == req['type']
                       and (req['categorie'] is None or c.categorie == req['categorie'])
                       for c in found.values()):
                return False
        return True

    def _check_condition(self, condition, graph, found: dict) -> bool:
        """@brief Vérifie une condition topologique sur les composants trouvés.

        [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (« les conditions de reconnaissance
        sont vieilles et pas mises à jour, aucune possibilité d'en ajouter ») : les 12
        conditions nommées ci-dessous étaient les SEULES possibles, chacune un bloc
        Python one-off -- en ajouter une nouvelle exigeait de modifier ce fichier.
        `condition` accepte maintenant AUSSI un dict générique et paramétré
        (`{"kind": ..., ...}`, cf. `_evaluer_condition_generique`) : l'utilisateur en
        construit une nouvelle depuis le wizard (type de composant + broche + cible),
        sans toucher au code. Les 12 conditions nommées restent inchangées (rétro-
        compatibilité de `custom_circuits.json` existant).

        @param condition Libellé nommé (cf. CONDITION_LABELS) OU dict générique.
        @param graph Le MultiGraph NetworkX du circuit.
        @param found Dict {ref -> Composant} des composants des types requis.
        @return bool True si la condition est satisfaite ; False si non remplie ou inconnue.
        """
        if isinstance(condition, dict):
            return _evaluer_condition_generique(condition, graph, found)
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

        if condition == "Au moins 2 résistances":
            return sum(1 for comp in found.values() if comp.type == 'R') >= 2

        if condition == "Au moins 2 condensateurs":
            return sum(1 for comp in found.values() if comp.type == 'C') >= 2

        if condition == "R et C connectés au même nœud signal":
            r_nets = set()
            c_nets = set()
            for comp in found.values():
                nets = {n for n in comp.pins.values() if n and not is_gnd(n) and not is_power(n)}
                if comp.type == 'R':
                    r_nets |= nets
                elif comp.type == 'C':
                    c_nets |= nets
            return bool(r_nets & c_nets)

        if condition == "Transistor émetteur à GND":
            for comp in found.values():
                if comp.type == 'Q':
                    e = comp.pins.get('E', '')
                    if e and is_gnd(e):
                        return True
            return False

        if condition == "Diode cathode sur alimentation":
            for comp in found.values():
                if comp.type == 'D':
                    k = comp.pins.get('K', '')
                    if k and is_power(k):
                        return True
            return False

        if condition == "Pas de transistor dans le circuit":
            return not any(comp.type in ('Q', 'M') for comp in found.values())

        if condition == "Self (inductance) présente":
            return any(comp.type == 'L' for comp in found.values())

        if condition == "Relais présent":
            return any(comp.type == 'K' for comp in found.values())

        # Unknown condition — fail safe rather than silently accepting
        return False


# [MODIF 2026-08-18] Moteur de conditions GÉNÉRIQUES et paramétrées (chantier
# « les conditions sont vieilles, aucune possibilité d'en ajouter »). Chaque
# "kind" ci-dessous est un GABARIT réutilisable (type de composant + broche +
# cible en paramètres) plutôt qu'un bloc Python figé par condition — couvre les
# mêmes besoins que les 12 conditions nommées ci-dessus (qui restent, pour la
# rétro-compatibilité), mais l'utilisateur en compose une NOUVELLE depuis le
# wizard sans toucher au code : choisir un "kind", remplir ses paramètres.
CONDITION_KINDS = [
    "broche_vers_rail",
    "au_moins_n",
    "meme_noeud",
    "en_serie",
    "en_serie_deux_types",
    "en_parallele",
    "type_absent",
    "contre_reaction",
    "connexion_broches",
    "broche_non_connectee",
    "valeur_compare",
    "valeur_dans_plage",
    "meme_valeur",
    "valeurs_differentes",
    "ratio_valeurs",
    "nombre_broches",
]

# Libellé + description de chaque KIND (pas d'une condition instanciée : ça,
# c'est `condition_display`/`_description_generique` ci-dessous, une fois les
# paramètres choisis par l'utilisateur).
CONDITION_KIND_LABELS = {
    "broche_vers_rail":  "Broche reliée à un rail (masse/alimentation)",
    "au_moins_n":        "Nombre de composants d'un type (≥, =, ≤, >, <)",
    "meme_noeud":        "Deux types partagent un nœud",
    "en_serie":          "Un type est en série avec un autre composant",
    "en_parallele":      "Deux types partagent leurs DEUX nœuds (en parallèle)",
    "type_absent":       "Un type est absent du circuit",
    "contre_reaction":   "Une broche reboucle sur une autre (même composant)",
    "connexion_broches": "Connexion précise entre deux broches (composants libres)",
    "broche_non_connectee": "Une broche reste non connectée (flottante)",
    "valeur_compare":    "La valeur d'un composant compare à un seuil",
    "meme_valeur":       "Deux composants ont la même valeur",
    "nombre_broches":    "Le nombre de broches d'un type compare à un seuil",
    # [MODIF 2026-08-19] Lot demandé après découverte du manque "composition
    # exacte" -- plage de valeur, différence de valeur, série stricte à deux
    # types précis (complément d'en_parallele), et ratio de valeurs.
    "en_serie_deux_types": "Deux types précis en série (exactement un nœud commun)",
    "valeur_dans_plage": "La valeur d'un composant est dans une plage [min, max]",
    "valeurs_differentes": "Deux composants ont des valeurs DIFFÉRENTES",
    "ratio_valeurs":     "Le ratio entre deux valeurs compare à une cible (± tolérance)",
}
CONDITION_KIND_DESCRIPTIONS = {
    "broche_vers_rail":  "ex. la cathode (K) d'une diode reliée à l'alimentation",
    "au_moins_n":        "ex. au moins 2, exactement 3, ou au plus 1 résistance(s)",
    "meme_noeud":        "ex. une résistance et un condensateur sur le même fil",
    "en_serie":          "ex. une résistance en série avec un autre composant du motif",
    "en_parallele":      "ex. deux résistances qui partagent leurs deux broches "
                        "(vraiment en parallèle, pas juste un nœud commun)",
    "type_absent":       "ex. aucun transistor (Q) ni MOSFET (M) dans le circuit",
    "contre_reaction":   "ex. la sortie (OUT) d'un AOP reboucle sur l'entrée − (IN-)",
    # [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (demande utilisateur : « select the
    # pins of componant and choose the connection between them ») : le plus général
    # des "kind" -- choisit une broche (ou un ENSEMBLE de broches acceptables, OU
    # "n'importe laquelle") d'un composant A, et une broche/ensemble d'un composant
    # B -- B pouvant être soit UN AUTRE composant (types différents ou même type,
    # instances différentes), soit LE MÊME composant que A (ex. deux broches d'un
    # même IC court-circuitées). Généralise `contre_reaction` (même composant
    # uniquement) et `meme_noeud` (broches non précisées) en un seul outil.
    "connexion_broches": "ex. la broche 1 OU 2 d'une résistance reliée à IN- d'un AOP "
                        "(autre composant), ou à une autre broche du même composant",
    # [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (demande utilisateur : « we are very
    # limited, add all the possible pattern of a schema ») : lot de "kind" couvrant
    # les primitives topologiques qui manquaient encore -- comptage avec comparateur
    # (pas seulement "au moins"), parallèle (complément d'en_serie), broche flottante,
    # comparaison/égalité de VALEUR (pas seulement de type), nombre de broches (utile
    # pour distinguer un boîtier 8 broches d'un 3 broches sans dépendre du catalogue).
    "broche_non_connectee": "ex. la broche V- d'un AOP jamais câblée (montage simple "
                           "alimentation) -- utile pour EXCLURE un montage complet",
    "valeur_compare":    "ex. une résistance > 100k (pull-up) vs une résistance de "
                        "gain, sans dépendre du nom précis",
    "meme_valeur":       "ex. R1 et R3 de même valeur (pont équilibré, paire appairée)",
    "nombre_broches":    "ex. un boîtier U à exactement 8 broches (NE555) vs 3 (AOP)",
    "en_serie_deux_types": "ex. une résistance en série avec UN CONDENSATEUR précis "
                          "(contrairement à « en_serie » qui accepte n'importe quel "
                          "autre composant du motif)",
    "valeur_dans_plage": "ex. une résistance entre 1k et 10k (plage typique de pull-up)",
    "valeurs_differentes": "ex. R1 et R2 doivent avoir des valeurs différentes "
                          "(exclut un pont équilibré)",
    "ratio_valeurs":     "ex. R1 vaut 2× R2, à ±10% près (diviseur de tension à ratio fixe)",
}

_LIBELLES_RAIL = {"masse": "la masse", "alimentation": "l'alimentation"}


def _comp_correspond(comp, type_cible, categorie_cible=None) -> bool:
    """@brief Vrai si `comp` a le type demandé et, si précisée, la categorie demandée.

    [MODIF 2026-08-18] Brique commune du filtrage type+categorie, réutilisée par
    tous les "kind" ci-dessous -- une categorie absente/None = comportement
    d'origine (filtre uniquement sur `type`, ex. "n'importe quel R").
    """
    return comp.type == type_cible and (categorie_cible is None
                                        or getattr(comp, "categorie", "") == categorie_cible)


# Comparateurs disponibles pour les "kind" numériques (comptage, valeur, nb de
# broches) -- clé stable stockée dans le JSON, jamais le symbole affiché.
_COMPARATEURS = {
    ">=": lambda a, b: a >= b, "==": lambda a, b: a == b, "<=": lambda a, b: a <= b,
    ">":  lambda a, b: a > b,  "<":  lambda a, b: a < b,
}
_LIBELLES_COMPARATEUR = {">=": "au moins", "==": "exactement", "<=": "au plus",
                         ">": "plus de", "<": "moins de"}


def _comparer(valeur, comparateur: str, seuil) -> bool:
    """@brief Applique un comparateur stable (clé JSON) entre deux nombres.

    @param comparateur Une des clés de `_COMPARATEURS` ; défaut ">=" si absente/inconnue.
    @return bool Résultat de la comparaison.
    """
    return _COMPARATEURS.get(comparateur, _COMPARATEURS[">="])(valeur, seuil)


def _evaluer_condition_generique(cond: dict, graph, found: dict) -> bool:
    """@brief Évalue une condition générique paramétrée (dict `{"kind": ...}`).

    [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (« AOP + photorésistance -> U + R,
    indiscernable de n'importe quel autre montage U+R ») : chaque "kind" accepte
    maintenant une "categorie" (ou "categories", en parallèle de "types") OPTIONNELLE
    en plus du type électrique -- ex. `{"kind": "broche_vers_rail", "type": "R",
    "categorie": "Photorésistance", ...}` ne matche QUE les R nommés ainsi, pas
    n'importe quel R. Absente = comportement d'origine (filtre sur le type seul).

    @param cond Condition générique (cf. CONDITION_KINDS pour les "kind" valides).
    @param graph Le MultiGraph NetworkX du circuit.
    @param found Dict {ref -> Composant} des composants des types requis.
    @return bool True si la condition est satisfaite ; False si "kind" inconnu.
    """
    kind = cond.get("kind")

    if kind == "broche_vers_rail":
        type_cible = cond.get("type")
        categorie = cond.get("categorie")
        broche = cond.get("broche")   # None = n'importe quelle broche du composant
        test_rail = is_gnd if cond.get("rail") == "masse" else is_power
        for comp in found.values():
            if not _comp_correspond(comp, type_cible, categorie):
                continue
            cibles = [comp.pins.get(broche, "")] if broche else list(comp.pins.values())
            if any(n and test_rail(n) for n in cibles):
                return True
        return False

    if kind == "au_moins_n":
        # [MODIF 2026-08-18] "comparateur" optionnel (défaut ">=", cf. _COMPARATEURS) --
        # ancien comportement inchangé pour toute condition sauvegardée avant cet ajout.
        type_cible = cond.get("type")
        categorie = cond.get("categorie")
        n = cond.get("n", 1)
        compte = sum(1 for c in found.values() if _comp_correspond(c, type_cible, categorie))
        return _comparer(compte, cond.get("comparateur", ">="), n)

    if kind == "en_parallele":
        # Complément d'"en_serie" : deux composants (types éventuellement identiques,
        # instances distinctes) partagent leurs DEUX broches -- vraiment en parallèle,
        # pas juste un nœud commun (cf. "meme_noeud", qui ne demande qu'UN nœud partagé).
        types_cibles = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types_cibles)
        if len(types_cibles) < 2:
            return False
        t1, c1 = types_cibles[0], categories[0]
        t2, c2 = types_cibles[1], categories[1]
        for ref_a, comp_a in found.items():
            if not _comp_correspond(comp_a, t1, c1):
                continue
            nets_a = {n for n in comp_a.pins.values() if n and not is_gnd(n) and not is_power(n)}
            for ref_b, comp_b in found.items():
                if ref_b == ref_a or not _comp_correspond(comp_b, t2, c2):
                    continue
                nets_b = {n for n in comp_b.pins.values() if n and not is_gnd(n) and not is_power(n)}
                if len(nets_a & nets_b) >= 2:
                    return True
        return False

    if kind == "meme_noeud":
        types_cibles = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types_cibles)
        if len(types_cibles) < 2:
            return False
        nets_par_cle: dict = {}
        for c in found.values():
            for t, cat in zip(types_cibles, categories):
                if _comp_correspond(c, t, cat):
                    nets = {n for n in c.pins.values() if n and not is_gnd(n) and not is_power(n)}
                    nets_par_cle.setdefault((t, cat), set()).update(nets)
        ensembles = [nets_par_cle.get((t, cat), set()) for t, cat in zip(types_cibles, categories)]
        if any(not e for e in ensembles):
            return False
        inter = ensembles[0]
        for e in ensembles[1:]:
            inter = inter & e
        return bool(inter)

    if kind == "en_serie":
        type_cible = cond.get("type")
        categorie = cond.get("categorie")
        cibles = {ref for ref, c in found.items() if _comp_correspond(c, type_cible, categorie)}
        autres = [c for ref, c in found.items() if ref not in cibles]
        for ref in cibles:
            nets = set(found[ref].pins.values())
            for c in autres:
                if nets & set(c.pins.values()):
                    return True
        return False

    if kind == "type_absent":
        types_exclus = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types_exclus)
        return not any(_comp_correspond(c, t, cat)
                       for c in found.values()
                       for t, cat in zip(types_exclus, categories))

    if kind == "contre_reaction":
        type_cible = cond.get("type")
        categorie = cond.get("categorie")
        p_source = cond.get("broche_source")
        p_cible = cond.get("broche_cible")
        for comp in found.values():
            if not _comp_correspond(comp, type_cible, categorie):
                continue
            n_source = comp.pins.get(p_source)
            n_cible = comp.pins.get(p_cible)
            if not n_source or not n_cible:
                continue
            for u, v, _d in graph.edges(n_source, data=True):
                if (v if u == n_source else u) == n_cible:
                    return True
        return False

    if kind == "connexion_broches":
        # [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT (demande utilisateur : « select
        # the pins of componant and choose the connection between them, u can
        # choose 2 or 1 also ») : `cote_a`/`cote_b` = {"type", "categorie",
        # "broches"} -- "broches" vide/absente = n'importe laquelle, sinon un
        # ENSEMBLE de broches acceptables (OR côté B : "connectée à L'UNE
        # d'elles"). `cote_b.meme_composant` = True -> cherche une connexion
        # entre deux broches DU MÊME composant que côté A (type/categorie de
        # côté_b ignorés, forcément identiques à côté_a) ; False (défaut) ->
        # cherche un AUTRE composant du circuit satisfaisant côté_b, connecté
        # (même net) à côté_a.
        #
        # [MODIF 2026-08-18] Lot « add more costomation ... 1 to a lot of pins or
        # this one should never be connected to this » :
        #  - `cote_a.mode` : "au_moins_une" (défaut, comportement d'origine -- une
        #    SEULE des broches sélectionnées suffit) ou "toutes" (CHAQUE broche
        #    sélectionnée doit, individuellement, être connectée -- ex. "V+ ET V-
        #    doivent TOUTES LES DEUX aller à la masse", pas juste l'une des deux).
        #  - `cond.sens` : "connectee" (défaut) ou "jamais_connectee" -- inverse le
        #    résultat de la recherche ci-dessous. Vide/absent côté_a (le type
        #    requis n'existe même pas dans cet îlot) -> la recherche positive est
        #    naturellement False -> "jamais_connectee" est alors VRAI (rien à
        #    exclure, condition satisfaite par défaut) -- même logique que
        #    `type_absent` : une exclusion sur un composant absent ne doit jamais
        #    faire échouer le pattern.
        cote_a = cond.get("cote_a", {})
        cote_b = cond.get("cote_b", {})
        type_a, categorie_a = cote_a.get("type"), cote_a.get("categorie")
        mode_a = cote_a.get("mode", "au_moins_une")
        meme_composant = bool(cote_b.get("meme_composant"))
        broches_b_cfg = cote_b.get("broches") or []
        type_b, categorie_b = cote_b.get("type"), cote_b.get("categorie")

        def _broche_connectee(comp_a, p_a, comp_b, pins_b) -> bool:
            """Vrai si la broche `p_a` de `comp_a` partage son net avec AU MOINS
            UNE broche de `pins_b` sur `comp_b` (`comp_b is comp_a` -> même
            composant, la broche identique ne compte jamais comme connexion)."""
            n_a = comp_a.pins.get(p_a)
            if not n_a:
                return False
            for p_b in pins_b:
                if comp_b is comp_a and p_b == p_a:
                    continue
                if comp_b.pins.get(p_b) == n_a:
                    return True
            return False

        def _existe_connexion() -> bool:
            for ref_a, comp_a in found.items():
                if not _comp_correspond(comp_a, type_a, categorie_a):
                    continue
                pins_a_cfg = cote_a.get("broches") or list(comp_a.pins.keys())
                pins_a = [p for p in pins_a_cfg if p in comp_a.pins]
                if not pins_a:
                    continue

                if meme_composant:
                    candidats_b = [comp_a]
                else:
                    candidats_b = [c for ref_b, c in found.items()
                                   if ref_b != ref_a and _comp_correspond(c, type_b, categorie_b)]
                if not candidats_b:
                    continue

                for comp_b in candidats_b:
                    pins_b = broches_b_cfg or list(comp_b.pins.keys())
                    resultats = [_broche_connectee(comp_a, p_a, comp_b, pins_b)
                                for p_a in pins_a]
                    satisfait = all(resultats) if mode_a == "toutes" else any(resultats)
                    if satisfait:
                        return True
            return False

        trouve = _existe_connexion()
        return (not trouve) if cond.get("sens") == "jamais_connectee" else trouve

    if kind == "broche_non_connectee":
        # "flottante" = pas de net réel (vide/None), littéralement "NC", ou un net
        # utilisé par UNE SEULE broche dans TOUT le circuit (personne d'autre ne s'y
        # raccorde, donc électriquement mort). `broche` absente = n'importe quelle
        # broche du composant.
        # [MODIF 2026-08-18] BUG TROUVÉ EN TESTANT : `graph.degree(net)` semblait le
        # bon signal, mais `build_graph` ne crée une ARÊTE que pour un composant à
        # EXACTEMENT 2 broches (R1 : N2-GND) -- un composant à 3+ broches (ex. l'AOP,
        # IN+/IN-/OUT) n'apparaît dans AUCUNE arête, donc `degree('N2')` ignorait
        # totalement que l'AOP utilise aussi N2 : IN- câblée à une vraie résistance
        # ressortait quand même "non connectée". Mesuré (`check_graph_model.py`) :
        # `N2 degree=1` alors que DEUX composants l'utilisent. Compte donc les
        # broches directement depuis `graph.graph['components']` (TOUS les
        # composants, pas seulement `found` -- un voisin hors du pattern compte
        # quand même comme "connecté").
        type_cible = cond.get("type")
        categorie = cond.get("categorie")
        broche = cond.get("broche")
        tous_comps = graph.graph.get('components', {})
        usage_net: dict = {}
        for comp in tous_comps.values():
            for net in comp.pins.values():
                if net:
                    usage_net[net] = usage_net.get(net, 0) + 1
        for comp in found.values():
            if not _comp_correspond(comp, type_cible, categorie):
                continue
            cibles = [comp.pins.get(broche)] if broche else list(comp.pins.values())
            for net in cibles:
                if not net or net == "NC" or usage_net.get(net, 0) <= 1:
                    return True
        return False

    if kind == "valeur_compare":
        # `Composant.value` brute ("10k", "100n"...) parsée en unité SI --
        # composant sans valeur exploitable (parse_valeur -> None) ignoré, jamais
        # une fausse victoire ni un crash.
        from circuit_analyzer.value_parser import parse_valeur
        type_cible = cond.get("type")
        categorie = cond.get("categorie")
        seuil = cond.get("seuil")
        if seuil is None:
            return False
        for comp in found.values():
            if not _comp_correspond(comp, type_cible, categorie):
                continue
            v = parse_valeur(getattr(comp, "value", ""))
            if v is not None and _comparer(v, cond.get("comparateur", ">="), seuil):
                return True
        return False

    if kind == "meme_valeur":
        # Deux composants (types éventuellement identiques, instances distinctes)
        # dont la valeur parsée est égale -- paire appairée, pont équilibré...
        # Tolérance relative (0.5 %) : "10k" vs "10.0k" ne doivent pas diverger
        # sur un artefact d'arrondi de formatage, mais "10k" vs "12k" doivent.
        from circuit_analyzer.value_parser import parse_valeur
        types_cibles = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types_cibles)
        if len(types_cibles) < 2:
            return False
        t1, c1 = types_cibles[0], categories[0]
        t2, c2 = types_cibles[1], categories[1]
        for ref_a, comp_a in found.items():
            if not _comp_correspond(comp_a, t1, c1):
                continue
            v_a = parse_valeur(getattr(comp_a, "value", ""))
            if v_a is None:
                continue
            for ref_b, comp_b in found.items():
                if ref_b == ref_a or not _comp_correspond(comp_b, t2, c2):
                    continue
                v_b = parse_valeur(getattr(comp_b, "value", ""))
                if v_b is None:
                    continue
                if v_a == 0 and v_b == 0:
                    return True
                if v_a != 0 and abs(v_a - v_b) / abs(v_a) <= 0.005:
                    return True
        return False

    if kind == "nombre_broches":
        type_cible = cond.get("type")
        categorie = cond.get("categorie")
        n = cond.get("n", 1)
        for comp in found.values():
            if _comp_correspond(comp, type_cible, categorie) and _comparer(
                    len(comp.pins), cond.get("comparateur", ">="), n):
                return True
        return False

    if kind == "en_serie_deux_types":
        # [MODIF 2026-08-19] Complément STRICT d'"en_parallele" : deux TYPES
        # précis (pas juste "un type contre le reste du motif", cf. "en_serie")
        # qui partagent EXACTEMENT un nœud (pas deux -- ce serait alors
        # "en_parallele"). Même structure de champs qu'"en_parallele"/"meme_valeur"
        # (types/categories, taille 2) pour cohérence.
        types_cibles = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types_cibles)
        if len(types_cibles) < 2:
            return False
        t1, c1 = types_cibles[0], categories[0]
        t2, c2 = types_cibles[1], categories[1]
        for ref_a, comp_a in found.items():
            if not _comp_correspond(comp_a, t1, c1):
                continue
            nets_a = {n for n in comp_a.pins.values() if n and not is_gnd(n) and not is_power(n)}
            for ref_b, comp_b in found.items():
                if ref_b == ref_a or not _comp_correspond(comp_b, t2, c2):
                    continue
                nets_b = {n for n in comp_b.pins.values() if n and not is_gnd(n) and not is_power(n)}
                if len(nets_a & nets_b) == 1:
                    return True
        return False

    if kind == "valeur_dans_plage":
        # "Au moins un" composant du type/categorie dont la valeur tombe dans
        # [min, max] -- même sémantique "au moins un" que "valeur_compare"
        # (pas besoin que TOUS les composants du type correspondent).
        from circuit_analyzer.value_parser import parse_valeur
        type_cible = cond.get("type")
        categorie = cond.get("categorie")
        vmin = cond.get("valeur_min")
        vmax = cond.get("valeur_max")
        if vmin is None or vmax is None:
            return False
        for comp in found.values():
            if not _comp_correspond(comp, type_cible, categorie):
                continue
            v = parse_valeur(getattr(comp, "value", ""))
            if v is not None and vmin <= v <= vmax:
                return True
        return False

    if kind == "valeurs_differentes":
        # Inverse de "meme_valeur" : au moins une paire dont les valeurs
        # PARSABLES divergent de plus de la même tolérance relative (0.5%)
        # utilisée par "meme_valeur" -- un composant sans valeur exploitable
        # ne peut prouver aucune différence, la paire est ignorée (jamais une
        # fausse victoire), même convention de robustesse que "meme_valeur".
        from circuit_analyzer.value_parser import parse_valeur
        types_cibles = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types_cibles)
        if len(types_cibles) < 2:
            return False
        t1, c1 = types_cibles[0], categories[0]
        t2, c2 = types_cibles[1], categories[1]
        for ref_a, comp_a in found.items():
            if not _comp_correspond(comp_a, t1, c1):
                continue
            v_a = parse_valeur(getattr(comp_a, "value", ""))
            if v_a is None:
                continue
            for ref_b, comp_b in found.items():
                if ref_b == ref_a or not _comp_correspond(comp_b, t2, c2):
                    continue
                v_b = parse_valeur(getattr(comp_b, "value", ""))
                if v_b is None:
                    continue
                memes = (v_a == 0 and v_b == 0) or (v_a != 0 and abs(v_a - v_b) / abs(v_a) <= 0.005)
                if not memes:
                    return True
        return False

    if kind == "ratio_valeurs":
        # Ratio valeur_a / valeur_b (A = premier type, B = second -- ordre
        # explicite dans le libellé pour ne pas prêter à confusion) comparé à
        # "ratio_cible" avec une tolérance RELATIVE en % de la cible.
        from circuit_analyzer.value_parser import parse_valeur
        types_cibles = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types_cibles)
        ratio_cible = cond.get("ratio_cible")
        if len(types_cibles) < 2 or not ratio_cible:
            return False
        tolerance_pct = cond.get("tolerance_pct", 10)
        t1, c1 = types_cibles[0], categories[0]
        t2, c2 = types_cibles[1], categories[1]
        for ref_a, comp_a in found.items():
            if not _comp_correspond(comp_a, t1, c1):
                continue
            v_a = parse_valeur(getattr(comp_a, "value", ""))
            if not v_a:
                continue
            for ref_b, comp_b in found.items():
                if ref_b == ref_a or not _comp_correspond(comp_b, t2, c2):
                    continue
                v_b = parse_valeur(getattr(comp_b, "value", ""))
                if not v_b:
                    continue
                ratio = v_a / v_b
                tol = abs(ratio_cible) * (tolerance_pct / 100.0)
                if abs(ratio - ratio_cible) <= tol:
                    return True
        return False

    return False


def _libelle_type(type_cible, categorie=None) -> str:
    """@brief "R" seul, ou "R (Photorésistance)" si une categorie est précisée."""
    return f"{type_cible} ({categorie})" if categorie else str(type_cible)


def condition_display_generique(cond: dict) -> str:
    """@brief Libellé lisible d'une condition générique déjà PARAMÉTRÉE (kind + valeurs).

    @param cond Condition générique.
    @return str Description en clair, ou une représentation brute si "kind" inconnu.
    """
    kind = cond.get("kind")
    if kind == "broche_vers_rail":
        broche = cond.get("broche")
        sujet = f"la broche {broche}" if broche else "une broche"
        rail = _LIBELLES_RAIL.get(cond.get("rail"), cond.get("rail"))
        type_txt = _libelle_type(cond.get("type"), cond.get("categorie"))
        return f"{sujet} d'un composant {type_txt} reliée à {rail}"
    if kind == "au_moins_n":
        type_txt = _libelle_type(cond.get("type"), cond.get("categorie"))
        mot = _LIBELLES_COMPARATEUR.get(cond.get("comparateur", ">="), "au moins")
        return f"{mot.capitalize()} {cond.get('n')} composant(s) de type {type_txt}"
    if kind == "meme_noeud":
        types = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types)
        return f"{' et '.join(_libelle_type(t, c) for t, c in zip(types, categories))} partagent un nœud"
    if kind == "en_serie":
        type_txt = _libelle_type(cond.get("type"), cond.get("categorie"))
        return f"{type_txt} en série avec un autre composant du motif"
    if kind == "en_parallele":
        types = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types)
        return (f"{' et '.join(_libelle_type(t, c) for t, c in zip(types, categories))} "
                f"en parallèle (mêmes deux nœuds)")
    if kind == "type_absent":
        types = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types)
        return f"Aucun {'/'.join(_libelle_type(t, c) for t, c in zip(types, categories))} dans le circuit"
    if kind == "contre_reaction":
        type_txt = _libelle_type(cond.get("type"), cond.get("categorie"))
        return (f"{cond.get('broche_source')} → {cond.get('broche_cible')} "
                f"sur un même composant {type_txt}")
    if kind == "connexion_broches":
        return _libelle_connexion_broches(cond)
    if kind == "broche_non_connectee":
        type_txt = _libelle_type(cond.get("type"), cond.get("categorie"))
        broche = cond.get("broche")
        sujet = f"la broche {broche}" if broche else "une broche"
        return f"{sujet} d'un {type_txt} reste non connectée"
    if kind == "valeur_compare":
        type_txt = _libelle_type(cond.get("type"), cond.get("categorie"))
        mot = _LIBELLES_COMPARATEUR.get(cond.get("comparateur", ">="), "au moins")
        return f"Valeur d'un {type_txt} {mot} {cond.get('seuil')}"
    if kind == "meme_valeur":
        types = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types)
        return f"{' et '.join(_libelle_type(t, c) for t, c in zip(types, categories))} ont la même valeur"
    if kind == "nombre_broches":
        type_txt = _libelle_type(cond.get("type"), cond.get("categorie"))
        mot = _LIBELLES_COMPARATEUR.get(cond.get("comparateur", ">="), "au moins")
        return f"Un {type_txt} a {mot} {cond.get('n')} broche(s)"
    if kind == "en_serie_deux_types":
        types = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types)
        return (f"{' et '.join(_libelle_type(t, c) for t, c in zip(types, categories))} "
                f"en série (exactement un nœud commun, pas deux)")
    if kind == "valeur_dans_plage":
        type_txt = _libelle_type(cond.get("type"), cond.get("categorie"))
        return f"Valeur d'un {type_txt} entre {cond.get('valeur_min')} et {cond.get('valeur_max')}"
    if kind == "valeurs_differentes":
        types = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types)
        return f"{' et '.join(_libelle_type(t, c) for t, c in zip(types, categories))} ont des valeurs DIFFÉRENTES"
    if kind == "ratio_valeurs":
        types = cond.get("types", [])
        categories = cond.get("categories") or [None] * len(types)
        libelles = [_libelle_type(t, c) for t, c in zip(types, categories)]
        t1 = libelles[0] if len(libelles) > 0 else "?"
        t2 = libelles[1] if len(libelles) > 1 else "?"
        return (f"Ratio {t1} / {t2} = {cond.get('ratio_cible')} "
                f"(± {cond.get('tolerance_pct', 10)}%)")
    return str(cond)


def libelle_nombre_composants_ilot(cfg: dict) -> str:
    """@brief Libellé lisible de l'option pattern-niveau "nombre_composants_ilot".

    [MODIF 2026-08-19] Utilisée par le wizard (étape 4) et l'onglet Circuits
    (résumé lecture seule) -- une seule source de vérité, même principe que
    `condition_display_generique` pour les conditions par-condition.

    @param cfg Dict {'min': int|None, 'max': int|None}.
    @return str Description complète, jamais ambiguë entre min seul/max seul/les deux.
    """
    lo, hi = cfg.get('min'), cfg.get('max')
    if lo is not None and hi is not None:
        return f"Entre {lo} et {hi} composant(s) au total dans le circuit."
    if lo is not None:
        return f"Au moins {lo} composant(s) au total dans le circuit."
    return f"Au plus {hi} composant(s) au total dans le circuit."


def _libelle_broches(broches) -> str:
    """@brief "n'importe laquelle", "1", ou "1 ou 2" selon la taille de l'ensemble."""
    if not broches:
        return "n'importe laquelle"
    return " ou ".join(broches)


def _libelle_connexion_broches(cond: dict) -> str:
    """@brief Libellé lisible d'une condition "connexion_broches".

    [MODIF 2026-08-19] BUG TROUVÉ EN TESTANT (demande utilisateur : « la
    vérification à l'étape 4 doit être exactement précise sur la condition
    faite ») : quand `mode == "toutes"` ET qu'aucune broche précise n'est
    cochée côté A (« n'importe laquelle » = `broches` vide, ce qui veut dire
    "TOUTES les broches du composant" côté évaluation, cf. `_evaluer_condition_
    generique`), l'ancien code exigeait `cote_a.get("broches")` en plus du mode
    pour afficher "TOUTES" -- avec une liste vide, il retombait silencieusement
    sur `_libelle_broches([])` = "n'importe laquelle", un texte IDENTIQUE à
    celui d'un mode "au_moins_une" sur les mêmes broches. Deux conditions
    RÉELLEMENT différentes (une seule broche suffit vs. toutes les broches du
    composant exigées) produisaient donc le même libellé -- exactement le
    défaut de précision signalé. Le mode "toutes" est maintenant toujours
    rendu explicitement, avec ou sans liste de broches précisée.
    """
    cote_a = cond.get("cote_a", {})
    cote_b = cond.get("cote_b", {})
    type_txt_a = _libelle_type(cote_a.get("type"), cote_a.get("categorie"))
    broches_a = cote_a.get("broches")
    if cote_a.get("mode") == "toutes":
        broches_txt_a = (f"TOUTES ({_libelle_broches(broches_a)})" if broches_a
                          else "TOUTES les broches")
    else:
        broches_txt_a = _libelle_broches(broches_a)
    broches_txt_b = _libelle_broches(cote_b.get("broches"))
    verbe = "n'est JAMAIS reliée" if cond.get("sens") == "jamais_connectee" else "est reliée"
    if cote_b.get("meme_composant"):
        return (f"Broche {broches_txt_a} d'un {type_txt_a} {verbe} à sa "
                f"propre broche {broches_txt_b} (même composant)")
    type_txt_b = _libelle_type(cote_b.get("type"), cote_b.get("categorie"))
    return (f"Broche {broches_txt_a} d'un {type_txt_a} {verbe} à la "
            f"broche {broches_txt_b} d'un {type_txt_b}")


def suggest_conditions(graph, refs: list) -> list:
    """@brief Détecte automatiquement les conditions topologiques vraies pour un groupe de composants.

    @param graph MultiGraph NetworkX du circuit.
    @param refs Liste de références de composants à analyser.
    @return list[str] Sous-ensemble de CONDITION_LABELS dont la condition est vraie.
    """
    composants = graph.graph.get('components', {})
    found = {ref: composants[ref] for ref in refs if ref in composants}
    if not found:
        return []
    dummy = CustomCircuitPattern({'name': '_', 'components': [], 'conditions': []})
    return [
        label for label in CONDITION_LABELS
        if dummy._check_condition(label, graph, found)
    ]
