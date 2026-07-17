import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox, QGridLayout,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QPalette, QTextCursor

from core.tunnel import TunnelManager
from core.executor import CommandExecutor


DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', Consolas, monospace;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px;
    font-weight: bold;
    color: #89b4fa;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QLineEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
}
QLineEdit:focus {
    border: 1px solid #89b4fa;
}
QPushButton {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 8px 20px;
    color: #cdd6f4;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #45475a;
    border: 1px solid #89b4fa;
    color: #89b4fa;
}
QPushButton:pressed {
    background-color: #89b4fa;
    color: #1e1e2e;
}
QPushButton:disabled {
    background-color: #1e1e2e;
    color: #585b70;
    border: 1px solid #313244;
}
QPushButton#tunnel_btn_active {
    background-color: #f38ba8;
    color: #1e1e2e;
    border: 1px solid #f38ba8;
}
QPushButton#tunnel_btn_active:hover {
    background-color: #eba0ac;
}
QTextEdit {
    background-color: #11111b;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 8px;
    color: #a6e3a1;
    font-family: Consolas, monospace;
    font-size: 12px;
}
QLabel#status_connected {
    color: #a6e3a1;
    font-weight: bold;
}
QLabel#status_disconnected {
    color: #f38ba8;
    font-weight: bold;
}
"""


class LogWorker(QObject):
    log_signal = pyqtSignal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("USB SSH Device Manager")
        self.setMinimumSize(760, 560)
        self.resize(800, 600)

        self.tunnel_manager = TunnelManager()
        self.executor = CommandExecutor()

        self._log_worker = LogWorker()
        self._log_worker.log_signal.connect(self._append_log)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setSpacing(10)
        root_layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel("⚡ USB SSH Device Manager")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #89b4fa; margin-bottom: 4px;")
        root_layout.addWidget(header)

        subtitle = QLabel("Automate SSH tunnel forwarding and run diagnostics on connected devices")
        subtitle.setStyleSheet("color: #6c7086; font-size: 11px; margin-bottom: 8px;")
        root_layout.addWidget(subtitle)

        # Connection Settings
        conn_group = QGroupBox("Connection Settings")
        conn_layout = QGridLayout(conn_group)
        conn_layout.setSpacing(10)

        conn_layout.addWidget(QLabel("IP Address:"), 0, 0)
        self.ip_input = QLineEdit("localhost")
        conn_layout.addWidget(self.ip_input, 0, 1)

        conn_layout.addWidget(QLabel("Port:"), 0, 2)
        self.port_input = QLineEdit("2222")
        self.port_input.setFixedWidth(80)
        conn_layout.addWidget(self.port_input, 0, 3)

        conn_layout.addWidget(QLabel("Username:"), 1, 0)
        self.user_input = QLineEdit("root")
        conn_layout.addWidget(self.user_input, 1, 1)

        conn_layout.addWidget(QLabel("Password:"), 1, 2)
        self.pass_input = QLineEdit("alpine")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        conn_layout.addWidget(self.pass_input, 1, 3)

        conn_layout.setColumnStretch(1, 1)
        conn_layout.setColumnStretch(3, 1)
        root_layout.addWidget(conn_group)

        # Control Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.tunnel_btn = QPushButton("🔌  Establish Tunnel (iproxy)")
        self.tunnel_btn.setObjectName("tunnel_btn")
        self.tunnel_btn.clicked.connect(self.toggle_tunnel)
        btn_layout.addWidget(self.tunnel_btn)

        self.diag_btn = QPushButton("🔍  Run Diagnostics")
        self.diag_btn.clicked.connect(self.run_diagnostics)
        btn_layout.addWidget(self.diag_btn)

        self.clear_btn = QPushButton("🗑  Clear Log")
        self.clear_btn.clicked.connect(self.clear_log)
        btn_layout.addWidget(self.clear_btn)

        btn_layout.addStretch()

        self.status_label = QLabel("● Disconnected")
        self.status_label.setObjectName("status_disconnected")
        btn_layout.addWidget(self.status_label)

        root_layout.addLayout(btn_layout)

        # Log Output
        log_group = QGroupBox("Log Output")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Activity log will appear here...")
        log_layout.addWidget(self.log_text)
        root_layout.addWidget(log_group, stretch=1)

        self._log("USB SSH Device Manager ready.\n")
        self._log("Connect a device via USB, then click 'Establish Tunnel' to begin.\n\n")

    def _log(self, message):
        """Thread-safe log via signal."""
        self._log_worker.log_signal.emit(message)

    def _append_log(self, message):
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)
        self.log_text.insertPlainText(message)
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)

    def clear_log(self):
        self.log_text.clear()

    def toggle_tunnel(self):
        if self.tunnel_manager.running:
            self.tunnel_manager.stop_tunnel(self._log)
            self.tunnel_btn.setText("🔌  Establish Tunnel (iproxy)")
            self.tunnel_btn.setObjectName("tunnel_btn")
            self.status_label.setText("● Disconnected")
            self.status_label.setObjectName("status_disconnected")
        else:
            self.tunnel_manager.start_tunnel(
                local_port=self.port_input.text(),
                remote_port=22,
                log_callback=self._log
            )
            self.tunnel_btn.setText("⏹  Stop Tunnel")
            self.tunnel_btn.setObjectName("tunnel_btn_active")
            self.status_label.setText("● Tunnel Active")
            self.status_label.setObjectName("status_connected")
        # Force style refresh
        self.tunnel_btn.style().unpolish(self.tunnel_btn)
        self.tunnel_btn.style().polish(self.tunnel_btn)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def run_diagnostics(self):
        self.diag_btn.setEnabled(False)
        self._log("\n--- Starting Diagnostics ---\n")

        def on_complete():
            self.diag_btn.setEnabled(True)
            self._log("--- Diagnostics Complete ---\n")

        self.executor.run_diagnostics(
            host=self.ip_input.text(),
            port=self.port_input.text(),
            username=self.user_input.text(),
            password=self.pass_input.text(),
            log_callback=self._log,
            completion_callback=on_complete
        )

    def closeEvent(self, event):
        self.tunnel_manager.stop_tunnel()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
