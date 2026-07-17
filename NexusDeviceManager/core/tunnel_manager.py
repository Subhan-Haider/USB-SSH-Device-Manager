"""
core/tunnel_manager.py
──────────────────────
Persistent hardware-polling QThread that manages the iproxy tunnel subprocess.

Design decisions
----------------
* A single ``connection_status_changed(bool, int)`` signal replaces the
  previous split connected/disconnected pair so callers only need one handler.
* ``_find_free_port`` tries the preferred port first and falls back to an
  OS-assigned ephemeral port, avoiding "address already in use" crashes.
* iproxy stdout is drained on a daemon thread so the OS pipe buffer never
  fills and the poll loop is never blocked by subprocess I/O.
* A ``TunnelManager`` alias is exported for backward compatibility.
"""

import os
import sys
import socket
import subprocess
import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal

# ── Locate bundled libimobiledevice binaries ──────────────────────────────────
# Search order:  <project>/tools/  →  sibling USB_SSH_Manager/tools/
_HERE         = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_TOOLS_DIRS   = [
    os.path.join(_PROJECT_ROOT, "tools"),
    os.path.join(os.path.dirname(_PROJECT_ROOT), "USB_SSH_Manager", "tools"),
]
for _td in _TOOLS_DIRS:
    if os.path.isdir(_td) and _td not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _td + os.pathsep + os.environ.get("PATH", "")
        break


# ── Utility ───────────────────────────────────────────────────────────────────

def _find_free_port(preferred: int = 2222) -> int:
    """
    Return ``preferred`` if it is not already in use, otherwise ask the OS for
    an available ephemeral port.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


# ── Worker thread ─────────────────────────────────────────────────────────────

class TunnelWorker(QThread):
    """
    Background QThread that polls for a connected iOS device and automatically
    starts/stops an ``iproxy`` port-forwarding process.

    Signals
    -------
    connection_status_changed(bool, int)
        Emitted whenever the tunnel state transitions.
        ``True``  → tunnel established; ``int`` is the local port.
        ``False`` → tunnel stopped;     ``int`` is 0.
    log_signal(str)
        Human-readable status/diagnostic messages for the UI console.
    """

    # Primary signal per architecture spec
    connection_status_changed = pyqtSignal(bool, int)

    # Legacy signals kept for backward-compatibility with any existing slots
    connected_signal    = pyqtSignal(int)
    disconnected_signal = pyqtSignal()

    # Log messages forwarded to the console tab
    log_signal = pyqtSignal(str)

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running: bool = False
        self._iproxy_proc: subprocess.Popen | None  = None
        self._iproxy_reader: threading.Thread | None = None

        # Exposed as a flag so MainWindow can guard SSH launches
        self.is_connected: bool = False
        self.local_port:   int  = 2222

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _popen_kwargs() -> dict:
        """Suppress the CMD console popup on Windows."""
        kw: dict = {}
        if sys.platform == "win32":
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        return kw

    def _check_device(self) -> bool:
        """
        Run ``ideviceinfo`` and return True if a device is attached.
        Returns False silently when the binary is absent (not an error).
        """
        try:
            result = subprocess.run(
                ["ideviceinfo"],
                capture_output=True,
                text=True,
                timeout=3,
                **self._popen_kwargs(),
            )
            return result.returncode == 0
        except FileNotFoundError:
            # ideviceinfo not available yet; suppress repeated noise
            pass
        except subprocess.TimeoutExpired:
            pass
        except Exception as exc:
            self.log_signal.emit(f"[TunnelWorker] Device check error: {exc}")
        return False

    def _start_tunnel(self) -> None:
        """Allocate a port, spawn iproxy, and emit the connected signal."""
        self.local_port = _find_free_port(2222)
        self.log_signal.emit(
            f"[TunnelWorker] Device detected – starting iproxy "
            f"on localhost:{self.local_port}…"
        )

        try:
            self._iproxy_proc = subprocess.Popen(
                ["iproxy", str(self.local_port), "22"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                **self._popen_kwargs(),
            )
        except FileNotFoundError:
            self.log_signal.emit(
                "[TunnelWorker] 'iproxy' not found. "
                "Place libimobiledevice binaries in tools/ or add them to PATH."
            )
            return
        except Exception as exc:
            self.log_signal.emit(f"[TunnelWorker] Failed to start iproxy: {exc}")
            return

        # Drain iproxy stdout on a daemon thread to prevent pipe-buffer stalls
        self._iproxy_reader = threading.Thread(
            target=self._drain_iproxy, daemon=True, name="iproxy-reader"
        )
        self._iproxy_reader.start()

        self.is_connected = True

        # Emit consolidated signal then legacy aliases
        self.connection_status_changed.emit(True, self.local_port)
        self.connected_signal.emit(self.local_port)
        self.log_signal.emit(
            f"[TunnelWorker] Tunnel active on localhost:{self.local_port}."
        )

    def _drain_iproxy(self) -> None:
        """
        Read iproxy's combined stdout/stderr line-by-line and forward each
        non-empty line to ``log_signal``.  Runs on a daemon thread.
        """
        proc = self._iproxy_proc
        if proc is None or proc.stdout is None:
            return
        try:
            for raw in proc.stdout:
                line = raw.rstrip()
                if line:
                    self.log_signal.emit(f"[iproxy] {line}")
        except Exception:
            pass  # Process was killed – this is expected during stop().
        self.log_signal.emit("[TunnelWorker] iproxy process exited.")

    def _stop_tunnel(self) -> None:
        """Terminate the iproxy process and emit the disconnected signal."""
        if self._iproxy_proc is not None:
            self.log_signal.emit("[TunnelWorker] Stopping iproxy…")
            try:
                self._iproxy_proc.terminate()
                self._iproxy_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._iproxy_proc.kill()
            except Exception as exc:
                self.log_signal.emit(f"[TunnelWorker] Error stopping iproxy: {exc}")
            finally:
                self._iproxy_proc = None

        if self.is_connected:
            self.is_connected = False
            self.connection_status_changed.emit(False, 0)
            self.disconnected_signal.emit()
            self.log_signal.emit("[TunnelWorker] Tunnel stopped.")

    # ── QThread entry point ───────────────────────────────────────────────────

    def run(self) -> None:
        """
        Device polling loop.  Runs entirely off the GUI thread.
        Wakes every 2 seconds to check whether a device is present.
        """
        self._running = True
        self.log_signal.emit("[TunnelWorker] Polling for device…")

        while self._running:
            device_present = self._check_device()

            if device_present and not self.is_connected:
                self._start_tunnel()
            elif not device_present and self.is_connected:
                self.log_signal.emit("[TunnelWorker] Device removed.")
                self._stop_tunnel()

            time.sleep(2)

        self.log_signal.emit("[TunnelWorker] Polling loop exited.")

    def stop(self) -> None:
        """
        Signal the polling loop to exit, tear down the iproxy process, and
        block until the thread has fully stopped (up to 5 seconds).
        """
        self._running = False
        self._stop_tunnel()
        self.quit()
        self.wait(msecs=5_000)


# Backward-compatibility alias
TunnelManager = TunnelWorker
