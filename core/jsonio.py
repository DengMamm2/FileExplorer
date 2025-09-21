# core/jsonio.py
from pathlib import Path
import json
import copy

def load_json(path: Path, default):
    try:
        if not path.exists():
            path.write_text(json.dumps(default, indent=2), encoding='utf-8')
            return copy.deepcopy(default)
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return copy.deepcopy(default)

def save_json(path: Path, obj):
    try:
        path.write_text(json.dumps(obj, indent=2), encoding='utf-8')
    except Exception:
        pass
