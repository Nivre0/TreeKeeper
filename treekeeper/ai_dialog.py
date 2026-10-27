"""Window for starting/stopping the MCP server and copying the client configuration."""

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
)

from .mcp_server import SERVER_NAME

INTRO = ("Let AI assistants such as Claude read and change the family tree that is open here: "
         "list, create, edit and delete persons, parents and partnerships. Changes appear in the "
         "tree immediately and are saved like your own edits. The server only accepts connections "
         "from this computer.")


def desktop_config(url):
    return json.dumps({"mcpServers": {SERVER_NAME: {"command": "npx", "args": ["-y", "mcp-remote", url]}}},
                      indent=2)


def code_command(url):
    return f"claude mcp add --transport http {SERVER_NAME} {url}"


class AiAccessDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.server = window.mcp_server
        self.setWindowTitle("AI access (MCP server)")
        self.setMinimumWidth(560)

        intro = QLabel(INTRO)
        intro.setWordWrap(True)

        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(window.mcp_port())
        self.port.valueChanged.connect(self._update)
        self.toggle = QPushButton()
        self.toggle.clicked.connect(self._toggle)
        self.status = QLabel()
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.autostart = QCheckBox("Start the server automatically when TreeKeeper opens")
        self.autostart.setChecked(window.settings.value("mcp_autostart", False, type=bool))
        self.autostart.toggled.connect(lambda on: window.settings.setValue("mcp_autostart", on))
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Port:"))
        port_row.addWidget(self.port)
        port_row.addWidget(self.toggle)
        port_row.addSpacing(10)
        port_row.addWidget(self.status, 1)

        mono = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self.tabs = QTabWidget()
        self.desktop_text = self._config_tab(
            "Claude Desktop app", mono,
            "In Claude Desktop open <b>Settings › Developer › Edit Config</b> and paste this into "
            "<i>claude_desktop_config.json</i> (if the file already has \"mcpServers\", add only the "
            "\"treekeeper\" entry). Restart Claude Desktop. Requires Node.js.")
        self.code_text = self._config_tab(
            "Claude Code", mono,
            "Run this command once in a terminal:")

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addSpacing(6)
        layout.addLayout(port_row)
        layout.addWidget(self.autostart)
        layout.addSpacing(6)
        layout.addWidget(QLabel("<b>Connect Claude</b> – copy the configuration:"))
        layout.addWidget(self.tabs, 1)
        layout.addWidget(buttons)
        self._update()

    def _config_tab(self, title, font, help_text):
        page = QWidget()
        help_label = QLabel(help_text)
        help_label.setWordWrap(True)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setFont(font)
        text.setMinimumHeight(140 if "Desktop" in title else 50)
        copy = QPushButton("Copy")
        copy.clicked.connect(lambda: self._copy(text, copy))
        layout = QVBoxLayout(page)
        layout.addWidget(help_label)
        layout.addWidget(text, 1)
        layout.addWidget(copy, alignment=Qt.AlignRight)
        self.tabs.addTab(page, title)
        return text

    def _copy(self, text, button):
        QGuiApplication.clipboard().setText(text.toPlainText())
        button.setText("Copied ✓")

    def _toggle(self):
        if self.server.running:
            self.window.stop_mcp_server()
        else:
            self.window.start_mcp_server(self.port.value())
        self._update()

    def _update(self):
        running = self.server.running
        port = self.server.port if running else self.port.value()
        url = f"http://127.0.0.1:{port}/mcp"
        self.port.setEnabled(not running)
        self.toggle.setText("Stop server" if running else "Start server")
        error = self.window.mcp_error
        if running:
            self.status.setText(f"<span style='color:#2e7d32'>● Running</span> at {url}")
        elif error:
            self.status.setText(f"<span style='color:#c62828'>● Could not start:</span> {error}")
        else:
            self.status.setText("<span style='color:#888'>● Stopped</span>")
        self.desktop_text.setPlainText(desktop_config(url))
        self.code_text.setPlainText(code_command(url))
        for i in range(self.tabs.count()):
            self.tabs.widget(i).findChild(QPushButton).setText("Copy")
