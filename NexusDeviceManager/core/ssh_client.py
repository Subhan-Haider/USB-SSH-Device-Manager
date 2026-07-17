import paramiko
from PyQt6.QtCore import QThread, pyqtSignal

class SSHWorker(QThread):
    output_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, host, port, username, password, command, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.command = command

    def run(self):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=5
            )
            stdin, stdout, stderr = client.exec_command(self.command)
            out = stdout.read().decode('utf-8', errors='replace')
            err = stderr.read().decode('utf-8', errors='replace')
            
            if out:
                self.output_signal.emit(out)
            if err:
                self.error_signal.emit(err)
        except Exception as e:
            self.error_signal.emit(f"SSH Exception: {e}")
        finally:
            client.close()
            self.finished_signal.emit()
