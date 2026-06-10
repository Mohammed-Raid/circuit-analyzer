# Explication du logiciel — Comment les schémas sont détectés

---

## Vue d'ensemble : les 4 étapes

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   FICHIER NETLIST       GRAPHE ÉLECTRIQUE      DÉTECTION          RAPPORT │
│   (texte brut)      →   (carte des liens)  →  (comparaison)  →  (résultats) │
│                                                                         │
│   R1  NET1  GND         NET1 ──[R1]── GND      "Filtre RC ?"     R1 + C2 │
│   C2  NET1  GND          │──[C2]── GND          → OUI !          détectés │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## ÉTAPE 1 — Lire le fichier netlist

### Qu'est-ce qu'une netlist ?

Un fichier texte qui liste les composants et leurs connexions.
Chaque ligne = un composant.

```
# Exemple de fichier netlist (sample_circuit.txt)
#
# RÉFÉRENCE   NŒUD1    NŒUD2    [VALEUR]
#
R1            NET_IN   NET_MID  10k
C2            NET_MID  GND      100nF
R3            NET_MID  GND      47k
U1            VCC      GND      IN+  IN-  OUT
```

### Ce que le logiciel crée à partir de chaque ligne

```
"R1  NET_IN  NET_MID  10k"
         │
         ▼
Composant(
    ref   = 'R1'
    type  = 'R'          ← deviné à partir du préfixe "R"
    pins  = {'1': 'NET_IN', '2': 'NET_MID'}   ← connexions
    value = '10k'
)
```

### Tableau des types reconnus

```
┌──────┬────────────────────┬─────────────────────────────┐
│ Code │ Nom                │ Broches                     │
├──────┼────────────────────┼─────────────────────────────┤
│  R   │ Résistance         │ 1, 2                        │
│  C   │ Condensateur       │ 1, 2                        │
│  L   │ Inductance         │ 1, 2                        │
│  D   │ Diode              │ A (anode), K (cathode)      │
│  Q   │ Transistor BJT     │ B (base), C (collecteur),   │
│      │                    │ E (émetteur)                │
│  M   │ MOSFET             │ G (grille), D (drain),      │
│      │                    │ S (source)                  │
│  U   │ AOP / CI           │ IN+, IN-, OUT, V+, V-       │
│  K   │ Relais             │ A1, A2, 11, 12, 14          │
│  F   │ Fusible            │ 1, 2                        │
│  SW  │ Interrupteur       │ 1, 2                        │
└──────┴────────────────────┴─────────────────────────────┘
```

---

## ÉTAPE 2 — Construire le graphe

### Pourquoi un graphe ?

Un graphe permet de répondre instantanément à des questions comme :
- "Quels composants sont connectés à NET_MID ?"
- "Est-ce que R1 et C2 partagent un nœud ?"

Sans graphe → boucles imbriquées complexes.
Avec graphe → une seule ligne de code.

### Structure du graphe

```
               Nœuds = points électriques
               Arêtes = composants à 2 broches

    VCC                        GND
     │                          │
    [C_decoupl]                 │
     │                          │
  NET_IN ──────[R1]────── NET_MID ──────[C2]────── GND
                                │
                               [R3]
                                │
                               GND

                 ┌─────────────────────────────┐
                 │  U1 (AOP) stocké à part     │
                 │  car 5 broches, pas 2        │
                 │  → graph['components']['U1'] │
                 └─────────────────────────────┘
```

### Règle des 2 types de stockage

```
Composant à 2 broches (R, C, L, D, F)
    → Stocké comme une ARÊTE dans le graphe
    → On peut chercher "les voisins de NET_MID" directement

Composant à 3+ broches (Q, M, U, K)
    → Stocké dans un DICTIONNAIRE séparé
    → graphe.graph['components']['U1'] = Composant(...)
    → Car on ne peut pas représenter 5 connexions avec une simple arête
```

---

## ÉTAPE 3 — La détection des schémas

### Principe général : vérification de règles fixes (pas de l'IA)

#### Analogie du douanier

```
  UN DOUANIER avec une checklist            LE LOGICIEL avec ses règles
  ─────────────────────────────             ──────────────────────────

  GABARIT "Passeport valide" :              GABARIT "Filtre RC passe-bas" :
  ┌─────────────────────────────┐           ┌──────────────────────────────────┐
  │ □ Passeport non expiré ?    │           │ □ Y a-t-il une résistance R ?    │
  │ □ Visa présent ?            │           │ □ Y a-t-il un condensateur C ?   │
  │ □ Photo correspond ?        │           │ □ R et C partagent un nœud ?     │
  │ □ Destination autorisée ?   │           │ □ L'autre bout du C va à GND ?   │
  └─────────────────────────────┘           └──────────────────────────────────┘
         4 OUI → Vous passez !                     4 OUI → Filtre RC trouvé !
         1 NON → Refusé.                           1 NON → Ce n'en est pas un.
```

Le douanier ne *pense* pas, ne *devine* pas. Il vérifie case par case.
Le logiciel fait exactement la même chose : il vérifie des règles fixes.

#### La différence avec une IA

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                                                                     │
  │  UNE IA apprendrait sur des milliers d'exemples et dirait :        │
  │  "Ces connexions ressemblent à 87% à un filtre RC..."               │
  │  → Elle DEVINE avec une probabilité. Elle peut se tromper.         │
  │                                                                     │
  │  NOTRE LOGICIEL vérifie des règles écrites à la main :             │
  │  "Est-ce que R et C partagent un nœud avec C vers GND ?"           │
  │  → C'est OUI ou NON. Jamais "peut-être". Jamais d'erreur aléatoire.│
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘
```

#### Ce que ça donne dans le code

```python
# Gabarit pour "Filtre RC passe-bas" — 4 règles, c'est tout :

for noeud in graphe.nodes():
    resistances   = composants_de_type(graphe, noeud, 'R')   # Règle 1 : y a-t-il une R ?
    condensateurs = composants_de_type(graphe, noeud, 'C')   # Règle 2 : y a-t-il un C ?

    for ref_r, autre_r in resistances:
        for ref_c, autre_c in condensateurs:
            if est_masse(autre_c):                            # Règle 3+4 : C va à GND ?
                → FILTRE RC TROUVÉ  (R1 + C2)
```

#### Comparaison visuelle gabarit ↔ circuit réel

```
  GABARIT (règle écrite)          CIRCUIT RÉEL (dans le graphe)
  ──────────────────────          ──────────────────────────────

  IN ──[R]── MID ──[C]── GND      NET_IN ──[R1]── NET_MID ──[C2]── GND
        ↑         ↑                         ↑               ↑
   une R ici   un C vers GND          R1 ici          C2 vers GND

  Le logiciel superpose le gabarit sur le graphe.
  Si ça correspond → circuit détecté.
  Si ça ne correspond pas → on passe au schéma suivant.
```

---

## Schémas des 27 circuits détectés

### ── FAMILLE AOP (Amplificateur Opérationnel) ──

```
1. SUIVEUR DE TENSION
   (gain = 1, copie le signal sans le charger)

   IN ──── IN+
           [U1] ──── OUT
   OUT ─── IN-   ←── court-circuit (IN- = OUT, même nœud)


2. AMPLIFICATEUR INVERSEUR
   (la sortie est l'inverse de l'entrée, multipliée)

   IN ──[R_in]── IN- ──[R_fb]── OUT
                  │              │
                 [U1] ──── OUT ──┘
                  IN+ ─── GND ou référence

   Règle : 2 résistances sur IN-, l'une vient de l'entrée,
           l'autre relie la sortie à IN- (= contre-réaction)


3. AMPLIFICATEUR NON-INVERSEUR
   (la sortie est dans le même sens que l'entrée)

   IN ──── IN+
           [U1] ──── OUT ──[R_fb]──┐
   GND ─[R_gnd]── IN- ─────────────┘

   Règle : R de feedback (OUT→IN-) + R vers GND sur IN-


4. INTÉGRATEUR
   (la sortie = intégrale du signal d'entrée dans le temps)

   IN ──[R]── IN- ──[C]── OUT
               │           │
              [U1] ── OUT ─┘

   Règle : R d'entrée sur IN-  +  C de feedback (OUT→IN-)


5. DÉRIVATEUR
   (la sortie = dérivée du signal d'entrée dans le temps)

   IN ──[C]── IN- ──[R]── OUT
               │           │
              [U1] ── OUT ─┘

   Règle : C d'entrée sur IN-  +  R de feedback (OUT→IN-)


6. COMPARATEUR
   (la sortie bascule entre haut et bas selon IN+ vs IN-)

   IN1 ──── IN+
            [U1] ──── OUT   ← aucun composant entre OUT et les entrées
   IN2 ──── IN-

   Règle : AOP sans AUCUNE contre-réaction


7. BASCULE DE SCHMITT
   (comparateur avec hystérésis = évite les oscillations)

   IN ──── IN-
           [U1] ──── OUT ──[R]──┐
   REF ─── IN+ ────────────────┘  ← R relie OUT à IN+ (contre-réaction POSITIVE)

   Règle : R entre OUT et IN+ (pas IN-)


8. AMPLIFICATEUR DIFFÉRENTIEL
   (mesure la différence entre 2 signaux)

   IN1 ──[R1]── IN- ──[R2]── OUT
   IN2 ──[R3]── IN+ ──[R4]── GND

   Règle : 4 résistances en pont, 2 sur IN+ et 2 sur IN-


9. AMPLIFICATEUR SOMMATEUR
   (additionne plusieurs signaux d'entrée)

   IN1 ──[R1]──┐
   IN2 ──[R2]──┼── IN- ──[Rf]── OUT
   IN3 ──[R3]──┘       └── [U1] ──┘

   Règle : au moins 2 R d'entrée sur IN- + 1 R de feedback
```

---

### ── FAMILLE TRANSISTORS ──

```
10. TRANSISTOR BJT EN COMMUTATION
    (transistor = interrupteur commandé)

    VCC ──── Charge ──── Collecteur (C)
                         Transistor BJT (Q)
    CMD ──[R_base]────── Base (B)
                         Émetteur (E) ──── GND

    Règle : émetteur à GND  +  R sur la base


11. AMPLIFICATEUR ÉMETTEUR COMMUN
    (amplification de signal avec BJT)

    VCC ──[Rc]──── Collecteur (C)
                   Transistor BJT (Q)
    IN ──[Rb]───── Base (B)
                   Émetteur (E) ──── GND (ou dégenération)

    Règle : R sur le collecteur  +  R sur la base


12. MIROIR DE COURANT BJT
    (copie un courant de référence)

    VCC ──── C1    C2 ──── Charge
              Q1    Q2
              B ─────B   ← bases reliées ensemble
              E     E
              │     │
             GND   GND

    Règle : 2 BJT, mêmes bases, 2 émetteurs à GND


13. MOSFET EN COMMUTATION (côté bas)
    (interrupteur de puissance, source à GND)

    VCC ──── Charge ──── Drain (D)
                         MOSFET (M)
    CMD ──[R_grille]─── Grille (G)
                         Source (S) ──── GND

    Règle : source à GND  +  R sur la grille


14. MOSFET HAUTE-TENSION (côté haut)
    (commute depuis le rail positif)

    VCC ──── Drain (D)
             MOSFET (M)
    CMD ─── Grille (G)
             Source (S) ──── Charge ──── GND

    Règle : drain sur alimentation  +  source NON à GND
```

---

### ── FAMILLE DIODES ──

```
15. PONT REDRESSEUR DE GRAETZ
    (convertit courant alternatif → continu)

          AC+ ──[D1]── DC+
           │                │
          [D4]            [D2]
           │                │
          AC- ──[D3]── DC-

    Règle : cycle fermé de 4 diodes (chercher un carré dans le graphe)


16. DIODE DE ROUE LIBRE
    (protège les transistors contre les surtensions des charges inductives)

    VCC ─── Cathode(K) ──[D]── Anode(A) ─── nœud de commutation

    Règle : cathode sur alimentation + anode sur nœud non-alimentation


17. DIODE DE PROTECTION ESD
    (protège contre les décharges électrostatiques)

    Signal ──[D]── GND   (ou GND──[D]──Signal)

    Règle : une broche de la diode est à la masse


18. REDRESSEUR SIMPLE ALTERNANCE
    (forme la plus basique de redressement)

    AC ──[D]── nœud ──[R_charge]── GND

    Règle : diode en série + R vers GND sur la cathode


19. DÉTECTEUR DE CRÊTE
    (mémorise le maximum d'un signal)

    AC ──[D]── nœud ──[C]── GND

    Règle : diode en série + C vers GND sur la cathode
```

---

### ── FAMILLE PASSIFS ──

```
20. CONDENSATEUR DE DÉCOUPLAGE
    (filtre les parasites sur l'alimentation)

    VCC ──[C]── GND   ← directement entre alim et masse, sans R

    Règle : C entre alimentation et GND, sans R en parallèle


21. FILTRE RC PASSE-BAS
    (laisse passer les basses fréquences)

    IN ──[R]── MID ──[C]── GND
          (serie)    (vers masse)

    Règle : R en série + C vers GND sur le nœud commun MID


22. FILTRE RC PASSE-HAUT
    (laisse passer les hautes fréquences)

    IN ──[C]── MID ──[R]── GND
          (serie)    (vers masse)

    Règle : C en série + R vers GND sur le nœud commun MID


23. FILTRE LC
    (filtre de sortie pour alimentations à découpage)

    IN ──[L]── MID ──[C]── GND

    Règle : inductance en série + C vers GND


24. ABSORBEUR RC (snubber)
    (absorbe les surtensions transitoires)

    A ──[R]── B   ← R et C entre les MÊMES deux nœuds
    A ──[C]── B     (en parallèle)

    Règle : R et C en parallèle entre les mêmes nœuds


25. PONT DIVISEUR DE TENSION
    (crée une tension intermédiaire)

    VCC ──[R1]── MID ──[R2]── GND

    Règle : 2 R connectées au même nœud MID,
            chacune allant vers un point différent


26. PROTECTION PAR FUSIBLE
    (coupe le circuit en cas de surintensité)

    ENTRÉE ──[F]── SORTIE

    Règle : composant de type F présent dans le circuit


27. COMMANDE DE RELAIS
    (transistor qui commute une bobine de relais)

    VCC ──[bobine K]── Collecteur/Drain
                       Transistor (Q ou M)
    CMD ────────────── Base/Grille
                       Émetteur/Source ──── GND

    Règle : relais K + transistor, collecteur/drain relié à la bobine
```

---

## ÉTAPE 3b — Est-ce qu'on pose toutes les questions à chaque fois ?

### Réponse courte : oui, mais chaque question est quasi-instantanée

Chaque détecteur commence toujours par une question de filtrage rapide.
Si la réponse est NON, il s'arrête immédiatement sans aller plus loin.

```
CIRCUIT EXEMPLE : R1, C2, R3, U1   (pas de transistor, pas de MOSFET)

Détecteur 1  "Ampli inverseur"     → cherche un U  → U1 trouvé → pose 3 sous-questions
Détecteur 2  "Ampli non-inv."      → cherche un U  → U1 trouvé → pose 3 sous-questions
Détecteur 3  "Suiveur de tension"  → cherche un U  → U1 trouvé → 1 question → STOP
Détecteur 4  "Transistor BJT"      → cherche un Q  → 0 trouvé  → ████ STOP immédiat
Détecteur 5  "MOSFET"              → cherche un M  → 0 trouvé  → ████ STOP immédiat
Détecteur 6  "Miroir courant"      → cherche 2 Q   → 0 trouvé  → ████ STOP immédiat
Détecteur 7  "Filtre RC passe-bas" → cherche R+C   → R1+C2 ok  → 2 questions → TROUVÉ
...
```

### Pourquoi c'est rapide malgré 27 détecteurs

```
┌───────────────────────────────────────────────────────────────────┐
│                                                                   │
│  Circuit de 20 composants  →  analyse complète < 0.01 seconde    │
│  162 tests d'un coup       →  < 10 secondes au total             │
│                                                                   │
│  Raison : la première question de chaque détecteur               │
│  ("y a-t-il un U / Q / M ?") élimine immédiatement              │
│  tous les détecteurs qui ne concernent pas ce circuit.           │
│                                                                   │
│  Si pas de transistor dans le circuit  →  les 6 détecteurs       │
│  transistors sont sautés en 6 × 0.00001 seconde.                 │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Comparaison avec un agent de sécurité

```
  AGENT DE SÉCURITÉ                    LOGICIEL

  "Êtes-vous sur la liste VIP ?"       "Y a-t-il un AOP (U) ?"
       → NON  →  stop, suivant              → NON → stop, détecteur suivant
       → OUI  →  vérifie les détails        → OUI → pose les sous-questions

  L'agent ne demande pas votre passeport   Le logiciel ne cherche pas les R, C
  si vous n'êtes pas sur la liste.         si l'AOP n'est même pas là.
```

---

## ÉTAPE 4 — La règle anti-"vol" (priorité)

```
PROBLÈME : Une résistance peut appartenir à PLUSIEURS schémas à la fois.
           Exemple : la R de feedback d'un AOP pourrait aussi être
           détectée comme faisant partie d'un pont diviseur.

SOLUTION : Ordre de priorité + liste des "composants déjà pris"

┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  PRIORITÉ 1 : Circuits complexes                               │
│    AOP (9 types), transistors (4 types), diodes spécialisées   │
│                        ↓                                        │
│  PRIORITÉ 2 : Circuits personnalisés (définis par l'utilisateur)│
│                        ↓                                        │
│  PRIORITÉ 3 : Circuits simples (passifs R, C, L seuls/paires)  │
│                                                                 │
│  Une fois qu'un composant est attribué → il est VERROUILLÉ.    │
│  Les détecteurs suivants l'ignorent.                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Exemple :
  R1, R2, U1 → Amplificateur inverseur détecté en PRIORITÉ 1
              → R1 et R2 sont verrouillés
              → Le détecteur "Pont diviseur" passera sur R1 et R2
                mais les ignorera car déjà utilisés
```

---

## Résumé visuel complet

```
                    ┌──────────────────────────────────┐
                    │         FICHIER NETLIST           │
                    │   R1 NET_IN NET_MID               │
                    │   C2 NET_MID GND                  │
                    │   U1 VCC GND IN+ IN- OUT          │
                    └────────────┬─────────────────────┘
                                 │  lire_netlist()
                                 ▼
                    ┌──────────────────────────────────┐
                    │       LISTE DE COMPOSANTS         │
                    │  [Composant(R1, R, ...), ...]     │
                    └────────────┬─────────────────────┘
                                 │  construire_graphe()
                                 ▼
                    ┌──────────────────────────────────┐
                    │         GRAPHE NETWORKX           │
                    │  Nœuds : NET_IN, NET_MID, GND... │
                    │  Arêtes : R1, C2...              │
                    │  graph['components'] : U1...     │
                    └────────────┬─────────────────────┘
                                 │  analyser()
                                 ▼
              ┌──────────────────────────────────────────────┐
              │              27 FONCTIONS DE DÉTECTION        │
              │                                              │
              │  detecter_amplificateur_inverseur()          │
              │  detecter_filtre_rc_passe_bas()              │
              │  detecter_pont_redresseur()                  │
              │  ... (27 fonctions au total)                 │
              │                                              │
              │  Chaque fonction pose des questions sur      │
              │  la TOPOLOGIE du graphe (qui est connecté   │
              │  à quoi) et retourne les circuits trouvés.  │
              └─────────────────┬────────────────────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────────────┐
                    │           RÉSULTATS               │
                    │  [                                │
                    │    {                              │
                    │      'circuit_type': 'Filtre RC', │
                    │      'components': ['R1', 'C2'],  │
                    │      'nodes': ['NET_IN', 'GND']   │
                    │    },                             │
                    │    ...                            │
                    │  ]                                │
                    └──────────────────────────────────┘
```

---

## Fichiers clés du projet

```
circuit_analyzer/
├── composant.py   ← Étape 1 & 2 : lire la netlist + construire le graphe
├── detecteur.py   ← Étape 3 : les 27 fonctions de détection
├── rapport.py     ← Étape 4 : formater et écrire les résultats
└── xml.py         ← Bonus : générer le schéma visuel au format XML
```
