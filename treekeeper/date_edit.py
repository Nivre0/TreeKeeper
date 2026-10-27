"""Date picker for possibly incomplete dates: qualifier, day, month, year + calendar popup."""

import calendar

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCalendarWidget, QComboBox, QHBoxLayout, QMenu, QSpinBox, QToolButton, QWidget, QWidgetAction,
)

from . import dates

QUALIFIERS = (("", "exact"), ("c.", "about"), ("bef.", "before"), ("aft.", "after"))
EMPTY = "–"


class YearSpin(QSpinBox):
    """Year selector; empty ('–') until a year is chosen. Arrows start at a sensible year."""

    START_YEAR = 1900

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 2200)
        self.setSpecialValueText(EMPTY)
        self.setAccelerated(True)
        self.setFixedWidth(72)
        self.setToolTip("Year – use the arrows or mouse wheel, or type it")

    def stepBy(self, steps):
        if self.value() == 0:
            self.setValue(self.START_YEAR)
        else:
            super().stepBy(steps)


class DateEdit(QWidget):
    """Edits one date. text() returns the stored form, e.g. 'ca. 03.1880'."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original = None   # unrecognised legacy text, returned unchanged until edited
        self._loading = False

        self.qualifier = QComboBox()
        for value, label in QUALIFIERS:
            self.qualifier.addItem(label, value)
        self.qualifier.setToolTip("Is the date exact or an estimate?")
        self.day = QComboBox()
        self.day.addItem(EMPTY, None)
        for d in range(1, 32):
            self.day.addItem(str(d), d)
        self.day.setMaxVisibleItems(16)
        self.day.setToolTip("Day (optional)")
        self.month = QComboBox()
        self.month.addItem(EMPTY, None)
        for m in range(1, 13):
            self.month.addItem(calendar.month_abbr[m], m)
        self.month.setMaxVisibleItems(13)
        self.month.setToolTip("Month (optional)")
        self.year = YearSpin()

        self.calendar = QCalendarWidget()
        self.calendar.setMinimumDate(QDate(100, 1, 1))
        self.calendar.setGridVisible(True)
        self.calendar.clicked.connect(self._pick_from_calendar)
        menu = QMenu(self)
        action = QWidgetAction(menu)
        action.setDefaultWidget(self.calendar)
        menu.addAction(action)
        menu.aboutToShow.connect(self._prepare_calendar)
        self.calendar_menu = menu
        pick = QToolButton()
        pick.setText("📅")
        pick.setToolTip("Pick an exact date from a calendar")
        pick.setPopupMode(QToolButton.InstantPopup)
        pick.setMenu(menu)
        clear = QToolButton()
        clear.setText("✕")
        clear.setToolTip("Clear the date")
        clear.clicked.connect(lambda: self.set_text(""))
        clear.clicked.connect(self._mark_changed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        for widget in (self.qualifier, self.day, self.month, self.year, pick, clear):
            layout.addWidget(widget)

        self.qualifier.currentIndexChanged.connect(self._mark_changed)
        self.day.currentIndexChanged.connect(self._mark_changed)
        self.month.currentIndexChanged.connect(self._mark_changed)
        self.year.valueChanged.connect(self._mark_changed)

    # --- value ----------------------------------------------------------------------

    def set_text(self, text):
        self._loading = True
        parsed = dates.parse_date(text)
        if parsed is None:
            # Unknown legacy text: show what we can, keep the original unless edited.
            self._original = text
            year, qualifier = dates.parse_year(text)
            parsed = (qualifier, None, None, year)
            self.setToolTip(f"Original text: “{text}”. It is kept unless you change the date.")
        else:
            self._original = None
            self.setToolTip("")
        qualifier, day, month, year = parsed
        self.qualifier.setCurrentIndex(max(0, self.qualifier.findData(qualifier)))
        self.day.setCurrentIndex(day or 0)
        self.month.setCurrentIndex(month or 0)
        self.year.setValue(year or 0)
        self._loading = False

    def parts(self):
        return (self.qualifier.currentData(), self.day.currentData(), self.month.currentData(),
                self.year.value() or None)

    def text(self):
        if self._original is not None:
            return self._original
        return dates.format_date(*self.parts())

    def error(self):
        """Message if the selected parts do not form a valid date, else None."""
        if self._original is not None:
            return None
        _, day, month, year = self.parts()
        return dates.date_error(day, month, year)

    # --- internals ------------------------------------------------------------------

    def _mark_changed(self):
        if self._loading:
            return
        if self._original is not None:
            self._original = None
            self.setToolTip("")
        self.changed.emit()

    def _prepare_calendar(self):
        _, day, month, year = self.parts()
        start = QDate(year or YearSpin.START_YEAR, month or 1, 1)
        if day and QDate.isValid(start.year(), start.month(), day):
            start = QDate(start.year(), start.month(), day)
        self.calendar.setSelectedDate(start)
        self.calendar.setCurrentPage(start.year(), start.month())

    def _pick_from_calendar(self, date):
        self.day.setCurrentIndex(date.day())
        self.month.setCurrentIndex(date.month())
        self.year.setValue(date.year())
        self.qualifier.setCurrentIndex(0)
        self.calendar_menu.close()
