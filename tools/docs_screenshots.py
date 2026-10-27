"""Take the screenshots used in README.md and docs/ (sample data, light theme).

Run: python tools/docs_screenshots.py [OUT_DIR]   (default: docs/images)

Uses the real window system so fonts look like in the app; windows appear briefly.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from treekeeper.ai_dialog import AiAccessDialog  # noqa: E402
from treekeeper.main_window import MODE_DIRECT, MainWindow, resource_path  # noqa: E402
from treekeeper.model import TreeKeeper  # noqa: E402
from treekeeper.person_dialog import PersonDialog  # noqa: E402


def settle(app):
    for _ in range(5):
        app.processEvents()


def main():
    root = os.path.join(os.path.dirname(__file__), "..")
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "docs", "images")
    os.makedirs(out_dir, exist_ok=True)
    app = QApplication(sys.argv)
    app.setOrganizationName("TreeKeeper-tests")  # keep the user's settings untouched
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyle("Fusion")

    window = MainWindow()
    window.settings.remove("mcp_port")  # show the default port, not one left by the tests
    window.resize(1280, 760)
    tree = TreeKeeper.load(resource_path("sample_family.json"))
    tree.path = None  # never write to the bundled sample
    window._set_tree(tree)
    window.act_parent_boxes.setChecked(True)
    window.act_child_boxes.setChecked(True)
    window.show()

    def person(first):
        return next(p for p in tree.persons.values() if p.first_name == first)

    def save(widget, name):
        settle(app)
        path = os.path.join(out_dir, name)
        widget.grab().save(path)
        print(path)

    window.act_child_boxes.setChecked(False)  # keep the crowded overview free of dashed lines
    window.set_focus(person("Walter").id)
    window.mode_combo.setCurrentIndex(1)
    settle(app)
    window.view.fit_all()
    save(window, "whole-family.png")

    window.act_child_boxes.setChecked(True)
    window.set_focus(person("Lukas").id)
    window.mode_combo.setCurrentIndex(MODE_DIRECT)
    settle(app)
    window.view.fit_all()
    save(window, "ancestors.png")

    dialog = PersonDialog(tree, person("Walter"), "Edit Walter Keller", window)
    dialog.show()
    save(dialog, "person-dialog.png")
    dialog.close()

    dialog = AiAccessDialog(window)
    dialog.show()
    save(dialog, "ai-access.png")
    dialog.close()

    window.tree.dirty = False
    window.close()


if __name__ == "__main__":
    main()
