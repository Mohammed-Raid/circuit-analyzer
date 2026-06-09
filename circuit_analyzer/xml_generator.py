"""
BoardSCH XML generator — produces files compatible with the design app.

Usage:
    gen = BoardSCHGenerator()
    r1 = gen.add("Résistance", "10k",  x=200,  y=400)
    c1 = gen.add("Capa",       "100n", x=400,  y=400)
    gnd= gen.add("GND",        "",     x=400,  y=600)
    gen.connect(r1, "1", c1, "+")      # R1 pin-1 → C1 plus
    gen.connect(c1, "-", gnd, "GND")   # C1 minus → GND
    xml = gen.to_xml()

The critical connection format understood by xml_parser.py:
    <CFirst>{compId}_{pinIdx}_0_{wireIdx}</CFirst>
    <CLast> {compId}_{pinIdx}_1_{wireIdx}</CLast>
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import textwrap

# ── Component shape library ───────────────────────────────────────────────────
# Each entry: (Name, {pin_name: (local_x, local_y, pin_idx)}, polygon_xml, segment_xml)
# Local coords are relative to CtrIem; scale matches "carte pour tester.xml"

_SHAPE: Dict[str, dict] = {
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
        <DataSegment><Spoint><X>-80</X><Y>0</Y></Spoint><Epoint><X>-50</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>
        <DataSegment><Spoint><X>50</X><Y>0</Y></Spoint><Epoint><X>80</X><Y>0</Y></Epoint><ESelected>false</ESelected><SSelected>false</SSelected><EPtGap><X>0</X><Y>0</Y></EPtGap><SPtGap><X>0</X><Y>0</Y></SPtGap></DataSegment>""",
    },
    "Relais": {
        # Coil (A1/A2) on the left, switch contacts (11 common, 12 NC, 14 NO) on the right
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

# Map type aliases used by xml_parser to component names in _SHAPE
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


@dataclass
class _Comp:
    cid:   int
    name:  str        # BoardSCH Name (e.g. "Résistance", or a rail name like "VMOT_48V")
    value: str
    x:     int        # CtrIem X
    y:     int        # CtrIem Y
    angle: int = 0
    shape: str = ""   # shape template override; "" → use `name` as the shape key


@dataclass
class _Wire:
    wid:   int
    c1:    int   # first component id
    p1:    int   # first pin index
    c2:    int   # second component id
    p2:    int   # second pin index


class BoardSCHGenerator:
    """Build a BoardSCH XML schematic programmatically."""

    def __init__(self):
        self._comps:  List[_Comp]  = []
        self._wires:  List[_Wire]  = []
        self._wire_id = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def add(self, name: str, value: str = "", x: int = 0, y: int = 0, angle: int = 0,
            shape: str = "") -> int:
        """Add a component. Returns its id.

        `shape` overrides which symbol template to draw; when empty the symbol is
        looked up from `name`. This lets a power port keep a distinct rail Name
        (e.g. "VMOT_48V") while still drawing the generic VCC symbol.
        """
        cid = len(self._comps)
        self._comps.append(_Comp(cid, name, value, x, y, angle, shape))
        return cid

    def connect(self, cid1: int, pin1: str, cid2: int, pin2: str) -> None:
        """Wire pin `pin1` of component `cid1` to pin `pin2` of component `cid2`."""
        p1 = self._pin_idx(cid1, pin1)
        p2 = self._pin_idx(cid2, pin2)
        wid = self._wire_id
        self._wire_id += 1
        self._wires.append(_Wire(wid, cid1, p1, cid2, p2))

    def to_xml(self) -> str:
        """Generate the complete BoardSCH XML string."""
        parts = ['<?xml version="1.0" encoding="utf-8"?>',
                 '<BoardSCH xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                 'xmlns:xsd="http://www.w3.org/2001/XMLSchema">',
                 '  <CmpntL>']

        # Build a lookup: (cid, pinIdx) → list[wire references in NodeL format]
        pin_nodes: Dict[Tuple[int,int], List[str]] = {}
        for w in self._wires:
            pin_nodes.setdefault((w.c1, w.p1), []).append(f"{w.c1}_{w.p1}_0_{w.wid}")
            pin_nodes.setdefault((w.c2, w.p2), []).append(f"{w.c2}_{w.p2}_1_{w.wid}")

        for comp in self._comps:
            parts.append(self._comp_xml(comp, pin_nodes))

        parts.append('  </CmpntL>')
        parts.append('  <lineL>')

        for w in self._wires:
            parts.append(self._wire_xml(w))

        parts.append('  </lineL>')
        parts.append('  <CCmpntL />')
        parts.append('  <GrpL />')
        parts.append('  <zoom>1</zoom>')
        parts.append('</BoardSCH>')
        return '\n'.join(parts)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _pin_idx(self, cid: int, pin_name: str) -> int:
        """Return the pin index for a named pin on component cid."""
        shape_name = _ALIAS.get(self._comps[cid].name, self._comps[cid].name)
        shape = _SHAPE.get(shape_name, {})
        pins = shape.get("pins", {})
        if pin_name not in pins:
            raise ValueError(f"Pin '{pin_name}' not found on component {cid} ({self._comps[cid].name}). "
                             f"Available: {list(pins.keys())}")
        return pins[pin_name][2]   # third element is the index

    def _pin_abs(self, cid: int, pin_name: str) -> Tuple[int, int]:
        """Return the ABSOLUTE position of a pin (CtrIem + local offset)."""
        comp = self._comps[cid]
        shape_name = _ALIAS.get(comp.name, comp.name)
        shape = _SHAPE.get(shape_name, {})
        pins = shape.get("pins", {})
        lx, ly, _ = pins.get(pin_name, (0, 0, 0))
        return comp.x + lx, comp.y + ly

    def _comp_xml(self, comp: _Comp, pin_nodes: Dict) -> str:
        shape_key = comp.shape or comp.name
        shape_name = _ALIAS.get(shape_key, shape_key)
        shape = _SHAPE.get(shape_name, {"pins": {}, "polygon": "", "segment": ""})
        pins_info = shape.get("pins", {})

        # Build the datapin XML
        dp_parts = []
        # Sort pins by their index so they appear in order
        sorted_pins = sorted(pins_info.items(), key=lambda kv: kv[1][2])
        for pname, (lx, ly, pidx) in sorted_pins:
            node_refs = pin_nodes.get((comp.cid, pidx), [])
            node_l = ''.join(f'<string>{r}</string>' for r in node_refs)
            dp_parts.append(f"""      <DataPin>
        <Pname>{pname}</Pname>
        <Pnumber>{pname}</Pnumber>
        <NodeL>{node_l}</NodeL>
        <Pin><X>{lx}</X><Y>{ly}</Y></Pin>
        <PinGap><X>0</X><Y>0</Y></PinGap>
        <Size>9</Size>
        <Selected>false</Selected>
        <ShowNbTxt>false</ShowNbTxt>
        <ShowNmTxt>false</ShowNmTxt>
        <VltgP>0</VltgP>
        <typ>0</typ>
      </DataPin>""")

        # Build PinCL from all wire refs for this component
        all_refs = []
        for pidx in range(len(pins_info)):
            all_refs.extend(pin_nodes.get((comp.cid, pidx), []))
        pin_cl = ''.join(f'<string>{r}</string>' for r in all_refs)

        poly = shape.get("polygon", "")
        seg  = shape.get("segment", "")

        return f"""    <DataItem>
      <Name>{comp.name}</Name>
      <Group />
      <reference />
      <value>{comp.value}</value>
      <datapolygon>{poly}</datapolygon>
      <datasegment>{seg}</datasegment>
      <dataarc />
      <datapin>
{''.join(dp_parts)}
      </datapin>
      <PinCL>{pin_cl}</PinCL>
      <CtrIem><X>{comp.x}</X><Y>{comp.y}</Y></CtrIem>
      <pgap><X>0</X><Y>0</Y></pgap>
      <TL><X>50</X><Y>25</Y></TL>
      <BR><X>210</X><Y>121</Y></BR>
      <angle>{comp.angle}</angle>
      <id>{comp.cid}</id>
      <GpId>0</GpId>
      <zmH>1</zmH><zmV>1</zmV>
      <FlipX>0</FlipX><FlipY>0</FlipY>
      <typ>82</typ>
      <Bottom>false</Bottom>
      <selected>false</selected>
      <focus>false</focus>
      <Visible>true</Visible>
      <Top>true</Top>
      <Begrp>false</Begrp>
      <freeze>false</freeze>
    </DataItem>"""

    # ── Conversion from analyzer Component objects ────────────────────────────

    # Component.type → (BoardSCH Name, {library_pin: boardsch_shape_pin})
    _TYPE_TO_SHAPE = {
        "R": ("Résistance", {"1": "1", "2": "2"}),
        "C": ("Capa",       {"1": "+", "2": "-"}),
        "U": ("AOP",        {"IN+": "+", "IN-": "-", "OUT": "s"}),
        "Q": ("Transistor", {"B": "B", "C": "C", "E": "E"}),
        "M": ("MOSFET",     {"G": "G", "D": "D", "S": "S"}),
        "D": ("Diode",      {"A": "A", "K": "K", "1": "A", "2": "K"}),
        "F": ("Fusible",    {"1": "1", "2": "2"}),
        "L": ("Bobine",     {"1": "1", "2": "2"}),
        "K": ("Relais",     {"A1": "A1", "A2": "A2", "11": "11", "12": "12", "14": "14"}),
    }

    # Net name → power symbol BoardSCH Name (None means "regular signal net").
    # Reuses the SAME is_gnd/is_power vocabulary as the pattern matcher so that a
    # net recognized as ground/power during analysis also gets a symbol here.
    @staticmethod
    def _power_symbol(net: str):
        from circuit_analyzer.patterns.base import is_gnd, is_power
        if is_gnd(net):
            return "GND"
        if is_power(net):
            return "VCC"
        return None

    def _wire_xml(self, w: _Wire) -> str:
        # Compute midpoint path for LP (simple straight line)
        c1, c2 = self._comps[w.c1], self._comps[w.c2]
        shape1 = _ALIAS.get(c1.shape or c1.name, c1.shape or c1.name)
        shape2 = _ALIAS.get(c2.shape or c2.name, c2.shape or c2.name)
        p1_info = _SHAPE.get(shape1, {}).get("pins", {})
        p2_info = _SHAPE.get(shape2, {}).get("pins", {})
        # Find pin names by index
        name1 = next((k for k, v in p1_info.items() if v[2] == w.p1), "")
        name2 = next((k for k, v in p2_info.items() if v[2] == w.p2), "")
        x1, y1 = c1.x + p1_info.get(name1, (0,0,0))[0], c1.y + p1_info.get(name1, (0,0,0))[1]
        x2, y2 = c2.x + p2_info.get(name2, (0,0,0))[0], c2.y + p2_info.get(name2, (0,0,0))[1]
        cf = f"{w.c1}_{w.p1}_0_{w.wid}"
        cl = f"{w.c2}_{w.p2}_1_{w.wid}"
        return f"""    <Line>
      <CFirst>{cf}</CFirst>
      <CLast>{cl}</CLast>
      <LP>
        <PointF><X>{x1}</X><Y>{y1}</Y></PointF>
        <PointF><X>{x2}</X><Y>{y2}</Y></PointF>
      </LP>
      <pGap />
      <ID>0</ID><idF>0</idF><idL>0</idL>
      <GpId>0</GpId>
      <Visible>true</Visible>
      <select>false</select>
      <Top>true</Top><Bottom>false</Bottom>
      <BeIngrp>false</BeIngrp>
      <VltgL>0</VltgL>
    </Line>"""


@dataclass
class _Block:
    """A visual group of components sharing a detected circuit pattern."""
    label: str
    comps: list   # list[Component]


def _layout_groups(components, results) -> List["_Block"]:
    """Group drawable components into blocks, one per detected pattern.

    Components not claimed by any pattern go into a final "Divers" block.
    Pure function: no XML, no side effects. Order is deterministic — patterns
    in the order they appear in `results`, then "Divers" last.
    """
    comp_by_ref = {c.ref: c for c in components
                   if BoardSCHGenerator._TYPE_TO_SHAPE.get(c.type) is not None}

    # ref → circuit_type (first pattern that claims it; matcher guarantees
    # exclusivity, so each ref appears in at most one result anyway)
    type_of_ref: dict[str, str] = {}
    for r in results or []:
        for ref in r["components"]:
            type_of_ref.setdefault(ref, r["circuit_type"])

    # Build blocks preserving first-seen pattern order
    blocks: list[_Block] = []
    block_by_label: dict[str, _Block] = {}
    for r in results or []:
        label = r["circuit_type"]
        if label not in block_by_label:
            b = _Block(label, [])
            block_by_label[label] = b
            blocks.append(b)
        for ref in r["components"]:
            if ref in comp_by_ref and type_of_ref.get(ref) == label:
                block_by_label[label].comps.append(comp_by_ref[ref])

    blocks = [b for b in blocks if b.comps]

    # Unclassified drawable components → "Divers"
    divers = [c for ref, c in comp_by_ref.items() if ref not in type_of_ref]
    if divers:
        blocks.append(_Block("Divers", divers))

    return blocks


# ── Module-level: convert analyzer Component objects → BoardSCH XML ────────────

def components_to_xml(components) -> str:
    """Convert a list of analyzer Component objects into a BoardSCH XML string
    openable in the design app. Pins sharing a net are wired together; power
    and ground nets get their own symbols.

    This is the inverse of xml_parser.parse_xml: it reconstructs a schematic
    from the abstract netlist so the design app can render and edit it.
    """
    gen = BoardSCHGenerator()

    # ── Step 1: place every component on a grid ───────────────────────────────
    COL_W, ROW_H = 320, 260
    PER_ROW = 4
    cid_of_ref: dict[str, int] = {}
    # library_pin → shape_pin map per ref
    pinmap_of_ref: dict[str, dict] = {}

    for i, comp in enumerate(components):
        spec = BoardSCHGenerator._TYPE_TO_SHAPE.get(comp.type)
        if spec is None:
            continue   # unknown type → skip (can't draw a shape for it)
        board_name, pinmap = spec
        x = 250 + (i % PER_ROW) * COL_W
        y = 250 + (i // PER_ROW) * ROW_H
        cid = gen.add(board_name, comp.value, x=x, y=y)
        cid_of_ref[comp.ref] = cid
        pinmap_of_ref[comp.ref] = pinmap

    # ── Step 2: group pins by net ─────────────────────────────────────────────
    # net → list of (cid, shape_pin)
    net_pins: dict[str, list] = {}
    for comp in components:
        if comp.ref not in cid_of_ref:
            continue
        cid = cid_of_ref[comp.ref]
        pinmap = pinmap_of_ref[comp.ref]
        for lib_pin, net in comp.pins.items():
            if not net or net == "NC":
                continue
            shape_pin = pinmap.get(lib_pin)
            if shape_pin is None:
                continue   # e.g. AOP V+ / V- have no drawable shape pin
            net_pins.setdefault(net, []).append((cid, shape_pin))

    # ── Step 3: wire each net + add power symbols ─────────────────────────────
    pwr_x = 250
    pwr_y = 250 + ((len(components) // PER_ROW) + 1) * ROW_H

    for net, pins in net_pins.items():
        sym = BoardSCHGenerator._power_symbol(net)
        if sym is not None:
            # Keep the rail's real name (e.g. "VMOT_48V") so distinct rails stay
            # distinct on re-parse; draw it with the generic GND/VCC shape.
            rail_name = net.lstrip('/').upper()
            pwr_pin = "GND" if sym == "GND" else "VCC"
            pcid = gen.add(rail_name, "", x=pwr_x, y=pwr_y, shape=sym)
            pwr_x += 200
            for (cid, shape_pin) in pins:
                _connect_by_idx(gen, pcid, _shape_pin_idx(gen, pcid, pwr_pin),
                                cid, _shape_pin_idx(gen, cid, shape_pin))
        else:
            # Regular net: chain consecutive pins together
            for k in range(len(pins) - 1):
                c1, sp1 = pins[k]
                c2, sp2 = pins[k + 1]
                _connect_by_idx(gen, c1, _shape_pin_idx(gen, c1, sp1),
                                c2, _shape_pin_idx(gen, c2, sp2))

    return gen.to_xml()


def _shape_pin_idx(gen: "BoardSCHGenerator", cid: int, shape_pin: str) -> int:
    """Resolve a shape pin name to its index for component cid."""
    comp = gen._comps[cid]
    shape_key = comp.shape or comp.name
    shape_name = _ALIAS.get(shape_key, shape_key)
    return _SHAPE[shape_name]["pins"][shape_pin][2]


def _connect_by_idx(gen: "BoardSCHGenerator", c1: int, p1: int, c2: int, p2: int) -> None:
    """Low-level wire by pin INDEX (bypasses name lookup)."""
    wid = gen._wire_id
    gen._wire_id += 1
    gen._wires.append(_Wire(wid, c1, p1, c2, p2))
