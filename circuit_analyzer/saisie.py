"""@file saisie.py
@brief Modèle PUR de l'onglet Saisie (spec 2026-07-15 §3.2) : tableau
netlist en mémoire (refs auto, validation, nets connus) et conversions
lignes ↔ Composant. AUCUN import graphique (testé en subprocess).
"""
import re
from collections import Counter
from dataclasses import dataclass, field

from circuit_analyzer.catalogue import identifier
from circuit_analyzer.composant import Composant, charger_bibliotheque

RAILS = ("VIN", "VOUT", "VCC", "GND")
_NET_AUTO = re.compile(r"NET\d+$")


@dataclass
class LigneSaisie:
    """@brief Une ligne du tableau : un composant en cours de saisie.

    pins : nom de broche -> net ("" = non câblée) ; l'ORDRE des clés est
    l'ordre d'affichage. fonctions : nom -> rôle indicatif catalogue
    ("" si aucun), ex. "2" -> "TRIG" pour un NE555.
    """
    ref: str
    type: str
    value: str = ""
    pins: dict = field(default_factory=dict)
    fonctions: dict = field(default_factory=dict)


class ModeleSaisie:
    """@brief État du tableau + opérations. L'onglet Tk ne calcule rien."""

    def __init__(self):
        self.lignes = []
        self._bibliotheque = charger_bibliotheque()

    def ref_auto(self, type_):
        """@brief Premier index libre pour le préfixe du type (R1, R2, U1…)."""
        pris = {l.ref for l in self.lignes}
        i = 1
        while f"{type_}{i}" in pris:
            i += 1
        return f"{type_}{i}"

    def _broches_du_type(self, type_):
        info = self._bibliotheque.get(type_) or {}
        return list(info.get("pins") or ("1", "2"))

    def ajouter(self, type_, value="", pins=None, fonctions=None):
        """@brief Ajoute une ligne ; broches du type si `pins` absent."""
        if pins is None:
            pins = {p: "" for p in self._broches_du_type(type_)}
        ligne = LigneSaisie(ref=self.ref_auto(type_), type=type_,
                            value=value, pins=dict(pins),
                            fonctions=dict(fonctions or {}))
        self.lignes.append(ligne)
        return ligne

    def ajouter_catalogue(self, type_, value):
        """@brief Ligne pré-remplie depuis le catalogue constructeur.

        U : broches NUMÉROTÉES du boîtier + fonctions indicatives (le flux
        réel : l'aliasing/identification existants s'appliquent à
        l'analyse). Q/M/D : broches du TYPE (B/C/E, G/D/S, A/K).
        """
        entree = identifier(type_, value) or {}
        broches = entree.get("broches")
        if type_ == "U" and broches:
            pins = {num: "" for num in sorted(broches, key=int)}
            fonctions = {num: broches[num] for num in pins}
            return self.ajouter(type_, value, pins, fonctions)
        return self.ajouter(type_, value)

    def supprimer(self, index):
        del self.lignes[index]

    def nets_connus(self):
        """@brief Rails d'abord (ordre fixe), puis nets saisis triés."""
        vus = {n for l in self.lignes for n in l.pins.values() if n}
        return list(RAILS) + sorted(vus - set(RAILS))

    def valider(self):
        """@brief (bloquants, avertissements) — spec §2.5."""
        bloquants, avertissements = [], []
        refs = [l.ref for l in self.lignes]
        for ref, n in Counter(refs).items():
            if not ref:
                bloquants.append("Une ligne n'a pas de référence.")
            elif n > 1:
                bloquants.append(f"Référence en double : {ref}.")
        for l in self.lignes:
            if not l.type:
                bloquants.append(f"{l.ref or '(sans ref)'} : type manquant.")
        compte_nets = Counter(n for l in self.lignes
                              for n in l.pins.values() if n)
        for net, n in sorted(compte_nets.items()):
            if n == 1 and net not in RAILS:
                avertissements.append(
                    f"Le net {net} n'apparaît qu'une fois.")
        if not self.lignes:
            avertissements.append("Aucun composant saisi.")
        return bloquants, avertissements

    def vers_composants(self):
        """@brief Composants prêts pour generer_xml (broches vides EXCLUES :
        generer_xml leur crée un net singleton NET#, convention existante)."""
        return [Composant(ref=l.ref, type=l.type, value=l.value,
                          pins={p: n for p, n in l.pins.items() if n})
                for l in self.lignes]

    @classmethod
    def depuis_composants(cls, comps):
        """@brief Reconstruit le tableau depuis des Composant lus (lecture
        BRUTE conseillée : lire_xml(..., alias_catalogue=False)).

        Les nets auto NET# singletons (broches non câblées à la génération)
        sont RE-MASQUÉS en champs vides ; les fonctions indicatives sont
        re-dérivées du catalogue quand la valeur est identifiée.
        """
        m = cls()
        compte = Counter(n for c in comps for n in c.pins.values() if n)
        for c in comps:
            pins = {}
            for p, net in c.pins.items():
                cache = bool(net) and _NET_AUTO.match(net) and compte[net] == 1
                pins[p] = "" if cache else (net or "")
            entree = identifier(getattr(c, "type", ""),
                                getattr(c, "value", "")) or {}
            broches = entree.get("broches") or {}
            fonctions = {p: broches.get(p, "") for p in pins}
            ligne = LigneSaisie(ref=c.ref, type=c.type,
                                value=getattr(c, "value", "") or "",
                                pins=pins, fonctions=fonctions)
            m.lignes.append(ligne)
        return m
