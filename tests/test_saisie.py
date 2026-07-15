"""@file test_saisie.py
@brief Modèle pur de l'onglet Saisie (spec 2026-07-15 §3.2) : refs auto,
catalogue, validation, nets connus, round-trip XML, pureté d'import.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from circuit_analyzer.saisie import RAILS, LigneSaisie, ModeleSaisie
from circuit_analyzer.xml import generer_xml, lire_xml


def test_ref_auto_par_prefixe_de_type():
    m = ModeleSaisie()
    assert m.ajouter("R").ref == "R1"
    assert m.ajouter("R").ref == "R2"
    assert m.ajouter("C").ref == "C1"
    u = m.ajouter("U")
    assert u.ref == "U1"
    m.supprimer(m.lignes.index(u))
    assert m.ajouter("U").ref == "U1"   # index libéré réutilisé


def test_ajouter_pre_remplit_la_valeur_par_defaut_du_type():
    m = ModeleSaisie()
    assert m.ajouter("R").value == "10k"
    assert m.ajouter("C").value == "100n"
    assert m.ajouter("R", value="4.7k").value == "4.7k"   # explicite prioritaire


def test_ajouter_expose_les_broches_du_type():
    m = ModeleSaisie()
    q = m.ajouter("Q")
    assert list(q.pins) == ["B", "C", "E"]
    d = m.ajouter("D")
    assert list(d.pins) == ["A", "K"]


def test_ajouter_catalogue_ne555_et_led():
    m = ModeleSaisie()
    u = m.ajouter_catalogue("U", "NE555")
    assert u.value == "NE555"
    assert list(u.pins) == [str(i) for i in range(1, 9)]
    assert u.fonctions["2"] == "TRIG" and u.fonctions["3"] == "OUT"
    led = m.ajouter_catalogue("D", "LED rouge")
    assert led.value == "LED rouge" and list(led.pins) == ["A", "K"]


def test_changer_type_remplace_les_broches_et_garde_ref_et_value():
    m = ModeleSaisie()
    ligne = m.ajouter("R", value="10k")
    ligne.pins["1"] = "VIN"
    ref_avant = ligne.ref
    m.changer_type(0, "Q")
    assert m.lignes[0] is ligne
    assert ligne.ref == ref_avant          # ref conservée
    assert ligne.type == "Q"
    assert ligne.value == "10k"            # value conservée
    assert list(ligne.pins) == ["B", "C", "E"]
    assert all(v == "" for v in ligne.pins.values())  # anciens nets perdus
    assert ligne.fonctions == {}


def test_valider_bloquants_et_avertissements():
    m = ModeleSaisie()
    r1 = m.ajouter("R"); r1.pins["1"] = "VIN"; r1.pins["2"] = "NET1"
    r2 = m.ajouter("R"); r2.pins["1"] = "NET1"; r2.pins["2"] = "GND"
    bloquants, avert = m.valider()
    assert not bloquants and not avert
    r2.ref = "R1"                       # doublon
    bloquants, _ = m.valider()
    assert any("R1" in b for b in bloquants)
    r2.ref = "R2"
    r2.pins["2"] = "NSEUL"              # singleton
    _, avert = m.valider()
    assert any("NSEUL" in a for a in avert)


def test_nets_connus_rails_d_abord_sans_doublons():
    m = ModeleSaisie()
    r = m.ajouter("R"); r.pins["1"] = "VIN"; r.pins["2"] = "NETB"
    c = m.ajouter("C"); c.pins["1"] = "NETB"; c.pins["2"] = "NETA"
    nets = m.nets_connus()
    assert nets[:4] == list(RAILS)
    assert nets[4:] == ["NETA", "NETB"]


def test_round_trip_xml_complet():
    # Circuit mixte : R câblée, Q, U catalogue, broche VIDE (spec §3.2).
    m = ModeleSaisie()
    r = m.ajouter("R", value="10k"); r.pins["1"] = "VIN"; r.pins["2"] = "NB"
    q = m.ajouter("Q", value="2N2222")
    q.pins["B"] = "NB"; q.pins["C"] = "VCC"; q.pins["E"] = "GND"
    u = m.ajouter_catalogue("U", "NE555")
    u.pins["1"] = "GND"; u.pins["8"] = "VCC"; u.pins["3"] = "NOUT"
    r2 = m.ajouter("R", value="1k"); r2.pins["1"] = "NOUT"; r2.pins["2"] = "GND"
    with tempfile.TemporaryDirectory() as tmp:
        chemin = str(Path(tmp) / "essai.xml")
        Path(chemin).write_text(generer_xml(m.vers_composants()),
                                encoding="utf-8")
        relu = ModeleSaisie.depuis_composants(
            lire_xml(chemin, alias_catalogue=False))
    par_ref = {l.ref: l for l in relu.lignes}
    assert set(par_ref) == {"R1", "Q1", "U1", "R2"}
    assert par_ref["R1"].value == "10k"
    # Nets nommés (NB, NOUT) : convertis en NodeL internes lors de generer_xml,
    # relus comme NET# auto lors de lire_xml (comportement writer : les NodeL
    # internes ne preservent pas les noms). Vérifie juste que les broches
    # partageant le même net avant conservent cette relation après round-trip.
    assert par_ref["R1"].pins["2"] == par_ref["Q1"].pins["B"]  # NB partagé
    assert par_ref["U1"].pins["3"] == par_ref["R2"].pins["1"]  # NOUT partagé
    assert par_ref["Q1"].pins["C"] == "VCC" and par_ref["Q1"].pins["E"] == "GND"
    # Broches non câblées de U1 : relues comme VIDES (les NET# singletons
    # crees par generer_xml sont re-masques, convention spec §3.2).
    assert par_ref["U1"].pins["2"] == ""
    assert par_ref["U1"].pins["4"] == ""


def test_import_sans_backend_graphique():
    code = ("import sys; import circuit_analyzer.saisie; "
            "sys.exit(1 if any(m in sys.modules for m in "
            "('tkinter', 'customtkinter', 'matplotlib')) else 0)")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert r.returncode == 0, r.stderr
