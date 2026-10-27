"""Dialog for creating and editing one person."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QCompleter, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QToolButton,
    QVBoxLayout, QWidget,
)

from .date_edit import DateEdit
from .model import GENDERS, PARTNERSHIP_STATUSES, PARTNERSHIP_TYPES, Partnership

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


class PartnershipRow:
    """Widgets of one partnership: partner, type, status on one line, from/to dates below."""

    def __init__(self, tree, own_id, ps):
        self.picker = PersonPicker(tree, exclude_id=own_id)
        self.picker.set_person(ps.partner or None)
        self.type_combo = _combo(PARTNERSHIP_TYPES, ps.type)
        self.status_combo = _combo(PARTNERSHIP_STATUSES, ps.status)
        self.remove = QToolButton()
        self.remove.setText("✕")
        self.remove.setToolTip("Remove this partnership")
        self.start = DateEdit()
        self.start.set_text(ps.start)
        self.end = DateEdit()
        self.end.set_text(ps.end)
        self.dates = QWidget()
        line = QHBoxLayout(self.dates)
        line.setContentsMargins(16, 0, 0, 8)
        line.addWidget(QLabel("from"))
        line.addWidget(self.start)
        line.addSpacing(10)
        line.addWidget(QLabel("to"))
        line.addWidget(self.end)
        line.addStretch()

    def widgets(self):
        return (self.picker, self.type_combo, self.status_combo, self.remove, self.dates)


class PartnershipRows(QWidget):
    """Editable list of partnerships: partner, type, status, from, to."""

    def __init__(self, tree, own_id, parent=None):
        super().__init__(parent)
        self.tree = tree
        self.own_id = own_id
        self.rows = []
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        for col, title in enumerate(("Partner", "Type", "Status")):
            label = QLabel(f"<b>{title}</b>")
            self.grid.addWidget(label, 0, col)
        self.grid.setColumnStretch(0, 3)
        self.empty_label = QLabel("<i>No partners recorded.</i>")
        self.grid.addWidget(self.empty_label, 1, 0, 1, 4)

    def add_row(self, partnership=None):
        row = PartnershipRow(self.tree, self.own_id, partnership or Partnership("", "marriage", "current"))
        row.remove.clicked.connect(lambda: self._remove_row(row))
        grid_row = self.grid.rowCount()
        for col, widget in enumerate((row.picker, row.type_combo, row.status_combo, row.remove)):
            self.grid.addWidget(widget, grid_row, col)
        self.grid.addWidget(row.dates, grid_row + 1, 0, 1, 4)
        self.rows.append(row)
        self.empty_label.hide()
        if partnership is None:
            row.picker.setFocus()

    def _remove_row(self, row):
        self.rows.remove(row)
        for widget in row.widgets():
            self.grid.removeWidget(widget)
            widget.deleteLater()
        self.empty_label.setVisible(not self.rows)

    def partnerships(self):
        """List of Partnership; raises ValueError on invalid input."""
        result = []
        for row in self.rows:
            partner = row.picker.person_id()
            if partner is None:
                continue
            name = self.tree.get(partner).full_name
            if any(p.partner == partner for p in result):
                raise ValueError(f"{name} is listed twice as partner.")
            for label, edit in (("start", row.start), ("end", row.end)):
                if edit.error():
                    raise ValueError(f"Partnership with {name}, {label} date: {edit.error()}")
            result.append(Partnership(partner, row.type_combo.currentData(), row.status_combo.currentData(),
                                      row.start.text(), row.end.text()))
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
        self.birth_date = DateEdit()
        self.birth_date.set_text(p.birth_date)
        self.birth_place = line(p.birth_place, "place")
        self.deceased = QCheckBox("Deceased")
        self.deceased.setToolTip("Tick if the person has died; the date may stay empty if unknown.")
        self.death_date = DateEdit()
        self.death_date.set_text("" if p.death_date.strip() == "?" else p.death_date)
        self.death_place = line(p.death_place, "place")
        self.deceased.toggled.connect(self.death_date.setEnabled)
        self.deceased.toggled.connect(self.death_place.setEnabled)
        self.deceased.setChecked(p.deceased)
        self.death_date.setEnabled(p.deceased)
        self.death_place.setEnabled(p.deceased)

        name_box = QGroupBox("Name")
        name_form = QFormLayout(name_box)
        name_form.addRow("First name:", self.first_name)
        name_form.addRow("Middle name:", self.middle_name)
        name_form.addRow("Last name:", self.last_name)
        name_form.addRow("Birth name:", self.birth_name)
        name_form.addRow("Gender:", self.gender)

        life_box = QGroupBox("Life")
        life_form = QFormLayout(life_box)
        life_form.addRow("Born:", self.birth_date)
        life_form.addRow("Birthplace:", self.birth_place)
        life_form.addRow("", self.deceased)
        life_form.addRow("Died:", self.death_date)
        life_form.addRow("Place of death:", self.death_place)

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

    def accept(self):
        p = self.person
        dated = [("Date of birth", self.birth_date)]
        if self.deceased.isChecked():
            dated.append(("Date of death", self.death_date))
        for label, edit in dated:
            if edit.error():
                QMessageBox.warning(self, "Invalid date", f"{label}: {edit.error()}")
                return
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
        p.birth_date = self.birth_date.text()
        p.birth_place = self.birth_place.text().strip()
        if self.deceased.isChecked():
            # "?" marks a death with unknown date, so the person still counts as deceased.
            p.death_date = self.death_date.text() or "?"
            p.death_place = self.death_place.text().strip()
        else:
            p.death_date = p.death_place = ""
        p.parents = parents
        p.partnerships = partnerships
        p.notes = self.notes.toPlainText().rstrip()
        super().accept()
