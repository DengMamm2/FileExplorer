# ui/effects.py
from PyQt5 import QtCore, QtWidgets, QtGui

class ShineEffect(QtWidgets.QFrame):
    def __init__(self, holder, visible_w, visible_h):
        super().__init__(holder)
        self.setStyleSheet(
            """background: qlineargradient(
                x1:1, y1:0, x2:0, y2:1,
                stop:0 rgba(255,255,255,0),
                stop:0.5 rgba(255,255,255,80),
                stop:1 rgba(255,255,255,0)
            );
            border-radius:10px;"""
        )
        # oversize so diagonal pass fully covers
        self.setGeometry(-visible_w, -visible_h, visible_w * 2, visible_h * 2)
        self.hide()

        self.anim = QtCore.QPropertyAnimation(self, b"pos", self)
        self.anim.setDuration(200)  # fast
        self.anim.setStartValue(QtCore.QPoint(visible_w, -visible_h))   # top-right
        self.anim.setEndValue(QtCore.QPoint(-visible_w, visible_h))     # bottom-left
        self.anim.setLoopCount(1)
        self.anim.setEasingCurve(QtCore.QEasingCurve.InOutCubic)

    def start(self):
        self.show()
        self.anim.stop()
        self.anim.start()

class HoverGrow(QtCore.QPropertyAnimation):
    def __init__(self, holder, visible_w, visible_h):
        super().__init__(holder, b"geometry")
        self.holder = holder
        self.visible_w = visible_w
        self.visible_h = visible_h
        self.setDuration(150)
        self.setEasingCurve(QtCore.QEasingCurve.InOutQuad)

    def grow(self):
        rect = self.holder.geometry()
        bigger = QtCore.QRect(
            int(rect.x() - rect.width() * 0.025),
            int(rect.y() - rect.height() * 0.025),
            int(rect.width() * 1.05),
            int(rect.height() * 1.05),
        )
        self.stop()
        self.setStartValue(rect)
        self.setEndValue(bigger)
        self.start()

    def shrink(self):
        self.stop()
        self.setEndValue(QtCore.QRect(0, 0, self.visible_w, self.visible_h))
        self.start()
