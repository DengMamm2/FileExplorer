# ui/tile.py
import os
import ui_settings
import traceback
from pathlib import Path
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

import utils
import config
from ui.widgets import LinkButton
from ui.thumbs import ThumbnailLoader
from workers.media_scanner import MediaScanner


class Tile(QtWidgets.QFrame):
    clicked_play = QtCore.pyqtSignal(str)
    clicked_open = QtCore.pyqtSignal(str)

    def __init__(
        self,
        path: str,
        visible_w: int,
        visible_h: int,
        native_w: int,
        native_h: int,
        font_scale: float,
        is_file=False,
        parent=None,
    ):
        super().__init__(parent)
        self.path = str(path)
        self.visible_w = int(visible_w)
        self.visible_h = int(visible_h)
        self.native_w = int(native_w)
        self.native_h = int(native_h)
        self.font_scale = float(font_scale)
        self.is_file = bool(is_file)

        # state
        self.poster_path: Optional[str] = None
        self.poster_loaded = False
        self.has_media = False
        self._scanner_job = None
        self._media_scan_done = False

        # COMPLETELY DYNAMIC APPROACH: NO HEIGHT RESTRICTIONS WHATSOEVER
        outer_margin = ui_settings.OUTER_MARGIN
    
        # Start with just the poster size - we'll expand as needed
        total_width = self.visible_w + outer_margin
    
        # Create a temporary widget to measure text size
        temp_widget = QtWidgets.QWidget()
        temp_layout = QtWidgets.QVBoxLayout(temp_widget)
        temp_layout.setContentsMargins(4, 0, 4, 0)
        temp_layout.setSpacing(2)
    
        # Parse folder name to determine what text we'll display
        nm = Path(self.path).name

        # Look for year (4 digits) and rating (x.x format) at the end
        import re
        year_rating_pattern = r'(.+?)\s*-\s*(\d{4})\s*-\s*(\d+\.\d+)$'
        match = re.match(year_rating_pattern, nm)

        if match:
            title = match.group(1).strip()
            year = match.group(2)
            rating = match.group(3)
            parts = [title, year, rating]
        else:
            parts = [nm]
    
        # Create temporary labels to measure text size
        meta_font_px = max(8, min(24, int(ui_settings.META_FONT_SIZE * self.font_scale)))
        temp_meta = QtWidgets.QLabel("")
        temp_meta.setStyleSheet(f"color: rgba(200,200,200,0.95); font-size:{meta_font_px}px;")
        temp_meta.setAlignment(QtCore.Qt.AlignCenter)
    
        title_pt = max(6, min(20, int(ui_settings.TITLE_FONT_SIZE * self.font_scale)))
        temp_title = QtWidgets.QLabel("")
        temp_title.setWordWrap(True)
        temp_title.setAlignment(QtCore.Qt.AlignCenter)
        title_font = temp_title.font()
        title_font.setPointSize(int(title_pt))
        title_font.setBold(True)
        temp_title.setFont(title_font)
    
        # Set the actual text content
        nm = Path(self.path).name

        # Look for year (4 digits) and rating (x.x format) at the end
        import re
        year_rating_pattern = r'(.+?)\s*-\s*(\d{4})\s*-\s*(\d+\.\d+)$'
        year_only_pattern = r'(.+?)\s*-\s*(\d{4})$'
        rating_only_pattern = r'(.+?)\s*-\s*(\d+\.\d+)$'

        match_both = re.match(year_rating_pattern, nm)
        match_year = re.match(year_only_pattern, nm)
        match_rating = re.match(rating_only_pattern, nm)

        if match_both:
            title = match_both.group(1).strip()
            year = match_both.group(2)
            rating = match_both.group(3)
            temp_meta.setText(f"{year} - ★{rating}")
            temp_title.setText(title)
        elif match_year:
            title = match_year.group(1).strip()
            year = match_year.group(2)
            temp_meta.setText(year)
            temp_title.setText(title)
        elif match_rating:
            title = match_rating.group(1).strip()
            rating = match_rating.group(2)
            temp_meta.setText(f"★{rating}")
            temp_title.setText(title)
        else:
            temp_meta.setText("")
            temp_title.setText(nm)
    
        # Set fixed width for text measurement (same as tile width minus margins)
        text_width = total_width - 12
        temp_title.setFixedWidth(text_width - 8)  # Account for layout margins
    
        temp_layout.addWidget(temp_meta)
        temp_layout.addWidget(temp_title)
    
        # Force the layout to calculate its size - with error handling
        try:
            temp_widget.adjustSize()
            needed_text_height = temp_widget.sizeHint().height()
            if needed_text_height <= 0 or needed_text_height > 200:
                needed_text_height = 50  # Safe fallback
        except Exception:
            needed_text_height = 50  # Safe fallback if measurement fails
    
        # Add generous padding to ensure text is never cut off
        text_area_height = needed_text_height + ui_settings.TEXT_PADDING
    
        # NOW set the total tile size with the measured text height
        total_height = self.visible_h + text_area_height + outer_margin + ui_settings.EXTRA_MARGIN
        self.setFixedSize(total_width, total_height)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

        # POSTER AREA: Positioned at the top with exact coordinates
        self.holder = QtWidgets.QFrame(self)
        poster_x = (total_width - self.visible_w) // 2  # Center horizontally
        poster_y = 6  # Top margin
        self.holder.setGeometry(poster_x, poster_y, self.visible_w, self.visible_h)
        self.holder.setStyleSheet("background:transparent; border-radius:10px;")

        # Shadow for poster
        sh = QtWidgets.QGraphicsDropShadowEffect(self.holder)
        sh.setBlurRadius(18)
        sh.setOffset(0, 6)
        sh.setColor(QtGui.QColor(0, 0, 0, 200))
        self.holder.setGraphicsEffect(sh)

        # Poster image label
        self.img_lbl = QtWidgets.QLabel(self.holder)
        self.img_lbl.setGeometry(0, 0, self.visible_w, self.visible_h)
        self.img_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.img_lbl.setStyleSheet("border-radius:10px;")
        self.img_lbl.setScaledContents(False)
        # --- DARKEN ON HOVER START ---
        self.overlay_lbl = QtWidgets.QLabel(self.holder)
        self.overlay_lbl.setGeometry(0, 0, self.visible_w, self.visible_h)
        self.overlay_lbl.setStyleSheet(
            "background-color: rgba(0, 0, 0, 0); border-radius:10px;"
        )
        self.overlay_lbl.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.overlay_lbl.hide()
        self.img_lbl.installEventFilter(self)

        # TEXT AREA: Positioned BELOW poster with NO HEIGHT RESTRICTIONS
        text_x = 6
        text_y = poster_y + self.visible_h + 10  # 10 pixels below poster
    
        # Create the actual text container with the measured height
        self.text_container = QtWidgets.QWidget(self)
        self.text_container.setGeometry(text_x, text_y, text_width, text_area_height)
        text_layout = QtWidgets.QVBoxLayout(self.text_container)
        text_layout.setContentsMargins(ui_settings.TEXT_MARGIN_LEFT, 0, ui_settings.TEXT_MARGIN_RIGHT, 0)
        text_layout.setSpacing(ui_settings.TEXT_SPACING)

        # Create the actual labels (same as temp ones but these are the real ones)
        self.meta_line = QtWidgets.QLabel("")
        self.meta_line.setStyleSheet(f"color: #707070; font-size:{meta_font_px}px;")
        self.meta_line.setAlignment(QtCore.Qt.AlignCenter)

        self.title_label = QtWidgets.QLabel("")
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.title_label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.title_label.mouseReleaseEvent = lambda ev: self.clicked_open.emit(self.path)

        # Style the title label
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("""
        QLabel {
            color: #ddd;
            border: none;
        }
        QLabel:hover {
            color: white;
        }
        """)

        text_layout.addWidget(self.meta_line)
        text_layout.addWidget(self.title_label)

        # Set the final text content
        nm = Path(self.path).name

        # Look for year (4 digits) and rating (x.x format) at the end
        import re
        year_rating_pattern = r'(.+?)\s*-\s*(\d{4})\s*-\s*(\d+\.\d+)$'
        year_only_pattern = r'(.+?)\s*-\s*(\d{4})$'
        rating_only_pattern = r'(.+?)\s*-\s*(\d+\.\d+)$'

        match_both = re.match(year_rating_pattern, nm)
        match_year = re.match(year_only_pattern, nm)
        match_rating = re.match(rating_only_pattern, nm)

        if match_both:
            title = match_both.group(1).strip()
            year = match_both.group(2)
            rating = match_both.group(3)
            self.meta_line.setText(f"{year} - ★{rating}")
            self.title_label.setText(title)
        elif match_year:
            title = match_year.group(1).strip()
            year = match_year.group(2)
            self.meta_line.setText(year)
            self.title_label.setText(title)
        elif match_rating:
            title = match_rating.group(1).strip()
            rating = match_rating.group(2)
            self.meta_line.setText(f"★{rating}")
            self.title_label.setText(title)
        else:
            self.meta_line.setText("")
            self.title_label.setText(nm)

        # Clean up temporary widget
        temp_widget.deleteLater()

        # Default SVG or fallback background
        try:
            svgpm = utils.svg_to_pixmap(utils.FOLDER_SVG, max(self.visible_w, self.visible_h))
            if not svgpm.isNull():
                svg_draw = svgpm.scaled(
                    self.visible_w, self.visible_h,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
                if not svg_draw.isNull():
                    self.img_lbl.setPixmap(svg_draw)
                else:
                    raise Exception("scaled svg returned null")
            else:
                raise Exception("svg returned null")
        except Exception:
            fb = QtGui.QPixmap(self.visible_w, self.visible_h)
            fb.fill(QtGui.QColor("#2b2b2b"))
            self.img_lbl.setPixmap(fb)

        # Schedule thumbnail load
        if self.is_file and utils.is_image_file(self.path):
            ThumbnailLoader.instance().load(
                self.path, self.native_w, self.native_h, self._on_thumb_ready
            )
        elif not self.is_file:
            QtCore.QTimer.singleShot(0, self._start_media_scan)

        # Build play icon pixmap
        self.play_overlay = None
        try:
            play_pm = self._build_play_pixmap()
            if play_pm is not None and not play_pm.isNull():
                self.play_overlay = QtWidgets.QLabel(self.holder)
                self.play_overlay.setPixmap(play_pm)
                self.play_overlay.setFixedSize(play_pm.size())
                self.play_overlay.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
                self.play_overlay.setStyleSheet("background: transparent;")
                self.play_overlay.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
                x = (self.visible_w - play_pm.width()) // 2
                y = (self.visible_h - play_pm.height()) // 2
                self.play_overlay.move(max(0, x), max(0, y))
                self.play_overlay.hide()

                def _on_play(ev):
                    if ev.button() == QtCore.Qt.LeftButton:
                        self.clicked_play.emit(self.path)

                self.play_overlay.mouseReleaseEvent = _on_play
        except Exception:
            self.play_overlay = None

        # Clicking the poster opens
        self.img_lbl.mouseReleaseEvent = lambda ev: self.clicked_open.emit(self.path)

    # ALL METHODS BELOW ARE UNCHANGED
    def _start_media_scan(self):
        """Start a MediaScanner QRunnable (kept as worker in workers/media_scanner.py)."""
        try:
            if getattr(self, "_scanner_job", None) is not None:
                return
            scanner = MediaScanner(self.path)
            self._scanner_job = scanner
            scanner.signals.media_scanned.connect(self._on_media_scanned, QtCore.Qt.QueuedConnection)
            QtCore.QThreadPool.globalInstance().start(scanner)
        except Exception:
            traceback.print_exc()

    def _on_media_scanned(self, path: str, poster: str, has_media: bool):
        """Apply results received from the MediaScanner worker."""
        try:
            if path != self.path:
                return

            self._media_scan_done = True
            self.has_media = bool(has_media)

            if poster and not self.poster_loaded:
                self.poster_loaded = True
                self.poster_path = poster
                ThumbnailLoader.instance().load(poster, self.native_w, self.native_h, self._on_thumb_ready)

            if self.play_overlay:
                try:
                    if self.has_media and self.underMouse():
                        self.play_overlay.show()
                        self.play_overlay.raise_()
                    else:
                        self.play_overlay.hide()
                except Exception:
                    try:
                        self.play_overlay.hide()
                    except Exception:
                        pass

            try:
                self.update()
                if self.play_overlay:
                    self.play_overlay.update()
            except Exception:
                pass

        except Exception:
            traceback.print_exc()

    def _on_thumb_ready(self, path: str, qimg: Optional[QtGui.QImage]):
        try:
            cached = utils.cache_get(path, self.visible_w, self.visible_h)
            if cached:
                self.img_lbl.setPixmap(cached)
                return

            if qimg is None or qimg.isNull():
                return

            out = utils.compose_centered_from_qimage(qimg, self.visible_w, self.visible_h)
            utils.cache_set(path, self.visible_w, self.visible_h, out)
            self.img_lbl.setPixmap(out)
        except Exception:
            traceback.print_exc()

    def _build_play_pixmap(self) -> Optional[QtGui.QPixmap]:
        try:
            size = 96
            pm = QtGui.QPixmap(size, size)
            pm.fill(QtCore.Qt.transparent)
            p = QtGui.QPainter(pm)
            p.setRenderHint(QtGui.QPainter.Antialiasing)

            brush = QtGui.QBrush(QtGui.QColor(0, 0, 0, 160))
            p.setBrush(brush)
            p.setPen(QtCore.Qt.NoPen)
            radius = int(size * 0.45)
            center = QtCore.QPoint(size // 2, size // 2)
            p.drawEllipse(center, radius, radius)

            p.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 230)))
            tri = [
                QtCore.QPoint(center.x() - radius // 3, center.y() - radius // 2),
                QtCore.QPoint(center.x() - radius // 3, center.y() + radius // 2),
                QtCore.QPoint(center.x() + radius // 2, center.y()),
            ]
            p.drawPolygon(QtGui.QPolygon(tri))
            p.end()

            disp_w = min(128, max(36, int(min(self.visible_w, self.visible_h) * 0.4)))
            scaled = pm.scaled(disp_w, disp_w, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            return scaled
        except Exception:
            return None

    # --- DARK OVERLAY ON HOVER LOGIC ---
    def eventFilter(self, obj, event):
        if obj == self.img_lbl:
            if event.type() == QtCore.QEvent.Enter:
                # Show overlay, 25% darker
                self.overlay_lbl.setStyleSheet(
                    "background-color: rgba(0, 0, 0, 128); border-radius:10px;"
                )  # 64/255 ≈ 25% opacity
                self.overlay_lbl.show()
            elif event.type() == QtCore.QEvent.Leave:
                self.overlay_lbl.hide()
        return super().eventFilter(obj, event)