"""@file test_bibliotheque_personnalisee_lecture_carte.py
@brief Pont entre l'onglet Composants (component_library.json, bouton « Recevoir la
bibliothèque partagée ») et la lecture d'une VRAIE carte (`circuit_analyzer.xml.lire_xml`).

BUG TROUVÉ EN TESTANT (demande utilisateur, 2026-08-18) : un composant réel absent de
`_NOM_VERS_TYPE` et du repli par forme (ex. « MOSFET canal N », « TL431 », « Diode
Zener ») reste type X (« Inconnu » dans le wizard « Créer le pattern ») MÊME après
l'avoir enregistré dans l'onglet Composants — `lire_xml` ne consultait jamais
`component_library.json`. `_types_personnalises()` comble ce pont.

Le type électrique est déduit des NOMS de broches (`_deviner_type_et_plan`), PAS du
préfixe : la validation de l'onglet Composants réserve déjà R/C/L/D/F/Q/M/U/T/K/SW
aux types intégrés (« type intégré réservé »), donc une entrée personnalisée n'a
JAMAIS l'une de ces lettres pour préfixe — et l'import en masse en génère un à 3
lettres (« MOS ») sans rapport avec le type électrique. Voir aussi
tests/test_eretro_symboles.py pour `plan_alias` (pont Pnumber -> Pname), utilisé ici
en aval.
"""
import json

import pytest

from circuit_analyzer import xml as xml_mod
from circuit_analyzer.xml import lire_xml


def _pin(num, name=None):
    """@brief <DataPin> minimal. `name` distinct de `num` simule un symbole où
    Pname (nom affiché) diffère de Pnumber (identité de broche pour lire_xml)."""
    pname = name if name is not None else num
    return (f"<DataPin><Pname>{pname}</Pname><Pnumber>{num}</Pnumber>"
            f"<Pin><X>0</X><Y>0</Y></Pin><NodeL /><Size>9</Size></DataPin>")


def _item(nom, ref, pins):
    return (f"<DataItem><Name>{nom}</Name><reference>{ref}</reference>"
            f"<value></value><datapin>{''.join(pins)}</datapin>"
            f"<CtrIem><X>0</X><Y>0</Y></CtrIem><angle>0</angle></DataItem>")


def _carte(items):
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<BoardSCH>'
            f'<CmpntL>{"".join(items)}</CmpntL>'
            f'<lineL /><CCmpntL /><Texts /><NetLabels /><Vias /></BoardSCH>')


@pytest.fixture(autouse=True)
def _reset_cache():
    """Le pont met en cache `component_library.json` au premier appel : sans
    reset, un test polluerait le suivant avec l'ancien contenu/chemin."""
    xml_mod._cache_types_personnalises = None
    yield
    xml_mod._cache_types_personnalises = None


def _bibliotheque(tmp_path, entrees, monkeypatch):
    chemin = tmp_path / "component_library.json"
    chemin.write_text(json.dumps(entrees), encoding="utf-8")
    monkeypatch.setattr("circuit_analyzer.composant.chemin_bibliotheque",
                        lambda: chemin)


@pytest.mark.parametrize("prefixe_stocke", ["M", "MOS", "M2"], ids=[
    "prefixe_manuel_reserve_impossible_en_pratique",
    "prefixe_auto_import_en_masse",
    "prefixe_arbitraire",
])
def test_mosfet_reconnu_quelle_que_soit_la_cle_de_prefixe(tmp_path, monkeypatch, prefixe_stocke):
    """Le type électrique vient des NOMS DE BROCHES (G/D/S), jamais de la clé de
    préfixe sous laquelle l'entrée est rangée dans component_library.json — les
    trois formes de clé réellement rencontrées doivent toutes marcher."""
    _bibliotheque(tmp_path, {
        prefixe_stocke: {"name": "MOSFET canal N", "pins": ["G", "D", "S"]},
    }, monkeypatch)
    monkeypatch.delenv("ERETRO_LIB", raising=False)

    xml = _carte([_item("MOSFET canal N", "X1",
                        [_pin("1"), _pin("2"), _pin("3")])])
    chemin = tmp_path / "carte.xml"
    chemin.write_text(xml, encoding="utf-8")

    composants = lire_xml(str(chemin))
    assert len(composants) == 1
    comp = composants[0]
    assert comp.type == "M", "toujours X : le pont vers component_library.json ne marche pas"
    assert any("bibliothèque personnalisée" in w for w in composants.warnings)


@pytest.mark.parametrize("pins,type_attendu", [
    (["A", "K"], "D"),
    (["+", "-"], "D"),
    (["B", "C", "E"], "Q"),
    (["G", "D", "S"], "M"),
    (["A1", "A2", "11", "12", "14"], "K"),
], ids=["diode_AK", "diode_plus_moins", "bjt_BCE", "mosfet_GDS", "relais_A1A2_11_12_14"])
def test_signatures_de_broches_reconnues(tmp_path, monkeypatch, pins, type_attendu):
    """Chaque signature de broches canonique doit résoudre vers son type électrique."""
    _bibliotheque(tmp_path, {"X9": {"name": "Composant perso", "pins": pins}}, monkeypatch)
    monkeypatch.delenv("ERETRO_LIB", raising=False)

    xml = _carte([_item("Composant perso", "X1", [_pin(str(i + 1), p)
                                                  for i, p in enumerate(pins)])])
    chemin = tmp_path / "carte.xml"
    chemin.write_text(xml, encoding="utf-8")

    assert lire_xml(str(chemin))[0].type == type_attendu


def test_signature_inconnue_devient_boite_ic_etiquetee_pas_x():
    """3 broches A/K/REF (ex. TL431, régulateur shunt) ne correspond à aucune
    signature diode/BJT/MOSFET connue : repli 'U' (boîte IC étiquetée du nom
    réel), jamais laissé invisible en X — c'est déjà mieux qu'avant (le nom
    et les vraies broches restent lisibles) même sans type électrique précis."""
    from circuit_analyzer.xml import _deviner_type_et_plan
    type_prefix, plan = _deviner_type_et_plan(["A", "K", "REF"])
    assert type_prefix == "U"
    assert plan == {"A": "A", "K": "K", "REF": "REF"}


@pytest.mark.parametrize("pins", [["1", "2"], ["FUSE1", "FUSE2"], ["1"]],
                          ids=["deux_broches_numeriques", "deux_broches_nommees", "une_broche"])
def test_moins_de_3_broches_sans_signature_ne_devient_pas_circuit_integre(pins):
    """BUG TROUVÉ EN TESTANT (« ça lit des composants simples comme des circuits
    intégrés ») : un composant à 1 ou 2 broches (fusible, self, interrupteur,
    résistance non standard…) ne correspond à aucune signature D/Q/M/K connue,
    mais ce n'est PAS pour autant une IC — son nom "1"/"2" est générique et
    indiscernable entre types passifs. `_deviner_type_et_plan` doit s'abstenir
    (None) plutôt que de forcer 'U', pour laisser le reste de `lire_xml` (repli
    par forme, ou X) trancher."""
    from circuit_analyzer.xml import _deviner_type_et_plan
    assert _deviner_type_et_plan(pins) is None


def test_composant_simple_a_2_broches_ne_devient_pas_circuit_integre_a_la_lecture(
        tmp_path, monkeypatch):
    """Bout-en-bout de la même correction : un composant personnalisé à 2 broches
    (ex. un fusible custom) enregistré dans l'onglet Composants ne doit plus
    ressortir type 'U' à la lecture d'une VRAIE carte -- il retombe X (repli
    normal pour un nom non reconnu), pas une fausse IC."""
    _bibliotheque(tmp_path, {"FUS2": {"name": "Fusible perso", "pins": ["1", "2"]}}, monkeypatch)
    monkeypatch.delenv("ERETRO_LIB", raising=False)

    xml = _carte([_item("Fusible perso", "X1", [_pin("1"), _pin("2")])])
    chemin = tmp_path / "carte.xml"
    chemin.write_text(xml, encoding="utf-8")

    assert lire_xml(str(chemin))[0].type != "U"


def test_broches_renommees_via_le_symbole_source_quand_disponible(tmp_path, monkeypatch):
    """Avec le dossier de bibliothèque partagée disponible (ERETRO_LIB), les
    broches brutes Pnumber "1"/"2"/"3" doivent se renommer en G/D/S (via
    `eretro_symboles.plan_alias`), pas rester numériques."""
    dossier_symboles = tmp_path / "LibItem_Lib"
    dossier_symboles.mkdir()
    (dossier_symboles / "MOSFET canal N.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        "<DataItem><Name>MOSFET canal N</Name><datapolygon /><datasegment />"
        "<dataarc /><datapin>"
        + _pin("1", "G") + _pin("2", "D") + _pin("3", "S")
        + "</datapin><typ>0</typ></DataItem>", encoding="utf-8")
    monkeypatch.setenv("ERETRO_LIB", str(dossier_symboles))

    _bibliotheque(tmp_path, {
        "MOS": {"name": "MOSFET canal N", "pins": ["G", "D", "S"]},
    }, monkeypatch)

    xml = _carte([_item("MOSFET canal N", "X1",
                        [_pin("1"), _pin("2"), _pin("3")])])
    chemin = tmp_path / "carte.xml"
    chemin.write_text(xml, encoding="utf-8")

    composants = lire_xml(str(chemin))
    comp = composants[0]
    assert comp.type == "M"
    assert set(comp.pins) == {"G", "D", "S"}, \
        f"broches non renommees via le symbole source : {comp.pins!r}"


def _item_avec_geometrie(nom, ref, pins):
    """@brief <DataItem> AVEC un vrai contour (segment) -- `_item` ci-dessus n'en a
    pas, donc `_forme_et_brochage_reels()` n'y trouve jamais rien à capturer."""
    return (f"<DataItem><Name>{nom}</Name><reference>{ref}</reference>"
            f"<value></value>"
            f"<datasegment><DataSegment><Spoint><X>-40</X><Y>0</Y></Spoint>"
            f"<Epoint><X>40</X><Y>0</Y></Epoint></DataSegment></datasegment>"
            f"<datapin>{''.join(pins)}</datapin>"
            f"<CtrIem><X>0</X><Y>0</Y></CtrIem><angle>0</angle></DataItem>")


def test_composant_a_plan_nomme_recoit_le_vrai_contour_a_l_ouverture(tmp_path, monkeypatch):
    """BUG TROUVÉ EN TESTANT (« quand j'ouvre le schéma depuis un fichier XML c'est
    le symbole AOP qui s'affiche, pas celui d'ERetroDesign ») : poser depuis la
    palette utilisait déjà la vraie forme (clé de bibliothèque dédiée), mais OUVRIR
    un fichier XML passe par `lire_xml` -> `Component.primitives`/`pinout`, restés
    vides pour tout type à plan NOMMÉ (ici via `_types_personnalises`, mais la même
    capture s'applique à un AOP catalogue natif) -- l'éditeur de schéma retombait
    alors sur le gabarit générique par type ('U' -> triangle AOP, broches comprises :
    « les pins sont encore celles de 3 broches d'ampli »). `comp.primitives` ET
    `comp.pinout` doivent porter le VRAI contour/les vraies positions, rekeyées avec
    le MÊME nommage sémantique que `comp.pins` (sinon l'éditeur perdrait des
    connexions en recoupant pins/pinout par nom)."""
    _bibliotheque(tmp_path, {
        "MOS": {"name": "MOSFET canal N", "pins": ["G", "D", "S"]},
    }, monkeypatch)
    monkeypatch.delenv("ERETRO_LIB", raising=False)

    xml = _carte([_item_avec_geometrie("MOSFET canal N", "X1",
                                       [_pin("1", "G"), _pin("2", "D"), _pin("3", "S")])])
    chemin = tmp_path / "carte.xml"
    chemin.write_text(xml, encoding="utf-8")

    comp = lire_xml(str(chemin))[0]
    assert comp.type == "M"
    assert comp.primitives, "aucun contour reel capture : retombe sur le triangle AOP generique"
    assert comp.pins == {"G": "NET1", "D": "NET2", "S": "NET3"}
    assert comp.pinout is not None
    assert set(comp.pinout) == set(comp.pins) == {"G", "D", "S"}, \
        f"pinout et pins desynchronises : pinout={comp.pinout!r} pins={comp.pins!r}"


def test_round_trip_generer_xml_conserve_le_type_d_un_composant_a_plan_nomme(tmp_path, monkeypatch):
    """BUG TROUVÉ EN TESTANT (carte réelle PG 3.xml, suite du test ci-dessus) :
    exporter puis relire un composant à plan nommé (ici MOSFET via la bibliothèque
    personnalisée) doit conserver son type -- pas seulement au premier lire_xml."""
    from circuit_analyzer.xml import generer_xml

    _bibliotheque(tmp_path, {
        "MOS": {"name": "MOSFET canal N", "pins": ["G", "D", "S"]},
    }, monkeypatch)
    monkeypatch.delenv("ERETRO_LIB", raising=False)

    xml = _carte([_item_avec_geometrie("MOSFET canal N", "X1",
                                       [_pin("1", "G"), _pin("2", "D"), _pin("3", "S")])])
    chemin = tmp_path / "carte.xml"
    chemin.write_text(xml, encoding="utf-8")
    avant = lire_xml(str(chemin))

    chemin2 = tmp_path / "carte2.xml"
    chemin2.write_text(generer_xml(avant), encoding="utf-8")
    xml_mod._cache_types_personnalises = None
    apres = lire_xml(str(chemin2))

    assert apres[0].type == "M", \
        f"type perdu au round-trip generer_xml : {apres[0].type!r}"


def test_catalogue_generique_plan_vide_ne_capture_toujours_pas_de_contour(tmp_path, monkeypatch):
    """Non-régression : un type PuceN générique (plan vide `{}`, broches
    purement numériques) garde `primitives is None` — sa géométrie est un
    gabarit DIP synthétique, pas un vrai contour importé (cf.
    tests/test_xml_generator.py::test_generer_xml_puce_generique_*)."""
    monkeypatch.setattr("circuit_analyzer.composant.chemin_bibliotheque",
                        lambda: tmp_path / "absent.json")
    monkeypatch.delenv("ERETRO_LIB", raising=False)

    xml = _carte([_item_avec_geometrie("Puce8", "U1",
                                       [_pin(str(i)) for i in range(1, 9)])])
    chemin = tmp_path / "carte.xml"
    chemin.write_text(xml, encoding="utf-8")

    comp = lire_xml(str(chemin))[0]
    assert comp.primitives is None


def test_aucune_bibliotheque_personnalisee_ne_change_rien(tmp_path, monkeypatch):
    """Sans component_library.json (cas courant, ou l'utilisateur n'a rien
    enregistré), le composant inconnu reste X — comportement d'avant ce
    pont, non-régression."""
    monkeypatch.setattr("circuit_analyzer.composant.chemin_bibliotheque",
                        lambda: tmp_path / "absent.json")
    monkeypatch.delenv("ERETRO_LIB", raising=False)

    xml = _carte([_item("MOSFET canal N", "X1",
                        [_pin("1"), _pin("2"), _pin("3")])])
    chemin = tmp_path / "carte.xml"
    chemin.write_text(xml, encoding="utf-8")

    composants = lire_xml(str(chemin))
    assert composants[0].type == "X"
