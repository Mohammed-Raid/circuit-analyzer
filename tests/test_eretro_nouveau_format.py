"""@file test_eretro_nouveau_format.py
@brief Fixture de non-regression du NOUVEAU format BoardSCH (ERetroDesign 2026-07).

Le collegue a fait evoluer son editeur C# : nouvelles refs de connexite
(`ConnRef`), jonctions fil-sur-fil (marque 999999), et trois listes en plus
(`Texts`, `NetLabels`, `Vias`). Ces cartes ont d'abord vecu en scratchpad ; on
les fige ici, generees a la volee dans un `tmp_path`, pour que toute regression
de lecture echoue en nommant le cas.

Contrat de refs repris du C# :
  ConnRef.Pin(c,p,n,l)      -> "c_p_n_l"
  ConnRef.Compound(c,p,n,l) -> "Tc_p_n_l"
  ConnRef.Junction(c,p,l)   -> "c_p_999999_l"

La connexite attendue est exprimee par INDICE d'ordre et par Pnumber : le
lecteur renumerote les reperes (X1, X2...) et nomme les broches par Pnumber.
"""
from xml.sax.saxutils import escape

import pytest

from circuit_analyzer.xml import lire_xml

JONCTION = 999999


# ── Mini-generateur BoardSCH (compact, suffisant pour la connexite) ──────────

def _pin(num, refs):
    noeuds = "".join(f"<string>{r}</string>" for r in refs)
    return (f"<DataPin><Pname>{num}</Pname><Pnumber>{num}</Pnumber>"
            f"<Pin><X>0</X><Y>0</Y></Pin><NodeL>{noeuds}</NodeL>"
            f"<Size>9</Size></DataPin>")


def _item(nom, ref, val, pins, balise="DataItem"):
    return (f"<{balise}><Name>{nom}</Name><reference>{ref}</reference>"
            f"<value>{val}</value><datapin>{''.join(pins)}</datapin>"
            f"<CtrIem><X>0</X><Y>0</Y></CtrIem><angle>0</angle></{balise}>")


def _fil(idx, cf, cl):
    return (f"<Line><ID>{idx}</ID><CFirst>{cf}</CFirst>"
            f"<CLast>{cl}</CLast></Line>")


def _carte(items=(), composes=(), fils=(), textes=(), etiquettes=(), vias=()):
    t = "".join(f"<DataText><Text>{escape(s)}</Text></DataText>"
                for s in textes)
    e = "".join(f"<NetLabel><Net>{n}</Net><AttachedLine>{a}</AttachedLine>"
                f"</NetLabel>" for n, a in etiquettes)
    v = "".join(f"<Via><Pos><X>{x}</X><Y>0</Y></Pos><Net>{n}</Net></Via>"
                for x, n in vias)
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<BoardSCH>'
            f'<CmpntL>{"".join(items)}</CmpntL>'
            f'<lineL>{"".join(fils)}</lineL>'
            f'<CCmpntL>{"".join(composes)}</CCmpntL>'
            f'<Texts>{t}</Texts><NetLabels>{e}</NetLabels><Vias>{v}</Vias>'
            f'</BoardSCH>')


def _res(ref, val, i):
    """Resistance a deux broches, refs de connexite indexees sur `i`."""
    return _item("R", ref, val,
                 [_pin("1", [f"{i}_0_0_0"]), _pin("2", [f"{i}_1_0_0"])])


def _ecrire(tmp_path, nom, xml):
    p = tmp_path / f"{nom}.xml"
    p.write_text(xml, encoding="utf-8")
    return str(p)


# ── Cas et connexite attendue : groupes de (indice, Pnumber) au meme net ─────

CAS = {
    "01_base_simple": (
        _carte(items=[_res("R1", "10k", 0), _res("R2", "22k", 1)],
               fils=[_fil(0, "0_1_0_0", "1_0_0_0")]),
        [[(0, "2"), (1, "1")]]),

    "02_compose_T": (
        _carte(
            items=[_res("R1", "10k", 0)],
            composes=[_item("CD4011", "U1", "CD4011",
                            [_pin("1", ["T0_0_0_0"]), _pin("3", ["T0_1_0_1"])],
                            balise="CComp")],
            fils=[_fil(0, "0_1_0_0", "T0_0_0_0")]),
        [[(0, "2"), (1, "1")]]),

    "03_jonction": (
        _carte(
            items=[_res("R1", "10k", 0), _res("R2", "22k", 1),
                   _res("R3", "33k", 2)],
            fils=[_fil(0, "0_1_0_0", "1_0_0_0"),
                  _fil(1, "2_0_0_0", f"1_0_{JONCTION}_0")]),
        [[(0, "2"), (1, "1"), (2, "1")]]),

    "04_netlabel": (
        _carte(
            items=[_res("R1", "10k", 0), _res("R2", "22k", 1)],
            fils=[_fil(0, "0_1_0_0", "0_1_0_0"),
                  _fil(1, "1_0_0_0", "1_0_0_0")],
            etiquettes=[("VCC", 0), ("VCC", 1)]),
        [[(0, "2"), (1, "1")]]),

    # Via : le collegue POSE et persiste des vias portant un Net, mais son app
    # ne les relie PAS encore a la netlist (comme les netlabels a l'origine), et
    # un via se raccorde par POSITION absolue de broche — infra que le lecteur
    # n'a pas. On garantit donc UNIQUEMENT la lecture sans erreur ; la fusion
    # par via reste a faire quand le collegue la cablera cote C#.
    # ponytail: via-by-position non implemente ; a ajouter si le collegue relie
    # les vias a sa netlist.
    "05_via": (
        _carte(
            items=[_res("R1", "10k", 0), _res("R2", "22k", 1)],
            vias=[(20, "N1"), (280, "N1")]),
        []),

    "06_textes": (
        _carte(items=[_res("R1", "10k", 0)],
               textes=["Alimentation 24V", "<&>\"'"]),
        []),

    "09_jonction_chaine": (
        _carte(
            items=[_res(f"R{i+1}", "10k", i) for i in range(4)],
            fils=[_fil(0, "0_1_0_0", "1_0_0_0"),
                  _fil(1, "2_0_0_0", f"1_0_{JONCTION}_0"),
                  _fil(2, "3_0_0_0", f"2_0_{JONCTION}_1")]),
        [[(0, "2"), (1, "1"), (2, "1"), (3, "1")]]),

    "13_espaces_casse": (
        _carte(
            items=[_res("R1", "10k", 0), _res("R2", "22k", 1)],
            fils=[_fil(0, "0_1_0_0", " 1_0_0_0 ")]),
        [[(0, "2"), (1, "1")]]),
}

def _net(comps, idx, pnum):
    assert idx < len(comps), f"composant #{idx} absent"
    n = (comps[idx].pins or {}).get(pnum)
    assert n is not None, f"#{idx}.{pnum} sans net"
    return n


@pytest.mark.parametrize("nom", sorted(CAS))
def test_le_nouveau_format_se_lit_sans_erreur(nom, tmp_path):
    """Aucune carte du nouveau format ne doit lever a la lecture."""
    xml, _ = CAS[nom]
    comps = lire_xml(_ecrire(tmp_path, nom, xml))
    assert comps, f"{nom} : aucun composant lu"


@pytest.mark.parametrize("nom", sorted(CAS))
def test_connexite_du_nouveau_format(nom, tmp_path):
    """Les broches attendues au meme net y sont effectivement."""
    xml, attendu = CAS[nom]
    comps = lire_xml(_ecrire(tmp_path, nom, xml))
    for groupe in attendu:
        nets = {_net(comps, idx, pnum) for idx, pnum in groupe}
        assert len(nets) == 1, (
            f"{nom} : {groupe} eclate sur {sorted(nets)}")


def test_etiquette_baptise_le_net_meme_avec_des_id_de_fil_dupliques(tmp_path):
    """Cas reel (test14) : les vrais fichiers portent des <ID> de fil tous a 0.
    L'AttachedLine d'une etiquette est donc un INDICE de fil, pas un <ID> ; le
    fil vise (indice 1) est le point milieu R1-R2, que l'utilisateur nomme
    « vout ». Ce nom doit baptiser le net, pas rester NET#."""
    xml = _carte(
        items=[_res("R1", "10k", 0), _res("R2", "22k", 1)],
        # Trois fils, TOUS <ID>0</ID> comme dans les vrais fichiers :
        #   0 : R1.2 -> VSS   1 : R1.1 -> R2.2 (milieu)   2 : R2.1 -> GND
        fils=[_fil(0, "0_1_0_0", "0_1_0_0"),
              _fil(0, "0_0_0_0", "1_1_0_0"),
              _fil(0, "1_0_0_0", "1_0_0_0")],
        etiquettes=[("vout", 1)])
    comps = lire_xml(_ecrire(tmp_path, "etiquette_id0", xml))
    nets = {n for c in comps for n in (c.pins or {}).values()}
    assert "vout" in nets, f"etiquette non appliquee ; nets={sorted(nets)}"
