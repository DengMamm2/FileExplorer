from PyQt5 import QtCore, QtGui, QtWidgets

class Spinner(QtWidgets.QLabel):
    def __init__(self, size=48, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAlignment(QtCore.Qt.AlignCenter)
        movie = QtGui.QMovie("assets/spinner.gif", QtCore.QByteArray(), self)
        movie.setScaledSize(QtCore.QSize(size, size))
        self.setMovie(movie)
        movie.start()

class LinkButton(QtWidgets.QPushButton):
    def __init__(self, text='', parent=None, pt=12):
        super().__init__(text, parent)
        self.setFlat(True)
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        f = self.font(); f.setPointSize(int(pt)); f.setBold(True); self.setFont(f)
        self.setStyleSheet("""
    QPushButton {
        color: #ddd;
        text-align: left;
        border: none;
    }
    QPushButton:hover {
        text-decoration: underline;
        color: white;
    }
    """)

