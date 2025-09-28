# workers/media_scanner.py
from PyQt5 import QtCore
from pathlib import Path
import os, traceback
from typing import List, Tuple
import concurrent.futures
import threading

class MediaScannerSignals(QtCore.QObject):
    media_scanned = QtCore.pyqtSignal(str, str, bool)
    batch_scanned = QtCore.pyqtSignal(list)  # List of (path, poster, has_media) tuples

class BatchMediaScanner(QtCore.QRunnable):
    """Scans multiple folders in batch for better performance."""
    def __init__(self, folder_paths: List[str], priority: bool = False):
        super().__init__()
        self.folder_paths = folder_paths
        self.priority = priority
        self.signals = MediaScannerSignals()
        self.setAutoDelete(True)
    
    @QtCore.pyqtSlot()
    def run(self):
        results = []
        
        # Use thread pool for parallel scanning
        max_workers = min(4, len(self.folder_paths))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(self._scan_single_folder, path): path 
                for path in self.folder_paths
            }
            
            for future in concurrent.futures.as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    poster, has_media = future.result()
                    results.append((path, poster, has_media))
                except Exception:
                    results.append((path, "", False))
        
        self.signals.batch_scanned.emit(results)
    
    def _scan_single_folder(self, folder_path: str) -> Tuple[str, bool]:
        """Scan a single folder for poster and media files."""
        poster = ""
        has_media = False
        
        try:
            # Quick poster detection
            for fn in ("poster.png", "poster.jpg", "poster.jpeg"):
                p = Path(folder_path) / fn
                if p.exists() and p.is_file():
                    poster = str(p)
                    break
            
            # Fast media detection - stop at first match
            try:
                with os.scandir(folder_path) as it:
                    for e in it:
                        if e.is_file() and any(e.name.lower().endswith(ext) for ext in 
                            ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.webm')):
                            has_media = True
                            break
            except Exception:
                pass
                
        except Exception:
            pass
        
        return poster, has_media

class MediaScanner(QtCore.QRunnable):
    def __init__(self, path: str, priority: bool = False):
        super().__init__()
        self.path = path
        self.priority = priority
        self.signals = MediaScannerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        log = []
        poster = ""
        has_media = False
        try:
            log.append(f"[MediaScanner] START scanning: {self.path}")
            
            # Optimized poster detection - check all at once
            folder_path = Path(self.path)
            poster_files = ['poster.png', 'poster.jpg', 'poster.jpeg']
            
            for fn in poster_files:
                p = folder_path / fn
                if p.exists() and p.is_file():
                    poster = str(p)
                    break

            # Optimized media detection - early exit
            try:
                video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.webm'}
                with os.scandir(self.path) as it:
                    for e in it:
                        if e.is_file():
                            ext = Path(e.name).suffix.lower()
                            if ext in video_extensions:
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
            
            # Optional debug logging (can be disabled for performance)
            if os.environ.get('DEBUG_SCANNER'):
                try:
                    with open("scanner_debug.log", "a", encoding="utf-8") as fh:
                        for L in log:
                            fh.write(L + "\n")
                        fh.write("\n")
                except Exception:
                    pass

class MediaScannerManager:
    """Manages batch scanning of multiple folders."""
    _instance = None
    
    def __init__(self):
        self.batch_queue = []
        self.batch_size = 10
        self.batch_timeout = 100  # ms
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._process_batch)
        self.timer.setSingleShot(True)
        
    @classmethod 
    def instance(cls):
        if cls._instance is None:
            cls._instance = MediaScannerManager()
        return cls._instance
    
    def scan_folder(self, path: str, callback, priority: bool = False):
        """Queue a folder for scanning."""
        self.batch_queue.append((path, callback, priority))
        
        # Start timer if not running
        if not self.timer.isActive():
            self.timer.start(self.batch_timeout)
    
    def scan_folders_batch(self, paths: List[str], callback, priority: bool = False):
        """Scan multiple folders in batch."""
        if not paths:
            return
            
        scanner = BatchMediaScanner(paths, priority)
        scanner.signals.batch_scanned.connect(callback)
        
        # Use global thread pool
        QtCore.QThreadPool.globalInstance().start(scanner)
    
    def _process_batch(self):
        """Process queued folders in batches."""
        if not self.batch_queue:
            return
            
        # Separate by priority
        high_priority = [(p, c) for p, c, pr in self.batch_queue if pr]
        normal_priority = [(p, c) for p, c, pr in self.batch_queue if not pr]
        
        # Process high priority first
        if high_priority:
            paths, callbacks = zip(*high_priority)
            self.scan_folders_batch(list(paths), 
                lambda results: self._handle_batch_results(results, callbacks), 
                priority=True)
        
        # Process normal priority in batches
        if normal_priority:
            batch_items = normal_priority[:self.batch_size]
            if batch_items:
                paths, callbacks = zip(*batch_items)
                self.scan_folders_batch(list(paths),
                    lambda results: self._handle_batch_results(results, callbacks))
                
                # Remove processed items
                self.batch_queue = normal_priority[self.batch_size:]
                
                # Continue processing if more items remain
                if self.batch_queue:
                    self.timer.start(self.batch_timeout)
        else:
            self.batch_queue.clear()
    
    def _handle_batch_results(self, results: List[Tuple[str, str, bool]], callbacks):
        """Handle batch scanning results."""
        for i, (path, poster, has_media) in enumerate(results):
            if i < len(callbacks):
                try:
                    callbacks[i](path, poster, has_media)
                except Exception:
                    pass

