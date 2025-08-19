from __future__ import annotations

import sys

try:
    from PySide6 import QtWidgets
    from PySide6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    from PyQt5 import QtWidgets  # type: ignore
    from PyQt5.QtWidgets import QApplication  # type: ignore

from .window import MainWindow


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

