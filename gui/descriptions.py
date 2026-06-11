"""
descriptions.py — Description courte de chaque circuit intégré, affichée dans
la fiche lecture seule de l'onglet Circuits.

Le test tests/test_descriptions.py vérifie que chaque nom de NOMS_CIRCUITS
a sa description : ajouter un détecteur impose d'ajouter une entrée ici.
"""

DESCRIPTIONS_CIRCUITS = {
    "Amplificateur différentiel (AOP)":
        "Amplifie la différence entre deux signaux. Pont de 4 résistances "
        "autour de l'AOP (entrées IN+ et IN-).",
    "Amplificateur sommateur (AOP)":
        "Additionne plusieurs signaux d'entrée. Plusieurs résistances "
        "d'entrée convergent vers IN-.",
    "Intégrateur (AOP)":
        "Sortie proportionnelle à l'intégrale du signal. Résistance en "
        "entrée, condensateur en contre-réaction.",
    "Dérivateur (AOP)":
        "Sortie proportionnelle à la variation du signal. Condensateur en "
        "entrée, résistance en contre-réaction.",
    "Bascule de Schmitt (AOP)":
        "Comparateur à hystérésis (seuils haut/bas distincts). "
        "Contre-réaction positive via résistance vers IN+.",
    "Amplificateur non-inverseur (AOP)":
        "Amplifie sans inverser le signal. Résistance de contre-réaction + "
        "résistance vers GND sur IN-.",
    "Amplificateur inverseur (AOP)":
        "Amplifie en inversant le signal. Résistance d'entrée et résistance "
        "de contre-réaction sur IN-.",
    "Suiveur de tension (AOP)":
        "Recopie la tension d'entrée (gain 1) en isolant la source. "
        "Sortie directement reliée à IN-.",
    "Comparateur (AOP)":
        "Compare deux tensions, sortie tout-ou-rien. AOP sans "
        "contre-réaction (boucle ouverte).",
    "Miroir de courant BJT":
        "Copie un courant de référence vers une charge. Deux transistors "
        "avec bases communes et émetteurs à GND.",
    "Commande de relais":
        "Un transistor pilote la bobine d'un relais. Souvent accompagné "
        "d'une diode de roue libre.",
    "Amplificateur émetteur commun":
        "Étage d'amplification BJT classique. Résistance de collecteur + "
        "résistance de polarisation de base.",
    "Transistor en commutation":
        "Le BJT fonctionne en interrupteur. Émetteur à GND, résistance de "
        "commande sur la base.",
    "MOSFET en commutation":
        "Le MOSFET fonctionne en interrupteur (côté bas). Source à GND, "
        "résistance sur la grille.",
    "MOSFET haute-tension (côté haut)":
        "MOSFET commutant le rail d'alimentation (côté haut). Drain sur "
        "l'alimentation, source vers la charge.",
    "Pont redresseur (Graetz)":
        "Redresse les deux alternances du secteur. Cycle fermé de "
        "4 diodes.",
    "Diode de roue libre":
        "Absorbe la surtension à la coupure d'une charge inductive. "
        "Cathode sur le rail d'alimentation.",
    "Diode de protection ESD":
        "Protège une entrée contre les décharges électrostatiques. "
        "Une broche reliée à GND.",
    "Redresseur simple alternance":
        "Ne laisse passer qu'une alternance. Diode en série + résistance "
        "de charge vers GND.",
    "Détecteur de crête":
        "Mémorise la tension maximale du signal. Diode en série + "
        "condensateur vers GND.",
    "Condensateur de découplage":
        "Stabilise l'alimentation près d'un composant. Condensateur "
        "directement entre alimentation et GND.",
    "Filtre RC passe-bas":
        "Atténue les hautes fréquences. Résistance en série + condensateur "
        "vers GND.",
    "Filtre RC passe-haut":
        "Atténue les basses fréquences. Condensateur en série + résistance "
        "vers GND.",
    "Filtre LC":
        "Filtre de puissance (alimentations à découpage). Inductance en "
        "série + condensateur vers GND.",
    "Absorbeur RC":
        "Snubber : absorbe les surtensions transitoires. Résistance et "
        "condensateur en parallèle.",
    "Pont diviseur de tension":
        "Crée une tension intermédiaire. Deux résistances en série, point "
        "milieu sur un nœud signal.",
    "Protection par fusible":
        "Coupe le circuit en cas de surintensité. Composant de type F en "
        "série.",
}
