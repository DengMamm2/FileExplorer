# ui/thumbs.py
from PyQt5 import QtCore, QtGui
import os
from pathlib import Path
from core import cache_utils
import traceback
import time

class ThumbSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(str, QtGui.QImage)

class ThumbJob(QtCore.QRunnable):
    def __init__(self, path: str, target_w: int, target_h: int):
        super().__init__()
        self.path = str(path)
        self.target_w = int(target_w)
        self.target_h = int(target_h)
        self.signals = ThumbSignals()
        self.setAutoDelete(True)

    @QtCore.pyqtSlot()
    def run(self):
        start_time = time.time()
        try:
            img = QtGui.QImage(self.path)
            if img.isNull():
                self.signals.finished.emit(self.path, QtGui.QImage())
                return
            self.signals.finished.emit(self.path, img)
        except Exception:
            try:
                self.signals.finished.emit(self.path, QtGui.QImage())
            except Exception:
                pass

class ThumbnailLoader(QtCore.QObject):
    _inst = None
    def __init__(self):
        super().__init__()
        self.pool = QtCore.QThreadPool.globalInstance()
        QtCore.QThreadPool.globalInstance().setMaxThreadCount(16)
        self.pending = {}

    @classmethod
    def instance(cls):
        if cls._inst is None:
            cls._inst = ThumbnailLoader()
        return cls._inst

    def load(self, path: str, target_w: int, target_h: int, cb):
        path = str(path)
        if cache_utils.cache_get(path, target_w, target_h):
            QtCore.QTimer.singleShot(0, lambda: cb(path, None))
            return
        if path in self.pending:
            self.pending[path].append(cb)
            return
        self.pending[path] = [cb]
        job = ThumbJob(path, target_w, target_h)
        job.signals.finished.connect(self._on_finished)
        print(f"[TIMING] Queuing thumbnail job for {path} at {time.time():.3f}")
        self.pool.start(job)

    def _on_finished(self, path: str, qimg: QtGui.QImage):
        cbs = self.pending.pop(str(path), [])
        for cb in cbs:
            try:
                cb(path, qimg)
            except Exception:
                pass