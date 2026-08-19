"""[MODIF 2026-08-19] Repli géométrique pour les jonctions fil-sur-fil.

BUG TROUVÉ EN TESTANT : un fil qui démarre sur un AUTRE fil (jonction fil-
sur-fil, `ERetroDesign/ConnRef.cs` JunctionMark=999999) portait une réf
comp/broche qui pouvait devenir périmée (composant supprimé, fichier
reconstruit) sans que le point physique de la jonction ne change -- la
lecture perdait alors toute la connexité de ce côté, sans même toujours
lever un avertissement clair. `lire_xml` répare maintenant ce cas comme il
le fait déjà pour les vias : par coïncidence géométrique exacte des points
<LP>, indépendamment de la référence textuelle.
"""

from pathlib import Path

from circuit_analyzer.xml import lire_xml

_FIXTURE = Path(__file__).resolve().parent / "_fixture_jonction_geometrique.xml"


def test_jonction_avec_reference_perimee_est_reparee_par_geometrie():
    comps = lire_xml(str(_FIXTURE))
    par_ref = {c.ref: c for c in comps}
    # R1-R2 sont reliés directement ; R3 rejoint le même réseau via une
    # jonction fil-sur-fil dont la référence (CFirst) est délibérément
    # invalide ('99_9_3_1', composant 99 inexistant) -- seule la géométrie
    # (le fil de R3 démarre EXACTEMENT sur le point (100,0), un sommet
    # explicite du fil R1-R2) permet de reconstituer la connexité.
    net_commun = par_ref["R1"].pins["1"]
    assert par_ref["R2"].pins["1"] == net_commun
    assert par_ref["R3"].pins["1"] == net_commun
    # La réf périmée reste bien signalée (diagnostic), sans empêcher la
    # réparation électrique.
    assert any("non résolu" in w for w in comps.warnings)


def test_jonction_perimee_ne_fusionne_pas_les_broches_non_reliees():
    comps = lire_xml(str(_FIXTURE))
    par_ref = {c.ref: c for c in comps}
    # Les broches 2 de chacun ne sont reliées à rien d'autre : chacune
    # doit rester sur son propre réseau, la réparation ne doit pas tout
    # écraser sur un seul net global.
    nets_broches_2 = {par_ref[r].pins["2"] for r in ("R1", "R2", "R3")}
    assert len(nets_broches_2) == 3
