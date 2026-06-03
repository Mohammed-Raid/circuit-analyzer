import copy
import json
from pathlib import Path
from circuit_analyzer.component_library.base import COMPONENT_TYPES


def load_library(json_path: str = 'component_library.json') -> dict:
    library = copy.deepcopy(COMPONENT_TYPES)
    path = Path(json_path)
    if path.exists():
        with open(path, encoding='utf-8') as f:
            overrides = json.load(f)
        library.update(overrides)
    return library


def get_pins(comp_type: str, json_path: str = 'component_library.json') -> list[str]:
    library = load_library(json_path)
    entry = library.get(comp_type)
    return entry.get('pins', ['1', '2']) if entry else ['1', '2']
