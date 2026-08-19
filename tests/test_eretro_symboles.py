"""@file test_eretro_symboles.py
@brief Chargement de la bibliotheque VIVANTE d'ERetroDesign (LibItem/Lib).

Sa bibliotheque est un <DataItem> complet par composant depuis son
[MODIF 2026-07-24] (Form1.cs:6104). Ne pas confondre avec bin/Debug/Lib/,
fonds MORT dont les symboles font ~997x201 et n'ont ni Name ni typ.
"""
import os
import xml.etree.ElementTree as ET
from copy import deepcopy

import pytest

from circuit_analyzer import eretro_symboles

_DOSSIER_REEL = os.path.join("ERetroDesign", "ERetroDesign", "bin", "Debug",
                             "LibItem", "Lib")


def _symbole(tmp_path, nom, pins, typ="0", segments=1):
    """@brief Ecrit un symbole minimal au format LibItem/Lib."""
    dp = "".join(
        f"<DataPin><Pname>{n}</Pname><Pnumber>{n}</Pnumber>"
        f"<Pin><X>{x}</X><Y>{y}</Y></Pin></DataPin>"
        for n, (x, y) in pins.items())
    seg = "".join(
        "<DataSegment><Spoint><X>-10</X><Y>0</Y></Spoint>"
        "<Epoint><X>10</X><Y>0</Y></Epoint></DataSegment>"
        for _ in range(segments))
    chemin = os.path.join(str(tmp_path), nom + ".xml")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(f'<?xml version="1.0" encoding="utf-8"?>'
                f"<DataItem><Name>{nom}</Name>"
                f"<datapolygon /><datasegment>{seg}</datasegment><dataarc />"
                f"<datapin>{dp}</datapin><typ>{typ}</typ></DataItem>")
    return chemin


def test_un_symbole_donne_ses_broches_avec_leur_rang(tmp_path):
    """Le 3e membre du tuple est le RANG dans <datapin> : c'est lui que
    `_xml_composant` emet comme index de broche, et sur lequel les refs de
    connexion `cid_pidx_..._wid` sont construites."""
    _symbole(tmp_path, "Truc", {"2": (-80, 0), "1": (80, 0)})
    formes = eretro_symboles.charger(str(tmp_path))
    assert formes["Truc"]["pins"] == {"2": (-80, 0, 0), "1": (80, 0, 1)}


def test_la_geometrie_ressort_en_fragments_xml(tmp_path):
    """`_FORME` stocke polygon/segment/arc en CHAINE XML, prete a etre
    concatenee par `_xml_composant`. On rend donc la meme chose."""
    _symbole(tmp_path, "Truc", {"1": (0, 0)}, segments=2)
    f = eretro_symboles.charger(str(tmp_path))["Truc"]
    assert f["segment"].count("<DataSegment>") == 2
    assert f["polygon"] == "" and f["arc"] == ""
    ET.fromstring("<r>" + f["segment"] + "</r>")   # fragment bien forme


def test_le_typ_du_symbole_est_rendu(tmp_path):
    _symbole(tmp_path, "Truc", {"1": (0, 0)}, typ="76")
    assert eretro_symboles.charger(str(tmp_path))["Truc"]["typ"] == 76


def test_un_symbole_sans_broche_est_ecarte(tmp_path):
    """Un symbole sans broche ne se cable pas : le garder ferait disparaitre
    en silence toutes les liaisons du composant qui l'utiliserait."""
    _symbole(tmp_path, "Muet", {})
    assert "Muet" not in eretro_symboles.charger(str(tmp_path))


def test_un_symbole_corrompu_n_empeche_pas_les_autres(tmp_path):
    """Robustesse exigee par la spec : on lit le dossier d'un TIERS, qui
    bouge sans nous prevenir."""
    _symbole(tmp_path, "Bon", {"1": (0, 0)})
    with open(os.path.join(str(tmp_path), "Casse.xml"), "w", encoding="utf-8") as f:
        f.write("<DataItem><Name>Casse</Name><datapin>")   # jamais referme
    formes = eretro_symboles.charger(str(tmp_path))
    assert "Bon" in formes and "Casse" not in formes


def test_un_dossier_absent_ne_leve_pas(tmp_path):
    """La CI n'a pas son dossier, et le .exe livre non plus."""
    assert eretro_symboles.charger(os.path.join(str(tmp_path), "nexiste_pas")) == {}


def test_le_chemin_vient_de_la_variable_d_environnement(tmp_path, monkeypatch):
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    assert eretro_symboles.chemin_par_defaut() == str(tmp_path)


def test_le_chemin_vient_du_dossier_partage_gui_si_pas_de_variable_env(
        tmp_path, monkeypatch):
    """Bug reel : sans ERETRO_LIB, seul un chemin relatif code en dur etait
    tente — l'utilisateur devait poser une variable d'environnement pour
    pointer vers la bibliotheque du collegue. Le dossier deja choisi via
    l'onglet Composants (persistant dans config/eretro_biblio.json, via
    eretro_lib.dossier_partage) doit desormais servir de secours
    automatique et reconfigurable sans variable d'environnement."""
    from circuit_analyzer import eretro_lib
    monkeypatch.delenv("ERETRO_LIB", raising=False)
    monkeypatch.setattr(eretro_lib, "_chemin_config", lambda: tmp_path / "cfg.json")
    dossier_lib = tmp_path / "biblio_partagee"
    dossier_lib.mkdir()
    eretro_lib.definir_dossier_partage(str(dossier_lib))
    assert eretro_symboles.chemin_par_defaut() == str(dossier_lib)


def test_la_variable_d_environnement_l_emporte_sur_le_dossier_partage_gui(
        tmp_path, monkeypatch):
    """La variable d'environnement reste la surcharge « développeur/CI » :
    un dossier partagé déjà mémorisé sur la machine ne doit jamais la
    court-circuiter silencieusement."""
    from circuit_analyzer import eretro_lib
    monkeypatch.setattr(eretro_lib, "_chemin_config", lambda: tmp_path / "cfg.json")
    dossier_lib = tmp_path / "biblio_partagee"
    dossier_lib.mkdir()
    eretro_lib.definir_dossier_partage(str(dossier_lib))
    dossier_env = tmp_path / "biblio_env"
    dossier_env.mkdir()
    monkeypatch.setenv("ERETRO_LIB", str(dossier_env))
    assert eretro_symboles.chemin_par_defaut() == str(dossier_env)


@pytest.mark.skipif(not os.path.isdir(_DOSSIER_REEL), reason="ERetroDesign absent")
def test_sa_vraie_bibliotheque_se_charge():
    """Garde-fou anti-test-creux : les tests ci-dessus tournent sur des
    symboles que NOUS fabriquons. Celui-ci lit les siens."""
    formes = eretro_symboles.charger(_DOSSIER_REEL)
    assert {"Résistance", "Capa", "AOP", "Diode", "GND", "Self", "2N2B"} <= set(formes)
    r = formes["Résistance"]
    assert set(r["pins"]) == {"1", "2"}
    assert r["pins"]["1"][:2] == (80, 0)
    assert r["pins"]["2"][:2] == (-80, 0)
    aop = formes["AOP"]
    assert set(aop["pins"]) == {"+", "-", "s"}, \
        "ses noms de broches sont ceux de nos plans _TYPE_VERS_FORME"


def _symbole_alias(tmp_path, nom, pins_pnumber_pname):
    """@brief Symbole avec Pnumber != Pname (cas MOSFET/TL431 : broche brute
    numérique, nom sémantique distinct) — `_symbole` ci-dessus les force égaux."""
    dp = "".join(
        f"<DataPin><Pname>{pname}</Pname><Pnumber>{pnum}</Pnumber>"
        f"<Pin><X>0</X><Y>0</Y></Pin></DataPin>"
        for pnum, pname in pins_pnumber_pname)
    chemin = os.path.join(str(tmp_path), nom + ".xml")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(f'<?xml version="1.0" encoding="utf-8"?>'
                f"<DataItem><Name>{nom}</Name>"
                f"<datapolygon /><datasegment /><dataarc />"
                f"<datapin>{dp}</datapin><typ>0</typ></DataItem>")
    return chemin


def test_plan_alias_relie_la_broche_brute_pnumber_au_nom_semantique_pname():
    """BUG TROUVÉ EN TESTANT (session gabarits, 2026-08-18) : `lire_xml`
    identifie une broche par Pnumber EN PRIORITÉ (pnum or pnom), alors que la
    bibliothèque personnalisée (onglet Composants) ne retient que le nom
    AFFICHÉ (Pname en priorité) — sur "MOSFET canal N" (Pnumber 1/2/3, Pname
    G/D/S), un plan {"G":"G","D":"D","S":"S"} seul ne matche JAMAIS la broche
    brute "1"/"2"/"3" que lire_xml cherche réellement. `plan_alias` doit
    fournir le pont : broche brute -> nom sémantique."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        chemin = _symbole_alias(d, "MOSFET canal N",
                                 [("1", "G"), ("2", "D"), ("3", "S")])
        plan = eretro_symboles.plan_alias(chemin)
    assert plan["1"] == "G" and plan["2"] == "D" and plan["3"] == "S"
    assert plan["G"] == "G" and plan["D"] == "D" and plan["S"] == "S"


def test_plan_alias_reste_identite_quand_pname_et_pnumber_coincident():
    """Un symbole où Pname == Pnumber (la majorité de la bibliothèque, ex.
    Résistance "1"/"2") n'a besoin d'aucun alias réel : le plan reste
    l'identité pure, `plan.get(pnom, pnom)` côté appelant y retombe de toute
    façon même sans cette entrée."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        chemin = _symbole_alias(d, "Truc", [("1", "1"), ("2", "2")])
        plan = eretro_symboles.plan_alias(chemin)
    assert plan == {"1": "1", "2": "2"}


def test_ses_formes_ecrasent_les_notres_a_nom_egal(tmp_path, monkeypatch):
    """Decision du boss : SA geometrie fait foi sur les noms communs."""
    _symbole(tmp_path, "Résistance", {"1": (80, 0), "2": (-80, 0)}, segments=3)
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    import importlib

    from circuit_analyzer import xml as cx
    importlib.reload(cx)
    try:
        assert cx._FORME["Résistance"]["segment"].count("<DataSegment>") == 3
        assert cx._FORME_MAISON["Résistance"]["segment"].count("<DataSegment>") != 3
    finally:
        monkeypatch.delenv("ERETRO_LIB")
        importlib.reload(cx)


def test_nos_orphelines_survivent_a_la_fusion(tmp_path, monkeypatch):
    """Il n'a ni MOSFET ni Fusible ni PuceN : les ecraser par un dict vide
    supprimerait des formes dont l'export depend."""
    _symbole(tmp_path, "Résistance", {"1": (80, 0), "2": (-80, 0)})
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    import importlib

    from circuit_analyzer import xml as cx
    importlib.reload(cx)
    try:
        assert {"MOSFET", "Fusible", "Puce4", "Puce8"} <= set(cx._FORME)
    finally:
        monkeypatch.delenv("ERETRO_LIB")
        importlib.reload(cx)


def test_le_typ_reste_le_notre(tmp_path, monkeypatch):
    """MESURE : son GND.xml porte typ=0 alors que le notre vaut 71 ('G'),
    valeur dont `eretro.classer_rail` se sert pour reconnaitre une masse.
    Adopter son typ ferait perdre la classification des rails."""
    _symbole(tmp_path, "GND", {"1": (0, -47)}, typ="0")
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    import importlib

    from circuit_analyzer import xml as cx
    importlib.reload(cx)
    try:
        assert cx._TYP_COMPOSANT["GND"] == 71
    finally:
        monkeypatch.delenv("ERETRO_LIB")
        importlib.reload(cx)


def test_positions_des_broches_suivent_sa_bibliotheque(tmp_path, monkeypatch):
    """Les positions (x, y) viennent de SA bibliotheque, les noms de CLE
    restent les notres. Fusionner par RANG : pour chaque broche de notre
    forme (triée par rang), prendre la POSITION de la sienne au même rang,
    en gardant NOTRE nom de clé."""
    # Notre Résistance a pins {"1": (80, 0, 1), "2": (-80, 0, 0)}
    # Rangs : "2" rank 0, "1" rank 1
    # Créer un symbole avec les mêmes rangs mais positions DIFFÉRENTES
    _symbole(tmp_path, "Résistance", {"2": (-85, -3), "1": (90, 5)})
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    import importlib

    from circuit_analyzer import xml as cx
    importlib.reload(cx)
    try:
        # Vérifier que les positions viennent de la sienne
        r1_pos = cx._FORME["Résistance"]["pins"]["1"][:2]
        r2_pos = cx._FORME["Résistance"]["pins"]["2"][:2]
        assert r1_pos == (90, 5), "Position de '1' (rang 1) doit venir de sa biblio"
        assert r2_pos == (-85, -3), "Position de '2' (rang 0) doit venir de sa biblio"
        # Vérifier que les noms de clé restent les nôtres
        assert "1" in cx._FORME["Résistance"]["pins"]
        assert "2" in cx._FORME["Résistance"]["pins"]
    finally:
        monkeypatch.delenv("ERETRO_LIB")
        importlib.reload(cx)


def test_broches_manquantes_du_plan_replient_sur_la_forme_maison(tmp_path, monkeypatch, caplog):
    """Revue finale, Important #1 : `_idx_broche_forme` (xml.py:1053) fait un
    lookup NON protege `_FORME[nom]["pins"][broche][2]`. Si un plan de
    `_TYPE_VERS_FORME` reclame un nom de broche absent de la forme fusionnee
    (typiquement une forme neuve arrivee via son dossier, dont les noms de
    broches ne couvrent pas notre plan), `generer_xml()` plante avec un
    KeyError brut. Latent aujourd'hui (aucun plan reel n'est dans ce cas),
    mais son dossier bouge sans nous prevenir : on valide apres fusion et on
    replie sur la forme maison plutot que de laisser le plantage arriver."""
    from circuit_analyzer import xml as cx

    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))   # dossier vide -> {}
    plan_original = cx._TYPE_VERS_FORME["R"]
    forme_avant = deepcopy(cx._FORME["Résistance"])
    forme_maison_attendue = deepcopy(cx._FORME_MAISON["Résistance"])
    cx._TYPE_VERS_FORME["R"] = ("Résistance",
                                {"1": "1", "2": "2", "3": "broche_fantome"})
    try:
        with caplog.at_level("WARNING", logger="circuit_analyzer.xml"):
            cx._fusionner_bibliotheque_eretro()
        messages = [rec.getMessage() for rec in caplog.records]
        assert any("Résistance" in m and "broche_fantome" in m for m in messages), \
            "la broche manquante du plan doit etre journalisee, nommant la forme"
        assert cx._FORME["Résistance"] == forme_maison_attendue, \
            "repli integral sur la forme maison : aucun risque de KeyError plus tard"
    finally:
        cx._TYPE_VERS_FORME["R"] = plan_original
        cx._FORME["Résistance"] = forme_avant
        monkeypatch.delenv("ERETRO_LIB")


def test_ecart_de_rangs_entre_nos_broches_et_les_siennes_est_journalise(tmp_path, monkeypatch, caplog):
    """Revue finale, Important #2 : quand sa forme et la notre partagent un
    nom mais n'ont pas le meme NOMBRE de broches (ou pas les memes rangs), la
    fusion par rang (Tour de Correction 1) garde silencieusement notre
    position d'origine pour le rang orphelin, et laisse tomber ses broches
    en trop. Comportement de repli inchange : ce test verifie seulement que
    l'ecart est desormais journalise et que la fusion ne plante pas."""
    # Notre Résistance a 2 broches : "1" au rang 1, "2" au rang 0. On ne lui
    # en donne qu'une seule (rang 0) : rangs qui ne correspondent plus.
    _symbole(tmp_path, "Résistance", {"1": (90, 5)})
    monkeypatch.setenv("ERETRO_LIB", str(tmp_path))
    import importlib

    from circuit_analyzer import xml as cx
    with caplog.at_level("WARNING", logger="circuit_analyzer.xml"):
        importlib.reload(cx)
    try:
        messages = [rec.getMessage() for rec in caplog.records]
        assert any("Résistance" in m for m in messages), \
            "l'ecart de rangs de broches doit etre journalise"
        # Rang orphelin (rang 1, notre "1") : on garde NOTRE position d'origine.
        assert cx._FORME["Résistance"]["pins"]["1"][:2] == (80, 0)
        # Rang qui correspond (rang 0, notre "2") : sa position est prise.
        assert cx._FORME["Résistance"]["pins"]["2"][:2] == (90, 5)
    finally:
        monkeypatch.delenv("ERETRO_LIB")
        importlib.reload(cx)


def test_formes_orphelines_sans_dossier_donne_tout_le_maison():
    """Sans dossier partage, rien a comparer : tout ce qu'on a est "orphelin"."""
    from circuit_analyzer.xml import _FORME_MAISON, formes_orphelines
    orph, _typs = formes_orphelines(None)
    assert set(orph) == set(_FORME_MAISON)


def test_formes_orphelines_exclut_les_noms_deja_chez_lui(tmp_path):
    from circuit_analyzer.xml import formes_orphelines
    _symbole(tmp_path, "Résistance", {"1": (80, 0), "2": (-80, 0)})
    orph, _typs = formes_orphelines(str(tmp_path))
    assert "Résistance" not in orph
    assert "MOSFET" in orph          # jamais chez lui (formes de test minimales)


def test_formes_orphelines_typs_restreint_aux_orphelines(tmp_path):
    from circuit_analyzer.xml import formes_orphelines
    _symbole(tmp_path, "AGND", {"1": (0, 0)})
    orph, typs = formes_orphelines(str(tmp_path))
    assert "AGND" not in orph
    assert "AGND" not in typs        # plus orpheline -> plus dans le sous-ensemble typs
    assert typs.get("VCC") == 86     # orpheline connue, typ present dans _TYP_COMPOSANT


def test_pousser_ecrit_un_fichier_par_forme(tmp_path):
    from circuit_analyzer.eretro_lib import ecrire_formes_dans_dossier
    formes = {"MonSymbole": {"pins": {"1": (-80, 0, 0), "2": (80, 0, 1)},
                             "polygon": "", "arc": "",
                             "segment": "<DataSegment><Spoint><X>-10</X>"
                                        "<Y>0</Y></Spoint><Epoint><X>10</X>"
                                        "<Y>0</Y></Epoint></DataSegment>"}}
    ecrits = ecrire_formes_dans_dossier(str(tmp_path), formes)
    assert len(ecrits) == 1
    assert os.path.isfile(os.path.join(str(tmp_path), "MonSymbole.xml"))


def test_le_fichier_pousse_est_relisible_par_notre_chargeur(tmp_path):
    """Aller-retour : ce qu'on lui envoie doit revenir identique chez nous.
    C'est la seule verification d'integrite qu'on puisse faire sans son GUI."""
    from circuit_analyzer.eretro_lib import ecrire_formes_dans_dossier
    formes = {"MonSymbole": {"pins": {"1": (-80, 0, 0), "2": (80, 0, 1)},
                             "polygon": "", "arc": "",
                             "segment": "<DataSegment><Spoint><X>-10</X>"
                                        "<Y>0</Y></Spoint><Epoint><X>10</X>"
                                        "<Y>0</Y></Epoint></DataSegment>"}}
    ecrire_formes_dans_dossier(str(tmp_path), formes)
    relu = eretro_symboles.charger(str(tmp_path))
    assert relu["MonSymbole"]["pins"] == {"1": (-80, 0, 0), "2": (80, 0, 1)}


def test_on_n_ecrase_jamais_un_symbole_a_lui(tmp_path):
    """Regle absolue : sa bibliotheque est SON travail. `ecrire_dans_dossier`
    documente deja qu'on n'efface jamais son dossier ; ici on ne remplace pas
    davantage un fichier existant."""
    from circuit_analyzer.eretro_lib import ecrire_formes_dans_dossier
    cible = os.path.join(str(tmp_path), "Sien.xml")
    with open(cible, "w", encoding="utf-8") as f:
        f.write("<DataItem><Name>Sien</Name></DataItem>")
    ecrits = ecrire_formes_dans_dossier(
        str(tmp_path), {"Sien": {"pins": {"1": (0, 0, 0)},
                                 "polygon": "", "segment": "", "arc": ""}})
    assert ecrits == []
    with open(cible, encoding="utf-8") as f:
        assert f.read() == "<DataItem><Name>Sien</Name></DataItem>"


def test_pin_absente_est_journalisee(tmp_path, caplog):
    """Revue finale, correctif groupe : un <DataPin> sans <Pin> est deja
    ecarte en silence (comportement voulu, cf. docstring de _lire_symbole),
    mais rien ne le journalisait. Sans log, ce mode de defaillance n'est pas
    diagnosticable sur le terrain."""
    chemin = os.path.join(str(tmp_path), "Trou.xml")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(
            '<?xml version="1.0" encoding="utf-8"?>'
            "<DataItem><Name>Trou</Name><datapolygon /><datasegment />"
            "<dataarc /><datapin>"
            "<DataPin><Pname>1</Pname></DataPin>"  # pas de <Pin> : ecartee
            "<DataPin><Pname>2</Pname><Pnumber>2</Pnumber>"
            "<Pin><X>10</X><Y>0</Y></Pin></DataPin>"
            "</datapin><typ>0</typ></DataItem>")
    with caplog.at_level("WARNING", logger="circuit_analyzer.eretro_symboles"):
        formes = eretro_symboles.charger(str(tmp_path))
    assert set(formes["Trou"]["pins"]) == {"2"}, \
        "la broche sans <Pin> reste ecartee : comportement inchange"
    messages = [rec.getMessage() for rec in caplog.records]
    assert any("Trou" in m for m in messages), \
        "la broche manquante doit etre journalisee, pas juste disparaitre"


def test_la_boite_de_palette_porte_la_constante_de_son_format(tmp_path):
    """A TL=BR=(0,0) le composant s'affiche dans sa palette mais est
    IMPOSSIBLE a selectionner (eretro_lib.py:37-45)."""
    from circuit_analyzer.eretro_lib import ecrire_formes_dans_dossier
    ecrire_formes_dans_dossier(
        str(tmp_path), {"S": {"pins": {"1": (0, 0, 0)},
                              "polygon": "", "segment": "", "arc": ""}})
    r = ET.parse(os.path.join(str(tmp_path), "S.xml")).getroot()
    assert (r.find("TL").findtext("X"), r.find("TL").findtext("Y")) == ("50", "25")
    assert (r.find("BR").findtext("X"), r.find("BR").findtext("Y")) == ("210", "121")
