"""Family Tree – a very simple genealogy app. Start: python main.py [file.json]"""

import sys

from PySide6.QtWidgets import QApplication

from familytree.main_window import APP_NAME, MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    window = MainWindow(sys.argv[1] if len(sys.argv) > 1 else None)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
