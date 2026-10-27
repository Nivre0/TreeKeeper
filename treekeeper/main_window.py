"""Main window: person list on the left, tree view on the right."""

import os
import sys

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMenu, QMessageBox, QPushButton, QSplitter, QToolBar, QVBoxLayout, QWidget,
)

from . import layout as lay
from .model import TreeKeeper, Partnership, Person
from .person_dialog import PersonDialog
from .tree_view import TreeView

APP_NAME = "TreeKeeper"
FILE_FILTER = "TreeKeeper files (*.json);;All files (*)"
MODE_DIRECT, MODE_ALL = 0, 1
LEGEND = ("<span style='color:#5a6470'>══</span> marriage &nbsp; "
          "<span style='color:#5a6470'>──</span> partnership &nbsp; "
          "<span style='color:#9aa3ad'>- - -</span> divorced / separated &nbsp; "
          "<span style='color:#9aa3ad'>·····</span> parents, no relationship recorded")


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    if getattr(sys, "frozen", False):
        base = os.path.join(base, "treekeeper")
    return os.path.join(base, "resources", name)


class MainWindow(QMainWindow):
    def __init__(self, path=None):
        super().__init__()
        self.settings = QSettings("TreeKeeper", "TreeKeeper")
        self.tree = TreeKeeper()
        self.focus_id = None
        self.resize(1300, 820)

        # --- left: search + list + buttons
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh_list)
        self.person_list = QListWidget()
        self.person_list.currentItemChanged.connect(self._list_selection_changed)
        self.person_list.itemDoubleClicked.connect(lambda item: self.edit_person(item.data(Qt.UserRole)))
        self.person_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.person_list.customContextMenuRequested.connect(self._list_context_menu)
        self.count_label = QLabel()
        add_btn = QPushButton("New person")
        add_btn.clicked.connect(self.new_person)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(lambda: self.edit_person(self.focus_id))
        del_btn = QPushButton("Delete")
        del_btn.clicked.connect(lambda: self.delete_person(self.focus_id))
        buttons = QHBoxLayout()
        for b in (add_btn, edit_btn, del_btn):
            buttons.addWidget(b)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(6, 6, 0, 6)
        left_layout.addWidget(self.search)
        left_layout.addWidget(self.person_list, 1)
        left_layout.addWidget(self.count_label)
        left_layout.addLayout(buttons)

        # --- right: tree controls + view
        self.view = TreeView()
        self.view.personClicked.connect(self.set_focus)
        self.view.personActivated.connect(self.edit_person)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Ancestors && descendants", "Whole family"])
        self.mode_combo.currentIndexChanged.connect(lambda: self.refresh_tree(recenter=True))
        self.focus_label = QLabel()
        self.engine_label = QLabel()
        self.engine_label.setStyleSheet("color: #777")
        controls = QHBoxLayout()
        controls.addWidget(QLabel("View:"))
        controls.addWidget(self.mode_combo)
        for text, tip, slot in (("−", "Zoom out", lambda: self.view.zoom(1 / 1.25)),
                                ("+", "Zoom in", lambda: self.view.zoom(1.25)),
                                ("Fit", "Show the whole tree", self.view.fit_all),
                                ("Center", "Center on the focus person", lambda: self.view.center_on(self.focus_id))):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setMaximumWidth(60)
            b.clicked.connect(slot)
            controls.addWidget(b)
        controls.addSpacing(12)
        controls.addWidget(self.focus_label, 1)
        controls.addWidget(self.engine_label)
        legend = QLabel(LEGEND)
        legend.setStyleSheet("color: #555")
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 6, 6, 6)
        right_layout.addLayout(controls)
        right_layout.addWidget(self.view, 1)
        right_layout.addWidget(legend)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([320, 980])
        self.setCentralWidget(splitter)

        self._build_actions()
        self.statusBar()
        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        last = path or self.settings.value("last_file", "")
        if last and os.path.isfile(last):
            self._load(last)
        else:
            self._set_tree(TreeKeeper())

    # --- actions & menus -------------------------------------------------------------

    def _action(self, text, slot, shortcut=None, tip=None):
        action = QAction(text, self)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if tip:
            action.setStatusTip(tip)
        return action

    def _build_actions(self):
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self._action("&New", self.file_new, QKeySequence.New))
        file_menu.addAction(self._action("&Open…", self.file_open, QKeySequence.Open))
        file_menu.addAction(self._action("Open &sample data", self.file_open_sample))
        file_menu.addSeparator()
        file_menu.addAction(self._action("&Save", self.file_save, QKeySequence.Save))
        file_menu.addAction(self._action("Save &as…", self.file_save_as, QKeySequence.SaveAs))
        file_menu.addSeparator()
        file_menu.addAction(self._action("E&xit", self.close, QKeySequence.Quit))

        self.act_new = self._action("New person", self.new_person, "Ctrl+Shift+N")
        self.act_edit = self._action("Edit person", lambda: self.edit_person(self.focus_id), "F2")
        self.act_child = self._action("Add child", lambda: self.add_child(self.focus_id), tip="Add a child of the focus person")
        self.act_parent = self._action("Add parent", lambda: self.add_parent(self.focus_id), tip="Add a parent of the focus person")
        self.act_partner = self._action("Add partner", lambda: self.add_partner(self.focus_id), tip="Add a partner of the focus person")
        self.act_delete = self._action("Delete person", lambda: self.delete_person(self.focus_id), QKeySequence.Delete)
        self.act_delete.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.person_list.addAction(self.act_delete)

        person_menu = self.menuBar().addMenu("&Person")
        for action in (self.act_new, self.act_edit, None, self.act_child, self.act_parent, self.act_partner,
                       None, self.act_delete):
            person_menu.addSeparator() if action is None else person_menu.addAction(action)

        toolbar = QToolBar("Quick actions")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        for action in (self.act_new, self.act_edit, None, self.act_child, self.act_parent, self.act_partner):
            toolbar.addSeparator() if action is None else toolbar.addAction(action)
        self.addToolBar(toolbar)

    def _update_actions(self):
        has_focus = self.focus_id is not None
        for action in (self.act_edit, self.act_child, self.act_parent, self.act_partner, self.act_delete):
            action.setEnabled(has_focus)

    def _list_context_menu(self, point):
        item = self.person_list.itemAt(point)
        if not item:
            return
        self.set_focus(item.data(Qt.UserRole))
        menu = QMenu(self)
        for action in (self.act_edit, None, self.act_child, self.act_parent, self.act_partner, None, self.act_delete):
            menu.addSeparator() if action is None else menu.addAction(action)
        menu.exec(self.person_list.mapToGlobal(point))

    # --- file handling -----------------------------------------------------------------

    def _set_tree(self, tree):
        self.tree = tree
        persons = tree.sorted_persons()
        self.focus_id = persons[0].id if persons else None
        self.search.clear()
        self.refresh_all(recenter=True)

    def _load(self, path):
        try:
            tree = TreeKeeper.load(path)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Open failed", f"Could not open {path}:\n{e}")
            return False
        self._set_tree(tree)
        self.settings.setValue("last_file", path)
        if tree.warnings:
            QMessageBox.information(self, "File repaired",
                                    "Some inconsistencies were fixed while loading:\n\n"
                                    + "\n".join(tree.warnings[:20])
                                    + ("\n…" if len(tree.warnings) > 20 else ""))
            tree.dirty = True
            self.update_title()
        return True

    def maybe_save(self):
        """Ask about unsaved changes. Returns False if the user cancelled."""
        if not self.tree.dirty:
            return True
        answer = QMessageBox.question(
            self, APP_NAME, "There are unsaved changes. Save them first?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if answer == QMessageBox.Save:
            return self.file_save()
        return answer == QMessageBox.Discard

    def file_new(self):
        if self.maybe_save():
            self._set_tree(TreeKeeper())

    def file_open(self):
        if not self.maybe_save():
            return
        start = os.path.dirname(self.tree.path or self.settings.value("last_file", "") or "")
        path, _ = QFileDialog.getOpenFileName(self, "Open TreeKeeper file", start, FILE_FILTER)
        if path:
            self._load(path)

    def file_open_sample(self):
        if not self.maybe_save():
            return
        try:
            tree = TreeKeeper.load(resource_path("sample_family.json"))
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Open failed", str(e))
            return
        tree.path = None  # never overwrite the bundled sample; Save asks for a location
        self._set_tree(tree)

    def file_save(self):
        if not self.tree.path:
            return self.file_save_as()
        return self._save(self.tree.path)

    def file_save_as(self):
        start = self.tree.path or os.path.join(os.path.expanduser("~"), "Documents", "family.json")
        path, _ = QFileDialog.getSaveFileName(self, "Save TreeKeeper file as", start, FILE_FILTER)
        if not path:
            return False
        if not path.lower().endswith(".json"):
            path += ".json"
        return self._save(path)

    def _save(self, path):
        try:
            self.tree.save(path)
        except OSError as e:
            QMessageBox.critical(self, "Save failed", f"Could not save {path}:\n{e}")
            return False
        self.settings.setValue("last_file", path)
        self.update_title()
        self.statusBar().showMessage(f"Saved {path}", 4000)
        return True

    def closeEvent(self, event):
        if self.maybe_save():
            self.settings.setValue("geometry", self.saveGeometry())
            event.accept()
        else:
            event.ignore()

    # --- refreshing ----------------------------------------------------------------------

    def update_title(self):
        name = os.path.basename(self.tree.path) if self.tree.path else "Untitled"
        self.setWindowTitle(f"{name}{' *' if self.tree.dirty else ''} – {APP_NAME}")

    def refresh_all(self, recenter=False):
        self.refresh_list()
        self.refresh_tree(recenter=recenter)
        self.update_title()
        self._update_actions()

    def refresh_list(self):
        query = self.search.text().strip()
        self.person_list.blockSignals(True)
        self.person_list.clear()
        shown = 0
        for person in self.tree.sorted_persons():
            if query and not person.matches(query):
                continue
            item = QListWidgetItem(person.list_label)
            item.setData(Qt.UserRole, person.id)
            self.person_list.addItem(item)
            shown += 1
            if person.id == self.focus_id:
                self.person_list.setCurrentItem(item)
        self.person_list.blockSignals(False)
        total = len(self.tree.persons)
        self.count_label.setText(f"{shown} of {total} persons" if query else f"{total} persons")

    def refresh_tree(self, recenter=False):
        if self.focus_id not in self.tree.persons:
            self.focus_id = None
        if self.focus_id is None:
            self.view.scene().clear()
            self.view.cards = {}
            self.focus_label.setText("No person selected – add or select a person." if self.tree.persons
                                     else "Empty file – use “New person” or File › Open sample data.")
            self.engine_label.clear()
            return
        if self.mode_combo.currentIndex() == MODE_DIRECT:
            result = lay.layout_direct(self.tree, self.focus_id)
        else:
            result = lay.layout_all(self.tree, self.focus_id)
        self.view.show_layout(self.tree, result, self.focus_id, recenter=recenter)
        self.focus_label.setText(f"Focus: <b>{self.tree.get(self.focus_id).full_name}</b>")
        self.engine_label.setText(f"{len(result.positions)} shown · layout: {result.engine}")

    def set_focus(self, pid):
        if pid == self.focus_id or pid not in self.tree.persons:
            return
        self.focus_id = pid
        self.refresh_list()
        self.refresh_tree(recenter=True)
        self._update_actions()

    def _list_selection_changed(self, current, _previous):
        if current is not None:
            self.set_focus(current.data(Qt.UserRole))

    # --- person editing ----------------------------------------------------------------

    def _run_dialog(self, person, title):
        dialog = PersonDialog(self.tree, person, title, self)
        return dialog.person if dialog.exec() else None

    def _commit(self, action, focus=None):
        try:
            action()
        except ValueError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return
        if focus:
            self.focus_id = focus
        self.refresh_all(recenter=True)

    def new_person(self):
        person = self._run_dialog(Person(), "New person")
        if person:
            self._commit(lambda: self.tree.add_person(person), focus=person.id)

    def edit_person(self, pid):
        original = self.tree.get(pid)
        if not original:
            return
        person = self._run_dialog(original, f"Edit {original.full_name}")
        if person:
            self._commit(lambda: self.tree.update_person(person), focus=pid)

    def add_child(self, pid):
        parent = self.tree.get(pid)
        if not parent:
            return
        child = Person(last_name=parent.last_name, parents=[pid])
        current = [p for p, ps in self.tree.partners_of(pid) if ps.status == "current"]
        partners = current or [p for p, _ in self.tree.partners_of(pid)]
        if len(partners) == 1:
            child.parents.append(partners[0].id)  # likely other parent; can be changed in the dialog
        person = self._run_dialog(child, f"Add child of {parent.full_name}")
        if person:
            self._commit(lambda: self.tree.add_person(person), focus=person.id)

    def add_parent(self, pid):
        child = self.tree.get(pid)
        if not child:
            return
        if len(child.parents) >= 2:
            QMessageBox.information(self, APP_NAME, f"{child.full_name} already has two parents.")
            return
        preset = Person()
        existing = self.tree.parents_of(pid)
        if existing and existing[0].gender in ("male", "female"):
            preset.gender = "female" if existing[0].gender == "male" else "male"
        if not existing or preset.gender == "male":
            preset.last_name = child.last_name
        person = self._run_dialog(preset, f"Add parent of {child.full_name}")
        if person:
            def action():
                self.tree.add_person(person)
                self.tree.add_parent(pid, person.id)
            self._commit(action, focus=pid)

    def add_partner(self, pid):
        partner = self.tree.get(pid)
        if not partner:
            return
        preset = Person(partnerships=[Partnership(pid, "marriage", "current")])
        if partner.gender in ("male", "female"):
            preset.gender = "female" if partner.gender == "male" else "male"
        person = self._run_dialog(preset, f"Add partner of {partner.full_name}")
        if person:
            self._commit(lambda: self.tree.add_person(person), focus=pid)

    def delete_person(self, pid):
        person = self.tree.get(pid)
        if not person:
            return
        children, partners = self.tree.reference_count(pid)
        details = []
        if children:
            details.append(f"{children} child(ren) will lose this parent")
        if partners:
            details.append(f"{partners} partnership(s) will be removed")
        text = f"Delete {person.full_name}?"
        if details:
            text += "\n\n" + "\n".join(details) + "."
        if QMessageBox.question(self, "Delete person", text) != QMessageBox.Yes:
            return
        neighbours = [p.id for p in self.tree.parents_of(pid)] + [p.id for p, _ in self.tree.partners_of(pid)] \
            + [c.id for c in self.tree.children_of(pid)]
        self.tree.delete_person(pid)
        remaining = self.tree.sorted_persons()
        self.focus_id = neighbours[0] if neighbours else (remaining[0].id if remaining else None)
        self.refresh_all(recenter=True)
