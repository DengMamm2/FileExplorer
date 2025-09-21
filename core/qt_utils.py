# core/qt_utils.py
from PyQt5 import QtCore, QtGui, QtSvg
from typing import Optional

# SVG helper strings (kept identical to original)
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

def compose_centered(src_pm: QtGui.QPixmap, target_w: int, target_h: int) -> QtGui.QPixmap:
    if src_pm.isNull():
        out = QtGui.QPixmap(target_w, target_h)
        out.fill(QtCore.Qt.transparent)
        return out
    sw, sh = src_pm.width(), src_pm.height()
    if sw > target_w or sh > target_h:
        scaled = src_pm.scaled(target_w, target_h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
    else:
        scaled = src_pm
    out = QtGui.QPixmap(target_w, target_h)
    out.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(out)
    x = (target_w - scaled.width()) // 2
    y = (target_h - scaled.height()) // 2
    p.drawPixmap(x, y, scaled)
    p.end()
    return out

def compose_centered_from_qimage(qimg: QtGui.QImage, target_w: int, target_h: int) -> QtGui.QPixmap:
    if qimg is None or qimg.isNull():
        out = QtGui.QPixmap(target_w, target_h)
        out.fill(QtCore.Qt.transparent)
        return out
    pm = QtGui.QPixmap.fromImage(qimg)
    return compose_centered(pm, target_w, target_h)
