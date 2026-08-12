"""@file test_tab_draw.py
@brief Groupage automatique a l'export du schema dessine (spec 2026-08-06).

Teste _xml_groupe_par_circuit directement (fonction module-level, aucun Tk) —
meme principe que test_eretro_patch.py pour tab_analyze._texte_export_analyse.
"""
import xml.etree.ElementTree as ET

from circuit_analyzer.composant import Composant
from gui.tab_draw import _xml_groupe_par_circuit


def _montage_reconnu():
    """@brief Diviseur R1/R2 + C1 + AOP U1 — meme montage que
    tests/test_eretro_groupes_reels.py::_carte, deja prouve detecte par
    test_grpl_est_creee_meme_absente_de_la_source."""
    return [
        Composant("R1", "R", {"1": "IN", "2": "N1"}, "10k"),
        Composant("R2", "R", {"1": "N1", "2": "OUT"}, "100k"),
        Composant("C1", "C", {"1": "N1", "2": "GND"}, "100n"),
        Composant("U1", "U", {"IN+": "GND", "IN-": "N1", "OUT": "OUT"}, ""),
    ]


def test_montage_reconnu_produit_un_groupe():
    xml = _xml_groupe_par_circuit(_montage_reconnu())
    racine = ET.fromstring(xml)
    assert racine.findall("./GrpL/GRPS"), "aucun groupe ecrit pour un montage reconnu"


def test_aucun_montage_reconnu_grpl_vide():
    """Non-regression : une resistance isolee ne doit RIEN grouper."""
    xml = _xml_groupe_par_circuit([Composant("R1", "R", {"1": "IN", "2": "OUT"}, "1k")])
    racine = ET.fromstring(xml)
    assert racine.findall("./GrpL/GRPS") == []
    assert racine.find("GrpL") is not None


def test_aucun_montage_reconnu_diode_non_classifiee_grpl_vide():
    """Non-regression : une diode isolee (non classifiee) ne doit RIEN grouper.

    Comme une resistance seule, une diode entre deux noeuds simples
    (pas sur un rail, pas dans un motif reconnu) est emise par
    detecter_diodes_non_classifiees comme catch-all. Le contrat
    non-regression exige que <GrpL> reste vide.
    """
    xml = _xml_groupe_par_circuit([Composant("D1", "D", {"1": "IN", "2": "OUT"}, "")])
    racine = ET.fromstring(xml)
    assert racine.findall("./GrpL/GRPS") == []
    assert racine.find("GrpL") is not None


def test_montage_reconnu_plus_composant_isole_cas_mixte():
    """Montage reconnu (R1/R2/C1/U1) + un residu catch-all authentiquement
    isole (R3, sur des noeuds X1/X2 qui ne touchent aucun noeud du montage,
    donc jamais rattache au groupe via le partage de net de
    `_grouper_par_circuit`) : le cas mixte, non couvert jusqu'ici.

    Rappel du mecanisme reel (verifie par execution, pas suppose) : le
    detecteur ne classe le montage que sous 'Derivateur (AOP)' avec
    [U1, C1, R2] — R1 lui-meme n'est capte QUE par le detecteur catch-all
    'Impedance Z'. Une fois ce match filtre par `_xml_groupe_par_circuit`,
    R1 redevient un composant "non classifie" que `_grouper_par_circuit`
    rattache a son montage par net partage (N1) : sans le filtre du
    catch-all, R1 recevrait son PROPRE bloc 'Impedance Z' et ne rejoindrait
    jamais le groupe du montage.

    Ce test protege donc deux choses a la fois :
      - R1 (composant reel du montage, seulement capte par le filet de
        securite) rejoint bien le groupe du montage (meme <GpId> que
        U1/R2/C1) plutot que de finir isole ou mal groupe ;
      - R3 (residu authentiquement isole, aucun net partage) N'EST PAS
        aspire dans le groupe du montage et n'est PAS silencieusement
        supprime de l'export (il obtient son propre <GpId>, dans le bloc
        « Divers » generique de `_grouper_par_circuit` — un mecanisme
        prexistant, hors perimetre de cette branche, qui regroupe tout
        composant non classifie non rattachable par net).
    """
    composants = _montage_reconnu() + [
        Composant("R3", "R", {"1": "X1", "2": "X2"}, "1k"),
    ]
    xml = _xml_groupe_par_circuit(composants)
    racine = ET.fromstring(xml)

    assert racine.findall("./GrpL/GRPS"), "aucun groupe ecrit pour le montage reconnu"

    gpid_par_ref = {
        di.find("reference").text: di.find("GpId").text
        for di in racine.findall(".//DataItem")
        if di.find("reference") is not None
    }
    assert gpid_par_ref["R3"] not in (None, "0"), "R3 a disparu de l'export"
    assert gpid_par_ref["R1"] == gpid_par_ref["U1"] == gpid_par_ref["R2"] == gpid_par_ref["C1"], (
        "R1 (capte seulement par le catch-all avant filtrage) aurait du "
        "rejoindre le groupe de son propre montage"
    )
    assert gpid_par_ref["R3"] != gpid_par_ref["U1"], (
        "R3 (isole, aucun net partage avec le montage) ne doit pas etre "
        "aspire dans le groupe du montage"
    )


def test_fonction_est_bien_exportee_du_module():
    import gui.tab_draw as td
    assert callable(td._xml_groupe_par_circuit)
