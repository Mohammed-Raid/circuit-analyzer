"""
xml.py — Lecture et génération de schémas BoardSCH au format XML.

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

from circuit_analyzer.composant import Composant as Component
from circuit_analyzer.patterns.base import (
    is_gnd, is_power, is_ground_net, is_power_net, is_protective_earth_net
)


# =============================================================================
# FORMES VISUELLES DES COMPOSANTS (coordonnées relatives au centre)
# =============================================================================
# Toutes les coordonnées sont en unités BoardSCH, centrées sur (0,0).
# Source : reverse-engineered depuis "carte pour tester.xml" du logiciel ERetroDesign.

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
    "Bobine": {
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
}

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
    "Bobine": "Bobine", "Inductance": "Bobine",
}

# type_composant → (nom_forme_BoardSCH, {broche_lib → broche_forme})
_TYPE_VERS_FORME = {
    "R": ("Résistance", {"1": "1", "2": "2"}),
    "C": ("Capa",       {"1": "+", "2": "-"}),
    "U": ("AOP",        {"IN+": "+", "IN-": "-", "OUT": "s"}),
    "Q": ("Transistor", {"B": "B", "C": "C", "E": "E"}),
    "M": ("MOSFET",     {"G": "G", "D": "D", "S": "S"}),
    "D": ("Diode",      {"A": "A", "K": "K", "1": "A", "2": "K"}),
    "F": ("Fusible",    {"1": "1", "2": "2"}),
    "L": ("Bobine",     {"1": "1", "2": "2"}),
    "K": ("Relais",     {"A1": "A1", "A2": "A2", "11": "11", "12": "12", "14": "14"}),
    # Composant inconnu (issu d'un XML avec nom non reconnu) → rendu comme résistance placeholder
    "X": ("Résistance", {"1": "1", "2": "2"}),
}

# Valeur <typ> observée dans les schematics de référence (ERetroDesign)
_TYP_COMPOSANT = {
    "Résistance": 82, "Capa": 32, "AOP": 79,
    "GND": 71, "AGND": 71, "VCC": 86, "Vss": 115,
}


# =============================================================================
# GÉNÉRATION XML (Composants → fichier BoardSCH)
# =============================================================================

@dataclass
class _Comp:
    cid: int; name: str; value: str; x: int; y: int; angle: int = 0; shape: str = ""

@dataclass
class _Wire:
    wid: int; c1: int; p1: int; c2: int; p2: int


class _Generateur:
    """Constructeur interne de schéma BoardSCH XML."""

    def __init__(self):
        self._comps: List[_Comp] = []
        self._wires: List[_Wire] = []
        self._wire_id = 0

    def ajouter(self, nom, valeur="", x=0, y=0, angle=0, forme="") -> int:
        cid = len(self._comps)
        self._comps.append(_Comp(cid, nom, valeur, x, y, angle, forme))
        return cid

    def relier(self, cid1, broche1, cid2, broche2):
        p1 = self._idx_broche(cid1, broche1)
        p2 = self._idx_broche(cid2, broche2)
        wid = self._wire_id; self._wire_id += 1
        self._wires.append(_Wire(wid, cid1, p1, cid2, p2))

    def vers_xml(self) -> str:
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
        parties += ['  </lineL>', '  <CCmpntL />', '  <GrpL />', '  <zoom>1</zoom>', '</BoardSCH>']
        return '\n'.join(parties)

    def _idx_broche(self, cid, nom_broche) -> int:
        forme_nom = _ALIAS.get(self._comps[cid].name, self._comps[cid].name)
        forme = _FORME.get(forme_nom, {})
        broches = forme.get("pins", {})
        if nom_broche not in broches:
            raise ValueError(f"Broche '{nom_broche}' introuvable sur composant {cid} ({self._comps[cid].name}). "
                             f"Disponibles : {list(broches.keys())}")
        return broches[nom_broche][2]

    def _xml_composant(self, comp, noeuds_pins) -> str:
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
      <angle>{comp.angle}</angle><id>{comp.cid}</id><GpId>0</GpId>
      <zmH>1</zmH><zmV>1</zmV><FlipX>0</FlipX><FlipY>0</FlipY>
      <typ>{typ_val}</typ>
      <Bottom>false</Bottom><selected>false</selected><focus>false</focus>
      <Visible>true</Visible><Top>true</Top><Begrp>false</Begrp><freeze>false</freeze>
    </DataItem>"""

    def _xml_fil(self, w) -> str:
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
      <pGap /><ID>0</ID><idF>0</idF><idL>0</idL><GpId>0</GpId>
      <Visible>true</Visible><select>false</select><Top>true</Top><Bottom>false</Bottom>
      <BeIngrp>false</BeIngrp><VltgL>0</VltgL>
    </Line>"""


# Constantes de mise en page
_BLOCS_PAR_RANGEE = 3
_GAP_BLOCS   = 160
_LARG_COMP   = 320
_HAUT_RANGEE = 260


@dataclass
class _Bloc:
    label: str
    comps: list


def _refs_du_bloc(r) -> list:
    """Refs d'un circuit + ses satellites sûrs (les « possibles » restent en Divers)."""
    refs = list(r["components"])
    refs += [s['ref'] for s in r.get('satellites', []) if s.get('status') == 'sure']
    return refs


def _ordre_des_circuits(resultats) -> list:
    """
    Ordre d'émission des blocs : les circuits du même îlot fonctionnel sont
    consécutifs (si .ilots est disponible), sinon ordre de détection.
    """
    indices = list(range(len(resultats or [])))
    ilots = getattr(resultats, 'ilots', [])
    if not ilots:
        return indices
    par_ilot = [i for ilot in ilots for i in ilot['circuits']]
    restants = [i for i in indices if i not in par_ilot]
    return par_ilot + restants


def _grouper_par_circuit(composants, resultats):
    """Regroupe les composants par circuit détecté. Composants non classifiés → bloc 'Divers'."""
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
        blocs.append(_Bloc("Divers", divers))
    return blocs


def _positionner_blocs(blocs) -> Dict[str, Tuple[int, int]]:
    """Calcule la position (x, y) de chaque composant selon son bloc."""
    pos = {}; x = 250; y = 250; col = 0
    for blk in blocs:
        for j, comp in enumerate(blk.comps):
            pos[comp.ref] = (x + j * _LARG_COMP, y)
        x += max(len(blk.comps), 1) * _LARG_COMP + _GAP_BLOCS
        col += 1
        if col >= _BLOCS_PAR_RANGEE:
            col = 0; x = 250; y += _HAUT_RANGEE
    return pos


def generer_xml(composants, resultats=None, results=None) -> str:
    """
    Convertit une liste de composants en schéma BoardSCH XML.

    Si `resultats` (sortie de detecteur.analyser()) est fourni, les composants
    sont groupés par circuit détecté. Sinon, grille simple.
    """
    gen = _Generateur()
    PER_RANGEE = 4

    resultats = resultats or results   # accepter les deux noms de paramètre
    positions = _positionner_blocs(_grouper_par_circuit(composants, resultats)) if resultats else None

    ref_vers_cid = {}
    ref_vers_map = {}
    for i, comp in enumerate(composants):
        spec = _TYPE_VERS_FORME.get(comp.type)
        if spec is None:
            continue
        nom_forme, plan_broches = spec
        if positions and comp.ref in positions:
            x, y = positions[comp.ref]
        else:
            x = 250 + (i % PER_RANGEE) * _LARG_COMP
            y = 250 + (i // PER_RANGEE) * _HAUT_RANGEE
        cid = gen.ajouter(nom_forme, comp.value, x=x, y=y)
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

    PWR_PAR_RANGEE = _BLOCS_PAR_RANGEE * 3
    pwr_x = 250; pwr_col = 0
    pwr_y = (max(y for _, y in positions.values()) + _HAUT_RANGEE) if positions else \
            (250 + ((len(composants) // PER_RANGEE) + 1) * _HAUT_RANGEE)

    for net, broches in nets.items():
        sym = "GND" if is_gnd(net) else ("VCC" if is_power(net) else None)
        if sym:
            rail = net.lstrip('/').upper()
            broche_pwr = "GND" if sym == "GND" else "VCC"
            pcid = gen.ajouter(rail, "", x=pwr_x, y=pwr_y, forme=sym)
            pwr_col += 1
            if pwr_col >= PWR_PAR_RANGEE:
                pwr_col = 0; pwr_x = 250; pwr_y += _HAUT_RANGEE
            else:
                pwr_x += 200
            for (cid, bp) in broches:
                _relier_par_idx(gen, pcid, _idx_broche_forme(gen, pcid, broche_pwr),
                                cid, _idx_broche_forme(gen, cid, bp))
        else:
            for k in range(len(broches) - 1):
                c1, bp1 = broches[k]; c2, bp2 = broches[k+1]
                _relier_par_idx(gen, c1, _idx_broche_forme(gen, c1, bp1),
                                c2, _idx_broche_forme(gen, c2, bp2))

    return gen.vers_xml()


def _idx_broche_forme(gen, cid, broche) -> int:
    comp = gen._comps[cid]
    cle = comp.shape or comp.name
    nom = _ALIAS.get(cle, cle)
    return _FORME[nom]["pins"][broche][2]


def _relier_par_idx(gen, c1, p1, c2, p2):
    wid = gen._wire_id; gen._wire_id += 1
    gen._wires.append(_Wire(wid, c1, p1, c2, p2))


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
    # ── AOP ──────────────────────────────────────────────────────────────────
    'AOP':         ('U', {'+': 'IN+', '-': 'IN-', 's': 'OUT'}),
    'OpAmp':       ('U', {'+': 'IN+', '-': 'IN-', 's': 'OUT'}),
    'Op-Amp':      ('U', {'+': 'IN+', '-': 'IN-', 's': 'OUT'}),
    # ── Transistors BJT ──────────────────────────────────────────────────────
    'Transistor':  ('Q', {'B': 'B', 'C': 'C', 'E': 'E'}),
    'BJT':         ('Q', {'B': 'B', 'C': 'C', 'E': 'E'}),
    # ── MOSFET ───────────────────────────────────────────────────────────────
    'MOSFET':      ('M', {'G': 'G', 'D': 'D', 'S': 'S'}),
    # ── Relais ───────────────────────────────────────────────────────────────
    'Relais':      ('K', {'A1': 'A1', 'A2': 'A2', '11': '11', '12': '12', '14': '14'}),
    'Relay':       ('K', {'A1': 'A1', 'A2': 'A2', '11': '11', '12': '12', '14': '14'}),
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
    Liste de Composant retournée par lire_xml().
    Compatible avec list classique.
    Attribut .warnings : avertissements non-bloquants rencontrés pendant la lecture.
    """
    def __init__(self, composants=None):
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
    """Parse 'compId_pinIdx_...' → (compId, pinIdx)."""
    parties = nid.split('_')
    if len(parties) < 2:
        raise ValueError(f"Référence de nœud invalide : {nid!r}")
    try:
        return int(parties[0]), int(parties[1])
    except ValueError:
        raise ValueError(f"Référence de nœud invalide : {nid!r}")


def lire_xml(chemin: str) -> list:
    """
    Lit un fichier BoardSCH XML et retourne une liste de Composant.

    Utilise l'algorithme Union-Find pour reconstruire les nœuds électriques
    à partir des fils (lignes) du schéma.
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
        broches = [{'pname': (dp.findtext('Pname') or '').strip()}
                   for dp in item.findall('.//datapin/DataPin')]
        elements[comp_id] = {'id': comp_id, 'name': nom, 'value': valeur, 'pins': broches}

    # Étape 2 : Union-Find pour regrouper les broches reliées par des fils
    parent: Dict[tuple, tuple] = {}

    def trouver(x):
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
        nonlocal compteur
        if cle in racine_vers_net:
            return racine_vers_net[cle]
        for (cid, _) in groupes_nets.get(cle, []):
            cnom = elements[cid]['name']
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

        if nom not in _NOM_VERS_TYPE:
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

        type_prefix, plan = _NOM_VERS_TYPE[nom]
        compteurs_type[type_prefix] = compteurs_type.get(type_prefix, 0) + 1
        ref = f'{type_prefix}{compteurs_type[type_prefix]}'
        broches = {}
        for pidx, info_b in enumerate(elem['pins']):
            pnom = info_b['pname']
            broche_lib = plan.get(pnom, pnom)
            net = broche_vers_net.get((cid, pidx), 'NC')
            broches[broche_lib] = net
        if type_prefix == 'U':
            for std in ('IN+', 'IN-', 'OUT', 'V+', 'V-'):
                broches.setdefault(std, 'NC')

        # Vérifier les broches critiques manquantes
        manquantes = [
            p for p in _BROCHES_CRITIQUES.get(type_prefix, [])
            if broches.get(p, 'NC') == 'NC'
        ]
        if manquantes:
            composants.warnings.append(
                f"{ref} ({nom}): broches critiques non connectées : {', '.join(manquantes)}"
            )

        composants.append(Component(ref=ref, type=type_prefix, pins=broches, value=elem['value']))

    return composants


# Alias anglais
parse_xml = lire_xml
