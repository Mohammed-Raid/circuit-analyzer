"""
@file descriptions.py
@brief Description courte de chaque circuit intégré, affichée dans la fiche
       lecture seule de l'onglet Circuits.

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
    "Ampli inverseur + boost HF (AOP)":
        "Variante inverseuse avec Zin = R//C. Le gain reste fini en continu "
        "et augmente aux hautes frÃ©quences.",
    "Ampli inverseur + action intégrale (AOP)":
        "Variante inverseuse avec Zf = R+C en sÃ©rie. Le comportement ajoute "
        "une action intÃ©grale aux basses frÃ©quences.",
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
    "Collecteur commun (suiveur d'émetteur)":
        "Recopie la tension de base sur l'émetteur (gain ~1, forte "
        "impédance d'entrée). Collecteur sur le rail, charge sur l'émetteur.",
    "Étage push-pull":
        "Étage de sortie classe B/AB : un NPN et un PNP aux émetteurs "
        "communs se partagent les alternances du signal.",
    "Paire Darlington":
        "Deux BJT en cascade (émetteur de Q1 sur la base de Q2) : gain en "
        "courant composé, se comporte comme un seul transistor.",
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
    "Impédance Z":
        "Dipôle passif équivalent : R/L/C combinés en série puis en "
        "parallèle (la composition détaille les éléments d'origine).",
}
