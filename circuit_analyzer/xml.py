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
from dataclasses import dataclass
from html import escape as _esc
from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET

from circuit_analyzer import eretro
from circuit_analyzer.composant import Composant as Component
from circuit_analyzer.patterns.base import (
    is_gnd, is_power, is_ground_net, is_power_net, is_protective_earth_net
)


# =============================================================================
# FORMES VISUELLES DES COMPOSANTS (coordonnées relatives au centre)
# =============================================================================
# Toutes les coordonnées sont en unités BoardSCH, centrées sur (0,0).
# Source : reverse-engineered depuis "exemples/carte pour tester.xml" du logiciel ERetroDesign.

_FORME: Dict[str, dict] = {
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
    # Composant inconnu (issu d'un XML avec nom non reconnu) → rendu comme résistance placeholder
    "X": ("Résistance", {"1": "1", "2": "2"}),
}

# Valeur <typ> observée dans les schematics de référence (ERetroDesign)
_TYP_COMPOSANT = {
    "Résistance": 82, "Capa": 32, "AOP": 79,
    "GND": 71, "AGND": 71, "VCC": 86, "VCC+": 86, "VCC-": 71, "Vss": 115,
}


# =============================================================================
# GÉNÉRATION XML (Composants → fichier BoardSCH)
# =============================================================================

@dataclass
class _Comp:
    """@brief Composant placé sur le schéma (id, nom de forme, valeur, position, forme)."""
    cid: int; name: str; value: str; x: int; y: int; angle: int = 0; shape: str = ""; group_id: int = 0

@dataclass
class _Wire:
    """@brief Fil reliant la broche p1 du composant c1 à la broche p2 du composant c2."""
    wid: int; c1: int; p1: int; c2: int; p2: int; group_id: int = 0


class _Generateur:
    """@brief Constructeur interne de schéma BoardSCH XML."""

    def __init__(self):
        """@brief Initialise un générateur vide (aucun composant ni fil)."""
        self._comps: List[_Comp] = []
        self._wires: List[_Wire] = []
        self._wire_id = 0

    def ajouter(self, nom, valeur="", x=0, y=0, angle=0, forme="", group_id=0) -> int:
        """@brief Ajoute un composant au schéma.

        @param nom Nom de la forme BoardSCH (ex. 'Résistance', 'AOP').
        @param valeur Valeur affichée du composant.
        @param x Abscisse du centre.
        @param y Ordonnée du centre.
        @param angle Angle de rotation (degrés).
        @param forme Forme explicite (sinon déduite du nom).
        @param group_id Identifiant de groupe BoardSCH (0 = aucun groupe).
        @return int Identifiant (cid) du composant ajouté.
        """
        cid = len(self._comps)
        self._comps.append(_Comp(cid, nom, valeur, x, y, angle, forme, group_id))
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
        noeuds_pins: Dict[Tuple[int,int], List[str]] = {}
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
        cle_forme = comp.shape or comp.name
        nom_forme = _ALIAS.get(cle_forme, cle_forme)
        forme = _FORME.get(nom_forme, {"pins": {}, "polygon": "", "segment": ""})
        broches_info = forme.get("pins", {})
        parties_broches = []
        for nom_b, (lx, ly, pidx) in sorted(broches_info.items(), key=lambda kv: kv[1][2]):
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
        poly = forme.get("polygon", ""); seg = forme.get("segment", ""); arc = forme.get("arc", "")
        typ_val = _TYP_COMPOSANT.get(nom_forme, ord(nom_forme[0]) if nom_forme and nom_forme[0].isascii() else 82)
        return f"""    <DataItem>
      <Name>{_esc(comp.name)}</Name><Group /><reference /><value>{_esc(comp.value)}</value>
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
    """@brief Bloc de mise en page : un libellé de circuit et ses composants."""
    label: str
    comps: list


def _refs_du_bloc(r) -> list:
    """@brief Refs d'un circuit + ses satellites sûrs (les « possibles » restent en Divers).

    @param r Match d'un circuit détecté.
    @return list Références du circuit et de ses satellites sûrs.
    """
    refs = list(r["components"])
    refs += [s['ref'] for s in r.get('satellites', []) if s.get('status') == 'sure']
    return refs


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
                          if ref in comp_par_ref and type_du_ref.get(ref) == label])
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


def _positionner_blocs(blocs) -> Dict[str, Tuple[int, int]]:
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


def _positionner_composants_bloc(bloc: _Bloc, x: int, y: int) -> Dict[str, Tuple[int, int]]:
    """@brief Place les composants a l'interieur d'un bloc visuel.

    @param bloc Bloc de circuit detecte.
    @param x Origine horizontale du bloc.
    @param y Origine verticale du bloc.
    @return dict {ref -> (x, y)} Positions absolues.
    """
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


def _positionner_commande_relais(comps, x: int, y: int) -> Dict[str, Tuple[int, int]]:
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


def _positionner_pont_diviseur(comps, x: int, y: int) -> Dict[str, Tuple[int, int]]:
    """@brief Gabarit vertical pour un pont diviseur et ses annexes eventuelles."""
    pos = {}
    resistances = [c for c in comps if c.type == "R"]
    autres = [c for c in comps if c.type != "R"]
    for j, comp in enumerate(resistances[:2]):
        pos[comp.ref] = (x, y + j * _PAS_Y_BLOC)
    for j, comp in enumerate(resistances[2:] + autres):
        pos[comp.ref] = (x + _PAS_X_BLOC, y + j * _PAS_Y_BLOC)
    return pos


def _positionner_aop(comps, x: int, y: int) -> Dict[str, Tuple[int, int]]:
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


def _positionner_rc(comps, x: int, y: int) -> Dict[str, Tuple[int, int]]:
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


def _positionner_grille_compacte(comps, x: int, y: int) -> Dict[str, Tuple[int, int]]:
    """@brief Placement par defaut en petite grille 2 colonnes."""
    return {
        comp.ref: (x + (j % 2) * _PAS_X_BLOC, y + (j // 2) * _PAS_Y_BLOC)
        for j, comp in enumerate(comps)
    }


def _ids_groupes_par_ref(blocs) -> Dict[str, int]:
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
        spec = _TYPE_VERS_FORME.get(comp.type)
        # Puce du catalogue (broches TOUTES numérotées, ex. NE555/74HC00) :
        # la forme statique "AOP" 3 broches nommées perdrait chaque net
        # (plan sans clé numérique -> broches silencieusement non émises).
        # -> forme DIP générique PuceN, plan identité. Un U à broches
        # nommées (IN+/IN-/OUT) garde la forme AOP historique.
        if comp.type == "U" and comp.pins and all(k.isdigit() for k in comp.pins):
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
        if spec is None:
            continue
        nom_forme, plan_broches = spec
        if positions and comp.ref in positions:
            x, y = positions[comp.ref]
        else:
            x = 250 + (i % PER_RANGEE) * _LARG_COMP
            y = 250 + (i // PER_RANGEE) * _HAUT_RANGEE
        cid = gen.ajouter(nom_forme, comp.value, x=x, y=y,
                          group_id=ids_groupes.get(comp.ref, 0))
        ref_vers_cid[comp.ref] = cid
        ref_vers_map[comp.ref] = plan_broches

    nets: dict = {}
    for comp in composants:
        if comp.ref not in ref_vers_cid:
            continue
        cid = ref_vers_cid[comp.ref]
        for broche_lib, net in comp.pins.items():
            if not net or net == "NC":
                continue
            broche_forme = ref_vers_map[comp.ref].get(broche_lib)
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
                    _relier_par_idx(gen, pcid, _idx_broche_forme(gen, pcid, broche_pwr),
                                    cid, _idx_broche_forme(gen, cid, bp))
        else:
            for k in range(len(broches) - 1):
                c1, bp1 = broches[k]; c2, bp2 = broches[k+1]
                _relier_par_idx(gen, c1, _idx_broche_forme(gen, c1, bp1),
                                c2, _idx_broche_forme(gen, c2, bp2))

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


def _positionner_symbole_alim(gen, broches, sym: str, group_id: int) -> Tuple[int, int]:
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
BoardSCHGenerator._TYPE_TO_SHAPE = _TYPE_VERS_FORME


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
    'Diode':       ('D', {'A': 'A', 'K': 'K', '1': 'A', '2': 'K'}),
    'LED':         ('D', {'A': 'A', 'K': 'K', '1': 'A', '2': 'K'}),
    'Zener':       ('D', {'A': 'A', 'K': 'K', '1': 'A', '2': 'K'}),
    'TVS':         ('D', {'A': 'A', 'K': 'K', '1': 'A', '2': 'K'}),
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
_BROCHES_CRITIQUES: Dict[str, list] = {
    'U': ['IN+', 'IN-', 'OUT'],
    'Q': ['B', 'C', 'E'],
    'M': ['G', 'D', 'S'],
    'D': ['A', 'K'],
}


class ListeComposantsXML(list):
    """
    @brief Liste de Composant retournée par lire_xml(), compatible avec list.

    Attribut .warnings : avertissements non-bloquants rencontrés pendant la lecture.
    """
    def __init__(self, composants=None):
        """@brief Initialise la liste de composants XML et ses avertissements.

        @param composants Composants initiaux à placer dans la liste (optionnel).
        @return None
        """
        super().__init__(composants or [])
        self.warnings: list[str] = []

_NET_ALIMENTATION: Dict[str, str] = {
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

    # Étape 1 : extraire tous les composants du fichier
    elements: Dict[int, dict] = {}
    for item in racine.findall('.//CmpntL/DataItem'):
        id_txt = item.findtext('id')
        if id_txt is None:
            continue
        try:
            comp_id = int(id_txt.strip())
        except ValueError:
            continue
        nom   = (item.findtext('Name') or '').strip()
        valeur = (item.findtext('value') or '').strip()
        broches = []
        for pidx, dp in enumerate(item.findall('.//datapin/DataPin')):
            pnum = (dp.findtext('Pnumber') or '').strip()
            pnom = (dp.findtext('Pname') or '').strip()
            # ERetroDesign : l'identité de broche vit dans Pnumber (Pname
            # souvent vide) ; les passifs n'ont ni l'un ni l'autre →
            # numérotation par position pour ne pas écraser les clés.
            broches.append({'pname': pnum or pnom or str(pidx + 1)})
        elements[comp_id] = {'id': comp_id, 'name': nom, 'value': valeur, 'pins': broches}

    # Étape 2 : Union-Find pour regrouper les broches reliées par des fils
    parent: Dict[tuple, tuple] = {}

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

    for fil in racine.findall('.//lineL/Line'):
        cf = (fil.findtext('CFirst') or '').strip()
        cl = (fil.findtext('CLast') or '').strip()
        if cf and cl:
            try:
                unir(_analyser_ref_noeud(cf), _analyser_ref_noeud(cl))
            except ValueError:
                pass

    # Étape 3 : regrouper les broches par nœud électrique
    groupes_nets: Dict[tuple, list] = {}
    for cid, comp in elements.items():
        for pidx in range(len(comp['pins'])):
            cle = trouver((cid, pidx))
            groupes_nets.setdefault(cle, []).append((cid, pidx))

    # Étape 4 : nommer les nœuds
    racine_vers_net: Dict[tuple, str] = {}
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
            norm = cnom.lstrip('/').upper()
            # PE/EARTH/CHASSIS → gardés tels quels, PAS traités comme GND
            if is_protective_earth_net(norm):
                racine_vers_net[cle] = norm; return norm
            if norm not in _NOM_VERS_TYPE and (is_gnd(norm) or is_power(norm)):
                racine_vers_net[cle] = norm; return norm
        compteur += 1
        net = f'NET{compteur}'
        racine_vers_net[cle] = net; return net

    broche_vers_net: Dict[tuple, str] = {}
    for cle, membres in groupes_nets.items():
        net = nom_net(cle)
        for k in membres:
            broche_vers_net[k] = net

    # Étape 5 : construire les objets Composant
    composants = ListeComposantsXML()
    compteurs_type: Dict[str, int] = {}

    for cid in sorted(elements):
        elem = elements[cid]
        nom  = elem['name']

        # Symboles d'alimentation → ne sont pas des composants
        if nom in _NOMS_ALIMENTATION:
            continue

        correspondance = _NOM_VERS_TYPE.get(nom) or eretro.mapper_nom(nom)
        if correspondance is None:
            # Composant inconnu : on le garde sous type 'X' pour ne pas perdre ses connexions
            compteurs_type['X'] = compteurs_type.get('X', 0) + 1
            ref = f'X{compteurs_type["X"]}'
            broches = {}
            for pidx, info_b in enumerate(elem['pins']):
                net = broche_vers_net.get((cid, pidx), 'NC')
                broches[str(pidx + 1)] = net
            composants.append(Component(ref=ref, type='X', pins=broches, value=elem['value']))
            composants.warnings.append(
                f"Composant inconnu '{nom}' (id={cid}) → gardé comme {ref} (type X)"
            )
            continue

        type_prefix, plan = correspondance
        compteurs_type[type_prefix] = compteurs_type.get(type_prefix, 0) + 1
        ref = f'{type_prefix}{compteurs_type[type_prefix]}'
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

        composants.append(Component(ref=ref, type=type_prefix, pins=broches, value=elem['value']))

    if alias_catalogue:
        from circuit_analyzer.catalogue import appliquer_catalogue
        appliquer_catalogue(composants)

    return composants


# Alias anglais
parse_xml = lire_xml
