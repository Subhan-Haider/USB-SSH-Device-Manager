"""
gui/main_window.py
──────────────────
Application shell that wires TunnelWorker and worker thread signals to the UI.

Threading contract
------------------
* ``TunnelWorker`` runs its polling loop on its own QThread.
* Every SSH and SFTP operation is dispatched to a new ``SSHWorker`` /
  ``SFTPWorker`` QThread.
* **All UI mutations happen exclusively via Qt signal→slot connections.**
  No worker thread ever touches a widget directly.
* ``closeEvent`` blocks until both the tunnel thread and all active workers
  have finished, preventing dangling threads at interpreter shutdown.
"""

import os

from PyQt6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt

from gui.tabs.console  import ConsoleTab
from gui.tabs.explorer import ExplorerTab
from gui.tabs.monitor  import MonitorTab
from gui.tabs.dashboard import DashboardTab
from core.tunnel_manager import TunnelWorker
from core.ssh_client     import SSHWorker
from core.sftp_client    import SFTPWorker

# ── Ensure bundled libimobiledevice binaries are on PATH ──────────────────────
_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS = os.path.join(_ROOT, "tools")
_TOOLS_SIBLING = os.path.join(
    os.path.dirname(_ROOT), "USB_SSH_Manager", "tools"
)
for _td in (_TOOLS, _TOOLS_SIBLING):
    if os.path.isdir(_td) and _td not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _td + os.pathsep + os.environ.get("PATH", "")
        break


class MainWindow(QMainWindow):
    """
    Top-level application window.

    Owns the ``TunnelWorker`` instance and maintains a list of active SSH /
    SFTP worker threads so they can all be cleanly terminated on exit.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("NexusDeviceManager")
        self.resize(900, 650)

        # ── SSH connection parameters ──────────────────────────────────────
        self.host:     str = "localhost"
        self.port:     int = 2222
        self.username: str = "root"
        self.password: str = "alpine"

        # Active worker threads; pruned when each emits finished_signal
        self._workers: list[SSHWorker | SFTPWorker] = []

        self._init_ui()
        self._init_tunnel()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # ── Device status badge ────────────────────────────────────────────
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_status_offline()
        layout.addWidget(self.status_label)

        # ── Tab container ──────────────────────────────────────────────────
        self.tabs = QTabWidget()

        # Console tab – receives all log and error output
        self.console_tab = ConsoleTab()
        self.console_tab.execute_command_signal.connect(self._run_ssh_command)

        # SFTP Explorer tab
        self.explorer_tab = ExplorerTab()
        self.explorer_tab.request_list_signal.connect(
            lambda path: self._run_sftp("list", path)
        )
        self.explorer_tab.request_download_signal.connect(
            lambda remote, local: self._run_sftp("download", remote, local)
        )
        self.explorer_tab.request_upload_signal.connect(
            lambda remote, local: self._run_sftp("upload", remote, local)
        )
        self.explorer_tab.request_delete_signal.connect(
            lambda remote: self._run_sftp("delete", remote)
        )

        # Process monitor tab
        self.monitor_tab = MonitorTab()
        self.monitor_tab.request_ps_signal.connect(self._run_monitor_command)
        
        # Hardware dashboard tab
        self.dashboard_tab = DashboardTab()
        self.dashboard_tab.scan_error.connect(self.console_tab.append_error)

        self.tabs.addTab(self.dashboard_tab, "Hardware Dashboard")
        self.tabs.addTab(self.console_tab, "Interactive Console")
        self.tabs.addTab(self.explorer_tab, "SFTP Explorer")
        self.tabs.addTab(self.monitor_tab, "Process Monitor")

        layout.addWidget(self.tabs)

    # ── Status badge helpers ──────────────────────────────────────────────────

    def _set_status_online(self, port: int) -> None:
        self.status_label.setText(f"⬤  Connected  –  localhost:{port}")
        self.status_label.setStyleSheet(
            "background:#005500; color:#aaffaa;"
            "font-weight:bold; padding:5px;"
        )

    def _set_status_offline(self) -> None:
        self.status_label.setText("⬤  No Device  –  Waiting for USB connection…")
        self.status_label.setStyleSheet(
            "background:#550000; color:#ffaaaa;"
            "font-weight:bold; padding:5px;"
        )

    # ── Tunnel initialisation ─────────────────────────────────────────────────

    def _init_tunnel(self) -> None:
        """Create and start the TunnelWorker; connect its signals to UI slots."""
        self.tunnel = TunnelWorker()

        # Single consolidated signal handler per the architecture spec
        self.tunnel.connection_status_changed.connect(self._on_connection_status)

        # Forward all tunnel log messages to the console tab
        self.tunnel.log_signal.connect(self.console_tab.append_output)

        self.tunnel.start()

    # ── Tunnel signal slot ────────────────────────────────────────────────────

    def _on_connection_status(self, connected: bool, port: int) -> None:
        """
        Slot for ``TunnelWorker.connection_status_changed``.

        ``connected=True``  → device bridged; update badge and auto-refresh
                              the SFTP explorer.
        ``connected=False`` → device removed; clear explorer and go offline.
        """
        if connected:
            self.port = port
            self._set_status_online(port)
            self.console_tab.append_output(
                f"[MainWindow] Tunnel established on localhost:{port}."
            )
            self.dashboard_tab.on_device_connected()
            # Auto-populate explorer on connect
            self._run_sftp("list", self.explorer_tab.current_path)
        else:
            self._set_status_offline()
            self.console_tab.append_output(
                "[MainWindow] Device disconnected – tunnel stopped."
            )
            self.dashboard_tab.on_device_disconnected()
            self.explorer_tab.tree.clear()

    # ── Worker thread dispatch ────────────────────────────────────────────────

    def _purge_finished_workers(self) -> None:
        """Drop references to workers that have already exited."""
        self._workers = [w for w in self._workers if w.isRunning()]

    def _run_ssh_command(self, cmd: str) -> None:
        """
        Dispatch a shell command to a new SSHWorker.
        Output is streamed line-by-line to the console via ``log_received``.
        """
        if not self.tunnel.is_connected:
            self.console_tab.append_error(
                "[MainWindow] Not connected – waiting for device."
            )
            return

        worker = SSHWorker(
            self.host, self.port, self.username, self.password, cmd
        )
        # log_received delivers output line-by-line as it arrives
        worker.log_received.connect(self.console_tab.append_output)
        worker.error_signal.connect(self.console_tab.append_error)
        worker.finished_signal.connect(self._purge_finished_workers)
        self._workers.append(worker)
        worker.start()

    def _run_monitor_command(self, cmd: str) -> None:
        """
        Run a process-listing command and pass the buffered result to
        ``MonitorTab.update_table``.

        Lines are collected in a local buffer on the worker thread, then
        joined and emitted once via ``finished_signal`` so the table is
        updated atomically rather than row-by-row.
        """
        if not self.tunnel.is_connected:
            return

        worker = SSHWorker(
            self.host, self.port, self.username, self.password, cmd
        )

        # Accumulate streamed lines and flush to update_table on completion
        _buf: list[str] = []
        worker.log_received.connect(_buf.append)
        worker.finished_signal.connect(
            lambda: self.monitor_tab.update_table("\n".join(_buf))
        )
        worker.finished_signal.connect(self._purge_finished_workers)
        self._workers.append(worker)
        worker.start()

    def _run_sftp(
        self,
        action:      str,
        remote_path: str,
        local_path:  str | None = None,
    ) -> None:
        """Dispatch an SFTP operation to a new SFTPWorker."""
        if not self.tunnel.is_connected:
            self.console_tab.append_error("[MainWindow] SFTP: not connected.")
            return

        worker = SFTPWorker(
            self.host, self.port, self.username, self.password,
            action, remote_path, local_path,
        )

        if action == "list":
            worker.list_result_signal.connect(self.explorer_tab.populate_tree)
        elif action in ("upload", "download", "delete"):
            # Refresh the current directory after any mutating operation
            worker.finished_signal.connect(
                lambda: self._run_sftp("list", self.explorer_tab.current_path)
            )

        worker.error_signal.connect(self.console_tab.append_error)
        worker.finished_signal.connect(self._purge_finished_workers)
        self._workers.append(worker)
        worker.start()

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """
        Override closeEvent to guarantee clean shutdown of all background
        threads before the Python interpreter exits.

        Order of operations
        -------------------
        1. Notify the user.
        2. Stop the TunnelWorker polling loop and kill iproxy (blocks ≤ 5 s).
        3. Terminate every active SSH/SFTP worker (blocks ≤ 2 s each).
        4. Accept the close event.
        """
        self.console_tab.append_output("[MainWindow] Shutting down…")

        # Stop tunnel polling loop and kill the iproxy subprocess
        self.tunnel.stop()

        # Terminate any SSH/SFTP workers still in flight
        for worker in list(self._workers):
            if worker.isRunning():
                worker.terminate()
                worker.wait(msecs=2_000)

        event.accept()
