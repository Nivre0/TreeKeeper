"""Graphical tree: person cards and connecting lines in a zoomable QGraphicsView."""

import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsScene, QGraphicsView

from . import layout as lay

GENDER_COLORS = {
    "male": QColor("#dce9f7"),
    "female": QColor("#f8e0e8"),
    "diverse": QColor("#e6f2dc"),
    "unknown": QColor("#ececec"),
}
LINE_COLOR = QColor("#5a6470")
FORMER_COLOR = QColor("#9aa3ad")
FOCUS_COLOR = QColor("#d08a1e")


class PersonCard(QGraphicsItem):
    def __init__(self, person, focused):
        super().__init__()
        self.person_id = person.id
        self.person = person
        self.focused = focused
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.hover = False
        tip = [f"<b>{person.full_name}</b>"]
        if person.birth_name:
            tip.append(f"née {person.birth_name}")
        if person.birth_date or person.birth_place:
            tip.append("* " + " in ".join(x for x in (person.birth_date, person.birth_place) if x))
        if person.deceased:
            tip.append("† " + " in ".join(x for x in (person.death_date, person.death_place) if x))
        tip.append("<i>Click: focus · Double-click: edit</i>")
        self.setToolTip("<br>".join(tip))

    def boundingRect(self):
        return QRectF(-lay.CARD_W / 2 - 3, -lay.CARD_H / 2 - 3, lay.CARD_W + 6, lay.CARD_H + 6)

    def hoverEnterEvent(self, event):
        self.hover = True
        self.update()

    def hoverLeaveEvent(self, event):
        self.hover = False
        self.update()

    def paint(self, painter, option, widget=None):
        rect = QRectF(-lay.CARD_W / 2, -lay.CARD_H / 2, lay.CARD_W, lay.CARD_H)
        fill = GENDER_COLORS.get(self.person.gender, GENDER_COLORS["unknown"])
        if self.hover:
            fill = fill.darker(106)
        if self.focused:
            pen = QPen(FOCUS_COLOR, 3)
        else:
            pen = QPen(QColor("#8c96a0"), 1)
        painter.setPen(pen)
        painter.setBrush(QBrush(fill))
        painter.drawRoundedRect(rect, 8, 8)

        p = self.person
        lines = []
        name_font = QFont(painter.font())
        name_font.setPointSizeF(9.5)
        name_font.setBold(True)
        small_font = QFont(painter.font())
        small_font.setPointSizeF(8.5)
        lines.append((p.short_name, name_font, QColor("#1d2329")))
        if p.birth_name and p.birth_name != p.last_name:
            lines.append((f"née {p.birth_name}", small_font, QColor("#4a525a")))
        span = p.lifespan
        if span:
            lines.append((span, small_font, QColor("#4a525a")))

        if p.deceased:
            cross_font = QFont(painter.font())
            cross_font.setPointSizeF(11)
            cross_font.setBold(True)
            painter.setFont(cross_font)
            painter.setPen(QColor("#4a525a"))
            painter.drawText(QRectF(lay.CARD_W / 2 - 20, -lay.CARD_H / 2 + 2, 16, 20), Qt.AlignCenter, "†")

        heights = [QFontMetrics(f).height() for _, f, _ in lines]
        y = -sum(heights) / 2
        inner = lay.CARD_W - (40 if p.deceased else 16)  # keep text clear of the † symbol
        for (text, font, color), h in zip(lines, heights):
            painter.setFont(font)
            painter.setPen(color)
            text = QFontMetrics(font).elidedText(text, Qt.ElideRight, inner)
            painter.drawText(QRectF(-inner / 2, y, inner, h), Qt.AlignCenter, text)
            y += h


class PlaceholderCard(QGraphicsItem):
    """Dashed card to add a missing father or mother, or a child, of the focus person."""

    def __init__(self, role):
        super().__init__()
        self.role = role
        self.hover = False
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to add a child of this person" if role == "child"
                        else f"Click to add the {role} of this person")

    def boundingRect(self):
        return QRectF(-lay.CARD_W / 2 - 2, -lay.CARD_H / 2 - 2, lay.CARD_W + 4, lay.CARD_H + 4)

    def hoverEnterEvent(self, event):
        self.hover = True
        self.update()

    def hoverLeaveEvent(self, event):
        self.hover = False
        self.update()

    def paint(self, painter, option, widget=None):
        rect = QRectF(-lay.CARD_W / 2, -lay.CARD_H / 2, lay.CARD_W, lay.CARD_H)
        color = {"father": GENDER_COLORS["male"], "mother": GENDER_COLORS["female"]}.get(
            self.role, GENDER_COLORS["unknown"])
        painter.setPen(QPen(QColor("#6f7a85") if self.hover else FORMER_COLOR, 1.5, Qt.DashLine))
        painter.setBrush(QBrush(color if self.hover else QColor(255, 255, 255, 0)))
        painter.drawRoundedRect(rect, 8, 8)
        font = QFont(painter.font())
        font.setPointSizeF(9.5)
        painter.setFont(font)
        painter.setPen(QColor("#5f6973"))
        painter.drawText(rect, Qt.AlignCenter, f"+ Add {self.role}")


class TreeView(QGraphicsView):
    personClicked = Signal(str)
    personActivated = Signal(str)
    addParentRequested = Signal(str)   # "father" or "mother" of the focus person
    addChildRequested = Signal()       # a child of the focus person

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#fbfbf9"))
        self.cards = {}
        self._press_pos = None
        self._pending_click = None
        self._last_click = (None, 0.0)   # (person id, time) of the last single click on a card
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._emit_click)

    # --- drawing ------------------------------------------------------------------

    def show_layout(self, tree, layout, focus_id, recenter=True):
        scene = self.scene()
        scene.clear()
        self.cards = {}
        pos = layout.positions
        self._draw_couples(tree, pos)
        self._draw_units(layout.units, pos)
        for pid, (x, y) in pos.items():
            card = PersonCard(tree.get(pid), pid == focus_id)
            card.setPos(x, y)
            card.setZValue(2)
            scene.addItem(card)
            self.cards[pid] = card
        self._draw_placeholders(layout.placeholders, pos.get(focus_id))
        rect = scene.itemsBoundingRect().adjusted(-400, -300, 400, 300)
        scene.setSceneRect(rect)
        if recenter and focus_id in self.cards:
            self.centerOn(self.cards[focus_id])

    def _draw_placeholders(self, placeholders, focus_pos):
        """'Add father/mother/child' cards with a dashed line to the focus person."""
        if not focus_pos:
            return
        fx, fy = focus_pos
        half_h = lay.CARD_H / 2
        pen = QPen(FORMER_COLOR, 1.3, Qt.DashLine)
        for role, (x, y) in placeholders.items():
            # From the bottom of the upper card to the top of the lower one.
            (ux, uy), (lx, ly) = ((fx, fy), (x, y)) if role == "child" else ((x, y), (fx, fy))
            mid = (uy + half_h + ly - half_h) / 2
            path = QPainterPath(QPointF(ux, uy + half_h))
            path.lineTo(ux, mid)
            path.lineTo(lx, mid)
            path.lineTo(lx, ly - half_h)
            self.scene().addPath(path, pen).setZValue(0)
            card = PlaceholderCard(role)
            card.setPos(x, y)
            card.setZValue(2)
            self.scene().addItem(card)

    def _draw_couples(self, tree, pos):
        half_w = lay.CARD_W / 2
        for a, b in lay.couples(tree, set(pos)):
            ps = tree.get(a).partnership_with(b)
            if ps is None:
                pen = QPen(FORMER_COLOR, 1.2, Qt.DotLine)       # parents without recorded partnership
            elif ps.is_former:
                pen = QPen(FORMER_COLOR, 2, Qt.DashLine)
            elif ps.type == "marriage":
                pen = QPen(LINE_COLOR, 2.2)
            else:
                pen = QPen(LINE_COLOR, 1.6)
            (ax, ay), (bx, by) = pos[a], pos[b]
            if abs(ay - by) < 1:
                left, right = sorted((ax, bx))
                start, end = QPointF(left + half_w, ay), QPointF(right - half_w, ay)
                if ps is not None and ps.type == "marriage" and not ps.is_former:
                    # double line for an ongoing (or widowed) marriage
                    for dy in (-2.5, 2.5):
                        line = self.scene().addLine(start.x(), start.y() + dy, end.x(), end.y() + dy,
                                                    QPen(LINE_COLOR, 1.3))
                        line.setZValue(1)
                    continue
            else:
                start, end = QPointF(ax, ay), QPointF(bx, by)
            line = self.scene().addLine(start.x(), start.y(), end.x(), end.y(), pen)
            line.setZValue(1)

    def _draw_units(self, units, pos):
        """Orthogonal lines parents -> bus -> children; overlapping buses get separate heights."""
        half_h = lay.CARD_H / 2
        items = []
        for unit in units:
            pxs = [pos[p][0] for p in unit.parents]
            pys = [pos[p][1] for p in unit.parents]
            if len(unit.parents) == 2 and abs(pys[0] - pys[1]) < 1:
                ox = unit.origin_x if unit.origin_x is not None else sum(pxs) / 2
                oy = pys[0]
                row_bottom = pys[0] + half_h
            elif len(unit.parents) == 2:
                ox, oy = sum(pxs) / 2, sum(pys) / 2
                row_bottom = max(pys) + half_h
            else:
                ox, oy = pxs[0], pys[0] + half_h
                row_bottom = oy
            child_top = min(pos[c][1] for c in unit.children) - half_h
            xs = [ox] + [pos[c][0] for c in unit.children]
            items.append({"unit": unit, "ox": ox, "oy": oy, "row": round(row_bottom),
                          "bottom": row_bottom, "top": child_top, "lo": min(xs), "hi": max(xs)})

        groups = {}
        for item in items:
            groups.setdefault(item["row"], []).append(item)
        for group in groups.values():
            group.sort(key=lambda it: it["lo"])
            level_ends = []
            for item in group:
                for level, end in enumerate(level_ends):
                    if end < item["lo"] - 8:
                        level_ends[level] = item["hi"]
                        item["level"] = level
                        break
                else:
                    item["level"] = len(level_ends)
                    level_ends.append(item["hi"])
            n = len(level_ends)
            gap = min(it["top"] for it in group) - group[0]["bottom"]
            spacing = min(10.0, max(2.0, (gap - 24) / max(n, 1)))
            for item in group:
                item["bus"] = item["bottom"] + gap / 2 + (item["level"] - (n - 1) / 2) * spacing

        pen = QPen(LINE_COLOR, 1.5)
        pen.setJoinStyle(Qt.RoundJoin)
        for item in items:
            path = QPainterPath(QPointF(item["ox"], item["oy"]))
            bus = item["bus"]
            path.lineTo(item["ox"], bus)
            for child in item["unit"].children:
                cx, cy = pos[child]
                path.moveTo(item["ox"], bus)
                path.lineTo(cx, bus)
                path.lineTo(cx, cy - half_h)
            line = self.scene().addPath(path, pen)
            line.setZValue(0)

    # --- navigation ---------------------------------------------------------------

    def zoom(self, factor):
        current = self.transform().m11()
        factor = max(0.08 / current, min(4.0 / current, factor))
        self.scale(factor, factor)

    def wheelEvent(self, event):
        self.zoom(1.15 ** (event.angleDelta().y() / 120))

    def fit_all(self):
        rect = self.scene().itemsBoundingRect().adjusted(-30, -30, 30, 30)
        if not rect.isEmpty():
            self.fitInView(rect, Qt.KeepAspectRatio)
            if self.transform().m11() > 1.2:
                self.resetTransform()
                self.centerOn(rect.center())

    def center_on(self, pid):
        if pid in self.cards:
            self.centerOn(self.cards[pid])

    def _card_at(self, view_pos):
        for item in self.items(view_pos):
            if isinstance(item, PersonCard):
                return item
        return None

    def mousePressEvent(self, event):
        self._press_pos = event.position()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() != Qt.LeftButton or self._press_pos is None:
            return
        moved = (event.position() - self._press_pos).manhattanLength()
        self._press_pos = None
        placeholder = next((i for i in self.items(event.position().toPoint()) if isinstance(i, PlaceholderCard)), None)
        if placeholder and moved < 5:
            # Open the dialog after this event has finished, not inside the mouse handler.
            if placeholder.role == "child":
                QTimer.singleShot(0, self.addChildRequested.emit)
            else:
                QTimer.singleShot(0, lambda role=placeholder.role: self.addParentRequested.emit(role))
            return
        card = self._card_at(event.position().toPoint())
        if card and moved < 5:
            # Delay so a double-click does not first re-layout the tree.
            self._pending_click = card.person_id
            self._last_click = (card.person_id, time.monotonic())
            self._click_timer.start(QApplication.doubleClickInterval())

    def mouseDoubleClickEvent(self, event):
        # Prefer the card hit by the first click: if the focus change already
        # re-laid out the tree, the cursor may now be over another card or none.
        pid, clicked_at = self._last_click
        if pid is None or time.monotonic() - clicked_at > 2 * QApplication.doubleClickInterval() / 1000:
            card = self._card_at(event.position().toPoint())
            pid = card.person_id if card else None
        self._last_click = (None, 0.0)
        if pid:
            self._click_timer.stop()
            self._pending_click = None
            self.personActivated.emit(pid)
        else:
            super().mouseDoubleClickEvent(event)

    def _emit_click(self):
        if self._pending_click:
            pid, self._pending_click = self._pending_click, None
            self.personClicked.emit(pid)
