# workers/scanner.py
from PyQt5 import QtCore
import os

class ScannerSignals(QtCore.QObject):
    folder_found = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

class FolderScanner(QtCore.QRunnable):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = ScannerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            with os.scandir(self.path) as it:
                for e in it:
                    if e.is_dir():
                        self.signals.folder_found.emit(e.path)
        except Exception:
            pass
        self.signals.finished.emit()
