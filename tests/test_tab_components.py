"""@file test_tab_components.py
@brief Onglet Composants : brochage positionné (spec 2026-07-23).

Tk -> skip sans display. La bibliothèque est isolée dans tmp_path : le VRAI
`component_library.json` (règle perso du boss) ne doit JAMAIS être touché.
"""
import json

import pytest

ctk = pytest.importorskip("customtkinter")


class _Boites:
    """Remplace `messagebox` : une modale non neutralisée GÈLE la suite."""

    def __init__(self):
        self.infos, self.erreurs = [], []

    def showinfo(self, _titre, message=""):
        self.infos.append(message)

    def showerror(self, _titre, message=""):
        self.erreurs.append(message)

    def showwarning(self, _titre, message=""):
        self.erreurs.append(message)

    def askyesno(self, _titre, _message=""):
        return True          # abandon de saisie toujours autorisé en test


@pytest.fixture
def onglet(tmp_path, monkeypatch):
    chemin = tmp_path / "component_library.json"
    monkeypatch.setattr("gui.tab_components.chemin_bibliotheque",
                        lambda: chemin)
    boites = _Boites()
    monkeypatch.setattr("gui.tab_components.messagebox", boites)
    from gui.tab_components import TabComponents
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("pas de display Tk")
    root.withdraw()
    t = TabComponents(root)
    root.update_idletasks()
    t._boites = boites
    yield t, chemin
    root.destroy()


def test_sauvegarde_ecrit_pins_dans_l_ordre_et_le_brochage(onglet):
    t, chemin = onglet
    t._prefix_var.set("IC")
    t._name_var.set("Ampli")
    t._brochage = [("VCC", "T", 0), ("IN", "L", -20), ("GND", "B", 0)]
    t._sauvegarder()
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert data["IC"]["pins"] == ["VCC", "IN", "GND"]
    assert data["IC"]["brochage"]["VCC"] == ["T", 0]


def test_relecture_d_un_type_sans_brochage_amorce_les_broches(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps(
        {"ZZ": {"name": "Ancien", "pins": ["A", "B", "C"]}}),
        encoding="utf-8")
    t._load()
    t._afficher_perso("ZZ")
    noms = [n for n, _, _ in t._brochage]
    assert noms == ["A", "B", "C"]                  # aucune broche perdue
    assert all(c in ("L", "R", "T", "B") for _n, c, _d in t._brochage)


def test_relecture_d_un_type_avec_brochage_est_fidele(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({"IC": {
        "name": "Ampli", "pins": ["VCC", "IN", "GND"],
        "brochage": {"VCC": ["T", 0], "IN": ["L", -20], "GND": ["B", 0]}}}),
        encoding="utf-8")
    t._load()
    t._afficher_perso("IC")
    assert t._brochage == [("VCC", "T", 0), ("IN", "L", -20), ("GND", "B", 0)]


def test_type_integre_est_en_lecture_seule(onglet):
    t, _ = onglet
    t._afficher_integre("R")
    assert t._canvas_broches._lecture_seule is True


def test_deplacer_une_broche_rend_le_formulaire_sale(onglet):
    t, _ = onglet
    t._prefix_var.set("IC")
    t._brochage = [("1", "L", 0)]
    t._prendre_snapshot()
    t._brochage = [("1", "R", 0)]
    assert t._etat_courant() != t._etat_initial


def test_selecteur_de_forme_liste_les_composants_importes(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "AOP2": {"name": "AOP2", "pins": ["1"], "brochage": {"1": ["L", 0]},
                 "primitives": [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]},
        "SANS": {"name": "SansForme", "pins": ["1"], "brochage": {"1": ["L", 0]}},
    }), encoding="utf-8")
    t._load()
    assert any("AOP2" in cle for cle in t._formes_disponibles)
    assert not any("SANS" in cle for cle in t._formes_disponibles)


def test_choisir_une_forme_met_a_jour_l_apercu_sans_toucher_aux_broches(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "AOP2": {"name": "AOP2", "pins": ["1"], "brochage": {"1": ["L", 0]},
                 "primitives": [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]},
    }), encoding="utf-8")
    t._load()
    t._afficher_nouveau()
    t._brochage = [("X", "L", 0)]
    cle = next(c for c in t._formes_disponibles if "AOP2" in c)
    t._sur_forme(cle)
    assert t._forme_primitives == [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]
    assert t._brochage == [("X", "L", 0)]     # broches inchangees


def test_afficher_perso_montre_la_forme_de_l_import(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "AOP2": {"name": "AOP2", "pins": ["1"], "brochage": {"1": ["L", 0]},
                 "primitives": [["polygon", [[0, -10], [10, 10], [-10, 10]], False]],
                 "xml_source": "<DataItem>...</DataItem>"},
    }), encoding="utf-8")
    t._load()
    t._afficher_perso("AOP2")
    assert t._forme_primitives == [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]
    assert t._xml_source_valide is True


def test_resauver_sans_toucher_la_forme_preserve_primitives_et_xml_source(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "AOP2": {"name": "AOP2", "pins": ["1"], "brochage": {"1": ["L", 0]},
                 "primitives": [["polygon", [[0, -10], [10, 10], [-10, 10]], False]],
                 "xml_source": "<DataItem>ORIGINAL</DataItem>"},
    }), encoding="utf-8")
    t._load()
    t._afficher_perso("AOP2")
    t._sauvegarder()
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert data["AOP2"]["primitives"] == [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]
    assert data["AOP2"]["xml_source"] == "<DataItem>ORIGINAL</DataItem>"


def test_changer_de_forme_invalide_le_xml_source_a_la_sauvegarde(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "AOP2": {"name": "AOP2", "pins": ["1"], "brochage": {"1": ["L", 0]},
                 "primitives": [["polygon", [[0, -10], [10, 10], [-10, 10]], False]],
                 "xml_source": "<DataItem>ORIGINAL</DataItem>"},
        "SELF2": {"name": "Self2", "pins": ["2"], "brochage": {"2": ["R", 0]},
                  "primitives": [["line", [[0, -7], [0, 7]], 2]]},
    }), encoding="utf-8")
    t._load()
    t._afficher_perso("AOP2")
    cle = next(c for c in t._formes_disponibles if "SELF2" in c)
    t._sur_forme(cle)
    t._sauvegarder()
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert "xml_source" not in data["AOP2"]
    assert data["AOP2"]["primitives"] == [["line", [[0, -7], [0, 7]], 2]]


def test_nouveau_composant_avec_forme_choisie_a_primitives_mais_pas_xml_source(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "AOP2": {"name": "AOP2", "pins": ["1"], "brochage": {"1": ["L", 0]},
                 "primitives": [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]},
    }), encoding="utf-8")
    t._load()
    t._afficher_nouveau()
    t._prefix_var.set("NEUF")
    t._brochage = [("A", "L", 0), ("B", "R", 0)]
    cle = next(c for c in t._formes_disponibles if "AOP2" in c)
    t._sur_forme(cle)
    t._sauvegarder()
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert data["NEUF"]["primitives"] == [["polygon", [[0, -10], [10, 10], [-10, 10]], False]]
    assert "xml_source" not in data["NEUF"]


def test_resauver_un_compose_preserve_le_marqueur_compose(onglet):
    """Un compose (`<CComp>` de la CCLib du collegue) doit rester exclu de
    `ecrire_dans_dossier` apres re-sauvegarde -- perdre `compose` le ferait
    ecrire comme un `<DataItem>` normal, aplati mais convaincant (revue
    finale 2026-08-06)."""
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "PONT": {"name": "Pont", "pins": ["1", "2"],
                 "brochage": {"1": ["L", 0], "2": ["R", 0]},
                 "primitives": [["polygon", [[0, -10], [10, 10], [-10, 10]], False]],
                 "compose": True},
    }), encoding="utf-8")
    t._load()
    t._afficher_perso("PONT")
    assert t._compose_courant is True
    t._sauvegarder()
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert data["PONT"]["compose"] is True


def test_nouveau_composant_n_a_jamais_le_marqueur_compose(onglet):
    """Non-regression : un type flambant neuf (ou une duplication) n'est
    jamais un `<CComp>` original -- `compose` ne doit pas fuir dedans."""
    t, chemin = onglet
    chemin.write_text(json.dumps({
        "PONT": {"name": "Pont", "pins": ["1"], "brochage": {"1": ["L", 0]},
                 "compose": True},
    }), encoding="utf-8")
    t._load()
    t._afficher_perso("PONT")
    assert t._compose_courant is True
    t._afficher_nouveau()
    assert t._compose_courant is False
    t._prefix_var.set("NEUF")
    t._name_var.set("Neuf")
    t._brochage = [("A", "L", 0)]
    t._sauvegarder()
    data = json.loads(chemin.read_text(encoding="utf-8"))
    assert "compose" not in data["NEUF"]


def test_duplication_clone_le_brochage(onglet):
    t, _ = onglet
    t._brochage = [("VCC", "T", 0)]
    t._dupliquer()
    t._brochage[0] = ("GND", "B", 0)
    assert t._etat_initial[2][0][0] == "VCC"        # snapshot non altéré


def test_sauvegarde_refuse_un_type_sans_broche(onglet):
    t, chemin = onglet
    erreurs = t._boites.erreurs
    t._prefix_var.set("IC")
    t._name_var.set("Vide")
    t._brochage = []
    t._sauvegarder()
    assert erreurs and "broche" in erreurs[0].lower()
    assert not chemin.exists() or "IC" not in json.loads(
        chemin.read_text(encoding="utf-8"))


def test_saisie_rapide_voit_les_broches_dans_l_ordre(onglet, monkeypatch):
    """L'ordre du canevas doit ressortir tel quel côté saisie rapide."""
    t, chemin = onglet
    t._prefix_var.set("IC")
    t._name_var.set("Ampli")
    t._brochage = [("GND", "B", 0), ("VCC", "T", 0), ("IN", "L", 0)]
    t._sauvegarder()
    monkeypatch.setattr("circuit_analyzer.composant.chemin_bibliotheque",
                        lambda: chemin)
    from circuit_analyzer.saisie import ModeleSaisie
    assert ModeleSaisie()._broches_du_type("IC") == ["GND", "VCC", "IN"]


# ── Task 6 : modeles, valeur par defaut, taille, persistance ─────────────────

def test_sauvegarde_ecrit_les_nouvelles_cles(onglet):
    t, chemin = onglet
    t._prefix_var.set("IC")
    t._name_var.set("Ampli")
    t._default_var.set("LM358")
    t._auto_taille_var.set(False)
    t._w_var.set("120"); t._h_var.set("160")
    t._brochage = [("VCC", "T", 0), ("GND", "B", 0)]
    t._canvas_broches.charger(t._brochage, roles={"VCC": "Alim"})
    t._sauvegarder()
    d = json.loads(chemin.read_text(encoding="utf-8"))["IC"]
    assert d["default_value"] == "LM358"
    assert d["fonctions"] == {"VCC": "Alim"}
    assert d["boite"] == {"w": 120, "h": 160}


def test_taille_auto_n_ecrit_pas_la_cle_boite(onglet):
    t, chemin = onglet
    t._prefix_var.set("IC"); t._name_var.set("X")
    t._auto_taille_var.set(True)
    t._brochage = [("1", "L", 0)]
    t._sauvegarder()
    assert "boite" not in json.loads(chemin.read_text(encoding="utf-8"))["IC"]


def test_relecture_restitue_les_nouvelles_cles(onglet):
    t, chemin = onglet
    chemin.write_text(json.dumps({"IC": {
        "name": "Ampli", "pins": ["VCC"], "default_value": "LM358",
        "brochage": {"VCC": ["T", 0]}, "fonctions": {"VCC": "Alim"},
        "boite": {"w": 120, "h": 160}}}), encoding="utf-8")
    t._load(); t._afficher_perso("IC")
    assert t._default_var.get() == "LM358"
    assert t._canvas_broches.roles() == {"VCC": "Alim"}
    assert t._auto_taille_var.get() is False
    assert t._w_var.get() == "120"


def test_poser_modele_remplit_le_brochage(onglet):
    t, _ = onglet
    t._modele_var.set("DIP-8")
    t._poser_modele()
    assert [n for n, _c, _d in t._brochage] == [str(i) for i in range(1, 9)]


def test_auto_def_propage_valeur_role_et_taille():
    from gui.schematic_editor import _auto_def
    d = _auto_def("Ampli", ["VCC"], {"VCC": ["T", 0]},
                  default_value="LM358", fonctions={"VCC": "Alim"},
                  boite={"w": 200, "h": 240})
    assert d["default_value"] == "LM358"
    assert d["fonctions"] == {"VCC": "Alim"}
    assert d["w"] >= 200 and d["h"] >= 240


def test_envoyer_puis_recevoir_la_bibliotheque_partagee(onglet, tmp_path, monkeypatch):
    """Aller-retour complet par le DOSSIER partagé (format LibItem/Lib du C#) :
    nos composants partent en .xml, et une réception les relit à l'identique."""
    t, _chemin = onglet
    partage = tmp_path / "LibShared"
    partage.mkdir()
    monkeypatch.setattr("gui.tab_components.dossier_partage", lambda: str(partage))

    t._prefix_var.set("CAPT")
    t._name_var.set("Mon capteur")
    t._brochage = [("1", "L", -20), ("2", "R", 20), ("VCC", "T", 0)]
    t._sauvegarder()

    t._envoyer_biblio()
    assert (partage / "Mon capteur.xml").exists()

    # Réception : même nom -> mise à jour, jamais un doublon.
    avant = len(t._custom)
    t._recevoir_biblio()
    assert len(t._custom) == avant
    relu = next(e for e in t._custom.values() if e.get("name") == "Mon capteur")
    assert set(relu["pins"]) == {"1", "2", "VCC"}
    assert relu["brochage"]["VCC"] == ["T", 0]


def test_recevoir_n_ecrase_pas_les_composants_du_collegue(onglet, tmp_path, monkeypatch):
    """Envoyer ne doit JAMAIS supprimer les .xml déjà présents chez le collègue
    (le C#, lui, vide son dossier avant de réécrire — pas nous)."""
    t, _chemin = onglet
    partage = tmp_path / "LibShared"
    partage.mkdir()
    monkeypatch.setattr("gui.tab_components.dossier_partage", lambda: str(partage))
    temoin = partage / "Resistance.xml"
    temoin.write_text("<DataItem><Name>Resistance</Name></DataItem>", encoding="utf-8")

    t._prefix_var.set("CAPT")
    t._name_var.set("Mon capteur")
    t._brochage = [("1", "L", 0), ("2", "R", 0)]
    t._sauvegarder()
    t._envoyer_biblio()

    assert temoin.exists(), "le composant du collegue a ete supprime"


def test_recevoir_biblio_previent_la_palette_de_l_editeur(tmp_path, monkeypatch):
    """BUG TROUVÉ EN TESTANT (« quand je fais update componant la majorite sont
    affiches en symbole AOP, pas le vrai symbole ») : `_sauvegarder`, `_supprimer`
    et `_importer_eretro` appellent tous `on_save()` pour que l'éditeur de schéma
    reconstruise sa palette (`SchematicEditor._defs`, mis en cache) -- `_recevoir_biblio`
    (le bouton « Recevoir la bibliothèque partagée », le chemin réellement emprunté
    pour peupler la bibliothèque en masse) ne le faisait PAS : les types reçus
    restaient invisibles pour l'éditeur, qui retombait sur le rendu générique par
    type ('U' -> triangle AOP) au lieu du vrai contour importé."""
    chemin = tmp_path / "component_library.json"
    monkeypatch.setattr("gui.tab_components.chemin_bibliotheque", lambda: chemin)
    boites = _Boites()
    monkeypatch.setattr("gui.tab_components.messagebox", boites)
    from gui.tab_components import TabComponents
    try:
        root = ctk.CTk()
    except Exception:
        pytest.skip("pas de display Tk")
    root.withdraw()
    appels = []
    t = TabComponents(root, on_save=lambda: appels.append(1))
    root.update_idletasks()

    source = tmp_path / "LibShared"
    source.mkdir()
    (source / "MOSFET canal N.xml").write_text(
        '<DataItem><Name>MOSFET canal N</Name>'
        '<datasegment><DataSegment><Spoint><X>-40</X><Y>0</Y></Spoint>'
        '<Epoint><X>40</X><Y>0</Y></Epoint></DataSegment></datasegment>'
        '<datapin><DataPin><Pname>G</Pname><Pnumber>1</Pnumber>'
        '<Pin><X>-40</X><Y>0</Y></Pin></DataPin>'
        '<DataPin><Pname>D</Pname><Pnumber>2</Pnumber>'
        '<Pin><X>40</X><Y>0</Y></Pin></DataPin></datapin></DataItem>',
        encoding="utf-8")
    monkeypatch.setattr("gui.tab_components.dossier_partage", lambda: str(source))

    t._recevoir_biblio()
    root.destroy()

    assert appels, "on_save() jamais appelé après _recevoir_biblio -- palette de l'éditeur restée périmée"


def test_envoyer_ne_renvoie_pas_les_composes_recus(onglet, tmp_path, monkeypatch):
    """Un composé reçu de CCLib ne doit pas repartir aplati dans Lib : côté
    collègue ça ferait un DOUBLON dans la palette, et la version riche
    (DItemL/CCLine) serait remplacée par une boîte vide."""
    t, _chemin = onglet
    source = tmp_path / "LibItem" / "CCLib"
    source.mkdir(parents=True)
    (source / "Pont.xml").write_text(
        '<CComp><Name>Pont</Name><Group>PT</Group><datapin>'
        '<DataPin><Pname>1</Pname><Pin><X>-40</X><Y>0</Y></Pin></DataPin>'
        '<DataPin><Pname>2</Pname><Pin><X>40</X><Y>0</Y></Pin></DataPin>'
        '</datapin><DItemL /><CCLine /></CComp>', encoding="utf-8")
    monkeypatch.setattr("gui.tab_components.dossier_partage", lambda: str(source))
    t._recevoir_biblio()
    assert any(e.get("name") == "Pont" for e in t._custom.values())

    cible = tmp_path / "Sortie"
    cible.mkdir()
    monkeypatch.setattr("gui.tab_components.dossier_partage", lambda: str(cible))
    t._envoyer_biblio()
    assert not (cible / "Pont.xml").exists(), "compose renvoye aplati"


def test_pousser_symboles_orphelins_ecrit_les_formes_maison(onglet, tmp_path, monkeypatch):
    """Bouton « Pousser mes symboles orphelins » : ecrivain distinct de
    _envoyer_biblio, part de circuit_analyzer.xml._FORME_MAISON (nos formes
    integrees) plutot que de self._custom (composants personnalises)."""
    t, _chemin = onglet
    partage = tmp_path / "LibShared"
    partage.mkdir()
    monkeypatch.setattr("gui.tab_components.dossier_partage", lambda: str(partage))

    t._pousser_symboles_orphelins()

    assert (partage / "MOSFET.xml").exists()
    assert (partage / "Fusible.xml").exists()
    assert any("orphelin" in msg for msg in t._boites.infos)


def test_pousser_symboles_orphelins_n_ecrase_jamais_un_nom_deja_present(
        onglet, tmp_path, monkeypatch):
    t, _chemin = onglet
    partage = tmp_path / "LibShared"
    partage.mkdir()
    temoin = partage / "MOSFET.xml"
    temoin.write_text("<DataItem><Name>MOSFET</Name></DataItem>", encoding="utf-8")
    monkeypatch.setattr("gui.tab_components.dossier_partage", lambda: str(partage))

    t._pousser_symboles_orphelins()

    with open(temoin, encoding="utf-8") as f:
        assert f.read() == "<DataItem><Name>MOSFET</Name></DataItem>"


def test_pousser_symboles_orphelins_previent_si_rien_a_pousser(
        onglet, tmp_path, monkeypatch):
    """Sa bibliotheque a deja TOUS nos noms (simule via un dossier qui
    contient une copie de chacune de nos formes maison) : rien a ecrire."""
    t, _chemin = onglet
    from circuit_analyzer.xml import _FORME_MAISON
    partage = tmp_path / "LibShared"
    partage.mkdir()
    for nom in _FORME_MAISON:
        nom_fichier = "".join(c for c in nom if c.isalnum()) or "X"
        (partage / f"{nom_fichier}.xml").write_text(
            f"<DataItem><Name>{nom}</Name><datapin>"
            "<DataPin><Pname>1</Pname><Pin><X>0</X><Y>0</Y></Pin></DataPin>"
            "</datapin></DataItem>", encoding="utf-8")
    monkeypatch.setattr("gui.tab_components.dossier_partage", lambda: str(partage))

    t._pousser_symboles_orphelins()

    assert any("Aucun symbole orphelin" in msg for msg in t._boites.infos)
