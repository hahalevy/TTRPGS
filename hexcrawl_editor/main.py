import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from hexcrawl.app_config import APP_NAME, APP_ORG
from hexcrawl.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName(APP_ORG)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    QTimer.singleShot(0, window.new_project)  # pick the base map; cancel = blank canvas
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
