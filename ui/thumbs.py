# ui/thumbs.py
from PyQt5 import QtCore, QtGui
import os
from pathlib import Path
from core import cache_utils
import traceback
import queue
import threading
from typing import List, Tuple, Callable, Optional

class ThumbSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(str, QtGui.QImage)

class BatchThumbSignals(QtCore.QObject):
    batch_finished = QtCore.pyqtSignal(list)  # List of (path, QImage) tuples

class BatchThumbJob(QtCore.QRunnable):
    """Processes multiple thumbnails in a batch for better performance"""
    def __init__(self, batch_items: List[Tuple[str, int, int]]):
        super().__init__()
        self.batch_items = batch_items  # List of (path, target_w, target_h)
        self.signals = BatchThumbSignals()
        self.setAutoDelete(True)

    @QtCore.pyqtSlot()
    def run(self):
        results = []
        for path, target_w, target_h in self.batch_items:
            try:
                # Check cache first
                cp = cache_utils.cache_path_for(path, target_w, target_h)
                if cp.exists():
                    img = QtGui.QImage(str(cp))
                    if not img.isNull():
                        results.append((path, img))
                        continue
                
                # Load and process image
                img = QtGui.QImage(path)
                if img.isNull():
                    results.append((path, QtGui.QImage()))
                    continue
                
                sw, sh = img.width(), img.height()
                if sw > target_w or sh > target_h:
                    scaled = img.scaled(target_w, target_h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                else:
                    scaled = img
                
                # Save to cache
                try:
                    tmp = cp.with_suffix('.tmp')
                    scaled.save(str(tmp), 'JPEG', 85)
                    tmp.replace(cp)
                except Exception:
                    pass
                
                results.append((path, scaled))
            except Exception:
                results.append((path, QtGui.QImage()))
        
        self.signals.batch_finished.emit(results)

class ThumbJob(QtCore.QRunnable):
    def __init__(self, path: str, target_w: int, target_h: int, priority: int = 0):
        super().__init__()
        self.path = str(path)
        self.target_w = int(target_w)
        self.target_h = int(target_h)
        self.priority = priority  # Higher number = higher priority
        self.signals = ThumbSignals()
        self.setAutoDelete(True)

    def __lt__(self, other):
        """For priority queue comparison - higher priority first"""
        return self.priority > other.priority

    @QtCore.pyqtSlot()
    def run(self):
        try:
            cp = cache_utils.cache_path_for(self.path, self.target_w, self.target_h)
            if cp.exists():
                img = QtGui.QImage(str(cp))
                if not img.isNull():
                    self.signals.finished.emit(self.path, img)
                    return
            img = QtGui.QImage(self.path)
            if img.isNull():
                self.signals.finished.emit(self.path, QtGui.QImage())
                return
            sw, sh = img.width(), img.height()
            if sw > self.target_w or sh > self.target_h:
                scaled = img.scaled(self.target_w, self.target_h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            else:
                scaled = img
            try:
                tmp = cp.with_suffix('.tmp')
                scaled.save(str(tmp), 'JPEG', 85)
                tmp.replace(cp)
            except Exception:
                pass
            self.signals.finished.emit(self.path, scaled)
        except Exception:
            try:
                self.signals.finished.emit(self.path, QtGui.QImage())
            except Exception:
                pass

class ThumbnailLoader(QtCore.QObject):
    _inst = None
    
    def __init__(self):
        super().__init__()
        # Create dedicated thread pool for image processing
        self.pool = QtCore.QThreadPool()
        self.pool.setMaxThreadCount(max(4, QtCore.QThread.idealThreadCount()))
        
        # Priority queue for batch processing
        self.priority_queue = queue.PriorityQueue()
        self.batch_queue = queue.Queue()
        self.pending = {}
        
        # Batch processing settings
        self.batch_size = 8
        self.batch_timeout = 50  # ms
        
        # Start batch processor thread
        self.batch_processor = BatchProcessor(self)
        self.batch_processor.start()
        
        # Timer for batch timeout
        self.batch_timer = QtCore.QTimer()
        self.batch_timer.timeout.connect(self._process_batch)
        self.batch_timer.setSingleShot(True)

    @classmethod
    def instance(cls):
        if cls._inst is None:
            cls._inst = ThumbnailLoader()
        return cls._inst

    def load(self, path: str, target_w: int, target_h: int, cb, priority: int = 0):
        """Load thumbnail with priority. Higher priority = loads first."""
        path = str(path)
        
        # Check memory cache first
        if cache_utils.cache_get(path, target_w, target_h):
            QtCore.QTimer.singleShot(0, lambda: cb(path, None))
            return
        
        # Check if already pending
        if path in self.pending:
            self.pending[path].append(cb)
            return
        
        self.pending[path] = [cb]
        
        # Add to batch queue for processing
        self.batch_queue.put((path, target_w, target_h, priority, cb))
        
        # Start batch timer if not running
        if not self.batch_timer.isActive():
            self.batch_timer.start(self.batch_timeout)

    def load_batch(self, items: List[Tuple[str, int, int, Callable]], priority: int = 0):
        """Load multiple thumbnails in a batch for better performance."""
        batch_items = []
        callbacks = {}
        
        for path, target_w, target_h, cb in items:
            path = str(path)
            
            # Check memory cache first
            if cache_utils.cache_get(path, target_w, target_h):
                QtCore.QTimer.singleShot(0, lambda p=path: cb(p, None))
                continue
                
            # Skip if already pending
            if path in self.pending:
                self.pending[path].append(cb)
                continue
                
            self.pending[path] = [cb]
            batch_items.append((path, target_w, target_h))
            callbacks[path] = cb
        
        if batch_items:
            job = BatchThumbJob(batch_items)
            job.signals.batch_finished.connect(lambda results: self._on_batch_finished(results, callbacks))
            self.pool.start(job)

    def _process_batch(self):
        """Process queued items in batches."""
        batch_items = []
        callbacks = {}
        
        # Collect items for batch processing
        while not self.batch_queue.empty() and len(batch_items) < self.batch_size:
            try:
                path, target_w, target_h, priority, cb = self.batch_queue.get_nowait()
                batch_items.append((path, target_w, target_h))
                callbacks[path] = cb
            except queue.Empty:
                break
        
        if batch_items:
            job = BatchThumbJob(batch_items)
            job.signals.batch_finished.connect(lambda results: self._on_batch_finished(results, callbacks))
            self.pool.start(job)
        
        # Restart timer if more items in queue
        if not self.batch_queue.empty():
            self.batch_timer.start(self.batch_timeout)

    def _on_batch_finished(self, results: List[Tuple[str, QtGui.QImage]], callbacks: dict):
        """Handle batch processing results."""
        for path, qimg in results:
            if path in callbacks:
                try:
                    callbacks[path](path, qimg)
                except Exception:
                    pass
            
            # Also handle any other pending callbacks for this path
            cbs = self.pending.pop(str(path), [])
            for cb in cbs:
                try:
                    cb(path, qimg)
                except Exception:
                    pass

    def _on_finished(self, path: str, qimg: QtGui.QImage):
        """Handle single thumbnail completion."""
        cbs = self.pending.pop(str(path), [])
        for cb in cbs:
            try:
                cb(path, qimg)
            except Exception:
                pass

class BatchProcessor(threading.Thread):
    """Background thread for managing batch processing."""
    def __init__(self, loader):
        super().__init__(daemon=True)
        self.loader = loader
        self.running = True
    
    def run(self):
        while self.running:
            try:
                # This will be used for future enhancements
                threading.Event().wait(0.1)
            except Exception:
                pass
    
    def stop(self):
        self.running = False

