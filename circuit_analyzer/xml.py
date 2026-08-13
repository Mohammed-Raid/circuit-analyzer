"""
@file xml.py
@brief Lecture et génération de schémas BoardSCH au format XML.

Ce fichier regroupe deux fonctions principales :
  - lire_xml(chemin)              : lit un fichier .xml BoardSCH → liste de Composant
  - generer_xml(composants, ...)  : liste de Composant → fichier .xml BoardSCH

Les noms anglais (parse_xml, components_to_xml) sont gardés comme alias
pour ne pas casser le reste du code.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from dataclasses import dataclass, field
from html import escape as _esc

from circuit_analyzer import eretro, eretro_lib, eretro_symboles
from circuit_analyzer.composant import Composant as Component
from circuit_analyzer.patterns.base import (
    is_gnd,
    is_power,
    is_protective_earth_net,
)
from gui.schematic_symbols import aimanter_bord, etendue_primitives, geometrie_reelle

# =============================================================================
# FORMES VISUELLES DES COMPOSANTS (coordonnées relatives au centre)
# =============================================================================
# Toutes les coordonnées sont en unités BoardSCH, centrées sur (0,0).
# Source : reverse-engineered depuis "exemples/carte pour tester.xml" du logiciel ERetroDesign.

_log = logging.getLogger(__name__)

# Pas de grille pour l'aimantation des broches catalogue sur leur boite
# (revue finale round 2, Critical 2 sous-point manque) -- meme valeur que
# `GRID`/`GRILLE` ailleurs dans le projet (gui/schematic_editor.py,
# gui/pin_canvas.py, circuit_analyzer/eretro_lib.py), dupliquee localement
# ici comme sur ces autres sites (pas de source commune existante).
_GRILLE = 20

_FORME: dict[str, dict] = {
    "Résistance": {
        "pins": {"1": (80, 0, 1), "2": (-80, 0, 0)},
        "polygon": """
        <DataPolygon><point><X>45</X><Y>-22</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-45</X><Y>-22</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-45</X><Y>-2</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-80</X><Y>-2</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-80</X><Y>2</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-45</X><Y>2</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-45</X><Y>22</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>45</X><Y>22</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>45</X><Y>2</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>80</X><Y>2</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>80</X><Y>-2</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>45</X><Y>-2</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>""",
        "segment": "",
    },
    "Capa": {
        "pins": {"+": (48, 0, 1), "-": (-48, 0, 0)},
        "polygon": """
        <DataPolygon><point><X>-6</X><Y>-48</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>0</X><Y>-48</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>0</X><Y>48</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-6</X><Y>48</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>""",
        "segment": """
        <DataSegment><Spoint><X>6</X><Y>-48</Y></Spoint><Epoint><X>6</X><Y>48</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-6</X><Y>0</Y></Spoint><Epoint><X>-48</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>6</X><Y>0</Y></Spoint><Epoint><X>48</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
    "AOP": {
        "pins": {"+": (-72, -24, 0), "-": (-72, 24, 1), "s": (72, 0, 2)},
        "polygon": """
        <DataPolygon><point><X>48</X><Y>0</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-48</X><Y>-48</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-48</X><Y>48</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>""",
        "segment": """
        <DataSegment><Spoint><X>48</X><Y>0</Y></Spoint><Epoint><X>72</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-48</X><Y>-24</Y></Spoint><Epoint><X>-72</X><Y>-24</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-48</X><Y>24</Y></Spoint><Epoint><X>-72</X><Y>24</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
    "Transistor": {
        "pins": {"B": (-80, 0, 0), "C": (40, -50, 1), "E": (40, 50, 2)},
        "polygon": "",
        "segment": """
        <DataSegment><Spoint><X>0</X><Y>-30</Y></Spoint><Epoint><X>0</X><Y>30</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-80</X><Y>0</Y></Spoint><Epoint><X>0</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>0</X><Y>-15</Y></Spoint><Epoint><X>40</X><Y>-50</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>0</X><Y>15</Y></Spoint><Epoint><X>40</X><Y>50</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
    # 2N2B : transistor BJT NPN — géométrie issue de Lib.xml ERetroDesign.
    # Ordre des pins IMPOSÉ par la bibliothèque : G(base)=0, E(émetteur)=1, C(collecteur)=2.
    "2N2B": {
        "pins": {"G": (-36, 0, 0), "E": (36, 48, 1), "C": (36, -48, 2)},
        "polygon": "",
        "segment": """
        <DataSegment><Spoint><X>4</X><Y>48</Y></Spoint><Epoint><X>4</X><Y>-48</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>4</X><Y>-16</Y></Spoint><Epoint><X>36</X><Y>-48</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>4</X><Y>16</Y></Spoint><Epoint><X>36</X><Y>48</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>4</X><Y>0</Y></Spoint><Epoint><X>-36</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>19</X><Y>-31</Y></Spoint><Epoint><X>27</X><Y>-33</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>19</X><Y>-31</Y></Spoint><Epoint><X>22</X><Y>-38</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
    "MOSFET": {
        "pins": {"G": (-80, 0, 0), "D": (40, -60, 1), "S": (40, 60, 2)},
        "polygon": "",
        "segment": """
        <DataSegment><Spoint><X>0</X><Y>-40</Y></Spoint><Epoint><X>0</X><Y>40</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-80</X><Y>0</Y></Spoint><Epoint><X>-10</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>10</X><Y>-20</Y></Spoint><Epoint><X>10</X><Y>20</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>10</X><Y>-20</Y></Spoint><Epoint><X>40</X><Y>-60</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>10</X><Y>20</Y></Spoint><Epoint><X>40</X><Y>60</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
    "Diode": {
        "pins": {"A": (-80, 0, 0), "K": (80, 0, 1)},
        "polygon": "",
        "segment": """
        <DataSegment><Spoint><X>-80</X><Y>0</Y></Spoint><Epoint><X>0</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>0</X><Y>-30</Y></Spoint><Epoint><X>0</X><Y>30</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>0</X><Y>-30</Y></Spoint><Epoint><X>40</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>0</X><Y>30</Y></Spoint><Epoint><X>40</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>40</X><Y>-30</Y></Spoint><Epoint><X>40</X><Y>30</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>40</X><Y>0</Y></Spoint><Epoint><X>80</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
    "Fusible": {
        "pins": {"1": (-80, 0, 0), "2": (80, 0, 1)},
        "polygon": "",
        "segment": """
        <DataSegment><Spoint><X>-80</X><Y>0</Y></Spoint><Epoint><X>-40</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-40</X><Y>-15</Y></Spoint><Epoint><X>40</X><Y>-15</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-40</X><Y>15</Y></Spoint><Epoint><X>40</X><Y>15</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-40</X><Y>-15</Y></Spoint><Epoint><X>-40</X><Y>15</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>40</X><Y>-15</Y></Spoint><Epoint><X>40</X><Y>15</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>40</X><Y>0</Y></Spoint><Epoint><X>80</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
    "GND": {
        "pins": {"GND": (0, -48, 0)},
        "polygon": "",
        "segment": """
        <DataSegment><Spoint><X>-72</X><Y>-12</Y></Spoint><Epoint><X>72</X><Y>-12</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-60</X><Y>0</Y></Spoint><Epoint><X>60</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-48</X><Y>12</Y></Spoint><Epoint><X>48</X><Y>12</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>0</X><Y>-48</Y></Spoint><Epoint><X>0</X><Y>-12</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
    "AGND": {
        "pins": {"GND": (0, -48, 0)},
        "polygon": "",
        "segment": """
        <DataSegment><Spoint><X>-72</X><Y>-12</Y></Spoint><Epoint><X>72</X><Y>-12</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-60</X><Y>0</Y></Spoint><Epoint><X>60</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>0</X><Y>-48</Y></Spoint><Epoint><X>0</X><Y>-12</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
    "VCC": {
        "pins": {"VCC": (0, 48, 0)},
        "polygon": "",
        "segment": """
        <DataSegment><Spoint><X>-60</X><Y>24</Y></Spoint><Epoint><X>60</X><Y>24</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>0</X><Y>48</Y></Spoint><Epoint><X>0</X><Y>24</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-40</X><Y>8</Y></Spoint><Epoint><X>40</X><Y>8</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
    "Vss": {
        "pins": {"VCC": (0, 32, 0)},
        "polygon": """
        <DataPolygon><point><X>-80</X><Y>-32</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>80</X><Y>-32</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>80</X><Y>-8</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-8</X><Y>-8</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-8</X><Y>16</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>8</X><Y>16</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>8</X><Y>-8</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-80</X><Y>-8</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>""",
        "segment": """
        <DataSegment><Spoint><X>0</X><Y>32</Y></Spoint><Epoint><X>0</X><Y>16</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
    "Self": {
        "pins": {"1": (-80, 0, 0), "2": (80, 0, 1)},
        "polygon": "",
        "segment": """
        <DataSegment><Spoint><X>-48</X><Y>0</Y></Spoint><Epoint><X>-80</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>48</X><Y>0</Y></Spoint><Epoint><X>80</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
        "arc": """
        <DataArc><pCenter><X>-32</X><Y>0</Y></pCenter><stAngle>-180</stAngle><swAngle>180</swAngle><Spoint><X>-48</X><Y>0</Y></Spoint><Epoint><X>-16</X><Y>0</Y></Epoint><Eangle>0</Eangle><OldAngle>180</OldAngle><w>16</w><h>0</h><Rect><Location><X>-48</X><Y>0</Y></Location><Size><Width>16</Width><Height>16</Height></Size><X>-48</X><Y>0</Y><Width>16</Width><Height>16</Height></Rect><CPtSelected>false</CPtSelected><SPtSelected>false</SPtSelected><EPtSelected>false</EPtSelected><ArcFinished>true</ArcFinished><Clockwise>false</Clockwise><CPtGap><X>0</X><Y>0</Y></CPtGap><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap><Sens>false</Sens></DataArc>
        <DataArc><pCenter><X>0</X><Y>0</Y></pCenter><stAngle>-180</stAngle><swAngle>180</swAngle><Spoint><X>-16</X><Y>0</Y></Spoint><Epoint><X>16</X><Y>0</Y></Epoint><Eangle>0</Eangle><OldAngle>180</OldAngle><w>16</w><h>0</h><Rect><Location><X>-16</X><Y>0</Y></Location><Size><Width>16</Width><Height>16</Height></Size><X>-16</X><Y>0</Y><Width>16</Width><Height>16</Height></Rect><CPtSelected>false</CPtSelected><SPtSelected>false</SPtSelected><EPtSelected>false</EPtSelected><ArcFinished>true</ArcFinished><Clockwise>false</Clockwise><CPtGap><X>0</X><Y>0</Y></CPtGap><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap><Sens>false</Sens></DataArc>
        <DataArc><pCenter><X>32</X><Y>0</Y></pCenter><stAngle>-180</stAngle><swAngle>180</swAngle><Spoint><X>16</X><Y>0</Y></Spoint><Epoint><X>48</X><Y>0</Y></Epoint><Eangle>0</Eangle><OldAngle>180</OldAngle><w>16</w><h>0</h><Rect><Location><X>16</X><Y>0</Y></Location><Size><Width>16</Width><Height>16</Height></Size><X>16</X><Y>0</Y><Width>16</Width><Height>16</Height></Rect><CPtSelected>false</CPtSelected><SPtSelected>false</SPtSelected><EPtSelected>false</EPtSelected><ArcFinished>true</ArcFinished><Clockwise>false</Clockwise><CPtGap><X>0</X><Y>0</Y></CPtGap><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap><Sens>false</Sens></DataArc>""",
    },
    "Relais": {
        "pins": {"A1": (-100, -40, 0), "A2": (-100, 40, 1),
                 "11": (100, 0, 2), "12": (100, -40, 3), "14": (100, 40, 4)},
        "polygon": """
        <DataPolygon><point><X>-60</X><Y>-40</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-20</X><Y>-40</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-20</X><Y>40</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-60</X><Y>40</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>""",
        "segment": """
        <DataSegment><Spoint><X>-100</X><Y>-40</Y></Spoint><Epoint><X>-60</X><Y>-40</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-100</X><Y>40</Y></Spoint><Epoint><X>-60</X><Y>40</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>40</X><Y>0</Y></Spoint><Epoint><X>100</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>40</X><Y>0</Y></Spoint><Epoint><X>100</X><Y>-40</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>40</X><Y>0</Y></Spoint><Epoint><X>100</X><Y>40</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
    "Relais_1FormC": {
        "pins": {
            "A1":  (-64, -44, 0),
            "A2":  (-64,  44, 1),
            "COM": ( 48,  44, 2),
            "NC":  ( 28, -44, 3),
            "NO":  ( 67, -44, 4),
        },
        "polygon": """
        <DataPolygon><point><X>-80</X><Y>-48</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>-80</X><Y>48</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>80</X><Y>48</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>
        <DataPolygon><point><X>80</X><Y>-48</Y></point><Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>""",
        "segment": """
        <DataSegment><Spoint><X>-48</X><Y>0</Y></Spoint><Epoint><X>-80</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>48</X><Y>0</Y></Spoint><Epoint><X>80</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>21</X><Y>43</Y></Spoint><Epoint><X>80</X><Y>43</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-21</X><Y>0</Y></Spoint><Epoint><X>-80</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>21</X><Y>-43</Y></Spoint><Epoint><X>80</X><Y>-43</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>-21</X><Y>0</Y></Spoint><Epoint><X>21</X><Y>-43</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>21</X><Y>-43</Y></Spoint><Epoint><X>7</X><Y>-43</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>21</X><Y>-43</Y></Spoint><Epoint><X>21</X><Y>-29</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
}


def _forme_puce(n):
    """@brief Forme « PuceN » : boîtier DIP générique à n broches NUMÉROTÉES.

    Pour les puces du catalogue (NE555, 74HC…, cf. circuit_analyzer.catalogue)
    dont les broches sont des numéros de boîtier : colonne gauche 1..n/2 de
    haut en bas, colonne droite n/2+1..n de bas en haut (convention DIP).
    Corps rectangulaire minimal ; la lecture repasse les Pname tels quels
    (plan vide dans _NOM_VERS_TYPE), donc le round-trip préserve les numéros.
    """
    demi = n // 2
    pas = 24
    haut = (demi - 1) * pas
    pins = {}
    for i in range(demi):                    # gauche : 1..demi, haut -> bas
        pins[str(i + 1)] = (-72, -haut // 2 + i * pas, i)
    for i in range(demi):                    # droite : demi+1..n, bas -> haut
        pins[str(demi + 1 + i)] = (72, haut // 2 - i * pas, demi + i)
    y0, y1 = -haut // 2 - 12, haut // 2 + 12
    poly = "".join(
        f"\n        <DataPolygon><point><X>{x}</X><Y>{y}</Y></point>"
        f"<Selected>false</Selected><PtGap><X>0</X><Y>0</Y></PtGap></DataPolygon>"
        for x, y in ((-48, y0), (48, y0), (48, y1), (-48, y1)))
    seg = "".join(
        f"\n        <DataSegment><Spoint><X>{sx}</X><Y>{y}</Y></Spoint>"
        f"<Epoint><X>{ex}</X><Y>{y}</Y></Epoint><ESelected>false</ESelected>"
        f"<SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap>"
        f"<SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>"
        for (sx, ex, y) in (
            [(-72, -48, p[1]) for nom, p in pins.items() if p[0] < 0]
            + [(48, 72, p[1]) for nom, p in pins.items() if p[0] > 0]))
    return {"pins": pins, "polygon": poly, "segment": seg}


def _etendue_forme_catalogue(forme: dict) -> tuple:
    """@brief (largeur, hauteur) de la boîte CATALOGUE d'une entrée `_FORME`.

    Équivalent de `gui.schematic_symbols.etendue_primitives`, mais sur la
    géométrie catalogue déjà sérialisée en XML (`polygon`/`segment`/`arc`
    d'une entrée `_FORME`) plutôt que sur des primitives structurées --
    ces formes n'existent qu'en XML pré-rendu ici, jamais en tuples
    `("line"/"polygon"/"arc", ...)`. Sert à « aimanter » les broches
    catalogue sur les bords de LEUR PROPRE boîte avant de les reprojeter
    dans un contour dessiné à la main, d'une échelle différente (revue
    finale round 2, Critical 2 sous-point manqué : les `<DataPin>` de la
    branche catalogue restaient en coordonnées catalogue -- ex. ±80 pour
    une Résistance -- alors que le contour dessiné est en coordonnées
    éditeur -- ex. ±40 --, deux fois plus petites).

    Plancher à 1 sur chaque dimension (jamais 0) : certaines formes ont
    tous leurs points alignés sur un axe (ex. "Self", segments/arc à
    Y=0 partout) -- une boîte de hauteur nulle fait dégénérer l'arbitrage
    de bord de `aimanter_bord` (égalité T/B/L/R à distance 0), qui aimante
    alors la broche sur le mauvais bord (T au lieu de L/R, cf. l'ordre
    d'arbitrage documenté dans `aimanter_bord`).
    """
    texte = forme.get("polygon", "") + forme.get("segment", "") + forme.get("arc", "")
    coords = re.findall(r'<X>(-?\d+)</X>\s*<Y>(-?\d+)</Y>', texte)
    mx = max((abs(int(x)) for x, _ in coords), default=0)
    my = max((abs(int(y)) for _, y in coords), default=0)
    return max(1, mx * 2), max(1, my * 2)


# Tailles de boîtier DIP couvertes par le catalogue v1 (4/8/14/16 broches).
_TAILLES_PUCE = (4, 8, 14, 16)
for _n in _TAILLES_PUCE:
    _FORME[f"Puce{_n}"] = _forme_puce(_n)


# Alias noms utilisés par lire_xml → noms dans _FORME
_ALIAS = {
    "Résistance": "Résistance", "Resistance": "Résistance",
    "Capa": "Capa", "Condensateur": "Capa",
    "AOP": "AOP",
    "Transistor": "Transistor",
    "MOSFET": "MOSFET",
    "Diode": "Diode",
    "Fusible": "Fusible",
    "GND": "GND", "AGND": "AGND", "PGND": "GND", "DGND": "GND",
    "VCC": "VCC", "Vcc": "VCC", "+5V": "VCC", "+3.3V": "VCC",
    "Vss": "Vss", "VMOT": "Vss", "VBUS": "Vss",
    "Self": "Self", "Bobine": "Self", "Inductance": "Self",
    "Relais": "Relais", "Relais_1FormC": "Relais_1FormC",
    "2N2B": "2N2B",
}

# type_composant → (nom_forme_BoardSCH, {broche_lib → broche_forme})
_TYPE_VERS_FORME = {
    "R": ("Résistance", {"1": "1", "2": "2"}),
    "C": ("Capa",       {"1": "+", "2": "-"}),
    "U": ("AOP",        {"IN+": "+", "IN-": "-", "OUT": "s"}),
    "Q": ("2N2B",       {"B": "G", "C": "C", "E": "E"}),
    "M": ("MOSFET",     {"G": "G", "D": "D", "S": "S"}),
    "D": ("Diode",      {"A": "A", "K": "K", "1": "A", "2": "K"}),
    "F": ("Fusible",    {"1": "1", "2": "2"}),
    "L": ("Self",       {"1": "1", "2": "2"}),
    "K": ("Relais_1FormC", {"A1": "A1", "A2": "A2", "11": "COM", "12": "NC", "14": "NO"}),
    # Les rails portent une broche NUMEROTEE ("1") : sans entree ici, ils
    # tombaient dans la branche « toutes broches numerotees » (l. 829) et
    # ressortaient en boitier DIP 4 broches. Mesure : 3 composants en entree,
    # 4 en sortie, dont un fantome. Noms de broches verifies sur _FORME apres
    # fusion (Task 2) : GND -> "GND", VCC -> "VCC", Vss -> "VCC".
    "GND": ("GND", {"1": "GND"}),
    "VCC": ("VCC", {"1": "VCC"}),
    "VSS": ("Vss", {"1": "VCC"}),
    # Composant inconnu (issu d'un XML avec nom non reconnu) → rendu comme résistance placeholder
    "X": ("Résistance", {"1": "1", "2": "2"}),
}

# Valeur <typ> observée dans les schematics de référence (ERetroDesign)
_TYP_COMPOSANT = {
    "Résistance": 82, "Capa": 32, "AOP": 79,
    "GND": 71, "AGND": 71, "VCC": 86, "VCC+": 86, "VCC-": 71, "Vss": 115,
}


#: Nos formes historiques, AVANT fusion. Conservees telles quelles : ce sont
#: elles qui servent de repli quand son dossier est absent (CI, .exe livre),
#: et le point de comparaison quand un dessin diverge.
#: Deep copy garantit l'indépendance complète, y compris les sous-dicts pins.
_FORME_MAISON = deepcopy(_FORME)


def _fusionner_bibliotheque_eretro():
    """@brief Superpose SA bibliotheque vivante sur nos formes maison.

    Decision du boss (2026-07-31) : sur les noms communs, SA geometrie fait
    foi — nos deux bibliotheques sont deux copies divergees de la meme, et il
    faut une seule source. Nos formes orphelines (MOSFET, Fusible, PuceN,
    Relais...) sont CONSERVEES : il ne les a pas, et l'export en depend.

    Le `typ`, lui, ne suit PAS le symbole. On partage la geometrie, pas la
    semantique electrique : son `GND.xml` porte `typ=0` la ou le notre vaut 71
    ('G'), la valeur meme dont `eretro.classer_rail` se sert pour reconnaitre
    une masse. D'ou un `setdefault`, qui ne comble qu'une entree absente.

    Les `pins` FUSIONNENT par RANG : on garde nos noms de clé (pour que
    _TYPE_VERS_FORME et _idx_broche continuent de fonctionner), mais on prend
    les POSITIONS (x, y) de SA bibliotheque au même rang. Cela garantit que la
    géométrie dessinée (segments/polygones) et l'ancrage des fils coïncident.
    """
    for nom, forme in eretro_symboles.charger().items():
        _TYP_COMPOSANT.setdefault(nom, forme["typ"])

        if nom in _FORME:
            # Merge: prendre sa géométrie, fusionner ses pins par rang
            _FORME[nom].update({cle: valeur for cle, valeur in forme.items()
                                if cle not in ("typ", "pins")})

            # Fusionner les pins par RANG : garder nos noms, prendre ses positions
            nos_pins = _FORME[nom]["pins"]
            ses_pins = forme["pins"]

            # Créer un map rang -> (nom_notre_clé, position_notre)
            nos_pins_par_rang = {rang: (nom_clé, (x, y))
                                 for nom_clé, (x, y, rang) in nos_pins.items()}
            ses_pins_par_rang = {rang: (x, y)
                                 for nom_clé, (x, y, rang) in ses_pins.items()}

            # Les rangs doivent correspondre EXACTEMENT : un decompte egal
            # mais des rangs differents est tout aussi desynchronisant qu'un
            # decompte different. Le repli (garder notre position d'origine
            # pour un rang orphelin) reste inchange ; on ajoute seulement la
            # visibilite, faute de quoi ce cas passe en silence (cf. Tour de
            # Correction 1, ou la meme desync geometrie/broches est apparue
            # pour une autre cause).
            if set(nos_pins_par_rang) != set(ses_pins_par_rang):
                _log.warning(
                    "forme %s : rangs de broches divergents apres fusion "
                    "(%d chez nous, %d chez lui) - les rangs orphelins "
                    "gardent notre position d'origine", nom,
                    len(nos_pins_par_rang), len(ses_pins_par_rang))

            # Construire les pins fusionnées
            pins_fusionnées = {}
            for rang, (nom_clé, _) in nos_pins_par_rang.items():
                if rang in ses_pins_par_rang:
                    # Prendre SA position au même rang, garder NOTRE nom
                    x, y = ses_pins_par_rang[rang]
                    pins_fusionnées[nom_clé] = (x, y, rang)
                else:
                    # Pas de broche au même rang chez lui : garder la nôtre
                    pins_fusionnées[nom_clé] = nos_pins[nom_clé]

            _FORME[nom]["pins"] = pins_fusionnées
        else:
            # New symbol from editor: use it as-is
            _FORME[nom] = {cle: valeur for cle, valeur in forme.items() if cle != "typ"}

    # Garde-fou (revue finale) : `_idx_broche_forme` (plus bas) fait un
    # lookup NON protege `_FORME[nom]["pins"][broche][2]`. Si un plan de
    # _TYPE_VERS_FORME reclame un nom de broche que la forme fusionnee ne
    # porte plus — typiquement une forme NEUVE arrivee via la branche
    # ci-dessus, dont les noms de broches sont les siens et pas les notres —
    # generer_xml() plante avec un KeyError brut. Le chargeur ne leve JAMAIS
    # pour cette meme raison (son dossier est un tiers, mouvant sans
    # prevenir) ; ce garde-fou etend la garantie un niveau plus haut : on
    # revient a notre forme maison plutot que de laisser l'export exploser.
    for nom_forme, plan_broches in _TYPE_VERS_FORME.values():
        if nom_forme not in _FORME:
            continue
        pins_disponibles = _FORME[nom_forme]["pins"]
        manquantes = sorted({nom_broche for nom_broche in plan_broches.values()
                             if nom_broche not in pins_disponibles})
        if not manquantes:
            continue
        if nom_forme in _FORME_MAISON:
            _FORME[nom_forme] = deepcopy(_FORME_MAISON[nom_forme])
            _log.warning(
                "forme %s : broches manquantes apres fusion (%s) - "
                "repli sur notre forme maison", nom_forme, ", ".join(manquantes))
        else:
            _log.warning(
                "forme %s : broches manquantes apres fusion (%s) et aucune "
                "forme maison de repli disponible - la forme reste telle quelle",
                nom_forme, ", ".join(manquantes))


def formes_orphelines(dossier):
    """@brief Nos formes maison absentes de sa bibliotheque (LibItem/Lib).

    Expose `_FORME_MAISON`/`_TYP_COMPOSANT` (prives a ce module) via une
    fonction publique, pour que `gui/tab_components.py` puisse pousser nos
    symboles orphelins (`eretro_lib.ecrire_formes_dans_dossier`) sans
    importer directement des noms prefixes `_` depuis un autre fichier.

    @param dossier Dossier `LibItem/Lib` a comparer, ou None/vide.
    @return tuple (formes: dict nom -> entree _FORME, typs: dict nom -> typ)
            restreints aux noms absents de sa bibliotheque.
    """
    from circuit_analyzer import eretro_symboles
    ses_formes = eretro_symboles.charger(dossier) if dossier else {}
    orphelines = {nom: forme for nom, forme in _FORME_MAISON.items()
                 if nom not in ses_formes}
    typs = {nom: t for nom, t in _TYP_COMPOSANT.items() if nom in orphelines}
    return orphelines, typs


_fusionner_bibliotheque_eretro()


# =============================================================================
# GÉNÉRATION XML (Composants → fichier BoardSCH)
# =============================================================================

@dataclass
class _Comp:
    """@brief Composant placé sur le schéma (id, nom de forme, valeur, position, forme)."""
    cid: int; name: str; value: str; x: int; y: int; angle: int = 0; shape: str = ""; group_id: int = 0; ref: str = ""
    primitives: list | None = None
    pinout: dict | None = None

@dataclass
class _Wire:
    """@brief Fil reliant la broche p1 du composant c1 à la broche p2 du composant c2."""
    wid: int; c1: int; p1: int; c2: int; p2: int; group_id: int = 0


class _Generateur:
    """@brief Constructeur interne de schéma BoardSCH XML."""

    def __init__(self):
        """@brief Initialise un générateur vide (aucun composant ni fil)."""
        self._comps: list[_Comp] = []
        self._wires: list[_Wire] = []
        self._wire_id = 0

    def ajouter(self, nom, valeur="", x=0, y=0, angle=0, forme="", group_id=0, ref="",
               primitives=None, pinout=None) -> int:
        """@brief Ajoute un composant au schéma.

        @param nom Nom de la forme BoardSCH (ex. 'Résistance', 'AOP').
        @param valeur Valeur affichée du composant.
        @param x Abscisse du centre.
        @param y Ordonnée du centre.
        @param angle Angle de rotation (degrés).
        @param forme Forme explicite (sinon déduite du nom).
        @param group_id Identifiant de groupe BoardSCH (0 = aucun groupe).
        @param ref Référence du composant (ex. 'R1', 'C1').
        @param primitives Contour réel de l'instance (primitives), prioritaire sur `_FORME` si fourni.
        @param pinout Brochage réel de l'instance ({nom: (côté, décalage)}), prioritaire sur `_FORME` si fourni.
        @return int Identifiant (cid) du composant ajouté.
        """
        cid = len(self._comps)
        self._comps.append(_Comp(cid, nom, valeur, x, y, angle, forme, group_id,
                                 ref=ref, primitives=primitives, pinout=pinout))
        return cid

    def relier(self, cid1, broche1, cid2, broche2):
        """@brief Relie deux broches par un fil.

        @param cid1 Composant source.
        @param broche1 Nom de la broche source.
        @param cid2 Composant destination.
        @param broche2 Nom de la broche destination.
        @return None
        """
        p1 = self._idx_broche(cid1, broche1)
        p2 = self._idx_broche(cid2, broche2)
        wid = self._wire_id; self._wire_id += 1
        group_id = _groupe_commun(self, cid1, cid2)
        self._wires.append(_Wire(wid, cid1, p1, cid2, p2, group_id))

    def vers_xml(self) -> str:
        """@brief Sérialise le schéma complet en chaîne XML BoardSCH.
        @return str Document XML BoardSCH.
        """
        parties = ['<?xml version="1.0" encoding="utf-8"?>',
                   '<BoardSCH xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                   'xmlns:xsd="http://www.w3.org/2001/XMLSchema">', '  <CmpntL>']
        noeuds_pins: dict[tuple[int,int], list[str]] = {}
        for w in self._wires:
            noeuds_pins.setdefault((w.c1, w.p1), []).append(f"{w.c1}_{w.p1}_0_{w.wid}")
            noeuds_pins.setdefault((w.c2, w.p2), []).append(f"{w.c2}_{w.p2}_1_{w.wid}")
        for comp in self._comps:
            parties.append(self._xml_composant(comp, noeuds_pins))
        parties += ['  </CmpntL>', '  <lineL>']
        for w in self._wires:
            parties.append(self._xml_fil(w))
        parties += ['  </lineL>', '  <CCmpntL />', self._xml_groupes(), '  <zoom>1</zoom>', '</BoardSCH>']
        return '\n'.join(parties)

    def _xml_groupes(self) -> str:
        """@brief Sérialise les groupes BoardSCH natifs déduits des GpId.

        @return str Fragment XML <GrpL> ou <GrpL /> si aucun groupe.
        """
        groupes = sorted({c.group_id for c in self._comps if c.group_id})
        if not groupes:
            return "  <GrpL />"

        parties = ["  <GrpL>"]
        for gid in groupes:
            items = [c.cid for c in self._comps if c.group_id == gid]
            lignes = [w.wid for w in self._wires if w.group_id == gid]
            if not items:
                continue
            rect = self._rect_groupe(items)
            parties.append(f"""    <GRPS>
      <CtrG><X>{rect['width'] // 2}</X><Y>{rect['height'] // 2}</Y></CtrG>
      <Gid>{gid}</Gid>
      <GRect>
        <Location><X>{rect['x']}</X><Y>{rect['y']}</Y></Location>
        <Size><Width>{rect['width']}</Width><Height>{rect['height']}</Height></Size>
        <X>{rect['x']}</X><Y>{rect['y']}</Y><Width>{rect['width']}</Width><Height>{rect['height']}</Height>
      </GRect>
      <Selected>false</Selected>
      <IidL>{''.join(f'<int>{i}</int>' for i in items)}</IidL>
      <LidL>{''.join(f'<int>{i}</int>' for i in lignes)}</LidL>
    </GRPS>""")
        parties.append("  </GrpL>")
        return "\n".join(parties)

    def _rect_groupe(self, item_ids: list[int]) -> dict:
        """@brief Calcule un rectangle englobant simple pour un groupe BoardSCH.

        @param item_ids Identifiants des composants du groupe.
        @return dict Coordonnées x/y/width/height.
        """
        marge_x = 140
        marge_y = 110
        xs = []
        ys = []
        for cid in item_ids:
            comp = self._comps[cid]
            xs.extend([comp.x - marge_x, comp.x + marge_x])
            ys.extend([comp.y - marge_y, comp.y + marge_y])
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}

    def _idx_broche(self, cid, nom_broche) -> int:
        """@brief Index interne d'une broche nommée sur un composant.

        @param cid Identifiant du composant.
        @param nom_broche Nom de la broche recherchée.
        @return int Index de broche dans la forme.
        @throws ValueError Si la broche n'existe pas sur la forme du composant.
        """
        comp = self._comps[cid]
        if comp.pinout:
            pins = sorted(comp.pinout)  # ordre stable, arbitraire mais deterministe
            if nom_broche in pins:
                return pins.index(nom_broche)
            raise ValueError(f"Broche '{nom_broche}' introuvable sur composant {cid} ({comp.name}). "
                             f"Disponibles : {pins}")
        forme_nom = _ALIAS.get(self._comps[cid].name, self._comps[cid].name)
        forme = _FORME.get(forme_nom, {})
        broches = forme.get("pins", {})
        if nom_broche not in broches:
            raise ValueError(f"Broche '{nom_broche}' introuvable sur composant {cid} ({self._comps[cid].name}). "
                             f"Disponibles : {list(broches.keys())}")
        return broches[nom_broche][2]

    def _xml_composant(self, comp, noeuds_pins) -> str:
        """@brief Sérialise un composant (DataItem) en fragment XML.

        @param comp Composant interne (_Comp) à sérialiser.
        @param noeuds_pins Dict {(cid, pidx) -> [refs de nœud]} construit depuis les fils.
        @return str Fragment XML <DataItem> du composant.
        """
        # `pinout` (brochage) et `primitives` (contour) sont deux informations
        # INDEPENDANTES -- un composant peut avoir l'un, l'autre, les deux ou
        # ni l'un ni l'autre (revue finale round 1, Critical 1+2 : traites
        # comme un seul signal avant ce fix, le contour dessine a la main sur
        # un composant SANS brochage libre d'instance disparaissait a
        # l'export). Les BROCHES restent tranchees par `comp.pinout` (nommage
        # reel via `geometrie_libre` si defini, sinon plan du catalogue) ; le
        # CONTOUR est tranche independamment par `comp.primitives` juste en
        # dessous, qu'il y ait ou non un `pinout`.
        if comp.pinout:
            geo = geometrie_reelle(comp.pinout, comp.primitives)
            pins_ordonnees = sorted(comp.pinout)
            parties_broches = []
            for pidx, nom_b in enumerate(pins_ordonnees):
                lx, ly = geo["pins"][nom_b]
                refs_noeud = noeuds_pins.get((comp.cid, pidx), [])
                node_l = ''.join(f'<string>{r}</string>' for r in refs_noeud)
                parties_broches.append(f"""      <DataPin>
        <Pname>{nom_b}</Pname><Pnumber>{nom_b}</Pnumber>
        <NodeL>{node_l}</NodeL>
        <Pin><X>{lx}</X><Y>{ly}</Y></Pin>
        <PinGap><X>0</X><Y>0</Y></PinGap><Size>9</Size>
        <Selected>false</Selected><ShowNbTxt>false</ShowNbTxt><ShowNmTxt>false</ShowNmTxt>
        <VltgP>0</VltgP><typ>{ord(nom_b[0]) if nom_b else 0}</typ>
      </DataPin>""")
            tous_refs = []
            for pidx in range(len(pins_ordonnees)):
                tous_refs.extend(noeuds_pins.get((comp.cid, pidx), []))
            pin_cl = ''.join(f'<string>{r}</string>' for r in tous_refs)
            typ_val = ord(comp.name[0]) if comp.name and comp.name[0].isascii() else 85
            forme = None
        else:
            cle_forme = comp.shape or comp.name
            nom_forme = _ALIAS.get(cle_forme, cle_forme)
            forme = _FORME.get(nom_forme, {"pins": {}, "polygon": "", "segment": ""})
            broches_info = forme.get("pins", {})
            if comp.primitives:
                # Contour dessine a la main (ou importe) SANS brochage libre
                # d'instance (comp.pinout is None) : les broches restent
                # nommees par le catalogue, mais leurs coordonnees catalogue
                # (ex. Resistance +-80) sont dans une echelle totalement
                # differente du contour dessine cote editeur (ex. +-40) --
                # revue finale round 2, Critical 2 sous-point manque. On
                # "aimante" chaque broche catalogue sur le bord de SA PROPRE
                # boite catalogue (meme mecanisme que `_amorcer_pinout` cote
                # editeur, gui/schematic_editor.py:866-875), puis on
                # reprojette ce pinout {cote, decalage} DANS le contour
                # reellement dessine via `geometrie_reelle` -- comme la
                # branche `if comp.pinout:` juste au-dessus le fait deja pour
                # un brochage libre d'instance.
                # `aimanter_bord` choisit le bord dans l'echelle CATALOGUE et
                # renvoie un decalage LONGITUDINAL (le long du bord) dans
                # cette meme echelle -- seule la coordonnee PERPENDICULAIRE
                # (+-w2/+-h2) est reprojetee par `geometrie_reelle` (elle
                # recalcule w2/h2 depuis le contour reel). Sans remise a
                # l'echelle du decalage longitudinal, une broche catalogue
                # a decalage non nul (ex. Transistor.C a Y=-50) ressort
                # encore hors du contour dessine -- revue finale round 2
                # bis, Critical 2 second sous-point manque (le premier
                # sous-point, cf. plus haut, n'a corrige que l'axe
                # perpendiculaire).
                box_w, box_h = _etendue_forme_catalogue(forme)
                reel_w, reel_h = etendue_primitives(comp.primitives)

                def _reprojeter_decalage(cote, dec):
                    if cote in ("L", "R"):
                        echelle, lim = reel_h / box_h, reel_h // 2
                    else:
                        echelle, lim = reel_w / box_w, reel_w // 2
                    lim = max(0, lim - _GRILLE // 2)
                    d2 = int(round(dec * echelle / _GRILLE)) * _GRILLE
                    return cote, max(-lim, min(lim, d2))

                pinout_synthetise = {
                    nom_b: _reprojeter_decalage(
                        *aimanter_bord(lx, ly, box_w, box_h, _GRILLE))
                    for nom_b, (lx, ly, _pidx) in broches_info.items()
                }
                positions = geometrie_reelle(pinout_synthetise, comp.primitives)["pins"]
            else:
                positions = {nom_b: (lx, ly) for nom_b, (lx, ly, _pidx) in broches_info.items()}
            parties_broches = []
            for nom_b, (_lx0, _ly0, pidx) in sorted(broches_info.items(), key=lambda kv: kv[1][2]):
                lx, ly = positions[nom_b]
                refs_noeud = noeuds_pins.get((comp.cid, pidx), [])
                node_l = ''.join(f'<string>{r}</string>' for r in refs_noeud)
                parties_broches.append(f"""      <DataPin>
        <Pname>{nom_b}</Pname><Pnumber>{nom_b}</Pnumber>
        <NodeL>{node_l}</NodeL>
        <Pin><X>{lx}</X><Y>{ly}</Y></Pin>
        <PinGap><X>0</X><Y>0</Y></PinGap><Size>9</Size>
        <Selected>false</Selected><ShowNbTxt>false</ShowNbTxt><ShowNmTxt>false</ShowNmTxt>
        <VltgP>0</VltgP><typ>{ord(nom_b[0]) if nom_b else 0}</typ>
      </DataPin>""")
            tous_refs = []
            for pidx in range(len(broches_info)):
                tous_refs.extend(noeuds_pins.get((comp.cid, pidx), []))
            pin_cl = ''.join(f'<string>{r}</string>' for r in tous_refs)
            typ_val = _TYP_COMPOSANT.get(nom_forme, ord(nom_forme[0]) if nom_forme and nom_forme[0].isascii() else 82)

        # Contour reel (Task 6 dessin a la main, ou import fidele) prioritaire
        # DES QU'IL EST PRESENT, meme sans `pinout` (Critical 2) : sinon un
        # contour dessine a la main sur un composant type disparait a
        # l'export et le XML reprend la forme catalogue generique.
        if comp.primitives:
            seg, poly, arc = eretro_lib._primitives_vers_xml(
                comp.primitives, lambda dx, dy: (int(round(dx)), int(round(dy))))
        elif forme is not None:
            poly = forme.get("polygon", ""); seg = forme.get("segment", ""); arc = forme.get("arc", "")
        else:
            seg, poly, arc = "", "", ""
        return f"""    <DataItem>
      <Name>{_esc(comp.name)}</Name><Group /><reference>{_esc(comp.ref)}</reference><value>{_esc(comp.value)}</value>
      <datapolygon>{poly}</datapolygon><datasegment>{seg}</datasegment><dataarc>{arc}</dataarc>
      <datapin>
{''.join(parties_broches)}
      </datapin>
      <PinCL>{pin_cl}</PinCL>
      <CtrIem><X>{comp.x}</X><Y>{comp.y}</Y></CtrIem>
      <pgap><X>0</X><Y>0</Y></pgap><TL><X>50</X><Y>25</Y></TL><BR><X>210</X><Y>121</Y></BR>
      <angle>{comp.angle}</angle><id>{comp.cid}</id><GpId>{comp.group_id}</GpId>
      <zmH>1</zmH><zmV>1</zmV><FlipX>0</FlipX><FlipY>0</FlipY>
      <typ>{typ_val}</typ>
      <Bottom>false</Bottom><selected>false</selected><focus>false</focus>
      <Visible>true</Visible><Top>true</Top><Begrp>{_bool_xml(bool(comp.group_id))}</Begrp><freeze>false</freeze>
    </DataItem>"""

    def _xml_fil(self, w) -> str:
        """@brief Sérialise un fil (Line) en fragment XML.

        @param w Fil interne (_Wire) à sérialiser.
        @return str Fragment XML <Line> du fil.
        """
        c1, c2 = self._comps[w.c1], self._comps[w.c2]
        f1 = _FORME.get(_ALIAS.get(c1.shape or c1.name, c1.shape or c1.name), {}).get("pins", {})
        f2 = _FORME.get(_ALIAS.get(c2.shape or c2.name, c2.shape or c2.name), {}).get("pins", {})
        n1 = next((k for k, v in f1.items() if v[2] == w.p1), "")
        n2 = next((k for k, v in f2.items() if v[2] == w.p2), "")
        x1 = c1.x + f1.get(n1, (0,0,0))[0]; y1 = c1.y + f1.get(n1, (0,0,0))[1]
        x2 = c2.x + f2.get(n2, (0,0,0))[0]; y2 = c2.y + f2.get(n2, (0,0,0))[1]
        return f"""    <Line>
      <CFirst>{w.c1}_{w.p1}_0_{w.wid}</CFirst><CLast>{w.c2}_{w.p2}_1_{w.wid}</CLast>
      <LP><PointF><X>{x1}</X><Y>{y1}</Y></PointF><PointF><X>{x2}</X><Y>{y2}</Y></PointF></LP>
      <pGap /><ID>0</ID><idF>0</idF><idL>0</idL><GpId>{w.group_id}</GpId>
      <Visible>true</Visible><select>false</select><Top>true</Top><Bottom>false</Bottom>
      <BeIngrp>{_bool_xml(bool(w.group_id))}</BeIngrp><VltgL>0</VltgL>
    </Line>"""


# Constantes de mise en page
_BLOCS_PAR_RANGEE = 3
_GAP_BLOCS   = 160
_LARG_COMP   = 320
_HAUT_RANGEE = 260
_LARG_BLOC   = 720
_HAUT_BLOC   = 460
_PAS_X_BLOC  = 260
_PAS_Y_BLOC  = 190


@dataclass
class _Bloc:
    """@brief Bloc de mise en page : un libellé de circuit et ses composants.

    `roles` associe un nom de rôle (ex. 'aop', 'Zin', 'Zf') à la liste des
    refs qui le jouent — vide si le montage n'a pas de décomposition par
    rôle connue (Divers, ou montage pas encore migré vers un positionneur
    canonique).
    """
    label: str
    comps: list
    roles: dict = field(default_factory=dict)


def _refs_du_bloc(r) -> list:
    """@brief Refs d'un circuit + ses satellites sûrs (les « possibles » restent en Divers).

    @param r Match d'un circuit détecté.
    @return list Références du circuit et de ses satellites sûrs.
    """
    refs = list(r["components"])
    refs += [s['ref'] for s in r.get('satellites', []) if s.get('status') == 'sure']
    return refs


def _roles_du_bloc(r) -> dict:
    """@brief Rôles des composants d'un match, depuis 'impedances'.

    @param r Match d'un circuit détecté (sortie de detecteur.py).
    @return dict {nom_role: [refs]} ; {} si le match n'a pas de champ
            'impedances' (Divers, ou montage pas encore migré).

    Le ou les refs de r['components'] qui n'apparaissent dans AUCUN rôle de
    'impedances' sont regroupés sous le rôle 'aop' (l'ancre du montage —
    vrai pour tous les montages AOP actuels, qui n'ont qu'un seul composant
    hors impédances).

    Une valeur de 'impedances' peut être un dict {'refs': [...], ...} (cas
    général) OU une liste de tels dicts (ex. 'Zin' du Sommateur, plusieurs
    entrées — detecteur.py:701/718).
    """
    impedances = r.get('impedances')
    if not impedances:
        return {}
    roles = {nom: _refs_du_role(bloc) for nom, bloc in impedances.items()}
    refs_connus = {ref for refs in roles.values() for ref in refs}
    ancre = [ref for ref in r['components'] if ref not in refs_connus]
    if ancre:
        roles['aop'] = ancre
    return roles


def _refs_du_role(bloc) -> list:
    """@brief Refs d'un rôle d'impédance : un dict {'refs': [...], ...} (cas
    général) OU une liste de tels dicts (ex. 'Zin' du Sommateur, plusieurs
    entrées — detecteur.py:701/718)."""
    if isinstance(bloc, dict):
        return list(bloc.get('refs', []))
    return [ref for sous in (bloc or []) if isinstance(sous, dict)
            for ref in sous.get('refs', [])]


def _ordre_des_circuits(resultats) -> list:
    """
    @brief Ordre d'émission des blocs (circuits d'un même îlot consécutifs).

    Les circuits du même îlot fonctionnel sont consécutifs si .ilots est
    disponible, sinon ordre de détection.

    @param resultats Sortie de detecteur.analyser() (avec éventuellement .ilots).
    @return list Indices des circuits dans l'ordre d'émission.
    """
    indices = list(range(len(resultats or [])))
    ilots = getattr(resultats, 'ilots', [])
    if not ilots:
        return indices
    par_ilot = [i for ilot in ilots for i in ilot['circuits']]
    restants = [i for i in indices if i not in par_ilot]
    return par_ilot + restants


def _grouper_par_circuit(composants, resultats):
    """@brief Regroupe les composants par circuit détecté.

    Les composants non classifiés vont dans un bloc 'Divers'.

    @param composants Liste des composants du schéma.
    @param resultats Sortie de detecteur.analyser() (ou None).
    @return list[_Bloc] Blocs de mise en page (un par circuit + 'Divers' éventuel).
    """
    comp_par_ref = {c.ref: c for c in composants if _TYPE_VERS_FORME.get(c.type) is not None}
    ordre = _ordre_des_circuits(resultats)
    type_du_ref: dict = {}
    for i in ordre:
        r = resultats[i]
        for ref in _refs_du_bloc(r):
            type_du_ref.setdefault(ref, r["circuit_type"])
    blocs = []
    for i in ordre:
        r = resultats[i]
        label = r["circuit_type"]
        b = _Bloc(label, [comp_par_ref[ref] for ref in _refs_du_bloc(r)
                          if ref in comp_par_ref and type_du_ref.get(ref) == label],
                  roles=_roles_du_bloc(r))
        if b.comps:
            blocs.append(b)
    divers = [c for ref, c in comp_par_ref.items() if ref not in type_du_ref]
    if divers:
        # Satellites "possible" : le détecteur les a classés incertains, ne pas forcer
        # leur rattachement (ils doivent rester visibles en Divers).
        satellites_possibles = {
            sat['ref']
            for r in (resultats or [])
            for sat in r.get('satellites', [])
            if isinstance(sat, dict) and sat.get('status') != 'sure'
        }

        # 1. Rattacher au groupe le plus proche par NET signal partagé.
        nets_du_groupe: dict = {}  # label -> set(nets)
        for r in (resultats or []):
            label = r["circuit_type"]
            for ref in _refs_du_bloc(r):
                c = comp_par_ref.get(ref)
                if c:
                    for net in getattr(c, 'pins', {}).values():
                        if net and net != 'NC' and not is_gnd(net) and not is_power(net):
                            nets_du_groupe.setdefault(label, set()).add(net)
        restants = []
        for c in divers:
            if c.ref in satellites_possibles:
                restants.append(c)
                continue
            pins_c = set(v for v in getattr(c, 'pins', {}).values()
                         if v and v != 'NC' and not is_gnd(v) and not is_power(v))
            cible = next((b for b in blocs
                          if nets_du_groupe.get(b.label, set()) & pins_c), None)
            if cible is not None:
                cible.comps.append(c)
                type_du_ref[c.ref] = cible.label
            else:
                restants.append(c)
        # 2. Parmi les restants, regrouper par cluster de nets partagés.
        #    Les composants isolés (aucun net partagé) sont fusionnés en un seul
        #    bloc Divers au lieu d'un bloc par composant.
        if restants:
            clusters = _clusteriser_par_nets(restants)
            multi = [cl for cl in clusters if len(cl) > 1]
            solo  = [cl[0] for cl in clusters if len(cl) == 1]
            for cluster in multi:
                blocs.append(_Bloc("Divers", cluster))
            if solo:
                blocs.append(_Bloc("Divers", solo))

    # Fusionner les blocs singleton (1 composant) d'un même label non-Divers.
    # Ex : 5 condensateurs de découplage détectés séparément → 1 seul bloc.
    singletons: dict = {}
    blocs_out = []
    for b in blocs:
        if len(b.comps) == 1 and b.label != "Divers":
            singletons.setdefault(b.label, []).append(b.comps[0])
        else:
            blocs_out.append(b)
    for label, comps_list in singletons.items():
        blocs_out.append(_Bloc(label, comps_list))
    return blocs_out


def _clusteriser_par_nets(comps) -> list:
    """@brief Regroupe les composants isolés en clusters par nets partagés (Union-Find).

    @param comps Liste de Composant à partitionner.
    @return list[list[Composant]] Clusters de composants interconnectés.
    """
    n = len(comps)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        parent[find(i)] = find(j)

    net_vers_idx: dict = {}
    for i, c in enumerate(comps):
        for net in getattr(c, 'pins', {}).values():
            if net and net != 'NC' and not is_gnd(net) and not is_power(net):
                if net in net_vers_idx:
                    union(i, net_vers_idx[net])
                else:
                    net_vers_idx[net] = i

    clusters: dict = {}
    for i, c in enumerate(comps):
        clusters.setdefault(find(i), []).append(c)
    return list(clusters.values())


def _positionner_blocs(blocs) -> dict:
    """@brief Calcule la position (x, y) de chaque composant selon son bloc.

    @param blocs Liste de _Bloc à disposer en grille.
    @return dict {ref -> (x, y)} Positions de chaque composant.
    """
    pos = {}
    for idx, blk in enumerate(blocs):
        col = idx % _BLOCS_PAR_RANGEE
        row = idx // _BLOCS_PAR_RANGEE
        x = 250 + col * (_LARG_BLOC + _GAP_BLOCS)
        y = 250 + row * _HAUT_BLOC
        pos.update(_positionner_composants_bloc(blk, x, y))
    return pos


def _positionner_amplificateur_inverseur(comps, roles, x: int, y: int) -> dict:
    """@brief Gabarit canonique de l'ampli inverseur.

    Zin en chaîne horizontale à gauche de l'AOP (alignée sur son entrée),
    AOP au centre, Zf en chaîne horizontale AU-DESSUS de l'AOP — c'est la
    POSITION (strictement au-dessus), pas une rotation, qui distingue le
    chemin de contre-réaction de la chaîne Zin. Angle toujours 0 : la
    rotation des broches de fil (_xml_fil) n'est pas fiable pour un symbole
    tourné dans ERetroDesign — confirmé : une Zf à angle=90 s'affichait mal
    (fils désalignés). Ne pas réintroduire de rotation sans corriger
    _xml_fil pour tenir compte de comp.angle.
    Tout composant du bloc absent de `roles` (satellite) est placé par la
    grille compacte existante, sous la disposition canonique — jamais perdu.

    @param comps Composants du bloc (Composant/Component).
    @param roles {'aop': [...], 'Zin': [...], 'Zf': [...]}.
    @param x, y Origine du bloc.
    @return dict {ref: (x, y, angle)} pour les rôles connus,
            {ref: (x, y)} pour les satellites.
    """
    pos = {}
    refs_du_bloc = {c.ref for c in comps}
    x_aop, y_aop = x + 2 * _PAS_X_BLOC, y + _PAS_Y_BLOC
    for ref in roles.get('aop', []):
        if ref in refs_du_bloc:
            pos[ref] = (x_aop, y_aop, 0)
    for j, ref in enumerate(roles.get('Zin', [])):
        if ref in refs_du_bloc:
            pos[ref] = (x + j * _PAS_X_BLOC, y_aop, 0)
    for j, ref in enumerate(roles.get('Zf', [])):
        if ref in refs_du_bloc:
            pos[ref] = (x_aop + j * _PAS_X_BLOC, y, 0)
    restants = [c for c in comps if c.ref not in pos]
    pos.update(_positionner_grille_compacte(restants, x, y + 2 * _PAS_Y_BLOC))
    return pos


def _positionner_amplificateur_differentiel(comps, roles, x: int, y: int) -> dict:
    """@brief Gabarit canonique de l'amplificateur différentiel.

    Deux chemins d'entrée empilés autour de l'AOP : Zf (contre-réaction,
    IN-) strictement au-dessus (même convention que Zf de l'ampli
    inverseur), Z1 (entrée IN-) à la même hauteur que l'AOP (même
    convention que Zin de l'ampli inverseur), puis Z3 (entrée IN+) une
    ligne EN DESSOUS de l'AOP, et Zg (référence masse de IN+) encore une
    ligne en dessous, alignée sous l'AOP. Angle toujours 0 (même raison
    que l'ampli inverseur — cf. sa docstring).

    @param comps Composants du bloc (Composant/Component).
    @param roles {'aop': [...], 'Z1': [...], 'Zf': [...], 'Z3': [...], 'Zg': [...]}.
    @param x, y Origine du bloc.
    @return dict {ref: (x, y, angle)} pour les rôles connus,
            {ref: (x, y)} pour les satellites.
    """
    pos = {}
    refs_du_bloc = {c.ref for c in comps}
    x_aop, y_aop = x + 2 * _PAS_X_BLOC, y + _PAS_Y_BLOC
    for ref in roles.get('aop', []):
        if ref in refs_du_bloc:
            pos[ref] = (x_aop, y_aop, 0)
    for j, ref in enumerate(roles.get('Z1', [])):
        if ref in refs_du_bloc:
            pos[ref] = (x + j * _PAS_X_BLOC, y_aop, 0)
    for j, ref in enumerate(roles.get('Zf', [])):
        if ref in refs_du_bloc:
            pos[ref] = (x_aop + j * _PAS_X_BLOC, y, 0)
    for j, ref in enumerate(roles.get('Z3', [])):
        if ref in refs_du_bloc:
            pos[ref] = (x + j * _PAS_X_BLOC, y_aop + _PAS_Y_BLOC, 0)
    for j, ref in enumerate(roles.get('Zg', [])):
        if ref in refs_du_bloc:
            pos[ref] = (x_aop + j * _PAS_X_BLOC, y_aop + 2 * _PAS_Y_BLOC, 0)
    restants = [c for c in comps if c.ref not in pos]
    pos.update(_positionner_grille_compacte(restants, x, y + 3 * _PAS_Y_BLOC))
    return pos


_POSITIONNEURS_PAR_MOTIF = {
    "Amplificateur inverseur (AOP)": _positionner_amplificateur_inverseur,
}


def _positionner_composants_bloc(bloc: _Bloc, x: int, y: int) -> dict:
    """@brief Place les composants a l'interieur d'un bloc visuel.

    @param bloc Bloc de circuit detecte.
    @param x Origine horizontale du bloc.
    @param y Origine verticale du bloc.
    @return dict {ref -> (x, y)} ou {ref -> (x, y, angle)} pour les
            montages avec un gabarit canonique. Positions absolues.
    """
    positionneur = _POSITIONNEURS_PAR_MOTIF.get(bloc.label)
    if positionneur is not None and bloc.roles:
        return positionneur(bloc.comps, bloc.roles, x, y)
    if "commande de relais" in bloc.label.lower():
        return _positionner_commande_relais(bloc.comps, x, y)
    if "pont diviseur" in bloc.label.lower():
        return _positionner_pont_diviseur(bloc.comps, x, y)
    label_low = bloc.label.lower()
    if any(k in label_low for k in ("aop", "amplificateur", "comparateur", "intégrateur",
                                     "dérivateur", "suiveur", "bascule", "sommateur")):
        return _positionner_aop(bloc.comps, x, y)
    if any(k in label_low for k in ("filtre rc", "absorbeur rc", "condensateur de découp")):
        return _positionner_rc(bloc.comps, x, y)
    return _positionner_grille_compacte(bloc.comps, x, y)


def _positionner_commande_relais(comps, x: int, y: int) -> dict[str, tuple[int, int]]:
    """@brief Gabarit compact pour relais + transistor/MOSFET + diode de roue libre."""
    pos = {}
    relais = [c for c in comps if c.type == "K"]
    switchs = [c for c in comps if c.type in {"Q", "M"}]
    diodes = [c for c in comps if c.type == "D"]
    autres = [c for c in comps if c.type not in {"K", "Q", "M", "D"}]

    if relais:
        pos[relais[0].ref] = (x, y)
    if switchs:
        pos[switchs[0].ref] = (x + _PAS_X_BLOC, y + _PAS_Y_BLOC)
    if diodes:
        pos[diodes[0].ref] = (x + 2 * _PAS_X_BLOC, y)

    restants = relais[1:] + switchs[1:] + diodes[1:] + autres
    pos.update(_positionner_grille_compacte(restants, x, y + 2 * _PAS_Y_BLOC))
    return pos


def _positionner_pont_diviseur(comps, x: int, y: int) -> dict[str, tuple[int, int]]:
    """@brief Gabarit vertical pour un pont diviseur et ses annexes eventuelles."""
    pos = {}
    resistances = [c for c in comps if c.type == "R"]
    autres = [c for c in comps if c.type != "R"]
    for j, comp in enumerate(resistances[:2]):
        pos[comp.ref] = (x, y + j * _PAS_Y_BLOC)
    for j, comp in enumerate(resistances[2:] + autres):
        pos[comp.ref] = (x + _PAS_X_BLOC, y + j * _PAS_Y_BLOC)
    return pos


def _positionner_aop(comps, x: int, y: int) -> dict[str, tuple[int, int]]:
    """@brief Gabarit AOP : opamp centré, résistances à gauche/droite, condensateurs en bas."""
    pos = {}
    aops = [c for c in comps if c.type in {"U", "AOP"}]
    resistances = [c for c in comps if c.type == "R"]
    caps = [c for c in comps if c.type == "C"]
    autres = [c for c in comps if c.type not in {"U", "AOP", "R", "C"}]

    if aops:
        pos[aops[0].ref] = (x + _PAS_X_BLOC, y)
    for j, r in enumerate(resistances[:2]):
        pos[r.ref] = (x + j * 2 * _PAS_X_BLOC, y + _PAS_Y_BLOC)
    restants = aops[1:] + resistances[2:] + caps + autres
    pos.update(_positionner_grille_compacte(restants, x, y + 2 * _PAS_Y_BLOC))
    return pos


def _positionner_rc(comps, x: int, y: int) -> dict[str, tuple[int, int]]:
    """@brief Gabarit RC : résistance à gauche, condensateur à droite.
    Si pas de résistance (cap seul), le condensateur est placé à x sans offset."""
    pos = {}
    resistances = [c for c in comps if c.type == "R"]
    caps = [c for c in comps if c.type == "C"]
    autres = [c for c in comps if c.type not in {"R", "C"}]

    if resistances:
        pos[resistances[0].ref] = (x, y)
        if caps:
            pos[caps[0].ref] = (x + _PAS_X_BLOC, y)
        restants = resistances[1:] + caps[1:] + autres
    else:
        if caps:
            pos[caps[0].ref] = (x, y)
        restants = caps[1:] + autres
    pos.update(_positionner_grille_compacte(restants, x, y + _PAS_Y_BLOC))
    return pos


def _positionner_grille_compacte(comps, x: int, y: int) -> dict[str, tuple[int, int]]:
    """@brief Placement par defaut en petite grille 2 colonnes."""
    return {
        comp.ref: (x + (j % 2) * _PAS_X_BLOC, y + (j // 2) * _PAS_Y_BLOC)
        for j, comp in enumerate(comps)
    }


def _ids_groupes_par_ref(blocs) -> dict[str, int]:
    """@brief Associe chaque référence composant à son identifiant de groupe BoardSCH.

    @param blocs Blocs de mise en page issus de _grouper_par_circuit().
    @return dict {ref -> group_id}; les IDs commencent à 1.
    """
    ids = {}
    for gid, bloc in enumerate(blocs, start=1):
        for comp in bloc.comps:
            ids[comp.ref] = gid
    return ids


def generer_xml(composants, resultats=None, results=None) -> str:
    """
    @brief Convertit une liste de composants en schéma BoardSCH XML.

    Si `resultats` (sortie de detecteur.analyser()) est fourni, les composants
    sont groupés par circuit détecté. Sinon, grille simple.

    @param composants Liste des composants à représenter.
    @param resultats Résultats d'analyse pour grouper par circuit (optionnel).
    @param results Alias anglais de `resultats`.
    @return str Document XML BoardSCH.
    """
    gen = _Generateur()
    PER_RANGEE = 4

    resultats = resultats or results   # accepter les deux noms de paramètre
    blocs = _grouper_par_circuit(composants, resultats) if resultats else []
    positions = _positionner_blocs(blocs) if blocs else None
    ids_groupes = _ids_groupes_par_ref(blocs) if blocs else {}

    ref_vers_cid = {}
    ref_vers_map = {}
    for i, comp in enumerate(composants):
        pinout = getattr(comp, "pinout", None)
        if pinout:
            # Contour + brochage REELS (Task 1/4) : `_xml_composant` dessine
            # chaque <DataPin> par NOM reel, indexe par `sorted(comp.pinout)`
            # (voir `_Generateur._idx_broche`, branche pinout). Le plan
            # catalogue (_TYPE_VERS_FORME) n'a donc RIEN a faire ici pour le
            # cablage : passer par lui desynchronise le NodeL du fil et le
            # <DataPin> reellement ecrit (bug trouve en boucle visuelle,
            # 2026-08-07 -- cf. task7-visual-loop-finding.md).
            #
            # <Name> : garder `comp.type` ("AMP", "X"...) plutot que le
            # neutraliser en "PuceN" comme avant -- "PuceN" resout DANS
            # _NOM_VERS_TYPE (catalogue), ce qui forcait `lire_xml` a
            # passer par un second garde de reclassification heuristique
            # (noms de broches non-numeriques) pour retrouver ce composant :
            # un type reel dont TOUTES les broches ont des noms numeriques
            # ('1','2'...  cas COURANT, pas marginal, d'un type cree sans
            # renommer ses broches) ratait ce garde et perdait sa forme en
            # silence a chaque aller-retour (trouve en testant AMP/ANT/BOU,
            # component_library.json). `comp.type` ne collisionne avec
            # AUCUNE entree du catalogue (lettres de type R/C/L/U/X... ou
            # cles custom) -> `correspondance is None` des la premiere passe,
            # qui capture le contour/brochage reels SANS heuristique.
            n = next((t for t in _TAILLES_PUCE if t >= max(len(pinout), 1)),
                     _TAILLES_PUCE[-1])
            nom_forme = comp.type if comp.type not in _NOM_VERS_TYPE else f"Puce{n}"
            # None = marqueur : le bouclage de cablage plus bas doit router
            # ce composant par NOM de broche (gen._idx_broche), pas par le
            # catalogue.
            plan_broches = None
        else:
            spec = _TYPE_VERS_FORME.get(comp.type)
            # Puce du catalogue (broches TOUTES numérotées, ex. NE555/74HC00) :
            # la forme statique "AOP" 3 broches nommées perdrait chaque net
            # (plan sans clé numérique -> broches silencieusement non émises).
            # -> forme DIP générique PuceN, plan identité. Un U à broches
            # nommées (IN+/IN-/OUT) garde la forme AOP historique.
            if (spec is None or comp.type == "U") and comp.pins \
                    and all(k.isdigit() for k in comp.pins):
                n = next((t for t in _TAILLES_PUCE
                          if t >= max(int(k) for k in comp.pins)), None)
                # PLAFOND : au-delà de 16 broches (max _TAILLES_PUCE), n=None ->
                # retombée forme AOP = broches numérotées perdues (comportement
                # pré-Puce). Couvre tout le catalogue v1 (max 16) ; pour un DIP
                # 20/28/40, ajouter la taille à _TAILLES_PUCE suffit. Les boîtiers
                # 3 broches (7805/LM317) arrondissent à Puce4 (4e broche en l'air,
                # cosmétique — net singleton, aucune collision).
                if n is not None:
                    spec = (f"Puce{n}", {k: k for k in comp.pins})
            if spec is None and comp.pins:
                # Dernier recours : boîte DIP générique, broches placées dans
                # l'ORDRE. Sans cela `spec is None` supprimait le composant EN
                # SILENCE — les 22 connecteurs (type J) des vraies cartes
                # disparaissaient à l'export, avec toutes leurs liaisons.
                noms = list(comp.pins)
                n = next((t for t in _TAILLES_PUCE if t >= len(noms)), _TAILLES_PUCE[-1])
                spec = (f"Puce{n}",
                        {nom: str(i + 1) for i, nom in enumerate(noms[:n])})
                if len(noms) > n:
                    _log.warning(
                        "%s : %d broches > %d (plus grand boîtier disponible) — "
                        "les broches au-delà ne sont pas exportées",
                        comp.ref, len(noms), n)
            if spec is None:
                continue
            nom_forme, plan_broches = spec
            # Une broche dont le NOM n'est pas au plan (D1 en '-'/'+', U2.1 en
            # 'C'/'E' sur les vraies cartes) était ignorée plus bas -> liaisons
            # perdues EN SILENCE. On lui attribue un emplacement LIBRE de la forme.
            # COPIE obligatoire : les plans de _TYPE_VERS_FORME sont partagés au
            # niveau module, les compléter en place empoisonnerait les exports
            # suivants.
            inconnues = [p for p in comp.pins if p not in plan_broches]
            if inconnues:
                plan_broches = dict(plan_broches)
                # Emplacements réellement pris par CE composant — pas tous les
                # alias du plan : la forme Diode mappe {A,K,1,2} sur DEUX broches
                # physiques seulement, donc « tout est occupé » serait faux.
                occupees = {plan_broches[p] for p in comp.pins if p in plan_broches}
                libres = [p for p in _FORME.get(nom_forme, {}).get("pins", {})
                          if p not in occupees]
                for nom_broche in inconnues:
                    if not libres:
                        _log.warning("%s : broche %r sans emplacement libre sur %s",
                                     comp.ref, nom_broche, nom_forme)
                        break
                    plan_broches[nom_broche] = libres.pop(0)
        angle = 0
        if positions and comp.ref in positions:
            pos_comp = positions[comp.ref]
            x, y = pos_comp[0], pos_comp[1]
            if len(pos_comp) > 2:
                angle = pos_comp[2]
        else:
            x = 250 + (i % PER_RANGEE) * _LARG_COMP
            y = 250 + (i // PER_RANGEE) * _HAUT_RANGEE
        cid = gen.ajouter(nom_forme, comp.value, x=x, y=y, angle=angle, ref=comp.ref,
                          group_id=ids_groupes.get(comp.ref, 0),
                          primitives=getattr(comp, "primitives", None),
                          pinout=getattr(comp, "pinout", None))
        ref_vers_cid[comp.ref] = cid
        ref_vers_map[comp.ref] = plan_broches

    nets: dict = {}
    for comp in composants:
        if comp.ref not in ref_vers_cid:
            continue
        cid = ref_vers_cid[comp.ref]
        plan_broches = ref_vers_map[comp.ref]
        for broche_lib, net in comp.pins.items():
            if not net or net == "NC":
                continue
            if plan_broches is None:
                # Composant a brochage reel (marqueur pose plus haut) : le
                # NOM de broche EST la reference de cablage -- resolu plus
                # bas par `gen._idx_broche` sur `comp.pinout`, pas via le
                # catalogue. Une broche absente du pinout reel (ne devrait
                # pas arriver, mais Composant.pins/.pinout peuvent diverger)
                # est ignorée EN SILENCE, comme le fait déjà le `.get()`
                # catalogue ci-dessous pour une broche hors plan.
                if broche_lib not in comp.pinout:
                    continue
                broche_forme = broche_lib
            else:
                broche_forme = plan_broches.get(broche_lib)
                if broche_forme is None:
                    continue
            nets.setdefault(net, []).append((cid, broche_forme))

    # Noms canoniques ERetroDesign pour les rails d'alimentation (Lib.xml)
    _NOM_ALIM_LIB = {"GND": "GND", "AGND": "GND", "VCC": "VCC+", "Vss": "VCC-"}

    for net, broches in nets.items():
        sym = "GND" if is_gnd(net) else ("VCC" if is_power(net) else None)
        if sym:
            rail = net.lstrip('/').upper()
            broche_pwr = "GND" if sym == "GND" else "VCC"
            nom_lib = _NOM_ALIM_LIB.get(sym, sym)
            for gid, broches_groupe in _grouper_broches_alim(gen, broches).items():
                px, py = _positionner_symbole_alim(gen, broches_groupe, sym, gid)
                # nom_lib = nom reconnu par ERetroDesign ; rail = valeur affichée
                pcid = gen.ajouter(nom_lib, rail, x=px, y=py, forme=sym, group_id=gid)
                for (cid, bp) in broches_groupe:
                    _relier_par_idx(gen, pcid, _idx_broche_auto(gen, pcid, broche_pwr),
                                    cid, _idx_broche_auto(gen, cid, bp))
        else:
            for k in range(len(broches) - 1):
                c1, bp1 = broches[k]; c2, bp2 = broches[k+1]
                _relier_par_idx(gen, c1, _idx_broche_auto(gen, c1, bp1),
                                c2, _idx_broche_auto(gen, c2, bp2))

    return gen.vers_xml()


def _grouper_broches_alim(gen, broches) -> dict:
    """@brief Regroupe les broches d'un rail par groupe BoardSCH.

    @param gen Generateur contenant les composants deja places.
    @param broches Liste (cid, broche_forme) connectee au meme rail.
    @return dict {group_id -> [(cid, broche_forme)]}.
    """
    groupes = {}
    for cid, bp in broches:
        groupes.setdefault(gen._comps[cid].group_id, []).append((cid, bp))
    return groupes


def _positionner_symbole_alim(gen, broches, sym: str, group_id: int) -> tuple[int, int]:
    """@brief Place un symbole VCC/GND pres des composants qu'il alimente.

    @param gen Generateur contenant les composants deja places.
    @param broches Broches cible du rail.
    @param sym Forme d'alimentation ('VCC' ou 'GND').
    @param group_id Groupe BoardSCH concerne (0 si aucun).
    @return tuple Position (x, y) du symbole.
    """
    points = []
    for cid, bp in broches:
        comp = gen._comps[cid]
        forme_nom = _ALIAS.get(comp.shape or comp.name, comp.shape or comp.name)
        pins = _FORME.get(forme_nom, {}).get("pins", {})
        if bp in pins:
            lx, ly, _ = pins[bp]
            points.append((comp.x + lx, comp.y + ly))
    if not points:
        return (250, 250 + group_id * _HAUT_RANGEE)

    x = int(sum(px for px, _ in points) / len(points))
    if sym == "GND":
        y = max(py for _, py in points) + 70
    else:
        y = min(py for _, py in points) - 80
    return (x, int(y))


def _idx_broche_forme(gen, cid, broche) -> int:
    """@brief Index d'une broche nommée sur un composant déjà placé dans le générateur.

    @param gen Générateur (_Generateur).
    @param cid Identifiant du composant.
    @param broche Nom de la broche.
    @return int Index de broche dans la forme.
    """
    comp = gen._comps[cid]
    cle = comp.shape or comp.name
    nom = _ALIAS.get(cle, cle)
    return _FORME[nom]["pins"][broche][2]


def _idx_broche_auto(gen, cid, broche) -> int:
    """@brief Index de broche, routé par brochage réel si dispo, catalogue sinon.

    `generer_xml()` câble aussi bien des composants au catalogue (symboles
    GND/VCC, formes historiques) que des composants à brochage RÉEL
    (Task 1/4, `comp.pinout`). `_idx_broche_forme` (catalogue, conserve son
    repli sur `comp.shape` pour les symboles d'alimentation dont le nom
    affiché diffère du nom de forme, ex. VCC+ / VCC) ne connaît pas
    `comp.pinout` ; `_Generateur._idx_broche` (instance) le connaît déjà
    mais n'était atteint que via `.relier()`, jamais par le bouclage de
    câblage de `generer_xml()` -- d'où le bug (voir
    task7-visual-loop-finding.md, 2026-08-07). Ce garde-fou choisit la bonne
    branche composant par composant, pour que les deux familles cohabitent
    dans le même bouclage (ex. un rail GND catalogue relié à un composant à
    brochage réel).

    @param gen Générateur (_Generateur).
    @param cid Identifiant du composant.
    @param broche Nom de la broche.
    @return int Index de broche (dans le pinout réel ou dans la forme catalogue).
    """
    if gen._comps[cid].pinout:
        return gen._idx_broche(cid, broche)
    return _idx_broche_forme(gen, cid, broche)


def _relier_par_idx(gen, c1, p1, c2, p2):
    """@brief Crée un fil entre deux broches déjà résolues en index.

    @param gen Générateur (_Generateur, muté en place).
    @param c1 Composant source.
    @param p1 Index de broche source.
    @param c2 Composant destination.
    @param p2 Index de broche destination.
    @return None
    """
    wid = gen._wire_id; gen._wire_id += 1
    gen._wires.append(_Wire(wid, c1, p1, c2, p2, _groupe_commun(gen, c1, c2)))


def _groupe_commun(gen, c1, c2) -> int:
    """@brief Groupe commun à deux composants, si les deux appartiennent au même.

    @param gen Générateur contenant les composants.
    @param c1 Identifiant du premier composant.
    @param c2 Identifiant du second composant.
    @return int GpId commun, ou 0 si aucun groupe commun.
    """
    g1 = gen._comps[c1].group_id
    g2 = gen._comps[c2].group_id
    return g1 if g1 and g1 == g2 else 0


def _bool_xml(valeur: bool) -> str:
    """@brief Convertit un booléen Python au format texte attendu par BoardSCH."""
    return "true" if valeur else "false"


# Alias anglais pour la compatibilité
components_to_xml = generer_xml

# Ajouter les méthodes anglaises sur _Generateur pour la compatibilité des tests
_Generateur.add     = _Generateur.ajouter
_Generateur.connect = _Generateur.relier
_Generateur.to_xml  = _Generateur.vers_xml

# Exposer BoardSCHGenerator pour les tests qui l'utilisent directement
BoardSCHGenerator = _Generateur


# =============================================================================
# LECTURE XML (fichier BoardSCH → liste de Composant)
# =============================================================================

_NOM_VERS_TYPE = {
    # ── Résistances (FR / EN) ─────────────────────────────────────────────────
    'Résistance':  ('R', {'1': '1', '2': '2'}),
    'Resistance':  ('R', {'1': '1', '2': '2'}),
    'Resistor':    ('R', {'1': '1', '2': '2'}),
    # ── Condensateurs ────────────────────────────────────────────────────────
    'Capa':        ('C', {'+': '1', '-': '2'}),
    'Condensateur':('C', {'+': '1', '-': '2'}),
    'Capacitor':   ('C', {'+': '1', '-': '2'}),
    'Cap':         ('C', {'+': '1', '-': '2'}),
    # ── Inductances ──────────────────────────────────────────────────────────
    'Bobine':      ('L', {'1': '1', '2': '2'}),
    'Inductance':  ('L', {'1': '1', '2': '2'}),
    'Inductor':    ('L', {'1': '1', '2': '2'}),
    'Self':        ('L', {'1': '1', '2': '2'}),
    # ── Diodes ───────────────────────────────────────────────────────────────
    # '+'/'-' : convention de polarite vue sur de vraies diodes ERetroDesign
    # (cartes industrielles et schemas de test) — '+' = anode (le courant y
    # entre en polarisation directe). Sans ce plan, ces broches restaient
    # '+'/'-' telles quelles et les 4 detecteurs de diode qui lisent
    # comp.pins.get('A')/.get('K') par nom litteral (roue libre, ESD,
    # redresseur simple, detecteur de crete) ignoraient ces diodes en silence.
    'Diode':       ('D', {'A': 'A', 'K': 'K', '1': 'A', '2': 'K', '+': 'A', '-': 'K'}),
    'LED':         ('D', {'A': 'A', 'K': 'K', '1': 'A', '2': 'K', '+': 'A', '-': 'K'}),
    'Zener':       ('D', {'A': 'A', 'K': 'K', '1': 'A', '2': 'K', '+': 'A', '-': 'K'}),
    'TVS':         ('D', {'A': 'A', 'K': 'K', '1': 'A', '2': 'K', '+': 'A', '-': 'K'}),
    # ── Puces génériques à broches numérotées (catalogue, plan vide =
    #    passthrough : broche_lib = Pname tel quel) ─────────────────────────
    'Puce4':       ('U', {}),
    'Puce8':       ('U', {}),
    'Puce14':      ('U', {}),
    'Puce16':      ('U', {}),
    # ── AOP ──────────────────────────────────────────────────────────────────
    'AOP':         ('U', {'+': 'IN+', '-': 'IN-', 's': 'OUT'}),
    'OpAmp':       ('U', {'+': 'IN+', '-': 'IN-', 's': 'OUT'}),
    'Op-Amp':      ('U', {'+': 'IN+', '-': 'IN-', 's': 'OUT'}),
    # ── Transistors BJT ──────────────────────────────────────────────────────
    '2N2B':        ('Q', {'G': 'B', 'E': 'E', 'C': 'C'}),
    'Transistor':  ('Q', {'B': 'B', 'C': 'C', 'E': 'E'}),
    'BJT':         ('Q', {'B': 'B', 'C': 'C', 'E': 'E'}),
    # ── MOSFET ───────────────────────────────────────────────────────────────
    'MOSFET':      ('M', {'G': 'G', 'D': 'D', 'S': 'S'}),
    # ── Relais ───────────────────────────────────────────────────────────────
    'Relais':        ('K', {'A1': 'A1', 'A2': 'A2', '11': '11', '12': '12', '14': '14'}),
    'Relais_1FormC': ('K', {'A1': 'A1', 'A2': 'A2', 'COM': '11', 'NC': '12', 'NO': '14'}),
    'Relay':         ('K', {'A1': 'A1', 'A2': 'A2', '11': '11', '12': '12', '14': '14'}),
    # ── Fusibles ─────────────────────────────────────────────────────────────
    'Fusible':     ('F', {'1': '1', '2': '2'}),
    'Fuse':        ('F', {'1': '1', '2': '2'}),
    # ── Connecteurs (ignorés pour la détection mais pas un crash) ────────────
    # Connecteur/Connector → None signale "inconnu mais attendu"
}

_NOMS_ALIMENTATION = {
    'GND', 'AGND', 'PGND', 'DGND', 'VCC', 'VDD', 'VSS', 'Vss', 'Vdd', 'Vcc',
    'VBUS', 'VMOT', 'VREG', 'VREF', 'VOUT', '+5V', '+3.3V', '+12V', '-12V',
    'PE', 'EARTH', 'CHASSIS',
    'VCC+', 'VCC-',  # noms canoniques ERetroDesign
}

# Broches critiques par type (manquante → warning)
_BROCHES_CRITIQUES: dict[str, list] = {
    'U': ['IN+', 'IN-', 'OUT'],
    'Q': ['B', 'C', 'E'],
    'M': ['G', 'D', 'S'],
    'D': ['A', 'K'],
}


class ListeComposantsXML(list):
    """
    @brief Liste de Composant retournée par lire_xml(), compatible avec list.

    Attribut .warnings : avertissements non-bloquants rencontrés pendant la lecture.
    Attribut .source : SourceXML (arbre d'origine + pont ref->element) si la
    liste vient d'un lire_xml, None sinon (ex. liste construite à la main).
    """
    def __init__(self, composants=None):
        """@brief Initialise la liste de composants XML et ses avertissements.

        @param composants Composants initiaux à placer dans la liste (optionnel).
        @return None
        """
        super().__init__(composants or [])
        self.warnings: list[str] = []
        self.groupes_puces: dict[str, str] = {}
        self.source = None

_NET_ALIMENTATION: dict[str, str] = {
    'GND': 'GND', 'AGND': 'GND', 'PGND': 'GND', 'DGND': 'GND',
    'VCC': 'VCC', 'Vcc': 'VCC', '+5V': 'VCC', '+3.3V': 'VCC', '+12V': 'VCC',
    'VDD': 'VDD', 'Vdd': 'VDD', 'VSS': 'VSS', 'Vss': 'VSS',
    'VBUS': 'VBUS', 'VMOT': 'VMOT', 'VREG': 'VREG',
    'VREF': 'VREF', 'VOUT': 'VOUT', '-12V': '-12V',
}


def _analyser_ref_noeud(nid: str) -> tuple:
    """@brief Parse 'compId_pinIdx_...' → (compId, pinIdx).

    @param nid Référence de nœud BoardSCH (ex. '3_1_0_42').
    @return tuple (compId, pinIdx) en entiers.
    @throws ValueError Si la référence est mal formée.
    """
    parties = nid.split('_')
    if len(parties) < 2:
        raise ValueError(f"Référence de nœud invalide : {nid!r}")
    try:
        return int(parties[0]), int(parties[1])
    except ValueError:
        raise ValueError(f"Référence de nœud invalide : {nid!r}")


def _analyser_ref_packee(nid: str) -> tuple:
    """@brief Parse le vieux format de ref concaténée à 4 chiffres 'CPXX'
    (ex. '2000') → (compId, pinIdx).

    Milliers = index composant (position dans CmpntL), centaines = index
    broche ; les 2 derniers chiffres sont un compteur/dédoublonnage du C#
    ignoré ici (non porteur de sens électrique). Dialecte encore plus
    ancien que i_j_u_v : observé sur les fichiers sans aucun NodeL
    (ex. SaveDiag.xml). Volontairement réservé aux fils du schéma
    principal (lineL/Line) — jamais aux fils internes de puce composée
    (CCLine), où la même plage numérique désigne un tout autre référentiel
    (adresses locales au boîtier) et où ce décodage produirait des unions
    fausses et silencieuses.

    @param nid Référence de nœud BoardSCH packée (exactement 4 chiffres).
    @return tuple (compId, pinIdx) en entiers.
    @throws ValueError Si la référence n'est pas composée de 4 chiffres.
    """
    if len(nid) != 4 or not nid.isdigit():
        raise ValueError(f"Référence packée invalide : {nid!r}")
    valeur = int(nid)
    return valeur // 1000, (valeur % 1000) // 100


def _capturer_entete_source(chemin: str, tag_racine: str):
    """@brief Capture ce que ET.parse() detruit silencieusement au parsing.

    `xml.etree.ElementTree` (contrairement a lxml) ne conserve PAS les
    declarations `xmlns:*` de la racine quand elles ne qualifient aucun
    tag/attribut, et ne rejoue pas le prologue `<?xml ...?>` a la
    serialisation. Cette info doit donc etre captee ICI, au moment de la
    lecture — la reconstruire plus tard reviendrait a la deviner.

    Best-effort explicitement : un echec de capture (fichier illisible en
    utf-8, etc.) ne doit jamais faire echouer la lecture principale, qui a
    deja reussi via ET.parse() au moment ou cette fonction est appelee.

    Tout se lit sur le MEME texte, en une passe. La version precedente tirait
    les namespaces d'un `ET.iterparse(events=('start-ns',))`, ce qui coutait
    un second parsing complet du document (63 ms contre 43 ms pour le ET.parse
    principal sur `pg carte.xml`, soit 38 % du temps de lecture) pour n'en
    extraire que deux paires de chaines. Trois defauts tombent avec :
      - la portee : `start-ns` remonte les xmlns declares sur N'IMPORTE QUEL
        descendant, qu'on reposait ensuite sur la RACINE — donc une ligne
        modifiee hors GpId, ce que le chantier promet de ne jamais faire ;
      - le namespace par DEFAUT (`xmlns="..."`, prefixe vide) devenait un
        `xmlns:=` litteral, du XML malforme ecrit sous un « Succes » ;
      - le cout, dans un projet qui vise 5000 composants.
    Le motif ci-dessous ne matche que `xmlns:prefixe=` sur la balise racine :
    le defaut (`xmlns=`) est ignore par construction, et lui reste porte par
    ET.parse() quand il qualifie reellement des tags.

    @param chemin Chemin du fichier source (le meme que ET.parse(chemin)).
    @param tag_racine Nom de la balise racine deja parsee (repere la fin
    du texte a capturer, sans en dependre pour le contenu).
    @return tuple (namespaces: list[(prefixe, uri)], avant_racine: str) —
    listes/chaine vides si le fichier n'en portait pas (on ne fabrique rien).
    """
    namespaces: list = []
    avant_racine = ""
    try:
        with open(chemin, 'rb') as f:
            brut = f.read().decode('utf-8')
    except (OSError, UnicodeDecodeError):
        return namespaces, avant_racine

    # Balise racine ouvrante, en tolerant un '>' a l'interieur d'une valeur
    # entre guillemets (d'ou l'alternance guillemets/reste plutot qu'un [^>]*).
    ouvrante = re.search(
        r'<' + re.escape(tag_racine) + r'((?:"[^"]*"|\'[^\']*\'|[^>"\'])*)>', brut)
    if ouvrante:
        avant_racine = brut[:ouvrante.start()]
        namespaces = re.findall(r'xmlns:([\w.-]+)\s*=\s*"([^"]*)"', ouvrante.group(1))

    return namespaces, avant_racine


def lire_xml(chemin: str, alias_catalogue: bool = True) -> list:
    """
    @brief Lit un fichier BoardSCH XML et retourne une liste de Composant.

    Utilise l'algorithme Union-Find pour reconstruire les nœuds électriques
    à partir des fils (lignes) du schéma.

    @param chemin Chemin du fichier .xml BoardSCH.
    @param alias_catalogue False = lecture BRUTE, sans renommage des broches
    par le catalogue — utilisé par l'onglet Saisie pour éditer le fichier
    tel quel.
    @return ListeComposantsXML Composants lus, avec l'attribut .warnings.
    @throws ValueError Si le fichier XML est invalide.
    """
    try:
        arbre = ET.parse(chemin)
    except ET.ParseError as e:
        raise ValueError(f"Fichier XML invalide : {e}") from e
    racine = arbre.getroot()
    # Capture, AVANT toute autre chose, ce que ET.parse() vient de detruire
    # silencieusement (prologue, xmlns:* non qualifiants) — c'est le seul
    # endroit ou `chemin` est encore en portee pour le relire.
    namespaces_source, avant_racine_source = _capturer_entete_source(chemin, racine.tag)

    # Étape 1 : extraire tous les composants du fichier.
    # Indexation par POSITION dans CmpntL (sémantique du C# ERetroDesign) :
    # les vrais fichiers portent des <id> dupliqués (id=0 partout) qui
    # écraseraient les entrées d'un dict indexé par id.
    avertissements: list = []
    elements: dict[int, dict] = {}
    for idx, item in enumerate(racine.findall('.//CmpntL/DataItem')):
        nom    = (item.findtext('Name') or '').strip()
        valeur = (item.findtext('value') or '').strip()
        broches = []
        for pidx, dp in enumerate(item.findall('.//datapin/DataPin')):
            pnum = (dp.findtext('Pnumber') or '').strip()
            pnom = (dp.findtext('Pname') or '').strip()
            # ERetroDesign : l'identité de broche vit dans Pnumber (Pname
            # souvent vide) ; les passifs n'ont ni l'un ni l'autre →
            # numérotation par position pour ne pas écraser les clés.
            refs = [(s.text or '').strip() for s in dp.findall('NodeL/string')]
            broches.append({'pname': pnum or pnom or str(pidx + 1),
                            'refs': [r for r in refs if r]})
        typ_txt = (item.findtext('typ') or '').strip()
        typc = chr(int(typ_txt)) if typ_txt.isdigit() and 0 < int(typ_txt) < 0x110000 else ''
        elements[idx] = {'id': idx, 'name': nom, 'value': valeur, 'pins': broches,
                         'rail': eretro.classer_rail(typc, valeur, len(broches), nom),
                         'geo': eretro.extraire_geometrie(item),
                         'xml': item}

    # Étape 1 bis : puces composées ERetroDesign (CCmpntL) — dépliées.
    elements_cc, fils_cc, avert_cc = eretro.extraire_composes(racine, len(elements))
    elements.update(elements_cc)
    avertissements.extend(avert_cc)

    # Étape 2 : Union-Find pour regrouper les broches reliées par des fils
    parent: dict[tuple, tuple] = {}

    def trouver(x):
        """@brief Trouve la racine Union-Find d'une broche avec compression de chemin.

        @param x Tuple (id composant, index broche).
        @return tuple Racine canonique du groupe de broches.
        """
        if x not in parent:
            parent[x] = x
        racine_uf = x
        while parent[racine_uf] != racine_uf:
            racine_uf = parent[racine_uf]
        noeud = x
        while parent[noeud] != racine_uf:
            parent[noeud], noeud = racine_uf, parent[noeud]
        return racine_uf

    def unir(x, y):
        """@brief Fusionne deux groupes Union-Find de broches reliées.

        @param x Première broche (id composant, index broche).
        @param y Deuxième broche (id composant, index broche).
        @return None
        """
        px, py = trouver(x), trouver(y)
        if px != py:
            parent[px] = py

    for cid, comp in elements.items():
        for pidx in range(len(comp['pins'])):
            trouver((cid, pidx))

    # Index {chaîne de ref NodeL → (composant, broche)} : la connexité
    # ERetroDesign se résout par égalité de chaînes (règle du C# lui-même).
    # Exception bornée (arbitrage patron 2026-07-20) : les refs à
    # EXACTEMENT 4 chiffres des fils lineL/Line sont décodées en dernier
    # recours via _analyser_ref_packee (voir resoudre_extremite plus bas) ;
    # les refs 5+ chiffres restent ambiguës et rejetées.
    ref_vers_broche: dict[str, tuple] = {}
    for cid, comp in elements.items():
        for pidx, b in enumerate(comp['pins']):
            for r in b['refs']:
                ref_vers_broche.setdefault(r, (cid, pidx))

    def resoudre_extremite(ref, autoriser_packe=False):
        """@brief (composant, broche) pour une extrémité de fil, ou None.

        Égalité NodeL d'abord ; fallback sur le format i_j_u_v (dialecte
        natif sans NodeL) avec garde d'existence ; puis, si autorisé, le
        format packé à 4 chiffres des tout premiers fichiers (SaveDiag.xml).

        @param ref Chaîne CFirst/CLast brute.
        @param autoriser_packe Autorise le fallback packé 'CPXX' (réservé
        aux fils du schéma principal, jamais aux fils internes de puce).
        @return tuple|None (cid, pidx) valide, ou None si irrésoluble.
        """
        if not ref:
            return None
        broche = ref_vers_broche.get(ref)
        if broche is not None:
            return broche
        try:
            cid, pidx = _analyser_ref_noeud(ref)
        except ValueError:
            if not autoriser_packe:
                return None
            try:
                cid, pidx = _analyser_ref_packee(ref)
            except ValueError:
                return None
        if cid in elements and 0 <= pidx < len(elements[cid]['pins']):
            return (cid, pidx)
        return None

    # Une étiquette de réseau désigne un fil par son AttachedLine, qui est
    # l'INDICE du fil dans lineL (C# : `lLine[nl.AttachedLine].Name = nl.Net`),
    # PAS son <ID> — les vrais fichiers portent des <ID> tous à 0. On mémorise
    # donc, par indice de fil, une broche à laquelle il aboutit.
    ligne_vers_broche: dict[str, tuple] = {}
    lignes_xml = racine.findall('.//lineL/Line')
    lignes_cids: dict[int, tuple] = {}
    for idx_fil, fil in enumerate(lignes_xml):
        cf = (fil.findtext('CFirst') or '').strip()
        cl = (fil.findtext('CLast') or '').strip()
        bf = resoudre_extremite(cf, autoriser_packe=True)
        bl = resoudre_extremite(cl, autoriser_packe=True)
        broche_fil = bf if bf is not None else bl
        if broche_fil is not None:
            ligne_vers_broche[str(idx_fil)] = broche_fil
        if bf is not None and bl is not None:
            unir(bf, bl)
            lignes_cids[idx_fil] = (bf[0], bl[0])
        elif cf or cl:
            avertissements.append(
                f"Fil non résolu : CFirst={cf!r}, CLast={cl!r}"
            )

    # Fils internes des puces composées (CCLine) : nets internes ET ponts X —
    # le C# (Form2.cs) relie une broche externe du boîtier à une broche
    # interne par un CCLine PONT dont CFirst = ref X du NodeL externe et
    # CLast = ref de la broche interne (extrémités toujours distinctes ;
    # deux broches ne partagent jamais la même chaîne NodeL).
    for cf, cl in fils_cc:
        bf, bl = resoudre_extremite(cf), resoudre_extremite(cl)
        if bf is not None and bl is not None:
            unir(bf, bl)
        elif cf or cl:
            avertissements.append(
                f"Fil interne de puce non résolu : CFirst={cf!r}, CLast={cl!r}"
            )

    # Étiquettes de réseau (NetLabels) : même <Net> ⇒ même nœud électrique.
    # Le collègue les pose et les persiste, mais son app C# ne les relie PAS
    # encore à sa netlist ; on fait le câblage ici. Une étiquette désigne un
    # fil par son AttachedLine (ID de Line) ; on unit les broches des fils qui
    # portent le même nom, et ce nom baptise le net.
    label_par_broche: dict[tuple, str] = {}
    premiere_broche_du_label: dict[str, tuple] = {}
    for et in racine.findall('.//NetLabels/NetLabel'):
        nom_label = (et.findtext('Net') or '').strip()
        aid = (et.findtext('AttachedLine') or '').strip()
        if not nom_label or not aid:
            continue
        broche = ligne_vers_broche.get(aid)
        if broche is None:
            continue
        label_par_broche[broche] = nom_label
        if nom_label in premiere_broche_du_label:
            unir(premiere_broche_du_label[nom_label], broche)
        else:
            premiere_broche_du_label[nom_label] = broche

    # Étape 3 : regrouper les broches par nœud électrique
    groupes_nets: dict[tuple, list] = {}
    for cid, comp in elements.items():
        for pidx in range(len(comp['pins'])):
            cle = trouver((cid, pidx))
            groupes_nets.setdefault(cle, []).append((cid, pidx))

    # Étape 4 : nommer les nœuds
    racine_vers_net: dict[tuple, str] = {}
    compteur = 0

    def nom_net(cle):
        """@brief Attribue un nom électrique stable à un groupe de broches.

        @param cle Racine Union-Find du groupe de broches.
        @return str Nom du net (rail reconnu ou NET# généré).
        """
        nonlocal compteur
        if cle in racine_vers_net:
            return racine_vers_net[cle]
        for (cid, _) in groupes_nets.get(cle, []):
            cnom = elements[cid]['name']
            cval = elements[cid].get('value', '')
            # VCC+/VCC- : le nom du rail spécifique est dans <value> (ex. "VMOT_48V")
            if cnom in ('VCC+', 'VCC-') and cval:
                norm_val = cval.lstrip('/').upper()
                if is_power(norm_val) or is_gnd(norm_val):
                    racine_vers_net[cle] = norm_val; return norm_val
            if cnom in _NET_ALIMENTATION:
                racine_vers_net[cle] = _NET_ALIMENTATION.get(cnom, cnom.upper())
                return racine_vers_net[cle]
            rail = elements[cid].get('rail')
            if rail:
                racine_vers_net[cle] = rail; return rail
            norm = cnom.lstrip('/').upper()
            # PE/EARTH/CHASSIS → gardés tels quels, PAS traités comme GND
            if is_protective_earth_net(norm):
                racine_vers_net[cle] = norm; return norm
            if norm not in _NOM_VERS_TYPE and (is_gnd(norm) or is_power(norm)):
                racine_vers_net[cle] = norm; return norm
        # Étiquette de réseau posée par l'utilisateur : son nom baptise le net.
        for m in groupes_nets.get(cle, []):
            if m in label_par_broche:
                racine_vers_net[cle] = label_par_broche[m]
                return racine_vers_net[cle]
        compteur += 1
        net = f'NET{compteur}'
        racine_vers_net[cle] = net; return net

    broche_vers_net: dict[tuple, str] = {}
    for cle, membres in groupes_nets.items():
        net = nom_net(cle)
        for k in membres:
            broche_vers_net[k] = net

    # Étape 5 : construire les objets Composant
    composants = ListeComposantsXML()
    composants.warnings.extend(avertissements)
    compteurs_type: dict[str, int] = {}
    refs_puces: dict[int, str] = {}     # num composé → ref boîtier ('U7')
    compteurs_internes: dict[int, int] = {}
    cid_vers_ref: dict[int, str] = {}   # id composant (elements) → ref émise

    def generer_ref(type_prefix, elem):
        """@brief Réf du composant courant, partagée par les deux branches
        (connue/inconnue) pour que les items internes d'une puce composée
        reçoivent la même ref préfixée <boîtier>.<n> quel que soit leur type.

        @param type_prefix Préfixe de type ('R', 'Q', 'X', ...).
        @param elem Entrée elements[cid] courante (peut porter 'puce').
        @return str Référence du composant.
        """
        puce = elem.get('puce')
        if puce is not None:
            num_puce, nom_puce = puce
            if num_puce not in refs_puces:
                compteurs_type['U'] = compteurs_type.get('U', 0) + 1
                refs_puces[num_puce] = f'U{compteurs_type["U"]}'
                composants.groupes_puces[refs_puces[num_puce]] = nom_puce
            compteurs_internes[num_puce] = compteurs_internes.get(num_puce, 0) + 1
            return f'{refs_puces[num_puce]}.{compteurs_internes[num_puce]}'
        compteurs_type[type_prefix] = compteurs_type.get(type_prefix, 0) + 1
        return f'{type_prefix}{compteurs_type[type_prefix]}'

    for cid in sorted(elements):
        elem = elements[cid]
        nom  = elem['name']

        # Boîtier de puce composée : pass-through Union-Find, non émis.
        if elem.get('emettre') is False:
            continue

        # Symboles d'alimentation → ne sont pas des composants
        if nom in _NOMS_ALIMENTATION:
            continue

        # Symboles d'alimentation ERetroDesign (typ G/V/N, 1 broche)
        if elem.get('rail'):
            continue

        correspondance = _NOM_VERS_TYPE.get(nom) or eretro.mapper_nom(nom)
        par_forme = False
        if correspondance is None:
            # Nom inconnu : dernier recours avant la boîte noire — la forme
            # du symbole (segments/arcs) est consultée UNIQUEMENT ici, jamais
            # quand le nom a déjà résolu le type (non-régression dialecte natif).
            geo = elem.get('geo')
            forme = eretro.classer_par_forme(geo) if geo else None
            if forme is not None:
                correspondance, par_forme = forme, True

        boite_ic = False
        # Catch-all IC : nom réel (composant de premier niveau, pas un fils de
        # puce composée) et suffisamment de broches pour être une vraie IC
        # (pas une forme franche R/C/D/Q déjà tranchée ci-dessus) -> boîte IC
        # honnête étiquetée du nom, jamais une boîte noire X muette ni un faux
        # AOP. Seuil (>=6) volontairement au-dessus des passifs/transfos à
        # petit nombre de broches déjà couverts ailleurs (non-régression
        # test_import_inconnu_reste_boite_x : 'transfo' 4 broches reste X).
        if (correspondance is None and elem.get('puce') is None
                and nom.strip() and len(elem['pins']) >= 6):
            correspondance, boite_ic = ('U', {}), True

        # Reclassification catch-all sur un XML RE-EXPORTE par nous-memes
        # (finding #2, boucle visuelle 2026-08-07) : a l'export, un composant
        # catch-all a brochage reel (comp.pinout) recoit un <Name> neutralise
        # en "PuceN" (jamais son nom d'origine — evite toute collision avec
        # un plan catalogue nomme, cf. commentaire generer_xml ~ligne 1017).
        # Ce "PuceN" resout ici en ('U', {}) via _NOM_VERS_TYPE AVANT d'
        # atteindre ce point -> `correspondance is not None` des la ligne
        # ci-dessus, le catch-all est saute, boite_ic reste False, et
        # _forme_et_brochage_reels() n'est jamais tentee alors que le DataItem
        # contient bel et bien le vrai polygone et les vraies broches
        # nommees. Signal fiable pour distinguer ce cas du "PuceN" catalogue
        # generique authentique (fallback ligne ~1047, transistor/connecteur
        # a broches numerotees) : `elem['value']`, jamais ecrase par le
        # renommage "PuceN" a l'export (`gen.ajouter(nom_forme, comp.value,
        # ...)`) et qui porte encore le nom reel d'origine (ex. "A788J").
        # `not par_forme` exclut le cas ('U', {}) obtenu par classification
        # de FORME (porte logique 3 broches, classer_par_forme) — deja
        # ecarte par le garde >=6 broches ci-dessous, mais explicite ici.
        # Garde revu (revue finale round 1, Important 5+6) : le garde d'origine
        # (`value` + seuil >=6 broches, commit 6f635aa) etait a la fois trop
        # LARGE (un composant catalogue authentique dont la `value` d'origine
        # ne matche aucun alias catalogue -- ex. un transfo/connecteur -- se
        # faisait promouvoir boite_ic a tort, etat ensuite STICKY) et trop
        # ETROIT (bloquait la reclassification de tout catch-all a MOINS de 6
        # broches, notamment un connecteur J a contour reel). `value` et le
        # compte de broches ne distinguent pas de facon fiable "ce PuceN vient
        # d'un vrai comp.pinout" de "ce PuceN vient du fallback catalogue
        # generique" -- mais le NOM des broches, si. `_xml_composant` ecrit
        # les <Pname> du catalogue (branche `else`) TOUJOURS depuis
        # `_FORME[nom_forme]["pins"]`, dont les cles sont litteralement les
        # chaines "1".."n" pour toute forme PuceN, alors que la branche
        # `pinout` ecrit les VRAIS noms de broches (`sorted(comp.pinout)`),
        # numeriques seulement par coincidence rare. Compromis assume : un
        # connecteur reel dont TOUTES les broches ont des noms purement
        # numeriques ("1", "2"...) ne sera pas reclassifie apres un
        # aller-retour -- faux negatif fail-closed accepte (perte silencieuse
        # de fidelite visuelle sur un cas marginal, pas de corruption de
        # donnees). Le seuil >=6 reste inchange pour le garde de PREMIER
        # import ci-dessus (ligne ~1775) -- il n'est retire QUE de ce garde-ci.
        if correspondance == ('U', {}) and not boite_ic and not par_forme:
            if (elem.get('puce') is None
                    and not all(p['pname'].strip().isdigit() for p in elem['pins'])):
                boite_ic = True

        def _forme_et_brochage_reels():
            """Capture le contour/brochage reel via le meme parseur que la
            bibliotheque (`eretro_lib._entree_depuis_dataitem`), ou (None, None)
            si le symbole n'a ni geometrie ni broche exploitable.

            Fail-closed si deux broches physiques se resolvent au meme nom (collision) :
            brochage_reel (dict) les collapse, ce qui desaligne les indices physiques
            et corrompt les nets. Retourne (None, None) pour laisser la construction
            positionnelle par defaut prendre le relais."""
            try:
                _prefix, _entree = eretro_lib._entree_depuis_dataitem(elem['xml'])
            except ValueError:
                return None, None
            if not _entree.get('primitives'):
                return None, None
            brochage_reel = {n: tuple(cd) for n, cd in _entree['brochage'].items()}
            # Detecter les collisions de noms de broches (deux broches physiques
            # avec le meme nom). brochage_reel étant un dict, les collisions
            # réduisent sa taille sous len(elem['pins']).
            if len(brochage_reel) != len(elem['pins']):
                return None, None
            return _entree['primitives'], brochage_reel

        if correspondance is None:
            # Composant inconnu : on le garde sous type 'X' pour ne pas perdre ses connexions
            ref = generer_ref('X', elem)
            cid_vers_ref[cid] = ref
            forme_reelle, brochage_reel = _forme_et_brochage_reels()
            broches = {}
            # Si on a un brochage reel, utiliser SES noms de broches pour les deux dicts
            # (pins et pinout), sinon utiliser la derivation positionnelle par defaut.
            if brochage_reel:
                for pidx, pin_name in enumerate(brochage_reel.keys()):
                    net = broche_vers_net.get((cid, pidx), 'NC')
                    broches[pin_name] = net
            else:
                for pidx, info_b in enumerate(elem['pins']):
                    net = broche_vers_net.get((cid, pidx), 'NC')
                    broches[str(pidx + 1)] = net
            composants.append(Component(ref=ref, type='X', pins=broches, value=elem['value'],
                                        primitives=forme_reelle, pinout=brochage_reel))
            composants.warnings.append(
                f"Composant inconnu '{nom}' (id={cid}) → gardé comme {ref} (type X)"
            )
            continue

        type_prefix, plan = correspondance
        ref = generer_ref(type_prefix, elem)
        cid_vers_ref[cid] = ref
        broches = {}
        for pidx, info_b in enumerate(elem['pins']):
            pnom = info_b['pname']
            # plan None (passif ERetroDesign) : broches par position.
            broche_lib = str(pidx + 1) if plan is None else plan.get(pnom, pnom)
            net = broche_vers_net.get((cid, pidx), 'NC')
            broches[broche_lib] = net
        # Broches AOP standard par défaut — UNIQUEMENT pour les formes à plan
        # nommé (AOP historique). Une puce numérotée (plan vide, forme PuceN)
        # ne doit PAS recevoir IN+/IN-/OUT en NC : ça créerait le mix
        # numéroté/nommé interdit par appliquer_catalogue (un 741 aliasé
        # verrait "2"->"IN-" collisionner avec le IN-='NC' injecté).
        if type_prefix == 'U' and plan:
            for std in ('IN+', 'IN-', 'OUT', 'V+', 'V-'):
                broches.setdefault(std, 'NC')

        # Vérifier les broches critiques manquantes — formes à plan NOMMÉ
        # uniquement : une puce numérotée (PuceN, plan vide) n'a pas encore
        # ses broches fonctionnelles ici (l'aliasing catalogue tourne APRÈS
        # la boucle), le check IN+/IN-/OUT tirerait à faux sur chaque puce.
        manquantes = [
            p for p in _BROCHES_CRITIQUES.get(type_prefix, [])
            if broches.get(p, 'NC') == 'NC'
        ] if plan else []
        if manquantes:
            composants.warnings.append(
                f"{ref} ({nom}): broches critiques non connectées : {', '.join(manquantes)}"
            )

        valeur = elem['value']
        # U et J sans <value> : le <Name> porte le n° de pièce (78L05CP…) ou le
        # libellé connecteur. On le préserve dans value pour que la puce reste
        # IDENTIFIABLE au rendu (identifier() travaille sur value) et que la
        # boîte ne s'affiche pas vide.
        if type_prefix in ('U', 'J') and not valeur:
            valeur = nom
        # Boîte neutre étiquetée : connecteur J et IC catch-all hors catalogue.
        # (Un régulateur catalogué reste boite_ic=False → _puce_ilot l'identifie
        # via le catalogue AVANT la branche boîte neutre.)
        if type_prefix == 'J' or boite_ic:
            boite_ic = True
        # Résistance R-code : valeur décodée depuis le nom si value vide.
        if type_prefix == 'R' and not valeur:
            v = eretro.decoder_valeur_resistance(nom)
            if v:
                valeur = v

        forme_reelle, brochage_reel = ((None, None) if not boite_ic
                                       else _forme_et_brochage_reels())
        # Si on a un brochage reel pour une boite_ic, reconstruire broches avec les
        # memes noms que pinout pour garantir set(pins) == set(pinout).
        if boite_ic and brochage_reel:
            broches_corrigees = {}
            for pidx, pin_name in enumerate(brochage_reel.keys()):
                net = broche_vers_net.get((cid, pidx), 'NC')
                broches_corrigees[pin_name] = net
            # Conserver les broches AOP standard ajoutees ci-dessus pour les formes nommees
            if type_prefix == 'U' and plan:
                for std in ('IN+', 'IN-', 'OUT', 'V+', 'V-'):
                    broches_corrigees.setdefault(std, 'NC')
            broches = broches_corrigees
        composants.append(Component(ref=ref, type=type_prefix, pins=broches,
                                    value=valeur, par_forme=par_forme,
                                    boite_ic=boite_ic,
                                    primitives=forme_reelle, pinout=brochage_reel))
        if par_forme:
            composants.warnings.append(
                f"Composant '{nom}' (id={cid}) typé par sa forme (dessin) "
                f"→ traité comme {type_prefix} ({ref})"
            )

    if alias_catalogue:
        from circuit_analyzer.catalogue import appliquer_catalogue
        appliquer_catalogue(composants)

    composants.source = eretro.SourceXML(
        arbre=arbre,
        elements={ref: elements[cid]['xml']
                  for cid, ref in cid_vers_ref.items()
                  if elements[cid].get('xml') is not None},
        lignes=lignes_xml,
        lignes_refs={idx: (cid_vers_ref[a], cid_vers_ref[b])
                     for idx, (a, b) in lignes_cids.items()
                     if a in cid_vers_ref and b in cid_vers_ref},
        namespaces=namespaces_source,
        avant_racine=avant_racine_source,
    )

    return composants


# Alias anglais
parse_xml = lire_xml
