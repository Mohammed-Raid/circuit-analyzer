"""
@file test_eretro.py
@brief Tests unitaires de l'import des fichiers réels ERetroDesign
(circuit_analyzer/eretro.py + adaptations de lire_xml). Fixtures BoardSCH
synthétiques écrites à la main — le corpus réel est couvert par
test_eretro_corpus.py.
"""
import os
import tempfile

import pytest

from circuit_analyzer.eretro import normaliser_nom, mapper_nom
from circuit_analyzer.xml import lire_xml, _analyser_ref_packee


# ── Helpers fixtures ──────────────────────────────────────────────────────────

ENTETE = ('<?xml version="1.0" encoding="utf-8"?>\n'
          '<BoardSCH xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
          'xmlns:xsd="http://www.w3.org/2001/XMLSchema">')


def _pin(refs=(), pnumber='', pname=''):
    """@brief Fragment <DataPin> ERetroDesign (Pname/Pnumber optionnels, comme les vrais fichiers)."""
    node_l = ''.join(f'<string>{r}</string>' for r in refs)
    morceaux = ['    <DataPin>']
    if pname:
        morceaux.append(f'      <Pname>{pname}</Pname>')
    if pnumber:
        morceaux.append(f'      <Pnumber>{pnumber}</Pnumber>')
    morceaux.append(f'      <NodeL>{node_l}</NodeL>')
    morceaux.append('      <Pin><X>0</X><Y>0</Y></Pin>')
    morceaux.append('    </DataPin>')
    return '\n'.join(morceaux)


def _item(name, value='', pins=(), comp_id=0, typ=None, segments=(), nb_arcs=0):
    """@brief Fragment <DataItem> ERetroDesign. pins = liste de fragments _pin().

    @param segments Liste de (sx, sy, ex, ey) → <datasegment><DataSegment>...
    @param nb_arcs Nombre d'arcs vides à émettre dans <dataarc> (pour classer_par_forme).
    """
    typ_xml = f'<typ>{typ}</typ>' if typ is not None else ''
    segs_xml = ''.join(
        f'<DataSegment><Spoint><X>{sx}</X><Y>{sy}</Y></Spoint>'
        f'<Epoint><X>{ex}</X><Y>{ey}</Y></Epoint></DataSegment>'
        for (sx, sy, ex, ey) in segments)
    arcs_xml = '<DataArc />' * nb_arcs
    return (f'  <DataItem>\n'
            f'    <Name>{name}</Name><value>{value}</value>\n'
            f'    <datasegment>{segs_xml}</datasegment>\n'
            f'    <dataarc>{arcs_xml}</dataarc>\n'
            f'    <datapin>\n' + '\n'.join(pins) + '\n    </datapin>\n'
            f'    <id>{comp_id}</id>{typ_xml}\n'
            f'  </DataItem>')


def _fil(cfirst, clast):
    """@brief Fragment <Line> ERetroDesign (extrémités = refs chaîne brutes)."""
    return (f'  <Line><CFirst>{cfirst}</CFirst><CLast>{clast}</CLast>'
            f'<LP /><ID>0</ID></Line>')


def _boardsch(items, fils, ccomps=''):
    """@brief Document BoardSCH complet à partir des fragments."""
    return (f'{ENTETE}\n<CmpntL>\n' + '\n'.join(items) + '\n</CmpntL>\n'
            f'<lineL>\n' + '\n'.join(fils) + '\n</lineL>\n'
            f'<CCmpntL>{ccomps}</CCmpntL>\n</BoardSCH>')


def _lire(xml_texte):
    """@brief Écrit le XML dans un fichier temporaire et le lit via lire_xml."""
    with tempfile.NamedTemporaryFile('w', suffix='.xml', delete=False,
                                     encoding='utf-8') as f:
        f.write(xml_texte)
        chemin = f.name
    try:
        return lire_xml(chemin)
    finally:
        os.unlink(chemin)


# ── Task 1 : normalisation + mapping ─────────────────────────────────────────

def test_normaliser_nom():
    assert normaliser_nom('Résistance  Trad') == 'resistance trad'
    assert normaliser_nom('  CONDO CMS ') == 'condo cms'


@pytest.mark.parametrize('nom, type_attendu', [
    ('resistance trad', 'R'), ('Resistance CMS', 'R'), ('pot', 'R'),
    ('THERMISTANCE', 'R'), ('VARISTANCE', 'R'),
    ('condo', 'C'), ('Condo CMS', 'C'),
    ('inductance', 'L'),
    ('DIODE', 'D'), ('ZENER', 'D'),
    ('npn', 'Q'), ('Transistor NPN', 'Q'), ('Transistor PNP', 'Q'),
    ('mosfet', 'M'), ('mosfet p', 'M'),
    ('FUSIBLE', 'F'), ('RELAIS 2RT', 'K'),
])
def test_mapper_nom_familles(nom, type_attendu):
    correspondance = mapper_nom(nom)
    assert correspondance is not None, f'{nom!r} devrait être mappé'
    assert correspondance[0] == type_attendu


def test_mapper_nom_puce_catalogue():
    # NE555 n'est pas dans la table ERetroDesign : reconnu via identifier()
    assert mapper_nom('NE555') == ('U', {})


def test_mapper_nom_inconnu():
    assert mapper_nom('transfo') is None
    assert mapper_nom('') is None


def test_import_npn_broches_pnumber():
    # npn.xml réel : Pname VIDE, Pnumber = B/C/E → les broches doivent
    # s'appeler B/C/E (préférence Pnumber sur Pname).
    xml = _boardsch(
        [_item('npn', pins=[_pin(refs=['0_0_0_0'], pnumber='B'),
                            _pin(pnumber='C'), _pin(pnumber='E')], comp_id=0),
         _item('resistance trad', value='10k',
               pins=[_pin(refs=['1_0_1_0']), _pin()], comp_id=1)],
        [_fil('0_0_0_0', '1_0_1_0')],
    )
    comps = _lire(xml)
    q = next(c for c in comps if c.type == 'Q')
    r = next(c for c in comps if c.type == 'R')
    assert set(q.pins) == {'B', 'C', 'E'}
    # passif ERetroDesign : broches anonymes → numérotées par position
    assert set(r.pins) == {'1', '2'}
    # la base du transistor et la broche 1 de la résistance partagent un net
    assert q.pins['B'] == r.pins['1']


def test_import_diode_plan_anode_cathode():
    # DIODE.xml réel : Pnumber = 1/2 → plan '1'→A, '2'→K
    xml = _boardsch(
        [_item('DIODE', pins=[_pin(pnumber='1', pname='ANODE'),
                              _pin(pnumber='2', pname='CATHODE')])],
        [],
    )
    comps = _lire(xml)
    d = next(c for c in comps if c.type == 'D')
    assert set(d.pins) == {'A', 'K'}


def test_import_inconnu_reste_boite_x():
    xml = _boardsch([_item('transfo', pins=[_pin(), _pin(), _pin(), _pin()])], [])
    comps = _lire(xml)
    x = next(c for c in comps if c.type == 'X')
    assert len(x.pins) == 4
    assert any('transfo' in w for w in comps.warnings)


# ── Task 2 : connexité par égalité NodeL, indexation par position ────────────

def test_connexite_refs_sans_underscore():
    # Vieux format réel (SaveDiag.xml) : refs concaténées '1001'/'2011' —
    # indécodables par parsing, résolues par égalité avec NodeL.
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['1001']), _pin()], comp_id=0),
         _item('condo', pins=[_pin(refs=['2011']), _pin()], comp_id=0)],
        [_fil('1001', '2011')],
    )
    comps = _lire(xml)
    r = next(c for c in comps if c.type == 'R')
    c = next(c for c in comps if c.type == 'C')
    assert r.pins['1'] == c.pins['1']          # même net
    assert r.pins['1'].startswith('NET')


def test_id_zero_partout_indexation_par_position():
    # 41 composants id=0 dans TestDiagram.xml : la clé <id> écraserait tout.
    xml = _boardsch(
        [_item('resistance trad', value='1k',
               pins=[_pin(refs=['A']), _pin()], comp_id=0),
         _item('resistance trad', value='2k',
               pins=[_pin(refs=['B']), _pin()], comp_id=0),
         _item('resistance trad', value='3k',
               pins=[_pin(refs=['C']), _pin()], comp_id=0)],
        [_fil('A', 'B'), _fil('B', 'C')],
    )
    comps = _lire(xml)
    rs = [c for c in comps if c.type == 'R']
    assert len(rs) == 3                        # aucun composant écrasé
    assert {r.value for r in rs} == {'1k', '2k', '3k'}
    # les trois broches 1 sont sur le même net via les deux fils
    assert len({r.pins['1'] for r in rs}) == 1


def test_fil_non_resolu_warning_sans_exception():
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['OK']), _pin()])],
        [_fil('OK', 'REF_FANTOME')],
    )
    comps = _lire(xml)
    assert len([c for c in comps if c.type == 'R']) == 1
    assert any('REF_FANTOME' in w for w in comps.warnings)


def test_dialecte_natif_round_trip_inchange():
    # Non-régression ciblée : un fichier produit par notre générateur donne
    # les mêmes nets qu'avant (la suite complète reste le vrai garde-fou).
    from circuit_analyzer.xml_generator import BoardSCHGenerator
    g = BoardSCHGenerator()
    r1 = g.add('Résistance', '10k')
    c1 = g.add('Capa', '100n')
    g.connect(r1, '1', c1, '+')
    comps = _lire(g.to_xml())
    r = next(c for c in comps if c.type == 'R')
    c = next(c for c in comps if c.type == 'C')
    assert r.pins['1'] == c.pins['1']


# ── Task 3 : puces composées ─────────────────────────────────────────────────

def _ccomp(name, pins_ext=(), items_int=(), fils_int=()):
    """@brief Fragment <CComp> : boîtier + items internes (DItemL) + fils internes (CCLine)."""
    return (f'  <CComp>\n'
            f'    <Name>{name}</Name><value />\n'
            f'    <datapin>\n' + '\n'.join(pins_ext) + '\n    </datapin>\n'
            f'    <id>0</id>\n'
            f'    <DItemL>\n' + '\n'.join(items_int) + '\n    </DItemL>\n'
            f'    <CCLine>\n' + '\n'.join(fils_int) + '\n    </CCLine>\n'
            f'  </CComp>')


def test_compose_aplati_en_items_internes():
    # Une « puce » de 2 transistors internes reliés par un fil interne ; la
    # broche externe est pontée vers le réseau interne par un CCLine PONT
    # (mécanisme réel du C#, Form2.cs) : CFirst = la ref X présente dans le
    # NodeL de la broche EXTERNE du boîtier, CLast = la ref de la broche
    # INTERNE — extrémités toujours distinctes, deux broches ne partagent
    # jamais la même chaîne NodeL.
    ccomp = _ccomp(
        'MODHYB',
        pins_ext=[_pin(refs=['T0000', 'X1'])],
        items_int=[
            _item('npn', pins=[_pin(refs=['CB1'], pnumber='B'),
                               _pin(refs=['C10'], pnumber='C'),
                               _pin(pnumber='E')]),
            _item('npn', pins=[_pin(refs=['C11'], pnumber='B'),
                               _pin(pnumber='C'), _pin(pnumber='E')]),
        ],
        fils_int=[_fil('X1', 'CB1'), _fil('C10', 'C11')],
    )
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['R00']), _pin()])],
        [_fil('R00', 'T0000')],
        ccomps=ccomp,
    )
    comps = _lire(xml)
    internes = [c for c in comps if '.' in c.ref]
    assert len(internes) == 2
    assert all(c.type == 'Q' for c in internes)
    assert comps.groupes_puces == {internes[0].ref.split('.')[0]: 'MODHYB'}
    # le signal traverse le boîtier : R → broche externe → X1 → base interne
    r = next(c for c in comps if c.type == 'R')
    q1 = next(c for c in internes if c.ref.endswith('.1'))
    assert r.pins['1'] == q1.pins['B']
    # le fil interne relie le collecteur de Q.1 à la base de Q.2
    q2 = next(c for c in internes if c.ref.endswith('.2'))
    assert q1.pins['C'] == q2.pins['B']


def test_compose_sans_interieur_devient_boite_noire():
    ccomp = _ccomp('MYSTERE', pins_ext=[_pin(refs=['T0000']), _pin()])
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['R00']), _pin()])],
        [_fil('R00', 'T0000')],
        ccomps=ccomp,
    )
    comps = _lire(xml)
    boite = next(c for c in comps if c.ref.startswith('X') or c.type == 'U')
    assert len(boite.pins) == 2
    assert any('MYSTERE' in w for w in comps.warnings)
    # la connexion externe est conservée
    r = next(c for c in comps if c.type == 'R')
    assert r.pins['1'] in boite.pins.values()


# ── Task 4 : alimentations par champ typ ─────────────────────────────────────

def test_alim_typ_g_devient_gnd():
    # <typ> = code ASCII du char C# : 71 = 'G' (masse ERetroDesign).
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['R01']), _pin(refs=['R02'])]),
         _item('MASSE1', pins=[_pin(refs=['G01'])], typ=71)],
        [_fil('R02', 'G01')],
    )
    comps = _lire(xml)
    r = next(c for c in comps if c.type == 'R')
    assert r.pins['2'] == 'GND'
    # le symbole d'alim n'est pas un composant
    assert all('MASSE1' != getattr(c, 'value', '') for c in comps)
    assert len([c for c in comps if c.type != 'R']) == 0


def test_alim_typ_v_devient_vcc():
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['R01']), _pin(refs=['R02'])]),
         _item('ALIM1', pins=[_pin(refs=['V01'])], typ=86)],   # 86 = 'V'
        [_fil('R01', 'V01')],
    )
    comps = _lire(xml)
    r = next(c for c in comps if c.type == 'R')
    assert r.pins['1'] == 'VCC'


def test_alim_typ_v_avec_rail_nomme_dans_value():
    xml = _boardsch(
        [_item('resistance trad', pins=[_pin(refs=['R01']), _pin(refs=['R02'])]),
         _item('ALIM1', value='+12V', pins=[_pin(refs=['V01'])], typ=86)],
        [_fil('R01', 'V01')],
    )
    comps = _lire(xml)
    r = next(c for c in comps if c.type == 'R')
    assert r.pins['1'] == '+12V'


def test_typ_v_deux_broches_reste_composant():
    # Garde anti-faux-positif : 2 broches = pas un symbole de rail (un vrai
    # composant peut porter typ 'V' par accident d'encodage ord(nom[0])).
    xml = _boardsch(
        [_item('VARISTANCE', pins=[_pin(), _pin()], typ=86)],
        [],
    )
    comps = _lire(xml)
    assert len(comps) == 1
    assert comps[0].type == 'R'    # mappé par Task 1, pas avalé comme rail


# ── Task 5 (fix post-review) : cas limites du décodeur de refs packées ───────

def test_ref_packee_5_chiffres_rejetee():
    # Cas ambigu historique ('14001') : indécodable sans les largeurs de
    # champs, doit rester rejeté (voir eretro.py, règle d'or + exception).
    with pytest.raises(ValueError):
        _analyser_ref_packee('14001')


def test_ref_packee_non_numerique_rejetee():
    with pytest.raises(ValueError):
        _analyser_ref_packee('20a0')
    with pytest.raises(ValueError):
        _analyser_ref_packee('T400')


def test_ref_packee_4_chiffres_decodee():
    assert _analyser_ref_packee('2000') == (2, 0)


# ── Task 3 : palier de reconnaissance par forme dans lire_xml ────────────────

def test_inconnu_type_par_sa_forme_zigzag_devient_R():
    # Nom inconnu + forme zigzag 2 broches → R, avec avertissement dédié.
    segs = [(502, 500, 749, 500), (749, 500, 799, 402), (800, 401, 901, 596),
            (903, 599, 997, 401), (999, 403, 1099, 601), (1101, 602, 1196, 402),
            (1198, 401, 1249, 499), (1251, 499, 1499, 499)]
    item = _item('ZigMachin', pins=[_pin(refs=['n1']), _pin(refs=['n2'])],
                 segments=segs)
    comps = _lire(_boardsch([item], []))
    c = comps[0]
    assert c.type == 'R'
    assert any('forme' in w.lower() and 'ZigMachin' in w for w in comps.warnings)


def test_inconnu_sans_forme_franche_reste_boite_noire():
    item = _item('Truc', pins=[_pin(refs=['a']), _pin(refs=['b'])], segments=[])
    comps = _lire(_boardsch([item], []))
    assert comps[0].type == 'X'


# ── Task 5 : marqueur par_forme (rendu boîte IC neutre, jamais un AOP) ──────

def test_composant_par_forme_defaut_false():
    from circuit_analyzer.composant import Composant
    c = Composant(ref="R1", type="R", pins={"1": "a", "2": "b"})
    assert c.par_forme is False


def test_forme_reconnue_pose_le_marqueur_par_forme():
    # Nom inconnu + zigzag 2 broches → R, marqué par_forme ; un nom connu ne l'est pas.
    segs = [(502, 500, 749, 500), (749, 500, 799, 402), (800, 401, 901, 596),
            (903, 599, 997, 401), (999, 403, 1099, 601), (1101, 602, 1196, 402),
            (1198, 401, 1249, 499), (1251, 499, 1499, 499)]
    inconnu = _item('ZigMachin', pins=[_pin(refs=['n1']), _pin(refs=['n2'])],
                    segments=segs)
    comps = _lire(_boardsch([inconnu], []))
    zig = next(c for c in comps if c.type == 'R')
    assert zig.par_forme is True
