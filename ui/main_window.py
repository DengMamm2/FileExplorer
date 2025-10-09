# ui/main_window.py
import os
import ui_settings
from pathlib import Path
from functools import partial
from PyQt5 import QtCore, QtGui, QtWidgets
from poster_utils import move_poster

import config
from core.jsonio import load_json, save_json  # small helper below
from core.qt_utils import svg_to_pixmap, MAG_SVG
from core.file_utils import launch_with_player, find_first_video

# NOTE: heavy widget modules (tile, widgets, thumbs, scanner) are imported
# inside MainWindow.__init__ to avoid early Qt initialization issues.

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Poster Wall Explorer')
        screen = QtWidgets.QApplication.instance().primaryScreen()
        size = screen.size() if screen else QtCore.QSize(1920, 1080)
        self.resize(size.width(), size.height())


        # ---- Delay heavy Qt imports until after attributes are set in app.py ----
        from ui.tile import Tile
        from workers.scanner import FolderScanner
        from ui.widgets import Spinner
        from ui.thumbs import ThumbnailLoader

        # store references on self for later use
        self._Tile = Tile
        self._FolderScanner = FolderScanner
        self._Spinner = Spinner
        self._ThumbnailLoader = ThumbnailLoader

        # load settings
        self.settings = load_json(config.SETTINGS_FILE, config.DEFAULT_SETTINGS)
        self.quick = load_json(config.QUICK_FILE, [])
        self.threadpool = QtCore.QThreadPool.globalInstance()
        self.threadpool.setMaxThreadCount(16)
        self.history = []
        self.history_index = -1
        self.current_path = ''

        # Baseline/native visible size
        self.base_w = config.VISIBLE_W   # 360
        self.base_h = config.VISIBLE_H   # 540

        screen = QtWidgets.QApplication.instance().primaryScreen()
        self.dpr = float(screen.devicePixelRatio()) if screen else 1.0
        if self.dpr < 1.0:
            self.dpr = 1.0
        self.native_w = max(1, int(self.base_w * self.dpr))
        self.native_h = max(1, int(self.base_h * self.dpr))
        # Safe font scale calculation - prevent crashes from extreme values
        raw_font_scale = screen.logicalDotsPerInch() / 96.0 if screen else 1.0
        self.font_scale = max(0.1, raw_font_scale)  # Only prevent extremely small values

        screen_w = screen.size().width() if screen else 1920
        raw_tile_w = max(1, screen_w // 8)
        self.tile_w = min(self.base_w, raw_tile_w)
        self.tile_h = max(1, int(self.tile_w * (self.base_h / self.base_w)))


        # apply palette
        self._apply_dark_palette()

        # build UI
        root = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(root)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)

        # top bar (REPLACE YOUR CURRENT TOP-BAR BLOCK WITH THIS)
        top = QtWidgets.QWidget()
        top.setFixedHeight(80)
        top.setStyleSheet('background:#0f0f10;')

        # grid layout with three columns: left / center / right
        top_layout = QtWidgets.QGridLayout(top)
        top_layout.setContentsMargins(12, 8, 12, 8)
        top_layout.setSpacing(12)

        # left nav + breadcrumbs (same as before)
        left_w = QtWidgets.QWidget()
        left_l = QtWidgets.QHBoxLayout(left_w)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(8)

        self.btn_back = QtWidgets.QToolButton()
        self.btn_back.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowBack))
        self.btn_back.clicked.connect(self.go_back)
        self.btn_forward = QtWidgets.QToolButton()
        self.btn_forward.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ArrowForward))
        self.btn_forward.clicked.connect(self.go_forward)
        self.btn_home = QtWidgets.QToolButton()
        self.btn_home.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirHomeIcon))
        self.btn_home.clicked.connect(self.show_home)

        left_l.addWidget(self.btn_back)
        left_l.addWidget(self.btn_forward)
        left_l.addWidget(self.btn_home)

        self.breadcrumb = QtWidgets.QWidget()
        self.breadcrumb_layout = QtWidgets.QHBoxLayout(self.breadcrumb)
        self.breadcrumb_layout.setContentsMargins(60, 0, 6, 0)
        self.breadcrumb_layout.setSpacing(6)
        self.breadcrumb.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)

        left_l.addWidget(self.breadcrumb)
        left_l.addStretch()

        # right quick button (same as before)
        self.quick_btn = QtWidgets.QToolButton()
        self.quick_btn.setText('Quick ▾')
        self.quick_btn.setMinimumSize(140, 40)
        self.collect_posters_btn = QtWidgets.QPushButton('Collect posters')
        self.collect_posters_btn.setMinimumSize(140, 40)
        self.collect_posters_btn.setStyleSheet('color:#7FC97F; font-weight:700;')
        self.collect_posters_btn.clicked.connect(self.collect_posters_from_quick)
        self.item_count_label = QtWidgets.QLabel("Items: 0")
        self.item_count_label.setStyleSheet('color:#FFC857; font-weight:700; font-size:14px; margin-right:16px;')
        qfont = QtGui.QFont()
        qfont.setPointSize(14)
        self.quick_btn.setFont(qfont)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)  # Will update this later
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)  # Hide it until needed
        self.quick_menu = QtWidgets.QMenu()
        self.quick_btn.setMenu(self.quick_menu)
        self.quick_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self._rebuild_quick_menu()

        # add left + right widgets into row 0 of grid
        top_layout.addWidget(left_w, 0, 0, alignment=QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        top_layout.addWidget(self.item_count_label, 0, 1, alignment=QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        top_layout.addWidget(self.collect_posters_btn, 0, 2, alignment=QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        top_layout.addWidget(self.quick_btn, 0, 3, alignment=QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        top_layout.addWidget(self.progress_bar, 0, 4, alignment=QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        top_layout.setColumnMinimumWidth(2, 40)
        self.quick_btn.setStyleSheet("margin-right: 60px;")


        # center search — responsive and centered regardless of breadcrumb width
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText('Search folders...')
        self.search.setMinimumHeight(44)

        # MAKE IT RESPONSIVE:
        # - allow it to expand
        # - set a reasonable minimum and maximum
        self.search.setMinimumWidth(600)                 # starting width you wanted
        self.search.setMaximumWidth(1400)                # won't grow beyond this
        self.search.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        try:
            mag = svg_to_pixmap(MAG_SVG, 18, 18)
            self.search.addAction(QtGui.QIcon(mag), QtWidgets.QLineEdit.LeadingPosition)
        except Exception:
            pass
        self.search.setStyleSheet('QLineEdit { background: white; color: black; border-radius: 12px; padding-left:10px; font-size:14px; }')
        # Add search delay timer
        self.search_timer = QtCore.QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.on_search_delayed)
        self.search.textChanged.connect(self.on_search_input)

        # put the search in the center column
        top_layout.addWidget(self.search, 0, 1, alignment=QtCore.Qt.AlignCenter)

        # IMPORTANT: control how the three columns share space.
        # Give the center column more stretch so the search gets the available width.
        top_layout.setColumnStretch(0, 1)   # left
        top_layout.setColumnStretch(1, 6)   # center (search)
        top_layout.setColumnStretch(2, 1)   # right

        rv.addWidget(top)


        # grid area
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.left = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(self.left)
        lv.setContentsMargins(8, 8, 8, 8)
        lv.setSpacing(8)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        # Make scrolling faster
        self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.scroll.verticalScrollBar().setSingleStep(ui_settings.SCROLL_SPEED)

        # wrapper to center the grid_container
        self.scroll_wrapper = QtWidgets.QWidget()
        wrapper_layout = QtWidgets.QHBoxLayout(self.scroll_wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addStretch()

        self.grid_container = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(config.GRID_PADDING, config.GRID_PADDING, config.GRID_PADDING, config.GRID_PADDING)
        self.grid_layout.setSpacing(config.GRID_GAP)
        # grid aligned top; horizontal centering comes from wrapper
        self.grid_layout.setAlignment(QtCore.Qt.AlignTop)

        wrapper_layout.addWidget(self.grid_container)
        wrapper_layout.addStretch()

        self.scroll.setWidget(self.scroll_wrapper)
        lv.addWidget(self.scroll)

        self.spinner = self._Spinner(48)
        self.spinner.hide()
        lv.addWidget(self.spinner, alignment=QtCore.Qt.AlignCenter)
        self.splitter.addWidget(self.left)

        # details pane
        self.details = QtWidgets.QTextEdit()
        self.details.setReadOnly(True)
        self.details.setFixedWidth(380)
        self.details.setStyleSheet('background:#121212;color:#ddd;padding:8px;')
        self.details.hide()
        self.splitter.addWidget(self.details)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        rv.addWidget(self.splitter)
        self.setCentralWidget(root)

        # ensure thumbnail loader exists (safe now)
        self._ThumbnailLoader.instance()

        # initial home (uses precomputed tile size & cols — won't change on resize)
        self.populate_home()

    def _apply_dark_palette(self):
        app = QtWidgets.QApplication.instance()
        if not app:
            return
        pal = QtGui.QPalette()
        pal.setColor(QtGui.QPalette.Window, QtGui.QColor('#0f0f10')); pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor('#ffffff'))
        pal.setColor(QtGui.QPalette.Base, QtGui.QColor('#0f0f10')); pal.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor('#121212'))
        pal.setColor(QtGui.QPalette.Text, QtGui.QColor('#ffffff')); pal.setColor(QtGui.QPalette.Button, QtGui.QColor('#151515'))
        pal.setColor(QtGui.QPalette.ButtonText, QtGui.QColor('#ffffff')); pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor('#2b6bd4'))
        pal.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor('#ffffff')); app.setPalette(pal); app.setStyle('Fusion')

    def _rebuild_quick_menu(self):
        self.quick_menu.clear()
        self.quick_menu.setMinimumWidth(420)
        provider = QtWidgets.QFileIconProvider()
        qfont = self.quick_btn.font()
        for p in self.quick:
            wa = QtWidgets.QWidgetAction(self.quick_menu)
            w = QtWidgets.QWidget()
            hl = QtWidgets.QHBoxLayout(w)
            hl.setContentsMargins(8, 4, 8, 4)
            hl.setSpacing(8)
            info = QtCore.QFileInfo(str(p))
            icon = provider.icon(info)
            icon_lbl = QtWidgets.QLabel()
            icon_pm = icon.pixmap(18, 18)
            if not icon_pm.isNull():
                icon_lbl.setPixmap(icon_pm)
            txt = QtWidgets.QLabel(os.path.basename(p) or p)
            txt.setFont(qfont)
            txt.setStyleSheet('color:white;')
            txt.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            txt.mouseReleaseEvent = (lambda pp: (lambda ev: self.populate_path(pp)))(p)
            btn = QtWidgets.QToolButton()
            btn.setText('−')
            btn.setStyleSheet('color:#ff6b6b; font-weight:700;')
            btn.setAutoRaise(True)
            btn.clicked.connect(partial(self._remove_quick, p))
            hl.addWidget(icon_lbl)
            hl.addWidget(txt)
            hl.addStretch()
            hl.addWidget(btn)
            wa.setDefaultWidget(w)
            self.quick_menu.addAction(wa)
        wa_add = QtWidgets.QWidgetAction(self.quick_menu)
        w_add = QtWidgets.QWidget()
        hl2 = QtWidgets.QHBoxLayout(w_add)
        hl2.setContentsMargins(8, 4, 8, 4)
        lbl_add = QtWidgets.QLabel('Add folder to QuickAccess...')
        lbl_add.setFont(qfont)
        lbl_add.setStyleSheet('color:white;')
        lbl_add.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        lbl_add.mouseReleaseEvent = lambda ev: self._add_quick()
        hl2.addWidget(lbl_add)
        hl2.addStretch()
        wa_add.setDefaultWidget(w_add)
        self.quick_menu.addSeparator()
        self.quick_menu.addAction(wa_add)

    def _add_quick(self):
        f = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select folder')
        if f and f not in self.quick:
            self.quick.append(f)
            save_json(config.QUICK_FILE, self.quick)
            self._rebuild_quick_menu()
            self.populate_home()

    def _remove_quick(self, p):
        ok = QtWidgets.QMessageBox.question(self, 'Remove Quick', f'Remove {p} from QuickAccess?', QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if ok == QtWidgets.QMessageBox.Yes:
            if p in self.quick:
                self.quick.remove(p)
                save_json(config.QUICK_FILE, self.quick)
                self._rebuild_quick_menu()
                self.populate_home()

    def clear_grid(self):
        while self.grid_layout.count():
            it = self.grid_layout.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def populate_home(self):
        """
        Populate quick-access tiles using precomputed tile display size and ALWAYS 8 columns.
        Tile sizes were computed once at startup (self.tile_w / self.tile_h). Window resize
        will NOT change these sizes.
        """
        self.clear_grid()
        self.details.hide()

        cols = 8  # ALWAYS 8 as you required

        r = c = 0
        for p in self.quick:
            try:
                if not os.path.isdir(p):
                    continue
            except:
                continue
            # Use computed display size + native request size for thumbs
            tile = self._Tile(p, self.tile_w, self.tile_h, self.native_w, self.native_h, self.font_scale, is_file=False)
            tile.clicked_play.connect(self._on_tile_play)
            tile.clicked_open.connect(self._on_tile_open)
            self.grid_layout.addWidget(tile, r, c, alignment=QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
            c += 1
            if c >= cols:
                c = 0
                r += 1

        if not self.history or (self.history and self.history_index >= 0 and self.history[self.history_index] != '[HOME]'):
            if self.history_index < len(self.history) - 1:
                self.history = self.history[: self.history_index + 1]
            self.history.append('[HOME]')
            self.history_index = len(self.history) - 1
        self._update_breadcrumb([])
        self.item_count_label.setText(f"Items: {len(self.quick)}")

    def populate_path(self, path):
        path = str(path).replace('\\', '/')  # Normalize path to use forward slashes
        """
        Populate directories + files using the same tile display size and ALWAYS 8 columns.
        """
        self.clear_grid()
        self.details.hide()
        self.spinner.show()

        cols = 8  # ALWAYS 8

        dirs = []
        files = []
        try:
            with os.scandir(path) as it:
                for e in it:
                    if e.is_dir():
                        dirs.append(e.path)
                    elif e.is_file():
                        files.append(str(Path(path) / e.name))
        except Exception:
            dirs = []
            files = []
        total_items = len(dirs) + len(files)
        self.item_count_label.setText(f"Items: {total_items}")


        r = c = 0
        for d in dirs:
            tile = self._Tile(d, self.tile_w, self.tile_h, self.native_w, self.native_h, self.font_scale, is_file=False)
            tile.clicked_play.connect(self._on_tile_play)
            tile.clicked_open.connect(self._on_tile_open)
            self.grid_layout.addWidget(tile, r, c, alignment=QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
            c += 1
            if c >= cols:
                c = 0
                r += 1

        for f in files:
            ft = self._Tile(f, self.tile_w, self.tile_h, self.native_w, self.native_h, self.font_scale, is_file=True)
            ft.clicked_play.connect(lambda ff=f: launch_with_player(self.settings.get('potplayer_path', '').strip(), ff))
            self.grid_layout.addWidget(ft, r, c, alignment=QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
            c += 1
            if c >= cols:
                c = 0
                r += 1

        if not self.history or (self.history and self.history_index >= 0 and self.history[self.history_index] != path):
            if self.history_index < len(self.history) - 1:
                self.history = self.history[: self.history_index + 1]
            self.history.append(path)
            self.history_index = len(self.history) - 1

        self.current_path = path
        parts = list(Path(path).parts)
        self._update_breadcrumb(parts)

        try:
            nfo = Path(self.current_path) / 'details.nfo'
            if nfo.exists():
                try:
                    txt = nfo.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    txt = '(failed to read details.nfo)'
                self.details.setPlainText(txt)
                self.details.show()
            else:
                self.details.hide()
        except Exception:
            self.details.hide()

        self.spinner.hide()

    def _on_tile_play(self, folder_path):
        pot = self.settings.get('potplayer_path', '').strip()
        dpl = Path(folder_path) / 'playlist.dpl'
        if dpl.exists():
            if launch_with_player(pot, str(dpl)):
                return
        fv = find_first_video(folder_path)
        if fv:
            if launch_with_player(pot, fv):
                return
        self.populate_path(folder_path)

    def _on_tile_open(self, folder_path):
        self.populate_path(folder_path)

    def _update_breadcrumb(self, parts):
        while self.breadcrumb_layout.count():
            it = self.breadcrumb_layout.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        home_btn = QtWidgets.QToolButton()
        home_btn.setText('Home')
        home_btn.clicked.connect(self.show_home)
        bfont = QtGui.QFont()
        bfont.setPointSize(14)
        home_btn.setFont(bfont)
        self.breadcrumb_layout.addWidget(home_btn)

        if not parts:
            return

        accum = Path(parts[0])
        max_seg_w = 160
        for p in parts[1:]:
            accum = accum / p
            sep = QtWidgets.QLabel('/')
            sep.setStyleSheet('color:#bbb;')
            self.breadcrumb_layout.addWidget(sep)
            btn = QtWidgets.QToolButton()
            btn.setAutoRaise(True)
            btn.setFont(bfont)
            metrics = QtGui.QFontMetrics(bfont)
            elided = metrics.elidedText(p, QtCore.Qt.ElideRight, max_seg_w)
            btn.setText(elided)
            btn.setToolTip(p)
            btn.clicked.connect(partial(self.populate_path, str(accum).replace('\\', '/')))
            self.breadcrumb_layout.addWidget(btn)

    def on_search_input(self, text):
        """Called immediately when text changes - just restart the timer"""
        self.search_timer.stop()
        if text.strip():
            self.search_timer.start(500)  # Wait 500ms after user stops typing
        else:
            self.on_search_delayed()  # Clear immediately when empty

    def on_search_delayed(self):
        """Called after user stops typing for 500ms"""
        text = self.search.text()
        q = text.strip().lower()
        if not q:
            if self.history and self.history_index >= 0:
                cur = self.history[self.history_index]
                if cur == '[HOME]':
                    self.populate_home()
                else:
                    self.populate_path(cur)
            else:
                self.populate_home()
            return

        cols = 8  # ALWAYS 8 for search results too

        cur = self.history[self.history_index] if (self.history and self.history_index >= 0) else ''
        if cur == '[HOME]':
            matches = [p for p in self.quick if q in os.path.basename(p).lower()]
            self.clear_grid()
            r = c = 0
            for p in matches:
                tile = self._Tile(p, self.tile_w, self.tile_h, self.native_w, self.native_h, self.font_scale, is_file=False)
                tile.clicked_play.connect(self._on_tile_play)
                tile.clicked_open.connect(self._on_tile_open)
                self.grid_layout.addWidget(tile, r, c, alignment=QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
                c += 1
                if c >= cols:
                    c = 0
                    r += 1
            return

        if cur and cur != '[HOME]' and os.path.isdir(cur):
            found = []
            try:
                with os.scandir(cur) as it:
                    for e in it:
                        if e.is_dir() and q in e.name.lower():
                            found.append(str(Path(cur) / e.name))
            except Exception:
                found = []
            self.clear_grid()
            r = c = 0
            for p in found:
                tile = self._Tile(p, self.tile_w, self.tile_h, self.native_w, self.native_h, self.font_scale, is_file=False)
                tile.clicked_play.connect(self._on_tile_play)
                tile.clicked_open.connect(self._on_tile_open)
                self.grid_layout.addWidget(tile, r, c, alignment=QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
                c += 1
                if c >= cols:
                    c = 0
                    r += 1
            try:
                count = self.grid_layout.count()
                self.item_count_label.setText(f"Items: {count}")
            except Exception:
                pass

    def resizeEvent(self, ev):
        # Intentionally do nothing to tile sizes on window resize:
        # tiles keep the computed size from startup (no popping).
        super().resizeEvent(ev)

    def show_home(self):
        self.populate_home()

    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            p = self.history[self.history_index]
            if p == '[HOME]':
                self.populate_home()
            else:
                self.populate_path(p)

    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            p = self.history[self.history_index]
            if p == '[HOME]':
                self.populate_home()
            else:
                self.populate_path(p)

    def collect_posters_from_quick(self):
        from poster_utils import move_poster, get_new_poster_path
        import config
        import os
        from pathlib import Path

        posters_root = str(config.APP_DIR / 'posters')
        moved_count = 0

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # --- Step 1: Find all folders to process ---
        folders_to_process = []

        def gather_folders(folder_path):
            folders_to_process.append(folder_path)
            try:
                with os.scandir(folder_path) as it:
                    for entry in it:
                        if entry.is_dir():
                            gather_folders(entry.path)
            except Exception:
                pass

        for folder_path in self.quick:
            gather_folders(folder_path)

        self.progress_bar.setMaximum(len(folders_to_process))

        # --- Step 2: Process each folder and update progress ---
        def process_folder(folder_path):
            nonlocal moved_count
            try:
                result = move_poster(folder_path, posters_root)
                if result:
                    moved_count += 1
            except Exception as e:
                    pass

        for idx, folder_path in enumerate(folders_to_process):
            process_folder(folder_path)
            self.progress_bar.setValue(idx + 1)
            QtWidgets.QApplication.processEvents()  # This keeps the UI responsive

        QtWidgets.QMessageBox.information(
            self, 
            "Posters Collected", 
            f"Finished moving {moved_count} posters from all Quick folders and their subfolders."
        )
        self.progress_bar.setVisible(False)