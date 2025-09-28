# core/cache_utils.py
import hashlib
from pathlib import Path
from PyQt5 import QtGui
import config
import time

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
    key = (str(path), int(w), int(h))
    if key in PX_CACHE:
        print(f"[TIMING] cache_get: HIT for {key} at {time.time():.3f}")
    else:
        print(f"[TIMING] cache_get: MISS for {key} at {time.time():.3f}")
    return PX_CACHE.get(key)

def cache_set(path, w, h, pix: QtGui.QPixmap):
    key = (str(path), int(w), int(h))
    PX_CACHE[key] = pix
    print(f"[TIMING] cache_set: SET for {key} at {time.time():.3f}")

