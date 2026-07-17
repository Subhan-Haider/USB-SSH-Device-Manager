import paramiko
from PyQt6.QtCore import QThread, pyqtSignal

class SFTPWorker(QThread):
    list_result_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal()

    def __init__(self, host, port, username, password, action, remote_path, local_path=None, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.action = action  # 'list', 'download', 'upload', 'delete'
        self.remote_path = remote_path
        self.local_path = local_path

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
            sftp = client.open_sftp()
            
            if self.action == 'list':
                attributes = sftp.listdir_attr(self.remote_path)
                # Parse attributes into a generic list of dicts
                result = []
                for attr in attributes:
                    import stat
                    is_dir = stat.S_ISDIR(attr.st_mode)
                    result.append({
                        'name': attr.filename,
                        'size': attr.st_size,
                        'is_dir': is_dir,
                        'permissions': stat.filemode(attr.st_mode)
                    })
                # Sort: dirs first, then alphabetical
                result.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
                self.list_result_signal.emit(result)
                
            elif self.action == 'download':
                def progress_cb(transferred, total):
                    self.progress_signal.emit(transferred, total)
                sftp.get(self.remote_path, self.local_path, callback=progress_cb)
                
            elif self.action == 'upload':
                def progress_cb(transferred, total):
                    self.progress_signal.emit(transferred, total)
                sftp.put(self.local_path, self.remote_path, callback=progress_cb)
                
            elif self.action == 'delete':
                sftp.remove(self.remote_path)
                
            sftp.close()
        except Exception as e:
            self.error_signal.emit(f"SFTP Error: {e}")
        finally:
            client.close()
            self.finished_signal.emit()
