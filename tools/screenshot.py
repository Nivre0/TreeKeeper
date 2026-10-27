"""Render the main window with the sample data to PNG files (for checking layouts).

Run: python tools/screenshot.py OUT_DIR [focus first name]
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import QApplication  # noqa: E402

from treekeeper.main_window import MainWindow, resource_path  # noqa: E402
from treekeeper.model import TreeKeeper  # noqa: E402


def main():
    out_dir = sys.argv[1]
    focus = sys.argv[2] if len(sys.argv) > 2 else "Thomas"
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.resize(1500, 900)
    tree = TreeKeeper.load(resource_path("sample_family.json"))
    window._set_tree(tree)
    window.show()
    window.set_focus(next(p.id for p in tree.persons.values() if p.first_name == focus))
    for mode, name in ((0, "mode1"), (1, "mode2")):
        window.mode_combo.setCurrentIndex(mode)
        app.processEvents()
        window.view.fit_all()
        app.processEvents()
        path = os.path.join(out_dir, f"{name}_{focus}.png")
        window.grab().save(path)
        print(path, window.engine_label.text())
    window.tree.dirty = False
    window.close()


if __name__ == "__main__":
    main()
