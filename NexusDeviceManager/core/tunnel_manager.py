import sys
import subprocess
import time
from PyQt6.QtCore import QThread, pyqtSignal

class TunnelManager(QThread):
    connected_signal = pyqtSignal(int)
    disconnected_signal = pyqtSignal()
    log_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.iproxy_process = None
        self.is_connected = False
        self.local_port = 2222

    def run(self):
        while self.running:
            device_present = self._check_device()
            
            if device_present and not self.is_connected:
                self._start_tunnel()
            elif not device_present and self.is_connected:
                self._stop_tunnel()
                
            time.sleep(2)  # Poll every 2 seconds

    def _check_device(self):
        try:
            # We use ideviceinfo to check for connected devices
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                
            result = subprocess.run(["ideviceinfo"], capture_output=True, text=True, **kwargs)
            # If ideviceinfo succeeds and outputs some XML or keys, it usually means device is connected.
            # Usually exit code is 0 when a device is attached, and non-zero when not.
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            # ideviceinfo not found. Maybe we should emit an error, but let's just avoid crashing.
            pass
        except Exception:
            pass
        return False

    def _start_tunnel(self):
        self.log_signal.emit("Device detected. Starting iproxy...")
        cmd = ["iproxy", str(self.local_port), "22"]
        try:
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            self.iproxy_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                **kwargs
            )
            self.is_connected = True
            self.connected_signal.emit(self.local_port)
            self.log_signal.emit(f"Tunnel established on port {self.local_port}.")
        except Exception as e:
            self.log_signal.emit(f"Failed to start iproxy: {e}")

    def _stop_tunnel(self):
        self.log_signal.emit("Device disconnected. Stopping iproxy...")
        if self.iproxy_process:
            self.iproxy_process.terminate()
            try:
                self.iproxy_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.iproxy_process.kill()
            self.iproxy_process = None
        self.is_connected = False
        self.disconnected_signal.emit()
        self.log_signal.emit("Tunnel stopped.")

    def stop(self):
        self.running = False
        self._stop_tunnel()
        self.wait()
