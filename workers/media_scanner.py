# workers/media_scanner.py
from PyQt5 import QtCore
from pathlib import Path
import os, traceback

class MediaScannerSignals(QtCore.QObject):
    media_scanned = QtCore.pyqtSignal(str, str, bool)

class MediaScanner(QtCore.QRunnable):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = MediaScannerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        log = []
        poster = ""
        has_media = False
        try:
            log.append(f"[MediaScanner] START scanning: {self.path}")
            for fn in ("poster.png", "poster.jpg", "poster.jpeg"):
                p = Path(self.path) / fn
                if p.exists() and p.is_file():
                    poster = str(p)
                    break

            try:
                with os.scandir(self.path) as it:
                    for e in it:
                        if e.is_file() and any(e.name.lower().endswith(ext) for ext in ('.mp4','.mkv','.avi','.mov','.wmv','.flv','.m4v','.webm')):
                            has_media = True
                            break
            except Exception as scandir_exc:
                log.append(f"[MediaScanner] scandir failed: {scandir_exc}")

        except Exception:
            log.append(traceback.format_exc())
        finally:
            try:
                self.signals.media_scanned.emit(self.path, poster or "", has_media)
                log.append(f"[MediaScanner] emitted for {self.path}")
            except Exception:
                log.append(traceback.format_exc())
            try:
                with open("scanner_debug.log", "a", encoding="utf-8") as fh:
                    for L in log:
                        fh.write(L + "\n")
                    fh.write("\n")
            except Exception:
                pass

