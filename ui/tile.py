# ui/tile.py
from PyQt5 import QtCore, QtGui, QtWidgets
from typing import Optional
from pathlib import Path
import os
import traceback

import utils
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

        # layout sizing (same approach as original)
        outer_margin_lr = 12
        visible_meta_h = max(20, int(getattr(utils, "META_H", 72)))
        self.setFixedSize(self.visible_w + outer_margin_lr, self.visible_h + visible_meta_h)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        # Poster holder
        self.holder = QtWidgets.QFrame(self)
        self.holder.setFixedSize(self.visible_w, self.visible_h)
        self.holder.setStyleSheet("background:#151515; border-radius:10px;")
        outer.addWidget(self.holder, alignment=QtCore.Qt.AlignHCenter)

        sh = QtWidgets.QGraphicsDropShadowEffect(self.holder)
        sh.setBlurRadius(18)
        sh.setOffset(0, 6)
        sh.setColor(QtGui.QColor(0, 0, 0, 200))
        self.holder.setGraphicsEffect(sh)

        # Poster label
        self.img_lbl = QtWidgets.QLabel(self.holder)
        self.img_lbl.setGeometry(0, 0, self.visible_w, self.visible_h)
        self.img_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.img_lbl.setStyleSheet("border-radius:10px;")
        self.img_lbl.setScaledContents(False)

        # Meta area (unchanged visual)
        meta_widget = QtWidgets.QWidget(self)
        mv = QtWidgets.QVBoxLayout(meta_widget)
        mv.setContentsMargins(4, 0, 4, 0)
        mv.setSpacing(2)
        self.meta_line = QtWidgets.QLabel("")
        meta_font_px = max(10, int(13 * self.font_scale))
        self.meta_line.setStyleSheet(f"color: rgba(200,200,200,0.95); font-size:{meta_font_px}px;")
        title_pt = max(10, int(12 * self.font_scale))
        self.title_btn = LinkButton("", parent=meta_widget, pt=title_pt)
        self.title_btn.clicked.connect(lambda: self.clicked_open.emit(self.path))
        mv.addWidget(self.meta_line)
        mv.addWidget(self.title_btn)
        outer.addWidget(meta_widget)

        # Name parsing (keeps title/metadata behavior exactly)
        nm = Path(self.path).name
        parts = [p.strip() for p in nm.rsplit(" - ", 2)]
        if len(parts) == 3:
            self.meta_line.setText(f"{parts[1]} - ★{parts[2]}")
            self.title_btn.setText(parts[0])
        else:
            self.meta_line.setText("")
            self.title_btn.setText(nm)

        # Default SVG or fallback background (same as before)
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

        # schedule thumbnail load (images) OR defer folder scan to event loop
        if self.is_file and utils.is_image_file(self.path):
          ThumbnailLoader.instance().load(
              self.path, self.native_w, self.native_h, self._on_thumb_ready
          )

        elif not self.is_file:
            # DEFER the scan until after constructor returns to avoid UI freeze
            QtCore.QTimer.singleShot(0, self._start_media_scan)

        # Build play icon pixmap (unchanged drawing)
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
                # center it
                x = (self.visible_w - play_pm.width()) // 2
                y = (self.visible_h - play_pm.height()) // 2
                self.play_overlay.move(max(0, x), max(0, y))

                # ensure hidden at startup (this prevents the "visible by default" bug)
                try:
                    self.play_overlay.hide()
                    self.play_overlay.setVisible(False)
                except Exception:
                    pass

                def _on_play(ev):
                    if self.has_media:
                        self.clicked_play.emit(self.path)

                self.play_overlay.mouseReleaseEvent = _on_play
        except Exception:
            self.play_overlay = None

        # clicking the poster opens
        self.img_lbl.mouseReleaseEvent = lambda ev: self.clicked_open.emit(self.path)

        # shine overlay (diagonal) + animations (inline, kept as earlier)
        self.shine_overlay = QtWidgets.QFrame(self.holder)
        self.shine_overlay.setStyleSheet(
            """background: qlineargradient(
                x1:1, y1:0, x2:0, y2:1,
                stop:0 rgba(255,255,255,0),
                stop:0.5 rgba(255,255,255,80),
                stop:1 rgba(255,255,255,0)
            );
            border-radius:10px;"""
        )
        # oversize so diagonal pass fully covers
        self.shine_overlay.setGeometry(-self.visible_w, -self.visible_h,
                                       self.visible_w * 2, self.visible_h * 2)
        self.shine_overlay.hide()

        self._shine_anim = QtCore.QPropertyAnimation(self.shine_overlay, b"pos", self)
        self._shine_anim.setDuration(200)
        self._shine_anim.setStartValue(QtCore.QPoint(self.visible_w, -self.visible_h))
        self._shine_anim.setEndValue(QtCore.QPoint(-self.visible_w, self.visible_h))
        self._shine_anim.setLoopCount(1)
        self._shine_anim.setEasingCurve(QtCore.QEasingCurve.InOutCubic)

        # pop-out animation
        self._hover_anim = QtCore.QPropertyAnimation(self.holder, b"geometry", self)
        self._hover_anim.setDuration(150)
        self._hover_anim.setEasingCurve(QtCore.QEasingCurve.InOutQuad)

        self.setAttribute(QtCore.Qt.WA_Hover, True)

    # --- Media scan (async) ---
    def _start_media_scan(self):
        """Start a MediaScanner QRunnable (kept as worker in workers/media_scanner.py)."""
        try:
            if getattr(self, "_scanner_job", None) is not None:
                return
            scanner = MediaScanner(self.path)
            # keep reference to avoid GC
            self._scanner_job = scanner
            scanner.signals.media_scanned.connect(self._on_media_scanned, QtCore.Qt.QueuedConnection)
            QtCore.QThreadPool.globalInstance().start(scanner)
        except Exception:
            # do not raise — keep UI alive
            traceback.print_exc()

    def _on_media_scanned(self, path: str, poster: str, has_media: bool):
        """Apply results received from the MediaScanner worker."""
        try:
            if path != self.path:
                return

            # mark done
            self._media_scan_done = True
            self.has_media = bool(has_media)

            #if poster found, load it (once)
            if poster and not self.poster_loaded:
              self.poster_loaded = True
              self.poster_path = poster
              ThumbnailLoader.instance().load(poster, self.native_w, self.native_h, self._on_thumb_ready)

            # update overlay visibility: only show if mouse is over this tile
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

            # force repaint so state is visible immediately
            try:
                self.update()
                if self.play_overlay:
                    self.play_overlay.update()
            except Exception:
                pass

        except Exception:
            traceback.print_exc()

    # --- Thumbnail callback ---
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

    # --- Play icon builder (unchanged) ---
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

    # --- Hover effects ---
    def enterEvent(self, ev):
        super().enterEvent(ev)
        if self.has_media and self.play_overlay:
            self.play_overlay.show()
            self.play_overlay.raise_()

        # shine
        self.shine_overlay.show()
        self._shine_anim.stop()
        self._shine_anim.start()

        # pop-out
        self._hover_anim.stop()
        rect = self.holder.geometry()
        bigger = QtCore.QRect(
            int(rect.x() - rect.width() * 0.025),
            int(rect.y() - rect.height() * 0.025),
            int(rect.width() * 1.05),
            int(rect.height() * 1.05),
        )
        self._hover_anim.setStartValue(rect)
        self._hover_anim.setEndValue(bigger)
        self._hover_anim.start()

    def leaveEvent(self, ev):
        super().leaveEvent(ev)
        if self.play_overlay:
            self.play_overlay.hide()
        self.shine_overlay.hide()

        # shrink back
        self._hover_anim.stop()
        self._hover_anim.setEndValue(QtCore.QRect(0, 0, self.visible_w, self.visible_h))
        self._hover_anim.start()
