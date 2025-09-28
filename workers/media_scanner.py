from PyQt5 import QtCore
from pathlib import Path
import time
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
        # Use centralized poster lookup from root/posters folder based on folder hash
        poster_path = get_new_poster_path(self.path, str(config.APP_DIR / 'posters'))
        if Path(poster_path).exists():
            poster = poster_path

        # We don't check for media files anymore, so just set has_media = False (or True if you want)
        has_media = False

        # Emit the result
        self.signals.media_scanned.emit(self.path, poster or "", has_media)

        # Optional: print timing info
        print(f"[TIMING] Checked for poster in {self.path} in {time.time()-start_time:.3f} sec")