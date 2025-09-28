from PyQt5 import QtCore
from pathlib import Path
import time

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
        # Only check for poster files, do not scan for media files
        for fn in ("poster.jpg",):  # or add "poster.png", "poster.jpeg" if you want
            p = Path(self.path) / fn
            if p.exists() and p.is_file():
                poster = str(p)
                break

        # We don't check for media files anymore, so just set has_media = False (or True if you want)
        has_media = False

        # Emit the result
        self.signals.media_scanned.emit(self.path, poster or "", has_media)

        # Optional: print timing info
        print(f"[TIMING] Checked for poster in {self.path} in {time.time()-start_time:.3f} sec")