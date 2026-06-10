"""
satellites.py — Rattachement des composants satellites aux circuits détectés.

Après la détection des 27 patterns, deux phases :
  Phase 1 : les circuits annexes mono-composant (roue libre, découplage, ESD)
            adjacents à un circuit multi-composants sont absorbés comme satellites.
  Phase 2 : les composants restés non classifiés sont examinés ; ceux qui touchent
            un circuit détecté reçoivent un rôle et un score de rattachement.

Chaque satellite porte un statut calculé une seule fois :
  score >= SEUIL_SUR                  -> status 'sure'     (verrouillé, exporté dans le bloc XML)
  SEUIL_POSSIBLE <= score < SEUIL_SUR -> status 'possible' (affiché à part, jamais exporté)

Format d'un satellite :
    {'ref': 'R2', 'role': 'pull-down', 'score': 0.9, 'status': 'sure',
     'reason': 'R 10k entre NET_BASE et GND'}
"""
from circuit_analyzer.patterns.base import (
    is_ground_net, is_power_net, is_protective_earth_net,
)
from circuit_analyzer.value_parser import (
    parse_valeur, classifier_resistance, classifier_condensateur,
)

SEUIL_SUR      = 0.6
SEUIL_POSSIBLE = 0.3


def _est_rail(net) -> bool:
    """Vrai si le net est une masse, une alimentation ou une terre de protection."""
    if not net:
        return False
    return is_ground_net(net) or is_power_net(net) or is_protective_earth_net(net)


def _noeuds_internes(match: dict) -> set:
    """Nœuds du circuit qui ne sont ni GND, ni alim, ni PE (= nœuds signal)."""
    return {n for n in match.get('nodes', []) if n and not _est_rail(n)}


def _rails_alim(match: dict) -> set:
    """Rails d'alimentation effectivement présents dans les nœuds du circuit."""
    return {n for n in match.get('nodes', []) if n and is_power_net(n)}


def _evaluer(comp, internes: set, rails: set):
    """
    Évalue le rôle d'un composant candidat vis-à-vis d'un circuit.

    Arguments :
        comp     : Composant (.type, .pins, .value)
        internes : nœuds signal du circuit
        rails    : rails d'alimentation du circuit

    Retourne (role, score, reason) ou None si le composant ne touche pas le circuit.
    Les chaînes reason restent compatibles cp1252 (console Windows).
    """
    nets = [n for n in comp.pins.values() if n]
    touche_interne = [n for n in nets if n in internes]

    # ── Découplage / bulk : C entre un rail d'alim du circuit et GND ─────────
    # Seul rôle qui ne passe pas par un nœud interne : un découplage vit
    # par définition entre rails, mais doit toucher le rail utilisé par le circuit.
    if comp.type == 'C' and len(nets) == 2:
        rail = next((n for n in nets if n in rails), None)
        if rail:
            autre = nets[1] if nets[0] == rail else nets[0]
            if is_ground_net(autre):
                classe = classifier_condensateur(comp.value, entre_power_gnd=True)
                if classe == 'decoupling':
                    return ('decoupling', 0.9, f"C {comp.value} entre {rail} et {autre}")
                if classe == 'bulk_filter':
                    return ('bulk', 0.8, f"C {comp.value} entre {rail} et {autre}")
                return ('decoupling', 0.7, f"C entre {rail} et {autre} (valeur inconnue)")

    if not touche_interne:
        return None
    noeud = touche_interne[0]

    # ── Résistances : pull-up / pull-down / série ─────────────────────────────
    if comp.type == 'R' and len(nets) == 2:
        autre = nets[1] if nets[0] == noeud else nets[0]
        if is_ground_net(autre) or is_power_net(autre):
            role = 'pull-down' if is_ground_net(autre) else 'pull-up'
            classe = classifier_resistance(comp.value)
            if classe == 'pull':
                return (role, 0.9, f"R {comp.value} entre {noeud} et {autre}")
            if classe == 'unknown':
                return (role, 0.7, f"R entre {noeud} et {autre} (valeur inconnue)")
            return ('unknown-neighbor', 0.4,
                    f"R {comp.value} entre {noeud} et {autre} (trop faible pour un pull)")
        if not _est_rail(autre):
            # R série : score plein uniquement si la valeur est typique (1 ohm - 1k)
            v = parse_valeur(comp.value)
            score = 0.7 if (v is not None and 1.0 <= v <= 1000.0) else 0.55
            return ('series-r', score, f"R en série sur {noeud} (vers {autre})")

    # ── Diode de roue libre : anode sur nœud interne, cathode sur rail ───────
    if comp.type == 'D':
        anode, cathode = comp.pins.get('A'), comp.pins.get('K')
        if anode in internes and cathode and is_power_net(cathode):
            return ('flyback', 0.85, f"D anode sur {anode}, cathode sur {cathode}")

    # ── Voisin direct sans rôle identifié ─────────────────────────────────────
    return ('unknown-neighbor', 0.4, f"adjacent à {noeud}, rôle non identifié")


def _ajouter_satellite(match: dict, ref: str, role: str, score: float, reason: str) -> None:
    """Ajoute un satellite au match avec son statut, et le warning si « possible »."""
    status = 'sure' if score >= SEUIL_SUR else 'possible'
    match['satellites'].append(
        {'ref': ref, 'role': role, 'score': score, 'status': status, 'reason': reason}
    )
    if status == 'possible':
        match.setdefault('warnings', []).append(
            f"{ref} : rattachement possible uniquement, validation ingénieur nécessaire"
        )


def rattacher_satellites(circuits: list, graphe, composants_utilises: set) -> None:
    """
    Rattache les composants non classifiés aux circuits détectés.

    Mute les matches en place : chaque match reçoit une clé 'satellites'
    (liste, toujours présente). Les satellites sûrs (status 'sure') sont
    ajoutés à composants_utilises ; les « possibles » restent libres.

    Conflit (un candidat éligible pour plusieurs circuits) : rattaché au
    meilleur score de rôle ; à égalité, au circuit avec la meilleure confidence.
    """
    for m in circuits:
        m.setdefault('satellites', [])

    infos = [(m, _noeuds_internes(m), _rails_alim(m)) for m in circuits]
    tous = graphe.graph.get('components', {})

    for ref, comp in tous.items():
        if ref in composants_utilises:
            continue
        meilleur = None   # (cle_de_tri, match, role, score, reason)
        for m, internes, rails in infos:
            resultat = _evaluer(comp, internes, rails)
            if resultat is None:
                continue
            role, score, reason = resultat
            cle = (score, m.get('confidence', 0))
            if meilleur is None or cle > meilleur[0]:
                meilleur = (cle, m, role, score, reason)
        if meilleur is None:
            continue
        _, m, role, score, reason = meilleur
        if score < SEUIL_POSSIBLE:
            continue
        _ajouter_satellite(m, ref, role, score, reason)
        if score >= SEUIL_SUR:
            composants_utilises.add(ref)
