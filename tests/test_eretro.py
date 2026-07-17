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
from circuit_analyzer.xml import lire_xml


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


def _item(name, value='', pins=(), comp_id=0, typ=None):
    """@brief Fragment <DataItem> ERetroDesign. pins = liste de fragments _pin()."""
    typ_xml = f'<typ>{typ}</typ>' if typ is not None else ''
    return (f'  <DataItem>\n'
            f'    <Name>{name}</Name><value>{value}</value>\n'
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
