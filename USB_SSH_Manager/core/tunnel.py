import subprocess
import threading
import sys
import os

class TunnelManager:
    def __init__(self):
        self.process = None
        self.running = False

    def start_tunnel(self, local_port=2222, remote_port=22, log_callback=None):
        if self.process is not None:
            if log_callback:
                log_callback("Tunnel is already running.\n")
            return

        cmd = ["iproxy", str(local_port), str(remote_port)]
        
        try:
            # Prevent command window from popping up on Windows
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                **kwargs
            )
            self.running = True
            if log_callback:
                log_callback(f"Started tunnel on port {local_port} -> {remote_port}\n")
                
            # Start a thread to read output so it doesn't block
            def read_output():
                for line in self.process.stdout:
                    if log_callback:
                        log_callback(f"[iproxy] {line}")
                self.running = False
                if log_callback:
                    log_callback("Tunnel process exited.\n")
                    
            threading.Thread(target=read_output, daemon=True).start()
            
        except FileNotFoundError:
            if log_callback:
                log_callback("Error: 'iproxy' not found in PATH. Make sure libimobiledevice is installed.\n")
            self.running = False
        except Exception as e:
            if log_callback:
                log_callback(f"Failed to start tunnel: {e}\n")
            self.running = False

    def stop_tunnel(self, log_callback=None):
        if self.process:
            if log_callback:
                log_callback("Stopping tunnel process...\n")
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            self.running = False
            if log_callback:
                log_callback("Tunnel stopped.\n")
