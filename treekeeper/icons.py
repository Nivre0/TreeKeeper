"""Small line-art icons drawn with QPainter (no image files, sharp at any screen scale)."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPalette, QPen, QPixmap

ACTIVE_COLOR = QColor("#2e9d4f")


def robot_icon(active=False, size=24, color=None):
    """Robot head outline; a green status dot in the corner when active.

    color defaults to the application's text colour, so the icon is white in
    dark mode and dark in light mode instead of looking disabled.
    """
    color = QColor(color) if color is not None else QGuiApplication.palette().color(QPalette.WindowText)
    icon = QIcon()
    for scale in (1, 2):
        pixmap = QPixmap(size * scale, size * scale)
        pixmap.setDevicePixelRatio(scale)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(size / 24, size / 24)  # draw on a 24×24 grid
        pen = QPen(color, 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(12, 4.6), QPointF(12, 7))                # antenna
        p.drawRoundedRect(QRectF(5, 7, 14, 11.5), 3, 3)             # head
        p.drawLine(QPointF(3, 11), QPointF(3, 14.5))                # ears
        p.drawLine(QPointF(21, 11), QPointF(21, 14.5))
        p.drawLine(QPointF(10, 15.3), QPointF(14, 15.3))            # mouth
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawEllipse(QPointF(12, 3.4), 1.5, 1.5)                   # antenna tip
        p.drawEllipse(QPointF(9.4, 11.6), 1.45, 1.45)               # eyes
        p.drawEllipse(QPointF(14.6, 11.6), 1.45, 1.45)
        if active:
            p.setBrush(QGuiApplication.palette().color(QPalette.Window))  # gap between dot and head
            p.drawEllipse(QPointF(19.6, 4.4), 4, 4)
            p.setBrush(ACTIVE_COLOR)
            p.drawEllipse(QPointF(19.6, 4.4), 2.9, 2.9)
        p.end()
        icon.addPixmap(pixmap)
    return icon
