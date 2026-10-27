"""Dialog for creating and editing one person."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QToolButton,
    QVBoxLayout, QWidget,
)

from .model import GENDERS, PARTNERSHIP_STATUSES, PARTNERSHIP_TYPES, Partnership

DATE_HINT = "e.g. 1923, 12.03.1923, ca. 1880, before 1900"
NONE_LABEL = "— none —"


class PersonPicker(QComboBox):
    """Editable combo box listing all persons; type to search by name."""

    def __init__(self, tree, exclude_id=None, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setMinimumWidth(260)
        self.addItem(NONE_LABEL, None)
        labels = {}
        for person in tree.sorted_persons():
            if person.id == exclude_id:
                continue
            label = person.list_label
            if label in labels:  # keep labels unique so typed text maps to one person
                label += f"  [{person.id[:6]}]"
            labels[label] = person.id
            self.addItem(label, person.id)
        completer = QCompleter(self.model(), self)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)
        self.lineEdit().setPlaceholderText("Type a name…")

    def set_person(self, pid):
        index = self.findData(pid)
        self.setCurrentIndex(index if index >= 0 else 0)

    def person_id(self):
        """Selected person id, None for 'none'; raises ValueError for unmatched text."""
        text = self.currentText().strip()
        if not text or text == NONE_LABEL:
            return None
        index = self.findText(text)
        if index < 0:
            raise ValueError(f"No person named “{text}”.")
        return self.itemData(index)


def _combo(values, current):
    combo = QComboBox()
    for value in values:
        combo.addItem(value.capitalize(), value)
    combo.setCurrentIndex(max(0, combo.findData(current)))
    return combo


class PartnershipRows(QWidget):
    """Editable list of partnerships: partner, type, status, from, to."""

    def __init__(self, tree, own_id, parent=None):
        super().__init__(parent)
        self.tree = tree
        self.own_id = own_id
        self.rows = []
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        for col, title in enumerate(("Partner", "Type", "Status", "From", "To")):
            label = QLabel(f"<b>{title}</b>")
            self.grid.addWidget(label, 0, col)
        self.grid.setColumnStretch(0, 3)
        self.empty_label = QLabel("<i>No partners recorded.</i>")
        self.grid.addWidget(self.empty_label, 1, 0, 1, 6)

    def add_row(self, partnership=None):
        ps = partnership or Partnership("", "marriage", "current")
        picker = PersonPicker(self.tree, exclude_id=self.own_id)
        picker.set_person(ps.partner or None)
        type_combo = _combo(PARTNERSHIP_TYPES, ps.type)
        status_combo = _combo(PARTNERSHIP_STATUSES, ps.status)
        start = QLineEdit(ps.start)
        end = QLineEdit(ps.end)
        for edit in (start, end):
            edit.setPlaceholderText("date")
            edit.setToolTip(DATE_HINT)
            edit.setMaximumWidth(110)
        remove = QToolButton()
        remove.setText("✕")
        remove.setToolTip("Remove this partnership")
        row = (picker, type_combo, status_combo, start, end, remove)
        remove.clicked.connect(lambda: self._remove_row(row))
        grid_row = self.grid.rowCount()
        for col, widget in enumerate(row):
            self.grid.addWidget(widget, grid_row, col)
        self.rows.append(row)
        self.empty_label.hide()
        if partnership is None:
            picker.setFocus()

    def _remove_row(self, row):
        self.rows.remove(row)
        for widget in row:
            self.grid.removeWidget(widget)
            widget.deleteLater()
        self.empty_label.setVisible(not self.rows)

    def partnerships(self):
        """List of Partnership; raises ValueError on invalid input."""
        result = []
        for picker, type_combo, status_combo, start, end, _ in self.rows:
            partner = picker.person_id()
            if partner is None:
                continue
            if any(p.partner == partner for p in result):
                raise ValueError(f"{self.tree.get(partner).full_name} is listed twice as partner.")
            result.append(Partnership(partner, type_combo.currentData(), status_combo.currentData(),
                                      start.text().strip(), end.text().strip()))
        return result


class PersonDialog(QDialog):
    """Edit a copy of a person. After exec() == Accepted, read .person."""

    def __init__(self, tree, person, title, parent=None):
        super().__init__(parent)
        self.tree = tree
        self.person = person.copy()
        self.setWindowTitle(title)
        self.setMinimumWidth(720)

        def line(text, placeholder=""):
            edit = QLineEdit(text)
            edit.setPlaceholderText(placeholder)
            return edit

        p = self.person
        self.first_name = line(p.first_name)
        self.middle_name = line(p.middle_name)
        self.last_name = line(p.last_name)
        self.birth_name = line(p.birth_name, "maiden / birth surname, if different")
        self.gender = QComboBox()
        for g in GENDERS:
            self.gender.addItem(g.capitalize(), g)
        self.gender.setCurrentIndex(self.gender.findData(p.gender))
        self.birth_date = line(p.birth_date, DATE_HINT)
        self.birth_place = line(p.birth_place, "place")
        self.death_date = line(p.death_date, DATE_HINT + " or ? if unknown")
        self.death_place = line(p.death_place, "place")
        self.death_date.setToolTip("Leave empty if the person is alive. Enter ? if the date of death is unknown.")

        name_box = QGroupBox("Name")
        name_form = QFormLayout(name_box)
        name_form.addRow("First name:", self.first_name)
        name_form.addRow("Middle name:", self.middle_name)
        name_form.addRow("Last name:", self.last_name)
        name_form.addRow("Birth name:", self.birth_name)
        name_form.addRow("Gender:", self.gender)

        life_box = QGroupBox("Life")
        life_form = QFormLayout(life_box)
        life_form.addRow("Born:", self._pair(self.birth_date, self.birth_place))
        life_form.addRow("Died:", self._pair(self.death_date, self.death_place))

        parents_box = QGroupBox("Parents")
        parents_form = QFormLayout(parents_box)
        self.parent_pickers = []
        for i in range(2):
            picker = PersonPicker(tree, exclude_id=p.id)
            picker.set_person(p.parents[i] if i < len(p.parents) else None)
            self.parent_pickers.append(picker)
            parents_form.addRow(f"Parent {i + 1}:", picker)

        partners_box = QGroupBox("Partners")
        partners_layout = QVBoxLayout(partners_box)
        self.partner_rows = PartnershipRows(tree, p.id)
        for ps in p.partnerships:
            self.partner_rows.add_row(ps)
        add_partner = QPushButton("Add partnership")
        add_partner.clicked.connect(lambda: self.partner_rows.add_row())
        partners_layout.addWidget(self.partner_rows)
        partners_layout.addWidget(add_partner, alignment=Qt.AlignLeft)

        notes_box = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_box)
        self.notes = QPlainTextEdit(p.notes)
        self.notes.setMinimumHeight(70)
        notes_layout.addWidget(self.notes)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        top = QHBoxLayout()
        top.addWidget(name_box, 1)
        right = QVBoxLayout()
        right.addWidget(life_box)
        right.addWidget(parents_box)
        right.addStretch()
        top.addLayout(right, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(partners_box)
        layout.addWidget(notes_box, 1)
        layout.addWidget(buttons)
        self.first_name.setFocus()

    @staticmethod
    def _pair(date_edit, place_edit):
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        date_edit.setMinimumWidth(170)
        row.addWidget(date_edit, 1)
        row.addWidget(QLabel("in"))
        row.addWidget(place_edit, 1)
        return widget

    def accept(self):
        p = self.person
        try:
            parents = [pid for pid in (pk.person_id() for pk in self.parent_pickers) if pid]
            partnerships = self.partner_rows.partnerships()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid input", str(e))
            return
        error = self.tree.check_parents(p.id, parents)
        if error:
            QMessageBox.warning(self, "Invalid parents", error)
            return
        clash = set(parents) & {ps.partner for ps in partnerships}
        if clash:
            QMessageBox.warning(self, "Invalid input", "A parent cannot also be a partner of the same person.")
            return
        p.first_name = self.first_name.text().strip()
        p.middle_name = self.middle_name.text().strip()
        p.last_name = self.last_name.text().strip()
        p.birth_name = self.birth_name.text().strip()
        if not (p.first_name or p.last_name):
            QMessageBox.warning(self, "Missing name", "Please enter at least a first or last name.")
            return
        p.gender = self.gender.currentData()
        p.birth_date = self.birth_date.text().strip()
        p.birth_place = self.birth_place.text().strip()
        p.death_date = self.death_date.text().strip()
        p.death_place = self.death_place.text().strip()
        p.parents = parents
        p.partnerships = partnerships
        p.notes = self.notes.toPlainText().rstrip()
        super().accept()
