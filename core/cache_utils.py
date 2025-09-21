# core/cache_utils.py
import hashlib
from pathlib import Path
from PyQt5 import QtGui
import config

# in-memory pixmap cache for the session
PX_CACHE = {}  # (path, w, h) -> QPixmap

def cache_path_for(source_path: str, w: int, h: int) -> Path:
    try:
        mtime = int(Path(source_path).stat().st_mtime)
    except Exception:
        mtime = 0
    key = hashlib.sha1(f"{str(Path(source_path).absolute())}|{mtime}".encode('utf-8')).hexdigest()
    bucket = config.CACHE_ROOT / f"{w}x{h}"
    bucket.mkdir(parents=True, exist_ok=True)
    return bucket / f"{key}.jpg"

def cache_get(path, w, h):
    return PX_CACHE.get((str(path), int(w), int(h)))

def cache_set(path, w, h, pix: QtGui.QPixmap):
    PX_CACHE[(str(path), int(w), int(h))] = pix

