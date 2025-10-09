import json
import os
import hashlib
from pathlib import Path
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets, QtSvg
import config

# in-memory pixmap cache for the session
PX_CACHE = {}  # (path, w, h) -> QPixmap


def load_json(path: Path, default: dict):
    try:
        if not path.exists():
            path.write_text(json.dumps(default, indent=2), encoding='utf-8')
            return default.copy()
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default.copy()


def save_json(path: Path, obj):
    try:
        path.write_text(json.dumps(obj, indent=2), encoding='utf-8')
    except Exception:
        pass


def is_video_file(name: str) -> bool:
    return Path(name).suffix.lower() in config.VIDEO_EXTS


def is_image_file(name: str) -> bool:
    return Path(name).suffix.lower() in config.IMAGE_EXTS


def find_first_video(folder: str) -> Optional[str]:
    try:
        with os.scandir(folder) as it:
            for e in it:
                if e.is_file() and is_video_file(e.name):
                    return str(Path(folder) / e.name)
    except Exception:
        return None
    return None




def read_first_dpl_basename(path: str) -> Optional[str]:
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                ln = line.strip()
                # look for the first line starting with "playname="
                if ln.lower().startswith('playname='):
                    filename = ln.split('=', 1)[1].strip()
                    # replace backslashes with forward slashes for consistent basename
                    filename = filename.replace('\\', '/')
                    return os.path.basename(filename)
    except Exception as e:
        return None
    return None




def launch_with_player(player_exe: str, target: str) -> bool:
    try:
        if player_exe:
            QtCore.QProcess.startDetached(player_exe, [target])
        else:
            if sys.platform.startswith('win'):
                os.startfile(target)
            else:
                QtCore.QProcess.startDetached('xdg-open', [target])
        return True
    except Exception as e:
        QtWidgets.QMessageBox.warning(None, 'Launch failed', f'Failed to open {target}:\n{e}')
        return False


# SVG helper
FOLDER_SVG = r'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 100">
  <rect x="2" y="30" rx="8" ry="8" width="116" height="64" fill="#222" stroke="#3a3a3a" stroke-width="2"/>
  <path d="M8 30 h30 l8-10 h44 v10" fill="#2d2d2d" stroke="#3a3a3a" stroke-width="2"/>
</svg>'''
MAG_SVG = r'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="#111" d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79L20 20.49 21.49 19 15.5 14zM10 14a4 4 0 110-8 4 4 0 010 8z"/></svg>'''


def svg_to_pixmap(svg_text: str, w: int, h: Optional[int] = None) -> QtGui.QPixmap:
    if h is None:
        h = w
    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg_text.encode('utf-8')))
    pix = QtGui.QPixmap(w, h)
    pix.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pix)
    renderer.render(painter)
    painter.end()
    return pix


# cache helpers

def cache_path_for(source_path: str, w: int, h: int) -> Path:
    try:
        mtime = int(Path(source_path).stat().st_mtime)
    except Exception:
        mtime = 0
    key = hashlib.sha1(f"{str(Path(source_path).absolute())}|{mtime}".encode('utf-8')).hexdigest()
    bucket = config.CACHE_ROOT / f"{w}x{h}"
    bucket.mkdir(parents=True, exist_ok=True)
    return bucket / f"{key}.jpg"


def cache_get(path, w, h):
    return PX_CACHE.get((str(path), int(w), int(h)))


def cache_set(path, w, h, pix: QtGui.QPixmap):
    PX_CACHE[(str(path), int(w), int(h))] = pix


# centered composition helpers

def compose_centered(src_pm: QtGui.QPixmap, target_w: int, target_h: int) -> QtGui.QPixmap:
    if src_pm.isNull():
        out = QtGui.QPixmap(target_w, target_h)
        out.fill(QtCore.Qt.transparent)
        return out
    
    # Scale to exact height (540px), maintain aspect ratio
    src_w, src_h = src_pm.width(), src_pm.height()
    scale_factor = target_h / src_h
    new_w = int(src_w * scale_factor)
    new_h = target_h
    
    # Scale the image to the calculated size
    scaled = src_pm.scaled(new_w, new_h, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
    
    # Create output pixmap
    out = QtGui.QPixmap(target_w, target_h)
    out.fill(QtCore.Qt.transparent)
    
    # Create rounded mask
    mask = QtGui.QBitmap(target_w, target_h)
    mask.fill(QtCore.Qt.color0)
    mask_painter = QtGui.QPainter(mask)
    mask_painter.setRenderHint(QtGui.QPainter.Antialiasing)
    mask_painter.setBrush(QtGui.QBrush(QtCore.Qt.color1))
    mask_painter.setPen(QtCore.Qt.NoPen)
    mask_painter.drawRoundedRect(0, 0, target_w, target_h, 10, 10)
    mask_painter.end()
    
    # Draw the scaled image, cropping if wider than target width
    p = QtGui.QPainter(out)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    
    if new_w <= target_w:
        # Image is narrower or equal to target width - center it
        x_offset = (target_w - new_w) // 2
        p.drawPixmap(x_offset, 0, scaled)
    else:
        # Image is wider than target width - crop it by centering the crop
        x_crop = (new_w - target_w) // 2
        source_rect = QtCore.QRect(x_crop, 0, target_w, target_h)
        p.drawPixmap(0, 0, target_w, target_h, scaled, x_crop, 0, target_w, target_h)
    
    p.end()
    
    # Apply the rounded mask to the final result
    out.setMask(mask)
    return out
    
    # Create output pixmap
    out = QtGui.QPixmap(target_w, target_h)
    out.fill(QtCore.Qt.transparent)
    
    # Create rounded mask
    mask = QtGui.QBitmap(target_w, target_h)
    mask.fill(QtCore.Qt.color0)
    mask_painter = QtGui.QPainter(mask)
    mask_painter.setRenderHint(QtGui.QPainter.Antialiasing)
    mask_painter.setBrush(QtGui.QBrush(QtCore.Qt.color1))
    mask_painter.setPen(QtCore.Qt.NoPen)
    mask_painter.drawRoundedRect(0, 0, target_w, target_h, 10, 10)
    mask_painter.end()
    
    # Draw the scaled image to fill entire area
    p = QtGui.QPainter(out)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.drawPixmap(0, 0, scaled)
    p.end()
    
    # Apply the rounded mask to the final result
    out.setMask(mask)
    return out


def compose_centered_from_qimage(qimg: QtGui.QImage, target_w: int, target_h: int) -> QtGui.QPixmap:
    if qimg is None or qimg.isNull():
        out = QtGui.QPixmap(target_w, target_h)
        out.fill(QtCore.Qt.transparent)
        return out
    pm = QtGui.QPixmap.fromImage(qimg)
    return compose_centered(pm, target_w, target_h)