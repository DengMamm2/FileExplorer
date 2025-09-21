import sys
import os
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"
from PyQt5 import QtCore

# ✅ High DPI scaling must be enabled before importing any Qt widgets
QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

from PyQt5 import QtGui
# keep the same font setting as before
try:
    # if app exists in this scope, set font (kept for parity with original)
    app.setFont(QtGui.QFont("Segoe UI", 10))
except Exception:
    pass
