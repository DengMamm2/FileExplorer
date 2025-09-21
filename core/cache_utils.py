# core/cache_utils.py
import hashlib
from pathlib import Path
from PyQt5 import QtGui
import config
import threading
from typing import Dict, Optional
import os
import time

# Enhanced in-memory cache with LRU eviction
class LRUCache:
    def __init__(self, max_size: int = 1000):
        self.cache: Dict[tuple, tuple] = {}  # (key) -> (value, timestamp)
        self.max_size = max_size
        self.lock = threading.RLock()
    
    def get(self, key: tuple) -> Optional[QtGui.QPixmap]:
        with self.lock:
            if key in self.cache:
                value, _ = self.cache[key]
                # Update timestamp for LRU
                self.cache[key] = (value, time.time())
                return value
            return None
    
    def set(self, key: tuple, value: QtGui.QPixmap):
        with self.lock:
            # Evict oldest entries if cache is full
            if len(self.cache) >= self.max_size:
                self._evict_oldest()
            
            self.cache[key] = (value, time.time())
    
    def _evict_oldest(self):
        if not self.cache:
            return
        
        # Remove 25% of oldest entries
        items = list(self.cache.items())
        items.sort(key=lambda x: x[1][1])  # Sort by timestamp
        remove_count = max(1, len(items) // 4)
        
        for i in range(remove_count):
            key = items[i][0]
            del self.cache[key]

# Enhanced cache system
PX_CACHE = LRUCache(max_size=1000)
DISK_CACHE_STATS = {"hits": 0, "misses": 0}

# Batch cache operations for better performance
_batch_cache_lock = threading.Lock()
_pending_disk_writes = {}  # path -> (image, timestamp)

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
    """Get cached pixmap from memory cache."""
    cache_key = (str(path), int(w), int(h))
    return PX_CACHE.get(cache_key)

def cache_set(path, w, h, pix: QtGui.QPixmap):
    """Set cached pixmap in memory cache."""
    cache_key = (str(path), int(w), int(h))
    PX_CACHE.set(cache_key, pix)

def cache_exists_on_disk(path: str, w: int, h: int) -> bool:
    """Check if thumbnail exists on disk without loading it."""
    try:
        cp = cache_path_for(path, w, h)
        return cp.exists() and cp.stat().st_size > 0
    except Exception:
        return False

def batch_cache_set(items: list):
    """Set multiple cache items efficiently."""
    with _batch_cache_lock:
        for path, w, h, pix in items:
            cache_set(path, w, h, pix)

def batch_save_to_disk(items: list):
    """Save multiple thumbnails to disk in batch."""
    for path, w, h, image in items:
        try:
            cp = cache_path_for(path, w, h)
            tmp = cp.with_suffix('.tmp')
            image.save(str(tmp), 'JPEG', 85)
            tmp.replace(cp)
        except Exception:
            pass

def cache_stats():
    """Get cache statistics for debugging."""
    return {
        "memory_cache_size": len(PX_CACHE.cache),
        "disk_hits": DISK_CACHE_STATS["hits"],
        "disk_misses": DISK_CACHE_STATS["misses"]
    }

def preload_adjacent_folders(folder_path: str, current_files: list):
    """Preload thumbnails for files in adjacent folders."""
    try:
        parent = Path(folder_path).parent
        if not parent.exists():
            return
        
        # Get adjacent folders
        adjacent_folders = []
        for item in parent.iterdir():
            if item.is_dir() and item != Path(folder_path):
                adjacent_folders.append(item)
        
        # Limit to closest folders (by name similarity)
        adjacent_folders.sort(key=lambda x: x.name)
        adjacent_folders = adjacent_folders[:3]  # Limit to 3 adjacent folders
        
        # Start background preloading for poster files
        for folder in adjacent_folders:
            _preload_folder_posters(folder)
            
    except Exception:
        pass

def _preload_folder_posters(folder_path: Path):
    """Background preload poster files from a folder."""
    try:
        for poster_name in ("poster.png", "poster.jpg", "poster.jpeg"):
            poster_path = folder_path / poster_name
            if poster_path.exists():
                # Check if we need to preload this thumbnail
                if not cache_exists_on_disk(str(poster_path), config.VISIBLE_W, config.VISIBLE_H):
                    # Schedule for background loading
                    from ui.thumbs import ThumbnailLoader
                    ThumbnailLoader.instance().load(
                        str(poster_path), 
                        config.VISIBLE_W, 
                        config.VISIBLE_H,
                        lambda *args: None,  # No callback for preloading
                        priority=-1  # Low priority for preloading
                    )
                break
    except Exception:
        pass

