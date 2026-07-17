from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QHBoxLayout
from PyQt6.QtCore import QTimer, pyqtSignal

class MonitorTab(QWidget):
    request_ps_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_processes)
        self.polling = False

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        controls_layout = QHBoxLayout()
        self.btn_toggle = QPushButton("Start Monitoring")
        self.btn_toggle.clicked.connect(self._toggle_polling)
        controls_layout.addWidget(self.btn_toggle)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["PID", "USER", "%CPU", "COMMAND"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

    def _toggle_polling(self):
        self.polling = not self.polling
        if self.polling:
            self.btn_toggle.setText("Stop Monitoring")
            self._poll_processes()
            self.timer.start(5000)  # Poll every 5 seconds
        else:
            self.btn_toggle.setText("Start Monitoring")
            self.timer.stop()

    def _poll_processes(self):
        self.request_ps_signal.emit("ps aux | head -n 50")

    def update_table(self, ps_output):
        lines = ps_output.strip().split('\n')
        if len(lines) <= 1:
            return
            
        self.table.setRowCount(0)
        # Assuming typical `ps aux` format: USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND
        # We need to handle arbitrary spaces.
        for row, line in enumerate(lines[1:]):
            parts = line.split(None, 10)
            if len(parts) >= 11:
                user, pid, cpu, mem, vsz, rss, tty, stat, start, time, cmd = parts
                
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(pid))
                self.table.setItem(row, 1, QTableWidgetItem(user))
                self.table.setItem(row, 2, QTableWidgetItem(cpu))
                self.table.setItem(row, 3, QTableWidgetItem(cmd))
