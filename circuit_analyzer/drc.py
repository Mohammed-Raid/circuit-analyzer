"""
@file drc.py
@brief Vérificateur de règles de conception (Design Rule Check).

Analyse les résultats de détection et signale les violations courantes :
découplage manquant, diode de roue libre absente, résistance de base surdimensionnée, etc.

Numérotation des règles : saute volontairement de 3 à 6 — retrait
délibéré, pas un oubli :
  - Règle 4 « Pont diviseur déséquilibré » (commit `76535a2`) : devenue
    du code mort quand les détecteurs passifs nommés ont été remplacés
    par le moteur Z unique (`impedance.reduire`) — le `circuit_type`
    'Pont diviseur de tension' qu'elle testait n'est plus jamais émis.
  - Règle 5 « Filtre RC sans découplage » (commit `8fa4e91`) : retirée
    pour faux positifs constants (message du commit).
Ne pas réutiliser les numéros 4/5 pour de nouvelles règles : les commits
ci-dessus restent la référence si l'une des deux doit un jour être
réintroduite sous une forme adaptée au modèle Impédance Z.
"""
from circuit_analyzer.patterns.base import is_power
from circuit_analyzer.value_parser import parse_valeur


def verifier_drc(resultats, graphe) -> list[dict]:
    """@brief Vérifie les règles de conception sur les circuits détectés.

    @param resultats ResultatsAnalyse (sortie de match_patterns / analyser).
    @param graphe MultiGraph NetworkX du circuit.
    @return list[dict] Violations : {'rule', 'severity', 'message', 'refs'}.
    """
    violations = []
    composants = graphe.graph.get('components', {})

    a_fusible = any(comp.type == 'F' for comp in composants.values())
    a_vcc     = any(is_power(n) for n in graphe.nodes())

    for res in resultats:
        ct   = res.get('circuit_type', '')
        refs = res.get('components', [])
        sats = res.get('satellites', [])
        sat_roles = {s['role'] for s in sats}

        # ── Règle 1 : AOP sans condensateur de découplage ────────────────────
        if 'AOP' in ct or ct in (
            'Amplificateur inverseur (AOP)', 'Amplificateur non-inverseur (AOP)',
            'Suiveur de tension (AOP)', 'Intégrateur (AOP)', 'Dérivateur (AOP)',
            'Bascule de Schmitt (AOP)', 'Comparateur (AOP)',
            'Amplificateur différentiel (AOP)', 'Amplificateur sommateur (AOP)',
        ):
            if 'decoupling' not in sat_roles:
                violations.append({
                    'rule': 'AOP sans découplage',
                    'severity': 'warning',
                    'message': f"{ct} ({', '.join(refs)}) : aucun condensateur de découplage détecté sur les rails d'alimentation.",
                    'refs': refs,
                })

        # ── Règle 2 : Transistor en commutation sans diode de roue libre ─────
        if ct == 'Transistor en commutation':
            has_inductor = any(composants[r].type == 'L' for r in composants if r not in refs)
            if has_inductor and 'flyback' not in sat_roles:
                violations.append({
                    'rule': 'Diode de roue libre manquante',
                    'severity': 'warning',
                    'message': f"Transistor en commutation ({', '.join(refs)}) : charge inductive (L) présente mais aucune diode de roue libre détectée.",
                    'refs': refs,
                })

        # ── Règle 3 : Résistance de base BJT > 100 kΩ ───────────────────────
        if ct == 'Transistor en commutation':
            for ref in refs:
                comp = composants.get(ref)
                if comp and comp.type == 'R':
                    val = parse_valeur(comp.value or '')
                    if val is not None and val > 100_000:
                        violations.append({
                            'rule': 'Résistance de base surdimensionnée',
                            'severity': 'warning',
                            'message': f"{ref} ({comp.value}) : résistance de base > 100 kΩ, le transistor risque de rester bloqué.",
                            'refs': [ref],
                        })

    # ── Règle 6 : Aucun fusible sur le rail VCC (règle globale) ──────────────
    nb_comps_reels = sum(
        1 for comp in composants.values()
        if comp.type not in ('GND', 'VCC', 'PWR')
    )
    if a_vcc and not a_fusible and nb_comps_reels >= 8:
        violations.append({
            'rule': 'Fusible manquant',
            'severity': 'warning',
            'message': "Rail d'alimentation VCC présent dans le schéma mais aucun fusible (F) détecté.",
            'refs': [],
        })

    return violations
