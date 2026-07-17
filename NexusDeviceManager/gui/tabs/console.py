from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton
from PyQt6.QtCore import pyqtSignal

class ConsoleTab(QWidget):
    execute_command_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Quick Actions
        quick_layout = QHBoxLayout()
        self.btn_df = QPushButton("Check Disk Capacity")
        self.btn_uname = QPushButton("System Info")
        self.btn_df.clicked.connect(lambda: self.execute_command_signal.emit("df -h"))
        self.btn_uname.clicked.connect(lambda: self.execute_command_signal.emit("uname -a"))
        quick_layout.addWidget(self.btn_df)
        quick_layout.addWidget(self.btn_uname)
        quick_layout.addStretch()
        layout.addLayout(quick_layout)

        # Output console
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas, monospace;")
        layout.addWidget(self.console_output)

        # Command Input
        input_layout = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter command to execute...")
        self.command_input.returnPressed.connect(self._send_command)
        self.btn_send = QPushButton("Send")
        self.btn_send.clicked.connect(self._send_command)
        input_layout.addWidget(self.command_input)
        input_layout.addWidget(self.btn_send)
        layout.addLayout(input_layout)

    def _send_command(self):
        cmd = self.command_input.text().strip()
        if cmd:
            self.execute_command_signal.emit(cmd)
            self.command_input.clear()

    def append_output(self, text):
        self.console_output.append(text)

    def append_error(self, text):
        self.console_output.append(f"<font color='red'>{text}</font>")
