"""@file test_eretro_bibliotheque.py
@brief Vocabulaire de la bibliothèque ERetroDesign (version collègue, 2026-07-23).

Diagnostic à l'origine : sur les 52 composants de la bibliothèque livrée avec
l'éditeur, seuls 4 étaient reconnus (18 % en occurrences). Tout le reste —
« Résistance », « Capa », « Self », « AOP », « Gate2 » (33×) — devenait une
boîte noire X. Pire : les symboles d'alimentation portent `typ=0` et non
'G'/'V'/'N', donc AUCUN rail n'était détecté, ce qui empêche tout détecteur de
montage de fonctionner.
"""
import pathlib
import re

import pytest

from circuit_analyzer.eretro import classer_rail, mapper_nom, normaliser_nom

# ── Vocabulaire de la bibliothèque ───────────────────────────────────────────

@pytest.mark.parametrize("nom,type_attendu", [
    # Passifs — les plus élémentaires, et pourtant inconnus jusqu'ici.
    ("Résistance", "R"),
    ("Capa", "C"),
    ("Self", "L"),
    # Actifs
    ("Transistor", "Q"),
    ("Mosfet_controle", "M"),
    ("AOP", "U"),
    ("Regulateur", "U"),
    ("Optocoupleur_simple", "U"),
    # Contacts et relais
    ("Relais_1FormC", "K"),
    ("Contact_NO", "SW"),
    ("Contact_Form_C", "SW"),
    ("Bouton_poussoir_double", "SW"),
    # Portes logiques — « Gate2 » est le composant le plus utilisé (33×)
    ("Gate2", "U"),
    ("Gate2IC", "U"),
    ("Gates4G", "U"),
    ("INVERTER", "U"),
    ("Nand_gate", "U"),
    ("BUFFER", "U"),
    # Circuits intégrés nommés
    ("HC165", "U"),
    ("MC4094", "U"),
    ("8_etage_registre", "U"),
])
def test_nom_de_bibliotheque_reconnu(nom, type_attendu):
    resultat = mapper_nom(nom)
    assert resultat is not None, f"{nom!r} non reconnu"
    assert resultat[0] == type_attendu


def test_normalisation_accents_et_underscores():
    """Le mapping doit survivre à la casse, aux accents et aux underscores."""
    assert normaliser_nom("Résistance") == "resistance"
    assert normaliser_nom("Mosfet_controle") == "mosfet controle"
    assert mapper_nom("RÉSISTANCE")[0] == "R"
    assert mapper_nom("  self  ")[0] == "L"


# ── Rails d'alimentation ─────────────────────────────────────────────────────

@pytest.mark.parametrize("nom,rail", [
    ("GND", "GND"),
    ("Vss", "VSS"),
    ("VCC+", "VCC"),
    ("VCC-", "VSS"),
])
def test_rail_reconnu_par_le_nom_quand_typ_est_absent(nom, rail):
    """La bibliothèque du collègue écrit typ=0 : sans repli par le NOM, aucun
    rail n'est détecté et plus aucun montage ne peut être reconnu."""
    assert classer_rail("", "", 1, nom) == rail


def test_rail_exige_une_seule_broche():
    """Garde conservée : un composant 2 broches n'est jamais un rail, même
    nommé « GND » (le typ natif vaut parfois ord(nom[0]) par accident)."""
    assert classer_rail("", "", 2, "GND") is None
    assert classer_rail("", "", 3, "VCC+") is None


def test_rail_par_typ_reste_prioritaire():
    """Non-régression : le chemin historique par `typ` ne bouge pas."""
    assert classer_rail("G", "", 1) == "GND"
    assert classer_rail("V", "+12V", 1) == "+12V"
    assert classer_rail("N", "", 1) == "VSS"
    assert classer_rail("", "", 1) is None       # ni typ ni nom -> rien


# ── Non-régression du dialecte déjà mappé ────────────────────────────────────

@pytest.mark.parametrize("nom,type_attendu", [
    ("R 810", "R"), ("RINF", "R"), ("Transistor_NPN", "Q"),
    ("Condensateur_polarise", "C"), ("Photodiode", "D"), ("Led", "D"),
    ("Diode", "D"), ("relais 2rt", "K"), ("JUMPER", "J"), ("Borne", "J"),
])
def test_dialecte_des_vraies_cartes_inchange(nom, type_attendu):
    assert mapper_nom(nom)[0] == type_attendu


def test_inconnu_reste_inconnu():
    """Les noms brouillons restent None : une boîte noire honnête vaut mieux
    qu'un faux symbole (lot B, en attente du collègue)."""
    for nom in ("Nouveau6", "df", "1AM", "027A", "Tr20", "16 pins"):
        assert mapper_nom(nom) is None, nom


# ── Lot B : un nom indéchiffrable se lit en boîte honnête, jamais une erreur ──

def _carte_un_composant(tmp_path, nom, nb_broches):
    pins = "".join(
        f"<DataPin><Pname>{i}</Pname><Pnumber>{i}</Pnumber>"
        f"<NodeL><string>0_{i}_0_0</string></NodeL></DataPin>"
        for i in range(nb_broches))
    xml = (f'<?xml version="1.0"?><BoardSCH><CmpntL><DataItem>'
           f'<Name>{nom}</Name><reference>R3</reference><value></value>'
           f'<datapin>{pins}</datapin></DataItem></CmpntL>'
           f'<lineL/><CCmpntL/></BoardSCH>')
    p = tmp_path / "b.xml"
    p.write_text(xml, encoding="utf-8")
    return str(p)


@pytest.mark.parametrize("nom", ["df", "1AM", "027A", "Tr20", "16 pins",
                                 "J314", "L25010MH", "Nouveau6"])
@pytest.mark.parametrize("nb_broches", [2, 8])
def test_nom_indechiffrable_se_lit_en_boite_sans_erreur(nom, nb_broches,
                                                        tmp_path):
    """Contrat du lot B : faute de savoir typer, on rend une boîte (X si peu de
    broches, U étiquetée si assez pour une IC) SANS perdre les connexions et
    SANS lever. Le collègue tranchera la sémantique plus tard."""
    from circuit_analyzer.xml import lire_xml
    comps = lire_xml(_carte_un_composant(tmp_path, nom, nb_broches))
    assert len(comps) == 1
    c = comps[0]
    assert c.type in ("X", "U"), f"{nom} typé {c.type} sans preuve"
    assert len(c.pins) == nb_broches      # aucune broche perdue


# ── Couverture réelle de la bibliothèque livrée ──────────────────────────────

_BIBLIO = pathlib.Path(__file__).resolve().parents[1] / (
    "ERetroDesign/ERetroDesign/bin/Debug")


def _noms_bibliotheque():
    """@brief Noms de TOUTE la bibliothèque ERetroDesign courante.

    Depuis 2026-07-24 le C# stocke un `.xml` PAR COMPOSANT dans `LibItem/Lib`
    et `LibItem/CCLib` ; les agrégats `Lib.xml`/`CCompLib.xml` ne sont plus
    que des reliquats (celui livré avec la version du 2026-07-27 ne contient
    plus qu'un seul nom). Les lire SEULS faisait silencieusement tomber la
    couverture de 16 composants à 1 — on lit donc les dossiers AUSSI.
    """
    import collections
    noms = collections.Counter()
    sources = [_BIBLIO / "LibItem" / "Lib.xml", _BIBLIO / "LibItem" / "CCompLib.xml"]
    for dossier in (_BIBLIO / "LibItem" / "Lib", _BIBLIO / "LibItem" / "CCLib"):
        if dossier.is_dir():
            sources.extend(sorted(dossier.glob("*.xml")))
    for src in sources:
        if src.exists() and src.is_file():
            noms.update(
                n.strip() for n in re.findall(
                    r"<Name>(.*?)</Name>",
                    src.read_text(encoding="utf-8", errors="replace"))
                if n.strip())
    return noms


# Noms que PERSONNE ne peut interpréter sans demander au collègue : brouillons
# (« Nouveau12 »), codes maison (« 027A », « Tr20 ») ou références inconnues.
# Ils restent volontairement non mappés — une boîte noire honnête vaut mieux
# qu'un faux symbole. Lot B : à trancher avec l'auteur de la bibliothèque.
_LOT_B = {
    "Nouveau12", "Nouveau13", "Nouveau15", "Nouveau17", "Nouveau24",
    "027A", "16 pins", "1AM", "2N2B", "A J314", "A314J", "J314",
    "L25010MH", "CA", "BAV99", "Alim_unipolaire", "Pont_diode_monophase",
    # Composants d'essai du collègue : noms sans aucune portée électrique,
    # rien à déduire (« home » est apparu avec la version du 2026-07-27).
    "TATA", "yoyo", "home",
    # Potentiomètre : le patron a sa propre règle dans custom_circuits.json,
    # on ne la contredit pas ici.
    "Potentiomètre",
}


@pytest.mark.skipif(not _BIBLIO.exists(),
                    reason="bibliothèque ERetroDesign absente (lecture seule)")
def test_toute_la_bibliotheque_est_couverte_sauf_le_lot_b():
    """Chaque composant de la bibliothèque est soit typé, soit un rail, soit
    explicitement listé comme non interprétable.

    Formuler la cible ainsi plutôt qu'en pourcentage a un intérêt : si le
    collègue ajoute un composant, le test échoue en le NOMMANT, au lieu de
    laisser un seuil chiffré absorber silencieusement la régression.
    """
    noms = _noms_bibliotheque()
    assert noms, "aucun nom lu dans la bibliothèque"
    orphelins = sorted(
        n for n in noms
        if not mapper_nom(n) and classer_rail("", "", 1, n) is None
        and n not in _LOT_B)
    assert not orphelins, f"composants ni typés ni listés en lot B : {orphelins}"


@pytest.mark.skipif(not _BIBLIO.exists(),
                    reason="bibliothèque ERetroDesign absente (lecture seule)")
def test_couverture_ponderee_a_fortement_progresse():
    """Garde-fou chiffré : on partait de 18 % des occurrences."""
    noms = _noms_bibliotheque()
    total = sum(noms.values())
    couvert = sum(c for n, c in noms.items()
                  if mapper_nom(n) or classer_rail("", "", 1, n))
    assert couvert / total >= 0.70, f"{couvert}/{total}"


# ── Contresens de forme revele par le typage par nom ─────────────────────────

@pytest.mark.skipif(not _BIBLIO.exists(), reason="bibliothèque absente")
@pytest.mark.parametrize("symbole", ["BUFFER", "INVERTER"])
def test_triangle_n_est_jamais_un_condensateur(symbole):
    """Les deux arêtes obliques d'un triangle convergent en un sommet : ce ne
    sont pas des armatures. `classer_par_forme` les classait « C »."""
    import xml.etree.ElementTree as ET

    from circuit_analyzer import eretro
    geo = eretro.extraire_geometrie(
        ET.parse(_BIBLIO / "Lib" / f"{symbole}.xml").getroot())
    obtenu = eretro.classer_par_forme(geo)
    assert obtenu is None or obtenu[0] != "C", f"{symbole} classe {obtenu}"
