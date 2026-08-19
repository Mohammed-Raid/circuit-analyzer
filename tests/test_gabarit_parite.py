"""
@file test_gabarit_parite.py
@brief Preuve (pas bascule) : sur des cas representatifs des detecteurs
Python existants, le moteur gabarit (Phase 1) produit les MEMES composants
que `detecter_suiveur_tension`/`detecter_amplificateur_inverseur`. Le
`circuit_type` peut differer par le nom de fichier gabarit -- documente,
pas un echec. Voir docs/superpowers/plans/2026-08-17-gabarits-xml-montages-canoniques.md,
Task 3 : ce test ne branche RIEN dans `analyser()`, il compare seulement.
"""
import os

from circuit_analyzer.composant import construire_graphe
from circuit_analyzer.detecteur import (
    detecter_amplificateur_differentiel,
    detecter_amplificateur_emetteur_commun,
    detecter_amplificateur_inverseur,
    detecter_amplificateur_non_inverseur,
    detecter_amplificateur_sommateur,
    detecter_bascule_schmitt,
    detecter_comparateur,
    detecter_darlington,
    detecter_derivateur,
    detecter_detecteur_crete,
    detecter_diode_protection_esd,
    detecter_diode_roue_libre,
    detecter_integrateur,
    detecter_redresseur_simple,
    detecter_miroir_courant,
    detecter_mosfet_commutation,
    detecter_mosfet_cote_haut,
    detecter_push_pull,
    detecter_suiveur_emetteur,
    detecter_suiveur_tension,
    detecter_transistor_commutation,
)
from circuit_analyzer.gabarit import charger_gabarit, charger_gabarit_relation
from circuit_analyzer.parser import Component

_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "patterns_reference")
_SUIVEUR = charger_gabarit(os.path.join(_DIR, "Suiveur de tension.xml"))
_INVERSEUR = charger_gabarit(os.path.join(_DIR, "Amplificateur inverseur.xml"))
_SOMMATEUR = charger_gabarit(os.path.join(_DIR, "Amplificateur sommateur.xml"))
_NON_INVERSEUR = charger_gabarit(os.path.join(_DIR, "Amplificateur non-inverseur.xml"))
_INTEGRATEUR = charger_gabarit(os.path.join(_DIR, "Integrateur.xml"))
_DERIVATEUR = charger_gabarit(os.path.join(_DIR, "Derivateur.xml"))
_DIFFERENTIEL = charger_gabarit(os.path.join(_DIR, "Amplificateur differentiel.xml"))
_COMPARATEUR = charger_gabarit(os.path.join(_DIR, "Comparateur.xml"))
_TRANSISTOR_COMMUT = charger_gabarit(os.path.join(_DIR, "Transistor en commutation.xml"))
_SUIVEUR_EMETTEUR = charger_gabarit(os.path.join(_DIR, "Collecteur commun (suiveur d'emetteur).xml"))
_MOSFET_COMMUT = charger_gabarit(os.path.join(_DIR, "MOSFET en commutation.xml"))
_MOSFET_HAUT = charger_gabarit(os.path.join(_DIR, "MOSFET haute-tension (cote haut).xml"))
_ROUE_LIBRE = charger_gabarit(os.path.join(_DIR, "Diode de roue libre.xml"))
_ESD = charger_gabarit(os.path.join(_DIR, "Diode de protection ESD.xml"))
_MIROIR = charger_gabarit_relation(os.path.join(_DIR, "Miroir de courant BJT.xml"))
_PUSHPULL = charger_gabarit_relation(os.path.join(_DIR, "Etage push-pull.xml"))
_DARLINGTON = charger_gabarit_relation(os.path.join(_DIR, "Paire Darlington.xml"))
_EMETTEUR_COMMUN = charger_gabarit(os.path.join(_DIR, "Amplificateur emetteur commun.xml"))
_SCHMITT = charger_gabarit(os.path.join(_DIR, "Bascule de Schmitt.xml"))
_REDRESSEUR_SIMPLE = charger_gabarit(os.path.join(_DIR, "Redresseur simple alternance.xml"))
_DETECTEUR_CRETE = charger_gabarit(os.path.join(_DIR, "Détecteur de crête.xml"))


def _refs(matches):
    return sorted({r for m in matches for r in m['components']})


def test_parite_suiveur_cas_simple():
    comps = [Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_OUT', 'OUT': 'NET_OUT',
                                   'V+': 'VCC', 'V-': 'GND'})]
    graphe = construire_graphe(comps)
    ancien = detecter_suiveur_tension(graphe)
    nouveau = _SUIVEUR.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['U1']


def test_parite_suiveur_pas_de_faux_positif_sur_inverseur():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_suiveur_tension(graphe)
    nouveau = _SUIVEUR.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_parite_inverseur_cas_simple():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_amplificateur_inverseur(graphe)
    nouveau = _INVERSEUR.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['R1', 'R2', 'U1']


def test_parite_inverseur_pas_de_faux_positif_sur_suiveur():
    comps = [Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_OUT', 'OUT': 'NET_OUT',
                                   'V+': 'VCC', 'V-': 'GND'})]
    graphe = construire_graphe(comps)
    ancien = detecter_amplificateur_inverseur(graphe)
    nouveau = _INVERSEUR.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_parite_inverseur_avec_valeurs_variees():
    """Meme structure, valeurs differentes du gabarit -- doit matcher pareil
    des deux cotes (ni l'ancien detecteur ni le gabarit ne comparent les
    valeurs)."""
    comps = [
        Component('U3', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R9', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '470R'),
        Component('R10', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '1M'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_amplificateur_inverseur(graphe)
    nouveau = _INVERSEUR.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['R10', 'R9', 'U3']


def test_parite_sommateur_2_entrees():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_A', '2': 'NET_INV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_B', '2': 'NET_INV'}, '10k'),
        Component('RF', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_amplificateur_sommateur(graphe)
    nouveau = _SOMMATEUR.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['R1', 'R2', 'RF', 'U1']


def test_parite_sommateur_4_entrees():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        *[Component(f'R{i}', 'R', {'1': f'NET_{i}', '2': 'NET_INV'}, '10k') for i in range(4)],
        Component('RF', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_amplificateur_sommateur(graphe)
    nouveau = _SOMMATEUR.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau)


def test_parite_sommateur_pas_de_faux_positif_sur_inverseur_1_entree():
    """Le detecteur Python reel exige len(zin) >= 2 : avec 1 seule entree
    c'est un inverseur, le vrai detecteur sommateur ne matche pas -- le
    gabarit ne doit pas non plus (seuil de repetition = 2, voir gabarit.py)."""
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('RF', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_amplificateur_sommateur(graphe)
    nouveau = _SOMMATEUR.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_parite_non_inverseur_cas_simple():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('RF', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
        Component('RG', 'R', {'1': 'GND', '2': 'NET_INV'}, '1k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_amplificateur_non_inverseur(graphe)
    nouveau = _NON_INVERSEUR.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['RF', 'RG', 'U1']


def test_parite_non_inverseur_ne_matche_pas_inverseur():
    """Le pont de l'inverseur (Zin externe + Zf->OUT, RIEN vers GND sur IN-)
    ne doit matcher NI l'ancien detecteur non-inverseur NI son gabarit."""
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_amplificateur_non_inverseur(graphe)
    nouveau = _NON_INVERSEUR.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_parite_integrateur_cas_simple():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('C1', 'C', {'1': 'NET_OUT', '2': 'NET_INV'}, '100nF'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_integrateur(graphe)
    nouveau = _INTEGRATEUR.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['C1', 'R1', 'U1']


def test_parite_integrateur_ne_matche_pas_inverseur():
    """Feedback resistif (pas capacitif) -> ni l'ancien detecteur integrateur
    ni son gabarit ne doivent matcher (c'est un inverseur classique)."""
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_integrateur(graphe)
    nouveau = _INTEGRATEUR.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_parite_derivateur_cas_simple():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('C1', 'C', {'1': 'NET_IN', '2': 'NET_INV'}, '100nF'),
        Component('R1', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_derivateur(graphe)
    nouveau = _DERIVATEUR.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['C1', 'R1', 'U1']


def test_parite_derivateur_ne_matche_pas_integrateur():
    """Croise volontairement le gabarit derivateur (Zin=C, Zf=R) contre un
    circuit integrateur reel (Zin=R, Zf=C) -- aucun des deux cotes ne doit
    matcher."""
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('C1', 'C', {'1': 'NET_OUT', '2': 'NET_INV'}, '100nF'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_derivateur(graphe)
    nouveau = _DERIVATEUR.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_parite_differentiel_cas_simple():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_INP', 'IN-': 'NET_INN', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN1', '2': 'NET_INN'}, '10k'),
        Component('RF', 'R', {'1': 'NET_OUT', '2': 'NET_INN'}, '10k'),
        Component('R3', 'R', {'1': 'NET_IN2', '2': 'NET_INP'}, '10k'),
        Component('RG', 'R', {'1': 'GND', '2': 'NET_INP'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_amplificateur_differentiel(graphe)
    nouveau = _DIFFERENTIEL.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['R1', 'R3', 'RF', 'RG', 'U1']


def test_parite_differentiel_ne_matche_pas_inverseur():
    """IN+ directement a GND (pas de pont Z3/Zg) -- un inverseur classique,
    ni l'ancien detecteur differentiel ni son gabarit ne doivent matcher."""
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_amplificateur_differentiel(graphe)
    nouveau = _DIFFERENTIEL.correspondre(graphe)
    assert ancien == [] and nouveau == []


# ── Lot 2 : broche directement sur un rail (Comparateur, transistors, MOSFET) ──

def test_parite_comparateur_cas_simple():
    """AOP nu, rien entre OUT et les entrees -- le cas le plus simple, mais
    seulement fiable depuis la correction du bug "broche vide" (voir
    test_gabarit_broche_vide_rejette_tout_voisin_supplementaire)."""
    comps = [Component('U1', 'U', {'IN+': 'NET_A', 'IN-': 'NET_B', 'OUT': 'NET_C',
                                   'V+': 'VCC', 'V-': 'GND'})]
    graphe = construire_graphe(comps)
    ancien = detecter_comparateur(graphe)
    nouveau = _COMPARATEUR.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['U1']


def test_parite_comparateur_ne_matche_pas_avec_contre_reaction():
    comps = [
        Component('U1', 'U', {'IN+': 'GND', 'IN-': 'NET_INV', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('R1', 'R', {'1': 'NET_IN', '2': 'NET_INV'}, '10k'),
        Component('R2', 'R', {'1': 'NET_OUT', '2': 'NET_INV'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_comparateur(graphe)
    nouveau = _COMPARATEUR.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_parite_transistor_commutation_cas_simple():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_DRIVE', '2': 'NET_BASE'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_transistor_commutation(graphe)
    nouveau = _TRANSISTOR_COMMUT.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['Q1', 'R1']


def test_parite_transistor_commutation_ne_matche_pas_emetteur_flottant():
    """Emetteur PAS a la masse -- ni l'ancien detecteur ni le gabarit ne
    doivent matcher (confirme aussi que le "rail direct" rejette bien un
    signal ordinaire, pas seulement l'inverse)."""
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'NET_EMET'}),
        Component('R1', 'R', {'1': 'NET_DRIVE', '2': 'NET_BASE'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_transistor_commutation(graphe)
    nouveau = _TRANSISTOR_COMMUT.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_parite_suiveur_emetteur_cas_simple():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'VCC', 'E': 'NET_EMET'}),
        Component('RB', 'R', {'1': 'NET_IN', '2': 'NET_BASE'}, '10k'),
        Component('RE', 'R', {'1': 'NET_EMET', '2': 'GND'}, '1k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_suiveur_emetteur(graphe)
    nouveau = _SUIVEUR_EMETTEUR.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['Q1', 'RB', 'RE']


def test_parite_suiveur_emetteur_ne_matche_pas_commutation():
    """Collecteur PAS sur le rail (c'est une commutation classique, pas un
    suiveur) -- ni l'ancien detecteur ni le gabarit ne doivent matcher."""
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('R1', 'R', {'1': 'NET_DRIVE', '2': 'NET_BASE'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_suiveur_emetteur(graphe)
    nouveau = _SUIVEUR_EMETTEUR.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_parite_mosfet_commutation_cas_simple():
    """Variante SIMPLE seulement (source directement a GND) -- le vrai
    detecteur accepte AUSSI un R de sense entre source et GND (1 saut), une
    disjonction qu'un gabarit unique ne peut pas exprimer (voir doc de
    conception, limitation documentee)."""
    comps = [
        Component('M1', 'M', {'G': 'NET_GRILLE', 'D': 'NET_DRAIN', 'S': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_GRILLE'}, '100R'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_mosfet_commutation(graphe)
    nouveau = _MOSFET_COMMUT.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['M1', 'R1']


def test_parite_mosfet_haut_cas_simple():
    comps = [
        Component('M1', 'M', {'G': 'NET_GRILLE', 'D': 'VCC', 'S': 'NET_COMMUT'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_GRILLE'}, '100R'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_mosfet_cote_haut(graphe)
    nouveau = _MOSFET_HAUT.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['M1', 'R1']


def test_parite_mosfet_haut_ne_matche_pas_commutation():
    """Source a la masse (c'est une commutation cote bas) -- ni l'ancien
    detecteur cote haut ni son gabarit ne doivent matcher."""
    comps = [
        Component('M1', 'M', {'G': 'NET_GRILLE', 'D': 'NET_DRAIN', 'S': 'GND'}),
        Component('R1', 'R', {'1': 'NET_CMD', '2': 'NET_GRILLE'}, '100R'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_mosfet_cote_haut(graphe)
    nouveau = _MOSFET_HAUT.correspondre(graphe)
    assert ancien == [] and nouveau == []


# ── Lot 4 : ancre à 2 broches (diode seule) ──

def test_parite_diode_roue_libre_cas_simple():
    comps = [Component('D1', 'D', {'A': 'NET_COMMUT', 'K': 'VCC'}, '1N4148')]
    graphe = construire_graphe(comps)
    ancien = detecter_diode_roue_libre(graphe)
    nouveau = _ROUE_LIBRE.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['D1']


def test_parite_diode_roue_libre_ne_matche_pas_cathode_hors_alim():
    comps = [Component('D1', 'D', {'A': 'NET_A', 'K': 'NET_B'}, '1N4148')]
    graphe = construire_graphe(comps)
    ancien = detecter_diode_roue_libre(graphe)
    nouveau = _ROUE_LIBRE.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_parite_diode_esd_cas_simple():
    comps = [Component('D1', 'D', {'A': 'NET_SIGNAL', 'K': 'GND'}, '1N4148')]
    graphe = construire_graphe(comps)
    ancien = detecter_diode_protection_esd(graphe)
    nouveau = _ESD.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['D1']


def test_parite_diode_esd_ne_matche_pas_sans_masse():
    comps = [Component('D1', 'D', {'A': 'NET_A', 'K': 'NET_B'}, '1N4148')]
    graphe = construire_graphe(comps)
    ancien = detecter_diode_protection_esd(graphe)
    nouveau = _ESD.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_gabarit_diode_roue_libre_avec_transistor_reel_toujours_ok():
    """@brief Cas REPRESENTATIF d'une vraie carte : l'anode d'une diode de
    roue libre est presque toujours le collecteur/drain d'un transistor de
    commutation (un composant a 3+ broches, jamais un simple passif 2
    broches) -- confirme que ca matche quand meme, puisque
    `graphe.edges()` ne cree JAMAIS d'arete pour un composant a 3+ broches
    (voir construire_graphe) : l'anode n'a donc aucun "voisin 2-broches"
    au sens du moteur, exactement comme dans le gabarit isole."""
    comps = [
        Component('D1', 'D', {'A': 'NET_COMMUT', 'K': 'VCC'}, '1N4148'),
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COMMUT', 'E': 'GND'}),
        Component('RB', 'R', {'1': 'NET_CMD', '2': 'NET_BASE'}, '4k7'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_diode_roue_libre(graphe)
    nouveau = _ROUE_LIBRE.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['D1']


def test_gabarit_diode_esd_avec_passif_supplementaire_sur_le_signal_echoue_cote_gabarit():
    """@brief LIMITATION REELLE trouvee en testant (documentee, pas corrigee
    ici) : le vrai detecteur Python `detecter_diode_protection_esd` ne
    regarde QUE si une broche est a la masse -- il se moque de ce qui est
    branche sur l'AUTRE broche (le signal). Le gabarit, lui, exige que la
    structure de l'anode soit IDENTIQUE au fichier de reference (anode
    SEULE, zero voisin dessine) -- un signal qui a par ailleurs un
    condensateur de decouplage local ne matche donc PLUS cote gabarit, la
    ou l'ancien detecteur continuerait de matcher. Divergence reelle et
    attendue entre les deux implementations pour ce montage precis -- pas
    un bug a corriger dans ce lot, une limitation du modele "structure
    identique au gabarit" quand le vrai detecteur est plus permissif que la
    structure dessinee."""
    comps = [
        Component('D1', 'D', {'A': 'NET_SIGNAL', 'K': 'GND'}, '1N4148'),
        Component('C1', 'C', {'1': 'NET_SIGNAL', '2': 'GND'}, '10pF'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_diode_protection_esd(graphe)
    nouveau = _ESD.correspondre(graphe)
    assert _refs(ancien) == ['D1'], "l'ancien detecteur ignore le C1 supplementaire, comme prevu"
    assert nouveau == [], (
        "divergence documentee : le gabarit est plus strict que le detecteur reel ici")


# ── Lot 5 : relations à deux ancres (Miroir de courant, Push-pull, Darlington) ──

def test_parite_miroir_courant_cas_simple():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_B', 'C': 'VCC', 'E': 'GND'}),
        Component('Q2', 'Q', {'B': 'NET_B', 'C': 'NET_LOAD', 'E': 'GND'}),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_miroir_courant(graphe)
    nouveau = _MIROIR.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['Q1', 'Q2']


def test_parite_miroir_courant_ne_matche_pas_bases_differentes():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_B1', 'C': 'VCC', 'E': 'GND'}),
        Component('Q2', 'Q', {'B': 'NET_B2', 'C': 'NET_LOAD', 'E': 'GND'}),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_miroir_courant(graphe)
    nouveau = _MIROIR.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_parite_pushpull_cas_simple():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_B1', 'C': 'VCC', 'E': 'NET_OUT'}),
        Component('Q2', 'Q', {'B': 'NET_B2', 'C': 'GND', 'E': 'NET_OUT'}),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_push_pull(graphe)
    nouveau = _PUSHPULL.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['Q1', 'Q2']


def test_parite_pushpull_ne_matche_pas_emetteurs_separes():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_B1', 'C': 'VCC', 'E': 'NET_OUT1'}),
        Component('Q2', 'Q', {'B': 'NET_B2', 'C': 'GND', 'E': 'NET_OUT2'}),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_push_pull(graphe)
    nouveau = _PUSHPULL.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_parite_darlington_cas_simple():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_IN', 'C': 'VCC', 'E': 'NET_LIEN'}),
        Component('Q2', 'Q', {'B': 'NET_LIEN', 'C': 'VCC', 'E': 'NET_OUT'}),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_darlington(graphe)
    nouveau = _DARLINGTON.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['Q1', 'Q2']


def test_parite_darlington_ne_matche_pas_sans_lien():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_A', 'C': 'VCC', 'E': 'NET_B'}),
        Component('Q2', 'Q', {'B': 'NET_C', 'C': 'VCC', 'E': 'NET_D'}),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_darlington(graphe)
    nouveau = _DARLINGTON.correspondre(graphe)
    assert ancien == [] and nouveau == []


# ── Lot 6 : ampli emetteur commun (forme simple, ancre unique) ──

def test_parite_emetteur_commun_cas_simple():
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'NET_COLL', 'E': 'GND'}),
        Component('RC', 'R', {'1': 'VCC', '2': 'NET_COLL'}, '2k2'),
        Component('RB', 'R', {'1': 'NET_IN', '2': 'NET_BASE'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_amplificateur_emetteur_commun(graphe)
    nouveau = _EMETTEUR_COMMUN.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['Q1', 'RB', 'RC']


def test_parite_emetteur_commun_ne_matche_pas_collecteur_couplage(tmp_path):
    """Collecteur DIRECTEMENT sur VCC (donc pas de Rc) -- ni l'ancien
    detecteur ni le gabarit ne doivent matcher (c'est un suiveur
    d'emetteur potentiel, pas un emetteur commun)."""
    comps = [
        Component('Q1', 'Q', {'B': 'NET_BASE', 'C': 'VCC', 'E': 'NET_EMET'}),
        Component('RB', 'R', {'1': 'NET_IN', '2': 'NET_BASE'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_amplificateur_emetteur_commun(graphe)
    nouveau = _EMETTEUR_COMMUN.correspondre(graphe)
    assert ancien == [] and nouveau == []


# ── Lot 7 : Bascule de Schmitt (forme sans Zin, ancre unique) ──

def test_parite_schmitt_cas_simple():
    comps = [
        Component('U1', 'U', {'IN+': 'NET_INP', 'IN-': 'NET_INN', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('RF', 'R', {'1': 'NET_OUT', '2': 'NET_INP'}, '10k'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_bascule_schmitt(graphe)
    nouveau = _SCHMITT.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['RF', 'U1']


def test_parite_schmitt_ne_matche_pas_suiveur():
    comps = [Component('U1', 'U', {'IN+': 'NET_IN', 'IN-': 'NET_OUT', 'OUT': 'NET_OUT',
                                   'V+': 'VCC', 'V-': 'GND'})]
    graphe = construire_graphe(comps)
    ancien = detecter_bascule_schmitt(graphe)
    nouveau = _SCHMITT.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_gabarit_schmitt_avec_zin_divergence_documentee():
    """@brief LIMITATION REELLE (documentee, pas corrigee) : le vrai
    detecteur `detecter_bascule_schmitt` accepte Zin OPTIONNEL sur IN+ (le
    matche avec OU sans) -- un gabarit dessine SANS Zin (la forme la plus
    simple, choisie ici) exige que IN+ n'ait STRICTEMENT que Rf dessus.
    Une cible qui ajoute aussi un Zin (resistance vers un point milieu, PAS
    vers OUT) matche donc toujours cote ancien detecteur, mais plus cote
    gabarit -- divergence reelle, prouvee explicitement des deux cotes,
    meme famille de limitation que MOSFET commutation / Diode ESD."""
    comps = [
        Component('U1', 'U', {'IN+': 'NET_INP', 'IN-': 'NET_INN', 'OUT': 'NET_OUT',
                              'V+': 'VCC', 'V-': 'GND'}),
        Component('RF', 'R', {'1': 'NET_OUT', '2': 'NET_INP'}, '10k'),
        Component('ZIN', 'R', {'1': 'NET_REF', '2': 'NET_INP'}, '4k7'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_bascule_schmitt(graphe)
    nouveau = _SCHMITT.correspondre(graphe)
    assert _refs(ancien) == ['RF', 'U1', 'ZIN'], "l'ancien detecteur accepte Zin, comme prevu"
    assert nouveau == [], (
        "divergence documentee : le gabarit (dessine sans Zin) est plus strict ici")


# ── Lot 9c : diode + un seul passif (bris d'egalite sur la diode) ──

def test_parite_redresseur_simple_cas_simple():
    comps = [
        Component('D1', 'D', {'A': 'NET_AC', 'K': 'NET_MID'}, '1N4007'),
        Component('R1', 'R', {'1': 'NET_MID', '2': 'GND'}, '4k7'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_redresseur_simple(graphe)
    nouveau = _REDRESSEUR_SIMPLE.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['D1', 'R1']


def test_parite_redresseur_simple_ne_matche_pas_roue_libre():
    """Cathode sur alim (roue libre), pas un redresseur simple -- ni
    l'ancien detecteur ni le gabarit ne doivent matcher."""
    comps = [
        Component('D1', 'D', {'A': 'NET_COMMUT', 'K': 'VCC'}, '1N4007'),
        Component('R1', 'R', {'1': 'NET_COMMUT', '2': 'GND'}, '4k7'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_redresseur_simple(graphe)
    nouveau = _REDRESSEUR_SIMPLE.correspondre(graphe)
    assert ancien == [] and nouveau == []


def test_parite_detecteur_crete_cas_simple():
    comps = [
        Component('D1', 'D', {'A': 'NET_AC', 'K': 'NET_MID'}, '1N4148'),
        Component('C1', 'C', {'1': 'NET_MID', '2': 'GND'}, '100nF'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_detecteur_crete(graphe)
    nouveau = _DETECTEUR_CRETE.correspondre(graphe)
    assert _refs(ancien) == _refs(nouveau) == ['C1', 'D1']


def test_parite_detecteur_crete_ne_matche_pas_redresseur_simple():
    """R (pas C) sur la cathode -- structure du redresseur simple, pas du
    detecteur de crete -- ni l'un ni l'autre cote gabarit ne doit croiser."""
    comps = [
        Component('D1', 'D', {'A': 'NET_AC', 'K': 'NET_MID'}, '1N4148'),
        Component('R1', 'R', {'1': 'NET_MID', '2': 'GND'}, '4k7'),
    ]
    graphe = construire_graphe(comps)
    ancien = detecter_detecteur_crete(graphe)
    nouveau = _DETECTEUR_CRETE.correspondre(graphe)
    assert ancien == [] and nouveau == []
