import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Apply global stylesheet for a basic dark theme
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #2b2b2b;
            color: #d4d4d4;
        }
        QTabWidget::pane {
            border: 1px solid #444;
        }
        QTabBar::tab {
            background: #3c3f41;
            padding: 8px;
            border: 1px solid #444;
        }
        QTabBar::tab:selected {
            background: #4b6eaf;
        }
        QHeaderView::section {
            background-color: #3c3f41;
            padding: 4px;
            border: 1px solid #444;
        }
        QPushButton {
            background-color: #3c3f41;
            border: 1px solid #555;
            padding: 5px;
        }
        QPushButton:hover {
            background-color: #4b6eaf;
        }
        QLineEdit {
            background-color: #3c3f41;
            border: 1px solid #555;
            padding: 4px;
        }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
