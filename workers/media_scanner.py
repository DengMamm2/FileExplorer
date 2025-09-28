# In workers/media_scanner.py
from PyQt5 import QtCore
from pathlib import Path
import time
import os
from poster_utils import get_new_poster_path
import config

class MediaScannerSignals(QtCore.QObject):
    media_scanned = QtCore.pyqtSignal(str, str, bool)

class MediaScanner(QtCore.QRunnable):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = MediaScannerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        start_time = time.time()
        poster = ""
        
        # Get the poster path using the poster_utils function
        try:
            # Use the APP_DIR / 'posters' as the posters root directory
            posters_root = str(config.APP_DIR / 'posters')
            poster_path = get_new_poster_path(self.path, posters_root)
            
            # Debug print - this will show in your console
            print(f"[DEBUG] Looking for poster at: {poster_path}")
            
            # Check if the poster exists
            if os.path.exists(poster_path):
                poster = str(poster_path)
                print(f"[DEBUG] Found poster: {poster}")
            else:
                print(f"[DEBUG] No poster found at: {poster_path}")
        except Exception as e:
            print(f"[DEBUG] Error getting poster path: {e}")
        
        # We don't check for media files anymore, so just set has_media = False
        has_media = False

        # Emit the result
        self.signals.media_scanned.emit(self.path, poster or "", has_media)

        # Timing info
        print(f"[TIMING] Checked for poster for {self.path} in {time.time()-start_time:.3f} sec")