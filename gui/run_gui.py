from __future__ import annotations

import os
import sys

# Prefer PySide6 for Matplotlib QtAgg backend; avoid old PyQt5
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("MPLBACKEND", "QtAgg")

try:
    from PySide6 import QtWidgets  # type: ignore
    from PySide6.QtWidgets import QApplication  # type: ignore
except Exception:  # pragma: no cover
    from PyQt5 import QtWidgets  # type: ignore
    from PyQt5.QtWidgets import QApplication  # type: ignore

# Support running as a script (python gui/run_gui.py) or module (python -m gui.run_gui)
if __package__ in (None, ""):
    # Ensure repo root on sys.path, then import absolute package
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from gui.window import MainWindow  # type: ignore
else:
    from .window import MainWindow


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
