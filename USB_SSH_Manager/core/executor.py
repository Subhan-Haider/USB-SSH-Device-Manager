import paramiko
import threading

class CommandExecutor:
    def __init__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.connected = False

    def connect(self, host, port, username, password, log_callback=None):
        try:
            if log_callback:
                log_callback(f"Connecting to {host}:{port} as {username}...\n")
            self.client.connect(
                hostname=host,
                port=int(port),
                username=username,
                password=password,
                timeout=5
            )
            self.connected = True
            if log_callback:
                log_callback("Connection established successfully.\n")
            return True
        except Exception as e:
            if log_callback:
                log_callback(f"Connection failed: {e}\n")
            return False

    def disconnect(self, log_callback=None):
        if self.connected:
            self.client.close()
            self.connected = False
            if log_callback:
                log_callback("Disconnected.\n")

    def execute_command(self, command, log_callback=None):
        if not self.connected:
            if log_callback:
                log_callback("Not connected to execute command.\n")
            return
            
        try:
            if log_callback:
                log_callback(f"\n> {command}\n")
            stdin, stdout, stderr = self.client.exec_command(command)
            out = stdout.read().decode('utf-8')
            err = stderr.read().decode('utf-8')
            
            if out and log_callback:
                log_callback(out)
            if err and log_callback:
                log_callback(f"ERROR: {err}")
                
        except Exception as e:
            if log_callback:
                log_callback(f"Error executing command: {e}\n")

    def run_diagnostics(self, host, port, username, password, log_callback=None, completion_callback=None):
        def task():
            if self.connect(host, port, username, password, log_callback):
                commands = [
                    "uname -a",
                    "df -h",
                    "ps aux"
                ]
                for cmd in commands:
                    self.execute_command(cmd, log_callback)
                self.disconnect(log_callback)
            if completion_callback:
                completion_callback()
                
        threading.Thread(target=task, daemon=True).start()
