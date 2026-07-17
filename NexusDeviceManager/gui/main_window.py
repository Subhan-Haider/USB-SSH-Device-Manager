from PyQt6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt
from gui.tabs.console import ConsoleTab
from gui.tabs.explorer import ExplorerTab
from gui.tabs.monitor import MonitorTab
from core.tunnel_manager import TunnelManager
from core.ssh_client import SSHWorker
from core.sftp_client import SFTPWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NexusDeviceManager")
        self.resize(800, 600)
        
        # Connection Config
        self.host = "localhost"
        self.port = 2222
        self.username = "root"
        self.password = "alpine"
        self.workers = []
        
        self.init_ui()
        self.init_tunnel()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Connection Badge
        self.status_label = QLabel("Offline")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("background-color: #aa0000; color: white; font-weight: bold; padding: 5px;")
        layout.addWidget(self.status_label)
        
        # Tabs
        self.tabs = QTabWidget()
        
        self.console_tab = ConsoleTab()
        self.console_tab.execute_command_signal.connect(self._run_ssh_command)
        
        self.explorer_tab = ExplorerTab()
        self.explorer_tab.request_list_signal.connect(lambda path: self._run_sftp('list', path))
        self.explorer_tab.request_download_signal.connect(lambda remote, local: self._run_sftp('download', remote, local))
        self.explorer_tab.request_upload_signal.connect(lambda remote, local: self._run_sftp('upload', remote, local))
        self.explorer_tab.request_delete_signal.connect(lambda remote: self._run_sftp('delete', remote))
        
        self.monitor_tab = MonitorTab()
        self.monitor_tab.request_ps_signal.connect(self._run_monitor_command)
        
        self.tabs.addTab(self.console_tab, "Interactive Console")
        self.tabs.addTab(self.explorer_tab, "SFTP Explorer")
        self.tabs.addTab(self.monitor_tab, "Process Monitor")
        
        layout.addWidget(self.tabs)

    def init_tunnel(self):
        self.tunnel = TunnelManager()
        self.tunnel.connected_signal.connect(self._on_device_connected)
        self.tunnel.disconnected_signal.connect(self._on_device_disconnected)
        self.tunnel.log_signal.connect(self.console_tab.append_output)
        self.tunnel.start()

    def _on_device_connected(self, port):
        self.port = port
        self.status_label.setText(f"Connected [Port {port}]")
        self.status_label.setStyleSheet("background-color: #00aa00; color: white; font-weight: bold; padding: 5px;")
        # Auto-refresh explorer
        self._run_sftp('list', self.explorer_tab.current_path)

    def _on_device_disconnected(self):
        self.status_label.setText("Offline")
        self.status_label.setStyleSheet("background-color: #aa0000; color: white; font-weight: bold; padding: 5px;")
        self.explorer_tab.tree.clear()

    def _cleanup_workers(self):
        self.workers = [w for w in self.workers if w.isRunning()]

    def _run_ssh_command(self, cmd):
        if not self.tunnel.is_connected:
            self.console_tab.append_error("Not connected.")
            return
            
        self.console_tab.append_output(f"\n> {cmd}")
        worker = SSHWorker(self.host, self.port, self.username, self.password, cmd)
        worker.output_signal.connect(self.console_tab.append_output)
        worker.error_signal.connect(self.console_tab.append_error)
        worker.finished_signal.connect(self._cleanup_workers)
        self.workers.append(worker)
        worker.start()

    def _run_monitor_command(self, cmd):
        if not self.tunnel.is_connected:
            return
            
        worker = SSHWorker(self.host, self.port, self.username, self.password, cmd)
        worker.output_signal.connect(self.monitor_tab.update_table)
        worker.finished_signal.connect(self._cleanup_workers)
        self.workers.append(worker)
        worker.start()

    def _run_sftp(self, action, remote_path, local_path=None):
        if not self.tunnel.is_connected:
            self.console_tab.append_error("SFTP: Not connected.")
            return
            
        worker = SFTPWorker(self.host, self.port, self.username, self.password, action, remote_path, local_path)
        if action == 'list':
            worker.list_result_signal.connect(self.explorer_tab.populate_tree)
        elif action in ('upload', 'download', 'delete'):
            worker.finished_signal.connect(lambda: self._run_sftp('list', self.explorer_tab.current_path))
            
        worker.error_signal.connect(self.console_tab.append_error)
        worker.finished_signal.connect(self._cleanup_workers)
        self.workers.append(worker)
        worker.start()

    def closeEvent(self, event):
        self.console_tab.append_output("Shutting down...")
        self.tunnel.stop()
        for worker in self.workers:
            if worker.isRunning():
                worker.terminate()
                worker.wait()
        event.accept()
