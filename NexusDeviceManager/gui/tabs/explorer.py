from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QMenu, QFileDialog, QHBoxLayout, QPushButton, QInputDialog
from PyQt6.QtCore import Qt, pyqtSignal

class ExplorerTab(QWidget):
    request_list_signal = pyqtSignal(str)
    request_download_signal = pyqtSignal(str, str)
    request_upload_signal = pyqtSignal(str, str)
    request_delete_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = "/var"
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        nav_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._refresh)
        
        self.btn_up = QPushButton("Up")
        self.btn_up.clicked.connect(self._go_up)
        
        nav_layout.addWidget(self.btn_up)
        nav_layout.addWidget(self.btn_refresh)
        nav_layout.addStretch()
        layout.addLayout(nav_layout)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Size", "Permissions"])
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.tree)

    def _refresh(self):
        self.request_list_signal.emit(self.current_path)

    def _go_up(self):
        import posixpath
        self.current_path = posixpath.dirname(self.current_path)
        if not self.current_path:
            self.current_path = "/"
        self._refresh()

    def _on_double_click(self, item, column):
        is_dir = item.data(0, Qt.ItemDataRole.UserRole)
        if is_dir:
            import posixpath
            name = item.text(0)
            if name == "..":
                self._go_up()
            else:
                self.current_path = posixpath.join(self.current_path, name)
                self._refresh()

    def _show_context_menu(self, position):
        item = self.tree.itemAt(position)
        if not item:
            return

        is_dir = item.data(0, Qt.ItemDataRole.UserRole)
        name = item.text(0)
        import posixpath
        remote_file_path = posixpath.join(self.current_path, name)

        menu = QMenu()
        download_action = menu.addAction("Download")
        upload_action = menu.addAction("Upload File Here")
        delete_action = menu.addAction("Delete")

        action = menu.exec(self.tree.viewport().mapToGlobal(position))

        if action == download_action and not is_dir:
            local_path, _ = QFileDialog.getSaveFileName(self, "Save File", name)
            if local_path:
                self.request_download_signal.emit(remote_file_path, local_path)
        elif action == upload_action:
            local_path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
            if local_path:
                import os
                filename = os.path.basename(local_path)
                target_path = posixpath.join(self.current_path, filename)
                self.request_upload_signal.emit(target_path, local_path)
        elif action == delete_action:
            self.request_delete_signal.emit(remote_file_path)

    def populate_tree(self, files):
        self.tree.clear()
        
        # Add a parent dir item
        up_item = QTreeWidgetItem(["..", "", ""])
        up_item.setData(0, Qt.ItemDataRole.UserRole, True)
        self.tree.addTopLevelItem(up_item)
        
        for f in files:
            item = QTreeWidgetItem([f['name'], str(f['size']), f['permissions']])
            item.setData(0, Qt.ItemDataRole.UserRole, f['is_dir'])
            # Can add icons here if needed
            self.tree.addTopLevelItem(item)
