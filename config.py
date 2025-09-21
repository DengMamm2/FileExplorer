# config.py
from pathlib import Path

APP_DIR = Path(__file__).parent

# Files
SETTINGS_FILE = APP_DIR / "settings.json"
QUICK_FILE = APP_DIR / "quickaccess.json"
DEFAULT_SETTINGS = {"potplayer_path": "", "max_cols": 8}

# VISIBILITY / layout (portrait posters)
VISIBLE_W = 360   # visible tile width (px)
VISIBLE_H = 540   # visible tile height (px)

# Grid spacing
GRID_PADDING = 12
GRID_GAP = 18

# Local cache folder for thumbnail files (optional)
CACHE_ROOT = APP_DIR / "cache"

# Extensions
VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.webm'}
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'}
