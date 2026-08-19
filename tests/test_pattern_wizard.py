"""@file test_pattern_wizard.py
@brief PatternWizard : apercu schematique de l'etape 4, rejet des doublons
de nom (spec 2026-08-04). Tk -> skip sans display.
"""
import pytest

ctk = pytest.importorskip("customtkinter")

from custom_circuits.loader import CONDITION_KIND_LABELS  # noqa: E402


@pytest.fixture
def ctk_root():
    import tkinter as tk
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("pas d'affichage Tk disponible")
    root.withdraw()
    yield root
    root.destroy()


def _wizard(ctk_root, refs_info):
    """@brief Construit un PatternWizard avec des composants deja coches.

    @param refs_info dict {ref: {"type":..., "value":..., "pins": {...}}}
    """
    from gui.pattern_wizard import PatternWizard
    return PatternWizard(ctk_root, graph=None,
                         unclassified=list(refs_info), comp_info=refs_info)


def test_apercu_dessine_un_symbole_par_composant_selectionne(ctk_root):
    refs_info = {
        "R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N2"}},
        "C1": {"type": "C", "value": "100n", "pins": {"1": "N2", "2": "GND"}},
    }
    w = _wizard(ctk_root, refs_info)
    fig = w._dessiner_apercu()
    with_elements = [el for ax in fig.axes for el in ax.texts]
    textes = {t.get_text() for t in with_elements}
    assert "R1" in textes and "C1" in textes


def test_apercu_relie_deux_composants_qui_partagent_un_net(ctk_root):
    refs_info = {
        "R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N2"}},
        "C1": {"type": "C", "value": "100n", "pins": {"1": "N2", "2": "GND"}},
    }
    w = _wizard(ctk_root, refs_info)
    fig = w._dessiner_apercu()
    assert set(fig._apercu_connexions) == {("R1", "C1")}


def test_apercu_dessine_un_composant_isole_sans_fil(ctk_root):
    """Aucun net partage entre R1 et C1 -> composants dessines, aucun fil."""
    refs_info = {
        "R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N2"}},
        "C1": {"type": "C", "value": "100n", "pins": {"1": "N3", "2": "N4"}},
    }
    w = _wizard(ctk_root, refs_info)
    fig = w._dessiner_apercu()
    textes = {t.get_text() for ax in fig.axes for t in ax.texts}
    assert "R1" in textes and "C1" in textes
    assert fig._apercu_connexions == [], "aucun net partage : pas de fil attendu"


def test_libelle_aop_reconnu_par_ses_broches_semantiques():
    """BUG TROUVÉ EN TESTANT (« aop is still showing circuit integre ») : un AOP
    reste type 'U' (pas de lettre dédiée dans ce système), mais son libellé
    affiché doit se distinguer d'un IC générique quand ses broches sémantiques
    (IN+/IN-/OUT, posées par le plan `_NOM_VERS_TYPE['AOP']`) sont présentes."""
    from gui.pattern_wizard import _type_label
    assert _type_label("U", {"IN+": "N1", "IN-": "N2", "OUT": "N3"}) == \
        "Amplificateur opérationnel (AOP)"
    # Padding AOP standard (V+/V- en NC, cf. circuit_analyzer/xml.py) : toujours reconnu.
    assert _type_label("U", {"IN+": "N1", "IN-": "N2", "OUT": "N3",
                             "V+": "NC", "V-": "NC"}) == \
        "Amplificateur opérationnel (AOP)"


def test_libelle_ic_generique_reste_circuit_integre_sans_broches_aop():
    """Un IC quelconque (TL431, régulateur...) dont les broches ne sont PAS
    IN+/IN-/OUT garde le libellé générique -- ne pas sur-affirmer "AOP"."""
    from gui.pattern_wizard import _type_label
    assert _type_label("U", {"A": "N1", "K": "N2", "REF": "N3"}) == "Circuit intégré"
    assert _type_label("U", None) == "Circuit intégré"
    assert _type_label("U") == "Circuit intégré"


def test_apercu_sans_selection_ne_leve_pas(ctk_root):
    w = _wizard(ctk_root, {})
    fig = w._dessiner_apercu()
    assert fig is not None


def test_go_to_etape_4_affiche_l_apercu(ctk_root):
    """La navigation vers l'etape 4 declenche bien le rendu (pas seulement
    un appel manuel isole a _dessiner_apercu)."""
    refs_info = {"R1": {"type": "R", "value": "10k",
                        "pins": {"1": "N1", "2": "N2"}}}
    w = _wizard(ctk_root, refs_info)
    w._go_to(2)
    w._name_var.set("Mon pattern")
    w._go_to(4)
    assert w._apercu_canvas is not None


def test_doublon_de_nom_refuse_a_l_etape_2(ctk_root, monkeypatch, tmp_path):
    """Remplace test_doublon_pattern_refuse (testait TabCircuits, retire) :
    meme comportement reel, teste directement sur PatternWizard, le seul
    chemin de creation qui subsiste apres le retrait de l'onglet Circuits."""
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)
    loader.save_custom_circuits([{"name": "Mon montage", "components": ["R"],
                                  "conditions": []}])

    refs_info = {"R1": {"type": "R", "value": "10k",
                        "pins": {"1": "N1", "2": "N2"}}}
    w = _wizard(ctk_root, refs_info)
    w._go_to(2)
    w._name_var.set("Mon montage")
    assert w._validate_current() is False


def test_doublon_de_nom_avec_un_circuit_integre_refuse_a_l_etape_2(
        ctk_root, monkeypatch, tmp_path):
    """Fix 5-1 : la validation doit aussi rejeter un nom qui collide avec un
    circuit INTEGRE (NOMS_CIRCUITS), pas seulement avec les personnalises.
    Sinon circuit_viewer decide "personnalise" par NOM : un pattern nomme
    comme un circuit integre ferait apparaitre un bouton Supprimer sur ce
    circuit integre, qui supprimerait en realite l'entree personnalisee
    homonyme."""
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)
    loader.save_custom_circuits([])

    refs_info = {"R1": {"type": "R", "value": "10k",
                        "pins": {"1": "N1", "2": "N2"}}}
    w = _wizard(ctk_root, refs_info)
    w._go_to(2)
    w._name_var.set("Suiveur de tension (AOP)")
    assert w._validate_current() is False


def test_apercu_rend_diode_sans_lever(ctk_root):
    """Fumee : l'apercu ne doit pas lever pour un composant D et affiche bien
    sa reference. Le VRAI test de non-regression (le symbole rendu est
    elm.Diode, pas une resistance) vit dans test_impedance_schematic.py
    (test_style_symbole_diode_rend_elm_diode) : style_symbole() est la
    fonction partagee que le wizard appelle pour choisir la classe schemdraw,
    donc c'est la qu'on verifie la classe reellement retournee."""
    refs_info = {
        "D1": {"type": "D", "value": "1N4007", "pins": {"1": "N1", "2": "GND"}},
    }
    w = _wizard(ctk_root, refs_info)
    fig = w._dessiner_apercu()
    textes = {t.get_text() for ax in fig.axes for t in ax.texts}
    assert "D1" in textes, "La diode doit avoir sa reference affichee"


def test_apercu_trois_composants_sur_un_net_font_une_chaine_pas_clique(ctk_root):
    """Fix 2: Trois composants partageant un net ne doivent pas creer une
    clique (3 connexions : R1-C1, R1-R2, C1-R2) mais une chaine
    (2 connexions : R1-C1, C1-R2). Cela evite que les fils ne traversent
    les composants intermediaires."""
    refs_info = {
        "R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "GND"}},
        "C1": {"type": "C", "value": "100n", "pins": {"1": "N2", "2": "GND"}},
        "R2": {"type": "R", "value": "1k", "pins": {"1": "N3", "2": "GND"}},
    }
    w = _wizard(ctk_root, refs_info)
    fig = w._dessiner_apercu()
    # Verifier une chaine (2 connexions) pas une clique (3 connexions)
    connexions = fig._apercu_connexions
    # Doit avoir exactement 2 connexions (chaine) et non 3 (clique)
    assert len(connexions) == 2, \
        f"Expected chain (2 connections) but got {len(connexions)}: {connexions}"


# ── Builder de condition générique (étape 3) ────────────────────────────────
# BUG TROUVÉ EN TESTANT (« les conditions de reconnaissance sont vieilles, pas
# de possibilité d'en ajouter par l'utilisateur ») : couvre le CHEMIN GUI --
# le moteur générique lui-même est testé dans tests/test_custom_circuits.py.

def _refs_diode():
    return {"D1": {"type": "D", "value": "1N4148",
                   "pins": {"A": "N1", "K": "VCC"}}}


def test_builder_ajoute_une_condition_broche_vers_rail(ctk_root):
    w = _wizard(ctk_root, _refs_diode())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["broche_vers_rail"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("D")
    w._builder_param_vars["broche"].set("K")
    w._builder_param_vars["rail"].set("Alimentation")
    w._ajouter_condition_perso()

    assert len(w._conditions_perso) == 1
    assert w._conditions_perso[0] == {
        "kind": "broche_vers_rail", "type": "D", "categorie": None,
        "broche": "K", "rail": "alimentation"}
    assert w._conditions_perso[0] in w._selected_conditions()


def test_builder_broche_import_n_importe_laquelle_donne_broche_none(ctk_root):
    w = _wizard(ctk_root, _refs_diode())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["broche_vers_rail"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("D")
    w._builder_param_vars["broche"].set("(n'importe laquelle)")
    w._builder_param_vars["rail"].set("Masse")
    w._ajouter_condition_perso()
    assert w._conditions_perso[0]["broche"] is None


def test_builder_meme_type_deux_fois_refuse(ctk_root):
    refs_info = {
        "R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N2"}},
        "C1": {"type": "C", "value": "100n", "pins": {"1": "N2", "2": "GND"}},
    }
    w = _wizard(ctk_root, refs_info)
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["meme_noeud"])
    w._rebuild_builder_params()
    w._builder_param_vars["type1"].set("R")
    w._builder_param_vars["type2"].set("R")
    w._ajouter_condition_perso()
    assert w._conditions_perso == []
    assert "différents" in w._err_label.cget("text")


def test_builder_nombre_invalide_refuse(ctk_root):
    refs_info = {"R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N2"}}}
    w = _wizard(ctk_root, refs_info)
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["au_moins_n"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("R")
    w._builder_param_vars["n"].set("pas un nombre")
    w._ajouter_condition_perso()
    assert w._conditions_perso == []


def test_builder_supprimer_une_condition_ajoutee(ctk_root):
    w = _wizard(ctk_root, _refs_diode())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["au_moins_n"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("D")
    w._builder_param_vars["n"].set("1")
    w._ajouter_condition_perso()
    assert len(w._conditions_perso) == 1

    w._supprimer_condition_perso(w._conditions_perso[0])
    assert w._conditions_perso == []


def test_builder_refuse_un_doublon_exact(ctk_root):
    w = _wizard(ctk_root, _refs_diode())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["au_moins_n"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("D")
    w._builder_param_vars["n"].set("1")
    w._ajouter_condition_perso()
    w._ajouter_condition_perso()
    assert len(w._conditions_perso) == 1


def test_condition_perso_survit_a_la_creation_du_pattern(ctk_root, monkeypatch, tmp_path):
    """Bout-en-bout : une condition ajoutée via le builder se retrouve bien
    dans le fichier custom_circuits.json après « Créer le pattern »."""
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)
    loader.save_custom_circuits([])

    w = _wizard(ctk_root, _refs_diode())
    w._comp_vars["D1"].set(True)
    w._go_to(2)
    w._name_var.set("Diode vers alim perso")
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["broche_vers_rail"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("D")
    w._builder_param_vars["broche"].set("K")
    w._builder_param_vars["rail"].set("Alimentation")
    w._ajouter_condition_perso()
    w._go_to(4)
    w._create_pattern()

    sauve = loader.load_custom_circuits(chemin)
    assert len(sauve) == 1
    assert sauve[0]["conditions"] == [
        {"kind": "broche_vers_rail", "type": "D", "categorie": None,
         "broche": "K", "rail": "alimentation"}]


# ── Verrouillage de categorie (AOP + photorésistance) ───────────────────────
# BUG TROUVÉ EN TESTANT (« AOP + photorésistance -> U + R, indiscernable de
# n'importe quel autre montage U+R, il faut pouvoir généraliser »).

def _refs_aop_photoresistance():
    return {
        "U1": {"type": "U", "value": "", "categorie": "AOP",
               "pins": {"IN+": "N1", "IN-": "N2", "OUT": "N3"}},
        "R1": {"type": "R", "value": "", "categorie": "Photorésistance",
               "pins": {"1": "N1", "2": "GND"}},
    }


def test_case_exiger_precisement_apparait_pour_un_composant_nomme(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    assert "R1" in w._verrouiller_categorie_vars
    assert "U1" in w._verrouiller_categorie_vars
    # Décochée par défaut : comportement inchangé tant qu'on ne l'active pas.
    assert w._verrouiller_categorie_vars["R1"].get() is False


def test_composants_requis_sans_verrou_reste_le_type_seul(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._comp_vars["U1"].set(True)
    w._comp_vars["R1"].set(True)
    requis = w._composants_requis()
    assert set(requis) == {"U", "R"}


def test_composants_requis_avec_verrou_devient_type_plus_categorie(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._comp_vars["U1"].set(True)
    w._comp_vars["R1"].set(True)
    w._verrouiller_categorie_vars["R1"].set(True)
    requis = w._composants_requis()
    assert "U" in requis
    assert {"type": "R", "categorie": "Photorésistance"} in requis
    assert "R" not in requis, "le R generique ne doit plus etre present, seul le verrouille"


def test_champ_categorie_pre_rempli_et_editable(ctk_root):
    """BUG TROUVÉ EN TESTANT (« ma photorésistance est lue comme R-résistance,
    je ne peux pas le voir/changer ») : le nom réel est pré-rempli (visible),
    ET modifiable -- pas un simple libellé figé."""
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    assert w._categorie_vars["R1"].get() == "Photorésistance"

    w._comp_vars["U1"].set(True)
    w._comp_vars["R1"].set(True)
    w._verrouiller_categorie_vars["R1"].set(True)
    w._categorie_vars["R1"].set("LDR (capteur lumière)")
    requis = w._composants_requis()
    assert {"type": "R", "categorie": "LDR (capteur lumière)"} in requis


def test_champ_categorie_utile_meme_sans_detection_automatique(ctk_root):
    """Un composant SANS nom réel détecté (categorie vide, ex. resté "X") peut
    quand même recevoir un nom tapé à la main par l'utilisateur."""
    refs_info = {"R1": {"type": "R", "value": "", "categorie": "",
                        "pins": {"1": "N1", "2": "N2"}}}
    w = _wizard(ctk_root, refs_info)
    assert w._categorie_vars["R1"].get() == ""

    w._comp_vars["R1"].set(True)
    w._verrouiller_categorie_vars["R1"].set(True)
    w._categorie_vars["R1"].set("Photorésistance")
    requis = w._composants_requis()
    assert {"type": "R", "categorie": "Photorésistance"} in requis


def test_case_cochee_mais_champ_vide_retombe_sur_le_type_seul(ctk_root):
    """Cocher la case puis vider le champ ne doit PAS produire une categorie
    vide silencieuse -- repli sur le type seul, comme si la case était
    décochée."""
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._comp_vars["U1"].set(False)
    w._comp_vars["R1"].set(True)
    w._verrouiller_categorie_vars["R1"].set(True)
    w._categorie_vars["R1"].set("   ")
    requis = w._composants_requis()
    assert requis == ["R"]


def test_pattern_verrouille_matche_photoresistance_pas_resistance_ordinaire(
        ctk_root, monkeypatch, tmp_path):
    """Bout-en-bout complet : le pattern créé avec le verrou coché matche une
    vraie photorésistance et PAS une résistance ordinaire du même type."""
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)
    loader.save_custom_circuits([])

    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._comp_vars["U1"].set(True)
    w._comp_vars["R1"].set(True)
    w._verrouiller_categorie_vars["R1"].set(True)
    w._go_to(2)
    w._name_var.set("Capteur lumiere AOP")
    w._go_to(4)
    w._create_pattern()

    from circuit_analyzer.graph_builder import build_graph
    from circuit_analyzer.parser import Component
    pattern = loader.get_custom_patterns(chemin)[0]

    comps_photo = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2'}),
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, ''),
    ]
    comps_photo[1].categorie = 'Photorésistance'
    assert len(pattern.match(build_graph(comps_photo))) == 1

    comps_ordinaire = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'N1', 'OUT': 'N2'}),
        Component('R1', 'R', {'1': 'N1', '2': 'N2'}, '10k'),
    ]
    comps_ordinaire[1].categorie = 'Résistance'
    assert pattern.match(build_graph(comps_ordinaire)) == [], \
        "une resistance ordinaire ne doit pas satisfaire le pattern verrouille"


def test_condition_builder_offre_le_nom_precis_optionnel(ctk_root):
    """Le builder de condition propose aussi un filtre par nom précis
    (categorie), pas seulement le type électrique."""
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["au_moins_n"])
    w._rebuild_builder_params()
    assert "categorie" in w._builder_param_vars
    w._builder_param_vars["type"].set("R")
    w._builder_param_vars["categorie"].set("Photorésistance")
    w._builder_param_vars["n"].set("1")
    w._ajouter_condition_perso()
    assert w._conditions_perso[0]["categorie"] == "Photorésistance"


# ── Type 'X' (non classifié) sélectionnable dans le builder de condition ────
# BUG TROUVÉ EN TESTANT (« je ne peux pas choisir qui je veux dans nom précis,
# je ne peux pas voir la photorésistance ») : une photorésistance réelle,
# jamais reconnue par le catalogue électrique, reste de type 'X' -- exclu du
# menu "Type :" du builder de condition, donc son "nom précis" n'était jamais
# atteignable, alors que l'étape 1 (case « exiger précisément ») le proposait
# déjà très bien pour ce même type.

def _refs_aop_photoresistance_x():
    """Comme _refs_aop_photoresistance, mais R1 est du VRAI type 'X' (non
    classifié) -- le cas réel d'une photorésistance, qui n'a pas de forme
    dédiée dans le catalogue électrique."""
    return {
        "U1": {"type": "U", "value": "", "categorie": "AOP",
               "pins": {"IN+": "N1", "IN-": "N2", "OUT": "N3"}},
        "X1": {"type": "X", "value": "", "categorie": "Photoresistance",
               "pins": {"1": "N1", "2": "GND"}},
    }


def test_types_disponibles_inclut_x_non_classifie(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance_x())
    assert "X" in w._types_disponibles()


def test_condition_builder_offre_le_nom_precis_dune_photoresistance_type_x(ctk_root):
    """Sélectionner le type 'X' dans le builder doit rendre "Photoresistance"
    choisissable comme nom précis -- pas juste visible à l'étape 1."""
    w = _wizard(ctk_root, _refs_aop_photoresistance_x())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["au_moins_n"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("X")
    assert "Photoresistance" in w._categories_pour_type("X")
    w._builder_param_vars["categorie"].set("Photoresistance")
    w._builder_param_vars["n"].set("1")
    w._ajouter_condition_perso()
    assert w._conditions_perso[0] == {
        "kind": "au_moins_n", "type": "X", "categorie": "Photoresistance", "n": 1,
        "comparateur": ">="}


# ── connexion_broches (choisir les broches et leur connexion, y compris
# entre deux broches du même composant) ─────────────────────────────────────
# BUG TROUVÉ EN TESTANT (demande utilisateur : « ajouter une condition où on
# choisit les broches d'un composant et leur connexion, y compris entre deux
# broches du MÊME composant -- il faut les deux cas »). Couvre le chemin GUI ;
# le moteur générique ("connexion_broches") est testé dans
# tests/test_custom_circuits.py.

def test_builder_connexion_broches_deux_composants_differents(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["connexion_broches"])
    w._rebuild_builder_params()

    w._builder_param_vars["type_a"].set("R")
    w._builder_broches_a["_any"].set(False)
    w._builder_broches_a["1"].set(True)

    w._builder_param_vars["type_b"].set("U")
    w._builder_broches_b["_any"].set(False)
    w._builder_broches_b["IN-"].set(True)

    w._ajouter_condition_perso()

    assert len(w._conditions_perso) == 1
    assert w._conditions_perso[0] == {
        "kind": "connexion_broches",
        "cote_a": {"type": "R", "categorie": None, "broches": ["1"]},
        "cote_b": {"type": "U", "categorie": None, "broches": ["IN-"]},
    }
    assert w._conditions_perso[0] in w._selected_conditions()


def test_builder_connexion_broches_n_importe_laquelle_par_defaut(ctk_root):
    """Sans toucher aux cases, les deux côtés restent "n'importe laquelle"
    (broches=[]) -- comportement par défaut, le plus permissif."""
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["connexion_broches"])
    w._rebuild_builder_params()
    w._ajouter_condition_perso()

    cond = w._conditions_perso[0]
    assert cond["cote_a"]["broches"] == []
    assert cond["cote_b"]["broches"] == []


def test_builder_connexion_broches_meme_composant(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["connexion_broches"])
    w._rebuild_builder_params()

    w._builder_param_vars["type_a"].set("U")
    w._builder_meme_composant_var.set(True)
    # Après bascule, le sélecteur côté B propose les broches du côté A (même
    # composant) -- ici IN+/IN-/OUT, pas les broches d'un "type_b" quelconque.
    assert set(w._builder_broches_b) >= {"IN+", "IN-", "OUT"}

    w._builder_broches_a["_any"].set(False)
    w._builder_broches_a["IN-"].set(True)
    w._builder_broches_b["_any"].set(False)
    w._builder_broches_b["OUT"].set(True)
    w._ajouter_condition_perso()

    assert w._conditions_perso[0] == {
        "kind": "connexion_broches",
        "cote_a": {"type": "U", "categorie": None, "broches": ["IN-"]},
        "cote_b": {"meme_composant": True, "broches": ["OUT"]},
    }


def test_builder_connexion_broches_ensemble_de_broches_ou(ctk_root):
    """Cocher plusieurs broches du même côté = un ensemble OR."""
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["connexion_broches"])
    w._rebuild_builder_params()

    w._builder_param_vars["type_a"].set("U")
    w._builder_broches_a["_any"].set(False)
    w._builder_broches_a["IN+"].set(True)
    w._builder_broches_a["IN-"].set(True)
    w._ajouter_condition_perso()

    assert sorted(w._conditions_perso[0]["cote_a"]["broches"]) == ["IN+", "IN-"]


def test_builder_connexion_broches_avec_categorie(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["connexion_broches"])
    w._rebuild_builder_params()

    w._builder_param_vars["type_a"].set("R")
    w._builder_param_vars["categorie_a"].set("Photorésistance")
    w._ajouter_condition_perso()

    assert w._conditions_perso[0]["cote_a"]["categorie"] == "Photorésistance"


def test_condition_connexion_broches_survit_a_la_creation_du_pattern(
        ctk_root, monkeypatch, tmp_path):
    """Bout-en-bout : une condition connexion_broches ajoutée via le builder
    se retrouve bien dans le fichier custom_circuits.json."""
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)
    loader.save_custom_circuits([])

    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._comp_vars["U1"].set(True)
    w._comp_vars["R1"].set(True)
    w._go_to(2)
    w._name_var.set("AOP relié à sa sortie")
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["connexion_broches"])
    w._rebuild_builder_params()
    w._builder_param_vars["type_a"].set("U")
    w._builder_meme_composant_var.set(True)
    w._builder_broches_a["_any"].set(False)
    w._builder_broches_a["IN-"].set(True)
    w._builder_broches_b["_any"].set(False)
    w._builder_broches_b["OUT"].set(True)
    w._ajouter_condition_perso()
    w._go_to(4)
    w._create_pattern()

    sauve = loader.load_custom_circuits(chemin)
    assert len(sauve) == 1
    assert sauve[0]["conditions"] == [{
        "kind": "connexion_broches",
        "cote_a": {"type": "U", "categorie": None, "broches": ["IN-"]},
        "cote_b": {"meme_composant": True, "broches": ["OUT"]},
    }]


# ── Lot "we are very limited, add all the possible pattern of a schema"
# (demande utilisateur 2026-08-18) : comparateur sur au_moins_n, en_parallele,
# broche_non_connectee, valeur_compare, meme_valeur, nombre_broches. Couvre le
# chemin GUI ; le moteur générique est testé dans tests/test_custom_circuits.py.

def test_builder_au_moins_n_comparateur_par_defaut_au_moins(ctk_root):
    w = _wizard(ctk_root, _refs_diode())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["au_moins_n"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("D")
    w._builder_param_vars["n"].set("2")
    w._ajouter_condition_perso()
    assert w._conditions_perso[0]["comparateur"] == ">="


def test_builder_au_moins_n_comparateur_exactement(ctk_root):
    from gui.pattern_wizard import _COMPARATEUR_LABEL_VERS_CLE
    w = _wizard(ctk_root, _refs_diode())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["au_moins_n"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("D")
    label_egal = next(l for l, c in _COMPARATEUR_LABEL_VERS_CLE.items() if c == "==")
    w._builder_param_vars["comparateur_txt"].set(label_egal)
    w._builder_param_vars["n"].set("3")
    w._ajouter_condition_perso()
    assert w._conditions_perso[0] == {
        "kind": "au_moins_n", "type": "D", "categorie": None, "n": 3, "comparateur": "=="}


def test_builder_en_parallele_meme_type_deux_fois_autorise(ctk_root):
    """Contrairement à meme_noeud, en_parallele autorise le même type des deux
    côtés (cas le plus courant : deux R en parallèle)."""
    refs_info = {"R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N2"}}}
    w = _wizard(ctk_root, refs_info)
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["en_parallele"])
    w._rebuild_builder_params()
    w._builder_param_vars["type1"].set("R")
    w._builder_param_vars["type2"].set("R")
    w._ajouter_condition_perso()
    assert w._conditions_perso[0] == {
        "kind": "en_parallele", "types": ["R", "R"], "categories": [None, None]}


def test_builder_broche_non_connectee_ajoute_une_condition(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["broche_non_connectee"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("U")
    w._builder_param_vars["broche"].set("IN+")
    w._ajouter_condition_perso()
    assert w._conditions_perso[0] == {
        "kind": "broche_non_connectee", "type": "U", "categorie": None, "broche": "IN+"}


def test_builder_valeur_compare_parse_le_seuil(ctk_root):
    from gui.pattern_wizard import _COMPARATEUR_LABEL_VERS_CLE
    w = _wizard(ctk_root, _refs_diode())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["valeur_compare"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("D")
    label_sup = next(l for l, c in _COMPARATEUR_LABEL_VERS_CLE.items() if c == ">")
    w._builder_param_vars["comparateur_txt"].set(label_sup)
    w._builder_param_vars["seuil_txt"].set("10k")
    w._ajouter_condition_perso()
    assert w._conditions_perso[0] == {
        "kind": "valeur_compare", "type": "D", "categorie": None,
        "comparateur": ">", "seuil": 10000.0}


def test_builder_valeur_compare_seuil_illisible_refuse(ctk_root):
    w = _wizard(ctk_root, _refs_diode())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["valeur_compare"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("D")
    w._builder_param_vars["seuil_txt"].set("pas une valeur")
    w._ajouter_condition_perso()
    assert w._conditions_perso == []
    assert "illisible" in w._err_label.cget("text")


def test_builder_meme_valeur_ajoute_une_condition(ctk_root):
    refs_info = {
        "R1": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N2"}},
        "R2": {"type": "R", "value": "10k", "pins": {"1": "N1", "2": "N3"}},
    }
    w = _wizard(ctk_root, refs_info)
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["meme_valeur"])
    w._rebuild_builder_params()
    w._builder_param_vars["type1"].set("R")
    w._builder_param_vars["type2"].set("R")
    w._ajouter_condition_perso()
    assert w._conditions_perso[0] == {
        "kind": "meme_valeur", "types": ["R", "R"], "categories": [None, None]}


def test_builder_nombre_broches_ajoute_une_condition(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["nombre_broches"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("U")
    w._builder_param_vars["n"].set("3")
    w._ajouter_condition_perso()
    assert w._conditions_perso[0] == {
        "kind": "nombre_broches", "type": "U", "categorie": None,
        "comparateur": ">=", "n": 3}


def test_nouveaux_kinds_apparaissent_dans_le_menu_du_builder(ctk_root):
    w = _wizard(ctk_root, _refs_diode())
    w._go_to(3)
    for cle in ("en_parallele", "broche_non_connectee", "valeur_compare",
               "meme_valeur", "nombre_broches"):
        w._builder_kind_var.set(CONDITION_KIND_LABELS[cle])
        w._rebuild_builder_params()  # ne doit pas lever


# ── connexion_broches : "sens" (jamais connectée) et "mode" (toutes les
# broches) -- demande utilisateur 2026-08-18 : « add more costomation ...
# choose like 1 to a lot of pins or this one should never be connected ».

def test_builder_connexion_broches_sens_par_defaut_omis_du_dict(ctk_root):
    """Comportement par défaut ("doit être connectée") -- pas de clé "sens"
    dans le JSON produit, exactement comme avant cet ajout (rétro-compat)."""
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["connexion_broches"])
    w._rebuild_builder_params()
    w._builder_param_vars["type_a"].set("R")
    w._builder_param_vars["type_b"].set("U")
    w._ajouter_condition_perso()
    assert "sens" not in w._conditions_perso[0]


def test_builder_connexion_broches_sens_jamais_ajoute_la_cle(ctk_root):
    from gui.pattern_wizard import _SENS_LABEL_VERS_CLE
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["connexion_broches"])
    w._rebuild_builder_params()
    w._builder_param_vars["type_a"].set("R")
    w._builder_param_vars["type_b"].set("U")
    label_jamais = next(l for l, c in _SENS_LABEL_VERS_CLE.items()
                        if c == "jamais_connectee")
    w._builder_param_vars["sens_txt"].set(label_jamais)
    w._ajouter_condition_perso()
    assert w._conditions_perso[0]["sens"] == "jamais_connectee"


def test_builder_connexion_broches_mode_toutes_ajoute_la_cle(ctk_root):
    from gui.pattern_wizard import _MODE_BROCHES_LABEL_VERS_CLE
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["connexion_broches"])
    w._rebuild_builder_params()
    w._builder_param_vars["type_a"].set("U")
    w._builder_broches_a["_any"].set(False)
    w._builder_broches_a["IN+"].set(True)
    w._builder_broches_a["IN-"].set(True)
    label_toutes = next(l for l, c in _MODE_BROCHES_LABEL_VERS_CLE.items()
                        if c == "toutes")
    w._builder_param_vars["mode_a_txt"].set(label_toutes)
    w._builder_param_vars["type_b"].set("R")
    w._ajouter_condition_perso()
    assert w._conditions_perso[0]["cote_a"]["mode"] == "toutes"
    assert sorted(w._conditions_perso[0]["cote_a"]["broches"]) == ["IN+", "IN-"]


def test_builder_connexion_broches_mode_par_defaut_omis_du_dict(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["connexion_broches"])
    w._rebuild_builder_params()
    w._builder_param_vars["type_a"].set("R")
    w._builder_param_vars["type_b"].set("U")
    w._ajouter_condition_perso()
    assert "mode" not in w._conditions_perso[0]["cote_a"]


def test_condition_connexion_broches_sens_et_mode_survivent_a_la_creation(
        ctk_root, monkeypatch, tmp_path):
    from gui.pattern_wizard import _SENS_LABEL_VERS_CLE
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)
    loader.save_custom_circuits([])

    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._comp_vars["U1"].set(True)
    w._comp_vars["R1"].set(True)
    w._go_to(2)
    w._name_var.set("AOP jamais relie a R")
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["connexion_broches"])
    w._rebuild_builder_params()
    w._builder_param_vars["type_a"].set("U")
    w._builder_broches_a["_any"].set(False)
    w._builder_broches_a["IN-"].set(True)
    label_jamais = next(l for l, c in _SENS_LABEL_VERS_CLE.items()
                        if c == "jamais_connectee")
    w._builder_param_vars["sens_txt"].set(label_jamais)
    w._builder_param_vars["type_b"].set("R")
    w._ajouter_condition_perso()
    w._go_to(4)
    w._create_pattern()

    sauve = loader.load_custom_circuits(chemin)
    assert len(sauve) == 1
    assert sauve[0]["conditions"][0]["sens"] == "jamais_connectee"


# ── Étape 4 : le résumé final doit lister CHAQUE condition en clair, pas
# seulement un compte -- demande utilisateur 2026-08-19 : « the verification
# etape the last one before confirmation ... need to be exactly precise on
# what condition u did ». BUG TROUVÉ EN TESTANT : `_summary_label` à l'étape 4
# ne montrait qu'un compte ("avec 1 condition(s)"), jamais le texte des
# conditions elles-mêmes -- le détail lisible par condition n'existait qu'à
# l'étape 3, sous « Options avancées », repliée par défaut. Un utilisateur
# validant depuis l'étape 4 (la dernière avant sauvegarde) ne voyait donc
# jamais ce que chaque condition signifie concrètement.

def test_etape_4_resume_liste_chaque_condition_en_clair(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["connexion_broches"])
    w._rebuild_builder_params()
    w._builder_param_vars["type_a"].set("U")
    w._builder_broches_a["_any"].set(False)
    w._builder_broches_a["IN-"].set(True)
    from gui.pattern_wizard import _SENS_LABEL_VERS_CLE
    label_jamais = next(l for l, c in _SENS_LABEL_VERS_CLE.items()
                        if c == "jamais_connectee")
    w._builder_param_vars["sens_txt"].set(label_jamais)
    w._builder_param_vars["type_b"].set("R")
    w._ajouter_condition_perso()
    w._go_to(4)

    texte = w._summary_label.cget("text")
    from custom_circuits.loader import condition_display
    assert condition_display(w._conditions_perso[0]) in texte
    assert "JAMAIS" in texte


def test_etape_4_resume_sans_condition_le_dit_explicitement(ctk_root):
    w = _wizard(ctk_root, _refs_diode())
    w._comp_vars["D1"].set(True)
    w._go_to(4)
    texte = w._summary_label.cget("text")
    assert "Aucune condition" in texte


def test_etape_4_resume_ne_montre_plus_seulement_un_compte(ctk_root):
    """[MODIF 2026-08-19] Non-régression du bug initial : l'ancien texte
    "avec N condition(s)" (sans détail) ne doit plus apparaître seul --
    chaque condition ajoutée doit être nommément listée."""
    w = _wizard(ctk_root, _refs_diode())
    w._go_to(3)
    w._builder_kind_var.set(CONDITION_KIND_LABELS["broche_vers_rail"])
    w._rebuild_builder_params()
    w._builder_param_vars["type"].set("D")
    w._builder_param_vars["broche"].set("K")
    w._builder_param_vars["rail"].set("Alimentation")
    w._ajouter_condition_perso()
    w._go_to(4)
    texte = w._summary_label.cget("text")
    assert "condition(s)." not in texte
    assert "Conditions exigées :" in texte


# ── « Composition exacte » (demande utilisateur 2026-08-19, repro exacte via
# test4.xml : pattern « 1 AOP + 1 photorésistance » matche quand même un îlot
# avec 2 ampoules en plus -- « there is no this option ») : case à cocher
# pattern-globale, décochée par défaut. Moteur testé dans test_custom_circuits.py.

def test_composition_exacte_decochee_par_defaut_absente_du_dict(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._comp_vars["U1"].set(True)
    w._go_to(2)
    w._name_var.set("Test")
    d = w._build_pattern_dict()
    assert "composition_exacte" not in d


def test_composition_exacte_cochee_ajoute_la_cle(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._comp_vars["U1"].set(True)
    w._go_to(2)
    w._name_var.set("Test")
    w._composition_exacte_var.set(True)
    d = w._build_pattern_dict()
    assert d["composition_exacte"] is True


def test_composition_exacte_survit_a_la_creation_du_pattern(
        ctk_root, monkeypatch, tmp_path):
    """Bout-en-bout : la case cochée à l'étape 1 se retrouve bien dans le
    fichier custom_circuits.json une fois le pattern créé."""
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)
    loader.save_custom_circuits([])

    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._comp_vars["U1"].set(True)
    w._comp_vars["R1"].set(True)
    w._composition_exacte_var.set(True)
    w._go_to(2)
    w._name_var.set("Composition stricte")
    w._go_to(4)
    w._create_pattern()

    sauve = loader.load_custom_circuits(chemin)
    assert len(sauve) == 1
    assert sauve[0]["composition_exacte"] is True


def test_composition_exacte_non_cochee_absente_du_pattern_sauve(
        ctk_root, monkeypatch, tmp_path):
    """Regression guard : par défaut (case non cochée), aucune clé
    "composition_exacte" n'est écrite -- comportement historique inchangé."""
    chemin = tmp_path / "custom_circuits.json"
    from custom_circuits import loader
    monkeypatch.setattr(loader, "chemin_custom_circuits", lambda: chemin)
    loader.save_custom_circuits([])

    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._comp_vars["U1"].set(True)
    w._comp_vars["R1"].set(True)
    w._go_to(2)
    w._name_var.set("Composition libre")
    w._go_to(4)
    w._create_pattern()

    sauve = loader.load_custom_circuits(chemin)
    assert len(sauve) == 1
    assert "composition_exacte" not in sauve[0]


def test_composition_exacte_cochee_change_le_texte_du_resume_etape4(ctk_root):
    w = _wizard(ctk_root, _refs_aop_photoresistance())
    w._comp_vars["U1"].set(True)
    w._composition_exacte_var.set(True)
    w._go_to(2)
    w._name_var.set("Test")
    w._go_to(4)
    texte = w._summary_label.cget("text")
    assert "EXACTEMENT" in texte and "aucun autre composant" in texte
